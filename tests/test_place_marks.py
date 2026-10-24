"""Marks on places (Expansion 6 B.3, docs/ADVENTURES.md §5.19, §8.13): what a settlement goes through is a mark
(world/marks.py), written through one door by every path of the politics engine, aging by the world's clock (burning
-> burned -> rebuilding -> gone), and spoken of on the world map, walking in and in the streets. (tests/test_marks.py
tests the marks spells leave on creatures.)"""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game.state import new_game
from realmwalker.world import factions as fx
from realmwalker.world import marks
from realmwalker.world.generator import WorldOptions
from realmwalker.world.politics import Politics
from realmwalker.world.tables import Tables
from tests.worlds import cached_world


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Markland", 21, "small", history=60), tables)


@pytest.fixture
def world(made):
    return copy.deepcopy(made)


def _pol(world, tables):
    return Politics(world, tables, RNG(5, "marks"))


def test_every_mark_has_its_words(tables):
    assert {"siege", "beset", "sacked", "burning", "burned", "rebuilding", "emptied", "plague", "famine", "raided",
            "tribute", "beast", "festival", "memorial"} <= set(tables.marks)
    for mid, m in tables.marks.items():
        into = (m.get("ages") or {}).get("into")
        assert into is None or into in tables.marks, mid
        for line in m["troubles"] + m["moments"]:
            assert line.count("<") == line.count(">"), (mid, line)


def test_each_politics_path_writes_its_mark(world, tables):
    pol = _pol(world, tables)
    s = next(t for t in world.settlements if t.kind in ("hamlet", "village"))
    pol.famine(fx.realm_of_settlement(world, s) or next(iter(world.factions.values())))
    tribes = [f for f in world.factions.values() if f.kind in ("tribe", "orc_tribe", "horde") and f.active]
    for tribe in tribes[:3]:
        pol.raid(tribe)
    lair = next(i for i, site in enumerate(world.sites)
                if any(abs(t.x - site.x) + abs(t.y - site.y) <= 14 for t in world.settlements))
    for _ in range(4):
        pol.dragon_wakes({"name": "Ashmaw", "lair": lair})
    marked = {k for t in world.settlements for k in marks.marks_of(t)}
    assert "famine" in marked or not fx.realm_of_settlement(world, s)
    assert marked & {"burned", "tribute"}, marked
    for t in world.settlements:
        for k in marks.marks_of(t):
            assert marks.since(t, k) is not None


def test_marks_age_by_the_clock(world, tables):
    s = world.settlements[0]
    marks.add(world, s, "burning", 100.0, tables)
    assert marks.since(s, "burning") == 100.0
    marks.age(world, tables, 101.0)
    assert "burning" in s.status, "it burns a day or two"
    marks.age(world, tables, 103.0)
    assert "burning" not in s.status and marks.since(s, "burned") == 103.0, "then it is burned"
    assert isinstance(s.status["burned"], float), "burned keeps its old form, a day number"
    marks.age(world, tables, 200.0)
    assert "burned" in s.status
    marks.age(world, tables, 260.0)
    assert "burned" not in s.status and "rebuilding" in s.status, "after a season, it builds again"
    assert s.status["rebuilding"]["until"] > 260.0
    marks.add(world, s, "plague", 300.0, tables, until=320.0)
    marks.age(world, tables, 321.0)
    assert "plague" not in s.status, "a plague passes"


def test_old_day_number_values_still_read(world, tables):
    s = world.settlements[0]
    s.status["sacked"] = 50
    s.status["tribute"] = "Ashmaw"
    s.status["raided"] = {"until": 70}
    assert marks.since(s, "sacked") == 50.0
    assert marks.since(s, "raided") == 70.0
    assert marks.since(s, "tribute") == 0.0
    marks.age(world, tables, 171.0)
    assert "sacked" not in s.status and "raided" not in s.status and s.status["tribute"] == "Ashmaw"


def test_marks_are_spoken_of(world, tables):
    game = new_game(world, tables)
    game.survival = False
    s = min(world.settlements, key=lambda t: abs(t.x - game.player.x) + abs(t.y - game.player.y))
    s.status.clear()
    marks.add(world, s, "burned", 10.0, tables)
    marks.add(world, s, "beast", 10.0, tables, until=40.0, by="Grimtooth")
    marks.add(world, s, "tribute", 10.0, tables, name="Ashmaw")
    from realmwalker.game.describe import settlement_line
    from realmwalker.game.people import town_moment

    line = settlement_line(game, s)
    assert "urned" in line and "beast" in line and "tribute" in line, line
    troubles = " ".join(game.settlement_troubles(s))
    assert "Grimtooth" in troubles and "Ashmaw" in troubles, troubles
    assert "{" not in troubles
    seen = {town_moment(game, s) for _ in range(1) for game.player.steps in range(40)}
    assert seen & {m for k in ("burned", "beast", "tribute") for m in tables.marks[k]["moments"]}
