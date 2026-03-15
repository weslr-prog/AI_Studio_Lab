from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from kernel.db import InvariantViolationRecord, KernelDB, SQLiteConnectionManager
from kernel.ledger import DecisionLedger


@dataclass(frozen=True)
class EvolutionProposal:
    summary: str
    target_module: str
    proposal_type: str
    risk: str
    confidence: float
    simulated_outcome: str
    ledger_required: int


class EvolutionEngine:
    def __init__(self, db: KernelDB | None = None):
        self._db = db or KernelDB()
        self._ledger = DecisionLedger(db=self._db)

    def record_exception(self, message: str, file_name: str = "runner.py") -> None:
        self._record_exception(message=message, file_name=file_name)

    def _record_exception(self, message: str, file_name: str = "evolution/evolution_engine.py") -> None:
        try:
            self._db.initialize()
            invariant_id = self._db.get_invariant_id("check_evolution_engine_exception")
            if invariant_id is None:
                return
            self._db.record_invariant_violation(
                InvariantViolationRecord(
                    invariant_id=invariant_id,
                    file=file_name,
                    description=message,
                    severity=3,
                    timestamp=datetime.now(UTC).isoformat(),
                )
            )
        except Exception:
            return

    def _proposal_exists(self, proposal: EvolutionProposal) -> bool:
        with SQLiteConnectionManager(self._db.db_path) as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                """
                SELECT id
                FROM evolution_proposals
                WHERE summary = ?
                  AND target_module = ?
                  AND proposal_type = ?
                  AND simulated_outcome = ?
                  AND approved = 0
                LIMIT 1
                """,
                (
                    proposal.summary,
                    proposal.target_module,
                    proposal.proposal_type,
                    proposal.simulated_outcome,
                ),
            ).fetchone()
        return row is not None

    def _insert_proposal(self, proposal: EvolutionProposal) -> None:
        with SQLiteConnectionManager(self._db.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO evolution_proposals (
                    summary,
                    target_module,
                    proposal_type,
                    risk,
                    confidence,
                    simulated_outcome,
                    ledger_required,
                    approved,
                    timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    proposal.summary,
                    proposal.target_module,
                    proposal.proposal_type,
                    proposal.risk,
                    proposal.confidence,
                    proposal.simulated_outcome,
                    proposal.ledger_required,
                    datetime.now(UTC).isoformat(),
                ),
            )

    def generate_proposals(self) -> list[dict[str, Any]]:
        self._db.initialize()
        proposals: list[EvolutionProposal] = []

        try:
            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()

                failed_groups = cursor.execute(
                    """
                    SELECT task_id, COUNT(*) AS fail_count
                    FROM task_attempts
                    WHERE success_flag = 0
                    GROUP BY task_id
                    ORDER BY task_id ASC
                    """
                ).fetchall()

                for row in failed_groups:
                    task_id = int(row["task_id"])
                    fail_count = int(row["fail_count"])
                    if fail_count >= 2:
                        proposals.append(
                            EvolutionProposal(
                                summary=(
                                    f"Repeated task failure detected for task_id={task_id} "
                                    f"({fail_count} failed attempts)."
                                ),
                                target_module="kernel/evaluator.py",
                                proposal_type="retry_policy_tuning",
                                risk="medium",
                                confidence=0.72,
                                simulated_outcome=(
                                    "Dry-run: introducing stricter pre-check ordering could "
                                    "reduce repeated failures by one attempt on average."
                                ),
                                ledger_required=1,
                            )
                        )

                drift_rows = cursor.execute(
                    """
                    SELECT id, module, severity, description
                    FROM drift_events
                    WHERE severity >= 2
                    ORDER BY id ASC
                    """
                ).fetchall()

                for row in drift_rows:
                    drift_id = int(row["id"])
                    module_name = str(row["module"])
                    severity = int(row["severity"])
                    proposals.append(
                        EvolutionProposal(
                            summary=(
                                f"Drift event {drift_id} indicates instability in module "
                                f"{module_name} (severity={severity})."
                            ),
                            target_module=module_name,
                            proposal_type="drift_hardening",
                            risk="medium",
                            confidence=0.68,
                            simulated_outcome=(
                                "Dry-run: adding deterministic guardrails around module "
                                "entry points may reduce drift recurrence."
                            ),
                            ledger_required=1,
                        )
                    )

                low_perf_rows = cursor.execute(
                    """
                    SELECT agent, success_rate, average_confidence
                    FROM agent_performance
                    WHERE success_rate < 0.5 OR average_confidence < 0.6
                    ORDER BY agent ASC
                    """
                ).fetchall()

                for row in low_perf_rows:
                    agent = str(row["agent"])
                    success_rate = float(row["success_rate"])
                    avg_confidence = float(row["average_confidence"])
                    proposals.append(
                        EvolutionProposal(
                            summary=(
                                f"Low performance profile for agent={agent} "
                                f"(success_rate={success_rate:.2f}, "
                                f"avg_confidence={avg_confidence:.2f})."
                            ),
                            target_module="kernel/evaluator.py",
                            proposal_type="evaluation_threshold_calibration",
                            risk="low",
                            confidence=0.65,
                            simulated_outcome=(
                                "Dry-run: tuning deterministic confidence gating may improve "
                                "stable pass/fail discrimination."
                            ),
                            ledger_required=0,
                        )
                    )

            inserted: list[dict[str, Any]] = []
            for proposal in sorted(
                proposals,
                key=lambda item: (
                    item.target_module,
                    item.proposal_type,
                    item.summary,
                ),
            ):
                if self._proposal_exists(proposal):
                    continue
                self._insert_proposal(proposal)
                inserted.append(
                    {
                        "summary": proposal.summary,
                        "target_module": proposal.target_module,
                        "proposal_type": proposal.proposal_type,
                        "risk": proposal.risk,
                        "confidence": proposal.confidence,
                        "simulated_outcome": proposal.simulated_outcome,
                        "ledger_required": proposal.ledger_required,
                    }
                )

            return inserted
        except Exception as exc:
            self._record_exception(f"generate_proposals exception: {exc}")
            return []

    def list_proposals(self) -> list[dict[str, Any]]:
        self._db.initialize()
        try:
            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()
                rows = cursor.execute(
                    """
                    SELECT
                        id,
                        summary,
                        target_module,
                        proposal_type,
                        risk,
                        confidence,
                        simulated_outcome,
                        ledger_required,
                        approved,
                        timestamp
                    FROM evolution_proposals
                    WHERE approved = 0
                    ORDER BY id ASC
                    """
                ).fetchall()

            proposals: list[dict[str, Any]] = []
            for row in rows:
                proposals.append(
                    {
                        "id": int(row["id"]),
                        "summary": str(row["summary"]),
                        "target_module": str(row["target_module"]),
                        "proposal_type": str(row["proposal_type"]),
                        "risk": str(row["risk"]),
                        "confidence": float(row["confidence"]),
                        "simulated_outcome": str(row["simulated_outcome"]),
                        "ledger_required": int(row["ledger_required"]),
                        "approved": int(row["approved"]),
                        "timestamp": str(row["timestamp"]),
                    }
                )
            return proposals
        except Exception as exc:
            self._record_exception(f"list_proposals exception: {exc}")
            return []

    def approve_proposal(self, proposal_id: int) -> bool:
        self._db.initialize()
        try:
            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()
                row = cursor.execute(
                    """
                    SELECT id, ledger_required, approved
                    FROM evolution_proposals
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (proposal_id,),
                ).fetchone()

                if row is None:
                    self._record_exception(
                        f"approve_proposal failed: proposal_id={proposal_id} not found."
                    )
                    return False

                if int(row["approved"]) != 0:
                    self._record_exception(
                        f"approve_proposal failed: proposal_id={proposal_id} already finalized."
                    )
                    return False

                ledger_required = int(row["ledger_required"]) == 1
                if ledger_required:
                    ledger_entries = self._ledger.get_decisions()
                    if not ledger_entries:
                        self._record_exception(
                            (
                                "approve_proposal blocked: ledger entry required but none exists "
                                f"for proposal_id={proposal_id}."
                            )
                        )
                        return False

                cursor.execute(
                    """
                    UPDATE evolution_proposals
                    SET approved = 1
                    WHERE id = ?
                    """,
                    (proposal_id,),
                )

            return True
        except Exception as exc:
            self._record_exception(f"approve_proposal exception for proposal_id={proposal_id}: {exc}")
            return False

    def reject_proposal(self, proposal_id: int) -> bool:
        self._db.initialize()
        try:
            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()
                row = cursor.execute(
                    """
                    SELECT id, approved
                    FROM evolution_proposals
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (proposal_id,),
                ).fetchone()

                if row is None:
                    self._record_exception(
                        f"reject_proposal failed: proposal_id={proposal_id} not found."
                    )
                    return False

                if int(row["approved"]) != 0:
                    self._record_exception(
                        f"reject_proposal failed: proposal_id={proposal_id} already finalized."
                    )
                    return False

                cursor.execute(
                    """
                    UPDATE evolution_proposals
                    SET approved = -1
                    WHERE id = ?
                    """,
                    (proposal_id,),
                )

            return True
        except Exception as exc:
            self._record_exception(f"reject_proposal exception for proposal_id={proposal_id}: {exc}")
            return False
