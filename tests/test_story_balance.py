"""The fairness measure (Expansion 6 E.6, docs/ADVENTURES.md §5.8 rule 1 and §9): a careful party of four at the tier's
target level goes down to each tale's finale (`tools/storyplay.py --finale all|none --kind K`). With every key found on
the way it wins at least 80% of the time; with none, at most 45%, and the retreat works (it falls back off the field,
gets away, and the tale goes on with its finale still open). 30 lives each here (48 by hand measured beast 88/38,
outlaw 88/38, risen 98/29 when this was tuned)."""

import pytest

from realmwalker.world.tables import Tables
from tools import storyplay

pytestmark = [pytest.mark.slow, pytest.mark.story]

RUNS = 30


def _say(runs) -> str:
    return "\n".join(f"{r.world} {r.threat} tier {r.tier}: {r.outcome} boss={r.boss} rounds={r.rounds} dead={r.dead}"
                     f"{' (fell back)' if r.retreated else ''} {r.why}" for r in runs)


@pytest.mark.parametrize("kind", storyplay.KINDS)
def test_with_every_key_a_careful_party_wins(data, kind):
    runs = [r for r in storyplay.finales(RUNS, kind, "all", tables=Tables(data), quiet=True) if r.outcome]
    assert len(runs) >= RUNS - 2, "every life reaches its finale"
    won = sum(r.won for r in runs)
    assert won >= 0.8 * len(runs), f"{kind}: {won} of {len(runs)} with every key\n" + _say(runs)


@pytest.mark.parametrize("kind", storyplay.KINDS)
def test_with_no_keys_it_is_beyond_them_and_the_retreat_works(data, kind):
    runs = [r for r in storyplay.finales(RUNS, kind, "none", tables=Tables(data), quiet=True) if r.outcome]
    assert len(runs) >= RUNS - 2, "every life reaches its finale"
    won = sum(r.won for r in runs)
    assert won <= 0.45 * len(runs), f"{kind}: {won} of {len(runs)} with no keys\n" + _say(runs)
    back = [r for r in runs if r.retreated]
    assert back, "a careful party falls back from a fight it cannot win"
    assert sum(r.retreat_ok for r in back) >= 0.8 * len(back), "most who fall back get away, the tale going on\n" + \
        _say(back)
