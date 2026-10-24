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
