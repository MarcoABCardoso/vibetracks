"""Load and validate song specs (the JSON "model of a song").

Two kinds of file:

* **the bible** (``soundtrack.json``): global musical identity shared by every
  track — key, bpm, instrument ``palette``, reusable ``motifs``, ``tracks`` list.
* **a track** (``tracks/<name>.json``): one piece of music. A track may
  ``extends`` the bible to inherit its key/bpm/palette and may override them.

A resolved track is returned as a plain dict with the bible folded in, ready for
the sequencer. Validation raises :class:`SpecError` with a human-readable path.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from . import theory
from .instruments import DEFAULT_PALETTE, merge_patch

VALID_DRUM_CHARS = set("x.Xo-")  # x/X = hit, o = open (hat), '.'/'-' = rest


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
    if "notes" in part:
        _validate_note_events(part["notes"], where)
    elif "motif" in part:
        if part["motif"] not in track["motifs"]:
            raise SpecError(f"{where}: unknown motif {part['motif']!r} "
                            f"(motifs: {sorted(track['motifs'])})")
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
