"""What magic items do, for the rules (the framework of Expansion 1, DMG 2024 chapter 7 and PHB "Magic Items").

An item's magic is `Item.magic`: {"rarity", "props": [{"kind", "value", ...}], "attune", "identified", "cursed",
"curse", "title", "story", "artifact", "sentient", "suppressed", ...}. Properties are effects read here:

- `bonus` (attack and damage), `ac`, `save`, `skill`, `ability`, `resist`, `light`, `warmth`, `speed`;
- `proficiency` {"skill"}: proficiency in a skill;
- `charges` {"spell", "value", "left", "regain", "keep_on", "at_will"}: a spell cast from the item (the Magic action,
  or the spell's own casting time), `left` of `value`, regaining `regain` dice at dawn (all of them if none);
  `keep_on` n: after a cast, a d6 of n or more keeps the charge (an artifact's "1-5: not again until dawn");
- `trait` {"trait"}: a definition in data/traits.json for the rules kernel (immunities, vulnerabilities, hooks);
- `flag` {"flag"}: something another system checks (data/magic.json "artifact" properties say what).

Attunement (PHB 2024): an item with `attune` works only for the one attuned to it, three items at most, one copy of a
kind; attuning and ending it take a short rest focused on the item (game/magic_items.py); a cursed item's attunement
cannot be ended. A property of an item that needs attunement works while attuned, if the item is worn or wielded or
cannot be (artifact properties work while attuned, wherever the thing is); other items work while worn or wielded.
A sentient item at odds with its bearer may withhold its powers (`suppressed`). Properties work whether or not the
item has been identified; only their names are hidden until then."""

from __future__ import annotations

ATTUNE_MAX = 3


def props(item) -> list[dict]:
    magic = getattr(item, "magic", None)
    return list(magic.get("props", [])) if magic else []


def is_magic(item) -> bool:
    return bool(getattr(item, "magic", None))


def needs_attunement(item) -> bool:
    return bool(is_magic(item) and item.magic.get("attune"))


def is_attuned(char, item) -> bool:
    return item is not None and item.uid in getattr(char, "attuned", ())


def attuned_items(char) -> list:
    out = []
    for uid in getattr(char, "attuned", ()):
        it = char.item(uid)
        if it is not None:
            out.append(it)
    return out


def working(char, item) -> bool:
    """Whether the item's powers answer this character at all (attuned if it must be, not withheld)."""
    if not is_magic(item) or item.magic.get("suppressed"):
        return False
    return not needs_attunement(item) or is_attuned(char, item)


def equipped(char) -> list:
    out = []
    for uid in set(char.equipped.values()):
        it = char.item(uid)
        if it is not None and is_magic(it):
            out.append(it)
    return out


def _slots(item) -> bool:
    return item.magic.get("kind") in ("weapon", "armor", "shield", "jewellery", "clothing", "focus")


def active(char) -> list[tuple[object, dict]]:
    """(item, property) for every property working for this character now."""
    out = []
    worn = {it.uid for it in equipped(char)}
    seen = set(worn)
    for it in equipped(char):
        if not working(char, it):
            continue
        for p in props(it):
            out.append((it, p))
    for it in attuned_items(char):
        if it.uid in seen or not working(char, it):
            continue
        seen.add(it.uid)
        for p in props(it):
            if p.get("artifact") or p.get("kind") in ("charges", "trait", "flag") or not _slots(it):
                out.append((it, p))
    return out


def total(char, kind: str, **match) -> int:
    """Sum of a property over everything working for the character (curses of worn things included)."""
    value = 0
    for _it, p in active(char):
        if p.get("kind") == kind and all(p.get(k) == v for k, v in match.items()):
            value += int(p.get("value", 0))
    for it in equipped(char):
        curse = it.magic.get("curse") if it.magic.get("cursed") else None
        if curse and curse.get("effect") == kind and all(curse.get(k) == v for k, v in match.items()):
            value += int(curse.get("value", 0))
    return value


def item_bonus(item, kind: str = "bonus", char=None) -> int:
    if char is not None and not working(char, item):
        return 0
    return sum(int(p.get("value", 0)) for p in props(item) if p.get("kind") == kind)


def resistances(char) -> list[str]:
    return [p["type"] for _it, p in active(char) if p.get("kind") == "resist" and p.get("type")]


def light(char) -> int:
    return max((int(p.get("value", 0)) for _it, p in active(char) if p.get("kind") == "light"), default=0)


def proficient(char, skill: str) -> bool:
    return any(p.get("kind") == "proficiency" and p.get("skill") == skill for _it, p in active(char))


def traits(char) -> frozenset[str]:
    """Kernel trait ids the character's items give (data/traits.json)."""
    return frozenset(p["trait"] for _it, p in active(char) if p.get("kind") == "trait" and p.get("trait"))


def flag(char, name: str) -> bool:
    return any(p.get("kind") == "flag" and p.get("flag") == name for _it, p in active(char))


def flag_value(char, name: str):
    return next((p.get("value") for _it, p in active(char) if p.get("kind") == "flag" and p.get("flag") == name), None)


def fingerprint(char) -> tuple:
    """What the kernel's trait cache must notice: which magic is working for the character."""
    return tuple(sorted((it.uid, bool(it.magic.get("suppressed"))) for it, _p in active(char)))


def charges(char) -> list[tuple[object, dict]]:
    """(item, property) for every spell an item can cast for this character (worn or carried)."""
    return [(it, p) for it in char.inventory for p in props(it)
            if p.get("kind") == "charges" and p.get("spell") and working(char, it)]


def spend_charge(prop: dict, rng) -> bool:
    """Use one charge (none for an at-will power); a `keep_on` power may keep it. True if a charge was spent."""
    if prop.get("at_will"):
        return False
    keep = int(prop.get("keep_on", 0) or 0)
    if keep and rng.randint(1, 6) >= keep:
        return False
    prop["left"] = max(0, int(prop.get("left", prop.get("value", 1))) - 1)
    return True


def charges_left(prop: dict) -> int:
    if prop.get("at_will"):
        return 1
    return int(prop.get("left", prop.get("value", 1)))


def dawn(items, rng) -> None:
    """Charges come back at dawn: `regain` dice of them, or all."""
    from realmwalker.core import dice

    for it in items:
        for p in props(it):
            if p.get("kind") != "charges" or p.get("at_will"):
                continue
            most = int(p.get("value", 1))
            if p.get("regain"):
                p["left"] = min(most, int(p.get("left", most)) + max(0, dice.roll(str(p["regain"]), rng).total))
            else:
                p["left"] = most


def recharge(char) -> None:
    """Everything back to full (a long rest where no dawn is counted: tests and old callers)."""
    for it, p in [(it, p) for it in char.inventory for p in props(it) if p.get("kind") == "charges"]:
        p["left"] = int(p.get("value", 1))


def cursed_and_worn(char, item) -> bool:
    return bool(getattr(item, "magic", None) and item.magic.get("cursed")
                and (char.slot_of(item.uid) is not None or is_attuned(char, item)))


def can_attune(char, item, sheet=None) -> str:
    """Why this character cannot attune to the item now, or ''."""
    if not needs_attunement(item):
        return "it needs no bond to work"
    if is_attuned(char, item):
        return "already bound to it"
    for other in attuned_items(char):
        if other.magic.get("jealous"):
            return f"the {other.magic.get('title') or 'artifact'} will share you with nothing else"
    if len(attuned_items(char)) >= ATTUNE_MAX:
        return f"already bound to {ATTUNE_MAX} things: end one bond first"
    same = item.magic.get("title")
    if item.magic.get("source") == "book" and any(o.magic.get("book") == item.magic.get("book")
                                                   for o in attuned_items(char)):
        return f"already bound to another {same}"
    need = item.magic.get("attune_by")
    if need == "spellcaster" and sheet is not None and not sheet.is_caster():
        return "only one who casts spells of their own can bind to it"
    if isinstance(need, list) and char.cls not in need:
        return "it will bind only to " + ", ".join(need[:-1]) + (" or " if len(need) > 1 else "") + need[-1] + "s"
    return ""
