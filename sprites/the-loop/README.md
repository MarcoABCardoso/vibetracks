# the-loop — the protagonist of *The Loop*

A single-character cast: **`wanderer`**, the lone, mobility-first hero of the
roguelike platformer *The Loop* (`marcoabcardoso/roguelike-game`). The design
centers on running, jumping, and evasion with one trusty sword — so the sprite is
built from a **light leather jerkin**, not plate: fast and travel-worn rather than
armoured.

| Character | Archetype | Layers |
|-----------|-----------|--------|
| `wanderer` | Scout / duelist | light body + **head + brown eyes**, messy brown hair, brown leather **jerkin** (a recolored sleeveless shirt), teal travelling pants, brown shoes |

> **Note — the modern body is headless.** Unlike the classic combined set (head +
> eyes baked into the body), the modern generator splits them out: `body/bodies/male`
> is neck-down, and the **head** (`head/heads/human/male`, skin-matched) and **eyes**
> (`eyes/human/adult/default`, brown) are their own layers. Both are included here —
> without the head layer the character renders faceless. The eyes have no `climb`
> file (you face away while climbing), so that row is simply left faceless.

```bash
python -m vibesprites render the-loop/wanderer   # -> wanderer.png (+ .atlas.json, .spec.json)
```

## Sourced from the modern generator — for the platformer poses

Every layer is assembled from the **modern**
[Universal-LPC generator](https://github.com/LiberatedPixelCup/Universal-LPC-Spritesheet-Character-Generator)
(split-per-animation art), not the classic combined set, because *The Loop* needs
the **expanded poses** — the charset opts into the 13-animation set
(`spellcast, thrust, walk, slash, shoot, hurt, climb, idle, jump, sit, emote, run,
combat_idle`), so the output is an **832×2944** sheet that includes **jump, climb,
and a battle-ready combat_idle**. The classic `jrconway3` art only has the six base
poses and can't carry those.

The jerkin is why the wanderer is *all* modern art: classic leather armour ships no
`combat_idle` frames, so a leather-clad hero would go bare-chested in that pose. A
sleeveless shirt (recolored to leather browns) covers the whole set instead — every
layer here spans all 13 poses.

Bodies and hair are recolorable single sheets (colour is the sheet default); pants
and shoes are colour-split (teal / brown chosen by path). Two layers are recolored:
the `messy2` hair (from the generator's `orange` reference ramp to `chestnut` brown)
and the sleeveless shirt (from its ivory/tan ramp to leather browns).

Nothing is vendored — layers are fetched on demand and composited in z-order. The
render also emits `wanderer.atlas.json` (a frame map — row range + rects per
animation, so a consumer knows exactly where `jump.down.2`, `combat_idle.*.1`, etc.
live) and `wanderer.spec.json` (the compiled, charset-folded spec that produced the
sheet).

Attribution and licensing for every layer are in `CREDITS.csv` (modern LPC art is
**OGA-BY 3.0 / CC-BY-SA 3.0 / GPL 3.0**; redistributing the rendered sheet carries
those terms).
