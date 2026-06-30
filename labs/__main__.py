"""Top-level dispatcher across every Lab in this repo.

    python -m labs                       # list the Labs
    python -m labs <lab> <command...>    # run a Lab's CLI
    python -m labs validate              # validate every Lab's specs

Each Lab keeps its own CLI (``python -m vibetracks ...``, ``python -m
pixeltracks ...``); this dispatcher is the unified front door that makes the
multi-Lab structure visible and routes to them by name.
"""

from __future__ import annotations

import sys

from labkit.registry import LABS, find_lab


def _print_labs() -> None:
    print("VibeTracks — a multi-Lab game-artifact workshop.\n")
    print("Labs:")
    width = max(len(lab.name) for lab in LABS)
    for lab in LABS:
        print(f"  {lab.name:<{width}}  {lab.summary}")
        print(f"  {'':<{width}}  artifact: {lab.artifact}; "
              f"assets in {lab.assets_dir}/<group>/{lab.bible_file}")
    print("\nRun a Lab:   python -m labs <lab> <command>   "
          "(e.g. python -m labs pixeltracks render-all)")
    print("Or directly: python -m <lab> <command>")
    print("All at once: python -m labs validate")


def _validate_all() -> int:
    rc = 0
    for lab in LABS:
        print(f"=== {lab.name} ===")
        rc |= lab.main(["validate"]) or 0
    return rc


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "list"):
        _print_labs()
        return 0
    if argv[0] == "validate":
        return _validate_all()
    lab = find_lab(argv[0])
    return lab.main(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
