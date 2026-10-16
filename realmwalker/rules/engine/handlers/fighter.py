"""The 2024 fighter and its paths (PHB chapter 3, Fighter; the Champion; the Knight, Realmwalker's own): what steps in
during a fight. Numbers the battle already works out are read where they are made: the extra attacks
(`query.attacks_per_action`), the critical range (`query.crit_range`), Remarkable Athlete's advantage (`query.
initiative_roll`, `Battle.check`), the Survivor's death saves (`Battle._death_save`), Tactical Master in the mastery
hook (`mastery.mastery_done`) and Tactical Mind on a failed check (`tactical_mind` below, from `camp.check` and
`Battle.check`).
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules.engine import durations
from realmwalker.rules.engine import resources as res
from realmwalker.rules.engine.events import handler
from realmwalker.rules.engine.handlers.mastery import _turn_key


def _word(f) -> str:
    return "good" if f.side == "party" else "info"


def _own_turn(b, f) -> bool:
    return bool(b.order) and b.current is f


def _slip(b, f, feet: int) -> None:
    """Half the speed more to move this turn, drawing no opportunity attacks (Tactical Shift, Remarkable Athlete)."""
    f.move_left += feet
    f.disengaged = True


# ---------------------------------------------------------------------------- Action Surge
@handler("surge_used")
def surge_used(b, f, ev, hook, buff) -> None:
    if ev.ability == "action_surge":
        f.__dict__["surged"] = _turn_key(b)


def surge_ready(b, f) -> str | None:
    return "already used this turn" if f.__dict__.get("surged") == _turn_key(b) else None


# ---------------------------------------------------------------------------- Tactical Shift
@handler("tactical_shift")
def tactical_shift(b, f, ev, hook, buff) -> None:
    """Second Wind with a bonus action: half the speed, slipping away from the foes around them."""
    if ev.ability == "second_wind" and _own_turn(b, f) and f.active:
        _slip(b, f, f.speed // 2)
        b.say(f"{f.the_name} gives ground, watching every blade.", "system")


# ---------------------------------------------------------------------------- Studied Attacks
@handler("studied_attacks")
def studied_attacks(b, f, ev, hook, buff) -> None:
    """A miss teaches: advantage on the next attack at that foe before the end of their next turn."""
    t = ev.target
    if ev.hit or t is None or not t.active:
        return
    durations.buff(f, {"vex": t.id, "source": f"studied:{t.id}"}, durations.until(b, f, "turn_end"))


# ---------------------------------------------------------------------------- the Champion
@handler("athlete_crit")
def athlete_crit(b, f, ev, hook, buff) -> None:
    """Remarkable Athlete: straight after a critical hit, half the speed in a step that draws no blows."""
    if ev.crit and _own_turn(b, f) and f.active and not f.__dict__.get("athlete_moved") == _turn_key(b):
        f.__dict__["athlete_moved"] = _turn_key(b)
        _slip(b, f, f.speed // 2)


@handler("heroic_warrior")
def heroic_warrior(b, f, ev, hook, buff) -> None:
    if f.char is not None and f.active and f.char.uses.get("heroic_inspiration", 0) <= 0:
        f.char.uses["heroic_inspiration"] = 1
        b.dice_say(f"{f.name} (Heroic Warrior): Heroic Inspiration")


@handler("heroic_rally")
def heroic_rally(b, f, ev, hook, buff) -> None:
    """Survivor: bloodied but standing, 5 + the Constitution modifier back at the start of each turn."""
    if f.active and 0 < f.hp <= f.max_hp // 2:
        b._heal(f, max(1, 5 + f.mod("con")))


# ---------------------------------------------------------------------------- the Knight
@handler("knight_unyielding")
def knight_unyielding(b, f, ev, hook, buff) -> None:
    c = f.char
    if c is None or ev.survived or res.left(c, "unyielding") <= 0:
        return
    res.spend(c, "unyielding")
    f.hp = max(1, c.level)
    b.say(f"{f.the_name} staggers, plants {f.possessive} feet, and does not fall.", _word(f))
    ev.survived = ev.stop = True


# ---------------------------------------------------------------------------- Tactical Mind (ability checks)
def tactical_mind(char, tables, total: int, dc: int, rng) -> tuple[int, str]:
    """A failed check: 1d10 from a use of Second Wind (spent only if it turns the check). Returns the new total and a
    line for the dice log ("" if nothing was tried)."""
    from realmwalker.rules.engine import traits as tr

    if total >= dc or res.left(char, "second_wind") <= 0 or total + 10 < dc \
            or "tactical_mind" not in tr.of_char(char, tables):
        return total, ""
    more = dice.roll("1d10", rng).total
    if total + more >= dc:
        res.spend(char, "second_wind")
        return total + more, f"Tactical Mind: +{more} = {total + more}, a use of Second Wind spent"
    return total, f"Tactical Mind: +{more}, still short (nothing spent)"
