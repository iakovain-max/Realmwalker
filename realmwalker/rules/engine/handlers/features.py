"""Race traits and class features that step in during a fight."""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules import spells as spellrules
from realmwalker.rules.engine.events import handler


# ---------------------------------------------------------------------------- rolls
@handler("lucky")
def lucky(b, f, ev, hook, buff) -> None:
    """Halflings: a natural 1 on an attack roll is rolled again."""
    if ev.roll == "attack" and ev.natural == 1 and f.char is not None:
        ev.natural = dice.d20(b.rng).natural
        b.dice_say(f"{f.name} is lucky: rerolls the 1 and gets {ev.natural}.")


@handler("indomitable")
def indomitable(b, f, ev, hook, buff) -> None:
    """A fighter refuses a failed saving throw, once a day."""
    if ev.roll != "save" or ev.ok or f.char is None or f.char.uses.get("indomitable", 1) <= 0:
        return
    f.char.uses["indomitable"] = 0
    again = dice.d20(b.rng).natural + ev.bonus
    ev.ok = again >= ev.dc
    b.dice_say(f"{f.name} is indomitable and tries again: {again} vs DC {ev.dc} — {'saved' if ev.ok else 'failed'}")
    if ev.ok:
        b.say(f"{f.the_name} will not give way.", "good")


# ---------------------------------------------------------------------------- attacks
@handler("guided_strike")
def guided_strike(b, f, ev, hook, buff) -> None:
    """The war god's hand on a blow that would have missed (+10), at the price of the Channel Divinity."""
    c = f.char
    if c is None or ev.natural == 1 or ev.total + 10 < ev.ac or ev.opt.kind not in ("melee", "ranged"):
        return
    if c.uses.get("channel_divinity", 0) <= 0 or any(x.kind == "undead" for x in b.enemies_of(f)):
        return
    c.uses["channel_divinity"] = 0
    ev.total += 10
    ev.hit = True
    b.say(f"<magic>{f.the_name}'s god guides the blow home.</>", "magic")


@handler("assassinate")
def assassinate(b, f, ev, hook, buff) -> None:
    """The Cutthroat: a blow at someone who has not seen it coming is a critical hit."""
    if ev.target.surprised and f.char is not None:
        ev.crit = True


@handler("savage_attacks")
def savage_attacks(b, f, ev, hook, buff) -> None:
    if ev.crit and f.char is not None and ev.opt.is_melee:
        ev.extra += b.rng.randint(1, ev.sides)


@handler("sneak_attack")
def sneak_attack(b, f, ev, hook, buff) -> None:
    """Once a turn: a finesse or ranged weapon, and advantage or a friend beside the target."""
    c, target, opt = f.char, ev.target, ev.opt
    if c is None or c.uses.get("sneak_round") == b.round:
        return
    if opt.kind not in ("melee", "ranged") or opt.kind == "melee" and "finesse" not in opt.properties:
        return
    from realmwalker.rules.engine import query

    ally_beside = any(x is not f and x.standing and not query.incapacitated(x) and b.gap(x, target) <= 1
                      for x in b.allies_of(f))
    if not (ev.advantage or ally_beside):
        return
    c.uses["sneak_round"] = b.round
    n = (c.level + 1) // 2
    ev.extra += dice.roll(f"{n}d6", b.rng, double_dice=ev.crit).total
    b.say(f"{f.the_name} finds the gap.", "good")


@handler("divine_strike")
def divine_strike(b, f, ev, hook, buff) -> None:
    if f.char is not None and ev.opt.kind in ("melee", "ranged"):
        ev.extra += dice.roll("1d8", b.rng, double_dice=ev.crit).total


# ---------------------------------------------------------------------------- damage
@handler("uncanny_dodge")
def uncanny_dodge(b, f, ev, hook, buff) -> None:
    """A rogue rolls with a blow they see coming, once a round: half the damage."""
    att = ev.actor
    if ev.stage != "blow" or f.char is None or att is None or f.uncanny_used_round == b.round:
        return
    if not f.standing or not b.can_see(f, att):
        return
    f.uncanny_used_round = b.round
    f.reaction = False
    ev.amount = max(1, ev.amount // 2)
    b.say(f"{f.the_name} rolls with the blow.", "good")


def make_ward(b, f, level: int) -> None:
    """An abjurer's Arcane Ward: made by the first abjuration of the day, strengthened by each after."""
    c = f.char
    if c is None or level < 1 or "arcane_ward" not in _traits(f):
        return
    most = 2 * c.level + f.mod("int")
    if not c.uses.get("ward_made"):
        c.uses["ward_made"] = 1
        c.uses["arcane_ward"] = most
        b.say(f"<magic>A shimmering ward settles over {f.the_name}.</>", "magic")
    else:
        c.uses["arcane_ward"] = min(most, c.uses.get("arcane_ward", 0) + 2 * level)


def _traits(f):
    from realmwalker.rules.engine import traits

    return traits.of(f)


@handler("arcane_ward")
def arcane_ward(b, f, ev, hook, buff) -> None:
    if ev.spell.get("school") == "abjuration":
        make_ward(b, f, ev.level)


def _soak(b, w, ev, projected: bool) -> None:
    left = w.char.uses["arcane_ward"]
    took = min(left, ev.amount)
    w.char.uses["arcane_ward"] = left - took
    ev.amount -= took
    if projected:
        w.reaction = False
    b.say(f"<magic>{w.the_name}'s ward takes {took} of it{' over ' + ev.target.the_name if projected else ''}.</>", "magic")
    if ev.amount <= 0:
        ev.stop = True


@handler("ward_soak")
def ward_soak(b, f, ev, hook, buff) -> None:
    if ev.stage == "hp" and f.char is not None and f.char.uses.get("arcane_ward", 0) > 0 and ev.amount > 0:
        _soak(b, f, ev, False)


@handler("projected_ward")
def projected_ward(b, f, ev, hook, buff) -> None:
    from realmwalker.rules.engine import query

    if ev.stage != "hp" or f.char is None or ev.amount <= 0 or f.char.uses.get("arcane_ward", 0) <= 0:
        return
    if b.feet(f, ev.target) > 30 or query.incapacitated(f):
        return
    _soak(b, f, ev, True)


@handler("evasion")
def evasion(b, f, ev, hook, buff) -> None:
    """Out of the way of an area: nothing on a successful Dexterity save, half on a failed one."""
    if ev.ability == "dex" and f.char is not None:
        ev.amount = 0 if ev.saved else ev.full // 2


# ---------------------------------------------------------------------------- falling
@handler("death_ward")
def death_ward(b, f, ev, hook, buff) -> None:
    if buff in f.buffs:
        f.buffs.remove(buff)
    if buff.get("lasting") and f.char:
        spellrules.end(f.char, buff["lasting"])  # spent: it does not come into the next fight
    f.hp = 1
    b.say(f"<magic>The ward over {f.the_name} takes the blow instead.</>", "good")
    ev.survived = ev.stop = True


@handler("relentless_endurance")
def relentless_endurance(b, f, ev, hook, buff) -> None:
    if f.char is not None and f.char.uses.get("relentless_endurance"):
        f.char.uses["relentless_endurance"] = 0
        f.hp = 1
        b.say(f"{f.the_name} should be down, and is not.", "good")
        ev.survived = ev.stop = True


# ---------------------------------------------------------------------------- healing
@handler("disciple_of_life")
def disciple_of_life(b, f, ev, hook, buff) -> None:
    ev.amount += 2 + max(1, ev.level)
