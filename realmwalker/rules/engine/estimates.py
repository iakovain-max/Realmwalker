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
    if spell.get("area"):
        cells = b.spell_area(f, sid, point, target)
        caught = b.in_area(cells, spell.get("affects", "all"), f)
    elif spell["target"] == "all_allies":
        reach = b.spell_range(spell, f)
        caught = [x for x in b.team(f.team) if (x.active or x.state == "down") and b.feet(f, x) <= reach]
    else:
        caught = [target] if target is not None else ([f] if spell["target"] == "self" else [])
    for o in spell.get("effects", ()):
        kind = o["op"]
        if kind == "attack" and target is not None:
            o = _typed(o, [target], f)
            for d, t, more in spellrules.damage_parts(o)[:1]:
                expr = spellrules.scaled(_scaled(d, mult if o.get("scaling") == "cantrip" else 1), more, up)
                opt = AttackOption("spell", spell["name"], "spell_ranged" if o["attack"] != "melee" else "spell_melee",
                                   bonus, expr, t)
                rays = int(o.get("rays", 1)) * (mult if o.get("rays_scaling") else 1) + int(o.get("rays_up", 0)) * up
                p = hit_chance(b, f, opt, target)
                ev = attack_value(b, f, opt, target) * rays
                if o.get("miss_half"):
                    ev += (1 - p) * avg(expr) * 0.5 * damage_factor(target, t) * rays
                ev += p * rays * _marks_worth(b, f, target, o.get("on_hit", ()), up)
                w.damage += ev
                w.kills += int(ev >= target.hp)
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
        elif kind == "heal":
            many = max(1, int(o.get("count", 1)) + int(o.get("count_up", 0)) * up)
            for x in sorted(caught, key=lambda x: x.hp / max(1, x.max_hp))[:many]:
                missing = x.max_hp - x.hp
                if missing > 0:
                    w.heal += min(missing, avg(spellrules.scaled(o["dice"], o.get("up", ""), up))
                                  + (_caster_mod(b, f) if o.get("add_mod") else 0))
                    if x.state == "down":
                        w.heal += 10.0  # up again
        elif kind == "modifier":
            n = int(o.get("count", 1)) + int(o.get("count_up", 0)) * up
            if spell["target"] not in ("self", "all_allies"):
                n = max(n, int(spell.get("targets", 1)) + int(spell.get("targets_up", 0)) * up)
            on = target if target is not None else f
            if on is not None and on.team != f.team:
                w.control += _mark_on_foe(b, f, on, o.get("buff", {}))  # (Hex, Faerie Fire on a foe)
            else:
                w.help += _buff_worth(spellrules.buff_at(o, spell["level"] + up, spell), n, b, f, on, spell)
        elif kind == "weapon_attack" and target is not None and f.char is not None:
            opts = [x for x in b.attack_options(f) if x.available and x.item_uid is not None
                    and x.kind in ("melee", "ranged") and b.in_reach(f, x, target)[0]]
            if opts:
                am = int(opts[0].extra.get("ability_mod", 0))
                spell_mod = _caster_mod(b, f)
                ev = attack_value(b, f, opts[0], target) * (1.0 + 0.1 * max(0, spell_mod - am))
                ev += hit_chance(b, f, opts[0], target) * (spell_mod - am + 3.5 * max(0, mult - 1))
                w.damage += max(0.0, ev)
                w.kills += int(ev >= target.hp)
        elif kind == "temp_hp" and (caught or spell["target"] == "self"):
            x = caught[0] if spell["target"] != "self" else f
            amount = avg(str(o["amount"])) + int(o.get("per_up", 0)) * up
            w.help += max(0.0, amount - x.temp_hp) * (0.6 if any(b.gap(x, e) <= 6 for e in b.enemies_of(f)) else 0.2)
        elif kind == "move_zone" and point is not None:
            w.damage += _moved_zone_worth(b, f, spell, point)
        elif kind in ("summon", "aura", "guardian"):
            d, t, more = spellrules.damage_parts(o)[0] if spellrules.damage_parts(o) else ("0", "", "")
            w.help += avg(spellrules.scaled(d, more, up)) * 0.55 * 3
        elif kind == "zone" and caught:
            _zone_worth(b, f, o, caught, dc, up, w)
    if spell.get("again"):
        w.help += _again_worth(b, f, spell, up)
    if up and spell.get("targets_up") and target is not None:  # (more creatures of the same kind nearby)
        others = [x for x in (b.enemies_of(f) if target.team != f.team else b.team(f.team))
                  if x is not target and x.active and b.feet(f, x) <= max(5, b.spell_range(spell, f))]
        extra = min(len(others), int(spell["targets_up"]) * up)
        if extra:
            w.damage, w.control, w.kills = (w.damage * (1 + 0.8 * extra), w.control * (1 + 0.8 * extra),
                                            w.kills * (1 + extra))
    return w


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
        else:
            w.damage += ev
            w.kills += int(ev >= x.hp)
            if o.get("on_fail"):
                w.control += pf * threat(x) * _control_rounds(o["on_fail"])
                w.damage += pf * _marks_worth(b, f, x, o["on_fail"], up)
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
        if o["op"] == "condition" and o["condition"] == "charmed":
            return 0.3  # (it will not strike the one who charmed it)
    return 0.0


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
        elif kind == "spikes":
            w.damage += dmg * 2.0  # (every square walked: a foe that comes at you through it)
        elif dmg:
            ev = dmg * (pf + (1 - pf) * (0.5 if o.get("half") else 0.0))
            w.damage += ev * 1.8  # (now, and as it stays)
        elif kind in ("fog", "darkness"):
            w.control += 0.3 * threat(x)
        elif kind == "silence" and x.cdef is not None and x.cdef.get("spells"):
            w.control += threat(x) * 1.5
    for x in friends:
        if dmg:
            w.friendly += dmg * 0.8
        elif kind in ("web", "plants", "grease"):
            w.friendly += 0.6 * threat(x)


def _buff_worth(buff: dict, count: int, b=None, f=None, on=None, spell: dict | None = None) -> float:
    """What a blessing on friends is worth in a fight (rough, in damage dealt or kept off)."""
    w = 0.0
    if buff.get("ac"):
        w += 1.2 * int(buff["ac"])
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
        weapon = striker is not None and striker.char is not None and striker.char.equipped_item("main_hand") is not None
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
    return w


def _again_worth(b, f, spell: dict, up: int) -> float:
    """A spell held for its follow-up (Flame Blade's strikes, Dragon's Breath): what the follow-up would deal over
    the next couple of rounds, when there are foes near enough to use it on."""
    if not any(b.feet(f, e) <= 30 for e in b.enemies_of(f) if e.standing):
        return 0.0
    dmg = 0.0
    for o in spellrules.ops({"effects": spell["again"].get("effects", ())}):
        for d, t, more in spellrules.damage_parts(o):
            dmg += avg(spellrules.scaled(d, more, up)) * (0.6 if o["op"] in ("attack", "save") else 1.0)
    return dmg * 1.5


def _mark_on_foe(b, f, x, buff: dict) -> float:
    """What a mark put on a foe without a save is worth (Hex, Hunter's Mark)."""
    if buff.get("quarry"):
        hits = 2.0 if f.char is not None and f.char.equipped_item("main_hand") is not None else 1.5
        return avg(str(buff["quarry"])) * hits * min(3.0, x.hp / 8.0)
    return 0.0


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
        elif o["op"] in ("pull", "flee", "push"):
            w += 1.0
        elif o["op"] == "no_reaction":
            w += 0.5
        elif o["op"] == "damage":
            w += sum(avg(d) * damage_factor(x, t) for d, t, _ in spellrules.damage_parts(o))
    return w


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
