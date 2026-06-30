"""Composite a resolved sprite spec into pixels.

The mirror of ``sequencer.py``. There, sections of parts are scheduled on a beat
grid, rendered, panned and mixed, then concatenated over time with loop sections
repeated. Here, layers of a frame are rasterised in z-order and composited (later
layers over earlier — the spatial analogue of mixing), then frames are laid out
left-to-right into a sprite **sheet** (the temporal analogue of concatenating
sections), with an **atlas** describing each frame's rectangle and hold count.

A still sprite is just the one-frame case, exactly as a non-looping single-section
track is the degenerate case of the music pipeline.
"""

from __future__ import annotations

import numpy as np

from . import raster, shapes


def _legend_to_rgba(legend: dict, sprite_palette: dict) -> dict:
    """Map a ``{char: palette name}`` legend to ``{char: RGBA}`` for the sprite."""
    return {ch: sprite_palette[name] for ch, name in legend.items()
            if name in sprite_palette}


def _draw_layer(canvas, layer, sprite) -> None:
    pal = sprite["palette"]
    ox, oy = layer.get("offset", [0, 0])

    if "pixels" in layer:
        legend = layer.get("legend", sprite.get("legend", {}))
        raster.draw_grid(canvas, layer["pixels"], _legend_to_rgba(legend, pal), ox, oy)
    elif "shape" in layer:
        motif = sprite["motifs"][layer["shape"]]
        legend = shapes.recolor_legend(motif.get("legend", {}), layer.get("recolor") or {})
        rows = shapes.transform_grid(motif["pixels"],
                                     flip_axis=layer.get("flip"),
                                     rotate_deg=layer.get("rotate", 0),
                                     scale_by=layer.get("scale", 1))
        raster.draw_grid(canvas, rows, _legend_to_rgba(legend, pal), ox, oy)
    elif "rect" in layer:
        r = layer["rect"]
        x, y = r.get("at", [0, 0])
        w, h = r.get("size", [1, 1])
        raster.draw_rect(canvas, x + ox, y + oy, w, h, pal[r["color"]], r.get("fill", True))
    elif "ellipse" in layer:
        e = layer["ellipse"]
        x, y = e.get("at", [0, 0])
        w, h = e.get("size", [1, 1])
        raster.draw_ellipse(canvas, x + ox, y + oy, w, h, pal[e["color"]], e.get("fill", True))
    elif "line" in layer:
        ln = layer["line"]
        x0, y0 = ln.get("from", [0, 0])
        x1, y1 = ln.get("to", [0, 0])
        raster.draw_line(canvas, x0 + ox, y0 + oy, x1 + ox, y1 + oy, pal[ln["color"]])


def composite_frame(sprite: dict, frame: dict) -> np.ndarray:
    """Rasterise one frame's layers (in order) onto a native-size RGBA canvas."""
    w, h = sprite["size"]
    canvas = raster.new_canvas(w, h)
    bg = sprite.get("background")
    if bg is not None:
        canvas[:, :] = sprite["palette"][bg]
    for layer in frame.get("layers", []):
        _draw_layer(canvas, layer, sprite)
    outline = sprite.get("outline")
    if outline is not None:
        raster.add_outline(canvas, sprite["palette"][outline["color"]])
    return canvas


def render_sprite(sprite: dict) -> dict:
    """Render every frame and pack them into a horizontal sheet plus an atlas.

    Returns ``{"frames": [native canvas, ...], "sheet": native sheet, "atlas":
    {...}}``. The sheet/atlas are at *native* resolution; export upscaling (the
    master stage) is applied by the CLI just before writing the PNG.
    """
    w, h = sprite["size"]
    scale = sprite["scale"]
    frames = [composite_frame(sprite, f) for f in sprite["frames"]]
    sheet = np.concatenate(frames, axis=1) if len(frames) > 1 else frames[0]

    # Frame rects are in EXPORTED (upscaled) pixel coordinates so they index the
    # written PNG directly; `size`/`scale` give the native cell for engines that
    # prefer it.
    cw, ch = w * scale, h * scale
    atlas_frames = []
    for i, f in enumerate(sprite["frames"]):
        atlas_frames.append({"name": f.get("name", f"frame{i}"),
                             "hold": f.get("hold", 1),
                             "x": i * cw, "y": 0, "w": cw, "h": ch})
    atlas = {
        "name": sprite["name"],
        "size": [w, h],
        "scale": scale,
        "frame_count": len(frames),
        "loop": len(frames) > 1,
        "frames": atlas_frames,
    }
    return {"frames": frames, "sheet": sheet, "atlas": atlas}


def coverage(canvas: np.ndarray) -> float:
    """Fraction of pixels that are not transparent — a cheap 'is it empty?' check."""
    if canvas.size == 0:
        return 0.0
    return float(np.count_nonzero(canvas[:, :, 3])) / (canvas.shape[0] * canvas.shape[1])
