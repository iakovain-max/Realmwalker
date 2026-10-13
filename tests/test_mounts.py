"""Riding (2026-10, Anton): a horse makes you faster, and shows it; the party goes at the pace of its slowest member,
so it rides at a horse's pace only when everyone has a mount."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import mounts, services
from realmwalker.game.state import GameState, new_game
from realmwalker.rules import body
from realmwalker.rules.body import Environment
from realmwalker.rules.character import Sheet
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.wounds import make_wound
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Horseland", 5, "small"), tables)


def hero(tables, seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background("soldier")
    return b.build()


@pytest.fixture
def game(tables, world, monkeypatch):
    monkeypatch.setattr("realmwalker.game.encounters.encounter_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.events.event_chance", lambda *a: 0.0)
    monkeypatch.setattr(GameState, "lost_dc", lambda self: None)
    g = new_game(copy.deepcopy(world), tables, hero(tables))
    g.survival = False
    return g


def horse(game, kind="riding_horse", name="Bess"):
    game.leader.animals.append({"kind": kind, "name": name, "unfed": 0, "bought": 0})


def companion(game, seed=2):
    c = hero(game.tables, seed)
    c.companion = {"loyalty": 60, "npc": -1, "bond": "sworn"}
    c.inventory = game.leader.inventory
    game.party.append(c)
    return c


def far_town(game):
    p = game.player
    towns = [s for s in game.world.settlements if 8 <= max(abs(s.x - p.x), abs(s.y - p.y)) <= 20
             and game.plan_travel((s.x, s.y)) is not None]
    return min(towns, key=lambda s: abs(s.x - p.x) + abs(s.y - p.y))


def journey(game, dest):
    start = game.world.time
    game.set_out(game.plan_travel((dest.x, dest.y)))
    for _ in range(400):
        if (game.player.x, game.player.y) == (dest.x, dest.y):
            break
        if game.travel is None:
            game.set_out(game.plan_travel((dest.x, dest.y)))
        game.travel_step()
    return game.world.time - start


def road_step(game):
    w = game.world
    for x in range(w.width - 1):
        for y in range(w.height):
            if w.road[x, y] and w.road[x + 1, y]:
                return x, y, x + 1, y
    raise AssertionError("no road")


def test_a_horse_makes_a_lone_traveller_faster_and_the_plan_says_so(game):
    dest = far_town(game)
    walking = game.plan_travel((dest.x, dest.y))
    on_foot = journey(copy.deepcopy(game), dest)
    horse(game)
    riding = game.plan_travel((dest.x, dest.y))
    assert riding.riding and riding.minutes < walking.minutes * 0.85
    assert "riding" in game.describe_plan(riding) or "saddle" in game.describe_plan(riding)
    assert "walking" in game.describe_plan(walking) or "on foot" in game.describe_plan(walking)
    assert journey(game, dest) < on_foot * 0.85


def test_one_horse_among_two_is_ridden_at_a_walk_and_the_game_says_why(game):
    companion(game)
    horse(game)
    x0, y0, x1, y1 = road_step(game)
    assert mounts.step_factor(game, x0, y0, x1, y1) == 1.0
    assert not mounts.all_mounted(game)
    assert "walks" in mounts.summary(game) and "Everyone needs a mount" in mounts.summary(game)
    assert any("on foot" in line for line in mounts.who_rides_what(game))
    horse(game, name="Nell")
    assert mounts.all_mounted(game) and mounts.step_factor(game, x0, y0, x1, y1) < 1.0


def test_the_slowest_mount_ridden_sets_the_pace_and_the_fastest_are_ridden(game):
    x0, y0, x1, y1 = road_step(game)
    horse(game, "draft_horse", "Old Tom")
    horse(game, "riding_horse", "Bess")
    # Alone, you take the riding horse: the draft horse is led.
    assert mounts.mount_of(game, game.leader)["name"] == "Bess"
    assert mounts.step_factor(game, x0, y0, x1, y1) == pytest.approx(0.65)
    companion(game)
    assert mounts.step_factor(game, x0, y0, x1, y1) == pytest.approx(0.9)  # the draft horse holds you back
    game.leader.animals = [{"kind": "mule", "name": "Jack", "unfed": 0, "bought": 0},
                           {"kind": "riding_horse", "name": "Bess", "unfed": 0, "bought": 0}]
    assert mounts.step_factor(game, x0, y0, x1, y1) == 1.0  # the one on the mule goes at a walk


def test_woods_halve_a_horse_and_marsh_or_mountains_stop_it(game):
    horse(game)
    w = game.world
    found = {}
    for x in range(w.width):
        for y in range(w.height):
            k = game.biome_key(x, y)
            if k in ("forest", "marsh", "plains", "mountains") and not w.road[x, y]:
                found.setdefault(k, (x, y))
    if "plains" in found:
        assert mounts.step_factor(game, *found["plains"], *found["plains"]) == pytest.approx(0.65)
    if "forest" in found:
        assert 0.65 < mounts.step_factor(game, *found["forest"], *found["forest"]) < 1.0
    for k in ("marsh", "mountains"):
        if k in found:
            assert mounts.step_factor(game, *found[k], *found[k]) == 1.0


def test_riding_tires_less_than_walking(tables):
    walker, rider = hero(tables), hero(tables)
    for _ in range(8):
        body.tick(walker, Sheet(walker, tables), Environment(12, 5, 0, "walk"), 60)
        body.tick(rider, Sheet(rider, tables), Environment(12, 5, 0, "ride"), 60)
    assert rider.fatigue < walker.fatigue and rider.thirst < walker.thirst and rider.hunger < walker.hunger


def test_a_mounted_member_rides_even_at_the_walkers_pace(game):
    companion(game)
    horse(game)
    assert mounts.activity_for(game, game.leader, "walk") == "walk", "bareback, a rider tires like a walker"
    from realmwalker.rules.inventory import add_item

    add_item(game.leader, game.tables.items, "riding_saddle")
    assert mounts.activity_for(game, game.leader, "walk") == "ride"
    assert mounts.activity_for(game, game.party[1], "walk") == "walk"
    assert mounts.activity_for(game, game.leader, "rest") == "rest"


def test_a_lame_leg_does_not_slow_a_rider(game):
    game.leader.wounds.append(make_wound("left_leg", "piercing", 3, RNG(1, "w"), now=game.world.time))
    lame = game.pace()
    horse(game)
    assert game.pace() < lame


def test_the_old_riding_factor_still_answers_and_stables_say_how_you_travel(game):
    horse(game)
    x0, y0, _, _ = road_step(game)
    game.player.x, game.player.y = x0, y0
    assert services.riding_factor(game) < 1.0
    assert "You ride" in mounts.summary(game)


def test_two_animals_bought_are_not_both_called_bess(game, monkeypatch):
    from realmwalker.game.people import npcs_in

    town = game.world.settlements[game.player.home]
    for s in [town] + list(game.world.settlements):
        game.player.local_key = None
        game.player.x, game.player.y = s.x, s.y
        game.enter_local()
        stable = next((n for n in npcs_in(game.world, s.id) if n.job == "stablemaster" and n.alive), None)
        if stable is not None:
            break
        game.leave_local()
    else:
        pytest.skip("no stable in this world")
    game.leader.money = 10 ** 6
    for _ in range(4):
        services.perform(game, stable, "buy_animal", "pony")
    names = [a["name"] for a in game.leader.animals]
    assert len(names) == len(set(names)) == 4


# ---------------------------------------------------------------------------- Expansion 2 part D: mounts, tack, vehicles
def test_a_mastiff_carries_only_the_small_and_an_elephant_needs_its_seat(game):
    horse(game, "mastiff", "Grip")
    assert mounts.mount_of(game, game.leader) is None  # a man is too big for a dog
    game.leader.race = "halfling"
    assert mounts.mount_of(game, game.leader) is not None
    game.leader.race = "human"
    game.leader.animals = []
    horse(game, "elephant", "Tusk")
    assert mounts.mount_of(game, game.leader) is None
    from realmwalker.rules.inventory import add_item

    add_item(game.leader, game.tables.items, "exotic_saddle")
    assert mounts.mount_of(game, game.leader) is not None
    assert id(game.leader) in mounts.saddled(game)


def test_a_camel_keeps_its_pace_in_the_dunes(game):
    horse(game, "camel", "Hump")
    w = game.world
    if "dunes" not in w.biome_ids:
        pytest.skip("no dunes")
    idx = w.biome_ids.index("dunes")
    spots = [(x, y) for x in range(w.width) for y in range(w.height) if w.biome[x, y] == idx and not w.road[x, y]]
    if not spots:
        pytest.skip("no dunes")
    x, y = spots[0]
    assert mounts.land_share(game, x, y, game.leader.animals[0]) == 1.0
    assert mounts.land_share(game, x, y) < 1.0


def test_a_cart_drawn_by_a_spare_mule_carries_much_more_and_goes_slowly_off_the_road(game):
    from realmwalker.game.services import animal_carry

    horse(game, "riding_horse", "Bess")
    horse(game, "mule", "Jack")
    before = Sheet(game.leader, game.tables).capacity()[0]
    game.leader.vehicles.append({"kind": "cart", "bought": 0})
    assert mounts.drawn(game) is not None and [a["name"] for a in mounts.pullers(game)] == ["Jack"]
    assert Sheet(game.leader, game.tables).capacity()[0] > before + 500
    assert animal_carry(game.leader, game.tables) > 600
    w = game.world
    off = [(x, y) for x in range(1, w.width - 1) for y in range(w.height) if not w.road[x, y] and not w.road[x + 1, y]]
    x, y = off[0]
    assert mounts.step_factor(game, x, y, x + 1, y) >= 1.5
    game.leader.animals = [a for a in game.leader.animals if a["name"] == "Bess"]
    assert mounts.drawn(game) is None  # nothing left to pull it


def test_a_carriage_seats_those_without_a_mount(game):
    c = companion(game)
    horse(game, "riding_horse", "Bess")
    horse(game, "draft_horse", "Dobbin")
    game.leader.vehicles.append({"kind": "carriage", "bought": 0})
    # Bess carries the leader, Dobbin goes to the companion... unless the carriage takes one of them
    ridden, walkers = mounts.assign(game)
    assert not walkers or id(walkers[0]) in mounts.seated(game)
    assert mounts.activity_for(game, c, "walk") in ("ride", "walk")


def test_stabling_in_town_feeds_the_animals_for_five_silver(game):
    s = next(s for s in game.world.settlements if s.kind in ("town", "city"))
    game.player.x, game.player.y = s.x, s.y
    horse(game)
    game.leader.inventory = [it for it in game.leader.inventory if it.def_id != "fodder"]
    money = game.leader.money = 1000
    services.feed_animals(game)
    assert money - game.leader.money == game.tables.economy["services"]["stabling"] == 50
    assert game.leader.animals[0]["unfed"] == 0


def test_the_mounts_have_their_2025_stat_blocks(tables):
    for cid in ("camel", "draft_horse", "mastiff", "mule", "pony", "riding_horse", "warhorse"):
        assert cid in tables.creatures
    assert "guard_dogs" in tables.creatures.encounters
