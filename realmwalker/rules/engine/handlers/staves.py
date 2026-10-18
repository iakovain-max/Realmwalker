"""Wands, staffs and rods (Expansion 5 Part D): the powers of the DMG 2024's wizard's and cleric's things that are more
than a spell cast from their charges (those are `charges` properties drawn from the item's store: rules/magic.py).

    staff_of_striking    a melee hit with it may spend up to 3 charges: 1d6 force more each (the battle's judgement:
                         as many as it takes to fell the foe, all three on a strong one; asked under Reactions "all")
    staff_of_charming    a save against an enchantment aimed at its bearer alone: a failure turned to a success once a
                         day (Resist Enchantment, `resist_enchantment`), a success turned back on the caster with the
                         reaction and a charge (Reflect Enchantment, cast once the spell is done: `after_cast`)
    staff_of_the_magi    Advantage on saves against spells (its trait's modifier); a spell aimed at its bearer alone
                         may be drunk with the reaction, its level added to the charges (past 50 it explodes)
    rod_of_absorption    a spell aimed at its bearer alone that fills no area may be drunk with the reaction, its levels
                         stored (50 in all its life); its bearer spends stored levels as a spent slot back (`draw`,
                         no action, a slot up to level 5 and no higher than their own)
    retributive_strike   the Staff of Power and the Staff of the Magi broken with the Magic action: a 30-foot
                         explosion (Battle: `retribution`)
The Rod of Alertness is a trait's modifiers (Perception, Initiative) and spells; its aura is the item spell
"rod_aura"; the Rod of Rulership is the item spell "rod_rulership"; the Wand of Enemy Detection the mark sense_foes.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules import grid, magic
from realmwalker.rules.engine import query
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.events import handler
from realmwalker.rules.engine.handlers.arms import blade, carried, held, ready, spend, trait_prop
from realmwalker.rules.engine.reactions import Decision, yes

RETRIBUTION_DC = 17
RADIUS_FT = 30


def _left(it) -> int:
    store = magic.pool(it)
    return int(store.get("left", 0)) if store else 0


# ---------------------------------------------------------------------------- the Staff of Striking
@handler("staff_of_striking")
def staff_of_striking(b, f, ev, hook, buff) -> None:
    """A melee hit with the staff: up to 3 charges, 1d6 force more for each."""
    it = blade(f, ev.opt, "staff_of_striking")
    t = ev.target
    if it is None or t is None or not ev.opt.is_melee or not t.active:
        return
    left = _left(it)
    if left <= 0:
        return
    want = 3 if t.hp > 25 else max(1, min(3, -(-t.hp // 7)))  # (enough to fell it, by an average of 3.5 a die)
    n = min(3, left, want)
    if not yes(b, Decision(f, "staff_of_striking", f"{f.name} hits {t.the_name} with the Staff of Striking. Spend "
                           f"{n} of its {left} charges for {n}d6 force more?", [("yes", f"Spend {n}"),
                                                                              ("no", "Not now")],
                           default="yes", free=True)):
        return
    store = magic.pool(it)
    store["left"] = left - n
    ev.typed.append((dice.roll(f"{n}d6", b.rng, double_dice=ev.crit).total, "force"))
    b.say(f"The staff cracks with force as it lands on {t.the_name}.", "magic")
    if f.char is not None:
        for line in magic.drained(f.char, it, b.rng):
            b.say(line, "magic")


# ---------------------------------------------------------------------------- the Staff of Charming
def _enchantment_at_me(b, f):
    """(caster, spell id, spell) of an enchantment being cast at `f` alone, if one is."""
    caster = b.__dict__.get("_casting")
    sid = b.__dict__.get("_casting_sid")
    if caster is None or sid not in b.t.spells or caster is f or caster.side == f.side:
        return None
    sp = b.t.spells[sid]
    if sp.get("school") != "enchantment" or sp.get("area") or int(sp.get("targets", 1)) > 1:
        return None
    return caster, sid, sp


@handler("staff_of_charming")
def staff_of_charming(b, f, ev, hook, buff) -> None:
    """A save against an enchantment aimed at the bearer alone: a failure made a success once a day; a success
    turned back on the caster for the reaction and a charge."""
    if ev.roll != "save" or f.char is None or query.incapacitated(f):
        return
    aimed = _enchantment_at_me(b, f)
    it = carried(f.char, "staff_of_charming")
    if aimed is None or it is None:
        return
    caster, sid, sp = aimed
    if not ev.ok and ready(it, "resist_enchantment") and yes(b, Decision(
            f, "resist_enchantment", f"{f.the_name} fails the save against {sp['name']}. Call on the Staff of "
            "Charming to shake it off? (once a day)", [("yes", "Shake it off"), ("no", "Let it take hold")],
            default="yes")):
        spend(it, "resist_enchantment")
        ev.ok = True
        b.say(f"The Staff of Charming hums, and {sp['name']} slides off {f.the_name}.", "magic")
        return
    if ev.ok and f.reaction and _left(it) > 0 and caster.active and yes(b, Decision(
            f, "reflect_enchantment", f"{f.the_name} resists {sp['name']}. Turn it back on {caster.the_name} with "
            "the Staff of Charming? (the reaction and a charge)", [("yes", "Turn it back"), ("no", "Let it go")],
            default="yes")):
        f.reaction = False
        magic.pool(it)["left"] = _left(it) - 1
        b.__dict__.setdefault("_reflected", []).append((f.id, caster.id, sid))
        for line in magic.drained(f.char, it, b.rng):
            b.say(line, "magic")


def after_cast(b) -> None:
    """Enchantments turned back by a Staff of Charming, cast now that the spell is done, as if the bearer cast them
    (their own save DC)."""
    from realmwalker.rules import spells as spellrules
    from realmwalker.rules.engine import effects

    waiting = b.__dict__.pop("_reflected", None) or []
    for fid, cid, sid in waiting:
        f, caster = b.fighter(fid), b.fighter(cid)
        if f is None or caster is None or not caster.active or f.char is None:
            continue
        sp = b.t.spells[sid]
        s = f.sheet
        b.say(f"<magic>{sp['name']} turns back on {caster.the_name}.</>", "magic")
        effects.cast(b, f, sid, sp, caster, (caster.x, caster.y), up=0,
                     mod=s.mod(spellrules.casting_ability(f.char, b.t)), dc=spellrules.save_dc(s, b.t),
                     bonus=spellrules.attack_bonus(s, b.t), mult=1, level=int(sp["level"]), slotted=False)


# ---------------------------------------------------------------------------- drinking spells
def _single(sp: dict, target) -> bool:
    return target is not None and not sp.get("area") and int(sp.get("targets", 1)) <= 1 and not sp.get("leap") \
        and sp.get("target") in ("enemy", "creature", "ally", "bound")


def absorbed(b, caster, sid: str, sp: dict, target, level: int) -> bool:
    """A spell aimed at a bearer of a Rod of Absorption or a Staff of the Magi alone, drunk with the reaction: it
    does nothing, and its level goes into the thing. True if it was drunk."""
    if not _single(sp, target) or target is caster or target.side == caster.side or target.char is None \
            or not target.reaction or query.incapacitated(target) or level <= 0 or sp.get("ability") \
            or "item" in sp.get("classes", ()):
        return False
    staff = held(target, "staff_of_the_magi")
    rod = carried(target.char, "rod_of_absorption")
    if staff is not None:
        left = _left(staff)
        burst = left + level > 50
        if yes(b, Decision(target, "spell_absorption", f"{caster.the_name} casts {sp['name']} at {target.the_name}. "
                           f"Let the Staff of the Magi drink it? (the reaction; +{level} charges"
                           + (", and the staff would burst" if burst else "") + ")",
                           [("yes", "Drink it"), ("no", "Let it come")], default="no" if burst else "yes")):
            target.reaction = False
            b.say(f"<magic>The Staff of the Magi drinks {caster.the_name}'s {sp['name']}.</>", "magic")
            b._event("countered", who=caster.id, by=target.id, spell=sid)
            if burst:
                retribution(b, target, staff, 6, words="The staff swells with more than it can hold, and bursts.")
            else:
                magic.pool(staff)["left"] = left + level
            return True
    prop = next((p for p in magic.props(rod) if p.get("kind") == "absorb"), None) if rod is not None else None
    if prop is not None and int(prop.get("value", 0)) + level <= int(prop.get("most", 50)) and yes(b, Decision(
            target, "spell_absorption", f"{caster.the_name} casts {sp['name']} at {target.the_name}. Let the Rod of "
            f"Absorption drink it? (the reaction; {level} levels stored)", [("yes", "Drink it"), ("no", "Let it come")],
            default="yes")):
        target.reaction = False
        prop["value"] = int(prop.get("value", 0)) + level
        prop["left"] = int(prop.get("left", 0)) + level
        b.say(f"<magic>The Rod of Absorption drinks {caster.the_name}'s {sp['name']}.</>", "magic")
        b._event("countered", who=caster.id, by=target.id, spell=sid)
        return True
    return False


def draw_level(b, f) -> int | None:
    """The spent slot a Rod of Absorption would give back now: the highest spent one it can pay for, up to 5."""
    from realmwalker.rules import spells as spellrules

    if f.char is None:
        return None
    rod = carried(f.char, "rod_of_absorption")
    prop = next((p for p in magic.props(rod) if p.get("kind") == "absorb"), None) if rod is not None else None
    if prop is None or not spellrules.is_caster(f.char, b.t):
        return None
    total = spellrules.slots_total(f.char, b.t)
    left = spellrules.slots_left(f.char, b.t)
    stored = int(prop.get("left", 0))
    spent = [i + 1 for i in range(min(5, len(total))) if total[i] and left[i] < total[i] and i + 1 <= stored]
    return max(spent) if spent else None


def draw_problem(b, f) -> str | None:
    return None if draw_level(b, f) is not None else "no spent slot the rod's stored levels can pay for"


@special("rod_draw")
def rod_draw(c, o, victim) -> None:
    """A spent slot back from the Rod of Absorption's stored levels."""
    from realmwalker.rules import spells as spellrules

    b, f = c.b, c.caster
    level = draw_level(b, f)
    if level is None:
        return
    rod = carried(f.char, "rod_of_absorption")
    prop = next(p for p in magic.props(rod) if p.get("kind") == "absorb")
    prop["left"] = int(prop.get("left", 0)) - level
    spellrules.unspend_slot(f.char, level)
    b.say(f"{f.the_name} draws {level} levels out of the Rod of Absorption: a level {level} slot again.", "magic")
    if int(prop["left"]) <= 0 and int(prop.get("value", 0)) >= int(prop.get("most", 50)):
        f.char.attuned = [u for u in f.char.attuned if u != rod.uid]
        rod.magic = {}
        b.say("The rod is spent and full: it is a plain rod now.", "magic")


# ---------------------------------------------------------------------------- Retributive Strike
def breakable(b, f):
    """The Staff of Power or of the Magi in hand, with charges in it to burst."""
    it = held(f, "retributive_strike")
    return it if it is not None and _left(it) > 0 else None


def breakable_problem(b, f) -> str | None:
    return None if breakable(b, f) is not None else "no charged staff of power in hand"


@special("retributive_strike")
def retributive_strike(c, o, victim) -> None:
    b, f = c.b, c.caster
    it = breakable(b, f)
    if it is None:
        return
    times = int((trait_prop(it, "retributive_strike") or {}).get("times", 4))
    retribution(b, f, it, times)


def retribution(b, f, it, times: int, words: str = "") -> None:
    """The staff breaks and its magic bursts 30 feet round: its bearer, half the time flung clear, else 16 force a
    charge; everyone else a Dexterity save (DC 17), `times` force a charge, half on a success."""
    from realmwalker.rules.inventory import remove_item

    n = _left(it)
    remove_item(f.char, it.uid, 1)
    f.char.attuned = [u for u in f.char.attuned if u != it.uid]
    b.say(words or f"<danger>{f.the_name} breaks the {it.magic.get('title', 'staff')} across a knee.</>", "danger")
    r = RADIUS_FT // grid.SQUARE_FT
    cells = b.area_cells(f, {"area": {"shape": "emanation", "size": RADIUS_FT}}, (f.x, f.y))
    b._event("cast", by=f.id, to=f.id, spell="retributive_strike", effect="damage", look="burst", dtype="force",
             area=[list(c) for c in cells])
    if b.rng.random() < 0.5:
        b.say(f"The burst throws {f.the_name} clear, between one heartbeat and the next.", "magic")
    else:
        b._hit(None, f, 16 * n, "force", crit=False, weapon="the staff's last fury")
    for x in list(b.fighters):
        if x is f or not (x.active or x.state == "down") or grid.gap(f.space, x.space) > r:
            continue
        amount = times * n
        if b._save(x, "dex", RETRIBUTION_DC):
            amount //= 2
        if amount > 0:
            b._hit(None, x, amount, "force", crit=False, weapon="the staff's burst")
    b._check_end()
