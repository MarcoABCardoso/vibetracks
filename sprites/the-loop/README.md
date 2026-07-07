# the-loop — the protagonist of *The Loop*

A single-character cast: **`wanderer`**, the lone, mobility-first hero of the
roguelike platformer *The Loop* (`marcoabcardoso/roguelike-game`). The design
centers on running, jumping, and evasion with one trusty sword — so the sprite is
built from **light leather**, not plate: fast and travel-worn rather than armoured.

| Character | Archetype | Layers |
|-----------|-----------|--------|
| `wanderer` | Scout / duelist | light body + messy brown hair, brown leather armour, teal travelling pants, brown shoes |

```bash
python -m vibesprites render the-loop/wanderer   # -> out/sprites/the-loop/wanderer.png (+ .atlas.json)
```

## Sourced from the modern generator — for the platformer poses

Every layer is assembled from the **modern**
[Universal-LPC generator](https://github.com/LiberatedPixelCup/Universal-LPC-Spritesheet-Character-Generator)
(split-per-animation art), not the classic combined set, because *The Loop* needs
the **expanded poses** — the charset opts into the 12-animation platformer set
(`spellcast, thrust, walk, slash, shoot, hurt, climb, idle, jump, sit, emote, run`),
so the output is an **832×2688** sheet that includes **jump and climb**. The classic
`jrconway3` art only has the six base poses and can't carry those.

Bodies, armour, and hair are recolorable single sheets (colour is the sheet
default); pants and shoes are colour-split (teal / brown chosen by path). The
`messy2` hair ships only its colourless master (the generator's `orange` reference
ramp), so a `recolor` remaps it to the `chestnut` brown ramp to keep the wanderer
brown-haired.

Nothing is vendored — layers are fetched on demand and composited in z-order. The
render also emits `wanderer.atlas.json`: a frame map (row range + rects per
animation) so a consumer knows exactly where `jump.down.2`, `climb.*.4`, etc. live.

Attribution and licensing for every layer are in `CREDITS.csv` (modern LPC art is
**OGA-BY 3.0 / CC-BY-SA 3.0 / GPL 3.0**; redistributing the rendered sheet carries
those terms).
