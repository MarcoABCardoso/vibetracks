# rpg-party — a stereotypical 4-person party

A `vibesprites` cast: the classic RPG party — tank, scout, caster, healer — each a
z-ordered stack of real LPC layers fetched on demand (nothing vendored). The whole
party is built from the **modern** Universal-LPC generator
([LiberatedPixelCup](https://github.com/LiberatedPixelCup/Universal-LPC-Spritesheet-Character-Generator)),
which stores one PNG *per animation*, so every member carries the expanded
platformer poses — and a battle-ready `combat_idle` — the classic combined set never
had.

| Character | Archetype | Layers |
|-----------|-----------|--------|
| `warrior` | Tank      | steel **plate** torso + **great helm**, charcoal trousers, iron boots |
| `ranger`  | Scout     | sleeveless tunic, teal pants, brown boots, brown **messy hair** (recolored) |
| `mage`    | Caster    | blue pointed **wizard hat**, long-sleeve gown, long hair, navy pants |
| `cleric`  | Healer    | white-and-gold long-sleeve robe, white pants, gilded shoes, fair hair |

```bash
python -m vibesprites render-all --cast rpg-party   # -> out/sprites/rpg-party/*
```

Each render writes three files per character: the `<name>.png` sheet, a
`<name>.atlas.json` frame map, and a `<name>.spec.json` — the compiled, charset-folded
spec that produced the sheet, so the output ships with its own recipe.

## Every pose stays fully equipped

The sheet is laid out over 13 animations (the classic six + `climb`, `idle`, `jump`,
`sit`, `emote`, `run`, and `combat_idle`) at their **canonical** Universal-LPC rows.
The modern library is generous but uneven: `body`, `head`, `hair`, cloth `pants`,
basic `shoes`, the `plate` torso, the great helm and the wizard hat all cover the
full set, but many pieces (leather armour, plate legs/boots, the female robe) stop
short of `combat_idle` — a gap would render as the bare body showing through. So each
member here is dressed **only in pieces whose art spans every pose**, and the party
sits on the well-covered male base (the generator draws its widest pose set there).
That is why the mage wears a long-sleeve gown rather than the true robe, and the
warrior's plate is paired with cloth trousers and boots.

## How the modern art is assembled

Each layer names an `assemble` base (relative to the charset's `remote`, the modern
generator's `spritesheets/` root). The `lpc` engine fetches that base's
per-animation file for every requested pose and pastes it at the pose's canonical
row, so the split-per-animation art drops into the same compositor as a combined
sheet. Colour-split pieces (pants, shoes, wizard hat, eyes) pick a colour by path;
single-sheet pieces (bodies, armour, hair) are recolorable — the ranger's brown hair
is a palette `recolor` of the colorless master sheet.

**Out of scope:** LPC *weapons* (a wizard's staff, a warrior's sword) use oversize
192×192 frames that don't fit the 64×64 grid this compositor targets — a separate
feature. Hence the party is equipped but unarmed.

Attribution/licensing for every layer is in `CREDITS.csv` (modern LPC art, variously
CC-BY-SA 3.0 / GPL 3.0 / OGA-BY 3.0 — honor each piece's terms in anything you ship).
