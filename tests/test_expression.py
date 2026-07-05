"""Tests for the expression additions: swing/groove, parameter automation, and
sidechain ducking.

The pure builders (``_swing_beat``, ``_automation_curve``, ``_drum_onsets``,
``_sidechain_env``) are checked directly; validation covers the new ``swing``,
``automation`` and ``sidechain`` spec fields; end-to-end renders prove the
features survive the whole pipeline.
"""

import unittest

import numpy as np

from vibetracks import spec
from vibetracks.instruments import DEFAULT_PALETTE, merge_patch
from vibetracks.sequencer import (_automation_curve, _drum_onsets, _sidechain_env,
                                  _swing_beat, render_track)


def _palette():
    return {k: merge_patch(v, None) for k, v in DEFAULT_PALETTE.items()}


class TestSwingBeat(unittest.TestCase):
    def test_straight_is_identity(self):
        for beat in (0.0, 0.25, 0.5, 1.0, 2.75):
            self.assertEqual(_swing_beat(beat, 0.0), beat)

    def test_integer_beats_are_fixed_points(self):
        # Section length depends on this: a whole beat must map to itself.
        for beat in (0.0, 1.0, 2.0, 8.0):
            self.assertAlmostEqual(_swing_beat(beat, 0.33), beat)

    def test_offbeat_midpoint_pushed_late(self):
        # The straight eighth at 0.5 lands at 0.5 + swing/2 (2/3 at swing 1/3).
        self.assertAlmostEqual(_swing_beat(0.5, 0.3), 0.5 + 0.3 * 0.5)
        self.assertAlmostEqual(_swing_beat(0.5, 1 / 3), 2 / 3)

    def test_monotonic_increasing(self):
        xs = np.linspace(0, 4, 400)
        ys = [_swing_beat(x, 0.33) for x in xs]
        self.assertEqual(ys, sorted(ys))


class TestAutomationCurve(unittest.TestCase):
    def test_linear_ramp_hits_endpoints(self):
        c = _automation_curve({"from": 0.3, "to": 1.0}, 100, 16000)
        self.assertEqual(len(c), 100)
        self.assertAlmostEqual(c[0], 0.3)
        self.assertAlmostEqual(c[-1], 1.0)

    def test_exp_ramp_hits_endpoints_and_is_geometric(self):
        c = _automation_curve({"from": 500, "to": 6000, "shape": "exp"}, 128, 16000)
        self.assertAlmostEqual(c[0], 500.0, places=3)
        self.assertAlmostEqual(c[-1], 6000.0, places=1)
        # Geometric: constant ratio between successive samples.
        ratios = c[1:] / c[:-1]
        self.assertTrue(np.allclose(ratios, ratios[0]))

    def test_lfo_stays_within_center_plus_minus_depth(self):
        c = _automation_curve({"lfo": {"rate": 0.5, "depth": 0.8, "center": 0.1}},
                              500, 16000)
        self.assertLessEqual(c.max(), 0.1 + 0.8 + 1e-9)
        self.assertGreaterEqual(c.min(), 0.1 - 0.8 - 1e-9)


class TestSidechain(unittest.TestCase):
    def test_drum_onsets_match_the_grid(self):
        # 120 bpm at sr=16000 -> 0.5 s/beat -> 8000 samples/beat.
        b2s = lambda beat: int(round(beat * 0.5 * 16000))
        parts = {"d": {"drums": {"kick": "x...x...", "hat": "x.x.x.x."}}}
        onsets = _drum_onsets(parts, "kick", b2s, bpb=4.0, total_beats=4.0)
        self.assertEqual(onsets, [0, 16000])  # kicks on beat 0 and beat 2

    def test_missing_voice_gives_no_onsets(self):
        b2s = lambda beat: int(round(beat * 8000))
        self.assertEqual(_drum_onsets({"d": {"drums": {"kick": "x..."}}},
                                      "clap", b2s, 4.0, 4.0), [])

    def test_env_dips_at_onset_and_recovers(self):
        env = _sidechain_env([0, 16000], 32000, 16000, amount=0.7, release=0.18)
        self.assertAlmostEqual(env[0], 0.3, places=2)   # ducked to 1-amount
        self.assertGreater(env[8000], 0.9)              # recovered between kicks
        self.assertLessEqual(env.max(), 1.0)

    def test_empty_onsets_is_unity(self):
        env = _sidechain_env([], 1000, 16000, amount=0.7, release=0.18)
        self.assertTrue(np.array_equal(env, np.ones(1000)))

    def test_sidechain_ducks_the_render_at_kicks(self):
        # A bass held under a kick should be quieter right after each kick than a
        # non-sidechained copy.
        def _track(sidechain):
            bass = {"instrument": "bass", "notes": [["A2", 4], ["A2", 4]]}
            if sidechain:
                bass["sidechain"] = {"amount": 0.85, "release": 0.2}
            return {"name": "t", "key": "A minor", "bpm": 120,
                    "time_signature": [4, 4], "motifs": {}, "loops": 1,
                    "palette": _palette(),
                    "sections": [{"name": "s", "bars": 2, "parts": {
                        "bass": bass,
                        "drums": {"instrument": "drums",
                                  "drums": {"kick": "x...x...x...x..."}}}}]}
        plain = render_track(_track(False), sr=16000, loops=1)
        pumped = render_track(_track(True), sr=16000, loops=1)
        self.assertEqual(plain.shape, pumped.shape)
        self.assertFalse(np.allclose(plain, pumped))


class TestValidation(unittest.TestCase):
    def _track(self, section, **top):
        return {"key": "C major", "bpm": 120, "time_signature": [4, 4],
                "motifs": {}, "palette": _palette(), "sections": [section], **top}

    def test_swing_accepted_track_and_section(self):
        spec._validate_track(self._track(
            {"name": "s", "bars": 1, "swing": 0.25, "parts": {}}, swing=0.1), "x")

    def test_bad_swing_rejected(self):
        for bad in (1.0, 1.5, -0.1, "0.3", True):
            with self.assertRaises(spec.SpecError):
                spec._validate_track(self._track(
                    {"name": "s", "bars": 1, "swing": bad, "parts": {}}), "x")

    def test_automation_targets_accepted(self):
        spec._validate_track(self._track({"name": "s", "bars": 1, "parts": {
            "a": {"instrument": "lead", "notes": [["C4", 1]], "automation": {
                "filter": {"from": 500, "to": 6000, "shape": "exp"},
                "gain": {"from": 0.3, "to": 1.0},
                "pan": {"lfo": {"rate": 0.25, "depth": 0.8, "center": 0.0}}}}}}), "x")

    def test_unknown_automation_target_rejected(self):
        with self.assertRaises(spec.SpecError):
            spec._validate_track(self._track({"name": "s", "bars": 1, "parts": {
                "a": {"instrument": "lead", "notes": [["C4", 1]],
                      "automation": {"reverb": {"from": 0, "to": 1}}}}}), "x")

    def test_bad_automation_shape_rejected(self):
        with self.assertRaises(spec.SpecError):
            spec._validate_track(self._track({"name": "s", "bars": 1, "parts": {
                "a": {"instrument": "lead", "notes": [["C4", 1]],
                      "automation": {"gain": {"from": 0, "to": 1,
                                              "shape": "sideways"}}}}}), "x")

    def test_non_object_automation_rejected(self):
        with self.assertRaises(spec.SpecError):
            spec._validate_track(self._track({"name": "s", "bars": 1, "parts": {
                "a": {"instrument": "lead", "notes": [["C4", 1]],
                      "automation": [1, 2, 3]}}}), "x")

    def test_sidechain_accepted(self):
        spec._validate_track(self._track({"name": "s", "bars": 1, "parts": {
            "a": {"instrument": "bass", "notes": [["A2", 1]],
                  "sidechain": {"amount": 0.8, "release": 0.2, "source": "kick"}}}}),
            "x")

    def test_bad_sidechain_rejected(self):
        for bad in ({"amount": 0}, {"amount": 1.5}, {"amount": "x"},
                    {"release": 0}, {"release": -1}, {"source": 3}):
            with self.assertRaises(spec.SpecError):
                spec._validate_track(self._track({"name": "s", "bars": 1, "parts": {
                    "a": {"instrument": "bass", "notes": [["A2", 1]],
                          "sidechain": bad}}}), "x")


class TestEndToEnd(unittest.TestCase):
    def test_swing_and_automation_render_together(self):
        track = {"name": "t", "key": "A minor", "bpm": 120, "time_signature": [4, 4],
                 "motifs": {}, "loops": 1, "swing": 0.33, "palette": _palette(),
                 "sections": [{
                     "name": "groove", "bars": 2, "parts": {
                         "lead": {"instrument": "lead",
                                  "notes": [["A4", 0.5], ["C5", 0.5],
                                            ["E5", 0.5], ["A5", 0.5]], "repeat": 4,
                                  "automation": {
                                      "filter": {"from": 500, "to": 6000,
                                                 "shape": "exp"},
                                      "gain": {"from": 0.3, "to": 1.0},
                                      "pan": {"lfo": {"rate": 0.5, "depth": 0.8}}}},
                         "drums": {"instrument": "drums",
                                   "drums": {"kick": "x...x...",
                                             "hat": "x.x.x.x."}}}}]}
        buf = render_track(track, sr=16000, loops=1)
        self.assertEqual(buf.shape[1], 2)
        self.assertFalse(np.isnan(buf).any())
        peak = float(np.max(np.abs(buf)))
        self.assertGreater(peak, 0.1)     # not silent
        self.assertLessEqual(peak, 1.0)

    def test_swing_changes_the_render(self):
        # A swung render must differ from the straight one (same notes, feel only).
        def _track(swing):
            return {"name": "t", "key": "A minor", "bpm": 120,
                    "time_signature": [4, 4], "motifs": {}, "loops": 1,
                    "swing": swing, "palette": _palette(),
                    "sections": [{"name": "s", "bars": 2, "parts": {
                        "hat": {"instrument": "arp", "arp": ["Am"], "rate": 0.5}}}]}
        straight = render_track(_track(0.0), sr=16000, loops=1)
        swung = render_track(_track(0.33), sr=16000, loops=1)
        self.assertEqual(straight.shape, swung.shape)
        self.assertFalse(np.allclose(straight, swung))


if __name__ == "__main__":
    unittest.main()
