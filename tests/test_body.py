"""The body (after v1): each need says where it is heading (design section 4: "each with its stage and trend"), and
a limb that cannot be saved can be taken off to save a life (design section 7)."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import care
from realmwalker.game.state import new_game
from realmwalker.rules import body, health
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.inventory import add_item, equip
from realmwalker.rules.wounds import Wound
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Flesh", 23, "small"), tables)


@pytest.fixture
def game(world, tables):
    return new_game(copy.deepcopy(world), tables, CharacterBuilder(tables, RNG(2, "hero")).build())


# ---------------------------------------------------------------------------- trends
@pytest.mark.parametrize("kind, value, rate, words", [
    ("hunger", 20, 2.0, "peckish in 5 hours"),
    ("hunger", 29.5, 2.0, "peckish within the hour"),
    ("thirst", 90, 2.0, "worsening"),
    ("fatigue", 60, -13.0, "easing"),
    ("hunger", 10, 0.01, ""),
    ("hunger", 0, 0.5, ""),  # peckish more than a day and a half off: nothing to say yet
    ("body_heat", -45, 6.0, "warming"),
    ("body_heat", -45, -3.0, "getting colder"),
    ("body_heat", 40, -5.0, "cooling"),
    ("body_heat", 0, 0.5, ""),
    ("wet", 60, -10.0, "drying"),
    ("wet", 20, 8.0, "getting wetter"),
    ("hunger", 20, None, ""),
])
def test_trend_words(kind, value, rate, words):
    assert body.trend_words(kind, value, rate) == words


def test_time_passing_leaves_a_trend_that_eating_does_not_hide(game):
    c = game.leader
    c.hunger, c.wet, c.body_heat = 50.0, 60.0, -30.0
    game.pass_time(30, "walk")
    rates = body.trend(c)
    assert set(rates) == set(body.TREND_KINDS)
    assert rates["hunger"] > 0  # even if the pack fed them after
    assert rates["fatigue"] > 0


def test_the_health_screen_shows_trends(make_app, world, tables):
    import tcod.console

    from realmwalker.ui.screens.health import HealthScreen

    app = make_app()
    game = new_game(copy.deepcopy(world), app.tables, CharacterBuilder(app.tables, RNG(2, "hero")).build())
    app.start_game(game)
    c = game.leader
    c.hunger, c.wet = 25.0, 50.0
    game.pass_time(30, "walk")
    app.push(HealthScreen(app, game))
    con = tcod.console.Console(160, 45, order="F")
    app.render(con)
    text = "\n".join("".join(chr(ch) for ch in con.rgb["ch"][:, y]) for y in range(con.height))
    assert "peckish" in text and "drying" in text
    assert app.error_count == 0


# ---------------------------------------------------------------------------- amputation
def festering(part="left_leg", infection=55.0):
    return Wound(part, "cut", 2, 0, 0, infection=infection, infected=True)


def test_amputation_is_offered_only_for_a_limb_that_cannot_be_saved(game, tables):
    c = game.leader
    add_item(c, tables.items, "knife")
    for w, offered in ((festering(), True), (festering(infection=10.0), False), (festering("torso"), False),
                       (Wound("right_arm", "fracture", 3, 0, 0), True), (Wound("right_arm", "cut", 3, 2, 0), False)):
        ids = [a for a, *_ in health.treatment_options(c, c, w, tables, fire=False, wooded=False)]
        assert ("amputate" in ids) == offered, w


def test_it_needs_a_blade(game, tables):
    c = game.leader
    c.inventory = [it for it in c.inventory if tables.items.get(it.def_id).get("damage_type") != "slashing"]
    w = festering()
    opts = {a: (ok, why) for a, _, ok, why in health.treatment_options(c, c, w, tables, fire=False, wooded=False)}
    assert opts["amputate"] == (False, "no blade to do it with (a knife, an axe, a sword)")


def test_taking_off_a_festering_leg_saves_a_life(game, tables):
    c = game.leader
    healer = CharacterBuilder(tables, RNG(9, "healer")).build()
    healer.is_player = False
    healer.skills.append("medicine")
    game.party.append(healer)
    add_item(healer, tables.items, "knife")
    add_item(healer, tables.items, "torch")
    w = festering("left_leg", 65.0)
    c.wounds.append(w)
    c.wounds.append(Wound("left_leg", "blunt", 1, 0, 0))
    msgs = care.treat(game, c, w, "amputate")
    assert "lost_left_leg" in c.injuries
    assert all(x.infection < 20 for x in c.wounds)  # the poison went with the leg
    assert [x.note for x in c.wounds if x.part == "left_leg"] == ["the stump", "cautery"]  # sealed with the torch
    assert any("left leg is gone" in m for m in msgs)
    assert health.travel_multiplier(c, tables) >= 1.6
    game.pass_time(24 * 60, "rest")
    assert not any(d["id"] == "wound_fever" for d in c.diseases) and c.alive


def test_a_one_armed_fighter_holds_one_thing(game, tables):
    c = game.leader
    c.injuries.append("lost_left_arm")
    shield = add_item(c, tables.items, "shield")
    ok, msg = equip(c, tables.items, shield.uid, "off_hand")
    assert not ok and "one hand" in msg
    axe = add_item(c, tables.items, "greataxe")
    ok, msg = equip(c, tables.items, axe.uid)
    assert not ok and "two hands" in msg
    sword = add_item(c, tables.items, "longsword")
    ok, _ = equip(c, tables.items, sword.uid, "main_hand")
    assert ok


def test_the_confirmation_comes_first(make_app, world):
    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.base import ConfirmBox
    from realmwalker.ui.screens.health import HealthScreen

    app = make_app()
    game = new_game(copy.deepcopy(world), app.tables, CharacterBuilder(app.tables, RNG(2, "hero")).build())
    app.start_game(game)
    c = game.leader
    add_item(c, app.tables.items, "knife")
    c.wounds.append(festering())
    app.push(HealthScreen(app, game))
    app.handle_event(KeyEvent("a"))
    assert isinstance(app.top, ConfirmBox)
    assert "lost_left_leg" not in c.injuries
    app.handle_event(KeyEvent("y"))
    assert "lost_left_leg" in c.injuries
    assert app.error_count == 0
