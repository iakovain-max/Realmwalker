"""The 2024 cleric and its domains (PHB chapter 3, Cleric; the Life and War Domains): Divine Spark, Sear Undead, the
Blessed Strikes, Divine Intervention as a spell the god casts, Blessed Healer, Supreme Healing, War God's Blessing.
Turn Undead, Preserve Life, Guided Strike and War Priest are in features.py; Disciple of Life too."""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules import spells as spellrules
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.events import handler
from realmwalker.rules.engine.handlers.mastery import once_a_turn


def _word(f) -> str:
    return "good" if f.side == "party" else "info"


def spark_dice(f) -> str:
    """Divine Spark: 1d8, 2d8 at 7, 3d8 at 13, 4d8 at 18."""
    lv = f.char.level if f.char is not None else 1
    return f"{1 + (lv >= 7) + (lv >= 13) + (lv >= 18)}d8"


def _spark_amount(b, f) -> int:
    n, sides, _ = dice.parse(spark_dice(f))
    rolled = n * sides if f.has_trait("supreme_healing") else dice.roll(spark_dice(f), b.rng).total
    return max(1, rolled + f.mod("wis"))


@special("divine_spark")
def divine_spark(c, o, victim) -> None:
    """Channel Divinity: holy fire for a friend's wounds (or, `harm`, a Constitution save against it)."""
    b, f = c.b, c.caster
    t = victim or c.target
    if t is None:
        return
    b._event("cast", by=f.id, to=t.id, spell="divine_spark", effect="heal" if not o.get("harm") else "save",
             look="bolt", dtype="radiant", area=list(t.cells), point=None, shape="")
    if not o.get("harm"):
        b.say(f"{f.the_name} points the holy symbol at {t.the_name}: light runs into the wounds.", "magic")
        b._heal(t, _spark_amount(b, f))
        return
    b.say(f"{f.the_name} points the holy symbol at {t.the_name}: a spark of the god's wrath.", "magic")
    amount = max(1, dice.roll(spark_dice(f), b.rng).total + f.mod("wis"))
    b._save_damage(f, t, "con", spellrules.save_dc(f.sheet, b.t), str(amount), "radiant", "half", rolled=amount)


@special("divine_spark_harm")
def divine_spark_harm(c, o, victim) -> None:
    divine_spark(c, {"harm": True}, victim)


def sear(b, f, undead) -> None:
    """Sear Undead: a d8 of radiant damage per point of Wisdom on each undead that failed against Turn Undead."""
    n = max(1, f.mod("wis"))
    for x in undead:
        if x.active or x.state == "fleeing":
            b._hit(f, x, dice.roll(f"{n}d8", b.rng).total, "radiant", crit=False, weapon="holy light")


# ---------------------------------------------------------------------------- Blessed Strikes
@handler("blessed_divine_strike")
def blessed_divine_strike(b, f, ev, hook, buff) -> None:
    """Once on each of their turns, a weapon hit deals 1d8 radiant more (2d8 from level 14)."""
    if f.char is None or ev.opt.kind not in ("melee", "ranged") or b.current is not f:
        return
    if not once_a_turn(b, f, "divine_strike"):
        return
    n = 2 if f.has_trait("improved_blessed_strikes") else 1
    ev.typed.append((dice.roll(f"{n}d8", b.rng, double_dice=ev.crit).total, "radiant"))


@handler("potent_vitality")
def potent_vitality(b, f, ev, hook, buff) -> None:
    """Improved Potent Spellcasting: a cleric cantrip cast at a foe gives twice the Wisdom modifier in temporary hit
    points to the caster or the friend within 60 feet who most needs them."""
    sp = ev.spell or {}
    if sp.get("level") != 0 or "cleric" not in sp.get("classes", ()) or not spellrules.harms(sp) \
            or not f.has_trait("improved_blessed_strikes"):
        return
    amount = 2 * max(1, f.mod("wis"))
    near = [x for x in b.team(f.team) if x.active and b.feet(f, x) <= 60 and x.temp_hp < amount]
    if near:
        x = min(near, key=lambda x: (x.hp / max(1, x.max_hp), x.id))
        x.temp_hp = amount
        b.dice_say(f"{f.name} (Potent Spellcasting): {x.name} +{amount} temporary hit points")


# ---------------------------------------------------------------------------- Divine Intervention
@special("divine_intervention")
def divine_intervention(c, o, victim) -> None:
    """The god answers: the cleric spell of level 5 or lower worth most here, cast without a slot (the battle's
    judgement chooses it)."""
    from realmwalker.rules import tactics

    b, f = c.b, c.caster
    b.say(f"{f.the_name} cries out to {f.possessive} god, and the god answers.", "magic")
    f.__dict__["free_slot"] = 5
    try:
        best = tactics._pick_cast(b, f, "action", beat=-99.0)
        if best is None:
            best = tactics._pick_cast(b, f, "bonus", beat=-99.0)
        if best is None:
            b.say("Nothing here needs the god's hand; the prayer goes unspent.", "system")
            f.char.uses["divine_intervention"] = f.char.uses.get("divine_intervention", 0) + 1
            return
        _, sid, target, point, _sp = best
        if not b.do_cast(f, sid, target, point=point):
            f.char.uses["divine_intervention"] = f.char.uses.get("divine_intervention", 0) + 1
        elif f.action > 0:
            f.action -= 1  # (it is the cleric's action, whatever the spell's own casting time)
    finally:
        f.__dict__.pop("free_slot", None)


# ---------------------------------------------------------------------------- the Life Domain
@handler("blessed_healer")
def blessed_healer(b, f, ev, hook, buff) -> None:
    """A healing spell on someone else heals the cleric too: 2 + the spell's level (once a spell)."""
    if ev.target is f or ev.level < 1 or not f.active and f.state != "down":
        return
    if once_a_turn(b, f, f"blessed_healer:{ev.level}"):
        b._heal(f, 2 + int(ev.level))


@handler("supreme_healing")
def supreme_healing(b, f, ev, hook, buff) -> None:
    """Healing dice count as their highest."""
    most, rolled = getattr(ev, "most", None), getattr(ev, "rolled", None)
    if most is not None and rolled is not None and most > rolled:
        ev.amount += most - rolled


# ---------------------------------------------------------------------------- the War Domain
@special("war_gods_blessing")
def war_gods_blessing(c, o, victim) -> None:
    """A use of Channel Divinity casts Shield of Faith or Spiritual Weapon without a slot."""
    b, f = c.b, c.caster
    sid = o.get("spell")
    t = victim or c.target
    f.__dict__["free_slot"] = 5
    try:
        if sid == "shield_of_faith":
            if t is None:
                t = min((x for x in b.team(f.team) if x.active and b.feet(f, x) <= 60),
                        key=lambda x: (x.hp / max(1, x.max_hp), x.id), default=f)
            ok = b.do_cast(f, sid, t)
        else:
            pts = b.spell_points(f, sid)
            foes = [e for e in b.enemies_of(f) if e.active]
            point = min(pts, key=lambda p: min((abs(p[0] - e.x) + abs(p[1] - e.y) for e in foes), default=0)) \
                if pts else None
            ok = point is not None and b.do_cast(f, sid, None, point=point)
    finally:
        f.__dict__.pop("free_slot", None)
    if not ok and f.char is not None:
        f.char.uses["channel_divinity"] = f.char.uses.get("channel_divinity", 0) + 1
