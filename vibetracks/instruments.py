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
#   engine   : synthesis engine — "subtractive" (default), "fm", or "karplus"
#   wave     : oscillator shape (sine/square/saw/triangle) [subtractive]
#   voices   : detuned voices for a supersaw (1 = single oscillator) [subtractive]
#   detune   : detune spread for supersaw voices (in octaves, small) [subtractive]
#   ratio    : FM modulator:carrier frequency ratio [fm]
#   index    : FM modulation depth / brightness [fm]
#   mod_decay: FM modulator fade for a struck, evolving attack [fm]
#   decay    : Karplus-Strong string decay, near 1.0 = long sustain [karplus]
#   adsr     : [attack, decay, sustain, release] in seconds/level
#   filter   : lowpass cutoff in Hz (0 = off)
#   resonance: filter Q; >0.7 adds a resonant peak (switches to a biquad)
#   vibrato  : optional {rate, depth, shape} pitch modulation (depth in semitones)
#   tremolo  : optional {rate, depth, shape} amplitude modulation (depth 0..1)
#   gain     : per-instrument level before the master mix
#   octave   : default octave shift applied to chord/arp helpers
#   delay    : optional {time, feedback, mix} echo
#   chorus   : optional {rate, depth, mix} modulated-delay widener
#   reverb   : wet amount in [0, 1], or {decay, mix, predelay} convolution reverb

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


# Note-level engines synthesize one pitch at a time (rendered by ``render_note``).
NOTE_ENGINES = ("subtractive", "fm", "karplus")
# Part-level engines render a whole part at once (handled in the sequencer);
# ``soundfont`` streams scheduled notes through FluidSynth (see ``soundfont.py``).
PART_ENGINES = ("soundfont",)
ENGINES = NOTE_ENGINES + PART_ENGINES


def _vibrato_freq(freq: float, n: int, patch: dict, sr: int):
    """Return a per-sample frequency array if the patch has vibrato, else ``freq``.

    Vibrato depth is in semitones; an optional ``delay`` (seconds) ramps the
    wobble in so the note starts steady — the way a player adds it mid-note.
    """
    vib = patch.get("vibrato")
    if not vib:
        return freq
    depth = float(vib.get("depth", 0.0))
    if depth <= 0:
        return freq
    mod = synth.lfo(float(vib.get("rate", 5.0)), n, sr, vib.get("shape", "sine"))
    onset = float(vib.get("delay", 0.0))
    if onset > 0:
        ramp = np.clip(np.arange(n) / sr / onset, 0.0, 1.0)
        mod = mod * ramp
    return freq * (2.0 ** (depth * mod / 12.0))


def render_note(freq: float, dur: float, patch: dict, sr: int = synth.SR) -> np.ndarray:
    """Render a single pitched note through a patch (engine -> env -> filter).

    The engine (subtractive/fm/karplus) generates the raw tone; an ADSR shapes
    its amplitude and trims it to the note slot; an optional resonant filter and
    tremolo finish it. Per-note work lives here; buffer-wide effects (delay,
    chorus, reverb) are applied once per part by the sequencer for efficiency.
    """
    engine = patch.get("engine", "subtractive")
    n = max(1, int(dur * sr))
    if engine == "karplus":
        # Pitch is fixed by the delay line, so vibrato does not apply here.
        sig = synth.karplus_strong(freq, dur, sr, decay=float(patch.get("decay", 0.996)))
    elif engine == "fm":
        f = _vibrato_freq(freq, n, patch, sr)
        sig = synth.fm(f, dur, sr, ratio=float(patch.get("ratio", 2.0)),
                       index=float(patch.get("index", 3.0)),
                       mod_decay=float(patch.get("mod_decay", 0.0)))
    else:
        f = _vibrato_freq(freq, n, patch, sr)
        voices = int(patch.get("voices", 1))
        if voices > 1:
            sig = synth.supersaw(f, dur, sr, voices=voices,
                                 detune=float(patch.get("detune", 0.0)),
                                 wave=patch.get("wave", "saw"))
        else:
            sig = synth.oscillator(f, dur, sr, patch.get("wave", "saw"))

    a, d, s, r = patch.get("adsr", [0.01, 0.08, 0.7, 0.12])
    sig = sig * synth.adsr(len(sig), sr, a, d, s, r)

    trem = patch.get("tremolo")
    if trem and float(trem.get("depth", 0.0)) > 0:
        depth = float(trem["depth"])
        mod = synth.lfo(float(trem.get("rate", 5.0)), len(sig), sr,
                        trem.get("shape", "sine"))
        sig = sig * (1.0 - depth * (0.5 - 0.5 * mod))

    cutoff = float(patch.get("filter", 0) or 0)
    if cutoff:
        q = float(patch.get("resonance", 0) or 0)
        sig = (synth.resonant_lowpass(sig, cutoff, q, sr) if q
               else synth.lowpass(sig, cutoff, sr))
    return sig


def apply_part_effects(sig: np.ndarray, patch: dict, sr: int = synth.SR) -> np.ndarray:
    """Apply buffer-wide effects (delay, chorus, reverb) declared on a patch."""
    dly = patch.get("delay")
    if dly:
        sig = synth.delay(sig, dly.get("time", 0.25), dly.get("feedback", 0.3),
                          dly.get("mix", 0.2), sr)
    cho = patch.get("chorus")
    if cho:
        sig = synth.chorus(sig, sr, rate=cho.get("rate", 0.8),
                           depth=cho.get("depth", 0.002), mix=cho.get("mix", 0.4))
    rev = patch.get("reverb")
    if isinstance(rev, dict):
        sig = synth.conv_reverb(sig, decay=rev.get("decay", 1.5),
                                mix=rev.get("mix", 0.3),
                                predelay=rev.get("predelay", 0.02), sr=sr)
    elif rev:
        sig = synth.reverb(sig, float(rev), sr)
    return sig
