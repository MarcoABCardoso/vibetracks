"""Sequence a resolved track spec into a mixed stereo float buffer.

Pipeline per track:
  sections -> parts -> events scheduled on a beat grid -> per-part buffer
  (with delay/reverb) -> panned into stereo -> summed -> sections concatenated
  (loop sections repeated) -> master normalize for consistent loudness.

Timing is expressed in *beats* (quarter notes). ``seconds_per_beat = 60/bpm``.
"""

from __future__ import annotations

import numpy as np

from . import soundfont, synth, theory
from .instruments import PART_ENGINES, apply_part_effects, render_note

DEFAULT_LOOPS = 2          # times a section marked {"loop": true} repeats
DEFAULT_VELOCITY = 0.8


def beats_per_bar(time_signature) -> float:
    num, denom = time_signature
    return num * 4.0 / denom


def _spb(bpm: float) -> float:
    return 60.0 / bpm


def _place(buf: np.ndarray, sig: np.ndarray, start_sample: int) -> None:
    """Add ``sig`` into mono ``buf`` at ``start_sample`` (clipped to length)."""
    end = start_sample + sig.shape[0]
    if start_sample >= buf.shape[0]:
        return
    if end > buf.shape[0]:
        sig = sig[: buf.shape[0] - start_sample]
        end = buf.shape[0]
    buf[start_sample:end] += sig


def _pan(mono: np.ndarray, pan: float) -> np.ndarray:
    """Equal-power pan a mono signal to stereo. ``pan`` in [-1, 1]."""
    angle = (pan + 1.0) * 0.25 * np.pi  # 0..pi/2
    left = mono * np.cos(angle)
    right = mono * np.sin(angle)
    return np.column_stack([left, right])


# --- Part renderers ----------------------------------------------------------

def _render_melody(events, patch, bpm, sr, section_samples):
    """Render a sequence of [pitch, beats, vel] events laid end to end."""
    buf = np.zeros(section_samples, dtype=np.float64)
    spb = _spb(bpm)
    beat = 0.0
    for ev in events:
        pitch, dur_beats = ev[0], ev[1]
        vel = ev[2] if len(ev) > 2 else DEFAULT_VELOCITY
        start = int(round(beat * spb * sr))
        if pitch is not None:  # None -> rest
            note = render_note(theory.note_to_freq(pitch), dur_beats * spb, patch, sr)
            _place(buf, note * vel, start)
        beat += dur_beats
    return buf


def _render_chords(symbols, patch, bpm, sr, section_samples, chord_beats, bpb, octave):
    """Render chord symbols in sequence, each held for ``chord_beats``, tiled."""
    buf = np.zeros(section_samples, dtype=np.float64)
    spb = _spb(bpm)
    total_beats = section_samples / (spb * sr)
    beat = 0.0
    i = 0
    while beat < total_beats - 1e-6:
        sym = symbols[i % len(symbols)]
        start = int(round(beat * spb * sr))
        for note_name in theory.chord_notes(sym, octave):
            note = render_note(theory.note_to_freq(note_name), chord_beats * spb, patch, sr)
            _place(buf, note * (DEFAULT_VELOCITY / 2.0), start)
        beat += chord_beats
        i += 1
    return buf


# --- Soundfont (part-level) renderers ---------------------------------------

def _melody_schedule(events, bpm, sr):
    """Turn a sequence of [pitch, beats, vel?] into scheduled soundfont notes.

    Notes are laid end to end (the same timing as :func:`_render_melody`);
    returns ``(start_sample, dur_samples, midi, velocity)`` tuples, skipping rests.
    """
    spb = _spb(bpm)
    sched = []
    beat = 0.0
    for ev in events:
        pitch, dur_beats = ev[0], ev[1]
        vel = ev[2] if len(ev) > 2 else DEFAULT_VELOCITY
        if pitch is not None:
            sched.append((int(round(beat * spb * sr)), int(round(dur_beats * spb * sr)),
                          theory.note_to_midi(pitch), int(round(vel * 127))))
        beat += dur_beats
    return sched


def _chord_schedule(symbols, bpm, sr, section_samples, chord_beats, octave):
    """Schedule tiled chord symbols as simultaneous soundfont notes."""
    spb = _spb(bpm)
    total_beats = section_samples / (spb * sr)
    dur = int(round(chord_beats * spb * sr))
    sched = []
    beat = 0.0
    i = 0
    while beat < total_beats - 1e-6:
        start = int(round(beat * spb * sr))
        for note_name in theory.chord_notes(symbols[i % len(symbols)], octave):
            sched.append((start, dur, theory.note_to_midi(note_name),
                          int(round(DEFAULT_VELOCITY * 127))))
        beat += chord_beats
        i += 1
    return sched


def _render_drums(voices, bpm, sr, section_samples, bpb, cache):
    """Render per-voice step patterns, tiled across the whole section."""
    buf = np.zeros(section_samples, dtype=np.float64)
    spb = _spb(bpm)
    bar_samples = bpb * spb * sr
    n_bars = max(1, int(round(section_samples / bar_samples)))
    for voice, pattern in voices.items():
        steps = len(pattern)
        if steps == 0:
            continue
        step_samples = bar_samples / steps
        for bar in range(n_bars):
            for s, ch in enumerate(pattern):
                if ch in ".-":
                    continue
                sample = cache["ohat" if ch == "o" else voice]
                start = int(round(bar * bar_samples + s * step_samples))
                _place(buf, sample, start)
    return buf


def _drum_cache(sr):
    return {name: fn(sr=sr) for name, fn in synth.DRUM_VOICES.items()}


def _transform(events, part):
    """Apply leitmotif transformations to a melody, in musical order.

    retrograde (reverse) -> invert (mirror) -> transpose (shift) -> stretch
    (augment/diminish durations). Rests (pitch ``None``) pass through untouched.
    These are how one motif recolors itself across a score (Undertale/Zelda style)
    rather than being restated verbatim.
    """
    if part.get("retrograde"):
        events = list(reversed(events))
    inv = part.get("invert")
    if inv:
        pivot = inv if isinstance(inv, str) else next(
            (e[0] for e in events if e[0] is not None), None)
        if pivot:
            events = [[None if e[0] is None else theory.invert(e[0], pivot), *e[1:]]
                      for e in events]
    semis = int(part.get("transpose", 0))
    if semis:
        events = [[None if e[0] is None else theory.transpose(e[0], semis), *e[1:]]
                  for e in events]
    stretch = float(part.get("stretch", 1.0))
    if stretch != 1.0:
        events = [[e[0], e[1] * stretch, *e[2:]] for e in events]
    return events


# --- Section / track assembly -----------------------------------------------

def render_section(section, track, sr, drum_cache):
    """Render one section (all its parts) to a stereo buffer."""
    bpm = track["bpm"]
    bpb = beats_per_bar(track["time_signature"])
    section_beats = section["bars"] * bpb
    section_samples = int(round(section_beats * _spb(bpm) * sr))
    stereo = np.zeros((section_samples, 2), dtype=np.float64)

    for part in section.get("parts", {}).values():
        patch = track["palette"][part["instrument"]]
        pan = float(part.get("pan", 0.0))
        gain = float(part.get("gain", patch.get("gain", 0.8)))
        octave = int(part.get("octave", patch.get("octave", 3)))
        is_sf = patch.get("engine") in PART_ENGINES

        if "drums" in part:
            mono = _render_drums(part["drums"], bpm, sr, section_samples, bpb, drum_cache)
        elif "chords" in part:
            chord_beats = float(part.get("chord_beats", bpb))
            if is_sf:
                sched = _chord_schedule(part["chords"], bpm, sr, section_samples,
                                        chord_beats, octave)
                mono = soundfont.render_scheduled(sched, patch, sr, section_samples)
            else:
                mono = _render_chords(part["chords"], patch, bpm, sr, section_samples,
                                      chord_beats, bpb, octave)
        else:
            if "motif" in part:
                events = list(track["motifs"][part["motif"]].get("notes",
                              track["motifs"][part["motif"]]))
                sl = part.get("slice")
                if sl:  # quote only part of the motif, e.g. [0, 3] = first 3 notes
                    events = events[sl[0]:sl[1]]
            else:
                events = list(part["notes"])
            events = _transform(events, part)
            events = events * int(part.get("repeat", 1))
            if is_sf:
                mono = soundfont.render_scheduled(_melody_schedule(events, bpm, sr),
                                                  patch, sr, section_samples)
            else:
                mono = _render_melody(events, patch, bpm, sr, section_samples)

        mono = apply_part_effects(mono, patch, sr)[:section_samples]
        if mono.shape[0] < section_samples:
            mono = np.pad(mono, (0, section_samples - mono.shape[0]))
        stereo += _pan(mono * gain, pan)
    return stereo


def render_track(track, sr=synth.SR, loops=None):
    """Render a resolved track dict to a stereo float buffer (shape (n, 2))."""
    if loops is None:
        loops = track.get("loops") or DEFAULT_LOOPS
    drum_cache = _drum_cache(sr)
    pieces = []
    for section in track["sections"]:
        rendered = render_section(section, track, sr, drum_cache)
        repeats = loops if section.get("loop") else section.get("repeat", 1)
        for _ in range(int(repeats)):
            pieces.append(rendered)
    if not pieces:
        return np.zeros((sr, 2), dtype=np.float64)
    full = np.concatenate(pieces, axis=0)
    # Gentle saturation then normalize to a fixed peak so all tracks match level.
    full = synth.soft_clip(full, drive=1.05)
    full = synth.normalize(full, peak=0.89)
    return full
