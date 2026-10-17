"""Poisons (DMG 2024, p. 90-91; Expansion 4 Part C).

A poison is an item with a `poison` record (data/items.json; the schema is POISON in data/schemas.py): how it gets in
(`kind`: contact, ingested, inhaled, injury), the Constitution save's `dc`, and what a failure brings: `damage` (`half`
on a success), the Poisoned condition for `hours` (or `hours_dice`, or until the end of the brewer's next turn: `ends`),
a condition `with` it (Paralyzed, Unconscious or Blinded while Poisoned in this way; `wakes`: a blow ends the sleep;
`fail_by`: only on a failure by that much), `repeat` (saved again at the end of each turn), `fumes` (Burnt Othur's
smoke, saved against at the start of each turn), `slow`, `midnight`, `daily` and `truth` (outside a fight).

In a fight an injury or contact poison is smeared on a weapon with the bonus action (the item spell "coat_poison"; the
buff `poisoned_blade` keeps the item's id, and `poison_dc` a brewed dose's DC): the next hit that cuts or pierces (any
hit, for a contact poison) within a minute delivers it (`on_hit`). Inhaled poisons are thrown vials (their spells
"poison_<id>" in data/spells.json, built from the same record: `battle_ops`). Ingested ones are slipped into a cup in
a conversation (game/shadows.py) or drunk by mistake (the Potion of Poison: `drink`).

Everything here is logic: it reads the tables and changes fighters and characters; screens only show it.
"""

from __future__ import annotations

from realmwalker.core import dice

COATS = ("injury", "contact")
# Venom a magic blade makes itself (the Dagger of Venom, DMG 2024: on the next hit of any kind within a minute).
BLADES = {"venom_dagger": {"kind": "contact", "dc": 15, "damage": "2d10", "hours": 0.0167, "name": "the dagger's venom"}}
ONE_MINUTE = 10  # rounds


def record(tables, def_id: str) -> dict | None:
    rec = tables.items.get(def_id).get("poison")
    return dict(rec) if rec else None


def of_item(tables, item) -> dict | None:
    """The poison an item holds, with what its own tags say: a brewed dose's DC ("dc:<n>"), a harvested venom's
    creature ("venom:<creature id>")."""
    rec = record(tables, item.def_id)
    if rec is None:
        return None
    for t in item.tags:
        if t.startswith("venom:"):
            rec.update(venom_of(tables, t[len("venom:"):]))
        elif t.startswith("dc:"):
            rec["dc"] = int(t[3:])
    return rec


def venomous(tables, cid: str) -> dict | None:
    """The poisoned blow of a creature (its first attack that deals poison damage), or None."""
    if cid not in tables.creatures:
        return None
    for a in tables.creatures[cid].get("attacks", []):
        if a.get("damage_type") == "poison" or a.get("type") == "poison":
            return {"damage": a.get("damage", "1d6"), "dc": a.get("dc")}
        for e in a.get("extra", ()):
            if e.get("type") == "poison":
                return {"damage": e["damage"], "dc": a.get("dc")}
    return None


def venom_of(tables, cid: str) -> dict:
    """A harvested venom's numbers: the creature's own poison damage, and a save of 8 + its proficiency bonus + its
    Constitution modifier (the DC of its poison, when its stat block prints one)."""
    c = tables.creatures[cid] if cid in tables.creatures else {}
    v = venomous(tables, cid) or {"damage": "1d6", "dc": None}
    con = int((c.get("abilities") or {}).get("con", 10))
    dc = int(v["dc"] or 8 + int(c.get("pb", 2)) + (con - 10) // 2)
    return {"damage": v["damage"], "dc": dc, "half": True, "creature": cid}


def label(tables, item) -> str:
    """A harvested venom's name says whose it is."""
    for t in item.tags:
        if t.startswith("venom:") and t[6:] in tables.creatures:
            return f"vial of {tables.creatures[t[6:]]['name']} venom"
    return ""


# ---------------------------------------------------------------------------------------------------- in a fight
def rounds_of(rec: dict) -> int:
    """How long the Poisoned condition lasts in a fight: rounds, or -1 for the whole of it."""
    if rec.get("hours_dice") or float(rec.get("hours", 0)) >= ONE_MINUTE / 600 * 2:
        return -1
    return ONE_MINUTE


def battle_ops(rec: dict) -> list[dict]:
    """The kernel's ops for a poison delivered in a fight (rules/engine/effects.py)."""
    if not rec.get("dc"):  # (basic poison: no save, only its damage)
        return [{"op": "damage", "damage": rec["damage"], "type": "poison"}] if rec.get("damage") else []
    fail = []
    if rec.get("hours") or rec.get("hours_dice") or rec.get("ends"):
        cond = {"op": "condition", "condition": "poisoned"}
        if rec.get("ends"):
            cond["ends"] = rec["ends"]
        else:
            cond["rounds"] = rounds_of(rec)
        if rec.get("repeat"):
            cond.update(repeat_save=True, save="con", save_dc=int(rec["dc"]))
        fail.append(cond)
    withc = None
    if rec.get("with"):
        withc = {"op": "condition", "condition": rec["with"], "with": "poisoned"}
        if rec.get("wakes"):
            withc["on_damage"] = True
    if rec.get("fumes"):
        fail.append({"op": "fumes", "dc": int(rec["dc"]), "damage": rec["fumes"]["damage"],
                     "successes": int(rec["fumes"]["successes"])})
    if withc is not None and not rec.get("fail_by"):
        fail.append(withc)
    save = {"op": "save", "ability": "con", "dc": int(rec["dc"]), "against": "poisoned"}
    if rec.get("damage") and rec.get("sure"):
        return [{"op": "damage", "damage": rec["damage"], "type": "poison"}, {**save, "on_fail": fail}]
    if rec.get("damage"):
        save.update(damage=rec["damage"], type="poison", half=bool(rec.get("half")))
    if fail:
        save["on_fail"] = fail
    if withc is not None and rec.get("fail_by"):
        save["fail_by"] = {"by": int(rec["fail_by"]), "on_fail": [withc]}
    return [save]


def coat(b, f, item) -> None:
    """After the coating's bonus action (Battle.do_cast with "coat_poison"): the blade carries this poison."""
    rec = of_item(b.t, item)
    for bf in f.buffs:
        if "poisoned_blade" in bf:
            bf["poisoned_blade"] = item.def_id
            if rec is not None and rec.get("dc"):
                bf["poison_dc"] = int(rec["dc"])
            if rec is not None and rec.get("creature"):
                bf["venom"] = rec["creature"]
            break


def blade(b, f) -> tuple[dict, dict] | None:
    """(buff, poison record) of the poison on this fighter's weapon, if any."""
    bf = next((x for x in f.buffs if x.get("poisoned_blade")), None)
    if bf is None:
        return None
    pid = bf["poisoned_blade"]
    if pid in BLADES:
        rec = dict(BLADES[pid])
    else:
        rec = record(b.t, pid) if isinstance(pid, str) and pid in b.t.items else {"kind": "injury", "dc": 0,
                                                                                  "damage": "1d4"}
    if rec is None:
        return None
    if bf.get("venom"):
        rec.update(venom_of(b.t, bf["venom"]))
    if bf.get("poison_dc"):
        rec["dc"] = int(bf["poison_dc"])
    return bf, rec


def delivers(rec: dict, dtype: str, poisoners: bool = False) -> bool:
    """A contact poison works on any hit, an injury poison on one that cuts or pierces (a Poisoner's own dose: any
    hit that deals damage)."""
    return rec["kind"] == "contact" or poisoners or dtype in ("piercing", "slashing")


def on_hit(b, att, target, opt, crit: bool) -> None:
    """The poison on a weapon goes into the wound (Battle._attack, after the blow's damage)."""
    got = blade(b, att)
    if got is None or opt.kind.startswith("spell"):
        return
    bf, rec = got
    if not delivers(rec, opt.damage_type, poisoners=bf["poisoned_blade"] == "poisoners_dose"):
        return
    if not (target.active or target.state == "down"):
        return
    att.buffs = [x for x in att.buffs if x is not bf]  # spent on the hit, as the book says
    b._event("poison", who=target.id, by=att.id, poison=bf["poisoned_blade"])
    if not rec.get("dc"):
        b._hit(att, target, dice.roll(rec["damage"], b.rng, double_dice=crit).total, "poison", crit=False,
               weapon=opt.name)
        return
    from realmwalker.rules.engine import effects

    pid = bf["poisoned_blade"]
    name = rec.get("name") or (b.t.items.get(pid)["name"] if isinstance(pid, str) else "poison")
    c = effects.Cast(b, att, name, {"target": "enemy", "name": name, "ability": True, "classes": ["item"]}, target,
                     None, dc=int(rec["dc"]))
    effects.run(c, battle_ops(rec), target)
    if "poisoned" in target.conditions and target.char is not None:  # (how long it lingers after the fight)
        hours = float(rec.get("hours") or 0) or (14.0 if rec.get("hours_dice") else 1.0)
        target.__dict__["poison_hours"] = max(float(target.__dict__.get("poison_hours", 0.0)), hours)


def turn_start(b, f) -> None:
    """Burnt Othur Fumes: the smoke in the lungs, saved against at the start of each of its turns."""
    bf = next((x for x in f.buffs if x.get("fumes")), None)
    if bf is None or not f.active:
        return
    if b._save(f, "con", int(bf["fumes"]), against=("poisoned",)):
        bf["fumes_saved"] = int(bf.get("fumes_saved", 0)) + 1
        if bf["fumes_saved"] >= int(bf.get("fumes_successes", 3)):
            f.buffs = [x for x in f.buffs if x is not bf]
            b.say(f"{f.the_name} coughs the last of the smoke out.", "info")
        return
    b.say(f"{f.the_name} chokes on the fumes.", "danger" if f.side == "party" else "info")
    b._hit(None, f, dice.roll(bf.get("fumes_dice", "1d6"), b.rng).total, "poison", crit=False, weapon="fumes")


def carried_hours(tables, f) -> float:
    """How long a character stays Poisoned after a fight, by the longest poison that took (`Fighter.poison_hours`)."""
    return float(f.__dict__.get("poison_hours", 0.0))


# ---------------------------------------------------------------------------------------------------- the Auto
def coatings(b, f) -> list:
    """The coatings this fighter carries that its weapon in hand could deliver."""
    if f.char is None:
        return []
    return [it for it in f.char.inventory if (b.t.items.get(it.def_id).get("use") or {}).get("coat")
            and (of_item(b.t, it) or {}).get("kind") in COATS]


def worth(b, item) -> float:
    """What a coating is worth to the Auto: the poison's expected damage, a little for what else it brings."""
    rec = of_item(b.t, item) or {}
    n, sides, plus = dice.parse(rec["damage"]) if rec.get("damage") else (0, 0, 0)
    value = n * (sides + 1) / 2 + plus
    if rec.get("with"):
        value += 12.0
    elif rec.get("hours") or rec.get("ends"):
        value += 3.0
    return value


# ---------------------------------------------------------------------------------------------------- masked potions
MASK = "secretly:"  # an item's tag: what it really is (a Potion of Poison passing for a potion of healing)


def masked(item) -> str | None:
    """What a thing really is, when it passes for something else."""
    return next((t[len(MASK):] for t in item.tags if t.startswith(MASK)), None)


def mask(item, real: str) -> None:
    item.tags = [t for t in item.tags if not t.startswith(MASK)] + [MASK + real]


def unmask(tables, item) -> str:
    """Shown for what it is: it becomes the thing it really was. Returns its true name."""
    real = masked(item)
    if real and real in tables.items:
        item.def_id = real
    item.tags = [t for t in item.tags if not t.startswith(MASK)]
    return tables.items.get(item.def_id)["name"]


def battle_drink(b, f, target, item) -> None:
    """A masked poison poured into someone in a fight, for a healing draught."""
    real = masked(item)
    rec = record(b.t, real) if real else None
    if rec is None:
        return
    from realmwalker.rules.engine import effects

    name = b.t.items.get(real)["name"]
    b.say(f"<danger>It is no healing draught: {target.the_name} doubles over. ({name})</>", "danger")
    c = effects.Cast(b, f, name, {"target": "ally", "name": name, "ability": True, "classes": ["item"]}, target,
                     None, dc=int(rec["dc"]))
    effects.run(c, battle_ops(rec), target)


# ---------------------------------------------------------------------------------------------------- outside a fight
def drink(game, char, item) -> list[str]:
    """Someone drinks a poison (a Potion of Poison taken for a healing draught, or a poisoned cup)."""
    rec = of_item(game.tables, item) or {}
    return suffer(game, char, rec, game.tables.items.get(item.def_id)["name"])


def immune(game, char) -> bool:
    from realmwalker.rules import magic

    return "proof_against_poison" in magic.traits(char) or "item_ward_poison" in magic.traits(char)


def save(game, char, dc: int, rng) -> tuple[bool, int]:
    """A Constitution save outside a fight (antitoxin gives advantage)."""
    from realmwalker.rules.character import Sheet

    s = Sheet(char, game.tables)
    bonus = s.save_bonus("con")
    roll = dice.d20(rng, advantage=char.effects.get("antitoxin", 0) > 0).natural
    return roll + bonus >= dc, roll + bonus


def suffer(game, char, rec: dict, name: str) -> list[str]:
    """A poison's work on a character outside a fight: the save, the damage, the hours of sickness."""
    rng = game.world.rng.child(f"poison/{char.name}/{game.world.time}")
    who = char.name.split()[0]
    if immune(game, char):
        return [f"{who} feels a moment's sickness, and it passes. <dim>({name}: warded against poison)</>"]
    ok, total = save(game, char, int(rec.get("dc", 10)), rng)
    out = []
    dmg = 0
    if rec.get("damage"):
        dmg = dice.roll(rec["damage"], rng).total
        if ok and not rec.get("sure"):
            dmg = dmg // 2 if rec.get("half") else 0
    if dmg:
        char.hp = max(0, char.hp - dmg)
    hours = 0.0
    if not ok:
        hours = float(rec.get("hours") or 0)
        if rec.get("hours_dice"):
            hours = float(dice.roll(rec["hours_dice"], rng).total)
        if hours:
            char.effects["poisoned"] = max(char.effects.get("poisoned", 0.0), hours)
    words = f"(Constitution {total} vs DC {rec.get('dc', 10)})"
    if ok:
        out.append(f"{who} retches but keeps it down. " + (f"<warn>{dmg} poison damage.</> " if dmg else "")
                   + f"<dim>{words}</>")
    else:
        bits = [f"<danger>{who} is poisoned</>"]
        if dmg:
            bits.append(f"<danger>{dmg} poison damage</>")
        if hours:
            bits.append(f"sick for {health_hours(hours)}")
        out.append(", ".join(bits) + f". <dim>{words}</>")
    if char.hp <= 0:
        out.append(f"<danger>{who} collapses.</>")
    return out


def health_hours(hours: float) -> str:
    if hours < 1:
        return "a few minutes"
    if hours < 2:
        return "an hour"
    if hours < 30:
        return f"{int(round(hours))} hours"
    return f"{int(round(hours / 24))} days"
