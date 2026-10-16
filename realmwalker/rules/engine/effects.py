"""Effect operations: what spells (and, in time, abilities and magic items) do, as data (docs/EXPANSIONS.md §4.3.2).

A spell's `effects` is a list of ops, run in order when it is cast (`cast`). A top-level op picks its own targets from
the spell's aim (`target`: enemy, ally, self, all_allies, downed_ally, dead_ally, point, direction; `area`; `affects`);
an op inside another (`on_hit`, `on_fail`, `then`) works on the creature the outer op was dealing with.

    attack     a spell attack: attack (ranged|melee), damage + type, up (dice per slot level above), scaling
               ("cantrip"), rays + rays_up (one attack each, re-aimed as targets fall), on_hit [ops]
    darts      sure hits: count + count_up, damage + type, each at the weakest when the first falls (Magic Missile)
    save       a saving throw: ability, damage (one or a list of {dice, type, up}), half (true: half on a save), cover
               (false: cover does not help), kinds / not_kinds (who it works on), sure_save (traits that always
               succeed), on_fail [ops]
    condition  condition, and how it ends: ends ("own_turn_end", "caster_turn_start"...), rounds (the old way),
               repeat_save (shaken off with the same save at the end of each of its turns), on_damage, then
               {save, on_fail}; while the spell needs concentration, the condition ends with it
    heal       dice, add_mod, up, mends_wound; count / count_up for several
    modifier   buff {...} for `rounds` (a lasting spell outlives the fight: rules/spells.py)
    zone       zone (web, ice, fire, fog, caltrops, bearings), rounds, dc (a fixed DC); a web catches (Dexterity save,
               Restrained); caltrops and ball bearings catch whoever walks in (Battle._zone_underfoot)
    aura       an emanation that moves with the caster and hurts enemies in it (Spirit Guardians)
    guardian   a token at a point that hurts enemies who come near, until its strength is spent
    summon     a spiritual weapon at a point: it strikes now and on later turns with a bonus action
    teleport   the caster to the point (Misty Step)
    push       feet, straight away from the caster or the point
    ignite     dry ground in the area catches; burn {rounds, damage}: the area keeps burning
    slow       feet off its speed, until the start of the caster's next turn
    no_opportunity, no_heal, mark   (until a turn ends or starts: see each)
    lose_turn  it spends its next turn grovelling on the ground (Command)
    burning    it catches fire (1d4 fire at the start of each of its turns, until put out with an action)
    damage     damage that has already landed (a stat block's extra harm): damage + type
    stabilize, restore (conditions, one, disease), revive (consumes, within_rounds), identify (outside a fight)
    gain_action (one more action this turn), say (a line: {name}, {their}), special (Python by id: SPECIAL)

Unknown ops are data errors at start-up (rules/engine/check.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from realmwalker.core import dice
from realmwalker.rules import grid
from realmwalker.rules import spells as spellrules
from realmwalker.rules.engine import conditions, durations, events, statblocks
from realmwalker.rules.inventory import remove_item

OPS: dict[str, Callable] = {}
SPECIAL: dict[str, Callable] = {}  # what an op {"op": "special", "handler": id} calls (rules/engine/handlers/)


def op(name: str):
    def register(fn: Callable) -> Callable:
        OPS[name] = fn
        return fn
    return register


def special(name: str):
    """Register Python for an effect the ops cannot say ({"op": "special", "handler": name})."""
    def register(fn: Callable) -> Callable:
        SPECIAL[name] = fn
        return fn
    return register


@dataclass
class Cast:
    """One casting: who, what, at whom or where, and the numbers it was cast with."""
    b: Any
    caster: Any
    sid: str
    spell: dict
    target: Any
    point: tuple | None
    area: list = field(default_factory=list)
    up: int = 0  # slot levels above the spell's own
    mod: int = 0  # the caster's spellcasting modifier
    dc: int = 10
    bonus: int = 0  # spell attack bonus
    mult: int = 1  # cantrip dice multiplier
    level: int = 0  # the level it was cast at
    empowered: int = 0  # damage added to one damage roll (Empowered Evocation, Potent Spellcasting)
    maximize: bool = False  # every damage die at its highest (an evoker's Overchannel)
    slotted: bool = True  # cast with a spell slot (not a scroll, a free cast, an item's or a creature's own magic)
    pushed: list = field(default_factory=list)  # (fighter, feet) to throw back once everyone has saved


MECHANICS = (("attack", "attack"), ("darts", "darts"), ("save", "save"), ("heal", "heal"), ("stabilize", "heal"),
             ("restore", "heal"), ("revive", "heal"), ("modifier", "buff"), ("teleport", "teleport"), ("zone", "zone"),
             ("summon", "summon"), ("guardian", "summon"), ("aura", "aura"))


def mechanic(spell: dict) -> str:
    """What a cast does, in one word, for the board and the sounds (its look is `fx`): attack, save, heal..."""
    if spell.get("fx") == "sleep":
        return "sleep"
    ops = {o["op"] for o in spell.get("effects", ())}
    return next((word for op, word in MECHANICS if op in ops), "")


def cast(b, f, sid: str, spell: dict, target, point, *, up: int, mod: int, dc: int, bonus: int, mult: int,
         level: int, slotted: bool = True) -> None:
    """A spell's effects, once it has been paid for (by a party caster, or a monster's own magic)."""
    area = b.spell_area(f, sid, point, target) if spell.get("area") else []
    if spell.get("thrown"):
        b.say(f"{f.the_name} throws a flask: <danger>{spell['name'].lower()}</>!", "info")
    else:
        b.say(f"{f.the_name} casts <magic>{spell['name']}</>.", "magic")
    b._event("cast", by=f.id, to=target.id if target is not None else None, spell=sid, effect=mechanic(spell),
             look=spell.get("fx", ""), dtype=spellrules.main_type(spell), area=list(area), point=point,
             shape=(spell.get("area") or {}).get("shape", ""))
    if spell.get("concentration"):
        b._start_concentration(f, sid, spell)
    events.emit(b, "spell_cast", actor=f, spell=spell, sid=sid, level=level, slotted=slotted)  # an Arcane Ward...
    c = Cast(b, f, sid, spell, target, point, list(area), up, mod, dc, bonus, mult, level, slotted=slotted)
    if f.char is not None and spell.get("school") == "evocation" and f.char.cls == "wizard" \
            and f.has_trait("empowered_evocation"):
        c.empowered = mod
    if f.char is not None and spell.get("level") == 0 and "cleric" in spell.get("classes", ()) \
            and f.has_trait("blessed_potent_spellcasting"):
        c.empowered = max(c.empowered, f.mod("wis"))  # (a cleric's Potent Spellcasting)
    if slotted and 1 <= level <= 5 and f.char is not None and "wizard" in spell.get("classes", ()) \
            and f.has_trait("overchannel") and spellrules.harms(spell):
        from realmwalker.rules.engine.handlers import wizard

        c.maximize = wizard.overchannel(b, f, spell, level)
    before = b.__dict__.get("_casting")
    b._casting = f if not spell.get("ability") and "item" not in spell.get("classes", ()) else None
    try:
        run(c, spell.get("effects", ()))
        if c.maximize:
            from realmwalker.rules.engine.handlers import wizard

            wizard.overchannel_price(b, f)
    finally:
        b._casting = before


def run(c: Cast, ops, victim=None) -> None:
    for o in ops:
        OPS[o["op"]](c, o, victim)


def expr(c: Cast, base: str, up: str = "", *, scaling: bool = False, empower: bool = False) -> str:
    """A dice expression with the cantrip multiplier, the slot levels above and an evoker's bonus worked in."""
    n, sides, flat = dice.parse(base)
    if scaling:
        n *= c.mult
    if up and c.up:
        un, us, _ = dice.parse(up)
        if us == sides:
            n += un * c.up
    if empower:
        flat += c.empowered
    if c.maximize:
        return str(n * sides + flat)  # (Overchannel: the greatest the dice can do)
    if not n:
        return str(flat)
    return f"{n}d{sides}{'+' + str(flat) if flat > 0 else (str(flat) if flat < 0 else '')}"


def potent(c: Cast) -> bool:
    """An evoker's Potent Cantrip: a cantrip that misses, or that is saved against, still does half its damage."""
    return c.spell.get("level") == 0 and c.caster.char is not None and c.caster.has_trait("potent_cantrip") \
        and not c.spell.get("ability") and "item" not in c.spell.get("classes", ())


def _allowed(o: dict, x) -> bool:
    if o.get("kinds") and x.kind not in o["kinds"]:
        return False
    if o.get("not_kinds") and x.kind in o["not_kinds"]:
        return False
    return True


def _targets(c: Cast) -> list:
    """The creature(s) a spell aimed at one target works on: the target, and with a higher slot more of the same kind
    (Hold Person, Command), nearest first."""
    if c.target is None:
        return []
    out = [c.target]
    extra = int(c.spell.get("targets_up", 0)) * c.up
    if extra:
        others = [x for x in c.b.spell_targets(c.caster, c.sid) if x is not c.target and x is not c.caster]
        others.sort(key=lambda x: c.b.gap(c.caster, x))
        out += others[:extra]
    return out


# ---------------------------------------------------------------------------- attacks and damage
@op("attack")
def _attack(c: Cast, o: dict, victim) -> None:
    from realmwalker.rules.combat import AttackOption

    b, f, spell = c.b, c.caster, c.spell
    target = victim or c.target
    rays = int(o.get("rays", 1)) + int(o.get("rays_up", 0)) * c.up
    reach = b.spell_range(spell)
    for _ in range(rays):
        if target is None or not target.active:
            options = b.spell_targets(f, c.sid)
            if not options:
                break
            target = b.rng.choice(options)
        for dice_, dtype, up in spellrules.damage_parts(o)[:1]:
            opt = AttackOption("spell", spell["name"].lower(), "spell_melee" if o["attack"] == "melee" else "spell_ranged",
                               c.bonus, expr(c, dice_, up, scaling=o.get("scaling") == "cantrip", empower=True), dtype,
                               range=(reach, reach))
            c.empowered = 0  # (one damage roll of the spell: the first ray)
            if b._attack(f, opt, target):
                if target.active:
                    run(c, o.get("on_hit", ()), target)
            elif potent(c) and (target.active or target.state == "down"):
                half = _roll(c, opt.damage, dtype) // 2
                if half > 0:
                    b.say(f"<magic>The cantrip still bites.</> (Potent Cantrip)", "magic")
                    b._hit(f, target, half, dtype, crit=False, weapon=spell["name"].lower())


@op("darts")
def _darts(c: Cast, o: dict, victim) -> None:
    b, f = c.b, c.caster
    target = victim or c.target
    count = int(o.get("count", 1)) + int(o.get("count_up", 0)) * c.up
    for _ in range(count):
        if target is None or not target.active:
            options = b.spell_targets(f, c.sid)
            if not options:
                break
            target = min(options, key=lambda x: x.hp)
        dice_, dtype, _ = spellrules.damage_parts(o)[0]
        amount = dice.roll(expr(c, dice_), b.rng).total
        b._event("dart", by=f.id, to=target.id, dtype=dtype)
        b._hit(f, target, amount, dtype, crit=False, weapon="dart of force")


@op("save")
def _save(c: Cast, o: dict, victim) -> None:
    b, f, spell = c.b, c.caster, c.spell
    if victim is not None:
        victims = [victim]
    elif c.area:
        victims = b.in_area(c.area, spell.get("affects", "all"), f)
    else:
        victims = _targets(c)
    parts = [(expr(c, d, up, scaling=o.get("scaling") == "cantrip", empower=True), t)
             for d, t, up in spellrules.damage_parts(o)]
    rolled = {i: _roll(c, e, t) for i, (e, t) in enumerate(parts)} if c.area else {}
    origin = c.point if spell["target"] == "point" and c.point is not None else (f.x, f.y)
    spared = b.sculpted(f, c.sid, victims, c.level) if c.area else set()
    on_save = "half" if o.get("half") or (parts and potent(c)) else "none"
    ability = o["ability"]
    dc = int(o.get("dc", c.dc))
    for x in victims:
        if not _allowed(o, x):
            if x is c.target:
                b.say(f"The spell finds no grip on {x.the_name}.", "system")
            continue
        if x.id in spared:
            b.say(f"<magic>The fire parts around {x.the_name}.</> (Sculpt Spells)" if spellrules.main_type(spell) == "fire"
                  else f"<magic>The spell passes {x.the_name} by.</> (Sculpt Spells)", "magic")
            continue
        cover = 0
        if ability == "dex" and o.get("cover", True):
            cover = min(grid.THREE_QUARTERS, b.field.cover((origin[0], origin[1], 1), x.space))
            cover = 0 if cover == grid.TOTAL else cover
        if any(x.has_trait(t) for t in o.get("sure_save", ())) or x.kind in o.get("sure_kinds", ()):
            saved = True
            b.dice_say(f"{x.name} {ability.upper()} save: not affected")
        else:
            saved = b._save(x, ability, dc, bonus=grid.COVER_AC[cover] if ability == "dex" else 0,
                            against=_conditions_in(o.get("on_fail", ())))
        b._event("save", who=x.id, ok=saved)
        for i, (e, dtype) in enumerate(parts):
            full = rolled[i] if i in rolled else _roll(c, e, dtype)
            b._save_hit(f, x, ability, saved, full, dtype, on_save)
        if not saved and x.active:
            run(c, o.get("on_fail", ()), x)
    # Hurled away, the farthest first so that nobody is stopped by a friend who is about to be thrown too.
    src = f if spell["target"] != "point" else (origin[0], origin[1])
    for x, feet in sorted(c.pushed, key=lambda p: -grid.gap((origin[0], origin[1], 1), p[0].space)):
        if x.active:
            b._push(src, x, int(feet) // 5)
    c.pushed.clear()


@op("push")
def _push(c: Cast, o: dict, victim) -> None:
    if o.get("max_size") and victim is not None and not statblocks.size_at_most(victim.size, o["max_size"]):
        return
    if victim is not None and victim is not c.caster and victim.hp > 0:
        if o.get("now"):
            c.b._push(c.caster, victim, int(o["feet"]) // 5)
        else:
            c.pushed.append((victim, int(o["feet"])))


def _roll(c: Cast, e: str, dtype: str) -> int:
    """A spell's damage roll (Elemental Adept: a 1 on a die of the chosen element counts as a 2)."""
    rolled = dice.roll(e, c.b.rng)
    if c.caster.char is not None and c.b.__dict__.get("_casting") is c.caster:
        from realmwalker.rules import feats

        return rolled.total + feats.adept_ones(c.caster.char, dtype, rolled.rolls)
    return rolled.total


@op("damage")
def _damage(c: Cast, o: dict, victim) -> None:
    """Damage without a roll to hit or a save (it has already landed)."""
    if o.get("max_size") and victim is not None and not statblocks.size_at_most(victim.size, o["max_size"]):
        return
    if o.get("charge_feet") and c.caster.moved_feet < int(o["charge_feet"]):
        return  # only after a charge (a boar's Gore)
    if victim is not None and (victim.active or victim.state == "down"):
        for dice_, dtype, up in spellrules.damage_parts(o):
            c.b._hit(c.caster, victim, _roll(c, expr(c, dice_, up), dtype), dtype, crit=False,
                     weapon=c.spell.get("name", dtype))


@op("ignite")
def _ignite(c: Cast, o: dict, victim) -> None:
    c.b._ignite(c.caster, c.area)


@op("burn")
def _burn(c: Cast, o: dict, victim) -> None:
    """Oil or alchemist's fire keeps burning where it fell."""
    from realmwalker.rules.combat import Zone

    b = c.b
    b._add_zone(Zone(b._zone_id(), "fire", set(c.area), owner=c.caster.id, rounds=int(o.get("rounds", 1)), save="dex",
                     dc=10, damage=str(o.get("damage", "1d4")), damage_type="fire", on_save="none"))


# ---------------------------------------------------------------------------- what a hit or a failed save brings
def _ends(c: Cast, x, how: str | None) -> dict | None:
    if not how:
        return None
    whose, at = how.rsplit("_turn_", 1)
    return durations.until(c.b, c.caster if whose == "caster" else x, f"turn_{at}")


@op("condition")
def _condition(c: Cast, o: dict, victim) -> None:
    b, f, spell = c.b, c.caster, c.spell
    victims = [victim] if victim is not None else _targets(c)
    cid = o["condition"]
    for x in victims:
        if x is None or not x.active:
            continue
        if o.get("max_size") and not statblocks.size_at_most(x.size, o["max_size"]):
            continue
        if x.kind in o.get("not_kinds", ()) or x.char is not None and x.char.race in o.get("not_species", ()):
            continue  # (a ghoul's touch: not the dead, not elves)
        if o.get("charge_feet") and f.moved_feet < int(o["charge_feet"]):
            continue
        extra = {}
        if o.get("escape"):
            extra["escape"] = int(o["escape"])
        if spell.get("concentration"):
            extra["conc"] = f.id
        if o.get("on_damage"):
            extra["on_damage"] = True
        if o.get("then"):
            t = o["then"]
            extra["then"] = {"save": t["save"], "dc": c.dc, "caster": f.id, "spell": c.sid,
                             "on_fail": t.get("on_fail", []), "conc": f.id if spell.get("concentration") else None}
        ends = _ends(c, x, o.get("ends"))
        rounds = None if spell.get("concentration") or ends is not None else \
            (-1 if cid == "prone" else int(o.get("rounds", spell.get("rounds", 1))))
        if not durations.give(b, x, cid, ends=ends, rounds=rounds, source=f, **extra):
            b.say(f"{x.the_name} shrugs it off.", "system")
            continue
        if cid == "grappled":
            x.grappled_by = f.id
        if o.get("repeat_save"):
            x.save_ends.append({"cond": cid, "save": o.get("save", spell_save(spell)), "dc": int(o.get("save_dc") or c.dc),
                                "conc": f.id if spell.get("concentration") else None})
        b._event("condition", who=x.id, cond=cid)
        b.say(f"{x.the_name} is {conditions.name(b.t, cid).lower()}.", "good" if x.side != f.side else "danger")


def _conditions_in(ops_: list) -> tuple:
    """The conditions a failed save would bring (Brave and Fey Ancestry read them)."""
    return tuple(o.get("condition") for o in ops_ if o.get("op") == "condition" and o.get("condition"))


def spell_save(spell: dict) -> str:
    s = spellrules.op(spell, "save")
    return s["ability"] if s else "con"


def then_save(b, x, then: dict) -> None:
    """The second saving throw of a spell that tightens its grip (Sleep): a failure brings what `on_fail` says."""
    caster = next((f for f in b.fighters if f.id == then.get("caster")), None)
    if then.get("conc") is not None and (caster is None or caster.concentration is None):
        return  # the spell is over
    if b._save(x, then["save"], int(then["dc"]), against=_conditions_in(then.get("on_fail", ()))):
        return
    spell = b.t.spells[then["spell"]] if then.get("spell") in b.t.spells else {}
    c = Cast(b, caster or x, then.get("spell", ""), spell, x, None, dc=int(then["dc"]))
    run(c, then.get("on_fail", ()), x)


@op("slow")
def _slow(c: Cast, o: dict, victim) -> None:
    if victim is not None:
        durations.buff(victim, {"slow": int(o["feet"]), "source": f"slow:{c.sid}"},
                       durations.until(c.b, c.caster, "turn_start"))


@op("no_opportunity")
def _no_opportunity(c: Cast, o: dict, victim) -> None:
    if victim is not None:
        durations.buff(victim, {"no_opportunity": True, "source": f"jolt:{c.sid}"},
                       durations.until(c.b, victim, "turn_start"))


@op("no_heal")
def _no_heal(c: Cast, o: dict, victim) -> None:
    if victim is not None:
        durations.buff(victim, {"no_heal": True, "source": f"chill:{c.sid}"},
                       durations.until(c.b, c.caster, "turn_end"))


@op("mark")
def _mark(c: Cast, o: dict, victim) -> None:
    """The next attack roll against it has advantage, until the end of the caster's next turn (Guiding Bolt)."""
    if victim is not None:
        durations.buff(victim, {"marked": c.caster.id, "source": f"mark:{c.sid}"},
                       durations.until(c.b, c.caster, "turn_end"))


@op("burning")
def _burning(c: Cast, o: dict, victim) -> None:
    """It catches fire: 1d4 fire at the start of each of its turns until put out (rules/engine/hazards.py)."""
    if victim is not None and victim.active:
        durations.buff(victim, {"burning": True, "source": "burning"})
        c.b.say(f"{victim.the_name} is on fire!", "danger" if victim.side == c.caster.side else "good")


@op("attach")
def _attach(c: Cast, o: dict, victim) -> None:
    """A stirge fastens on: it drinks at the start of each of its turns (statblock damage `when` start of turn)."""
    if victim is not None and victim.active:
        c.caster.attached_to = victim.id
        c.b.say(f"{c.caster.the_name} fastens onto {victim.the_name}.", "danger" if victim.side == "party" else "info")


@op("lose_turn")
def _lose_turn(c: Cast, o: dict, victim) -> None:
    """Command's Grovel: on its next turn it throws itself down, and does nothing else."""
    if victim is not None:
        victim.grovel = True


# ---------------------------------------------------------------------------- help
@op("heal")
def _heal(c: Cast, o: dict, victim) -> None:
    b, f, spell = c.b, c.caster, c.spell
    if victim is not None:
        targets = [victim]
    elif spell["target"] == "self":
        targets = [f]
    elif spell["target"] == "all_allies":
        reach = b.spell_range(spell)
        near = [x for x in b.team(f.team) if (x.active or x.state == "down") and b.feet(f, x) <= reach]
        targets = sorted(near, key=lambda x: x.hp / max(1, x.max_hp))[: int(o.get("count", 6)) + int(o.get("count_up", 0)) * c.up]
    elif c.area:
        near = [x for x in b.in_area(c.area, "allies", f)]
        targets = sorted(near, key=lambda x: x.hp / max(1, x.max_hp))[: int(o.get("count", 6))]
    else:
        targets = [c.target]
    for x in targets:
        if x is None:
            continue
        if x.no_heal:
            b.say(f"The magic finds no hold in {x.the_name}.", "warn")
            continue
        rolled = dice.roll(expr(c, o["dice"], o.get("up", "")), b.rng)
        amount = rolled.total + (c.mod if o.get("add_mod") else 0)
        if f.has_trait("feat_healer") and not spell.get("ability"):  # Healer: healing dice of 1 rolled again
            amount += sum(b.rng.randint(1, max(1, dice.parse(o["dice"])[1])) - 1 for r in rolled.rolls if r == 1)
        if o.get("add") == "level" and f.char is not None:
            amount += f.char.level  # Second Wind
        if not spell.get("ability"):
            n_, s_, flat_ = dice.parse(expr(c, o["dice"], o.get("up", "")))
            amount = events.emit(b, "heal_spell", actor=f, target=x, amount=amount, level=c.level,
                                 rolled=rolled.total, most=n_ * s_ + flat_).amount
        b._heal(x, amount)
        if o.get("mends_wound") and x.wounds:
            w = max(x.wounds, key=lambda w: (w.severity, w.bleed))
            w.severity -= 1
            w.bleed = max(0, w.bleed - 1)
            if w.severity <= 0:
                x.wounds.remove(w)
            b.say(f"The worst of {x.the_name}'s wounds closes a little.", "magic")


@op("modifier")
def _modifier(c: Cast, o: dict, victim) -> None:
    b, f, spell, sid = c.b, c.caster, c.spell, c.sid
    if victim is not None:
        targets = [victim]
    elif spell["target"] == "all_allies":
        reach = b.spell_range(spell)
        near = [x for x in b.team(f.team) if x.active and b.feet(f, x) <= reach]
        near.sort(key=lambda x: (x is not f, b.feet(f, x)))
        targets = near[: int(o.get("count", 3)) + int(o.get("count_up", 0)) * c.up]
    elif spell["target"] == "self":
        targets = [f]
    else:
        targets = [c.target]
    for x in targets:
        if x is None:
            continue
        if x.char is not None and spellrules.lasts(b.t, sid):
            # It outlives the fight: kept on them (the sheet counts its armour), the rest carried here.
            spellrules.keep(x.char, b.t, sid)
            x.buffs = [bf for bf in x.buffs if bf.get("lasting") != sid]
            part = spellrules.battle_part(b.t, sid)
            if part:
                x.buffs.append(part)
            if spell.get("concentration") and f.concentration is not None:
                f.concentration.setdefault("on", []).append(x.id)  # (lost with the caster's concentration)
        else:
            x.buffs = [bf for bf in x.buffs if bf.get("source") != sid]
            bf = {**o["buff"], "rounds": int(o.get("rounds", spell.get("rounds", 10))), "source": sid}
            if spell.get("concentration"):
                bf["conc"] = f.id
            x.buffs.append(bf)
        b._event("buff", who=x.id, spell=sid)
    b.say(spell["text"], "magic")


@op("stabilize")
def _stabilize(c: Cast, o: dict, victim) -> None:
    x = victim or c.target
    if x is not None:
        x.stable = True
        c.b.say(f"{x.the_name} stops bleeding out.", "good")


@op("restore")
def _restore(c: Cast, o: dict, victim) -> None:
    """Lesser Restoration: one condition ends (the worst first); here it also eases a disease taking hold."""
    x = victim or c.target
    if x is None:
        return
    for cid in o.get("conditions", ()):
        if cid in x.conditions:
            durations.remove(x, cid)
            x.save_ends = [se for se in x.save_ends if se["cond"] != cid]
            if o.get("one"):
                break
    if o.get("disease") and x.char:
        x.char.conditions = [k for k in x.char.conditions if not k.startswith("exposed:")]
    c.b.say(f"{x.the_name} looks clearer.", "good")


@op("revive")
def _revive(c: Cast, o: dict, victim) -> None:
    b, f = c.b, c.caster
    x = victim or c.target
    if x is None or x.state != "dead" or x.char is None:
        return
    item = next((i for i in f.char.inventory if i.def_id == o.get("consumes")), None) if f.char else None
    if o.get("consumes") and item is None:
        return
    if item is not None:
        remove_item(f.char, item.uid, 1)
    x.state = "fighting"
    x.char.alive = True
    x.char.death_cause = None  # (or the body would be found dead of it again as time passed)
    x.hp = int(o.get("hp", 1))
    x.conditions = {"prone": -1}
    x.cond_ends = {}
    x.death_saves = [0, 0]
    b._event("heal", to=x.id, amount=x.hp)
    b.say(f"{x.the_name} draws a ragged breath.", "magic")


@op("identify")
def _identify(c: Cast, o: dict, victim) -> None:
    pass  # outside a fight only (game/magic.py)


@op("special")
def _special(c: Cast, o: dict, victim) -> None:
    SPECIAL[o["handler"]](c, o, victim)


@op("gain_action")
def _gain_action(c: Cast, o: dict, victim) -> None:
    """One more action this turn (Action Surge)."""
    c.caster.action += int(o.get("count", 1))


@op("say")
def _say(c: Cast, o: dict, victim) -> None:
    f = victim or c.caster
    c.b.say(o["text"].replace("{name}", f.the_name).replace("{their}", f.possessive), o.get("style", "info"))


# ---------------------------------------------------------------------------- things left on the field
@op("zone")
def _zone(c: Cast, o: dict, victim) -> None:
    from realmwalker.rules.combat import Zone

    b, f, spell = c.b, c.caster, c.spell
    rounds = -1 if spell.get("concentration") else int(o.get("rounds", spell.get("rounds", 10)))
    z = Zone(b._zone_id(), o["zone"], set(c.area), owner=f.id, spell=c.sid, rounds=rounds, save=o.get("save", "dex"),
             dc=int(o.get("dc", c.dc)))  # (caltrops and ball bearings have the book's own DC)
    b._add_zone(z)
    if o.get("catch"):
        for x in b.in_area(c.area, spell.get("affects", "all"), f):
            b._zone_catch(x, z)


@op("aura")
def _aura(c: Cast, o: dict, victim) -> None:
    from realmwalker.rules.combat import Zone

    b, f, spell = c.b, c.caster, c.spell
    dice_, dtype, up = spellrules.damage_parts(o)[0]
    z = Zone(b._zone_id(), "guardians", set(), owner=f.id, spell=c.sid,
             rounds=-1 if spell.get("concentration") else int(spell.get("rounds", 10)), radius=int(o["radius"]) // 5,
             save=o["ability"], dc=c.dc, damage=expr(c, dice_, up), damage_type=dtype,
             on_save="half" if o.get("half") else "none", friends_safe=True)
    b._add_zone(z)
    b._follow_auras()


@op("guardian")
def _guardian(c: Cast, o: dict, victim) -> None:
    from realmwalker.rules.combat import Token, Zone

    b, f, spell, point = c.b, c.caster, c.spell, c.point
    if point is None:
        return
    tok = Token(b._zone_id(), "guardian", point[0], point[1], f.id, rounds=int(spell.get("rounds", 10)), spell=c.sid)
    b.tokens.append(tok)
    b._event("token", id=tok.id, what=tok.kind, x=tok.x, y=tok.y, owner=f.id)
    r = int(o["radius"]) // 5
    cells = {(x, y) for x in range(point[0] - r, point[0] + r + 1) for y in range(point[1] - r, point[1] + r + 1)
             if b.field.in_bounds(x, y)}
    dice_, dtype, up = spellrules.damage_parts(o)[0]
    z = Zone(b._zone_id(), "guardian", cells, owner=f.id, spell=c.sid, rounds=int(spell.get("rounds", 10)), radius=r,
             centre=point, save=o["ability"], dc=c.dc, damage=expr(c, dice_, up), damage_type=dtype,
             on_save="half" if o.get("half") else "none", friends_safe=True, budget=int(o.get("budget", 60)))
    z.token = tok.id  # type: ignore[attr-defined]
    b._add_zone(z)


@op("summon")
def _summon(c: Cast, o: dict, victim) -> None:
    from realmwalker.rules.combat import Token, signed_mod

    b, f, spell, point = c.b, c.caster, c.spell, c.point
    if point is None:
        return
    dice_, dtype, up = spellrules.damage_parts(o)[0]
    tok = Token(b._zone_id(), o.get("token", "spiritual_weapon"), point[0], point[1], f.id,
                rounds=-1 if spell.get("concentration") else int(spell.get("rounds", 10)),
                damage=expr(c, dice_, up) + (signed_mod(c.mod) if o.get("add_mod") else ""), bonus=c.bonus,
                damage_type=dtype, spell=c.sid)
    b.tokens = [t for t in b.tokens if not (t.owner == f.id and t.kind == tok.kind)]
    b.tokens.append(tok)
    b._event("token", id=tok.id, what=tok.kind, x=tok.x, y=tok.y, owner=f.id)
    near = [e for e in b.enemies_of(f) if grid.gap((tok.x, tok.y, 1), e.space) <= 1]
    if near:
        b._spirit_strike(f, tok, min(near, key=lambda e: e.hp))


@op("teleport")
def _teleport(c: Cast, o: dict, victim) -> None:
    b, f, point = c.b, c.caster, c.point
    if point is not None:
        start = (f.x, f.y)
        f.x, f.y = point
        b._event("teleport", who=f.id, path=[start, point])
        b._sync_grapples(f)
        b.say(f"{f.the_name} steps through the mist and is somewhere else.", "magic")
