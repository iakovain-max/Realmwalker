"""Runs the App in a real window: builds the font, pumps events, presents frames.

Also supports a scripted "smoke test" run (python main.py --smoke-test) that opens the real
window, presses a few keys, saves a screenshot and exits, so launching can be checked
automatically.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import tcod.console
import tcod.context
import tcod.event
from PIL import Image

from realmwalker import GAME_NAME
from realmwalker.app import MIN_COLUMNS, MIN_ROWS, App
from realmwalker.ui import colors, fonts
from realmwalker.ui.input import EventTranslator, InputEvent

log = logging.getLogger("realmwalker.window")

ScriptStep = tuple[int, "InputEvent | Callable[[App], None]"]


def save_screenshot(tileset, console: tcod.console.Console, path: Path) -> Path:
    pixels = tileset.render(console)
    Image.fromarray(np.asarray(pixels)).save(path)
    return path


def run(app: App, *, script: list[ScriptStep] | None = None, max_frames: int | None = None,
        screenshot_to: Path | None = None) -> None:
    font_path = fonts.default_font_path(app.paths.fonts)
    tileset = fonts.build_tileset(app.settings.font_size, font_path)
    flags = tcod.context.SDL_WINDOW_RESIZABLE | tcod.context.SDL_WINDOW_MAXIMIZED
    with tcod.context.new(width=1600, height=900, tileset=tileset, title=GAME_NAME, vsync=True,
                          sdl_window_flags=flags) as ctx:
        window = ctx.sdl_window
        if window is not None:
            try:
                window.start_text_input()
            except Exception:
                log.warning("Could not start text input", exc_info=True)
            if app.settings.fullscreen:
                window.fullscreen = True
        translator = EventTranslator()
        console: tcod.console.Console | None = None
        frame = 0
        pending_script = sorted(script or [], key=lambda s: s[0])
        while app.running:
            cols, rows = ctx.recommended_console_size(MIN_COLUMNS, MIN_ROWS)
            if console is None or console.width != cols or console.height != rows:
                console = tcod.console.Console(cols, rows, order="F")
            app.render(console)
            ctx.present(console, keep_aspect=True, integer_scaling=True, clear_color=colors.BG)

            timeout = 0.02 if pending_script else app.frame_timeout()
            for event in tcod.event.wait(timeout=timeout):
                if isinstance(event, tcod.event.Quit):
                    app.request_quit()
                    break
                for ev in translator.translate(ctx.convert_event(event)):
                    app.handle_event(ev)
            while pending_script and pending_script[0][0] <= frame:
                _, step = pending_script.pop(0)
                if callable(step):
                    step(app)
                else:
                    app.handle_event(step)
            app.update()

            if "font" in app.window_requests:
                tileset = fonts.build_tileset(app.settings.font_size, font_path)
                ctx.change_tileset(tileset)
            if "fullscreen" in app.window_requests and window is not None:
                window.fullscreen = app.settings.fullscreen
            if "screenshot" in app.window_requests and console is not None:
                name = time.strftime("realmwalker-%Y%m%d-%H%M%S.png")
                path = save_screenshot(tileset, console, app.paths.screenshots / name)
                app.notify(f"Screenshot saved: {path.name}", "info")
            app.window_requests.clear()

            frame += 1
            if max_frames is not None and frame >= max_frames:
                if screenshot_to is not None and console is not None:
                    save_screenshot(tileset, console, screenshot_to)
                app.request_quit()
