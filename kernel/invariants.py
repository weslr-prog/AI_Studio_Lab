from typing import TypedDict

from kernel.config import load_kernel_config
from kernel.constitution import RUNTIME_LIMITS
from kernel.db import KernelDB
from kernel.structure import ProjectStructureAnalyzer


class ValidationResult(TypedDict):
    passed: bool
    severity: int
    message: str


def _result(passed: bool, severity: int, message: str) -> ValidationResult:
    return {
        "passed": passed,
        "severity": severity,
        "message": message,
    }


def check_no_large_python_files(max_lines: int = 500) -> ValidationResult:
    config = load_kernel_config()
    analyzer = ProjectStructureAnalyzer()
    files = analyzer.scan_python_files(config.project_root)
    offending_files: list[str] = []

    for file_path in files:
        line_count = analyzer.count_lines(file_path)
        if line_count > max_lines:
            offending_files.append(file_path.relative_to(config.project_root).as_posix())

    if offending_files:
        return _result(
            False,
            2,
            f"Python file size invariant failed: {offending_files[0]} exceeds {max_lines} lines.",
        )

    return _result(True, 0, "All Python files are within maximum line count.")


def check_no_circular_imports() -> ValidationResult:
    config = load_kernel_config()
    analyzer = ProjectStructureAnalyzer()
    files = analyzer.scan_python_files(config.project_root)
    graph = analyzer.build_dependency_graph(files)
    cycles = analyzer.detect_circular_dependencies(graph)

    if cycles:
        formatted_cycles = [" -> ".join(cycle + [cycle[0]]) for cycle in cycles if cycle]
        cycle_details = "; ".join(formatted_cycles)
        return _result(False, 3, f"Circular import detected: {cycle_details}")

    return _result(True, 0, "No circular imports detected.")


def check_required_ledger_entry() -> ValidationResult:
    db = KernelDB()
    if not db.db_path.exists():
        return _result(False, 3, "Ledger database file does not exist.")

    if not db.has_required_tables():
        return _result(False, 3, "Ledger schema is incomplete.")

    return _result(True, 0, "Required ledger schema is present.")


def check_confidence_threshold(confidence: float) -> ValidationResult:
    if confidence >= RUNTIME_LIMITS.minimum_confidence:
        return _result(True, 0, "Confidence threshold satisfied.")

    return _result(
        False,
        2,
        (
            "Confidence threshold failed: "
            f"{confidence:.3f} < {RUNTIME_LIMITS.minimum_confidence:.3f}."
        ),
    )


def check_retry_limit(attempt_number: int) -> ValidationResult:
    if attempt_number <= RUNTIME_LIMITS.retry_limit:
        return _result(True, 0, "Retry limit satisfied.")

    return _result(
        False,
        3,
        (
            "Retry limit failed: "
            f"attempt {attempt_number} exceeds limit {RUNTIME_LIMITS.retry_limit}."
        ),
    )
