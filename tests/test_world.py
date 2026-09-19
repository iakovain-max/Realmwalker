"""World generation, local maps and the calendar."""

import time
from collections import deque

import numpy as np
import pytest

from realmwalker.world.calendar import duration_text
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.local import LocalBuilder, get_local_map
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Testmark", 101, "small"), tables).generate()


def test_same_seed_same_world(tables):
    a = WorldGenerator(WorldOptions("A", 7, "small"), tables).generate()
    b = WorldGenerator(WorldOptions("A", 7, "small"), tables).generate()
    for name, arr in a.arrays().items():
        assert np.array_equal(arr, b.arrays()[name]), name
    assert [s.name for s in a.settlements] == [s.name for s in b.settlements]
    c = WorldGenerator(WorldOptions("A", 8, "small"), tables).generate()
    assert not np.array_equal(a.elevation, c.elevation)


def test_large_world_is_quick(tables):
    start = time.monotonic()
    WorldGenerator(WorldOptions("Big", 5, "large"), tables).generate()
    assert time.monotonic() - start < 30


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_biome_mix_is_sensible(tables, seed):
    w = WorldGenerator(WorldOptions("Mix", seed, "medium"), tables).generate()
    B = tables.biomes.index
    land = w.biome != B["ocean"]
    frac = {bid: float(((w.biome == i) & land).sum() / land.sum()) for bid, i in B.items()}
    assert 0.3 < land.mean() < 0.8
    assert frac["plains"] + frac["coast"] > 0.12
    assert frac["forest"] + frac["pine_forest"] > 0.10
    assert 0.03 < frac["mountains"] + frac["high_mountains"] < 0.25
    assert frac["lake"] > 0


def test_rivers_run_to_water(world, tables):
    B = tables.biomes.index
    water = np.isin(world.biome, [B["ocean"], B["lake"]])
    xs, ys = np.nonzero(world.river)
    assert len(xs) > 20
    for x, y in zip(xs.tolist(), ys.tolist()):
        seen = set()
        while not water[x, y]:
            assert (x, y) not in seen, "river loops back on itself"
            seen.add((x, y))
            nxt = world.downstream(x, y)
            if nxt is None:
                break  # drains off the map edge
            x, y = nxt
            assert len(seen) < 2000


def test_settlements_on_open_land_and_unique(world, tables):
    positions = set()
    for s in world.settlements:
        assert tables.biomes.passable[world.biome[s.x, s.y]], s
        assert (s.x, s.y) not in positions
        positions.add((s.x, s.y))
        assert world.settlement_at(s.x, s.y) is s
        assert s.name and s.population > 0
    kinds = {s.kind for s in world.settlements}
    assert {"city", "town", "village", "hamlet"} <= kinds


def test_roads_join_most_towns(world):
    main = [s for s in world.settlements if s.kind in ("city", "town", "village")]
    start = main[0]
    seen = {(start.x, start.y)}
    queue = deque(seen)
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if world.in_bounds(nx, ny) and world.road[nx, ny] and (nx, ny) not in seen:
                seen.add((nx, ny))
                queue.append((nx, ny))
    connected = sum(1 for s in main if (s.x, s.y) in seen)
    assert connected >= 0.8 * len(main)


def test_named_areas(world):
    assert any(a.kind == "river" for a in world.areas)
    for a in world.areas:
        assert a.name and not a.name.startswith("The ")
        assert world.in_bounds(a.x, a.y)


def test_local_maps_are_deterministic_and_enterable(world, tables):
    walk = tables.terrain.walk
    samples = [(s.x, s.y) for s in world.settlements[:6]]
    samples += [tuple(int(v) for v in p) for p in np.argwhere(world.river > 0)[:3]]
    samples += [(s.x, s.y) for s in world.sites[:3]]
    for x, y in samples:
        a = LocalBuilder(world, tables, x, y).build()
        b = LocalBuilder(world, tables, x, y).build()
        assert np.array_equal(a.terrain, b.terrain)
        ex, ey = a.entry
        assert walk[a.terrain[ex, ey]], (x, y)
    town = next(s for s in world.settlements if s.kind in ("town", "city"))
    lm = get_local_map(world, tables, town.x, town.y)
    assert lm.kind == "settlement" and len(lm.buildings) >= 5
    door = tables.terrain.index["door_closed"]
    for b in lm.buildings:
        assert lm.terrain[b.door] == door
    assert get_local_map(world, tables, town.x, town.y) is lm  # kept once generated


def test_calendar(tables):
    cal = tables.calendar
    t = cal.minutes_for(1047, 4, 15, 12, 30)
    m = cal.at(t)
    assert (m.year, m.month.name, m.day, m.hour, m.minute) == (1047, "Highsun", 15, 12, 30)
    summer = cal.at(cal.minutes_for(1047, 5, 1, 12)).daylight_hours(0.3)
    winter = cal.at(cal.minutes_for(1047, 11, 1, 12)).daylight_hours(0.3)
    assert summer > 14 and winter < 10
    assert cal.at(cal.minutes_for(1047, 1, 1, 12)).light() == 1.0
    assert cal.at(cal.minutes_for(1047, 1, 1, 0)).light() < 0.2
    assert duration_text(60 * 24 * 2 + 125) == "2 days 2 hours"
    assert duration_text(45) == "45 minutes"
