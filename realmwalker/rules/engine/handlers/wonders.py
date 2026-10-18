"""The wizard's wondrous things in a fight (Expansion 5 Part E, DMG 2024): the Pearl of Power's slot, the Robe of
Stars' step into the Astral Plane and back, the Robe of Eyes' drawback (Light on the robe, Daylight beside it).

- `pearl_problem` / special "pearl_draw": the Magic action, once a day: a spent slot of level 3 or lower back.
- `astral_problem` / special "astral_step": the Magic action takes the wearer off the field (`Battle.send_away`,
  "astral"); at the start of their next turn the Magic action brings them back where they were (`back_from_astral`).
- `after_light(b, caster, sid)`: from `Battle.cast` - a Robe of Eyes Blinds its wearer for a minute.
The Robe of Scintillating Colors is an item spell (robe_colors); the Robe of the Archmagi and the Robe of Eyes' senses
are properties the sheet reads (rules/magic.py)."""

from __future__ import annotations

from realmwalker.rules import magic
from realmwalker.rules.engine import durations
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.handlers.arms import carried, ready, spend, trait_prop


def worn(char, trait: str):
    """A working item with this trait that the character wears (a robe)."""
    if char is None:
        return None
    on = set(char.equipped.values())
    for it in char.inventory:
        if it.uid in on and it.magic and trait_prop(it, trait) is not None and magic.working(char, it):
            return it
    return None


# ---------------------------------------------------------------------------- the Pearl of Power
def pearl_problem(b, f) -> str | None:
    from realmwalker.game import wonders

    pearl = carried(f.char, "pearl_of_power")
    if pearl is None:
        return "no pearl of power"
    if not ready(pearl, "pearl_of_power"):
        return "the pearl was used since the last dawn"
    if wonders.pearl_level(f.char, b.t) is None:
        return "no spent spell slot of the third level or lower"
    return None


@special("pearl_draw")
def pearl_draw(c, o, victim) -> None:
    from realmwalker.game import wonders
    from realmwalker.rules import spells as spellrules

    b, f = c.b, c.caster
    if pearl_problem(b, f):
        return
    pearl = carried(f.char, "pearl_of_power")
    level = wonders.pearl_level(f.char, b.t)
    spend(pearl, "pearl_of_power")
    spellrules.unspend_slot(f.char, level)
    b.say(f"{f.the_name} breathes on the Pearl of Power: a level {level} spell slot comes back.", "magic")


# ---------------------------------------------------------------------------- the Robe of Stars
def astral_problem(b, f) -> str | None:
    if worn(f.char, "robe_of_stars") is None:
        return "no robe of stars worn"
    if f.state != "fighting":
        return "not now"
    return None


@special("astral_step")
def astral_step(c, o, victim) -> None:
    b, f = c.b, c.caster
    if astral_problem(b, f):
        return
    b.say(f"{f.the_name} gathers the robe's stars about them and steps out of the world, into the silver of the "
          "Astral Plane.", "magic")
    b.send_away(f, "astral", by=f)


def back_from_astral(b, f) -> None:
    """At the start of their turn: the Magic action brings them back where they left (or the nearest free place)."""
    b.bring_back(f)
    f.action = 0
    b.say(f"(The Magic action: {f.the_name} steps back out of the Astral Plane.)", "system")


# ---------------------------------------------------------------------------- the Robe of Eyes
def after_light(b, caster, sid: str) -> None:
    """Light cast by a Robe of Eyes' wearer settles on the robe (DC 11); Daylight cast within 5 feet of one (DC 15):
    the wearer is Blinded for a minute, a Constitution save at the end of each of their turns ending it."""
    if sid not in ("light", "daylight"):
        return
    for x in b.fighters:
        if x.char is None or not x.active or worn(x.char, "robe_of_eyes") is None:
            continue
        if sid == "light" and x is not caster:
            continue
        if sid == "daylight" and x is not caster and b.feet(x, caster) > 5:
            continue
        dc = 11 if sid == "light" else 15
        if durations.give(b, x, "blinded", rounds=10):
            x.save_ends.append({"cond": "blinded", "save": "con", "dc": dc, "conc": None})
            b._event("condition", who=x.id, cond="blinded")
            b.say(f"The hundred eyes of {x.the_name}'s robe flare in the {'light' if sid == 'light' else 'daylight'}: "
                  f"{x.the_name} is Blinded.", "danger")
