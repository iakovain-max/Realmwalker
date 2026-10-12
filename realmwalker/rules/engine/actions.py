"""What a fighter can do with a feature (docs/EXPANSIONS.md §4.3.7, begun): the abilities that traits and features
give (data/traits.json "activate"), whether each can be used now and why not, and using one.

An activation is {"id", "name", "cost": "action" | "bonus" | "free", "uses": pool id (rules/engine/resources.py),
"requires": [tests from REQUIRES], "via": a battle action done with the bonus action instead (Cunning Action's
"dash", "disengage", "hide"), "effects": [ops] (rules/engine/effects.py)}. A trait may give several.

`options(b, f)` is the one list of everything a fighter can do now - every attack with each weapon, every spell, every
ability, the other actions (Dash, Disengage, Dodge, Hide, Help, Study, Search, Ready, Shove, Grapple, Influence...),
items - each with its cost, whether it can be done and why not, and what it can be aimed at. The battle screen's
menus, the companions' Auto and the enemy all read it (rules/engine/estimates.py says what each is worth).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

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


# ---------------------------------------------------------------------------- everything a fighter can do now
@dataclass
class Option:
    """One thing a fighter could do now: how it is paid for, whether it can be done and why not, what it is aimed at."""
    id: str  # "attack:main", "cast:fire_bolt", "ability:second_wind", "action:dash"...
    kind: str  # attack, cast, ability, action, item
    name: str
    cost: str  # action, bonus, attack (one attack of the Attack action), free, reaction
    available: bool = True
    why: str = ""
    value: Any = None  # what the battle's do_ method takes (an AttackOption, a spell value, an ability id, an item uid)
    aim: str = "none"  # creature, point, none
    targets: list = field(default_factory=list)  # creatures it can be aimed at from here
    points: set | None = None  # squares it can be aimed at


def options(b, f) -> list[Option]:
    """Everything `f` can do now, in a fixed order: attacks, spells, abilities, the other actions, items."""
    out: list[Option] = []
    acting = b.has_action(f)
    for o in b.attack_options(f):
        ok = o.available and acting
        why = o.reason if not o.available else ("" if acting else "no action left this turn")
        out.append(Option(f"attack:{o.key}", "attack", o.name, "attack", ok, why, o, "creature",
                          b.targets_for(f, o) if ok else []))
    if f.char is not None:
        for sid, ok, why in b.spell_options(f):
            out.append(_spell_option(b, f, sid, ok, why))
    else:
        for sid in b.creature_spells(f):
            out.append(_spell_option(b, f, sid, True, ""))
    for aid, name, ok, why in b.class_abilities(f):
        a = find(f, aid)
        cost = a["cost"] if a else ("bonus" if aid in ("offhand", "spirit_strike") else "action")
        targets = []
        if aid == "offhand" and ok:
            opt = b.offhand_option(f)
            targets = [t for t in b.enemies_of(f) if opt is not None and b.in_reach(f, opt, t)[0]]
        elif aid == "spirit_strike" and ok:
            targets = b.spirit_targets(f)
        out.append(Option(f"ability:{aid}", "ability", name, cost, ok, why, aid, "creature" if targets else "none",
                          targets))
    free = f.action > 0
    no = "" if free else "no action left this turn"
    for key, name in (("dash", "Dash"), ("disengage", "Disengage"), ("dodge", "Dodge")):
        out.append(Option(f"action:{key}", "action", name, "action", free, no, key))
    hide = b.hide_problem(f)
    out.append(Option("action:hide", "action", "Hide", "action", free and hide is None, no or hide or "", "hide"))
    helped = b.help_targets(f)
    out.append(Option("action:help", "action", "Help", "action", free and bool(helped),
                      no or ("" if helped else "nobody to help"), "help", "creature", helped))
    unknown = [e for e in b.enemies_of(f) if e.creature is not None and e.creature.def_id not in b.known]
    out.append(Option("action:study", "action", "Study", "action", free and bool(unknown),
                      no or ("" if unknown else "you know all of them"), "study", "creature", unknown))
    out.append(Option("action:search", "action", "Search", "action", free, no, "search"))
    for trig, name in (("reach", "Ready a blow"), ("sight", "Ready a shot")):
        out.append(Option(f"action:ready:{trig}", "action", name, "action", free, no, trig))
    grabbable = [t for t in b.enemies_of(f) if b.can_grapple(f, t)[0]]
    for mode, name in (("prone", "Shove down"), ("push", "Shove back"), ("grapple", "Grapple")):
        ok = acting and bool(grabbable)
        why = "" if ok else ("no action left this turn" if not acting else "nobody beside you")
        out.append(Option(f"action:{mode}", "action", name, "attack", ok, why, mode, "creature", grabbable))
    if "grappled" in f.conditions or "restrained" in f.conditions:
        out.append(Option("action:escape", "action", "Break free", "action", free, no, "escape"))
    for key in ("persuade", "intimidate", "calm"):
        dc = b.parley_dc(key)
        out.append(Option(f"action:influence:{key}", "action", f"Influence ({key})", "action", free and dc is not None,
                          no or ("" if dc is not None else "they will not listen"), key))
    for it in b.usable_items(f):
        throw = b.throw_value(it)
        ok = acting if throw else (f.action > 0 or b.fast_hands(f))
        out.append(Option(f"item:{it.uid}", "item", b.t.items.name(it, False), "action", ok,
                          "" if ok else "no action left this turn", throw or it.uid, "point" if throw else "creature",
                          [] if throw else b.item_targets(f), b.spell_points(f, throw) if throw and ok else None))
    if b.can_leave(f):
        out.append(Option("action:leave", "action", "Leave the field", "free", True, "", "leave"))
    return out


def _spell_option(b, f, sid: str, ok: bool, why: str) -> Option:
    from realmwalker.rules.combat import spell_id

    sp = b.t.spells[spell_id(sid)]
    cost = {"bonus": "bonus", "reaction": "reaction"}.get(sp.get("cast", "action"), "action")
    mode = sp["target"]
    targets, points, aim = [], None, "none"
    if ok and mode in ("enemy", "ally", "downed_ally", "dead_ally"):
        targets, aim = b.spell_targets(f, sid), "creature"
        if not targets:
            ok, why = False, "no one in reach"
    elif ok and mode in ("point", "direction"):
        points, aim = b.spell_points(f, sid), "point"
    return Option(f"cast:{sid}", "cast", sp["name"], cost, ok, why, sid, aim, targets, points)


def possible(opts: list[Option], kind: str) -> bool:
    return any(o.available for o in opts if o.kind == kind)
