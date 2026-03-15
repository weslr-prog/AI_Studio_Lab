import unittest
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

from agents.architect_agent import ArchitectAgent
from agents.programmer_agent import ProgrammerAgent
from kernel.config import load_kernel_config
from kernel.db import KernelDB, SQLiteConnectionManager


class AgentDocsSourcesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = KernelDB()
        self.db.initialize()
        self.config = load_kernel_config()

    def _insert_task(self, description: str, assigned_agent: str) -> int:
        task_id = int(uuid.uuid4().int % 900000) + 100000
        created_at = datetime.now(UTC).isoformat()
        with SQLiteConnectionManager(self.config.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (id, description, status, assigned_agent, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, description, "queued", assigned_agent, created_at, None),
            )
        return task_id

    def test_architect_proposal_includes_docs_sources(self) -> None:
        task_id = self._insert_task("Design a player movement scene architecture", "architect")

        agent = ArchitectAgent(db=self.db)
        agent._call_ollama_json = lambda _prompt: {
            "ledger_entry": {
                "problem": "Need movement architecture",
                "context": "Godot 4.2 Node2D scene",
                "options": "Single scene or split files",
                "chosen": "Single scene with script",
                "tradeoffs": "Less modular but simpler",
                "risks": "Input mapping gaps",
                "confidence": 0.8,
            },
            "rationale": "Minimal viable scene architecture",
            "module_plan": ["projects/sandbox_project/scenes/Main.tscn"],
        }

        with patch(
            "agents.architect_agent.retrieve_docs_context",
            return_value={
                "status": "ok",
                "snippets": [
                    {
                        "path": "docs/godot/4.2/classes/class_characterbody2d.html",
                        "title": "CharacterBody2D",
                        "excerpt": "CharacterBody2D provides velocity and move_and_slide",
                    }
                ],
            },
        ):
            result = agent.propose_architecture(task_id)

        self.assertIn("docs_sources", result)
        self.assertEqual(len(result["docs_sources"]), 1)
        self.assertEqual(result["docs_sources"][0]["title"], "CharacterBody2D")

    def test_programmer_implementation_includes_docs_sources(self) -> None:
        task_id = self._insert_task("Implement movement script", "programmer")

        architect = ArchitectAgent(db=self.db)
        decision_id = architect.submit_ledger_entry(
            problem="Movement script",
            context="Godot 4.2",
            options="Use CharacterBody2D",
            chosen="Use Input.get_vector and move_and_slide",
            tradeoffs="Basic motion only",
            risks="No acceleration",
            confidence=0.75,
            agent="architect_agent",
        )

        agent = ProgrammerAgent(db=self.db)
        agent._call_ollama_json = lambda _prompt: {
            "file_path": "projects/sandbox_project/scripts/player.gd",
            "content": "extends CharacterBody2D\n",
            "output_summary": "Added movement script",
            "confidence": 0.7,
        }
        agent._evaluator.evaluate_task_attempt = lambda **_kwargs: True
        agent._godot.validate_project = lambda _path: {"errors": [], "warnings": []}
        agent._godot.record_results_in_db = lambda *_args, **_kwargs: None

        with patch(
            "agents.programmer_agent.retrieve_docs_context",
            return_value={
                "status": "ok",
                "snippets": [
                    {
                        "path": "docs/godot/4.2/tutorials/2d/2d_movement.html",
                        "title": "2D Movement",
                        "excerpt": "Use Input.get_vector for directional movement.",
                    }
                ],
            },
        ):
            result = agent.implement_task(task_id=task_id, decision_id=decision_id, run_id="docs-test")

        self.assertIn("docs_sources", result)
        self.assertEqual(len(result["docs_sources"]), 1)
        self.assertEqual(result["docs_sources"][0]["path"], "docs/godot/4.2/tutorials/2d/2d_movement.html")


if __name__ == "__main__":
    unittest.main()
