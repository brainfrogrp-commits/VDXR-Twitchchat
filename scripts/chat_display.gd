extends Control

const MAX_MESSAGES := 150

@onready var chat_log: RichTextLabel = $Margin/VBox/ChatLog
@onready var title_label: Label = $Margin/VBox/Title

var _lines: Array[String] = []
var _channel := ""

func _ready() -> void:
	TwitchChat.message_received.connect(_on_message_received)
	TwitchChat.connection_status_changed.connect(_on_status_changed)
	TwitchChat.connected_to_channel.connect(_on_connected)

func _on_connected(channel: String) -> void:
	_channel = channel
	_update_title("connected")

func _on_status_changed(status: String) -> void:
	_update_title(status)
	_push_line("[color=#888888][i]-- %s --[/i][/color]" % status)

func _update_title(status: String) -> void:
	if _channel.is_empty():
		title_label.text = "Twitch Chat (%s)" % status
	else:
		title_label.text = "#%s (%s)" % [_channel, status]

func _on_message_received(display_name: String, text: String, color: String) -> void:
	var safe_name := _sanitize(display_name)
	var safe_text := _sanitize(text)
	_push_line("[color=%s][b]%s[/b][/color]: %s" % [color, safe_name, safe_text])

func _push_line(line: String) -> void:
	_lines.append(line)
	if _lines.size() > MAX_MESSAGES:
		_lines.pop_front()
	chat_log.clear()
	chat_log.append_text("\n".join(_lines))

func _sanitize(s: String) -> String:
	return s.replace("[", "(").replace("]", ")")
