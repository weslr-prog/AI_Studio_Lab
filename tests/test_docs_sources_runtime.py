import unittest
import uuid
from datetime import UTC, datetime

from agents.architect_agent import ArchitectAgent
from agents.programmer_agent import ProgrammerAgent
from kernel.config import load_kernel_config
from kernel.db import KernelDB, SQLiteConnectionManager
from kernel.ledger import DecisionLedger


class DocsSourcesRuntimeTests(unittest.TestCase):
    def test_architect_proposal_contains_docs_sources(self) -> None:
        db = KernelDB()
        db.initialize()

        task_id = int(uuid.uuid4().int % 900000) + 100000
        created_at = datetime.now(UTC).isoformat()

        config = load_kernel_config()
        with SQLiteConnectionManager(config.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (id, description, status, assigned_agent, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, "Create architecture for a 2D movement scene", "queued", "architect", created_at, None),
            )

        agent = ArchitectAgent(db=db)
        agent._call_ollama_json = lambda prompt: {
            "ledger_entry": {
                "problem": "Need scene structure for movement.",
                "context": "Godot 4.2 sandbox project.",
                "options": "Single scene vs scene + script split.",
                "chosen": "Main scene with CharacterBody2D and script.",
                "tradeoffs": "Simple now, less modular later.",
                "risks": "Input actions may be missing.",
                "confidence": 0.8,
            },
            "rationale": "Meets deterministic sandbox constraints.",
            "module_plan": ["projects/sandbox_project/scenes/Main.tscn"],
        }

        result = agent.propose_architecture(task_id)

        self.assertIn("docs_sources", result)
        self.assertIsInstance(result["docs_sources"], list)
        for item in result["docs_sources"]:
            self.assertIsInstance(item, dict)
            self.assertIn("path", item)
            self.assertIn("title", item)

    def test_programmer_implementation_contains_docs_sources(self) -> None:
        db = KernelDB()
        db.initialize()

        task_id = int(uuid.uuid4().int % 900000) + 100000
        created_at = datetime.now(UTC).isoformat()

        config = load_kernel_config()
        with SQLiteConnectionManager(config.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (id, description, status, assigned_agent, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, "Implement player movement script", "queued", "programmer", created_at, None),
            )

        decision_id = DecisionLedger(db=db).add_decision(
            problem="Implement player movement",
            context="Godot 4.2 CharacterBody2D",
            options="Simple script",
            chosen="Write sandbox movement script",
            tradeoffs="Not fully modular",
            risks="Input mapping assumptions",
            confidence=0.75,
            agent="architect_agent",
        )

        agent = ProgrammerAgent(db=db)
        agent._call_ollama_json = lambda prompt: {
            "file_path": "projects/sandbox_project/scripts/docs_sources_runtime.gd",
            "content": "extends Node\n",
            "output_summary": "Created runtime verification script.",
            "confidence": 0.7,
        }
        agent._evaluator.evaluate_task_attempt = lambda **kwargs: True
        agent._godot.validate_project = lambda project_path: {
            "total_scenes": 0,
            "total_scripts": 1,
            "scenes_loaded": 0,
            "scripts_checked": 1,
            "errors": [],
            "warnings": [],
        }
        agent._godot.record_results_in_db = lambda *args, **kwargs: None

        result = agent.implement_task(task_id=task_id, decision_id=decision_id, run_id="docs-sources-runtime-test")

        self.assertIn("docs_sources", result)
        self.assertIsInstance(result["docs_sources"], list)
        for item in result["docs_sources"]:
            self.assertIsInstance(item, dict)
            self.assertIn("path", item)
            self.assertIn("title", item)
        self.assertEqual(result["written_file"], "projects/sandbox_project/scripts/docs_sources_runtime.gd")
        generated_file = config.project_root / "projects" / "sandbox_project" / "scripts" / "docs_sources_runtime.gd"
        if generated_file.exists():
            generated_file.unlink()


if __name__ == "__main__":
    unittest.main()