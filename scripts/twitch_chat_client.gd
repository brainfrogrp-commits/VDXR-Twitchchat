extends Node
## Anonymous, read-only Twitch IRC client over WebSocket.
## Autoloaded as "TwitchChat".

signal message_received(display_name: String, text: String, color: String)
signal connected_to_channel(channel: String)
signal connection_status_changed(status: String)

const IRC_URL := "wss://irc-ws.chat.twitch.tv:443"
const RECONNECT_DELAY := 3.0
const DEFAULT_COLOR := "#a970ff"

var _socket := WebSocketPeer.new()
var _last_state := WebSocketPeer.STATE_CLOSED
var _channel := ""
var _nick := ""
var _reconnecting := false

func _ready() -> void:
	randomize()
	_channel = _load_channel_name()
	_nick = "justinfan%d" % (10000 + randi() % 89999)
	_connect_socket()

func _load_channel_name() -> String:
	var channel := "your_channel_name"
	var config := ConfigFile.new()
	var exe_dir := OS.get_executable_path().get_base_dir()
	var candidates := [exe_dir.path_join("config.ini"), "res://config.ini", "user://config.ini"]
	for path in candidates:
		if config.load(path) == OK:
			channel = config.get_value("twitch", "channel", channel)
			break
	for arg in OS.get_cmdline_args():
		if arg.begins_with("--channel="):
			channel = arg.substr("--channel=".length())
	return channel.strip_edges().to_lower()

func _connect_socket() -> void:
	connection_status_changed.emit("connecting")
	var err := _socket.connect_to_url(IRC_URL)
	if err != OK:
		connection_status_changed.emit("connect failed (%s), retrying..." % err)
		_schedule_reconnect()

func _process(_delta: float) -> void:
	_socket.poll()
	var state := _socket.get_ready_state()
	if state != _last_state:
		_last_state = state
		if state == WebSocketPeer.STATE_OPEN:
			_on_socket_opened()
		elif state == WebSocketPeer.STATE_CLOSED:
			connection_status_changed.emit("disconnected, retrying...")
			_schedule_reconnect()

	while _socket.get_ready_state() == WebSocketPeer.STATE_OPEN and _socket.get_available_packet_count() > 0:
		var packet := _socket.get_packet().get_string_from_utf8()
		_handle_packet(packet)

func _schedule_reconnect() -> void:
	if _reconnecting:
		return
	_reconnecting = true
	await get_tree().create_timer(RECONNECT_DELAY).timeout
	_reconnecting = false
	_socket = WebSocketPeer.new()
	_last_state = WebSocketPeer.STATE_CLOSED
	_connect_socket()

func _on_socket_opened() -> void:
	_socket.send_text("CAP REQ :twitch.tv/tags")
	_socket.send_text("NICK %s" % _nick)
	_socket.send_text("JOIN #%s" % _channel)
	connection_status_changed.emit("connected")
	connected_to_channel.emit(_channel)

func _handle_packet(packet: String) -> void:
	for line in packet.split("\r\n"):
		if not line.is_empty():
			_handle_line(line)

func _handle_line(line: String) -> void:
	if line.begins_with("PING"):
		_socket.send_text(line.replace("PING", "PONG"))
		return

	var tags := {}
	var rest := line
	if line.begins_with("@"):
		var sp := line.find(" ")
		var tag_str := line.substr(1, sp - 1)
		rest = line.substr(sp + 1)
		for pair in tag_str.split(";"):
			var kv := pair.split("=", true, 1)
			if kv.size() == 2:
				tags[kv[0]] = _unescape_tag(kv[1])

	var privmsg_idx := rest.find("PRIVMSG")
	if privmsg_idx == -1:
		return

	var msg_start := rest.find(" :", privmsg_idx)
	if msg_start == -1:
		return
	var text := rest.substr(msg_start + 2)

	var display_name: String = tags.get("display-name", "")
	if display_name.is_empty() and rest.begins_with(":"):
		var bang := rest.find("!")
		if bang != -1:
			display_name = rest.substr(1, bang - 1)

	var color: String = tags.get("color", "")
	if color.is_empty():
		color = DEFAULT_COLOR

	message_received.emit(display_name, text, color)

func _unescape_tag(value: String) -> String:
	return value.replace("\\s", " ").replace("\\:", ";").replace("\\r", "").replace("\\n", "").replace("\\\\", "\\")
