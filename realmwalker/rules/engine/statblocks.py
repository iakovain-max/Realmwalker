"""2025 stat blocks (data/statblocks.json) turned into the creatures a fight uses (docs/EXPANSIONS.md §4.3.8).

A creature in data/creatures.json is its *flavour* - what the game calls it, how it looks and behaves in the world
(name, plural, body, morale, rank, names, gear, money, loot, butcher, descriptions; extra traits the game gives it,
such as a scavenger's "takes_food"; per-action extras such as the wound a bite leaves or a disease it carries) - plus
`"statblock": id`, the 2025 Monster Manual block it fights with. `resolve` puts the two together into the fields the
battle has always read (ac, hp, speed, abilities, skills, darkvision, attacks, multiattack, traits, immune...), and
adds the 2025 ones (initiative, speeds, senses, resist, condition_immune, multiattack_plan, legendary_resistance,
legendary, spellcasting at will and per day).

The block's own numbers win, except where the flavour says otherwise on purpose (`"override": {...}`).
"""

from __future__ import annotations

# The 2025 trait names the game's traits answer to (data/traits.json).
TRAIT_ALIASES = {
    "sunlight_sensitivity": "sunlight_sensitive",
    "spider_climb": "spider_climb",
    "web_walker": "web_walker",
    "keen_smell": "keen_senses",
    "keen_hearing_and_smell": "keen_senses",
}
SIZE_ORDER = ("tiny", "small", "medium", "large", "huge", "gargantuan")
FLAVOUR = ("name", "plural", "body", "morale", "rank", "names", "gear", "money", "loot", "butcher", "descriptions")


def resolve(cid: str, flavour: dict, blocks: dict) -> dict:
    """The creature as the game uses it."""
    sb = blocks[flavour["statblock"]]
    out = {
        "statblock": flavour["statblock"],
        "name": sb["name"].lower(), "plural": sb["name"].lower() + "s",
        "kind": sb["type"], "tags": list(sb.get("tags", [])), "size": sb["size"],
        "cr": float(sb["cr"]), "xp": int(sb["xp"]), "pb": int(sb["pb"]),
        "ac": int(sb["ac"]), "hp": sb["hp"], "initiative": int(sb["initiative"]),
        "speed": int(sb["speed"].get("walk", 0)), "speeds": dict(sb["speed"]),
        "abilities": dict(sb["abilities"]), "saves": dict(sb.get("saves", {})), "skills": dict(sb.get("skills", {})),
        "senses": dict(sb.get("senses", {})), "darkvision": int(sb.get("senses", {}).get("darkvision", 0)),
        "passive": int(sb.get("passive", 10)), "languages": list(sb.get("languages", [])),
        "telepathy": int(sb.get("telepathy", 0) or 0),
        "resist": list(sb.get("resist", [])), "vulnerable": list(sb.get("vulnerable", [])),
        "immune": list(sb.get("immune", [])), "condition_immune": list(sb.get("condition_immune", [])),
        "traits": [TRAIT_ALIASES.get(t["id"], t["id"]) for t in sb.get("traits", [])],
        "trait_numbers": {TRAIT_ALIASES.get(t["id"], t["id"]): {k: v for k, v in t.items() if k not in ("id", "name", "note")}
                          for t in sb.get("traits", [])},
        "legendary_resistance": sb.get("legendary_resistance"), "legendary": sb.get("legendary"),
        "bonus_actions": list(sb.get("bonus_actions", [])), "reactions": list(sb.get("reactions", [])),
    }
    extras = flavour.get("attack_extras", {})
    out["attacks"] = attacks(sb.get("actions", []), extras)
    plan = multiattack_plan(sb.get("multiattack"), out["attacks"])
    if plan:
        out["multiattack"] = len(plan)
        out["multiattack_plan"] = plan
    sc = sb.get("spellcasting")
    if sc:
        out["spellcasting"] = {"ability": sc["ability"], "dc": int(sc["dc"]), "attack": int(sc.get("attack", 0)),
                               "at_will": list(sc.get("at_will", [])),
                               "per_day": {str(k): list(v) for k, v in (sc.get("per_day") or {}).items()},
                               "slots": list(sc.get("slots", []))}
        out["spells"] = list(dict.fromkeys(out["spellcasting"]["at_will"]
                                           + [s for v in out["spellcasting"]["per_day"].values() for s in v]))
    for key in FLAVOUR:
        if key in flavour:
            out[key] = flavour[key]
    out["traits"] = list(dict.fromkeys(out["traits"] + list(flavour.get("traits", []))))
    for k, v in flavour.get("override", {}).items():
        out[k] = v
    out.setdefault("morale", "warrior")
    out.setdefault("rank", "front")
    out.setdefault("body", "humanoid")
    out.setdefault("gear", [])
    out.setdefault("descriptions", [f"A {out['name']}."])
    return out


def attacks(actions: list[dict], extras: dict) -> list[dict]:
    """The block's attack actions as the battle's attack list (a weapon both thrown and swung is two entries)."""
    out = []
    for a in actions:
        kind = a.get("kind")
        base = {"id": a["id"], "name": a["name"].lower(), "bonus": int(a.get("bonus", 0)), "damage": a.get("damage", "0"),
                "damage_type": a.get("type", "bludgeoning")}
        for k in ("extra", "on_hit", "recharge", "uses"):
            if a.get(k):
                base[k] = a[k]
        base.update(extras.get(a["id"], {}))
        if kind in ("melee", "melee_or_ranged"):
            out.append({**base, "kind": "melee", "reach": int(a.get("reach", 5)) >= 10})
        if kind in ("ranged", "melee_or_ranged"):
            rng = a.get("range") or [20, 60]
            out.append({**base, "kind": "ranged", "range": [int(rng[0]), int(rng[1])]})
        if kind == "save" and a.get("area"):
            out.append({**base, "kind": "ranged", "area": dict(a["area"]), "save": a["save"], "dc": int(a["dc"]),
                        "half": bool(a.get("half", True)), "on_fail": a.get("on_fail", [])})
    return out


def multiattack_plan(m: dict | None, atks: list[dict]) -> list[str]:
    """The attacks a Multiattack makes, by action id, in order ("two Rend attacks"; "a Bite and two Claws")."""
    if not m:
        return []
    if m.get("attacks"):
        return [x["id"] for x in m["attacks"] for _ in range(int(x.get("count", 1)))]
    of = list(m.get("of", []))
    count = int(m.get("count", len(of) or 1))
    if not of:
        of = [a["id"] for a in atks if a["kind"] == "melee"][:1]
    return [of[i % len(of)] for i in range(count)]


ENDS = {"end_of_target_next_turn": "own_turn_end", "start_of_target_next_turn": "own_turn_start",
        "start_of_source_next_turn": "caster_turn_start", "end_of_source_next_turn": "caster_turn_end"}


def ops(block_effects: list[dict]) -> list[dict]:
    """A stat block's on_hit / on_fail effects as the kernel's effect ops (rules/engine/effects.py)."""
    out = []
    for e in block_effects:
        kind = e.get("op")
        if kind == "condition":
            o = {"op": "condition", "condition": e["condition"]}
            if e.get("max_size"):
                o["max_size"] = e["max_size"]
            if e.get("escape_dc"):
                o["escape"] = int(e["escape_dc"])
            ends = e.get("ends")
            if ends in ENDS:
                o["ends"] = ENDS[ends]
            if ends == "repeat_save":
                o["repeat_save"], o["save"] = True, e.get("save", "con")
                o["save_dc"] = e.get("dc")
            if e.get("dc") and e.get("save") and ends != "repeat_save":
                out.append({"op": "save", "ability": e["save"], "dc": int(e["dc"]), "on_fail": [o]})
            else:
                out.append(o)
        elif kind == "damage":
            out.append({"op": "damage", "damage": e["damage"], "type": e.get("type", "bludgeoning")})
        elif kind == "push":
            out.append({"op": "push", "feet": int(e.get("feet", 5)), "now": True})
    return out


def size_at_most(size: str, limit: str) -> bool:
    return SIZE_ORDER.index(size) <= SIZE_ORDER.index(limit)
