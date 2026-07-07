"""Load and validate sprite specs — the JSON "model of a character".

Mirrors :mod:`vibetracks.spec` layer for layer:

* **a cast** (``sprites/<name>/``): one self-contained set of characters plus the
  layer art they share — the counterpart of a soundtrack *group*.
* **the charset** (``sprites/<name>/charset.json``): global visual identity shared
  by every character — frame size, the layer ``palette``, reusable ``outfits``,
  and the ordered ``characters`` list. The counterpart of the *bible*.
* **a character** (``sprites/<name>/characters/<c>.json``): one sprite. It may
  ``extends`` the charset to inherit its palette/outfits and override, then stacks
  ``layers``. The counterpart of a *track*.

A resolved character is returned as a plain dict with the charset folded in, ready
for the compositor. Validation raises :class:`SpriteSpecError` with a readable path.
Nothing here imports Pillow — validation works without the ``lpc`` engine's deps.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from . import layout
from .layers import DEFAULT_PALETTE, ENGINES, merge_patch
from .layout import FRAME

SPRITES_DIR = "sprites"          # where casts live (parallel to groups/)
CHARSET_FILE = "charset.json"
CHARACTERS_SUBDIR = "characters"


class SpriteSpecError(ValueError):
    """Raised when a sprite spec is structurally or visually invalid."""


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise SpriteSpecError(f"{path}: invalid JSON: {e}") from e


@dataclass
class Charset:
    path: str
    title: str = "Untitled Cast"
    style: str = "lpc"
    frame: list = field(default_factory=lambda: [FRAME, FRAME])
    palette: dict = field(default_factory=dict)
    outfits: dict = field(default_factory=dict)
    characters: list = field(default_factory=list)
    remote: str | None = None  # base URL layer art is fetched from (see lpc.py)
    animations: list | None = None  # animation subset (default: the classic six)

    def resolved_palette(self) -> dict:
        """Palette defaults merged with the charset's per-category overrides."""
        out = {}
        names = set(DEFAULT_PALETTE) | set(self.palette)
        for name in names:
            out[name] = merge_patch(DEFAULT_PALETTE.get(name, {}),
                                    self.palette.get(name))
        return out


def load_charset(path: str) -> Charset:
    data = load_json(path)
    cs = Charset(
        path=path,
        title=data.get("title", "Untitled Cast"),
        style=data.get("style", "lpc"),
        frame=data.get("frame", [FRAME, FRAME]),
        palette=data.get("palette", {}),
        outfits=data.get("outfits", {}),
        characters=data.get("characters", []),
        remote=data.get("remote"),
        animations=data.get("animations"),
    )
    _validate_charset(cs)
    return cs


def _resolve_animation_set(names, where: str) -> tuple:
    """Validate an animation selection into ``((name, frames, dirs), ...)``."""
    try:
        return layout.resolve_animations(names)
    except KeyError as e:
        raise SpriteSpecError(f"{where}: {e}") from e


def _validate_frame(frame, where: str) -> None:
    if not (isinstance(frame, (list, tuple)) and len(frame) == 2
            and all(isinstance(n, int) and n > 0 for n in frame)):
        raise SpriteSpecError(f"{where}: frame must be [w, h] positive ints, got {frame!r}")


def _validate_palette(palette: dict, where: str) -> None:
    for name, patch in palette.items():
        engine = patch.get("engine")
        if engine is not None and engine not in ENGINES:
            raise SpriteSpecError(f"{where}: layer {name!r} has unknown engine "
                                  f"{engine!r} (valid: {list(ENGINES)})")


def _validate_charset(cs: Charset) -> None:
    _validate_frame(cs.frame, cs.path)
    _validate_palette(cs.resolved_palette(), cs.path)
    _resolve_animation_set(cs.animations, cs.path)  # reject unknown animation names
    if cs.remote is not None and not (isinstance(cs.remote, str)
                                      and cs.remote.startswith(("http://", "https://"))):
        raise SpriteSpecError(f"{cs.path}: 'remote' must be an http(s) URL, got {cs.remote!r}")
    # Outfit definitions are lists of concrete layer entries.
    for name, entries in cs.outfits.items():
        if not isinstance(entries, list) or not entries:
            raise SpriteSpecError(f"{cs.path}: outfit {name!r} must be a non-empty list")
        for entry in entries:
            if "variant" not in entry or "layer" not in entry:
                raise SpriteSpecError(f"{cs.path}: outfit {name!r} entries need "
                                      f"'layer' and 'variant', got {entry!r}")


def resolve_character(path: str, charset: Charset | None = None) -> dict:
    """Load a character spec and fold in the charset it ``extends`` (if any)."""
    data = load_json(path)
    name = data.get("name", os.path.splitext(os.path.basename(path))[0])

    if charset is None and data.get("extends"):
        charset_path = os.path.join(os.path.dirname(path), data["extends"])
        charset = load_charset(charset_path)

    frame = data.get("frame", charset.frame if charset else [FRAME, FRAME])
    palette = charset.resolved_palette() if charset else {
        k: merge_patch(v, None) for k, v in DEFAULT_PALETTE.items()}
    outfits = dict(charset.outfits) if charset else {}

    # Per-character palette overrides merge on top of the charset's palette.
    for cat, override in (data.get("palette") or {}).items():
        palette[cat] = merge_patch(palette.get(cat, {}), override)

    anim_names = data.get("animations", charset.animations if charset else None)

    resolved = {
        "name": name,
        "frame": frame,
        "palette": palette,
        "outfits": outfits,
        "remote": data.get("remote", charset.remote if charset else None),
        "animations": _resolve_animation_set(anim_names, path),
        "layers": data.get("layers", []),
    }
    _validate_character(resolved, path)
    return resolved


def compiled_spec(character: dict) -> dict:
    """A JSON-friendly, self-contained copy of a resolved character.

    This is the *compiled* spec — the charset already folded in, so it needs no
    ``extends`` — written beside the rendered sheet so the output ships with the
    exact recipe that produced it. ``animations`` is flattened from the internal
    ``(name, frames, dirs)`` tuples back to the ordered list of names.
    """
    out = {
        "name": character["name"],
        "frame": list(character["frame"]),
        "animations": [name for name, _f, _d in character["animations"]],
        "palette": character["palette"],
        "outfits": character.get("outfits", {}),
        "layers": character["layers"],
    }
    if character.get("remote"):
        out["remote"] = character["remote"]
    return out


def _validate_character(c: dict, path: str) -> None:
    _validate_frame(c["frame"], path)
    _validate_palette(c["palette"], path)
    if not c["layers"]:
        raise SpriteSpecError(f"{path}: character has no layers")
    for i, entry in enumerate(c["layers"]):
        _validate_layer(entry, c, where=f"{path}: layer {i}")


def _validate_layer(entry: dict, character: dict, where: str) -> None:
    kinds = [k for k in ("variant", "outfit") if k in entry]
    if len(kinds) != 1:
        raise SpriteSpecError(f"{where}: a layer needs exactly one of "
                              f"variant/outfit, found {kinds}")
    if "zPos" in entry and not isinstance(entry["zPos"], (int, float)):
        raise SpriteSpecError(f"{where}: 'zPos' must be a number, got {entry['zPos']!r}")
    _validate_recolor(entry.get("recolor"), where)
    _validate_assemble(entry.get("assemble"), where)
    if "variant" in entry:
        cat = entry.get("layer")
        if cat is None:
            raise SpriteSpecError(f"{where}: a variant layer needs a 'layer' category")
        if cat not in character["palette"]:
            raise SpriteSpecError(f"{where}: unknown layer {cat!r} "
                                  f"(palette: {sorted(character['palette'])})")
    else:  # outfit
        if entry["outfit"] not in character["outfits"]:
            raise SpriteSpecError(f"{where}: unknown outfit {entry['outfit']!r} "
                                  f"(outfits: {sorted(character['outfits'])})")


def _validate_assemble(assemble, where: str) -> None:
    if assemble is None:
        return
    if not isinstance(assemble, dict) or not isinstance(assemble.get("base"), str):
        raise SpriteSpecError(f"{where}: 'assemble' needs a string 'base'")
    # 'color' is optional: present -> <base>/<anim>/<color>.png (color-split art,
    # e.g. robes); absent -> <base>/<anim>.png (a recolorable single sheet, e.g.
    # bodies/armour, tinted via a palette 'recolor').
    if assemble.get("color") is not None and not isinstance(assemble["color"], str):
        raise SpriteSpecError(f"{where}: 'assemble.color' must be a string when set")


def _validate_recolor(recolor, where: str) -> None:
    if recolor is None:
        return
    if not isinstance(recolor, dict):
        raise SpriteSpecError(f"{where}: 'recolor' must be a map of #rrggbb -> #rrggbb")
    for src, dst in recolor.items():
        for h in (src, dst):
            s = str(h).lstrip("#")
            if len(s) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in s):
                raise SpriteSpecError(f"{where}: bad recolor colour {h!r} (want #rrggbb)")


# --- Casts ---------------------------------------------------------------- #

@dataclass
class Cast:
    """One self-contained sprite set: a charset plus its characters directory.

    Lives in ``sprites/<name>/`` with its own ``charset.json`` and ``characters/``
    folder, alongside the ``assets/`` art it composites. The sprite counterpart of
    a soundtrack :class:`~vibetracks.spec.Group`.
    """
    name: str
    dir: str

    @property
    def charset_path(self) -> str:
        return os.path.join(self.dir, CHARSET_FILE)

    @property
    def characters_dir(self) -> str:
        return os.path.join(self.dir, CHARACTERS_SUBDIR)

    def load_charset(self) -> Charset | None:
        return load_charset(self.charset_path) if os.path.isfile(self.charset_path) else None

    def character_path(self, name: str) -> str:
        """Resolve a bare character name (or a path) to its JSON file in the cast."""
        if name.endswith(".json") or os.path.sep in name:
            return name
        return os.path.join(self.characters_dir, f"{name}.json")

    def character_names(self) -> list:
        """Ordered names: the charset's ``characters`` list, else ``characters/*.json``."""
        cs = self.load_charset()
        if cs and cs.characters:
            return list(cs.characters)
        if os.path.isdir(self.characters_dir):
            return [os.path.splitext(f)[0]
                    for f in sorted(os.listdir(self.characters_dir))
                    if f.endswith(".json")]
        return []


def discover_casts(root: str = ".") -> list:
    """Find every sprite cast under ``root`` (parallels ``discover_groups``)."""
    casts = []
    sdir = os.path.join(root, SPRITES_DIR)
    if os.path.isdir(sdir):
        for name in sorted(os.listdir(sdir)):
            d = os.path.join(sdir, name)
            if os.path.isfile(os.path.join(d, CHARSET_FILE)):
                casts.append(Cast(name=name, dir=d))
    if not casts and os.path.isfile(os.path.join(root, CHARSET_FILE)):
        casts.append(Cast(name="default", dir=root))
    return casts


def find_cast(name: str, root: str = ".") -> Cast:
    """Look up a cast by name, raising :class:`SpriteSpecError` if unknown."""
    casts = discover_casts(root)
    for c in casts:
        if c.name == name:
            return c
    raise SpriteSpecError(f"unknown cast {name!r} (casts: {[c.name for c in casts]})")
