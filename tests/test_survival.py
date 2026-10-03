"""Survival: weather, needs, body heat, wetness, exhaustion, food and water."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import save, survival
from realmwalker.game.state import new_game
from realmwalker.rules import body
from realmwalker.rules.body import Environment
from realmwalker.rules.character import Sheet
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.inventory import add_item, container_capacity
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables
from realmwalker.world.weather import describe, season_offset, weather_at, weather_grid


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Weatherland", 31, "small"), tables).generate()


def hero(tables, seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background("soldier")
    return b.build()


def live(char, tables, env, hours):
    s = Sheet(char, tables)
    for _ in range(hours):
        body.tick(char, s, env, 60)
    return char


# ---------------------------------------------------------------------------- weather
def test_weather_is_deterministic_and_sane(world, tables):
    x, y = world.settlements[0].x, world.settlements[0].y
    kinds = set()
    for minute in range(0, 60 * 24 * 360, 60 * 37):
        a = weather_at(world, tables, x, y, minute)
        assert a == weather_at(world, tables, x, y, minute)
        assert -60 < a.temp < 60 and 0 <= a.wind < 150 and 0 <= a.precip <= 1 and 0 < a.visibility <= 1
        if a.snowing:
            assert a.temp <= 0.5
        kinds.add(a.kind)
        assert describe(a).endswith(".")
    assert len(kinds) >= 4, kinds


def test_seasons_are_smooth_and_follow_the_calendar(tables):
    cal = tables.calendar
    day = 24 * 60
    values = [season_offset(cal, d * day) for d in range(cal.days_per_year)]
    assert min(values) < -5 < 5 < max(values)
    assert all(abs(a - b) < 1.0 for a, b in zip(values, values[1:]))


def test_weather_grid_matches_the_map(world, tables):
    precip, temp, cloud = weather_grid(world, tables, 12345)
    assert precip.shape == temp.shape == (world.width, world.height)
    assert 0 <= precip.min() and precip.max() <= 1


def test_fronts_move(world, tables):
    x, y = world.width // 2, world.height // 2
    seen = {weather_at(world, tables, x, y, m * 60).kind for m in range(0, 24 * 20, 3)}
    assert len(seen) >= 3, "twenty days of weather in one place should change"


# ---------------------------------------------------------------------------- the body
def test_needs_grow_and_sleep_restores(tables):
    c = hero(tables)
    live(c, tables, Environment(15, 5, 0, "walk"), 10)
    assert c.hunger > 10 and c.thirst > 20 and c.fatigue > 20
    tired = c.fatigue
    live(c, tables, Environment(15, 5, 0, "sleep", bedding=3), 8)
    assert c.fatigue < tired / 4


def test_a_winter_night_outside_is_dangerous_and_a_fire_saves_you(tables):
    cold = live(hero(tables), tables, Environment(-8, 15, 0, "sleep", bedding=3), 8)
    assert body.heat_index(cold.body_heat) <= -2, "cold and shivering by morning"
    longer = live(hero(tables), tables, Environment(-8, 15, 0, "sleep", bedding=3), 12)
    assert body.heat_index(longer.body_heat) <= -3, "and hypothermic if it goes on"
    warm = live(hero(tables), tables, Environment(-8, 15, 0, "sleep", fire=True, bedding=3), 8)
    assert body.heat_index(warm.body_heat) == 0
    inn = live(hero(tables), tables, Environment(-8, 15, 0, "sleep", sheltered=True, bedding=3), 8)
    assert body.heat_index(inn.body_heat) == 0


def test_rain_soaks_and_a_fire_dries(tables):
    c = live(hero(tables), tables, Environment(8, 10, 60, "walk"), 3)
    assert c.wet > 50
    live(c, tables, Environment(8, 10, 0, "rest", fire=True), 3)
    assert c.wet == 0


def test_heat_waves_are_dangerous_to_walk_in(tables):
    c = live(hero(tables), tables, Environment(35, 5, 0, "walk"), 8)
    assert body.heat_index(c.body_heat) >= 2
    shade = live(hero(tables), tables, Environment(35, 5, 0, "rest", sheltered=True), 8)
    assert body.heat_index(shade.body_heat) <= 1


def test_starving_and_thirst_build_exhaustion_and_kill(tables):
    c = hero(tables)
    live(c, tables, Environment(15, 5, 0, "rest"), 80)
    assert c.exhaustion == 6
    assert body.travel_multiplier(c) is None
    assert body.hp_cap(c) == max(1, c.max_hp // 2)


def test_condition_penalties(tables):
    c = hero(tables)
    assert body.condition_penalty(c) == 0
    c.hunger, c.thirst, c.fatigue = 60, 70, 95
    assert body.condition_penalty(c) == -4
    c.body_heat = -90
    assert body.condition_penalty(c) == -6


def test_long_rest_removes_exhaustion_only_when_fed(tables):
    c = hero(tables)
    c.exhaustion = 2
    c.hunger = 90
    body.sleep_recovery(c)
    assert c.exhaustion == 2
    c.hunger = 10
    body.sleep_recovery(c)
    assert c.exhaustion == 1


# ---------------------------------------------------------------------------- food and water in the game
@pytest.fixture
def game(tables, world):
    import copy

    return new_game(copy.deepcopy(world), tables, hero(tables))


def test_characters_start_with_water(game):
    skins = [it for it in game.leader.inventory if container_capacity(game.tables.items, it)]
    assert skins and all(it.fill == container_capacity(game.tables.items, it) and it.fill_kind == "clean" for it in skins)
    assert game.tables.items.weight(skins[0]) > game.tables.items.get("waterskin")["weight"]


def test_eating_and_drinking_from_the_pack(game):
    c = game.leader
    rations = sum(it.qty for it in c.inventory if it.def_id == "rations")
    water = sum(it.fill for it in c.inventory)
    c.hunger, c.thirst = 60, 60
    game.player.x, game.player.y = next((x, y) for x in range(game.world.width) for y in range(game.world.height)
                                        if game.world.settlement_at(x, y) is None and not game.world.river[x, y]
                                        and game.biome_def(x, y)["passable"] and game.biome_key(x, y) != "marsh")
    survival.feed(game, c)
    assert c.hunger < 60 and c.thirst < 60
    assert sum(it.qty for it in c.inventory if it.def_id == "rations") < rations
    assert sum(it.fill for it in c.inventory) < water


def test_wells_in_town_are_free_and_clean(game):
    s = game.world.settlements[0]
    game.player.x, game.player.y = s.x, s.y
    assert survival.water_here(game) == ("clean", "the well")
    c = game.leader
    for it in c.inventory:
        it.fill, it.fill_kind = 0.0, ""
    notes = survival.fill_skins(game)
    assert any("fill" in n for n in notes)
    assert all(it.fill_kind == "clean" for it in c.inventory if it.fill)


def test_river_water_may_make_you_sick(game):
    exposed = 0
    for i in range(200):
        c = game.leader
        c.conditions.clear()
        game.world.time += 7
        survival.drink_from(game, c, "marsh", 1, "the marsh")
        exposed += any(x.startswith("exposed:") for x in c.conditions)
    assert 5 <= exposed <= 60


def test_spoiled_food_is_avoided(game):
    c = game.leader
    bread = add_item(c, game.tables.items, "bread", 1, made_at=game.world.time - 10 * 24 * 60)
    assert survival.spoiled(game, bread)
    assert bread not in survival.food_choices(game, c)
    assert bread in survival.food_choices(game, c, desperate=True)


def test_time_passing_feeds_the_body_and_death_ends_the_game(game):
    c = game.leader
    for it in list(c.inventory):
        if game.tables.items.get(it.def_id).get("food") or it.fill:
            c.inventory.remove(it)
    game.player.x, game.player.y = next((x, y) for x in range(game.world.width) for y in range(game.world.height)
                                        if game.world.settlement_at(x, y) is None and not game.world.river[x, y]
                                        and game.biome_key(x, y) in ("plains", "hills", "forest"))
    game.auto_supplies = True
    for _ in range(24 * 6):
        game.pass_time(60, "rest")
        if game.over:
            break
    assert game.over is not None and not c.alive
    assert "thirst" in game.over["cause"] or "starv" in game.over["cause"] or "exhaust" in game.over["cause"] \
        or "froze" in game.over["cause"] or "heat" in game.over["cause"]


def test_new_body_fields_survive_saving(game, tmp_path):
    c = game.leader
    c.hunger, c.thirst, c.body_heat, c.wet, c.exhaustion, c.blood = 40.5, 22.0, -35.0, 60.0, 2, 80.0
    c.injuries.append("limp")
    folder = save.save_game(game, tmp_path)
    loaded = save.load_game(folder, game.tables)
    d = loaded.leader
    assert (d.hunger, d.thirst, d.body_heat, d.wet, d.exhaustion, d.blood) == (40.5, 22.0, -35.0, 60.0, 2, 80.0)
    assert d.injuries == ["limp"]
    skin = next(it for it in d.inventory if it.def_id == "waterskin")
    assert skin.fill > 0 and skin.fill_kind == "clean"


def test_weather_slows_travel_and_shortens_sight(game):
    from realmwalker.world.weather import Weather

    assert Weather("blizzard", -10, 50, 0.9, 1, 0.2).travel_factor() > Weather("clear", 10, 5, 0, 0, 1).travel_factor()
    game.enter_local()
    from realmwalker.game.vision import sight_radius

    game._weather_cache._value = Weather("fog", 5, 3, 0, 0.8, 0.25)
    game._weather_cache._key = (game.player.x, game.player.y, game.world.time // 10)
    radius, _ = sight_radius(game, game.local)
    assert 0 < radius <= 12


def test_the_sky_says_when_it_turns(game, monkeypatch):
    """Rain, snow, fog and heat are remarked on when they start and when they stop; cloud is not."""
    from realmwalker.world.weather import Weather

    kinds = ["clear", "cloudy", "overcast", "rain", "rain", "clear", "fog"]
    state = {"i": 0}

    def fake_weather(g):
        return Weather(kind=kinds[min(state["i"], len(kinds) - 1)], temp=10.0, wind=5.0, precip=0.0,
                       cloud=0.5, visibility=1.0)

    monkeypatch.setattr("realmwalker.game.survival.weather", fake_weather)
    said = []
    game.say = lambda text, color="fg": said.append(text)
    for i in range(len(kinds)):
        state["i"] = i
        game.world.time += 200  # past the cooldown
        game._weather_moment()
    text = " ".join(said)
    assert "rain" in text.lower() and ("fog" in text.lower() or "world shrinks" in text)
    assert not any("cloud comes up" in line.lower() for line in said[:1])
    assert len(said) <= 4, said  # cloud thickening and thinning is not news
