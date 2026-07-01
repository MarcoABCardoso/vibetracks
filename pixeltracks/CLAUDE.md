# PixelTracks — the sprite Lab (spec reference)

> ⚠️ **Early, exploratory work.** PixelTracks is much younger than VibeTracks and
> its procedural raster engine is still limited — rendered sprites come out rough
> and results may fall well short of the music Lab. Treat it as a proof that the
> `labkit` core generalizes to a second medium, not a finished sprite generator,
> and set the user's expectations accordingly.

The visual sibling of VibeTracks, built on the same `labkit` core and mirroring
its module layout (see the root `CLAUDE.md` for the multi-Lab overview). Sprites
are modeled as JSON and compiled to **PNG** by a procedural raster engine
(`numpy` + stdlib `zlib` for PNG — **no image generator**, no Pillow). When the
user wants game sprites/pixel art, use the **`/spritesheet` skill**;
**`docs/pixelcraft.md`** is the craft guide (palette, silhouette, shape motifs,
the palette-swap leitmotif, animation).

## Commands

```bash
python -m pixeltracks validate                  # check every group's specs
python -m pixeltracks describe [<group>]        # index of a group's motifs/sprites — see below
python -m pixeltracks render <group>/<sprite>   # render one sprite to out/<group>/<sprite>.png
python -m pixeltracks inspect <group>/<sprite>  # evaluate a sprite as TEXT (no PNG) — see below
python -m pixeltracks render-all                # render every sprite in every group
python -m pixeltracks new <sprite> --group <g>  # scaffold groups/sprites/<g>/sprites/<sprite>.json
python -m pixeltracks new-group <name>          # scaffold a whole new group
```

### `describe` — a table of contents for a bulky artbook

A music bible fits in a screenful because a motif is a few notes; a sprite motif
is a pixel grid, so a multi-character `artbook.json` (e.g. `emberhold`, ~750
lines) is mostly ASCII-art rows. `describe` derives an index from data already in
the specs — no new authoring field — so you can scan a group's shape before
grepping pixel grids: per motif, its size, `anchors`, and which sprites reference
it as a `shape` (including bones expanded from a `skeleton`); per sprite, its
size, the motifs it uses, frame/check counts; and an `unused motifs` line (dead
weight to prune). Bare `describe` lists every group; `describe <group>` limits
to one.

### `inspect` — judge a sprite without looking at the PNG

An upscaled PNG is unreliable to evaluate by eye (is the belt on the hips? is the
blade clipped?). `inspect` renders the composited frame back to **text** so those
questions are read as characters and numbers, not pixels. Prefer it over
"render then squint" — it is the fastest way to hit a pose target in few iterations.

- **ASCII dump** — the composite as a grid of palette-role chars (`#`=outline,
  the same alphabet you author in) + a legend. You see exactly what landed.
- **geometry** — each layer's bounding box, plus lint: `FLOATING` layers (touch
  nothing), off-canvas `clipped`, and how many disconnected pieces the silhouette
  is in (real parts vs `<3px` rotation specks). These are the "horseshoe" and
  "stubby clipped sword" bugs, caught before you render.
- **checks** — a sprite's declared `checks` evaluated to PASS/FAIL (see below).

Flags: `--frame N` / `--all-frames`, `--no-ascii|--no-geometry|--no-checks`,
`--strict` (non-zero exit on any warning/fail — good for a pre-commit gate).

Same addressing as VibeTracks: `<group>/<sprite>`, a bare `<sprite>` (with
`--group`), or a path to its JSON. `render-all` writes `out/<group>/manifest.json`
plus a top-level index; an animated sprite also gets a `<sprite>.atlas.json`.

## The model (mirror of the music model)

### Group — `groups/sprites/<name>/`
One self-contained sprite set: its own bible (`groups/sprites/<name>/artbook.json`)
plus `groups/sprites/<name>/sprites/*.json`. The repo ships two demo groups:
`mossy-hollow` (a small five-sprite demo — woodland critters) and `emberhold`
(a bigger 4-class JRPG party). The two share no shape language or even outline
colour — proof that the artbook, not the engine, is what shapes a set's world.
Sprite groups live under `groups/sprites/` alongside the music groups under
`groups/music/` — one `groups/` tree, one subdirectory per medium.

### Bible — `groups/sprites/<name>/artbook.json`

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

### Sprite — `groups/sprites/<name>/sprites/<sprite>.json`

| Field | Meaning |
|-------|---------|
| `name` | Output filename stem. |
| `extends` | Path to the bible, e.g. `"../artbook.json"`. |
| `size`, `scale`, `palette`, `background`, `outline` | Optional overrides. A `palette` override is the **palette-swap leitmotif**. |
| `flip` | Optional `"h"`/`"v"`/`"hv"` — mirror the whole finished composite. Face a sprite the other way (an enemy mirroring the hero) without re-rigging: `dark-knight-battle` is `knight-battle`'s rig + dark palette + `flip:"h"`. |
| `legend` | Optional sprite-level default `char → colorName` for `pixels` layers. |
| `motifs` | Optional per-sprite extra shapes. |
| `layers` | List of layers composited in z-order (later paints over earlier). |
| `skeleton` | Optional list of **bones** — parts attached at named anchors so they connect by construction (see below). Expands into `layers` (drawn beneath any explicit `layers`). |
| `checks` | Optional list of declarative art-direction predicates, run by `inspect` (see below). |
| `frames` | Optional list of `{name?, hold?, layers?/skeleton?}` for animation; absent ⇒ one frame from `layers`/`skeleton`. |

### Layers (= music's parts)
Each layer is composited in order and is **exactly one** of:

- **`pixels`** — `[rows]` of legend chars (`.`/space = transparent) + a `legend`
  (or the sprite-level default). The workhorse; ASCII-art-legible in a diff.
- **`shape`** — name of a bible/sprite motif (the coherence mechanism). Supports
  the leitmotif transforms: `flip` (`"h"`/`"v"`/`"hv"`), `rotate` (any angle in
  degrees; a multiple of 90 without a `pivot` is a lossless grid turn, anything
  else rotates in pixel space about `pivot` pinned to canvas `at`), `scale`
  (positive int = augment), `recolor` (`{colorName: colorName}` swap for this
  placement only). Plus two **affine** transforms for turning/leaning a part in
  space (they route through the `pivot`/`at` path): `skew` `[kx, ky]` shear
  (kx = the sideways "lean" with depth) and `squash` `[sx, sy]` non-uniform
  fractional scale (sx < 1 foreshortens width — a turned torso). Grid transforms
  apply flip→rotate→scale; the articulated matrix is rotate∘shear∘squash about
  the pivot.
- **`rect`** / **`ellipse`** — `{"at": [x,y], "size": [w,h], "color": <name>, "fill": bool}`.
- **`line`** — `{"from": [x,y], "to": [x,y], "color": <name>}`.

Optional per-layer `offset` `[dx, dy]` shifts the layer on the canvas.

### Skeleton — connect parts by construction (not by luck)

Hand-placing many `offset`/`at` stamps and hoping they meet is the #1 source of
mangled poses (a leaning torso drifts off the hips → a gap → a "horseshoe").
A **skeleton** removes the guesswork. A motif declares named **`anchors`**
(`{name: [x, y]}` in its own grid coords — `neck`, `shoulder_r`, `hips`, `hand`,
`foot`). A sprite's `skeleton` is a list of **bones**, each an affine `shape`
placement whose pivot is pinned either to an absolute point or, via `attach`, to a
**parent bone's world anchor** — so the parts meet no matter how the parent is
rotated/leaned:

```jsonc
"skeleton": [
  { "name": "chest", "shape": "knight_chest", "pivot": "hips",
    "at": [13, 17], "skew": [-0.1, 0] },                         // root
  { "name": "head",  "shape": "knight_head_3q", "pivot": "neck",
    "attach": { "to": "chest", "anchor": "neck" } },             // neck meets neck
  { "name": "back-leg", "shape": "knight_leg", "pivot": "hip",
    "attach": { "to": "chest", "anchor": "hip_l" } },
  { "name": "sword", "shape": "sword", "pivot": "grip", "rotate": 56,
    "attach": { "to": "sword-arm", "anchor": "hand" } }
]
```

A bone takes the same transforms as a `shape` layer (`rotate`/`skew`/`squash`/
`flip`/`scale`/`recolor`); `pivot` may be an anchor name or `[x, y]`; `attach`
supports an optional `shift: [dx, dy]`. Bone order is z-order; attach order is
resolved automatically. `sprites/knight-battle.json` is the worked example. See
`emberhold` motifs for anchor placement.

### Checks — art direction as pass/fail predicates

Encode the target as predicates so iterating is "fix the failures", not "guess
from the picture". `inspect` evaluates them. Rules: `connected` (one solid
piece); `on_canvas` (`layer?`, `margin?` — nothing clipped); `centered_x`
(`layer`, `in`, `tol?`); `left_of`/`right_of`/`above`/`below` (`layer`, `of`,
`slack?`, whole-bbox ordering); `top_above` (`layer`, `of`, `by?` — the layer's
*highest* point sits above the other's, e.g. a blade rising past the shoulders
even while the grip is low); `touches` (`layer`, `of?`); `min_coverage`
(`value`). A target region
is a layer name, a list of names, or `"all"`.

```jsonc
"checks": [
  { "rule": "connected" },
  { "rule": "centered_x", "layer": "shield", "in": ["chest","back-leg","front-leg"], "tol": 1 },
  { "rule": "above", "layer": "sword", "of": "chest" },
  { "rule": "left_of", "layer": "cape", "of": "chest", "slack": 1 }
]
```

## How compilation works (where to edit)

- `pixeltracks/palette.py` — hex↔RGBA, named palettes, `shade` (≈ `theory.py`).
- `pixeltracks/shapes.py` — grids + transforms `flip`/`rotate`/`scale`/`recolor`.
- `pixeltracks/raster.py` — canvas, pixel/rect/ellipse/line painters, the affine
  grid draw (rotate/shear/squash, **sub-pixel supersampled so thin rotated parts
  don't break into gaps**), auto-outline, upscale (≈ `synth.py`).
- `pixeltracks/inspect.py` — the text/geometry evaluators behind `inspect`
  (ASCII dump, per-layer bbox + connectivity lint, `checks` runner). Add new
  check rules here.
- `pixeltracks/describe.py` — the motif/sprite index behind `describe` (size,
  anchors, `used_by` cross-reference, unused-motif detection).
- `pixeltracks/compositor.py` — composites a resolved sprite's layers/frames into a
  sheet + atlas (≈ `sequencer.py`). Add new layer *kinds* here.
- `pixeltracks/spec.py` — load/validate bible + sprites; `extends`; `Group`/
  `discover_groups` for the `groups/sprites/` layout (and validation in `_validate_layer`).
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

## Authoring notes (lessons from building a party + attack animations)

Practical things that bite when authoring a multi-character animated set (see the
`emberhold` group: a 4-class RPG party with per-class attacks and monsters):

- **Generate specs from a small builder script** that asserts every row in a
  motif/`pixels` grid is the same length and *names the offending row*. Ragged
  grids are the #1 hand-authoring error; catch them before the renderer does.
- **Don't forget the `palette` field.** A missing bible `palette` surfaces as the
  confusing `outline colour 'outline' is not in the palette` (the outline name has
  nothing to resolve against). If validate complains about the outline colour,
  check the palette exists first.
- **Rig animations with shared sub-shapes, then transform — don't redraw.** Split
  the hero into a `*_torso` + a reused `*_leg` (placed twice) so the torso can lean
  while the back foot plants and the front foot lunges; swing the weapon as a
  separate motif about a `pivot` pinned with `at`, through a real angle arc. Give
  attack sprites a `size` override (wider/taller than the still) so the swung
  weapon has room.
- **A motion-trail crescent must be concentric with the swing — concave toward the
  pivot, not toward the blade.** Reusing the *sword's* rotation for the `slash`
  makes the crescent's opening face the blade, so the blade pokes through it and it
  reads as a hollow "eyeglass" loop. Instead set the crescent's concavity with
  `flip` and give it only a small `rotate` tangent to the blade, placed just past
  the edge (e.g. strike `flip:h, rotate:~8`; follow-through `flip:h, rotate:~120`).
- **Weapon facing must match the attack direction.** An arrow that flies right
  needs the bow in the forward (right) hand — `flip:"h"` it — or the projectile
  appears to pass back through the body. Draw back toward the body, loose away.
- **Reuse one effect motif, recolour per class.** One `spark`/`flash` motif serves
  every caster; `recolor` it at the placement (e.g. cyan→gold) so a cleric's smite
  reads *holy* while a mage's bolt reads *arcane* — no second motif needed.
- **A 4-class party justifies ~24-28 palette entries** (per-class material ramps),
  above the 8-16 rule of thumb; hold coherence with one shared outline, one warm
  gold accent across classes, and identical body proportions.
- **You can see animations directly:** an animated sprite exports a horizontal
  sheet PNG — `Read` it to view all frames at once. For stills, tile them into one
  contact-sheet PNG (composite each `frame0`, `upscale`, paste onto a backdrop)
  rather than reading a dozen files.

### Posing for life (why a sprite reads as "plastered on a wall" — and what fixes it)

A dead-front, bilaterally symmetric, perfectly vertical figure reads as a paper
doll. The fixes come straight from classical drawing/animation, and they told us
what the *engine* was missing:

- **Line of action.** Build the pose on one sweeping C- or S-curve (sword tip →
  leaning spine → planted foot). A straight vertical spine is the stiffest line
  there is.
- **Contrapposto / weight shift.** Put the weight on one leg and let the hips and
  shoulders tilt in *opposite* directions. A horizontal shoulder line is robotic;
  a diagonal one is alive. Draw the turned body's shoulders on a slant.
- **Break the frontal plane (the 3/4 turn).** Facing dead-front is the flattest
  view. Turning the body needs a genuine *redraw* of the head/torso (a `body_3q`
  motif: features clustered to one side, a nose bump on the leading contour, the
  far shoulder smaller) — affine transforms can't rotate a flat face into a
  profile. But they *can* finish the illusion: a small `skew` leans the torso and
  a `squash` (sx≈0.85–0.9) foreshortens it, so it sits in depth without redrawing
  per angle. This is exactly why the engine grew `skew`/`squash` — the art demand
  drove the feature. Rotation alone keeps everything feeling head-on.
- **Total asymmetry + overlap.** Nothing mirrored: sword arm cocked back-high,
  off-hand forward as a guard, legs at different bends. Let the near limbs cross
  *in front of* the torso — overlap is the cheapest depth cue (and a contrasting
  material like a steel gauntlet keeps the crossing arm from reading as a blob
  against a same-colour tunic).
- **Streaming cloth.** A scarf/cape given a `skew` streams with the motion and
  breaks the silhouette's symmetry — an easy, high-value "this figure is moving"
  signal.

The general lesson for the engine: 2D **affine** transforms (rotate + shear +
non-uniform scale about a joint) buy a lot of the "in-space" feel cheaply, but a
true change of *view* is still a redraw — so the roadmap is motif **view-sets**
(front / three-quarter / side) rather than trying to fake a turn with math alone.
