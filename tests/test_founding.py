"""Founding (Expansion 6 G.9, docs/ADVENTURES.md §5.21 "New places", §8.16 "Founding"): a besieged city's people
pitch a camp outside its walls on the side away from the besiegers; the camp is a real settlement appended to the
world (named, held by the realm, of its people, a road to the nearest road, in the ledgers), laid out as rows of canvas
tents that work; it goes home in part when the siege lifts, fortifies, and grows into a village, its map laid out
again at the next visit (unless someone the player knows lives there); the world map draws it larger than any town."""

import copy

import numpy as np
import pytest

from realmwalker.core.rng import RNG
from realmwalker.world import factions as fx
from realmwalker.world import founding, news, reshape
from realmwalker.world.generator import WorldOptions
from realmwalker.world.local import LocalBuilder, get_local_map, local_key
from realmwalker.world.politics import Politics
from realmwalker.world.tables import Tables
from tests.test_towns import check_works
from tests.worlds import cached_world


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Threatland", 61, "medium"), tables)


@pytest.fixture
def world(made):
    w = copy.deepcopy(made)
    w.politics["hosts"] = []
    return w


def _pol(world, tables, seed=1):
    return Politics(world, tables, RNG(seed, "founding"), day=news.now_days(world))


def _city(world):
    """A town or city held by a realm, and an enemy realm to besiege it."""
    for s in sorted(world.settlements, key=lambda s: -s.population):
        realm = fx.top_liege(world, world.factions.get(s.owner))
        if s.kind in ("town", "city") and realm is not None and realm.kind in fx.REALM_KINDS:
            enemy = next(f for f in fx.active_factions(world, "kingdom") if f.id != realm.id)
            return s, realm, enemy
    pytest.skip("no town held by a realm")


def _camp(world, tables, monkeypatch):
    target, realm, enemy = _city(world)
    sp = founding.spec(tables)
    monkeypatch.setitem(sp["refugee_camp"], "chance", 1.0)
    pol = _pol(world, tables)
    before = target.population
    s = founding.refugee_camp(pol, target, enemy)
    if s is None:
        pytest.skip("no room for a camp outside it")
    return pol, target, realm, enemy, s, before


def _ledger_holder(world, sid):
    holder = -1
    for e in world.history:
        for i, fid in (e.get("data") or {}).get("owners", ()):
            if i == sid:
                holder = fid
    return holder


def test_a_besieged_city_gets_a_refugee_camp_founded_by_the_checklist(world, tables, monkeypatch):
    n = len(world.settlements)
    pol, target, realm, enemy, s, before = _camp(world, tables, monkeypatch)
    assert s.id == n and world.settlements[-1] is s, "appended at the end, its index its id"
    assert world.settlement_grid[s.x, s.y] == s.id
    assert s.owner == realm.id and _ledger_holder(world, s.id) == realm.id, "held by the realm, in the ledger"
    assert s.culture == target.culture and world.culture_ids[int(world.culture[s.x, s.y])] == target.culture
    assert s.population > 0 and target.population + s.population == before, "its people came out of the city"
    assert 2 <= np.hypot(s.x - target.x, s.y - target.y) <= 3.7 and s.name and s.name != target.name
    assert founding.style_of(world, s) == "encampment" and founding.stage_of(world, s) == 0
    roads = [r for r in reshape.ledger(world) if r["kind"] == "road"]
    near_road = world.road[max(0, s.x - 1):s.x + 2, max(0, s.y - 1):s.y + 2].any()
    assert roads or near_road, "a road to the nearest road"
    assert reshape.check(world) == [] and founding.check(world, tables) == []
    assert any(n["kind"] == "camp_pitched" and s.id in n["places"] for n in world.news)
    assert any(e.get("kind") == "camp_pitched" for e in world.history[-5:]), "the history remembers it"
    assert founding.refugee_camp(pol, target, enemy) is None, "one camp a siege"


def test_the_camp_is_away_from_the_besiegers(world, tables, monkeypatch):
    pol, target, realm, enemy, s, _ = _camp(world, tables, monkeypatch)
    seat = pol.place_of(enemy)
    if seat is None or seat == (target.x, target.y):
        pytest.skip("the enemy has no seat")
    ax, ay = seat[0] - target.x, seat[1] - target.y
    assert (s.x - target.x) * ax + (s.y - target.y) * ay <= 0.3 * np.hypot(ax, ay) * np.hypot(s.x - target.x,
                                                                                               s.y - target.y)


def test_the_camps_map_is_tents_that_work_at_every_stage(world, tables, monkeypatch):
    pol, target, realm, enemy, s, _ = _camp(world, tables, monkeypatch)
    rec = founding.record_of(world, s.id)
    lm = LocalBuilder(world, tables, s.x, s.y).build()
    assert lm.kind == "settlement"
    check_works(lm, tables, "camp")
    tents = [b for b in lm.buildings if (b.look or {}).get("roof") == "canvas"]
    assert len(tents) >= 6 and len(tents) == len(lm.buildings), "a camp of canvas tents"
    kinds = {b.kind for b in lm.buildings}
    assert {"temple", "smithy"} <= kinds, "a chapel tent and a forge"
    T = tables.terrain
    assert (lm.terrain == T.index["standard"]).any() and (lm.terrain == T.index["fire_pit"]).any()
    assert not (lm.terrain == T.index["palisade"]).any(), "no palisade yet"
    founding.set_stage(pol, rec, s, 1)
    lm = LocalBuilder(world, tables, s.x, s.y).build()
    check_works(lm, tables, "fortified camp")
    assert (lm.terrain == T.index["palisade"]).any(), "a palisade round it"
    roofs = {(b.look or {}).get("roof") for b in lm.buildings}
    assert "shingle" in roofs and "canvas" in roofs, "timber halls among the tents"
    founding.set_stage(pol, rec, s, 2)
    assert s.kind == "village" and founding.style_of(world, s) is None
    lm = LocalBuilder(world, tables, s.x, s.y).build()
    check_works(lm, tables, "camp grown a village")
    assert not any((b.look or {}).get("roof") == "canvas" for b in lm.buildings), "built its people's own way"
    assert founding.check(world, tables) == []


def test_the_camp_goes_home_in_part_then_grows_fortifies_and_becomes_a_village(world, tables, monkeypatch):
    pol, target, realm, enemy, s, _ = _camp(world, tables, monkeypatch)
    rec = founding.record_of(world, s.id)
    target.status["siege"] = {"by": enemy.id}
    for _ in range(4):
        pol.day += 7
        founding.weekly(pol)
    assert rec["stage"] == 0 and rec.get("home") is None, "while the siege lasts it waits"
    target.status.pop("siege")
    people = s.population
    pol.day += 7
    founding.weekly(pol)
    assert rec["home"] is not None and s.population < people, "half went home when the siege lifted"
    s.population = max(s.population, 200)
    for _ in range(60):
        pol.day += 7
        founding.weekly(pol)
        assert founding.check(world, tables) == []
    assert rec["stage"] == 2 and s.kind == "village" and s.walled
    kinds = [n["kind"] for n in world.news if s.id in n["places"]]
    assert "camp_home" in kinds and "camp_fortified" in kinds and "camp_grown" in kinds


def test_a_grown_camps_map_is_laid_out_again_at_the_next_visit(make_app, monkeypatch):
    from realmwalker.game import founding as play
    from realmwalker.game.people import npcs_in, prepare_town
    from realmwalker.game.state import new_game

    app = make_app()
    w = copy.deepcopy(cached_world(WorldOptions("Threatland", 61, "medium"), app.tables))
    game = new_game(w, app.tables)
    pol, target, realm, enemy, s, _ = _camp(w, app.tables, monkeypatch)
    rec = founding.record_of(w, s.id)
    prepare_town(game, s)
    lm = w.local_maps[local_key(s.x, s.y)]
    assert lm.meta["founded_stage"] == 0 and npcs_in(w, s.id)
    folk = npcs_in(w, s.id)
    founding.set_stage(pol, rec, s, 1)
    folk[0].flags["story"] = "x"
    assert play.before_entry(game, s.x, s.y) is False, "someone a story is about lives there: the old map stands"
    folk[0].flags.pop("story")
    assert play.before_entry(game, s.x, s.y) is True
    assert all(n.flags.get("moved_on") for n in folk) and s.id not in w.towns
    prepare_town(game, s)
    lm = get_local_map(w, app.tables, s.x, s.y)
    assert lm.meta["founded_stage"] == 1 and (lm.terrain == app.tables.terrain.index["palisade"]).any()
    assert npcs_in(w, s.id) and all(n.alive for n in npcs_in(w, s.id)), "new folk for the fortified camp"


def test_founding_keeps_its_rules(world, tables):
    target, realm, enemy = _city(world)
    pol = _pol(world, tables)
    with pytest.raises(ValueError):
        founding.found(pol, target.x, target.y, kind="refugee_camp", people="heartland", owner=realm.id,
                       population=50)
    gang = next((f for f in world.factions.values() if f.kind not in fx.REALM_KINDS), None)
    spot = founding.spot_near(world, tables, target, rng=pol.rng)
    if gang is not None and spot is not None:
        with pytest.raises(ValueError):
            founding.found(pol, *spot, kind="refugee_camp", people="heartland", owner=gang.id, population=50)
    world.politics["party_at"] = list(spot) if spot else None
    if spot is not None:
        again = founding.spot_near(world, tables, target, rng=pol.rng)
        assert again != spot, "never on the party's square"


def test_the_camp_is_drawn_on_the_world_map_larger_than_any_town(make_app, monkeypatch):
    import tcod.console

    from realmwalker.game.state import new_game
    from realmwalker.ui.gfx import mapsigns
    from realmwalker.ui.gfx.scene import Image
    from realmwalker.ui.gfx.worldview import town_mark
    from realmwalker.ui.screens.world_map import WorldMapScreen

    app = make_app()
    w = copy.deepcopy(cached_world(WorldOptions("Signland", 21, "small", history=60), app.tables))
    game = new_game(w, app.tables)
    game.survival = False
    game.player.explored[:] = True
    pol, target, realm, enemy, s, _ = _camp(w, app.tables, monkeypatch)
    assert town_mark(app.tables, s, "map/hamlet", w) == "map/town_encampment_small"
    assert town_mark(app.tables, s, "map/hamlet") != "map/town_encampment_small", "without the world: as before"
    for st in (0, 1):
        pic = mapsigns.camp_picture(st)
        assert pic.shape == (mapsigns.CAMP_H, mapsigns.CAMP_W, 4) and (pic[..., 3] > 0).sum() > 120
    assert (mapsigns.camp_picture(1)[..., 3] > 0).sum() > (mapsigns.camp_picture(0)[..., 3] > 0).sum()
    app.start_game(game)
    game.player.x, game.player.y = s.x, s.y
    wm = WorldMapScreen(app, app.top)
    app.push(wm)
    wm.target = wm.ppc = 16.0
    con = tcod.console.Console(160, 50, order="F")
    app.render(con)
    app.update()
    app.render(con)
    keys = [c.key for layer in app.last_canvas.layers for c in layer.under + layer.over if isinstance(c, Image)]
    assert ("sign", "camp", 0) in keys, "the camp's picture"
    assert ("sign", "banner") in keys, "its realm's banner"


def test_a_tent_has_its_own_picture():
    from realmwalker.ui.gfx import houses

    assert houses.form_of("rect", "canvas", "house") == "tent"
    pic, glow = houses.draw(5, 4, 16, "canvas", "canvas", "tent", "house", (2, 3), 7, True)
    assert pic.shape[1] == 80 and pic.shape[0] == 64 + houses.extra_top("tent", 16)
    assert (pic[..., 3] > 0).mean() > 0.6 and glow is not None


def test_the_console_pitches_and_grows_a_camp_and_walking_in_works(make_app):
    from realmwalker.game.state import new_game
    from realmwalker.ui.screens.debug_console import DebugConsole

    app = make_app()
    w = copy.deepcopy(cached_world(WorldOptions("Signland", 21, "small", history=60), app.tables))
    game = new_game(w, app.tables)
    game.survival = False
    app.start_game(game)
    n = len(w.settlements)
    console = DebugConsole(app)
    console.run("camp")
    if len(w.settlements) == n:
        pytest.skip("no room for a camp")
    s = w.settlements[-1]
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    assert game.local.kind == "settlement" and game.local.meta["founded_stage"] == 0
    assert any(b.look.get("roof") == "canvas" for b in game.local.buildings)
    console.run("camp grow")
    assert founding.stage_of(w, s) == 1
    game.player.local_key = None  # (out, and in again)
    game.enter_local()
    assert game.local.meta["founded_stage"] == 1, "laid out again for its new stage"
    assert app.error_count == 0
