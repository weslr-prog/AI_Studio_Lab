import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from kernel.docs_retriever import retrieve_docs_context


class DocsRetrieverTests(unittest.TestCase):
    def test_retrieve_docs_context_returns_matches(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            docs_root = project_root / "docs" / "godot" / "4.2"
            docs_root.mkdir(parents=True, exist_ok=True)
            (docs_root / "index.html").write_text(
                "<html><head><title>Index</title></head><body>Godot Node2D basics and Label usage.</body></html>",
                encoding="utf-8",
            )
            (docs_root / "classes.html").write_text(
                "<html><head><title>Node2D</title></head><body>CharacterBody2D movement with velocity and move_and_slide.</body></html>",
                encoding="utf-8",
            )

            with patch("kernel.docs_retriever.load_kernel_config", return_value=SimpleNamespace(project_root=project_root)):
                result = retrieve_docs_context("CharacterBody2D movement", version="4.2", max_results=2)

            self.assertEqual(result["status"], "ok")
            self.assertTrue(len(result["snippets"]) >= 1)
            self.assertIn("path", result["snippets"][0])

    def test_retrieve_docs_context_handles_missing_docs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            with patch("kernel.docs_retriever.load_kernel_config", return_value=SimpleNamespace(project_root=project_root)):
                result = retrieve_docs_context("Node2D", version="4.2", max_results=2)

            self.assertEqual(result["status"], "error")
            self.assertEqual(result["snippets"], [])


if __name__ == "__main__":
    unittest.main()
