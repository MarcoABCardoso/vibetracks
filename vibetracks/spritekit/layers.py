"""Layer palette + engine dispatch — the sprite analogue of ``instruments.py``.

A character is a stack of named **layers** (body, hair, torso…), each drawn by an
**engine**. Just as an instrument patch's ``engine`` selects how a pitch becomes
sound (``NOTE_ENGINES`` render one note, ``PART_ENGINES`` render a whole part), a
layer patch's ``engine`` selects how a category becomes pixels:

* ``LAYER_ENGINES`` would draw a single layer from primitives — the seam for a
  future numpy ``procedural`` engine (not built yet), mirroring the synth engines.
* ``SHEET_ENGINES`` render a whole layer sheet at once from an external source.
  ``lpc`` is the one implemented here, mirroring the ``soundfont`` part engine.

``DEFAULT_PALETTE`` gives each common category a sane default z-order so a cast
only has to name the variants it wants; ``zPos`` is the drawing order (low =
behind), the visual counterpart of a mix's layering.
"""

from __future__ import annotations

# Default layer patches: category -> patch. ``zPos`` sets draw order (low behind
# high). A cast's bible overrides ``source``/``zPos``/``recolor`` per category.
DEFAULT_PALETTE = {
    "body":   {"engine": "lpc", "zPos": 10},
    "legs":   {"engine": "lpc", "zPos": 30},
    "feet":   {"engine": "lpc", "zPos": 40},
    "torso":  {"engine": "lpc", "zPos": 50},
    "hair":   {"engine": "lpc", "zPos": 80},
    "weapon": {"engine": "lpc", "zPos": 90},
}

# Engine dispatch tuples, mirroring instruments.NOTE_ENGINES / PART_ENGINES.
LAYER_ENGINES = ()            # future: procedural per-layer drawing (numpy)
SHEET_ENGINES = ("lpc",)      # render a whole layer sheet from source art
ENGINES = LAYER_ENGINES + SHEET_ENGINES  # the validation whitelist


def merge_patch(base: dict, override: dict | None) -> dict:
    """Shallow-merge ``override`` onto ``base`` (mirrors instruments.merge_patch)."""
    out = dict(base)
    if override:
        out.update(override)
    return out
