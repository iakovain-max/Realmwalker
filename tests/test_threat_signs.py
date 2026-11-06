"""A threat's signs in play (Expansion 6 G.1, docs/ADVENTURES.md §5.1, §5.19): every stage of every kind has its full
set (news, words on the land, barks, a shadow on road meetings, a scene where its effects begin and where people
flee); the land speaks of it only with the world's voice on; its towns' people talk of it; folk met in its reach carry
its mark; its scene plays once a stage in a town it threatens; its marks make prices dear, and the trade screen says
why."""

import copy
from types import SimpleNamespace

import pytest

from realmwalker.game import economy, story, townlife
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.story import signs, stage
from realmwalker.world import marks, threats
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


def _at_stage(game, t, stage_id, applied=True):
    i = next(i for i, s in enumerate(threats.stages(game.tables, t)) if s["id"] == stage_id)
    t["state"] = "active" if i else "stirring"
    t["scheme"].update(stage=i, applied=applied)


def test_every_stage_of_every_kind_has_its_full_set_of_signs(tables):
    scenes = tables.scenes
    for kid, kind in tables.threats["kinds"].items():
        staged = 0
        for i, st in enumerate(kind["stages"]):
            where = f"{kid}/{st['id']}"
            assert len(st["signs"]) >= 4, where
            assert len(st.get("flavour", [])) >= 4, where
            assert len(st.get("barks", [])) >= 5 and max(map(len, st["barks"])) <= 70, where
            assert len(st.get("overlay", [])) >= 4, where
            if st.get("scene"):
                assert st["scene"] in scenes, where
                staged += 1
            if i > 0 and not st.get("doom"):
                assert st.get("roads"), f"{where}: its bands met on the land"
        assert staged >= 2, f"{kid}: a scene where its effects begin and where people flee"
    for sid in ("threat_mourning", "threat_wake", "threat_robbed", "threat_refugees"):
        cues = scenes[sid]["cues"]
        assert cues[-1] == {"cue": "disperse", "always": True}, sid
        assert not {c["cue"] for c in cues} & {"talk", "beat", "fight", "hold"}, f"{sid} asks nothing of you"


def test_the_land_speaks_of_it_only_with_the_worlds_voice_on(made, tables):
    game, t = _start_near_a_beast(made, tables)
    _at_stage(game, t, "spoor")
    hx, hy = threats.home_xy(game.world, t)
    game.player.x, game.player.y = hx, hy
    game.player.local_key = None
    lines = {signs.land_line(game, game.world.rng.child(f"t/{i}")) for i in range(40)}
    spoor = {s[:1].upper() + s[1:] for s in threats.stages(tables, t)[0]["flavour"]}
    assert lines and lines <= spoor | {None} and None not in lines
    said = []
    game.say = lambda text, *a, **k: said.append(text)
    for step in range(0, 400, 7):
        game.player.steps = step
        signs.on_the_land(game)
    assert said, "a line now and then on the walk"
    assert len(said) <= 400 // signs.LAND_GAP + 1, "not at every step"
    said.clear()
    from realmwalker.game.state import VERBOSITY

    game.verbosity = min(VERBOSITY, key=VERBOSITY.get)
    game.renown.flags.pop("land_sign", None)
    for step in range(1000, 1400, 7):
        game.player.steps = step
        signs.on_the_land(game)
    assert not said, "with the least Text detail the land says nothing"
    game.player.x, game.player.y = 0, 0
    if threats.distance(game.world, t, 0, 0) > t["reach"]["r"]:
        assert signs.land_line(game, game.world.rng.child("far")) is None or signs.here(game.world, tables, 0, 0)


def test_its_towns_people_talk_of_it(made, tables):
    game, t = _start_near_a_beast(made, tables)
    _at_stage(game, t, "killings")
    town = game.world.settlements[t["stakes"][0]]
    prepare_town(game, town)
    npc = next(n for n in npcs_in(game.world, town.id) if n.alive)
    barks = {signs._fill(game.world, t, [b], game.world.rng.child("x")) for b in threats.stages(tables, t)[1]["barks"]}
    words = signs.bark(game, npc, 0)
    assert words in barks
    assert signs.bark(game, npc, 1) is None, "only a share of what they say"
    said = [townlife._words_for(game, npc, r) for r in range(0, 300, 3)]
    assert any(w in barks for w in said), "said in passing in the streets"
    t["state"] = "ended"
    assert signs.bark(game, npc, 0) is None, "an ended threat is not talked of so"


def test_folk_met_in_its_reach_carry_its_shadow(made, tables):
    game, t = _start_near_a_beast(made, tables)
    _at_stage(game, t, "hunger")
    hx, hy = threats.home_xy(game.world, t)
    game.player.x, game.player.y = hx, hy
    from realmwalker.game.encounters import make_encounter

    rng = game.world.rng.child("meet")
    group = next(g for g in ("pilgrims", "merchants", "travellers", "bandits", "deserters")
                 if g in tables.creatures.encounters)
    enc = make_encounter(game, group, rng)
    enc.attitude, before = "indifferent", enc.intro
    story.overlay(game, enc, rng)
    shadows = threats.stages(tables, t)[2]["overlay"]
    assert enc.intro.startswith(before) and enc.intro != before
    assert any(enc.intro.endswith(signs._fill(game.world, t, [s], rng)) for s in shadows)
    hostile = make_encounter(game, group, rng)
    hostile.attitude, before = "hostile", hostile.intro
    assert story.overlay(game, hostile, rng).intro == before, "those who mean harm are their own story"
    wolves = make_encounter(game, "wolf_pack", rng)
    wolves.attitude, before = "indifferent", wolves.intro
    assert story.overlay(game, wolves, rng).intro == before, "the words are about people"
    _at_stage(game, t, "hunger", applied=False)
    enc.intro = before = "Travellers."
    assert story.overlay(game, enc, rng).intro == before, "not before the stage's effects have come"


def _enter(game, s):
    townlife.forget()
    at_hour(game, 11)
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()


def test_its_scene_plays_once_a_stage_in_a_town_it_threatens(made, tables):
    game, t = _start_near_a_beast(made, tables)
    _at_stage(game, t, "killings")
    t["adventure"] = "taken"  # (no offer of the tale at the gate: this is the scene alone)
    town = game.world.settlements[t["stakes"][0]]
    prepare_town(game, town)
    _enter(game, town)
    rec = stage.current(game)
    assert rec is not None and rec["id"] == "threat_mourning", rec
    assert rec["words"]["villain"] == threats.villain_name(game.world, t)
    lm = game.local
    for _ in range(400):
        if stage.current(game) is None:
            break
        townlife.tick(game, lm, town)
    assert stage.current(game) is None, "the scene plays to its end by itself"
    assert t["staged"] == ["killings"]
    game.world.politics["director"].pop("scene", None)
    from realmwalker.game.people import town_of

    town_of(game.world, town.id).flags["scene_day"] = -99
    assert not signs.on_enter_town(game, town), "once a stage"
    _at_stage(game, t, "hunger")
    assert signs.on_enter_town(game, town) and stage.current(game)["id"] == "threat_refugees"


def test_its_marks_make_prices_dear_and_the_trade_screen_says_why(tables):
    game = SimpleNamespace(tables=tables, world=SimpleNamespace(wars=[]))
    s = SimpleNamespace(id=3, status={})
    plain = economy.troubles_factor(game, s, "food")
    assert plain == 1.0 and economy.dear_because(game, s) == []
    s.status = {"siege": {"since": 0.0}}
    assert economy.troubles_factor(game, s, "food") == pytest.approx(2.0), "the old numbers stand, now as data"
    assert economy.troubles_factor(game, s, "weapon") == pytest.approx(1.3)
    for mark in ("beast", "bled", "extorted", "emptied", "haunted"):
        s.status = {mark: {"since": 0.0}}
        assert economy.troubles_factor(game, s, "food") > 1.0, mark
        assert economy.dear_because(game, s) == [marks.table(tables)[mark]["label"]]
    s.status = {"memorial": {"since": 0.0}}
    assert economy.troubles_factor(game, s, "food") == 1.0 and economy.dear_because(game, s) == []


def test_the_trade_screen_names_what_makes_it_dear(make_app):
    import tcod.console

    from realmwalker.game.state import new_game
    from realmwalker.ui.screens.trade import MarketScreen

    app = make_app()
    world = copy.deepcopy(cached_world(WorldOptions("Forgeland", 77, "medium"), app.tables))
    game = new_game(world, app.tables)
    game.survival = False
    app.start_game(game)
    s = game.world.settlement_at(game.player.x, game.player.y) or game.world.settlements[0]
    prepare_town(game, s)
    npc = next((n for n in npcs_in(game.world, s.id) if economy.shop_spec(game, n) is not None), None)
    if npc is None:
        pytest.skip("no shop in the starting town")
    marks.add(game.world, s, "bled", 0.0, tables=app.tables, by="the gang")
    app.push(MarketScreen(app, game, npc))
    app.render(tcod.console.Console(140, 46, order="F"))
    text = " ".join(app.last_canvas.words().split())
    assert "dear: robbed roads" in text, text[:400]
