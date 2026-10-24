"""The application core: configuration, data, sound and the screen stack.

The App does not own a window. `ui/window.py` runs it in a real window; tests and the autoplay
bot drive it headlessly by calling handle_event(), update() and render() themselves.
Every call into screen code is guarded: an error is logged, the player sees a friendly notice,
and the game carries on.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import tcod.console

from realmwalker import GAME_NAME, MILESTONE, __version__
from realmwalker.audio import Audio
from realmwalker.audio.bank import SoundBank
from realmwalker.audio.music import MusicLibrary
from realmwalker.audio.watch import GameWatch
from realmwalker.config import DEFAULT_FONT_SIZE, FONT_SIZES, GameConfig, Settings
from realmwalker.core.logs import setup_logging
from realmwalker.core.rng import RNG
from realmwalker.data.registry import DataRegistry
from realmwalker.game.save import SaveError, list_saves, load_game, save_game
from realmwalker.game.state import GameState
from realmwalker.paths import Paths
from realmwalker.ui import colors
from realmwalker.ui.input import InputEvent, KeyEvent, MouseEvent
from realmwalker.ui.screens.base import MessageBox, Screen
from realmwalker.ui.widgets import Canvas, Menu, Region
from realmwalker.world.tables import Tables

log = logging.getLogger("realmwalker.app")

MIN_COLUMNS = 80
MIN_ROWS = 30
RENDER_FAILURES_BEFORE_CLOSING = 3
CARD_DELAY = 0.3  # seconds of hovering before a tooltip card shows (docs/EXPANSIONS.md §4.15)
NAV_KEYS = {"up", "down", "left", "right", "pageup", "pagedown", "home", "end", "tab"}


def ui_state(screen: Screen) -> tuple:
    """What a screen is showing, in brief (its choices, pages, tabs and modes), to tell whether a key changed it."""
    out = []
    for key, value in vars(screen).items():
        if key == "app":
            continue
        if value is None or isinstance(value, (bool, int, str)):
            out.append((key, value))
        elif isinstance(value, tuple) and len(value) <= 4 and all(isinstance(v, (int, str)) for v in value):
            out.append((key, value))
        elif isinstance(value, Menu):
            out.append((key, value.selected))
    return tuple(out)


@dataclass
class Toast:
    text: str
    color: tuple[int, int, int]
    expires: float


class App:
    def __init__(
        self,
        *,
        home: Path | str | None = None,
        headless: bool = False,
        config_overrides: dict | None = None,
        settings_overrides: dict | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.paths = Paths(home)
        self.headless = headless
        self.clock = clock
        setup_logging(self.paths.logs)
        log.info("%s %s (%s) starting%s", GAME_NAME, __version__, MILESTONE, " headless" if headless else "")

        self.config = GameConfig.load(self.paths.config_file)
        for key, value in (config_overrides or {}).items():
            setattr(self.config, key, value)
        self.settings = Settings.load(self.paths.settings_file)
        for key, value in (settings_overrides or {}).items():
            setattr(self.settings, key, value)
        self.settings.normalise()

        self.data, self.data_errors = DataRegistry.load(self.paths.data)
        self.tables: Tables | None = None
        if not self.data_errors:
            try:
                self.tables = Tables(self.data)
            except Exception as exc:  # data passed validation but still could not be used
                log.exception("Could not build game tables")
                self.data_errors.append(f"The game data could not be prepared: {exc}")
            if self.tables is not None:
                from realmwalker.rules.engine import check

                self.data_errors.extend(check.problems(self.tables))  # what the rules data names must exist in code
                from realmwalker.game.story import check as story_check

                self.data_errors.extend(story_check.problems(self.tables))  # and the story data's
        from realmwalker.ui.gfx import headless

        # The pictures: headless they are recorded and checked, never shown; a window replaces this with its own.
        self.gfx = headless()
        if not self.gfx.atlas.ok:
            self.data_errors.append("The game's pictures (assets/tiles) are missing. Download the game again.")
        self.game: GameState | None = None
        self._last_autosave = clock()

        # Randomness for menus and demos only. Game worlds own their own seeded RNG.
        self.ui_rng = RNG(int(time.time() * 1000) % (2**31), "ui")
        # Sound: silent until a window opens the speakers (start_sound); the same calls work either way.
        self.audio = self._make_audio(None)
        self._sound_failed = False
        self._ears = GameWatch()

        self.screens: list[Screen] = []
        self.running = True
        self.error_count = 0
        self.toasts: list[Toast] = []
        self.regions: list[Region] = []
        self.mouse = (-1, -1)
        self.mouse_px = (-1.0, -1.0)
        self.window_requests: set[str] = set()
        self._render_failures: dict[int, int] = {}
        self.last_console_size = (MIN_COLUMNS, MIN_ROWS)

        if self.data_errors:
            from realmwalker.ui.screens.data_errors import DataErrorScreen

            self.push(DataErrorScreen(self, self.data_errors))
        else:
            from realmwalker.ui.screens.title import TitleScreen

            self.push(TitleScreen(self))

    # ------------------------------------------------------------------ setup helpers
    def _make_audio(self, backend) -> Audio:
        bank = SoundBank(self.data.get("sounds.json") or {}, self.paths.sounds)
        library = MusicLibrary(self.data.get("music.json") or {}, self.paths.music_builtin, self.paths.music)
        return Audio(bank=bank, library=library, settings=self.settings, clock=self.clock,
                     rng=self.ui_rng.child("sound"), backend=backend,
                     levels_file=self.paths.music_levels if backend is not None else None)

    def start_sound(self) -> None:
        """Open the speakers (the window does this once it is up). Without a sound device the game stays silent."""
        from realmwalker.audio.engine import open_speakers

        backend = open_speakers()
        if backend is None:
            return
        self.audio = self._make_audio(backend)
        self.audio.library.make_folders()
        self.audio.library.scan()
        self.audio.bank.preload()
        self.audio.start()

    def music_mood(self) -> str | None:
        """The music the screens want: the top screen that has an opinion decides (a pack opened on the road keeps
        the road's music; a battle has its own)."""
        for screen in reversed(self.screens):
            mood = screen.music()
            if mood is not None:
                return mood
        return None

    # ------------------------------------------------------------------ screen stack
    @property
    def top(self) -> Screen | None:
        return self.screens[-1] if self.screens else None

    def push(self, screen: Screen) -> None:
        self.screens.append(screen)
        self.audio.ui(screen.sound_open)
        self._guard("opening a screen", screen.on_enter)

    def pop(self) -> Screen | None:
        if not self.screens:
            return None
        screen = self.screens.pop()
        self.audio.ui(screen.sound_close)
        self._guard("closing a screen", screen.on_exit)
        if not self.screens:
            from realmwalker.ui.screens.title import TitleScreen

            self.push(TitleScreen(self))
        return screen

    def replace(self, screen: Screen) -> None:
        if self.screens:
            old = self.screens.pop()
            self._guard("closing a screen", old.on_exit)
        self.push(screen)

    def find_screen(self, kind: type) -> Screen | None:
        for s in reversed(self.screens):
            if isinstance(s, kind):
                return s
        return None

    # ------------------------------------------------------------------ errors
    def _guard(self, context: str, fn: Callable, *args) -> bool:
        try:
            fn(*args)
            return True
        except Exception:
            self.report_error(context)
            return False

    def report_error(self, context: str) -> None:
        """Log the current exception and tell the player, without crashing."""
        self.error_count += 1
        log.exception("Recovered from an error while %s", context)
        if not any(getattr(s, "is_error_notice", False) for s in self.screens):
            box = MessageBox(
                self,
                "Something went wrong",
                f"The game ran into a problem while {context}, but it has recovered and you can carry on. "
                f"Details were written to <place>{self.paths.logs / 'errors.log'}</>.",
                color=colors.named("danger"),
            )
            box.is_error_notice = True
            self.screens.append(box)
            self.audio.ui("ui_error")

    # ------------------------------------------------------------------ input
    def handle_event(self, ev: InputEvent) -> None:
        try:
            if isinstance(ev, MouseEvent):
                self._handle_mouse(ev)
            elif not self._global_key(ev) and self.top is not None:
                self._key_to_screen(ev)
        except Exception:
            self.report_error("handling your input")

    def _key_to_screen(self, ev: KeyEvent) -> None:
        """Give the key to the top screen. If it visibly changed something there (the choice moved, a page turned, a
        value changed), a quiet sound answers; screens with sounds of their own (the map, a battle) say so."""
        top = self.top
        before = ui_state(top) if top.key_sounds and not top.captures_text else None
        top.handle_key(ev)
        if before is not None and self.top is top and ui_state(top) != before:
            self.audio.ui("ui_move" if ev.key in NAV_KEYS else "ui_click")

    def _handle_mouse(self, ev: MouseEvent) -> None:
        if ev.x >= 0:
            self.mouse = (ev.x, ev.y)
            self.mouse_px = (ev.px, ev.py)
        top = self.top
        if top is not None and top.handle_mouse(ev):
            return
        if ev.kind == "click":
            for region in reversed(self.regions):
                if region.contains(ev.x, ev.y):
                    action = region.right_action if ev.button == "right" else region.action
                    if action:
                        self.audio.ui("ui_click")
                        action()
                        return
                    if region.action is None and region.right_action is None and region.wheel is None:
                        return  # a blocking region (e.g. outside a dialog)
        elif ev.kind == "wheel":
            for region in reversed(self.regions):
                if region.contains(*self.mouse) and region.wheel:
                    region.wheel(ev.dy)
                    return

    def _global_key(self, ev: KeyEvent) -> bool:
        if ev.ctrl and ev.key in ("=", "+"):
            self.change_font_size(+1)
        elif ev.ctrl and ev.key == "-":
            self.change_font_size(-1)
        elif ev.ctrl and ev.key == "0":
            self.set_font_size(DEFAULT_FONT_SIZE)
        elif ev.key == "f11" or (ev.key == "enter" and ev.alt):
            self.toggle_fullscreen()
        elif ev.key == "f12":
            self.window_requests.add("screenshot")
        elif ev.ctrl and ev.key in ("m", "M"):
            self.toggle_mute()
        elif ev.key == "f1":
            from realmwalker.ui.screens.help import HelpScreen

            if not isinstance(self.top, HelpScreen):
                self.push(HelpScreen(self))
        elif ev.key in ("`", "~") and self.config.debug_console and not (self.top and self.top.captures_text):
            from realmwalker.ui.screens.debug_console import DebugConsole

            if not isinstance(self.top, DebugConsole):
                self.push(DebugConsole(self))
        else:
            return False
        return True

    # ------------------------------------------------------------------ settings actions
    def save_settings(self) -> None:
        try:
            self.settings.save(self.paths.settings_file)
        except OSError:
            log.exception("Could not save settings")
            self.notify("Could not save settings (see logs).", "warn")

    def set_font_size(self, size: int) -> None:
        size = min(FONT_SIZES, key=lambda s: abs(s - size))
        if size != self.settings.font_size:
            self.settings.font_size = size
            self.window_requests.add("font")
            self.save_settings()
        self.notify(f"Text size {size}", "info")

    def change_font_size(self, step: int) -> None:
        idx = FONT_SIZES.index(self.settings.font_size)
        self.set_font_size(FONT_SIZES[max(0, min(len(FONT_SIZES) - 1, idx + step))])

    def toggle_fullscreen(self) -> None:
        self.settings.fullscreen = not self.settings.fullscreen
        self.window_requests.add("fullscreen")
        self.save_settings()

    def toggle_mute(self) -> None:
        self.settings.muted = not self.settings.muted
        self.audio.apply_settings()
        self.save_settings()
        self.notify("Sound off (Ctrl M to turn it back on)" if self.settings.muted else "Sound on", "info", 2.0)

    def open_folder(self, path: Path) -> bool:
        """Show a folder in Explorer (or the desktop's file manager). Never from tests or the autoplay bot."""
        if self.headless:
            return False
        try:
            path.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(str(path))  # noqa: S606 - the player's own folder, at their request
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
            return True
        except Exception:
            log.exception("Could not open the folder %s", path)
            return False

    def sound_settings_changed(self) -> None:
        self.audio.apply_settings()
        self.save_settings()

    # ------------------------------------------------------------------ frame
    def notify(self, text: str, color: str = "fg", seconds: float = 3.5) -> None:
        self.toasts.append(Toast(text, colors.named(color), self.clock() + seconds))
        self.toasts = self.toasts[-4:]

    def update(self) -> None:
        if self.top is not None:
            self._guard("updating the screen", self.top.update)
        now = self.clock()
        self.toasts = [t for t in self.toasts if t.expires > now]
        self._update_sound()

    def _update_sound(self) -> None:
        """Sound never interrupts the game: a problem is written to the log once and the game plays on quietly."""
        try:
            self._ears.hear(self.game, self.audio)
            self.audio.want_music(self.music_mood())
            self.audio.update()
        except Exception:
            if not self._sound_failed:
                self._sound_failed = True
                log.exception("Sound failed; carrying on without it")

    def _time_card(self, canvas: Canvas) -> None:
        """A card appears after a short hover over the same thing (words show at once)."""
        rect = canvas.tip_rect if canvas.tip_is_card else None
        now = self.clock()
        if rect != getattr(self, "_tip_rect", None):
            self._tip_rect, self._tip_since = rect, now
        canvas.tip_ready = rect is not None and now - self._tip_since >= CARD_DELAY
        self._tip_waiting = rect is not None and not canvas.tip_ready

    def frame_timeout(self) -> float:
        """How long the window may sleep waiting for input before redrawing."""
        if getattr(self, "_tip_waiting", False):
            return 0.05  # a card is about to appear
        moving = self.gfx.animate and getattr(self.top, "moving", False)
        if moving:
            return 1 / 60  # something on screen is in motion: keep it smooth
        busy = self.toasts or getattr(self.top, "animating", False)
        if busy:
            return 0.05
        if self.gfx.ambient and getattr(self.top, "ambient", False):
            return 1 / 30  # water, fire and weather keep moving
        return 0.25

    def gfx_frame(self):
        """The picture context for this frame, brought up to date with the settings and the clock."""
        g = self.gfx
        g.now = self.clock()
        g.motion = self.settings.animations
        return g

    def render(self, console: tcod.console.Console) -> None:
        self.last_console_size = (console.width, console.height)
        console.clear(fg=colors.FG, bg=colors.BG)
        canvas = Canvas(console, self.mouse, gfx=self.gfx_frame(),
                        mouse_px=self.mouse_px if self.mouse_px[0] >= 0 else None)
        self.last_canvas = canvas
        start = len(self.screens) - 1
        while start > 0 and self.screens[start].modal:
            start -= 1
        for i in range(max(0, start), len(self.screens)):
            if i >= len(self.screens):
                break
            screen = self.screens[i]
            canvas.interactive = i == len(self.screens) - 1
            if screen.modal and i > start:
                # Dim what lies beneath a dialog, and draw the dialog above any picture.
                canvas.dim()
                canvas.push_layer()
            try:
                screen.render(canvas)
                self._render_failures.pop(id(screen), None)
            except Exception:
                self._render_failed(screen)
                return
        try:
            canvas.push_layer()  # the status line, notices and tooltips sit above every picture
            self._render_toasts(canvas)
            self._time_card(canvas)
            canvas.draw_tooltip()
        except Exception:
            self.report_error("drawing the screen")
        self.regions = canvas.regions

    def _render_failed(self, screen: Screen) -> None:
        count = self._render_failures.get(id(screen), 0) + 1
        self._render_failures[id(screen)] = count
        if count >= RENDER_FAILURES_BEFORE_CLOSING and screen in self.screens:
            # This screen keeps failing to draw: close it so the game stays usable.
            self.screens.remove(screen)
            if not self.screens:
                from realmwalker.ui.screens.title import TitleScreen

                self.screens.append(TitleScreen(self))
        self.report_error("drawing the screen")

    def _render_toasts(self, canvas: Canvas) -> None:
        y = canvas.height - 3
        for toast in reversed(self.toasts):
            width = len(toast.text) + 4
            x = (canvas.width - width) // 2
            canvas.fill(x, y, width, 1, (30, 28, 24))
            canvas.text(x + 2, y, toast.text, toast.color)
            y -= 1

    # ------------------------------------------------------------------ game sessions
    def start_game(self, game: GameState) -> None:
        """Begin playing: save at once, then show the main game screen over the title."""
        from realmwalker.ui.screens.game_screen import GameScreen

        self.game = game
        self.save_game()
        while len(self.screens) > 1:
            self.pop()
        self.push(GameScreen(self, game))

    def save_game(self) -> bool:
        if self.game is None:
            return False
        try:
            save_game(self.game, self.paths.saves)
            self._last_autosave = self.clock()
            return True
        except Exception:
            self.report_error("saving the game")
            return False

    def maybe_autosave(self) -> None:
        if self.game is not None and self.game.dirty:
            if self.clock() - self._last_autosave >= self.settings.autosave_minutes * 60:
                if self.save_game():
                    self.notify("Game saved.", "dim", 1.5)

    def end_game(self) -> None:
        """Save and leave the current game (back to the title screen)."""
        self.save_game()
        self.game = None
        from realmwalker.ui.screens.title import TitleScreen

        while self.screens:
            self.screens.pop().on_exit()
        self.push(TitleScreen(self))

    def saves_with_characters(self) -> list:
        try:
            return [s for s in list_saves(self.paths.saves) if s.character]
        except OSError:
            return []

    def worlds_without_characters(self) -> list:
        try:
            return [s for s in list_saves(self.paths.saves) if not s.character]
        except OSError:
            return []

    def create_character_in(self, folder) -> bool:
        """Open character creation for a saved world that has no living character."""
        from realmwalker.game.save import load_world
        from realmwalker.ui.screens.creation import CreationScreen

        try:
            world = load_world(folder)
        except SaveError as exc:
            self.push(MessageBox(self, "Could not load", f"{exc}", color=colors.named("danger")))
            return False
        self.push(CreationScreen(self, world))
        return True

    def continue_game(self, folder) -> bool:
        if self.tables is None:
            return False
        try:
            game = load_game(folder, self.tables)
        except SaveError as exc:
            self.push(MessageBox(self, "Could not load", f"{exc} The files are still there, untouched.",
                                 color=colors.named("danger")))
            return False
        self.start_game(game)
        game.say("You take up your journey again.", "system")
        return True

    # ------------------------------------------------------------------ shutdown
    def request_quit(self) -> None:
        self.running = False

    def shutdown(self) -> None:
        if self.game is not None:
            self.save_game()
        for screen in reversed(self.screens):  # let go of what screens hold (the map painter's thread, a preview)
            self._guard("closing the screen", screen.on_exit)
        try:
            self.audio.close()
        except Exception:
            log.exception("Error closing the sound")
        self.save_settings()
        log.info("%s shut down cleanly (%d recovered errors this session)", GAME_NAME, self.error_count)
