"""Shapes (Expansion 3 F.6): Polymorph and True Polymorph turn a creature into another for the fight.

The forms are the creatures the game has (a Beast for Polymorph, any creature for True Polymorph) whose Challenge
Rating is no more than the target's own (a character: its level). The game chooses (as Chromatic Orb picks its
damage): the strongest form a friend may take, the weakest for a foe. What a shape does to a fighter is
`Battle.shape` / `Battle.unshape` (rules/combat.py). Pure rules: no UI."""
from __future__ import annotations

from realmwalker.core import dice

# Never a form: what is called up by a spell (its numbers belong to the spell) or is one of a kind.
NOT_FORMS = ("otherworldly_steed", "animated_object")
SHAPECHANGERS = ("shapechanger",)  # (traits that a shape cannot take hold of)


def avg(expr: str) -> float:
    n, s, flat = dice.parse(str(expr))
    return n * (s + 1) / 2 + flat


def challenge(f) -> float:
    """The Challenge Rating a form may not pass: a character's level, a creature's rating."""
    if f.char is not None:
        return float(f.char.level)
    return float((f.cdef or {}).get("cr", 0))


def shapeable(f) -> bool:
    """A creature a shape can take: on the field, above 0 hit points, not already shaped, not a shapechanger."""
    return f.active and f.hp > 0 and getattr(f, "shape", None) is None \
        and not any(f.has_trait(t) for t in SHAPECHANGERS) and f.bond is None


def forms(tables, kinds, cr_max: float) -> list[str]:
    """Every creature that may be the form: `kinds` a list of creature types, or "any"."""
    out = []
    for cid, d in tables.creatures.defs.items():
        if cid in NOT_FORMS or d.get("summon") or d.get("unique") or float(d.get("cr", 0)) > cr_max:
            continue
        if kinds != "any" and d.get("kind") not in kinds:
            continue
        if not d.get("attacks"):
            continue
        out.append(cid)
    return sorted(out)


def strength(tables, cid: str) -> float:
    """How much a form is worth in a fight: its hit points and its blows (three rounds of them)."""
    d = tables.creatures[cid]
    blows = 0.0
    for a in d.get("attacks", ()):
        if a.get("damage"):
            blows = max(blows, avg(a["damage"]))
    many = d.get("multiattack", 1)
    blows *= max(1, many if isinstance(many, int) else len(many))
    return avg(d["hp"]) + 3 * blows + 2 * int(d.get("ac", 10))


def best(tables, f, kinds) -> str | None:
    """The strongest form a friend may take (None: none)."""
    out = forms(tables, kinds, challenge(f))
    return max(out, key=lambda c: (strength(tables, c), c)) if out else None


def worst(tables, f, kinds) -> str | None:
    """The weakest form for a foe (None: none)."""
    out = forms(tables, kinds, challenge(f))
    return min(out, key=lambda c: (strength(tables, c), c)) if out else None


def form_hp(tables, cid: str) -> int:
    """The form's own hit points (the stat block's average): its temporary hit points."""
    return max(1, int(avg(tables.creatures[cid]["hp"])))
