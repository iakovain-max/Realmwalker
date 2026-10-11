"""Finding your way on foot (after v1): walk to a spot on a close-up map, walk up to someone to talk, and jump
between the places you have seen with Tab in look mode."""

import copy

import pytest

from realmwalker.game import wayfinding
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Streetland", 8, "medium"), tables).generate()


@pytest.fixture
def town(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    s = max(game.world.settlements, key=lambda s: s.population)
    game.player.x, game.player.y = s.x, s.y
    game.player.local_key = None
    game.enter_local()
    game.local.seen[:] = True  # as if you had walked every street
    game.world.time = (game.moment.total_days + 1) * 1440 + 11 * 60  # late morning: people are about
    return game, s


def walk(game, limit=400):
    steps = 0
    while game.walk_to is not None and steps < limit:
        wayfinding.step(game)
        steps += 1
    return steps


def test_the_places_of_a_town_are_known_once_seen(town):
    game, s = town
    labels = [label for _, _, label in wayfinding.places(game)]
    assert any(label.startswith("the inn") for label in labels), labels
    assert any(label.startswith(("the shop", "the smithy", "the market")) for label in labels), labels
    game.local.seen[:] = False
    assert not any(label.startswith("the inn") for _, _, label in wayfinding.places(game)), "not until seen"


def test_you_can_walk_to_the_inn(town):
    game, s = town
    inn = next((x, y) for x, y, label in wayfinding.places(game) if label.startswith("the inn"))
    assert wayfinding.begin(game, inn, talk=False)
    walk(game)
    p = game.player
    assert game.talk_to is None, "walking to a door is not walking up to whoever stands in it"
    in_the_way = any("is in your way" in m.text for m in game.log.messages[-2:])
    assert max(abs(p.lx - inn[0]), abs(p.ly - inn[1])) <= 1 or in_the_way, ((p.lx, p.ly), inn)


def test_walking_up_to_someone_starts_a_conversation(town):
    game, s = town
    p = game.player
    folk = [n for n in npcs_in(game.world, s.id) if n.alive and n.present and n.notable]
    npc = min(folk, key=lambda n: abs(n.x - p.lx) + abs(n.y - p.ly))
    assert wayfinding.begin(game, (npc.x, npc.y))
    walk(game)
    assert game.talk_to == npc.id, "you follow them if they wander, and talk when you reach them"


def test_a_walk_stops_for_trouble(town, monkeypatch):
    game, s = town
    inn = next((x, y) for x, y, label in wayfinding.places(game) if label.startswith("the inn"))
    wayfinding.begin(game, inn)
    real_move = type(game).move

    def move_and_worry(self, dx, dy):
        ok = real_move(self, dx, dy)
        self.say("Somebody shouts for the watch.", "warn")
        return ok

    monkeypatch.setattr(type(game), "move", move_and_worry)
    assert walk(game) == 1


def test_there_is_no_walking_to_what_you_have_not_seen(town):
    game, s = town
    game.local.seen[:] = False
    p = game.player
    game.local.seen[p.lx, p.ly] = True
    assert not wayfinding.begin(game, (p.lx + 5, p.ly))


def test_underground_the_stairs_are_a_place(tables, world):
    from realmwalker.game import dungeon

    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    site = game.world.sites[0]
    game.player.x, game.player.y = site.x, site.y
    game.player.local_key = None
    game.enter_local()
    dungeon.descend(game, 1)
    p = game.player
    lm = game.local
    lm.seen[:] = True
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    # (you arrive on the stairs, and where you stand is not a place to walk to: step off them)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
        if lm.in_bounds(p.lx + dx, p.ly + dy) and walk[p.lx + dx, p.ly + dy]:
            p.lx, p.ly = p.lx + dx, p.ly + dy
            break
    labels = [label for _, _, label in wayfinding.places(game)]
    assert "the stairs up" in labels or "the stairs down" in labels, labels


def test_look_tab_and_enter_walk_you_there(make_app, world):
    from realmwalker.ui.input import KeyEvent

    app = make_app()
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    s = max(game.world.settlements, key=lambda s: s.population)
    game.player.x, game.player.y = s.x, s.y
    app.start_game(game)
    game.enter_local()
    game.local.seen[:] = True
    gs = app.top
    app.handle_event(KeyEvent("l"))
    app.handle_event(KeyEvent("tab"))
    first = gs.look
    assert first in [(x, y) for x, y, _ in wayfinding.places(game)]
    app.handle_event(KeyEvent("tab"))
    assert gs.look != first
    app.handle_event(KeyEvent("enter"))
    assert gs.look is None and game.walk_to is not None
    start = (game.player.lx, game.player.ly)
    for _ in range(5):
        app.update()
    assert (game.player.lx, game.player.ly) != start or game.walk_to is None
    app.handle_event(KeyEvent("x"))
    assert game.walk_to is None, "any key stops you"
    assert app.error_count == 0
