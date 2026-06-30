# VibeTracks — guide for Claude

This repo is a **game-soundtrack lab**: songs are modeled as JSON specs and
compiled to WAV by a pure-Python synth (`numpy` + `scipy` only — no FluidSynth,
SoX, ffmpeg, or soundfonts; those aren't installable in this environment).

When the user wants to make game music, use the **`/soundtrack` skill** — it
encodes the compose→render→iterate workflow. This file is the **spec reference**.

## Commands

```bash
python -m vibetracks validate            # check the bible + all track specs
python -m vibetracks render <name|path>  # render one track to out/<name>.wav
python -m vibetracks render-all          # render every track + out/manifest.json
python -m vibetracks new <name>          # scaffold tracks/<name>.json
python -m unittest discover -s tests     # run tests
```

Render is CPU-bound (pure-Python DSP): roughly real-time-ish — a 25 s track takes
~20 s. For a quick check, render a single short track rather than `render-all`.

## The model

### Bible — `soundtrack.json`
Global identity inherited by every track.

| Field | Meaning |
|-------|---------|
| `title`, `aesthetic` | Labels (informational). |
| `key` | e.g. `"A minor"`. Used for validation + `scale`/`chord` helpers. |
| `bpm` | Default tempo; tracks may override. |
| `palette` | Map of instrument name → patch overrides (merged onto the defaults in `vibetracks/instruments.py`). |
| `motifs` | Named melodies, each `{"notes": [[pitch, beats, vel?], ...]}`. The cohesion mechanism. |
| `tracks` | Ordered track names that `render-all` builds. |

### Track — `tracks/<name>.json`

| Field | Meaning |
|-------|---------|
| `name` | Output filename stem. |
| `extends` | Path to the bible, e.g. `"../soundtrack.json"`. |
| `key`, `bpm`, `time_signature` | Optional overrides (`time_signature` default `[4,4]`). |
| `palette` | Optional per-track patch overrides. |
| `loops` | Default repeat count for `"loop": true` sections (CLI `--loops` overrides). |
| `sections` | List of `{name, bars, loop?, repeat?, parts}`. |

Section assembly: non-loop sections play `repeat` times (default 1); a section with
`"loop": true` repeats `loops` times (default 2). Sections are concatenated in order,
so the usual shape is `intro` (once) + `loop` (×N).

### Parts
Each section's `parts` is a map of part-name → part. Every part needs an
`instrument` (a palette name) and is **exactly one** of:

- **`notes`** — `[[pitch, beats, velocity?], ...]`. `pitch` is a note name
  (`"C#4"`, `"Bb2"`); use `null` for a rest. `beats` are quarter notes.
  Supports `transpose` (semitones) and `repeat` (tile the figure).
- **`motif`** — name of a bible motif; supports `transpose` and `repeat`. Prefer
  this for melodic cues so the theme recurs across tracks.
- **`chords`** — `["Am", "F", "C", "G"]`; each chord held `chord_beats` (default =
  one bar), tiled to fill the section. Qualities: `m, maj, dim, aug, sus2, sus4, 7,
  maj7, m7, add9, 5`, default major. `octave` sets the chord root octave.
- **`drums`** — `{"kick": "x...x...", "snare": "....x...", "hat": "x.x.x.x.", ...}`.
  Each string is one bar; `x`/`X` = hit, `o` = open hi-hat (on the `hat` voice),
  `.`/`-` = rest. Patterns tile across the section's bars.

Optional per-part knobs: `gain` (level), `pan` (−1 left … 1 right).

## How compilation works (where to edit)

- `vibetracks/theory.py` — note↔frequency, scales, chord parsing, transpose.
- `vibetracks/synth.py` — oscillators, ADSR, drum synths, filters/delay/reverb,
  normalize. Add new waveforms or effects here.
- `vibetracks/instruments.py` — `DEFAULT_PALETTE` patches + the per-note renderer.
- `vibetracks/sequencer.py` — schedules parts on a beat grid, mixes, pans, loops,
  master-normalizes. Add new part *kinds* here (and validation in `spec.py`).
- `vibetracks/spec.py` — load/validate the bible and tracks; `extends` inheritance.
- `vibetracks/wavio.py` — float buffer → 16-bit PCM WAV (stdlib `wave`).

## Conventions

- Keep tracks coherent: `extends` the bible, reuse motifs, keep keys/tempos related.
- The master stage normalizes every track to the same peak (≈0.89), so don't fight
  loudness with per-part `gain` — use `gain` only for *balance within* a track.
- WAV is the only output format (no MIDI/OGG yet). 44.1 kHz, 16-bit, stereo.
- Rendered `out/*.wav` are build artifacts (gitignored); commit the JSON specs.
