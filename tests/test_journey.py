"""Journeys that look after you (after v1): the travel command stops for the night and for what is wrong with
the body, says where the nearest roof or water is, can be taken up again, and warns before a long walk; sleep is
broken by the cold rather than slept through to the end."""

import copy
from types import SimpleNamespace

import pytest

from realmwalker.game import fight, journey
from realmwalker.game.state import GameState, new_game
from realmwalker.rules import body
from realmwalker.rules.body import Environment
from realmwalker.rules.character import Sheet
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Roadland", 5, "medium"), tables).generate()


@pytest.fixture
def game(tables, world, monkeypatch):
    monkeypatch.setattr("realmwalker.game.encounters.encounter_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.events.event_chance", lambda *a: 0.0)
    monkeypatch.setattr(GameState, "lost_dc", lambda self: None)
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    return g


def at_hour(game, hour: int) -> None:
    m = game.moment
    game.world.time = (m.total_days + 1) * 1440 + hour * 60


def far_town(game, lo=10, hi=30):
    p = game.player
    towns = [s for s in game.world.settlements if lo <= max(abs(s.x - p.x), abs(s.y - p.y)) <= hi]
    towns = [s for s in towns if game.plan_travel((s.x, s.y)) is not None]
    assert towns, "a town a long day's walk away"
    return min(towns, key=lambda s: abs(s.x - p.x) + abs(s.y - p.y))


def walk(game, limit=200) -> int:
    steps = 0
    while game.travel is not None and steps < limit:
        game.travel_step()
        steps += 1
    return steps


def last(game) -> str:
    return game.log.messages[-1].text


def test_a_journey_stops_when_night_comes_on_and_goes_on_after(game):
    at_hour(game, 14)
    dest = far_town(game)
    game.set_out(game.plan_travel((dest.x, dest.y)))
    walk(game)
    assert (game.player.x, game.player.y) != (dest.x, dest.y), "a long walk does not end the same day"
    assert "You stop." in last(game) and "Night is coming on" in last(game)
    assert game.light < journey.NIGHT_LIGHT
    assert game.journey_to == (dest.x, dest.y), "the journey remembers where it was going"
    # Choosing to walk on through the dark is allowed, and the dark does not stop you twice.
    x, y = game.player.x, game.player.y
    game.set_out(game.plan_travel((dest.x, dest.y)))
    game.travel_step()
    assert (game.player.x, game.player.y) != (x, y)
    assert "Night is coming on" not in last(game)


def test_setting_out_in_the_dark_is_not_stopped_for_the_dark(game):
    at_hour(game, 23)
    dest = far_town(game)
    game.set_out(game.plan_travel((dest.x, dest.y)))
    game.travel_step()
    assert game.travel is not None, "you knew it was night when you set out"


def test_the_body_stops_a_journey_once_for_each_new_trouble(game):
    at_hour(game, 7)
    dest = far_town(game)
    game.set_out(game.plan_travel((dest.x, dest.y)))
    game.travel_step()
    assert game.travel is not None
    game.leader.fatigue = 75.0  # weary
    game.travel_step()
    assert game.travel is None and "weary" in last(game)
    game.set_out(game.plan_travel((dest.x, dest.y)))
    game.travel_step()
    assert game.travel is not None, "being told once is enough"
    game.leader.body_heat = -65.0  # and now the cold is dangerous
    game.travel_step()
    assert game.travel is None and "hypothermic" in last(game)


def test_a_dry_skin_stops_the_journey_and_says_where_water_is(game):
    at_hour(game, 7)
    dest = far_town(game)
    game.set_out(game.plan_travel((dest.x, dest.y)))
    game.travel_step()
    p = game.player
    for it in game.leader.inventory:
        it.fill = 0.0
    game.player.explored[:] = True
    game.travel_step()
    assert game.travel is None and "The last of the water is gone" in last(game)
    w = game.world
    near = any(w.river[x, y] or w.settlement_at(x, y) for x in range(p.x - 4, p.x + 5) for y in range(p.y - 4, p.y + 5)
               if w.in_bounds(x, y) and (x, y) != (p.x, p.y))
    assert ("There is water" in last(game)) == near


def test_a_town_close_by_is_offered_as_a_roof_for_the_night(game):
    at_hour(game, 14)
    town = next(s for s in game.world.settlements if s.id in game.player.known_settlements)
    game.player.x, game.player.y = town.x + 1, town.y
    game.player.known_settlements.add(town.id)
    assert "a roof for the night" in (journey.nearest_roof(game) or "")


def test_t_and_enter_take_up_a_stopped_journey(make_app, world, monkeypatch):
    """The world map opens on where the journey was going, and the plan says what the road will ask of you."""
    import tcod.console

    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.base import ConfirmBox
    from realmwalker.ui.screens.world_map import WorldMapScreen

    monkeypatch.setattr("realmwalker.game.encounters.encounter_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.events.event_chance", lambda *a: 0.0)
    monkeypatch.setattr(GameState, "lost_dc", lambda self: None)
    app = make_app()
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    app.start_game(game)
    gs = app.top
    at_hour(game, 14)
    dest = far_town(game)
    game.set_out(game.plan_travel((dest.x, dest.y)))
    walk(game)
    assert game.travel is None and game.journey_to == (dest.x, dest.y)
    app.handle_event(KeyEvent("t"))
    assert isinstance(app.top, WorldMapScreen) and app.top.cursor == (dest.x, dest.y)
    app.handle_event(KeyEvent("enter"))
    assert isinstance(app.top, ConfirmBox)
    con = tcod.console.Console(120, 45, order="F")
    app.render(con)
    shown = "\n".join("".join(chr(c) for c in con.rgb["ch"][:, y]) for y in range(con.height))
    assert "in the open" in shown or "before dark" in shown
    app.handle_event(KeyEvent("y"))
    assert app.top is gs and game.travel is not None
    assert app.error_count == 0


def test_too_exhausted_to_walk_is_not_called_too_heavy(game):
    game.leader.exhaustion = 5
    assert game.pace() is None
    game.move(1, 0)
    text = last(game)
    assert "too far gone" in text and "carrying" not in text


def test_the_plan_warns_of_hunger_and_of_nights_in_the_open(game):
    at_hour(game, 14)
    for it in list(game.leader.inventory):
        if game.tables.items.get(it.def_id).get("food"):
            game.leader.inventory.remove(it)
    far = max(game.world.settlements, key=lambda s: abs(s.x - game.player.x) + abs(s.y - game.player.y)
              if game.plan_travel((s.x, s.y)) is not None else -1)
    plan = game.plan_travel((far.x, far.y))
    lines = journey.outlook(game, plan)
    assert journey.nights(game, plan) >= 1
    assert any("in the open" in line for line in lines)
    assert any("<danger>Food for" in line for line in lines), lines


def test_sleep_in_the_bitter_cold_is_broken_before_it_kills(tables):
    from tools import balance
    from realmwalker.rules.inventory import remove_item

    world = WorldGenerator(WorldOptions("Coldland", 7, "small"), tables).generate()
    spot = balance.wild_spot(world, tables)
    winter = next(day for day in range(tables.calendar.days_per_year)
                  if tables.calendar.at(day * 1440).season == "winter")
    broken = 0
    for seed in range(4):
        game = new_game(copy.deepcopy(world), tables)
        game.player.x, game.player.y = spot
        c = game.leader
        for it in list(c.inventory):
            if tables.items.get(it.def_id)["category"] == "clothing":
                remove_item(c, it.uid)
        game.world.time = (winter + 20) * 1440 + 21 * 60 + seed
        t0 = game.world.time
        notes = fight.rest(game, "long")
        if any("The cold wakes you" in n for n in notes):
            broken += 1
            assert game.world.time - t0 < 8 * 60, "the rest ends when you wake"
            assert game.over is None, "you wake before you die"
    assert broken == 4


def test_a_fire_dries_you_in_a_drizzle(tables):
    from realmwalker.rules.creation import CharacterBuilder
    from realmwalker.core.rng import RNG

    b = CharacterBuilder(tables, RNG(1, "wet"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background("soldier")
    for fire, drier in ((True, True), (False, False)):
        c = b.build()
        c.wet = 80.0
        env = Environment(air=6.0, wind=10.0, wet_per_hour=30.0, activity="rest", fire=fire)
        body.tick(c, Sheet(c, tables), env, 60)
        assert (c.wet < 80.0) == drier, (fire, c.wet)


def test_too_exhausted_to_take_a_step_in_town_is_not_called_too_heavy(game):
    town = game.world.settlements[0]
    game.player.x, game.player.y = town.x, town.y
    game.player.local_key = None
    game.enter_local()
    game.leader.exhaustion = 5
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        game.move(dx, dy)
    assert any("too far gone" in m.text for m in game.log.messages[-4:])
    assert not any("carrying too much" in m.text for m in game.log.messages[-4:])
