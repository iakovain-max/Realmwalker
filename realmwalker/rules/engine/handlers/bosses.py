"""A story's boss in a fight (Expansion 6, docs/ADVENTURES.md §5.8): its second phase, once, when it falls to the
share of its hit points its template names (`cdef["boss_phase"]` {at, kind, lines}, set by game/story/finale.py).

PHASES are the kinds of second phase (villains.json bosses' `phase.kind`); game/story/check.py reports any other.
`Battle._hit` calls `after_damage`.
"""

from __future__ import annotations

PHASES: dict[str, object] = {}


def phase(name: str):
    """fn(battle, fighter, spec)"""
    def wrap(fn):
        PHASES[name] = fn
        return fn
    return wrap


def after_damage(battle, f) -> None:
    spec = f.cdef.get("boss_phase") if f.creature is not None else None
    if not spec or f.__dict__.get("phased") or f.hp <= 0 or f.hp > f.max_hp * float(spec["at"]):
        return
    f.phased = True
    PHASES[spec["kind"]](battle, f, spec)


@phase("frenzy")
def _frenzy(battle, f, spec) -> None:
    """Cornered, it goes mad: no more flight, and it strikes harder (a beast's second phase)."""
    line = battle.rng.choice(spec["lines"])
    battle.say(line, "danger")
    d = dict(f.cdef)
    d["morale"] = "fanatic"
    f.cdef = d
    f.buffs.append({"id": "frenzy", "name": "frenzy", "attack_die": "1d4", "damage_die": "1d6", "rounds": -1})
    battle.events.append({"kind": "phase", "who": f.id, "phase": "frenzy"})
