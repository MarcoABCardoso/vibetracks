# VibeTracks — the music Lab (spec reference)

The music Lab of this repo (see the root `CLAUDE.md` for the multi-Lab overview
and how to pick a Lab). Songs are modeled as JSON specs and compiled to WAV by a
pure-Python synth (`numpy` + `scipy` only — no FluidSynth, SoX, ffmpeg, or
soundfonts; those aren't installable in this environment).

When the user wants to make game music, use the **`/soundtrack` skill** — it
encodes the compose→render→iterate workflow. **`docs/composition.md`** is the
craft guide (leitmotif transformation, melody, harmony, form — lessons from
Zelda/Castlevania/Undertale and others).

## Commands

```bash
python -m vibetracks validate                   # check every group's specs
python -m vibetracks render <group>/<track>     # render one track to out/<group>/<track>.wav
python -m vibetracks render-all                 # render every track in every group
python -m vibetracks new <track> --group <g>    # scaffold groups/music/<g>/tracks/<track>.json
python -m vibetracks new-group <name>           # scaffold a whole new group
python -m unittest discover -s tests            # run tests
```

`render`, `render-all`, `validate`, and `new` take an optional `--group`; when a
repo has just one group you can omit it. A track is addressed as `<group>/<track>`,
as a bare `<track>` (with `--group`), or as a path to its JSON. `render-all` writes
`out/<group>/manifest.json` per group plus a top-level `out/manifest.json` index.

Render is CPU-bound (pure-Python DSP): roughly real-time-ish — a 25 s track takes
~20 s. For a quick check, render a single short track rather than `render-all`.

## The model

### Group — `groups/music/<name>/`
One self-contained soundtrack: its own bible plus tracks. Groups let a single repo
hold several independent scores — different regions of a game, or different games
entirely — without sharing or overwriting one top-level bible. The repo ships a
demo group (`neon-frontier`); `new-group` scaffolds a fresh one alongside it. Each
group is `groups/music/<name>/soundtrack.json` + `groups/music/<name>/tracks/*.json`.
(For backward compatibility, a `soundtrack.json` at the repo root still works as a
lone `default` group when there's no `groups/music/` directory.)

### Bible — `groups/music/<name>/soundtrack.json`
Global identity inherited by every track in its group.

| Field | Meaning |
|-------|---------|
| `title`, `aesthetic` | Labels (informational). |
| `key` | e.g. `"A minor"`. Used for validation + `scale`/`chord` helpers. |
| `bpm` | Default tempo; tracks may override. |
| `palette` | Map of instrument name → patch overrides (merged onto the defaults in `vibetracks/instruments.py`). |
| `motifs` | Named melodies, each `{"notes": [[pitch, beats, vel?], ...]}`. The cohesion mechanism. |
| `tracks` | Ordered track names that `render-all` builds. |

### Track — `groups/music/<name>/tracks/<track>.json`

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
- **`motif`** — name of a bible motif; supports `slice` (`[start, end]`, quote only
  those notes), `repeat`, and the leitmotif transforms below. Prefer this for melodic
  cues so the theme recurs across tracks.

  Transforms (also work on `notes` parts; applied retrograde→invert→transpose→stretch):
  `transpose` (semitones), `stretch` (×duration: `2.0` augment/slow, `0.5` diminish/
  fast), `invert` (`true`, or a pivot note like `"A4"`), `retrograde` (`true`).
- **`chords`** — `["Am", "F", "C", "G"]`; each chord held `chord_beats` (default =
  one bar), tiled to fill the section. Qualities: `m, maj, dim, aug, sus2, sus4, 7,
  maj7, m7, add9, 5`, default major. `octave` sets the chord root octave.
- **`drums`** — `{"kick": "x...x...", "snare": "....x...", "hat": "x.x.x.x.", ...}`.
  Each string is one bar; `x`/`X` = hit, `o` = open hi-hat (on the `hat` voice),
  `.`/`-` = rest. Patterns tile across the section's bars.

Optional per-part knobs: `gain` (level), `pan` (−1 left … 1 right).

## Instrument engines & expression (palette patches)

A patch's `engine` chooses how a pitch becomes sound — this is the lever for
going beyond bare-oscillator chiptune (full param list in `instruments.py`):

- **`subtractive`** (default) — detuned `wave` oscillators → ADSR → filter. The
  classic synthwave voice. Add `resonance` (filter Q) for an analog squelch.
- **`fm`** — two-operator FM. `ratio` (modulator:carrier) + `index` (brightness);
  integer ratios sound harmonic (Rhodes-like electric piano at `1.0`), inharmonic
  ratios give bells/metallic tones. `mod_decay` fades the modulator for a struck attack.
- **`karplus`** — Karplus-Strong plucked string (guitar/harp/koto) from a noise
  burst through a tuned lossy comb. `decay` near `1.0` sustains longer.
- **`soundfont`** — *real recorded instruments* (piano, strings, brass, woodwinds,
  harp, mallets…) via FluidSynth + a General MIDI soundfont. `program` is the GM
  patch number (0–127), optional `bank`; `soundfont` overrides the `.sf2` path.
  This engine is **optional and sample-based**, not numpy — see below.

### The `soundfont` engine (sample-based realism)

The numpy engines synthesize every timbre from math; `soundfont` instead plays
back real multisamples for genuine acoustic instruments. It needs FluidSynth and
a GM `.sf2`, which the core synth path does not:

```bash
scripts/setup-soundfont.sh          # apt: fluidsynth + FluidR3_GM.sf2 + pyfluidsynth
# or: pip install vibetracks[soundfont]  (still needs the FluidSynth system lib)
```

The soundfont is resolved from a patch's `soundfont` field, then
`$VIBETRACKS_SOUNDFONT`, then `/usr/share/sounds/sf2/FluidR3_GM.sf2`. The engine
is imported lazily — `validate` works without FluidSynth; only *rendering* a
soundfont part needs it (and raises a clear `SoundfontError` with install hints
if missing). A soundfont part is rendered whole (notes streamed through one
cached FluidSynth instance), downmixed to mono, and flows through the same
pan/effects/master-normalize pipeline as synth parts — so the two engine families
mix freely in one track. The `amber-court` group is a worked orchestral demo
(`vibetracks/soundfont.py`).

Per-note expression (numpy engines only): `vibrato`/`tremolo` `{rate, depth,
shape, delay}` (pitch / amplitude LFOs; vibrato `delay` eases the wobble in
mid-note). Buffer effects (every engine, including `soundfont`): `delay`,
`chorus` `{rate, depth, mix}` for width, and `reverb` as either a scalar (cheap
Schroeder) or `{decay, mix, predelay}` for the denser convolution reverb. The
`verdant-vale` group is a worked demo of the numpy engines and their expression.

## How compilation works (where to edit)

- `vibetracks/theory.py` — note↔frequency, scales, chord parsing, transpose.
- `vibetracks/synth.py` — oscillators, ADSR, drum synths, filters/delay/reverb,
  normalize. Add new waveforms or effects here.
- `vibetracks/instruments.py` — `DEFAULT_PALETTE` patches + the per-note renderer
  and engine dispatch (`NOTE_ENGINES`/`PART_ENGINES`).
- `vibetracks/soundfont.py` — the optional `soundfont` engine: FluidSynth setup,
  soundfont discovery, and the part-level scheduled renderer.
- `vibetracks/sequencer.py` — schedules parts on a beat grid, mixes, pans, loops,
  master-normalizes. Add new part *kinds* here (and validation in `spec.py`).
- `vibetracks/spec.py` — load/validate the bible and tracks; `extends` inheritance;
  `Group`/`discover_groups`/`find_group` for the `groups/music/` layout.
- `vibetracks/wavio.py` — float buffer → 16-bit PCM WAV (stdlib `wave`).

## Conventions

- Keep tracks coherent: `extends` the bible, reuse motifs, keep keys/tempos related.
- **State the full theme in one place** (usually the title). Elsewhere, vary how
  prominent it is — `slice` a fragment, move it off the lead, or drop it entirely
  and let the shared key/palette plus a secondary motif (e.g. `danger`) carry
  continuity. Restating the whole hook in every track makes them sound identical.
- The master stage normalizes every track to the same peak (≈0.89), so don't fight
  loudness with per-part `gain` — use `gain` only for *balance within* a track.
- WAV is the only output format (no MIDI/OGG yet). 44.1 kHz, 16-bit, stereo.
- Rendered `out/<group>/*.wav` are build artifacts (gitignored); commit the JSON specs.
- One group = one coherent score. Don't reach across groups for motifs/palette; to
  start a new game or region, `new-group` rather than overwriting an existing bible.
