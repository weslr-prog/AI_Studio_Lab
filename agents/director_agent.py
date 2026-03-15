from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
from typing import Any

from kernel.config import load_kernel_config
from kernel.db import InvariantViolationRecord, KernelDB, SQLiteConnectionManager
from kernel.godot_validator import GodotValidator
from kernel.llm_utils import extract_json_from_response
from kernel.model_gateway import ModelGateway
from kernel.structure import ProjectStructureAnalyzer


@dataclass(frozen=True)
class TaskRecord:
    id: int
    description: str
    status: str
    assigned_agent: str
    created_at: str
    completed_at: str | None


class DirectorAgent:
    AGENT_NAME = "director"
    MODEL_NAME = "qwen2.5:7b"
    PROMPT_TEMPLATE = (
        "You are DirectorAgent for AI_STUDIO_LAB.\n"
        "Return ONLY valid JSON. No explanation. No markdown. No commentary.\n"
        "Schema:\n"
        "{{\n"
        '  "plan_summary": "string",\n'
        '  "priorities": ["string"],\n'
        '  "assignments": [{{"task": "string", "assigned_agent": "director|architect|programmer|qa", "ledger_required": true}}],\n'
        '  "proposal_audit": ["string"],\n'
        '  "ledger_notes": ["string"]\n'
        "}}\n"
        "All recommendations must be deterministic and sandbox-safe.\n"
        "Task context:\n{task_context}\n\n"
        "Project status snapshot:\n{status_snapshot}\n"
    )

    def __init__(self, db: KernelDB | None = None):
        self._db = db or KernelDB()
        self._gateway = ModelGateway()
        self.MODEL_NAME = self._gateway.model_for(self.AGENT_NAME)
        self._analyzer = ProjectStructureAnalyzer()
        self._godot = GodotValidator(db=self._db)
        self._logger = logging.getLogger("agents.director")
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
                    file="agents/director_agent.py",
                    description=message,
                    severity=3,
                    timestamp=datetime.now(UTC).isoformat(),
                )
            )
        except Exception:
            return

    def _validate_plan_schema(self, payload: dict[str, Any]) -> None:
        required = ["plan_summary", "priorities", "assignments", "proposal_audit", "ledger_notes"]
        for key in required:
            if key not in payload:
                raise ValueError(f"Missing key in plan JSON: {key}")

        if not isinstance(payload["plan_summary"], str):
            raise ValueError("plan_summary must be string")
        if not isinstance(payload["priorities"], list):
            raise ValueError("priorities must be list")
        if not isinstance(payload["assignments"], list):
            raise ValueError("assignments must be list")
        if not isinstance(payload["proposal_audit"], list):
            raise ValueError("proposal_audit must be list")
        if not isinstance(payload["ledger_notes"], list):
            raise ValueError("ledger_notes must be list")

        allowed_agents = {"director", "architect", "programmer", "qa"}
        for assignment in payload["assignments"]:
            if not isinstance(assignment, dict):
                raise ValueError("assignment entries must be objects")
            if "task" not in assignment or "assigned_agent" not in assignment or "ledger_required" not in assignment:
                raise ValueError("assignment missing required fields")
            if assignment["assigned_agent"] not in allowed_agents:
                raise ValueError("assignment assigned_agent is invalid")
            if not isinstance(assignment["ledger_required"], bool):
                raise ValueError("assignment ledger_required must be bool")

    def _call_ollama_json(self, prompt: str) -> dict[str, Any]:
        generation = self._gateway.generate_json(agent_name=self.AGENT_NAME, prompt=prompt)
        if generation.get("status") == "error":
            return generation

        payload = extract_json_from_response(str(generation["response"]))
        if payload.get("status") == "error":
            return payload
        self._validate_plan_schema(payload)
        return payload

    def _build_status_snapshot(self) -> dict[str, Any]:
        with SQLiteConnectionManager(self._db.db_path) as connection:
            cursor = connection.cursor()
            tasks = cursor.execute(
                """
                SELECT id, description, status, assigned_agent, created_at
                FROM tasks
                ORDER BY id ASC
                """
            ).fetchall()
            drift = cursor.execute(
                """
                SELECT id, description, severity, module
                FROM drift_events
                ORDER BY id ASC
                """
            ).fetchall()
            performance = cursor.execute(
                """
                SELECT agent, success_rate, average_confidence, last_updated
                FROM agent_performance
                ORDER BY agent ASC
                """
            ).fetchall()
            proposals = cursor.execute(
                """
                SELECT id, summary, target_module, proposal_type, risk, confidence, ledger_required
                FROM evolution_proposals
                WHERE approved = 0
                ORDER BY id ASC
                """
            ).fetchall()

        return {
            "tasks": [
                {
                    "id": int(row["id"]),
                    "description": str(row["description"]),
                    "status": str(row["status"]),
                    "assigned_agent": str(row["assigned_agent"]),
                    "created_at": str(row["created_at"]),
                }
                for row in tasks
            ],
            "drift_events": [
                {
                    "id": int(row["id"]),
                    "description": str(row["description"]),
                    "severity": int(row["severity"]),
                    "module": str(row["module"]),
                }
                for row in drift
            ],
            "agent_performance": [
                {
                    "agent": str(row["agent"]),
                    "success_rate": float(row["success_rate"]),
                    "average_confidence": float(row["average_confidence"]),
                    "last_updated": str(row["last_updated"]),
                }
                for row in performance
            ],
            "pending_proposals": [
                {
                    "id": int(row["id"]),
                    "summary": str(row["summary"]),
                    "target_module": str(row["target_module"]),
                    "proposal_type": str(row["proposal_type"]),
                    "risk": str(row["risk"]),
                    "confidence": float(row["confidence"]),
                    "ledger_required": int(row["ledger_required"]),
                }
                for row in proposals
            ],
        }

    def _ledger_enforced(self) -> bool:
        with SQLiteConnectionManager(self._db.db_path) as connection:
            cursor = connection.cursor()
            row = cursor.execute("SELECT COUNT(*) AS count FROM decision_ledger").fetchone()
            return row is not None and int(row["count"]) > 0

    def create_task(self, description: str, assigned_agent: str) -> int:
        self._db.initialize()
        try:
            if not self._ledger_enforced():
                raise ValueError("Ledger enforcement failed: no decision entries available.")

            timestamp = datetime.now(UTC).isoformat()
            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO tasks (
                        description,
                        status,
                        assigned_agent,
                        created_at,
                        completed_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (description, "queued", assigned_agent, timestamp, None),
                )
                row_id = cursor.lastrowid
                if row_id is None:
                    raise ValueError("Failed to create task row.")

            task_id = int(row_id)
            self._log("task_created", {"task_id": task_id, "assigned_agent": assigned_agent})
            return task_id
        except Exception as exc:
            self._record_exception(f"create_task exception: {exc}")
            raise

    def assign_task(self, task_id: int, agent_name: str) -> bool:
        self._db.initialize()
        try:
            if not self._ledger_enforced():
                raise ValueError("Ledger enforcement failed: no decision entries available.")

            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()
                existing = cursor.execute(
                    "SELECT id FROM tasks WHERE id = ? LIMIT 1",
                    (task_id,),
                ).fetchone()
                if existing is None:
                    return False

                cursor.execute(
                    """
                    UPDATE tasks
                    SET assigned_agent = ?, status = ?
                    WHERE id = ?
                    """,
                    (agent_name, "assigned", task_id),
                )

            self._log("task_assigned", {"task_id": task_id, "agent_name": agent_name})
            return True
        except Exception as exc:
            self._record_exception(f"assign_task exception: {exc}")
            return False

    def monitor_progress(self) -> list[dict[str, Any]]:
        self._db.initialize()
        try:
            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()
                rows = cursor.execute(
                    """
                    SELECT
                        id,
                        description,
                        status,
                        assigned_agent,
                        created_at,
                        completed_at
                    FROM tasks
                    ORDER BY id ASC
                    """
                ).fetchall()

            progress: list[dict[str, Any]] = []
            for row in rows:
                record = TaskRecord(
                    id=int(row["id"]),
                    description=str(row["description"]),
                    status=str(row["status"]),
                    assigned_agent=str(row["assigned_agent"]),
                    created_at=str(row["created_at"]),
                    completed_at=str(row["completed_at"]) if row["completed_at"] is not None else None,
                )
                progress.append(
                    {
                        "id": record.id,
                        "description": record.description,
                        "status": record.status,
                        "assigned_agent": record.assigned_agent,
                        "created_at": record.created_at,
                        "completed_at": record.completed_at,
                    }
                )

            self._log("progress_monitored", {"tasks": len(progress)})
            return progress
        except Exception as exc:
            self._record_exception(f"monitor_progress exception: {exc}")
            return []

    def prioritize_tasks(self) -> list[dict[str, Any]]:
        self._db.initialize()
        try:
            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()
                rows = cursor.execute(
                    """
                    SELECT
                        id,
                        description,
                        status,
                        assigned_agent,
                        created_at,
                        completed_at
                    FROM tasks
                    WHERE status != 'completed'
                    ORDER BY created_at ASC, id ASC
                    """
                ).fetchall()

            prioritized: list[dict[str, Any]] = []
            for row in rows:
                prioritized.append(
                    {
                        "id": int(row["id"]),
                        "description": str(row["description"]),
                        "status": str(row["status"]),
                        "assigned_agent": str(row["assigned_agent"]),
                    }
                )

            self._log("tasks_prioritized", {"count": len(prioritized)})
            return prioritized
        except Exception as exc:
            self._record_exception(f"prioritize_tasks exception: {exc}")
            return []

    def generate_task_plan(self, task_context: str) -> dict[str, Any]:
        self._db.initialize()
        try:
            if not self._ledger_enforced():
                raise ValueError("Ledger enforcement failed: no decision entries available.")

            snapshot = self._build_status_snapshot()
            prompt = self.PROMPT_TEMPLATE.format(
                task_context=task_context,
                status_snapshot=json.dumps(snapshot, ensure_ascii=True, sort_keys=True),
            )

            plan = self._call_ollama_json(prompt)
            if plan.get("status") == "error":
                return plan

            config = load_kernel_config()
            structure = self._analyzer.generate_structure_report(config.project_root)
            godot_report = self._godot.validate_project(config.project_root / "projects" / "sandbox_project")
            godot_clean = len(godot_report["errors"]) == 0

            result = {
                "model": self.MODEL_NAME,
                "plan": plan,
                "validation": {
                    "large_files": len(structure["large_files"]),
                    "circular_dependencies": len(structure["circular_dependencies"]),
                    "godot_errors": len(godot_report["errors"]),
                    "godot_warnings": len(godot_report["warnings"]),
                    "passed": len(structure["circular_dependencies"]) == 0 and godot_clean,
                },
            }
            self._log("task_plan_generated", result)
            return result
        except Exception as exc:
            self._record_exception(f"generate_task_plan exception: {exc}")
            raise
