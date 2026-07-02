"""Shaded solid forms — the sprite Lab's *synth*.

This module is the visual answer to the question "why does JSON modeling feel
higher-leverage for music than for sprites?" A music note sits far above the
waveform: the synth (``synth.py``) manufactures the timbre (oscillators, ADSR,
filters, reverb) from a compact ``[pitch, beats]`` token. A pixel grid, by
contrast, sits *right on top of* the PNG — ``draw_grid`` is nearly the identity
map, so the author must hand-place every pixel. There is no abstraction gap for
the engine to fill.

A **form** restores that gap. The author declares a solid primitive — a sphere,
capsule, box or cone — with a *material* (a palette **ramp**, shadow→highlight)
and a *light* direction, and this module renders it to shaded pixels: it derives
a 2.5-D surface normal for every interior pixel, lights it against the ramp, and
snaps the result onto the ramp's colours (so the output is provably on-palette,
exactly like every other layer). The author supplies what an artist *decides*
(which forms, where, what material, lit from where); the engine supplies what an
artist grinds out by hand (every pixel and its shade).

Crucially this makes the bible's ``ramps`` — until now inert documentation — do
real work, precisely as a synth patch turns one note into a full ADSR-shaped
timbre. See ``docs/proposals/form-model.md`` for the full rationale.
"""

from __future__ import annotations

import math

import numpy as np

from . import raster

# Named light directions as ``(x, y, z)`` unit-ish vectors. Image y grows
# downward, so a light "up" has a *negative* y; z points toward the viewer, so a
# form's core (facing the camera) always catches some light.
LIGHTS = {
    "up_left": (-0.6, -0.6, 0.55),
    "up_right": (0.6, -0.6, 0.55),
    "up": (0.0, -0.75, 0.55),
    "left": (-0.85, -0.1, 0.45),
    "right": (0.85, -0.1, 0.45),
    "down": (0.0, 0.75, 0.55),
    "front": (0.0, 0.0, 1.0),
}
DEFAULT_LIGHT = "up_left"

FORM_KINDS = ("sphere", "disc", "capsule", "box", "cone")


def light_vector(light) -> np.ndarray:
    """Resolve a light preset name or explicit ``[x, y, z]`` to a unit vector."""
    if isinstance(light, str):
        vec = LIGHTS.get(light, LIGHTS[DEFAULT_LIGHT])
    else:
        vec = tuple(light)
    v = np.array(vec, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else np.array(LIGHTS[DEFAULT_LIGHT])


def ramp_rgba(material: str, sprite: dict) -> list:
    """The material's shadow→highlight colours as a list of RGBA tuples.

    ``material`` names either a bible ``ramp`` (→ its ordered colours, so a form
    shades across three-plus values) or a single palette colour (→ a one-entry
    ramp, i.e. a flat fill). Either way every emitted colour is a palette member,
    keeping the on-palette invariant the validator enforces for every other layer.
    """
    ramps = sprite.get("ramps", {})
    pal = sprite["palette"]
    if material in ramps:
        return [pal[name] for name in ramps[material]]
    return [pal[material]]


def _fields(kind: str, w: int, h: int, round_px: int):
    """Per-pixel geometry of a form on its ``h×w`` bounding box.

    Returns ``(mask, e, ox, oy)``: ``mask`` = inside the silhouette; ``e`` =
    normalized distance from the form's medial core (0) to its surface (1); and
    ``(ox, oy)`` = the outward surface direction in the image plane. Every form
    reduces to "distance from a medial primitive, normalized by a radius": a
    point (sphere), a segment (capsule), a rectangle (box) or a tapering axis
    (cone). That single model gives all four a rounded, form-reading shade.
    """
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0

    if kind in ("sphere", "disc"):
        rx, ry = max(w / 2.0, 0.5), max(h / 2.0, 0.5)
        nx, ny = (xs - cx) / rx, (ys - cy) / ry
        e = np.sqrt(nx * nx + ny * ny)
        mask = e <= 1.0
        mag = np.maximum(e, 1e-6)
        ox, oy = nx / mag, ny / mag

    elif kind == "capsule":
        if h >= w:                       # vertical capsule
            r = max(w / 2.0, 0.5)
            half = max(h / 2.0 - r, 0.0)
            qx, qy = cx, np.clip(ys, cy - half, cy + half)
        else:                            # horizontal capsule
            r = max(h / 2.0, 0.5)
            half = max(w / 2.0 - r, 0.0)
            qx, qy = np.clip(xs, cx - half, cx + half), cy
        dx, dy = xs - qx, ys - qy
        dist = np.sqrt(dx * dx + dy * dy)
        e = dist / r
        mask = e <= 1.0
        mag = np.maximum(dist, 1e-6)
        ox, oy = dx / mag, dy / mag

    elif kind == "box":
        r = max(int(round_px), 0)
        ix, iy = max(w / 2.0 - r, 0.0), max(h / 2.0 - r, 0.0)
        qx = np.clip(xs, cx - ix, cx + ix)
        qy = np.clip(ys, cy - iy, cy + iy)
        dx, dy = xs - qx, ys - qy
        dist = np.sqrt(dx * dx + dy * dy)
        rr = max(r, 0.5)
        inside_rect = (np.abs(xs - cx) <= w / 2.0) & (np.abs(ys - cy) <= h / 2.0)
        mask = inside_rect & (dist <= rr + 1e-6)
        e = np.clip(dist / rr, 0.0, 1.0)  # 0 across the flat face, →1 at rounded edges
        mag = np.maximum(dist, 1e-6)
        ox, oy = dx / mag, dy / mag

    elif kind == "cone":                 # apex at top, base at bottom
        top = cy - h / 2.0
        frac = np.clip((ys - top) / max(h, 1.0), 0.0, 1.0)
        halfw = np.maximum(frac * (w / 2.0), 0.5)
        e = np.abs(xs - cx) / halfw
        mask = (e <= 1.0) & (ys >= top) & (ys <= cy + h / 2.0)
        ox, oy = np.sign(xs - cx), np.zeros_like(xs)

    else:
        raise ValueError(f"unknown form kind {kind!r}")

    e = np.clip(e, 0.0, 1.0)
    return mask, e, ox, oy


def shade_form(kind: str, w: int, h: int, ramp: list, light, round_px: int = 0) -> np.ndarray:
    """Render one form to an ``h×w`` RGBA tile, shaded from ``ramp`` under ``light``.

    The lighting model: from ``_fields`` recover a unit surface normal per pixel
    (``n = (ox·e, oy·e, sqrt(1-e²))`` — sideways at the silhouette, facing the
    viewer at the core), take ``dot(n, light)`` for brightness, and map that onto
    the ramp so the core lands mid-ramp, lit faces climb toward the highlight and
    away-faces fall to the shadow. A lit rim on the silhouette gets the top value —
    the classic pixel-art edge light. With a one-entry ramp this degrades to a
    flat fill.
    """
    mask, e, ox, oy = _fields(kind, w, h, round_px)
    nz = np.sqrt(np.clip(1.0 - e * e, 0.0, 1.0))
    nx, ny = ox * e, oy * e

    lx, ly, lz = light_vector(light)
    brightness = nx * lx + ny * ly + nz * lz
    mid = float(lz)                       # a viewer-facing surface catches exactly lz

    k = len(ramp)
    tile = np.zeros((h, w, 4), dtype=np.uint8)
    if k == 0:
        return tile
    if k == 1:
        tile[mask] = ramp[0]
        return tile

    t = 0.5 + (brightness - mid) * 1.35
    idx = np.clip(np.round(t * (k - 1)).astype(int), 0, k - 1)
    rim = (e > 0.82) & (brightness > mid)   # lit silhouette → edge highlight
    idx = np.where(rim, k - 1, idx)

    ramp_arr = np.array(ramp, dtype=np.uint8)
    tile[mask] = ramp_arr[idx[mask]]
    return tile


def shadow_map(sprite: dict) -> dict:
    """A ``rgba -> darker rgba`` map: each ramp colour to the step below it.

    This is what keeps the contact shadow on-palette. A soft drop shadow would
    need arbitrary darkened colours; instead a shadowed pixel is snapped **one
    step down its own material ramp** — provably still a palette member, and it
    reads as the same material in shade. Colours at the bottom of a ramp (or not
    in any ramp) have no darker step and are left untouched.
    """
    pal = sprite["palette"]
    out = {}
    for seq in sprite.get("ramps", {}).values():
        rgbas = [tuple(int(c) for c in pal[n]) for n in seq if n in pal]
        for i in range(1, len(rgbas)):
            out.setdefault(rgbas[i], rgbas[i - 1])
    return out


def _shift_mask(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """A copy of ``mask`` translated by ``(dx, dy)``, zero-filled at the edges."""
    out = np.zeros_like(mask)
    h, w = mask.shape
    ys0, ys1 = max(0, dy), min(h, h + dy)
    xs0, xs1 = max(0, dx), min(w, w + dx)
    if ys1 <= ys0 or xs1 <= xs0:
        return out
    out[ys0:ys1, xs0:xs1] = mask[max(0, -dy):max(0, -dy) + (ys1 - ys0),
                                 max(0, -dx):max(0, -dx) + (xs1 - xs0)]
    return out


def cast_contact_shadow(canvas, mask, z, zbuf, light, smap, depth: int = 2) -> None:
    """Darken a band of pixels *behind* this form, offset away from the light.

    The cheap depth cue the craft guide teaches authors to place by hand: a near
    form drops a soft shade onto the farther form it overlaps. Here it is derived —
    pixels in a ``depth``-px band just outside the form silhouette on the
    light-away side, that are already opaque and sit *behind* this form
    (``zbuf < z``), get ramp-shifted one step darker via ``smap`` (staying on
    palette). This is what lets same-material forms read as distinct masses.
    """
    if not smap:
        return
    lx, ly, _ = light_vector(light)
    dx = -1 if lx > 0.15 else (1 if lx < -0.15 else 0)
    dy = -1 if ly > 0.15 else (1 if ly < -0.15 else 0)
    if dx == 0 and dy == 0:
        dy = 1
    band = np.zeros_like(mask)
    for d in range(1, depth + 1):
        band |= _shift_mask(mask, dx * d, dy * d)
    band &= ~mask
    target = band & (canvas[:, :, 3] > 0) & (zbuf < z)
    for y, x in zip(*np.where(target)):
        rep = smap.get((int(canvas[y, x, 0]), int(canvas[y, x, 1]),
                        int(canvas[y, x, 2]), int(canvas[y, x, 3])))
        if rep is not None:
            canvas[y, x] = rep


def _rotate_light_vec(light, degrees: float) -> list:
    """Rotate a light's in-plane direction by ``degrees`` (its z is unchanged)."""
    v = light_vector(light)
    th = math.radians(degrees)
    c, s = math.cos(th), math.sin(th)
    return [c * v[0] - s * v[1], s * v[0] + c * v[1], float(v[2])]


def draw_form(canvas: np.ndarray, layer: dict, sprite: dict,
              zbuf: np.ndarray | None = None, z: int = 0) -> None:
    """Composite a ``form`` layer onto the canvas (the compositor's entry point).

    * Phase 2 — with a ``zbuf``, the form first casts a contact shadow onto the
      geometry behind it, so nearer forms sit in front of farther ones.
    * Phase 3 — a form may be **articulated**: ``rotate`` (deg) / ``skew`` /
      ``squash`` about a ``pivot`` pinned to ``at``, the same affine a `shape`
      layer or skeleton bone uses. The shading is computed in the form's *local*
      frame with the world light pre-rotated by ``-rotate``, so after the tile
      turns into world space the highlight lands on the world-lit side — a limb
      that leans is relit, not a highlight that spins with the part.
    """
    kind = layer["form"]
    w, h = layer["size"]
    ax, ay = layer.get("at", layer.get("offset", [0, 0]))
    ox, oy = layer.get("offset", [0, 0]) if "at" in layer else (0, 0)
    world_light = layer.get("light", sprite.get("light", DEFAULT_LIGHT))
    ramp = ramp_rgba(layer["material"], sprite)

    rotate = layer.get("rotate", 0)
    skew = layer.get("skew")
    squash = layer.get("squash")
    pivot = layer.get("pivot")
    articulated = bool(rotate) or bool(skew) or bool(squash) or pivot is not None

    shade_light = _rotate_light_vec(world_light, -rotate) if rotate else world_light
    tile = shade_form(kind, int(w), int(h), ramp, shade_light, int(layer.get("round", 0)))

    flip = layer.get("flip")
    if flip:
        if "h" in flip:
            tile = tile[:, ::-1]
        if "v" in flip:
            tile = tile[::-1, :]

    # Render the form into its own full-canvas layer so its placed silhouette (for
    # the contact shadow) is exact whether it is axis-aligned or articulated.
    ch, cw = canvas.shape[:2]
    layer_canvas = raster.new_canvas(cw, ch)
    if articulated:
        matrix = raster.affine_matrix(rotate,
                                      skew=tuple(skew) if skew else (0.0, 0.0),
                                      scale=tuple(squash) if squash else (1.0, 1.0))
        gh, gw = tile.shape[:2]
        piv = pivot if pivot is not None else [gw / 2.0, gh / 2.0]
        raster.blit_affine(layer_canvas, tile, matrix, piv, [int(ax) + int(ox), int(ay) + int(oy)])
    else:
        raster.blit(layer_canvas, tile, int(ax) + int(ox), int(ay) + int(oy))

    if zbuf is not None and layer.get("cast", True):
        cast_contact_shadow(canvas, layer_canvas[:, :, 3] > 0, z, zbuf,
                            world_light, shadow_map(sprite))
    raster.blit(canvas, layer_canvas, 0, 0)
