"""The Lab registry — what makes this repo a multi-Lab workshop.

Every Lab ships a CLI with the same verbs (``validate`` / ``render`` /
``render-all`` / ``new`` / ``new-group``) over its own artifact class. The
registry records each Lab's name, one-line description, asset layout, and CLI
entry point so a single dispatcher (``python -m labs``) can list the Labs and
forward to any of them. Adding a Lab is one :class:`Lab` entry — the structural
claim of VISION.md that "every Lab is the same machine with a different theory."
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Lab:
    """One artifact workshop: its identity, asset layout, and CLI entry point."""

    name: str
    artifact: str          # what it compiles, e.g. "music / SFX", "sprites"
    summary: str           # one-line description for `python -m labs`
    assets_dir: str        # where this Lab's groups live, e.g. "groups/music"
    bible_file: str        # the per-group bible filename
    specs_subdir: str      # the per-group specs subfolder
    entry: str             # "module:function" returning an int exit code

    def main(self, argv) -> int:
        """Import and invoke the Lab's CLI ``main(argv)``."""
        module_name, _, func_name = self.entry.partition(":")
        func: Callable = getattr(importlib.import_module(module_name), func_name)
        return func(argv)


# The Labs this repo ships. VibeTracks is Lab 0 (the proof); PixelTracks is the
# second Lab built on the same labkit core. New Labs append here.
LABS = [
    Lab(
        name="vibetracks",
        artifact="music / SFX",
        summary="Game soundtracks: JSON song specs compiled to WAV by a pure-Python synth.",
        assets_dir="groups/music",
        bible_file="soundtrack.json",
        specs_subdir="tracks",
        entry="vibetracks.__main__:main",
    ),
    Lab(
        name="pixeltracks",
        artifact="sprites / images",
        summary="Pixel-art sprites: JSON sprite specs compiled to PNG by a procedural raster engine. (Early work — results are limited.)",
        assets_dir="groups/sprites",
        bible_file="artbook.json",
        specs_subdir="sprites",
        entry="pixeltracks.__main__:main",
    ),
]

BY_NAME = {lab.name: lab for lab in LABS}


def find_lab(name: str) -> Lab:
    try:
        return BY_NAME[name]
    except KeyError:
        raise SystemExit(f"unknown lab {name!r} (labs: {list(BY_NAME)})")
