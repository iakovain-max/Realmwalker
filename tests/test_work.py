"""Paid work (Expansion 6 C.3): contracts, one a town and two in a city, each with a real danger on its way; bounties
on gangs and on the beasts of the history; the terms shown wherever the work is."""

import pytest

from realmwalker.game import fight, notices, quests
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import prepare_town
from realmwalker.game.story import work
from realmwalker.rules.combat import PARTY
from realmwalker.ui.screens.journal import details
from realmwalker.world.tables import Tables
from tests.test_first_hour import SEEDS, a_life


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def contract(game, town):
    recs = [r for r in work.contracts(game, town) if not r.get("taken")]
    assert recs, f"{town.name} ({town.kind}) has paid work"
    return recs[0]


@pytest.mark.parametrize("seed", SEEDS)
def test_every_peopled_town_has_a_contract_with_a_real_danger(tables, seed):
    game, town = a_life(tables, seed)
    rec = contract(game, town)
    q = rec["quest"]
    assert q["template"] in ("escort", "deliver", "defend") and q["state"] == "offered"
    assert q["giver"] == rec["giver"] and game.world.npcs[q["giver"]].settlement == town.id
    lo, hi = tables.quests["templates"][q["template"]]["reward"]
    assert 10 <= q["reward"] <= hi * 3, "paid as the old jobs were (base_quest)"
    assert int(rec["until"]) - int(game.moment.total_days) <= 28
    if q["template"] != "defend":
        d = q["danger"]
        assert d["group"] in tables.creatures.encounters and d["name"] and len(d["at"]) == 2
        assert d["kind"] in ("threat", "gang", "lair", "wild")
        assert d["name"] in quests.pitch(game, q), "the giver says what is on the road"
        dest = game.world.settlements[q["target"]["dest"]]
        assert dest.kind in work.MARKET or dest.great, "carts and pilgrims go to a market or temple town"
    assert q in work.waiting(game)
    assert any(x is q for _, x in work.offers_here(game, town)), "the bots and the Earner find it"


def test_a_city_has_two(tables):
    game, _ = a_life(tables, SEEDS[0])
    w = game.world
    city = next((s for s in w.settlements if s.kind == "city" or s.great), None)
    if city is None:
        pytest.skip("no city in this world")
    prepare_town(game, city)
    recs = work.contracts(game, city)
    assert len(recs) == 2 and recs[0]["kind"] != recs[1]["kind"]


@pytest.mark.parametrize("seed", SEEDS)
def test_taken_from_its_giver_with_its_terms_shown(tables, seed):
    game, town = a_life(tables, seed)
    rec = contract(game, town)
    q = rec["quest"]
    giver = game.world.npcs[rec["giver"]]
    conv = Conversation(game, giver)
    own = next((c for c in conv.menu() if c.id == "own_work" and c.data.get("q") == q["id"]), None)
    assert own is not None, "the one hiring has their own choice"
    assert "Is there any work" not in own.label
    conv.choose(own)
    assert any("Paid work" in text for _, text in conv.lines), "the terms are shown"
    accept = next(c for c in conv.menu() if c.id == "work_accept")
    conv.choose(accept)
    assert quests.by_id(game, q["id"]) is not None
    assert rec["taken"] and q not in work.waiting(game)
    assert "Paid work" in details(game, q), "the journal's Work tab shows the terms"
    assert work.contracts(game, town) and work.contracts(game, town)[0]["taken"], \
        "the town has no other contract until this one's time is up"
    game.world.time += int((int(rec["until"]) - game.moment.total_days + 1) * 24 * 60)
    again = work.contracts(game, town)
    assert again and all(r["id"] != rec["id"] for r in again), "after its days, the town hires again"


def walk_into_the_danger(game, q):
    """Walk the carters' road from a few miles short of the danger's place (the overworld walk, step by step)."""
    w = game.world
    path = work._route(game, w.settlements[q["town"]], w.settlements[q["target"]["dest"]])
    i = path.index(tuple(q["danger"]["at"]))
    game.leave_local()
    game.player.x, game.player.y = path[max(1, i - 5)]
    for x, y in path[max(1, i - 5) + 1:i + 3]:
        if game.encounter is not None or game.busy:
            return
        assert game.move(x - game.player.x, y - game.player.y), "the road can be walked"


@pytest.mark.parametrize("seed", SEEDS)
def test_the_danger_is_met_on_the_road_and_fought(tables, seed, monkeypatch):
    from tools.arena import run as play_out

    monkeypatch.setattr("realmwalker.game.encounters.encounter_chance", lambda *a: 0.0)
    monkeypatch.setattr("realmwalker.game.events.event_chance", lambda *a: 0.0)
    game, town = a_life(tables, seed)
    rec = next((r for r in work.contracts(game, town) if r["quest"]["template"] != "defend"), None)
    if rec is None:
        pytest.skip("this town hires swords against raiders")
    q = rec["quest"]
    quests.accept(game, q)
    walk_into_the_danger(game, q)
    enc = game.encounter
    assert enc is not None and enc.group == q["danger"]["group"], "it was where they said it would be"
    assert q["danger"]["met"] is not False
    assert work.on_the_road(game) is None, "met once"
    assert "On the road" not in quests.danger_note(game, q)
    for c in game.party:  # (a party able to see it through, so the fight is played to its end)
        c.level = max(c.level, 5)
    fight.encounter_fight(game, ambush=False)
    b = game.battle
    assert b is not None
    for f in b.side(PARTY):
        f.auto = True
    play_out(b, max_steps=6000)
    after = fight.finish_battle(game)
    assert after.outcome, "the fight is played out"
    if after.outcome == "victory" and q["template"] == "escort":
        assert quests.by_id(game, q["id"])["state"] == "active", "the traveller walks on with you"


def test_the_board_posts_beasts_of_the_history(tables):
    for seed in SEEDS + (7,):
        game, town = a_life(tables, seed)
        beasts = [q for q in quests.board_bounties(game, town) if q["template"] == "hunt_beast"]
        if beasts:
            q = beasts[0]
            assert q["giver"] == -1 and q["target"].get("beast") is not None, "paid by the watch, on a real beast"
            assert any(n.get("bounty") is q for n in notices.notices(game, town)), "pinned on the board"
            quests.accept(game, q)
            assert quests.by_id(game, q["id"]) is not None
            return
    pytest.skip("no beast of the history lairs near these first towns")


def test_the_board_shows_who_is_hiring(tables):
    game, town = a_life(tables, SEEDS[0])
    rec = contract(game, town)
    hiring = [n for n in notices.notices(game, town) if n["kind"] == "hiring"]
    assert hiring and rec["quest"]["giver_name"] in hiring[0]["text"] and "Paid work" in hiring[0]["text"]


def test_contracts_are_kept_in_the_save(tables, tmp_path):
    from realmwalker.game import save

    game, town = a_life(tables, SEEDS[0])
    rec = contract(game, town)
    loaded = save.load_game(save.save_game(game, tmp_path), tables)
    recs = loaded.world.politics["contracts"][str(town.id)]
    assert recs[0]["id"] == rec["id"] and recs[0]["quest"]["reward"] == rec["quest"]["reward"]
