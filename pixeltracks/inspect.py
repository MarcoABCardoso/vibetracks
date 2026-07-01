"""Evaluate a sprite as text and geometry instead of as a raster.

The renderer's PNG is hard to judge by eye — spatial relationships (does the
belt span the hips? is the shield centred? is the blade clipped?) are far more
reliable read as *numbers and characters* than as upscaled pixels. This module
turns a composited frame into three text views a reviewer (human or model) can
evaluate deterministically:

* :func:`ascii_dump` — the composited frame re-emitted as a grid of palette-role
  characters (the same alphabet the author draws in), so you read exactly what
  landed on the canvas.
* :func:`geometry` — per-layer bounding boxes plus lint: floating (disconnected)
  layers, off-canvas clipping, and how many separate pieces the silhouette is in.
  These are the exact failure modes ("horseshoe", "stubby clipped sword") that a
  glance at the PNG missed.
* :func:`run_checks` — evaluate a sprite's declared ``checks`` (art direction as
  predicates: shield centred, sword above the head, cape behind the torso, whole
  figure connected) into pass/fail, so iterating is "fix the failures" not "guess
  from the picture".

All three operate on plain resolved layers, so they see skeleton-built sprites
exactly as hand-placed ones.
"""

from __future__ import annotations

import copy

import numpy as np

from . import compositor, raster

SPECK = 3  # components smaller than this (px) are rotation crumbs, not detached parts


# --- per-layer rasterisation ------------------------------------------------ #

def _shift_layer(layer: dict, dx: int, dy: int) -> dict:
    """Copy a layer with its canvas anchor(s) shifted by ``(dx, dy)``.

    Must mirror ``compositor._draw_layer``'s own resolution exactly, or the
    padded-canvas trick below misreads a shift as off-canvas clipping:

    * ``pixels`` and the ``shape`` fast path place at ``offset`` alone (default
      ``[0, 0]``) — shifting it is enough, whether or not the key was present.
    * the ``shape`` affine path (pivot/skew/squash) places at ``at``, falling
      back to ``offset`` only when ``at`` is absent — so ``offset`` must still
      shift for that fallback, and an *explicit* ``at`` must shift too.
    * ``rect``/``ellipse``/``line`` sum their own anchor *and* ``offset`` — so
      only one of the two may be shifted here, or the shift doubles.
    """
    out = copy.deepcopy(layer)
    ox, oy = out.get("offset", [0, 0])
    out["offset"] = [ox + dx, oy + dy]
    if "shape" in out and "at" in out:
        out["at"] = [out["at"][0] + dx, out["at"][1] + dy]
    return out


def layer_mask(sprite: dict, layer: dict, margin: int = 0) -> np.ndarray:
    """Opaque boolean mask of one layer drawn alone, on a canvas padded by ``margin``.

    The margin lets callers detect draws that spill *off* the real canvas (which
    the painter would otherwise silently clip): anything opaque inside the margin
    ring is off-canvas.
    """
    w, h = sprite["size"]
    canvas = raster.new_canvas(w + 2 * margin, h + 2 * margin)
    tmp = dict(sprite, size=(w + 2 * margin, h + 2 * margin))
    compositor._draw_layer(canvas, _shift_layer(layer, margin, margin), tmp)
    return canvas[:, :, 3] > 0


def frame_layers(sprite: dict, frame_index: int = 0) -> list:
    return sprite["frames"][frame_index].get("layers", [])


def bbox(mask: np.ndarray, margin: int = 0):
    """``(minx, maxx, miny, maxy)`` in *true* canvas coords, or ``None`` if empty."""
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return (int(xs.min()) - margin, int(xs.max()) - margin,
            int(ys.min()) - margin, int(ys.max()) - margin)


# --- 1. ASCII dump ---------------------------------------------------------- #

def _char_map(palette_names) -> dict:
    """Assign each palette role a stable single display char (outline -> ``#``)."""
    used = {"."}
    out = {}
    for name in sorted(palette_names):
        if name == "outline":
            out[name] = "#"
            used.add("#")
            continue
        pick = None
        for ch in list(name) + list(name.upper()) + list("0123456789"):
            if ch.isalnum() and ch not in used:
                pick = ch
                break
        pick = pick or "?"
        out[name] = pick
        used.add(pick)
    return out


def ascii_dump(sprite: dict, frame_index: int = 0) -> str:
    """The composited frame as a role-char grid plus a legend of the chars used."""
    frame = sprite["frames"][frame_index]
    canvas = compositor.composite_frame(sprite, frame)
    pal = sprite["palette"]
    charmap = _char_map(pal)
    # Reverse-lookup exact RGBA -> role name (all roles here are opaque).
    rev = {tuple(int(v) for v in rgba): name for name, rgba in pal.items()}
    h, w = canvas.shape[:2]
    rows, legend_used = [], {}
    for y in range(h):
        line = []
        for x in range(w):
            r, g, b, a = (int(v) for v in canvas[y, x])
            if a == 0:
                line.append(".")
                continue
            name = rev.get((r, g, b, a))
            if name is None:  # blended/anti-aliased -> nearest role by RGB
                best, bd = None, 1e18
                for (rr, gg, bb, aa), nm in rev.items():
                    d = (rr - r) ** 2 + (gg - g) ** 2 + (bb - b) ** 2
                    if d < bd:
                        best, bd = nm, d
                name = best
            ch = charmap.get(name, "?")
            legend_used[ch] = name
            line.append(ch)
        rows.append("".join(line))
    legend = "  ".join(f"{ch}={legend_used[ch]}" for ch in sorted(legend_used))
    header = f"{sprite['name']} frame {frame_index} ({w}x{h})"
    return header + "\n" + "\n".join(rows) + "\n  legend: " + legend


# --- 2. geometry + connectivity lint --------------------------------------- #

def _components(mask: np.ndarray) -> list:
    """4-connected component sizes of a boolean mask (largest first)."""
    seen = np.zeros_like(mask, dtype=bool)
    h, w = mask.shape
    sizes = []
    for sy in range(h):
        for sx in range(w):
            if not mask[sy, sx] or seen[sy, sx]:
                continue
            stack, n = [(sy, sx)], 0
            seen[sy, sx] = True
            while stack:
                y, x = stack.pop()
                n += 1
                for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            sizes.append(n)
    return sorted(sizes, reverse=True)


def _dilate(mask: np.ndarray) -> np.ndarray:
    out = mask.copy()
    out[:-1, :] |= mask[1:, :]
    out[1:, :] |= mask[:-1, :]
    out[:, :-1] |= mask[:, 1:]
    out[:, 1:] |= mask[:, :-1]
    return out


def geometry(sprite: dict, frame_index: int = 0) -> dict:
    """Per-layer bounding boxes + lint warnings for one frame.

    Returns ``{"layers": [{name, bbox, clipped}], "components": [...],
    "warnings": [str, ...]}``.
    """
    w, h = sprite["size"]
    layers = frame_layers(sprite, frame_index)
    m = 4  # padding margin for off-canvas detection
    infos, warnings = [], []
    plain_masks = []  # on-canvas masks, for connectivity
    for i, layer in enumerate(layers):
        name = layer.get("name", f"layer{i}")
        padded = layer_mask(sprite, layer, margin=m)
        box = bbox(padded, margin=m)
        plain = layer_mask(sprite, layer, margin=0)
        plain_masks.append((name, plain))
        if box is None:
            infos.append({"name": name, "bbox": None, "clipped": False})
            warnings.append(f"layer '{name}' is EMPTY (draws nothing)")
            continue
        minx, maxx, miny, maxy = box
        off = []
        if minx < 0:
            off.append(f"left by {-minx}")
        if miny < 0:
            off.append(f"top by {-miny}")
        if maxx > w - 1:
            off.append(f"right by {maxx - (w - 1)}")
        if maxy > h - 1:
            off.append(f"bottom by {maxy - (h - 1)}")
        infos.append({"name": name, "bbox": box, "clipped": bool(off)})
        if off:
            warnings.append(f"layer '{name}' clipped off-canvas ({', '.join(off)})")

    # Floating layers: a layer whose (dilated) mask touches no other layer.
    for i, (name, mask) in enumerate(plain_masks):
        if not mask.any():
            continue
        others = np.zeros_like(mask)
        for j, (_, om) in enumerate(plain_masks):
            if j != i:
                others |= om
        if others.any() and not (_dilate(mask) & others).any():
            warnings.append(f"layer '{name}' is FLOATING (touches no other layer)")

    union = np.zeros((h, w), dtype=bool)
    for _, mask in plain_masks:
        union |= mask
    comps = _components(union)
    solid = [c for c in comps if c >= SPECK]      # real body pieces
    specks = [c for c in comps if c < SPECK]      # 1-2px rotation crumbs
    if len(solid) > 1:
        warnings.append(f"silhouette is in {len(solid)} disconnected pieces "
                        f"(sizes {solid}); expected 1 — a part is detached")
    if specks:
        warnings.append(f"{len(specks)} stray speck(s) (<= {SPECK - 1}px): a thin "
                        f"rotated/sheared part likely has gaps")
    return {"layers": infos, "components": comps, "solid": solid,
            "specks": specks, "warnings": warnings}


# --- 3. declarative checks -------------------------------------------------- #

def _region_box(masks: dict, ref, w, h):
    """Bounding box of a check target: a layer name, ``"all"``, or a list of names."""
    if ref == "all":
        names = list(masks)
    elif isinstance(ref, list):
        names = ref
    else:
        names = [ref]
    union = np.zeros((h, w), dtype=bool)
    for n in names:
        if n in masks:
            union |= masks[n]
    return bbox(union)


def _cx(box):
    return (box[0] + box[1]) / 2.0


def run_checks(sprite: dict, frame_index: int = 0) -> list:
    """Evaluate ``sprite['checks']`` (or a frame's) -> ``[{ok, rule, detail}]``."""
    w, h = sprite["size"]
    frame = sprite["frames"][frame_index]
    checks = frame.get("checks", sprite.get("checks", []))
    layers = frame_layers(sprite, frame_index)
    masks = {}
    for i, layer in enumerate(layers):
        masks[layer.get("name", f"layer{i}")] = layer_mask(sprite, layer)
    geo = geometry(sprite, frame_index)
    results = []

    def emit(ok, rule, detail):
        results.append({"ok": bool(ok), "rule": rule, "detail": detail})

    for c in checks:
        rule = c.get("rule")
        if rule == "connected":
            solid = geo["solid"]
            emit(len(solid) <= 1, "connected",
                 f"{len(solid)} solid piece(s)" + (f" sizes {solid}" if len(solid) > 1 else "")
                 + (f"; {len(geo['specks'])} speck(s)" if geo["specks"] else ""))
        elif rule == "on_canvas":
            ref = c.get("layer", "all")
            names = list(masks) if ref == "all" else ([ref] if isinstance(ref, str) else ref)
            margin = c.get("margin", 0)
            bad = [n for n in names if masks.get(n) is not None
                   and any(layer_bad_offcanvas(sprite, layers, n, margin))]
            emit(not bad, "on_canvas",
                 f"ok (margin {margin})" if not bad else f"off-canvas/clipped: {bad}")
        elif rule in ("left_of", "right_of", "above", "below"):
            a = _region_box(masks, c["layer"], w, h)
            b = _region_box(masks, c["of"], w, h)
            if a is None or b is None:
                emit(False, rule, f"missing region ({c['layer']} or {c['of']})")
                continue
            s = c.get("slack", 0)  # permitted overlap (e.g. a cape at the shoulder)
            ok = {"left_of": a[1] <= b[0] + s, "right_of": a[0] >= b[1] - s,
                  "above": a[3] <= b[2] + s, "below": a[2] >= b[3] - s}[rule]
            emit(ok, rule, f"{c['layer']}{_box_short(a)} vs {c['of']}{_box_short(b)}"
                 + (f" (slack {s})" if s else ""))
        elif rule == "top_above":
            a = _region_box(masks, c["layer"], w, h)
            b = _region_box(masks, c["of"], w, h)
            by = c.get("by", 0)
            if a is None or b is None:
                emit(False, "top_above", f"missing region ({c['layer']} or {c['of']})")
                continue
            emit(a[2] <= b[2] - by, "top_above",
                 f"{c['layer']} top y{a[2]} vs {c['of']} top y{b[2]}"
                 + (f" (by {by})" if by else ""))
        elif rule == "centered_x":
            a = _region_box(masks, c["layer"], w, h)
            b = _region_box(masks, c["in"], w, h)
            tol = c.get("tol", 1)
            if a is None or b is None:
                emit(False, "centered_x", "missing region")
                continue
            d = _cx(a) - _cx(b)
            emit(abs(d) <= tol, "centered_x",
                 f"{c['layer']} cx {_cx(a):.1f} vs {c['in']} cx {_cx(b):.1f} (dx {d:+.1f}, tol {tol})")
        elif rule == "touches":
            a = masks.get(c["layer"])
            if a is None or not a.any():
                emit(False, "touches", f"{c['layer']} empty")
                continue
            if "of" in c:
                b = masks.get(c["of"], np.zeros((h, w), bool))
            else:
                b = np.zeros((h, w), bool)
                for n, m2 in masks.items():
                    if n != c["layer"]:
                        b |= m2
            emit(bool((_dilate(a) & b).any()), "touches",
                 f"{c['layer']} vs {c.get('of', 'any')}")
        elif rule == "min_coverage":
            union = np.zeros((h, w), bool)
            for m2 in masks.values():
                union |= m2
            cov = union.mean()
            emit(cov >= c["value"], "min_coverage", f"coverage {cov:.0%} >= {c['value']:.0%}")
        else:
            emit(False, str(rule), "unknown rule")
    return results


def layer_bad_offcanvas(sprite, layers, name, margin):
    """Yield offence strings if the named layer spills past the canvas minus margin."""
    w, h = sprite["size"]
    m = max(4, margin + 1)
    for layer in layers:
        if layer.get("name") == name:
            box = bbox(layer_mask(sprite, layer, margin=m), margin=m)
            if box is None:
                return
            minx, maxx, miny, maxy = box
            if minx < margin:
                yield "left"
            if miny < margin:
                yield "top"
            if maxx > w - 1 - margin:
                yield "right"
            if maxy > h - 1 - margin:
                yield "bottom"
            return


def _box_short(box):
    return f"[x{box[0]}..{box[1]},y{box[2]}..{box[3]}]"


# --- text report ------------------------------------------------------------ #

def report(sprite: dict, frame_index: int = 0, *, ascii=True, geom=True, checks=True) -> str:
    out = []
    if ascii:
        out.append(ascii_dump(sprite, frame_index))
    if geom:
        g = geometry(sprite, frame_index)
        out.append("geometry:")
        for info in g["layers"]:
            b = info["bbox"]
            box = _box_short(b) if b else "EMPTY"
            flag = "  <clipped>" if info["clipped"] else ""
            out.append(f"  {info['name']:12s} {box}{flag}")
        if g["warnings"]:
            out.append("warnings:")
            out.extend(f"  ! {wmsg}" for wmsg in g["warnings"])
        else:
            out.append("  (no warnings)")
    if checks:
        res = run_checks(sprite, frame_index)
        if res:
            out.append("checks:")
            for r in res:
                out.append(f"  [{'PASS' if r['ok'] else 'FAIL'}] {r['rule']}: {r['detail']}")
    return "\n".join(out)
