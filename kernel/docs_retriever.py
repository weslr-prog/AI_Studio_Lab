from pathlib import Path
import re
from typing import Any

from kernel.config import load_kernel_config


_MAX_FILES = 250
_CHUNK_SIZE = 700
_FILE_TEXT_CAP = 3500


class _DocChunk:
    def __init__(self, path: str, title: str, text: str):
        self.path = path
        self.title = title
        self.text = text
        self.tokens = _tokenize(f"{title} {text}")


_CACHE: dict[str, list[_DocChunk]] = {}


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(token) > 2}


def _strip_html(html: str) -> str:
    without_scripts = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    without_styles = re.sub(r"<style[\s\S]*?</style>", " ", without_scripts, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", without_styles)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_title(html: str, fallback: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if match is None:
        return fallback
    title = re.sub(r"\s+", " ", match.group(1)).strip()
    return title or fallback


def _resolve_docs_root(version: str) -> Path | None:
    config = load_kernel_config()
    canonical_root = (config.project_root / "docs" / "godot" / version).resolve()
    if not canonical_root.exists() or not canonical_root.is_dir():
        return None

    direct_index = canonical_root / "index.html"
    if direct_index.exists():
        return canonical_root

    nested_candidates = []
    for child in canonical_root.iterdir():
        if child.is_dir() and (child / "index.html").exists():
            nested_candidates.append(child)

    if len(nested_candidates) == 1:
        return nested_candidates[0]
    return None


def _build_chunks(root: Path) -> list[_DocChunk]:
    chunks: list[_DocChunk] = []
    files = sorted(root.rglob("*.html"))[:_MAX_FILES]
    for file_path in files:
        try:
            html = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        title = _extract_title(html, file_path.stem)
        text = _strip_html(html)
        if not text:
            continue
        text = text[:_FILE_TEXT_CAP]
        for start in range(0, len(text), _CHUNK_SIZE):
            segment = text[start : start + _CHUNK_SIZE].strip()
            if len(segment) < 40:
                continue
            relative = str(file_path.relative_to(root))
            chunks.append(_DocChunk(path=relative, title=title, text=segment))
    return chunks


def _get_chunks(version: str) -> list[_DocChunk]:
    root = _resolve_docs_root(version)
    if root is None:
        return []

    key = str(root)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    built = _build_chunks(root)
    _CACHE[key] = built
    return built


def retrieve_docs_context(query: str, version: str = "4.2", max_results: int = 3) -> dict[str, Any]:
    chunks = _get_chunks(version)
    if not chunks:
        return {
            "status": "error",
            "message": "No local docs index available",
            "snippets": [],
        }

    query_tokens = _tokenize(query)
    if not query_tokens:
        return {
            "status": "ok",
            "message": "Empty query tokens",
            "snippets": [],
        }

    scored: list[tuple[int, _DocChunk]] = []
    for chunk in chunks:
        overlap = len(query_tokens & chunk.tokens)
        if overlap > 0:
            scored.append((overlap, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[: max(1, max_results)]
    snippets = [
        {
            "path": item.path,
            "title": item.title,
            "score": score,
            "excerpt": item.text,
        }
        for score, item in top
    ]

    return {
        "status": "ok",
        "message": "retrieved" if snippets else "no matches",
        "snippets": snippets,
    }
