"""The Risen and the Outlaw Lord, first forms (Expansion 6 D.3, docs/ADVENTURES.md §6.2): both tales forge on a real
world and read clean in the storybook; the risen king's letter in an old hand and the gang's warning on your door
are pages kept in the pack; the ford is held at night between burning carts, with the militia you raised, in a real
fight; the rite lays him to rest; the finale in his barrow (the barrow wakes at half his hit points, the keys found
take hold) and in the outlaw's hideout are real fights; the inside man is followed at midnight; a parley ends the
gang without blood, a broken gang ends its threat."""

import copy
from types import SimpleNamespace

import pytest

from realmwalker.game import camp, dungeon, letters
from realmwalker.game import story
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.state import new_game
from realmwalker.game.story import beats, cast, deeds, endings, places, stage
from realmwalker.rules.combat import FOE, PARTY
from realmwalker.rules.engine.handlers import bosses
from realmwalker.world import threats
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world

pytestmark = pytest.mark.story


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Threatland", 61, "medium"), tables)


def _tale(made, tables, kind):
    """A new hero in the town nearest a threat of this kind, its tale taken on."""
    w = copy.deepcopy(made)
    found = [t for t in threats.records(w).values() if t["kind"] == kind and t["state"] != "ended"]
    assert found, f"this world has a threat of the {kind}"
    for t in found:
        town = min((s for s in w.settlements if s.kind in ("town", "village")),
                   key=lambda s: threats.distance(w, t, s.x, s.y))
        game = new_game(w, tables, start_settlement=town.id)
        game.survival = False
        t = threats.records(game.world)[t["id"]]
        if t["state"] == "dormant":
            threats.stir(game.world, tables, t, game.world.rng, day=0)
        story.take_hook(game, t["id"])
        if story.active(game):
            adv = story.active(game)[0]
            beats.director(game.world)["card"] = None
            return game, adv, t
    pytest.fail(f"no tale of the {kind} could be forged here")


def _step(adv, kind, chapter=None):
    return next(s for i, ch in enumerate(adv["chapters"]) for s in ch["steps"]
                if s["kind"] == kind and (chapter is None or i == chapter))


def _open_chapter(game, adv, n):
    """Steps of the chapters before n done (the tale moved on, as by play)."""
    for ch in adv["chapters"][:n]:
        for st in ch["steps"]:
            if st["state"] == "open":
                st["state"] = "done"
        ch["state"] = "done"
    adv["chapter"] = n
    adv["chapters"][n]["state"] = "open"
    deeds.setup(game, adv)
    beats.director(game.world)["card"] = None


def _stand(game, place):
    game.player.x, game.player.y = places.xy(game.world, place)


def _play(game, i=0):
    rec = beats.pending(game)
    assert rec is not None, "a beat waits"
    return rec, beats.choose(game, rec, i)


def _to_level(game, place, level=None):
    w = game.world
    site = w.sites[place["site"]]
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    depth = level or dungeon.gen.depth_for(w, site)
    dungeon.descend(game, 1)
    while int(game.local.meta.get("level", 1)) < depth:
        dungeon.descend(game, int(game.local.meta["level"]) + 1)


def test_both_tales_forge_and_read_clean_in_the_storybook(made, tables):
    from tools import storybook

    for kind, bid in (("risen", "risen"), ("outlaw", "outlaw")):
        game, adv, t = _tale(made, tables, kind)
        assert adv["blueprint"] == bid and len(adv["chapters"]) == 3
        assert storybook.problems(game, adv) == []
        text = storybook.synopsis(game, adv)
        assert adv["title"].upper() in text and "FINALE" in text
        assert t["villain"]["temper"] in game.tables.threats["kinds"][kind]["tempers"]


def test_each_kind_is_asked_about_in_its_own_words(made, tables):
    game, adv, t = _tale(made, tables, "risen")
    assert story.asking(game, adv, "learn_ask", "?").startswith("Who was ")
    group, name = story.villain_group(game, adv)
    assert group == "barrow_wight" and name
    game, adv, t = _tale(made, tables, "outlaw")
    assert story.villain_group(game, adv)[0] == "bandit_hideout"
    assert "caravans" in story.asking(game, adv, "learn_ask", "?")


def test_the_risen_king_writes_in_an_old_hand(made, tables):
    game, adv, t = _tale(made, tables, "risen")
    _open_chapter(game, adv, 1)
    beats.offer(game, "risen_letter", adv=adv["id"], where="camp")
    rec, lines = _play(game, 1)
    assert game.letter is not None
    letter = letters.records(game.world)[game.letter]
    assert letter["hand"] == "dark" and len(letter["lines"]) >= 2
    assert not any("{" in line for line in letter["lines"]), letter["lines"]
    assert any(letters.lid_of(it) == game.letter for it in game.leader.inventory), "kept in the pack"
    assert "kept_his_letter" in adv["flags"]


def test_the_gang_nails_a_warning_to_your_door(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    beats.offer(game, "outlaw_warning", adv=adv["id"], where="inn")
    _play(game, 0)
    assert game.letter is not None and letters.records(game.world)[game.letter]["hand"] == "dark"
    assert any(it.def_id == "dagger" for it in game.leader.inventory), "the knife, kept"


def test_the_ford_is_held_at_night_between_burning_carts(made, tables, monkeypatch):
    from realmwalker.game.fight import start_battle
    from tools.arena import run

    game, adv, t = _tale(made, tables, "risen")
    _open_chapter(game, adv, 2)
    adv["keys"].append("militia")
    hold = _step(adv, "hold", 2)
    assert hold["target"]["field"] == "ford" and hold["target"].get("night") is not None
    game.world.time += 1440 * (int(hold["target"]["night"]) - int(game.moment.total_days) + 1)
    _stand(game, adv["places"]["ford"])
    assert story.on_arrive(game) and game.encounter is not None and game.encounter.field == "ford"
    enc = game.encounter
    for c in game.party:
        c.level = max(c.level, adv["target_level"])
    b = start_battle(game, enc.creatures, enc.intro)
    T = tables.terrain.index
    assert (b.field.terrain == T["cart"]).sum() >= 3 and (b.field.terrain == T["ford"]).sum() >= 2
    assert any(z.kind == "fire" and z.owner is None for z in b.zones), "the carts are burning"
    militia = [f for f in b.side(PARTY) if f.bond and f.bond.get("kind") == "story_ally"]
    assert len(militia) == 2, "the people you raised stand with you"
    for f in b.side(PARTY):
        f.auto = True
    run(b, max_steps=4000)
    assert b.outcome is not None


def test_the_rite_lays_him_to_rest(made, tables, monkeypatch):
    monkeypatch.setattr(camp, "check", lambda game, skill, dc, **kw: (True, f"{skill} check: success"))
    game, adv, t = _tale(made, tables, "risen")
    _open_chapter(game, adv, 2)
    for kind in ("rally", "hold"):
        _step(adv, kind, 2)["state"] = "done"
    adv["keys"].append("anchor")
    _stand(game, adv["places"]["home"])
    assert story.on_arrive(game)
    rec, _ = _play(game, 0)
    assert rec["beat"] == "risen_the_barrow"
    assert beats.pending(game) is not None and beats.pending(game)["beat"] == "risen_the_rite"
    _play(game, 0)
    assert adv["state"] == "won" and adv["ending"] == "laid_to_rest"
    site = str(t["home"]["site"])
    assert site in game.world.politics["laid"] and t["state"] == "ended" and t["outcome"] == "laid"
    assert adv["epilogue"] and not any("{" in p["text"] for p in adv["epilogue"])


def test_the_finale_under_the_barrow_in_a_real_fight(made, tables):
    from tools.arena import run

    game, adv, t = _tale(made, tables, "risen")
    _open_chapter(game, adv, 2)
    for kind in ("rally", "hold", "go"):
        _step(adv, kind, 2)["state"] = "done"
    _step(adv, "rite", 2)["state"] = "done"
    adv["keys"] += ["anchor", "name", "ford"]
    prepare_town(game, game.world.settlements[adv["places"]["town"]["settlement"]])
    for c in game.party:
        c.level = max(c.level, adv["target_level"])
    _to_level(game, adv["places"]["home"])
    band = next(a for a in game.local.actors if a.creatures and (getattr(a.creatures[0], "story", None) or {})
                .get("role") == "villain")
    assert band.creatures[0].def_id == "wight" and band.creatures[0].named
    assert story.hold_for_finale(game, band)
    story.fight_finale(game)
    b = game.battle
    boss = next(f for f in b.side(FOE) if f.creature is not None and (f.creature.story or {}).get("role") == "villain")
    assert boss.cdef.get("legendary_resistance") is None, "what bound him is in your hands"
    assert boss.cdef["boss_phase"]["kind"] == "raise"
    before = len(b.side(FOE))
    boss.hp = boss.max_hp // 2 - 1
    bosses.after_damage(b, boss)
    assert len(b.side(FOE)) == before + 2, "the barrow wakes: its sarcophagi open"
    for f in b.side(PARTY):
        f.auto = True
    run(b, max_steps=4000)
    assert b.outcome is not None


def test_destroyed_with_his_crown_he_is_gone_for_good_and_without_it_he_returns(made, tables):
    for keys, ending in ((["anchor"], "destroyed"), ([], "destroyed_for_now")):
        game, adv, t = _tale(made, tables, "risen")
        _open_chapter(game, adv, 2)
        adv["keys"] = list(keys)
        boss = SimpleNamespace(story={"adv": adv["id"], "role": "villain"}, name="him")
        story.on_battle(game, SimpleNamespace(outcome="victory", dead=[boss], captives=[], fled=[]))
        assert adv["ending"] == ending and adv["state"] == "won"
        if ending == "destroyed":
            assert t["state"] == "ended" and str(t["home"]["site"]) in game.world.politics["laid"]
        else:
            assert t["state"] == "dormant" and t.get("sequel") == "returns", "he will be back"


def test_the_inside_man_is_followed_at_midnight(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    _open_chapter(game, adv, 1)
    learn = _step(adv, "learn", 1)
    assert any(r["how"] == "tail" for r in learn["target"]["routes"])
    town = game.world.settlements[adv["places"]["town"]["settlement"]]
    game.player.x, game.player.y = town.x, town.y
    game.enter_local()
    suspect = cast.person(game.world, adv["cast"]["suspect"])
    if suspect is None:
        suspect = next(n for n in npcs_in(game.world, town.id) if n.alive and story._is(game, adv["cast"]["suspect"], n))
    day = int(game.moment.total_days)
    game.world.time = (day + 1) * 1440 + 30  # (half past midnight)
    story.on_town_tick(game, game.local, town)
    rec = stage.current(game)
    assert rec is not None and rec["id"] == "midnight_tail" and rec["cast"]["suspect"] == suspect.id
    stage._learn(game, rec, "inside_followed")  # (followed to the gate unseen)
    assert learn["state"] == "done" and "inside" in adv["clues"] and "inside_followed" in adv["flags"]
    stage.end(game)


def test_a_parley_ends_the_gang_without_blood(made, tables, monkeypatch):
    monkeypatch.setattr(camp, "check", lambda game, skill, dc, **kw: (True, f"{skill} check: success"))
    game, adv, t = _tale(made, tables, "outlaw")
    _open_chapter(game, adv, 2)
    adv["flags"].append("parley")
    gang = threats.gang_of(game.world, t)
    fig = threats.villain_figure(game.world, t)
    _stand(game, adv["places"]["home"])
    assert story.on_arrive(game)
    _play(game, 0)
    assert adv["ending"] == "pardoned" and adv["state"] == "won"
    assert not gang.active and fig.alive, "the band disbands; its captain lives"
    assert t["state"] == "ended"


def test_the_hideout_in_a_real_fight_and_the_gang_broken(made, tables):
    from tools.arena import run

    game, adv, t = _tale(made, tables, "outlaw")
    _open_chapter(game, adv, 2)
    _step(adv, "go", 2)["state"] = "done"
    adv["keys"] += ["backway", "inside"]
    for c in game.party:
        c.level = max(c.level, adv["target_level"])
    _to_level(game, adv["places"]["home"])
    band = next(a for a in game.local.actors if a.creatures and (getattr(a.creatures[0], "story", None) or {})
                .get("role") == "villain")
    assert band.creatures[0].def_id == "bandit_captain"
    assert story.hold_for_finale(game, band)
    story.fight_finale(game)
    b = game.battle
    assert b.env.surprised == FOE, "in by the back way"
    for f in b.side(PARTY):
        f.auto = True
    run(b, max_steps=4000)
    assert b.outcome is not None
    gang = threats.gang_of(game.world, t)
    fig = threats.villain_figure(game.world, t)
    game.battle = None
    boss = SimpleNamespace(story={"adv": adv["id"], "role": "villain"}, name=fig.full_name())
    story.on_battle(game, SimpleNamespace(outcome="victory", dead=[boss], captives=[], fled=[]))
    assert adv["ending"] == "broken" and not gang.active and not fig.alive and t["state"] == "ended"


def test_the_captain_taken_alive_hangs(made, tables):
    game, adv, t = _tale(made, tables, "outlaw")
    _open_chapter(game, adv, 2)
    fig = threats.villain_figure(game.world, t)
    boss = SimpleNamespace(story={"adv": adv["id"], "role": "villain"}, name=fig.full_name())
    story.on_battle(game, SimpleNamespace(outcome="victory", dead=[], captives=[boss], fled=[]))
    assert adv["ending"] == "taken" and not fig.alive and t["state"] == "ended"


def test_both_tales_pass_the_start_up_check(tables):
    from realmwalker.game.story import check

    assert check.problems(tables) == []
    assert "letter" in beats.OPS and "finish" in beats.OPS and "key" in beats.CONDITIONS
    assert {"risen_laid", "risen_destroyed", "outlaw_broken", "outlaw_pardoned"} <= set(endings.OPS)
