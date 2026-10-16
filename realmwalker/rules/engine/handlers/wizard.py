"""The 2024 wizard (PHB pp. 165-177): Overchannel for the Evoker, the Arcane Ward's mending for the Abjurer, and the
Counterspell any wizard may know (Spell Breaker keeps it ready). Sculpt Spells, Empowered Evocation and Potent Cantrip
are read where a spell's damage is made (rules/engine/effects.py); Arcane Ward and Projected Ward are in features.py;
Spell Mastery and Signature Spells are casts without a slot (rules/spells.free_cast)."""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules import spells as spellrules
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.reactions import Decision, yes


# ---------------------------------------------------------------------------- the Abjurer's ward
def ward_most(f) -> int:
    return 2 * f.char.level + f.mod("int")


def mend_problem(b, f) -> str | None:
    """Why the ward cannot be mended with a slot now (Arcane Ward's bonus action)."""
    c = f.char
    if c is None or not c.uses.get("ward_made"):
        return "no ward woven since the last long rest"
    if c.uses.get("arcane_ward", 0) >= ward_most(f):
        return "the ward is whole"
    if spellrules.lowest_free_slot(c, b.t, 1) is None:
        return "no spell slot left"
    return None


@special("ward_mend")
def ward_mend(c, o, victim) -> None:
    """A bonus action: a slot spent, the ward mended by twice its level (the lowest slot that will do)."""
    b, f = c.b, c.caster
    ch = f.char
    want = ward_most(f) - ch.uses.get("arcane_ward", 0)
    slot = spellrules.lowest_free_slot(ch, b.t, 1)
    if slot == 1 and want > 2 and spellrules.lowest_free_slot(ch, b.t, 2) == 2:
        slot = 2  # (a second-level slot when the ward is far gone)
    if slot is None:
        return
    spellrules.spend_slot(ch, slot)
    ch.uses["arcane_ward"] = min(ward_most(f), ch.uses.get("arcane_ward", 0) + 2 * slot)
    b.say(f"<magic>{f.the_name} pours a level {slot} slot into the ward</> (it holds {ch.uses['arcane_ward']}).", "magic")
    b._event("buff", who=f.id, spell="arcane_ward")


# ---------------------------------------------------------------------------- the Evoker's Overchannel
def overchannel_cost(f, level: int) -> str:
    """The necrotic price of the next Overchannel: nothing the first time after a long rest, then 2d12 for each slot
    level, a d12 more each time after."""
    n = f.char.uses.get("overchannel", 0)
    return "" if n == 0 else f"{(n + 1) * level}d12"


def overchannel(b, f, spell: dict, level: int) -> bool:
    """Whether the evoker pours everything into this spell (its damage at its greatest). The battle's judgement: when
    it is free; asked of the player under the Reactions setting."""
    cost = overchannel_cost(f, level)
    text = (f"Overchannel {spell['name']}? Its damage at its greatest" +
            (f"; it costs you {cost} necrotic." if cost else "; free this time (it hurts after this)."))
    if not yes(b, Decision(f, "overchannel", text, [("yes", "Overchannel"), ("no", "Cast it as it is")],
                           default="yes" if not cost else "no")):
        return False
    f.char.uses["overchannel"] = f.char.uses.get("overchannel", 0) + 1
    b.say(f"<magic>{f.the_name} overchannels the spell.</>", "magic")
    if cost:
        f.__dict__["_overchannel_cost"] = cost
    return True


def overchannel_price(b, f) -> None:
    """After the spell: the price, which nothing resists."""
    cost = f.__dict__.pop("_overchannel_cost", "")
    if not cost or not f.active:
        return
    amount = dice.roll(cost, b.rng).total
    b.say(f"<danger>The power tears at {f.the_name} on its way out</> ({amount} necrotic).", "danger")
    b._hit(None, f, amount, "necrotic", crit=False, weapon="overchannel", raw=True)


# ---------------------------------------------------------------------------- Counterspell
def counter_slot(b, x) -> int | None:
    """The slot level a fighter would spend on Counterspell now, or None: a caster who knows it with a level 3 slot
    left, or a creature whose spells name it."""
    if x.char is not None:
        if "counterspell" not in spellrules.known_spells(x.char, b.t) or spellrules.armour_problem(x.char, b.t):
            return None
        return spellrules.lowest_free_slot(x.char, b.t, 3)
    if x.creature is None or "counterspell" not in x.cdef.get("spells", ()):
        return None
    per_day = b._per_day(x, "counterspell")
    if per_day is not None:
        return 3 if per_day > 0 else None
    return next((i + 1 for i in range(2, len(x.slots)) if x.slots[i] > 0), None)


def pay_counter(b, x, slot: int) -> None:
    if x.char is not None:
        spellrules.spend_slot(x.char, slot)
    elif b._per_day(x, "counterspell") is not None:
        b._spend_per_day(x, "counterspell")
    else:
        x.slots[slot - 1] -= 1


def counter_dc(b, x) -> int:
    if x.char is not None:
        return spellrules.save_dc(x.sheet, b.t)
    return int((x.cdef.get("spellcasting") or {}).get("dc", 13))
