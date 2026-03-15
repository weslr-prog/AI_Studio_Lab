# Godot Docs Version Policy

Use versioned folders for offline docs:

- `docs/godot/4.2/`
- `docs/godot/4.3/`
- `docs/godot/4.4/`

## Update workflow

1. Download HTML docs for the target Godot version.
2. Extract into `docs/godot/<version>/`.
3. Preferred canonical layout: `docs/godot/<version>/index.html`.
4. Validate with:
   - `python runner.py docs-index --version <version>`
   - Optional strict check: `python runner.py docs-index --version <version> --strict`

## Notes

- Non-strict mode allows a single nested wrapper folder if the download ships that way.
- Strict mode enforces canonical layout and is suitable for CI-style checks.
