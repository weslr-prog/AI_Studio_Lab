import unittest

from agents.qa_agent import QAgent


class QATaskScopeTests(unittest.TestCase):
    def test_task_related_violations_filters_by_task_marker(self) -> None:
        violations = [
            {"description": "[task_id=2] first"},
            {"description": "[task_id=3] second"},
            {"description": "no marker"},
            {"description": "[task_id=2] third"},
        ]
        related = QAgent._task_related_violations(task_id=2, violations=violations)
        self.assertEqual(len(related), 2)

    def test_task_related_violations_with_window(self) -> None:
        violations = [
            {"description": "[task_id=2] old", "timestamp": "2026-02-18T10:00:00+00:00", "run_id": "r1"},
            {"description": "[task_id=2] new", "timestamp": "2026-02-18T10:05:00+00:00", "run_id": "r2"},
            {"description": "[task_id=3] new", "timestamp": "2026-02-18T10:06:00+00:00", "run_id": "r2"},
        ]
        related = QAgent._task_related_violations(
            task_id=2,
            violations=violations,
            since_timestamp="2026-02-18T10:03:00+00:00",
            run_id="r2",
        )
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]["description"], "[task_id=2] new")


if __name__ == "__main__":
    unittest.main()
