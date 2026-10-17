"""Shapes in a fight (Expansion 3 F.6): Polymorph turns a foe into the weakest beast (the Wisdom save, the beast's
numbers, back as it was when the borrowed hit points are gone, the rest of the blow on its own), a friend into the
strongest it may be (no save, still the player's, no spells, back when the concentration ends with its own hit
points); True Polymorph into a creature that is not a beast; the fight's end undoes every shape; the Auto casts it."""

import pytest

from realmwalker.rules import shapes, tactics
from realmwalker.rules.combat import FOE, PARTY
from realmwalker.rules.engine import actions, estimates
from tests.test_servants import battle, hero
from tests.test_wave4 import cast, my_turn


@pytest.fixture(scope="module")
def tables(data):
    from realmwalker.world.tables import Tables

    return Tables(data)


def test_the_forms_follow_the_challenge_rating_and_never_a_summoned_thing(tables):
    beasts = shapes.forms(tables, ["beast"], 1.0)
    assert "brown_bear" in beasts and "rat" in beasts and "ogre" not in beasts
    assert all(tables.creatures[c]["kind"] == "beast" and float(tables.creatures[c]["cr"]) <= 1 for c in beasts)
    anything = shapes.forms(tables, "any", 2.0)
    assert "ogre" in anything and "celestial_spirit" not in anything and "otherworldly_steed" not in anything
    assert shapes.strength(tables, "brown_bear") > shapes.strength(tables, "rat")


def test_a_foe_that_fails_its_save_is_the_weakest_beast_until_the_borrowed_hit_points_go(tables):
    b = battle(tables, [hero(tables)], ["ogre"], {0: (2, 4), 1: (6, 4)})
    me, ogre = b.fighters[0], b.fighters[1]
    hp, form = ogre.hp, shapes.worst(tables, ogre, ["beast"])
    my_turn(b, me)
    cast(b, me, "polymorph", ogre, dc=40)
    assert ogre.shape is not None and ogre.cdef["name"] == tables.creatures[form]["name"]
    assert ogre.hp == hp and ogre.temp_hp == shapes.form_hp(tables, form)
    assert ogre.ac() == tables.creatures[form]["ac"] and ogre.side == FOE
    assert ogre.name.startswith("the ogre, as a")
    b._apply_hp_loss(ogre, ogre.temp_hp + 5, source=me, cause="test")
    assert ogre.shape is None and ogre.cdef["name"] == "ogre" and ogre.hp == hp - 5 and ogre.temp_hp == 0


def test_a_foe_that_saves_keeps_its_shape(tables):
    b = battle(tables, [hero(tables)], ["ogre"], {0: (2, 4), 1: (6, 4)})
    me, ogre = b.fighters[0], b.fighters[1]
    my_turn(b, me)
    cast(b, me, "polymorph", ogre, dc=-20)
    assert ogre.shape is None and ogre.cdef["name"] == "ogre"


def test_a_friend_takes_the_strongest_beast_plays_on_and_casts_nothing_until_the_spell_ends(tables):
    wiz, friend = hero(tables), hero(tables, "fighter", seed=2)
    b = battle(tables, [wiz, friend], ["ogre"], {0: (2, 4), 1: (3, 6), 2: (8, 4)})
    me, ally = b.fighters[0], b.fighters[1]
    hp, form = ally.hp, shapes.best(tables, ally, ["beast"])
    my_turn(b, me)
    cast(b, me, "polymorph", ally, dc=40)
    assert ally.shape is not None and ally.char is None and ally.creature.def_id == form
    assert ally.hp == hp and ally.temp_hp >= shapes.form_hp(tables, form) and ally.side == PARTY
    my_turn(b, ally)
    assert b.pending_party() is ally  # (the player still plays it)
    assert not [o for o in actions.options(b, ally) if o.kind == "cast"]
    assert {o.id for o in actions.options(b, ally) if o.kind == "attack"} ==         {f"attack:c{i}" for i in range(len(tables.creatures[form]["attacks"]))}  # (the beast's own blows)
    b._end_concentration(me, quiet=False)
    assert ally.shape is None and ally.char is friend and friend.hp == hp


def test_true_polymorph_reaches_past_the_beasts(tables):
    wiz = hero(tables)
    b = battle(tables, [wiz], ["bandit"], {0: (2, 4), 1: (8, 4)})
    me = b.fighters[0]
    my_turn(b, me)
    cast(b, me, "true_polymorph", me, dc=40, level=9)
    assert me.shape is not None and tables.creatures[me.creature.def_id]["kind"] != "beast"
    assert float(tables.creatures[me.creature.def_id]["cr"]) <= wiz.level
    assert me.concentration is not None  # (it holds its own spell, though it casts nothing more)


def test_the_end_of_the_fight_undoes_every_shape(tables):
    wiz = hero(tables)
    b = battle(tables, [wiz], ["bandit", "bandit"], {0: (2, 4), 1: (8, 4), 2: (9, 6)})
    me, foe = b.fighters[0], b.fighters[1]
    my_turn(b, me)
    cast(b, me, "polymorph", foe, dc=40)
    assert foe.shape is not None
    b.result()
    assert foe.shape is None and foe.cdef["name"] == "bandit"
    b.fighters[2].creature.hp = 0
    b.fighters[2].state = "dead"
    cast(b, me, "polymorph", foe, dc=40)
    b._kill(foe, "test")
    assert foe.shape is None and foe.state == "dead" and not foe.creature.alive


def test_the_auto_turns_a_strong_foe_into_something_harmless(tables, monkeypatch):
    from realmwalker.rules import spells as sp

    monkeypatch.setattr(sp, "known_spells", lambda char, t: ["polymorph"])
    wiz = hero(tables)
    b = battle(tables, [wiz], ["ogre"], {0: (2, 4), 1: (5, 4)})
    me, ogre = b.fighters[0], b.fighters[1]
    my_turn(b, me)
    worth = estimates.spell_value(b, me, "polymorph", target=ogre).total(care=4.0)
    assert worth > estimates.spell_value(b, me, "polymorph", target=me).total(care=4.0)
    assert worth > 0.5
    me.auto = True
    tactics.take_turn(b, me)
    assert any(e.get("kind") == "cast" and e.get("spell") == "polymorph" for e in b.events)
