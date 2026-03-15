import unittest

from kernel.contracts import TaskExecutionContract


class TaskExecutionContractTests(unittest.TestCase):
    def test_valid_contract_roundtrip(self) -> None:
        contract = TaskExecutionContract(
            task_id=10,
            assigned_agent="programmer",
            ledger_required=True,
            required_artifacts=("projects/sandbox_project/scripts/player.gd",),
            decision_id=2,
        )
        contract.validate()

        restored = TaskExecutionContract.from_dict(contract.to_dict())
        self.assertEqual(restored.task_id, 10)
        self.assertEqual(restored.assigned_agent, "programmer")
        self.assertEqual(restored.decision_id, 2)

    def test_rejects_missing_decision_when_ledger_required(self) -> None:
        with self.assertRaises(ValueError):
            TaskExecutionContract(
                task_id=11,
                assigned_agent="programmer",
                ledger_required=True,
                required_artifacts=("projects/sandbox_project/scripts/player.gd",),
                decision_id=None,
            ).validate()

    def test_rejects_non_sandbox_artifacts(self) -> None:
        with self.assertRaises(ValueError):
            TaskExecutionContract(
                task_id=12,
                assigned_agent="architect",
                ledger_required=False,
                required_artifacts=("scripts/player.gd",),
            ).validate()

    def test_accepts_run_id_extension(self) -> None:
        payload = {
            "task_id": 13,
            "assigned_agent": "programmer",
            "ledger_required": True,
            "required_artifacts": ["projects/sandbox_project/scripts/player.gd"],
            "decision_id": 3,
            "run_id": "run-123",
        }
        contract = TaskExecutionContract.from_dict(payload)
        self.assertEqual(contract.task_id, 13)

    def test_rejects_unknown_extension_key(self) -> None:
        payload = {
            "task_id": 14,
            "assigned_agent": "architect",
            "ledger_required": False,
            "required_artifacts": ["projects/sandbox_project/scenes/Main.tscn"],
            "debug": True,
        }
        with self.assertRaises(ValueError):
            TaskExecutionContract.from_dict(payload)

    def test_rejects_objective_spec_for_non_architect(self) -> None:
        payload = {
            "task_id": 15,
            "assigned_agent": "programmer",
            "ledger_required": True,
            "required_artifacts": ["projects/sandbox_project/scripts/player.gd"],
            "decision_id": 5,
            "objective_spec": {
                "objective": "Build",
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
                    "description": "desc",
                    "checks": ["Main.tscn exists"],
                },
            },
        }
        with self.assertRaises(ValueError):
            TaskExecutionContract.from_dict(payload)

    def test_accepts_objective_spec_for_architect(self) -> None:
        payload = {
            "task_id": 16,
            "assigned_agent": "architect",
            "ledger_required": True,
            "required_artifacts": ["projects/sandbox_project/scenes/Main.tscn"],
            "decision_id": 6,
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
                    "checks": ["Main scene contains Label text Hello World"],
                },
            },
        }
        contract = TaskExecutionContract.from_dict(payload)
        self.assertEqual(contract.assigned_agent, "architect")


if __name__ == "__main__":
    unittest.main()
