"""The app and its screens, headless: rendering at many sizes, input, error recovery, settings."""

import time

import numpy as np
import pytest
import tcod.console

from realmwalker.config import Settings
from realmwalker.ui import fonts, markup
from realmwalker.ui.input import KeyEvent, MouseEvent
from realmwalker.ui.screens.base import ConfirmBox, MessageBox
from realmwalker.ui.screens.debug_console import DebugConsole
from realmwalker.ui.screens.help import HelpScreen
from realmwalker.ui.screens.player2_test import Player2TestScreen
from realmwalker.ui.screens.settings_screen import SettingsScreen
from realmwalker.ui.screens.title import TitleScreen

SIZES = [(80, 30), (120, 45), (192, 54), (240, 67)]


def render(app, size=(120, 45)):
    con = tcod.console.Console(*size, order="F")
    app.render(con)
    app.update()
    return con


def screen_text(con) -> str:
    return "\n".join("".join(chr(c) for c in con.rgb["ch"][:, y]) for y in range(con.height))


@pytest.mark.parametrize("screen_cls", [TitleScreen, Player2TestScreen, SettingsScreen, HelpScreen, DebugConsole])
@pytest.mark.parametrize("size", SIZES)
def test_every_screen_renders_at_every_size(make_app, screen_cls, size):
    app = make_app()
    app.push(screen_cls(app))
    render(app, size)
    assert app.error_count == 0


def test_title_menu_opens_screens(make_app):
    app = make_app()
    assert isinstance(app.top, TitleScreen)
    app.handle_event(KeyEvent("p"))
    assert isinstance(app.top, Player2TestScreen)
    app.handle_event(KeyEvent("escape"))
    app.handle_event(KeyEvent("s"))
    assert isinstance(app.top, SettingsScreen)
    app.handle_event(KeyEvent("escape"))
    app.handle_event(KeyEvent("q"))
    assert not app.running


def test_disabled_item_explains_itself(make_app):
    app = make_app()
    app.handle_event(KeyEvent("r"))
    assert any("New World" in t.text for t in app.toasts)


def test_mouse_click_on_menu(make_app):
    app = make_app()
    con = render(app)
    text = screen_text(con)
    row = next(y for y, line in enumerate(text.splitlines()) if "Settings" in line and "S" in line)
    col = text.splitlines()[row].index("Settings")
    app.handle_event(MouseEvent("move", col, row))
    render(app)
    app.handle_event(MouseEvent("click", col, row))
    assert isinstance(app.top, SettingsScreen)


def test_tooltip_on_hover(make_app):
    app = make_app()
    con = render(app)
    lines = screen_text(con).splitlines()
    row = next(y for y, line in enumerate(lines) if "Player2 Connection Test" in line)
    app.handle_event(MouseEvent("move", lines[row].index("Player2"), row))
    con = render(app)
    assert "Check the connection" in screen_text(con)


def test_player2_screen_falls_back_when_offline(make_app):
    app = make_app(ai=False)
    screen = Player2TestScreen(app)
    app.push(screen)
    app.handle_event(KeyEvent("g"))
    assert screen.result_source == "fallback" and screen.result["name"]
    assert "Built-in text" in screen_text(render(app))


def test_player2_screen_generates_with_mock(make_app, mock_p2):
    app = make_app(base_url=mock_p2.base_url, ai=True)
    deadline = time.monotonic() + 5
    while not app.ai.usable() and time.monotonic() < deadline:
        time.sleep(0.02)
    screen = Player2TestScreen(app)
    app.push(screen)
    app.handle_event(KeyEvent("g"))
    assert app.ai.wait_idle(5)
    render(app)
    assert screen.result_source == "ai"
    assert "AI text" in screen_text(render(app))


def test_errors_are_caught_and_shown(make_app):
    app = make_app()
    app.push(DebugConsole(app))
    for ch in "test-error":
        app.handle_event(KeyEvent(ch))
    app.handle_event(KeyEvent("enter"))
    assert app.error_count == 1
    assert isinstance(app.top, MessageBox)
    render(app)
    app.handle_event(KeyEvent("enter"))
    assert not isinstance(app.top, MessageBox)


def test_broken_screen_is_closed_after_repeated_render_failures(make_app):
    from realmwalker.ui.screens.base import Screen

    class Broken(Screen):
        def render(self, canvas):
            raise ValueError("boom")

    app = make_app()
    app.push(Broken(app))
    for _ in range(5):
        render(app)
        while isinstance(app.top, MessageBox):
            app.handle_event(KeyEvent("enter"))
    assert not any(isinstance(s, Broken) for s in app.screens)
    assert app.error_count >= 3


def test_font_size_hotkeys_and_settings_persist(make_app, home):
    app = make_app()
    start = app.settings.font_size
    app.handle_event(KeyEvent("=", ctrl=True))
    assert app.settings.font_size == start + 2 and "font" in app.window_requests
    app.handle_event(KeyEvent("0", ctrl=True))
    assert app.settings.font_size == 20
    app.push(SettingsScreen(app))
    for key in ["down", "down", "enter"]:  # "Show dice rolls" -> off
        app.handle_event(KeyEvent(key))
    assert Settings.load(app.paths.settings_file).show_dice is False


def test_settings_reset_asks_first(make_app):
    app = make_app()
    app.settings.show_dice = False
    app.push(SettingsScreen(app))
    app.handle_event(KeyEvent("r"))
    assert isinstance(app.top, ConfirmBox)
    app.handle_event(KeyEvent("y"))
    assert app.settings.show_dice is True


def test_settings_file_tolerates_garbage(home):
    home.mkdir(parents=True, exist_ok=True)
    path = home / "settings.json"
    path.write_text('{"font_size": 999, "verbosity": 7, "show_dice": "yes"', encoding="utf-8")
    s = Settings.load(path)
    assert s == Settings()
    path.write_text('{"font_size": 23, "verbosity": "loud", "show_dice": false}', encoding="utf-8")
    s = Settings.load(path)
    assert s.font_size in (22, 24) and s.verbosity == "normal" and s.show_dice is False


def test_markup_parse_and_wrap():
    spans = markup.parse("a <danger>red <loot>gold</> red</> a <unknown>x")
    assert [t for t, _ in spans] == ["a ", "red ", "gold", " red", " a <unknown>x"]
    lines = markup.wrap("The <danger>bandit's axe</> bites into her thigh.", 12)
    assert [markup_plain(line) for line in lines] == ["The bandit's", "axe bites", "into her", "thigh."]


def markup_plain(line):
    return "".join(t for t, _ in line)


def test_tileset_builds_with_box_and_block_glyphs(home):
    from realmwalker.paths import Paths

    ts = fonts.build_tileset(20, fonts.default_font_path(Paths(home).fonts))
    assert ts.tile_height == 20 and ts.tile_width >= 8
    full = ts.get_tile(ord("█"))[:, :, 3]
    assert full.min() == 255
    horizontal = ts.get_tile(ord("─"))[:, :, 3]
    assert horizontal[:, 0].max() == 255 and horizontal[:, -1].max() == 255  # reaches both edges
    letter = ts.get_tile(ord("A"))[:, :, 3]
    assert 0 < np.count_nonzero(letter) < letter.size


# ---------------------------------------------------------------------------- M1 screens
def start_small_world(app, seed=5):
    from realmwalker.game.state import new_game
    from realmwalker.world.generator import WorldGenerator, WorldOptions

    world = WorldGenerator(WorldOptions("Screenland", seed, "small"), app.tables).generate()
    app.start_game(new_game(world, app.tables))
    return app.top


def game_screens(app, gs):
    from realmwalker.ui.screens.game_menu import ContinueScreen, GameMenu
    from realmwalker.ui.screens.legend import LegendScreen
    from realmwalker.ui.screens.log_screen import LogScreen
    from realmwalker.ui.screens.new_world import NewWorldScreen
    from realmwalker.ui.screens.world_map import WorldMapScreen

    return [WorldMapScreen(app, gs), LegendScreen(app), LogScreen(app, gs.game), GameMenu(app), ContinueScreen(app),
            NewWorldScreen(app)]


@pytest.mark.parametrize("size", SIZES)
def test_game_screens_render_at_every_size(make_app, size):
    from realmwalker.ui.screens.game_screen import GameScreen

    app = make_app()
    gs = start_small_world(app)
    assert isinstance(gs, GameScreen)
    render(app, size)
    gs.enter()
    render(app, size)
    for screen in game_screens(app, gs):
        app.push(screen)
        render(app, size)
        app.pop()
    assert app.error_count == 0


def test_new_world_flow_generates_and_starts(make_app):
    from realmwalker.ui.screens.game_screen import GameScreen

    from realmwalker.ui.screens.creation import CreationScreen

    app = make_app()
    app.handle_event(KeyEvent("n"))
    app.handle_event(KeyEvent("enter"))
    deadline = time.monotonic() + 30
    while not isinstance(app.top, CreationScreen) and time.monotonic() < deadline:
        render(app)
        time.sleep(0.02)
    assert isinstance(app.top, CreationScreen)
    # Accepting every default makes a playable character.
    for _ in range(12):
        if isinstance(app.top, GameScreen):
            break
        app.handle_event(KeyEvent("enter"))
        render(app)
    assert isinstance(app.top, GameScreen)
    assert app.game is not None and app.saves_with_characters()
    assert app.game.leader.ties and app.game.leader.backstory


def test_walk_look_travel_and_continue(make_app):
    from realmwalker.ui.screens.game_screen import GameScreen

    app = make_app()
    gs = start_small_world(app)
    t0 = app.game.world.time
    for key in ["right", "down", "l", "up", "escape", ".", ">", "left", "<"]:
        app.handle_event(KeyEvent(key))
        render(app)
    assert app.game.world.time > t0
    app.handle_event(KeyEvent("t"))
    for key in ["right", "right", "right", "enter"]:
        app.handle_event(KeyEvent(key))
    if isinstance(app.top, ConfirmBox):
        app.handle_event(KeyEvent("y"))
        for _ in range(200):
            render(app)
    assert app.error_count == 0
    app.handle_event(KeyEvent("escape"))
    app.handle_event(KeyEvent("t"))  # save and return to the title
    assert app.game is None
    app.handle_event(KeyEvent("c"))
    assert isinstance(app.top, GameScreen) and app.game is not None


def test_mouse_hover_describes_the_map(make_app):
    app = make_app()
    gs = start_small_world(app)
    con = render(app)
    p = app.game.player
    vx, vy, mx0, my0, ox, oy = gs.view
    sx, sy = p.x - mx0 + vx + ox, p.y - my0 + vy + oy
    app.handle_event(MouseEvent("move", sx, sy))
    assert "You are here" in screen_text(render(app))


# ---------------------------------------------------------------------------- M3 screens
def fight_through_screens(app, group, seed, keys_rng, size=(120, 45), max_steps=800):
    """Meet a group on the road and play the fight out with the screens' own sensible keys."""
    from realmwalker.core.rng import RNG
    from realmwalker.game.encounters import make_encounter

    game = app.game
    game.encounter = make_encounter(game, group, RNG(seed, "ui-enc"))
    seen = set()
    for step in range(max_steps):
        render(app, size)
        name = type(app.top).__name__
        seen.add(name)
        if name == "TitleScreen" or (name == "GameScreen" and not game.busy and step > 2):
            break
        app.handle_event(keys_rng.choice(app.top.autoplay_keys()))
    else:
        raise AssertionError(f"fight did not end; stuck on {type(app.top).__name__}")
    return seen


@pytest.mark.parametrize("size", SIZES)
def test_battle_screens_render_at_every_size(make_app, size):
    import random

    app = make_app()
    start_small_world(app)
    seen = fight_through_screens(app, "bandits", 3, random.Random(size[0]), size)
    assert "EncounterScreen" in seen
    assert app.error_count == 0


def test_many_fights_through_the_screens(make_app):
    import random

    app = make_app()
    start_small_world(app)
    rng = random.Random(7)
    groups = sorted(app.tables.creatures.encounters)
    screens = set()
    for i, group in enumerate(groups):
        if app.game is None:
            start_small_world(app, seed=i)
        for c in app.game.party:
            c.hp = c.max_hp
        screens |= fight_through_screens(app, group, i, rng)
        assert app.error_count == 0, group
    assert {"EncounterScreen", "BattleScreen", "AftermathScreen"} <= screens


def test_battle_keys_attack_and_targets(make_app):
    from realmwalker.game import fight
    from realmwalker.ui.screens.battle import BattleScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    from realmwalker.core.rng import RNG
    from realmwalker.game.encounters import make_encounter

    game.encounter = make_encounter(game, "wolf_pack", RNG(2, "k"))
    fight.encounter_fight(game, ambush=False)
    render(app)
    screen = app.top
    assert isinstance(screen, BattleScreen)
    for _ in range(50):
        if screen.actor() is not None:
            break
        render(app)
    assert screen.actor() is not None
    log_len = len(game.battle.log)
    app.handle_event(KeyEvent("a"))
    assert screen.mode == "choose"
    app.handle_event(KeyEvent("enter"))
    assert screen.mode == "target"
    app.handle_event(KeyEvent("1"))
    assert len(game.battle.log) > log_len
    assert screen.mode in ("menu", "over")
    app.handle_event(KeyEvent("?"))  # help from the battle
    assert app.error_count == 0


def test_rest_screen(make_app):
    app = make_app()
    start_small_world(app)
    app.game.leader.hp = 1
    app.handle_event(KeyEvent("r"))
    render(app)
    app.handle_event(KeyEvent("l"))
    for _ in range(3):
        render(app)
    assert app.game.leader.hp > 1  # a long rest in town is never interrupted
    assert app.error_count == 0


def test_death_returns_to_title_and_frees_the_world(make_app):
    from realmwalker.game.save import list_saves

    app = make_app()
    start_small_world(app)
    game = app.game
    game.over = {"cause": "killed in a test", "place": "here"}
    render(app)
    assert type(app.top).__name__ == "DeathScreen"
    assert "killed in a test" in screen_text(render(app))
    app.handle_event(KeyEvent("enter"))
    assert app.game is None and type(app.top).__name__ == "TitleScreen"
    assert all(s.character is None for s in list_saves(app.paths.saves))


# ---------------------------------------------------------------------------- M4 screens
@pytest.mark.parametrize("size", SIZES)
def test_health_screen_and_weather_map_render(make_app, size):
    from realmwalker.ui.screens.health import HealthScreen
    from realmwalker.ui.screens.world_map import WorldMapScreen

    app = make_app()
    gs = start_small_world(app)
    c = app.game.leader
    c.hunger, c.thirst, c.body_heat, c.wet, c.exhaustion = 70, 90, -65, 80, 2
    render(app, size)
    assert "hypothermic" in screen_text(render(app, size))
    app.push(HealthScreen(app, app.game))
    text = screen_text(render(app, size))
    assert "Exhaustion 2" in text and "Needs" in text
    app.pop()
    wm = WorldMapScreen(app, gs)
    app.push(wm)
    app.handle_event(KeyEvent("w"))
    assert wm.show_weather
    render(app, size)
    assert app.error_count == 0


def test_inventory_eats_and_drinks(make_app):
    from realmwalker.ui.screens.sheets import InventoryScreen

    app = make_app()
    start_small_world(app)
    c = app.game.leader
    c.hunger, c.thirst = 60, 60
    inv = InventoryScreen(app, app.game)
    app.push(inv)
    items = inv.visible_items()
    inv.selected = next(i for i, it in enumerate(items) if it.def_id == "rations")
    assert inv.action_name(inv.current()) == "Eat"
    app.handle_event(KeyEvent("enter"))
    assert c.hunger < 60
    items = inv.visible_items()
    inv.selected = next(i for i, it in enumerate(items) if it.def_id == "waterskin")
    assert inv.action_name(inv.current()) == "Drink"
    app.handle_event(KeyEvent("enter"))
    assert c.thirst < 60
    render(app)
    assert app.error_count == 0
