---
name: spritesheet
description: Compose or extend a coherent pixel-art sprite set in this PixelTracks Lab. Use when the user wants to create game sprites/images, add or revise a sprite, design the visual identity (palette/shape motifs), animate a sprite, or render specs to PNG. Drives the model→compile→view→iterate loop.
---

# Composing pixel-art sprites with PixelTracks

PixelTracks is the sprite/image Lab — the visual sibling of the VibeTracks music
Lab. It models a sprite as **JSON** and compiles it to **PNG** with a procedural
raster engine (`numpy` + stdlib, no image generator). Your job is to author/edit
the JSON specs and render them. Sprites live in **groups** — each
`groups/sprites/<name>/` is a self-contained set with its own bible
(`groups/sprites/<name>/artbook.json`) and `sprites/`. A group stays coherent
because every sprite shares its bible: one colour `palette` and reusable shape
**motifs**.

Read `pixeltracks/CLAUDE.md` for the full spec reference, and
**`docs/pixelcraft.md` for the craft** — palette discipline, silhouette, shape
motifs, the palette-swap leitmotif, animation timing, coherence ≠ repetition.
The loop below is the procedure; the craft guide is what makes the output good.

Note: PixelTracks is a capable, deterministic pixel-art engine — it's genuinely
good at pixel art and flat/stylised work (coherent sets, rigged poses, animation,
higher-detail portraits) and doesn't aim at photoreal or painterly illustration.
Author within that lane and it delivers.

You can **see your output**: render a sprite, then read the PNG (it displays
inline) and iterate, exactly as the music skill sends a WAV to the user. And so
should the user — **send the rendered PNG with SendUserFile on every meaningful
revision** (the sprite is the deliverable; they want to look at it, not just hear
it's done).

## 0. Pick (or create) the group

A new game or character set is a **new group** — never overwrite a demo
(`mossy-hollow`, `emberhold`). `python -m pixeltracks new-group <name> --title "<Title>"`
scaffolds `groups/sprites/<name>/` with a starter bible + a `main` sprite. If extending an
existing set, work inside its group.

**Is this part of a bigger world?** If the user wants art *and* music for one
game, or a shared identity across media, start one level up with
`python -m labs new-world <name>` — it scaffolds `worlds/<name>/world.json` plus a
sprite group already wired to `extends` it, so the set inherits the world's
meaning palette and entities. A single-medium sprite set needs no world; a group
can also be *promoted* later by adding an `extends`. See the root `CLAUDE.md`
("When to use a world").

## 1. Establish the bible (do this first, once)

Edit `groups/sprites/<name>/artbook.json`. Interview briefly if needed: game & mood, the
sprite list (hero, enemies, items, an animation), and the visual identity. Then
write:
- `size` — the canvas, e.g. `[16, 16]`. `scale` — export upscale (16 → a 256px PNG).
- `palette` — 8–16 colours, **named by role** (`armor`, `armor_hi`, `cloak`,
  `gold`), each a `#hex`. This is the coherence anchor; keep it tight.
- `outline` — `{ "color": "outline" }` turns on the auto-silhouette outline so you
  don't draw the outer ring by hand.
- `motifs` — reusable grids (see §2). `sprites` — the ordered list to render.

## 2. Draw the hero shape motif before any sprite

The motif is the glue. Author the hero pose as a bible motif: a `legend`
(`char → palette name`) and a `pixels` grid (rows of chars; `.` = transparent).
Draw it **without** the outer black outline — the engine adds that — carrying
only interior shading. ASCII-art it so it reads in a diff. Add small emblem
motifs (a crest) you can reuse on other sprites.

## 2.5 Forms — sculpt characters from shaded solids (the high-leverage path)

For **characters, creatures, and props with volume**, prefer **`form` layers**
over hand-placing pixels. A form is a solid primitive — `sphere`/`disc`/`capsule`/
`box`/`cone` — with a `material` (a bible **ramp**) and the engine derives every
pixel *and its shadow/highlight* from the form's surface normal under the sprite
`light`. You decide *which solid, where, what material*; the engine does the
shading. A whole figure is ~10 forms, not a 400-cell grid. (Keep `pixels` grids
for emblems, UI, faces, and fine detail.) Full reference: `pixeltracks/CLAUDE.md`
"form" layer; craft: `docs/pixelcraft.md` §8. The worked demos are the
`forge-knights` group.

The rules that save exploration (learned the hard way):

- **Material must be a ramp to shade.** Declare `ramps` in the bible
  (`steel: [steel_sh, steel, steel_hi]`); point a form's `material` at the ramp
  name. A bare palette colour fills flat. The light defaults to `up_left`.
- **Separate touching masses.** Same-material forms merge visually; the engine's
  automatic **contact shadow** (Phase 2) helps, but for clarity give adjacent
  parts different materials (iron limbs, gold accents) or rely on the shadow and
  *check* the read in `inspect`, never the PNG.
- **Rig any real pose with a form skeleton — do not hand-place rotated forms.**
  Articulated forms (`rotate`/`skew`/`squash`) do **not** connect by construction;
  hand-placed limbs float, clip, or detach (and the PNG hides it). Use a
  `skeleton` whose **bones are forms**: each bone carries `form`/`size`/`material`
  and its own inline `anchors`, and `attach`es its pivot to a parent bone's anchor
  — so parts meet no matter how the torso leans. `knight-forms-rig` is the model.
- **A raised weapon needs a CONTRASTING material.** A steel blade beside a steel
  helm reads as a *pipe* joining the arm to the head. Make the blade gold (or any
  ramp that isn't the armour's), and aim it into **empty space**, away from the
  head.
- **Derive rotation angles; don't guess.** For a capsule that hangs down at
  `rotate: 0` (pivot at the top), the free end lands at offset
  `(-L·sin θ, L·cos θ)` from the pivot: `θ≈180` points it up, `θ≈270` right,
  `θ≈90` left, `θ≈0` down. When animating, make **all** turning parts (arm *and*
  blade) rotate the **same** direction and make the hand actually **travel**
  through the motion — an arm that only spins while staying put reads as "rotating
  the wrong way."
- **Gate every posed/animated form sprite with `checks`** — at least
  `{ "rule": "connected" }` and `{ "rule": "on_canvas", "margin": 0 }` — and judge
  it with `inspect` (`--all-frames` for animations), **never** by reading the PNG.

## 3. Draft → render → view → iterate (per sprite)

1. Hand-write `groups/sprites/<g>/sprites/<name>.json` (or `python -m pixeltracks new
   <name> --group <g>`). A sprite `extends` the bible and is built from `layers`
   (composited in z-order). A layer is exactly one of: `pixels` (+`legend`),
   `shape` (a bible motif, +`flip`/`rotate`/`scale`/`recolor`), `rect`,
   `ellipse`, `line`, or `sprite` (stamp another sprite — the scene mechanism,
   §7). Optional `offset` per layer.
2. `python -m pixeltracks validate` — catches off-palette colours, ragged grids,
   unknown motifs (the visual analogue of a wrong note).
3. `python -m pixeltracks inspect <g>/<name>` — **evaluate as text before you
   trust the picture.** The ASCII dump, per-layer bounding boxes, and
   connectivity lint catch the structural bugs a glance at the PNG misses
   (floating limbs, disconnected "horseshoe" bodies, clipped weapons, off-centre
   parts). For anything articulated — a pose, a multi-part body, an animation —
   this is where you spend your iterations, not on re-rendering. Add `checks`
   (connected / centred / above / left_of …) to the sprite so the target is
   pass/fail. For rigged poses, prefer a `skeleton` (parts attached at anchors)
   so connection is guaranteed, not tuned. See `pixeltracks/CLAUDE.md`.
4. `python -m pixeltracks render <g>/<name>` — writes `out/<g>/<name>.png`.
5. **Judge structure in `inspect`, not the PNG.** Whether a pose is connected,
   whether a limb floats or clips, whether the sword is beside the helm — these
   are read from the ASCII dump + geometry + `checks`, because an upscaled PNG
   *hides* them (a broken sprite can look fine at a glance — this has bitten us
   more than once). Use the PNG only for what text can't convey — **colour,
   shading, overall read** — and for **delivery**. Iterate on the spec until
   `inspect` is clean *first*, then look at the PNG for feel.
6. **Always send the PNG to the user with SendUserFile** — the sprite is the
   deliverable, so they want to *see* every meaningful revision. Send proactively
   after each render worth showing (a new sprite, a pose change, a before/after);
   don't wait to be asked. A labelled contact sheet is ideal for a set or an
   animation's frames. (For an animated sprite the native output is a horizontal
   **sheet** PNG + `.atlas.json`; a spritesheet is the reliable way to show
   motion.) Translate feedback into spec edits: "muddy" → widen the ramp spread;
   "unreadable" → simplify the silhouette; "reads as a pipe" → contrasting
   material + aim into empty space; "doesn't fit" → pull colours back to the
   palette or reuse a shared motif/ramp.

## 4. Derive variants from the hero (coherence ≠ repetition)

Make new sprites feel like the same set without repeating the hero everywhere:
- **Palette swap** — copy the layers, override only the `palette`. The headline
  leitmotif move: a provably-identical sprite in night/faction/status colours.
- **Transform the shape** — `flip` (face the other way), `rotate`, `scale`
  (enlarge), `recolor` (remap names for one placement). Same DNA, new pose.
- **Reuse an emblem** elsewhere (a charm on the hero, then enlarged on a prop).
- **Companions** (enemies/items) share only the palette + outline and carry their
  own shape — they belong without echoing the hero.

How the `mossy-hollow` demo does it: `fox` states the pose + `leaf` charm;
`fox-night` is a pure palette swap; `signpost` reuses the leaf enlarged; `owl`
shares only the palette; `fox-hop` re-poses the fox across 4 frames.

## 5. Animate by re-posing (optional)

For motion, give the sprite `frames` (a list); each frame has its own `layers`
(or `skeleton`). Re-pose the shared shape per frame (windup → strike → recover),
`hold` the impact frame, add a `flash`/`slash` on the action frame only. It
compiles to a horizontal sheet + `<name>.atlas.json` (frame rects + holds). See
`docs/pixelcraft.md` §6.

For a **form rig**, each frame is its own `skeleton`; only the moving bones'
angles change. Because that repeats the whole rig per frame, define it **once in a
small builder script** and sweep the animated angles — the repo endorses this
(`groups/sprites/forge-knights/build_swing.py` builds `knight-forms-swing`, a
5-frame sword chop). Give the canvas room for the swing extremes, and verify
**every** frame with `inspect --all-frames --strict` before rendering.

## 6. Scenes & large sprites (optional)

Two moves beyond a single small sprite (see the `dusk-glade` demo):

- **Scenes** — compose a picture from *whole sprites*. Give a sprite a big `size`,
  `"scene": true`, `outline: null`, a `background` fill + `rect`/`ellipse`/`line`
  backdrop bands, then place objects with **`sprite` layers** (`{ "sprite":
  "<sibling>", "offset": [x,y], "flip"?, "scale"?, "frame"? }`). Objects are
  reused-transformed, not re-authored — the same rock flipped, the same mushroom
  scaled. `scene: true` relaxes the single-silhouette lint (a scene is meant to be
  many pieces); per-layer bboxes, off-canvas clipping and `checks` still work for
  placement. `dusk-glade/meadow` stamps a 64px oak + toadstools + boulders + ferns
  over a pond backdrop.
- **Large sprites (48/64px+)** — the engine takes any `size`, but don't hand-draw
  a 64-row grid. **Compose from small motifs** with `shape`/skeleton + affine, and
  lower `scale` (6–8). `dusk-glade/great-oak` is a 64² tree = one `trunk` motif +
  one `leaf_cluster` stamped ~6× into a canopy.

## 7. Master pass

`python -m pixeltracks render-all --group <g>` renders every sprite and writes
`out/<g>/manifest.json` (per-sprite size/frames/coverage); plain `render-all`
does every group plus a top-level index. Check the manifest for sane coverage
(a `coverage` of 0 means an empty sprite). Commit specs when the user is happy.

## Cohesion checklist

- [ ] Every sprite `extends` its group's `artbook.json`.
- [ ] Every colour is a palette **name**; the palette is small and role-named.
- [ ] The hero shape is a bible motif (or form set), stated once and reused.
- [ ] At least one variant is a pure palette swap; at least one companion shares
      only the palette.
- [ ] Characters/creatures use **`form` layers** shaded from bible `ramps`; any
      real pose is a **form skeleton** (bones attached at anchors), not
      hand-placed rotated forms.
- [ ] Every posed/animated sprite carries `connected` + `on_canvas` `checks` and
      was judged in **`inspect`** (`--all-frames` for animations) — not by the PNG.
- [ ] `validate` passes and `render-all` produces a clean manifest.
