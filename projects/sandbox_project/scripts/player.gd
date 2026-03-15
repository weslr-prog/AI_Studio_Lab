extends CharacterBody2D

@export var speed: float = 200.0
@export var max_stamina: int = 100
@export var guardian_speed: float = 110.0
@export var guardian_contact_range: float = 28.0
@export var guardian_contact_cooldown: float = 0.9
@export var world_view_scale: float = 1.6
@export var character_scale_boost: float = 2.2

var stamina: int
var _guardian_contact_timer: float = 0.0
var _walk_anim_timer: float = 0.0
var _walk_anim_step: int = 0

func _ready() -> void:
	stamina = max_stamina
	_ensure_readable_actor_scale()
	_build_autotile_layout()
	_update_status_label()


func _physics_process(delta: float) -> void:
	var direction: Vector2 = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	velocity = direction * speed
	move_and_slide()
	_update_player_animation(direction, delta)

	if _guardian_contact_timer > 0.0:
		_guardian_contact_timer -= delta

	_run_guardian_behavior()


func _run_guardian_behavior() -> void:
	var root: Node = get_parent()
	if root == null:
		return

	var guardian_node: Node = root.get_node_or_null("Enemy")
	if guardian_node == null or not (guardian_node is CharacterBody2D):
		return

	var guardian: CharacterBody2D = guardian_node as CharacterBody2D
	var to_player: Vector2 = global_position - guardian.global_position
	var distance: float = to_player.length()

	if distance > 1.0:
		guardian.velocity = to_player.normalized() * guardian_speed
	else:
		guardian.velocity = Vector2.ZERO
	guardian.move_and_slide()

	if distance <= guardian_contact_range and _guardian_contact_timer <= 0.0:
		apply_contact_penalty(10)
		_guardian_contact_timer = guardian_contact_cooldown

	_update_guardian_animation(guardian, to_player)


func _update_player_animation(direction: Vector2, delta: float) -> void:
	var visual: Node = get_node_or_null("Visual")
	if visual == null or not (visual is Sprite2D):
		return

	var sprite: Sprite2D = visual as Sprite2D
	if sprite.hframes <= 1 or sprite.vframes <= 1:
		return

	var row: int = _direction_row(direction, sprite.vframes)
	var cols: int = max(1, sprite.hframes)
	if direction.length() < 0.05:
		sprite.frame = row * cols
		return

	_walk_anim_timer += delta
	if _walk_anim_timer >= 0.12:
		_walk_anim_timer = 0.0
		_walk_anim_step += 1

	var walk_frames: int = min(cols, 4)
	var frame_offset: int = _walk_anim_step % walk_frames
	sprite.frame = row * cols + frame_offset


func _update_guardian_animation(guardian: CharacterBody2D, to_player: Vector2) -> void:
	var visual: Node = guardian.get_node_or_null("Visual")
	if visual == null or not (visual is Sprite2D):
		return

	var sprite: Sprite2D = visual as Sprite2D
	if sprite.hframes <= 1 or sprite.vframes <= 1:
		return

	var row: int = _direction_row(to_player.normalized(), sprite.vframes)
	sprite.frame = row * max(1, sprite.hframes)


func _direction_row(direction: Vector2, rows: int) -> int:
	if rows <= 1:
		return 0
	if rows < 4:
		return min(rows - 1, 1 if abs(direction.x) > abs(direction.y) else 0)

	if abs(direction.x) > abs(direction.y):
		return 2 if direction.x > 0.0 else 1
	return 3 if direction.y < 0.0 else 0


func _terrain_hash(px: int, py: int, s: int) -> float:
	var dot_val: float = float(px) * 12.9898 + float(py) * 78.233 + float(s) * 43.7585
	return fmod(abs(sin(dot_val) * 43758.5453), 1.0)


func _choose_prop_cell_size(tex_w: int, tex_h: int) -> int:
	var candidates: Array = [128, 96, 64, 48, 32, 24, 16]
	for c in candidates:
		if tex_w % c != 0 or tex_h % c != 0:
			continue
		var cols: int = int(float(tex_w) / float(c))
		var rows: int = int(float(tex_h) / float(c))
		if cols >= 3 and rows >= 2 and cols * rows >= 10:
			return c
	return 0


func _collect_nonempty_cells(tex: Texture2D, cell: int, cols: int, rows: int) -> Array:
	var img: Image = tex.get_image()
	if img == null:
		return []

	var iw: int = img.get_width()
	var ih: int = img.get_height()
	var out: Array = []
	for cy in range(rows):
		for cx in range(cols):
			var ox: int = cx * cell
			var oy: int = cy * cell
			if ox + cell > iw or oy + cell > ih:
				continue

			var sx0: int = min(iw - 1, ox + int(float(cell) * 0.50))
			var sy0: int = min(ih - 1, oy + int(float(cell) * 0.78))
			var sx1: int = min(iw - 1, ox + int(float(cell) * 0.32))
			var sy1: int = min(ih - 1, oy + int(float(cell) * 0.52))
			var sx2: int = min(iw - 1, ox + int(float(cell) * 0.68))
			var sy2: int = min(ih - 1, oy + int(float(cell) * 0.52))

			var a0: float = img.get_pixel(sx0, sy0).a
			var a1: float = img.get_pixel(sx1, sy1).a
			var a2: float = img.get_pixel(sx2, sy2).a
			if a0 > 0.06 or a1 > 0.06 or a2 > 0.06:
				out.append(cy * cols + cx)
	return out


func _collect_classified_cells(tex: Texture2D, cell: int, cols: int, rows: int, kind: String) -> Array:
	var img: Image = tex.get_image()
	if img == null:
		return []

	var iw: int = img.get_width()
	var ih: int = img.get_height()
	var out: Array = []
	for cy in range(rows):
		for cx in range(cols):
			var ox: int = cx * cell
			var oy: int = cy * cell
			if ox + cell > iw or oy + cell > ih:
				continue

			var samples: int = 0
			var full_alpha: float = 0.0
			var top_alpha: float = 0.0
			var bottom_alpha: float = 0.0
			var edge_hits: float = 0.0
			var edge_samples: float = 0.0
			for sy in range(0, cell, 6):
				for sx in range(0, cell, 6):
					var px: int = min(iw - 1, ox + sx)
					var py: int = min(ih - 1, oy + sy)
					var a: float = img.get_pixel(px, py).a
					samples += 1
					var is_edge: bool = sx <= 4 or sx >= cell - 6 or sy <= 4 or sy >= cell - 6
					if is_edge:
						edge_samples += 1.0
						if a > 0.06:
							edge_hits += 1.0
					if a > 0.06:
						full_alpha += 1.0
						if sy < int(float(cell) * 0.5):
							top_alpha += 1.0
						if sy > int(float(cell) * 0.72):
							bottom_alpha += 1.0

			if samples <= 0:
				continue

			var full_ratio: float = full_alpha / float(samples)
			var top_ratio: float = top_alpha / float(samples)
			var bottom_ratio: float = bottom_alpha / float(samples)
			var edge_ratio: float = 0.0
			if edge_samples > 0.0:
				edge_ratio = edge_hits / edge_samples

			var accept: bool = false
			if kind == "tree":
				accept = full_ratio > 0.16 and top_ratio > 0.08 and bottom_ratio > 0.02 and bottom_ratio < 0.16 and edge_ratio < 0.45
			elif kind == "shrub":
				accept = full_ratio > 0.07 and full_ratio < 0.36 and top_ratio < 0.14 and bottom_ratio > 0.03 and edge_ratio < 0.42
			elif kind == "rock":
				accept = full_ratio > 0.06 and full_ratio < 0.30 and top_ratio < 0.12 and bottom_ratio > 0.03 and edge_ratio < 0.42

			if accept:
				out.append(cy * cols + cx)
	return out


func _prop_catalog() -> Array:
	# Curated atlas cells only. Add entries as {"x": col, "y": row}.
	# Empty `entries` arrays mean this category will be skipped safely.
	return [
		{
			"path": "res://assets/2D Isometric Village Asset Pack/Isometric Assets 2.png",
			"kind": "tree",
			"cell": 64,
			"scale": 1.45,
			"count": 24,
			"collider": true,
			"collider_w": 0.34,
			"collider_h": 0.24,
			"entries": [
				{"x": 1, "y": 1}, {"x": 2, "y": 1}, {"x": 3, "y": 1}, {"x": 4, "y": 1},
				{"x": 1, "y": 2}, {"x": 2, "y": 2}, {"x": 3, "y": 2}, {"x": 4, "y": 2}
			]
		},
		{
			"path": "res://assets/2D Isometric Village Asset Pack/Isometric Assets 3.png",
			"kind": "shrub",
			"cell": 64,
			"scale": 1.25,
			"count": 28,
			"collider": false,
			"collider_w": 0.28,
			"collider_h": 0.20,
			"entries": [
				{"x": 6, "y": 3}, {"x": 7, "y": 3}, {"x": 8, "y": 3}, {"x": 9, "y": 3},
				{"x": 6, "y": 4}, {"x": 7, "y": 4}, {"x": 8, "y": 4}, {"x": 9, "y": 4}
			]
		},
		{
			"path": "res://assets/2D Isometric Village Asset Pack/Isometric Assets 4.png",
			"kind": "rock",
			"cell": 64,
			"scale": 1.30,
			"count": 18,
			"collider": true,
			"collider_w": 0.38,
			"collider_h": 0.24,
			"entries": [
				{"x": 10, "y": 5}, {"x": 11, "y": 5}, {"x": 12, "y": 5}, {"x": 13, "y": 5},
				{"x": 10, "y": 6}, {"x": 11, "y": 6}, {"x": 12, "y": 6}, {"x": 13, "y": 6}
			]
		}
	]


func _validated_catalog_entries(tex: Texture2D, cell: int, cols: int, rows: int, kind: String, entries: Array) -> Array:
	var allowed: Array = _collect_classified_cells(tex, cell, cols, rows, kind)
	if allowed.size() == 0:
		return []

	var allowed_map: Dictionary = {}
	for idx in allowed:
		allowed_map[int(idx)] = true

	var out: Array = []
	for e in entries:
		if not (e is Dictionary):
			continue
		var tx: int = int((e as Dictionary).get("x", -1))
		var ty: int = int((e as Dictionary).get("y", -1))
		if tx < 0 or ty < 0 or tx >= cols or ty >= rows:
			continue
		var idx: int = ty * cols + tx
		if allowed_map.has(idx):
			out.append({"x": tx, "y": ty})
	return out


func _spawn_catalog_props(
	terrain_container: Node2D,
	world_w: float,
	world_h: float,
	border_thickness: float,
	river_center_y: float,
	river_width: float,
	path_cx: float,
	path_cy: float,
	path_w: float
) -> void:
	var props: Node2D = Node2D.new()
	props.name = "Props"
	props.y_sort_enabled = true
	terrain_container.add_child(props)

	var placed_points: Array = []
	var prop_margin: float = border_thickness + 28.0

	var kinds: Array = [
		{"kind": "tree", "count": 24, "min_gap": 72.0, "collider": true},
		{"kind": "shrub", "count": 34, "min_gap": 44.0, "collider": false},
		{"kind": "rock", "count": 18, "min_gap": 64.0, "collider": true}
	]

	for si in range(kinds.size()):
		var spec: Dictionary = kinds[si]
		var kind: String = str(spec["kind"])
		var target_count: int = int(spec["count"])
		var min_gap: float = float(spec["min_gap"])
		var has_collider: bool = bool(spec["collider"])

		var placed: int = 0
		var attempts: int = target_count * 10
		for ai in range(attempts):
			if placed >= target_count:
				break

			var dx: float = prop_margin + _terrain_hash(si, ai, 901) * (world_w - prop_margin * 2.0)
			var dy: float = prop_margin + _terrain_hash(ai, si, 902) * (world_h - prop_margin * 2.0)

			var est_river_y: float = river_center_y + sin(dx / world_w * 8.0) * 55.0
			if abs(dy - est_river_y) < river_width * 1.8:
				continue

			var est_hpath_y: float = path_cy + sin(dx * 0.008) * 18.0
			if abs(dy - est_hpath_y) < path_w * 2.1:
				continue
			var est_vpath_x: float = path_cx + sin(dy * 0.009) * 15.0
			if abs(dx - est_vpath_x) < path_w * 2.1:
				continue

			if Vector2(dx, dy).distance_to(Vector2(world_w * 0.15, path_cy)) < 100.0:
				continue

			var too_close: bool = false
			for pp in placed_points:
				if (pp as Vector2).distance_to(Vector2(dx, dy)) < min_gap:
					too_close = true
					break
			if too_close:
				continue

			var prop_node: Node2D = Node2D.new()
			prop_node.position = Vector2(dx, dy)
			prop_node.name = "Prop_%s_%d" % [kind, placed]
			prop_node.z_index = int(dy)
			props.add_child(prop_node)

			if kind == "tree":
				var canopy: Polygon2D = Polygon2D.new()
				var canopy_pts: PackedVector2Array = PackedVector2Array()
				var segs: int = 11
				var rx: float = 26.0 + _terrain_hash(si, ai, 905) * 8.0
				var ry: float = 18.0 + _terrain_hash(si, ai, 906) * 6.0
				for pi in range(segs):
					var ang: float = float(pi) / float(segs) * TAU
					var n: float = 0.85 + _terrain_hash(pi, ai, 907) * 0.25
					canopy_pts.append(Vector2(cos(ang) * rx * n, -36.0 + sin(ang) * ry * n))
				canopy.polygon = canopy_pts
				canopy.color = Color(0.14, 0.46, 0.17, 1.0)
				prop_node.add_child(canopy)

				var trunk: Polygon2D = Polygon2D.new()
				trunk.polygon = PackedVector2Array([
					Vector2(-5, -14), Vector2(5, -14), Vector2(5, 8), Vector2(-5, 8)
				])
				trunk.color = Color(0.42, 0.28, 0.16, 1.0)
				prop_node.add_child(trunk)

			elif kind == "shrub":
				var shrub: Polygon2D = Polygon2D.new()
				var shrub_pts: PackedVector2Array = PackedVector2Array()
				var ssegs: int = 9
				var srx: float = 14.0 + _terrain_hash(si, ai, 908) * 6.0
				var sry: float = 9.0 + _terrain_hash(si, ai, 909) * 4.0
				for spi in range(ssegs):
					var sang: float = float(spi) / float(ssegs) * TAU
					var sn: float = 0.85 + _terrain_hash(spi, ai, 910) * 0.30
					shrub_pts.append(Vector2(cos(sang) * srx * sn, -8.0 + sin(sang) * sry * sn))
				shrub.polygon = shrub_pts
				shrub.color = Color(0.20, 0.52, 0.22, 1.0)
				prop_node.add_child(shrub)

			else:
				var rock: Polygon2D = Polygon2D.new()
				var rock_pts: PackedVector2Array = PackedVector2Array([
					Vector2(-13, -3), Vector2(-6, -12), Vector2(8, -11),
					Vector2(14, -2), Vector2(8, 6), Vector2(-9, 6)
				])
				rock.polygon = rock_pts
				rock.color = Color(0.50, 0.50, 0.55, 1.0)
				prop_node.add_child(rock)

			if has_collider:
				var body: StaticBody2D = StaticBody2D.new()
				var shape_node: CollisionShape2D = CollisionShape2D.new()
				var rect: RectangleShape2D = RectangleShape2D.new()
				rect.size = Vector2(16.0 if kind == "tree" else 20.0, 10.0 if kind == "tree" else 12.0)
				shape_node.shape = rect
				shape_node.position = Vector2(0.0, 4.0)
				body.add_child(shape_node)
				prop_node.add_child(body)

			placed += 1
			placed_points.append(Vector2(dx, dy))


func _build_autotile_layout() -> void:
	var root: Node = get_parent()
	if root == null:
		return

	var tile_root: Node = root.get_node_or_null("TileMapRoot")
	if tile_root == null:
		return

	# --- Clean up previous generation ---
	var generated: Node = tile_root.get_node_or_null("GeneratedTerrain")
	if generated != null:
		generated.queue_free()

	var terrain_container: Node2D = Node2D.new()
	terrain_container.name = "GeneratedTerrain"
	tile_root.add_child(terrain_container)

	# --- World sizing ---
	var world_w: float = 1920.0
	var world_h: float = 1280.0

	# =============================================
	# LAYER 0: Grass base (full world rectangle)
	# =============================================
	var grass: Polygon2D = Polygon2D.new()
	grass.polygon = PackedVector2Array([
		Vector2(0, 0), Vector2(world_w, 0),
		Vector2(world_w, world_h), Vector2(0, world_h)
	])
	grass.color = Color(0.28, 0.55, 0.22, 1.0)
	terrain_container.add_child(grass)

	# =============================================
	# LAYER 1: Border treeline (darker green frame)
	# =============================================
	var border_thickness: float = 64.0
	var border_colors: Array = [
		Color(0.12, 0.30, 0.10, 1.0),
		Color(0.16, 0.36, 0.14, 1.0)
	]
	# Top strip
	var bt: Polygon2D = Polygon2D.new()
	bt.polygon = PackedVector2Array([
		Vector2(0, 0), Vector2(world_w, 0),
		Vector2(world_w, border_thickness), Vector2(0, border_thickness)
	])
	bt.color = border_colors[0]
	terrain_container.add_child(bt)
	# Bottom strip
	var bb: Polygon2D = Polygon2D.new()
	bb.polygon = PackedVector2Array([
		Vector2(0, world_h - border_thickness), Vector2(world_w, world_h - border_thickness),
		Vector2(world_w, world_h), Vector2(0, world_h)
	])
	bb.color = border_colors[0]
	terrain_container.add_child(bb)
	# Left strip
	var bl: Polygon2D = Polygon2D.new()
	bl.polygon = PackedVector2Array([
		Vector2(0, 0), Vector2(border_thickness, 0),
		Vector2(border_thickness, world_h), Vector2(0, world_h)
	])
	bl.color = border_colors[1]
	terrain_container.add_child(bl)
	# Right strip
	var br: Polygon2D = Polygon2D.new()
	br.polygon = PackedVector2Array([
		Vector2(world_w - border_thickness, 0), Vector2(world_w, 0),
		Vector2(world_w, world_h), Vector2(world_w - border_thickness, world_h)
	])
	br.color = border_colors[1]
	terrain_container.add_child(br)

	# Irregular inner border bumps (organic treeline feel)
	for bx in range(0, int(world_w), 80):
		var bump_h: float = 20.0 + _terrain_hash(bx, 0, 11) * 30.0
		var bump_w: float = 40.0 + _terrain_hash(bx, 1, 12) * 50.0
		# Top bumps
		var tbump: Polygon2D = Polygon2D.new()
		tbump.polygon = PackedVector2Array([
			Vector2(float(bx), border_thickness),
			Vector2(float(bx) + bump_w * 0.5, border_thickness + bump_h),
			Vector2(float(bx) + bump_w, border_thickness)
		])
		tbump.color = border_colors[0].lerp(Color(0.24, 0.48, 0.18), 0.3)
		terrain_container.add_child(tbump)
		# Bottom bumps
		var bbump: Polygon2D = Polygon2D.new()
		bbump.polygon = PackedVector2Array([
			Vector2(float(bx), world_h - border_thickness),
			Vector2(float(bx) + bump_w * 0.5, world_h - border_thickness - bump_h),
			Vector2(float(bx) + bump_w, world_h - border_thickness)
		])
		bbump.color = border_colors[0].lerp(Color(0.24, 0.48, 0.18), 0.3)
		terrain_container.add_child(bbump)

	# =============================================
	# LAYER 2: Meandering river
	# =============================================
	var river_center_y: float = world_h * 0.35
	var river_width: float = 48.0
	var river_points_top: PackedVector2Array = PackedVector2Array()
	var river_points_bot: PackedVector2Array = PackedVector2Array()
	var bridge_cx: float = world_w * 0.5
	var bridge_half: float = 60.0

	for rx in range(0, int(world_w) + 20, 20):
		var frac: float = float(rx) / world_w
		var wobble: float = sin(frac * 8.0) * 55.0 + sin(frac * 3.2) * 30.0
		var jitter: float = (_terrain_hash(rx, 0, 42) - 0.5) * 20.0
		var cy: float = river_center_y + wobble + jitter
		var half_w: float = river_width * 0.5 + (_terrain_hash(rx, 1, 43) - 0.5) * 16.0

		# Skip rendering over the bridge
		if abs(float(rx) - bridge_cx) < bridge_half:
			continue

		river_points_top.append(Vector2(float(rx), cy - half_w))
		river_points_bot.append(Vector2(float(rx), cy + half_w))

	# Build closed polygon from top + reversed bottom
	if river_points_top.size() > 2:
		var river_poly: PackedVector2Array = PackedVector2Array()
		for i in range(river_points_top.size()):
			river_poly.append(river_points_top[i])
		for i in range(river_points_bot.size() - 1, -1, -1):
			river_poly.append(river_points_bot[i])

		var river: Polygon2D = Polygon2D.new()
		river.polygon = river_poly
		river.color = Color(0.18, 0.42, 0.72, 1.0)
		terrain_container.add_child(river)

		# River bank (slightly darker, slightly wider)
		var bank: Polygon2D = Polygon2D.new()
		bank.polygon = river_poly
		bank.color = Color(0.22, 0.38, 0.20, 1.0)
		bank.z_index = -1
		bank.scale = Vector2(1.0, 1.15)
		bank.position = Vector2(0, -river_width * 0.04)
		terrain_container.add_child(bank)

	# Bridge surface
	var bridge: Polygon2D = Polygon2D.new()
	var bcx: float = bridge_cx
	bridge.polygon = PackedVector2Array([
		Vector2(bcx - bridge_half, river_center_y - river_width * 0.7),
		Vector2(bcx + bridge_half, river_center_y - river_width * 0.7),
		Vector2(bcx + bridge_half, river_center_y + river_width * 0.7),
		Vector2(bcx - bridge_half, river_center_y + river_width * 0.7)
	])
	bridge.color = Color(0.52, 0.38, 0.24, 1.0)
	terrain_container.add_child(bridge)

	# =============================================
	# LAYER 3: Dirt paths (curved)
	# =============================================
	var path_color: Color = Color(0.55, 0.42, 0.28, 1.0)
	var path_w: float = 28.0

	# Horizontal path across the middle
	var hpath: PackedVector2Array = PackedVector2Array()
	var hpath_bot: PackedVector2Array = PackedVector2Array()
	var path_cy: float = world_h * 0.52
	for px in range(0, int(world_w) + 20, 20):
		var wobble: float = sin(float(px) * 0.008) * 18.0 + sin(float(px) * 0.003) * 10.0
		hpath.append(Vector2(float(px), path_cy + wobble - path_w * 0.5))
		hpath_bot.append(Vector2(float(px), path_cy + wobble + path_w * 0.5))
	var hpath_poly: PackedVector2Array = PackedVector2Array()
	for i in range(hpath.size()):
		hpath_poly.append(hpath[i])
	for i in range(hpath_bot.size() - 1, -1, -1):
		hpath_poly.append(hpath_bot[i])
	var h_path_node: Polygon2D = Polygon2D.new()
	h_path_node.polygon = hpath_poly
	h_path_node.color = path_color
	terrain_container.add_child(h_path_node)

	# Vertical path through the center
	var vpath: PackedVector2Array = PackedVector2Array()
	var vpath_right: PackedVector2Array = PackedVector2Array()
	var path_cx: float = world_w * 0.5
	for py in range(0, int(world_h) + 20, 20):
		var wobble: float = sin(float(py) * 0.009) * 15.0 + sin(float(py) * 0.004) * 8.0
		vpath.append(Vector2(path_cx + wobble - path_w * 0.5, float(py)))
		vpath_right.append(Vector2(path_cx + wobble + path_w * 0.5, float(py)))
	var vpath_poly: PackedVector2Array = PackedVector2Array()
	for i in range(vpath.size()):
		vpath_poly.append(vpath[i])
	for i in range(vpath_right.size() - 1, -1, -1):
		vpath_poly.append(vpath_right[i])
	var v_path_node: Polygon2D = Polygon2D.new()
	v_path_node.polygon = vpath_poly
	v_path_node.color = path_color
	terrain_container.add_child(v_path_node)

	# =============================================
	# LAYER 4: Dark foliage patches (elliptical clearings)
	# =============================================
	var foliage_centers: Array = [
		Vector2(280, 220), Vector2(600, 160), Vector2(1500, 300),
		Vector2(200, 900), Vector2(1100, 980), Vector2(1650, 850)
	]
	var foliage_color: Color = Color(0.18, 0.42, 0.15, 1.0)
	for fc in foliage_centers:
		var radius: float = 60.0 + _terrain_hash(int(fc.x), int(fc.y), 99) * 50.0
		var points: PackedVector2Array = PackedVector2Array()
		var segments: int = 12
		for si in range(segments):
			var angle: float = float(si) / float(segments) * TAU
			var r: float = radius * (0.8 + _terrain_hash(int(fc.x) + si, int(fc.y), 55) * 0.4)
			points.append(Vector2(fc.x + cos(angle) * r, fc.y + sin(angle) * r * 0.7))
		var patch: Polygon2D = Polygon2D.new()
		patch.polygon = points
		patch.color = foliage_color
		terrain_container.add_child(patch)

	# Hide the atlas preview sprite so only curated props render.
	var ground_visual: Node = root.get_node_or_null("TileMapRoot/GroundSprite")
	if ground_visual != null and ground_visual is Sprite2D:
		(ground_visual as Sprite2D).visible = false

	# Spawn curated props (whitelist-only atlas cells + collision presets).
	_spawn_catalog_props(
		terrain_container,
		world_w,
		world_h,
		border_thickness,
		river_center_y,
		river_width,
		path_cx,
		path_cy,
		path_w
	)

	# =============================================
	# Position player, camera, NPCs
	# =============================================
	global_position = Vector2(world_w * 0.15, path_cy)

	var camera_node: Node = get_node_or_null("Camera2D")
	if camera_node == null:
		var camera: Camera2D = Camera2D.new()
		camera.name = "Camera2D"
		add_child(camera)
		camera.enabled = true
		camera.make_current()
		camera.limit_enabled = true
		camera.limit_left = 0
		camera.limit_top = 0
		camera.limit_right = int(world_w)
		camera.limit_bottom = int(world_h)
		camera.zoom = Vector2(world_view_scale, world_view_scale)
	elif camera_node is Camera2D:
		var existing_camera: Camera2D = camera_node as Camera2D
		existing_camera.enabled = true
		existing_camera.make_current()
		existing_camera.limit_enabled = true
		existing_camera.limit_left = 0
		existing_camera.limit_top = 0
		existing_camera.limit_right = int(world_w)
		existing_camera.limit_bottom = int(world_h)
		existing_camera.zoom = Vector2(world_view_scale, world_view_scale)

	var guardian_node: Node = root.get_node_or_null("Enemy")
	if guardian_node != null and guardian_node is CharacterBody2D:
		(guardian_node as CharacterBody2D).global_position = Vector2(world_w * 0.72, world_h * 0.52)

	var npc_a: Node = root.get_node_or_null("NPCs/NPC_A")
	if npc_a != null and npc_a is Node2D:
		(npc_a as Node2D).global_position = Vector2(world_w * 0.25, world_h * 0.75)

	var npc_b: Node = root.get_node_or_null("NPCs/NPC_B")
	if npc_b != null and npc_b is Node2D:
		(npc_b as Node2D).global_position = Vector2(world_w * 0.82, world_h * 0.78)

	var npc_c: Node = root.get_node_or_null("NPCs/NPC_C")
	if npc_c != null and npc_c is Node2D:
		(npc_c as Node2D).global_position = Vector2(world_w * 0.52, world_h * 0.28)


func apply_contact_penalty(amount: int) -> void:
	stamina = max(0, stamina - max(1, amount))
	_update_status_label()


func _update_status_label() -> void:
	var root: Node = get_parent()
	if root == null:
		return
	var label_node: Node = root.get_node_or_null("HUD/HealthLabel")
	if label_node != null and label_node is Label:
		(label_node as Label).text = "STAMINA: %d/%d" % [stamina, max_stamina]


func _ensure_readable_actor_scale() -> void:
	var player_visual := get_node_or_null("Visual")
	if player_visual != null and player_visual is Sprite2D:
		var sprite := player_visual as Sprite2D
		if sprite.scale.length() < 0.01:
			sprite.scale = Vector2.ONE
		sprite.scale = sprite.scale * character_scale_boost

	var root: Node = get_parent()
	if root == null:
		return

	var enemy_visual := root.get_node_or_null("Enemy/Visual")
	if enemy_visual != null and enemy_visual is Sprite2D:
		var enemy_sprite := enemy_visual as Sprite2D
		if enemy_sprite.scale.length() < 0.01:
			enemy_sprite.scale = Vector2.ONE
		enemy_sprite.scale = enemy_sprite.scale * max(1.4, character_scale_boost * 0.85)

	var npc_root := root.get_node_or_null("NPCs")
	if npc_root != null:
		for child in npc_root.get_children():
			if child is Node2D:
				var npc_visual := (child as Node2D).get_node_or_null("Visual")
				if npc_visual != null and npc_visual is Sprite2D:
					var npc_sprite := npc_visual as Sprite2D
					if npc_sprite.scale.length() < 0.01:
						npc_sprite.scale = Vector2.ONE
					npc_sprite.scale = npc_sprite.scale * max(1.25, character_scale_boost * 0.75)
