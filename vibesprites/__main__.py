"""VibeSprites CLI: validate sprite specs and composite them to PNG.

Characters are organized into **casts** — each ``sprites/<name>/`` is a
self-contained sprite set with its own ``charset.json``, a ``characters/`` folder,
and the ``assets/`` LPC art it composites. Mirrors the audio CLI:

    python -m vibesprites validate                    # check every cast
    python -m vibesprites render rpg-party/warrior     # composite one -> out/
    python -m vibesprites render-all                  # every character
    python -m vibesprites new <char> --cast <c>       # scaffold a character
    python -m vibesprites new-cast <name>             # scaffold a whole cast

A character may be addressed as ``<cast>/<char>``, as a bare ``<char>`` (with
``--cast``, or when only one cast exists), or as a path to its JSON file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import spec
from .atlas import build_atlas
from .compositor import render_sheet
from .pngio import write_png

SPRITES_DIR = "sprites"
OUT_DIR = os.path.join("out", "sprites")


# --- cast / character resolution ----------------------------------------- #

def _resolve_cast(name, casts):
    if name:
        for c in casts:
            if c.name == name:
                return c
        raise SystemExit(f"unknown cast {name!r} (casts: {[c.name for c in casts]})")
    if len(casts) == 1:
        return casts[0]
    if not casts:
        raise SystemExit("no sprite casts found "
                         f"(expected {SPRITES_DIR}/<name>/{spec.CHARSET_FILE})")
    raise SystemExit("multiple casts — pass --cast or use <cast>/<char>: "
                     f"{[c.name for c in casts]}")


def _cast_for_path(path, casts):
    ap = os.path.abspath(path)
    for c in casts:
        if ap.startswith(os.path.abspath(c.characters_dir) + os.sep):
            return c
    cdir = os.path.dirname(os.path.dirname(ap))
    return spec.Cast(name=os.path.basename(cdir) or "default", dir=cdir)


def _locate(char_arg, cast_name, casts):
    """Resolve a character argument to ``(cast, character_path)``."""
    if char_arg.endswith(".json"):
        return _cast_for_path(char_arg, casts), char_arg
    if "/" in char_arg:
        cname, _, chname = char_arg.partition("/")
        c = _resolve_cast(cname, casts)
        return c, c.character_path(chname)
    c = _resolve_cast(cast_name, casts)
    return c, c.character_path(char_arg)


# --- commands ------------------------------------------------------------- #

def cmd_validate(args) -> int:
    casts = spec.discover_casts()
    if args.cast:
        casts = [_resolve_cast(args.cast, casts)]
    if not casts:
        print(f"no sprite casts found "
              f"(expected {SPRITES_DIR}/<name>/{spec.CHARSET_FILE})")
        return 1

    ok = True
    for c in casts:
        print(f"cast {c.name!r}:")
        try:
            cs = c.load_charset()
        except spec.SpriteSpecError as e:
            print(f"  ERR  {e}")
            ok = False
            continue
        if cs is None:
            print(f"  --  no {spec.CHARSET_FILE}; characters use built-in defaults")
        else:
            print(f"  ok  {c.charset_path}  (frame {cs.frame}, {len(cs.outfits)} "
                  f"outfit(s), {len(cs.characters)} character(s))")
        for name in c.character_names():
            path = c.character_path(name)
            try:
                ch = spec.resolve_character(path, cs)
                print(f"  ok  {path}  ({len(ch['layers'])} layer(s))")
            except (spec.SpriteSpecError, FileNotFoundError) as e:
                print(f"  ERR  {e}")
                ok = False
    print("\nAll specs valid." if ok else "\nValidation failed.")
    return 0 if ok else 1


def _render_one(char_path, charset, cast_dir, cast_name, out_root) -> dict:
    ch = spec.resolve_character(char_path, charset)
    sheet = render_sheet(ch, cast_dir)
    out_dir = os.path.join(out_root, cast_name)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{ch['name']}.png")
    w, h = write_png(out_path, sheet)
    print(f"  rendered  {out_path}  ({w}x{h}, {len(ch['layers'])} layer(s))")
    atlas_path = os.path.join(out_dir, f"{ch['name']}.atlas.json")
    atlas = build_atlas(os.path.basename(out_path))
    with open(atlas_path, "w", encoding="utf-8") as f:
        json.dump(atlas, f, indent=2)
    print(f"  atlas     {atlas_path}  ({len(atlas['frames'])} frames, "
          f"{len(atlas['animations'])} animations)")
    return {"character": ch["name"], "file": out_path, "atlas": atlas_path,
            "width": w, "height": h, "layers": len(ch["layers"])}


def cmd_render(args) -> int:
    casts = spec.discover_casts()
    c, path = _locate(args.character, args.cast, casts)
    charset = c.load_charset()
    info = _render_one(path, charset, c.dir, c.name, args.out_dir)
    if args.out:
        os.replace(info["file"], args.out)
        # Keep the atlas beside the PNG, renamed to match: foo.png -> foo.atlas.json.
        atlas_out = os.path.splitext(args.out)[0] + ".atlas.json"
        os.replace(info["atlas"], atlas_out)
        print(f"  -> {args.out}  (+ {atlas_out})")
    return 0


def cmd_render_all(args) -> int:
    casts = spec.discover_casts()
    if not casts:
        print(f"no sprite casts found "
              f"(expected {SPRITES_DIR}/<name>/{spec.CHARSET_FILE})", file=sys.stderr)
        return 1
    if args.cast:
        casts = [_resolve_cast(args.cast, casts)]

    index = {"casts": []}
    for c in casts:
        charset = c.load_charset()
        if charset is None:
            print(f"  skip  cast {c.name!r}: no {spec.CHARSET_FILE}", file=sys.stderr)
            continue
        manifest = {"cast": c.name, "title": charset.title, "style": charset.style,
                    "frame": charset.frame, "characters": []}
        for name in c.character_names():
            manifest["characters"].append(
                _render_one(c.character_path(name), charset, c.dir, c.name, args.out_dir))
        out_dir = os.path.join(args.out_dir, c.name)
        os.makedirs(out_dir, exist_ok=True)
        manifest_path = os.path.join(out_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"  {c.name}: {len(manifest['characters'])} character(s) -> {manifest_path}")
        index["casts"].append({"name": c.name, "title": charset.title,
                               "characters": len(manifest["characters"]),
                               "manifest": os.path.join(c.name, "manifest.json")})

    os.makedirs(args.out_dir, exist_ok=True)
    index_path = os.path.join(args.out_dir, "manifest.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    print(f"\n{len(index['casts'])} cast(s) -> {index_path}")
    return 0


CHARACTER_TEMPLATE = {
    "name": "",
    "extends": "../charset.json",
    "layers": [
        {"layer": "body", "variant": "male/light"},
        {"outfit": "default-outfit"},
        {"layer": "hair", "variant": "male/plain/blonde"},
    ],
}

CHARSET_TEMPLATE = {
    "title": "",
    "style": "lpc",
    "frame": [64, 64],
    "palette": {
        "body": {"engine": "lpc"},
        "torso": {"engine": "lpc"},
        "legs": {"engine": "lpc"},
        "feet": {"engine": "lpc"},
        "hair": {"engine": "lpc"},
    },
    "outfits": {
        "default-outfit": [
            {"layer": "legs", "variant": "pants/male/teal_pants_male"},
            {"layer": "feet", "variant": "shoes/male/black_shoes_male"},
            {"layer": "torso", "variant": "leather/chest_male"},
        ],
    },
    "characters": ["hero"],
}


def cmd_new(args) -> int:
    casts = spec.discover_casts()
    c = _resolve_cast(args.cast, casts)
    path = c.character_path(args.name)
    if os.path.exists(path) and not args.force:
        print(f"{path} exists (use --force to overwrite)", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(CHARACTER_TEMPLATE, name=args.name), f, indent=2)
    print(f"scaffolded {path} — edit it, then: "
          f"python -m vibesprites render {c.name}/{args.name}")
    return 0


def cmd_new_cast(args) -> int:
    cdir = os.path.join(SPRITES_DIR, args.name)
    charset_path = os.path.join(cdir, spec.CHARSET_FILE)
    if os.path.exists(charset_path) and not args.force:
        print(f"{charset_path} exists (use --force to overwrite)", file=sys.stderr)
        return 1
    chars_dir = os.path.join(cdir, spec.CHARACTERS_SUBDIR)
    os.makedirs(chars_dir, exist_ok=True)
    os.makedirs(os.path.join(cdir, "assets"), exist_ok=True)

    with open(charset_path, "w", encoding="utf-8") as f:
        json.dump(dict(CHARSET_TEMPLATE, title=args.title or args.name), f, indent=2)
    char_path = os.path.join(chars_dir, "hero.json")
    if not os.path.exists(char_path) or args.force:
        with open(char_path, "w", encoding="utf-8") as f:
            json.dump(dict(CHARACTER_TEMPLATE, name="hero"), f, indent=2)

    print(f"scaffolded cast {args.name!r} at {cdir}/")
    print(f"  charset:    {charset_path}")
    print(f"  character:  {char_path}")
    print(f"  add LPC PNGs under {cdir}/assets/ (or set $VIBETRACKS_LPC_ASSETS), then:")
    print(f"  render:     python -m vibesprites render-all --cast {args.name}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="vibesprites", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="validate every cast's specs")
    pv.add_argument("--cast", help="limit to one cast")

    pr = sub.add_parser("render", help="composite one character to PNG")
    pr.add_argument("character", help="<cast>/<char>, a char name, or a path to JSON")
    pr.add_argument("--cast", help="cast to look up a bare character name in")
    pr.add_argument("-o", "--out", help="explicit output PNG path")
    pr.add_argument("--out-dir", default=OUT_DIR)

    pa = sub.add_parser("render-all", help="composite every character in every cast")
    pa.add_argument("--cast", help="limit to one cast")
    pa.add_argument("--out-dir", default=OUT_DIR)

    pn = sub.add_parser("new", help="scaffold a new character spec in a cast")
    pn.add_argument("name")
    pn.add_argument("--cast", help="cast to create the character in")
    pn.add_argument("--force", action="store_true")

    pg = sub.add_parser("new-cast", help="scaffold a whole new sprite cast")
    pg.add_argument("name")
    pg.add_argument("--title", help="charset title (defaults to the cast name)")
    pg.add_argument("--force", action="store_true")

    args = p.parse_args(argv)
    return {
        "validate": cmd_validate,
        "render": cmd_render,
        "render-all": cmd_render_all,
        "new": cmd_new,
        "new-cast": cmd_new_cast,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
