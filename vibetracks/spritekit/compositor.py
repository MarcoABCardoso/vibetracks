"""Assemble a resolved character into a finished spritesheet.

The sprite analogue of :mod:`vibetracks.sequencer`. Where the sequencer schedules
parts on a beat grid and sums them into a stereo buffer, the compositor expands a
character's layers (folding in ``outfits``), sorts them by ``zPos``, and
alpha-composites each layer sheet onto one RGBA canvas.

``expand_layers`` — the resolve step — is pure and Pillow-free, so it is testable
without any art (mirroring the schedule builders in the audio path). Only the
final ``render_sheet`` touches the ``lpc`` engine to load real pixels.
"""

from __future__ import annotations

import numpy as np

from . import layout, lpc


def expand_layers(character: dict) -> list:
    """Flatten ``layers`` (expanding outfit references) into sorted concrete layers.

    Each returned entry is a dict with the layer's patch merged in:
    ``{layer, variant, source, engine, zPos, recolor, offset}``. Sorted by ``zPos``
    (stable), so lower z draws first (behind).
    """
    palette = character["palette"]
    outfits = character.get("outfits", {})

    raw = []
    for entry in character["layers"]:
        if "outfit" in entry:
            raw.extend(outfits[entry["outfit"]])
        else:
            raw.append(entry)

    concrete = []
    for i, entry in enumerate(raw):
        cat = entry["layer"]
        patch = palette.get(cat, {})
        variant = entry["variant"]
        source = entry.get("source") or patch.get("source") or f"{cat}/{variant}.png"
        concrete.append({
            "layer": cat,
            "variant": variant,
            "source": source,
            "engine": entry.get("engine", patch.get("engine", "lpc")),
            "zPos": entry.get("zPos", patch.get("zPos", 0)),
            "recolor": entry.get("recolor") or patch.get("recolor"),
            "offset": entry.get("offset", [0, 0]),
            "_order": i,  # stable tiebreak within equal zPos
        })
    concrete.sort(key=lambda l: (l["zPos"], l["_order"]))
    return concrete


def alpha_over(dst: np.ndarray, src: np.ndarray, offset=(0, 0)) -> None:
    """Composite ``src`` RGBA over ``dst`` RGBA in place at ``(dx, dy)`` pixels.

    Standard "source-over": ``out = src*a + dst*(1-a)``, working in float and
    clipping to the overlapping region so a layer may sit at an offset.
    """
    dx, dy = int(offset[0]), int(offset[1])
    sh, sw = src.shape[:2]
    dh, dw = dst.shape[:2]
    x0, y0 = max(0, dx), max(0, dy)
    x1, y1 = min(dw, dx + sw), min(dh, dy + sh)
    if x1 <= x0 or y1 <= y0:
        return
    d = dst[y0:y1, x0:x1].astype(np.float64)
    s = src[y0 - dy:y1 - dy, x0 - dx:x1 - dx].astype(np.float64)
    sa = s[..., 3:4] / 255.0
    da = d[..., 3:4] / 255.0
    out_a = sa + da * (1 - sa)
    safe = np.where(out_a > 0, out_a, 1.0)
    out_rgb = (s[..., :3] * sa + d[..., :3] * da * (1 - sa)) / safe
    dst[y0:y1, x0:x1, :3] = np.round(out_rgb).astype(np.uint8)
    dst[y0:y1, x0:x1, 3:4] = np.round(out_a * 255.0).astype(np.uint8)


def render_sheet(character: dict, cast_dir: str | None = None) -> np.ndarray:
    """Composite a resolved character into an ``(h, w, 4)`` uint8 RGBA sheet."""
    fw, fh = character["frame"]
    canvas = np.zeros((layout.ROWS * fh, layout.COLS * fw, 4), dtype=np.uint8)
    for lyr in expand_layers(character):
        engine = lyr["engine"]
        if engine in ("lpc",):  # SHEET_ENGINES
            path = lpc.find_asset(lyr["source"], cast_dir)
            sheet = lpc.load_layer_sheet(path)
            if lyr["recolor"]:
                sheet = lpc.recolor(sheet, lyr["recolor"])
            alpha_over(canvas, sheet, lyr["offset"])
        else:  # pragma: no cover - reserved for future procedural LAYER_ENGINES
            raise lpc.LPCError(f"layer {lyr['layer']!r}: unsupported engine {engine!r}")
    return canvas
