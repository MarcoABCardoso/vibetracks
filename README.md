# VibeTracks 🎮🎶🖼️

A **multi-Lab game-artifact workshop** for Claude Code. The premise: Claude is
great at editing structured text, so a game asset is described as a **spec**
(diffable, reviewable, version-controlled), and a small deterministic compiler
turns that spec into the real artifact — **no black-box generator at the wheel.**
A whole set of assets stays coherent because everything shares one **bible**.

A **Lab** is one such workshop for one artifact class. Every Lab is the same
machine — *bible → specs → reusable motifs → validator → deterministic engine →
artifact* — with a different theory. This repo ships two:

| Lab | Artifact | Author edits | Compiles to | Engine |
|-----|----------|--------------|-------------|--------|
| **VibeTracks** | music / SFX | JSON song specs | `.wav` | pure-Python synth (`numpy`+`scipy`) |
| **PixelTracks** | sprites / images | JSON sprite specs | `.png` | procedural raster (`numpy`+stdlib) |

See **`VISION.md`** for the thesis and the roadmap of further Labs (tiles, UI,
lore, systems) bound by a shared World Bible.

## Quickstart

```bash
pip install -r requirements.txt

python -m labs                               # list the Labs
python -m labs validate                      # validate every Lab's specs

# the music Lab
python -m vibetracks render-all              # -> out/<group>/*.wav
python -m vibetracks render neon-frontier/battle

# the sprite Lab
python -m pixeltracks render-all             # -> out/<group>/*.png
python -m pixeltracks render mossy-hollow/fox
```

Each Lab has the same CLI verbs (`validate` / `render` / `render-all` / `new` /
`new-group`) and the same addressing (`<group>/<asset>`, a bare `<asset>` with
`--group`, or a path). Run a Lab directly (`python -m vibetracks …`) or through
the dispatcher (`python -m labs vibetracks …`).

## How the repo is laid out

```
labkit/           # shared core: SpecError/load_json, group discovery, the Lab registry
labs/             # the multi-Lab dispatcher (python -m labs)
CLAUDE.md         # index; per-Lab spec reference in vibetracks/ & pixeltracks/CLAUDE.md

vibetracks/       # the music Lab (theory, synth, instruments, sequencer, wavio, CLI)
groups/music/<g>/soundtrack.json + tracks/*.json     # music groups (demo: neon-frontier)

pixeltracks/      # the sprite Lab (palette, shapes, raster, compositor, pngio, CLI)
groups/sprites/<g>/artbook.json + sprites/*.json     # sprite groups (demo: mossy-hollow)

docs/composition.md   # music craft guide      docs/pixelcraft.md   # sprite craft guide
.claude/skills/soundtrack                       .claude/skills/spritesheet
tests/                                          out/<group>/   # build artifacts (gitignored)
```

All assets live under one **`groups/`** tree, split by medium: `groups/music/`
for VibeTracks and `groups/sprites/` for PixelTracks.

Adding a Lab is a new package mirroring this layout plus one `Lab(...)` entry in
`labkit/registry.py` — that's the structural claim of the vision.

---

## 🎶 VibeTracks — the music Lab

A coherent soundtrack stays coherent because every track shares one bible: the
same key, tempo family, instrument palette, and recurring musical **motifs**.
Tracks live in **groups** (`groups/music/<name>/`) — independent scores in one repo.

### The included demo: *Neon Frontier*

A five-cue synthwave score in A minor. The full `main_theme` is stated in only
**one** track, so the set feels like a family of cues rather than one song on
repeat:

| Track | Feel | Theme treatment |
|-------|------|------------------|
| `title-theme` | Anthemic | Full hook over Am–F–C–G (the anchor) |
| `exploration` | Calm, spacious | Only the first 3 notes, as a sparse callback |
| `battle` | Fast, driving | Original riff; the shared `danger` motif carries continuity |
| `boss` | Dark, intense | Just the 4-note head, dropped an octave; `danger` leads |
| `victory` | Bright fanfare | Quotes the opening phrase, then an original flourish home |

A **part** is exactly one of `notes` (explicit events), `motif` (a bible motif
with leitmotif transforms — `slice`/`transpose`/`stretch`/`invert`/`retrograde`),
`chords`, or `drums`. It compiles `spec → sequencer → synth → WAV`. See
`docs/composition.md` for the craft and the `/soundtrack` skill for the workflow.

---

## 🖼️ PixelTracks — the sprite Lab

> 🖼️ **A deterministic pixel-art engine.** Built on the same `labkit` core as
> VibeTracks, PixelTracks renders coherent sprite sets from JSON — palette swaps,
> skeleton-rigged poses, animation, scenes, higher-detail portraits — with **no
> image model**. It targets pixel art and flat/stylised work rather than photoreal
> illustration, and within that lane it delivers.

The visual sibling, built on the same `labkit` core and mirroring VibeTracks
module-for-module. A sprite set stays coherent because every sprite shares one
**artbook**: a colour `palette` and reusable shape **motifs**. The leitmotif move
is a **palette swap** — change the bible's colours and a sprite recolours in step.

### The included demo: *Mossy Hollow*

A five-sprite 20×20 set of woodland critters on a warm autumn palette —
deliberately not a re-skin of an armoured hero, to show that swapping the
artbook reshapes the whole world, not just the colours:

| Sprite | What it shows |
|--------|---------------|
| `fox` | The anchor: states the hero shape in full and wears the `leaf` charm |
| `fox-night` | **Palette swap** — identical layers, moonlit colours (the headline move) |
| `signpost` | The `leaf` motif recurring elsewhere, plus `rect`/`line` primitives |
| `owl` | Coherence ≠ repetition — shares only the palette, carries its own shape |
| `fox-hop` | A 4-frame animation re-posing the fox → sprite sheet + `.atlas.json` |

A second, bigger group (`emberhold`) shows the same mechanics scaled up to a
4-class JRPG party with battle poses and skeleton-rigged attacks.

A **layer** is exactly one of `pixels` (a char grid + legend), `shape` (a motif
with transforms — `flip`/`rotate`/`scale`/`recolor`), `rect`, `ellipse`, or
`line`. It compiles `spec → compositor → raster → PNG`, with an auto-outline pass
and an integer export upscale. PNG is written with stdlib `zlib` — no Pillow, no
image generator. See `docs/pixelcraft.md` for the craft and the `/spritesheet`
skill for the workflow.

## Tests

```bash
python -m unittest discover -s tests
```
