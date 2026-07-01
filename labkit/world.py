"""The Root Spec — one world, many artifacts (VISION.md, the world layer).

Every Lab already proves coherence *within* one medium: a bible plus reusable
motifs keep a soundtrack or a sprite set from drifting. The **World Bible**
(``worlds/<name>/world.json``) is the coherence anchor one level up — the single
root spec from which every Lab's bible descends, declaring the things that are
true *across* modalities:

* **identity** — ``name`` / ``genre`` / ``tone`` / ``era``;
* a **palette of meaning** — a shape/colour/voice language (``round + warm +
  gentle = safe``) each Lab interprets in its own medium;
* **named entities** — places, factions, characters, referenced by *id* from any
  Lab;
* **cross-modal motifs** — the payoff: one root motif with a *face* in every
  medium (the keep's sun-crest as a sprite shape, its theme as a melody). Darken
  the root — the "fallen" transform — and every medium's face transforms in step.

A group's bible ``extends`` a world the same way a track extends its bible. This
module loads and validates a world and, crucially, checks **coherence across
Labs**: does every motif face point at a motif that actually exists in the named
Lab's bible? That check is what no prompt-per-asset workflow can offer — the
guarantee that music and art moved together because they share a root.

The world declares a *palette of meaning* and named *entities*; :func:`check_spec_refs`
pushes those one level down, letting the **leaf specs** the AI actually authors —
a track, a sprite — claim a meaning tag or reference an entity by id, validated
against the world with the same "cannot drift" guarantee the motif faces get.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .registry import BY_NAME
from .specbase import SpecError, load_json

WORLDS_DIR = "worlds"          # where world specs live: worlds/<name>/world.json
WORLD_FILE = "world.json"


@dataclass
class World:
    """The identity every Lab's bible descends from (the root spec)."""

    path: str
    name: str = "Untitled World"
    genre: str = ""
    tone: str = ""
    era: str = ""
    meaning: dict = field(default_factory=dict)    # tag -> {shape, color, voice}
    entities: dict = field(default_factory=dict)   # id -> {kind, name, ...}
    motifs: dict = field(default_factory=dict)     # id -> cross-modal motif (below)


def load_world(path: str) -> World:
    """Load and structurally validate a ``world.json``."""
    data = load_json(path)
    world = World(
        path=path,
        name=data.get("name", "Untitled World"),
        genre=data.get("genre", ""),
        tone=data.get("tone", ""),
        era=data.get("era", ""),
        meaning=data.get("meaning", {}),
        entities=data.get("entities", {}),
        motifs=data.get("motifs", {}),
    )
    _validate_world(world)
    return world


def _validate_world(w: World) -> None:
    if not isinstance(w.meaning, dict):
        raise SpecError(f"{w.path}: 'meaning' must be a map of tag -> descriptor")
    if not isinstance(w.entities, dict):
        raise SpecError(f"{w.path}: 'entities' must be a map of id -> descriptor")
    if not isinstance(w.motifs, dict):
        raise SpecError(f"{w.path}: 'motifs' must be a map of id -> cross-modal motif")
    for mid, motif in w.motifs.items():
        where = f"{w.path}: motif {mid!r}"
        if not isinstance(motif, dict):
            raise SpecError(f"{where}: must be an object")
        meaning = motif.get("meaning")
        if meaning is not None and meaning not in w.meaning:
            raise SpecError(f"{where}: meaning {meaning!r} is not declared in "
                            f"'meaning' (have: {sorted(w.meaning)})")
        faces = motif.get("faces", {})
        if not isinstance(faces, dict) or not faces:
            raise SpecError(f"{where}: needs a non-empty 'faces' map "
                            "(lab -> {group, motif})")
        for lab, face in faces.items():
            _validate_face(lab, face, where=f"{where} face {lab!r}")
        transforms = motif.get("transforms", {})
        if not isinstance(transforms, dict):
            raise SpecError(f"{where}: 'transforms' must be a map of name -> per-lab spec")
    # Entity references from a motif must resolve to a declared entity.
    for mid, motif in w.motifs.items():
        for eid in motif.get("entities", []):
            if eid not in w.entities:
                raise SpecError(f"{w.path}: motif {mid!r} references unknown "
                                f"entity {eid!r} (have: {sorted(w.entities)})")


def _validate_face(lab: str, face, where: str) -> None:
    if lab not in BY_NAME:
        raise SpecError(f"{where}: unknown lab {lab!r} (labs: {sorted(BY_NAME)})")
    if not isinstance(face, dict) or "group" not in face or "motif" not in face:
        raise SpecError(f"{where}: must be {{'group': <name>, 'motif': <name>}}")


# --- Leaf-spec references into the world (VISION.md, the world layer) --------- #
#
# Until now only a world's OWN motifs could name its meaning tags and entities.
# These two helpers push that binding down to the leaf specs the AI edits day to
# day — a track, a sprite — so a spec can declare what it *means* and *who it is
# about*, checked against the world exactly as a wrong note is checked against the
# key. Both Labs call the same function, so it is one mechanism, not a per-Lab copy.

def check_spec_refs(data: dict, world: "World | None", where: str) -> tuple:
    """Validate a leaf spec's optional references into its world.

    Recognised fields on ``data``:

    * ``meaning`` — a tag that must be one of the world's ``meaning`` keys (the
      *palette of meaning* each Lab reads in its own medium);
    * ``entity`` / ``entities`` — an id, or list of ids, into the world's
      ``entities`` (``entities`` wins if both are present).

    Returns ``(meaning, entities)`` — the tag or ``None``, and a list of ids — so
    the caller can stash them on the resolved spec for tooling to surface. A spec
    that references nothing is unaffected; a *standalone* spec (no world) that
    names a meaning/entity is a clear error, not a silent no-op — you cannot point
    at a world you do not descend from.
    """
    meaning = data.get("meaning")
    entities = data.get("entities")
    if entities is None:
        entities = [data["entity"]] if "entity" in data else []
    elif not isinstance(entities, list):
        raise SpecError(f"{where}: 'entities' must be a list of entity ids, got {entities!r}")

    if meaning is None and not entities:
        return None, []
    if world is None:
        raise SpecError(f"{where}: references the world ('meaning'/'entity') but this "
                        f"spec extends no world")
    # `_`-prefixed keys are documentation (a world's `_comment`), not selectable tags.
    valid_meanings = {k for k in world.meaning if not k.startswith("_")}
    valid_entities = {k for k in world.entities if not k.startswith("_")}
    if meaning is not None and meaning not in valid_meanings:
        raise SpecError(f"{where}: meaning {meaning!r} is not in the world's palette of "
                        f"meaning (have: {sorted(valid_meanings)})")
    for eid in entities:
        if eid not in valid_entities:
            raise SpecError(f"{where}: unknown entity {eid!r} "
                            f"(world declares: {sorted(valid_entities)})")
    return meaning, entities


def fmt_refs(meaning, entities) -> str:
    """A short ``  [means X; about a, b]`` suffix for CLI listings (empty if none)."""
    bits = []
    if meaning:
        bits.append(f"means {meaning}")
    if entities:
        bits.append("about " + ", ".join(entities))
    return f"  [{'; '.join(bits)}]" if bits else ""


def discover_worlds(root: str = ".") -> list:
    """Return ``(name, path)`` for each ``worlds/<name>/world.json``, sorted."""
    base = os.path.join(root, WORLDS_DIR)
    out = []
    if os.path.isdir(base):
        for name in sorted(os.listdir(base)):
            p = os.path.join(base, name, WORLD_FILE)
            if os.path.isfile(p):
                out.append((name, p))
    return out


def _bible_data(lab, group: str, root: str) -> dict:
    """Load a Lab group's bible JSON (motif *names* only — no per-Lab model)."""
    path = os.path.join(root, lab.assets_dir, group, lab.bible_file)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return load_json(path)


def _spec_exists(lab, group: str, name: str, root: str) -> bool:
    path = os.path.join(root, lab.assets_dir, group, lab.specs_subdir, f"{name}.json")
    return os.path.isfile(path)


def check_world(world: World, root: str = ".") -> list:
    """Cross-Lab coherence: every motif face (and transform target) must resolve.

    Returns a list of human-readable error strings — empty when the world is
    coherent. This is the check that binds the Labs: a cross-modal motif is only
    real if the melody it names in the music bible and the shape it names in the
    art bible both exist. Deliberately generic — it reads bible/​spec JSON by the
    registry's layout, so it never needs a Lab's Python model.
    """
    errs = []
    for mid, motif in world.motifs.items():
        faces = motif.get("faces", {})
        for lab_name, face in faces.items():
            lab = BY_NAME.get(lab_name)
            if lab is None:
                errs.append(f"motif {mid!r}: unknown lab {lab_name!r}")
                continue
            group, motif_name = face.get("group"), face.get("motif")
            try:
                data = _bible_data(lab, group, root)
            except FileNotFoundError:
                errs.append(f"motif {mid!r} face {lab_name}: no group {group!r} "
                            f"under {lab.assets_dir}/")
                continue
            except SpecError as e:
                errs.append(f"motif {mid!r} face {lab_name}: {e}")
                continue
            if motif_name not in data.get("motifs", {}):
                errs.append(f"motif {mid!r} face {lab_name}: {group}/{lab.bible_file} "
                            f"has no motif {motif_name!r}")
        # Transform targets (a fallen sprite / a minor-key track) must exist too.
        for tname, tspec in motif.get("transforms", {}).items():
            if not isinstance(tspec, dict):
                continue
            for lab_name, per in tspec.items():
                lab = BY_NAME.get(lab_name)
                if lab is None or not isinstance(per, dict):
                    continue
                group = faces.get(lab_name, {}).get("group") or per.get("group")
                if group is None:
                    continue
                kinds = {lab.specs_subdir.rstrip("s"), "sprite", "track", "spec"}
                for kind in kinds:
                    if kind in per and not _spec_exists(lab, group, per[kind], root):
                        errs.append(f"motif {mid!r} transform {tname!r} ({lab_name}): "
                                    f"no {kind} {per[kind]!r} in {group}/")
    return errs
