"""Rumours, letters and notice boards that lead somewhere (Expansion 6 G.5, docs/ADVENTURES.md §5.14): a townsperson
won over tells of the nearest real trouble (its den goes on the map, its tale is offered), points at where a tale you
have taken goes on (who knows, who saw it, where to look; never the same pointer twice), an ordinary rumour may be
about a real threat near, and a dead stranger's letter found in a chest may be about one and offer its tale."""

import copy

import pytest

from realmwalker.game import books, story
from realmwalker.game.dialogue import Conversation, builtin_special
from realmwalker.game.people import prepare_town
from realmwalker.game.state import new_game
from realmwalker.game.story import beats, rumours
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


def _near_a_threat(made, tables, kind="beast"):
    w = copy.deepcopy(made)
    live = [t for t in threats.records(w).values() if t["kind"] == kind and t["state"] != "ended"]
    if not live:
        pytest.skip(f"no {kind}")
    t = live[0]
    for other in threats.records(w).values():
        if other is not t:
            other["state"] = "ended"
    town = min((s for s in w.settlements if s.kind in ("town", "village")),
               key=lambda s: threats.distance(w, t, s.x, s.y))
    g = new_game(w, tables, start_settlement=town.id)
    g.survival = False
    d = beats.director(g.world)
    d["opening"] = None
    d["pending"] = None
    t = threats.records(g.world)[t["id"]]
    if t["state"] == "dormant":
        threats.stir(g.world, tables, t, g.world.rng, day=0)
    if threats.distance(g.world, t, town.x, town.y) > rumours.reach(g):
        pytest.skip("the threat is beyond a week's walk")
    prepare_town(g, town)
    return g, t, town


def _someone(game, town, notable=False):
    return next(n for n in game.world.npcs.values() if n.settlement == town.id and n.alive and
                n.notable == notable and not n.flags.get("story"))


def test_a_rumour_won_from_someone_offers_the_nearest_tale(made, tables):
    game, t, town = _near_a_threat(made, tables)
    hx, hy = threats.home_xy(game.world, t)
    game.player.explored[hx, hy] = False
    conv = Conversation(game, _someone(game, town))
    conv.apply_outcome("reveal_hook", "")
    said = " ".join(text for _, text in conv.lines)
    assert threats.villain_name(game.world, t) in said or threats.home_name(game.world, t) in said
    assert game.player.explored[hx, hy], "its den is on the map"
    assert (hx, hy, "sign") in story.map_signs(game), "and its claw marks with it"
    rec = beats.pending(game)
    assert rec is not None and rec["beat"] == "story_hook" and rec["words"]["threat"] == t["id"]
    story.take_hook(game, t["id"])
    assert story.active(game) and t.get("adventure"), "taking it forges the tale"


def test_with_nothing_near_it_is_only_news(made, tables):
    game, t, town = _near_a_threat(made, tables)
    t["state"] = "ended"
    conv = Conversation(game, _someone(game, town))
    conv.apply_outcome("reveal_hook", "")
    assert conv.lines and beats.pending(game) is None


def test_a_rumour_does_not_push_aside_a_waiting_moment(made, tables):
    game, t, town = _near_a_threat(made, tables)
    waiting = beats.offer(game, "story_hook", words={"threat": "T0"})
    lines = rumours.tell_hook(game, town, game.world.rng.child("t"))
    assert lines and beats.pending(game) is waiting


def test_a_clue_points_where_the_tale_goes_on_and_is_never_told_twice(made, tables):
    game, t, town = _near_a_threat(made, tables)
    story.take_hook(game, t["id"])
    adv = story.active(game)[0]
    pointers = rumours._pointers(game, adv)
    if not pointers:
        pytest.skip("this chapter has nothing to point at")
    npc = _someone(game, town)
    before = len(adv["journal"])
    lines = rumours.tell_clue(game, npc, game.world.rng.child("c1"))
    assert lines, "someone points the way"
    assert adv["hints"] == [pointers[0][0]] and len(adv["journal"]) == before + 1
    key, table, values = pointers[0]
    if values.get("_npc") is not None:
        assert values["_npc"].known and values["_npc"].name in lines[0]
    if values.get("_at") is not None:
        assert values["place"] in lines[0]
    for i in range(len(pointers) + 1):
        rumours.tell_clue(game, npc, game.world.rng.child(f"c{i + 2}"))
    assert len(adv["hints"]) == len(set(adv["hints"])), "a pointer is told once"
    conv = Conversation(game, npc)
    conv.apply_outcome("reveal_clue", "")  # (nothing left to point at: they say so)
    assert conv.lines and conv.lines[-1][0] == "npc"


def test_the_clue_option_needs_a_tale(made, tables):
    game, t, town = _near_a_threat(made, tables)
    npc = _someone(game, town)
    for i in range(20):
        opts = builtin_special(game, npc, game.world.rng.child(f"s{i}"))
        assert all(o["success"]["outcome"] != "reveal_clue" for o in opts)
    story.take_hook(game, t["id"])
    seen = {o["success"]["outcome"] for i in range(40) for o in builtin_special(game, npc, game.world.rng.child(f"s{i}"))}
    assert "reveal_clue" in seen and "reveal_hook" in seen


def test_won_over_in_talk_through_the_special_option(made, tables, monkeypatch):
    game, t, town = _near_a_threat(made, tables)
    npc = _someone(game, town)
    conv = Conversation(game, npc)
    conv.special = [dict(o, used=False) for o in game.tables.dialogue["special"]["any"]
                    if o["success"]["outcome"] == "reveal_hook"]
    monkeypatch.setattr(Conversation, "check", lambda self, skill, dc: (True, "<dice>won</>"))
    conv.choose(next(c for c in conv.menu() if c.id == "special"))
    assert beats.pending(game) is not None and beats.pending(game)["words"]["threat"] == t["id"]


def test_an_ordinary_rumour_may_be_about_a_real_threat(made, tables, monkeypatch):
    game, t, town = _near_a_threat(made, tables)
    monkeypatch.setattr(rumours, "RUMOUR_CHANCE", 1.0)
    line = rumours.rumour_line(game, town.x, town.y, game.world.rng.child("r"))
    assert line and threats.home_name(game.world, t) in line
    assert beats.pending(game) is None, "a rumour is not an offer"


def test_a_found_letter_can_start_a_tale(made, tables, monkeypatch):
    game, t, town = _near_a_threat(made, tables)
    monkeypatch.setattr(rumours, "LETTER_CHANCE", 1.0)
    hx, hy = threats.home_xy(game.world, t)
    game.player.explored[hx, hy] = False
    it = add_item(game.leader, game.tables.items, "found_letter", 1)
    lines = books.read(game, game.leader, it)
    assert any(threats.home_name(game.world, t) in line for line in lines)
    assert game.player.explored[hx, hy]
    rec = beats.pending(game)
    assert rec is not None and rec["words"]["threat"] == t["id"]
    beats.director(game.world)["pending"] = None
    assert books.read(game, game.leader, it) == lines and beats.pending(game) is None, "read again: the same words"
