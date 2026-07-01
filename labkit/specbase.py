"""Shared spec primitives every Lab reuses.

A *Lab* (VibeTracks, PixelTracks, …) is the same machine with a different
theory: author a structured JSON spec, validate it cheaply, compile it
deterministically to an artifact. The two things every Lab needs from the very
bottom of that stack are a common error type and a JSON loader that turns parse
failures into that error — so a malformed spec reports the same way whether it
describes a song or a sprite. They live here so the error class is genuinely
*one* class across Labs, not a per-package copy.
"""

from __future__ import annotations

import json
import os


class SpecError(ValueError):
    """Raised when a spec is structurally or semantically invalid.

    Shared by every Lab so callers can catch one error type regardless of which
    Lab produced it.
    """


def load_json(path: str) -> dict:
    """Load JSON, raising :class:`SpecError` (with the path) on a parse error."""
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise SpecError(f"{path}: invalid JSON: {e}") from e


def extends_path(spec_path: str, data: dict) -> str | None:
    """Resolve a spec's ``extends`` to the file path it points at, or ``None``.

    Every Lab uses the same inheritance chain — a leaf spec ``extends`` its group
    bible, and a bible ``extends`` its world — and every link is a path
    relative to the *extending* file's directory. Factored here so the one
    convention lives in one place instead of being re-derived per Lab.
    """
    ext = data.get("extends")
    if not ext:
        return None
    return os.path.join(os.path.dirname(spec_path), ext)
