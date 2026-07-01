# Vision — Structured, Coherent Game-Artifact Generation

## The thesis

Most "AI for game assets" today is a prompt box wrapped around a generator.
You type, it returns a thing, you type again, it returns a *different* thing.
Each output is plausible in isolation and **dissonant in aggregate** — the
sprites don't share a palette, the music doesn't share a key, the writing
doesn't share a voice. There is no source of truth, nothing is reusable, and a
change to the world's identity means re-rolling everything and hoping.

VibeTracks (this repo) demonstrates a different model for **one** asset class —
game music. Its lessons generalize, and that generalization is the vision:

> **Author a structured spec; compile it deterministically; make the generator a
> constrained primitive, never the pipeline. Coherence comes from a shared
> bible and reusable motifs that are _transformed, not regenerated_.**

The AI's job is to write and edit **specs** — small, diffable, reviewable
documents — not to emit final pixels or samples. A deterministic engine turns
specs into artifacts. Where genuine generative texture is needed, it is bolted
in as an *engine* whose output is forced back through the project's shared
constraints (palette, key, voice). The black box is on a leash, not at the
wheel.

## What VibeTracks already proves

VibeTracks is **Lab 0** — the existence proof. It models a song as JSON and
compiles it to WAV with a pure-Python synth. The pieces that matter are not
musical; they are *architectural*, and every one of them ports:

| Mechanism | In VibeTracks | Why it generalizes |
|-----------|---------------|--------------------|
| **Spec, not output** | tracks are JSON; Claude edits JSON | reviewable, diffable, deterministic, version-controlled |
| **Bible** | `soundtrack.json`: key, bpm, palette, motifs | one inherited identity → nothing drifts |
| **Palette** | named instruments every track shares | the same "voices" everywhere |
| **Motifs + transforms** | `transpose`/`invert`/`retrograde`/`stretch` | variants by transformation, not re-prompting |
| **Deterministic engine** | oscillators/filters → samples | inspectable, reproducible, free |
| **Optional generative engine** | `soundfont` (sample-based), conformed to the mix | generation as a *plug-in primitive* |
| **Validator** | scales catch wrong notes before render | cheap correctness checks pre-compile |
| **Groups** | self-contained scores | bounded, composable units |
| **compile → preview → iterate** | `render` → listen → edit | the authoring loop |

A throwaway visual prototype ("pixeltracks") confirmed the port: from a ~200-line
palette + spec + raster engine — **no image generator** — we compiled a coherent
character sprite, produced a "dusk" variant by *palette swap* (the leitmotif
move), and animated a knight's attack as the same parts re-posed on a frame
grid. The structure, coherence, and controllability carried over directly. The
expressive ceiling of pure procedural rendering is lower for images than audio —
which is precisely the signal for *where* the constrained generative engine
earns its place.

## The shape of every Lab

A "Lab" is a structured spec → compile → iterate workshop for one artifact
class. Every Lab is the same machine with a different theory:

```
  bible (identity)  ─┐
  asset specs       ─┼──►  validator  ──►  deterministic engine  ──►  artifact
  reusable motifs   ─┘                          ▲
                                                │ (optional)
                              constrained generative engine ──► conform pass
                                                                  (palette / key / voice)
```

- **Bible** — the identity every asset inherits (the coherence anchor).
- **Specs** — declarative, composable, what the AI authors.
- **Motifs + transforms** — reuse over regeneration; family resemblance is
  structural.
- **Deterministic engine** — the default renderer; reproducible and free.
- **Generative engine** — optional, seeded, *and always conformed* to the
  bible's constraints on the way out (the "master bus").
- **Validator** — modality-specific "theory" checks before you spend a render.

## The Labs

| Lab | Artifact | "Theory" (constraints) | Engine spectrum |
|-----|----------|------------------------|-----------------|
| **VibeTracks** *(exists)* | music / SFX | scales, harmony, rhythm | pure DSP → soundfont |
| **PixelTracks** *(exists)* | sprites, items, animation, VFX | palette, silhouette, shape motifs, frame timing | procedural raster → (later) ControlNet/seeded diffusion, palette-conformed |
| **TileTracks** | tilesets, autotiling, levels/maps | grid adjacency rules, Wang/blob tiles, connectivity | procedural → constrained gen |
| **UITracks** | HUD, panels, icons, fonts | 9-slice, type scale, spacing grid, contrast | procedural (strongest fit) |
| **LoreTracks** | dialogue, item text, quests, codex | character voice "palette", world facts, tone | templated → LLM-with-guardrails |
| **SystemTracks** | enemy stats, loot tables, balance curves | math/data constraints, monotonicity, budgets | pure deterministic |
| **MeshTracks** *(stretch)* | low-poly props, materials | shape language, topology budgets | procedural / parametric → gen |

Each Lab ships, like VibeTracks, with a worked demo group and a craft guide
(its `docs/composition.md` equivalent) so the AI authors *intentionally*, not
just *validly*.

## The Root Spec — one world, many artifacts

The ambitious payoff is binding the Labs together with a single **World Bible**
(`world.json`) — the root spec from which every Lab's bible descends.

```
                         world.json  (the Root Spec)
        ┌──────────────┬──────────┴───────┬──────────────┬─────────────┐
   music bible     art bible          tile bible      lore bible    systems bible
   (VibeTracks)   (PixelTracks)      (TileTracks)    (LoreTracks)  (SystemTracks)
```

The World Bible declares the things that are *true across modalities*:

- **Identity** — name, genre, tone, era.
- **Palette of meaning** — a "shape/color/voice language": *round + warm +
  gentle = safe*; *spiky + cold + terse = hostile*. Each Lab interprets it in
  its own medium.
- **Named entities** — places, factions, characters, items — referenced by *id*
  from any Lab.
- **Cross-modal motifs** — the single most important idea: one motif with
  faces in every medium. The kingdom's **sun-crest** (a shape in PixelTracks),
  its **sunrise theme** (a melody in VibeTracks), and its **"dawn" tonal note**
  (a phrase in LoreTracks) are three projections of one root motif. Transform
  the root — darken it for the fallen kingdom — and *every* medium's version
  transforms in step.

This is what no prompt-per-asset workflow can do: change the world's identity in
one place and have the music, art, and writing all move together, provably
coherent because they share a root.

## High-level plan

**Phase 0 — Proof (done).** VibeTracks ships a complete music Lab: bible,
motifs, transforms, deterministic synth + optional soundfont engine, validator,
groups, demo scores, craft guide.

**Phase 1 — A second Lab (PixelTracks). _(done)_** The visual prototype is now a
real Lab mirroring VibeTracks' module layout: an art bible (`artbook.json`:
palette, shape motifs, outline), JSON sprite/animation specs, a procedural raster
engine (`pixeltracks/`), a validator (palette adherence, well-formed grids,
empty-silhouette coverage check), and exporters (PNG sheet + atlas JSON). The
shared machine was factored into `labkit/` (group discovery, the Lab registry)
and a `python -m labs` dispatcher now unifies both Labs. **No generative model
yet** — the structured core is proven first, exactly as the music Lab did before
soundfont. Worked demos: the `mossy-hollow` group (a small critter set — a
palette-swap variant and a re-posed hop animation included) and the bigger
`emberhold` JRPG party (skeleton-rigged attack poses).

**Phase 2 — The Root Spec.** Introduce `world.json` and refactor both Labs'
bibles to `extend` it. Add cross-Lab references by entity id and the first
cross-modal motif (the sun-crest ⇄ sunrise theme). Validate coherence *across*
Labs (does every entity referenced exist? do shared motifs stay in sync?).

**Phase 3 — Breadth.** Add Labs where deterministic theory is strongest and
payoff is high: TileTracks (levels), UITracks (HUD/icons), SystemTracks
(balance data). Each follows the same template; each adds its craft guide.

**Phase 4 — Constrained generation.** Add the optional generative engine to the
Labs that need it (PixelTracks, LoreTracks), strictly as a primitive: seeded and
reproducible, structurally conditioned by the procedural spec (e.g. ControlNet
from a procedural silhouette), and **conformed** to the bible on output (palette
quantize, voice-check). Generation may vary the texture; it may not break the
identity.

**Phase 5 — Integration & packaging.** Exporters into real engines (Godot,
Unity, Tiled, Aseprite, glTF), a unified `build` that compiles a whole world,
and a manifest the way `render-all` already indexes every track — so a game's
entire artifact set rebuilds, coherently, from specs.

## Honest scope

- **Where this shines:** anything with discrete, formalizable structure — music,
  pixel/flat art, tiles, UI, systems data, animation timing. Here the
  deterministic engine reaches near the quality ceiling on its own.
- **Where the generative engine is required:** organic texture and
  illustration — painterly portraits, photoreal scenes. The analogy doesn't
  remove the black box there; it *cages* it (seed-locked, structure-conditioned,
  palette-conformed) so it can't drift off-world.
- **Style matters:** choose styles where constraints are natural (pixel art,
  flat vector, low-poly, chiptune/synth) — the visual equivalent of VibeTracks
  choosing a synth-forward aesthetic. Fighting for photoreal everything is the
  fast path back to dissonance.

The north star is simple: **a game whose music, art, and writing are coherent by
construction, because they are compiled from one world.**
