"""BrainFrog's engine: watches the Twitch chat buffer and, every so often,
reads whatever's new aloud in character. No mic, no game, no conversation --
just chat in, voice out."""

import collections
import logging
import threading
import time
from typing import Optional, Tuple

from frog_voice import config, inworld, llm, persona, pipeline, streaming, twitch

log = logging.getLogger("brainfrog")

# Fixed lines that never touch the language model, so they play almost
# instantly (and don't cost an API call for something this simple).
PHRASES = {
    "greeting": ["Hopped into chat, ready to read!", "I'm in chat and ready to go."],
    "chat_off": ["I'm not connected to a chat right now."],
    "chat_down": ["I can't reach chat right now."],
    "chat_quiet": ["Chat's been quiet for a bit."],
}


class Engine:
    def __init__(self):
        self.log = collections.deque(maxlen=60)
        self.status = "idle"
        self._busy = threading.Lock()
        self._cursor = 0
        self._last_read_t = 0.0
        self._phrase_cache = {}
        self._greeted_channel = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_done = 0.0  # monotonic time the last reading finished (lets a mic listener avoid our own voice)

    # --- logging for the web page ---
    def note(self, kind: str, text: str) -> None:
        self.log.append({"t": time.time(), "kind": kind, "text": text})
        log.info("%s: %s", kind, text)

    # --- the watch loop ---
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                self.note("error", str(e))
            self._stop.wait(1.0)

    def _tick(self) -> None:
        cfg = config.load()
        if not cfg["twitch_enabled"] or not cfg["twitch_channel"].strip():
            return
        st = twitch.chat.status()
        if st["state"] != "connected":
            self._greeted_channel = None
            return
        if self._greeted_channel != st["channel"]:
            self._greeted_channel = st["channel"]
            self._cursor = twitch.chat.latest_seq()  # don't read the backlog, only what arrives from now on
            self._in_thread(self._say_phrase, "greeting")
            return
        if not cfg["auto_read_enabled"]:
            return
        if self._busy.locked():
            return
        now = time.monotonic()
        if now - self._last_read_t < cfg["min_gap_s"]:
            return
        messages, cursor = twitch.chat.since(self._cursor)
        if not messages:
            return
        batch = messages[-cfg["max_batch"]:]
        skipped = len(messages) - len(batch)
        self._cursor = cursor
        self._last_read_t = now
        self._in_thread(self._run_guarded, self._read_batch, batch, skipped)

    # --- speaking ---
    def _system(self, cfg: dict) -> str:
        return persona.build_system_prompt(cfg["persona_extra"])

    def speak(self, cfg: dict, text: str, voice_id: str = "") -> None:
        self.status = "speaking"
        pipeline.speak(cfg, iter(inworld.split_text(text)), voice_id)

    def _stream_reply(self, cfg: dict, messages: list, max_tokens: int) -> Tuple[Optional[str], dict]:
        t0 = time.monotonic()
        marks = {}
        parts = []

        def fragments():
            for fragment in llm.chat_stream(cfg, messages, max_tokens):
                marks.setdefault("first_words", time.monotonic() - t0)
                parts.append(fragment)
                yield fragment

        def audio_started():
            marks.setdefault("first_audio", time.monotonic() - t0)
            self.status = "speaking"

        pipeline.speak(cfg, streaming.sentences(fragments()), "", on_first_audio=audio_started)
        return "".join(parts).strip() or None, marks

    def _note_timing(self, marks: dict) -> None:
        bits = []
        if "first_words" in marks:
            bits.append(f"model's first words {marks['first_words']:.1f}s")
        if "first_audio" in marks:
            bits.append(f"first sound {marks['first_audio']:.1f}s after that")
        if bits:
            self.note("info", "Speed: " + ", ".join(bits))

    def _read_batch(self, messages, skipped: int) -> None:
        cfg = config.load()
        self.status = "thinking"
        prompt = twitch.chat_prompt(messages, skipped)
        reply, marks = self._stream_reply(
            cfg,
            [{"role": "system", "content": self._system(cfg)}, {"role": "user", "content": prompt}],
            min(450, 70 * len(messages) + 90),
        )
        if reply:
            self.note("frog", reply)
        self._note_timing(marks)

    def read_now(self) -> None:
        """Manual trigger from the settings page: read the latest messages right away.
        The quick "nothing to read" replies are said directly (no API call involved);
        only the actual LLM+TTS reading is handed off to a thread."""
        cfg = config.load()
        if not cfg["twitch_enabled"] or not cfg["twitch_channel"].strip():
            self._say_fixed(cfg, PHRASES["chat_off"][0])
            return
        if twitch.chat.status()["state"] != "connected":
            self._say_fixed(cfg, PHRASES["chat_down"][0])
            return
        messages = twitch.chat.recent(cfg["max_batch"])
        if not messages:
            self._say_fixed(cfg, PHRASES["chat_quiet"][0])
            return
        self._cursor = max(self._cursor, messages[-1].seq)
        self._last_read_t = time.monotonic()
        self._in_thread(self._run_guarded, self._read_batch, messages, 0)

    # --- plumbing ---
    def is_busy(self) -> bool:
        return self._busy.locked()

    def _in_thread(self, fn, *args) -> None:
        threading.Thread(target=fn, args=args, daemon=True).start()

    def _run_guarded(self, fn, *args) -> None:
        if not self._busy.acquire(blocking=False):
            self.note("info", "Still busy with the last reading.")
            return
        try:
            fn(*args)
        except Exception as e:
            self.note("error", str(e))
        finally:
            self.status = "idle"
            self.last_done = time.monotonic()
            self._busy.release()

    def _say_fixed(self, cfg: dict, text: str) -> None:
        key = (cfg["inworld_voice_id"], cfg["inworld_model_id"], cfg["speaking_rate"], text)
        if key not in self._phrase_cache:
            try:
                self._phrase_cache[key] = inworld.synthesize_chunk(cfg, text)
            except Exception as e:
                self.note("error", str(e))
                return
        self.note("frog", text)
        self.status = "speaking"
        try:
            from frog_voice import speech_io

            speech_io.play_mp3(self._phrase_cache[key], cfg["volume"])
        finally:
            self.status = "idle"

    def _say_phrase(self, kind: str) -> None:
        self._say_fixed(config.load(), PHRASES[kind][0])

    def prepare_phrases(self) -> None:
        """Synthesize the fixed lines ahead of time so they play instantly."""
        cfg = config.load()
        if not (cfg["inworld_api_key"] and cfg["inworld_voice_id"]):
            return
        for lines in PHRASES.values():
            for text in lines:
                key = (cfg["inworld_voice_id"], cfg["inworld_model_id"], cfg["speaking_rate"], text)
                if key not in self._phrase_cache:
                    try:
                        self._phrase_cache[key] = inworld.synthesize_chunk(cfg, text)
                    except Exception as e:
                        self.note("error", f"Couldn't prepare a phrase: {e}")
                        return


engine = Engine()
