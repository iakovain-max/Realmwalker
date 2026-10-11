"""Towns (2026-10-11, Anton: "make town generator way more varied ... Dwarven cities now look like human cities
inside a mountain ... Elven cities are human cities made of wood with green woods ... add way, way more variety to
shapes, sizes, and especially looks"): every people builds its own way (data/towns.json, world/towns), and whatever
the plan, the place works: its streets join up, every door can be reached from where you come in, and nothing
inside a building shuts anybody in."""

import collections

import numpy as np
import pytest
import tcod.path

from realmwalker.world import towns
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.local import LocalBuilder
from realmwalker.world.tables import Tables

PASSABLE = ("door_closed", "door_open", "doorway", "gate_open")


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Townland", 21, "small", history=40), tables).generate()


def build_as(world, tables, style: str, kind: str, great: bool = False, walled: bool | None = None):
    """The close-up map of a settlement of this kind, built the way this people builds (on a real settlement's
    square, put back as it was afterwards)."""
    s = max(world.settlements, key=lambda s: s.population)
    old = (s.culture, s.kind, s.great, s.walled)
    s.culture, s.kind, s.great = style, kind, great
    if walled is not None:
        s.walled = walled
    try:
        return LocalBuilder(world, tables, s.x, s.y).build()
    finally:
        s.culture, s.kind, s.great, s.walled = old


def reach_from(lm, tables, start) -> np.ndarray:
    """Every square that can be walked to from `start` (doors count as open), by steps along the sides."""
    T = tables.terrain
    walk = T.walk[lm.terrain].copy()
    for name in PASSABLE:
        walk |= lm.terrain == T.index[name]
    dist = np.full(walk.shape, 10**6, dtype=np.int32)
    dist[start] = 0
    tcod.path.dijkstra2d(dist, walk.astype(np.int32), 1, 0, out=dist)
    return dist < 10**6


def check_works(lm, tables, label: str) -> None:
    T = tables.terrain
    walk = T.walk[lm.terrain]
    ex, ey = lm.entry
    assert walk[ex, ey], f"{label}: you would come in on {T.ids[int(lm.terrain[ex, ey])]}"
    assert lm.building_at(ex, ey) is None, f"{label}: you would come in inside a {lm.building_at(ex, ey).kind}"
    seen = reach_from(lm, tables, (ex, ey))
    edge = np.zeros_like(seen)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    assert (seen & edge).any(), f"{label}: no way out of the map from where you come in"
    for b in lm.buildings:
        assert seen[b.door], f"{label}: the door of a {b.kind} at {b.door} cannot be reached"
        inside = np.zeros_like(seen)
        for x in range(b.x, b.x + b.w):
            for y in range(b.y, b.y + b.h):
                if b.contains(x, y):
                    inside[x, y] = True
        floor = inside & walk
        shut = floor & ~seen
        assert not shut.any(), f"{label}: {int(shut.sum())} squares of a {b.kind} at {b.x},{b.y} are shut off"


STYLES = ("heartland", "highland", "northmarch", "southron", "thalassian", "qasari", "khurgan", "volsk", "itzan",
          "orcish", "halfling")


@pytest.mark.parametrize("style", STYLES)
def test_every_people_builds_villages_and_cities_that_work(world, tables, style):
    for kind in ("village", "city"):
        lm = build_as(world, tables, style, kind)
        assert (lm.width, lm.height) == tuple(tables.towns["sizes"][kind])
        assert len(lm.buildings) >= (6 if kind == "village" else 30), (style, kind, len(lm.buildings))
        check_works(lm, tables, f"{style} {kind}")


def test_hamlets_and_towns_work_too(world, tables):
    for style in ("heartland", "qasari", "khurgan", "northmarch"):
        for kind in ("hamlet", "town"):
            check_works(build_as(world, tables, style, kind), tables, f"{style} {kind}")


def test_a_great_city_is_far_bigger_than_a_city(world, tables):
    city = build_as(world, tables, "southron", "city")
    great = build_as(world, tables, "southron", "city", great=True)
    assert (great.width, great.height) == tuple(tables.towns["sizes"]["great"])
    assert len(great.buildings) >= 1.6 * len(city.buildings)
    check_works(great, tables, "a great southron city")


def test_peoples_build_differently(world, tables):
    """Roofs, walls and shapes: what each people's houses look like."""
    looks = {}
    for style in ("heartland", "qasari", "khurgan", "volsk", "itzan", "halfling", "northmarch"):
        lm = build_as(world, tables, style, "city")
        looks[style] = collections.Counter((b.look.get("roof"), b.look.get("shape")) for b in lm.buildings)
    assert looks["khurgan"].most_common(1)[0][0][1] == "round"  # a camp of round tents
    assert any(roof.startswith("felt") for roof, _ in looks["khurgan"])
    assert any(shape == "court" for _, shape in looks["qasari"])  # houses round a court
    assert any(roof in ("flat", "dome", "dome_blue") for roof, _ in looks["qasari"])
    assert any(roof == "onion" for roof, _ in looks["volsk"])  # the church's onion domes
    assert any(roof == "mound" for roof, _ in looks["halfling"])
    assert any(shape == "long" for _, shape in looks["northmarch"])  # long halls
    assert not set(looks["heartland"]) & set(looks["khurgan"])
    itzan = build_as(world, tables, "itzan", "city")
    assert (itzan.terrain == tables.terrain.index["pyramid"]).any()  # the stepped pyramid on its plaza


def test_a_dwarven_hold_is_cut_in_the_rock_and_lit_by_its_own_fires(world, tables):
    lm = build_as(world, tables, "dwarven", "hold")
    check_works(lm, tables, "a dwarven hold")
    T = tables.terrain
    assert lm.meta.get("underground") and lm.under_rock(lm.width // 2, lm.height // 2)
    assert not lm.under_rock(*lm.entry)  # you come up the road to its gate, under the sky
    assert all(b.shape == "carved" for b in lm.buildings)
    kinds = collections.Counter(b.kind for b in lm.buildings)
    assert kinds["hall"] == 1 and kinds["smithy"] >= 1 and kinds["house"] >= 10
    names = collections.Counter(T.ids[int(t)] for t in lm.terrain.ravel())
    for thing in ("lava", "pillar", "brazier", "statue", "gate_open", "deep_water"):
        assert names[thing], f"a hold without {thing}"
    assert names["rubble"] <= 40  # no pockets of rubble all through the rock
    rock = lm.terrain == T.index["cave_wall"]
    assert rock.mean() < 0.7  # it fills the mountain, not a thin band of it
    seen = reach_from(lm, tables, lm.entry)
    open_floor = T.walk[lm.terrain] & np.array([[lm.under_rock(x, y) for y in range(lm.height)]
                                                for x in range(lm.width)])
    assert (open_floor & seen).sum() >= 0.97 * open_floor.sum()  # every hall and gallery joined to the gate


def test_an_elven_hall_is_homes_in_giant_trees_round_a_moonwell(world, tables):
    lm = build_as(world, tables, "elven", "elfhall")
    check_works(lm, tables, "an elven hall")
    T = tables.terrain
    assert sum(b.shape == "tree" for b in lm.buildings) >= len(lm.buildings) - 1
    assert (lm.terrain == T.index["glow_water"]).any()


def test_towns_are_the_same_every_time(world, tables):
    a = build_as(world, tables, "volsk", "town")
    b = build_as(world, tables, "volsk", "town")
    assert np.array_equal(a.terrain, b.terrain)
    assert [(x.x, x.y, x.kind) for x in a.buildings] == [(x.x, x.y, x.kind) for x in b.buildings]


def test_town_sizes_come_from_the_data(tables, world):
    s = next(s for s in world.settlements if not s.great)
    assert towns.size_of(tables, s) == tuple(tables.towns["sizes"][s.kind])


def test_every_world_has_its_great_cities(tables, world):
    """The biggest city of a world is a great city, many times the size of the rest, with the biggest map."""
    great = [s for s in world.settlements if s.great]
    cities = [s for s in world.settlements if s.kind == "city" and not s.great]
    assert len(great) == tables.towns["great"]["count"][0]  # a small world has one
    assert all(g.kind == "city" for g in great)
    if cities:
        assert min(g.population for g in great) >= 2 * max(c.population for c in cities)
    assert towns.size_of(tables, great[0]) == tuple(tables.towns["sizes"]["great"])


# ---------------------------------------------------------------------------- seen in pictures
def _pictured_town(make_app, world, style: str, kind: str):
    """An app drawing with pictures (no window), a game started, and you standing in a settlement of this kind."""
    import copy

    from realmwalker.game.state import new_game
    from realmwalker.paths import Paths
    from realmwalker.ui.gfx import GfxContext
    from realmwalker.ui.gfx.atlas import Atlas

    app = make_app()
    app.gfx = GfxContext(Atlas(Paths().tiles), 10, 20)
    w = copy.deepcopy(world)
    s = max(w.settlements, key=lambda s: s.population)
    s.kind, s.culture, s.great = kind, style, False
    game = new_game(w, app.tables)
    game.survival = False
    app.start_game(game)
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    return app, game


def _render(app):
    import tcod.console

    con = tcod.console.Console(160, 50, order="F")
    app.render(con)
    app.update()
    assert app.error_count == 0


def test_a_hold_is_lit_the_same_at_noon_and_midnight(make_app, world):
    from realmwalker.game import survival, vision
    from realmwalker.ui.gfx.localview import HOLD

    app, game = _pictured_town(make_app, world, "dwarven", "hold")
    lm = game.local
    T = game.tables.terrain
    walk = T.walk[game.remap_for(lm)[lm.terrain]]
    inside = [(int(x), int(y)) for x, y in np.argwhere(walk) if lm.under_rock(int(x), int(y))
              and lm.building_at(int(x), int(y)) is None]
    game.player.lx, game.player.ly = min(inside, key=lambda c: (c[0] - lm.width // 2) ** 2 + (c[1] - lm.height // 2) ** 2)
    day = game.world.time // 1440
    seen = []
    for hour in (12, 0):
        game.world.time = (day + 1) * 1440 + hour * 60
        _render(app)
        seen.append((tuple(app.top.local_view.base_light), vision.sight_radius(game, lm)))
    assert seen[0] == seen[1], "no sun under the mountain: noon and midnight look the same"
    assert np.allclose(seen[0][0], HOLD)
    assert survival.sheltered(game, "walk"), "no rain falls in the halls"
    game.player.lx, game.player.ly = lm.entry  # out before the gate, under the sky again
    assert not lm.under_rock(*lm.entry) and not survival.sheltered(game, "walk")


def test_lamps_and_braziers_light_a_town_at_night(make_app, world):
    app, game = _pictured_town(make_app, world, "heartland", "city")
    game.world.time = (game.world.time // 1440 + 1) * 1440 + 23 * 60
    _render(app)
    art = app.top.local_view.art
    T = game.tables.terrain
    lm = game.local
    lamps = {(int(x), int(y)) for x, y in np.argwhere(game.remap_for(lm)[lm.terrain] == T.index["lamp_post"])}
    assert lamps, "a city has lamp posts along its streets"
    lit = {(x, y) for x, y, *_ in art.lights}
    assert lamps <= lit, "every lamp post gives light"
    assert float(np.mean(app.top.local_view.base_light)) < 0.75  # (and lights only show in the dark)
