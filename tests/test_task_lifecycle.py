import unittest
import uuid
from datetime import UTC, datetime

from kernel.config import load_kernel_config
from kernel.db import KernelDB, SQLiteConnectionManager


class TaskLifecycleTests(unittest.TestCase):
    def test_update_task_status_marks_completion_timestamp(self) -> None:
        db = KernelDB()
        db.initialize()

        task_id = int(uuid.uuid4().int % 900000) + 200000
        created_at = datetime.now(UTC).isoformat()

        config = load_kernel_config()
        with SQLiteConnectionManager(config.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (id, description, status, assigned_agent, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, "Lifecycle test task", "queued", "programmer", created_at, None),
            )

        updated = db.update_task_status(task_id=task_id, status="completed")
        self.assertTrue(updated)

        with SQLiteConnectionManager(config.db_path) as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                "SELECT status, completed_at FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(str(row["status"]), "completed")
        self.assertIsNotNone(row["completed_at"])

    def test_update_task_status_returns_false_for_missing_task(self) -> None:
        db = KernelDB()
        db.initialize()
        self.assertFalse(db.update_task_status(task_id=999999999, status="failed"))


if __name__ == "__main__":
    unittest.main()
