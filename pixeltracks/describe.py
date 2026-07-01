"""Summarize a group's artbook as a searchable index instead of raw pixel grids.

A music bible fits in a screenful because a motif is a few notes; an artbook's
motifs are pixel grids, so ``emberhold/artbook.json`` runs 700+ lines. This
module builds a table of contents from data already in the specs — no new
authoring field required: each motif's size/anchors plus which sprites
reference it (a `shape` layer or skeleton bone naming it), and one line per
sprite. ``python -m pixeltracks describe <group>`` prints it so Claude (or a
human) can scan the shape of a set before grepping pixel rows.
"""

from __future__ import annotations

from . import shapes, spec


def motif_usage(group, bible) -> dict:
    """motif name -> sorted list of sprite names that reference it as a `shape`
    (including bones expanded from a `skeleton`)."""
    usage: dict = {}
    for name in group.sprite_names():
        sprite = spec.resolve_sprite(group.sprite_path(name), bible)
        used = set()
        for frame in sprite["frames"]:
            for layer in frame["layers"]:
                if "shape" in layer:
                    used.add(layer["shape"])
        for m in used:
            usage.setdefault(m, set()).add(name)
    return {m: sorted(names) for m, names in usage.items()}


def describe_group(group) -> dict:
    """A plain-dict index of one group: bible summary, per-motif facts, per-sprite facts."""
    bible = group.load_bible()
    if bible is None:
        return {"name": group.name, "bible": None}

    usage = motif_usage(group, bible)
    motifs = []
    for name, motif in bible.motifs.items():
        w, h = shapes.grid_size(motif["pixels"])
        motifs.append({
            "name": name,
            "size": (w, h),
            "anchors": sorted(motif.get("anchors", {})),
            "comment": motif.get("_comment", ""),
            "used_by": usage.get(name, []),
        })

    sprites = []
    for name in group.sprite_names():
        sprite = spec.resolve_sprite(group.sprite_path(name), bible)
        shapes_used = sorted({layer["shape"] for frame in sprite["frames"]
                              for layer in frame["layers"] if "shape" in layer})
        sprites.append({
            "name": name,
            "size": sprite["size"],
            "frames": len(sprite["frames"]),
            "shapes": shapes_used,
            "checks": len(sprite["checks"]),
            "flip": sprite["flip"],
        })

    return {
        "name": group.name,
        "bible": {
            "title": bible.title,
            "aesthetic": bible.aesthetic,
            "path": bible.path,
            "size": bible.size,
            "scale": bible.scale,
            "palette": sorted(bible.palette),
            "ramps": sorted(bible.ramps),
            "background": bible.background,
            "outline": bible.outline,
        },
        "motifs": motifs,
        "sprites": sprites,
        "unused_motifs": sorted(m["name"] for m in motifs if not m["used_by"]),
    }


def format_report(info: dict) -> str:
    if info["bible"] is None:
        return f"group {info['name']!r}: no artbook.json"

    b = info["bible"]
    out = [f"group {info['name']!r}: {b['title']}  "
          f"({b['size'][0]}x{b['size'][1]} canvas, scale {b['scale']}, "
          f"{len(b['palette'])} colour(s), {len(info['motifs'])} motif(s), "
          f"{len(info['sprites'])} sprite(s))",
          f"  aesthetic: {b['aesthetic']}",
          f"  bible: {b['path']}",
          f"  palette: {', '.join(b['palette'])}"]
    if b["ramps"]:
        out.append(f"  ramps: {', '.join(b['ramps'])}")
    out.append(f"  background: {b['background'] or 'none'}   "
              f"outline: {b['outline']['color'] if b['outline'] else 'none'}")

    out.append(f"\nmotifs ({len(info['motifs'])}):")
    for m in sorted(info["motifs"], key=lambda m: m["name"]):
        size = f"{m['size'][0]}x{m['size'][1]}"
        anchors = ",".join(m["anchors"]) if m["anchors"] else "-"
        used = ", ".join(m["used_by"]) if m["used_by"] else "(unused)"
        out.append(f"  {m['name']:18s} {size:7s} anchors: {anchors:24s} used by: {used}")
        if m["comment"]:
            out.append(f"    {m['comment']}")

    out.append(f"\nsprites ({len(info['sprites'])}):")
    for s in info["sprites"]:
        size = f"{s['size'][0]}x{s['size'][1]}"
        extra = []
        if s["frames"] > 1:
            extra.append(f"{s['frames']} frames")
        if s["flip"]:
            extra.append(f"flip:{s['flip']}")
        if s["checks"]:
            extra.append(f"{s['checks']} check(s)")
        extra_s = f"  ({', '.join(extra)})" if extra else ""
        shapes_s = ", ".join(s["shapes"]) if s["shapes"] else "-"
        out.append(f"  {s['name']:18s} {size:7s} shapes: {shapes_s}{extra_s}")

    if info["unused_motifs"]:
        out.append(f"\nunused motifs (not referenced by any sprite): {', '.join(info['unused_motifs'])}")

    return "\n".join(out)
