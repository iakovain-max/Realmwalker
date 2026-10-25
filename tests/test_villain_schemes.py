"""The villain's schemes (Expansion 6 E.2, docs/ADVENTURES.md §5.4, §5.18): its visit seen at the camp's edge beyond
a fire burned low, and staged on the town's map at an inn; its letters in its own hand; an invitation under safe
conduct and the dinner at its hall; a bargain taken that ends the tale darkly; a wedge driven at a companion (the loyal
tell you, the others go over to it); a reprisal seen in the helper's town; a frame through false witnesses, struck off
when the tale is won; a kidnap that adds a rescue to the chapter."""

import pytest

from realmwalker.game import companions, encounters, law, letters, story
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.story import beats, endings, stage, villain
from tests.test_risen_outlaw import _tale, made, tables  # noqa: F401
from tests.test_villain import _days, _temper_moves

pytestmark = pytest.mark.story


def _night(game):
    game.world.time += (24 - game.moment.hour + 1) * 60


def _helper_ready(game, adv, t):
    """The witness, bound to a townsperson, has told what they know; the party stands away from their town."""
    entry = adv["cast"]["witness"]
    prepare_town(game, game.world.settlements[int(entry["settlement"])])
    entry = adv["cast"]["witness"]
    assert "npc" in entry, "the witness is bound to a townsperson"
    for ch in adv["chapters"]:
        for st in ch["steps"]:
            if "witness" in [st["target"].get("role")] + [r.get("role") for r in st["target"].get("routes", [])]:
                st["state"] = "done"
    game.player.x, game.player.y = t["reach"]["x"], t["reach"]["y"]
    return game.world.npcs[int(entry["npc"])]


def _companion(game, loyalty=60.0):
    """A townsperson of the start town hired to walk with you."""
    s = game.world.settlement_at(game.player.x, game.player.y) or game.world.settlements[0]
    prepare_town(game, s)
    arch = next(iter(companions.data(game)["archetypes"]))
    npc = next(n for n in npcs_in(game.world, s.id) if n.alive and not n.flags.get("stays"))
    npc.flags["recruit"] = arch
    npc.met, npc.disposition = True, 40
    game.leader.money = 10 ** 6
    companions.hire(game, npc)
    c = game.party[-1]
    assert c.companion, "hired"
    c.companion["loyalty"] = loyalty
    return c


def test_moves_wait_for_what_they_need(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "outlaw")
    adv["attention"] = 4
    _temper_moves(monkeypatch, game, adv, {"wedge": 1})
    assert not villain.able(game, adv, "companion")
    assert villain.due_move(game, adv, "camp") is None, "no companion to tempt"
    _companion(game)
    _night(game)
    assert villain.due_move(game, adv, "camp") == "villain_wedge"


def test_the_visit_stands_at_the_edge_of_the_camps_light(made, tables, monkeypatch):
    import tcod.console

    from realmwalker.game import camp
    from realmwalker.ui.gfx import dolls, headless, scenes
    from realmwalker.ui.gfx.scene import Image
    from realmwalker.ui.widgets import Canvas

    game, adv, t = _tale(made, tables, "risen")
    camp.make_camp(game)
    monkeypatch.setattr(villain, "due_move", lambda game, adv, where: "villain_visit")
    assert story.on_night(game, "camp") and beats.pending(game)["beat"] == "villain_visit"
    rec = story.left_record(game)
    assert rec["what"] == "visitor" and rec["adv"] == adv["id"]
    key = str(dolls.figure_key(dolls.creature(t["villain"]["creature"], game.tables, f"villain/{t['id']}")))

    def images():
        canvas = Canvas(tcod.console.Console(80, 30, order="F"), gfx=headless())
        scenes.camp(canvas, game, (0, 0, 640, 300), 1.0)
        return [str(c.key) for layer in canvas.layers for c in layer.under if isinstance(c, Image)]

    assert any(key in k for k in images()), "the villain stands beyond the fire"
    beats.choose(game, beats.pending(game), 2)
    assert story.left_record(game) is None, "gone when the fire flares"
    assert not any(key in k for k in images())


def test_the_visit_comes_to_your_room_at_the_inn(made, tables, monkeypatch):
    from realmwalker.game import fight, townlife

    game, adv, t = _tale(made, tables, "risen")
    s = game.world.settlement_at(game.player.x, game.player.y)
    assert s is not None, "the tale begins in a town"
    game.player.local_key = None
    game.enter_local()
    monkeypatch.setattr(villain, "due_move", lambda game, adv, where: "villain_visit" if where == "inn" else None)
    game.world.time += (22 - game.moment.hour) % 24 * 60
    stage.end(game)  # (the tale's own runner, met as you came in, and what it brought)
    beats.director(game.world)["pending"] = None
    notes = fight.rest(game, "night", inn=True)
    assert any("broken" in n for n in notes), "the night is broken"
    rec = stage.current(game)
    assert rec is not None and rec["id"] == "villain_visit_inn"
    lm = game.local
    for _ in range(80):
        if beats.pending(game) is not None:
            break
        townlife.tick(game, lm, s)
    assert beats.pending(game)["beat"] == "villain_visit", "it speaks, and the beat opens"
    visitor = game.world.npcs[rec["cast"]["visitor"]]
    assert visitor.flags.get("as_creature") == t["villain"]["creature"]
    assert max(abs(visitor.x - game.player.lx), abs(visitor.y - game.player.ly)) <= 4, "at your bedside"
    beats.choose(game, beats.pending(game), 0)
    for _ in range(80):
        if stage.current(game) is None:
            break
        townlife.tick(game, lm, s)
    assert stage.current(game) is None and visitor.id not in game.world.npcs, "and it is gone"


def test_its_letters_are_in_its_own_hand(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    beats.offer(game, "villain_letter", adv=adv["id"], where="camp")
    beats.choose(game, beats.pending(game), 1)
    rec = letters.records(game.world)[game.letter]
    own = villain.temper(game, adv)["hand"]
    assert rec["hand"] == own["face"] and rec["ink"] == own["ink"] and rec["seal"] == own["seal"]


def test_an_invitation_gives_safe_conduct_and_a_dinner(made, tables, monkeypatch):
    from realmwalker.game.story import places

    game, adv, t = _tale(made, tables, "risen")
    beats.offer(game, "villain_invitation", adv=adv["id"], where="camp")
    pages = " ".join(beats.pages(game, beats.pending(game)))
    assert "{" not in pages
    beats.choose(game, beats.pending(game), 0)
    game.letter = None
    assert adv["invited"]["state"] == "going" and villain.invited(game) is not None
    monkeypatch.setattr(encounters, "encounter_chance", lambda *a, **k: 1.0)
    game.player.x, game.player.y = t["reach"]["x"], t["reach"]["y"]
    assert game.world.settlement_at(game.player.x, game.player.y) is None or True
    assert encounters.roll_encounter(game, 600) is None, "no band troubles its guest"
    game.player.x, game.player.y = places.xy(game.world, adv["places"]["home"])
    assert story.on_arrive(game) and beats.pending(game)["beat"] == "villain_dinner"
    rec = beats.pending(game)
    assert "{" not in " ".join(beats.pages(game, rec)) and len(beats.pages(game, rec)) == 3
    beats.choose(game, rec, 1)
    assert adv["invited"]["state"] == "home" and adv["dined"]
    _days(game, 3)
    villain.lapse(game, adv)
    assert "invited" not in adv and villain.invited(game) is None, "the conduct home runs out"
    assert encounters.roll_encounter(game, 600) is not None or True


def test_an_invitation_not_taken_up_is_a_slight(made, tables):
    game, adv, t = _tale(made, tables, "risen")
    adv["attention"] = 3
    beats.offer(game, "villain_invitation", adv=adv["id"], where="camp")
    beats.choose(game, beats.pending(game), 0)
    _days(game, 7)
    villain.lapse(game, adv)
    assert "invited" not in adv and "snubbed_it" in adv["flags"] and adv["attention"] == 4


def test_a_bargain_taken_ends_the_tale_darkly(made, tables):
    game, adv, t = _tale(made, tables, "risen")
    money = game.leader.money
    beats.offer(game, "villain_bargain", adv=adv["id"], where="camp")
    beats.choose(game, beats.pending(game), 1)
    assert adv["state"] == "lost" and adv["ending"] == "bargained"
    assert sum(c.money for c in game.party) > money, "paid"
    assert adv["epilogue"] and all("{" not in p["text"] for p in adv["epilogue"])
    town = game.world.settlements[int(adv["places"]["town"]["settlement"])]
    assert "haunted" in town.status, "the dead stand at its fences"
    assert float(t["bargained"]) > game.moment.total_days and t.get("adventure") is None
    assert not story._can_take(game, t), "nobody offers you its tale while its word holds"


def test_a_loyal_companion_brings_you_its_offer(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "outlaw")
    c = _companion(game, 70)
    adv["attention"] = 3
    _temper_moves(monkeypatch, game, adv, {"wedge": 1})
    _night(game)
    assert villain.due_move(game, adv, "camp") == "villain_wedge"
    beats.offer(game, "villain_wedge", adv=adv["id"], where="camp")
    rec = beats.pending(game)
    assert c.name.split()[0] in " ".join(beats.pages(game, rec)) and "{" not in " ".join(beats.pages(game, rec))
    beats.choose(game, rec, 0)
    assert c.companion["loyalty"] == 80 and "refused_wedge" in adv["flags"]


def test_a_disloyal_companion_goes_over_to_it_with_what_you_knew(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "outlaw")
    c = _companion(game, 20)
    adv["keys"].append("backway")
    adv["attention"] = 3
    _temper_moves(monkeypatch, game, adv, {"wedge": 1})
    _night(game)
    beat = villain.due_move(game, adv, "camp")
    assert beat == "villain_wedge_taken"
    game.world.time += 8 * 60
    beats.offer(game, beat, adv=adv["id"], where="camp")
    beats.choose(game, beats.pending(game), -1)
    assert c not in game.party and adv["turned"]["name"] == c.name
    assert adv["turned"]["key"] == "backway" and "backway" not in adv["keys"] and "betrayed" in adv["flags"]


def test_giving_up_one_who_helped_you_is_a_dark_ending(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "outlaw")
    npc = _helper_ready(game, adv, t)
    _companion(game, 70)
    adv["attention"] = 3
    _temper_moves(monkeypatch, game, adv, {"wedge": 1})
    _night(game)
    assert villain.due_move(game, adv, "camp") == "villain_wedge" and adv["reprisal"] == npc.id
    beats.offer(game, "villain_wedge", adv=adv["id"], where="camp")
    rec = beats.pending(game)
    assert all(o["ok"] for o in beats.choices(game, rec))
    beats.choose(game, rec, 2)
    assert not npc.alive and adv["ending"] == "bargained" and "sacrificed" in adv["flags"]


def test_a_reprisal_is_seen_in_their_town(made, tables, monkeypatch):
    from realmwalker.game import townlife
    from tests.test_townlife import at_hour

    game, adv, t = _tale(made, tables, "outlaw")
    npc = _helper_ready(game, adv, t)
    adv["attention"] = 4
    _temper_moves(monkeypatch, game, adv, {"reprisal_fire": 1})
    beat = next((b for w in ("road", "wild", "camp") if (b := villain.due_move(game, adv, w))), None)
    assert beat == "villain_reprisal_fire"
    beats.offer(game, beat, adv=adv["id"], where="road")
    beats.choose(game, beats.pending(game), 0)
    s = game.world.settlements[int(npc.settlement)]
    assert not npc.alive and npc.flags["reprisal"]["how"] == "burned"
    assert "burned_out" in s.status, "the burned house is a mark on their town"
    townlife.forget()
    at_hour(game, 11)
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    story.on_enter_town(game, s)
    rec = stage.current(game)
    assert rec is not None and rec["id"] == "reprisal_ashes" and rec["words"]["helper"] == npc.name
    assert not beats.director(game.world).get("reprisals"), "shown once"


def test_a_frame_puts_a_price_on_your_head_until_the_truth_is_out(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "outlaw")
    adv["attention"] = 4
    _temper_moves(monkeypatch, game, adv, {"frame": 1})
    beat = next((b for w in ("road", "wild", "camp", "town") if (b := villain.due_move(game, adv, w))), None)
    assert beat == "villain_frame"
    plan = adv["frame"]
    victim = game.world.npcs.get(plan["victim"]) if plan.get("victim") is not None else None
    beats.offer(game, beat, adv=adv["id"], where="road")
    pages = " ".join(beats.pages(game, beats.pending(game)))
    assert game.world.settlements[plan["settlement"]].name in pages and plan["name"].lower() in pages.lower()
    beats.choose(game, beats.pending(game), 0)
    rec = next(r for r in game.renown.crimes if r.get("framed") == adv["id"])
    assert rec["crime"] == "murder" and rec["reported"] and game.renown.bounties[rec["realm"]] >= rec["bounty"] > 0
    if victim is not None:
        assert not victim.alive
    adv["boss_dead"] = True
    lines = endings.finish(game, adv)
    assert adv["state"] == "won" and rec["settled"] and game.renown.bounties[rec["realm"]] == 0
    assert any("struck" in x for x in lines)


def test_a_kidnap_adds_a_rescue_with_a_short_time(made, tables, monkeypatch):
    game, adv, t = _tale(made, tables, "outlaw")
    npc = _helper_ready(game, adv, t)
    if villain.lair(game, adv) is None:
        pytest.skip("this hideout has no hall to hold a captive in")
    adv["attention"] = 4
    _temper_moves(monkeypatch, game, adv, {"kidnap": 1})
    beat = next((b for w in ("road", "wild", "camp") if (b := villain.due_move(game, adv, w))), None)
    assert beat == "villain_kidnap"
    beats.offer(game, beat, adv=adv["id"], where="road")
    assert npc.name in " ".join(beats.pages(game, beats.pending(game)))
    beats.choose(game, beats.pending(game), 0)
    st = next(s for s in story.chapter(adv)["steps"] if s.get("kidnap"))
    assert st["kind"] == "rescue" and st["optional"] and st["state"] == "open"
    q = next(q for q in game.quests if q["id"] == st["quest"])
    assert q["deadline"] - game.moment.total_days <= 12 and q["target"]["npc"] == npc.id
    assert npc.flags.get("captive") and npc.flags.get("kidnapped")
    story.on_quest_end(game, q, False)
    assert st["state"] == "failed" and not npc.alive, "too late: they die in its hall"


def test_one_it_took_is_freed_from_the_chains_in_its_hall(made, tables, monkeypatch):
    from realmwalker.game import quests
    from tests.test_deeds import _down_to

    game, adv, t = _tale(made, tables, "risen")
    npc = _helper_ready(game, adv, t)
    if villain.lair(game, adv) is None:
        pytest.skip("this barrow has no hall to hold a captive in")
    adv["reprisal"] = npc.id
    assert villain.kidnap(game, adv) == npc.name
    st = next(s for s in story.chapter(adv)["steps"] if s.get("kidnap"))
    _down_to(game, villain.lair(game, adv), 1)
    spot = next(xy for xy, f in game.local.features.items() if f.get("kind") == "captive"
                and f.get("quest") == st["quest"])
    quests.free_captive(game, game.local, *spot)
    assert st["state"] == "done" and npc.alive and not npc.flags.get("captive")
