# Godot 4.2 Offline Docs

Canonical local docs location for this project:

- `docs/godot/4.2/`

## Recommended layout

- `docs/godot/4.2/index.html`
- `docs/godot/4.2/classes/`
- `docs/godot/4.2/tutorials/`
- `docs/godot/4.2/...`

If your download arrives as a zip/tar archive, extract its contents directly into `docs/godot/4.2/` so `index.html` is at the folder root.

## Why this path

- Keeps references deterministic across agents and scripts.
- Supports future tooling that can index docs from one known location.
- Avoids mixing runtime project assets with reference documentation.
