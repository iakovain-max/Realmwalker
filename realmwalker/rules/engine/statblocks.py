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
FLAVOUR = ("name", "plural", "body", "morale", "ai", "names", "gear", "money", "loot", "butcher", "descriptions",
           "summon")  # (summon: a summoned creature's numbers by the slot, rules/allies.summon_def)


def resolve(cid: str, flavour: dict, blocks: dict) -> dict:
    """The creature as the game uses it."""
    sb = blocks[flavour["statblock"]]
    out = {
        "statblock": flavour["statblock"],
        "name": sb["name"].lower(), "plural": sb["name"].lower() + "s",
        "kind": sb["type"], "tags": list(sb.get("tags", [])), "size": sb["size"],
        "cr": float(sb["cr"]), "xp": int(sb["xp"]), "pb": int(sb["pb"]),
        "alignment": sb.get("alignment", "unaligned"), "treasure": list(sb.get("treasure", ["none"])),
        "ac": int(sb["ac"]), "hp": sb["hp"], "initiative": int(sb["initiative"]),
        "speed": int(sb["speed"].get("walk", 0)), "speeds": dict(sb["speed"]),
        "abilities": dict(sb["abilities"]), "saves": dict(sb.get("saves", {})), "skills": dict(sb.get("skills", {})),
        "senses": dict(sb.get("senses", {})), "darkvision": int(sb.get("senses", {}).get("darkvision", 0)),
        "passive": int(sb.get("passive", 10)), "languages": list(sb.get("languages", [])),
        "telepathy": int(sb.get("telepathy", 0) or 0),
        "resist": list(sb.get("resist", [])), "vulnerable": list(sb.get("vulnerable", [])),
        "immune": list(sb.get("immune", [])), "condition_immune": list(sb.get("condition_immune", [])),
        # Traits, and the bonus actions and reactions the game knows by a trait (Nimble Escape, Charge, Parry...).
        "traits": [TRAIT_ALIASES.get(t["id"], t["id"]) for t in sb.get("traits", [])]
                  + [a["id"] for a in sb.get("bonus_actions", []) + sb.get("reactions", []) if a.get("kind") == "special"
                     and not a.get("casts") and not a.get("casts_one_of")],
        "trait_numbers": {TRAIT_ALIASES.get(t["id"], t["id"]): {k: v for k, v in t.items() if k not in ("id", "name", "note")}
                          for t in sb.get("traits", [])},
        "legendary_resistance": sb.get("legendary_resistance"), "legendary": sb.get("legendary"),
        "bonus_actions": list(sb.get("bonus_actions", [])), "reactions": list(sb.get("reactions", [])),
    }
    extras = flavour.get("attack_extras", {})
    swap = flavour.get("action_swap", {})
    actions = [swap.get(a["id"], a) for a in sb.get("actions", [])]
    out["attacks"] = attacks(actions, extras)
    # A bonus action that is a blow or a save against one creature (the elephant's Trample), made besides the Action.
    out["attacks"] += [{**x, "bonus_action": True}
                       for x in attacks([a for a in sb.get("bonus_actions", []) if a.get("kind") != "special"], extras)]
    multi = sb.get("multiattack")
    if multi and swap:
        rename = {old: new["id"] for old, new in swap.items()}
        multi = {**multi, "of": [rename.get(x, x) for x in multi.get("of", [])],
                 "attacks": [{**x, "id": rename.get(x["id"], x["id"])} for x in multi.get("attacks", [])]}
    plan = multiattack_plan(multi, out["attacks"])
    if plan:
        out["multiattack"] = len(plan)
        out["multiattack_plan"] = plan
    sc = sb.get("spellcasting")
    if sc:
        mod = (int(sb["abilities"][sc["ability"]]) - 10) // 2
        dc = sc.get("dc") or 8 + int(sb["pb"]) + mod  # (a block whose spells need neither prints neither)
        attack = sc.get("attack") if sc.get("attack") is not None else int(sb["pb"]) + mod
        out["spellcasting"] = {"ability": sc["ability"], "dc": int(dc), "attack": int(attack),
                               "at_will": list(sc.get("at_will", [])),
                               "per_day": {str(k): list(v) for k, v in (sc.get("per_day") or {}).items()},
                               "slots": list(sc.get("slots", [])), "self_only": bool(sc.get("self_only"))}
        if sc.get("levels"):  # ("Fireball (level 4 version)": cast at that level)
            out["spellcasting"]["levels"] = {k: int(v) for k, v in sc["levels"].items()}
        before = set(sc.get("before", ()))  # (Mage Armor "included in AC", Mind Blank "cast before combat")
        out["spells"] = [s for s in dict.fromkeys(out["spellcasting"]["at_will"]
                                                  + [s for v in out["spellcasting"]["per_day"].values() for s in v])
                         if s not in before]
    # Bonus actions that cast a spell so many times a day (a fanatic's Spiritual Weapon, an acolyte's Divine Aid,
    # cast with the bonus action whatever the spell's own casting time), and reactions that do (a mage's Protective
    # Magic: Counterspell or Shield, three a day between them).
    for a in sb.get("bonus_actions", []) + sb.get("reactions", []):
        spells = [a["casts"]] if a.get("casts") else list(a.get("casts_one_of", []))
        if spells and a.get("uses"):
            sc_out = out.setdefault("spellcasting", {"ability": "wis", "dc": 10, "attack": 2, "at_will": [], "per_day": {},
                                                     "slots": []})
            if a in sb.get("bonus_actions", []):
                sc_out.setdefault("bonus", []).extend(s for s in spells if s not in sc_out.get("bonus", []))
            n = int(str(a["uses"]).split("/")[0])
            if len(spells) == 1:
                sc_out["per_day"].setdefault(str(n), []).extend(spells)
            else:  # "Bless, Healing Word or Sanctuary": one use between them
                sc_out.setdefault("shared", {})[a["id"]] = {"uses": n, "spells": spells}
            out["spells"] = list(dict.fromkeys(out.get("spells", []) + spells))
    for key in FLAVOUR:
        if key in flavour:
            out[key] = flavour[key]
    out["traits"] = list(dict.fromkeys(out["traits"] + list(flavour.get("traits", []))))
    for k, v in flavour.get("override", {}).items():
        out[k] = v
    out.setdefault("morale", "warrior")
    out.setdefault("ai", {"role": "brute"})
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
        for k in ("extra", "on_hit", "recharge", "uses", "plus_level", "with_multiattack", "spares", "dust",
                  "advantage_if", "requires", "fail_by", "max_size"):
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
                        "half": bool(a.get("half", True)), "on_fail": a.get("on_fail", []),
                        **({"range": [int(a["range"]), int(a["range"])]} if a.get("range") else {}),
                        **({"enemies": True} if a.get("enemies") else {})})  # (Holy Word: each enemy in it)
        elif kind == "save":  # one creature in range makes the save (a spider's web, a wight's touch)
            reach = int(a.get("range", 5))
            out.append({**base, "kind": "melee" if reach <= 5 else "ranged", "single_save": True, "save": a["save"],
                        "dc": int(a["dc"]), "half": bool(a.get("half", False)), "on_fail": a.get("on_fail", []),
                        "range": [reach, reach], "reach": False})
    return out


def multiattack_plan(m: dict | None, atks: list[dict]) -> list[list[str]]:
    """The attacks a Multiattack makes, in order, each a list of the actions that may make it: "two Rend attacks"
    [[rend], [rend]]; "a Bite and two Claws"; "two attacks, Sword or Bow in any combination" [[sword, bow], [sword,
    bow]]; "it can replace one attack with Life Drain" adds the replacement to the last."""
    if not m:
        return []
    if m.get("attacks"):
        plan = [[x["id"]] for x in m["attacks"] for _ in range(int(x.get("count", 1)))]
    else:
        of = list(m.get("of", []))
        count = int(m.get("count", len(of) or 1))
        if not of:
            of = [a["id"] for a in atks if a["kind"] == "melee"][:1]
        plan = [list(of) for _ in range(count)] if m.get("any_combination") else [[of[i % len(of)]] for i in range(count)]
    known = {a["id"] for a in atks}
    for r in m.get("replace", []):
        if r.get("with") in known:
            for slot in plan[-int(r.get("count", 1)):]:
                slot.append(r["with"])
    return plan


ENDS = {"end_of_target_next_turn": "own_turn_end", "start_of_target_next_turn": "own_turn_start",
        "start_of_source_next_turn": "caster_turn_start", "end_of_source_next_turn": "caster_turn_end"}


def ops(block_effects: list[dict]) -> list[dict]:
    """A stat block's on_hit / on_fail effects as the kernel's effect ops (rules/engine/effects.py)."""
    out = []
    for e in block_effects:
        kind = e.get("op")
        if kind == "condition":
            o = {"op": "condition", "condition": e["condition"]}
            for k in ("max_size", "charge_feet"):
                if e.get(k):
                    o[k] = e[k]
            if e.get("not_types"):
                o["not_kinds"] = list(e["not_types"])
            if e.get("not_species"):
                o["not_species"] = list(e["not_species"])
            if e.get("save_to_avoid"):
                e = {**e, "save": e["save_to_avoid"]}
            if e.get("escape_dc"):
                o["escape"] = int(e["escape_dc"])
            if e.get("while") == "grappled":
                o["with"] = "grappled"  # (Restrained while Grappled: it ends with the hold)
            ends = e.get("ends")
            if ends == "damage":
                o["on_damage"], ends = True, None  # (the pseudodragon's sleep: until it takes damage)
            if e.get("rounds"):
                o["rounds"] = int(e["rounds"])  # (the pseudodragon's poison: an hour, the whole fight)
            elif e["condition"] == "grappled" or o.get("with") or o.get("on_damage") or ends == "repeat_save":
                o["rounds"] = -1  # (held until it breaks free, is woken or saves: not a round's worth)
            if ends in ENDS:
                o["ends"] = ENDS[ends]
            if ends == "repeat_save":
                o["repeat_save"], o["save"] = True, e.get("save", "con")
                o["save_dc"] = e.get("dc")
            if e.get("dc") and e.get("save") and ends != "repeat_save":
                out.append({"op": "save", "ability": e["save"], "dc": int(e["dc"]), "on_fail": [o]})
            else:
                out.append(o)
        elif kind == "damage" and e.get("when") is None:
            out.append({"op": "damage", "damage": e["damage"], "type": e.get("type", "bludgeoning"),
                        **{k: e[k] for k in ("max_size", "charge_feet") if e.get(k)}})
        elif kind == "push":
            out.append({"op": "push", "feet": int(e.get("feet", 5)), "now": True,
                        **{k: e[k] for k in ("max_size",) if e.get(k)}})
        elif kind == "special" and e.get("attach"):
            out.append({"op": "attach"})
        elif kind == "kernel":  # (the kernel's own ops, written out: a summoned spirit's blows, Expansion 3 F.2)
            out.extend(e["ops"])
    return out


def size_at_most(size: str, limit: str) -> bool:
    return SIZE_ORDER.index(size) <= SIZE_ORDER.index(limit)
