"""PixelTracks CLI: validate sprite specs and compile them to PNG.

Sprites are organized into **groups** — each ``groups/sprites/<name>/`` is a
self-contained sprite set with its own ``artbook.json`` bible and ``sprites/``.
The repo ships a demo group (``tiny-knight``); spin up your own with
``new-group``.

Note: PixelTracks is early, exploratory work — the procedural raster engine is
still limited, so rendered sprites are rough compared with the music Lab.

    python -m pixeltracks validate                    # check every group's specs
    python -m pixeltracks render tiny-knight/knight   # render one sprite to out/
    python -m pixeltracks render-all                  # render every sprite in every group
    python -m pixeltracks new <sprite> --group <g>    # scaffold a sprite spec
    python -m pixeltracks new-group <name>            # scaffold a whole new group

A sprite may be addressed as ``<group>/<sprite>``, as a bare ``<sprite>`` (with
``--group``, or when only one group exists), or as a path to its JSON file. This
mirrors ``python -m vibetracks`` exactly — the same verbs over a different medium.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import spec
from .compositor import coverage, render_sprite
from .pngio import write_png
from .raster import upscale

ART_DIR = spec.ART_DIR
OUT_DIR = "out"


# --- group / sprite resolution ------------------------------------------- #

def _resolve_group(name, groups):
    if name:
        for g in groups:
            if g.name == name:
                return g
        raise SystemExit(f"unknown group {name!r} (groups: {[g.name for g in groups]})")
    if len(groups) == 1:
        return groups[0]
    if not groups:
        raise SystemExit(f"no sprite groups found "
                         f"(expected {ART_DIR}/<name>/{spec.BIBLE_FILE})")
    raise SystemExit("multiple groups — pass --group or use <group>/<sprite>: "
                     f"{[g.name for g in groups]}")


def _group_for_path(path, groups):
    ap = os.path.abspath(path)
    for g in groups:
        if ap.startswith(os.path.abspath(g.sprites_dir) + os.sep):
            return g
    gdir = os.path.dirname(os.path.dirname(ap))
    return spec.Group(name=os.path.basename(gdir) or "default", dir=gdir)


def _locate(sprite_arg, group_name, groups):
    if sprite_arg.endswith(".json"):
        return _group_for_path(sprite_arg, groups), sprite_arg
    if "/" in sprite_arg:
        gname, _, sname = sprite_arg.partition("/")
        g = _resolve_group(gname, groups)
        return g, g.sprite_path(sname)
    g = _resolve_group(group_name, groups)
    return g, g.sprite_path(sprite_arg)


# --- commands ------------------------------------------------------------- #

def cmd_validate(args) -> int:
    groups = spec.discover_groups()
    if args.group:
        groups = [_resolve_group(args.group, groups)]
    if not groups:
        print(f"no sprite groups found (expected {ART_DIR}/<name>/{spec.BIBLE_FILE})")
        return 1

    ok = True
    for g in groups:
        print(f"group {g.name!r}:")
        try:
            bible = g.load_bible()
        except spec.SpecError as e:
            print(f"  ERR  {e}")
            ok = False
            continue
        if bible is None:
            print(f"  --  no {spec.BIBLE_FILE}; sprites use built-in defaults")
        else:
            print(f"  ok  {g.bible_path}  (size {bible.size[0]}x{bible.size[1]}, "
                  f"{len(bible.palette)} colour(s), {len(bible.motifs)} motif(s), "
                  f"{len(bible.sprites)} sprite(s))")
        for name in g.sprite_names():
            path = g.sprite_path(name)
            try:
                s = spec.resolve_sprite(path, bible)
                frames = len(s["frames"])
                shape = f"{s['size'][0]}x{s['size'][1]}"
                extra = f", {frames} frames" if frames > 1 else ""
                print(f"  ok  {path}  ({shape}{extra})")
            except (spec.SpecError, FileNotFoundError) as e:
                print(f"  ERR  {e}")
                ok = False
    print("\nAll specs valid." if ok else "\nValidation failed.")
    return 0 if ok else 1


def _render_one(sprite_path, bible, group_name, out_root) -> dict:
    sprite = spec.resolve_sprite(sprite_path, bible)
    result = render_sprite(sprite)
    sheet = upscale(result["sheet"], sprite["scale"])
    out_dir = os.path.join(out_root, group_name)
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, f"{sprite['name']}.png")
    w, h = write_png(png_path, sheet)
    cov = coverage(result["frames"][0])
    flag = "  (empty!)" if cov == 0 else ""
    print(f"  rendered  {png_path}  ({w}x{h}, {result['atlas']['frame_count']} frame(s), "
          f"coverage {cov:.0%}){flag}")

    atlas = dict(result["atlas"], file=png_path)
    if result["atlas"]["frame_count"] > 1:
        atlas_path = os.path.join(out_dir, f"{sprite['name']}.atlas.json")
        with open(atlas_path, "w", encoding="utf-8") as f:
            json.dump(atlas, f, indent=2)
    return {"sprite": sprite["name"], "file": png_path,
            "size": [sprite["size"][0], sprite["size"][1]],
            "scale": sprite["scale"], "frames": result["atlas"]["frame_count"],
            "coverage": round(cov, 3)}


def cmd_render(args) -> int:
    groups = spec.discover_groups()
    g, path = _locate(args.sprite, args.group, groups)
    bible = g.load_bible()
    info = _render_one(path, bible, g.name, args.out_dir)
    if args.out:
        os.replace(info["file"], args.out)
        print(f"  -> {args.out}")
    return 0


def cmd_inspect(args) -> int:
    from . import inspect as _inspect
    groups = spec.discover_groups()
    g, path = _locate(args.sprite, args.group, groups)
    bible = g.load_bible()
    sprite = spec.resolve_sprite(path, bible)
    frames = range(len(sprite["frames"])) if args.all_frames else [args.frame]
    any_fail = False
    for fi in frames:
        print(_inspect.report(sprite, fi,
                              ascii=not args.no_ascii,
                              geom=not args.no_geometry,
                              checks=not args.no_checks))
        if not args.no_checks:
            any_fail = any_fail or any(not r["ok"] for r in _inspect.run_checks(sprite, fi))
        if not args.no_geometry:
            any_fail = any_fail or bool(_inspect.geometry(sprite, fi)["warnings"])
    return 1 if (any_fail and args.strict) else 0


def cmd_render_all(args) -> int:
    groups = spec.discover_groups()
    if not groups:
        print(f"no sprite groups found (expected {ART_DIR}/<name>/{spec.BIBLE_FILE})",
              file=sys.stderr)
        return 1
    if args.group:
        groups = [_resolve_group(args.group, groups)]

    index = {"groups": []}
    for g in groups:
        bible = g.load_bible()
        if bible is None:
            print(f"  skip  group {g.name!r}: no {spec.BIBLE_FILE}", file=sys.stderr)
            continue
        manifest = {"group": g.name, "title": bible.title, "aesthetic": bible.aesthetic,
                    "size": [bible.size[0], bible.size[1]], "sprites": []}
        for name in g.sprite_names():
            manifest["sprites"].append(_render_one(g.sprite_path(name), bible, g.name, args.out_dir))
        out_dir = os.path.join(args.out_dir, g.name)
        os.makedirs(out_dir, exist_ok=True)
        manifest_path = os.path.join(out_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"  {g.name}: {len(manifest['sprites'])} sprite(s) -> {manifest_path}")
        index["groups"].append({"name": g.name, "title": bible.title,
                                "sprites": len(manifest["sprites"]),
                                "manifest": os.path.join(g.name, "manifest.json")})

    os.makedirs(args.out_dir, exist_ok=True)
    index_path = os.path.join(args.out_dir, "manifest.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    print(f"\n{len(index['groups'])} group(s) -> {index_path}")
    return 0


SPRITE_TEMPLATE = {
    "name": "",
    "extends": "../artbook.json",
    "layers": [
        {"name": "body", "shape": "blob"},
    ],
}

BIBLE_TEMPLATE = {
    "title": "",
    "aesthetic": "pixel-art",
    "size": [16, 16],
    "scale": 16,
    "palette": {
        "outline": "#1a1a2e",
        "body": "#5fcde4",
        "body_hi": "#a8e6f0",
        "eye": "#1a1a2e",
    },
    "background": None,
    "outline": {"color": "outline"},
    "motifs": {
        "blob": {
            "legend": {"o": "outline", "b": "body", "h": "body_hi", "e": "eye"},
            "pixels": [
                "................",
                "................",
                "................",
                ".....oooooo.....",
                "....obbbbbbo....",
                "...obbhhhhbbo...",
                "..obbhhhhhhbbo..",
                "..obebbbbebbo...",
                "..obbbbbbbbbo...",
                "..obbbbbbbbbo...",
                "...obbbbbbbo....",
                "....oobbboo.....",
                "......ooo.......",
                "................",
                "................",
                "................",
            ],
        },
    },
    "sprites": ["main"],
}


def cmd_new(args) -> int:
    groups = spec.discover_groups()
    g = _resolve_group(args.group, groups)
    path = g.sprite_path(args.name)
    if os.path.exists(path) and not args.force:
        print(f"{path} exists (use --force to overwrite)", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmpl = dict(SPRITE_TEMPLATE, name=args.name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tmpl, f, indent=2)
    print(f"scaffolded {path} — edit it, then: "
          f"python -m pixeltracks render {g.name}/{args.name}")
    return 0


def cmd_new_group(args) -> int:
    gdir = os.path.join(ART_DIR, args.name)
    bible_path = os.path.join(gdir, spec.BIBLE_FILE)
    if os.path.exists(bible_path) and not args.force:
        print(f"{bible_path} exists (use --force to overwrite)", file=sys.stderr)
        return 1
    sprites_dir = os.path.join(gdir, spec.SPRITES_SUBDIR)
    os.makedirs(sprites_dir, exist_ok=True)

    bible = dict(BIBLE_TEMPLATE, title=args.title or args.name)
    with open(bible_path, "w", encoding="utf-8") as f:
        json.dump(bible, f, indent=2)

    sprite_path = os.path.join(sprites_dir, "main.json")
    if not os.path.exists(sprite_path) or args.force:
        with open(sprite_path, "w", encoding="utf-8") as f:
            json.dump(dict(SPRITE_TEMPLATE, name="main"), f, indent=2)

    print(f"scaffolded group {args.name!r} at {gdir}/")
    print(f"  bible:  {bible_path}")
    print(f"  sprite: {sprite_path}")
    print(f"  render: python -m pixeltracks render-all --group {args.name}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="pixeltracks", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="validate every group's specs")
    pv.add_argument("--group", help="limit to one group")

    pr = sub.add_parser("render", help="render one sprite to PNG")
    pr.add_argument("sprite", help="<group>/<sprite>, a sprite name, or a path to JSON")
    pr.add_argument("--group", help="group to look up a bare sprite name in")
    pr.add_argument("-o", "--out", help="explicit output PNG path")
    pr.add_argument("--out-dir", default=OUT_DIR)

    pi = sub.add_parser("inspect", help="evaluate a sprite as text/geometry (no PNG)")
    pi.add_argument("sprite", help="<group>/<sprite>, a sprite name, or a path to JSON")
    pi.add_argument("--group", help="group to look up a bare sprite name in")
    pi.add_argument("--frame", type=int, default=0, help="which frame to inspect")
    pi.add_argument("--all-frames", action="store_true", help="inspect every frame")
    pi.add_argument("--no-ascii", action="store_true")
    pi.add_argument("--no-geometry", action="store_true")
    pi.add_argument("--no-checks", action="store_true")
    pi.add_argument("--strict", action="store_true",
                    help="exit non-zero if any warning or check fails")

    pa = sub.add_parser("render-all", help="render every sprite in every group")
    pa.add_argument("--group", help="limit to one group")
    pa.add_argument("--out-dir", default=OUT_DIR)

    pn = sub.add_parser("new", help="scaffold a new sprite spec in a group")
    pn.add_argument("name")
    pn.add_argument("--group", help="group to create the sprite in")
    pn.add_argument("--force", action="store_true")

    pg = sub.add_parser("new-group", help="scaffold a whole new sprite group")
    pg.add_argument("name")
    pg.add_argument("--title", help="bible title (defaults to the group name)")
    pg.add_argument("--force", action="store_true")

    args = p.parse_args(argv)
    return {
        "validate": cmd_validate,
        "render": cmd_render,
        "inspect": cmd_inspect,
        "render-all": cmd_render_all,
        "new": cmd_new,
        "new-group": cmd_new_group,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
