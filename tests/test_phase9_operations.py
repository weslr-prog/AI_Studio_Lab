import unittest
from unittest.mock import patch

from runner import (
    _build_release_handoff,
    _build_upgrade_workflow_report,
    _evaluate_proposal_rollout_policy,
)


class Phase9OperationsTests(unittest.TestCase):
    @patch("runner._docs_index_report")
    @patch("runner._missing_required_models_for_orchestrate")
    @patch("runner._required_models_for_orchestrate")
    def test_build_upgrade_workflow_report(
        self,
        mock_required: object,
        mock_missing: object,
        mock_docs: object,
    ) -> None:
        mock_docs.return_value = {"status": "ok", "version": "4.2", "is_canonical_layout": False}
        mock_required.return_value = ("qwen2.5:7b", "qwen2.5-coder:14b")
        mock_missing.return_value = ["qwen2.5-coder:14b"]

        report = _build_upgrade_workflow_report(docs_version="4.2", docs_strict=False)
        self.assertEqual(report["status"], "ok")
        self.assertIn("models", report)
        self.assertEqual(report["models"]["missing"], ["qwen2.5-coder:14b"])

    def test_evaluate_proposal_rollout_policy(self) -> None:
        proposal = {"id": 1, "risk": "high", "confidence": 0.9}
        evaluated = _evaluate_proposal_rollout_policy(proposal)
        self.assertEqual(evaluated["action"], "reject")
        self.assertIn("rollback_criteria", evaluated)

    @patch("runner._build_run_report")
    def test_build_release_handoff(self, mock_report: object) -> None:
        mock_report.return_value = {
            "summary": {"release_ready": True},
            "release_readiness": {"passed": True},
            "objective_spec": {"objective": "x"},
            "acceptance": {"passed": True},
        }
        payload = _build_release_handoff("run-abc")
        self.assertEqual(payload["run_id"], "run-abc")
        self.assertTrue(payload["release_ready"])
        self.assertEqual(payload["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
