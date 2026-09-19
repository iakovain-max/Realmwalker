"""History and the politics engine (M6 parts 3 and 4): past rulers, wars and plagues, the world moving on while
you play, news travelling along the roads, notice boards and the chronicle."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import news, notices
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.world import factions as fx
from realmwalker.world import history, politics
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.politics import DYNASTIC, Politics
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Chronicleland", 14, "medium"), tables).generate()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    return g


# ---------------------------------------------------------------------------- history
def test_history_is_made_with_the_world(world, tables):
    h = world.history
    assert len(h) > 100
    assert [e["year"] for e in h] == sorted(e["year"] for e in h)
    kinds = {e["kind"] for e in h}
    for needed in ("succession", "war", "plague", "dragon", "legend", "artifact", "ruin"):
        assert needed in kinds, needed
    assert all("{" not in e["text"] for e in h)
    assert world.politics["history_done"]
    assert world.politics["dragons"] and world.politics["artifacts"]


def test_every_line_of_rulers_ends_today(world, tables):
    present = tables.calendar.start_year
    for f in fx.active_factions(world, *DYNASTIC):
        if f.flags.get("minor"):
            continue
        rulers = [world.figures[r] for r in f.rulers]
        assert rulers[-1].id == f.leader and rulers[-1].alive
        past = rulers[:-1]
        assert all(not r.alive and r.died <= present for r in past)
        assert [r.died for r in past] == sorted(r.died for r in past)
    king = fx.active_factions(world, "kingdom")[0]
    assert len(king.rulers) >= 4


def test_conquests_told_agree_with_the_map(world):
    for e in world.history:
        if e["kind"] != "taken" or not e["places"]:
            continue
        s = world.settlements[e["places"][0]]
        winner = world.factions[e["factions"][0]]
        top = fx.realm_of_settlement(world, s)
        assert top is not None and (top.id == winner.id or fx.top_liege(world, winner) is top)


def test_old_worlds_get_a_history(world, tables):
    w = copy.deepcopy(world)
    w.history.clear()
    w.politics.clear()
    assert history.ensure_history(w, tables)
    assert w.history and not history.ensure_history(w, tables)


# ---------------------------------------------------------------------------- the world moves on
def test_the_world_moves_on(world, tables):
    w = copy.deepcopy(world)
    politics.tick(w, tables)
    news_before = len(w.news)
    w.time += 4 * 360 * 1440
    assert politics.tick(w, tables)
    assert len(w.news) > news_before
    for s in w.settlements:
        assert s.owner < 0 or s.owner in w.factions
    for f in fx.active_factions(w):
        leader = fx.leader_of(w, f)
        assert leader is not None and leader.alive, f.name
    for war in w.wars:
        assert war["attacker"] in w.factions and war["defender"] in w.factions


def test_a_king_dies_and_is_succeeded(world, tables):
    w = copy.deepcopy(world)
    k = fx.active_factions(w, "kingdom")[0]
    old = fx.leader_of(w, k)
    engine = Politics(w, tables, RNG(1, "succession"))
    engine.die(old, "of a fever", k)
    new = fx.leader_of(w, k)
    assert not old.alive and new is not old and new.alive
    assert new.title in ("King", "Queen")
    assert any(n["kind"] in ("succession", "crisis") for n in w.news)


def test_a_war_is_fought_and_a_town_changes_hands(world, tables):
    w = copy.deepcopy(world)
    a, d = fx.active_factions(w, "kingdom")[:2]
    engine = Politics(w, tables, RNG(2, "war"))
    war = engine.start_war(a, d, "border")
    war["score"] = 50
    d.military = 1
    engine.sieges(war, a, d, 7)
    siege = war["siege"]
    assert siege is not None
    target = w.settlements[siege["settlement"]]
    assert target.status.get("siege")
    engine.day = siege["until"] + 1
    engine.rng = RNG(3, "win")
    for _ in range(20):
        if war["siege"] is None:
            break
        engine.sieges(war, a, d, 7)
    assert not target.status.get("siege")
    if any(n["kind"] in ("taken", "sacked") for n in w.news):
        assert fx.top_liege(w, fx.owner_of(w, target)) is a
    engine.end_war(war, a)
    assert not war["active"] and fx.relation(w, a.id, d.id) < 0
    assert a.flags["peace_until"][str(d.id)] > engine.day


def test_plague_comes_and_goes(world, tables):
    w = copy.deepcopy(world)
    k = fx.active_factions(w, "kingdom")[0]
    engine = Politics(w, tables, RNG(4, "plague"))
    engine.plague(k)
    sick = [s for s in w.settlements if s.status.get("plague")]
    assert sick
    engine.day += 400
    engine.expire_status()
    assert not any(s.status.get("plague") for s in w.settlements)


def test_troubles_raise_prices(game):
    from realmwalker.game.economy import troubles_factor

    s = game.world.settlements[0]
    assert troubles_factor(game, s, "food") == pytest.approx(troubles_factor(game, s, "food"))
    base = troubles_factor(game, s, "food")
    s.status["siege"] = {"war": 0, "by": -1, "since": 0}
    s.status["famine"] = {"until": 10**6, "since": 0}
    assert troubles_factor(game, s, "food") > base * 3
    assert troubles_factor(game, s, "weapon") > 1.2


# ---------------------------------------------------------------------------- news
def test_news_travels_at_the_pace_of_carters(game):
    w = game.world
    towns = sorted(w.settlements, key=lambda s: s.x)
    a, b = towns[0], towns[-1]
    item = news.add(w, "something happened", a.x, a.y, importance=5)
    assert news.arrived(item, a.x, a.y, news.now_days(w))
    assert not news.arrived(item, b.x, b.y, news.now_days(w))
    days = news.travel_days(a.x, a.y, b.x, b.y)
    assert news.arrived(item, b.x, b.y, news.now_days(w) + days + 0.01)
    small = news.add(w, "a cow died", a.x, a.y, importance=1)
    assert not news.arrived(small, b.x, b.y, news.now_days(w) + 1000)


def test_the_inn_has_news(game):
    w = game.world
    s = next(s for s in w.settlements if s.kind in ("town", "city"))
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    item = news.add(w, "the old queen is dead", s.x, s.y, importance=4)
    keeper = next(n for n in npcs_in(w, s.id) if n.job in ("innkeeper", "guard", "headman"))
    conv = Conversation(game, keeper)
    conv.choose(next(c for c in conv.menu() if c.id == "rumours"))
    assert item["id"] in game.renown.heard
    assert any("old queen" in text for _, text in conv.lines)


def test_the_notice_board(game):
    w = game.world
    s = next(s for s in w.settlements if s.kind in ("town", "city") and fx.realm_of_settlement(w, s))
    realm = fx.realm_of_settlement(w, s)
    game.player.x, game.player.y = s.x, s.y
    lm = game.enter_local()
    item = news.add(w, "war has come", s.x, s.y, kind="war", importance=4)
    game.renown.bounties[realm.id] = 2000
    board = notices.read(game, s)
    kinds = [n["kind"] for n in board]
    assert "wanted" in kinds and "proclamation" in kinds
    assert any(game.leader.name in n["text"] for n in board if n["kind"] == "wanted")
    assert item["id"] in game.renown.heard
    # The board stands in the square; walking into it reads it.
    tid = game.tables.terrain.index["notice_board"]
    cells = [(x, y) for x in range(lm.width) for y in range(lm.height)
             if int(game.remap_for(lm)[lm.terrain[x, y]]) == tid]
    assert cells
    x, y = cells[0]
    game.player.lx, game.player.ly = x - 1, y
    game._move_local(1, 0)
    assert game.read_board


# ---------------------------------------------------------------------------- the chronicle
def test_the_built_in_chronicle(world, tables):
    chron = history.chronicle_fallback(world, tables)
    assert chron["source"] == "fallback" and len(chron["text"]) > 400
    assert str(tables.calendar.start_year) in chron["text"]
    facts = history.chronicle_facts(world, tables)
    assert facts["events"].count("\n") >= 5 and facts["today"]


def test_the_ai_writes_the_chronicle(make_app, mock_p2, tables, world):
    import time

    from realmwalker.ui.screens.chronicle import request_chronicle

    app = make_app(base_url=mock_p2.base_url, ai=True)
    game = new_game(copy.deepcopy(world), app.tables)
    app.start_game(game)
    deadline = time.monotonic() + 10
    while not app.ai.usable() and time.monotonic() < deadline:
        app.update()
        time.sleep(0.05)
    request_chronicle(app, game)
    deadline = time.monotonic() + 15
    while game.world.politics.get("chronicle") is None and time.monotonic() < deadline:
        app.update()
        time.sleep(0.05)
    chron = game.world.politics.get("chronicle")
    assert chron is not None and chron["source"] == "ai" and chron["text"]
