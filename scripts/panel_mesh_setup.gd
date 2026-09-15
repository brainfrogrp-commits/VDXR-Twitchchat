extends MeshInstance3D
## Wires the SubViewport's live texture onto this quad at runtime.
## Done in code rather than in the .tscn to avoid brittle hand-authored
## ViewportTexture resource paths.

@export var viewport_path: NodePath

func _ready() -> void:
	var vp := get_node(viewport_path) as SubViewport
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = vp.get_texture()
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	material_override = mat
