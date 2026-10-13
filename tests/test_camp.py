"""Camping, living off the land, travel events, getting lost and the day's passage."""

import copy

import numpy as np
import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import camp, events, fight
from realmwalker.game.state import new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.inventory import add_item
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from realmwalker.world.weather import Weather
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Campland", 41, "small"), tables)


def hero(tables, seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background("guide")
    return b.build()


@pytest.fixture
def game(tables, world):
    return new_game(copy.deepcopy(world), tables, hero(tables))


def go_to(game, biome: str, road: bool | None = None, river: bool | None = None):
    w = game.world
    idx = w.biome_ids.index(biome)
    cells = np.argwhere(w.biome == idx)
    for x, y in cells:
        x, y = int(x), int(y)
        if w.settlement_at(x, y) is not None:
            continue
        if road is not None and bool(w.road[x, y]) != road:
            continue
        if river is not None and bool(w.river[x, y]) != river:
            continue
        game.player.x, game.player.y = x, y
        return x, y
    pytest.skip(f"no {biome} tile to test in")


def set_weather(game, kind="clear", temp=10.0, vis=1.0, wind=5.0, precip=0.0):
    from realmwalker.world.weather import WeatherCache

    game._weather_cache = WeatherCache(minutes=10 ** 9)
    game._weather_cache._value = Weather(kind, temp, wind, precip, 0.5, vis)
    game._weather_cache._key = (game.player.x, game.player.y, game.world.time // 10 ** 9)


# ---------------------------------------------------------------------------- fire and food
def test_fire_needs_fuel_and_a_tinderbox(game):
    go_to(game, "forest")
    set_weather(game)
    assert any("fire" in m for m in camp.light_fire(game))
    assert camp.camp_here(game).fire
    game.camp = None
    go_to(game, "desert") if "desert" in game.world.biome_ids and (game.world.biome == game.world.biome_ids.index("desert")).any() \
        else go_to(game, "tundra")
    set_weather(game)
    for c in game.party:
        c.inventory = [i for i in c.inventory if i.def_id != "firewood"]
    msgs = camp.light_fire(game)
    lit = camp.camp_here(game).fire
    add_item(game.leader, game.tables.items, "firewood", 1)
    if not lit:
        assert any("firewood" in m or "burn" in m for m in msgs)
        camp.light_fire(game)
        assert camp.camp_here(game).fire


def test_no_fire_in_a_storm_without_shelter(game):
    go_to(game, "forest")
    set_weather(game, "storm", 8, 0.55, 50, 0.9)
    msgs = camp.light_fire(game)
    assert not camp.camp_here(game).fire and "weather" in msgs[0]


def test_cooking_and_boiling(game):
    go_to(game, "forest")
    set_weather(game)
    c = game.leader
    add_item(c, game.tables.items, "raw_meat", 3, made_at=game.world.time)
    assert "fire" in camp.cook(game)[0]
    camp.light_fire(game)
    camp.cook(game)
    assert not any(i.def_id == "raw_meat" for i in c.inventory)
    assert sum(i.qty for i in c.inventory if i.def_id == "cooked_meat") == 3
    skin = next(i for i in c.inventory if i.def_id == "waterskin")
    skin.fill_kind = "river"
    assert "pot" in camp.boil_water(game)[0]
    add_item(c, game.tables.items, "iron_pot")
    camp.boil_water(game)
    assert skin.fill_kind == "boiled"


def test_the_camp_breaks_when_you_move(game):
    go_to(game, "plains")
    set_weather(game)
    camp.make_camp(game)
    assert camp.camp_here(game) is not None
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if game.move(dx, dy):
            break
    assert game.camp is None


def test_a_fire_keeps_a_winter_night_at_bay(game):
    go_to(game, "plains")
    results = {}
    for fire in (False, True):
        g = copy.deepcopy(game)
        set_weather(g, "clear", -14, 1.0, 15)
        c = camp.make_camp(g)
        c.fire = fire
        g.encounter = None
        for _ in range(8):
            g.pass_time(60, "sleep")
        results[fire] = g.leader.body_heat
    assert results[False] < -15 and results[True] > results[False] + 15


# ---------------------------------------------------------------------------- the land provides
@pytest.mark.parametrize("action", ["forage", "hunt"])
def test_living_off_the_land_sometimes_works(game, action):
    go_to(game, "forest")
    set_weather(game)
    got = 0
    for i in range(12):
        before = sum(it.qty for it in game.leader.inventory if game.tables.items.get(it.def_id).get("food"))
        getattr(camp, action)(game)
        after = sum(it.qty for it in game.leader.inventory if game.tables.items.get(it.def_id).get("food"))
        got += after > before
        game.world.time += 97
    assert 1 <= got <= 12


def test_fishing_needs_water(game):
    go_to(game, "plains", river=False)
    assert "no water" in camp.fish(game)[0]
    go_to(game, "plains", river=True)
    add_item(game.leader, game.tables.items, "fishing_tackle")
    caught = 0
    for _ in range(8):
        msgs = camp.fish(game)
        caught += "catch" in msgs[-1]
        game.world.time += 131
    assert caught >= 1


def test_butchering_beasts_after_a_fight(game):
    from realmwalker.game.encounters import make_encounter

    go_to(game, "forest")
    game.encounter = make_encounter(game, "wolf_pack", RNG(3))
    fight.encounter_fight(game, ambush=False)
    for f in game.battle.side("foe"):
        f.state = "dead"
        f.creature.alive = False
    game.battle._check_end()
    after = fight.finish_battle(game)
    assert after.carcasses
    items, msgs = camp.butcher(game, after.carcasses)
    assert any(i.def_id == "raw_meat" for i in items) or "waste" in msgs[-1]


# ---------------------------------------------------------------------------- travel events
@pytest.mark.slow
def test_every_event_and_option_can_be_played(game):
    c = game.leader
    c.money = 100000
    for item in ("rations", "bandages", "healing_herbs"):
        add_item(c, game.tables.items, item, 10)
    for item in ("rope", "crowbar", "shovel", "grappling_hook"):  # some ways through need a tool
        add_item(c, game.tables.items, item)
    for eid, spec in game.tables.travel_events.items():
        for i, opt in enumerate(spec["options"]):
            g = copy.deepcopy(game)
            ev = events.make_event(g, eid)
            g.event = ev
            shop = events.choose(g, ev, i)
            if "shop" in opt:
                assert shop is not None
                stock = {item: int(q) for item, q in shop["stock"]}
                item = next(iter(stock))
                money = events.party_money(g)
                assert "buy" in events.buy(g, item, shop["markup"], stock)
                assert events.party_money(g) < money
            else:
                assert ev.done and ev.result, (eid, i)


def test_options_need_what_they_ask_for(game):
    c = game.leader
    c.money = 0
    c.inventory = [i for i in c.inventory if i.def_id != "rations"]
    ev = events.make_event(game, "refugees")
    opts = events.options(game, ev)
    assert not opts[0][1] and "rations" in opts[0][2]
    assert not opts[1][1]


def test_news_puts_places_on_the_map(game):
    before = int(game.player.explored.sum()) + len(game.player.known_settlements)
    text = events.hear_place(game, RNG(1))
    after = int(game.player.explored.sum()) + len(game.player.known_settlements)
    assert "hear of" in text and after > before


def test_events_happen_on_the_road(game, monkeypatch):
    monkeypatch.setattr("realmwalker.game.encounters.encounter_chance", lambda *a: 0.0)
    go_to(game, "plains", road=True)
    seen = 0
    for i in range(300):
        game.world.time += 60
        ev = events.roll_event(game, 120)
        seen += ev is not None
    assert seen >= 5


# ---------------------------------------------------------------------------- getting lost
def test_fog_off_the_road_can_lose_you_and_a_road_finds_you(game, monkeypatch):
    monkeypatch.setattr("realmwalker.game.encounters.encounter_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.events.event_chance", lambda *a: 0.0)
    go_to(game, "plains", road=False)
    set_weather(game, "fog", 5, 0.25, 3)
    assert game.lost_dc() is not None and game.lost_dc() >= 15
    for _ in range(30):
        game._check_bearings()
        if game.lost:
            break
    assert game.lost
    x, y = go_to(game, "plains", road=True)
    game._check_bearings()
    assert not game.lost


# ---------------------------------------------------------------------------- the day's passage
def test_a_day_on_the_road_is_written_up(game, data, monkeypatch):

    monkeypatch.setattr("realmwalker.game.encounters.encounter_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.events.event_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.state.GameState.lost_dc", lambda self: None)
    game.survival = False
    start_day = game.moment.total_days
    for _ in range(200):
        moved = any(game.move(dx, dy) for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)))
        if game.narration or not moved:
            break
    assert game.moment.total_days > start_day
    assert game.narration and game.narration[0]["miles"] > 0
    facts = events.travel_day_facts(game, game.narration[0])
    text = events.travel_day_passage(RNG(2), data, facts)
    assert "{" not in text and str(facts["miles"]) in text or facts["lands"] in text or len(text) > 40


def test_a_night_in_the_open_is_heard(game):
    """A long rest outdoors brings one thing heard: the land, or the fire, or nothing much."""
    from realmwalker.game.camp import night_sound

    heard = {night_sound(game) for _ in range(1) for game.world.time in
             range(game.world.time, game.world.time + 400, 37)}
    assert heard and all(line and "{" not in line for line in heard)
    assert len(heard) > 1, heard


def test_making_things_at_camp(game):
    """Simple crafting (design section 11): torches, bandages, splints, salting, drying, a remedy."""
    from realmwalker.game import camp as camplogic

    c = game.leader
    ids = {cid for cid, *_ in camplogic.crafts(game)}
    assert {"torches", "bandages", "splints", "salted_meat", "dried_fish", "remedy"} <= ids
    # Nothing to work with: every recipe says why not.
    for it in list(c.inventory):
        remove = it.def_id in ("firewood", "linen_bolt", "salt", "raw_meat", "raw_fish", "healing_herbs")
        if remove:
            from realmwalker.rules.inventory import remove_item

            remove_item(c, it.uid)
    assert all(not ok for _, _, ok, _ in camplogic.crafts(game))
    assert "can't" in camplogic.make(game, "torches")[0]
    # With wood, torches can be made.
    add_item(c, game.tables.items, "firewood", 2)
    options = {cid: (ok, why) for cid, _, ok, why in camplogic.crafts(game)}
    assert options["torches"][0], options["torches"]
    before = sum(i.qty for i in c.inventory if i.def_id == "torch")
    out = camplogic.make(game, "torches")
    assert any("torch" in line for line in out)
    assert sum(i.qty for i in c.inventory if i.def_id == "torch") > before
    assert not sum(i.qty for i in c.inventory if i.def_id == "firewood") >= 2  # the wood was used


def test_being_lost_lasts_until_the_weather_lifts(game, monkeypatch):
    """You lose the way once and stay lost: no losing and finding it again at every step."""
    monkeypatch.setattr("realmwalker.game.encounters.encounter_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.events.event_chance", lambda *a: 0.0)
    go_to(game, "plains", road=False)
    set_weather(game, "fog", 5, 0.25, 3)
    for _ in range(30):
        game._check_bearings()
        if game.lost:
            break
    assert game.lost
    said = len(game.log.messages)
    for _ in range(10):
        game.world.time += 90
        game._check_bearings()
    assert game.lost, "the fog is still down"
    assert len(game.log.messages) == said, "and it says so once, not once a step"
    set_weather(game, "clear", 15, 1.0, 0)
    game.world.time += (12 - game.moment.hour) * 60  # noon
    game._check_bearings()
    assert not game.lost


def test_crossing_a_river_is_told_and_the_cold_is_felt(game, monkeypatch):
    """Wading is remarked on every time, in words that change, and winter water says so."""
    monkeypatch.setattr("realmwalker.game.encounters.encounter_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.events.event_chance", lambda *a: 0.0)
    w = game.world
    spot = None
    for x, y in np.argwhere(w.river):
        x, y = int(x), int(y)
        if w.road[x, y] or w.settlement_at(x, y) is not None:
            continue
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            if w.in_bounds(x - dx, y - dy) and not w.river[x - dx, y - dy] and                     game.step_minutes(x - dx, y - dy, x, y) is not None:
                spot = (x - dx, y - dy, dx, dy)
                break
        if spot:
            break
    if spot is None:
        pytest.skip("no river to wade in this world")
    sx, sy, dx, dy = spot

    def wade(temp):
        game.player.x, game.player.y = sx + dx, sy + dy  # pin the weather where the wading happens
        set_weather(game, "clear", temp, 1.0, 0)
        game.player.x, game.player.y = sx, sy
        game.lost = False  # hours pass with every step; don't let a dark night send us the wrong way
        game.world.time += (12 - game.moment.hour) * 60
        game.say("(wading again)", "system")  # the log folds a line repeated straight after itself into a count
        before = len(game.log.messages)
        game.move(dx, dy)
        said = [m.text for m in game.log.messages[before:] if "river" in m.text.lower()]
        assert said, "crossing a river is worth saying"
        assert said[0][:1].isupper(), f"and it starts like a sentence: {said[0]}"
        return said[0]

    warm = {wade(14.0) for _ in range(8)}
    assert len(warm) >= 2, f"and it does not say it the same way every time: {warm}"
    cold = {wade(-2.0) for _ in range(8)}
    assert cold & {"There is ice at the edges of a river. You cross anyway, and cannot feel your legs at the "
                   "far side.", "A river is snowmelt to the waist, and it takes your breath away.",
                   "You wade a river. The cold of it goes through you like a nail."} or         any("cold" in c or "ice" in c or "snowmelt" in c for c in cold), f"winter water is worse: {cold}"
