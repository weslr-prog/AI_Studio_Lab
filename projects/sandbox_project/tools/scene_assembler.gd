extends SceneTree

const SANDBOX_PREFIX := "projects/sandbox_project/"
const OUTPUT_SCENE := "res://scenes/Main.tscn"
const OUTPUT_RESULT := "res://.studio/assembly_result.json"

func _initialize() -> void:
	var args := _parse_args(OS.get_cmdline_args())
	var scene_spec_path: String = args.get("scene_spec", "")
	var asset_registry_path: String = args.get("asset_registry", "")
	if scene_spec_path.is_empty() or asset_registry_path.is_empty():
		_emit_error("Missing required arguments --scene-spec and --asset-registry")
		quit(1)
		return

	var scene_spec_result := _load_json_file(scene_spec_path)
	if scene_spec_result.has("error"):
		_emit_error(str(scene_spec_result["error"]))
		quit(1)
		return
	var asset_registry_result := _load_json_file(asset_registry_path)
	if asset_registry_result.has("error"):
		_emit_error(str(asset_registry_result["error"]))
		quit(1)
		return

	var scene_spec: Dictionary = scene_spec_result
	var asset_registry: Dictionary = asset_registry_result
	var validation_error := _validate_inputs(scene_spec, asset_registry)
	if not validation_error.is_empty():
		_emit_error(validation_error)
		quit(1)
		return

	var build_result := _build_scene(scene_spec, asset_registry)
	_write_result(build_result)
	if str(build_result.get("status", "error")) == "ok":
		quit(0)
	else:
		quit(1)


func _parse_args(argv: PackedStringArray) -> Dictionary:
	var parsed := {}
	for i in range(argv.size()):
		if argv[i] == "--scene-spec" and i + 1 < argv.size():
			parsed["scene_spec"] = argv[i + 1]
		if argv[i] == "--asset-registry" and i + 1 < argv.size():
			parsed["asset_registry"] = argv[i + 1]
	return parsed


func _load_json_file(path: String) -> Dictionary:
	var absolute_path := path
	if not path.begins_with("res://") and not path.begins_with("/"):
		absolute_path = "res://" + path
	var file := FileAccess.open(absolute_path, FileAccess.READ)
	if file == null:
		return {"error": "Unable to open JSON file: %s" % absolute_path}
	var raw := file.get_as_text()
	var parsed = JSON.parse_string(raw)
	if typeof(parsed) != TYPE_DICTIONARY:
		return {"error": "JSON payload must be an object: %s" % absolute_path}
	return parsed


func _validate_inputs(scene_spec: Dictionary, asset_registry: Dictionary) -> String:
	if int(scene_spec.get("scene_spec_version", 0)) != 1:
		return "scene_spec_version must be 1"
	if int(asset_registry.get("registry_version", 0)) != 1:
		return "registry_version must be 1"
	var scene_path := str(scene_spec.get("scene_path", ""))
	if not scene_path.begins_with(SANDBOX_PREFIX):
		return "scene_path must remain in sandbox"
	return ""


func _build_scene(scene_spec: Dictionary, asset_registry: Dictionary) -> Dictionary:
	var root := Node2D.new()
	root.name = "Main"

	var created_nodes: Array[String] = ["Main"]
	var warnings: Array[String] = []
	var role_bindings: Dictionary = asset_registry.get("role_bindings", {})
	var terrain: Dictionary = scene_spec.get("terrain", {})
	var representation := str(terrain.get("representation", "sprite_fallback"))

	var ground_node: Node
	if representation == "tilemap":
		ground_node = TileMapLayer.new()
		ground_node.name = "Ground"
		created_nodes.append("Ground")
		if _resolve_role_path("ground_tileset_primary", role_bindings, asset_registry).is_empty():
			warnings.append("ground_tileset_primary unresolved; tilemap created without tileset")
	else:
		var sprite := Sprite2D.new()
		sprite.name = "Ground"
		var ground_path := _resolve_role_path("ground_sprite_fallback", role_bindings, asset_registry)
		var texture := _load_texture(ground_path)
		if texture != null:
			sprite.texture = texture
		else:
			warnings.append("ground_sprite_fallback unresolved; using empty ground sprite")
		ground_node = sprite
		created_nodes.append("Ground")
	root.add_child(ground_node)

	var player := _build_actor_node("Player", "player_sprite_primary", role_bindings, asset_registry, warnings)
	root.add_child(player)
	created_nodes.append("Player")
	var enemy := _build_actor_node("Enemy", "enemy_sprite_primary", role_bindings, asset_registry, warnings)
	root.add_child(enemy)
	created_nodes.append("Enemy")
	var npc := _build_actor_node("NPC", "npc_sprite_primary", role_bindings, asset_registry, warnings)
	root.add_child(npc)
	created_nodes.append("NPC")

	var ui := CanvasLayer.new()
	ui.name = "UI"
	var label := Label.new()
	label.name = "HealthLabel"
	label.text = "STAMINA: 100/100"
	ui.add_child(label)
	root.add_child(ui)
	created_nodes.append("UI")
	created_nodes.append("HealthLabel")

	_apply_spawns(scene_spec.get("spawns", {}), player, enemy, npc)
	_set_owner_recursive(root, root)

	var packed := PackedScene.new()
	var pack_result := packed.pack(root)
	if pack_result != OK:
		root.free()
		return {
			"status": "error",
			"message": "Failed to pack scene",
			"pack_error": pack_result,
			"warnings": warnings,
		}

	var save_result := ResourceSaver.save(packed, OUTPUT_SCENE)
	if save_result != OK:
		root.free()
		return {
			"status": "error",
			"message": "Failed to save scene",
			"save_error": save_result,
			"warnings": warnings,
		}

	root.free()

	return {
		"status": "ok",
		"scene_path": "projects/sandbox_project/scenes/Main.tscn",
		"terrain_mode": representation,
		"fallbacks_used": warnings,
		"created_nodes": created_nodes,
		"warnings": warnings,
	}


func _set_owner_recursive(root: Node, node: Node) -> void:
	for child in node.get_children():
		if child is Node:
			child.owner = root
			_set_owner_recursive(root, child)


func _build_actor_node(node_name: String, asset_role: String, role_bindings: Dictionary, asset_registry: Dictionary, warnings: Array[String]) -> CharacterBody2D:
	var actor := CharacterBody2D.new()
	actor.name = node_name
	var sprite := Sprite2D.new()
	sprite.name = "Sprite"
	var asset_path := _resolve_role_path(asset_role, role_bindings, asset_registry)
	var texture := _load_texture(asset_path)
	if texture != null:
		sprite.texture = texture
	else:
		warnings.append("%s unresolved; using empty sprite" % asset_role)
	actor.add_child(sprite)
	return actor


func _apply_spawns(spawns: Dictionary, player: CharacterBody2D, enemy: CharacterBody2D, npc: CharacterBody2D) -> void:
	if spawns.has("player") and typeof(spawns["player"]) == TYPE_ARRAY and spawns["player"].size() == 2:
		player.position = Vector2(float(spawns["player"][0]), float(spawns["player"][1]))
	if spawns.has("enemy") and typeof(spawns["enemy"]) == TYPE_ARRAY and spawns["enemy"].size() == 2:
		enemy.position = Vector2(float(spawns["enemy"][0]), float(spawns["enemy"][1]))
	if spawns.has("npc") and typeof(spawns["npc"]) == TYPE_ARRAY and spawns["npc"].size() == 2:
		npc.position = Vector2(float(spawns["npc"][0]), float(spawns["npc"][1]))


func _resolve_role_path(role: String, role_bindings: Dictionary, asset_registry: Dictionary) -> String:
	if not role_bindings.has(role):
		return ""
	var binding = role_bindings[role]
	var asset_id := ""
	if typeof(binding) == TYPE_STRING:
		asset_id = str(binding)
	elif typeof(binding) == TYPE_ARRAY and binding.size() > 0:
		asset_id = str(binding[0])
	if asset_id.is_empty():
		return ""
	for entry in asset_registry.get("assets", []):
		if typeof(entry) != TYPE_DICTIONARY:
			continue
		if str(entry.get("asset_id", "")) == asset_id:
			return _to_res_path(str(entry.get("path", "")))
	return ""


func _to_res_path(sandbox_path: String) -> String:
	if not sandbox_path.begins_with(SANDBOX_PREFIX):
		return ""
	var local_path := sandbox_path.trim_prefix(SANDBOX_PREFIX)
	return "res://" + local_path


func _load_texture(res_path: String) -> Texture2D:
	if res_path.is_empty():
		return null
	var loaded = load(res_path)
	if loaded == null:
		return null
	if loaded is Texture2D:
		return loaded
	return null


func _write_result(payload: Dictionary) -> void:
	DirAccess.make_dir_recursive_absolute("res://.studio")
	var file := FileAccess.open(OUTPUT_RESULT, FileAccess.WRITE)
	if file == null:
		print(JSON.stringify({"status": "error", "message": "Unable to write assembly result"}))
		return
	file.store_string(JSON.stringify(payload, "  "))
	print(JSON.stringify(payload))


func _emit_error(message: String) -> void:
	var payload = {"status": "error", "message": message}
	_write_result(payload)
