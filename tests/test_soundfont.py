"""Tests for the Stage 2 soundfont engine.

The schedule builders and spec validation are pure and always run. The actual
FluidSynth render is gated behind ``soundfont.available()`` so the suite still
passes in environments without FluidSynth or a soundfont installed.
"""

import os
import unittest

import numpy as np

from vibetracks import soundfont, spec
from vibetracks.instruments import ENGINES, PART_ENGINES
from vibetracks.sequencer import _chord_schedule, _melody_schedule

HAVE_SF = soundfont.available()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSchedules(unittest.TestCase):
    def test_melody_schedule_lays_notes_end_to_end(self):
        sr, bpm = 44100, 120  # 0.5 s per beat
        sched = _melody_schedule([["C4", 1], [None, 1], ["E4", 2]], bpm, sr)
        # The rest is skipped; E4 starts two beats (1 s) in and lasts 2 beats.
        self.assertEqual(len(sched), 2)
        self.assertEqual(sched[0][2], 60)             # C4 midi
        self.assertEqual(sched[1][0], int(round(2 * 0.5 * sr)))  # start sample
        self.assertEqual(sched[1][2], 64)             # E4 midi

    def test_chord_schedule_is_simultaneous_and_tiles(self):
        sr, bpm = 44100, 120
        n = int(round(8 * 0.5 * sr))  # 8 beats
        sched = _chord_schedule(["C", "G"], bpm, sr, n, 4, 4)
        # Two chords across 8 beats, three notes each.
        self.assertEqual(len(sched), 6)
        # First triad all share start sample 0.
        starts = sorted({s for s, *_ in sched})
        self.assertEqual(starts[0], 0)
        self.assertEqual(len(starts), 2)


class TestEngineRegistry(unittest.TestCase):
    def test_soundfont_is_a_part_engine(self):
        self.assertIn("soundfont", PART_ENGINES)
        self.assertIn("soundfont", ENGINES)


class TestValidation(unittest.TestCase):
    def _track(self, patch):
        return {"key": "C major", "bpm": 100,
                "sections": [{"name": "s", "bars": 1, "parts": {}}],
                "palette": {"piano": patch}}

    def test_bad_program_rejected(self):
        with self.assertRaises(spec.SpecError):
            spec._validate_track(self._track({"engine": "soundfont", "program": 200}), "x")

    def test_valid_program_accepted(self):
        spec._validate_track(self._track({"engine": "soundfont", "program": 48}), "x")


@unittest.skipUnless(HAVE_SF, "FluidSynth/soundfont not installed")
class TestRender(unittest.TestCase):
    def test_melody_renders_finite_audio(self):
        sr, bpm = 44100, 120
        n = int(round(4 * 0.5 * sr))
        sched = _melody_schedule([["C4", 1], ["E4", 1], ["G4", 1], ["C5", 1]], bpm, sr)
        buf = soundfont.render_scheduled(sched, {"engine": "soundfont", "program": 0}, sr, n)
        self.assertEqual(buf.shape[0], n)
        self.assertTrue(np.isfinite(buf).all())
        self.assertGreater(float(np.max(np.abs(buf))), 0.05)  # not silent

    def test_empty_schedule_is_silent_but_sized(self):
        buf = soundfont.render_scheduled([], {"engine": "soundfont"}, 44100, 1000)
        self.assertEqual(buf.shape[0], 1000)
        # No notes -> effectively silent (FluidSynth may leave a tiny reset residual).
        self.assertLess(float(np.max(np.abs(buf))), 1e-3)


if __name__ == "__main__":
    unittest.main()
