"""Grateful companions (design section 12: companions come from "taverns, guilds, freed prisoners, grateful NPCs and
so on"). Someone you free from a dungeon's chains, once the work is handed in, waits at the inn and will travel with
you for their keep."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import companions, quests
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Chains", 12, "medium"), tables)


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables, CharacterBuilder(tables, RNG(4, "hero")).build())
    g.survival = False
    return g


def in_a_town_with_an_inn(game):
    for s in game.world.settlements:
        if s.kind in ("town", "city"):
            game.player.local_key = None
            game.player.x, game.player.y = s.x, s.y
            lm = game.enter_local()
            if any(b.kind == "inn" for b in lm.buildings):
                return s
    raise AssertionError("no town with an inn")


def rescue(s, captive="Mary Tanner"):
    return {"id": 77, "town": s.id, "template": "rescue", "target": {"site": 0, "captive": captive, "sex": "female",
                                                                     "freed": True}}


def test_the_freed_wait_at_the_inn_and_ask_only_for_their_keep(game):
    s = in_a_town_with_an_inn(game)
    said = companions.grateful(game, rescue(s))
    assert said and "Mary is at the inn" in said[0]
    npc = next(n for n in npcs_in(game.world, s.id) if n.name == "Mary Tanner")
    assert npc.flags["grateful"] and npc.sex == "female" and npc.present
    t = companions.terms(game, npc)
    assert t["upfront"] == 0 and t["wage"] == 0 and "keep" in companions.terms_text(game, npc)
    game.leader.money = 0  # no coin needed to take them on
    said = companions.hire(game, npc)
    c = game.party[-1]
    assert c.name == "Mary Tanner" and c.companion["loyalty"] >= 70
    assert "joins you" in said[0]


def test_they_do_not_drift_away_with_the_travellers(game):
    from realmwalker.game.people import refresh_travellers

    s = in_a_town_with_an_inn(game)
    companions.grateful(game, rescue(s))
    npc = next(n for n in npcs_in(game.world, s.id) if n.name == "Mary Tanner")
    game.world.towns[s.id].flags["travellers_day"] = -10**6
    refresh_travellers(game, game.local, s)
    assert npc.alive and not npc.flags.get("moved_on")


def test_handing_in_a_rescue_brings_them(game, monkeypatch):
    s = in_a_town_with_an_inn(game)
    giver = next(n for n in npcs_in(game.world, s.id) if n.alive)
    q = quests.base_quest(game, giver, "rescue", RNG(1, "q"))
    q["target"] = {"site": 0, "captive": "Hal Tanner", "sex": "male", "holder": -1, "freed": True}
    q["words"].update(captive="Hal Tanner", kin="son", site=game.world.sites[0].name, where="north")
    q["state"] = "active"
    game.quests.append(q)
    out = quests.reward(game, q)
    assert any("Hal is at the inn" in line for line in out)
