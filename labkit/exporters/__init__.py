"""Engine exporters — one module per target (Godot today; Tiled/Unity next).

Each exporter exposes ``export(records, dist_root, name) -> pack_dir`` and is
registered in ``labkit/export.py``. See that module for the record shape.
"""
