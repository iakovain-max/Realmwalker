"""Animal Shapes and Shapechange outside a fight (Expansion 3 F.8), through game/spellwork's door (subjects, problem,
cast): the forms to choose on the Spells page, the shapes the party wears on the road (`rules/shapes.record` on each
character: its form, its hour, the borrowed hit points it has left), changing them again or leaving them with no slot
(the Magic action), and their end. What a shape does in a fight is `Battle.shape` (rules/combat.py); what it does to
the travel pace and the crossings is `GameState.pace` and `magic_crossing`, which ask `party_forms` here."""
from __future__ import annotations

from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.divining import Subject
from realmwalker.rules import shapes
from realmwalker.rules import spells as spellrules


def _first(c) -> str:
    return esc(c.name.split()[0])


def _name(tables, cid: str) -> str:
    from realmwalker.rules.allies import a_or_an

    return a_or_an(tables.creatures[cid]["name"])


def _op(game, sid: str) -> dict:
    return spellrules.op(game.tables.spells[sid], "shape") or {}


# ---------------------------------------------------------------------------- what the party wears
def form_of(game, char) -> str | None:
    """The creature a member of the party is shaped as just now (None: themselves)."""
    rec = shapes.on_road(char, game.world.time)
    return rec["form"] if rec is not None and rec["form"] in game.tables.creatures else None


def party_forms(game) -> list[str | None]:
    """The form of each living member of the party (None for one in their own shape)."""
    return [form_of(game, c) for c in game.party if c.alive]


def all_shaped(game, test) -> bool:
    """Every living member wears a shape that passes `test(tables, form)` (all fly, all swim)."""
    forms = party_forms(game)
    return bool(forms) and all(cid is not None and test(game.tables, cid) for cid in forms)


def no_hands(game, char) -> str | None:
    """Why a shaped member cannot use a thing it carries (its gear has melded into the form), or None."""
    cid = form_of(game, char)
    if cid is None:
        return None
    return f"{_first(char)} is {_name(game.tables, cid)} just now: the gear has melded into the shape"


def words(game, char) -> str | None:
    """A line for the sheet and the Spells page: the shape a member wears and how long it has left."""
    rec = shapes.on_road(char, game.world.time)
    if rec is None or rec["form"] not in game.tables.creatures:
        return None
    from realmwalker.game.magic import lasting_text

    left = max(0.0, (float(rec["until"]) - game.world.time) / 60)
    spell = game.tables.spells.defs.get(rec.get("spell"), {}).get("name", "a spell")
    return (f"<magic>{esc(game.tables.creatures[rec['form']]['name'].capitalize())}</> ({esc(spell)}) "
            f"<dim>({lasting_text(left)} left, {int(rec.get('temp', 0))} borrowed hit points)</>")


# ---------------------------------------------------------------------------- the Spells page
def road_forms(game, caster, sid: str) -> list[str]:
    """The forms a spell offers on the road: the fliers first, then the swiftest, then the strongest; never one that
    breathes only water (the land is dry)."""
    t = game.tables
    o = _op(game, sid)
    top = float(o["cr"]) if o.get("cr") is not None else float(caster.level)
    out = [c for c in shapes.forms(t, o.get("forms", ["beast"]), top, **shapes.limits(o))
           if not shapes.breathes_only_water(t, c)]
    return sorted(out, key=lambda c: (not shapes.flies(t, c), -shapes.speed(t, c), -shapes.strength(t, c), c))


def _group(tables, cid: str) -> str:
    if shapes.flies(tables, cid):
        return "wings"
    return "swift" if shapes.speed(tables, cid) >= 40 else "strong"


def _form_words(tables, cid: str) -> str:
    sp = tables.creatures[cid].get("speeds") or {}
    bits = []
    if sp.get("fly"):
        bits.append(f"flies {sp['fly']} ft")
    bits.append(f"walks {sp.get('walk', tables.creatures[cid].get('speed', 30))} ft")
    if sp.get("swim"):
        bits.append(f"swims {sp['swim']}")
    if sp.get("climb"):
        bits.append(f"climbs {sp['climb']}")
    cr = float(tables.creatures[cid].get("cr", 0))
    rating = {0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}.get(cr, str(int(cr)))
    return f"{_name(tables, cid)} (CR {rating}): {', '.join(bits)}, {shapes.form_hp(tables, cid)} hit points"


def held_by(game, caster, sid: str) -> list:
    """The members of the party wearing a shape this caster gave them with this spell, still working."""
    return [c for c in game.party if c.alive and (rec := shapes.on_road(c, game.world.time)) is not None
            and rec.get("spell") == sid and rec.get("caster") == caster.name]


def subjects(game, caster, sid: str) -> list[Subject]:
    t = game.tables
    mine = held_by(game, caster, sid)
    if mine:  # (the spell is working: change the shapes again, or let them go, with no slot)
        who = "everyone" if len(mine) > 1 else _first(mine[0])
        out = [Subject(f"{who} back to their own shape (no slot)", "shape", "leave", data={"free": True, "group": "leave"})]
        if len(mine) > 1:
            out += [Subject(f"{_first(c)} back to their own shape (no slot)", "shape", ("leave", c.name),
                            data={"free": True, "group": "leave"}) for c in mine]
        for cid in road_forms(game, caster, sid):
            out.append(Subject(f"{who} into {_form_words(t, cid)} (no slot)", "shape", cid,
                               data={"free": True, "form": cid, "group": _group(t, cid)}))
        return out
    return [Subject(_form_words(t, cid), "shape", cid, data={"form": cid, "group": _group(t, cid)})
            for cid in road_forms(game, caster, sid)]


def problem(game, caster, sid: str, target) -> str | None:
    if not isinstance(target, Subject):
        return "choose a shape (←→)"
    if target.data.get("free") and not held_by(game, caster, sid):
        return "the spell is not working on anyone now"
    if target.data.get("form") and target.data["form"] not in road_forms(game, caster, sid):
        return "not a shape this spell can give"
    if not target.data.get("free") and any(form_of(game, c) is not None for c in _takers(game, caster, sid)):
        return "someone wears a shape already: let it go first"
    return None


def _takers(game, caster, sid: str) -> list:
    """Who takes the shape on the road: the whole party for Animal Shapes (all willing; a caster can leave it whenever
    it likes), the caster alone for Shapechange."""
    if game.tables.spells[sid]["target"] == "all_allies":
        return [c for c in game.party if c.alive]
    return [caster]


def free_use(game, caster, sid: str, target) -> list[str] | None:
    """Changing the shapes again or letting them go: a Magic action, no slot (None: not one of those)."""
    if not isinstance(target, Subject) or not target.data.get("free"):
        return None
    mine = held_by(game, caster, sid)
    if not mine:
        return ["The spell is not working on anyone now."]
    game.dirty = True
    if target.ref == "leave" or (isinstance(target.ref, tuple) and target.ref[0] == "leave"):
        going = mine if target.ref == "leave" else [c for c in mine if c.name == target.ref[1]]
        for c in going:
            shapes.drop(c)
        names = " and ".join(_first(c) for c in going) if len(going) <= 2 else "everyone"
        game.cue("spell")
        return [f"{names} {'is' if len(going) == 1 else 'are'} themselves again, blinking, a little stiff in limbs "
                f"that feel too few or too many."]
    cid = target.data["form"]
    for c in mine:
        rec = shapes.record(c)
        rec["form"], rec["temp"] = cid, shapes.form_hp(game.tables, cid)
    game.cue("spell")
    return [f"<magic>At a word from {_first(caster)} the shapes flow and settle again:</> "
            f"{'everyone is' if len(mine) > 1 else _first(mine[0]) + ' is'} {_name(game.tables, cid)} now."]


def cast(game, caster, sid: str, target, level: int) -> list[str]:
    if not isinstance(target, Subject) or not target.data.get("form"):
        return []
    t = game.tables
    o = _op(game, sid)
    spell = t.spells[sid]
    cid = target.data["form"]
    hours = float(o.get("hours", 1))
    until = game.world.time + hours * 60
    takers = _takers(game, caster, sid)
    for c in takers:
        shapes.keep(c, {"form": cid, "spell": sid, "until": until, "temp": shapes.form_hp(t, cid),
                        "caster": caster.name, "conc": bool(spell.get("concentration"))})
    from realmwalker.game.magic import lasting_text

    who = "the whole party" if len(takers) > 1 else _first(caster)
    out = [f"<magic>{_first(caster)} speaks the words of {spell['name']}, and {who} "
           f"{'twist and settle' if len(takers) > 1 else 'twists and settles'} into the shape of "
           f"{_name(t, cid)}</> for {lasting_text(hours)}."]
    if shapes.flies(t, cid):
        out.append("<dim>On wings the party crosses rivers, lakes, the sea and the mountains as the crow flies.</>")
    elif shapes.speed(t, cid) > 30:
        out.append("<dim>On four swift legs the party travels faster than any walker.</>")
    if any(spellrules.is_caster(c, t) for c in takers) and "spells" not in (o.get("keeps") or ()):
        out.append("<dim>No spells while in it; the caster can let the shapes go at any moment (no slot).</>")
    return out


# ---------------------------------------------------------------------------- as time passes
def tick(game) -> None:
    """A shape whose hour has come ends (spellwork's tick, as time passes)."""
    now = game.world.time
    for c in game.party:
        rec = shapes.record(c)
        if rec is not None and float(rec.get("until", 0)) <= now:
            shapes.drop(c)
            game.dirty = True
            if c.alive:
                game.say(f"<magic>The shape slips from {_first(c)}</>: {_first(c)} is themselves again.", "magic")
