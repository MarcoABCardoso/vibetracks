# VibeTracks 🎮🎶

A **game-soundtrack lab** for Claude Code. Model a song as plain JSON, then
compile it into real audio with a **pure-Python synthesizer** — `numpy` + `scipy`,
no SoX and no ffmpeg, nothing but `pip install -r requirements.txt` to render
four of the five demo scores. Two capabilities are **optional add-ons**: a
`soundfont` engine (FluidSynth + a General MIDI soundfont) for real *recorded*
instruments, and compressed `ogg`/`mp3`/`flac` export for game delivery.

The point: Claude is great at editing structured text, so a song is described as
a **spec** (diffable, reviewable, version-controlled), and a small compiler turns
that spec into sound. A whole soundtrack stays coherent because every track shares
one **bible** — the same key, tempo family, instrument palette, and recurring
musical motifs.

Tracks are organized into **groups**. A group is one self-contained soundtrack —
its own bible plus tracks — so a single repo can hold several independent scores:
different regions of a game, or entirely different games. The repo ships five demo
groups, each chosen to showcase a **distinct slice of the toolkit** (see below);
spin up your own with `new-group` without touching them.

## Quickstart

```bash
pip install -r requirements.txt                # numpy + scipy: enough for 3 of the 4 demos
scripts/setup-soundfont.sh                     # optional: FluidSynth + GM soundfont (for the sunspire demo)
pip install 'vibetracks[export]'               # optional: ogg / mp3 / flac export

python -m vibetracks validate                  # check every group's specs
python -m vibetracks render-all                # render all groups -> out/<group>/*.wav
python -m vibetracks render-all --format ogg   # ... as game-ready OGG instead
python -m vibetracks render neon-frontier/battle  # render one track -> out/neon-frontier/battle.wav
python -m vibetracks new menu --group neon-frontier  # scaffold a track in a group
python -m vibetracks new-group spooky-cave     # start a fresh, independent soundtrack
```

A track is addressed as `<group>/<track>`, or as a bare `<track>` with `--group`
(or when the repo has just one group).

## The demo soundtracks

Five groups ship with the repo. Each is a coherent little score in its own right,
but each was also built to **demonstrate one axis of the toolkit** — so reading them
side by side is a tour of what VibeTracks can do. Start with `neon-frontier`.

| Group | Feature focus | What it shows |
|-------|---------------|---------------|
| **`neon-frontier`** | Core workflow · subtractive synth · leitmotif score | Five synthwave cues (title / exploration / battle / boss / victory) over one bible. The full `main_theme` is stated in **one** track, then `slice`d, `invert`ed, `retrograde`d, and transposed across the rest — a family of cues, not one song on repeat. |
| **`verdant-vale`** | numpy engines + per-note expression | Goes beyond bare chiptune: `fm`, `karplus` (plucked string), and `subtractive` voices dressed with `vibrato`, `chorus`, `delay`, and `reverb`. The reference for the synthesis and effects params. |
| **`sunspire`** | `soundfont` engine (sample-based orchestral) | A nine-cue mythic-heroic score built almost entirely from **real recorded instruments** (strings, brass, woodwinds, choir, percussion) via FluidSynth. Needs the optional soundfont setup to render — see below. |
| **`aurelia`** | Long-form development + advanced sequencing | One theme grown from a lonely music-box to a full finale across seven sections — `arp` arpeggios, per-section tempo ramps (`bpm_end`), section `transpose`, and tuplet durations. |
| **`midnight-drive`** | Groove + motion (`swing` · `automation` · `sidechain`) | A nocturnal synthwave cruise built to move: a shuffled pocket (`swing`), per-part `automation` envelopes that open a filter, swell a pad, and drift an arp across the stereo field, and `sidechain` ducking that pumps the bass and keys to the kick — the tools for shaping sound *over time*. |

### `neon-frontier`, up close

The flagship. Cohesion comes from a shared key, palette, and motifs — but because
the full hook lands in only one track, the set feels like a coherent family of cues:

| Track | Feel | Theme treatment |
|-------|------|------------------|
| `title-theme` | Anthemic | Full hook over Am–F–C–G (the anchor) |
| `exploration` | Calm, spacious | Only the first 3 notes, as a sparse callback |
| `battle` | Fast, driving | Original riff; the shared `danger` motif carries continuity |
| `boss` | Dark, intense | Just the 4-note head, dropped an octave; `danger` leads |
| `victory` | Bright fanfare | Quotes the opening phrase, then an original flourish home |

> **Rendering `sunspire`** uses the `soundfont` engine, which needs FluidSynth and a
> GM soundfont (`scripts/setup-soundfont.sh`). The other three groups render with
> only `numpy` + `scipy`. `validate` works for every group without FluidSynth.

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
- `arp`: the same chord list broken into a running arpeggio — a `rate`/`pattern`/`octaves`-driven shimmer instead of held blocks
- `drums`: per-voice step patterns, e.g. `{"kick": "x...x...", "hat": "x.x.x.x."}`

See **`CLAUDE.md`** for the complete spec reference, **`docs/composition.md`** for
the craft of writing a coherent score (leitmotif transformation, melody, harmony,
form — lessons from Zelda/Castlevania/Undertale and others), and the `/soundtrack`
skill for the compose→render→iterate workflow.

## How it compiles to sound

`spec → sequencer → synth → audio`. Each palette patch picks an **engine** for
turning a pitch into sound: `subtractive` (oscillators + ADSR + filter — the
synthwave default), `fm` (two-operator FM for bells and electric pianos),
`karplus` (plucked strings), or the optional `soundfont` (real multisamples via
FluidSynth). Parts are mixed and panned to stereo, dressed with per-note
expression (vibrato/tremolo) and buffer effects (delay/chorus/reverb, IIR via
`scipy.signal.lfilter`), then normalized to a consistent peak so every track
matches in loudness. Output is 16-bit stereo **WAV** by default; `--format
ogg|mp3|flac` exports compressed audio for game delivery (OGG, seamless-loop
friendly, is the game default).

## Project layout

```
groups/<name>/soundtrack.json   # a group's bible
groups/<name>/tracks/*.json      # one spec per track in that group
vibetracks/                      # the compiler (theory, synth, instruments, sequencer,
                                 #   soundfont, audioexport, wavio, CLI)
tests/                           # theory, validation, engines, export, soundfont, render sanity
.claude/skills/soundtrack        # the authoring workflow skill
out/<group>/                     # rendered WAVs (gitignored) + per-group manifest.json
```

## Tests

```bash
python -m unittest discover -s tests
```
