"""Generic *group* discovery shared by every Lab.

A **group** is one self-contained, coherent unit of work — a soundtrack in
VibeTracks, a sprite set in PixelTracks. Each lives in its own directory holding
a *bible* (the shared identity) plus a folder of *specs* (the individual
artifacts). The directory convention is identical across Labs; only the bible
filename and the specs subfolder differ, so the discovery logic is factored out
here and parameterized rather than copied per Lab.

    <assets_dir>/<group>/<bible_file>     # the group's bible
    <assets_dir>/<group>/<specs_subdir>/  # one .json spec per artifact
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Group:
    """A bible plus its specs directory, addressed by ``name``.

    Subclasses (or callers) set ``bible_file``/``specs_subdir`` for their Lab and
    add a ``load_bible`` that knows how to parse that Lab's bible.
    """

    name: str
    dir: str
    bible_file: str = "bible.json"
    specs_subdir: str = "specs"

    @property
    def bible_path(self) -> str:
        return os.path.join(self.dir, self.bible_file)

    @property
    def specs_dir(self) -> str:
        return os.path.join(self.dir, self.specs_subdir)

    def spec_path(self, name: str) -> str:
        """Resolve a bare spec name (or a path) to its JSON file in the group."""
        if name.endswith(".json") or os.path.sep in name:
            return name
        return os.path.join(self.specs_dir, f"{name}.json")

    def spec_files(self) -> list:
        """All ``<specs_subdir>/*.json`` names on disk, sorted (no bible order)."""
        if not os.path.isdir(self.specs_dir):
            return []
        return [os.path.splitext(f)[0]
                for f in sorted(os.listdir(self.specs_dir))
                if f.endswith(".json")]


def discover_group_dirs(assets_dir: str, bible_file: str) -> list:
    """Return ``(name, dir)`` for each subdir of ``assets_dir`` holding a bible.

    Sorted by name. This is the modality-agnostic half of group discovery; a Lab
    wraps it to build its own :class:`Group` subclass and to add any
    backward-compatible fallbacks (e.g. a bible at the repo root).
    """
    out = []
    if os.path.isdir(assets_dir):
        for name in sorted(os.listdir(assets_dir)):
            d = os.path.join(assets_dir, name)
            if os.path.isfile(os.path.join(d, bible_file)):
                out.append((name, d))
    return out
