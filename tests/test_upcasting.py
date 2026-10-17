"""Casting with a higher slot (Expansion 3 C.2, PHB 2024): what a higher slot adds comes from the spell's ops (up,
count_up, rays_up, targets_up); the battle screen asks which slot when there is a choice; the Auto and the enemy
spend a spare higher slot (one with no spell of its own level ready) where it does more; the card says what it adds."""

import copy

import pytest
import tcod.console

from realmwalker.core.rng import RNG
from realmwalker.rules import describe
from realmwalker.rules import spells as sp
from realmwalker.rules.combat import FOE, PARTY, Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.progression import award_xp
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402

XP = {3: 900, 5: 6500}


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def hero(tables, cls, level=1, seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("sage")
    c = b.build()
    if level > 1:
        award_xp(c, XP[level], tables, RNG(2), auto=True)
    return c


def to_turn(b):
    while b.pending_party() is None and b.outcome is None:
        b.step()
    return b.pending_party()


def test_what_a_higher_slot_adds(tables):
    s = tables.spells
    assert sp.up_gain(s["fireball"], 2) == ["+2d6 fire"]
    assert sp.up_gain(s["magic_missile"], 1) == ["+1 dart"]
    assert sp.up_gain(s["cure_wounds"], 1) == ["heals +2d8"]
    assert sp.up_gain(s["hold_person"], 2) == ["+2 targets"]
    assert sp.scaled("8d6", "1d6", 2) == "10d6" and sp.scaled("3d8", "1d6", 1) == "3d8+1d6"
    assert not sp.upcasts(s["shield"]) and not sp.upcasts(s["misty_step"]) and sp.upcasts(s["scorching_ray"])
    card = describe.spell(tables, "fireball", level=5)
    assert "cast at level 5" in card.subtitle and any("+2d6 fire" in line for line in card.lines)
    assert any("A higher slot" in line for line in describe.spell(tables, "guiding_bolt").lines)


def test_a_higher_slot_in_a_real_fight(tables):
    c = hero(tables, "cleric", 5)
    c.spells["prepared"] = ["guiding_bolt", "healing_word", "command", "hold_person"]
    b = Battle(tables, [c], [spawn(tables, "ogre", RNG(1), 1)], Env(), RNG(1, "battle"))
    b.start("Test fight.")
    f = to_turn(b)
    ogre = b.side(FOE)[0]
    assert sp.slot_choices(c, tables, "guiding_bolt") == [1, 2, 3]
    hp = ogre.hp
    assert b.do_cast(f, "guiding_bolt", ogre, slot_level=3)
    assert c.spells["slots_used"][:3] == [0, 0, 1]
    cast = [e for e in b.events if e.get("kind") == "cast" or e.get("type") == "cast"]
    assert cast and ogre.hp <= hp
    # A level with no slot left is refused, and nothing is spent.
    c.spells["slots_used"][1] = 3
    b.end_turn()
    f = to_turn(b)
    if f is not None:
        used = list(c.spells["slots_used"])
        assert not b.do_cast(f, "guiding_bolt", ogre, slot_level=2) and c.spells["slots_used"] == used


def test_the_auto_spends_a_spare_slot_where_it_does_more(tables):
    w = hero(tables, "wizard", 3)
    w.spells["prepared"] = ["magic_missile", "shield", "burning_hands", "mage_armor"]
    assert 2 in sp.idle_levels(w, tables)
    assert sp.auto_slot(w, tables, "magic_missile") == 2
    assert sp.auto_slot(w, tables, "shield") == 1  # (no more from a higher slot)
    if "web" in w.spells["spellbook"]:
        w.spells["prepared"] = ["magic_missile", "shield", "burning_hands", "web"]
        assert sp.auto_slot(w, tables, "magic_missile") == 1  # (the level 2 slot is wanted for Web)
    # In a fight, on Auto: four darts from the spare slot.
    w.spells["prepared"] = ["magic_missile", "shield", "burning_hands", "mage_armor"]
    b = Battle(tables, [w], [spawn(tables, "ogre", RNG(1), 1)], Env(), RNG(1, "battle"))
    b.start("Test fight.")
    from realmwalker.rules import tactics

    f = to_turn(b)
    f.auto = True
    tactics.take_turn(b, f)
    assert w.spells["slots_used"][1] == 1, b.log[-8:]


def test_an_enemy_caster_casts_higher_with_a_spare_slot(tables):
    # (The 2025 stat blocks cast so many times a day; a caster with slots comes with Part G. A cult fanatic given
    # slots stands in for one.)
    b = Battle(tables, [hero(tables, "fighter")], [spawn(tables, "cult_fanatic", RNG(5), 1)], Env(), RNG(1, "battle"))
    b.start("Test fight.")
    f, target = b.side(FOE)[0], b.side(PARTY)[0]
    f.cdef = copy.deepcopy(f.cdef)
    f.cdef["spellcasting"].update({"per_day": {}, "shared": {}, "at_will": []})
    f.slots = [2, 2]
    f.action = 1
    f.cast_action_spell = False
    assert b.creature_cast(f, "command", target, slot_level=2)
    assert f.slots == [2, 1]
    from realmwalker.rules import tactics

    command = tables.spells["command"]
    assert tactics._slot_levels(b, f, "command", command) == [1]  # (its level 2 slots are for Hold Person)
    f.cdef["spells"] = ["light", "command"]
    assert tactics._slot_levels(b, f, "command", command) == [1, 2]  # (now a spare one: two creatures commanded)


def test_the_battle_screen_asks_which_slot(make_app):
    from realmwalker.game.state import new_game
    from realmwalker.ui.screens.battle import BattleScreen
    from realmwalker.world.generator import WorldOptions

    app = make_app()
    t = app.tables
    wiz = hero(t, "wizard", 3)
    wiz.spells["prepared"] = ["magic_missile", "shield", "burning_hands", "mage_armor"]
    g = new_game(copy.deepcopy(cached_world(WorldOptions("Slotland", 7, "small"), t)), t, wiz)
    g.survival = False
    app.start_game(g)
    b = Battle(t, [wiz], [spawn(t, "ogre", RNG(1), 1)], Env(), RNG(1, "battle"))
    b.start("Test fight.")
    g.battle = b
    to_turn(b)
    screen = BattleScreen(app, g)
    app.push(screen)
    app.render(tcod.console.Console(160, 45, order="F"))
    screen.pick_action("cast")
    assert screen.mode == "choose" and screen.choice_kind == "cast"
    screen.choice_index = next(i for i, r in enumerate(screen.choices) if r[1] == "magic_missile")
    screen.confirm_choice()
    assert screen.choice_kind == "slot" and [r[1] for r in screen.choices] == [1, 2]
    assert "+1 dart" in screen.choices[1][0]
    app.render(tcod.console.Console(160, 45, order="F"))
    screen.choice_index = 1
    screen.confirm_choice()
    assert screen.mode == "target"
    screen.confirm_target()
    assert wiz.spells["slots_used"][:2] == [0, 1]
    app.render(tcod.console.Console(160, 45, order="F"))
    assert app.error_count == 0


def test_a_higher_slot_on_the_road_and_on_the_spells_page(make_app):
    from realmwalker.game import magic
    from realmwalker.game.state import new_game
    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.spells import SpellsScreen
    from realmwalker.world.generator import WorldOptions

    app = make_app()
    t = app.tables
    c = hero(t, "cleric", 3)
    c.spells["prepared"] = ["cure_wounds", "healing_word", "command", "hold_person"]
    g = new_game(copy.deepcopy(cached_world(WorldOptions("Slotland", 7, "small"), t)), t, c)
    g.survival = False
    app.start_game(g)
    screen = SpellsScreen(app, g)
    app.push(screen)
    screen.sel = screen.spells().index("cure_wounds")
    c.hp = 1
    app.handle_event(KeyEvent("l"))
    assert screen.slot == 2
    app.render(tcod.console.Console(160, 45, order="F"))
    assert "Slot: level 2" in app.last_canvas.words()
    app.handle_event(KeyEvent("enter"))
    assert c.spells["slots_used"][:2] == [0, 1] and c.hp > 1
    # A spell that gains nothing from a higher slot is cast with the lowest, whatever was asked.
    c.spells["prepared"] = ["cure_wounds", "healing_word", "command", "shield_of_faith"]
    assert not sp.upcasts(t.spells["shield_of_faith"])
    assert magic.road_problem(g, c, "shield_of_faith") is None
    magic.cast_on_road(g, c, "shield_of_faith", c, 2)
    assert c.spells["slots_used"][:2] == [1, 1]
    assert app.error_count == 0
