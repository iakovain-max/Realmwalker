"""Signs on the world map for marks (Expansion 6 B.8, docs/ADVENTURES.md §8.16): what a settlement is going through,
seen from afar over its mark - smoke rising from a burning, burned or sacked town (darker, and lit from below at night,
while it burns), a ring of tents and banners round a besieged one (in the besieger's colours; a beset one's in the
horde's), the black flag of plague, a dragon's shadow circling over a town that pays it tribute, lanterns strung for a
festival, a statue beside a town that keeps a memorial. Drawn every frame from the marks (world/marks.py) in a handful
of small pictures made once; nothing is painted into the map's chunks, and nothing here changes the game. Still with
Animations "calm" or "off".

    signed(s)                                      the marks of s that show on the map, strongest first
    under(canvas, game, places, now, tint)         what stands behind the towns' marks (the far tents, a fire's glow)
    over(canvas, game, places, now, tint)          what stands before them (smoke, flags, the near tents, lanterns)

`places` is [(settlement, x, y, size, alpha)]: the mark's rectangle on the screen (x, y its top left corner, size its
side in pixels), as WorldView.draw lays it, and how clearly it is seen (1 explored, 0.6 only known).
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from realmwalker.ui.gfx.scene import Image, Lines

SMOKE = ("burning", "sacked", "burned")  # one column of smoke a town, the strongest of these
SHOWN = SMOKE + ("siege", "beset", "plague", "tribute", "festival", "memorial")
BESET_RGB = (120, 34, 30)  # a horde has no realm's colours: its banners are old blood
SMALLEST = 24.0  # pixels: signs round a smaller mark are laid as round one this big
LANTERNS = ((236, 92, 60), (248, 204, 90), (120, 200, 120), (236, 140, 70), (150, 170, 240))

# How each column of smoke looks: puffs at once, rate (columns a second), colour, opacity, how high and how wide.
SMOKE_LOOK = {
    "burning": (7, 0.32, (58, 52, 50), 225, 2.0, 0.55),
    "sacked": (6, 0.22, (92, 88, 84), 190, 1.6, 0.45),
    "burned": (4, 0.14, (124, 120, 116), 185, 1.2, 0.35),
}


def signed(s) -> list[str]:
    st = s.status
    out = [m for m in SHOWN if st.get(m) is not None and st.get(m) is not False]
    smoke = [m for m in out if m in SMOKE]
    return [m for m in out if m not in SMOKE or m == (smoke[0] if smoke else None)]


def _seed(s) -> float:
    return (int(s.id) * 0.618034) % 1.0


def _lit(tint, a: float, rgb=(255, 255, 255), alpha: int = 255) -> tuple:
    """A thing on the land, as light as the hour, as clear as it is seen."""
    return (int(rgb[0] * tint[0] / 255), int(rgb[1] * tint[1] / 255), int(rgb[2] * tint[2] / 255), int(alpha * a))


def _frame(x: float, y: float, size: float) -> tuple[float, float, float]:
    """The rectangle the signs are laid in: the mark's, but never smaller than SMALLEST, so a hamlet's smoke is seen
    (kept on the mark's middle and its foot)."""
    if size >= SMALLEST:
        return x, y, size
    cx, foot = x + size / 2, y + size * 0.92
    return cx - SMALLEST / 2, foot - SMALLEST * 0.92, SMALLEST


def _ring(s, x, y, size, behind: bool):
    """The tents round a town: (index, cx, ground y, depth) for those behind (or before) its mark."""
    n = 8 if s.kind in ("town", "city", "hold") or getattr(s, "great", False) else 6
    cx, cy = x + size / 2, y + size * 0.78
    rx, ry = size * 0.78, size * 0.34
    start = _seed(s) * math.tau
    for i in range(n):
        a = start + math.tau * i / n
        depth = math.sin(a)
        if (depth < 0) == behind:
            yield i, cx + math.cos(a) * rx, cy + depth * ry, depth


def _camp(canvas, factions, s, x, y, size, a, tint, behind: bool, mark: str) -> None:
    if mark == "siege":
        rec = s.status.get("siege")
        fid = rec.get("by") if isinstance(rec, dict) else None
        f = factions.get(fid) if isinstance(fid, int) else None  # (world.factions: id -> Faction)
        colour = tuple(f.color) if f is not None else (160, 40, 36)
    else:
        colour = BESET_RGB
    tw = max(7.0, size * 0.34)
    for i, tx, ty, depth in _ring(s, x, y, size, behind):
        k = 0.85 + 0.15 * depth  # the far ones a little smaller
        if i % 2 == 0:
            w, h = tw * k, tw * k * 0.78
            canvas.under(Image(("sign", "tent"), _tent, (tx - w / 2, ty - h, w, h), rgba=_lit(tint, a), smooth=False))
        else:
            w, h = tw * k * 0.5, tw * k * 1.1
            canvas.under(Image(("sign", "banner"), _banner, (tx - w * 0.2, ty - h, w, h),
                               rgba=_lit(tint, a, colour), smooth=False))


def under(canvas, game, places, now: float, tint) -> None:
    animate = canvas.gfx.ambient
    t = now if animate else 0.0
    night = 1.0 - tint[0] / 255
    for s, x, y, size, a in places:
        x, y, size = _frame(x, y, size)
        for mark in signed(s):
            if mark in ("siege", "beset"):
                _camp(canvas, game.world.factions, s, x, y, size, a, tint, True, mark)
            elif mark == "burning":  # the glow of it, stronger in the dark
                flicker = 0.85 + 0.15 * math.sin(t * 7.3 + s.id) * math.sin(t * 3.1 + s.id * 2) if animate else 0.9
                r = size * (0.95 + 0.1 * flicker)
                alpha = (90 + 140 * night) * flicker
                canvas.under(Image(("sign", "glow"), _glow, (x + size / 2 - r, y + size * 0.62 - r * 0.7, 2 * r,
                                                              1.4 * r), rgba=(255, 140, 60, int(alpha * a))))


def over(canvas, game, places, now: float, tint) -> None:
    animate = canvas.gfx.ambient
    t = now if animate else 0.0
    night = 1.0 - tint[0] / 255
    for s, x, y, size, a in places:
        x, y, size = _frame(x, y, size)
        for mark in signed(s):
            if mark in SMOKE:
                _smoke(canvas, s, x, y, size, a, tint, t, mark, night)
            elif mark in ("siege", "beset"):
                _camp(canvas, game.world.factions, s, x, y, size, a, tint, False, mark)
            elif mark == "plague":
                h = max(9.0, size * 0.5)
                w = h * 0.75
                frame = int(t * 2.2 + _seed(s) * 2) % 2 if animate else 0
                canvas.under(Image(("sign", "black_flag", frame), lambda f=frame: _black_flag(f),
                                   (x + size * 0.72, y + size * 0.5 - h, w, h), rgba=_lit(tint, a), smooth=False))
            elif mark == "tribute":
                _shadow(canvas, s, x, y, size, a, t)
            elif mark == "festival":
                _lanterns(canvas, s, x, y, size, a, tint, t, animate, night)
            elif mark == "memorial":
                h = max(9.0, size * 0.42)
                canvas.under(Image(("sign", "statue"), _statue, (x - h * 0.2, y + size * 0.92 - h, h * 0.64, h),
                                   rgba=_lit(tint, a), smooth=False))


def _smoke(canvas, s, x, y, size, a, tint, t, mark, night) -> None:
    n, rate, rgb, alpha, high, wide = SMOKE_LOOK[mark]
    seed = _seed(s)
    cx, base = x + size * (0.42 + 0.16 * seed), y + size * 0.45
    for i in range(n):
        p = (t * rate + i / n + seed) % 1.0
        r = size * (0.22 + 0.42 * p) * (wide / 0.55)
        px = cx + size * wide * p * 0.9 + math.sin(p * 5.0 + seed * 9) * size * 0.06
        py = base - size * high * p
        fade = (1.0 - p) * min(1.0, p * 6.0 + 0.15)
        col = rgb
        if mark == "burning":  # lit from below by the fire, the more the darker the hour
            k = (1.0 - p) ** 2 * (0.25 + 0.6 * night)
            col = tuple(int(c + (h - c) * k) for c, h in zip(rgb, (214, 96, 40)))
            col = tuple(min(255, int(v * (0.55 + 0.45 * tint[0] / 255) + 40 * k)) for v in col)
        else:
            col = tuple(int(v * tint[j] / 255) for j, v in enumerate(col))
        canvas.under(Image(("sign", "puff", i % 3), lambda v=i % 3: _puff(v), (px - r, py - r, 2 * r, 2 * r),
                           rgba=(*col, int(alpha * fade * a))))


def _shadow(canvas, s, x, y, size, a, t) -> None:
    ang = t * 0.35 + _seed(s) * math.tau
    cx, cy = x + size / 2, y + size * 0.55
    rx, ry = size * 1.0, size * 0.5
    px, py = cx + math.cos(ang) * rx, cy + math.sin(ang) * ry
    heading = math.degrees(math.atan2(math.cos(ang) * ry, -math.sin(ang) * rx))
    w, h = size * 1.05, size * 0.66
    canvas.under(Image(("sign", "dragon_shadow"), _dragon, (px - w / 2, py - h / 2, w, h), rgba=(255, 255, 255,
                                                                                                int(105 * a)),
                       angle=heading))


def _lanterns(canvas, s, x, y, size, a, tint, t, animate, night) -> None:
    left, right = (x + size * 0.04, y + size * 0.3), (x + size * 0.96, y + size * 0.26)
    sag = size * 0.16
    pts = []
    for i in range(7):
        k = i / 6
        pts.append((left[0] + (right[0] - left[0]) * k, left[1] + (right[1] - left[1]) * k + sag * 4 * k * (1 - k)))
    canvas.under(Lines(pts, max(1.0, size * 0.025), _lit(tint, a, (70, 52, 36), 230)))
    lw = max(3.0, size * 0.09)
    for i, (px, py) in enumerate(pts[1:-1]):
        rgb = LANTERNS[(i + s.id) % len(LANTERNS)]
        flick = 0.8 + 0.2 * math.sin(t * 5.0 + i * 1.7 + s.id) if animate else 0.9
        g = lw * 3.6
        canvas.under(Image(("sign", "glow"), _glow, (px - g / 2, py - g / 2 + lw * 0.5, g, g),
                           rgba=(*rgb, int((60 + 150 * night) * flick * a))))
        bright = 0.6 + 0.4 * max(night, tint[0] / 255)
        canvas.under(Image(("sign", "lantern"), _lantern, (px - lw / 2, py, lw, lw * 1.3),
                           rgba=(int(rgb[0] * bright), int(rgb[1] * bright), int(rgb[2] * bright), int(255 * a)),
                           smooth=False))
    for (px, py), k in ((left, 0), (right, 1)):  # a pennant at either end
        w, h = max(3.0, size * 0.14), max(6.0, size * 0.32)
        canvas.under(Image(("sign", "banner"), _banner, (px - w * 0.2, py - h * 0.25, w, h),
                           rgba=_lit(tint, a, LANTERNS[(s.id + 2 * k + 1) % len(LANTERNS)]), smooth=False))


# ---------------------------------------------------------------------------- the pictures (made once)
def _grid(rows: tuple[str, ...], pal: dict) -> np.ndarray:
    h, w = len(rows), max(len(r) for r in rows)
    a = np.zeros((h, w, 4), np.uint8)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in pal:
                a[y, x] = pal[ch]
    return a


INK = (54, 38, 26, 255)


@lru_cache(maxsize=1)
def _tent():
    return _grid((
        "......#......",
        ".....#w#.....",
        "....#wws#....",
        "...#wwwss#...",
        "..#wwwdsss#..",
        ".#wwwwddsss#.",
        "#wwwwwddssss#",
        "#############",
    ), {"#": INK, "w": (230, 218, 188, 255), "s": (178, 162, 132, 255), "d": (74, 52, 36, 255)})


@lru_cache(maxsize=1)
def _banner():
    """A pole and a white cloth (tinted to its colours as it is drawn)."""
    return _grid((
        "#.....",
        "#cccc.",
        "#ccckk",
        "#cccc.",
        "#cck..",
        "#c....",
        "#.....",
        "#.....",
        "#.....",
        "#.....",
        "#.....",
    ), {"#": (60, 52, 46, 255), "c": (255, 255, 255, 255), "k": (205, 205, 205, 255)})


@lru_cache(maxsize=2)
def _black_flag(frame: int):
    cloth = (("#bbbbb.", "#bbbbbb", "#bbbbg.", "#bbbb..", "#bb...."),
             ("#bbbb..", "#bbbbbb", "#bbbbbg", "#bbbb..", "#b....."))[frame]
    return _grid(cloth + ("#......",) * 6, {"#": (70, 58, 48, 255), "b": (20, 18, 20, 255), "g": (44, 40, 42, 255)})


@lru_cache(maxsize=1)
def _statue():
    return _grid((
        "..ll...",
        "..gg...",
        ".lggg..",
        "lgggdg.",
        ".lggd..",
        "..gd...",
        "..gd...",
        ".lgdd..",
        "#######",
        "#ppppd#",
        "#######",
    ), {"l": (214, 210, 200, 255), "g": (168, 164, 156, 255), "d": (112, 108, 104, 255), "#": (64, 60, 58, 255),
        "p": (140, 134, 126, 255)})


@lru_cache(maxsize=1)
def _lantern():
    return _grid((
        ".#.",
        "#w#",
        "#w#",
        ".#.",
    ), {"#": (110, 80, 50, 255), "w": (255, 255, 255, 255)})


@lru_cache(maxsize=1)
def _glow():
    yy, xx = np.mgrid[0:48, 0:48].astype(np.float32)
    d = np.sqrt((xx - 23.5) ** 2 + (yy - 23.5) ** 2) / 24.0
    a = np.zeros((48, 48, 4), np.uint8)
    a[..., :3] = 255
    a[..., 3] = (np.clip(1.0 - d, 0, 1) ** 2 * 255).astype(np.uint8)
    return a


@lru_cache(maxsize=3)
def _puff(variant: int):
    """A soft cloud of smoke, white (tinted as it is drawn), a little lumpy and lighter on top."""
    rng = np.random.default_rng(5100 + variant)
    yy, xx = np.mgrid[0:32, 0:32].astype(np.float32)
    m = np.zeros((32, 32), np.float32)
    for _ in range(5):
        bx, by, br = rng.uniform(10, 22), rng.uniform(11, 21), rng.uniform(6, 10)
        m = np.maximum(m, np.clip(1.0 - np.sqrt((xx - bx) ** 2 + (yy - by) ** 2) / br, 0, 1))
    a = np.zeros((32, 32, 4), np.uint8)
    shade = (0.82 + 0.18 * (1.0 - yy / 31.0)) * 255
    a[..., 0] = a[..., 1] = a[..., 2] = shade.astype(np.uint8)
    a[..., 3] = (np.clip(m * 1.6, 0, 1) ** 1.2 * 255).astype(np.uint8)
    return a


@lru_cache(maxsize=1)
def _dragon():
    """A dragon's shadow from above, facing right: body, tail, two great wings."""
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (64, 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ink = (10, 8, 12, 255)
    d.polygon([(2, 20), (22, 18), (22, 22)], fill=ink)  # the tail
    d.ellipse([20, 16, 48, 24], fill=ink)  # the body
    d.polygon([(46, 18), (55, 18), (55, 22), (46, 22)], fill=ink)  # the neck
    d.ellipse([53, 17, 62, 23], fill=ink)  # the head
    wing = [(42, 17), (36, 0), (33, 6), (29, 4), (28, 10), (24, 9), (27, 17)]  # swept back, its edge scalloped
    d.polygon(wing, fill=ink)
    d.polygon([(x, 40 - y) for x, y in wing], fill=ink)
    return im.filter(ImageFilter.GaussianBlur(1.2))
