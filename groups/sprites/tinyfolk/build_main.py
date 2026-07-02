"""Builder for the tinyfolk chibi hero.

Emits sprites/main.json: a shaded **form-skeleton** (head/torso/limbs/jerkin —
the volumes, auto-lit and connected by construction) plus a hand-pixelled
**overlay** (hair fringe + big glossy eyes + cheeks + mouth) pinned over the
head. Run:  python groups/sprites/tinyfolk/build_main.py
"""
import json
import os

W, H = 28, 30

# ---- head placement (the overlay is aligned to this) -------------------------
HEAD_TL = [4, 1]               # desired top-left of the head on the canvas
HEAD_SIZE = [20, 18]           # head spans x4..23, y1..18; centre ~ (13.5, 9.5)
HEAD_NECK = [10, 17]           # neck anchor in head-local coords
# The resolver pivot-pins a bone by `at`, so the root head's `at` is the world
# position of its pivot (the neck) = top-left + neck-local.
HEAD_AT = [HEAD_TL[0] + HEAD_NECK[0], HEAD_TL[1] + HEAD_NECK[1]]

# ---- the hand-pixelled hair + face overlay -----------------------------------
# One transparent 28x30 grid; hair painted first, then face features on top.
LEGEND = {
    "o": "outline", "w": "eyewhite", "g": "gleam", "c": "cheek",
    "r": "hair", "R": "hair_sh", "H": "hair_hi", "S": "skin_sh",
}


def blank():
    return [["."] * W for _ in range(H)]


def px(grid, x, y, ch):
    if ch != "." and 0 <= x < W and 0 <= y < H:
        grid[y][x] = ch


def stamp(grid, x0, y0, rows):
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            px(grid, x0 + dx, y0 + dy, ch)


def build_overlay():
    g = blank()

    # Hair cap: follow the top of the head circle. cx,cy,rx,ry match HEAD.
    cx, cy = 13.5, 9.5
    rx, ry = 10.0, 9.0
    for y in range(H):
        for x in range(W):
            nx, ny = (x - cx) / rx, (y - cy) / ry
            if nx * nx + ny * ny <= 1.0:
                # top of the scalp + sideburns down the sides
                if y <= 6 or (x <= cx - 7.0 and y <= 11) or (x >= cx + 6.5 and y <= 11):
                    ch = "H" if (nx < -0.2 and ny < -0.2) else ("R" if ny > 0.3 else "r")
                    px(g, x, y, ch)
    # A ragged fringe of bangs over the forehead (a few dipping locks).
    for x, yb in [(6, 7), (7, 8), (9, 7), (10, 8), (12, 7), (13, 8),
                  (15, 7), (16, 8), (18, 7), (19, 7), (20, 6)]:
        for y in range(1, yb + 1):
            if g[y][x] == ".":
                px(g, x, y, "r")
        px(g, x, yb, "R")

    # Brows: short hair-dark strokes lifted a row above each eye.
    stamp(g, 8, 7, ["RRR"])
    stamp(g, 15, 7, ["RR"])

    # --- Eyes: big and glossy, a clear nose-bridge gap between them -----------
    # o = dark iris/lid, g = white gleam (upper-left), w = eyewhite lower rim.
    # Near (left) eye — larger, faces the viewer.
    stamp(g, 8, 8, [
        ".oo.",
        "ogoo",
        "oowo",
        ".oo.",
    ])
    # Far (right) eye — smaller & foreshortened by the three-quarter turn.
    stamp(g, 15, 8, [
        "ooo",
        "ogo",
        "oow",
        ".o.",
    ])

    # Nose: a single soft shadow tick just off the near side of centre.
    px(g, 12, 11, "S")
    px(g, 12, 12, "S")

    # Rosy cheeks under the outer corner of each eye.
    for (x, y) in [(7, 11), (8, 11), (18, 10), (19, 10)]:
        if g[y][x] == ".":
            px(g, x, y, "c")

    # Mouth: a tiny upturned smile, a hair left of centre.
    stamp(g, 11, 14, ["o.o", ".o."])

    return ["".join(row) for row in g]


# ---- the form skeleton (volumes) ---------------------------------------------
def skeleton():
    return [
        # far arm first (behind the torso)
        {"name": "arm-far", "form": "capsule", "material": "tunic", "size": [4, 8],
         "anchors": {"shoulder": [2, 1], "hand": [2, 7]}, "pivot": "shoulder",
         "attach": {"to": "torso", "anchor": "shoulder_r"}, "rotate": -16},
        # legs (staggered stance for the iso turn) + boots
        # back leg sits higher & shorter (further from camera in the iso turn)
        {"name": "leg-back", "form": "capsule", "material": "pants", "size": [5, 6],
         "anchors": {"hip": [2.5, 0.5], "foot": [2.5, 5.5]}, "pivot": "hip",
         "attach": {"to": "torso", "anchor": "hip_r", "shift": [-1, -1]}, "rotate": -14},
        {"name": "boot-back", "form": "box", "material": "boot", "size": [6, 3], "round": 1,
         "anchors": {"top": [3, 0]}, "pivot": "top", "rotate": -16,
         "attach": {"to": "leg-back", "anchor": "foot"}},
        # front leg is longer & planted lower/forward (nearer the camera)
        {"name": "leg-front", "form": "capsule", "material": "pants", "size": [5, 8],
         "anchors": {"hip": [2.5, 0.5], "foot": [2.5, 7.5]}, "pivot": "hip",
         "attach": {"to": "torso", "anchor": "hip_l", "shift": [0, 1]}, "rotate": 8},
        {"name": "boot-front", "form": "box", "material": "boot", "size": [8, 4], "round": 1,
         "anchors": {"top": [3, 0]}, "pivot": "top", "rotate": 14,
         "attach": {"to": "leg-front", "anchor": "foot"}},
        # torso (root of the lower body; hangs off the head's neck)
        {"name": "torso", "form": "box", "material": "tunic", "size": [13, 10], "round": 3,
         "anchors": {"neck": [6.5, 0], "shoulder_l": [1, 2], "shoulder_r": [12, 2],
                     "chest_mid": [6.5, 4], "waist": [6.5, 8], "hip_l": [4, 9.5],
                     "hip_r": [9, 9.5]},
         "pivot": "neck", "attach": {"to": "head", "anchor": "neck", "shift": [0, -1]},
         "skew": [-0.16, 0]},
        # leather jerkin over the tunic front
        {"name": "jerkin", "form": "box", "material": "vest", "size": [9, 8], "round": 2,
         "anchors": {"top": [4.5, 0]}, "pivot": "top",
         "attach": {"to": "torso", "anchor": "chest_mid", "shift": [0, -1]}},
        # rope belt at the waist
        {"name": "belt", "form": "box", "material": "rope", "size": [11, 2],
         "anchors": {"c": [5.5, 1]}, "pivot": "c",
         "attach": {"to": "torso", "anchor": "waist"}},
        # near arm (in front of the torso)
        {"name": "arm-near", "form": "capsule", "material": "tunic", "size": [4, 8],
         "anchors": {"shoulder": [2, 1], "hand": [2, 7]}, "pivot": "shoulder",
         "attach": {"to": "torso", "anchor": "shoulder_l"}, "rotate": 18},
        # the big head — the root, drawn last so it sits on top
        {"name": "head", "form": "sphere", "material": "skin", "size": HEAD_SIZE,
         "anchors": {"neck": HEAD_NECK, "crown": [10, 1]}, "pivot": "neck",
         "at": HEAD_AT},
    ]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    overlay = build_overlay()
    assert all(len(r) == W for r in overlay), "ragged overlay row"
    assert len(overlay) == H, "overlay wrong height"
    sprite = {
        "name": "main",
        "extends": "../artbook.json",
        "_comment": ("Chibi peasant hero, hybrid build: a shaded form-skeleton for the "
                     "volumes (sphere head, capsule limbs, box torso/jerkin — auto-lit, "
                     "connected by construction, poseable) plus a hand-pixelled overlay "
                     "for the face/hair (big glossy eyes, fringe, cheeks) pinned over the "
                     "head. A three-quarter turn from the torso skew, a staggered stance "
                     "and eyes nudged to the near side. Regenerate with build_main.py."),
        "checks": [
            {"rule": "connected", "layer": ["head", "torso", "leg-front", "leg-back",
                                            "boot-front", "boot-back", "arm-near",
                                            "arm-far", "jerkin", "belt"]},
            {"rule": "on_canvas", "margin": 0},
        ],
        "skeleton": skeleton(),
        "layers": [
            {"name": "face", "pixels": overlay, "legend": LEGEND},
        ],
    }
    out = os.path.join(here, "sprites", "main.json")
    with open(out, "w") as f:
        json.dump(sprite, f, indent=2)
    print("wrote", out)


if __name__ == "__main__":
    main()
