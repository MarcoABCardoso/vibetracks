"""Pure-numpy sound synthesis: oscillators, envelopes, drums, effects.

No system dependencies (no FluidSynth/SoX/ffmpeg). Everything is generated from
math into float32 numpy arrays in the range roughly [-1, 1], then mixed and
written to WAV by :mod:`vibetracks.wavio`.

Conventions:
- ``sr`` is the sample rate in Hz (default 44100).
- Mono signals are 1-D float arrays. The sequencer mixes them and handles stereo.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import lfilter

SR = 44100


# --- Oscillators -------------------------------------------------------------

def _phase(freq: float, n: int, sr: int) -> np.ndarray:
    t = np.arange(n, dtype=np.float64) / sr
    return 2.0 * np.pi * freq * t


def oscillator(freq: float, dur: float, sr: int = SR, wave: str = "saw") -> np.ndarray:
    """Generate ``dur`` seconds of a waveform at ``freq``.

    Supported waves: sine, square, saw, triangle, noise. Band-limiting is naive
    (no PolyBLEP); a gentle one-pole lowpass is applied by instruments to tame
    the harshest aliasing, which is fine for the lo-fi synthwave aesthetic.
    """
    n = max(1, int(dur * sr))
    if wave == "noise":
        return np.random.uniform(-1.0, 1.0, n).astype(np.float64)
    ph = _phase(freq, n, sr)
    if wave == "sine":
        return np.sin(ph)
    if wave == "square":
        return np.sign(np.sin(ph))
    if wave == "saw":
        # Rising sawtooth in [-1, 1].
        return 2.0 * (ph / (2.0 * np.pi) % 1.0) - 1.0
    if wave == "triangle":
        return 2.0 * np.abs(2.0 * (ph / (2.0 * np.pi) % 1.0) - 1.0) - 1.0
    raise ValueError(f"unknown wave {wave!r}")


def supersaw(freq: float, dur: float, sr: int = SR, voices: int = 3,
             detune: float = 0.012, wave: str = "saw") -> np.ndarray:
    """Stack ``voices`` slightly detuned oscillators for a fat synth lead/pad."""
    if voices <= 1:
        return oscillator(freq, dur, sr, wave)
    n = max(1, int(dur * sr))
    out = np.zeros(n, dtype=np.float64)
    # Spread voices symmetrically around the centre frequency.
    spread = np.linspace(-1.0, 1.0, voices)
    for s in spread:
        f = freq * (2.0 ** (s * detune))
        out += oscillator(f, dur, sr, wave)
    return out / voices


# --- Envelopes ---------------------------------------------------------------

def adsr(n: int, sr: int = SR, attack: float = 0.01, decay: float = 0.08,
         sustain: float = 0.7, release: float = 0.12) -> np.ndarray:
    """Return an ADSR amplitude envelope of length ``n`` samples.

    The release tail is carved out of the note's own duration so notes do not
    overrun their slot. Times are in seconds and clamped to fit ``n``.
    """
    a = int(attack * sr)
    d = int(decay * sr)
    r = int(release * sr)
    # Ensure A+D+R fit inside the note; sustain fills whatever is left.
    a = min(a, n)
    d = min(d, max(0, n - a))
    r = min(r, max(0, n - a - d))
    s_len = max(0, n - a - d - r)
    env = np.zeros(n, dtype=np.float64)
    idx = 0
    if a:
        env[idx:idx + a] = np.linspace(0.0, 1.0, a, endpoint=False)
        idx += a
    if d:
        env[idx:idx + d] = np.linspace(1.0, sustain, d, endpoint=False)
        idx += d
    if s_len:
        env[idx:idx + s_len] = sustain
        idx += s_len
    if r:
        env[idx:idx + r] = np.linspace(sustain, 0.0, r, endpoint=True)
        idx += r
    return env


# --- Filters & effects -------------------------------------------------------

def lowpass(sig: np.ndarray, cutoff: float, sr: int = SR) -> np.ndarray:
    """One-pole lowpass filter. ``cutoff`` in Hz. Cheap, mellows bright waves.

    Implemented as a first-order IIR via :func:`scipy.signal.lfilter` so it is
    fast even on long buffers: ``y[n] = a*x[n] + (1-a)*y[n-1]``.
    """
    if cutoff <= 0 or cutoff >= sr / 2:
        return sig
    dt = 1.0 / sr
    rc = 1.0 / (2.0 * np.pi * cutoff)
    alpha = dt / (rc + dt)
    return lfilter([alpha], [1.0, -(1.0 - alpha)], sig)


def delay(sig: np.ndarray, time: float, feedback: float = 0.35,
          mix: float = 0.25, sr: int = SR) -> np.ndarray:
    """Feedback delay / echo. ``time`` in seconds.

    The wet path is a feedback comb filter ``y[n] = x[n] + fb*y[n-d]`` realised
    with ``lfilter`` (denominator has ``-fb`` at lag ``d``). A tail is appended
    so trailing echoes are not cut off.
    """
    d = int(time * sr)
    if d <= 0 or mix <= 0:
        return sig
    tail = np.zeros(int(d * 4), dtype=np.float64)
    dry = np.concatenate([sig.astype(np.float64), tail])
    a = np.zeros(d + 1)
    a[0] = 1.0
    a[d] = -feedback
    wet = lfilter([1.0], a, dry)
    return (1.0 - mix) * dry + mix * wet


def reverb(sig: np.ndarray, amount: float = 0.2, sr: int = SR) -> np.ndarray:
    """Small Schroeder-style reverb: a few feedback combs summed into a wet mix.

    Cheap and a touch grainy, but enough to glue pads together. ``amount`` is
    the wet mix in [0, 1]. Each comb uses :func:`scipy.signal.lfilter`.
    """
    if amount <= 0:
        return sig
    comb_times = [0.0297, 0.0371, 0.0411, 0.0437]  # seconds, mutually prime-ish
    tail = np.zeros(int(0.12 * sr), dtype=np.float64)
    base = np.concatenate([sig.astype(np.float64), tail])
    wet = np.zeros_like(base)
    for ct in comb_times:
        d = int(ct * sr)
        a = np.zeros(d + 1)
        a[0] = 1.0
        a[d] = -0.7
        wet += lfilter([1.0], a, base)
    wet /= len(comb_times)
    wet = wet[:len(sig)]
    return (1.0 - amount) * sig + amount * wet


def soft_clip(sig: np.ndarray, drive: float = 1.0) -> np.ndarray:
    """Smooth saturation via tanh; tames peaks and adds a touch of warmth."""
    return np.tanh(sig * drive)


def normalize(sig: np.ndarray, peak: float = 0.89) -> np.ndarray:
    """Scale a signal so its absolute peak equals ``peak`` (no-op if silent)."""
    m = float(np.max(np.abs(sig))) if sig.size else 0.0
    if m < 1e-9:
        return sig
    return sig * (peak / m)


# --- Drum synthesis ----------------------------------------------------------

def kick(dur: float = 0.28, sr: int = SR) -> np.ndarray:
    """Synth kick: a sine whose pitch drops fast, plus a short click."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    # Pitch envelope: 120 Hz -> 45 Hz exponential drop.
    f = 45.0 + (120.0 - 45.0) * np.exp(-t * 28.0)
    phase = 2.0 * np.pi * np.cumsum(f) / sr
    body = np.sin(phase) * np.exp(-t * 7.0)
    click = oscillator(1800, 0.004, sr, "sine") * np.exp(-np.arange(int(0.004 * sr)) / (0.001 * sr))
    out = body
    out[:click.shape[0]] += click * 0.5
    return normalize(out, 0.95)


def snare(dur: float = 0.2, sr: int = SR) -> np.ndarray:
    """Synth snare: filtered noise burst + a short tonal body."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    noise = np.random.uniform(-1, 1, n) * np.exp(-t * 22.0)
    tone = (oscillator(190, dur, sr, "triangle") + oscillator(260, dur, sr, "sine")) \
        * np.exp(-t * 30.0)
    out = 0.7 * noise + 0.3 * tone
    return normalize(out, 0.9)


def hat(dur: float = 0.06, sr: int = SR, open_: bool = False) -> np.ndarray:
    """Synth hi-hat: short bright noise burst (longer decay if ``open_``)."""
    if open_:
        dur = 0.18
    n = int(dur * sr)
    t = np.arange(n) / sr
    decay = 14.0 if open_ else 60.0
    noise = np.random.uniform(-1, 1, n) * np.exp(-t * decay)
    # High-pass-ish by subtracting a smoothed copy.
    smooth = np.convolve(noise, np.ones(8) / 8, mode="same")
    out = noise - smooth
    return normalize(out, 0.55)


DRUM_VOICES = {"kick": kick, "snare": snare, "hat": hat, "ohat": lambda **k: hat(open_=True, **k)}
