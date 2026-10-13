"""The general and fighting style feats that step in during a fight (PHB 2024 chapter 5; data/feats.json, their traits
in data/traits.json "feat_<id>" and "style_<id>").

What a feat changes in a number the battle already works out (a style's +2, Speedy's feet, Sharpshooter's cover) is
read where that number is made (rules/combat.py, rules/engine/query.py, through `rules/feats.has`); what happens after
a blow, a step or a hurt is a hook here. Free choices (push or not) are the battle's judgement for the enemy and the
Auto (`rules/tactics.mastery_choice`), asked of the player only under the Reactions setting "all"; reactions that cost
something (Sentinel's blow, a parry) are asked as the Reactions setting says.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules import feats as featrules
from realmwalker.rules.engine import durations, query
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.events import handler
from realmwalker.rules.engine.handlers.mastery import PUSHABLE, choose, once_a_turn, used_this_turn
from realmwalker.rules.engine.reactions import Decision, yes


def _side_word(f) -> str:
    return "good" if f.side == "party" else "info"


def _own_turn(b, f) -> bool:
    return bool(b.order) and b.current is f


def _weapon_hit(ev) -> bool:
    return ev.hit and ev.opt is not None and ev.opt.kind in ("melee", "ranged")


def _bigger_by_more_than_one(f, t) -> bool:
    sizes = list(PUSHABLE) + ["huge", "gargantuan"]
    return sizes.index(t.size) > sizes.index(f.size) + 1 if t.size in sizes and f.size in sizes else False


# ---------------------------------------------------------------------------- Great Weapon Master
@handler("gwm_heavy")
def gwm_heavy(b, f, ev, hook, buff) -> None:
    """A hit with a Heavy weapon on one's own turn: the proficiency bonus in extra damage."""
    opt = ev.opt
    if opt.kind in ("melee", "ranged") and "heavy" in opt.properties and _own_turn(b, f):
        ev.extra += query.proficiency(f)


@handler("gwm_hew")
def gwm_hew(b, f, ev, hook, buff) -> None:
    """Hew: a melee weapon's critical hit, or a blow that drops a foe, earns a bonus-action blow with it this turn."""
    opt, t = ev.opt, ev.target
    weapon = opt.item_uid is not None or f.char is None and opt.extra.get("item")
    if not ev.hit or opt.kind != "melee" or not weapon or not _own_turn(b, f) or f.bonus <= 0:
        return
    if ev.crit or t is None or not t.active or t.hp <= 0:
        f.__dict__["hew"] = (b.round, opt.key)
        b.say(f"{f.the_name} has the swing for another blow (Hew: a bonus action).", "system")


def hew_ready(b, f) -> str | None:
    """The attack option key Hew allows now, or None."""
    got = f.__dict__.get("hew")
    if got and got[0] == b.round and _own_turn(b, f) and f.bonus > 0:
        return got[1]
    return None


# ---------------------------------------------------------------------------- Charger
@handler("charger")
def charger(b, f, ev, hook, buff) -> None:
    """After running at least 10 feet straight at a foe, once a turn: 1d8 more damage, or drive it 10 feet back."""
    opt, t = ev.opt, ev.target
    if opt.kind != "melee" or t is None or not _own_turn(b, f) or not charged(b, f, t):
        return
    if not once_a_turn(b, f, "charger"):
        return
    if t.size in PUSHABLE and not _bigger_by_more_than_one(f, t) and choose(
            b, f, "charge_push", t, f"The charge: drive {t.the_name} ten feet back instead of 1d8 more damage?"):
        f.__dict__["charge_push"] = t.id
        return
    extra = b.rng.randint(1, 8) * (2 if ev.crit else 1)
    ev.extra += extra
    b.dice_say(f"{f.name} (Charger): +{extra}")


@handler("charger_push")
def charger_push(b, f, ev, hook, buff) -> None:
    t = ev.target
    if f.__dict__.pop("charge_push", None) == getattr(t, "id", None) and ev.hit and t.active and b._push(f, t, 2):
        b._event("mastery", who=t.id, by=f.id, trick="push")
        b.say(f"{f.the_name}'s charge drives {t.the_name} back.", "system")


def charged(b, f, t) -> bool:
    """They have come at least 10 feet closer to `t` this turn, running (Charger)."""
    start = f.__dict__.get("turn_start_at")
    if start is None or f.moved_feet < 10:
        return False
    from realmwalker.rules import grid

    before = grid.gap((start[0], start[1], f.sq), t.space)
    return before - b.gap(f, t) >= 2


# ---------------------------------------------------------------------------- Crusher, Piercer, Slasher
@handler("crusher")
def crusher(b, f, ev, hook, buff) -> None:
    """Bludgeoning: once a turn a hit shoves 5 feet; a critical hit opens the foe to everyone until your next turn."""
    opt, t = ev.opt, ev.target
    if not ev.hit or opt.damage_type != "bludgeoning" or t is None or not (t.active or t.state == "down"):
        return
    if ev.crit and t.active:
        durations.buff(t, {"reeling": f.id, "source": f"crusher:{f.id}"}, durations.until(b, f, "turn_start"))
        b._event("mastery", who=t.id, by=f.id, trick="reeling")
        b.say(f"{t.the_name} reels from the crushing blow: everyone has an opening.", "system")
    if t.active and t.size in PUSHABLE and not _bigger_by_more_than_one(f, t) \
            and not used_this_turn(b, f, "crusher") and choose(b, f, "push", t, f"Shove {t.the_name} five feet (Crusher)?") and once_a_turn(b, f, "crusher") \
            and b._push(f, t, 1):
        b._event("mastery", who=t.id, by=f.id, trick="push")
        b.say(f"The blow knocks {t.the_name} back a step.", "system")


@handler("piercer")
def piercer(b, f, ev, hook, buff) -> None:
    """Piercing: once a turn the lowest damage die is rolled again; a critical hit adds one more die."""
    opt = ev.opt
    if opt.damage_type != "piercing" or not ev.rolls:
        return
    sides = ev.sides or 0
    if sides <= 1:
        return
    if ev.crit:
        more = b.rng.randint(1, sides)
        ev.extra += more
        b.dice_say(f"{f.name} (Piercer): one more die, {more}")
    low = min(ev.rolls)
    if low <= sides // 2 and once_a_turn(b, f, "piercer"):
        again = b.rng.randint(1, sides)
        ev.extra += again - low
        b.dice_say(f"{f.name} (Piercer): a {low} rolled again, {again}")


@handler("slasher")
def slasher(b, f, ev, hook, buff) -> None:
    """Slashing: once a turn a hit takes 10 feet off the foe's speed; a critical hit leaves it unsteady (disadvantage
    on its attacks) until your next turn."""
    opt, t = ev.opt, ev.target
    if not ev.hit or opt.damage_type != "slashing" or t is None or not t.active:
        return
    if ev.crit:
        durations.buff(t, {"unsteady": f.id, "source": f"slasher_crit:{f.id}"}, durations.until(b, f, "turn_start"))
        b._event("mastery", who=t.id, by=f.id, trick="unsteady")
        b.say(f"The cut leaves {t.the_name} unsteady.", "system")
    if once_a_turn(b, f, "slasher"):
        durations.buff(t, {"slow": 10, "source": "feat_slasher"}, durations.until(b, f, "turn_start"))
        b._event("mastery", who=t.id, by=f.id, trick="slow")


# ---------------------------------------------------------------------------- Grappler
@handler("grappler_grab")
def grappler_grab(b, f, ev, hook, buff) -> None:
    """Punch and Grab: once a turn, a punch that lands also grabs (the foe saves against your grapple DC)."""
    t = ev.target
    if not ev.hit or ev.opt.key != "unarmed" or t is None or not t.active or "grappled" in t.conditions:
        return
    if used_this_turn(b, f, "grappler") or not b.can_grapple(f, t)[0] or not choose(b, f, "grab", t, f"Grab {t.the_name} as well?") \
            or not once_a_turn(b, f, "grappler"):
        return
    b.grapple(f, t, free=True)


# ---------------------------------------------------------------------------- Shield Master
@handler("shield_bash")
def shield_bash(b, f, ev, hook, buff) -> None:
    """Once a turn after a melee hit on your turn, your shield bashes the foe: 5 feet back or down (a Strength save)."""
    opt, t = ev.opt, ev.target
    if not ev.hit or opt.kind != "melee" or t is None or not t.active or not _own_turn(b, f) or f.char is None:
        return
    shield = f.char.equipped_item("off_hand")
    if shield is None or b.t.items.category(shield) != "shield" or t.size not in PUSHABLE \
            or _bigger_by_more_than_one(f, t) or used_this_turn(b, f, "shield_bash"):
        return
    prone = t.standing and not query.condition_immune(t, "prone") and choose(
        b, f, "topple", t, f"Bash {t.the_name} to the ground with your shield? (No: drive them 5 feet back.)")
    push = not prone and choose(b, f, "push", t, f"Drive {t.the_name} 5 feet back with your shield?")
    if not (prone or push) or not once_a_turn(b, f, "shield_bash"):
        return
    dc = 8 + f.mod("str") + query.proficiency(f)
    if b._save(t, "str", dc, against=("prone",) if prone else ()):
        b.say(f"{t.the_name} takes the shield's blow and holds.", "system")
        return
    if prone and durations.give(b, t, "prone", source=f):
        b._event("prone", who=t.id)
        b._event("mastery", who=t.id, by=f.id, trick="topple")
        b.say(f"{f.the_name} smashes {t.the_name} down with {f.possessive} shield.", _side_word(f))
    elif push and b._push(f, t, 1):
        b._event("mastery", who=t.id, by=f.id, trick="push")
        b.say(f"{f.the_name}'s shield drives {t.the_name} back.", "system")


@handler("shield_interpose")
def shield_interpose(b, f, ev, hook, buff) -> None:
    """Interpose Shield: a Dexterity save made for half damage, behind a shield, takes none (the reaction)."""
    if ev.ability != "dex" or not ev.saved or ev.amount <= 0 or f.char is None or not f.reaction:
        return
    shield = f.char.equipped_item("off_hand")
    if shield is None or b.t.items.category(shield) != "shield" or query.incapacitated(f):
        return
    if not yes(b, Decision(f, "interpose_shield", f"{f.the_name} ducks behind {f.possessive} shield: take no damage "
                           f"instead of {ev.amount}? (your reaction)", [("yes", "Shield up"), ("no", "Keep it")])):
        return
    f.reaction = False
    ev.amount = 0
    b.say(f"{f.the_name} takes it all on {f.possessive} shield.", _side_word(f))


# ---------------------------------------------------------------------------- Heavy Armor Master
@handler("heavy_armor_master")
def heavy_armor_master(b, f, ev, hook, buff) -> None:
    """In heavy armour, bludgeoning, piercing and slashing damage is reduced by the proficiency bonus."""
    if ev.stage != "blow" or ev.dtype not in ("bludgeoning", "piercing", "slashing") or f.char is None:
        return
    armor = f.char.equipped_item("armor")
    if armor is None or b.t.items.get(armor.def_id).get("armor_type") != "heavy":
        return
    cut = min(ev.amount, query.proficiency(f))
    if cut > 0:
        ev.amount -= cut
        b.note_roll(f"heavy armour master: -{cut}")


# ---------------------------------------------------------------------------- Mage Slayer
@handler("guarded_mind")
def guarded_mind(b, f, ev, hook, buff) -> None:
    """A failed Intelligence, Wisdom or Charisma save made good, once between rests."""
    c = f.char
    if ev.roll != "save" or ev.ok or ev.ability not in ("int", "wis", "cha") or c is None:
        return
    from realmwalker.rules.engine import resources

    if resources.left(c, "guarded_mind") <= 0:
        return
    resources.spend(c, "guarded_mind")
    ev.ok = True
    b.dice_say(f"{f.name} (Mage Slayer, Guarded Mind): the save succeeds after all")


# ---------------------------------------------------------------------------- Sentinel
@handler("sentinel_guard")
def sentinel_guard(b, f, ev, hook, buff) -> None:
    """A foe beside you that strikes someone else invites your reaction blow."""
    att, t = ev.actor, ev.target
    if att is None or t is None or t is f or att is f or att.team == f.team or not f.reaction:
        return
    if not att.active or not f.active or not f.standing or query.incapacitated(f) or b.gap(f, att) > 1:
        return
    b.opportunity(f, att, why="sentinel")  # 2024: a hit on anyone but you


# ---------------------------------------------------------------------------- Polearm Master
def pole_option(b, f):
    """The butt end's blow (1d4 bludgeoning) after attacking with a quarterstaff, spear or polearm this turn."""
    if f.char is None or not f.__dict__.get("pole_swung") == b.round or not _own_turn(b, f):
        return None
    main = f.char.equipped_item("main_hand")
    if main is None or main.def_id not in featrules.POLEARMS and not (
            "heavy" in b.t.items.get(main.def_id).get("properties", []) and "reach" in
            b.t.items.get(main.def_id).get("properties", [])):
        return None
    from dataclasses import replace

    opt = b._weapon_option(f, f.sheet, main, "pole")
    mod = int(opt.extra.get("ability_mod", 0))
    from realmwalker.rules.character import signed

    return replace(opt, name=f"{opt.name} (butt end)", damage=f"1d4{signed(mod) if mod else ''}",
                   damage_type="bludgeoning", properties=[p for p in opt.properties if p != "heavy"])


@handler("pole_swung")
def pole_swung(b, f, ev, hook, buff) -> None:
    opt = ev.opt
    if opt.kind == "melee" and opt.item_uid is not None and opt.key == "main" and _own_turn(b, f):
        it = f.char.item(opt.item_uid) if f.char else None
        props = b.t.items.get(it.def_id).get("properties", []) if it else []
        if it is not None and (it.def_id in featrules.POLEARMS or "heavy" in props and "reach" in props):
            f.__dict__["pole_swung"] = b.round


# ---------------------------------------------------------------------------- the fighting styles
@handler("interception")
def interception(b, f, ev, hook, buff) -> None:
    """A friend beside you is hit: your reaction turns 1d10 + your proficiency bonus of it aside (with a shield or a
    simple or martial weapon in hand)."""
    t = ev.target
    if ev.stage != "blow" or t is f or ev.amount <= 0 or f.char is None or not f.reaction:
        return
    if not f.active or not f.standing or query.incapacitated(f) or b.gap(f, t) > 1 or not b.can_see(f, ev.actor):
        return
    hand = [f.char.equipped_item(s) for s in ("main_hand", "off_hand")]
    if not any(i is not None and b.t.items.category(i) in ("shield", "weapon") for i in hand):
        return
    if not yes(b, Decision(f, "interception", f"{ev.actor.the_name} hits {t.the_name} for {ev.amount}. Turn the blow "
                           f"aside? (your reaction: 1d10 + {query.proficiency(f)} less)",
                           [("yes", "Intercept"), ("no", "Keep the reaction")])):
        return
    f.reaction = False
    cut = min(ev.amount, b.rng.randint(1, 10) + query.proficiency(f))
    ev.amount -= cut
    b.say(f"{f.the_name} catches part of the blow meant for {t.the_name} ({cut} less).", _side_word(f))
    b.dice_say(f"{f.name} (Interception): -{cut}")


@handler("unarmed_grip")
def unarmed_grip(b, f, ev, hook, buff) -> None:
    """Unarmed Fighting: anyone you hold takes 1d4 bludgeoning at the start of your turn."""
    for x in list(b.fighters):
        if x.active and "grappled" in x.conditions and query.source(x, "grappled") == f.id:
            b._hit(f, x, b.rng.randint(1, 4), "bludgeoning", crit=False, weapon="grip")


# ---------------------------------------------------------------------------- bonus actions
@special("speedy_recovery")
def speedy_recovery(c, o, victim) -> None:
    """Durable: a Hit Die spent, and what it rolls healed."""
    b, f = c.b, c.caster
    if f.char is None or f.char.hit_dice <= 0:
        return
    f.char.hit_dice -= 1
    roll = b.rng.randint(1, b.t.classes[f.char.cls]["hit_die"])
    b.say(f"{f.the_name} catches {f.possessive} breath and steadies.", _side_word(f))
    b._heal(f, roll)


@special("chef_treat")
def chef_treat(c, o, victim) -> None:
    """Chef: a treat eaten, temporary hit points equal to the cook's proficiency bonus."""
    b, f = c.b, c.caster
    amount = query.proficiency(f)
    if amount > f.temp_hp:
        f.temp_hp = amount
    b.say(f"{f.the_name} eats one of the cook's treats (+{amount} temporary hit points).", _side_word(f))


@special("telekinetic_shove")
def telekinetic_shove(c, o, victim) -> None:
    """Telekinetic: a creature within 30 feet shoved 5 feet toward or away (a Strength save)."""
    b, f = c.b, c.caster
    t = victim
    if t is None or not t.active:
        return
    ability = next((x["choices"].get("increase") for x in f.char.feats if x["id"] == "telekinetic"), "int") \
        if f.char else "int"
    dc = 8 + f.mod(ability or "int") + query.proficiency(f)
    b._event("cast", by=f.id, to=t.id, spell="telekinetic", effect="push", dtype="force", area=[])
    if b._save(t, "str", dc):
        b.say(f"{t.the_name} braces against the unseen push.", "system")
        return
    if b._push(f, t, 1):
        b.say(f"An unseen force shoves {t.the_name} back.", _side_word(f))
