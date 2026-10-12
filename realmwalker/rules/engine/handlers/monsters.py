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
    if f.creature is not None and b.rng.random() < 0.5:
        if b._save(f, "con", 5 + ev.amount):
            f.hp = 1
            b.say(f"{f.the_name} shudders and keeps coming.", "danger")
            ev.survived = ev.stop = True


@handler("regeneration")
def regeneration(b, f, ev, hook, buff) -> None:
    """Trolls: wounds close at the start of its turn, unless fire or acid burned it since the last."""
    if f.hp > 0 and not f.took_fire:
        healed = min(int(hook.get("amount", 10)), f.max_hp - f.hp)
        if healed:
            f.hp += healed
            b._event("heal", to=f.id, amount=healed)
            b.say(f"{f.the_name}'s wounds knit closed before your eyes.", "danger")


@handler("leader_falls")
def leader_falls(b, f, ev, hook, buff) -> None:
    """The others take it hard when the leader goes down."""
    for other in b.side(f.side):
        if other.active and other is not f:
            b._morale_check(other, "leader")
