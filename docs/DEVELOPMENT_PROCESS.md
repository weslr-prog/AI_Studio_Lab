# AI_STUDIO_LAB Development Process (End-to-End)

This is the canonical execution order for building and operating the studio from foundation to autonomous production loops.

Operator execution guide: `docs/STUDIO_OPERATOR_RUNBOOK.md`

## Phase 0 — Environment Baseline

**Goal:** deterministic local runtime on constrained hardware.

- Python environment fixed and reproducible.
- Ollama daemon reachable with required local models.
- Godot CLI available for headless validation.
- VS Code tasking available for repeatable local operations.

**Status:** COMPLETE.

---

## Phase 1 — Agent Runtime Reliability

**Goal:** stable model I/O and schema-constrained behavior.

- Shared JSON extraction for all agent responses.
- Defensive handling for malformed model outputs.
- Correct response object access patterns.
- Role-based model gateway and fallback policy.

**Status:** COMPLETE.

---

## Phase 2 — Contract-Driven Orchestration

**Goal:** every run executes under typed contracts and deterministic artifact gates.

- Director creates task plan and contracts.
- Architect/programmer execute contract payloads.
- Required artifact enforcement and sandbox constraints.
- Runtime preflight checks for dependencies and models.

**Status:** COMPLETE.

---

## Phase 3 — Validation and Acceptance Policy

**Goal:** objective outcomes are enforced, not inferred.

- Objective spec compiler (artifacts + acceptance checks).
- Acceptance checks executed post-implementation.
- Acceptance check persistence and run-report visibility.
- Run fails when acceptance policy fails.

**Status:** COMPLETE.

---

## Phase 4 — Observability and Correlation

**Goal:** single-run traceability across all stages.

- run_id propagation through attempts/violations.
- Run manifest persistence for planned work.
- Objective spec and acceptance report integration.

**Status:** COMPLETE.

---

## Phase 5 — Documentation Governance

**Goal:** versioned, enforceable offline engine docs.

- Canonical docs root under `docs/godot/<version>/`.
- `docs-index` command for presence/layout validation.
- Strict mode support for canonical layout enforcement.
- Version policy documentation for future upgrades.

**Status:** COMPLETE (non-strict production mode enabled; strict mode available).

---

## Phase 6 — Task Lifecycle Integrity

**Goal:** orchestration reflects real execution state transitions.

- Transition task statuses through `queued -> in_progress -> completed|failed`.
- Record completion timestamps reliably.
- Expose lifecycle summary in run reporting.

**Status:** COMPLETE.

---

## Phase 7 — Retry and Recovery Policy

**Goal:** controlled resilience without hidden drift.

- Deterministic retry budget per stage.
- Structured failure reasons and retry eligibility.
- Recovery path that preserves run contracts and auditability.

**Status:** COMPLETE.

### Implemented now

- Stage-level deterministic retry policy wired in orchestration (`director_plan`, `architect_proposal`, `programmer_implementation`, `qa_analysis`).
- Retry trace emitted in orchestrate JSON output for full auditability.
- Recovery policy payload emitted with retry budgets and retryable error signatures.
- Deterministic fallback director plan added after retry exhaustion for retryable planning failures.
- Deterministic fallback architect proposal added after retry exhaustion for retryable architecture proposal failures.
- Stage-specific success predicates added so retry traces normalize stage outcomes without `unknown` status drift.

## Phase 8 — Release Readiness Gate

**Goal:** promote only runs that satisfy all hard gates.

- Unified release-readiness decision from acceptance + invariants + artifact/docs policy.
- Optional strict docs/layout policy for CI-style environments.
- Final report snapshot suitable for handoff.

**Status:** COMPLETE.

### Implemented now

- Persistent release-readiness snapshots per run.
- Unified hard-gate evaluation with blocking gate list.
- Optional strict docs policy support in orchestration (`--docs-strict`).
- Run-report includes release readiness and handoff snapshot payload.

---

## Phase 9 — Continuous Studio Operations

**Goal:** sustainable autonomous operation and iterative upgrades.

- Version migration workflow for docs/models/contracts.
- Performance and drift monitoring loops.
- Planned evolution proposals with policy gates.
- Release handoff packaging for downstream automation.

**Status:** COMPLETE.

### Implemented now

- `upgrade-workflow` command for docs/models/contracts operational readiness.
- `health-snapshot` command with persisted snapshot history.
- `proposal-policy` command with rollout action and rollback criteria evaluation.
- `release-handoff` command that writes versioned handoff payloads for run outputs.
- `template-search` command for targeted search of reusable template/demo projects.
- `template-fetch` command for downloading template subprojects into a local template library.
- `template-advisor` command to decide when templates should be used per objective.
- `orchestrate` template precheck integration that emits non-blocking `template_guidance` per run.
- `orchestrate` automatic template bootstrap: selected templates are copied to `projects/sandbox_project/template_bootstrap/current` before implementation when guidance recommends template use.

### Template policy (operator simplicity)

- Install a small common template pack once per project (`platformer`, `top_down`, `inventory` defaults).
- Keep template count intentionally low to reduce operator choice overload.
- For each objective, run `template-advisor` and only use templates when confidence/reasons indicate clear fit.
- Prefer direct generated artifacts in `scenes/` + `scripts/`; treat templates as reference/bootstrap inputs.

---

## Current Checkpoint

All defined phases are complete. The studio now has end-to-end orchestration plus operational governance workflows.

## Ordered Remaining Work (Do Next in Sequence)

1. **Backlog grooming and prioritization** for new feature proposals.
2. **Performance optimization pass** on largest modules.
3. **Optional CI integration** of strict docs and release-readiness policies.
4. **Template quality curation loop** (periodic review and pruning of local template library).
