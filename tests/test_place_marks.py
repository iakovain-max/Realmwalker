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


# ---------------------------------------------------------------------------- the close-up map (B.4)
def _as_tables_order(lm, tables):
    """The map with its terrain in the tables' own order (check_works reads the indices as the tables' own; a stamp
    adds terrains to the end of a map's own list)."""
    import numpy as np

    view = copy.copy(lm)
    view.terrain = np.array([tables.terrain.index[n] for n in lm.terrain_ids], np.int32)[lm.terrain]
    view.terrain_ids = list(tables.terrain.ids)
    return view


def test_every_mark_on_a_town_of_every_people_keeps_it_working(tables):
    """Each mark with a dress, stamped on a town of each people: the entry, a way out and every door still reached;
    lifting it gives back the map exactly. (On test_towns.py's own world, where every people's towns are checked.)"""
    from realmwalker.game import placemarks
    from tests.test_towns import STYLES, build_as, check_works

    world = copy.deepcopy(cached_world(WorldOptions("Townland", 21, "small", history=40), tables))
    game = new_game(world, tables)
    game.survival = False
    s = max(world.settlements, key=lambda t: t.population)
    dressed = [m for m, d in tables.marks.items() if d.get("dress")]
    assert {"burned", "sacked", "rebuilding", "festival", "siege"} <= set(dressed)
    for style in STYLES:
        old = s.culture
        s.culture = style
        try:
            lm = build_as(world, tables, style, "village")  # (every people's villages are checked in test_towns.py)
            before = lm.terrain.copy()
            ids_before = list(lm.terrain_ids)
            looks = [dict(b.look or {}) for b in lm.buildings]
            for mark in dressed:
                s.status.clear()
                marks.add(world, s, mark, 10.0, tables, until=99.0)
                assert placemarks.stamp(game, lm, s), (style, mark)
                check_works(_as_tables_order(lm, tables), tables, f"{style} {mark}")
                s.status.clear()
                assert placemarks.stamp(game, lm, s)
                now = [lm.terrain_ids[i] for i in lm.terrain.ravel()]
                was = [ids_before[i] for i in before.ravel()]
                assert now == was, f"{style} {mark}: the map was not restored"
                assert [dict(b.look or {}) for b in lm.buildings] == looks
        finally:
            s.culture = old
            s.status.clear()


def test_a_burned_town_looks_burned_the_first_time_you_walk_in(world, tables):
    from realmwalker.game import placemarks
    from realmwalker.game.economy import burnt_out

    game = new_game(world, tables)
    game.survival = False
    s = max((t for t in world.settlements if t.kind in ("town", "city")), key=lambda t: t.population)
    s.status.clear()
    marks.add(world, s, "burned", 1.0, tables)
    world.local_maps.pop(f"{s.x},{s.y}", None)
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    lm = game.enter_local()
    rec = lm.meta["marks"]["burned"]
    assert rec["cells"] and rec["looks"], "charred shells and ash in the streets"
    names = {lm.terrain_ids[int(lm.terrain[x, y])] for x, y, _ in rec["cells"]}
    assert "ash" in names
    assert any(lm.buildings[i].look.get("roof") == "none" for i, _ in rec["looks"]), "roofless shells"
    from realmwalker.game.people import npcs_in

    keepers = [n for n in npcs_in(world, s.id) if n.building in rec["shut"]]
    assert all(burnt_out(game, n) for n in keepers)
    walk = tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    assert all(walk[n.x, n.y] for n in npcs_in(world, s.id) if n.alive and n.present)
    s.status.clear()
    marks.add(world, s, "rebuilding", 400.0, tables)
    assert placemarks.stamp(game, lm, s)
    assert "burned" not in lm.meta["marks"] and "rebuilding" in lm.meta["marks"], "the mark ages, the map with it"
