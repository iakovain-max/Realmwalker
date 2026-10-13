"""What a fighter can do with a feature (docs/EXPANSIONS.md §4.3.7, begun): the abilities that traits and features
give (data/traits.json "activate"), whether each can be used now and why not, and using one.

An activation is {"id", "name", "cost": "action" | "bonus" | "free", "uses": pool id (rules/engine/resources.py),
"requires": [tests from REQUIRES], "via": a battle action done with the bonus action instead (Cunning Action's
"dash", "disengage", "hide"; Keen Mind's "study", aimed at a creature), "aim": what it is aimed at ("enemy" within
"range" feet, "unknown": a creature not yet studied), "effects": [ops] (rules/engine/effects.py)}. A trait may give
several.

`options(b, f)` is the one list of everything a fighter can do now - every attack with each weapon, striking a thing
(a door, a barrel), every spell, every ability, flying up or down, the other actions (Dash, Disengage, Dodge, Hide,
Help, Study, Search, Ready, Shove, Grapple, Influence...), items - each with its cost, whether it can be done and why
not, and what it can be aimed at. The battle screen's
menus, the companions' Auto and the enemy all read it (rules/engine/estimates.py says what each is worth).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from realmwalker.rules.engine import effects, events
from realmwalker.rules.engine.handlers import mastery
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
    if a.get("aim") and not aim_targets(b, f, a):
        return "nobody to aim it at"
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
        if a.get("aim"):
            if target is None:
                return False
            getattr(b, f"do_{a['via']}")(f, target, bonus=True)
        else:
            getattr(b, f"do_{a['via']}")(f, bonus=True)  # the battle action pays for itself, with the bonus action
        if a.get("uses"):
            res.spend(f.char, a["uses"])
        if a.get("effects"):
            c = effects.Cast(b, f, aid, {"target": "self", "name": a["name"], "ability": True}, None, None)
            effects.run(c, a["effects"])
        events.emit(b, "ability_used", actor=f, ability=aid)
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


def _medic_ready(b, f) -> str | None:
    if f.char is None or not any(i.def_id == "healers_kit" and i.condition > 0 for i in f.char.inventory):
        return "no healer's kit"
    if not any(x is not f and (x.active or x.state == "down") and x.hp < x.max_hp and b.gap(f, x) <= 1
               and (x.char is None or x.char.hit_dice > 0) for x in b.team(f.team)):
        return "no hurt friend beside you with a Hit Die to spend"
    return None


def _on_stone(b, f) -> str | None:
    if b.field.underground or "stone" in b.field.name(f.x, f.y) or "rock" in b.field.name(f.x, f.y):
        return None
    return "no stone underfoot"


def _hurt_with_hit_die(b, f) -> str | None:
    if f.char is None or f.char.hit_dice <= 0:
        return "no Hit Dice left"
    return None if f.hp < f.max_hp else "not hurt"


def aim_targets(b, f, a: dict) -> list:
    """Whom an ability can be aimed at now ("aim": "enemy" within its range, seen; "unknown": a creature not yet
    studied)."""
    aim = a.get("aim")
    if aim == "enemy":
        return [e for e in b.enemies_of(f) if e.active and b.feet(f, e) <= int(a.get("range", 5)) and b.can_see(f, e)]
    if aim == "unknown":
        return [e for e in b.enemies_of(f) if e.creature is not None and e.creature.def_id not in b.known]
    return []


def _not_sensing(b, f) -> str | None:
    return "already feeling the stone" if any(bf.get("tremorsense") for bf in f.buffs) else None


def _blink_ready(b, f) -> str | None:
    from realmwalker.rules.engine.handlers import boons

    return boons.blink_ok(b, f)


def _vitality_left(b, f) -> str | None:
    from realmwalker.rules.engine.handlers import boons

    return boons.vitality_ok(b, f)


def _in_shadow(b, f) -> str | None:
    from realmwalker.rules.engine.handlers import boons

    return boons.in_shadow(b, f)


def _surge_ready(b, f) -> str | None:
    from realmwalker.rules.engine.handlers import fighter

    return fighter.surge_ready(b, f)


REQUIRES: dict[str, Callable] = {
    "surge_ready": _surge_ready,
    "blink_ready": _blink_ready,
    "vitality_left": _vitality_left,
    "in_shadow": _in_shadow,
    "not_sensing": _not_sensing,
    "undead_within_30": _undead_near,
    "god_ready": _god_ready,
    "on_stone": _on_stone,
    "medic_ready": _medic_ready,
    "hurt_with_hit_die": _hurt_with_hit_die,
}


# ---------------------------------------------------------------------------- everything a fighter can do now
@dataclass
class Option:
    """One thing a fighter could do now: how it is paid for, whether it can be done and why not, what it is aimed at."""
    id: str  # "attack:main", "cast:fire_bolt", "ability:second_wind", "action:dash", "move:up", "object"...
    kind: str  # attack, object, cast, ability, move, action, item
    name: str
    cost: str  # action, bonus, attack (one attack of the Attack action), free, reaction
    available: bool = True
    why: str = ""
    value: Any = None  # what the battle's do_ method takes (an AttackOption, a spell value, an ability id, an item uid)
    aim: str = "none"  # creature, point, none
    targets: list = field(default_factory=list)  # creatures it can be aimed at from here
    points: set | None = None  # squares it can be aimed at


def options(b, f, only: tuple[str, ...] | None = None) -> list[Option]:
    """Everything `f` can do now, in a fixed order: attacks, spells, abilities, the other actions, items (`only`
    these kinds, if given: the rest is not worked out)."""
    out: list[Option] = []
    acting = b.has_action(f)
    for o in (b.attack_options(f) if only is None or "attack" in only else ()):
        ok = o.available and acting
        why = o.reason if not o.available else ("" if acting else "no action left this turn")
        targets = b.targets_for(f, o) if ok else []
        if ok and not targets:
            ok, why = False, "no one in reach"
        trick = mastery.of(f, o)
        name = f"{o.name} ({trick.title()})" if trick else o.name
        out.append(Option(f"attack:{o.key}", "attack", name, "attack", ok, why, o, "creature", targets))
    if only is None or "object" in only:
        things = b.breakables(f) if acting else {}
        if things or b.t.rules.get("objects", {}).get("terrain"):
            out.append(Option("object", "object", "Break something", "attack", bool(things),
                              "" if things else ("no action left this turn" if not acting else "nothing in reach to break"),
                              things, "point", [], set(things)))
    if only is None or "cast" in only:
        if f.char is not None:
            for sid, ok, why in b.spell_options(f):
                out.append(_spell_option(b, f, sid, ok, why))
        else:
            for sid in b.creature_spells(f):
                out.append(_spell_option(b, f, sid, True, ""))
    for aid, name, ok, why in (b.class_abilities(f) if only is None or "ability" in only else ()):
        a = find(f, aid)
        cost = a["cost"] if a else ("bonus" if aid in ("offhand", "spirit_strike", "hew", "pole_strike") else "action")
        targets = []
        if aid == "offhand" and ok:
            opt = b.offhand_option(f)
            targets = [t for t in b.enemies_of(f) if opt is not None and b.in_reach(f, opt, t)[0]]
        elif aid == "spirit_strike" and ok:
            targets = b.spirit_targets(f)
        elif aid in ("hew", "pole_strike") and ok:
            opt = b.feat_blow_option(f, aid)
            targets = [t for t in b.enemies_of(f) if opt is not None and b.in_reach(f, opt, t)[0]]
        elif a is not None and a.get("aim") and ok:
            targets = aim_targets(b, f, a)
        out.append(Option(f"ability:{aid}", "ability", name, cost, ok, why, aid, "creature" if targets else "none",
                          targets))
    if (only is None or "move" in only) and f.fly_speed > 0:
        up = f.move_left >= 5
        out.append(Option("move:up", "move", "Fly up", "move", up, "" if up else "no movement left", 10))
        if f.z > 0:
            out.append(Option("move:down", "move", "Come down", "move", up, "" if up else "no movement left",
                              -min(f.z, f.move_left // 5 * 5)))
    if only is not None and "action" not in only and "item" not in only:
        return out
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
    for key in ("persuade", "intimidate", "calm") if f.side == "party" and not f.controlled else ():
        dc = b.parley_dc(key)
        out.append(Option(f"action:influence:{key}", "action", f"Influence ({key})", "action", free and dc is not None,
                          no or ("" if dc is not None else "they will not listen"), key))
    for it in b.usable_items(f):
        throw = b.throw_value(it)
        name = b.t.items.name(it, False)
        if not throw:
            ok = f.action > 0 or b.fast_hands(f)
            out.append(Option(f"item:{it.uid}", "item", name, "action", ok, "" if ok else "no action left this turn",
                              it.uid, "creature", b.item_targets(f), None))
            continue
        sp = b.t.spells[throw.split(":", 2)[2]]  # a flask, acid, a net, caltrops, a coating: aimed as its spell says
        cost = "bonus" if sp.get("cast") == "bonus" else "action"
        ok = f.bonus > 0 if cost == "bonus" else acting
        why = "" if ok else f"no {'bonus ' if cost == 'bonus' else ''}action left this turn"
        mode = sp["target"]
        targets = b.spell_targets(f, throw) if ok and mode in ("enemy", "ally") else []
        if ok and mode in ("enemy", "ally") and not targets:
            ok, why = False, "no one in reach"
        aim = "creature" if mode in ("enemy", "ally") else ("point" if mode in ("point", "direction") else "none")
        out.append(Option(f"item:{it.uid}", "item", name, cost, ok, why, throw, aim, targets,
                          b.spell_points(f, throw) if ok and aim == "point" else None))
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
