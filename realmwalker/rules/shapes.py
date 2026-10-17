"""Shapes (Expansion 3 F.6): Polymorph and True Polymorph turn a creature into another for the fight.

The forms are the creatures the game has (a Beast for Polymorph, any creature for True Polymorph) whose Challenge
Rating is no more than the target's own (a character: its level). The game chooses (as Chromatic Orb picks its
damage): the strongest form a friend may take, the weakest for a foe. What a shape does to a fighter is
`Battle.shape` / `Battle.unshape` (rules/combat.py). Pure rules: no UI.

Expansion 3 F.8 adds the shapes that outlast a fight (Animal Shapes, Shapechange): limits on the forms (`cr`, `size`,
`not`: the effects op's), what a shape keeps of its wearer (the mind, the Spellcasting), and the record a lasting shape
leaves on a character (`char.spells["shape"]`: `record`, `on_road`), read by the battle at its start and by the road
(game/shapeshift.py)."""
from __future__ import annotations

from realmwalker.core import dice

# Never a form: what is called up by a spell (its numbers belong to the spell) or is one of a kind.
NOT_FORMS = ("otherworldly_steed", "animated_object")
SHAPECHANGERS = ("shapechanger",)  # (traits that a shape cannot take hold of)
SIZES = ("tiny", "small", "medium", "large", "huge", "gargantuan")
MIND = ("int", "wis", "cha")  # (what Animal Shapes and Shapechange leave of the wearer: F.8)


def avg(expr: str) -> float:
    n, s, flat = dice.parse(str(expr))
    return n * (s + 1) / 2 + flat


def challenge(f) -> float:
    """The Challenge Rating a form may not pass: a character's level, a creature's rating (of what it is underneath a
    shape it wears: a shift takes the wearer's own measure, Expansion 3 F.8)."""
    was = getattr(f, "shape", None)
    if was is not None:
        if was.get("char") is not None:
            return float(was["char"].level)
        return float((was.get("cdef") or {}).get("cr", 0))
    if f.char is not None:
        return float(f.char.level)
    return float((f.cdef or {}).get("cr", 0))


def shapeable(f) -> bool:
    """A creature a shape can take: on the field, above 0 hit points, not already shaped, not a shapechanger."""
    return f.active and f.hp > 0 and getattr(f, "shape", None) is None \
        and not any(f.has_trait(t) for t in SHAPECHANGERS) and f.bond is None


def forms(tables, kinds, cr_max: float, *, size: str | None = None, never=()) -> list[str]:
    """Every creature that may be the form: `kinds` a list of creature types, or "any"; `size` the largest it may be
    (Animal Shapes: "large"); `never` kinds it may not be (Shapechange: construct, undead)."""
    out = []
    top = SIZES.index(size) if size in SIZES else len(SIZES)
    for cid, d in tables.creatures.defs.items():
        if cid in NOT_FORMS or d.get("summon") or d.get("unique") or float(d.get("cr", 0)) > cr_max:
            continue
        if kinds != "any" and d.get("kind") not in kinds:
            continue
        if d.get("kind") in never or SIZES.index(d.get("size", "medium")) > top:
            continue
        if not d.get("attacks"):
            continue
        out.append(cid)
    return sorted(out)


def limits(o: dict) -> dict:
    """The keyword limits an effects op "shape" sets on its forms: {size, never} for `forms`."""
    return {"size": o.get("size"), "never": tuple(o.get("not", ()))}


def cap(f, o: dict) -> float:
    """The Challenge Rating a form may not pass: the op's own (Animal Shapes: 4) or the wearer's."""
    return float(o["cr"]) if o.get("cr") is not None else challenge(f)


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


def breathes_only_water(tables, cid: str) -> bool:
    """A form that would flounder on dry ground (an octopus, a reef shark): never a friend's (Expansion 3 F.7)."""
    return "water_breathing" in tables.creatures[cid].get("traits", ())


def best(tables, f, kinds, o: dict | None = None, *, other: str | None = None) -> str | None:
    """The strongest form a friend may take (None: none); never one that breathes only water, as fights are on dry
    ground until they go under the sea. `o`: the op's limits (F.8); `other`: a form not to take again (a shift)."""
    o = o or {}
    out = [c for c in forms(tables, kinds, cap(f, o), **limits(o)) if not breathes_only_water(tables, c) and c != other]
    return max(out, key=lambda c: (strength(tables, c), c)) if out else None


def worst(tables, f, kinds, o: dict | None = None) -> str | None:
    """The weakest form for a foe (None: none)."""
    o = o or {}
    out = forms(tables, kinds, cap(f, o), **limits(o))
    return min(out, key=lambda c: (strength(tables, c), c)) if out else None


def form_hp(tables, cid: str) -> int:
    """The form's own hit points (the stat block's average): its temporary hit points."""
    return max(1, int(avg(tables.creatures[cid]["hp"])))


def speed(tables, cid: str) -> int:
    """How fast a form goes over the land: its walking speed, or its flying speed when that is more."""
    sp = tables.creatures[cid].get("speeds") or {}
    return max(int(sp.get("walk", tables.creatures[cid].get("speed", 30)) or 0), int(sp.get("fly", 0) or 0))


def flies(tables, cid: str) -> bool:
    return int((tables.creatures[cid].get("speeds") or {}).get("fly", 0) or 0) > 0


def swims(tables, cid: str) -> bool:
    return int((tables.creatures[cid].get("speeds") or {}).get("swim", 0) or 0) > 0


def mind_kept(cdef: dict, char, tables, *, proficient: bool, block: dict | None = None) -> dict:
    """A form's stat block with its wearer's Intelligence, Wisdom and Charisma (Animal Shapes, Shapechange); with
    `proficient` (Shapechange keeps the proficiencies) their saves are the wearer's own where those are better. A
    creature wearing it (`char` None) gives its own stat block's (`block`: Expansion 3 G.1)."""
    from realmwalker.rules.character import Sheet

    out = dict(cdef)
    abilities = dict(cdef.get("abilities") or {})
    saves = dict(cdef.get("saves") or {})
    sheet = Sheet(char, tables) if proficient and char is not None else None
    mine = (block or {}).get("abilities") or {}
    for a in MIND:
        score = int(char.abilities.get(a, 10)) if char is not None else int(mine.get(a, 10))
        abilities[a] = score
        mod = (score - 10) // 2
        own = int(saves[a]) - ((int(cdef.get("abilities", {}).get(a, 10)) - 10) // 2) + mod if a in saves else mod
        if sheet is not None:
            own = max(own, int(sheet.save_bonus(a)))
        elif proficient and block is not None and a in (block.get("saves") or {}):
            own = max(own, int(block["saves"][a]))
        saves[a] = own
    out["abilities"], out["saves"] = abilities, saves
    return out


# ---------------------------------------------------------------------------- a shape that outlasts the fight (F.8)
def record(char) -> dict | None:
    """The lasting shape a character wears (Animal Shapes, Shapechange), or None: {form, spell, until (world minute),
    temp (its borrowed hit points left), caster (the name of who cast it), conc (held by the caster's
    concentration)}."""
    rec = (getattr(char, "spells", None) or {}).get("shape")
    return rec if isinstance(rec, dict) and rec.get("form") else None


def on_road(char, now: float) -> dict | None:
    """The lasting shape still working at world minute `now` (None when it has run out or there is none)."""
    rec = record(char)
    return rec if rec is not None and float(rec.get("until", 0)) > now else None


def keep(char, rec: dict) -> None:
    char.spells["shape"] = rec


def drop(char) -> dict | None:
    return (getattr(char, "spells", None) or {}).pop("shape", None)
