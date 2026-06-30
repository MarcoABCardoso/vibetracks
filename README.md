# VibeTracks 🎮🎶

A **game-soundtrack lab** for Claude Code. Model a song as plain JSON, then
compile it into real `.wav` audio with a pure-Python synthesizer — no FluidSynth,
no SoX, no ffmpeg, no soundfonts. Just `numpy` + `scipy`.

The point: Claude is great at editing structured text, so a song is described as
a **spec** (diffable, reviewable, version-controlled), and a small compiler turns
that spec into sound. A whole soundtrack stays coherent because every track shares
one **bible** — the same key, tempo family, instrument palette, and recurring
musical motifs.

Tracks are organized into **groups**. A group is one self-contained soundtrack —
its own bible plus tracks — so a single repo can hold several independent scores:
different regions of a game, or entirely different games. The repo ships a demo
group, `neon-frontier`; spin up your own with `new-group` without touching it.

## Quickstart

```bash
pip install -r requirements.txt

python -m vibetracks validate                  # check every group's specs
python -m vibetracks render-all                # render all groups -> out/<group>/*.wav
python -m vibetracks render neon-frontier/battle  # render one track -> out/neon-frontier/battle.wav
python -m vibetracks new menu --group neon-frontier  # scaffold a track in a group
python -m vibetracks new-group spooky-cave     # start a fresh, independent soundtrack
```

A track is addressed as `<group>/<track>`, or as a bare `<track>` with `--group`
(or when the repo has just one group).

## The included demo: *Neon Frontier*

A coherent five-cue synthwave score in A minor. Cohesion comes from a shared key,
palette, and motifs — but the full `main_theme` is stated in only **one** track, so
the set feels like a family of cues rather than one song on repeat:

| Track | Feel | Theme treatment |
|-------|------|------------------|
| `title-theme` | Anthemic | Full hook over Am–F–C–G (the anchor) |
| `exploration` | Calm, spacious | Only the first 3 notes, as a sparse callback |
| `battle` | Fast, driving | Original riff; the shared `danger` motif carries continuity |
| `boss` | Dark, intense | Just the 4-note head, dropped an octave; `danger` leads |
| `victory` | Bright fanfare | Quotes the opening phrase, then an original flourish home |

## How a song is modeled

Each group (`groups/<name>/`) has two file kinds:

- **`groups/<name>/soundtrack.json`** — the *bible*: global `key`, `bpm`,
  `aesthetic`, instrument `palette`, reusable `motifs`, and the `tracks` list.
- **`groups/<name>/tracks/<track>.json`** — one cue. It `extends` the bible
  (inherits key/bpm/palette), may override them, and is built from `sections` of
  named `parts`.

A **part** is exactly one of:

- `notes`: explicit events `[pitch, beats, velocity?]`, e.g. `["A4", 1, 0.8]`
- `motif`: a named motif from the bible, with leitmotif transforms — `slice` (quote a fragment), `transpose`, `stretch` (augment/diminish), `invert`, `retrograde`, `repeat`
- `chords`: chord symbols like `["Am", "F", "C", "G"]`, each held `chord_beats`
- `drums`: per-voice step patterns, e.g. `{"kick": "x...x...", "hat": "x.x.x.x."}`

See **`CLAUDE.md`** for the complete spec reference, **`docs/composition.md`** for
the craft of writing a coherent score (leitmotif transformation, melody, harmony,
form — lessons from Zelda/Castlevania/Undertale and others), and the `/soundtrack`
skill for the compose→render→iterate workflow.

## How it compiles to sound

`spec → sequencer → synth → WAV`. Oscillators (sine/square/saw/triangle/noise),
ADSR envelopes, detuned supersaws, synth drums, and lightweight delay/reverb
(IIR via `scipy.signal.lfilter`) are mixed per part, panned to stereo, and
normalized to a consistent peak so every track matches in loudness.

## Project layout

```
groups/<name>/soundtrack.json   # a group's bible
groups/<name>/tracks/*.json      # one spec per track in that group
vibetracks/                      # the compiler (theory, synth, instruments, sequencer, wavio, CLI)
tests/test_smoke.py              # theory + validation + render sanity
.claude/skills/soundtrack        # the authoring workflow skill
out/<group>/                     # rendered WAVs (gitignored) + per-group manifest.json
```

## Tests

```bash
python -m unittest discover -s tests
```
