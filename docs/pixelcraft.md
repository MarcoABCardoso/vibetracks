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

## Cohesion checklist

- [ ] Every sprite `extends` its group's `artbook.json`.
- [ ] Every colour is a palette **name**; the palette is small and role-named.
- [ ] The hero shape is a bible motif, stated in full once and reused by
      reference (transformed) elsewhere — not pasted.
- [ ] At least one variant is a pure **palette swap** of another sprite.
- [ ] At least one companion shares only the palette, not the hero shape.
- [ ] Silhouettes read at native size; the auto-outline is on.
- [ ] `validate` passes and `render-all` produces a clean manifest.
