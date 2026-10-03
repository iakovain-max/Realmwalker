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
        # A journey that stopped on the way (for the night, for trouble) opens on where it was going.
        going = getattr(self.game, "journey_to", None)
        if travel_mode and going is not None and going != (p.x, p.y) and self.game.world.in_bounds(*going):
            self.cursor = going
        self.travel_mode = travel_mode
        self.fit = False  # False: 1 tile per cell; True: squeeze the whole world onto the screen
        self.show_weather = False
        self.show_realms = False
        self._weather: tuple[int, tuple] | None = None
        self.view = (0, 0, 1, 0, 0)  # x0, y0 of map on screen, scale, first tile x, first tile y
        self.painted = None  # a WorldView when the map is drawn as a picture
        self._plan_key = None
        self._plan = None

    def plan(self):
        """The journey to the cursor (worked out once per cursor position)."""
        key = (self.cursor, self.game.player.x, self.game.player.y, self.game.world.time // 60)
        if key != self._plan_key:
            self._plan_key = key
            here = (self.game.player.x, self.game.player.y)
            self._plan = self.game.plan_travel(self.cursor) if self.cursor != here else None
        return self._plan

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        mw, mh = w - SIDE_W, h - 1
        if canvas.tiles:
            self._render_painted(canvas, mw, mh)
            self._side(canvas, mw, 0, SIDE_W, h)
            return
        self.painted = None
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
        if self.show_weather:
            self._tint_weather(grid, fg, bg, explored)
        ch[~explored] = ord(" ")
        bg[~explored] = UNSEEN_BG
        if self.show_realms:
            self._tint_realms(grid, bg, explored)
        stypes = self.game.tables.sites["settlement_types"]
        for s in world.settlements:
            if s.id not in p.known_settlements and not p.explored[s.x, s.y]:
                continue
            sx, sy = s.x // scale - x0, s.y // scale - y0
            if 0 <= sx < vw and 0 <= sy < vh:
                ch[sx, sy] = ord(stypes[s.kind]["glyph"])
                fg[sx, sy] = stypes[s.kind]["fg"]
        from realmwalker.ui.map_render import QUEST_BG, quest_marks

        for qx, qy in quest_marks(self.game):
            mx, my = qx // scale - x0, qy // scale - y0
            if 0 <= mx < vw and 0 <= my < vh:
                bg[mx, my] = QUEST_BG
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

    def _render_painted(self, canvas: Canvas, mw: int, mh: int) -> None:
        from realmwalker.ui.gfx.worldview import WorldView
        from realmwalker.ui.map_render import quest_marks

        game = self.game
        world = game.world
        if self.painted is None:
            self.painted = WorldView()
            self.gs.world_view.ready(game)
            self.painted.share(self.gs.world_view)
        rect = tuple(int(v) for v in canvas.cell_rect(0, 0, mw, mh))
        if self.fit:
            ppc = max(3, int(min(rect[2] / world.width, rect[3] / world.height)))
            focus = (world.width // 2, world.height // 2)
        else:
            ppc = 16
            focus = self.cursor
        canvas.clear_cells(0, 0, mw, mh)
        overlays = []
        if self.show_realms:
            overlays.append(self._realm_overlay())
        if self.show_weather:
            overlays.append(self._weather_overlay())
        plan = self.plan()
        self.painted.draw(canvas, game, rect, ppc, quests=quest_marks(game), look=self.cursor, focus=focus,
                          overlays=[o for o in overlays if o], route=plan.path if plan else None)
        canvas.hit(0, 0, mw, mh)

    def _realm_overlay(self):
        from realmwalker.world.factions import territory

        world = self.game.world
        if not world.factions:
            return None
        _, realm = territory(world)
        known = self.game.renown.known
        explored = self.game.player.explored
        key = ("realms", id(world), world.faction_version, int(explored.sum()), len(known))

        def make():
            """Four pixels per square: a light wash of each realm's colour and a firm line along its border.
            Realms you have not heard of are only outlined, faintly."""
            from PIL import Image as PImage, ImageFilter

            k = 4
            big = np.repeat(np.repeat(realm.T, k, axis=0), k, axis=1)
            seen = np.repeat(np.repeat(explored.T, k, axis=0), k, axis=1)
            a = np.zeros((big.shape[0], big.shape[1], 4), np.uint8)
            border = np.zeros(big.shape, bool)
            border[:-1, :] |= big[:-1, :] != big[1:, :]
            border[1:, :] |= big[:-1, :] != big[1:, :]
            border[:, :-1] |= big[:, :-1] != big[:, 1:]
            border[:, 1:] |= big[:, :-1] != big[:, 1:]
            for fid in np.unique(realm):
                if fid < 0:
                    continue
                f = world.factions.get(int(fid))
                if f is None:
                    continue
                mine = big == fid
                is_known = int(fid) in known
                show = mine & (seen | is_known)
                if is_known:
                    a[show, :3] = f.color
                    a[show, 3] = 60
                    a[show & border, 3] = 230
                else:
                    a[show & border, :3] = (150, 150, 156)
                    a[show & border, 3] = 110
            im = PImage.fromarray(a, "RGBA").filter(ImageFilter.GaussianBlur(0.6))
            return im

        return (key, make, 255)

    def _weather_overlay(self):
        from realmwalker.world.weather import weather_grid

        game = self.game
        key = game.world.time // 30
        if self._weather is None or self._weather[0] != key:
            self._weather = (key, weather_grid(game.world, game.tables, game.world.time))
        precip, temp, cloud = self._weather[1]

        def make():
            a = np.zeros((precip.shape[1], precip.shape[0], 4), np.uint8)
            grey = (cloud > 0.7) & (precip <= 0)
            rain = (precip > 0) & (temp > 0.5)
            snow = (precip > 0) & (temp <= 0.5)
            for mask, color, alpha in ((grey, (70, 70, 80), 90), (rain, (50, 90, 190), 150), (snow, (230, 232, 245), 160)):
                a[mask.T, :3] = color
                a[mask.T, 3] = alpha
            return a

        return (("weather", id(game.world), key), make, 255)

    def _tint_weather(self, grid, fg, bg, explored) -> None:
        """Rain shows blue, snow white and heavy cloud grey, over the land you have seen."""
        from realmwalker.world.weather import weather_grid

        game = self.game
        key = game.world.time // 30
        if self._weather is None or self._weather[0] != key:
            self._weather = (key, weather_grid(game.world, game.tables, game.world.time))
        precip, temp, cloud = (a[grid] for a in self._weather[1])
        bgf = bg.astype(np.float32)
        rain = (precip > 0) & (temp > 0.5)
        snow = (precip > 0) & (temp <= 0.5)
        grey = (cloud > 0.7) & (precip <= 0)
        for mask, color, strength in ((grey, (70, 70, 78), 0.35), (rain, (40, 70, 150), 0.45), (snow, (200, 200, 215), 0.5)):
            if mask.any():
                k = (strength + 0.4 * precip[mask])[:, None] if mask is not grey else strength
                bgf[mask] = bgf[mask] * (1 - k) + np.array(color, dtype=np.float32) * k
        bg[:] = bgf.astype(np.uint8)

    def _tint_realms(self, grid, bg, explored) -> None:
        """Each realm's lands in its own colour. Borders of realms you know of are common knowledge, so they show
        (faintly) even where you have not been; lands of realms you do not know show grey where you have."""
        from realmwalker.world.factions import territory

        world = self.game.world
        if not world.factions:
            return
        _, realm = territory(world)
        ids = realm[grid]
        known = self.game.renown.known
        bgf = bg.astype(np.float32)
        for fid in np.unique(ids):
            if fid < 0:
                continue
            f = world.factions.get(int(fid))
            if f is None:
                continue
            color = np.array(f.color if int(fid) in known else (90, 90, 96), dtype=np.float32)
            seen = (ids == fid) & explored
            bgf[seen] = bgf[seen] * 0.45 + color * 0.55
            if int(fid) in known:
                unseen = (ids == fid) & ~explored
                bgf[unseen] = bgf[unseen] * 0.7 + color * 0.3
        bg[:] = bgf.astype(np.uint8)

    def _side(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        title = "Travel: choose where" if self.travel_mode else self.title
        canvas.frame(x, y, w, h, title, double=True)
        ix, iw = x + 2, w - 4
        row = y + 2
        canvas.markup(ix, row, f"<place>{self.game.world.meta.name}</>", max_width=iw)
        row += 2
        text = describe_overworld(self.game, *self.cursor)
        row += canvas.wrapped(ix, row, text, iw, max_lines=max(3, h - 22)) + 1
        plan = self.plan()
        if plan is not None:
            canvas.wrapped(ix, row, f"<good>Journey:</> {self.game.describe_plan(plan)}.", iw, max_lines=3)
            row += 3
        keys = [("arrows", "move the cursor"), ("Shift+arrows", "move faster"), ("Enter", "travel there"),
                ("z", "zoom out / in"), ("w", "weather: " + ("shown" if self.show_weather else "hidden")),
                ("p", "realms: " + ("shown" if self.show_realms else "hidden")),
                ("@", "back to yourself"), ("Esc", "close")]
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
        elif ev.key == "w":
            self.show_weather = not self.show_weather
        elif ev.key == "p":
            self.show_realms = not self.show_realms
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
        if self.painted is not None:
            px, py = ev.px, ev.py
            if px < 0 and self.app.gfx is not None:
                px, py = (ev.x + 0.5) * self.app.gfx.cell_w, (ev.y + 0.5) * self.app.gfx.cell_h
            cell = self.painted.to_cell(px, py)
            tx, ty = cell if cell is not None else (-1, -1)
            if ev.kind == "wheel" and cell is not None:
                self.fit = ev.dy < 0
                return True
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
        return [KeyEvent(k) for k in ("up", "down", "left", "right", "z", "w", "p", "@", "escape")] + [KeyEvent("enter")]


def canvas_width_guard(app) -> int:
    return app.last_console_size[0]
