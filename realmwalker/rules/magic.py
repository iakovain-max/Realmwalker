"""What magic items do, for the rules (the framework of Expansion 1, DMG 2024 chapter 7 and PHB "Magic Items").

An item's magic is `Item.magic`: {"rarity", "props": [{"kind", "value", ...}], "attune", "identified", "cursed",
"curse", "title", "story", "artifact", "sentient", "suppressed", ...}. Properties are effects read here:

- `bonus` (attack and damage), `ac`, `save`, `skill`, `ability`, `resist`, `light`, `warmth`, `speed`;
- `proficiency` {"skill"}: proficiency in a skill;
- `charges` {"spell", "value", "left", "regain", "keep_on", "at_will", "no_regain", "daily"}: a spell cast from the
  item (the Magic action, or the spell's own casting time), `left` of `value`, regaining `regain` dice at dawn (all of
  them if none; none ever with `no_regain`);
  `keep_on` n: after a cast, a d6 of n or more keeps the charge (an artifact's "1-5: not again until dawn");
- `trait` {"trait"}: a definition in data/traits.json for the rules kernel (immunities, vulnerabilities, hooks);
- `flag` {"flag"}: something another system checks (data/magic.json "artifact" properties say what);
- `helps` {"helps": {key: n}}: what it does for a task (as data/items.json "helps": a ram for forcing doors);
  `bearings` {"value"}: a needle that finds north (GameState.bearings_bonus).
Any property may say `daily`: used once (`today`), it is ready again at dawn (`dawn`; rules/engine/handlers/arms.py).

Wands, staffs and rods (Expansion 5 Part D) keep one store of charges for all their spells: a `pool` property {"value",
"left", "regain", "last", "lucky"} and spells drawn from it, `charges` properties with a `cost` (0: at will) and maybe
`level` (the version cast), `more` (charges that may be added, a level each: the Wand of Fireballs, the Staff of
Healing's Cure Wounds), `dc` and `attack` (the item's own numbers; else the user's). When the last charge goes, `last`
says what a d20 of 1 does (`drained`): "crumble", "vanish" or "display" (gone), "mundane" (a plain thing of its kind),
"weaken" (only its +N to hit and damage stays: the Staff of Power); `lucky` dice come back on a 20.

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


def item_flag(item, name: str) -> bool:
    """A flag on the item itself, working whoever holds it (a material: adamantine, mithral, silver)."""
    return item is not None and any(p.get("kind") == "flag" and p.get("flag") == name for p in props(item))


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


def pool(item) -> dict | None:
    """The store of charges a wand, staff or rod shares among its spells (a `pool` property), if it has one."""
    return next((p for p in props(item) if p.get("kind") == "pool"), None)


def pooled(prop: dict) -> bool:
    """A spell drawn from its item's store of charges (it says its `cost`)."""
    return prop.get("cost") is not None


def charge_cost(prop: dict, level: int | None = None) -> int:
    """Charges a spell from the store takes, cast at `level` (each level above its own takes one more)."""
    base = int(prop.get("cost", 1))
    if level is None or not prop.get("more"):
        return base
    return base + max(0, min(int(prop["more"]), int(level) - int(prop.get("level", 0))))


def charge_levels(item, prop: dict, own: int) -> list[int]:
    """The levels this item's spell can be cast at now: its own version, and one more for each charge added (no
    more than the store holds)."""
    first = int(prop.get("level", own))
    if not pooled(prop) or not prop.get("more"):
        return [first]
    store = pool(item)
    left = int(store.get("left", store.get("value", 0))) if store else 0
    return [first + n for n in range(int(prop["more"]) + 1) if int(prop.get("cost", 1)) + n <= left] or [first]


def spend_charge(prop: dict, rng, item=None, level: int | None = None) -> bool:
    """Use one charge (none for an at-will power); a `keep_on` power may keep it; a spell of a store takes its cost
    (more for a higher `level`). True if a charge was spent."""
    if prop.get("at_will"):
        return False
    if pooled(prop):
        cost = charge_cost(prop, level)
        store = pool(item) if item is not None else None
        if store is None or cost <= 0:
            return False
        store["left"] = max(0, int(store.get("left", store.get("value", 0))) - cost)
        return True
    keep = int(prop.get("keep_on", 0) or 0)
    if prop.get("daily"):
        prop["today"] = 1  # (a power used once between dawns, whatever charges are left: the Luck Blade's Wish)
    if keep and rng.randint(1, 6) >= keep:
        return False
    prop["left"] = max(0, int(prop.get("left", prop.get("value", 1))) - 1)
    return True


def charges_left(prop: dict, item=None) -> int:
    """How many times it can still be used: charges left, or casts the store still pays for (at will: 1)."""
    if prop.get("at_will"):
        return 1
    if prop.get("daily") and prop.get("today"):
        return 0  # (used since the last dawn)
    if pooled(prop):
        cost = int(prop.get("cost", 1))
        if cost <= 0:
            return 1
        store = pool(item) if item is not None else None
        return int(store.get("left", store.get("value", 0))) // cost if store else 0
    return int(prop.get("left", prop.get("value", 1)))


def drained(char, item, rng) -> list[str]:
    """After a charge is spent: if that was the last of the store, a d20 says what becomes of the thing (DMG 2024).
    Returns what to say (empty when nothing happened). The item is taken from `char` when it is gone."""
    store = pool(item)
    if store is None or int(store.get("left", 0)) > 0 or not (store.get("last") or store.get("lucky")):
        return []
    from realmwalker.core import dice

    roll = rng.randint(1, 20)
    name = item.magic.get("title") or "it"
    if roll == 20 and store.get("lucky"):
        back = max(1, dice.roll(str(store["lucky"]), rng).total)
        store["left"] = min(int(store.get("value", back)), back)
        return [f"The last charge goes out of the {name}, and the power floods back into it ({back} charges)."]
    if roll != 1 or not store.get("last"):
        return []
    last = store["last"]
    if last in ("crumble", "vanish", "display"):
        from realmwalker.rules.inventory import remove_item

        remove_item(char, item.uid, 1)
        char.attuned = [u for u in char.attuned if u != item.uid]
        return [f"The {name} " + {"crumble": "crumbles into ashes and is gone.",
                                  "vanish": "vanishes in a flash of light, lost for ever.",
                                  "display": "goes up in a last harmless blaze of coloured fire and is gone."}[last]]
    if last == "mundane":
        char.attuned = [u for u in char.attuned if u != item.uid]
        item.magic = {}
        return [f"The {name} gives up its last power: it is a plain thing now."]
    if last == "weaken":
        item.magic["props"] = [p for p in props(item) if p.get("kind") == "bonus"]
        item.magic["attune"] = False
        char.attuned = [u for u in char.attuned if u != item.uid]
        return [f"The {name} goes dull: its strength as a weapon stays, and every other power is gone."]
    return []


def dawn(items, rng) -> None:
    """Charges come back at dawn: `regain` dice of them, or all."""
    from realmwalker.core import dice

    for it in items:
        for p in props(it):
            if p.get("daily"):
                p.pop("today", None)  # (once a day: ready again)
            if p.get("kind") not in ("charges", "pool") or p.get("at_will") or p.get("no_regain") or pooled(p):
                continue
            most = int(p.get("value", 1))
            if p.get("regain"):
                p["left"] = min(most, int(p.get("left", most)) + max(0, dice.roll(str(p["regain"]), rng).total))
            else:
                p["left"] = most


def recharge(char) -> None:
    """Everything back to full (a long rest where no dawn is counted: tests and old callers)."""
    for it, p in [(it, p) for it in char.inventory for p in props(it)]:
        p.pop("today", None)
        if p.get("kind") in ("charges", "pool") and not p.get("no_regain") and not pooled(p):
            p["left"] = int(p.get("value", 1))


def cursed_and_worn(char, item) -> bool:
    return bool(getattr(item, "magic", None) and item.magic.get("cursed")
                and (char.slot_of(item.uid) is not None or is_attuned(char, item)))


def can_attune(char, item, sheet=None, others=()) -> str:
    """Why this character cannot attune to the item now, or ''. `others`: everyone else who might hold the bond (an
    item is bound to one creature at a time; the party carries one pack)."""
    if not needs_attunement(item):
        return "it needs no bond to work"
    if is_attuned(char, item):
        return "already bound to it"
    holder = next((o for o in others if o is not char and is_attuned(o, item)), None)
    if holder is not None:
        return f"it is bound to {holder.name.split()[0]}"
    for other in attuned_items(char):
        if other.magic.get("jealous"):
            return f"the {other.magic.get('title') or 'artifact'} will share you with nothing else"
    if len(attuned_items(char)) >= ATTUNE_MAX + (1 if "use_magic_device" in char.features else 0):
        return f"already bound to {ATTUNE_MAX} things: end one bond first"
    same = item.magic.get("title")
    if item.magic.get("source") == "book" and any(o.magic.get("book") == item.magic.get("book")
                                                   for o in attuned_items(char)):
        return f"already bound to another {same}"
    need = item.magic.get("attune_by")
    if need == "spellcaster" and sheet is not None and not sheet.is_caster():
        return "only one who casts spells of their own can bind to it"
    if isinstance(need, list) and char.cls not in need:
        names = [n + "s" for n in need]
        return "it will bind only to " + (", ".join(names[:-1]) + " or " if len(names) > 1 else "") + names[-1]
    return ""
