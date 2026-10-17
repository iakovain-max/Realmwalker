"""The Battle Master (PHB 2024, Fighter subclass; Expansion 4 Part A): superiority dice and the twenty maneuvers.

The pool is `char.uses["superiority"]` (data/traits.json combat_superiority: four, five from level 7, six from 15; back
after a short rest); the die is a d8, a d10 from Improved Combat Superiority, a d12 from Ultimate (`sides`). Relentless
rolls a free d8 for the first maneuver of each turn (`roll_die`). A character knows a maneuver when its id
("maneuver_trip_attack") is among its features, so each maneuver is a kernel trait.

One maneuver an attack. The blows' maneuvers are chosen on `attack_damage` (`maneuver_blow`: the die is added there;
the battle's judgement for the Auto, `tactics.maneuver`, asked of the player as the Reactions setting says) and take
hold on `attack_done` (`maneuver_after`), after the blow's damage, with a save against 8 + the better of Strength and
Dexterity + proficiency (`dc_of`). Precision Attack is a miss turned (`attack_missed`), Parry a blow lessened
(`damage_incoming`), Riposte a blow back (`attack_done` as the target), each with the reaction. The bonus-action
maneuvers and Commander's Strike, Bait and Switch and Know Your Enemy are abilities (`actions.options`); a die they
promise for a later hit waits as the buff `maneuver_die` (events.BUFF_HOOKS). Ambush is read at Initiative
(`Battle.start`) and, with Commanding Presence and Tactical Assessment, on a failed check (`check_die`, from
`camp.check`, `Battle.check` and `dialogue.check`).
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules.engine import durations, query
from realmwalker.rules.engine import resources as res
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.events import handler
from realmwalker.rules.engine.handlers.mastery import _turn_key
from realmwalker.rules.engine.reactions import Decision, ask, yes

# The maneuvers that ride on a hit, in the order they are offered.
ON_HIT = ("trip_attack", "pushing_attack", "menacing_attack", "goading_attack", "distracting_strike",
          "sweeping_attack", "disarming_attack", "maneuvering_attack")
WORDS = {"trip_attack": "trip", "pushing_attack": "push", "menacing_attack": "menace", "goading_attack": "goad",
         "distracting_strike": "distract", "sweeping_attack": "sweep on", "disarming_attack": "disarm",
         "maneuvering_attack": "move a friend"}
# The checks a maneuver adds its die to (outside a fight and in one).
CHECKS = {"stealth": "ambush", "intimidation": "commanding_presence", "performance": "commanding_presence",
          "persuasion": "commanding_presence", "history": "tactical_assessment",
          "investigation": "tactical_assessment", "insight": "tactical_assessment"}
_SMALL_ENOUGH = ("tiny", "small", "medium", "large")


def _word(f) -> str:
    return "good" if f.side == "party" else "info"


def knows(f, m: str) -> bool:
    return f.has_trait(f"maneuver_{m}")


def sides(f) -> int:
    if f.has_trait("ultimate_combat_superiority"):
        return 12
    return 10 if f.has_trait("improved_combat_superiority") else 8


def char_sides(char, tables) -> int:
    from realmwalker.rules.engine import traits as tr

    have = tr.of_char(char, tables)
    return 12 if "ultimate_combat_superiority" in have else 10 if "improved_combat_superiority" in have else 8


def dc_of(f) -> int:
    return 8 + max(f.mod("str"), f.mod("dex")) + query.proficiency(f)


def dice_left(f) -> int:
    return res.left(f.char, "superiority") if f.char is not None else 0


def _free_die(b, f) -> bool:
    """Relentless: the first maneuver of a turn rolls a d8 of its own."""
    return f.has_trait("bm_relentless") and f.__dict__.get("relentless_turn") != _turn_key(b)


def ready(b, f) -> bool:
    return f.char is not None and f.has_trait("combat_superiority") and (dice_left(f) > 0 or _free_die(b, f))


def roll_die(b, f, what: str) -> int:
    """Spend a superiority die (or Relentless's free d8) and roll it."""
    if _free_die(b, f):  # (the turn's first maneuver keeps the dice: a d8 of its own)
        f.__dict__["relentless_turn"] = _turn_key(b)
        n, how = 8, "Relentless"
    else:
        res.spend(f.char, "superiority")
        n, how = sides(f), f"{dice_left(f)} left"
    v = dice.roll(f"1d{n}", b.rng).total
    b.dice_say(f"{f.name} ({what}): superiority die d{n} = {v} ({how})")
    b._event("maneuver", who=f.id, what=what)
    return v


def _avg(expr: str) -> float:
    n, s, flat = dice.parse(expr)
    return n * (s + 1) / 2 + flat


def _small_enough(t) -> bool:
    return t.size in _SMALL_ENOUGH


# ---------------------------------------------------------------------------- the blows' maneuvers
def blows_open(b, f, target, opt) -> list[str]:
    """The maneuvers this hit could carry."""
    weapon = opt.kind in ("melee", "ranged") and not opt.kind.startswith("spell")
    out = []
    for m in ON_HIT:
        if not knows(f, m):
            continue
        if m in ("trip_attack", "pushing_attack") and (not weapon or not _small_enough(target)):
            continue
        if m == "trip_attack" and "prone" in target.conditions:
            continue
        if m == "sweeping_attack" and (not opt.is_melee or not sweep_targets(b, f, target, opt)):
            continue
        if m == "disarming_attack" and not held_weapon(target):
            continue
        if m == "maneuvering_attack" and not friends_to_move(b, f, target):
            continue
        out.append(m)
    return out


def sweep_targets(b, f, target, opt) -> list:
    return [x for x in b.enemies_of(f) if x is not target and x.active and b.gap(x, target) <= 1
            and b.in_reach(f, opt, x)[0]]


def held_weapon(t) -> str:
    """The name of the weapon a creature holds in its stat block's attacks ("" if none it could drop)."""
    if t.char is not None:
        it = t.char.equipped_item("main_hand")
        return it.name if it is not None else ""
    items = t.t.items
    for a in (t.cdef or {}).get("attacks", ()):
        key = str(a.get("name", "")).lower().replace(" ", "_")
        d = items.get(key) if key in items else None
        if d and d.get("category") == "weapon":
            return a["name"]
    return ""


def friends_to_move(b, f, target) -> list:
    return [x for x in b.allies_of(f) if x is not f and x.active and x.reaction and not query.incapacitated(x)
            and b.gap(x, target) <= 1 and x.speed >= 10]


@handler("maneuver_blow")
def maneuver_blow(b, f, ev, hook, buff) -> None:
    """A hit: one maneuver may ride on it (unless Precision Attack, a feint or a lunge was this attack's)."""
    if f.__dict__.pop("maneuver_this_attack", False) or ev.target is None or not ready(b, f):
        return
    t, opt = ev.target, ev.opt
    opts = blows_open(b, f, t, opt)
    if not opts:
        return
    from realmwalker.rules import tactics

    best = tactics.maneuver(b, f, t, opts)
    choices = [(m, f"{WORDS[m].capitalize()} ({b.t.classes['fighter']['options']['maneuver_' + m]['name']})")
               for m in opts] + [("none", "No maneuver")]
    got = ask(b, Decision(f, "maneuver", f"{f.name} hits {t.the_name}. A maneuver? ({dice_left(f)} superiority "
                          "dice)", choices, default=best or "none", free=True))
    if got in (None, "none") or got not in opts:
        return
    v = roll_die(b, f, b.t.classes["fighter"]["options"]["maneuver_" + got]["name"])
    ev.extra += v
    f.__dict__["maneuver"] = (t.id, got, v, ev.natural + opt.bonus)


@handler("maneuver_after")
def maneuver_after(b, f, ev, hook, buff) -> None:
    """The blow's maneuver takes hold once its damage is dealt."""
    f.__dict__.pop("maneuver_this_attack", None)
    got = f.__dict__.pop("maneuver", None)
    t = ev.target
    if got is None or t is None or got[0] != t.id:
        return
    _, m, v, total = got
    dc = dc_of(f)
    if m == "sweeping_attack":
        near = [x for x in sweep_targets(b, f, t, ev.opt) if total >= b.target_ac(f, x, ev.opt)[0]]
        if near:
            x = min(near, key=lambda x: (x.hp, x.id))
            b.say(f"{f.the_name}'s blow carries on into {x.the_name}.", _word(f))
            b._hit(f, x, v, ev.opt.damage_type, crit=False, weapon=ev.opt.name)
        return
    if m == "maneuvering_attack":
        _move_friend(b, f, t)
        return
    if not t.active or t.state == "dead":
        return
    if m == "trip_attack":
        if t.standing and not b._save(t, "str", dc, against=("prone",)) and durations.give(b, t, "prone", source=f):
            b._event("prone", who=t.id)
            b.say(f"{t.the_name} is swept off {t.possessive if t.char else 'its'} feet.", _word(f))
    elif m == "pushing_attack":
        if not b._save(t, "str", dc) and b._push(f, t, 3):
            b.say(f"{t.the_name} is driven back.", _word(f))
    elif m == "menacing_attack":
        if not b._save(t, "wis", dc, against=("frightened",)) and durations.give(
                b, t, "frightened", ends=durations.until(b, f, "turn_end"), source=f):
            b._event("condition", who=t.id, cond="frightened")
            b.say(f"{t.the_name} falters before {f.the_name}.", _word(f))
    elif m == "goading_attack":
        if not b._save(t, "wis", dc, against=("charmed",)):
            durations.buff(t, {"goaded": f.id, "source": f"goaded:{f.id}"}, durations.until(b, f, "turn_end"))
            b.say(f"{t.the_name} has eyes only for {f.the_name}.", _word(f))
    elif m == "distracting_strike":
        durations.buff(t, {"exposed": f.id, "source": f"exposed:{f.id}"}, durations.until(b, f, "turn_start"))
        b.say(f"{t.the_name} turns to {f.the_name}, open to the others.", _word(f))
    elif m == "disarming_attack":
        what = held_weapon(t)
        if what and not b._save(t, "str", dc):
            durations.buff(t, {"disarmed": what, "source": "disarmed"}, durations.until(b, t, "turn_start"))
            b._event("disarm", who=t.id, what=what)
            b.say(f"{t.the_name}'s {what.lower()} goes to the ground.", _word(f))


def _move_friend(b, f, target) -> None:
    """Maneuvering Attack: the friend in most danger beside the foe steps away with their reaction, half their speed,
    to the square where fewest foes can reach them."""
    from realmwalker.rules import grid

    near = friends_to_move(b, f, target)
    if not near:
        return
    x = min(near, key=lambda x: (x.hp / max(1, x.max_hp), x.id))
    tree = b.move_tree(x, x.speed // 2)
    occ = b.occupied_by_others(x)
    foes = [e for e in b.enemies_of(x) if e.standing]

    def danger(sq):
        return (sum(1 for e in foes if grid.gap((sq[0], sq[1], x.sq), e.space) <= 1),
                -grid.gap((sq[0], sq[1], x.sq), target.space))
    stops = [sq for sq in tree if sq != (x.x, x.y) and grid.can_stop(sq, x.sq, occ)]
    if not stops:
        return
    dest = min(stops, key=lambda sq: (danger(sq), sq))
    if danger(dest) >= danger((x.x, x.y)):
        return
    x.reaction = False
    b.walk(x, grid.route(tree, dest), free=True)
    b.say(f"At {f.the_name}'s word {x.the_name} slips clear.", _word(f))


# ---------------------------------------------------------------------------- Precision Attack
@handler("precision_attack")
def precision_attack(b, f, ev, hook, buff) -> None:
    """A miss: the die added to the roll, if it could be enough."""
    if ev.hit or ev.target is None or ev.natural == 1 or not ready(b, f) or ev.total + sides(f) < ev.ac:
        return
    need = ev.ac - ev.total
    if not yes(b, Decision(f, "precision_attack", f"{f.name}'s attack misses {ev.target.the_name} ({ev.total} against "
                           f"AC {ev.ac}). Precision Attack: add a superiority die? ({dice_left(f)} left)",
                           [("yes", "Add the die"), ("no", "Let it miss")],
                           default="yes" if need <= (sides(f) + 1) // 2 + 1 else "no")):
        return
    v = roll_die(b, f, "Precision Attack")
    ev.total += v
    ev.hit = ev.total >= ev.ac
    f.__dict__["maneuver_this_attack"] = True
    if ev.hit:
        b.say(f"{f.the_name} finds the line at the last moment.", _word(f))


# ---------------------------------------------------------------------------- Parry and Riposte
@handler("bm_parry")
def bm_parry(b, f, ev, hook, buff) -> None:
    """A melee blow that hurts: the reaction and a die take some of it."""
    att = ev.actor
    if att is None or ev.stage != "blow" or not b.__dict__.get("_melee_blow") or ev.amount <= 0 or not ready(b, f) \
            or not f.reaction or query.incapacitated(f):
        return
    cut = max(f.mod("str"), f.mod("dex"))
    worth = ev.amount >= max(6, (sides(f) + 1) // 2 + cut) or ev.amount >= f.hp
    if not yes(b, Decision(f, "parry", f"{att.the_name} lands a blow on {f.name} ({ev.amount}). Parry: a superiority "
                           f"die plus {cut} off it? ({dice_left(f)} left; your reaction)",
                           [("yes", "Parry"), ("no", "Take it")], default="yes" if worth else "no")):
        return
    f.reaction = False
    v = roll_die(b, f, "Parry")
    ev.amount = max(0, ev.amount - v - cut)
    b.say(f"{f.the_name} turns the blow on {f.possessive if f.char else 'its'} blade.", _word(f))


@handler("riposte")
def riposte(b, f, ev, hook, buff) -> None:
    """A foe misses in melee: a blow back with the reaction."""
    att, opt = ev.actor, ev.opt
    if ev.hit or att is None or opt is None or not opt.is_melee or att.team == f.team or not att.active \
            or not f.active or not f.reaction or query.incapacitated(f) or not ready(b, f):
        return
    blows = [o for o in b.attack_options(f) if o.is_melee and o.available and b.in_reach(f, o, att)[0]
             and not o.extra.get("bonus_action")]
    if not blows:
        return
    if not yes(b, Decision(f, "riposte", f"{att.the_name} misses {f.name}. Riposte: strike back with a superiority "
                           f"die? ({dice_left(f)} left; your reaction)", [("yes", "Riposte"), ("no", "Hold")],
                           default="yes")):
        return
    f.reaction = False
    o = max(blows, key=lambda o: _avg(o.damage) + o.bonus)
    v = roll_die(b, f, "Riposte")
    durations.buff(f, {"maneuver_die": v, "against": att.id, "source": "riposte"})
    b.say(f"{f.the_name} answers the miss with steel.", _word(f))
    try:
        b._attack(f, o, att)
    finally:
        f.buffs = [x for x in f.buffs if x.get("source") != "riposte"]
    b._check_end()


# ---------------------------------------------------------------------------- a die promised to a later hit
@handler("maneuver_die")
def maneuver_die(b, f, ev, hook, buff) -> None:
    """A feint's, a lunge's, a commanded strike's or a riposte's die, added to the hit it was for."""
    if buff is None or ev.target is None:
        return
    if buff.get("against") is not None and buff["against"] != ev.target.id:
        return
    if buff.get("melee") and not (ev.opt.is_melee and f.moved_feet >= 5):
        return
    ev.extra += int(buff["maneuver_die"])
    f.buffs = [x for x in f.buffs if x is not buff]
    f.__dict__["maneuver_this_attack"] = True


# ---------------------------------------------------------------------------- the abilities
def superiority_ready(b, f) -> str | None:
    return None if ready(b, f) else "no superiority dice left; rest to recover"


def know_ready(b, f) -> str | None:
    if f.char is None:
        return "not yours"
    return None if res.left(f.char, "know_your_enemy") > 0 or dice_left(f) > 0 else "used; rest to recover"


@special("know_your_enemy")
def know_your_enemy(c, o, victim) -> None:
    b, f = c.b, c.caster
    victim = victim if victim is not None else c.target
    if victim is None or victim.creature is None:
        return
    if res.left(f.char, "know_your_enemy") > 0:
        res.spend(f.char, "know_your_enemy")
    else:
        res.spend(f.char, "superiority")
        b.dice_say(f"{f.name} (Know Your Enemy): a superiority die spent ({dice_left(f)} left)")
    b.known.add(victim.creature.def_id)
    b.say(f"{f.the_name} weighs up {victim.the_name}: {b.what_is_known(victim)}.", "info")


@special("evasive_footwork")
def evasive_footwork(c, o, victim) -> None:
    b, f = c.b, c.caster
    victim = victim if victim is not None else c.target
    v = roll_die(b, f, "Evasive Footwork")
    durations.buff(f, {"ac": v, "source": "evasive_footwork"}, durations.until(b, f, "turn_start"))
    b.say(f"{f.the_name} gives ground light-footed, hard to pin.", "system")


@special("lunging_attack")
def lunging_attack(c, o, victim) -> None:
    b, f = c.b, c.caster
    victim = victim if victim is not None else c.target
    v = roll_die(b, f, "Lunging Attack")
    durations.buff(f, {"maneuver_die": v, "melee": True, "source": "lunge"}, durations.until(b, f, "turn_end"))
    b.say(f"{f.the_name} gathers for a lunge.", "system")


@special("feinting_attack")
def feinting_attack(c, o, victim) -> None:
    b, f = c.b, c.caster
    victim = victim if victim is not None else c.target
    if victim is None:
        return
    v = roll_die(b, f, "Feinting Attack")
    durations.buff(f, {"vex": victim.id, "source": f"feint_adv:{victim.id}"}, durations.until(b, f, "turn_end"))
    durations.buff(f, {"maneuver_die": v, "against": victim.id, "source": "feint"}, durations.until(b, f, "turn_end"))
    b.say(f"{f.the_name} feints at {victim.the_name}.", "system")


@special("rally")
def rally(c, o, victim) -> None:
    b, f = c.b, c.caster
    victim = victim if victim is not None else c.target
    if victim is None:
        return
    v = roll_die(b, f, "Rally") + (f.char.level // 2 if f.char is not None else 0)
    if v > victim.temp_hp:
        victim.temp_hp = v
        b._event("heal", who=victim.id, amount=v, temp=True)
    b.say(f"{f.the_name} rallies {victim.the_name} ({v} to spare).", "good" if f.side == "party" else "info")


@special("bait_and_switch")
def bait_and_switch(c, o, victim) -> None:
    """Swap places with a friend beside you (both of one square), 5 feet of movement, no blows drawn; the die to the
    AC of whichever of the two stands with more foes around them."""
    from realmwalker.rules import grid

    b, f = c.b, c.caster
    victim = victim if victim is not None else c.target
    x = victim
    if x is None or x.sq != f.sq or b.gap(f, x) > 1 or query.incapacitated(x):
        return
    f.move_left -= 5
    v = roll_die(b, f, "Bait and Switch")
    here, there = (f.x, f.y), (x.x, x.y)
    (f.x, f.y), (x.x, x.y) = there, here
    b._event("push", who=f.id, path=[here, there])  # (drawn as each sliding into the other's place)
    b._event("push", who=x.id, path=[there, here])
    foes = [e for e in b.enemies_of(f) if e.standing]
    pressed = max((f, x), key=lambda y: (sum(1 for e in foes if grid.gap(y.space, e.space) <= 1), y is not f))
    durations.buff(pressed, {"ac": v, "source": f"bait:{f.id}"}, durations.until(b, f, "turn_start"))
    b.say(f"{f.the_name} and {x.the_name} change places; {pressed.the_name} is the harder to strike.", "system")


def attack_left(b, f) -> str | None:
    if b.current is not f:
        return "only on your turn"
    return None if f.attacks_left > 0 or f.action > 0 else "no attack left this turn"


@special("commanders_strike")
def commanders_strike(c, o, victim) -> None:
    """One attack of the Attack action given to a friend: their reaction, a blow at once with the die added."""
    b, f = c.b, c.caster
    victim = victim if victim is not None else c.target
    x = victim
    if x is None or not x.reaction or not x.active or query.incapacitated(x):
        return
    blows = [(opt, e) for opt in b.attack_options(x) if opt.available and not opt.extra.get("bonus_action")
             for e in b.targets_for(x, opt) if e.active]
    if not blows:
        b.say(f"{x.the_name} has nothing to strike at.", "system")
        return
    if f.attacks_left <= 0:  # (the attack given up is one of the Attack action's)
        f.action -= 1
        f.attacks_left = query.attacks_per_action(f)
    f.attacks_left -= 1
    v = roll_die(b, f, "Commander's Strike")
    opt, e = max(blows, key=lambda p: (b.hit_chance(x, p[0], p[1]) * (_avg(p[0].damage) + v), -p[1].hp))
    x.reaction = False
    durations.buff(x, {"maneuver_die": v, "against": e.id, "source": "commanded"})
    b.say(f"{f.the_name} calls the stroke, and {x.the_name} strikes.", "good" if f.side == "party" else "info")
    try:
        b._attack(x, opt, e)
    finally:
        x.buffs = [y for y in x.buffs if y.get("source") != "commanded"]
    b._check_end()


# ---------------------------------------------------------------------------- Ambush and the checks
def ambush_initiative(b, f) -> int:
    """Ambush at the start of a fight: the die to Initiative when the roll is poor and dice are to spare (the
    battle's judgement; the player is not asked before the order is known)."""
    if f.char is None or not knows(f, "ambush") or not f.has_trait("combat_superiority") or query.incapacitated(f):
        return 0
    if dice_left(f) < 2 or f.initiative - f.mod("dex") > 10:
        return 0
    res.spend(f.char, "superiority")
    v = dice.roll(f"1d{sides(f)}", b.rng).total
    b.dice_say(f"{f.name} (Ambush): +{v} to Initiative ({dice_left(f)} left)")
    return v


def check_die(char, tables, skill: str, total: int, dc: int, rng) -> tuple[int, str]:
    """A failed check a maneuver covers (Ambush's Stealth, Commanding Presence, Tactical Assessment): the die, spent
    only if it could turn it. Returns the new total and a line for the dice log ("" if nothing was tried)."""
    from realmwalker.rules.engine import traits as tr

    m = CHECKS.get(skill)
    if m is None or total >= dc or res.left(char, "superiority") <= 0:
        return total, ""
    have = tr.of_char(char, tables)
    n = char_sides(char, tables)
    if f"maneuver_{m}" not in have or "combat_superiority" not in have or total + n < dc:
        return total, ""
    res.spend(char, "superiority")
    v = dice.roll(f"1d{n}", rng).total
    name = tables.classes["fighter"]["options"][f"maneuver_{m}"]["name"]
    return total + v, f"{name}: +{v} = {total + v} (a superiority die)"
