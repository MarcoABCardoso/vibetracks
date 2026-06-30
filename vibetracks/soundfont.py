"""Stage 2 — sample-based realism via FluidSynth + a General MIDI soundfont.

The pure-numpy engines in :mod:`vibetracks.synth` synthesize every timbre from
math, which is wonderful for synths but can only approximate acoustic
instruments. This module adds a ``soundfont`` engine: real recorded multisamples
(piano, strings, brass, woodwinds, harp, mallets, …) played back through
FluidSynth from a `.sf2` soundfont.

It is intentionally **optional** — the core retro/synth path depends only on
numpy + scipy. FluidSynth and ``pyfluidsynth`` are imported lazily, and a missing
library or soundfont raises :class:`SoundfontError` with install instructions
only when a track actually asks for the engine. Validation never imports it.

Unlike the numpy engines (rendered per note), a soundfont part is rendered as a
whole: notes are scheduled on a sample timeline and streamed out of one cached,
reused FluidSynth instance. The result is downmixed to mono so it flows through
the same pan / effects / master-normalize pipeline as every other part.
"""

from __future__ import annotations

import os

import numpy as np

# Standard locations the FluidR3_GM soundfont lands in on Debian/Ubuntu when
# ``fluidsynth`` (or ``fluid-soundfont-gm``) is installed. Overridable per patch
# (``"soundfont"``) or via the VIBETRACKS_SOUNDFONT environment variable.
DEFAULT_SOUNDFONTS = (
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/default-GM.sf2",
)

# FluidSynth's master gain is conservative; this lifts a velocity-100 note to a
# peak comparable to the numpy engines so soundfont and synth parts mix at sane
# relative levels before the master normalize (per-part ``gain`` still balances).
SYNTH_GAIN = 2.4

_INSTALL_HINT = (
    "the soundfont engine needs FluidSynth + a General MIDI soundfont.\n"
    "  install:  sudo apt-get install -y fluidsynth && pip install pyfluidsynth\n"
    "  (that also provides /usr/share/sounds/sf2/FluidR3_GM.sf2)\n"
    "  or point VIBETRACKS_SOUNDFONT at a .sf2 file."
)


class SoundfontError(RuntimeError):
    """Raised when the soundfont engine is requested but unavailable."""


def find_soundfont(path: str | None = None) -> str:
    """Resolve the soundfont path: explicit arg, env var, then known defaults."""
    candidates = [path] if path else []
    env = os.environ.get("VIBETRACKS_SOUNDFONT")
    if env:
        candidates.append(env)
    candidates.extend(DEFAULT_SOUNDFONTS)
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    raise SoundfontError(
        f"no soundfont found (looked in {[c for c in candidates if c]}).\n  {_INSTALL_HINT}")


def available(path: str | None = None) -> bool:
    """True if pyfluidsynth imports and a soundfont can be found (no exceptions)."""
    try:
        import fluidsynth  # noqa: F401
        find_soundfont(path)
        return True
    except (ImportError, SoundfontError):
        return False


# A FluidSynth instance owns a loaded soundfont (~140 MB) — expensive to build,
# so cache one per (path, sample-rate) and reuse it across parts, resetting state
# between renders. Keyed cache lives for the process.
_SYNTHS: dict = {}


def _get_synth(path: str, sr: int):
    key = (path, sr)
    cached = _SYNTHS.get(key)
    if cached is not None:
        return cached
    try:
        import fluidsynth
    except ImportError as e:
        raise SoundfontError(f"{e}\n  {_INSTALL_HINT}") from e
    fs = fluidsynth.Synth(samplerate=float(sr), gain=SYNTH_GAIN)
    # Drive FluidSynth dry; our own effects/reverb own the space so soundfont and
    # synth parts share one consistent ambience.
    for setting in ("synth.reverb.active", "synth.chorus.active"):
        try:
            fs.setting(setting, 0)
        except Exception:  # pragma: no cover - older bindings ignore unknown settings
            pass
    sfid = fs.sfload(path)
    if sfid == -1:  # FluidSynth returns -1 on a load failure rather than raising.
        raise SoundfontError(f"failed to load soundfont {path!r}")
    _SYNTHS[key] = (fs, sfid)
    return fs, sfid


def render_scheduled(notes, patch: dict, sr: int, n_samples: int) -> np.ndarray:
    """Render scheduled notes through the soundfont to a mono float buffer.

    ``notes`` is a list of ``(start_sample, dur_samples, midi, velocity)`` tuples
    (velocity 1-127). Notes are streamed out of FluidSynth in time order; a
    release tail past ``n_samples`` lets sustains ring before the buffer is
    trimmed to the section length.
    """
    path = find_soundfont(patch.get("soundfont"))
    fs, sfid = _get_synth(path, sr)
    fs.system_reset()  # clear any voices/state left by the previous part
    bank = int(patch.get("bank", 0))
    program = int(patch.get("program", 0))
    fs.program_select(0, sfid, bank, program)

    # Flatten to a sorted event stream: (sample, is_noteon, midi, vel).
    events = []
    for start, dur, midi, vel in notes:
        start = max(0, int(start))
        end = start + max(1, int(dur))
        events.append((start, 1, int(midi), int(np.clip(vel, 1, 127))))
        events.append((end, 0, int(midi), 0))
    # Note-offs before note-ons at the same instant so a repeated pitch retriggers.
    events.sort(key=lambda e: (e[0], e[1]))

    tail = int(float(patch.get("release", 1.2)) * sr)
    total = n_samples + tail
    chunks = []
    cursor = 0
    for sample, is_on, midi, vel in events:
        target = min(sample, total)
        if target > cursor:
            chunks.append(fs.get_samples(target - cursor))
            cursor = target
        if cursor >= total:
            break
        if is_on:
            fs.noteon(0, midi, vel)
        else:
            fs.noteoff(0, midi)
    if cursor < total:
        chunks.append(fs.get_samples(total - cursor))
    fs.system_reset()

    if not chunks:
        return np.zeros(n_samples, dtype=np.float64)
    inter = np.concatenate(chunks).astype(np.float64) / 32768.0
    stereo = inter.reshape(-1, 2)
    mono = stereo.mean(axis=1)
    if mono.shape[0] >= n_samples:
        return mono[:n_samples]
    return np.pad(mono, (0, n_samples - mono.shape[0]))
