"""Smoke tests: theory correctness, every spec validates, a track renders sane.

Run with:  python -m unittest discover -s tests   (or: python -m pytest)

Rendering is the slow step, so the render test uses a low sample rate and a
single loop — enough to prove the pipeline produces finite, in-range audio.
"""

import glob
import os
import unittest

import numpy as np

from vibetracks import spec, theory
from vibetracks.sequencer import _transform, render_track

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "groups", "music", "neon-frontier")
BIBLE = os.path.join(DEMO, "soundtrack.json")
TRACKS = sorted(glob.glob(os.path.join(DEMO, "tracks", "*.json")))


class TestTheory(unittest.TestCase):
    def test_reference_pitches(self):
        self.assertAlmostEqual(theory.note_to_freq("A4"), 440.0, places=3)
        self.assertEqual(theory.note_to_midi("C4"), 60)
        self.assertAlmostEqual(theory.note_to_freq("A5"), 880.0, places=3)

    def test_transpose_and_chords(self):
        self.assertEqual(theory.transpose("A4", 12), "A5")
        self.assertEqual(theory.transpose("A4", -12), "A3")
        self.assertEqual(theory.chord_notes("Am", octave=3), ["A3", "C4", "E4"])
        self.assertEqual(theory.chord_notes("C", octave=4), ["C4", "E4", "G4"])

    def test_invert_mirrors_around_pivot(self):
        # C5 is 3 semitones above A4, so its mirror is 3 below -> F#4.
        self.assertEqual(theory.invert("C5", "A4"), "F#4")
        self.assertEqual(theory.invert("A4", "A4"), "A4")  # pivot is fixed


class TestTransforms(unittest.TestCase):
    def setUp(self):
        self.motif = [["A4", 1], ["C5", 1], ["E5", 2]]

    def test_stretch_scales_durations(self):
        out = _transform(self.motif, {"stretch": 2.0})
        self.assertEqual([e[1] for e in out], [2.0, 2.0, 4.0])

    def test_retrograde_reverses(self):
        out = _transform(self.motif, {"retrograde": True})
        self.assertEqual([e[0] for e in out], ["E5", "C5", "A4"])

    def test_invert_and_rests_preserved(self):
        out = _transform([["A4", 1], [None, 1], ["C5", 1]], {"invert": "A4"})
        self.assertEqual([e[0] for e in out], ["A4", None, "F#4"])

    def test_transforms_compose(self):
        # retrograde then up an octave: reversed pitches, each +12.
        out = _transform(self.motif, {"retrograde": True, "transpose": 12})
        self.assertEqual([e[0] for e in out], ["E6", "C6", "A5"])

    def test_scale(self):
        self.assertEqual(theory.scale_notes("A minor"),
                         ["A4", "B4", "C5", "D5", "E5", "F5", "G5"])

    def test_bad_input_raises(self):
        with self.assertRaises(ValueError):
            theory.note_to_freq("H4")
        with self.assertRaises(ValueError):
            theory.chord_notes("Azz")


class TestSpecs(unittest.TestCase):
    def test_bible_loads(self):
        bible = spec.load_bible(BIBLE)
        self.assertTrue(bible.tracks)
        self.assertIn("main_theme", bible.motifs)

    def test_all_tracks_resolve(self):
        bible = spec.load_bible(BIBLE)
        self.assertTrue(TRACKS, "no track specs found")
        for path in TRACKS:
            with self.subTest(track=os.path.basename(path)):
                t = spec.resolve_track(path, bible)
                self.assertTrue(t["sections"])

    def test_validation_rejects_bad_pitch(self):
        with self.assertRaises(spec.SpecError):
            spec._validate_note_events([["H9", 1]], where="x")
        with self.assertRaises(spec.SpecError):
            spec._validate_note_events([["A4", -1]], where="x")

    def test_motif_slice_quotes_fragment(self):
        track = {"motifs": {"m": {"notes": [["A4", 1], ["C5", 1], ["E5", 1]]}},
                 "palette": {"lead": {}}}
        # A valid slice passes validation.
        spec._validate_part({"instrument": "lead", "motif": "m", "slice": [0, 2]},
                            track, where="x")
        # A malformed slice is rejected.
        with self.assertRaises(spec.SpecError):
            spec._validate_part({"instrument": "lead", "motif": "m", "slice": [0]},
                                track, where="x")


class TestGroups(unittest.TestCase):
    def test_discover_finds_demo(self):
        groups = spec.discover_groups(ROOT)
        names = [g.name for g in groups]
        self.assertIn("neon-frontier", names)

    def test_group_track_names_follow_bible_order(self):
        g = spec.find_group("neon-frontier", ROOT)
        self.assertEqual(g.track_names(),
                         ["title-theme", "exploration", "battle", "boss", "victory"])
        self.assertTrue(os.path.isfile(g.track_path("boss")))

    def test_unknown_group_raises(self):
        with self.assertRaises(spec.SpecError):
            spec.find_group("does-not-exist", ROOT)


class TestRender(unittest.TestCase):
    def test_track_renders_in_range(self):
        bible = spec.load_bible(BIBLE)
        track = spec.resolve_track(os.path.join(DEMO, "tracks", "victory.json"), bible)
        buf = render_track(track, sr=16000, loops=1)
        self.assertEqual(buf.ndim, 2)
        self.assertEqual(buf.shape[1], 2)
        self.assertGreater(buf.shape[0], 0)
        self.assertFalse(np.isnan(buf).any())
        peak = float(np.max(np.abs(buf)))
        self.assertGreater(peak, 0.1)        # not silent
        self.assertLessEqual(peak, 1.0)       # not clipping past full scale


if __name__ == "__main__":
    unittest.main()
