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
    battle.events.append({"kind": "phase", "who": f.id, "by": f.id, "phase": "frenzy", "name": f.name, "line": line})


@phase("breaks_off")
def _breaks_off(battle, f, spec) -> None:
    """Met before its den, hurt, it breaks off and is gone into the dark at once, faster than anyone can follow (the
    tale goes on: it will be waiting at its den). Held fast, it can only run as anything runs."""
    if f.state != "fighting":
        return
    line = battle.rng.choice(spec["lines"])
    battle.say(line, "danger")
    battle.events.append({"kind": "phase", "who": f.id, "by": f.id, "phase": "breaks_off", "name": f.name, "line": line})
    if "grappled" in f.conditions or "restrained" in f.conditions or "paralyzed" in f.conditions:
        f.state = "fleeing"
        return
    f.state = "fled"
    battle._event("leave", who=f.id)
    battle._release(f)
    battle._check_end()


@phase("escape")
def _escape(battle, f, spec) -> None:
    """A story's lieutenant, hurt, tries to get away (game/story/lieutenants.py): with nobody beside it and nothing
    holding it, it is gone at once (a horse waiting, smoke, a ditch it knew); with a foe at its side or held, it must
    run for it like anything else, and can be cut down on the way (law: an escape can be prevented)."""
    if f.state != "fighting":
        return
    line = battle.rng.choice(spec["lines"])
    battle.say(line, "danger")
    battle.events.append({"kind": "phase", "who": f.id, "by": f.id, "phase": "escape", "name": f.name, "line": line})
    held = any(c in f.conditions for c in ("grappled", "restrained", "paralyzed"))
    if held or any(battle.gap(f, e) <= 1 for e in battle.enemies_of(f) if e.standing):
        f.state = "fleeing"
        return
    f.state = "fled"
    battle._event("leave", who=f.id)
    battle._release(f)
    battle._check_end()


@phase("raise")
def _raise(battle, f, spec) -> None:
    """Its second phase brings more of its own onto the field beside it (the barrow wakes and its sarcophagi open;
    the captain's men come running): `count` of the `creature`, fighting on its side from its next turn."""
    from realmwalker.rules.creatures import spawn

    cid = spec.get("creature", "skeleton")
    if cid not in battle.t.creatures or f.state != "fighting":
        f.phased = False  # (not now: it comes when the boss stands and fights again)
        return
    line = battle.rng.choice(spec["lines"])
    battle.say(line, "danger")
    battle.events.append({"kind": "phase", "who": f.id, "by": f.id, "phase": "raise", "name": f.name, "line": line})
    for i in range(int(spec.get("count", 2))):
        c = spawn(battle.t, cid, battle.rng.child(f"raise/{f.id}/{i}"), 9000 + i, now=int(battle.now or 0))
        battle.add_ally(c, f, "raised")
