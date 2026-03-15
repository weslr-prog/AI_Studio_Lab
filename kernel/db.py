import sqlite3
from dataclasses import dataclass
from datetime import datetime, UTC
import json
from pathlib import Path
from typing import Any

from kernel.config import KernelConfig, load_kernel_config


TABLES: tuple[str, ...] = (
    "tasks",
    "task_attempts",
    "run_manifests",
    "objective_specs",
    "run_acceptance_results",
    "run_release_readiness",
    "studio_health_snapshots",
    "architectural_decisions",
    "decision_ledger",
    "evolution_proposals",
    "invariants",
    "invariant_violations",
    "commits",
    "drift_events",
    "agent_performance",
)


@dataclass(frozen=True)
class InvariantViolationRecord:
    invariant_id: int
    file: str
    description: str
    severity: int
    timestamp: str
    run_id: str | None = None


class SQLiteConnectionManager:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self._connection = sqlite3.connect(self._db_path)
        self._connection.row_factory = sqlite3.Row
        return self._connection

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        if self._connection is None:
            return
        if exc_type is None:
            self._connection.commit()
        else:
            self._connection.rollback()
        self._connection.close()
        self._connection = None


class KernelDB:
    def __init__(self, config: KernelConfig | None = None):
        self._config = config or load_kernel_config()

    @property
    def db_path(self) -> Path:
        return self._config.db_path

    def initialize(self) -> None:
        self._config.memory_dir.mkdir(parents=True, exist_ok=True)
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY,
                    description TEXT,
                    status TEXT,
                    assigned_agent TEXT,
                    created_at TEXT,
                    completed_at TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS task_attempts (
                    id INTEGER PRIMARY KEY,
                    task_id INTEGER,
                    attempt_number INTEGER,
                    output_summary TEXT,
                    success_flag INTEGER,
                    confidence REAL,
                    timestamp TEXT,
                    run_id TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS run_manifests (
                    id INTEGER PRIMARY KEY,
                    run_id TEXT,
                    task_id INTEGER,
                    task TEXT,
                    assigned_agent TEXT,
                    created_at TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS objective_specs (
                    id INTEGER PRIMARY KEY,
                    run_id TEXT,
                    objective TEXT,
                    objective_type TEXT,
                    spec_json TEXT,
                    created_at TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS run_acceptance_results (
                    id INTEGER PRIMARY KEY,
                    run_id TEXT,
                    check_name TEXT,
                    passed INTEGER,
                    detail TEXT,
                    timestamp TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS run_release_readiness (
                    id INTEGER PRIMARY KEY,
                    run_id TEXT,
                    passed INTEGER,
                    snapshot_json TEXT,
                    timestamp TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS studio_health_snapshots (
                    id INTEGER PRIMARY KEY,
                    snapshot_json TEXT,
                    timestamp TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS architectural_decisions (
                    id INTEGER PRIMARY KEY,
                    problem TEXT,
                    context TEXT,
                    options TEXT,
                    chosen TEXT,
                    tradeoffs TEXT,
                    risks TEXT,
                    confidence REAL,
                    agent TEXT,
                    timestamp TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_ledger (
                    id INTEGER PRIMARY KEY,
                    problem TEXT,
                    context TEXT,
                    options TEXT,
                    chosen TEXT,
                    tradeoffs TEXT,
                    risks TEXT,
                    confidence REAL,
                    agent TEXT,
                    timestamp TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS evolution_proposals (
                    id INTEGER PRIMARY KEY,
                    summary TEXT,
                    target_module TEXT,
                    proposal_type TEXT,
                    risk TEXT,
                    confidence REAL,
                    simulated_outcome TEXT,
                    ledger_required INTEGER,
                    approved INTEGER DEFAULT 0,
                    timestamp TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS invariants (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    severity INTEGER
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS invariant_violations (
                    id INTEGER PRIMARY KEY,
                    invariant_id INTEGER,
                    file TEXT,
                    description TEXT,
                    severity INTEGER,
                    timestamp TEXT,
                    run_id TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS commits (
                    id INTEGER PRIMARY KEY,
                    summary TEXT,
                    approved INTEGER,
                    timestamp TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS drift_events (
                    id INTEGER PRIMARY KEY,
                    description TEXT,
                    severity INTEGER,
                    module TEXT,
                    timestamp TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_performance (
                    id INTEGER PRIMARY KEY,
                    agent TEXT,
                    success_rate REAL,
                    average_confidence REAL,
                    last_updated TEXT
                )
                """
            )

        self._ensure_optional_columns()
        self._ensure_default_invariants()

    def _ensure_optional_columns(self) -> None:
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()

            task_attempt_columns = {
                str(row["name"])
                for row in cursor.execute("PRAGMA table_info(task_attempts)").fetchall()
            }
            if "run_id" not in task_attempt_columns:
                cursor.execute("ALTER TABLE task_attempts ADD COLUMN run_id TEXT")

            violation_columns = {
                str(row["name"])
                for row in cursor.execute("PRAGMA table_info(invariant_violations)").fetchall()
            }
            if "run_id" not in violation_columns:
                cursor.execute("ALTER TABLE invariant_violations ADD COLUMN run_id TEXT")

    def _ensure_default_invariants(self) -> None:
        defaults = (
            ("check_no_large_python_files", "No Python files exceed max line count", 2),
            ("check_no_circular_imports", "No circular imports in internal modules", 3),
            ("check_required_ledger_entry", "Task attempt output summary is non-empty", 2),
            ("check_confidence_threshold", "Attempt confidence meets minimum threshold", 2),
            ("check_retry_limit", "Attempt number does not exceed retry limit", 3),
            ("check_godot_project_validation", "Godot project scenes/scripts validate headlessly", 3),
            ("check_decision_ledger_reference", "Task attempts must reference valid decision ledger entries", 3),
            ("check_evolution_engine_exception", "Evolution engine exceptions are tracked", 3),
        )
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            for name, description, severity in defaults:
                existing = cursor.execute(
                    "SELECT id FROM invariants WHERE name = ? LIMIT 1", (name,)
                ).fetchone()
                if existing is None:
                    cursor.execute(
                        "INSERT INTO invariants (name, description, severity) VALUES (?, ?, ?)",
                        (name, description, severity),
                    )

    def get_next_attempt_number(self, task_id: int) -> int:
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                "SELECT MAX(attempt_number) AS max_attempt FROM task_attempts WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if row is None or row["max_attempt"] is None:
                return 1
            return int(row["max_attempt"]) + 1

    def record_task_attempt(
        self,
        task_id: int,
        attempt_number: int,
        output_summary: str,
        success_flag: int,
        confidence: float,
        timestamp: str | None = None,
        run_id: str | None = None,
    ) -> None:
        current_timestamp = timestamp or datetime.now(UTC).isoformat()
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO task_attempts (
                    task_id,
                    attempt_number,
                    output_summary,
                    success_flag,
                    confidence,
                    timestamp,
                    run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    attempt_number,
                    output_summary,
                    success_flag,
                    confidence,
                    current_timestamp,
                    run_id,
                ),
            )

    def update_task_status(
        self,
        task_id: int,
        status: str,
        completed_at: str | None = None,
    ) -> bool:
        timestamp = completed_at
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            existing = cursor.execute(
                "SELECT id FROM tasks WHERE id = ? LIMIT 1",
                (task_id,),
            ).fetchone()
            if existing is None:
                return False

            if status in {"completed", "failed"}:
                resolved_completed_at = timestamp or datetime.now(UTC).isoformat()
            else:
                resolved_completed_at = None

            cursor.execute(
                """
                UPDATE tasks
                SET status = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, resolved_completed_at, task_id),
            )
            return True

    def get_invariant_id(self, name: str) -> int | None:
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                "SELECT id FROM invariants WHERE name = ? LIMIT 1", (name,)
            ).fetchone()
            if row is None:
                return None
            return int(row["id"])

    def record_run_manifest_task(
        self,
        run_id: str,
        task_id: int,
        task: str,
        assigned_agent: str,
        created_at: str | None = None,
    ) -> None:
        current_timestamp = created_at or datetime.now(UTC).isoformat()
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO run_manifests (
                    run_id,
                    task_id,
                    task,
                    assigned_agent,
                    created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, task_id, task, assigned_agent, current_timestamp),
            )

    def record_objective_spec(
        self,
        run_id: str,
        objective: str,
        objective_type: str,
        spec_payload: dict[str, Any],
        created_at: str | None = None,
    ) -> None:
        current_timestamp = created_at or datetime.now(UTC).isoformat()
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO objective_specs (
                    run_id,
                    objective,
                    objective_type,
                    spec_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    objective,
                    objective_type,
                    json.dumps(spec_payload, ensure_ascii=True, sort_keys=True),
                    current_timestamp,
                ),
            )

    def get_objective_spec(self, run_id: str) -> dict[str, Any] | None:
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                """
                SELECT objective, objective_type, spec_json, created_at
                FROM objective_specs
                WHERE run_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "objective": str(row["objective"]),
            "objective_type": str(row["objective_type"]),
            "spec": json.loads(str(row["spec_json"])),
            "created_at": str(row["created_at"]),
        }

    def record_run_acceptance_result(
        self,
        run_id: str,
        check_name: str,
        passed: bool,
        detail: str,
        timestamp: str | None = None,
    ) -> None:
        current_timestamp = timestamp or datetime.now(UTC).isoformat()
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO run_acceptance_results (
                    run_id,
                    check_name,
                    passed,
                    detail,
                    timestamp
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, check_name, 1 if passed else 0, detail, current_timestamp),
            )

    def get_run_acceptance_results(self, run_id: str) -> list[dict[str, Any]]:
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            rows = cursor.execute(
                """
                SELECT check_name, passed, detail, timestamp
                FROM run_acceptance_results
                WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()

        return [
            {
                "check": str(row["check_name"]),
                "passed": bool(int(row["passed"])),
                "detail": str(row["detail"]),
                "timestamp": str(row["timestamp"]),
            }
            for row in rows
        ]

    def record_run_release_readiness(
        self,
        run_id: str,
        passed: bool,
        snapshot_payload: dict[str, Any],
        timestamp: str | None = None,
    ) -> None:
        current_timestamp = timestamp or datetime.now(UTC).isoformat()
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO run_release_readiness (
                    run_id,
                    passed,
                    snapshot_json,
                    timestamp
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    run_id,
                    1 if passed else 0,
                    json.dumps(snapshot_payload, ensure_ascii=True, sort_keys=True),
                    current_timestamp,
                ),
            )

    def get_run_release_readiness(self, run_id: str) -> dict[str, Any] | None:
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                """
                SELECT passed, snapshot_json, timestamp
                FROM run_release_readiness
                WHERE run_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()

        if row is None:
            return None
        return {
            "passed": bool(int(row["passed"])),
            "snapshot": json.loads(str(row["snapshot_json"])),
            "timestamp": str(row["timestamp"]),
        }

    def record_health_snapshot(
        self,
        snapshot_payload: dict[str, Any],
        timestamp: str | None = None,
    ) -> None:
        current_timestamp = timestamp or datetime.now(UTC).isoformat()
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO studio_health_snapshots (
                    snapshot_json,
                    timestamp
                ) VALUES (?, ?)
                """,
                (
                    json.dumps(snapshot_payload, ensure_ascii=True, sort_keys=True),
                    current_timestamp,
                ),
            )

    def list_health_snapshots(self, limit: int = 10) -> list[dict[str, Any]]:
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            rows = cursor.execute(
                """
                SELECT snapshot_json, timestamp
                FROM studio_health_snapshots
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "snapshot": json.loads(str(row["snapshot_json"])),
                "timestamp": str(row["timestamp"]),
            }
            for row in rows
        ]

    def record_invariant_violation(self, record: InvariantViolationRecord) -> None:
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO invariant_violations (
                    invariant_id,
                    file,
                    description,
                    severity,
                    timestamp,
                    run_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.invariant_id,
                    record.file,
                    record.description,
                    record.severity,
                    record.timestamp,
                    record.run_id,
                ),
            )

    def has_required_tables(self) -> bool:
        with SQLiteConnectionManager(self._config.db_path) as connection:
            cursor = connection.cursor()
            existing_rows = cursor.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
            existing = {str(row["name"]) for row in existing_rows}
            return all(table in existing for table in TABLES)
