"""The LPC universal spritesheet geometry — the compile target.

Every LPC layer PNG is laid out on the same fixed grid of 64x64 frames: rows are
grouped by animation, each animation occupies one row per facing direction, and
columns run left-to-right through the animation's frames. Because every layer
shares this grid, compositing a character is just a per-pixel alpha-over of
same-size sheets in z-order — no per-frame scheduling is needed (contrast the
audio sequencer, which schedules notes on a beat timeline).

This module is pure data: the constants every cast shares. It is the sprite
analogue of a fixed time-signature/tempo grid.
"""

from __future__ import annotations

FRAME = 64  # one animation frame is FRAME x FRAME pixels

# Facing directions, in the row order LPC sheets use within each animation block.
DIRECTIONS = ("up", "left", "down", "right")

# The classic Universal-LPC layout. Each entry is (name, frames, directions):
# ``frames`` columns wide, one row per direction (``hurt`` is a single row).
ANIMATIONS = (
    ("spellcast", 7, 4),
    ("thrust", 8, 4),
    ("walk", 9, 4),
    ("slash", 6, 4),
    ("shoot", 13, 4),
    ("hurt", 6, 1),
)

# Sheet dimensions fall out of the layout: width = widest animation, height =
# total rows. 13 cols x 21 rows x 64 px = 832 x 1344.
COLS = max(frames for _, frames, _ in ANIMATIONS)          # 13
ROWS = sum(dirs for _, _, dirs in ANIMATIONS)              # 21
WIDTH = COLS * FRAME                                        # 832
HEIGHT = ROWS * FRAME                                       # 1344
SHEET = (WIDTH, HEIGHT)


def animation_row(name: str) -> int:
    """Return the first sheet row (0-indexed, in frames) of an animation block."""
    row = 0
    for anim, _frames, dirs in ANIMATIONS:
        if anim == name:
            return row
        row += dirs
    raise KeyError(f"unknown animation {name!r} (have {[a for a, *_ in ANIMATIONS]})")
