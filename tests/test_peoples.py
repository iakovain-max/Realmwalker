"""The peoples of the world (2026-10, Anton: "specific cultures with drastically different styles ... reminiscent of
the real world", "way more names and naming variations"): data/cultures.json and its registry, the name forge that
grows each world's own names, where the peoples live, and how the history names its realms, houses and rulers."""

import collections
import re

import pytest

from realmwalker.core.rng import RNG
from realmwalker.world import factions as fx
from realmwalker.world.generator import WorldOptions
from realmwalker.world.model import NO_CULTURE
from realmwalker.world.names import BLOCKED, NameForge
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402

HUMAN = ("heartland", "northmarch", "southron", "highland", "qasari", "khurgan", "volsk", "thalassian", "itzan")


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Peopleland", 21, "large"), tables)


# ---------------------------------------------------------------------------- the registry and its data
def test_nine_human_peoples_and_their_elders(tables):
    c = tables.cultures
    assert set(HUMAN) <= set(c.human)
    assert {"elven", "dwarven"} <= set(c.elder)
    for cid in c.ids:
        assert c.race(cid) in tables.races or c.race(cid) == "half_orc"
        assert c.faith(cid) in tables.factions["faiths"]
        assert c.about(cid) and c.get(cid)["like"]


def test_every_human_people_has_plenty_of_names(tables):
    for cid in HUMAN:
        pool = tables.names["cultures"][cid]
        for key in ("male", "female", "family"):
            assert len(pool[key]) >= 90, (cid, key)
            assert len(set(pool[key])) == len(pool[key]), (cid, key)
        assert pool.get("byname"), cid


def test_rulers_are_called_what_their_people_call_them(tables):
    c = tables.cultures
    assert c.title("kingdom", "female", "qasari") == "Sultana"
    assert c.title("kingdom", "male", "khurgan") == "Khagan"
    assert c.title("noble_house", "male", "northmarch") == "Jarl"
    assert c.title("kingdom", "male", "heartland") == "King"
    assert c.title("temple", "female", "qasari") == "High Priestess"  # nothing of their own: the general title
    assert any("Sultanate" in p for p in c.realm_patterns("kingdom", "qasari"))
    assert c.realm_patterns("clan", "dwarven") == tables.factions["kinds"]["clan"]["names"]


# ---------------------------------------------------------------------------- the name forge
def test_a_world_grows_names_of_its_own(tables):
    a, b, again = NameForge(1, tables), NameForge(2, tables), NameForge(1, tables)
    assert a.pools[("qasari", "male")] == again.pools[("qasari", "male")]  # the same seed, the same names
    real = set(tables.names["cultures"]["qasari"]["male"])
    grown_a = set(a.pools[("qasari", "male")]) - real
    grown_b = set(b.pools[("qasari", "male")]) - real
    assert grown_a and grown_b and grown_a != grown_b
    for cid in tables.cultures.ids:
        for key in ("male", "female", "family"):
            grown = set(a.pools[(cid, key)]) - set(tables.names["cultures"][cid][key])
            for name in grown:
                assert not any(bad in name.lower() for bad in BLOCKED), name


def test_names_are_put_together_as_each_people_does(tables):
    f = NameForge(7, tables)
    rng = RNG(3, "names")
    assert f.patronymic("northmarch", "Bjorn", "male") == "Bjornsson"
    assert f.patronymic("northmarch", "Bjorn", "female") == "Bjornsdottir"
    assert f.patronymic("qasari", "Tariq", "female") == "bint Tariq"
    assert f.patronymic("highland", "Aodh", "male") == "mac Aodh"
    assert f.patronymic("volsk", "Ivan", "male") == "Ivanovich"
    assert f.patronymic("volsk", "Nikita", "female") == "Nikitichna"
    assert f.patronymic("volsk", "Dmitri", "male") == "Dmitrievich"
    assert f.family_for("volsk", "Volkov", "female") == "Volkova"
    assert f.family_for("volsk", "Obolensky", "female") == "Obolenskaya"
    assert f.family_for("thalassian", "Komnenos", "female") == "Komnenou"
    assert f.family_for("heartland", "Ashdown", "female") == "Ashdown"
    noble = f.person("qasari", "male", rng, noble=True, family="Qasimi")
    assert noble.endswith(" al-Qasimi")
    seen = [f.person("volsk", "female", rng, family="Morozov") for _ in range(30)]
    assert any(n.endswith("Morozova") for n in seen) and not any(n.endswith(" Morozov") for n in seen)


def test_every_people_names_every_kind_of_country(tables):
    f = NameForge(11, tables)
    rng = RNG(5, "geo")
    kinds = ("mountains", "hills", "forest", "pine_forest", "marsh", "plains", "desert", "tundra", "coast", "lake",
             "river", "ocean", "island", "bay", "peak")
    for cid in tables.cultures.ids:
        for kind in kinds:
            name = f.geo(cid, kind, rng)
            assert name and "{" not in name and "}" not in name, (cid, kind, name)
    names = {f.geo("highland", "lake", rng) for _ in range(40)}
    assert any(re.match(r"(Loch|Llyn|Lough) ", n) for n in names)


# ---------------------------------------------------------------------------- the peoples on the map
def test_the_peoples_live_on_the_land(world, tables):
    land = world.culture != NO_CULTURE
    water = world.biome == world.biome_ids.index("ocean")
    assert land.sum() > 0 and not (land & water).any()
    share = collections.Counter(world.culture_ids[i] for i in world.culture[land].tolist())
    human = {c: n for c, n in share.items() if c in HUMAN}
    assert len(human) >= 6
    biggest = max(human.values()) / land.sum()
    assert biggest < 0.4  # no one people swallows the world
    assert world.politics["peoples"]["northmarch"]  # this world's own name for the Norse people


def test_settlements_belong_to_the_people_of_their_ground(world):
    for s in world.settlements:
        if s.kind in ("hold", "elfhall") or s.culture == "halfling":
            continue
        ground = world.culture_at(s.x, s.y)
        assert s.culture == ground or s.culture in HUMAN, s.name


def test_realms_and_houses_are_named_by_their_people(world, tables):
    c = tables.cultures
    for f in fx.active_factions(world, "kingdom", "noble_house"):
        leader = fx.leader_of(world, f)
        assert leader is not None
        expected = c.title(f.kind, leader.sex, f.culture)
        if leader.title and not leader.title.startswith("the "):
            assert leader.title == expected, (f.name, leader.title, expected)
    for f in fx.active_factions(world, "noble_house"):
        family = f.flags.get("family", "")
        assert family and family in f.name, f.name


def test_children_carry_a_parent_s_family_name(world):
    checked = 0
    for fig in world.figures.values():
        if fig.kind != "person" or not fig.family:
            continue
        parents = [world.figures.get(p) for p in (fig.father, fig.mother) if p >= 0]
        families = {p.family for p in parents if p is not None and p.family}
        if families:
            checked += 1
            assert fig.family in families, fig.name
    assert checked > 50


def test_towns_change_their_people_over_a_long_history(tables):
    w = cached_world(WorldOptions("Shifting", 33, "medium", history=500), tables)
    changed = [e for e in w.history if e["kind"] == "assimilated"]
    assert changed, "five hundred years and nobody changed"
    for e in changed:
        assert "{" not in e["text"]
    for s in w.settlements:  # the map of peoples was redrawn where the history left them
        assert w.culture_at(s.x, s.y) == s.culture, s.name


def test_a_character_starts_among_their_own_people(world, tables):
    from realmwalker.rules.creation import starting_places

    peoples = collections.Counter(s.culture for s in world.settlements if s.kind in ("village", "town", "city"))
    culture = next(c for c, n in peoples.most_common() if c in HUMAN and c != "heartland")
    places = starting_places(world, tables, "soldier", "human", RNG(4, "start"), culture=culture)
    assert places and world.settlements[places[0]].culture == culture
