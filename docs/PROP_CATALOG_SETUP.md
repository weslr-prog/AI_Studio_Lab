# Prop Catalog Setup (Whitelist + Collisions)

This project now uses a **whitelist-only prop catalog** to spawn atlas assets safely.

## Where to edit

- Runtime script: `projects/sandbox_project/scripts/player.gd`
- Generator template: `agents/programmer_agent.py` (inside `_PLAYER_SCRIPT_TEMPLATE`)

Edit `_prop_catalog()` and adjust each `entries` list.
The catalog now includes a starter set of coordinates.

## Entry format

Each approved atlas cell is:

```gdscript
{"x": <column>, "y": <row>}
```

Example:

```gdscript
"entries": [
  {"x": 3, "y": 2},
  {"x": 4, "y": 2},
  {"x": 5, "y": 2}
]
```

## Collision behavior

Per catalog item:

- `collider: true` adds `StaticBody2D + CollisionShape2D`
- `collider_w` and `collider_h` scale trunk/rock footprint
- Shrubs should usually be `collider: false`

## Safe workflow

1. Add 2-4 entries for `tree` first.
2. Run scene and verify no fragment pieces.
3. Add rocks, then shrubs.
4. Tune `count`, `scale`, `collider_w`, `collider_h`.

If `entries` is empty for a category, it is skipped (no random fallback).

All manual `entries` are validated against the strict silhouette filter before spawning,
so invalid or fragment-prone cells are automatically ignored.
