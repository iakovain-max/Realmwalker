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
    assert {"room_common", "room_private", "meal", "bath", "perform", "gamble"} <= set(got)
    c.hunger, c.thirst, c.dirt, c.wet, c.fatigue, c.hp = 70, 70, 80, 60, 80, 1
    money = c.money
    services.perform(game, inn, "meal")
    assert c.hunger < 20 and c.thirst < 40 and c.money < money
    services.perform(game, inn, "bath")
    assert c.dirt < 1 and c.wet < 1
    services.perform(game, inn, "room_private")
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
