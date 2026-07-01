# Vision — a coherence engine for solo game worlds

## Who this is for

**A solo dev (or a game-jam team, or anyone prototyping) who needs a whole
game's worth of assets that read as _one game_ — fast, and without an art team.**

You have a world in your head. You need music, sprites, and — soon — tiles, UI,
item text, and enemy stats to match it. What you do *not* have is an artist, a
composer, a writer, and three weeks. The job to be done:

> Get a coherent set of world assets on screen quickly, keep them consistent as
> the game changes, and never hit the wall where "add one more asset" means
> "re-roll everything and hope it still matches."

That's the customer and that's the promise. Everything below serves it.

## The problem you actually have

Today the options are a prompt box or an asset pack, and both fail the *aggregate*:

- **A prompt box** (image/music generators) returns a plausible thing, then a
  *different* plausible thing. Ten prompts later your sprites don't share a
  palette, your music doesn't share a key, and there is no source of truth to
  fix. Change your game's identity and you re-roll all of it.
- **Asset packs** are internally consistent but don't match *each other* or
  *your* game — you end up with a patchwork that screams "assembled," not
  "authored."

Neither gives you the one thing a solo dev needs most: **a single source of truth
for what your world looks and sounds like, from which everything else follows.**

## What this is (and isn't)

VibeTracks is a **coherence engine**, not a generator. You — with an AI copilot —
author a small, structured **spec** describing your world; a deterministic engine
compiles it into finished assets; and coherence is *guaranteed* because every
asset descends from one world identity and is built by reusing shared motifs.

> **Author a structured spec; compile it deterministically; keep the generator a
> constrained primitive, never the pipeline. Coherence comes from a shared world
> and reusable motifs that are _transformed, not regenerated_.**

It is **not** trying to out-paint Midjourney or out-sing Suno. That's the wrong
fight and a crowded one. This is the layer those tools don't have: the
diffable, version-controlled **source of truth** and the orchestration that keeps
a solo dev's entire world consistent — and lets an AI agent build and edit it
*with* you, because specs are exactly what an agent is good at authoring. Where
real generative texture is genuinely needed, it's bolted in as a leashed
*engine*, its output forced back through your world's constraints (palette, key,
voice) on the way out. The black box is on a leash, not at the wheel.

## Why a solo dev should care

- **Speed.** `python -m labs new-world <name>` scaffolds a coherent starter world
  across every medium in one command. From there you iterate by editing tiny
  specs (or asking the agent to), not by re-rolling a prompt and praying.
- **Coherence by construction.** Everything `extends` one world bible, so nothing
  drifts — and a validator *proves* it: `python -m labs validate` checks that
  your art and music still resolve to the same world before you ship.
- **Change once, everything moves.** Your world's motifs have a face in every
  medium. Darken your kingdom's emblem and *both* the crest sprite and the theme
  music fall in step — the thing no prompt-per-asset workflow can do.
- **Free and reproducible where it counts.** The default engines are pure code:
  no per-asset API bill, deterministic output, all of it in git, all of it
  reviewable in a diff.

## Honest scope — read this before you get excited

The engine is not equally good everywhere, and pretending otherwise is how you
end up disappointed. Choose the fight you can win:

- **Where it's genuinely great — formal, discrete domains.** Music, tiles, UI,
  systems/balance data, and flat/pixel art. Here structure *is* the medium, and
  the deterministic engine reaches near the quality ceiling on its own. This is
  the core, and it's real: **VibeTracks' synth output is legitimately good.**
- **Where it's a boundary case — organic, illustrative work.** Painterly
  portraits, photoreal scenes, richly rendered sprites. Pure procedural rendering
  visibly falls short here, and no amount of structure fixes that. This is
  exactly where the caged generative engine earns its place (below) — and until
  it lands, set expectations accordingly.
- **So: pick a style whose constraints are natural** — pixel art, flat vector,
  low-poly, chiptune/synth. That's the visual equivalent of VibeTracks choosing a
  synth-forward aesthetic. Fighting for photoreal-everything is the fast road
  back to dissonance.

The tool's honesty is a feature: it will show you a coherent *rough* sprite and a
polished track, and it will tell you which is which.

## What exists today

- **VibeTracks (music) — the flagship.** A complete music Lab: a world/soundtrack
  bible, reusable motifs with real transforms (`transpose`/`invert`/`retrograde`/
  `stretch`), a pure-Python synth (numpy/scipy — no system audio tools), an
  optional sample-based `soundfont` engine conformed to the same mix, a validator
  that catches wrong notes before you render, and worked demo scores. This is the
  existence proof that a deterministic engine can hit the quality bar.
- **PixelTracks (sprites) — the honest boundary case.** The same machine in a
  second medium: an art bible (palette, shape motifs, outline), JSON sprite/
  animation specs, a procedural raster engine, a skeleton rig for connected poses,
  and a text-based `inspect`/`describe` toolchain for judging a sprite without
  squinting at a PNG. It proves the *architecture* ports cleanly — and it also
  maps precisely where procedural *quality* runs out. That boundary is a finding,
  not a failure: it's the map of where a leashed generator will go.
- **The world layer — coherence made checkable.** `worlds/<name>/world.json` is
  the root spec every medium's bible descends from: an identity, a *palette of
  meaning* (shape/colour/voice tags), named entities, and **cross-modal motifs**
  (one root, a face per medium, with transforms that move every face at once).
  `python -m labs validate` runs a cross-Lab coherence pass, and leaf specs (a
  track, a sprite) can declare what they `mean` and which `entities` they're
  about — all checked, so the media provably cannot drift. `new-world` scaffolds a
  wired, already-coherent starting point.

## How the machine works

A **Lab** is a spec → compile → iterate workshop for one artifact class. Every
Lab is the same machine with a different theory:

```
  world (identity)  ─┐
  asset specs       ─┼──►  validator  ──►  deterministic engine  ──►  artifact
  reusable motifs   ─┘                          ▲
                                                │ (optional)
                              constrained generative engine ──► conform pass
                                                                  (palette / key / voice)
```

- **World / bible** — the identity every asset inherits (the coherence anchor).
- **Specs** — small, declarative, composable; what you and the agent author.
- **Motifs + transforms** — reuse over regeneration; family resemblance is
  structural, not lucky.
- **Deterministic engine** — the default renderer: reproducible, free, in git.
- **Generative engine** — optional, seeded, *always conformed* to the world's
  constraints on output (the "master bus" for a black box).
- **Validator** — cheap, domain-specific correctness checks before you spend a
  render.

## The world — one identity, many artifacts

```
                         world.json  (the Root Spec)
        ┌──────────────┬──────────┴───────┬──────────────┬─────────────┐
   music bible     art bible          tile bible      lore bible    systems bible
   (VibeTracks)   (PixelTracks)      (TileTracks)    (LoreTracks)  (SystemTracks)
```

The world declares what's true *across* media: identity (name, genre, tone, era);
a **palette of meaning** (*round + warm + rising = hope*; *jagged + cold +
falling = threat*), read by each medium in its own way; **named entities**
referenced by id from any Lab; and **cross-modal motifs** — the payoff. One
motif, a face in every medium; transform the root and every face transforms in
step. A world is optional: a single-medium set needs none, and any group can be
*promoted* into a world later without a rewrite. You reach for a world exactly
when something must cohere across media — which, for a game, is the whole point.

## Roadmap — depth first

The core loop (author a world → compile coherent music + art → iterate) is
**built and works**. The temptation now is breadth — seven Labs on a checklist.
That's the wrong instinct: more Labs where structure already wins doesn't answer
the hard questions (organic quality, does anyone *use* this), it just adds
surface area. So the plan is depth first.

1. **Prove the loop on one real, playable world.** Build a small game's actual
   asset set end-to-end and make the authoring loop genuinely *fast* and *good* —
   this is both the proof and the template. Sharpen what a solo dev touches: the
   agent-driven authoring flow, the preview loop, and the moment-to-value of
   `new-world`. **A real user's world is the forcing function; find one.**
2. **Make assets actually ship.** Exporters into the tools a solo dev already
   uses — Godot, Tiled, Aseprite — and a unified `build` that compiles a whole
   world at once (the way `render-all` already indexes every track). Coherent
   assets that can't leave the repo aren't a product.
3. **Add the next Lab a real project needs — pulled, not pushed.** When an actual
   world hits a wall, fill it. The cheapest, highest-certainty wins are
   **SystemTracks** (enemy stats, loot, balance — pure deterministic data) and
   **TileTracks** (levels, autotiling); **UITracks** and **LoreTracks** follow.
   Each reuses the same machine and ships with a craft guide, but only when a
   world asks for it.
4. **Cage a generator for the media that need it.** Add the leashed generative
   engine to sprites and lore — seeded, structurally conditioned by the
   procedural spec (e.g. ControlNet from a procedural silhouette), and conformed
   to the world on output (palette-quantize, voice-check). It may vary the
   texture; it may not break the identity. This is what raises PixelTracks off its
   boundary — and it comes *after* depth proves the loop is worth generating into.

Future Labs, when their time comes: TileTracks, UITracks, LoreTracks,
SystemTracks, and (stretch) MeshTracks for low-poly props — each the same
spec→validate→compile machine with a different theory.

## North star

**A solo dev builds a whole game world that looks and sounds like one game —
coherent by construction, fast to change, shippable into their engine — without
an art team and without the asset-pack patchwork.** That's the win. Everything in
this repo is in service of making that loop fast, honest, and coherent.
