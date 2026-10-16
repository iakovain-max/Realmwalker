"""The 2024 rogue and its paths (PHB chapter 3, Rogue; the Thief; the Assassin): Sneak Attack and the Cunning Strikes
bought with its dice, Steady Aim, Stroke of Luck, Thief's Reflexes and the Assassin's first blow.

Sneak Attack is worked out on `attack_damage`; the Cunning Strikes chosen there (the battle's judgement for the Auto
and the enemy, `tactics.cunning_strikes`; asked of the player as the Reactions setting says) take hold on
`attack_done`, after the blow's damage, with a save against 8 + Dexterity + proficiency.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules.engine import durations, query
from realmwalker.rules.engine import resources as res
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.events import handler
from realmwalker.rules.engine.reactions import Decision, ask, yes

# Cunning Strike tricks: their die cost, and the feature that brings them.
TRICKS = {"poison": (1, "cunning_strike"), "trip": (1, "cunning_strike"), "withdraw": (1, "cunning_strike"),
          "stealth": (1, "supreme_sneak"), "daze": (2, "devious_strikes"), "obscure": (3, "devious_strikes"),
          "knock_out": (6, "devious_strikes")}
WORDS = {"poison": "poison the blade", "trip": "trip them", "withdraw": "slip away", "stealth": "stay hidden",
         "daze": "daze them", "obscure": "blind them", "knock_out": "knock them out"}


def _word(f) -> str:
    return "good" if f.side == "party" else "info"


def dc_of(f) -> int:
    return 8 + f.mod("dex") + query.proficiency(f)


def tricks_open(b, f, target, n: int) -> list[str]:
    """The tricks this rogue can buy now with n Sneak Attack dice."""
    out = []
    for t, (cost, feature) in TRICKS.items():
        if cost > n or not f.has_trait(feature):
            continue
        if t == "poison" and not (f.char is not None and any(i.def_id == "poisoners_kit" for i in f.char.inventory)):
            continue
        if t == "trip" and target.size in ("huge", "gargantuan"):
            continue
        if t == "stealth" and not f.__dict__.get("was_hidden"):
            continue
        out.append(t)
    return out


# ---------------------------------------------------------------------------- Sneak Attack
@handler("sneak_attack")
def sneak_attack(b, f, ev, hook, buff) -> None:
    """Once a turn: a finesse or ranged weapon, and advantage or a friend beside the target; some of its dice may buy
    Cunning Strikes; an assassin's first-round blow bites deeper."""
    c, target, opt = f.char, ev.target, ev.opt
    if c is None or c.uses.get("sneak_round") == b.round:
        return
    if opt.kind not in ("melee", "ranged") or opt.kind == "melee" and "finesse" not in opt.properties:
        return
    ally_beside = any(x is not f and x.standing and not query.incapacitated(x) and b.gap(x, target) <= 1
                      for x in b.allies_of(f))
    if not (ev.advantage or ally_beside and not getattr(ev, "disadvantage", False)):
        return
    c.uses["sneak_round"] = b.round
    n = (c.level + 1) // 2
    chosen = choose_tricks(b, f, target, n)
    n -= sum(TRICKS[t][0] for t in chosen)
    if chosen:
        f.__dict__["cunning"] = (target.id, chosen)
    if n > 0:
        ev.extra += dice.roll(f"{n}d6", b.rng, double_dice=ev.crit).total
    b.say(f"{f.the_name} finds the gap.", "good")
    if b.round <= 1 and f.has_trait("assassinate"):
        ev.extra += c.level  # (Assassinate: Surprising Strikes)
        if f.has_trait("death_strike") and target.active and not b._save(target, "con", dc_of(f)):
            ev.double = True
            b.say(f"<danger>{f.the_name}'s first blow is a death stroke.</>" if f.side != "party"
                  else f"{f.the_name}'s first blow is a death stroke.", _word(f))


def choose_tricks(b, f, target, n: int) -> list[str]:
    """The Cunning Strikes bought on this blow (none before level 5)."""
    if not f.has_trait("cunning_strike"):
        return []
    from realmwalker.rules import tactics

    most = 2 if f.has_trait("improved_cunning_strike") else 1
    picked: list[str] = []
    for _ in range(most):
        left = n - sum(TRICKS[t][0] for t in picked)
        opts = [t for t in tricks_open(b, f, target, left) if t not in picked]
        if not opts:
            break
        best = tactics.cunning_strike(b, f, target, opts, left)
        choices = [(t, f"{WORDS[t].capitalize()} ({TRICKS[t][0]}d6)") for t in opts] + [("none", "No trick")]
        got = ask(b, Decision(f, "cunning_strike", f"Sneak Attack on {target.the_name} ({left}d6). A Cunning Strike?",
                              choices, default=best or "none", free=True))
        if got in (None, "none") or got not in opts:
            break
        picked.append(got)
    return picked


@handler("cunning_after")
def cunning_after(b, f, ev, hook, buff) -> None:
    """The Cunning Strikes take hold once the blow's damage is dealt."""
    got = f.__dict__.pop("cunning", None)
    was_hidden = f.__dict__.pop("was_hidden", 0)
    t = ev.target
    if got is None or t is None or got[0] != t.id:
        return
    dc = dc_of(f)
    for trick in got[1]:
        if trick == "withdraw":
            if f.active and b.current is f:
                f.move_left += f.speed // 2
                f.disengaged = True
                b.say(f"{f.the_name} slips away from the blow.", "system")
            continue
        if trick == "stealth":
            f.hidden = was_hidden  # (Supreme Sneak: the blow does not give them away)
            continue
        if not (t.active or t.state == "down") or t.state == "dead":
            continue
        if trick == "poison":
            if not b._save(t, "con", dc, against=("poisoned",)):
                if durations.give(b, t, "poisoned", rounds=10, source=f):
                    t.save_ends.append({"cond": "poisoned", "save": "con", "dc": dc, "conc": None})
                    b._event("condition", who=t.id, cond="poisoned")
                    b.say(f"{t.the_name} is poisoned.", _word(f))
                if f.has_trait("envenom_weapons"):
                    hurt = dice.roll("2d6", b.rng).total
                    b.__dict__["_envenom"] = f
                    try:
                        b._hit(f, t, hurt, "poison", crit=False, weapon="poison")
                    finally:
                        b.__dict__.pop("_envenom", None)
        elif trick == "trip" and t.standing:
            if not b._save(t, "dex", dc, against=("prone",)) and durations.give(b, t, "prone", source=f):
                b._event("prone", who=t.id)
                b.say(f"{t.the_name} goes down.", _word(f))
        elif trick == "daze":
            if not b._save(t, "con", dc):
                durations.buff(t, {"dazed": True, "by": f.id, "source": f"daze:{f.id}"}, durations.until(b, t, "turn_end"))
                b.say(f"{t.the_name} reels, dazed.", _word(f))
        elif trick == "obscure":
            if not b._save(t, "dex", dc, against=("blinded",)) and durations.give(
                    b, t, "blinded", ends=durations.until(b, t, "turn_end"), source=f):
                b._event("condition", who=t.id, cond="blinded")
                b.say(f"{t.the_name} is blinded.", _word(f))
        elif trick == "knock_out":
            if not b._save(t, "con", dc, against=("unconscious",)) and durations.give(
                    b, t, "unconscious", rounds=10, source=f, on_damage=True):
                t.save_ends.append({"cond": "unconscious", "save": "con", "dc": dc, "conc": None})
                b._event("condition", who=t.id, cond="unconscious")
                b.say(f"{t.the_name} drops, senseless.", _word(f))


@handler("dazed")
def dazed(b, f, ev, hook, buff) -> None:
    """Dazed by a Cunning Strike: this turn they may only act (no moving, no bonus action)."""
    durations.buff(f, {"slow": 1000, "source": "dazed_still"}, durations.until(b, f, "turn_end"))  # (no moving)
    f.move_left = 0
    f.bonus = 0
    b.say(f"{f.the_name} is dazed: only one thing this turn.", "system")


# ---------------------------------------------------------------------------- Steady Aim
def not_moved(b, f) -> str | None:
    return "you have moved this turn" if f.moved_feet > 0 else None


@special("steady_aim")
def steady_aim(c, o, victim) -> None:
    b, f = c.b, c.caster
    durations.buff(f, {"aimed": True, "source": "steady_aim"}, durations.until(b, f, "turn_end"))
    if not f.has_trait("roving_aim"):
        f.move_left = 0
    b.say(f"{f.the_name} takes careful aim.", "system")


# ---------------------------------------------------------------------------- Stroke of Luck
def _luck(f) -> bool:
    return f.char is not None and res.left(f.char, "stroke_of_luck") > 0


@handler("stroke_attack")
def stroke_attack(b, f, ev, hook, buff) -> None:
    if ev.hit or not _luck(f) or ev.target is None:
        return
    if not yes(b, Decision(f, "stroke_of_luck", f"{f.the_name}'s attack misses ({ev.total} against AC {ev.ac}). Stroke "
                           "of Luck: make it a 20? (once between rests)", [("yes", "A 20"), ("no", "Let it miss")],
                           default="yes" if b.feet(f, ev.target) <= 120 else "no")):
        return
    res.spend(f.char, "stroke_of_luck")
    ev.total += 20 - ev.natural
    ev.natural = 20
    ev.hit = True
    b.dice_say(f"{f.name} (Stroke of Luck): the roll becomes a 20")


@handler("stroke_save")
def stroke_save(b, f, ev, hook, buff) -> None:
    if ev.roll != "save" or ev.ok or not _luck(f) or 20 + ev.bonus < ev.dc:
        return
    if not yes(b, Decision(f, "stroke_of_luck", f"{f.the_name} fails a {ev.ability.upper()} save. Stroke of Luck: make "
                           "it a 20? (once between rests)", [("yes", "A 20"), ("no", "Accept it")])):
        return
    res.spend(f.char, "stroke_of_luck")
    ev.natural = 20
    ev.ok = True
    b.dice_say(f"{f.name} (Stroke of Luck): the save becomes a 20")


# ---------------------------------------------------------------------------- Thief's Reflexes
@handler("thiefs_reflexes")
def thiefs_reflexes(b, f, ev, hook, buff) -> None:
    """In the first round, the thief acts twice over: a second action, bonus action and move this turn."""
    if b.round <= 1 and f.active and not f.__dict__.get("reflexes_used"):
        f.__dict__["reflexes_used"] = True
        f.action += 1
        f.bonus += 1
        f.move_left += f.speed
        b.say(f"{f.the_name} moves before anyone else can think.", _word(f))
