"""The Reading (Expansion 6 F.4, docs/ADVENTURES.md §5.7): the Wayfarer's Deck (twenty great cards, four suits, the
game's own), seers at the crossroads and in cities and hermits at wonders, the reading staged at the seer's fire (the
beat, then the cards laid out as a picture), riddles written from the true places' own pasts, silent cards read again
after the next chapter, the villain's own card (it knows, and strikes first at the one the Hand named), the cards'
imagery pointed out when met, and the Hand never the traitor."""

import copy

import pytest
import tcod.console

from realmwalker.game import story
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import make_npc, npcs_in, prepare_town
from realmwalker.game.story import beats, check, places, reading, traitors, villain
from realmwalker.ui.gfx import headless
from realmwalker.ui.gfx.scene import Sprite
from realmwalker.ui.widgets import Canvas
from tests.test_risen_outlaw import _open_chapter, _tale, made, tables  # noqa: F401

pytestmark = pytest.mark.story


def _whole(text: str) -> bool:
    return bool(text) and "{" not in text and "}" not in text


def _seer(game, adv):
    """A seer in the tale's own town (made there if the roads do not meet at it)."""
    s = game.world.settlements[adv["places"]["town"]["settlement"]]
    prepare_town(game, s)
    found = [n for n in npcs_in(game.world, s.id) if n.job == "seer"]
    if found:
        return found[0]
    npc = make_npc(game, s, "seer", game.world.rng.child("test-seer"), post=(1, 1), home=(1, 1))
    game.world.npcs[npc.id] = npc
    game.world.towns[s.id].npcs.append(npc.id)
    return npc


def _read(game, adv, monkeypatch, *, silent=0.0, villain_card=0.0, how=0):
    sp = game.tables.reading
    monkeypatch.setitem(sp["silent"], "chance", silent)
    monkeypatch.setitem(sp["villain_card"], "chance", villain_card)
    monkeypatch.setitem(sp["villain_card"], "per_attention", 0.0)
    npc = _seer(game, adv)
    game.player.x, game.player.y = npc_xy = places.xy(game.world, adv["places"]["town"])
    conv = Conversation(game, npc)
    opts = [c for c in conv.menu() if c.id == "story_reading"]
    assert opts, "a seer offers to read the cards"
    conv.choose(opts[0])
    rec = beats.pending(game)
    assert rec is not None and rec["beat"] == reading.BEAT, "the reading is staged as a beat at the seer's fire"
    for c in game.party:
        c.money = 10_000
    lines = beats.choose(game, rec, how)
    assert all(_whole(x) for x in lines if x)
    assert beats.director(game.world).get("reading") == {"adv": adv["id"]}, "the cards' screen waits"
    assert npc_xy
    return adv["reading"]


def test_the_deck_and_its_words_pass_the_start_up_check(tables):
    assert [p for p in check.problems(tables) if "reading" in p] == []
    sp = tables.reading
    assert len(sp["great"]) == 20 and set(sp["suits"]) == {"blades", "coins", "cups", "stones"}
    names = {c["name"].lower() for c in sp["great"].values()}
    assert "the ford" in names and "the widow" in names and "the wolf" in names
    assert "seer" in tables.people["occupations"] and reading.BEAT in tables.beats


def test_a_reading_lays_five_cards_whose_truths_fit_and_whose_riddles_hide_the_names(made, tables, monkeypatch):
    for kind in ("beast", "risen", "outlaw"):
        game, adv, t = _tale(made, tables, kind)
        rec = _read(game, adv, monkeypatch)
        assert set(rec["cards"]) == set(reading.POSITIONS)
        deck = tables.reading["great"]
        cards = [c["card"] for c in rec["cards"].values()]
        assert len(set(cards)) == 5, "no card twice on the cloth"
        for pos, c in rec["cards"].items():
            assert not c["silent"], (kind, pos)
            assert _whole(c["riddle"]), (kind, pos, c["riddle"])
            tags = set(c["truth"].get("tags", []))
            if tags & set().union(*(set(d["tags"]) for d in deck.values())):
                assert tags & set(deck[c["card"]]["tags"]), (kind, pos, c["card"], tags)  # (the truth came first)
            if c["truth"].get("place"):
                name = places.name(game.world, c["truth"]["place"])
                assert name not in c["riddle"], (kind, pos, c["riddle"])  # (a riddle does not say the answer)
        door = rec["cards"]["door"]["truth"]["place"]
        assert door.get("site") == adv["places"]["home"]["site"], "the door is the villain's own hall"
        hand = rec["cards"]["hand"]["truth"]
        assert rec["named"] is not None and hand["npc"] == rec["named"], "the Hand names a person, by npc id"
        journal = " ".join(e["text"] for e in adv["journal"])
        assert "read the cards" in journal and rec["cards"]["key"]["riddle"] in journal


def test_a_beasts_shadow_is_its_true_weakness(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "beast")
    rec = _read(game, adv, monkeypatch)
    sh = rec["cards"]["shadow"]
    weak = adv["hidden"]["weakness"]["weakness"]
    w = next(x for lst in tables.villains["weaknesses"].values() for x in lst if x["id"] == weak)
    assert sh["truth"]["key"] == "weakness"
    assert sh["truth"]["fear"] in tables.reading["shadows"][w["name"]]["words"]
    out = beats.OPS["key"](game, {"adv": adv["id"]}, "weakness")
    assert any(sh["truth"]["fear"] in x for x in out), "the shadow pointed out when its key is found"
    assert "shadow" in rec["pointed"]


def test_silent_cards_are_read_again_after_the_next_chapter(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "risen")
    rec = _read(game, adv, monkeypatch, silent=1.0)
    silent = [p for p, c in rec["cards"].items() if c["silent"]]
    assert len(silent) == tables.reading["silent"]["most"], "never more than the deck allows go silent"
    assert all(_whole(rec["cards"][p]["riddle"]) for p in silent)
    beats.director(game.world)["reading"] = None
    assert reading.readable(game, adv) is None
    npc = _seer(game, adv)
    conv = Conversation(game, npc)
    conv.choose(next(c for c in conv.menu() if c.id == "story_reading"))
    assert beats.pending(game) is None, "not again in the same chapter"
    _open_chapter(game, adv, 1)
    assert reading.readable(game, adv) == "again"
    rec = _read(game, adv, monkeypatch, silent=1.0, how=1)
    assert not any(rec["cards"][p]["silent"] for p in silent), "the silent cards speak the second time"
    assert rec["times"] == 2


def test_the_villains_card_raises_its_attention_and_it_strikes_at_the_one_named(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "beast")
    before = int(adv.get("attention", 0))
    rec = _read(game, adv, monkeypatch, villain_card=1.0)
    assert rec.get("villain") and rec["villain_knows"]
    assert int(adv["attention"]) > before, "the villain learns of the reading"
    assert _whole(rec["villain"]["voice"])
    named = game.world.npcs[rec["named"]]
    game.player.x, game.player.y = 0, 0  # (away from their town)
    role = next(r for r, e in adv["cast"].items() if isinstance(e, dict) and e.get("npc") == named.id)
    needing = [st for ch in adv["chapters"] for st in ch["steps"] if st["state"] != "done" and
               role in {st["target"].get("role")} | {r.get("role") for r in st["target"].get("routes", [])}]
    if needing:
        assert villain._helper(game, adv) != named.id, "never one a step still needs: the tale stays winnable"
        for st in needing:
            st["state"] = "done"
    assert villain._helper(game, adv) == named.id, "it strikes first at the one the cards favour"


def test_the_hand_is_never_the_traitor_and_the_turn_warns_of_one(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "risen")
    rec = _read(game, adv, monkeypatch)
    named = rec["named"]
    _open_chapter(game, adv, 1)
    assert all(int(getattr(w, "id", -1)) != named for _, w in traitors._candidates(game, adv))
    # a hidden traitor: the turn is their warning, and counts as one of their tells
    adv["traitor"] = {"role": "companion", "npc": None, "name": "Hal Sorrel", "first": "Hal", "sex": "male",
                      "reason": "paid", "used": {"near": [], "far": []}, "seen": 0, "last": 0, "state": "hidden",
                      "made": 0}
    beats.director(game.world)["reading"] = None
    rec = _read(game, adv, monkeypatch, how=1)
    assert rec["cards"]["turn"]["truth"]["what"] == "traitor"
    assert adv["traitor"]["seen"] == 1
    assert rec["cards"]["turn"]["card"] == "mask" or "traitor" in tables.reading["great"][
        rec["cards"]["turn"]["card"]]["tags"]


def test_the_cards_imagery_is_pointed_out_where_it_is_met(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "beast")
    rec = _read(game, adv, monkeypatch)
    said = []
    monkeypatch.setattr(game, "say", lambda text, *a, **k: said.append(text))
    door = rec["cards"]["door"]["truth"]["place"]
    game.player.x, game.player.y = places.xy(game.world, door)
    story.on_arrive(game)
    card = tables.reading["great"][rec["cards"]["door"]["card"]]["name"]
    assert any(card.lower() in s.lower() for s in said), said
    assert "door" in rec["pointed"]
    named = game.world.npcs[rec["named"]]
    conv = Conversation(game, named)
    conv.greet()
    notes = " ".join(t for k, t in conv.lines if k == "note")
    assert tables.reading["great"][rec["cards"]["hand"]["card"]]["name"].lower() in notes.lower()


def test_seers_keep_fires_where_the_roads_meet_and_hermits_at_wonders(made, tables):
    game, adv, t = _tale(made, tables, "beast")
    w = game.world
    cities = [s for s in w.settlements if s.kind == "city"]
    assert cities and all(reading.keeps_seer(game, s) for s in cities)
    cross = [s for s in w.settlements if reading.crossroads(w, s)]
    s = (cross or cities)[0]
    prepare_town(game, s)
    assert any(n.job == "seer" for n in npcs_in(w, s.id)), "a seer by the gate"
    hermits = [wd for wd in w.wonders if reading.hermit_at(game, wd.x, wd.y) is not None]
    if not hermits:
        pytest.skip("no hermit at this world's wonders")
    wd = hermits[0]
    game.player.x, game.player.y = wd.x, wd.y
    beats.director(w)["pending"] = None
    assert reading.hermit(game)
    rec = beats.pending(game)
    assert rec["beat"] == reading.BEAT and wd.name in " ".join(beats.pages(game, rec))
    beats.director(w)["pending"] = None
    assert not reading.hermit(game), "once a week"


def test_the_cards_are_laid_out_as_a_picture(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "outlaw")
    rec = _read(game, adv, monkeypatch, villain_card=1.0)
    from realmwalker.ui.gfx import cards

    canvas = Canvas(tcod.console.Console(80, 30, order="F"), gfx=headless())
    spots = cards.table(canvas, game, (0, 0, 640, 360), rec, 1.0, "hand")
    names = {c.name for layer in canvas.layers for c in layer.under if isinstance(c, Sprite)}
    assert {f"card/{c['card']}" for c in rec["cards"].values()} <= names
    assert f"card/{rec['villain']['card']}" in names and "villain" in spots
    assert any(n.startswith("card/suit_") for n in names) and any(n.startswith("feature/campfire") for n in names)
    atlas = canvas.gfx.atlas
    for cid in list(tables.reading["great"]) + [f"suit_{s}" for s in tables.reading["suits"]] + ["back"]:
        assert atlas.has(f"card/{cid}"), cid


@pytest.fixture
def pictured(make_app, made):
    from realmwalker.game.state import new_game

    app = make_app()
    game = new_game(copy.deepcopy(made), app.tables)
    game.survival = False
    app.start_game(game)
    return app, game


def test_the_readings_screen_opens_draws_and_closes(pictured, monkeypatch):
    from realmwalker.ui.input import KeyEvent

    app, game = pictured
    from realmwalker.world import threats

    t = next((t for t in threats.records(game.world).values() if t["kind"] == "beast" and t["state"] != "ended"),
             None)
    if t is None:
        pytest.skip("no beast here")
    if t["state"] == "dormant":
        threats.stir(game.world, app.tables, t, game.world.rng, day=0)
    beats.director(game.world)["pending"] = None
    beats.director(game.world)["opening"] = None
    story.take_hook(game, t["id"])
    beats.director(game.world)["card"] = None
    adv = story.active(game)[0]
    for c in game.party:
        c.money = 10_000
    reading.lay(game, adv, "Old Maud")

    def render():
        con = tcod.console.Console(100, 40, order="F")
        app.render(con)
        app.update()
        return app.last_canvas

    render()
    canvas = render()
    assert type(app.screens[-1]).__name__ == "ReadingScreen"
    words = canvas.words()
    assert "The Key" in words and adv["reading"]["cards"]["key"]["riddle"][:20] in words
    app.handle_event(KeyEvent("right"))
    canvas = render()
    assert "The Turn" in canvas.words()
    app.handle_event(KeyEvent("enter"))
    render()
    assert beats.director(game.world).get("reading") is None
    assert app.error_count == 0


def test_a_traitor_chosen_before_the_reading_is_never_the_hand(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "risen")
    prepare_town(game, game.world.settlements[adv["places"]["town"]["settlement"]])
    first = reading._hand_truth(game, adv, game.world.rng.child("t"))
    assert first and first["npc"] is not None
    adv["traitor"] = {"role": "ally", "npc": first["npc"], "name": "X", "first": "X", "sex": "male",
                      "reason": "kin", "used": {"near": [], "far": []}, "seen": 0, "last": 0, "state": "hidden",
                      "made": 0}
    rec = _read(game, adv, monkeypatch)
    assert rec["named"] != first["npc"], "the cards never name the one who serves the villain"
