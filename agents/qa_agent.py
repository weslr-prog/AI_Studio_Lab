from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
from typing import Any

from kernel.config import load_kernel_config
from kernel.db import InvariantViolationRecord, KernelDB, SQLiteConnectionManager
from kernel.evaluator import EvaluationPipeline
from kernel.godot_validator import GodotValidator
from kernel.ledger import DecisionLedger
from kernel.structure import ProjectStructureAnalyzer
from kernel.llm_utils import extract_json_from_response
from kernel.model_gateway import ModelGateway


@dataclass(frozen=True)
class ViolationSummary:
    id: int
    file: str
    description: str
    severity: int
    timestamp: str
    run_id: str | None


class QAgent:
    AGENT_NAME = "qa"
    MODEL_NAME = "qwen2.5:7b"
    PROMPT_TEMPLATE = (
        "You are QA Agent for AI_STUDIO_LAB.\n"
        "Return ONLY valid JSON. No explanation. No markdown. No commentary.\n"
        "Schema:\n"
        "{{\n"
        '  "assessment": "string",\n'
        '  "risk_level": "low|medium|high",\n'
        '  "suggestions": ["string"]\n'
        "}}\n"
        "Task id: {task_id}\n"
        "Validation summary:\n{summary}\n"
    )

    def __init__(self, db: KernelDB | None = None):
        self._db = db or KernelDB()
        self._gateway = ModelGateway()
        self.MODEL_NAME = self._gateway.model_for(self.AGENT_NAME)
        self._ledger = DecisionLedger(db=self._db)
        self._evaluator = EvaluationPipeline(db=self._db)
        self._analyzer = ProjectStructureAnalyzer()
        self._godot = GodotValidator(db=self._db)
        self._logger = logging.getLogger("agents.qa")
        self._logger.setLevel(logging.INFO)
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.propagate = False

    def _log(self, event: str, payload: dict[str, Any]) -> None:
        data = {"event": event, **payload}
        self._logger.info(json.dumps(data, ensure_ascii=True, sort_keys=True))

    def _record_exception(self, message: str) -> None:
        try:
            self._db.initialize()
            invariant_id = self._db.get_invariant_id("check_evolution_engine_exception")
            if invariant_id is None:
                return
            self._db.record_invariant_violation(
                InvariantViolationRecord(
                    invariant_id=invariant_id,
                    file="agents/qa_agent.py",
                    description=message,
                    severity=3,
                    timestamp=datetime.now(UTC).isoformat(),
                )
            )
        except Exception:
            return

    def _validate_schema(self, payload: dict[str, Any]) -> None:
        required = ["assessment", "risk_level", "suggestions"]
        for key in required:
            if key not in payload:
                raise ValueError(f"Missing field in QA model output: {key}")
        if not isinstance(payload["assessment"], str):
            raise ValueError("assessment must be string")
        if payload["risk_level"] not in {"low", "medium", "high"}:
            raise ValueError("risk_level must be low|medium|high")
        if not isinstance(payload["suggestions"], list):
            raise ValueError("suggestions must be list")

    def _call_ollama_json(self, prompt: str) -> dict[str, Any]:
        generation = self._gateway.generate_json(agent_name=self.AGENT_NAME, prompt=prompt)
        if generation.get("status") == "error":
            return generation

        payload = extract_json_from_response(str(generation["response"]))
        if payload.get("status") == "error":
            return payload
        self._validate_schema(payload)
        return payload

    def run_validation(self, task_id: int, run_id: str | None = None) -> bool:
        self._db.initialize()
        try:
            decisions = self._ledger.get_decisions()
            if not decisions:
                raise ValueError("No decision entries available for QA validation.")
            decision_id = int(decisions[-1]["id"])
            result = self._evaluator.evaluate_task_attempt(
                task_id=task_id,
                output_summary="QAgent validation pass",
                confidence=0.8,
                decision_id=decision_id,
                run_id=run_id,
            )
            self._log("qa_validation_run", {"task_id": task_id, "passed": result})
            return result
        except Exception as exc:
            self._record_exception(f"run_validation exception: {exc}")
            return False

    def report_violations(self) -> list[dict[str, Any]]:
        self._db.initialize()
        try:
            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()
                rows = cursor.execute(
                    """
                    SELECT id, file, description, severity, timestamp, run_id
                    FROM invariant_violations
                    ORDER BY id ASC
                    """
                ).fetchall()

            violations: list[dict[str, Any]] = []
            for row in rows:
                summary = ViolationSummary(
                    id=int(row["id"]),
                    file=str(row["file"]),
                    description=str(row["description"]),
                    severity=int(row["severity"]),
                    timestamp=str(row["timestamp"]),
                    run_id=str(row["run_id"]) if row["run_id"] is not None else None,
                )
                violations.append(
                    {
                        "id": summary.id,
                        "file": summary.file,
                        "description": summary.description,
                        "severity": summary.severity,
                        "timestamp": summary.timestamp,
                        "run_id": summary.run_id,
                    }
                )

            self._log("violations_reported", {"count": len(violations)})
            return violations
        except Exception as exc:
            self._record_exception(f"report_violations exception: {exc}")
            return []

    @staticmethod
    def _is_at_or_after(timestamp: str, since_timestamp: str) -> bool:
        try:
            return datetime.fromisoformat(timestamp) >= datetime.fromisoformat(since_timestamp)
        except Exception:
            return False

    @staticmethod
    def _task_related_violations(
        task_id: int,
        violations: list[dict[str, Any]],
        since_timestamp: str | None = None,
        run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        marker = f"[task_id={task_id}]"
        related = [item for item in violations if marker in str(item.get("description", ""))]
        if run_id is not None:
            related = [item for item in related if str(item.get("run_id", "")) == run_id]
        if since_timestamp is None:
            return related
        return [
            item
            for item in related
            if QAgent._is_at_or_after(str(item.get("timestamp", "")), since_timestamp)
        ]

    def feed_results_to_director(self, task_id: int) -> dict[str, Any]:
        self._db.initialize()
        try:
            violations = self.report_violations()
            related = [
                item
                for item in violations
                if f"task_id={task_id}" in item["description"] or str(task_id) in item["description"]
            ]
            payload = {
                "task_id": task_id,
                "total_violations": len(violations),
                "related_violations": len(related),
                "status": "reported",
            }
            self._log("results_fed_to_director", payload)
            return payload
        except Exception as exc:
            self._record_exception(f"feed_results_to_director exception: {exc}")
            return {
                "task_id": task_id,
                "total_violations": 0,
                "related_violations": 0,
                "status": "error",
            }

    def analyze_task(self, task_id: int, run_id: str | None = None) -> dict[str, Any]:
        self._db.initialize()
        try:
            run_window_start = datetime.now(UTC).isoformat()
            decisions = self._ledger.get_decisions()
            if not decisions:
                raise ValueError("No decision entries available for QA analysis.")
            decision_id = int(decisions[-1]["id"])

            config = load_kernel_config()
            structure_report = self._analyzer.generate_structure_report(config.project_root)
            godot_report = self._godot.validate_project(config.project_root / "projects" / "sandbox_project")
            self._godot.record_results_in_db(godot_report, task_id=task_id, run_id=run_id)
            violations = self.report_violations()
            task_violations = self._task_related_violations(
                task_id=task_id,
                violations=violations,
                since_timestamp=run_window_start,
                run_id=run_id,
            )

            summary = {
                "task_id": task_id,
                "structure": {
                    "total_files": int(structure_report["total_files"]),
                    "large_files": len(structure_report["large_files"]),
                    "circular_dependencies": len(structure_report["circular_dependencies"]),
                },
                "godot": {
                    "errors": len(godot_report["errors"]),
                    "warnings": len(godot_report["warnings"]),
                },
                "violations_count": len(task_violations),
                "evaluation_window_start": run_window_start,
                "run_id": run_id,
            }

            prompt = self.PROMPT_TEMPLATE.format(
                task_id=task_id,
                summary=json.dumps(summary, ensure_ascii=True, sort_keys=True),
            )
            model_assessment = self._call_ollama_json(prompt)
            if model_assessment.get("status") == "error":
                return model_assessment

            evaluation_passed = self._evaluator.evaluate_task_attempt(
                task_id=task_id,
                output_summary=f"QAgent analysis: {model_assessment['assessment']}",
                confidence=0.8,
                decision_id=decision_id,
                artifact_scope=[
                    "projects/sandbox_project/scenes/Main.tscn",
                    "projects/sandbox_project/scripts/player.gd",
                ],
                run_id=run_id,
            )

            result = {
                "task_id": task_id,
                "model": self.MODEL_NAME,
                "assessment": model_assessment,
                "summary": summary,
                "evaluation_passed": evaluation_passed,
                "overall_passed": evaluation_passed and len(godot_report["errors"]) == 0,
            }
            self._log("qa_task_analyzed", result)
            return result
        except Exception as exc:
            self._record_exception(f"analyze_task exception: {exc}")
            return {
                "task_id": task_id,
                "model": self.MODEL_NAME,
                "assessment": {"assessment": "error", "risk_level": "high", "suggestions": []},
                "summary": {},
                "evaluation_passed": False,
                "overall_passed": False,
            }
