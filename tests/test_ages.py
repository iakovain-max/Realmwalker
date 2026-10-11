"""The lived history (world/ages, 2026-10): a world whose present is what is left of its past, after Dwarf Fortress.

Same seed, same history; every reference resolves; families are families (parents older than their children, nobody
dying before they were born); the ledger of who held what agrees with today's map; every ruin was a real place; and
today's world has the shape the rest of the game needs, at every size and every length of history.
"""

import collections
import time

import pytest

from realmwalker.world import factions as fx
from realmwalker.world import politics
from realmwalker.world.ages.sim import DYNASTIC
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402

SPAN = {"dwarf": 3.5, "elf": 7.0, "halfling": 1.6, "half_orc": 0.85, "human": 1.0}


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Agesland", 17, "medium"), tables)


def make(tables, seed: int, size: str = "small", years: int = 0):
    return cached_world(WorldOptions("Ages", seed, size, history=years), tables)


def ref_ok(world, ref: str) -> bool:
    if not ref:
        return True
    kind, num = ref[0], ref[1:]
    if not num.isdigit():
        return False
    n = int(num)
    return {"S": n < len(world.settlements), "X": n < len(world.sites)}.get(kind, False)


# ---------------------------------------------------------------------------- the same seed, the same past
def test_the_history_data_is_there(tables):
    h = tables.history
    assert "dragon" in h["beasts"] and h["text"]["battle_named"] and h["lengths"]


def test_same_seed_same_history(tables):
    a = make(tables, 3)
    b = make(tables, 3)
    assert [e["text"] for e in a.history] == [e["text"] for e in b.history]
    assert [f.to_dict() for _, f in sorted(a.figures.items())] == [f.to_dict() for _, f in sorted(b.figures.items())]
    assert [s.name for s in a.settlements] == [s.name for s in b.settlements]
    assert [s.name for s in a.sites] == [s.name for s in b.sites]


# ---------------------------------------------------------------------------- a history that holds together
def test_every_reference_resolves(world):
    w = world
    war_ids = {war["id"] for war in w.wars}
    for e in w.history:
        assert "{" not in e["text"] and e["text"].strip(), e
        assert all(0 <= p < len(w.settlements) for p in e.get("places", [])), e
        assert all(0 <= p < len(w.sites) for p in e.get("sites", [])), e
        assert all(f in w.factions for f in e.get("factions", [])), e
        assert all(h in w.figures for h in e.get("figures", [])), e
        if "war" in e:
            assert e["war"] in war_ids, e
    for fig in w.figures.values():
        for ref in (fig.home, fig.died_at, fig.buried):
            assert ref_ok(w, ref), (fig.name, ref)
        assert fig.faction < 0 or fig.faction in w.factions
        assert all(k in w.figures for k in fig.kills)
    for a in w.politics["artifacts"]:
        assert -1 <= a["site"] < len(w.sites)
        assert a["holder"] < 0 or w.figures[a["holder"]].alive, a
        assert a["maker"] < 0 or a["maker"] in w.figures
        assert ref_ok(w, a["place"]) and a["name"] and a["fate"]
    for site_id, hid in w.politics["lairs"].items():
        assert 0 <= int(site_id) < len(w.sites) and w.figures[hid].alive
    for site_id, hid in w.politics["tombs"].items():
        assert 0 <= int(site_id) < len(w.sites) and hid in w.figures


def test_families_are_families(world, tables):
    w = world
    present = tables.calendar.start_year
    for fig in w.figures.values():
        if fig.kind != "person":
            continue
        assert fig.died is None or fig.died >= fig.born, fig.name
        span = SPAN.get(fig.race, 1.0)
        if fig.alive:
            assert present - fig.born <= 110 * span, (fig.name, fig.born)
        for p in (fig.mother, fig.father):
            if p < 0:
                continue
            parent = w.figures[p]
            pspan = SPAN.get(parent.race, 1.0)
            assert fig.born - parent.born >= 13 * pspan, (parent.name, parent.born, fig.name, fig.born)
            assert parent.died is None or fig.born <= parent.died + 1, (parent.name, parent.died, fig.name, fig.born)


def test_the_ledger_of_who_held_what_agrees_with_today(world):
    """Replaying every change of hands in the history gives exactly today's holder of every place."""
    w = world
    owners: dict[int, int] = {}
    for e in w.history:
        for sid, fid in e.get("data", {}).get("owners", []):
            owners[sid] = fid
    for s in w.settlements:
        assert owners.get(s.id, -1) == s.owner, (s.name, owners.get(s.id), s.owner)


def test_every_line_of_rulers_comes_down_to_today(world):
    w = world
    active_leaders = {f.leader for f in fx.active_factions(w)}
    for f in fx.active_factions(w, *DYNASTIC):
        rulers = [w.figures[r] for r in f.rulers]
        assert rulers and rulers[-1].id == f.leader and rulers[-1].alive, f.name
        for r in rulers[:-1]:
            assert not r.alive or r.id in active_leaders, (f.name, r.name)  # dead, or crowned somewhere greater


# ---------------------------------------------------------------------------- what the ages leave
def test_every_ruin_was_a_real_place(world):
    w = world
    ruins = w.politics["ruins"]
    for site in w.sites:
        if site.kind == "ruin":
            past = ruins.get(str(site.id))
            assert past and past.get("cause"), site.name
            assert past.get("fell", past.get("year")) is not None
    lost = [p for p in ruins.values() if not p.get("elder")]
    assert lost, "no town of the ages fell"
    for past in lost:
        assert past["names"] and past["was"] and past["fell"] >= past["names"][0][1]
    for s in w.settlements:
        place = w.politics["places"][str(s.id)]
        assert place["founded"] is not None and place["names"][-1][0] == s.name


def test_wars_have_names_battles_and_their_dead(world):
    w = world
    fought = [war for war in w.wars if war["battles"] >= 2]
    assert fought
    battles = [e for e in w.history if e["kind"] == "battle_named"]
    assert battles and all(e.get("war") is not None and e["data"]["commanders"] for e in battles)
    for war in fought:
        assert war["name"] and any(e.get("war") == war["id"] for e in battles)
    slain = [f for f in w.figures.values() if f.kind == "person" and f.slayer >= 0]
    assert slain and all(f.id in w.figures[f.slayer].kills for f in slain)


def test_beasts_dragons_heroes_and_artifacts(world):
    w = world
    lairs = w.politics["lairs"]
    for site_id, hid in lairs.items():
        beast = w.figures[hid]
        assert beast.kind in ("beast", "dragon") and beast.creature
        assert w.sites[int(site_id)].faction < 0, "a lair held by a faction too"
    living = [d for d in w.politics["dragons"] if d["alive"]]
    assert living and all(0 <= d["lair"] < len(w.sites) for d in living)
    artifacts = w.politics["artifacts"]
    assert artifacts and any(a["site"] >= 0 for a in artifacts), "no artifact lies anywhere to be found"
    kinds = collections.Counter(e["kind"] for e in w.history)
    for needed in ("succession", "war_named", "battle_named", "artifact_made", "wedding", "settled"):
        assert kinds[needed], needed


def test_the_ages_are_named(world, tables):
    eras = world.politics["eras"]
    assert eras[0]["theme"] == "myth" and eras[0]["end"] == eras[1]["start"]
    for a, b in zip(eras[1:], eras[2:]):
        assert a["end"] == b["start"]
    assert eras[-1]["end"] == tables.calendar.start_year
    assert all(e["name"] and e["summary"] for e in eras)


def test_every_cause_of_death_reads_after_died(data):
    """A cause is written both "X died {cause}" and "Died in 907, {cause}": not "died devoured by the troll",
    "died burned as a heretic" or "died drowned crossing a river"."""
    wrong = ("devoured", "torn", "killed", "burned", "taken", "beheaded", "drowned", "slain", "and ")
    for source in ("history.json", "politics.json"):
        for kind, causes in data[source]["causes"].items():
            for cause in causes:
                assert not cause.startswith(wrong), (source, kind, cause)


def test_an_age_is_named_for_what_set_it_apart(tables):
    """Measured against the world's own usual: a burst of battles is a war, the usual run of things an age of kings,
    and only a stretch quieter than the usual is called a peace ("the Long Peace" once held five wars)."""
    from types import SimpleNamespace

    from realmwalker.world.ages.eras import Judge

    stats = collections.defaultdict(lambda: collections.defaultdict(float))
    for y in range(200):
        stats[y]["battles"] = 5.0 if y < 50 else 2.0 if y < 150 else 0.0
        stats[y]["founded"] = 0.3
    judge = Judge(SimpleNamespace(data=tables.history, stats=stats, year0=0, present=200, years=200, top_realm={}))
    assert judge.theme(0, 50) == "war"
    assert judge.theme(50, 150) == "kings"
    assert judge.theme(150, 200) == "peace"


@pytest.mark.slow
def test_great_realms_still_go_to_war_late_in_a_long_history(tables):
    """Once the land had grown into a few great realms whose seats lay far apart, the wars stopped for good; their
    borders touch, and that is enough to fight over."""
    w = make(tables, 9, "medium", 1000)
    end = tables.calendar.start_year
    wars = [war["year"] for war in w.wars]
    early = sum(1 for y in wars if y < end - 700)
    late = sum(1 for y in wars if y >= end - 300)
    assert late >= max(5, early / 4), (early, late)


# ---------------------------------------------------------------------------- today, at every size and length
@pytest.mark.parametrize("size,years,seed", [("small", 100, 4), ("medium", 500, 8), ("large", 250, 2),
                                             ("small", 1000, 6)])
@pytest.mark.slow
def test_today_has_the_shape_the_game_needs(tables, size, years, seed):
    w = make(tables, seed, size, years)
    kinds = {f.kind for f in fx.active_factions(w)}
    for needed in ("kingdom", "noble_house", "temple", "merchant_guild", "cult", "bandit_gang", "healers_guild"):
        assert needed in kinds, needed
    assert len(fx.active_factions(w, "kingdom")) >= 2
    for f in fx.active_factions(w):
        leader = fx.leader_of(w, f)
        assert leader is not None and leader.alive and leader.faction == f.id, f.name
    for s in w.settlements:
        if s.kind in ("town", "city", "hold", "elfhall"):
            owner = fx.owner_of(w, s)
            assert owner is not None and owner.kind in fx.REALM_KINDS, s.name
    assert {"city", "town", "village", "hamlet"} <= {s.kind for s in w.settlements}
    assert w.politics["history_from"] == tables.calendar.start_year - years
    assert any(d["alive"] for d in w.politics["dragons"])
    assert all("{" not in e["text"] for e in w.history)


def test_a_history_is_lived_quickly(tables):
    start = time.monotonic()
    make(tables, 12, "medium")
    assert time.monotonic() - start < 10


# ---------------------------------------------------------------------------- old saves, and the world after
def test_figures_saved_before_the_ages_still_load():
    old = {"id": 3, "name": "Aldric Draycott", "sex": "male", "race": "human", "culture": "heartland", "born": 1000,
           "faction": 1, "title": "Lord", "role": "ruler"}
    fig = fx.Figure.from_dict(old)
    assert fig.kind == "person" and fig.kills == [] and fig.full_name() == "Lord Aldric Draycott"


def test_the_world_lives_on_after_its_history(world, tables):
    import copy

    w = copy.deepcopy(world)
    politics.tick(w, tables)
    w.time += 3 * 360 * 1440
    assert politics.tick(w, tables)
    for f in fx.active_factions(w):
        leader = fx.leader_of(w, f)
        assert leader is not None and leader.alive, f.name
