"""Tests for the vibesprites subsystem.

The spec loaders, validators, and the pure ``expand_layers`` resolve step always
run — they depend only on numpy. The actual composite render is gated behind
``lpc.available()`` (Pillow present + real art), mirroring how ``test_soundfont``
gates the FluidSynth render, so the suite still passes without Pillow.
"""

import os
import unittest

import numpy as np

from vibesprites import atlas, compositor, layout, lpc, pngio, spec
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

    def test_compiled_spec_is_self_contained_and_json_friendly(self):
        import json
        cast = spec.find_cast("rpg-party", ROOT)
        ch = spec.resolve_character(cast.character_path(
            cast.character_names()[0]), cast.load_charset())
        out = spec.compiled_spec(ch)
        # No 'extends' — the charset is already folded in.
        self.assertNotIn("extends", out)
        # animations flattened from (name, frames, dirs) tuples back to names.
        self.assertEqual(out["animations"],
                         [name for name, _f, _d in ch["animations"]])
        self.assertTrue(all(isinstance(a, str) for a in out["animations"]))
        self.assertEqual(out["name"], ch["name"])
        self.assertEqual(out["layers"], ch["layers"])
        # Round-trips through JSON (nothing but plain lists/dicts/str/num).
        json.loads(json.dumps(out))


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
                             "assemble": {"color": "blue"}}]), "x")  # missing base

    def test_valid_assemble_accepted(self):
        spec._validate_character(
            self._char([{"layer": "body", "variant": "v",
                         "assemble": {"base": "http://x", "color": "blue"}}]), "x")

    def test_colorless_assemble_accepted(self):
        # Recolorable single-sheet convention (bodies/armour): base, no color.
        spec._validate_character(
            self._char([{"layer": "body", "variant": "v",
                         "assemble": {"base": "http://x"}}]), "x")


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


class TestAtlas(unittest.TestCase):
    """The frame map is pure (derived from ``layout``), so it always runs."""

    def setUp(self):
        self.atlas = atlas.build_atlas("hero.png")

    def test_header_matches_layout(self):
        self.assertEqual(self.atlas["image"], "hero.png")
        self.assertEqual(self.atlas["frame_size"], [layout.FRAME, layout.FRAME])
        self.assertEqual(self.atlas["sheet_size"], [layout.WIDTH, layout.HEIGHT])
        self.assertEqual(self.atlas["direction_order"], list(layout.DIRECTIONS))

    def test_every_animation_row_matches_layout(self):
        for name, cols, dirs in layout.ANIMATIONS:
            block = self.atlas["animations"][name]
            self.assertEqual(block["row"], layout.animation_row(name))
            self.assertEqual(block["rows"], dirs)
            self.assertEqual(block["frames"], cols)

    def test_frame_count_is_the_ragged_total(self):
        # Ragged sheet: sum of cols*dirs, NOT a full COLS*ROWS grid.
        expected = sum(cols * dirs for _, cols, dirs in layout.ANIMATIONS)
        self.assertEqual(len(self.atlas["frames"]), expected)
        self.assertLess(expected, layout.COLS * layout.ROWS)

    def test_directional_frame_rect(self):
        # walk = rows 8-11 (up/left/down/right); "down" is the 3rd facing (row 10).
        rect = self.atlas["frames"]["walk.down.3"]
        self.assertEqual(rect, {"x": 3 * 64, "y": 10 * 64, "w": 64, "h": 64})

    def test_single_row_block_is_not_split_by_direction(self):
        # hurt is one shared row (20), keyed without a direction segment.
        self.assertEqual(self.atlas["animations"]["hurt"]["directions"],
                         [atlas.NON_DIRECTIONAL])
        self.assertIn("hurt.0", self.atlas["frames"])
        self.assertNotIn("hurt.down.0", self.atlas["frames"])
        self.assertEqual(self.atlas["frames"]["hurt.5"],
                         {"x": 5 * 64, "y": 20 * 64, "w": 64, "h": 64})


class TestAnimationCatalog(unittest.TestCase):
    """The expanded universal catalog + selectable animation sets."""

    def test_catalog_has_expanded_poses(self):
        names = [n for n, *_ in layout.ANIMATION_CATALOG]
        for pose in ("jump", "climb", "run", "idle", "sit", "emote"):
            self.assertIn(pose, names)

    def test_canonical_rows_match_generator_offsets(self):
        # Verified against the modern generator's ANIMATION_OFFSETS.
        self.assertEqual(layout.animation_row("walk"), 8)
        self.assertEqual(layout.animation_row("hurt"), 20)
        self.assertEqual(layout.animation_row("climb"), 21)
        self.assertEqual(layout.animation_row("jump"), 26)
        self.assertEqual(layout.animation_row("run"), 38)

    def test_default_is_the_classic_six(self):
        self.assertEqual(layout.resolve_animations(), layout.ANIMATIONS)
        self.assertEqual(layout.sheet_size(layout.ANIMATIONS), (832, 1344))

    def test_resolve_returns_canonical_order(self):
        got = layout.resolve_animations(["jump", "walk"])  # given out of order
        self.assertEqual([n for n, *_ in got], ["walk", "jump"])

    def test_unknown_animation_rejected(self):
        with self.assertRaises(KeyError):
            layout.resolve_animations(["moonwalk"])

    def test_expanded_sheet_is_taller(self):
        anims = layout.resolve_animations(
            list(layout.CLASSIC_ANIMATIONS) + ["jump", "climb"])
        self.assertEqual(layout.sheet_size(anims), (832, (26 + 4) * 64))


class TestExpandedAtlas(unittest.TestCase):
    def test_atlas_places_jump_at_canonical_row(self):
        anims = layout.resolve_animations(["walk", "jump"])
        a = atlas.build_atlas("hero.png", anims)
        self.assertEqual(a["animations"]["jump"]["row"], 26)
        self.assertEqual(a["animations"]["jump"]["frames"], 5)
        self.assertEqual(a["frames"]["jump.down.0"],
                         {"x": 0, "y": (26 + 2) * 64, "w": 64, "h": 64})
        self.assertEqual(a["sheet_size"], [832, (26 + 4) * 64])
        self.assertNotIn("spellcast", a["animations"])  # not selected


class TestAnimationSelection(unittest.TestCase):
    def test_defaults_to_classic_without_an_animation_set(self):
        # A character that names no animations (and whose charset names none)
        # falls back to the classic six.
        self.assertEqual(layout.resolve_animations(None), layout.ANIMATIONS)

    def test_character_inherits_charset_animation_set(self):
        # rpg-party opts the whole cast into the expanded catalog, incl combat_idle.
        cs = spec.load_charset(os.path.join(CAST_DIR, spec.CHARSET_FILE))
        ch = spec.resolve_character(
            os.path.join(CAST_DIR, "characters", "warrior.json"), cs)
        names = [n for n, _f, _d in ch["animations"]]
        self.assertIn("combat_idle", names)
        self.assertIn("jump", names)

    def test_bad_animation_name_in_charset_rejected(self):
        with self.assertRaises(spec.SpriteSpecError):
            spec._validate_charset(spec.Charset(path="x", animations=["boogie"]))


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
            return ch, compositor.render_sheet(ch, cast.dir)
        except lpc.LPCError as e:
            self.skipTest(f"LPC art unavailable (offline?): {e}")

    def test_mage_composites_to_universal_sheet(self):
        ch, sheet = self._render_mage()
        # Sheet is sized to the character's selected animation set (rpg-party opts
        # into the expanded catalog through combat_idle), not the classic default.
        w, h = layout.sheet_size(ch["animations"])
        self.assertEqual(sheet.shape, (h, w, 4))
        self.assertEqual(sheet.dtype, np.uint8)
        # Compositing real layers must produce visible (non-empty) pixels.
        self.assertGreater(int(sheet[..., 3].max()), 0)
        self.assertGreater(int((sheet[..., 3] > 0).sum()), 1000)

    def test_write_png_produces_readable_file(self):
        import tempfile
        from PIL import Image
        ch, sheet = self._render_mage()
        w, h = layout.sheet_size(ch["animations"])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mage.png")
            pngio.write_png(path, sheet)
            with Image.open(path) as im:
                self.assertEqual(im.size, (w, h))
                self.assertEqual(im.mode, "RGBA")


if __name__ == "__main__":
    unittest.main()
