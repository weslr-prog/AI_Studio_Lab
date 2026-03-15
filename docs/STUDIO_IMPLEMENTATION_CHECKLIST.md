# Studio Implementation Checklist

Date: 2026-02-19
Purpose: Convert strategy into an execution-ready delivery plan with dependencies and realistic effort sizing.

Effort scale:
- S = 0.5-2 days
- M = 3-7 days
- L = 8-15 days

## Phase 0 — Baseline hardening (do first)

### 0.1 Baseline reliability snapshot
- Status: TODO
- Effort: S
- Depends on: none
- Actions:
  - Run current regression suite.
  - Record baseline pass/fail and runtime.
  - Capture known operational limits on current hardware.
- Done when:
  - Baseline report exists with test pass rate + runtime reference.

### 0.2 Orchestrate observability baseline
- Status: TODO
- Effort: S
- Depends on: 0.1
- Actions:
  - Standardize log capture for orchestrate, run-report, release-handoff.
  - Define per-run metrics: duration, retries, fallback use, release_ready.
- Done when:
  - One run summary JSON/log bundle is generated consistently.

### 0.3 Scene assembly contract freeze
- Status: TODO
- Effort: S
- Depends on: 0.1, 0.2
- Actions:
  - Adopt `docs/SCENE_ASSEMBLY_PLAN_V1.md` as the implementation boundary for V1.
  - Freeze scope to `topdown_adventure_v1` plus deterministic scene assembly.
  - Explicitly defer workflow-shell redesign until the 10-run gate passes.
- Done when:
  - Team is building against one stable scene-assembly direction instead of parallel redesign paths.

### 0.4 Scene-spec and asset-registry schema implementation
- Status: TODO
- Effort: M
- Depends on: 0.3
- Actions:
  - Implement validators for the schemas defined in `docs/SCENE_SPEC_AND_ASSET_REGISTRY_V1.md`.
  - Add runner-side payload generation for `Asset Registry` and `Scene Spec`.
  - Add test fixtures for valid and invalid payloads.
- Done when:
  - Runner can emit validated scene-assembly payloads for `topdown_adventure_v1`.

### 0.5 Godot headless assembler spike
- Status: TODO
- Effort: M
- Depends on: 0.4
- Actions:
  - Implement a headless assembler following `docs/GODOT_HEADLESS_ASSEMBLER_V1.md`.
  - Support required node baseline plus tilemap and sprite-ground fallback.
  - Emit machine-readable result payload for run reporting.
- Done when:
  - Godot can build parse-valid `Main.tscn` from validated JSON inputs.

### 0.6 Deployment profile benchmarking
- Status: TODO
- Effort: S
- Depends on: 0.4
- Actions:
  - Add development and deployment routing profiles described in `docs/MODEL_DEPLOYMENT_PROFILES_V1.md`.
  - Benchmark M4 and M1-equivalent runtime behavior using the same objectives.
  - Record latency, retries, fallback use, and failure counts.
- Done when:
  - One default development profile and one deployment profile are selected from measured data.

## Phase 1 — Non-technical intake MVP

### 1.1 Stage A <-> B state model
- Status: TODO
- Effort: M
- Depends on: 0.1
- Actions:
  - Define explicit states (`intake`, `clarify`, `draft_brief`, `await_approval`, `approved`).
  - Define transitions and guardrails.
- Done when:
  - Build cannot start unless state is `approved`.

### 1.2 Plain-language question bank
- Status: TODO
- Effort: S
- Depends on: 1.1
- Actions:
  - Write 10-15 low-jargon questions for genre, player loop, feel, and success criteria.
  - Add follow-up question rules for ambiguous answers.
- Done when:
  - Intake can collect complete minimal brief without technical terms.

### 1.3 Chat-to-brief translator
- Status: TODO
- Effort: M
- Depends on: 1.1, 1.2
- Actions:
  - Map natural language responses to `creative-brief` fields.
  - Emit both plain-language summary and structured payload.
  - Add `needs_confirmation` status.
- Done when:
  - Translator outputs valid structured brief + summary + objective candidates.

### 1.4 Approval checklist gate
- Status: TODO
- Effort: S
- Depends on: 1.3
- Actions:
  - Add approval checklist before orchestration.
  - Require explicit user confirmation.
- Done when:
  - Orchestrate invocation is blocked until checklist confirmation.

## Phase 1.5 — Template launcher (limited)

### 1.5.1 Starter template catalog
- Status: TODO
- Effort: M
- Depends on: 1.3
- Actions:
  - Implement 5-8 starter templates only.
  - Include style label, game reference hint, and prefilled variables.
- Done when:
  - User can select template and receive prefilled brief draft.

### 1.5.2 Support-tier labeling
- Status: TODO
- Effort: S
- Depends on: 1.5.1
- Actions:
  - Label each template `supported now`, `experimental`, or `later`.
  - Show estimated risk in plain language.
- Done when:
  - Users see scope/risk before starting build.

## Phase 2 — Additive build continuity

### 2.1 Extend mode default with rollback snapshot
- Status: TODO
- Effort: M
- Depends on: 0.2
- Actions:
  - Add pre-run snapshot creation.
  - Default run mode to `extend`.
- Done when:
  - Every run has rollback point unless user explicitly chooses `reset`.

### 2.2 Touched-files and change summary
- Status: TODO
- Effort: S
- Depends on: 2.1
- Actions:
  - Capture changed files by run.
  - Publish plain-language "what changed" summary.
- Done when:
  - Run output includes machine-readable and human-readable change logs.

### 2.3 Continuity acceptance checks
- Status: TODO
- Effort: M
- Depends on: 2.1
- Actions:
  - Add checks for previously accepted artifacts.
  - Fail run on unintended regressions.
- Done when:
  - Extend runs protect prior accepted behavior by default.

## Phase 2.5 — Modular build units (v1)

### 2.5.1 Unit contract definition
- Status: TODO
- Effort: M
- Depends on: 2.3
- Actions:
  - Define unit interfaces (dependencies, signals, expected nodes/paths).
  - Create schema for reusable unit metadata.
- Done when:
  - Units can be validated before assembly.

### 2.5.2 Unit-level validation and assembly checks
- Status: TODO
- Effort: L
- Depends on: 2.5.1
- Actions:
  - Validate each unit independently.
  - Add integration checks for assembled project.
- Done when:
  - Project assembly fails fast on incompatible units.

### 2.5.3 Curated reuse registry
- Status: TODO
- Effort: M
- Depends on: 2.5.2
- Actions:
  - Store validated units with tags and compatibility metadata.
  - Suggest reusable units during planning.
- Done when:
  - At least 4 reusable validated unit types exist (`player`, `tilemap`, `hud`, `hazard`).

## Phase 3 — Feedback loop UX

### 3.1 Plain-language feedback parser
- Status: TODO
- Effort: M
- Depends on: 2.2
- Actions:
  - Parse comments like "movement too slow" into scoped delta tasks.
  - Add confidence score and required clarifications.
- Done when:
  - User feedback consistently maps to actionable follow-up objectives.

### 3.2 Delta recommendation assistant
- Status: TODO
- Effort: S
- Depends on: 3.1
- Actions:
  - Suggest minimal next objective with acceptance criteria.
- Done when:
  - User receives one-click refinement objective after each playtest report.

## Phase 4 — Product shell (optional after stability)

### 4.1 Lightweight guided UI wrapper
- Status: TODO
- Effort: L
- Depends on: 1.4, 2.2, 3.2
- Actions:
  - Provide guided flow UI while preserving current CLI backend.
- Done when:
  - Non-technical users can run full loop without terminal commands.

## Deferred by default (not in MVP)

- Multiplayer networking
- Cloud orchestration
- Deep style catalog beyond starter templates
- Large simulation-heavy genres
- Full polished standalone packaging

## Dependency-critical path

1. 0.1 -> 0.2
2. 1.1 -> 1.2 -> 1.3 -> 1.4
3. 1.3 -> 1.5.1 -> 1.5.2
4. 2.1 -> 2.2 and 2.3
5. 2.3 -> 2.5.1 -> 2.5.2 -> 2.5.3
6. 2.2 -> 3.1 -> 3.2

## Operational checkpoint cadence

- Weekly: run regression + runtime trend snapshot.
- Biweekly: validate one full non-technical user loop end-to-end.
- Per milestone: compare against MVP success metrics and defer anything that threatens reliability.
