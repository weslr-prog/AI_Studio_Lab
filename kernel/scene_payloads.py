from typing import Any


_SANDBOX_PREFIX = "projects/sandbox_project/"
_ASSET_KINDS = {"texture", "scene", "audio", "font", "script", "unknown"}
_TERRAIN_REPRESENTATIONS = {"tilemap", "sprite_fallback"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _is_sandbox_path(path: str) -> bool:
    return str(path).startswith(_SANDBOX_PREFIX)


def validate_asset_registry_payload(payload: dict[str, Any]) -> None:
    _require(isinstance(payload, dict), "asset registry payload must be object")
    _require(int(payload.get("registry_version", 0)) == 1, "asset registry version must be 1")
    _require(str(payload.get("project_root", "")) == "projects/sandbox_project", "asset registry project_root must be sandbox")

    assets = payload.get("assets")
    _require(isinstance(assets, list), "asset registry assets must be list")
    seen_ids: set[str] = set()
    for entry in assets:
        _require(isinstance(entry, dict), "asset registry asset entry must be object")
        asset_id = str(entry.get("asset_id", "")).strip()
        _require(bool(asset_id), "asset registry asset_id is required")
        _require(asset_id not in seen_ids, f"duplicate asset_id: {asset_id}")
        seen_ids.add(asset_id)

        path = str(entry.get("path", "")).strip()
        _require(_is_sandbox_path(path), "asset path must remain in sandbox")

        kind = str(entry.get("kind", "")).strip()
        _require(kind in _ASSET_KINDS, "asset kind is invalid")

        role_candidates = entry.get("role_candidates")
        _require(isinstance(role_candidates, list), "role_candidates must be list")
        _require(all(isinstance(item, str) and item.strip() for item in role_candidates), "role_candidates must contain non-empty strings")

        confidence = float(entry.get("confidence", 0.0))
        _require(0.0 <= confidence <= 1.0, "asset confidence must be between 0.0 and 1.0")

    role_bindings = payload.get("role_bindings")
    _require(isinstance(role_bindings, dict), "asset registry role_bindings must be object")
    for _role, raw_value in role_bindings.items():
        if isinstance(raw_value, str):
            _require(raw_value in seen_ids, f"role binding references unknown asset_id: {raw_value}")
            continue
        _require(isinstance(raw_value, list), "role binding must be string or list")
        for item in raw_value:
            _require(isinstance(item, str) and item in seen_ids, "role binding list references unknown asset_id")


def validate_scene_spec_payload(payload: dict[str, Any]) -> None:
    _require(isinstance(payload, dict), "scene spec payload must be object")
    _require(int(payload.get("scene_spec_version", 0)) == 1, "scene spec version must be 1")
    _require(str(payload.get("archetype_id", "")).strip() != "", "scene spec archetype_id is required")

    scene_path = str(payload.get("scene_path", "")).strip()
    _require(_is_sandbox_path(scene_path), "scene spec scene_path must remain in sandbox")

    terrain = payload.get("terrain")
    _require(isinstance(terrain, dict), "scene spec terrain must be object")
    representation = str(terrain.get("representation", "")).strip()
    _require(representation in _TERRAIN_REPRESENTATIONS, "scene terrain representation is invalid")

    nodes = payload.get("nodes")
    _require(isinstance(nodes, list), "scene spec nodes must be list")
    required_node_ids = {"Main", "Ground", "Player", "Enemy", "NPC", "UI", "HealthLabel"}
    present_node_ids: set[str] = set()
    for node in nodes:
        _require(isinstance(node, dict), "scene node entry must be object")
        node_id = str(node.get("node_id", "")).strip()
        _require(bool(node_id), "scene node_id is required")
        present_node_ids.add(node_id)
        if node.get("script_path") is not None:
            script_path = str(node.get("script_path", "")).strip()
            _require(_is_sandbox_path(script_path), "scene node script_path must remain in sandbox")

    missing_nodes = sorted(required_node_ids - present_node_ids)
    _require(not missing_nodes, f"scene spec missing required nodes: {', '.join(missing_nodes)}")

    spawns = payload.get("spawns")
    _require(isinstance(spawns, dict), "scene spec spawns must be object")
    for actor in ("player", "enemy", "npc"):
        coords = spawns.get(actor)
        _require(isinstance(coords, list) and len(coords) == 2, f"scene spec spawn '{actor}' must be [x, y]")
        _require(all(isinstance(item, (int, float)) for item in coords), f"scene spec spawn '{actor}' coordinates must be numbers")
