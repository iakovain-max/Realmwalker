"""Services in town: inns, healers, temples, smiths, stables and paid work; animals on the road."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import services
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.state import new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.character import Sheet
from realmwalker.rules.inventory import add_item
from realmwalker.rules.wounds import Wound
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Serviceland", 8, "medium"), tables)


def hero(tables):
    b = CharacterBuilder(tables, RNG(1, "hero"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background("farmer")
    return b.build()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables, hero(tables))
    g.leader.money = 100000
    return g


def person(game, job: str):
    for s in game.world.settlements:
        if s.kind not in ("town", "city"):
            continue
        prepare_town(game, s)
        for n in npcs_in(game.world, s.id):
            if n.job == job:
                game.player.x, game.player.y = s.x, s.y
                return n
    pytest.skip(f"no {job}")


def offered(game, npc):
    return {s.id: s for s in services.services_for(game, npc)}


def test_the_inn(game):
    inn = person(game, "innkeeper")
    c = game.leader
    got = offered(game, inn)
    assert {"room", "stay", "meal", "bath", "perform", "gamble"} <= set(got)
    c.hunger, c.thirst, c.dirt, c.wet, c.fatigue, c.hp = 70, 70, 80, 60, 80, 1
    money = c.money
    services.perform(game, inn, "meal", "modest")
    assert c.hunger < 20 and c.thirst < 40 and c.money < money
    services.perform(game, inn, "bath")
    assert c.dirt < 1 and c.wet < 1
    services.perform(game, inn, "room", "modest")
    assert c.fatigue < 20 and c.hp == c.max_hp
    before = c.money
    services.perform(game, inn, "perform")
    assert not offered(game, inn)["perform"].enabled, "once a day"
    assert c.money >= before
    results = set()
    for _ in range(12):
        m = c.money
        services.perform(game, inn, "gamble", "10")
        results.add((c.money > m) - (c.money < m))
        game.world.time += 7
    assert results & {1, -1}


def test_healers_and_temples(game):
    healer = person(game, "healer")
    c = game.leader
    c.wounds += [Wound("left_arm", "cut", 2, 2, 0), Wound("right_leg", "fracture", 2, 0, 0),
                 Wound("torso", "puncture", 3, 1, 0, internal=True, infection=30.0, infected=True)]
    got = offered(game, healer)
    assert got["treat_wounds"].enabled and got["treat_wounds"].price > 0 and got["surgery"].enabled
    services.perform(game, healer, "treat_wounds")
    assert all(w.bandaged or not w.bleed for w in c.wounds)
    assert next(w for w in c.wounds if w.kind == "fracture").splinted
    services.perform(game, healer, "surgery")
    assert not any(w.internal for w in c.wounds)
    assert not offered(game, healer)["herbal_cure"].enabled, "nothing left to cure"
    c.wounds[0].infection = 25.0
    services.perform(game, healer, "herbal_cure")
    assert c.effects.get("herbal", 0) > 0 and c.wounds[0].infection < 25
    priest = person(game, "priest")
    c.hp = 1
    services.perform(game, priest, "prayer_healing")
    assert c.hp > 1
    c.diseases.append({"id": "dysentery", "phase": "sick", "stage": 1, "hours": 0.0, "until": 0, "day": 0.0, "wins": 0,
                       "rested": 0.0})
    assert offered(game, priest)["cure_disease"].enabled
    services.perform(game, priest, "cure_disease")
    assert not any(d["id"] == "dysentery" for d in c.diseases)


def test_the_smith_mends_and_pays_for_work(game):
    smith = person(game, "smith")
    c = game.leader
    sword = add_item(c, game.tables.items, "longsword", condition=40)
    repair = offered(game, smith)["repair"]
    assert repair.enabled and any(arg == str(sword.uid) for arg, _, _ in repair.options)
    services.perform(game, smith, "repair", str(sword.uid))
    assert sword.condition == 100
    money, t = c.money, game.world.time
    services.perform(game, smith, "labour")
    assert c.money > money and game.world.time - t >= 8 * 60
    assert not offered(game, smith)["labour"].enabled


def test_animals(game):
    stable = person(game, "stablemaster")
    c = game.leader
    s = Sheet(c, game.tables)
    light = s.capacity()[0]
    buy = offered(game, stable)["buy_animal"]
    assert {arg for arg, _, _ in buy.options} >= {"mule", "riding_horse"}
    services.perform(game, stable, "buy_animal", "mule")
    assert c.animals and Sheet(c, game.tables).capacity()[0] == light + 200
    services.perform(game, stable, "buy_animal", "riding_horse")
    road = next((x, y) for x in range(game.world.width) for y in range(game.world.height) if game.world.road[x, y])
    game.player.x, game.player.y = road
    assert services.riding_factor(game) < 1.0
    sell = offered(game, stable)["sell_animal"]
    money = c.money
    services.perform(game, stable, "sell_animal", sell.options[0][0])
    assert c.money > money and len(c.animals) == 1


def test_hungry_animals_starve(game):
    c = game.leader
    c.animals.append({"kind": "mule", "name": "Nell", "unfed": 0, "bought": 0})
    c.inventory = [i for i in c.inventory if i.def_id != "fodder"]
    snow = next(((x, y) for x in range(game.world.width) for y in range(game.world.height)
                 if game.biome_key(x, y) in ("tundra", "high_mountains", "desert")
                 and game.world.settlement_at(x, y) is None), None)
    if snow is None:
        pytest.skip("no barren land")
    game.player.x, game.player.y = snow
    msgs = []
    for _ in range(5):
        msgs += services.feed_animals(game)
    assert not c.animals and any("starved" in m for m in msgs)
    c.animals.append({"kind": "mule", "name": "Bess", "unfed": 2, "bought": 0})
    add_item(c, game.tables.items, "fodder", 1)
    services.feed_animals(game)
    assert c.animals[0]["unfed"] == 0 and not any(i.def_id == "fodder" for i in c.inventory)


def test_hostile_people_offer_nothing(game):
    inn = person(game, "innkeeper")
    inn.disposition = -90
    assert services.services_for(game, inn) == []


def test_services_in_conversation(game):
    from realmwalker.game.dialogue import Conversation

    inn = person(game, "innkeeper")
    game.enter_local()
    conv = Conversation(game, inn)
    choice = next(c for c in conv.menu() if c.id == "services")
    assert conv.choose(choice) == "services"


def test_animals_survive_saving(game, tmp_path):
    from realmwalker.game import save

    game.leader.animals.append({"kind": "pony", "name": "Mouse", "unfed": 1, "bought": 5})
    folder = save.save_game(game, tmp_path)
    assert save.load_game(folder, game.tables).leader.animals == game.leader.animals


# ---------------------------------------------------------------------------- Expansion 2 part D: lifestyles and passage
def test_inns_offer_the_books_grades_at_the_books_prices(game):
    inn = person(game, "innkeeper")
    got = offered(game, inn)
    rooms = {arg: price for arg, _, price in got["room"].options}
    meals = {arg: price for arg, _, price in got["meal"].options}
    spec = game.tables.economy["services"]["inn"]
    town = game.world.settlements[inn.settlement]
    assert set(rooms) == set(spec["grades"][town.kind])
    party = len(game.party)
    if inn.mood() == "neutral" and not inn.flags.get("price_mod"):
        assert rooms["poor"] == 10 * party and meals["modest"] == 10 * party  # 1 sp a bed, 1 sp a meal (PHB 2024)
    assert rooms["squalid"] < rooms["poor"] < rooms["modest"]


def test_a_squalid_bed_may_cost_you_your_purse_and_a_wealthy_one_is_noticed(game, monkeypatch):
    from realmwalker.core.rng import RNG as R

    inn = person(game, "innkeeper")
    monkeypatch.setattr(R, "chance", lambda self, p: p > 0)
    before = game.leader.money
    msgs = services.perform(game, inn, "room", "squalid")
    assert game.leader.money < before - 7 and any("purse is lighter" in m for m in msgs)
    town = game.world.settlements[inn.settlement]
    if "wealthy" in game.tables.economy["services"]["inn"]["grades"][town.kind]:
        services.perform(game, inn, "room", "wealthy")
        seen = game.renown.flags["seen_living_well"]
        assert seen[0] == inn.settlement and seen[2] > 0


def test_a_week_at_the_inn_passes_the_days_fed_and_rested(game):
    inn = person(game, "innkeeper")
    c = game.leader
    c.hunger, c.thirst = 80, 80
    t0, money = game.world.time, c.money
    services.perform(game, inn, "stay", "modest:3")
    assert game.world.time - t0 >= 3 * 24 * 60 - 120
    assert c.hunger < 60 and c.thirst < 60
    assert money - c.money == offered(game, inn)["stay"].options[0][2] // 3 * 3 or c.money < money


def test_the_coach_takes_you_to_another_town_along_the_roads(game):
    from realmwalker.game import passage

    for s in game.world.settlements:
        routes = passage.coach_routes(game, s)
        if routes:
            break
    else:
        pytest.skip("no coach routes")
    dest, miles, minutes = routes[0]
    assert miles > 0 and minutes > 0 and dest is not s
    fare = passage.fare(game, "coach", miles)
    assert fare == 3 * miles * len(game.party)
    game.player.x, game.player.y = s.x, s.y
    t0 = game.world.time
    passage.travel(game, "coach", dest, miles, minutes)
    assert (game.player.x, game.player.y) == (dest.x, dest.y) and game.world.time - t0 >= minutes


def test_ships_sail_between_harbours(game):
    from realmwalker.game import passage

    ports = [s for s in game.world.settlements if passage.harbour(game, s)]
    for s in ports:
        routes = passage.ship_routes(game, s)
        if routes:
            assert all(passage.harbour(game, d) for d, _, _ in routes)
            assert passage.fare(game, "ship", routes[0][1]) == 10 * routes[0][1] * len(game.party)
            return
    pytest.skip("no harbours with routes here")


def test_a_messenger_fetches_a_waiting_companion(game):
    from realmwalker.game import companions, passage

    inn = person(game, "innkeeper")
    here = game.world.settlements[inn.settlement]
    friend = hero(game.tables)
    friend.is_player = False
    friend.companion = {"npc": -1, "archetype": "sellsword", "values": [], "want": "pay", "loyalty": 50.0,
                        "wage": 0, "share": 0.0, "hired": 0, "order": "wait", "home": 0, "unpaid": 0,
                        "wait_at": [here.x + 9, here.y]}
    game.waiting.append(friend)
    jobs = passage.messenger_jobs(game, here)
    assert jobs and jobs[0][0] is friend
    services.perform(game, inn, "messenger", "0")
    assert friend.companion["wait_at"] == [here.x, here.y]
    game.player.x, game.player.y = here.x, here.y
    assert not companions.rejoin(game)  # still on the road
    game.pass_time(int(friend.companion["coming"] - game.world.time) + 30, "rest")
    assert friend in game.party


def test_shops_stock_the_new_gear_by_size_and_people(game):
    from realmwalker.game import economy

    econ = game.tables.economy
    assert any(len(line) == 4 for line in econ["shops"]["general"]["stock"])
    city_only = {line[0] for line in econ["shops"]["general"]["stock"] if len(line) == 4 and line[3] == "city"}
    for s in game.world.settlements:
        if s.kind != "hamlet":
            continue
        prepare_town(game, s)
        for n in npcs_in(game.world, s.id):
            if economy.shop_kind(game, n) == "general":
                assert not city_only & set(economy.shop_state(game, n)["stock"])
                return


def test_a_stay_rolls_for_thieves_once_a_night_and_a_messenger_can_be_sent_again(game, monkeypatch):
    from realmwalker.game import passage

    inn = person(game, "innkeeper")
    rolls = []
    real = services._night
    monkeypatch.setattr(services, "_night", lambda *a, **k: rolls.append(k.get("theft", True)) or real(*a, **k))
    services.perform(game, inn, "stay", "squalid:3")
    assert rolls.count(True) == 3
    here = game.world.settlements[inn.settlement]
    friend = hero(game.tables)
    friend.is_player = False
    friend.companion = {"npc": -1, "order": "wait", "wait_at": [here.x + 9, here.y], "coming": game.world.time + 10}
    game.waiting.append(friend)
    assert passage.messenger_jobs(game, here)  # sent for before, gone elsewhere: may be sent for again
