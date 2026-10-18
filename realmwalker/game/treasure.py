"""Treasure by the Dungeon Master's Guide (2024), chapters 4 and 7 (Expansion 1, D.2; numbers in data/treasure.json).

- What one creature carries: `individual(game, cr, rng)` (Random Individual Treasure, by Challenge Rating), for the
  creatures whose Monster Manual treasure says "Individual" (set when they are spawned, rules/creatures.py); a band
  whose kind keeps a hoard instead carries one purse, its leader's (`band_purse`).
- A hoard: `hoard(game, cr, rng, theme=)` (Random Treasure Hoard): money by CR, turned into what the theme likes
  (Arcana gems, Armaments coins and trade bars, Implements coins, bars and trade goods, Relics art objects), and
  magic items by the Magic Item Rarities table (read by the hoard's CR, since enemies scale with the land and not
  the party) and the theme's random tables. An item the game does not have yet is rolled again; after a few tries
  a Realmwalker item of that rarity and theme is made instead, so treasure grows richer as expansions land. The
  world's Magic setting scales how many magic items there are.
- Where it lies: a dungeon's ordinary chests hold a stash (individual treasure of the place's strength, a few times
  over, and the small finds of old: books, potions, scrolls, arms); the deepest level's last chest holds the hoard
  of whoever rules the place; a barrow's coffins hold grave goods (art objects). Quest rewards by the DMG roll the
  hoard table with the party's level as the CR (`quest_reward`).
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.rules.creatures import individual_treasure, keeps
from realmwalker.rules.items import Item

BOOKS = [("old_map", 4), ("found_letter", 3), ("history_book", 2), ("lore_book", 2)]
THEMES = ("arcana", "armaments", "implements", "relics")
RARITIES = ("common", "uncommon", "rare", "very_rare", "legendary")
MAX_PIECES = 12  # gems or art objects in one find; the rest of the value is in coin


def spec(game) -> dict:
    return game.tables.treasure


def new_item(game, def_id: str, rng: RNG, *, qty: int = 1, quality: str = "common", condition: int = 100) -> Item:
    return Item(uid=0, def_id=def_id, qty=qty, quality=quality, condition=condition, made_at=game.world.time)


def _band(rows: list, cr: float) -> list:
    cr = max(0.0, float(cr))
    for row in rows:
        if row[0] <= cr <= row[1] or cr < row[0]:
            return row
    return rows[-1]


def _gp(game, coin: str) -> int:
    return int(spec(game)["coins"][coin])


# ---------------------------------------------------------------------------- money
def individual(game, cr: float, rng: RNG) -> int:
    """Random Individual Treasure: copper for one creature of this Challenge Rating."""
    return individual_treasure(game.tables, cr, rng)


def theme_of(game, def_ids: list[str], rng: RNG) -> str:
    """The treasure theme of a band or a lair: its strongest member's, a d4 for "Any" (DMG: no theme, roll 1d4)."""
    best = max(def_ids, key=lambda d: float(game.tables.creatures[d].get("cr", 0)), default=None)
    themes = [t for t in keeps(game.tables.creatures[best]) if t in THEMES] if best else []
    if not themes:
        for d in def_ids:
            themes = [t for t in keeps(game.tables.creatures[d]) if t in THEMES]
            if themes:
                break
    return rng.choice(themes) if themes else rng.choice(list(THEMES))


def monetary(game, gp: int, theme: str | None, rng: RNG) -> tuple[list[Item], int]:
    """A treasure's worth (in GP) in the form its theme likes: coins, trade bars, trade goods, gems, art objects."""
    s = spec(game)
    forms = s["themes"].get(theme, {}).get("money", ["coins"]) if theme else ["coins", "gems", "art", "bars"]
    form = rng.choice(forms)
    items: list[Item] = []
    copper = 0
    if form in ("gems", "art"):
        table = s[form]
        values = sorted(int(v) for v in table)
        target = max(values[0], gp // 4)
        value = max([v for v in values if v <= target] or [values[0]])
        count = min(MAX_PIECES, max(1, gp // value)) if gp >= value else 0
        entry = table[str(value)]
        for _ in range(count):
            it = new_item(game, entry["item"], rng)
            it.name = rng.choice(entry["names"])
            items.append(it)
        copper = max(0, gp - count * value) * 100
    elif form == "bars":
        fit = [b for b in s["bars"] if b[1] * 2 <= gp and b[0] in game.tables.items]
        if fit:
            def_id, value = max(fit, key=lambda b: b[1])
            n = min(20, int(gp // value))
            items.append(new_item(game, def_id, rng, qty=n))
            copper = int(gp - n * value) * 100
        else:
            copper = gp * 100
    elif form == "goods":
        def_id, value = rng.choice(s["goods"])
        n = min(10, int(gp * 0.5 // max(0.5, float(value))))
        if n and def_id in game.tables.items:
            items.append(new_item(game, def_id, rng, qty=n))
            copper = int(gp - n * float(value)) * 100
        else:
            copper = gp * 100
    else:
        copper = gp * 100
    return items, copper


# ---------------------------------------------------------------------------- magic items
def rarity_for(game, cr: float, rng: RNG) -> str:
    """Magic Item Rarities (DMG 2024), read by the hoard's Challenge Rating as the characters' level."""
    _lo, _hi, tops = _band(spec(game)["rarity"], cr)
    roll = rng.randint(1, 100)
    for rarity, top in zip(RARITIES, tops):
        if roll <= top:
            return rarity
    return "legendary"


def magic_item(game, rng: RNG, rarity: str, theme: str | None = None) -> Item | None:
    """One magic item by the DMG's random tables: theme (a d4 when there is none) and rarity; an item the game has
    not got yet is rolled again, and after a few tries a Realmwalker item of the same rarity and theme is made."""
    s = spec(game)
    theme = theme if theme in THEMES else rng.choice(list(THEMES))
    table = s["tables"].get(f"{theme}/{rarity}", [])
    for _ in range(int(s["reroll"])):
        if not table:
            break
        roll = rng.randint(1, 100)
        row = next((r for r in table if r[0] <= roll <= r[1]), None)
        if row is None:
            continue
        it = make_listed(game, row[2], row[3], rarity, rng)
        if it is not None:
            return it
    from realmwalker.game import magic_items

    kind = rng.choice(s["themes"][theme]["kinds"])
    return magic_items.make(game, rng.child("own"), kind=kind, rarity=rarity if rarity != "common" else "common")


def make_listed(game, slug: str, variant: str, rarity: str, rng: RNG) -> Item | None:
    """A named item of the DMG's tables, if the game has it (data/treasure.json makers), else None."""
    variants = spec(game)["makers"].get(slug)
    if not variants:
        return None
    how = variants.get(variant) or variants.get("*")
    if how is None:
        return None
    if how.get("item"):
        if how["item"] not in game.tables.items:
            return None
        it = new_item(game, how["item"], rng)
        if how.get("secretly"):  # (a Potion of Poison passing for a potion of healing: rules/poisons.mask)
            from realmwalker.rules import poisons

            poisons.mask(it, how["secretly"])
        return it
    if how.get("scroll"):
        levels = _levels(variant)
        scrolls = sorted(d for d, sd in game.tables.items.defs.items() if sd.get("use", {}).get("scroll")
                         and game.tables.spells[sd["use"]["scroll"]]["level"] in levels)
        return new_item(game, rng.choice(scrolls), rng) if scrolls else None
    if how.get("kind"):
        from realmwalker.game import magic_items

        lo, hi = how.get("qty") or (1, 1)
        it = magic_items.make(game, rng.child(slug), kind=how["kind"], rarity=rarity, props=how.get("props"),
                              sentient=False, bases=how.get("bases"), qty=rng.randint(int(lo), int(hi)))
        if it is not None:
            it.magic["book"] = f"{slug}{variant}"
            if how.get("title"):
                it.magic["title"] = how["title"]  # (a named item of the book: the Dagger of Venom)
            it.magic["source"] = "book"
            it.magic["attune"] = bool(how.get("attune", False))  # a book item binds only if its entry says so
            if how.get("attune_by"):
                it.magic["attune_by"] = how["attune_by"]  # ("spellcaster", or [classes]: the Staff of Healing)
            if how.get("enspell") and not _enspell(game, it, variant, rng):
                return None  # (no spell of those levels the game can bind: rolled again)
            if how.get("title"):  # (its look from the book's name, not the made-up one: a Staff of Frost is icy)
                it.magic["look"] = magic_items.look_for(game, it.magic, rng.child("look"))
            if how.get("form"):
                it.magic["form"] = how["form"]  # (the Veteran's Cane: a walking cane until it is twisted)
            if how.get("curse"):
                it.magic["cursed"] = True  # (the Sword of Vengeance: the book's own curse)
                it.magic["curse"] = dict(how["curse"])
            for p in it.magic.get("props", ()):
                if p.get("dice"):  # (the Luck Blade's 1d3 charges of Wish)
                    p["value"] = p["left"] = max(1, dice.roll(str(p.pop("dice")), rng).total)
        return it
    return None


def _enspell(game, it, variant: str, rng: RNG) -> bool:
    """The Enspelled Staff (DMG 2024): a spell of the variant's levels bound into it, cast for a charge with the
    staff's own save DC and attack bonus by the spell's level (data/treasure.json "enspell"). False if none fits."""
    from realmwalker.rules import spells as spellrules

    levels = _levels(variant)
    pool = sorted(sid for sid, sp in game.tables.spells.defs.items()
                  if int(sp.get("level", 0)) in levels and sp.get("school") not in (None, "none")
                  and not set(sp.get("classes", ())) & {"item", "creature", "again"} and not sp.get("again_of")
                  and not sp.get("stress") and not spellrules.has_op(sp, "identify")
                  and (not spellrules.out_of_battle(sp) or spellrules.on_the_road(game.tables, sid)[0]))
    if not pool:
        return False
    sid = rng.choice(pool)
    sp = game.tables.spells[sid]
    dc, attack = spec(game).get("enspell", {}).get(str(sp["level"]), [13, 5])
    words = f"{sp['name']} is bound into it: a charge casts it (save DC {dc}, attack +{attack})."
    it.magic["props"].append({"kind": "charges", "spell": sid, "cost": 1, "dc": int(dc), "attack": int(attack),
                              "text": words})
    it.magic["title"] = f"Enspelled Staff of {sp['name']}"
    return True


def _levels(variant: str) -> set[int]:
    """'cantrip or level 1 spell' -> {0, 1}; 'level 6, 7, or 8 spell' -> {6, 7, 8}."""
    import re

    out = {int(n) for n in re.findall(r"\d", variant)}
    if "cantrip" in variant:
        out.add(0)
    return out or {1}


def magic_count(game, expr: str, rng: RNG) -> int:
    """How many magic items: the hoard's dice, scaled by the world's Magic setting (each extra fraction a chance)."""
    n = max(0, dice.roll(str(expr), rng).total)
    scale = float(spec(game)["magic_scale"][max(1, min(3, int(getattr(game.world.meta, "magic", 2)))) - 1])
    whole = int(n * scale)
    if rng.random() < n * scale - whole:
        whole += 1
    return whole


# ---------------------------------------------------------------------------- hoards and stashes
def hoard(game, cr: float, rng: RNG, *, theme: str | None = None, double: bool = False) -> tuple[list[Item], int]:
    """Random Treasure Hoard (DMG 2024): money by CR in the theme's form, and magic items."""
    _lo, _hi, expr, times, magic = _band(spec(game)["hoard"], cr)
    gp = dice.roll(expr, rng).total * int(times) * (2 if double else 1)
    items, copper = monetary(game, gp, theme, rng)
    for _ in range(magic_count(game, magic, rng) * (2 if double else 1)):
        it = magic_item(game, rng, rarity_for(game, cr, rng), theme)
        if it is not None:
            items.append(it)
    return items, copper


def stash(game, cr: float, tier: int, rng: RNG, *, grave: bool = False, theme: str | None = None
          ) -> tuple[list[Item], int]:
    """An ordinary chest or coffin: individual treasure of the place's strength a few times over (grave goods as art
    objects), and the small finds of old, now and then a magic item of the place's rarity."""
    tier = max(1, min(6, tier))
    worth = sum(individual(game, cr, rng) for _ in range(tier)) // 100  # in GP
    items, copper = monetary(game, worth, "relics" if grave else theme, rng)
    items_table = game.tables.items
    count = rng.randint(0, 1) + (tier >= 3)
    for _ in range(count):
        kind = rng.weighted(["potion", "scroll", "arms", "magic", "book"],
                            [3, 2 if not grave else 0, 2, 1 if tier >= 2 else 0, 2])
        if grave:
            kind = rng.choice(["arms", "book"])
        if kind == "potion" and "potion_healing" in items_table:
            items.append(new_item(game, "potion_healing", rng, qty=rng.randint(1, 2)))
        elif kind == "scroll":
            top = min(5, 1 + tier // 2)
            scrolls = [d for d, s in items_table.defs.items() if s.get("use", {}).get("scroll")
                       and game.tables.spells[s["use"]["scroll"]]["level"] <= top]
            if scrolls:
                items.append(new_item(game, rng.choice(sorted(scrolls)), rng))
        elif kind == "arms":
            arms = sorted(d for d, s in items_table.defs.items() if s["category"] in ("weapon", "armor", "shield") and not s.get("rare")
                          and s.get("value", 0) >= 500)
            if arms:
                quality = rng.weighted(["common", "fine", "masterwork"], [5, 3, 1 + tier // 2])
                condition = rng.randint(30, 70) if grave else rng.randint(60, 100)
                items.append(new_item(game, rng.choice(arms), rng, quality=quality, condition=condition))
        elif kind == "book":
            def_id = rng.weighted([b[0] for b in BOOKS], [b[1] for b in BOOKS])
            if def_id in items_table:
                items.append(new_item(game, def_id, rng, condition=rng.randint(20, 80)))
        elif kind == "magic" and magic_count(game, "1", rng):
            it = magic_item(game, rng, rarity_for(game, cr, rng), theme)
            if it is not None:
                items.append(it)
    keepsake = rng.child("trinket")  # (its own stream: the rest of the chest is as it was)
    if "trinket" in items_table and keepsake.chance(float(game.tables.trinket_chance["chest"])):
        from realmwalker.rules.items import make_trinket

        items.append(make_trinket(game.tables, keepsake, now=game.world.time))
    return items, copper


def roll(game, tier: int, rng: RNG, *, grave: bool = False, cr: float | None = None,
         theme: str | None = None) -> tuple[list[Item], int]:
    """(items, copper) for a chest of the given tier (1 = a poor chest, 6 = the best a deep place holds)."""
    if cr is None:
        cr = max(0.0, tier - 1.5)
    return stash(game, cr, tier, rng, grave=grave, theme=theme)
