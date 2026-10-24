"""The story's hooks in a real game (Expansion 6 A.6): a new life is offered the Beast's hook; taking it forges the
tale; each listener moves its step - arriving at the kill, its search, the witness's words, the route to its
weakness, the means carried, the choice of bait or tracks and the fight it brings, the den, and the finale's band on
its level - until the ending, the epilogue and the epithet."""

import copy
from types import SimpleNamespace

import pytest

from realmwalker.game import camp, dungeon
from realmwalker.game import story
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import prepare_town
from realmwalker.game.state import new_game
from realmwalker.game.story import beats, cast, forge, places
from realmwalker.rules.inventory import add_item
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
    return cached_world(WorldOptions("Forgeland", 77, "medium"), tables)


def _start_near_a_beast(made, tables):
    w = copy.deepcopy(made)
    beasts = [t for t in threats.records(w).values() if t["kind"] == "beast" and t["state"] != "ended"]
    if not beasts:
        pytest.skip("no beast")
    t = beasts[0]
    town = min((s for s in w.settlements if s.kind in ("town", "village")),
               key=lambda s: threats.distance(w, t, s.x, s.y))
    g = new_game(w, tables, start_settlement=town.id)
    g.survival = False
    return g, threats.records(g.world)[t["id"]]


def _play(game, choice=0):
    rec = beats.pending(game)
    assert rec is not None, "a beat waits"
    return beats.choose(game, rec, choice)


def _choice(game, words):
    rec = beats.pending(game)
    for c in beats.choices(game, rec):
        if words in c["label"]:
            return c["i"]
    raise AssertionError(f"no choice with {words!r}: {[c['label'] for c in beats.choices(game, rec)]}")


def _stand(game, place):
    game.player.x, game.player.y = places.xy(game.world, place)


def test_a_new_life_is_offered_a_tale_on_its_first_day(made, tables):
    game, t = _start_near_a_beast(made, tables)
    d = beats.director(game.world)
    assert any(item.get("hook") for item in d.get("scheduled", [])), "a hook is waiting for the first day"
    story.daily(game)
    rec = beats.pending(game)
    assert rec is not None and rec["beat"] == "story_hook" and game.busy
    assert rec["words"]["threat"] in threats.records(game.world)


def test_the_beast_from_its_hook_to_its_ending(made, tables, monkeypatch):
    game, _ = _start_near_a_beast(made, tables)
    story.daily(game)
    tid = beats.pending(game)["words"]["threat"]
    t = threats.records(game.world)[tid]
    _play(game, _choice(game, "hunt it"))
    adv = story.active(game)[0]
    assert t["adventure"] == adv["id"] and beats.director(game.world)["card"]["chapter"] == 0
    beats.director(game.world)["card"] = None
    monkeypatch.setattr(camp, "check", lambda game, skill, dc, **kw: (True, f"{skill} check: success"))

    # I. The Killings: the kill, its search, the witness.
    _stand(game, adv["places"]["kill"])
    assert story.on_arrive(game) and beats.pending(game)["beat"] == "beast_kill_found"
    _play(game)
    assert beats.pending(game)["beat"] == "beast_search_kill", "the search follows the arrival"
    _play(game, _choice(game, "tooth"))
    assert "took_tooth" in adv["flags"] and adv["clues"].get("size")
    town = game.world.settlements[adv["places"]["town"]["settlement"]]
    prepare_town(game, town)
    witness = cast.person(game.world, adv["cast"]["witness"])
    assert witness is not None
    conv = Conversation(game, witness)
    choice = next(c for c in conv.menu() if c.id == "story_witness")
    conv.choose(choice)
    assert adv["chapter"] == 1 and adv["chapters"][0]["state"] == "done"
    beats.director(game.world)["card"] = None

    # II. The Hunt's Price: what it fears (at the kill), the means, bait or tracks, and the fight.
    _stand(game, adv["places"]["kill"])
    assert story.on_arrive(game) and beats.pending(game)["beat"] == "beast_lore_at_kill"
    _play(game)
    assert "weakness" in adv["keys"]
    means = story.find_step(game, adv["id"], "price.2")["target"]["means"]
    add_item(game.leader, game.tables.items, means[0], 1)
    beats.director(game.world)["day"] = -1  # (the next day)
    story.daily(game)
    assert story.find_step(game, adv["id"], "price.2")["state"] == "done"
    beats.offer(game, "beast_bait_or_track", adv=adv["id"], step="price.3", where="wild")
    _play(game, _choice(game, "Follow the blood"))
    assert "tracked" in adv["flags"] and game.encounter is not None
    beast = game.encounter.creatures[0]
    assert beast.story == {"adv": adv["id"], "role": "villain"}
    game.encounter = None
    story.on_battle(game, SimpleNamespace(outcome="defeat", dead=[], captives=[], fled=[beast]))
    assert adv["chapter"] == 2, [s["state"] for s in adv["chapters"][1]["steps"]]
    beats.director(game.world)["card"] = None

    # III. The Den: its mouth, then the finale's band on the deepest level.
    _stand(game, adv["places"]["home"])
    assert story.on_arrive(game) and beats.pending(game)["beat"] == "beast_the_den"
    _play(game, _choice(game, "quietly"))
    assert "quiet" in adv["keys"]
    game.enter_local()
    site = game.world.sites[adv["places"]["home"]["site"]]
    depth = dungeon.gen.depth_for(game.world, site)
    dungeon.descend(game, 1)
    while int(game.local.meta.get("level", 1)) < depth:
        dungeon.descend(game, int(game.local.meta["level"]) + 1)
    band = [a for a in game.local.actors if a.creatures and getattr(a.creatures[0], "story", None)]
    assert band and band[0].creatures[0].story["role"] == "villain"
    villain = band[0].creatures[0]
    fig = threats.villain_figure(game.world, t)
    game.local.actors.remove(band[0])
    fame = game.renown.fame
    story.on_battle(game, SimpleNamespace(outcome="victory", dead=[villain], captives=[], fled=[]))
    assert adv["state"] == "won" and adv["ending"] == "slain"
    assert not fig.alive and t["state"] == "ended"
    assert game.epilogue == {"adv": adv["id"]} and adv["epilogue"]
    assert game.renown.legend.get("offered"), "an epithet is offered"
    assert game.renown.fame > fame
    assert any(e.get("data", {}).get("adventure") == adv["id"] for e in game.world.history)


def test_the_hero_s_death_orphans_the_tale(made, tables):
    game, t = _start_near_a_beast(made, tables)
    adv = forge.make(game, t)
    story.on_death(game)
    assert adv["state"] == "orphaned" and t["adventure"] is None
    assert beats.pending(game) is None


def test_the_villain_answers_at_night(made, tables):
    game, t = _start_near_a_beast(made, tables)
    adv = forge.make(game, t)
    adv["attention"] = 3
    game.world.time += (24 - game.moment.hour + 1) * 60  # (an hour past midnight)
    assert story.on_night(game, "camp")
    assert beats.pending(game)["beat"] in ("beast_test_night", "beast_omen")


def test_the_board_shows_every_stirring_threat_near(made, tables):
    game, t = _start_near_a_beast(made, tables)
    if t["state"] not in threats.LIVE:
        threats.stir(game.world, tables, t, game.world.rng, day=0)
    town = game.world.settlements[t["stakes"][0]] if t["stakes"] else game.world.settlements[0]
    lines = story.notices(game, town)
    assert any(threats.villain_name(game.world, t) in line for line in lines)


def test_a_tale_and_its_foes_are_saved_and_come_back_the_same(made, tables, tmp_path):
    """Story records are JSON-native: they come back from a save exactly as they were (A.11)."""
    import json

    from realmwalker.game import save

    game, t = _start_near_a_beast(made, tables)
    adv = forge.make(game, t)
    game.renown.legend["epithet"] = "the Hunter"
    site = game.world.sites[adv["places"]["home"]["site"]]
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    depth = dungeon.gen.depth_for(game.world, site)
    dungeon.descend(game, 1)
    while int(game.local.meta.get("level", 1)) < depth:
        dungeon.descend(game, int(game.local.meta["level"]) + 1)
    folder = save.save_game(game, tmp_path)
    back = save.load_game(folder, tables)
    for key in ("threats", "adventures", "director", "story_sites", "story_people"):
        mine = game.world.politics.get(key)
        assert json.loads(json.dumps(mine)) == mine, key
        assert back.world.politics.get(key) == mine, key
    assert back.renown.legend["epithet"] == "the Hunter"
    lm = back.world.local_maps[game.local.key]
    assert any(getattr(c, "story", None) == {"adv": adv["id"], "role": "villain"} for a in lm.actors
               for c in a.creatures)
