# Design Contract V1

Date: 2026-02-21
Status: Decision draft (no code behavior changes)
Owner: Studio kernel + orchestration

## 1) Purpose

Define a stable, enforceable design contract that makes output quality consistent for small 2D Godot prototype runs, especially when user prompts are vague.

This contract is intended to answer one question before implementation:

- Is a style-archetype + strict artifact-gate approach the best route for AI_STUDIO_LAB right now?

## 2) Decision statement

Decision for V1:
- Adopt a **Style Archetype Contract** layered on top of existing role contracts.
- Keep current orchestrate workflow intact.
- Add deterministic defaults and hard required-artifact recovery before adding new UX layers.

Why this is the proposed best route now:
- It directly addresses current failure mode (missing required artifact like `scripts/player.gd`).
- It improves consistency without requiring full architecture rewrite.
- It aligns with existing project direction in:
  - `docs/PROJECT_WRITEUP_FOR_SHARING.md`
  - `docs/STUDIO_VISION_ALIGNMENT_PLAN.md`
  - `docs/OBJECTIVE_DESIGN_PLAYBOOK.md`

## 3) Scope (V1)

In scope:
- One primary playable archetype family first: top-down 2D slice.
- Deterministic defaults for scene/script generation when input is underspecified.
- Required artifact guarantees for baseline files.
- Quality gate extensions focused on consistency and contract compliance.

Out of scope (V1):
- Full multi-style library at launch.
- Rich desktop/chat UI redesign.
- Deep modular assembly system across many independent units.

## 4) Core contract entities

### 4.1 Style archetype
A style archetype is a bounded profile that predefines:
- camera perspective
- movement baseline
- enemy behavior baseline
- tile/world layout baseline
- minimum HUD baseline
- acceptable artifact list

V1 archetype set:
- `topdown_action_v1` (only required archetype at launch)

### 4.2 Design intent payload
Each run must compile objective text into:
- `intent_summary`: plain-language one paragraph
- `archetype_id`: required (explicit or inferred)
- `feature_targets`: concise list (2-5)
- `asset_hints`: discovered textures/spritesheets/tilesets
- `acceptance_targets`: measurable pass/fail checks

### 4.3 Output contract
For V1, run is invalid if any required artifact is missing:
- `projects/sandbox_project/project.godot`
- `projects/sandbox_project/scenes/Main.tscn`
- `projects/sandbox_project/scripts/player.gd`

## 5) Deterministic defaulting policy

When user input is vague, defaults are applied in this order:
1. Explicit user constraints in objective.
2. Archetype defaults.
3. Safe studio defaults.

V1 safe defaults:
- single scene baseline (`Main.tscn`)
- one controllable player
- one enemy with chase/attack baseline
- one NPC baseline
- one visible HUD label
- deterministic movement and collision setup

## 6) Invariants and hard gates

A run must fail early (clear reason) if any invariant breaks.

Required invariants:
1. Required artifacts exist.
2. Generated files are inside sandbox scope.
3. Scene references resolvable assets only.
4. Script parse checks pass.
5. Acceptance checks remain machine-readable.

Recovery rule for missing required artifacts:
- Before final failure, deterministic recovery must attempt to produce missing baseline artifacts from archetype templates.
- If recovery fails, run terminates with explicit missing list and stage attribution.

## 7) Quality consistency score (V1)

Add a consistency score (advisory, not release gate in first rollout):

Components (0-100):
- Artifact compliance (40)
- Archetype alignment (20)
- Validation cleanliness (20)
- Objective-to-output coverage (20)

Usage:
- Persist in run report.
- Compare across iterative runs.
- Promote thresholds to hard gates only after stability window.

## 8) Why this approach is optimal now

### 8.1 Compared to “full conversational UX first”
Not optimal first step because:
- It improves intake quality but does not solve deterministic artifact failures.
- It adds latency/complexity on older local hardware.

### 8.2 Compared to “large modular assembly now”
Not optimal first step because:
- Higher integration complexity and regression risk.
- Current blocker is baseline reliability, not feature breadth.

### 8.3 Why Style Archetype Contract first is optimal
- Smallest change with highest reliability gain.
- Directly enforces consistency where failures currently happen.
- Preserves compatibility with existing CLI/orchestrate operations.

## 9) Implementation phases for V1

Phase A (must-do first):
- Enforce required artifact target discipline per role.
- Add deterministic missing-artifact recovery.
- Add explicit stage-level failure reasons.

Phase B:
- Formalize `topdown_action_v1` archetype defaults.
- Apply consistent scene/script baseline mapping.

Phase C:
- Add consistency score + reporting.
- Validate score stability over repeated runs.

## 10) Go / No-Go criteria

Go if all are true:
1. 10 consecutive runs produce required baseline artifacts.
2. No “missing required artifact” failures in those runs.
3. Godot validation remains clean for baseline files.
4. Consistency score variance stays within agreed tolerance.

No-Go if any are true:
- Required artifact misses remain common.
- Recovery layer causes uncontrolled file drift.
- Latency increase is unacceptable for local hardware.

## 11) Risks and controls

Risk: archetype over-constrains creativity.
- Control: keep archetype baseline minimal; allow additive optional targets.

Risk: recovery logic hides deeper planning defects.
- Control: emit recovery telemetry with root-cause classification.

Risk: style drift despite defaults.
- Control: archetype alignment checks + explicit fallback template references.

## 12) Recommendation

Recommendation: **Proceed with this contract as V1.**

Reason:
- It is the most practical and lowest-risk path to your stated goal: consistent, dependable studio output before expanding UX surface area.

## 13) Immediate next artifacts after approval

1. `STYLE_ARCHETYPE_TOPDOWN_V1.md` (concrete defaults and knobs)
2. `CONSISTENCY_SCORE_SPEC.md` (formula and thresholds)
3. `ARTIFACT_RECOVERY_POLICY.md` (deterministic recovery rules)
4. `RUN_EVAL_CHECKLIST_V1.md` (10-run verification protocol)
