"""What magic items do (M8), for the rules: bonuses to attacks, armour, saves, skills and abilities, warmth,
resistances, light, spell charges, and the flaws of cursed things. An item's magic is `Item.magic`:
{"rarity", "props": [{"kind", "value", ...}], "cursed", "curse", "identified", "title", "story"}. Properties
work whether or not the item has been identified; only their names are hidden until then."""

from __future__ import annotations


def props(item) -> list[dict]:
    magic = getattr(item, "magic", None)
    return list(magic.get("props", [])) if magic else []


def is_magic(item) -> bool:
    return bool(getattr(item, "magic", None))


def equipped(char) -> list:
    out = []
    for uid in set(char.equipped.values()):
        it = char.item(uid)
        if it is not None and is_magic(it):
            out.append(it)
    return out


def total(char, kind: str, **match) -> int:
    """Sum of a property over everything the character wears or wields (curses included)."""
    value = 0
    for it in equipped(char):
        for p in props(it):
            if p.get("kind") == kind and all(p.get(k) == v for k, v in match.items()):
                value += int(p.get("value", 0))
        curse = it.magic.get("curse") if it.magic.get("cursed") else None
        if curse and curse.get("effect") == kind and all(curse.get(k) == v for k, v in match.items()):
            value += int(curse.get("value", 0))
    return value


def item_bonus(item, kind: str = "bonus") -> int:
    return sum(int(p.get("value", 0)) for p in props(item) if p.get("kind") == kind)


def resistances(char) -> list[str]:
    return [p["type"] for it in equipped(char) for p in props(it) if p.get("kind") == "resist" and p.get("type")]


def light(char) -> int:
    return max((int(p.get("value", 0)) for it in equipped(char) for p in props(it) if p.get("kind") == "light"),
               default=0)


def charges(char) -> list[tuple[object, dict]]:
    """(item, property) for every spell an item can cast (equipped or carried)."""
    return [(it, p) for it in char.inventory for p in props(it) if p.get("kind") == "charges" and p.get("spell")]


def recharge(char) -> None:
    for it, p in charges(char):
        p["left"] = int(p.get("value", 1))


def cursed_and_worn(char, item) -> bool:
    return bool(getattr(item, "magic", None) and item.magic.get("cursed") and char.slot_of(item.uid) is not None)
