"""War Bond (PHB 2024 Eldritch Knight, level 3; Expansion 4 Part B): up to two weapons bound to a knight.

The bonds are `char.spells["war_bond"]` {str(uid): {"name"}} (kept with the character; no save format change). The
hour's ritual is done at a rest (`at_rest`, from `progression.short_rest` and `long_rest`): the weapon in the main hand
first, then a second weapon carried (one of another reach: a bow beside a sword), as the knight would choose; a third
bond would break one of these, so the game never makes one. A bonded weapon:
- is never knocked from the hand (`holds`: Disarming Attack, any disarm);
- comes back to the hand with a bonus action in a fight (`away`, `call`: thrown and lying on the field, or the other
  bonded weapon from the pack), and after robbers carried it off, as soon as the knight is on their feet (`taken`).
"""

from __future__ import annotations

from realmwalker.core.textgen import escape_markup as esc
from realmwalker.rules.character import Character

KEY = "war_bond"
MAX_BONDS = 2


def bonds(char: Character | None) -> dict:
    if char is None or not isinstance(char.spells, dict):
        return {}
    have = char.spells.get(KEY)
    return have if have is not None else {}


def is_bonded(char: Character | None, item) -> bool:
    return item is not None and str(item.uid) in bonds(char)


def holds(char: Character | None) -> bool:
    """The weapon in the main hand cannot be knocked away (War Bond)."""
    return char is not None and is_bonded(char, char.equipped_item("main_hand"))


def _weapon(tables, it) -> dict | None:
    d = tables.items.get(it.def_id)
    return d if d.get("category") == "weapon" else None


def at_rest(char: Character, tables) -> list[str]:
    """The hour's ritual over a weapon at hand, done during a rest (the main weapon first, then one of another reach)."""
    if "war_bond" not in char.features:
        return []
    have = bonds(char)
    for uid in [u for u in have if char.item(int(u)) is None and not have[u].get("item")]:
        del have[uid]  # (sold or given away: the bond goes with it)
    if len(have) >= MAX_BONDS:
        return []
    main = char.equipped_item("main_hand")
    picks = []
    if main is not None and _weapon(tables, main) and str(main.uid) not in have:
        picks.append(main)
    if len(have) + len(picks) < MAX_BONDS:
        ranged_main = main is not None and "ranged" in (_weapon(tables, main) or {}).get("properties", ())
        other = [it for it in char.inventory if _weapon(tables, it) and str(it.uid) not in have and it not in picks
                 and not any(t.startswith("conjured") for t in it.tags)]  # (Creation's things vanish)
        other = [it for it in other if ("ranged" in (_weapon(tables, it) or {}).get("properties", ())) != ranged_main
                 or "thrown" in (_weapon(tables, it) or {}).get("properties", ())]
        if other:
            picks.append(max(other, key=lambda it: (tables.items.value(it), -it.uid)))
    out = []
    for it in picks[:MAX_BONDS - len(have)]:
        have[str(it.uid)] = {"name": tables.items.name(it, False)}
        out.append(f"{esc(char.name.split()[0])} binds the {esc(tables.items.name(it, False))} with an hour's ritual "
                   f"(War Bond).")
    if out:
        char.spells[KEY] = have
    return out


def away(b, f) -> list:
    """The bonded weapons that could be called to the hand now: thrown and lying on the field, then those in the pack
    (not in the hand already)."""
    if f.char is None or "war_bond" not in f.char.features:
        return []
    mine = bonds(f.char)
    out = [it for it in getattr(b, "thrown", ()) if str(it.uid) in mine]
    main = f.char.equipped.get("main_hand")
    out += [it for it in f.char.inventory if str(it.uid) in mine and it.uid != main]
    return out


def call(b, f, it) -> bool:
    """A bonded weapon flies to the knight's hand (the one held goes into the pack)."""
    from realmwalker.rules.inventory import add_existing, equip, unequip

    c = f.char
    if it in getattr(b, "thrown", ()):
        b.thrown.remove(it)
        old = str(it.uid)
        it = add_existing(c, b.t.items, it)
        if str(it.uid) != old:  # (a new uid in the pack: the bond follows it)
            rec = bonds(c).pop(old, {"name": b.t.items.name(it, False)})
            bonds(c)[str(it.uid)] = rec
    if c.equipped.get("off_hand") is not None and "two_handed" in b.t.items.get(it.def_id).get("properties", ()):
        unequip(c, "off_hand")
    unequip(c, "main_hand")
    ok, _ = equip(c, b.t.items, it.uid, "main_hand")
    if not ok:
        ok, _ = equip(c, b.t.items, it.uid)
    return ok


def home(b) -> None:
    """The fight is over: a bonded weapon thrown and lying on the field goes back to its knight (the bond kept)."""
    from realmwalker.rules.inventory import add_existing

    for it in list(getattr(b, "thrown", ())):
        knight = next((f.char for f in b.fighters if f.char is not None and f.char.alive
                       and str(it.uid) in bonds(f.char)), None)
        if knight is None:
            continue
        b.thrown.remove(it)
        rec = bonds(knight).pop(str(it.uid))
        it = add_existing(knight, b.t.items, it)
        bonds(knight)[str(it.uid)] = rec


def taken(game, items, by: str) -> list[str]:
    """Robbers carried off a bonded weapon: it answers its knight's call as soon as they can call it."""
    from realmwalker.core.textgen import escape_markup as esc
    from realmwalker.rules.inventory import add_existing

    if by != "robbers":
        return []  # (the watch's strongbox gives it back with the rest at the release)
    out = []
    for it in items:
        knight = next((c for c in game.party if c.alive and str(it.uid) in bonds(c)), None)
        if knight is None:
            continue
        rec = bonds(knight).pop(str(it.uid))
        it = add_existing(knight, game.tables.items, it)
        bonds(knight)[str(it.uid)] = rec
        out.append(f"<good>The {esc(rec['name'])} tears free of the robbers' sack and flies back to "
                   f"{esc(knight.name.split()[0])}'s hand</> (War Bond).")
    return out
