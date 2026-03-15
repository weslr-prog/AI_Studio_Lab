# Gap Closure Checklist V1

Date: 2026-02-28
Status: Active execution checklist
Scope: AI_STUDIO_LAB reliability for one game type (`topdown_adventure_v1`)

## 1) Goal

Build a repeatable studio process for one Godot game type by stabilizing one feature at a time.

Primary rule:
- Do not expand scope until the current feature slice passes its quality gate repeatedly.

## 2) Short answer to your question

Yes. This is the correct approach:
- Start with one feature (tilemap terrain).
- Run repeated build/validate loops until stable.
- Freeze baseline.
- Add next feature as a delta.

This reduces regression risk and matches the kernel/contract architecture already in place.

## 3) What is still lacking (must close)

1. Required artifact enforcement finalization
- Ensure baseline artifacts are always produced.
- Deterministic recovery must run before final failure.

2. Archetype runtime binding
- `topdown_adventure_v1` defaults must be applied when prompt is underspecified.

3. Repeatability harness
- Add a 10-run evaluator for the same objective/profile.
- Persist consistency metrics and failure reasons.

4. Smoke-test determinism
- Resolve current smoke-test non-zero exit path.
- Make failure reason classification explicit and consistent.

5. Golden baseline fixtures
- Add canonical baseline scene/script for recovery/comparison.

## 4) Execution strategy: one-feature-at-a-time

Feature pipeline (strict):
1. Define feature contract.
2. Implement deterministic baseline.
3. Run targeted validation.
4. Run repeated orchestration checks.
5. Freeze feature baseline (no drift).
6. Add next feature as additive delta only.

Stop condition:
- If current feature fails gate, do not add new feature.

## 5) Phase 1 feature: Tilemap Terrain

### 5.1 Feature contract (tilemap v1)
Required outcomes:
- `Main.tscn` contains valid ground representation.
- Prefer tilemap path when tileset is valid.
- Fallback to ground sprite when tile inference is ambiguous.
- Spawn points are valid and non-overlapping.
- Scene remains parse-valid in Godot.

Required files affected:
- `projects/sandbox_project/scenes/Main.tscn`
- `projects/sandbox_project/scripts/player.gd` (must remain valid, even if unchanged)

### 5.2 Acceptance checks (tilemap v1)
Pass checks:
1. Required artifacts exist.
2. `Main.tscn` loads with no parse errors.
3. Ground node exists (tile-backed or sprite fallback).
4. Player can spawn and move without immediate collision lock.
5. Smoke test passes for baseline scene/script.

### 5.3 Repeatability gate for tilemap v1
- Run 10 consecutive iterations using same objective profile.
- Success target: 10/10 with no required artifact misses.
- Allowed fallback: ground sprite fallback is acceptable if deterministic and parse-valid.

## 6) Suggested objective profile for tilemap-first loop

Use a narrow objective that avoids unrelated features:
- "Build a top-down adventure terrain slice with deterministic tilemap ground, valid player spawn, and baseline movement. Keep scope low, sandbox-only writes, and require zero parse errors."

Constraints:
- deterministic
- low scope
- single feature slice
- sandbox-only writes

## 7) Evidence required before moving to next feature

You can add Feature 2 only when all are true:
1. Tilemap v1 gate passed (10 consecutive runs).
2. No missing required artifacts in those runs.
3. Smoke test consistently passes.
4. Failure logs (if any) have classified root causes.

## 8) Recommended next feature order (after tilemap)

1. Player interaction polish (movement feel + collision readability)
2. Non-violent guardian pressure loop
3. Objective markers/checkpoints
4. NPC interaction layer
5. HUD clarity polish

## 9) Operational cadence (lightweight)

Per feature cycle:
- Cycle A: targeted build + validation
- Cycle B: 3-run mini repeatability check
- Cycle C: full 10-run gate
- Freeze baseline and tag docs

## 10) Definition of “good enough” for this studio phase

A feature is "good" when:
- it is deterministic,
- it survives repeated runs,
- it does not break baseline artifacts,
- and it does not increase unresolved smoke-test failures.

At that point, move to the next additive feature.
