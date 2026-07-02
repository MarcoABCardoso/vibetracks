# Proposal: the Form model — give sprites the abstraction gap that makes music work

> Status: **Phases 1–3 landed.** The `form` layer kind + `forms.py` lighting
> model (Phase 1), per-form depth with automatic contact shadow (Phase 2), and
> articulated forms with world-fixed pose relighting (Phase 3) are implemented and
> tested, with the `forge-knights` demo (`knight-forms`, `knight-forms-mono`,
> `knight-forms-hero`, `knight-pixels`) as the proof. What remains: a skeleton
> whose bones are forms, and `light` view-preset sugar. This is the design case for
> why PixelTracks felt "limited" next to VibeTracks and the change that closes it.

## The observation

Modeling worked *well* for music and only *okay* for sprites, even though both
Labs are the same machine (bible + motifs + leitmotif transforms + a
deterministic compile). The difference is not the engine's power. It is **where
the authoring primitive sits relative to the output** — and that one fact
decides how much leverage an AI author gets.

## Diagnosis: music has an abstraction gap, sprites don't

**Music's primitive — the note `["C4", 1, 0.8]` — sits far above the WAV.** The
synth (`vibetracks/synth.py`, `instruments.py`) *manufactures* the richness:
oscillators, ADSR, filters, FM, Karplus, reverb. The author writes what a
*musician decides* (pitch, duration, harmony, which motif) and the engine
supplies what a musician never hand-crafts (the waveform sample by sample). A
small spec becomes a rich sound. Just as importantly, the AI already **reasons
natively in notes, chords and motifs** — the spec *is* its mental model.

**Sprites' primitive — the ASCII pixel grid — sits right on top of the PNG.**
`raster.draw_grid` is a near-identity map: the char at `(i, j)` becomes the pixel
at `(i, j)`. The engine adds almost no *form* — a 1px outline (`add_outline`) and
affine **re-arrangements** of pixels the author already placed
(`draw_grid_affine`). There is no abstraction gap: the author decides all ~400
pixels of a 20×20 sprite by hand, in a representation the AI reasons poorly in
(spatial layout as rows of characters). Music's equivalent would be forcing the
AI to hand-type PCM samples instead of notes.

### The tell: every piece of scaffolding unique to PixelTracks is compensation

VibeTracks needs none of these; PixelTracks grew all of them to paper over the
missing gap:

| Feature | Exists because… |
|---------|-----------------|
| `inspect` (ASCII dump, geometry lint) | the author **can't see** what they wrote. You never "inspect" music — you read the notes. |
| `describe` | a motif is a 20-row grid, not "a few notes," so an artbook is unscannable. |
| `checks` (`connected`, `centered_x`, `top_above`…) | you can't eyeball whether the belt sits on the hips. |
| `skeleton` / anchors | hand-placed stamps don't meet; parts must be connected *by construction*. |
| the "posing for life" + "view-sets" notes | the ceiling itself: affine math can *rearrange* pixels but can't *synthesize a new view* — "a true change of view is still a redraw." |

None of this makes the pictures better; it makes an intractable primitive
survivable. Sprites aren't limited because the engine is weak. They're limited
because **the author works one abstraction tier below where the AI is strong.**
Music handed the AI a composer's console; sprites handed it a bitmap editor.

## The fix: raise the primitive so the engine synthesizes *form*

Give sprites the same abstraction gap music has. Let the author describe a
subject the way an illustrator actually thinks about one — a small hierarchy of
**solid forms with materials, posed at joints, under a light** — and have the
engine *render* that down to shaded pixels. That render step is the visual
analogue of the synth turning a note into a waveform: the author supplies what
an **artist decides** (which forms, where, what material, lit from where); the
engine supplies what an artist grinds out by hand (every pixel, the shading
ramp, the core/rim shadow, the contact occlusion, the outline).

Working name: the **Form model**, exposed as a new `form` **layer kind** beside
the existing `pixels` / `shape` / `rect` / `ellipse` layers. It is **additive** —
not a rewrite. The whole current engine, palette-swap, skeleton, scene, and
export pipeline stay intact; a sprite may freely mix `pixels`, `shape` and
`form` layers.

### The new primitive: a `form`

A form is a filled 2.5D **blob primitive** with a *material* and a *depth*, not a
grid of chars:

```jsonc
{ "form": "capsule",          // sphere | capsule | box | disc | cone | blob(path)
  "at": [10, 8], "size": [8, 12], "round": 3,
  "material": "steel",         // a palette RAMP name — not a flat colour
  "light": "up_left",          // optional per-form override of the sprite light
  "z": 2,                       // depth order + who occludes whom (auto contact shadow)
  "rotate": -12, "squash": [0.9, 1] }   // the leitmotif transforms it already supports
```

The engine turns that one line into a **shaded** form:

1. **Rasterise** the primitive to a mask (generalising today's
   `draw_ellipse` / box painters).
2. **Shade it from the material ramp automatically.** Pick the declared ramp
   (`steel_sh → steel → steel_hi` — already sitting in the bible's `ramps`) and
   assign values by a cheap lighting model: the sprite's light direction dotted
   against the blob's surface normal gives shadow on the away side, highlight on
   the lit side, a 1px rim on the lit contour. **Today `ramps` is inert
   documentation.** The Form model makes ramps do real work — precisely as a
   synth patch turns one note into a full ADSR-shaped, filtered timbre.
3. **Auto core-shadow + contact occlusion** between forms by `z`: the arm in
   front drops a soft shade onto the torso behind it — the depth cue the craft
   guide currently spends five bullets teaching authors to fake by hand.
4. **Form-derived outline** already works (`add_outline` over the composite).

So the *content* the AI authors is ~8 forms for a character instead of ~400
pixels — and each form is a concept it holds cleanly ("steel capsule torso,"
"skin sphere head," "gold cone helm"), the way it holds "a C-minor chord." The
engine synthesizes the pixels **and the shading**, which is exactly where
hand-authoring is hardest and least suited to the AI's talent.

### Why this is the *same* win music got — not a different one

| | Music (works) | Sprites today (limited) | Sprites + Form model |
|---|---|---|---|
| Primitive | note (pitch, dur) | pixel char in a grid | form (shape, material, pose) |
| Engine supplies | timbre: ADSR, FM, filter, reverb | 1px outline + pixel re-arrange | shading: ramp lighting, core/contact shadow, rim, outline |
| Abstraction gap | **large** | **~none** | **large** |
| AI reasons in the spec's units? | yes (composer) | no (bitmap editor) | yes (draughtsman: forms + light) |
| `ramps` / patch role | patch shapes the sound | ramp is inert docs | ramp shapes the shading |
| A new view / pose | — | **redraw required** | re-pose forms + relight (no redraw) |

The line-of-action / contrapposto / ¾-turn problem the craft guide documents
largely dissolves: a form hierarchy posed at joints and *relit* gives weight
shift and turn for free, because the engine is **shading solids in space**
instead of shoving flat pixels around. "A true change of view is still a redraw"
stops being true once the primitive is a solid with a surface normal.

### It composes with everything already there

- **Palette-swap leitmotif** — unchanged and *better*: swapping a ramp recolours
  *with correct shading*, not flat.
- **Skeleton / anchors** — a bone's `shape` can be a form (or form group); joints
  pose forms exactly as they pose grids today.
- **Scenes / tiles / big sprites** — unchanged; a 64px hero becomes a handful of
  forms instead of a canopy of motif stamps.
- **`inspect` / `checks`** — still apply, and a whole class of them (`FLOATING`,
  connectivity, "is the belt on the hips") largely evaporates because forms
  connect and shade by construction.
- **Export** — the PNG / atlas / Godot pipeline is downstream of the composite and
  is untouched.

## Where it plugs in (real seams)

- `pixeltracks/forms.py` *(new)* — `shade_form(mask, ramp, light, normals)`: the
  lighting model that maps a material ramp onto a rasterised blob. This is the
  new "synth."
- `pixeltracks/raster.py` — add `draw_form_shaded(...)`; generalise the
  ellipse/box painters to emit a mask + normal field.
- `pixeltracks/compositor.py::_draw_layer` — one new `elif "form" in layer:`
  branch; per-form `z` feeds an occlusion pass in `composite_frame`.
- `pixeltracks/spec.py::_validate_layer` — validate `form`, `material` (must name
  a ramp/palette entry), `light`, `z`.
- `docs/pixelcraft.md` + `/spritesheet` skill — a "Form the figure, don't pixel
  it" section; teach authoring in forms + light.
- `pixeltracks/describe.py` / `inspect.py` — learn to summarise forms.

## Phased, additive migration

1. **Phase 1 — `form` layer kind + lighting model. ✅ DONE.** `pixeltracks/forms.py`
   (`shade_form`/`draw_form`) + the compositor branch + spec validation, consuming
   the bible's existing `ramps` and a new (optional) `light`. No spec breaks — a
   sprite mixes `pixels`, `shape` and `form` layers freely. The `forge-knights`
   group ships the proof: `knight-forms` is the figure in a dozen shaded solids,
   `knight-pixels` the same figure hand-pixelled at the same size; the forms output
   is verified on-palette and genuinely multi-step-shaded (`tests/test_pixeltracks.py`).
2. **Phase 2 — depth / occlusion + auto contact shadow. ✅ DONE.** `composite_frame`
   keeps a z-buffer (depth = draw order, override with a form's `z`); a nearer form
   ramp-shifts the geometry behind it one step darker (`cast_contact_shadow`), so
   overlapping *same-material* forms read as distinct masses with the shadow still
   provably on-palette. `knight-forms-mono` (all steel + a skin face) is the proof
   — in Phase 1 it fused into one blob. Retires the hand-faked shadow guidance.
3. **Phase 3 — articulated forms + pose relighting. ✅ DONE.** A form poses through
   the same affine as a `shape`/bone (`rotate`/`skew`/`squash` about a `pivot`), via
   a shared `raster.blit_affine` sub-pixel sampler. The key move: shade each form in
   its *local* frame with the world light pre-rotated by `-rotate`, so once the tile
   turns into world space the highlight lands on the world-lit side — a limb that
   leans is **relit**, not a highlight that spins with the part (verified by
   `test_articulated_form_relights_world_fixed`). `knight-forms-hero` is the posed
   proof. This kills the "a true change of view is still a redraw" ceiling for forms.
   *Still ahead:* `light: front | three_quarter | side` view-preset sugar and a
   skeleton whose bones are forms.
4. **Phase 4 — craft guide + skill + `describe`/`inspect`** updated to make forms
   the default way to author a figure; grids remain for emblems, UI, and pixel
   detail.

## The alternative I am *not* recommending (but naming honestly)

Bolt a real **diffusion / image model** onto a `diffusion` layer kind — the exact
mirror of the optional `soundfont` engine, "sample-based realism" for pixels. It
would raise fidelity fastest, but it **breaks the repo's thesis**: determinism,
coherence-by-shared-spec, and *provable* palette-swap variants all come from the
pure-Python compile. A diffusion asset can't be palette-swapped by editing a
colour table, can't be diffed, and drifts from its siblings — the exact "pile of
stickers" the whole engine exists to prevent. It is worth offering as an
**opt-in** engine for one-off hero art (as `soundfont` is opt-in for orchestral
realism), but not as the core model, and not the thing that fixes "sprites feel
limited." The core fix is raising the primitive, not outsourcing it.

## One-line summary

Music works because the author writes *notes* and the synth makes the *sound*.
Sprites are limited because the author writes *pixels* and the engine barely adds
anything. The Form model gives sprites their synth: author *forms + light*, let
the engine make the *pixels*.
