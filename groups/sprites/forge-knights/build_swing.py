"""Build the form-rig sword-swing animation for forge-knights.

The base knight is one skeleton of form bones; only the sword arm + blade (and a
little torso/leg counter-motion) change per frame, so we define the rig once and
sweep the swing angles. Emits sprites/knight-forms-swing.json (the committed
artifact) with one full skeleton per frame — the pattern the grid attack sprites
use. Corrects the earlier "pipe" read: the sword is GOLD (contrasts the steel
helm) and the arm is genuinely raised so the blade rises into empty space.
"""
import json, sys

CANVAS = [48, 60]
HIP = [18, 45]   # where the chest's hip pivot lands


def rig(arm_deg, sword_deg, lean, step):
    return [
        # back leg (viewer-left), plants; front leg (viewer-right) steps with `step`
        {"name": "leg-back", "form": "capsule", "material": "iron", "size": [5, 11],
         "anchors": {"hip": [2.5, 0.5], "foot": [2.5, 10.5]},
         "pivot": "hip", "attach": {"to": "chest", "anchor": "hip_l"}, "rotate": 10},
        {"name": "leg-front", "form": "capsule", "material": "iron", "size": [5, 11],
         "anchors": {"hip": [2.5, 0.5], "foot": [2.5, 10.5]},
         "pivot": "hip", "attach": {"to": "chest", "anchor": "hip_r"}, "rotate": -12 - step},
        # off arm across the body (static guard)
        {"name": "arm-off", "form": "capsule", "material": "iron", "size": [5, 11],
         "anchors": {"shoulder": [2.5, 1], "hand": [2.5, 10]},
         "pivot": "shoulder", "attach": {"to": "chest", "anchor": "shoulder_l"}, "rotate": 36},
        {"name": "chest", "form": "box", "material": "steel", "size": [15, 15], "round": 4,
         "anchors": {"neck": [7.5, 1.5], "chest_mid": [7.5, 5],
                     "shoulder_l": [2, 4], "shoulder_r": [13, 4],
                     "hip_l": [4, 14.5], "hip_r": [11, 14.5]},
         "pivot": "hip_l", "at": HIP, "skew": [lean, 0]},
        {"name": "surcoat", "form": "box", "material": "cloak", "size": [5, 13], "round": 1,
         "anchors": {"top": [2.5, 0]}, "pivot": "top",
         "attach": {"to": "chest", "anchor": "chest_mid"}},
        {"name": "pauldron-off", "form": "sphere", "material": "gold", "size": [7, 7],
         "anchors": {"c": [3.5, 3.5]}, "pivot": "c",
         "attach": {"to": "chest", "anchor": "shoulder_l"}},
        {"name": "pauldron-sword", "form": "sphere", "material": "gold", "size": [7, 7],
         "anchors": {"c": [3.5, 3.5]}, "pivot": "c",
         "attach": {"to": "chest", "anchor": "shoulder_r"}},
        {"name": "head", "form": "sphere", "material": "skin", "size": [8, 8],
         "anchors": {"neck": [4, 7], "crown": [4, 1]},
         "pivot": "neck", "attach": {"to": "chest", "anchor": "neck", "shift": [0, -1]}},
        {"name": "helm", "form": "sphere", "material": "steel", "size": [10, 7],
         "anchors": {"base": [5, 6], "top": [5, 1]},
         "pivot": "base", "attach": {"to": "head", "anchor": "crown"}},
        {"name": "plume", "form": "cone", "material": "gold", "size": [4, 6],
         "anchors": {"base": [2, 5.5]}, "pivot": "base",
         "attach": {"to": "helm", "anchor": "top"}},
        # sword ARM (raised) — the animated bone
        {"name": "arm-sword", "form": "capsule", "material": "iron", "size": [5, 12],
         "anchors": {"shoulder": [2.5, 1], "hand": [2.5, 11]},
         "pivot": "shoulder", "attach": {"to": "chest", "anchor": "shoulder_r"},
         "rotate": arm_deg},
        # the blade — GOLD so it never blends into the steel helm
        {"name": "sword", "form": "capsule", "material": "gold", "size": [3, 18],
         "anchors": {"grip": [1.5, 16]}, "pivot": "grip",
         "attach": {"to": "arm-sword", "anchor": "hand"}, "rotate": sword_deg},
    ]


def frame(name, hold, arm, sword, lean, step):
    return {"name": name, "hold": hold, "skeleton": rig(arm, sword, lean, step)}


# Swing arc. Both the arm and the blade must rotate the SAME way (clockwise here)
# and the hand must actually travel DOWN — the earlier version kept the hand up and
# turned the arm and blade in opposite directions, which read as "rotating the wrong
# way". Arm hand offset from the shoulder is (-10 sin a, 10 cos a); the blade tip
# offset from the grip is (16 sin s, -16 cos s), so:
#   a=190 -> hand up (cocked);  a=310/340 -> hand down-right/down (the chop).
#   s=0   -> blade straight up; s=150/170 -> blade leading down.
FRAMES = [
    frame("ready",   2, 210,  20, -0.08, 0),
    frame("windup",  2, 190,   0, -0.13, 0),
    frame("strike",  3, 310, 150,  0.06, 2),
    frame("follow",  1, 340, 170,  0.10, 2),
    frame("recover", 2, 210,  20, -0.08, 0),
]

sprite = {
    "name": "knight-forms-swing",
    "extends": "../artbook.json",
    "_comment": "Form-rig sword-swing animation (regenerate with build_swing.py in this dir). "
                "One skeleton of form bones per frame; only the sword arm + gold blade "
                "and a little counter-motion change. Anticipation (windup) -> strike (held) "
                "-> follow-through -> recover. Every frame stays connected by construction "
                "and is gated by the checks below via `inspect --all-frames`.",
    "size": CANVAS,
    "fps": 8,
    "checks": [{"rule": "connected"}, {"rule": "on_canvas", "margin": 0}],
    "frames": FRAMES,
}

if len(sys.argv) > 1 and sys.argv[1] == "--one":
    # emit a single still for angle testing: args --one ARM SWORD
    arm, sword = float(sys.argv[2]), float(sys.argv[3])
    sprite["frames"] = [frame("test", 1, arm, sword, -0.10, 0)]

out = "groups/sprites/forge-knights/sprites/knight-forms-swing.json"
json.dump(sprite, open(out, "w"), indent=2)
print("wrote", out, "frames:", len(sprite["frames"]))
