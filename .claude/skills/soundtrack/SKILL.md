---
name: soundtrack
description: Compose or extend a coherent game soundtrack in this VibeTracks repo. Use when the user wants to create game music, add or revise a track, design the musical identity (key/tempo/instruments/motifs), or render specs to WAV. Drives the model→compile→listen→iterate loop.
---

# Composing a game soundtrack with VibeTracks

VibeTracks models a song as **JSON** and compiles it to **WAV** with a pure-Python
synth (`numpy` + `scipy`, no system audio tools). Your job is to author/edit the
JSON specs and render them. Tracks live in **groups** — each `groups/music/<name>/`
is a self-contained soundtrack with its own bible
(`groups/music/<name>/soundtrack.json`) and `tracks/`. A group stays coherent
because every track shares its bible: the same key, tempo family, instrument
`palette`, and reusable **motifs**.

Read `vibetracks/CLAUDE.md` for the full spec reference, and **`docs/composition.md` for the
craft** — how to write a score that sounds intentional (leitmotif transformation,
singable melodies, accompaniment-driven energy, harmony, form). The loop below is
the procedure; the composition guide is what makes the output good.

## 0. Pick (or create) the group

A new game or region is a **new group** — never overwrite the demo (`neon-frontier`)
or another existing bible. `python -m vibetracks new-group <name> --title "<Title>"`
scaffolds `groups/music/<name>/` with a starter bible and a `main-theme` track. If the
user is extending a soundtrack that already exists, work inside its group instead.

## 1. Establish the bible (do this first, once)

Edit the group's `groups/music/<name>/soundtrack.json`. If it doesn't reflect the game
yet, interview the user briefly:
- **Game & mood** — genre, setting, emotional tone.
- **Track list** — which cues are needed (title, exploration, battle, boss, victory, …).
- **Musical identity** — key (default `A minor`), base BPM, aesthetic (synthwave by default).

Then write the bible: `title`, `key`, `bpm`, `aesthetic`, the `palette` (override
only the patch params you want; defaults live in `vibetracks/instruments.py`), and
the `tracks` list.

## 2. Compose the main motif before any track

The motif is the glue that makes separate cues feel like one score. Author at
least a `main_theme` under `motifs` (8 beats / 2 bars is a good hook), in the home
key. Optionally add answer phrases like `danger` for tense cues.

## 3. Draft → render → listen → iterate (per track)

1. `python -m vibetracks new <name> --group <g>` to scaffold, or hand-write
   `groups/music/<g>/tracks/<name>.json`. A track `extends` the bible and overrides
   `bpm`/`key`/`palette` as needed. Build it from `sections`; each section has
   `bars` and named `parts`. A part is exactly one of: `notes`, `motif`
   (+`transpose`/`repeat`), `chords`, or `drums`.
2. `python -m vibetracks validate` — catch bad pitches/instruments/motifs early.
3. `python -m vibetracks render <g>/<name>` — writes `out/<g>/<name>.wav`.
4. **Send the WAV to the user** (SendUserFile) and ask for direction. Translate
   feedback into spec edits: "too busy" → thin the drums/arp; "needs energy" →
   raise BPM or add an eighth-note bass; "doesn't fit the others" → reuse the motif
   or pull the chords toward the bible's progression.

## 4. Derive variation tracks from the theme (coherence ≠ repetition)

Make new cues feel like the same score — but don't restate the whole hook in every
track, or they all sound like one song. **State the full theme in one place** (the
title), then vary its prominence everywhere else. Tools for that (see `docs/composition.md` for the full kit):
- **Fragment it** — `"slice": [0, 3]` quotes just the opening cell as a callback.
- **Transform it** — `transpose`, `stretch` (2.0 = grand/augmented, 0.5 = frantic/
  diminished), `invert`, `retrograde`. Same DNA, opposite mood (the Undertale move).
- **Move it off the lead / drop it** — let a track stand on its own melody and rely
  on the shared key, palette, and a secondary motif (e.g. `danger`) for continuity.

How the demo does it: `title-theme` states the full hook; `exploration` quotes only
its first 3 notes; `battle` has an original riff with `danger` underneath; `boss`
echoes just the 4-note head dropped `-12`; `victory` quotes the opening phrase then
breaks into an original flourish.

## 5. Master pass

`python -m vibetracks render-all --group <g>` renders every track in the group and
writes `out/<g>/manifest.json` (per-track duration/peak); plain `render-all` does
every group plus a top-level `out/manifest.json` index. The engine normalizes every
track to the same peak, so loudness already matches; review the manifest for sane
durations and confirm loop sections (`"loop": true`) tile cleanly. Commit specs when
the user is happy.

## Cohesion checklist

- [ ] Every track `extends` its group's `soundtrack.json`.
- [ ] Every melodic cue references a shared motif (transposed/retimed), not a one-off tune.
- [ ] Tempos and keys are related (same key family; tempos are deliberate, not random).
- [ ] `validate` passes and `render-all` produces a clean manifest.
