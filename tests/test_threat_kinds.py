"""The risen and the outlaw lord as threats (Expansion 6 D.1, docs/ADVENTURES.md §5.1, §6.2): made from the barrows
of the history's dead (at least two levels deep) and from the active gangs; their schemes show themselves as marks on
places (haunted, robbed roads, a town paying the gang) and as bands met on the land (the dead on the road at night,
the gang's toll); their dooms are bounded; the world ends them too (priests lay the dead, politics hangs gangs), and a
new captain takes a dead one's place."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.world import dungeon, news, threats
from realmwalker.world import factions as fx
from realmwalker.world.generator import WorldOptions
from realmwalker.world.politics import Politics
from realmwalker.world.tables import Tables
from tests.worlds import cached_world


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Threatland", 61, "medium"), tables)


@pytest.fixture
def world(made):
    return copy.deepcopy(made)


def _politics(world, tables, seed=1):
    return Politics(world, tables, RNG(seed), day=news.now_days(world))


def _of(world, kind):
    return [t for t in sorted(threats.records(world).values(), key=lambda t: int(t["id"][1:])) if t["kind"] == kind]


def _apply(pol, t, stage_id):
    st = next(s for s in threats.stages(pol.t, t) if s["id"] == stage_id)
    for op in st.get("effects", []):
        threats.STAGE_OPS[op[0]](pol, t, *op[1:])


def test_the_risen_come_from_deep_barrows_and_the_outlaw_lords_from_living_gangs(made, tables):
    risen = _of(made, "risen")
    deep = {site.id for site, _ in threats.risen_sources(made)}
    assert deep, "this world's history left a barrow two levels deep"
    assert {t["home"]["site"] for t in risen} == deep
    for t in risen:
        site = made.sites[t["home"]["site"]]
        assert site.kind == "barrow" and dungeon.depth_for(made, site) >= 2
        assert made.politics["tombs"][str(site.id)] == t["villain"]["figure"]
        assert not made.figures[t["villain"]["figure"]].alive and threats.villain_lives(made, t)
        assert t["villain"]["creature"] == "wight" and t["tier"] >= 2, "a wight is no tale for a first-level band"
        assert t["source"]["scar"] is None or 0 <= t["source"]["scar"] < len(made.politics["scars"])
    outlaws = _of(made, "outlaw")
    gangs = {g.id for g, _ in threats.gang_sources(made)}
    assert gangs and {t["source"]["faction"] for t in outlaws} == gangs
    for t in outlaws:
        gang = threats.gang_of(made, t)
        assert t["home"]["site"] == gang.site and fx.leader_of(made, gang).id == t["villain"]["figure"]
        assert t["villain"]["creature"] == "bandit_captain"


def test_the_risen_scheme_haunts_then_empties_a_hamlet_then_a_village(world, tables):
    t = _of(world, "risen")[0]
    pol = _politics(world, tables)
    t["stakes"] = [s.id for s in world.settlements if s.kind in ("hamlet", "village")][:4] + t["stakes"]
    _apply(pol, t, "walking")
    first = world.settlements[t["stakes"][0]]
    assert first.status["haunted"]["threat"] == t["id"]
    _apply(pol, t, "emptying")
    emptied = [s for s in world.settlements if (s.status.get("emptied") or {}).get("threat") == t["id"]]
    assert len(emptied) == 1
    _apply(pol, t, "march")
    again = [s for s in world.settlements if (s.status.get("emptied") or {}).get("threat") == t["id"]]
    assert len(again) == 2, "the doom empties another place, not the same one twice"
    held = [s for s in again if s not in emptied][0]
    assert "haunted" in held.status, "the doom's village is held by the dead"
    assert all(s.population >= 10 for s in world.settlements)
    assert any(e["kind"] == "emptied" for e in world.history)


def test_the_outlaw_lords_doom_is_a_town_paying_his_band_until_it_falls(world, tables):
    t = _of(world, "outlaw")[0]
    gang = threats.gang_of(world, t)
    pol = _politics(world, tables)
    if not t["stakes"]:
        t["stakes"] = [min(world.settlements, key=lambda s: abs(s.x - t["reach"]["x"]) + abs(s.y - t["reach"]["y"])).id]
    _apply(pol, t, "bleeding")
    s = world.settlements[t["stakes"][0]]
    assert "bled" in s.status
    men = gang.military
    _apply(pol, t, "tribute")
    assert s.status["extorted"]["by"] == gang.id and gang.military > men
    assert any(e["kind"] == "extorted" for e in world.history)
    pol.hang_gang(gang)
    if gang.active:
        pol.fall(gang)  # (no lord to hang them here: the band breaks all the same)
    threats._recover(pol)
    assert "extorted" not in s.status, "a town paying a fallen band pays nobody"


def test_a_band_that_falls_ends_its_outlaw_lord_and_a_new_captain_takes_his_place(world, tables):
    t = _of(world, "outlaw")[0]
    gang = threats.gang_of(world, t)
    pol = _politics(world, tables)
    old = fx.leader_of(world, gang)
    new = pol.new_leader(gang)
    pol.crown(gang, new)
    old.died = pol.year
    threats.settle(world, pol.day)
    assert t["state"] != "ended" and t["villain"]["figure"] == new.id and new.full_name() == t["villain"]["name"]
    pol.fall(gang)
    threats.settle(world, pol.day)
    assert t["state"] == "ended" and t["outcome"] == "fallen"


def test_a_new_gang_makes_an_outlaw_lord(world, tables):
    pol = _politics(world, tables, seed=9)
    before = len(_of(world, "outlaw"))
    gangs = len(fx.active_factions(world, "bandit_gang"))
    for i in range(6):
        pol.new_gang()
        if len(fx.active_factions(world, "bandit_gang")) > gangs:
            break
    if len(fx.active_factions(world, "bandit_gang")) == gangs:
        pytest.skip("no place left for a new gang")
    made = _of(world, "outlaw")
    assert len(made) == before + 1 and made[-1]["source"]["faction"] == fx.active_factions(world, "bandit_gang")[-1].id


def test_the_risen_are_laid_by_the_hero_or_by_the_world(world, tables, monkeypatch):
    a, b = _of(world, "risen")[:2]
    world.politics.setdefault("laid", {})[str(a["home"]["site"])] = 1
    threats.settle(world, 0)
    assert a["state"] == "ended" and a["outcome"] == "laid"
    pol = _politics(world, tables)
    threats.stir(world, tables, b, RNG(2), day=pol.day)
    monkeypatch.setitem(tables.threats["kinds"]["risen"]["ends"], "chance", 1.0)
    threats._ends_alone(pol, b)
    assert b["state"] == "ended" and b["outcome"] == "laid"
    assert str(b["home"]["site"]) in world.politics["laid"]
    assert any(n["kind"] == "threat_laid" for n in world.news)


def test_an_ignored_risen_or_outlaw_threat_reaches_its_doom_and_the_world_stays_whole(world, tables):
    for t in threats.live(world):
        threats.end(world, t, "test", 0)
    for kind in ("risen", "outlaw"):
        t = _of(world, kind)[-1]
        threats.stir(world, tables, t, RNG(4), day=news.now_days(world))
    for i in range(70):
        world.time += 7 * 1440
        _politics(world, tables, 30 + i).advance(7.0)
    for kind in ("risen", "outlaw"):
        t = _of(world, kind)[-1]
        assert t["state"] == "ended" and t["outcome"], t
    assert all(s.population > 0 for s in world.settlements)


def test_the_dead_walk_the_roads_by_night_and_the_gang_takes_its_toll(made, tables, monkeypatch):
    from realmwalker.game import encounters
    from realmwalker.game.state import new_game

    game = new_game(copy.deepcopy(made), tables)
    game.survival = False
    w = game.world
    for t in threats.live(w):
        threats.end(w, t, "test", 0)
    t = _of(w, "risen")[0]
    pol = _politics(w, tables)
    threats.stir(w, tables, t, RNG(1), day=pol.day)
    threats._begin_stage(w, tables, t, 1, RNG(1), pol.day)  # (the dead walk)
    t["scheme"]["applied"] = True
    x, y = threats.home_xy(w, t)
    spot = next((i, j) for i in range(x - 3, x + 4) for j in range(y - 3, y + 4)
                if w.in_bounds(i, j) and w.settlement_at(i, j) is None and w.site_at(i, j) is None)
    game.player.x, game.player.y = spot
    assert threats.on_the_road(w, tables, *spot, night=False) is None, "the dead walk by night"
    assert threats.on_the_road(w, tables, *spot, night=True)[0] is t
    monkeypatch.setattr(game.__class__, "light", property(lambda self: 0.1))
    monkeypatch.setattr(encounters, "encounter_chance", lambda *a, **k: 1.0)
    met = []
    for i in range(30):
        w.time += 60
        met.append(encounters.roll_encounter(game, 60))
    dead = [m for m in met if m is not None and m.group == "restless_dead"]
    assert dead and any(threats.villain_name(w, t) in m.intro or threats.home_name(w, t) in m.intro or
                        "dead" in m.intro.lower() for m in dead)
    threats.end(w, t, "test", 0)
    o = _of(w, "outlaw")[0]
    threats.stir(w, tables, o, RNG(1), day=pol.day)
    o["scheme"]["applied"] = True
    x, y = threats.home_xy(w, o)
    road = threats.on_the_road(w, tables, x, y, night=False)
    assert road is not None and road[0] is o and road[1]["group"] in tables.creatures.encounters
    words = threats.road_words(w, o, road[1], RNG(3))
    assert "{" not in words
