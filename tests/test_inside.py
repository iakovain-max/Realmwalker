"""Situations inside adventures (Expansion 6 C.10, docs/ADVENTURES.md §5.16): the Beast's witness who will not speak
and the hunter who will not hunt are situations bound to the tale's step; however they end, the step goes on."""

import pytest

from realmwalker.game import story
from realmwalker.game.people import prepare_town
from realmwalker.game.story import cast, situations, stage
from tests.test_beast_shown import _enter, _run, _tale, made, tables  # noqa: F401
from tests.test_situations import talk

pytestmark = pytest.mark.story


def _always(monkeypatch, tables, pid):
    spec = situations.predicaments(tables)[pid]
    monkeypatch.setitem(spec, "inside", dict(spec["inside"], chance=1.0))


def _step(adv, kind):
    return next(st for ch in adv["chapters"] for st in ch["steps"] if st["kind"] == kind)


def _witness_sit(made, tables, monkeypatch):
    _always(monkeypatch, tables, "silent_witness")
    game, adv = _tale(made, tables)
    town = game.world.settlements[adv["places"]["town"]["settlement"]]
    prepare_town(game, town)
    witness = cast.person(game.world, adv["cast"]["witness"])
    if witness is None or witness.settlement != town.id:
        pytest.skip("the witness is not of the town")
    _enter(game, town)
    st = _step(adv, "witness")
    sit = situations.of_step(game, st)
    assert sit is not None and sit["predicament"] == "silent_witness", "the witness's step became a situation"
    from tools import storybook

    assert not storybook.situation_words(game, sit) + storybook.situation_rules(game, sit)
    return game, adv, st, sit, witness


def test_the_witness_who_will_not_speak_is_met_in_a_scene_and_tells_once_the_kin_stands_aside(made, tables,
                                                                                              monkeypatch):
    from realmwalker.game.dialogue import Conversation

    game, adv, st, sit, witness = _witness_sit(made, tables, monkeypatch)
    assert sit["adventure"] == adv["id"] and situations.asker(game, sit) is witness
    assert (witness.flags.get("story") or {}).get("adv") == adv["id"], "the witness keeps their part in the tale"
    assert stage.current(game) is None or stage.current(game)["id"] != "survivor", "no plain telling in the street"
    assert _run(game, lambda: sit["state"] == "met"), "met in its own scene"
    assert not any(c.id == "story_witness" for c in Conversation(game, witness).menu()), "the plain question waits"
    stage.settle(game, game.local)
    game.talk_to = None
    talk(game, witness, "sit_take")
    kin = situations._npc(game, sit, "kin")
    game.leader.money += 5000
    talk(game, kin, "sit_act", act="pay")
    clues = len(adv.get("clues", []))
    talk(game, witness, "sit_act", act="tell")
    assert sit["state"] == "done" and sit["ending"] == "told", "told with the kin's leave"
    assert st["state"] == "done", "and the tale's witness step is done"
    assert len(adv.get("clues", [])) > clues or "name" in str(adv.get("clues")), "with what it gives"


def test_a_witness_left_alone_tells_it_in_the_end(made, tables, monkeypatch):
    game, adv, st, sit, witness = _witness_sit(made, tables, monkeypatch)
    sit["clock"]["due"] = int(game.moment.total_days)  # (the clock runs out: the world's own outcome)
    situations.daily(game)
    assert sit["state"] == "lapsed" and st["state"] == "done", "the tale is never stuck"


def test_the_hunter_who_will_not_hunt_comes_when_the_oath_is_answered(made, tables, monkeypatch):
    _always(monkeypatch, tables, "hunter_holds_back")
    game, adv = _tale(made, tables)
    adv["chapter"] = next(i for i, ch in enumerate(adv["chapters"]) if ch["id"] == "price")
    st = _step(adv, "learn")
    route = next((r for r in st["target"]["routes"] if r.get("role") == "ally"), None)
    if route is None or "settlement" not in (route.get("who") or {}):
        pytest.skip("this tale's hunter is not a townsperson")
    town = game.world.settlements[int(route["who"]["settlement"])]
    prepare_town(game, town)
    _enter(game, town)
    stage.settle(game, game.local)
    sit = situations.of_step(game, st)
    assert sit is not None and sit["predicament"] == "hunter_holds_back"
    hunter = situations.asker(game, sit)
    from tools import storybook

    assert not storybook.situation_words(game, sit) + storybook.situation_rules(game, sit)
    assert cast.person(game.world, adv["cast"]["ally"]) is hunter
    talk(game, hunter, "sit_ask")
    talk(game, hunter, "sit_take")
    talk(game, hunter, "sit_act", act="why")
    from realmwalker.game import dialogue

    monkeypatch.setattr(dialogue.Conversation, "check", lambda self, skill, dc: (True, "You find the words."))
    talk(game, hunter, "sit_act", act="swear")
    assert sit["ending"] == "comes" and "ally" in adv["keys"], "the hunter will stand with you"
    assert st["state"] == "done", "and has told you what it fears"
    assert story.chapter(adv) is not None


def test_ordinary_forging_never_makes_an_adventure_s_situation(made, tables):
    from realmwalker.game import townlife
    from tests.test_first_hour import SEEDS, a_life

    townlife.forget()
    game, s = a_life(tables, SEEDS[0])
    for pid in situations.inside(tables, "witness") + situations.inside(tables, "learn", "ally"):
        assert situations.make(game, s.id, predicament=pid) is None


def test_the_hunter_left_alone_keeps_the_oath_and_the_other_routes_stay(made, tables, monkeypatch):
    from realmwalker.game.dialogue import Conversation

    _always(monkeypatch, tables, "hunter_holds_back")
    game, adv = _tale(made, tables)
    adv["chapter"] = next(i for i, ch in enumerate(adv["chapters"]) if ch["id"] == "price")
    st = _step(adv, "learn")
    route = next((r for r in st["target"]["routes"] if r.get("role") == "ally"), None)
    if route is None or "settlement" not in (route.get("who") or {}):
        pytest.skip("this tale's hunter is not a townsperson")
    town = game.world.settlements[int(route["who"]["settlement"])]
    prepare_town(game, town)
    _enter(game, town)
    stage.settle(game, game.local)
    sit = situations.of_step(game, st)
    assert sit is not None
    hunter = situations.asker(game, sit)
    sit["clock"]["due"] = int(game.moment.total_days)
    situations.daily(game)
    assert sit["state"] == "lapsed" and st["state"] == "open" and "ally" not in adv["keys"], "the oath holds"
    assert not any(c.id == "story_learn" for c in Conversation(game, hunter).menu()), "the hunter will not tell it"
    assert any(r.get("how") != "talk" or r.get("role") != "ally" for r in st["target"]["routes"]), \
        "and the truth has its other routes"


def test_a_step_done_another_way_ends_its_situation_quietly(made, tables, monkeypatch):
    game, adv, st, sit, witness = _witness_sit(made, tables, monkeypatch)
    story.step_done(game, adv["id"], st["id"])
    situations.daily(game)
    assert sit["state"] == "lapsed" and sit["ending"] == "moot"
    assert (witness.flags.get("story") or {}).get("adv") == adv["id"], "the witness keeps their part in the tale"


def test_the_board_posts_the_nearest_den_and_takes_it_down_once_cleared(made, tables):
    from realmwalker.game import notices, quests

    game, adv = _tale(made, tables)
    town = game.world.settlements[adv["places"]["town"]["settlement"]]
    prepare_town(game, town)
    dens = [q for q in quests.board_bounties(game, town) if q["template"] == "clear_lair"]
    if not dens:
        pytest.skip("no den near this town")
    q = dens[0]
    assert len(dens) == quests.DENS
    poster = next(n for n in notices.notices(game, town) if n.get("bounty") is q)
    assert game.world.sites[q["target"]["site"]].name in poster["text"] and "{" not in poster["text"]
    game.world.politics.setdefault("cleared", []).append(q["target"]["site"])  # (cleared by someone else's work)
    again = [x for x in quests.board_bounties(game, town) if x["template"] == "clear_lair"]
    assert all(x["target"]["site"] != q["target"]["site"] for x in again), "a cleared den comes down"
    if again:
        quests.accept(game, again[0])
        assert again[0] in game.quests
        assert not any(x is again[0] for x in quests.board_bounties(game, town)), "and a taken one too"
