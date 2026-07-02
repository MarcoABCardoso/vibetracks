# Shipping into Godot — the resource-pack exporter

The Labs turn specs into raw artifacts (`.wav`, `.png` + `.atlas.json`). The
**exporter** wraps a whole world's artifacts into a **drop-in Godot 4 resource
pack** — the last mile that lets the assets actually run in a game. It is plain
text generation (no Godot binary in the loop), so the pack is deterministic and
diffable like everything else here.

```bash
python -m labs build <world> --engine godot      # -> dist/<world>/ + dist/<world>.zip
python -m labs build                             # no world = every group in every Lab
python -m labs build <world> --out build/ --no-zip
```

`build` renders every asset in the world's groups (reusing each Lab's own render
path), then emits the pack. Building `<world>` includes only the groups whose
bible `extends` that world.

## What the pack contains

```
dist/<world>/
  README.md                       # install + node-wiring notes
  pack.json                       # index of every asset (paths, types, fps, loop)
  music/<group>/<track>.wav       # + <track>.wav.import
  sprites/<group>/<sprite>.png    # + <sprite>.png.import
  sprites/<group>/<sprite>.tres   # SpriteFrames — animated sprites only
```

The `res://` paths baked into the resources assume the pack lives at
**`res://<world>/`** — extract the zip at your project root and it lands there.

### Sprites → `Texture2D` / `AnimatedSprite2D`

Each sprite PNG ships with a `.png.import` set for pixel art: **uncompressed**
(`compress/mode=0`) with **mipmaps off**. A still sprite is just a texture — drop
it on a `Sprite2D`.

An **animated** sprite (more than one `frame`) additionally gets a **SpriteFrames**
`.tres`. It is built straight from the PixelTracks atlas:

- one `AtlasTexture` per frame, its `region` = the frame's rect in the sheet
  (already in exported pixel coordinates);
- one animation named `"default"`, `loop` = the atlas loop flag;
- `speed` = the sprite's **`fps`** (bible default or per-sprite; default 10);
- each frame's **`duration`** = its **`hold`** (so a `hold: 2` frame lingers twice
  as long, exactly as in the spec).

Use it: add an `AnimatedSprite2D`, set *Sprite Frames* to the `.tres`, call
`play("default")`.

### Music → `AudioStreamPlayer`

Each track ships as a `.wav` + a `.wav.import`. A track with a `"loop": true`
section imports with **forward loop** enabled (`edit/loop_mode=1`) so game BGM
repeats seamlessly; a one-shot (e.g. a victory fanfare) imports with looping off.
Drop the `.wav` on an `AudioStreamPlayer`.

## Crisp pixels

Godot 4 controls texture filtering on the node/project, not the import. For pixel
art set **Project Settings → Rendering → Textures → Canvas Textures → Default
Texture Filter = Nearest** (or set each `CanvasItem`'s *Texture Filter* to
"Nearest"). The textures already ship uncompressed with mipmaps disabled.

## Notes

- **UIDs are omitted on purpose.** Godot resolves `ExtResource`/imports by `path`
  and assigns uids on first import — no invalid-uid warnings, fully deterministic
  output. On first project open Godot re-imports the PNG/WAV (the `.godot/imported`
  cache is not shipped, as usual).
- **A real `.pck`** needs the Godot binary, which isn't part of this pipeline; the
  drop-in folder + zip is the deliverable and imports identically.
- **Another engine?** Exporters are a registry (`labkit/export.py`) mirroring the
  Lab registry — a new target (Tiled, Unity) is one `Exporter(...)` entry plus an
  emitter under `labkit/exporters/`. Today `godot` is the shipped target.
- Build output (`out/`, `dist/`) is gitignored; commit the specs and regenerate
  the pack with one `build`.
