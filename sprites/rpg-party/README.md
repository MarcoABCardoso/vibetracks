# rpg-party — a stereotypical 4-person party

A second `vibesprites` cast: the classic RPG party, each member a z-ordered stack
of real [Universal-LPC](https://github.com/jrconway3/Universal-LPC-spritesheet)
layers fetched on demand (nothing vendored).

| Character | Archetype | Layers |
|-----------|-----------|--------|
| `warrior` | Tank      | full steel plate (chest / pants / boots) + metal helm |
| `ranger`  | Scout     | brown leather chest + shoulders + bracers, tanned body, messy hair, teal pants |
| `mage`    | Caster    | wizardess: real purple **robe** + pointed **wizard hat** (assembled from the modern LPC library) over a classic female body |
| `cleric`  | Healer    | gold chest + blonde hair (holy) |

```bash
python -m vibesprites render-all --cast rpg-party   # -> out/sprites/rpg-party/*.png
```

## Two asset sources in one character (the mage)

The warrior, ranger and cleric are built from the **classic** Universal-LPC set
(one combined 832×1344 sheet per layer). That set is armour-focused — no robes.

The mage's robe and hat come from the **modern** LPC library
([LiberatedPixelCup](https://github.com/LiberatedPixelCup/Universal-LPC-Spritesheet-Character-Generator)),
which stores one PNG *per animation* instead of a combined sheet. A layer with an
`assemble` block stitches those per-animation files into the classic grid on the
fly, so classic and modern art composite together. Because `find_asset` accepts an
absolute-URL `source`/`base`, a single character freely mixes both repos.

**Limitation:** LPC *weapons* (a wizard's staff included) use oversize 192×192
frames and only exist for some animations, so they don't fit the 64×64 classic grid
this compositor targets — supporting them is a separate feature. Hence the mage has
robe + hat but no staff.

Attribution/licensing for every layer is in `CREDITS.csv` (classic art CC-BY-SA 3.0
/ GPL 3.0; the robe and hat carry their own upstream terms).
