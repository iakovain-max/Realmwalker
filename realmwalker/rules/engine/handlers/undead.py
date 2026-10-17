"""The raised dead's own traits (Expansion 3 F.4, MM 2025): the ghast's Stench and the mummy's Rotting Fist curse.
The fist's dust (a creature it brings to 0 dies and turns to dust) is the attack's `dust` (Battle._turn_to_dust)."""

from __future__ import annotations

from realmwalker.rules.engine import durations
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.events import handler


@handler("stench")
def stench(b, f, ev, hook, buff) -> None:
    """Any creature that starts its turn within 5 feet of the ghast: a Constitution save or Poisoned until the start
    of its next turn; one that saves is spared this ghast's Stench for the fight (the book: 24 hours)."""
    x = ev.actor
    if x is None or x is f or not f.active or not x.active or b.gap(f, x) > 1 or x.kind == "undead":
        return
    spared = f.__dict__.setdefault("spared", set())
    if x.id in spared or "poisoned" in x.conditions:
        return
    dc = int((f.cdef.get("trait_numbers", {}).get("stench") or {}).get("dc", 10))
    if b._save(x, "con", dc):
        spared.add(x.id)
        return
    if durations.give(b, x, "poisoned", ends=durations.until(b, x, "turn_start"), source=f):
        b.say(f"The reek of {f.the_name} turns {x.the_name}'s stomach.", "info")


@special("mummy_rot")
def mummy_rot(c, o, victim) -> None:
    """A mummy's Rotting Fist curses a creature it hits: it cannot regain hit points while the fight lasts, and a
    party member carries the curse after it (`char.effects["kept:mummy_rot"]`: game/servants.rot_day lowers the maximum
    each day until Remove Curse lifts it)."""
    b = c.b
    if victim is None or victim.kind == "undead" and victim.char is None:
        return
    first = not any(bf.get("source") == "mummy_rot" for bf in victim.buffs)
    if first:
        durations.buff(victim, {"no_heal": True, "source": "mummy_rot"})
    from realmwalker.rules.servants import ROT

    if victim.char is not None and not victim.char.effects.get(ROT):
        victim.char.effects[ROT] = float(b.now or 0) or 1.0
        b.say(f"Where the mummy's fist struck {victim.the_name}, the skin greys and begins to rot.", "danger")
    elif first:
        b.say(f"Rot spreads from where the mummy's fist struck {victim.the_name}.", "info")
