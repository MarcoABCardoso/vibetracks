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
from vibetracks.sequencer import render_track

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIBLE = os.path.join(ROOT, "soundtrack.json")
TRACKS = sorted(glob.glob(os.path.join(ROOT, "tracks", "*.json")))


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


class TestRender(unittest.TestCase):
    def test_track_renders_in_range(self):
        bible = spec.load_bible(BIBLE)
        track = spec.resolve_track(os.path.join(ROOT, "tracks", "victory.json"), bible)
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
