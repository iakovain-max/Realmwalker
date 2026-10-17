"""Creature traits that step in during a fight."""

from __future__ import annotations

from realmwalker.rules.engine.events import handler


@handler("relentless")
def relentless(b, f, ev, hook, buff) -> None:
    """Once, a blow of 7 or less that would fell it leaves it at 1 hit point (boars, berserkers)."""
    if f.creature is not None and f.creature.uses.get("relentless") and ev.amount <= 7:
        f.creature.uses["relentless"] = 0
        f.hp = 1
        b.say(f"{f.the_name} refuses to fall.", "danger")
        ev.survived = ev.stop = True


@handler("undead_fortitude")
def undead_fortitude(b, f, ev, hook, buff) -> None:
    """2025: a Constitution save, DC 5 + the damage, unless the blow was radiant or a critical hit."""
    if f.creature is None or getattr(ev, "crit", False):
        return
    n = f.cdef.get("trait_numbers", {}).get("undead_fortitude", {})
    if getattr(ev, "dtype", "") in n.get("not_types", ["radiant"]):
        return
    if b._save(f, "con", int(n.get("dc_plus_damage", 5)) + ev.amount):
        f.hp = 1
        b.say(f"{f.the_name} shudders and keeps coming.", "danger")
        ev.survived = ev.stop = True


@handler("regeneration")
def regeneration(b, f, ev, hook, buff) -> None:
    """Trolls: wounds close at the start of its turn, unless fire or acid burned it since the last."""
    if f.hp > 0 and not f.took_fire:
        amount = (f.cdef or {}).get("trait_numbers", {}).get("regeneration", {}).get("amount", hook.get("amount", 10))
        healed = min(int(amount), f.max_hp - f.hp)
        if healed:
            f.hp += healed
            b._event("heal", to=f.id, amount=healed)
            b.say(f"{f.the_name}'s wounds knit closed before your eyes.", "danger")


@handler("leader_falls")
def leader_falls(b, f, ev, hook, buff) -> None:
    """The others take it hard when the leader goes down."""
    for other in b.team(f.team):
        if other.active and other is not f:
            b._morale_check(other, "leader")


@handler("burst_of_ingenuity")
def burst_of_ingenuity(b, f, ev, hook, buff) -> None:
    """The sphinx of wonder's Reaction, twice a day: +2 to a failed saving throw or ability check of its own or a
    friend's within 30 feet, spent only when the 2 turns it (the battle's judgement, for the party's sphinx too)."""
    who = ev.actor
    if ev.roll not in ("save", "check") or ev.ok or f.creature is None or who is None or who.team != f.team \
            or not f.active or f.incapacitated or (who is not f and b.feet(f, who) > 30):
        return
    spec = next((a for a in f.cdef.get("reactions", ()) if a.get("id") == "burst_of_ingenuity"), {})
    plus = int(spec.get("bonus", 2))
    left = f.creature.uses.setdefault("burst_of_ingenuity", int(str(spec.get("uses", "2/day")).split("/")[0]))
    if left <= 0 or ev.natural + ev.bonus + plus < ev.dc:
        return
    f.creature.uses["burst_of_ingenuity"] = left - 1
    f.reaction = False
    ev.ok = True
    b.dice_say(f"{f.name} (Burst of Ingenuity): +{plus} → {ev.natural + ev.bonus + plus} vs DC {ev.dc} — "
               f"{'saved' if ev.roll == 'save' else 'made'}")
    whose = "its own" if who is f else f"{who.the_name}'s"
    b.say(f"{f.the_name} turns {whose} failing aside with a bright thought.", "magic")

