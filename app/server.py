"""Local web UI + API. Bound to 127.0.0.1 only; API keys never leave this PC
except to Inworld/OpenRouter."""

import logging
import os
import threading

from flask import Flask, jsonify, request, send_from_directory

from frog_voice import config, inworld, lifecycle, twitch
from frog_voice.engine import engine
from frog_voice.wake import WakeListener

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
PORT = 5858
_ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
_ALLOWED_ORIGINS = {f"http://{host}" for host in _ALLOWED_HOSTS}

_refused = set()
app = Flask(__name__, static_folder="web", static_url_path="")
listener = WakeListener(engine)


@app.before_request
def only_our_own_page():
    """Any website open in your browser can fire requests at localhost. Refuse
    anything that isn't this app's own page."""
    origin = request.headers.get("Origin")
    if request.host not in _ALLOWED_HOSTS or (origin and origin not in _ALLOWED_ORIGINS):
        key = (request.host, origin)
        if key not in _refused:  # say so on the page, once per kind, so a wrongly blocked sender is visible
            _refused.add(key)
            engine.note("info", f"Refused a request from outside (host {request.host}, origin {origin or 'none'}).")
        return jsonify(error="forbidden"), 403


@app.get("/")
def index():
    return send_from_directory("web", "index.html")


@app.get("/api/config")
def get_config():
    return jsonify(config.public_view(config.load()))


@app.post("/api/config")
def set_config():
    cfg = config.update(request.get_json(force=True) or {})
    twitch.chat.apply(cfg)
    listener.apply(cfg)
    return jsonify(config.public_view(cfg))


@app.get("/api/voices")
def voices():
    try:
        return jsonify({"voices": inworld.list_voices(config.load())})
    except Exception as e:
        return jsonify({"voices": [], "error": str(e)}), 200


@app.post("/api/preview")
def preview():
    body = request.get_json(force=True) or {}
    voice = body.get("voice_id", "")
    text = body.get("text") or "Hey there, I'm BrainFrog! This is what I sound like."

    def run():
        try:
            engine.speak(config.load(), text, voice)
        except Exception as e:
            engine.note("error", str(e))
        finally:
            engine.status = "idle"

    threading.Thread(target=run, daemon=True).start()
    return jsonify(ok=True)


@app.post("/api/read_now")
def read_now():
    engine.read_now()
    return jsonify(ok=True)


@app.get("/api/chat")
def chat_status():
    return jsonify(
        **twitch.chat.status(),
        messages=[{"name": m.name, "text": m.text} for m in twitch.chat.recent(8)],
    )


@app.get("/api/status")
def status():
    return jsonify(
        status=engine.status,
        log=list(engine.log),
        listening=listener.running,
        listen_error=listener.error,
        mic_level=round(listener.level, 4),
    )


def warm_up() -> None:
    """Do the slow one-time work now instead of on the first message."""
    cfg = config.load()
    if cfg["wake_word_enabled"]:
        try:
            engine.note("info", f"Loading the speech model ({cfg['whisper_model_size']})...")
            from frog_voice import speech_io

            speech_io.preload(cfg["whisper_model_size"])
            engine.note("info", "Speech model ready.")
        except Exception as e:
            engine.note("error", f"Couldn't load the speech model: {e}")
    try:  # the fixed lines, ready to play instantly
        engine.prepare_phrases()
    except Exception as e:
        engine.note("error", f"Couldn't prepare BrainFrog's short phrases: {e}")
    for url in ("https://openrouter.ai", cfg["inworld_base_url"]):
        try:  # opens the secure connection now so the first real request skips the handshake
            from frog_voice import llm

            llm._session.head(url, timeout=5)
        except Exception:
            pass


def shutdown() -> None:
    engine.stop()
    twitch.chat.stop()
    if listener.running:
        try:
            listener.stop()
        except Exception:
            pass


def already_running(port: int) -> bool:
    """Windows lets a second copy bind a port an older copy already holds, so
    the old one silently keeps serving. Detect that and refuse to start."""
    import socket

    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


if __name__ == "__main__":
    if already_running(PORT):
        print("\nBrainFrog Voice is ALREADY RUNNING (another window, maybe from an older folder).")
        print("Close every black console window running it, then start this again.")
        print(f"To find it:  netstat -ano | findstr {PORT}   then   taskkill /PID <number> /F\n")
        raise SystemExit(1)
    twitch.chat.apply(config.load())
    engine.start()
    listener.apply(config.load())
    lifecycle.install(shutdown)
    threading.Thread(target=warm_up, daemon=True).start()
    print(f"BrainFrog Voice: open http://127.0.0.1:{PORT}")
    app.run(host="127.0.0.1", port=PORT, threaded=True)
