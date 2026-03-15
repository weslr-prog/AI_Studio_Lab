from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import struct
from typing import Any

from kernel.config import load_kernel_config
from kernel.contracts import TaskExecutionContract
from kernel.db import InvariantViolationRecord, KernelDB, SQLiteConnectionManager
from kernel.docs_retriever import retrieve_docs_context
from kernel.ledger import DecisionLedger
from kernel.llm_utils import extract_json_from_response
from kernel.model_gateway import ModelGateway
from kernel.structure import ProjectStructureAnalyzer


@dataclass(frozen=True)
class ArchitectureProposal:
    task_id: int
    problem: str
    context: str
    options: str
    chosen: str
    tradeoffs: str
    risks: str
    confidence: float
    agent: str
    timestamp: str


class ArchitectAgent:
    AGENT_NAME = "architect"
    MODEL_NAME = "qwen2.5-coder:14b"
    PROMPT_TEMPLATE = (
        "You are ArchitectAgent for AI_STUDIO_LAB.\n"
        "Return ONLY valid JSON. No explanation. No markdown. No commentary.\n"
        "Schema:\n"
        "{{\n"
        '  "ledger_entry": {{\n'
        '    "problem": "string",\n'
        '    "context": "string",\n'
        '    "options": "string",\n'
        '    "chosen": "string",\n'
        '    "tradeoffs": "string",\n'
        '    "risks": "string",\n'
        '    "confidence": 0.0\n'
        "  }},\n"
        '  "rationale": "string",\n'
        '  "module_plan": ["string"]\n'
        "}}\n"
        "Task:\n{task_payload}\n\n"
        "Structure report:\n{structure_report}\n"
            "Godot docs context:\n{docs_context}\n"
    )

    def __init__(self, db: KernelDB | None = None):
        self._db = db or KernelDB()
        self._gateway = ModelGateway()
        self.MODEL_NAME = self._gateway.model_for(self.AGENT_NAME)
        self._ledger = DecisionLedger(db=self._db)
        self._analyzer = ProjectStructureAnalyzer()
        self._logger = logging.getLogger("agents.architect")
        self._logger.setLevel(logging.INFO)
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.propagate = False

    def _log(self, event: str, payload: dict[str, Any]) -> None:
        data = {"event": event, **payload}
        self._logger.info(json.dumps(data, ensure_ascii=True, sort_keys=True))

    def _record_exception(self, message: str) -> None:
        try:
            self._db.initialize()
            invariant_id = self._db.get_invariant_id("check_evolution_engine_exception")
            if invariant_id is None:
                return
            self._db.record_invariant_violation(
                InvariantViolationRecord(
                    invariant_id=invariant_id,
                    file="agents/architect_agent.py",
                    description=message,
                    severity=3,
                    timestamp=datetime.now(UTC).isoformat(),
                )
            )
        except Exception:
            return

    def _validate_schema(self, payload: dict[str, Any]) -> None:
        if "ledger_entry" not in payload or "rationale" not in payload or "module_plan" not in payload:
            raise ValueError("Missing required architecture response fields")
        ledger_entry = payload["ledger_entry"]
        if not isinstance(ledger_entry, dict):
            raise ValueError("ledger_entry must be object")

        required_ledger = [
            "problem",
            "context",
            "options",
            "chosen",
            "tradeoffs",
            "risks",
            "confidence",
        ]
        for key in required_ledger:
            if key not in ledger_entry:
                raise ValueError(f"ledger_entry missing field: {key}")

        if not isinstance(payload["rationale"], str):
            raise ValueError("rationale must be string")
        if not isinstance(payload["module_plan"], list):
            raise ValueError("module_plan must be list")

        confidence = float(ledger_entry["confidence"])
        if confidence < 0.0 or confidence > 1.0:
            raise ValueError("ledger_entry confidence must be between 0.0 and 1.0")

    def _call_ollama_json(self, prompt: str) -> dict[str, Any]:
        generation = self._gateway.generate_json(agent_name=self.AGENT_NAME, prompt=prompt)
        if generation.get("status") == "error":
            return generation

        payload = extract_json_from_response(str(generation["response"]))
        if payload.get("status") == "error":
            return payload
        self._validate_schema(payload)
        return payload

    @staticmethod
    def _format_docs_context(docs_payload: dict[str, Any]) -> str:
        snippets = docs_payload.get("snippets", [])
        if not snippets:
            return "No matching local docs snippets found."
        lines: list[str] = []
        for item in snippets:
            lines.append(f"- {item['path']} | {item['title']}")
            lines.append(f"  {item['excerpt'][:240]}")
        return "\n".join(lines)

    def propose_architecture(self, task_id: int) -> dict[str, Any]:
        self._db.initialize()
        try:
            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()
                task_row = cursor.execute(
                    "SELECT id, description FROM tasks WHERE id = ? LIMIT 1",
                    (task_id,),
                ).fetchone()
                if task_row is None:
                    raise ValueError(f"Task not found: {task_id}")

                task_payload = {
                    "id": int(task_row["id"]),
                    "description": str(task_row["description"]),
                }

            project_root = Path(__file__).resolve().parent.parent
            structure_report = self._analyzer.generate_structure_report(project_root)
            docs_payload = retrieve_docs_context(
                query=str(task_payload["description"]),
                version="4.2",
                max_results=3,
            )
            prompt = self.PROMPT_TEMPLATE.format(
                task_payload=json.dumps(task_payload, ensure_ascii=True, sort_keys=True),
                structure_report=json.dumps(structure_report, ensure_ascii=True, sort_keys=True),
                docs_context=self._format_docs_context(docs_payload),
            )

            model_output = self._call_ollama_json(prompt)
            if model_output.get("status") == "error":
                return model_output
            ledger_entry = model_output["ledger_entry"]
            proposal = ArchitectureProposal(
                task_id=task_id,
                problem=str(ledger_entry["problem"]),
                context=str(ledger_entry["context"]),
                options=str(ledger_entry["options"]),
                chosen=str(ledger_entry["chosen"]),
                tradeoffs=str(ledger_entry["tradeoffs"]),
                risks=str(ledger_entry["risks"]),
                confidence=float(ledger_entry["confidence"]),
                agent="architect_agent",
                timestamp=datetime.now(UTC).isoformat(),
            )

            with SQLiteConnectionManager(self._db.db_path) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO architectural_decisions (
                        problem,
                        context,
                        options,
                        chosen,
                        tradeoffs,
                        risks,
                        confidence,
                        agent,
                        timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        proposal.problem,
                        proposal.context,
                        proposal.options,
                        proposal.chosen,
                        proposal.tradeoffs,
                        proposal.risks,
                        proposal.confidence,
                        proposal.agent,
                        proposal.timestamp,
                    ),
                )

            result = {
                "model": self.MODEL_NAME,
                "task_id": proposal.task_id,
                "ledger_entry": {
                    "problem": proposal.problem,
                    "context": proposal.context,
                    "options": proposal.options,
                    "chosen": proposal.chosen,
                    "tradeoffs": proposal.tradeoffs,
                    "risks": proposal.risks,
                    "confidence": proposal.confidence,
                },
                "rationale": str(model_output["rationale"]),
                "module_plan": list(model_output["module_plan"]),
                "docs_sources": [
                    {
                        "path": str(item["path"]),
                        "title": str(item["title"]),
                    }
                    for item in docs_payload.get("snippets", [])
                ],
            }
            self._log("architecture_proposed", result)
            return result
        except Exception as exc:
            self._record_exception(f"propose_architecture exception: {exc}")
            raise

    def review_structure(self, project_path: Path) -> dict[str, Any]:
        self._db.initialize()
        try:
            report = self._analyzer.generate_structure_report(project_path)
            self._log(
                "structure_reviewed",
                {
                    "total_files": int(report["total_files"]),
                    "circular_dependencies": len(report["circular_dependencies"]),
                    "large_files": len(report["large_files"]),
                },
            )
            return report
        except Exception as exc:
            self._record_exception(f"review_structure exception: {exc}")
            return {
                "total_files": 0,
                "large_files": [],
                "circular_dependencies": [],
                "dependency_graph_size": 0,
            }

    def submit_ledger_entry(
        self,
        problem: str,
        context: str,
        options: str,
        chosen: str,
        tradeoffs: str,
        risks: str,
        confidence: float,
        agent: str,
    ) -> int:
        self._db.initialize()
        try:
            decision_id = self._ledger.add_decision(
                problem=problem,
                context=context,
                options=options,
                chosen=chosen,
                tradeoffs=tradeoffs,
                risks=risks,
                confidence=confidence,
                agent=agent,
            )
            self._log("ledger_entry_submitted", {"decision_id": decision_id, "agent": agent})
            return decision_id
        except Exception as exc:
            self._record_exception(f"submit_ledger_entry exception: {exc}")
            raise

    @staticmethod
    def _required_main_scene_label_text(contract_payload: dict[str, Any]) -> str | None:
        objective_spec = contract_payload.get("objective_spec")
        if not isinstance(objective_spec, dict):
            return None

        acceptance = objective_spec.get("acceptance")
        if not isinstance(acceptance, dict):
            return None

        checks = acceptance.get("checks")
        if not isinstance(checks, list):
            return None

        prefix = "Main scene contains Label text "
        for check in checks:
            text = str(check)
            if text.startswith(prefix):
                label_text = text[len(prefix) :].strip()
                if label_text:
                    return label_text
        return None

    @staticmethod
    def _requires_topdown_combat_scene(contract_payload: dict[str, Any]) -> bool:
        objective_spec = contract_payload.get("objective_spec")
        if not isinstance(objective_spec, dict):
            return False
        objective = str(objective_spec.get("objective", "")).lower()
        topdown = "top-down" in objective or "top down" in objective
        enemy = "enemy" in objective or "combat" in objective or "attack" in objective
        npc = "npc" in objective
        adventure = "adventure" in objective or "explore" in objective or "exploration" in objective
        terrain = "tilemap" in objective or "terrain" in objective or "ground" in objective
        spawn = "spawn" in objective
        return topdown and (enemy or npc or adventure or terrain or spawn)

    @staticmethod
    def _build_default_scene_lines(label_text: str | None) -> list[str]:
        scene_lines = [
            "[gd_scene format=3]",
            "",
            "[node name=\"Main\" type=\"Node2D\"]",
            "",
            "[node name=\"Player\" type=\"CharacterBody2D\" parent=\".\"]",
            "",
        ]
        if label_text is not None:
            escaped = label_text.replace('"', '\\"')
            scene_lines.extend(
                [
                    "[node name=\"Label\" type=\"Label\" parent=\".\"]",
                    f'text = "{escaped}"',
                    "",
                ]
            )
        return scene_lines

    @staticmethod
    def _discover_texture_assignments(project_root: Path) -> dict[str, str]:
        assets_root = project_root / "projects" / "sandbox_project" / "assets"
        if not assets_root.exists() or not assets_root.is_dir():
            return {}

        all_pngs = sorted(path for path in assets_root.rglob("*.png") if path.is_file())
        if not all_pngs:
            return {}

        relative_paths = [
            path.relative_to(project_root / "projects" / "sandbox_project").as_posix()
            for path in all_pngs
        ]

        def _pick(tokens: tuple[str, ...], fallback_index: int) -> str:
            for token in tokens:
                for candidate in relative_paths:
                    if token in candidate.lower():
                        return candidate
            index = min(max(0, fallback_index), len(relative_paths) - 1)
            return relative_paths[index]

        return {
            "player": _pick(("player", "character", "hero"), 0),
            "enemy": _pick(("enemy", "monster", "slime", "foe", "npc_", "character"), min(1, len(relative_paths) - 1)),
            "npc": _pick(("npc", "villager", "citizen", "character"), min(2, len(relative_paths) - 1)),
            "ground": _pick(("tile", "tileset", "ground", "map"), min(3, len(relative_paths) - 1)),
        }

    @staticmethod
    def _png_dimensions(path: Path) -> tuple[int, int] | None:
        try:
            with path.open("rb") as handle:
                signature = handle.read(8)
                if signature != b"\x89PNG\r\n\x1a\n":
                    return None
                ihdr_length = handle.read(4)
                ihdr_type = handle.read(4)
                if len(ihdr_length) != 4 or ihdr_type != b"IHDR":
                    return None
                ihdr_data = handle.read(13)
                if len(ihdr_data) != 13:
                    return None
                width, height = struct.unpack(">II", ihdr_data[:8])
                return int(width), int(height)
        except Exception:
            return None

    @staticmethod
    def _infer_sprite_sheet_grid(width: int, height: int) -> tuple[int, int] | None:
        if width <= 0 or height <= 0:
            return None
        if width < 96 and height < 96:
            return None

        best: tuple[int, int] | None = None
        best_score: float = -1.0
        common_sizes = (16, 24, 32, 48, 64, 96)
        for columns in range(1, 13):
            if width % columns != 0:
                continue
            frame_width = width // columns
            for rows in range(1, 13):
                if height % rows != 0:
                    continue
                frame_height = height // rows
                if frame_width < 16 or frame_height < 16:
                    continue
                if frame_width > 256 or frame_height > 256:
                    continue
                frame_count = columns * rows
                if frame_count < 4:
                    continue

                closest = min(abs(frame_width - size) + abs(frame_height - size) for size in common_sizes)
                size_score = max(0.0, 60.0 - float(closest))

                square_penalty = abs(frame_width - frame_height) * 0.35
                count_penalty = max(0, frame_count - 48) * 1.5
                tiny_frame_penalty = 8.0 if min(frame_width, frame_height) < 24 else 0.0
                score = size_score - square_penalty - count_penalty - tiny_frame_penalty

                if columns in (3, 4, 6, 8):
                    score += 4.0
                if rows in (3, 4, 6, 8, 9):
                    score += 4.0

                if score > best_score:
                    best_score = score
                    best = (columns, rows)
        if best_score < 18.0:
            return None
        return best

    @staticmethod
    def _infer_tileset_grid(width: int, height: int) -> tuple[int, int] | None:
        if width <= 0 or height <= 0:
            return None

        candidate_sizes = (16, 24, 32, 48, 64)
        best: tuple[int, int] | None = None
        best_score: float = -1.0
        for tile_size in candidate_sizes:
            if width % tile_size != 0 or height % tile_size != 0:
                continue
            columns = width // tile_size
            rows = height // tile_size
            if columns < 4 or rows < 4:
                continue
            tile_count = columns * rows
            if tile_count < 32:
                continue

            count_score = min(120.0, float(tile_count) * 1.2)
            size_bonus = 14.0 if tile_size in (16, 32) else 8.0
            squareness_penalty = abs(columns - rows) * 0.35
            score = count_score + size_bonus - squareness_penalty
            if score > best_score:
                best_score = score
                best = (columns, rows)
        return best

    @classmethod
    def _sprite_usage_settings(cls, project_root: Path, relative_asset_path: str | None) -> dict[str, Any]:
        if not relative_asset_path:
            return {"path": None, "kind": "none"}

        absolute_path = project_root / "projects" / "sandbox_project" / relative_asset_path
        dimensions = cls._png_dimensions(absolute_path)
        if dimensions is None:
            return {
                "path": relative_asset_path,
                "kind": "single",
                "scale": 1.0,
            }

        width, height = dimensions
        lower_path = str(relative_asset_path).lower()
        if any(token in lower_path for token in ("tile", "tileset", "terrain", "ground", "map")):
            tile_grid = cls._infer_tileset_grid(width, height)
            if tile_grid is not None:
                columns, rows = tile_grid
                return {
                    "path": relative_asset_path,
                    "kind": "tileset",
                    "hframes": columns,
                    "vframes": rows,
                    "frame": 0,
                    "scale": 1.0,
                }

        grid = cls._infer_sprite_sheet_grid(width, height)
        if grid is not None:
            columns, rows = grid
            frame_width = max(1, width // columns)
            frame_height = max(1, height // rows)
            scale = 1.0
            if frame_height <= 24 or frame_width <= 24:
                scale = 3.0
            elif frame_height <= 32 or frame_width <= 32:
                scale = 2.4
            elif frame_height <= 48 or frame_width <= 48:
                scale = 1.8
            elif frame_height > 96:
                scale = 0.7
            elif frame_height > 64:
                scale = 0.85
            return {
                "path": relative_asset_path,
                "kind": "spritesheet",
                "hframes": columns,
                "vframes": rows,
                "frame": 0,
                "scale": scale,
            }

        scale = 1.0
        if max(width, height) <= 24:
            scale = 3.0
        elif max(width, height) <= 32:
            scale = 2.4
        elif max(width, height) <= 48:
            scale = 1.8
        elif max(width, height) > 256:
            scale = 0.6
        elif max(width, height) > 128:
            scale = 0.8
        return {
            "path": relative_asset_path,
            "kind": "single",
            "scale": scale,
        }

    @staticmethod
    def _build_topdown_scene_lines(label_text: str | None, textures: dict[str, dict[str, Any]]) -> list[str]:
        player_tex = textures.get("player") or {"path": None}
        enemy_tex = textures.get("enemy") or {"path": None}
        npc_tex = textures.get("npc") or {"path": None}
        ground_tex = textures.get("ground") or {"path": None}

        ext_resources: list[str] = [
            '[ext_resource type="Script" path="res://scripts/player.gd" id="1"]',
        ]
        next_id = 2

        def _add_texture(path: str | None) -> str | None:
            nonlocal next_id
            if not path:
                return None
            resource_id = str(next_id)
            next_id += 1
            ext_resources.append(f'[ext_resource type="Texture2D" path="res://{path}" id="{resource_id}"]')
            return resource_id

        player_tex_id = _add_texture(player_tex.get("path"))
        enemy_tex_id = _add_texture(enemy_tex.get("path"))
        npc_tex_id = _add_texture(npc_tex.get("path"))
        ground_tex_id = _add_texture(ground_tex.get("path"))

        def _sprite_lines(texture_id: str | None, texture_info: dict[str, Any], fallback_modulate: str) -> list[str]:
            if texture_id is None:
                return [fallback_modulate]
            lines: list[str] = [f'texture = ExtResource("{texture_id}")']
            scale = float(texture_info.get("scale", 1.0))
            if abs(scale - 1.0) > 0.001:
                lines.append(f"scale = Vector2({scale}, {scale})")
            if texture_info.get("kind") == "spritesheet":
                lines.append(f"hframes = {int(texture_info.get('hframes', 1))}")
                lines.append(f"vframes = {int(texture_info.get('vframes', 1))}")
                lines.append(f"frame = {int(texture_info.get('frame', 0))}")
            return lines

        scene_lines = [
            "[gd_scene format=3]",
            "",
            *ext_resources,
            "",
            "[sub_resource type=\"RectangleShape2D\" id=\"RectangleShape2D_player\"]",
            "size = Vector2(20, 20)",
            "",
            "[sub_resource type=\"RectangleShape2D\" id=\"RectangleShape2D_enemy\"]",
            "size = Vector2(20, 20)",
            "",
            "[node name=\"Main\" type=\"Node2D\"]",
            "",
            "[node name=\"TileMapRoot\" type=\"Node2D\" parent=\".\"]",
            "",
            "[node name=\"Ground\" type=\"Polygon2D\" parent=\"TileMapRoot\"]",
            "polygon = PackedVector2Array(-640, -360, 640, -360, 640, 360, -640, 360)",
            "color = Color(0.14, 0.18, 0.14, 1)",
            "",
            "[node name=\"GroundSprite\" type=\"Sprite2D\" parent=\"TileMapRoot\"]",
            "position = Vector2(320, 180)",
            "scale = Vector2(1, 1)",
            "centered = false",
            *(
                [
                    f"hframes = {int(ground_tex.get('hframes', 1))}",
                    f"vframes = {int(ground_tex.get('vframes', 1))}",
                    f"frame = {int(ground_tex.get('frame', 0))}",
                ]
                if str(ground_tex.get("kind", "")) in {"spritesheet", "tileset"}
                else []
            ),
            *( [f'texture = ExtResource("{ground_tex_id}")'] if ground_tex_id is not None else [] ),
            "",
            "[node name=\"HUD\" type=\"CanvasLayer\" parent=\".\"]",
            "",
            "[node name=\"HealthLabel\" type=\"Label\" parent=\"HUD\"]",
            "offset_left = 16.0",
            "offset_top = 12.0",
            "text = \"Health: 100\"",
            "",
            "[node name=\"Player\" type=\"CharacterBody2D\" parent=\".\"]",
            "position = Vector2(96, 96)",
            'script = ExtResource("1")',
            "",
            "[node name=\"CollisionShape2D\" type=\"CollisionShape2D\" parent=\"Player\"]",
            "shape = SubResource(\"RectangleShape2D_player\")",
            "",
            "[node name=\"Visual\" type=\"Sprite2D\" parent=\"Player\"]",
            *(_sprite_lines(player_tex_id, player_tex, "modulate = Color(0.22, 0.74, 1, 1)")),
            "",
            "[node name=\"Enemy\" type=\"CharacterBody2D\" parent=\".\"]",
            "position = Vector2(380, 220)",
            "",
            "[node name=\"CollisionShape2D\" type=\"CollisionShape2D\" parent=\"Enemy\"]",
            "shape = SubResource(\"RectangleShape2D_enemy\")",
            "",
            "[node name=\"Visual\" type=\"Sprite2D\" parent=\"Enemy\"]",
            *(_sprite_lines(enemy_tex_id, enemy_tex, "modulate = Color(0.95, 0.2, 0.2, 1)")),
            "",
            "[node name=\"NPCs\" type=\"Node2D\" parent=\".\"]",
            "",
            "[node name=\"NPC_A\" type=\"Node2D\" parent=\"NPCs\"]",
            "position = Vector2(180, 280)",
            "",
            "[node name=\"Visual\" type=\"Sprite2D\" parent=\"NPCs/NPC_A\"]",
            *(_sprite_lines(npc_tex_id, npc_tex, "modulate = Color(0.95, 0.9, 0.25, 1)")),
            "",
            "[node name=\"Label\" type=\"Label\" parent=\"NPCs/NPC_A\"]",
            "text = \"NPC A\"",
            "position = Vector2(-16, -26)",
            "",
            "[node name=\"NPC_B\" type=\"Node2D\" parent=\"NPCs\"]",
            "position = Vector2(480, 300)",
            "",
            "[node name=\"Visual\" type=\"Sprite2D\" parent=\"NPCs/NPC_B\"]",
            *(_sprite_lines(npc_tex_id, npc_tex, "modulate = Color(0.95, 0.9, 0.25, 1)")),
            "",
            "[node name=\"Label\" type=\"Label\" parent=\"NPCs/NPC_B\"]",
            "text = \"NPC B\"",
            "position = Vector2(-16, -26)",
            "",
            "[node name=\"NPC_C\" type=\"Node2D\" parent=\"NPCs\"]",
            "position = Vector2(320, 120)",
            "",
            "[node name=\"Visual\" type=\"Sprite2D\" parent=\"NPCs/NPC_C\"]",
            *(_sprite_lines(npc_tex_id, npc_tex, "modulate = Color(0.95, 0.9, 0.25, 1)")),
            "",
            "[node name=\"Label\" type=\"Label\" parent=\"NPCs/NPC_C\"]",
            "text = \"NPC C\"",
            "position = Vector2(-16, -26)",
            "",
        ]
        if label_text is not None:
            escaped = label_text.replace('"', '\\"')
            scene_lines.extend(
                [
                    "[node name=\"ObjectiveLabel\" type=\"Label\" parent=\"HUD\"]",
                    "offset_left = 16.0",
                    "offset_top = 34.0",
                    f'text = "{escaped}"',
                    "",
                ]
            )
        return scene_lines

    def implement_scene_contract(self, contract_payload: dict[str, Any]) -> dict[str, Any]:
        self._db.initialize()
        try:
            contract = TaskExecutionContract.from_dict(contract_payload)
            if contract.assigned_agent != "architect":
                raise ValueError("contract assigned_agent must be architect")

            if contract.ledger_required:
                if contract.decision_id is None:
                    raise ValueError("architect contract missing decision_id")
                if not self._ledger.validate_change(task_id=contract.task_id, decision_id=contract.decision_id):
                    raise ValueError("Ledger validation failed for implement_scene_contract")

            scene_target = "projects/sandbox_project/scenes/Main.tscn"
            for artifact in contract.required_artifacts:
                if artifact.endswith(".tscn"):
                    scene_target = artifact
                    break

            config = load_kernel_config()
            scene_path = (config.project_root / scene_target).resolve()
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            label_text = self._required_main_scene_label_text(contract_payload)
            texture_usage: dict[str, Any] = {}
            if self._requires_topdown_combat_scene(contract_payload):
                texture_assignments = self._discover_texture_assignments(config.project_root)
                texture_usage = {
                    key: self._sprite_usage_settings(config.project_root, value)
                    for key, value in texture_assignments.items()
                }
                scene_lines = self._build_topdown_scene_lines(label_text, texture_usage)
            else:
                scene_lines = self._build_default_scene_lines(label_text)
            scene_path.write_text("\n".join(scene_lines), encoding="utf-8")

            missing_artifacts = [
                item
                for item in contract.required_artifacts
                if not (config.project_root / item).exists()
            ]
            if missing_artifacts:
                return {
                    "agent": "architect",
                    "status": "error",
                    "message": "Missing required artifacts after scene implementation",
                    "task_id": contract.task_id,
                    "missing_artifacts": missing_artifacts,
                }

            result = {
                "status": "ok",
                "contract": contract.to_dict(),
                "written_file": scene_target,
                "texture_usage": texture_usage,
            }
            self._log("scene_implemented", result)
            return result
        except Exception as exc:
            self._record_exception(f"implement_scene_contract exception: {exc}")
            return {
                "agent": "architect",
                "status": "error",
                "message": str(exc),
            }
