"""Instrument patches: synthwave palette defaults + the note renderer.

A *patch* is a plain dict of parameters describing how to turn a pitch + a
duration into samples. The bible's ``palette`` (and per-track overrides) are
merged on top of these defaults, so a track only needs to mention the params it
wants to change.
"""

from __future__ import annotations

import numpy as np

from . import synth

# --- Default synthwave palette ----------------------------------------------
# Each patch:
#   wave     : oscillator shape (sine/square/saw/triangle)
#   voices   : detuned voices for a supersaw (1 = single oscillator)
#   detune   : detune spread for supersaw voices (in octaves, small)
#   adsr     : [attack, decay, sustain, release] in seconds/level
#   filter   : one-pole lowpass cutoff in Hz (0 = off)
#   gain     : per-instrument level before the master mix
#   octave   : default octave shift applied to chord/arp helpers
#   delay    : optional {time, feedback, mix} echo
#   reverb   : optional wet amount in [0, 1]

DEFAULT_PALETTE = {
    "lead": {
        "wave": "saw", "voices": 2, "detune": 0.010,
        "adsr": [0.008, 0.10, 0.65, 0.18], "filter": 6000, "gain": 0.85,
        "delay": {"time": 0.30, "feedback": 0.30, "mix": 0.22}, "reverb": 0.12,
    },
    "pad": {
        "wave": "saw", "voices": 4, "detune": 0.016,
        "adsr": [0.25, 0.20, 0.80, 0.40], "filter": 3200, "gain": 0.5,
        "reverb": 0.30,
    },
    "bass": {
        "wave": "square", "voices": 1, "detune": 0.0,
        "adsr": [0.006, 0.06, 0.85, 0.06], "filter": 1400, "gain": 0.9,
    },
    "arp": {
        "wave": "triangle", "voices": 1, "detune": 0.0,
        "adsr": [0.004, 0.05, 0.40, 0.06], "filter": 5000, "gain": 0.5,
        "delay": {"time": 0.21, "feedback": 0.28, "mix": 0.25},
    },
    "pluck": {
        "wave": "saw", "voices": 1, "detune": 0.0,
        "adsr": [0.002, 0.12, 0.0, 0.05], "filter": 4500, "gain": 0.6,
    },
    "drums": {"gain": 0.95},
}


def merge_patch(default: dict, override: dict | None) -> dict:
    """Shallow-merge ``override`` onto ``default`` (override wins per key)."""
    out = dict(default)
    if override:
        out.update(override)
    return out


def render_note(freq: float, dur: float, patch: dict, sr: int = synth.SR) -> np.ndarray:
    """Render a single pitched note through a patch (osc -> env -> filter).

    Per-note effects (filter) are applied here; buffer-wide effects (delay,
    reverb) are applied once per part by the sequencer for efficiency.
    """
    voices = int(patch.get("voices", 1))
    detune = float(patch.get("detune", 0.0))
    wave = patch.get("wave", "saw")
    if voices > 1:
        sig = synth.supersaw(freq, dur, sr, voices=voices, detune=detune, wave=wave)
    else:
        sig = synth.oscillator(freq, dur, sr, wave)
    a, d, s, r = patch.get("adsr", [0.01, 0.08, 0.7, 0.12])
    sig = sig * synth.adsr(len(sig), sr, a, d, s, r)
    cutoff = float(patch.get("filter", 0) or 0)
    if cutoff:
        sig = synth.lowpass(sig, cutoff, sr)
    return sig


def apply_part_effects(sig: np.ndarray, patch: dict, sr: int = synth.SR) -> np.ndarray:
    """Apply buffer-wide effects (delay, reverb) declared on a patch."""
    dly = patch.get("delay")
    if dly:
        sig = synth.delay(sig, dly.get("time", 0.25), dly.get("feedback", 0.3),
                          dly.get("mix", 0.2), sr)
    rev = patch.get("reverb")
    if rev:
        sig = synth.reverb(sig, float(rev), sr)
    return sig
