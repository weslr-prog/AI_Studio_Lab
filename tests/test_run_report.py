import unittest
import uuid
from datetime import UTC, datetime

from kernel.config import load_kernel_config
from kernel.db import KernelDB, SQLiteConnectionManager
from runner import _build_run_report


class RunReportTests(unittest.TestCase):
    def test_build_run_report_for_latest_run_id(self) -> None:
        run_id = "3377968f-8707-4035-af1b-f3d98349f9ee"
        report = _build_run_report(run_id)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["run_id"], run_id)
        self.assertIn("objective_spec", report)
        self.assertIn("summary", report)
        self.assertIn("attempts", report)
        self.assertIn("tasks", report)
        self.assertIn("violations", report)

    def test_build_run_report_includes_manifest_tasks_without_attempts(self) -> None:
        run_id = str(uuid.uuid4())
        task_id = int(uuid.uuid4().int % 900000) + 100000
        db = KernelDB()
        db.initialize()

        timestamp = datetime.now(UTC).isoformat()
        db.record_run_manifest_task(
            run_id=run_id,
            task_id=task_id,
            task="Manifest only director task",
            assigned_agent="director",
            created_at=timestamp,
        )

        config = load_kernel_config()
        with SQLiteConnectionManager(config.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (id, description, status, assigned_agent, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, "Manifest only director task", "queued", "director", timestamp, None),
            )

        report = _build_run_report(run_id)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["summary"]["tasks"], 1)
        self.assertEqual(report["tasks"][0]["assigned_agent"], "director")

    def test_build_run_report_includes_acceptance_results(self) -> None:
        run_id = str(uuid.uuid4())
        db = KernelDB()
        db.initialize()

        db.record_run_acceptance_result(
            run_id=run_id,
            check_name="project.godot exists",
            passed=True,
            detail="found",
        )
        db.record_run_acceptance_result(
            run_id=run_id,
            check_name="godot validation has zero errors",
            passed=False,
            detail="godot_error_count=1",
        )

        report = _build_run_report(run_id)
        self.assertEqual(report["status"], "ok")
        self.assertIn("acceptance", report)
        self.assertEqual(report["acceptance"]["passed"], False)
        self.assertEqual(len(report["acceptance"]["checks"]), 2)
        self.assertEqual(report["summary"]["acceptance_checks"], 2)
        self.assertEqual(report["summary"]["acceptance_failed"], 1)

    def test_build_run_report_includes_task_status_counts(self) -> None:
        run_id = str(uuid.uuid4())
        task_id = int(uuid.uuid4().int % 900000) + 100000
        db = KernelDB()
        db.initialize()

        timestamp = datetime.now(UTC).isoformat()
        db.record_run_manifest_task(
            run_id=run_id,
            task_id=task_id,
            task="Lifecycle status task",
            assigned_agent="programmer",
            created_at=timestamp,
        )

        config = load_kernel_config()
        with SQLiteConnectionManager(config.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (id, description, status, assigned_agent, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, "Lifecycle status task", "completed", "programmer", timestamp, timestamp),
            )

        report = _build_run_report(run_id)
        self.assertEqual(report["status"], "ok")
        self.assertIn("task_status_counts", report["summary"])
        self.assertEqual(report["summary"]["task_status_counts"]["completed"], 1)

    def test_build_run_report_includes_release_readiness(self) -> None:
        run_id = str(uuid.uuid4())
        db = KernelDB()
        db.initialize()

        snapshot = {
            "run_id": run_id,
            "release_ready": False,
            "hard_gates": {
                "acceptance_passed": True,
                "invariants_passed": True,
                "artifacts_present": True,
                "docs_policy_passed": False,
            },
            "blocking_gates": ["docs_policy_passed"],
            "handoff": {
                "run_id": run_id,
                "release_ready": False,
                "blocking_gates": ["docs_policy_passed"],
                "summary": "blocked",
            },
        }
        db.record_run_release_readiness(
            run_id=run_id,
            passed=False,
            snapshot_payload=snapshot,
        )

        report = _build_run_report(run_id)
        self.assertEqual(report["status"], "ok")
        self.assertIn("release_readiness", report)
        self.assertFalse(report["release_readiness"]["passed"])
        self.assertEqual(report["summary"]["release_ready"], False)


if __name__ == "__main__":
    unittest.main()
