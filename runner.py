import argparse
from datetime import UTC, datetime
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
import uuid
import zipfile
from collections.abc import Callable
from typing import Any

from agents.architect_agent import ArchitectAgent
from agents.director_agent import DirectorAgent
from agents.programmer_agent import ProgrammerAgent
from agents.qa_agent import QAgent
from evolution.evolution_engine import EvolutionEngine
from kernel.config import load_kernel_config
from kernel.acceptance_validator import evaluate_acceptance_spec
from kernel.contracts import TaskExecutionContract
from kernel.db import KernelDB, SQLiteConnectionManager
from kernel.godot_validator import GodotValidator
from kernel.ledger import DecisionLedger
from kernel.model_gateway import ModelGateway
from kernel.scene_payloads import validate_asset_registry_payload, validate_scene_spec_payload
from kernel.spec_compiler import compile_objective_spec
from kernel.structure import ProjectStructureAnalyzer


_RETRY_POLICY: dict[str, int] = {
    "director_plan": 2,
    "architect_proposal": 2,
    "programmer_implementation": 2,
    "qa_analysis": 1,
}


def _fallback_director_plan(objective: str) -> dict[str, Any]:
    return {
        "status": "ok",
        "model": "deterministic-fallback",
        "plan": {
            "plan_summary": f"Fallback deterministic plan for objective: {objective}",
            "priorities": [
                "Initialize project directory",
                "Set up main scene",
                "Configure player script",
            ],
            "assignments": [
                {
                    "task": "Initialize project directory",
                    "assigned_agent": "director",
                    "ledger_required": True,
                },
                {
                    "task": "Set up main scene",
                    "assigned_agent": "architect",
                    "ledger_required": True,
                },
                {
                    "task": "Configure player script",
                    "assigned_agent": "programmer",
                    "ledger_required": True,
                },
            ],
            "proposal_audit": [
                "Fallback plan used due to retryable director planning failure",
            ],
            "ledger_notes": [
                "Deterministic fallback used to preserve orchestration continuity",
            ],
        },
        "validation": {
            "fallback": True,
            "reason": "director_plan retry exhaustion",
        },
    }


def _fallback_architect_proposal(task_id: int, objective: str) -> dict[str, Any]:
    return {
        "model": "deterministic-fallback",
        "task_id": task_id,
        "ledger_entry": {
            "problem": "Set up main scene",
            "context": f"Fallback architecture proposal for objective: {objective}",
            "options": "Use deterministic scene scaffold with required objective-spec artifacts.",
            "chosen": "Use deterministic architect scene contract implementation.",
            "tradeoffs": "Lower creativity, higher reliability and reproducibility.",
            "risks": "May not optimize layout quality for complex objectives.",
            "confidence": 0.75,
        },
        "rationale": "Architect fallback used after retryable proposal failures.",
        "module_plan": [
            "Use deterministic scene scaffold",
            "Ensure objective-spec acceptance fields are represented",
            "Proceed with contract-based implementation",
        ],
        "validation": {
            "fallback": True,
            "reason": "architect_proposal retry exhaustion",
        },
    }


def _recovery_policy_payload() -> dict[str, Any]:
    return {
        "retry_policy": dict(_RETRY_POLICY),
        "retryable_error_signatures": [
            "llm returned invalid json",
            "missing key in plan json",
            "missing key in",
            "schema",
            "timed out",
            "timeout",
            "connection reset",
            "temporarily unavailable",
        ],
    }


def _recovery_payload_with_fallback(
    director_fallback_used: bool,
    director_fallback_reason: str | None,
    architect_fallback_used: bool,
    architect_fallback_reason: str | None,
) -> dict[str, Any]:
    payload = _recovery_policy_payload()
    payload["fallbacks"] = {
        "director_plan": {
            "used": director_fallback_used,
            "reason": director_fallback_reason,
        },
        "architect_proposal": {
            "used": architect_fallback_used,
            "reason": architect_fallback_reason,
        }
    }
    return payload


def _is_retryable_stage_error(result: dict[str, Any]) -> bool:
    if not isinstance(result, dict):
        return False
    message = str(result.get("message", "")).strip().lower()
    if not message:
        return False
    signatures = _recovery_policy_payload()["retryable_error_signatures"]
    return any(signature in message for signature in signatures)


def _default_stage_success(result: dict[str, Any]) -> bool:
    return str(result.get("status", "")).strip().lower() != "error"


def _attempt_status_label(result: dict[str, Any], success: bool) -> str:
    raw_status = str(result.get("status", "")).strip().lower()
    if raw_status:
        return raw_status
    return "ok" if success else "error"


def _invoke_with_retry(
    stage_name: str,
    operation: Callable[[], dict[str, Any]],
    success_predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    max_retries = int(_RETRY_POLICY.get(stage_name, 0))
    attempts: list[dict[str, Any]] = []
    result: dict[str, Any] = {"status": "error", "message": "stage not executed"}
    predicate = success_predicate or _default_stage_success

    for attempt_number in range(1, max_retries + 2):
        try:
            result = operation()
        except Exception as exc:
            result = {
                "status": "error",
                "message": str(exc),
                "exception_type": exc.__class__.__name__,
            }
        success = predicate(result)
        retryable = (not success) and _is_retryable_stage_error(result)
        attempts.append(
            {
                "stage": stage_name,
                "attempt_number": attempt_number,
                "status": _attempt_status_label(result, success),
                "message": str(result.get("message", "")),
                "retryable": retryable,
            }
        )
        if success:
            break
        if not retryable:
            break
        if attempt_number > max_retries:
            break

    return {
        "result": result,
        "attempts": attempts,
        "max_retries": max_retries,
    }


def _format_structure_report(report: dict) -> str:
    lines: list[str] = []
    lines.append("Structural Report")
    lines.append(f"- total_files: {report['total_files']}")
    lines.append(f"- dependency_graph_size: {report['dependency_graph_size']}")

    large_files = report["large_files"]
    if large_files:
        lines.append("- large_files:")
        for entry in large_files:
            lines.append(f"  - {entry['file']} ({entry['lines']} lines)")
    else:
        lines.append("- large_files: none")

    circular_dependencies = report["circular_dependencies"]
    if circular_dependencies:
        lines.append("- circular_dependencies:")
        for cycle in circular_dependencies:
            lines.append(f"  - {' -> '.join(cycle + [cycle[0]])}")
    else:
        lines.append("- circular_dependencies: none")

    return "\n".join(lines)


def _format_validation_report(report: dict) -> str:
    lines: list[str] = []
    lines.append("Godot Validation Report")
    lines.append(f"- total_scenes: {report['total_scenes']}")
    lines.append(f"- total_scripts: {report['total_scripts']}")
    lines.append(f"- scenes_loaded: {report['scenes_loaded']}")
    lines.append(f"- scripts_checked: {report['scripts_checked']}")

    errors = report["errors"]
    warnings = report["warnings"]

    if errors:
        lines.append("- errors:")
        for error in errors:
            lines.append(f"  - {error['file']}: {error['message']}")
    else:
        lines.append("- errors: none")

    if warnings:
        lines.append("- warnings:")
        for warning in warnings:
            lines.append(f"  - {warning['file']}: {warning['message']}")
    else:
        lines.append("- warnings: none")

    return "\n".join(lines)


def _format_ledger_entries(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "Decision Ledger\n- entries: none"

    lines: list[str] = ["Decision Ledger", f"- entries: {len(entries)}"]
    for entry in entries:
        lines.append(
            (
                f"- id={entry['id']} | agent={entry['agent']} | "
                f"confidence={entry['confidence']:.3f} | chosen={entry['chosen']}"
            )
        )
        lines.append(f"  problem: {entry['problem']}")
        lines.append(f"  timestamp: {entry['timestamp']}")
    return "\n".join(lines)


def _format_evolution_proposals(proposals: list[dict[str, Any]]) -> str:
    if not proposals:
        return "Evolution Proposals\n- entries: none"

    lines: list[str] = ["Evolution Proposals", f"- entries: {len(proposals)}"]
    for proposal in proposals:
        lines.append(
            (
                f"- id={proposal['id']} | type={proposal['proposal_type']} | "
                f"target={proposal['target_module']} | risk={proposal['risk']} | "
                f"confidence={proposal['confidence']:.3f} | "
                f"ledger_required={proposal['ledger_required']}"
            )
        )
        lines.append(f"  summary: {proposal['summary']}")
        lines.append(f"  simulated_outcome: {proposal['simulated_outcome']}")
    return "\n".join(lines)


def _read_required_input(prompt: str) -> str:
    value = input(prompt).strip()
    if not value:
        raise ValueError(f"Required input missing for: {prompt}")
    return value


def _read_optional_input(prompt: str, default: str) -> str:
    value = input(prompt).strip()
    return value if value else default


def _parse_csv_values(raw: str) -> list[str]:
    values = [item.strip() for item in raw.split(",")]
    return [item for item in values if item]


def _extract_error_warning_lines(output: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if (
            "objectdb instances leaked at exit" in lowered
            or "unrecognized output string \"misc2\" in mapping" in lowered
        ):
            continue
        if "error" in lowered:
            errors.append(line)
        elif "warning" in lowered:
            warnings.append(line)
    return errors, warnings


def _run_headless_boot(project_path: Path, quit_after: int = 1) -> dict[str, Any]:
    command = [
        "godot",
        "--headless",
        "--path",
        str(project_path),
        "--quit-after",
        str(max(1, int(quit_after))),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout_errors, stdout_warnings = _extract_error_warning_lines(completed.stdout)
    stderr_errors, stderr_warnings = _extract_error_warning_lines(completed.stderr)
    errors = stdout_errors + stderr_errors
    warnings = stdout_warnings + stderr_warnings
    return {
        "returncode": int(completed.returncode),
        "errors": errors,
        "warnings": warnings,
        "stdout_tail": completed.stdout.splitlines()[-40:],
        "stderr_tail": completed.stderr.splitlines()[-40:],
    }


def _run_headless_import_pass(project_path: Path) -> dict[str, Any]:
    command = [
        "godot",
        "--headless",
        "--path",
        str(project_path),
        "--import",
        "--quit-after",
        "1",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout_errors, stdout_warnings = _extract_error_warning_lines(completed.stdout)
    stderr_errors, stderr_warnings = _extract_error_warning_lines(completed.stderr)
    return {
        "returncode": int(completed.returncode),
        "errors": stdout_errors + stderr_errors,
        "warnings": stdout_warnings + stderr_warnings,
        "stdout_tail": completed.stdout.splitlines()[-40:],
        "stderr_tail": completed.stderr.splitlines()[-40:],
    }


def _build_smoke_test_payload(project_name: str, warnings_as_errors: bool) -> dict[str, Any]:
    config = load_kernel_config()
    project_path = config.project_root / "projects" / project_name
    if not project_path.exists():
        return {
            "status": "error",
            "project_name": project_name,
            "passed": False,
            "warnings_as_errors": bool(warnings_as_errors),
            "message": f"Project path does not exist: {project_path}",
        }

    import_report = _run_headless_import_pass(project_path)
    validator = GodotValidator()
    validation_report = validator.validate_project(project_path)
    boot_report = _run_headless_boot(project_path)

    validation_error_count = len(validation_report.get("errors", []))
    validation_warning_count = len(validation_report.get("warnings", []))
    boot_error_count = len(boot_report.get("errors", []))
    boot_warning_count = len(boot_report.get("warnings", []))

    total_errors = validation_error_count + boot_error_count
    total_warnings = validation_warning_count + boot_warning_count
    passed = total_errors == 0 and (not warnings_as_errors or total_warnings == 0)

    recommendations: list[str] = []
    if validation_error_count > 0:
        recommendations.append("Fix script/scene validation errors first (python runner.py validate).")
    if boot_error_count > 0:
        recommendations.append("Inspect startup scene and runtime script wiring for boot-time errors.")
    if total_warnings > 0 and not warnings_as_errors:
        recommendations.append("Warnings detected; rerun with --warnings-as-errors to enforce stricter quality gate.")
    if passed:
        recommendations.append("Smoke test passed. Safe to run playtest and continue iteration.")

    return {
        "status": "ok" if passed else "error",
        "project_name": project_name,
        "passed": passed,
        "warnings_as_errors": bool(warnings_as_errors),
        "import_report": {
            "returncode": int(import_report.get("returncode", 1)),
            "errors": import_report.get("errors", []),
            "warnings": import_report.get("warnings", []),
            "stdout_tail": import_report.get("stdout_tail", []),
            "stderr_tail": import_report.get("stderr_tail", []),
        },
        "summary": {
            "validation_errors": validation_error_count,
            "validation_warnings": validation_warning_count,
            "boot_errors": boot_error_count,
            "boot_warnings": boot_warning_count,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "boot_returncode": int(boot_report.get("returncode", 1)),
        },
        "validation_report": validation_report,
        "boot_report": {
            "returncode": int(boot_report.get("returncode", 1)),
            "errors": boot_report.get("errors", []),
            "warnings": boot_report.get("warnings", []),
            "stdout_tail": boot_report.get("stdout_tail", []),
            "stderr_tail": boot_report.get("stderr_tail", []),
        },
        "recommendations": recommendations,
    }


def _handle_smoke_test(project_name: str, warnings_as_errors: bool) -> None:
    payload = _build_smoke_test_payload(project_name=project_name, warnings_as_errors=warnings_as_errors)
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2))


def _tokenize_template_query(text: str) -> list[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(text).lower())
    tokens = [token for token in normalized.split() if token]
    return [token for token in tokens if token not in {"the", "a", "an", "with", "for", "and", "to"}]


def _fetch_json_url(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "AI_STUDIO_LAB-template-tools",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read().decode("utf-8")
    return json.loads(data)


def _fetch_binary_url(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AI_STUDIO_LAB-template-tools",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _discover_repo_project_paths(repo: str, ref: str) -> list[str]:
    branch_url = f"https://api.github.com/repos/{repo}/branches/{urllib.parse.quote(ref, safe='')}"
    branch_payload = _fetch_json_url(branch_url)
    branch_commit = str(branch_payload.get("commit", {}).get("sha", "")).strip()
    if not branch_commit:
        raise RuntimeError(f"Unable to resolve branch '{ref}' for repo '{repo}'")

    tree_url = f"https://api.github.com/repos/{repo}/git/trees/{branch_commit}?recursive=1"
    tree_payload = _fetch_json_url(tree_url)
    tree_items = tree_payload.get("tree")
    if not isinstance(tree_items, list):
        raise RuntimeError("Invalid tree payload returned by GitHub API")

    project_dirs: set[str] = set()
    for item in tree_items:
        if not isinstance(item, dict):
            continue
        if str(item.get("type", "")).strip().lower() != "blob":
            continue
        item_path = str(item.get("path", "")).strip()
        if not item_path.endswith("project.godot"):
            continue
        parent = Path(item_path).parent.as_posix().strip()
        if parent:
            project_dirs.add(parent)

    return sorted(project_dirs)


def _score_template_candidate(path: str, query_tokens: list[str]) -> int:
    lowered = path.lower()
    score = 0
    for token in query_tokens:
        if token in lowered:
            score += 3
    if lowered.startswith("2d/"):
        score += 1
    if lowered.startswith("3d/"):
        score += 1
    score += max(0, 6 - min(len(path.split("/")), 6))
    return score


def _search_repo_templates(query: str, repo: str, ref: str, limit: int) -> dict[str, Any]:
    query_tokens = _tokenize_template_query(query)
    generic_tokens = {"2d", "3d", "gui", "demo", "project"}
    meaningful_tokens = [token for token in query_tokens if token not in generic_tokens]
    project_paths = _discover_repo_project_paths(repo=repo, ref=ref)
    ranked: list[dict[str, Any]] = []
    for path in project_paths:
        score = _score_template_candidate(path, query_tokens)
        lowered = path.lower()
        meaningful_match_count = sum(1 for token in meaningful_tokens if token in lowered)
        if query_tokens and score <= 0:
            continue
        if meaningful_tokens and meaningful_match_count == 0:
            continue
        ranked.append(
            {
                "path": path,
                "score": score,
                "meaningful_match_count": meaningful_match_count,
                "template_name": Path(path).name.replace("_", " "),
            }
        )
    ranked.sort(
        key=lambda item: (
            int(item["meaningful_match_count"]),
            int(item["score"]),
            str(item["path"]),
        ),
        reverse=True,
    )
    effective_limit = max(1, int(limit))
    return {
        "status": "ok",
        "repo": repo,
        "ref": ref,
        "query": query,
        "tokens": query_tokens,
        "total_candidates": len(ranked),
        "candidates": ranked[:effective_limit],
    }


def _template_usage_advice(objective: str) -> dict[str, Any]:
    text = str(objective).strip().lower()
    if not text:
        return {
            "status": "ok",
            "should_use_template": True,
            "confidence": 0.6,
            "reasons": ["No objective text provided; templates reduce ambiguity for initial builds."],
            "recommended_queries": ["2d platformer", "2d top down", "inventory gui"],
        }

    template_signals = {
        "platformer": "2d platformer",
        "top down": "2d top down",
        "rpg": "2d role playing game",
        "inventory": "gui inventory",
        "dialogue": "dialogue",
        "save": "save load",
        "shooter": "2d shooter",
        "vehicle": "vehicle",
        "network": "networking",
        "procgen": "2d procedural generation",
        "mapgen": "2d procedural generation",
        "procedural map": "2d procedural generation",
        "terrain generator": "2d procedural generation",
        "world generator": "2d procedural generation",
    }
    avoid_signals = ["minimal", "single scene", "from scratch", "blank", "prototype shell"]

    matched_queries: list[str] = []
    for signal, query in template_signals.items():
        if signal in text and query not in matched_queries:
            matched_queries.append(query)

    avoid_matched = [signal for signal in avoid_signals if signal in text]
    should_use = bool(matched_queries) and not bool(avoid_matched)
    confidence = 0.8 if should_use else 0.55
    reasons: list[str] = []
    if matched_queries:
        reasons.append("Objective includes known gameplay/system patterns that map to reusable templates.")
    if avoid_matched:
        reasons.append("Objective asks for ultra-minimal or from-scratch setup; template overhead may slow iteration.")
    if not reasons:
        reasons.append("Objective does not strongly indicate template-heavy systems.")

    if not matched_queries:
        matched_queries = ["2d top down", "2d platformer", "gui inventory"]

    return {
        "status": "ok",
        "should_use_template": should_use,
        "confidence": confidence,
        "reasons": reasons,
        "recommended_queries": matched_queries,
    }


def _rank_installed_templates_for_objective(objective: str, installed_paths: list[str], limit: int = 2) -> list[str]:
    tokens = _tokenize_template_query(objective)
    ranked: list[tuple[int, str]] = []
    procgen_objective = any(token in tokens for token in ("procgen", "mapgen", "procedural", "terrain", "world"))
    for path in installed_paths:
        lowered = str(path).lower()
        score = 0
        for token in tokens:
            if token in lowered:
                score += 3
        if "role_playing" in lowered and ("top" in tokens or "rpg" in tokens or "inventory" in tokens):
            score += 2
        if "platformer" in lowered and "platformer" in tokens:
            score += 2
        if "ui" in lowered and ("ui" in tokens or "inventory" in tokens or "dialogue" in tokens):
            score += 2
        if procgen_objective and any(
            marker in lowered for marker in ("procedural", "procgen", "map", "terrain", "world")
        ):
            score += 3
        if procgen_objective:
            if lowered.startswith("2d/"):
                score += 6
            elif lowered.startswith("3d/"):
                score -= 4
        ranked.append((score, path))

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    positive = [path for score, path in ranked if score > 0]
    if positive:
        return positive[: max(1, int(limit))]
    return [path for _score, path in ranked[: max(1, int(limit))]]


def _build_orchestrate_template_guidance(
    objective: str,
    project_name: str,
    precheck_enabled: bool,
) -> dict[str, Any]:
    if not precheck_enabled:
        return {
            "status": "skipped",
            "project_name": project_name,
            "precheck_enabled": False,
            "message": "Template advisor precheck disabled by operator flag.",
        }

    advice = _template_usage_advice(objective)
    library = _load_template_library_index(project_name)
    templates = library.get("templates", []) if isinstance(library, dict) else []
    installed_paths = [
        str(item.get("template_path", "")).strip()
        for item in templates
        if isinstance(item, dict) and str(item.get("template_path", "")).strip()
    ]
    recommended_installed = _rank_installed_templates_for_objective(objective, installed_paths, limit=2)

    should_use_template = bool(advice.get("should_use_template", False))
    return {
        "status": "ok",
        "project_name": project_name,
        "precheck_enabled": True,
        "usage_advice": advice,
        "installed_template_count": len(installed_paths),
        "recommended_installed_templates": recommended_installed if should_use_template else [],
        "decision": {
            "use_template": should_use_template and bool(recommended_installed),
            "reason": (
                "Template-friendly objective with matching installed templates"
                if should_use_template and recommended_installed
                else "No matching installed templates or objective does not require templates"
            ),
        },
        "next_steps": (
            [
                "Use recommended installed templates as reference/bootstrap before implementation.",
                "If no good template exists, run template-fetch --common-pack or template-search + template-fetch.",
            ]
            if should_use_template
            else ["Proceed without template bootstrap for this objective."]
        ),
    }


def _apply_template_bootstrap(
    project_name: str,
    guidance: dict[str, Any],
    max_starter_files: int = 24,
) -> dict[str, Any]:
    if str(guidance.get("status", "")).strip().lower() != "ok":
        return {
            "status": "skipped",
            "project_name": project_name,
            "reason": "template_guidance_not_available",
        }

    decision = guidance.get("decision")
    if not isinstance(decision, dict) or not bool(decision.get("use_template", False)):
        return {
            "status": "skipped",
            "project_name": project_name,
            "reason": "guidance_did_not_recommend_template",
        }

    recommended = guidance.get("recommended_installed_templates")
    if not isinstance(recommended, list) or not recommended:
        return {
            "status": "skipped",
            "project_name": project_name,
            "reason": "no_recommended_template_paths",
        }

    library = _load_template_library_index(project_name)
    template_entries = library.get("templates") if isinstance(library, dict) else []
    entry_by_template_path: dict[str, dict[str, Any]] = {}
    if isinstance(template_entries, list):
        for item in template_entries:
            if not isinstance(item, dict):
                continue
            template_path = str(item.get("template_path", "")).strip()
            if template_path:
                entry_by_template_path[template_path] = item

    chosen_template_path = ""
    chosen_local_path = ""
    for template_path in recommended:
        key = str(template_path).strip()
        if not key:
            continue
        candidate = entry_by_template_path.get(key)
        if not isinstance(candidate, dict):
            continue
        local_path = str(candidate.get("local_path", "")).strip()
        if not local_path:
            continue
        candidate_path = Path(local_path)
        if candidate_path.exists() and candidate_path.is_dir():
            chosen_template_path = key
            chosen_local_path = local_path
            break

    if not chosen_template_path or not chosen_local_path:
        return {
            "status": "skipped",
            "project_name": project_name,
            "reason": "recommended_templates_not_installed",
            "recommended_templates": recommended,
        }

    config = load_kernel_config()
    project_root = config.project_root
    bootstrap_root = project_root / "projects" / project_name / "template_bootstrap"
    destination = bootstrap_root / "current"

    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(chosen_local_path), destination)

    starter_files: list[str] = []
    preferred_names = {
        "project.godot",
        "main.tscn",
        "player.gd",
        "world.gd",
        "level.gd",
        "hud.gd",
        "ui.gd",
    }
    candidates: list[Path] = []
    for file_path in destination.rglob("*"):
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()
        if suffix in {".gd", ".tscn", ".tres", ".tscn", ".cfg"} or file_path.name == "project.godot":
            candidates.append(file_path)

    candidates.sort(key=lambda item: item.as_posix())
    preferred = [item for item in candidates if item.name.lower() in preferred_names]
    ordered = preferred + [item for item in candidates if item not in preferred]

    for file_path in ordered[: max(1, int(max_starter_files))]:
        starter_files.append(file_path.relative_to(project_root).as_posix())

    return {
        "status": "applied",
        "project_name": project_name,
        "template_path": chosen_template_path,
        "source_local_path": chosen_local_path,
        "bootstrap_path": destination.relative_to(project_root).as_posix(),
        "starter_files": starter_files,
        "starter_file_count": len(starter_files),
    }


def _template_library_root(project_name: str) -> Path:
    config = load_kernel_config()
    return config.project_root / "projects" / project_name / "templates"


def _template_library_index_path(project_name: str) -> Path:
    return _template_library_root(project_name) / "library_index.json"


def _load_template_library_index(project_name: str) -> dict[str, Any]:
    index_path = _template_library_index_path(project_name)
    if not index_path.exists():
        return {
            "status": "ok",
            "project_name": project_name,
            "templates": [],
        }
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "status": "ok",
            "project_name": project_name,
            "templates": [],
        }
    templates = payload.get("templates")
    if not isinstance(templates, list):
        templates = []
    return {
        "status": "ok",
        "project_name": project_name,
        "templates": templates,
    }


def _write_template_library_index(project_name: str, templates: list[dict[str, Any]]) -> None:
    root = _template_library_root(project_name)
    root.mkdir(parents=True, exist_ok=True)
    index_path = _template_library_index_path(project_name)
    payload = {
        "status": "ok",
        "project_name": project_name,
        "updated_at": datetime.now(UTC).isoformat(),
        "templates": templates,
    }
    index_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2), encoding="utf-8")


def _safe_template_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value.strip("/"))
    return slug.strip("_") or "template"


def _extract_repo_subdir_archive(archive_bytes: bytes, subdir: str, destination: Path) -> dict[str, Any]:
    target_subdir = subdir.strip("/")
    if not target_subdir:
        raise ValueError("Template path is required")

    destination.mkdir(parents=True, exist_ok=True)
    file_count = 0
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for member in archive.infolist():
            member_name = member.filename
            parts = member_name.split("/", 1)
            if len(parts) != 2:
                continue
            relative_path = parts[1]
            if not (relative_path == target_subdir or relative_path.startswith(f"{target_subdir}/")):
                continue
            tail = relative_path[len(target_subdir):].lstrip("/")
            if not tail:
                continue

            tail_path = Path(tail)
            if ".." in tail_path.parts:
                continue
            output_path = destination / tail_path
            if member.is_dir():
                output_path.mkdir(parents=True, exist_ok=True)
                continue

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source_file:
                output_path.write_bytes(source_file.read())
            file_count += 1

    return {
        "status": "ok",
        "file_count": file_count,
        "destination": destination.as_posix(),
    }


def _fetch_single_template(
    project_name: str,
    repo: str,
    ref: str,
    template_path: str,
    source_query: str,
) -> dict[str, Any]:
    template_root = _template_library_root(project_name)
    slug = _safe_template_slug(template_path)
    destination = template_root / slug

    if destination.exists():
        shutil.rmtree(destination)

    archive_url = f"https://codeload.github.com/{repo}/zip/refs/heads/{urllib.parse.quote(ref, safe='')}"
    archive_bytes = _fetch_binary_url(archive_url)
    extract_result = _extract_repo_subdir_archive(archive_bytes=archive_bytes, subdir=template_path, destination=destination)
    if int(extract_result.get("file_count", 0)) == 0:
        raise RuntimeError(f"Template path not found in archive: {template_path}")

    index_payload = _load_template_library_index(project_name)
    templates = [entry for entry in index_payload["templates"] if str(entry.get("template_path")) != template_path]
    templates.append(
        {
            "template_path": template_path,
            "repo": repo,
            "ref": ref,
            "local_path": destination.as_posix(),
            "fetched_at": datetime.now(UTC).isoformat(),
            "source_query": source_query,
        }
    )
    _write_template_library_index(project_name, templates)

    return {
        "status": "ok",
        "project_name": project_name,
        "template_path": template_path,
        "local_path": destination.as_posix(),
        "files": int(extract_result.get("file_count", 0)),
        "repo": repo,
        "ref": ref,
        "source_query": source_query,
    }


def _resolve_common_template_paths(repo: str, ref: str, max_common: int) -> list[dict[str, str]]:
    scenarios = [
        ("platformer", "2d platformer", ["2d/platformer", "2d/physics_platformer"]),
        ("top_down", "top down", ["2d/top_down_movement", "2d/role_playing_game"]),
        ("inventory", "inventory", ["gui/inventory", "2d/role_playing_game"]),
        ("shooter", "2d shooter"),
    ]
    selected: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    all_paths = _discover_repo_project_paths(repo=repo, ref=ref)
    for scenario in scenarios:
        if len(scenario) == 3:
            label, query, preferred_paths = scenario
        else:
            label, query = scenario
            preferred_paths = []

        preferred_match = ""
        for preferred in preferred_paths:
            if preferred in all_paths:
                preferred_match = preferred
                break

        if preferred_match and preferred_match not in seen_paths:
            seen_paths.add(preferred_match)
            selected.append({"scenario": label, "query": query, "path": preferred_match})
            if len(selected) >= max(1, int(max_common)):
                break
            continue

        search_payload = _search_repo_templates(query=query, repo=repo, ref=ref, limit=6)
        for candidate in search_payload.get("candidates", []):
            path = str(candidate.get("path", "")).strip()
            if not path or path in seen_paths:
                continue
            seen_paths.add(path)
            selected.append({"scenario": label, "query": query, "path": path})
            break
        if len(selected) >= max(1, int(max_common)):
            break
    return selected


def _resolve_procgen_template_paths(repo: str, ref: str, max_procgen: int) -> list[dict[str, str]]:
    scenarios = [
        ("procgen_tilemap", "procedural tilemap", ["2d/procedural_generation", "2d/roguelike"]),
        ("terrain_noise", "terrain noise", ["2d/procedural_generation"]),
        ("world_gen", "world generation", ["2d/procedural_generation", "2d/role_playing_game"]),
    ]
    selected: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    all_paths = _discover_repo_project_paths(repo=repo, ref=ref)
    for scenario in scenarios:
        label, query, preferred_paths = scenario

        preferred_match = ""
        for preferred in preferred_paths:
            if preferred in all_paths:
                preferred_match = preferred
                break

        if preferred_match and preferred_match not in seen_paths:
            seen_paths.add(preferred_match)
            selected.append({"scenario": label, "query": query, "path": preferred_match})
            if len(selected) >= max(1, int(max_procgen)):
                break
            continue

        search_payload = _search_repo_templates(query=query, repo=repo, ref=ref, limit=8)
        candidates = [
            str(candidate.get("path", "")).strip()
            for candidate in search_payload.get("candidates", [])
            if isinstance(candidate, dict) and str(candidate.get("path", "")).strip()
        ]
        two_d_candidates = [path for path in candidates if path.startswith("2d/")]
        ordered = two_d_candidates + [path for path in candidates if path not in two_d_candidates]
        for path in ordered:
            if path in seen_paths:
                continue
            seen_paths.add(path)
            selected.append({"scenario": label, "query": query, "path": path})
            break
        if len(selected) >= max(1, int(max_procgen)):
            break
    return selected


def _handle_template_search(query: str, repo: str, ref: str, limit: int) -> None:
    advice = _template_usage_advice(query)
    payload = _search_repo_templates(query=query, repo=repo, ref=ref, limit=limit)
    payload["usage_advice"] = advice
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2))


def _handle_template_advisor(objective: str, project_name: str) -> None:
    advice = _template_usage_advice(objective)
    library = _load_template_library_index(project_name)
    available_templates = library.get("templates", []) if isinstance(library, dict) else []
    available_queries = [str(item.get("template_path", "")) for item in available_templates if isinstance(item, dict)]
    payload = {
        "status": "ok",
        "project_name": project_name,
        "objective": objective,
        "usage_advice": advice,
        "installed_template_count": len(available_templates),
        "installed_template_paths": available_queries[:20],
        "operator_default": {
            "recommended": "Install a common-pack once, then use template-advisor for each objective.",
            "commands": [
                "python runner.py template-fetch --project-name sandbox_project --common-pack",
                "python runner.py template-advisor --project-name sandbox_project --objective \"<objective sentence>\"",
            ],
        },
    }
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2))


def _handle_template_fetch(
    project_name: str,
    repo: str,
    ref: str,
    template_path: str | None,
    query: str | None,
    common_pack: bool,
    max_common: int,
    procgen_pack: bool,
    max_procgen: int,
) -> None:
    installed: list[dict[str, Any]] = []
    selected_from_search: list[dict[str, Any]] = []

    def _print_error(message: str, context: dict[str, Any] | None = None) -> None:
        payload = {
            "status": "error",
            "project_name": project_name,
            "repo": repo,
            "ref": ref,
            "message": message,
            "hint": "Try template-search first, then use --path or --query with a known candidate.",
        }
        if context:
            payload.update(context)
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2))

    try:
        if common_pack or procgen_pack:
            selected: list[dict[str, str]] = []
            if common_pack:
                selected.extend(_resolve_common_template_paths(repo=repo, ref=ref, max_common=max_common))
            if procgen_pack:
                selected.extend(_resolve_procgen_template_paths(repo=repo, ref=ref, max_procgen=max_procgen))

            deduped: list[dict[str, str]] = []
            seen_paths: set[str] = set()
            for item in selected:
                path = str(item.get("path", "")).strip()
                if not path or path in seen_paths:
                    continue
                seen_paths.add(path)
                deduped.append(item)

            selected = deduped
            for item in selected:
                fetched = _fetch_single_template(
                    project_name=project_name,
                    repo=repo,
                    ref=ref,
                    template_path=item["path"],
                    source_query=item["query"],
                )
                installed.append(fetched)
                selected_from_search.append(item)
        else:
            resolved_path = str(template_path or "").strip()
            source_query = "direct-path"
            if not resolved_path:
                if not query:
                    _print_error("template-fetch requires --path, --query, --common-pack, or --procgen-pack")
                    return
                search_payload = _search_repo_templates(query=query, repo=repo, ref=ref, limit=1)
                candidates = search_payload.get("candidates", [])
                if not candidates:
                    _print_error(
                        message=f"No template candidates found for query: {query}",
                        context={
                            "query": query,
                            "suggested_next": [
                                "python runner.py template-search --query \"2d platformer\"",
                                "python runner.py template-search --query \"top down\"",
                                "python runner.py template-search --query \"ui mirroring\"",
                            ],
                        },
                    )
                    return
                candidate = candidates[0]
                resolved_path = str(candidate.get("path", "")).strip()
                source_query = str(query)
                selected_from_search.append(candidate)

            fetched = _fetch_single_template(
                project_name=project_name,
                repo=repo,
                ref=ref,
                template_path=resolved_path,
                source_query=source_query,
            )
            installed.append(fetched)
    except Exception as exc:
        _print_error(str(exc))
        return

    library = _load_template_library_index(project_name)
    payload = {
        "status": "ok",
        "project_name": project_name,
        "repo": repo,
        "ref": ref,
        "packs": {
            "common_pack": bool(common_pack),
            "procgen_pack": bool(procgen_pack),
        },
        "installed": installed,
        "selected_from_search": selected_from_search,
        "library_index": {
            "path": _template_library_index_path(project_name).as_posix(),
            "template_count": len(library.get("templates", [])),
        },
        "next_steps": [
            "Use template-advisor per objective to decide if template bootstrap is beneficial.",
            "Reference template files as source patterns; keep generated artifacts in scenes/ and scripts/.",
        ],
    }
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2))


def _discover_project_assets(project_name: str) -> list[str]:
    config = load_kernel_config()
    project_root = config.project_root
    assets_root = project_root / "projects" / project_name / "assets"
    fallback_root = project_root / "projects" / project_name / "game_assets"
    search_roots = [assets_root, fallback_root]
    allowed_extensions = {".glb", ".gltf", ".png", ".wav", ".ogg", ".mp3"}

    discovered: list[str] = []
    seen: set[str] = set()
    for root in search_roots:
        if not root.exists() or not root.is_dir():
            continue
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in allowed_extensions:
                continue
            relative = file_path.relative_to(project_root).as_posix()
            if relative in seen:
                continue
            seen.add(relative)
            discovered.append(relative)

    discovered.sort()
    return discovered


def _build_asset_catalog(asset_paths: list[str]) -> dict[str, Any]:
    roles: dict[str, list[str]] = {
        "characters": [],
        "terrain": [],
        "vegetation": [],
        "rocks": [],
        "structures": [],
        "caves": [],
        "audio": [],
        "other": [],
    }

    for raw_path in asset_paths:
        path = str(raw_path).strip()
        if not path:
            continue
        lower = path.lower()
        ext = Path(path).suffix.lower()

        if ext in {".wav", ".ogg", ".mp3"}:
            roles["audio"].append(path)
            continue

        if ext not in {".glb", ".gltf", ".png"}:
            roles["other"].append(path)
            continue

        if any(token in lower for token in ("ranger", "knight", "mage", "rogue", "barbarian", "character", "adventurer")):
            roles["characters"].append(path)
            continue

        if any(token in lower for token in ("cave", "dungeon", "mine", "tunnel")):
            roles["caves"].append(path)
            continue

        if any(token in lower for token in ("house", "hut", "building", "tower", "gate", "door", "bridge", "wall")):
            roles["structures"].append(path)
            continue

        if any(token in lower for token in ("tree", "bush", "shrub", "plant", "grass", "flower")):
            roles["vegetation"].append(path)
            continue

        if any(token in lower for token in ("rock", "stone", "boulder")):
            roles["rocks"].append(path)
            continue

        if any(token in lower for token in ("terrain", "ground", "tile", "forest_texture", "path", "road", "dirt")):
            roles["terrain"].append(path)
            continue

        roles["other"].append(path)

    counts = {key: len(value) for key, value in roles.items()}
    return {
        "total_assets": len(asset_paths),
        "role_counts": counts,
        "roles": roles,
    }


def _select_preferred_asset(paths: list[str], preferred_terms: list[str]) -> str:
    if not paths:
        return ""
    model_paths = [item for item in paths if Path(item).suffix.lower() in {".glb", ".gltf"}]
    ordered_paths = model_paths + [item for item in paths if item not in model_paths]
    lowered = [item.lower() for item in ordered_paths]
    for term in preferred_terms:
        needle = term.strip().lower()
        if not needle:
            continue
        for index, candidate in enumerate(lowered):
            if needle in candidate:
                return ordered_paths[index]
    return ordered_paths[0]


def _asset_brief_to_objectives(brief: dict[str, Any]) -> dict[str, Any]:
    project_name = str(brief.get("project_name", "sandbox_project")).strip() or "sandbox_project"
    genre_template = str(brief.get("genre_template", "top-down adventure prototype")).strip() or "top-down adventure prototype"
    goal = str(brief.get("goal", "collect items and unlock the exit")).strip() or "collect items and unlock the exit"
    character_preference = str(brief.get("character_preference", "ranger")).strip() or "ranger"

    provided_assets = brief.get("asset_paths")
    if isinstance(provided_assets, list) and provided_assets:
        asset_paths = [str(item).strip() for item in provided_assets if str(item).strip()]
    else:
        asset_paths = _discover_project_assets(project_name)

    catalog = _build_asset_catalog(asset_paths)
    roles = catalog["roles"]

    character_asset = str(brief.get("character_asset", "")).strip()
    if not character_asset:
        character_asset = _select_preferred_asset(
            roles["characters"],
            [character_preference, "ranger", "character"],
        )

    terrain_assets = brief.get("terrain_assets")
    terrain_candidates = roles["terrain"] + roles["vegetation"] + roles["rocks"]
    if isinstance(terrain_assets, list) and terrain_assets:
        selected_terrain_assets = [str(item).strip() for item in terrain_assets if str(item).strip()]
    else:
        selected_terrain_assets = terrain_candidates[:6]

    structure_assets = brief.get("structure_assets")
    if isinstance(structure_assets, list) and structure_assets:
        selected_structure_assets = [str(item).strip() for item in structure_assets if str(item).strip()]
    else:
        selected_structure_assets = roles["structures"][:4]

    cave_assets = brief.get("cave_assets")
    if isinstance(cave_assets, list) and cave_assets:
        selected_cave_assets = [str(item).strip() for item in cave_assets if str(item).strip()]
    else:
        selected_cave_assets = roles["caves"][:2]

    audio_assets = brief.get("audio_assets")
    if isinstance(audio_assets, list) and audio_assets:
        selected_audio_assets = [str(item).strip() for item in audio_assets if str(item).strip()]
    else:
        selected_audio_assets = roles["audio"][:3]

    missing_roles: list[str] = []
    if not character_asset:
        missing_roles.append("character_asset")
    if not selected_terrain_assets:
        missing_roles.append("terrain_assets")

    assignments = {
        "character_asset": character_asset,
        "terrain_assets": selected_terrain_assets,
        "structure_assets": selected_structure_assets,
        "cave_assets": selected_cave_assets,
        "audio_assets": selected_audio_assets,
    }

    genre_lower = genre_template.lower()
    if "isometric" in genre_lower or "2.5d" in genre_lower:
        style_phrase = "isometric 2.5D exploration prototype"
        loop_phrase = "walks across mixed terrain, gathers key items, and unlocks a final door"
    elif "tower" in genre_lower and "defense" in genre_lower:
        style_phrase = "tower-defense slice"
        loop_phrase = "places defenses and survives timed waves"
    elif "runner" in genre_lower:
        style_phrase = "endless-runner slice"
        loop_phrase = "avoids hazards and collects pickups to increase score"
    else:
        style_phrase = f"{genre_template} prototype"
        loop_phrase = goal

    character_name = Path(character_asset).stem if character_asset else "player character"
    terrain_count = len(selected_terrain_assets)
    structure_count = len(selected_structure_assets)
    cave_count = len(selected_cave_assets)

    use_cases = [
        f"Use {character_name} as the controllable player avatar.",
        f"Populate world terrain with {terrain_count} terrain/vegetation/rock assets.",
        f"Place {structure_count} structure assets and {cave_count} cave assets as exploration landmarks.",
        "Implement collectible objective items that unlock a final door/win trigger.",
    ]

    if selected_audio_assets:
        use_cases.append("Bind available audio assets to pickup/win/background channels.")
    else:
        use_cases.append("Use procedural audio for pickup/win/background if no audio files are available.")

    artifact_targets = [
        f"projects/{project_name}/scenes/Main.tscn",
        f"projects/{project_name}/scripts/player.gd",
        f"projects/{project_name}/scripts/world_builder.gd",
        f"projects/{project_name}/scripts/objective_system.gd",
    ]

    acceptance = (
        "scene loads with no missing-resource errors, player movement works, collectibles update counter, "
        "door unlocks when objective count reached, and Godot validation has zero errors"
    )

    minimal = (
        f"Build a {style_phrase} where player {loop_phrase}, use {character_name}, target Main.tscn + player.gd, "
        f"acceptance: {acceptance}."
    )
    balanced = (
        f"Implement a {style_phrase} using asset roles (character, terrain, structures), include a collectible-to-door objective loop, "
        f"target Main.tscn + player.gd + world_builder.gd, acceptance: {acceptance}."
    )
    strict = (
        f"Implement a {style_phrase} with {terrain_count} terrain assets, {structure_count} structures, {cave_count} caves, and explicit win-state UI; "
        f"target Main.tscn + world_builder.gd + objective_system.gd, acceptance: {acceptance}."
    )

    available_asset_list = {
        key: value[:20]
        for key, value in roles.items()
    }

    return {
        "status": "ok",
        "project_name": project_name,
        "genre_template": genre_template,
        "goal": goal,
        "asset_catalog_summary": {
            "total_assets": catalog["total_assets"],
            "role_counts": catalog["role_counts"],
        },
        "available_asset_list": available_asset_list,
        "asset_role_assignments": assignments,
        "missing_asset_roles": missing_roles,
        "suggested_use_cases": use_cases,
        "artifact_targets": artifact_targets,
        "objectives": [
            {"mode": "minimal", "objective_sentence": minimal, "risk_note": "Fastest route; may need one refinement run."},
            {"mode": "balanced", "objective_sentence": balanced, "risk_note": "Good quality/scope tradeoff for current pipeline."},
            {"mode": "strict", "objective_sentence": strict, "risk_note": "Higher complexity may require multiple runs."},
        ],
    }


def _read_png_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
        if len(header) < 24:
            return None, None
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            return None, None
        width, height = struct.unpack(">II", header[16:24])
        return int(width), int(height)
    except Exception:
        return None, None


def _role_candidates_for_asset(path: str) -> tuple[list[str], str]:
    lowered = str(path).lower()
    suffix = Path(path).suffix.lower()

    if suffix in {".wav", ".ogg", ".mp3"}:
        return ["audio_track_primary"], "audio"

    if any(token in lowered for token in ("font", ".ttf", ".otf")):
        return ["hud_font_primary"], "font"

    if any(token in lowered for token in ("ranger", "hero", "player", "adventurer", "protagonist")):
        return ["player_sprite_primary"], "texture"

    if any(token in lowered for token in ("enemy", "monster", "slime", "skeleton", "boss")):
        return ["enemy_sprite_primary"], "texture"

    if any(token in lowered for token in ("npc", "villager", "merchant", "civilian")):
        return ["npc_sprite_primary"], "texture"

    if any(token in lowered for token in ("tile", "tileset", "terrain", "ground", "path", "road", "dirt")):
        return ["ground_tileset_primary", "ground_sprite_fallback"], "texture"

    if any(token in lowered for token in ("tree", "bush", "shrub", "plant", "flower", "grass")):
        return ["prop_tree_variants", "ground_sprite_fallback"], "texture"

    if any(token in lowered for token in ("rock", "stone", "boulder")):
        return ["prop_rock_variants", "ground_sprite_fallback"], "texture"

    if suffix in {".glb", ".gltf"}:
        return ["prop_tree_variants", "prop_rock_variants"], "scene"

    if suffix == ".png":
        return ["ground_sprite_fallback"], "texture"

    return ["unassigned"], "unknown"


def _infer_texture_metadata(project_root: Path, relative_path: str) -> dict[str, Any]:
    absolute_path = project_root / relative_path
    suffix = absolute_path.suffix.lower()
    metadata: dict[str, Any] = {
        "extension": suffix,
        "exists": absolute_path.exists(),
    }
    if suffix != ".png":
        return metadata

    width, height = _read_png_dimensions(absolute_path)
    metadata["width"] = width
    metadata["height"] = height
    lowered = absolute_path.name.lower()

    sprite_sheet = any(marker in lowered for marker in ("sheet", "spritesheet", "atlas", "tileset"))
    metadata["sprite_sheet"] = sprite_sheet

    if width and height and "tile" in lowered:
        for candidate in (64, 48, 32, 24, 16, 8):
            if width % candidate == 0 and height % candidate == 0:
                metadata["tile_size"] = [candidate, candidate]
                metadata["hframes"] = width // candidate
                metadata["vframes"] = height // candidate
                break

    if sprite_sheet and width and height and "hframes" not in metadata:
        for candidate in (8, 6, 5, 4, 3, 2):
            if width % candidate == 0:
                frame_width = width // candidate
                if frame_width > 0 and height % frame_width == 0:
                    metadata["hframes"] = candidate
                    metadata["vframes"] = max(1, height // frame_width)
                    break

    return metadata


def _build_asset_registry_payload(
    project_name: str,
    archetype_id: str = "topdown_adventure_v1",
    asset_paths: list[str] | None = None,
) -> dict[str, Any]:
    config = load_kernel_config()
    project_root = config.project_root
    discovered_assets = asset_paths if asset_paths is not None else _discover_project_assets(project_name)
    normalized_assets = [str(path).strip() for path in discovered_assets if str(path).strip()]

    assets: list[dict[str, Any]] = []
    for index, relative_path in enumerate(normalized_assets, start=1):
        role_candidates, kind = _role_candidates_for_asset(relative_path)
        confidence = 0.9 if role_candidates[0] != "unassigned" else 0.4
        assets.append(
            {
                "asset_id": f"asset_{index:03d}_{Path(relative_path).stem.lower().replace('-', '_').replace(' ', '_')}",
                "path": relative_path,
                "kind": kind,
                "role_candidates": role_candidates,
                "tags": [Path(relative_path).suffix.lower().lstrip(".")],
                "metadata": _infer_texture_metadata(project_root=project_root, relative_path=relative_path),
                "confidence": confidence,
            }
        )

    def _best_asset_id(role: str) -> str:
        candidates = [item for item in assets if role in item["role_candidates"]]
        if not candidates:
            return ""
        candidates.sort(key=lambda item: float(item.get("confidence", 0.0)), reverse=True)
        return str(candidates[0]["asset_id"])

    def _asset_ids(role: str, max_items: int) -> list[str]:
        candidates = [item for item in assets if role in item["role_candidates"]]
        candidates.sort(key=lambda item: float(item.get("confidence", 0.0)), reverse=True)
        return [str(item["asset_id"]) for item in candidates[: max(1, int(max_items))]]

    role_bindings: dict[str, Any] = {
        "player_sprite_primary": _best_asset_id("player_sprite_primary"),
        "enemy_sprite_primary": _best_asset_id("enemy_sprite_primary"),
        "npc_sprite_primary": _best_asset_id("npc_sprite_primary"),
        "ground_tileset_primary": _best_asset_id("ground_tileset_primary"),
        "ground_sprite_fallback": _best_asset_id("ground_sprite_fallback"),
        "hud_font_primary": _best_asset_id("hud_font_primary"),
        "prop_rock_variants": _asset_ids("prop_rock_variants", 3),
        "prop_tree_variants": _asset_ids("prop_tree_variants", 3),
    }

    role_bindings = {
        key: value
        for key, value in role_bindings.items()
        if (isinstance(value, str) and value) or (isinstance(value, list) and value)
    }

    catalog = _build_asset_catalog(normalized_assets)
    payload = {
        "registry_version": 1,
        "project_root": "projects/sandbox_project",
        "archetype_id": str(archetype_id).strip() or "topdown_adventure_v1",
        "assets": assets,
        "role_bindings": role_bindings,
        "discovery_summary": {
            "project_name": project_name,
            "total_assets": len(assets),
            "role_counts": catalog.get("role_counts", {}),
        },
        "warnings": [],
    }

    critical_roles = ["player_sprite_primary", "ground_tileset_primary", "ground_sprite_fallback"]
    for role in critical_roles:
        if role not in role_bindings:
            payload["warnings"].append(f"missing_role_binding:{role}")

    validate_asset_registry_payload(payload)
    return payload


def _build_scene_spec_payload(
    project_name: str,
    asset_registry_payload: dict[str, Any],
    archetype_id: str = "topdown_adventure_v1",
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    role_bindings = asset_registry_payload.get("role_bindings", {})
    has_tileset = bool(role_bindings.get("ground_tileset_primary"))
    terrain_representation = "tilemap" if has_tileset else "sprite_fallback"
    merged_overrides = overrides or {}
    override_terrain = str(merged_overrides.get("terrain_representation", "")).strip().lower()
    if override_terrain in {"tilemap", "sprite_fallback"}:
        terrain_representation = override_terrain

    terrain_grammar = str(merged_overrides.get("terrain_grammar", "")).strip() or "border walls + central path + one water band + bridge"
    prop_tree_count = int(merged_overrides.get("prop_tree_count", 6))
    prop_rock_count = int(merged_overrides.get("prop_rock_count", 4))
    spawn_layout = merged_overrides.get("spawns") if isinstance(merged_overrides.get("spawns"), dict) else {}

    payload = {
        "scene_spec_version": 1,
        "archetype_id": str(archetype_id).strip() or "topdown_adventure_v1",
        "scene_path": f"projects/{project_name}/scenes/Main.tscn",
        "assembly_mode": "create_or_replace",
        "terrain": {
            "representation": terrain_representation,
            "grammar": terrain_grammar,
            "grid_size": [20, 12],
            "tile_size": [16, 16],
            "terrain_types": [
                [1, 1, 1, 1, 1, 1],
                [1, 0, 0, 0, 0, 1],
                [1, 0, 2, 2, 0, 1],
                [1, 0, 0, 0, 0, 1],
                [1, 1, 1, 1, 1, 1],
            ],
            "tileset_role": "ground_tileset_primary",
            "fallback_role": "ground_sprite_fallback",
        },
        "nodes": [
            {
                "node_id": "Main",
                "node_type": "Node2D",
                "parent": "",
                "role": "root",
                "required": True,
            },
            {
                "node_id": "Ground",
                "node_type": "TileMapLayer" if terrain_representation == "tilemap" else "Sprite2D",
                "parent": "Main",
                "role": "ground",
                "asset_role": "ground_tileset_primary" if terrain_representation == "tilemap" else "ground_sprite_fallback",
                "required": True,
            },
            {
                "node_id": "Player",
                "node_type": "CharacterBody2D",
                "parent": "Main",
                "role": "player_actor",
                "asset_role": "player_sprite_primary",
                "script_path": f"projects/{project_name}/scripts/player.gd",
                "required": True,
            },
            {
                "node_id": "Enemy",
                "node_type": "CharacterBody2D",
                "parent": "Main",
                "role": "enemy_actor",
                "asset_role": "enemy_sprite_primary",
                "required": True,
            },
            {
                "node_id": "NPC",
                "node_type": "CharacterBody2D",
                "parent": "Main",
                "role": "npc_actor",
                "asset_role": "npc_sprite_primary",
                "required": True,
            },
            {
                "node_id": "UI",
                "node_type": "CanvasLayer",
                "parent": "Main",
                "role": "ui_root",
                "required": True,
            },
            {
                "node_id": "HealthLabel",
                "node_type": "Label",
                "parent": "UI",
                "role": "hud_label",
                "required": True,
            },
        ],
        "spawns": {
            "player": list(spawn_layout.get("player", [96, 96])),
            "enemy": list(spawn_layout.get("enemy", [224, 96])),
            "npc": list(spawn_layout.get("npc", [160, 160])),
        },
        "props": [
            {
                "prop_role": "prop_tree_variants",
                "placement_mode": "scatter",
                "zone": "outer_grass",
                "count": max(0, prop_tree_count),
                "avoid": ["player_spawn", "enemy_spawn"],
            },
            {
                "prop_role": "prop_rock_variants",
                "placement_mode": "scatter",
                "zone": "path_edges",
                "count": max(0, prop_rock_count),
                "avoid": ["player_spawn", "enemy_spawn"],
            },
        ],
        "ui": {
            "show_stamina_label": True,
            "text_format": "STAMINA: {current}/{max}",
            "font_role": "hud_font_primary",
        },
        "fallbacks": [
            {
                "when": "ground_tileset_primary_unavailable",
                "action": "use_sprite_fallback_ground",
            },
            {
                "when": "npc_sprite_primary_low_confidence",
                "action": "spawn_static_placeholder_color",
            },
        ],
        "acceptance_hints": [
            "required artifacts exist",
            "Main.tscn parse-valid",
            "ground representation present",
            "player spawn valid",
        ],
    }

    validate_scene_spec_payload(payload)
    return payload


def _required_role_binding_violations(asset_registry_payload: dict[str, Any]) -> list[str]:
    role_bindings = asset_registry_payload.get("role_bindings", {}) if isinstance(asset_registry_payload, dict) else {}
    violations: list[str] = []
    if not str(role_bindings.get("player_sprite_primary", "")).strip():
        violations.append("player_sprite_primary")

    has_ground_tileset = bool(str(role_bindings.get("ground_tileset_primary", "")).strip())
    has_ground_fallback = bool(str(role_bindings.get("ground_sprite_fallback", "")).strip())
    if not has_ground_tileset and not has_ground_fallback:
        violations.append("ground_tileset_primary|ground_sprite_fallback")
    return violations


def _extract_terrain_grammar_from_objective(objective: str) -> str:
    text = str(objective)
    match = re.search(r"terrain\s+grammar\s*:\s*(.+)", text, flags=re.IGNORECASE)
    if not match:
        return ""
    value = match.group(1).strip()
    if "\n" in value:
        value = value.split("\n", 1)[0].strip()
    return value


def _infer_scene_spec_overrides_from_architect(architecture_payload: dict[str, Any], objective: str) -> dict[str, Any]:
    module_plan = architecture_payload.get("module_plan", []) if isinstance(architecture_payload, dict) else []
    rationale = str(architecture_payload.get("rationale", "")) if isinstance(architecture_payload, dict) else ""
    ledger_entry = architecture_payload.get("ledger_entry", {}) if isinstance(architecture_payload, dict) else {}

    combined = "\n".join([
        rationale,
        str(ledger_entry.get("chosen", "")),
        str(ledger_entry.get("context", "")),
        "\n".join(str(item) for item in module_plan if isinstance(item, str)),
        str(objective),
    ]).lower()

    overrides: dict[str, Any] = {}
    if any(token in combined for token in ("sprite fallback", "fallback ground", "sprite ground")):
        overrides["terrain_representation"] = "sprite_fallback"
    elif any(token in combined for token in ("tilemap", "terrain connect", "tileset")):
        overrides["terrain_representation"] = "tilemap"

    grammar = _extract_terrain_grammar_from_objective(objective)
    if grammar:
        overrides["terrain_grammar"] = grammar

    if any(token in combined for token in ("dense", "high density", "crowded")):
        overrides["prop_tree_count"] = 10
        overrides["prop_rock_count"] = 8
    elif any(token in combined for token in ("sparse", "low density", "minimal props")):
        overrides["prop_tree_count"] = 3
        overrides["prop_rock_count"] = 2

    return overrides


def _handle_scene_spec(project_name: str, archetype_id: str, output_dir: str | None, no_write: bool) -> None:
    registry_payload = _build_asset_registry_payload(project_name=project_name, archetype_id=archetype_id)
    scene_spec_payload = _build_scene_spec_payload(
        project_name=project_name,
        asset_registry_payload=registry_payload,
        archetype_id=archetype_id,
    )

    result: dict[str, Any] = {
        "status": "ok",
        "project_name": project_name,
        "archetype_id": archetype_id,
        "asset_registry": registry_payload,
        "scene_spec": scene_spec_payload,
    }

    if not no_write:
        config = load_kernel_config()
        default_output_dir = config.project_root / "projects" / project_name / ".studio"
        resolved_output_dir = Path(output_dir) if output_dir else default_output_dir
        resolved_output_dir.mkdir(parents=True, exist_ok=True)

        asset_registry_path = resolved_output_dir / "asset_registry.json"
        scene_spec_path = resolved_output_dir / "scene_spec.json"
        asset_registry_path.write_text(
            json.dumps(registry_payload, ensure_ascii=True, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        scene_spec_path.write_text(
            json.dumps(scene_spec_payload, ensure_ascii=True, sort_keys=True, indent=2),
            encoding="utf-8",
        )

        result["written_files"] = {
            "asset_registry": str(asset_registry_path),
            "scene_spec": str(scene_spec_path),
        }

    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))


def _extract_json_objects_from_text(raw_text: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for line in str(raw_text).splitlines():
        candidate = line.strip()
        if not candidate.startswith("{") or not candidate.endswith("}"):
            continue
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            payloads.append(parsed)
    return payloads


def _run_scene_assembler(
    project_name: str,
    scene_spec_relative_path: str = ".studio/scene_spec.json",
    asset_registry_relative_path: str = ".studio/asset_registry.json",
) -> dict[str, Any]:
    config = load_kernel_config()
    project_path = config.project_root / "projects" / project_name
    command = [
        "godot",
        "--headless",
        "--path",
        str(project_path),
        "--script",
        "tools/scene_assembler.gd",
        "--scene-spec",
        scene_spec_relative_path,
        "--asset-registry",
        asset_registry_relative_path,
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    parsed_payloads = _extract_json_objects_from_text(completed.stdout)
    scene_payload = parsed_payloads[-1] if parsed_payloads else {}

    result = {
        "status": "ok" if completed.returncode == 0 else "error",
        "returncode": int(completed.returncode),
        "scene_payload": scene_payload,
        "stdout_tail": completed.stdout.splitlines()[-80:],
        "stderr_tail": completed.stderr.splitlines()[-80:],
        "command": command,
    }
    if completed.returncode != 0:
        result["message"] = "Godot scene assembler failed"
    return result


def _assemble_scene_from_payloads(project_name: str, archetype_id: str) -> dict[str, Any]:
    config = load_kernel_config()
    studio_dir = config.project_root / "projects" / project_name / ".studio"
    studio_dir.mkdir(parents=True, exist_ok=True)

    asset_registry_payload = _build_asset_registry_payload(project_name=project_name, archetype_id=archetype_id)
    scene_spec_payload = _build_scene_spec_payload(
        project_name=project_name,
        asset_registry_payload=asset_registry_payload,
        archetype_id=archetype_id,
        overrides=None,
    )

    asset_registry_path = studio_dir / "asset_registry.json"
    scene_spec_path = studio_dir / "scene_spec.json"
    asset_registry_path.write_text(
        json.dumps(asset_registry_payload, ensure_ascii=True, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    scene_spec_path.write_text(
        json.dumps(scene_spec_payload, ensure_ascii=True, sort_keys=True, indent=2),
        encoding="utf-8",
    )

    assembler_result = _run_scene_assembler(
        project_name=project_name,
        scene_spec_relative_path=".studio/scene_spec.json",
        asset_registry_relative_path=".studio/asset_registry.json",
    )
    return {
        "status": assembler_result.get("status", "error"),
        "project_name": project_name,
        "archetype_id": archetype_id,
        "payload_paths": {
            "asset_registry": str(asset_registry_path),
            "scene_spec": str(scene_spec_path),
        },
        "asset_registry_summary": {
            "total_assets": int(len(asset_registry_payload.get("assets", []))),
            "warnings": list(asset_registry_payload.get("warnings", [])),
            "role_bindings": sorted(list(asset_registry_payload.get("role_bindings", {}).keys())),
        },
        "assembler": assembler_result,
    }


def _load_scene_assembly_artifacts(project_name: str = "sandbox_project") -> dict[str, Any] | None:
    config = load_kernel_config()
    studio_dir = config.project_root / "projects" / project_name / ".studio"
    assembly_path = studio_dir / "assembly_result.json"
    scene_spec_path = studio_dir / "scene_spec.json"
    asset_registry_path = studio_dir / "asset_registry.json"

    if not assembly_path.exists() and not scene_spec_path.exists() and not asset_registry_path.exists():
        return None

    def _safe_load(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    assembly_payload = _safe_load(assembly_path)
    scene_spec_payload = _safe_load(scene_spec_path)
    asset_registry_payload = _safe_load(asset_registry_path)

    return {
        "files": {
            "assembly_result": str(assembly_path),
            "scene_spec": str(scene_spec_path),
            "asset_registry": str(asset_registry_path),
        },
        "assembly_result": assembly_payload,
        "scene_spec": {
            "archetype_id": (scene_spec_payload or {}).get("archetype_id"),
            "terrain_representation": ((scene_spec_payload or {}).get("terrain") or {}).get("representation"),
            "node_count": len((scene_spec_payload or {}).get("nodes", [])),
        },
        "asset_registry": {
            "total_assets": len((asset_registry_payload or {}).get("assets", [])),
            "warnings": (asset_registry_payload or {}).get("warnings", []),
            "role_bindings": sorted(list(((asset_registry_payload or {}).get("role_bindings") or {}).keys())),
        },
    }


def _build_progress_smoke_snapshot(stage: str, project_name: str = "sandbox_project") -> dict[str, Any]:
    smoke = _build_smoke_test_payload(project_name=project_name, warnings_as_errors=False)
    return {
        "stage": stage,
        "passed": bool(smoke.get("passed", False)),
        "summary": smoke.get("summary", {}),
        "status": smoke.get("status", "error"),
        "errors": [
            *(smoke.get("import_report", {}).get("errors", []) if isinstance(smoke.get("import_report"), dict) else []),
            *(smoke.get("boot_report", {}).get("errors", []) if isinstance(smoke.get("boot_report"), dict) else []),
        ],
    }


def _handle_asset_brief() -> None:
    project_name = _read_optional_input("project_name [sandbox_project]: ", "sandbox_project")
    genre_template = _read_optional_input("genre_template [isometric 2.5D exploration]: ", "isometric 2.5D exploration")
    goal = _read_optional_input("goal [collect items to unlock a door and win]: ", "collect items to unlock a door and win")
    character_preference = _read_optional_input("character_preference [ranger]: ", "ranger")

    preview = _asset_brief_to_objectives(
        {
            "project_name": project_name,
            "genre_template": genre_template,
            "goal": goal,
            "character_preference": character_preference,
        }
    )

    auto_character = str(preview.get("asset_role_assignments", {}).get("character_asset", ""))
    auto_terrain = ", ".join(preview.get("asset_role_assignments", {}).get("terrain_assets", [])[:4])
    auto_structures = ", ".join(preview.get("asset_role_assignments", {}).get("structure_assets", [])[:3])
    auto_caves = ", ".join(preview.get("asset_role_assignments", {}).get("cave_assets", [])[:2])

    character_override = _read_optional_input(
        f"character_asset override [auto: {auto_character or 'none'}]: ",
        auto_character,
    )
    terrain_override_raw = _read_optional_input(
        f"terrain_assets CSV override [auto: {auto_terrain or 'none'}]: ",
        auto_terrain,
    )
    structure_override_raw = _read_optional_input(
        f"structure_assets CSV override [auto: {auto_structures or 'none'}]: ",
        auto_structures,
    )
    cave_override_raw = _read_optional_input(
        f"cave_assets CSV override [auto: {auto_caves or 'none'}]: ",
        auto_caves,
    )

    payload = _asset_brief_to_objectives(
        {
            "project_name": project_name,
            "genre_template": genre_template,
            "goal": goal,
            "character_preference": character_preference,
            "character_asset": character_override,
            "terrain_assets": _parse_csv_values(terrain_override_raw),
            "structure_assets": _parse_csv_values(structure_override_raw),
            "cave_assets": _parse_csv_values(cave_override_raw),
        }
    )
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2))


def _creative_brief_to_objectives(brief: dict[str, Any]) -> dict[str, Any]:
    project_name = str(brief.get("project_name", "sandbox_project")).strip() or "sandbox_project"
    theme = str(brief.get("theme", "creative")).strip() or "creative"
    game_style = str(brief.get("game_style", "2D prototype")).strip() or "2D prototype"
    core_loop = str(brief.get("core_loop", "move and interact")).strip() or "move and interact"
    feel_target = str(brief.get("feel_target", "responsive"))
    presentation_target = str(brief.get("presentation_target", "clear feedback"))
    acceptance = str(
        brief.get(
            "acceptance",
            "baseline artifacts exist and Godot validation has zero errors",
        )
    ).strip() or "baseline artifacts exist and Godot validation has zero errors"
    constraints = str(
        brief.get(
            "constraints",
            "deterministic, low scope, sandbox-only writes",
        )
    ).strip() or "deterministic, low scope, sandbox-only writes"

    artifacts = brief.get("artifact_targets", [])
    if not isinstance(artifacts, list) or not artifacts:
        artifacts = [
            "projects/sandbox_project/scenes/Main.tscn",
            "projects/sandbox_project/scripts/player.gd",
        ]
    artifact_targets = [str(item).strip() for item in artifacts if str(item).strip()]
    artifact_short = [Path(path).name for path in artifact_targets]

    minimal_targets = " + ".join(artifact_short[:2]) if artifact_short else "Main.tscn + player.gd"
    balanced_targets = " + ".join(artifact_short[:3]) if artifact_short else "Main.tscn + player.gd"
    strict_targets = " + ".join(artifact_short) if artifact_short else "Main.tscn + player.gd"

    minimal = (
        f"Build a {theme} {game_style} slice where player {core_loop}, include {presentation_target}, "
        f"target {minimal_targets}, acceptance: {acceptance}."
    )
    balanced = (
        f"Implement a {theme} {game_style} prototype with {feel_target} feel where player {core_loop}, include "
        f"{presentation_target}, target {balanced_targets}, acceptance: {acceptance}."
    )
    strict = (
        f"Implement a {theme} {game_style} build where player {core_loop}, enforce {constraints}, include "
        f"{presentation_target}, target {strict_targets}, acceptance: {acceptance}."
    )

    missing_fields: list[str] = []
    for key in ("theme", "game_style", "core_loop"):
        if not str(brief.get(key, "")).strip():
            missing_fields.append(key)

    return {
        "status": "ok",
        "project_name": project_name,
        "objectives": [
            {
                "mode": "minimal",
                "objective_sentence": minimal,
                "risk_note": "May be too sparse for strong game feel without follow-up refinement.",
            },
            {
                "mode": "balanced",
                "objective_sentence": balanced,
                "risk_note": "Moderate scope; may need one extra run for polish.",
            },
            {
                "mode": "strict",
                "objective_sentence": strict,
                "risk_note": "Constraint-heavy objective can reduce creative variance.",
            },
        ],
        "artifact_targets": artifact_targets,
        "missing_brief_fields": missing_fields,
    }


def _handle_creative_brief() -> None:
    project_name = _read_optional_input("project_name [sandbox_project]: ", "sandbox_project")
    theme = _read_required_input("theme (e.g., cozy, neon arcade): ")
    game_style = _read_required_input("game_style (e.g., top-down prototype): ")
    core_loop = _read_required_input("core_loop (e.g., dodge hazards and collect keys): ")
    feel_target = _read_optional_input("feel_target [responsive]: ", "responsive")
    presentation_target = _read_optional_input(
        "presentation_target [one satisfying feedback effect and one UI label]: ",
        "one satisfying feedback effect and one UI label",
    )
    artifact_targets_raw = _read_optional_input(
        "artifact_targets CSV [projects/sandbox_project/scenes/Main.tscn, projects/sandbox_project/scripts/player.gd]: ",
        "projects/sandbox_project/scenes/Main.tscn, projects/sandbox_project/scripts/player.gd",
    )
    acceptance = _read_optional_input(
        "acceptance [baseline artifacts exist and Godot validation has zero errors]: ",
        "baseline artifacts exist and Godot validation has zero errors",
    )
    constraints = _read_optional_input(
        "constraints [deterministic, low scope, sandbox-only writes]: ",
        "deterministic, low scope, sandbox-only writes",
    )

    payload = _creative_brief_to_objectives(
        {
            "project_name": project_name,
            "theme": theme,
            "game_style": game_style,
            "core_loop": core_loop,
            "feel_target": feel_target,
            "presentation_target": presentation_target,
            "artifact_targets": _parse_csv_values(artifact_targets_raw),
            "acceptance": acceptance,
            "constraints": constraints,
        }
    )
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2))


def _required_artifacts_for_agent(agent_name: str) -> tuple[str, ...]:
    if agent_name == "director":
        return ("projects/sandbox_project/project.godot",)
    if agent_name == "architect":
        return ("projects/sandbox_project/scenes/Main.tscn",)
    if agent_name == "programmer":
        return ("projects/sandbox_project/scripts/player.gd",)
    return tuple()


def _required_pipeline_artifacts() -> tuple[str, ...]:
    return (
        "projects/sandbox_project/project.godot",
        "projects/sandbox_project/scenes/Main.tscn",
        "projects/sandbox_project/scripts/player.gd",
    )


def _artifact_map_from_spec(spec_payload: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    mapping: dict[str, list[str]] = {}
    for artifact in spec_payload.get("artifacts", []):
        owner = str(artifact.get("owner_agent", ""))
        path = str(artifact.get("path", ""))
        if not owner or not path:
            continue
        mapping.setdefault(owner, []).append(path)
    return {key: tuple(value) for key, value in mapping.items()}


def _ensure_decision_ledger_seed() -> dict[str, Any]:
    ledger = DecisionLedger()
    entries = ledger.get_decisions()
    if entries:
        return {
            "status": "existing",
            "entry_id": int(entries[0].get("id", 0)),
            "count": len(entries),
        }

    decision_id = ledger.add_decision(
        problem="Bootstrap decision ledger availability",
        context="Seed initial ledger entry so director orchestration can create and assign tasks.",
        options="1. Keep ledger empty and fail orchestrate\n2. Insert one neutral bootstrap entry",
        chosen="Insert one neutral bootstrap entry",
        tradeoffs="Enables deterministic startup after memory reset with minimal policy impact.",
        risks="Low; entry is auditable and non-task-specific.",
        confidence=0.9,
        agent="kernel_bootstrap",
    )
    return {
        "status": "seeded",
        "entry_id": int(decision_id),
        "count": 1,
    }


def _default_assignment_task(agent_name: str, objective: str) -> str:
    lowered = objective.lower()
    if agent_name == "director":
        return "Initialize project directory"
    if agent_name == "architect":
        if "top-down" in lowered or "top down" in lowered:
            return "Set up top-down main scene with player, enemy, and NPC layout"
        return "Set up main scene"
    if agent_name == "programmer":
        if "enemy" in lowered or "npc" in lowered:
            return "Configure player movement and combat-ready interactions"
        return "Configure player script"
    return "Implement task"


def _normalize_director_plan_assignments(
    plan_payload: dict[str, Any],
    objective_spec_payload: dict[str, Any],
    objective: str,
) -> dict[str, Any]:
    raw_plan = plan_payload.get("plan")
    plan_section = raw_plan if isinstance(raw_plan, dict) else {}
    raw_assignments = plan_section.get("assignments")

    normalized_assignments: list[dict[str, Any]] = []
    seen_required: set[str] = set()

    if isinstance(raw_assignments, list):
        for item in raw_assignments:
            if not isinstance(item, dict):
                continue
            assigned_agent = str(item.get("assigned_agent", "")).strip().lower()
            if assigned_agent not in {"director", "architect", "programmer"}:
                continue
            task_text = str(item.get("task", "")).strip() or _default_assignment_task(assigned_agent, objective)
            normalized_assignments.append(
                {
                    "task": task_text,
                    "assigned_agent": assigned_agent,
                    "ledger_required": bool(item.get("ledger_required", True)),
                }
            )
            seen_required.add(assigned_agent)

    artifact_map = _artifact_map_from_spec(objective_spec_payload)
    required_agents = ["director", "architect", "programmer"]
    for agent_name in required_agents:
        should_require = bool(artifact_map.get(agent_name)) or agent_name in {"architect", "programmer"}
        if should_require and agent_name not in seen_required:
            normalized_assignments.append(
                {
                    "task": _default_assignment_task(agent_name, objective),
                    "assigned_agent": agent_name,
                    "ledger_required": True,
                }
            )
            seen_required.add(agent_name)

    normalized_plan = dict(plan_payload)
    normalized_section = dict(plan_section)
    normalized_section["assignments"] = normalized_assignments
    normalized_section.setdefault(
        "plan_summary",
        f"Normalized plan for objective: {objective}",
    )
    normalized_plan["plan"] = normalized_section
    normalized_plan["plan_normalization"] = {
        "applied": True,
        "assignment_count": len(normalized_assignments),
        "required_agents_present": sorted(seen_required),
    }
    return normalized_plan


def _bootstrap_project_godot(project_root: Path) -> str:
    relative_path = "projects/sandbox_project/project.godot"
    target = (project_root / relative_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    baseline_content = """; Engine configuration file.
; It's best edited using the editor and not directly,
; since the parameters that go here are not all obvious.
;
; Format:
;   [section] ; section goes between []
;   param=value ; assign values to parameters

config_version=5

[application]

config/name=\"AI_STUDIO_LAB Sandbox\"
run/main_scene=\"res://scenes/Main.tscn\"

[display]

window/size/viewport_width=1920
window/size/viewport_height=1080
window/stretch/mode=\"canvas_items\"
window/stretch/aspect=\"expand\"

[rendering]

renderer/rendering_method=\"forward_plus\"
"""
    if not target.exists():
        target.write_text(baseline_content, encoding="utf-8")
        return relative_path

    current = target.read_text(encoding="utf-8")
    required_tokens = (
        "window/size/viewport_width=1920",
        "window/size/viewport_height=1080",
        "window/stretch/mode=\"canvas_items\"",
        "window/stretch/aspect=\"expand\"",
    )
    if all(token in current for token in required_tokens):
        return relative_path

    if "[display]" in current:
        normalized_lines = [line for line in current.splitlines() if not line.startswith("window/size/viewport_width=") and not line.startswith("window/size/viewport_height=") and not line.startswith("window/stretch/mode=") and not line.startswith("window/stretch/aspect=")]
        current = "\n".join(normalized_lines)
        display_block = "\n[display]\n\nwindow/size/viewport_width=1920\nwindow/size/viewport_height=1080\nwindow/stretch/mode=\"canvas_items\"\nwindow/stretch/aspect=\"expand\"\n"
        current = current.replace("[display]\n", display_block)
        target.write_text(current.rstrip() + "\n", encoding="utf-8")
        return relative_path

    target.write_text(current.rstrip() + "\n\n[display]\n\nwindow/size/viewport_width=1920\nwindow/size/viewport_height=1080\nwindow/stretch/mode=\"canvas_items\"\nwindow/stretch/aspect=\"expand\"\n", encoding="utf-8")
    return relative_path


def _handle_reset_sandbox(keep_assets: bool, clear_godot_cache: bool) -> None:
    config = load_kernel_config()
    sandbox_path = config.project_root / "projects" / "sandbox_project"
    if not sandbox_path.exists() or not sandbox_path.is_dir():
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": f"Sandbox project not found: {sandbox_path}",
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
        )
        return

    removed_paths: list[str] = []
    recreated_paths: list[str] = []

    for relative in ("scenes", "scripts"):
        target = sandbox_path / relative
        if target.exists() and target.is_dir():
            shutil.rmtree(target)
            removed_paths.append(str(target.relative_to(config.project_root).as_posix()))
        target.mkdir(parents=True, exist_ok=True)
        recreated_paths.append(str(target.relative_to(config.project_root).as_posix()))

    if not keep_assets:
        assets_path = sandbox_path / "assets"
        if assets_path.exists() and assets_path.is_dir():
            shutil.rmtree(assets_path)
            removed_paths.append(str(assets_path.relative_to(config.project_root).as_posix()))
        assets_path.mkdir(parents=True, exist_ok=True)
        recreated_paths.append(str(assets_path.relative_to(config.project_root).as_posix()))

    if clear_godot_cache:
        cache_path = sandbox_path / ".godot"
        if cache_path.exists() and cache_path.is_dir():
            shutil.rmtree(cache_path)
            removed_paths.append(str(cache_path.relative_to(config.project_root).as_posix()))

    bootstrap_file = _bootstrap_project_godot(config.project_root)

    print(
        json.dumps(
            {
                "status": "ok",
                "sandbox": str(sandbox_path.relative_to(config.project_root).as_posix()),
                "keep_assets": bool(keep_assets),
                "clear_godot_cache": bool(clear_godot_cache),
                "removed_paths": removed_paths,
                "recreated_paths": recreated_paths,
                "bootstrap_file": bootstrap_file,
                "next_steps": [
                    "python runner.py orchestrate",
                    "python runner.py smoke-test --project-name sandbox_project --warnings-as-errors",
                ],
            },
            ensure_ascii=True,
            sort_keys=True,
            indent=2,
        )
    )


def _godot_cli_available() -> bool:
    return shutil.which("godot") is not None


def _required_models_for_orchestrate() -> tuple[str, ...]:
    gateway = ModelGateway()
    required = {
        gateway.model_for("director"),
        gateway.model_for("architect"),
        gateway.model_for("programmer"),
        gateway.model_for("qa"),
    }
    return tuple(sorted(required))


def _installed_ollama_models() -> set[str]:
    try:
        output = subprocess.run(
            ["ollama", "list"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return set()

    models: set[str] = set()
    lines = output.stdout.splitlines()
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        model_name = stripped.split()[0]
        if model_name:
            models.add(model_name)
    return models


def _missing_required_models_for_orchestrate() -> list[str]:
    installed = _installed_ollama_models()
    required = _required_models_for_orchestrate()
    missing = [model for model in required if model not in installed]
    return sorted(missing)


def _docs_index_report(version: str = "4.2", strict: bool = False) -> dict[str, Any]:
    config = load_kernel_config()
    normalized_version = version.strip()
    if not normalized_version:
        return {
            "status": "error",
            "message": "Docs version must be non-empty",
            "version": version,
        }

    canonical_root = (config.project_root / "docs" / "godot" / normalized_version).resolve()

    if not canonical_root.exists() or not canonical_root.is_dir():
        return {
            "status": "error",
            "message": "Godot docs root not found",
            "canonical_root": str(canonical_root),
            "version": normalized_version,
        }

    direct_index = canonical_root / "index.html"
    resolved_root = canonical_root
    is_canonical = True

    if not direct_index.exists():
        nested_candidates = []
        for child in canonical_root.iterdir():
            if child.is_dir() and (child / "index.html").exists():
                nested_candidates.append(child)

        if len(nested_candidates) == 1:
            resolved_root = nested_candidates[0]
            is_canonical = False
            if strict:
                return {
                    "status": "error",
                    "message": "Nested docs layout found while strict mode is enabled",
                    "canonical_root": str(canonical_root),
                    "resolved_root": str(resolved_root),
                    "version": normalized_version,
                    "strict": strict,
                }
        elif len(nested_candidates) == 0:
            return {
                "status": "error",
                "message": "Godot docs index.html not found",
                "canonical_root": str(canonical_root),
                "version": normalized_version,
                "strict": strict,
            }
        else:
            return {
                "status": "error",
                "message": "Multiple nested docs roots found",
                "canonical_root": str(canonical_root),
                "candidates": [str(item) for item in nested_candidates],
                "version": normalized_version,
                "strict": strict,
            }

    required_paths = [
        resolved_root / "index.html",
        resolved_root / "classes",
        resolved_root / "tutorials",
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        return {
            "status": "error",
            "message": "Godot docs are incomplete",
            "canonical_root": str(canonical_root),
            "resolved_root": str(resolved_root),
            "missing": missing,
            "version": normalized_version,
            "strict": strict,
        }

    return {
        "status": "ok",
        "version": normalized_version,
        "strict": strict,
        "canonical_root": str(canonical_root),
        "resolved_root": str(resolved_root),
        "is_canonical_layout": is_canonical,
    }


def _build_release_readiness_snapshot(
    run_id: str,
    acceptance_passed: bool,
    invariant_violation_count: int,
    docs_index: dict[str, Any],
    docs_strict: bool,
    artifacts_present: bool,
) -> dict[str, Any]:
    docs_ok = str(docs_index.get("status", "")).strip().lower() == "ok"
    docs_canonical = bool(docs_index.get("is_canonical_layout", False))
    docs_policy_passed = docs_ok and ((not docs_strict) or docs_canonical)
    invariants_passed = invariant_violation_count == 0

    hard_gates = {
        "acceptance_passed": acceptance_passed,
        "invariants_passed": invariants_passed,
        "artifacts_present": artifacts_present,
        "docs_policy_passed": docs_policy_passed,
    }
    blocking_gates = [name for name, passed in hard_gates.items() if not passed]
    release_ready = len(blocking_gates) == 0

    return {
        "run_id": run_id,
        "release_ready": release_ready,
        "hard_gates": hard_gates,
        "blocking_gates": blocking_gates,
        "policy": {
            "docs_strict": docs_strict,
            "docs_version": str(docs_index.get("version", "4.2")),
        },
        "metrics": {
            "invariant_violations": invariant_violation_count,
        },
        "handoff": {
            "run_id": run_id,
            "release_ready": release_ready,
            "blocking_gates": blocking_gates,
            "summary": "ready" if release_ready else "blocked",
        },
    }


def _handle_docs_index(version: str, strict: bool) -> None:
    report = _docs_index_report(version=version, strict=strict)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))


def _build_upgrade_workflow_report(docs_version: str, docs_strict: bool) -> dict[str, Any]:
    docs_report = _docs_index_report(version=docs_version, strict=docs_strict)
    missing_models = _missing_required_models_for_orchestrate()
    required_models = list(_required_models_for_orchestrate())

    actions: list[str] = []
    if docs_report.get("status") != "ok":
        actions.append("Fix docs layout/version before strict release")
    if missing_models:
        actions.append("Install missing Ollama models")

    return {
        "status": "ok",
        "docs": docs_report,
        "models": {
            "required": required_models,
            "missing": missing_models,
            "ready": len(missing_models) == 0,
        },
        "contracts": {
            "task_execution_contract_version": 1,
            "objective_spec_version": 1,
        },
        "actions": actions,
    }


def _handle_upgrade_workflow(docs_version: str, docs_strict: bool) -> None:
    report = _build_upgrade_workflow_report(docs_version=docs_version, docs_strict=docs_strict)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))


def _evaluate_proposal_rollout_policy(proposal: dict[str, Any]) -> dict[str, Any]:
    risk = str(proposal.get("risk", "")).strip().lower()
    confidence = float(proposal.get("confidence", 0.0))

    if risk == "high" or confidence < 0.60:
        action = "reject"
    elif risk == "medium" or confidence < 0.75:
        action = "review"
    else:
        action = "approve"

    rollback_criteria = [
        "acceptance fails after rollout",
        "new invariant violations introduced",
        "godot validation errors increase",
    ]
    return {
        "proposal_id": int(proposal.get("id", 0)),
        "action": action,
        "risk": risk,
        "confidence": confidence,
        "rollback_criteria": rollback_criteria,
    }


def _handle_proposal_policy() -> None:
    config = load_kernel_config()
    with SQLiteConnectionManager(config.db_path) as connection:
        cursor = connection.cursor()
        rows = cursor.execute(
            """
            SELECT id, summary, proposal_type, target_module, risk, confidence, approved
            FROM evolution_proposals
            ORDER BY id ASC
            """
        ).fetchall()

    evaluations = []
    for row in rows:
        proposal = {
            "id": int(row["id"]),
            "summary": str(row["summary"]),
            "proposal_type": str(row["proposal_type"]),
            "target_module": str(row["target_module"]),
            "risk": str(row["risk"]),
            "confidence": float(row["confidence"]),
            "approved": int(row["approved"]),
        }
        evaluated = _evaluate_proposal_rollout_policy(proposal)
        evaluated["summary"] = proposal["summary"]
        evaluated["proposal_type"] = proposal["proposal_type"]
        evaluated["target_module"] = proposal["target_module"]
        evaluations.append(evaluated)

    print(
        json.dumps(
            {
                "status": "ok",
                "count": len(evaluations),
                "evaluations": evaluations,
            },
            ensure_ascii=True,
            sort_keys=True,
            indent=2,
        )
    )


def _build_health_snapshot() -> dict[str, Any]:
    db = KernelDB()
    db.initialize()
    config = load_kernel_config()
    with SQLiteConnectionManager(config.db_path) as connection:
        cursor = connection.cursor()
        task_row = cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress
            FROM tasks
            """
        ).fetchone()
        pending_proposals_row = cursor.execute(
            "SELECT COUNT(*) AS count FROM evolution_proposals WHERE approved = 0"
        ).fetchone()
        invariant_row = cursor.execute(
            "SELECT COUNT(*) AS count FROM invariant_violations"
        ).fetchone()
        release_row = cursor.execute(
            """
            SELECT COUNT(*) AS total, SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) AS passed
            FROM run_release_readiness
            """
        ).fetchone()

    release_total = int(release_row["total"]) if release_row is not None and release_row["total"] is not None else 0
    release_passed = int(release_row["passed"]) if release_row is not None and release_row["passed"] is not None else 0

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "tasks": {
            "total": int(task_row["total"]) if task_row is not None and task_row["total"] is not None else 0,
            "completed": int(task_row["completed"]) if task_row is not None and task_row["completed"] is not None else 0,
            "failed": int(task_row["failed"]) if task_row is not None and task_row["failed"] is not None else 0,
            "in_progress": int(task_row["in_progress"]) if task_row is not None and task_row["in_progress"] is not None else 0,
        },
        "evolution": {
            "pending_proposals": int(pending_proposals_row["count"]) if pending_proposals_row is not None else 0,
        },
        "invariants": {
            "violations_total": int(invariant_row["count"]) if invariant_row is not None else 0,
        },
        "release_readiness": {
            "runs_total": release_total,
            "runs_passed": release_passed,
            "pass_rate": (release_passed / release_total) if release_total > 0 else None,
        },
    }


def _handle_health_snapshot(limit: int) -> None:
    db = KernelDB()
    db.initialize()
    snapshot = _build_health_snapshot()
    db.record_health_snapshot(snapshot)
    history = db.list_health_snapshots(limit=max(1, limit))
    print(
        json.dumps(
            {
                "status": "ok",
                "snapshot": snapshot,
                "history": history,
            },
            ensure_ascii=True,
            sort_keys=True,
            indent=2,
        )
    )


def _build_release_handoff(run_id: str) -> dict[str, Any]:
    report = _build_run_report(run_id)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "release_ready": report.get("summary", {}).get("release_ready"),
        "release_readiness": report.get("release_readiness"),
        "objective_spec": report.get("objective_spec"),
        "acceptance": report.get("acceptance"),
        "summary": report.get("summary"),
    }


def _handle_release_handoff(run_id: str | None, output: str | None) -> None:
    resolved_run_id = _resolve_run_id(run_id)
    if resolved_run_id is None:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": "No run_id available. Provide --run-id or run orchestrate first.",
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
        )
        return

    payload = _build_release_handoff(resolved_run_id)
    default_output = Path("memory") / "handoffs" / f"{resolved_run_id}.json"
    output_path = Path(output) if output else default_output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "run_id": resolved_run_id,
                "output": str(output_path),
                "release_ready": payload.get("release_ready"),
            },
            ensure_ascii=True,
            sort_keys=True,
            indent=2,
        )
    )


def _handle_ledger_add() -> None:
    ledger = DecisionLedger()
    try:
        problem = _read_required_input("problem: ")
        context = _read_required_input("context: ")
        options = _read_required_input("options: ")
        chosen = _read_required_input("chosen: ")
        tradeoffs = _read_required_input("tradeoffs: ")
        risks = _read_required_input("risks: ")
        confidence_raw = _read_required_input("confidence (0.0-1.0): ")
        agent = _read_required_input("agent: ")

        confidence = float(confidence_raw)
        if confidence < 0.0 or confidence > 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

        decision_id = ledger.add_decision(
            problem=problem,
            context=context,
            options=options,
            chosen=chosen,
            tradeoffs=tradeoffs,
            risks=risks,
            confidence=confidence,
            agent=agent,
        )
        print(f"Decision added with id={decision_id}")
    except Exception as exc:
        ledger.record_exception(message=f"runner ledger add exception: {exc}", file_name="runner")
        raise


def _handle_ledger_list() -> None:
    ledger = DecisionLedger()
    try:
        entries = ledger.get_decisions()
        print(_format_ledger_entries(entries))
    except Exception as exc:
        ledger.record_exception(message=f"runner ledger list exception: {exc}", file_name="runner")
        raise


def _handle_ledger_validate() -> None:
    ledger = DecisionLedger()
    try:
        task_id_raw = _read_required_input("task_id: ")
        decision_id_raw = _read_required_input("decision_id: ")
        task_id = int(task_id_raw)
        decision_id = int(decision_id_raw)
        is_valid = ledger.validate_change(task_id=task_id, decision_id=decision_id)
        print(f"Ledger validation: {'passed' if is_valid else 'failed'}")
    except Exception as exc:
        ledger.record_exception(message=f"runner ledger validate exception: {exc}", file_name="runner")
        raise


def _handle_evolution_propose() -> None:
    engine = EvolutionEngine()
    try:
        proposals = engine.generate_proposals()
        print(f"Generated proposals: {len(proposals)}")
    except Exception as exc:
        engine.record_exception(message=f"runner evolution propose exception: {exc}")
        raise


def _handle_evolution_list() -> None:
    engine = EvolutionEngine()
    try:
        proposals = engine.list_proposals()
        print(_format_evolution_proposals(proposals))
    except Exception as exc:
        engine.record_exception(message=f"runner evolution list exception: {exc}")
        raise


def _handle_evolution_approve() -> None:
    engine = EvolutionEngine()
    try:
        proposal_id_raw = _read_required_input("proposal_id: ")
        proposal_id = int(proposal_id_raw)
        approved = engine.approve_proposal(proposal_id)
        print(f"Evolution approval: {'passed' if approved else 'failed'}")
    except Exception as exc:
        engine.record_exception(message=f"runner evolution approve exception: {exc}")
        raise


def _handle_evolution_reject() -> None:
    engine = EvolutionEngine()
    try:
        proposal_id_raw = _read_required_input("proposal_id: ")
        proposal_id = int(proposal_id_raw)
        rejected = engine.reject_proposal(proposal_id)
        print(f"Evolution rejection: {'passed' if rejected else 'failed'}")
    except Exception as exc:
        engine.record_exception(message=f"runner evolution reject exception: {exc}")
        raise


def _resolve_run_id(requested_run_id: str | None) -> str | None:
    if requested_run_id:
        return requested_run_id

    config = load_kernel_config()
    with SQLiteConnectionManager(config.db_path) as connection:
        cursor = connection.cursor()
        attempt_row = cursor.execute(
            """
            SELECT run_id
            FROM task_attempts
            WHERE run_id IS NOT NULL AND run_id != ''
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if attempt_row is not None and str(attempt_row["run_id"]):
            return str(attempt_row["run_id"])

        violation_row = cursor.execute(
            """
            SELECT run_id
            FROM invariant_violations
            WHERE run_id IS NOT NULL AND run_id != ''
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if violation_row is not None and str(violation_row["run_id"]):
            return str(violation_row["run_id"])

    return None


def _build_run_report(run_id: str) -> dict[str, Any]:
    db = KernelDB()
    db.initialize()
    config = load_kernel_config()
    objective_spec_payload = db.get_objective_spec(run_id)
    acceptance_results = db.get_run_acceptance_results(run_id)
    release_readiness = db.get_run_release_readiness(run_id)
    with SQLiteConnectionManager(config.db_path) as connection:
        cursor = connection.cursor()

        attempts = cursor.execute(
            """
            SELECT id, task_id, attempt_number, output_summary, success_flag, confidence, timestamp
            FROM task_attempts
            WHERE run_id = ?
            ORDER BY id ASC
            """,
            (run_id,),
        ).fetchall()

        manifest_rows = cursor.execute(
            """
            SELECT task_id, task, assigned_agent, created_at
            FROM run_manifests
            WHERE run_id = ?
            ORDER BY id ASC
            """,
            (run_id,),
        ).fetchall()

        task_ids = sorted({int(row["task_id"]) for row in attempts} | {int(row["task_id"]) for row in manifest_rows})
        tasks: list[dict[str, Any]] = []
        task_lookup: dict[int, dict[str, Any]] = {}
        if task_ids:
            placeholders = ",".join("?" for _ in task_ids)
            task_rows = cursor.execute(
                f"""
                SELECT id, description, status, assigned_agent, created_at, completed_at
                FROM tasks
                WHERE id IN ({placeholders})
                ORDER BY id ASC
                """,
                tuple(task_ids),
            ).fetchall()
            task_lookup = {
                int(row["id"]): {
                    "id": int(row["id"]),
                    "description": str(row["description"]),
                    "status": str(row["status"]),
                    "assigned_agent": str(row["assigned_agent"]),
                    "created_at": str(row["created_at"]),
                    "completed_at": str(row["completed_at"]) if row["completed_at"] is not None else None,
                }
                for row in task_rows
            }

        manifest_lookup = {
            int(row["task_id"]): {
                "task": str(row["task"]),
                "assigned_agent": str(row["assigned_agent"]),
                "created_at": str(row["created_at"]),
            }
            for row in manifest_rows
        }

        tasks = []
        for task_id in task_ids:
            row = task_lookup.get(task_id)
            manifest = manifest_lookup.get(task_id)
            if row is None:
                tasks.append(
                    {
                        "id": task_id,
                        "description": manifest["task"] if manifest is not None else "",
                        "status": "unknown",
                        "assigned_agent": manifest["assigned_agent"] if manifest is not None else "unknown",
                        "created_at": manifest["created_at"] if manifest is not None else "",
                        "completed_at": None,
                    }
                )
                continue

            if manifest is not None and not row["description"]:
                row["description"] = manifest["task"]
            tasks.append(row)

        violations = cursor.execute(
            """
            SELECT id, invariant_id, file, description, severity, timestamp
            FROM invariant_violations
            WHERE run_id = ?
            ORDER BY id ASC
            """,
            (run_id,),
        ).fetchall()

    attempt_payload = [
        {
            "id": int(row["id"]),
            "task_id": int(row["task_id"]),
            "attempt_number": int(row["attempt_number"]),
            "output_summary": str(row["output_summary"]),
            "success_flag": int(row["success_flag"]),
            "confidence": float(row["confidence"]),
            "timestamp": str(row["timestamp"]),
        }
        for row in attempts
    ]

    violation_payload = [
        {
            "id": int(row["id"]),
            "invariant_id": int(row["invariant_id"]),
            "file": str(row["file"]),
            "description": str(row["description"]),
            "severity": int(row["severity"]),
            "timestamp": str(row["timestamp"]),
        }
        for row in violations
    ]

    status_counts = {
        "queued": 0,
        "assigned": 0,
        "in_progress": 0,
        "completed": 0,
        "failed": 0,
        "other": 0,
    }
    for task in tasks:
        status = str(task.get("status", "")).strip()
        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts["other"] += 1

    scene_assembly = _load_scene_assembly_artifacts(project_name="sandbox_project")

    return {
        "status": "ok",
        "run_id": run_id,
        "objective_spec": objective_spec_payload,
        "scene_assembly": scene_assembly,
        "release_readiness": release_readiness,
        "acceptance": {
            "passed": all(item["passed"] for item in acceptance_results) if acceptance_results else None,
            "checks": acceptance_results,
        },
        "summary": {
            "tasks": len(tasks),
            "attempts": len(attempt_payload),
            "successful_attempts": sum(1 for row in attempt_payload if row["success_flag"] == 1),
            "violations": len(violation_payload),
            "acceptance_checks": len(acceptance_results),
            "acceptance_failed": sum(1 for item in acceptance_results if not item["passed"]),
            "task_status_counts": status_counts,
            "release_ready": release_readiness["passed"] if release_readiness is not None else None,
        },
        "tasks": tasks,
        "attempts": attempt_payload,
        "violations": violation_payload,
    }


def _handle_run_report(run_id: str | None) -> None:
    resolved_run_id = _resolve_run_id(run_id)
    if resolved_run_id is None:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": "No run_id available. Provide --run-id or run orchestrate first.",
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
        )
        return

    report = _build_run_report(resolved_run_id)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))


def _interactive_director() -> None:
    agent = DirectorAgent()
    print("Director Interface: create | assign | monitor | prioritize | exit")
    while True:
        command = input("director> ").strip().lower()
        if command == "exit":
            break
        if command == "create":
            description = _read_required_input("description: ")
            assigned_agent = _read_required_input("assigned_agent: ")
            task_id = agent.create_task(description=description, assigned_agent=assigned_agent)
            print(f"created task_id={task_id}")
        elif command == "assign":
            task_id = int(_read_required_input("task_id: "))
            agent_name = _read_required_input("agent_name: ")
            result = agent.assign_task(task_id=task_id, agent_name=agent_name)
            print(f"assign result={result}")
        elif command == "monitor":
            print(json.dumps(agent.monitor_progress(), ensure_ascii=True, sort_keys=True, indent=2))
        elif command == "prioritize":
            print(json.dumps(agent.prioritize_tasks(), ensure_ascii=True, sort_keys=True, indent=2))
        else:
            print("unknown command")


def _interactive_architect() -> None:
    agent = ArchitectAgent()
    print("Architect Interface: propose | review | ledger | exit")
    while True:
        command = input("architect> ").strip().lower()
        if command == "exit":
            break
        if command == "propose":
            task_id = int(_read_required_input("task_id: "))
            print(json.dumps(agent.propose_architecture(task_id=task_id), ensure_ascii=True, sort_keys=True, indent=2))
        elif command == "review":
            config = load_kernel_config()
            report = agent.review_structure(config.project_root)
            print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
        elif command == "ledger":
            problem = _read_required_input("problem: ")
            context = _read_required_input("context: ")
            options = _read_required_input("options: ")
            chosen = _read_required_input("chosen: ")
            tradeoffs = _read_required_input("tradeoffs: ")
            risks = _read_required_input("risks: ")
            confidence = float(_read_required_input("confidence (0.0-1.0): "))
            decision_id = agent.submit_ledger_entry(
                problem=problem,
                context=context,
                options=options,
                chosen=chosen,
                tradeoffs=tradeoffs,
                risks=risks,
                confidence=confidence,
                agent="architect_agent",
            )
            print(f"decision_id={decision_id}")
        else:
            print("unknown command")


def _interactive_programmer() -> None:
    agent = ProgrammerAgent()
    print("Programmer Interface: implement | evaluate | attempt | exit")
    while True:
        command = input("programmer> ").strip().lower()
        if command == "exit":
            break
        if command == "implement":
            task_id = int(_read_required_input("task_id: "))
            decision_id = int(_read_required_input("decision_id: "))
            print(json.dumps(agent.implement_task(task_id=task_id, decision_id=decision_id), ensure_ascii=True, sort_keys=True, indent=2))
        elif command == "evaluate":
            task_id = int(_read_required_input("task_id: "))
            print(f"evaluation={agent.run_evaluation(task_id=task_id)}")
        elif command == "attempt":
            output_summary = _read_required_input("output_summary: ")
            success_flag = int(_read_required_input("success_flag (0|1): "))
            confidence = float(_read_required_input("confidence: "))
            print(f"attempt_recorded={agent.record_attempt(output_summary, success_flag, confidence)}")
        else:
            print("unknown command")


def _interactive_qa() -> None:
    agent = QAgent()
    print("QA Interface: validate | violations | feed | exit")
    while True:
        command = input("qa> ").strip().lower()
        if command == "exit":
            break
        if command == "validate":
            task_id = int(_read_required_input("task_id: "))
            print(f"validation={agent.run_validation(task_id=task_id)}")
        elif command == "violations":
            print(json.dumps(agent.report_violations(), ensure_ascii=True, sort_keys=True, indent=2))
        elif command == "feed":
            task_id = int(_read_required_input("task_id: "))
            print(json.dumps(agent.feed_results_to_director(task_id=task_id), ensure_ascii=True, sort_keys=True, indent=2))
        else:
            print("unknown command")


def _handle_agent_interface(agent_name: str) -> None:
    if agent_name == "director":
        _interactive_director()
    elif agent_name == "architect":
        _interactive_architect()
    elif agent_name == "programmer":
        _interactive_programmer()
    elif agent_name == "qa":
        _interactive_qa()


def _run_director() -> None:
    agent = DirectorAgent()
    task_context = _read_required_input("task_context: ")
    plan = agent.generate_task_plan(task_context)
    print(json.dumps(plan, ensure_ascii=True, sort_keys=True, indent=2))

    assignments = plan.get("plan", {}).get("assignments", [])
    created: list[dict[str, Any]] = []
    for item in assignments:
        task_description = str(item.get("task", ""))
        assigned_agent = str(item.get("assigned_agent", ""))
        if not task_description or not assigned_agent:
            continue
        task_id = agent.create_task(description=task_description, assigned_agent=assigned_agent)
        created.append({"task_id": task_id, "assigned_agent": assigned_agent})

    print(json.dumps({"created_tasks": created}, ensure_ascii=True, sort_keys=True, indent=2))


def _run_architect() -> None:
    agent = ArchitectAgent()
    task_id = int(_read_required_input("task_id: "))
    proposal = agent.propose_architecture(task_id)
    print(json.dumps(proposal, ensure_ascii=True, sort_keys=True, indent=2))

    ledger_entry = proposal.get("ledger_entry", {})
    decision_id = agent.submit_ledger_entry(
        problem=str(ledger_entry.get("problem", "")),
        context=str(ledger_entry.get("context", "")),
        options=str(ledger_entry.get("options", "")),
        chosen=str(ledger_entry.get("chosen", "")),
        tradeoffs=str(ledger_entry.get("tradeoffs", "")),
        risks=str(ledger_entry.get("risks", "")),
        confidence=float(ledger_entry.get("confidence", 0.0)),
        agent="architect_agent",
    )
    print(json.dumps({"decision_id": decision_id}, ensure_ascii=True, sort_keys=True, indent=2))


def _run_programmer() -> None:
    agent = ProgrammerAgent()
    task_id = int(_read_required_input("task_id: "))
    decision_id = int(_read_required_input("decision_id: "))
    result = agent.implement_task(task_id=task_id, decision_id=decision_id)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))


def _run_qa() -> None:
    agent = QAgent()
    task_id = int(_read_required_input("task_id: "))
    result = agent.analyze_task(task_id=task_id)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))


def _run_orchestrate(
    docs_strict: bool = False,
    smoke_warnings_as_errors: bool = True,
    skip_smoke_test: bool = False,
    template_advisor_precheck: bool = True,
    template_project_name: str = "sandbox_project",
    progress_smoke: bool = False,
) -> None:
    objective = _read_required_input("objective: ")
    template_guidance = _build_orchestrate_template_guidance(
        objective=objective,
        project_name=template_project_name,
        precheck_enabled=bool(template_advisor_precheck),
    )
    template_bootstrap = _apply_template_bootstrap(
        project_name=template_project_name,
        guidance=template_guidance,
    )
    planning_objective = objective
    if str(template_bootstrap.get("status", "")).strip().lower() == "applied":
        bootstrap_path = str(template_bootstrap.get("bootstrap_path", "")).strip()
        if bootstrap_path:
            planning_objective = (
                f"{objective}\n"
                f"Template bootstrap available at {bootstrap_path}. "
                "Use it as reference for scene/script structure while keeping outputs in standard sandbox artifacts."
            )
    run_id = str(uuid.uuid4())

    try:
        ledger_bootstrap = _ensure_decision_ledger_seed()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": f"Ledger bootstrap failed: {exc}",
                    "run_id": run_id,
                    "template_guidance": template_guidance,
                    "template_bootstrap": template_bootstrap,
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
        )
        return

    db = KernelDB()
    db.initialize()
    try:
        objective_spec = compile_objective_spec(objective)
        objective_spec_payload = objective_spec.to_dict()
        db.record_objective_spec(
            run_id=run_id,
            objective=objective_spec.objective,
            objective_type=objective_spec.objective_type,
            spec_payload=objective_spec_payload,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": f"Objective spec gate failed: {exc}",
                    "run_id": run_id,
                    "ledger_bootstrap": ledger_bootstrap,
                    "template_guidance": template_guidance,
                    "template_bootstrap": template_bootstrap,
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
        )
        return

    artifact_map = _artifact_map_from_spec(objective_spec_payload)

    missing_models = _missing_required_models_for_orchestrate()
    docs_index_report = _docs_index_report(version="4.2", strict=docs_strict)
    missing_dependency: list[str] = []
    if not _godot_cli_available():
        missing_dependency.append("godot")

    if missing_dependency or missing_models:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": "Missing required runtime dependencies",
                    "missing_dependencies": missing_dependency,
                    "missing_models": missing_models,
                    "required_models": list(_required_models_for_orchestrate()),
                    "docs_index": docs_index_report,
                    "ledger_bootstrap": ledger_bootstrap,
                    "template_guidance": template_guidance,
                    "template_bootstrap": template_bootstrap,
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
        )
        return

    director = DirectorAgent()
    architect = ArchitectAgent()
    programmer = ProgrammerAgent()
    qa = QAgent()
    retry_trace: dict[str, list[dict[str, Any]]] = {}
    progress_smoke_checks: list[dict[str, Any]] = []
    scene_assembly_result: dict[str, Any] = {
        "status": "skipped",
        "reason": "not_executed",
    }
    director_fallback_used = False
    director_fallback_reason: str | None = None
    architect_fallback_used = False
    architect_fallback_reason: str | None = None

    plan_execution = _invoke_with_retry(
        "director_plan",
        lambda: director.generate_task_plan(planning_objective),
        success_predicate=lambda result: isinstance(result.get("plan"), dict),
    )
    retry_trace["director_plan"] = plan_execution["attempts"]
    plan = plan_execution["result"]
    if plan.get("status") == "error":
        if _is_retryable_stage_error(plan):
            director_fallback_used = True
            director_fallback_reason = "director_plan retry exhaustion"
            plan = _fallback_director_plan(planning_objective)
            retry_trace["director_plan"].append(
                {
                    "stage": "director_plan",
                    "attempt_number": len(retry_trace["director_plan"]) + 1,
                    "status": "fallback",
                    "message": director_fallback_reason,
                    "retryable": False,
                }
            )
        else:
            print(
                json.dumps(
                    {
                        **plan,
                        "ledger_bootstrap": ledger_bootstrap,
                        "template_guidance": template_guidance,
                        "template_bootstrap": template_bootstrap,
                        "recovery": _recovery_payload_with_fallback(
                            director_fallback_used=director_fallback_used,
                            director_fallback_reason=director_fallback_reason,
                            architect_fallback_used=architect_fallback_used,
                            architect_fallback_reason=architect_fallback_reason,
                        ),
                        "retry_trace": retry_trace,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                    indent=2,
                )
            )
            return

    plan = _normalize_director_plan_assignments(
        plan_payload=plan,
        objective_spec_payload=objective_spec_payload,
        objective=objective,
    )

    assignments = plan.get("plan", {}).get("assignments", [])
    created_tasks: list[dict[str, Any]] = []
    contracts: list[dict[str, Any]] = []

    for item in assignments:
        task_description = str(item.get("task", "")).strip()
        assigned_agent = str(item.get("assigned_agent", "")).strip()
        if not task_description or not assigned_agent:
            continue
        if str(template_bootstrap.get("status", "")).strip().lower() == "applied":
            bootstrap_hint = str(template_bootstrap.get("bootstrap_path", "")).strip()
            if bootstrap_hint:
                task_description = (
                    f"{task_description} "
                    f"(template_reference={bootstrap_hint}; use as pattern only, keep artifact outputs in sandbox targets)"
                )
        task_id = director.create_task(description=task_description, assigned_agent=assigned_agent)
        created_tasks.append(
            {
                "task_id": task_id,
                "task": task_description,
                "assigned_agent": assigned_agent,
            }
        )
        contract = TaskExecutionContract(
            task_id=task_id,
            assigned_agent=assigned_agent,
            ledger_required=bool(item.get("ledger_required", False)),
            required_artifacts=artifact_map.get(assigned_agent, _required_artifacts_for_agent(assigned_agent)),
            decision_id=None,
        )
        if not (contract.assigned_agent == "programmer" and contract.ledger_required and contract.decision_id is None):
            contract.validate()
        contracts.append(contract.to_dict())

    for created in created_tasks:
        db.record_run_manifest_task(
            run_id=run_id,
            task_id=int(created["task_id"]),
            task=str(created["task"]),
            assigned_agent=str(created["assigned_agent"]),
        )

    director_contract = next((c for c in contracts if c["assigned_agent"] == "director"), None)
    architect_contract = next((c for c in contracts if c["assigned_agent"] == "architect"), None)
    programmer_contract = next((c for c in contracts if c["assigned_agent"] == "programmer"), None)

    if architect_contract is None or programmer_contract is None:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": "Missing architect or programmer assignment in director plan",
                    "created_tasks": created_tasks,
                    "ledger_bootstrap": ledger_bootstrap,
                    "template_guidance": template_guidance,
                    "template_bootstrap": template_bootstrap,
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
        )
        return

    if director_contract is not None:
        db.update_task_status(task_id=int(director_contract["task_id"]), status="completed")
    db.update_task_status(task_id=int(architect_contract["task_id"]), status="in_progress")

    bootstrap_file = None
    if director_contract is not None:
        config = load_kernel_config()
        bootstrap_file = _bootstrap_project_godot(config.project_root)

    architecture_execution = _invoke_with_retry(
        "architect_proposal",
        lambda: architect.propose_architecture(int(architect_contract["task_id"])),
        success_predicate=lambda result: isinstance(result.get("ledger_entry"), dict),
    )
    retry_trace["architect_proposal"] = architecture_execution["attempts"]
    architecture = architecture_execution["result"]
    if architecture.get("status") == "error":
        if _is_retryable_stage_error(architecture):
            architect_fallback_used = True
            architect_fallback_reason = "architect_proposal retry exhaustion"
            architecture = _fallback_architect_proposal(int(architect_contract["task_id"]), objective)
            retry_trace["architect_proposal"].append(
                {
                    "stage": "architect_proposal",
                    "attempt_number": len(retry_trace["architect_proposal"]) + 1,
                    "status": "fallback",
                    "message": architect_fallback_reason,
                    "retryable": False,
                }
            )
        else:
            db.update_task_status(task_id=int(architect_contract["task_id"]), status="failed")
            print(
                json.dumps(
                    {
                        **architecture,
                        "ledger_bootstrap": ledger_bootstrap,
                        "template_guidance": template_guidance,
                        "template_bootstrap": template_bootstrap,
                        "recovery": _recovery_payload_with_fallback(
                            director_fallback_used=director_fallback_used,
                            director_fallback_reason=director_fallback_reason,
                            architect_fallback_used=architect_fallback_used,
                            architect_fallback_reason=architect_fallback_reason,
                        ),
                        "retry_trace": retry_trace,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                    indent=2,
                )
            )
            return

    ledger_entry = architecture.get("ledger_entry", {})
    decision_id = architect.submit_ledger_entry(
        problem=str(ledger_entry.get("problem", "")),
        context=str(ledger_entry.get("context", "")),
        options=str(ledger_entry.get("options", "")),
        chosen=str(ledger_entry.get("chosen", "")),
        tradeoffs=str(ledger_entry.get("tradeoffs", "")),
        risks=str(ledger_entry.get("risks", "")),
        confidence=float(ledger_entry.get("confidence", 0.0)),
        agent="architect_agent",
    )

    architect_contract["decision_id"] = decision_id
    architect_contract["objective_spec"] = objective_spec_payload
    TaskExecutionContract.from_dict(architect_contract)
    architecture_implementation = architect.implement_scene_contract(architect_contract)
    if architecture_implementation.get("status") == "error":
        db.update_task_status(task_id=int(architect_contract["task_id"]), status="failed")
        print(
            json.dumps(
                {
                    **architecture_implementation,
                    "ledger_bootstrap": ledger_bootstrap,
                    "template_guidance": template_guidance,
                    "template_bootstrap": template_bootstrap,
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
        )
        return
    db.update_task_status(task_id=int(architect_contract["task_id"]), status="completed")

    programmer_contract["decision_id"] = decision_id
    programmer_contract["run_id"] = run_id
    db.update_task_status(task_id=int(programmer_contract["task_id"]), status="in_progress")
    TaskExecutionContract.from_dict(programmer_contract)
    implementation_execution = _invoke_with_retry(
        "programmer_implementation",
        lambda: programmer.implement_task_contract(programmer_contract),
        success_predicate=lambda result: str(result.get("status", "")).strip().lower() == "ok",
    )
    retry_trace["programmer_implementation"] = implementation_execution["attempts"]
    implementation = implementation_execution["result"]
    if implementation.get("status") == "error":
        db.update_task_status(task_id=int(programmer_contract["task_id"]), status="failed")
        print(
            json.dumps(
                {
                    **implementation,
                    "ledger_bootstrap": ledger_bootstrap,
                    "template_guidance": template_guidance,
                    "template_bootstrap": template_bootstrap,
                    "recovery": _recovery_payload_with_fallback(
                        director_fallback_used=director_fallback_used,
                        director_fallback_reason=director_fallback_reason,
                        architect_fallback_used=architect_fallback_used,
                        architect_fallback_reason=architect_fallback_reason,
                    ),
                    "retry_trace": retry_trace,
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
        )
        return
    db.update_task_status(task_id=int(programmer_contract["task_id"]), status="completed")

    scene_spec_overrides = _infer_scene_spec_overrides_from_architect(architecture, objective)
    config = load_kernel_config()
    studio_dir = config.project_root / "projects" / "sandbox_project" / ".studio"
    studio_dir.mkdir(parents=True, exist_ok=True)
    asset_registry_payload = _build_asset_registry_payload(
        project_name="sandbox_project",
        archetype_id="topdown_adventure_v1",
    )
    missing_required_roles = _required_role_binding_violations(asset_registry_payload)
    if missing_required_roles:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": "Required asset role bindings missing before scene assembly",
                    "missing_required_role_bindings": missing_required_roles,
                    "asset_registry_summary": {
                        "total_assets": len(asset_registry_payload.get("assets", [])),
                        "warnings": asset_registry_payload.get("warnings", []),
                        "role_bindings": sorted(list((asset_registry_payload.get("role_bindings") or {}).keys())),
                    },
                    "scene_spec_overrides": scene_spec_overrides,
                    "created_tasks": created_tasks,
                    "contracts": contracts,
                    "run_id": run_id,
                    "bootstrap_file": bootstrap_file,
                    "decision_id": decision_id,
                    "architecture_implementation": architecture_implementation,
                    "implementation": implementation,
                    "ledger_bootstrap": ledger_bootstrap,
                    "template_guidance": template_guidance,
                    "template_bootstrap": template_bootstrap,
                    "recovery": _recovery_payload_with_fallback(
                        director_fallback_used=director_fallback_used,
                        director_fallback_reason=director_fallback_reason,
                        architect_fallback_used=architect_fallback_used,
                        architect_fallback_reason=architect_fallback_reason,
                    ),
                    "retry_trace": retry_trace,
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
        )
        return

    scene_spec_payload = _build_scene_spec_payload(
        project_name="sandbox_project",
        asset_registry_payload=asset_registry_payload,
        archetype_id="topdown_adventure_v1",
        overrides=scene_spec_overrides,
    )
    asset_registry_path = studio_dir / "asset_registry.json"
    scene_spec_path = studio_dir / "scene_spec.json"
    asset_registry_path.write_text(
        json.dumps(asset_registry_payload, ensure_ascii=True, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    scene_spec_path.write_text(
        json.dumps(scene_spec_payload, ensure_ascii=True, sort_keys=True, indent=2),
        encoding="utf-8",
    )

    scene_assembly_result = {
        "status": "pending",
        "project_name": "sandbox_project",
        "archetype_id": "topdown_adventure_v1",
        "scene_spec_overrides": scene_spec_overrides,
        "payload_paths": {
            "asset_registry": str(asset_registry_path),
            "scene_spec": str(scene_spec_path),
        },
    }
    assembler = _run_scene_assembler(
        project_name="sandbox_project",
        scene_spec_relative_path=".studio/scene_spec.json",
        asset_registry_relative_path=".studio/asset_registry.json",
    )
    scene_assembly_result["assembler"] = assembler
    scene_assembly_result["status"] = assembler.get("status", "error")
    if str(scene_assembly_result.get("status", "")).strip().lower() != "ok":
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": "Scene assembly stage failed",
                    "scene_assembly": scene_assembly_result,
                    "created_tasks": created_tasks,
                    "contracts": contracts,
                    "run_id": run_id,
                    "bootstrap_file": bootstrap_file,
                    "decision_id": decision_id,
                    "architecture_implementation": architecture_implementation,
                    "implementation": implementation,
                    "ledger_bootstrap": ledger_bootstrap,
                    "template_guidance": template_guidance,
                    "template_bootstrap": template_bootstrap,
                    "recovery": _recovery_payload_with_fallback(
                        director_fallback_used=director_fallback_used,
                        director_fallback_reason=director_fallback_reason,
                        architect_fallback_used=architect_fallback_used,
                        architect_fallback_reason=architect_fallback_reason,
                    ),
                    "retry_trace": retry_trace,
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
        )
        return

    if progress_smoke:
        smoke_snapshot = _build_progress_smoke_snapshot(stage="post_scene_assembly", project_name="sandbox_project")
        progress_smoke_checks.append(smoke_snapshot)
        if not bool(smoke_snapshot.get("passed", False)):
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": "Progress smoke check failed after scene assembly",
                        "progress_smoke": progress_smoke_checks,
                        "scene_assembly": scene_assembly_result,
                        "run_id": run_id,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                    indent=2,
                )
            )
            return

    qa_execution = _invoke_with_retry(
        "qa_analysis",
        lambda: qa.analyze_task(int(programmer_contract["task_id"]), run_id=run_id),
        success_predicate=lambda result: (
            isinstance(result.get("assessment"), dict)
            and str(result.get("assessment", {}).get("assessment", "")).strip().lower() != "error"
        ),
    )
    retry_trace["qa_analysis"] = qa_execution["attempts"]
    qa_result = qa_execution["result"]

    if progress_smoke:
        smoke_snapshot = _build_progress_smoke_snapshot(stage="post_qa", project_name="sandbox_project")
        progress_smoke_checks.append(smoke_snapshot)
        if not bool(smoke_snapshot.get("passed", False)):
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": "Progress smoke check failed after QA",
                        "progress_smoke": progress_smoke_checks,
                        "scene_assembly": scene_assembly_result,
                        "run_id": run_id,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                    indent=2,
                )
            )
            return

    config = load_kernel_config()
    missing_pipeline_artifacts = [
        item
        for item in _required_pipeline_artifacts()
        if not (config.project_root / item).exists()
    ]

    if missing_pipeline_artifacts:
        with SQLiteConnectionManager(db.db_path) as connection:
            cursor = connection.cursor()
            violation_row = cursor.execute(
                "SELECT COUNT(*) AS count FROM invariant_violations WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        invariant_violation_count = int(violation_row["count"]) if violation_row is not None else 0
        release_readiness_snapshot = _build_release_readiness_snapshot(
            run_id=run_id,
            acceptance_passed=False,
            invariant_violation_count=invariant_violation_count,
            docs_index=docs_index_report,
            docs_strict=docs_strict,
            artifacts_present=False,
        )
        db.record_run_release_readiness(
            run_id=run_id,
            passed=bool(release_readiness_snapshot["release_ready"]),
            snapshot_payload=release_readiness_snapshot,
        )
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": "Required orchestration artifacts are missing",
                    "missing_artifacts": missing_pipeline_artifacts,
                    "created_tasks": created_tasks,
                    "contracts": contracts,
                    "run_id": run_id,
                    "bootstrap_file": bootstrap_file,
                    "decision_id": decision_id,
                    "architecture_implementation": architecture_implementation,
                    "implementation": implementation,
                    "qa": qa_result,
                    "docs_index": docs_index_report,
                    "ledger_bootstrap": ledger_bootstrap,
                    "template_guidance": template_guidance,
                    "template_bootstrap": template_bootstrap,
                    "recovery": _recovery_payload_with_fallback(
                        director_fallback_used=director_fallback_used,
                        director_fallback_reason=director_fallback_reason,
                        architect_fallback_used=architect_fallback_used,
                        architect_fallback_reason=architect_fallback_reason,
                    ),
                    "release_readiness": release_readiness_snapshot,
                    "retry_trace": retry_trace,
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
        )
        return

    godot_error_count: int | None = None
    qa_summary = qa_result.get("summary") if isinstance(qa_result, dict) else None
    if isinstance(qa_summary, dict):
        godot_summary = qa_summary.get("godot")
        if isinstance(godot_summary, dict):
            raw_errors = godot_summary.get("errors")
            if isinstance(raw_errors, int):
                godot_error_count = raw_errors

    acceptance_result = evaluate_acceptance_spec(
        spec_payload=objective_spec_payload,
        project_root=config.project_root,
        godot_error_count=godot_error_count,
    )
    for check in acceptance_result["checks"]:
        db.record_run_acceptance_result(
            run_id=run_id,
            check_name=str(check["check"]),
            passed=bool(check["passed"]),
            detail=str(check["detail"]),
        )

    with SQLiteConnectionManager(db.db_path) as connection:
        cursor = connection.cursor()
        violation_row = cursor.execute(
            "SELECT COUNT(*) AS count FROM invariant_violations WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    invariant_violation_count = int(violation_row["count"]) if violation_row is not None else 0
    smoke_test_result = {
        "status": "skipped",
        "project_name": "sandbox_project",
        "passed": True,
        "warnings_as_errors": bool(smoke_warnings_as_errors),
        "summary": {
            "validation_errors": 0,
            "validation_warnings": 0,
            "boot_errors": 0,
            "boot_warnings": 0,
            "total_errors": 0,
            "total_warnings": 0,
            "boot_returncode": 0,
        },
        "recommendations": ["Smoke test skipped by operator flag."],
    }
    if not skip_smoke_test:
        smoke_test_result = _build_smoke_test_payload(
            project_name="sandbox_project",
            warnings_as_errors=bool(smoke_warnings_as_errors),
        )

    smoke_passed = bool(smoke_test_result.get("passed", False))
    effective_acceptance_passed = bool(acceptance_result["passed"]) and smoke_passed

    release_readiness_snapshot = _build_release_readiness_snapshot(
        run_id=run_id,
        acceptance_passed=effective_acceptance_passed,
        invariant_violation_count=invariant_violation_count,
        docs_index=docs_index_report,
        docs_strict=docs_strict,
        artifacts_present=True,
    )
    release_readiness_snapshot["quality_gates"] = {
        "smoke_test_passed": smoke_passed,
        "smoke_test_warnings_as_errors": bool(smoke_warnings_as_errors),
        "smoke_test_skipped": bool(skip_smoke_test),
        "scene_assembly_passed": str(scene_assembly_result.get("status", "")).strip().lower() == "ok",
    }
    if not bool(release_readiness_snapshot["quality_gates"]["scene_assembly_passed"]):
        if "scene_assembly_passed" not in release_readiness_snapshot["blocking_gates"]:
            release_readiness_snapshot["blocking_gates"].append("scene_assembly_passed")
        release_readiness_snapshot["release_ready"] = False
        release_readiness_snapshot["handoff"] = {
            "run_id": run_id,
            "release_ready": False,
            "blocking_gates": release_readiness_snapshot["blocking_gates"],
            "summary": "blocked",
        }
    if not smoke_passed and "smoke_test_passed" not in release_readiness_snapshot["blocking_gates"]:
        release_readiness_snapshot["blocking_gates"].append("smoke_test_passed")
        release_readiness_snapshot["release_ready"] = False
        release_readiness_snapshot["handoff"] = {
            "run_id": run_id,
            "release_ready": False,
            "blocking_gates": release_readiness_snapshot["blocking_gates"],
            "summary": "blocked",
        }
    db.record_run_release_readiness(
        run_id=run_id,
        passed=bool(release_readiness_snapshot["release_ready"]),
        snapshot_payload=release_readiness_snapshot,
    )

    if not effective_acceptance_passed:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": "Acceptance/smoke quality gate failed",
                    "acceptance": acceptance_result,
                    "smoke_test": smoke_test_result,
                    "created_tasks": created_tasks,
                    "contracts": contracts,
                    "run_id": run_id,
                    "bootstrap_file": bootstrap_file,
                    "decision_id": decision_id,
                    "architecture_implementation": architecture_implementation,
                    "implementation": implementation,
                    "scene_assembly": scene_assembly_result,
                    "progress_smoke": progress_smoke_checks,
                    "qa": qa_result,
                    "ledger_bootstrap": ledger_bootstrap,
                    "template_guidance": template_guidance,
                    "template_bootstrap": template_bootstrap,
                    "recovery": _recovery_payload_with_fallback(
                        director_fallback_used=director_fallback_used,
                        director_fallback_reason=director_fallback_reason,
                        architect_fallback_used=architect_fallback_used,
                        architect_fallback_reason=architect_fallback_reason,
                    ),
                    "release_readiness": release_readiness_snapshot,
                    "retry_trace": retry_trace,
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
        )
        return

    print(
        json.dumps(
            {
                "status": "ok",
                "plan": plan,
                "created_tasks": created_tasks,
                "contracts": contracts,
                "run_id": run_id,
                "ledger_bootstrap": ledger_bootstrap,
                "bootstrap_file": bootstrap_file,
                "decision_id": decision_id,
                "architecture_implementation": architecture_implementation,
                "implementation": implementation,
                "scene_assembly": scene_assembly_result,
                "progress_smoke": progress_smoke_checks,
                "qa": qa_result,
                "acceptance": acceptance_result,
                "smoke_test": smoke_test_result,
                "template_guidance": template_guidance,
                "template_bootstrap": template_bootstrap,
                "docs_index": docs_index_report,
                "recovery": _recovery_payload_with_fallback(
                    director_fallback_used=director_fallback_used,
                    director_fallback_reason=director_fallback_reason,
                    architect_fallback_used=architect_fallback_used,
                    architect_fallback_reason=architect_fallback_reason,
                ),
                "release_readiness": release_readiness_snapshot,
                "retry_trace": retry_trace,
            },
            ensure_ascii=True,
            sort_keys=True,
            indent=2,
        )
    )


def _handle_agent_run(agent_name: str) -> None:
    try:
        if agent_name == "director":
            _run_director()
        elif agent_name == "architect":
            _run_architect()
        elif agent_name == "programmer":
            _run_programmer()
        elif agent_name == "qa":
            _run_qa()
    except Exception as exc:
        print(json.dumps({"status": "error", "agent": agent_name, "message": str(exc)}, ensure_ascii=True, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Studio Lab kernel runner")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Initialize kernel database")
    subparsers.add_parser("scan", help="Run structural scan")
    subparsers.add_parser("validate", help="Run Godot validation")
    reset_parser = subparsers.add_parser("reset-sandbox", help="Clear sandbox scenes/scripts for a clean rerun")
    reset_parser.add_argument("--drop-assets", dest="drop_assets", action="store_true", help="Also clear assets folder (default keeps assets)")
    reset_parser.add_argument("--clear-godot-cache", dest="clear_godot_cache", action="store_true", help="Remove .godot cache for full reimport")
    docs_index_parser = subparsers.add_parser("docs-index", help="Validate Godot docs index location")
    docs_index_parser.add_argument("--version", dest="docs_version", required=False, default="4.2")
    docs_index_parser.add_argument("--strict", dest="docs_strict", action="store_true")
    upgrade_parser = subparsers.add_parser("upgrade-workflow", help="Show operational upgrade readiness report")
    upgrade_parser.add_argument("--docs-version", dest="docs_version", required=False, default="4.2")
    upgrade_parser.add_argument("--docs-strict", dest="docs_strict", action="store_true")
    health_parser = subparsers.add_parser("health-snapshot", help="Record and show studio health snapshot")
    health_parser.add_argument("--limit", dest="limit", type=int, required=False, default=5)
    subparsers.add_parser("proposal-policy", help="Evaluate rollout policy for evolution proposals")
    handoff_parser = subparsers.add_parser("release-handoff", help="Generate release handoff package for a run")
    handoff_parser.add_argument("--run-id", dest="run_id", required=False)
    handoff_parser.add_argument("--output", dest="output", required=False)
    orchestrate_parser = subparsers.add_parser("orchestrate", help="Run ECS-1 orchestration flow")
    orchestrate_parser.add_argument("--docs-strict", dest="docs_strict", action="store_true")
    orchestrate_parser.add_argument("--skip-smoke-test", dest="skip_smoke_test", action="store_true")
    orchestrate_parser.add_argument(
        "--smoke-ignore-warnings",
        dest="smoke_ignore_warnings",
        action="store_true",
        help="Allow orchestrate smoke-test warnings without failing release readiness",
    )
    orchestrate_parser.add_argument(
        "--no-template-advisor-precheck",
        dest="no_template_advisor_precheck",
        action="store_true",
        help="Disable template advisor precheck in orchestrate output",
    )
    orchestrate_parser.add_argument(
        "--template-project-name",
        dest="template_project_name",
        required=False,
        default="sandbox_project",
        help="Project template library used by template advisor precheck",
    )
    orchestrate_parser.add_argument(
        "--progress-smoke",
        dest="progress_smoke",
        action="store_true",
        help="Run lightweight smoke checks during build stages (post scene assembly and post QA)",
    )
    run_report_parser = subparsers.add_parser("run-report", help="Show run correlation report")
    run_report_parser.add_argument("--run-id", dest="run_id", required=False)
    subparsers.add_parser("creative-brief", help="Generate stronger objective candidates from a structured creative brief")
    subparsers.add_parser("asset-brief", help="Scan project assets, suggest role assignments, and generate objective candidates")
    scene_spec_parser = subparsers.add_parser("scene-spec", help="Generate validated Asset Registry and Scene Spec payloads")
    scene_spec_parser.add_argument("--project-name", dest="project_name", required=False, default="sandbox_project")
    scene_spec_parser.add_argument("--archetype-id", dest="archetype_id", required=False, default="topdown_adventure_v1")
    scene_spec_parser.add_argument("--output-dir", dest="output_dir", required=False)
    scene_spec_parser.add_argument("--no-write", dest="no_write", action="store_true")
    template_search_parser = subparsers.add_parser("template-search", help="Targeted search for reusable Godot template/demo projects")
    template_search_parser.add_argument("--query", dest="query", required=True)
    template_search_parser.add_argument("--repo", dest="repo", required=False, default="godotengine/godot-demo-projects")
    template_search_parser.add_argument("--ref", dest="ref", required=False, default="master")
    template_search_parser.add_argument("--limit", dest="limit", type=int, required=False, default=8)
    template_fetch_parser = subparsers.add_parser("template-fetch", help="Download template demo folders into local template library")
    template_fetch_parser.add_argument("--project-name", dest="project_name", required=False, default="sandbox_project")
    template_fetch_parser.add_argument("--repo", dest="repo", required=False, default="godotengine/godot-demo-projects")
    template_fetch_parser.add_argument("--ref", dest="ref", required=False, default="master")
    template_fetch_parser.add_argument("--path", dest="template_path", required=False)
    template_fetch_parser.add_argument("--query", dest="query", required=False)
    template_fetch_parser.add_argument("--common-pack", dest="common_pack", action="store_true")
    template_fetch_parser.add_argument("--max-common", dest="max_common", type=int, required=False, default=3)
    template_fetch_parser.add_argument(
        "--procgen-pack",
        dest="procgen_pack",
        action="store_true",
        help="Install a small procedural-generation starter pack for map/terrain objectives",
    )
    template_fetch_parser.add_argument("--max-procgen", dest="max_procgen", type=int, required=False, default=3)
    template_advisor_parser = subparsers.add_parser("template-advisor", help="Recommend when templates should be used for an objective")
    template_advisor_parser.add_argument("--objective", dest="objective", required=True)
    template_advisor_parser.add_argument("--project-name", dest="project_name", required=False, default="sandbox_project")
    smoke_test_parser = subparsers.add_parser("smoke-test", help="Validate scenes/scripts and boot project headlessly")
    smoke_test_parser.add_argument("--project-name", dest="project_name", required=False, default="sandbox_project")
    smoke_test_parser.add_argument("--warnings-as-errors", dest="warnings_as_errors", action="store_true")

    ledger_parser = subparsers.add_parser("ledger", help="Decision ledger operations")
    ledger_parser.add_argument("ledger_command", choices=["add", "list", "validate"])

    evolution_parser = subparsers.add_parser("evolution", help="Evolution engine operations")
    evolution_parser.add_argument(
        "evolution_command",
        choices=["propose", "list", "approve", "reject"],
    )

    agent_parser = subparsers.add_parser("agent", help="AI development team interfaces")
    agent_parser.add_argument(
        "agent_name",
        choices=["director", "architect", "programmer", "qa"],
    )
    agent_parser.add_argument(
        "agent_command",
        nargs="?",
        default="shell",
        choices=["run", "shell"],
    )

    parser.set_defaults(command="init")
    args = parser.parse_args()

    if args.command == "init":
        db = KernelDB()
        db.initialize()
        print("Kernel Ready")
    elif args.command == "reset-sandbox":
        _handle_reset_sandbox(
            keep_assets=not bool(getattr(args, "drop_assets", False)),
            clear_godot_cache=bool(getattr(args, "clear_godot_cache", False)),
        )
    elif args.command == "scan":
        config = load_kernel_config()
        analyzer = ProjectStructureAnalyzer()
        report = analyzer.generate_structure_report(config.project_root)
        print(_format_structure_report(report))
    elif args.command == "validate":
        config = load_kernel_config()
        validator = GodotValidator()
        project_path = config.project_root / "projects" / "sandbox_project"
        report = validator.validate_project(project_path)
        validator.record_results_in_db(report)
        print(_format_validation_report(report))
    elif args.command == "docs-index":
        _handle_docs_index(args.docs_version, args.docs_strict)
    elif args.command == "upgrade-workflow":
        _handle_upgrade_workflow(args.docs_version, args.docs_strict)
    elif args.command == "health-snapshot":
        _handle_health_snapshot(args.limit)
    elif args.command == "proposal-policy":
        _handle_proposal_policy()
    elif args.command == "release-handoff":
        _handle_release_handoff(args.run_id, args.output)
    elif args.command == "orchestrate":
        _run_orchestrate(
            docs_strict=bool(getattr(args, "docs_strict", False)),
            smoke_warnings_as_errors=not bool(getattr(args, "smoke_ignore_warnings", False)),
            skip_smoke_test=bool(getattr(args, "skip_smoke_test", False)),
            template_advisor_precheck=not bool(getattr(args, "no_template_advisor_precheck", False)),
            template_project_name=str(getattr(args, "template_project_name", "sandbox_project")),
            progress_smoke=bool(getattr(args, "progress_smoke", False)),
        )
    elif args.command == "run-report":
        _handle_run_report(args.run_id)
    elif args.command == "creative-brief":
        _handle_creative_brief()
    elif args.command == "asset-brief":
        _handle_asset_brief()
    elif args.command == "scene-spec":
        _handle_scene_spec(
            project_name=str(getattr(args, "project_name", "sandbox_project")),
            archetype_id=str(getattr(args, "archetype_id", "topdown_adventure_v1")),
            output_dir=getattr(args, "output_dir", None),
            no_write=bool(getattr(args, "no_write", False)),
        )
    elif args.command == "template-search":
        _handle_template_search(query=args.query, repo=args.repo, ref=args.ref, limit=args.limit)
    elif args.command == "template-fetch":
        _handle_template_fetch(
            project_name=args.project_name,
            repo=args.repo,
            ref=args.ref,
            template_path=args.template_path,
            query=args.query,
            common_pack=bool(getattr(args, "common_pack", False)),
            max_common=int(getattr(args, "max_common", 3)),
            procgen_pack=bool(getattr(args, "procgen_pack", False)),
            max_procgen=int(getattr(args, "max_procgen", 3)),
        )
    elif args.command == "template-advisor":
        _handle_template_advisor(objective=args.objective, project_name=args.project_name)
    elif args.command == "smoke-test":
        _handle_smoke_test(project_name=args.project_name, warnings_as_errors=bool(args.warnings_as_errors))
    elif args.command == "ledger":
        if args.ledger_command == "add":
            _handle_ledger_add()
        elif args.ledger_command == "list":
            _handle_ledger_list()
        elif args.ledger_command == "validate":
            _handle_ledger_validate()
    elif args.command == "evolution":
        if args.evolution_command == "propose":
            _handle_evolution_propose()
        elif args.evolution_command == "list":
            _handle_evolution_list()
        elif args.evolution_command == "approve":
            _handle_evolution_approve()
        elif args.evolution_command == "reject":
            _handle_evolution_reject()
    elif args.command == "agent":
        if args.agent_command == "run":
            _handle_agent_run(args.agent_name)
        else:
            _handle_agent_interface(args.agent_name)


if __name__ == "__main__":
    main()
