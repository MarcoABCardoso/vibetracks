"""VibeTracks CLI: validate specs and compile them to WAV.

    python -m vibetracks validate                 # check the bible + all tracks
    python -m vibetracks render tracks/x.json      # render one track to out/
    python -m vibetracks render-all                # render every track in the bible
    python -m vibetracks new <name>                # scaffold a new track spec

Run from the project root (where ``soundtrack.json`` lives).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import spec
from .sequencer import render_track
from .wavio import write_wav

BIBLE = "soundtrack.json"
TRACKS_DIR = "tracks"
OUT_DIR = "out"


def _track_path(name: str) -> str:
    """Accept either a bare track name or a path to its JSON file."""
    if name.endswith(".json") or os.path.sep in name:
        return name
    return os.path.join(TRACKS_DIR, f"{name}.json")


def cmd_validate(args) -> int:
    ok = True
    bible = None
    if os.path.exists(BIBLE):
        try:
            bible = spec.load_bible(BIBLE)
            print(f"  ok  {BIBLE}  (key {bible.key}, {bible.bpm:g} bpm, "
                  f"{len(bible.motifs)} motif(s), {len(bible.tracks)} track(s))")
        except spec.SpecError as e:
            print(f" ERR  {e}")
            ok = False
    else:
        print(f"  --  no {BIBLE} found; tracks will use built-in defaults")

    names = bible.tracks if bible else []
    if not names:
        names = [os.path.splitext(f)[0] for f in sorted(os.listdir(TRACKS_DIR))
                 if f.endswith(".json")] if os.path.isdir(TRACKS_DIR) else []
    for name in names:
        path = _track_path(name)
        try:
            t = spec.resolve_track(path, bible)
            secs = ", ".join(s.get("name", "?") for s in t["sections"])
            print(f"  ok  {path}  ({t['bpm']:g} bpm, sections: {secs})")
        except (spec.SpecError, FileNotFoundError) as e:
            print(f" ERR  {e}")
            ok = False
    print("\nAll specs valid." if ok else "\nValidation failed.")
    return 0 if ok else 1


def _render_one(name: str, bible, out_dir: str, loops) -> dict:
    path = _track_path(name)
    track = spec.resolve_track(path, bible)
    buf = render_track(track, loops=loops)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{track['name']}.wav")
    dur = write_wav(out_path, buf)
    peak = float(__import__("numpy").max(__import__("numpy").abs(buf)))
    print(f"  rendered  {out_path}  ({dur:.1f}s, peak {peak:.2f})")
    return {"track": track["name"], "file": out_path, "seconds": round(dur, 2),
            "peak": round(peak, 3), "bpm": track["bpm"], "key": track["key"]}


def cmd_render(args) -> int:
    bible = spec.load_bible(BIBLE) if os.path.exists(BIBLE) else None
    info = _render_one(args.track, bible, args.out_dir, args.loops)
    if args.out:
        # Honour an explicit output path by moving the rendered file.
        os.replace(info["file"], args.out)
        print(f"  -> {args.out}")
    return 0


def cmd_render_all(args) -> int:
    if not os.path.exists(BIBLE):
        print(f"need {BIBLE} to render-all", file=sys.stderr)
        return 1
    bible = spec.load_bible(BIBLE)
    manifest = {"title": bible.title, "key": bible.key, "bpm": bible.bpm,
                "aesthetic": bible.aesthetic, "tracks": []}
    for name in bible.tracks:
        manifest["tracks"].append(_render_one(name, bible, args.out_dir, args.loops))
    manifest_path = os.path.join(args.out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    total = sum(t["seconds"] for t in manifest["tracks"])
    print(f"\n{len(manifest['tracks'])} track(s), {total:.0f}s total -> {manifest_path}")
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


def cmd_new(args) -> int:
    path = _track_path(args.name)
    if os.path.exists(path) and not args.force:
        print(f"{path} exists (use --force to overwrite)", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmpl = dict(TRACK_TEMPLATE, name=args.name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tmpl, f, indent=2)
    print(f"scaffolded {path} — edit it, then: python -m vibetracks render {args.name}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="vibetracks", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate", help="validate the bible and all track specs")

    pr = sub.add_parser("render", help="render one track to WAV")
    pr.add_argument("track", help="track name or path to its JSON")
    pr.add_argument("-o", "--out", help="explicit output WAV path")
    pr.add_argument("--out-dir", default=OUT_DIR)
    pr.add_argument("--loops", type=int, default=None, help="loop-section repeats")

    pa = sub.add_parser("render-all", help="render every track in the bible")
    pa.add_argument("--out-dir", default=OUT_DIR)
    pa.add_argument("--loops", type=int, default=None)

    pn = sub.add_parser("new", help="scaffold a new track spec")
    pn.add_argument("name")
    pn.add_argument("--force", action="store_true")

    args = p.parse_args(argv)
    return {
        "validate": cmd_validate,
        "render": cmd_render,
        "render-all": cmd_render_all,
        "new": cmd_new,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
