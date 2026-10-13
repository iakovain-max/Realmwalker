"""Traits and features as definitions (data/traits.json): what a creature's traits, a character's race and class
features (by their `rule` tag) and, later, feats and magic items do in the rules.

A definition has a name and a text (for its card), and any of:
    modifiers   timed-free numbers and flags, each with an optional `when` (named tests, WHEN below) and a `why`:
                {"attack": "advantage"}         its own attack rolls
                {"attacked": "disadvantage"}    attack rolls against it
                {"enemy_attacks": ...}           attack rolls of an enemy standing by it ("{name}" in `why`)
                {"save": "advantage", "abilities": ["con"]}, {"save": "advantage", "against": ["charmed"]}
                {"resist": ["poison"]}, {"vulnerable": ["poison"] or ["all"]}, {"crit_range": 19},
                {"passive": {"perception": 5}}, {"check": "disadvantage", "abilities": ["str"]} (ability checks)
    hooks       [{"event": ..., "as": "self"|"attacker"|"target"|"ally"|"any", "handler": id}] (rules/engine/events.py)
    resource    {"id", "max", "recover": "short"|"long"|"dawn"|"turn"} (rules/engine/resources.py)
    where       "sheet" when the character sheet or another system handles it and a fight has nothing to do
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from realmwalker.rules import grid


@dataclass
class Ctx:
    """What a modifier's `when` tests can look at."""
    b: Any  # the battle
    owner: Any  # the fighter whose trait it is
    att: Any = None
    target: Any = None
    opt: Any = None
    space: tuple | None = None
    ability: str | None = None
    against: tuple = ()  # the conditions a saving throw is made against (Brave, Fey Ancestry)


def table(tables) -> dict[str, dict]:
    return tables.traits["traits"]


def of(f) -> frozenset[str]:
    """Every trait a fighter has: a creature's listed traits; a character's race traits and class features by rule
    tag, and the features they have been given by id."""
    if f.char is None:
        key = ("c", id(f.cdef))
    else:
        c = f.char
        key = (c.race, c.cls, c.subclass, c.level, len(c.features), tuple(c.features[-3:]), len(c.feats),
               _magic_key(c))
    cached = f.__dict__.get("_traits")
    if cached is not None and cached[0] == key:
        return cached[1]
    found = frozenset(f.cdef.get("traits", [])) if f.char is None else of_char(f.char, f.t)
    f.__dict__["_traits"] = (key, found)
    return found


def of_char(char, tables) -> frozenset[str]:
    """A character's traits, in a fight or out of one: race traits and class features by rule tag, and the features
    they have been given by id."""
    from realmwalker.rules.character import Sheet

    s = Sheet(char, tables)
    names = {t["rule"] for t in s.race["traits"] if t.get("rule")}
    names |= {feat["rule"] for feat in s.features() if feat.get("rule")}
    names |= set(char.features)
    feat_defs = tables.feats["feats"] if hasattr(tables, "feats") else {}
    names |= {feat_defs[f["id"]]["trait"] for f in char.feats if feat_defs.get(f["id"], {}).get("trait")}
    if char.equipped or char.attuned:
        from realmwalker.rules import magic

        names |= magic.traits(char)  # an item's powers (artifacts, sentient things), while it works for them
    return frozenset(names)


def _magic_key(char) -> tuple:
    """Cheap: what is bound and what is worn (an item's magic changes only outside a fight)."""
    return tuple(char.attuned), tuple(sorted(char.equipped.values()))


def has(f, trait: str) -> bool:
    return trait in of(f)


def modifiers(f, kind: str, ctx: Ctx):
    """(mode, why) for each of a fighter's modifiers of this kind whose tests pass."""
    defs = table(f.t)
    for t in sorted(of(f)):
        d = defs.get(t)
        if not d:
            continue
        for m in d.get("modifiers", ()):
            if kind not in m:
                continue
            if "abilities" in m and ctx.ability not in m["abilities"]:
                continue
            if "against" in m and not set(m["against"]) & set(ctx.against):
                continue
            if all(WHEN[w](ctx) for w in m.get("when", ())):
                yield m[kind], m.get("why", d["name"].lower())


def values(f, key: str, *, flat: bool = False) -> list:
    """Every unconditional value a fighter's traits give for a key ({"resist": [...]}, {"crit_range": 19})."""
    defs = table(f.t)
    out: list = []
    for t in sorted(of(f)):
        for m in (defs.get(t) or {}).get("modifiers", ()):
            if key in m and not m.get("when"):
                if flat and isinstance(m[key], list):
                    out.extend(m[key])
                else:
                    out.append(m[key])
    return out


# ---------------------------------------------------------------------------- the tests a modifier can name
def _incap(f) -> bool:
    from realmwalker.rules.engine import query

    return query.incapacitated(f)


def _ally_beside_target(c: Ctx) -> bool:
    return any(x is not c.owner and x.standing and not _incap(x) and c.b.gap(x, c.target) <= 1
               for x in c.b.allies_of(c.owner))


def _in_sunlight(c: Ctx) -> bool:
    fld = c.b.field
    return not fld.underground and not fld.indoors and fld.base_light >= grid.BRIGHT


WHEN: dict[str, Callable[[Ctx], bool]] = {
    "ally_beside_target": _ally_beside_target,  # a friend of the owner stands beside its target
    "target_not_acted": lambda c: not c.target.acted,  # the target has not had a turn in this fight yet
    "in_sunlight": _in_sunlight,  # out under a bright sky
    "owner_able": lambda c: c.owner.standing and not _incap(c.owner),
    "owner_bloodied": lambda c: c.owner.hp <= c.owner.max_hp * c.owner.t.conditions["bloodied"]["at_most"],
    "attacker_beside_owner": lambda c: c.b.gap(c.owner, c.att) <= 1,
    "melee": lambda c: c.opt is not None and c.opt.is_melee,
    "ranged": lambda c: c.opt is not None and not c.opt.is_melee,
    "weapon": lambda c: c.opt is not None and c.opt.kind in ("melee", "ranged"),
}
