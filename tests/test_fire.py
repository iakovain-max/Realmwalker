"""Fire on close-up maps (Expansion 6 B.7, docs/ADVENTURES.md §8.14; game/fire.py): spread stops at stone and water;
nobody ever stands on a burning square; a town marked burning has buildings alight and its people keep away; a battle
in a burning street burns and writes back; a Fireball in an ordinary inn starts no blaze; burned squares are patched in
the map's art square by square; the town mends; under a millisecond a step on a great city."""

import copy
import time

import numpy as np
import pytest

from realmwalker.game import fight, fire, townlife
from realmwalker.game.dungeon import set_terrain
from realmwalker.game.encounters import make_encounter
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.rules.combat import FOE
from realmwalker.world import marks
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.test_townlife import go_to
from tests.worlds import cached_world


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Lifeland", 33, "small", history=40), tables)


def _game(made, tables, **kw):
    game = new_game(copy.deepcopy(made), tables)
    game.survival = False
    townlife.forget()
    s = go_to(game, **kw)
    return game, s, game.local


def _clear(game, lm, x0, y0, w, h, ground="cobbles"):
    """A patch of the map laid bare (and nobody standing in it), for a fire to be set in."""
    for x in range(x0, x0 + w):
        for y in range(y0, y0 + h):
            set_terrain(lm, x, y, ground)
    s = game.world.settlement_at(game.player.x, game.player.y)
    for n in npcs_in(game.world, s.id):
        if x0 - 1 <= n.x <= x0 + w and y0 - 1 <= n.y <= y0 + h:
            n.x, n.y = lm.entry
    lm.actors.clear()
    if x0 - 1 <= game.player.lx <= x0 + w and y0 - 1 <= game.player.ly <= y0 + h:
        game.player.lx, game.player.ly = lm.entry
    game._remaps.pop(lm.key, None)
    townlife.forget()


def _corner(lm, w=16, h=7):
    ex, ey = lm.entry
    x0 = 2 if ex > lm.width // 2 else lm.width - w - 2
    y0 = 2 if ey > lm.height // 2 else lm.height - h - 2
    return x0, y0


def _burn_for(game, lm, steps):
    for _ in range(steps):
        game.world.time += 0  # (the steps are the fire's own)
        fire.tick(game, lm)
    fire.flush(game, lm)


def test_spread_stops_at_stone_and_water(made, tables):
    game, s, lm = _game(made, tables)
    x0, y0 = _corner(lm)
    _clear(game, lm, x0 - 1, y0 - 1, 18, 9)
    for x in range(x0, x0 + 16):  # a strip of dry grass, cut by a stone wall and by water
        for y in range(y0, y0 + 7):
            set_terrain(lm, x, y, "dry_grass")
    for y in range(y0, y0 + 7):
        set_terrain(lm, x0 + 5, y, "wall_stone")
        set_terrain(lm, x0 + 10, y, "shallow_water")
        set_terrain(lm, x0 + 11, y, "shallow_water")
    fire._weather.clear()
    fire._weather[int(game.world.time) // 10] = (1.0, 0.0, 0.3, 0.0)  # (a dry day, a light wind)
    assert fire.light(game, lm, [(x0, y0 + 3)]) == 1
    _burn_for(game, lm, 300)
    T = lambda x, y: lm.terrain_ids[int(lm.terrain[x, y])]  # noqa: E731
    left = [T(x, y) for x in range(x0, x0 + 5) for y in range(y0, y0 + 7)]
    beyond = [T(x, y) for x in range(x0 + 6, x0 + 16) for y in range(y0, y0 + 7) if x not in (x0 + 10, x0 + 11)]
    assert left.count("scorched") > 25, "the grass burned"
    assert "scorched" not in beyond, "stone stopped it"
    assert T(x0 + 5, y0) == "wall_stone" and T(x0 + 10, y0) == "shallow_water"
    assert not lm.meta.get("fire"), "it burned out"
    assert all(rec[2] == "dry_grass" for rec in lm.meta["burnt"]), "what burned is remembered"
    # Wet weather, no wind: the same grass hardly catches (rain slows it).
    fire._weather.clear()
    fire._weather[int(game.world.time) // 10] = (1.0, 0.0, 0.0, 1.0)
    for x in range(x0, x0 + 5):
        for y in range(y0, y0 + 7):
            set_terrain(lm, x, y, "grass")
    fire._mats.clear()
    fire.light(game, lm, [(x0, y0 + 3)])
    _burn_for(game, lm, 300)
    wet = [T(x, y) for x in range(x0, x0 + 5) for y in range(y0, y0 + 7)].count("scorched")
    fire._weather.clear()
    assert wet < 25


def test_nobody_ever_stands_on_a_burning_square(made, tables):
    game, s, lm = _game(made, tables)
    marks.add(game.world, s, "burning", game.world.time / 1440.0, tables)
    game.player.local_key = None
    game.enter_local()
    lm = game.local
    assert lm.meta.get("fire"), "a burning town has buildings alight when you walk in"
    folk = [n for n in npcs_in(game.world, s.id) if n.alive and n.present]
    lit_at_start = len(lm.meta["fire"])
    for _ in range(150):
        townlife.tick(game, lm, s)
        burning = set(lm.meta.get("fire") or {})
        on = [n for n in folk if f"{n.x},{n.y}" in burning]
        assert not on, f"{len(on)} townsfolk on burning squares"
        assert f"{game.player.lx},{game.player.ly}" not in burning
        assert not any(f"{a.x},{a.y}" in burning for a in lm.actors)
    assert lm.meta.get("burnt") or len(lm.meta.get("fire") or {}) != lit_at_start, "it burned on"
    # Your own way is barred by it.
    k = next(iter(lm.meta.get("fire") or {}), None)
    if k is not None:
        x, y = (int(v) for v in k.split(","))
        for dx, dy in fire.NEIGHBOURS:
            if lm.in_bounds(x - dx, y - dy) and game.tables.terrain.walk[game.remap_for(lm)[lm.terrain[x - dx, y - dy]]] \
                    and not fire.burning(lm, x - dx, y - dy):
                game.player.lx, game.player.ly = x - dx, y - dy
                assert game._move_local(dx, dy) is False
                assert (game.player.lx, game.player.ly) == (x - dx, y - dy)
                break


def test_townsfolk_keep_away_from_a_burning_building(made, tables):
    game, s, lm = _game(made, tables)
    i, b = next((i, b) for i, b in enumerate(lm.buildings) if b.kind == "house" and b.w >= 4 and b.h >= 4)
    inside = [(x, y) for x in range(b.x + 1, b.x + b.w - 1) for y in range(b.y + 1, b.y + b.h - 1) if b.contains(x, y)]
    fire.light(game, lm, inside[:2])
    assert i in fire.alight_buildings(lm)
    town = townlife.town_for(game, lm)
    for n in [n for n in npcs_in(game.world, s.id) if n.alive][:30]:
        n.home = n.post = inside[0]
        g = townlife.goal(game, lm, n, town)
        assert not fire.unsafe(lm, g), "they make for the open, not their burning home"


def _street_battle(game):
    enc = make_encounter(game, "bandits", game.world.rng.child("street"))
    return fight.start_battle(game, enc.creatures, enc.intro, title="Bandits")


def test_a_battle_in_a_burning_street_burns_and_writes_back(made, tables):
    game, s, lm = _game(made, tables)
    px, py = game.player.lx, game.player.ly
    ring = [(px + dx, py + dy) for dx in range(-6, 7) for dy in range(-5, 6) if max(abs(dx), abs(dy)) >= 4]
    ring = [c for c in ring if lm.in_bounds(*c)]
    for x, y in ring:  # a street of straw and timber, burning at its end
        set_terrain(lm, x, y, "haystack" if (x + y) % 3 == 0 else "floor_wood")
    game._remaps.pop(lm.key, None)
    fire._mats.clear()
    townlife.forget()
    lit = fire.light(game, lm, [c for c in ring if max(abs(c[0] - px), abs(c[1] - py)) >= 5][:12],
                     taken={(px, py)})
    assert lit > 0
    battle = _street_battle(game)
    z = fire._fire_zone(battle)
    assert z is not None and z.owner is None and z.rounds < 0, "the burning squares are ownerless fire"
    assert battle.round_hooks, "and it spreads round by round"
    assert battle.field.__dict__.get("burning") and battle.field.flammable.any()
    assert any(zz.kind == "smoke" for zz in battle.zones)
    before = set(z.cells)
    for _ in range(8):
        for hook in list(battle.round_hooks):
            hook(battle)
    scorched = battle.t.terrain.index["scorched"]
    assert (battle.field.terrain == scorched).any(), "squares burned out on the field"
    assert z.cells != before or not z.cells
    taken = {c for f in battle.fighters if f.active for c in f.cells}
    assert not taken & z.cells, "the fire never lights a square someone stands on"
    for f in battle.fighters:
        if f.side == FOE:
            f.hp, f.state = 0, "dead"
    battle.outcome = "victory"
    fight.finish_battle(game)
    burnt = {(int(r[0]), int(r[1])) for r in lm.meta.get("burnt", [])}
    assert any(lm.terrain_ids[int(lm.terrain[x, y])] == "scorched" for x, y in burnt), "written back to the map"


def test_a_fireball_in_an_ordinary_inn_starts_no_blaze(made, tables):
    game, s, lm = _game(made, tables)
    b = next(b for b in lm.buildings if b.kind == "inn")
    cells = [(x, y) for x in range(b.x + 1, b.x + b.w - 1) for y in range(b.y + 1, b.y + b.h - 1)
             if b.contains(x, y) and game.tables.terrain.walk[game.remap_for(lm)[lm.terrain[x, y]]]]
    game.player.lx, game.player.ly = cells[len(cells) // 2]
    battle = _street_battle(game)
    assert not battle.round_hooks and fire._fire_zone(battle) is None
    ox, oy = battle.field.origin
    area = [(x - ox, y - oy) for x, y in cells if battle.field.in_bounds(x - ox, y - oy)]
    me = next(f for f in battle.fighters if f.char is game.leader)
    n = len(battle.zones)
    battle._ignite(me, area)  # (what fire damage landing on the floor does)
    assert len(battle.zones) == n, "floorboards, tables and benches do not catch in an ordinary fight"
    battle.outcome = "victory"
    for f in battle.fighters:
        if f.side == FOE:
            f.hp, f.state = 0, "dead"
    fight.finish_battle(game)
    assert not lm.meta.get("fire")


def test_burned_squares_are_patched_in_the_art(made, tables):
    from realmwalker.ui.gfx import headless
    from realmwalker.ui.gfx.localview import LocalArt, LocalView

    game, s, lm = _game(made, tables)
    atlas = headless().atlas
    view = LocalView()
    art = view.art_for(game, lm, atlas)
    i, b = next((i, b) for i, b in enumerate(lm.buildings) if b.kind == "house" and b.w >= 4)
    cells = [(x, y) for x in range(b.x, b.x + b.w) for y in range(b.y, b.y + b.h) if b.contains(x, y)]
    fire.light(game, lm, cells, taken=set())
    for rec in lm.meta["fire"].values():
        rec[0] = 3
    written = fire.flush(game, lm)
    assert written
    again = view.art_for(game, lm, atlas)
    assert again is art, "patched, not made again"
    fresh = LocalArt(game, lm, atlas)
    for x, y in written:
        assert (art.WALL[x, y], art.O[x, y], art.V[x, y]) == (fresh.WALL[x, y], fresh.O[x, y], fresh.V[x, y])
        assert (art.G[x, y] >= 0) == (fresh.G[x, y] >= 0)
    assert fire.shell(lm, i) and lm.buildings[i].look.get("roof") == "none", "burned through: a shell"
    from realmwalker.game import placemarks

    assert placemarks.shut(lm, i), "no trade in a burnt shell"


def test_the_town_mends(made, tables):
    game, s, lm = _game(made, tables)
    i, b = next((i, b) for i, b in enumerate(lm.buildings) if b.kind == "house" and b.w >= 4)
    cells = [(x, y) for x in range(b.x, b.x + b.w) for y in range(b.y, b.y + b.h) if b.contains(x, y)]
    before = {c: lm.terrain_ids[int(lm.terrain[c])] for c in cells}
    look = dict(b.look or {})
    fire.light(game, lm, cells, taken=set())
    for rec in lm.meta["fire"].values():
        rec[0] = 3
    fire.flush(game, lm)
    game.world.time += int(fire.COOL_DAYS * 1440) + 10
    fire.mend(game, lm, s)
    assert "embers" not in {lm.terrain_ids[int(lm.terrain[c])] for c in cells}, "the embers have gone cold"
    game.world.time += fire.MEND_DAYS * 1440
    fire.mend(game, lm, s)
    assert {c: lm.terrain_ids[int(lm.terrain[c])] for c in cells} == before, "built again as it was"
    assert (b.look or {}) == look and not lm.meta.get("burnt") and not fire.shell(lm, i)


def test_fire_burns_out_at_once_in_the_wild(made, tables):
    game, s, lm = _game(made, tables)
    game.player.local_key = None
    game.player.x, game.player.y = next((x, y) for x in range(game.world.width) for y in range(game.world.height)
                                        if game.world.settlement_at(x, y) is None and game.world.site_at(x, y) is None
                                        and game.biome_key(x, y) in ("grassland", "plains", "forest", "steppe"))
    lm = game.enter_local()
    cells = [(x, y) for x in range(lm.width) for y in range(lm.height) if fire.burns(game, lm, x, y)][:20]
    if not cells:
        pytest.skip("nothing burns here")
    fire.light(game, lm, cells, taken=set())
    fire.tick(game, lm)
    assert not lm.meta.get("fire")
    assert all(lm.terrain_ids[int(lm.terrain[c])] in ("scorched", "embers") for c in cells)


def test_a_step_of_fire_on_a_great_city_is_quick(made, tables):
    game, s, lm = _game(made, tables, kind="city", great=True)
    houses = [b for b in lm.buildings if b.kind == "house"][:30]
    seeds = [(x, y) for b in houses for x in range(b.x, b.x + b.w) for y in range(b.y, b.y + b.h) if b.contains(x, y)]
    fire.light(game, lm, seeds, taken=set())
    n = len(lm.meta.get("fire") or {})
    assert n > 200, "a great fire: thirty houses alight"
    times = []
    for _ in range(30):  # (three batches of burned-out squares among them)
        t0 = time.perf_counter()
        fire.tick(game, lm)
        times.append(time.perf_counter() - t0)
    times.sort()
    each, worst = times[len(times) // 2], times[-1]
    print(f"a step of fire with {n} burning squares: {each * 1000:.2f} ms, at worst {worst * 1000:.2f} ms")
    assert each < 0.001 * max(1.0, n / 300), f"{each * 1000:.2f} ms a step"
    assert worst < 0.02, "a batch written never stalls the town"


def test_a_burning_town_is_drawn(made, tables):
    from realmwalker.ui.gfx import headless
    from realmwalker.ui.gfx.localview import LocalView
    from realmwalker.ui.gfx.scene import Sprite
    from realmwalker.ui.widgets import Canvas

    game, s, lm = _game(made, tables)
    marks.add(game.world, s, "burning", game.world.time / 1440.0, tables)
    game.player.local_key = None
    game.enter_local()
    lm = game.local
    lm.seen[:] = True
    import tcod.console

    gfx = headless()
    canvas = Canvas(tcod.console.Console(160, 50, order="F"), gfx=gfx)
    fov = np.ones((lm.width, lm.height), bool)
    view = LocalView()
    k = next(iter(lm.meta["fire"]))
    game.player.lx, game.player.ly = (int(v) for v in k.split(","))
    game.player.lx += 2
    view.draw(canvas, game, (0, 0, 1600, 1000), 32, fov)
    sprites = [c for layer in canvas.layers for c in layer.under + layer.over if isinstance(c, Sprite)]
    blaze = set(gfx.atlas.family("fx/blaze"))
    assert any(c.name in blaze for c in sprites), "flames on the burning squares"
    from realmwalker.ui.gfx import atmosfx

    assert atmosfx.choose(game, lm) in ("embers", "red_sky")
    atmosfx.draw(canvas, (0, 0, 1600, 1000), game, 1.0)
