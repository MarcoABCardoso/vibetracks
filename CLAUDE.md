# VibeTracks — guide for Claude

This repo is a **multi-Lab game-artifact workshop**. A *Lab* is a structured
spec → validate → compile → iterate workshop for one artifact class. Every Lab is
the same machine with a different theory (see `VISION.md`):

| Lab | Artifact | Author edits | Compiles to | Skill |
|-----|----------|--------------|-------------|-------|
| **VibeTracks** | music / SFX | JSON song specs | WAV (pure-Python synth) | `/soundtrack` |
| **PixelTracks** | sprites / images | JSON sprite specs | PNG (procedural raster) | `/spritesheet` |

Shared core in **`labkit/`** (error type, group discovery, the Lab registry);
each Lab is its own package (`vibetracks/`, `pixeltracks/`) with the *same* CLI
verbs. A dispatcher unifies them:

```bash
python -m labs                       # list the Labs
python -m labs <lab> <command...>    # run a Lab's CLI (e.g. labs pixeltracks render-all)
python -m labs validate              # validate every Lab's specs
python -m <lab> <command...>         # or run a Lab directly
```

**Pick the right Lab for the request:** game *music* → VibeTracks (`/soundtrack`);
game *sprites / pixel art / images* → PixelTracks (`/spritesheet`). The rest of
this file is the **spec reference** for both — VibeTracks first, then PixelTracks
(see "PixelTracks — the sprite Lab" near the end).

---

## VibeTracks — the music Lab

Songs are modeled as JSON specs and compiled to WAV by a pure-Python synth
(`numpy` + `scipy` only — no FluidSynth, SoX, ffmpeg, or soundfonts; those aren't
installable in this environment).

When the user wants to make game music, use the **`/soundtrack` skill** — it
encodes the compose→render→iterate workflow. **`docs/composition.md`** is the
craft guide (leitmotif transformation, melody, harmony, form — lessons from
Zelda/Castlevania/Undertale and others).

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
entirely — without sharing or overwriting one top-level bible. The repo ships a
demo group (`neon-frontier`); `new-group` scaffolds a fresh one alongside it. Each
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
- WAV is the only output format (no MIDI/OGG yet). 44.1 kHz, 16-bit, stereo.
- Rendered `out/<group>/*.wav` are build artifacts (gitignored); commit the JSON specs.
- One group = one coherent score. Don't reach across groups for motifs/palette; to
  start a new game or region, `new-group` rather than overwriting an existing bible.

---

# PixelTracks — the sprite Lab

The visual sibling of VibeTracks, built on the same `labkit` core and mirroring
its module layout. Sprites are modeled as JSON and compiled to **PNG** by a
procedural raster engine (`numpy` + stdlib `zlib` for PNG — **no image
generator**, no Pillow). When the user wants game sprites/pixel art, use the
**`/spritesheet` skill**; **`docs/pixelcraft.md`** is the craft guide (palette,
silhouette, shape motifs, the palette-swap leitmotif, animation).

## Commands

```bash
python -m pixeltracks validate                  # check every group's specs
python -m pixeltracks render <group>/<sprite>   # render one sprite to out/<group>/<sprite>.png
python -m pixeltracks render-all                # render every sprite in every group
python -m pixeltracks new <sprite> --group <g>  # scaffold art/<g>/sprites/<sprite>.json
python -m pixeltracks new-group <name>          # scaffold a whole new group
```

Same addressing as VibeTracks: `<group>/<sprite>`, a bare `<sprite>` (with
`--group`), or a path to its JSON. `render-all` writes `out/<group>/manifest.json`
plus a top-level index; an animated sprite also gets a `<sprite>.atlas.json`.

## The model (mirror of the music model)

### Group — `art/<name>/`
One self-contained sprite set: its own bible (`art/<name>/artbook.json`) plus
`art/<name>/sprites/*.json`. The repo ships a demo group (`tiny-knight`).

### Bible — `art/<name>/artbook.json`

| Field | Meaning |
|-------|---------|
| `title`, `aesthetic` | Labels (informational). |
| `size` | Default canvas `[width, height]` in pixels (e.g. `[16, 16]`). |
| `scale` | Integer export upscale (nearest-neighbour); `16` → a 256px PNG. |
| `palette` | Map of **role name → `#hex`**. The coherence anchor; sprites reference names, never raw hex. `#rgb`/`#rrggbb`/`#rrggbbaa` and `"transparent"` accepted. |
| `ramps` | Optional named shadow→highlight lists of palette names (documentation/shading). |
| `background` | Palette name to fill the canvas, or `null` for transparent. |
| `outline` | `{"color": <name>}` to auto-trace a 1px silhouette outline, or `null`. |
| `motifs` | Named reusable shapes, each `{"legend": {char: colorName}, "pixels": [rows]}`. The cohesion mechanism (= music's `motifs`). |
| `sprites` | Ordered sprite names that `render-all` builds (= music's `tracks`). |

### Sprite — `art/<name>/sprites/<sprite>.json`

| Field | Meaning |
|-------|---------|
| `name` | Output filename stem. |
| `extends` | Path to the bible, e.g. `"../artbook.json"`. |
| `size`, `scale`, `palette`, `background`, `outline` | Optional overrides. A `palette` override is the **palette-swap leitmotif**. |
| `legend` | Optional sprite-level default `char → colorName` for `pixels` layers. |
| `motifs` | Optional per-sprite extra shapes. |
| `layers` | List of layers composited in z-order (later paints over earlier). |
| `frames` | Optional list of `{name?, hold?, layers}` for animation; absent ⇒ one frame from `layers`. |

### Layers (= music's parts)
Each layer is composited in order and is **exactly one** of:

- **`pixels`** — `[rows]` of legend chars (`.`/space = transparent) + a `legend`
  (or the sprite-level default). The workhorse; ASCII-art-legible in a diff.
- **`shape`** — name of a bible/sprite motif (the coherence mechanism). Supports
  the leitmotif transforms: `flip` (`"h"`/`"v"`/`"hv"`), `rotate` (0/90/180/270),
  `scale` (positive int = augment), `recolor` (`{colorName: colorName}` swap for
  this placement only). Applied flip→rotate→scale.
- **`rect`** / **`ellipse`** — `{"at": [x,y], "size": [w,h], "color": <name>, "fill": bool}`.
- **`line`** — `{"from": [x,y], "to": [x,y], "color": <name>}`.

Optional per-layer `offset` `[dx, dy]` shifts the layer on the canvas.

## How compilation works (where to edit)

- `pixeltracks/palette.py` — hex↔RGBA, named palettes, `shade` (≈ `theory.py`).
- `pixeltracks/shapes.py` — grids + transforms `flip`/`rotate`/`scale`/`recolor`.
- `pixeltracks/raster.py` — canvas, pixel/rect/ellipse/line painters, auto-outline,
  upscale (≈ `synth.py`: the low-level renderers/effects).
- `pixeltracks/compositor.py` — composites a resolved sprite's layers/frames into a
  sheet + atlas (≈ `sequencer.py`). Add new layer *kinds* here.
- `pixeltracks/spec.py` — load/validate bible + sprites; `extends`; `Group`/
  `discover_groups` for the `art/` layout (and validation in `_validate_layer`).
- `pixeltracks/pngio.py` — RGBA array → PNG, stdlib only (≈ `wavio.py`).

## Conventions

- Keep sprites coherent: `extends` the bible, reference colours by **name**,
  reuse shape motifs. The validator rejects off-palette colours like a wrong note.
- **State the hero shape once** (the anchor sprite) and reuse it transformed
  elsewhere; let companions share only the palette. Don't quote the hero in every
  sprite, or the set looks monotonous (= the "don't restate the hook everywhere" rule).
- Author motifs **without** the outer outline — the `outline` effect adds it; carry
  only interior shading so grids stay readable.
- PNG is the only output format. Rendered `out/<group>/*.png` are build artifacts
  (gitignored); commit the JSON specs.
- One group = one coherent set. `new-group` to start a new world rather than
  overwriting an existing bible.

---

## The shared core & adding a Lab

- `labkit/` — `SpecError` + `load_json` (`specbase.py`), generic group discovery
  (`groups.py`), and the `Lab` registry (`registry.py`). Both Labs build on it.
- `labs/__main__.py` — the dispatcher (`python -m labs`).
- To add a Lab: create a package mirroring this layout (model + validator +
  deterministic engine + CLI with the same verbs) and append a `Lab(...)` entry to
  `labkit/registry.py`. See `VISION.md` for the roadmap of future Labs.
