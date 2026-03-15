# Model Deployment Profiles V1

Date: 2026-03-15
Status: Working recommendation
Depends on:
- docs/SCENE_ASSEMBLY_PLAN_V1.md

## 1) Purpose

Define practical model-routing profiles for development and lower-power deployment targets without changing the role contract.

## 2) Core rule

Keep logical roles fixed:
- Director
- Architect
- Programmer
- QA

Allow physical model assignment to vary by hardware profile.

## 3) Why this matters

The product depends on role separation more than separate heavyweight models living in memory at the same time.

That means:
- prompts stay specialized
- contracts stay specialized
- model instances may be consolidated on weaker hardware

## 4) Development profile: M4

Recommended use:
- feature development
- prompt tuning
- schema and assembler bring-up

Suggested routing:
- Director -> smaller general model
- Architect -> stronger coding model
- Programmer -> stronger coding model
- QA -> smaller general model

Recommended behavior:
- serial execution is fine
- fallback models remain enabled
- collect latency and failure telemetry for each stage

## 5) Deployment profile: M1 16 GB

Recommended use:
- local packaged studio
- stable V1 archetype runs

Suggested routing:
- Director -> shared primary model or smaller general model
- Architect -> shared primary coding-capable model
- Programmer -> same shared primary coding-capable model
- QA -> same shared model reused serially or smaller checker model

Recommended behavior:
- one model loaded at a time when possible
- reduce `num_predict` where safe
- keep deterministic options unchanged
- prioritize reliability over theoretical specialization

## 6) Recommended operational policy

### M4 policy

- keep current split during development if it improves outputs
- benchmark per-stage latency and retry rates
- use this profile to tune prompts and schema boundaries

### M1 policy

- collapse Architect + Programmer to one shared model first
- only keep a smaller separate QA model if it provides a measurable gain
- avoid concurrent heavyweight model residency

## 7) Decision framework

Choose one shared primary model if these are true:
- memory pressure is visible
- stage outputs are already contract-limited
- retries increase due to model swapping or load failures

Keep separate models only if both are true:
- quality difference is real and measured
- the hardware can sustain the footprint comfortably

## 8) V1 recommendation

Recommended default for product direction:
- preserve four roles
- preserve role-specific prompts
- design runtime so one primary model can serve multiple roles serially

This avoids future re-architecture when moving from stronger development hardware to weaker deployment hardware.

## 9) Benchmark checklist

Collect for both M4 and M1:
- total run duration
- per-stage duration
- retries per stage
- fallback usage
- parse failure count
- validation failure count
- peak memory pressure

Do not change the architecture based on feel. Change it only on measured reliability and runtime data.