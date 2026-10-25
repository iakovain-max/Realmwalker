"""Escapes, early ends, anchors and returning villains (Expansion 6 E.4, docs/ADVENTURES.md §5.4): a villain met before
its finale gets away once in a tale, never with what binds it in your hands, and met again it stands; killed before
its finale it leaves a short last chapter - a lieutenant takes its place at its den (a real fight), its last orders
are a set piece lived through on the road (a beat and a real fight), or nothing is left and the tale ends at once;
the dead make no moves; put down without its anchor it sleeps its weeks and comes back for the hero who did it,
angry and harder to kill; at the top of its attention it carries its anchor home."""

from types import SimpleNamespace

import pytest

from realmwalker.game import fight, story
from realmwalker.game.story import beats, deeds, early, finale, lieutenants, places, villain
from realmwalker.rules.combat import FOE, PARTY
from realmwalker.world import threats
from tests.test_lieutenants import _trait
from tests.test_risen_outlaw import _open_chapter, _step, _tale, _to_level, made, tables  # noqa: F401

pytestmark = pytest.mark.story


def _strong(game):
    for c in game.party:
        c.level = max(c.level, 12)
        c.hp = c.max_hp = 250


def _early_only(monkeypatch, tables, adv, kind):
    bp = dict(tables.adventures["blueprints"][adv["blueprint"]], early={kind: 1})
    monkeypatch.setitem(tables.adventures["blueprints"], adv["blueprint"], bp)


def _villain_dies(game, adv):
    boss = SimpleNamespace(story={"adv": adv["id"], "role": "villain"}, name="it")
    story.on_battle(game, SimpleNamespace(outcome="victory", dead=[boss], captives=[], fled=[]))


def _hunted(game, adv):
    """The villain met on the road, before its den: a real battle with it."""
    game.encounter = None
    story.named_encounter(game, adv, "villain")
    enc, game.encounter = game.encounter, None
    assert enc is not None and enc.creatures
    b = fight.start_battle(game, enc.creatures, enc.intro)
    boss = next(f for f in b.side(FOE) if (getattr(f.creature, "story", None) or {}).get("role") == "villain")
    return b, boss


def test_it_gets_away_once_and_met_again_it_stands(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    _strong(game)
    b, boss = _hunted(game, adv)
    assert boss.cdef["boss_phase"]["kind"] == "breaks_off", "hurt, it breaks off"
    game.battle = None
    fled = SimpleNamespace(story={"adv": adv["id"], "role": "villain"}, name="it")
    n = len(adv["journal"])
    story.on_battle(game, SimpleNamespace(outcome="victory", dead=[], captives=[], fled=[fled]))
    assert adv["escaped"] and adv["boss_fled"] and adv["state"] == "active"
    assert len(adv["journal"]) == n + 1, "the journal says it will not get away twice"
    b, boss = _hunted(game, adv)
    assert "boss_phase" not in boss.cdef and boss.cdef["morale"] == "fanatic", "its escape is spent: it stands"
    for f in b.side(PARTY):
        f.auto = True
    from tools.arena import run

    run(b, max_steps=4000)
    assert b.outcome is not None


def test_what_binds_it_forbids_any_escape(made, tables):
    game, adv, t = _tale(made, tables, "risen")
    assert "no_escape" in adv["finale"]["keys"]["anchor"]
    assert early.may_escape(game, adv)
    adv["keys"].append("anchor")
    assert not early.may_escape(game, adv), "with its crown in your hands it cannot get away"
    boss = SimpleNamespace(cdef={"boss_phase": {"kind": "breaks_off"}, "morale": "normal"})
    finale.KEYS["no_escape"](None, game, adv, boss)
    assert "boss_phase" not in boss.cdef and boss.cdef["morale"] == "fanatic"


def test_a_lieutenant_takes_its_place_at_its_den_in_a_real_fight(made, tables, monkeypatch):
    from tools.arena import run

    game, adv, t = _tale(made, tables, "outlaw")
    _early_only(monkeypatch, tables, adv, "succession")
    fin = _step(adv, "finale")
    _villain_dies(game, adv)
    assert adv["state"] == "active" and adv["early"]["kind"] == "succession", "not over yet: it has an heir"
    last = story.chapter(adv)
    assert last["id"] == "early" and adv["chapters"][-1] is last and last["title"]
    st = last["steps"][0]
    assert st["kind"] == "defeat" and st["target"]["level"] == fin["target"]["level"]
    heir = st["target"]["role"]
    rec = lieutenants.of(game, adv, heir)
    assert rec["name"] in last["opening"] or lieutenants.full(rec) in last["opening"], "the heir is named"
    _trait(monkeypatch, tables, rec, flee_at=0)
    recs = game.world.politics["story_sites"][st["target"]["level"]]
    assert not any(r["adv"] == adv["id"] and not r.get("role") for r in recs), "the dead villain is not at its den"
    assert villain.due_move(game, adv, "road") is None, "the dead make no moves"
    _to_level(game, adv["places"]["home"])
    band = next(a for a in game.local.actors if a.creatures and (getattr(a.creatures[0], "story", None) or {})
                .get("role") == heir)
    assert not story.hold_for_finale(game, band), "no finale card: the villain is dead"
    _strong(game)
    b = fight.start_battle(game, band.creatures, "the heir", actor=band)
    for f in b.side(PARTY):
        f.auto = True
    run(b, max_steps=4000)
    assert b.outcome == "victory"
    fight.finish_battle(game)
    assert st["state"] == "done" and adv["state"] == "won" and adv["ending"] == "broken", "the gang is broken"
    assert rec["fate"] == "slain"


def test_its_last_orders_are_lived_through_on_the_road_in_a_real_fight(made, tables, monkeypatch):
    from tools.arena import run

    game, adv, t = _tale(made, tables, "risen")
    _early_only(monkeypatch, tables, adv, "contingency")
    _villain_dies(game, adv)
    st = story.chapter(adv)["steps"][0]
    assert adv["early"]["kind"] == "contingency" and st["kind"] == "endure"
    assert st["target"]["beat"] == "early_last_letter", "a villain who speaks leaves a letter"
    assert st["target"]["group"] == "restless_dead"
    game.world.time += 1440 * (int(st["target"]["due"]) - int(game.moment.total_days) + 1)
    town = game.world.settlements[adv["places"]["town"]["settlement"]]
    game.player.x, game.player.y = places.xy(game.world, adv["places"]["home"])
    assert game.world.settlement_at(game.player.x, game.player.y) is None or town is not None
    beats.director(game.world)["pending"] = beats.director(game.world)["card"] = None  # (its title card seen)
    assert story.on_travel(game, 60) and beats.pending(game)["beat"] == "early_last_letter"
    beats.choose(game, beats.pending(game), 0)
    enc, game.encounter = game.encounter, None
    assert enc is not None and all(c.story["role"] == "endure" and c.story["step"] == st["id"] for c in enc.creatures)
    _strong(game)
    b = fight.start_battle(game, enc.creatures, enc.intro)
    for f in b.side(PARTY):
        f.auto = True
    run(b, max_steps=4000)
    fight.finish_battle(game)
    assert st["state"] == "done" and adv["state"] == "won"
    assert adv["ending"] == "destroyed_for_now", "killed without its crown: it will be back"


def test_a_set_piece_never_met_passes_by_itself(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "outlaw")
    _early_only(monkeypatch, tables, adv, "contingency")
    _villain_dies(game, adv)
    st = story.chapter(adv)["steps"][0]
    game.world.time += 1440 * (int(st["target"]["due"]) - int(game.moment.total_days) + deeds.ENDURE_WAIT + 1)
    deeds.daily(game)
    assert st["state"] == "done" and adv["state"] == "won", "law 6: never stuck"


def test_nothing_left_behind_and_the_tale_ends_at_once(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "outlaw")
    _early_only(monkeypatch, tables, adv, "cat_away")
    _villain_dies(game, adv)
    assert adv["early"]["kind"] == "cat_away" and adv["state"] == "won" and adv["ending"] == "broken"
    assert not any(r["adv"] == adv["id"] and not r.get("role") for recs in
                   game.world.politics.get("story_sites", {}).values() for r in recs), "its den lies open"


def test_killed_at_its_finale_is_no_early_end(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    _open_chapter(game, adv, len(adv["chapters"]) - 1)
    _villain_dies(game, adv)
    assert "early" not in adv and adv["state"] == "won"


def test_it_comes_back_for_the_hero_who_put_it_down(made, tables):
    from realmwalker.world import news
    from realmwalker.world.politics import Politics

    game, adv, t = _tale(made, tables, "risen")
    _open_chapter(game, adv, 2)
    _villain_dies(game, adv)
    assert adv["ending"] == "destroyed_for_now" and t["state"] == "dormant"
    assert t["returns"]["life"] == adv["hero"]["life"] and t["returns"]["times"] == 1
    day = float(news.now_days(game.world))
    pol = Politics(game.world, game.tables, game.world.rng.child("e4"), day=day)
    threats.advance(pol, 7)
    assert t["state"] == "dormant", "it sleeps its weeks first"
    t["scheme"]["held_until"] = day - 1
    threats.advance(pol, 7)
    assert t["state"] == "stirring", "and then it comes back, for sure"
    beats.director(game.world)["pending"] = None
    beats.director(game.world)["day"] = -1
    game.epilogue = None  # (the last tale's epilogue read)
    story.daily(game)
    rec = beats.pending(game)
    assert rec is not None and rec["beat"] == "villain_returns", "the hero who put it down hears of it first"
    beats.choose(game, rec, 0)
    back = next(a for a in story.active(game) if a["threat"] == t["id"])
    assert back["returning"]["times"] == 1 and back["attention"] >= 3, "it starts out angry with you"
    assert "sequel" not in t
    f = SimpleNamespace(max_hp=100, hp=100)
    assert early.on_boss(None, game, back, f) and f.max_hp == 115 and f.hp == 115, "harder to put down again"


def test_at_the_top_of_its_attention_it_carries_its_anchor_home(made, tables):
    game, adv, t = _tale(made, tables, "risen")
    st = _step(adv, "fetch")
    home = adv["places"]["home"]["site"]
    assert st["target"]["place"]["site"] != home
    adv["attention"] = 5
    assert villain.able(game, adv, "anchor")
    n = len(adv["journal"])
    beats.offer(game, "villain_relic_moved", adv=adv["id"], where="road")
    beats.choose(game, beats.pending(game), -1)
    assert len(adv["journal"]) == n + 1 and "{" not in adv["journal"][-1]["text"], "the journal tells where it is"
    assert st["target"]["place"] == {"site": home, "part": "level", "level": 1} and st["moved"]
    assert st["target"]["level"] == places.dungeon_key(game.world, st["target"]["place"])
    assert not villain.able(game, adv, "anchor"), "it moves it once"
    _open_chapter(game, adv, 1)
    from realmwalker.game import quests

    q = quests.by_id(game, st["quest"])
    assert q["target"]["site"] == home and q["target"]["level"] == 1, "you must go under its roof for it"


def test_the_words_read_clean(made, tables, monkeypatch):
    for kind in ("succession", "contingency", "cat_away"):
        game, adv, t = _tale(made, tables, "outlaw")
        _early_only(monkeypatch, tables, adv, kind)
        _villain_dies(game, adv)
        text = " ".join(j["text"] for j in adv["journal"]) + " ".join(
            str(adv["chapters"][-1].get(k, "")) for k in ("title", "goal", "opening", "reveal"))
        assert "{" not in text and "}" not in text, text
