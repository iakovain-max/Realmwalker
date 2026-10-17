"""Allies on the field (Expansion 3 F.1): a familiar and a steed fighting for the party.

Their records live on their owner, in `char.spells` (saved with the character): "familiar" {form, type, name, hp,
max_hp, gone, away} and "steed" {look, type, level, name, hp, gone, uses}. A fight makes a Creature of each from its
record (`bring_in`, from game/fight.start_battle), puts it beside its owner (`Battle.add_ally`), and writes what
became of it back into the record afterwards (`after`). Find Steed cast in a fight calls `summon` through the "ally"
op. Pure rules: no UI, no game state beyond the characters."""
from __future__ import annotations

import copy

from realmwalker.rules.creatures import Creature

# The forms a familiar may take (PHB 2024 Find Familiar; Appendix B's beasts of challenge 0 the game has: the octopus
# waits for fights under water).
FAMILIAR_FORMS = ("bat", "cat", "crab", "frog", "hawk", "lizard", "owl", "rat", "raven", "scorpion", "spider", "weasel")
TYPES = ("celestial", "fey", "fiend")
# What a steed looks like -> its picture (the elk waits for its picture in F.4).
STEED_LOOKS = {"horse": "riding_horse", "camel": "camel", "dire_wolf": "dire_wolf"}
STEED_DAMAGE = {"celestial": "radiant", "fey": "psychic", "fiend": "necrotic"}
STEED_GIFT = {"celestial": "steed_healing_touch", "fey": "steed_fey_step", "fiend": "steed_fell_glare"}
FAMILIAR_UID = 90000  # (creatures made for a fight: out of the way of any band's numbers)


def record(char, kind: str) -> dict | None:
    """The owner's familiar or steed, or None."""
    rec = (char.spells or {}).get(kind) if char is not None else None
    return rec if isinstance(rec, dict) else None


def present(char, kind: str) -> dict | None:
    """The record of a familiar or steed that is with its owner now (not gone, not sent away)."""
    rec = record(char, kind)
    return rec if rec is not None and not rec.get("gone") and not rec.get("away") else None


def steed_max_hp(level: int) -> int:
    return 5 + 10 * int(level)


def steed_def(tables, level: int, type_: str, attack: int, dc: int) -> dict:
    """The Otherworldly Steed's numbers for its slot and its rider (PHB 2024): AC 10 + level, 5 + 10 hit points a
    level, the rider's spell attack, a slam of 1d8 + level in its kind's damage, a Fly Speed from level 4, and its
    kind's gift once a long rest (a spell of its own: Fell Glare, Fey Step, Healing Touch)."""
    d = copy.deepcopy(tables.creatures["otherworldly_steed"])
    level = max(2, int(level))
    d["kind"] = type_
    d["ac"] = 10 + level
    d["hp"] = str(steed_max_hp(level))
    d["speeds"] = dict(d.get("speeds", {}))
    if level >= 4:
        d["speeds"]["fly"] = 60
    for a in d["attacks"]:
        a["bonus"] = int(attack)
        a["damage"] = f"1d8+{level}"
        a["damage_type"] = STEED_DAMAGE.get(type_, "radiant")
    gift = STEED_GIFT.get(type_, "steed_healing_touch")
    d["spellcasting"] = {"ability": "cha", "dc": int(dc), "attack": int(attack), "at_will": [], "per_day": {"1": [gift]},
                         "slots": []}
    d["spells"] = [gift]
    return d


def caster_numbers(char, tables) -> tuple[int, int]:
    """The owner's spell attack bonus and save DC (the steed's slam and glare use them)."""
    from realmwalker.rules import spells as spellrules
    from realmwalker.rules.character import Sheet

    sheet = Sheet(char, tables)
    return spellrules.attack_bonus(sheet, tables), spellrules.save_dc(sheet, tables)


def _creature(def_id: str, rec: dict, uid: int, max_hp: int) -> Creature:
    hp = max(0, min(int(rec.get("hp", max_hp)), max_hp))
    c = Creature(uid=uid, def_id=def_id, name=rec.get("name") or def_id, hp=hp, max_hp=max_hp, named=bool(rec.get("name")))
    c.uses = dict(rec.get("uses") or {})
    return c


def familiar_max_hp(tables, form: str) -> int:
    """A familiar has its form's average hit points (the stat block's number), so the same owl comes back the same."""
    from realmwalker.core import dice

    n, s, flat = dice.parse(str(tables.creatures[form]["hp"]))
    return max(1, int(n * (s + 1) / 2 + flat))


def bring_in(b, owners: list) -> list:
    """Every familiar and steed with its owner comes into the fight beside them. Returns the new fighters."""
    out = []
    for owner in owners:
        if owner.char is None or not owner.char.alive:
            continue
        rec = present(owner.char, "familiar")
        if rec is not None and rec.get("form") in b.t.creatures and int(rec.get("hp", 1)) > 0:
            out.append(_familiar_in(b, owner, rec))
        rec = present(owner.char, "steed")
        if rec is not None and int(rec.get("hp", 1)) > 0:
            out.append(_steed_in(b, owner, rec))
    return out


def _familiar_in(b, owner, rec: dict):
    form = rec["form"]
    cr = _creature(form, rec, FAMILIAR_UID + owner.id * 10, familiar_max_hp(b.t, form))
    return b.add_ally(cr, owner, "familiar", spell="find_familiar", level=1, type_=rec.get("type", "fey"))


def _steed_in(b, owner, rec: dict):
    level = int(rec.get("level", 2))
    attack, dc = caster_numbers(owner.char, b.t)
    cdef = steed_def(b.t, level, rec.get("type", "celestial"), attack, dc)
    cr = _creature("otherworldly_steed", rec, FAMILIAR_UID + owner.id * 10 + 1, steed_max_hp(level))
    cr.name = rec.get("name") or "steed"
    f = b.add_ally(cr, owner, "steed", spell="find_steed", level=level, type_=rec.get("type", "celestial"), cdef=cdef)
    f.bond["picture"] = STEED_LOOKS.get(rec.get("look", "horse"), "riding_horse")
    return f


def new_steed(char, level: int, look: str = "", type_: str = "", name: str = "") -> dict:
    """Find Steed: a steed at this slot's level, whole (a casting while one lives replaces it; its look and kind are
    kept unless new ones are chosen)."""
    old = record(char, "steed") or {}
    rec = {"look": look or old.get("look") or "horse", "type": type_ or old.get("type") or "celestial",
           "level": max(2, int(level)), "name": name or old.get("name") or "", "gone": False, "uses": {}}
    rec["hp"] = steed_max_hp(rec["level"])
    char.spells["steed"] = rec
    return rec


def summon(b, owner, kind: str, level: int):
    """Find Steed cast in a fight: the steed (a new one, or the old one whole again) appears beside its caster; one
    already on the field is replaced. Returns the fighter, or None."""
    if kind != "steed" or owner.char is None:
        return None
    for x in b.allies_of_owner(owner):
        if x.bond.get("kind") == "steed" and x.state != "dead":
            x.state = "dead"  # (replaced: it goes without a word)
            x.creature.alive = False
            b._event("vanish", who=x.id)
    rec = new_steed(owner.char, level)
    f = _steed_in(b, owner, rec)
    b.say(f"{owner.the_name[:1].upper() + owner.the_name[1:]} calls, and a steed that is not of this world stands "
          f"beside {owner.possessive} side.", "magic")
    return f


def after(b) -> None:
    """What became of each familiar and steed in the fight, written back into its owner's record."""
    # (in the order they came: a steed replaced mid-fight comes before the new one, which has the last word)
    for f in b.fighters:
        if f.bond is None or f.creature is None:
            continue
        owner = b.fighter(f.bond["owner"])
        rec = record(owner.char, f.bond["kind"]) if owner.char is not None else None
        if rec is None:
            continue
        if f.state == "dead" or f.hp <= 0:
            rec["gone"] = True
            rec["hp"] = 0
        else:
            rec["hp"] = int(f.hp)
            rec["gone"] = False
        rec["uses"] = dict(f.creature.uses)


def rest(char, long: bool) -> None:
    """A long rest makes a familiar and a steed whole and gives the steed back its gift."""
    if not long:
        return
    for kind in ("familiar", "steed"):
        rec = record(char, kind)
        if rec is None or rec.get("gone"):
            continue
        rec["uses"] = {}
        rec["hp"] = steed_max_hp(rec.get("level", 2)) if kind == "steed" else int(rec.get("max_hp", rec.get("hp", 1)))
