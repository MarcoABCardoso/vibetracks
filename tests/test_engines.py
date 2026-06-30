"""Tests for the Stage 1 synthesis engines and modern effects.

Covers the non-retro additions: array-frequency oscillators (vibrato), FM and
Karplus-Strong engines, the resonant filter, chorus, convolution reverb, the
``render_note`` engine dispatch, and spec validation of the ``engine`` field.
Everything must stay finite and roughly in range so the master stage can mix it.
"""

import os
import unittest

import numpy as np

from vibetracks import spec, synth
from vibetracks.instruments import ENGINES, apply_part_effects, render_note

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _finite(sig):
    sig = np.asarray(sig)
    return sig.size > 0 and not np.isnan(sig).any() and not np.isinf(sig).any()


class TestOscillators(unittest.TestCase):
    def test_scalar_and_array_freq_agree_when_constant(self):
        # A constant per-sample freq array must match the scalar oscillator.
        n = 2000
        scalar = synth.oscillator(220.0, n / synth.SR, wave="sine")
        arr = synth.oscillator(np.full(n, 220.0), 0.0, wave="sine")
        self.assertEqual(arr.shape[0], n)
        np.testing.assert_allclose(scalar[:n], arr, atol=1e-9)

    def test_array_freq_length_drives_output(self):
        out = synth.oscillator(np.full(1234, 440.0), 0.0)
        self.assertEqual(out.shape[0], 1234)

    def test_lfo_in_range(self):
        for shape in ("sine", "triangle", "square"):
            l = synth.lfo(5.0, 4000, shape=shape)
            self.assertTrue(_finite(l))
            self.assertLessEqual(float(np.max(np.abs(l))), 1.0 + 1e-9)


class TestEngines(unittest.TestCase):
    def test_karplus_is_tonal_and_decays(self):
        sig = synth.karplus_strong(220.0, 1.0)
        self.assertTrue(_finite(sig))
        # A plucked string should ring out then fade: tail quieter than the head.
        head = np.max(np.abs(sig[: sig.size // 8]))
        tail = np.max(np.abs(sig[-sig.size // 8:]))
        self.assertGreater(head, tail)

    def test_fm_index_controls_brightness(self):
        soft = synth.fm(220.0, 0.5, ratio=2.0, index=0.1)
        bright = synth.fm(220.0, 0.5, ratio=2.0, index=8.0)
        self.assertTrue(_finite(soft) and _finite(bright))
        # More modulation index spreads energy into higher harmonics, so the
        # waveform has more sample-to-sample variation (higher mean |diff|).
        self.assertGreater(np.mean(np.abs(np.diff(bright))),
                           np.mean(np.abs(np.diff(soft))))


class TestFiltersEffects(unittest.TestCase):
    def test_resonant_lowpass_stable(self):
        noise = np.random.uniform(-1, 1, 8000)
        out = synth.resonant_lowpass(noise, 1200.0, q=6.0)
        self.assertTrue(_finite(out))

    def test_chorus_and_conv_reverb_keep_length(self):
        sig = synth.oscillator(220.0, 0.3)
        self.assertEqual(synth.chorus(sig).shape[0], sig.shape[0])
        wet = synth.conv_reverb(sig, decay=1.0, mix=0.4)
        self.assertEqual(wet.shape[0], sig.shape[0])
        self.assertTrue(_finite(wet))

    def test_zero_mix_effects_are_noops(self):
        sig = synth.oscillator(220.0, 0.1)
        np.testing.assert_array_equal(synth.conv_reverb(sig, mix=0.0), sig)


class TestRenderNoteDispatch(unittest.TestCase):
    def test_every_engine_renders(self):
        patches = {
            "subtractive": {"engine": "subtractive", "wave": "saw", "voices": 2},
            "fm": {"engine": "fm", "ratio": 2.0, "index": 4.0, "mod_decay": 3.0},
            "karplus": {"engine": "karplus", "decay": 0.99},
        }
        for name in ENGINES:
            with self.subTest(engine=name):
                sig = render_note(330.0, 0.4, patches[name])
                self.assertTrue(_finite(sig))

    def test_vibrato_and_tremolo_apply(self):
        vib = render_note(440.0, 0.4, {"vibrato": {"rate": 6.0, "depth": 0.5}})
        trem = render_note(440.0, 0.4, {"tremolo": {"rate": 6.0, "depth": 0.6}})
        self.assertTrue(_finite(vib) and _finite(trem))

    def test_dict_reverb_routes_to_convolution(self):
        sig = render_note(330.0, 0.2, {})
        out = apply_part_effects(sig, {"reverb": {"decay": 1.0, "mix": 0.3},
                                       "chorus": {"mix": 0.3}})
        self.assertTrue(_finite(out))


class TestEngineValidation(unittest.TestCase):
    def test_unknown_engine_rejected(self):
        track = {"key": "A minor", "bpm": 100, "sections": [
                    {"name": "s", "bars": 1, "parts": {}}],
                 "palette": {"lead": {"engine": "wavetable"}}}
        with self.assertRaises(spec.SpecError):
            spec._validate_track(track, "x")

    def test_known_engine_accepted(self):
        track = {"key": "A minor", "bpm": 100, "sections": [
                    {"name": "s", "bars": 1, "parts": {}}],
                 "palette": {"lead": {"engine": "fm"}}}
        spec._validate_track(track, "x")  # must not raise


if __name__ == "__main__":
    unittest.main()
