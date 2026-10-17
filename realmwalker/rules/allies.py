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


# ---------------------------------------------------------------------------- summoned spirits (Expansion 3 F.2)
SUMMON_UID = 91000  # (spirits made for a fight: out of the way of any band's numbers and of familiars and steeds)


def summon_def(tables, cid: str, level: int, form: str, attack: int, dc: int) -> dict:
    """A summoned creature's numbers for its slot, form and caster (PHB 2024: "use the spell slot's level for the
    spell's level in the stat block"): its `summon` record in the creature data says the spell's own level, AC and
    hit points (and per level above), and what each form changes; attacks marked `plus_level` add the slot level
    to their damage and use the caster's spell attack; the Multiattack is half the slot level (round down) of the
    form's attacks; its own magic uses the caster's spell save DC."""
    from realmwalker.core import dice

    d = copy.deepcopy(tables.creatures[cid])
    s = d["summon"]
    base = int(s["level"])
    level = max(base, int(level))
    fm = s.get("forms", {}).get(form) or {}
    d["form"] = form
    d["name"] = fm.get("name", d["name"])
    d["ac"] = int(s["ac"]) + level + int(fm.get("ac", 0))
    d["hp"] = str(int(fm.get("hp", s["hp"])) + int(s.get("hp_up", 0)) * (level - base))
    d["speeds"] = {**d.get("speeds", {}), **fm.get("speeds", {})}
    d["speed"] = int(d["speeds"].get("walk", d.get("speed", 0)))
    keep = fm.get("attacks")
    out = []
    for a in d["attacks"]:
        if keep is not None and a["id"] not in keep:
            continue
        a = dict(a)
        a["bonus"] = int(attack)
        if a.get("save"):
            a["dc"] = int(dc)  # (a draconic spirit's breath: the caster's spell save DC)
        if a.get("plus_level"):
            n, sides, flat = dice.parse(str(a["damage"]))
            a["damage"] = f"{n}d{sides}+{flat + level}" if n else str(flat + level)
        if fm.get("damage_type"):
            a["damage_type"] = fm["damage_type"]  # (an elemental's Slam: cold, lightning, fire or bludgeoning)
        if a["id"] in fm.get("attack_types", {}):
            a["damage_type"] = fm["attack_types"][a["id"]]  # (a draconic spirit's breath: its chosen type)
        out.append(a)
    d["attacks"] = out
    # (the Multiattack's attacks; a breath made with them, `with_multiattack`, is not one of them)
    ids = list(dict.fromkeys(a["id"] for a in out if not a.get("with_multiattack")))
    n = level // 2 if s.get("multiattack", True) else 1
    d.pop("multiattack", None)
    d.pop("multiattack_plan", None)
    if n > 1 and ids:
        d["multiattack"] = n
        d["multiattack_plan"] = [list(ids) for _ in range(n)]
    d["traits"] = list(dict.fromkeys(list(d.get("traits", [])) + list(fm.get("traits", []))))
    for key in ("resist", "immune", "condition_immune"):
        d[key] = list(dict.fromkeys(list(d.get(key, [])) + list(fm.get(key, []))))
    own = list(fm.get("spells", []))
    per_day = {str(n): list(sids) for n, sids in {**s.get("per_day", {}), **fm.get("per_day", {})}.items()}
    d["spellcasting"] = {"ability": "int", "dc": int(dc), "attack": int(attack), "at_will": own, "per_day": per_day,
                         "slots": []}
    d["spells"] = own + [sid for sids in per_day.values() for sid in sids if sid not in own]
    if fm.get("shared"):
        d["resist"] = list(dict.fromkeys(list(d.get("resist", [])) + [fm["shared"]]))
    return d


def _foes_of(b, owner) -> list:
    return [e for e in b.enemies_of(owner) if e.active]


def form_scores(b, owner, cid: str) -> dict[str, float]:
    """How well each form suits this fight (`best_form` takes the best): a flier when foes are aloft or fly, a
    ranged form when they stand far off, the element whose blow hurts them most, a water form only where there is
    deep water."""
    from realmwalker.rules.engine import query

    s = b.t.creatures[cid]["summon"]
    foes = _foes_of(b, owner)
    if not s.get("forms"):
        return {"": 1.0}  # (no forms: an animated object's sizes are chosen by object_sizes)
    aloft = any(e.z > 0 or e.fly_speed > 0 for e in foes)
    near = min((b.gap(owner, e) for e in foes), default=0)
    wet = float(b.field.swim.mean()) if hasattr(b.field, "swim") else 0.0
    out = {}
    for form, fm in s.get("forms", {}).items():
        score = float(fm.get("weight", 1.0))
        likes = fm.get("likes", [])
        if "aloft" in likes and aloft:
            score += 3.0
        if "far" in likes and near > 6:
            score += 2.0
        if "many" in likes and len(foes) >= 3:
            score += 1.5
        if "brawl" in likes and _brawl(b, owner, foes):
            score += 1.5  # (a celestial Defender: friends already trading blows with the foes)
        if "water" in likes:
            score += 3.0 if wet > 0.3 else -10.0
        dtype = fm.get("damage_type") or next(iter(fm.get("attack_types", {}).values()), None)
        if dtype and foes:
            hurt = sum(query.damage_taken(e, 10, dtype)[0] for e in foes) / (10.0 * len(foes))
            score += 2.0 * hurt
        out[form] = score
    return out


def _brawl(b, owner, foes: list) -> bool:
    return any(b.gap(x, e) <= 1 for x in b.allies_of(owner) if x.active for e in foes)


def best_form(b, owner, cid: str) -> str:
    scores = form_scores(b, owner, cid)
    return max(scores, key=lambda k: scores[k])  # (ties: the first written)


def summon_spirit(b, owner, cid: str, level: int, point=None, sid: str = "", form: str = ""):
    """A summoning spell cast in a fight (Summon Beast... Giant Insect): the creature appears at the point (the
    nearest free squares to it), in the form that suits the fight, its numbers for the slot; it fights on its
    caster's side right after the caster's turn and goes when the spell ends (Battle._end_concentration) or at 0
    hit points. Returns the fighter."""
    form = form or best_form(b, owner, cid)
    attack, dc, _mod = caster_attack_dc(b, owner)
    cdef = summon_def(b.t, cid, level, form, attack, dc)
    hp = int(cdef["hp"])  # (a summoned creature's hit points are a number, not dice)
    uid = max([SUMMON_UID] + [x.creature.uid + 1 for x in b.fighters if x.creature is not None])
    cr = Creature(uid=uid, def_id=cid, name=cdef["name"], hp=hp, max_hp=hp, named=False)
    f = b.add_ally(cr, owner, "summon", spell=sid, level=max(int(cdef["summon"]["level"]), int(level)),
                   type_=cdef.get("kind", ""), cdef=cdef, point=point)
    f.bond["conc"] = True
    f.bond["form"] = form
    fm = cdef["summon"].get("forms", {}).get(form, {})
    if fm.get("picture"):
        f.bond["picture"] = fm["picture"]
    b.say(f"{a_or_an(cdef['name']).capitalize()} answers the call.", "magic")
    if fm.get("shared"):  # (Shared Resistances: its caster resists its breath while the spell holds)
        from realmwalker.rules.engine import durations

        durations.buff(owner, {"resist": [fm["shared"]], "conc": owner.id, "source": f"shared_resistance:{f.id}"})
        b.say(f"The spirit's {fm['shared']} settles over {owner.the_name} like a cloak.", "magic")
    return f


def caster_attack_dc(b, owner) -> tuple[int, int, int]:
    """The spell attack, save DC and spellcasting modifier of whoever summons."""
    if owner.char is not None:
        from realmwalker.rules import spells as spellrules
        from realmwalker.rules.character import Sheet

        attack, dc = caster_numbers(owner.char, b.t)
        return attack, dc, Sheet(owner.char, b.t).mod(spellrules.casting_ability(owner.char, b.t))
    sc = owner.cdef.get("spellcasting") or {}
    return int(sc.get("attack", 5)), int(sc.get("dc", 13)), owner.mod(sc.get("ability", "int"))


# ---------------------------------------------------------------------------- Animate Objects (Expansion 3 F.3)
OBJECT_SIZES = ("medium", "large", "huge")
OBJECT_COUNT = {"medium": 1, "large": 2, "huge": 3}


def object_sizes(b, owner, budget: int) -> list[str]:
    """The things the game wakes for a budget of the caster's spellcasting modifier (a Large one counts two, a Huge
    one three): a Huge one against a single great foe, else Large ones in pairs, a Medium one for what is left."""
    foes = _foes_of(b, owner)
    out = []
    left = max(1, int(budget))
    big = len(foes) == 1 and (foes[0].sq >= 2 or foes[0].hp >= 60)
    while left >= 3 and big:
        out.append("huge")
        left -= 3
    while left >= 2:
        out.append("large")
        left -= 2
    return out + ["medium"] * left


def object_def(tables, size: str, level: int, attack: int, mod: int, inside: bool) -> dict:
    """An animated object's numbers (PHB 2024): its size's hit points and Slam (force; the caster's spell attack;
    Large and Huge add the spellcasting modifier), one more die of its size for each slot above 5; what it is follows
    the place (a chest, a table, a statue under a roof; a stone, a log, a boulder outside)."""
    from realmwalker.core import dice

    d = copy.deepcopy(tables.creatures["animated_object"])
    s = d["summon"]
    z = s["sizes"][size]
    up = max(0, int(level) - int(s["level"]))
    look = z["in" if inside else "out"]
    d["name"] = look["name"]
    d["size"] = size
    d["form"] = size
    d["hp"] = str(int(z["hp"]))
    n, sides, flat = dice.parse(z["damage"])
    un, _us, _ = dice.parse(z["up"])
    n += un * up
    flat += int(mod) if z.get("mod") else 0
    out = []
    for a in d["attacks"]:
        a = dict(a)
        a["bonus"] = int(attack)
        a["damage"] = f"{n}d{sides}" + (f"+{flat}" if flat > 0 else (str(flat) if flat < 0 else ""))
        out.append(a)
    d["attacks"] = out
    d.pop("multiattack", None)
    d.pop("multiattack_plan", None)
    d["spellcasting"] = {"ability": "int", "dc": 10, "attack": int(attack), "at_will": [], "per_day": {}, "slots": []}
    d["spells"] = []
    d["picture"] = look["picture"]
    return d


def indoors(b) -> bool:
    """Under a roof or underground (what lies about there is furniture, not stones)."""
    return getattr(b.env, "place", "") in ("indoors", "underground", "building", "dungeon", "town")


def animate_objects(b, owner, level: int, point=None, sid: str = "") -> list:
    """Animate Objects cast in a fight: as many things as the caster's spellcasting modifier wake at the point (the
    nearest free squares to it), each a Fighter on the caster's side with `bond` kind "objects"; they act right after
    the caster, only when commanded (`Battle.command_objects`), and go when the concentration ends or at 0."""
    attack, _dc, mod = caster_attack_dc(b, owner)
    inside = indoors(b)
    made = []
    for size in object_sizes(b, owner, mod):
        cdef = object_def(b.t, size, level, attack, mod, inside)
        hp = int(cdef["hp"])
        uid = max([SUMMON_UID] + [x.creature.uid + 1 for x in b.fighters if x.creature is not None])
        cr = Creature(uid=uid, def_id="animated_object", name=cdef["name"], hp=hp, max_hp=hp, named=False)
        f = b.add_ally(cr, owner, "objects", spell=sid, level=max(5, int(level)), type_="construct", cdef=cdef,
                       point=point)
        f.bond["conc"] = True
        f.bond["form"] = size
        f.bond["picture"] = cdef["picture"]
        made.append(f)
    if made:
        n = len(made)
        what = "a thing" if n == 1 else f"{NUMBERS.get(n, str(n))} things"
        b.say(f"{what[:1].upper() + what[1:]} lying about {'shudders' if n == 1 else 'shudder'}, "
              f"{'sprouts' if n == 1 else 'sprout'} legs and {'rises' if n == 1 else 'rise'} for {owner.the_name}.",
              "magic")
    return made


NUMBERS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven"}


def a_or_an(words: str) -> str:
    return ("an " if words[:1].lower() in "aeiou" else "a ") + words
