# Godot Headless Assembler V1

Date: 2026-03-15
Status: Implementation design
Depends on:
- docs/SCENE_ASSEMBLY_PLAN_V1.md
- docs/SCENE_SPEC_AND_ASSET_REGISTRY_V1.md

## 1) Purpose

Define how Godot should build `Main.tscn` from `Asset Registry` and `Scene Spec` using engine-native APIs instead of fragile direct text generation.

## 2) Design objective

Use Godot itself as the final compiler for scene creation.

This assembler should:
- read validated JSON payloads
- create or replace the target scene deterministically
- bind assets by semantic role
- apply fallback behavior when asset confidence is low
- save parse-valid resources back into the sandbox

## 3) Proposed runtime entrypoint

Recommended entrypoint:
- `projects/sandbox_project/tools/scene_assembler.gd`

Recommended invocation pattern:

```bash
godot --headless --path projects/sandbox_project --script tools/scene_assembler.gd \
  --scene-spec .studio/scene_spec.json \
  --asset-registry .studio/asset_registry.json
```

Alternate placement is acceptable if the path remains sandbox-safe and testable.

## 4) Inputs

Required:
- `scene_spec.json`
- `asset_registry.json`

Optional:
- archetype defaults file
- prior snapshot reference for extend mode

## 5) Output contract

Required outputs:
- `scenes/Main.tscn`
- machine-readable assembly result JSON

Suggested result payload:

```json
{
  "status": "ok",
  "scene_path": "projects/sandbox_project/scenes/Main.tscn",
  "terrain_mode": "tilemap",
  "fallbacks_used": [],
  "created_nodes": ["Main", "Ground", "Player", "Enemy", "NPC", "UI", "HealthLabel"],
  "warnings": []
}
```

## 6) Assembly stages

### Stage 1: Load and validate inputs

- load JSON files
- validate required fields
- reject out-of-sandbox paths
- fail fast on malformed payloads

### Stage 2: Resolve role bindings

- map semantic roles to actual resources
- preload textures, scenes, and fonts
- classify unresolved roles as critical or advisory

Critical unresolved V1 roles:
- `player_sprite_primary`
- one of `ground_tileset_primary` or `ground_sprite_fallback`

### Stage 3: Create root and required nodes

- create `Main` as `Node2D`
- create `Ground`
- create `Player`, `Enemy`, `NPC`
- create `UI` and `HealthLabel`

### Stage 4: Materialize terrain

If `representation=tilemap` and role binding is valid:
- create `TileMapLayer`
- paint terrain from terrain-type grid
- use terrain-connect or deterministic tile placement strategy

If tilemap path is invalid or ambiguous:
- switch to `Sprite2D` fallback ground
- record fallback usage in result payload

### Stage 5: Bind actors

- instantiate required actor nodes
- attach textures or child sprites
- apply spawn positions
- attach scripts where contract requires them

### Stage 6: Materialize props and UI

- scatter low-risk props using deterministic seed
- avoid required spawn zones
- create label and baseline HUD values

### Stage 7: Save and verify

- save packed scene to `scenes/Main.tscn`
- re-open scene resource if needed for parse check
- emit assembly result JSON

## 7) Determinism rules

- fixed seed for any placement randomness
- stable node names
- stable child ordering
- stable fallback choice ordering
- no runtime dependence on editor-only state

## 8) Error policy

Hard fail on:
- malformed input JSON
- out-of-sandbox path
- missing required root scene path
- missing player script path when required by contract
- inability to save `Main.tscn`

Recoverable with fallback on:
- ambiguous ground tileset usage
- low-confidence NPC or prop bindings
- missing optional font or prop role

## 9) Extend-mode compatibility

V1 may support `create_or_replace` only.

When extend mode is added later, assembler should support:
- loading existing scene
- replacing only targeted subtrees
- preserving untouched validated nodes

Do not add extend complexity before create-or-replace is stable.

## 10) Suggested implementation split

Godot-side modules:
- JSON loader/validator
- role resolver
- terrain builder
- actor builder
- prop scatterer
- scene saver

Python-side modules:
- asset discovery
- asset registry builder
- scene spec validation
- assembler subprocess invocation
- result ingestion into run report

## 11) V1 acceptance for assembler

Assembler is considered ready when:
- it can build `Main.tscn` for `topdown_adventure_v1`
- it succeeds with both tilemap and sprite-ground fallback
- it emits machine-readable warnings and fallback usage
- it supports the 10-run terrain acceptance matrix without parse failures