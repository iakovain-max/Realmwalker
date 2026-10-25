"""Rivals (Expansion 6 F.2, docs/ADVENTURES.md §5.6): a band after the same prize on its own clock - met at an inn or a
camp; reaching the thing to fetch first (bought, given, taken from them or let go), going into the villain's hall
first and found dead there (its wounds carried into the finale); a truce that brings them to the finale, a plea for
help answered in a fight beside them, a theft, your road sold, an ambush; their relation from -2 to 2; their page in
the epilogue."""

import pytest

from realmwalker.game import fight, quests, story
from realmwalker.game.story import beats, endings, rivals
from realmwalker.rules.combat import FOE, PARTY
from tests.test_finale_arenas import _den, _fight  # noqa: F401
from tests.test_risen_outlaw import _open_chapter, _play, _step, _tale, _to_level, made, tables  # noqa: F401

pytestmark = pytest.mark.story


def _with_rival(game, adv, monkeypatch, kind=None, relation=None):
    rv = game.tables.adventures["rivals"]
    monkeypatch.setitem(rv["chance"], adv["blueprint"], 1.0)
    if kind is not None:
        monkeypatch.setitem(rv, "kinds", {kind: rv["kinds"][kind]})
    adv.pop("rival", None)
    rivals.decide(game, adv)
    r = adv["rival"]
    if relation is not None:
        r["relation"] = relation
    return r


def _meet(game, adv, r, choice=0):
    r["made"] = int(game.moment.total_days) - 5
    assert rivals.on_night(game, "camp")
    rec = beats.pending(game)
    assert rec["beat"] == "rival_meeting"
    return beats.choose(game, rec, choice)


def _no_slots(text):
    return "{" not in text and "}" not in text


def _battle(game, *, win=True):
    from tools.arena import run

    enc = game.encounter
    assert enc is not None, "a fight waits"
    game.encounter = None
    b = fight.start_battle(game, enc.creatures, enc.intro)
    for f in b.side(PARTY):
        f.auto = True
        if win:
            f.hp = 400
    if win:
        for f in b.side(FOE):
            f.hp = 1
    run(b, max_steps=4000)
    fight.finish_battle(game)
    return b


def test_every_kind_of_rival_is_made_and_written_whole(made, tables, monkeypatch):
    game, adv, _ = _tale(made, tables, "beast")
    for kind in tables.adventures["rivals"]["kinds"]:
        r = _with_rival(game, adv, monkeypatch, kind=kind)
        assert r["kind"] == kind and r["state"] == "unmet" and -2 <= r["relation"] <= 2
        assert r["name"] and _no_slots(r["who"]) and _no_slots(r["band_words"])
        creatures = rivals.band(game, adv, r, game.world.rng.child("t"))
        assert len(creatures) >= 2 and creatures[0].name == r["name"], "a leader by name and a band"
        assert all(c.story["role"] == "rival" for c in creatures)
        monkeypatch.undo()


def test_a_tale_has_one_rival_or_none_decided_once(made, tables):
    game, adv, _ = _tale(made, tables, "beast")
    adv.pop("rival", None)
    story.daily(game)
    first = adv["rival"]
    rivals.decide(game, adv)
    assert adv["rival"] is first


def test_the_meeting_starts_their_race(made, tables, monkeypatch):
    game, adv, _ = _tale(made, tables, "beast")
    r = _with_rival(game, adv, monkeypatch, kind="hero", relation=0)
    lines = _meet(game, adv, r, 0)
    assert r["state"] == "racing" and r["relation"] == 1 and r["due"] > game.moment.total_days
    assert r["prize"] == "finale", "a beast's tale has nothing to fetch: they want its head"
    assert all(_no_slots(x) for x in lines)
    assert rivals.journal_line(game, adv).startswith(r["name"])
    pages = beats.pages(game, {"beat": "rival_meeting", "adv": adv["id"], "n": 1, "words": rivals._words(game, adv)})
    assert all(_no_slots(p) for p in pages)


def test_every_rival_beat_reads_whole(made, tables, monkeypatch):
    game, adv, _ = _tale(made, tables, "risen")
    _with_rival(game, adv, monkeypatch, kind="noble")
    for i, bid in enumerate(rivals.BEATS):
        rec = {"beat": bid, "adv": adv["id"], "n": 100 + i, "words": rivals._words(game, adv)}
        for text in beats.pages(game, rec) + [beats.title(game, rec)] + [c["label"] for c in beats.choices(game, rec)]:
            assert _no_slots(text), (bid, text)


def _fetch_race(made, tables, monkeypatch):
    """A risen tale in its second chapter, its anchor's quest out, and a rival who got there first."""
    game, adv, _ = _tale(made, tables, "risen")
    _open_chapter(game, adv, 1)
    r = _with_rival(game, adv, monkeypatch, kind="hero", relation=0)
    _meet(game, adv, r, 2)
    st = _step(adv, "fetch", 1)
    assert r["prize"] == st["id"], "the thing to fetch is the prize"
    r["due"] = int(game.moment.total_days)
    beats.director(game.world)["day"] = -1
    story.daily(game)
    assert r["state"] == "ahead" and r["holds"]
    q = quests.by_id(game, st["quest"])
    assert q["target"]["rival"] and quests.on_chest(game, {"quest": q["id"]}) == [], "the chest is found empty"
    r["last"] = -99
    assert rivals.on_night(game, "inn")
    assert beats.pending(game)["beat"] == "rival_prize"
    return game, adv, r, st, q


def test_they_reach_the_thing_first_and_you_buy_it(made, tables, monkeypatch):
    game, adv, r, st, q = _fetch_race(made, tables, monkeypatch)
    game.leader.money += rivals.price(game, adv)
    rec = beats.pending(game)
    ch = beats.choices(game, rec)
    assert ch[0]["ok"]
    money = sum(c.money for c in game.party)
    _play(game, 0)
    assert sum(c.money for c in game.party) == money - rivals.price(game, adv)
    assert any(st["target"]["tag"] in it.tags for it in game.leader.inventory), "the thing is yours"
    assert q["done"] and r["state"] == "bought" and not r["holds"]


def test_they_reach_the_thing_first_and_you_take_it(made, tables, monkeypatch):
    game, adv, r, st, q = _fetch_race(made, tables, monkeypatch)
    _play(game, 2)
    assert r["relation"] == -2
    leader = game.encounter.creatures[0]
    assert leader.name == r["name"] and leader.story["leader"]
    _battle(game)
    assert r["state"] in ("slain", "gone") and not r["holds"]
    assert any(st["target"]["tag"] in it.tags for it in game.leader.inventory), "taken from them"


def test_they_reach_the_thing_first_and_you_let_it_go(made, tables, monkeypatch):
    game, adv, r, st, q = _fetch_race(made, tables, monkeypatch)
    _play(game, 3)
    assert st["state"] == "failed" and r["fate"] == "prize", "the step is lost; the tale goes on"


def test_into_its_hall_first_and_found_dead_there(made, tables, monkeypatch):
    game, adv, band = _den(made, tables, "beast", arena="")
    r = _with_rival(game, adv, monkeypatch, kind="deserters", relation=-1)
    r.update(state="racing", met=0, prize="finale", due=int(game.moment.total_days))
    beats.director(game.world)["day"] = -1
    beats.director(game.world)["pending"] = None
    story.daily(game)
    assert r["state"] == "dead" and r["in_lair"] and r["hurt"] > 0
    rivals.on_descend(game, game.local)
    assert beats.pending(game)["beat"] == "rival_found_dead" and r["found"]
    ex, ey = game.local.entry
    lm = game.local
    bones = [(x, y) for x in range(ex - 4, ex + 5) for y in range(ey - 4, ey + 5)
             if lm.in_bounds(x, y) and lm.terrain_ids[int(lm.terrain[x, y])] == "bones"]
    assert bones, "their bones lie on the floor"
    money = game.leader.money
    _play(game, 0)
    assert game.leader.money > money
    b, boss = _fight(game, adv, band)
    assert boss.hp < boss.max_hp, "it carries the wounds they gave it"
    endings.finish(game, adv)
    page = next(p for p in adv["epilogue"] if p["about"] == "rival")
    assert r["name"] in page["text"] and _no_slots(page["text"])


def test_a_truce_brings_them_to_the_finale(made, tables, monkeypatch):
    game, adv, band = _den(made, tables, "beast", arena="")
    r = _with_rival(game, adv, monkeypatch, kind="hero", relation=1)
    r.update(state="racing", met=0, prize="finale", due=999)
    beats.OPS["rival"](game, {"adv": adv["id"]}, "truce")
    assert r["state"] == "truce" and "rival" in adv["keys"]
    b, boss = _fight(game, adv, band)
    n = len([f for f in b.side(PARTY) if f.bond and f.bond.get("kind") == "story_ally"])
    b.round = rivals.ARRIVE_ROUND
    for hook in list(b.round_hooks):
        hook(b)
    came = [f for f in b.side(PARTY) if f.bond and f.bond.get("kind") == "story_ally"]
    assert len(came) >= n + 2 and any(f.name == r["name"] for f in came), "they come on their round, with their band"
    assert r["fought"]


def test_a_villain_told_your_road_is_not_surprised(made, tables, monkeypatch):
    game, adv, band = _den(made, tables, "beast", arena="", keys=["bait"])
    r = _with_rival(game, adv, monkeypatch, kind="deserters", relation=-1)
    r.update(state="racing", met=0, prize="finale", due=999)
    _sold_rec = {"beat": "rival_sold", "adv": adv["id"], "n": 7, "words": {}}
    beats.director(game.world)["pending"] = _sold_rec
    beats.choose(game, _sold_rec, 1)
    assert r["sold"]
    b, boss = _fight(game, adv, band)
    assert b.env.surprised != FOE, "it was waiting for you"


def test_the_plea_answered_is_a_fight_beside_them(made, tables, monkeypatch):
    game, adv, _ = _tale(made, tables, "risen")
    _open_chapter(game, adv, 1)
    r = _with_rival(game, adv, monkeypatch, kind="hero", relation=1)
    r.update(state="truce", met=0, last=-99)
    adv["keys"].append("rival")
    monkeypatch.setitem(tables.adventures["rivals"]["clock"], "event_chance", 1.0)
    assert rivals.on_night(game, "camp")
    assert beats.pending(game)["beat"] == "rival_plea"
    _play(game, 0)
    assert r["helping"] and game.encounter is not None
    enc = game.encounter
    game.encounter = None
    b = fight.start_battle(game, enc.creatures, enc.intro)
    beside = [f for f in b.side(PARTY) if f.bond and f.bond.get("kind") == "story_ally"]
    assert any(f.name == r["name"] for f in beside), "they fight beside you"
    from tools.arena import run

    for f in b.side(PARTY):
        f.auto, f.hp = True, 400
    for f in b.side(FOE):
        f.hp = 1
    run(b, max_steps=4000)
    fight.finish_battle(game)
    assert r["state"] == "truce" and r["relation"] == 2 and not r["helping"]


def test_the_plea_refused_leaves_them_overrun(made, tables, monkeypatch):
    game, adv, _ = _tale(made, tables, "risen")
    r = _with_rival(game, adv, monkeypatch, kind="noble", relation=1)
    r.update(state="truce", met=0)
    beats.OPS["rival"](game, {"adv": adv["id"]}, "plea_refused")
    assert r["state"] == "pinned"
    r["pinned_until"] = int(game.moment.total_days) - 1
    beats.director(game.world)["day"] = -1
    story.daily(game)
    assert r["state"] == "dead" and r["fate"] == "overrun"


def test_a_hostile_rival_robs_you_and_an_enemy_ambushes_you(made, tables, monkeypatch):
    game, adv, _ = _tale(made, tables, "beast")
    r = _with_rival(game, adv, monkeypatch, kind="deserters", relation=-1)
    r.update(state="racing", met=0, prize="finale", due=999, last=-99)
    monkeypatch.setitem(tables.adventures["rivals"]["clock"], "event_chance", 1.0)
    game.leader.money = 10000
    assert rivals.on_night(game, "inn")
    assert beats.pending(game)["beat"] == "rival_theft"
    _play(game, 1)
    assert game.leader.money < 10000 and r["relation"] == -2
    r["last"] = -99
    assert rivals.on_night(game, "camp")
    assert beats.pending(game)["beat"] == "rival_ambush"
    _play(game, 0)
    assert game.encounter is not None and all(c.story["role"] == "rival" for c in game.encounter.creatures)
    _battle(game)
    assert r["state"] in ("slain", "gone")
    assert r["relation"] == -2, "never below -2"


def test_relation_stays_in_bounds_and_a_friend_offers_a_truce(made, tables, monkeypatch):
    game, adv, _ = _tale(made, tables, "beast")
    r = _with_rival(game, adv, monkeypatch, kind="hero", relation=0)
    r.update(state="racing", met=0, prize="finale", due=999)
    for _ in range(5):
        beats.OPS["rival"](game, {"adv": adv["id"]}, "relation", -1)
    assert r["relation"] == -2
    r["relation"] = 1
    r["last"] = -99
    monkeypatch.setitem(tables.adventures["rivals"]["clock"], "event_chance", 1.0)
    assert rivals.on_night(game, "camp")
    assert beats.pending(game)["beat"] == "rival_truce"
    _play(game, 0)
    assert r["state"] == "truce" and "rival" in adv["keys"]


def test_the_epilogue_names_them(made, tables, monkeypatch):
    game, adv, _ = _tale(made, tables, "beast")
    r = _with_rival(game, adv, monkeypatch, kind="hero", relation=0)
    r.update(state="racing", met=0, prize="finale", due=999)
    adv["boss_dead"] = True
    endings.finish(game, adv)
    page = next(p for p in adv["epilogue"] if p["about"] == "rival")
    assert r["fate"] in ("late", "gone") and r["name"] in page["text"]
