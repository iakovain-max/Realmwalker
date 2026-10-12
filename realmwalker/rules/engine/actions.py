"""What a fighter can do with a feature (docs/EXPANSIONS.md §4.3.7, begun): the abilities that traits and features
give (data/traits.json "activate"), whether each can be used now and why not, and using one.

An activation is {"id", "name", "cost": "action" | "bonus" | "free", "uses": pool id (rules/engine/resources.py),
"requires": [tests from REQUIRES], "via": a battle action done with the bonus action instead (Cunning Action's
"dash", "disengage", "hide"), "effects": [ops] (rules/engine/effects.py)}. A trait may give several.
Part C turns this into the one list of everything a fighter can do (moves, attacks, spells, abilities).
"""

from __future__ import annotations

from typing import Callable

from realmwalker.rules.engine import effects, events
from realmwalker.rules.engine import resources as res
from realmwalker.rules.engine import traits as tr


def activations(f) -> list[dict]:
    """Every ability a fighter's traits give, in a fixed order."""
    defs = tr.table(f.t)
    out = []
    for t in sorted(tr.of(f), key=lambda t: _ORDER.get(t, 50)):
        a = (defs.get(t) or {}).get("activate")
        if a:
            out.extend(a if isinstance(a, list) else [a])
    return out


# The order abilities are listed in (the order the battle menu always had).
_ORDER = {"second_wind": 0, "action_surge": 1, "cunning_action": 2, "channel_divinity": 3, "preserve_life": 4,
          "divine_intervention": 5, "war_priest": 6}


def find(f, aid: str) -> dict | None:
    return next((a for a in activations(f) if a["id"] == aid), None)


def problem(b, f, a: dict) -> str | None:
    """Why this ability cannot be used now (None when it can)."""
    if f.char is None:
        return "not yours"
    if a.get("uses") and res.left(f.char, a["uses"]) <= 0:
        return "used; rest to recover"
    for r in a.get("requires", ()):
        why = REQUIRES[r](b, f)
        if why:
            return why
    if a["cost"] == "action" and f.action <= 0:
        return "no action left"
    if a["cost"] == "bonus" and f.bonus <= 0:
        return "no bonus action left"
    return None


def label(a: dict) -> str:
    return a["name"]


def use(b, f, aid: str, target=None) -> bool:
    """Use an ability: pay for it, spend its use, do what it does. False if it could not be used."""
    a = find(f, aid)
    if a is None or problem(b, f, a):
        return False
    if a.get("via"):
        getattr(b, f"do_{a['via']}")(f, bonus=True)  # the battle action pays for itself, with the bonus action
        return True
    if a["cost"] != "free" and not b._spend(f, bonus=a["cost"] == "bonus"):
        return False
    if a.get("uses"):
        res.spend(f.char, a["uses"])
    c = effects.Cast(b, f, aid, {"target": a.get("target", "self"), "name": a["name"], "ability": True}, target, None)
    effects.run(c, a.get("effects", ()))
    events.emit(b, "ability_used", actor=f, ability=aid)
    if a["cost"] != "free":
        b._after_action(f)
    return True


# ---------------------------------------------------------------------------- what an ability can require
def _undead_near(b, f) -> str | None:
    if any(x.kind == "undead" and b.feet(f, x) <= 30 for x in b.enemies_of(f)):
        return None
    return "no undead within 30 feet"


def _god_ready(b, f) -> str | None:
    if b.now - f.char.uses.get("divine_answered", -10**9) >= 7 * 1440:
        return None
    return "your god has answered this week"


REQUIRES: dict[str, Callable] = {
    "undead_within_30": _undead_near,
    "god_ready": _god_ready,
}
