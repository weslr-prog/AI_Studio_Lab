# AI_STUDIO_LAB

## Overview
Local multi-agent AI orchestration framework using Ollama and Godot.

## Environment
- MacBook Air M-series
- 8GB RAM
- Python 3.11
- Ollama local models
- Godot 4.x
- VSCode + Copilot Chat GPT-5.x

## Agents
- Director → planning
- Architect → structure & design
- Programmer → implementation

## Core Constraints
- Local inference only
- Deterministic outputs
- Strict JSON responses
- Ledger validation required
- Defensive parsing required

## Documentation Sources
- Godot 4.2 offline docs path: `docs/godot/4.2/`

## Models
Primary:
- qwen2.5-coder:14bplease

Fallback:
- qwen2.5:14b
- deepseek-r1:14b

## System Goals
- Autonomous game project generation
- Structured Godot project creation
- Expandable architecture
- Stable multi-agent orchestration

## User Experience Backlog (Requested)
- Add low-technical operator flow (guided objective wizard and plain-language prompts)
- Add clean GUI dashboard for run status, gates, artifacts, and next actions
- Support operation outside VS Code via packaged standalone desktop app
- Add objective templates by genre (platformer, top-down, arcade, puzzle)
- Keep supplemental design-research corpora optional and measured to avoid retrieval noise
