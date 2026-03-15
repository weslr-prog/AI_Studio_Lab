# Scene Assembly Plan V1

Date: 2026-03-15
Status: Approved working plan
Owner: Studio kernel + Godot scene pipeline
Depends on:
- docs/DESIGN_CONTRACT_V1.md
- docs/STYLE_ARCHETYPE_TOPDOWN_V1.md
- docs/TILEMAP_TERRAIN_ACCEPTANCE_MATRIX_V1.md

## 1) Purpose

Lock the next implementation direction so AI_STUDIO_LAB can create stable Godot scenes without redesigning the orchestration system.

This plan preserves the current Director -> Architect -> Programmer -> QA flow and adds one missing layer:
- a deterministic asset-to-scene assembly pipeline

## 2) Decision summary

Decision for V1:
- Keep current orchestration and role contracts.
- Keep role-specialized prompts.
- Do not build a separate workflow shell similar to gstack.
- Introduce two new runtime artifacts:
  - `Asset Registry`
  - `Scene Spec`
- Move final scene creation into a Godot-side assembler executed headlessly.

## 3) Why this is the right move

Current system strengths already exist:
- deterministic model invocation
- strict JSON extraction
- ledger enforcement
- artifact contracts
- validation gates

Current weakness is not planning structure. It is the translation of discovered assets into a parse-valid, visually coherent Godot scene.

This plan addresses the actual failure surface:
- ambiguous tile usage
- brittle scene authoring
- unclear asset-role binding
- missing or invalid scene structure

## 4) Non-goals for V1

Do not do these before the 10-run gate passes:
- full workflow-slash-command system
- browser automation
- multi-session coordination
- low-poly 3D scene generation
- broad UX redesign
- many archetypes at once

## 5) V1 architecture

### 5.1 Stable orchestration remains

The current runtime stays in place:
- Director plans the run.
- Architect converts objective + assets into a scene plan.
- Programmer fills scripts and helper files.
- QA validates artifacts and runtime behavior.

### 5.2 New translation boundary

The new boundary is:

1. Objective -> Design Intent
2. Design Intent + discovered assets -> Asset Registry
3. Asset Registry + archetype defaults -> Scene Spec
4. Scene Spec -> Godot headless assembler
5. Assembler output -> `Main.tscn` and supporting artifacts
6. Validator + smoke test -> pass or fail

### 5.3 Responsibility split

AI responsibilities:
- infer archetype
- select layout grammar
- choose asset roles
- select fallback strategy
- define spawn logic and gameplay layout intent

Godot responsibilities:
- instantiate nodes
- bind textures and scenes
- create tilemap or sprite fallback ground
- save scene resources
- ensure engine-native scene validity

## 6) Core V1 runtime artifacts

### 6.1 Asset Registry

Purpose:
- hide raw file-path and import complexity from the LLM
- normalize discovered assets into stable categories

Examples of roles:
- `player_sprite_primary`
- `enemy_sprite_primary`
- `npc_sprite_primary`
- `ground_tileset_primary`
- `ground_sprite_fallback`
- `prop_rock_variants`
- `prop_tree_variants`
- `ui_font_primary`

### 6.2 Scene Spec

Purpose:
- provide a high-level, machine-validated scene plan
- prevent the LLM from writing fragile `.tscn` structure directly

Examples of decisions in Scene Spec:
- terrain representation: tilemap or sprite fallback
- required nodes to create
- asset bindings by role
- player/enemy/NPC spawn positions
- prop placement zones
- HUD requirements
- fallback modes when asset confidence is low

## 7) Recommended V1 content scope

Single supported gameplay family:
- `topdown_adventure_v1`

Single supported scene target:
- `projects/sandbox_project/scenes/Main.tscn`

Required artifacts remain:
- `projects/sandbox_project/project.godot`
- `projects/sandbox_project/scenes/Main.tscn`
- `projects/sandbox_project/scripts/player.gd`

Ground strategy for V1:
- use tile-backed terrain when registry confidence is sufficient
- otherwise use deterministic sprite fallback ground

## 8) Model strategy

Keep three logical roles, but do not require three heavy models loaded at once.

Recommended runtime policy:
- M4 development profile: current split remains acceptable
- M1 deployment profile: collapse Architect + Programmer onto one stronger model used serially
- Director and QA may use smaller models or reuse the same shared model with role-specific prompts

The role contract matters more than one-model-per-role purity.

## 9) Immediate implementation sequence

### Step 1
- Define `Asset Registry` schema and validation.

### Step 2
- Define `Scene Spec` schema and validation.

### Step 3
- Add `topdown_adventure_v1` scene grammar and fallback rules.

### Step 4
- Add Godot headless assembler entrypoint that reads Scene Spec and writes `Main.tscn`.

### Step 5
- Wire runner handoff from architect output to assembler invocation.

### Step 6
- Run the 10-run acceptance matrix and freeze scope until it passes.

## 10) Success criteria

This plan is successful when all are true:
- 10 consecutive runs pass the tilemap terrain acceptance matrix
- no required artifact is missing
- `Main.tscn` remains parse-valid
- player spawn and movement remain valid
- ground representation always exists, even under asset ambiguity

## 11) Failure signals

Reconsider only if one of these happens repeatedly:
- Scene Spec is too weak to express the needed layout
- assembler complexity exceeds scene-authoring complexity
- asset registry cannot classify assets reliably enough for V1
- M1 runtime cost becomes operationally unacceptable

If none of those occur, do not redesign orchestration during V1.

## 12) Implementation rule

Until the 10-run gate passes:
- do not add new orchestration modes
- do not add broad UX layers
- do not branch into 3D
- do not expand archetype count

The shortest path to progress is stable scene assembly.