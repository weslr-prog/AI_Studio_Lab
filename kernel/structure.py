import ast
from pathlib import Path
from typing import Dict, List


class ProjectStructureAnalyzer:
    _EXCLUDED_DIR_NAMES: tuple[str, ...] = (
        ".venv",
        "venv",
        "__pycache__",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
    )

    def __init__(self) -> None:
        self._base_path: Path | None = None

    def scan_python_files(self, base_path: Path) -> List[Path]:
        resolved_base = base_path.resolve()
        self._base_path = resolved_base
        files: list[Path] = []
        for path in resolved_base.rglob("*.py"):
            if any(part in self._EXCLUDED_DIR_NAMES for part in path.parts):
                continue
            files.append(path.resolve())
        return sorted(files)

    def _require_base_path(self) -> Path:
        if self._base_path is None:
            raise ValueError("Base path is not set. Call scan_python_files(base_path) first.")
        return self._base_path

    def _module_name(self, file_path: Path, base_path: Path) -> str:
        relative = file_path.relative_to(base_path)
        return ".".join(relative.with_suffix("").parts)

    def _relative_file_name(self, file_path: Path, base_path: Path) -> str:
        return file_path.relative_to(base_path).as_posix()

    def _resolve_relative_module(self, current_module: str, module: str | None, level: int) -> str:
        current_parts = current_module.split(".")
        package_parts = current_parts[:-1]

        if level <= 0:
            return module or ""

        up_steps = level - 1
        if up_steps > len(package_parts):
            return ""

        anchor_parts = package_parts[: len(package_parts) - up_steps]
        module_parts = module.split(".") if module else []
        all_parts = anchor_parts + module_parts
        return ".".join(part for part in all_parts if part)

    def build_dependency_graph(self, files: List[Path]) -> Dict[str, List[str]]:
        if not files:
            return {}

        base_path = self._base_path
        if base_path is None:
            base_path = Path(Path.commonpath([str(path) for path in files])).resolve()

        module_to_file: dict[str, str] = {}
        file_to_module: dict[str, str] = {}

        for file_path in sorted(files):
            module_name = self._module_name(file_path, base_path)
            relative_name = self._relative_file_name(file_path, base_path)
            module_to_file[module_name] = relative_name
            file_to_module[relative_name] = module_name

        graph: Dict[str, List[str]] = {relative_name: [] for relative_name in sorted(file_to_module)}

        for relative_name in sorted(file_to_module):
            module_name = file_to_module[relative_name]
            file_path = base_path / relative_name
            try:
                tree = ast.parse(file_path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue

            imports: set[str] = set()

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_module = alias.name
                        if imported_module in module_to_file:
                            imports.add(module_to_file[imported_module])
                elif isinstance(node, ast.ImportFrom):
                    absolute_module = self._resolve_relative_module(
                        current_module=module_name,
                        module=node.module,
                        level=node.level,
                    )

                    candidate_modules: list[str] = []
                    if absolute_module:
                        candidate_modules.append(absolute_module)

                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        if absolute_module:
                            candidate_modules.append(f"{absolute_module}.{alias.name}")

                    for candidate in candidate_modules:
                        if candidate in module_to_file:
                            imports.add(module_to_file[candidate])

            graph[relative_name] = sorted(imports)

        return graph

    def detect_circular_dependencies(self, graph: Dict[str, List[str]]) -> List[List[str]]:
        visited: set[str] = set()
        visiting: set[str] = set()
        stack: list[str] = []
        cycles: list[list[str]] = []
        seen_cycle_keys: set[tuple[str, ...]] = set()

        def normalize_cycle(cycle: list[str]) -> tuple[str, ...]:
            if not cycle:
                return tuple()
            rotations = [tuple(cycle[index:] + cycle[:index]) for index in range(len(cycle))]
            return min(rotations)

        def dfs(node: str) -> None:
            visiting.add(node)
            stack.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in graph:
                    continue
                if neighbor in visiting:
                    start_index = stack.index(neighbor)
                    cycle = stack[start_index:].copy()
                    cycle_key = normalize_cycle(cycle)
                    if cycle_key and cycle_key not in seen_cycle_keys:
                        seen_cycle_keys.add(cycle_key)
                        cycles.append(list(cycle_key))
                    continue
                if neighbor in visited:
                    continue
                dfs(neighbor)

            stack.pop()
            visiting.remove(node)
            visited.add(node)

        for node in sorted(graph):
            if node not in visited:
                dfs(node)

        return sorted(cycles)

    def count_lines(self, file: Path) -> int:
        with file.open("r", encoding="utf-8") as handle:
            return sum(1 for _ in handle)

    def generate_structure_report(self, base_path: Path) -> dict:
        files = self.scan_python_files(base_path)
        graph = self.build_dependency_graph(files)
        cycles = self.detect_circular_dependencies(graph)

        large_files: list[dict[str, int | str]] = []
        for file_path in files:
            line_count = self.count_lines(file_path)
            if line_count > 500:
                relative_name = file_path.relative_to(base_path.resolve()).as_posix()
                large_files.append({"file": relative_name, "lines": line_count})

        return {
            "total_files": len(files),
            "large_files": sorted(large_files, key=lambda item: str(item["file"])),
            "circular_dependencies": cycles,
            "dependency_graph_size": len(graph),
        }
