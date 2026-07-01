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
DEMO = os.path.join(ROOT, "groups", "sprites", "tiny-knight")
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
        # Six posed frames of the articulated swing on a 28x24 canvas.
        self.assertEqual(out["atlas"]["frame_count"], 6)
        self.assertTrue(out["atlas"]["loop"])
        self.assertEqual(out["sheet"].shape, (24, 28 * 6, 4))

    def test_pivoted_rotation_swings_about_a_joint(self):
        from pixeltracks.raster import draw_grid_rotated
        # A 1x3 horizontal bar; pivot at its left end. A 90 turn should swing the
        # far end from +x down to +y (clockwise) while the pinned end stays put.
        rows = ["xxx"]
        legend = {"x": (255, 255, 255, 255)}
        canvas = new_canvas(8, 8)
        draw_grid_rotated(canvas, rows, legend, 90, pivot=[0, 0], at=[4, 4])
        self.assertEqual(tuple(canvas[4, 4]), (255, 255, 255, 255))  # pinned joint
        self.assertEqual(tuple(canvas[6, 4]), (255, 255, 255, 255))  # tip swung to +y
        self.assertEqual(canvas[4, 6, 3], 0)                          # no longer along +x

    def test_arbitrary_rotation_validates(self):
        bible = spec.load_bible(BIBLE)
        layer = {"shape": "sword", "rotate": 37, "pivot": [1, 8], "at": [10, 10]}
        sprite = {"motifs": bible.motifs}
        names = set(bible.resolved_palette())
        spec._validate_layer(layer, sprite, names, where="t")  # should not raise

    def test_skew_leans_a_vertical_bar(self):
        from pixeltracks.raster import affine_matrix, draw_grid_affine
        rows, legend = ["x", "x", "x"], {"x": (255, 255, 255, 255)}
        # No skew: a vertical bar stays directly above its pinned base.
        c0 = new_canvas(9, 9)
        draw_grid_affine(c0, rows, legend, affine_matrix(0), pivot=[0, 2], at=[4, 6])
        self.assertEqual(c0[6, 4, 3], 255)   # base pinned
        self.assertEqual(c0[4, 4, 3], 255)   # top directly above
        # Positive horizontal skew leans the top off to the side (the "lean").
        c1 = new_canvas(9, 9)
        draw_grid_affine(c1, rows, legend, affine_matrix(0, skew=(1.0, 0.0)),
                         pivot=[0, 2], at=[4, 6])
        self.assertEqual(c1[6, 4, 3], 255)   # base still pinned
        self.assertEqual(c1[4, 4, 3], 0)     # top no longer directly above
        self.assertEqual(c1[4, 2, 3], 255)   # it moved sideways with depth

    def test_squash_narrows_width(self):
        from pixeltracks.raster import affine_matrix, draw_grid_affine
        rows, legend = ["xxxx"], {"x": (255, 255, 255, 255)}
        c = new_canvas(12, 6)
        draw_grid_affine(c, rows, legend, affine_matrix(0, scale=(0.5, 1.0)),
                         pivot=[0, 0], at=[2, 3])
        self.assertLessEqual(int((c[..., 3] > 0).sum()), 3)  # 4px foreshortened to ~2

    def test_skew_and_squash_validate(self):
        bible = spec.load_bible(BIBLE)
        sprite = {"motifs": bible.motifs}
        names = set(bible.resolved_palette())
        ok = {"shape": "sword", "skew": [-0.2, 0], "squash": [0.9, 1.0],
              "pivot": [1, 8], "at": [5, 5]}
        spec._validate_layer(ok, sprite, names, where="t")   # should not raise
        with self.assertRaises(spec.SpecError):
            spec._validate_layer({"shape": "sword", "squash": [0, 1.0]},
                                 sprite, names, where="t")

    def test_png_has_signature_and_upscale(self):
        canvas = new_canvas(2, 2)
        canvas[0, 0] = (10, 20, 30, 255)
        data = encode_png(upscale(canvas, 4))
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(upscale(canvas, 4).shape, (8, 8, 4))


EMBER = os.path.join(ROOT, "groups", "sprites", "emberhold")


class TestSkeleton(unittest.TestCase):
    def test_attach_meets_parent_anchor(self):
        motifs = {
            "trunk": {"legend": {"a": "steel"}, "anchors": {"top": [1, 0], "bot": [1, 3]},
                      "pixels": ["aaa", "aaa", "aaa", "aaa"]},
            "limb": {"legend": {"a": "steel"}, "anchors": {"root": [0, 0]},
                     "pixels": ["aa", "aa"]},
        }
        bones = [
            {"name": "t", "shape": "trunk", "pivot": "top", "at": [10, 10]},
            {"name": "l", "shape": "limb", "pivot": "root",
             "attach": {"to": "t", "anchor": "bot"}},
        ]
        layers = spec.resolve_skeleton(bones, motifs)
        limb = next(L for L in layers if L["name"] == "l")
        # trunk 'top' pinned at (10,10); 'bot' sits 3px below -> world (10,13);
        # the limb's 'root' is pinned there.
        self.assertEqual([round(v) for v in limb["at"]], [10, 13])
        # bones lower to numeric pivot/at so the rest of the pipeline is unchanged.
        for L in layers:
            self.assertTrue(all(isinstance(v, (int, float)) for v in L["pivot"] + L["at"]))

    def test_unknown_anchor_raises(self):
        motifs = {"m": {"legend": {"a": "steel"}, "anchors": {"a": [0, 0]}, "pixels": ["a"]}}
        with self.assertRaises(spec.SpecError):
            spec.resolve_skeleton([{"name": "x", "shape": "m", "pivot": "nope", "at": [0, 0]}],
                                  motifs)

    def test_battle_sprite_is_one_connected_piece(self):
        from pixeltracks import inspect
        s = spec.resolve_sprite(os.path.join(EMBER, "sprites", "knight-battle.json"))
        geo = inspect.geometry(s, 0)
        self.assertEqual(len(geo["solid"]), 1, geo["warnings"])
        self.assertTrue(all(r["ok"] for r in inspect.run_checks(s, 0)))


class TestCompositeFlip(unittest.TestCase):
    def test_flip_h_mirrors_frame(self):
        s = spec.resolve_sprite(os.path.join(EMBER, "sprites", "knight-battle.json"))
        base = composite_frame(s, s["frames"][0])
        mirrored = composite_frame(dict(s, flip="h"), s["frames"][0])
        self.assertTrue(np.array_equal(mirrored, base[:, ::-1]))

    def test_dark_knight_battle_faces_left(self):
        # the boss is the hero's rig mirrored; its composite is the un-flipped
        # frame reversed, so its weapon-side mass lands on the opposite half.
        s = spec.resolve_sprite(os.path.join(EMBER, "sprites", "dark-knight-battle.json"))
        self.assertEqual(s["flip"], "h")
        from pixeltracks import inspect
        self.assertTrue(all(r["ok"] for r in inspect.run_checks(s, 0)))


class TestInspect(unittest.TestCase):
    def _knight(self):
        return spec.resolve_sprite(os.path.join(EMBER, "sprites", "knight.json"))

    def test_ascii_dump_has_grid_and_legend(self):
        from pixeltracks import inspect
        dump = inspect.ascii_dump(self._knight(), 0)
        self.assertIn("legend:", dump)
        self.assertIn("#=outline", dump)   # outline always renders as '#'

    def test_geometry_flags_disconnected_and_floating(self):
        from pixeltracks import inspect
        s = self._knight()
        s["frames"][0]["layers"].append(
            {"name": "floater", "rect": {"at": [0, 0], "size": [3, 3], "color": "gold"}})
        geo = inspect.geometry(s, 0)
        self.assertTrue(any("disconnected" in w or "FLOATING" in w for w in geo["warnings"]))

    def test_checks_detect_violation(self):
        from pixeltracks import inspect
        s = self._knight()
        s["checks"] = [{"rule": "above", "layer": "body", "of": "sword"}]  # false by design
        res = inspect.run_checks(s, 0)
        self.assertFalse(res[0]["ok"])


class TestThinRotation(unittest.TestCase):
    def test_thin_line_rotates_without_gaps(self):
        from pixeltracks import inspect
        from pixeltracks.raster import affine_matrix, draw_grid_affine
        rows = ["a"] * 8                       # 1px-wide, 8-tall blade
        legend = {"a": (255, 255, 255, 255)}
        c = new_canvas(24, 24)
        draw_grid_affine(c, rows, legend, affine_matrix(56), pivot=[0, 7], at=[12, 12])
        solid = [n for n in inspect._components(c[:, :, 3] > 0) if n >= inspect.SPECK]
        self.assertEqual(len(solid), 1)        # supersampling keeps it one piece


if __name__ == "__main__":
    unittest.main()
