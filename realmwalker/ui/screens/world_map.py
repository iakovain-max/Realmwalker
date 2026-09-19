"""The World Map: the whole land as far as you know it, with a cursor to plan journeys."""

from __future__ import annotations

import numpy as np

from realmwalker.game.describe import describe_overworld
from realmwalker.ui import colors
from realmwalker.ui.input import KeyEvent, MouseEvent
from realmwalker.ui.map_render import PLAYER_FG, UNSEEN_BG, apply_light, camera
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.screens.game_screen import key_direction
from realmwalker.ui.widgets import Canvas

SIDE_W = 36


class WorldMapScreen(Screen):
    title = "World Map"

    def __init__(self, app, game_screen, travel_mode: bool = False) -> None:
        super().__init__(app)
        self.gs = game_screen
        self.game = game_screen.game
        p = self.game.player
        self.cursor = (p.x, p.y)
        self.travel_mode = travel_mode
        self.fit = False  # False: 1 tile per cell; True: squeeze the whole world onto the screen
        self.view = (0, 0, 1, 0, 0)  # x0, y0 of map on screen, scale, first tile x, first tile y

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        mw, mh = w - SIDE_W, h - 1
        world = self.game.world
        pic = self.gs.picture
        scale = 1
        if self.fit:
            scale = max(1, int(np.ceil(max(world.width / mw, world.height / mh))))
        cols, rows = int(np.ceil(world.width / scale)), int(np.ceil(world.height / scale))
        cx, cy = self.cursor[0] // scale, self.cursor[1] // scale
        x0, ox = camera(cx, mw, cols)
        y0, oy = camera(cy, mh, rows)
        vw, vh = min(mw, cols), min(mh, rows)
        xs = np.minimum((np.arange(x0, x0 + vw) * scale + scale // 2), world.width - 1)
        ys = np.minimum((np.arange(y0, y0 + vh) * scale + scale // 2), world.height - 1)
        grid = np.ix_(xs, ys)
        ch = pic.ch[grid].copy()
        fg, bg = apply_light(pic.fg[grid], pic.bg[grid], 1.0)
        fg, bg = fg.copy(), bg.copy()
        p = self.game.player
        if scale == 1:
            explored = p.explored[grid]
        else:
            # A squeezed cell counts as explored if any tile inside it was seen.
            padded = np.zeros((cols * scale, rows * scale), dtype=bool)
            padded[: world.width, : world.height] = p.explored
            blocks = padded.reshape(cols, scale, rows, scale).any(axis=(1, 3))
            explored = blocks[x0:x0 + vw, y0:y0 + vh]
        ch[~explored] = ord(" ")
        bg[~explored] = UNSEEN_BG
        stypes = self.game.tables.sites["settlement_types"]
        for s in world.settlements:
            if s.id not in p.known_settlements and not p.explored[s.x, s.y]:
                continue
            sx, sy = s.x // scale - x0, s.y // scale - y0
            if 0 <= sx < vw and 0 <= sy < vh:
                ch[sx, sy] = ord(stypes[s.kind]["glyph"])
                fg[sx, sy] = stypes[s.kind]["fg"]
        px, py = p.x // scale - x0, p.y // scale - y0
        if 0 <= px < vw and 0 <= py < vh:
            ch[px, py] = ord("@")
            fg[px, py] = PLAYER_FG
        kx, ky = cx - x0, cy - y0
        if 0 <= kx < vw and 0 <= ky < vh:
            bg[kx, ky] = (130, 104, 40)
        dst = (slice(ox, ox + vw), slice(oy, oy + vh))
        canvas.con.rgb["ch"][dst] = ch
        canvas.con.rgb["fg"][dst] = fg
        canvas.con.rgb["bg"][dst] = bg
        self.view = (ox, oy, scale, x0, y0)
        canvas.hit(ox, oy, vw, vh)
        self._side(canvas, mw, 0, SIDE_W, h)

    def _side(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        title = "Travel: choose where" if self.travel_mode else self.title
        canvas.frame(x, y, w, h, title, double=True)
        ix, iw = x + 2, w - 4
        row = y + 2
        canvas.markup(ix, row, f"<place>{self.game.world.meta.name}</>", max_width=iw)
        row += 2
        text = describe_overworld(self.game, *self.cursor)
        row += canvas.wrapped(ix, row, text, iw, max_lines=max(3, h - 22)) + 1
        plan = self.game.plan_travel(self.cursor) if self.cursor != (self.game.player.x, self.game.player.y) else None
        if plan is not None:
            canvas.wrapped(ix, row, f"<good>Journey:</> {self.game.describe_plan(plan)}.", iw, max_lines=3)
            row += 3
        keys = [("arrows", "move the cursor"), ("Shift+arrows", "move faster"), ("Enter", "travel to the cursor"),
                ("z", "zoom out / in"), ("@", "back to yourself"), ("Esc", "close")]
        ky = h - len(keys) - 1
        for key, what in keys:
            canvas.markup(ix, ky, f"<loot>{key:>12}</> <dim>{what}</>", max_width=iw)
            ky += 1

    # ------------------------------------------------------------------ input
    def _move_cursor(self, dx: int, dy: int, fast: bool = False) -> None:
        step = (self.view[2] if self.fit else 1) * (8 if fast else 1)
        world = self.game.world
        x = max(0, min(world.width - 1, self.cursor[0] + dx * step))
        y = max(0, min(world.height - 1, self.cursor[1] + dy * step))
        self.cursor = (x, y)

    def _travel(self) -> None:
        dest = self.cursor
        self.close()
        self.gs.plan_travel_to(dest)

    def handle_key(self, ev: KeyEvent) -> bool:
        d = key_direction(ev)
        if d is not None:
            self._move_cursor(*d, fast=ev.shift)
        elif ev.key == "enter":
            self._travel()
        elif ev.key in ("z", "Z"):
            self.fit = not self.fit
        elif ev.key == "@":
            self.cursor = (self.game.player.x, self.game.player.y)
        elif ev.key in ("escape", "m", "t"):
            self.close()
        else:
            return False
        return True

    def handle_mouse(self, ev: MouseEvent) -> bool:
        ox, oy, scale, x0, y0 = self.view
        tx, ty = (ev.x - ox + x0) * scale + scale // 2, (ev.y - oy + y0) * scale + scale // 2
        world = self.game.world
        if ev.x >= canvas_width_guard(self.app) - SIDE_W or not world.in_bounds(tx, ty):
            return False
        if ev.kind == "move":
            self.cursor = (tx, ty)
        elif ev.kind == "click":
            self.cursor = (tx, ty)
            if ev.button == "left":
                self._travel()
            return True
        return False

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("up", "down", "left", "right", "z", "@", "escape")] + [KeyEvent("enter")]


def canvas_width_guard(app) -> int:
    return app.last_console_size[0]
