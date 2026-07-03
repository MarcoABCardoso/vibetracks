# knight-guild — LPC sprite cast (demo / PoC)

A worked demo of the `spritekit` **LPC-compositor** engine: a character is a JSON
stack of real [Universal-LPC](https://github.com/jrconway3/Universal-LPC-spritesheet)
layer PNGs, composited to an 832×1344 spritesheet.

```bash
python -m vibetracks.spritekit validate                    # no Pillow needed
python -m vibetracks.spritekit render knight-guild/knight  # needs Pillow (pip install vibetracks[sprites])
# -> out/sprites/knight-guild/knight.png
```

## The spec

- `charset.json` — the cast bible: `frame`, the layer `palette` (category → z-order),
  reusable `outfits`, and the `characters` list. (Counterpart of a soundtrack bible.)
- `characters/knight.json` — a z-ordered stack of `layers`; the `guild-uniform`
  outfit is quoted for cohesion. (Counterpart of a track.)
- `assets/` — the vendored LPC layer PNGs this cast composites.

## Licensing (important)

The bundled art in `assets/` is from the Universal-LPC project and is dual-licensed
**CC-BY-SA 3.0 / GPL 3.0** — see `CREDITS.csv` for per-file authors and sources.
Attribution is **required**, and derivatives inherit the copyleft terms. Keep
`CREDITS.csv` with any sprites you ship from this cast. To composite against a full
LPC checkout instead of the vendored subset, point `$VIBETRACKS_LPC_ASSETS` at it.
