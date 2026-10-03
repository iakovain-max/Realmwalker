"""The overworld as a painted map (paint.py), with the towns and ruins on it, names, fog over country you have not
seen, the work you have in hand, the road you are on, and you.
"""

from __future__ import annotations

import math

import numpy as np

from realmwalker.ui.gfx import dolls
from realmwalker.ui.gfx.paint import ChunkCache, WorldPainter
from realmwalker.ui.gfx.scene import Clip, Image, Lines, Rect, Text, tile_batch

STEP_SECONDS = 0.16
NIGHT_TINT = (96, 108, 150)
FOG_RGB = (14, 13, 16)


def daylight_tint(light: float) -> tuple[int, int, int]:
    if light >= 0.95:
        return (255, 255, 255)
    if light >= 0.45:
        t = (light - 0.45) / 0.5
        return tuple(int(a + (255 - a) * t) for a in (238, 196, 160))
    t = max(0.0, light / 0.45)
    return tuple(int(n + (d - n) * t) for n, d in zip(NIGHT_TINT, (238, 196, 160)))


class WorldView:
    def __init__(self) -> None:
        self.world = None
        self.painter: WorldPainter | None = None
        self.cache: ChunkCache | None = None
        self.cam: tuple[float, float] | None = None
        self.cam_key = None
        self.glide = None  # [fx, fy, tx, ty, t0]
        self.last_t = 0.0
        self.origin = (0.0, 0.0)
        self.ppc = 24
        self.rect = (0, 0, 0, 0)
        self._fog_key = None

    def close(self) -> None:
        if self.cache is not None and not getattr(self, "shared", False):
            self.cache.close()

    def share(self, other: "WorldView") -> None:
        """Use another view's painter and painted pieces (the world map borrows the game screen's)."""
        self.world, self.painter, self.cache = other.world, other.painter, other.cache
        self.shared = True

    def ready(self, game) -> None:
        if self.world is not game.world:
            self.close()
            self.world = game.world
            self.painter = WorldPainter(game.world, game.tables)
            self.cache = ChunkCache(self.painter)
            self.cam = None
            self.glide = None

    # ------------------------------------------------------------------ geometry
    def to_cell(self, px: float, py: float) -> tuple[int, int] | None:
        x0, y0, w, h = self.rect
        if not (x0 <= px < x0 + w and y0 <= py < y0 + h):
            return None
        return int(math.floor((px - self.origin[0]) / self.ppc)), int(math.floor((py - self.origin[1]) / self.ppc))

    def cell_px(self, x: float, y: float) -> tuple[float, float]:
        return self.origin[0] + x * self.ppc, self.origin[1] + y * self.ppc

    def moving(self, now: float) -> bool:
        g = self.glide
        return g is not None and now - g[4] < STEP_SECONDS and (g[0], g[1]) != (g[2], g[3])

    def _player_pos(self, x: int, y: int, now: float, animate: bool) -> tuple[float, float]:
        g = self.glide
        if g is None or not animate:
            self.glide = [x, y, x, y, now]
            return float(x), float(y)
        if (g[2], g[3]) != (x, y):
            cx, cy = self._at(g, now)
            if abs(cx - x) > 3 or abs(cy - y) > 3:
                self.glide = [x, y, x, y, now]
                return float(x), float(y)
            self.glide = g = [cx, cy, x, y, now]
        return self._at(g, now)

    @staticmethod
    def _at(g, now: float) -> tuple[float, float]:
        t = min(1.0, max(0.0, (now - g[4]) / STEP_SECONDS))
        t = t * t * (3 - 2 * t)
        return g[0] + (g[2] - g[0]) * t, g[1] + (g[3] - g[1]) * t

    # ------------------------------------------------------------------ drawing
    def draw(self, canvas, game, rect_px, ppc: int, *, quests=(), look=None, hover=None, focus=None,
             overlays=(), route=None, figure: bool = True) -> None:
        self.ready(game)
        gfx = canvas.gfx
        now = gfx.now
        world = game.world
        p = game.player
        X0, Y0, VW, VH = rect_px
        self.rect = rect_px
        if ppc != self.ppc:
            self.cam = None
        self.ppc = ppc
        pos = self._player_pos(p.x, p.y, now, gfx.animate)
        target = (pos[0] + 0.5, pos[1] + 0.5) if focus is None else (focus[0] + 0.5, focus[1] + 0.5)
        dt = max(0.0, now - self.last_t)
        self.last_t = now
        if self.cam is None or not gfx.animate:
            self.cam = target
        else:
            k = min(1.0, dt * 8.0)
            self.cam = (self.cam[0] + (target[0] - self.cam[0]) * k, self.cam[1] + (target[1] - self.cam[1]) * k)
            if abs(self.cam[0] - target[0]) > 15 or abs(self.cam[1] - target[1]) > 15:
                self.cam = target
        half_w, half_h = VW / (2 * ppc), VH / (2 * ppc)
        cx, cy = self.cam
        cx = world.width / 2 if world.width <= 2 * half_w else min(max(cx, half_w), world.width - half_w)
        cy = world.height / 2 if world.height <= 2 * half_h else min(max(cy, half_h), world.height - half_h)
        ox = round(X0 + VW / 2 - cx * ppc)
        oy = round(Y0 + VH / 2 - cy * ppc)
        self.origin = (ox, oy)
        tint = daylight_tint(float(game.light))
        canvas.under(Clip(rect_px), Rect(X0, Y0, VW, VH, (*FOG_RGB, 255)))
        # The painted country, chunk by chunk.
        n = self.painter.chunk_cells(ppc)
        cx0 = max(0, int((X0 - ox) // (n * ppc)))
        cy0 = max(0, int((Y0 - oy) // (n * ppc)))
        cx1 = min((world.width - 1) // n, int((X0 + VW - ox) // (n * ppc)))
        cy1 = min((world.height - 1) // n, int((Y0 + VH - oy) // (n * ppc)))
        wanted, missing = [], 0
        for gy in range(cy0 - 1, cy1 + 2):
            for gx in range(cx0 - 1, cx1 + 2):
                if 0 <= gx <= (world.width - 1) // n and 0 <= gy <= (world.height - 1) // n:
                    wanted.append((ppc, gx, gy))
        visible = [(ppc, gx, gy) for gx in range(cx0, cx1 + 1) for gy in range(cy0, cy1 + 1)]
        for key in visible:
            im = self.cache.get(key)
            if im is None and missing < 2:
                im = self.cache.paint_now(key)  # what you are looking at cannot wait
                missing += 1
            if im is None:
                continue
            _, gx, gy = key
            canvas.under(Image(("chunk", id(world), *key), lambda im=im: im,
                               (ox + gx * n * ppc, oy + gy * n * ppc, im.width, im.height), rgba=(*tint, 255), smooth=False))
        self.cache.want([k for k in wanted if self.cache.get(k) is None])
        # Fog over what you have not seen: a soft edge, from a picture one pixel per square.
        explored = p.explored
        for key, make, alpha, *sharp in overlays:  # realms (in map pixels, sharp), weather (a pixel a square, soft)
            canvas.under(Image(key, make, (ox, oy, world.width * ppc, world.height * ppc), rgba=(255, 255, 255, alpha),
                               smooth=not (sharp and sharp[0])))
        fog_key = ("fog", id(world), int(explored.sum()))
        canvas.under(Image(fog_key, lambda: _fog_image(explored), (ox, oy, world.width * ppc, world.height * ppc)))
        # Places.
        sp = game.tables.sprites["world"]
        stypes = sp["settlements"]
        names, dst, cols = [], [], []
        labels = []
        light = tint[0] / 255
        for s in world.settlements:
            known = s.id in p.known_settlements
            if not explored[s.x, s.y] and not known:
                continue
            sx, sy = self.cell_px(s.x, s.y)
            if sx < X0 - 3 * ppc or sx > X0 + VW + 3 * ppc or sy < Y0 - 3 * ppc or sy > Y0 + VH + 3 * ppc:
                continue
            size = ppc * {"hamlet": 1.1, "village": 1.35, "town": 1.6, "city": 2.0}.get(s.kind, 1.5)
            names.append(stypes.get(s.kind, "map/village"))
            dst.append((sx + ppc / 2 - size / 2, sy + ppc - size * 0.92, size, size))
            a = 1.0 if explored[s.x, s.y] else 0.6
            cols.append((light, light, min(1.0, light * 1.05), a))
            if ppc >= 12:
                labels.append((sx + ppc / 2, sy + ppc + 1, s.name, s.kind, a))
        for site in world.sites:
            if not explored[site.x, site.y]:
                continue
            sx, sy = self.cell_px(site.x, site.y)
            if sx < X0 - 2 * ppc or sx > X0 + VW + 2 * ppc or sy < Y0 - 2 * ppc or sy > Y0 + VH + 2 * ppc:
                continue
            size = ppc * 1.1
            names.append(sp["sites"].get(site.kind, "map/ruin"))
            dst.append((sx + ppc / 2 - size / 2, sy + ppc - size * 0.95, size, size))
            cols.append((light, light, light, 1.0))
        if names:
            canvas.under(*tile_batch(gfx.atlas, names, np.array(dst, np.float32), np.array(cols, np.float32)))
        for lx, ly, name, kind, a in labels:
            big = kind in ("town", "city", "hold")
            size = max(11, int(ppc * (0.62 if big else 0.5)))
            canvas.under(Text(lx, ly, name, "heading" if big else "heading_light", size,
                              (236, 222, 186, int(255 * a)), anchor="mt", shadow=False, outline=True))
        # Work in hand: a slow pulse of lamplight.
        pulse = 0.5 + 0.5 * math.sin(now * 2.6) if gfx.ambient else 0.7
        for qx, qy in quests:
            sx, sy = self.cell_px(qx, qy)
            r = ppc * (1.3 + 0.25 * pulse)
            canvas.under(Image("ring", _ring_image, (sx + ppc / 2 - r, sy + ppc / 2 - r, 2 * r, 2 * r),
                               rgba=(255, 200, 90, int(140 + 90 * pulse))))
        # The road ahead.
        path = route if route is not None else (game.travel.path if game.travel is not None else None)
        if path:
            pts = [(pos[0] + 0.5, pos[1] + 0.5)] + [(x + 0.5, y + 0.5) for x, y in path]
            line = [(ox + x * ppc, oy + y * ppc) for x, y in pts]
            canvas.under(Lines(line, max(2, ppc * 0.12), (30, 20, 10, 200), dash=(ppc * 0.45, ppc * 0.3)))
            canvas.under(Lines(line, max(1, ppc * 0.07), (250, 214, 120, 235), dash=(ppc * 0.45, ppc * 0.3)))
            dx, dy = path[-1]
            fx, fy = self.cell_px(dx, dy)
            canvas.under(Image("flag", _flag_image, (fx + ppc * 0.3, fy - ppc * 0.6, ppc * 0.9, ppc * 1.2)))
        # You.
        if figure:
            self._figure(canvas, game, pos, 64 if ppc >= 40 else 32)
        for spot, rgba in ((hover, (255, 255, 255, 110)), (look, (255, 214, 110, 235))):
            if spot is not None:
                sx, sy = self.cell_px(*spot)
                canvas.under(Rect(sx, sy, ppc, ppc, rgba, line=2))
        canvas.under(Clip(None))

    def _figure(self, canvas, game, pos, size) -> None:
        gfx = canvas.gfx
        ppc = self.ppc
        px_, py_ = self.cell_px(*pos)
        canvas.under(Image("shadow_w", _shadow_image, (px_ + ppc / 2 - size * 0.3, py_ + ppc * 0.85 - size * 0.08,
                                                        size * 0.6, size * 0.2), rgba=(255, 255, 255, 160)))
        cmd = dolls.draw(gfx.atlas, dolls.character(game.leader, game.tables, atlas=gfx.atlas),
                         px_ + ppc / 2 - size / 2, py_ + ppc * 0.95 - size, size)
        if cmd is not None:
            canvas.under(cmd)


def _fog_image(explored: np.ndarray):
    """Fog at four pixels per square, softened, so its edge is a cloud and not a staircase."""
    from PIL import Image as PImage, ImageFilter

    k = 4
    m = np.where(explored.T, 0, 255).astype(np.uint8)
    big = PImage.fromarray(m, "L").resize((m.shape[1] * k, m.shape[0] * k), PImage.NEAREST)
    big = big.filter(ImageFilter.GaussianBlur(k * 0.9))
    a = np.zeros((big.height, big.width, 4), np.uint8)
    a[..., 0], a[..., 1], a[..., 2] = FOG_RGB
    a[..., 3] = np.asarray(big)
    return a


def _ring_image():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([10, 10, 86, 86], outline=(255, 255, 255, 255), width=5)
    im = im.filter(ImageFilter.GaussianBlur(2.5))
    d = ImageDraw.Draw(im)
    d.ellipse([14, 14, 82, 82], outline=(255, 255, 255, 220), width=2)
    return im


def _flag_image():
    from PIL import Image as PImage, ImageDraw

    im = PImage.new("RGBA", (36, 48), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line([(6, 2), (6, 46)], fill=(40, 30, 20, 255), width=3)
    d.polygon([(8, 4), (32, 10), (8, 18)], fill=(200, 60, 44, 255), outline=(40, 20, 14, 255))
    return im


def _shadow_image():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (64, 24), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([6, 4, 58, 20], fill=(0, 0, 0, 200))
    return im.filter(ImageFilter.GaussianBlur(3))
