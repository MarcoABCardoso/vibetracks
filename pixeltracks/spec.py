"""Load and validate sprite specs (the JSON "model of a sprite").

The same three layers as VibeTracks, in a different medium:

* **a group** (``groups/sprites/<name>/``): one self-contained sprite set — its
  own bible plus sprites — so a repo can hold several independent visual
  identities.
* **the bible** (``groups/sprites/<name>/artbook.json``): the visual identity
  shared by every sprite in the group — canvas ``size``, the colour ``palette``,
  reusable shape ``motifs``, an optional ``outline``/``background``, and the
  ``sprites`` list.
* **a sprite** (``groups/sprites/<name>/sprites/<sprite>.json``): one image. It
  ``extends`` the bible to inherit size/palette/motifs, and may override them.

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
from labkit.specbase import SpecError, extends_path, load_json  # shared across Labs
from labkit.world import World, check_spec_refs, load_world

from . import palette, raster, shapes

ART_DIR = os.path.join("groups", "sprites")   # where sprite groups live
BIBLE_FILE = "artbook.json"
SPRITES_SUBDIR = "sprites"

PRIMITIVES = ("pixels", "shape", "rect", "ellipse", "line", "sprite")
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
    fps: int = 10                                    # default animation playback rate
    sprites: list = field(default_factory=list)
    world: World | None = None   # the Root Spec this bible extends, if any

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
        fps=int(data.get("fps", 10)),
        sprites=data.get("sprites", []),
    )
    # A bible may `extends` a world (the Root Spec) to inherit the shared identity
    # and enrol in the world's cross-modal motifs; a broken world link fails
    # validation here, before any pixels are drawn.
    world_path = extends_path(path, data)
    if world_path:
        bible.world = load_world(world_path)
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
    anchors = motif.get("anchors", {})
    if not isinstance(anchors, dict):
        raise SpecError(f"{where}: motif {name!r}: 'anchors' must be a map of name -> [x, y]")
    for an, pt in anchors.items():
        if not _is_point(pt):
            raise SpecError(f"{where}: motif {name!r}: anchor {an!r} must be [x, y] numbers, got {pt!r}")


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
    if not (isinstance(b.fps, int) and b.fps >= 1):
        raise SpecError(f"{b.path}: fps must be a positive int")
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


# --- Skeleton resolution ----------------------------------------------------- #
#
# A skeleton makes connection STRUCTURAL instead of lucky. Motifs declare named
# `anchors` (neck, shoulder, hips, hand, foot) in their own grid coords; a bone
# pins one of its anchors to a parent bone's world anchor, so a chest's `hips`
# and a leg's `hip` meet exactly no matter how the chest is rotated/leaned. Each
# bone lowers to an ordinary affine `shape` layer (numeric pivot/at), so the rest
# of the pipeline — compositor, ascii, geometry, checks — is unchanged.

def _anchor_in_transformed(pt, flip_axis, scale_by, gw0, gh0):
    """Map an anchor from raw motif coords into the flip/scale-transformed grid,
    matching :func:`shapes.transform_grid` (flip on the original, then scale)."""
    x, y = pt
    if flip_axis and "h" in flip_axis:
        x = gw0 - 1 - x
    if flip_axis and "v" in flip_axis:
        y = gh0 - 1 - y
    if scale_by and scale_by > 1:
        x = x * scale_by + (scale_by - 1) / 2.0
        y = y * scale_by + (scale_by - 1) / 2.0
    return (float(x), float(y))


def resolve_skeleton(bones, motifs, where="skeleton") -> list:
    """Expand a list of skeleton bones into plain affine ``shape`` layers.

    Each bone is drawn like a normal shape layer but its ``at`` (where its pivot
    lands on the canvas) may be *derived* from a parent bone's world anchor via
    ``attach: {to, anchor}``. Returns the layers in bone order (z-order).
    """
    by_name, order = {}, []
    for b in bones:
        if not isinstance(b, dict) or "shape" not in b:
            raise SpecError(f"{where}: each bone needs a 'shape'")
        name = b.get("name", b["shape"])
        by_name[name] = b
        order.append(name)

    world_anchors = {}   # bone name -> {anchor name -> [wx, wy]}
    layers, done = [], set()

    def resolve(name, stack):
        if name in done:
            return
        if name in stack:
            raise SpecError(f"{where}: attach cycle through {name!r}")
        b = by_name[name]
        motif = motifs.get(b["shape"])
        if motif is None:
            raise SpecError(f"{where}: bone {name!r} unknown shape {b['shape']!r}")
        anchors = motif.get("anchors", {})
        gw0, gh0 = shapes.grid_size(motif["pixels"])
        flip_axis = b.get("flip")
        scale_by = b.get("scale", 1)

        def anchor_pt(a):
            if isinstance(a, str):
                if a not in anchors:
                    raise SpecError(f"{where}: bone {name!r} shape {b['shape']!r} "
                                    f"has no anchor {a!r} (anchors: {sorted(anchors)})")
                raw = anchors[a]
            else:
                raw = a
            return _anchor_in_transformed(raw, flip_axis, scale_by, gw0, gh0)

        piv = anchor_pt(b["pivot"]) if "pivot" in b else (gw0 * scale_by / 2.0,
                                                          gh0 * scale_by / 2.0)

        att = b.get("attach")
        if att:
            parent = att["to"]
            if parent not in by_name:
                raise SpecError(f"{where}: bone {name!r} attaches to unknown bone {parent!r}")
            resolve(parent, stack | {name})
            pa = world_anchors[parent]
            if att["anchor"] not in pa:
                raise SpecError(f"{where}: bone {parent!r} has no world anchor "
                                f"{att['anchor']!r} (has: {sorted(pa)})")
            at = list(pa[att["anchor"]])
            if "shift" in att:
                at = [at[0] + att["shift"][0], at[1] + att["shift"][1]]
        else:
            at = list(b.get("at", b.get("offset", [0, 0])))

        rotate = b.get("rotate", 0)
        skew = b.get("skew")
        squash = b.get("squash")
        matrix = raster.affine_matrix(rotate,
                                      skew=tuple(skew) if skew else (0.0, 0.0),
                                      scale=tuple(squash) if squash else (1.0, 1.0))
        a_, b_, c_, d_ = matrix
        wa = {}
        for an, raw in anchors.items():
            tx, ty = _anchor_in_transformed(raw, flip_axis, scale_by, gw0, gh0)
            rx, ry = tx - piv[0], ty - piv[1]
            wa[an] = [at[0] + a_ * rx + b_ * ry, at[1] + c_ * rx + d_ * ry]
        world_anchors[name] = wa

        layer = {"name": name, "shape": b["shape"],
                 "pivot": [piv[0], piv[1]], "at": [at[0], at[1]], "rotate": rotate}
        for k in ("skew", "squash", "flip", "scale", "recolor"):
            if k in b:
                layer[k] = b[k]
        layers.append((order.index(name), layer))
        done.add(name)

    for name in order:
        resolve(name, set())
    layers.sort(key=lambda t: t[0])
    return [layer for _, layer in layers]


# --- Sprite resolution ------------------------------------------------------- #

def resolve_sprite(path: str, bible: Bible | None = None, _stack=frozenset()) -> dict:
    """Load a sprite spec and fold in the bible it ``extends`` (if any).

    A ``sprite`` layer (scene composition) references a sibling sprite by name;
    that child is resolved recursively with the same bible and stashed on the
    layer, so a scene is simply a sprite whose layers are other sprites. ``_stack``
    carries the chain of sprites currently being resolved to reject reference
    cycles.
    """
    abspath = os.path.abspath(path)
    if abspath in _stack:
        chain = " -> ".join([os.path.basename(p) for p in _stack] + [os.path.basename(path)])
        raise SpecError(f"{path}: sprite reference cycle ({chain})")
    data = load_json(path)
    name = data.get("name", os.path.splitext(os.path.basename(path))[0])

    if bible is None:
        bible_path = extends_path(path, data)
        if bible_path:
            bible = load_bible(bible_path)

    colours = dict(bible.palette) if bible else {}
    colours.update(data.get("palette", {}))          # per-sprite palette override
    motifs = dict(bible.motifs) if bible else {}
    motifs.update(data.get("motifs", {}))

    # Normalise to a list of frames; a still sprite is a single frame. A frame
    # (or the whole sprite) may declare a `skeleton` that expands into layers
    # with parts attached at anchors — drawn beneath any explicit `layers`.
    if data.get("frames"):
        raw_frames = [dict(f) for f in data["frames"]]
    else:
        raw_frames = [{"name": "frame0", "layers": data.get("layers", []),
                       "skeleton": data.get("skeleton")}]
    frames = []
    for f in raw_frames:
        nf = dict(f)
        skel = nf.pop("skeleton", None)
        layers = list(nf.get("layers", []))
        if skel:
            where = f"{path}: frame {nf.get('name', '?')} skeleton"
            layers = resolve_skeleton(skel, motifs, where) + layers
        nf["layers"] = layers
        frames.append(nf)

    # A sprite may claim a world `meaning` tag and reference world `entities` —
    # the Root Spec's palette of meaning inherited down to the leaf spec. Checked
    # against the bible's world, so a stray tag/id fails like an off-palette colour.
    world = bible.world if bible else None
    meaning, entities = check_spec_refs(data, world, path)

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
        "checks": data.get("checks", []),    # declarative art-direction predicates
        "flip": data.get("flip"),            # mirror the whole composite ("h"/"v"/"hv")
        "scene": bool(data.get("scene", False)),  # a multi-object composite, not one figure
        "fps": data.get("fps", bible.fps if bible else 10),  # animation playback rate
        "meaning": meaning,          # world meaning tag (or None)
        "entities": entities,        # world entity ids this sprite is about
    }
    if not isinstance(data.get("scene", False), bool):
        raise SpecError(f"{path}: 'scene' must be true/false")
    if resolved["flip"] is not None and (not isinstance(resolved["flip"], str)
                                         or set(resolved["flip"]) - set("hv")
                                         or not resolved["flip"]):
        raise SpecError(f"{path}: sprite 'flip' must be 'h', 'v' or 'hv'")
    _resolve_sprite_layers(resolved, path, bible, _stack | {abspath})
    _validate_sprite(resolved, path)
    return resolved


def _resolve_sprite_layers(sprite: dict, path: str, bible, stack) -> None:
    """Resolve every ``sprite`` layer to its referenced sibling (in place).

    A ``sprite`` layer names another sprite in the same ``sprites/`` directory;
    the child is resolved recursively (same bible, same cycle chain) and stashed
    under ``_resolved`` so the compositor can stamp its composited frame. Missing
    references and cycles are caught here, before any pixels are drawn.
    """
    sprite_dir = os.path.dirname(path)
    for fi, frame in enumerate(sprite["frames"]):
        for li, layer in enumerate(frame.get("layers", [])):
            if not isinstance(layer, dict) or "sprite" not in layer:
                continue
            ref = layer["sprite"]
            where = f"{path}: frame {fi} layer {li}"
            if not isinstance(ref, str):
                raise SpecError(f"{where}: 'sprite' must be a sprite name (string), got {ref!r}")
            child_path = os.path.join(sprite_dir, ref + ".json")
            if not os.path.isfile(child_path):
                raise SpecError(f"{where}: sprite layer references unknown sprite {ref!r} "
                                f"(looked for {child_path})")
            layer["_resolved"] = resolve_sprite(child_path, bible, stack)


def _validate_sprite(s: dict, path: str) -> None:
    _check_size(s["size"], path)
    names = set(s["palette"])
    if s["background"] is not None and s["background"] not in names:
        raise SpecError(f"{path}: background {s['background']!r} is not a palette colour")
    _check_outline(s["outline"], names, path)
    if not (isinstance(s["fps"], int) and s["fps"] >= 1):
        raise SpecError(f"{path}: fps must be a positive int")
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
    elif kind == "sprite":
        # A scene layer that stamps another sprite. Existence/cycles were checked
        # at resolution (which attached `_resolved`); here we vet the placement.
        frame = layer.get("frame", 0)
        if not (isinstance(frame, int) and frame >= 0):
            raise SpecError(f"{where}: sprite 'frame' must be a non-negative int, got {frame!r}")
        sc = layer.get("scale", 1)
        if not (isinstance(sc, int) and sc >= 1):
            raise SpecError(f"{where}: sprite 'scale' must be a positive int, got {sc!r}")
        flip_axis = layer.get("flip")
        if flip_axis is not None and (not isinstance(flip_axis, str)
                                      or set(flip_axis) - set("hv") or not flip_axis):
            raise SpecError(f"{where}: sprite 'flip' must be 'h', 'v' or 'hv', got {flip_axis!r}")
        child = layer.get("_resolved")
        if child is not None and frame >= len(child["frames"]):
            raise SpecError(f"{where}: sprite {layer['sprite']!r} has no frame {frame} "
                            f"(it has {len(child['frames'])})")
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
    # skew (shear) and squash (non-uniform fractional scale) drive the affine
    # placement — the "turn/lean" transforms. Both are [x, y] number pairs.
    skew = layer.get("skew")
    if skew is not None and not _is_point(skew):
        raise SpecError(f"{where}: 'skew' must be [kx, ky] numbers, got {skew!r}")
    squash = layer.get("squash")
    if squash is not None:
        if not _is_point(squash):
            raise SpecError(f"{where}: 'squash' must be [sx, sy] numbers, got {squash!r}")
        if any(v <= 0 for v in squash):
            raise SpecError(f"{where}: 'squash' factors must be > 0, got {squash!r}")


# --- Groups ------------------------------------------------------------------ #

@dataclass
class Group(_GroupBase):
    """One sprite set: an ``artbook.json`` bible plus its ``sprites/`` directory.

    A group lives in ``groups/sprites/<name>/`` alongside the music groups under
    ``groups/music/`` — one ``groups/`` tree, one subdirectory per medium.
    """

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
    """Find every sprite group under ``root`` (each ``groups/sprites/<name>/artbook.json``)."""
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
