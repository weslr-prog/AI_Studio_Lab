# AI_STUDIO_LAB Operator Runbook

This runbook is the practical, day-to-day operating guide for running the studio.

Objective design reference: `docs/OBJECTIVE_DESIGN_PLAYBOOK.md`

## First 10 Minutes (Quick Cheat Sheet)

If you want the fastest start, use this section first.

1) **Paste this to start**

```bash
cd /Users/wesleyrufus/AI_STUDIO_LAB
pyenv shell 3.11.9
python runner.py docs-index --version 4.2
python runner.py orchestrate
```

2) **When you see `objective:` paste one line like this**

```text
Build a top-down 2D prototype with Main.tscn and scripts/player.gd, acceptance: player movement responds to ui_left/ui_right/ui_up/ui_down and run-report acceptance passes.
```

Prefer guided objective generation? Run this first, then copy one generated objective sentence into `orchestrate`:

```bash
python runner.py creative-brief
```

Want asset-aware suggestions with auto role assignment? Run:

```bash
python runner.py asset-brief
```

Want a low-confusion template baseline (recommended once per project)? Run:

```bash
python runner.py template-fetch --project-name sandbox_project --common-pack
```

Want a procedural-map starter pack (MapGen-style baseline without external repo references)? Run:

```bash
python runner.py template-fetch --project-name sandbox_project --procgen-pack
```

3) **After it finishes, paste this (replace RUN_ID)**

```bash
python runner.py run-report --run-id <RUN_ID>
```

Need to decide whether a new objective should use templates:

```bash
python runner.py template-advisor --project-name sandbox_project --objective "Build a top-down RPG with inventory and dialogue"
```

**Quick build health check (errors/warnings + runtime boot):**

```bash
python runner.py smoke-test --project-name sandbox_project
```

Strict mode (treat warnings as failures):

```bash
python runner.py smoke-test --project-name sandbox_project --warnings-as-errors
```

**See the game now (launch the generated scene):**

```bash
godot --path projects/sandbox_project --scene scenes/Main.tscn
```

**Open Godot editor instead (optional):**

```bash
godot --path projects/sandbox_project --editor
```

If no game window appears:
- Bring Godot to the foreground from macOS Dock.
- Check macOS security prompts and allow Godot if prompted.
- Re-run the launch command once after permissions are granted.

**RUN_ID tip (quick manual):**
- In orchestrate JSON output, copy the value of `"run_id"` and paste it into `<RUN_ID>`.

**RUN_ID tip (copy/paste extraction):**

```bash
python - <<'PY'
import json
from pathlib import Path

p = Path("logs/last-orchestrate.json")
if not p.exists():
   print("logs/last-orchestrate.json not found")
else:
   data = json.loads(p.read_text(encoding="utf-8"))
   print(data.get("run_id", "run_id not found"))
PY
```

4) **If there is an error, paste this first**

```bash
python runner.py docs-index --version 4.2
python runner.py upgrade-workflow --docs-version 4.2
```

5) **If errors persist, paste this and retry smaller scope**

```bash
python runner.py health-snapshot --limit 5
python runner.py proposal-policy
python runner.py orchestrate
```

6) **If you want logs, paste this**

```bash
mkdir -p logs
python runner.py run-report --run-id <RUN_ID> | tee logs/run-report-<RUN_ID>.log
python runner.py release-handoff --run-id <RUN_ID> | tee logs/release-handoff-<RUN_ID>.log
```

Optional: capture orchestrate JSON first, then extract `run_id` automatically:

```bash
mkdir -p logs
python runner.py orchestrate | tee logs/last-orchestrate.json
```

7) **If you want a visual that it is running (not hung), use this two-terminal view**

Terminal A (run studio):

```bash
mkdir -p logs
python runner.py orchestrate | tee logs/last-orchestrate.log
```

Terminal B (live visual monitor):

```bash
while true; do
   clear
   date
   echo "----- orchestrate log tail -----"
   tail -n 25 logs/last-orchestrate.log 2>/dev/null || echo "waiting for logs/last-orchestrate.log"
   echo
   echo "----- latest health snapshot -----"
   python runner.py health-snapshot --limit 1 | head -n 40
   sleep 3
done
```

How to read this visual:
- New lines appearing in log tail = studio is actively progressing.
- Timestamp updating every 3 seconds = monitor is alive.
- If no new log lines for several minutes, first wait (large local models can be slow), then retry with a smaller objective.

Then continue with full details below.

## Build failed? Do this exact reconcile loop

Use this when `orchestrate` returns blocked/failed or the game does not run correctly.

1) **Run strict smoke test first**

```bash
python runner.py smoke-test --project-name sandbox_project --warnings-as-errors
```

2) **Read the blocking reason from orchestrate output**
- If `blocking_gates` contains `smoke_test_passed`, fix runtime/validation first.
- If `blocking_gates` contains `acceptance_passed`, tighten objective acceptance wording and rerun.

3) **Capture run report and inspect acceptance + release gates**

```bash
python runner.py run-report --run-id <RUN_ID>
```

4) **Apply one focused fix only**
- Scene/script wiring issue -> fix node paths/scripts.
- Asset warning/missing resource -> fix asset paths/imports and rerun smoke-test.
- Objective too broad -> split into smaller objective and rerun orchestrate.

5) **Re-run orchestration**

```bash
python runner.py orchestrate
```

Optional escape hatch (development only):

```bash
python runner.py orchestrate --smoke-ignore-warnings
```

If you intentionally need to skip smoke testing once (not recommended):

```bash
python runner.py orchestrate --skip-smoke-test
```

Studio reconciliation behavior now:
- `orchestrate` automatically runs smoke-test by default.
- Release readiness is blocked when smoke-test fails.
- This catches run-time issues earlier and prevents false "ready" states.
- `orchestrate` now emits `template_guidance` (non-blocking) so the studio can auto-decide if installed templates should be used for the objective.
- Objectives that mention procedural-map intent (`procgen`, `mapgen`, `procedural map`, `terrain generator`, `world generator`) are treated as template-friendly by default; user does not need to reference external repos in prompt text.
- When `template_guidance.decision.use_template=true`, `orchestrate` auto-copies the selected installed template into `projects/sandbox_project/template_bootstrap/current` and passes that path as task context.
- Generated deliverables still remain in normal sandbox targets (`scenes/` and `scripts/`); bootstrap files are reference input.

Optional: disable template precheck for one run

```bash
python runner.py orchestrate --no-template-advisor-precheck
```

## Template-first defaults (simple operator policy)

Use this to minimize choices and keep operator UX simple.

1) Install a small starter library once:

```bash
python runner.py template-fetch --project-name sandbox_project --common-pack --max-common 3
```

Optional for procedural terrain/map objectives:

```bash
python runner.py template-fetch --project-name sandbox_project --procgen-pack --max-procgen 3
```

`--procgen-pack` now prefers 2D templates by default and only falls back to non-2D candidates when no 2D match is available.

2) For each new objective, ask advisor first:

```bash
python runner.py template-advisor --project-name sandbox_project --objective "<objective sentence>"
```

3) If you need a specific category, search then fetch:

```bash
python runner.py template-search --query "2d platformer"
python runner.py template-fetch --project-name sandbox_project --query "2d platformer"
```

Default team policy:
- Keep only a few common templates installed.
- Use templates when objective includes known systems (platformer, inventory, dialogue, save/load).
- Skip templates for minimal single-scene prototypes.

### If Godot launches but you get no game output (blank/wrong scene)

Reset generated gameplay files but keep your imported assets:

```bash
python runner.py reset-sandbox --clear-godot-cache
```

Then run a clean build cycle:

```bash
python runner.py orchestrate
python runner.py smoke-test --project-name sandbox_project --warnings-as-errors
```

What this reset does:
- Clears `projects/sandbox_project/scenes/` and `projects/sandbox_project/scripts/`
- Keeps `projects/sandbox_project/assets/` by default
- Optionally clears `.godot` import/cache state (when `--clear-godot-cache` is used)
- Recreates baseline `project.godot` if needed

Only if you intentionally want to wipe assets too:

```bash
python runner.py reset-sandbox --drop-assets --clear-godot-cache
```

## Collaboration FAQ (How you work with the studio)

### Will another run create a new project or modify current sandbox?

Current behavior: runs execute in the same folder:
- `projects/sandbox_project/`

So each run usually adds/updates files in that sandbox. It does not auto-create a new project per run.

Recommended safety habit:
- Snapshot before major iterations (copy folder or commit to git).

### If I am building multiple scenes, how will studio manage that?

Current pipeline is optimized around baseline artifacts:
- `projects/sandbox_project/project.godot`
- `projects/sandbox_project/scenes/Main.tscn`
- `projects/sandbox_project/scripts/player.gd`

You can request extra scenes/scripts, but multi-scene planning/versioning is not fully automated yet. Best practice: expand one scene/feature slice per run.

### Can I play the demo and then request changes?

Yes. Recommended loop:
1. Run studio (`python runner.py orchestrate`).
2. Play demo (`godot --path projects/sandbox_project --scene scenes/Main.tscn`).
3. Note what to improve (feel, readability, mechanics, pacing).
4. Re-run studio with a focused refinement objective.

### Can studio build while I am away and then I refine later?

Yes. Use unattended mode with logs:

```bash
mkdir -p logs
python runner.py orchestrate | tee logs/unattended-orchestrate.log
```

When you return:

```bash
python runner.py run-report --run-id <RUN_ID>
python runner.py release-handoff --run-id <RUN_ID>
```

Then continue with small refinement objectives.

## 1) How the studio currently uses Godot documentation

Today, Godot docs are used in **three ways**:

1. **Availability/policy gate (implemented):**
   - The studio validates docs location and structure with `docs-index`.
   - Release readiness can enforce strict docs layout with `--docs-strict`.

2. **Agent-consumed local retrieval (implemented for architect/programmer):**
   - Architect and programmer prompts include top-matching local docs snippets.
   - Agent outputs include `docs_sources` trace fields.

3. **Human-guided reference (still recommended):**
   - You (the operator) use docs to shape objectives/acceptance language.
   - You use docs while triaging failures and deciding next prompts.

Important: docs retrieval is context enrichment only. Contract/spec/acceptance gates still decide pass/fail.

---

## 2) Start-to-finish workflow (from computer on)

### Step A — Start the machine and open workspace

1. Turn on Mac.
2. Open VS Code.
3. Open folder: `AI_STUDIO_LAB`.
4. Open terminal in that folder.

### Step B — Activate Python runtime

1. Run:
   - `pyenv shell 3.11.9`
2. Verify command path (optional):
   - `which python`

### Step C — Confirm runtime prerequisites

1. Check docs layout for working version:
   - `python runner.py docs-index --version 4.2`
2. Check strict docs policy (release mode):
   - `python runner.py docs-index --version 4.2 --strict`
3. Check upgrade readiness overview:
   - `python runner.py upgrade-workflow --docs-version 4.2 --docs-strict`

If strict fails because docs are nested, either:
- run in non-strict mode for development, or
- flatten docs so `docs/godot/4.2/index.html` exists at root.

### Step D — Decide your operating mode

You have two practical modes:

### Mode 1: Objective-first (fast iteration)

Provide one clear objective sentence when running orchestrate.

Example:
- `Build a Godot 2D Hello World scene with player script`

### Mode 2: SDD-guided (recommended for serious work)

Use an SDD document, then convert it into a concise objective string for orchestrate.

Current system behavior:
- There is no separate SDD parser command yet.
- You still pass one objective prompt, but it should be derived from SDD scope.

Recommended objective format:
- `Implement SDD v0.3: [feature], [artifact targets], [acceptance condition]`

Optional helper command for stronger prompts:
- `python runner.py creative-brief`

---

## 3) Run a development cycle

1. Start orchestration:
   - `python runner.py orchestrate`
2. Enter objective at prompt (`objective:`).
3. Capture `run_id` from output.
4. Inspect full report:
   - `python runner.py run-report --run-id <RUN_ID>`
5. Generate release handoff package:
   - `python runner.py release-handoff --run-id <RUN_ID>`

Where you interact as operator during this cycle:
- You type the objective directly into the terminal when `objective:` appears.
- You run follow-up report commands in the same terminal.
- You inspect generated artifacts under `projects/sandbox_project/` in VS Code.
- You then decide whether to iterate objective wording or fix one gate failure.

### Headless quick-start: copy/paste blocks

Use these exact blocks while operating headless.

1) **Paste this to get started**

```bash
cd /Users/wesleyrufus/AI_STUDIO_LAB
pyenv shell 3.11.9
python runner.py docs-index --version 4.2
python runner.py orchestrate
```

2) **When you see `objective:` paste something like this**

```text
Build a top-down 2D prototype with Main.tscn and scripts/player.gd, acceptance: player movement responds to ui_left/ui_right/ui_up/ui_down and run-report acceptance passes.
```

Or paste an SDD-derived objective sentence (single line) from Section 13.

3) **After run completes, paste this to inspect result**

```bash
python runner.py run-report --run-id <RUN_ID>
```

4) **If you get an error, try this first**

```bash
python runner.py docs-index --version 4.2
python runner.py upgrade-workflow --docs-version 4.2
```

5) **If the error persists, try these checks**

```bash
python runner.py docs-index --version 4.2 --strict
python runner.py health-snapshot --limit 5
python runner.py proposal-policy
```

6) **If it still persists, try one of these reset-style retries**

```bash
python runner.py orchestrate
```

- Retry with a smaller objective (one feature only).
- Remove ambiguous wording and specify concrete artifact targets.
- Use one of the objective examples from Section 16.

7) **If you want logs, paste this in terminal**

```bash
mkdir -p logs
python runner.py run-report --run-id <RUN_ID> | tee logs/run-report-<RUN_ID>.log
python runner.py release-handoff --run-id <RUN_ID> | tee logs/release-handoff-<RUN_ID>.log
```

Optional: capture orchestrate terminal output manually in VS Code terminal scrollback, then save relevant JSON blocks with run_id into `logs/` notes.

---

## 4) Bug triage loop (the “work out the bugs” path)

Use this exact order each cycle:

1. **Run orchestration** and capture `run_id`.
2. **Read run report** for:
   - acceptance failures,
   - invariant violations,
   - release readiness blocking gates,
   - retry traces/fallback usage.
3. **Classify failure type**:
   - Contract/spec issue,
   - Artifact generation issue,
   - Validation issue,
   - Policy/docs issue,
   - Model output/retry issue.
4. **Apply one focused fix**.
5. **Re-run orchestrate**.
6. **Compare new run-report** and confirm gate moved from blocked to passed.

Do not batch many unrelated fixes in one cycle. One bug class per pass keeps causality clear.

---

## 5) Daily health and governance operations

At least once per session run:

1. Health snapshot:
   - `python runner.py health-snapshot --limit 5`
2. Proposal rollout policy:
   - `python runner.py proposal-policy`
3. Upgrade workflow check (before strict release):
   - `python runner.py upgrade-workflow --docs-version 4.2 --docs-strict`

---

## 6) Release decision policy (simple)

A run is release-ready only when all are true:

- Acceptance passed,
- Invariants passed,
- Required artifacts present,
- Docs policy passed (strict/non-strict based on run mode).

Use:
- `run-report` for diagnosis,
- `release-handoff` for downstream packaging and traceable handoff.

---

## 7) What you should provide each run

Minimum required input today:

1. A clear objective sentence.
2. Optional SDD-derived constraints encoded in that objective.
3. Choice of docs policy mode:
   - default (non-strict) for development,
   - strict for release-grade checks.

You do **not** currently answer an automated questionnaire in CLI.
You can run fully autonomously after objective entry, then review gates in report.

Recommended task size per run (important):
- Best throughput: 1 gameplay feature + 1–3 artifacts + 2–5 acceptance checks.
- Good examples: “player movement”, “single enemy patrol”, “basic HUD label”.
- Avoid in one run: full menus + save/load + combat + multiple scenes.
- If scope feels large, split into milestone objectives and run orchestrate per milestone.

---

## 8) Recommended “first serious bug-fix session” checklist

1. `python runner.py upgrade-workflow --docs-version 4.2 --docs-strict`
2. If docs strict fails, decide:
   - flatten docs now (recommended before release), or
   - continue non-strict for development.
3. `python runner.py orchestrate`
4. `python runner.py run-report --run-id <RUN_ID>`
5. Fix top blocking gate only.
6. Repeat until `release_ready = true` under your chosen policy.
7. `python runner.py release-handoff --run-id <RUN_ID>`

---

## 9) Direct docs retrieval (implemented)

Direct local HTML docs retrieval is enabled for architect/programmer prompts.

Operator guidance:

1. Keep docs updated in `docs/godot/<version>/`.
2. Keep retrieval local-only for deterministic operation.
3. Keep release gates authoritative over prompt context.

---

## 10) Should we add direct Godot docs retrieval now?

Short answer: **yes, and it is now enabled**.

It is not a bad idea if you add it with controls:

1. Keep local-only retrieval (no internet dependency).
2. Use docs retrieval as context enrichment, not as an override of contracts.
3. Keep deterministic contract/acceptance gates as final authority.
4. Add a retrieval budget (limit chunks/tokens) for stability on low-memory hardware.
5. Add source trace fields in output (which doc pages informed the decision).

Recommended rollout sequence:

1. Build a simple local docs index (title/path/text chunks).
2. Add retrieval for architect/programmer prompts only.
3. Run A/B checks on bug-fix tasks (with retrieval vs without retrieval).
4. Keep retrieval enabled only when it improves acceptance pass rate.

---

## 11) Other documents that strengthen each agent

Yes — several document types significantly improve agent performance and reduce bug churn.

### Director

1. Product Requirements Document (PRD).
2. Scope and milestone roadmap.
3. Risk register with priorities.
4. Definition of done per milestone.

### Architect

1. System architecture decision records (ADR).
2. Interface/API contracts.
3. Data model and schema definitions.
4. Non-functional requirements (performance/reliability/security).

### Programmer

1. Implementation plan with module boundaries.
2. Coding standards/style guide.
3. API usage examples and edge-case notes.
4. Test plan mapping requirements to test cases.

### QA

1. Acceptance criteria matrix (requirement → expected evidence).
2. Regression checklist.
3. Bug taxonomy and severity rubric.
4. Release gate policy and rollback triggers.

### Cross-cutting documents (high value)

1. SDD (core source of truth).
2. Environment setup/runbook.
3. Change log/migration notes.
4. Observability metrics definitions.

If you only choose three to start, pick:
1. Strong SDD,
2. Acceptance criteria matrix,
3. ADR log.

---

## 12) SDD checklist (generally needed for most dev projects)

Use this checklist before feeding an SDD into the studio workflow.

1. Product goal and problem statement.
2. Target users/personas.
3. Scope in/out (what is included, what is excluded).
4. Functional requirements (numbered, testable).
5. Non-functional requirements:
    - Performance,
    - Reliability,
    - Security/privacy,
    - Maintainability,
    - Accessibility (if UI).
6. System constraints:
    - Platform/runtime,
    - Dependencies,
    - Data/storage constraints,
    - Hardware limits.
7. Architecture overview and key design decisions.
8. Data model/contracts/interfaces.
9. Acceptance criteria (clear pass/fail language).
10. Test strategy:
      - Unit,
      - Integration,
      - End-to-end,
      - Regression.
11. Risks and mitigations.
12. Rollout and rollback plan.
13. Observability/monitoring expectations.
14. Versioning and migration notes (if modifying existing system).

If an SDD is missing items 4, 9, or 10, expect noisy iterations and slower bug closure.

---

## 13) Copy/paste prompt: convert SDD into operator-ready objective sentences

Paste the following prompt into your chatbot, then paste your SDD below it.

You are an AI technical planner.

Task: Convert the SDD into operator-ready objective statements for AI_STUDIO_LAB orchestration.

Output requirements:
1. Return plain JSON only.
2. Provide exactly 3 objective candidates: minimal, balanced, and strict.
3. Each objective must be one sentence and include:
    - feature outcome,
    - artifact targets,
    - measurable acceptance condition.
4. Add one short risk note per objective.
5. Keep each objective under 220 characters.

JSON schema:
{
   "project_name": "string",
   "objectives": [
      {
         "mode": "minimal|balanced|strict",
         "objective_sentence": "string",
         "risk_note": "string"
      }
   ],
   "missing_sdd_fields": ["string"],
   "assumptions": ["string"]
}

Rules:
- Prefer deterministic language.
- Do not invent requirements not present in the SDD.
- If acceptance criteria are weak, include that in missing_sdd_fields.
- Use artifact language compatible with AI_STUDIO_LAB (project.godot, Main.tscn, player.gd or explicit replacements).

After receiving JSON from chatbot:
1. Pick one objective_sentence.
2. Run orchestrate with that sentence.
3. Evaluate run-report and iterate with strict mode objective if needed.

---

## 14) Starting a Godot project with the studio (user interaction map)

Use this exact interaction path for a new project.

1. Open terminal in `AI_STUDIO_LAB`.
2. Run: `python runner.py orchestrate`.
3. At `objective:` prompt, type one objective sentence and press Enter.
4. Wait for JSON output and copy `run_id`.
5. Run: `python runner.py run-report --run-id <RUN_ID>`.
6. Review gates and generated files in `projects/sandbox_project/`.
7. Iterate objective or acceptance wording for next run.

Primary user touchpoints today:
- Terminal prompt input (`objective:`).
- CLI command execution (`orchestrate`, `run-report`, `release-handoff`).
- File inspection/edit in workspace (`projects/sandbox_project/*`).

---

## 15) Where to store game assets so the studio can use them

Store project assets inside sandbox project paths only:

- Scenes: `projects/sandbox_project/scenes/`
- Scripts: `projects/sandbox_project/scripts/`
- Art/audio/UI assets (recommended): `projects/sandbox_project/assets/`

Practical rules:
1. Keep all runtime game files under `projects/sandbox_project/`.
2. Use stable, descriptive names (`player_idle.png`, `enemy_slime.tscn`).
3. Do not store active game assets under `docs/` or repository root.
4. Keep objective text aligned to actual asset paths you expect to be written/used.

---

## 16) Example operator inputs (beyond Hello World)

Where these are entered:
- Enter each line below at `objective:` after `python runner.py orchestrate`.

Example objective inputs:

1. **2D Platformer Movement Slice**
   - `Build a Godot 2D platformer slice with Main.tscn and player.gd implementing left/right movement, jump, and acceptance: player responds to ui_left/ui_right/ui_up without validator errors.`

2. **Top-Down Adventure Prototype**
   - `Implement a top-down movement prototype with CharacterBody2D in Main.tscn and scripts/player.gd, acceptance: diagonal movement works and project validates headlessly.`

3. **Arcade Dodge Core Loop**
   - `Create an arcade dodge core with player movement script and one enemy scene artifact, acceptance: required artifacts exist and run-report acceptance passes.`

4. **Puzzle Room Interaction Seed**
   - `Build a single-room puzzle seed with interactable node wiring and label hints in Main.tscn, acceptance: scene loads and required scene/script artifacts are present.`

5. **Runner Prototype Foundation**
   - `Create runner foundation with continuous forward movement logic in script and simple obstacle scene setup, acceptance: scripts validate and no blocking gate remains except optional polish.`

Tip: Keep objective sentence under ~220 characters when possible, but clarity matters more than brevity.

---

## 17) What game types this setup can currently build well

Current strength (best fit):
- Small-scope 2D prototypes.
- Single-scene or few-scene gameplay slices.
- Core mechanic implementations (movement, collisions, simple interaction).
- Deterministic artifact generation and validation loops.

Current limitations (expected for this phase):
- Large multi-system games in one pass.
- Heavy content pipelines (many assets, full UI flow, full economy systems).
- Rich production-quality polish in one iteration.

Good target projects now:
1. Minimal platformer prototype.
2. Top-down movement + interaction demo.
3. Arcade dodge/survival micro-game.
4. Puzzle room proof-of-concept.

---

## 18) Making user engagement less technical (backlog direction)

Yes, this should be a roadmap item.

Recommended improvements:
1. Guided objective wizard (instead of free-form prompt only).
2. Preset templates for common game genres and feature slices.
3. One-click run/report/handoff workflow with plain-language status.
4. Automatic “next best action” suggestions after failed gates.

---

## 19) GUI/UI and standalone operation roadmap

Yes, both are high-value and compatible with current architecture.

Suggested implementation order:
1. Build local desktop UI wrapper around existing CLI commands.
2. Add run dashboard (status, gates, artifacts, retry trace).
3. Add objective template editor with validation hints.
4. Package as standalone app for macOS operation outside VS Code.

This keeps today’s stable headless kernel while improving usability.

---

## 20) Additional knowledge corpora (beyond Godot docs) without noise

Your idea is valid: supplemental documents can help the studio generate more fun and appealing designs.

High-value optional corpora:
1. Game design pattern libraries (mechanics, feedback loops, onboarding patterns).
2. UX heuristics for games (readability, affordances, cognitive load).
3. Level design principles (pacing, flow, signposting).
4. Accessibility guidelines for games (color/contrast/input alternatives).
5. Postmortem-style design lessons from shipped indie games.

Noise-control policy (important to prevent bloat):
1. Add one corpus category at a time.
2. Keep retrieval role-scoped (Director/Architect first).
3. Require source traces just like `docs_sources`.
4. A/B test acceptance pass rate and iteration count before keeping new corpora.
5. Remove any corpus that increases token noise without measurable improvement.

If you prefer minimalism now, keep only Godot docs and revisit additional corpora after UI roadmap kickoff.
