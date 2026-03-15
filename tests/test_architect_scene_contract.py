import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from agents.architect_agent import ArchitectAgent


class ArchitectSceneContractTests(unittest.TestCase):
    def test_required_main_scene_label_text_from_objective_spec(self) -> None:
        payload = {
            "objective_spec": {
                "acceptance": {
                    "checks": [
                        "project.godot exists",
                        "Main scene contains Label text Hello World",
                    ]
                }
            }
        }
        label_text = ArchitectAgent._required_main_scene_label_text(payload)
        self.assertEqual(label_text, "Hello World")

    def test_implement_scene_contract_writes_required_label(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            contract_payload = {
                "task_id": 42,
                "assigned_agent": "architect",
                "ledger_required": False,
                "required_artifacts": ["projects/sandbox_project/scenes/Main.tscn"],
                "decision_id": None,
                "contract_version": 1,
                "objective_spec": {
                    "objective": "Build a Godot 2D Hello World scene",
                    "objective_type": "godot-2d",
                    "spec_version": 1,
                    "artifacts": [
                        {
                            "path": "projects/sandbox_project/scenes/Main.tscn",
                            "kind": "scene",
                            "owner_agent": "architect",
                        }
                    ],
                    "acceptance": {
                        "description": "Deterministic criteria",
                        "checks": [
                            "Main scene contains Label text Hello World",
                        ]
                    }
                },
            }

            with patch("agents.architect_agent.load_kernel_config", return_value=SimpleNamespace(project_root=project_root)):
                agent = ArchitectAgent()
                result = agent.implement_scene_contract(contract_payload)

            self.assertEqual(result["status"], "ok")
            scene_path = project_root / "projects" / "sandbox_project" / "scenes" / "Main.tscn"
            self.assertTrue(scene_path.exists())
            content = scene_path.read_text(encoding="utf-8")
            self.assertIn("[node name=\"Label\" type=\"Label\" parent=\".\"]", content)
            self.assertIn('text = "Hello World"', content)


if __name__ == "__main__":
    unittest.main()
