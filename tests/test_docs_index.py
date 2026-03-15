import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from runner import _docs_index_report


class DocsIndexTests(unittest.TestCase):
    def test_docs_index_report_ok_for_canonical_layout(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            docs_root = project_root / "docs" / "godot" / "4.2"
            (docs_root / "classes").mkdir(parents=True, exist_ok=True)
            (docs_root / "tutorials").mkdir(parents=True, exist_ok=True)
            (docs_root / "index.html").write_text("<html></html>", encoding="utf-8")

            with patch("runner.load_kernel_config", return_value=SimpleNamespace(project_root=project_root)):
                report = _docs_index_report(version="4.2", strict=False)

            self.assertEqual(report["status"], "ok")
            self.assertTrue(report["is_canonical_layout"])

    def test_docs_index_report_ok_for_single_nested_wrapper(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            docs_root = project_root / "docs" / "godot" / "4.2" / "godot-docs-html-stable"
            (docs_root / "classes").mkdir(parents=True, exist_ok=True)
            (docs_root / "tutorials").mkdir(parents=True, exist_ok=True)
            (docs_root / "index.html").write_text("<html></html>", encoding="utf-8")

            with patch("runner.load_kernel_config", return_value=SimpleNamespace(project_root=project_root)):
                report = _docs_index_report(version="4.2", strict=False)

            self.assertEqual(report["status"], "ok")
            self.assertFalse(report["is_canonical_layout"])

    def test_docs_index_report_strict_rejects_nested_wrapper(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            docs_root = project_root / "docs" / "godot" / "4.2" / "godot-docs-html-stable"
            (docs_root / "classes").mkdir(parents=True, exist_ok=True)
            (docs_root / "tutorials").mkdir(parents=True, exist_ok=True)
            (docs_root / "index.html").write_text("<html></html>", encoding="utf-8")

            with patch("runner.load_kernel_config", return_value=SimpleNamespace(project_root=project_root)):
                report = _docs_index_report(version="4.2", strict=True)

            self.assertEqual(report["status"], "error")
            self.assertIn("strict", report)
            self.assertTrue(report["strict"])

    def test_docs_index_report_error_when_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            with patch("runner.load_kernel_config", return_value=SimpleNamespace(project_root=project_root)):
                report = _docs_index_report(version="4.2", strict=False)

            self.assertEqual(report["status"], "error")


if __name__ == "__main__":
    unittest.main()
