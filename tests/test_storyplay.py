"""Storyplay (Expansion 6 A.11, docs/ADVENTURES.md §9): a careful party plays the Beast through on real roads, from
its hook to its epilogue; Part A's measure is that it finishes in at least 90% of 20 runs. Part D's (D.5): the Risen
and the Outlaw Lord the same, and a new life's opening begins a tale (`tools/storyplay.py --kind risen|outlaw`,
`--openings`, 20 runs each; here six of each, the slow suite's share)."""

import pytest

from realmwalker.world.tables import Tables
from tools import storyplay

pytestmark = [pytest.mark.slow, pytest.mark.story]


def test_the_beast_is_finished_nine_times_in_ten(data):
    runs = storyplay.play(20, tables=Tables(data))
    done = [r for r in runs if r.finished]
    assert len(done) >= 18, "\n".join(f"{r.world} {r.threat}: {r.why or r.ending}" for r in runs if not r.finished)
    assert all(r.ending == "slain" for r in done)
    assert sum(1 for r in done if r.fights >= 2) >= len(done) // 2, "most hunts reach the den and its finale"


@pytest.mark.parametrize("kind", ["risen", "outlaw"])
def test_part_ds_tales_are_finished(data, kind):
    runs = storyplay.play(6, tables=Tables(data), kind=kind)
    done = [r for r in runs if r.finished]
    assert len(done) >= 5, "\n".join(f"{r.world} {r.threat}: {r.why or r.ending}" for r in runs if not r.finished)
    assert all(r.ending not in ("doom", "abandoned") for r in done), [r.ending for r in done]
    assert all(r.fights >= 2 for r in done), "every tale is fought for"


def test_a_new_life_opens_with_a_tale(data):
    runs = storyplay.openings(6, tables=Tables(data))
    assert sum(r.begun for r in runs) >= 5, "\n".join(f"{r.world} {r.kind}: {r.why}" for r in runs if not r.begun)
    assert sum(r.finished for r in runs) >= 4, "\n".join(f"{r.world} {r.kind}: {r.why or r.ending}" for r in runs)
    # (which first hour a life draws follows its dice, keyed by the world's id - which changes with the game's data -
    # and the hero's name: more than one kind is asked of many draws, not of these six lives)
    assert len({r.kind for r in runs} | _first_hours(data)) >= 2, "more than one kind of first hour"


def _first_hours(data) -> set:
    import copy

    from realmwalker.game.state import new_game
    from realmwalker.game.story import beats, opening
    from realmwalker.world import threats
    from realmwalker.world.generator import WorldOptions
    from tests.worlds import cached_world

    tables, kinds = Tables(data), set()
    for wo in storyplay.WORLDS:
        w = copy.deepcopy(cached_world(WorldOptions(*wo), tables))
        towns = sorted((s for s in w.settlements if s.kind in ("town", "village", "hamlet", "city")), key=lambda s: s.id)
        game = new_game(w, tables, start_settlement=towns[0].id)
        rec = beats.director(w).get("opening")
        if rec is None:
            continue
        t, town = threats.records(w)[rec["threat"]], w.settlements[rec["town"]]
        for n in range(12):
            game.leader.name = f"Hero {n}"
            kinds.add(opening.choose(game, t, town))
    return kinds


def test_the_income_reference_is_kept():
    """C.1: the careful player's income before Part C, the yardstick of the income measure (C.10: 0.7-1.3 times)."""
    import json

    ref = json.loads(storyplay.INCOME_REF.read_text(encoding="utf-8"))
    assert ref["days"] == storyplay.INCOME_DAYS and ref["runs"] == len(ref["per_run"]) >= 20
    assert ref["mean_total"] > 0 and 0 < ref["mean_work"] <= ref["mean_total"]
    assert sum(r["jobs"] for r in ref["per_run"]) > 2 * ref["runs"], "the careful player lived by its work"


def test_the_careful_player_earns_by_its_work(data, monkeypatch):
    """A short stretch of the income measure's player: what waits in the towns looked at, taken, done and paid for.
    Since C.3 every peopled town has a contract, so the careful player finds work again (jobs >= 1)."""
    from realmwalker.world.generator import WorldOptions
    from tests.worlds import cached_world

    monkeypatch.setattr(storyplay, "INCOME_DAYS", 8)
    tables = Tables(data)
    w = storyplay.WORLDS[2]
    e = storyplay.earn_once(tables, cached_world(WorldOptions(*w), tables), w[0], 0)
    assert e.days >= 8 or e.died, "\n".join(e.log)
    assert (e.work > 0) == (e.jobs > 0), "\n".join(e.log)
    assert e.jobs >= 1, "\n".join(e.log)
