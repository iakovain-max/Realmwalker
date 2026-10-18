"""Magic items: made by code within a budget for their rarity, named and given a history by built-in words that draw
on the world's real past, hidden until identified, now and then cursed; and the framework of the Dungeon Master's
Guide (2024) around them (Expansion 1): attunement, charges that come back at dawn, identification the 2024 way,
artifacts with properties rolled for this world, and sentient things with minds of their own.

- `make(game, rng, tier=, kind=, rarity=, props=)`: a new magic item (the rules read it in rules/magic.py).
- `make_artifact(game, rng, kind=)`: an artifact, its properties rolled on the DMG's tables.
- `study(game, char, item)`: a short rest spent handling it tells what it does (never its curse).
- `attune(game, char, item)` / `end_attunement(...)`: a short rest's bond; three at most; a curse holds it.
- `tick(game, before, after)`: dawn (charges, an artifact's spite) and what sentient things want.
- `notice(game, tag, creatures=)`: something a sentient thing may like or hate (a victory, a flight, a find...).
- `lift_curse(item)`: what a temple's rite does.
"""

from __future__ import annotations

from realmwalker.core import dice, textgen
from realmwalker.core.rng import RNG
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.rules import magic as magicrules
from realmwalker.rules.items import Item

KIND_WEIGHTS = {"weapon": 3, "armor": 2, "shield": 1, "jewellery": 3, "clothing": 2, "focus": 1}
RARITY_ORDER = ("common", "uncommon", "rare", "very_rare", "legendary", "artifact")
SHORT_REST = 60
DAY = 24 * 60
SPELL_LEVEL_FOR = {"common": 0, "uncommon": 1, "rare": 2, "very_rare": 3, "legendary": 4, "artifact": 5}


def data(game) -> dict:
    return game.tables.magic


def rarity_for(tier: int, rng: RNG) -> str:
    if tier >= 5:
        return rng.weighted(["uncommon", "rare", "very_rare"], [1, 2, 1])
    if tier >= 3:
        return rng.weighted(["uncommon", "rare"], [3, 2])
    return "uncommon" if rng.chance(0.9) else "rare"


def at_least(rarity: str, floor: str) -> bool:
    return RARITY_ORDER.index(rarity) >= RARITY_ORDER.index(floor) if rarity in RARITY_ORDER else False


def make(game, rng: RNG, *, tier: int = 1, kind: str | None = None, rarity: str | None = None,
         props: list[dict] | None = None, sentient: bool | None = None, bases: list[str] | None = None,
         qty: int = 1) -> Item | None:
    """A magic item of a kind and rarity: its properties chosen within the rarity's budget (or the `props` given),
    named, storied and given a look; maybe cursed, maybe awake."""
    spec = data(game)
    items = game.tables.items
    kind = kind or rng.weighted(list(KIND_WEIGHTS), list(KIND_WEIGHTS.values()))
    bases = [b for b in (bases or spec["bases"].get(kind, [])) if b in items]
    if not bases:
        return None
    base = rng.choice(bases)
    rarity = rarity or rarity_for(tier, rng)
    chosen = [dict(p) for p in props] if props is not None else _choose_props(game, rng, kind, rarity)
    if not chosen:
        return None
    magic = {"rarity": rarity, "kind": kind, "props": chosen, "identified": False, "cursed": False}
    if props is None and rng.chance(float(spec["cursed_chance"])):
        magic["cursed"] = True
        magic["curse"] = dict(rng.choice(spec["curses"]))
    r = spec["rarities"][rarity]
    magic["value"] = int(items.get(base)["value"] * float(r["value_mult"]) + int(r["value_add"]))
    if kind == "ammo":
        magic["value"] //= 10  # ten pieces are worth a potion of the same rarity (DMG 2024)
    title, story = built_in_words(game, base, rng)
    magic.update(title=title, story=story)
    magic["look"] = look_for(game, magic, rng.child("look"))
    item = Item(uid=0, def_id=base, qty=max(1, qty), quality="fine", condition=100, made_at=game.world.time,
                magic=magic)
    awake = (sentient if sentient is not None else rng.chance(float(spec["sentient"]["chance"].get(rarity, 0.0)))) \
        and kind != "ammo"
    if awake:
        make_sentient(game, item, rng.child("mind"))
    set_attunement(game, item)
    return item


def _choose_props(game, rng: RNG, kind: str, rarity: str) -> list[dict]:
    spec = data(game)
    budget = float(spec["rarities"][rarity]["budget"])
    chosen: list[dict] = []
    used = set()
    for _ in range(12):
        if budget < 0.5:
            break
        options = [(pid, p) for pid, p in spec["properties"].items()
                   if kind in p["for"] and float(p["cost"]) <= budget and pid not in used]
        if not options:
            break
        if kind == "weapon" and "bonus" not in used and any(pid == "bonus" for pid, _ in options):
            pid, p = next((pid, p) for pid, p in options if pid == "bonus")
        elif kind in ("armor", "shield") and "ac" not in used and any(pid == "ac" for pid, _ in options):
            pid, p = next((pid, p) for pid, p in options if pid == "ac")
        else:
            pid, p = rng.choice(options)
        cost = float(p["cost"])
        steps = min(int(p["max"]), int(budget // cost)) if cost else 1
        steps = max(1, rng.randint(1, max(1, steps)) if pid not in ("bonus", "ac") else steps)
        prop = {"kind": pid, "value": steps * int(p.get("step", 1))}
        if pid == "skill":
            prop["skill"] = rng.choice(spec["skills"])
        elif pid == "resist":
            prop["type"] = rng.choice(spec["resist_types"])
        elif pid == "ability":
            prop["ability"] = rng.choice(spec["abilities"])
        elif pid == "charges":
            top = SPELL_LEVEL_FOR.get(rarity, 1)
            spells = [s for s in spec["charge_spells"] if s in game.tables.spells
                      and 0 < game.tables.spells[s]["level"] <= max(1, top)]
            if not spells:
                continue
            prop["spell"] = rng.choice(spells)
            prop["left"] = prop["value"]
            prop["regain"] = f"1d{max(2, prop['value'])}"  # like a wand: some of it back each dawn
        chosen.append(prop)
        used.add(pid)
        budget -= cost * steps
    return chosen


def set_attunement(game, item: Item) -> None:
    """DMG 2024: most items of real power need attunement; a plain +N weapon or armour does not. A focus or a thing
    that casts spells binds only to one who casts spells of their own."""
    spec = data(game)
    magic = item.magic
    kinds = {p.get("kind") for p in magic.get("props", [])}
    needs = (bool(kinds & set(spec.get("attune_props", []))) or at_least(magic["rarity"], spec.get("attune_from", "rare"))
             or bool(magic.get("artifact")) or bool(magic.get("sentient")))
    magic["attune"] = needs
    if needs and magic.get("kind") == "focus" and "charges" in kinds:
        magic["attune_by"] = "spellcaster"


# ---------------------------------------------------------------------------- artifacts
def make_artifact(game, rng: RNG, *, kind: str | None = None, title: str = "", story: str = "") -> Item | None:
    """An artifact: a legendary item's powers plus properties rolled once on the DMG's Artifact Properties tables
    (rolled again where the game cannot run one yet), indestructible but for one way this world remembers."""
    kind = kind or rng.weighted(["weapon", "armor", "jewellery", "focus"], [4, 2, 3, 2])
    item = make(game, rng.child("base"), kind=kind, rarity="legendary", sentient=False)
    if item is None:
        return None
    magic = item.magic
    magic["rarity"] = "artifact"
    magic["cursed"] = False
    magic.pop("curse", None)
    art = data(game)["artifact"]
    rolled: list[str] = []
    for group in ("minor_good", "major_good", "minor_bad", "major_bad"):
        lo, hi = art["count"][group]
        for _ in range(rng.randint(lo, hi)):
            for _try in range(20):
                pid = _d100(art[group], rng)
                if pid in rolled:
                    continue
                prop = _artifact_prop(game, pid, rng)
                if prop is None:
                    continue  # nothing the game can run yet (a creature, a spell level or a quest it does not have)
                rolled.append(pid)
                prop["artifact"] = group
                magic["props"].append(prop)
                if art["properties"][pid].get("on"):
                    magic.setdefault("on", []).append(art["properties"][pid]["on"])
                break
    if "jealous" in magic.get("on", []):
        magic["jealous"] = True
    facts = lore(game, rng)
    magic["destroy"] = textgen.fill(rng.choice(art["destroy"]), rng, {}, {"hero": facts["hero"], "place": facts["place"]})
    if title:
        magic["title"] = title
    if story:
        magic["story"] = story
    magic["value"] = int(data(game)["rarities"]["artifact"]["value_add"])
    magic["look"] = look_for(game, magic, rng.child("look"))
    if rng.chance(float(data(game)["sentient"]["chance"].get("artifact", 0.5))):
        make_sentient(game, item, rng.child("mind"))
    set_attunement(game, item)
    return item


def _d100(table: list, rng: RNG):
    roll = rng.randint(1, 100)
    return next(v for lo, hi, v in table if lo <= roll <= hi)


def _artifact_prop(game, pid: str, rng: RNG) -> dict | None:
    spec = data(game)
    d = spec["artifact"]["properties"].get(pid)
    if d is None:
        return None  # quest, avatar, prisoner: rolled again (they need a person, or a creature not yet in the game)
    words: dict[str, str] = {}
    prop = dict(d.get("prop") or {"kind": "flag", "flag": pid})
    if pid == "skill":
        prop["skill"] = rng.choice(sorted(game.tables.rules["skills"]))
        words["skill"] = game.tables.rules["skills"][prop["skill"]]["name"]
    elif pid == "resist":
        prop["type"] = rng.choice(spec["resist_types"])
        words["type"] = prop["type"]
    elif pid == "ability":
        prop["ability"] = rng.choice(spec["abilities"])
        words["ability"] = game.tables.rules["abilities"][prop["ability"]]["name"]
    elif prop.get("kind") == "charges":
        level = int(d.get("level", 1))
        pool = sorted(s for s, sp in game.tables.spells.defs.items() if int(sp.get("level", 0)) == level
                      and "item" not in sp.get("classes", []) and not _spell_unfit(sp))
        if not pool:
            return None
        prop["spell"] = rng.choice(pool)
        prop["left"] = int(prop.get("value", 1))
        words["spell"] = game.tables.spells[prop["spell"]]["name"]
    elif pid == "hated_by":
        types = list(spec["artifact"]["hated_types"])
        prop["value"] = rng.choice(types)
        words["creature"] = prop["value"]
    prop["id"] = pid
    text = d["text"]
    for k, v in words.items():
        text = text.replace("{" + k + "}", str(v))
    prop["text"] = text
    return prop


def _spell_unfit(spell: dict) -> bool:
    from realmwalker.rules import spells as spellrules

    return spellrules.has_op(spell, "identify", "revive")


# ---------------------------------------------------------------------------- sentient things
def make_sentient(game, item: Item, rng: RNG) -> None:
    """DMG 2024: Intelligence, Wisdom and Charisma (4d6, the lowest dropped), an alignment, a way of speaking,
    senses and a special purpose."""
    s = data(game)["sentient"]

    def stat() -> int:
        rolls = sorted(rng.randint(1, 6) for _ in range(4))
        return sum(rolls[1:])

    mind = {"int": stat(), "wis": stat(), "cha": stat(), "alignment": _d100(s["alignment"], rng),
            "communication": _d10(s["communication"], rng), "senses": _d4(s["senses"], rng),
            "purpose": rng.choice(sorted(s["purposes"]))}
    if mind["purpose"] == "aligned" and mind["alignment"] in ("neutral", "neutral evil"):
        # Never neutral (DMG); and an evil one needs a side against which the world's creatures stand: the lawful.
        mind["alignment"] = rng.choice(["lawful good", "chaotic good", "lawful evil"])
    if mind["purpose"] == "bane":
        mind["creature"] = rng.choice(list(data(game)["artifact"]["hated_types"]) + ["humanoid"])
    elif mind["purpose"] == "protector":
        mind["people"] = rng.choice(s["protects"])
    elif mind["purpose"] == "templar":
        faiths = sorted(game.tables.factions["faiths"])
        mind["faith"] = game.tables.factions["faiths"][rng.choice(faiths)].get("name", "the old gods") if faiths else \
            "the old gods"
    item.magic["sentient"] = mind


def _d10(table: list, rng: RNG):
    roll = rng.randint(1, 10)
    return next(v for lo, hi, v in table if lo <= roll <= hi)


def _d4(table: list, rng: RNG):
    roll = rng.randint(1, 4)
    return next(v for lo, hi, v in table if lo <= roll <= hi)


def purpose_text(game, mind: dict) -> str:
    p = data(game)["sentient"]["purposes"][mind["purpose"]]
    text = p["text"]
    for key in ("creature", "people", "faith"):
        text = text.replace("{" + key + "}", str(mind.get(key, "")))
    return text


def bearer(game, item: Item):
    """Who the thing is bound to in the party (attunement), or None."""
    for c in list(game.party) + list(getattr(game, "waiting", [])):
        if item.uid in c.attuned and c.alive:
            return c
    return None


def sentient_items(game) -> list[tuple[Item, object]]:
    out = []
    seen = set()
    for c in game.party:
        for it in magicrules.attuned_items(c):
            if it.magic.get("sentient") and it.uid not in seen and c.alive:
                seen.add(it.uid)
                out.append((it, c))
    return out


def _voice(game, item: Item, mood: str, rng: RNG, **extra) -> str:
    s = data(game)["sentient"]
    mind = item.magic["sentient"]
    line = rng.choice(s["voices"][mind["communication"]][mood])
    name = esc(game.tables.items.name(item, False))
    return line.replace("{item}", name).replace("{demand}", esc(extra.get("demand", "")))


def _meaning(item: Item, tag: str, creatures: list[dict]) -> str | None:
    mind = item.magic["sentient"]
    p = mind["purpose"]
    types = {c.get("type", "") for c in creatures}
    aligns = {c.get("alignment", "") for c in creatures}
    if p == "bane":
        if mind.get("creature") not in types:
            return None
        tag = {"victory": "victory_bane", "fled": "fled_bane", "parley": "parley_bane"}.get(tag, tag)
    if p == "aligned" and tag == "victory":
        mine = mind["alignment"]
        opposed = {"good": "evil", "evil": "good", "lawful": "chaotic", "chaotic": "lawful"}
        if any(opposed[side] in a for side in opposed if side in mine for a in aligns):
            tag = "victory_opposed"  # good against evil, law against chaos (the DMG's "diametrically opposed")
        else:
            return None
    return tag


def notice(game, tag: str, *, creatures: list[dict] | None = None, hard: bool = False) -> list[str]:
    """Something happened that a sentient thing may care about. Pleased, it says so (and an urgent want of its may be
    met); angered, there is a conflict: the bearer's Charisma save, or a demand (DMG 2024)."""
    out: list[str] = []
    things = sentient_items(game)
    if not things:
        return out
    spec = data(game)["sentient"]
    angered = False
    for item, who in things:
        mind = item.magic["sentient"]
        purpose = spec["purposes"][mind["purpose"]]
        meant = _meaning(item, tag, creatures or [])
        if meant is None:
            continue
        if meant == "victory" and hard:
            meant = "victory_hard" if "victory_hard" in purpose["pleased"] else meant
        rng = game.world.rng.child(f"sentient/{item.uid}/{game.world.time}/{tag}")
        if meant in purpose["pleased"]:
            mind["content"] = game.world.time
            demand = mind.get("demand")
            if demand and demand.get("kind") == "dreams":
                out += _satisfy(game, item, rng)
            elif mind.get("said_day") != game.moment.total_days:
                mind["said_day"] = game.moment.total_days
                out.append(_voice(game, item, "pleased", rng))
        elif meant in purpose["angered"]:
            angered = True
            out += conflict(game, item, who, rng)
    for line in out:
        game.say(f"<magic>{line}</>", "magic")
    if out:
        game.cue("danger" if angered else "spell")
    return out


def conflict(game, item: Item, who, rng: RNG) -> list[str]:
    """The bearer has gone against the thing: a Charisma save (DC 12 + its Charisma modifier), or it makes a demand."""
    mind = item.magic["sentient"]
    if mind.get("demand"):
        return [_voice(game, item, "angered", rng)]
    dc = 12 + (mind["cha"] - 10) // 2
    roll = dice.d20(rng).natural + game.sheet(who).save_bonus("cha")
    if roll >= dc:
        return [_voice(game, item, "angered", rng) + f" <dim>({who.name.split()[0]} holds firm: Charisma {roll} vs {dc})</>"]
    demand = _demand(game, item, who, rng)
    mind["demand"] = demand
    spec = data(game)["sentient"]["demands"]
    text = spec[demand["kind"]].replace("{thing}", demand.get("thing_name", "thing"))
    return [_voice(game, item, "demand", rng, demand=text) + f" <dim>(Charisma {roll} vs {dc})</>"]


def _demand(game, item: Item, who, rng: RNG) -> dict:
    kinds = ["dreams"]
    if game.tables.items.slots_for(item):
        kinds.append("keep_close")
    others = [it for it in who.inventory if it.uid != item.uid and it.magic]
    if others:
        kinds.append("get_rid")
    if len([c for c in game.party if c.alive]) > 1:
        kinds.append("change")
    kind = rng.choice(kinds)
    days = 7 if kind == "dreams" else 3
    demand = {"kind": kind, "since": game.world.time, "until": game.world.time + days * DAY, "stage": 0,
              "bearer": who.name}
    if kind == "get_rid":
        thing = rng.choice(others)
        demand["thing"] = thing.uid
        demand["thing_name"] = game.tables.items.name(thing, False)
    return demand


def _met(game, item: Item, demand: dict) -> bool:
    who = bearer(game, item)
    kind = demand["kind"]
    if kind == "keep_close":
        return who is not None and who.slot_of(item.uid) is not None
    if kind == "get_rid":
        return all(demand.get("thing") != it.uid for c in game.party for it in c.inventory)
    if kind == "change":
        return who is not None and who.name != demand.get("bearer")
    return False  # dreams: met by something it likes (notice)


def _satisfy(game, item: Item, rng: RNG) -> list[str]:
    mind = item.magic["sentient"]
    mind.pop("demand", None)
    mind.pop("seized_until", None)
    item.magic["suppressed"] = False
    return [data(game)["sentient"]["satisfied"].replace("{item}", game.tables.items.name(item, False))]


def check_demands(game) -> list[str]:
    """Whether the things' demands are met; past the time they gave: first they withhold their power, then they try
    to take hold of the bearer (a Charisma save, or charmed for 1d12 hours: in a fight they fight as it wills)."""
    out: list[str] = []
    spec = data(game)["sentient"]
    for item, who in sentient_items(game):
        mind = item.magic["sentient"]
        demand = mind.get("demand")
        rng = game.world.rng.child(f"demand/{item.uid}/{game.world.time}")
        if mind.get("seized_until") and game.world.time >= mind["seized_until"]:
            mind.pop("seized_until")
            out.append(spec["freed"].replace("{name}", esc(who.name.split()[0])).replace(
                "{item}", esc(game.tables.items.name(item, False))))
        if not demand:
            continue
        if demand["kind"] != "keep_close" and _met(game, item, demand):
            out += _satisfy(game, item, rng)
            continue
        if game.world.time < demand["until"]:
            continue
        if demand["kind"] == "keep_close" and _met(game, item, demand):
            out += _satisfy(game, item, rng)
            continue
        name = esc(game.tables.items.name(item, False))
        if demand["stage"] == 0:
            demand["stage"] = 1
            demand["until"] = game.world.time + 3 * DAY
            item.magic["suppressed"] = True
            out.append(spec["withheld"].replace("{item}", name))
        elif not mind.get("seized_day") == game.moment.total_days:
            mind["seized_day"] = game.moment.total_days  # once a day at most
            demand["until"] = game.world.time + 3 * DAY
            dc = 12 + (mind["cha"] - 10) // 2
            roll = dice.d20(rng).natural + game.sheet(who).save_bonus("cha")
            if roll < dc:
                mind["seized_until"] = game.world.time + rng.randint(1, 12) * 60
                out.append(spec["seized"].replace("{item}", name).replace("{name}", esc(who.name.split()[0])) +
                           f" <dim>(Charisma {roll} vs {dc})</>")
            else:
                out.append(_voice(game, item, "angered", rng) + f" <dim>({who.name.split()[0]} resists: Charisma "
                                                                   f"{roll} vs {dc})</>")
    for line in out:
        game.say(f"<magic>{line}</>", "magic")
    if out:
        game.cue("danger")
    return out


def seized(game, char) -> bool:
    """Whether a sentient thing has hold of this character now (they fight on Auto, as it wills)."""
    for it in magicrules.attuned_items(char):
        mind = it.magic.get("sentient")
        if mind and mind.get("seized_until") and game.world.time < mind["seized_until"]:
            return True
    return False


# ---------------------------------------------------------------------------- the bond (attunement)
def attune(game, char, item: Item) -> list[str]:
    """A short rest spent focused on the thing: bound to it at the end, if nothing forbids it (PHB 2024). An artifact's
    spite strikes then, and a curse makes itself known."""
    why = magicrules.can_attune(char, item, game.sheet(char), list(game.party) + list(getattr(game, "waiting", [])))
    name = esc(game.tables.items.name(item, False))
    first = esc(char.name.split()[0])
    if why:
        return [f"{first} cannot bind to the {name}: {esc(why)}."]
    game.pass_time(SHORT_REST, "rest")
    if game.over is not None or not char.alive:
        return []
    item.magic.pop("loosed", None)  # (bound again, a curse Remove Curse loosened takes hold again)
    out = [f"<magic>{first} spends an hour with the {name} and feels it settle, like a hand closing.</>"]
    if not item.magic.get("identified"):
        # The bond teaches what the thing is (the hour spent with it is more than the PHB's study asks); what it does
        # to its bearer when bound is learned in the same moment it strikes.
        item.magic["identified"] = True
        out.append(f"<magic>Bound to it, {first} knows it now: {esc(game.tables.items.name(item, False))}.</>")
    for other in list(magicrules.attuned_items(char)):
        if item.magic.get("jealous") and other.uid != item.uid:
            char.attuned.remove(other.uid)
            out.append(f"The bond with the {game.tables.items.name(other, False)} snaps.")
    char.attuned.append(item.uid)
    game.cue("buff")
    if item.magic.get("cursed") and not item.magic.get("curse_known"):
        item.magic["curse_known"] = True
        out.append("<danger>Something tightens as the bond closes. It is cursed, and it will not let go.</>")
    rng = game.world.rng.child(f"attune/{item.uid}/{game.world.time}")
    for effect in item.magic.get("on", []):
        out += _on_attune(game, char, item, effect, rng)
    game.dirty = True
    return out


def _on_attune(game, char, item: Item, effect: str, rng: RNG) -> list[str]:
    first = char.name.split()[0]
    if effect == "drains":
        ability = rng.choice(sorted(char.abilities))
        if char.abilities[ability] > 3:
            char.abilities[ability] = max(3, char.abilities[ability] - 2)
            name = game.tables.rules["abilities"][ability]["name"]
            return [f"<danger>Something goes out of {first} into it: {name} falls by 2.</>"]
    elif effect == "shock":
        hurt = dice.roll("8d10", rng).total
        char.hp -= hurt
        game.cue("magic_hit")
        line = f"<danger>Pain like a struck bell: {hurt} psychic harm.</>"
        if char.hp <= 0:
            if -char.hp >= char.max_hp:
                char.death_cause = "the artifact's bond burned out their mind"
                from realmwalker.game.survival import check_death

                check_death(game, char)
                return [line]
            from realmwalker.game.fight import lie_senseless

            char.hp = 1
            return [line, f"<danger>{first} drops senseless.</> " + lie_senseless(game, 1)]
        return [line]
    elif effect == "deadly_bond":
        roll = dice.d20(rng).natural + game.sheet(char).save_bonus("con")
        if roll < 10:
            char.death_cause = "the artifact's bond stopped their heart"
            from realmwalker.game.survival import check_death

            check_death(game, char)
            return [f"<danger>The bond closes like a fist around {first}'s heart (Constitution {roll} vs 10).</>"]
        return [f"<dim>The bond closes around {first}'s heart, and lets go (Constitution {roll} vs 10).</>"]
    return []


def end_attunement(game, char, item: Item) -> list[str]:
    name = game.tables.items.name(item, False)
    first = char.name.split()[0]
    if not magicrules.is_attuned(char, item):
        return [f"{first} is not bound to the {name}."]
    if item.magic.get("cursed") and not item.magic.get("loosed"):
        item.magic["curse_known"] = True
        return [f"<danger>{first} tries to put the {name} out of mind, and cannot. It is cursed; a priest might lift "
                f"it.</>"]
    game.pass_time(SHORT_REST, "rest")
    if item.uid in char.attuned:
        char.attuned.remove(item.uid)
    game.dirty = True
    return [f"{first} spends an hour unpicking the bond with the {name}. It is just a thing again."]


def prune(game) -> None:
    """A bond ends when the thing is gone from the party (sold, lost, left behind) or its bearer dies."""
    here = {it.uid for c in list(game.party) + list(getattr(game, "waiting", [])) for it in c.inventory}
    for c in list(game.party) + list(getattr(game, "waiting", [])):
        if c.attuned:
            c.attuned = [u for u in c.attuned if u in here and c.alive]


# ---------------------------------------------------------------------------- the days
def tick(game, before, after) -> None:
    """Called after time passes: dawn brings charges back (and an artifact's spite at potions and scrolls); the
    sentient things' demands come due; bonds to things that are gone end."""
    prune(game)
    b = before.total_days * 24 + before.hour
    a = after.total_days * 24 + after.hour
    dawns = sum(1 for d in range(before.total_days, after.total_days + 1) if b < d * 24 + 6 <= a)
    if dawns:
        dawn(game)
    if a != b:
        if sentient_items(game):
            check_demands(game)
            idle(game)


def dawn(game) -> None:
    rng = game.world.rng.child(f"dawn/{game.world.time}")
    pack = [it for c in game.party for it in c.inventory]
    seen = set()
    unique = []
    for it in pack:
        if id(it) not in seen:
            seen.add(id(it))
            unique.append(it)
    magicrules.dawn(unique, rng)
    for c in game.party:
        for it in magicrules.attuned_items(c):
            for effect in it.magic.get("on", []):
                if effect in ("sours_potions", "blanks_scrolls"):
                    _spoil(game, c, effect)
        if c.attuned and magicrules.flag(c, "spoils_holy_water"):
            _spoil(game, c, "spoils_holy_water")


def _spoil(game, char, effect: str) -> None:
    t = game.tables.items
    gone = []
    for it in list(char.inventory):
        d = t.get(it.def_id)
        if effect == "sours_potions" and d.get("use", {}).get("heal") and not it.magic:
            gone.append(it)
        elif effect == "blanks_scrolls" and d.get("use", {}).get("scroll"):
            gone.append(it)
        elif effect == "spoils_holy_water" and it.def_id == "holy_water":
            gone.append(it)
    if not gone:
        return
    from realmwalker.rules.inventory import remove_item

    for it in gone:
        remove_item(char, it.uid, it.qty)
    what = {"sours_potions": "potions have gone flat and lifeless", "blanks_scrolls": "scrolls have faded blank",
            "spoils_holy_water": "holy water is plain water now"}[effect]
    game.say(f"<warn>By morning the {what} in the pack. The artifact is to blame.</>", "warn")


def idle(game) -> None:
    """A seeker that has been given nothing to seek for a week grows restless (DMG: conflict)."""
    for item, _who in sentient_items(game):
        mind = item.magic["sentient"]
        purpose = data(game)["sentient"]["purposes"][mind["purpose"]]
        if "idle" not in purpose["angered"]:
            continue
        last = int(mind.get("content", mind.setdefault("content", game.world.time)))
        if game.world.time - last >= 7 * DAY:
            mind["content"] = game.world.time
            rng = game.world.rng.child(f"idle/{item.uid}/{game.world.time}")
            for line in conflict(game, item, _who, rng):  # this one alone has waited a week
                game.say(f"<magic>{line}</>", "magic")
            game.cue("danger")


# ---------------------------------------------------------------------------- the look
def look_for(game, magic: dict, rng: RNG) -> dict:
    """How a magic item looks, from the words in its name and story and from its powers: its metal, the colour of its
    cloth (or a shield's field), an emblem, and maybe a faint glow."""
    spec = data(game)["looks"]
    words = set(textgen_words(f"{magic.get('title', '')} {magic.get('story', '')}"))

    def by_words(table: str, pool: str) -> str:
        for keys, value in spec[table]:
            if words & set(keys):
                return value
        return rng.choice(spec[pool])

    look = {"metal": by_words("metal", "metals"), "cloth": by_words("cloth", "cloths"),
            "emblem": by_words("emblem", "emblems")}
    glow = None
    for p in magic.get("props", []):
        key = p["kind"] + (":" + str(p.get("type") or p.get("ability") or "") if p.get("type") or p.get("ability") else "")
        glow = spec["glow_props"].get(key) or spec["glow_props"].get(p["kind"])
        if glow:
            break
    chance = float(spec["glow_chance"].get(magic.get("rarity", "uncommon"), 0.9 if magic.get("rarity") in
                                           ("legendary", "artifact") else 0.2))
    if glow is None and rng.chance(chance):
        glow = rng.choice(spec["glows"])
    elif glow is not None and not rng.chance(min(1.0, chance + 0.4)):
        glow = None
    if glow:
        look["glow"] = glow
    return look


def textgen_words(text: str) -> list[str]:
    import re

    return re.findall(r"[a-z]+", text.lower())


def lore(game, rng: RNG) -> dict:
    """Real names from the world's past: a hero or ruler, a place, a year, a faction."""
    w = game.world
    heroes = [f for f in w.figures.values() if f.role in ("legend", "past") and f.died is not None]
    hero = rng.choice(heroes) if heroes else None
    events = [e for e in w.history if e.get("places")]
    event = rng.choice(events) if events else None
    place = ""
    if event is not None:
        pid = event["places"][0]
        if 0 <= pid < len(w.settlements):
            place = w.settlements[pid].name
    if not place:
        place = rng.choice(w.settlements).name if w.settlements else "the old kingdom"
    facs = [f for f in w.factions.values()]
    return {
        "hero": hero.full_name() if hero is not None else "a forgotten king",
        "hero_first": hero.first_name if hero is not None else "Aldric",
        "place": place,
        "year": str(event["year"] if event is not None else (hero.died if hero is not None else 900)),
        "faction": rng.choice(facs).name if facs else "a vanished order",
    }


def built_in_words(game, base: str, rng: RNG) -> tuple[str, str]:
    spec = data(game)
    facts = lore(game, rng)
    base_name = game.tables.items.get(base)["name"]
    values = {"base": " ".join(w[:1].upper() + w[1:] for w in base_name.split()),
              "hero": facts["hero_first"], "place": facts["place"], "year": facts["year"],
              "epithet": rng.choice(spec["names"]["epithets"]), "faction": facts["faction"]}
    title = textgen.fill(rng.choice(spec["names"]["patterns"]), rng, {}, values)
    title = title[:1].upper() + title[1:]
    story = textgen.fill(rng.choice(spec["stories"]), rng, {}, {**values, "hero": facts["hero"]})
    return title, story


# ---------------------------------------------------------------------------- knowing what it is
def prop_text(game, p: dict) -> str:
    """One property in words (an artifact's own words when it has them)."""
    if p.get("text"):
        text = p["text"]
    else:
        spec = data(game)
        label = spec["properties"].get(p["kind"], {}).get("label", p["kind"])
        words = {"value": p.get("value", ""), "skill": game.tables.rules["skills"].get(p.get("skill", ""), {}).get(
            "name", p.get("skill", "")), "type": p.get("type", ""),
                 "ability": game.tables.rules["abilities"].get(p.get("ability", ""), {}).get("name", ""),
                 "spell": game.tables.spells[p["spell"]]["name"] if p.get("spell") in game.tables.spells else ""}
        text = label
        for k, v in words.items():
            text = text.replace("{" + k + "}", str(v))
        if p["kind"] == "charges":
            text += f" ({p.get('left', p.get('value'))} left" + (f", {p['regain']} back at dawn" if p.get("regain")
                                                                  else ", all back at dawn") + ")"
    if p.get("kind") == "charges" and p.get("text") and not p.get("at_will") and not magicrules.pooled(p):
        text += f" ({magicrules.charges_left(p)} left)"
    if p.get("kind") == "absorb":  # (the Rod of Absorption's stored levels)
        text += f" ({p.get('left', 0)} levels stored; {p.get('value', 0)} of {p.get('most', 50)} drunk in its life)"
    if p.get("kind") == "pool":  # (a wand's or a staff's store, shared by its spells)
        text += f" ({p.get('left', p.get('value'))} of {p.get('value')} left)"
    return text


def describe(game, item, char=None) -> list[str]:
    """What the player knows about a magic item (marked up)."""
    from realmwalker.core.textgen import escape_markup as esc

    magic = item.magic
    if not magic:
        return []
    bond = _bond_line(game, item, char)
    if not magic.get("identified"):
        out = ["<magic>There is something strange about it.</> Its nature is hidden: handle it through a short rest "
               "(Study it), ask a priest, or have a wizard cast Identify (the Spells screen, S)."]
        if bond:
            out.append(bond)
        if magic.get("cursed") and magic.get("curse_known"):
            out.append("<danger>It is cursed, and it will not let go.</>")
        return out
    rarity = magic.get("rarity", "uncommon").replace("_", " ")
    lines = [f"<magic>{esc(magic.get('title', ''))}</> <dim>({rarity})</>"]
    if bond:
        lines.append(bond)
    for p in magic.get("props", []):
        if p.get("kind") == "trait" and not p.get("text"):
            continue  # (a power the item's other words already tell: the Staff of Charming's daily resistance)
        mark = "<danger>" if p.get("artifact") in ("minor_bad", "major_bad") else ""
        lines.append(f"· {mark}{esc(prop_text(game, p))}{'</>' if mark else ''}")
    for effect in magic.get("on", []):
        if effect in data(game)["artifact"]["properties"] and not any(p.get("id") == effect for p in magic["props"]):
            lines.append(f"· <danger>{esc(data(game)['artifact']['properties'][effect]['text'])}</>")
    mind = magic.get("sentient")
    if mind:
        talk = {"emotion": "it makes its feelings felt", "speech": "it speaks aloud",
                "telepathy": "it speaks into the mind"}[mind["communication"]]
        lines.append(f"<magic>It is awake.</> Intelligence {mind['int']}, Wisdom {mind['wis']}, Charisma "
                     f"{mind['cha']}; {mind['alignment']}; {talk}; it {mind['senses']}.")
        lines.append(f"<magic>{esc(purpose_text(game, mind))}</>")
        demand = mind.get("demand")
        if demand:
            want = data(game)["sentient"]["demands"][demand["kind"]].replace("{thing}", demand.get("thing_name", "thing"))
            lines.append(f"<warn>It wants: {esc(want)}</>")
        if magic.get("suppressed"):
            lines.append("<danger>It is withholding its power.</>")
    if magic.get("cursed") and magic.get("curse_known"):
        lines.append(f"<danger>Cursed: {esc(magic['curse']['text'])}</>")
    if magic.get("destroy"):
        lines.append(f"<dim>It cannot be broken by any ordinary means. {esc(magic['destroy'])}</>")
    if magic.get("story"):
        lines.append("<dim>" + esc(magic["story"]) + "</>")
    return lines


def _bond_line(game, item, char) -> str:
    if not item.magic.get("attune"):
        return ""
    who = bearer(game, item) if hasattr(game, "party") else None
    if who is not None:
        return f"<good>Bound to {who.name.split()[0]}.</>"
    need = item.magic.get("attune_by")
    extra = " (only by one who casts spells)" if need == "spellcaster" else ""
    if isinstance(need, list):
        names = [n + "s" for n in need]
        extra = " (only by " + (", ".join(names[:-1]) + " or " if len(names) > 1 else "") + names[-1] + ")"
    return f"<warn>It must be bound to work{extra}: a short rest's attunement (a). Three such bonds at most.</>"


def identify(game, item) -> list[str]:
    """What it is and does (never a curse: DMG 2024, most ways of knowing a thing miss it)."""
    item.magic["identified"] = True
    game.dirty = True
    name = game.tables.items.name(item, False)
    out = [f"<magic>It is {name}.</>"] + describe(game, item)[1:]
    return out


def study(game, char, item) -> list[str]:
    """PHB 2024: a short rest spent handling it, in physical contact, teaches what it does and how to use it."""
    magic = item.magic
    if not magic or magic.get("identified"):
        return ["There is nothing more to learn about it."]
    game.pass_time(SHORT_REST, "rest")
    first = char.name.split()[0]
    return [f"{first} spends an hour turning it over, feeling for the magic in it."] + identify(game, item)


def lift_curse(item) -> None:
    item.magic["cursed"] = False
    item.magic.pop("curse", None)
    # (a curse that is a power of the thing itself goes with it: the Sword of Vengeance is a +1 weapon after)
    item.magic["props"] = [p for p in item.magic.get("props", ()) if not p.get("curse_prop")]
