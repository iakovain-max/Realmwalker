"""Weapon masteries (PHB 2024, "Mastery Properties"): what a weapon's trick does when its wielder has mastered it.

A character uses a weapon's mastery when they have the Weapon Mastery feature (fighters, rogues; trait
`weapon_mastery`) and the kind of weapon is among `Character.masteries`; a creature only when its stat block's attack
names one (`"mastery"` on the attack, with the trait). The hook is `attack_done` (after the blow, hit or miss, with the
damage it dealt); Nick is read where the off-hand blow is offered (`Battle.offhand_option`).

Choices the rules leave to the attacker (whether to push, whom to cleave into) are the battle's judgement for the enemy
and the Auto (`rules/tactics.mastery_choice`); a party member the player commands is asked only under the Reactions
setting "all" (they are free choices).
"""

from __future__ import annotations

from dataclasses import replace

from realmwalker.core import dice
from realmwalker.rules.engine import durations, query
from realmwalker.rules.engine import traits as tr
from realmwalker.rules.engine.events import handler
from realmwalker.rules.engine.reactions import Decision, yes

MASTERIES = ("cleave", "graze", "nick", "push", "sap", "slow", "topple", "vex")
PUSHABLE = ("tiny", "small", "medium", "large")


def weapon_of(f, opt):
    """The item behind an attack option, or None."""
    if f.char is None or opt.item_uid is None:
        return None
    return f.char.item(opt.item_uid)


def of(f, opt) -> str | None:
    """The mastery this attack can use, or None."""
    if opt is None or opt.kind not in ("melee", "ranged") or "improvised" in opt.properties:
        return None
    if not tr.has(f, "weapon_mastery"):
        return None
    if f.char is None:
        return opt.extra.get("mastery")
    it = weapon_of(f, opt)
    if it is None or it.def_id not in f.char.masteries:
        return None
    return f.t.items.get(it.def_id).get("mastery")


def item_mastery(f, item) -> str | None:
    """The mastery a character can use with this item (for Nick, read before any attack is made)."""
    if item is None or f.char is None or not tr.has(f, "weapon_mastery") or item.def_id not in f.char.masteries:
        return None
    return f.t.items.get(item.def_id).get("mastery")


def ability_mod(f, opt) -> int:
    """The ability modifier the attack was made with (a stat block's: its bonus less its proficiency)."""
    if "ability_mod" in opt.extra:
        return int(opt.extra["ability_mod"])
    return int(opt.bonus) - query.proficiency(f) if f.char is None else 0


def _turn_key(b) -> tuple:
    cur = b.current if b.order else None
    return b.round, cur.id if cur is not None else None


def once_a_turn(b, f, name: str) -> bool:
    """True the first time in a turn (then marks it used)."""
    used = f.__dict__.setdefault("mastery_used", {})
    key = _turn_key(b)
    if used.get(name) == key:
        return False
    used[name] = key
    return True


def nick_ready(b, f) -> bool:
    """The Light weapon's extra blow may be part of the Attack action (a Nick weapon in either hand), once a turn."""
    if f.char is None:
        return False
    used = f.__dict__.get("mastery_used", {})
    if used.get("nick") == _turn_key(b):
        return False
    return any(item_mastery(f, f.char.equipped_item(slot)) == "nick" for slot in ("main_hand", "off_hand"))


def choose(b, f, kind: str, target, text: str) -> bool:
    """A free choice of the attacker's: the battle's judgement, or the player under the Reactions setting "all"."""
    from realmwalker.rules import tactics

    default = "yes" if tactics.mastery_choice(b, f, kind, target) else "no"
    return yes(b, Decision(f, f"mastery_{kind}", text, [("yes", "Yes"), ("no", "No")], default=default, free=True))


# ---------------------------------------------------------------------------- after a blow
@handler("mastery_done")
def mastery_done(b, f, ev, hook, buff) -> None:
    opt, target = ev.opt, ev.target
    kind = of(f, opt)
    if kind is None or target is None or opt.extra.get("cleave_blow"):
        return
    words = b.t.combat_text.get("mastery", {})
    if not ev.hit:
        if kind == "graze":
            mod = ability_mod(f, opt)
            if mod > 0 and (target.active or target.state == "down"):
                b.say(_line(b, words, "graze", f, target, opt), "good" if f.side == "party" else "info")
                b._event("mastery", who=target.id, by=f.id, trick="graze")
                b._hit(f, target, mod, opt.damage_type, crit=False, weapon=opt.name)
        return
    if not (target.active or target.state == "down"):
        if kind == "cleave":
            _cleave(b, f, opt, target, words)
        return
    if kind == "sap":
        durations.buff(target, {"sapped": f.id, "source": f"sap:{f.id}"}, durations.until(b, f, "turn_start"))
        b._event("mastery", who=target.id, by=f.id, trick="sap")
        b.say(_line(b, words, "sap", f, target, opt), "system")
    elif kind == "slow" and ev.dealt > 0:
        durations.buff(target, {"slow": 10, "source": "mastery_slow"}, durations.until(b, f, "turn_start"))
        b._event("mastery", who=target.id, by=f.id, trick="slow")
        b.say(_line(b, words, "slow", f, target, opt), "system")
    elif kind == "vex" and ev.dealt > 0:
        durations.buff(f, {"vex": target.id, "source": f"vex:{target.id}"}, durations.until(b, f, "turn_end"))
        b._event("mastery", who=target.id, by=f.id, trick="vex")
        b.say(_line(b, words, "vex", f, target, opt), "system")
    elif kind == "topple" and target.standing:
        if "prone" in target.conditions or query.condition_immune(target, "prone"):
            return
        dc = 8 + ability_mod(f, opt) + query.proficiency(f)
        if not choose(b, f, "topple", target, f"Knock {target.the_name} down? (a Constitution save, DC {dc})"):
            return
        if not b._save(target, "con", dc) and durations.give(b, target, "prone", source=f):
            b._event("prone", who=target.id)
            b._event("mastery", who=target.id, by=f.id, trick="topple")
            b.say(_line(b, words, "topple", f, target, opt), "good" if f.side == "party" else "danger")
        else:
            b.say(f"{target.the_name} staggers but keeps {target.possessive} feet.", "system")
    elif kind == "push" and target.size in PUSHABLE:
        if not choose(b, f, "push", target, f"Drive {target.the_name} ten feet back?"):
            return
        if b._push(f, target, 2):
            b._event("mastery", who=target.id, by=f.id, trick="push")
            b.say(_line(b, words, "push", f, target, opt), "system")
    elif kind == "cleave":
        _cleave(b, f, opt, target, words)


def _cleave(b, f, opt, first, words) -> None:
    """Through the first and into the next: a second melee attack roll against a creature within 5 feet of the first,
    within reach, for the weapon's damage without the ability bonus; once a turn."""
    if not opt.is_melee:
        return
    from realmwalker.rules import tactics

    near = [x for x in b.enemies_of(f) if x is not first and x.active and b.gap(x, first) <= 1
            and b.in_reach(f, opt, x)[0]]
    if not near:
        return
    second = tactics.cleave_target(b, f, near)
    if second is None or not once_a_turn(b, f, "cleave"):
        return
    n, sides, flat = dice.parse(opt.damage)
    mod = ability_mod(f, opt)
    flat -= max(0, mod)
    damage = (f"{n}d{sides}" if n else "") + (f"{flat:+d}" if flat and n else (str(max(1, flat)) if not n else ""))
    blow = replace(opt, key=f"{opt.key}:cleave", damage=damage or "1", extra=dict(opt.extra, cleave_blow=True))
    b.say(_line(b, words, "cleave", f, second, opt), "good" if f.side == "party" else "danger")
    b._event("mastery", who=second.id, by=f.id, trick="cleave")
    b._attack(f, blow, second)


def _line(b, words: dict, kind: str, f, target, opt) -> str:
    lines = words.get(kind) or ["{A} uses the {weapon}'s trick on {T}."]
    return b._fill(b.rng.choice(lines), f, target, weapon=opt.name, armor="")
