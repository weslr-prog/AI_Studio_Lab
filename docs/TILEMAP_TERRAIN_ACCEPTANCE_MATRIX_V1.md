# Tilemap Terrain Acceptance Matrix V1

Date: 2026-02-28
Status: Active test template
Scope: Feature 1 validation for `topdown_adventure_v1`
Depends on:
- docs/GAP_CLOSURE_CHECKLIST_V1.md
- docs/STYLE_ARCHETYPE_TOPDOWN_V1.md

## 1) Objective under test

Use one fixed objective across all 10 runs:

- "Build a top-down adventure terrain slice with deterministic tilemap ground, valid player spawn, and baseline movement. Keep scope low, sandbox-only writes, and require zero parse errors."

Constraints:
- deterministic
- low scope
- single feature slice
- sandbox-only writes

## 2) Pass criteria per run

All must pass for a run to count as successful:
1. Required artifacts exist (`project.godot`, `Main.tscn`, `player.gd`).
2. `Main.tscn` parse-valid in Godot.
3. Ground representation present (tile-backed or sprite fallback).
4. Player spawn valid and movement not collision-locked.
5. Smoke test pass (or explicitly classified transient infra issue).

## 3) Run matrix (10-run gate)

Legend:
- PASS = meets criterion
- FAIL = criterion not met
- N/A = not executed due to earlier hard failure

| Run | Artifacts | Scene Parse | Ground Present | Spawn/Move | Smoke Test | Recovery Invoked | Consistency Score | Result | Failure Class | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | PASS | PASS | PASS | PASS | PASS | no | n/a | PASS | n/a | run_id=56f2022c-38ae-4fb3-b9b6-e8c2ec793986; texture_usage ground=assets/tileset.png (tileset); import warning observed for nested template project.godot but smoke passed |
| 2 |  |  |  |  |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |  |  |  |  |
| 4 |  |  |  |  |  |  |  |  |  |  |
| 5 |  |  |  |  |  |  |  |  |  |  |
| 6 |  |  |  |  |  |  |  |  |  |  |
| 7 |  |  |  |  |  |  |  |  |  |  |
| 8 |  |  |  |  |  |  |  |  |  |  |
| 9 |  |  |  |  |  |  |  |  |  |  |
| 10 |  |  |  |  |  |  |  |  |  |  |

## 4) Failure class taxonomy

Use one class per failed run:
- `missing_artifact`
- `scene_parse_error`
- `tilemap_assignment_error`
- `spawn_or_collision_lock`
- `smoke_test_failure`
- `contract_violation`
- `infra_transient`

## 5) Evidence checklist per run

Record at minimum:
- run_id
- objective text used
- asset set hash or snapshot label
- validator output summary
- smoke-test output summary
- recovered artifact list (if any)

Quick run log block template:

- Run #: 
- run_id: 
- objective variant: 
- asset snapshot: 
- validator summary: 
- smoke summary: 
- recovery invoked: yes/no
- failure class (if fail): 
- notes: 

## 6) Gate decision rules

Gate PASS:
- 10/10 runs pass all required criteria.
- 0 `missing_artifact` failures.
- No unresolved smoke test failures.

Gate CONDITIONAL (retest required):
- 9/10 pass and the single fail is `infra_transient` with clear evidence.

Gate FAIL:
- Any `missing_artifact` failure.
- Any repeated failure class (>=2 occurrences).
- Any unresolved parse or contract violation.

## 7) Summary block

After 10 runs, complete:

- Total passed: 
- Total failed: 
- Most common failure class: 
- Recovery invocation count: 
- Consistency score range: 
- Final decision: PASS / CONDITIONAL / FAIL
- Ready for Feature 2 (yes/no): 
- If no, exact fix target for next cycle: 

## 8) Feature 2 entry rule

Do not start Feature 2 until:
1. Final decision is PASS (or approved CONDITIONAL).
2. Missing artifact count is zero.
3. Baseline scene/script stability is demonstrated in this matrix.
