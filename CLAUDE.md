# VibeTracks — guide for Claude

This repo is a **game-soundtrack lab**: songs are modeled as JSON specs and
compiled to WAV by a pure-Python synth (`numpy` + `scipy` only — no FluidSynth,
SoX, ffmpeg, or soundfonts; those aren't installable in this environment).

When the user wants to make game music, use the **`/soundtrack` skill** — it
encodes the compose→render→iterate workflow. This file is the **spec reference**;
**`docs/composition.md`** is the craft guide (leitmotif transformation, melody,
harmony, form — lessons from Zelda/Castlevania/Undertale and others).

## Commands

```bash
python -m vibetracks validate                   # check every group's specs
python -m vibetracks render <group>/<track>     # render one track to out/<group>/<track>.wav
python -m vibetracks render-all                 # render every track in every group
python -m vibetracks new <track> --group <g>    # scaffold groups/<g>/tracks/<track>.json
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

### Group — `groups/<name>/`
One self-contained soundtrack: its own bible plus tracks. Groups let a single repo
hold several independent scores — different regions of a game, or different games
entirely — without sharing or overwriting one top-level bible. The repo ships four
demo groups, each showcasing a distinct feature set (see the README's demo table);
`new-group` scaffolds a fresh one alongside them. Each
group is `groups/<name>/soundtrack.json` + `groups/<name>/tracks/*.json`. (For
backward compatibility, a `soundtrack.json` at the repo root still works as a lone
`default` group when there's no `groups/` directory.)

### Bible — `groups/<name>/soundtrack.json`
Global identity inherited by every track in its group.

| Field | Meaning |
|-------|---------|
| `title`, `aesthetic` | Labels (informational). |
| `key` | e.g. `"A minor"`. Used for validation + `scale`/`chord` helpers. |
| `bpm` | Default tempo; tracks may override. |
| `palette` | Map of instrument name → patch overrides (merged onto the defaults in `vibetracks/instruments.py`). |
| `motifs` | Named melodies, each `{"notes": [[pitch, beats, vel?], ...]}`. The cohesion mechanism. |
| `tracks` | Ordered track names that `render-all` builds. |

### Track — `groups/<name>/tracks/<track>.json`

| Field | Meaning |
|-------|---------|
| `name` | Output filename stem. |
| `extends` | Path to the bible, e.g. `"../soundtrack.json"`. |
| `key`, `bpm`, `time_signature` | Optional overrides (`time_signature` default `[4,4]`). |
| `swing` | Shuffle amount in `[0, 1)` (0 = straight, ~`1/3` = triplet feel); section-overridable. |
| `palette` | Optional per-track patch overrides. |
| `loops` | Default repeat count for `"loop": true` sections (CLI `--loops` overrides). |
| `sections` | List of `{name, bars, loop?, repeat?, parts}`. |

Section assembly: non-loop sections play `repeat` times (default 1); a section with
`"loop": true` repeats `loops` times (default 2). Sections are concatenated in order,
so the usual shape is `intro` (once) + `loop` (×N).

Per-section overrides (all optional): `bpm` overrides the track tempo for that
section; `bpm_end` ramps tempo linearly from `bpm` to `bpm_end` across the section
(accelerando/ritardando — drive into a climax or relax out of one). `transpose`
(semitones) shifts every pitched part in the section — the one-line "kick the final
chorus up a step" modulation, without editing each part. `swing` overrides the
track shuffle for that section (e.g. a straight intro into a shuffled groove). The
`aurelia` group is a worked demo of these long-form tools: a single theme grown
across seven sections with tempo ramps, per-section transpose, arpeggios, and
tuplets. The `midnight-drive` group demos the two *motion* tools — `swing` for a
shuffled pocket and per-part `automation` envelopes for filter sweeps, swells, and
auto-pan.

### Parts
Each section's `parts` is a map of part-name → part. Every part needs an
`instrument` (a palette name) and is **exactly one** of:

- **`notes`** — `[[pitch, beats, velocity?], ...]`. `pitch` is a note name
  (`"C#4"`, `"Bb2"`); use `null` for a rest. `beats` are quarter notes — a number,
  or a fraction string like `"1/3"`/`"3/2"` for exact tuplets (a triplet is three
  `"1/3"` notes). Supports `transpose` (semitones) and `repeat` (tile the figure).
- **`motif`** — name of a bible motif; supports `slice` (`[start, end]`, quote only
  those notes), `repeat`, and the leitmotif transforms below. Prefer this for melodic
  cues so the theme recurs across tracks.

  Transforms (also work on `notes` parts; applied retrograde→invert→transpose→stretch):
  `transpose` (semitones), `stretch` (×duration: `2.0` augment/slow, `0.5` diminish/
  fast), `invert` (`true`, or a pivot note like `"A4"`), `retrograde` (`true`).
- **`chords`** — `["Am", "F", "C", "G"]`; each chord held `chord_beats` (default =
  one bar), tiled to fill the section. Qualities: `m, maj, dim, aug, sus2, sus4, 7,
  maj7, m7, add9, 5`, default major. `octave` sets the chord root octave.
- **`arp`** — same chord list as `chords`, but **broken into a running arpeggio**
  instead of held blocks — the continuous shimmer under a big melody (think Hopes
  and Dreams). Each chord owns `chord_beats` (default = one bar) and is struck one
  note at a time every `rate` beats (default `0.25` = sixteenths; fractions like
  `"1/3"` allowed). `pattern` picks the traversal — `"up"` (default), `"down"`,
  `"updown"`, `"downup"`, or an explicit index list like `[0, 2, 1, 2]`. `octaves`
  (default 1) stacks the chord across that many octaves for a wider sweep; `octave`
  sets the root. Renders through the melody path, so it works with every engine
  (including `soundfont`) and obeys section `transpose`.
- **`drums`** — `{"kick": "x...x...", "snare": "....x...", "hat": "x.x.x.x.", ...}`.
  Each string is one bar; `x`/`X` = hit, `o` = open hi-hat (on the `hat` voice),
  `.`/`-` = rest. Patterns tile across the section's bars.

Optional per-part knobs: `gain` (level), `pan` (−1 left … 1 right), `automation`
(envelopes that move a parameter *over the section*), and `sidechain` (kick-
triggered ducking) — both detailed below.

### `automation` — parameter movement over time
The one lever for *continuous shape*, not just static levels — a filter that
opens, a pad that swells, an arp that drifts across the field. A per-part
`automation` maps a target to an envelope; targets are `filter`, `gain`, `pan`:

```json
"automation": {
  "filter": {"from": 500, "to": 6000, "shape": "exp"},
  "gain":   {"from": 0.3, "to": 1.0},
  "pan":    {"lfo": {"rate": 0.25, "depth": 0.8, "center": 0.0}}
}
```

Each envelope is one of two forms:
- **ramp** `{"from", "to", "shape": "linear"|"exp"}` — interpolate across the
  section. `exp` sweeps musically over wide ranges (use it for filter cutoff Hz).
- **lfo** `{"lfo": {"rate" (Hz), "depth", "center", "shape"}}` — a cyclic move
  around `center` with amplitude `depth` (auto-pan, wah, gain wobble).

`gain` (rides on top of the part's balance level) and `pan` (absolute position)
automate exactly, per sample, for **every engine including `soundfont`**.
`filter` automation is **numpy engines only** and sampled per note-onset (a
stepped sweep — ideal for leads/arps/plucks; a single long pad note gets one
value). It applies to melodic parts (`notes`/`motif`/`arp`).

### `sidechain` — the kick-triggered pump
`"sidechain": {"amount": 0.7, "release": 0.18, "source": "kick"}` ducks the part's
level on every hit of a drum `source` voice (default `"kick"`, from a `drums` part
in the same section), then breathes it back up over `release` seconds — the
classic synthwave/EDM pump. `amount` in `(0, 1]` is the depth (`0.7` = drops to
30% on the beat). Applies at the mix stage, so it works for **every engine** and
stacks with `gain` automation. Reach for it on sustained parts (bass, pads) to
carve space for the kick.

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
mix freely in one track. The `sunspire` group is a worked orchestral demo of this
engine — a full mythic-heroic score built almost entirely from soundfont
instruments (`vibetracks/soundfont.py`).

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
  `Group`/`discover_groups`/`find_group` for the `groups/` layout.
- `vibetracks/wavio.py` — float buffer → 16-bit PCM WAV (stdlib `wave`).

## Conventions

- Keep tracks coherent: `extends` the bible, reuse motifs, keep keys/tempos related.
- **State the full theme in one place** (usually the title). Elsewhere, vary how
  prominent it is — `slice` a fragment, move it off the lead, or drop it entirely
  and let the shared key/palette plus a secondary motif (e.g. `danger`) carry
  continuity. Restating the whole hook in every track makes them sound identical.
- The master stage normalizes every track to the same peak (≈0.89), so don't fight
  loudness with per-part `gain` — use `gain` only for *balance within* a track.
- Default output is 44.1 kHz, 16-bit, stereo **WAV** (stdlib, no deps). For game
  delivery, `render`/`render-all` take `--format ogg|mp3|flac` (or `render -o
  name.ogg` — the extension picks the format). **OGG Vorbis** is the game default
  (small, royalty-free, seamless-loop friendly); MP3/FLAC are also supported.
  Compressed export needs the optional `vibetracks[export]` extra (`soundfile` for
  OGG/FLAC, `lameenc` for MP3), imported lazily like the soundfont engine — see
  `vibetracks/audioexport.py`. No MIDI yet.
- Rendered `out/<group>/*.wav` are build artifacts (gitignored); commit the JSON specs.
- One group = one coherent score. Don't reach across groups for motifs/palette; to
  start a new game or region, `new-group` rather than overwriting an existing bible.
