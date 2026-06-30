"""Grids and their leitmotif transforms.

A **grid** is the pixel motif's raw form: a list of equal-length strings, one per
row, where each character is a key into a *legend* (``char -> palette name``) and
``.`` / space mean transparent. It is the visual counterpart of a melodic motif's
note list, and ASCII-art-legible so a reviewer can read a sprite in a diff.

These functions are the pixel equivalents of VibeTracks' ``transpose`` /
``invert`` / ``retrograde`` / ``stretch``: ways to restate one motif as a related
variant instead of redrawing it. ``flip`` mirrors (the inversion move), ``rotate``
turns, ``scale`` enlarges (augmentation), and recolouring the legend is the
palette-swap. Same shape DNA, new pose — coherence by transformation.
"""

from __future__ import annotations


def normalize_grid(rows) -> list:
    """Validate a grid is a non-empty list of equal-length strings; return it.

    Raises :class:`ValueError` (no rows / ragged rows) so callers can report the
    location, mirroring how a malformed note list is rejected.
    """
    if not isinstance(rows, list) or not rows or not all(isinstance(r, str) for r in rows):
        raise ValueError("grid must be a non-empty list of strings")
    width = len(rows[0])
    if width == 0 or any(len(r) != width for r in rows):
        raise ValueError("grid rows must be non-empty and all the same length")
    return list(rows)


def grid_size(rows) -> tuple:
    """Return ``(width, height)`` of a grid."""
    return (len(rows[0]), len(rows))


def flip(rows, axis: str) -> list:
    """Mirror a grid. ``axis`` is ``"h"`` (left/right), ``"v"`` (up/down) or ``"hv"``."""
    out = list(rows)
    if "h" in axis:
        out = [r[::-1] for r in out]
    if "v" in axis:
        out = out[::-1]
    return out


def rotate(rows, degrees: int) -> list:
    """Rotate a grid clockwise by 0/90/180/270 degrees."""
    deg = degrees % 360
    if deg == 0:
        return list(rows)
    if deg == 180:
        return [r[::-1] for r in rows[::-1]]
    if deg == 90:  # clockwise: first column (bottom→top) becomes the top row
        return ["".join(rows[len(rows) - 1 - r][c] for r in range(len(rows)))
                for c in range(len(rows[0]))]
    if deg == 270:
        return ["".join(rows[r][len(rows[0]) - 1 - c] for r in range(len(rows)))
                for c in range(len(rows[0]))]
    raise ValueError(f"rotate degrees must be 0/90/180/270, got {degrees}")


def scale(rows, factor: int) -> list:
    """Integer nearest-neighbour upscale (augmentation): each cell -> factor×factor."""
    if not isinstance(factor, int) or factor < 1:
        raise ValueError(f"scale factor must be a positive int, got {factor!r}")
    if factor == 1:
        return list(rows)
    out = []
    for row in rows:
        wide = "".join(ch * factor for ch in row)
        out.extend([wide] * factor)
    return out


def recolor_legend(legend: dict, mapping: dict) -> dict:
    """Return a legend with its palette-name values remapped via ``mapping``.

    ``mapping`` is ``{palette_name: palette_name}``; unmentioned entries pass
    through. This is the palette-swap applied to one motif placement rather than
    the whole sprite — recolour the crest without touching the body.
    """
    return {ch: mapping.get(name, name) for ch, name in legend.items()}


# Transform order, applied like the music engine's retrograde→invert→transpose→
# stretch chain: mirror, then rotate, then scale. Documented so results are
# predictable when several are combined.
def transform_grid(rows, *, flip_axis=None, rotate_deg=0, scale_by=1) -> list:
    out = list(rows)
    if flip_axis:
        out = flip(out, flip_axis)
    if rotate_deg:
        out = rotate(out, rotate_deg)
    if scale_by and scale_by != 1:
        out = scale(out, scale_by)
    return out
