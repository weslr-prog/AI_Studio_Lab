# Tilemap Terrain Command Runner V1

Date: 2026-02-28
Status: Active operator checklist
Scope: Deterministic run procedure for Feature 1 (tilemap terrain)
Depends on:
- docs/TILEMAP_TERRAIN_ACCEPTANCE_MATRIX_V1.md
- docs/GAP_CLOSURE_CHECKLIST_V1.md

## 1) Purpose

Use the exact same command sequence for each run so results are comparable across the 10-run gate.

## 2) Fixed test objective

Use this objective text for all runs:

Build a top-down adventure terrain slice with deterministic tilemap ground, valid player spawn, and baseline movement. Keep scope low, sandbox-only writes, and require zero parse errors.

## 3) One-time setup per session

From repo root:

`cd /Users/wesleyrufus/AI_STUDIO_LAB`

Confirm Python runtime:

`/Users/wesleyrufus/.pyenv/versions/3.11.9/bin/python --version`

Optional baseline snapshot label for notes:

`date +"tilemap_v1_%Y%m%d_%H%M%S"`

## 4) Per-run deterministic sequence

For each run N (1..10), execute in order.

Important staged workflow rule:
- Run Step A (reset) only for the initial setup run, or when you explicitly want a clean rebuild.
- For iterative quality passes, skip Step A so the studio extends existing artifacts instead of deleting and recreating them.

### Step A — Reset workspace state

`/Users/wesleyrufus/.pyenv/versions/3.11.9/bin/python runner.py reset-sandbox --clear-godot-cache`

### Step B — Orchestrate with fixed objective

Use stdin piping to avoid prompt variation:

`printf '%s\n' "Build a top-down adventure terrain slice with deterministic tilemap ground, valid player spawn, and baseline movement. Keep scope low, sandbox-only writes, and require zero parse errors." | /Users/wesleyrufus/.pyenv/versions/3.11.9/bin/python runner.py orchestrate`

### Step C — Script parse check

`cd /Users/wesleyrufus/AI_STUDIO_LAB && /Users/wesleyrufus/.pyenv/versions/3.11.9/bin/python -c "import subprocess; r=subprocess.run(['godot','--headless','--path','projects/sandbox_project','--script','scripts/player.gd','--check-only'],capture_output=True,text=True); print('rc',r.returncode); print('out',r.stdout[:500]); print('err',r.stderr[:500])"`

### Step D — Smoke test

`/Users/wesleyrufus/.pyenv/versions/3.11.9/bin/python runner.py smoke-test --project-name sandbox_project --warnings-as-errors`

### Step E — Capture run report summary

`/Users/wesleyrufus/.pyenv/versions/3.11.9/bin/python runner.py run-report --project-name sandbox_project`

## 4.1 Staged execution mode (recommended)

Stage 0 (one-time bootstrap):
1. Run Step A once.
2. Run Steps B-E.

Stage 1+ (iterative improvement):
1. Do NOT run Step A.
2. Run Steps B-E repeatedly with refinement objectives.

When to reset again:
- only after structural corruption,
- or when intentionally starting a fresh baseline.

## 5) What to record in matrix each run

Populate one row in docs/TILEMAP_TERRAIN_ACCEPTANCE_MATRIX_V1.md with:
- Artifacts pass/fail
- Scene parse pass/fail
- Ground present pass/fail
- Spawn/move pass/fail
- Smoke test pass/fail
- Recovery invoked (yes/no)
- Consistency score (if present)
- Failure class + note

## 6) Failure handling protocol (do not skip)

If any step fails:
1. Record failing step and exit code in matrix notes.
2. Classify using failure taxonomy in the matrix doc.
3. Continue to next run only after classification is recorded.
4. Do not modify objective text mid-series.

## 7) Lightweight operator timing rule

Because hardware is resource-constrained:
- Wait for each command to finish fully.
- Do not assume hang unless system activity is idle for an extended period.
- Keep one active run at a time.

## 7.1 No-hang execution mode (recommended on older hardware)

When orchestrate appears stuck, use this pattern:

1. Run orchestrate with log capture:

`printf '%s\n' "Build a top-down adventure terrain slice with deterministic tilemap ground, valid player spawn, and baseline movement. Keep scope low, sandbox-only writes, and require zero parse errors." | /Users/wesleyrufus/.pyenv/versions/3.11.9/bin/python runner.py orchestrate --skip-smoke-test | tee logs/orchestrate-live.log`

2. In another terminal, watch progress:

`tail -n 40 -f /Users/wesleyrufus/AI_STUDIO_LAB/logs/orchestrate-live.log`

3. Run smoke test separately only after orchestrate completes:

`/Users/wesleyrufus/.pyenv/versions/3.11.9/bin/python runner.py smoke-test --project-name sandbox_project --warnings-as-errors`

This split reduces long silent periods and makes model-latency visible.

## 8) Optional shell helper (single-run wrapper)

If useful, run this for each run index manually:

`RUN_INDEX=1; echo "=== RUN ${RUN_INDEX} ===" && /Users/wesleyrufus/.pyenv/versions/3.11.9/bin/python runner.py reset-sandbox --clear-godot-cache && printf '%s\n' "Build a top-down adventure terrain slice with deterministic tilemap ground, valid player spawn, and baseline movement. Keep scope low, sandbox-only writes, and require zero parse errors." | /Users/wesleyrufus/.pyenv/versions/3.11.9/bin/python runner.py orchestrate && cd /Users/wesleyrufus/AI_STUDIO_LAB && /Users/wesleyrufus/.pyenv/versions/3.11.9/bin/python -c "import subprocess; r=subprocess.run(['godot','--headless','--path','projects/sandbox_project','--script','scripts/player.gd','--check-only'],capture_output=True,text=True); print('rc',r.returncode); print('out',r.stdout[:500]); print('err',r.stderr[:500])" && /Users/wesleyrufus/.pyenv/versions/3.11.9/bin/python runner.py smoke-test --project-name sandbox_project --warnings-as-errors && /Users/wesleyrufus/.pyenv/versions/3.11.9/bin/python runner.py run-report --project-name sandbox_project`

## 9) Exit criteria for Feature 1

Feature 1 is complete only when matrix gate condition is met:
- 10/10 runs pass required checks with no missing artifact failures.
