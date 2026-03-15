# Scene Spec And Asset Registry V1

Date: 2026-03-15
Status: Draft schema for implementation
Depends on:
- docs/SCENE_ASSEMBLY_PLAN_V1.md
- docs/STYLE_ARCHETYPE_TOPDOWN_V1.md

## 1) Purpose

Define the two new runtime payloads required for deterministic AI-driven scene assembly:
- `Asset Registry`
- `Scene Spec`

These payloads sit between orchestration and Godot scene creation.

## 2) Design rules

- JSON only
- deterministic field names
- explicit fallback behavior
- no raw Godot node serialization from the LLM
- all file references remain sandbox-scoped

## 3) Asset Registry schema

### 3.1 Top-level structure

```json
{
  "registry_version": 1,
  "project_root": "projects/sandbox_project",
  "archetype_id": "topdown_adventure_v1",
  "assets": [],
  "role_bindings": {},
  "discovery_summary": {},
  "warnings": []
}
```

### 3.2 Asset entry

```json
{
  "asset_id": "ground_tileset_01",
  "path": "projects/sandbox_project/assets/tileset.png",
  "kind": "texture",
  "role_candidates": ["ground_tileset_primary", "ground_sprite_fallback"],
  "tags": ["topdown", "terrain", "tileset"],
  "metadata": {
    "width": 256,
    "height": 256,
    "alpha": true,
    "sprite_sheet": true,
    "tile_size": [16, 16],
    "hframes": 16,
    "vframes": 16
  },
  "confidence": 0.92
}
```

### 3.3 Required fields

- `asset_id`: stable internal identifier
- `path`: sandbox-relative path
- `kind`: one of `texture`, `scene`, `audio`, `font`, `script`, `unknown`
- `role_candidates`: ranked semantic roles
- `tags`: searchable behavior/style tags
- `metadata`: normalized engine-relevant facts
- `confidence`: classification confidence 0.0 to 1.0

### 3.4 Role binding map

The final selected roles should be explicit.

```json
{
  "role_bindings": {
    "player_sprite_primary": "player_sheet_01",
    "enemy_sprite_primary": "slime_sheet_01",
    "npc_sprite_primary": "villager_sheet_01",
    "ground_tileset_primary": "ground_tileset_01",
    "ground_sprite_fallback": "ground_flat_01",
    "hud_font_primary": "font_main_01"
  }
}
```

### 3.5 V1 role set

Minimum V1 supported roles:
- `player_sprite_primary`
- `enemy_sprite_primary`
- `npc_sprite_primary`
- `ground_tileset_primary`
- `ground_sprite_fallback`
- `hud_font_primary`
- `prop_rock_variants`
- `prop_tree_variants`

### 3.6 Validation rules

- every `path` must stay under `projects/sandbox_project/`
- every selected role binding must reference an existing `asset_id`
- confidence below threshold must trigger fallback or warning
- V1 does not fail solely because a non-critical prop role is unbound

## 4) Scene Spec schema

### 4.1 Top-level structure

```json
{
  "scene_spec_version": 1,
  "archetype_id": "topdown_adventure_v1",
  "scene_path": "projects/sandbox_project/scenes/Main.tscn",
  "assembly_mode": "create_or_replace",
  "terrain": {},
  "nodes": [],
  "spawns": {},
  "props": [],
  "ui": {},
  "fallbacks": [],
  "acceptance_hints": []
}
```

### 4.2 Terrain block

```json
{
  "terrain": {
    "representation": "tilemap",
    "grammar": "border walls + central path + one water band + bridge",
    "grid_size": [20, 12],
    "tile_size": [16, 16],
    "terrain_types": [
      [1, 1, 1, 1],
      [1, 0, 0, 1]
    ],
    "tileset_role": "ground_tileset_primary",
    "fallback_role": "ground_sprite_fallback"
  }
}
```

`representation` allowed values:
- `tilemap`
- `sprite_fallback`

### 4.3 Node entries

```json
{
  "node_id": "player",
  "node_type": "CharacterBody2D",
  "parent": "Main",
  "role": "player_actor",
  "asset_role": "player_sprite_primary",
  "script_path": "projects/sandbox_project/scripts/player.gd",
  "required": true
}
```

### 4.4 Required V1 nodes

The Scene Spec must be able to materialize this minimum baseline:
- `Main` (`Node2D`)
- `Ground` (`TileMapLayer` or `Sprite2D` fallback)
- `Player` (`CharacterBody2D`)
- `Enemy` (`CharacterBody2D`)
- `NPC` (`CharacterBody2D`)
- `UI` (`CanvasLayer`)
- `HealthLabel` (`Label` under `UI`)

### 4.5 Spawn block

```json
{
  "spawns": {
    "player": [96, 96],
    "enemy": [224, 96],
    "npc": [160, 160]
  }
}
```

### 4.6 Prop entries

```json
{
  "prop_role": "prop_tree_variants",
  "placement_mode": "scatter",
  "zone": "outer_grass",
  "count": 6,
  "avoid": ["player_spawn", "enemy_spawn"]
}
```

### 4.7 UI block

```json
{
  "ui": {
    "show_stamina_label": true,
    "text_format": "STAMINA: {current}/{max}",
    "font_role": "hud_font_primary"
  }
}
```

### 4.8 Fallback entries

```json
{
  "fallbacks": [
    {
      "when": "ground_tileset_primary_unavailable",
      "action": "use_sprite_fallback_ground"
    },
    {
      "when": "npc_sprite_primary_low_confidence",
      "action": "spawn_static_placeholder_color"
    }
  ]
}
```

## 5) LLM output boundaries

The LLM may choose:
- archetype
- terrain grammar
- role selection
- spawn layout
- prop density
- fallback policy

The LLM may not directly choose:
- raw tile IDs
- engine import UUIDs
- `.tscn` serialization details
- hard-coded node owner metadata

## 6) V1 compiler handoff

Expected flow:

1. Runner discovers assets.
2. Registry builder normalizes them into `Asset Registry`.
3. Architect returns `Scene Spec`.
4. Godot assembler reads both payloads.
5. Assembler writes `Main.tscn` and reports a machine-readable result.

## 7) V1 validation checklist

Asset Registry validation:
- JSON schema valid
- role bindings resolvable
- paths sandbox-safe

Scene Spec validation:
- required nodes represented
- scene path sandbox-safe
- terrain representation valid
- spawn coordinates present for required actors
- fallback rules provided for ambiguous terrain mapping