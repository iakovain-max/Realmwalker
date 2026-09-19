"""The AI side of townsfolk: what is asked, how replies are applied, and the fallbacks."""

import copy
import time

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.people_ai import (allowed_outcomes, apply_dialogue, apply_settlement, dialogue_variables,
                                        settlement_variables)
from realmwalker.game.state import new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.ui.input import KeyEvent
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Talkland", 8, "medium"), tables).generate()


def hero(tables):
    b = CharacterBuilder(tables, RNG(1, "hero"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background("soldier")
    return b.build()


@pytest.fixture
def game(tables, world):
    return new_game(copy.deepcopy(world), tables, hero(tables))


def a_town(game, kind="town"):
    s = next(s for s in game.world.settlements if s.kind == kind)
    town = prepare_town(game, s)
    return s, town


def test_the_settlement_request_lists_its_notables(game):
    s, town = a_town(game)
    v = settlement_variables(game, s, town)
    notables = [n for n in npcs_in(game.world, s.id) if n.notable]
    assert notables and all(f"id {n.id}: {n.name}" in v["people"] for n in notables)
    assert v["name"] == s.name and v["inn_count"] >= 1


def test_ai_words_replace_only_what_has_not_been_seen(game):
    s, town = a_town(game)
    notables = [n for n in npcs_in(game.world, s.id) if n.notable]
    seen, unseen = notables[0], notables[1]
    seen.profile_seen = True
    old_seen = dict(seen.profile)
    data = {"description": "A test town under grey rain.", "inn_names": ["The Test Crow"],
            "people": [{"id": n.id, "appearance": f"AI looks {n.id}", "personality": "AI mind", "backstory": "AI past.",
                        "secret": "AI secret", "want": "AI want"} for n in notables] + [{"id": 999999, "appearance": "x",
                                                                                          "personality": "x", "backstory": "x",
                                                                                          "secret": "x", "want": "x"}]}
    updated = apply_settlement(game, s, town, data)
    assert updated == len(notables) - 1
    assert seen.profile == old_seen and seen.profile_source == "fallback"
    assert unseen.profile["appearance"] == f"AI looks {unseen.id}" and unseen.profile_source == "ai"
    assert town.description == "A test town under grey rain." and town.description_source == "ai"
    assert "The Test Crow" in town.names.values()
    town.seen = True
    apply_settlement(game, s, town, {"description": "Something else."})
    assert town.description == "A test town under grey rain."


def test_the_dialogue_request_says_what_they_can_offer(game):
    s, _ = a_town(game)
    people = npcs_in(game.world, s.id)
    smith = next(n for n in people if n.job == "smith")
    priest = next(n for n in people if n.job == "priest")
    v = dialogue_variables(game, smith)
    assert smith.name in v["npc"] and "smith" in v["offers"]
    assert "price_down" in allowed_outcomes(game, smith)
    assert "price_down" not in allowed_outcomes(game, priest)
    assert "price_down" not in v["outcomes"] or "price_down" in allowed_outcomes(game, smith)


def test_ai_options_are_kept_to_the_whitelist(game):
    s, _ = a_town(game)
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    priest = next(n for n in npcs_in(game.world, s.id) if n.job == "priest")
    conv = Conversation(game, priest, defer_greeting=True)
    data = {"line": "\"Peace be on you, stranger.\"", "options": [
        {"text": "[Insight] She is hiding something about the bell", "skill": "insight", "difficulty": "medium",
         "success": {"outcome": "price_down", "line": "\"Cheaper candles for you.\""},
         "failure": {"outcome": "disposition_down", "line": "\"How dare you.\""}},
        {"text": "Offer to pray with her", "skill": "religion", "difficulty": "easy",
         "success": {"outcome": "disposition_up", "line": "\"Kneel, then.\""},
         "failure": {"outcome": "none", "line": "\"Not now.\""}},
    ]}
    assert apply_dialogue(conv, data) == 2
    assert conv.greeted and any("Peace be on you" in t for _, t in conv.lines)
    first = conv.special[0]
    assert first["text"] == "[Insight] She is hiding something about the bell"
    assert first["success"]["outcome"] == "none", "a priest cannot change prices"
    assert priest.flags["ai_day"] == game.moment.total_days
    for c in [c for c in conv.menu() if c.id == "special"]:
        conv.choose(c)


def _usable(app):
    for _ in range(100):
        app.update()
        if app.ai.usable():
            return True
        time.sleep(0.05)
    return False


def test_a_conversation_with_the_ai(make_app, mock_p2):
    from test_app_ui import render, start_small_world

    from realmwalker.ui.screens.dialogue import DialogueScreen

    app = make_app(base_url=mock_p2.base_url, ai=True)
    start_small_world(app)
    assert _usable(app)
    game = app.game
    game.enter_local()
    s = game.world.settlement_at(game.player.x, game.player.y)
    npc = next(n for n in npcs_in(game.world, s.id) if n.notable)
    game.talk_to = npc.id
    render(app)
    screen = app.top
    assert isinstance(screen, DialogueScreen) and screen.conv.pending_ai
    app.ai.wait_idle(10)
    render(app)
    assert not screen.conv.pending_ai and screen.conv.greeted
    assert any(t.startswith("<ai>") for _, t in screen.conv.lines)
    assert any(o.get("source") == "ai" for o in screen.conv.special)
    for i in range(1, 6):
        app.handle_event(KeyEvent(str(i)))
        render(app)
    assert app.error_count == 0


def test_a_slow_ai_falls_back_to_built_in_lines(make_app, mock_p2):
    from test_app_ui import render, start_small_world

    from realmwalker.ui.screens.dialogue import DialogueScreen

    app = make_app(base_url=mock_p2.base_url, ai=True)
    start_small_world(app)
    assert _usable(app)
    game = app.game
    game.enter_local()
    s = game.world.settlement_at(game.player.x, game.player.y)
    npc = next(n for n in npcs_in(game.world, s.id) if n.notable)
    game.talk_to = npc.id
    render(app)
    screen = app.top
    assert isinstance(screen, DialogueScreen)
    screen.asked_at -= 100  # pretend the AI has kept us waiting too long
    render(app)
    assert screen.conv.greeted and not screen.conv.pending_ai
    assert not any(o.get("source") == "ai" for o in screen.conv.special)
    app.ai.wait_idle(10)
    render(app)
    assert not any(o.get("source") == "ai" for o in screen.conv.special), "a late reply is ignored"


def test_approaching_a_town_asks_for_its_words(make_app, mock_p2):
    from test_app_ui import render, start_small_world

    app = make_app(base_url=mock_p2.base_url, ai=True)
    start_small_world(app)
    assert _usable(app)
    game = app.game
    before = mock_p2.chat_calls
    render(app)
    app.ai.wait_idle(10)
    render(app)
    s = game.world.settlement_at(game.player.x, game.player.y)
    assert mock_p2.chat_calls > before
    assert npcs_in(game.world, s.id), "the town was made ready ahead of arrival"
    assert app.error_count == 0
