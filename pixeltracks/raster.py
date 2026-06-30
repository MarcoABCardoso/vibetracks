"""Low-level rasterisers: turn primitives into pixels on an RGBA canvas.

This is PixelTracks' ``synth`` module. Where the synth has oscillators, ADSR and
filters that a patch composes into a note, here we have grid/rect/ellipse/line
painters plus an outline post-effect that the compositor composes into a sprite.
A canvas is a ``numpy`` ``uint8`` array of shape ``(h, w, 4)`` (RGBA); pixels are
combined with straight alpha-over compositing, so later layers paint over earlier
ones the way later parts mix over a track.
"""

from __future__ import annotations

import math

import numpy as np


def new_canvas(width: int, height: int) -> np.ndarray:
    """A fully transparent RGBA canvas of shape ``(height, width, 4)``."""
    return np.zeros((height, width, 4), dtype=np.uint8)


def paint(canvas: np.ndarray, x: int, y: int, rgba) -> None:
    """Alpha-over a single colour onto pixel ``(x, y)`` (out-of-bounds ignored)."""
    h, w = canvas.shape[:2]
    if not (0 <= x < w and 0 <= y < h) or rgba[3] == 0:
        return
    sa = rgba[3] / 255.0
    if sa >= 1.0:
        canvas[y, x] = rgba
        return
    dst = canvas[y, x].astype(np.float64)
    da = dst[3] / 255.0
    out_a = sa + da * (1.0 - sa)
    if out_a <= 0:
        canvas[y, x] = (0, 0, 0, 0)
        return
    rgb = (np.array(rgba[:3]) * sa + dst[:3] * da * (1.0 - sa)) / out_a
    canvas[y, x] = (*np.round(rgb).astype(np.uint8), round(out_a * 255))


def draw_grid(canvas, rows, legend_rgba, ox=0, oy=0) -> None:
    """Paint a char grid using ``legend_rgba`` (``char -> RGBA``) at offset ``(ox, oy)``.

    Characters ``.`` and space are transparent; any char absent from the legend is
    treated as transparent too (the validator catches stray chars earlier).
    """
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch in ". ":
                continue
            rgba = legend_rgba.get(ch)
            if rgba is not None:
                paint(canvas, ox + i, oy + j, rgba)


def draw_grid_rotated(canvas, rows, legend_rgba, degrees, pivot, at) -> None:
    """Paint a char grid rotated by an arbitrary angle about a ``pivot``.

    Unlike :func:`shapes.rotate` (a lossless 90°-step grid turn), this is a
    *pixel-space* rotation by any angle, so a sword can trace a real swing arc
    instead of snapping to a quarter-turn. ``degrees`` is clockwise; ``pivot``
    ``[px, py]`` is the centre of rotation in the grid's own pixel coordinates,
    and that pivot is placed at canvas point ``at`` ``[ax, ay]`` — i.e. the grid
    rotates *about its hand/joint* and that joint is pinned to the body.

    Inverse-mapped + nearest-neighbour so the result stays hole-free and crisp,
    the way pixel art should look. Out-of-palette/transparent cells are skipped.
    """
    gh, gw = len(rows), len(rows[0])
    tile = np.zeros((gh, gw, 4), dtype=np.uint8)
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch in ". ":
                continue
            rgba = legend_rgba.get(ch)
            if rgba is not None:
                tile[j, i] = rgba

    th = math.radians(degrees)
    c, s = math.cos(th), math.sin(th)
    px, py = pivot
    ax, ay = at

    # Output bounding box: forward-rotate the grid's corners about the pivot.
    xs, ys = [], []
    for gx, gy in ((0, 0), (gw, 0), (0, gh), (gw, gh)):
        rx, ry = gx - px, gy - py
        xs.append(c * rx - s * ry)
        ys.append(s * rx + c * ry)
    minx, maxx = math.floor(min(xs)), math.ceil(max(xs))
    miny, maxy = math.floor(min(ys)), math.ceil(max(ys))

    # Inverse map each output pixel back to a source cell (no gaps).
    for oy in range(miny, maxy + 1):
        for ox in range(minx, maxx + 1):
            sx = int(round(px + c * ox + s * oy))
            sy = int(round(py - s * ox + c * oy))
            if 0 <= sx < gw and 0 <= sy < gh:
                rgba = tile[sy, sx]
                if rgba[3] > 0:
                    paint(canvas, int(round(ax)) + ox, int(round(ay)) + oy,
                          (int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3])))


def draw_rect(canvas, x, y, w, h, rgba, fill=True) -> None:
    """Draw a rectangle; ``fill=False`` draws only its 1px border."""
    for j in range(y, y + h):
        for i in range(x, x + w):
            if fill or i in (x, x + w - 1) or j in (y, y + h - 1):
                paint(canvas, i, j, rgba)


def draw_ellipse(canvas, x, y, w, h, rgba, fill=True) -> None:
    """Draw an ellipse inscribed in the box ``(x, y, w, h)``."""
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    rx, ry = max(cx, 0.5), max(cy, 0.5)
    for j in range(h):
        for i in range(w):
            nx, ny = (i - cx) / rx, (j - cy) / ry
            d = nx * nx + ny * ny
            if d <= 1.0 and (fill or d > (1.0 - 2.0 / max(w, h))):
                paint(canvas, x + i, y + j, rgba)


def draw_line(canvas, x0, y0, x1, y1, rgba) -> None:
    """Bresenham line from ``(x0, y0)`` to ``(x1, y1)``."""
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        paint(canvas, x0, y0, rgba)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def add_outline(canvas, rgba) -> None:
    """Paint ``rgba`` on every transparent pixel 4-adjacent to an opaque one.

    A 1px silhouette outline — the pixel-art finishing pass, and the engine-level
    "effect" analogous to a track's reverb: it reads the whole buffer and is
    applied once. Computed against a snapshot so the outline doesn't feed itself.
    """
    opaque = canvas[:, :, 3] > 0
    h, w = opaque.shape
    border = np.zeros_like(opaque)
    border[:-1, :] |= opaque[1:, :]
    border[1:, :] |= opaque[:-1, :]
    border[:, :-1] |= opaque[:, 1:]
    border[:, 1:] |= opaque[:, :-1]
    border &= ~opaque
    for y, x in zip(*np.where(border)):
        canvas[y, x] = rgba


def upscale(canvas, factor: int) -> np.ndarray:
    """Nearest-neighbour integer upscale for a viewable export (master stage)."""
    if factor <= 1:
        return canvas
    return np.repeat(np.repeat(canvas, factor, axis=0), factor, axis=1)
