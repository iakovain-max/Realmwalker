"""The Eldritch Knight and the Arcane Trickster (PHB 2024; Expansion 4 Part B): the fighter's and rogue's arcane paths.

Both are third casters of the wizard's list through the class's spellcasting door (`rules/spells.casting`: the
subclass's own table). What this module adds:

- Eldritch Strike: a weapon hit leaves the buff `eldritch_struck` (the knight's id) until the end of the knight's next
  turn; `query.save_roll` gives Disadvantage on the next save against a spell of the knight's, and the casting spends
  it (`spend_struck`, from `effects.cast`).
- Magical Ambush: a trickster who was hidden or Invisible as the spell began (`Battle.do_cast` notes `ambush_turn`)
  gives Disadvantage on the saves against it that turn (`query.save_roll`).
- War Magic and Improved War Magic are `Battle.war_magic` (a casting in place of the Attack action's attacks); War
  Bond, Arcane Charge, the unseen Mage Hand, Versatile Trickster and Spell Thief are the battle's (abilities, the
  Cunning Strike's Trip and a reaction to a spell).
"""

from __future__ import annotations

from realmwalker.rules.engine import durations
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.events import handler


@handler("eldritch_strike")
def eldritch_strike(b, f, ev, hook, buff) -> None:
    """A weapon hit undercuts the creature's ward against the knight's next spell."""
    t = ev.target
    if not ev.hit or t is None or ev.opt is None or str(ev.opt.kind).startswith("spell") or not t.active:
        return
    durations.buff(t, {"eldritch_struck": f.id, "source": f"eldritch:{f.id}"}, durations.until(b, f, "turn_end"))


def spend_struck(b, caster) -> None:
    """The casting is over: an Eldritch Strike that weakened a save against it is spent."""
    used = b.__dict__.pop("_struck_used", None)
    if not used or caster is None:
        return
    for x in b.fighters:
        if x.id in used:
            x.buffs = [bf for bf in x.buffs if bf.get("eldritch_struck") != caster.id]


def ambush_ready(b, f) -> bool:
    """A trickster's spell begun out of sight (Magical Ambush): hidden, or Invisible."""
    from realmwalker.rules.engine import query

    return f.has_trait("magical_ambush") and (f.hidden > 0 or query.flag(f, "unseen"))


# ---------------------------------------------------------------------------- War Bond and Arcane Charge
def bond_away(b, f) -> str | None:
    from realmwalker.rules import war_bond

    if f.bonus <= 0:
        return "no bonus action left"
    return None if war_bond.away(b, f) else "your bonded weapons are in hand"


@special("call_bonded")
def call_bonded(c, o, victim) -> None:
    """A bonded weapon flies to the knight's hand: one thrown and lying on the field first, else the other bond."""
    from realmwalker.rules import war_bond

    b, f = c.b, c.caster
    away = war_bond.away(b, f)
    if not away:
        return
    thrown = [it for it in away if it in b.thrown]
    it = thrown[0] if thrown else away[0]
    name = b.t.items.name(it, False)
    if war_bond.call(b, f, it):
        b._event("rearm", who=f.id)
        b.say(f"The {name} {'leaps from the ground and ' if thrown else ''}flies to {f.the_name}'s hand.",
              "good" if f.side == "party" else "info")


@handler("arcane_charge")
def arcane_charge(b, f, ev, hook, buff) -> None:
    """Action Surge: the knight first steps through space, up to 30 feet, to the weakest foe out of reach (the
    battle's judgement; none when a foe is in reach already)."""
    from realmwalker.rules import grid

    if ev.ability != "action_surge" or f.char is None or not f.has_trait("arcane_charge"):
        return
    reach = max(1, b.reach_of(f))
    foes = [e for e in b.enemies_of(f) if e.active and e.standing]
    if not foes or any(b.gap(f, e) <= reach for e in foes):
        return
    spots = arrival_points(b, f)
    for e in sorted(foes, key=lambda e: (e.hp, e.id)):
        near = [p for p in spots if grid.gap((p[0], p[1], f.sq), e.space) <= reach]
        if near:
            best = min(near, key=lambda p: (grid.gap(f.space, (p[0], p[1], 1)), p))
            start = (f.x, f.y)
            f.x, f.y = best
            b._event("teleport", who=f.id, path=[start, best])
            b._sync_grapples(f)
            b.say(f"{f.the_name} vanishes and steps out of the air beside {e.the_name} (Arcane Charge).", "magic")
            return


def arrival_points(b, f, feet: int = 30) -> set:
    """Unoccupied squares within `feet` that the fighter can see (where a teleport may land)."""
    from realmwalker.rules import grid

    n = feet // grid.SQUARE_FT
    occ = {c for x in b.on_field() if x is not f for c in x.cells}
    out = set()
    for x in range(max(0, f.x - n), min(b.field.width, f.x + f.sq + n)):
        for y in range(max(0, f.y - n), min(b.field.height, f.y + f.sq + n)):
            if grid.gap(f.space, (x, y, 1)) > n or (x, y) in f.cells or (x, y) in occ:
                continue
            if b.field.solid[x, y] or not b.field.passable(x, y) or not b.can_see_point(f, x, y):
                continue
            out.add((x, y))
    return out


# ---------------------------------------------------------------------------- the unseen hand
HAND = "mage_hand"


def hand_of(b, f):
    return next((t for t in b.tokens if t.owner == f.id and t.kind == HAND), None)


def hand_known(b, f) -> str | None:
    if f.char is None or HAND not in (f.char.spells or {}).get("cantrips", ()):
        return "Mage Hand not known"
    return None if f.bonus > 0 else "no bonus action left"


@special("unseen_hand")
def unseen_hand(c, o, victim) -> None:
    """Mage Hand Legerdemain: the unseen hand is cast (or sent on) with the bonus action, to a creature within 30
    feet; it stays a minute."""
    from realmwalker.rules.combat import Token

    b, f = c.b, c.caster
    t = victim if victim is not None else c.target
    if t is None:
        return
    tok = hand_of(b, f)
    if tok is None:
        tok = Token(b._zone_id(), HAND, t.x, t.y, f.id, rounds=10, spell=HAND)
        b.tokens.append(tok)
        b._event("token", id=tok.id, what=tok.kind, x=tok.x, y=tok.y, owner=f.id)
        if f.side == "party":
            b.say(f"{f.the_name}'s unseen hand reaches out towards {t.the_name}.", "magic")
        return
    start = (tok.x, tok.y)
    tok.x, tok.y = t.x, t.y
    b._event("token_move", id=tok.id, path=[start, (tok.x, tok.y)])
    if f.side == "party":
        b.say(f"{f.the_name} steers the unseen hand to {t.the_name}.", "magic")


def trip_beside_hand(b, f, t, dc: int) -> None:
    """Versatile Trickster: a Cunning Strike's Trip catches another creature within 5 feet of the unseen hand."""
    from realmwalker.rules.engine.handlers import rogue

    tok = hand_of(b, f)
    if tok is None or not f.has_trait("versatile_trickster"):
        return
    near = [e for e in b.enemies_of(f) if e is not t and e.active and e.standing
            and e.size not in ("huge", "gargantuan")
            and max(abs(e.x - tok.x), abs(e.y - tok.y)) <= 1]
    if not near:
        return
    x = min(near, key=lambda e: (e.hp, e.id))
    if not b._save(x, "dex", dc, against=("prone",)) and durations.give(b, x, "prone", source=f):
        b._event("prone", who=x.id)
        b.say(f"An unseen hand hooks {x.the_name}'s ankle: down they go (Versatile Trickster).", rogue._word(f))


# ---------------------------------------------------------------------------- Spell Thief
def spell_thief(b, caster, spell: dict, sid: str, level: int, target, area) -> list:
    """Spell Thief: a trickster the spell is aimed at or caught in turns it with the reaction (the battle's judgement:
    a harmful spell of level 1 or more). The caster's Intelligence save against the trickster's spell DC; a failure:
    the spell does nothing to the trickster, who knows it until their next long rest, and the caster cannot cast it
    again this fight. Returns those the spell now passes by."""
    from realmwalker.rules import spells as sr
    from realmwalker.rules.engine import query
    from realmwalker.rules.engine import resources as res

    if level < 1 or caster is None or not sr.harms(spell):
        return []
    out = []
    cells = set(area or ())
    for x in b.fighters:
        if x.team == caster.team or x.char is None or not x.active or not x.reaction or query.incapacitated(x):
            continue
        if not x.has_trait("spell_thief") or res.left(x.char, "spell_thief") <= 0:
            continue
        if x is not target and not (cells & set(x.cells)):
            continue
        x.reaction = False
        res.spend(x.char, "spell_thief")
        dc = sr.save_dc(x.sheet, b.t)
        b.say(f"{x.the_name} reaches into the spell as it is woven (Spell Thief).", "magic")
        if b._save(caster, "int", dc):
            b.say(f"{caster.the_name} holds on to the spell.", "info")
            continue
        out.append(x)
        caster.__dict__.setdefault("stolen", set()).add(sid)
        if level <= sr.max_spell_level(x.char, b.t) and sid in b.t.spells:
            x.char.spells["stolen"] = sid
            b.say(f"<good>{x.the_name} tears {spell['name']} out of {caster.the_name}'s mind</>: it passes "
                  f"{x.the_name} by, and is {x.the_name}'s until the next long rest.", "good")
        else:
            b.say(f"{spell['name']} unravels around {x.the_name}, too great a spell to keep.", "good")
    return out
