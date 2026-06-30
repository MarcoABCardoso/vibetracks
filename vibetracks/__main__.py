"""VibeTracks CLI: validate specs and compile them to WAV.

Tracks are organized into **groups** — each ``groups/<name>/`` is a
self-contained soundtrack with its own ``soundtrack.json`` bible and ``tracks/``.
The repo ships a demo group (``neon-frontier``); spin up your own with
``new-group`` instead of overwriting it.

    python -m vibetracks validate                   # check every group's specs
    python -m vibetracks render neon-frontier/boss  # render one track to out/
    python -m vibetracks render-all                 # render every track in every group
    python -m vibetracks new <track> --group <g>    # scaffold a track in a group
    python -m vibetracks new-group <name>           # scaffold a whole new group

A track may be addressed as ``<group>/<track>``, as a bare ``<track>`` (with
``--group``, or when only one group exists), or as a path to its JSON file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import spec
from .sequencer import render_track
from .wavio import write_wav

GROUPS_DIR = "groups"
OUT_DIR = "out"


# --- group / track resolution -------------------------------------------- #

def _resolve_group(name, groups):
    """Pick the group named ``name``, or the sole group when ``name`` is None."""
    if name:
        for g in groups:
            if g.name == name:
                return g
        raise SystemExit(f"unknown group {name!r} "
                         f"(groups: {[g.name for g in groups]})")
    if len(groups) == 1:
        return groups[0]
    if not groups:
        raise SystemExit("no soundtrack groups found "
                         f"(expected {GROUPS_DIR}/<name>/{spec.BIBLE_FILE})")
    raise SystemExit("multiple groups — pass --group or use <group>/<track>: "
                     f"{[g.name for g in groups]}")


def _group_for_path(path, groups):
    """Find the group a track-file path belongs to, synthesizing one if needed."""
    ap = os.path.abspath(path)
    for g in groups:
        if ap.startswith(os.path.abspath(g.tracks_dir) + os.sep):
            return g
    # Standalone file outside any known group: treat its parent dir as the group.
    gdir = os.path.dirname(os.path.dirname(ap))
    return spec.Group(name=os.path.basename(gdir) or "default", dir=gdir)


def _locate(track_arg, group_name, groups):
    """Resolve a track argument to ``(group, track_path)``.

    Accepts ``<group>/<track>``, a bare ``<track>``, or a path to a ``.json``.
    """
    if track_arg.endswith(".json"):
        return _group_for_path(track_arg, groups), track_arg
    if "/" in track_arg:
        gname, _, tname = track_arg.partition("/")
        g = _resolve_group(gname, groups)
        return g, g.track_path(tname)
    g = _resolve_group(group_name, groups)
    return g, g.track_path(track_arg)


# --- commands ------------------------------------------------------------- #

def cmd_validate(args) -> int:
    groups = spec.discover_groups()
    if args.group:
        groups = [_resolve_group(args.group, groups)]
    if not groups:
        print(f"no soundtrack groups found "
              f"(expected {GROUPS_DIR}/<name>/{spec.BIBLE_FILE})")
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
            print(f"  --  no {spec.BIBLE_FILE}; tracks use built-in defaults")
        else:
            print(f"  ok  {g.bible_path}  (key {bible.key}, {bible.bpm:g} bpm, "
                  f"{len(bible.motifs)} motif(s), {len(bible.tracks)} track(s))")
        for name in g.track_names():
            path = g.track_path(name)
            try:
                t = spec.resolve_track(path, bible)
                secs = ", ".join(s.get("name", "?") for s in t["sections"])
                print(f"  ok  {path}  ({t['bpm']:g} bpm, sections: {secs})")
            except (spec.SpecError, FileNotFoundError) as e:
                print(f"  ERR  {e}")
                ok = False
    print("\nAll specs valid." if ok else "\nValidation failed.")
    return 0 if ok else 1


def _render_one(track_path, bible, group_name, out_root, loops) -> dict:
    track = spec.resolve_track(track_path, bible)
    buf = render_track(track, loops=loops)
    out_dir = os.path.join(out_root, group_name)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{track['name']}.wav")
    dur = write_wav(out_path, buf)
    import numpy as np
    peak = float(np.max(np.abs(buf)))
    print(f"  rendered  {out_path}  ({dur:.1f}s, peak {peak:.2f})")
    return {"track": track["name"], "file": out_path, "seconds": round(dur, 2),
            "peak": round(peak, 3), "bpm": track["bpm"], "key": track["key"]}


def cmd_render(args) -> int:
    groups = spec.discover_groups()
    g, path = _locate(args.track, args.group, groups)
    bible = g.load_bible()
    info = _render_one(path, bible, g.name, args.out_dir, args.loops)
    if args.out:
        # Honour an explicit output path by moving the rendered file.
        os.replace(info["file"], args.out)
        print(f"  -> {args.out}")
    return 0


def cmd_render_all(args) -> int:
    groups = spec.discover_groups()
    if not groups:
        print(f"no soundtrack groups found "
              f"(expected {GROUPS_DIR}/<name>/{spec.BIBLE_FILE})", file=sys.stderr)
        return 1
    if args.group:
        groups = [_resolve_group(args.group, groups)]

    index = {"groups": []}
    for g in groups:
        bible = g.load_bible()
        if bible is None:
            print(f"  skip  group {g.name!r}: no {spec.BIBLE_FILE}", file=sys.stderr)
            continue
        manifest = {"group": g.name, "title": bible.title, "key": bible.key,
                    "bpm": bible.bpm, "aesthetic": bible.aesthetic, "tracks": []}
        for name in g.track_names():
            manifest["tracks"].append(
                _render_one(g.track_path(name), bible, g.name, args.out_dir, args.loops))
        out_dir = os.path.join(args.out_dir, g.name)
        os.makedirs(out_dir, exist_ok=True)
        manifest_path = os.path.join(out_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        total = sum(t["seconds"] for t in manifest["tracks"])
        print(f"  {g.name}: {len(manifest['tracks'])} track(s), "
              f"{total:.0f}s -> {manifest_path}")
        index["groups"].append({"name": g.name, "title": bible.title,
                                "tracks": len(manifest["tracks"]),
                                "manifest": os.path.join(g.name, "manifest.json")})

    os.makedirs(args.out_dir, exist_ok=True)
    index_path = os.path.join(args.out_dir, "manifest.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    print(f"\n{len(index['groups'])} group(s) -> {index_path}")
    return 0


TRACK_TEMPLATE = {
    "name": "",
    "extends": "../soundtrack.json",
    "sections": [
        {"name": "intro", "bars": 2, "parts": {
            "pad": {"instrument": "pad", "chords": ["Am", "F", "C", "G"]}}},
        {"name": "loop", "bars": 4, "loop": True, "parts": {
            "lead": {"instrument": "lead", "motif": "main_theme", "transpose": 0},
            "bass": {"instrument": "bass",
                     "notes": [["A2", 1], ["A2", 1], ["F2", 1], ["G2", 1]]},
            "pad": {"instrument": "pad", "chords": ["Am", "F", "C", "G"]},
            "drums": {"instrument": "drums", "drums": {
                "kick": "x...x...", "snare": "....x...", "hat": "x.x.x.x."}}}},
    ],
}

# A fresh group's bible: a generic, valid starting point users edit to taste.
BIBLE_TEMPLATE = {
    "title": "",
    "aesthetic": "synthwave",
    "key": "A minor",
    "bpm": 112,
    "palette": {},
    "motifs": {
        "main_theme": {
            "notes": [["A4", 1], ["C5", 1], ["E5", 1.5], ["D5", 0.5],
                      ["C5", 1], ["B4", 1], ["A4", 2]]},
    },
    "tracks": ["main-theme"],
}


def cmd_new(args) -> int:
    groups = spec.discover_groups()
    g = _resolve_group(args.group, groups)
    path = g.track_path(args.name)
    if os.path.exists(path) and not args.force:
        print(f"{path} exists (use --force to overwrite)", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmpl = dict(TRACK_TEMPLATE, name=args.name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tmpl, f, indent=2)
    print(f"scaffolded {path} — edit it, then: "
          f"python -m vibetracks render {g.name}/{args.name}")
    return 0


def cmd_new_group(args) -> int:
    gdir = os.path.join(GROUPS_DIR, args.name)
    bible_path = os.path.join(gdir, spec.BIBLE_FILE)
    if os.path.exists(bible_path) and not args.force:
        print(f"{bible_path} exists (use --force to overwrite)", file=sys.stderr)
        return 1
    tracks_dir = os.path.join(gdir, spec.TRACKS_SUBDIR)
    os.makedirs(tracks_dir, exist_ok=True)

    bible = dict(BIBLE_TEMPLATE, title=args.title or args.name)
    with open(bible_path, "w", encoding="utf-8") as f:
        json.dump(bible, f, indent=2)

    track_path = os.path.join(tracks_dir, "main-theme.json")
    if not os.path.exists(track_path) or args.force:
        with open(track_path, "w", encoding="utf-8") as f:
            json.dump(dict(TRACK_TEMPLATE, name="main-theme"), f, indent=2)

    print(f"scaffolded group {args.name!r} at {gdir}/")
    print(f"  bible:  {bible_path}")
    print(f"  track:  {track_path}")
    print(f"  render: python -m vibetracks render-all --group {args.name}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="vibetracks", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="validate every group's specs")
    pv.add_argument("--group", help="limit to one group")

    pr = sub.add_parser("render", help="render one track to WAV")
    pr.add_argument("track", help="<group>/<track>, a track name, or a path to JSON")
    pr.add_argument("--group", help="group to look up a bare track name in")
    pr.add_argument("-o", "--out", help="explicit output WAV path")
    pr.add_argument("--out-dir", default=OUT_DIR)
    pr.add_argument("--loops", type=int, default=None, help="loop-section repeats")

    pa = sub.add_parser("render-all", help="render every track in every group")
    pa.add_argument("--group", help="limit to one group")
    pa.add_argument("--out-dir", default=OUT_DIR)
    pa.add_argument("--loops", type=int, default=None)

    pn = sub.add_parser("new", help="scaffold a new track spec in a group")
    pn.add_argument("name")
    pn.add_argument("--group", help="group to create the track in")
    pn.add_argument("--force", action="store_true")

    pg = sub.add_parser("new-group", help="scaffold a whole new soundtrack group")
    pg.add_argument("name")
    pg.add_argument("--title", help="bible title (defaults to the group name)")
    pg.add_argument("--force", action="store_true")

    args = p.parse_args(argv)
    return {
        "validate": cmd_validate,
        "render": cmd_render,
        "render-all": cmd_render_all,
        "new": cmd_new,
        "new-group": cmd_new_group,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
