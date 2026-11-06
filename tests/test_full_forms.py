"""The three tales' full forms (Expansion 6 F.5, docs/ADVENTURES.md §6.2): each its own rival (the Beast's
glory-hunter, the Risen's barrow-breakers after the gold, the Outlaw's lord's own captain), its own traitor (the
Risen's patron who paid the waker, found out when the waker falls; the Outlaw's informer's cut of the toll), and the
Outlaw's ally (a robbed carter or a deserter who wants out)."""

import pytest

from realmwalker.game import story
from realmwalker.game.people import prepare_town
from realmwalker.game.story import beats, cast, check, patrons, rivals, stakes, traitors
from tests.test_risen_outlaw import _open_chapter, _step, _tale, made, tables  # noqa: F401

pytestmark = pytest.mark.story

OWN = {"beast": "hunter", "risen": "graverobbers", "outlaw": "captain"}


def _whole(text: str) -> bool:
    return bool(text) and "{" not in text and "}" not in text


def _only_own(game, adv, monkeypatch):
    rv = game.tables.adventures["rivals"]
    monkeypatch.setitem(rv["chance"], adv["blueprint"], 1.0)
    monkeypatch.setitem(rv, "kinds", {k: v for k, v in rv["kinds"].items() if v.get("blueprints")})
    adv.pop("rival", None)
    rivals.decide(game, adv)
    return adv["rival"]


@pytest.mark.parametrize("kind", ["beast", "risen", "outlaw"])
def test_each_tale_has_its_own_rival_and_prize(made, tables, monkeypatch, kind):
    game, adv, _ = _tale(made, tables, kind)
    r = _only_own(game, adv, monkeypatch)
    assert r is not None and r["kind"] == OWN[kind]
    assert _whole(r["who"]) and _whole(r["band_words"])
    r["prize"] = "finale"
    prize = rivals.prize_name(game, adv)
    assert _whole(prize) and not prize.endswith("'s head") or kind == "beast"
    creatures = rivals.band(game, adv, r, game.world.rng.child("t"))
    assert len(creatures) >= 2 and creatures[0].name == r["name"]


def test_another_tales_own_rival_never_rides_in_this_one(made, tables, monkeypatch):
    game, adv, _ = _tale(made, tables, "outlaw")
    rv = game.tables.adventures["rivals"]
    monkeypatch.setitem(rv["chance"], "outlaw", 1.0)
    monkeypatch.setitem(rv, "kinds", {"graverobbers": rv["kinds"]["graverobbers"]})
    adv.pop("rival", None)
    rivals.decide(game, adv)
    assert adv["rival"] is None


def _risen_patron_traitor(game, adv, monkeypatch):
    prepare_town(game, game.world.settlements[adv["places"]["town"]["settlement"]])
    if patrons.npc(game, adv) is None:
        pytest.skip("this tale's patron is not a townsperson")
    tr = game.tables.adventures["traitors"]
    monkeypatch.setitem(tr["chance"], "risen", 1.0)
    monkeypatch.setitem(tr, "from_by", {"risen": {"patron": 1}})
    adv.pop("traitor", None)
    patrons.decide(game, adv)
    adv["patron"]["motive"] = "plain"
    _open_chapter(game, adv, 1)
    traitors.decide(game, adv)
    return adv["traitor"]


def test_the_risen_patron_paid_the_waker_and_the_waker_gives_them_away(made, tables, monkeypatch):
    game, adv, _ = _tale(made, tables, "risen")
    rec = _risen_patron_traitor(game, adv, monkeypatch)
    assert rec is not None and rec["role"] == "patron"
    reasons = tables.adventures["traitors"]["reasons"]
    if rec["reason"] != "woke":
        monkeypatch.setitem(tables.adventures["traitors"], "reasons", {"woke": reasons["woke"]})
        rec["reason"] = "woke"
    assert _whole(rec["why"])
    traitors.daily(game)
    assert not rec.get("waker"), "nothing found while the waker stands"
    _step(adv, "defeat", 1)["state"] = "done"
    traitors.daily(game)
    assert rec["waker"] == "due"
    assert traitors.on_night(game, "inn", morning=True)
    pending = beats.pending(game)
    assert pending["beat"] == "traitor_tell" and rec["waker"] == "told" and rec["seen"] == 1
    assert _whole(pending["words"]["tell"])
    assert any("Something is wrong about" in e.get("text", "") for e in adv.get("journal", []))


def test_the_waker_tell_belongs_to_the_risen_patron_alone(made, tables):
    reasons = tables.adventures["traitors"]["reasons"]
    assert reasons["woke"]["blueprints"] == ["risen"] and reasons["woke"]["roles"] == ["patron"]
    assert reasons["toll"]["blueprints"] == ["outlaw"]
    assert not any(v.get("waker") for k, v in reasons.items() if k != "woke")


def test_the_outlaw_has_an_ally_with_a_stake_of_the_road(made, tables):
    game, adv, _ = _tale(made, tables, "outlaw")
    assert "ally" in adv["cast"], "the Outlaw's tale casts an ally"
    rec = _step(adv, "recruit")
    assert rec.get("optional") and rec["target"]["role"] == "ally"
    prepare_town(game, game.world.settlements[adv["places"]["town"]["settlement"]])
    ally = cast.person(game.world, adv["cast"]["ally"])
    if ally is None or not hasattr(ally, "job"):
        pytest.skip("this tale's ally is not a townsperson")
    beats.OPS["key"](game, {"adv": adv["id"]}, "ally")
    a = adv["ally"]
    assert a["state"] in ("joined", "riding")
    st = tables.adventures["allies"]["stakes"][a["stake"]]
    assert "outlaw" in st.get("blueprints", ["outlaw"]) and ally.job in st.get("jobs", [ally.job])
    own = [k for k, s in tables.adventures["allies"]["stakes"].items() if "outlaw" in s.get("blueprints", ())]
    assert {"robbed_road", "deserter_out"} <= set(own), "the road's own stakes (weighted up by stakes.OWN_WEIGHT)"
    assert _whole(a["words"]["stake"]) and _whole(a["words"]["confidence"])
    assert stakes.journal_line(game, adv)


def test_the_full_forms_pass_the_start_up_check(tables):
    assert not [p for p in check.problems(tables) if "rival" in p or "traitor" in p or "ally" in p]


def test_story_tale_words_fill_for_every_own_kind(made, tables, monkeypatch):
    """Every line of each own rival kind and own traitor reason fills whole in its own tale."""
    from realmwalker.core import textgen

    for kind in ("risen", "outlaw"):
        game, adv, _ = _tale(made, tables, kind)
        r = _only_own(game, adv, monkeypatch)
        words = rivals._words(game, adv)
        ks = tables.adventures["rivals"]["kinds"][r["kind"]]
        rng = game.world.rng.child("w")
        for line in ks["who"] + ks["band_words"] + ks["prize"]:
            assert _whole(textgen.fill(line, rng, tables.adventures.get("words", {}), words)), line
        adv["traitor"] = {"role": "patron", "first": "Odo", "name": "Odo Mill", "sex": "male", "why": ""}
        tw = traitors._words(game, adv)
        for rk, rs in tables.adventures["traitors"]["reasons"].items():
            if kind not in rs.get("blueprints", [kind]):
                continue
            for line in rs["why"] + rs["near"] + rs["far"] + rs.get("waker", []):
                assert _whole(textgen.fill(line, rng, tables.adventures.get("words", {}), tw)), (rk, line)
        monkeypatch.undo()
        assert story.adventures(game.world)
