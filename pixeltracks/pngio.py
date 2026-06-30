"""Write an RGBA numpy array to a PNG file using only the standard library.

The mirror of ``wavio.py``: just as that turns a float buffer into a 16-bit WAV
with stdlib ``wave``, this turns a ``(h, w, 4)`` uint8 array into an 8-bit RGBA
PNG with stdlib ``zlib`` + ``struct`` — no Pillow, no system image tools, in
keeping with the project's "pure, dependency-light compiler" rule.
"""

from __future__ import annotations

import struct
import zlib

import numpy as np

_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def encode_png(rgba: np.ndarray) -> bytes:
    """Encode an ``(h, w, 4)`` uint8 RGBA array as PNG bytes (colour type 6)."""
    arr = np.ascontiguousarray(rgba, dtype=np.uint8)
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError(f"expected an (h, w, 4) RGBA array, got {arr.shape}")
    h, w = arr.shape[:2]
    # Each scanline is prefixed with a filter-type byte (0 = none).
    rows = np.concatenate(
        [np.zeros((h, 1), dtype=np.uint8), arr.reshape(h, w * 4)], axis=1)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    idat = zlib.compress(rows.tobytes(), 9)
    return (_SIGNATURE + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", idat) + _chunk(b"IEND", b""))


def write_png(path: str, rgba: np.ndarray) -> tuple:
    """Write ``rgba`` to ``path`` as a PNG; return its ``(width, height)``."""
    data = encode_png(rgba)
    with open(path, "wb") as f:
        f.write(data)
    return (rgba.shape[1], rgba.shape[0])
