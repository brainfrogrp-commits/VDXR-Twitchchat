extends Node3D
## Grip to pick up the panel; while holding it, press the face button
## (ax_button) to lock it in place relative to that hand -- e.g. hold it
## against your forearm and lock it there. Press the face button again
## to unlock and let it float freely in world space again.

const GRAB_ACTION := "grip_click"
const LOCK_ACTION := "ax_button"
const GRAB_DISTANCE := 0.25

var _held_by: XRController3D = null
var _hold_offset := Transform3D.IDENTITY

var _locked := false
var _locked_by: XRController3D = null
var _locked_offset := Transform3D.IDENTITY

func _ready() -> void:
	for hand in get_tree().get_nodes_in_group("vr_hand"):
		hand.button_pressed.connect(_on_button_pressed.bind(hand))

func _physics_process(_delta: float) -> void:
	if _locked:
		if is_instance_valid(_locked_by):
			global_transform = _locked_by.global_transform * _locked_offset
		return

	if _held_by:
		if not is_instance_valid(_held_by) or not _held_by.is_button_pressed(GRAB_ACTION):
			_release()
			return
		global_transform = _held_by.global_transform * _hold_offset
		return

	for hand in get_tree().get_nodes_in_group("vr_hand"):
		if hand.is_button_pressed(GRAB_ACTION) and global_transform.origin.distance_to(hand.global_transform.origin) < GRAB_DISTANCE:
			_grab(hand)
			break

func _grab(hand: XRController3D) -> void:
	_held_by = hand
	_hold_offset = hand.global_transform.affine_inverse() * global_transform

func _release() -> void:
	if is_instance_valid(_held_by):
		global_transform = _held_by.global_transform * _hold_offset
	_held_by = null

func _on_button_pressed(button_name: String, hand: XRController3D) -> void:
	if button_name != LOCK_ACTION:
		return
	if _locked:
		global_transform = _locked_by.global_transform * _locked_offset
		_locked = false
		_locked_by = null
	elif _held_by == hand:
		_locked = true
		_locked_by = hand
		_locked_offset = _hold_offset
		_held_by = null
