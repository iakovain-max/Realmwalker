"""After dark (after v1), three things the design asked for: sneaking on a close-up map (Stealth against Perception),
town gates that shut at night, and animals that can be stolen from a camp in the wild."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import encounters, events, fight
from realmwalker.game.encounters import LocalActor
from realmwalker.game.state import new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Nightfall", 29, "medium"), tables)


@pytest.fixture
def game(world, tables):
    g = new_game(copy.deepcopy(world), tables, CharacterBuilder(tables, RNG(3, "hero")).build())
    g.survival = False
    return g


def at_hour(game, hour: float) -> None:
    """Move the clock forward to the next time it is this hour."""
    now = game.moment.fractional_hour
    game.world.time += int(round(((hour - now) % 24) * 60))


# ---------------------------------------------------------------------------- sneaking
def band(game, tables, group="bandits"):
    first = tables.creatures.encounters[group]["members"][0][0]
    return LocalActor(99, group, 0, 0, [spawn(tables, first, RNG(1, "band"), 1)])


def test_sneaking_is_stealth_against_perception(game, tables):
    game.player.local_key = None
    game.enter_local()
    a = band(game, tables)
    pp = encounters.passive_perception(game, a)
    game.sneaking, game.sneak_roll = True, pp + 3
    assert encounters.notice_chance(game, a, 4) == 0.0  # 2 closer than 6 tiles: still not enough
    assert encounters.notice_chance(game, a, 1) == 1.0  # right next to them: +5
    game.sneak_roll = pp - 1
    assert encounters.notice_chance(game, a, 7) == 1.0
    game.sneaking = False
    assert 0.0 < encounters.notice_chance(game, a, 7) < 1.0  # walking openly, it is luck and light


def test_z_starts_and_stops_creeping_only_on_foot(game):
    assert "close view" in game.toggle_sneak() and not game.sneaking
    game.player.local_key = None
    game.enter_local()
    said = game.toggle_sneak()
    assert game.sneaking and "Stealth" in said and game.sneak_roll > 0
    game.toggle_sneak()
    assert not game.sneaking
    game.toggle_sneak()
    game.leave_local()
    assert not game.sneaking


def test_creeping_takes_longer(game):
    game.player.local_key = None
    lm = game.enter_local()
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    p = game.player

    def step_time() -> int:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if lm.in_bounds(p.lx + dx, p.ly + dy) and walk[p.lx + dx, p.ly + dy]:
                before = game.world.time * 60 + p.seconds
                game.move(dx, dy)
                return game.world.time * 60 + p.seconds - before
        raise AssertionError("nowhere to step")

    openly = step_time()
    game.sneaking = True
    assert step_time() >= 2 * openly - 1


def test_the_watch_does_not_see_what_it_cannot_beat(game, tables):
    from realmwalker.game import law
    from realmwalker.game.people import npcs_in
    from realmwalker.world import factions as fx

    s = next(s for s in game.world.settlements if s.kind == "town" and fx.owner_of(game.world, s) is not None)
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    seen = law.witnesses_here(game, radius=60)
    if not seen:
        pytest.skip("nobody in sight in this town")
    game.sneaking, game.sneak_roll = True, 40
    assert law.witnesses_here(game, radius=60) == []
    game.sneak_roll = 0
    assert law.witnesses_here(game, radius=60) == seen
    assert npcs_in  # imported for the town to be populated


# ---------------------------------------------------------------------------- the gates at night
def walled_town(game):
    s = next(s for s in game.world.settlements if s.walled and s.kind in ("town", "city"))
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    return s


def test_the_gates_shut_at_night_and_open_at_dawn(game):
    s = walled_town(game)
    at_hour(game, 12)
    assert not game.gate_shut()
    at_hour(game, 23)
    assert game.gate_shut()
    game.let_in = (s.id, game._night_of())
    assert not game.gate_shut()  # let in tonight
    at_hour(game, 2)
    assert not game.gate_shut()  # the same night, after midnight
    game.let_in = None
    assert game.gate_shut()
    game.world.time += game.minutes_to_dawn() + 60
    assert not game.gate_shut()


def test_villages_have_no_gate_to_shut(game):
    v = next(s for s in game.world.settlements if s.kind in ("village", "hamlet"))
    game.player.x, game.player.y = v.x, v.y
    at_hour(game, 23)
    assert not game.gate_shut()


def option(game, start: str) -> int:
    """The shut gate's option that begins with these words (they are not always in the same place)."""
    return next(i for i, o in enumerate(game.tables.travel_events["shut_gate"]["options"]) if o["label"].startswith(start))


def test_paying_the_warden_lets_you_in(game):
    walled_town(game)
    at_hour(game, 23)
    game.leader.money = 500
    ev = events.make_event(game, "shut_gate")
    labels = [label for label, *_ in events.options(game, ev)]
    assert len(labels) == 5 and "Sleep under the walls until dawn" in labels
    assert any("grappling hook" in label for label in labels)
    events.choose(game, ev, option(game, "Knock at the postern"))
    assert game.leader.money == 480 and not game.gate_shut()
    assert any("> to go in" in m for m in ev.result)


def test_sleeping_under_the_walls_waits_for_dawn(game):
    walled_town(game)
    at_hour(game, 23)
    ev = events.make_event(game, "shut_gate")
    events.choose(game, ev, option(game, "Sleep under the walls"))
    assert game.moment.part_of_day(game.latitude) == "dawn"
    assert not game.gate_shut()


def test_a_fall_from_the_wall_hurts_but_does_not_kill(game, monkeypatch):
    from realmwalker.core import dice

    walled_town(game)
    at_hour(game, 23)
    game.leader.hp = 2

    class Low:
        natural = 1
        total = 1

    monkeypatch.setattr(dice, "d20", lambda *a, **k: Low())
    ev = events.make_event(game, "shut_gate")
    events.choose(game, ev, option(game, "Climb the wall"))
    assert game.leader.hp == 1 and game.gate_shut()


def test_pressing_enter_at_a_shut_gate_meets_the_warden(make_app, world):
    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.event import EventScreen

    app = make_app()
    game = new_game(copy.deepcopy(world), app.tables, CharacterBuilder(app.tables, RNG(3, "hero")).build())
    app.start_game(game)
    walled_town(game)
    at_hour(game, 23)
    app.handle_event(KeyEvent(">"))
    app.update()
    assert isinstance(app.top, EventScreen) and not game.in_local
    assert app.error_count == 0


def test_the_gate_never_turns_up_on_the_road(game, tables):
    spec = tables.travel_events["shut_gate"]
    p = game.player
    for x, y in ((p.x, p.y), (p.x + 1, p.y), (p.x, p.y + 1)):
        assert not events.fits(spec, game, x, y, True)


# ---------------------------------------------------------------------------- animals in the night
def test_a_camp_without_a_watch_can_lose_a_mule(game, monkeypatch):
    game.leader.animals = [{"kind": "mule", "name": "Bess", "unfed": 0, "bought": 0}]
    monkeypatch.setattr(fight, "RUSTLING_CHANCE", 1.0)
    notes = fight._rustlers(game, fire=False)
    assert not game.leader.animals and "Bess the mule is gone" in notes[0]


def test_someone_on_watch_sees_the_thieves_off(game, monkeypatch):
    from realmwalker.game import companions

    game.leader.animals = [{"kind": "mule", "name": "Bess", "unfed": 0, "bought": 0}]
    monkeypatch.setattr(fight, "RUSTLING_CHANCE", 1.0)
    monkeypatch.setattr(companions, "watching", lambda g: True)
    notes = fight._rustlers(game, fire=True)
    assert game.leader.animals and "on watch" in notes[0]


def test_the_wardens_let_back_in_someone_they_saw_go_out(game):
    walled_town(game)
    at_hour(game, 12)
    game.enter_local()
    at_hour(game, 23)
    game.leave_local()
    assert not game.gate_shut()
