"""The exporter registry — the last mile that ships assets into a game engine.

The Labs (``labkit/registry.py``) turn JSON specs into raw artifacts (WAV, PNG);
an :class:`Exporter` wraps those artifacts into a resource pack a specific engine
can consume — Godot ``.tres``/``.import`` today, room for Tiled/Unity/… next.

This mirrors the :class:`~labkit.registry.Lab` pattern deliberately: adding an
engine is one :class:`Exporter` entry, exactly as adding a Lab is one ``Lab``
entry. VISION.md's roadmap item 2 ("make assets actually ship — exporters into
Godot … a unified build") is this module plus the ``build`` verb that drives it.

An exporter is a pure function of *records* — the structured per-asset data the
``build`` command collects while rendering (medium, group, name, the artifact in
``out/``, and any playback metadata: loop for music, fps/atlas for animation).
Consuming records rather than the ``out/`` manifests avoids a pre-existing quirk
(both Labs write ``out/<group>/manifest.json``, so a world sharing a group name
across media clobbers one), and keeps exporters engine-focused, not spec-aware.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Exporter:
    """One engine target: its name, a one-line description, and its entry point."""

    name: str
    summary: str           # one-line description for `python -m labs`
    entry: str             # "module:function"; func(records, dist_root, name) -> str

    def export(self, records, dist_root: str, name: str) -> str:
        """Import and invoke the exporter, returning the written pack directory.

        ``records`` maps a medium key (``"vibetracks"`` / ``"pixeltracks"``) to a
        ``{group: [asset record, ...]}`` map, exactly as produced by ``build``.
        """
        module_name, _, func_name = self.entry.partition(":")
        func: Callable = getattr(importlib.import_module(module_name), func_name)
        return func(records, dist_root, name)


# The engines this repo can ship to. Godot is the first target; new engines append
# here — the same "one entry" structural claim VISION.md makes for the Labs.
EXPORTERS = [
    Exporter(
        name="godot",
        summary="Godot 4 drop-in pack: PNG/WAV + .import, SpriteFrames .tres for animations.",
        entry="labkit.exporters.godot:export",
    ),
]

BY_NAME = {e.name: e for e in EXPORTERS}


def find_exporter(name: str) -> Exporter:
    try:
        return BY_NAME[name]
    except KeyError:
        raise SystemExit(f"unknown exporter {name!r} (engines: {list(BY_NAME)})")
