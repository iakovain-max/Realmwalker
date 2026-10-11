"""The World Map: the whole land as far as you know it, painted and shown at any zoom, in four views: the land
itself (its names written across it), its realms, its peoples and the weather, the last three each with a key in the
side panel. The mouse wheel zooms where the pointer is, dragging looks about, a click picks a place to read about;
Enter, a double click or the Travel button sets off there. Without pictures the map is drawn in letters."""

from __future__ import annotations

import math

import numpy as np

from realmwalker.game.describe import describe_overworld
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent, MouseEvent
from realmwalker.ui.map_render import PLAYER_FG, UNSEEN_BG, apply_light, camera
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.screens.game_screen import key_direction
from realmwalker.ui.widgets import Canvas

SIDE_W = 38
ZOOMS = (3, 6, 12, 24, 36, 48)  # screen pixels to a square: the map is painted at 12 a square, so these stay sharp
START_ZOOM = 24
VIEWS = ("land", "realms", "peoples", "weather")
VIEW_NAMES = {"land": "Land", "realms": "Realms", "peoples": "Peoples", "weather": "Weather"}
VIEW_KEYS = {"l": "land", "p": "realms", "c": "peoples", "w": "weather"}
GLIDE = 14.0  # how quickly a zoom settles (per second)
DRAG_PX = 5  # a press that moves further than this is a drag, not a click
OVERLAY_K = 4  # pixels a square of the realm and people pictures


class WorldMapScreen(Screen):
    title = "World Map"
    sound_open = "ui_map"
    key_sounds = False  # the keys move across the map

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
        self.view_mode = "land"
        self.fit = False  # letters only: squeeze the whole world onto the screen
        self.target: float | None = None  # pictures: the zoom (pixels a square) being glided to
        self.ppc: float | None = None  # ...and the zoom shown now
        self.cam: tuple[float, float] | None = None  # the square in the middle of the view
        self.anchor = None  # (world x, world y, screen x, screen y): held under the pointer while the zoom glides
        self.drag = None
        self.hover = None
        self.highlight = None  # a realm (faction id) or a people (culture id) picked in the key
        self.legend: list[tuple] = []  # (key, label, colour, tooltip) of the key of the view shown
        self.view = (0, 0, 1, 0, 0)  # letters: x0, y0 of map on screen, scale, first tile x, first tile y
        self.painted = None  # a WorldView when the map is drawn as a picture
        self.rect = None
        self._last = None
        self._weather: tuple[int, tuple] | None = None
        self._plan_key = None
        self._plan = None
        self._names_key = None
        self._names: list = []

    # The views, as the old flags (the bot and older tests ask these).
    @property
    def show_weather(self) -> bool:
        return self.view_mode == "weather"

    @property
    def show_realms(self) -> bool:
        return self.view_mode == "realms"

    @property
    def show_peoples(self) -> bool:
        return self.view_mode == "peoples"

    def set_view(self, mode: str) -> None:
        self.view_mode = "land" if self.view_mode == mode and mode != "land" else mode
        self.highlight = None

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
        self.legend = self._legend()
        if canvas.tiles:
            self._render_painted(canvas, mw, mh)
            self._side(canvas, mw, 0, SIDE_W, h)
            return
        self.painted = None
        self.rect = None
        self._render_letters(canvas, mw, mh)
        self._side(canvas, mw, 0, SIDE_W, h)

    def _render_letters(self, canvas: Canvas, mw: int, mh: int) -> None:
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
        elif self.show_peoples:
            self._tint_peoples(grid, bg, explored)
        stypes = self.game.tables.sites["settlement_types"]
        for s in world.settlements:
            if s.id not in p.known_settlements and not p.explored[s.x, s.y]:
                continue
            sx, sy = s.x // scale - x0, s.y // scale - y0
            if 0 <= sx < vw and 0 <= sy < vh:
                ch[sx, sy] = ord(stypes[s.kind]["glyph"])
                fg[sx, sy] = stypes[s.kind]["fg"]
        for wd in world.wonders:
            sx, sy = wd.x // scale - x0, wd.y // scale - y0
            if 0 <= sx < vw and 0 <= sy < vh and p.explored[wd.x, wd.y]:
                ch[sx, sy] = ord("*")
                fg[sx, sy] = (250, 220, 120)
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

    def levels(self, rect) -> list[float]:
        """The zooms there are: the whole world on the screen, then the sharp ones nearer in."""
        world = self.game.world
        whole = min(rect[2] / world.width, rect[3] / world.height)
        return [whole] + [z for z in ZOOMS if z > whole * 1.15]

    def _render_painted(self, canvas: Canvas, mw: int, mh: int) -> None:
        from realmwalker.ui.gfx.worldview import WorldView
        from realmwalker.ui.map_render import quest_marks

        game = self.game
        if self.painted is None:
            self.painted = WorldView()
            self.gs.world_view.ready(game)
            self.painted.share(self.gs.world_view)
        rect = tuple(int(v) for v in canvas.cell_rect(0, 0, mw, mh))
        self.rect = rect
        levels = self.levels(rect)
        if self.target is None:
            self.target = START_ZOOM if START_ZOOM in levels else levels[-1]
        if self.fit:
            self.target, self.fit = levels[0], False
        gfx = canvas.gfx
        now = gfx.now
        dt = 0.0 if self._last is None else min(0.1, max(0.0, now - self._last))
        self._last = now
        if self.ppc is None or not gfx.animate:
            self.ppc = self.target
        else:
            self.ppc += (self.target - self.ppc) * min(1.0, dt * GLIDE)
            if abs(self.ppc - self.target) <= 0.02 * self.target:
                self.ppc = self.target
        if self.cam is None:
            self.cam = (self.cursor[0] + 0.5, self.cursor[1] + 0.5)
        if self.anchor is not None:  # the point under the pointer stays under it while the zoom glides
            wx, wy, sx, sy = self.anchor
            mx, my = rect[0] + rect[2] / 2, rect[1] + rect[3] / 2
            self.cam = (wx - (sx - mx) / self.ppc, wy - (sy - my) / self.ppc)
            if self.ppc == self.target:
                self.anchor = None
        self.cam = self._clamp(self.cam)
        canvas.clear_cells(0, 0, mw, mh)
        overlay = self._overlay()
        plan = self.plan()
        self.painted.draw(canvas, game, rect, self.ppc, quests=quest_marks(game), look=self.cursor, hover=self.hover,
                          overlays=[overlay] if overlay else (), route=plan.path if plan else None, camera=self.cam,
                          land_names=self.view_mode in ("land", "weather"))
        if self.view_mode in ("realms", "peoples"):
            self._draw_view_names(canvas, rect)
        canvas.hit(0, 0, mw, mh)

    def _clamp(self, cam):
        if self.rect is None or not self.ppc:
            return cam
        world = self.game.world
        half_w, half_h = self.rect[2] / (2 * self.ppc), self.rect[3] / (2 * self.ppc)
        cx = world.width / 2 if world.width <= 2 * half_w else min(max(cam[0], half_w), world.width - half_w)
        cy = world.height / 2 if world.height <= 2 * half_h else min(max(cam[1], half_h), world.height - half_h)
        return (cx, cy)

    # ------------------------------------------------------------------ the views
    def _overlay(self):
        if self.view_mode == "realms":
            return self._realm_overlay()
        if self.view_mode == "peoples":
            return self._people_overlay()
        if self.view_mode == "weather":
            return self._weather_overlay()
        return None

    def _fill_picture(self, ids: np.ndarray, colour_of, seen: np.ndarray, *, under: np.ndarray | None = None,
                      under_colour=None, picked=None) -> np.ndarray:
        """A picture of territories: each filled in its colour, a strong line round it, the land under another's
        rule (a vassal's, `under`) striped in that ruler's colour; with one picked, the rest are dimmed."""
        k = OVERLAY_K
        big = np.repeat(np.repeat(ids.T, k, axis=0), k, axis=1)
        shown = np.repeat(np.repeat(seen.T, k, axis=0), k, axis=1) & (big >= 0)
        a = np.zeros((big.shape[0], big.shape[1], 4), np.uint8)
        border = np.zeros(big.shape, bool)
        border[:-1, :] |= big[:-1, :] != big[1:, :]
        border[1:, :] |= big[:-1, :] != big[1:, :]
        border[:, :-1] |= big[:, :-1] != big[:, 1:]
        border[:, 1:] |= big[:, :-1] != big[:, 1:]
        ys, xs = np.mgrid[0:big.shape[0], 0:big.shape[1]]
        stripes = (xs + ys) % 8 < 3
        for i in np.unique(big[shown]):
            colour = colour_of(int(i))
            if colour is None:
                continue
            mine = shown & (big == i)
            dim = picked is not None and int(i) != picked
            a[mine, :3] = colour
            a[mine, 3] = 40 if dim else 105
            a[mine & border, 3] = 90 if dim else 235
        if under is not None and under_colour is not None:
            sub = np.repeat(np.repeat(under.T, k, axis=0), k, axis=1)
            for j in np.unique(sub[shown & (sub >= 0)]):
                colour = under_colour(int(j))
                if colour is None:
                    continue
                band = shown & (sub == j) & stripes
                a[band, :3] = colour
                a[band, 3] = 150
        return a

    def _realm_overlay(self):
        from realmwalker.world.factions import territory

        world = self.game.world
        if not world.factions:
            return None
        owner, realm = territory(world)
        known = self.game.renown.known
        explored = self.game.player.explored
        key = ("realms", id(world), world.faction_version, int(explored.sum()), len(known), self.highlight)

        def colour(fid):
            f = world.factions.get(fid)
            if f is None:
                return None
            return tuple(f.color) if fid in known else (150, 150, 156)

        def vassal_colour(fid):
            f = world.factions.get(fid)
            return tuple(f.color) if f is not None and fid in known else None

        def make():
            # Lands of realms you know of are common knowledge, so they show where you have not been.
            seen = explored | np.isin(realm, list(known))
            vassal = np.where(owner != realm, owner, -1)
            return self._fill_picture(realm, colour, seen, under=vassal, under_colour=vassal_colour,
                                      picked=self.highlight)

        return (key, make, 255, True)

    def _people_overlay(self):
        from realmwalker.world.model import NO_CULTURE

        world = self.game.world
        C = self.game.tables.cultures
        explored = self.game.player.explored
        key = ("peoples", id(world), int(explored.sum()), self.highlight, tuple(world.culture_ids))
        ids = np.where(world.culture == NO_CULTURE, -1, world.culture.astype(np.int32))
        picked = world.culture_ids.index(self.highlight) if self.highlight in world.culture_ids else None

        def colour(i):
            cid = world.culture_ids[i] if 0 <= i < len(world.culture_ids) else None
            return tuple(C.color(cid)) if cid else None

        def make():
            return self._fill_picture(ids, colour, explored, picked=picked)

        return (key, make, 255, True)

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

    def _view_names(self) -> list[tuple]:
        """(x, y, squares, name, colour) for each realm or people shown: written across the middle of its land."""
        world = self.game.world
        explored = self.game.player.explored
        key = (self.view_mode, world.faction_version, int(explored.sum()), len(self.game.renown.known))
        if key == self._names_key:
            return self._names
        out = []
        if self.view_mode == "realms" and world.factions:
            from realmwalker.world.factions import territory

            _, realm = territory(world)
            known = self.game.renown.known
            for fid in np.unique(realm[realm >= 0]):
                f = world.factions.get(int(fid))
                if f is None or int(fid) not in known:
                    continue
                spot = _middle(realm == fid)
                if spot is not None:
                    out.append((*spot, _short(f.name), tuple(f.color)))
        elif self.view_mode == "peoples":
            C = self.game.tables.cultures
            for i, cid in enumerate(world.culture_ids):
                mask = (world.culture == i) & explored
                spot = _middle(mask)
                if spot is not None:
                    out.append((*spot, C.people(world, cid), tuple(C.color(cid))))
        self._names_key, self._names = key, out
        return out

    def _draw_view_names(self, canvas: Canvas, rect) -> None:
        from realmwalker.ui.gfx import typefaces
        from realmwalker.ui.gfx.scene import Clip, Text

        ppc = self.ppc or 12
        ox, oy = self.painted.origin
        boxes = []
        canvas.under(Clip(rect))
        for x, y, count, name, colour in sorted(self._view_names(), key=lambda t: -t[2]):
            size = int(max(11, min(30, math.sqrt(count) * ppc * 0.09)))
            if math.sqrt(count) * ppc < 40:
                continue
            text = name[:1].upper() + name[1:]
            tw, th = typefaces.measure(text, "heading", size)
            cx, cy = ox + (x + 0.5) * ppc, oy + (y + 0.5) * ppc
            box = (cx - tw / 2, cy - th / 2, tw, th)
            if any(b[0] < box[0] + box[2] and box[0] < b[0] + b[2] and b[1] < box[1] + box[3] and box[1] < b[1] + b[3]
                   for b in boxes):
                continue
            boxes.append(box)
            ink = tuple(int(c * 0.45) for c in colour) + (255,)
            canvas.under(Text(cx, cy, text, "heading", size, ink, anchor="mm", shadow=False,
                              outline=(236, 224, 196, 210)))
        canvas.under(Clip(None))

    def _legend(self) -> list[tuple]:
        """The key of the view shown: (key, label, colour, tooltip)."""
        world = self.game.world
        game = self.game
        if self.view_mode == "realms" and world.factions:
            from realmwalker.game.reputation import standing_markup
            from realmwalker.world.factions import territory

            _, realm = territory(world)
            counts = {int(f): int(n) for f, n in zip(*np.unique(realm[realm >= 0], return_counts=True))}
            out = []
            for fid, n in sorted(counts.items(), key=lambda kv: -kv[1]):
                f = world.factions.get(fid)
                if f is None or fid not in game.renown.known:
                    continue
                ruler = world.figures.get(f.leader) if f.leader >= 0 else None
                who = f"{ruler.title} {ruler.name}".strip() if ruler is not None else "no one"
                wars = [war for war in world.wars if war.get("active") and fid in
                        (war.get("attacker"), war.get("defender"))]
                tip = f"{_short(f.name)}: ruled by {who}. Your standing: {markup.plain(standing_markup(game, fid))}." + \
                    (f" At war: {wars[0].get('name', 'a war')}." if wars else "")
                out.append((fid, _short(f.name), tuple(f.color), tip))
            return out
        if self.view_mode == "peoples":
            C = game.tables.cultures
            from realmwalker.world.model import NO_CULTURE

            land = world.culture != NO_CULTURE
            counts = np.bincount(world.culture[land], minlength=len(world.culture_ids))
            out = []
            for i in np.argsort(-counts):
                if i >= len(world.culture_ids) or counts[i] == 0:
                    continue
                cid = world.culture_ids[int(i)]
                like = C.get(cid).get("like", "")
                tip = f"{C.people(world, cid)} ({C.adjective(world, cid)} folk{', like the ' + like if like else ''}). " \
                      f"{C.about(cid)}"
                out.append((cid, C.people(world, cid), tuple(C.color(cid)), tip))
            return out
        return []

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
            if self.highlight is not None and int(fid) != self.highlight:
                color = color * 0.4 + 40
            seen = (ids == fid) & explored
            bgf[seen] = bgf[seen] * 0.45 + color * 0.55
            if int(fid) in known:
                unseen = (ids == fid) & ~explored
                bgf[unseen] = bgf[unseen] * 0.7 + color * 0.3
        bg[:] = bgf.astype(np.uint8)

    def _tint_peoples(self, grid, bg, explored) -> None:
        """Each people's lands in its colour, where you have been."""
        from realmwalker.world.model import NO_CULTURE

        world = self.game.world
        C = self.game.tables.cultures
        ids = world.culture[grid]
        bgf = bg.astype(np.float32)
        for i in np.unique(ids):
            if i == NO_CULTURE or i >= len(world.culture_ids):
                continue
            cid = world.culture_ids[int(i)]
            color = np.array(C.color(cid), dtype=np.float32)
            if self.highlight is not None and cid != self.highlight:
                color = color * 0.4 + 40
            seen = (ids == i) & explored
            bgf[seen] = bgf[seen] * 0.45 + color * 0.55
        bg[:] = bgf.astype(np.uint8)

    # ------------------------------------------------------------------ the side panel
    def _side(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        title = "Travel: choose where" if self.travel_mode else self.title
        canvas.frame(x, y, w, h, title, double=True)
        ix, iw = x + 2, w - 4
        row = y + 2
        canvas.markup(ix, row, f"<place>{markup.escape(self.game.world.meta.name)}</>", max_width=iw)
        row += 1
        bx = ix
        for mode in VIEWS:  # the views, as buttons
            label = VIEW_NAMES[mode]
            chosen = mode == self.view_mode
            text = f"[{label}]" if chosen else f" {label} "
            if bx + len(text) > ix + iw:
                row += 1
                bx = ix
            over = canvas.hit(bx, row, len(text), 1, lambda m=mode: self.set_view(m),
                              tooltip=f"{label} view ({next(k for k, v in VIEW_KEYS.items() if v == mode)})")
            fg = colors.SELECT_FG if chosen else (colors.FG if over else colors.DIM)
            bx = canvas.text(bx, row, text, fg, colors.HILITE_BG if chosen else None) + 1
        row += 2
        keys_h = 6
        legend = self.legend
        legend_h = min(len(legend), max(0, (h - row - keys_h - 10) // 2)) if legend else 0
        text = describe_overworld(self.game, *self.cursor)
        room = max(3, h - row - keys_h - (legend_h + 2 if legend_h else 0) - 5)
        row += canvas.wrapped(ix, row, text, iw, max_lines=room) + 1
        plan = self.plan()
        if plan is not None:
            row += canvas.wrapped(ix, row, f"<good>Journey:</> {self.game.describe_plan(plan)}.", iw, max_lines=3)
            canvas.button(ix, row, "Travel there", self._travel, hotkey="Enter")
            row += 2
        if legend_h:
            canvas.text(ix, row, "Realms you know" if self.view_mode == "realms" else "The peoples", colors.TITLE)
            row += 1
            for key, label, colour, tip in legend[:legend_h]:
                chosen = self.highlight == key
                canvas.fill(ix, row, 2, 1, colour)
                over = canvas.hit(ix, row, iw, 1, lambda k=key: self._pick(k), tooltip=tip)
                fg = colors.SELECT_FG if chosen else (colors.FG if over else colors.DIM)
                canvas.text(ix + 3, row, label, fg, colors.HILITE_BG if chosen else None, max_width=iw - 3)
                row += 1
            if len(legend) > legend_h:
                canvas.text(ix + 3, row, f"and {len(legend) - legend_h} more", colors.FAINT)
        keys = [("wheel / drag", "zoom / look about"), ("click, 2× click", "choose / travel"),
                ("arrows, Enter", "cursor / travel"), ("l p c w", "land realms peoples weather"),
                ("+ - z  @  Esc", "zoom · yourself · close")]
        ky = h - len(keys) - 1
        for key, what in keys:
            canvas.markup(ix, ky, f"<loot>{key:>15}</> <dim>{what}</>", max_width=iw)
            ky += 1

    def _pick(self, key) -> None:
        self.highlight = None if self.highlight == key else key

    # ------------------------------------------------------------------ input
    def _move_cursor(self, dx: int, dy: int, fast: bool = False) -> None:
        step = (self.view[2] if self.fit else 1) * (8 if fast else 1)
        world = self.game.world
        x = max(0, min(world.width - 1, self.cursor[0] + dx * step))
        y = max(0, min(world.height - 1, self.cursor[1] + dy * step))
        self.cursor = (x, y)
        self._follow()

    def _follow(self) -> None:
        """Keep the cursor in sight: when it nears the edge of the view, the view moves."""
        if self.rect is None or self.cam is None or not self.ppc:
            return
        half_w, half_h = self.rect[2] / (2 * self.ppc), self.rect[3] / (2 * self.ppc)
        mx, my = min(3.0, half_w * 0.4), min(3.0, half_h * 0.4)
        cx, cy = self.cam
        x, y = self.cursor[0] + 0.5, self.cursor[1] + 0.5
        if x < cx - half_w + mx:
            cx = x + half_w - mx
        elif x > cx + half_w - mx:
            cx = x - half_w + mx
        if y < cy - half_h + my:
            cy = y + half_h - my
        elif y > cy + half_h - my:
            cy = y - half_h + my
        self.cam = self._clamp((cx, cy))
        self.anchor = None

    def zoom(self, step: int, at: tuple[float, float] | None = None) -> None:
        """One zoom level in (1) or out (-1), keeping the point `at` (screen pixels; the cursor if None) still."""
        if self.rect is None:
            self.fit = step < 0 if step else not self.fit
            return
        levels = self.levels(self.rect)
        cur = self.target or START_ZOOM
        if step > 0:
            nxt = next((z for z in levels if z > cur * 1.01), cur)
        else:
            nxt = next((z for z in reversed(levels) if z < cur * 0.99), cur)
        if nxt == cur:
            return
        ppc = self.ppc or cur
        mx, my = self.rect[0] + self.rect[2] / 2, self.rect[1] + self.rect[3] / 2
        if at is None:
            wx, wy = self.cursor[0] + 0.5, self.cursor[1] + 0.5
            sx, sy = mx + (wx - self.cam[0]) * ppc, my + (wy - self.cam[1]) * ppc
        else:
            sx, sy = at
            wx, wy = self.cam[0] + (sx - mx) / ppc, self.cam[1] + (sy - my) / ppc
        self.anchor = (wx, wy, sx, sy)
        self.target = nxt

    def _home(self) -> None:
        p = self.game.player
        self.cursor = (p.x, p.y)
        self.cam = (p.x + 0.5, p.y + 0.5)
        self.anchor = None

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
        elif ev.key in ("+", "="):
            self.zoom(1)
        elif ev.key == "-":
            self.zoom(-1)
        elif ev.key in ("z", "Z"):
            if self.rect is None:
                self.fit = not self.fit
            else:
                levels = self.levels(self.rect)
                self.anchor = None
                self.target = START_ZOOM if (self.target or 0) <= levels[0] * 1.01 else levels[0]
        elif ev.key in VIEW_KEYS:
            self.set_view(VIEW_KEYS[ev.key])
        elif ev.key in ("tab", "v"):
            self.set_view(VIEWS[(VIEWS.index(self.view_mode) + 1) % len(VIEWS)])
        elif ev.key in ("@", "home"):
            self._home()
        elif ev.key in ("escape", "m", "t"):
            self.close()
        else:
            return False
        return True

    def _pixels(self, ev: MouseEvent) -> tuple[float, float]:
        px, py = ev.px, ev.py
        if px < 0 and self.app.gfx is not None:
            px, py = (ev.x + 0.5) * self.app.gfx.cell_w, (ev.y + 0.5) * self.app.gfx.cell_h
        return px, py

    def handle_mouse(self, ev: MouseEvent) -> bool:
        if self.painted is None or self.rect is None:
            return self._mouse_letters(ev)
        world = self.game.world
        px, py = self._pixels(ev)
        x0, y0, w, h = self.rect
        inside = x0 <= px < x0 + w and y0 <= py < y0 + h
        if ev.kind == "release":
            if self.drag is None:
                return False
            moved, self.drag = self.drag["moved"], None
            if not moved and inside:
                cell = self.painted.to_cell(px, py)
                if cell is not None and world.in_bounds(*cell):
                    self.cursor = cell
            return True
        if ev.kind == "move" and self.drag is not None:
            dx, dy = px - self.drag["px"], py - self.drag["py"]
            if self.drag["moved"] or abs(dx) + abs(dy) > DRAG_PX:
                self.drag["moved"] = True
                cx, cy = self.drag["cam"]
                self.cam = self._clamp((cx - dx / self.ppc, cy - dy / self.ppc))
                self.anchor = None
            return True
        if not inside:
            if ev.kind == "move":
                self.hover = None
            return False
        cell = self.painted.to_cell(px, py)
        if cell is not None and not world.in_bounds(*cell):
            cell = None
        if ev.kind == "wheel":
            self.zoom(1 if ev.dy > 0 else -1, at=(px, py))
            return True
        if ev.kind == "click":
            if ev.button == "left" and ev.clicks >= 2 and cell is not None:
                self.drag = None
                self.cursor = cell
                self._travel()
                return True
            if ev.button == "left":
                self.drag = {"px": px, "py": py, "cam": self.cam, "moved": False}
                return True
            if cell is not None:
                self.cursor = cell
            return True
        if ev.kind == "move":
            self.hover = cell
            return True
        return False

    def _mouse_letters(self, ev: MouseEvent) -> bool:
        ox, oy, scale, x0, y0 = self.view
        tx, ty = (ev.x - ox + x0) * scale + scale // 2, (ev.y - oy + y0) * scale + scale // 2
        world = self.game.world
        if ev.x >= canvas_width_guard(self.app) - SIDE_W or not world.in_bounds(tx, ty):
            return False
        if ev.kind == "wheel":
            self.fit = ev.dy < 0
            return True
        if ev.kind == "click":
            self.cursor = (tx, ty)
            if ev.button == "left" and ev.clicks >= 2:
                self._travel()
            return True
        if ev.kind == "move":
            self.hover = (tx, ty)
        return False

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("up", "down", "left", "right", "z", "w", "p", "c", "l", "+", "-", "@",
                                      "escape")] + [KeyEvent("enter")]


def _middle(mask: np.ndarray):
    """(x, y, count) of a square well inside the biggest piece of mask, or None."""
    from realmwalker.world import hydrology

    if not mask.any():
        return None
    labels, sizes = hydrology.label_components(mask)
    if not sizes:
        return None
    i = int(np.argmax(sizes))
    cells = np.argwhere(labels == i)
    centre = cells.mean(axis=0)
    x, y = cells[np.argmin(((cells - centre) ** 2).sum(axis=1))]
    return int(x), int(y), int(sizes[i])


def _short(name: str) -> str:
    """'the Kingdom of Ashmere' as written across its lands: 'Kingdom of Ashmere'."""
    return name[4:] if name.startswith("the ") else name


def canvas_width_guard(app) -> int:
    return app.last_console_size[0]
