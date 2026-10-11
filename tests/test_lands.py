"""The land (2026-10-11, Anton: "allow for extremes ... Extremely hot deserts. Inhospitable northern glacial planes.
Epic mountain ranges ... great wonders of the world"): kinds of world and climates, the new lands and the families
they belong to, cliffs and gorges, and the wonders of the world (world/wonders.py)."""

import collections
import copy

import numpy as np
import pytest
import tcod.path

from realmwalker.core.rng import RNG
from realmwalker.game import save, survival
from realmwalker.game.state import GameState, new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import choose_encounter
from realmwalker.world import hydrology, wonders
from realmwalker.world.generator import WorldOptions
from realmwalker.world.local import get_local_map, terrain_remap
from realmwalker.world.model import CLIFF, RAVINE
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402

NEW_LANDS = ("glacier", "steppe", "savanna", "jungle", "dunes", "badlands", "salt_flat", "volcanic", "fey_forest")
KINDS_OF_WORLD = [("continent", "temperate"), ("islands", "warm"), ("twin", "cold"), ("inland_sea", "varied"),
                  ("continent", "scorched"), ("continent", "frozen")]


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def worlds(tables):
    """One world of each lie of the land and each climate."""
    return {(land, climate): cached_world(WorldOptions("Land", 300 + i, "medium", history=40, land=land,
                                                         climate=climate), tables)
            for i, (land, climate) in enumerate(KINDS_OF_WORLD)}


def shares(w) -> tuple[dict[str, float], float]:
    """Each land's share of the dry land, and the dry land's share of the map."""
    water = np.isin(w.biome, [w.biome_ids.index("ocean"), w.biome_ids.index("lake")])
    counts = collections.Counter(w.biome_ids[int(b)] for b in w.biome[~water])
    n = int((~water).sum())
    return {k: v / n for k, v in counts.items()}, n / water.size


def game_at(world, tables, x: int, y: int) -> GameState:
    g = new_game(copy.deepcopy(world), tables, CharacterBuilder(tables, RNG(1, "hero")).build())
    g.survival = False
    g.player.x, g.player.y = x, y
    return g


# ---------------------------------------------------------------------------- the lands
def test_every_land_belongs_to_a_family_the_systems_know(tables):
    B = tables.biomes
    for bid in B.ids:
        family = B.family(bid)
        assert B.family(family) == family, bid
        d = B.defs[B.index[bid]]
        assert d["local"]["ground"] and d["descriptions"], bid
    assert (B.family("jungle"), B.family("dunes"), B.family("glacier"), B.family("steppe")) == \
        ("forest", "desert", "tundra", "plains")
    assert B.lookup({"forest": 1}, "fey_forest") == 1  # nothing of its own: its family's
    forage = tables.camping["forage"]
    assert B.lookup(forage, "jungle")["dc"] < B.lookup(forage, "dunes")["dc"]  # its own entry first
    assert B.lookup(tables.camping["firewood"], "volcanic") == "none"
    assert B.lookup(tables.economy["ride_lands"], "steppe") == 1.0
    assert B.lookup(tables.economy["ride_lands"], "jungle") == 0.0


def test_the_wild_has_its_dangers_in_every_new_land(tables):
    rng = RNG(5, "encounters")
    for bid in NEW_LANDS:
        met = {choose_encounter(tables, bid, 4, night, False, rng) for night in (False, True) for _ in range(20)}
        assert met - {None}, bid


@pytest.mark.slow
def test_each_kind_of_world_looks_like_itself(worlds):
    for (land, climate), w in worlds.items():
        assert (w.meta.land, w.meta.climate) == (land, climate)
    _, continent_land = shares(worlds[("continent", "temperate")])
    _, island_land = shares(worlds[("islands", "warm")])
    assert island_land < continent_land  # more sea
    w = worlds[("islands", "warm")]
    water = np.isin(w.biome, [w.biome_ids.index("ocean"), w.biome_ids.index("lake")])
    _, sizes = hydrology.label_components(~water)
    assert sum(1 for s in sizes if s >= 40) >= 3, "an archipelago has islands"
    frozen, _ = shares(worlds[("continent", "frozen")])
    assert frozen.get("glacier", 0) + frozen.get("tundra", 0) > 0.5
    scorched, _ = shares(worlds[("continent", "scorched")])
    assert scorched.get("desert", 0) + scorched.get("dunes", 0) > 0.15
    assert scorched.get("glacier", 0) < 0.01  # ice only on the highest mountains


def test_an_ordinary_world_still_has_its_extremes(worlds):
    w = worlds[("continent", "temperate")]
    s, _ = shares(w)
    assert s.get("glacier", 0) > 0, "a frozen north"
    assert s.get("desert", 0) + s.get("dunes", 0) > 0.02, "a burning south"
    assert s.get("plains", 0) > 0.08, "and plenty of ordinary country between"
    assert int(w.elevation.max()) >= 6000, "a range that touches the sky"
    peak = next(wd for wd in w.wonders if wd.kind == "great_peak")
    assert int(w.elevation[peak.x, peak.y]) >= 0.95 * int(w.elevation.max())


def test_cliffs_and_gorges(worlds):
    assert any(((w.relief & CLIFF) > 0).any() for w in worlds.values())
    assert any(((w.relief & RAVINE) > 0).any() for w in worlds.values())
    for w in worlds.values():
        gorge = (w.relief & RAVINE) > 0
        assert (w.river[gorge] > 0).all(), "a gorge is cut by a river"


def test_new_lands_are_named_by_the_people_who_live_there(worlds):
    kinds = set()
    for w in worlds.values():
        for a in w.areas:
            assert a.name and "{" not in a.name, a
            kinds.add(a.kind)
    assert {"glacier", "dunes", "jungle", "steppe"} <= kinds


# ---------------------------------------------------------------------------- the wonders
def test_wonders_are_placed_named_and_kept_clear(worlds, tables):
    kinds = collections.Counter()
    for w in worlds.values():
        assert sum(wd.kind == "great_peak" for wd in w.wonders) == 1
        names = [wd.name for wd in w.wonders]
        assert len(names) == len(set(names))
        for wd in w.wonders:
            kinds[wd.kind] += 1
            assert wd.name and "{" not in wd.name, wd
            assert w.wonder_at(wd.x, wd.y) is wd
            assert w.settlement_at(wd.x, wd.y) is None and w.site_at(wd.x, wd.y) is None, wd
    assert sum(wd.flags.get("awake", False) for w in worlds.values() for wd in w.wonders) >= 1
    missing = set(tables.wonders["kinds"]) - set(kinds)
    assert not missing, f"never placed: {missing}"


def test_every_wonder_has_a_close_up_map_you_can_walk_out_of(worlds, tables):
    seen = set()
    for w in worlds.values():
        for wd in w.wonders:
            if wd.kind in seen:
                continue
            seen.add(wd.kind)
            lm = get_local_map(w, tables, wd.x, wd.y)
            assert lm.meta.get("wonder") == wd.id
            walk = tables.terrain.walk[terrain_remap(lm, tables)[lm.terrain]]
            ex, ey = lm.entry
            assert walk[ex, ey], wd.kind
            dist = np.full(walk.shape, 10**6, dtype=np.int32)
            dist[ex, ey] = 0
            tcod.path.dijkstra2d(dist, walk.astype(np.int32), 1, 1, out=dist)
            edge = np.concatenate([dist[0, :], dist[-1, :], dist[:, 0], dist[:, -1]])
            assert (edge < 10**6).any(), f"no way out of {wd.kind}"
    assert seen == set(tables.wonders["kinds"])


def test_finding_a_wonder_is_told_and_rewarded_once(worlds, tables):
    w = worlds[("continent", "temperate")]
    wd = next(x for x in w.wonders if x.kind == "great_peak")
    g = game_at(w, tables, wd.x, wd.y)
    fame, xp = g.renown.fame, g.leader.xp
    before = len(g.log.messages)
    wonders.arrive(g)
    told = " ".join(m.text for m in g.log.messages[before:])
    assert wd.name.removeprefix("the ") in told
    assert g.renown.fame > fame and g.leader.xp > xp
    fame, xp = g.renown.fame, g.leader.xp
    wonders.arrive(g)
    assert (g.renown.fame, g.leader.xp) == (fame, xp)
    assert wd.name.removeprefix("the ") in wonders.describe_line(g, g.world.wonders[wd.id])


def test_the_gifts_of_the_wonders(worlds, tables):
    def find(kind):
        for w in worlds.values():
            for wd in w.wonders:
                if wd.kind == kind:
                    return w, wd
        raise AssertionError(kind)

    w, oasis = find("oasis")
    g = game_at(w, tables, oasis.x, oasis.y)
    assert survival.water_here(g)[0] == "clean"
    w, springs = find("hot_springs")
    g = game_at(w, tables, springs.x, springs.y)
    assert survival.health_context(g, "sleep").healing > 1.0
    assert survival.health_context(g, "walk").healing == 1.0
    assert survival.environment(g, g.leader, "rest").fire
    w, wood = find("enchanted_forest")
    g = game_at(w, tables, wood.x, wood.y)
    assert GameState.lost_dc(g) >= 14  # even on a clear day


def test_wonders_and_the_shape_of_the_land_are_saved(worlds, tables, tmp_path):
    w = worlds[("islands", "warm")]
    save.save_world(w, tmp_path)
    back = save.load_world(tmp_path)
    assert [(wd.kind, wd.name, wd.x, wd.y, wd.flags) for wd in back.wonders] == \
        [(wd.kind, wd.name, wd.x, wd.y, wd.flags) for wd in w.wonders]
    assert (back.relief == w.relief).all()
    assert (back.meta.land, back.meta.climate) == ("islands", "warm")
    assert back.wonder_at(w.wonders[0].x, w.wonders[0].y).name == w.wonders[0].name
