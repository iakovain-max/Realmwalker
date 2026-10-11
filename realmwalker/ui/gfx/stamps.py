"""Little drawings stamped on the painted world map (ui/gfx/paint.py): the plants and stones of the newer lands
(palms, acacias, jungle crowns, silver fey trees, steppe grass, mesas, cinder cones, glacier cracks, salt) and the
wonders of the world, drawn large (a smoking volcano, the highest peak with snow streaming off it, falls, an oasis...).

Sharp pixels in the map's own grain: each is an (h, w, 4) uint8 array drawn for k map pixels to a square of country
(the map is painted at 12), in flat colours with an ink outline like the rest of the map. Pure numpy and Pillow.
"""

from __future__ import annotations

import zlib
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

INK = (52, 38, 26, 255)


def _outline(mask: np.ndarray) -> np.ndarray:
    o = np.zeros_like(mask)
    o[1:] |= mask[:-1]
    o[:-1] |= mask[1:]
    o[:, 1:] |= mask[:, :-1]
    o[:, :-1] |= mask[:, 1:]
    return o & ~mask


def _finish(im: Image.Image, ink: bool = True, foot: bool = True) -> np.ndarray:
    a = np.array(im, np.uint8)
    if ink:
        m = a[..., 3] > 0
        o = _outline(m)
        if not foot:
            o[-1] = False
        a[o] = INK
    return a


def _new(w: int, h: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGBA", (max(1, int(w)), max(1, int(h))), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def _c(rgb, a: int = 255) -> tuple:
    return tuple(int(v) for v in rgb[:3]) + (a,)


@lru_cache(maxsize=512)
def stamp(kind: str, k: int, variant: int) -> np.ndarray | None:
    """The drawing for `kind`, or None if this module does not draw it."""
    fn = STAMPS.get(kind)
    if fn is None:
        return None
    rng = np.random.default_rng(zlib.crc32(f"{kind}/{k}/{variant}".encode()))
    return fn(max(4, k), variant, rng)


# ---------------------------------------------------------------------------- plants and stones of the land
def _palm(k, v, rng):
    s = k / 12
    w, h = int(9 * s) | 1, int(9 * s)
    im, d = _new(w + 2, h + 2)
    cx = w // 2 + 1
    d.line([(cx, h), (cx + (1 if v % 2 else -1), int(3 * s))], fill=_c((120, 90, 56)), width=max(1, int(s)))
    top = (cx + (1 if v % 2 else -1), int(3 * s))
    for dx, dy in ((-4, 1), (4, 1), (-3, -2), (3, -2), (0, -3)):
        d.line([top, (top[0] + dx * s, top[1] + dy * s)], fill=_c((70, 120, 56)), width=max(1, int(s)))
    return _finish(im, foot=False)


def _acacia(k, v, rng):
    s = k / 12
    w, h = int(10 * s), int(7 * s)
    im, d = _new(w + 2, h + 2)
    d.line([(w // 2 + 1, h), (w // 2 + 1, int(3 * s))], fill=_c((100, 76, 52)), width=max(1, int(s)))
    d.rectangle([1, int(1 * s), w, int(3 * s)], fill=_c((112, 128, 62)))
    d.line([(1, int(1 * s)), (w, int(1 * s))], fill=_c((140, 156, 78)))
    return _finish(im, foot=False)


def _jungle(k, v, rng):
    s = k / 12
    r = max(2, int(3.4 * s))
    w = 2 * r + 3
    im, d = _new(w + 2, w + 1)
    greens = [(38, 92, 44), (46, 104, 48), (34, 84, 42)]
    g = greens[v % 3]
    for ox, oy, rr in ((0, 1, r), (-r // 2, 0, r - 1), (r // 2, 0, r - 1)):
        cx, cy = w // 2 + 1 + ox, r + 1 + oy
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=_c(g))
    d.ellipse([w // 2 - r // 2, 2, w // 2 + 1, r], fill=_c((72, 128, 60)))
    return _finish(im)


def _fey(k, v, rng):
    """A silver tree with long hanging strands of shining leaves (a weeping crown, not a ball)."""
    s = k / 12
    w, h = int(9 * s) | 1, int(9 * s)
    im, d = _new(w + 2, h + 2)
    cx = w // 2 + 1
    glow = [(96, 176, 168), (146, 128, 196), (110, 160, 196)][v % 3]
    bright = tuple(min(255, c + 60) for c in glow)
    d.line([(cx, h), (cx, int(3 * s))], fill=_c((216, 220, 230)), width=max(1, int(s)))
    d.chord([1, 1, w, int(6 * s)], 180, 360, fill=_c(glow))
    for x in range(1, w + 1, max(1, int(2 * s))):  # the strands, longest at the sides
        length = int((2 + abs(x - cx) * 0.6) * s)
        d.line([(x, int(3 * s)), (x, int(3 * s) + length)], fill=_c(glow))
        d.point((x, int(3 * s) + length), fill=_c(bright))
    return _finish(im, foot=False)


def _steppe(k, v, rng):
    s = k / 12
    im, d = _new(int(5 * s) + 1, int(3 * s) + 1)
    straw = (150, 142, 84)
    for x in range(0, int(5 * s) + 1, max(1, int(2 * s))):
        d.line([(x, int(3 * s)), (x + 1, 0)], fill=_c(straw))
    return _finish(im, ink=False)


def _mesa(k, v, rng):
    s = k / 12
    w, h = int((8 + v % 3 * 2) * s), int(5 * s)
    im, d = _new(w + 2, h + 2)
    top = int(1.5 * s)
    d.polygon([(1, h), (int(2 * s), top), (w - int(2 * s), top), (w, h)], fill=_c((166, 96, 62)))
    d.polygon([(w // 2, top), (w - int(2 * s), top), (w, h), (w // 2, h)], fill=_c((132, 72, 48)))
    d.line([(int(2 * s), top), (w - int(2 * s), top)], fill=_c((196, 130, 88)))
    return _finish(im, foot=False)


def _cinder(k, v, rng):
    s = k / 12
    w, h = int(6 * s) | 1, int(4 * s)
    im, d = _new(w + 2, h + 2)
    d.polygon([(1, h), (w // 2 + 1, 1), (w, h)], fill=_c((70, 60, 58)))
    d.polygon([(w // 2 + 1, 1), (w, h), (w // 2 + 1, h)], fill=_c((52, 44, 44)))
    return _finish(im, foot=False)


def _glacier(k, v, rng):
    s = k / 12
    w = int(7 * s)
    im, d = _new(w + 1, int(3 * s) + 1)
    pts = [(0, int(2 * s)), (int(2 * s), int(1 * s)), (int(4 * s), int(2 * s)), (w, 0)]
    d.line(pts, fill=_c((150, 180, 206)))
    return _finish(im, ink=False)


def _salt(k, v, rng):
    s = k / 12
    im, d = _new(int(6 * s) + 1, int(4 * s) + 1)
    d.line([(0, int(2 * s)), (int(3 * s), int(1 * s)), (int(6 * s), int(3 * s))], fill=_c((196, 190, 172)))
    d.line([(int(3 * s), int(1 * s)), (int(3 * s), int(4 * s))], fill=_c((196, 190, 172)))
    return _finish(im, ink=False)


# ---------------------------------------------------------------------------- the wonders, drawn large
def _w_peak(k, v, rng):
    s = k / 12
    w, h = int(30 * s) | 1, int(30 * s)
    im, d = _new(w + 2, h + 2)
    apex = (w // 2 + 1, 1)
    d.polygon([(1, h), apex, (w, h)], fill=_c((150, 140, 128)))
    d.polygon([apex, (w, h), (w // 2 + 1, h)], fill=_c((104, 96, 92)))
    snow = int(h * 0.45)
    d.polygon([apex, (apex[0] - snow * 0.48, snow), (apex[0] - snow * 0.2, snow - int(2 * s)),
               (apex[0], snow + int(1 * s)), (apex[0] + snow * 0.25, snow - int(3 * s)),
               (apex[0] + snow * 0.48, snow)], fill=_c((244, 244, 240)))
    d.polygon([apex, (apex[0], snow + int(1 * s)), (apex[0] + snow * 0.25, snow - int(3 * s)),
               (apex[0] + snow * 0.48, snow)], fill=_c((200, 206, 218)))
    for i in range(3):  # snow streaming off the summit in the wind
        d.line([(apex[0] + 2 + i * 2, 2 + i), (apex[0] + int((8 + i * 3) * s), 1 + i * 2)], fill=_c((236, 240, 244, 200)))
    return _finish(im, foot=False)


def _w_volcano(k, v, rng, awake: bool = True):
    s = k / 12
    w, h = int(26 * s) | 1, int(20 * s)
    im, d = _new(w + 2, h + int(10 * s) + 2)
    top = int(10 * s)
    lip = int(4 * s)
    d.polygon([(1, top + h), (w // 2 - lip, top + 1), (w // 2 + lip + 2, top + 1), (w, top + h)], fill=_c((88, 74, 70)))
    d.polygon([(w // 2 + 1, top + 1), (w // 2 + lip + 2, top + 1), (w, top + h), (w // 2 + 1, top + h)],
              fill=_c((66, 56, 54)))
    if awake:
        d.rectangle([w // 2 - lip + 1, top, w // 2 + lip + 1, top + max(1, int(s))], fill=_c((250, 140, 40)))
        for i in range(3):  # lava running down
            x = w // 2 - lip + 2 + i * lip
            d.line([(x, top + 2), (x + (i - 1) * int(2 * s), top + int((6 + i * 2) * s))], fill=_c((230, 100, 30)))
        for i, (ox, oy, rr) in enumerate(((0, -3, 3), (2, -6, 4), (-1, -9, 3))):  # smoke
            cx, cy = w // 2 + 1 + int(ox * s), top + int(oy * s)
            r = max(1, int(rr * s))
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_c((120, 114, 112, 210 - i * 40)))
    else:
        d.rectangle([w // 2 - lip + 1, top, w // 2 + lip + 1, top + max(1, int(s))], fill=_c((228, 232, 236)))
    a = _finish(im, foot=False)
    return a


def _w_volcano_cold(k, v, rng):
    return _w_volcano(k, v, rng, awake=False)


def _w_falls(k, v, rng):
    s = k / 12
    w, h = int(18 * s), int(16 * s)
    im, d = _new(w + 2, h + 2)
    d.rectangle([1, 1, w, int(6 * s)], fill=_c((132, 122, 110)))
    d.rectangle([1, int(6 * s), w, h], fill=_c((112, 102, 94)))
    fx0, fx1 = w // 2 - int(3 * s), w // 2 + int(3 * s)
    d.rectangle([fx0, int(4 * s), fx1, h], fill=_c((214, 230, 244)))
    for x in range(fx0, fx1 + 1, max(1, int(2 * s))):
        d.line([(x, int(4 * s)), (x, h)], fill=_c((160, 190, 220)))
    d.ellipse([fx0 - int(3 * s), h - int(3 * s), fx1 + int(3 * s), h + int(1 * s)], fill=_c((240, 246, 250)))
    return _finish(im, foot=False)


def _w_oasis(k, v, rng):
    s = k / 12
    w, h = int(20 * s), int(12 * s)
    im, d = _new(w + 2, h + 2)
    d.ellipse([int(4 * s), int(5 * s), w - int(4 * s), h], fill=_c((70, 140, 170)))
    d.ellipse([int(2 * s), int(3 * s), w - int(2 * s), h + int(1 * s)], outline=_c((96, 140, 64)), width=max(1, int(s)))
    a = _finish(im)
    for px in (int(3 * s), w - int(5 * s), w // 2):  # palms round the pool
        palm = _palm(k, 1, rng)
        ph, pw = palm.shape[:2]
        y0 = 0 if px == w // 2 else int(2 * s)
        _blit(a, palm, px, y0)
    return a


def _w_springs(k, v, rng):
    s = k / 12
    w, h = int(18 * s), int(12 * s)
    im, d = _new(w + 2, h + 2)
    for (x, y, rw) in ((2, 6, 6), (9, 8, 7), (5, 2, 5)):
        d.ellipse([x * s, y * s, (x + rw) * s, (y + 3) * s], fill=_c((236, 230, 206)))
        d.ellipse([(x + 1) * s, (y + 0.6) * s, (x + rw - 1) * s, (y + 2.4) * s], fill=_c((110, 190, 196)))
    a = _finish(im)
    im2, d2 = _new(a.shape[1], a.shape[0])
    for (x, y, r) in ((5, 2, 2), (12, 4, 2.5)):
        d2.ellipse([(x - r) * s, (y - r) * s, (x + r) * s, (y + r) * s], fill=(240, 240, 240, 170))
    st = np.array(im2)
    m = st[..., 3] > 0
    a[m] = st[m]
    return a


def _w_fey(k, v, rng):
    s = k / 12
    a = np.zeros((int(14 * s) + 2, int(22 * s) + 2, 4), np.uint8)
    for i, (x, y) in enumerate(((0, 4), (7, 0), (14, 3), (4, 7), (11, 6))):
        _blit(a, _fey(k, i, rng), int(x * s), int(y * s))
    return a


def _w_giant_tree(k, v, rng):
    s = k / 12
    w, h = int(26 * s), int(28 * s)
    im, d = _new(w + 2, h + 2)
    trunk = (110, 80, 52)
    d.polygon([(w // 2 - int(3 * s), h), (w // 2 - int(2 * s), int(12 * s)), (w // 2 + int(2 * s), int(12 * s)),
               (w // 2 + int(3 * s), h)], fill=_c(trunk))
    d.polygon([(w // 2 - int(3 * s), h), (w // 2 - int(7 * s), h), (w // 2 - int(2 * s), h - int(4 * s))], fill=_c(trunk))
    d.polygon([(w // 2 + int(3 * s), h), (w // 2 + int(7 * s), h), (w // 2 + int(2 * s), h - int(4 * s))], fill=_c(trunk))
    for (x, y, r, g) in ((13, 9, 9, (58, 96, 52)), (6, 11, 6, (52, 88, 48)), (20, 10, 6, (52, 88, 48)),
                         (11, 5, 6, (70, 110, 58)), (16, 4, 5, (78, 118, 62))):
        d.ellipse([(x - r) * s, (y - r) * s, (x + r) * s, (y + r) * s], fill=_c(g))
    return _finish(im, foot=False)


def _w_arch(k, v, rng):
    s = k / 12
    w, h = int(16 * s), int(12 * s)
    im, d = _new(w + 2, h + 2)
    rock = (176, 104, 70)
    d.pieslice([1, 1, w, h * 2 - int(2 * s)], 180, 360, fill=_c(rock))
    d.pieslice([int(4 * s), int(4 * s), w - int(3 * s), h * 2 - int(4 * s)], 180, 360, fill=(0, 0, 0, 0))
    d.rectangle([1, h // 2 + int(2 * s), int(4 * s), h], fill=_c(rock))
    d.rectangle([w - int(3 * s), h // 2 + int(2 * s), w, h], fill=_c((150, 86, 58)))
    return _finish(im, foot=False)


def _w_sinkhole(k, v, rng):
    s = k / 12
    w, h = int(18 * s), int(11 * s)
    im, d = _new(w + 2, h + 2)
    d.ellipse([1, 1, w, h], fill=_c((120, 110, 90)))
    d.ellipse([int(2 * s), int(2 * s), w - int(2 * s), h - int(1 * s)], fill=_c((26, 22, 22)))
    d.ellipse([int(4 * s), int(2 * s), w - int(4 * s), h // 2], fill=_c((54, 50, 46)))
    return _finish(im)


def _w_stone_trees(k, v, rng):
    s = k / 12
    w, h = int(16 * s), int(10 * s)
    im, d = _new(w + 2, h + 2)
    stone = (150, 142, 132)
    for x, hh in ((2, 8), (7, 10), (12, 7)):
        d.line([(x * s, h), (x * s, (h - hh * 0.9) if hh else h)], fill=_c(stone), width=max(1, int(s)))
        d.line([(x * s, (h - hh * 0.6)), ((x + 2) * s, (h - hh * 0.8))], fill=_c(stone), width=max(1, int(s * 0.7)))
    d.line([(1, h - 1), (w, h - 2)], fill=_c((170, 120, 90)), width=max(1, int(s)))  # a fallen trunk
    return _finish(im, foot=False)


def _w_ice_wall(k, v, rng):
    s = k / 12
    w, h = int(24 * s), int(10 * s)
    im, d = _new(w + 2, h + 2)
    d.rectangle([1, int(3 * s), w, h], fill=_c((150, 196, 226)))
    for x in range(1, w, max(2, int(3 * s))):
        d.line([(x, int(3 * s)), (x + int(s), h)], fill=_c((206, 232, 246)))
    d.rectangle([1, int(1 * s), w, int(3 * s)], fill=_c((236, 244, 250)))
    return _finish(im, foot=False)


def _w_drifting(k, v, rng):
    s = k / 12
    w, h = int(22 * s), int(18 * s)
    im, d = _new(w + 2, h + 2)
    rocks = ((2, 2, 8, 5), (11, 0, 9, 6), (6, 8, 7, 4))
    for x, y, rw, rh in rocks:  # their shadows on the ground far below
        d.ellipse([(x + 1) * s, (y + rh + 7) * s, (x + rw) * s, (y + rh + 8.5) * s], fill=(0, 0, 0, 70))
    a = np.array(im)
    im2, d2 = _new(w + 2, h + 2)
    for x, y, rw, rh in rocks:  # islands in the air: grass on top, the torn-off rock hanging under
        d2.polygon([(x * s, (y + 1.5) * s), ((x + rw) * s, (y + 1.5) * s), ((x + rw * 0.55) * s, (y + rh) * s),
                    ((x + rw * 0.35) * s, (y + rh - 0.5) * s)], fill=_c((128, 112, 100)))
        d2.ellipse([x * s, y * s, (x + rw) * s, (y + 2.5) * s], fill=_c((104, 140, 72)))
        d2.line([((x + rw * 0.45) * s, (y + rh) * s), ((x + rw * 0.45) * s, (y + rh + 2) * s)],
                fill=_c((200, 220, 236)))  # water spilling off it
    b = _finish(im2)
    m = b[..., 3] > 0
    a[m] = b[m]
    return a


def _w_glow(k, v, rng):
    s = k / 12
    w, h = int(14 * s), int(8 * s)
    im, d = _new(w + 2, h + 2)
    d.ellipse([1, 1, w, h], outline=_c((150, 250, 220, 220)), width=max(1, int(s)))
    d.ellipse([int(3 * s), int(2.5 * s), w - int(3 * s), h - int(1.5 * s)], outline=_c((200, 255, 240, 160)))
    return _finish(im, ink=False)


def _blit(dst: np.ndarray, src: np.ndarray, x: int, y: int) -> None:
    h, w = src.shape[:2]
    H, W = dst.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    sub = src[y0 - y:y1 - y, x0 - x:x1 - x]
    m = sub[..., 3] > 0
    dst[y0:y1, x0:x1][m] = sub[m]


STAMPS = {
    "palm": _palm, "acacia": _acacia, "jungle": _jungle, "fey": _fey, "steppe": _steppe, "mesa": _mesa,
    "cinder": _cinder, "glacier": _glacier, "salt": _salt,
    "w_peak": _w_peak, "w_volcano": _w_volcano, "w_volcano_cold": _w_volcano_cold, "w_falls": _w_falls,
    "w_oasis": _w_oasis, "w_springs": _w_springs, "w_fey": _w_fey, "w_giant_tree": _w_giant_tree,
    "w_arch": _w_arch, "w_sinkhole": _w_sinkhole, "w_stone_trees": _w_stone_trees, "w_ice_wall": _w_ice_wall,
    "w_drifting": _w_drifting, "w_glow": _w_glow,
}
# Which wonder is drawn with which stamp (the rest are painted into the map itself: a gorge, cliffs, a salt pan).
WONDER_STAMP = {
    "great_peak": "w_peak", "volcano": "w_volcano", "great_falls": "w_falls", "oasis": "w_oasis",
    "hot_springs": "w_springs", "enchanted_forest": "w_fey", "giant_tree": "w_giant_tree", "stone_arches": "w_arch",
    "sinkhole": "w_sinkhole", "petrified_forest": "w_stone_trees", "glacier_wall": "w_ice_wall",
    "drifting_stones": "w_drifting", "glowing_lake": "w_glow",
}
