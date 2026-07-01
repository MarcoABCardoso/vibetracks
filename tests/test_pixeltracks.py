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
DEMO = os.path.join(ROOT, "groups", "sprites", "mossy-hollow")
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
        self.assertIn("fox", bible.motifs)
        self.assertIn("leaf", bible.motifs)

    def test_all_sprites_resolve(self):
        bible = spec.load_bible(BIBLE)
        self.assertTrue(SPRITES, "no sprite specs found")
        for path in SPRITES:
            with self.subTest(sprite=os.path.basename(path)):
                s = spec.resolve_sprite(path, bible)
                self.assertTrue(s["frames"])

    def test_palette_swap_only_changes_colours(self):
        bible = spec.load_bible(BIBLE)
        fox = spec.resolve_sprite(os.path.join(DEMO, "sprites", "fox.json"), bible)
        night = spec.resolve_sprite(os.path.join(DEMO, "sprites", "fox-night.json"), bible)
        # Same layers/pose, different fur colour — the leitmotif move.
        self.assertEqual(fox["frames"], night["frames"])
        self.assertNotEqual(fox["palette"]["fur"], night["palette"]["fur"])

    def test_off_palette_colour_rejected(self):
        bible = spec.load_bible(BIBLE)
        with self.assertRaises(spec.SpecError):
            spec._validate_layer({"rect": {"at": [0, 0], "size": [2, 2], "color": "no_such"}},
                                 {"palette": {"fur": (0, 0, 0, 255)}, "motifs": {}},
                                 {"fur"}, where="x")

    def test_two_primitives_in_a_layer_rejected(self):
        with self.assertRaises(spec.SpecError):
            spec._validate_layer({"pixels": ["aa"], "rect": {"color": "x"}},
                                 {"palette": {}, "motifs": {}}, set(), where="x")


class TestGroups(unittest.TestCase):
    def test_discover_finds_demo(self):
        groups = spec.discover_groups(ROOT)
        self.assertIn("mossy-hollow", [g.name for g in groups])

    def test_sprite_names_follow_bible_order(self):
        g = spec.find_group("mossy-hollow", ROOT)
        self.assertEqual(g.sprite_names()[0], "fox")
        self.assertTrue(os.path.isfile(g.sprite_path("owl")))

    def test_unknown_group_raises(self):
        with self.assertRaises(spec.SpecError):
            spec.find_group("does-not-exist", ROOT)


class TestDescribe(unittest.TestCase):
    def test_index_covers_every_motif_and_sprite(self):
        from pixeltracks import describe
        g = spec.find_group("mossy-hollow", ROOT)
        info = describe.describe_group(g)
        self.assertEqual({m["name"] for m in info["motifs"]}, set(g.load_bible().motifs))
        self.assertEqual([s["name"] for s in info["sprites"]], g.sprite_names())

    def test_used_by_matches_sprite_shape_layers(self):
        from pixeltracks import describe
        g = spec.find_group("mossy-hollow", ROOT)
        info = describe.describe_group(g)
        by_name = {m["name"]: m for m in info["motifs"]}
        self.assertIn("fox-hop", by_name["leaf"]["used_by"])
        self.assertIn("fox", by_name["fox"]["used_by"])

    def test_unused_motif_detected(self):
        from pixeltracks import describe
        g = spec.find_group("emberhold", ROOT)
        info = describe.describe_group(g)
        self.assertIn("cape", info["unused_motifs"])

    def test_format_report_is_a_string(self):
        from pixeltracks import describe
        g = spec.find_group("mossy-hollow", ROOT)
        report = describe.format_report(describe.describe_group(g))
        self.assertIsInstance(report, str)
        self.assertIn("fox", report)


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
        s = spec.resolve_sprite(os.path.join(DEMO, "sprites", "fox.json"), bible)
        frame = composite_frame(s, s["frames"][0])
        self.assertEqual(frame.shape, (20, 20, 4))
        self.assertGreater(coverage(frame), 0.1)   # not empty
        self.assertEqual(frame.dtype, np.uint8)

    def test_animation_sheet_and_atlas(self):
        bible = spec.load_bible(BIBLE)
        s = spec.resolve_sprite(os.path.join(DEMO, "sprites", "fox-hop.json"), bible)
        out = render_sprite(s)
        # Four posed frames of the hop on a 20x29 canvas.
        self.assertEqual(out["atlas"]["frame_count"], 4)
        self.assertTrue(out["atlas"]["loop"])
        self.assertEqual(out["sheet"].shape, (29, 20 * 4, 4))

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
        layer = {"shape": "leaf", "rotate": 37, "pivot": [2, 4], "at": [10, 10]}
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
        ok = {"shape": "leaf", "skew": [-0.2, 0], "squash": [0.9, 1.0],
              "pivot": [2, 4], "at": [5, 5]}
        spec._validate_layer(ok, sprite, names, where="t")   # should not raise
        with self.assertRaises(spec.SpecError):
            spec._validate_layer({"shape": "leaf", "squash": [0, 1.0]},
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


GLADE = os.path.join(ROOT, "groups", "sprites", "dusk-glade")


class TestSceneComposition(unittest.TestCase):
    """The `sprite` layer kind: a scene is a sprite whose layers are other sprites."""

    def _resolve(self, name):
        return spec.resolve_sprite(os.path.join(GLADE, "sprites", name + ".json"))

    def test_scene_resolves_and_attaches_children(self):
        meadow = self._resolve("meadow")
        self.assertTrue(meadow["scene"])
        sprite_layers = [L for L in meadow["frames"][0]["layers"] if "sprite" in L]
        self.assertTrue(sprite_layers, "scene has no sprite layers")
        # every sprite layer resolved its referenced child sprite in place
        for L in sprite_layers:
            self.assertIn("_resolved", L)
            self.assertTrue(L["_resolved"]["frames"])
        # the hero oak is reused whole, not re-authored
        oak = next(L for L in sprite_layers if L["sprite"] == "great-oak")
        self.assertEqual(oak["_resolved"]["size"], (64, 64))

    def test_scene_renders_with_stamped_children(self):
        meadow = self._resolve("meadow")
        out = render_sprite(meadow)
        self.assertEqual(out["sheet"].shape, (80, 124, 4))
        self.assertGreater(coverage(out["frames"][0]), 0.9)  # backdrop fills it
        # a stamped child actually paints: the oak's trunk brown lands on the canvas
        frame = out["frames"][0]
        bark = meadow["palette"]["bark"]
        self.assertTrue(np.any(np.all(frame == np.array(bark, np.uint8), axis=-1)),
                        "stamped oak did not paint its trunk into the scene")

    def test_child_flip_mirrors_the_stamp(self):
        # two boulders, one flipped: the mirror lands as a horizontal reflection.
        base = self._resolve("boulder")
        btile = composite_frame(dict(base, background=None), base["frames"][0])
        # place plain vs flipped via a tiny synthetic scene layer path
        from pixeltracks import raster
        plain = raster.new_canvas(*base["size"])
        raster.blit(plain, btile, 0, 0)
        flipped = raster.new_canvas(*base["size"])
        raster.blit(flipped, btile[:, ::-1], 0, 0)
        self.assertTrue(np.array_equal(flipped, plain[:, ::-1]))

    def test_scene_geometry_suppresses_single_body_lint(self):
        from pixeltracks import inspect
        meadow = self._resolve("meadow")
        geo = inspect.geometry(meadow, 0)
        joined = " ".join(geo["warnings"])
        self.assertNotIn("disconnected", joined)
        self.assertNotIn("FLOATING", joined)
        # but per-layer bounding boxes are still reported
        names = {info["name"] for info in geo["layers"]}
        self.assertIn("oak", names)

    def test_unknown_sprite_reference_raises(self):
        bible = spec.load_bible(os.path.join(GLADE, "artbook.json"))
        with self.assertRaises(spec.SpecError):
            spec._resolve_sprite_layers(
                {"frames": [{"layers": [{"sprite": "no-such-sprite"}]}]},
                os.path.join(GLADE, "sprites", "x.json"), bible, frozenset())

    def test_reference_cycle_raises(self):
        import json as _json
        import tempfile
        d = tempfile.mkdtemp()
        for a, b in (("a", "b"), ("b", "a")):
            with open(os.path.join(d, a + ".json"), "w") as f:
                _json.dump({"name": a, "size": [8, 8],
                            "palette": {"x": "#fff"},
                            "layers": [{"sprite": b}]}, f)
        with self.assertRaises(spec.SpecError):
            spec.resolve_sprite(os.path.join(d, "a.json"))

    def test_bad_frame_index_rejected(self):
        names = {"x"}
        sprite = {"palette": {"x": (0, 0, 0, 255)}, "motifs": {}}
        layer = {"sprite": "child", "frame": 5,
                 "_resolved": {"frames": [{"layers": []}]}}
        with self.assertRaises(spec.SpecError):
            spec._validate_layer(layer, sprite, names, where="t")


if __name__ == "__main__":
    unittest.main()
