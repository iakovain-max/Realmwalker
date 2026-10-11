"""Small fixes (after v1): loose ends found while measuring the game."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import quests
from realmwalker.game.encounters import _one
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.state import new_game
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Loosend", 2, "medium"), tables).generate()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    return g


def test_a_band_that_sees_you_takes_the_right_verb(tables):
    names = {spec["name"] for spec in tables.creatures.encounters.values()}
    assert _one("a lone wolf") and _one("an ogre") and _one("the barrow's lord") and _one("a bandit gang")
    assert not _one("footpads") and not _one("hired thugs") and not _one("the restless dead")
    assert all(isinstance(_one(n), bool) for n in names)


@pytest.mark.slow
def test_every_piece_of_work_leaves_time_for_the_real_walk(game):
    checked = 0
    for s in game.world.settlements[:25]:
        prepare_town(game, s)
        for npc in npcs_in(game.world, s.id):
            if npc.job not in quests.giver_jobs(game):
                continue
            for t, spec in game.tables.quests["templates"].items():
                if npc.job not in spec["givers"]:
                    continue
                q = quests.make_offer(game, npc, RNG(npc.id, t), template=t)
                if q is None or not q["target"]:
                    continue
                tg = q["target"]
                to = (game.world.sites[tg["site"]] if "site" in tg else game.world.settlements[tg["dest"]]
                      if "dest" in tg else quests._Spot(tg["x"], tg["y"]) if "x" in tg else None)
                if to is None:
                    continue
                minutes = quests.walking_minutes(game, s, to)
                if minutes is None:
                    continue
                trips = 1 if t in quests.ONE_WAY else 2
                assert minutes * trips / quests.WALKING_DAY_MINUTES < q["days"], (t, minutes, q["days"])
                checked += 1
    assert checked > 50


def test_a_trap_that_kills_is_named(game):
    from realmwalker.game import dungeon

    site = game.world.sites[0]
    game.player.x, game.player.y = site.x, site.y
    game.player.local_key = None
    game.enter_local()
    dungeon.descend(game, 1)
    lm = game.local
    game.leader.hp = 1
    game.leader.max_hp = 1  # so frail that the darts kill outright (more than a whole life's hit points below nothing)
    trap = {"kind": "trap", "trap": "darts", "dc": 30}
    for c in game.party:
        c.abilities["wis"] = 1  # nobody will spot it
    dungeon.spring(game, lm, game.player.lx, game.player.ly, trap)
    if game.over is None:
        pytest.skip("the darts missed")
    assert game.over["cause"].startswith("killed by"), game.over


def test_a_trap_that_takes_the_last_hit_point_knocks_you_senseless(game):
    """0 hit points from a trap is down, as in a fight, not dead (2026-10)."""
    from realmwalker.game import dungeon

    site = game.world.sites[0]
    game.player.x, game.player.y = site.x, site.y
    game.player.local_key = None
    game.enter_local()
    dungeon.descend(game, 1)
    game.leader.hp = 1
    for c in game.party:
        c.abilities["wis"] = 1
    start = game.world.time
    dungeon.spring(game, game.local, game.player.lx, game.player.ly, {"kind": "trap", "trap": "pit", "dc": 30})
    assert game.over is None and game.leader.alive and game.leader.hp >= 1
    assert game.world.time - start >= 30  # lying senseless


def test_a_chest_of_coins_does_not_end_in_a_space(game, monkeypatch):
    from realmwalker.game import dungeon, treasure

    site = game.world.sites[0]
    game.player.x, game.player.y = site.x, site.y
    game.player.local_key = None
    game.enter_local()
    dungeon.descend(game, 1)
    lm = game.local
    p = game.player
    lm.features[(p.lx + 1, p.ly)] = {"kind": "chest", "treasure": 1}
    monkeypatch.setattr(treasure, "roll", lambda *a, **k: ([], 60))
    dungeon.open_chest(game, lm, p.lx + 1, p.ly)
    text = game.log.messages[-1].text
    assert "6 sp" in text and not text.endswith(" ")
