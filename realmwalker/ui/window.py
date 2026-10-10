"""Runs the App in a real window: builds the font, pumps events, presents frames.

Each frame the screens draw their text into a console and record pictures beside it (ui/gfx); the GPU draws
both, layer by layer, into a frame the size of the text grid, which is put in the middle of the window.

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


class Presenter:
    """Where the frame sits in the window, and how to turn a window pixel into a frame pixel and a cell."""

    def __init__(self) -> None:
        self.ox = self.oy = 0.0
        self.scale = 1.0
        self.tile_w, self.tile_h = 10, 20
        self.ratio = (1.0, 1.0)  # output pixels per window coordinate (high-DPI screens)

    def to_frame(self, wx: float, wy: float) -> tuple[int, int, float, float]:
        px, py = wx * self.ratio[0], wy * self.ratio[1]
        fx = (px - self.ox) / self.scale
        fy = (py - self.oy) / self.scale
        return int(fx // self.tile_w), int(fy // self.tile_h), fx, fy


def run(app: App, *, script: list[ScriptStep] | None = None, max_frames: int | None = None,
        screenshot_to: Path | None = None, screenshots_at: dict[int, Path] | None = None) -> None:
    from realmwalker.ui.gfx import GfxContext, typefaces
    from realmwalker.ui.gfx import atlas as atlas_mod

    font_path = fonts.default_font_path(app.paths.fonts)
    tileset = fonts.build_tileset(app.settings.font_size, font_path)
    typefaces.set_folder(app.paths.fonts)
    flags = tcod.context.SDL_WINDOW_RESIZABLE | tcod.context.SDL_WINDOW_MAXIMIZED
    with tcod.context.new(width=1600, height=900, tileset=tileset, title=GAME_NAME, vsync=True,
                          sdl_window_flags=flags) as ctx:
        window = ctx.sdl_window
        renderer = getattr(ctx, "sdl_renderer", None)
        gpu = None
        presenter = Presenter()
        if renderer is not None:
            try:
                from realmwalker.ui.gfx.gpu import Gpu

                atlas = atlas_mod.load(str(app.paths.tiles))
                gpu = Gpu(renderer, atlas)
                gpu.set_tileset(tileset)
                app.gfx = GfxContext(atlas, tileset.tile_width, tileset.tile_height)
            except Exception:
                log.exception("Pictures are not available; drawing text only")
                gpu = None
                app.gfx = None
        if window is not None:
            try:
                window.start_text_input()
            except Exception:
                log.warning("Could not start text input", exc_info=True)
            if app.settings.fullscreen:
                window.fullscreen = True
        try:
            app.start_sound()
        except Exception:
            log.exception("Sound could not be started; playing in silence")
        translator = EventTranslator(presenter.to_frame if gpu is not None else None)
        console: tcod.console.Console | None = None
        frame = 0
        pending_script = sorted(script or [], key=lambda s: s[0])

        def shoot(path: Path) -> None:
            if gpu is not None:
                pixels = gpu.read_frame()
                if pixels is not None:
                    Image.fromarray(pixels[..., :3]).save(path)
                    return
            if console is not None:
                save_screenshot(tileset, console, path)

        while app.running:
            if gpu is not None:
                out_w, out_h = renderer.output_size
                tw, th = tileset.tile_width, tileset.tile_height
                cols, rows = max(MIN_COLUMNS, out_w // tw), max(MIN_ROWS, out_h // th)
            else:
                cols, rows = ctx.recommended_console_size(MIN_COLUMNS, MIN_ROWS)
            if console is None or console.width != cols or console.height != rows:
                console = tcod.console.Console(cols, rows, order="F")
            app.render(console)
            if gpu is not None:
                fw, fh = cols * tw, rows * th
                presenter.tile_w, presenter.tile_h = tw, th
                presenter.scale = min(1.0, out_w / fw, out_h / fh)
                presenter.ox = (out_w - fw * presenter.scale) / 2
                presenter.oy = (out_h - fh * presenter.scale) / 2
                if window is not None:
                    ww, wh = window.size
                    presenter.ratio = (out_w / max(1, ww), out_h / max(1, wh))
                canvas = getattr(app, "last_canvas", None)
                layers = canvas.layers if canvas is not None else []
                if not layers:
                    from realmwalker.ui.gfx.scene import Layer

                    layers = [Layer(console)]
                tex = gpu.draw(layers, fw, fh, colors.BG)
                gpu.present(tex, presenter.ox, presenter.oy, presenter.scale, colors.BG)
            else:
                ctx.present(console, keep_aspect=True, integer_scaling=True, clear_color=colors.BG)

            timeout = 0.02 if pending_script else app.frame_timeout()
            for event in tcod.event.wait(timeout=timeout):
                if isinstance(event, tcod.event.Quit):
                    app.request_quit()
                    break
                if isinstance(event, tcod.event.WindowEvent) and event.type in ("WindowFocusGained", "WindowFocusLost"):
                    app.audio.set_focus(event.type == "WindowFocusGained")
                ev = event if gpu is not None else ctx.convert_event(event)
                for gev in translator.translate(ev):
                    app.handle_event(gev)
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
                if gpu is not None:
                    gpu.set_tileset(tileset)
                    app.gfx.cell_w, app.gfx.cell_h = tileset.tile_width, tileset.tile_height
            if "fullscreen" in app.window_requests and window is not None:
                window.fullscreen = app.settings.fullscreen
            if "screenshot" in app.window_requests and console is not None:
                name = time.strftime("realmwalker-%Y%m%d-%H%M%S.png")
                path = app.paths.screenshots / name
                shoot(path)
                app.notify(f"Screenshot saved: {path.name}", "info")
            app.window_requests.clear()

            if screenshots_at and frame in screenshots_at and console is not None:
                shoot(screenshots_at[frame])
            frame += 1
            if max_frames is not None and frame >= max_frames:
                if screenshot_to is not None and console is not None:
                    shoot(screenshot_to)
                app.request_quit()
