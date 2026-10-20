"""Audio playback and local speech-to-text. The heavy libraries are imported
lazily so the settings page still opens (and can report a clear error) if
one isn't installed."""

import threading

_whisper = {}
_whisper_lock = threading.Lock()


def _model(model_size: str):
    if model_size not in _whisper:
        from faster_whisper import WhisperModel

        _whisper[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _whisper[model_size]


def preload(model_size: str) -> None:
    """Load (and download, the first time) the speech model ahead of the first wake word."""
    with _whisper_lock:
        _model(model_size)


def transcribe(audio, model_size: str) -> str:
    if audio.size == 0:
        return ""
    with _whisper_lock:
        segments, _ = _model(model_size).transcribe(
            audio, language="en", beam_size=1, condition_on_previous_text=False, initial_prompt="BrainFrog, Twitch, chat"
        )
        # drop segments the model itself thinks are not speech: this is where "thanks for watching"
        # style inventions from room noise come from
        kept = [s.text.strip() for s in segments if not (s.no_speech_prob > 0.6 and s.avg_logprob < -1.0)]
        return " ".join(kept).strip()


def play_mp3(mp3_data: bytes, volume: float = 1.0) -> None:
    import miniaudio
    import numpy as np
    import sounddevice as sd

    decoded = miniaudio.decode(mp3_data)
    samples = np.frombuffer(decoded.samples, dtype=np.int16)
    if volume != 1.0:
        samples = np.clip(samples.astype(np.float32) * volume, -32768, 32767).astype(np.int16)
    if decoded.nchannels > 1:
        samples = samples.reshape(-1, decoded.nchannels)
    sd.play(samples, decoded.sample_rate)
    sd.wait()
