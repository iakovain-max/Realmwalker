"""A story's boss in a fight (Expansion 6, docs/ADVENTURES.md §5.8): its second phase, once, when it falls to the
share of its hit points its template names (`cdef["boss_phase"]` {at, kind, lines}, set by game/story/finale.py).

PHASES are the kinds of second phase (villains.json bosses' `phase.kind`); game/story/check.py reports any other.
`Battle._hit` calls `after_damage`; after the phase's own kind, `battle.phase_hooks` run (the arena changing with it:
game/story/arenas.py).

The great attack (E.5, law 5: it telegraphs): `cdef["boss_great"]` {name, area {size, range} in feet, save, dc,
damage, type, every, first, warn, go}. On one of its turns (`turn_start`, from Battle's turn engine) it marks where
it will fall - an "omen" zone on the field, harmless in itself, and a line ("draws in a breath") - and at the start
of its next turn the blow falls there on every foe still inside (a save for half), taking its action. Anyone can
step out in between; the Auto does (tactics._out_of_harm). Held, stunned or down when the turn comes, it fizzles.

The legendary action "command" (`{"command": true}` among `legendary.actions`): one of its own side close to a foe
strikes at once, out of turn (`command`, from Battle._legendary_window when the boss has no blow of its own to make).
"""

from __future__ import annotations

PHASES: dict[str, object] = {}
OMEN = "omen"  # the zone kind that shows where a great attack will fall


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
    if f.__dict__.get("phased"):  # (a phase put off - "raise" with nobody to raise yet - changes nothing yet)
        for hook in list(battle.__dict__.get("phase_hooks", ())):
            hook(battle, f, spec)


# ---------------------------------------------------------------------------- the great attack
def turn_start(battle, f) -> None:
    """A boss's turn begins: a great attack marked last turn falls now; or, its time come, it marks the next."""
    spec = f.cdef.get("boss_great") if f.creature is not None else None
    if not spec:
        return
    st = f.__dict__.setdefault("great", {"cells": None, "zone": None, "last": None})
    if st["cells"] is not None:
        _fall(battle, f, spec, st)
        return
    first = int(spec.get("first", 2))
    every = int(spec.get("every", 3))
    if battle.round < first or (st["last"] is not None and battle.round - st["last"] < every) or not f.can_act():
        return
    cells = _aim(battle, f, spec)
    if cells is None:
        return
    from realmwalker.rules.combat import Zone

    z = Zone(battle._zone_id(), OMEN, set(cells), owner=f.id, rounds=-1)
    battle._add_zone(z)
    st["cells"], st["zone"] = sorted(cells), z.id
    from realmwalker.core.textgen import escape_markup as esc

    line = battle.rng.choice(spec["warn"]).replace("{name}", esc(f.the_name))
    battle.say(line[:1].upper() + line[1:], "danger")
    battle._event("telegraph", by=f.id, name=spec.get("name", ""), cells=sorted(cells), line=line)


def _area(battle, centre, size_ft: int) -> set:
    r = max(1, int(size_ft) // 5)
    fld = battle.field
    out = set()
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            c = (centre[0] + dx, centre[1] + dy)
            if dx * dx + dy * dy <= r * r + r and fld.in_bounds(*c) and fld.walk[c]:
                out.add(c)
    return out


def _aim(battle, f, spec) -> set | None:
    """Where it falls: centred on itself (range 0) or on a foe in range, to catch the most of them."""
    area = spec.get("area") or {}
    size, rng_ft = int(area.get("size", 10)), int(area.get("range", 0))
    foes = [e for e in battle.enemies_of(f) if e.standing and e.state != "away"]
    if not foes:
        return None
    if rng_ft <= 0:
        centres = [(f.x, f.y)]
    else:
        centres = [(e.x, e.y) for e in foes if battle.gap(f, e) * 5 <= rng_ft]
    best, score = None, 0
    for c in centres:
        cells = _area(battle, c, size)
        if rng_ft <= 0:
            cells -= set(f.cells)
        n = sum(1 for e in foes if any(x in cells for x in e.cells))
        if n > score:
            best, score = cells, n
    return best


def _fall(battle, f, spec, st) -> None:
    cells = {tuple(c) for c in st["cells"]}
    z = next((z for z in battle.zones if z.id == st["zone"]), None)
    st["cells"], st["zone"], st["last"] = None, None, battle.round
    if z is None:
        return  # (its omen is gone from the field: nothing falls where nothing was shown)
    battle._remove_zone(z)
    if not f.can_act():
        battle.say(_words(battle, "fizzle", f), "good")
        return
    from realmwalker.core.textgen import escape_markup as esc

    line = battle.rng.choice(spec["go"]).replace("{name}", esc(f.the_name))
    battle.say(line[:1].upper() + line[1:], "danger")
    caught = [e for e in battle.enemies_of(f) if any(c in cells for c in e.cells)]
    battle._event("great", by=f.id, name=spec.get("name", ""), cells=sorted(cells), hit=[e.id for e in caught])
    f.action = 0  # (the great attack is its action this turn)
    for e in caught:
        battle._save_damage(f, e, spec.get("save", "dex"), int(spec["dc"]), str(spec["damage"]),
                            spec.get("type", "force"), "half")
    battle._check_end()


def _omens_against(battle, f) -> list:
    """The omens of `f`'s foes still standing (one whose boss fell or fled is gone from the field)."""
    out = []
    for z in [z for z in battle.zones if z.kind == OMEN]:
        owner = next((x for x in battle.fighters if x.id == z.owner), None)
        if owner is None or not owner.active:
            battle._remove_zone(z)
            if owner is not None and owner.__dict__.get("great"):
                owner.great["cells"], owner.great["zone"] = None, None  # (what it gathered is lost with it)
        elif owner.team != f.team:
            out.append(z)
    return out


WORDS = {"fizzle": ["What {name} was gathering breaks apart and is gone."],
         "command": ["{name} snaps an order, and {man} strikes."]}  # (if villains.json "boss_words" has none)


def _words(battle, key: str, f, m=None) -> str:
    """A line of villains.json "boss_words" (the fizzle of a great attack, an order to its men), names escaped."""
    from realmwalker.core.textgen import escape_markup as esc

    lines = (getattr(battle.t, "villains", None) or {}).get("boss_words", {}).get(key) or WORDS[key]
    text = battle.rng.choice(lines).replace("{name}", esc(f.the_name)).replace("{man}", esc(m.the_name if m else ""))
    return text[:1].upper() + text[1:]


def in_omen(battle, f) -> bool:
    """`f` stands where a foe's great attack is about to fall."""
    return any(any(c in z.cells for c in f.cells) for z in _omens_against(battle, f))


def omen_cells(battle, f) -> set:
    return {c for z in _omens_against(battle, f) for c in z.cells}


# ---------------------------------------------------------------------------- command its minions
def command(battle, f, left: int) -> bool:
    """A legendary action: one of its own side beside a foe strikes at once (its best blow at the weakest foe in
    reach). True if one did."""
    best = None
    for m in battle.allies_of(f):
        if m is f or m.creature is None or not m.can_act() or m.state != "fighting" or not getattr(m, "blows", True):
            continue
        for opt in battle.attack_options(m):
            if not opt.available or opt.kind not in ("melee", "ranged"):
                continue
            targets = [t for t in battle.targets_for(m, opt) if t.active and t.team != m.team]
            if targets:
                t = min(targets, key=lambda t: t.hp)
                if best is None or t.hp < best[2].hp:
                    best = (m, opt, t)
                break
    if best is None:
        return False
    m, opt, t = best
    f.creature.uses["legendary_actions"] = left - 1
    battle.say(_words(battle, "command", f, m) + " <dim>(Legendary Action)</>", "danger")
    battle._event("legendary", by=f.id, what="command", who=m.id)
    battle._attack(m, opt, t)
    battle._check_end()
    return True


@phase("frenzy")
def _frenzy(battle, f, spec) -> None:
    """Cornered, it goes mad: no more flight, and it strikes harder (a beast's second phase; the phase's `damage`, a
    die more on each blow, and `attacks`, more blows: E.6)."""
    line = battle.rng.choice(spec["lines"])
    battle.say(line, "danger")
    d = dict(f.cdef)
    d["morale"] = "fanatic"
    if spec.get("attacks"):
        d["multiattack"] = max(1, int(d.get("multiattack", 1) or 1)) + int(spec["attacks"])
    f.cdef = d
    f.buffs.append({"id": "frenzy", "name": "frenzy", "attack_die": "1d4", "damage_die": spec.get("damage") or "1d6",
                    "rounds": -1})
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
