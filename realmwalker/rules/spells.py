"""Spellcasting: which spells a character can cast, spell slots, attack bonus and save DC.

Wizards cast from their spellbook (they copy new spells in from scrolls and books, M8). Clerics
may call on any cleric prayer of a level they have slots for. v1 has no separate preparation step.
"""

from __future__ import annotations

from realmwalker.rules.character import Character, Sheet


class SpellTable:
    def __init__(self, data: dict) -> None:
        self.defs: dict[str, dict] = {k: v for k, v in data["spells"].items() if not k.startswith("_")}
        self.starting: dict[str, dict] = data.get("starting", {})

    def __getitem__(self, spell_id: str) -> dict:
        return self.defs[spell_id]

    def __contains__(self, spell_id: str) -> bool:
        return spell_id in self.defs

    def for_class(self, cls: str, max_level: int) -> list[str]:
        return [sid for sid, s in self.defs.items() if cls in s["classes"] and s["level"] <= max_level]


def is_caster(char: Character, tables) -> bool:
    return "spellcasting" in tables.classes[char.cls]


def init_spells(char: Character, tables) -> None:
    """Give a new caster their starting cantrips (and, for a wizard, a spellbook)."""
    if not is_caster(char, tables):
        return
    start = tables.spells.starting.get(char.cls, {})
    char.spells = {
        "cantrips": list(start.get("cantrips", [])),
        "spellbook": list(start.get("spellbook", [])),
        "slots_used": [0] * 9,
    }


def slots_total(char: Character, tables) -> list[int]:
    """Spell slots per spell level (index 0 = level 1)."""
    sc = tables.classes[char.cls].get("spellcasting")
    if not sc:
        return []
    row = sc["slots"][max(0, min(len(sc["slots"]) - 1, char.level - 1))]
    return list(row)


def slots_left(char: Character, tables) -> list[int]:
    used = char.spells.get("slots_used", [0] * 9)
    return [max(0, n - (used[i] if i < len(used) else 0)) for i, n in enumerate(slots_total(char, tables))]


def max_spell_level(char: Character, tables) -> int:
    return len(slots_total(char, tables))


def known_spells(char: Character, tables) -> list[str]:
    """Every spell this character could cast (given a free slot)."""
    if not is_caster(char, tables):
        return []
    out = [s for s in char.spells.get("cantrips", []) if s in tables.spells]
    top = max_spell_level(char, tables)
    if char.cls == "wizard":
        out += [s for s in char.spells.get("spellbook", []) if s in tables.spells and tables.spells[s]["level"] <= top]
    else:
        out += [s for s in tables.spells.for_class(char.cls, top) if tables.spells[s]["level"] > 0]
    return list(dict.fromkeys(out))


def can_cast(char: Character, tables, spell_id: str) -> tuple[bool, str]:
    spell = tables.spells[spell_id]
    if spell["level"] == 0:
        return True, ""
    left = slots_left(char, tables)
    if any(left[i] > 0 for i in range(spell["level"] - 1, len(left))):
        return True, ""
    return False, "no spell slots of that level left (rest to recover)"


def lowest_free_slot(char: Character, tables, level: int) -> int | None:
    left = slots_left(char, tables)
    for i in range(level - 1, len(left)):
        if left[i] > 0:
            return i + 1
    return None


def spend_slot(char: Character, slot_level: int) -> None:
    used = char.spells.setdefault("slots_used", [0] * 9)
    used[slot_level - 1] += 1


def restore_slots(char: Character) -> None:
    if char.spells:
        char.spells["slots_used"] = [0] * 9


def casting_ability(char: Character, tables) -> str:
    sc = tables.classes[char.cls].get("spellcasting")
    return sc["ability"] if sc else "int"


def attack_bonus(sheet: Sheet, tables) -> int:
    return sheet.proficiency + sheet.mod(casting_ability(sheet.c, tables))


def save_dc(sheet: Sheet, tables) -> int:
    return 8 + sheet.proficiency + sheet.mod(casting_ability(sheet.c, tables))


def cantrip_multiplier(level: int) -> int:
    return 1 if level < 5 else (2 if level < 11 else 3)
