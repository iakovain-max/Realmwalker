"""The opening of the game, done on purpose rather than at random: a new character in a new world can find
people, food, work, and the way to it. If any of this breaks, a new player is stuck on their first evening."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import economy, quests
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables

SEEDS = (3, 42)


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def a_life(tables, seed):
    world = WorldGenerator(WorldOptions("Firstland", seed, "small"), tables).generate()
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background("soldier")
    game = new_game(world, tables, b.build())
    game.survival = False
    town = min(world.settlements, key=lambda s: abs(s.x - game.player.x) + abs(s.y - game.player.y))
    game.player.x, game.player.y = town.x, town.y
    game.player.local_key = None
    game.enter_local()
    return game, town


@pytest.mark.parametrize("seed", SEEDS)
def test_the_first_town_has_people_money_and_a_shop(tables, seed):
    game, town = a_life(tables, seed)
    folk = [n for n in npcs_in(game.world, town.id) if n.alive]
    assert folk, "the first town you walk into is not empty"
    assert game.leader.money > 0, "you start with something in your purse"
    assert any(economy.shop_spec(game, n) is not None for n in folk), "and somebody will sell you food"


@pytest.mark.parametrize("seed", SEEDS)
def test_there_is_work_in_the_first_town_and_the_map_shows_where(tables, seed):
    game, town = a_life(tables, seed)
    offers = [(n, quests.offer_for(game, n)) for n in npcs_in(game.world, town.id) if n.alive]
    offers = [(n, q) for n, q in offers if q is not None]
    assert offers, "somebody in the first town wants something doing"
    npc, q = offers[0]
    labels = [c.label for c in Conversation(game, npc).menu()]
    assert any("work" in s.lower() for s in labels), f"and you can ask them for it: {labels}"
    quests.accept(game, q)
    assert any(x["id"] == q["id"] for x in game.quests), "taking it puts it in the journal"
    assert quests.title(game, q), "and it has a name"
    assert quests.map_marks(game), "and the map is lit where it wants you"


@pytest.mark.parametrize("seed", SEEDS)
def test_you_can_walk_from_the_town_towards_the_work(tables, seed, monkeypatch):
    monkeypatch.setattr("realmwalker.game.encounters.encounter_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.events.event_chance", lambda *a: 0.0)
    game, town = a_life(tables, seed)
    offers = [q for q in (quests.offer_for(game, n) for n in npcs_in(game.world, town.id) if n.alive)
              if q is not None]
    assert offers
    quests.accept(game, offers[0])
    game.leave_local()
    spot = quests.map_marks(game)[0]
    was = abs(spot[0] - game.player.x) + abs(spot[1] - game.player.y)
    for _ in range(60):
        if game.busy:
            break
        dx = (spot[0] > game.player.x) - (spot[0] < game.player.x)
        dy = (spot[1] > game.player.y) - (spot[1] < game.player.y)
        if (dx, dy) == (0, 0) or not game.move(dx, dy):
            break
    now = abs(spot[0] - game.player.x) + abs(spot[1] - game.player.y)
    assert now < was, f"walking gets you closer to the work ({was} -> {now})"
