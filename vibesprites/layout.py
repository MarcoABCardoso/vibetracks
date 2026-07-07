"""The LPC universal spritesheet geometry — the compile target.

Every LPC layer PNG is laid out on the same fixed grid of 64x64 frames: rows are
grouped by animation, each animation occupies one row per facing direction, and
columns run left-to-right through the animation's frames. Because every layer
shares this grid, compositing a character is just a per-pixel alpha-over of
same-size sheets in z-order — no per-frame scheduling is needed (contrast the
audio sequencer, which schedules notes on a beat timeline).

The **catalog** below is the full modern Universal-LPC animation set (the poses the
generator exports); the classic six (``spellcast``…``hurt``) are its first block and
remain the default so a cast only pays for the taller sheet if it opts into the
expanded poses (``jump``, ``climb``, ``run``…). Rows sit at their **canonical**
universal-sheet offsets — walk is always row 8, jump always row 26 — so a sheet
holding any subset stays compatible with every other LPC tool.

This module is pure data + geometry helpers: the constants every cast shares. It is
the sprite analogue of a fixed time-signature/tempo grid.
"""

from __future__ import annotations

FRAME = 64  # one animation frame is FRAME x FRAME pixels

# Facing directions, in the row order LPC sheets use within each animation block.
DIRECTIONS = ("up", "left", "down", "right")

# The full Universal-LPC animation catalog, in canonical row order. Each entry is
# (name, frames, directions): ``frames`` columns wide, one row per direction
# (``hurt``/``climb`` are single-row). Frame counts and order match the modern LPC
# generator's ANIMATION_CONFIGS/ANIMATION_OFFSETS (verified against real body art),
# so cumulative direction-rows reproduce its canonical y-offsets exactly.
ANIMATION_CATALOG = (
    ("spellcast", 7, 4),
    ("thrust", 8, 4),
    ("walk", 9, 4),
    ("slash", 6, 4),
    ("shoot", 13, 4),
    ("hurt", 6, 1),
    ("climb", 6, 1),
    ("idle", 2, 4),
    ("jump", 5, 4),
    ("sit", 3, 4),
    ("emote", 3, 4),
    ("run", 8, 4),
    ("combat_idle", 2, 4),
    ("backslash", 13, 4),
    ("halfslash", 6, 4),
)

_FRAMES = {name: frames for name, frames, _ in ANIMATION_CATALOG}
_DIRS = {name: dirs for name, _, dirs in ANIMATION_CATALOG}

# Canonical first-row of each animation block (cumulative direction-rows).
_CANON: dict = {}
_row = 0
for _name, _frames, _dirs in ANIMATION_CATALOG:
    _CANON[_name] = _row
    _row += _dirs
del _name, _frames, _dirs, _row

# The classic six-animation subset — the default a cast renders unless it opts into
# more. Keeping it the default preserves the 832x1344 sheet used before the catalog.
ANIMATIONS = ANIMATION_CATALOG[:6]
CLASSIC_ANIMATIONS = tuple(name for name, *_ in ANIMATIONS)

# Backward-compatible dimensions: the classic sheet everything defaulted to.
COLS = max(frames for _, frames, _ in ANIMATION_CATALOG)   # 13 (shoot / backslash)
ROWS = sum(dirs for _, _, dirs in ANIMATIONS)              # 21 (classic)
WIDTH = COLS * FRAME                                        # 832
HEIGHT = ROWS * FRAME                                       # 1344 (classic)
SHEET = (WIDTH, HEIGHT)


def animation_row(name: str) -> int:
    """First sheet row (0-indexed, in frames) of an animation's block, at its
    canonical universal-sheet offset (walk is always 8, jump always 26…)."""
    try:
        return _CANON[name]
    except KeyError:
        raise KeyError(f"unknown animation {name!r} "
                       f"(have {[a for a, *_ in ANIMATION_CATALOG]})")


def frames(name: str) -> int:
    """Number of frames (columns) in an animation."""
    return _FRAMES[name]


def directions(name: str) -> int:
    """Number of facing rows in an animation (4, or 1 for hurt/climb)."""
    return _DIRS[name]


def resolve_animations(names=None) -> tuple:
    """Normalize an animation selection to ``((name, frames, dirs), ...)``.

    ``None`` → the classic six. A list of names is validated against the catalog
    and returned **in canonical row order** (not the order given), so a sheet is
    always laid out top-to-bottom canonically regardless of how a cast lists them.
    """
    if names is None:
        return ANIMATIONS
    unknown = [n for n in names if n not in _FRAMES]
    if unknown:
        raise KeyError(f"unknown animation(s) {unknown} "
                       f"(have {[a for a, *_ in ANIMATION_CATALOG]})")
    chosen = set(names)
    return tuple(entry for entry in ANIMATION_CATALOG if entry[0] in chosen)


def sheet_rows(anims) -> int:
    """Frame-rows a sheet needs to hold ``anims`` at their canonical offsets."""
    return max((_CANON[name] + dirs) for name, _f, dirs in anims)


def sheet_size(anims) -> tuple:
    """(width, height) in pixels for a sheet holding ``anims``."""
    return (WIDTH, sheet_rows(anims) * FRAME)
