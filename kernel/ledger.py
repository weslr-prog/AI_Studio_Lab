from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from kernel.db import InvariantViolationRecord, KernelDB, SQLiteConnectionManager


@dataclass(frozen=True)
class DecisionEntry:
    id: int
    problem: str
    context: str
    options: str
    chosen: str
    tradeoffs: str
    risks: str
    confidence: float
    agent: str
    timestamp: str


class DecisionLedger:
    def __init__(self, db: KernelDB | None = None):
        self._db = db or KernelDB()

    def record_exception(self, message: str, file_name: str) -> None:
        self._record_violation(message=message, file_name=file_name, severity=3)

    def _record_violation(self, message: str, file_name: str, severity: int = 3) -> None:
        try:
            self._db.initialize()
            invariant_id = self._db.get_invariant_id("check_decision_ledger_reference")
            if invariant_id is None:
                return
            self._db.record_invariant_violation(
                InvariantViolationRecord(
                    invariant_id=invariant_id,
                    file=file_name,
                    description=message,
                    severity=severity,
                    timestamp=datetime.now(UTC).isoformat(),
                )
            )
        except Exception:
            return

    def add_decision(
        self,
        problem: str,
        context: str,
        options: str,
        chosen: str,
        tradeoffs: str,
        risks: str,
        confidence: float,
        agent: str,
    ) -> int:
        self._db.initialize()
        timestamp = datetime.now(UTC).isoformat()
        try:
            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO decision_ledger (
                        problem,
                        context,
                        options,
                        chosen,
                        tradeoffs,
                        risks,
                        confidence,
                        agent,
                        timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        problem,
                        context,
                        options,
                        chosen,
                        tradeoffs,
                        risks,
                        confidence,
                        agent,
                        timestamp,
                    ),
                )
                row_id = cursor.lastrowid
                if row_id is None:
                    raise ValueError("Failed to create decision ledger entry.")
                return int(row_id)
        except Exception as exc:
            self._record_violation(
                message=f"Decision add failed: {exc}",
                file_name="decision_ledger",
                severity=3,
            )
            raise

    def get_decisions(self) -> list[dict[str, Any]]:
        try:
            self._db.initialize()
            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()
                rows = cursor.execute(
                    """
                    SELECT
                        id,
                        problem,
                        context,
                        options,
                        chosen,
                        tradeoffs,
                        risks,
                        confidence,
                        agent,
                        timestamp
                    FROM decision_ledger
                    ORDER BY id ASC
                    """
                ).fetchall()
        except Exception as exc:
            self._record_violation(
                message=f"Decision list failed: {exc}",
                file_name="decision_ledger",
                severity=3,
            )
            raise

        entries: list[dict[str, Any]] = []
        for row in rows:
            entry = DecisionEntry(
                id=int(row["id"]),
                problem=str(row["problem"]),
                context=str(row["context"]),
                options=str(row["options"]),
                chosen=str(row["chosen"]),
                tradeoffs=str(row["tradeoffs"]),
                risks=str(row["risks"]),
                confidence=float(row["confidence"]),
                agent=str(row["agent"]),
                timestamp=str(row["timestamp"]),
            )
            entries.append(
                {
                    "id": entry.id,
                    "problem": entry.problem,
                    "context": entry.context,
                    "options": entry.options,
                    "chosen": entry.chosen,
                    "tradeoffs": entry.tradeoffs,
                    "risks": entry.risks,
                    "confidence": entry.confidence,
                    "agent": entry.agent,
                    "timestamp": entry.timestamp,
                }
            )
        return entries

    def get_decision(self, decision_id: int) -> dict[str, Any]:
        try:
            self._db.initialize()
            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()
                row = cursor.execute(
                    """
                    SELECT
                        id,
                        problem,
                        context,
                        options,
                        chosen,
                        tradeoffs,
                        risks,
                        confidence,
                        agent,
                        timestamp
                    FROM decision_ledger
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (decision_id,),
                ).fetchone()
        except Exception as exc:
            self._record_violation(
                message=f"Decision fetch failed for id={decision_id}: {exc}",
                file_name="decision_ledger",
                severity=3,
            )
            raise

        if row is None:
            raise ValueError(f"Decision entry not found for id={decision_id}.")

        entry = DecisionEntry(
            id=int(row["id"]),
            problem=str(row["problem"]),
            context=str(row["context"]),
            options=str(row["options"]),
            chosen=str(row["chosen"]),
            tradeoffs=str(row["tradeoffs"]),
            risks=str(row["risks"]),
            confidence=float(row["confidence"]),
            agent=str(row["agent"]),
            timestamp=str(row["timestamp"]),
        )
        return {
            "id": entry.id,
            "problem": entry.problem,
            "context": entry.context,
            "options": entry.options,
            "chosen": entry.chosen,
            "tradeoffs": entry.tradeoffs,
            "risks": entry.risks,
            "confidence": entry.confidence,
            "agent": entry.agent,
            "timestamp": entry.timestamp,
        }

    def validate_change(self, task_id: int, decision_id: int) -> bool:
        self._db.initialize()
        try:
            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()
                task_row = cursor.execute(
                    "SELECT id FROM tasks WHERE id = ? LIMIT 1",
                    (task_id,),
                ).fetchone()
                decision_row = cursor.execute(
                    "SELECT id FROM decision_ledger WHERE id = ? LIMIT 1",
                    (decision_id,),
                ).fetchone()

            if task_row is None:
                self._record_violation(
                    message=f"Invalid ledger reference: task_id={task_id} does not exist.",
                    file_name="tasks",
                    severity=3,
                )
                return False

            if decision_row is None:
                self._record_violation(
                    message=(
                        "Invalid ledger reference: "
                        f"task_id={task_id} references missing decision_id={decision_id}."
                    ),
                    file_name="decision_ledger",
                    severity=3,
                )
                return False

            return True
        except Exception as exc:
            self._record_violation(
                message=f"Ledger validation exception for task_id={task_id}: {exc}",
                file_name="decision_ledger",
                severity=3,
            )
            return False
