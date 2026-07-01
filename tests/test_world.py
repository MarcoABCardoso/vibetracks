"""Tests for the Root Spec (VISION.md, the world layer) — one world, many artifacts.

These cover the mechanism that binds the Labs: a ``world.json`` both a music
bible and an art bible ``extends``, and the *cross-Lab* coherence check that a
cross-modal motif's face exists in every medium it claims. Content-specific
assertions use the bundled ``emberhold`` world, which spans both media.
"""

import json
import os
import shutil
import tempfile
import unittest

import labs.__main__ as dispatcher
from labkit import world as world_mod
from labkit.registry import LABS
from labkit.specbase import SpecError
from labkit.world import check_spec_refs, check_world, discover_worlds, load_world

import vibetracks.spec as vspec
import pixeltracks.spec as pspec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMBERHOLD = os.path.join(ROOT, "worlds", "emberhold", "world.json")


def _cwd(root):
    """Context-free helper: check_world/discover_worlds resolve paths from cwd."""
    return root


class TestWorldLoads(unittest.TestCase):
    def test_emberhold_world_loads(self):
        w = load_world(EMBERHOLD)
        self.assertEqual(w.name, "Emberhold")
        self.assertIn("ember", w.motifs)
        self.assertIn("the-keep", w.entities)
        self.assertIn("hope", w.meaning)

    def test_cross_modal_motif_has_both_faces(self):
        w = load_world(EMBERHOLD)
        faces = w.motifs["ember"]["faces"]
        self.assertIn("vibetracks", faces)   # a melody
        self.assertIn("pixeltracks", faces)  # a shape

    def test_bad_meaning_ref_rejected(self):
        # A motif tagged with an undeclared meaning is caught at load.
        import json
        import tempfile
        data = {"name": "X", "meaning": {},
                "motifs": {"m": {"meaning": "ghost",
                                 "faces": {"vibetracks": {"group": "g", "motif": "t"}}}}}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "world.json")
            with open(p, "w") as f:
                json.dump(data, f)
            with self.assertRaises(SpecError):
                load_world(p)


class TestCoherence(unittest.TestCase):
    def setUp(self):
        self._old = os.getcwd()
        os.chdir(ROOT)

    def tearDown(self):
        os.chdir(self._old)

    def test_emberhold_is_coherent(self):
        w = load_world(EMBERHOLD)
        self.assertEqual(check_world(w), [])

    def test_discover_finds_emberhold(self):
        names = [n for n, _ in discover_worlds()]
        self.assertIn("emberhold", names)

    def test_drifted_face_is_caught(self):
        # If the music bible loses the motif the world names, coherence fails.
        w = load_world(EMBERHOLD)
        w.motifs["ember"]["faces"]["vibetracks"]["motif"] = "ghost_theme"
        errs = check_world(w)
        self.assertTrue(errs)
        self.assertIn("ghost_theme", errs[0])

    def test_missing_transform_target_is_caught(self):
        w = load_world(EMBERHOLD)
        w.motifs["ember"]["transforms"]["fallen"]["pixeltracks"]["sprite"] = "nope"
        errs = check_world(w)
        self.assertTrue(any("nope" in e for e in errs))


class TestBibleExtendsWorld(unittest.TestCase):
    """Both Labs' emberhold bibles descend from the same Root Spec."""

    def test_music_bible_resolves_world(self):
        b = vspec.load_bible(os.path.join(ROOT, "groups", "music", "emberhold",
                                          "soundtrack.json"))
        self.assertIsNotNone(b.world)
        self.assertEqual(b.world.name, "Emberhold")
        self.assertIn("ember_theme", b.motifs)  # the music face exists

    def test_art_bible_resolves_world(self):
        b = pspec.load_bible(os.path.join(ROOT, "groups", "sprites", "emberhold",
                                          "artbook.json"))
        self.assertIsNotNone(b.world)
        self.assertEqual(b.world.name, "Emberhold")
        self.assertIn("crest", b.motifs)         # the art face exists

    def test_both_bibles_share_one_world(self):
        m = vspec.load_bible(os.path.join(ROOT, "groups", "music", "emberhold",
                                          "soundtrack.json"))
        a = pspec.load_bible(os.path.join(ROOT, "groups", "sprites", "emberhold",
                                          "artbook.json"))
        self.assertEqual(os.path.abspath(m.world.path),
                         os.path.abspath(a.world.path))

    def test_worldless_bible_still_loads(self):
        # A bible without `extends` keeps working (backward compatible).
        b = pspec.load_bible(os.path.join(ROOT, "groups", "sprites", "mossy-hollow",
                                          "artbook.json"))
        self.assertIsNone(b.world)


class TestLeafSpecRefs(unittest.TestCase):
    """Leaf specs (a track / a sprite) reference the world's meaning + entities.

    The Phase-2 finisher: the *palette of meaning* and named entities, until now
    only nameable by the world's own motifs, are inherited down to the specs the
    AI actually authors — with the same "cannot drift" guarantee the faces get.
    """

    def setUp(self):
        self.world = load_world(EMBERHOLD)

    def test_valid_meaning_and_entity_resolve(self):
        m, ents = check_spec_refs({"meaning": "hope", "entity": "the-keep"},
                                  self.world, "spec")
        self.assertEqual(m, "hope")
        self.assertEqual(ents, ["the-keep"])

    def test_entities_list_takes_precedence_over_entity(self):
        _, ents = check_spec_refs(
            {"entities": ["the-keep", "the-shadow"], "entity": "ignored"},
            self.world, "spec")
        self.assertEqual(ents, ["the-keep", "the-shadow"])

    def test_no_refs_is_a_noop_even_without_a_world(self):
        self.assertEqual(check_spec_refs({}, None, "spec"), (None, []))

    def test_unknown_meaning_rejected(self):
        with self.assertRaises(SpecError):
            check_spec_refs({"meaning": "ghost"}, self.world, "spec")

    def test_comment_key_is_not_a_selectable_meaning(self):
        # A world's `_comment` documentation key must not validate as a tag.
        with self.assertRaises(SpecError):
            check_spec_refs({"meaning": "_comment"}, self.world, "spec")

    def test_unknown_entity_rejected(self):
        with self.assertRaises(SpecError):
            check_spec_refs({"entity": "nobody"}, self.world, "spec")

    def test_entities_must_be_a_list(self):
        with self.assertRaises(SpecError):
            check_spec_refs({"entities": "the-keep"}, self.world, "spec")

    def test_reference_without_a_world_is_an_error(self):
        # You cannot point at a world you do not descend from.
        with self.assertRaises(SpecError):
            check_spec_refs({"meaning": "hope"}, None, "spec")

    def test_emberhold_track_carries_its_meaning(self):
        t = vspec.resolve_track(
            os.path.join(ROOT, "groups", "music", "emberhold", "tracks", "siege.json"))
        self.assertEqual(t["meaning"], "hostile")
        self.assertEqual(t["entities"], ["the-shadow"])

    def test_emberhold_sprite_carries_its_meaning(self):
        s = pspec.resolve_sprite(
            os.path.join(ROOT, "groups", "sprites", "emberhold", "sprites",
                         "dark-knight.json"))
        self.assertEqual(s["meaning"], "hostile")
        self.assertEqual(s["entities"], ["the-shadow"])

    def test_fmt_refs(self):
        self.assertEqual(world_mod.fmt_refs(None, []), "")
        self.assertEqual(world_mod.fmt_refs("hope", ["the-keep"]),
                         "  [means hope; about the-keep]")


class TestNewWorld(unittest.TestCase):
    """`python -m labs new-world` scaffolds a coherent cross-modal starting point.

    A world-scale project should start coherent: a world plus one group per Lab,
    each pre-wired to `extends` it, validating out of the box (empty motifs — a
    cross-modal motif is added once each medium has a face to bind).
    """

    def setUp(self):
        self._old = os.getcwd()
        self._tmp = tempfile.mkdtemp()
        os.chdir(self._tmp)

    def tearDown(self):
        os.chdir(self._old)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_scaffolds_world_and_wired_groups(self):
        rc = dispatcher.main(["new-world", "testrealm", "--title", "Test Realm"])
        self.assertEqual(rc, 0)
        w = load_world(os.path.join("worlds", "testrealm", "world.json"))
        self.assertEqual(w.name, "Test Realm")
        self.assertIn("hero", w.meaning)
        # A wired group bible per Lab, each `extends`-ing the world.
        for lab in LABS:
            bpath = os.path.join(lab.assets_dir, "testrealm", lab.bible_file)
            self.assertTrue(os.path.isfile(bpath), bpath)
            with open(bpath) as f:
                self.assertIn("extends", json.load(f))
        # Coherent from the start (no dangling faces — motifs is empty).
        self.assertEqual(check_world(w), [])

    def test_scaffolded_bibles_resolve_the_world(self):
        dispatcher.main(["new-world", "testrealm"])
        mb = vspec.load_bible(os.path.join("groups", "music", "testrealm",
                                           "soundtrack.json"))
        ab = pspec.load_bible(os.path.join("groups", "sprites", "testrealm",
                                           "artbook.json"))
        self.assertIsNotNone(mb.world)
        self.assertIsNotNone(ab.world)
        self.assertEqual(os.path.abspath(mb.world.path),
                         os.path.abspath(ab.world.path))

    def test_world_only_skips_groups(self):
        rc = dispatcher.main(["new-world", "lonely", "--world-only"])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(os.path.join("worlds", "lonely", "world.json")))
        self.assertFalse(os.path.isdir(os.path.join("groups", "music", "lonely")))

    def test_media_flag_limits_scaffolded_labs(self):
        rc = dispatcher.main(["new-world", "just-music", "--media", "vibetracks"])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isdir(os.path.join("groups", "music", "just-music")))
        self.assertFalse(os.path.isdir(os.path.join("groups", "sprites", "just-music")))

    def test_refuses_to_clobber_without_force(self):
        self.assertEqual(dispatcher.main(["new-world", "dup", "--world-only"]), 0)
        self.assertEqual(dispatcher.main(["new-world", "dup", "--world-only"]), 1)


if __name__ == "__main__":
    unittest.main()
