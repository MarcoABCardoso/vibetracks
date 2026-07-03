"""Tests for the sprite spritekit subsystem.

The spec loaders, validators, and the pure ``expand_layers`` resolve step always
run — they depend only on numpy. The actual composite render is gated behind
``lpc.available()`` (Pillow present + real art), mirroring how ``test_soundfont``
gates the FluidSynth render, so the suite still passes without Pillow.
"""

import os
import unittest

import numpy as np

from vibetracks.spritekit import compositor, layout, lpc, pngio, spec
from vibetracks.spritekit.layers import ENGINES, SHEET_ENGINES

HAVE_LPC = lpc.available()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAST_DIR = os.path.join(ROOT, "sprites", "knight-guild")


class TestLayout(unittest.TestCase):
    def test_universal_sheet_dimensions(self):
        self.assertEqual(layout.SHEET, (832, 1344))
        self.assertEqual(layout.COLS, 13)
        self.assertEqual(layout.ROWS, 21)

    def test_animation_rows_are_sequential(self):
        self.assertEqual(layout.animation_row("spellcast"), 0)
        self.assertEqual(layout.animation_row("walk"), 8)   # after 4+4 rows
        self.assertEqual(layout.animation_row("hurt"), 20)  # last row


class TestEngineRegistry(unittest.TestCase):
    def test_lpc_is_a_sheet_engine(self):
        self.assertIn("lpc", SHEET_ENGINES)
        self.assertIn("lpc", ENGINES)


class TestSpec(unittest.TestCase):
    def test_demo_cast_resolves(self):
        cast = spec.find_cast("knight-guild", ROOT)
        charset = cast.load_charset()
        self.assertIsNotNone(charset)
        for name in cast.character_names():
            ch = spec.resolve_character(cast.character_path(name), charset)
            self.assertTrue(ch["layers"])

    def test_discover_finds_the_cast(self):
        names = [c.name for c in spec.discover_casts(ROOT)]
        self.assertIn("knight-guild", names)


class TestValidation(unittest.TestCase):
    def _char(self, layers, outfits=None):
        return {"name": "x", "frame": [64, 64],
                "palette": {"body": {"engine": "lpc"}, "hair": {"engine": "lpc"}},
                "outfits": outfits or {}, "layers": layers}

    def test_layer_needs_exactly_one_kind(self):
        with self.assertRaises(spec.SpriteSpecError):
            spec._validate_character(
                self._char([{"layer": "body", "variant": "v", "outfit": "o"}]), "x")

    def test_unknown_layer_category_rejected(self):
        with self.assertRaises(spec.SpriteSpecError):
            spec._validate_character(
                self._char([{"layer": "wings", "variant": "v"}]), "x")

    def test_unknown_outfit_rejected(self):
        with self.assertRaises(spec.SpriteSpecError):
            spec._validate_character(self._char([{"outfit": "nope"}]), "x")

    def test_unknown_engine_rejected(self):
        bad = self._char([{"layer": "body", "variant": "v"}])
        bad["palette"]["body"] = {"engine": "diffusion"}
        with self.assertRaises(spec.SpriteSpecError):
            spec._validate_character(bad, "x")

    def test_bad_recolor_rejected(self):
        with self.assertRaises(spec.SpriteSpecError):
            spec._validate_character(
                self._char([{"layer": "body", "variant": "v",
                             "recolor": {"#zzzzzz": "#000000"}}]), "x")

    def test_valid_character_accepted(self):
        spec._validate_character(
            self._char([{"layer": "body", "variant": "v"}]), "x")


class TestExpandLayers(unittest.TestCase):
    def test_outfit_expands_and_sorts_by_zpos(self):
        character = {
            "frame": [64, 64],
            "palette": {"body": {"engine": "lpc", "zPos": 10},
                        "hair": {"engine": "lpc", "zPos": 80},
                        "torso": {"engine": "lpc", "zPos": 50}},
            "outfits": {"kit": [{"layer": "torso", "variant": "leather/x"}]},
            "layers": [{"layer": "hair", "variant": "h"},
                       {"outfit": "kit"},
                       {"layer": "body", "variant": "b"}],
        }
        got = compositor.expand_layers(character)
        # Sorted by zPos: body(10), torso(50), hair(80).
        self.assertEqual([l["layer"] for l in got], ["body", "torso", "hair"])
        # Source path defaults to <layer>/<variant>.png.
        body = next(l for l in got if l["layer"] == "body")
        self.assertEqual(body["source"], "body/b.png")


class TestPngIo(unittest.TestCase):
    def test_write_png_roundtrips_size(self):
        import tempfile
        arr = np.zeros((4, 6, 4), dtype=np.uint8)
        arr[..., 0] = 200  # red, opaque via alpha below
        arr[..., 3] = 255
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.png")
            self.assertEqual(pngio.write_png(path, arr), (6, 4))
            self.assertTrue(os.path.getsize(path) > 0)


class TestAlphaOver(unittest.TestCase):
    def test_opaque_source_replaces_destination(self):
        dst = np.zeros((2, 2, 4), dtype=np.uint8)
        src = np.zeros((2, 2, 4), dtype=np.uint8)
        src[..., 1] = 255  # green
        src[..., 3] = 255  # opaque
        compositor.alpha_over(dst, src)
        self.assertTrue(np.all(dst[..., 1] == 255))
        self.assertTrue(np.all(dst[..., 3] == 255))

    def test_transparent_source_leaves_destination(self):
        dst = np.zeros((2, 2, 4), dtype=np.uint8)
        dst[..., 0] = 100
        dst[..., 3] = 255
        src = np.zeros((2, 2, 4), dtype=np.uint8)  # fully transparent
        compositor.alpha_over(dst, src)
        self.assertTrue(np.all(dst[..., 0] == 100))


@unittest.skipUnless(HAVE_LPC, "Pillow (lpc engine) not installed")
class TestRender(unittest.TestCase):
    def test_knight_composites_to_universal_sheet(self):
        cast = spec.find_cast("knight-guild", ROOT)
        ch = spec.resolve_character(
            cast.character_path("knight"), cast.load_charset())
        sheet = compositor.render_sheet(ch, cast.dir)
        self.assertEqual(sheet.shape, (1344, 832, 4))
        self.assertEqual(sheet.dtype, np.uint8)
        # Compositing real layers must produce visible (non-empty) pixels.
        self.assertGreater(int(sheet[..., 3].max()), 0)
        self.assertGreater(int((sheet[..., 3] > 0).sum()), 1000)

    def test_write_png_produces_readable_file(self):
        import tempfile
        from PIL import Image
        cast = spec.find_cast("knight-guild", ROOT)
        ch = spec.resolve_character(
            cast.character_path("knight"), cast.load_charset())
        sheet = compositor.render_sheet(ch, cast.dir)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "knight.png")
            pngio.write_png(path, sheet)
            with Image.open(path) as im:
                self.assertEqual(im.size, (832, 1344))
                self.assertEqual(im.mode, "RGBA")


if __name__ == "__main__":
    unittest.main()
