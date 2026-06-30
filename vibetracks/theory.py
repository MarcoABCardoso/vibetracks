"""Music theory helpers: note names, frequencies, scales, chords, transposition.

Everything here is pure Python (no numpy) so it is easy to test and reason about.
Pitches are written as note names like ``"A4"``, ``"C#5"``, ``"Bb3"`` where the
number is the octave (scientific pitch notation, middle C = ``C4``). A4 = 440 Hz
in 12-tone equal temperament.
"""

from __future__ import annotations

# Semitone offset of each natural note from C within an octave.
_NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# Scale formulas as semitone offsets from the root.
SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],          # natural minor / aeolian
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "pentatonic_minor": [0, 3, 5, 7, 10],
    "pentatonic_major": [0, 2, 4, 7, 9],
    "chromatic": list(range(12)),
}

# Aliases accepted in the "key" field, e.g. "A minor", "C# major".
_MODE_ALIASES = {
    "maj": "major",
    "major": "major",
    "min": "minor",
    "minor": "minor",
    "m": "minor",
    "harmonic": "harmonic_minor",
    "harmonic_minor": "harmonic_minor",
}


def note_to_midi(name: str) -> int:
    """Convert a note name like ``"A4"`` to a MIDI note number (A4 -> 69)."""
    name = name.strip()
    if not name:
        raise ValueError("empty note name")
    letter = name[0].upper()
    if letter not in _NATURAL:
        raise ValueError(f"bad note letter in {name!r}")
    semis = _NATURAL[letter]
    i = 1
    while i < len(name) and name[i] in "#b":
        semis += 1 if name[i] == "#" else -1
        i += 1
    octave_part = name[i:]
    if not (octave_part.lstrip("-").isdigit()):
        raise ValueError(f"bad octave in note {name!r}")
    octave = int(octave_part)
    # MIDI: C-1 = 0, so C4 = 60, A4 = 69.
    return (octave + 1) * 12 + semis


def midi_to_freq(midi: float) -> float:
    """MIDI note number to frequency in Hz (A4 = MIDI 69 = 440 Hz)."""
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def note_to_freq(name: str) -> float:
    """Note name (e.g. ``"C#4"``) to frequency in Hz."""
    return midi_to_freq(note_to_midi(name))


def transpose(name: str, semitones: int) -> str:
    """Transpose a note name by ``semitones`` and return a new note name."""
    return midi_to_name(note_to_midi(name) + semitones)


_SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_name(midi: int) -> str:
    """MIDI note number to a sharp-spelled note name (69 -> ``"A4"``)."""
    octave = midi // 12 - 1
    return f"{_SHARP_NAMES[midi % 12]}{octave}"


def parse_key(key: str) -> tuple[str, str]:
    """Parse ``"A minor"`` -> (root_note_without_octave, scale_name)."""
    parts = key.strip().split()
    if not parts:
        raise ValueError("empty key")
    root = parts[0]
    mode = "major"
    if len(parts) > 1:
        mode = _MODE_ALIASES.get(parts[1].lower(), parts[1].lower())
    if mode not in SCALES:
        raise ValueError(f"unknown mode {mode!r} in key {key!r}")
    return root, mode


def scale_notes(key: str, octave: int = 4) -> list[str]:
    """Return one octave of note names for ``key`` starting at ``octave``."""
    root, mode = parse_key(key)
    root_midi = note_to_midi(f"{root}{octave}")
    return [midi_to_name(root_midi + step) for step in SCALES[mode]]


# --- Chord parsing -----------------------------------------------------------

# Chord quality -> intervals from the chord root (in semitones).
_CHORD_QUALITIES = {
    "": [0, 4, 7],          # major triad (default)
    "maj": [0, 4, 7],
    "M": [0, 4, 7],
    "m": [0, 3, 7],         # minor triad
    "min": [0, 3, 7],
    "dim": [0, 3, 6],
    "aug": [0, 4, 8],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
    "7": [0, 4, 7, 10],     # dominant 7th
    "maj7": [0, 4, 7, 11],
    "m7": [0, 3, 7, 10],
    "min7": [0, 3, 7, 10],
    "add9": [0, 4, 7, 14],
    "madd9": [0, 3, 7, 14],
    "5": [0, 7],            # power chord
}


def chord_notes(symbol: str, octave: int = 3) -> list[str]:
    """Expand a chord symbol like ``"Am"``/``"Fmaj7"`` to a list of note names.

    The chord root is placed in ``octave``. Quality defaults to major.
    """
    symbol = symbol.strip()
    if not symbol:
        raise ValueError("empty chord symbol")
    # Root is the letter plus any accidentals.
    i = 1
    while i < len(symbol) and symbol[i] in "#b":
        i += 1
    root, quality = symbol[:i], symbol[i:]
    if quality not in _CHORD_QUALITIES:
        raise ValueError(f"unknown chord quality {quality!r} in {symbol!r}")
    root_midi = note_to_midi(f"{root}{octave}")
    return [midi_to_name(root_midi + iv) for iv in _CHORD_QUALITIES[quality]]
