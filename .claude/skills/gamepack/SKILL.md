---
name: gamepack
description: Turn a game description into a coherent Godot resource pack. Use when the user describes a game and wants ready-to-use assets (music + sprites) exported for Godot 4 (or asks for a "resource pack", "asset pack", "assets for my game"). Drives the whole pipeline — world → assets → build → deliver.
---

# From a game description to a Godot resource pack

This repo is a **coherence engine**: the user describes a game, you author its
assets as JSON across the Labs (music + sprites), and one command compiles and
**exports a drop-in Godot 4 resource pack** (PNG/WAV + `.import` + SpriteFrames
`.tres`, zipped). The value over ad-hoc generation is that everything descends
from one **world** — a shared identity, palette of meaning, and cross-modal
motifs — so the pack reads as *one game*, coherent by construction.

You are the orchestrator. This skill *composes* the two authoring skills rather
than repeating them: use **`/soundtrack`** for music and **`/spritesheet`** for
sprites, then build. Read the root `CLAUDE.md` for the multi-Lab overview.

## 1. Understand the game (interview, briefly)

From the user's description, pin down what the pack needs. Ask only what you can't
infer:

- **Identity** — genre, tone, era/setting (feeds `world.json`).
- **Entities** — the protagonist, key places, factions/enemies (named things the
  assets are *about*).
- **Meaning palette** — the shape/colour/voice language (e.g. hope = round/warm/
  rising; threat = jagged/cold/falling). This is what makes media move together.
- **Asset list** — which **tracks** (title theme, battle, exploration, boss…) and
  which **sprites** (hero, party, enemies, items, tiles) — and which sprites need
  **animation** (walk, attack, idle).

Propose a concrete asset list and confirm scope before authoring. Keep the first
pass small and coherent (a hero + one enemy + a title theme + a battle theme reads
as a game); breadth can come later.

## 2. Scaffold the world

A game spans media, so start at the world layer:

```bash
python -m labs new-world <game>            # world.json + a wired group per Lab
```

This creates `worlds/<game>/world.json` (identity + starter meaning palette +
entities, empty `motifs`) and, under each Lab, a group whose bible already
`extends` the world (`groups/music/<game>/`, `groups/sprites/<game>/`). Fill in
the world's identity, `meaning`, and `entities` from the interview. Add a
cross-modal `motif` entry once each medium has a face to bind (a melody + a shape)
— see `worlds/emberhold/world.json` for the worked example, and validate coherence
any time with `python -m labs validate`.

If the user only wants one medium for now, `--media vibetracks` (or `pixeltracks`)
scaffolds just that one; promote later by adding the other group.

## 3. Author the assets (delegate to the Lab skills)

Work medium by medium, staying inside the world's groups:

- **Music** → follow **`/soundtrack`**: establish the bible (key/BPM/instrument
  palette), compose the main motif, then each track (`new` → edit sections/parts →
  `validate` → `render` → send the WAV → iterate). Reuse the world's motif so
  themes recur.
- **Sprites** → follow **`/spritesheet`**: establish the artbook (palette + shape
  motifs), draw the hero, then each sprite (`new` → `validate` → `inspect` → `render`
  → read the PNG → iterate). For animation, author `frames` with `hold` timings and
  set an `fps` (bible-level default or per sprite; default 10) — this becomes the
  Godot SpriteFrames playback rate.

Coherence discipline (the whole point): every bible `extends` the world; colours
by name and melodies by motif; the meaning tags and entities on leaf specs tie
back to the world so `validate` catches drift.

## 4. Build the pack

One command renders every asset and exports the engine pack:

```bash
python -m labs build <game> --engine godot        # -> dist/<game>/ + dist/<game>.zip
```

It builds only the groups under `<game>`'s world. The pack contains, per asset:
a texture/audio file, a `.import` (crisp uncompressed textures; forward-loop on
looping music), and a **SpriteFrames `.tres`** for every animated sprite (frame
regions + per-frame `hold` durations + `fps` + loop). A `pack.json` indexes it and
a `README.md` explains install. See `docs/godot.md` for how the pieces map to
Godot nodes.

## 5. Deliver

Hand over `dist/<game>.zip` with `SendUserFile`, and tell the user to extract it at
their Godot project root (so it lands at `res://<game>/`), then:

- animated sprite → `AnimatedSprite2D` + the `.tres`, `play("default")`;
- still sprite → `Sprite2D` + the `.png`;
- music → `AudioStreamPlayer` + the `.wav`;
- for pixel-crisp rendering, set the project's default texture filter to *Nearest*.

Commit the **specs** (`worlds/`, `groups/`), not the build output (`out/`, `dist/`
are gitignored) — the pack regenerates from the specs with one `build`.

## Notes

- Other engines: the exporter is a registry entry (`labkit/export.py`); today only
  `godot` ships. If asked for another engine, say Godot is the supported target.
- A true `.pck` needs the Godot binary (unavailable here); the drop-in folder + zip
  is the deliverable and imports identically.
