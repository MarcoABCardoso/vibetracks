# VibeTracks — guide for Claude

This repo is a **coherence engine for solo game worlds** — a multi-Lab
workshop that lets a solo dev (with an AI copilot) build a whole game's worth of
assets that read as *one game*. A *Lab* is a structured spec → validate →
compile → iterate workshop for one artifact class. Every Lab is the same machine
with a different theory; `VISION.md` frames the product (who it's for, honest
scope, roadmap).

| Lab | Artifact | Author edits | Compiles to | Skill | Spec reference |
|-----|----------|--------------|-------------|-------|----------------|
| **VibeTracks** | music / SFX | JSON song specs | WAV (pure-Python synth) | `/soundtrack` | `vibetracks/CLAUDE.md` |
| **PixelTracks** | sprites / images | JSON sprite specs | PNG (procedural raster) | `/spritesheet` | `pixeltracks/CLAUDE.md` |

> 🖼️ **PixelTracks is a capable pixel-art engine.** Its deterministic raster
> engine renders coherent sprite sets straight from JSON — palette-swap
> leitmotifs, skeleton-rigged poses, frame animation, multi-object scenes, even
> higher-detail bust portraits — with no image model in the loop. It's tuned for
> pixel art and flat/stylised work, not photoreal or painterly illustration; author
> within that lane and it stands beside the music Lab.

## This file is an index, not the whole manual

The per-Lab **spec reference lives next to each Lab's code** so you only load the
detail you need:

- **VibeTracks (music)** → **`vibetracks/CLAUDE.md`** — bible/track/part model,
  instrument engines, expression, where to edit.
- **PixelTracks (sprites)** → **`pixeltracks/CLAUDE.md`** — bible/sprite/layer
  model, shape transforms, authoring + posing notes.

Claude Code loads a subdirectory's `CLAUDE.md` automatically when you work on
files there, so opening the relevant Lab pulls in its reference. Read the matching
one before authoring specs — this index is deliberately thin.

## Picking the right Lab

Game *music* → VibeTracks (`/soundtrack`); game *sprites / pixel art / images* →
PixelTracks (`/spritesheet`).

## The dispatcher & layout

A single front door unifies the Labs:

```bash
python -m labs                       # list the Labs
python -m labs <lab> <command...>    # run a Lab's CLI (e.g. labs pixeltracks render-all)
python -m labs validate              # validate every Lab's specs
python -m <lab> <command...>         # or run a Lab directly
```

Every Lab ships the **same CLI verbs** (`validate` / `render` / `render-all` /
`new` / `new-group`) and the same addressing (`<group>/<asset>`, a bare `<asset>`
with `--group`, or a path). All assets live under one **`groups/`** tree, split by
medium:

```
worlds/<w>/world.json                                # Root Specs (the cross-medium bible; demo: emberhold)
groups/music/<g>/soundtrack.json + tracks/*.json     # VibeTracks groups (demo: neon-frontier)
groups/sprites/<g>/artbook.json  + sprites/*.json    # PixelTracks groups (demo: mossy-hollow)
out/<group>/                                          # rendered artifacts (gitignored)
```

## The Root Spec — one world, many artifacts

A **world** (`worlds/<name>/world.json`) is the coherence anchor *above* the
Labs: the single identity from which each medium's bible descends. A group bible
`extends` a world exactly as a track/sprite `extends` its bible. A world declares
what is true *across* modalities — identity, a **palette of meaning** (shape/
colour/voice tags), named **entities**, and **cross-modal motifs**: one root
motif with a *face* in every medium, plus **transforms** that move every face
together (darken the root once → both the art and the music fall in step).

`python -m labs validate` validates each world and runs a **cross-Lab coherence
pass**: every motif face and transform target must resolve to a real motif/spec
in the named Lab, so the media provably cannot drift apart. The bundled
`emberhold` world spans both media (`groups/music/emberhold` +
`groups/sprites/emberhold`); its `ember` motif is the gold sun-crest you *see* and
the `ember_theme` you *hear*, with a `fallen` transform (the `dark-knight`
palette-swap ⇄ the `siege` dirge). The meaning palette and entities reach the
**leaf specs** too: a track or sprite may declare what it `means` (a meaning tag)
and which `entities` it is about, checked against the world at validate time
(shared `check_spec_refs` in `labkit`). Not every group needs a world — a bible
with no `extends` is a standalone identity, exactly as before.

### When to use a world (and when not to)

A world earns its keep only when something has to cohere *across* media; its
unique machinery — the meaning palette, cross-modal motifs, `fallen`-style
transforms — is inert or redundant for a single artifact class. So don't default
to `worlds/` for every job:

| The ask | Start at |
|---------|----------|
| one artifact class ("a boss theme", "a fox sprite") | a **standalone group** (`new-group`), no world |
| music **and** art for one game; "a whole world"; a shared identity across media | a **world** (`new-world`), then author in each Lab's group |
| single medium now, maybe more later | a group now — **promote** it later (add `extends`) with no rewrite |

Prefer **lazy promotion**: build the group world-less, and only add the world the
moment a second medium or a genuine cross-modal motif appears. A world-scale
project starts coherent with:

```bash
python -m labs new-world <name>            # world.json + one wired group per Lab
python -m labs new-world <name> --media vibetracks   # only some media
python -m labs new-world <name> --world-only         # just the Root Spec
```

Each scaffolded group's bible is pre-wired to `extends` the new world; the world
ships with a starter meaning palette + entities and an **empty** `motifs` map (add
a cross-modal motif once each medium has a face to bind). `python -m labs validate`
passes immediately, so you fill in identity from a coherent base.

## The shared core & adding a Lab

- `labkit/` — `SpecError` + `load_json` + the shared `extends_path` inheritance
  helper (`specbase.py`), generic group discovery (`groups.py`), the `Lab`
  registry (`registry.py`), and the Root Spec: `World` + `load_world` +
  cross-Lab `check_world` coherence (`world.py`). Both Labs build on it.
- `labs/__main__.py` — the dispatcher (`python -m labs`).
- To add a Lab: create a package mirroring the existing layout (model + validator +
  deterministic engine + CLI with the same verbs) and append a `Lab(...)` entry to
  `labkit/registry.py`, pointing `assets_dir` at its `groups/<medium>/` subtree.
  See `VISION.md` for the roadmap of future Labs.
