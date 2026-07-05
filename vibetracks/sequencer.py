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


def _pan(mono: np.ndarray, pan) -> np.ndarray:
    """Equal-power pan a mono signal to stereo.

    ``pan`` in [-1, 1] as a scalar, or a per-sample array (length == ``mono``)
    for automated auto-pan movement. ``np.cos``/``np.sin`` vectorise over both.
    """
    angle = (np.asarray(pan, dtype=np.float64) + 1.0) * 0.25 * np.pi  # 0..pi/2
    left = mono * np.cos(angle)
    right = mono * np.sin(angle)
    return np.column_stack([left, right])


# --- Tempo map ---------------------------------------------------------------

def _tempo_map(bpm, bpm_end, total_beats, sr):
    """Build ``beat -> sample`` for a section, honoring an optional tempo ramp.

    With no ``bpm_end`` (or one equal to ``bpm``) tempo is constant and a beat
    maps linearly to samples — identical to the old ``round(beat*spb*sr)``. When
    ``bpm_end`` differs, tempo changes linearly *in bpm* across the section, so
    the beat->time map is the integral of its reciprocal: an accelerando
    (``bpm_end > bpm``) that drives into a climax, or a ritardando that relaxes.
    """
    bpm0 = float(bpm)
    if not bpm_end or float(bpm_end) == bpm0 or total_beats <= 0:
        spb = _spb(bpm0)
        return lambda beat: int(round(beat * spb * sr))
    k = (float(bpm_end) - bpm0) / total_beats  # bpm slope per beat
    scale = 60.0 / k

    def beat_to_sample(beat):
        # time(beat) = ∫₀ᵇ 60/(bpm0 + k·x) dx = (60/k)·ln((bpm0 + k·beat)/bpm0)
        return int(round(scale * np.log((bpm0 + k * beat) / bpm0) * sr))

    return beat_to_sample


# --- Swing / groove ----------------------------------------------------------

def _swing_beat(beat: float, swing: float) -> float:
    """Warp a straight beat position into a swung one (shuffle feel).

    Swing is a piecewise-linear time-warp *within each quarter-note beat*: the
    straight eighth-note midpoint (``0.5``) is pushed later to ``0.5 + swing*0.5``,
    with the two halves of the beat stretched/squeezed linearly to match. So the
    on-beat eighth lengthens and the off-beat eighth is delayed — the long-short
    lilt of a shuffle. ``swing`` in ``[0, 1)``: ``0`` = straight, ``~1/3`` = a
    triplet-feel hard swing (off-beat lands at 2/3).

    Integer beat boundaries are fixed points, so a section's total length is
    unchanged. Working in beat-space (before the beat->sample map) means one wrap
    swings every part kind at once — melody eighths, arp sixteenths, drum
    off-hats — and composes with the ``bpm_end`` tempo ramp downstream.
    """
    if swing <= 0:
        return beat
    whole = np.floor(beat)
    frac = beat - whole
    pivot = 0.5 + swing * 0.5
    if frac <= 0.5:
        warped = frac * (pivot / 0.5)
    else:
        warped = pivot + (frac - 0.5) * ((1.0 - pivot) / 0.5)
    return float(whole + warped)


# --- Automation envelopes ----------------------------------------------------

def _automation_curve(env: dict, n: int, sr: int) -> np.ndarray:
    """Build a length-``n`` per-sample envelope for one automation target.

    Two forms (a sibling to ``vibrato``/``tremolo`` in style):

    * **ramp** ``{"from": x, "to": y, "shape": "linear"|"exp"}`` — a swell, a
      filter opening: interpolate across the whole section, linearly or
      geometrically (``exp`` sweeps musically over wide ranges like cutoff Hz).
    * **lfo** ``{"lfo": {"rate", "depth", "center", "shape"}}`` — a cyclic move
      (auto-pan, wah, gain wobble) around ``center`` with amplitude ``depth``.
    """
    lfo_spec = env.get("lfo")
    if lfo_spec is not None:
        center = float(lfo_spec.get("center", 0.0))
        depth = float(lfo_spec.get("depth", 0.0))
        rate = float(lfo_spec.get("rate", 1.0))
        return center + depth * synth.lfo(rate, n, sr, lfo_spec.get("shape", "sine"))
    start = float(env.get("from", 0.0))
    end = float(env.get("to", start))
    if env.get("shape") == "exp" and start > 0 and end > 0:
        return start * (end / start) ** np.linspace(0.0, 1.0, n)
    return np.linspace(start, end, n)


# --- Part renderers ----------------------------------------------------------

def _render_melody(events, patch, b2s, sr, section_samples, filter_env=None):
    """Render a sequence of [pitch, beats, vel] events laid end to end.

    ``filter_env`` (optional length-``section_samples`` array) automates the
    lowpass cutoff: each note's cutoff is sampled at its onset, so a filter sweep
    steps per note-onset — ideal for leads/arps/plucks where sweeps live.
    """
    buf = np.zeros(section_samples, dtype=np.float64)
    beat = 0.0
    for ev in events:
        pitch, dur_beats = ev[0], ev[1]
        vel = ev[2] if len(ev) > 2 else DEFAULT_VELOCITY
        start = b2s(beat)
        if pitch is not None:  # None -> rest
            dur = max(1, b2s(beat + dur_beats) - start) / sr
            note_patch = patch
            if filter_env is not None:
                cutoff = float(filter_env[min(max(start, 0), section_samples - 1)])
                note_patch = {**patch, "filter": cutoff}
            note = render_note(theory.note_to_freq(pitch), dur, note_patch, sr)
            _place(buf, note * vel, start)
        beat += dur_beats
    return buf


def _render_chords(symbols, patch, b2s, sr, section_samples, chord_beats,
                   total_beats, octave, transpose):
    """Render chord symbols in sequence, each held for ``chord_beats``, tiled."""
    buf = np.zeros(section_samples, dtype=np.float64)
    beat = 0.0
    i = 0
    while beat < total_beats - 1e-6:
        sym = symbols[i % len(symbols)]
        start = b2s(beat)
        dur = max(1, b2s(min(beat + chord_beats, total_beats)) - start) / sr
        for note_name in theory.chord_notes(sym, octave):
            if transpose:
                note_name = theory.transpose(note_name, transpose)
            note = render_note(theory.note_to_freq(note_name), dur, patch, sr)
            _place(buf, note * (DEFAULT_VELOCITY / 2.0), start)
        beat += chord_beats
        i += 1
    return buf


# --- Arpeggiator -------------------------------------------------------------

def _arp_order(pool, pattern):
    """Order a chord's pitch ``pool`` into the traversal the arp cycles through."""
    if isinstance(pattern, list):  # explicit step indices into the pool
        n = len(pool)
        return [pool[int(i) % n] for i in pattern]
    p = (pattern or "up").lower()
    if p == "down":
        return list(reversed(pool))
    if p == "updown":  # ascend then descend without repeating the endpoints
        return list(pool) if len(pool) <= 2 else list(pool) + list(reversed(pool))[1:-1]
    if p == "downup":
        d = list(reversed(pool))
        return d if len(pool) <= 2 else d + list(pool)[1:-1]
    return list(pool)  # "up" (default)


def _arp_events(symbols, total_beats, chord_beats, rate, pattern, octaves, octave):
    """Expand chord symbols into an arpeggiated ``[pitch, beats]`` event list.

    Each symbol owns a ``chord_beats`` window; within it the chord's notes
    (spanning ``octaves``, ordered by ``pattern``) are struck every ``rate``
    beats, cycling until that window — and finally the section — ends. Steps are
    clipped at window/section boundaries so the stream is gapless and exactly
    fills the section. This is the continuous broken-chord shimmer that block
    ``chords`` can't produce.
    """
    events = []
    beat = 0.0
    i = 0
    while beat < total_beats - 1e-6:
        base = theory.chord_notes(symbols[i % len(symbols)], octave)
        pool = [theory.transpose(n, 12 * o)
                for o in range(max(1, octaves)) for n in base]
        order = _arp_order(pool, pattern)
        window_end = min(beat + chord_beats, total_beats)
        k = 0
        while beat < window_end - 1e-6:
            step = min(rate, window_end - beat)
            events.append([order[k % len(order)], step])
            beat += step
            k += 1
        i += 1
    return events


# --- Soundfont (part-level) renderers ---------------------------------------

def _melody_schedule(events, b2s):
    """Turn a sequence of [pitch, beats, vel?] into scheduled soundfont notes.

    Notes are laid end to end (the same timing as :func:`_render_melody`);
    returns ``(start_sample, dur_samples, midi, velocity)`` tuples, skipping rests.
    """
    sched = []
    beat = 0.0
    for ev in events:
        pitch, dur_beats = ev[0], ev[1]
        vel = ev[2] if len(ev) > 2 else DEFAULT_VELOCITY
        if pitch is not None:
            start = b2s(beat)
            sched.append((start, max(1, b2s(beat + dur_beats) - start),
                          theory.note_to_midi(pitch), int(round(vel * 127))))
        beat += dur_beats
    return sched


def _chord_schedule(symbols, b2s, total_beats, chord_beats, octave, transpose):
    """Schedule tiled chord symbols as simultaneous soundfont notes."""
    sched = []
    beat = 0.0
    i = 0
    while beat < total_beats - 1e-6:
        start = b2s(beat)
        dur = max(1, b2s(min(beat + chord_beats, total_beats)) - start)
        for note_name in theory.chord_notes(symbols[i % len(symbols)], octave):
            if transpose:
                note_name = theory.transpose(note_name, transpose)
            sched.append((start, dur, theory.note_to_midi(note_name),
                          int(round(DEFAULT_VELOCITY * 127))))
        beat += chord_beats
        i += 1
    return sched


def _render_drums(voices, b2s, section_samples, bpb, total_beats, cache):
    """Render per-voice step patterns, tiled across the whole section."""
    buf = np.zeros(section_samples, dtype=np.float64)
    n_bars = max(1, int(round(total_beats / bpb)))
    for voice, pattern in voices.items():
        steps = len(pattern)
        if steps == 0:
            continue
        for bar in range(n_bars):
            for s, ch in enumerate(pattern):
                if ch in ".-":
                    continue
                sample = cache["ohat" if ch == "o" else voice]
                start = b2s(bar * bpb + (s / steps) * bpb)
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
    """Render one section (all its parts) to a stereo buffer.

    A section may override tempo (``bpm``, plus ``bpm_end`` for a linear ramp)
    and set ``transpose`` (semitones) applied to every pitched part — the two
    levers behind a driving-then-modulating climax. ``swing`` (track- or
    section-level) shuffles the off-beats.
    """
    bpm = float(section.get("bpm", track["bpm"]))
    bpb = beats_per_bar(track["time_signature"])
    total_beats = section["bars"] * bpb
    b2s_raw = _tempo_map(bpm, section.get("bpm_end"), total_beats, sr)
    swing = float(section.get("swing", track.get("swing", 0.0)))
    # Swing warps beat positions before the sample map, so it grooves every part
    # kind at once; identity on integer beats, so section length is untouched.
    b2s = (lambda beat: b2s_raw(_swing_beat(beat, swing))) if swing else b2s_raw
    section_samples = max(1, b2s(total_beats))
    sec_transpose = int(section.get("transpose", 0))
    stereo = np.zeros((section_samples, 2), dtype=np.float64)

    for part in section.get("parts", {}).values():
        patch = track["palette"][part["instrument"]]
        pan = float(part.get("pan", 0.0))
        gain = float(part.get("gain", patch.get("gain", 0.8)))
        octave = int(part.get("octave", patch.get("octave", 3)))
        is_sf = patch.get("engine") in PART_ENGINES
        auto = part.get("automation") or {}
        # gain/pan automate at the mix stage (exact, every engine); a filter
        # sweep is sampled per note-onset on the numpy melody path only.
        filter_env = (_automation_curve(auto["filter"], section_samples, sr)
                      if "filter" in auto and not is_sf else None)

        if "drums" in part:
            mono = _render_drums(part["drums"], b2s, section_samples, bpb,
                                 total_beats, drum_cache)
        elif "chords" in part:
            chord_beats = theory.parse_beats(part.get("chord_beats", bpb))
            if is_sf:
                sched = _chord_schedule(part["chords"], b2s, total_beats,
                                        chord_beats, octave, sec_transpose)
                mono = soundfont.render_scheduled(sched, patch, sr, section_samples)
            else:
                mono = _render_chords(part["chords"], patch, b2s, sr, section_samples,
                                      chord_beats, total_beats, octave, sec_transpose)
        else:
            if "arp" in part:
                events = _arp_events(
                    part["arp"], total_beats,
                    theory.parse_beats(part.get("chord_beats", bpb)),
                    theory.parse_beats(part.get("rate", 0.25)),
                    part.get("pattern", "up"), int(part.get("octaves", 1)), octave)
            elif "motif" in part:
                motif = track["motifs"][part["motif"]]
                events = list(motif["notes"] if isinstance(motif, dict) else motif)
                sl = part.get("slice")
                if sl:  # quote only part of the motif, e.g. [0, 3] = first 3 notes
                    events = events[sl[0]:sl[1]]
            else:
                events = list(part["notes"])
            # Normalize durations (numbers or "1/3" fractions) to floats up front,
            # so transforms and renderers only ever see numbers.
            events = [[e[0], theory.parse_beats(e[1]), *e[2:]] for e in events]
            if "arp" not in part:  # generated arps aren't leitmotif material
                events = _transform(events, part)
            events = events * int(part.get("repeat", 1))
            if sec_transpose:
                events = [[e[0] if e[0] is None else theory.transpose(e[0], sec_transpose),
                           *e[1:]] for e in events]
            if is_sf:
                mono = soundfont.render_scheduled(_melody_schedule(events, b2s),
                                                  patch, sr, section_samples)
            else:
                mono = _render_melody(events, patch, b2s, sr, section_samples,
                                      filter_env)

        mono = apply_part_effects(mono, patch, sr)[:section_samples]
        if mono.shape[0] < section_samples:
            mono = np.pad(mono, (0, section_samples - mono.shape[0]))
        # gain/pan automation (exact, per-sample). gain rides as an envelope on
        # top of the part's balance scalar; pan sets absolute position.
        gain_val = gain
        if "gain" in auto:
            gain_val = gain * _automation_curve(auto["gain"], section_samples, sr)
        pan_val = pan
        if "pan" in auto:
            pan_val = np.clip(_automation_curve(auto["pan"], section_samples, sr),
                              -1.0, 1.0)
        stereo += _pan(mono * gain_val, pan_val)
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
