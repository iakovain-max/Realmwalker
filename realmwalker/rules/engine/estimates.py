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
from realmwalker.rules import grid
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


def fail_chance(b, x, ability: str, dc: int) -> float:
    sr = query.save_roll(b, x, ability)
    if sr.auto_fail:
        return 1.0
    bonus = sr.bonus + sum(avg(d) for d in sr.dice)
    return 1.0 - _p(int(round(dc - bonus)), sr.roll.mode)


def damage_factor(x, dtype: str) -> float:
    """What resistance, vulnerability or immunity leaves of damage of this kind."""
    amount, _ = query.damage_taken(x, 100, dtype)
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
                level: int | None = None) -> Worth:
    """What casting this spell here would do, in expected numbers."""
    from realmwalker.rules.combat import AttackOption, spell_id

    spell = b.t.spells[spell_id(sid)]
    w = Worth()
    dc = dc if dc is not None else _caster_dc(b, f)
    bonus = bonus if bonus is not None else _caster_attack(b, f)
    mult = spellrules.cantrip_multiplier(f.char.level) if f.char is not None else 1
    if spell.get("area"):
        cells = b.spell_area(f, sid, point, target)
        caught = b.in_area(cells, spell.get("affects", "all"), f)
    elif spell["target"] == "all_allies":
        reach = b.spell_range(spell, f)
        caught = [x for x in b.team(f.team) if (x.active or x.state == "down") and b.feet(f, x) <= reach]
    else:
        caught = [target] if target is not None else []
    for o in spell.get("effects", ()):
        kind = o["op"]
        if kind == "attack" and target is not None:
            for d, t, _ in spellrules.damage_parts(o)[:1]:
                expr = _scaled(d, mult if o.get("scaling") == "cantrip" else 1)
                opt = AttackOption("spell", spell["name"], "spell_ranged" if o["attack"] != "melee" else "spell_melee",
                                   bonus, expr, t)
                ev = attack_value(b, f, opt, target) * int(o.get("rays", 1))
                w.damage += ev
                w.kills += int(ev >= target.hp)
        elif kind == "darts" and target is not None:
            d, t, _ = spellrules.damage_parts(o)[0]
            ev = avg(d) * int(o.get("count", 1)) * damage_factor(target, t)
            w.damage += ev
            w.kills += int(ev >= target.hp)
        elif kind == "save":
            for x in caught:
                if not _allowed(o, x):
                    continue
                pf = fail_chance(b, x, o["ability"], int(o.get("dc", dc)))
                dmg = sum(avg(_scaled(d, mult if o.get("scaling") == "cantrip" else 1)) * damage_factor(x, t)
                          for d, t, _ in spellrules.damage_parts(o))
                ev = dmg * (pf + (1 - pf) * (0.5 if o.get("half") else 0.0))
                if x.team == f.team:
                    w.friendly += ev
                else:
                    w.damage += ev
                    w.kills += int(ev >= x.hp)
                    if o.get("on_fail"):
                        w.control += pf * threat(x) * _control_rounds(o["on_fail"])
        elif kind == "heal":
            for x in sorted(caught, key=lambda x: x.hp / max(1, x.max_hp))[:max(1, int(o.get("count", 1)))]:
                missing = x.max_hp - x.hp
                if missing > 0:
                    w.heal += min(missing, avg(o["dice"]) + (_caster_mod(b, f) if o.get("add_mod") else 0))
                    if x.state == "down":
                        w.heal += 10.0  # up again
        elif kind == "modifier":
            w.help += _buff_worth(o.get("buff", {}), int(o.get("count", 1)))
        elif kind in ("summon", "aura", "guardian"):
            d, t, _ = spellrules.damage_parts(o)[0] if spellrules.damage_parts(o) else ("0", "", "")
            w.help += avg(d) * 0.55 * 3
    return w


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
            w.heal += min(amount, max(0, f.max_hp - f.hp))
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
        give = min(max(0, x.max_hp // 2 - x.hp), pool)
        pool -= give
        w.heal += give + (10.0 if give and x.state == "down" else 0.0)


def _battle_medic(b, f, w: Worth) -> None:
    near = [x for x in b.team(f.team) if x is not f and (x.active or x.state == "down") and b.gap(f, x) <= 1]
    if near:
        x = min(near, key=lambda x: x.hp / max(1, x.max_hp))
        die = (b.t.classes[x.char.cls]["hit_die"] if x.char is not None else 8) / 2 + 0.5
        w.heal += min(die + proficiency_of(f), max(0, x.max_hp - x.hp)) + (10.0 if x.state == "down" else 0.0)


def proficiency_of(f) -> int:
    from realmwalker.rules.engine import query

    return query.proficiency(f)


def _speedy_recovery(b, f, w: Worth) -> None:
    die = (b.t.classes[f.char.cls]["hit_die"] if f.char is not None else 8) / 2 + 0.5
    w.heal += min(die, max(0, f.max_hp - f.hp))


def _chef_treat(b, f, w: Worth) -> None:
    w.heal += max(0, proficiency_of(f) - f.temp_hp) * (1.0 if f.hp < f.max_hp else 0.3)


def _telekinetic_shove(b, f, w: Worth) -> None:
    w.control += 1.0  # (where to shove is the tactics' judgement: rules/tactics._mind_shove)


def _recover_vitality(b, f, w: Worth) -> None:
    left = f.char.uses.get("vitality_dice", 0) if f.char is not None else 0
    want = max(0, f.max_hp - f.hp)
    w.heal += min(want, 5.5 * min(left, -(-want * 2 // 11)))


def _divine_spark_harm(b, f, w: Worth) -> None:
    from realmwalker.rules.engine.handlers import cleric

    n, sides, _ = dice.parse(cleric.spark_dice(f))
    w.damage += 0.75 * (n * (sides + 1) / 2 + f.mod("wis"))  # (a Constitution save halves it)


_ABILITY_WORTH = {"divine_spark_harm": _divine_spark_harm, "turn_undead": _turn_undead, "preserve_life": _preserve_life, "battle_medic": _battle_medic,
                  "speedy_recovery": _speedy_recovery, "chef_treat": _chef_treat,
                  "telekinetic_shove": _telekinetic_shove, "recover_vitality": _recover_vitality}


def _control_rounds(ops: list[dict]) -> float:
    """Roughly how many of the victim's rounds a failed save takes away."""
    for o in ops:
        if o["op"] == "condition" and o["condition"] in ("paralyzed", "stunned", "unconscious", "incapacitated"):
            return 2.5  # its turns lost, and every blow at it with advantage (and from beside it, a critical)
        if o["op"] == "lose_turn":
            return 1.0
        if o["op"] == "condition" and o["condition"] in ("restrained", "prone", "frightened", "blinded"):
            return 0.4
    return 0.0


def _buff_worth(buff: dict, count: int) -> float:
    w = 0.0
    if buff.get("ac"):
        w += 1.2 * int(buff["ac"])
    if buff.get("attack_die"):
        w += 2.5 * count
    if buff.get("resist"):
        w += 4.0
    if buff.get("death_ward"):
        w += 5.0
    return w


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
