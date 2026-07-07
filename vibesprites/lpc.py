"""The ``lpc`` layer engine — composite real LPC art via Pillow.

The sprite analogue of :mod:`vibetracks.soundfont`. Where the numpy synth engines
generate every timbre from math, and the ``soundfont`` engine instead *plays back
real recorded samples*, the ``lpc`` engine *plays back real drawn pixel art*: the
Liberated Pixel Cup layer PNGs (bodies, hair, clothes, weapons…). It is the direct
counterpart of the soundfont engine, not of a procedural one.

Like soundfont, it is intentionally **optional**. The core spec/validate path
depends only on numpy; Pillow is imported lazily and a missing library raises
:class:`LPCError` with install instructions only when a character actually asks to
be rendered. Validation never imports Pillow.

Layer art is **fetched on demand**, not vendored: the copyleft LPC PNGs are never
committed to this repo. A missing layer is downloaded from the cast's ``remote``
base into a local cache (gitignored) and reused thereafter, so a first render needs
the network but repeats are offline. Point ``$VIBESPRITES_ASSETS`` at a local LPC
checkout to render fully offline. Attribution/copyleft still apply to anything you
distribute — see each cast's ``CREDITS.csv``.

Reading source art needs Pillow; *writing* the finished sheet does not
(:mod:`vibesprites.pngio` uses the stdlib) — the same split as
soundfont-reads vs. wavio-writes. Fetching uses only the stdlib (``urllib``).
"""

from __future__ import annotations

import os
import ssl
import tempfile
import urllib.parse
import urllib.request

import numpy as np

from . import layout

# A relative layer ``source`` (e.g. ``body/male/light.png``) is resolved against,
# in order: a local checkout in $VIBESPRITES_ASSETS, the download cache, then the
# remote base (fetched into the cache). The default remote is the upstream LPC art.
ASSETS_ENV = "VIBESPRITES_ASSETS"       # a local LPC checkout, for offline rendering
REMOTE_ENV = "VIBESPRITES_REMOTE"       # override the remote base URL
CACHE_ENV = "VIBESPRITES_CACHE"         # override the download cache directory
DEFAULT_REMOTE = ("https://raw.githubusercontent.com/"
                  "jrconway3/Universal-LPC-spritesheet/master")

_INSTALL_HINT = (
    "the lpc engine needs Pillow to read layer art.\n"
    "  install:  pip install Pillow   (or:  pip install vibetracks[sprites])\n"
    "  layer art is fetched from the cast's 'remote' base; set $VIBESPRITES_ASSETS\n"
    "  to a local LPC checkout to render offline."
)


class LPCError(RuntimeError):
    """Raised when the lpc engine is requested but unavailable or misconfigured."""


def available() -> bool:
    """True if Pillow imports (no exceptions) — used to gate rendering and tests."""
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def _is_url(s: str) -> bool:
    return s.startswith(("http://", "https://"))


def cache_dir(cast_dir: str | None = None) -> str:
    """The download cache: ``$VIBESPRITES_CACHE``, else ``<cast>/.cache``."""
    env = os.environ.get(CACHE_ENV)
    if env:
        return env
    if cast_dir:
        return os.path.join(cast_dir, ".cache")
    return os.path.join(tempfile.gettempdir(), "vibesprites-cache")


def fetch_asset(url: str, dest: str) -> str:
    """Download ``url`` to ``dest`` (atomic), returning ``dest``. Stdlib only."""
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    try:
        ctx = ssl.create_default_context()  # honors $SSL_CERT_FILE / system CAs
        with urllib.request.urlopen(url, context=ctx, timeout=30) as r:
            data = r.read()
    except Exception as e:  # network / TLS / HTTP error
        raise LPCError(f"failed to fetch layer art {url!r}: {e}\n  {_INSTALL_HINT}") from e
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)
    return dest


def find_asset(source: str, cast_dir: str | None = None,
               remote: str | None = None) -> str:
    """Resolve a layer's ``source`` to a real file, fetching it if necessary.

    Order: an explicit ``http(s)`` ``source`` (cached by URL) → a local checkout in
    ``$VIBESPRITES_ASSETS`` → the download cache → fetched from ``remote`` (or
    ``$VIBESPRITES_REMOTE``, else the default LPC base) into the cache.
    """
    cache = cache_dir(cast_dir)

    if _is_url(source):
        rel = urllib.parse.urlparse(source).path.lstrip("/")
        dest = os.path.join(cache, rel)
        return dest if os.path.isfile(dest) else fetch_asset(source, dest)

    if os.path.isabs(source):
        if os.path.isfile(source):
            return source
        raise LPCError(f"layer asset not found: {source!r}")

    # A local checkout wins over the cache (lets a user render fully offline).
    assets = os.environ.get(ASSETS_ENV)
    if assets:
        local = os.path.join(assets, source)
        if os.path.isfile(local):
            return local

    cached = os.path.join(cache, source)
    if os.path.isfile(cached):
        return cached

    base = remote or os.environ.get(REMOTE_ENV) or DEFAULT_REMOTE
    url = base.rstrip("/") + "/" + source.lstrip("/")
    return fetch_asset(url, cached)


def load_layer_sheet(path: str) -> np.ndarray:
    """Load an LPC layer PNG as an ``(h, w, 4)`` uint8 RGBA array.

    Palette-mode ("P") and other source modes are converted to RGBA so every layer
    composites uniformly.
    """
    try:
        from PIL import Image
    except ImportError as e:  # pragma: no cover - exercised only without Pillow
        raise LPCError(f"{e}\n  {_INSTALL_HINT}") from e
    with Image.open(path) as im:
        return np.asarray(im.convert("RGBA"), dtype=np.uint8)


def assemble_sheet(assemble: dict, cast_dir: str | None = None,
                   remote: str | None = None, anims=None) -> np.ndarray:
    """Build a sheet from a *split-per-animation* source.

    The modern LPC library stores one PNG per animation instead of one combined
    sheet, which unlocks thousands of assets (robes, cloaks, hats, and — crucially —
    the expanded poses jump/climb/run/idle…) the classic set lacks. This fetches each
    requested animation's file and pastes it at that animation's canonical row, so the
    result drops into the same compositor as a combined layer.

    Two on-disk conventions are supported via ``assemble = {"base", "color"?, "slot"?}``:

    * ``color`` set → ``<base>/<anim>/<color>.png`` — colour-split art (e.g. robes).
    * ``color`` absent → ``<base>/<anim>.png`` — a single recolorable sheet (e.g.
      bodies and armour, whose colour comes from a palette ``recolor``, not the path).

    ``anims`` selects which animations to pull (default: the classic six). Animations
    the source omits are skipped, leaving those rows transparent. Oversize-frame art
    (some weapons) does not fit the 64px grid and is out of scope here.
    """
    base = assemble["base"].rstrip("/")
    color = assemble.get("color")
    slot = assemble.get("slot")
    mid = f"{slot}/" if slot else ""
    anims = anims or layout.ANIMATIONS
    canvas = np.zeros((layout.sheet_rows(anims) * layout.FRAME, layout.WIDTH, 4),
                      dtype=np.uint8)
    placed = 0
    for name, _frames, _dirs in anims:
        sub = (f"{base}/{name}/{mid}{color}.png" if color
               else f"{base}/{mid}{name}.png")
        try:
            path = find_asset(sub, cast_dir, remote=remote)
        except LPCError:
            continue  # this source has no art for that animation
        _paste_animation(canvas, load_layer_sheet(path), name)
        placed += 1
    if placed == 0:
        raise LPCError(f"assemble found no animations under {base!r} "
                       f"(color {color!r}).\n  {_INSTALL_HINT}")
    return canvas


def _paste_animation(canvas: np.ndarray, sheet: np.ndarray, anim: str) -> None:
    """Paste a per-animation sheet into ``canvas`` at that animation's row block."""
    y = layout.animation_row(anim) * layout.FRAME
    h = min(sheet.shape[0], canvas.shape[0] - y)
    w = min(sheet.shape[1], canvas.shape[1])
    canvas[y:y + h, 0:w] = sheet[:h, :w]


def recolor(arr: np.ndarray, mapping: dict) -> np.ndarray:
    """Apply an LPC-style palette swap: ``{"#rrggbb": "#rrggbb", ...}``.

    Opaque source pixels matching a key colour are replaced by its value; alpha is
    preserved. This is the layer counterpart of a soundfont program change — same
    art, different colourway.
    """
    if not mapping:
        return arr
    out = arr.copy()
    rgb = out[..., :3]
    for src_hex, dst_hex in mapping.items():
        src = _hex_rgb(src_hex)
        dst = _hex_rgb(dst_hex)
        match = np.all(rgb == src, axis=-1)
        out[..., :3][match] = dst
    return out


def _hex_rgb(s: str) -> tuple:
    s = s.lstrip("#")
    if len(s) != 6:
        raise LPCError(f"recolor colour must be #rrggbb, got {s!r}")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
