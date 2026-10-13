"""Encounters by the Dungeon Master's Guide (Expansion 1, D.3): the XP budget, bands built for the land, how hard a band
looks, travel pace, and the attitudes that feed Influence on the road, in a fight and in conversation."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import encounters, fight
from realmwalker.game.state import new_game
from realmwalker.rules import encounter
from realmwalker.rules.creatures import spawn, spawn_group
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Roadland", 43, "small"), tables)


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    return g


def test_the_xp_budget_per_character(tables):
    assert encounter.per_character(tables, 1) == [50, 75, 100]
    assert encounter.per_character(tables, 5) == [500, 750, 1100]
    assert encounter.per_character(tables, 20) == [6400, 13200, 22000]
    assert encounter.budget(tables, [1, 1, 1, 1], "low") == 200  # the DMG's own example


def test_how_hard_a_band_is(tables):
    assert encounter.difficulty(tables, ["wolf"], [1]) == "low"
    assert encounter.difficulty(tables, ["wolf", "wolf"], [1]) == "high"
    assert encounter.difficulty(tables, ["troll"], [1]) == "deadly"
    assert encounter.difficulty(tables, ["giant_rat"], [3, 3]) == "trivial"


def test_a_band_is_built_to_its_budget(tables):
    members = [["bandit_captain", "1"], ["bandit", "1d3+1"], ["bandit_archer", "1d2"]]
    xp = {d: int(tables.creatures[d]["xp"]) for d, _ in members}
    for i in range(50):
        counts = encounter.counts_for(tables, members, RNG(i), 500, 3)
        assert all(c >= 1 for c in counts)  # never the last of a kind
        total = sum(xp[d] * c for (d, _), c in zip(members, counts))
        assert total <= 500 or counts[1:] == [1, 1]
    big = encounter.counts_for(tables, [["wolf", "1d2+1"]], RNG(1), 3000, 3)
    assert big[0] <= int(3 * 1.3)  # grows only so far
    host = encounter.counts_for(tables, [["wolf", "1d2+1"]], RNG(1), 3 * 6400, 3)
    assert big[0] < host[0] <= 3 * int(3 * 1.3)  # (a budget for heroes of the fourth tier: a host, Demigods & Magics)
    troll = spawn_group(tables, "troll", RNG(2), budget=50)
    assert len(troll) == 1  # a troll is a troll, budget or not: some fights should be avoided


def test_road_bands_have_an_attitude_and_some_can_be_let_be(game):
    seen = {}
    for i in range(200):
        enc = encounters.make_encounter(game, "deserters", RNG(i, "enc"))
        seen[enc.attitude] = seen.get(enc.attitude, 0) + 1
        if enc.attitude == "indifferent" and "indifferent" not in seen.get("_done", ()):
            game.encounter = enc
            assert fight.encounter_pass(game) and game.encounter is None
    assert seen.get("hostile") and seen.get("indifferent")
    watch = encounters.make_encounter(game, "town_watch", RNG(1))
    assert watch.attitude == "hostile"
    game.encounter = watch
    assert not fight.encounter_pass(game) and game.encounter is watch


def test_the_screen_offers_letting_them_be(game, make_app):
    from realmwalker.ui.screens.encounter import EncounterScreen

    enc = encounters.make_encounter(game, "deserters", RNG(3))
    enc.attitude = "indifferent"
    game.encounter = enc
    app = make_app()
    screen = EncounterScreen(app, game)
    keys = {o[0]: o for o in screen.options()}
    assert "l" in keys and keys["l"][3]
    enc.attitude = "hostile"
    assert "l" not in {o[0] for o in screen.options()}
    assert "disadvantage" in next(o[1] for o in screen.options() if o[0] == "t")


def test_travel_pace(game):
    p = game.player
    assert game.travel_pace() == "normal"
    said = game.cycle_pace()
    assert p.pace == "fast" and "Fast" in said
    assert encounter.max_pace(game.tables, "marsh", "marsh", False) == "slow"
    assert encounter.max_pace(game.tables, "marsh", "marsh", True) == "normal"  # a good road: one step faster
    assert encounter.max_pace(game.tables, "plains", "plains", False) == "fast"
    assert encounter.allowed("fast", "slow") == "slow"
    from realmwalker.game.save import character_entries

    assert '"pace": "fast"' in str(character_entries(game))


def test_a_fast_pace_covers_ground_sooner(game, monkeypatch):
    monkeypatch.setattr(encounters, "encounter_chance", lambda *a, **k: 0.0)
    p = game.player
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if game.step_minutes(p.x, p.y, p.x + dx, p.y + dy) is not None:
            break
    times = {}
    for pace in ("normal", "fast", "slow"):
        g = copy.deepcopy(game)
        g.player.pace = pace
        if g.travel_pace() != pace:
            pytest.skip("the land here holds the pace back")
        t0 = g.world.time
        g.move(dx, dy)
        times[pace] = g.world.time - t0
    assert times["fast"] < times["normal"] < times["slow"]


def test_attitude_in_a_fight(tables):
    from realmwalker.rules.combat import Battle, Env

    b = Battle(tables, [], [spawn(tables, "bandit", RNG(1), 1), spawn(tables, "bandit", RNG(2), 2)], Env(), RNG(1))
    assert b.foe_attitude() == "hostile"
    for f in b.fighters:
        if f.creature is not None:
            f.hp = 1
    assert b.foe_attitude() == "indifferent"


def test_attitude_in_conversation(game, monkeypatch):
    from realmwalker.core import dice
    from realmwalker.game.dialogue import Conversation
    from realmwalker.game.people import npcs_in

    s = next(s for s in game.world.settlements if s.kind in ("town", "city", "village"))
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    npc = next(n for n in npcs_in(game.world, s.id))
    conv = Conversation(game, npc)
    seen = {}
    real = dice.d20

    def spy(rng, advantage=False, disadvantage=False):
        seen["adv"], seen["dis"] = advantage, disadvantage
        return real(rng, advantage=advantage, disadvantage=disadvantage)

    monkeypatch.setattr(dice, "d20", spy)
    npc.disposition = 80
    assert conv.attitude() == "friendly"
    assert "adv" in conv.check("persuasion", 13)[1] and seen["adv"]
    npc.disposition = -80
    assert conv.attitude() == "hostile"
    conv.check("persuasion", 13)
    assert seen["dis"]
