"""Race traits and class features that step in during a fight."""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules import spells as spellrules
from realmwalker.rules.engine import reactions
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.events import handler
from realmwalker.rules.engine.reactions import Decision


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
    if not reactions.yes(b, Decision(f, "indomitable", f"{f.the_name} fails a {ev.ability.upper()} save. Use "
                                     "Indomitable to roll it again? (once a day)", [("yes", "Roll again"), ("no", "Accept it")])):
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
    if not reactions.yes(b, Decision(f, "guided_strike", f"{f.the_name}'s blow misses ({ev.total} against AC {ev.ac}). "
                                     "Guided Strike: +10, for the Channel Divinity?", [("yes", "Guide it"), ("no", "Let it miss")])):
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
    if not reactions.yes(b, Decision(f, "uncanny_dodge", f"{att.the_name} hits {f.the_name} for {ev.amount}. Roll with "
                                     "the blow? (your reaction: half the damage)", [("yes", "Uncanny Dodge"), ("no", "Take it")],
                                     free=True)):
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
    if not reactions.yes(b, Decision(f, "projected_ward", f"{ev.target.the_name} is about to take {ev.amount}. Throw "
                                     f"your ward over them? (your reaction; it holds {f.char.uses['arcane_ward']})",
                                     [("yes", "Project the ward"), ("no", "Keep it")])):
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


# ---------------------------------------------------------------------------- abilities used in a fight
@handler("rallying_cry")
def rallying_cry(b, f, ev, hook, buff) -> None:
    """A knight's Second Wind heals the friends around them too."""
    if ev.ability != "second_wind" or f.char is None:
        return
    b.say(f"'To me! On your feet!' {f.the_name}'s shout carries.", "speech")
    for a in b.team(f.team):
        if a is not f and (a.active or a.state == "down") and b.feet(f, a) <= 30:
            b._heal(a, f.char.level)


@special("turn_undead")
def turn_undead(c, o, victim) -> None:
    b, f = c.b, c.caster
    dc = spellrules.save_dc(f.sheet, b.t)
    b.say(f"{f.the_name} raises the holy symbol and speaks the words of banishing.", "magic")
    near = [x for x in b.enemies_of(f) if x.kind == "undead" and b.feet(f, x) <= 30]
    b._event("cast", by=f.id, to=None, spell="turn_undead", effect="burst", dtype="radiant",
             area=[cell for x in near for cell in x.cells])
    for x in near:
        if not b._save(x, "wis", dc):
            if f.has_trait("destroy_undead") and x.cdef["cr"] <= 0.5:
                b._kill(x, "turned to dust", killer=f)
            else:
                x.state = "fleeing"
                b.say(f"{x.the_name} recoils from the light and flees.", "good")


@special("preserve_life")
def preserve_life(c, o, victim) -> None:
    """Five times the cleric's level in healing, shared out: nobody past half their hit points."""
    b, f = c.b, c.caster
    pool = 5 * f.char.level
    near = [a for a in b.team(f.team) if (a.active or a.state == "down") and b.feet(f, a) <= 30]
    for ally in sorted(near, key=lambda a: a.hp / max(1, a.max_hp)):
        if pool <= 0:
            break
        give = min(max(0, ally.max_hp // 2 - ally.hp), pool)
        if give:
            b._heal(ally, give)
            pool -= give
    b.say("Warm light spreads through the wounded.", "magic")


@special("divine_intervention")
def divine_intervention(c, o, victim) -> None:
    from realmwalker.rules.combat import FEARLESS

    b, f = c.b, c.caster
    ch = f.char
    roll = b.rng.randint(1, 100)
    b.dice_say(f"Divine Intervention ({f.name}): {roll} vs {ch.level} or less")
    b.say(f"{f.the_name} cries out to {f.possessive} god.", "magic")
    if roll > ch.level:
        b.say("Nothing answers.", "system")
        return
    ch.uses["divine_answered"] = b.now
    b.say("<magic>And the god answers.</> Light like noon floods the place.", "magic")
    b._event("cast", by=f.id, to=None, spell="divine_intervention", effect="burst", dtype="radiant",
             area=[cell for x in b.fighters if x.active or x.state == "down" for cell in x.cells])
    for a in b.team(f.team):
        if a.state in ("fighting", "down"):
            b._heal(a, a.max_hp)
    dc = spellrules.save_dc(f.sheet, b.t)
    for e in b.enemies_of(f):
        if not b._save(e, "wis", dc):
            e.conditions["frightened"] = 10
            e.sources["frightened"] = f.id
            if e.morale_type not in FEARLESS or e.kind == "undead":
                b._break(e, "flee" if e.kind != "humanoid" else None)


@special("war_priest")
def war_priest(c, o, victim) -> None:
    """A weapon blow with the bonus action, at the weakest in reach (or the one chosen)."""
    b, f = c.b, c.caster
    opts = [x for x in b.attack_options(f) if x.available and x.item_uid is not None]
    targets = [t for x in opts[:1] for t in b.targets_for(f, x)]
    if c.target is not None and c.target in targets:
        targets = [c.target]
    if opts and targets:
        b._attack(f, opts[0], min(targets, key=lambda t: t.hp))
