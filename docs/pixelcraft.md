# PixelCraft — writing a coherent sprite set

This is PixelTracks' craft guide, the visual counterpart of `docs/composition.md`.
The CLI tells you how to *compile* a sprite; this tells you how to make a *set*
of sprites look like they belong to one game. The engine guarantees validity
(every colour is on-palette, every grid is well-formed); craft is what makes the
output look intentional instead of merely valid.

The governing idea is the same as the music Lab's: **coherence comes from a
shared bible — one palette and a few reusable shape motifs — transformed, not
re-drawn.** A sprite set that shares nothing is a pile of stickers; a set that
restates the same hook in every sprite is monotonous. Aim between.

## 1. The palette is the key signature

In music every cue shares a key; in art every sprite shares a **palette**. This
is the single biggest lever for coherence, so spend real effort here.

- **Keep it small.** 8–16 colours for a whole group. A tight palette forces
  family resemblance — the reason a NES game looks like one game.
- **Name by role, not by hue.** `armor`, `armor_hi`, `armor_sh`, `cloak`,
  `gold` — not `blue1`, `blue2`. Roles let a *palette swap* recolour an entire
  sprite meaningfully (see §4). Sprites reference names, never raw hex.
- **Build ramps.** For each material give a shadow/mid/highlight trio
  (`steel_sh` → `steel` → `steel_hi`). Three values per material reads as form;
  one value reads as a flat blob. Declare them under the bible's `ramps` so the
  relationship is documented.
- **One warm accent.** A mostly-cool palette with a single warm accent (or vice
  versa) gives the eye a focal point — here, the gold crest against cool steel.

## 2. Silhouette first, detail second

A sprite is read as a **shape** before any interior colour registers. If the
silhouette is mush, no amount of shading saves it.

- Block the silhouette in one colour, squint, and check it's legible at native
  size. Only then add interior shading.
- Let the engine's **auto-outline** (`outline` in the bible) trace the
  silhouette for you — author motifs *without* the outer black ring and carry
  only interior shading (visor slits, belt lines). This keeps grids readable in
  a diff and guarantees a consistent 1px outline everywhere.
- Reserve the darkest palette value for outlines/eyes so features punch through.

## 3. Shape motifs are your leitmotifs

A **motif** in the bible is a reusable grid — a body pose, an emblem, a prop.
Quote it across sprites the way a score quotes its theme, and the set coheres.

- **State the hero shape in full once** (the anchor sprite), then reuse it by
  reference (`{"shape": "knight"}`) rather than pasting pixels. One edit to the
  motif updates every sprite that uses it — the whole point of a spec.
- **Transform instead of redrawing.** A layer that references a shape can
  `flip` (mirror — a facing change), `rotate` (any angle; a multiple of 90 is a
  lossless grid turn, any other angle rotates in pixel space about a `pivot`),
  `scale` (integer
  enlarge — the augmentation move), and `recolor` (remap palette names for *this
  placement only*). Same DNA, new pose. These are the exact analogues of music's
  `invert` / `retrograde` / `stretch` / `transpose`.
- **Let a small emblem recur.** A crest that sits on the hero's chest and again,
  enlarged, on a banner is one motif with two faces — the cross-modal idea in
  miniature, and the cheapest way to make two unrelated sprites feel related.

## 4. The palette swap is the headline move

The pixel equivalent of transposing a theme into a darker key is the **palette
swap**: keep the layers identical and override only the colours.

```jsonc
// knight-dusk.json — same pose as knight.json, night colours
{ "extends": "../artbook.json",
  "palette": { "steel": "#465089", "cloak": "#7a2f6a", "gold": "#d8a24a" },
  "layers": [ { "shape": "knight" }, { "shape": "crest", "offset": [5, 6] } ] }
```

This is what no prompt-per-asset workflow gives you: a "dusk" or "corrupted" or
"player-2" variant that is *provably* the same sprite, because the only diff is
the colour table. Use it for day/night, factions, status effects, and reskins.

## 5. Coherence is not repetition

If every sprite quotes the hero shape, the set is monotonous — the visual version
of restating the full hook in every track. Vary how present the theme is:

- **Anchor sprite** states the hero pose + emblem in full.
- **Variants** restate it transformed (palette swap, flip, re-pose).
- **Companions** (an enemy, an item) share only the *palette* and outline, and
  carry their own shape. They belong to the world without echoing the hero — the
  way a battle cue rides the shared key while dropping the main theme.

## 6. Animation: pose, don't redraw

An animated sprite is a list of `frames`; each frame is a still composited the
same way, and they export to a horizontal **sheet** + an `.atlas.json` of frame
rects and `hold` counts (the temporal analogue of concatenating sections).

- **Rig it, don't slide it.** Split the character into parts (torso, a `leg`
  placed twice, the weapon) and pose them *independently* per frame. Sliding one
  baked stamp a pixel or two reads as nothing — the body must articulate: the
  back leg **plants** while the front leg **lunges**, and the torso **leans**.
  Weight shift is what sells a swing; a rigid body with only the sword moving
  looks dead. (See `sprites/knight-attack.json`.)
- **Swing about a joint, not a corner.** Give the weapon a `pivot` (the hand, in
  the shape's own pixel coordinates), pin that pivot to a body point with `at`,
  and animate `rotate` through a real arc (e.g. −32° → 60° → 102° → 145°). A
  90°-only stamp rotation snaps and lands the blade in the wrong place; a pivoted
  arbitrary angle traces the arc the way an arm actually moves.
- **Anticipation → action → follow-through → settle.** Wind the blade *back* past
  rest before the strike, and let it *overshoot* down-and-across after. A 5–6
  frame swing with these reads far better than the hit alone.
- **Hold the key frame.** Give the impact frame a `hold` of 2 so the eye catches
  it; keep in-between frames at 1.
- **Trail the spark.** Put the `slash`/`flash` motif on the action frames only,
  rotated to follow the blade (same `rotate`/`pivot` trick) so it *trails the
  edge* instead of floating beside the body. Energy spikes where motion peaks.

## 7. Scenes & big sprites: build up, don't blow up

Two ways to go bigger than one small figure — both are *composition*, the same
"reuse transformed" discipline one level up (see the `dusk-glade` demo).

- **A scene is a sprite made of sprites.** Give it a wide `size`, `"scene": true`,
  `outline: null`, paint a backdrop with a `background` fill + `rect`/`ellipse`/
  `line` bands (sky, ground, water), then stamp finished sprites with `sprite`
  layers. Compose for depth: **overlap** (a near rock crossing the tree base) and
  **size/height** (things lower on the canvas read as closer) do the work a flat
  row of icons can't. Vary each stamp — `flip` and `scale` the same object so a
  scatter of three ferns isn't three identical stamps. Because the pieces are
  *meant* to be separate, `scene: true` mutes the single-body lint; keep using
  `on_canvas`/`left_of`/`above` `checks` to pin placement.
- **A 64px hero is a canopy of motifs, not a 64-row grid.** Hand-pixelling a big
  grid is a trap; instead draw a few small motifs (a `trunk`, one `leaf_cluster`)
  and stamp them with `shape`/skeleton + `scale`/`flip`/`offset` into the large
  form — then drop `scale` to 6–8 so the PNG isn't enormous. `great-oak` is six
  leaf stamps and a trunk. The silhouette rule still rules: get the big shape
  reading first, shade second.

## 8. Forms: sculpt with light, don't place pixels

For anything with **volume** — a character, a creature, a rounded prop — reach for
**`form` layers** before hand-pixelling. This is the visual echo of the music
Lab's synth: a note is a compact token the synth turns into a full timbre, and a
form is a compact solid the engine turns into fully-shaded pixels. You state
*which solid, where, in what material, lit from where*; the engine derives every
shadow and highlight. A figure becomes ~10 forms you can hold in your head, not a
400-cell grid you place by hand.

- **Think in solids.** Block the body as spheres/capsules/boxes/cones the way a
  sculptor blocks masses: a capsule torso, a sphere head, cone helm, capsule
  limbs. Get the *masses* right first — silhouette still rules (§2), so check the
  blocked silhouette in `inspect` before fussing shading.
- **The ramp is the material; light does the modelling.** A form's `material` is a
  bible **ramp** (`steel_sh → steel → steel_hi`). Three values read as a rounded
  surface; one reads flat. This is finally what makes `ramps` *work* — declare them
  once and every form of that material shades consistently under one `light`
  (default `up_left`). Keep the light direction the same across a set, exactly as a
  score keeps one key.
- **Depth is overlap + contact shadow.** Forms composite back-to-front (later =
  nearer); a nearer form drops an automatic **contact shadow** on the one behind.
  Order lower-on-canvas parts *later* so nearer things overlap farther ones, and
  let the shadow carve the seams — it's what separates a helm from a head even in
  one colour.
- **Separate touching masses by material.** Same-material forms fuse into a blob.
  Contact shadow helps, but give adjacent parts a *reason* to differ — iron limbs
  against a steel torso, a warm gold accent on the pauldrons — the same
  one-warm-accent discipline as §1, now doing double duty as mass separation.
- **Pose for life — but rig it.** Everything in §6's "posing for life" applies:
  a line of action, contrapposto (hips and shoulders tilting opposite ways),
  breaking the flat frontal plane with a `skew`/`squash`, total asymmetry and
  overlap. Forms buy this cheaply because articulating a form **relights** it (the
  highlight stays with the world light, it doesn't spin with the part). But
  articulated forms **do not hold together on their own** — hand-placed rotated
  limbs float and gap. Build any real pose as a **form skeleton**: bones that
  `attach` at anchors so the parts meet by construction (the same fix grids needed).
- **A raised weapon must contrast — or it reads as a pipe.** A steel blade ending
  next to a steel helm looks like a tube joining the arm to the head. Make the
  blade a *different* ramp (gold), and swing it into **empty space** away from the
  body, not back across the head.
- **Animate by sweeping the rig.** A form rig animates like any skeleton (§6): one
  skeleton per frame, only the moving bones' angles changing, with anticipation →
  strike (held) → follow-through. Two rules that are easy to get backwards: make
  **all** the turning parts rotate the **same** direction, and make the acting
  hand actually **travel** through the arc (a limb that only spins in place reads
  as moving the wrong way). Derive the angles from the geometry rather than
  guessing — a down-hanging capsule's free end sits at `(-L·sinθ, L·cosθ)`.
- **Judge it in `inspect`, never the PNG.** Every rule above is verified as text +
  geometry + `checks` (`connected`, `on_canvas`, `top_above` a blade over the
  helm…), because an upscaled PNG *hides* floating limbs, clipped blades, and
  pipe-to-the-head reads. Add the checks, get `inspect --all-frames` clean, *then*
  look at the PNG for colour and feel. The `forge-knights` group is the worked set:
  `knight-forms` (a figure in solids), `knight-forms-mono` (contact shadow alone
  separating one material), `knight-forms-rig` (a skeleton-held steep pose), and
  `knight-forms-swing` (a 5-frame chop).

## Cohesion checklist

- [ ] Every sprite `extends` its group's `artbook.json`.
- [ ] Every colour is a palette **name**; the palette is small and role-named.
- [ ] The hero shape is a bible motif, stated in full once and reused by
      reference (transformed) elsewhere — not pasted.
- [ ] At least one variant is a pure **palette swap** of another sprite.
- [ ] At least one companion shares only the palette, not the hero shape.
- [ ] Silhouettes read at native size; the auto-outline is on.
- [ ] Volumetric subjects use **`form` layers** shaded from bible `ramps` under one
      consistent `light`; a raised weapon uses a contrasting material.
- [ ] Any real pose is a **form skeleton** (bones attached at anchors), not
      hand-placed rotated forms; it carries `connected` + `on_canvas` `checks`.
- [ ] Structure/pose was judged in **`inspect`** (`--all-frames` for animations),
      with the PNG used only for colour and delivery.
- [ ] `validate` passes and `render-all` produces a clean manifest.
