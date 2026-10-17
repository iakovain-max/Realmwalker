"""The summoned spirits' traits and gifts (Expansion 3 F.2 and F.3, PHB 2024): the slaad's Regeneration, the mind
flayer's Whispering Aura, the putrid spirit's Festering Aura, the construct's Heated Body, Stony Lethargy and Berserk
Lashing, the fey spirit's moods after its Fey Step; the celestial Defender's ward, the demon's Death Throes and the
yugoloth's step. A spirit's DC is its caster's spell save DC (its `spellcasting` numbers, set by
rules/allies.summon_def)."""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules import grid
from realmwalker.rules.engine import durations
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.events import handler


def _dc(f) -> int:
    return int((f.cdef.get("spellcasting") or {}).get("dc", 13))


def _owner_id(f) -> int | None:
    return f.bond.get("owner") if f.bond is not None else None


def _awake(f) -> bool:
    return f.active and not f.incapacitated


@handler("spirit_regeneration")
def spirit_regeneration(b, f, ev, hook, buff) -> None:
    """A slaad spirit: 5 hit points back at the start of its turn, while it has at least 1 (fire or not)."""
    if f.hp <= 0 or f.state != "fighting" or f.buff_value("no_heal"):
        return
    healed = min(int(hook.get("amount", 5)), f.max_hp - f.hp)
    if healed > 0:
        f.hp += healed
        b._event("heal", to=f.id, amount=healed)
        b.say(f"{f.the_name[:1].upper() + f.the_name[1:]}'s flesh knits closed.", "magic")


@handler("whispering_aura")
def whispering_aura(b, f, ev, hook, buff) -> None:
    """At the start of its turn, unless incapacitated: every creature within 5 feet but its caster, a Wisdom save
    or 2d6 psychic (friends too: the book spares only the caster)."""
    if not _awake(f):
        return
    near = [x for x in b.on_field() if x is not f and x.id != _owner_id(f) and x.state in ("fighting", "fleeing", "down")
            and b.gap(f, x) <= 1]
    if near:
        b.say(f"Whispers pour out of {f.the_name}.", "magic")
    for x in near:
        b._save_damage(f, x, "wis", _dc(f), "2d6", "psychic", "none")
        if b.outcome is not None:
            return


@handler("festering_aura")
def festering_aura(b, f, ev, hook, buff) -> None:
    """Any creature but its caster that starts its turn within 5 feet: a Constitution save or Poisoned until the
    start of its next turn."""
    x = ev.actor
    if x is None or x is f or x.id == _owner_id(f) or not f.active or not x.active or b.gap(f, x) > 1:
        return
    if "poisoned" in x.conditions:
        return
    if not b._save(x, "con", _dc(f)):
        if durations.give(b, x, "poisoned", ends=durations.until(b, x, "turn_start"), source=f):
            b.say(f"The stench of {f.the_name} turns {x.the_name}'s stomach.", "info")


@handler("heated_body")
def heated_body(b, f, ev, hook, buff) -> None:
    """A creature that hits it with a melee attack takes 1d10 fire."""
    att, opt = ev.actor, getattr(ev, "opt", None)
    if att is None or att is f or not ev.hit or opt is None or not opt.is_melee or not att.active:
        return
    b.say(f"{att.the_name} is burned by {f.the_name}'s glowing metal.", "info")
    b._hit(f, att, dice.roll("1d10", b.rng).total, "fire", crit=False, weapon="heated body")


@handler("stony_lethargy")
def stony_lethargy(b, f, ev, hook, buff) -> None:
    """A foe starting its turn within 10 feet, where the spirit sees it: a Wisdom save, or until the start of its
    next turn no Opportunity Attacks and half its Speed."""
    x = ev.actor
    if x is None or x.team == f.team or not _awake(f) or not x.active or b.gap(f, x) > 2 or not b.can_see(f, x):
        return
    if b._save(x, "wis", _dc(f)):
        return
    from realmwalker.rules.engine import query

    half = (query.speed(x) // 2) // grid.SQUARE_FT * grid.SQUARE_FT
    ends = durations.until(b, x, "turn_start")
    durations.buff(x, {"no_opportunity": True, "slow": max(5, half), "source": f"lethargy:{f.id}"}, ends)
    b.say(f"{x.the_name} moves as if through wet stone.", "info")


@handler("berserk_lashing")
def berserk_lashing(b, f, ev, hook, buff) -> None:
    """Its reaction when a creature hurts it: a Slam at that creature, if it can reach it."""
    att = ev.actor
    if att is None or att is f or att.team == f.team or not att.active or not _awake(f) or not f.reaction:
        return
    slam = [o for o in b.attack_options(f) if o.is_melee and o.available and b.in_reach(f, o, att)[0]]
    if not slam:
        return
    f.reaction = False
    b.say(f"{f.the_name} lashes back at {att.the_name}.", "info")
    b._attack(f, slam[0], att)
    b._check_end()


@special("fey_mood")
def fey_mood(c, o, victim) -> None:
    """What a fey spirit's Fey Step brings, by its mood: Fuming, Advantage on its next attack this turn; Mirthful, a
    foe it sees within 10 feet saves (Wisdom) or is Charmed for a minute, until it takes damage; Tricksy, magical
    Darkness on a 10-foot cube beside it until its next turn is over (it lifts as the turn after begins)."""
    b, f = c.b, c.caster
    mood = o.get("mood", "fuming")
    if mood == "fuming":
        durations.buff(f, {"aimed": True, "source": "fey_fuming"}, durations.until(b, f, "turn_end"))
        b.say(f"{f.the_name} bares its teeth.", "info")
    elif mood == "mirthful":
        foes = [x for x in b.enemies_of(f) if x.active and b.gap(f, x) <= 2 and b.can_see(f, x)
                and "charmed" not in x.conditions]
        if not foes:
            return
        x = max(foes, key=lambda e: (e.hp, -e.id))  # (the strongest foe near)
        b.say(f"{f.the_name} laughs, and {x.the_name} cannot help smiling back.", "magic")
        if not b._save(x, "wis", c.dc):
            durations.give(b, x, "charmed", rounds=10, source=f, on_damage=True)
    elif mood == "tricksy":
        from realmwalker.rules.combat import Zone

        here = (f.x + f.sq, f.y)
        cells = {(x, y) for x in range(here[0], here[0] + 2) for y in range(here[1], here[1] + 2)
                 if b.field.in_bounds(x, y)}
        if not cells:
            return
        z = Zone(b._zone_id(), "darkness", cells, owner=f.id, spell=c.sid, rounds=1, centre=here, dark=True)
        b._add_zone(z)
        b.say(f"{f.the_name} giggles, and darkness pools beside it.", "magic")


# ---------------------------------------------------------------------------- Expansion 3 F.3
@special("defender_ward")
def defender_ward(c, o, victim) -> None:
    """A celestial Defender's Radiant Mace: itself or a friend it sees within 10 feet of the target gains 1d10
    temporary hit points (the one who needs them most: the most hurt, with the fewest temporary hit points)."""
    b, f = c.b, c.caster
    if victim is None:
        return
    near = [x for x in b.team(f.team) if x.active and b.gap(x, victim) <= 2 and (x is f or b.can_see(f, x))]
    if not near:
        return
    x = max(near, key=lambda y: ((y.max_hp - y.hp) / max(1, y.max_hp) - y.temp_hp / 10.0, y is not f, -y.id))
    amount = dice.roll("1d10", b.rng).total
    if amount > x.temp_hp:
        x.temp_hp = amount
        b._event("buff", who=x.id, spell=c.sid)
        whom = "itself" if x is f else x.the_name
        b.say(f"Light from {f.the_name}'s mace settles on {whom} like armour "
              f"({amount} temporary hit point{'' if amount == 1 else 's'}).", "magic")


@handler("death_throes")
def death_throes(b, f, ev, hook, buff) -> None:
    """A demon spirit falling to 0 or the spell ending: it explodes; everyone within 10 feet makes a Dexterity save
    against its caster's DC, 2d10 fire and the spell's level, half on a save."""
    if f.__dict__.get("throes_done") or f.bond is None:
        return
    f.__dict__["throes_done"] = True
    level = int(f.bond.get("level", 6))
    near = [x for x in b.on_field() if x is not f and x.state in ("fighting", "fleeing", "down") and b.gap(f, x) <= 2
            and b.solid_field().cover(f.space, x.space) != grid.TOTAL]  # (an emanation: total cover keeps it off)
    cells = {(x, y) for x in range(f.x - 2, f.x + f.sq + 2) for y in range(f.y - 2, f.y + f.sq + 2)
             if b.field.in_bounds(x, y)}
    b.say(f"{f.the_name[:1].upper() + f.the_name[1:]} bursts apart in a gout of hellfire!", "danger")
    b._event("cast", by=f.id, to=None, spell="death_throes", effect="burst", dtype="fire", area=sorted(cells),
             point=(f.x, f.y), shape="emanation")
    rolled = dice.roll(f"2d10+{level}", b.rng).total
    for x in near:
        b._save_damage(f, x, "dex", _dc(f), f"2d10+{level}", "fire", "half", rolled=rolled)
        if b.outcome is not None:
            return
    b._check_end()


def _free(b, f, x: int, y: int, occ: set) -> bool:
    return b.field.fits(x, y, f.sq) and not any(c in occ for c in grid.cells(x, y, f.sq))


@handler("yugoloth_step")
def yugoloth_step(b, f, ev, hook, buff) -> None:
    """A yugoloth spirit's Claws, hit or miss: it may teleport up to 30 feet to a space it can see (the game's
    choice: beside the foe hurt worst when its own target fell and no other foe is within reach, or out of a crowd
    when it is bloodied and two or more foes stand beside it)."""
    opt = getattr(ev, "opt", None)
    if opt is None or opt.extra.get("id") != "claws" or not f.active or not f.can_act() or f.bond is None:
        return
    foes = [e for e in b.enemies_of(f) if e.active]
    if not foes:
        return
    occ = b.occupied_by_others(f)
    reach = 6  # (30 feet)
    spots = [(x, y) for x in range(f.x - reach, f.x + reach + 1) for y in range(f.y - reach, f.y + reach + 1)
             if (x, y) != (f.x, f.y) and _free(b, f, x, y, occ) and b.can_see_point(f, x, y)]
    if not spots:
        return
    beside = [e for e in foes if b.gap(f, e) <= 1]
    goal = None
    if not ev.target.active and not beside:
        e = min(foes, key=lambda e: (e.hp, b.gap(f, e)))
        near = [sq for sq in spots if grid.gap((sq[0], sq[1], f.sq), e.space) == 1]
        if near:
            goal = min(near, key=lambda sq: max(abs(sq[0] - f.x), abs(sq[1] - f.y)))
    elif f.hp <= f.max_hp // 2 and len(beside) >= 2:
        def threat(sq):
            return sum(1 for e in foes if grid.gap((sq[0], sq[1], f.sq), e.space) <= 1)

        calm = [sq for sq in spots if threat(sq) == 0]
        if calm:
            goal = min(calm, key=lambda sq: max(abs(sq[0] - f.x), abs(sq[1] - f.y)))
    if goal is None:
        return
    start = (f.x, f.y)
    f.x, f.y = goal
    b._event("teleport", who=f.id, path=[start, goal])
    b._sync_grapples(f)
    b.say(f"{f.the_name[:1].upper() + f.the_name[1:]} folds out of the world and back into it somewhere else.", "magic")
