import unittest

from kernel.spec_compiler import compile_objective_spec


class SpecCompilerTests(unittest.TestCase):
    def test_compile_hello_world_objective(self) -> None:
        spec = compile_objective_spec("Create a 2D hello world display in Godot")
        self.assertEqual(spec.objective_type, "godot-2d")
        payload = spec.to_dict()
        self.assertEqual(len(payload["artifacts"]), 3)
        self.assertIn("Main scene contains Label text Hello World", payload["acceptance"]["checks"])

    def test_compile_general_objective(self) -> None:
        spec = compile_objective_spec("Refactor architecture")
        self.assertEqual(spec.objective_type, "general")


if __name__ == "__main__":
    unittest.main()
