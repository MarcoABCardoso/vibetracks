"""Tests for the Godot exporter and the shared ``Exporter`` registry.

The exporter emits plain text (``.tres``/``.import``) from structured records, so
most of it is checked without a Godot binary: the emitters are pure functions, and
one integration pass renders a real sprite and asserts the pack round-trips the
animation atlas. Audio rendering is intentionally avoided here (it is ~real-time);
the WAV path is covered by the emitter test + the end-to-end ``labs build`` run.

Run with:  python -m unittest discover -s tests
"""

import glob
import json
import os
import re
import tempfile
import unittest

from labkit.export import EXPORTERS, find_exporter
from labkit.exporters import godot
from pixeltracks import spec as px_spec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "groups", "sprites", "mossy-hollow")


class TestRegistry(unittest.TestCase):
    def test_find_godot(self):
        self.assertEqual(find_exporter("godot").name, "godot")

    def test_unknown_raises(self):
        with self.assertRaises(SystemExit):
            find_exporter("nope")

    def test_every_exporter_entry_imports(self):
        for e in EXPORTERS:
            self.assertTrue(e.entry.count(":") == 1)


class TestWavImport(unittest.TestCase):
    RES = "res://demo/music/g/theme.wav"

    def test_forward_loop_when_looping(self):
        text = godot._wav_import(self.RES, loop=True)
        self.assertIn("edit/loop_mode=1", text)
        self.assertIn('type="AudioStreamWAV"', text)
        self.assertIn("compress/mode=0", text)     # uncompressed
        self.assertIn(self.RES, text)

    def test_loop_disabled_when_not(self):
        self.assertIn("edit/loop_mode=0", godot._wav_import(self.RES, loop=False))


class TestPngImport(unittest.TestCase):
    def test_crisp_uncompressed(self):
        text = godot._png_import("res://demo/sprites/g/hero.png")
        self.assertIn('type="CompressedTexture2D"', text)
        self.assertIn("compress/mode=0", text)         # lossless
        self.assertIn("mipmaps/generate=false", text)  # crisp pixels


class TestSpriteFramesTres(unittest.TestCase):
    def setUp(self):
        self.atlas = {
            "name": "hop", "size": [8, 8], "scale": 2, "fps": 12,
            "frame_count": 3, "loop": True,
            "frames": [
                {"name": "a", "hold": 1, "x": 0,  "y": 0, "w": 16, "h": 16},
                {"name": "b", "hold": 2, "x": 16, "y": 0, "w": 16, "h": 16},
                {"name": "c", "hold": 1, "x": 32, "y": 0, "w": 16, "h": 16},
            ],
        }
        self.text = godot._sprite_frames_tres(self.atlas, "res://demo/sprites/g/hop.png")

    def test_header_and_load_steps(self):
        # load_steps = 1 ext_resource + 3 sub_resources + 1 [resource].
        self.assertIn("[gd_resource type=\"SpriteFrames\" load_steps=5 format=3]", self.text)
        self.assertEqual(self.text.count("[sub_resource type=\"AtlasTexture\""), 3)

    def test_regions_match_atlas(self):
        rects = re.findall(r"region = Rect2\(([^)]*)\)", self.text)
        self.assertEqual(rects, ["0, 0, 16, 16", "16, 0, 16, 16", "32, 0, 16, 16"])

    def test_durations_are_holds(self):
        durs = re.findall(r'"duration": ([0-9.]+)', self.text)
        self.assertEqual(durs, ["1.0", "2.0", "1.0"])

    def test_loop_and_speed_and_name(self):
        self.assertIn('"loop": true', self.text)
        self.assertIn('"speed": 12.0', self.text)
        self.assertIn('"name": &"default"', self.text)


class TestExportIntegration(unittest.TestCase):
    """Render real sprites and assert the pack mirrors the animation atlas."""

    def _render(self, out_root):
        group = "mossy-hollow"
        bible = px_spec.load_bible(os.path.join(DEMO, "artbook.json"))
        recs = []
        for name in ("fox", "fox-hop"):          # a still + a 4-frame animation
            path = os.path.join(DEMO, "sprites", name + ".json")
            sprite = px_spec.resolve_sprite(path, bible)
            from pixeltracks.compositor import render_sprite
            from pixeltracks.raster import upscale
            from pixeltracks.pngio import write_png
            result = render_sprite(sprite)
            out_dir = os.path.join(out_root, group)
            os.makedirs(out_dir, exist_ok=True)
            png = os.path.join(out_dir, sprite["name"] + ".png")
            write_png(png, upscale(result["sheet"], sprite["scale"]))
            recs.append({"sprite": sprite["name"], "file": png,
                         "frames": result["atlas"]["frame_count"],
                         "fps": result["atlas"]["fps"], "loop": result["atlas"]["loop"],
                         "atlas": result["atlas"]})
        return {"pixeltracks": {group: recs}}

    def test_pack_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            records = self._render(os.path.join(tmp, "out"))
            dist = find_exporter("godot").export(records, os.path.join(tmp, "dist"), "demo")

            base = os.path.join(dist, "sprites", "mossy-hollow")
            # every sprite -> png + import; only the animated one -> a SpriteFrames.
            for name in ("fox", "fox-hop"):
                self.assertTrue(os.path.isfile(os.path.join(base, name + ".png")))
                self.assertTrue(os.path.isfile(os.path.join(base, name + ".png.import")))
            self.assertFalse(os.path.isfile(os.path.join(base, "fox.tres")))
            self.assertTrue(os.path.isfile(os.path.join(base, "fox-hop.tres")))

            with open(os.path.join(dist, "pack.json")) as f:
                manifest = json.load(f)
            self.assertEqual(manifest["engine"], "godot4")
            names = {a["name"]: a for a in manifest["assets"]}
            self.assertFalse(names["fox"]["animated"])
            self.assertTrue(names["fox-hop"]["animated"])
            self.assertIn("sprite_frames", names["fox-hop"])

    def test_tres_regions_match_rendered_atlas(self):
        with tempfile.TemporaryDirectory() as tmp:
            records = self._render(os.path.join(tmp, "out"))
            dist = find_exporter("godot").export(records, os.path.join(tmp, "dist"), "demo")
            atlas = records["pixeltracks"]["mossy-hollow"][1]["atlas"]  # fox-hop
            with open(os.path.join(dist, "sprites", "mossy-hollow", "fox-hop.tres")) as f:
                tres = f.read()
            rects = re.findall(r"region = Rect2\(([^)]*)\)", tres)
            expected = [f'{f["x"]}, {f["y"]}, {f["w"]}, {f["h"]}' for f in atlas["frames"]]
            self.assertEqual(rects, expected)


if __name__ == "__main__":
    unittest.main()
