"""Buildings in a town seen from the street, a little from the south: the roof from above and the front wall below it,
in sharp pixels.

Each building is drawn once per size and kept. Its look comes from what it is and where: thatch, shingle, red tile,
slate, turf or stone on top; plaster with timber framing, brick, stone or logs for walls. The roof takes one of a few
forms (a ridge along the house, a ridge front to back with the gable end facing you, a hipped roof, a temple's tower
and spire, a keep's battlements, a cross gable on an inn) with chimneys and dormers. The front wall shows its
windows and, when the door is on that side, the door itself (a striped awning over a shop's, double doors on a
stable, an arch on a temple). A door on another side shows as a gap in the eaves, so a door is always visible.

While you stand inside, the building is not drawn and you see the room. Windows glow at night (a second picture,
drawn untinted, so lamplight stays warm).
"""

from __future__ import annotations

import zlib
from functools import lru_cache

import numpy as np

# Roof colours: base (the slope facing you), shade (the far slope), light (ridge and highlights).
STYLES = {
    "charred": ((44, 38, 36), (24, 20, 18), (70, 58, 50)),  # (blackened by fire: game/placemarks.py)
    "thatch": ((178, 146, 86), (128, 100, 56), (206, 178, 116)),
    "slate": ((96, 104, 118), (66, 72, 86), (134, 142, 154)),
    "tile": ((164, 78, 56), (112, 50, 40), (196, 110, 80)),
    "shingle": ((120, 90, 62), (84, 62, 44), (150, 118, 84)),
    "turf": ((88, 112, 64), (62, 80, 48), (118, 142, 86)),
    "stone": ((128, 124, 116), (92, 88, 82), (160, 156, 148)),
}
# Walls: (face, trim/beams, shadow).
WALLS = {
    "plaster": ((222, 208, 178), (98, 68, 46), (176, 160, 132)),
    "ochre": ((214, 184, 128), (92, 62, 42), (170, 142, 96)),
    "rose": ((214, 180, 164), (96, 66, 50), (170, 138, 124)),
    "brick": ((156, 86, 64), (204, 190, 170), (118, 62, 48)),
    "stone": ((152, 146, 134), (110, 104, 96), (118, 112, 102)),
    "logs": ((132, 94, 60), (84, 58, 38), (104, 72, 46)),
    "dark_stone": ((112, 108, 104), (78, 74, 70), (88, 84, 80)),
    "whitewash": ((240, 238, 230), (120, 100, 80), (196, 190, 178)),
    "mudbrick": ((196, 160, 110), (120, 92, 60), (156, 124, 84)),
    "sandstone": ((214, 186, 132), (150, 120, 80), (176, 148, 102)),
    "marble": ((234, 230, 222), (170, 166, 158), (196, 192, 184)),
    "limestone": ((228, 220, 196), (160, 150, 124), (190, 182, 160)),
    "dark_wood": ((96, 70, 48), (60, 42, 28), (76, 56, 38)),
    "charred": ((58, 48, 42), (28, 22, 20), (42, 34, 30)),  # (a house the fire went through: game/placemarks.py)
}
STYLES.setdefault("hide", ((150, 116, 80), (116, 88, 60), (178, 144, 104)))
OUTLINE = (34, 26, 20)
GLASS = (40, 44, 52)
LAMP = (255, 196, 110)
AWNINGS = ((168, 52, 44), (52, 92, 146), (60, 120, 70), (180, 140, 50), (120, 60, 120))

SIGNS = {"inn": "item/ale", "temple": "item/holy_symbol", "smithy": "feature/anvil", "store": "item/_coins_1",
         "healer": "item/potion_healing", "stable": "creature/horse", "hall": "wall/banner", "keep": "wall/banner"}


def _h(key: str, n: int = 100) -> int:
    return zlib.crc32(key.encode()) % n


def style_for(settlement_kind: str, building_kind: str, key: str) -> str:
    h = _h(key)
    if settlement_kind == "hold":
        return "stone"
    if settlement_kind == "elfhall":
        return "turf"
    if building_kind in ("temple", "hall"):
        return "slate"
    if building_kind == "keep":
        return "stone"
    if building_kind == "stable":
        return "thatch" if settlement_kind in ("hamlet", "village") or h < 50 else "shingle"
    if settlement_kind in ("hamlet", "village"):
        return "thatch" if h < 60 else ("shingle" if h < 85 else "tile")
    return "tile" if h < 50 else ("slate" if h < 75 else ("shingle" if h < 90 else "thatch"))


def wall_for(settlement_kind: str, building_kind: str, key: str) -> str:
    h = _h(key + "wall")
    if settlement_kind == "hold":
        return "dark_stone"
    if settlement_kind == "elfhall":
        return "logs"
    if building_kind in ("temple", "keep"):
        return "stone"
    if building_kind == "hall":
        return "stone" if h < 60 else "brick"
    if building_kind == "stable":
        return "logs"
    if settlement_kind == "hamlet":
        return "logs" if h < 45 else "plaster"
    if settlement_kind == "village":
        return ("plaster", "plaster", "ochre", "logs", "rose")[h % 5]
    return ("plaster", "ochre", "rose", "brick", "stone", "plaster")[h % 6]


def form_for(building_kind: str, w: int, h: int, key: str) -> str:
    """The shape of the roof."""
    r = _h(key + "form")
    if building_kind == "keep":
        return "keep"
    if building_kind == "temple":
        return "temple"
    if building_kind == "hall":
        return "hip"
    if building_kind == "inn" and w >= 8:
        return "cross"
    if building_kind == "stable":
        return "gable"
    if w <= 6 and r < 40:
        return "front"
    return "hip" if r < 25 else "gable"


def pixel_size(tile: int) -> int:
    """Building pixels to a square: about 16, a whole divisor of the square's size on screen."""
    divisors = [d for d in range(1, tile + 1) if tile % d == 0]
    s = min(divisors, key=lambda d: (abs(tile / d - 16), d))
    return tile // s


def extra_top(form: str, r: int) -> int:
    """Rows drawn above the building's own squares (a spire, a turret)."""
    return {"temple": 2 * r, "keep": r // 2}.get(form, 0)


# ---------------------------------------------------------------------------- drawing
class _Pic:
    def __init__(self, w: int, h: int) -> None:
        self.a = np.zeros((h, w, 4), np.uint8)
        self.w, self.h = w, h

    def rect(self, x0, y0, x1, y1, rgb, alpha: int = 255) -> None:
        x0, y0 = max(0, int(x0)), max(0, int(y0))
        x1, y1 = min(self.w, int(x1)), min(self.h, int(y1))
        if x1 > x0 and y1 > y0:
            self.a[y0:y1, x0:x1, :3] = rgb
            self.a[y0:y1, x0:x1, 3] = alpha

    def mask(self, m: np.ndarray, rgb) -> None:
        self.a[m, :3] = rgb
        self.a[m, 3] = 255

    def px(self, x, y, rgb) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[int(y), int(x), :3] = rgb
            self.a[int(y), int(x), 3] = 255


def _shade(rgb, k: float):
    return tuple(int(max(0, min(255, c * k))) for c in rgb)


def _outline(m: np.ndarray) -> np.ndarray:
    o = np.zeros_like(m)
    o[1:] |= m[:-1]
    o[:-1] |= m[1:]
    o[:, 1:] |= m[:, :-1]
    o[:, :-1] |= m[:, 1:]
    return o & ~m


def _courses(pic: _Pic, region: np.ndarray, style: str, along_x: bool, base, rng) -> None:
    """The stuff of the roof inside `region`: courses of tile, slate or shingle, streaks of thatch, tufts of turf."""
    ys, xs = np.mgrid[0:pic.h, 0:pic.w]
    along = ys if along_x else xs
    across = xs if along_x else ys
    if style == "thatch":
        streak = rng.uniform(0.86, 1.1, max(pic.w, pic.h) + 1)
        f = streak[across] * np.where(along % 4 == 0, 0.9, 1.0)
        rgb = np.clip(np.array(base, np.float32)[None, None, :] * f[..., None], 0, 255).astype(np.uint8)
        pic.a[region, :3] = rgb[region]
        return
    if style == "turf":
        speck = rng.random((pic.h, pic.w))
        pic.a[region & (speck < 0.12), :3] = _shade(base, 0.82)
        pic.a[region & (speck > 0.95), :3] = (196, 186, 110)  # a flower or two
        return
    row = 3 if style in ("tile", "slate") else (4 if style == "stone" else 3)
    groove = (along % row) == 0
    width = 4 if style == "tile" else (5 if style == "slate" else 6)
    seam = ((across + (along // row) * (width // 2)) % width) == 0
    pic.a[region & groove, :3] = _shade(base, 0.72)
    pic.a[region & seam & ~groove, :3] = _shade(base, 0.86)
    if style == "tile":
        pic.a[region & ((along % row) == 1) & ~seam, :3] = _shade(base, 1.1)
    worn = rng.random((pic.h, pic.w)) < 0.025
    pic.a[region & worn & ~groove, :3] = _shade(base, 0.8)


def _window(pic: _Pic, x: int, y: int, ww: int, wh: int, frame, shutters, glow: _Pic | None) -> None:
    pic.rect(x - 1, y - 1, x + ww + 1, y + wh + 1, frame)
    pic.rect(x, y, x + ww, y + wh, GLASS)
    if ww >= 3:
        pic.rect(x + ww // 2, y, x + ww // 2 + 1, y + wh, frame)  # the mullion
    pic.px(x, y, (90, 100, 116))  # a glint
    if shutters is not None and ww >= 2:
        pic.rect(x - 2, y - 1, x - 1, y + wh + 1, shutters)
        pic.rect(x + ww + 1, y - 1, x + ww + 2, y + wh + 1, shutters)
    pic.rect(x - 1, y + wh + 1, x + ww + 1, y + wh + 2, _shade(frame, 0.8))  # the sill
    if glow is not None:
        glow.rect(x, y, x + ww, y + wh, LAMP)
        if ww >= 3:
            glow.rect(x + ww // 2, y, x + ww // 2 + 1, y + wh, (0, 0, 0), 0)


def _wall(pic: _Pic, x0: int, y0: int, x1: int, y1: int, wall: str, rng) -> None:
    face, trim, shadow = WALLS[wall]
    pic.rect(x0, y0, x1, y1, face)
    ys, xs = np.mgrid[0:pic.h, 0:pic.w]
    inside = (xs >= x0) & (xs < x1) & (ys >= y0) & (ys < y1)
    if wall in ("stone", "dark_stone"):
        course = (ys - y0) // 3
        pic.a[inside & ((ys - y0) % 3 == 0), :3] = trim
        pic.a[inside & ((xs + course * 3) % 7 == 0), :3] = trim
        pic.a[inside & (rng.random((pic.h, pic.w)) < 0.06), :3] = _shade(face, 1.08)
    elif wall == "brick":
        course = (ys - y0) // 2
        pic.a[inside & ((ys - y0) % 2 == 0), :3] = _shade(face, 0.82)
        pic.a[inside & ((xs + course * 2) % 4 == 0) & ((ys - y0) % 2 == 1), :3] = _shade(face, 0.78)
    elif wall == "logs":
        pic.a[inside & ((ys - y0) % 3 == 2), :3] = trim
        pic.a[inside & ((ys - y0) % 3 == 0), :3] = _shade(face, 1.1)
    else:  # plaster between timbers
        pic.a[inside & (rng.random((pic.h, pic.w)) < 0.05), :3] = shadow
    pic.rect(x0, y1 - 1, x1, y1, shadow)  # the footing


def _timbers(pic: _Pic, x0: int, y0: int, x1: int, y1: int, wall: str, r: int, skip: tuple[int, int], rng) -> None:
    """Timber framing on a plaster wall: corner posts, posts every two squares, a rail, now and then a brace."""
    if wall not in ("plaster", "ochre", "rose"):
        return
    trim = WALLS[wall][1]
    pic.rect(x0, y0, x1, y0 + 1, trim)
    pic.rect(x0, y0 + (y1 - y0) // 2, x1, y0 + (y1 - y0) // 2 + 1, trim)
    for x in list(range(x0, x1, 2 * r)) + [x1 - 1]:
        if skip[0] <= x < skip[1]:
            continue
        pic.rect(x, y0, x + 1, y1, trim)
        if rng.random() < 0.4 and x + r < x1 and not (skip[0] <= x + r // 2 < skip[1]):
            for i in range(min(r, y1 - y0) // 2):
                pic.px(x + 1 + i, y0 + (y1 - y0) // 2 - 1 - i, trim)


def _door(pic: _Pic, x: int, y_bottom: int, r: int, kind: str, wall: str, rng, glow: _Pic | None) -> None:
    wood = (112, 76, 46) if rng.random() < 0.6 else (86, 96, 70)
    frame = OUTLINE
    if kind == "stable":
        dw, dh = r - 2, int(r * 0.85)
        x0 = x + 1
        pic.rect(x0 - 1, y_bottom - dh - 1, x0 + dw + 1, y_bottom, frame)
        pic.rect(x0, y_bottom - dh, x0 + dw, y_bottom, wood)
        for i in range(dh):  # the cross brace of a barn door
            pic.px(x0 + int(i * (dw - 1) / max(1, dh - 1)), y_bottom - dh + i, _shade(wood, 0.7))
            pic.px(x0 + dw - 1 - int(i * (dw - 1) / max(1, dh - 1)), y_bottom - dh + i, _shade(wood, 0.7))
        pic.rect(x0 + dw // 2, y_bottom - dh, x0 + dw // 2 + 1, y_bottom, frame)
        return
    dw = max(4, int(r * 0.5)) | 1
    dh = max(6, int(r * 0.78))
    x0 = x + (r - dw) // 2
    top = y_bottom - dh
    pic.rect(x0 - 1, top - 1, x0 + dw + 1, y_bottom, frame)
    pic.rect(x0, top, x0 + dw, y_bottom, wood)
    for px_ in range(x0 + 1, x0 + dw, 2):
        pic.rect(px_, top, px_ + 1, y_bottom, _shade(wood, 0.82))
    if kind == "temple":  # an arch
        pic.px(x0, top, frame)
        pic.px(x0 + dw - 1, top, frame)
        pic.rect(x0 - 1, top - 2, x0 + dw + 1, top - 1, WALLS[wall][1])
    pic.px(x0 + dw - 2, top + dh // 2, (210, 190, 120))  # the latch
    pic.rect(x0 - 2, y_bottom - 1, x0 + dw + 2, y_bottom, (120, 114, 104))  # the step
    if glow is not None and kind in ("inn", "temple", "hall"):
        glow.rect(x0 - 3, top + 2, x0 - 2, top + 4, LAMP)  # a lamp by the door


def _awning(pic: _Pic, cx: int, y: int, r: int, colour) -> None:
    w = int(r * 2.4)
    x0 = cx - w // 2
    depth = max(4, r // 2)
    for i in range(w):
        c = colour if (i // 3) % 2 == 0 else (226, 214, 190)
        pic.rect(x0 + i, y, x0 + i + 1, y + depth + (1 if i % 3 == 1 else 0), c)
        pic.px(x0 + i, y + depth + (1 if i % 3 == 1 else 0), OUTLINE)
    pic.rect(x0, y - 1, x0 + w, y, OUTLINE)
    pic.rect(x0, y, x0 + 1, y + depth, OUTLINE)
    pic.rect(x0 + w - 1, y, x0 + w, y + depth, OUTLINE)


def _chimney(pic: _Pic, x: int, y: int, r: int, wall: str) -> None:
    cw, chh = max(4, r // 3 + 1), max(5, r // 2)
    brick = (132, 80, 62) if wall != "logs" else (120, 116, 108)
    pic.rect(x - 1, y - 1, x + cw + 1, y + chh + 1, OUTLINE)
    pic.rect(x, y, x + cw, y + chh, brick)
    pic.rect(x, y, x + cw, y + 1, _shade(brick, 1.2))
    pic.rect(x + 1, y + 1, x + cw - 1, y + 2, (24, 18, 16))


def chimney_spot(w: int, h: int, seed: int, form: str = "gable") -> tuple[float, float]:
    """Where the chimney stands, as fractions of the building's width and of its height (the same at every zoom)."""
    t = (zlib.crc32(f"chimney{seed}".encode()) % 1000) / 1000.0
    if form == "front":
        return 0.62 + 0.15 * t, 0.25
    return 0.22 + 0.5 * t, 0.18


@lru_cache(maxsize=384)
def building(w: int, h: int, r: int, style: str, wall: str, form: str, kind: str, door: tuple[int, int],
             seed: int, chimney: bool, lit: bool):
    """The building w x h squares at r pixels a square, as (picture, window glow or None), each (H, W, 4) uint8;
    H is h * r plus extra_top(form, r) rows above."""
    rng = np.random.default_rng(seed)
    E = extra_top(form, r)
    W, Hb = w * r, h * r
    pic = _Pic(W, Hb + E)
    glow = _Pic(W, Hb + E) if lit else None
    base, dark, light = STYLES.get(style, STYLES["thatch"])
    dx, dy = door
    side = "south" if dy == h - 1 else ("north" if dy == 0 else ("west" if dx == 0 else "east"))
    # The front wall: the bottom square of the building and a little more, so it reads as a wall.
    fh = r + r // 2 if h >= 5 else r + r // 4
    fy0, fy1 = E + Hb - fh, E + Hb
    eave = max(2, r // 4)
    wall_top = fy0 + eave - 1
    _wall(pic, 0, wall_top, W, fy1, wall, rng)
    door_x = dx * r if side == "south" else -10 * r
    _timbers(pic, 0, wall_top, W, fy1, wall, r, (door_x - 1, door_x + r + 1), rng)
    frame = WALLS[wall][1] if wall not in ("brick",) else (90, 70, 54)
    shutters = None
    if wall in ("plaster", "ochre", "rose", "logs") and rng.random() < 0.55:
        shutters = ((70, 96, 70), (64, 82, 120), (120, 60, 50), (96, 72, 46))[int(rng.integers(0, 4))]
    ww, wh = max(3, r // 3), max(3, int(r * 0.32))
    for cx in range(r // 2, W, 2 * r if w > 4 else r + r // 2):
        if side == "south" and abs(cx - (door_x + r // 2)) < r:
            continue
        if cx - ww // 2 < 3 or cx + ww // 2 > W - 3:
            continue
        _window(pic, cx - ww // 2, wall_top + (fy1 - wall_top - wh) // 2 - 1, ww, wh, frame, shutters, glow)
    if side == "south":
        _door(pic, door_x, fy1, r, kind, wall, rng, glow)
    # The roof over the rest.
    ry1 = fy0 + eave  # the eave hangs a little over the wall
    ys, xs = np.mgrid[0:pic.h, 0:pic.w]
    roof = (ys >= E) & (ys < ry1)
    near_rgb, far_rgb = base, dark
    if form in ("gable", "cross", "hip", "temple"):
        ridge = E + int((ry1 - E) * 0.4)
        far = roof & (ys < ridge)
        near = roof & (ys >= ridge)
        if form == "hip":
            d = min((ry1 - E) // 2 + 1, W // 3)
            reach = np.where(ys < ridge, (ridge - ys) / max(1, ridge - E), (ys - ridge) / max(1, ry1 - 1 - ridge))
            span = d * (1 - np.clip(reach, 0, 1))
            left_hip = roof & (xs < span)
            right_hip = roof & (W - 1 - xs < span)
            pic.mask(far, far_rgb)
            _courses(pic, far, style, True, far_rgb, rng)
            pic.mask(near, near_rgb)
            _courses(pic, near, style, True, near_rgb, rng)
            pic.mask(left_hip, _shade(base, 1.08))
            _courses(pic, left_hip, style, False, _shade(base, 1.08), rng)
            pic.mask(right_hip, _shade(dark, 0.95))
            _courses(pic, right_hip, style, False, _shade(dark, 0.95), rng)
            pic.mask(roof & (ys == ridge) & ~left_hip & ~right_hip, light)
        else:
            pic.mask(far, far_rgb)
            _courses(pic, far, style, True, far_rgb, rng)
            pic.mask(near, near_rgb)
            _courses(pic, near, style, True, near_rgb, rng)
            # Light falls off down the near slope, and the far slope darkens towards its ridge.
            k = np.where(near, 1.08 - 0.16 * (ys - ridge) / max(1, ry1 - ridge), 0.92 + 0.08 * (ys - E) / max(1, ridge - E))
            sel = roof
            pic.a[sel, :3] = np.clip(pic.a[sel, :3].astype(np.float32) * k[sel][:, None], 0, 255).astype(np.uint8)
            pic.mask(roof & (ys == ridge), light)
            pic.mask(roof & (ys == ridge + 1) & (xs % 3 == 0), _shade(light, 0.85))
            pic.rect(0, E, 1, ry1, OUTLINE)  # barge boards at the gable ends
            pic.rect(W - 1, E, W, ry1, OUTLINE)
    elif form == "front":
        mid = W // 2
        gh = min(int(r * 1.3), (ry1 - E) // 2)
        bottom = ry1 - (gh * (1 - np.abs(xs - mid + 0.5) / (W / 2))).astype(int)
        roof = (ys >= E) & (ys < bottom)
        left = roof & (xs < mid)
        right = roof & (xs >= mid)
        pic.mask(left, base)
        _courses(pic, left, style, False, base, rng)
        pic.mask(right, dark)
        _courses(pic, right, style, False, dark, rng)
        pic.mask(roof & ((xs == mid) | (xs == mid - 1)), light)
        gable = (ys >= bottom) & (ys < wall_top) & (ys >= E)
        face = WALLS[wall][0]
        pic.mask(gable, face)
        if wall in ("logs",):
            pic.a[gable & ((ys - E) % 3 == 2), :3] = WALLS[wall][1]
        tip = ry1 - gh
        if wall_top - tip > 5:  # a little window in the gable
            gw = max(2, r // 5)
            _window(pic, mid - gw // 2, tip + (wall_top - tip) // 2, gw, gw, frame, None, glow)
        pic.mask(_outline(roof) & ~roof & (ys >= E) & (ys < wall_top + 1) & gable, _shade(dark, 0.6))
    elif form == "keep":
        lead = (84, 88, 96)
        pic.mask(roof, lead)
        _courses(pic, roof, "slate", True, lead, rng)
        pw = max(3, r // 4)  # the parapet all round, with merlons on its outer edge
        ring = roof & ((ys < E + pw) | (ys >= ry1 - pw) | (xs < pw) | (xs >= W - pw))
        pic.mask(ring, base)
        _courses(pic, ring, "stone", True, base, rng)
        pic.mask(roof & ((ys == E + pw) | (xs == pw) | (xs == W - pw - 1)) & ~ring, _shade(lead, 0.7))
        merl = ((ys == E) & (xs % 4 < 2)) | ((xs == 0) & (ys % 4 < 2)) | ((xs == W - 1) & (ys % 4 < 2))
        pic.a[roof & ring & ~merl & ((ys == E) | (xs == 0) | (xs == W - 1)), 3] = 0
        tw = max(6, int(r * 0.9)) // 2 * 2
        for tx in (0, W - tw):  # round turrets at the back corners, with cones
            for ty, cone in ((E, True), (ry1 - tw, False)):
                yy, xx = np.mgrid[0:tw, 0:tw]
                disc = (xx - tw / 2 + 0.5) ** 2 + (yy - tw / 2 + 0.5) ** 2 <= (tw / 2) ** 2
                sub = pic.a[max(0, ty):ty + tw, tx:tx + tw]
                d = disc[:sub.shape[0], :sub.shape[1]]
                sub[d, :3] = _shade(base, 1.05)
                sub[d, 3] = 255
                if cone:
                    for i in range(tw // 2 + 2):
                        half = int(tw / 2 * (i + 1) / (tw // 2 + 2))
                        y = ty - tw // 2 + i
                        pic.rect(tx + tw // 2 - half, y, tx + tw // 2, y + 1, _shade(STYLES["slate"][0], 1.1))
                        pic.rect(tx + tw // 2, y, tx + tw // 2 + half, y + 1, STYLES["slate"][1])
        cw_ = min(2 * r, W // 3) // 2 * 2  # the great tower in the middle
        cx0, cy0 = (W - cw_) // 2, E + (ry1 - E - cw_) // 2
        pic.rect(cx0, cy0, cx0 + cw_, cy0 + cw_, _shade(base, 1.08))
        for i in range(cw_ // 2):
            pic.rect(cx0 + i, cy0 + i, cx0 + cw_ - i, cy0 + i + 1, _shade(STYLES["slate"][1], 1.0 + 0.02 * i))
            pic.rect(cx0 + i, cy0 + cw_ - 1 - i, cx0 + cw_ - i, cy0 + cw_ - i, _shade(STYLES["slate"][0], 1.05))
            pic.rect(cx0 + i, cy0 + i, cx0 + i + 1, cy0 + cw_ - i, _shade(STYLES["slate"][0], 1.15))
            pic.rect(cx0 + cw_ - 1 - i, cy0 + i, cx0 + cw_ - i, cy0 + cw_ - i, STYLES["slate"][1])
        pic.mask(_outline((xs >= cx0) & (xs < cx0 + cw_) & (ys >= cy0) & (ys < cy0 + cw_)), OUTLINE)
        flag = ((150, 40, 36), (40, 70, 140), (60, 100, 50))[seed % 3]
        fx = cx0 + cw_ // 2
        pic.rect(fx, cy0 - r // 2 - 2, fx + 1, cy0 + cw_ // 2, (60, 50, 40))
        pic.rect(fx + 1, cy0 - r // 2 - 2, fx + 6, cy0 - r // 2 + 2, flag)
    if form == "cross":  # a front gable over the middle of the house, over the door when it is in front
        cw_ = 3 * r if w >= 9 else 2 * r
        cx0 = (door_x + r // 2 - cw_ // 2) if side == "south" else (W - cw_) // 2
        cx0 = max(r // 2, min(W - cw_ - r // 2, cx0))
        mid = cx0 + cw_ // 2
        gh = min(int(r * 0.9), (ry1 - E) // 2)
        top = E + (ry1 - E) // 3
        span = (xs >= cx0) & (xs < cx0 + cw_)
        bottom = ry1 - (gh * (1 - np.abs(xs - mid + 0.5) / (cw_ / 2))).astype(int)
        wing = span & (ys >= top) & (ys < bottom)
        pic.mask(wing & (xs < mid), _shade(base, 1.06))
        _courses(pic, wing & (xs < mid), style, False, _shade(base, 1.06), rng)
        pic.mask(wing & (xs >= mid), _shade(dark, 1.05))
        _courses(pic, wing & (xs >= mid), style, False, _shade(dark, 1.05), rng)
        pic.mask(wing & ((xs == mid) | (xs == mid - 1)), light)
        gable = span & (ys >= bottom) & (ys < wall_top)
        pic.mask(gable, WALLS[wall][0])
        pic.mask(_outline(wing) & span & (ys >= top - 1) & (ys < wall_top), OUTLINE)
    if form == "temple":
        tw = min(W // 3, 3 * r) // 2 * 2
        tx0 = 0 if seed % 2 == 0 else W - tw
        tb = ry1  # the tower's own front wall reaches the eaves
        tt = E + r // 2
        _wall(pic, tx0, tt, tx0 + tw, tb + 1, "stone", rng)
        pic.rect(tx0 + tw // 2 - 1, tt + 3, tx0 + tw // 2 + 1, tt + 3 + r // 2, GLASS)  # a slit window
        if glow is not None:
            glow.rect(tx0 + tw // 2 - 1, tt + 3, tx0 + tw // 2 + 1, tt + 3 + r // 2, LAMP)
        # The spire.
        sp_h = E + r // 2
        for y in range(sp_h):
            half = int(tw / 2 * (y + 1) / sp_h)
            c = tx0 + tw // 2
            pic.rect(c - half, y, c, y + 1, _shade(dark, 1.1))
            pic.rect(c, y, c + half, y + 1, _shade(dark, 0.85))
        pic.mask(_outline(pic.a[..., 3] > 0) & (ys < tt + 1) & (xs >= tx0 - 1) & (xs <= tx0 + tw), OUTLINE)
        pic.rect(tx0 + tw // 2, 0, tx0 + tw // 2 + 1, 2, (200, 170, 90))  # the finial
        pic.rect(tx0, tt, tx0 + tw, tt + 1, OUTLINE)
    # Dormers on long roofs of inns and halls; chimneys.
    if kind in ("inn", "hall") and form not in ("front",) and W >= 6 * r:
        for k in range(2):
            dx0 = int(W * (0.2 + 0.5 * k))
            dy0 = E + int((ry1 - E) * 0.5)
            dw_ = max(4, r // 2)
            pic.rect(dx0 - 1, dy0 - 3, dx0 + dw_ + 1, dy0 + dw_, OUTLINE)
            pic.rect(dx0, dy0 - 2, dx0 + dw_, dy0 + dw_ - 1, WALLS[wall][0])
            _window(pic, dx0 + 1, dy0, dw_ - 2, dw_ - 3, frame, None, glow)
            for i in range(dw_ // 2 + 1):
                pic.rect(dx0 - 1 + i, dy0 - 3 - (dw_ // 2) + i, dx0 + dw_ + 1 - i, dy0 - 2 - (dw_ // 2) + i, dark)
    if chimney and form not in ("keep",):
        fx, fy = chimney_spot(w, h, seed, form)
        _chimney(pic, int(W * fx), E + int((Hb) * fy) - r // 4, r, wall)
    if kind == "smithy" and form not in ("keep",):
        _chimney(pic, int(W * 0.15), E + r // 3, r + r // 2, "stone")
    if kind in ("store", "healer", "market") and side == "south":
        colour = AWNINGS[seed % len(AWNINGS)] if kind != "healer" else (60, 120, 70)
        _awning(pic, door_x + r // 2, wall_top, r, colour)
    # Ink along the eaves and around the whole building.
    solid = pic.a[..., 3] > 0
    eaves = (ys == ry1 - 1) & roof & solid
    pic.a[eaves, :3] = (np.asarray(pic.a[eaves, :3], np.float32) * 0.55).astype(np.uint8)
    edge = solid & ~(np.roll(solid, 1, 0) & np.roll(solid, -1, 0) & np.roll(solid, 1, 1) & np.roll(solid, -1, 1))
    edge[0, :] |= solid[0, :]
    edge[-1, :] |= solid[-1, :]
    edge[:, 0] |= solid[:, 0]
    edge[:, -1] |= solid[:, -1]
    pic.a[edge, :3] = OUTLINE
    # A door on another side: a gap in the eaves where it is, so it is plain where to go in.
    if side != "south":
        gx0, gy0 = dx * r, E + dy * r
        gx1, gy1 = gx0 + r, gy0 + r
        if side == "north":
            gy1 = gy0 + r // 2 + 2
        elif side == "west":
            gx1 = gx0 + r // 2 + 2
        else:
            gx0 = gx1 - r // 2 - 2
        pic.a[gy0:gy1, gx0:gx1] = 0
        hole = np.zeros(solid.shape, bool)
        hole[max(0, gy0):gy1, max(0, gx0):gx1] = True
        pic.a[_outline(hole) & solid, :3] = OUTLINE
    return pic.a, (glow.a if glow is not None and glow.a[..., 3].any() else None)


def smoke_puff():
    from PIL import Image, ImageDraw, ImageFilter

    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([6, 6, 26, 26], fill=(200, 200, 205, 200))
    return im.filter(ImageFilter.GaussianBlur(4))
