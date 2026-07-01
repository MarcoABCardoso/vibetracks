"""Top-level dispatcher across every Lab in this repo.

    python -m labs                       # list the Labs
    python -m labs <lab> <command...>    # run a Lab's CLI
    python -m labs validate              # validate every Lab's specs
    python -m labs new-world <name>      # scaffold a cross-modal world + wired group per Lab

Each Lab keeps its own CLI (``python -m vibetracks ...``, ``python -m
pixeltracks ...``); this dispatcher is the unified front door that makes the
multi-Lab structure visible and routes to them by name. ``new-world`` lives here
rather than in any one Lab because a world is the anchor *above* the Labs — it is
the entry point for a project that spans media, so cross-modal work starts
coherent (each medium's group pre-wired to `extends` the world).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from labkit.registry import LABS, find_lab
from labkit.specbase import SpecError, load_json
from labkit.world import (WORLD_FILE, WORLDS_DIR, check_world, discover_worlds,
                          load_world)


def _print_labs() -> None:
    print("VibeTracks — a multi-Lab game-artifact workshop.\n")
    print("Labs:")
    width = max(len(lab.name) for lab in LABS)
    for lab in LABS:
        print(f"  {lab.name:<{width}}  {lab.summary}")
        print(f"  {'':<{width}}  artifact: {lab.artifact}; "
              f"assets in {lab.assets_dir}/<group>/{lab.bible_file}")
    print("\nRun a Lab:   python -m labs <lab> <command>   "
          "(e.g. python -m labs pixeltracks render-all)")
    print("Or directly: python -m <lab> <command>")
    print("All at once: python -m labs validate")
    print("New world:   python -m labs new-world <name>   "
          "(a cross-modal project spanning every Lab)")


# A fresh world (VISION.md Phase 2): identity + a palette of MEANING + named
# entities, ready to edit. `motifs` starts EMPTY on purpose — a cross-modal motif
# can only bind faces that already exist, so you add one once each medium has a
# motif to name (see worlds/emberhold for a worked two-face motif + transform).
# An empty-motif world is still a coherent shared identity: `validate` passes.
WORLD_TEMPLATE = {
    "name": "",
    "genre": "",
    "tone": "",
    "era": "",
    "_comment": (
        "The Root Spec (VISION.md Phase 2): one world, many Labs. Each medium's "
        "bible `extends` this file, so a single identity feeds every artifact. "
        "Fill in the identity, tune the `meaning` palette and `entities`, then — "
        "once each medium has a motif to bind — add a cross-modal entry under "
        "`motifs` with a `face` per Lab (a melody in vibetracks, a shape in "
        "pixeltracks) and optional `transforms` that move every face together. "
        "See worlds/emberhold/world.json for a worked example."),
    "meaning": {
        "_comment": ("The palette of MEANING — a shape/colour/voice language each "
                     "Lab reads in its own medium. Rename/extend these tags; a "
                     "track or sprite can then declare \"meaning\": \"<tag>\"."),
        "hero":   {"shape": "round, upright, symmetrical", "color": "warm, bright",
                   "voice": "consonant, rising"},
        "steady": {"shape": "solid, grounded",             "color": "cool, muted",
                   "voice": "steady, march-like"},
        "threat": {"shape": "jagged, asymmetrical",        "color": "cold, dark",
                   "voice": "dissonant, falling"},
    },
    "entities": {
        "_comment": ("Named things — places, factions, characters — referenced by "
                     "id from any leaf spec via \"entity\": \"<id>\"."),
        "protagonist": {"kind": "character", "name": "", "meaning": "hero",   "about": ""},
        "home":        {"kind": "place",     "name": "", "meaning": "steady", "about": ""},
        "antagonist":  {"kind": "faction",   "name": "", "meaning": "threat", "about": ""},
    },
    "motifs": {},
}


def _wire_bible_to_world(bible_path: str, world_path: str) -> None:
    """Insert an ``extends`` pointing a freshly scaffolded group bible at the world.

    Kept generic — it only rewrites JSON by the registry's layout, so it needs no
    per-Lab schema knowledge: load the bible, add ``extends`` (a path relative to
    the bible, forward-slashed) right after ``title``, write it back.
    """
    data = load_json(bible_path)
    if "extends" in data:
        return
    rel = os.path.relpath(world_path, os.path.dirname(bible_path)).replace(os.sep, "/")
    out, inserted = {}, False
    for k, v in data.items():
        out[k] = v
        if k == "title" and not inserted:
            out["extends"] = rel
            inserted = True
    if not inserted:
        out = {"extends": rel, **data}
    with open(bible_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def cmd_new_world(argv) -> int:
    p = argparse.ArgumentParser(prog="labs new-world",
                                description="Scaffold a cross-modal world (the Root Spec).")
    p.add_argument("name", help="world name, created at worlds/<name>/world.json")
    p.add_argument("--title", help="display name (defaults to <name>)")
    p.add_argument("--media", nargs="*", metavar="LAB",
                   help="which Labs to scaffold a wired group for (default: all; "
                        "give none of these to still get all, or use --world-only)")
    p.add_argument("--world-only", action="store_true",
                   help="scaffold only world.json, no per-Lab groups")
    p.add_argument("--force", action="store_true", help="overwrite an existing world.json")
    args = p.parse_args(argv)

    wdir = os.path.join(WORLDS_DIR, args.name)
    world_path = os.path.join(wdir, WORLD_FILE)
    if os.path.exists(world_path) and not args.force:
        print(f"{world_path} exists (use --force to overwrite)", file=sys.stderr)
        return 1
    os.makedirs(wdir, exist_ok=True)
    world = dict(WORLD_TEMPLATE, name=args.title or args.name)
    with open(world_path, "w", encoding="utf-8") as f:
        json.dump(world, f, indent=2)
    print(f"scaffolded world {args.name!r} at {world_path}")

    media = [] if args.world_only else (args.media or [lab.name for lab in LABS])
    for lab_name in media:
        lab = find_lab(lab_name)
        rc = lab.main(["new-group", args.name])
        if rc:
            print(f"  !!  {lab_name}: new-group failed", file=sys.stderr)
            continue
        bible_path = os.path.join(lab.assets_dir, args.name, lab.bible_file)
        _wire_bible_to_world(bible_path, world_path)
        print(f"  wired {lab_name} group -> extends {os.path.basename(world_path)}")

    print("\nNext: edit the world's identity/meaning/entities, then author in each "
          "Lab's group.\nCheck coherence any time with:  python -m labs validate")
    return 0


def _validate_worlds() -> int:
    """Validate every world (the Root Spec) and check coherence ACROSS Labs.

    This is the cross-modal guarantee: a world's cross-modal motif is only real if
    every medium's *face* (the melody it names in the music bible, the shape it
    names in the art bible) actually exists. No prompt-per-asset workflow can make
    that promise — coherence here is checked, not hoped for.
    """
    worlds = discover_worlds()
    if not worlds:
        return 0
    print("=== worlds ===")
    rc = 0
    for name, path in worlds:
        try:
            world = load_world(path)
        except SpecError as e:
            print(f"  ERR  {e}")
            rc = 1
            continue
        errs = check_world(world)
        # `_`-prefixed keys are documentation (a template's `_comment`), not content.
        n_ent = sum(1 for k in world.entities if not k.startswith("_"))
        n_mot = sum(1 for k in world.motifs if not k.startswith("_"))
        print(f"  world {name!r}: {world.name}  "
              f"({n_ent} entities, {n_mot} cross-modal motif(s))")
        for mid, motif in world.motifs.items():
            if mid.startswith("_"):
                continue
            faces = ", ".join(f"{lab}:{f['group']}/{f['motif']}"
                              for lab, f in motif.get("faces", {}).items())
            print(f"    motif {mid!r} -> {faces}")
        for e in errs:
            print(f"  ERR  {e}")
        if errs:
            rc = 1
    print("  ok  worlds coherent." if rc == 0 else "  worlds INCOHERENT.")
    return rc


def _validate_all() -> int:
    rc = 0
    for lab in LABS:
        print(f"=== {lab.name} ===")
        rc |= lab.main(["validate"]) or 0
    rc |= _validate_worlds()
    return rc


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "list"):
        _print_labs()
        return 0
    if argv[0] == "validate":
        return _validate_all()
    if argv[0] == "new-world":
        return cmd_new_world(argv[1:])
    lab = find_lab(argv[0])
    return lab.main(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
