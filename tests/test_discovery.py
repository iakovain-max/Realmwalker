"""Experience for discovery (design section 6: "XP comes from combat, quests, discovery (new regions, ruins, lore) and
notable deeds"). The first time a character enters a region, reaches a site or goes down to a level under the
ground, everyone in the party gains a little (data/rules.json "discovery_xp", times each one's level)."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import dungeon, encounters, events, save
from realmwalker.game.state import GameState, new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.ui import markup
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Wander", 19, "small"), tables)


@pytest.fixture
def game(world, tables, monkeypatch):
    monkeypatch.setattr(encounters, "encounter_chance", lambda *a, **k: 0.0)
    monkeypatch.setattr(events, "event_chance", lambda *a, **k: 0.0)
    monkeypatch.setattr(GameState, "lost_dc", lambda self: 0)
    g = new_game(copy.deepcopy(world), tables, CharacterBuilder(tables, RNG(1, "hero")).build())
    g.survival = False
    return g


def said(game, since: int) -> list[str]:
    return [markup.plain(m.text) for m in game.log.messages[since:]]


def walk_into_a_new_region(game):
    """Stand at the edge of a region you know and step over into one you don't; returns the log index before."""
    w, p = game.world, game.player
    for x in range(1, w.width - 1):
        for y in range(1, w.height - 1):
            a = w.area_at(x, y)
            if a is None or not game.step_minutes(x, y, x + 1, y):
                continue
            b = w.area_at(x + 1, y)
            if b is not None and b is not a and b.id not in p.visited_areas and w.settlement_at(x + 1, y) is None \
                    and w.site_at(x + 1, y) is None and game.step_minutes(x, y, x + 1, y):
                p.x, p.y = x, y
                p.visited_areas.add(a.id)
                p.steps = max(p.steps, 1)
                before = len(game.log.messages)
                game.move(1, 0)
                assert (p.x, p.y) == (x + 1, y)
                return before
    raise AssertionError("no border to cross")


def test_the_first_region_you_enter_gives_experience_but_not_where_you_start(game):
    start_xp = game.leader.xp
    assert start_xp == 0 and not any("experience" in t for t in said(game, 0))  # being born there is no discovery
    before = walk_into_a_new_region(game)
    lines = said(game, before)
    assert any(t.startswith("You enter") and "(+10 experience)" in t for t in lines), lines
    assert game.leader.xp == 10


def test_a_region_counts_once(game):
    walk_into_a_new_region(game)
    xp = game.leader.xp
    area = game.world.area_at(game.player.x, game.player.y)
    game.player.visited_areas.add(area.id)
    game._arrive(None)  # back in a region already known
    assert game.leader.xp == xp


def test_reaching_a_site_and_going_under_count_once_each(game, tables):
    site = next(s for s in game.world.sites if game.world.site_at(s.x, s.y) is s)
    p = game.player
    p.x, p.y = site.x, site.y
    p.steps = 1
    p.visited_areas.add(game.world.area_at(p.x, p.y).id if game.world.area_at(p.x, p.y) else -1)
    before = len(game.log.messages)
    game._arrive(game.world.area_at(p.x, p.y))
    assert any("You come upon" in t and "(+25 experience)" in t for t in said(game, before))
    xp = game.leader.xp
    game._arrive(game.world.area_at(p.x, p.y))  # again: nothing more
    assert game.leader.xp == xp
    p.local_key = None
    game.enter_local()
    before = len(game.log.messages)
    dungeon.descend(game, 1)
    assert any("You go down" in t and "(+25 experience)" in t for t in said(game, before))
    assert game.leader.xp == xp + 25
    p.local_key = None
    game.enter_local()
    dungeon.descend(game, 1)  # the same level again
    assert game.leader.xp == xp + 25


def test_everyone_in_the_party_learns_and_by_their_level(game, tables):
    from realmwalker.rules.progression import award_xp

    friend = CharacterBuilder(tables, RNG(7, "friend")).build()
    friend.is_player = False
    award_xp(friend, 900, tables, RNG(1), auto=True)
    assert friend.level == 3
    game.party.append(friend)
    note, _ = game.discover("site", "site:test")
    assert note == " <dim>(+25 experience)</>"
    assert game.leader.xp == 25 and friend.xp == 900 + 75


def test_nothing_when_the_data_says_nothing(game, tables, monkeypatch):
    monkeypatch.setitem(tables.rules, "discovery_xp", {"region": 0, "site": 0, "deeper": 0})
    assert game.discover("site", "site:1") == ("", [])
    assert game.leader.xp == 0


def test_discoveries_are_kept_in_the_save(game, tmp_path):
    game.discover("deeper", "deeper:3/2")
    folder = save.save_game(game, tmp_path)
    loaded = save.load_game(folder, game.tables)
    assert "deeper:3/2" in loaded.player.discoveries
