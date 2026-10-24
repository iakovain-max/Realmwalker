"""The forge (Expansion 6 A.4, docs/ADVENTURES.md §8.5): a threat and a blueprint become an adventure - places by
selectors, the cast from the world (people of towns never visited bound when the town fills), the hidden truths,
chapters and steps with three routes to every truth, the finale bound to its exact dungeon level - the same way for
the same seed."""

import copy
import json

import pytest

from realmwalker.game.state import new_game
from realmwalker.game.story import cast, forge, places
from realmwalker.world import threats
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Forgeland", 77, "medium"), tables)


@pytest.fixture
def game(tables, made):
    g = new_game(copy.deepcopy(made), tables)
    g.survival = False
    return g


def beast_threats(game):
    out = [t for t in threats.records(game.world).values() if t["kind"] == "beast" and t["state"] != "ended"
           and forge.fitting(game, t)]
    if not out:
        pytest.skip("no beast threat with a tale in this world")
    return out


def test_the_beast_is_forged_with_every_role_and_place_bound(game):
    t = beast_threats(game)[0]
    adv = forge.make(game, t)
    assert adv is not None and t["adventure"] == adv["id"] and t["offer"] is None
    w = game.world
    bp = game.tables.adventures["blueprints"][adv["blueprint"]]
    for name in bp["places"]:
        assert places.exists(w, adv["places"][name]), name
    assert adv["places"]["home"]["site"] == t["home"]["site"]
    for role in bp["cast"]:
        entry = adv["cast"].get(role)
        assert entry, role
        assert cast.pending(entry) or cast.person(w, entry) is not None or "settlement" in entry
    for ch in adv["chapters"]:
        assert ch["title"] and ch["goal"] and ch["steps"]
        for st in ch["steps"]:
            if st["kind"] == "learn":
                assert len(st["target"]["routes"]) >= 3, "every truth has three ways to be learned"
            if "place" in st["target"]:
                assert places.exists(w, st["target"]["place"])
    assert [c["state"] for c in adv["chapters"]][:2] == ["open", "locked"]
    fin = [st for ch in adv["chapters"] for st in ch["steps"] if st["kind"] == "finale"][0]
    assert fin["target"]["level"] in w.politics["story_sites"]
    assert json.loads(json.dumps(adv)) == adv, "records are JSON-native"


def test_the_same_seed_forges_the_same_tale(game, tables, made):
    t = beast_threats(game)[0]
    a = forge.make(game, t)
    other = new_game(copy.deepcopy(made), tables)
    b = forge.make(other, threats.records(other.world)[t["id"]])
    assert a == b


def test_people_of_a_town_never_filled_are_bound_when_it_fills(game):
    from realmwalker.game.people import prepare_town

    t = beast_threats(game)[0]
    adv = forge.make(game, t)
    waiting = {k: v for k, v in game.world.politics.get("story_people", {}).items() if any(r["adv"] == adv["id"]
                                                                                       for r in v)}
    if not waiting:
        pytest.skip("every town of this tale had its people already")
    key = next(iter(waiting))
    s = game.world.settlements[int(key[1:])]
    prepare_town(game, s)
    roles = [r["role"] for r in waiting[key]]
    for role in roles:
        who = cast.person(game.world, adv["cast"][role])
        assert who is not None and who.flags["story"] == {"adv": adv["id"], "role": role}
    assert key not in game.world.politics.get("story_people", {})


def test_a_story_person_is_not_moved_on_with_the_travellers(game):
    t = beast_threats(game)[0]
    adv = forge.make(game, t)
    for role, entry in adv["cast"].items():
        who = cast.person(game.world, entry)
        if who is not None:
            assert who.flags.get("story")
