"""The balance targets from the design (section 16), measured rather than assumed (tools/balance.py).

These are seeded, so the numbers are exact; the bands are wide enough that ordinary tuning will not break them,
but a change that makes the game much softer or much deadlier will.
"""

import pytest

from realmwalker.world.tables import Tables
from tools import balance
from tests.worlds import cached_world  # noqa: E402

pytestmark = pytest.mark.slow  # the balance runs fight many battles


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def fight_rates(tables, group, size, level, party_size, runs=16):
    rows = [balance.fight_once(tables, group, size, level, party_size, seed) for seed in range(runs)]
    won = sum(1 for r in rows if r["outcome"] in ("victory", "parley")) / runs
    down = sum(1 for r in rows if r["down"]) / runs
    dead = sum(1 for r in rows if r["party_dead"] or r["wipe"]) / runs
    return won, down, dead


def test_two_wolves_are_a_real_threat_at_level_one(tables):
    won, down, dead = fight_rates(tables, "wolf_pack", 2, 1, 1)
    # (2024 origins - a background's feat, a weapon's mastery - make a level 1 hero a little stronger: measured over 80
    # fights, 85% won and 15% knocked down, where the band was at most 80% and at least 20%; Expansion 2 part B)
    assert 0.2 <= won <= 0.9, won  # you can win, and you can very much lose
    assert down >= 0.1, down  # and you will be on your back often enough to remember it


def test_three_bandits_are_a_real_threat_at_level_one(tables):
    won, down, dead = fight_rates(tables, "bandits", 3, 1, 1)
    assert 0.15 <= won <= 0.75, won
    assert down >= 0.25, down


def test_one_wolf_is_a_fight_not_a_death_sentence(tables):
    won, down, dead = fight_rates(tables, "wolf_pack", 1, 1, 1)
    assert won >= 0.6, won


def test_a_careful_party_prospers(tables):
    """Three of them, at level 3, against what killed them at level 1."""
    won, down, dead = fight_rates(tables, "bandits", 3, 3, 3)
    assert won >= 0.9, won
    assert dead <= 0.1, dead


def test_heroes_of_the_higher_tiers_meet_hosts_in_the_worst_lands(tables):
    """Level 11 and 17 parties of three against High bands built for danger 9 and 10 (Demigods & Magics part A).
    Measured 2026-10-13 over 12 fights each: every one won, at most 16% with someone down, 80-98% of the hit points
    left. The creatures that can truly test heroes of legend come with the bestiary expansions: until then the worst
    lands send hosts (two or three trolls where one came), and the band is that the heroes prevail and are touched."""
    for level, group, danger in balance.TIER_CASES:
        rows = [balance.fight_once(tables, group, 0, level, 3, seed, danger=danger) for seed in range(8)]
        won = sum(1 for r in rows if r["outcome"] in ("victory", "parley")) / len(rows)
        dead = sum(1 for r in rows if r["party_dead"] or r["wipe"]) / len(rows)
        assert won >= 0.85 and dead <= 0.15, (level, group, won, dead)
        assert sum(r["hp_left"] for r in rows) / len(rows) < 1.0  # (they were in a fight)
    assert any(r["foes"] >= 2 for r in [balance.fight_once(tables, "troll", 0, 17, 3, 1, danger=10)])


def test_low_lands_stay_low(tables):
    """A level 15 party walks through farmland in peace: the budget follows the land, not the party."""
    from realmwalker.rules import encounter

    assert all(encounter.danger_level(tables, d) <= 3 for d in range(8))
    assert encounter.tier_extra(tables, encounter.land_budget(tables, 3, 3, "high"), 3) == 1.0


def test_a_winter_night_without_fire_is_dangerous(tables):
    bare = balance.winter_night(tables, 4, fire=False, tent=False, clothes="poor")
    warm = balance.winter_night(tables, 4, fire=True, tent=True)
    assert bare["dead"] + bare["hurt"] + bare["cold"] == bare["runs"], bare  # nobody comes through it well
    assert warm["dead"] == 0 and warm["cold"] == 0, warm  # a fire and a tent are the answer


def test_an_untreated_critical_wound_kills_and_a_bandage_saves(tables):
    """A critical wound bleeds; left alone for a day it kills, and binding it saves you."""
    import copy

    from realmwalker.core.rng import RNG
    from realmwalker.game.state import new_game
    from realmwalker.rules.wounds import make_wound
    from realmwalker.world.generator import WorldOptions

    world = cached_world(WorldOptions("Woundland", 3, "small"), tables)
    runs = 12
    outcomes = {}
    for treated in (False, True):
        died = 0
        for seed in range(runs):
            game = new_game(copy.deepcopy(world), tables)
            game.survival = True
            game.world.time += seed  # the health stream is keyed on the clock: vary it, or every run is one run
            c = game.leader
            wound = make_wound("torso", "slashing", 3, RNG(seed, "balance-wound"), now=game.world.time)
            if treated:
                wound.bandaged = True
                wound.cleaned = True
            c.wounds.append(wound)
            for _ in range(24):
                c.hunger = min(c.hunger, 20.0)
                c.thirst = min(c.thirst, 20.0)
                game.pass_time(60, "rest")
                if not c.alive or game.over is not None:
                    died += 1
                    break
        outcomes[treated] = died
    assert outcomes[False] >= runs * 0.5, outcomes  # bleeding out is what an untreated critical wound means
    assert outcomes[True] <= 1, outcomes  # and binding it is what saves you


def test_a_serious_wound_left_alone_can_still_kill_you(tables):
    """A week with a serious, dirty wound and no treatment: most live, some fester, a few die of it."""
    untreated = balance.untreated_wound(tables, 16, treat=False)
    treated = balance.untreated_wound(tables, 16, treat=True)
    assert untreated["fine"] < untreated["runs"], untreated  # it is not a scratch
    assert untreated["sick"] + untreated["dead"] >= 2, untreated
    assert treated["fine"] >= untreated["fine"], (treated, untreated)  # binding and cleaning it helps
