"""Spellcasting: which spells a character can cast, spell slots, attack bonus and save DC.

Casters prepare their level 1+ spells (2024): a wizard from the spellbook (new spells are copied in from scrolls
and books, M8), a cleric from the whole cleric list; see "preparing spells" below.

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
CAST_AT = "spell_at:"  # ...and the slot level a lasting spell was cast with, when higher than its own
MIN_LASTING_ROUNDS = 100  # ten minutes (a round is six seconds): long enough to be worth casting before a fight
ROUNDS_PER_HOUR = 600
# The parts of a lasting spell the character sheet already counts (so a fight does not count them twice), and the parts
# only the world outside a fight reads (Part E.2: a phantom horse, the servant, walking on water, flying as a cloud...).
SHEET_KEYS = ("ac", "mage_armor", "darkvision", "speed", "skills", "check_adv", "carry",
              "steed", "servant", "water_walk", "water_breathing", "wind", "ethereal", "pathfinding")


class SpellTable:
    def __init__(self, data: dict) -> None:
        self.defs: dict[str, dict] = {k: v for k, v in data["spells"].items() if not k.startswith("_")}
        self.starting: dict[str, dict] = data.get("starting", {})
        for sid, spell in list(self.defs.items()):
            if spell.get("again"):  # its follow-up, cast without a slot while the spell is held (combat.again_spell)
                self.defs[f"{sid}_again"] = again_def(sid, spell)

    def learnable(self) -> dict[str, dict]:
        """The spells of the books, without the follow-ups made from them."""
        return {k: v for k, v in self.defs.items() if not v.get("again_of")}

    def __getitem__(self, spell_id: str) -> dict:
        return self.defs[spell_id]

    def __contains__(self, spell_id: str) -> bool:
        return spell_id in self.defs

    def for_class(self, cls: str, max_level: int) -> list[str]:
        return [sid for sid, s in self.defs.items() if cls in s["classes"] and s["level"] <= max_level]


def again_def(sid: str, spell: dict) -> dict:
    """A spell's follow-up as a spell of its own (`again` in data/spells.json: name, text, cast, target, range, area,
    affects, effects), at the spell's level, of the class "again" (nobody learns it, no scroll is made of it)."""
    a = spell["again"]
    out = {"name": a.get("name", spell["name"]), "level": spell["level"], "school": spell.get("school", ""),
           "classes": ["again"], "again_of": sid, "target": a.get("target", "enemy"),
           "range": a.get("range", spell.get("range", 60)), "effects": a["effects"], "text": a["text"],
           "fx": a.get("fx", spell.get("fx", "bolt"))}
    for key in ("cast", "area", "affects"):
        if key in a:
            out[key] = a[key]
    return out


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
    char.uses["prepare"] = 1  # (a new caster chooses the prepared list freely until the first fight)


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
    """Every spell this character could cast (given a free slot): the cantrips, the spells prepared today and the
    ones always prepared (a domain's spells, Spell Breaker's)."""
    if not is_caster(char, tables):
        return []
    out = [s for s in char.spells.get("cantrips", []) if s in tables.spells]
    out += prepared(char, tables) + always_prepared(char, tables)
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------------------- preparing spells (2024)
# Every caster prepares a list of level 1+ spells, as many as the class table's Prepared Spells column says: a
# cleric from the whole cleric list, a wizard from the spellbook. The list is `char.spells["prepared"]`; spells a
# feature always has prepared (a domain's, Spell Breaker's) are on top of it. It may be changed whole after a long
# rest or a new level (`char.uses["prepare"]`), one spell after a short rest for a wizard's Memorize Spell
# (`char.uses["memorize"]`); either stays open until the next fight. An empty place may be filled at any time.
# Nobody is left with empty places: the Auto fills them by what the caster is for (`fill_prepared`).
def prepared_count(char: Character, tables) -> int:
    row = (tables.classes[char.cls].get("spellcasting") or {}).get("prepared")
    if not row:
        return 0
    return int(row[max(0, min(len(row) - 1, char.level - 1))])


def always_prepared(char: Character, tables) -> list[str]:
    """Spells a feature keeps prepared beyond the count: a domain's spells (by class level; those not yet in the game
    wait for it), Spell Breaker's Counterspell and Dispel Magic."""
    if not is_caster(char, tables):
        return []
    top = max_spell_level(char, tables)
    sub = tables.classes[char.cls].get("subclasses", {}).get(char.subclass or "", {})
    out = [sid for lvl, ids in sorted((sub.get("spells") or {}).items(), key=lambda kv: int(kv[0]))
           if int(lvl) <= char.level for sid in ids]
    if "spell_breaker" in char.features:  # (an abjurer's Spell Breaker: always ready, in the book or not)
        out += SPELL_BREAKER
    return [s for s in dict.fromkeys(out) if s in tables.spells and 0 < tables.spells[s]["level"] <= top]


def preparable(char: Character, tables) -> list[str]:
    """The level 1+ spells they may choose to prepare: a wizard's spellbook, a cleric's whole list (of a level they
    have slots for), less those always prepared."""
    if not is_caster(char, tables) or not char.spells:
        return []
    top = max_spell_level(char, tables)
    if (tables.classes[char.cls].get("spellcasting") or {}).get("type") == "spellbook":
        pool = [s for s in char.spells.get("spellbook", []) if s in tables.spells]
    else:
        pool = tables.spells.for_class(char.cls, top)
    always = set(always_prepared(char, tables))
    return [s for s in dict.fromkeys(pool) if 0 < tables.spells[s]["level"] <= top and s not in always]


def prepared(char: Character, tables) -> list[str]:
    """The spells they chose to prepare (not counting the always prepared). A caster who never chose has the Auto's
    choice."""
    if not is_caster(char, tables) or not char.spells:
        return []
    if "prepared" not in char.spells:
        char.spells["prepared"] = []
        fill_prepared(char, tables)
    can = set(preparable(char, tables))
    return [s for s in dict.fromkeys(char.spells["prepared"]) if s in can][:prepared_count(char, tables)]


def room_to_prepare(char: Character, tables) -> int:
    return max(0, prepared_count(char, tables) - len(prepared(char, tables)))


# What each kind of spell is worth to each kind of caster (feats.archetype): a healer prays for healing first, a
# fighting priest for blessings on the blade, a wizard for fire and the means to stop a foe.
PREPARE_WEIGHTS = {
    "healer": {"heal": 6.0, "buff": 4.0, "harm": 3.0, "guard": 2.0, "other": 0.5},
    "caster": {"harm": 6.0, "guard": 4.5, "buff": 3.0, "heal": 2.0, "other": 0.5},
    "_": {"buff": 5.0, "harm": 4.0, "heal": 4.0, "guard": 2.0, "other": 0.5},
}


def prepare_kind(spell: dict) -> str:
    """What a spell is for, as the Auto prepares: heal, guard (a reaction), harm, buff, road (for outside a fight)
    or other."""
    if out_of_battle(spell) or has_op(spell, "road"):
        return "road"
    if heal_op(spell) or has_op(spell, "revive", "restore"):
        return "heal"
    if spell.get("cast") == "reaction":
        return "guard"
    if harms(spell):
        return "harm"
    if buff_of(spell) or has_op(spell, "summon", "zone", "max_up"):
        return "buff"
    return "other"


def auto_prepare_order(char: Character, tables, pool: list[str], have: list[str]) -> list[str]:
    """The pool in the order the Auto would prepare it, after what they `have`: by what the caster is for, the
    strongest first, and a mixture rather than many of one kind. A wizard's rituals are read from the book when
    needed (Ritual Adept), so they come last."""
    from realmwalker.rules import feats

    weights = PREPARE_WEIGHTS.get(feats.archetype(char, tables), PREPARE_WEIGHTS["_"])
    kinds: dict[str, int] = {}
    for sid in have:
        k = prepare_kind(tables.spells[sid])
        kinds[k] = kinds.get(k, 0) + 1
    adept = "ritual_adept" in char.features

    def worth(sid: str) -> float:
        sp = tables.spells[sid]
        kind = prepare_kind(sp)
        if kind == "road":  # (outside a fight: chosen by the player for a need, never ahead of the fight's spells)
            return 0.5 - 2.0 * kinds.get(kind, 0) - (20 if adept and sp.get("ritual") else 0)
        w = weights[kind] + 1.5 * sp["level"] - 2.0 * kinds.get(kind, 0)
        return w - 20 if adept and sp.get("ritual") else w

    left = sorted(pool, key=lambda sid: tables.spells[sid]["name"])
    out = []
    while left:
        best = max(left, key=worth)  # (the first in name order among equals)
        left.remove(best)
        out.append(best)
        k = prepare_kind(tables.spells[best])
        kinds[k] = kinds.get(k, 0) + 1
    return out


def fill_prepared(char: Character, tables) -> list[str]:
    """Fill every empty place on the prepared list the way the Auto would; returns the spells added."""
    if not is_caster(char, tables) or not char.spells:
        return []
    have = prepared(char, tables) if "prepared" in char.spells else []
    char.spells["prepared"] = list(have)
    room = prepared_count(char, tables) - len(have)
    if room <= 0:
        return []
    pool = [s for s in preparable(char, tables) if s not in have]
    added = auto_prepare_order(char, tables, pool, have)[:room]
    char.spells["prepared"] += added
    return added


def open_preparing(char: Character, how: str) -> None:
    """A long rest or a new level ("prepare": the whole list), a short rest ("memorize": one spell, a wizard's
    Memorize Spell)."""
    if not char.spells:
        return
    if how == "prepare":
        char.uses["prepare"] = 1
    elif how == "memorize" and "memorize_spell" in char.features:
        char.uses["memorize"] = 1


def close_preparing(char: Character) -> None:
    """A fight begins: the list stays as it is until the next rest."""
    char.uses.pop("prepare", None)
    char.uses.pop("memorize", None)


def preparing_open(char: Character) -> str:
    """"prepare" (the whole list may change), "memorize" (one spell) or "" (only empty places may be filled)."""
    if char.uses.get("prepare", 0) > 0:
        return "prepare"
    if char.uses.get("memorize", 0) > 0 and "memorize_spell" in char.features:
        return "memorize"
    return ""


def unprepare_problem(char: Character, tables, spell_id: str) -> str | None:
    if spell_id in always_prepared(char, tables):
        return "always prepared"
    if spell_id not in prepared(char, tables):
        return "not prepared"
    if not preparing_open(char):
        return "prepared spells change after a long rest" + (
            " (one after a short rest: Memorize Spell)" if "memorize_spell" in char.features else "")
    return None


def prepare_problem(char: Character, tables, spell_id: str) -> str | None:
    if spell_id in always_prepared(char, tables) or spell_id in prepared(char, tables):
        return "already prepared"
    if spell_id not in preparable(char, tables):
        return "not a spell you can prepare yet"
    if room_to_prepare(char, tables) <= 0:
        return "the list is full: put a spell aside first"
    return None


def toggle_prepared(char: Character, tables, spell_id: str) -> str:
    """Prepare the spell, or put it aside; returns what to say."""
    name = tables.spells[spell_id]["name"]
    if spell_id in prepared(char, tables) or spell_id in always_prepared(char, tables):
        why = unprepare_problem(char, tables, spell_id)
        if why:
            return f"{name}: {why}."
        how = preparing_open(char)
        char.spells["prepared"] = [s for s in prepared(char, tables) if s != spell_id]
        if how == "memorize":
            char.uses["memorize"] = 0
            return f"{name} is put aside (Memorize Spell): prepare another from the book in its place."
        return f"{name} is put aside: {room_to_prepare(char, tables)} to prepare."
    why = prepare_problem(char, tables, spell_id)
    if why:
        return f"{name}: {why}."
    char.spells["prepared"] = prepared(char, tables) + [spell_id]
    return f"{name} is prepared."


def ritual_spells(char: Character, tables) -> list[str]:
    """Rituals they may cast outside a fight without having them prepared: a wizard's spellbook (Ritual Adept)."""
    if "ritual_adept" not in char.features or not char.spells:
        return []
    return [s for s in char.spells.get("spellbook", []) if s in tables.spells and tables.spells[s].get("ritual")]


SPELL_BREAKER = ("counterspell", "dispel_magic")  # (Dispel Magic comes with the catalogue, Part D)


def free_cast(char: Character, tables, spell_id: str, slot_level: int | None = None) -> str | None:
    """How a spell can be cast at its own level without a slot, or None: a wizard's Spell Mastery ("mastery", at
    will) or Signature Spells ("signature", once until a short or long rest)."""
    sp = tables.spells.defs.get(spell_id)
    if sp is None or sp["level"] == 0 or not char.spells or (slot_level and slot_level != sp["level"]):
        return None
    if spell_id in char.spells.get("mastery", ()) and "spell_mastery" in char.features:
        return "mastery"
    if spell_id in char.spells.get("signature", ()) and "signature_spells" in char.features \
            and char.uses.get(f"signature:{spell_id}", 0) > 0:
        return "signature"
    return None


def spend_free(char: Character, spell_id: str, how: str | None) -> None:
    if how == "signature":
        char.uses[f"signature:{spell_id}"] = 0


# ---------------------------------------------------------------------------- casting with a higher slot (2024)
# What a higher slot adds is in the spell's ops: `up` (dice more per slot level above the spell's), `count_up` (one
# more dart, one more creature blessed or healed), `rays_up` (one more ray) and the spell's `targets_up` (one more
# creature of the same kind). A spell without any of them gains nothing from a higher slot.
UP_KEYS = ("up", "count_up", "rays_up")
UP_OPS = ("max_up", "road")  # ops whose `per_up` makes a higher slot worth it (Aid, Create or Destroy Water)


def upcasts(spell: dict) -> bool:
    """Whether a higher slot does more with this spell."""
    if spell.get("level", 0) <= 0:
        return False
    return bool(spell.get("targets_up")) or any(o.get(k) for o in ops(spell) for k in UP_KEYS) \
        or any(o.get("per_up") for o in ops(spell) if o["op"] in UP_OPS) \
        or any(more for o in ops(spell) for _, _, more in damage_parts(o))


def more_dice(more: str, up: int) -> str:
    """`more` taken `up` times ("1d6", 2 -> "2d6")."""
    from realmwalker.core import dice

    n, sides, flat = dice.parse(more)
    return (f"{n * up}d{sides}" if n else "") + (f"{flat * up:+d}" if flat else "")


def scaled(base: str, more: str, up: int) -> str:
    """Dice with `more` added `up` times ("8d6", "1d6", 2 -> "10d6"); a different die is added as its own term."""
    if not more or up <= 0:
        return base
    from realmwalker.core import dice

    bn, bs, bf = dice.parse(base)
    mn, ms, mf = dice.parse(more)
    if ms == bs or bn == 0:
        n, sides = bn + mn * up, ms if bn == 0 else bs
        flat = bf + mf * up
        return f"{n}d{sides}" + (f"{flat:+d}" if flat else "")
    return f"{base}+{mn * up}d{ms}" + (f"{mf * up:+d}" if mf else "")


def up_gain(spell: dict, up: int) -> list[str]:
    """What `up` slot levels above the spell's own add, in a few words ("+2d6 fire", "+1 dart")."""
    if up <= 0:
        return []
    out: list[str] = []
    for o in spell.get("effects", ()):
        for _, dtype, more in damage_parts(o):
            if more:
                out.append(f"+{more_dice(more, up)} {dtype}".strip())
        if o["op"] == "heal" and o.get("up"):
            out.append(f"heals +{more_dice(o['up'], up)}")
        if o["op"] == "heal" and o.get("per_up"):
            out.append(f"heals +{int(o['per_up']) * up}")
        if o.get("heal_up"):
            out.append(f"heals +{more_dice(o['heal_up'], up)}")
        if o["op"] == "temp_hp" and o.get("per_up"):
            out.append(f"+{int(o['per_up']) * up} temporary hit points")
        if o["op"] == "max_up" and o.get("per_up"):
            out.append(f"+{int(o['per_up']) * up} hit points")
        if o["op"] == "road" and o.get("per_up") and o.get("pints"):
            out.append(f"+{int(o['per_up']) * up // 8} gallons")
        what = {"darts": "dart", "heal": "creature healed", "modifier": "creature"}.get(o["op"], "more")
        if o.get("count_up"):
            n = int(o["count_up"]) * up
            out.append(f"+{n} {what}{'s' if n > 1 and not what.endswith('more') else ''}")
        if o.get("rays_up"):
            n = int(o["rays_up"]) * up
            out.append(f"+{n} ray{'s' if n > 1 else ''}")
    if spell.get("targets_up"):
        n = int(spell["targets_up"]) * up
        out.append(f"+{n} target{'s' if n > 1 else ''}")
    return list(dict.fromkeys(out))


def slot_choices(char: Character, tables, spell_id: str) -> list[int]:
    """The slot levels with a slot left that could cast this spell (its own level and up)."""
    sp = tables.spells.defs.get(spell_id)
    if sp is None or sp["level"] <= 0 or not char.spells:
        return []
    left = slots_left(char, tables)
    return [i + 1 for i in range(sp["level"] - 1, len(left)) if left[i] > 0]


def idle_levels(char: Character, tables) -> set[int]:
    """Slot levels for which they have no spell of that very level ready: such a slot is only good for casting a
    lower spell higher."""
    have = {tables.spells[s]["level"] for s in known_spells(char, tables)}
    return {lvl for lvl in range(1, max_spell_level(char, tables) + 1) if lvl not in have}


def auto_slot(char: Character, tables, spell_id: str) -> int | None:
    """The slot the Auto would cast this spell with: a spare higher slot (one with no spell of its own level ready)
    when the spell does more with it, else the lowest that will do."""
    levels = slot_choices(char, tables, spell_id)
    if not levels:
        return None
    if upcasts(tables.spells[spell_id]):
        idle = [lvl for lvl in levels if lvl > levels[0] and lvl in idle_levels(char, tables)]
        if idle:
            return max(idle)
    return levels[0]


def armour_problem(char: Character, tables) -> str:
    """Armour worn without training stops all spellcasting (2024)."""
    armor = char.equipped_item("armor")
    if armor is not None and not Sheet(char, tables).proficient_with_armor(armor):
        return "no spells in armour you are not trained to wear"
    return ""


# ---------------------------------------------------------------------------- components (2024)
# A spell's Material component without a cost is stood in for by a component pouch or a spellcasting focus of the
# caster's kind (a cleric's holy symbol, a wizard's crystal, orb, rod, staff or the spellbook itself); one with a cost
# (`spell["material"]`) needs that very thing, and one the spell consumes is used up as it is cast. The party carries
# one pack, so a focus anywhere in it serves (the book has it held or worn). Verbal and Somatic components are taken
# as given until something in the game can silence a caster or bind their hands.
def has_focus(char: Character, tables) -> bool:
    sc = tables.classes[char.cls].get("spellcasting") if char.cls in tables.classes else None
    kind = "arcane" if (sc or {}).get("type") == "spellbook" else "divine"
    for it in char.inventory:
        d = tables.items.get(it.def_id)
        if it.def_id == "component_pouch" or (d.get("focus") or {}).get("kind") == kind \
                or (kind == "arcane" and it.def_id == "spellbook"):
            return True
    return False


def component_problem(char: Character, tables, spell_id: str) -> str:
    """Why the spell's material component is missing ("" when it is at hand)."""
    spell = tables.spells[spell_id]
    if "M" not in (spell.get("components") or ()):
        return ""
    m = spell.get("material")
    if m:
        if not any(it.def_id in m["items"] for it in char.inventory):
            return f"needs {m['text'].split(',')[0]}"
        return ""
    if not has_focus(char, tables):
        return "needs a focus or a component pouch for its materials"
    return ""


def spend_material(char: Character, tables, spell_id: str) -> str | None:
    """The spell is cast: a component it consumes is used up. Returns the thing's name, or None."""
    m = tables.spells[spell_id].get("material")
    if not m or not m.get("consumed"):
        return None
    from realmwalker.rules.inventory import remove_item

    have = [it for it in char.inventory if it.def_id in m["items"]]
    if not have:
        return None
    it = min(have, key=lambda it: int(tables.items.get(it.def_id).get("value", 0)))  # (the cheapest that will do)
    remove_item(char, it.uid, 1)
    return tables.items.get(it.def_id)["name"]


def can_cast(char: Character, tables, spell_id: str) -> tuple[bool, str]:
    spell = tables.spells[spell_id]
    if spell_id == "wish" and char.spells.get("wish_lost"):
        return False, "the strain of an old wish: Wish will never come again"
    if "item" not in spell.get("classes", ()) and armour_problem(char, tables):
        return False, armour_problem(char, tables)
    if "item" not in spell.get("classes", ()) and component_problem(char, tables, spell_id):
        return False, component_problem(char, tables, spell_id)
    if spell["level"] == 0 or free_cast(char, tables, spell_id):
        return True, ""
    left = slots_left(char, tables)
    if any(left[i] > 0 for i in range(spell["level"] - 1, len(left))):
        return True, ""
    return False, "no spell slots of that level left (rest to recover)"


# ---------------------------------------------------------------------------- Wish (PHB 2024)
# Its basic use copies any other spell of level 8 or lower, with no requirements (no components), and is safe. Any
# other use (here: Instant Health, the "wish" spell's own effects) brings the stress: every spell cast until a long
# rest costs 1d10 necrotic a level of it (nothing reduces it), Strength becomes 3 for 2d4 days, and a third of the time
# Wish never comes again. Kept on the character: effects "wish_stress" (until a long rest) and "wish_strength"
# (hours), spells["wish_lost"].
def wish_copies(tables) -> list[str]:
    """The spells Wish can copy in a fight: every battle spell of level 1 to 8 (not a reaction, not one cast in
    minutes, not an item's or a follow-up)."""
    cached = getattr(tables, "_wish_copies", None)
    if cached is not None:
        return cached
    out = []
    for sid, sp in tables.spells.defs.items():
        if not isinstance(sp, dict) or sid.startswith("_") or not 1 <= int(sp.get("level", 0)) <= 8:
            continue
        cls = set(sp.get("classes", ()))
        if not cls or cls <= {"item", "again", "wish"} or "item" in cls or sp.get("again_of") or sp.get("ability") \
                or sp.get("thrown") or out_of_battle(sp) or sp.get("cast") == "reaction" or sp.get("target") == "item" \
                or has_op(sp, "identify", "revive"):
            continue
        out.append(sid)
    out.sort(key=lambda s: (-int(tables.spells[s]["level"]), tables.spells[s]["name"]))
    tables._wish_copies = out
    return out


def wish_stress(char: Character, rng) -> list[str]:
    """The stress of a Wish used for anything but copying a spell. Returns what to say."""
    days = rng.randint(1, 4) + rng.randint(1, 4)
    char.effects["wish_stress"] = 1.0e6  # (until a long rest: progression.long_rest)
    char.effects["wish_strength"] = 24.0 * days
    first = char.name.split()[0]
    out = [f"<danger>The wish takes its toll.</> {first}'s strength drains away (Strength 3 for {days} days), and "
           "every spell until a long rest will tear at them."]
    if rng.chance(0.33):
        char.spells["wish_lost"] = True
        out.append(f"<danger>Something in {first} has broken:</> Wish will never come to them again.")
    return out


def strain(char: Character | None, level: int, rng) -> int:
    """The stress of an earlier Wish: necrotic damage for casting a spell of this level (0 when there is none)."""
    if char is None or level <= 0 or not char.effects.get("wish_stress"):
        return 0
    return sum(rng.randint(1, 10) for _ in range(level))


# ---------------------------------------------------------------------------- spell scrolls (DMG 2024)
# A scroll is read by whoever has its spell on their spell list (their class's list, or a feature's spells that are
# always prepared); to anyone else it is unintelligible. It casts with its own save DC and attack bonus (by the spell's
# level, data/rules.json "spell_scrolls"), needs no materials and no slot, and crumbles once the spell is cast. A spell
# above the highest level the reader can cast takes an ability check with the spellcasting ability first (DC 10 + the
# spell's level); on a failure the words fade and nothing happens. A thief's Use Magic Device reads any scroll with
# Intelligence: cantrips and level 1 spells surely, higher ones after an Intelligence (Arcana) check, DC the same.
def scroll_numbers(tables, level: int) -> tuple[int, int]:
    """(save DC, attack bonus) a scroll of this spell level casts with."""
    n = tables.rules.get("spell_scrolls") or {}
    dcs, attacks = n.get("dc") or [13], n.get("attack") or [5]
    i = max(0, min(int(level), len(dcs) - 1))
    return int(dcs[i]), int(attacks[min(i, len(attacks) - 1)])


def scroll_reader(char: Character, tables, spell_id: str) -> str | None:
    """How this character reads a scroll of this spell: "sure" (on their list, a level they can cast), "check" (on
    their list but above them: a spellcasting check first), "device" (Use Magic Device: Intelligence, sure for a
    cantrip or level 1, else an Arcana check: "device_check"), or None (unintelligible to them)."""
    spell = tables.spells[spell_id] if spell_id in tables.spells else None
    if spell is None:
        return None
    level = int(spell["level"])
    own = is_caster(char, tables) and (char.cls in spell.get("classes", ()) or spell_id in always_prepared(char, tables))
    if own:
        return "sure" if level <= max_spell_level(char, tables) else "check"
    if "use_magic_device" in char.features:
        return "device" if level <= 1 else "device_check"
    return None


def scroll_ability(char: Character, tables, how: str | None) -> str:
    """The ability the reader casts a scroll's spell with (Intelligence through Use Magic Device)."""
    return "int" if how in ("device", "device_check") else casting_ability(char, tables)


def scroll_check(sheet: Sheet, tables, spell_id: str, how: str | None) -> tuple[int, int, str] | None:
    """(bonus, DC, words) of the check before reading a scroll above the reader, or None when none is needed."""
    if how not in ("check", "device_check"):
        return None
    dc = 10 + int(tables.spells[spell_id]["level"])
    if how == "device_check":
        return sheet.skill_bonus("arcana"), dc, "Intelligence (Arcana)"
    ability = casting_ability(sheet.c, tables)
    return sheet.mod(ability), dc, tables.rules["abilities"][ability]["name"]


def scroll_odds(sheet: Sheet, tables, spell_id: str, how: str | None) -> float:
    """The chance a reading of the scroll works (1.0 when no check is needed)."""
    check = scroll_check(sheet, tables, spell_id, how)
    if check is None:
        return 1.0
    bonus, dc, _ = check
    return max(0.05, min(1.0, (21 - (dc - bonus)) / 20))


def scroll_problem(char: Character, tables, spell_id: str) -> str:
    """Why this character cannot read a scroll of this spell ("" if they can)."""
    if scroll_reader(char, tables, spell_id) is None:
        return "unintelligible to you: the spell is not on your list"
    return armour_problem(char, tables) or ""


# ---------------------------------------------------------------------------- reading a spell's effects
NESTED = ("on_hit", "on_fail", "on_save", "after", "do")


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
        for _, inner in o.get("tiers", ()):  # (Divine Word: what each band of hit points brings)
            todo.extend(inner)
        for inner in o.get("choices", ()):  # (Prismatic Spray: each ray)
            todo.extend(inner)
        for st in o.get("stages", ()):  # (Storm of Vengeance: each turn of the storm)
            todo.extend(st.get("ops", ()))
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


def buff_of(spell: dict, level: int | None = None) -> dict:
    """What a spell's modifier puts on its target ({"ac": 2}, {"resist": [...]}...), {} if it has none; cast with a
    slot of `level`, its numbers grown by the op's `per_up` and `by_level`."""
    m = op(spell, "modifier")
    return buff_at(m, level, spell) if m else {}


def buff_at(m: dict, level: int | None, spell: dict) -> dict:
    """A modifier op's buff at a slot level: `per_up` {key: more for each level above the spell's}, `by_level`
    {key: {"4": value, "6": value}} (the highest reached)."""
    out = dict(m["buff"])
    up = max(0, int(level or spell["level"]) - int(spell["level"]))
    for k, more in (m.get("per_up") or {}).items():
        if isinstance(more, str):  # dice: "1d6" more for each level above (Searing Smite's burning)
            out[k] = scaled(str(out.get(k, "0")), more, up)
        else:
            out[k] = int(out.get(k, 0)) + int(more) * up
    for k, steps in (m.get("by_level") or {}).items():
        reached = [int(lv) for lv in steps if int(lv) <= int(level or spell["level"])]
        if reached:
            out[k] = steps[str(max(reached))]
    return out


def harms(spell: dict) -> bool:
    """Whether the spell is aimed at enemies (an attack or a saving throw)."""
    return has_op(spell, "attack", "save", "darts")


def heal_op(spell: dict) -> dict | None:
    return op(spell, "heal")


def heals_many(spell: dict) -> bool:
    return spell["target"] == "all_allies" or bool(spell.get("area")) and spell.get("affects") == "allies"


# What the spells of Part E do outside a fight: a spell's {"op": "road", "does": ...} names one of these (game/spellwork
# does it; the start-up check knows them), its "ward" one of WARDS (kept on the camp: game/spellwork.ward).
ROAD_USES = ("feed", "water", "purify", "goodberry", "feast", "ward", "repose", "uncurse", "regenerate",
             "flame", "travel")  # (Part E.2: an everburning torch; travel by magic, game/waymagic.py)
WARDS = ("alarm", "hut", "hound", "rope", "mansion", "meld")
# How a "travel" spell goes (game/waymagic.py), and what a lasting spell does as it is cast outside a fight (its
# "outside": game/waymagic.after_lasting).
TRAVELS = ("teleport", "circle", "recall", "plants", "shift", "astral", "gate_far", "gate")
OUTSIDE = ("disguise", "path")


def road_use(tables, spell_id: str) -> str | None:
    """What a spell is for outside a fight: "heal", "cure", "identify", "revive" (a fallen companion: game/revival),
    "lasting" (cast before a fight), one of ROAD_USES, or None."""
    spell = tables.spells[spell_id]
    if has_op(spell, "identify"):
        return "identify"
    if has_op(spell, "revive"):
        return "revive"
    road = op(spell, "road")
    if road is not None:
        return road["does"]
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
    return (bool(buff_of(spell)) or has_op(spell, "max_up")) and int(spell.get("rounds", 0)) >= MIN_LASTING_ROUNDS \
        and not spell.get("battle_only")


def lasting(char: Character, tables=None) -> dict[str, float]:
    """The spells still working on someone: spell id -> hours left."""
    out = {k[len(LASTING):]: float(v) for k, v in char.effects.items() if k.startswith(LASTING) and v > 0}
    return {k: v for k, v in out.items() if tables is None or k in tables.spells}


def keep(char: Character, tables, spell_id: str, level: int | None = None) -> float:
    """A lasting spell has just been cast on this character: it works for its full time from now (casting it
    again renews it; the same spell never stacks). `level`: the slot it was cast with (Magic Weapon grows with
    it). Returns the hours it will last."""
    hours = int(tables.spells[spell_id].get("rounds", 0)) / ROUNDS_PER_HOUR
    key = LASTING + spell_id
    char.effects[key] = max(float(char.effects.get(key, 0.0)), hours)
    if level and int(level) > int(tables.spells[spell_id]["level"]):
        char.effects[CAST_AT + spell_id] = float(level)
    else:
        char.effects.pop(CAST_AT + spell_id, None)
    return hours


def cast_at(char: Character, tables, spell_id: str) -> int:
    """The slot level a lasting spell on a character was cast with."""
    return int(char.effects.get(CAST_AT + spell_id, 0)) or int(tables.spells[spell_id]["level"])


def end(char: Character, spell_id: str) -> None:
    char.effects.pop(LASTING + spell_id, None)
    char.effects.pop(CAST_AT + spell_id, None)
    lower_max(char, spell_id)


# ---------------------------------------------------------------------------- a raised maximum (Aid, Heroes' Feast)
# A spell that raises the hit point maximum (an op {"op": "max_up", "amount": dice, "per_up", "count"}) does it to the
# character itself while the spell lasts: `max_hp` and `hp` go up by the amount, kept in `effects["spell_hp:<id>"]`
# (which does not wear down: it goes with the spell), and come down again when the spell ends (rules/health.py).
MAX_UP = "spell_hp:"


def raise_max(char: Character, spell_id: str, amount: int) -> int:
    """Raise a character's maximum (and hit points) by a spell; the same spell never stacks: the larger stays.
    Returns what was gained."""
    key = MAX_UP + spell_id
    old = int(char.effects.get(key, 0))
    if amount <= old:
        return 0
    char.max_hp += amount - old
    char.hp += amount - old
    char.effects[key] = float(amount)
    return amount - old


def lower_max(char: Character, spell_id: str) -> int:
    """The spell that raised the maximum has ended: it comes down again (and hit points with it, if above)."""
    amount = int(char.effects.pop(MAX_UP + spell_id, 0))
    if amount:
        char.max_hp = max(1, char.max_hp - amount)
        char.hp = min(char.hp, char.max_hp)
    return amount


def max_up_amount(spell: dict, level: int, rng=None) -> int:
    """How much a max_up op raises the maximum, cast with a slot of `level` (its dice rolled with `rng`, or the
    average without one)."""
    from realmwalker.core import dice

    o = op(spell, "max_up")
    if o is None:
        return 0
    extra = int(o.get("per_up", 0)) * max(0, level - int(spell["level"]))
    text = str(o["amount"])
    if rng is None:
        count, sides, mod = dice.parse(text)
        return int(count * (sides + 1) / 2) + mod + extra
    return dice.roll(text, rng).total + extra


def out_of_battle(spell: dict) -> bool:
    """A spell that is never cast in a fight: it takes a minute or more ("minutes"), or its use is only outside one
    ("road_only": food, water, wards, bodies)."""
    return bool(spell.get("minutes") or spell.get("road_only"))


def lasting_values(char: Character, tables, key: str) -> list:
    """One part of the lasting spells on a character (their "ac" bonuses, a "mage_armor" base...)."""
    if not char.effects:
        return []
    out = []
    for sid in lasting(char, tables):
        buff = buff_of(tables.spells[sid], cast_at(char, tables, sid))
        if key in buff:
            out.append(buff[key])
    return out


def lasting_flag(char: Character, tables, key: str) -> bool:
    """Whether a lasting spell on this character gives it `key` (Water Walk's "water_walk", Wind Walk's "wind"...)."""
    return bool(char.effects) and any(lasting_values(char, tables, key))


def lasting_number(char: Character, tables, key: str) -> int:
    """The largest number a lasting spell on this character gives for `key` (0 for none): Light's squares."""
    return max([0] + [int(v) for v in lasting_values(char, tables, key) if v is not True]) if char.effects else 0


def best_ability(char: Character) -> str:
    """The ability Enhance Ability sharpens on someone: their strongest (Strength first in a tie; never
    Constitution, which the 2024 spell does not offer)."""
    order = ("str", "dex", "int", "wis", "cha")
    return max(order, key=lambda a: (int(char.abilities.get(a, 10)), -order.index(a)))


def battle_part(tables, spell_id: str, char: Character | None = None) -> dict:
    """What a battle has to carry of a lasting spell (the sheet already counts its armour): {} for nothing."""
    level = cast_at(char, tables, spell_id) if char is not None else None
    part = {k: v for k, v in buff_of(tables.spells[spell_id], level).items() if k not in SHEET_KEYS}
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
