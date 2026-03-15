import unittest

from kernel.evaluator import EvaluationPipeline


class EvaluatorScopingTests(unittest.TestCase):
    def test_filter_godot_results_without_scope(self) -> None:
        sample = {
            "total_scenes": 1,
            "total_scripts": 1,
            "scenes_loaded": 1,
            "scripts_checked": 1,
            "errors": [{"file": "scripts/player.gd", "message": "x"}],
            "warnings": [{"file": "scenes/Main.tscn", "message": "y"}],
        }
        filtered = EvaluationPipeline._filter_godot_results(sample, artifact_scope=None)
        self.assertEqual(filtered, sample)

    def test_filter_godot_results_with_project_relative_scope(self) -> None:
        sample = {
            "total_scenes": 1,
            "total_scripts": 2,
            "scenes_loaded": 1,
            "scripts_checked": 2,
            "errors": [
                {"file": "scripts/player.gd", "message": "bad player"},
                {"file": "scripts/legacy.gd", "message": "bad legacy"},
            ],
            "warnings": [
                {"file": "scenes/Main.tscn", "message": "scene warn"},
                {"file": "scenes/Old.tscn", "message": "old warn"},
            ],
        }
        filtered = EvaluationPipeline._filter_godot_results(
            sample,
            artifact_scope=[
                "projects/sandbox_project/scripts/player.gd",
                "projects/sandbox_project/scenes/Main.tscn",
            ],
        )
        self.assertEqual(len(filtered["errors"]), 1)
        self.assertEqual(filtered["errors"][0]["file"], "scripts/player.gd")
        self.assertEqual(len(filtered["warnings"]), 1)
        self.assertEqual(filtered["warnings"][0]["file"], "scenes/Main.tscn")


if __name__ == "__main__":
    unittest.main()
