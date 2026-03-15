import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from kernel.acceptance_validator import evaluate_acceptance_spec


class AcceptanceValidatorTests(unittest.TestCase):
    def test_evaluate_acceptance_spec_passes_for_valid_artifacts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            project_file = project_root / "projects" / "sandbox_project" / "project.godot"
            scene_file = project_root / "projects" / "sandbox_project" / "scenes" / "Main.tscn"
            script_file = project_root / "projects" / "sandbox_project" / "scripts" / "player.gd"

            project_file.parent.mkdir(parents=True, exist_ok=True)
            scene_file.parent.mkdir(parents=True, exist_ok=True)
            script_file.parent.mkdir(parents=True, exist_ok=True)

            project_file.write_text("[application]\n", encoding="utf-8")
            scene_file.write_text("[node name=\"Main\"]\nHello World\n", encoding="utf-8")
            script_file.write_text("extends Node2D\n", encoding="utf-8")

            spec_payload = {
                "acceptance": {
                    "checks": [
                        "project.godot exists",
                        "Main.tscn exists",
                        "player.gd exists",
                        "godot validation has zero errors",
                        "Main scene contains Label text Hello World",
                    ]
                }
            }

            result = evaluate_acceptance_spec(
                spec_payload=spec_payload,
                project_root=project_root,
                godot_error_count=0,
            )

            self.assertTrue(result["passed"])
            self.assertEqual(len(result["checks"]), 5)
            self.assertTrue(all(check["passed"] for check in result["checks"]))

    def test_evaluate_acceptance_spec_fails_when_required_files_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            spec_payload = {
                "acceptance": {
                    "checks": [
                        "project.godot exists",
                        "Main.tscn exists",
                        "player.gd exists",
                    ]
                }
            }

            result = evaluate_acceptance_spec(
                spec_payload=spec_payload,
                project_root=project_root,
                godot_error_count=0,
            )

            self.assertFalse(result["passed"])
            self.assertEqual(len(result["checks"]), 3)
            self.assertTrue(any(not check["passed"] for check in result["checks"]))


if __name__ == "__main__":
    unittest.main()
