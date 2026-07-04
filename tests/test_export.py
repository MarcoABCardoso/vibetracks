"""Tests for the optional game-ready audio export (OGG / MP3 / FLAC).

The format dispatch and WAV path are pure stdlib and always run; the compressed
encodes are gated behind the optional encoders (soundfile / lameenc) so the suite
still passes without the `export` extra installed — exactly like the soundfont
tests. A ~1s tone stands in for a rendered track.
"""

import importlib.util
import os
import tempfile
import unittest

import numpy as np

from vibetracks import audioexport

HAVE_SF = importlib.util.find_spec("soundfile") is not None
HAVE_LAME = importlib.util.find_spec("lameenc") is not None


def _tone(secs=1.0, sr=44100):
    t = np.arange(int(secs * sr)) / sr
    x = 0.2 * np.sin(2 * np.pi * 330 * t)
    return np.column_stack([x, x]), sr


class TestDispatch(unittest.TestCase):
    def test_unknown_format_raises(self):
        buf, sr = _tone(0.1)
        with self.assertRaises(audioexport.ExportError):
            audioexport.write_audio("x.xyz", buf, sr, fmt="xyz")

    def test_wav_always_works_without_extras(self):
        buf, sr = _tone(0.2)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.wav")
            dur = audioexport.write_audio(p, buf, sr)  # fmt inferred from ".wav"
            self.assertAlmostEqual(dur, buf.shape[0] / sr, places=3)
            self.assertGreater(os.path.getsize(p), 1000)

    def test_formats_list(self):
        self.assertEqual(audioexport.FORMATS[0], "wav")
        for f in ("ogg", "mp3", "flac"):
            self.assertIn(f, audioexport.FORMATS)


@unittest.skipUnless(HAVE_SF, "soundfile/libsndfile not installed")
class TestSndfile(unittest.TestCase):
    def test_ogg_and_flac_roundtrip(self):
        import soundfile as sf
        buf, sr = _tone(1.0)
        with tempfile.TemporaryDirectory() as d:
            for fmt in ("ogg", "flac"):
                p = os.path.join(d, f"t.{fmt}")
                dur = audioexport.write_audio(p, buf, sr, fmt=fmt)
                self.assertAlmostEqual(dur, buf.shape[0] / sr, places=2)
                self.assertGreater(os.path.getsize(p), 500)
                data, rsr = sf.read(p)
                self.assertEqual(rsr, sr)
                self.assertEqual(data.shape[1], 2)
                self.assertGreater(float(np.max(np.abs(data))), 0.05)  # not silent


@unittest.skipUnless(HAVE_LAME, "lameenc not installed")
class TestMp3(unittest.TestCase):
    def test_mp3_writes_nonempty(self):
        buf, sr = _tone(1.0)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.mp3")
            dur = audioexport.write_audio(p, buf, sr, fmt="mp3")
            self.assertAlmostEqual(dur, buf.shape[0] / sr, places=2)
            self.assertGreater(os.path.getsize(p), 500)


if __name__ == "__main__":
    unittest.main()
