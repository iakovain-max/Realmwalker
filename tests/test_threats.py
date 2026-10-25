"""Threats in the world (Expansion 6 A.3, docs/ADVENTURES.md §5.1): made from the history's named beasts at world
creation, moving week by week with signs before effects, ending in a bounded doom when nobody stops them, ended by the
history's own hunters, woken when a beast comes down, and kept within the budget and the cap near the hero."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.world import news, threats
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


def _weeks(world, tables, n, seed=1):
    for i in range(n):
        world.time += 7 * 1440
        _politics(world, tables, seed + i).advance(7.0)


def _a_beast_stirring(world, tables) -> list:
    """The stirring beasts, stirring one if none is (the world's budget may have gone to the other kinds)."""
    live = [t for t in threats.live(world) if t["kind"] == "beast"]
    if not live:
        dormant = [t for t in threats.records(world).values() if t["kind"] == "beast" and t["state"] == "dormant"]
        if dormant:
            threats.stir(world, tables, dormant[0], RNG(1), day=news.now_days(world))
            live = [dormant[0]]
    return live


def test_threats_are_seeded_from_the_history_s_beasts(made, tables):
    recs = threats.records(made)
    beasts = {int(k) for k, hid in made.politics.get("lairs", {}).items()
              if made.figures[hid].alive and made.figures[hid].kind == "beast"}
    if not beasts:
        pytest.skip("no named beast in this world")
    assert {t["home"]["site"] for t in recs.values() if t["kind"] == "beast"} == beasts
    lo, hi = threats.budget(made, tables)
    assert len(threats.live(made)) <= hi
    for t in recs.values():
        assert t["state"] in threats.STATES
        assert 1 <= t["tier"] <= 4 and t["villain"]["name"]
        assert all(0 <= s < len(made.settlements) for s in t["stakes"])
        if t["state"] in threats.LIVE:
            assert t["scheme"]["stage"] == 0 and t["signs"], "a stirring threat has shown its first sign"


def test_the_same_seed_makes_the_same_threats(made, tables):
    again = cached_world(WorldOptions("Threatland", 61, "medium"), tables)
    assert threats.records(again) == threats.records(made)


def test_signs_come_before_effects_and_an_ignored_threat_reaches_its_doom(world, tables):
    live = _a_beast_stirring(world, tables)  # (the risen and the outlaw: test_threat_kinds)
    if not live:
        pytest.skip("no beast")
    t = live[0]
    t["scheme"]["applied"] = False
    first = list(t["signs"])
    stage_signs = {}
    for _ in range(80):
        before = (t["scheme"]["stage"], t["scheme"]["applied"])
        _weeks(world, tables, 1, seed=len(stage_signs) + 7)
        if t["state"] == "ended":
            break
        if t["scheme"]["stage"] != before[0]:
            stage_signs[t["scheme"]["stage"]] = len(t["signs"])
            assert not t["scheme"]["applied"], "a stage's signs come at least a week before its effects"
    assert t["state"] == "ended" and t["outcome"] in ("doom", "hunted", "slain"), t
    assert len(t["signs"]) > len(first)
    for s in world.settlements:
        assert s.population > 0
    if t["outcome"] == "doom":
        emptied = [s for s in world.settlements if isinstance(s.status.get("emptied"), dict)
                   and s.status["emptied"].get("threat") == t["id"]]
        assert emptied and all(s.population >= 10 for s in emptied)
        assert any(e["kind"] == "emptied" for e in world.history)


def test_a_doom_is_recovered_from(world, tables):
    s = next(s for s in world.settlements if s.kind in ("hamlet", "village"))
    pol = _politics(world, tables)
    t = threats.make(world, tables, RNG(3), "beast", source={"kind": "test"}, home={"settlement": s.id}, day=pol.day)
    t["stakes"] = [s.id]
    was = s.population
    threats.STAGE_OPS["emptied"](pol, t)
    assert s.status["emptied"]["was"] == was and 10 <= s.population < was
    for o in threats.live(world):
        threats.end(world, o, "test", 0)  # (nothing else empties it meanwhile)
    _weeks(world, tables, 16)
    assert "emptied" not in s.status and "rebuilding" in s.status
    assert s.population >= int(was * 0.5)


def test_the_beasts_doom_leaves_a_burned_farmstead(world, tables):
    """B.9: the beast's doom empties the hamlet and leaves it burned (its smoke on the world map, charred houses)."""
    s = next(s for s in world.settlements if s.kind in ("hamlet", "village"))
    pol = _politics(world, tables)
    t = threats.make(world, tables, RNG(5), "beast", source={"kind": "test"}, home={"settlement": s.id}, day=pol.day)
    t["stakes"] = [s.id]
    doom = next(st for st in threats.stages(tables, t) if st.get("doom"))
    for op in doom["effects"]:
        threats.STAGE_OPS[op[0]](pol, t, *op[1:])
    assert "emptied" in s.status and "burned" in s.status


def test_the_owners_still_replay_from_the_ledger_after_a_year_of_threats(world, tables):
    _weeks(world, tables, 52)
    owners = {}
    for e in world.history:
        for sid, fid in (e.get("data") or {}).get("owners", ()):
            owners[sid] = fid
    for s in world.settlements:
        if s.id in owners:
            assert owners[s.id] == s.owner, s.name


def test_a_beast_that_comes_down_wakes_its_threat(world, tables):
    beasts = [t for t in threats.records(world).values() if t["state"] != "ended" and t["kind"] == "beast"]
    if not beasts:
        pytest.skip("no beast")
    t = beasts[0]
    for o in threats.live(world):
        threats.end(world, o, "test", 0)  # (room in the budget)
    t["state"], t["outcome"], t["scheme"]["stage"] = "dormant", None, -1
    pol = _politics(world, tables)
    fig = threats.villain_figure(world, t)
    pol.beast_comes(fig, t["home"]["site"])
    assert t["state"] == "stirring"


def test_the_history_s_hunters_may_end_a_threat(world, tables, monkeypatch):
    live = _a_beast_stirring(world, tables)
    if not live:
        pytest.skip("no beast")
    t = live[0]
    hx, hy = threats.home_xy(world, t)
    hero = next((f for f in world.figures.values() if f.alive and f.role == "hero" and f.kind == "person"), None)
    if hero is None:
        pytest.skip("no hero")
    near = min(world.settlements, key=lambda s: abs(s.x - hx) + abs(s.y - hy))
    hero.home = f"S{near.id}"
    monkeypatch.setitem(tables.threats, "hunters", {"chance": 1.0, "per_fame": 0.0})
    pol = _politics(world, tables)
    threats._hunted(pol, t)
    beast = threats.villain_figure(world, t)
    assert t["state"] == "ended" and t["outcome"] == "hunted" and not beast.alive
    assert str(t["home"]["site"]) not in world.politics["lairs"]
    assert beast.id in hero.kills


def test_only_a_few_untaken_threats_stir_near_the_hero(world, tables):
    live = threats.live(world)
    if not live:
        pytest.skip("nothing stirring")
    x, y = threats.home_xy(world, live[0])
    world.politics.setdefault("director", {})["at"] = [x, y]
    near = tables.threats["near_hero"]
    for i in range(near["untaken"] + 2):
        t = threats.make(world, tables, RNG(i), "beast", source={"kind": "test"}, home=dict(live[0]["home"]), day=0)
        t["villain"]["figure"] = None
        if threats.room_for(world, tables, t):
            threats.stir(world, tables, t, RNG(i), day=0)
    untaken = [t for t in threats.live(world) if threats.distance(world, t, x, y) <= near["tiles"]]
    assert len(untaken) <= max(near["untaken"], len([t for t in live if threats.distance(world, t, x, y)
                                                     <= near["tiles"]]))


def test_the_interlude_moves_a_threat_a_stage_at_most(world, tables):
    from realmwalker.game.interlude import pass_the_years

    live = threats.live(world)
    if not live:
        pytest.skip("nothing stirring")
    before = {t["id"]: t["scheme"]["stage"] for t in live}
    pass_the_years(world, tables, RNG(4), days=150)
    for tid, stage in before.items():
        t = threats.records(world)[tid]
        if t["state"] != "ended":
            assert t["scheme"]["stage"] - stage <= tables.threats["interlude_stages"]
        assert "interlude_moved" not in t
    assert "interlude" not in world.politics


def test_threat_records_are_json_native(made):
    import json

    recs = threats.records(made)
    assert json.loads(json.dumps(recs)) == recs
