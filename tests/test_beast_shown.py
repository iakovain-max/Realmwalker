"""The Beast, shown (Expansion 6 B.9, docs/ADVENTURES.md §5.18, §8.11-8.12): the survivor tells it again in the street
with a crowd round and comes to you; the hunter who stands with you sends a boy with a note in the hunter's hand; the
carcass the beast leaves at your camp lies in the camp's picture; the epilogue's pages have their pictures."""

import pytest

from realmwalker.game import story, townlife
from realmwalker.game.people import npcs_in, prepare_town, town_of
from realmwalker.game.story import beats, cast, forge, stage
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.test_story_hooks import _start_near_a_beast
from tests.test_townlife import at_hour
from tests.worlds import cached_world

pytestmark = pytest.mark.story


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Forgeland", 77, "medium"), tables)


def _tale(made, tables):
    game, t = _start_near_a_beast(made, tables)
    adv = forge.make(game, t)
    d = beats.director(game.world)
    d["card"], d["scheduled"] = None, []
    return game, adv


def _enter(game, s):
    townlife.forget()
    at_hour(game, 11)
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()


def _run(game, until, ticks=300):
    lm = game.local
    s = game.world.settlement_at(game.player.x, game.player.y)
    for _ in range(ticks):
        if until():
            return True
        townlife.tick(game, lm, s)
    return until()


def test_the_survivor_tells_it_in_the_street_and_comes_to_you(made, tables):
    from realmwalker.game.dialogue import Conversation

    game, adv = _tale(made, tables)
    town = game.world.settlements[adv["places"]["town"]["settlement"]]
    prepare_town(game, town)
    witness = cast.person(game.world, adv["cast"]["witness"])
    if witness is None or witness.settlement != town.id:
        pytest.skip("the witness is not of the town")
    next(st for st in story.open_steps(adv) if st["kind"] == "witness")["inside"] = None  # (no situation: C.10)
    _enter(game, town)
    rec = stage.current(game)
    assert rec is not None and rec["id"] == "survivor" and rec["cast"]["survivor"] == witness.id
    gathered = []

    def came():
        g = town_of(game.world, town.id).flags.get("gathering") if stage.current(game) else None
        if g:
            gathered.append(g)
        return game.talk_to == witness.id

    assert _run(game, came), "the survivor comes to you and speaks"
    assert gathered, "a crowd gathered round the telling"
    assert witness.flags.get("opener"), "their first words open the conversation"
    conv = Conversation(game, witness)
    assert any(c.id == "story_witness" for c in conv.menu()), "and you can ask them to tell it"
    game.talk_to = None
    _run(game, lambda: stage.current(game) is None, 80)
    stage.settle(game, game.local)
    game.player.local_key = None
    game.player.x, game.player.y = town.x + 1, town.y
    _enter(game, town)
    assert (stage.current(game) or {}).get("id") != "survivor", "once a tale"


def test_the_hunter_sends_a_note_once_the_den_chapter_begins(made, tables):
    from realmwalker.game import letters

    game, adv = _tale(made, tables)
    home_town = game.world.settlements[adv["places"]["town"]["settlement"]]
    other = next(s for s in sorted(game.world.settlements, key=lambda s: abs(s.x - home_town.x) + abs(s.y - home_town.y))
                 if s.id != home_town.id and s.kind in ("village", "town"))
    prepare_town(game, home_town)
    hunter = next(n for n in npcs_in(game.world, home_town.id) if n.alive)
    adv["cast"]["ally"] = {"npc": hunter.id, "settlement": home_town.id}
    adv["keys"].append("ally")
    adv["chapter"] = next(i for i, ch in enumerate(adv["chapters"]) if ch["id"] == "den")
    _enter(game, other)
    rec = stage.current(game)
    assert rec is not None and rec["id"] == "ally_note", "a boy comes running with the hunter's note"
    assert _run(game, lambda: game.letter is not None), "its page opens"
    page = game.world.politics["letters"][game.letter]
    assert hunter.first_name in page["from"] and "{" not in " ".join(page["lines"])
    assert adv["ally_note"] is not None


def test_the_epilogue_shows_the_places_as_they_now_are(made, tables):
    from realmwalker.ui.gfx import vignette
    from realmwalker.world import marks

    game, adv = _tale(made, tables)
    town = game.world.settlements[adv["places"]["town"]["settlement"]]
    town.status.clear()
    assert vignette.for_epilogue(game, adv, "place")["backdrop"] == "square"
    marks.add(game.world, town, "memorial", 1.0, tables)
    assert "feature/statue" in vignette.for_epilogue(game, adv, "place")["props"], "a statue in its square"
    marks.add(game.world, town, "burned", 1.0, tables)
    assert vignette.for_epilogue(game, adv, "place")["backdrop"] == "burned_street"
    hero = vignette.for_epilogue(game, adv, "hero")
    assert hero["backdrop"] == "road" and hero["figures"]
    for about in ("patron", "ally", "witness", "innocent"):
        assert vignette.for_epilogue(game, adv, about)["backdrop"] in vignette.BACKDROPS


def test_the_carcass_lies_in_the_camps_picture(made, tables, monkeypatch):
    from realmwalker.game import camp
    from realmwalker.game.story import villain
    from realmwalker.ui.gfx import headless, scenes
    from realmwalker.ui.gfx.scene import Sprite
    from realmwalker.ui.widgets import Canvas
    import tcod.console

    game, adv = _tale(made, tables)
    camp.make_camp(game)
    monkeypatch.setattr(villain, "due_move", lambda game, adv, where: "beast_carcass")
    assert story.on_night(game, "camp") and beats.pending(game)["beat"] == "beast_carcass"
    assert story.left_at_camp(game) == "carcass"

    def drawn():
        canvas = Canvas(tcod.console.Console(80, 30, order="F"), gfx=headless())
        scenes.camp(canvas, game, (0, 0, 640, 300), 1.0)
        return {c.name for layer in canvas.layers for c in layer.under if isinstance(c, Sprite)}

    assert "creature/elk" in drawn(), "the dead hind at the camp's edge"
    camp.break_camp(game)
    assert story.left_at_camp(game) is None


def test_the_console_stages_marks_scenes_and_the_showcase(make_app):
    import copy

    from realmwalker.game.state import new_game
    from realmwalker.ui.screens.debug_console import DebugConsole
    from realmwalker.world.generator import WorldOptions

    app = make_app()
    t = app.tables
    game = new_game(copy.deepcopy(cached_world(WorldOptions("Lifeland", 33, "small", history=40), t)), t)
    game.survival = False
    app.start_game(game)
    console = DebugConsole(app)
    console.run("showcase")
    assert sum(1 for s in game.world.settlements if s.status) >= 6, "towns about you carry a sign each"
    s = max((s for s in game.world.settlements if s.kind in ("town", "city")), key=lambda s: s.population)
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    console.run("mark memorial")
    assert "memorial" in s.status and "memorial" in (game.local.meta.get("marks") or {}), "stamped where you stand"
    console.run("mark clear")
    assert not s.status
    console.run("scene plea")
    assert (stage.current(game) or {}).get("id") == "plea"
    assert app.error_count == 0
