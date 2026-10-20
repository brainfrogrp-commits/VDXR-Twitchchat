"""Audio playback. The decoding/playback libraries are imported lazily so the
settings page still opens (and can report a clear error) if one isn't installed."""


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
