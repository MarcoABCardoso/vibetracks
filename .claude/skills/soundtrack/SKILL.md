---
name: soundtrack
description: Compose or extend a coherent game soundtrack in this VibeTracks repo. Use when the user wants to create game music, add or revise a track, design the musical identity (key/tempo/instruments/motifs), or render specs to WAV. Drives the model→compile→listen→iterate loop.
---

# Composing a game soundtrack with VibeTracks

VibeTracks models a song as **JSON** and compiles it to **WAV** with a pure-Python
synth (`numpy` + `scipy`, no system audio tools). Your job is to author/edit the
JSON specs and render them. A whole soundtrack stays coherent because every track
shares one **bible** (`soundtrack.json`): the same key, tempo family, instrument
`palette`, and reusable **motifs**.

Read `CLAUDE.md` for the full spec reference. The loop below is the procedure.

## 1. Establish the bible (do this first, once)

If `soundtrack.json` doesn't reflect the game yet, interview the user briefly:
- **Game & mood** — genre, setting, emotional tone.
- **Track list** — which cues are needed (title, exploration, battle, boss, victory, …).
- **Musical identity** — key (default `A minor`), base BPM, aesthetic (synthwave by default).

Then write `soundtrack.json`: `title`, `key`, `bpm`, `aesthetic`, the `palette`
(override only the patch params you want; defaults live in `vibetracks/instruments.py`),
and the `tracks` list.

## 2. Compose the main motif before any track

The motif is the glue that makes separate cues feel like one score. Author at
least a `main_theme` under `motifs` (8 beats / 2 bars is a good hook), in the home
key. Optionally add answer phrases like `danger` for tense cues.

## 3. Draft → render → listen → iterate (per track)

1. `python -m vibetracks new <name>` to scaffold, or hand-write `tracks/<name>.json`.
   A track `extends` the bible and overrides `bpm`/`key`/`palette` as needed. Build
   it from `sections`; each section has `bars` and named `parts`. A part is exactly
   one of: `notes`, `motif` (+`transpose`/`repeat`), `chords`, or `drums`.
2. `python -m vibetracks validate` — catch bad pitches/instruments/motifs early.
3. `python -m vibetracks render <name>` — writes `out/<name>.wav`.
4. **Send the WAV to the user** (SendUserFile) and ask for direction. Translate
   feedback into spec edits: "too busy" → thin the drums/arp; "needs energy" →
   raise BPM or add an eighth-note bass; "doesn't fit the others" → reuse the motif
   or pull the chords toward the bible's progression.

## 4. Derive variation tracks from the theme (coherence ≠ repetition)

Make new cues feel like the same score — but don't restate the whole hook in every
track, or they all sound like one song. **State the full theme in one place** (the
title), then vary its prominence everywhere else. Tools for that:
- **Fragment it** — `"slice": [0, 3]` quotes just the opening cell as a callback.
- **Move it off the lead / drop it** — let a track stand on its own melody and rely
  on the shared key, palette, and a secondary motif (e.g. `danger`) for continuity.
- **Transform it** — `transpose`, change tempo, re-harmonise.

How the demo does it: `title-theme` states the full hook; `exploration` quotes only
its first 3 notes; `battle` has an original riff with `danger` underneath; `boss`
echoes just the 4-note head dropped `-12`; `victory` quotes the opening phrase then
breaks into an original flourish.

## 5. Master pass

`python -m vibetracks render-all` renders every track and writes `out/manifest.json`
(per-track duration/peak). The engine normalizes every track to the same peak, so
loudness already matches; review the manifest for sane durations and confirm loop
sections (`"loop": true`) tile cleanly. Commit specs when the user is happy.

## Cohesion checklist

- [ ] Every track `extends` `soundtrack.json`.
- [ ] Every melodic cue references a shared motif (transposed/retimed), not a one-off tune.
- [ ] Tempos and keys are related (same key family; tempos are deliberate, not random).
- [ ] `validate` passes and `render-all` produces a clean manifest.
