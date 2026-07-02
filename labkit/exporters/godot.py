"""Godot 4 exporter — wrap rendered artifacts into a drop-in resource pack.

The Labs render raw artifacts (``out/<group>/<name>.png|wav`` + a sprite's
``.atlas.json``); this module turns them into what a Godot 4 project actually
loads, as plain text (no Godot binary in the loop — the pack stays deterministic
and diffable, in keeping with the rest of the repo):

* **Sprite PNG**  → the image + a ``.png.import`` (uncompressed, no mipmaps) so
  pixel art imports crisp. A **still** sprite needs nothing more (use it as a
  ``Sprite2D`` texture).
* **Animated sprite** → additionally a **SpriteFrames** ``.tres``: one
  ``AtlasTexture`` sub-resource per frame (its ``region`` is the frame rect from
  the atlas, already in exported pixel coords), gathered into one animation
  (``"default"``) whose per-frame ``duration`` is the frame's ``hold`` and whose
  ``speed`` is the sprite's ``fps``. Drop it on an ``AnimatedSprite2D``.
* **Music WAV** → the audio + a ``.wav.import`` whose ``edit/loop_mode`` is
  forward-loop when the track has a ``loop`` section (seamless BGM), else off.

Layout written under ``<dist_root>/<name>/`` (and the res:// paths baked into the
resources assume the pack sits at ``res://<name>/`` — extract the zip at the
project root):

    <name>/
      README.md   pack.json
      music/<group>/<track>.wav (+ .wav.import)
      sprites/<group>/<sprite>.png (+ .png.import) (+ <sprite>.tres if animated)

UIDs are intentionally omitted: Godot resolves ``ExtResource``/imports by ``path``
and assigns uids itself on first import (no invalid-uid warnings, fully
deterministic output).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil

# medium key (the Lab name) -> the pack subdirectory it exports into.
_MEDIUM_DIR = {"vibetracks": "music", "pixeltracks": "sprites"}


def _res_path(name: str, rel: str) -> str:
    """A res:// path for a pack-relative file, assuming the pack is at res://<name>/."""
    return f"res://{name}/{rel}".replace(os.sep, "/")


def _cache_hash(res: str) -> str:
    """A stable filename token for the (never-shipped) import cache entry."""
    return hashlib.md5(res.encode("utf-8")).hexdigest()[:16]


def _png_import(res_png: str) -> str:
    """A Godot 4 texture ``.import`` tuned for crisp, uncompressed pixel art."""
    cache = f"res://.godot/imported/{os.path.basename(res_png)}-{_cache_hash(res_png)}.ctex"
    return (
        "[remap]\n\n"
        'importer="texture"\n'
        'type="CompressedTexture2D"\n'
        f'path="{cache}"\n'
        "metadata={\n"
        '"vram_texture": false\n'
        "}\n\n"
        "[deps]\n\n"
        f'source_file="{res_png}"\n'
        f'dest_files=["{cache}"]\n\n'
        "[params]\n\n"
        "compress/mode=0\n"
        "compress/high_quality=false\n"
        "compress/lossy_quality=0.7\n"
        "compress/hdr_compression=1\n"
        "compress/normal_map=0\n"
        "compress/channel_pack=0\n"
        "mipmaps/generate=false\n"
        "mipmaps/limit=-1\n"
        "roughness/mode=0\n"
        'roughness/src_normal=""\n'
        "process/fix_alpha_border=true\n"
        "process/premult_alpha=false\n"
        "process/normal_map_invert_y=false\n"
        "process/hdr_as_srgb=false\n"
        "process/hdr_clamp_exposure=false\n"
        "process/size_limit=0\n"
        "detect_3d/compress_to=1\n"
    )


def _wav_import(res_wav: str, loop: bool) -> str:
    """A Godot 4 ``AudioStreamWAV`` ``.import``; forward-loops looping BGM tracks."""
    cache = f"res://.godot/imported/{os.path.basename(res_wav)}-{_cache_hash(res_wav)}.sample"
    loop_mode = 1 if loop else 0        # 0=disabled, 1=forward, 2=ping-pong, 3=backward
    return (
        "[remap]\n\n"
        'importer="wav"\n'
        'type="AudioStreamWAV"\n'
        f'path="{cache}"\n\n'
        "[deps]\n\n"
        f'source_file="{res_wav}"\n'
        f'dest_files=["{cache}"]\n\n'
        "[params]\n\n"
        "force/8_bit=false\n"
        "force/mono=false\n"
        "force/max_rate=false\n"
        "force/max_rate_hz=44100\n"
        "edit/trim=false\n"
        "edit/normalize=false\n"
        f"edit/loop_mode={loop_mode}\n"
        "edit/loop_begin=0\n"
        "edit/loop_end=-1\n"
        "compress/mode=0\n"
    )


def _sprite_frames_tres(atlas: dict, res_png: str) -> str:
    """A Godot 4 SpriteFrames ``.tres`` built from a PixelTracks atlas.

    Each frame becomes an ``AtlasTexture`` region over the source sheet; ``hold``
    maps to Godot's per-frame ``duration`` multiplier and ``fps`` to ``speed``.
    """
    frames = atlas["frames"]
    tex_id = "1_tex"
    # load_steps = the ext_resource + one sub_resource per frame + the [resource].
    load_steps = len(frames) + 2

    parts = [f'[gd_resource type="SpriteFrames" load_steps={load_steps} format=3]\n']
    parts.append(f'[ext_resource type="Texture2D" path="{res_png}" id="{tex_id}"]\n')

    sub_ids = []
    for i, fr in enumerate(frames):
        sid = f"AtlasTexture_{i}"
        sub_ids.append(sid)
        parts.append(
            f'[sub_resource type="AtlasTexture" id="{sid}"]\n'
            f'atlas = ExtResource("{tex_id}")\n'
            f'region = Rect2({fr["x"]}, {fr["y"]}, {fr["w"]}, {fr["h"]})\n'
        )

    frame_entries = ",\n".join(
        '{\n'
        f'"duration": {float(fr.get("hold", 1))},\n'
        f'"texture": SubResource("{sid}")\n'
        '}'
        for fr, sid in zip(frames, sub_ids)
    )
    loop = "true" if atlas.get("loop") else "false"
    speed = float(atlas.get("fps", 10))
    parts.append(
        "[resource]\n"
        "animations = [{\n"
        f'"frames": [{frame_entries}],\n'
        f'"loop": {loop},\n'
        '"name": &"default",\n'
        f'"speed": {speed}\n'
        "}]\n"
    )
    return "\n".join(parts)


def _readme(name: str, assets: list) -> str:
    n_sprites = sum(1 for a in assets if a["type"] == "sprite")
    n_anim = sum(1 for a in assets if a["type"] == "sprite" and a.get("animated"))
    n_tracks = sum(1 for a in assets if a["type"] == "music")
    return f"""# {name} — Godot resource pack

Generated by VibeTracks (`python -m labs build {name} --engine godot`).
Contains **{n_sprites} sprite(s)** ({n_anim} animated) and **{n_tracks} music track(s)**.

## Install

Extract this folder at your project root so it lives at **`res://{name}/`**
(the resource paths inside the `.tres`/`.import` files assume that location).
Open the project in Godot 4 — it re-imports the PNG/WAV files automatically.

## Use

- **Animated sprite** — add an `AnimatedSprite2D`, set its *Sprite Frames* to
  `res://{name}/sprites/<group>/<sprite>.tres`, then `play("default")`.
- **Still sprite** — add a `Sprite2D`, set its *Texture* to the `.png`.
- **Music** — add an `AudioStreamPlayer`, set its *Stream* to the `.wav`
  (looping tracks already import with forward loop enabled).

## Crisp pixels

For pixel art, set **Project Settings → Rendering → Textures → Canvas Textures →
Default Texture Filter = Nearest** (or set each node's *Texture Filter* to
"Nearest"). The textures ship uncompressed with mipmaps off.

See `pack.json` for the full asset index.
"""


def export(records: dict, dist_root: str, name: str) -> str:
    """Write a Godot 4 resource pack from ``build``'s records; return the pack dir.

    ``records``: ``{medium: {group: [asset record, ...]}}`` where a music record
    has ``file``/``loop`` and a sprite record has ``file``/``frames``/``atlas``.
    """
    dist_dir = os.path.join(dist_root, name)
    assets = []  # entries for pack.json / the README summary

    for medium, groups in records.items():
        subdir = _MEDIUM_DIR.get(medium)
        if subdir is None:
            continue  # a Lab with no Godot mapping — skip rather than guess
        for group, recs in groups.items():
            for rec in recs:
                src = rec["file"]
                base = os.path.basename(src)
                rel = os.path.join(subdir, group, base)
                dest = os.path.join(dist_dir, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(src, dest)
                res = _res_path(name, rel)

                if medium == "pixeltracks":
                    _write(dest + ".import", _png_import(res))
                    entry = {"type": "sprite", "group": group, "name": rec["sprite"],
                             "texture": res, "frames": rec.get("frames", 1),
                             "animated": rec.get("frames", 1) > 1}
                    if entry["animated"]:
                        tres_rel = os.path.join(subdir, group, rec["sprite"] + ".tres")
                        _write(os.path.join(dist_dir, tres_rel),
                               _sprite_frames_tres(rec["atlas"], res))
                        entry["sprite_frames"] = _res_path(name, tres_rel)
                        entry["fps"] = rec.get("fps", 10)
                    assets.append(entry)
                elif medium == "vibetracks":
                    _write(dest + ".import", _wav_import(res, rec.get("loop", False)))
                    assets.append({"type": "music", "group": group, "name": rec["track"],
                                   "stream": res, "loop": rec.get("loop", False),
                                   "seconds": rec.get("seconds")})

    os.makedirs(dist_dir, exist_ok=True)
    _write(os.path.join(dist_dir, "pack.json"),
           json.dumps({"name": name, "engine": "godot4", "assets": assets}, indent=2))
    _write(os.path.join(dist_dir, "README.md"), _readme(name, assets))
    return dist_dir


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
