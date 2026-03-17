# Studio Implementation Checklist

Date: 2026-02-19
Purpose: Convert strategy into an execution-ready delivery plan with dependencies and realistic effort sizing.

## Canonical planning precedence

Use documents in this order when deciding what to build next:

1. `docs/SCENE_ASSEMBLY_PLAN_V1.md`
  - Approved implementation boundary for current V1 work.
2. `docs/GAP_CLOSURE_CHECKLIST_V1.md`
  - Active execution gate for the current feature slice.
3. `docs/STUDIO_IMPLEMENTATION_CHECKLIST.md`
  - Umbrella roadmap and dependency tracker.
4. `docs/STUDIO_VISION_ALIGNMENT_PLAN.md`
  - Direction document for future UX/product evolution.
5. `docs/DEVELOPMENT_PROCESS.md`
  - Runtime/orchestration maturity record, not the active product-feature queue.

Rule:
- If two documents appear to conflict, follow the highest-precedence document in this list.

## Active execution now

Current active lane is stable scene assembly for one supported archetype:
- Scope: `topdown_adventure_v1`
- Boundary: `Asset Registry` -> `Scene Spec` -> Godot headless assembler -> smoke test -> repeatability gate
- Current stop condition: do not advance to intake UX, template launcher, or broader product shell work until the scene-assembly 10-run gate passes.

This means:
- `docs/DEVELOPMENT_PROCESS.md` phases being complete does not mean product-direction phases are complete.
- `Phase 1` and beyond in this document are intentionally deferred until the scene-assembly lane is stable.
- `docs/AI_Studio_Build_Single_Machine.md` is supplemental workflow guidance, not a replacement architecture plan.

## Immediate execution sequence for the current lane

1. Complete baseline snapshot and observability setup (`0.1`, `0.2`).
2. Freeze scene-assembly scope and reject parallel redesign paths (`0.3`).
3. Implement and validate `Asset Registry` and `Scene Spec` schemas (`0.4`).
4. Implement Godot headless assembly for deterministic `Main.tscn` output (`0.5`).
5. Benchmark development vs deployment model profiles on constrained hardware (`0.6`).
6. Run the gap-closure tilemap terrain gate until it passes repeatedly before expanding scope.

## Single-machine checklist mapping

Apply the single-machine build document in these ways during the active lane:

- Adopt now: smoke tests, prompt log discipline, strict scope control, session separation for heavy local tasks.
- Adapt for Studio: semantic intent, asset registry, scene spec, deterministic translator.
- Defer for now: runtime AI, broad UX shell work, multi-agent redesign, 3D expansion.

## Do Next Now (execution queue)

Use this queue as the active working set. Do not pull new roadmap items until all checkboxes here are complete.

### Queue 1 — Baseline and observability

- [ ] Run baseline validation and record current status.
  - Command: `python runner.py validate`
  - Evidence file: `logs/baseline_validate.log`
- [ ] Run one orchestrated pass and generate report artifacts.
  - Commands: `python runner.py orchestrate` then `python runner.py run-report`
  - Evidence files: latest run manifest and report under `logs/`

### Queue 2 — Scene payload generation

- [ ] Generate `Asset Registry` and `Scene Spec` payloads.
  - Command: `python runner.py scene-spec --project-name sandbox_project`
  - Required files:
    - `projects/sandbox_project/.studio/asset_registry.json`
    - `projects/sandbox_project/.studio/scene_spec.json`
- [ ] Validate payload structure against V1 schema expectations.
  - Source of truth: `docs/SCENE_SPEC_AND_ASSET_REGISTRY_V1.md`
  - Evidence: payloads are parse-valid JSON and include required top-level sections.

### Queue 3 — Headless scene assembly

- [ ] Assemble `Main.tscn` from generated payloads using Godot headless.
  - Command:
    `godot --headless --path projects/sandbox_project --script tools/scene_assembler.gd --scene-spec .studio/scene_spec.json --asset-registry .studio/asset_registry.json`
  - Required output files:
    - `projects/sandbox_project/scenes/Main.tscn`
    - `projects/sandbox_project/.studio/assembly_result.json`
- [ ] Confirm required baseline artifacts still exist post-assembly.
  - Required files:
    - `projects/sandbox_project/project.godot`
    - `projects/sandbox_project/scenes/Main.tscn`
    - `projects/sandbox_project/scripts/player.gd`

### Queue 4 — Smoke and repeatability gate

- [ ] Run smoke tests for the baseline scene/script path.
  - Command: `pytest -k "smoke or tilemap"`
  - Evidence file: `logs/smoke_tilemap.log`
- [ ] Run the tilemap terrain repeatability cycle and record outcomes.
  - Source of truth: `docs/TILEMAP_TERRAIN_ACCEPTANCE_MATRIX_V1.md`
  - Gate: 10 consecutive passes before opening next feature slice.

### Queue completion rule

- [ ] Only after Queues 1-4 are complete, update status for `0.1` through `0.6` and consider activating `Phase 1 — Non-technical intake MVP`.

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
