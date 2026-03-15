# AI_STUDIO_LAB

Local multi-agent game studio orchestration for Godot with deterministic JSON contracts, ledger-gated planning, and validation-first execution.

## What it does

- Runs a role-based pipeline: Director -> Architect -> Programmer -> QA
- Uses strict contract and invariant checks for deterministic outputs
- Generates Godot project artifacts in sandbox scope
- Supports scene payload generation (`Asset Registry` + `Scene Spec`)
- Compiles scenes headlessly in Godot via a scene assembler script

## Current V1 direction

The project is currently focused on `topdown_adventure_v1` and a stable scene assembly pipeline:

1. Discover assets
2. Build `Asset Registry` payload
3. Build `Scene Spec` payload
4. Run Godot headless assembler
5. Validate artifacts and acceptance gates

Design docs:

- `docs/SCENE_ASSEMBLY_PLAN_V1.md`
- `docs/SCENE_SPEC_AND_ASSET_REGISTRY_V1.md`
- `docs/GODOT_HEADLESS_ASSEMBLER_V1.md`
- `docs/MODEL_DEPLOYMENT_PROFILES_V1.md`

## Quick start

### 1) Initialize and inspect

```bash
python runner.py init
python runner.py scan
python runner.py validate
```

### 2) Generate scene payloads

```bash
python runner.py scene-spec --project-name sandbox_project
```

This writes:

- `projects/sandbox_project/.studio/asset_registry.json`
- `projects/sandbox_project/.studio/scene_spec.json`

### 3) Assemble scene headlessly in Godot

```bash
godot --headless --path projects/sandbox_project --script tools/scene_assembler.gd --scene-spec .studio/scene_spec.json --asset-registry .studio/asset_registry.json
```

Assembler output report:

- `projects/sandbox_project/.studio/assembly_result.json`

### 4) Run orchestration

```bash
python runner.py orchestrate
python runner.py run-report
```

## Notes

- The project is local-first and optimized for constrained hardware.
- Keep writes inside `projects/sandbox_project/` for contract compatibility.
- Prefer deterministic behavior (`temperature=0`, fixed seed, strict schema checks).
