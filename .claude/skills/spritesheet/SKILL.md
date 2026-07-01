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

Note: PixelTracks is early, exploratory work — the raster engine is still
limited, so sprites come out rough. Set expectations accordingly.

You can **see your output**: render a sprite, then read the PNG (it displays
inline) and iterate, exactly as the music skill sends a WAV to the user.

## 0. Pick (or create) the group

A new game or character set is a **new group** — never overwrite the demo
(`tiny-knight`). `python -m pixeltracks new-group <name> --title "<Title>"`
scaffolds `groups/sprites/<name>/` with a starter bible + a `main` sprite. If extending an
existing set, work inside its group.

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

## 3. Draft → render → view → iterate (per sprite)

1. Hand-write `groups/sprites/<g>/sprites/<name>.json` (or `python -m pixeltracks new
   <name> --group <g>`). A sprite `extends` the bible and is built from `layers`
   (composited in z-order). A layer is exactly one of: `pixels` (+`legend`),
   `shape` (a bible motif, +`flip`/`rotate`/`scale`/`recolor`), `rect`,
   `ellipse`, or `line`. Optional `offset` per layer.
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
5. **Read the PNG** to judge *colour/shading/read* (what text can't tell you),
   and/or send it to the user with SendUserFile. Translate feedback into spec
   edits: "muddy" → widen the shadow/highlight spread; "unreadable" → simplify
   the silhouette; "doesn't fit" → pull colours back to the palette or reuse a
   shared motif.

## 4. Derive variants from the hero (coherence ≠ repetition)

Make new sprites feel like the same set without repeating the hero everywhere:
- **Palette swap** — copy the layers, override only the `palette`. The headline
  leitmotif move: a provably-identical sprite in night/faction/status colours.
- **Transform the shape** — `flip` (face the other way), `rotate`, `scale`
  (enlarge), `recolor` (remap names for one placement). Same DNA, new pose.
- **Reuse an emblem** elsewhere (crest on the chest, then enlarged on a banner).
- **Companions** (enemies/items) share only the palette + outline and carry their
  own shape — they belong without echoing the hero.

How the demo does it: `knight` states the pose + crest; `knight-dusk` is a pure
palette swap; `banner` reuses the crest; `slime` shares only the palette;
`knight-attack` re-poses the knight across 4 frames.

## 5. Animate by re-posing (optional)

For motion, give the sprite `frames` (a list); each frame has its own `layers`.
Re-pose the shared shape with per-frame `offset`/`flip` (windup → strike →
recover), `hold` the impact frame, and add a `flash`/`slash` motif on the action
frame only. It compiles to a horizontal sheet + `<name>.atlas.json` (frame rects
+ holds). See `docs/pixelcraft.md` §6.

## 6. Master pass

`python -m pixeltracks render-all --group <g>` renders every sprite and writes
`out/<g>/manifest.json` (per-sprite size/frames/coverage); plain `render-all`
does every group plus a top-level index. Check the manifest for sane coverage
(a `coverage` of 0 means an empty sprite). Commit specs when the user is happy.

## Cohesion checklist

- [ ] Every sprite `extends` its group's `artbook.json`.
- [ ] Every colour is a palette **name**; the palette is small and role-named.
- [ ] The hero shape is a bible motif, stated once and reused by reference.
- [ ] At least one variant is a pure palette swap; at least one companion shares
      only the palette.
- [ ] `validate` passes and `render-all` produces a clean manifest.
