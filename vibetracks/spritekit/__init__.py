"""VibeTracks spritekit — model characters as JSON, composite them to PNG sheets.

The sprite counterpart of the audio engine: a JSON *sprite spec* describes a
character as a stack of LPC layers, and the compositor renders it to a Universal-LPC
832x1344 spritesheet. The ``lpc`` engine (which reads real art via Pillow) is the
direct analogue of the optional ``soundfont`` engine; the core spec/validate path
depends only on numpy, exactly like the audio core.
"""
