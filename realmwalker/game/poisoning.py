"""Poison outside a fight (Expansion 4 Part C; DMG 2024 p. 90): venom harvested from the slain.

A venomous creature that is dead (`rules/poisons.venomous`: one of its blows deals poison damage) yields one dose to a
poisoner's kit: 1d6 minutes and a DC 20 Intelligence (Nature) check by whoever does it best with the kit. A success is
a dose (a named poison when the creature is in that poison's `from` list, else a vial of its own venom); a failure is
nothing, and a failure by 5 or more pricks the harvester with the creature's poison. The rules of a poison itself are
in rules/poisons.py; buying, brewing and slipping one into a cup are game/shadows.py and the camp's crafts.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules import poisons
from realmwalker.rules.items import Item

HARVEST_DC = 20
KIT = "poisoners_kit"


def has_kit(game) -> bool:
    return any(it.def_id == KIT for c in game.party if c.alive for it in c.inventory)


def harvestable(game, dead) -> list:
    """The bodies a poisoner's kit could take a dose from (none without a kit in the party)."""
    if not has_kit(game):
        return []
    return [cr for cr in dead if poisons.venomous(game.tables, cr.def_id) is not None]


def poison_for(game, cid: str) -> str | None:
    """The book's poison this creature gives, when it is one (Serpent Venom from a venomous snake...)."""
    sb = (game.tables.creatures[cid].get("statblock") or cid) if cid in game.tables.creatures else cid
    for pid, d in game.tables.items.defs.items():
        if set((d.get("poison") or {}).get("from", ())) & {cid, sb}:
            return pid
    return None


def harvester(game):
    """Whoever does the work best with the kit: Intelligence (Nature), and the kit's proficiency."""
    from realmwalker.game import camp
    from realmwalker.rules.character import Sheet

    able = [c for c in game.party if c.alive and c.hp > 0] or game.party
    return max(able, key=lambda c: Sheet(c, game.tables).skill_bonus("nature")
               + camp.tool_bonus(game, c, "nature", KIT)[0])


def harvest(game, bodies) -> tuple[list[Item], list[str]]:
    """Take venom from each body. Returns (new items, messages)."""
    from realmwalker.game import camp
    from realmwalker.rules.character import Sheet

    if not bodies or not has_kit(game):
        return [], []
    who = harvester(game)
    first = who.name.split()[0]
    sheet = Sheet(who, game.tables)
    bonus = sheet.skill_bonus("nature")
    extra, adv = camp.tool_bonus(game, who, "nature", KIT)
    items: list[Item] = []
    msgs: list[str] = []
    minutes = 0
    for cr in bodies:
        rng = game.world.rng.child(f"venom/{cr.uid}/{game.world.time}")
        minutes += dice.roll("1d6", rng).total
        roll = dice.d20(rng, advantage=adv).natural
        total = roll + bonus + extra
        name = game.tables.creatures[cr.def_id]["name"]
        words = f"<dice>Nature with a poisoner's kit ({first}): {roll} + {bonus + extra} = {total} vs DC {HARVEST_DC}</>"
        if total >= HARVEST_DC:
            pid = poison_for(game, cr.def_id)
            it = Item(0, pid or "harvested_venom", 1, made_at=game.world.time,
                      tags=[] if pid else [f"venom:{cr.def_id}"])
            items.append(it)
            label = game.tables.items.get(it.def_id)["name"] if pid else poisons.label(game.tables, it)
            if not pid:
                it.name = label
            msgs += [words, f"<loot>{first} milks the {name}'s glands into a vial: {label}.</>"]
        elif HARVEST_DC - total >= 5:
            v = poisons.venom_of(game.tables, cr.def_id)
            msgs += [words, f"<danger>The {name}'s fang slips and pricks {first}'s hand.</>"]
            msgs += poisons.suffer(game, who, {"dc": v["dc"], "damage": v["damage"], "half": True, "hours": 1},
                                   f"{name} venom")
        else:
            msgs += [words, f"{first} cannot get anything clean out of the {name}."]
    camp.chore(game, max(1, minutes), "rest")
    return items, msgs
