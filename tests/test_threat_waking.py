"""Waking dormant threats (Expansion 6 G.2, docs/ADVENTURES.md §5.1): a sleeping threat stirs when something happens
near it (a battle or a plague by a barrow, a famine round a lair, a town sacked near a hideout), when the hero robs
its barrow or walks into its lair, when the Storyteller needs one near a hero with nothing to take on, or slowly by
chance; every Politics method that can make a threat calls `seed_from`; the interlude says what woke, grew and ended;
and the world ends each kind by itself (priests, a lord's great hunt, a lord's riders)."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import dungeon, story
from realmwalker.game.interlude import pass_the_years
from realmwalker.game.state import new_game
from realmwalker.game.story import beats
from realmwalker.world import dungeon as gen
from realmwalker.world import factions as fx
from realmwalker.world import news, threats
from realmwalker.world.generator import WorldOptions
from realmwalker.world.politics import Politics
from realmwalker.world.tables import Tables
from tests.worlds import cached_world

pytestmark = pytest.mark.story


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


def _sleeping(world, kind):
    out = [t for t in sorted(threats.records(world).values(), key=lambda t: int(t["id"][1:]))
           if t["kind"] == kind and threats.villain_lives(world, t)]
    for t in out:
        t["state"] = "dormant"
        t["scheme"]["stage"] = -1
    if not out:
        pytest.skip(f"no {kind} in this world")
    return out


def _quiet(world, but=()):
    """Every other threat ended, so that the world's budget has room."""
    for t in threats.records(world).values():
        if t["id"] not in but:
            t["state"] = "ended"


def _certain(tables, monkeypatch, why):
    spec = dict(tables.threats["triggers"][why], chance=1.0)
    monkeypatch.setitem(tables.threats["triggers"], why, spec)


def test_a_battle_near_a_barrow_wakes_its_dead_and_one_far_away_does_not(world, tables, monkeypatch):
    t = _sleeping(world, "risen")[0]
    _quiet(world, but={t["id"]})
    _certain(tables, monkeypatch, "battle")
    pol = _politics(world, tables)
    hx, hy = threats.home_xy(world, t)
    far = max(world.settlements, key=lambda s: threats.distance(world, t, s.x, s.y))
    assert threats.distance(world, t, far.x, far.y) > t["reach"]["r"]
    assert threats.trigger(pol, "battle", [(far.x, far.y)]) == []
    assert t["state"] == "dormant"
    assert threats.trigger(pol, "battle", [(hx + 2, hy)]) == [t]
    assert t["state"] == "stirring" and t["woke"]["why"] == "battle"
    assert t["signs"], "its first sign is on the roads at once"
    assert threats.trigger(pol, "battle", [(hx, hy)]) == [], "a threat wakes once"


def test_a_trigger_only_wakes_the_kinds_it_touches_and_minds_the_budget(world, tables, monkeypatch):
    t = _sleeping(world, "risen")[0]
    _certain(tables, monkeypatch, "raid")
    pol = _politics(world, tables)
    assert "risen" not in tables.threats["triggers"]["raid"]["kinds"]
    assert threats.trigger(pol, "raid", [threats.home_xy(world, t)]) == [], "a raid is no business of the dead"
    _certain(tables, monkeypatch, "plague")
    lo, hi = threats.budget(world, tables)
    others = [o for o in threats.records(world).values() if o["id"] != t["id"]][:hi]
    for o in others:
        o["state"] = "active"
    assert len(threats.live(world)) >= hi
    assert threats.trigger(pol, "plague", [threats.home_xy(world, t)]) == [], "no room in the world"
    assert t["state"] == "dormant"


def test_the_politics_engine_fires_its_triggers_and_seeds(world, tables, monkeypatch):
    calls, seeds = [], []
    monkeypatch.setattr(threats, "trigger", lambda pol, why, points, site=None: calls.append(why) or [])
    real = threats.seed_from
    monkeypatch.setattr(threats, "seed_from", lambda pol, kind, **refs: seeds.append(kind) or real(pol, kind, **refs))
    pol = _politics(world, tables)
    realm = next(r for r in pol.powers() if r.kind != "tribe" and fx.holdings(world, r, deep=True))
    pol.plague(realm)
    pol.famine(realm)
    tribes = fx.active_factions(world, "tribe")
    for tribe in tribes:
        pol.raid(tribe)
    for d in world.politics.get("dragons", []):
        if d.get("alive"):
            pol.dragon_wakes(d)
            break
    assert {"plague", "famine"} <= set(calls)
    assert "sickness" in seeds, "a plague may make the sickness (its kind comes later: nothing happens yet)"
    assert real(pol, "sickness", faction=realm) is None
    if tribes and "raid" in calls:
        assert "warband" in seeds


def test_seed_from_finds_a_threat_by_its_faction_and_wakes_it(world, tables):
    t = _sleeping(world, "outlaw")[0]
    _quiet(world, but={t["id"]})
    pol = _politics(world, tables)
    gang = threats.gang_of(world, t)
    assert threats.seed_from(pol, "outlaw", faction=gang) is t
    assert t["state"] == "stirring" and t["woke"]["why"] == "seed:outlaw"


def test_robbing_the_barrow_wakes_its_king_and_the_hero_feels_it(made, tables):
    w = copy.deepcopy(made)
    t = _sleeping(w, "risen")[0]
    _quiet(w, but={t["id"]})
    town = min((s for s in w.settlements if s.kind in ("town", "village")),
               key=lambda s: threats.distance(w, t, s.x, s.y))
    game = new_game(w, tables, start_settlement=town.id)
    game.survival = False
    beats.director(game.world)["opening"] = None
    t = threats.records(game.world)[t["id"]]
    t["state"], t["scheme"]["stage"] = "dormant", -1
    site = game.world.sites[t["home"]["site"]]
    game.player.x, game.player.y = site.x, site.y
    lm = gen.get_dungeon(game.world, game.tables, site, 1)
    game.player.local_key = lm.key
    assert int(lm.meta["site"]) == site.id
    spot = next((xy for xy, f in lm.features.items() if f.get("grave")), None)
    if spot is None:
        spot = next(xy for xy, f in lm.features.items() if f["kind"] == "chest")
        lm.features[spot]["grave"] = True
    lm.features[spot]["locked"] = 0
    lm.features[spot].pop("rouse", None)
    game.player.lx, game.player.ly = spot
    dungeon.open_chest(game, lm, *spot)
    assert t["state"] == "stirring" and t["woke"]["why"] == "tomb_robbed"
    felt = tables.threats["triggers"]["tomb_robbed"]["felt"]
    said = " ".join(m.text for m in game.log.messages)
    assert any(line.split(">", 1)[1].split("<", 1)[0][:30] in said for line in felt), "the hero is warned"


def test_the_storyteller_wakes_a_threat_for_a_hero_with_nothing_near(made, tables):
    w = copy.deepcopy(made)
    first = [t for t in threats.records(w).values() if t["tier"] == 1 and threats.villain_lives(w, t)]
    if not first:
        pytest.skip("no first-tier threat")
    t = first[0]
    town = min((s for s in w.settlements if s.kind in ("town", "village")),
               key=lambda s: threats.distance(w, t, s.x, s.y))
    game = new_game(w, tables, start_settlement=town.id)
    game.survival = False
    d = beats.director(game.world)
    d["opening"] = None
    for o in threats.records(game.world).values():
        o["state"] = "ended" if o["id"] != t["id"] else "dormant"
    t = threats.records(game.world)[t["id"]]
    t["scheme"]["stage"] = -1
    assert threats.distance(game.world, t, game.player.x, game.player.y) <= tables.threats["need"]["tiles"]
    woke = None
    for i in range(40):  # (a chance a week: within forty weeks it comes)
        woke = threats.needed(game.world, tables, RNG(i), game.player.x, game.player.y, game.leader.level,
                              day=news.now_days(game.world))
        if woke is not None:
            break
    assert woke is t and t["state"] == "stirring" and t["woke"]["why"] == "need"
    assert threats.needed(game.world, tables, RNG(0), game.player.x, game.player.y, 1,
                          day=news.now_days(game.world)) is None, "one stirring near is enough"
    # (and from the day's turn itself)
    t["state"], t["scheme"]["stage"] = "dormant", -1
    d.pop("need_day", None)
    d["day"] = -1
    for day in range(60):
        game.world.time += 1440
        story.daily(game)
        if t["state"] != "dormant":
            break
    assert t["state"] == "stirring"


def test_a_hero_of_the_first_tier_is_not_given_a_wight(made, tables):
    assert threats.hero_tier(tables, 1) == 1 and threats.hero_tier(tables, 5) == 2
    assert threats.hero_tier(tables, 11) == 3 and threats.hero_tier(tables, 20) == 4
    w = copy.deepcopy(made)
    risen = _sleeping(w, "risen")
    _quiet(w, but={t["id"] for t in risen})
    t = risen[0]
    x, y = threats.home_xy(w, t)
    assert t["tier"] >= 2
    for i in range(30):
        assert threats.needed(w, tables, RNG(i), x, y, 1, day=0.0) is None


def test_the_world_ends_each_kind_by_itself(world, tables, monkeypatch):
    for kid in ("risen", "beast", "outlaw"):
        assert tables.threats["kinds"][kid].get("ends") and kid in threats.ENDINGS
    pol = _politics(world, tables)
    ended = 0
    for kid, outcome in (("beast", "hunted"), ("outlaw", "fallen")):
        kind = tables.threats["kinds"][kid]
        monkeypatch.setitem(kind, "ends", dict(kind["ends"], chance=1.0))
        ts = [t for t in _sleeping(world, kid) if threats._lord_near(pol, t) is not None]
        assert ts, f"a {kid} in some realm's land"
        t = ts[0]
        lord = threats._lord_near(pol, t)
        assert tables.factions["kinds"][lord.kind]["group"] == "realms"
        t["state"] = "stirring"
        name = threats.villain_name(world, t)
        threats._ends_alone(pol, t)
        assert t["state"] == "ended" and t["outcome"] == outcome
        assert not threats.villain_lives(world, t)
        assert any(name in n["text"] for n in world.news[-5:]), "the roads hear of it"
        ended += 1
    assert ended == 2


def test_with_no_lord_near_the_riders_do_not_come(world, tables, monkeypatch):
    t = _sleeping(world, "outlaw")[0]
    t["state"] = "stirring"
    pol = _politics(world, tables)
    monkeypatch.setattr(threats, "_lord_near", lambda pol, t: None)
    kind = tables.threats["kinds"]["outlaw"]
    monkeypatch.setitem(kind, "ends", dict(kind["ends"], chance=1.0))
    threats._ends_alone(pol, t)
    assert t["state"] == "stirring"


def test_the_interlude_says_what_woke_and_what_ended(world, tables):
    from realmwalker.game.interlude import snapshot, threat_changes

    ts = [t for t in threats.records(world).values() if threats.villain_lives(world, t)][:3]
    if len(ts) < 2:
        pytest.skip("too few threats")
    for t in ts:
        t["state"], t["scheme"]["stage"] = "dormant", -1
    before = snapshot(world)["threats"]
    pol = _politics(world, tables)
    threats.wake(world, tables, ts[0], pol.rng, day=pol.day, why="chance", force=True)
    threats.wake(world, tables, ts[1], pol.rng, day=pol.day, why="chance", force=True)
    threats.end(world, ts[1], "slain", pol.day)
    lines = threat_changes(world, tables, before, snapshot(world)["threats"])
    assert len(lines) == 2 and all("{" not in line for line in lines)
    assert any(line.startswith("<warn>") for line in lines) and any(line.startswith("<good>") for line in lines)
    unheard = next((t for t in threats.records(world).values() if t["state"] == "dormant"), None)
    if unheard is not None:  # (a sleeping threat ended by others before anyone heard of it: no line)
        before = snapshot(world)["threats"]
        threats.end(world, unheard, "slain", pol.day)
        assert threat_changes(world, tables, before, snapshot(world)["threats"]) == []
    summary = pass_the_years(world, tables, RNG(5), days=60)
    assert all("{" not in line for line in summary["lines"])


def test_a_busy_interlude_still_has_room_for_the_threats(world, tables, monkeypatch):
    from realmwalker.game import interlude

    t = next(t for t in threats.records(world).values() if threats.villain_lives(world, t))
    t["state"], t["scheme"]["stage"] = "dormant", -1
    before = interlude.snapshot(world)
    pol = _politics(world, tables)
    threats.wake(world, tables, t, pol.rng, day=pol.day, why="chance", force=True)
    for s in world.settlements[:30]:  # (a world on fire: a line for every burned town)
        s.status["burned"] = {"since": pol.day}
    lines = interlude.changes(world, tables, before, interlude.snapshot(world))
    assert len(lines) == interlude.MAX_LINES
    assert lines[-1].startswith("<warn>") and "burned" not in lines[-1], "the threat's line is kept"
