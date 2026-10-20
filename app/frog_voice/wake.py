"""Hands-free wake-word listening: detect speech on the mic, transcribe it
locally, and if it mentions the wake word or just sounds like someone asking
what chat is saying, read the latest chat messages aloud. There's no open
conversation to manage here (unlike a Q&A companion) -- each utterance is
either a trigger or it isn't.

The trigger logic (mentions_wake_word, is_noise, Segmenter) is pure and has
no audio or network dependency, so it can be tested without a microphone."""

import collections
import re
import threading
import time
from typing import List, Optional

import numpy as np

SAMPLE_RATE = 16000
BLOCK = 1024  # about 64 ms per audio block
PREROLL_BLOCKS = 5  # keep ~0.3 s before speech starts so first syllables aren't clipped
MIN_SPEECH_S = 0.4
MAX_UTTERANCE_S = 12.0

# things speech recognition invents out of room noise or silence
NOISE = {"you", "thank you", "thanks", "bye", "okay", "ok", "the", "uh", "um", "hmm", "mm", "huh", "oh", "so",
         "thanks for watching", "thank you for watching"}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())).strip()


def is_noise(text: str) -> bool:
    cleaned = normalize(text)
    return not cleaned or cleaned in NOISE


def mentions_wake_word(text: str, wake_word: str) -> bool:
    """Lenient match: punctuation and spaces are ignored on both sides, so a
    wake word of "brainfrog" still matches "brain frog" (speech recognition
    sometimes splits one word into two)."""
    squashed = re.sub(r"[^a-z0-9]", "", (text or "").lower())
    target = re.sub(r"[^a-z0-9]", "", (wake_word or "").lower())
    return bool(target) and target in squashed


class Segmenter:
    """Turns a stream of audio blocks into utterances using a loudness
    threshold. Pure logic, so it can be tested without a microphone."""

    def __init__(self, threshold: float, silence_s: float):
        self.threshold = threshold
        self.silence_s = silence_s
        self._preroll: "collections.deque[np.ndarray]" = collections.deque(maxlen=PREROLL_BLOCKS)
        self._buf: List[np.ndarray] = []
        self._active = False
        self._last_voice = 0.0
        self._started = 0.0

    def reset(self) -> None:
        self._preroll.clear()
        self._buf = []
        self._active = False

    def feed(self, block: np.ndarray, now: float) -> Optional[np.ndarray]:
        loud = float(np.sqrt(np.mean(block * block))) >= self.threshold
        if not self._active:
            self._preroll.append(block)
            if loud:
                self._active = True
                self._started = self._last_voice = now
                self._buf = list(self._preroll)
            return None
        self._buf.append(block)
        if loud:
            self._last_voice = now
        if now - self._last_voice >= self.silence_s or now - self._started >= MAX_UTTERANCE_S:
            speech_s = self._last_voice - self._started
            audio = np.concatenate(self._buf)
            self.reset()
            return audio if speech_s >= MIN_SPEECH_S else None
        return None


class WakeListener:
    """Owns the mic stream. `apply(cfg)` starts/stops it to match settings."""

    def __init__(self, engine):
        self.engine = engine
        self.level = 0.0
        self.running = False
        self.error = ""
        self._stream = None
        self._seg: Optional[Segmenter] = None
        self._cfg = {}
        self._cfg_at = 0.0
        self._pending: "collections.deque" = collections.deque(maxlen=3)
        self._wake_evt = threading.Event()
        self._worker: Optional[threading.Thread] = None

    def apply(self, cfg: dict) -> None:
        wanted = cfg["wake_word_enabled"] and cfg["twitch_enabled"]
        if wanted and not self.running:
            self.start()
        elif not wanted and self.running:
            self.stop()
        elif self.running:
            self._refresh_cfg(force=True)

    def start(self) -> None:
        try:
            import sounddevice as sd

            self._refresh_cfg(force=True)
            self._seg = Segmenter(self._cfg["vad_threshold"], self._cfg["vad_silence_s"])
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=BLOCK, callback=self._callback
            )
            self._stream.start()
            self.running, self.error = True, ""
            self._worker = threading.Thread(target=self._work, daemon=True)
            self._worker.start()
            self.engine.note("info", f'Listening for "{self._cfg["wake_word"]}" (or just ask what chat is saying).')
        except Exception as e:
            self.running, self.error = False, f"Mic error: {e}"
            self.engine.note("error", self.error)

    def stop(self) -> None:
        self.running = False
        self._wake_evt.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self.level = 0.0

    def _refresh_cfg(self, force: bool = False) -> None:
        from frog_voice import config

        if force or time.monotonic() - self._cfg_at > 2.0:
            self._cfg = config.load()
            self._cfg_at = time.monotonic()
            if self._seg:
                self._seg.threshold = self._cfg["vad_threshold"]
                self._seg.silence_s = self._cfg["vad_silence_s"]

    def _callback(self, indata, frames, time_info, status) -> None:
        block = indata[:, 0].copy()
        self.level = float(np.sqrt(np.mean(block * block)))
        self._refresh_cfg()
        now = time.monotonic()
        # don't listen while BrainFrog is thinking or talking (his own voice leaks into the mic)
        if self.engine.is_busy() or now - self.engine.last_done < 0.8:
            self._seg.reset()
            return
        audio = self._seg.feed(block, now)
        if audio is not None:
            self._pending.append(audio)
            self._wake_evt.set()

    def _work(self) -> None:
        while self.running:
            self._wake_evt.wait(timeout=1.0)
            self._wake_evt.clear()
            while self._pending and self.running:
                audio = self._pending.popleft()
                try:
                    self._handle(audio)
                except Exception as e:
                    self.engine.note("error", f"Listening error: {e}")

    def _handle(self, audio) -> None:
        from frog_voice import speech_io, twitch

        cfg = self._cfg
        text = speech_io.transcribe(audio, cfg["whisper_model_size"])
        if not text or is_noise(text):
            return
        if mentions_wake_word(text, cfg["wake_word"]) or twitch.sounds_like_chat_request(text):
            self.engine.note("info", f'Heard "{text}" -- reading chat.')
            self.engine.read_now()
        else:
            self.engine.note("info", f'Heard "{text}" (not a trigger).')
