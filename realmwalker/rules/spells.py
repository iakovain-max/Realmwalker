"""Spellcasting: which spells a character can cast, spell slots, attack bonus and save DC.

Wizards cast from their spellbook (they copy new spells in from scrolls and books, M8). Clerics
may call on any cleric prayer of a level they have slots for. v1 has no separate preparation step.

A spell that lasts ten minutes or more (Mage Armour, Shield of Faith, Stoneskin, Death Ward) outlives the fight it
was cast in, and can be cast on the road before one: it is kept on the character as a timed effect,
`Character.effects["spell:<id>"]` = hours left, which wears off as time passes like any other (rules/health.py).
The sheet counts its armour; a battle carries the rest of it (resistances, the ward) while it lasts.

What a spell does is a list of effect operations, `spell["effects"]` (rules/engine/effects.py runs them in a fight).
The helpers below read them for everything else: what it heals, the buff it gives, its damage type, a short summary.
"""

from __future__ import annotations

from realmwalker.rules.character import Character, Sheet


LASTING = "spell:"  # the key prefix in Character.effects
MIN_LASTING_ROUNDS = 100  # ten minutes (a round is six seconds): long enough to be worth casting before a fight
ROUNDS_PER_HOUR = 600
SHEET_KEYS = ("ac", "mage_armor")  # the parts of a lasting spell the character sheet already counts


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
        if "spell_breaker" in char.features:  # (an abjurer's Spell Breaker: always ready, in the book or not)
            out += [s for s in SPELL_BREAKER if s in tables.spells and tables.spells[s]["level"] <= top]
    else:
        out += [s for s in tables.spells.for_class(char.cls, top) if tables.spells[s]["level"] > 0]
    return list(dict.fromkeys(out))


SPELL_BREAKER = ("counterspell", "dispel_magic")  # (Dispel Magic comes with the catalogue, Part D)


def free_cast(char: Character, tables, spell_id: str, slot_level: int | None = None) -> str | None:
    """How a spell can be cast at its own level without a slot, or None: a wizard's Spell Mastery ("mastery", at
    will) or Signature Spells ("signature", once until a short or long rest)."""
    sp = tables.spells.defs.get(spell_id)
    if sp is None or sp["level"] == 0 or not char.spells or (slot_level and slot_level != sp["level"]):
        return None
    if spell_id in char.spells.get("mastery", ()) and "spell_mastery" in char.features:
        return "mastery"
    if spell_id in char.spells.get("signature", ()) and "signature_spells" in char.features             and char.uses.get(f"signature:{spell_id}", 0) > 0:
        return "signature"
    return None


def spend_free(char: Character, spell_id: str, how: str | None) -> None:
    if how == "signature":
        char.uses[f"signature:{spell_id}"] = 0


def armour_problem(char: Character, tables) -> str:
    """Armour worn without training stops all spellcasting (2024)."""
    armor = char.equipped_item("armor")
    if armor is not None and not Sheet(char, tables).proficient_with_armor(armor):
        return "no spells in armour you are not trained to wear"
    return ""


def can_cast(char: Character, tables, spell_id: str) -> tuple[bool, str]:
    spell = tables.spells[spell_id]
    if "item" not in spell.get("classes", ()) and armour_problem(char, tables):
        return False, armour_problem(char, tables)
    if spell["level"] == 0 or free_cast(char, tables, spell_id):
        return True, ""
    left = slots_left(char, tables)
    if any(left[i] > 0 for i in range(spell["level"] - 1, len(left))):
        return True, ""
    return False, "no spell slots of that level left (rest to recover)"


# ---------------------------------------------------------------------------- reading a spell's effects
NESTED = ("on_hit", "on_fail", "do")


def ops(spell: dict) -> list[dict]:
    """Every effect operation of a spell, the ones inside others too (an attack's on_hit, a save's on_fail)."""
    out: list[dict] = []
    todo = list(spell.get("effects", ()))
    while todo:
        o = todo.pop(0)
        out.append(o)
        for key in NESTED:
            todo.extend(o.get(key, ()))
        then = o.get("then")
        if then:
            todo.extend(then.get("on_fail", ()))
    return out


def op(spell: dict, name: str) -> dict | None:
    return next((o for o in ops(spell) if o["op"] == name), None)


def has_op(spell: dict, *names: str) -> bool:
    return any(o["op"] in names for o in ops(spell))


def damage_parts(o: dict) -> list[tuple[str, str, str]]:
    """(dice, type, more dice per slot level above the spell's) for each kind of damage an op deals."""
    d = o.get("damage")
    if not d:
        return []
    if isinstance(d, str):
        return [(d, o.get("type", ""), o.get("up", ""))]
    return [(p["dice"], p["type"], p.get("up", "")) for p in d]


def main_type(spell: dict) -> str:
    """The spell's damage type, for its colour and sound ("" if it does no damage)."""
    for o in ops(spell):
        parts = damage_parts(o)
        if parts:
            return parts[0][1]
    return ""


def buff_of(spell: dict) -> dict:
    """What a spell's modifier puts on its target ({"ac": 2}, {"resist": [...]}...), {} if it has none."""
    m = op(spell, "modifier")
    return dict(m["buff"]) if m else {}


def harms(spell: dict) -> bool:
    """Whether the spell is aimed at enemies (an attack or a saving throw)."""
    return has_op(spell, "attack", "save", "darts")


def heal_op(spell: dict) -> dict | None:
    return op(spell, "heal")


def heals_many(spell: dict) -> bool:
    return spell["target"] == "all_allies" or bool(spell.get("area")) and spell.get("affects") == "allies"


def road_use(tables, spell_id: str) -> str | None:
    """What a spell is for outside a fight: "heal", "cure", "identify", "lasting" (cast before a fight), or None."""
    spell = tables.spells[spell_id]
    if has_op(spell, "identify"):
        return "identify"
    if has_op(spell, "heal"):
        return "heal"
    if has_op(spell, "restore"):
        return "cure"
    if lasts(tables, spell_id):
        return "lasting"
    return None


def summary(spell: dict) -> list[str]:
    """A few words on what it does: "8d6 fire", "DEX save", "heals 2d8"."""
    bits: list[str] = []
    for o in spell.get("effects", ()):
        for dice_, dtype, _ in damage_parts(o):
            bits.append(f"{dice_} {dtype}".strip())
        if o["op"] == "heal":
            bits.append(f"heals {o['dice']}")
        if o["op"] == "save":
            bits.append(f"{o['ability'].upper()} save")
        if o["op"] == "attack":
            bits.append(f"{o['attack']} attack")
    return list(dict.fromkeys(bits))


def lasts(tables, spell_id: str) -> bool:
    """A spell that outlives a fight: a buff of ten minutes or more."""
    spell = tables.spells[spell_id]
    return bool(buff_of(spell)) and int(spell.get("rounds", 0)) >= MIN_LASTING_ROUNDS


def lasting(char: Character, tables=None) -> dict[str, float]:
    """The spells still working on someone: spell id -> hours left."""
    out = {k[len(LASTING):]: float(v) for k, v in char.effects.items() if k.startswith(LASTING) and v > 0}
    return {k: v for k, v in out.items() if tables is None or k in tables.spells}


def keep(char: Character, tables, spell_id: str) -> float:
    """A lasting spell has just been cast on this character: it works for its full time from now (casting it
    again renews it; the same spell never stacks). Returns the hours it will last."""
    hours = int(tables.spells[spell_id].get("rounds", 0)) / ROUNDS_PER_HOUR
    key = LASTING + spell_id
    char.effects[key] = max(float(char.effects.get(key, 0.0)), hours)
    return hours


def end(char: Character, spell_id: str) -> None:
    char.effects.pop(LASTING + spell_id, None)


def lasting_values(char: Character, tables, key: str) -> list:
    """One part of the lasting spells on a character (their "ac" bonuses, a "mage_armor" base...)."""
    if not char.effects:
        return []
    return [buff_of(tables.spells[sid])[key] for sid in lasting(char, tables)
            if key in buff_of(tables.spells[sid])]


def battle_part(tables, spell_id: str) -> dict:
    """What a battle has to carry of a lasting spell (the sheet already counts its armour): {} for nothing."""
    part = {k: v for k, v in buff_of(tables.spells[spell_id]).items() if k not in SHEET_KEYS}
    return {**part, "lasting": spell_id, "source": spell_id} if part else {}


def on_the_road(tables, spell_id: str) -> tuple[bool, str]:
    """Whether a spell is any use outside a fight, and why not."""
    spell = tables.spells[spell_id]
    if road_use(tables, spell_id) is not None:
        return True, ""
    if buff_of(spell):
        return False, "over too quickly to cast before a fight"
    return False, "only in a fight"


def lowest_free_slot(char: Character, tables, level: int) -> int | None:
    left = slots_left(char, tables)
    for i in range(level - 1, len(left)):
        if left[i] > 0:
            return i + 1
    return None


def spend_slot(char: Character, slot_level: int) -> None:
    used = char.spells.setdefault("slots_used", [0] * 9)
    used[slot_level - 1] += 1


def unspend_slot(char: Character, slot_level: int) -> None:
    """A slot given back (a spell that was countered, a Spell Breaker's Counterspell that stopped nothing)."""
    used = char.spells.setdefault("slots_used", [0] * 9)
    used[slot_level - 1] = max(0, used[slot_level - 1] - 1)


def restore_slots(char: Character) -> None:
    if char.spells:
        char.spells["slots_used"] = [0] * 9


def casting_ability(char: Character, tables) -> str:
    sc = tables.classes[char.cls].get("spellcasting")
    return sc["ability"] if sc else "int"


def focus_bonus(char: Character, tables) -> int:
    """+1 to spell attacks and spell DCs with the right focus: a priest's holy symbol worn or held, a wizard's crystal
    held in the hand or component pouch carried (data/items.json `focus`)."""
    sc = tables.classes[char.cls].get("spellcasting") if char.cls in tables.classes else None
    if not sc:
        return 0
    kind = "arcane" if sc.get("type") == "spellbook" else "divine"
    worn = set(char.equipped.values())
    for it in char.inventory:
        f = tables.items.get(it.def_id).get("focus")
        if f and f["kind"] == kind and (it.uid in worn or f.get("carried")):
            return 1
    return 0


def attack_bonus(sheet: Sheet, tables) -> int:
    return sheet.proficiency + sheet.mod(casting_ability(sheet.c, tables)) + focus_bonus(sheet.c, tables)


def save_dc(sheet: Sheet, tables) -> int:
    return 8 + sheet.proficiency + sheet.mod(casting_ability(sheet.c, tables)) + focus_bonus(sheet.c, tables)


def cantrip_multiplier(level: int) -> int:
    return 1 if level < 5 else (2 if level < 11 else 3)
