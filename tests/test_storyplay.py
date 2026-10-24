"""Storyplay (Expansion 6 A.11, docs/ADVENTURES.md §9): a careful party plays the Beast through on real roads, from
its hook to its epilogue; Part A's measure is that it finishes in at least 90% of 20 runs."""

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


def test_the_income_reference_is_kept():
    """C.1: the careful player's income before Part C, the yardstick of the income measure (C.10: 0.7-1.3 times)."""
    import json

    ref = json.loads(storyplay.INCOME_REF.read_text(encoding="utf-8"))
    assert ref["days"] == storyplay.INCOME_DAYS and ref["runs"] == len(ref["per_run"]) >= 20
    assert ref["mean_total"] > 0 and 0 < ref["mean_work"] <= ref["mean_total"]
    assert sum(r["jobs"] for r in ref["per_run"]) > 2 * ref["runs"], "the careful player lived by its work"


def test_the_careful_player_earns_by_its_work(data, monkeypatch):
    """A short stretch of the income measure's player: what waits in the towns looked at, taken, done and paid for.
    From C.2 to C.3 there is little honest work about (the weekly offers are gone, the contracts not yet come), so
    the stretch must only run its days and count what it is paid; C.3 asks for a job again (jobs >= 1)."""
    from realmwalker.world.generator import WorldOptions
    from tests.worlds import cached_world

    monkeypatch.setattr(storyplay, "INCOME_DAYS", 8)
    tables = Tables(data)
    w = storyplay.WORLDS[2]
    e = storyplay.earn_once(tables, cached_world(WorldOptions(*w), tables), w[0], 0)
    assert e.days >= 8 or e.died, "\n".join(e.log)
    assert (e.work > 0) == (e.jobs > 0), "\n".join(e.log)
