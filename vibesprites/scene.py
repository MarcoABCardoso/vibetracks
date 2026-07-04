"""Compose a *battle scene* — a still that stages a party against monsters.

Where :mod:`vibesprites.compositor` builds one character's whole animation sheet,
a **scene** is the next layer up: it picks a single facing/frame from several
finished sheets — party members (composited on the fly from a character cast) and
monsters (sliced straight from a :mod:`bestiary <sprites>` sheet) — and stages them,
with a painted background and cast shadows, into one framed picture. It is to the
compositor what a mixed-and-mastered track is to a single instrument part: the
place the individual voices are arranged into a finished whole.

A scene is described by a JSON *scene spec* (``scenes/<name>.json``):

    {
      "name": "ff3-battle",
      "size": [w, h],                     // native canvas, before `upscale`
      "upscale": 3,                       // final nearest-neighbour zoom
      "background": { ... },              // sky/ground gradient (see draw_background)
      "party_cast": "rpg-party",          // default cast for `kind: party` actors
      "actors": [
        {"kind": "party",   "character": "warrior", "pos": [x, y], "dir": "left"},
        {"kind": "monster", "monster":   "pumpking", "pos": [x, y], "dir": "right"}
      ]
    }

``pos`` is the top-left of the sprite's (scaled) cell on the native canvas, so a
scene is authored in low-res pixels and blown up crisply at the end — exactly how
the games it evokes were drawn. Party character sheets are cached per character, so
rendering the same member twice costs one composite.

Only slicing party cells needs the character compositor (and thus the ``lpc``
engine to fetch layer art); monster cells are plain reads. Everything composites
through :func:`compositor.alpha_over`, the same source-over used for layers.
"""

from __future__ import annotations

import json
import os

import numpy as np

from . import layout, lpc, spec
from .compositor import alpha_over, render_sheet

SCENES_DIR = "scenes"
MONSTERS_DIR = os.path.join("sprites", "lpc-monsters")
BESTIARY_FILE = "bestiary.json"


class SceneError(ValueError):
    """Raised when a scene spec is structurally invalid or references unknown art."""


# --- loading -------------------------------------------------------------- #

def load_scene(path: str) -> dict:
    """Load and validate a scene spec, returning it as a plain dict."""
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise SceneError(f"{path}: invalid JSON: {e}") from e
    data.setdefault("name", os.path.splitext(os.path.basename(path))[0])
    _validate_scene(data, path)
    return data


def _validate_scene(scene: dict, where: str) -> None:
    size = scene.get("size")
    if not (isinstance(size, (list, tuple)) and len(size) == 2
            and all(isinstance(n, int) and n > 0 for n in size)):
        raise SceneError(f"{where}: 'size' must be [w, h] positive ints, got {size!r}")
    actors = scene.get("actors")
    if not isinstance(actors, list) or not actors:
        raise SceneError(f"{where}: 'actors' must be a non-empty list")
    for i, a in enumerate(actors):
        w = f"{where}: actor {i}"
        kind = a.get("kind")
        if kind not in ("party", "monster"):
            raise SceneError(f"{w}: 'kind' must be 'party' or 'monster', got {kind!r}")
        pos = a.get("pos")
        if not (isinstance(pos, (list, tuple)) and len(pos) == 2
                and all(isinstance(n, (int, float)) for n in pos)):
            raise SceneError(f"{w}: 'pos' must be [x, y], got {pos!r}")
        if kind == "party" and not (a.get("character")):
            raise SceneError(f"{w}: a party actor needs a 'character'")
        if kind == "monster" and not (a.get("monster")):
            raise SceneError(f"{w}: a monster actor needs a 'monster'")


def load_bestiary(root: str = ".") -> dict:
    """Load the monster set's ``bestiary.json`` (geometry for every monster sheet)."""
    path = os.path.join(root, MONSTERS_DIR, BESTIARY_FILE)
    if not os.path.isfile(path):
        raise SceneError(f"no monster bestiary at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --- pixel helpers -------------------------------------------------------- #

def _hex_rgba(s: str, alpha: int = 255) -> np.ndarray:
    s = str(s).lstrip("#")
    if len(s) not in (6, 8):
        raise SceneError(f"colour must be #rrggbb or #rrggbbaa, got {s!r}")
    vals = [int(s[i:i + 2], 16) for i in range(0, len(s), 2)]
    if len(vals) == 3:
        vals.append(alpha)
    return np.array(vals, dtype=np.float64)


def scale_nearest(cell: np.ndarray, factor: int) -> np.ndarray:
    """Integer nearest-neighbour upscale of an RGBA array (keeps hard pixel edges)."""
    if factor <= 1:
        return cell
    return np.repeat(np.repeat(cell, factor, axis=0), factor, axis=1)


def draw_background(canvas: np.ndarray, bg: dict | None) -> None:
    """Paint a sky→ground gradient onto ``canvas`` in place.

    ``bg`` keys (all optional): ``top``/``bottom`` sky colours, ``horizon`` (0..1
    fraction of height where the ground starts), ``ground_top``/``ground_bottom``.
    With no ``bg`` the canvas is left transparent.
    """
    if not bg:
        return
    h, w = canvas.shape[:2]
    horizon = int(np.clip(bg.get("horizon", 0.62), 0.0, 1.0) * h)
    horizon = max(1, min(h - 1, horizon))

    def band(y0, y1, c0, c1):
        if y1 <= y0:
            return
        t = np.linspace(0.0, 1.0, y1 - y0)[:, None]
        col = (c0[None, :] * (1 - t) + c1[None, :] * t)
        canvas[y0:y1, :, :] = np.round(col[:, None, :]).astype(np.uint8)

    top = _hex_rgba(bg.get("top", "#20304f"))
    bottom = _hex_rgba(bg.get("bottom", "#4a6ea0"))
    band(0, horizon, top, bottom)
    g_top = _hex_rgba(bg.get("ground_top", "#3f6b34"))
    g_bot = _hex_rgba(bg.get("ground_bottom", "#243f1f"))
    band(horizon, h, g_top, g_bot)


def draw_shadow(canvas: np.ndarray, cx: float, cy: float, rx: float, ry: float,
                alpha: float = 0.33) -> None:
    """Alpha-blend a soft dark ellipse (a cast shadow) onto ``canvas`` in place."""
    h, w = canvas.shape[:2]
    x0, x1 = max(0, int(cx - rx)), min(w, int(cx + rx) + 1)
    y0, y1 = max(0, int(cy - ry)), min(h, int(cy + ry) + 1)
    if x1 <= x0 or y1 <= y0:
        return
    ys, xs = np.mgrid[y0:y1, x0:x1]
    d = ((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2
    a = np.clip(1.0 - d, 0.0, 1.0) * alpha
    region = canvas[y0:y1, x0:x1, :3].astype(np.float64)
    canvas[y0:y1, x0:x1, :3] = np.round(region * (1 - a[..., None])).astype(np.uint8)
    ca = canvas[y0:y1, x0:x1, 3].astype(np.float64) / 255.0
    ca = ca + (1 - ca) * a
    canvas[y0:y1, x0:x1, 3] = np.round(ca * 255.0).astype(np.uint8)


# --- cell extraction ------------------------------------------------------ #

def _dir_row(dirs: list, want: str) -> int:
    """Row index for a facing, falling back to the first row if it is absent."""
    return dirs.index(want) if want in dirs else 0


def party_cell(sheet: np.ndarray, anim: str, direction: str, frame: int) -> np.ndarray:
    """Slice one 64px cell from a Universal-LPC character sheet."""
    row = layout.animation_row(anim) + _dir_row(list(layout.DIRECTIONS), direction)
    fs = layout.FRAME
    y, x = row * fs, frame * fs
    return sheet[y:y + fs, x:x + fs].copy()


def monster_cell(sheet: np.ndarray, entry: dict, bestiary: dict,
                 direction: str, frame: int) -> np.ndarray:
    """Slice one animation cell from a monster sheet, honouring its geometry."""
    fw, fh = entry.get("frame", bestiary.get("frame", [layout.FRAME, layout.FRAME]))
    dirs = entry.get("dirs", bestiary.get("dirs", list(layout.DIRECTIONS)))
    row = _dir_row(dirs, direction)
    y, x = row * fh, frame * fw
    if y + fh > sheet.shape[0] or x + fw > sheet.shape[1]:
        raise SceneError(f"monster cell out of range for frame [{fw},{fh}] "
                         f"dir {direction!r} frame {frame} on {sheet.shape[1]}x{sheet.shape[0]}")
    return sheet[y:y + fh, x:x + fw].copy()


# --- rendering ------------------------------------------------------------ #

def _flip_h(cell: np.ndarray) -> np.ndarray:
    return cell[:, ::-1, :]


def render_scene(scene: dict, root: str = ".") -> np.ndarray:
    """Composite a scene spec into an ``(H, W, 4)`` uint8 RGBA picture.

    Actors are drawn in list order (later actors sit in front). Each actor may set
    ``scale`` (integer pixel zoom of its cell), ``flip`` (mirror horizontally),
    ``frame``/``dir``/``anim``, and ``shadow`` (default on). The whole canvas is
    finally zoomed by the scene's ``upscale``.
    """
    w, h = scene["size"]
    canvas = np.zeros((h, w, 4), dtype=np.uint8)
    draw_background(canvas, scene.get("background"))

    bestiary = None
    sheet_cache: dict = {}   # (cast, character) -> composited sheet
    monster_cache: dict = {}  # monster name -> loaded sheet

    party_cast = scene.get("party_cast", "rpg-party")
    for actor in scene["actors"]:
        scale = int(actor.get("scale", 1))
        if actor["kind"] == "party":
            cast_name = actor.get("cast", party_cast)
            key = (cast_name, actor["character"])
            if key not in sheet_cache:
                cast = spec.find_cast(cast_name, root)
                charset = cast.load_charset()
                ch = spec.resolve_character(
                    cast.character_path(actor["character"]), charset)
                sheet_cache[key] = render_sheet(ch, cast.dir)
            cell = party_cell(sheet_cache[key], actor.get("anim", "walk"),
                              actor.get("dir", "left"), int(actor.get("frame", 0)))
        else:  # monster
            if bestiary is None:
                bestiary = load_bestiary(root)
            name = actor["monster"]
            entry = bestiary["monsters"].get(name)
            if entry is None:
                raise SceneError(f"unknown monster {name!r} "
                                 f"(have {sorted(bestiary['monsters'])})")
            if name not in monster_cache:
                path = os.path.join(root, MONSTERS_DIR, "assets", entry["sheet"])
                monster_cache[name] = lpc.load_layer_sheet(path)
            cell = monster_cell(monster_cache[name], entry, bestiary,
                                actor.get("dir", "right"), int(actor.get("frame", 0)))

        if actor.get("flip"):
            cell = _flip_h(cell)
        cell = scale_nearest(cell, scale)
        x, y = int(actor["pos"][0]), int(actor["pos"][1])
        ch_, cw_ = cell.shape[:2]

        if actor.get("shadow", True):
            # Grounded ellipse under the sprite's visual feet (its opaque bottom).
            opaque_rows = np.where(cell[..., 3].any(axis=1))[0]
            if opaque_rows.size:
                cols = np.where(cell[..., 3].any(axis=0))[0]
                feet_y = y + int(opaque_rows.max())
                mid_x = x + (int(cols.min()) + int(cols.max())) / 2.0
                span = (int(cols.max()) - int(cols.min()) + 1)
                draw_shadow(canvas, mid_x, feet_y - 1, span * 0.42, span * 0.16)

        alpha_over(canvas, cell, (x, y))

    return scale_nearest(canvas, int(scene.get("upscale", 1)))


# --- discovery ------------------------------------------------------------ #

def find_scene(name: str, root: str = ".") -> str:
    """Resolve a scene name (or path) to its JSON file under ``scenes/``."""
    if name.endswith(".json") or os.path.sep in name:
        return name
    path = os.path.join(root, SCENES_DIR, f"{name}.json")
    if not os.path.isfile(path):
        raise SceneError(f"unknown scene {name!r} (looked for {path})")
    return path
