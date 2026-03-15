# Objective Design Playbook

Use this guide when writing prompts for `python runner.py orchestrate`.

Fast path: run `python runner.py creative-brief` to generate three objective candidates (minimal, balanced, strict), then paste one into `orchestrate`.

Asset-aware fast path: run `python runner.py asset-brief` to scan `projects/sandbox_project/assets`, auto-suggest asset roles (character/terrain/structures/caves/audio), and generate objective candidates you can paste into `orchestrate`.

## Why this exists

Simple objective prompts produce minimal valid outputs. This playbook helps you ask for richer, more creative builds while staying compatible with current studio gates.

## 1) Objective formula (copy/paste template)

Use one sentence with these parts:

`[Theme + Fantasy] + [Core Loop] + [Creative Flavor] + [Artifact Targets] + [Acceptance Checks]`

Example structure:

`Build a [theme] [game style] where player [core loop], include [creative flavor], target [artifacts], acceptance: [checks].`

## 2) Category word lists mapped to `creative-brief` fields (pick 1-3)

Use these words directly when `python runner.py creative-brief` asks for each field.

### `theme` (Theme / Fantasy words)
- cozy
- mysterious
- neon arcade
- spooky
- playful
- retro pixel
- nature/garden
- sci-fi facility
- dungeon crawl
- sky islands

### `game_style` (Game format / camera / scope words)
- top-down prototype
- side-view platformer slice
- arena dodge demo
- puzzle-room prototype
- auto-runner microgame
- arcade score-chaser
- short narrative slice
- survival mini-loop
- one-room challenge
- single-scene demo

### `core_loop` (Core loop verbs and action phrases)
- move
- dodge
- collect
- survive
- chase
- patrol
- interact
- push/pull
- trigger switches
- deliver items

### `feel_target` (Feel / Juice words)
- snappy
- responsive
- satisfying
- punchy
- readable
- calm
- tense
- rewarding
- polished
- expressive

### `presentation_target` (Presentation words)
- screen shake
- flash on hit
- particle burst
- floating text
- sound cue hook
- UI counter
- status label
- objective label
- color pulse
- simple animation cue

### `constraints` (Constraint words for safer runs)
- deterministic
- low scope
- single feature slice
- no external dependencies
- sandbox-only writes
- Godot 4.2 compatible
- headless validation required

### `acceptance` (Acceptance language starters)
- baseline artifacts exist and Godot validation has zero errors
- baseline artifacts exist and run-report acceptance passes
- Main.tscn and player.gd load with zero parse errors
- required files exist and QA returns release_ready true
- acceptance checks all pass with no invariant violations

## 3) `creative-brief` prompt guide (what each question is asking)

### `project_name [sandbox_project]`
What it wants:
- The target project folder name (usually keep default).

Expected responses:
- `sandbox_project` (recommended)
- `prototype_a` (only if your workflow supports a different folder)

### `theme (e.g., cozy, neon arcade)`
What it wants:
- The fantasy/mood wrapper for your game idea.

Expected responses:
- `cozy`
- `spooky dungeon`
- `neon arcade`

### `game_style (e.g., top-down prototype)`
What it wants:
- The game format and scope shape.

Expected responses:
- `top-down prototype`
- `side-view platformer slice`
- `single-scene puzzle-room prototype`

### `core_loop (e.g., dodge hazards and collect keys)`
What it wants:
- One short sentence describing what the player does repeatedly.

Expected responses:
- `dodge hazards and collect keys`
- `plant seeds, water crops, and harvest`
- `push blocks to activate switches and reach exit`

### `feel_target [responsive]`
What it wants:
- The control/game-feel quality you want the player to notice.

Expected responses:
- `snappy and responsive`
- `calm but readable`
- `tense with punchy collisions`

### `presentation_target [one satisfying feedback effect and one UI label]`
What it wants:
- At least one visual/audio feedback effect and one UI communication element.

Expected responses:
- `flash on hit and score label`
- `particle burst on pickup and objective label`
- `color pulse on interaction and key counter`

### `artifact_targets CSV [...]`
What it wants:
- A comma-separated list of files you want this run to focus on.

Expected responses:
- `projects/sandbox_project/scenes/Main.tscn, projects/sandbox_project/scripts/player.gd`
- `projects/sandbox_project/scenes/Main.tscn, projects/sandbox_project/scripts/player.gd, projects/sandbox_project/scripts/hazard.gd`

### `acceptance [baseline artifacts exist and Godot validation has zero errors]`
What it wants:
- A measurable definition of done.

Expected responses:
- `baseline artifacts exist and Godot validation has zero errors`
- `run-report shows all acceptance checks passed`
- `Main.tscn and player.gd validate with zero errors`

### `constraints [deterministic, low scope, sandbox-only writes]`
What it wants:
- Guardrails that limit risk and keep runs stable.

Expected responses:
- `deterministic, low scope, sandbox-only writes`
- `single feature slice, no external dependencies, headless validation required`

### Quick quality check (`creative-brief` bad vs better)

| Field | Weak input (too vague) | Better input (clear + actionable) |
| --- | --- | --- |
| `theme` | `fun` | `cozy garden at dusk` |
| `game_style` | `platformer` | `side-view platformer slice` |
| `core_loop` | `move around` | `dodge hazards and collect keys to unlock exit` |
| `feel_target` | `good controls` | `snappy jumps with readable landings` |
| `presentation_target` | `add effects` | `flash on hit and score label` |
| `artifact_targets` | `main files` | `projects/sandbox_project/scenes/Main.tscn, projects/sandbox_project/scripts/player.gd, projects/sandbox_project/scripts/hazard.gd` |
| `acceptance` | `works fine` | `baseline artifacts exist and Godot validation has zero errors` |
| `constraints` | `keep it simple` | `deterministic, low scope, sandbox-only writes` |

## 4) Targets you can ask for

### Guaranteed baseline targets (current pipeline)
These are the default acceptance/gate artifacts today:
- `projects/sandbox_project/project.godot`
- `projects/sandbox_project/scenes/Main.tscn`
- `projects/sandbox_project/scripts/player.gd`

### Optional stretch targets (ask explicitly)
These can be requested, but are not guaranteed by default acceptance checks yet:
- Additional scenes under `projects/sandbox_project/scenes/`
- Additional scripts under `projects/sandbox_project/scripts/`
- Assets under `projects/sandbox_project/assets/`
- Simple UI nodes in `Main.tscn` (labels/counters)

## 5) Objective examples (creative but safe)

1. `Build a cozy top-down gardening prototype where player plants and waters crops, include a satisfying feedback flash and seed counter label, target Main.tscn + player.gd + one UI node, acceptance: baseline artifacts exist and Godot validation has zero errors.`

2. `Create a neon arcade dodge slice where player avoids moving hazards, include punchy collision feedback and a score label, target Main.tscn + player.gd + one extra hazard script, acceptance: baseline artifacts exist and no validation errors.`

3. `Implement a spooky puzzle-room prototype where player toggles two switches to open a path, include readable objective text and interaction feedback, target Main.tscn + player.gd + one interaction script, acceptance: baseline artifacts exist and run-report acceptance passes.`

4. `Build a retro micro-runner where player auto-moves and jumps obstacles, include one visual juice effect and a distance label, target Main.tscn + player.gd + one obstacle scene, acceptance: baseline artifacts exist and Godot validation has zero errors.`

## 6) Anti-minimal checklist before you run

Before pressing Enter at `objective:` confirm your sentence includes:
- 1 theme/fantasy phrase,
- 1 core loop,
- 1 feel/presentation requirement,
- 2-4 explicit artifacts,
- measurable acceptance language.

If any is missing, output will usually be minimal.

## 7) Collaboration rhythm (recommended)

1. Generate a build with one focused feature slice.
2. Launch and play test (`godot --path projects/sandbox_project --scene scenes/Main.tscn`).
3. Record what feels weak (e.g., movement feel, feedback clarity).
4. Run studio again with a refinement objective.
5. Repeat in small slices.

This loop produces better creative quality than one very large objective.

## 8) What happens when you run again?

Current behavior:
- Studio runs against the same `projects/sandbox_project` folder.
- It may update/overwrite existing files (especially `Main.tscn` and `player.gd`).
- It does not automatically create isolated project versions per run.

Recommended operator safety habit:
- Save snapshots before major changes (copy folder or use git commit).

## 9) Multi-scene status (current)

Current pipeline is optimized for one primary scene target (`Main.tscn`) plus script.

You can request extra scenes/scripts, but today:
- acceptance gates primarily check baseline artifacts,
- orchestration does not yet provide full scene-graph planning/versioning across many scenes.

Use incremental scene expansion until multi-scene orchestration is upgraded.

## 10) Unattended build while away (practical mode)

Yes, you can do this today in headless mode.

Recommended unattended command pattern:

```bash
mkdir -p logs
python runner.py orchestrate | tee logs/unattended-orchestrate.log
```

When you return:

```bash
python runner.py run-report --run-id <RUN_ID>
python runner.py release-handoff --run-id <RUN_ID>
```

Then resume collaborative refinement with smaller follow-up objectives.
