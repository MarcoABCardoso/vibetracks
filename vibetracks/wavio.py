"""Write float audio buffers to 16-bit PCM WAV using only the stdlib.

No external audio libraries are needed (no libsndfile/ffmpeg). A buffer is a
float array in roughly [-1, 1]; mono is 1-D, stereo is shape ``(n, 2)``.
"""

from __future__ import annotations

import wave

import numpy as np

from .synth import SR


def to_int16(buf: np.ndarray) -> np.ndarray:
    """Clip a float buffer to [-1, 1] and convert to int16 PCM samples."""
    clipped = np.clip(buf, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2")


def write_wav(path: str, buf: np.ndarray, sr: int = SR) -> float:
    """Write ``buf`` to ``path`` as 16-bit PCM WAV. Returns duration in seconds.

    Accepts mono (1-D) or stereo (shape ``(n, 2)``) float buffers.
    """
    buf = np.asarray(buf, dtype=np.float64)
    if buf.ndim == 1:
        channels = 1
        frames = buf.shape[0]
        data = to_int16(buf)
    elif buf.ndim == 2 and buf.shape[1] == 2:
        channels = 2
        frames = buf.shape[0]
        # Interleave L/R for WAV frame layout.
        data = to_int16(buf).reshape(-1)
    else:
        raise ValueError(f"buffer must be mono 1-D or stereo (n, 2); got {buf.shape}")

    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sr)
        w.writeframes(data.tobytes())
    return frames / sr
