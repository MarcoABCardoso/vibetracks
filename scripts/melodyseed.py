#!/usr/bin/env python3
"""Seed a raw melody from real entropy — so the tune isn't the model's default.

A language model asked to "write a nice theme" collapses onto its prior (in this
repo, an A-minor tonic-triad-up-then-step-down cliché) every time. The cure is to
take the melodic choices *out of the model's head*: roll them from a seeded RNG
and build the phrase from the roll, then hand-edit for musicality.

    python scripts/melodyseed.py <track-name>     # seed = track name -> reproducible
    python scripts/melodyseed.py                   # unseeded -> fresh every run

Prints the frame it rolled (key/mode) and a VibeTracks motif. Treat the output as
raw clay: keep the frame, then edit pitches for singability (see docs/composition.md
"Break the default"). It deliberately roams modes and roots you wouldn't default to.
"""
import random
import sys

MODES = {
    "minor": [0, 2, 3, 5, 7, 8, 10], "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10], "major": [0, 2, 4, 5, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10], "lydian": [0, 2, 4, 6, 7, 9, 11],
}
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def seed_phrase(rng, n=8):
    """Roll one 8-note, 8-beat phrase: a random walk landing on an open tone."""
    root = rng.choice(["C", "D", "E", "F", "G", "A"])
    mode = rng.choice(list(MODES))
    root_midi = 60 + NAMES.index(root)
    scale = [root_midi + 12 * o + s for o in range(2) for s in MODES[mode]]

    deg = rng.choice([0, 2, 4])                 # start stable, but not always the tonic
    degs, leaps = [deg], rng.randint(1, 2)      # budget of 1-2 leaps, rest are steps
    for i in range(1, n):
        if i == n - 1:                          # end OPEN (supertonic / dominant / leading)
            deg = rng.choice([1, 4, 6])
        elif leaps and rng.random() < 0.25:
            deg += rng.choice([-4, -3, 3, 4]); leaps -= 1
        else:
            deg += rng.choice([-2, -1, 1, 2])
        degs.append(max(0, min(len(scale) - 2, deg)))

    cell = rng.choice([[1, 1, 1, 0.5, 0.5, 1, 1, 2], [0.5, 0.5, 1, 1, 1, 1, 1, 2],
                       [1, 0.5, 0.5, 1, 1, 1, 1, 2], [2, 1, 1, 0.5, 0.5, 1, 1, 1]])
    notes = [[f"{NAMES[scale[d] % 12]}{scale[d] // 12 - 1}", dur]
             for d, dur in zip(degs, cell)]
    return root, mode, notes


def main():
    seed = sys.argv[1] if len(sys.argv) > 1 else None
    rng = random.Random(seed)
    root, mode, notes = seed_phrase(rng)
    print(f"# rolled frame: {root} {mode}   (seed: {seed!r})")
    print(f"# raw clay — keep the frame, edit pitches for singability")
    print('"notes": ' + str(notes).replace("'", '"'))


if __name__ == "__main__":
    main()
