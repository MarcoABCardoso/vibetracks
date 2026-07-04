"""Tests for the vibesprites subsystem.

The spec loaders, validators, and the pure ``expand_layers`` resolve step always
run — they depend only on numpy. The actual composite render is gated behind
``lpc.available()`` (Pillow present + real art), mirroring how ``test_soundfont``
gates the FluidSynth render, so the suite still passes without Pillow.
"""

import os
import unittest

import numpy as np

from vibesprites import compositor, layout, lpc, pngio, scene, spec
from vibesprites.layers import ENGINES, SHEET_ENGINES

HAVE_LPC = lpc.available()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAST_DIR = os.path.join(ROOT, "sprites", "rpg-party")


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
        cast = spec.find_cast("rpg-party", ROOT)
        charset = cast.load_charset()
        self.assertIsNotNone(charset)
        for name in cast.character_names():
            ch = spec.resolve_character(cast.character_path(name), charset)
            self.assertTrue(ch["layers"])

    def test_discover_finds_the_cast(self):
        names = [c.name for c in spec.discover_casts(ROOT)]
        self.assertIn("rpg-party", names)


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

    def test_bad_assemble_rejected(self):
        with self.assertRaises(spec.SpriteSpecError):
            spec._validate_character(
                self._char([{"layer": "body", "variant": "v",
                             "assemble": {"base": "http://x"}}]), "x")  # missing color

    def test_valid_assemble_accepted(self):
        spec._validate_character(
            self._char([{"layer": "body", "variant": "v",
                         "assemble": {"base": "http://x", "color": "blue"}}]), "x")


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


class TestFindAsset(unittest.TestCase):
    """Fetch resolution — exercised without any network access."""

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in
                       (lpc.ASSETS_ENV, lpc.REMOTE_ENV, lpc.CACHE_ENV)}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_cache_hit_returns_without_fetching(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            os.environ[lpc.CACHE_ENV] = d
            dest = os.path.join(d, "body", "x.png")
            os.makedirs(os.path.dirname(dest))
            open(dest, "wb").close()
            # A cache hit must resolve without contacting the (unset) remote.
            self.assertEqual(lpc.find_asset("body/x.png"), dest)

    def test_local_checkout_wins_over_cache(self):
        import tempfile
        with tempfile.TemporaryDirectory() as assets:
            os.environ[lpc.ASSETS_ENV] = assets
            f = os.path.join(assets, "hair", "y.png")
            os.makedirs(os.path.dirname(f))
            open(f, "wb").close()
            self.assertEqual(lpc.find_asset("hair/y.png"), f)

    def test_url_source_cache_hit(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            os.environ[lpc.CACHE_ENV] = d
            # A URL source caches under its URL path; a pre-seeded cache avoids fetch.
            dest = os.path.join(d, "torso", "z.png")
            os.makedirs(os.path.dirname(dest))
            open(dest, "wb").close()
            got = lpc.find_asset("https://example.test/torso/z.png")
            self.assertEqual(got, dest)


@unittest.skipUnless(HAVE_LPC, "Pillow (lpc engine) not installed")
class TestAssemble(unittest.TestCase):
    """Assembling split-per-animation art into the classic grid — no network."""

    def test_places_present_animations_and_skips_missing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as base:
            # A local 'source' with only walk + spellcast files (as an absolute base).
            for anim, frames in (("walk", 9), ("spellcast", 7)):
                d = os.path.join(base, anim)
                os.makedirs(d)
                tile = np.zeros((4 * 64, frames * 64, 4), dtype=np.uint8)
                tile[..., :] = (20, 200, 40, 255)  # opaque green
                pngio.write_png(os.path.join(d, "x.png"), tile)
            sheet = lpc.assemble_sheet({"base": base, "color": "x"})
            self.assertEqual(sheet.shape, (layout.HEIGHT, layout.WIDTH, 4))
            wy = layout.animation_row("walk") * 64
            self.assertGreater(int(sheet[wy:wy + 256, :576, 3].min()), 0)   # walk filled
            ty = layout.animation_row("thrust") * 64
            self.assertEqual(int(sheet[ty:ty + 256, :, 3].max()), 0)        # thrust absent

    def test_no_animations_raises(self):
        import tempfile
        with tempfile.TemporaryDirectory() as base:
            with self.assertRaises(lpc.LPCError):
                lpc.assemble_sheet({"base": base, "color": "nope"})


@unittest.skipUnless(HAVE_LPC, "Pillow (lpc engine) not installed")
class TestRender(unittest.TestCase):
    def _render_mage(self):
        cast = spec.find_cast("rpg-party", ROOT)
        ch = spec.resolve_character(
            cast.character_path("mage"), cast.load_charset())
        try:  # first render fetches art; skip (don't fail) when offline
            return compositor.render_sheet(ch, cast.dir)
        except lpc.LPCError as e:
            self.skipTest(f"LPC art unavailable (offline?): {e}")

    def test_mage_composites_to_universal_sheet(self):
        sheet = self._render_mage()
        self.assertEqual(sheet.shape, (1344, 832, 4))
        self.assertEqual(sheet.dtype, np.uint8)
        # Compositing real layers must produce visible (non-empty) pixels.
        self.assertGreater(int(sheet[..., 3].max()), 0)
        self.assertGreater(int((sheet[..., 3] > 0).sum()), 1000)

    def test_write_png_produces_readable_file(self):
        import tempfile
        from PIL import Image
        sheet = self._render_mage()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mage.png")
            pngio.write_png(path, sheet)
            with Image.open(path) as im:
                self.assertEqual(im.size, (832, 1344))
                self.assertEqual(im.mode, "RGBA")


class TestSceneSpec(unittest.TestCase):
    def _scene(self, **over):
        base = {"name": "s", "size": [64, 64],
                "actors": [{"kind": "monster", "monster": "slime", "pos": [0, 0]}]}
        base.update(over)
        return base

    def test_bad_size_rejected(self):
        with self.assertRaises(scene.SceneError):
            scene._validate_scene(self._scene(size=[64]), "s")

    def test_empty_actors_rejected(self):
        with self.assertRaises(scene.SceneError):
            scene._validate_scene(self._scene(actors=[]), "s")

    def test_bad_kind_rejected(self):
        with self.assertRaises(scene.SceneError):
            scene._validate_scene(
                self._scene(actors=[{"kind": "hero", "pos": [0, 0]}]), "s")

    def test_party_actor_needs_character(self):
        with self.assertRaises(scene.SceneError):
            scene._validate_scene(
                self._scene(actors=[{"kind": "party", "pos": [0, 0]}]), "s")

    def test_monster_actor_needs_monster(self):
        with self.assertRaises(scene.SceneError):
            scene._validate_scene(
                self._scene(actors=[{"kind": "monster", "pos": [0, 0]}]), "s")

    def test_valid_scene_accepted(self):
        scene._validate_scene(self._scene(), "s")

    def test_demo_scene_loads_and_validates(self):
        path = scene.find_scene("ff3-battle", ROOT)
        data = scene.load_scene(path)
        self.assertEqual(data["name"], "ff3-battle")
        self.assertTrue(any(a["kind"] == "party" for a in data["actors"]))
        self.assertTrue(any(a["kind"] == "monster" for a in data["actors"]))

    def test_unknown_scene_raises(self):
        with self.assertRaises(scene.SceneError):
            scene.find_scene("no-such-scene", ROOT)

    def test_bestiary_lists_the_provided_monsters(self):
        best = scene.load_bestiary(ROOT)
        for name in ("slime", "pumpking", "ghost", "eyeball"):
            self.assertIn(name, best["monsters"])


class TestScenePixels(unittest.TestCase):
    def test_scale_nearest_repeats_pixels(self):
        cell = np.zeros((2, 2, 4), dtype=np.uint8)
        cell[0, 0] = (10, 20, 30, 255)
        big = scene.scale_nearest(cell, 3)
        self.assertEqual(big.shape, (6, 6, 4))
        self.assertTrue(np.all(big[0:3, 0:3] == cell[0, 0]))

    def test_scale_one_is_identity(self):
        cell = np.zeros((2, 2, 4), dtype=np.uint8)
        self.assertIs(scene.scale_nearest(cell, 1), cell)

    def test_hex_rgba_parses_alpha(self):
        self.assertTrue(np.array_equal(scene._hex_rgba("#ff8000"), [255, 128, 0, 255]))
        self.assertTrue(np.array_equal(scene._hex_rgba("#01020380"), [1, 2, 3, 128]))

    def test_background_fills_sky_and_ground(self):
        canvas = np.zeros((10, 4, 4), dtype=np.uint8)
        scene.draw_background(canvas, {"top": "#000000", "bottom": "#000000",
                                       "horizon": 0.5, "ground_top": "#00ff00",
                                       "ground_bottom": "#00ff00"})
        self.assertEqual(int(canvas[0, 0, 3]), 255)          # sky opaque
        self.assertTrue(np.all(canvas[7, :, 1] == 255))       # ground is green

    def test_no_background_leaves_transparent(self):
        canvas = np.zeros((4, 4, 4), dtype=np.uint8)
        scene.draw_background(canvas, None)
        self.assertEqual(int(canvas[..., 3].max()), 0)

    def test_shadow_darkens_and_adds_alpha(self):
        canvas = np.full((8, 8, 4), 200, dtype=np.uint8)
        canvas[..., 3] = 0
        scene.draw_shadow(canvas, 4, 4, 3, 2, alpha=0.5)
        self.assertLess(int(canvas[4, 4, 0]), 200)            # centre darkened
        self.assertGreater(int(canvas[4, 4, 3]), 0)           # gained coverage

    def test_dir_row_falls_back_to_first_row(self):
        self.assertEqual(scene._dir_row(["down", "up"], "right"), 0)
        self.assertEqual(scene._dir_row(["up", "left", "down", "right"], "right"), 3)

    def test_party_cell_slices_walk_left(self):
        sheet = np.zeros((layout.HEIGHT, layout.WIDTH, 4), dtype=np.uint8)
        row = layout.animation_row("walk") + layout.DIRECTIONS.index("left")
        sheet[row * 64:row * 64 + 64, 0:64] = (5, 6, 7, 255)
        cell = scene.party_cell(sheet, "walk", "left", 0)
        self.assertEqual(cell.shape, (64, 64, 4))
        self.assertTrue(np.all(cell == (5, 6, 7, 255)))

    def test_monster_cell_honours_frame_height(self):
        entry = {"frame": [64, 128], "dirs": ["up", "left", "down", "right"]}
        best = {"frame": [64, 64], "dirs": ["up", "left", "down", "right"]}
        sheet = np.zeros((512, 768, 4), dtype=np.uint8)  # 12x4 of 64x128
        cell = scene.monster_cell(sheet, entry, best, "right", 0)
        self.assertEqual(cell.shape, (128, 64, 4))


@unittest.skipUnless(HAVE_LPC, "Pillow (lpc engine) not installed")
class TestSceneRender(unittest.TestCase):
    """Rendering the monster half needs Pillow but no network (assets are vendored)."""

    def test_monster_only_scene_composites_over_background(self):
        spec_data = {
            "name": "t", "size": [80, 64], "upscale": 2,
            "background": {"top": "#101020", "bottom": "#101020"},
            "actors": [{"kind": "monster", "monster": "slime", "pos": [8, 8]}],
        }
        pic = scene.render_scene(spec_data, ROOT)
        self.assertEqual(pic.shape, (128, 160, 4))            # size x upscale
        self.assertGreater(int(pic[..., 3].max()), 0)         # something drawn

    def test_unknown_monster_raises(self):
        spec_data = {"name": "t", "size": [64, 64],
                     "actors": [{"kind": "monster", "monster": "dragon", "pos": [0, 0]}]}
        with self.assertRaises(scene.SceneError):
            scene.render_scene(spec_data, ROOT)


if __name__ == "__main__":
    unittest.main()
