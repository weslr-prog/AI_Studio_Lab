import unittest

from kernel.model_gateway import ModelGateway


class ModelGatewayTests(unittest.TestCase):
    def test_model_mapping(self) -> None:
        gateway = ModelGateway()
        self.assertEqual(gateway.model_for("director"), "qwen2.5:7b")
        self.assertEqual(gateway.model_for("architect"), "qwen2.5-coder:14b")
        self.assertEqual(gateway.model_for("programmer"), "qwen2.5-coder:14b")
        self.assertEqual(gateway.model_for("qa"), "qwen2.5:7b")

    def test_unknown_agent_returns_error(self) -> None:
        gateway = ModelGateway()
        result = gateway.generate_json(agent_name="unknown", prompt="{}")
        self.assertEqual(result.get("status"), "error")
        self.assertIn("Unknown", str(result.get("message")))


if __name__ == "__main__":
    unittest.main()
