from pathlib import Path
from typing import Any


def evaluate_acceptance_spec(
    spec_payload: dict[str, Any],
    project_root: Path,
    godot_error_count: int | None = None,
) -> dict[str, Any]:
    checks = spec_payload.get("acceptance", {}).get("checks", [])
    if not isinstance(checks, list):
        raise ValueError("spec acceptance checks must be list")

    scene_path = project_root / "projects" / "sandbox_project" / "scenes" / "Main.tscn"
    project_file = project_root / "projects" / "sandbox_project" / "project.godot"
    script_path = project_root / "projects" / "sandbox_project" / "scripts" / "player.gd"

    results: list[dict[str, Any]] = []
    for check in checks:
        check_name = str(check)
        passed = False
        detail = ""

        if check_name == "project.godot exists":
            passed = project_file.exists()
            detail = "found" if passed else "missing"
        elif check_name == "Main.tscn exists":
            passed = scene_path.exists()
            detail = "found" if passed else "missing"
        elif check_name == "player.gd exists":
            passed = script_path.exists()
            detail = "found" if passed else "missing"
        elif check_name == "godot validation has zero errors":
            passed = godot_error_count == 0
            detail = f"godot_error_count={godot_error_count}"
        elif check_name == "Main scene contains Label text Hello World":
            if scene_path.exists():
                scene_content = scene_path.read_text(encoding="utf-8")
                passed = "Hello World" in scene_content
                detail = "Hello World found" if passed else "Hello World missing"
            else:
                passed = False
                detail = "scene missing"
        else:
            passed = False
            detail = "unknown acceptance check"

        results.append(
            {
                "check": check_name,
                "passed": passed,
                "detail": detail,
            }
        )

    return {
        "passed": all(bool(item["passed"]) for item in results),
        "checks": results,
    }
