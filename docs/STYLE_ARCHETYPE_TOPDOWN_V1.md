# Style Archetype Topdown V1

Date: 2026-02-21
Status: Design spec (no code changes in this document)
Depends on: docs/DESIGN_CONTRACT_V1.md

## 1) Purpose

Define one reliable top-down adventure archetype the studio can generate repeatedly with different assets while preserving consistent gameplay structure.

This document is the concrete default profile for archetype_id:
- topdown_adventure_v1

Compatibility mapping:
- topdown_action_v1 may map to topdown_adventure_v1 unless an explicit combat objective is requested.

## 2) Strategic direction

Yes, you can choose a known game feel as a reference and build a repeatable studio profile around that feel.

Recommended product framing:
- inspired-by structure, original implementation
- same gameplay grammar, different art/audio/level data
- avoid copying names, characters, maps, story, and unique branded content

## 3) Archetype identity

Archetype name:
- Top-Down Adventure Loop

Core fantasy:
- Move through compact rooms, explore paths, avoid pressure from roaming guardians, complete objectives, and receive immediate feedback.

Core loop:
1. Move and navigate obstacles.
2. Avoid guardian pressure and path-blocking behavior.
3. Trigger interaction with non-violent goals (switches, keys, checkpoints, deliveries).
4. Resolve progress or setback state.
5. Continue loop until objective condition.

## 4) Deterministic defaults

### 4.1 Scene and file contract
Required artifacts:
- projects/sandbox_project/project.godot
- projects/sandbox_project/scenes/Main.tscn
- projects/sandbox_project/scripts/player.gd

Optional archetype artifacts (if requested):
- projects/sandbox_project/scripts/enemy.gd
- projects/sandbox_project/scripts/npc.gd
- projects/sandbox_project/scripts/hud.gd

### 4.2 Required node baseline in Main.tscn
Minimum required nodes:
- Main (Node2D)
- Ground (Sprite2D or TileMapLayer fallback)
- Player (CharacterBody2D)
- Enemy (CharacterBody2D)
- NPC (CharacterBody2D)
- UI (CanvasLayer)
- HealthLabel (Label under UI)

Fallback rule:
- If tileset mapping is ambiguous, use Ground Sprite2D fallback and keep gameplay valid.

### 4.3 Movement and interaction defaults
Player defaults:
- movement_speed: 180
- acceleration_model: immediate (deterministic)
- input_axes: left/right/up/down
- collision_required: true

Guardian defaults:
- chase_enabled: true
- chase_speed: 120
- pressure_range: 48
- contact_cooldown_sec: 1.0
- progress_penalty_on_contact: true

Player state defaults:
- max_stamina: 100
- contact_penalty_enabled: true
- grace_window_sec: 0.2

NPC defaults:
- stationary by default
- simple interaction text optional

### 4.4 Camera and world defaults
Camera:
- top-down 2D camera behavior
- smoothing disabled in V1 for deterministic reproducibility

World layout default:
- room_count: 1 to 3
- deterministic simple layout if no map instructions are provided
- player spawn and enemy spawn must not overlap

### 4.5 HUD defaults
UI minimum:
- one visible label showing stamina or objective state
- update event on contact penalty or objective progress

Display text format:
- STAMINA: current/max

## 5) Asset mapping policy

### 5.1 Discovery categories
Detected textures are classified as:
- character
- enemy
- npc
- tileset_ground
- unassigned

### 5.2 Spritesheet inference
If a texture is likely spritesheet:
- infer hframes/vframes from dimensions
- apply frame metadata for deterministic initial frame

If inference confidence is low:
- treat as static sprite
- keep run valid

### 5.3 Tile usage
If tileset is detected and valid:
- initialize tile-backed ground path

If tile indexing fails or is unclear:
- fallback to ground sprite mode
- do not fail run solely for tile ambiguity in V1

## 6) Prompt under-spec behavior

When objective text is vague, enforce this order:
1. explicit objective constraints
2. topdown_action_v1 defaults
3. safe studio fallback defaults

Minimum generated gameplay behavior under vague prompts:
- controllable player exists
- guardian pursuit and avoidance loop exists
- stamina or objective label updates
- run remains parse-valid and within sandbox

## 7) Hard invariants for this archetype

Run must fail if any are broken:
1. required artifact missing at finalize stage
2. player script parse invalid
3. Main.tscn missing required node baseline
4. out-of-sandbox write attempted
5. unresolved critical scene/script reference

Recovery requirement:
- deterministic artifact recovery must run before final failure and report recovered/missing status.

## 8) Archetype compliance scoring (input to consistency score)

Archetype alignment checkpoints (0-20):
- required node baseline present (6)
- player movement loop works structurally (4)
- guardian pursuit/avoidance loop present (4)
- HUD stamina or objective label present and connected (3)
- asset mapping applied without critical breaks (3)

## 9) Reference profile system (for your clone-like workflow)

Use this to choose game feel while keeping original implementation.

Reference profile fields:
- pacing: slow, medium, fast
- encounter_density: low, medium, high
- room_complexity: simple, moderate, dense
- risk_curve: forgiving, balanced, punishing
- feedback_intensity: subtle, medium, punchy

V1 starter presets:
- profile_arcade: fast pacing, high density, simple rooms, punishing, punchy feedback
- profile_adventure: medium pacing, medium density, moderate rooms, balanced, medium feedback
- profile_relaxed: slow pacing, low density, simple rooms, forgiving, subtle feedback

## 10) Evaluation checklist for 10-run gate

For each run, record:
- required artifacts present (yes/no)
- parse checks pass (yes/no)
- baseline node contract pass (yes/no)
- guardian loop present (yes/no)
- HUD update visible (yes/no)
- recovery invoked (yes/no)
- consistency score

Gate success target:
- 10 consecutive runs with no required-artifact miss

## 11) Future expansion (not in V1)

After topdown_action_v1 is stable:
- topdown_shooter_v1
- topdown_roguelite_v1
- action_rpg_lite_v1

Each new archetype must include:
- deterministic defaults
- required node/file contract
- recovery and scoring hooks

## 12) Terrain plausibility controls (operator-facing)

To avoid chaotic terrain placement and tiny scenes, use these deterministic controls in objective text:

- `terrain grammar: border walls + central path + one water band + bridge`
- `layout style: human-authored rooms and corridors`
- `map density: low|medium|high` (recommended `medium`)
- `tile scale target: readable` (forces non-tiny visual scale)
- `spawn rule: player starts near primary path, never inside obstacles`

Recommended objective suffix:

`Use human-authored terrain grammar (walls, paths, landmarks), readable tile scale, and coherent room/corridor ordering.`

Deterministic composition order for V1:
1. Border/walkability envelope.
2. Main route and branch route.
3. Landmark layer (water/foliage/clearings).
4. Spawn and encounter placement.
5. Camera limits and readability scale.
