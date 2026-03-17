**AI-Driven Game Development Process**

Godot Engine · Lean · Iterative · Budget-Conscious

_A practical solo-developer pipeline using AI as a co-developer - single machine edition_

# **Overview**

This document outlines a complete, practical process for developing 2D games (and later, Low Poly 3D games) using AI-assisted tools in conjunction with the Godot engine. It is designed for a solo developer working with a single machine and limited resources, and is built around efficiency, reproducibility, and maintaining creative momentum from first idea through to a shippable build.

The core philosophy of this system is deliberate: build a playable experience first, then expand it intelligently using AI as a co-developer - not a replacement for direction. AI tools are powerful when aimed precisely. They are wasteful and demoralising when used without structure.

This process addresses and eliminates common solo-developer failure modes: overbuilding before testing, generating inconsistent assets, using the wrong AI tool for the job, losing prompts that worked, and losing forward momentum to perfectionism.

# **Development Philosophy**

Traditional game development often follows a linear structure: design → build → polish. This model does not translate well to AI-assisted solo workflows because it front-loads decision-making before you have enough feedback to make good decisions.

This system is built instead on a tight iterative loop:

- Build the smallest possible playable version of a mechanic
- Test it immediately
- Identify the single most limiting problem
- Fix only that problem using the right tool
- Repeat

At every stage, the guiding question is: Does this improve the playable experience right now? If the answer is no, it is not the next step. This keeps scope controlled and prevents the common trap of building systems for a game that does not yet exist in playable form.

**Principle to Internalize**

Progress comes from iteration, not perfection.

A working game with rough edges is infinitely more valuable than a polished design document.

Treat every session as: what is the smallest thing I can build and test today?

# **Hardware Configuration**

This pipeline is designed to run entirely on a single development machine. Everything - Godot, VSCode, GitHub Copilot, Ollama, and your browser-based AI tools - runs on the same device. The workflow is structured so that AI tasks do not interrupt active development, by separating generation sessions from coding sessions rather than separating them across hardware.

## **Your Development Machine**

Your single machine handles all roles in this pipeline. Use it for:

- Writing and running GDScript in VSCode or the Godot built-in editor
- GitHub Copilot-assisted code completion
- Running and playtesting your Godot project
- Running Ollama locally for debugging and code refactoring
- AI prompting via browser (ChatGPT, Claude)
- Asset generation and import into Godot

## **Installing and Running Ollama Locally**

Ollama runs as a background service on your machine and is queried from your terminal. It does not require an internet connection once a model is downloaded, making it your cost-free local reasoning partner for debugging and refactoring tasks.

| \# Install Ollama from <https://ollama.com>                                       |
| --------------------------------------------------------------------------------- |
| \# Then pull a capable model - codellama is recommended for GDScript work         |
| ollama pull codellama                                                             |
| ollama pull llama3 # Good general-purpose reasoning                               |
|                                                                                   |
| \# Ollama starts automatically as a background service after install.             |
| \# Query it directly from your terminal:                                          |
| ollama run codellama 'Explain this GDScript error and fix it: ...'                |
|                                                                                   |
| \# Or use the local API (useful for scripting longer prompts):                    |
| curl <http://localhost:11434/api/generate> \\                                     |
| \-d '{"model": "codellama", "prompt": "Fix this GDScript: ...", "stream": false}' |
|                                                                                   |

**Managing Ollama and Godot on the Same Machine**

Ollama inference uses RAM and CPU. If you notice Godot slowing during a playtest session, stop the Ollama service temporarily: run 'ollama stop' in your terminal.

A practical rhythm: run Godot for playtesting, switch to terminal for Ollama debugging, switch back. Do not run heavy inference and active playtesting simultaneously.

If your machine has 16GB RAM or more, this co-existence is generally comfortable. On 8GB machines, alternate rather than overlap.

# **Tool Roles and Responsibilities**

One of the most common mistakes in an AI-assisted workflow is reaching for the wrong tool. Each tool in this pipeline has a distinct role. Using them interchangeably wastes time and produces worse results.

| **Tool**                 | **Primary Role - What It Is For**                                                                                                                                                         |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Godot Engine             | Your game runtime, editor, and export pipeline. All gameplay lives here.                                                                                                                  |
| GDScript                 | Godot's native scripting language. Prefer it over C# for solo 2D work - faster iteration, better Copilot support in this context, and no compile step.                                    |
| GitHub Copilot (Premium) | Inline code completion as you type in VSCode. It completes functions, suggests patterns, and fills boilerplate. It does not reason about broken code - it autocompletes.                  |
| Ollama (local)           | Your reasoning partner for debugging and restructuring. Runs locally on your machine. Feed it errors and broken logic; receive fixes and explanations. Best for iterative back-and-forth. |
| ChatGPT / Claude (web)   | High-context planning, architecture decisions, long-form content generation, and tasks that benefit from a conversational interface with memory in the session.                           |
| AI Image Generator       | Sprite and asset generation. Used in controlled, structured sessions using a locked master prompt. Never used ad hoc.                                                                     |
| AI Audio Tool            | Sound effects and ambient loops. Used only during the Polish phase (Step 8). Not part of early development.                                                                               |

**Copilot vs Ollama - The Key Distinction**

Copilot is a writing assistant. It helps you write new code faster by predicting what you intend to type.

Ollama is a thinking assistant. It analyses existing code, explains errors, and reasons about structure.

Use Copilot when your fingers are moving. Use Ollama when something is broken or needs to be redesigned.

Mixing these up - asking Copilot to explain a deep bug, or using Ollama to autocomplete lines - underuses both.

# **Engine Commitment: Godot**

Choosing and committing to an engine before writing any code is a required step, not an optional preference. The engine determines your file structure, your scripting language, how assets are imported, how you package your final build, and what GitHub Copilot is actually trained to help you write.

## **Why Godot for This Pipeline**

- Godot is free and open-source with no royalties or licensing costs, which aligns directly with a budget-conscious approach.
- Its built-in 2D engine is first-class - not a port of a 3D system. Sprites, tilemaps, collision, and animation are native and efficient.
- Godot 4 includes a full Low Poly 3D pipeline, meaning the same engine scales with your ambitions without requiring a platform change.
- GDScript is Python-like and readable. GitHub Copilot handles it well, and Ollama local models have sufficient training data on it.
- The export pipeline is straightforward for solo developers targeting desktop and web platforms.

## **GDScript vs C# - Make This Decision Once**

For solo 2D development using this pipeline, use GDScript. The reasons are practical:

- No compilation step - changes are reflected immediately in the editor.
- Copilot completes GDScript reliably. C# in Godot requires additional project configuration and introduces .NET dependencies.
- Ollama local models perform reasonably well on GDScript given its syntactic similarity to Python.
- When you move to Low Poly 3D work later, you can reassess. For now, GDScript keeps your feedback loop fast.

## **VSCode as Your Editor**

While Godot has a built-in script editor, VSCode with the Godot Tools extension provides GitHub Copilot integration and a more capable editing environment. Set it up as your external editor.

| \# In Godot: Editor > Editor Settings > Text Editor > External           |
| ------------------------------------------------------------------------ |
| \# Set 'Use External Editor' to On                                       |
| \# Set Exec Path to: /usr/local/bin/code (or your VSCode binary path)    |
| \# Set Exec Flags to: {project} --goto {file}:{line}:{col}               |
|                                                                          |
| \# Install the Godot Tools extension in VSCode                           |
| \# Extension ID: geequlim.godot-tools                                    |
|                                                                          |
| \# In VSCode settings - point the extension at your Godot binary         |
| \# godot_tools.editor_path: /Applications/Godot.app/Contents/MacOS/Godot |
|                                                                          |

# **Step 1 - Define the Core Game Loop**

Before writing any code or generating any assets, you must define the core player interaction loop in plain language. This definition is your north star for every decision that follows. If a feature or asset does not serve this loop, it does not belong in your first build.

The core loop answers exactly three questions:

- What does the player do repeatedly?
- What determines success or failure?
- What feedback does the player receive that tells them how they are doing?

Write the answers in two to four sentences. If you cannot summarise the loop that concisely, the design is not resolved enough to begin building. Use ChatGPT or Claude to help you pressure-test it.

## **Prompt: Pressure-Testing Your Core Loop**

Send this to ChatGPT or Claude when you have a draft loop definition:

| I am designing a 2D game for a solo developer with a tight budget.    |
| --------------------------------------------------------------------- |
| Here is my intended core loop:                                        |
| \[INSERT YOUR LOOP DESCRIPTION\]                                      |
|                                                                       |
| Please evaluate this loop on three criteria:                          |
| 1\. Is it narrow enough to build in a two-week prototype?             |
| 2\. Does it require mechanics that are disproportionately complex for |
| what the player experiences?                                          |
| 3\. What is the single highest-risk assumption in this design?        |
|                                                                       |
| Be direct and critical. I want problems identified now, not after I   |
| have built the wrong thing.                                           |
|                                                                       |

## **AI-Native Game Design - A Strategic Consideration**

The most efficient game designs for this pipeline are ones that align structurally with what AI tools are good at generating and maintaining. This is not a creative limitation - it is a force multiplier.

Games built around decisions, dialogue, narrative branching, or systems-driven emergent play benefit from this pipeline more than games built around tight action physics, complex animation rigs, or procedural generation of spatial environments. Consider designing toward AI strengths when you have a choice between two otherwise equivalent directions.

# **Step 2 - Establish the Asset Pipeline**

AI-generated art can become inconsistent and disorganised within a single session if not controlled from the start. This step creates two permanent structures: a Style Lock that governs all visual generation, and a folder structure that governs all asset storage. Both must be established before any assets are created.

## **Part A: Style Lock**

A style lock is a master prompt template that defines every visual constraint for your game. All assets are generated from variations of this master prompt, modifying only what is necessary to change, while keeping every other parameter identical.

| \# MASTER PROMPT TEMPLATE (2D Pixel Art example)                              |
| ----------------------------------------------------------------------------- |
| Art style: pixel art                                                          |
| View: 2D side view                                                            |
| Sprite size: 32x32 pixels                                                     |
| Palette: limited, warm earthy tones, no more than 16 colours                  |
| Outline: clean 1px dark outline                                               |
| Shading: soft, two-tone shading per surface                                   |
| Background: transparent                                                       |
| Rendering: flat, no gradients                                                 |
| Consistency: same lighting angle throughout (top-left)                        |
|                                                                               |
| \# VARIATION FIELDS - change only one at a time:                              |
| Subject: \[DESCRIBE CHARACTER OR OBJECT\]                                     |
| Pose / State: \[idle \| walking_01 \| walking_02 \| attack \| hurt \| death\] |
| Expression: \[neutral \| surprised \| angry \| talking\]                      |
|                                                                               |

| \# MASTER PROMPT TEMPLATE (Low Poly 3D example, for future use) |
| --------------------------------------------------------------- |
| Art style: low poly 3D                                          |
| Polygon count: very low, faceted surfaces visible               |
| Texture: flat colour per face, no texture maps                  |
| Palette: muted natural tones, consistent across all assets      |
| Lighting bake: pre-baked flat shading, no real-time shadows     |
| Perspective: isometric or 3/4 view reference image              |
| Background: transparent or white ground plane                   |
|                                                                 |
| \# VARIATION FIELDS:                                            |
| Subject: \[DESCRIBE OBJECT OR CHARACTER\]                       |
| State: \[default \| damaged \| active \| destroyed\]            |
|                                                                 |

**Critical Rules for Style Lock**

Generate all variations of a character or object in a single session. AI image generators drift over time and between sessions - even with identical prompts, results shift. Batch everything.

Save every prompt that produced a usable result alongside the image output in your Prompt Log (see Step 3).

Never generate assets ad hoc. Every generation session starts by loading the master prompt, not rewriting it from memory.

If a result is unusable, note what changed in the prompt and why. This becomes part of your iterative prompt knowledge.

## **Part B: Asset Folder Structure**

Establish this folder structure inside your Godot project before importing a single asset. Naming discipline prevents hours of reorganisation later and ensures Godot's import system behaves consistently.

| res:// ← Godot project root  |
| ---------------------------- |
| ├── assets/                  |
| │ ├── characters/            |
| │ │ ├── player/              |
| │ │ │ ├── player_idle.png    |
| │ │ │ ├── player_walk_01.png |
| │ │ │ ├── player_walk_02.png |
| │ │ │ ├── player_attack.png  |
| │ │ │ └── player_hurt.png    |
| │ │ └── enemy_slime/         |
| │ │ ├── slime_idle.png       |
| │ │ └── slime_death.png      |
| │ ├── environment/           |
| │ │ ├── tiles/               |
| │ │ └── props/               |
| │ ├── ui/                    |
| │ │ ├── hud/                 |
| │ │ └── menus/               |
| │ └── audio/                 |
| │ ├── sfx/                   |
| │ └── music/                 |
| ├── scenes/                  |
| │ ├── characters/            |
| │ ├── levels/                |
| │ └── ui/                    |
| ├── scripts/                 |
| │ ├── characters/            |
| │ ├── systems/               |
| │ └── ui/                    |
| ├── data/                    |
| │ └── dialogue/              |
| └── exports/                 |
|                              |

Naming convention for all asset files: lowercase, underscores only, no spaces, prefixed by category. This ensures alphabetical sorting groups related assets and prevents Godot import conflicts.

# **Step 3 - The Prompt Log**

The Prompt Log is the single most underestimated piece of infrastructure in this pipeline. It is a living document - a plain text file or Markdown file committed to your project repository - that records every prompt that produced a useful result, whether for code, assets, dialogue, or debugging.

Without a Prompt Log, you will rediscover the same solutions repeatedly. With it, your knowledge compounds across sessions and across projects.

## **Prompt Log Structure**

| \# PROMPT LOG                                                                  |
| ------------------------------------------------------------------------------ |
| \# Project: \[Your Game Name\]                                                 |
| \# Format: Date \| Category \| Tool \| Prompt \| Notes                         |
|                                                                                |
| \## ASSET PROMPTS                                                              |
|                                                                                |
| \### Master Style Prompt (2D Pixel)                                            |
| Date: \[date\]                                                                 |
| Tool: \[image generator name\]                                                 |
| Prompt:                                                                        |
| Pixel art, 2D side view, 32x32 sprite, limited earthy palette,                 |
| clean 1px outline, transparent background, top-left lighting.                  |
| Subject: player character, brown jacket, short hair.                           |
| Pose: idle standing.                                                           |
| Result: KEEPER - use as base for all character variants                        |
| Notes: Slightly too dark on left arm. Add 'bright highlights' to next variant. |
|                                                                                |
| \## CODE PROMPTS                                                               |
|                                                                                |
| \### State Machine Refactor                                                    |
| Date: \[date\]                                                                 |
| Tool: Ollama (codellama)                                                       |
| Prompt:                                                                        |
| Refactor this GDScript into a clean state machine pattern.                     |
| States needed: IDLE, WALK, JUMP, ATTACK, HURT.                                 |
| Use an enum, not string comparisons.                                           |
| \[code pasted below\]                                                          |
| Result: KEEPER - clean output, minor variable name edits needed                |
|                                                                                |
| \## DIALOGUE / CONTENT PROMPTS                                                 |
|                                                                                |
| \### NPC Dialogue - Shopkeeper                                                 |
| Date: \[date\]                                                                 |
| Tool: ChatGPT (GPT-4)                                                          |
| Prompt:                                                                        |
| Write five lines of dialogue for a grumpy shopkeeper in a                      |
| medieval fantasy town. Tone: dry, world-weary, not hostile.                    |
| Each line should be usable as an idle ambient dialogue snippet                 |
| of no more than 15 words.                                                      |
| Result: PARTIAL - 3 of 5 lines usable. Lines 2 and 4 too on-the-nose.          |
|                                                                                |

**Prompt Log Rules**

Log a prompt immediately when it produces a useful result - not at the end of the session.

Mark results clearly: KEEPER (use again), PARTIAL (use with edits), REJECT (note why).

Commit the prompt log to your Git repository so it is version-controlled alongside your code.

Review the log at the start of each session before generating anything new.

# **Step 4 - Build the Minimum Viable System**

At this stage you open Godot and begin building. The goal is the simplest possible version of your game that is playable - meaning a human can interact with it and receive feedback. This is called the Minimum Viable System (MVS).

The MVS is not a prototype of everything. It is a proof of the core loop and nothing more. No menus, no audio, no multiple levels, no full UI. Those are polish, and polish comes last.

## **Recommended Minimum Scene Structure in Godot**

| \# Recommended starting scene hierarchy in Godot |
| ------------------------------------------------ |
|                                                  |
| Main.tscn                                        |
| └── Node2D (root)                                |
| ├── Player (CharacterBody2D)                     |
| │ ├── Sprite2D                                   |
| │ ├── CollisionShape2D                           |
| │ └── player.gd                                  |
| ├── Level (Node2D)                               |
| │ ├── TileMap                                    |
| │ └── Spawner (Node2D)                           |
| └── GameManager (Node)                           |
| └── game_manager.gd                              |
|                                                  |

Resist the urge to build a complex scene tree immediately. Add nodes only when a gameplay need makes them necessary.

## **Using GitHub Copilot Effectively During This Step**

Copilot is most effective when you write descriptive comments before the code you intend to write. This gives Copilot context to generate accurate completions rather than generic boilerplate.

| \# player.gd - Copilot-assisted workflow example                     |
| -------------------------------------------------------------------- |
|                                                                      |
| \# Handle movement using arrow keys or WASD.                         |
| \# Apply gravity when not on floor.                                  |
| \# Jump when space is pressed and player is on floor.                |
| func \_physics_process(delta):                                       |
| \# Copilot will suggest the full implementation here                 |
| \# based on the comments above - review and accept selectively       |
| pass                                                                 |
|                                                                      |
| \# Emit a signal when player health drops to zero.                   |
| signal player_died                                                   |
|                                                                      |
| \# Take damage, clamp health above zero, emit died signal if needed. |
| func take_damage(amount: int) -> void:                               |
| pass # Copilot will complete this                                    |
|                                                                      |

**Copilot Validation Rule**

Never accept a Copilot suggestion without reading it. Copilot autocompletes toward the most statistically likely code, not the most correct code for your specific system.

Accept suggestions line-by-line using Tab, not in bulk. Test after every logical block.

## **MVS Completion Criteria**

The Minimum Viable System is complete when all of the following are true:

- A player can start the game and immediately interact with a core mechanic
- The game responds to input with visible feedback
- One full cycle of the core loop (start → action → outcome) can complete
- The build does not crash on a clean run

Do not proceed to Step 5 until these criteria are met. Everything built before this point is fragile scaffolding.

# **Step 5 - AI-Assisted Debugging and Iteration**

Once the MVS is running, this step becomes your primary ongoing workflow. It is not a single phase - it is a loop that runs continuously throughout development. When friction appears (a bug, a design problem, an unwieldy script), this is how you resolve it.

## **Debugging Workflow with Ollama**

When an error occurs or a script needs improvement, the process is:

- Run the game and reproduce the problem
- Copy the error message and the relevant GDScript
- Send it to Ollama in your terminal
- Receive the fix, apply it, and test immediately
- Log the prompt if the result was useful

## **Prompt Templates for Ollama Debugging**

For error explanation and fix:

| I am working in Godot 4 using GDScript.                           |
| ----------------------------------------------------------------- |
| Here is the error I am receiving:                                 |
| \[PASTE FULL ERROR MESSAGE FROM GODOT OUTPUT PANEL\]              |
|                                                                   |
| Here is the script where the error occurs:                        |
| \[PASTE RELEVANT SCRIPT\]                                         |
|                                                                   |
| Explain what is causing this error in plain terms,                |
| then provide a corrected version of the problematic section only. |
| Do not rewrite the entire script.                                 |
|                                                                   |

For refactoring:

| I have the following GDScript that works but is difficult to maintain. |
| ---------------------------------------------------------------------- |
| Refactor it to be cleaner and more modular.                            |
| Requirements:                                                          |
| \- Use an enum for state management instead of string comparisons      |
| \- Break logic longer than 20 lines into named helper functions        |
| \- Add brief comments on any non-obvious logic                         |
| \- Do not change the external behaviour                                |
|                                                                        |
| \[PASTE SCRIPT\]                                                       |
|                                                                        |

For generating a new system from a description:

| I am building a 2D game in Godot 4 using GDScript.                     |
| ---------------------------------------------------------------------- |
| I need a reusable inventory system with the following behaviour:       |
| \- The player can hold up to 10 item slots                             |
| \- Items are represented as a Dictionary with keys: id, name, quantity |
| \- Methods needed: add_item, remove_item, has_item, get_all_items      |
| \- Emit a signal when inventory changes                                |
|                                                                        |
| Provide a clean GDScript implementation.                               |
| Use typed variables where possible.                                    |
| No UI code - this is a data system only.                               |
|                                                                        |

## **When to Use ChatGPT or Claude Instead of Ollama**

Local Ollama models are fast and cost-free but have limitations on context length and reasoning depth. Use a web-based model when:

- The problem requires understanding a large codebase across multiple files
- You need architectural advice, not just a bug fix
- You are designing a system from scratch and want iterative back-and-forth with memory in the session
- Ollama has given you two incorrect answers in a row on the same problem

Save Ollama for the fast, high-frequency tasks. Save the premium web models for the slow, high-stakes decisions.

# **Step 6 - Controlled Content Expansion**

Once the core loop is functional, stable, and demonstrably engaging - even in rough form - you can begin expanding content. The key word is controlled. AI is highly capable of generating content volume, which makes it equally capable of burying your game in content you did not actually need.

Before any expansion session, write down the specific gap you are filling: one missing mechanic, one missing level, one set of NPC dialogue for a specific scene. Generate for that gap only.

## **Expanding Dialogue and Narrative**

AI is highly effective at generating dialogue, branching conversations, and emotional tone variation. The prompts below are designed to produce output that is immediately usable with minimal editing.

For branching dialogue:

| Write a conversation between \[CHARACTER A\] and \[CHARACTER B\].             |
| ----------------------------------------------------------------------------- |
| Context: \[1-2 sentences describing the scene and stakes\]                    |
| Tone: \[e.g., tense and guarded / warm but secretive / comedic with an edge\] |
|                                                                               |
| Structure the response as follows:                                            |
| \- An opening line from Character A                                           |
| \- Three player response choices, each clearly leading to a different         |
| emotional or factual outcome                                                  |
| \- One follow-up line from Character A for each choice                        |
|                                                                               |
| Keep all lines under 20 words.                                                |
| Do not use ellipses for dramatic effect.                                      |
| Do not resolve the conversation - leave it at a decision point.               |
|                                                                               |

For ambient or environmental flavour text:

| Write 8 short ambient dialogue lines for a \[CHARACTER TYPE\] in a \[SETTING\]. |
| ------------------------------------------------------------------------------- |
| These are idle lines the character says when the player is nearby but not       |
| engaged in conversation.                                                        |
|                                                                                 |
| Requirements:                                                                   |
| \- Each line must be standalone (no context required to understand it)          |
| \- Maximum 12 words per line                                                    |
| \- Tone: \[describe tone\]                                                      |
| \- Avoid anything that references specific plot events                          |
| \- Vary the emotional register: include at least 2 humorous, 2 serious, 2 tired |
|                                                                                 |

## **Expanding Level and Scenario Design**

Use AI to generate structured progression frameworks, not full level designs. Levels require spatial judgment that AI cannot reliably provide, but the scaffolding of progression - what a level introduces, what it tests, what new element appears - is well within AI's capability.

| I am designing a 2D game with the following core loop:                 |
| ---------------------------------------------------------------------- |
| \[DESCRIBE YOUR CORE LOOP\]                                            |
|                                                                        |
| Generate a 5-level progression framework.                              |
| For each level provide:                                                |
| \- The primary mechanic being introduced or tested                     |
| \- One new twist or complication not present in the previous level     |
| \- The expected player failure mode (what most players will get wrong) |
| \- A one-sentence description of the emotional arc (what should the    |
| player feel at the start vs. end of this level?)                       |
|                                                                        |
| Do not describe spatial layout. Focus only on design logic.            |
|                                                                        |

## **Expanding the Codebase**

As the game grows, use Ollama to generate new systems rather than building them manually from scratch. Always describe the system's interface - what goes in and what comes out - before asking for an implementation.

| I need a save/load system for a Godot 4 game.                      |
| ------------------------------------------------------------------ |
| Data to persist: player health, inventory (Array of Dictionaries), |
| current level name (String), elapsed time (float).                 |
|                                                                    |
| Requirements:                                                      |
| \- Save to a JSON file at user://savegame.json                     |
| \- Load on game start if file exists, otherwise use defaults       |
| \- Include a method to check if a save file exists                 |
| \- Emit a signal when save completes successfully                  |
| \- Handle file-not-found gracefully without crashing               |
|                                                                    |
| Provide a complete GDScript autoload singleton.                    |
|                                                                    |

# **Step 7 - Editorial Curation of AI Content**

At the content expansion stage, your role changes from builder to editor. AI will generate volume. Your job is to maintain quality, consistency, and design integrity. This is a skill that requires criteria - without clear standards, curation collapses into gut feel, which is inconsistent.

## **Editorial Rubric for AI-Generated Content**

Apply this rubric to every piece of AI-generated content before committing it to the project. A content piece must pass all four criteria to be accepted without modification.

| **Criterion**        | **Question to Ask**                                                                                                                                                                          |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tone Fit             | Does this match the emotional register established in the style guide? A line that is too witty in a serious game or too grim in a light one breaks immersion immediately.                   |
| Mechanical Relevance | Does this introduce, reinforce, or extend a mechanic? Content that only adds world flavour without serving the loop is a low priority and should be deferred.                                |
| Branching Integrity  | If this is dialogue with choices, do the choices lead to meaningfully different outcomes, or are they cosmetically different paths to the same result? The latter wastes player time.        |
| Scope Discipline     | Does accepting this content require building anything new? If a dialogue line references a location, item, or character that does not yet exist in the game, it is not ready for this phase. |

**The Editor's Discipline**

Never accept AI content wholesale. Even if 90% is usable, that 10% will introduce inconsistency that compounds across the project.

Editing AI output is not a failure of the process - it is the process. AI generates the material. You shape it.

When you find yourself editing the same type of problem repeatedly across multiple generations, update your prompt to fix it at the source. Log the improved prompt.

# **Step 8 - Real-Time vs Pre-Generated AI**

Before scaling your game significantly, you must make one architectural decision that has far-reaching consequences: will AI be a development tool only, or will it be a runtime component during actual gameplay?

This is not a trivial choice. Getting it wrong late in development is expensive to reverse.

| **Approach**                                   | **Description and Implications**                                                                                                                                                                                                                                                                                                                               |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pre-Generated (Recommended for First Projects) | All AI content - dialogue, scenarios, level data - is generated during development and stored as static files (JSON, text). At runtime, the game reads from these files. No AI calls happen during play. This approach has zero latency, zero API cost during play, full offline support, and deterministic behaviour.                                         |
| Real-Time AI (Advanced, High Complexity)       | The game makes live API calls to a language model during play. Player input is sent to an AI and responses are generated on the fly. This enables genuinely dynamic behaviour but introduces latency (noticeable pauses), per-play API costs, dependency on internet connectivity, inconsistent output quality, and significantly more complex error handling. |

For your first games using this pipeline, use pre-generated content. Treat the real-time approach as a feature to prototype in a future project once you have a stable grasp of the full pipeline. Introducing runtime AI into a first project risks collapsing the development loop under the weight of integration complexity.

**If You Choose Real-Time AI Later**

Budget for API latency in your UX - add loading states or ambient animations to mask response time.

Always implement a fallback: if the API call fails or times out, the game must handle it gracefully rather than crash.

Set a hard token budget per request to control cost. A game that makes 50 uncapped API calls per session will become unaffordable quickly.

Rate-limit requests on the client side to avoid burning through API allowances during testing.

# **Step 9 - Polish and Packaging**

Polish is the final layer, not an ongoing concern. It is earned by completing everything before it. Adding polish to a game with an unstable core loop is one of the most common ways solo projects fail - the developer loses momentum in polish work and never returns to the structural problems underneath.

Polish begins only when the game is consistently playable, the content is complete to its defined scope, and the core loop is demonstrably engaging to someone who did not build it.

## **UI Polish**

At this stage, add the interface elements the player needs to understand the game state: health indicators, score display, item counts, and any contextual prompts. Build these in Godot's CanvasLayer so they exist in screen space rather than world space.

| \# Generate UI layout suggestions with ChatGPT or Claude          |
| ----------------------------------------------------------------- |
|                                                                   |
| I am building a HUD for a 2D game in Godot 4.                     |
| The core loop is: \[DESCRIBE LOOP\]                               |
| The information the player needs to track at all times is:        |
| \- \[list what matters\]                                          |
|                                                                   |
| Suggest a minimal HUD layout for a 1280x720 resolution.           |
| Prioritise clarity and minimal visual noise.                      |
| Describe element positions relative to screen edges.              |
| Do not suggest decorative elements unless functionally necessary. |
|                                                                   |

## **Audio**

Sound is disproportionately effective for perceived quality. A small set of contextually appropriate sound effects - interaction feedback, state changes, ambient loops - raises the feel of the game significantly.

Use AI audio generation tools for:

- UI sounds: button clicks, menu transitions, confirmation tones
- Ambient loops: background environment audio for each scene
- Feedback sounds: success, failure, pickup, hit

Avoid generated music as a background layer for your first build. It rarely sits well under gameplay and adds a layer of judgement complexity. Use either silence or a single simple ambient loop.

| \# Prompt for AI audio generation tools                           |
| ----------------------------------------------------------------- |
|                                                                   |
| Short sound effect, approximately 0.3 seconds.                    |
| Purpose: player collecting a small item in a 2D adventure game.   |
| Tone: light, satisfying, not dramatic.                            |
| No reverb. No pitch variation beyond a single brief upward chirp. |
| Format: WAV, 44100Hz, mono.                                       |
|                                                                   |

## **Menus and Transitions**

Add a main menu and a game-over screen last. These are the first and last things a player sees but the last things you should build, because their design depends on knowing what the game actually is.

Use Copilot to generate the scene transition code, and Ollama to debug it. Keep menus functional rather than decorative for a first build.

## **Packaging and Export**

Godot's export pipeline is straightforward but requires export templates to be downloaded and platform-specific settings to be configured. Use AI to generate platform-specific instructions relevant to your target.

| \# Export prompt for ChatGPT or Claude                                |
| --------------------------------------------------------------------- |
|                                                                       |
| I am exporting a Godot 4 game built with GDScript.                    |
| Target platform: \[macOS / Windows / Web / Linux\]                    |
| Development machine: Apple Silicon Mac.                               |
|                                                                       |
| Provide step-by-step export instructions for this platform.           |
| Include: export template installation, any platform-specific settings |
| I need to change, codesigning requirements if applicable, and         |
| the final file format the player will receive.                        |
|                                                                       |

# **Scope Management - When Is a Game Done?**

The back half of solo development - expansion, curation, and polish - is where most projects stall indefinitely. This happens because there is no explicit definition of done. The game is always one feature away from being ready.

Before you begin Step 6, define your version 1.0 scope in writing. Be specific and ruthless.

| \# Version 1.0 Scope Definition Template                                   |
| -------------------------------------------------------------------------- |
|                                                                            |
| Game title: \[name\]                                                       |
| Core loop: \[one sentence\]                                                |
| Number of levels / stages: \[specific number\]                             |
| Number of enemy / NPC types: \[specific number\]                           |
| Dialogue lines (approx): \[specific number\]                               |
| Audio: \[list specific sounds only, no music / one ambient track\]         |
| Platform target: \[single platform for v1.0\]                              |
|                                                                            |
| NOT in v1.0 (explicitly excluded):                                         |
| \- \[feature you want but do not need\]                                    |
| \- \[feature you want but do not need\]                                    |
| \- \[feature you want but do not need\]                                    |
|                                                                            |
| v1.0 is done when:                                                         |
| \- A person who did not build it can play start to finish without guidance |
| \- No crashes occur in a 15-minute play session                            |
| \- The core loop is completable at least 3 different ways                  |
|                                                                            |

**The Not-List Is As Important As the Scope List**

Explicitly naming what is not in v1.0 prevents scope creep far more effectively than general discipline.

Every time you feel the pull toward a new feature, check it against the not-list.

Features on the not-list are not abandoned - they are version 1.1 and beyond. Ship 1.0 first.

# **Efficiency Principles**

These rules govern decisions throughout the entire process. When you are unsure what to do next, check against this list first.

- Build only what is necessary for the current loop. Everything else is speculation about a future state that may never arrive.
- Test immediately after every change. The longer you go without testing, the harder bugs become to isolate.
- Avoid regenerating assets unless absolutely required. Time spent regenerating is time not spent building.
- Reuse prompts, systems, and structures whenever possible. The prompt log is the mechanism for this.
- Separate AI generation sessions from implementation sessions. Do not switch between generating and coding mid-task. Finish one mode, then switch.
- When Copilot and Ollama disagree, test both. When both are wrong, escalate to a web model.
- If a problem has taken more than two Ollama iterations without resolution, change your approach - not your model.
- Name everything clearly on first creation. Renaming files and nodes later breaks Godot references and wastes time.
- Commit to Git at the end of every session, even if the work is incomplete. Uncommitted work that gets lost is the most demoralising event in solo development.

# **Appendix A - Minimal Git Workflow**

Git is non-negotiable for this pipeline. Every session should end with a commit. Use descriptive messages that describe what changed in the game, not what you typed.

| \# Initial setup inside your Godot project folder             |
| ------------------------------------------------------------- |
| git init                                                      |
| git add .                                                     |
| git commit -m 'Initial project structure'                     |
|                                                               |
| \# .gitignore essentials for Godot                            |
| \# (Godot generates this automatically - verify it includes:) |
| .godot/                                                       |
| \*.uid                                                        |
|                                                               |
| \# End-of-session commit                                      |
| git add .                                                     |
| git commit -m 'Player movement working, jump height tuned'    |
|                                                               |
| \# If something breaks badly - revert to last commit          |
| git checkout -- .                                             |
|                                                               |
| \# Creating a named checkpoint before risky work              |
| git tag v0.1-mvs-complete                                     |
|                                                               |

# **Appendix B - Quick Prompt Reference**

This section summarises the key prompt patterns from throughout the document for fast reference during a session.

## **Copilot - In-editor Patterns**

- Write a descriptive comment before every function you want Copilot to complete
- Comment the expected inputs, outputs, and behaviour before the function signature
- Accept suggestions selectively - Tab for line, Escape to reject

## **Ollama - Debug and Refactor**

| \# Error explanation                                                            |
| ------------------------------------------------------------------------------- |
| 'I am in Godot 4 GDScript. Error: \[paste error\]. Script: \[paste script\].    |
| Explain the cause and fix only the broken section.'                             |
|                                                                                 |
| \# Refactor                                                                     |
| 'Refactor this GDScript to use a state machine enum. Keep external              |
| behaviour identical. Add brief comments on non-obvious logic.'                  |
|                                                                                 |
| \# New system                                                                   |
| 'Build a \[system name\] GDScript autoload with interface: \[describe in/out\]. |
| Typed variables. No UI code. Emit signals on key state changes.'                |
|                                                                                 |

## **ChatGPT / Claude - Architecture and Content**

| \# Core loop pressure test                                                 |
| -------------------------------------------------------------------------- |
| 'Evaluate my core loop for: narrowness, complexity risk, and biggest       |
| assumption. Be direct.'                                                    |
|                                                                            |
| \# Level progression                                                       |
| 'Generate a 5-level progression for my loop: \[describe\]. Per level:      |
| mechanic tested, new twist, player failure mode, emotional arc.'           |
|                                                                            |
| \# Branching dialogue                                                      |
| 'Write a conversation between \[A\] and \[B\]. Context: \[1-2 sentences\]. |
| Tone: \[tone\]. Three player choices leading to different outcomes.        |
| Lines under 20 words. Leave it at a decision point.'                       |
|                                                                            |
| \# Export instructions                                                     |
| 'Step-by-step Godot 4 export for \[platform\] from Apple Silicon Mac.'     |
|                                                                            |

# **Appendix C - Studio Build Alignment Checklist**

This checklist translates the guidance in this document into decisions for the Studio build itself. Its purpose is to separate process advice you should adopt immediately from architecture work that still needs to be designed and implemented in the Studio.

## **Use This Checklist in Three Buckets**

- Adopt now: guidance that directly improves the current build with little or no redesign.
- Adapt for Studio: guidance that is useful, but must be reshaped for an AI-to-Godot pipeline.
- Defer or ignore for v1: guidance that adds complexity before the foundation is stable.

## **Adopt Now**

- [ ] Keep Godot as the engine for the first Studio generation target.
- [ ] Keep GDScript as the implementation language for the first working slice.
- [ ] Keep the single-machine workflow as the default operating mode.
- [ ] Separate heavy AI generation sessions from active Godot testing sessions.
- [ ] Use a Prompt Log in the repository and update it during every useful AI interaction.
- [ ] Use a locked asset naming convention and stable folder structure before importing more assets.
- [ ] Build only one thin vertical slice before expanding scope.
- [ ] Add smoke tests after each major generation step instead of waiting for full integration.
- [ ] Prefer pre-generated AI outputs for v1 rather than runtime AI calls.
- [ ] Define a strict v1 not-list so the Studio does not drift into new systems too early.

## **Adapt for Studio**

- [ ] Convert "core loop" into a "core generation loop" for the Studio.
- [ ] Define the smallest complete Studio loop as: prompt in, structured scene spec out, Godot scene assembled, scene validated.
- [ ] Treat AI as a planner that emits semantic intent, not engine-ready tile IDs or node paths.
- [ ] Build an asset registry that maps semantic labels to concrete Godot resources.
- [ ] Build a translation layer that converts scene intent into deterministic Godot operations.
- [ ] Represent generated scenes as structured data files such as JSON, not freeform prose.
- [ ] Add validation rules that reject incomplete or contradictory scene specs before assembly.
- [ ] Keep visual style lock principles, but apply them to reusable asset packs and scene themes.
- [ ] Use AI for progression, composition ideas, and high-level layout intent, but keep exact placement rule-driven.
- [ ] Reframe prompt logging to capture not just prompts, but also output schemas, failures, and repair patterns.

## **Defer or Ignore for V1**

- [ ] Defer real-time runtime AI inside the game or editor until the offline pipeline is stable.
- [ ] Defer broad content generation at scale until one scene type assembles correctly every time.
- [ ] Defer multi-agent orchestration unless a single orchestrated planner clearly fails a validated use case.
- [ ] Defer low-value polish work such as advanced menus, presentation layers, or decorative UI in the Studio itself.
- [ ] Ignore any workflow that requires the AI to choose exact assets blindly from raw project paths.
- [ ] Ignore any approach that lets the model directly mutate complex Godot scenes without an intermediate spec.
- [ ] Ignore large architectural pivots unless a smoke test proves the current approach cannot meet the goal.

## **Direct Similarities to Keep**

- [ ] AI should be used with defined roles, not as an unbounded generator.
- [ ] Reproducibility matters more than novelty in early builds.
- [ ] Testing immediately after each change is mandatory.
- [ ] Scope discipline is a technical requirement, not just a productivity preference.
- [ ] Deterministic outputs are more valuable than flexible outputs in the first version.

## **Direct Differences to Keep in View**

- [ ] This document describes a solo development workflow, not the full Studio architecture.
- [ ] This document assumes AI mainly assists development, while the Studio requires AI to drive structured content generation.
- [ ] This document does not define how semantic intent becomes Godot scenes.
- [ ] This document does not define the asset registry, scene schema, or validation pipeline the Studio needs.
- [ ] This document improves process discipline, but it does not remove the need for an explicit generation architecture.

## **Decision Checkpoint**

If the answer to all of the questions below is yes, this document is supplementing the build rather than changing it:

- [ ] Does the current plan still center on a semantic scene spec?
- [ ] Does the current plan still require a translation layer between AI output and Godot resources?
- [ ] Does the current plan still avoid runtime AI dependency for v1?
- [ ] Does the current plan still target a small validated vertical slice first?
- [ ] Does this document mainly improve discipline, naming, logging, and testing rather than changing the core architecture?

If any answer is no, review the architecture before implementing further systems.

# **Conclusion**

This system transforms AI from a collection of independent tools into a cohesive development pipeline with defined roles, reproducible outputs, and compounding knowledge. The Prompt Log, the Style Lock, the asset structure, and the hardware separation are not optional enhancements - they are the infrastructure that makes everything else reliable.

The path from core loop to shippable game is the same for every project: build the smallest thing that works, test it, identify the most limiting problem, fix only that, repeat. AI accelerates every part of that loop. Your discipline determines whether the acceleration is pointed in the right direction.

The goal of the first project is not a perfect game. It is a complete one - a game that starts, plays through, and ends, and that taught you the pipeline. Every subsequent project benefits from that foundation.

**_Build small. Test immediately. Iterate without mercy._**