extends Node3D
## Boots the OpenXR session for the main scene.

func _ready() -> void:
	var xr_interface := XRServer.find_interface("OpenXR")
	if xr_interface and xr_interface.initialize():
		get_viewport().use_xr = true
		print("VDXR Twitch Chat: OpenXR initialized, entering VR.")
	else:
		push_error("OpenXR failed to initialize. Make sure Virtual Desktop is running with VDXR set as the active OpenXR runtime.")
