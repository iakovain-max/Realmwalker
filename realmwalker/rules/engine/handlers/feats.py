"""Feats that step in during a fight (data/feats.json, their traits in data/traits.json)."""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules.engine import query
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.events import handler
from realmwalker.rules.engine.handlers.mastery import choose, once_a_turn


# ---------------------------------------------------------------------------- Lucky
@handler("lucky_attack")
def lucky_attack(b, f, ev, hook, buff) -> None:
    """A missed attack rolled again with a luck point (the better roll kept)."""
    c = f.char
    if c is None or c.uses.get("luck", 0) <= 0 or ev.natural == 1 and False:
        return
    if ev.total + 20 - ev.natural < ev.ac:
        return  # (not even a 20 would do)
    c.uses["luck"] -= 1
    again = dice.d20(b.rng).natural
    total = ev.total - ev.natural + again
    b.dice_say(f"{f.name} spends a luck point: {again} → {total} vs AC {ev.ac}")
    if again == 20 or again != 1 and total >= ev.ac:
        ev.hit, ev.total = True, total


@handler("lucky_save")
def lucky_save(b, f, ev, hook, buff) -> None:
    c = f.char
    if ev.roll != "save" or ev.ok or c is None or c.uses.get("luck", 0) <= 0:
        return
    if ev.bonus + 20 < ev.dc:
        return
    c.uses["luck"] -= 1
    again = dice.d20(b.rng).natural
    ev.ok = again + ev.bonus >= ev.dc
    b.dice_say(f"{f.name} spends a luck point: {again} + {ev.bonus} = {again + ev.bonus} vs DC {ev.dc} — "
               f"{'saved' if ev.ok else 'failed'}")


# ---------------------------------------------------------------------------- Savage Attacker
@handler("savage_attacker")
def savage_attacker(b, f, ev, hook, buff) -> None:
    """Once a turn: the weapon's damage dice rolled again, the higher kept."""
    opt = ev.opt
    if f.char is None or opt.kind not in ("melee", "ranged") or opt.item_uid is None or not ev.rolls:
        return
    if not once_a_turn(b, f, "savage_attacker"):
        return
    n, sides, _ = dice.parse(opt.damage)
    again = sum(b.rng.randint(1, sides) for _ in range(len(ev.rolls)))
    if again > sum(ev.rolls):
        ev.extra += again - sum(ev.rolls)
        b.dice_say(f"{f.name} (Savage Attacker): {sum(ev.rolls)} rolled again, {again} kept")


# ---------------------------------------------------------------------------- Tavern Brawler
@handler("tavern_brawler")
def tavern_brawler(b, f, ev, hook, buff) -> None:
    """A punch's 1s on the damage die rolled again."""
    if ev.opt.key != "unarmed" or not ev.rolls:
        return
    n, sides, _ = dice.parse(ev.opt.damage)
    ev.extra += sum(b.rng.randint(1, sides) - 1 for r in ev.rolls if r == 1)


@handler("tavern_shove")
def tavern_shove(b, f, ev, hook, buff) -> None:
    """Once a turn, a punch that lands can shove the one hit 5 feet away."""
    t = ev.target
    if not ev.hit or ev.opt.key != "unarmed" or t is None or not t.active or not t.standing:
        return
    if not choose(b, f, "push", t, f"Shove {t.the_name} five feet away?") or not once_a_turn(b, f, "tavern_shove"):
        return
    if b._push(f, t, 1):
        b._event("mastery", who=t.id, by=f.id, trick="push")
        b.say(f"{f.the_name} sends {t.the_name} reeling back.", "system")


# ---------------------------------------------------------------------------- Healer
@special("battle_medic")
def battle_medic(c, o, victim) -> None:
    """With a healer's kit: the worst hurt friend beside you spends a Hit Die, and heals it and your proficiency
    bonus (a 1 rolled again)."""
    b, f = c.b, c.caster
    near = [x for x in b.team(f.team) if x is not f and (x.active or x.state == "down") and x.hp < x.max_hp
            and b.gap(f, x) <= 1 and (x.char is None or x.char.hit_dice > 0)]
    if not near:
        return
    x = min(near, key=lambda x: (x.state != "down", x.hp / max(1, x.max_hp)))
    die = b.t.classes[x.char.cls]["hit_die"] if x.char is not None else 8
    if x.char is not None:
        x.char.hit_dice -= 1
    roll = b.rng.randint(1, die)
    if roll == 1:
        roll = b.rng.randint(1, die)
    amount = roll + query.proficiency(f)
    b.say(f"{f.the_name} works fast with the healer's kit on {x.the_name}.", "good" if f.side == "party" else "info")
    b._heal(x, amount)
