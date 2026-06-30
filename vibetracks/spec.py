"""Load and validate song specs (the JSON "model of a song").

Three layers:

* **a group** (``groups/<name>/``): one self-contained soundtrack — its own
  bible plus tracks. Groups let a single repo hold several independent scores
  (different regions of a game, or different games entirely) without sharing or
  overwriting one top-level bible.
* **the bible** (``groups/<name>/soundtrack.json``): global musical identity
  shared by every track in the group — key, bpm, instrument ``palette``,
  reusable ``motifs``, ``tracks`` list.
* **a track** (``groups/<name>/tracks/<track>.json``): one piece of music. A
  track may ``extends`` the bible to inherit its key/bpm/palette and override.

A resolved track is returned as a plain dict with the bible folded in, ready for
the sequencer. Validation raises :class:`SpecError` with a human-readable path.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from . import theory
from .instruments import DEFAULT_PALETTE, ENGINES, merge_patch

VALID_DRUM_CHARS = set("x.Xo-")  # x/X = hit, o = open (hat), '.'/'-' = rest

GROUPS_DIR = "groups"        # where soundtrack groups live
BIBLE_FILE = "soundtrack.json"
TRACKS_SUBDIR = "tracks"


class SpecError(ValueError):
    """Raised when a spec is structurally or musically invalid."""


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise SpecError(f"{path}: invalid JSON: {e}") from e


@dataclass
class Bible:
    path: str
    title: str = "Untitled Soundtrack"
    key: str = "A minor"
    bpm: float = 110.0
    aesthetic: str = "synthwave"
    palette: dict = field(default_factory=dict)
    motifs: dict = field(default_factory=dict)
    tracks: list = field(default_factory=list)

    def resolved_palette(self) -> dict:
        """Palette defaults merged with the bible's per-instrument overrides."""
        out = {}
        names = set(DEFAULT_PALETTE) | set(self.palette)
        for name in names:
            out[name] = merge_patch(DEFAULT_PALETTE.get(name, {}),
                                    self.palette.get(name))
        return out


def load_bible(path: str) -> Bible:
    data = load_json(path)
    bible = Bible(
        path=path,
        title=data.get("title", "Untitled Soundtrack"),
        key=data.get("key", "A minor"),
        bpm=float(data.get("bpm", 110)),
        aesthetic=data.get("aesthetic", "synthwave"),
        palette=data.get("palette", {}),
        motifs=data.get("motifs", {}),
        tracks=data.get("tracks", []),
    )
    _validate_bible(bible)
    return bible


def _validate_bible(b: Bible) -> None:
    try:
        theory.parse_key(b.key)
    except ValueError as e:
        raise SpecError(f"{b.path}: bad key {b.key!r}: {e}") from e
    if b.bpm <= 0:
        raise SpecError(f"{b.path}: bpm must be positive")
    for name, motif in b.motifs.items():
        notes = motif.get("notes", motif) if isinstance(motif, dict) else motif
        _validate_note_events(notes, where=f"{b.path}: motif {name!r}")


def _validate_note_events(events, where: str) -> None:
    if not isinstance(events, list):
        raise SpecError(f"{where}: notes must be a list of [pitch, beats, vel?]")
    for ev in events:
        if not isinstance(ev, (list, tuple)) or len(ev) < 2:
            raise SpecError(f"{where}: bad note event {ev!r} (need [pitch, beats])")
        pitch, beats = ev[0], ev[1]
        if pitch is not None:  # None == a rest
            try:
                theory.note_to_midi(pitch)
            except ValueError as e:
                raise SpecError(f"{where}: bad pitch {pitch!r}: {e}") from e
        if not isinstance(beats, (int, float)) or beats <= 0:
            raise SpecError(f"{where}: beats must be a positive number, got {beats!r}")


def resolve_track(path: str, bible: Bible | None = None) -> dict:
    """Load a track spec and fold in the bible it ``extends`` (if any)."""
    data = load_json(path)
    name = data.get("name", os.path.splitext(os.path.basename(path))[0])

    # Resolve the bible the track extends, if not supplied.
    if bible is None and data.get("extends"):
        bible_path = os.path.join(os.path.dirname(path), data["extends"])
        bible = load_bible(bible_path)

    base_key = bible.key if bible else "A minor"
    base_bpm = bible.bpm if bible else 110.0
    palette = bible.resolved_palette() if bible else {
        k: merge_patch(v, None) for k, v in DEFAULT_PALETTE.items()}
    motifs = dict(bible.motifs) if bible else {}

    # Per-track palette overrides merge on top of the bible's palette.
    for inst, override in (data.get("palette") or {}).items():
        palette[inst] = merge_patch(palette.get(inst, {}), override)

    resolved = {
        "name": name,
        "key": data.get("key", base_key),
        "bpm": float(data.get("bpm", base_bpm)),
        "time_signature": data.get("time_signature", [4, 4]),
        "sections": data.get("sections", []),
        "palette": palette,
        "motifs": motifs,
        "loops": data.get("loops"),  # default loop repeats; CLI can override
    }
    _validate_track(resolved, path)
    return resolved


def _validate_track(t: dict, path: str) -> None:
    try:
        theory.parse_key(t["key"])
    except ValueError as e:
        raise SpecError(f"{path}: bad key {t['key']!r}: {e}") from e
    if t["bpm"] <= 0:
        raise SpecError(f"{path}: bpm must be positive")
    if not t["sections"]:
        raise SpecError(f"{path}: track has no sections")

    for name, patch in t["palette"].items():
        engine = patch.get("engine")
        if engine is not None and engine not in ENGINES:
            raise SpecError(f"{path}: instrument {name!r} has unknown engine "
                            f"{engine!r} (valid: {list(ENGINES)})")

    for si, section in enumerate(t["sections"]):
        where = f"{path}: section {section.get('name', si)!r}"
        if "bars" not in section or section["bars"] <= 0:
            raise SpecError(f"{where}: needs a positive 'bars'")
        parts = section.get("parts", {})
        if not isinstance(parts, dict):
            raise SpecError(f"{where}: 'parts' must be an object")
        for pname, part in parts.items():
            _validate_part(part, t, where=f"{where}: part {pname!r}")


def _validate_part(part: dict, track: dict, where: str) -> None:
    inst = part.get("instrument")
    if inst is None:
        raise SpecError(f"{where}: missing 'instrument'")
    if inst not in track["palette"]:
        raise SpecError(f"{where}: unknown instrument {inst!r} "
                        f"(palette: {sorted(track['palette'])})")
    kinds = [k for k in ("notes", "motif", "chords", "drums") if k in part]
    if len(kinds) != 1:
        raise SpecError(f"{where}: a part needs exactly one of "
                        f"notes/motif/chords/drums, found {kinds}")
    if "stretch" in part and not (isinstance(part["stretch"], (int, float))
                                  and part["stretch"] > 0):
        raise SpecError(f"{where}: 'stretch' must be a positive number")
    inv = part.get("invert")
    if isinstance(inv, str):
        try:
            theory.note_to_midi(inv)
        except ValueError as e:
            raise SpecError(f"{where}: 'invert' pivot {inv!r} is not a note: {e}") from e
    if "notes" in part:
        _validate_note_events(part["notes"], where)
    elif "motif" in part:
        if part["motif"] not in track["motifs"]:
            raise SpecError(f"{where}: unknown motif {part['motif']!r} "
                            f"(motifs: {sorted(track['motifs'])})")
        sl = part.get("slice")
        if sl is not None and not (isinstance(sl, list) and len(sl) == 2
                                   and all(isinstance(i, int) for i in sl)):
            raise SpecError(f"{where}: 'slice' must be [start, end] integers")
    elif "chords" in part:
        for sym in part["chords"]:
            try:
                theory.chord_notes(sym)
            except ValueError as e:
                raise SpecError(f"{where}: bad chord {sym!r}: {e}") from e
    elif "drums" in part:
        for voice, pattern in part["drums"].items():
            bad = set(pattern) - VALID_DRUM_CHARS
            if bad:
                raise SpecError(f"{where}: drum voice {voice!r} has bad chars {bad}")


# --- Groups --------------------------------------------------------------- #

@dataclass
class Group:
    """One self-contained soundtrack: a bible plus its tracks directory.

    A group lives in ``groups/<name>/`` with its own ``soundtrack.json`` and
    ``tracks/`` folder. Several groups coexist in one repo without sharing or
    overwriting a single top-level bible, so users can spin up their own score
    alongside the bundled demo.
    """
    name: str
    dir: str

    @property
    def bible_path(self) -> str:
        return os.path.join(self.dir, BIBLE_FILE)

    @property
    def tracks_dir(self) -> str:
        return os.path.join(self.dir, TRACKS_SUBDIR)

    def load_bible(self) -> Bible | None:
        return load_bible(self.bible_path) if os.path.isfile(self.bible_path) else None

    def track_path(self, name: str) -> str:
        """Resolve a bare track name (or a path) to its JSON file in the group."""
        if name.endswith(".json") or os.path.sep in name:
            return name
        return os.path.join(self.tracks_dir, f"{name}.json")

    def track_names(self) -> list:
        """Ordered track names: the bible's ``tracks`` list, else ``tracks/*.json``."""
        bible = self.load_bible()
        if bible and bible.tracks:
            return list(bible.tracks)
        if os.path.isdir(self.tracks_dir):
            return [os.path.splitext(f)[0]
                    for f in sorted(os.listdir(self.tracks_dir))
                    if f.endswith(".json")]
        return []


def discover_groups(root: str = ".") -> list:
    """Find every soundtrack group under ``root``.

    Each subdirectory of ``groups/`` that holds a ``soundtrack.json`` is a group,
    returned sorted by name. For backward compatibility a ``soundtrack.json`` at
    ``root`` itself is exposed as the ``default`` group when there is no
    ``groups/`` directory.
    """
    groups = []
    gdir = os.path.join(root, GROUPS_DIR)
    if os.path.isdir(gdir):
        for name in sorted(os.listdir(gdir)):
            d = os.path.join(gdir, name)
            if os.path.isfile(os.path.join(d, BIBLE_FILE)):
                groups.append(Group(name=name, dir=d))
    if not groups and os.path.isfile(os.path.join(root, BIBLE_FILE)):
        groups.append(Group(name="default", dir=root))
    return groups


def find_group(name: str, root: str = ".") -> Group:
    """Look up a group by name, raising :class:`SpecError` if it is unknown."""
    groups = discover_groups(root)
    for g in groups:
        if g.name == name:
            return g
    raise SpecError(f"unknown group {name!r} "
                    f"(groups: {[g.name for g in groups]})")
