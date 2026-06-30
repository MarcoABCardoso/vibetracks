"""Load and validate sprite specs (the JSON "model of a sprite").

The same three layers as VibeTracks, in a different medium:

* **a group** (``art/<name>/``): one self-contained sprite set — its own bible
  plus sprites — so a repo can hold several independent visual identities.
* **the bible** (``art/<name>/artbook.json``): the visual identity shared by
  every sprite in the group — canvas ``size``, the colour ``palette``, reusable
  shape ``motifs``, an optional ``outline``/``background``, and the ``sprites``
  list.
* **a sprite** (``art/<name>/sprites/<sprite>.json``): one image. It ``extends``
  the bible to inherit size/palette/motifs, and may override them.

A resolved sprite is a plain dict with the bible folded in and the palette turned
into RGBA, ready for the compositor. Validation raises :class:`SpecError` with a
human-readable path — the cheap "does it adhere to the palette / is it a valid
grid" check before any pixels are drawn, mirroring music's pre-render validation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from labkit.groups import Group as _GroupBase
from labkit.groups import discover_group_dirs
from labkit.specbase import SpecError, load_json  # shared across Labs

from . import palette, shapes

ART_DIR = "art"                  # where sprite groups live
BIBLE_FILE = "artbook.json"
SPRITES_SUBDIR = "sprites"

PRIMITIVES = ("pixels", "shape", "rect", "ellipse", "line")
TRANSPARENT_CHARS = set(". ")

__all__ = ["SpecError", "load_json", "Bible", "load_bible", "resolve_sprite",
           "Group", "discover_groups", "find_group"]


@dataclass
class Bible:
    path: str
    title: str = "Untitled Artbook"
    aesthetic: str = "pixel-art"
    size: tuple = (16, 16)
    scale: int = 16
    palette: dict = field(default_factory=dict)      # name -> "#hex"
    ramps: dict = field(default_factory=dict)        # name -> [palette name, ...]
    motifs: dict = field(default_factory=dict)       # name -> {legend, pixels}
    background: object = None                        # palette name or None
    outline: object = None                           # {"color": name} or None
    sprites: list = field(default_factory=list)

    def resolved_palette(self) -> dict:
        """The bible palette as ``{name: (r, g, b, a)}``."""
        return palette.resolve_palette(self.palette)


def load_bible(path: str) -> Bible:
    data = load_json(path)
    size = data.get("size", [16, 16])
    bible = Bible(
        path=path,
        title=data.get("title", "Untitled Artbook"),
        aesthetic=data.get("aesthetic", "pixel-art"),
        size=tuple(size),
        scale=int(data.get("scale", 16)),
        palette=data.get("palette", {}),
        ramps=data.get("ramps", {}),
        motifs=data.get("motifs", {}),
        background=data.get("background"),
        outline=data.get("outline"),
        sprites=data.get("sprites", []),
    )
    _validate_bible(bible)
    return bible


def _check_size(size, where: str) -> None:
    if (not isinstance(size, (list, tuple)) or len(size) != 2
            or not all(isinstance(v, int) and v > 0 for v in size)):
        raise SpecError(f"{where}: size must be [width, height] positive ints, got {size!r}")


def _validate_motif(name, motif, names, where) -> None:
    if not isinstance(motif, dict) or "pixels" not in motif:
        raise SpecError(f"{where}: motif {name!r} needs a 'pixels' grid")
    legend = motif.get("legend", {})
    try:
        shapes.normalize_grid(motif["pixels"])
    except ValueError as e:
        raise SpecError(f"{where}: motif {name!r}: {e}") from e
    _check_legend(legend, motif["pixels"], names, f"{where}: motif {name!r}")


def _check_legend(legend, rows, palette_names, where) -> None:
    """Every legend value must be a known colour; every grid char must be legible."""
    if not isinstance(legend, dict):
        raise SpecError(f"{where}: 'legend' must be a map of char -> colour name")
    for ch, cname in legend.items():
        if cname not in palette_names:
            raise SpecError(f"{where}: legend {ch!r} -> {cname!r} is not in the palette "
                            f"(palette: {sorted(palette_names)})")
    used = {ch for row in rows for ch in row} - TRANSPARENT_CHARS
    unknown = used - set(legend)
    if unknown:
        raise SpecError(f"{where}: grid uses char(s) {sorted(unknown)} absent from the legend")


def _validate_bible(b: Bible) -> None:
    _check_size(b.size, b.path)
    if not (isinstance(b.scale, int) and b.scale >= 1):
        raise SpecError(f"{b.path}: scale must be a positive int")
    try:
        names = set(b.resolved_palette())
    except ValueError as e:
        raise SpecError(f"{b.path}: {e}") from e
    if b.background is not None and b.background not in names:
        raise SpecError(f"{b.path}: background {b.background!r} is not a palette colour")
    _check_outline(b.outline, names, b.path)
    for cname, ramp in b.ramps.items():
        bad = [c for c in ramp if c not in names]
        if bad:
            raise SpecError(f"{b.path}: ramp {cname!r} references unknown colours {bad}")
    for name, motif in b.motifs.items():
        _validate_motif(name, motif, names, b.path)


def _check_outline(outline, names, where) -> None:
    if outline is None:
        return
    if not isinstance(outline, dict) or "color" not in outline:
        raise SpecError(f"{where}: outline must be {{'color': <palette name>}}")
    if outline["color"] not in names:
        raise SpecError(f"{where}: outline colour {outline['color']!r} is not in the palette")


# --- Sprite resolution ------------------------------------------------------- #

def resolve_sprite(path: str, bible: Bible | None = None) -> dict:
    """Load a sprite spec and fold in the bible it ``extends`` (if any)."""
    data = load_json(path)
    name = data.get("name", os.path.splitext(os.path.basename(path))[0])

    if bible is None and data.get("extends"):
        bible = load_bible(os.path.join(os.path.dirname(path), data["extends"]))

    colours = dict(bible.palette) if bible else {}
    colours.update(data.get("palette", {}))          # per-sprite palette override
    motifs = dict(bible.motifs) if bible else {}
    motifs.update(data.get("motifs", {}))

    # Normalise to a list of frames; a still sprite is a single frame.
    if data.get("frames"):
        frames = [dict(f) for f in data["frames"]]
    else:
        frames = [{"name": "frame0", "layers": data.get("layers", [])}]

    resolved = {
        "name": name,
        "size": tuple(data.get("size", bible.size if bible else (16, 16))),
        "scale": int(data.get("scale", bible.scale if bible else 16)),
        "palette": palette.resolve_palette(colours),
        "background": data.get("background", bible.background if bible else None),
        "outline": data.get("outline", bible.outline if bible else None),
        "legend": data.get("legend", {}),   # sprite-level default for pixels layers
        "motifs": motifs,
        "frames": frames,
    }
    _validate_sprite(resolved, path)
    return resolved


def _validate_sprite(s: dict, path: str) -> None:
    _check_size(s["size"], path)
    names = set(s["palette"])
    if s["background"] is not None and s["background"] not in names:
        raise SpecError(f"{path}: background {s['background']!r} is not a palette colour")
    _check_outline(s["outline"], names, path)
    if not s["frames"]:
        raise SpecError(f"{path}: sprite has no frames")
    for fi, frame in enumerate(s["frames"]):
        layers = frame.get("layers")
        if not layers:
            raise SpecError(f"{path}: frame {frame.get('name', fi)!r} has no layers")
        hold = frame.get("hold", 1)
        if not (isinstance(hold, int) and hold >= 1):
            raise SpecError(f"{path}: frame {frame.get('name', fi)!r} 'hold' must be a positive int")
        for li, layer in enumerate(layers):
            _validate_layer(layer, s, names, where=f"{path}: frame {fi} layer {li}")


def _validate_layer(layer, sprite, names, where) -> None:
    if not isinstance(layer, dict):
        raise SpecError(f"{where}: layer must be an object")
    kinds = [k for k in PRIMITIVES if k in layer]
    if len(kinds) != 1:
        raise SpecError(f"{where}: a layer needs exactly one of {list(PRIMITIVES)}, found {kinds}")
    offset = layer.get("offset", [0, 0])
    if not (isinstance(offset, (list, tuple)) and len(offset) == 2
            and all(isinstance(v, int) for v in offset)):
        raise SpecError(f"{where}: 'offset' must be [dx, dy] integers")
    kind = kinds[0]
    if kind == "pixels":
        try:
            shapes.normalize_grid(layer["pixels"])
        except ValueError as e:
            raise SpecError(f"{where}: {e}") from e
        legend = layer.get("legend", sprite.get("legend", {}))
        _check_legend(legend, layer["pixels"], names, where)
    elif kind == "shape":
        if layer["shape"] not in sprite["motifs"]:
            raise SpecError(f"{where}: unknown shape {layer['shape']!r} "
                            f"(motifs: {sorted(sprite['motifs'])})")
        _check_transforms(layer, where)
        for src, dst in (layer.get("recolor") or {}).items():
            if dst not in names:
                raise SpecError(f"{where}: recolor target {dst!r} is not a palette colour")
    else:  # rect / ellipse / line
        spec = layer[kind]
        if not isinstance(spec, dict) or spec.get("color") not in names:
            raise SpecError(f"{where}: {kind} needs a 'color' that is a palette name "
                            f"(palette: {sorted(names)})")


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_point(v) -> bool:
    return isinstance(v, (list, tuple)) and len(v) == 2 and all(_is_num(c) for c in v)


def _check_transforms(layer, where) -> None:
    flip_axis = layer.get("flip")
    if flip_axis is not None and (not isinstance(flip_axis, str)
                                  or set(flip_axis) - set("hv") or not flip_axis):
        raise SpecError(f"{where}: 'flip' must be 'h', 'v' or 'hv'")
    # rotate is any angle (degrees, clockwise). Multiples of 90 without a pivot
    # use the lossless grid turn; anything else rotates about the pivot in pixels.
    rot = layer.get("rotate", 0)
    if not _is_num(rot):
        raise SpecError(f"{where}: 'rotate' must be a number (degrees), got {rot!r}")
    pivot = layer.get("pivot")
    if pivot is not None and not _is_point(pivot):
        raise SpecError(f"{where}: 'pivot' must be [px, py] numbers, got {pivot!r}")
    at = layer.get("at")
    if at is not None and not _is_point(at):
        raise SpecError(f"{where}: 'at' must be [x, y] numbers, got {at!r}")
    sc = layer.get("scale", 1)
    if not (isinstance(sc, int) and sc >= 1):
        raise SpecError(f"{where}: 'scale' must be a positive int, got {sc!r}")


# --- Groups ------------------------------------------------------------------ #

@dataclass
class Group(_GroupBase):
    """One sprite set: an ``artbook.json`` bible plus its ``sprites/`` directory."""

    bible_file: str = BIBLE_FILE
    specs_subdir: str = SPRITES_SUBDIR

    def load_bible(self) -> Bible | None:
        return load_bible(self.bible_path) if os.path.isfile(self.bible_path) else None

    # Friendlier, medium-specific aliases over the generic labkit names.
    @property
    def sprites_dir(self) -> str:
        return self.specs_dir

    def sprite_path(self, name: str) -> str:
        return self.spec_path(name)

    def sprite_names(self) -> list:
        """Ordered names: the bible's ``sprites`` list, else ``sprites/*.json``."""
        bible = self.load_bible()
        if bible and bible.sprites:
            return list(bible.sprites)
        return self.spec_files()


def discover_groups(root: str = ".") -> list:
    """Find every sprite group under ``root`` (each ``art/<name>/artbook.json``)."""
    groups = [Group(name=name, dir=d)
              for name, d in discover_group_dirs(os.path.join(root, ART_DIR), BIBLE_FILE)]
    if not groups and os.path.isfile(os.path.join(root, BIBLE_FILE)):
        groups.append(Group(name="default", dir=root))
    return groups


def find_group(name: str, root: str = ".") -> Group:
    for g in discover_groups(root):
        if g.name == name:
            return g
    raise SpecError(f"unknown group {name!r} "
                    f"(groups: {[g.name for g in discover_groups(root)]})")
