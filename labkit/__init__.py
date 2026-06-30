"""labkit — the shared core every VibeTracks Lab is built from.

VISION.md frames this repo as a set of *Labs*: structured spec → validate →
compile → iterate workshops, one per artifact class (music, sprites, tiles, …).
labkit holds the parts that are the *same* in every Lab — the error type, JSON
loading, group discovery, and the Lab registry — so each Lab adds only its own
"theory" (a model, a validator, a deterministic engine) on top.
"""

from __future__ import annotations

from .groups import Group, discover_group_dirs
from .registry import LABS, Lab, find_lab
from .specbase import SpecError, load_json

__all__ = [
    "SpecError",
    "load_json",
    "Group",
    "discover_group_dirs",
    "Lab",
    "LABS",
    "find_lab",
]
