"""Emit a **frame map** alongside a rendered sheet — the sprite analogue of a
soundtrack manifest, but per character.

A finished LPC sheet is just pixels: 832×1344 of them, laid out on the grid in
:mod:`vibesprites.layout`. That grid is common knowledge *inside* this package,
but a downstream consumer — a game engine, or a model that can't eyeball poses —
only receives the PNG. Nothing in the image says "rows 8–11 are the walk cycle,
facing up/left/down/right, nine frames each." This module writes that knowledge
out as a JSON sidecar so the layout ships *with* the art instead of living only in
code.

The map is derived entirely from :mod:`layout`, so it can never disagree with how
the sheet was actually composited — change the grid there and the atlas follows.
It is pure (no Pillow/numpy), so it is built and tested without any real art.

Schema (``<name>.atlas.json``)::

    {
      "image": "wanderer.png",
      "frame_size": [64, 64],
      "sheet_size": [832, 1344],
      "direction_order": ["up", "left", "down", "right"],
      "animations": {
        "walk": {"row": 8, "rows": 4, "frames": 9,
                 "directions": ["up", "left", "down", "right"]},
        "hurt": {"row": 20, "rows": 1, "frames": 6, "directions": ["*"]},
        ...
      },
      "frames": {
        "walk.down.3": {"x": 192, "y": 640, "w": 64, "h": 64},
        "hurt.0":      {"x": 0,   "y": 1280, "w": 64, "h": 64},
        ...
      }
    }

``animations`` is the compact, human/model-readable grid (compute any frame from
``row``/``frames``/``direction_order``); ``frames`` is the fully expanded lookup so
a consumer needs no arithmetic. Directional blocks key frames as
``<anim>.<direction>.<col>``; a single-row block (``hurt``, drawn once and not
split per facing — marked ``"directions": ["*"]``) keys them as ``<anim>.<col>``.
"""

from __future__ import annotations

from . import layout

#: Marker for a block that occupies one shared row rather than one row per facing.
NON_DIRECTIONAL = "*"


def build_atlas(image: str, anims=None) -> dict:
    """Build the frame-map dict for a sheet whose file name is ``image``.

    ``anims`` is the character's selected animation set (``((name, frames, dirs),
    …)`` as :func:`layout.resolve_animations` returns); ``None`` defaults to the
    classic six. Each block is placed at its **canonical** universal-sheet row
    (walk always 8, jump always 26…), so the map matches the grid the compositor
    drew — including empty bands when a subset skips an intervening block. Pure and
    Pillow-free.
    """
    anims = anims or layout.ANIMATIONS
    fw = fh = layout.FRAME
    order = list(layout.DIRECTIONS)

    animations: dict = {}
    frames: dict = {}
    for name, cols, dirs in anims:
        row = layout.animation_row(name)  # canonical offset, not packed
        directional = dirs == len(order)
        labels = order[:dirs] if directional else [NON_DIRECTIONAL]
        animations[name] = {
            "row": row,
            "rows": dirs,
            "frames": cols,
            "directions": labels,
        }
        for d in range(dirs):
            y = (row + d) * fh
            label = order[d] if directional else None
            for c in range(cols):
                key = f"{name}.{label}.{c}" if label else f"{name}.{c}"
                frames[key] = {"x": c * fw, "y": y, "w": fw, "h": fh}

    return {
        "image": image,
        "frame_size": [fw, fh],
        "sheet_size": list(layout.sheet_size(anims)),
        "direction_order": order,
        "animations": animations,
        "frames": frames,
    }
