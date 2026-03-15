from dataclasses import dataclass
from datetime import datetime, UTC

from kernel.config import load_kernel_config
from kernel.db import InvariantViolationRecord, KernelDB
from kernel.godot_validator import GodotValidator
from kernel.invariants import (
    ValidationResult,
    check_confidence_threshold,
    check_required_ledger_entry,
    check_retry_limit,
)
from kernel.ledger import DecisionLedger
from kernel.structure import ProjectStructureAnalyzer


@dataclass(frozen=True)
class InvariantExecution:
    name: str
    result: ValidationResult
    file: str


class EvaluationPipeline:
    def __init__(self, db: KernelDB | None = None):
        self._db = db or KernelDB()
        self._analyzer = ProjectStructureAnalyzer()
        self._godot_validator = GodotValidator(db=self._db)
        self._ledger = DecisionLedger(db=self._db)

    def _record_violation_if_present(
        self,
        invariant_name: str,
        file_name: str,
        message: str,
        severity: int,
        timestamp: str,
        run_id: str | None = None,
    ) -> None:
        invariant_id = self._db.get_invariant_id(invariant_name)
        if invariant_id is None:
            return
        self._db.record_invariant_violation(
            InvariantViolationRecord(
                invariant_id=invariant_id,
                file=file_name,
                description=message,
                severity=severity,
                timestamp=timestamp,
                run_id=run_id,
            )
        )

    def evaluate_task_attempt(
        self,
        task_id: int,
        output_summary: str,
        confidence: float,
        decision_id: int,
        artifact_scope: list[str] | None = None,
        run_id: str | None = None,
    ) -> bool:
        self._db.initialize()
        attempt_number = self._db.get_next_attempt_number(task_id)
        project_root = load_kernel_config().project_root
        sandbox_project_path = project_root / "projects" / "sandbox_project"
        structure_report = self._analyzer.generate_structure_report(sandbox_project_path)

        checks: list[InvariantExecution] = []

        large_files = structure_report["large_files"]
        if large_files:
            first_large_file = large_files[0]
            checks.append(
                InvariantExecution(
                    name="check_no_large_python_files",
                    result={
                        "passed": False,
                        "severity": 2,
                        "message": (
                            "Python file size invariant failed: "
                            f"{first_large_file['file']} exceeds 500 lines "
                            f"({first_large_file['lines']} lines)."
                        ),
                    },
                    file=str(first_large_file["file"]),
                )
            )
        else:
            checks.append(
                InvariantExecution(
                    name="check_no_large_python_files",
                    result={
                        "passed": True,
                        "severity": 0,
                        "message": "All Python files are within maximum line count.",
                    },
                    file="workspace",
                )
            )

        cycles = structure_report["circular_dependencies"]
        if cycles:
            cycle_text = "; ".join(" -> ".join(cycle + [cycle[0]]) for cycle in cycles if cycle)
            checks.append(
                InvariantExecution(
                    name="check_no_circular_imports",
                    result={
                        "passed": False,
                        "severity": 3,
                        "message": f"Circular import detected: {cycle_text}",
                    },
                    file="workspace",
                )
            )
        else:
            checks.append(
                InvariantExecution(
                    name="check_no_circular_imports",
                    result={
                        "passed": True,
                        "severity": 0,
                        "message": "No circular imports detected.",
                    },
                    file="workspace",
                )
            )

        checks.extend([
            InvariantExecution(
                name="check_required_ledger_entry",
                result=check_required_ledger_entry(),
                file="memory/studio.db",
            ),
            InvariantExecution(
                name="check_confidence_threshold",
                result=check_confidence_threshold(confidence),
                file="task_attempt",
            ),
            InvariantExecution(
                name="check_retry_limit",
                result=check_retry_limit(attempt_number),
                file="task_attempt",
            ),
        ])

        timestamp = datetime.now(UTC).isoformat()
        passed = True

        try:
            ledger_is_valid = self._ledger.validate_change(task_id=task_id, decision_id=decision_id)
        except Exception as exc:
            ledger_is_valid = False
            self._record_violation_if_present(
                invariant_name="check_decision_ledger_reference",
                file_name="decision_ledger",
                message=f"Ledger validation exception: {exc}",
                severity=3,
                timestamp=timestamp,
                run_id=run_id,
            )

        if not ledger_is_valid:
            passed = False
            self._record_violation_if_present(
                invariant_name="check_decision_ledger_reference",
                file_name="decision_ledger",
                message=(
                    "Task attempt rejected: invalid ledger reference "
                    f"for task_id={task_id}, decision_id={decision_id}."
                ),
                severity=3,
                timestamp=timestamp,
                run_id=run_id,
            )

        for check in checks:
            if not check.result["passed"]:
                passed = False
                self._record_violation_if_present(
                    invariant_name=check.name,
                    file_name=check.file,
                    message=check.result["message"],
                    severity=check.result["severity"],
                    timestamp=timestamp,
                    run_id=run_id,
                )

        try:
            godot_results = self._godot_validator.validate_project(sandbox_project_path)
            scoped_results = self._filter_godot_results(godot_results, artifact_scope=artifact_scope)
            self._godot_validator.record_results_in_db(scoped_results, task_id=task_id, run_id=run_id)
            if scoped_results.get("errors"):
                passed = False
        except Exception as exc:
            passed = False
            self._record_violation_if_present(
                invariant_name="check_godot_project_validation",
                file_name="projects/sandbox_project",
                message=f"Godot validation exception: {exc}",
                severity=3,
                timestamp=timestamp,
                run_id=run_id,
            )

        self._db.record_task_attempt(
            task_id=task_id,
            attempt_number=attempt_number,
            output_summary=output_summary,
            success_flag=1 if passed else 0,
            confidence=confidence,
            timestamp=timestamp,
            run_id=run_id,
        )

        return passed

    @staticmethod
    def _filter_godot_results(results: dict, artifact_scope: list[str] | None) -> dict:
        if not artifact_scope:
            return results

        normalized_scope = {
            path.replace("projects/sandbox_project/", "", 1)
            if path.startswith("projects/sandbox_project/")
            else path
            for path in artifact_scope
        }

        filtered_errors = [
            item
            for item in results.get("errors", [])
            if str(item.get("file", "")) in normalized_scope
        ]
        filtered_warnings = [
            item
            for item in results.get("warnings", [])
            if str(item.get("file", "")) in normalized_scope
        ]

        return {
            "total_scenes": int(results.get("total_scenes", 0)),
            "total_scripts": int(results.get("total_scripts", 0)),
            "scenes_loaded": int(results.get("scenes_loaded", 0)),
            "scripts_checked": int(results.get("scripts_checked", 0)),
            "errors": filtered_errors,
            "warnings": filtered_warnings,
        }
