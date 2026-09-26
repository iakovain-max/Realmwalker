"""Magic items (M8): made by code within a budget for their rarity, named and given a history by the AI (or by
built-in words that draw on the world's real past), hidden until identified, and now and then cursed.

- `make(game, rng, tier)`: a new magic item for a treasure of that tier.
- `study(game, char, item)`: an hour with the thing and an Arcana check; a priest can also tell you (services).
- `lift_curse(item)`: what a temple's rite does.
- `dressing_facts(game, item)` / `apply_dressing(item, data)`: what the AI is told, and what we keep.
"""

from __future__ import annotations

from realmwalker.core import dice, textgen
from realmwalker.core.rng import RNG
from realmwalker.rules.items import Item

KIND_WEIGHTS = {"weapon": 3, "armor": 2, "shield": 1, "jewellery": 3, "clothing": 2, "focus": 1}
STUDY_DC = {"uncommon": 12, "rare": 15, "very_rare": 18}


def data(game) -> dict:
    return game.tables.magic


def rarity_for(tier: int, rng: RNG) -> str:
    if tier >= 5:
        return rng.weighted(["uncommon", "rare", "very_rare"], [1, 2, 1])
    if tier >= 3:
        return rng.weighted(["uncommon", "rare"], [3, 2])
    return "uncommon" if rng.chance(0.9) else "rare"


def make(game, rng: RNG, *, tier: int = 1, kind: str | None = None, rarity: str | None = None) -> Item | None:
    spec = data(game)
    items = game.tables.items
    kind = kind or rng.weighted(list(KIND_WEIGHTS), list(KIND_WEIGHTS.values()))
    bases = [b for b in spec["bases"].get(kind, []) if b in items]
    if not bases:
        return None
    base = rng.choice(bases)
    rarity = rarity or rarity_for(tier, rng)
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
            spells = [s for s in spec["charge_spells"] if s in game.tables.spells
                      and game.tables.spells[s]["level"] <= {"uncommon": 1, "rare": 2, "very_rare": 3}[rarity]]
            if not spells:
                continue
            prop["spell"] = rng.choice(spells)
            prop["left"] = prop["value"]
        chosen.append(prop)
        used.add(pid)
        budget -= cost * steps
    if not chosen:
        return None
    magic = {"rarity": rarity, "props": chosen, "identified": False, "cursed": False}
    if rng.chance(float(spec["cursed_chance"])):
        magic["cursed"] = True
        magic["curse"] = dict(rng.choice(spec["curses"]))
    r = spec["rarities"][rarity]
    magic["value"] = int(items.get(base)["value"] * float(r["value_mult"]) + int(r["value_add"]))
    title, story = built_in_words(game, base, rng)
    magic.update(title=title, story=story, source="fallback")
    return Item(uid=0, def_id=base, qty=1, quality="fine", condition=100, made_at=game.world.time, magic=magic)


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
def describe(game, item) -> list[str]:
    """What the player knows about a magic item (marked up)."""
    from realmwalker.core.textgen import escape_markup as esc

    magic = item.magic
    if not magic:
        return []
    if not magic.get("identified"):
        out = ["<magic>There is something strange about it.</> Its nature is hidden: study it (Arcana), ask a "
               "priest, or have a wizard cast Identify (the Spells screen, S)."]
        if magic.get("cursed") and magic.get("curse_known"):
            out.append("<danger>It is cursed, and it will not come off.</>")
        return out
    spec = data(game)
    lines = [f"<magic>{esc(magic.get('title', ''))}</> <dim>({magic.get('rarity', 'uncommon').replace('_', ' ')})</>"]
    for p in magic.get("props", []):
        label = spec["properties"].get(p["kind"], {}).get("label", p["kind"])
        words = {"value": p.get("value", ""), "skill": game.tables.rules["skills"].get(p.get("skill", ""), {}).get(
            "name", p.get("skill", "")), "type": p.get("type", ""),
                 "ability": game.tables.rules["abilities"].get(p.get("ability", ""), {}).get("name", ""),
                 "spell": game.tables.spells[p["spell"]]["name"] if p.get("spell") in game.tables.spells else ""}
        text = label
        for k, v in words.items():
            text = text.replace("{" + k + "}", str(v))
        if p["kind"] == "charges":
            text += f" ({p.get('left', p.get('value'))} left)"
        lines.append(f"· {text}")
    if magic.get("cursed"):
        lines.append(f"<danger>Cursed: {esc(magic['curse']['text'])}</>")
    if magic.get("story"):
        lines.append(("<ai>" if magic.get("source") == "ai" else "<dim>") + esc(magic["story"]) + "</>")
    return lines


def identify(game, item) -> list[str]:
    item.magic["identified"] = True
    item.magic["curse_known"] = item.magic.get("cursed", False)
    game.dirty = True
    name = game.tables.items.name(item, False)
    out = [f"<magic>It is {name}.</>"] + describe(game, item)[1:]
    return out


def study(game, char, item) -> list[str]:
    """An hour spent with it, and an Arcana check. One try a day for each thing."""
    magic = item.magic
    if not magic or magic.get("identified"):
        return ["There is nothing more to learn about it."]
    today = game.moment.total_days
    if magic.get("studied_day") == today:
        return ["You have learned all you can from it today. Try again tomorrow, or ask a priest."]
    magic["studied_day"] = today
    game.pass_time(60, "rest")
    who = max(game.party, key=lambda c: game.sheet(c).skill_bonus("arcana"))
    rng = game.world.rng.child(f"study/{item.uid}/{today}")
    roll = dice.d20(rng).natural + game.sheet(who).skill_bonus("arcana")
    dc = STUDY_DC.get(magic.get("rarity", "uncommon"), 14)
    check = f"<dim>({who.name.split()[0]}'s Arcana {roll} vs {dc})</>"
    if roll >= dc:
        return identify(game, item) + [check]
    return [f"An hour of turning it over tells you little. {check}"]


def lift_curse(item) -> None:
    item.magic["cursed"] = False
    item.magic.pop("curse", None)


# ---------------------------------------------------------------------------- AI words
def needs_dressing(item) -> bool:
    m = item.magic
    return bool(m) and not m.get("identified") and m.get("source") == "fallback" and not m.get("ai_asked")


def dressing_facts(game, item) -> dict:
    spec = data(game)
    rng = game.world.rng.child(f"dress/{item.uid}/{item.def_id}")
    facts = lore(game, rng)
    props = []
    for p in item.magic.get("props", []):
        label = spec["properties"].get(p["kind"], {}).get("label", p["kind"])
        props.append(label.replace("{value}", str(p.get("value", ""))).replace("{skill}", p.get("skill", ""))
                     .replace("{type}", p.get("type", "")).replace("{ability}", p.get("ability", ""))
                     .replace("{spell}", p.get("spell", "").replace("_", " ")))
    return {
        "base": game.tables.items.get(item.def_id)["name"], "rarity": item.magic.get("rarity", "uncommon").replace("_", " "),
        "powers": "; ".join(props), "cursed": "yes" if item.magic.get("cursed") else "no",
        "hero": facts["hero"], "place": facts["place"], "year": facts["year"], "faction": facts["faction"],
    }


def apply_dressing(item, result: dict) -> bool:
    """Keep the AI's name and history, unless the player already knows the old ones."""
    m = item.magic
    if not m or m.get("identified"):
        return False
    if result.get("name"):
        m["title"] = result["name"]
    if result.get("history"):
        m["story"] = result["history"]
    m["source"] = "ai"
    return True
