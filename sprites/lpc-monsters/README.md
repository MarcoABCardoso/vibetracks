# lpc-monsters — a monster set for battle scenes

A **monster set**: a folder of finished LPC-style enemy spritesheets plus a
`bestiary.json` that records each sheet's geometry. Unlike a character *cast*
(`sprites/rpg-party/`), a monster is **not** a stack of composited layers — it is
one ready-made sheet the scene compositor slices a single facing/frame from. So
this folder has no `charset.json` and does not appear as a `vibesprites` cast.

Each sheet is a grid of 64×64 cells: **rows are facings** in LPC order
(`up`, `left`, `down`, `right`) and **columns are animation frames**. A couple of
sheets differ, and `bestiary.json` names only those exceptions:

| Monster | Sheet | Notes |
|---------|-------|-------|
| `slime`, `bat`, `snake`, `ghost`, `eyeball`, `pumpking`, `big_worm`, `small_worm` | 64px cells, 4 facings | the default geometry |
| `bee` | 2 rows only | `dirs: ["down","up"]` |
| `man_eater_flower` | tall 64×128 cells | `frame: [64,128]` |

The art lives in `assets/` and is **vendored** (committed), because it was supplied
with the project rather than fetched from the upstream LPC remote the way character
layers are.

## Battle scenes

A **scene** stages a party against monsters into one framed picture — the layer
above the compositor. Scenes live in the top-level `scenes/` folder:

```bash
python -m vibesprites scene ff3-battle     # -> out/scenes/ff3-battle.png
```

`scenes/ff3-battle.json` is a Final Fantasy III-style battle: the four-member
`rpg-party` ranked in a diagonal column on the right facing left, this monster set
massed on the left facing right, over a dusk field. A scene spec is authored in
low-res native pixels (`size`) and nearest-neighbour zoomed by `upscale`, so it
stays crisp and chunky like the games it evokes:

```json
{
  "size": [384, 240], "upscale": 3,
  "background": { "top": "#161d3f", "bottom": "#6a5788", "horizon": 0.44,
                  "ground_top": "#4d743c", "ground_bottom": "#1d3115" },
  "actors": [
    {"kind": "monster", "monster": "pumpking", "pos": [120, 118]},
    {"kind": "party",   "character": "warrior", "pos": [286, 54], "dir": "left"}
  ]
}
```

Each actor's `pos` is the top-left of its (scaled) cell; actors draw in list order
(later = in front) and get an automatic ground shadow (`"shadow": false` to opt
out). Party actors accept `anim`/`dir`/`frame`; monster actors accept `dir`/`frame`.
See `vibesprites/scene.py` for the full set of knobs.

## Attribution

The monster art in `assets/` was supplied via the project's `lpcmonsters.zip`. It
is LPC-style pixel art and, like the rest of the Liberated Pixel Cup ecosystem, is
presumed to carry the usual LPC dual license (**CC-BY-SA 3.0 / GPL 3.0**). Exact
authorship was not included with the archive — verify provenance and credit the
original artists against the upstream source before redistributing. See
`CREDITS.csv`.
