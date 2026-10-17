"""How long things last in a fight, and how they end (docs/EXPANSIONS.md §4.3.1).

Most of the 2024 rules time their effects by someone's turn: "until the start of your next turn" (Shield, Ray of Frost),
"until the end of its next turn" (Sleep's first grip), "until the end of your next turn" (Chill Touch, Guiding Bolt).
An ending is a small record, `{"at": "turn_start" | "turn_end", "of": fighter id, "left": n}`: each time that fighter's
turn starts (or ends) `left` goes down by one, and at nothing the thing is over. It can sit on a buff (`buff["ends"]`)
or on a condition (`Fighter.cond_ends[condition]`). A condition's ending may also say:
    conc        the caster whose concentration holds it (it ends with that concentration)
    on_damage   it ends when the creature takes damage (Sleep)
    damage_save {save, dc}: each time the creature takes damage it saves again, and a success ends it (Dominate)
    control     the side it fights for while it lasts (Dominate: Fighter.team)
    then        a saving throw to make when it runs out, and what a failure brings (Sleep's second save):
                {"save": "wis", "dc": 13, "caster": id, "spell": id, "on_fail": [effect ops]}

Older timings stay as they were: a buff's "rounds" and a condition's number count down at the start of the holder's
own turns (rules/combat.py _start_of_turn).
"""

from __future__ import annotations


def until(b, who, at: str) -> dict:
    """An ending at the start or end of `who`'s next turn. A turn under way does not count as the next one."""
    left = 1
    if at == "turn_end" and b.order and b.turn_started and b.current is who:
        left = 2
    return {"at": at, "of": who.id, "left": left}


def buff(f, part: dict, ends: dict | None = None) -> dict:
    """Put a buff on a fighter (replacing one from the same source), with its ending."""
    b = dict(part)
    if ends is not None:
        b["ends"] = dict(ends)
    if b.get("source"):
        f.buffs = [x for x in f.buffs if x.get("source") != b["source"]]
    f.buffs.append(b)
    return b


def give(b, f, cid: str, *, ends: dict | None = None, rounds: int | None = None, source=None, quiet: bool = True,
         **extra) -> bool:
    """A condition takes hold (unless something keeps it off). `ends` times it by turns; `rounds` the old way."""
    from realmwalker.rules.engine import query

    if query.condition_immune(f, cid):
        return False
    if ends is not None:
        f.conditions[cid] = -1
        f.cond_ends[cid] = {**ends, **extra}
    else:
        f.conditions[cid] = -1 if rounds is None else int(rounds)
        if extra:
            f.cond_ends[cid] = dict(extra)
    if source is not None:
        f.sources[cid] = source.id
    return True


def remove(f, cid: str) -> None:
    """A condition ends. (When Unconscious ends, the creature is still lying down: 2024.)"""
    had = cid in f.conditions
    f.conditions.pop(cid, None)
    f.cond_ends.pop(cid, None)
    f.sources.pop(cid, None)
    if had and cid == "unconscious":
        f.conditions["prone"] = -1
    for other, e in list(f.cond_ends.items()):
        if e.get("with") == cid:  # (a crocodile's hold: Restrained while Grappled)
            remove(f, other)


def tick(b, f, at: str) -> None:
    """`f`'s turn starts or ends: whatever was waiting for that runs down, and what has run out ends."""
    from realmwalker.rules.engine import effects

    for x in b.fighters:
        for bf in list(x.buffs):
            e = bf.get("ends")
            if e and e["of"] == f.id and e["at"] == at:
                e["left"] -= 1
                if e["left"] <= 0:
                    x.buffs.remove(bf)
        for cid, e in list(x.cond_ends.items()):
            if e.get("of") != f.id or e.get("at") != at:
                continue
            e["left"] -= 1
            if e["left"] > 0:
                continue
            then = e.get("then")
            remove(x, cid)
            if cid in ("stunned", "restrained", "frightened", "paralyzed", "incapacitated", "unconscious") and x.active:
                b.say(f"{x.the_name} is no longer {_word(b, cid)}.", "system")
            if then and x.active:
                effects.then_save(b, x, then)


def on_damage(b, f) -> None:
    """Damage breaks what damage breaks (a magical sleep)."""
    for cid, e in list(f.cond_ends.items()):
        if e.get("on_damage"):
            remove(f, cid)
            if cid in ("unconscious", "incapacitated") and f.state == "fighting":
                b.say(f"{f.the_name} wakes with a start.", "system")
        elif e.get("damage_save") and f.active and cid in f.conditions:  # (Dominate: hurt, it fights the hold)
            ds = e["damage_save"]
            if b._save(f, ds["save"], int(ds["dc"]), against=(cid,)):
                remove(f, cid)
                b.say(f"{f.the_name} throws off the hold on {'their' if f.char else 'its'} mind.", "system")


def end_concentration(b, caster) -> None:
    """The caster's concentration is gone: conditions it held end."""
    for x in b.fighters:
        for cid, e in list(x.cond_ends.items()):
            if e.get("conc") == caster.id:
                remove(x, cid)


def _word(b, cid: str) -> str:
    from realmwalker.rules.engine import conditions as cond

    return cond.name(b.t, cid).lower()
