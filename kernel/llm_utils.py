from datetime import UTC, datetime
import json

from kernel.db import InvariantViolationRecord, KernelDB


_ERROR_RESPONSE = {"status": "error", "message": "LLM returned invalid JSON"}


def _record_invariant_violation(message: str) -> None:
    try:
        db = KernelDB()
        db.initialize()
        invariant_id = db.get_invariant_id("check_evolution_engine_exception")
        if invariant_id is None:
            return
        db.record_invariant_violation(
            InvariantViolationRecord(
                invariant_id=invariant_id,
                file="kernel/llm_utils.py",
                description=message,
                severity=3,
                timestamp=datetime.now(UTC).isoformat(),
            )
        )
    except Exception:
        return


def _strip_markdown_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_json_from_response(text: str) -> dict:
    stripped = _strip_markdown_fences(text)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        _record_invariant_violation("LLM response missing JSON object")
        return dict(_ERROR_RESPONSE)

    candidate = stripped[start : end + 1]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        _record_invariant_violation("LLM response contained invalid JSON")
        return dict(_ERROR_RESPONSE)

    if not isinstance(payload, dict):
        _record_invariant_violation("LLM response JSON was not an object")
        return dict(_ERROR_RESPONSE)

    return payload
