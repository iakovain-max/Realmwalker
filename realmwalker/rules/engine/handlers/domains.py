"""The Light and the Trickery Domains (PHB 2024, the cleric's subclasses; Expansion 5 Part B).

The Light Domain: Warding Flare (`warding_flare`, from `Battle._attack` before the roll: a reaction, the battle's
judgement, asked under the Reactions setting "all"; Improved Warding Flare's temporary hit points), Radiance of the
Dawn (the Channel Divinity "radiance_of_the_dawn": magical darkness within 30 feet ends, foes there save), Corona of
Light (the buff "corona": sunlight 60 feet round; `corona_against` puts foes' saves at a disadvantage in
`query.save_roll`).

The Trickery Domain: Blessing of the Trickster (`blessed`: the mark "kept:trickster_blessing" on the one blessed, read
by every Stealth roll; `bless_after_rest` gives it to the party's worst sneak), Invoke Duplicity (a Token of kind
"duplicity" on the field: `double_of`; spells are cast from its square through `standing_in`, `cast_from_double`
and `Battle.spell_targets`/`spell_points`; `distracted` gives the advantage of Distract and Improved Duplicity in
`query.attack_roll`), Trickster's Transposition (the swap as it is made or moved), Improved Duplicity's healing as it
ends (`double_ends`, from `Battle._start_turn` and `check_doubles`).
"""

from __future__ import annotations

from contextlib import contextmanager

from realmwalker.core import dice
from realmwalker.rules import grid
from realmwalker.rules import spells as spellrules
from realmwalker.rules.engine import reactions
from realmwalker.rules.engine import resources as res
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.reactions import Decision

DOUBLE = "duplicity"
BLESSING = "kept:trickster_blessing"


def _word(f) -> str:
    return "good" if f.side == "party" else "info"


# ---------------------------------------------------------------------------- the Light Domain
def warding_flare(b, att, target, opt, adv: bool, dis: bool) -> tuple[bool, str | None]:
    """A Light cleric who sees the attacker within 30 feet flares in its eyes with the reaction: the roll is at a
    disadvantage. Returns (disadvantage now, why)."""
    from realmwalker.rules.engine import query

    if dis:
        return dis, None  # (already at a disadvantage, or cancelled out by an advantage: a flare would add nothing)
    for x in b.fighters:
        if x.char is None or x.team == att.team or x.team != target.team or not x.has_trait("warding_flare"):
            continue
        if not x.active or not x.reaction or query.incapacitated(x) or res.left(x.char, "warding_flare") <= 0:
            continue
        if b.feet(x, att) > 30 or not b.can_see(x, att):
            continue
        left = res.left(x.char, "warding_flare")
        worth = _flare_worth(b, x, att, target, opt, left)
        if not reactions.yes(b, Decision(
                x, "warding_flare", f"{att.the_name} strikes at {target.the_name}. Warding Flare? (your reaction: "
                f"the blow is at a disadvantage; {left} left)", [("yes", "Flare"), ("no", "Let it come")],
                default="yes" if worth else "no", free=True)):
            continue
        x.reaction = False
        res.spend(x.char, "warding_flare")
        b._event("flare", by=x.id, at=att.id, to=target.id)
        b.say(f"Light flares from {x.the_name}'s holy symbol into {att.the_name}'s eyes.", _word(x))
        if x.has_trait("warding_flare_improved"):
            gift = dice.roll("2d6", b.rng).total + max(0, x.mod("wis"))
            if gift > target.temp_hp:
                target.temp_hp = gift
                b.dice_say(f"{x.name} (Improved Warding Flare): {target.name} +{gift} temporary hit points")
        return True, "a warding flare"
    return dis, None


def _flare_worth(b, x, att, target, opt, left: int) -> bool:
    """The battle's judgement: a blow likely to land, at a friend in a bad way, or a heavy one; with uses to spare,
    any blow likely to land."""
    from realmwalker.rules.engine import estimates

    if b.hit_chance(att, opt, target) < 0.35:
        return False
    heavy = estimates.avg(opt.damage) >= max(1, target.hp) * 0.3 if getattr(opt, "damage", "") else False
    return left >= 2 or heavy or target.hp <= target.max_hp // 2 or target.concentration is not None


def dawn_worth(b, f) -> str | None:
    """Radiance of the Dawn wants a foe within 30 feet, or magical darkness there to end."""
    if any(e.standing and b.feet(f, e) <= 30 for e in b.enemies_of(f)):
        return None
    if _darkness_near(b, f):
        return None
    return "no foe or darkness within 30 feet"


def _area(b, f) -> list:
    return b.field.area("emanation", 30, origin=f.space, toward=(f.x, f.y))


def _darkness_near(b, f) -> list:
    cells = set(_area(b, f))
    return [z for z in b.zones if z.kind == "darkness" and z.cells & cells]


@special("radiance_of_the_dawn")
def radiance_of_the_dawn(c, o, victim) -> None:
    """Channel Divinity: a flash of light in a 30-foot emanation. Magical darkness in it ends; each foe in it makes a
    Constitution save against 2d10 + the cleric's level radiant damage, half on a success."""
    b, f = c.b, c.caster
    area = _area(b, f)
    cells = set(area)
    b.say(f"{f.the_name} raises the holy symbol, and the light of the dawn breaks from it.", "magic")
    b._event("cast", by=f.id, to=None, spell="radiance_of_the_dawn", effect="burst", dtype="radiant", area=area,
             point=None, shape="emanation", look="burst")
    for z in _darkness_near(b, f):
        b._remove_zone(z)
        b.say("The magical darkness burns away in the dawn.", "magic")
    dc = spellrules.save_dc(f.sheet, b.t)
    expr = f"2d10+{f.char.level if f.char is not None else 1}"
    before = b.__dict__.get("_dawn")
    b._dawn = f  # (Corona of Light: foes in it save against the Dawn at a disadvantage)
    try:
        for e in [e for e in b.enemies_of(f) if e.active and cells & set(e.cells)]:
            b._save_damage(f, e, "con", dc, expr, "radiant", "half")
    finally:
        b._dawn = before


def corona_out(b, f) -> str | None:
    return "the corona already shines" if corona_of(f) else None


def corona_of(f):
    return next((bf for bf in f.buffs if bf.get("corona")), None)


@special("corona_of_light")
def corona_of_light(c, o, victim) -> None:
    """A minute of sunlight round the cleric: bright 60 feet (the light), foes in it save at a disadvantage against the
    cleric's Radiance of the Dawn and fire and radiant spells."""
    b, f = c.b, c.caster
    f.buffs = [bf for bf in f.buffs if not bf.get("corona")]
    f.buffs.append({"corona": True, "light": 12, "rounds": 10, "source": "corona_of_light"})
    b._event("cast", by=f.id, to=f.id, spell="corona_of_light", effect="buff", dtype="radiant", area=list(f.cells),
             point=None, shape="", look="aura")
    b.say(f"{f.the_name} blazes like the sun at noon.", "magic")


def corona_against(b, f) -> str | None:
    """Why a save is at a disadvantage under a foe's corona (None if it is not): `f` is in the bright light of a cleric
    whose Corona of Light shines, and the save is against that cleric's Radiance of the Dawn or a spell of theirs that
    deals fire or radiant damage."""
    caster = b.__dict__.get("_dawn")
    dawn = caster is not None
    if caster is None:
        caster = b.__dict__.get("_casting")
    if caster is None or not getattr(caster, "buffs", None) or caster.team == f.team or not corona_of(caster):
        return None
    if not dawn:
        spell = b.__dict__.get("_casting_spell")
        if spell is None or not _fiery(spell):
            return None
    if b.feet(caster, f) > 60:
        return None
    return "the corona's glare"


def _fiery(spell: dict) -> bool:
    for o in spellrules.ops(spell):
        for _, dtype, _up in spellrules.damage_parts(o):
            if dtype in ("fire", "radiant"):
                return True
    return False


# ---------------------------------------------------------------------------- the Trickery Domain: the blessing
def blessed(char) -> bool:
    """Blessing of the Trickster: advantage on Stealth."""
    return char is not None and bool((char.effects or {}).get(BLESSING))


def bless(party, who, stamp: int = 1) -> None:
    """The blessing moves to `who` (it ends on anyone else: one at a time). `stamp` says when it was laid (the
    newest wins where the party is gathered again: `one_blessing`)."""
    for c in party:
        if c is not None and c.effects:
            c.effects.pop(BLESSING, None)
    if who is not None:
        who.effects[BLESSING] = max(1, int(stamp))


def one_blessing(people) -> None:
    """Only the newest blessing holds (one laid in a fight while a companion waited elsewhere with the old one)."""
    have = [c for c in people if c is not None and (c.effects or {}).get(BLESSING)]
    if len(have) > 1:
        keep = max(have, key=lambda c: c.effects[BLESSING])
        for c in have:
            if c is not keep:
                c.effects.pop(BLESSING, None)


def bless_after_rest(game) -> list[str]:
    """A Trickery cleric rising from a long rest blesses the party's worst sneak (the last blessing ended with the
    rest). Returns what to say."""
    everyone = list(game.party) + list(getattr(game, "waiting", None) or ())
    priests = [c for c in game.party if c.alive and "blessing_of_the_trickster" in c.features]
    if not priests:
        bless(everyone, None)  # (the long rest ends it, priest or none)
        return []
    alive = [c for c in game.party if c.alive]
    worst = min(alive, key=lambda c: (game.sheet(c).skill_bonus("stealth"), c is not priests[0]))
    bless(everyone, worst, int(game.world.time) * 100)
    who = "themselves" if worst is priests[0] else worst.name.split()[0]
    return [f"{priests[0].name.split()[0]} lays the Trickster's blessing on {who}: soft feet until the next long rest."]


def blessable(b, f) -> list:
    """Whom a Blessing of the Trickster can be laid on: the cleric, or a friend within 30 feet, not blessed yet."""
    return [x for x in b.team(f.team) if x.char is not None and x.bond is None and (x.active or x.state == "down")
            and (x is f or b.feet(f, x) <= 30 and b.can_see(f, x)) and not blessed(x.char)]


@special("blessing_of_the_trickster")
def blessing_of_the_trickster(c, o, victim) -> None:
    b, f = c.b, c.caster
    t = victim or c.target or f
    if t.char is None:
        return
    bless([x.char for x in b.fighters if x.char is not None and x.team == f.team], t.char,
          int(b.now) * 100 + b.round)
    b._event("cast", by=f.id, to=t.id, spell="blessing_of_the_trickster", effect="buff", dtype="", area=list(t.cells),
             point=None, shape="", look="aura")
    b.say(f"{f.the_name} touches {'their own brow' if t is f else t.the_name} with the Trickster's blessing: "
          "soft feet and a shadow that keeps close.", "magic")


# ---------------------------------------------------------------------------- the Trickery Domain: the double
def double_of(b, f):
    return next((t for t in b.tokens if t.owner == f.id and t.kind == DOUBLE), None)


def no_double(b, f) -> str | None:
    return "your double already stands" if double_of(b, f) is not None else None


def double_up(b, f) -> str | None:
    return None if double_of(b, f) is not None else "no double on the field"


def _free(b, x: int, y: int, occ: set) -> bool:
    return b.field.in_bounds(x, y) and not b.field.solid[x, y] and b.field.passable(x, y) and (x, y) not in occ \
        and not any(t.x == x and t.y == y and t.kind == DOUBLE for t in b.tokens)


def _spots_beside(b, f, e, start, reach_sq: int, home_sq: int) -> list:
    """Free squares beside the foe `e` within `reach_sq` squares of `start` and `home_sq` of the cleric, seen."""
    occ = {c for x in b.on_field() for c in x.cells}
    out = []
    for x in range(e.x - 1, e.x + e.sq + 1):
        for y in range(e.y - 1, e.y + e.sq + 1):
            if (x, y) in e.cells or not _free(b, x, y, occ - set(f.cells)):
                continue
            if grid.gap((start[0], start[1], 1), (x, y, 1)) > reach_sq or grid.gap(f.space, (x, y, 1)) > home_sq:
                continue
            if (x, y) in f.cells or not b.can_see_point(f, x, y):
                continue
            out.append((x, y))
    return out


def _best_spot(b, f, e, spots: list):
    """Flanking the foe with the cleric first; else the square that reaches farthest from the cleric."""
    return max(spots, key=lambda p: (grid.flanks(f.space, (p[0], p[1], 1), e.space),
                                     grid.gap(f.space, (p[0], p[1], 1)), -p[0], -p[1])) if spots else None


def new_targets(b, f) -> list:
    """Foes a double can be made beside: a free square beside them within 30 feet of the cleric, seen."""
    return [e for e in b.enemies_of(f) if e.active and b.can_see(f, e) and _spots_beside(b, f, e, (f.x, f.y), 6, 6)]


def move_targets(b, f) -> list:
    """Foes the double can be moved beside: 50 feet from where it stands, within 120 feet of the cleric."""
    tok = double_of(b, f)
    if tok is None:
        return []
    return [e for e in b.enemies_of(f) if e.active and b.can_see(f, e)
            and _spots_beside(b, f, e, (tok.x, tok.y), 10, 24)]


@special("invoke_duplicity")
def invoke_duplicity(c, o, victim) -> None:
    """Channel Divinity, a Bonus Action: a perfect double in a free square within 30 feet (beside the foe it is aimed
    at), for a minute. With Trickster's Transposition (`swap`) the cleric and the double change places."""
    from realmwalker.rules.combat import Token

    b, f = c.b, c.caster
    e = victim or c.target
    spot = _best_spot(b, f, e, _spots_beside(b, f, e, (f.x, f.y), 6, 6)) if e is not None else None
    if spot is None:
        if f.char is not None:
            f.char.uses["channel_divinity"] = f.char.uses.get("channel_divinity", 0) + 1
        return
    tok = Token(b._zone_id(), DOUBLE, spot[0], spot[1], f.id, rounds=9, spell="invoke_duplicity")  # (a minute)
    b.tokens.append(tok)
    b._event("token", id=tok.id, what=tok.kind, x=tok.x, y=tok.y, owner=f.id)
    b.say(f"A second {f.name.split(',')[0]} stands beside {e.the_name}, smiling the same smile.", "magic")
    if o.get("swap"):
        _swap(b, f, tok)


@special("move_duplicity")
def move_duplicity(c, o, victim) -> None:
    """A Bonus Action: the double moves up to 50 feet, beside the foe it is aimed at (and the cleric may swap)."""
    b, f = c.b, c.caster
    tok, e = double_of(b, f), victim or c.target
    if tok is None or e is None:
        return
    spot = _best_spot(b, f, e, _spots_beside(b, f, e, (tok.x, tok.y), 10, 24))
    if spot is None:
        return
    start = (tok.x, tok.y)
    tok.x, tok.y = spot
    b._event("token_move", id=tok.id, path=[start, spot])
    b.say(f"{f.the_name}'s double glides to {e.the_name}.", "magic")
    if o.get("swap"):
        _swap(b, f, tok)


def _swap(b, f, tok) -> None:
    """Trickster's Transposition: the cleric and the double change places (a teleport)."""
    occ = {c for x in b.on_field() if x is not f for c in x.cells}
    if f.sq != 1 or (tok.x, tok.y) in occ:
        return
    start = (f.x, f.y)
    f.x, f.y, tok.x, tok.y = tok.x, tok.y, start[0], start[1]
    b._event("teleport", who=f.id, path=[start, (f.x, f.y)])
    b._event("token_move", id=tok.id, path=[(f.x, f.y), start])
    b._sync_grapples(f)
    b.say(f"{f.the_name} and the double change places in a blink: which was which?", "magic")


def double_ends(b, f, tok) -> None:
    """The double is gone. With Improved Duplicity, the cleric or the friend beside it worst off regains the cleric's
    level in hit points."""
    if tok in b.tokens:
        b.tokens.remove(tok)
        b._event("token_end", id=tok.id)
    if b.outcome is not None or f.char is None or not f.has_trait("improved_duplicity"):
        return
    near = [x for x in b.team(f.team) if (x.active or x.state == "down") and x.hp < x.max_hp
            and (x is f or grid.gap((tok.x, tok.y, 1), x.space) <= 1)]
    if near:
        x = min(near, key=lambda x: (x.hp / max(1, x.max_hp), x.id))
        b.say(f"The double fades into {x.the_name}, and warmth with it.", "magic")
        b._heal(x, f.char.level)


def check_doubles(b) -> None:
    """A double ends early when its maker is Incapacitated (or down, or gone)."""
    from realmwalker.rules.engine import query

    for tok in [t for t in b.tokens if t.kind == DOUBLE]:
        owner = next((x for x in b.fighters if x.id == tok.owner), None)
        if owner is None or not owner.active or query.incapacitated(owner):
            double_ends(b, owner, tok) if owner is not None else b.tokens.remove(tok)


def distracted(b, att, target, a_space) -> str | None:
    """Distract and Improved Duplicity: a foe within 5 feet of a double (and able to see it) is open to its maker when
    the maker is beside it too, and to all the maker's friends with Improved Duplicity."""
    if "blinded" in target.conditions:
        return None
    for tok in b.tokens:
        if tok.kind != DOUBLE or grid.gap((tok.x, tok.y, 1), target.space) > 1:
            continue
        owner = next((x for x in b.fighters if x.id == tok.owner), None)
        if owner is None or owner.team != att.team:
            continue
        if owner is att and grid.gap(a_space, target.space) <= 1:
            return "the double distracts them"
        if owner.has_trait("improved_duplicity"):
            return "the double distracts them"
    return None


# ---------------------------------------------------------------------------- casting from the double
def casts_through(spell: dict) -> bool:
    """A spell that can be cast as though from the double's square: one with a range of at least 10 feet (not self or
    touch) that does not move its caster."""
    r = spell.get("range", 60)
    if r in ("self", "touch") or not isinstance(r, int) or r < 10:
        return False
    return spell.get("target") in ("enemy", "ally", "creature", "point", "bound") and not spellrules.has_op(
        spell, "teleport")


def casting_double(b, f):
    """The double a character's spells may also be aimed from (None while already aiming from it)."""
    if not b.tokens or f.char is None or f.__dict__.get("at_double"):
        return None
    return double_of(b, f)


@contextmanager
def standing_in(b, f, tok):
    """The cleric counted as standing in the double's square (for range, sight lines and areas) while a spell is
    aimed or cast from there; then back."""
    start = (f.x, f.y)
    f.x, f.y = tok.x, tok.y
    f.__dict__["at_double"] = True
    try:
        yield
    finally:
        f.x, f.y = start
        f.__dict__.pop("at_double", None)


def cast_from_double(b, f, sid: str, target, point):
    """The double to cast from: when the target (or point) is out of the cleric's own reach but within the double's."""
    from realmwalker.rules.combat import spell_id

    if f.char is None or not b.tokens or f.__dict__.get("at_double"):
        return None
    tok = double_of(b, f)
    if tok is None:
        return None
    try:
        spell = b.t.spells[spell_id(sid)]
    except KeyError:
        return None
    if not casts_through(spell):
        return None
    if spell["target"] == "point":
        if point is None or point in b._spell_points(f, sid):
            return None
        with standing_in(b, f, tok):
            mine = point in b._spell_points(f, sid)
        return tok if mine and b.can_see_point(f, *point) else None
    if target is None or target in b._spell_targets(f, sid):
        return None
    with standing_in(b, f, tok):
        mine = target in b._spell_targets(f, sid)
    return tok if mine and b.can_see(f, target) else None
