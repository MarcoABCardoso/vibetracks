"""Colour helpers: hex parsing, named palettes, and shading.

This is PixelTracks' equivalent of VibeTracks' ``theory`` module. Where music
theory turns note names into frequencies and knows about scales, here we turn
hex strings into RGBA and know about *palettes* — the named set of colours every
sprite in a group shares. A sprite never names a raw colour; it names a palette
entry (``"armor"``, ``"cloak"``), exactly as a track names an instrument. That
indirection is what makes the leitmotif move — a **palette swap** — possible:
change the bible's colours in one place and every sprite recolours in step.

Everything here is pure Python (no numpy) so it is trivial to test and reason
about, mirroring ``theory.py``.
"""

from __future__ import annotations

RGBA = tuple  # (r, g, b, a), each 0..255

TRANSPARENT: RGBA = (0, 0, 0, 0)


def parse_hex(value: str) -> RGBA:
    """Parse ``#rgb`` / ``#rrggbb`` / ``#rrggbbaa`` into an ``(r, g, b, a)`` tuple.

    A bare ``"transparent"`` (or ``"none"``) yields a fully transparent colour.
    """
    s = value.strip()
    if s.lower() in ("transparent", "none"):
        return TRANSPARENT
    if not s.startswith("#"):
        raise ValueError(f"colour must start with '#': {value!r}")
    h = s[1:]
    if len(h) == 3:  # #rgb shorthand
        h = "".join(c * 2 for c in h)
    if len(h) not in (6, 8):
        raise ValueError(f"colour must be #rgb, #rrggbb or #rrggbbaa: {value!r}")
    try:
        nums = [int(h[i:i + 2], 16) for i in range(0, len(h), 2)]
    except ValueError as e:
        raise ValueError(f"bad hex digits in {value!r}: {e}") from e
    if len(nums) == 3:
        nums.append(255)
    return tuple(nums)


def to_hex(rgba: RGBA) -> str:
    """Inverse of :func:`parse_hex` (always ``#rrggbbaa``)."""
    return "#" + "".join(f"{c:02x}" for c in rgba)


def resolve_palette(colours: dict) -> dict:
    """Map a ``{name: "#hex"}`` palette to ``{name: (r, g, b, a)}``.

    Raises :class:`ValueError` naming the offending entry on a bad colour, so the
    validator can surface it the way a bad pitch is surfaced in music.
    """
    out = {}
    for name, value in colours.items():
        try:
            out[name] = parse_hex(value)
        except ValueError as e:
            raise ValueError(f"palette colour {name!r}: {e}") from e
    return out


def shade(rgba: RGBA, amount: float) -> RGBA:
    """Lighten (``amount`` > 0) or darken (``< 0``) a colour, keeping its alpha.

    ``amount`` is a fraction in roughly ``[-1, 1]``: ``+0.2`` mixes 20% toward
    white, ``-0.2`` mixes 20% toward black. The cheap building block for light
    direction and shading ramps.
    """
    r, g, b, a = rgba
    if amount >= 0:
        mix = lambda c: round(c + (255 - c) * amount)
    else:
        mix = lambda c: round(c * (1.0 + amount))
    return (max(0, min(255, mix(r))),
            max(0, min(255, mix(g))),
            max(0, min(255, mix(b))), a)
