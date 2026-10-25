"""Allies with stakes (Expansion 6 F.1, docs/ADVENTURES.md §5.6): a tale's ally, once won, comes as a companion under
the bond "oath" with a stake of their own (or rides with the patron when the company is full, and fights beside you
in the tale's fights); their join condition may be a situation of its own (a parent to bury); their arc is a
confidence, a crisis and a fate (dying well at the finale, an oath to you, or home)."""

from types import SimpleNamespace

import pytest

from realmwalker.game import companions, story
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import prepare_town
from realmwalker.game.story import beats, cast, endings, situations, stakes
from realmwalker.rules.combat import PARTY
from tests.test_risen_outlaw import _open_chapter, _play, _step, _tale, _to_level, made, tables  # noqa: F401
from tests.test_situations import talk

pytestmark = pytest.mark.story


def _risen(made, tables):
    """A risen tale with its ally bound to a person of its town."""
    game, adv, t = _tale(made, tables, "risen")
    prepare_town(game, game.world.settlements[adv["places"]["town"]["settlement"]])
    ally = cast.person(game.world, adv["cast"]["ally"])
    if ally is None or not hasattr(ally, "job"):
        pytest.skip("this tale's ally is not a townsperson")
    return game, adv, ally


def _won(game, adv):
    beats.OPS["key"](game, {"adv": adv["id"]}, "ally")
    return adv["ally"]


def _no_words_left(text: str) -> bool:
    return "{" not in text and "}" not in text


def test_the_ally_comes_under_oath_with_a_stake_of_their_own(made, tables):
    game, adv, ally = _risen(made, tables)
    n = len(game.party)
    rec = _won(game, adv)
    c = stakes.companion_of(game, adv)
    assert rec["state"] == "joined" and len(game.party) == n + 1 and c is not None
    assert c.name == ally.name and companions.bond_of(c) == "oath" and c.companion["wage"] == 0
    assert c.level == game.leader.level, "a story's ally fights at the hero's level"
    assert rec["stake"] in tables.adventures["allies"]["stakes"]
    assert _no_words_left(rec["words"]["stake"]) and _no_words_left(rec["words"]["confidence"])
    assert rec["words"]["stake"] in companions.bond_text(game, c)
    assert stakes.journal_line(game, adv).startswith(ally.name)
    assert ally.flags.get("story"), "still cast in the tale: never moved on as a traveller"


def test_with_the_company_full_the_ally_rides_with_the_patron_and_fights_beside_you(made, tables, monkeypatch):
    from tools.arena import run

    game, adv, ally = _risen(made, tables)
    monkeypatch.setattr(companions, "room", lambda game: False)
    n = len(game.party)
    rec = _won(game, adv)
    assert rec["state"] == "riding" and len(game.party) == n, "no place taken in the party"
    _open_chapter(game, adv, 2)
    for kind in ("rally", "hold", "go", "rite"):
        _step(adv, kind, 2)["state"] = "done"
    adv["keys"] += ["anchor", "name", "ford"]
    for c in game.party:
        c.level = max(c.level, adv["target_level"])
    _to_level(game, adv["places"]["home"])
    band = next(a for a in game.local.actors if a.creatures and (getattr(a.creatures[0], "story", None) or {})
                .get("role") == "villain")
    assert story.hold_for_finale(game, band)
    story.fight_finale(game)
    b = game.battle
    beside = [f for f in b.side(PARTY) if f.bond is not None and f.bond.get("kind") == "story_ally"
              and f.char is not None]
    assert len(beside) == 1 and beside[0].char.name == ally.name, "the ally is on the field, a character of their own"
    assert beside[0].auto and stakes.fighting(b, adv)
    assert not any(f.char is not None and f.char.name == ally.name for f in b.side(PARTY) if f.bond is None)
    for f in b.side(PARTY):
        f.auto = True
    from realmwalker.rules.combat import FOE

    for f in b.side(FOE):
        f.hp = 1  # (the fight itself is not what is measured here: storyplay does that)
    for f in b.side(PARTY):
        f.hp = 400
    run(b, max_steps=4000)
    assert b.outcome == "victory"
    from realmwalker.game import fight

    fight.finish_battle(game)
    assert rec["at_finale"] and rec["state"] == "riding", "remembered as one who stood at the end"
    game.battle, beside[0].state = b, "dead"  # (had they fallen there)
    stakes.on_battle(game, None)
    assert rec["state"] == "fell" and not ally.alive


def test_the_join_condition_is_a_grave_to_dig(made, tables, monkeypatch):
    game, adv, ally = _risen(made, tables)
    preds = situations.predicaments(tables)
    monkeypatch.setitem(preds["ally_unburied"], "inside", dict(preds["ally_unburied"]["inside"], chance=1.0))
    monkeypatch.setitem(preds["ally_doubts"], "inside", dict(preds["ally_doubts"]["inside"], step="none"))
    _open_chapter(game, adv, 1)
    st = _step(adv, "recruit", 1)
    Conversation(game, ally).menu()  # (talking to them: the step becomes their situation)
    sit = situations.of_step(game, st)
    assert sit is not None and sit["predicament"] == "ally_unburied"
    from tools import storybook

    assert not storybook.situation_words(game, sit) + storybook.situation_rules(game, sit)
    talk(game, ally, "sit_ask")
    talk(game, ally, "sit_take")
    game.leader.money += 5000
    talk(game, ally, "sit_act", act="priest")
    assert sit["ending"] == "buried" and "ally" in adv["keys"]
    assert st["state"] == "done" and adv["ally"]["state"] == "joined", "and once the grave is dug, they come"


def test_the_confidence_then_a_crisis_by_the_fire(made, tables, monkeypatch):
    game, adv, ally = _risen(made, tables)
    rec = _won(game, adv)
    today = int(game.moment.total_days)
    rec["joined"] = today - 3
    assert story.on_night(game, "camp")
    pend = beats.pending(game)
    assert pend["beat"] == "ally_confidence"
    pages = beats.pages(game, pend)
    assert rec["words"]["confidence"] in pages[1] and all(_no_words_left(p) for p in pages)
    c = stakes.companion_of(game, adv)
    before = c.companion["loyalty"]
    _play(game, 1)
    assert rec["told"] == today and "ally_promised" in adv["flags"] and c.companion["loyalty"] > before
    _open_chapter(game, adv, 1)
    rec["told"] = today - 5
    monkeypatch.setitem(tables.adventures["allies"]["arc"], "crisis_chance", 1.0)
    assert story.on_night(game, "camp")
    pend = beats.pending(game)
    kind = tables.adventures["allies"]["stakes"][rec["stake"]]["crisis"]
    assert pend["beat"] == stakes.CRISES[kind] and rec["crisis"] == kind
    assert all(_no_words_left(p) for p in beats.pages(game, pend))
    _play(game, 2)  # (let them go)
    assert rec["state"] in ("broke", "home") and stakes.companion_of(game, adv) is None
    assert "ally" not in adv["keys"], "the key goes with them"
    endings.finish(game, adv)
    page = next(p for p in adv["epilogue"] if p["about"] == "ally")
    assert rec["fate"] in ("broke", "home") and _no_words_left(page["text"]) and ally.first_name in page["text"]


def test_one_who_rides_with_the_patron_may_be_taken(made, tables, monkeypatch):
    from realmwalker.game.story import villain

    game, adv, ally = _risen(made, tables)
    monkeypatch.setattr(companions, "room", lambda game: False)
    rec = _won(game, adv)
    if villain.lair(game, adv) is None:
        pytest.skip("this villain keeps no hall")
    rec["told"] = int(game.moment.total_days) - 5
    _open_chapter(game, adv, 1)
    monkeypatch.setitem(tables.adventures["allies"]["arc"], "crisis_chance", 1.0)
    assert story.on_night(game, "inn")
    assert beats.pending(game)["beat"] == "ally_crisis_taken"
    _play(game)
    assert rec["state"] == "taken" and ally.flags.get("kidnapped")
    assert any(st.get("kidnap") for st in story.chapter(adv)["steps"]), "a rescue joins the chapter"


def test_the_fates_dying_well_an_oath_or_home(made, tables):
    game, adv, ally = _risen(made, tables)
    rec = _won(game, adv)
    c = stakes.companion_of(game, adv)
    game.party.remove(c)
    companions.died(game, c)
    rec["at_finale"] = True
    adv["boss_dead"] = True
    endings.finish(game, adv)
    page = next(p for p in adv["epilogue"] if p["about"] == "ally")
    assert rec["fate"] == "fell_well" and page["text"] in [
        stakes._say(game, adv, [x], game.world.rng) for x in tables.adventures["allies"]["fates"]["fell_well"]]

    for choice, bond in ((0, "pledged"), (1, None)):
        game, adv, ally = _risen(made, tables)
        rec = _won(game, adv)
        adv["boss_dead"] = True
        endings.finish(game, adv)
        assert adv["state"] == "won" and rec.get("fate_due"), "asked at the next night's fire"
        game.epilogue = None
        assert story.on_night(game, "camp") and beats.pending(game)["beat"] == "ally_fate"
        _play(game, choice)
        c = next((x for x in game.party if x.name == ally.name), None)
        if bond:
            assert rec["fate"] == "sworn" and c is not None and companions.bond_of(c) == bond
            assert "adv" not in c.companion and not ally.flags.get("story")
        else:
            assert rec["fate"] == "home" and c is None and ally.present


def test_a_retreat_that_breaks_the_ally_sends_them_home(made, tables):
    from realmwalker.game.story import defeat

    game, adv, ally = _risen(made, tables)
    rec = _won(game, adv)
    tables.adventures["retreat"]["ally_lost"], was = 1.0, tables.adventures["retreat"]["ally_lost"]
    try:
        defeat.on_retreat(game, SimpleNamespace(finale_of=adv["id"], story_bosses={}, fighters=[]))
    finally:
        tables.adventures["retreat"]["ally_lost"] = was
    assert rec["state"] == "home" and stakes.companion_of(game, adv) is None


def test_the_ally_data_passes_the_start_up_check(tables):
    from realmwalker.game.story import check

    assert [p for p in check.problems(tables) if "ally" in p or "allies" in p] == []
    sp = tables.adventures["allies"]
    for sid, s in sp["stakes"].items():
        assert len(s["stake"]) >= 3 and len(s["confidence"]) >= 3, sid
    for fate in ("fell_well", "fell", "broke", "home", "sworn"):
        assert len(sp["fates"][fate]) >= 3, fate
