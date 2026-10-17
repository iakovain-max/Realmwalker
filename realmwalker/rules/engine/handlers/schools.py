"""The Diviner and the Illusionist (Expansion 5 Part A; PHB 2024 pp. 176-178).

Portent: the foretold d20s live in `char.spells["portent"]` (rolled at `progression.long_rest`, three from Greater
Portent). A fight asks before every D20 Test (`Battle.foretold` emits "d20_before" with the roll's kind and the natural
number it needs); a diviner who sees the roller may lay a die in its place, once a turn, by the battle's judgement
(asked only under the Reactions setting "all"). Outside a fight `foretell_check` does the same for the party's own
checks. Expert Divination gives a lower slot back; The Third Eye is `char.spells["third_eye"]` ("dark", "read",
"unseen") until a rest. The Illusionist: Illusory Self (`illusory_self`, called where a blow lands), Phantasmal
Creatures (`spells.free_cast` "phantasm", the summon at half hit points), Illusory Reality (`illusory_reality`).
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules import spells as spellrules
from realmwalker.rules.engine import reactions
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.events import handler
from realmwalker.rules.engine.handlers.mastery import once_a_turn, used_this_turn
from realmwalker.rules.engine.reactions import Decision

ROLL_WORDS = {"attack": "attack roll", "save": "saving throw", "check": "check", "death": "death save"}


# ---------------------------------------------------------------------------- Portent
def portent_count(char) -> int:
    if "portent" not in char.features:
        return 0
    return 3 if "greater_portent" in char.features else 2


def roll_portent(char, rng) -> list[int]:
    """At a long rest: the day's foretold rolls (the old ones are lost)."""
    n = portent_count(char)
    if not n or char.spells is None:
        return []
    char.spells["portent"] = sorted((dice.d20(rng).natural for _ in range(n)), reverse=True)
    return list(char.spells["portent"])


def dice_left(char) -> list[int]:
    return list((char.spells or {}).get("portent") or ()) if char is not None else []


def spend(char, value: int) -> None:
    left = dice_left(char)
    if value in left:
        left.remove(value)
    char.spells["portent"] = left


def chance(need: int, adv: bool = False, dis: bool = False) -> float:
    """The chance a d20 reaches `need` (a 20 always, a 1 never, as attacks and death saves have it)."""
    p = max(0.05, min(0.95, (21 - need) / 20.0))
    if adv and not dis:
        return 1 - (1 - p) ** 2
    if dis and not adv:
        return p * p
    return p


def pick(dice_: list[int], need: int, want: bool, kind: str) -> int | None:
    """The die that turns the roll the diviner's way: the lowest that is enough for a friend (the high ones kept),
    the highest that is too little for a foe (the low ones kept). A 20 is a critical hit and a 1 a sure miss."""
    if want:
        good = [d for d in dice_ if (d >= need or (d == 20 and kind in ("attack", "death"))) and d != 1]
        return min(good) if good else None
    bad = [d for d in dice_ if (d < need or (d == 1 and kind == "attack")) and d != 20]
    return max(bad) if bad else None


def judge(b, owner, ev, die: int, want: bool, p: float) -> bool:
    """Whether the battle would spend this die here: when the roll matters and could well go the wrong way."""
    who = ev.actor
    if ev.roll == "death":
        return want and (die == 20 or who.death_saves[1] >= 1 or p < 0.6)
    if ev.roll == "attack":
        target = ev.target
        if want:  # (a friend's blow: one that would fell the foe, or a hard one)
            return p <= 0.5 or die == 20 or (target is not None and target.hp <= target.max_hp // 3 and p <= 0.7)
        hurt = target is not None and target.hp <= target.max_hp // 2  # (a foe's blow at a friend who cannot take many)
        return p >= 0.45 and (hurt or p >= 0.65 or (ev.__dict__.get("big") and p >= 0.5))
    if ev.roll == "save":
        if want:  # (a friend's save against what a foe does to them)
            return p <= 0.6
        return p >= 0.4 and bool(ev.__dict__.get("spell"))  # (a foe resisting the party's spell)
    return want and p <= 0.5  # (a friend's check in a fight: escaping a grapple, a hard jump)


@handler("portent")
def portent(b, owner, ev, hook, buff) -> None:
    """A diviner lays a foretold die in place of a D20 Test (before it is rolled)."""
    if ev.natural is not None or owner.char is None:
        return
    left = dice_left(owner.char)
    who = ev.actor
    if not left or who is None or not owner.active or owner.incapacitated:
        return
    if who is not owner and not b.can_see(owner, who):
        return
    if used_this_turn(b, owner, "portent"):
        return
    want = who.team == owner.team
    die = pick(left, ev.need, want, ev.roll)
    if die is None:
        return
    p = chance(ev.need, ev.__dict__.get("adv", False), ev.__dict__.get("dis", False))
    if (want and p >= 0.95) or (not want and p <= 0.05):
        return  # (already sure)
    default = judge(b, owner, ev, die, want, p)
    what = ROLL_WORDS.get(ev.roll, "roll")
    text = (f"{who.the_name.capitalize()} is about to make {'an' if what[0] in 'a' else 'a'} {what} "
            f"(needs {max(1, min(20, ev.need))}). Lay a foretold {die} in its place?")
    if not reactions.yes(b, Decision(owner, "portent", text, [("yes", f"Portent: {die}"), ("no", "Let it roll")],
                                     default="yes" if default else "no", free=True)):
        return
    once_a_turn(b, owner, "portent")
    spend(owner.char, die)
    ev.natural = die
    ev.stop = True
    whose = "" if who is owner else f" for {who.the_name}"
    b.say(f"<magic>{owner.the_name} saw this coming:</> the {what}{whose} is {die}.", "magic")
    b._event("portent", who=owner.id, to=who.id, value=die)


def foretell_check(char, need: int, *, stake: bool = True) -> int | None:
    """Outside a fight: a foretold die for the party's own check, when one makes a likely failure a success.
    Spent and returned, or None."""
    left = dice_left(char)
    if not left or not stake or chance(need) > 0.55:
        return None
    die = pick(left, need, True, "check")
    if die is None:
        return None
    spend(char, die)
    return die


# ---------------------------------------------------------------------------- Expert Divination
@handler("expert_divination")
def expert_divination(b, f, ev, hook, buff) -> None:
    if f.char is not None and ev.spell.get("school") == "divination" and getattr(ev, "slotted", True):
        line = slot_back(f.char, int(ev.level or 0))
        if line:
            b.say(f"<magic>{f.the_name}</> {line}", "magic")


def slot_back(char, level: int) -> str:
    """After a divination with a slot of level 2+: the highest spent slot below it (5 at most) comes back."""
    if level < 2 or "expert_divination" not in char.features or not char.spells:
        return ""
    used = char.spells.get("slots_used") or []
    for lvl in range(min(level - 1, 5), 0, -1):
        if lvl <= len(used) and used[lvl - 1] > 0:
            spellrules.unspend_slot(char, lvl)
            return f"feels the vision settle: a level {lvl} slot comes back (Expert Divination)."
    return ""


# ---------------------------------------------------------------------------- The Third Eye
EYE_WORDS = {"dark": "sees through the dark", "read": "reads every script", "unseen": "sees the unseen"}


def eye(char) -> str:
    return str((char.spells or {}).get("third_eye") or "") if char is not None else ""


def open_eye(char, gift: str) -> None:
    char.spells["third_eye"] = gift


def close_eye(char) -> None:
    if char.spells:
        char.spells.pop("third_eye", None)


def _eye(c, gift: str) -> None:
    b, f = c.b, c.caster
    open_eye(f.char, gift)
    b.say(f"<magic>{f.the_name}'s third eye opens:</> {f.name.split()[0]} {EYE_WORDS[gift]}.", "magic")
    b._event("buff", who=f.id, spell="the_third_eye")
    if gift == "unseen":
        from realmwalker.rules.engine import durations

        durations.buff(f, {"see_invisible": True, "source": "the_third_eye"})


@special("third_eye_dark")
def third_eye_dark(c, o, victim) -> None:
    _eye(c, "dark")


@special("third_eye_unseen")
def third_eye_unseen(c, o, victim) -> None:
    _eye(c, "unseen")


@handler("eye_still_open")
def eye_still_open(b, f, ev, hook, buff) -> None:
    """An eye opened before the fight still sees the invisible in it."""
    if eye(f.char) == "unseen" and not f.buff_value("see_invisible"):
        from realmwalker.rules.engine import durations

        durations.buff(f, {"see_invisible": True, "source": "the_third_eye"})


def eye_problem(b, f) -> str | None:
    return "your third eye is already open" if eye(f.char) else None


# ---------------------------------------------------------------------------- the Illusionist
def improved(char) -> bool:
    return char is not None and "improved_illusions" in char.features


def illusion_range(char, spell: dict, rng: int) -> int:
    """Improved Illusions: an illusion's range of 10 feet or more is 60 feet longer."""
    if improved(char) and spell.get("school") == "illusion" and isinstance(rng, int) and rng >= 10:
        return rng + 60
    return rng


def illusory_self(b, att, target, shield: bool = False) -> bool:
    """Illusory Self: a blow that hits meets a double instead (the reaction; once a rest, or a slot of 2+). `shield`:
    Shield would turn it too (then a slot of 2 is not spent on the double: Shield's first-level slot will do)."""
    c = target.char
    if c is None or "illusory_self" not in c.features or not target.reaction or target.incapacitated:
        return False
    ready = c.uses.get("illusory_self", 1) > 0
    slot = None
    if not ready:
        slot = spellrules.lowest_free_slot(c, b.t, 2)
        if slot is None or shield and "shield" in spellrules.known_spells(c, b.t) \
                and spellrules.lowest_free_slot(c, b.t, 1) is not None:
            return False
    hurt = target.hp <= target.max_hp // 2
    default = ready or hurt  # (a slot is spent on it only when the blow could matter)
    cost = "once a rest" if ready else f"a level {slot} slot"
    if not reactions.yes(b, Decision(target, "illusory_self", f"{att.the_name.capitalize()}'s blow would hit "
                                     f"{target.the_name}. Put an illusory double in its way? ({cost})",
                                     [("yes", "Illusory Self"), ("no", "Take it")],
                                     default="yes" if default else "no", free=ready)):
        return False
    if ready:
        c.uses["illusory_self"] = 0
    else:
        spellrules.spend_slot(c, slot)
    target.reaction = False
    b.say(f"<magic>{att.the_name.capitalize()} strikes {target.the_name}</> - and the figure bursts into mist. "
          f"The real one stands a step away.", "magic")
    b._event("illusion", who=target.id, what="double")
    return True


def phantasm_ready(char, spell_id: str) -> bool:
    return (spell_id in ("summon_beast", "summon_fey") and "phantasmal_creatures" in char.features
            and char.uses.get(f"phantasm:{spell_id}", 1) > 0)


def phantasm_spent(char, spell_id: str) -> None:
    char.uses[f"phantasm:{spell_id}"] = 0


def rest(char, long: bool) -> None:
    """A rest: the third eye closes, Illusory Self comes back; a long rest brings the phantasms back too."""
    close_eye(char)
    if "illusory_self" in char.features:
        char.uses["illusory_self"] = 1
    if long:
        for key in [k for k in char.uses if k.startswith("phantasm:")]:
            del char.uses[key]


def party_foretell(party, need: int) -> tuple[int, object] | tuple[None, None]:
    """Outside a fight: a diviner in the party lays a foretold die on a check of the party's that would likely fail
    (`foretell_check`). (die, the diviner) or (None, None)."""
    for c in party:
        if c.alive and c.hp > 0 and dice_left(c):
            die = foretell_check(c, need)
            if die is not None:
                return die, c
    return None, None


# ---------------------------------------------------------------------------- Illusory Reality
REAL_ROUNDS = 10  # a minute


def realisable(b, f) -> list:
    """The caster's images cast with a slot that are still up and not yet made real."""
    return [z for z in b.zones if z.kind == "illusion" and z.owner == f.id and z.slotted and not z.real
            and not z.cast.get("made_real")]


def reality_problem(b, f) -> str | None:
    if f.char is None or "illusory_reality" not in f.char.features:
        return "not yours"
    return None if realisable(b, f) else "no illusion of yours cast with a slot"


@special("illusory_reality")
def illusory_reality(c, o, victim) -> None:
    """One thing in the illusion is made real for a minute: on water or a chasm a bridge, elsewhere a wall of the
    stones it showed (nobody standing there is touched; it harms nobody)."""
    b, f = c.b, c.caster
    zones = realisable(b, f)
    if not zones:
        return
    z = max(zones, key=lambda z: z.id)  # (the latest image)
    T = b.t.terrain
    taken = {sq for x in b.on_field() for sq in x.cells}
    for sq in sorted(z.cells):
        if sq in taken or not b.field.in_bounds(*sq):
            continue
        name = b.field.name(*sq)
        tags = T.tags[T.index[name]]
        if "water" in tags or "chasm" in tags or "swim" in tags:
            z.was[sq] = name
            b.field.terrain[sq] = T.index["bridge"]
        elif b.field.passable(*sq):
            z.was[sq] = name
            b.field.terrain[sq] = T.index["ruin_wall"]  # (stones that stop feet as well as eyes)
    if not z.was:
        return
    b.field._derive()
    z.real = REAL_ROUNDS
    z.cast["made_real"] = True
    bridge = any(b.field.name(*sq) == "bridge" for sq in z.was)
    b.say(f"<magic>{f.the_name} weaves shadow into the image:</> the "
          f"{'bridge' if bridge else 'wall of stones'} is real now.", "magic")
    b._event("illusion", who=f.id, what="real", id=z.id, cells=sorted(z.was))
    b._sync_zones()


def unreal(b, z) -> None:
    """Its minute is up: what was made real is an image again."""
    z.real = 0
    if not z.was:
        b._sync_zones()
        return
    for (x, y), name in z.was.items():
        b.field.terrain[x, y] = b.t.terrain.index[name]
    z.was = {}
    b.field._derive()
    b.say("The thing that was made real fades back into an image.", "magic")
    b._event("illusion", who=z.owner, what="unreal", id=z.id)
    b._sync_zones()
