"""Optional game-ready audio export (OGG / MP3 / FLAC) on top of the WAV core.

The core render path writes 16-bit WAV with only the stdlib (see ``wavio.py``).
Games usually ship a compressed, royalty-free format instead: **OGG Vorbis** is
the de-facto game standard — small, seamless-loop friendly, decoded by every
major engine (Godot, Unity, Unreal, web) — with **MP3** for universality and
**FLAC** when you want lossless. Those need real encoders, imported lazily so
``validate`` and the WAV path never depend on them:

    pip install vibetracks[export]     # soundfile (OGG/FLAC) + lameenc (MP3)

OGG/FLAC go through libsndfile via the ``soundfile`` package; MP3 through LAME
via the self-contained ``lameenc`` wheel. A missing encoder raises
:class:`ExportError` with the install hint, mirroring the optional soundfont
engine — so the two extras stay independent of the core.
"""

from __future__ import annotations

import numpy as np

from .synth import SR
from .wavio import to_int16, write_wav

# Export extension -> (libsndfile container, subtype) for the soundfile path.
_SNDFILE = {"ogg": ("OGG", "VORBIS"), "flac": ("FLAC", "PCM_16")}
FORMATS = ("wav", "ogg", "mp3", "flac")


class ExportError(RuntimeError):
    """Raised for an unknown format or a missing optional encoder."""


def _write_sndfile(path: str, buf: np.ndarray, sr: int, fmt: str) -> None:
    try:
        import soundfile
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise ExportError(
            f"{fmt.upper()} export needs the 'soundfile' package (libsndfile). "
            "Install it with:  pip install vibetracks[export]") from e
    container, subtype = _SNDFILE[fmt]
    data = np.ascontiguousarray(np.clip(np.asarray(buf, dtype=np.float32), -1.0, 1.0))
    channels = 1 if data.ndim == 1 else data.shape[1]
    # Stream in ~1s blocks: some libsndfile builds' Vorbis encoder segfaults on a
    # single very large write, and blocking keeps peak memory flat regardless.
    block = max(1, int(sr))
    with soundfile.SoundFile(path, "w", samplerate=int(sr), channels=channels,
                             format=container, subtype=subtype) as f:
        for i in range(0, data.shape[0], block):
            f.write(data[i:i + block])


def _write_mp3(path: str, buf: np.ndarray, sr: int, bitrate: int = 192) -> None:
    try:
        import lameenc
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise ExportError(
            "MP3 export needs the 'lameenc' package (bundled LAME). "
            "Install it with:  pip install vibetracks[export]") from e
    buf = np.asarray(buf, dtype=np.float64)
    channels = 1 if buf.ndim == 1 else 2
    pcm = to_int16(buf).reshape(-1)  # stereo (n, 2) -> interleaved L/R
    enc = lameenc.Encoder()
    enc.set_bit_rate(int(bitrate))
    enc.set_in_sample_rate(int(sr))
    enc.set_channels(channels)
    enc.set_quality(2)  # 0 = best/slowest .. 9 = worst/fastest
    with open(path, "wb") as f:
        f.write(enc.encode(pcm.tobytes()) + enc.flush())


def write_audio(path: str, buf: np.ndarray, sr: int = SR, fmt: str | None = None,
                bitrate: int = 192) -> float:
    """Write ``buf`` to ``path`` in ``fmt`` (else inferred from the extension).

    Returns duration in seconds. ``wav`` uses the stdlib core; ``ogg``/``flac``
    use libsndfile; ``mp3`` uses LAME. Accepts mono (1-D) or stereo ``(n, 2)``
    float buffers. Raises :class:`ExportError` for an unknown format or a missing
    optional encoder.
    """
    fmt = (fmt or path.rsplit(".", 1)[-1]).lower()
    if fmt == "wav":
        return write_wav(path, buf, sr)
    if fmt in _SNDFILE:
        _write_sndfile(path, buf, sr, fmt)
    elif fmt == "mp3":
        _write_mp3(path, buf, sr, bitrate)
    else:
        raise ExportError(f"unknown export format {fmt!r} (choose from {FORMATS})")
    return int(np.asarray(buf).shape[0]) / sr
