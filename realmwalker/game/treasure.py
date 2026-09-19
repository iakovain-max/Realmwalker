"""Treasure (M8): what is found in chests, coffins and hoards. Deeper and better-guarded means richer.
Magic items join the mix from part 3 (game/magic_items.py)."""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.rules.items import Item

BOOKS = [("old_map", 4), ("found_letter", 3), ("history_book", 2), ("lore_book", 2)]
VALUABLES = [("gold_ring", 3), ("silver_chalice", 3), ("jewelled_brooch", 2), ("gemstone", 2), ("silver_ingot", 3),
             ("diamond", 1)]
GRAVE_GOODS = [("gold_ring", 3), ("jewelled_brooch", 2), ("silver_chalice", 2), ("gemstone", 1)]


def new_item(game, def_id: str, rng: RNG, *, qty: int = 1, quality: str = "common", condition: int = 100) -> Item:
    return Item(uid=0, def_id=def_id, qty=qty, quality=quality, condition=condition, made_at=game.world.time)


def roll(game, tier: int, rng: RNG, *, grave: bool = False) -> tuple[list[Item], int]:
    """(items, copper) for a treasure of the given tier (1 = a poor chest, 5 = a dragon's leavings)."""
    tier = max(1, min(6, tier))
    items_table = game.tables.items
    money = dice.roll(f"{tier}d6", rng).total * (60 if not grave else 90) * tier
    items: list[Item] = []
    count = rng.randint(0, 1) + (tier >= 2) + (tier >= 4)
    for _ in range(count):
        kind = rng.weighted(["valuable", "potion", "scroll", "arms", "magic", "book"],
                            [4, 3, 2 if not grave else 0, 2, min(4, tier) if tier >= 2 else 0, 2])
        if grave:
            kind = rng.choice(["valuable", "valuable", "arms", "book"])
        if kind == "valuable":
            table = GRAVE_GOODS if grave else VALUABLES
            def_id = rng.weighted([t[0] for t in table], [t[1] for t in table])
            if def_id in items_table:
                items.append(new_item(game, def_id, rng))
        elif kind == "potion" and "potion_healing" in items_table:
            items.append(new_item(game, "potion_healing", rng, qty=rng.randint(1, 2)))
        elif kind == "scroll":
            top = min(5, 1 + tier // 2)
            scrolls = [d for d, s in items_table.defs.items() if s.get("use", {}).get("scroll")
                       and game.tables.spells[s["use"]["scroll"]]["level"] <= top]
            if scrolls:
                items.append(new_item(game, rng.choice(sorted(scrolls)), rng))
        elif kind == "arms":
            arms = sorted(d for d, s in items_table.defs.items() if s["category"] in ("weapon", "armor", "shield")
                          and s.get("value", 0) >= 500)
            if arms:
                quality = rng.weighted(["common", "fine", "masterwork"], [5, 3, 1 + tier // 2])
                condition = rng.randint(30, 70) if grave else rng.randint(60, 100)
                items.append(new_item(game, rng.choice(arms), rng, quality=quality, condition=condition))
        elif kind == "book":
            def_id = rng.weighted([b[0] for b in BOOKS], [b[1] for b in BOOKS])
            if def_id in items_table:
                items.append(new_item(game, def_id, rng, condition=rng.randint(20, 80)))
        elif kind == "magic":
            from realmwalker.game import magic_items

            it = magic_items.make(game, rng, tier=tier)
            if it is not None:
                items.append(it)
    return items, int(money)
