# rpg-party — a stereotypical 4-person party

A second `vibesprites` cast: the classic RPG party, each member a z-ordered stack
of real [Universal-LPC](https://github.com/jrconway3/Universal-LPC-spritesheet)
layers fetched on demand (nothing vendored).

| Character | Archetype | Layers |
|-----------|-----------|--------|
| `warrior` | Tank      | full steel plate (chest / pants / boots) + metal helm |
| `ranger`  | Scout     | brown leather chest + shoulders + bracers, tanned body, messy hair, teal pants |
| `mage`    | Caster    | cloth hood + leather chest & cloth pants **recolored** to an indigo robe |
| `cleric`  | Healer    | gold chest + blonde hair (holy) |

```bash
python -m vibesprites render-all --cast rpg-party   # -> out/sprites/rpg-party/*.png
```

The **mage's blue robe is not a separate asset** — it is the same brown leather
chest and white cloth pants the others use, remapped by the engine's per-layer
`recolor` (each source colour tinted along an indigo ramp by its brightness). This
is the sprite counterpart of a soundfont program change: same art, different palette.

The base LPC set is armor-focused (no robes or staves — those live in expanded
sets), so the party leans martial; point `$VIBESPRITES_ASSETS` at a fuller LPC
checkout to dress a wizard in cloth. Attribution/licensing for every layer is in
`CREDITS.csv` (all art is CC-BY-SA 3.0 / GPL 3.0).
