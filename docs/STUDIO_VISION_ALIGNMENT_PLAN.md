# Studio Vision Alignment Plan

Date: 2026-02-19
Status: Direction document (no code or behavior changes in this step)

## 1) Vision statement

The studio should feel like a collaborative game-dev partner for non-technical users:

1. User describes the game in normal language (chat or uploaded document).
2. Studio responds with clear feedback and plain-language questions.
3. Studio converts intent into a structured build brief.
4. Studio builds a playable increment.
5. User plays and gives feedback in simple language.
6. Studio applies changes incrementally without losing prior progress.

This plan aligns current capabilities to that target behavior.

## 2) Product principles

- Human-first language: every prompt and response must be understandable by a non-technical user.
- Translation layer, not user burden: studio converts vague ideas into technical structure.
- Build continuity: new runs should extend prior work by default.
- Short feedback loops: build -> play -> comment -> update.
- Safe operation: preserve current stable flow while iterating toward the target UX.

## 3) Current-state baseline (keep operational)

Current studio remains operational and should stay available while upgrades are added:

- Objective-driven orchestration works today.
- `creative-brief` can generate structured objective candidates.
- Headless run/report workflow is documented.
- Baseline artifacts and acceptance gates are reliable.

Policy for near-term development:
- Do not break existing orchestrate workflow.
- Add new UX as optional front doors first.
- Promote to default only after reliability checks.

## 4) Target user journey (non-technical)

Flow rule:
- Stage A <-> Stage B is a required loop until the user explicitly approves the build document.
- No build starts until the user confirms: "Yes, this build doc matches what I want."

### Stage A: Idea intake
Input types:
- Chat conversation
- Paste-in concept note
- Uploaded design document

Studio behavior:
- Summarizes idea in plain words.
- Asks 5-10 short clarifying questions (genre, player actions, feel, success condition, must-have features).
- Shows user a simple "Did I understand this correctly?" summary.

### Stage B: Brief synthesis
Studio outputs:
- Human-readable "game plan" summary.
- Structured technical brief mapped to runner fields.
- 2-3 scope options (safe, balanced, ambitious) with expected effort/risk.
- A plain-language "approval checklist" so non-technical users can confirm intent.

Stage A <-> B loop behavior:
- If user says "not quite," studio asks follow-up questions in plain language.
- Studio regenerates the build doc with tracked edits (what changed and why).
- Loop continues until user approves the build doc.

### Stage C: Build and preview
Studio outputs:
- Build status in plain language.
- What was created/changed.
- How to run and test.

### Stage D: Feedback loop
User says:
- "movement feels too slow"
- "make enemies easier"
- "add better feedback when I collect items"

Studio does:
- Converts feedback into delta tasks.
- Applies changes as additive updates.
- Preserves and reports what changed.

## 5) Quick solution (near-term): chat-to-brief translator

Goal: accept simple human language, generate high-quality structured `creative-brief` inputs.

### Proposed capability
A guided chat prompt/template that asks plain questions and returns:

- `theme`
- `game_style`
- `core_loop`
- `feel_target`
- `presentation_target`
- `artifact_targets`
- `acceptance`
- `constraints`

### Why this is high value
- Immediate usability upgrade without rewriting the orchestration core.
- Reduces confusion around technical phrasing.
- Increases creative quality of initial builds.

### Output contract
Translator should return:
1. Plain-language summary for user confirmation.
2. Structured JSON block compatible with `creative-brief`.
3. Final objective sentence candidates (minimal/balanced/strict).
4. "Needs confirmation" status until user accepts the brief.

## 6) Template-first acceleration strategy (limited at launch, expandable)

Goal:
- Reduce build-from-scratch effort by starting from style templates with preset variables.

### Template UX behavior
- User can choose either:
  - "Describe my own game idea," or
  - "Start from a style template."
- Template picker shows:
  - Style label (plain language)
  - One known game reference for personal lookup (example: "Mario-style side scroller")
  - What variables are already prefilled
  - What the user still needs to decide

### Launch policy
- Initial template set is intentionally limited but high-value.
- Template catalog expands in phases as stability is proven.

### Common style families to cover over time
- Side scroller / platformer (reference example: Mario-style side scroller)
- Metroidvania
- Top-down adventure
- Action RPG
- Rogue-like / roguelite
- Tower defense
- Real-time strategy
- Turn-based tactics
- First-person shooter
- Third-person action
- Endless runner
- Racing / kart racing
- Point-and-click adventure
- Puzzle / match / logic
- Survival / crafting
- Farming simulator / life sim
- City builder / management sim
- Sandbox builder (including Roblox-style social sandbox concepts)
- Party mini-games
- Visual novel / interactive story
- Rhythm / music timing
- Bullet-hell / shmup
- Idle / incremental
- Multiplayer arena (future scope)

### Why templates help
- Core variables are pre-set (camera, movement baseline, loop archetype, UI expectations).
- Fewer decisions are required from non-technical users.
- Build quality is more consistent across first runs.

## 7) Upgrade requirement from section 8: additive running builds

Problem to solve:
- Current flow can behave like rebuilding baseline artifacts instead of continuing project evolution.

Target behavior:
- Studio defaults to extending existing project state.
- Each run is a delta against prior accepted state.
- User can still request a full reset explicitly.

### Proposed design direction

#### 7.1 Project state model
- Introduce project state profile per sandbox project.
- Track current scene/script graph and feature inventory.
- Save run snapshots and delta metadata.

#### 7.2 Planning mode options
- `extend` (default): add/modify without destructive reset.
- `refactor`: targeted rework with migration notes.
- `reset`: rebuild from baseline by explicit user request.

#### 7.3 Delta execution contract
Each task should specify:
- Existing assets touched.
- New assets created.
- Compatibility checks against current scenes/scripts.
- Rollback point if validation fails.

#### 7.4 Acceptance evolution
Add continuity checks to acceptance gates:
- Existing core scene still loads unless intentionally replaced.
- Existing interactions remain valid unless intentionally changed.
- New feature passes plus no regression in previous accepted checks.

## 8) Modular Godot build pipeline (node/scene decomposition + assembly)

Concept:
- Break a project into smaller build units, execute and validate each unit, then assemble into one integrated project.

### Build unit examples
- Unit A: Player character + movement controller
- Unit B: Tilemap/world layout
- Unit C: Enemies/hazards
- Unit D: UI/HUD
- Unit E: Interaction systems (switches, pickups, doors)

### Proposed workflow
1. Plan units from approved build doc.
2. Build each unit in isolation with unit-level acceptance checks.
3. Mark unit status (`planned`, `in-progress`, `validated`, `blocked`).
4. Run assembly pass to combine validated units.
5. Run integration acceptance and regression checks.

### Reuse model
- Validated units become reusable assets/templates for future projects.
- Reuse metadata includes style tags, compatibility tags, and required dependencies.
- Studio can suggest reusable units during planning to reduce build time.

### Safety rule
- Assembly only uses units marked `validated` unless user explicitly allows experimental units.

## 9) Functional roadmap

### Phase 0: Stabilize and measure (now)
- Keep current studio fully operational.
- Add lightweight telemetry for run type (new vs extend), regressions, and overwrite events.

### Phase 1: Human-language intake layer
- Implement conversation script for non-technical intake.
- Add document summarizer + clarifier question generator.
- Emit structured brief + objective candidates.
- Enforce Stage A <-> B approval loop before build execution.

### Phase 1.5: Template launcher
- Ship limited starter template catalog with style references.
- Add template variable prefill mapping to `creative-brief` fields.
- Add user-friendly template descriptions and lookup hints.

### Phase 2: Additive build engine
- Implement run mode selection (`extend/refactor/reset`).
- Add project-state index and delta planner.
- Add non-destructive defaults and rollback points.

### Phase 2.5: Modular unit pipeline
- Add unit planner for Godot scene/node subsystems.
- Add unit-level acceptance checks.
- Add assembly and integration regression checks.
- Publish validated units to reusable asset registry.

### Phase 3: Continuous playtest loop UX
- Add a feedback command that converts plain comments into delta tasks.
- Generate change logs in non-technical language.
- Add "what changed since last run" summary.

### Phase 4: Productized operator experience
- Add guided UI/chat shell around existing runner commands.
- Keep headless mode available for power users.

## 10) Definition of success

### User experience outcomes
- Non-technical users can produce a meaningful first playable without technical vocabulary.
- User feedback in plain language reliably maps to useful project updates.
- Users understand what changed after each run.
- Users can stay in Stage A <-> B until they are satisfied with the build doc.
- Template-first users can launch quality prototypes with fewer decisions.

### Engineering outcomes
- Existing orchestrate reliability remains intact.
- Extend-mode becomes the default and reduces destructive rewrites.
- Regression rates remain acceptable as continuity features expand.
- Modular unit assembly enables reuse and lowers implementation time over repeated projects.

## 11) Risks and mitigations

- Risk: Ambiguous user language causes incorrect technical mapping.
  - Mitigation: confirmation summary + clarifying questions before build.

- Risk: Additive updates introduce regressions in existing scenes.
  - Mitigation: continuity acceptance checks + rollback snapshot.

- Risk: Scope creep from large requests.
  - Mitigation: enforce safe/balanced/ambitious modes and suggest incremental slices.

- Risk: Template references may imply copying specific games.
  - Mitigation: use references as style guidance only; generate original implementations.

- Risk: Modular units fail when combined.
  - Mitigation: require unit-level validation + integration checks before release-ready status.

## 12) Alignment note on direction shift

Original concept included Openclaw as a development path. Current direction (objective-driven studio with conversational front-end and additive build continuity) is better aligned with the intended outcome: a non-technical, iterative, human-centered game studio workflow.

This plan keeps today’s stable operation while defining the transition path clearly.

## 13) Immediate next planning artifacts to produce

1. Conversational intake question bank (plain language).
2. Chat-to-brief translation schema and examples.
3. Stage A <-> B approval-loop spec (states, transitions, confirmations).
4. Starter template catalog (limited launch set + style-reference labels).
5. Extend/refactor/reset technical design note.
6. Modular build-unit and assembly spec for Godot scenes/nodes.
7. Continuity + integration acceptance test matrix.
8. Pilot evaluation checklist with 3 non-technical user scenarios.

## 14) Professional engineering reality check (budget/resource aware)

This section is a practical assessment to protect scope, cost, and maintainability.

### What should work well (high confidence)
- Stage A <-> B approval loop before any build starts.
- Chat-to-brief translator for non-technical input.
- Limited template launcher with prefilled variables.
- Keeping current CLI workflow as stable fallback while adding new UX.

### What will be difficult (and why)
- Additive build continuity: scene/script merge conflicts and regressions compound over time.
- Modular unit assembly: independently valid units can fail when integrated.
- Broad style coverage at launch: each style needs tuning, tests, and ongoing maintenance.
- Conversational UX on older local hardware: long prompts and large models increase latency.

### Adjustments needed to stay practical
- Ship narrow MVP scope first: 2D, single-player, no networking.
- Start with a small template set (5-8) and publish support tiers (`supported now`, `experimental`, `later`).
- Default to non-destructive extend mode with snapshots and touched-file reporting.
- Treat reusable units as curated building blocks before attempting fully automatic deep composition.
- Enforce prompt/compute budgets (short clarifiers, constrained context windows, small build slices).

### Hard truths plus solutions
- Hard truth: "all common game styles" at launch will hurt reliability.
  - Solution: staged catalog rollout with explicit support labels.
- Hard truth: full autonomous composition is expensive to stabilize.
  - Solution: require unit interface contracts (inputs, signals, dependencies) before reuse.
- Hard truth: vague chat requests can produce weak outputs.
  - Solution: mandatory approval checklist and measurable acceptance before execution.

### 90-day practical delivery shape
- Days 1-30: Stage A <-> B loop, translator, 5 starter templates, support-tier labeling.
- Days 31-60: extend mode with snapshot/rollback and regression checks.
- Days 61-90: modular unit v1 (`player`, `tilemap`, `hud`, `hazard`) with assembly checks.

Reference implementation scope and defer list:
- See [docs/STUDIO_MVP_CUT_LIST.md](docs/STUDIO_MVP_CUT_LIST.md).
