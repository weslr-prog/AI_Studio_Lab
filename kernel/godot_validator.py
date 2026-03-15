from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import subprocess
from typing import Any

from kernel.db import InvariantViolationRecord, KernelDB


class GodotValidator:
    def __init__(self, db: KernelDB | None = None):
        self._db = db or KernelDB()
        self._logger = logging.getLogger("kernel.godot_validator")
        self._logger.setLevel(logging.INFO)
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
            self._logger.propagate = False

    def _log(self, level: str, payload: dict[str, Any]) -> None:
        message = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        if level == "error":
            self._logger.error(message)
        elif level == "warning":
            self._logger.warning(message)
        else:
            self._logger.info(message)

    def _run_godot_check(self, project_path: Path, target_file: Path) -> subprocess.CompletedProcess[str]:
        relative_target = target_file.relative_to(project_path).as_posix()
        if target_file.suffix == ".gd":
            command = [
                "godot",
                "--headless",
                "--path",
                str(project_path),
                "--script",
                relative_target,
                "--check-only",
            ]
        else:
            command = [
                "godot",
                "--headless",
                "--path",
                str(project_path),
                "--scene",
                relative_target,
                "--quit",
            ]
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

    def _is_ignorable_message(self, line: str) -> bool:
        lowered = line.lower()
        ignorable_signatures = [
            "objectdb instances leaked at exit",
            "unrecognized output string \"misc2\" in mapping",
        ]
        return any(signature in lowered for signature in ignorable_signatures)

    def _parse_messages(self, output: str) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if self._is_ignorable_message(line):
                continue
            lowered = line.lower()
            if "error" in lowered:
                errors.append(line)
            elif "warning" in lowered:
                warnings.append(line)
        return errors, warnings

    def _is_excluded_target(self, project_path: Path, target_file: Path) -> bool:
        relative = target_file.relative_to(project_path).as_posix()
        excluded_prefixes = (
            "templates/",
            "template_bootstrap/",
        )
        return any(relative.startswith(prefix) for prefix in excluded_prefixes)

    def validate_project(self, project_path: Path) -> dict:
        resolved_project = project_path.resolve()
        scene_files = sorted(
            file_path
            for file_path in resolved_project.rglob("*.tscn")
            if not self._is_excluded_target(resolved_project, file_path)
        )
        script_files = sorted(
            file_path
            for file_path in resolved_project.rglob("*.gd")
            if not self._is_excluded_target(resolved_project, file_path)
        )
        targets = sorted(scene_files + script_files)

        results: dict[str, Any] = {
            "total_scenes": len(scene_files),
            "total_scripts": len(script_files),
            "scenes_loaded": 0,
            "scripts_checked": 0,
            "errors": [],
            "warnings": [],
        }

        for target in targets:
            relative_file = target.relative_to(resolved_project).as_posix()
            try:
                completed = self._run_godot_check(resolved_project, target)
                stdout_errors, stdout_warnings = self._parse_messages(completed.stdout)
                stderr_errors, stderr_warnings = self._parse_messages(completed.stderr)

                if target.suffix == ".tscn" and completed.returncode == 0 and not stderr_errors:
                    results["scenes_loaded"] += 1
                if target.suffix == ".gd":
                    results["scripts_checked"] += 1

                all_errors = stdout_errors + stderr_errors
                all_warnings = stdout_warnings + stderr_warnings

                if completed.returncode != 0 and not all_errors:
                    all_errors.append(
                        f"Godot command failed with return code {completed.returncode}."
                    )

                for message in all_errors:
                    results["errors"].append({"file": relative_file, "message": message})
                for message in all_warnings:
                    results["warnings"].append({"file": relative_file, "message": message})

                self._log(
                    "info",
                    {
                        "event": "godot_check_completed",
                        "file": relative_file,
                        "returncode": completed.returncode,
                        "errors": len(all_errors),
                        "warnings": len(all_warnings),
                    },
                )
            except Exception as exc:  # explicit capture required by phase rules
                results["errors"].append(
                    {
                        "file": relative_file,
                        "message": f"Exception during validation: {exc}",
                    }
                )
                self._log(
                    "error",
                    {
                        "event": "godot_check_exception",
                        "file": relative_file,
                        "message": str(exc),
                    },
                )

        return results

    def record_results_in_db(
        self,
        results: dict,
        task_id: int | None = None,
        run_id: str | None = None,
    ) -> None:
        self._db.initialize()
        invariant_id = self._db.get_invariant_id("check_godot_project_validation")
        if invariant_id is None:
            return

        timestamp = datetime.now(UTC).isoformat()
        task_prefix = f"[task_id={task_id}] " if task_id is not None else ""

        entries: list[tuple[str, str, int]] = []
        for item in results.get("errors", []):
            entries.append((str(item.get("file", "unknown")), str(item.get("message", "")), 3))
        for item in results.get("warnings", []):
            entries.append((str(item.get("file", "unknown")), str(item.get("message", "")), 1))

        for file_name, message, severity in entries:
            try:
                self._db.record_invariant_violation(
                    InvariantViolationRecord(
                        invariant_id=invariant_id,
                        file=file_name,
                        description=f"{task_prefix}{message}",
                        severity=severity,
                        timestamp=timestamp,
                        run_id=run_id,
                    )
                )
            except Exception as exc:  # explicit capture required by phase rules
                self._log(
                    "error",
                    {
                        "event": "db_record_exception",
                        "file": file_name,
                        "message": str(exc),
                    },
                )
