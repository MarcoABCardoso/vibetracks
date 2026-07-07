# the-loop — the protagonist of *The Loop*

A single-character cast: **`wanderer`**, the lone, mobility-first hero of the
roguelike platformer *The Loop* (`marcoabcardoso/roguelike-game`). The design
centers on running, jumping, and evasion with one trusty sword — so the sprite is
built from **light leather**, not plate: fast and travel-worn rather than armoured.

| Character | Archetype | Layers |
|-----------|-----------|--------|
| `wanderer` | Scout / duelist | light body + messy brown hair, leather chest + shoulders + bracers over a leather belt, teal travelling pants, brown shoes |

```bash
python -m vibesprites render the-loop/wanderer   # -> out/sprites/the-loop/wanderer.png
```

Every layer is a real [Universal-LPC](https://github.com/jrconway3/Universal-LPC-spritesheet)
classic sheet, fetched on demand and composited in z-order — nothing is vendored
here. The output is a full 832×1344 LPC sheet (spellcast / thrust / walk / slash /
shoot / hurt, four facings), ready to slice into a Phaser atlas.

Attribution and licensing for every layer are in `CREDITS.csv` (classic LPC art is
**CC-BY-SA 3.0 / GPL 3.0** — redistributing the rendered sheet carries those terms).
