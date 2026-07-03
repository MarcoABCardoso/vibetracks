"""Write RGBA pixel arrays to PNG using only the stdlib.

The sprite analogue of :mod:`vibetracks.wavio`: just as a float audio buffer is
serialized to WAV with the stdlib ``wave`` module, an ``(h, w, 4)`` uint8 RGBA
array is serialized to a PNG here with stdlib ``zlib`` + ``struct``. No Pillow is
needed to *write* — reading arbitrary source art is the only thing that needs it
(see :mod:`vibesprites.lpc`), exactly as FluidSynth is only needed to
read soundfonts, never to write WAVs.
"""

from __future__ import annotations

import struct
import zlib

import numpy as np


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def write_png(path: str, rgba: np.ndarray) -> tuple:
    """Write an ``(h, w, 4)`` uint8 RGBA array to ``path``. Returns ``(w, h)``."""
    arr = np.asarray(rgba)
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError(f"expected (h, w, 4) RGBA array, got {arr.shape}")
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    h, w = arr.shape[0], arr.shape[1]

    # PNG filter byte 0 (None) prepended to each scanline, then zlib-compress.
    raw = np.concatenate(
        [np.zeros((h, 1), dtype=np.uint8), arr.reshape(h, w * 4)], axis=1)
    compressed = zlib.compress(raw.tobytes(), level=6)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)  # 8-bit, colour type 6 = RGBA
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(_chunk(b"IHDR", ihdr))
        f.write(_chunk(b"IDAT", compressed))
        f.write(_chunk(b"IEND", b""))
    return (w, h)
