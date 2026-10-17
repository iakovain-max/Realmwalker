"""Simulacrum (Expansion 3 G.3, PHB 2024 p. 320): a copy in snow of one beast or humanoid, made by its maker's
twelve hours of work, that obeys them until it melts.

A copy of a party member is a character made from the original as they were at the casting: its hit point maximum
half theirs (full at first), what they wore and held copied in snow without any magic, nothing in a pack, no coin;
no familiar, steed, servants, shape, Contingency or Simulacrum of its own. It never gains a level, rests, eats or
heals: its hit points come back only by the maker's repair at a long rest (100 GP a hit point), and its spell slots
never come back. Its record lives on the maker, `char.spells["simulacrum"]` {of (the original's name), char (the
copy's Character record), made (the world minute)}, saved with them. A copy of a creature (a beast of the herd, a
prisoner) is a servant record instead (`rules/servants.py`, spell "simulacrum", type construct).

In a fight (`bring_in`, from game/fight.start_battle) the copy is a party-side Fighter with the copy's character and a
bond {owner, kind "simulacrum", type "construct"}, beside its maker and acting right after them; healing does nothing
to it (`Battle._heal`), at 0 hit points it melts (`Battle._apply_hp_loss`), it earns nothing and is never among the
party's dead. `after` writes back what the fight left of it. Pure rules: no UI, no game state beyond the
characters."""
from __future__ import annotations

from realmwalker.rules.character import Character

KEY = "simulacrum"
SPELL = "simulacrum"
REPAIR = 10000  # copper a hit point: 100 GP (PHB 2024)
SPEND_SHARE = 0.5  # (the game's choice: a long rest spends at most half the maker's coin on the repair)
DROP = ("familiar", "steed", "servants", "shape", "simulacrum", "contingency", "jar")  # (records of the original's)
FROST = "pale as frost"


def record(char) -> dict | None:
    """The maker's copy of a person, or None."""
    if char is None:
        return None
    rec = (char.spells or {}).get(KEY)
    return rec if isinstance(rec, dict) and rec.get("char") else None


def copy_char(rec: dict) -> Character:
    """The copy as a Character of its own (nothing shared with the record: what a fight does is written back by
    `after`)."""
    import copy

    return Character.from_dict(copy.deepcopy(rec["char"]))


_SEEN: dict[int, tuple[dict, Character]] = {}


def likeness(rec: dict) -> Character:
    """The copy as a Character for pictures, made once per record (the map draws it every frame)."""
    got = _SEEN.get(id(rec))
    if got is None or got[0] is not rec["char"]:
        if len(_SEEN) > 32:
            _SEEN.clear()
        got = _SEEN[id(rec)] = (rec["char"], copy_char(rec))
    return got[1]


def name_for(original_name: str) -> str:
    return f"{original_name.split()[0]}'s simulacrum"


def make(original: Character, tables) -> Character:
    """The copy itself: the original's statistics, half the hit point maximum, only what is worn and held (in snow:
    no magic), nothing more."""
    c = Character.from_dict(original.to_dict())
    c.name = name_for(original.name)
    c.is_player = False
    c.alive = True
    c.companion = {}
    c.max_hp = max(1, int(original.max_hp) // 2)
    c.hp = c.max_hp
    c.temp_hp = 0
    worn = set(c.equipped.values())
    keep = []
    for it in c.inventory:
        if it.uid not in worn or it.def_id not in tables.items.defs:
            continue
        it.magic = {}  # (snow and ice in the likeness of the thing: none of its magic)
        it.tags = [t for t in it.tags if t != "stolen"] + ["snow"]
        it.qty = 1 if it.qty < 1 else it.qty
        keep.append(it)
    c.inventory = keep
    kept = {it.uid for it in keep}
    c.equipped = {slot: uid for slot, uid in c.equipped.items() if uid in kept}
    c.attuned = []
    c.money = 0
    c.animals = []
    c.vehicles = []
    c.pending = []
    c.deeds = []
    c.kills = {}
    c.ties = []
    c.wounds = []
    c.injuries = []
    c.diseases = []
    c.addictions = {}
    c.effects = {}
    c.conditions = []
    c.hunger = c.thirst = c.fatigue = c.dirt = c.body_heat = c.wet = c.strain = c.hurt_carry = 0.0
    c.intoxication = 0.0
    c.exhaustion = 0
    c.blood = 100.0
    spells = dict(c.spells or {})
    for key in DROP:
        spells.pop(key, None)
    for key in ("spellbook", "prepared", "known", "mastery", "signature"):
        if isinstance(spells.get(key), list):
            spells[key] = [s for s in spells[key] if s != SPELL]  # (it cannot cast this spell)
    c.spells = spells
    return c


def keep(maker: Character, copy: Character, original_name: str, now: float) -> dict:
    """The copy is the maker's now (any copy of a person made before is gone: see `destroy`)."""
    rec = {"of": original_name, "char": copy.to_dict(), "made": float(now)}
    maker.spells[KEY] = rec
    return rec


def destroy(maker: Character) -> str | None:
    """Casting it again: the simulacrum made before is gone at once (a person's or a creature's). Returns the name of
    what melted, or None."""
    from realmwalker.rules import servants

    gone = None
    rec = record(maker)
    if rec is not None:
        gone = rec["char"].get("name")
    maker.spells.pop(KEY, None)
    for r in servants.of_spell(maker, SPELL):
        gone = gone or r.get("name")
        servants.drop(maker, r)
    return gone


def missing(rec: dict) -> int:
    d = rec["char"]
    return max(0, int(d.get("max_hp", 1)) - int(d.get("hp", 0)))


def repair(maker: Character) -> list[str]:
    """A long rest beside it: 100 GP of components a hit point, as many as are missing, never more than half the coin
    the maker carries. Returns what to say. (A creature's copy is mended the same way.)"""
    from realmwalker.rules import servants

    if not maker.alive:
        return []
    out = []
    rows = []
    rec = record(maker)
    if rec is not None:
        rows.append((rec["char"], missing(rec)))
    for r in servants.of_spell(maker, SPELL):
        rows.append((r, max(0, int(r.get("max_hp", 1)) - int(r.get("hp", 0)))))
    for row, need in rows:
        if need <= 0:
            continue
        can = int(maker.money * SPEND_SHARE) // REPAIR
        n = min(need, can)
        name = row.get("name", "the simulacrum")
        if n <= 0:
            out.append(f"{name} stays as the last fight left it: the repair takes 100 GP of powders a hit point, and "
                       f"{maker.name.split()[0]} has not the coin to spare.")
            continue
        maker.money -= n * REPAIR
        row["hp"] = int(row.get("hp", 0)) + n
        whole = "whole again" if n >= need else f"{n} of {need} hit points mended"
        out.append(f"Through the night {maker.name.split()[0]} packs fresh snow into {name}'s hurts and works "
                   f"{n * REPAIR // 100} GP of powders into them: {whole}.")
    return out


def bring_in(b, owners: list) -> list:
    """Each maker's copy of a person comes into the fight beside them. Returns the new fighters."""
    out = []
    for owner in owners:
        if owner.char is None or not owner.char.alive or owner.bond is not None:
            continue
        rec = record(owner.char)
        if rec is None or int(rec["char"].get("hp", 0)) <= 0:
            continue
        f = b.add_ally(None, owner, "simulacrum", char=copy_char(rec), type_="construct", spell=SPELL)
        out.append(f)
    return out


def after(b) -> list[str]:
    """What the fight left of each copy, written back on its maker; one that melted is struck off. Returns lines."""
    out = []
    for f in b.fighters:
        if f.bond is None or f.bond.get("kind") != "simulacrum" or f.char is None:
            continue
        owner = b.fighter(f.bond["owner"])
        if owner is None or owner.char is None:
            continue
        rec = record(owner.char)
        if rec is None:
            continue
        if f.state == "dead" or f.hp <= 0:
            owner.char.spells.pop(KEY, None)
            out.append(f"{f.char.name} slumps into a heap of wet snow and is gone.")
            continue
        f.char.hp = int(f.hp)
        f.char.temp_hp = 0
        f.char.alive = True
        f.char.wounds = []  # (snow takes no lasting wounds: what was lost is in the hit points)
        f.char.conditions = []
        rec["char"] = f.char.to_dict()
    return out


def snow(f) -> bool:
    """Whether a fighter is a simulacrum (a person's copy or a creature's)."""
    bond = getattr(f, "bond", None)
    return bond is not None and (bond.get("kind") == "simulacrum" or bond.get("spell") == SPELL)
