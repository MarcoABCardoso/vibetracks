"""Tests for the Stage 3 additions: arpeggiator, section transpose, per-section
tempo (with ramp), and fraction-string (tuplet) beat durations.

The pure builders (arp expansion, tempo map, beat parsing) are checked directly;
an end-to-end render proves the four features survive the whole pipeline together.
"""

import os
import unittest

import numpy as np

from vibetracks import spec, theory
from vibetracks.instruments import DEFAULT_PALETTE, merge_patch
from vibetracks.sequencer import _arp_events, _arp_order, _tempo_map, render_track

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _palette():
    return {k: merge_patch(v, None) for k, v in DEFAULT_PALETTE.items()}


class TestParseBeats(unittest.TestCase):
    def test_numbers_and_fractions(self):
        self.assertEqual(theory.parse_beats(2), 2.0)
        self.assertEqual(theory.parse_beats(0.5), 0.5)
        self.assertAlmostEqual(theory.parse_beats("1/3"), 1 / 3)
        self.assertAlmostEqual(theory.parse_beats("3/2"), 1.5)
        self.assertEqual(theory.parse_beats("2"), 2.0)

    def test_rejects_bad_values(self):
        for bad in (0, -1, "1/0", "abc", None, True, "1/"):
            with self.assertRaises(ValueError):
                theory.parse_beats(bad)

    def test_triplet_sums_to_one_beat(self):
        self.assertAlmostEqual(sum(theory.parse_beats("1/3") for _ in range(3)), 1.0)


class TestArp(unittest.TestCase):
    def test_order_patterns(self):
        pool = ["C4", "E4", "G4"]
        self.assertEqual(_arp_order(pool, "up"), ["C4", "E4", "G4"])
        self.assertEqual(_arp_order(pool, "down"), ["G4", "E4", "C4"])
        # updown/downup don't repeat the turning-point notes.
        self.assertEqual(_arp_order(pool, "updown"), ["C4", "E4", "G4", "E4"])
        self.assertEqual(_arp_order(pool, "downup"), ["G4", "E4", "C4", "E4"])
        self.assertEqual(_arp_order(pool, [0, 2]), ["C4", "G4"])

    def test_events_fill_section_gaplessly(self):
        ev = _arp_events(["C", "G"], total_beats=4.0, chord_beats=2.0, rate=0.25,
                         pattern="up", octaves=1, octave=4)
        self.assertAlmostEqual(sum(e[1] for e in ev), 4.0)  # no gaps, no overrun
        self.assertEqual(ev[0][0], "C4")                    # first C-major note
        self.assertEqual(len(ev), 16)                       # 4 beats / 0.25

    def test_octaves_expand_the_pool(self):
        ev = _arp_events(["C"], total_beats=1.5, chord_beats=1.5, rate=0.25,
                         pattern="up", octaves=2, octave=4)
        pitches = [e[0] for e in ev]
        self.assertEqual(pitches, ["C4", "E4", "G4", "C5", "E5", "G5"])

    def test_step_clipped_at_window_edge(self):
        # chord_beats not a multiple of rate: the last step of a window is short.
        ev = _arp_events(["C"], total_beats=1.0, chord_beats=1.0, rate=0.3,
                         pattern="up", octaves=1, octave=4)
        self.assertAlmostEqual(sum(e[1] for e in ev), 1.0)
        self.assertAlmostEqual(ev[-1][1], 0.1)  # 1.0 - 0.3 - 0.3 - 0.3


class TestTempoMap(unittest.TestCase):
    def test_constant_matches_legacy_formula(self):
        sr = 16000
        b2s = _tempo_map(120, None, 8, sr)
        self.assertEqual(b2s(8), int(round(8 * 0.5 * sr)))
        self.assertEqual(b2s(0), 0)

    def test_ramp_is_monotonic_and_between_endpoints(self):
        sr = 16000
        ramp = _tempo_map(60, 120, 8, sr)          # accelerando 60 -> 120 bpm
        slow = _tempo_map(60, None, 8, sr)          # constant 60
        fast = _tempo_map(120, None, 8, sr)         # constant 120
        samples = [ramp(b) for b in range(9)]
        self.assertEqual(samples, sorted(samples))  # strictly increasing in time
        # An accelerando finishes sooner than staying slow, later than being fast.
        self.assertLess(ramp(8), slow(8))
        self.assertGreater(ramp(8), fast(8))


class TestValidation(unittest.TestCase):
    def _track(self, section):
        return {"key": "C major", "bpm": 120, "time_signature": [4, 4],
                "motifs": {}, "palette": _palette(), "sections": [section]}

    def test_arp_part_accepted(self):
        spec._validate_track(self._track({"name": "s", "bars": 1, "parts": {
            "a": {"instrument": "arp", "arp": ["C", "G"], "pattern": "updown",
                  "rate": "1/3", "octaves": 2}}}), "x")

    def test_bad_arp_pattern_rejected(self):
        with self.assertRaises(spec.SpecError):
            spec._validate_track(self._track({"name": "s", "bars": 1, "parts": {
                "a": {"instrument": "arp", "arp": ["C"], "pattern": "sideways"}}}), "x")

    def test_two_kinds_in_one_part_rejected(self):
        with self.assertRaises(spec.SpecError):
            spec._validate_track(self._track({"name": "s", "bars": 1, "parts": {
                "a": {"instrument": "arp", "arp": ["C"], "notes": [["C4", 1]]}}}), "x")

    def test_section_tempo_and_transpose_validated(self):
        spec._validate_track(self._track({"name": "s", "bars": 1, "transpose": 2,
                                          "bpm": 90, "bpm_end": 140, "parts": {}}), "x")
        for bad in ({"bpm": 0}, {"bpm_end": -1}, {"transpose": 1.5}):
            with self.assertRaises(spec.SpecError):
                spec._validate_track(self._track(
                    {"name": "s", "bars": 1, "parts": {}, **bad}), "x")

    def test_fraction_beats_validate(self):
        spec._validate_note_events([["C4", "1/3"], ["E4", "1/3"], ["G4", "1/3"]], "x")
        with self.assertRaises(spec.SpecError):
            spec._validate_note_events([["C4", "1/0"]], "x")


class TestEndToEnd(unittest.TestCase):
    def test_all_four_features_render_together(self):
        track = {"name": "t", "key": "C major", "bpm": 120, "time_signature": [4, 4],
                 "motifs": {}, "loops": 1, "palette": _palette(),
                 "sections": [{
                     "name": "climax", "bars": 2, "bpm": 100, "bpm_end": 150,
                     "transpose": 2, "parts": {
                         "arp": {"instrument": "arp", "arp": ["C", "G"],
                                 "rate": 0.25, "pattern": "updown", "octaves": 2},
                         "trip": {"instrument": "lead",
                                  "notes": [["C5", "1/3"], ["E5", "1/3"], ["G5", "1/3"]],
                                  "repeat": 6},
                         "drums": {"instrument": "drums",
                                   "drums": {"kick": "x...x...", "hat": "x.x.x.x."}}}}]}
        buf = render_track(track, sr=16000, loops=1)
        self.assertEqual(buf.shape[1], 2)
        self.assertFalse(np.isnan(buf).any())
        peak = float(np.max(np.abs(buf)))
        self.assertGreater(peak, 0.1)     # not silent
        self.assertLessEqual(peak, 1.0)


if __name__ == "__main__":
    unittest.main()
