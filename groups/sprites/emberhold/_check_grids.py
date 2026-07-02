#!/usr/bin/env python3
"""Author-time sanity check for emberhold pixel grids.

The engine rejects ragged grids at render time but does NOT name the offending
motif/row (shapes.normalize_grid raises a bare ValueError). This walks a spec's
`motifs` and any `pixels` layers/frames and reports every grid whose rows are not
all the same length, naming the motif/layer + the offending row indices. Run it
after editing grids, before render:

    python groups/sprites/emberhold/_check_grids.py                 # artbook + all sprites
    python groups/sprites/emberhold/_check_grids.py <file.json>...  # just these
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _check_grid(name, rows):
    problems = []
    if not rows:
        return [f"{name}: empty grid"]
    width = len(rows[0])
    for i, row in enumerate(rows):
        if len(row) != width:
            problems.append(
                f"{name}: row {i} is {len(row)} wide, expected {width}  ->  {row!r}"
            )
    return problems


def _walk(spec, source):
    problems = []
    for mname, motif in (spec.get("motifs") or {}).items():
        if isinstance(motif, dict) and "pixels" in motif:
            problems += _check_grid(f"{source} motif '{mname}'", motif["pixels"])

    def layers_of(container):
        return container.get("layers") or []

    def check_layers(layers, where):
        out = []
        for j, layer in enumerate(layers):
            if isinstance(layer, dict) and "pixels" in layer:
                lname = layer.get("name", f"#{j}")
                out += _check_grid(f"{source} {where} layer '{lname}'", layer["pixels"])
        return out

    problems += check_layers(layers_of(spec), "layer")
    for f, frame in enumerate(spec.get("frames") or []):
        problems += check_layers(layers_of(frame), f"frame {f}")
    return problems


def main(argv):
    if argv:
        files = [Path(a) for a in argv]
    else:
        files = [HERE / "artbook.json"] + sorted((HERE / "sprites").glob("*.json"))
    all_problems = []
    for f in files:
        try:
            spec = json.loads(f.read_text())
        except Exception as e:  # noqa: BLE001
            all_problems.append(f"{f}: could not parse ({e})")
            continue
        all_problems += _walk(spec, f.name)
    if all_problems:
        print("RAGGED GRIDS:")
        for p in all_problems:
            print("  " + p)
        return 1
    print(f"ok: all grids rectangular across {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
