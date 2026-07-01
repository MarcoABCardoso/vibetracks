# VibeTracks — guide for Claude

This repo is a **multi-Lab game-artifact workshop**. A *Lab* is a structured
spec → validate → compile → iterate workshop for one artifact class. Every Lab is
the same machine with a different theory (see `VISION.md`):

| Lab | Artifact | Author edits | Compiles to | Skill | Spec reference |
|-----|----------|--------------|-------------|-------|----------------|
| **VibeTracks** | music / SFX | JSON song specs | WAV (pure-Python synth) | `/soundtrack` | `vibetracks/CLAUDE.md` |
| **PixelTracks** | sprites / images | JSON sprite specs | PNG (procedural raster) | `/spritesheet` | `pixeltracks/CLAUDE.md` |

> ⚠️ **PixelTracks is early, exploratory work.** Its procedural raster engine is
> still limited, so rendered sprites are rough and results may fall well short of
> the music Lab. It's a proof that the shared core generalizes to a second medium,
> not a finished sprite generator — set expectations accordingly.

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
palette-swap ⇄ the `siege` dirge). Not every group needs a world — a bible with
no `extends` is a standalone identity, exactly as before.

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
