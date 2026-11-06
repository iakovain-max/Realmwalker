"""Assaults, battles through a living town (Expansion 6 H.1, docs/ADVENTURES.md §5.20, §8.15): the record and its
clock, waves coming in as bands with goals, the fire set, the bands' march through the streets, a band met and fought
as any band is, the leader's fall breaking them, arriving in the middle of one, leaving it, and the abstract end when
nobody is there (through hosts.strike); politics sacks, raids, burns and the hosts' strikes begin one when the party
stands at the town."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import assault, fight, townlife
from realmwalker.game.encounters import LocalActor
from realmwalker.game.state import new_game
from realmwalker.rules.combat import FOE
from realmwalker.world import assaults, hosts, news
from realmwalker.world.generator import WorldOptions
from realmwalker.world.politics import Politics
from realmwalker.world.tables import Tables
from tests.worlds import cached_world


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Lifeland", 33, "small", history=40), tables)


def _town_game(tables, made, kind="town"):
    game = new_game(copy.deepcopy(made), tables)
    game.survival = False
    townlife.forget()
    s = max((s for s in game.world.settlements if s.kind in ("town", "city")), key=lambda s: s.population)
    s.kind = kind
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.world.politics["party_at"] = [s.x, s.y]
    game.enter_local()
    return game, s


def _begin(game, s, kind, ago=0.0):
    w = game.world
    rec = assaults.begin(w, game.tables, s, kind, day=w.time / 1440.0, rng=RNG(7, "assault-test"))
    rec["since"] -= ago / 1440.0
    return rec


def _ticks(game, n):
    for _ in range(n):
        if game.battle is not None or game.busy:
            return
        game.town_tick()


def test_the_data_names_creatures_the_game_has(tables):
    sp = assaults.spec(tables)
    assert set(sp["kinds"]) == set(assaults.KINDS)
    enc = tables.creatures.encounters
    for kind, k in sp["kinds"].items():
        assert k["strike"] in hosts.spec(tables)["strike"], kind
        assert kind in sp["words"]["begin"] and kind in sp["words"]["arrive"]
        assert any(b.get("leader") for w in k["waves"] for b in w["bands"]), kind
        for w in k["waves"]:
            for b in w["bands"]:
                for g in b["group"]:
                    assert g == "$main" or g in enc, (kind, g)
        assert f"host_{k['strike']}_strikes" in tables.politics["text"], kind
        assert k["strike"] in hosts.spec(tables)["names"], kind


def test_a_record_is_made_by_the_town_s_size_and_checks_clean(tables, made):
    w = copy.deepcopy(made)
    small = next(s for s in w.settlements if s.kind in ("hamlet", "village"))
    big = max(w.settlements, key=lambda s: s.population)
    a = assaults.begin(w, tables, small, "raid", day=news.now_days(w), rng=RNG(1, "a"))
    b = assaults.begin(w, tables, big, "raid", day=news.now_days(w), rng=RNG(1, "a"))
    assert a["id"] != b["id"] and assaults.get(w, small.id) is a
    assert assaults.begin(w, tables, small, "sack", day=news.now_days(w), rng=RNG(2, "a")) is a  # (one at a time)
    count = lambda r: sum(len(x["bands"]) for x in r["waves"])
    assert count(b) > count(a)
    assert 60 <= a["clock"] <= 90 and a["fire"]["seeds"] >= 1
    assert not assaults.check(w, tables)


def test_an_assault_nobody_sees_ends_in_the_abstract(tables, made):
    w = copy.deepcopy(made)
    s = next(s for s in w.settlements if s.kind == "village")
    was = s.population
    rec = assaults.begin(w, tables, s, "sack", day=news.now_days(w), rng=RNG(3, "a"), who="the Red Banner")
    assaults.due(w, tables, news.now_days(w) + 0.01, RNG(1, "due"))
    assert assaults.get(w, s.id) is rec  # (its clock has not run out)
    assaults.due(w, tables, assaults.over_at(rec) + 0.01, RNG(1, "due"))
    assert assaults.get(w, s.id) is None
    assert "sacked" in s.status and s.population < was
    assert any(n.get("kind") == "host_sack_strikes" for n in w.news)


def test_politics_and_hosts_begin_an_assault_where_the_party_stands(tables, made):
    w = copy.deepcopy(made)
    w.politics["hosts"] = []
    pol = Politics(w, tables, RNG(5, "p"), day=news.now_days(w))
    village = next(s for s in w.settlements if s.kind == "village" and fx_owned(w, s))
    w.politics["party_at"] = [village.x, village.y]
    tribe = next((f for f in w.factions.values() if f.active and f.kind == "tribe"), None)
    if tribe is not None:
        was = village.population
        pol.raid(tribe, target=village)
        rec = assaults.get(w, village.id)
        assert rec is not None and rec["kind"] == "raid" and village.population == was  # (not yet: it is fought)
        assert "raided" not in village.status
        assaults.records(w).clear()
    host = {"id": "H9", "kind": "the_dead", "faction": -1, "group": "zombies", "strength": 80, "who": "Old Harrow",
            "x": village.x, "y": village.y, "path": [[village.x, village.y]], "at": 0, "goal": {"settlement": village.id},
            "speed": 2, "since": pol.day, "state": "marching"}
    w.politics["hosts"].append(host)
    hosts.strike(w, tables, host, village, day=pol.day, rng=RNG(1, "s"))
    rec = assaults.get(w, village.id)
    assert rec is not None and rec["kind"] == "the_dead" and rec["strike"] == "the_dead" and rec["who"] == "Old Harrow"
    assert "emptied" not in village.status and host not in w.politics["hosts"]
    w.politics["party_at"] = [village.x + 40, village.y + 40]  # (far away: the dead empty it at once)
    other = next(s for s in w.settlements if s.kind == "village" and s.id != village.id)
    hosts.strike(w, tables, dict(host, id="H10"), other, day=pol.day, rng=RNG(1, "s"))
    assert assaults.get(w, other.id) is None and "emptied" in other.status


def fx_owned(w, s):
    from realmwalker.world import factions as fx

    return fx.owner_of(w, s) is not None


def test_waves_come_in_with_goals_set_the_fire_and_march(tables, made):
    game, s = _town_game(tables, made)
    lm = game.local
    rec = _begin(game, s, "raid")
    assault.notice(game, lm)
    assert rec["state"] == "live" and rec["phase"] == "first_wave"
    first = assault.bands(game, lm)
    assert first and all(a.goal is not None for a in first)
    ids = [a.id for a in lm.actors]
    assert len(ids) == len(set(ids))  # (new ids: one past the largest)
    p = game.player
    assert all(max(abs(a.x - p.lx), abs(a.y - p.ly)) >= assault.FAR for a in first)
    goal_band = next(a for a in first if a.goal == "folk")
    start = (goal_band.x, goal_band.y)
    p.lx, p.ly = 1, 1  # (out of their way: this test watches them, it does not fight them)
    while game.battle is None and assaults.minute(game.world, rec) < rec["fire"]["at"] + 1:
        game.town_tick()
    assert game.battle is None
    if goal_band in lm.actors:
        assert (goal_band.x, goal_band.y) != start  # (it went for the townsfolk)
    assert rec["fire"]["since"] is not None and lm.meta.get("fire")  # (the town set alight)
    d = goal_band.to_dict()
    assert LocalActor.from_dict(d).goal == goal_band.goal
    while game.battle is None and assaults.get(game.world, s.id) is not None:
        game.town_tick()
    if game.battle is None:  # (its clock ran out: they go, and the harm is counted)
        assert not assault.bands(game, lm) and not any(a.goal is not None for a in lm.actors)
        assert "raided" in s.status


def test_arriving_in_the_middle_of_one(tables, made):
    game, s = _town_game(tables, made)
    game.leave_local()
    rec = _begin(game, s, "the_dead", ago=40)
    game.enter_local()
    assert rec["state"] == "live"
    assert [w["in"] for w in rec["waves"]] == [True, True, False]
    assert len(assault.bands(game, game.local)) == sum(len(w["bands"]) for w in rec["waves"][:2])
    said = " ".join(m.text for m in game.log.messages[-8:])
    assert "middle of it" in said or "dead" in said
    assert not assaults.check(game.world, game.tables)


def test_a_band_hunting_you_is_fought_and_its_leader_s_fall_breaks_them(tables, made):
    game, s = _town_game(tables, made)
    for c in game.party:
        c.level = max(c.level, 5)
    lm = game.local
    rec = _begin(game, s, "summoned")
    assault.notice(game, lm)
    leader = next(b for w in rec["waves"] for b in w["bands"] if b.get("leader"))
    band = next(a for a in lm.actors if a.id == leader["actor"])
    band.alert, band.goal = True, "you"
    p = game.player
    band.x, band.y = p.lx + 3, p.ly
    _ticks(game, 40)
    assert game.battle is not None and game.battle_actor is band
    b = game.battle
    for f in b.side("party"):
        f.auto = True
    for _ in range(6):  # (a few real rounds, then the rest of them fall)
        if b.outcome is not None:
            break
        b.step()
    for f in b.side(FOE):
        f.state, f.hp = "dead", 0
        if f.creature is not None:
            f.creature.alive = False
    b._check_end()
    assert b.outcome == "victory"
    fight.finish_battle(game)
    game.aftermath = None
    assert band not in lm.actors
    game.town_tick()
    assert assaults.get(game.world, s.id) is None  # (broken: the rest flee, the harm counted)
    assert leader["state"] == "slain" and rec["tally"]["slain"] >= 1
    assert not any(a.goal is not None for a in lm.actors)
    assert any("flee" in m.text or "scatter" in m.text or "run" in m.text for m in game.log.messages[-12:])


def test_leaving_it_lets_it_go_on_and_end_without_you(tables, made):
    game, s = _town_game(tables, made)
    rec = _begin(game, s, "raid")
    assault.notice(game, game.local)
    game.leave_local()
    assert rec["state"] == "coming"
    game.world.politics["party_at"] = [s.x, s.y]
    hosts.advance_world(game.world, game.tables, assaults.over_at(rec) + 0.05)
    assert assaults.get(game.world, s.id) is None and "raided" in s.status
    game.enter_local()  # (they have gone from its streets)
    assert not any(a.goal is not None for a in game.local.actors)
