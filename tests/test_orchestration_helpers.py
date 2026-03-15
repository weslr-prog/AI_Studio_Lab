import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from types import SimpleNamespace

from runner import (
    _apply_template_bootstrap,
    _build_asset_registry_payload,
    _build_orchestrate_template_guidance,
    _build_scene_spec_payload,
    _asset_brief_to_objectives,
    _build_asset_catalog,
    _build_release_readiness_snapshot,
    _bootstrap_project_godot,
    _creative_brief_to_objectives,
    _ensure_decision_ledger_seed,
    _extract_error_warning_lines,
    _fallback_architect_proposal,
    _fallback_director_plan,
    _godot_cli_available,
    _invoke_with_retry,
    _is_retryable_stage_error,
    _missing_required_models_for_orchestrate,
    _normalize_director_plan_assignments,
    _recovery_payload_with_fallback,
    _required_artifacts_for_agent,
    _required_models_for_orchestrate,
    _required_pipeline_artifacts,
    _rank_installed_templates_for_objective,
    _resolve_procgen_template_paths,
    _score_template_candidate,
    _template_usage_advice,
)


class OrchestrationHelperTests(unittest.TestCase):
    def test_required_artifacts_mapping(self) -> None:
        self.assertEqual(
            _required_artifacts_for_agent("director"),
            ("projects/sandbox_project/project.godot",),
        )
        self.assertEqual(
            _required_artifacts_for_agent("architect"),
            ("projects/sandbox_project/scenes/Main.tscn",),
        )
        self.assertEqual(
            _required_artifacts_for_agent("programmer"),
            ("projects/sandbox_project/scripts/player.gd",),
        )
        self.assertEqual(_required_artifacts_for_agent("qa"), tuple())

    def test_required_pipeline_artifacts(self) -> None:
        self.assertEqual(
            _required_pipeline_artifacts(),
            (
                "projects/sandbox_project/project.godot",
                "projects/sandbox_project/scenes/Main.tscn",
                "projects/sandbox_project/scripts/player.gd",
            ),
        )

    def test_bootstrap_project_godot_creates_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            relative = _bootstrap_project_godot(project_root)
            target = project_root / relative
            self.assertTrue(target.exists())
            content = target.read_text(encoding="utf-8")
            self.assertIn("run/main_scene=\"res://scenes/Main.tscn\"", content)

    @patch("runner.shutil.which", return_value="/usr/local/bin/godot")
    def test_godot_cli_available_true(self, _mock_which: object) -> None:
        self.assertTrue(_godot_cli_available())

    @patch("runner.shutil.which", return_value=None)
    def test_godot_cli_available_false(self, _mock_which: object) -> None:
        self.assertFalse(_godot_cli_available())

    def test_required_models_for_orchestrate(self) -> None:
        self.assertEqual(
            _required_models_for_orchestrate(),
            ("qwen2.5-coder:14b", "qwen2.5:7b"),
        )

    @patch("runner.subprocess.run")
    def test_missing_required_models_for_orchestrate(self, mock_run: object) -> None:
        mock_run.return_value = SimpleNamespace(
            stdout=(
                "NAME                 ID              SIZE      MODIFIED\n"
                "qwen2.5:7b           abc123          4.7 GB    now\n"
            )
        )

        self.assertEqual(_missing_required_models_for_orchestrate(), ["qwen2.5-coder:14b"])

    def test_retryable_stage_error_detection(self) -> None:
        self.assertTrue(
            _is_retryable_stage_error(
                {
                    "status": "error",
                    "message": "LLM returned invalid JSON",
                }
            )
        )
        self.assertFalse(
            _is_retryable_stage_error(
                {
                    "status": "error",
                    "message": "Missing architect or programmer assignment in director plan",
                }
            )
        )

    def test_invoke_with_retry_respects_retry_budget(self) -> None:
        call_count = {"value": 0}

        def flaky_operation() -> dict[str, object]:
            call_count["value"] += 1
            if call_count["value"] < 3:
                return {"status": "error", "message": "LLM returned invalid JSON"}
            return {"status": "ok"}

        result = _invoke_with_retry("director_plan", flaky_operation)
        self.assertEqual(call_count["value"], 3)
        self.assertEqual(result["result"].get("status"), "ok")
        self.assertEqual(len(result["attempts"]), 3)

    def test_invoke_with_retry_uses_success_predicate(self) -> None:
        call_count = {"value": 0}

        def operation() -> dict[str, object]:
            call_count["value"] += 1
            if call_count["value"] == 1:
                return {"assessment": {"assessment": "error"}, "message": "LLM returned invalid JSON"}
            return {"assessment": {"assessment": "ok"}}

        result = _invoke_with_retry(
            "qa_analysis",
            operation,
            success_predicate=lambda payload: str(payload.get("assessment", {}).get("assessment", "")) == "ok",
        )
        self.assertEqual(call_count["value"], 2)
        self.assertEqual(result["attempts"][-1]["status"], "ok")

    def test_invoke_with_retry_catches_exceptions(self) -> None:
        call_count = {"value": 0}

        def raising_operation() -> dict[str, object]:
            call_count["value"] += 1
            raise ValueError("Missing key in plan JSON: plan_summary")

        result = _invoke_with_retry("director_plan", raising_operation)
        self.assertEqual(call_count["value"], 3)
        self.assertEqual(result["result"].get("status"), "error")
        self.assertIn("Missing key in plan JSON", str(result["result"].get("message", "")))
        self.assertTrue(all(attempt["retryable"] for attempt in result["attempts"]))

    def test_fallback_director_plan_is_deterministic_and_complete(self) -> None:
        plan = _fallback_director_plan("Build a Godot demo")
        self.assertEqual(plan["status"], "ok")
        assignments = plan["plan"]["assignments"]
        self.assertEqual(len(assignments), 3)
        self.assertEqual(assignments[0]["assigned_agent"], "director")
        self.assertEqual(assignments[1]["assigned_agent"], "architect")
        self.assertEqual(assignments[2]["assigned_agent"], "programmer")

    def test_fallback_architect_proposal_has_ledger_entry(self) -> None:
        proposal = _fallback_architect_proposal(task_id=42, objective="Build a scene")
        self.assertEqual(proposal["task_id"], 42)
        self.assertIn("ledger_entry", proposal)
        self.assertIn("confidence", proposal["ledger_entry"])

    def test_recovery_payload_with_fallback(self) -> None:
        payload = _recovery_payload_with_fallback(
            director_fallback_used=True,
            director_fallback_reason="director_plan retry exhaustion",
            architect_fallback_used=False,
            architect_fallback_reason=None,
        )
        self.assertIn("retry_policy", payload)
        self.assertIn("fallbacks", payload)
        self.assertTrue(payload["fallbacks"]["director_plan"]["used"])
        self.assertFalse(payload["fallbacks"]["architect_proposal"]["used"])

    def test_release_readiness_snapshot_blocks_on_docs_policy(self) -> None:
        snapshot = _build_release_readiness_snapshot(
            run_id="run-1",
            acceptance_passed=True,
            invariant_violation_count=0,
            docs_index={"status": "ok", "is_canonical_layout": False, "version": "4.2"},
            docs_strict=True,
            artifacts_present=True,
        )
        self.assertFalse(snapshot["release_ready"])
        self.assertIn("docs_policy_passed", snapshot["blocking_gates"])

    def test_release_readiness_snapshot_ready_when_all_gates_pass(self) -> None:
        snapshot = _build_release_readiness_snapshot(
            run_id="run-2",
            acceptance_passed=True,
            invariant_violation_count=0,
            docs_index={"status": "ok", "is_canonical_layout": True, "version": "4.2"},
            docs_strict=True,
            artifacts_present=True,
        )
        self.assertTrue(snapshot["release_ready"])
        self.assertEqual(snapshot["blocking_gates"], [])

    def test_creative_brief_to_objectives_returns_three_modes(self) -> None:
        payload = _creative_brief_to_objectives(
            {
                "project_name": "sandbox_project",
                "theme": "cozy",
                "game_style": "top-down prototype",
                "core_loop": "plants and waters crops",
                "feel_target": "responsive",
                "presentation_target": "a satisfying flash and seed counter label",
                "artifact_targets": [
                    "projects/sandbox_project/scenes/Main.tscn",
                    "projects/sandbox_project/scripts/player.gd",
                    "projects/sandbox_project/scripts/garden_logic.gd",
                ],
                "acceptance": "baseline artifacts exist and Godot validation has zero errors",
                "constraints": "deterministic, low scope",
            }
        )
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(payload["objectives"]), 3)
        self.assertEqual(payload["objectives"][0]["mode"], "minimal")
        self.assertEqual(payload["objectives"][1]["mode"], "balanced")
        self.assertEqual(payload["objectives"][2]["mode"], "strict")
        self.assertIn("plants and waters crops", payload["objectives"][1]["objective_sentence"])

    def test_creative_brief_to_objectives_defaults_missing_artifacts(self) -> None:
        payload = _creative_brief_to_objectives(
            {
                "theme": "neon",
                "game_style": "arcade",
                "core_loop": "dodges hazards",
                "artifact_targets": [],
            }
        )
        self.assertIn("projects/sandbox_project/scenes/Main.tscn", payload["artifact_targets"])
        self.assertIn("projects/sandbox_project/scripts/player.gd", payload["artifact_targets"])

    def test_build_asset_catalog_classifies_roles(self) -> None:
        catalog = _build_asset_catalog(
            [
                "projects/sandbox_project/assets/chars/Ranger.glb",
                "projects/sandbox_project/assets/world/Tree_1_A.gltf",
                "projects/sandbox_project/assets/world/Rock_1_A.gltf",
                "projects/sandbox_project/assets/world/Cave_Entrance.gltf",
                "projects/sandbox_project/assets/audio/win.ogg",
                "projects/sandbox_project/assets/textures/forest_texture.png",
            ]
        )
        self.assertEqual(catalog["total_assets"], 6)
        self.assertEqual(catalog["role_counts"]["characters"], 1)
        self.assertEqual(catalog["role_counts"]["vegetation"], 1)
        self.assertEqual(catalog["role_counts"]["rocks"], 1)
        self.assertEqual(catalog["role_counts"]["caves"], 1)
        self.assertEqual(catalog["role_counts"]["audio"], 1)

    def test_asset_brief_to_objectives_prefers_ranger_assignment(self) -> None:
        payload = _asset_brief_to_objectives(
            {
                "project_name": "sandbox_project",
                "genre_template": "isometric 2.5D exploration",
                "goal": "collect 3 keys and unlock a door",
                "character_preference": "ranger",
                "asset_paths": [
                    "projects/sandbox_project/assets/KayKit/Characters/Ranger.glb",
                    "projects/sandbox_project/assets/KayKit/Characters/Knight.glb",
                    "projects/sandbox_project/assets/KayKit/Forest/Tree_1_A.gltf",
                    "projects/sandbox_project/assets/KayKit/Forest/Rock_2_A.gltf",
                ],
            }
        )
        self.assertEqual(payload["status"], "ok")
        self.assertIn("Ranger.glb", payload["asset_role_assignments"]["character_asset"])
        self.assertEqual(len(payload["objectives"]), 3)
        self.assertIn("collectible", payload["objectives"][1]["objective_sentence"])

    def test_build_asset_registry_payload_minimal(self) -> None:
        payload = _build_asset_registry_payload(
            project_name="sandbox_project",
            asset_paths=[
                "projects/sandbox_project/assets/chars/player_ranger.png",
                "projects/sandbox_project/assets/world/terrain_tileset.png",
                "projects/sandbox_project/assets/world/tree_01.png",
            ],
        )
        self.assertEqual(payload["registry_version"], 1)
        self.assertEqual(payload["project_root"], "projects/sandbox_project")
        self.assertGreaterEqual(len(payload["assets"]), 3)
        self.assertIn("ground_tileset_primary", payload["role_bindings"])

    def test_build_scene_spec_payload_uses_sprite_fallback_without_tileset(self) -> None:
        asset_registry = _build_asset_registry_payload(
            project_name="sandbox_project",
            asset_paths=[
                "projects/sandbox_project/assets/chars/player_ranger.png",
            ],
        )
        scene_spec = _build_scene_spec_payload(
            project_name="sandbox_project",
            asset_registry_payload=asset_registry,
        )
        self.assertEqual(scene_spec["scene_spec_version"], 1)
        self.assertEqual(scene_spec["terrain"]["representation"], "sprite_fallback")
        node_ids = {node["node_id"] for node in scene_spec["nodes"]}
        self.assertIn("Main", node_ids)
        self.assertIn("Player", node_ids)

    def test_extract_error_warning_lines(self) -> None:
        errors, warnings = _extract_error_warning_lines(
            "Info line\nWARNING: texture is large\nError: missing resource\n"
        )
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(warnings), 1)
        self.assertIn("missing resource", errors[0].lower())

    def test_template_candidate_scoring_prefers_matching_paths(self) -> None:
        tokens = ["platformer", "2d"]
        high_score = _score_template_candidate("2d/platformer", tokens)
        low_score = _score_template_candidate("gui/inventory", tokens)
        self.assertGreater(high_score, low_score)

    @patch("runner._discover_repo_project_paths", return_value=["2d/procedural_generation", "2d/roguelike"])
    def test_resolve_procgen_template_paths_prefers_known_paths(self, _mock_discover: object) -> None:
        selected = _resolve_procgen_template_paths(
            repo="godotengine/godot-demo-projects",
            ref="master",
            max_procgen=2,
        )
        self.assertGreaterEqual(len(selected), 1)
        self.assertEqual(selected[0]["path"], "2d/procedural_generation")

    @patch("runner._search_repo_templates")
    @patch("runner._discover_repo_project_paths", return_value=[])
    def test_resolve_procgen_template_paths_falls_back_to_search(
        self,
        _mock_discover: object,
        mock_search: object,
    ) -> None:
        mock_search.side_effect = [
            {"candidates": [{"path": "3d/procedural_materials"}, {"path": "2d/noise_terrain"}]},
            {"candidates": [{"path": "2d/world_builder"}]},
            {"candidates": []},
        ]
        selected = _resolve_procgen_template_paths(
            repo="godotengine/godot-demo-projects",
            ref="master",
            max_procgen=2,
        )
        self.assertEqual(len(selected), 2)
        self.assertEqual(selected[0]["path"], "2d/noise_terrain")
        self.assertEqual(selected[1]["path"], "2d/world_builder")

    def test_template_usage_advice_detects_template_friendly_objective(self) -> None:
        advice = _template_usage_advice("Build a 2D platformer with inventory and dialogue")
        self.assertTrue(advice["should_use_template"])
        self.assertGreaterEqual(advice["confidence"], 0.7)
        self.assertIn("2d platformer", advice["recommended_queries"])

    def test_template_usage_advice_avoids_templates_for_minimal_shell(self) -> None:
        advice = _template_usage_advice("minimal single scene blank prototype shell")
        self.assertFalse(advice["should_use_template"])
        self.assertLessEqual(advice["confidence"], 0.6)

    def test_template_usage_advice_detects_procgen_map_objective(self) -> None:
        advice = _template_usage_advice("Build a procedural mapgen terrain system for a top-down prototype")
        self.assertTrue(advice["should_use_template"])
        self.assertIn("2d procedural generation", advice["recommended_queries"])

    def test_rank_installed_templates_for_procgen_prefers_2d(self) -> None:
        ranked = _rank_installed_templates_for_objective(
            objective="build procedural terrain map generator",
            installed_paths=["3d/procedural_materials", "2d/role_playing_game"],
            limit=2,
        )
        self.assertEqual(ranked[0], "2d/role_playing_game")

    @patch("runner._load_template_library_index")
    def test_orchestrate_template_guidance_recommends_installed_templates(self, mock_library: object) -> None:
        mock_library.return_value = {
            "status": "ok",
            "project_name": "sandbox_project",
            "templates": [
                {"template_path": "2d/platformer"},
                {"template_path": "2d/role_playing_game"},
                {"template_path": "gui/ui_mirroring"},
            ],
        }
        payload = _build_orchestrate_template_guidance(
            objective="build top down exploration with inventory",
            project_name="sandbox_project",
            precheck_enabled=True,
        )
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["decision"]["use_template"])
        self.assertGreaterEqual(len(payload["recommended_installed_templates"]), 1)

    def test_orchestrate_template_guidance_skipped_when_disabled(self) -> None:
        payload = _build_orchestrate_template_guidance(
            objective="anything",
            project_name="sandbox_project",
            precheck_enabled=False,
        )
        self.assertEqual(payload["status"], "skipped")
        self.assertFalse(payload["precheck_enabled"])

    @patch("runner._load_template_library_index")
    def test_orchestrate_template_guidance_recommends_procgen_template(self, mock_library: object) -> None:
        mock_library.return_value = {
            "status": "ok",
            "project_name": "sandbox_project",
            "templates": [
                {"template_path": "2d/procedural_generation"},
                {"template_path": "2d/top_down_movement"},
            ],
        }
        payload = _build_orchestrate_template_guidance(
            objective="create a mapgen-style procedural map terrain generator",
            project_name="sandbox_project",
            precheck_enabled=True,
        )
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["decision"]["use_template"])
        self.assertIn("2d/procedural_generation", payload["recommended_installed_templates"])

    @patch("runner._load_template_library_index")
    @patch("runner.load_kernel_config")
    def test_apply_template_bootstrap_copies_selected_template(
        self,
        mock_load_config: object,
        mock_load_library: object,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template_source = root / "projects" / "sandbox_project" / "templates" / "2d_role_playing_game"
            (template_source / "scenes").mkdir(parents=True, exist_ok=True)
            (template_source / "scripts").mkdir(parents=True, exist_ok=True)
            (template_source / "project.godot").write_text("config_version=5\n", encoding="utf-8")
            (template_source / "scenes" / "Main.tscn").write_text("[gd_scene]\n", encoding="utf-8")
            (template_source / "scripts" / "player.gd").write_text("extends Node\n", encoding="utf-8")

            mock_load_config.return_value = SimpleNamespace(project_root=root)
            mock_load_library.return_value = {
                "status": "ok",
                "project_name": "sandbox_project",
                "templates": [
                    {
                        "template_path": "2d/role_playing_game",
                        "local_path": template_source.as_posix(),
                    }
                ],
            }

            guidance = {
                "status": "ok",
                "decision": {"use_template": True},
                "recommended_installed_templates": ["2d/role_playing_game"],
            }
            payload = _apply_template_bootstrap(
                project_name="sandbox_project",
                guidance=guidance,
            )

            self.assertEqual(payload["status"], "applied")
            self.assertIn("template_bootstrap/current", payload["bootstrap_path"])
            copied_project = root / payload["bootstrap_path"] / "project.godot"
            self.assertTrue(copied_project.exists())

    def test_apply_template_bootstrap_skips_when_not_recommended(self) -> None:
        payload = _apply_template_bootstrap(
            project_name="sandbox_project",
            guidance={"status": "ok", "decision": {"use_template": False}},
        )
        self.assertEqual(payload["status"], "skipped")
        self.assertEqual(payload["reason"], "guidance_did_not_recommend_template")

    @patch("runner.DecisionLedger")
    def test_ensure_decision_ledger_seed_creates_entry_when_empty(self, mock_ledger_cls: object) -> None:
        mock_ledger = mock_ledger_cls.return_value
        mock_ledger.get_decisions.return_value = []
        mock_ledger.add_decision.return_value = 7

        payload = _ensure_decision_ledger_seed()
        self.assertEqual(payload["status"], "seeded")
        self.assertEqual(payload["entry_id"], 7)

    def test_normalize_director_plan_assignments_injects_architect_and_programmer(self) -> None:
        normalized = _normalize_director_plan_assignments(
            plan_payload={
                "status": "ok",
                "plan": {
                    "assignments": [
                        {
                            "task": "Implement movement",
                            "assigned_agent": "programmer",
                            "ledger_required": True,
                        }
                    ]
                },
            },
            objective_spec_payload={
                "artifacts": [
                    {"owner_agent": "director", "path": "projects/sandbox_project/project.godot"},
                    {"owner_agent": "architect", "path": "projects/sandbox_project/scenes/Main.tscn"},
                    {"owner_agent": "programmer", "path": "projects/sandbox_project/scripts/player.gd"},
                ]
            },
            objective="Build top-down scene with enemy and NPC",
        )
        assignments = normalized["plan"]["assignments"]
        agents = {item["assigned_agent"] for item in assignments}
        self.assertIn("architect", agents)
        self.assertIn("programmer", agents)


if __name__ == "__main__":
    unittest.main()
