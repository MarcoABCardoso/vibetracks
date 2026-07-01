"""Tests for the Root Spec (VISION.md Phase 2) — one world, many artifacts.

These cover the mechanism that binds the Labs: a ``world.json`` both a music
bible and an art bible ``extends``, and the *cross-Lab* coherence check that a
cross-modal motif's face exists in every medium it claims. Content-specific
assertions use the bundled ``emberhold`` world, which spans both media.
"""

import os
import unittest

from labkit import world as world_mod
from labkit.specbase import SpecError
from labkit.world import check_world, discover_worlds, load_world

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


if __name__ == "__main__":
    unittest.main()
