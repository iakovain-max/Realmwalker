"""The application core: configuration, data, the AI service and the screen stack.

The App does not own a window. `ui/window.py` runs it in a real window; tests and the autoplay
bot drive it headlessly by calling handle_event(), update() and render() themselves.
Every call into screen code is guarded: an error is logged, the player sees a friendly notice,
and the game carries on.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import tcod.console

from realmwalker import GAME_NAME, MILESTONE, __version__
from realmwalker.ai.client import Player2Client
from realmwalker.ai.prompts import PromptLibrary
from realmwalker.ai.service import SYSTEM_PROMPT, AIService, AIStatus
from realmwalker.ai.tasks import ALL_TASKS
from realmwalker.config import DEFAULT_FONT_SIZE, FONT_SIZES, GameConfig, Settings
from realmwalker.core.logs import set_ai_debug, setup_logging
from realmwalker.core.rng import RNG
from realmwalker.data.registry import DataRegistry
from realmwalker.game.save import SaveError, list_saves, load_game, save_game
from realmwalker.game.state import GameState
from realmwalker.paths import Paths
from realmwalker.ui import colors
from realmwalker.ui.input import InputEvent, KeyEvent, MouseEvent
from realmwalker.ui.screens.base import MessageBox, Screen
from realmwalker.ui.widgets import Canvas, Region
from realmwalker.world.tables import Tables

log = logging.getLogger("realmwalker.app")

MIN_COLUMNS = 80
MIN_ROWS = 30
RENDER_FAILURES_BEFORE_CLOSING = 3


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
        client_factory: Callable[[], Player2Client] | None = None,
        start_ai: bool = True,
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
        set_ai_debug(self.settings.ai_debug_log)

        self.data, self.data_errors = DataRegistry.load(self.paths.data)
        self.prompts = PromptLibrary(self.paths.prompts)
        self.data_errors += self._check_prompts()
        self.tables: Tables | None = None
        if not self.data_errors:
            try:
                self.tables = Tables(self.data)
            except Exception as exc:  # data passed validation but still could not be used
                log.exception("Could not build game tables")
                self.data_errors.append(f"The game data could not be prepared: {exc}")
        self.game: GameState | None = None
        self._last_autosave = clock()

        self.ai = AIService(
            prompts=self.prompts,
            client_factory=client_factory or self._make_client,
            enabled=self.settings.ai_enabled,
            workers=self.config.ai_workers,
        )
        # Randomness for menus and demos only. Game worlds own their own seeded RNG.
        self.ui_rng = RNG(int(time.time() * 1000) % (2**31), "ui")

        self.screens: list[Screen] = []
        self.running = True
        self.error_count = 0
        self.toasts: list[Toast] = []
        self.regions: list[Region] = []
        self.mouse = (-1, -1)
        self.window_requests: set[str] = set()
        self._render_failures: dict[int, int] = {}
        self.last_console_size = (MIN_COLUMNS, MIN_ROWS)

        if self.data_errors:
            from realmwalker.ui.screens.data_errors import DataErrorScreen

            self.push(DataErrorScreen(self, self.data_errors))
        else:
            from realmwalker.ui.screens.title import TitleScreen

            self.push(TitleScreen(self))
        if start_ai:
            self.ai.start()

    # ------------------------------------------------------------------ setup helpers
    def _make_client(self) -> Player2Client:
        return Player2Client(self.config.player2_base_url or None, self.config.player2_game_client_id)

    def _check_prompts(self) -> list[str]:
        errors = []
        for name in [SYSTEM_PROMPT] + [t.name for t in ALL_TASKS]:
            if not self.prompts.exists(name):
                errors.append(f"ai/prompts/{name}.txt is missing.")
        return errors

    # ------------------------------------------------------------------ screen stack
    @property
    def top(self) -> Screen | None:
        return self.screens[-1] if self.screens else None

    def push(self, screen: Screen) -> None:
        self.screens.append(screen)
        self._guard("opening a screen", screen.on_enter)

    def pop(self) -> Screen | None:
        if not self.screens:
            return None
        screen = self.screens.pop()
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

    # ------------------------------------------------------------------ input
    def handle_event(self, ev: InputEvent) -> None:
        try:
            if isinstance(ev, MouseEvent):
                self._handle_mouse(ev)
            elif not self._global_key(ev) and self.top is not None:
                self.top.handle_key(ev)
        except Exception:
            self.report_error("handling your input")

    def _handle_mouse(self, ev: MouseEvent) -> None:
        if ev.x >= 0:
            self.mouse = (ev.x, ev.y)
        top = self.top
        if top is not None and top.handle_mouse(ev):
            return
        if ev.kind == "click":
            for region in reversed(self.regions):
                if region.contains(ev.x, ev.y):
                    action = region.right_action if ev.button == "right" else region.action
                    if action:
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

    def set_ai_enabled(self, enabled: bool) -> None:
        self.settings.ai_enabled = enabled
        self.ai.set_enabled(enabled)
        self.save_settings()

    def set_ai_debug_log(self, enabled: bool) -> None:
        self.settings.ai_debug_log = enabled
        set_ai_debug(enabled)
        self.save_settings()

    # ------------------------------------------------------------------ frame
    def notify(self, text: str, color: str = "fg", seconds: float = 3.5) -> None:
        self.toasts.append(Toast(text, colors.named(color), self.clock() + seconds))
        self.toasts = self.toasts[-4:]

    def update(self) -> None:
        try:
            self.ai.poll()
        except Exception:
            self.report_error("receiving AI text")
        if self.top is not None:
            self._guard("updating the screen", self.top.update)
        now = self.clock()
        self.toasts = [t for t in self.toasts if t.expires > now]

    def frame_timeout(self) -> float:
        """How long the window may sleep waiting for input before redrawing."""
        busy = self.toasts or self.ai.pending or getattr(self.top, "animating", False)
        return 0.05 if busy else 0.25

    def render(self, console: tcod.console.Console) -> None:
        self.last_console_size = (console.width, console.height)
        console.clear(fg=colors.FG, bg=colors.BG)
        canvas = Canvas(console, self.mouse)
        start = len(self.screens) - 1
        while start > 0 and self.screens[start].modal:
            start -= 1
        for i in range(max(0, start), len(self.screens)):
            if i >= len(self.screens):
                break
            screen = self.screens[i]
            canvas.interactive = i == len(self.screens) - 1
            if screen.modal and i > start:
                # Dim what lies beneath a dialog.
                console.rgb["fg"] = console.rgb["fg"] // 2
                console.rgb["bg"] = console.rgb["bg"] // 2
            try:
                screen.render(canvas)
                self._render_failures.pop(id(screen), None)
            except Exception:
                self._render_failed(screen)
                return
        try:
            if self.top is not None and self.top.show_status:
                self._render_status(canvas)
            self._render_toasts(canvas)
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

    def _render_status(self, canvas: Canvas) -> None:
        label, color = self.ai.status_text()
        if self.ai.pending and self.ai.status == AIStatus.ONLINE:
            label = "AI writing…"
        energy = ""
        if self.ai.joules is not None and self.ai.status in (AIStatus.ONLINE, AIStatus.NO_ENERGY):
            energy = f" · energy {self.ai.joules}"
        text = f"● {label}{energy}"
        x = canvas.width - len(text) - 1
        y = canvas.height - 1
        canvas.text(x, y, "●", colors.named(color))
        canvas.text(x + 2, y, f"{label}{energy}", colors.DIM)
        canvas.hit(x, y, len(text), 1, tooltip=self._status_tooltip())

    def _status_tooltip(self) -> str:
        s = self.ai.status
        if s == AIStatus.ONLINE:
            return "Player2 is connected. Names, descriptions and dialogue are written by the AI."
        if s == AIStatus.DISABLED:
            return "AI text is switched off in Settings. The game uses its built-in text."
        if s == AIStatus.NO_ENERGY:
            return "Player2's daily energy has run out. The game uses built-in text until it refills."
        if s == AIStatus.NOT_LOGGED_IN:
            return "Open the Player2 app and log in to get AI-written text."
        return "Start the Player2 app to get AI-written text. Until then the game uses built-in text."

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
        try:
            self.ai.stop()
        except Exception:
            log.exception("Error stopping the AI service")
        self.save_settings()
        log.info("%s shut down cleanly (%d recovered errors this session)", GAME_NAME, self.error_count)
