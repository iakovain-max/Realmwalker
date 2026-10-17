"""Servants (Expansion 3 F.4): creatures that serve a party member beyond one fight - the dead of Animate Dead and
Create Undead, and the zombie Finger of Death leaves.

Their records live on their master, in `char.spells["servants"]` (saved with the character): a list of {id, cid (the
creature), name, hp, max_hp, spell, word (it acts only when commanded), reach (feet the command carries), until (the
world minute its control ends; None: for ever), made, warned}; the bound of F.5 (a Planar Ally's spirit, a creature
held by Planar Binding) may also carry form and level (a spirit's numbers for its slot, `allies.summon_def`), picture,
heals (whole again at a long rest: `rest`), bound (Planar Binding holds it) and uses (its own magic once a day). A
fight makes a Creature of each (`bring_in`, from
game/fight.start_battle beside the familiar and the steed), puts it beside its master (`Battle.add_ally`, bond kind
"servant"), and writes back what became of it afterwards (`after`). The undead neither eat, sleep nor heal: what a
fight takes from them stays taken (the bound heal at a long rest). Pure rules: no UI, no game state beyond the
characters."""
from __future__ import annotations

from realmwalker.rules.creatures import Creature

MAX = 12  # (servants to a master: the wight's own number; the book has no cap, the battle needs one)
UID = 92000  # (servants made for a fight: out of the way of bands, familiars, steeds and spirits)
REACH = {"animate_dead": 60, "create_undead": 120}
UNDEAD = ("animate_dead", "create_undead", "finger_of_death")  # (the spells whose servants are the risen dead)
DAY = 24 * 60
WARN = 120  # (minutes before control ends that the game warns)
# Marks kept on a character until lifted (rules/health leaves "kept:" effects alone): the mummy's rot (the minute it
# took hold), the hit points it allows, the maximum it has taken and the days counted; dust (no body to raise).
ROT, ROT_HP, ROT_LOST, ROT_DAYS, DUST = "kept:mummy_rot", "kept:rot_hp", "kept:rot_lost", "kept:rot_days", "kept:dust"


def records(char, make: bool = False) -> list[dict]:
    """The master's servants (the list itself). Only `make` writes the key: an empty one would make anyone look like a
    caster to the code that reads `char.spells` as "has magic"."""
    if char is None:
        return []
    rows = char.spells.get("servants")
    if isinstance(rows, list):
        return rows
    if not make:
        return []
    rows = char.spells["servants"] = []
    return rows


def of_spell(char, spell: str) -> list[dict]:
    return [r for r in records(char) if r.get("spell") == spell]


def room(char) -> int:
    return max(0, MAX - len(records(char)))


def avg_hp(tables, cid: str) -> int:
    """A creature's average hit points (the stat block's number): a raised body starts whole."""
    from realmwalker.core import dice

    n, s, flat = dice.parse(str(tables.creatures[cid]["hp"]))
    return max(1, int(n * (s + 1) / 2 + flat))


def add(char, tables, cid: str, spell: str, *, until: float | None, now: float, word: bool = True,
        name: str = "", hp: int | None = None, max_hp: int | None = None, **more) -> dict | None:
    """A new servant for `char` (None when twelve already serve). `more`: a bound creature's form, level, picture,
    heals, bound."""
    if len(records(char)) >= MAX:
        return None
    rows = records(char, make=True)
    top = int(max_hp) if max_hp else avg_hp(tables, cid)
    rec = {"id": max([0] + [int(r.get("id", 0)) for r in rows]) + 1, "cid": cid,
           "name": name or tables.creatures[cid]["name"], "hp": top if hp is None else max(1, min(int(hp), top)),
           "max_hp": top, "spell": spell, "word": bool(word), "reach": int(REACH.get(spell, 60)),
           "until": None if until is None else float(until), "made": float(now), "warned": False, **more}
    rows.append(rec)
    return rec


def hold(char, spell: str, count: int, until: float) -> list[dict]:
    """The spell cast again on its own creatures: up to `count` of them (those whose hold ends soonest first) obey
    until `until`. Returns those held."""
    rows = sorted([r for r in of_spell(char, spell) if r.get("until") is not None], key=lambda r: r["until"])
    held = rows[:max(0, int(count))]
    for r in held:
        r["until"] = max(float(r["until"]), float(until))
        r["warned"] = False
    return held


def due(char, now: float) -> list[dict]:
    """Servants whose hold has ended."""
    return [r for r in records(char) if r.get("until") is not None and float(r["until"]) <= now]


def soon(char, now: float) -> list[dict]:
    """Servants whose hold ends within two hours, not warned yet."""
    return [r for r in records(char) if r.get("until") is not None and not r.get("warned")
            and now < float(r["until"]) <= now + WARN]


def drop(char, rec: dict) -> None:
    rows = records(char)
    if rec in rows:
        rows.remove(rec)
    if not rows and "servants" in char.spells:
        del char.spells["servants"]  # (none left: no empty key behind)


def is_undead(rec: dict) -> bool:
    return rec.get("spell") in UNDEAD


def creature_of(rec: dict, uid: int) -> Creature:
    hp = max(1, min(int(rec.get("hp", 1)), int(rec.get("max_hp", 1))))
    c = Creature(uid=uid, def_id=rec["cid"], name=rec.get("name") or rec["cid"], hp=hp, max_hp=int(rec["max_hp"]),
                 named=False)
    c.uses = dict(rec.get("uses") or {})
    return c


def spirit_def(tables, rec: dict, owner_char) -> dict | None:
    """A spirit's numbers for its slot and its master (Planar Ally: F.3's spirits), or None for a creature that is
    its own stat block."""
    if not rec.get("form") or "summon" not in tables.creatures[rec["cid"]]:
        return None
    from realmwalker.rules import allies

    attack, dc = allies.caster_numbers(owner_char, tables)
    cdef = allies.summon_def(tables, rec["cid"], int(rec.get("level", 0)), rec["form"], attack, dc)
    cdef["name"] = rec.get("name") or cdef["name"]
    return cdef


def spirit_max_hp(tables, cid: str, form: str, level: int) -> int:
    from realmwalker.rules import allies

    return int(allies.summon_def(tables, cid, level, form, 0, 10)["hp"])


def rest(char) -> None:
    """A long rest: the bound that heal are whole again, and their own magic comes back (the dead never heal)."""
    for rec in records(char):
        if rec.get("heals"):
            rec["hp"] = int(rec.get("max_hp", rec.get("hp", 1)))
            rec["uses"] = {}


def bring_in(b, owners: list, only: str | None = None) -> list:
    """Every servant of each master comes into the fight beside them (`only`: those of that spell). Returns the new
    fighters."""
    out = []
    for owner in owners:
        if owner.char is None or not owner.char.alive:
            continue
        for rec in records(owner.char):
            if int(rec.get("hp", 0)) <= 0 or rec.get("cid") not in b.t.creatures:
                continue
            if only is not None and rec.get("spell") != only:
                continue
            cr = creature_of(rec, UID + owner.id * 100 + int(rec["id"]))
            cdef = spirit_def(b.t, rec, owner.char)
            f = b.add_ally(cr, owner, "servant", spell=rec.get("spell", ""), level=int(rec.get("level", 0)),
                           type_=rec.get("type") or b.t.creatures[rec["cid"]]["kind"], cdef=cdef)
            if rec.get("picture"):
                f.bond["picture"] = rec["picture"]
            f.bond["word"] = bool(rec.get("word"))
            f.bond["reach"] = int(rec.get("reach", 60))
            f.bond["rid"] = int(rec["id"])
            out.append(f)
    return out


def after(b, now: float) -> list[str]:
    """What became of each servant, written back on its master: hit points kept, the destroyed struck off; a zombie
    Finger of Death raised for a party member serves on (for ever). Returns lines for the log."""
    out = []
    for f in b.fighters:
        if f.bond is None or f.bond.get("kind") != "servant" or f.creature is None:
            continue
        owner = b.fighter(f.bond["owner"])
        if owner is None or owner.char is None:
            continue  # (a foe's zombie goes with the fight)
        rid = f.bond.get("rid")
        rec = next((r for r in records(owner.char) if r.get("id") == rid), None) if rid is not None else None
        lost = f.state == "dead" or f.hp <= 0
        if rec is not None:
            if lost:
                drop(owner.char, rec)
            else:
                rec["hp"] = int(f.hp)
                if f.creature.uses:
                    rec["uses"] = dict(f.creature.uses)
            continue
        if lost or not f.bond.get("keep") or not owner.char.alive:
            continue
        new = add(owner.char, b.t, f.creature.def_id, f.bond.get("spell", ""), until=None, now=now, word=False,
                  hp=f.hp)
        if new is not None:
            first = owner.char.name.split()[0]
            out.append(f"The {new['name']} that rose in the fight shambles after {first}, waiting on {first}'s word.")
    return out
