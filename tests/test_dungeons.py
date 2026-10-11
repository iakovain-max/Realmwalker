"""Dungeons (M8 part 1): levels beneath the sites, stairs, darkness and light, traps, searching, locks, chests and
coffins, inhabitants and bosses, the dragon's hoard, and saving."""

import copy
from collections import deque

import numpy as np
import pytest

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.game import dungeon, save
from realmwalker.game.state import new_game
from realmwalker.rules.inventory import add_item
from realmwalker.world import dungeon as gen
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Deepland", 31, "large"), tables).generate()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    return g


def reachable(tables, lm, start):
    """Cells reachable from start, walking through doors, locked doors and secret doors too."""
    passable = set(i for i, tid in enumerate(lm.terrain_ids)
                   if tables.terrain.walk[tables.terrain.index[tid]] or tid in ("door_closed", "door_locked",
                                                                               "secret_door"))
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if lm.in_bounds(nx, ny) and (nx, ny) not in seen and int(lm.terrain[nx, ny]) in passable:
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


def cells_of(lm, tid):
    if tid not in lm.terrain_ids:
        return []
    return [tuple(int(v) for v in c) for c in np.argwhere(lm.terrain == lm.terrain_ids.index(tid))]


def test_every_site_has_a_dungeon_below(world, tables):
    styles = set()
    for site in world.sites:
        depth = gen.depth_for(world, site)
        for level in range(1, depth + 1):
            lm = gen.DungeonBuilder(world, tables, site, level).build()
            styles.add(lm.meta["style"])
            ups = cells_of(lm, "stairs_up")
            downs = cells_of(lm, "stairs_down")
            assert len(ups) == 1, (site.name, level)
            assert (len(downs) == 1) == (level < depth)
            reach = reachable(tables, lm, ups[0])
            for d in downs:
                assert d in reach, f"{site.name} level {level}: the way down cannot be reached"
            for (x, y), f in lm.features.items():
                if f["kind"] == "chest":
                    neighbours = {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)}
                    assert neighbours & reach, f"{site.name}: an unreachable chest"
    assert {"cave", "crypt", "cellars"} <= styles or len(styles) >= 3


def test_going_down_and_up(game):
    site = next(s for s in game.world.sites if gen.depth_for(game.world, s) >= 2)
    game.player.x, game.player.y = site.x, site.y
    surface = game.enter_local()
    ex, ey = gen.add_entrance(game.tables, surface)
    game.player.lx, game.player.ly = ex - 1, ey
    if not game.tables.terrain.walk[game.remap_for(surface)[surface.terrain[ex - 1, ey]]]:
        game.player.lx, game.player.ly = ex, ey - 1
    game._move_local(ex - game.player.lx, ey - game.player.ly)
    lm = game.local
    assert lm.kind == "dungeon" and lm.meta["level"] == 1
    assert lm.actors, "someone lives down here"
    downs = cells_of(lm, "stairs_down")
    game.player.lx, game.player.ly = downs[0][0], downs[0][1] - 1 if lm.in_bounds(downs[0][0], downs[0][1] - 1) else 0
    dungeon.descend(game, 2)
    assert game.local.meta["level"] == 2
    ups = cells_of(game.local, "stairs_up")
    game.player.lx, game.player.ly = ups[0]
    dungeon.ascend(game)
    assert game.local.meta["level"] == 1
    game.player.lx, game.player.ly = cells_of(game.local, "stairs_up")[0]
    dungeon.ascend(game)
    assert game.local.kind != "dungeon" and game.local.key == f"{site.x},{site.y}"


def test_darkness_and_light(game):
    site = game.world.sites[0]
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    game.party[0].inventory = [it for it in game.party[0].inventory
                               if not game.tables.items.get(it.def_id).get("light")]
    dungeon.descend(game, 1)
    from realmwalker.game.vision import sight_radius

    dark, _ = sight_radius(game, game.local)
    assert dark <= max(1, game.sheet().darkvision // 5)
    add_item(game.leader, game.tables.items, "torch", 2)
    dungeon.light_up(game)
    lit, _ = sight_radius(game, game.local)
    assert lit >= 6 and game.lit["def_id"] == "torch"
    game.pass_time(70)
    assert game.lit is not None and game.lit["hours"] > 0, "a fresh torch was lit"
    assert sum(it.qty for it in game.leader.inventory if it.def_id == "torch") == 0


def fixed_d20(monkeypatch, value):
    class Roll:
        natural = value
        total = value

    monkeypatch.setattr(dice, "d20", lambda *a, **k: Roll())


def test_traps_spring_or_are_spotted(game, monkeypatch):
    site = game.world.sites[0]
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    dungeon.descend(game, 1)
    lm = game.local
    trap = next(((x, y), f) for (x, y), f in lm.features.items() if f["kind"] == "trap")
    (x, y), f = trap
    f["dc"] = 30
    hp = game.leader.hp
    fixed_d20(monkeypatch, 1)
    game.player.lx, game.player.ly = x, y
    dungeon.on_step(game, x, y)
    assert f["spent"] and game.leader.hp < hp
    # A found trap is stepped around.
    f2 = dict(f, spent=False, found=True)
    lm.features[(x, y)] = f2
    hp = game.leader.hp
    dungeon.on_step(game, x, y)
    assert game.leader.hp == hp


def test_searching_finds_hidden_things(game, monkeypatch):
    for site in game.world.sites:
        lm = gen.get_dungeon(game.world, game.tables, site, 1)
        secret = next(((x, y) for (x, y), f in lm.features.items() if f["kind"] == "secret"), None)
        if secret is not None:
            break
    else:
        pytest.skip("no secret doors in this world")
    game.player.x, game.player.y = site.x, site.y
    game.player.local_key = lm.key
    x, y = secret
    game.player.lx, game.player.ly = x, y + 1 if lm.in_bounds(x, y + 1) else y - 1
    fixed_d20(monkeypatch, 20)
    lines = dungeon.search(game)
    assert any("hidden door" in line for line in lines)
    assert lm.terrain_ids[int(lm.terrain[x, y])] == "door_closed"


def test_locks_and_chests(game, monkeypatch):
    site = game.world.sites[0]
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    dungeon.descend(game, 1)
    lm = game.local
    (x, y), f = next(((x, y), f) for (x, y), f in lm.features.items() if f["kind"] == "chest")
    f["locked"] = 15
    add_item(game.leader, game.tables.items, "thieves_tools", 1)
    game.player.lx, game.player.ly = x, y
    fixed_d20(monkeypatch, 1)
    dungeon.open_chest(game, lm, x, y)
    assert not f.get("opened")
    fixed_d20(monkeypatch, 20)
    money = game.leader.money
    dungeon.open_chest(game, lm, x, y)
    assert f["opened"]
    assert game.leader.money > money or lm.items.get((x, y))


def test_coffins_may_hold_the_restless_dead(game, monkeypatch):
    crypt = next((s for s in game.world.sites if gen.style_for(game.world, s) == "crypt"), None)
    if crypt is None:
        pytest.skip("no crypt")
    game.player.x, game.player.y = crypt.x, crypt.y
    lm = gen.get_dungeon(game.world, game.tables, crypt, 1)
    game.player.local_key = lm.key
    (x, y), f = next(((x, y), f) for (x, y), f in lm.features.items() if f.get("grave"))
    f["rouse"] = True
    before = len(lm.actors)
    game.player.lx, game.player.ly = x + 1, y
    dungeon.open_chest(game, lm, x, y)
    assert len(lm.actors) == before + 1 and lm.actors[-1].alert


def test_the_deepest_level_has_its_master(game):
    for site in game.world.sites:
        depth = gen.depth_for(game.world, site)
        style = gen.style_for(game.world, site)
        if style not in dungeon.BOSSES:
            continue
        lm = gen.get_dungeon(game.world, game.tables, site, depth)
        game.player.x, game.player.y = site.x, site.y
        game.player.local_key = lm.key
        dungeon.populate(game, lm)
        assert any(a.group == dungeon.BOSSES[style] for a in lm.actors), (site.name, style)
        return


def test_dungeons_survive_saving(game, tmp_path):
    site = game.world.sites[0]
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    dungeon.descend(game, 1)
    lm = game.local
    save.save_game(game, tmp_path)
    loaded = save.load_game(tmp_path / game.world.meta.id, game.tables)
    again = loaded.world.local_maps[lm.key]
    assert again.kind == "dungeon" and again.meta == lm.meta
    assert set(again.features) == set(lm.features)
    assert loaded.player.local_key == lm.key
    assert (again.terrain == lm.terrain).all()


def test_a_level_describes_itself(game):
    """Each level has built-in words, said once."""
    site = game.world.sites[0]
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    dungeon.descend(game, 1)
    lm = game.local
    assert lm.meta["desc"]
    assert any(lm.meta["desc"] in m.text for m in game.log.messages)
    assert lm.meta["desc_seen"]
    dungeon.descend(game, 1)  # again: not said twice
    said = sum(1 for m in game.log.messages if lm.meta["desc"] in m.text)
    assert said == 1
