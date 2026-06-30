# VibeTracks 🎮🎶

A **game-soundtrack lab** for Claude Code. Model a song as plain JSON, then
compile it into real `.wav` audio with a pure-Python synthesizer — no FluidSynth,
no SoX, no ffmpeg, no soundfonts. Just `numpy` + `scipy`.

The point: Claude is great at editing structured text, so a song is described as
a **spec** (diffable, reviewable, version-controlled), and a small compiler turns
that spec into sound. A whole soundtrack stays coherent because every track shares
one **bible** — the same key, tempo family, instrument palette, and recurring
musical motifs.

## Quickstart

```bash
pip install -r requirements.txt

python -m vibetracks validate        # check the bible + every track spec
python -m vibetracks render-all      # render all tracks -> out/*.wav + manifest.json
python -m vibetracks render battle   # render one track -> out/battle.wav
python -m vibetracks new menu        # scaffold tracks/menu.json
```

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

Two file kinds:

- **`soundtrack.json`** — the *bible*: global `key`, `bpm`, `aesthetic`, instrument
  `palette`, reusable `motifs`, and the `tracks` list.
- **`tracks/<name>.json`** — one cue. It `extends` the bible (inherits key/bpm/palette),
  may override them, and is built from `sections` of named `parts`.

A **part** is exactly one of:

- `notes`: explicit events `[pitch, beats, velocity?]`, e.g. `["A4", 1, 0.8]`
- `motif`: a named motif from the bible, with optional `transpose`, `repeat`, and `slice` (quote a fragment)
- `chords`: chord symbols like `["Am", "F", "C", "G"]`, each held `chord_beats`
- `drums`: per-voice step patterns, e.g. `{"kick": "x...x...", "hat": "x.x.x.x."}`

See **`CLAUDE.md`** for the complete spec reference, and the `/soundtrack` skill
for the compose→render→iterate workflow.

## How it compiles to sound

`spec → sequencer → synth → WAV`. Oscillators (sine/square/saw/triangle/noise),
ADSR envelopes, detuned supersaws, synth drums, and lightweight delay/reverb
(IIR via `scipy.signal.lfilter`) are mixed per part, panned to stereo, and
normalized to a consistent peak so every track matches in loudness.

## Project layout

```
soundtrack.json          # the bible
tracks/*.json            # one spec per track
vibetracks/              # the compiler (theory, synth, instruments, sequencer, wavio, CLI)
tests/test_smoke.py      # theory + validation + render sanity
.claude/skills/soundtrack # the authoring workflow skill
out/                     # rendered WAVs (gitignored) + manifest.json
```

## Tests

```bash
python -m unittest discover -s tests
```
