"""Hosts on the map (Expansion 6 G.7, docs/ADVENTURES.md §5.21, §8.16): an army marches to the town it will besiege
and the siege begins when it gets there; a tribe's warband rides out and raids where it arrives; the dead of a risen
king march on a village and empty it, and a crusade may go to meet them; a horde with no war behind it besets a town;
refugees take to the roads from a ruined town and swell the town they reach; bands are met near a host; a faction
with only a host in the field is heard of where its host is; the hosts are drawn on the world map; the stamp keeps the
daily and the weekly steps in step."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.world import factions as fx
from realmwalker.world import hosts, news, threats
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
    w = copy.deepcopy(made)
    w.politics["hosts"] = []
    return w


def _pol(world, tables, seed=1, day=None):
    return Politics(world, tables, RNG(seed, "hosts"), day=news.now_days(world) if day is None else day)


def _march(pol, days=60, step=1.0):
    """Days pass, a day at a time: every host on the road moves on (checked each day)."""
    for _ in range(int(days / step)):
        pol.day += step
        hosts.advance(pol, days=step)
        assert hosts.check(pol.w, pol.t) == []


def _apart(world, a_kind=("village", "town"), least=6):
    """Two settlements a few days apart by road."""
    for s in world.settlements:
        if s.kind not in a_kind:
            continue
        for t in world.settlements:
            d = abs(s.x - t.x) + abs(s.y - t.y)
            if t is not s and least <= d <= 25:
                return s, t
    pytest.skip("no two places apart")


def test_an_army_marches_to_its_siege_and_the_siege_begins_when_it_arrives(world, tables):
    kingdoms = fx.active_factions(world, "kingdom")
    a = kingdoms[0]
    d = max(kingdoms[1:], key=lambda k: (len(fx.holdings(world, k, deep=True)), -k.id))
    pol = _pol(world, tables)
    war = pol.start_war(a, d, "border")
    war["score"] = 75
    d.military = 1
    pol.sieges(war, a, d, 7)
    if war.get("siege") is not None:
        pytest.skip("the army mustered at the walls")
    h = hosts.get(world, war["march"])
    assert h is not None and h["kind"] == "army" and h["faction"] == a.id and h["war"] == war["id"]
    target = world.settlements[h["goal"]["settlement"]]
    assert h["path"][-1] == [target.x, target.y] and not target.status.get("siege")
    assert any(n["kind"] == "host_marches" for n in world.news), "the march is news: a siege is seen coming"
    pol.sieges(war, a, d, 7)
    assert war.get("siege") is None, "no siege while the army is on the road"
    start = (h["x"], h["y"])
    pol.day += 1
    hosts.advance(pol, days=1)
    assert (h["x"], h["y"]) != start and [h["x"], h["y"]] in h["path"], "it moved along its road"
    _march(pol, 60)
    assert hosts.get(world, h["id"]) is None and war["march"] is None
    assert war["siege"] is not None and war["siege"]["settlement"] == target.id
    assert target.status["siege"]["by"] == a.id


def test_an_army_goes_home_when_its_war_ends(world, tables):
    kingdoms = fx.active_factions(world, "kingdom")
    a, d = kingdoms[0], max(kingdoms[1:], key=lambda k: len(fx.holdings(world, k, deep=True)))
    pol = _pol(world, tables, 2)
    war = pol.start_war(a, d, "border")
    war["score"] = 75
    pol.sieges(war, a, d, 7)
    if war.get("march") is None:
        pytest.skip("the army mustered at the walls")
    hid = war["march"]
    pol.end_war(war, None)
    pol.day += 1
    hosts.advance(pol, days=1)
    assert hosts.get(world, hid) is None and hosts.check(world, tables) == []


def test_a_warband_rides_out_and_raids_where_it_arrives(world, tables):
    pol = _pol(world, tables, 3)
    rode = None
    for tribe in fx.active_factions(world, "tribe"):
        before = len(hosts.records(world))
        pol.raid(tribe, ride=True)
        if len(hosts.records(world)) > before:
            rode = hosts.records(world)[-1]
            break
    if rode is None:
        pytest.skip("no tribe rides far enough to be seen")
    assert rode["kind"] == "warband"
    s = world.settlements[rode["goal"]["settlement"]]
    assert "raided" not in s.status, "the raid falls when the warband gets there"
    _march(pol, 30)
    assert hosts.get(world, rode["id"]) is None and s.status.get("raided")


def _risen_marching(world, tables):
    t = next((t for t in sorted(threats.records(world).values(), key=lambda t: int(t["id"][1:]))
              if t["kind"] == "risen"), None)
    if t is None:
        pytest.skip("no risen")
    t["state"] = "active"
    hx, hy = threats.home_xy(world, t)
    t["stakes"] = [s.id for s in sorted(world.settlements, key=lambda s: abs(s.x - hx) + abs(s.y - hy))
                   if s.kind in ("hamlet", "village") and abs(s.x - hx) + abs(s.y - hy) >= 4][:3]
    return t


def test_the_dead_march_on_a_village_and_empty_it_and_its_people_flee(world, tables):
    t = _risen_marching(world, tables)
    pol = _pol(world, tables, 4)
    threats.STAGE_OPS["host"](pol, t, "the_dead", "village", "haunted")
    dead = next((h for h in hosts.records(world) if h["kind"] == "the_dead"), None)
    if dead is None:
        assert any((s.status.get("emptied") or {}).get("threat") == t["id"] for s in world.settlements), \
            "no road: emptied at once, as before"
        return
    assert dead["threat"] == t["id"] and dead["who"] == threats.villain_name(world, t)
    s = world.settlements[dead["goal"]["settlement"]]
    was = s.population
    for c in [h for h in hosts.records(world) if h["kind"] == "crusade"]:
        hosts.records(world).remove(c)  # (this test is about the dead alone)
    threats.STAGE_OPS["host"](pol, t, "the_dead", "village", "haunted")
    assert len([h for h in hosts.records(world) if h["kind"] == "the_dead"]) == 1, "its dead march once"
    _march(pol, 60)
    assert (s.status.get("emptied") or {}).get("threat") == t["id"] and "haunted" in s.status
    assert 10 <= s.population < was
    fled = [n for n in world.news if n["kind"] == "host_refugees_flee"]
    if fled:
        _march(pol, 30)
        assert any(n["kind"] == "host_refugees_arrive" for n in world.news), "the refugees come somewhere"


def test_the_dead_go_back_to_the_earth_when_their_king_is_laid(world, tables):
    t = _risen_marching(world, tables)
    pol = _pol(world, tables, 5)
    dead = hosts.the_dead_march(pol, t, world.settlements[t["stakes"][0]], ("haunted",))
    if dead is None:
        pytest.skip("no road")
    threats.end(world, t, "laid", pol.day)
    _march(pol, 1)
    assert hosts.get(world, dead["id"]) is None


def test_a_crusade_holds_a_town_against_the_dead(world, tables):
    t = _risen_marching(world, tables)
    a, b = _apart(world)
    pol = _pol(world, tables, 6)
    guard = hosts.raise_host(world, tables, "crusade", (a.x, a.y), b.id, day=pol.day, faction=next(iter(world.factions)),
                             strength=100000)
    if guard is None:
        pytest.skip("no road")
    _march(pol, 20)
    assert guard["state"] == "holding" and any(n["kind"] == "host_crusade_arrives" for n in world.news)
    dead = hosts.raise_host(world, tables, "the_dead", (a.x, a.y), b.id, day=pol.day, threat=t["id"], strength=1,
                            who="the Barrow King")
    was = b.population
    _march(pol, 20)
    assert hosts.get(world, dead["id"]) is None and b.population == was and "emptied" not in b.status
    assert any(n["kind"] == "host_crusade_holds" for n in world.news)
    _march(pol, 40)
    assert hosts.get(world, guard["id"]) is None, "a crusade holds a town a month, then goes home"


def test_a_horde_with_no_war_besets_a_town_and_sends_its_people_on_the_road(world, tables):
    a, b = _apart(world, ("town", "village"))
    pol = _pol(world, tables, 7)
    b.population = max(b.population, 400)
    h = hosts.raise_host(world, tables, "horde", (a.x, a.y), b.id, day=pol.day, strength=300, who="the Red Hand")
    if h is None:
        pytest.skip("no road")
    was = b.population
    _march(pol, 20)
    assert b.status.get("beset") and b.status["beset"]["until"] > pol.day and b.population < was
    assert any(n["kind"] == "host_horde_strikes" for n in world.news)
    column = [x for x in hosts.records(world) if x["kind"] == "refugees" and x["came_from"] == b.id]
    if column:
        to = world.settlements[column[0]["goal"]["settlement"]]
        before = to.population
        people = column[0]["people"]
        _march(pol, 30)
        assert to.population >= before + people


def test_a_faction_with_only_a_host_is_heard_of_where_its_host_is(world, tables):
    a, b = _apart(world)
    f = next(iter(world.factions.values()))
    f.seat, f.site, f.area = -1, -1, -1
    f.flags.pop("coast", None)
    assert news.faction_place(world, f) is None
    h = hosts.raise_host(world, tables, "crusade", (a.x, a.y), b.id, day=0.0, faction=f.id, strength=50)
    if h is None:
        pytest.skip("no road")
    assert news.faction_place(world, f) == (a.x, a.y)


def test_the_daily_and_weekly_steps_keep_in_step(world, tables):
    a, b = _apart(world)
    pol = _pol(world, tables, 8)
    world.politics["hosts_tick"] = pol.day
    h = hosts.raise_host(world, tables, "army", (a.x, a.y), b.id, day=pol.day, strength=50)
    if h is None or len(h["path"]) < 6:
        pytest.skip("no road")
    hosts.advance_world(world, tables, pol.day + 1)  # (a day: game/story.daily)
    at = h["at"]
    assert at == pytest.approx(h["speed"])
    hosts.advance_world(world, tables, pol.day + 1)  # (the same day again: nothing)
    assert h["at"] == at
    late = _pol(world, tables, 9, day=pol.day + 0.5)  # (a weekly step whose day is behind the stamp: nothing)
    hosts.advance(late)
    assert h["at"] == at


def test_bands_are_met_near_a_host(world, tables, monkeypatch):
    from realmwalker.game import encounters
    from realmwalker.game.state import new_game

    g = new_game(world, tables)
    g.survival = False
    w = g.world
    p = g.player
    w.politics["hosts"] = []
    x, y = p.x, p.y
    while w.settlement_at(x, y) is not None:
        x += 1
    p.x, p.y = x, y
    goal = min(w.settlements, key=lambda s: abs(s.x - x) + abs(s.y - y))
    h = hosts.raise_host(w, tables, "army", (x, y), goal.id, day=0.0, strength=200)
    if h is None:
        pytest.skip("no road")
    monkeypatch.setattr(encounters, "encounter_chance", lambda *a, **k: 1.0)
    groups = set()
    for i in range(20):
        w.time += 37
        enc = encounters.roll_encounter(g, 60)
        if enc is not None:
            groups.add(enc.group)
    assert "army_foragers" in groups


def test_hosts_are_drawn_on_the_world_map(make_app):
    import tcod.console

    from realmwalker.game.state import new_game
    from realmwalker.ui.gfx.scene import Image
    from realmwalker.ui.screens.world_map import WorldMapScreen

    app = make_app()
    w = copy.deepcopy(cached_world(WorldOptions("Signland", 21, "small", history=60), app.tables))
    game = new_game(w, app.tables)
    game.survival = False
    game.player.explored[:] = True
    app.start_game(game)
    p = game.player
    near = sorted(w.settlements, key=lambda s: abs(s.x - p.x) + abs(s.y - p.y))
    w.politics["hosts"] = []
    made = [hosts.raise_host(w, app.tables, kind, (near[0].x, near[0].y), near[1].id, day=0.0, faction=f, strength=200)
            for kind, f in (("army", next(iter(w.factions))), ("refugees", -1))]
    if None in made:
        pytest.skip("no road")
    for h in made:
        h["at"] = min(1.0, len(h["path"]) - 1)
        h["x"], h["y"] = h["path"][int(h["at"])]
    wm = WorldMapScreen(app, app.top)
    app.push(wm)
    wm.target = wm.ppc = 16.0
    con = tcod.console.Console(160, 50, order="F")
    app.render(con)
    app.update()
    app.render(con)
    keys = [c.key for layer in app.last_canvas.layers for c in layer.under + layer.over if isinstance(c, Image)]
    assert ("sign", "banner") in keys, "the army's banner"
    assert sum(1 for k in keys if isinstance(k, tuple) and k[:2] == ("sign", "puff")) >= 3, "and its dust"
