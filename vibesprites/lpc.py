"""The ``lpc`` layer engine — composite real LPC art via Pillow.

The sprite analogue of :mod:`vibetracks.soundfont`. Where the numpy synth engines
generate every timbre from math, and the ``soundfont`` engine instead *plays back
real recorded samples*, the ``lpc`` engine *plays back real drawn pixel art*: the
Liberated Pixel Cup layer PNGs (bodies, hair, clothes, weapons…). It is the direct
counterpart of the soundfont engine, not of a procedural one.

Like soundfont, it is intentionally **optional**. The core spec/validate path
depends only on numpy; Pillow is imported lazily and a missing library raises
:class:`LPCError` with install instructions only when a character actually asks to
be rendered. Validation never imports Pillow.

Reading source art needs Pillow; *writing* the finished sheet does not
(:mod:`vibesprites.pngio` uses the stdlib) — the same split as
soundfont-reads vs. wavio-writes.
"""

from __future__ import annotations

import os

import numpy as np

# Where layer PNGs are looked up when a patch ``source`` is relative: first the
# cast's own ``assets/`` dir, then a shared LPC checkout pointed at by this env
# var (so a user can render against the full upstream asset library).
ASSETS_ENV = "VIBETRACKS_LPC_ASSETS"

_INSTALL_HINT = (
    "the lpc engine needs Pillow to read layer art.\n"
    "  install:  pip install Pillow   (or:  pip install vibetracks[sprites])\n"
    "  point $VIBETRACKS_LPC_ASSETS at an LPC checkout to render against its assets."
)


class LPCError(RuntimeError):
    """Raised when the lpc engine is requested but unavailable or misconfigured."""


def available() -> bool:
    """True if Pillow imports (no exceptions) — used to gate rendering and tests."""
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def find_asset(source: str, cast_dir: str | None = None) -> str:
    """Resolve a layer's ``source`` to a real file.

    An absolute ``source`` is used as-is; a relative one is resolved against the
    cast's ``assets/`` directory, then against ``$VIBETRACKS_LPC_ASSETS``.
    """
    if os.path.isabs(source):
        if os.path.isfile(source):
            return source
        raise LPCError(f"layer asset not found: {source!r}")
    candidates = []
    if cast_dir:
        candidates.append(os.path.join(cast_dir, "assets", source))
    env = os.environ.get(ASSETS_ENV)
    if env:
        candidates.append(os.path.join(env, source))
    for c in candidates:
        if os.path.isfile(c):
            return c
    raise LPCError(
        f"layer asset {source!r} not found (looked in {candidates}).\n  {_INSTALL_HINT}")


def load_layer_sheet(path: str) -> np.ndarray:
    """Load an LPC layer PNG as an ``(h, w, 4)`` uint8 RGBA array.

    Palette-mode ("P") and other source modes are converted to RGBA so every layer
    composites uniformly.
    """
    try:
        from PIL import Image
    except ImportError as e:  # pragma: no cover - exercised only without Pillow
        raise LPCError(f"{e}\n  {_INSTALL_HINT}") from e
    with Image.open(path) as im:
        return np.asarray(im.convert("RGBA"), dtype=np.uint8)


def recolor(arr: np.ndarray, mapping: dict) -> np.ndarray:
    """Apply an LPC-style palette swap: ``{"#rrggbb": "#rrggbb", ...}``.

    Opaque source pixels matching a key colour are replaced by its value; alpha is
    preserved. This is the layer counterpart of a soundfont program change — same
    art, different colourway.
    """
    if not mapping:
        return arr
    out = arr.copy()
    rgb = out[..., :3]
    for src_hex, dst_hex in mapping.items():
        src = _hex_rgb(src_hex)
        dst = _hex_rgb(dst_hex)
        match = np.all(rgb == src, axis=-1)
        out[..., :3][match] = dst
    return out


def _hex_rgb(s: str) -> tuple:
    s = s.lstrip("#")
    if len(s) != 6:
        raise LPCError(f"recolor colour must be #rrggbb, got {s!r}")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
