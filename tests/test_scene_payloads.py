import unittest

from kernel.scene_payloads import validate_asset_registry_payload, validate_scene_spec_payload


class ScenePayloadValidationTests(unittest.TestCase):
    def test_validate_asset_registry_payload_accepts_valid_payload(self) -> None:
        payload = {
            "registry_version": 1,
            "project_root": "projects/sandbox_project",
            "archetype_id": "topdown_adventure_v1",
            "assets": [
                {
                    "asset_id": "asset_001_player",
                    "path": "projects/sandbox_project/assets/player.png",
                    "kind": "texture",
                    "role_candidates": ["player_sprite_primary"],
                    "tags": ["png"],
                    "metadata": {"extension": ".png", "exists": False},
                    "confidence": 0.9,
                }
            ],
            "role_bindings": {
                "player_sprite_primary": "asset_001_player",
            },
            "discovery_summary": {"total_assets": 1},
            "warnings": [],
        }
        validate_asset_registry_payload(payload)

    def test_validate_asset_registry_payload_rejects_out_of_sandbox_path(self) -> None:
        payload = {
            "registry_version": 1,
            "project_root": "projects/sandbox_project",
            "archetype_id": "topdown_adventure_v1",
            "assets": [
                {
                    "asset_id": "asset_001_player",
                    "path": "assets/player.png",
                    "kind": "texture",
                    "role_candidates": ["player_sprite_primary"],
                    "tags": ["png"],
                    "metadata": {"extension": ".png", "exists": False},
                    "confidence": 0.9,
                }
            ],
            "role_bindings": {},
            "discovery_summary": {"total_assets": 1},
            "warnings": [],
        }
        with self.assertRaises(ValueError):
            validate_asset_registry_payload(payload)

    def test_validate_scene_spec_payload_accepts_valid_payload(self) -> None:
        payload = {
            "scene_spec_version": 1,
            "archetype_id": "topdown_adventure_v1",
            "scene_path": "projects/sandbox_project/scenes/Main.tscn",
            "terrain": {"representation": "sprite_fallback"},
            "nodes": [
                {"node_id": "Main"},
                {"node_id": "Ground"},
                {"node_id": "Player", "script_path": "projects/sandbox_project/scripts/player.gd"},
                {"node_id": "Enemy"},
                {"node_id": "NPC"},
                {"node_id": "UI"},
                {"node_id": "HealthLabel"},
            ],
            "spawns": {
                "player": [0, 0],
                "enemy": [10, 10],
                "npc": [20, 20],
            },
        }
        validate_scene_spec_payload(payload)

    def test_validate_scene_spec_payload_rejects_missing_required_nodes(self) -> None:
        payload = {
            "scene_spec_version": 1,
            "archetype_id": "topdown_adventure_v1",
            "scene_path": "projects/sandbox_project/scenes/Main.tscn",
            "terrain": {"representation": "tilemap"},
            "nodes": [{"node_id": "Main"}],
            "spawns": {
                "player": [0, 0],
                "enemy": [10, 10],
                "npc": [20, 20],
            },
        }
        with self.assertRaises(ValueError):
            validate_scene_spec_payload(payload)


if __name__ == "__main__":
    unittest.main()
