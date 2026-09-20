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


@pytest.mark.parametrize("size", SIZES)
def test_camp_event_and_trade_screens(make_app, size):
    import random

    from realmwalker.game.events import make_event
    from realmwalker.ui.screens.camp import CampScreen
    from realmwalker.ui.screens.event import EventScreen, TradeScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    app.handle_event(KeyEvent("r"))
    assert isinstance(app.top, CampScreen)
    text = screen_text(render(app, size))
    assert "Light a fire" in text or "Put out the fire" in text
    for key in ("e", "s", "w", "escape"):
        app.handle_event(KeyEvent(key))
        render(app, size)
    game.event = make_event(game, "pedlar")
    render(app, size)
    assert isinstance(app.top, EventScreen)
    app.handle_event(KeyEvent("1"))
    assert isinstance(app.top, TradeScreen)
    money = game.leader.money
    app.handle_event(KeyEvent("enter"))
    render(app, size)
    assert game.leader.money < money
    app.handle_event(KeyEvent("escape"))
    app.handle_event(KeyEvent("3"))
    render(app, size)
    app.handle_event(KeyEvent("enter"))
    render(app, size)
    assert game.event is None and not isinstance(app.top, EventScreen)
    rng = random.Random(size[0])
    for eid in sorted(app.tables.travel_events):
        game.event = make_event(game, eid)
        for _ in range(12):
            render(app, size)
            if app.game is None or not (game.busy or not isinstance(app.top, type(app.top))):
                break
            app.handle_event(rng.choice(app.top.autoplay_keys()))
    assert app.error_count == 0


@pytest.mark.parametrize("with_ai", [False, True])
def test_travel_days_are_written_up(make_app, mock_p2, with_ai):
    app = make_app(base_url=mock_p2.base_url, ai=True) if with_ai else make_app()
    start_small_world(app)
    game = app.game
    if with_ai:
        for _ in range(100):
            app.update()
            if app.ai.usable():
                break
            import time

            time.sleep(0.05)
        assert app.ai.usable()
    before = len(game.log.messages)
    game.narration.append({"miles": 18, "lands": ["grassland", "hills"], "weather": "rain", "road": 4, "off_road": 2})
    render(app)
    if with_ai:
        app.ai.wait_idle(10)
        app.update()
    flavor = [m for m in game.log.messages[before:] if m.category == "flavor"]
    assert flavor and "{" not in flavor[-1].text
    assert not game.narration


# ---------------------------------------------------------------------------- M5 screens
@pytest.mark.parametrize("size", SIZES)
def test_talking_to_townsfolk(make_app, size):
    import random

    from realmwalker.game.people import npcs_in
    from realmwalker.ui.screens.dialogue import DialogueScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    game.enter_local()
    s = game.world.settlement_at(game.player.x, game.player.y)
    rng = random.Random(size[0])
    for npc in npcs_in(game.world, s.id)[:6]:
        game.talk_to = npc.id
        render(app, size)
        assert isinstance(app.top, DialogueScreen)
        for _ in range(12):
            if not isinstance(app.top, DialogueScreen):
                break
            app.handle_event(rng.choice(app.top.autoplay_keys()))
            render(app, size)
        while app.top is not None and not type(app.top).__name__ == "GameScreen" and not game.busy:
            app.handle_event(KeyEvent("escape"))
            render(app, size)
        if game.busy:
            break
    assert app.error_count == 0


@pytest.mark.parametrize("size", SIZES)
def test_the_market_window(make_app, size):
    from realmwalker.game import economy
    from realmwalker.game.people import npcs_in
    from realmwalker.ui.screens.trade import MarketScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    game.enter_local()
    s = game.world.settlement_at(game.player.x, game.player.y)
    npc = next((n for n in npcs_in(game.world, s.id) if economy.shop_kind(game, n)), None)
    if npc is None:
        pytest.skip("nobody here trades")
    game.leader.money = 100000
    app.push(MarketScreen(app, game, npc))
    render(app, size)
    money = game.leader.money
    app.handle_event(KeyEvent("enter"))
    render(app, size)
    assert game.leader.money < money
    for key in ("tab", "down", "enter", "h", "pagedown", "tab", "up", "escape"):
        app.handle_event(KeyEvent(key))
        render(app, size)
    assert app.error_count == 0


@pytest.mark.parametrize("size", SIZES)
def test_the_services_window(make_app, size):
    from realmwalker.game.people import npcs_in, prepare_town
    from realmwalker.ui.screens.services import ServicesScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    game.leader.money = 100000
    for s in game.world.settlements:
        prepare_town(game, s)
        npc = next((n for n in npcs_in(game.world, s.id) if n.job in ("innkeeper", "stablemaster")), None)
        if npc is not None:
            break
    else:
        pytest.skip("no inn or stable")
    app.push(ServicesScreen(app, game, npc))
    render(app, size)
    for key in ("3", "1", "escape", "4", "1", "escape"):
        app.handle_event(KeyEvent(key))
        render(app, size)
    assert app.error_count == 0


@pytest.mark.parametrize("size", SIZES)
def test_the_factions_screen_and_realm_map(make_app, size):
    from realmwalker.ui.screens.factions import FactionsScreen
    from realmwalker.ui.screens.world_map import WorldMapScreen

    app = make_app()
    gs = start_small_world(app)
    game = app.game
    for f in game.world.factions.values():
        game.renown.known.add(f.id)
    game.renown.bounties[next(iter(game.world.factions))] = 1500
    app.handle_event(KeyEvent("f"))
    assert isinstance(app.top, FactionsScreen)
    con = render(app, size)
    assert "Factions" in screen_text(con)
    for key in ("down", "down", "end", "pagedown", "pageup", "home", "up"):
        app.handle_event(KeyEvent(key))
        render(app, size)
    app.handle_event(KeyEvent("escape"))
    app.push(WorldMapScreen(app, gs))
    app.handle_event(KeyEvent("p"))
    render(app, size)
    app.handle_event(KeyEvent("z"))
    render(app, size)
    assert app.error_count == 0


@pytest.mark.parametrize("size", SIZES)
def test_the_arrest_and_sentence_windows(make_app, size):
    from realmwalker.game import law
    from realmwalker.game.people import npcs_in
    from realmwalker.ui.screens.law import ArrestScreen, SentenceScreen
    from realmwalker.world import factions as fx

    app = make_app()
    start_small_world(app)
    game = app.game
    game.survival = False
    s = next(s for s in game.world.settlements if s.kind in ("town", "city") and fx.owner_of(game.world, s))
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    guard = next(n for n in npcs_in(game.world, s.id) if n.job == "guard")
    law.commit(game, "assault", witnesses=[guard])
    render(app, size)
    assert isinstance(app.top, ArrestScreen)
    app.handle_event(KeyEvent("b"))
    render(app, size)
    app.handle_event(KeyEvent("q"))
    render(app, size)
    assert isinstance(app.top, SentenceScreen)
    for _ in range(6):
        app.handle_event(KeyEvent("enter"))
        render(app, size)
    assert game.sentence is None or game.over is not None
    assert app.error_count == 0


@pytest.mark.parametrize("size", SIZES)
def test_the_chronicle_and_notice_board_windows(make_app, size):
    from realmwalker.game import news
    from realmwalker.ui.screens.chronicle import ChronicleScreen
    from realmwalker.ui.screens.notices import NoticeBoardScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    s = next(s for s in game.world.settlements if s.kind in ("town", "city"))
    news.add(game.world, "a great battle was fought", s.x, s.y, kind="battle", importance=4)
    news.hear(game, count=5, x=s.x, y=s.y)
    app.handle_event(KeyEvent("n"))
    assert isinstance(app.top, ChronicleScreen)
    for key in ("pagedown", "tab", "pagedown", "tab", "down", "1"):
        render(app, size)
        app.handle_event(KeyEvent(key))
    render(app, size)
    app.handle_event(KeyEvent("escape"))
    app.push(NoticeBoardScreen(app, game, s))
    render(app, size)
    app.handle_event(KeyEvent("pagedown"))
    render(app, size)
    assert app.error_count == 0


@pytest.mark.parametrize("size", SIZES)
def test_the_level_up_window(make_app, size):
    from realmwalker.core.rng import RNG
    from realmwalker.rules import progression
    from realmwalker.ui.screens.levelup import LevelUpScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    progression.award_xp(game.leader, 14000, game.tables, RNG(1))
    assert game.leader.pending
    render(app, size)
    assert isinstance(app.top, LevelUpScreen), "a level-up opens the choices"
    for key in ("down", "enter", "pagedown", "enter", "escape"):
        app.handle_event(KeyEvent(key))
        render(app, size)
    app.handle_event(KeyEvent("c"))
    render(app, size)
    app.handle_event(KeyEvent("l"))
    render(app, size)
    app.handle_event(KeyEvent("a"))
    render(app, size)
    assert not game.leader.pending
    assert app.error_count == 0


@pytest.mark.parametrize("size", SIZES)
def test_the_party_window(make_app, size):
    from realmwalker.game import companions
    from realmwalker.game.people import npcs_in
    from realmwalker.ui.screens.party import PartyScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    game.leader.money = 100000
    for s in game.world.settlements:
        if s.kind not in ("town", "city"):
            continue
        game.player.local_key = None
        game.player.x, game.player.y = s.x, s.y
        game.enter_local()
        folk = [n for n in npcs_in(game.world, s.id) if n.flags.get("recruit")]
        if folk:
            folk[0].met, folk[0].disposition = True, 20
            companions.hire(game, folk[0])
            break
    app.handle_event(KeyEvent("p"))
    assert isinstance(app.top, PartyScreen)
    for key in ("down", "t", "o", "o", "w", "up", "down", "pagedown"):
        render(app, size)
        app.handle_event(KeyEvent(key))
    render(app, size)
    app.handle_event(KeyEvent("i"))
    render(app, size)
    app.handle_event(KeyEvent("tab"))
    render(app, size)
    assert app.error_count == 0


@pytest.mark.parametrize("size", SIZES)
def test_the_journal_window(make_app, size):
    from realmwalker.game import quests
    from realmwalker.game.people import npcs_in
    from realmwalker.ui.screens.journal import JournalScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    taken = 0
    for s in game.world.settlements:
        if s.kind not in ("town", "city"):
            continue
        game.player.local_key = None
        game.player.x, game.player.y = s.x, s.y
        game.enter_local()
        for npc in npcs_in(game.world, s.id):
            q = quests.offer_for(game, npc)
            if q is not None:
                quests.accept(game, q)
                taken += 1
        if taken >= 3:
            break
    assert taken, "nobody in this world had any work"
    app.handle_event(KeyEvent("j"))
    assert isinstance(app.top, JournalScreen)
    for key in ("down", "down", "pagedown", "up"):
        render(app, size)
        app.handle_event(KeyEvent(key))
    render(app, size)
    app.handle_event(KeyEvent("a"))  # give one up: it asks first
    assert isinstance(app.top, ConfirmBox)
    render(app, size)
    app.handle_event(KeyEvent("y"))
    render(app, size)
    assert any(q["state"] == "abandoned" for q in game.quests)
    app.handle_event(KeyEvent("escape"))
    assert app.error_count == 0


def test_taking_a_bounty_from_the_board(make_app):
    from realmwalker.game import quests
    from realmwalker.ui.screens.notices import NoticeBoardScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    for s in game.world.settlements:
        game.player.x, game.player.y = s.x, s.y
        screen = NoticeBoardScreen(app, game, s)
        if screen.bounties:
            break
    else:
        pytest.skip("no bounties posted anywhere in this world")
    app.push(screen)
    render(app)
    app.handle_event(KeyEvent("1"))
    render(app)
    assert any(q["template"] == "bounty" and q["state"] == "active" for q in game.quests)
    app.handle_event(KeyEvent("escape"))
    assert app.error_count == 0


@pytest.mark.parametrize("size", SIZES)
def test_the_death_screen_and_the_world_after(make_app, size):
    """M9: the obituary at every size, and the 'while you were away' page for the next character."""
    from realmwalker.game import death, interlude
    from realmwalker.ui.screens.interlude import InterludeScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    game.leader.deeds.append("cleared the barrow at Ashfell")
    game.leader.kills["bandit"] = 5
    game.renown.fame = 12
    game.over = {"cause": "killed by a dragon, of all things", "place": "the mountains"}
    render(app, size)
    assert type(app.top).__name__ == "DeathScreen"
    text = screen_text(render(app, size))
    assert "dragon" in text and "bandits" in text
    app.handle_event(KeyEvent("down"))
    render(app, size)
    assert death.fallen(game.world)[-1]["name"] == game.leader.name
    # The next character is told what changed while nobody was watching.
    summary = interlude.pass_the_years(game.world, app.tables, days=90)
    app.push(InterludeScreen(app, game, summary))
    text = screen_text(render(app, size))
    assert "months" in text or "days" in text
    app.handle_event(KeyEvent("pagedown"))
    render(app, size)
    app.handle_event(KeyEvent("enter"))
    render(app, size)
    assert app.error_count == 0


def test_a_job_from_the_first_word_to_the_pay(make_app):
    """Through the screens: ask for work, take it, see it in the journal, finish it, get paid."""
    from realmwalker.game import quests
    from realmwalker.game.people import npcs_in
    from realmwalker.ui.screens.dialogue import DialogueScreen
    from realmwalker.ui.screens.journal import JournalScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    town = next(s for s in game.world.settlements if s.kind in ("town", "city"))
    game.player.x, game.player.y = town.x, town.y
    game.enter_local()
    offer = npc = None
    for person in npcs_in(game.world, town.id):
        offer = quests.offer_for(game, person)
        if offer is not None:
            npc = person
            break
    assert offer is not None, "nobody in this town has work"

    game.talk_to = npc.id
    render(app)
    assert isinstance(app.top, DialogueScreen)
    screen = app.top
    menu = screen.conv.menu()
    work = next(i for i, c in enumerate(menu) if c.id == "work")
    screen.choose(work)
    render(app)
    assert screen.conv.mode == "quest_offer"
    yes = next(i for i, c in enumerate(screen.conv.menu()) if c.id == "work_accept")
    screen.choose(yes)
    render(app)
    assert offer in game.quests and offer["state"] == "active"
    app.handle_event(KeyEvent("escape"))

    app.handle_event(KeyEvent("j"))
    assert isinstance(app.top, JournalScreen)
    text = screen_text(render(app))
    assert quests.title(game, offer).split()[0] in text
    app.handle_event(KeyEvent("escape"))

    # The work is done (however it was done); now go back and say so.
    quests.mark_done(game, offer)
    if offer["template"] in ("retrieve", "steal"):
        from realmwalker.rules.inventory import add_existing

        add_existing(game.leader, game.tables.items, quests.quest_item(game, offer))
    if offer["template"] == "collect_debt":
        offer["target"]["collected"] = 0
    money = game.leader.money
    game.talk_to = npc.id
    render(app)
    screen = app.top
    assert isinstance(screen, DialogueScreen)
    turn_in = next((i for i, c in enumerate(screen.conv.menu()) if c.id == "quest_turn_in"), None)
    if turn_in is None:  # some work is reported to somebody else (a letter, a crate, a companion)
        assert offer["template"] in ("deliver", "smuggle", "escort", "cure") or offer.get("personal") is not None
        return
    screen.choose(turn_in)
    render(app)
    assert offer["state"] == "finished" and game.leader.money > money
    assert app.error_count == 0


def test_ai_extras_can_be_switched_off(make_app):
    """The setting keeps Player2 energy for people and places: no background flourishes are asked for."""
    app = make_app()
    app.settings.ai_enabled = True
    assert not app.ai_extras()  # the AI is not online in tests, so nothing is asked for at all
    app.settings.ai_extras = False
    calls = []
    app.ai.usable = lambda: True  # pretend it is online
    app.ai.submit = lambda *a, **k: calls.append(a)
    assert app.ai.usable() and not app.ai_extras()
    start_small_world(app)
    gs = app.top
    gs._dress_magic_items()
    gs._word_dungeon()
    gs._word_area()
    gs._word_quests()
    assert not calls
    app.settings.ai_extras = True
    assert app.ai_extras()


def test_a_life_ends_and_another_begins_in_the_same_world(make_app):
    """M9 through the screens: die, go back to the title, make a new character in the same world."""
    from realmwalker.game import death
    from realmwalker.ui.screens.creation import CreationScreen
    from realmwalker.ui.screens.game_menu import WorldPickScreen
    from realmwalker.ui.screens.game_screen import GameScreen
    from realmwalker.ui.screens.interlude import InterludeScreen
    from realmwalker.ui.screens.title import TitleScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    world_id = game.world.meta.id
    first_name = game.leader.name
    game.leader.deeds.append("killed the wolf of Ashfell")
    game.renown.fame = 15
    game.over = {"cause": "killed by a bear", "place": "the hills"}
    render(app)
    assert type(app.top).__name__ == "DeathScreen"
    app.handle_event(KeyEvent("enter"))
    assert isinstance(app.top, TitleScreen) and app.game is None

    # The world is still there, without a living character in it.
    empty = [s for s in app.worlds_without_characters() if s.folder.name == world_id]
    assert empty, "the world should be waiting for a new character"
    app.handle_event(KeyEvent("r"))
    assert isinstance(app.top, WorldPickScreen)
    app.handle_event(KeyEvent("enter"))
    assert isinstance(app.top, CreationScreen)
    screen = app.top
    for _ in range(12):  # Enter through every step: sensible defaults all the way
        render(app)
        app.handle_event(KeyEvent("enter"))
        if not isinstance(app.top, CreationScreen):
            break
    assert app.game is not None and app.game.world.meta.id == world_id
    assert app.game.leader.name != first_name
    # The world moved on, and says so; behind that page is the game.
    if isinstance(app.top, InterludeScreen):
        text = screen_text(render(app))
        assert "moved on" in text or "pass" in text
        app.handle_event(KeyEvent("enter"))
    assert isinstance(app.top, GameScreen)
    assert death.fallen(app.game.world)[-1]["name"] == first_name
    assert app.error_count == 0


@pytest.mark.parametrize("size", SIZES)
def test_the_spells_window(make_app, size):
    """A caster can see what they know, what it does and how many slots are left."""
    from realmwalker.rules import spells as sp
    from realmwalker.ui.screens.spells import SpellsScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    c = game.leader
    if not sp.is_caster(c, game.tables):  # make the leader a wizard for the test
        c.cls = "wizard"
        sp.init_spells(c, game.tables)
    app.handle_event(KeyEvent("S"))
    assert isinstance(app.top, SpellsScreen)
    text = screen_text(render(app, size))
    assert "Cantrips" in text or "Slots" in text
    for key in ("down", "tab", "pagedown"):
        app.handle_event(KeyEvent(key))
        render(app, size)
    app.handle_event(KeyEvent("escape"))
    assert app.error_count == 0


def test_drawing_steel_on_a_townsman_asks_first(make_app):
    """The design asks for a confirmation before dangerous things; attacking somebody is one."""
    from realmwalker.game.people import npcs_in
    from realmwalker.ui.screens.dialogue import DialogueScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    town = next(s for s in game.world.settlements if s.kind in ("town", "city"))
    game.player.x, game.player.y = town.x, town.y
    game.enter_local()
    npc = next(n for n in npcs_in(game.world, town.id) if n.alive)
    game.talk_to = npc.id
    render(app)
    screen = app.top
    assert isinstance(screen, DialogueScreen)
    attack = next(i for i, c in enumerate(screen.conv.menu()) if c.id == "attack")
    screen.choose(attack)
    assert isinstance(app.top, ConfirmBox), "it should ask first"
    assert game.battle is None
    render(app)
    app.handle_event(KeyEvent("n"))  # no: nothing happens
    assert game.battle is None
    screen.choose(attack)
    app.handle_event(KeyEvent("y"))
    render(app)
    assert game.battle is not None or game.encounter is not None
    assert app.error_count == 0


@pytest.mark.parametrize("size", SIZES)
def test_the_make_something_window(make_app, size):
    from realmwalker.rules.inventory import add_item
    from realmwalker.ui.screens.camp import CampScreen, CraftScreen

    app = make_app()
    start_small_world(app)
    game = app.game
    add_item(game.leader, game.tables.items, "firewood", 2)
    app.push(CampScreen(app, game))
    render(app, size)
    app.handle_event(KeyEvent("m"))
    assert isinstance(app.top, CraftScreen)
    text = screen_text(render(app, size))
    assert "torches" in text
    app.handle_event(KeyEvent("down"))
    render(app, size)
    app.handle_event(KeyEvent("1"))  # make torches
    render(app, size)
    assert any(i.def_id == "torch" for i in game.leader.inventory)
    assert app.error_count == 0
