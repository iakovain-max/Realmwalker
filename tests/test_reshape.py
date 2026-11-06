"""Changes to the land while you play (Expansion 6 G.6, docs/ADVENTURES.md §5.21 and §8.16): a ledger of what the
world's great events did to the land (a god's rift, a barrow's blight spreading week by week, a dragon's scorched
fields, a drowned valley, a fallen star's crater), which replays to today's land and can be undone; travel follows it
at once; a close-up map built before the change takes it on entry; and the painted map paints again only the pieces
the change touched, the old pictures standing in."""

import copy
import math
import numpy as np
import pytest
import tcod.console

from realmwalker.game.state import new_game
from realmwalker.world import reshape, threats
from realmwalker.world.local import TREES, get_local_map, patch_land
from realmwalker.world.politics import Politics
from realmwalker.world.tables import Tables
from tests.worlds import cached_world


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    from realmwalker.world.generator import WorldOptions

    return cached_world(WorldOptions("Mapland", 13, "small", history=60), tables)


def _land_spot(w, tables, *, away=(), forest=False, room=4):
    """A square of open land far from towns, sites and the water (and of forest, if asked)."""
    mask = reshape.keep_out(w)
    forests = [i for i, b in enumerate(w.biome_ids) if b in reshape.FORESTS]
    best = None
    for x in range(room, w.width - room):
        for y in range(room, w.height - room):
            if mask[x - 2:x + 3, y - 2:y + 3].any():
                continue
            if forest and int(w.biome[x, y]) not in forests:
                continue
            if any(abs(x - ax) + abs(y - ay) < 6 for ax, ay in away):
                continue
            best = (x, y)
            break
        if best:
            break
    if best is None:
        pytest.skip("no open land in this world")
    return best


def _arrays(w):
    return {f: getattr(w, f).copy() for f in reshape.FIELDS if getattr(w, f, None) is not None}


# ---------------------------------------------------------------------------- the ledger
def test_every_kind_writes_the_ledger_and_the_ledger_replays_and_undoes(made, tables):
    w = copy.deepcopy(made)
    before = _arrays(w)
    used = []
    shapes = {"blight": {"r": 2.5}, "scorch": {"r": 2}, "crater": {"r": 2.5}, "drown": {"n": 18},
              "rift": {"dir": 0.3, "len": 20}, "dead_forest": {"r": 3}}
    for kind, extra in shapes.items():
        x, y = _land_spot(w, tables, away=used, forest=kind == "dead_forest") if kind != "dead_forest" else \
            _land_spot(w, tables, away=used, forest=True)
        used.append((x, y))
        rec = reshape.make(w, kind, {"x": x, "y": y, **extra}, seed=f"test/{kind}", day=1.0)
        assert rec is not None, kind
        assert rec["cells"] and len({(c[0], c[1]) for c in rec["cells"]}) <= reshape.MAX_CELLS
        for cx, cy, field, old, new in rec["cells"]:
            assert w.settlement_grid[cx, cy] < 0 and w.site_grid[cx, cy] < 0
            assert w.biome_ids[int(before["biome"][cx, cy])] not in reshape.WATER
    assert set(reshape.NEW_BIOMES) <= set(w.biome_ids)
    assert reshape.check(w) == []
    v = reshape.version(w)
    assert v == len(shapes)
    # A rift is impassable but for its ledges; the roads it cuts are cut.
    rift = next(r for r in reshape.ledger(w) if r["kind"] == "rift")
    kinds = {w.biome_ids[c[4]] for c in rift["cells"] if c[2] == "biome"}
    assert kinds <= {"rift", "rift_ledge"} and "rift_ledge" in kinds and "rift" in kinds
    # Something else changing an array the ledger owns is found.
    cx, cy = rift["cells"][0][:2]
    w.biome[cx, cy] = before["biome"][cx, cy]
    assert reshape.check(w)
    w.biome[cx, cy] = rift["cells"][0][4]
    # Undone, newest first, the land is as it was; an older change under a newer one is refused first.
    led = reshape.ledger(w)
    for rec in reversed(list(led)):
        assert reshape.undo(w, rec["id"])
    for f, a in before.items():
        assert np.array_equal(a, getattr(w, f)), f
    assert reshape.version(w) == 2 * len(shapes) and not reshape.ledger(w)


def test_a_change_never_falls_on_the_party_or_its_map(made, tables):
    w = copy.deepcopy(made)
    x, y = _land_spot(w, tables)
    w.politics["party_at"] = [x, y]
    rec = reshape.make(w, "scorch", {"x": x, "y": y, "r": 2.5}, seed="test/party", day=1.0)
    assert rec is not None
    assert (x, y) not in {(c[0], c[1]) for c in rec["cells"]}
    assert reshape.make(w, "scorch", {"x": x, "y": y, "r": 0.3}, seed="test/party2", day=1.0, keep=[(x, y)]) is None


def test_changes_since_tells_the_squares_and_says_when_it_cannot(made, tables):
    w = copy.deepcopy(made)
    x, y = _land_spot(w, tables)
    rec = reshape.make(w, "blight", {"x": x, "y": y, "r": 2}, seed="test/since", day=1.0)
    cells, fields = reshape.changes_since(w, 0)
    assert cells == {(c[0], c[1]) for c in rec["cells"]} and fields == {"biome"}
    assert reshape.changes_since(w, reshape.version(w)) == (set(), set())
    w.politics["land_log"] = w.politics["land_log"][-1:]
    w.politics["land_version"] = 5
    w.politics["land_log"][0][0] = 5
    assert reshape.changes_since(w, 1) is None  # (too old to follow: everything is read again)


# ---------------------------------------------------------------------------- the world moving
def test_a_risen_kings_blight_spreads_a_ring_a_week_while_he_walks(made, tables, monkeypatch):
    w = copy.deepcopy(made)
    t = next(iter(threats.records(w).values()), None)
    if t is None:
        pytest.skip("no threat in this world")
    t["state"] = "active"
    monkeypatch.setattr(threats, "villain_lives", lambda world, rec: rec["state"] == "active")
    x, y = _land_spot(w, tables, room=8)
    monkeypatch.setattr(threats, "home_xy", lambda world, rec: (x, y))
    pol = Politics(w, tables, w.rng.child("test"), day=10.0, year=1)
    threats.STAGE_OPS["reshape"](pol, t, "blight", 2, 4)
    first = reshape.ledger(w)[-1]
    assert first["spread"] == {"threat": str(t["id"]), "max": 4.0} and first["story"] == str(t["id"])
    threats.STAGE_OPS["reshape"](pol, t, "blight", 2, 4)  # (once a threat)
    assert len(reshape.ledger(w)) == 1
    assert any(n["text"] for n in w.news[-3:])
    taken = {(c[0], c[1]) for c in first["cells"]}
    grown = reshape.weekly(pol)
    assert len(grown) == 1 and "spread" not in first and grown[0]["spread"]
    ring = {(c[0], c[1]) for c in grown[0]["cells"]}
    assert ring and not ring & taken
    assert all(math.hypot(cx - x, cy - y) > 1.2 for cx, cy in ring)
    t["state"] = "ended"  # (laid: it spreads no more, and what died stays dead)
    assert reshape.weekly(pol) == [] and not any(r.get("spread") for r in reshape.ledger(w))
    assert reshape.check(w) == []


def test_a_dragon_burning_a_village_scorches_its_fields(made, tables):
    w = copy.deepcopy(made)
    lairs = [i for i, s in enumerate(w.sites)
             if any(abs(t.x - s.x) + abs(t.y - s.y) <= 14 for t in w.settlements)]
    if not lairs:
        pytest.skip("no village near a site")
    for seed in range(40):
        pol = Politics(w, tables, w.rng.child(f"dragon/{seed}"), day=10.0 + seed, year=1)
        n = len(reshape.ledger(w))
        pol.dragon_wakes({"name": "Ashwing", "lair": lairs[0]})
        if len(reshape.ledger(w)) > n:
            rec = reshape.ledger(w)[-1]
            assert rec["kind"] == "scorch"
            assert {w.biome_ids[c[4]] for c in rec["cells"]} == {"scorched_land"}
            return
    pytest.skip("the dragon only ever took tribute")


# ---------------------------------------------------------------------------- the game following
def test_travel_and_the_games_caches_follow_a_change(made, tables):
    g = new_game(copy.deepcopy(made), tables)
    g.survival = False
    w = g.world
    px, py = g.player.x, g.player.y
    x, y = _land_spot(w, tables, away=[(px, py)])
    plan = g.plan_travel((x, y))
    if plan is None or len(plan.path) < 6:
        pytest.skip("no journey to make")
    g.travel = plan
    mid = plan.path[len(plan.path) // 2]
    mask = reshape.keep_out(w, keep=[(px, py)])
    if mask[mid]:
        pytest.skip("the middle of the way is kept out")
    before = g.travel_costs().copy()
    rec = reshape.make(w, "crater", {"x": mid[0], "y": mid[1], "r": 2.6}, seed="test/travel", day=1.0,
                       keep=[(px, py)])
    assert rec is not None
    g.land_check()
    costs = g.travel_costs()
    lake = [(c[0], c[1]) for c in rec["cells"] if c[2] == "biome" and w.biome_ids[c[4]] == "lake"]
    assert lake and all(costs[c] == 0 for c in lake) and any(before[c] > 0 for c in lake)
    assert len(g._biome_remap) == len(w.biome_ids)
    assert g.land_key(*lake[0]) == "lake"
    if g.travel is not None:
        assert not set(lake) & set(map(tuple, g.travel.path))
    assert any("land ahead has changed" in m.text for m in g.log.messages[-3:])


def test_a_close_up_map_built_before_takes_the_change(made, tables):
    w = copy.deepcopy(made)
    x, y = _land_spot(w, tables, forest=True)
    lm = get_local_map(w, tables, x, y)
    T = tables.terrain
    t = lambda: np.array(T.ids, dtype=object)[np.array([T.index.get(n, 0) for n in lm.terrain_ids])[lm.terrain]]
    had = np.isin(t(), TREES).sum()
    assert had > 0
    assert not patch_land(w, tables, lm)  # (nothing changed yet)
    rec = reshape.make(w, "blight", {"x": x, "y": y, "r": 1.5}, seed="test/patch", day=1.0)
    assert rec is not None and (x, y) in {(c[0], c[1]) for c in rec["cells"]}
    assert patch_land(w, tables, lm)
    now = t()
    assert not np.isin(now, TREES).any() and (now == "dead_tree").sum() >= had
    assert T.walk[np.array([T.index[n] for n in lm.terrain_ids])[lm.terrain[lm.entry]]]
    assert not patch_land(w, tables, lm)  # (once)
    # A map built after the change is built from the new land, and is not patched again.
    rec2 = reshape.make(w, "rift", {"x": x + 6, "y": y - 6, "dir": 1.57, "len": 14}, seed="test/rift", day=2.0)
    if rec2 is not None:
        ledge = [(c[0], c[1]) for c in rec2["cells"] if c[2] == "biome" and w.biome_ids[c[4]] == "rift_ledge"]
        if ledge:
            lm2 = get_local_map(w, tables, *ledge[0])
            ids = np.array(lm2.terrain_ids, dtype=object)[lm2.terrain]
            assert (ids == "chasm").sum() > 50 and (ids == "ledge").sum() > 0
            assert lm2.meta["land_version"] == reshape.version(w)


# ---------------------------------------------------------------------------- the painted map
def test_the_painter_paints_again_only_what_a_change_touched(made, tables):
    from realmwalker.ui.gfx.paint import ChunkCache, WorldPainter

    w = copy.deepcopy(made)
    painter = WorldPainter(w, tables)
    cache = ChunkCache(painter)
    cache.paint_overview()
    keys = [(gx, gy) for gx in range(cache.cols) for gy in range(cache.rows)]
    x, y = _land_spot(w, tables)
    home = (x // cache.n, y // cache.n)
    im0 = cache.paint_now(home)
    rec = reshape.make(w, "rift", {"x": x, "y": y, "dir": 0.0, "len": 6}, seed="test/paint", day=1.0)
    assert rec is not None
    cells, fields = reshape.changes_since(w, 0)
    touched = cache.refresh(cells, fields, reshape.version(w))
    assert home in touched and len(touched) < len(keys) or len(keys) <= 4
    assert home in cache.stale and not cache.finished
    v0 = cache.overview_v
    cache.catch_up()
    assert cache.overview_v == v0 + 1 and cache.pending is None
    assert painter.rift_segs and np.array_equal(painter.biome, w.biome.astype(np.int64))
    assert cache.get_painted(home) == (im0, 1)  # (the old picture stands in)
    im1 = cache.paint_now(home)
    assert cache.get_painted(home) == (im1, 2) and home not in cache.stale
    assert np.asarray(im1).tobytes() != np.asarray(im0).tobytes()
    cache.close()


def test_the_repaint_is_recorded_headless(make_app):
    from realmwalker.ui.gfx.scene import Image
    from realmwalker.world.generator import WorldOptions

    app = make_app()
    world = cached_world(WorldOptions("Mapland", 13, "small", history=60), app.tables)
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    game.player.explored[:] = True
    app.start_game(game)

    def overview_keys():
        con = tcod.console.Console(160, 50, order="F")
        app.render(con)
        app.update()
        out = []
        for layer in app.last_canvas.layers:
            out += [c.key for c in layer.under + layer.over if isinstance(c, Image) and isinstance(c.key, tuple)
                    and c.key[0] == "map overview"]
        return out

    first = overview_keys()
    assert first and all(k[2] == 0 for k in first)
    w = game.world
    x, y = _land_spot(w, app.tables, away=[(game.player.x, game.player.y)])
    assert reshape.make(w, "scorch", {"x": x, "y": y, "r": 2}, seed="test/headless", day=1.0) is not None
    after = overview_keys()
    assert after and all(k[2] == 1 for k in after)
