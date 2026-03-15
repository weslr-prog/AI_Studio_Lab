# Studio MVP Cut List

Date: 2026-02-19
Purpose: Keep costs controlled and reliability high on limited hardware while delivering visible user value.

## 1) MVP target (ship first)

Ship only what is required to prove the non-technical loop:
- User can describe game in plain language.
- Studio runs Stage A <-> B until build-doc approval.
- Studio generates a structured brief and one objective sentence.
- Studio builds one playable 2D slice.
- User gives plain-language feedback and gets one additive update.

If this loop works reliably, MVP is successful.

## 2) In scope now (must-have)

### UX and flow
- Stage A <-> B required approval loop.
- Plain-language intake prompts and clarifying questions.
- Chat-to-brief translator to current runner fields.
- Approval checklist before build execution.

### Build behavior
- `extend` default mode with pre-run snapshot.
- Touched-files report per run.
- Baseline continuity checks (no unintended breakage of accepted artifacts).

### Template launcher (limited)
- 5-8 templates maximum at launch.
- Each template includes: style label, reference hint, prefilled variables, remaining decisions.
- Support-tier label shown to user: `supported now`, `experimental`, `later`.

### Initial template set (recommended)
- Side scroller / platformer
- Top-down adventure
- Endless runner
- Puzzle room
- Tower defense lite
- Farming lite (optional in first 8)

### Technical constraints
- 2D only.
- Single-player only.
- Local/offline operation.
- Godot baseline artifacts remain first-class acceptance targets.

## 3) Explicitly deferred (first 6 months)

### High complexity systems
- Multiplayer networking and lobbies.
- MMO/social platform behavior.
- Live service economy systems.
- Cloud-hosted orchestration requirements.

### Expensive genre depth
- Full RTS pipelines.
- Full city-builder simulation depth.
- Full first-person shooter polish pipelines.
- Large-scale procedural world generation.

### Heavy product surface area
- Full standalone desktop product packaging polish.
- Complex GUI dashboard suite beyond core loop needs.
- Multi-project workspace orchestration at scale.

## 4) Defer until stability milestone is met

Only advance to these after MVP reliability targets are consistently met:
- Large style catalog expansion (> 12 templates).
- Automatic deep composition of reusable units without manual guards.
- Advanced reusable asset marketplace behavior.
- Aggressive unattended long-chain build plans.

## 5) Non-negotiable guardrails

- No build without approved build doc.
- No destructive reset unless user explicitly selects reset mode.
- Every run has snapshot + rollback point.
- Every additive run includes regression checks on previously accepted behavior.
- Keep prompts short and deterministic for hardware limits.

## 6) Budget-aware success metrics

### Product metrics
- Time from first user message to approved build doc.
- Time from approval to first playable run.
- User satisfaction with plain-language interaction.

### Engineering metrics
- Extend-mode success rate.
- Regression rate after additive updates.
- Mean runtime per orchestration run on current hardware.
- Retry/fallback frequency trend.

## 7) Exit criteria for MVP

MVP is complete when all are true for pilot users:
- They can complete the full non-technical loop without needing technical terms.
- First playable builds complete reliably in constrained scope.
- Additive second run improves prior build without destructive regressions.
- Operational cost and runtime remain acceptable on current local hardware.
