"""Fair chances (2026-10, Anton: "make the game a bit easier, it is too easy to randomly die"). Measured by playing
sixty careful lives for a month each: nearly all of them died, most of things a careful player could not see coming or
could do nothing about. Each test here is one of those things."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import camp, dungeon, fight, quests, survival
from realmwalker.game.encounters import DEADLY_RATIO, make_encounter
from realmwalker.game.people import npcs_in
from realmwalker.game.state import GameState, new_game
from realmwalker.rules import body
from realmwalker.rules.body import Environment
from realmwalker.rules.character import Sheet
from realmwalker.rules.combat import WOUND_HP_FLOOR
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.inventory import add_item
from realmwalker.rules.items import Item
from realmwalker.rules.wounds import make_wound
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables
from realmwalker.world.weather import Weather


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Fairland", 41, "small"), tables).generate()


def hero(tables, cls="fighter", seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("soldier")
    return b.build()


@pytest.fixture
def game(tables, world, monkeypatch):
    monkeypatch.setattr("realmwalker.game.encounters.encounter_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.events.event_chance", lambda *a: 0.0)
    monkeypatch.setattr(GameState, "lost_dc", lambda self: None)
    return new_game(copy.deepcopy(world), tables, hero(tables))


def sky(monkeypatch, kind, temp=8.0, precip=0.6):
    w = Weather(kind, temp, 10.0, precip, 0.9, 0.8)
    monkeypatch.setattr(survival, "weather", lambda game: w)
    return w


def wild(game):
    """Out in the open, away from any town or river."""
    w = game.world
    for x in range(w.width):
        for y in range(w.height):
            if w.settlement_at(x, y) is None and not w.river[x, y] and game.step_minutes(x, y, x, y) is not None and \
                    not any(w.biome_id(nx, ny) == "lake" for _, nx, ny in w.neighbours(x, y)) and \
                    game.biome_key(x, y) not in ("marsh",):
                game.player.x, game.player.y = x, y
                game.player.local_key = None
                return x, y
    raise AssertionError("no dry wild country")


# ---------------------------------------------------------------------------- fights
def test_robbers_leave_the_spellbook_the_holy_symbol_and_the_work(game):
    leader = game.leader
    for item in ("spellbook", "holy_symbol"):
        add_item(leader, game.tables.items, item)
    leader.inventory.append(Item(9999, "gold_ring", 1, name="the Fernsby ring", tags=["quest:7"]))
    fight._rob_party(game, RNG(1, "rob"))
    left = {it.def_id for it in leader.inventory}
    assert {"spellbook", "holy_symbol", "gold_ring"} <= left


def test_a_new_character_is_not_sent_after_a_troll(game):
    town = game.world.settlements[game.player.home]
    game.enter_local()
    giver = next(n for n in npcs_in(game.world, town.id) if n.alive)
    groups = set()
    for seed in range(60):
        q = quests.make_offer(game, giver, RNG(seed, "beast"), template="hunt_beast")
        if q is not None:
            groups.add(q["target"]["group"])
            assert quests.beast_ratio(game, q["target"]["group"]) < DEADLY_RATIO
    assert groups and not groups & {"troll", "ogre", "brown_bear", "dire_wolves"}
    q = quests.make_offer(game, giver, RNG(1, "beast"), template="hunt_beast")
    assert "Hunting" in quests.danger_note(game, q)


def test_robbers_take_half_the_purse_and_no_blood_is_spilled(game):
    game.leader.money = 1000
    game.encounter = make_encounter(game, "footpads", RNG(3, "enc"))
    cost, why = fight.encounter_pay_cost(game)
    assert cost == 500 and not why
    assert fight.encounter_pay(game)
    assert game.encounter is None and game.battle is None and game.leader.money == 500


def test_wolves_take_food_instead_of_you(game):
    for it in list(game.leader.inventory):
        if game.tables.items.get(it.def_id).get("food"):
            game.leader.inventory.remove(it)
    game.encounter = make_encounter(game, "wolf_pack", RNG(3, "enc"))
    food, why = fight.encounter_bait_food(game)
    assert food is None and "enough food" in why  # nothing to throw them
    add_item(game.leader, game.tables.items, "raw_meat", 5)
    assert fight.encounter_bait(game)
    assert game.encounter is None and game.battle is None
    assert sum(it.qty for it in game.leader.inventory if it.def_id == "raw_meat") < 5


def test_purse_and_food_are_offered_only_where_they_would_work(game):
    game.leader.money = 1000
    add_item(game.leader, game.tables.items, "rations", 5)
    game.encounter = make_encounter(game, "wolf_pack", RNG(3, "enc"))
    assert fight.encounter_pay_cost(game)[0] is None  # wolves want no money
    game.encounter = make_encounter(game, "restless_dead", RNG(3, "enc"))
    assert fight.encounter_pay_cost(game)[0] is None and fight.encounter_bait_food(game)[0] is None
    game.encounter = make_encounter(game, "bandits", RNG(3, "enc"))
    assert fight.encounter_bait_food(game)[0] is None


def test_a_small_hit_on_a_frail_character_is_not_a_gushing_wound(tables):
    """A level-1 wizard's seven hit points are luck and nerve: wounds are sized against a body of at least
    WOUND_HP_FLOOR hit points."""
    from realmwalker.rules.wounds import severity_for

    assert severity_for(5, max(7, WOUND_HP_FLOOR), False, RNG(1, "w")) < 3


def test_the_bleeding_wakes_you_before_you_bleed_out_in_a_faint(game):
    c = game.leader
    game.survival = True
    c.wounds.append(make_wound("torso", "slashing", 3, RNG(2, "w"), now=game.world.time))
    c.hp = 1
    note = fight.lie_senseless(game, 4)
    assert c.alive and game.over is None
    assert "bleeding brings you round" in note


# ---------------------------------------------------------------------------- the body
def test_a_fire_does_not_give_you_heatstroke(tables):
    c = hero(tables)
    s = Sheet(c, tables)
    for _ in range(10):
        body.tick(c, s, Environment(14, 5, 0, "rest", fire=True), 60)
    assert body.heat_index(c.body_heat) <= 1, c.body_heat


def test_a_rough_shelter_keeps_off_the_wind_and_the_rain(tables):
    bare = hero(tables)
    under = hero(tables)
    for _ in range(6):
        body.tick(bare, Sheet(bare, tables), Environment(3, 30, 60, "rest"), 60)
        body.tick(under, Sheet(under, tables), Environment(3, 30, 60, "rest", shelter=True), 60)
    assert under.wet < bare.wet and under.body_heat > bare.body_heat


def test_you_can_build_a_shelter_and_light_a_fire_in_its_lee_in_a_storm(game, monkeypatch):
    wild(game)
    sky(monkeypatch, "storm", temp=2.0, precip=0.9)
    assert "no fire will catch" in camp.light_fire(game)[0]
    monkeypatch.setattr(camp, "check", lambda *a, **k: (True, "<dice>Survival</>"))
    msgs = camp.build_shelter(game)
    assert camp.camp_here(game).shelter, msgs
    add_item(game.leader, game.tables.items, "firewood", 1)
    camp.light_fire(game)
    assert camp.camp_here(game).fire


def test_rain_fills_a_waterskin_and_snow_does_by_a_fire(game, monkeypatch):
    wild(game)
    sky(monkeypatch, "rain", precip=0.6)
    assert survival.water_here(game) == ("clean", "rainwater")
    sky(monkeypatch, "snow", temp=-4, precip=0.6)
    assert survival.water_here(game) is None
    camp.make_camp(game).fire = True
    assert survival.water_here(game) == ("clean", "melted snow")
    sky(monkeypatch, "clear", precip=0.0)
    assert survival.water_here(game) is None


def test_skins_are_topped_up_at_a_well_and_from_the_rain_when_dry(game, monkeypatch):
    wild(game)
    skins = [it for it in game.leader.inventory if survival.container_capacity(game.tables.items, it)]
    assert skins
    for it in skins:
        it.fill, it.fill_kind = 0.5, "clean"
    sky(monkeypatch, "rain", precip=0.6)
    assert "rainwater" in survival.top_up(game)
    assert all(it.fill == survival.container_capacity(game.tables.items, it) for it in skins)
    for it in skins:
        it.fill = 2.0
    assert survival.top_up(game) == ""  # not while there is still water in them


def test_under_the_ground_the_rain_does_not_fall(game, monkeypatch):
    site = game.world.sites[0]
    game.player.x, game.player.y = site.x, site.y
    game.player.local_key = None
    game.enter_local()
    dungeon.descend(game, 1)
    assert game.local.kind == "dungeon"
    sky(monkeypatch, "rain", temp=1.0, precip=0.8)
    env = survival.environment(game, game.leader, "rest")
    assert env.sheltered
    assert survival.water_here(game) != ("clean", "rainwater")
    game.lit = None
    monkeypatch.setattr(fight, "party_has_light", lambda g: False)
    assert fight.battle_env(game, None).light == 0.0  # no noon under the ground
    game.lit = {"def_id": "torch", "hours": 1.0}
    assert fight.battle_env(game, None).party_light


def test_sleep_until_morning_wakes_you_at_first_light(game):
    m = game.moment
    game.world.time = (m.total_days + 1) * 1440 + 19 * 60
    game.survival = False
    wild(game)
    fight.rest(game, "night")
    assert game.light >= 0.3 or game.moment.hour >= 5, game.moment.time_text()
    assert game.moment.hour < 12


def test_worn_to_exhaustion_five_you_can_still_stagger(tables):
    c = hero(tables)
    c.exhaustion = 5
    assert body.travel_multiplier(c) == 4.0
    c.exhaustion = 6
    assert body.travel_multiplier(c) is None


def test_a_fur_cloak_does_not_cook_you_in_an_inn(tables):
    """Warm clothes warm you up to comfortable and no further when it is mild: you would open the cloak. (A traveller
    died of heatstroke sitting in a town at 16 C in a fur cloak.)"""
    from realmwalker.rules.inventory import equip

    c = hero(tables)
    it = add_item(c, tables.items, "fur_cloak")
    equip(c, tables.items, it.uid)
    s = Sheet(c, tables)
    for _ in range(24):
        body.tick(c, s, Environment(18, 0, 0, "rest", sheltered=True), 60)
    assert body.heat_index(c.body_heat) == 0, c.body_heat
    hot = hero(tables)
    for _ in range(6):
        body.tick(hot, Sheet(hot, tables), Environment(36, 5, 0, "walk"), 60)
    assert body.heat_index(hot.body_heat) >= 2, "a heat wave on the march is still dangerous"
