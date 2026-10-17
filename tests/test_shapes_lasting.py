"""Shapes that outlast a fight (Expansion 3 F.8): Animal Shapes on the willing (never a caster, never the one who
casts it), Large or smaller beasts of Challenge Rating 4 at most, left with a Bonus Action, changed again by the
caster's Magic action, held by no concentration; a lasting shape kept with its borrowed hit points when the fight ends
and brought into the next one, ended at its hour; Shapechange keeping its wearer's mind and spells (a slot spent in the
form is the character's), shifting into another form, ending with its concentration; on the road the forms on the
Spells page, the whole party shaped, the pace, wings over the water, no spells and no gear in a beast, the picture."""

import copy

import pytest

from realmwalker.game import fight as game_fight
from realmwalker.game import gear, magic, shapeshift
from realmwalker.game.state import new_game
from realmwalker.rules import shapes, tactics
from realmwalker.rules import spells as sp
from realmwalker.rules.combat import PARTY
from realmwalker.rules.engine import actions, check, estimates
from realmwalker.rules.inventory import add_item
from realmwalker.world.generator import WorldOptions
from tests.test_servants import battle, hero
from tests.test_wave4 import cast, my_turn
from tests.worlds import cached_world

SPELLS = ("animal_shapes", "shapechange")


@pytest.fixture(scope="module")
def tables(data):
    from realmwalker.world.tables import Tables

    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Lastrites", 37, "small"), tables)


@pytest.fixture(autouse=True)
def casters_know_them(monkeypatch):
    real = sp.known_spells

    def known(char, tables):
        out = real(char, tables)
        return list(dict.fromkeys(out + list(SPELLS) + ["fire_bolt", "magic_missile"])) \
            if sp.is_caster(char, tables) else out

    monkeypatch.setattr(sp, "known_spells", known)


def game_with(world, tables, *party):
    game = new_game(copy.deepcopy(world), tables, party[0])
    for c in party[1:]:
        game.party.append(c)
    game.survival = False
    return game


def wild(game):
    game.leave_local() if game.local is not None else None
    for x in range(game.world.width):
        for y in range(game.world.height):
            if game.world.settlement_at(x, y) is None and game.biome_def(x, y)["passable"] \
                    and any(game.world.in_bounds(x + dx, y) and game.biome_key(x + dx, y) in ("lake", "ocean")
                            for dx in (1, -1)):
                game.player.x, game.player.y = x, y
                return next((x + dx, y) for dx in (1, -1) if game.biome_key(x + dx, y) in ("lake", "ocean"))
    raise AssertionError("no shore")


# ---------------------------------------------------------------------------- the data
def test_the_spells_their_forms_and_the_circlet(tables):
    a, s = tables.spells["animal_shapes"], tables.spells["shapechange"]
    assert (a["level"], a["range"], a["rounds"], a.get("concentration")) == (8, 30, 14400, None)
    assert (s["level"], s["rounds"], s["concentration"]) == (9, 600, True)
    assert sp.road_use(tables, "animal_shapes") == sp.road_use(tables, "shapechange") == "shape"
    assert s["material"]["items"] == ["jade_circlet"] and not s["material"]["consumed"]
    assert tables.items.get("jade_circlet")["value"] == 150000 and "scroll_animal_shapes" in tables.items
    assert not check.problems(tables)
    o = sp.op(a, "shape")
    beasts = shapes.forms(tables, o["forms"], 4, **shapes.limits(o))
    assert beasts and "elephant" not in beasts  # (Huge)
    for cid in beasts:
        d = tables.creatures[cid]
        assert d["kind"] == "beast" and float(d["cr"]) <= 4 and d["size"] in ("tiny", "small", "medium", "large")
    any_form = shapes.forms(tables, "any", 20, **shapes.limits(sp.op(s, "shape")))
    assert not [c for c in any_form if tables.creatures[c]["kind"] in ("construct", "undead")]
    assert "troll" in any_form


# ---------------------------------------------------------------------------- Animal Shapes in a fight
def test_animal_shapes_takes_the_willing_who_cast_no_spells(tables):
    me, fighter, priest = hero(tables), hero(tables, "fighter", xp=0, seed=2), hero(tables, "cleric", xp=0, seed=3)
    b = battle(tables, [me, fighter, priest], ["ogre"], {0: (2, 4), 1: (3, 5), 2: (3, 3), 3: (9, 4)})
    f_me, f_fighter, f_priest = b.fighters[0], b.fighters[1], b.fighters[2]
    my_turn(b, f_me)
    cast(b, f_me, "animal_shapes", level=8)
    assert f_me.shape is None and f_priest.shape is None  # (never the caster; a cleric would lose its spells)
    assert f_fighter.shape is not None and f_fighter.char is None
    form = tables.creatures[f_fighter.creature.def_id]
    assert form["kind"] == "beast" and float(form["cr"]) <= 4 and form["size"] in ("tiny", "small", "medium", "large")
    assert f_fighter.score("int") == fighter.abilities["int"]  # (its mind is its own)
    assert f_me.concentration is None  # (no concentration: a day)
    rec = shapes.record(fighter)
    assert rec["spell"] == "animal_shapes" and rec["caster"] == me.name and rec["until"] == b.now + 24 * 60


def test_a_beast_leaves_its_shape_with_a_bonus_action_and_the_druid_changes_them_again(tables):
    me, fighter, other = hero(tables), hero(tables, "fighter", xp=0, seed=2), hero(tables, "rogue", xp=0, seed=4)
    b = battle(tables, [me, fighter, other], ["ogre"], {0: (2, 4), 1: (3, 5), 2: (3, 3), 3: (9, 4)})
    f_me, f_fighter, f_other = b.fighters[0], b.fighters[1], b.fighters[2]
    my_turn(b, f_me)
    cast(b, f_me, "animal_shapes", level=8)
    assert f_fighter.shape is not None and f_other.shape is not None
    full = shapes.form_hp(tables, f_fighter.creature.def_id)
    b._apply_hp_loss(f_fighter, full - 2, source=None, cause="test")
    assert f_fighter.shape is not None and f_fighter.temp_hp == 2
    f_me.action = 1
    assert ("reshape", True) in [(a, ok) for a, _, ok, _ in b.class_abilities(f_me)]
    b.do_ability(f_me, "reshape")
    assert f_fighter.shape is not None and f_fighter.temp_hp == full and f_me.action == 0
    my_turn(b, f_other)
    opts = {o.id: o for o in actions.options(b, f_other)}
    assert opts["ability:leave_shape"].cost == "bonus" and opts["ability:leave_shape"].available
    b.do_ability(f_other, "leave_shape")
    assert f_other.shape is None and f_other.char is other and f_other.bonus == 0
    assert shapes.record(other) is None  # (the shape is gone for good)


def test_another_spell_let_go_does_not_end_animal_shapes(tables):
    me, fighter = hero(tables), hero(tables, "fighter", xp=0, seed=2)
    b = battle(tables, [me, fighter], ["ogre"], {0: (2, 4), 1: (3, 5), 2: (9, 4)})
    f_me, f_fighter = b.fighters[0], b.fighters[1]
    my_turn(b, f_me)
    cast(b, f_me, "animal_shapes", level=8)
    f_me.concentration = {"spell": "bless", "rounds": 10, "on": []}
    b._end_concentration(f_me, quiet=True)
    assert f_fighter.shape is not None


def test_the_shape_outlasts_the_fight_and_comes_into_the_next(tables):
    me, fighter = hero(tables), hero(tables, "fighter", xp=0, seed=2)
    b = battle(tables, [me, fighter], ["bandit"], {0: (2, 4), 1: (3, 5), 2: (9, 4)})
    f_me, f_fighter = b.fighters[0], b.fighters[1]
    my_turn(b, f_me)
    cast(b, f_me, "animal_shapes", level=8)
    form = f_fighter.creature.def_id
    b._apply_hp_loss(f_fighter, 3, source=None, cause="test")
    left = f_fighter.temp_hp
    b.result()
    assert f_fighter.char is fighter and shapes.record(fighter)["temp"] == left
    assert shapes.record(fighter)["form"] == form
    b2 = battle(tables, [me, fighter], ["bandit"], {0: (2, 4), 1: (3, 5), 2: (9, 4)})
    shaped = b2.bring_shapes()
    g = b2.fighters[1]
    assert shaped == [g] and g.creature.def_id == form and g.temp_hp == left and g.hp == fighter.hp
    b2._apply_hp_loss(g, left + 1, source=None, cause="test")
    assert g.shape is None and shapes.record(fighter) is None  # (its borrowed hit points gone: the spell is over)


# ---------------------------------------------------------------------------- Shapechange
def test_shapechange_keeps_the_mind_and_casts_in_the_form(tables):
    me = hero(tables)
    b = battle(tables, [me], ["ogre", "ogre"], {0: (2, 4), 1: (9, 4), 2: (9, 6)})
    f = b.fighters[0]
    my_turn(b, f)
    cast(b, f, "shapechange", level=9)
    assert f.shape is not None and f.char is None and f.concentration is not None
    form = tables.creatures[f.creature.def_id]
    assert form["kind"] not in ("construct", "undead") and float(form["cr"]) <= me.level
    from realmwalker.rules.character import Sheet

    assert f.score("int") == me.abilities["int"] and f.cdef["saves"]["int"] >= Sheet(me, tables).save_bonus("int")
    assert "magic_missile" in f.cdef["spells"] and not any(tables.spells[s].get("concentration")
                                                         for s in f.cdef["spells"])
    used = list(me.spells.get("slots_used", [0] * 9))
    my_turn(b, f)
    assert "magic_missile" in b.creature_spells(f)
    assert b.do_cast(f, "magic_missile", b.fighters[1])
    assert f.shape is not None  # (a spell without concentration leaves the shape)
    b._end_concentration(f, quiet=True)
    assert f.shape is None and f.char is me and shapes.record(me) is None
    assert sum(me.spells["slots_used"]) == sum(used) + 1  # (the slot spent in the form is the wizard's)


def test_a_shapechanger_shifts_into_another_form_with_fresh_borrowed_hit_points(tables):
    me = hero(tables)
    b = battle(tables, [me], ["ogre"], {0: (2, 4), 1: (9, 4)})
    f = b.fighters[0]
    my_turn(b, f)
    cast(b, f, "shapechange", level=9)
    first = f.creature.def_id
    b._apply_hp_loss(f, f.temp_hp - 1, source=None, cause="test")
    my_turn(b, f)
    assert ("shift_shape", True) in [(a, ok) for a, _, ok, _ in b.class_abilities(f)]
    b.do_ability(f, "shift_shape")
    assert f.shape is not None and f.creature.def_id != first and f.concentration is not None
    assert f.temp_hp == shapes.form_hp(tables, f.creature.def_id) and f.action == 0
    assert shapes.record(me)["form"] == f.creature.def_id


def test_the_auto_casts_them_and_shifts_when_low(tables):
    me, fighter = hero(tables), hero(tables, "fighter", xp=0, seed=2)
    b = battle(tables, [me, fighter], ["ogre"], {0: (2, 4), 1: (3, 5), 2: (9, 4)})
    f_me = b.fighters[0]
    my_turn(b, f_me)
    assert estimates.spell_value(b, f_me, "animal_shapes").total(care=4.0) > 0.5
    assert estimates.spell_value(b, f_me, "shapechange").total(care=4.0) > 0.5
    veteran = hero(tables, "fighter", seed=5)  # (level 20: a lion would be a loss)
    b2 = battle(tables, [hero(tables), veteran], ["ogre"], {0: (2, 4), 1: (3, 5), 2: (9, 4)})
    my_turn(b2, b2.fighters[0])
    assert estimates.spell_value(b2, b2.fighters[0], "animal_shapes").total(care=4.0) <= 0.0
    me3 = hero(tables)
    b3 = battle(tables, [me3], ["ogre"], {0: (2, 4), 1: (3, 4)})
    f = b3.fighters[0]
    my_turn(b3, f)
    cast(b3, f, "shapechange", level=9)
    first = f.creature.def_id
    b3._apply_hp_loss(f, f.temp_hp - 1, source=None, cause="test")
    my_turn(b3, f)
    f.auto = True
    tactics.take_turn(b3, f)
    assert f.shape is not None and f.creature.def_id != first


# ---------------------------------------------------------------------------- on the road
def test_the_party_takes_a_shape_on_the_road_and_flies_over_the_water(world, tables):
    me, friend = hero(tables), hero(tables, "fighter", xp=0, seed=2)
    game = game_with(world, tables, me, friend)
    lake = wild(game)
    subs = magic.road_targets(game, me, "animal_shapes")
    assert subs and all(s.data.get("form") for s in subs)
    wings = subs[0]
    assert shapes.flies(tables, wings.data["form"])  # (the fliers first)
    assert magic.road_problem(game, me, "animal_shapes", wings) is None
    out = magic.cast_on_road(game, me, "animal_shapes", wings)
    assert "Animal Shapes" in " ".join(out)
    assert shapeshift.form_of(game, me) == shapeshift.form_of(game, friend) == wings.data["form"]
    assert game.magic_crossing(*lake) == "fly" and game.step_minutes(game.player.x, game.player.y, *lake) is not None
    assert game.pace() < 1.0 or shapes.speed(tables, wings.data["form"]) <= 30
    ok, why = sp.can_cast(me, tables, "fire_bolt")
    assert not ok and "beast" in why  # (no spells in a beast's shape)
    tool = add_item(friend, tables.items, "whetstone")
    assert "melded" in " ".join(gear.use_item(game, friend, tool))
    from realmwalker.ui.gfx import dolls

    parts = dolls.character(me, tables)
    assert parts == dolls.creature(wings.data["form"], tables, f"pc{me.name}", sex=me.sex)
    # The Magic action: back to their own shapes, with no slot.
    slots = list(me.spells.get("slots_used", [0] * 9))
    back = next(s for s in magic.road_targets(game, me, "animal_shapes") if s.ref == "leave")
    assert magic.road_problem(game, me, "animal_shapes", back) is None
    magic.cast_on_road(game, me, "animal_shapes", back)
    assert shapeshift.form_of(game, me) is None and shapeshift.form_of(game, friend) is None
    assert me.spells.get("slots_used", [0] * 9) == slots
    assert game.magic_crossing(*lake) is None


def test_the_shape_ends_at_its_hour_and_comes_into_a_fight(world, tables):
    me, friend = hero(tables), hero(tables, "fighter", xp=0, seed=2)
    add_item(me, tables.items, "jade_circlet")
    game = game_with(world, tables, me, friend)
    wild(game)
    form = next(s for s in magic.road_targets(game, me, "shapechange") if not shapes.flies(tables, s.data["form"]))
    out = magic.cast_on_road(game, me, "shapechange", form)
    assert shapeshift.form_of(game, me) == form.data["form"] and shapeshift.form_of(game, friend) is None
    assert sp.can_cast(me, tables, "fire_bolt")[0]  # (Shapechange keeps the spells)
    assert out
    from realmwalker.core.rng import RNG
    from realmwalker.rules.creatures import spawn

    b = game_fight.start_battle(game, [spawn(tables, "bandit", RNG(1, "f"), 1)], "Test fight.")
    f = next(x for x in b.side(PARTY) if x.shape is not None)
    assert f.creature.def_id == form.data["form"] and f.concentration["spell"] == "shapechange"
    b.result()
    game.battle = None
    assert shapes.record(me)["form"] == form.data["form"]  # (still worn after the fight)
    game.pass_time(61, "rest")
    assert shapes.record(me) is None and shapeshift.form_of(game, me) is None
