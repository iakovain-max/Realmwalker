"""The epic boons (PHB 2024 chapter 5, level 19; data/feats.json category "epic", their traits "feat_boon_of_<id>" in
data/traits.json).

What a boon changes in a number the battle already works out is read where that number is made: Irresistible
Offense in `Battle._ignores_resist`, the Night Spirit's resistance in `Battle._hit`, Energy Resistance in
`query.resists`, Truesight in `Fighter.senses`, Speed in `Sheet.speed`, Fortitude's hit points and Skill's
proficiencies in `feats.grant`. What steps in during a fight is here. Choices that spend something limited (Peerless
Aim, Improve Fate, Energy Redirection, Last Stand) are asked as the Reactions setting says; the enemy and the Auto
take the battle's judgement.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules import feats as featrules
from realmwalker.rules import grid
from realmwalker.rules.engine import durations, query
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.events import handler
from realmwalker.rules.engine.handlers.mastery import once_a_turn
from realmwalker.rules.engine.reactions import Decision, yes


def _word(f) -> str:
    return "good" if f.side == "party" else "info"


def _own_turn(b, f) -> bool:
    return bool(b.order) and b.current is f


def _boon_ability(f, fid: str, default: str) -> str:
    """The ability a boon raised (its "increase" choice)."""
    if f.char is None:
        return default
    for x in featrules.taken(f.char, fid):
        got = (x.get("choices") or {}).get("increase")
        if got:
            return got if isinstance(got, str) else got[0]
    return default


# ---------------------------------------------------------------------------- Combat Prowess
@handler("peerless_aim")
def peerless_aim(b, f, ev, hook, buff) -> None:
    """A missed attack hits instead; then not again until the start of their next turn."""
    if ev.hit or f.__dict__.get("peerless_used") or ev.target is None:
        return
    if not yes(b, Decision(f, "peerless_aim", f"{f.the_name}'s attack misses ({ev.total} against AC {ev.ac}). Peerless "
                           "Aim: make it a hit? (not again until your next turn)", [("yes", "Hit"), ("no", "Let it miss")])):
        return
    f.__dict__["peerless_used"] = True
    ev.hit = True
    ev.total = max(ev.total, ev.ac)
    b.say(f"{f.the_name}'s aim does not fail: the blow finds its mark after all.", _word(f))


@handler("peerless_ready")
def peerless_ready(b, f, ev, hook, buff) -> None:
    f.__dict__.pop("peerless_used", None)


# ---------------------------------------------------------------------------- Dimensional Travel
@handler("blink_ready")
def blink_ready(b, f, ev, hook, buff) -> None:
    """An attack or a spell on their own turn: Blink Steps may follow."""
    if _own_turn(b, f) and f.active and not (ev.kind == "attack_done" and f.attacks_left > 0) \
            and f.__dict__.get("blinked") != _turn(b, f):
        f.__dict__["blink"] = _turn(b, f)


def _turn(b, f) -> tuple:
    return b.round, b.order.index(f.id) if f.id in b.order else -1


def blink_ok(b, f) -> str | None:
    if f.char is None or f.__dict__.get("blink") != _turn(b, f):
        return "only straight after the Attack action or a spell"
    if not _own_turn(b, f):
        return "only on your turn"
    if not blink_squares(b, f):
        return "nowhere to go"
    return None


def blink_squares(b, f) -> list[tuple[int, int]]:
    """Places within 30 feet they can see and stand in, best first: away from the foes beside them, then nearest the
    foes they want to reach (a caster or an archer keeps away)."""
    fld = b.field
    foes = [x for x in b.enemies_of(f) if x.active]
    taken = {c for x in b.fighters if x is not f and x.state != "dead" for c in x.cells}
    keep_away = f.prefers_range
    out = []
    for x in range(f.x - 6, f.x + 7):
        for y in range(f.y - 6, f.y + 7):
            if (x, y) == (f.x, f.y) or not fld.fits(x, y, f.sq):
                continue
            cells = grid.cells(x, y, f.sq)
            if any(c in taken for c in cells):
                continue
            space = (x, y, f.sq)
            if grid.gap(f.space, space) > 6 or fld.cover(f.space, space) == grid.TOTAL:
                continue
            near = [grid.gap(space, e.space) for e in foes] or [99]
            beside = sum(1 for d in near if d <= 1)
            out.append(((beside, -min(near) if keep_away else min(near) if min(near) > 1 else 99, x, y), (x, y)))
    out.sort()
    return [p for _, p in out]


@special("blink_steps")
def blink_steps(c, o, victim) -> None:
    b, f = c.b, c.caster
    places = blink_squares(b, f)
    f.__dict__.pop("blink", None)
    f.__dict__["blinked"] = _turn(b, f)  # (once a turn)
    if not places:
        return
    start = (f.x, f.y)
    f.x, f.y = places[0]
    b._event("teleport", who=f.id, path=[start, places[0]])
    b._sync_grapples(f)
    b.say(f"{f.the_name} blinks out of the world and steps back into it a few strides away.", "magic")


# ---------------------------------------------------------------------------- Energy Resistance
@handler("energy_redirection")
def energy_redirection(b, f, ev, hook, buff) -> None:
    """Hurt by one of their two energies: a reaction turns it on a foe within 60 feet (Dexterity save or 2d12 + Con)."""
    if f.char is None or ev.dtype not in featrules.boon_resists(f.char) or not f.active or f.incapacitated:
        return
    foes = [x for x in b.enemies_of(f) if x.active and b.feet(f, x) <= 60 and b.can_see(f, x)
            and b.field.cover(f.space, x.space) != grid.TOTAL]
    foes = [x for x in foes if query.damage_taken(x, 10, ev.dtype)[0] > 0]
    if not foes:
        return
    t = ev.actor if ev.actor in foes else min(foes, key=lambda x: (x.hp, x.id))
    if not yes(b, Decision(f, "energy_redirection", f"{f.the_name} is struck by {ev.dtype}. Turn it on {t.the_name} "
                           "with your reaction (Energy Redirection)?", [("yes", "Turn it"), ("no", "Let it be")])):
        return
    f.reaction = False
    dc = 8 + f.mod("con") + query.proficiency(f)
    b._event("cast", by=f.id, to=t.id, spell="energy_redirection", effect="attack", look="bolt", dtype=ev.dtype,
             area=list(t.cells), point=None, shape="")
    b.say(f"{f.the_name} gathers the {ev.dtype} that struck home and hurls it at {t.the_name}.", _word(f))
    if b._save(t, "dex", dc):
        b.say(f"{t.the_name} dives clear.", "flavor")
        return
    amount = dice.roll("2d12", b.rng).total + f.mod("con")
    b._hit(f, t, max(1, amount), ev.dtype, crit=False, weapon=ev.dtype)


# ---------------------------------------------------------------------------- Fate
@handler("fate_renewed")
def fate_renewed(b, f, ev, hook, buff) -> None:
    """Improve Fate comes back when a fight begins (rolling initiative)."""
    if f.char is not None:
        f.char.uses["improve_fate"] = 1


def _fate_ready(b, f, other) -> bool:
    return (f.char is not None and f.char.uses.get("improve_fate", 0) > 0 and f.active and not f.incapacitated
            and other is not None and (other is f or b.feet(f, other) <= 60))


def _fate(b, f, text: str) -> int | None:
    """2d4 rolled for Improve Fate, if they choose to (None if not)."""
    if not yes(b, Decision(f, "improve_fate", text + " (Improve Fate: once a fight)", [("yes", "Improve fate"),
                                                                                       ("no", "Let it be")])):
        return None
    f.char.uses["improve_fate"] = 0
    return dice.roll("2d4", b.rng).total


@handler("improve_fate_save")
def improve_fate_save(b, f, ev, hook, buff) -> None:
    """A friend's failed save gets 2d4 more; a foe's save that held gets 2d4 less."""
    if ev.roll != "save" or not _fate_ready(b, f, ev.actor):
        return
    who = ev.actor
    total = ev.natural + ev.bonus
    if who.team == f.team and not ev.ok and ev.dc - total <= 5:
        got = _fate(b, f, f"{who.the_name} fails a {ev.ability.upper()} save by {ev.dc - total}. Add 2d4?")
        if got is not None:
            ev.ok = total + got >= ev.dc
            b.dice_say(f"{f.name} (Improve Fate): +{got} → {total + got} vs DC {ev.dc} — {'saved' if ev.ok else 'failed'}")
    elif who.team != f.team and ev.ok and total - ev.dc < 4 and ev.natural != 20:
        got = _fate(b, f, f"{who.the_name} makes a {ev.ability.upper()} save by {total - ev.dc + 1}. Take 2d4 away?")
        if got is not None:
            ev.ok = total - got >= ev.dc
            b.dice_say(f"{f.name} (Improve Fate): -{got} → {total - got} vs DC {ev.dc} — {'saved' if ev.ok else 'failed'}")


@handler("improve_fate_attack")
def improve_fate_attack(b, f, ev, hook, buff) -> None:
    """A friend's attack that missed by a little gets 2d4 more."""
    att = ev.actor
    if ev.hit or att is None or att.team != f.team or ev.natural == 1 or ev.ac - ev.total > 5 \
            or not _fate_ready(b, f, att):
        return
    got = _fate(b, f, f"{att.the_name}'s attack misses ({ev.total} against AC {ev.ac}). Add 2d4?")
    if got is None:
        return
    ev.total += got
    ev.hit = ev.total >= ev.ac
    b.dice_say(f"{f.name} (Improve Fate): +{got} → {ev.total} vs AC {ev.ac} — {'hit' if ev.hit else 'miss'}")


# ---------------------------------------------------------------------------- Fortitude
@handler("fortified_health")
def fortified_health(b, f, ev, hook, buff) -> None:
    """Healing restores the Constitution modifier more, once a turn."""
    more = f.mod("con")
    if more > 0 and ev.amount > 0 and f.state != "dead" and once_a_turn(b, f, "fortified_health"):
        ev.amount += more


# ---------------------------------------------------------------------------- Irresistible Offense
@handler("overwhelming_strike")
def overwhelming_strike(b, f, ev, hook, buff) -> None:
    """A 20 on the die of an attack: damage equal to the ability score the boon raised."""
    if getattr(ev, "natural", 0) != 20 or f.char is None:
        return
    ability = _boon_ability(f, "boon_of_irresistible_offense", "str")
    more = int(f.char.abilities.get(ability, 10))
    ev.extra += more
    b.dice_say(f"{f.name} (Overwhelming Strike): +{more}")


# ---------------------------------------------------------------------------- Recovery
@handler("last_stand")
def last_stand(b, f, ev, hook, buff) -> None:
    """Once a day, a blow that would drop them leaves them standing with half their hit points."""
    c = f.char
    if c is None or ev.survived or c.uses.get("last_stand", 0) <= 0:
        return
    if not yes(b, Decision(f, "last_stand", f"{f.the_name} is about to fall. Last Stand: stand again with half your "
                           "hit points? (once a day)", [("yes", "Stand"), ("no", "Fall")])):
        return
    c.uses["last_stand"] = 0
    f.hp = 1
    b._heal(f, f.max_hp // 2)
    b.say(f"{f.the_name} will not fall here. Not yet.", _word(f))
    ev.survived = ev.stop = True


def vitality_ok(b, f) -> str | None:
    if f.char is None or f.char.uses.get("vitality_dice", 0) <= 0:
        return "no dice of vitality left"
    return None if f.hp < f.max_hp else "not hurt"


@special("recover_vitality")
def recover_vitality(c, o, victim) -> None:
    """As many of the ten d10s as the hurt needs (about 5.5 each), rolled and healed."""
    b, f = c.b, c.caster
    left = f.char.uses.get("vitality_dice", 0) if f.char else 0
    if left <= 0:
        return
    n = max(1, min(left, -(-(f.max_hp - f.hp) * 2 // 11)))
    f.char.uses["vitality_dice"] = left - n
    amount = dice.roll(f"{n}d10", b.rng).total
    b.dice_say(f"{f.name} (Recover Vitality): {n}d10 = {amount}, {left - n} dice left")
    b.say(f"{f.the_name} draws on a deep well of strength.", _word(f))
    b._heal(f, amount)


# ---------------------------------------------------------------------------- Speed
@special("escape_artist")
def escape_artist(c, o, victim) -> None:
    """Disengaging with the bonus action also slips any grip on them."""
    b, f = c.b, c.caster
    if "grappled" in f.conditions:
        durations.remove(f, "grappled")
        f.grappled_by = None
        b.say(f"{f.the_name} twists out of the hold.", _word(f))


# ---------------------------------------------------------------------------- Spell Recall
@handler("free_casting")
def free_casting(b, f, ev, hook, buff) -> None:
    """A spell cast with a slot of level 1 to 4: a d4 that shows the slot's level keeps it."""
    level = int(getattr(ev, "level", 0) or 0)
    if f.char is None or not 1 <= level <= 4 or not f.char.spells or not getattr(ev, "slotted", True):
        return  # (a cast without a slot - Spell Mastery, a signature spell - keeps none)
    used = f.char.spells.get("slots_used") or []
    if len(used) < level or used[level - 1] <= 0:
        return
    roll = b.rng.randint(1, 4)
    if roll == level:
        used[level - 1] -= 1
        b.dice_say(f"{f.name} (Free Casting): d4 = {roll}, the level {level} slot is kept")
        b.say(f"The spell leaves {f.the_name}'s power whole.", "magic")


# ---------------------------------------------------------------------------- Night Spirit
def in_shadow(b, f) -> str | None:
    if "invisible" in f.conditions:
        return "already unseen"
    return None if b.light_on(f) < grid.BRIGHT else "not in dim light or darkness"


@special("merge_with_shadows")
def merge_with_shadows(c, o, victim) -> None:
    b, f = c.b, c.caster
    if durations.give(b, f, "invisible", night=True):
        b._event("condition", who=f.id, cond="invisible")
        b.say(f"{f.the_name} steps into the shadows and is gone.", _word(f))


@handler("shadow_left")
def shadow_left(b, f, ev, hook, buff) -> None:
    """The shadows let them go when they next act."""
    if getattr(ev, "ability", None) in ("merge_with_shadows", "blink_steps"):
        return
    if (f.cond_ends.get("invisible") or {}).get("night"):
        durations.remove(f, "invisible")
        b.say(f"{f.the_name} comes out of the shadows.", "system")
