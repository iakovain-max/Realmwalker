"""What an attack or a spell is worth, by the same numbers the player sees (docs/EXPANSIONS.md §4.3.7, §4.7).

    hit_chance(b, att, opt, target)     the chance an attack hits (advantage, disadvantage, cover)
    fail_chance(b, x, ability, dc)      the chance a creature fails a saving throw
    attack_value(b, att, opt, target)   expected damage of one attack, after resistances
    spell_value(b, f, sid, ...)         a spell's worth: damage to enemies and to friends, control, healing, help

Rough, quick and consistent: the battle screen's preview, the enemy's planner and the companions' Auto all ask here.
"""

from __future__ import annotations

from dataclasses import dataclass

from realmwalker.core import dice
from realmwalker.rules import grid, simulacrum
from realmwalker.rules import spells as spellrules
from realmwalker.rules.engine import query


def avg(expr: str) -> float:
    try:
        n, sides, flat = dice.parse(str(expr))
    except dice.DiceError:
        return 0.0
    return n * (sides + 1) / 2 + flat


def _p(need: int, mode: str) -> float:
    """The chance a d20 roll reaches `need` (2..20), with advantage or disadvantage."""
    need = max(2, min(20, need))
    p = (21 - need) / 20.0
    if mode == "advantage":
        return 1 - (1 - p) ** 2
    if mode == "disadvantage":
        return p * p
    return p


def hit_chance(b, att, opt, target) -> float:
    r = query.attack_roll(b, att, target, opt)
    ac, _ = b.target_ac(att, target, opt)
    return _p(ac - opt.bonus, r.mode)


_MEMO: dict | None = None  # (while a choice is weighed: see `thinking`)


class thinking:
    """While one choice of spell is weighed nothing on the field changes, so a save's chance and a resistance are
    worked out once for each creature (an enemy caster with a long list of spells: Expansion 3 G.1)."""

    def __enter__(self):
        global _MEMO
        self.outer = _MEMO
        if _MEMO is None:
            _MEMO = {}
        return self

    def __exit__(self, *exc):
        global _MEMO
        _MEMO = self.outer
        return False


def fail_chance(b, x, ability: str, dc: int) -> float:
    key = ("fail", id(x), ability, dc)
    if _MEMO is not None and key in _MEMO:
        return _MEMO[key]
    sr = query.save_roll(b, x, ability)
    if sr.auto_fail:
        out = 1.0
    else:
        bonus = sr.bonus + sum(avg(d) for d in sr.dice)
        out = 1.0 - _p(int(round(dc - bonus)), sr.roll.mode)
    if _MEMO is not None:
        _MEMO[key] = out
    return out


def damage_factor(x, dtype: str) -> float:
    """What resistance, vulnerability or immunity leaves of damage of this kind."""
    key = ("damage", id(x), dtype)
    if _MEMO is not None and key in _MEMO:
        return _MEMO[key]
    amount, _ = query.damage_taken(x, 100, dtype)
    if _MEMO is not None:
        _MEMO[key] = amount / 100.0
    return amount / 100.0


def attack_value(b, att, opt, target) -> float:
    """Expected damage of one attack on this target."""
    p = hit_chance(b, att, opt, target)
    dmg = avg(opt.damage) * damage_factor(target, opt.damage_type)
    dmg += sum(avg(e["damage"]) * damage_factor(target, e["type"]) for e in opt.extra.get("extra", ()) if not e.get("if"))
    return p * dmg


def threat(x) -> float:
    """How dangerous a creature is each round: what it could deal (a rough measure for choosing whom to stop)."""
    if x.char is not None:
        return 4.0 + 1.5 * x.char.level
    best = max((avg(a.get("damage", "0")) for a in x.cdef.get("attacks", [])), default=2.0)
    return best * max(1, int(x.cdef.get("multiattack", 1)))


# What freeing a friend of a condition is worth, in rounds of its threat (Lesser and Greater Restoration: G.1).
RESTORED = {"paralyzed": 2.5, "petrified": 3.0, "stunned": 2.0, "charmed": 1.5, "blinded": 1.0, "poisoned": 0.6,
            "deafened": 0.2}


def casts_spells(b, x) -> bool:
    """A fighter that casts spells: a creature with spells on its stat block, or a character of a casting class (the
    party's casters count for the enemy's Silence and Circle of Power as the enemy's do for the Auto: Expansion 3
    G.1)."""
    if x.char is not None:
        return bool(b is not None and spellrules.is_caster(x.char, b.t) and x.char.spells)
    return bool(x.cdef is not None and x.cdef.get("spells"))


def weapon_blows(b, f, target=None) -> list:
    """The blows a fighter strikes with a weapon (True Strike, a smite): a character's weapons in hand, a creature's
    attacks with a weapon its stat block names (Expansion 3 G.1); in reach of `target` if one is given."""
    out = []
    for x in b.attack_options(f):
        if not x.available or x.kind not in ("melee", "ranged"):
            continue
        if x.item_uid is None and not (f.char is None and str(x.extra.get("item", "")) in b.t.items):
            continue
        if target is not None and not b.in_reach(f, x, target)[0]:
            continue
        out.append(x)
    return out


def blow_mod(b, f, opt) -> int:
    """The ability modifier already in a blow (a character's is kept on the option; a creature's is its Dexterity
    for a ranged or finesse weapon if that is better, else its Strength)."""
    if "ability_mod" in opt.extra:
        return int(opt.extra["ability_mod"])
    props = b.t.items.get(str(opt.extra.get("item", ""))).get("properties", []) \
        if str(opt.extra.get("item", "")) in b.t.items else []
    if opt.kind == "ranged":
        return f.mod("dex")
    return max(f.mod("str"), f.mod("dex")) if "finesse" in props else f.mod("str")



def mends(x) -> int:
    """The hit points healing could give back: none to a Simulacrum, which only its maker's repair mends (G.3)."""
    return 0 if simulacrum.snow(x) else max(0, x.max_hp - x.hp)

@dataclass
class Worth:
    damage: float = 0.0  # expected damage to enemies
    friendly: float = 0.0  # expected damage to friends (an area that catches them)
    control: float = 0.0  # expected damage prevented by stopping someone (paralysed, asleep, grovelling)
    heal: float = 0.0  # hit points given where they are missing
    help: float = 0.0  # the worth of a buff or a summoned thing
    kills: int = 0  # enemies it would likely finish

    def total(self, *, care: float = 1.0) -> float:
        return self.damage + self.control + self.heal + self.help + 3.0 * self.kills - care * self.friendly


def spell_value(b, f, sid: str, *, target=None, point=None, dc: int | None = None, bonus: int | None = None,
                level: int | None = None, up: int = 0) -> Worth:
    """What casting this spell here would do, in expected numbers (`up`: cast that many slot levels higher)."""
    from realmwalker.rules.combat import AttackOption, spell_id

    spell = b.t.spells[spell_id(sid)]
    w = Worth()
    if str(sid).startswith("scroll:") and dc is None:  # (a scroll casts with its own numbers)
        dc, bonus = spellrules.scroll_numbers(b.t, spell["level"])
    dc = dc if dc is not None else _caster_dc(b, f)
    bonus = bonus if bonus is not None else _caster_attack(b, f)
    mult = spellrules.cantrip_multiplier(f.char.level) if f.char is not None else 1
    from realmwalker.rules.engine import effects

    lvl = int(level if level is not None else spell["level"] + up)
    if target is not None and target is not f and effects.warded(b, f, target, lvl):
        return w  # (Globe of Invulnerability: it would break on the barrier)
    several = target is not None and (int(spell.get("targets", 1)) > 1 or spell.get("leap"))
    if spell.get("area"):
        cells = b.spell_area(f, sid, point, target)
        caught = [x for x in b.in_area(cells, spell.get("affects", "all"), f) if not effects.warded(b, f, x, lvl)]
    elif spell["target"] == "all_allies":
        reach = b.spell_range(spell, f)
        caught = [x for x in b.team(f.team) if (x.active or x.state == "down") and b.feet(f, x) <= reach]
    elif several:
        caught = effects.many(b, f, spell_id(sid), spell, target, up, level=lvl)
    else:
        caught = [target] if target is not None else ([f] if spell["target"] == "self" else [])
    for o in spell.get("effects", ()):
        kind = o["op"]
        if kind == "revive" and target is not None and target.state == "dead" and target.team == f.team \
                and not target.__dict__.get("dust"):
            w.heal += 8.0 + 3.0 * threat(target)  # (a friend back on its feet: Revivify in a fight, G.1)
            continue
        if kind == "restore" and target is not None and target.team == f.team and target.active:
            for cid in o.get("conditions", ()):  # (a friend freed of what holds it, the worst first: G.1)
                if cid in target.conditions:
                    w.heal += threat(target) * RESTORED.get(cid, 0.5)
                    if o.get("one"):
                        break
            continue
        if kind == "attack" and target is not None:
            o = _typed(o, [target], f)
            for d, t, more in spellrules.damage_parts(o)[:1]:
                expr = spellrules.scaled(_scaled(d, mult if o.get("scaling") == "cantrip" else 1), more, up)
                opt = AttackOption("spell", spell["name"], "spell_ranged" if o["attack"] != "melee" else "spell_melee",
                                   bonus, expr, t)
                rays = int(o.get("rays", 1)) * (mult if o.get("rays_scaling") else 1) + int(o.get("rays_up", 0)) * up
                if o.get("spread"):  # (one blow for each foe in reach)
                    rays = min(rays, max(1, len([e for e in b.enemies_of(f)
                                                 if b.feet(f, e) <= b.spell_range(spell, f)])))
                p = hit_chance(b, f, opt, target)
                ev = attack_value(b, f, opt, target) * rays
                if o.get("miss_half"):
                    ev += (1 - p) * avg(expr) * 0.5 * damage_factor(target, t) * rays
                ev += p * rays * _marks_worth(b, f, target, o.get("on_hit", ()), up)
                w.damage += ev
                w.kills += int(ev >= target.hp)
            if not spellrules.damage_parts(o):  # (a touch that only carries the spell: Plane Shift)
                opt = AttackOption("spell", spell["name"], "spell_ranged" if o["attack"] != "melee" else "spell_melee",
                                   bonus, "0", "force")
                p = hit_chance(b, f, opt, target)
                for inner in o.get("on_hit", ()):
                    if inner["op"] == "save":
                        part = Worth()
                        _save_part(b, f, inner, [target], target, dc, up, mult, part)
                        w.damage += p * part.damage
                        w.control += p * part.control
                        w.friendly += p * part.friendly
                        w.kills += int(p * part.kills >= 0.5)
            for a in o.get("after", ()):
                if a["op"] == "save":
                    _save_part(b, f, a, [target], target, dc, up, mult, w)
        elif kind == "darts" and target is not None:
            d, t, more = spellrules.damage_parts(o)[0]
            ev = avg(spellrules.scaled(d, more, up)) * (int(o.get("count", 1)) + int(o.get("count_up", 0)) * up) \
                * damage_factor(target, t)
            w.damage += ev
            w.kills += int(ev >= target.hp)
        elif kind == "save":
            _save_part(b, f, o, caught, target, dc, up, mult, w)
        elif kind == "heal" and (o.get("full") or o.get("pool")):
            pool = float(o["pool"]) if o.get("pool") else None
            whom = caught
            if pool is not None and spell["target"] == "all_allies":
                reach = b.spell_range(spell, f)
                whom = [x for x in b.team(f.team) if (x.active or x.state == "down") and b.feet(f, x) <= reach]
            for x in sorted(whom, key=lambda x: x.hp / max(1, x.max_hp)):
                missing = mends(x)
                got = missing if pool is None else min(missing, pool)
                if pool is not None:
                    pool -= got
                w.heal += got + (10.0 if x.state == "down" and got > 0 else 0.0)
                w.heal += 2.0 * sum(1 for cid in o.get("restore", ()) if cid in x.conditions and cid != "prone")
        elif kind == "heal":
            many = max(1, int(o.get("count", 1)) + int(o.get("count_up", 0)) * up)
            for x in sorted(caught, key=lambda x: x.hp / max(1, x.max_hp))[:many]:
                missing = mends(x)
                if missing > 0:
                    w.heal += min(missing, avg(spellrules.scaled(o["dice"], o.get("up", ""), up))
                                  + (_caster_mod(b, f) if o.get("add_mod") else 0) + int(o.get("per_up", 0)) * up)
                    if x.state == "down":
                        w.heal += 10.0  # up again
        elif kind == "modifier":
            n = int(o.get("count", 1)) + int(o.get("count_up", 0)) * up
            if spell["target"] not in ("self", "all_allies"):
                n = max(n, int(spell.get("targets", 1)) + int(spell.get("targets_up", 0)) * up)
            on = target if target is not None else f
            if on is not None and any(bf.get("source") == spell_id(sid) or bf.get("lasting") == spell_id(sid)
                                      for bf in on.buffs):
                continue  # (already on them: casting it again buys nothing)
            if on is not None and on.team != f.team:
                w.control += _mark_on_foe(b, f, on, o.get("buff", {}))  # (Hex, Faerie Fire on a foe)
            else:
                w.help += _buff_worth(spellrules.buff_at(o, spell["level"] + up, spell), n, b, f, on, spell)
        elif kind == "weapon_attack" and target is not None:
            opts = weapon_blows(b, f, target)
            if opts:
                am = blow_mod(b, f, opts[0])
                spell_mod = _caster_mod(b, f)
                ev = attack_value(b, f, opts[0], target) * (1.0 + 0.1 * max(0, spell_mod - am))
                ev += hit_chance(b, f, opts[0], target) * (spell_mod - am + 3.5 * max(0, mult - 1))
                w.damage += max(0.0, ev)
                w.kills += int(ev >= target.hp)
        elif kind == "temp_hp" and o.get("share") and spell["target"] == "all_allies":
            amount = avg(str(o["amount"])) + int(o.get("per_up", 0)) * up
            for x, each in effects.shares(b, f, spell, int(amount), int(o.get("count", 6)), level=lvl):
                gain = max(0.0, each - x.temp_hp)
                w.help += gain * (0.6 if any(b.gap(x, e) <= 6 for e in b.enemies_of(f)) else 0.2)
        elif kind == "max_up":  # (Aid: hit points now, and a higher maximum that outlives the fight)
            amount = spellrules.max_up_amount(spell, lvl)
            n = int(o.get("count", 3)) + int(o.get("count_up", 0)) * up
            whom = sorted(caught if caught else [f], key=lambda x: (x is not f, x.hp / max(1, x.max_hp)))[:n]
            for x in whom:
                if x.char is None and x.creature is None:
                    continue
                had = x.char.effects if x.char is not None else x.creature.uses  # (a creature's: G.1)
                gain = max(0, amount - int(had.get(spellrules.MAX_UP + spell_id(sid), 0)))
                near = any(b.gap(x, e) <= 6 for e in b.enemies_of(f))
                w.help += gain * (0.6 if near else 0.3) + (10.0 if x.state == "down" and gain else 0.0)
        elif kind == "temp_hp" and (caught or spell["target"] == "self"):
            x = caught[0] if spell["target"] != "self" else f
            amount = avg(str(o["amount"])) + int(o.get("per_up", 0)) * up
            w.help += max(0.0, amount - x.temp_hp) * (0.6 if any(b.gap(x, e) <= 6 for e in b.enemies_of(f)) else 0.2)
        elif kind == "move_zone" and point is not None:
            w.damage += _moved_zone_worth(b, f, spell, point)
        elif kind == "ally" and o.get("kind") == "summon":  # (a summoned spirit: its blows for three rounds, its body)
            w.help += _summon_worth(b, f, o["creature"], lvl, bonus, dc, point)
        elif kind == "ally" and o.get("kind") == "objects":  # (Animate Objects: the things it would wake)
            w.help += _objects_worth(b, f, lvl, point)
        elif kind == "ally":  # (Find Steed: a fighter more on the field, unless one stands there already)
            if not any(x.bond.get("kind") == o.get("kind", "steed") and x.active for x in b.allies_of_owner(f)):
                w.help += (4.5 + lvl) * 0.55 * 3 + (5 + 10 * lvl) * 0.3
        elif kind in ("summon", "aura", "guardian"):
            d, t, more = spellrules.damage_parts(o)[0] if spellrules.damage_parts(o) else ("0", "", "")
            w.help += avg(spellrules.scaled(d, more, up)) * 0.55 * 3
            if o.get("on_hit"):
                w.help += 2.0  # (Conjure Fey's fear)
        elif kind == "by_hp" and target is not None and target.team != f.team:  # (Power Word Stun, Power Word Kill)
            fail = _resolve([o], target)
            if not _already(b, f, target, fail):
                w.control += threat(target) * _control_rounds(fail)
                w.damage += _marks_worth(b, f, target, fail, up)
            if any(i["op"] == "slay" for i in fail):
                w.kills += 1
        elif kind == "banish" and target is not None and not spell.get("area") and target.team != f.team:
            esc = o.get("escape") or {}
            if esc:  # (Maze: away until it finds the way out, a check each turn)
                bonus = target.skill(esc.get("skill", "investigation")) if hasattr(target, "skill") else 0
                p_out = max(0.05, min(1.0, (21 - (int(esc.get("dc", 20)) - bonus)) / 20.0))
                w.control += threat(target) * min(4.0, 1.0 / p_out)
            else:
                w.control += 3.0 * threat(target)
        elif kind == "shape" and spell["target"] == "all_allies":  # (Animal Shapes: the willing, F.8)
            w.control += sum(_shape_worth(b, f, o, x, dc) for x in effects.willing(b, f, spell))
        elif kind == "shape" and (target is not None or spell["target"] == "self"):  # (Polymorph: F.6)
            w.control += _shape_worth(b, f, o, target if target is not None else f, dc)
        elif kind == "time_stop":  # (Time Stop: turns of one's own, to heal, ward and set the field)
            hurt = f.hp < f.max_hp * 0.6
            near = any(b.gap(f, e) <= 2 for e in b.enemies_of(f) if e.standing)
            w.help += avg(str(o.get("dice", "1d4+1"))) * (3.0 if hurt or near else 1.5)
        elif kind == "zone" and o.get("follow") and o.get("zone") == "antimagic":
            w.control += _antimagic_worth(b, f, spell)
        elif kind == "zone" and o.get("stages") and caught:  # (Storm of Vengeance: the turns of the storm to come)
            _zone_worth(b, f, o, caught, dc, up, w)
            w.damage += _stages_worth(b, f, o, caught, dc)
        elif kind == "zone" and o.get("zone") in ("wind", "stone", "force", "icewall", "prismatic") and point is not None:
            w.control += _wall_worth(b, f, o, point)
            if o.get("near"):  # (Prismatic Wall: the glare beside it)
                cells = b.spell_area(f, sid, point, target)
                r = int(o["near"]) // 5
                for e in b.enemies_of(f):
                    if e.active and any(grid.gap((cx, cy, 1), e.space) <= r for cx, cy in cells):
                        pf = fail_chance(b, e, o.get("near_save", "con"), dc)
                        w.control += pf * threat(e) * 1.2
            if o.get("catch") and spellrules.damage_parts(o):  # (Wall of Ice: those it rises beside)
                _save_part(b, f, {**o, "ability": o.get("save", "dex")}, caught, target, dc, up, mult, w)
        elif kind == "banish" and spell.get("area"):  # (Forcecage: everyone in the box sealed away, no save)
            left_free = [e for e in b.enemies_of(f) if e.active and e not in caught]
            for x in caught:
                if x.team != f.team and not left_free:
                    continue  # (the last foes caged: nobody left to fight, the fight only waits for the hour)
                if x is f or not x.active:
                    continue
                if x.team == f.team:
                    w.friendly += 4.0 * threat(x)  # (a friend shut out of the fight for as long as it holds)
                else:
                    w.control += 3.0 * threat(x)
        elif kind == "one_of":  # (Prismatic Spray: each ray by its chance)
            n = len(o["choices"])
            die = int(o.get("die", n))
            share = (n + 2 * max(0, die - n)) / max(1, die) / max(1, n)
            for choice in o["choices"]:
                part = Worth()
                for inner in choice:
                    if inner["op"] == "save":
                        _save_part(b, f, inner, caught, target, dc, up, mult, part)
                w.damage += part.damage * share
                w.control += part.control * share
                w.friendly += part.friendly * share
                w.kills += int(part.kills * share + 0.5) if share * part.kills >= 0.5 else 0
        elif kind == "zone" and o.get("zone") == "illusion":
            if point is not None:  # (an image: the shooters and casters it blinds to the caster's side)
                w.control += image_worth(b, f, b.spell_area(f, sid, point, target))
        elif kind == "zone" and caught:
            _zone_worth(b, f, o, caught, dc, up, w)
        elif kind == "dispel":
            w.control += _dispel_worth(b, f, target, point)
        elif kind == "condition" and o.get("condition") == "invisible" and spell["target"] in ("ally", "self"):
            on = target if target is not None else f
            if on is not None and "invisible" not in on.conditions:  # (Greater Invisibility: unseen, striking freely)
                near = any(b.gap(on, e) <= 6 for e in b.enemies_of(f))
                w.help += 5.0 if near else 1.5
        elif kind == "teleport" and point is not None:
            w.help += _escape_worth(b, f, point)
        elif kind == "undark":  # (Daylight: a foe's magical darkness burned away)
            mine = {x.id for x in b.team(f.team)}
            w.control += 2.0 * sum(1 for z in b.zones if z.kind == "darkness" and z.owner not in mine)
    if spell.get("again"):
        w.help += _again_worth(b, f, spell, up)
    if up and spell.get("targets_up") and target is not None and not several:  # (more of the same kind nearby)
        others = [x for x in (b.enemies_of(f) if target.team != f.team else b.team(f.team))
                  if x is not target and x.active and b.feet(f, x) <= max(5, b.spell_range(spell, f))]
        extra = min(len(others), int(spell["targets_up"]) * up)
        if extra:
            w.damage, w.control, w.kills = (w.damage * (1 + 0.8 * extra), w.control * (1 + 0.8 * extra),
                                            w.kills * (1 + extra))
    return w


def _shape_worth(b, f, o: dict, target, dc: int) -> float:
    """Polymorph's worth: a foe's threat taken away for as long as its form lasts (times the chance it fails its
    save); a friend made stronger than it is (the form's blows and temporary hit points over its own), less what a
    friend stronger than the form gives up (Animal Shapes on a seasoned fighter: Expansion 3 F.8)."""
    from realmwalker.rules import shapes

    if not shapes.shapeable(target):
        return 0.0
    kinds = o.get("forms", ["beast"])
    if target.team != f.team:
        cid = shapes.worst(b.t, target, kinds, o)
        if cid is None:
            return 0.0
        left = threat(target) * max(0.0, 1.0 - shapes.strength(b.t, cid) / max(1.0, 3.0 * threat(target) + 40.0))
        return 3.0 * left * fail_chance(b, target, "wis", dc)
    cid = shapes.best(b.t, target, kinds, o)
    if cid is None:
        return 0.0
    form = b.t.creatures[cid]
    own = 3.0 * threat(target) + 40
    strength = shapes.strength(b.t, cid)
    gain = shapes.form_hp(b.t, cid) / 10.0 + max(0.0, strength - own) / 20.0 - max(0.0, own - strength) / 20.0
    keeps = "spells" in (o.get("keeps") or ())
    casts = casts_spells(b, target) and not keeps  # (a caster loses its spells while in the form)
    if casts and target is f:
        return 0.0  # (a caster would give up every spell it has to be a bear: the Auto never does)
    if gain <= 0:
        return 0.0
    near = any(b.gap(target, e) <= 2 for e in b.enemies_of(f) if e.standing)
    return gain * (1.5 if near else 1.0) * (0.3 if casts else 1.0) + (0.5 if form.get("speeds", {}).get("fly") else 0)


def _save_part(b, f, o: dict, caught: list, target, dc: int, up: int, mult: int, w: Worth) -> None:
    """A saving throw's worth, added to `w`: the damage (half on a save), the turns it takes away, the marks it
    leaves; `around` a creature, everyone that close (Ice Knife's burst)."""
    who = caught
    if o.get("around") and target is not None:
        n = int(o["around"]) // 5
        who = [x for x in b.fighters if (x.active or x.state == "down") and grid.gap(target.space, x.space) <= n
               and not (o.get("affects") == "enemies" and x.team == f.team)]
    o = _typed(o, who, f)
    for x in who:
        if x is None or not _allowed(o, x):
            continue
        pf = fail_chance(b, x, o["ability"], int(o.get("dc", dc)))
        if o.get("advantage"):
            pf *= pf
        parts = spellrules.damage_parts(o)
        if o.get("hurt_damage") and x.hp < x.max_hp and parts:
            parts = [(o["hurt_damage"], parts[0][1], parts[0][2])] + parts[1:]
        dmg = sum(avg(spellrules.scaled(_scaled(d, mult if o.get("scaling") == "cantrip" else 1), more, up))
                  * damage_factor(x, t) for d, t, more in parts)
        ev = dmg * (pf + (1 - pf) * (0.5 if o.get("half") else 0.0))
        if x.team == f.team:
            w.friendly += ev
            if o.get("on_fail"):  # (a friend held, lifted, charmed or sent away by it)
                fail = _resolve(o["on_fail"], x)
                w.friendly += pf * (threat(x) * _control_rounds(fail) + _marks_worth(b, f, x, fail, up))
        else:
            w.damage += ev
            w.kills += int(ev >= x.hp)
            if o.get("on_fail"):
                fail = _resolve(o["on_fail"], x)
                if not _already(b, f, x, fail):
                    w.control += pf * threat(x) * _control_rounds(fail)
                    w.damage += pf * _marks_worth(b, f, x, fail, up)
                if any(i["op"] == "slay" and (i.get("max_hp") is None or x.hp <= int(i["max_hp"])) for i in fail) \
                        or any(i["op"] == "banish" and i.get("forever") and _allowed(i, x) for i in fail):
                    w.kills += int(pf >= 0.4)
            if o.get("max_hp_loss"):
                w.damage += pf * dmg * 0.2  # (Harm: the healing it cannot come back to)
            if o.get("on_save"):
                w.damage += (1 - pf) * _marks_worth(b, f, x, o["on_save"], up)


def _scaled(expr: str, mult: int) -> str:
    n, sides, flat = dice.parse(expr)
    n *= mult
    return f"{n}d{sides}{'+' + str(flat) if flat > 0 else (str(flat) if flat < 0 else '')}" if n else str(flat)


def _allowed(o: dict, x) -> bool:
    return not (o.get("kinds") and x.kind not in o["kinds"] or o.get("not_kinds") and x.kind in o["not_kinds"])


def ability_value(b, f, a: dict) -> Worth:
    """What using an ability (data/traits.json "activate") would do now, in the same numbers as a spell: hit points
    brought back where they are missing, undead turned by their threat and the chance they fail."""
    w = Worth()
    for o in a.get("effects", ()):
        if o["op"] == "heal":
            add = o.get("add", 0)
            amount = avg(o["dice"]) + (f.char.level if add == "level" and f.char else add if isinstance(add, int) else 0)
            w.heal += min(amount, mends(f))
        elif o["op"] == "special" and o["handler"] in _ABILITY_WORTH:
            _ABILITY_WORTH[o["handler"]](b, f, w)
    return w


def _turn_undead(b, f, w: Worth) -> None:
    dc = _caster_dc(b, f)
    for x in b.enemies_of(f):
        if x.standing and x.kind == "undead" and b.feet(f, x) <= 30:
            w.control += fail_chance(b, x, "wis", dc) * threat(x) * 3.0  # it flees: a minute of its blows spared


def _preserve_life(b, f, w: Worth) -> None:
    pool = 5 * f.char.level  # (as the handler shares it: the worst off first, nobody past half)
    near = [x for x in b.team(f.team) if (x.active or x.state == "down") and b.feet(f, x) <= 30]
    for x in sorted(near, key=lambda x: x.hp / max(1, x.max_hp)):
        give = 0 if simulacrum.snow(x) else min(max(0, x.max_hp // 2 - x.hp), pool)
        pool -= give
        w.heal += give + (10.0 if give and x.state == "down" else 0.0)


def _battle_medic(b, f, w: Worth) -> None:
    near = [x for x in b.team(f.team) if x is not f and (x.active or x.state == "down") and b.gap(f, x) <= 1]
    if near:
        x = min(near, key=lambda x: x.hp / max(1, x.max_hp))
        die = (b.t.classes[x.char.cls]["hit_die"] if x.char is not None else 8) / 2 + 0.5
        w.heal += min(die + proficiency_of(f), mends(x)) + (10.0 if x.state == "down" and mends(x) else 0.0)


def proficiency_of(f) -> int:
    from realmwalker.rules.engine import query

    return query.proficiency(f)


def _speedy_recovery(b, f, w: Worth) -> None:
    die = (b.t.classes[f.char.cls]["hit_die"] if f.char is not None else 8) / 2 + 0.5
    w.heal += min(die, mends(f))


def _chef_treat(b, f, w: Worth) -> None:
    w.heal += max(0, proficiency_of(f) - f.temp_hp) * (1.0 if f.hp < f.max_hp else 0.3)


def _telekinetic_shove(b, f, w: Worth) -> None:
    w.control += 1.0  # (where to shove is the tactics' judgement: rules/tactics._mind_shove)


def _recover_vitality(b, f, w: Worth) -> None:
    left = f.char.uses.get("vitality_dice", 0) if f.char is not None else 0
    want = mends(f)
    w.heal += min(want, 5.5 * min(left, -(-want * 2 // 11)))


def _divine_spark_harm(b, f, w: Worth) -> None:
    from realmwalker.rules.engine.handlers import cleric

    n, sides, _ = dice.parse(cleric.spark_dice(f))
    w.damage += 0.75 * (n * (sides + 1) / 2 + f.mod("wis"))  # (a Constitution save halves it)


_ABILITY_WORTH = {"divine_spark_harm": _divine_spark_harm, "turn_undead": _turn_undead, "preserve_life": _preserve_life, "battle_medic": _battle_medic,
                  "speedy_recovery": _speedy_recovery, "chef_treat": _chef_treat,
                  "telekinetic_shove": _telekinetic_shove, "recover_vitality": _recover_vitality}


def _already(b, f, x, fail: list[dict]) -> bool:
    """A failed save would bring nothing new: the foe already has the condition or the mark (a second Mass
    Suggestion, Hold Person, Otto's dance on the same foe), or it is the last foe and banishing it only delays the
    fight (it would come back)."""
    from realmwalker.rules.combat import EXTRAPLANAR

    for o in fail:
        if o["op"] == "condition" and (o.get("condition") in x.conditions or o.get("petrify") and "petrified" in x.conditions):
            return True
        if o["op"] == "modifier":
            keys = [k for k in o.get("buff", {}) if k not in ("dc", "by", "up", "level", "mod", "source")]
            if keys and any(bf.get(k) for bf in x.buffs for k in keys):
                return True
        if o["op"] == "lift" and x.buff_value("aloft"):
            return True
        if o["op"] == "banish" and not o.get("forever") and o.get("how", "banished") == "banished" \
                and x.kind not in EXTRAPLANAR and len([e for e in b.enemies_of(f) if e.active]) <= 1:
            return True
    return False


def _resolve(ops: list[dict], x) -> list[dict]:
    """The ops a failed save would bring on this creature: Divine Word's band for its hit points, banishing only for
    the kinds it names."""
    out = []
    for o in ops:
        if o["op"] == "by_hp":
            tier = next((inner for most, inner in o["tiers"] if x.hp <= int(most)), [])
            out.extend(_resolve(tier, x))
        elif o["op"] == "banish" and not _allowed(o, x):
            continue
        else:
            out.append(o)
    return out


def _control_rounds(ops: list[dict]) -> float:
    """Roughly how many of the victim's rounds a failed save takes away."""
    for o in ops:
        if o["op"] == "slay":
            return 0.0  # (counted as its death: _save_part)
        if o["op"] == "banish" and o.get("forever"):
            return 6.0  # (gone for good)
        if o["op"] == "banish":
            return 3.0  # (out of the fight while the spell holds, and perhaps for good)
        if o["op"] == "lift":
            return 1.5  # (hanging in the air, out of reach of blades)
        if o["op"] == "condition" and o.get("petrify"):
            return 1.4  # (held fast, and perhaps turned to stone)
        if o["op"] == "condition" and o.get("control"):
            return 3.5  # (its turns lost to its friends, and spent against them)
        if o["op"] == "condition" and o.get("terror"):
            return 2.0  # (a Mace of Terror: its turns spent running away, no blows, until it shakes the fright off)
        if o["op"] == "condition" and o["condition"] in ("paralyzed", "stunned", "unconscious", "incapacitated"):
            return 2.5  # its turns lost, and every blow at it with advantage (and from beside it, a critical)
        if o["op"] == "lose_turn":
            return 1.0
        if o["op"] == "condition" and o["condition"] in ("restrained", "prone", "frightened", "blinded"):
            return 0.4
        if o["op"] == "condition" and o["condition"] == "charmed":
            return 0.3  # (it will not strike the one who charmed it)
        if o["op"] == "condition" and o["condition"] == "poisoned":
            return 0.3  # (its attacks and checks at a disadvantage: a centipede's spew)
    return 0.0


def _wall_worth(b, f, o: dict, point) -> float:
    """A wall raised near the foes (Wind Wall against archers; stone and force against everyone who must go round)."""
    out = 0.0
    friends = [x for x in b.team(f.team) if x.active]
    for e in b.enemies_of(f):
        if max(abs(e.x - point[0]), abs(e.y - point[1])) > 6:
            continue
        if any(b.gap(x, e) <= 1 for x in friends):
            out -= 0.3 * threat(e)  # (already at blows with us: a wall would only part friends from them)
            continue
        ex, ey = e.x - f.x, e.y - f.y
        px, py = point[0] - f.x, point[1] - f.y
        between = ex * px + ey * py > 0 and px * px + py * py < ex * ex + ey * ey
        if not between:
            continue
        if o.get("zone") == "wind":
            if any(op.kind == "ranged" for op in b.attack_options(e)):
                out += 0.8 * threat(e)
        else:
            out += 0.35 * threat(e)
    return max(0.0, out)


def _escape_worth(b, f, point) -> float:
    """A step through space (Misty Step, Dimension Door) away from foes pressing a hurt caster: the blows it escapes,
    less those waiting where it lands."""
    if f.hp >= f.max_hp * 0.75:
        return 0.0
    now = sum(threat(e) for e in b.enemies_of(f) if b.gap(f, e) <= 1)
    there = sum(threat(e) for e in b.enemies_of(f) if grid.gap((point[0], point[1], f.sq), e.space) <= 1)
    return max(0.0, (now - there) * 0.5 * (1.5 - f.hp / max(1, f.max_hp)))


def _dispel_worth(b, f, target, point) -> float:
    """Dispel Magic: the spells it would end - a foe's blessings, a friend's hold, ground laid against us."""
    from realmwalker.rules.engine.effects import held_spells

    x = target if target is not None else (b.at(*point) if point is not None else None)
    out = 0.0
    if x is not None:
        for level, _, _, by in held_spells(b, x):
            caster = next((y for y in b.fighters if y.id == by), None) if by is not None else None
            team = caster.team if caster is not None else x.team  # (a blessing of unknown hand: the bearer's own)
            if x.team != f.team and team == x.team:
                out += (0.6 + 0.2 * level) * threat(x)  # (a foe's blessing undone)
            elif x.team == f.team and team != f.team:
                out += 2.0 + level  # (a friend freed of a foe's spell)
            elif team == f.team:
                out -= 2.0 + level  # (our own magic undone: never wanted)
    if point is not None:
        for z in b.zones:
            if point in z.cells and z.spell and z.owner is not None and z.kind != "force":
                owner = next((y for y in b.fighters if y.id == z.owner), None)
                if owner is not None and owner.team != f.team:
                    out += 3.0
    return out


def image_worth(b, f, cells) -> float:
    """An illusion laid on these squares (Expansion 5 Part A): for each foe striking from afar (or casting), the share
    of the caster's side it sees now whose line from it would cross the image, by how much it threatens; nothing
    over a creature. The lines are worked out once a turn (`_sight_lines`); each point is then a set test."""
    lines = _sight_lines(b, f)
    if not lines:
        return 0.0
    taken = lines[0]
    cells = {c for c in cells if c not in taken}
    if not cells:
        return 0.0
    out = 0.0
    for e, pairs in lines[1]:
        hidden = [x for x, line in pairs if line & cells]
        if hidden:  # (out of its sight; a Search may undo it, so a little over half of what it seems)
            out += 0.6 * threat(e) * (0.4 + 0.6 * len(hidden) / len(pairs)) * (1.3 if f in hidden else 1.0)
    return out


def _sight_lines(b, f):
    """(squares where creatures stand, [(foe, [(friend it sees, squares between them)])]) for this turn."""
    key = (b.round, b.turn, f.id, len(b.zones))
    cache = b.__dict__.get("_image_lines")
    if cache is not None and cache[0] == key:
        return cache[1]
    taken = {sq for x in b.on_field() for sq in x.cells}
    friends = [x for x in b.team(f.team) if x.active][:6]
    out = []
    for e in b.enemies_of(f):
        if not e.active or b.feet(f, e) > 120 or any(b.gap(e, x) <= 1 for x in friends):
            continue  # (one fighting hand to hand is not stopped by a picture)
        pairs = []
        for x in friends:
            if b.can_see(e, x):
                line = set(grid.crossed(e.x + e.sq / 2, e.y + e.sq / 2, x.x + x.sq / 2, x.y + x.sq / 2))
                pairs.append((x, line - set(e.cells) - set(x.cells)))
        if pairs:
            out.append((e, pairs))
    result = (taken, out) if out else None
    b.__dict__["_image_lines"] = (key, result)
    return result


def _zone_worth(b, f, o: dict, caught: list, dc: int, up: int, w: Worth) -> None:
    """Ground a spell lays (Entangle, Grease, Moonbeam, Spike Growth, Fog Cloud...): what it does to those under it
    now and over the next rounds (`caught`: who stands in the area)."""
    foes = [x for x in caught if x.team != f.team]
    friends = [x for x in caught if x.team == f.team and x is not f]
    kind = o.get("zone")
    ability = o.get("save", "dex")
    parts = spellrules.damage_parts(o)
    dmg = sum(avg(spellrules.scaled(d, more, up)) for d, _, more in parts)
    for x in foes:
        pf = fail_chance(b, x, ability, int(o.get("dc", dc))) if ability not in ("", "none") else 1.0
        if kind in ("web", "plants"):
            w.control += pf * threat(x) * 1.2
        elif kind == "grease":
            w.control += pf * threat(x) * 0.5
        elif kind == "overgrowth":  # (Plant Growth: a foe that must come to you through it hardly comes at all)
            w.control += threat(x) * 0.4
        elif kind == "spikes":
            w.damage += dmg * 2.0  # (every square walked: a foe that comes at you through it)
        elif dmg or o.get("fail"):
            ev = dmg * (pf + (1 - pf) * (0.5 if o.get("half") else 0.0))
            w.damage += ev * 1.8  # (now, and as it stays)
            w.control += pf * threat(x) * {"restrained": 1.2, "retching": 0.8, "prone": 0.4}.get(o.get("fail", ""),
                                                                                                 0.3 if o.get("fail") else 0.0)
            if o.get("breaks") and x.concentration is not None:
                w.control += pf * threat(x) * 1.5  # (Earthquake: the spell it holds is lost)
            if o.get("dark"):
                w.control += 0.2 * threat(x)
        elif kind in ("fog", "darkness"):
            w.control += 0.3 * threat(x)
        elif kind == "lights" and x in _unseen_foes(b, f):
            w.control += 0.5 * threat(x)  # (Dancing Lights: a foe in the dark is lit, and can be seen and struck)
        elif kind == "silence" and casts_spells(b, x):
            w.control += threat(x) * 1.5
    if o.get("heal"):
        heal = avg(spellrules.scaled(o["heal"], o.get("heal_up", ""), up)) + (_caster_mod(b, f) if o.get("add_mod") else 0)
        for x in [y for y in caught if y.team == f.team]:
            w.heal += min(mends(x), heal) * 1.5  # (now, and as they stay in its light)
        friends = []  # (its light heals them rather than hurting them)
    for x in friends:
        if dmg:
            w.friendly += dmg * 0.8
        elif kind in ("web", "plants", "grease"):
            w.friendly += 0.6 * threat(x)
        elif kind == "silence" and casts_spells(b, x):
            w.friendly += threat(x) * 1.5  # (our own casters silenced too)


def _buff_worth(buff: dict, count: int, b=None, f=None, on=None, spell: dict | None = None) -> float:
    """What a blessing on friends is worth in a fight (rough, in damage dealt or kept off)."""
    w = 0.0
    if buff.get("ac"):
        w += 1.2 * int(buff["ac"])
    if buff.get("mage_armor") and on is not None and not query.wears_armour(on):
        w += 1.2 * max(0, int(buff["mage_armor"]) + on.mod("dex") - query.ac(on))  # (G.1)
    if buff.get("attack_die") and not str(buff["attack_die"]).startswith("-"):
        w += 2.5 * count
    if buff.get("resist"):
        w += 4.0
    if buff.get("death_ward"):
        w += 5.0
    near = b is not None and on is not None and any(b.gap(on, e) <= 6 for e in b.enemies_of(f))
    if buff.get("ac_floor") and on is not None:
        w += max(0, int(buff["ac_floor"]) - on.ac()) * 1.2
    if buff.get("blurred") or buff.get("images"):
        w += (3.0 + 1.5 * int(buff.get("images", 0))) * (1.0 if near else 0.5)
    if buff.get("sanctuary") is not None:
        w += 2.5 if near and on is not None and on.hp < on.max_hp / 2 else (1.0 if near else 0.3)
    if buff.get("until_act"):
        w += 1.5 if near else 0.4  # (unseen: blows at them have disadvantage, theirs advantage)
    if buff.get("ward_die"):
        w += 1.5 if near else 0.3
    if buff.get("warded_kinds") and b is not None:
        w += 3.0 * sum(1 for e in b.enemies_of(f) if e.kind in buff["warded_kinds"])
    if buff.get("heroism"):
        w += 4.0
    if buff.get("retaliate"):
        w += 3.0 if near else 1.0
    if buff.get("hit_extra") or buff.get("weapon_plus") or buff.get("smite"):
        striker = on if on is not None else f
        if striker is not None and striker.char is not None:
            weapon = striker.char.equipped_item("main_hand") is not None
        else:  # (a creature's blade or bow: Expansion 3 G.1)
            weapon = striker is not None and b is not None and bool(weapon_blows(b, striker))
        wants = 1.0 if weapon and any(b.gap(striker, e) <= 2 for e in b.enemies_of(f)) else 0.2
        if buff.get("hit_extra"):
            w += avg(str(buff["hit_extra"])) * 2.5 * wants
        if buff.get("weapon_plus"):
            w += int(buff["weapon_plus"]) * 3.0 * wants
        if buff.get("smite") and spell is not None:
            w += sum(avg(d) for o in spellrules.ops({"effects": spell.get("on_hit", ())})
                     for d, _, _ in spellrules.damage_parts(o)) * 0.7 * wants
            if any(o["op"] in ("condition", "push", "modifier") for o in spellrules.ops({"effects": spell.get("on_hit", ())})):
                w += 2.5 * wants  # (a hold, a fall or a fear riding on the blow)
    if buff.get("bond") is not None:
        w += 3.0 if near else 1.0
    if buff.get("save_bonus") and not buff.get("bond"):
        w += 1.0 * count
    if buff.get("traits") and "expeditious_retreat" in buff["traits"]:
        w += 0.6 if f is not None and f.hp < f.max_hp / 2 else 0.2
    if buff.get("shillelagh") and on is not None and on.char is not None:
        staff = on.char.equipped_item("main_hand")
        if staff is not None and staff.def_id in ("club", "quarterstaff"):
            w += 3.0 if any(b.gap(on, e) <= 2 for e in b.enemies_of(f)) else 1.0
    if buff.get("soak"):
        w += 2.5 if near else 0.8
    # The second wave (D.2)
    if buff.get("haste"):
        w += 7.0 if near else 3.0
    if buff.get("blink"):
        w += 3.5 if near else 1.0
    if buff.get("thorns"):
        w += avg(str(buff["thorns"])) * (1.0 if near else 0.3)
    if buff.get("save_adv"):
        w += 0.8 * count
    if buff.get("save_adv_against"):
        w += 0.8 * count
    if buff.get("save_adv_spells"):
        w += 1.0 * count * (2.0 if b is not None and any(casts_spells(b, e)
                                                         for e in b.enemies_of(f)) else 0.5)
    if buff.get("heal_max") and b is not None:
        w += 1.0 * sum(1 for x in b.team(f.team) if x.hp < x.max_hp)
    if buff.get("rise"):
        w += 1.0
    if buff.get("immune") and not buff.get("heroism"):
        w += 0.5 * len(buff["immune"])
    if buff.get("fly"):
        w += 1.0 if near else 0.6  # (out of reach of those on the ground)
    if buff.get("truesight") and b is not None and f is not None:
        hidden = sum(1 for e in b.enemies_of(f) if "invisible" in e.conditions or e.hidden
                     or any(bf.get("blurred") or bf.get("images") for bf in e.buffs))
        dark = any(z.opaque and z.owner is not None and z.owner not in {x.id for x in b.team(f.team)} for z in b.zones)
        w += 3.0 * hidden + (2.0 if dark else 0.0) + 0.2
    if buff.get("spell_ward") and b is not None and f is not None:
        casters = sum(1 for e in b.enemies_of(f) if casts_spells(b, e))
        w += 3.0 * casters if casters else 0.3
    # The fourth wave (D.4)
    if buff.get("foresight"):
        w += 6.0 if near else 2.0
    if buff.get("holy"):
        w += 2.5 if near else 0.8
    if buff.get("immune_damage") and b is not None and f is not None:
        w += 0.5 + 3.0 * sum(1 for e in b.enemies_of(f) if any(
            a.get("type") in buff["immune_damage"] for a in (e.cdef or {}).get("attacks", ())))
    # Part E.2 (the body on the move)
    if b is not None and f is not None:
        w += _body_worth(b, f, on if on is not None else f, buff, count)
    if buff.get("aura") and b is not None and f is not None:
        aura = buff["aura"]
        bearer = on if on is not None else f
        r = int(aura.get("radius", 30)) // 5
        friends = [x for x in b.team(f.team) if x.active and grid.gap(bearer.space, x.space) <= r]
        w += sum(_buff_worth(aura.get("grant", {}), 1, b, f, x, spell) for x in friends)
    return w


def _unseen_foes(b, f) -> list:
    """Foes standing where the side of `f` cannot see them: in the dark, beyond darkvision."""
    friends = [x for x in b.team(f.team) if x.active]
    return [e for e in b.enemies_of(f) if not any(b.can_see(x, e) for x in friends)]


def _body_worth(b, f, on, buff: dict, count: int) -> float:
    """Part E.2's blessings: light and darkvision where the party cannot see its foes, sight of the invisible, a
    mist or a feigned death only for a friend about to fall (anything else would take a fighter out of the fight)."""
    w = 0.0
    if buff.get("light") or buff.get("darkvision"):
        dark = _unseen_foes(b, f)
        sighted = on.darkvision > 0 if buff.get("darkvision") else False
        w += 0.0 if sighted else 1.5 * len(dark)
    if buff.get("see_invisible"):
        w += 3.0 * sum(1 for e in b.enemies_of(f) if "invisible" in e.conditions)
    if buff.get("sense_thoughts"):  # (Detect Thoughts: the unseen minds within 30 feet are found)
        w += 3.0 * sum(1 for e in b.enemies_of(f) if ("invisible" in e.conditions or e.hidden) and b.thinks(e)
                       and b.feet(on, e) <= int(buff["sense_thoughts"]))
    if buff.get("mist") or buff.get("feigning"):
        near = any(b.gap(on, e) <= 2 for e in b.enemies_of(f))
        dying = on.hp <= on.max_hp // 4 and near
        w += 4.0 if dying else -20.0
    if buff.get("swim") is True and b.field.swim.any():
        w += 0.6 * count
    if buff.get("climb") is True and b.field.climb.any():
        w += 0.4 * count
    return w


def _again_worth(b, f, spell: dict, up: int) -> float:
    """A spell held for its follow-up (Flame Blade's strikes, Dragon's Breath): what the follow-up would deal over
    the next couple of rounds, when there are foes near enough to use it on."""
    if not any(b.feet(f, e) <= 30 for e in b.enemies_of(f) if e.standing):
        return 0.0
    dmg = 0.0
    hurt = sum(min(mends(x), 10) for x in b.team(f.team) if x.active or x.state == "down")
    for o in spellrules.ops({"effects": spell["again"].get("effects", ())}):
        for d, t, more in spellrules.damage_parts(o):
            dmg += avg(spellrules.scaled(d, more, up)) * (0.6 if o["op"] in ("attack", "save") else 1.0)
        if o["op"] == "heal" and hurt:  # (Aura of Vitality: the healing to come)
            dmg += min(hurt, avg(spellrules.scaled(o["dice"], o.get("up", ""), up))) * 0.8
        if o["op"] == "weapon_attack":  # (Swift Quiver: shots to come)
            dmg += 4.5
    return dmg * 1.5


def _mark_on_foe(b, f, x, buff: dict) -> float:
    """What a mark put on a foe without a save is worth (Hex, Hunter's Mark)."""
    if buff.get("quarry"):
        hits = 2.0 if f.char is not None and f.char.equipped_item("main_hand") is not None else 1.5
        return avg(str(buff["quarry"])) * hits * min(3.0, x.hp / 8.0)
    return 0.0


def _summon_worth(b, f, cid: str, level: int, bonus: int, dc: int, point) -> float:
    """A summoned spirit (Expansion 3 F.2): its blows for three rounds (in the form the game would pick), its hit
    points as a wall, more where it lands among the foes; nothing while one of its caster's spirits still fights."""
    from realmwalker.rules import allies

    if any(x.bond.get("conc") and x.active for x in b.allies_of_owner(f)):
        return 0.0
    key = ("summon", id(f), cid, level, bonus, dc)
    d = _MEMO.get(key) if _MEMO is not None else None
    if d is None:
        d = allies.summon_def(b.t, cid, level, allies.best_form(b, f, cid), bonus, dc)
        if _MEMO is not None:
            _MEMO[key] = d
    blow = max((avg(str(a["damage"])) + sum(avg(str(e.get("damage", "0"))) for e in a.get("extra", ()))
                for a in d["attacks"] if not a.get("area")), default=0.0)
    worth = blow * max(1, int(d.get("multiattack", 1))) * 0.6 * 3 + int(d["hp"]) * 0.3
    for a in d["attacks"]:
        if a.get("area") and a.get("with_multiattack"):  # (a draconic spirit's breath every turn, on one or two)
            worth += avg(str(a["damage"])) * 0.75 * 1.5 * 3
    if d["spellcasting"].get("per_day"):  # (a celestial spirit's Healing Touch)
        worth += 9.0 + level
    if point is not None:
        foes = [e for e in b.enemies_of(f) if e.active]
        near = min((max(abs(e.x - point[0]), abs(e.y - point[1])) for e in foes), default=99)
        worth *= 1.0 if near <= 2 else (0.9 if near <= 6 else 0.75)
    return worth


def _objects_worth(b, f, level: int, point) -> float:
    """Animate Objects (Expansion 3 F.3): the things it would wake, their slams for three rounds (a fifth less: they
    wait for the caster's word, a Bonus Action each turn) and their bodies."""
    from realmwalker.rules import allies

    if any(x.bond.get("conc") and x.active for x in b.allies_of_owner(f)):
        return 0.0
    attack, _dc, mod = allies.caster_attack_dc(b, f)
    worth = 0.0
    for size in allies.object_sizes(b, f, mod):
        d = allies.object_def(b.t, size, level, attack, mod, allies.indoors(b))
        worth += avg(str(d["attacks"][0]["damage"])) * 0.65 * 3 * 0.8 + int(d["hp"]) * 0.3
    if point is not None:
        foes = [e for e in b.enemies_of(f) if e.active]
        near = min((max(abs(e.x - point[0]), abs(e.y - point[1])) for e in foes), default=99)
        worth *= 1.0 if near <= 2 else (0.9 if near <= 6 else 0.75)
    return worth


def _marks_worth(b, f, x, ops: list, up: int) -> float:
    """What the marks a hit or a failed save leaves are worth beyond its damage (Melf's Acid Arrow's sting, Faerie
    Fire's light, Bane, Hex...)."""
    w = 0.0
    for o in ops:
        if o["op"] == "modifier":
            buff = o.get("buff", {})
            if buff.get("outlined"):
                w += 2.0 * sum(1 for a in b.team(f.team) if a.active and a is not x)
            if buff.get("dot"):
                w += avg(str(buff["dot"])) * (1.0 if buff.get("dot_once") else 2.0)
            if str(buff.get("attack_die", "")).startswith("-") or buff.get("weak") or buff.get("duel") is not None:
                w += 0.3 * threat(x)
            if str(buff.get("save_die", "")).startswith("-"):
                w += 1.0
            if buff.get("sapped"):
                w += 0.25 * threat(x)
            if buff.get("maddened") is not None:
                w += 1.2 * threat(x)
            if buff.get("confused"):
                w += 1.5 * threat(x)
            if buff.get("sluggish"):
                w += 1.0 * threat(x)
            if buff.get("dancing"):
                w += 1.2 * threat(x)  # (no moving, its blows and its dodging weak, blows at it strong)
            if buff.get("befuddled") and casts_spells(b, x):
                w += 2.0 * threat(x)  # (Befuddlement: a caster with no spells)
            if buff.get("quarry"):
                w += avg(str(buff["quarry"])) * 2.0
        elif o["op"] in ("pull", "flee", "push"):
            w += 1.0
        elif o["op"] == "no_reaction":
            w += 0.5
        elif o["op"] == "slay":
            w += x.hp  # (all it has left)
        elif o["op"] == "lift":
            w += avg("10d6") * 0.5  # (the fall to come, when the spell ends)
        elif o["op"] == "damage":
            w += sum(avg(d) * damage_factor(x, t) for d, t, _ in spellrules.damage_parts(o))
    return w


def _antimagic_worth(b, f, spell: dict) -> float:
    """Antimagic Field: foes who cast spells, or stand in magic, close round the caster lose it; the caster and the
    friends beside them lose theirs too."""
    r = int((spell.get("area") or {}).get("size", 10)) // 5 + 1  # (and those who would step into it)
    out = 0.0
    for x in b.fighters:
        if not x.active or grid.gap(f.space, x.space) > r:
            continue
        caster = casts_spells(b, x)
        magic = sum(1 for bf in x.buffs if bf.get("source") in b.t.spells)
        if x.team != f.team:
            out += threat(x) * (2.0 if caster else 0.0) + 1.5 * magic
        else:
            out -= (threat(x) * 1.5 if caster else 0.0) + 1.0 * magic
    return out


def _stages_worth(b, f, o: dict, caught: list, dc: int) -> float:
    """Storm of Vengeance: what its next turns would deal to the foes under it (held by concentration: weighed down)."""
    foes = [x for x in caught if x.team != f.team and x.active]
    out = 0.0
    for st in o.get("stages", ())[:4]:
        share = min(1.0, int(st["count"]) / max(1, len(foes))) if st.get("count") else 1.0
        for x in foes:
            for inner in st.get("ops", ()):
                for d, t, more in spellrules.damage_parts(inner):
                    ev = avg(d) * damage_factor(x, t)
                    if inner["op"] == "save":
                        pf = fail_chance(b, x, inner.get("ability", "dex"), dc)
                        ev *= pf + (1 - pf) * (0.5 if inner.get("half") else 0.0)
                    out += ev * share
    return out * 0.6


def _typed(o: dict, xs: list, f) -> dict:
    """The damage type the caster would choose for these creatures (`types`)."""
    if not o.get("types"):
        return o
    foes = [x for x in xs if x is not None and x.team != f.team] or [x for x in xs if x is not None]
    best = max(o["types"], key=lambda t: (sum(damage_factor(x, t) for x in foes), -o["types"].index(t)))
    return {**o, "type": best}


def _moved_zone_worth(b, f, spell: dict, point) -> float:
    """Moving a spell's zone (Moonbeam, Cloud of Daggers): foes newly under it."""
    base = spell.get("again_of", "")
    z = next((z for z in b.zones if z.owner == f.id and z.spell == base), None)
    if z is None:
        return 0.0
    area = b.t.spells[base].get("area") or {}
    cells = set(b.field.area(area.get("shape", "sphere"), int(area.get("size", 5)), origin=f.space, toward=point))
    now = sum(1 for e in b.enemies_of(f) if any(c in z.cells for c in e.cells))
    then = sum(1 for e in b.enemies_of(f) if any(c in cells for c in e.cells))
    friends = sum(1 for a in b.team(f.team) if any(c in cells for c in a.cells))
    dmg = avg(z.damage) if z.damage else 3.0
    return max(0.0, (then - now) * dmg * 0.6 - friends * dmg)


def _caster_dc(b, f) -> int:
    if f.char is not None:
        return spellrules.save_dc(f.sheet, b.t)
    return int((f.cdef.get("spellcasting") or {}).get("dc", 10))


def _caster_attack(b, f) -> int:
    if f.char is not None:
        return spellrules.attack_bonus(f.sheet, b.t)
    return int((f.cdef.get("spellcasting") or {}).get("attack", 2))


def _caster_mod(b, f) -> int:
    if f.char is not None:
        return f.sheet.mod(spellrules.casting_ability(f.char, b.t))
    return f.mod((f.cdef.get("spellcasting") or {}).get("ability", "wis"))


def squares_of(cells) -> set:
    return {(int(c[0]), int(c[1])) for c in cells}


def near_enemy(b, f, space=None) -> int:
    """How many standing enemies are within reach of this square."""
    sp = space or f.space
    return sum(1 for e in b.enemies_of(f) if e.standing and grid.gap(sp, e.space) <= b.reach_of(e))
