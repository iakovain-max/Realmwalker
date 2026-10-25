"""Lieutenants who remember (Expansion 6 E.3, docs/ADVENTURES.md §5.5, the nemesis rule): named heads of the
villain's bands, with a look, a trait and a weakness; one who gets away comes back scarred and better armed; one
spared may turn (and may be lying) or goes back with a grudge; one slain makes the villain grieve or rage; the free
stand beside the villain at the end; each has a page in the epilogue; the one with the greatest grudge when the
villain falls is promoted, and comes for you on the road."""

import json
from types import SimpleNamespace

import pytest

from realmwalker.game import fight, story
from realmwalker.game.story import cast, endings, lieutenants, places
from realmwalker.rules.combat import FOE, PARTY
from tests.test_risen_outlaw import _tale, made, tables  # noqa: F401

pytestmark = pytest.mark.story


def _band_step(adv, role):
    return next(st for ch in adv["chapters"] for st in ch["steps"] if st["target"].get("role") == role
                and st["kind"] in ("defeat", "capture"))


def _meet(game, adv, role):
    """Stand where the role's band waits (a new day) and meet it."""
    st = _band_step(adv, role)
    game.player.x, game.player.y = places.xy(game.world, st["target"]["place"])
    game.world.time += 1440
    for ch in adv["chapters"]:  # (the other band of the same road is met another day)
        for other in ch["steps"]:
            if other is not st and other["kind"] in ("defeat", "capture"):
                other["met"] = int(game.moment.total_days)
    game.encounter = None
    assert story.on_arrive(game) and game.encounter is not None, "the band waits there"
    enc = game.encounter
    game.encounter = None
    return enc


def _trait(monkeypatch, tables, rec, **numbers):
    tr = dict(tables.villains["lieutenants"]["traits"][rec["trait"]], **numbers)
    monkeypatch.setitem(tables.villains["lieutenants"]["traits"], rec["trait"], tr)


def test_named_lieutenants_lead_the_bands_and_are_kept_on_the_threat(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    assert {r["as"] for r in t["lieutenants"]} == {"raiders", "lookout"}
    rec = lieutenants.of(game, adv, "raiders")
    assert rec["name"] and rec["title"] and rec["look"] and rec["weakness"] and rec["fate"] == "unmet"
    assert rec["trait"] in tables.villains["lieutenants"]["traits"]
    assert cast.describe(game, adv, "raiders") == lieutenants.full(rec), "the band is named for its head"
    assert json.loads(json.dumps(t["lieutenants"])) == t["lieutenants"], "JSON-native records"
    enc = _meet(game, adv, "raiders")
    head = enc.creatures[0]
    assert head.name == lieutenants.full(rec) and head.named and head.def_id == rec["creature"]
    assert head.story["lt"] == adv["cast"]["raiders"]["lt"] and head.story["role"] == "raiders"
    assert rec["fate"] == "met" and lieutenants.journal_lines(game, adv), "the journal shows who you have met"


def test_one_who_gets_away_comes_back_scarred_and_better_armed(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    rec = lieutenants.of(game, adv, "raiders")
    enc = _meet(game, adv, "raiders")
    head = enc.creatures[0]
    head.hp = max(1, head.max_hp // 3)
    story.on_battle(game, SimpleNamespace(outcome="victory", dead=list(enc.creatures[1:]), captives=[], fled=[head]))
    assert rec["fate"] == "escaped" and rec["grudge"] == 1 and len(rec["scars"]) == 1
    assert _band_step(adv, "raiders")["state"] == "open", "the step waits: they will be back"
    enc = _meet(game, adv, "raiders")
    assert rec["scars"][0] in enc.intro, "they come back with the scar you gave them"
    plain = game.tables.creatures[rec["creature"]]["ac"]
    b = fight.start_battle(game, enc.creatures, enc.intro)
    f = next(x for x in b.side(FOE) if x.creature is enc.creatures[0])
    assert int(f.cdef["ac"]) == int(plain) + 1 and any(bf["id"] == "grudge" for bf in f.buffs)
    assert f.creature.max_hp > 0 and f.creature.uses.get("lt_armed")
    assert f.cdef["morale"] == tables.villains["lieutenants"]["traits"][rec["trait"]]["morale"]


def test_a_lieutenant_tries_to_escape_in_a_real_fight(made, tables, monkeypatch):
    from realmwalker.rules.engine.handlers import bosses
    from tools.arena import run

    game, adv, t = _tale(made, tables, "outlaw")
    rec = lieutenants.of(game, adv, "raiders")
    _trait(monkeypatch, tables, rec, flee_at=0.5)
    enc = _meet(game, adv, "raiders")
    for c in game.party:
        c.level = max(c.level, 12)
        c.hp = c.max_hp = 200
    b = fight.start_battle(game, enc.creatures, enc.intro)
    for x in b.side(PARTY):
        x.auto = True
    f = next(x for x in b.side(FOE) if x.creature is enc.creatures[0])
    assert f.cdef["boss_phase"]["kind"] == "escape"
    f.creature.hp = 1
    bosses.after_damage(b, f)
    assert f.state in ("fled", "fleeing"), "hurt, it breaks for it"
    assert any(e.get("phase") == "escape" for e in b.events)
    run(b, max_steps=4000)
    fight.finish_battle(game)
    assert rec["fate"] in ("escaped", "slain"), "it got away, or was cut down running"
    assert rec["grudge"] == (1 if rec["fate"] == "escaped" else 0)


def test_mercy_may_turn_one_or_send_them_back_with_a_grudge(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "outlaw")
    rec = lieutenants.of(game, adv, "raiders")
    enc = _meet(game, adv, "raiders")
    head = enc.creatures[0]
    _trait(monkeypatch, tables, rec, turn=1.0, betray=0.0)
    story.on_battle(game, SimpleNamespace(outcome="victory", dead=[], captives=[head], fled=[]))
    assert rec["fate"] == "taken"
    assert story.on_fate(game, head, "spare")
    assert rec["fate"] == "turned" and "backway" in adv["keys"], "one who turns tells you what they know"

    game, adv, t = _tale(made, tables, "outlaw")
    rec = lieutenants.of(game, adv, "lookout")
    enc = _meet(game, adv, "lookout")
    head = enc.creatures[0]
    _trait(monkeypatch, tables, rec, turn=1.0, betray=1.0)
    story.on_battle(game, SimpleNamespace(outcome="victory", dead=[], captives=[head], fled=[]))
    story.on_fate(game, head, "spare")
    assert rec["fate"] == "turncoat" and adv["clues"].get("inside", 0) == 0, "a liar's word gives nothing"

    game, adv, t = _tale(made, tables, "outlaw")
    rec = lieutenants.of(game, adv, "raiders")
    enc = _meet(game, adv, "raiders")
    _trait(monkeypatch, tables, rec, turn=0.0)
    story.on_battle(game, SimpleNamespace(outcome="victory", dead=[], captives=[enc.creatures[0]], fled=[]))
    story.on_fate(game, enc.creatures[0], "rob")
    assert rec["fate"] == "spared" and rec["grudge"] == 1, "mercy refused: back to the villain, angrier"


def test_one_slain_is_grieved_or_raged_over(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    rec = lieutenants.of(game, adv, "raiders")
    enc = _meet(game, adv, "raiders")
    before = int(adv.get("attention", 0))
    story.on_battle(game, SimpleNamespace(outcome="victory", dead=list(enc.creatures), captives=[], fled=[]))
    assert rec["fate"] == "slain"
    assert int(adv["attention"]) >= before + 2, "a lieutenant slain: it notices, and its wrath"
    assert rec["name"] in adv["journal"][-1]["text"] or any(rec["name"] in j["text"] for j in adv["journal"])


def test_the_free_stand_beside_the_villain_at_the_end_and_the_slain_do_not(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    look = lieutenants.of(game, adv, "lookout")
    raid = lieutenants.of(game, adv, "raiders")
    look["fate"], raid["fate"], raid["grudge"], raid["scars"] = "slain", "escaped", 2, ["a notched ear"]
    villain = SimpleNamespace(uid=1, story={"adv": adv["id"], "role": "villain"})
    actor = SimpleNamespace(creatures=[villain])
    lines = lieutenants.join_finale(game, adv, actor)
    assert len(actor.creatures) == 2 and actor.creatures[1].name == lieutenants.full(raid)
    assert actor.creatures[1].story == {"adv": adv["id"], "role": "raiders", "lt": adv["cast"]["raiders"]["lt"]}
    assert lines and "notched ear" in lines[0], "it brings its grudge"
    assert not lieutenants.join_finale(game, adv, actor), "once"


def test_their_pages_in_the_epilogue_and_the_nemesis_promoted(made, tables):
    from realmwalker.ui.gfx import vignette

    game, adv, t = _tale(made, tables, "outlaw")
    raid = lieutenants.of(game, adv, "raiders")
    look = lieutenants.of(game, adv, "lookout")
    raid["fate"], raid["grudge"], raid["scars"] = "escaped", 1, ["a broken nose set crooked"]
    look["fate"] = "taken"
    adv["boss_dead"] = True
    endings.finish(game, adv)
    pages = {p["about"]: p["text"] for p in adv["epilogue"]}
    assert "lieutenant:raiders" in pages and "lieutenant:lookout" in pages
    assert raid["fate"] == "promoted" and raid["name"] in pages["lieutenant:raiders"]
    assert vignette.for_epilogue(game, adv, "lieutenant:raiders").get("figures")
    assert vignette.for_epilogue(game, adv, "lieutenant:lookout").get("props")
    nem = game.world.politics["nemeses"]
    assert len(nem) == 1 and nem[0]["state"] == "hunting"
    assert json.loads(json.dumps(nem)) == nem
    # Weeks later, out on the land: they come with the villain's old company.
    game.world.time += 1440 * 31
    s = game.world.settlement_at(game.player.x, game.player.y)
    if s is not None:
        game.player.x, game.player.y = places.xy(game.world, _band_step(adv, "raiders")["target"]["place"])
    game.encounter = None
    assert lieutenants.on_travel(game) and game.encounter is not None
    head = game.encounter.creatures[0]
    assert head.name == lieutenants.full(raid) and "nemesis" in head.story
    assert lieutenants.full(raid) in game.encounter.intro or raid["name"] in game.encounter.intro
    band = game.encounter.creatures
    game.encounter = None
    assert not lieutenants.on_travel(game), "not again at once"
    story.on_battle(game, SimpleNamespace(outcome="victory", dead=list(band), captives=[], fled=[]))
    assert nem[0]["state"] == "slain"
