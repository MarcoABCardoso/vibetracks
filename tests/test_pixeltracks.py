"""Smoke tests for the PixelTracks Lab: colour theory, grid transforms, every
spec validates, a sprite renders to sane pixels, and the PNG round-trips.

Run with:  python -m unittest discover -s tests
"""

import glob
import os
import unittest

import numpy as np

from pixeltracks import palette, shapes, spec
from pixeltracks.compositor import composite_frame, coverage, render_sprite
from pixeltracks.pngio import encode_png
from pixeltracks.raster import add_outline, new_canvas, upscale

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "art", "tiny-knight")
BIBLE = os.path.join(DEMO, "artbook.json")
SPRITES = sorted(glob.glob(os.path.join(DEMO, "sprites", "*.json")))


class TestPalette(unittest.TestCase):
    def test_parse_hex_forms(self):
        self.assertEqual(palette.parse_hex("#ff8800"), (255, 136, 0, 255))
        self.assertEqual(palette.parse_hex("#f80"), (255, 136, 0, 255))
        self.assertEqual(palette.parse_hex("#ff880080"), (255, 136, 0, 128))
        self.assertEqual(palette.parse_hex("transparent"), (0, 0, 0, 0))

    def test_shade_lightens_and_darkens(self):
        self.assertEqual(palette.shade((100, 100, 100, 255), 0.0), (100, 100, 100, 255))
        self.assertEqual(palette.shade((100, 100, 100, 255), -1.0), (0, 0, 0, 255))
        self.assertEqual(palette.shade((100, 100, 100, 255), 1.0), (255, 255, 255, 255))

    def test_bad_colour_raises(self):
        with self.assertRaises(ValueError):
            palette.parse_hex("ff8800")          # missing '#'
        with self.assertRaises(ValueError):
            palette.parse_hex("#xyzxyz")         # bad hex digits


class TestShapeTransforms(unittest.TestCase):
    def setUp(self):
        self.grid = ["ab", "cd"]

    def test_flip(self):
        self.assertEqual(shapes.flip(self.grid, "h"), ["ba", "dc"])
        self.assertEqual(shapes.flip(self.grid, "v"), ["cd", "ab"])
        self.assertEqual(shapes.flip(self.grid, "hv"), ["dc", "ba"])

    def test_rotate_clockwise(self):
        self.assertEqual(shapes.rotate(self.grid, 90), ["ca", "db"])
        self.assertEqual(shapes.rotate(self.grid, 180), ["dc", "ba"])
        self.assertEqual(shapes.rotate(self.grid, 270), ["bd", "ac"])

    def test_scale_augments(self):
        self.assertEqual(shapes.scale(["ab"], 2), ["aabb", "aabb"])

    def test_recolor_legend_swaps_names(self):
        leg = {"x": "steel", "y": "gold"}
        self.assertEqual(shapes.recolor_legend(leg, {"steel": "night"}),
                         {"x": "night", "y": "gold"})

    def test_ragged_grid_raises(self):
        with self.assertRaises(ValueError):
            shapes.normalize_grid(["ab", "c"])


class TestSpecs(unittest.TestCase):
    def test_bible_loads(self):
        bible = spec.load_bible(BIBLE)
        self.assertTrue(bible.sprites)
        self.assertIn("knight", bible.motifs)
        self.assertIn("crest", bible.motifs)

    def test_all_sprites_resolve(self):
        bible = spec.load_bible(BIBLE)
        self.assertTrue(SPRITES, "no sprite specs found")
        for path in SPRITES:
            with self.subTest(sprite=os.path.basename(path)):
                s = spec.resolve_sprite(path, bible)
                self.assertTrue(s["frames"])

    def test_palette_swap_only_changes_colours(self):
        bible = spec.load_bible(BIBLE)
        knight = spec.resolve_sprite(os.path.join(DEMO, "sprites", "knight.json"), bible)
        dusk = spec.resolve_sprite(os.path.join(DEMO, "sprites", "knight-dusk.json"), bible)
        # Same layers/pose, different steel colour — the leitmotif move.
        self.assertEqual(knight["frames"], dusk["frames"])
        self.assertNotEqual(knight["palette"]["steel"], dusk["palette"]["steel"])

    def test_off_palette_colour_rejected(self):
        bible = spec.load_bible(BIBLE)
        with self.assertRaises(spec.SpecError):
            spec._validate_layer({"rect": {"at": [0, 0], "size": [2, 2], "color": "no_such"}},
                                 {"palette": {"steel": (0, 0, 0, 255)}, "motifs": {}},
                                 {"steel"}, where="x")

    def test_two_primitives_in_a_layer_rejected(self):
        with self.assertRaises(spec.SpecError):
            spec._validate_layer({"pixels": ["aa"], "rect": {"color": "x"}},
                                 {"palette": {}, "motifs": {}}, set(), where="x")


class TestGroups(unittest.TestCase):
    def test_discover_finds_demo(self):
        groups = spec.discover_groups(ROOT)
        self.assertIn("tiny-knight", [g.name for g in groups])

    def test_sprite_names_follow_bible_order(self):
        g = spec.find_group("tiny-knight", ROOT)
        self.assertEqual(g.sprite_names()[0], "knight")
        self.assertTrue(os.path.isfile(g.sprite_path("slime")))

    def test_unknown_group_raises(self):
        with self.assertRaises(spec.SpecError):
            spec.find_group("does-not-exist", ROOT)


class TestRenderAndPng(unittest.TestCase):
    def test_outline_traces_silhouette(self):
        canvas = new_canvas(4, 4)
        canvas[1:3, 1:3] = (255, 0, 0, 255)        # a 2x2 opaque block
        add_outline(canvas, (0, 0, 0, 255))
        # A transparent pixel orthogonally adjacent to the block is now outlined.
        self.assertEqual(tuple(canvas[0, 1]), (0, 0, 0, 255))
        self.assertEqual(tuple(canvas[1, 1]), (255, 0, 0, 255))  # interior untouched

    def test_sprite_renders_non_empty(self):
        bible = spec.load_bible(BIBLE)
        s = spec.resolve_sprite(os.path.join(DEMO, "sprites", "knight.json"), bible)
        frame = composite_frame(s, s["frames"][0])
        self.assertEqual(frame.shape, (16, 16, 4))
        self.assertGreater(coverage(frame), 0.1)   # not empty
        self.assertEqual(frame.dtype, np.uint8)

    def test_animation_sheet_and_atlas(self):
        bible = spec.load_bible(BIBLE)
        s = spec.resolve_sprite(os.path.join(DEMO, "sprites", "knight-attack.json"), bible)
        out = render_sprite(s)
        self.assertEqual(out["atlas"]["frame_count"], 4)
        self.assertTrue(out["atlas"]["loop"])
        # Four 16-wide frames laid side by side.
        self.assertEqual(out["sheet"].shape, (16, 64, 4))

    def test_png_has_signature_and_upscale(self):
        canvas = new_canvas(2, 2)
        canvas[0, 0] = (10, 20, 30, 255)
        data = encode_png(upscale(canvas, 4))
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(upscale(canvas, 4).shape, (8, 8, 4))


if __name__ == "__main__":
    unittest.main()
