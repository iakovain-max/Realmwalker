"""Buildings of other peoples, seen from the street a little from the south, in sharp pixels (roofs.py draws the
gabled houses of the Heartland and its like; this draws the rest): flat roofs behind a parapet with a dome or two,
onion domes over a log church, felt yurts, round thatched huts, turf-roofed long halls with carved gable heads, the
crowns of the elves' tree homes, the grassy mounds of halfling burrows, and houses round an open court.

Each returns (picture, window glow or None) as roofs.building does: (H, W, 4) uint8, H = h * r + extra rows above.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

OUTLINE = (34, 26, 20)
LAMP = (255, 196, 110)
GLASS = (40, 44, 52)

ROOF = {
    "flat": ((226, 218, 200), (196, 186, 166), (244, 240, 230)),
    "dome": ((236, 232, 222), (196, 190, 178), (252, 250, 244)),
    "dome_blue": ((70, 110, 180), (48, 78, 140), (120, 160, 220)),
    "onion": ((90, 120, 80), (66, 90, 60), (120, 150, 104)),
    "felt": ((222, 210, 186), (190, 176, 150), (240, 232, 214)),
    "felt_white": ((240, 236, 226), (206, 198, 184), (252, 250, 246)),
    "thatch_round": ((186, 152, 90), (140, 108, 62), (214, 184, 120)),
    "leaves": ((70, 120, 76), (50, 92, 58), (110, 160, 110)),
    "mound": ((96, 140, 72), (72, 110, 54), (132, 170, 96)),
    "hide": ((150, 116, 80), (116, 88, 60), (178, 144, 104)),
}
FACE = {
    "whitewash": ((240, 238, 230), (190, 184, 170)), "mudbrick": ((196, 160, 110), (150, 118, 80)),
    "sandstone": ((214, 186, 132), (170, 142, 96)), "marble": ((234, 230, 222), (190, 186, 178)),
    "limestone": ((228, 220, 196), (182, 174, 150)), "dark_wood": ((96, 70, 48), (70, 50, 34)),
    "felt": ((222, 210, 186), (176, 160, 134)), "living_wood": ((150, 160, 170), (110, 118, 128)),
    "earth": ((96, 140, 72), (72, 106, 54)), "plaster": ((222, 208, 178), (176, 160, 132)),
    "ochre": ((214, 184, 128), (170, 142, 96)), "rose": ((214, 180, 164), (170, 138, 124)),
    "brick": ((156, 86, 64), (118, 62, 48)), "stone": ((152, 146, 134), (118, 112, 102)),
    "logs": ((132, 94, 60), (104, 72, 46)), "dark_stone": ((112, 108, 104), (88, 84, 80)),
    "rock": ((112, 108, 104), (88, 84, 80)),
}
FORMS = ("flat", "dome", "onion", "round", "tree", "mound", "court", "long_turf", "none")


def form_of(shape: str, roof: str, kind: str) -> str | None:
    """The form a building takes in this module, or None for roofs.py's own (gables and hips)."""
    if shape == "carved" or roof == "none":
        return "none"
    if shape == "tree" or roof == "leaves":
        return "tree"
    if shape == "mound" or roof == "mound":
        return "mound"
    if shape == "round":
        return "round"
    if shape == "court":
        return "court"
    if roof == "onion":
        return "onion"
    if roof in ("dome", "dome_blue"):
        return "dome"
    if roof == "flat":
        return "flat"
    if roof == "turf" and shape == "long":
        return "long_turf"
    return None


def _round_wall(r: int) -> int:
    """The height of a round hut's wall in pixels (its roof is drawn that much above its ground)."""
    return max(4, int(r * 0.75))


def extra_top(form: str, r: int, kind: str = "") -> int:
    return {"dome": r, "onion": 2 * r, "tree": r, "round": _round_wall(r) + 1, "long_turf": max(3, r // 3) + 1}.get(form, 0) + \
        (r if form in ("flat", "court") and kind in ("temple",) else 0)


def smoke_spot(form: str, w: int, h: int, r: int, kind: str = "") -> tuple[float, float] | None:
    """Where smoke comes out of this building, as fractions of its squares (x across, y down; above 0 is over the
    squares north of it), or None: a long hall's smoke hole, a tent's crown, a burrow's chimney pot."""
    E = extra_top(form, r, kind)
    Hb = h * r
    if form == "long_turf":
        fh = r + r // 2 if h >= 5 else r + r // 4
        return (1 / 3 if w >= 9 else 0.5), ((Hb - fh) / 2 - E * 0) / Hb
    if form == "round":
        return 0.5, (Hb / 2 - _round_wall(r) - r * 0.85) / Hb
    if form == "mound":
        return 0.7, 0.3
    return None


def _sh(rgb, k: float):
    return tuple(int(max(0, min(255, c * k))) for c in rgb[:3])


class _Pic:
    def __init__(self, w: int, h: int) -> None:
        self.a = np.zeros((h, w, 4), np.uint8)
        self.w, self.h = w, h
        self.ys, self.xs = np.mgrid[0:h, 0:w]

    def rect(self, x0, y0, x1, y1, rgb, alpha: int = 255) -> None:
        x0, y0 = max(0, int(x0)), max(0, int(y0))
        x1, y1 = min(self.w, int(x1)), min(self.h, int(y1))
        if x1 > x0 and y1 > y0:
            self.a[y0:y1, x0:x1, :3] = rgb[:3]
            self.a[y0:y1, x0:x1, 3] = alpha

    def mask(self, m, rgb) -> None:
        self.a[m, :3] = rgb[:3]
        self.a[m, 3] = 255

    def px(self, x, y, rgb) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[int(y), int(x), :3] = rgb[:3]
            self.a[int(y), int(x), 3] = 255

    def ellipse(self, cx, cy, rx, ry) -> np.ndarray:
        return ((self.xs - cx + 0.5) / max(0.5, rx)) ** 2 + ((self.ys - cy + 0.5) / max(0.5, ry)) ** 2 <= 1.0


def _ink(pic: _Pic) -> None:
    solid = pic.a[..., 3] > 0
    edge = solid & ~(np.roll(solid, 1, 0) & np.roll(solid, -1, 0) & np.roll(solid, 1, 1) & np.roll(solid, -1, 1))
    edge[0, :] |= solid[0, :]
    edge[-1, :] |= solid[-1, :]
    edge[:, 0] |= solid[:, 0]
    edge[:, -1] |= solid[:, -1]
    pic.a[edge, :3] = OUTLINE


def _front(pic: _Pic, x0, y0, x1, y1, wall: str, r: int, door_x: int | None, kind: str, rng, glow) -> None:
    """The front wall: its face, small deep windows, the door."""
    face, shade = FACE.get(wall, FACE["plaster"])
    pic.rect(x0, y0, x1, y1, face)
    pic.rect(x0, y1 - 1, x1, y1, shade)
    if wall in ("logs", "dark_wood"):
        pic.a[(pic.ys >= y0) & (pic.ys < y1) & (pic.xs >= x0) & (pic.xs < x1) & ((pic.ys - y0) % 3 == 2), :3] = shade
    if wall in ("mudbrick", "sandstone"):
        speck = rng.random((pic.h, pic.w)) < 0.05
        pic.a[speck & (pic.ys >= y0) & (pic.ys < y1) & (pic.xs >= x0) & (pic.xs < x1), :3] = shade
    ww, wh = max(2, r // 4), max(3, r // 3)
    for cx in range(x0 + r // 2, x1 - r // 2, max(r, 2 * r - 2)):
        if door_x is not None and abs(cx - (door_x + r // 2)) < r:
            continue
        top = y0 + (y1 - y0 - wh) // 2 - 1
        pic.rect(cx - ww // 2, top, cx - ww // 2 + ww, top + wh, GLASS)
        if wall in ("whitewash", "marble", "limestone", "sandstone", "mudbrick"):  # a pointed or round head
            pic.px(cx - ww // 2 + ww // 2, top - 1, GLASS)
        if glow is not None:
            glow.rect(cx - ww // 2, top, cx - ww // 2 + ww, top + wh, LAMP)
    if door_x is not None:
        dw, dh = max(4, int(r * 0.5)) | 1, max(6, int(r * 0.8))
        dx0 = door_x + (r - dw) // 2
        wood = (112, 76, 46) if wall not in ("felt",) else (170, 60, 44)
        pic.rect(dx0 - 1, y1 - dh - 1, dx0 + dw + 1, y1, OUTLINE)
        pic.rect(dx0, y1 - dh, dx0 + dw, y1, wood)
        if wall in ("whitewash", "marble", "sandstone", "mudbrick", "limestone"):  # an arch over it
            pic.px(dx0, y1 - dh, OUTLINE)
            pic.px(dx0 + dw - 1, y1 - dh, OUTLINE)
        pic.px(dx0 + dw - 2, y1 - dh // 2, (210, 190, 120))


@lru_cache(maxsize=384)
def draw(w: int, h: int, r: int, roof: str, wall: str, form: str, kind: str, door: tuple[int, int], seed: int,
         lit: bool):
    rng = np.random.default_rng(seed)
    E = extra_top(form, r, kind)
    W, Hb = w * r, h * r
    pic = _Pic(W, Hb + E)
    glow = _Pic(W, Hb + E) if lit else None
    if form == "none":
        return pic.a, None
    if roof in ROOF:
        base, dark, light = ROOF[roof]
    else:  # a roof of the old kinds (thatch, slate, shingle...) on a round hut or a long hall
        from realmwalker.ui.gfx import roofs

        base, dark, light = roofs.STYLES.get(roof, ROOF["flat"])
    dx, dy = door
    door_x = dx * r if dy == h - 1 else None
    fh = r + r // 2 if h >= 5 else r + r // 4  # the front wall's height in pixels
    fy0, fy1 = E + Hb - fh, E + Hb
    if form in ("flat", "dome", "court"):
        _front(pic, 0, fy0, W, fy1, wall, r, door_x, kind, rng, glow)
        if roof == "flat" and wall in ("mudbrick", "sandstone", "ochre"):  # a roof of the same earth as the walls
            base, dark, light = (214, 194, 156), (180, 160, 124), (232, 216, 184)
        top = (pic.ys >= E) & (pic.ys < fy0 + 1)
        pic.mask(top, base)
        speck = rng.random((pic.h, pic.w))
        pic.mask(top & (speck < 0.05), _sh(base, 0.94))  # the plaster patched and weathered
        rim = top & ((pic.ys < E + 2) | (pic.xs < 2) | (pic.xs >= W - 2) | (pic.ys >= fy0 - 1))
        pic.mask(rim, light)
        pic.mask(top & ~rim & ((pic.ys == E + 2) | (pic.xs == 2)), _sh(base, 0.82))  # the parapet's shadow
        if form == "court":  # the open court in the middle, its fountain or tree
            depth = 2 * r if min(w, h) >= 11 else int(1.6 * r)
            cx0, cy0, cx1, cy1 = depth, E + depth, W - depth, fy0 - depth // 2
            if cx1 - cx0 > 4 and cy1 - cy0 > 4:
                court = (pic.xs >= cx0) & (pic.xs < cx1) & (pic.ys >= cy0) & (pic.ys < cy1)
                pic.mask(court, (186, 174, 150))
                tiles = court & (((pic.xs - cx0) // 3 + (pic.ys - cy0) // 3) % 2 == 0)
                pic.mask(tiles, (200, 188, 164))
                inner_rim = (pic.xs >= cx0 - 1) & (pic.xs < cx1 + 1) & (pic.ys >= cy0 - 1) & (pic.ys < cy1 + 1) & ~court
                pic.mask(inner_rim, _sh(base, 0.8))
                mx, my = (cx0 + cx1) // 2, (cy0 + cy1) // 2
                if seed % 2:  # a fountain
                    pic.mask(pic.ellipse(mx, my, 3, 2), (90, 150, 190))
                    pic.px(mx, my - 1, (230, 240, 250))
                else:  # a palm
                    pic.mask(pic.ellipse(mx, my, 3, 3), (70, 120, 60))
                    pic.mask(pic.ellipse(mx - 1, my - 1, 1.5, 1.5), (110, 160, 80))
        else:  # things on a flat roof: a stair hatch, jars, a rug airing, a water tank, an awning, a line of washing
            hx = int(W * (0.2 + 0.5 * rng.random()))
            pic.rect(hx - 1, E + r // 2 - 1, hx + max(3, r // 3) + 1, E + r // 2 + max(2, r // 4) + 1, _sh(base, 0.8))
            pic.rect(hx, E + r // 2, hx + max(3, r // 3), E + r // 2 + max(2, r // 4), (70, 56, 44))
            homely = kind not in ("temple", "hall", "keep", "library", "bank")
            for _ in range(int(rng.integers(1, 4)) if homely else 0):  # clay jars
                jx = int(rng.integers(4, max(5, W - 6)))
                jy = int(rng.integers(E + 4, max(E + 5, fy0 - 5)))
                pic.mask(pic.ellipse(jx, jy, 1.6, 1.6), (176, 104, 64))
                pic.px(jx - 1, jy - 1, (214, 150, 104))
            if homely and W > 2 * r and rng.random() < 0.5:  # a rug airing over the parapet
                rx0 = int(rng.integers(3, max(4, W - r)))
                rw, rh = max(4, r // 2), max(3, r // 3)
                ry0 = fy0 - rh - 1
                col = ((150, 50, 44), (60, 62, 120), (170, 120, 50))[int(rng.integers(0, 3))]
                pic.rect(rx0, ry0, rx0 + rw, ry0 + rh, col)
                pic.rect(rx0, ry0 + 1, rx0 + rw, ry0 + 2, (224, 190, 110))
                pic.rect(rx0, ry0 + rh - 2, rx0 + rw, ry0 + rh - 1, (224, 190, 110))
            if rng.random() < 0.25:  # a water tank
                tx, ty = int(W * 0.78), E + max(4, r // 2)
                pic.mask(pic.ellipse(tx, ty, max(2, r // 4), max(2, r // 5)), (110, 122, 130))
                pic.mask(pic.ellipse(tx - 0.5, ty - 0.5, max(1, r // 6), max(1, r // 8)), (70, 96, 120))
            if homely and W > 3 * r and rng.random() < 0.3:  # a striped awning for the heat of the day
                ax0, aw = int(W * 0.15), max(6, int(W * 0.3))
                ay0 = E + max(3, int((fy0 - E) * 0.2))
                for k in range(aw):
                    pic.rect(ax0 + k, ay0, ax0 + k + 1, ay0 + max(3, r // 3),
                             (200, 70, 50) if (k // 2) % 2 else (236, 226, 204))
            if homely and W > 3 * r and rng.random() < 0.6:
                ly = E + int((fy0 - E) * 0.55)
                for x in range(r, W - r):
                    pic.px(x, ly + (1 if (x // 3) % 2 else 0), (120, 110, 100))
                for x in range(r + 2, W - r - 2, 5):
                    pic.rect(x, ly + 1, x + 3, ly + 4, ((170, 60, 50), (60, 90, 150), (220, 210, 180))[x % 3])
        if form == "dome":  # a dome, or two, raised on the roof
            dr = max(r // 2, min(W // 3, (fy0 - E)) // 2 + (r // 2 if kind in ("temple", "hall") else 0))
            mx, my = W // 2, E + dr + (r // 3)
            dome = pic.ellipse(mx, my, dr, dr) & (pic.ys <= my)
            drum = (pic.xs >= mx - dr) & (pic.xs < mx + dr) & (pic.ys > my) & (pic.ys <= my + max(2, r // 4))
            dcol = ROOF.get(roof if roof.startswith("dome") else "dome")
            stone = FACE.get(wall, FACE["whitewash"])[0]
            pic.mask(drum, _sh(stone, 0.9))
            pic.mask(drum & (pic.xs > mx + dr // 2), _sh(stone, 0.75))
            pic.mask(pic.ellipse(mx, my, dr + 1, dr + 1) & (pic.ys <= my + 1), _sh(dcol[1], 0.7))  # its rim
            pic.mask(dome, dcol[0])
            pic.mask(dome & ~pic.ellipse(mx - dr * 0.25, my - dr * 0.1, dr * 0.85, dr * 1.05), dcol[1])
            pic.mask(dome & pic.ellipse(mx - dr * 0.4, my - dr * 0.55, dr * 0.3, dr * 0.25), dcol[2])
            pic.rect(mx, my - dr - max(2, r // 3), mx + 1, my - dr, (210, 180, 90))  # the finial
            pic.rect(mx - 1, my - dr - max(2, r // 3) + 1, mx + 2, my - dr - max(2, r // 3) + 2, (210, 180, 90))
            if kind == "temple" and W > 4 * r:  # and a slender tower beside it, with a balcony and a pointed cap
                tw = max(4, r // 3)
                tx = W - r - tw // 2 if seed % 2 else r // 2
                top = max(5, E // 3)
                col = _sh(stone, 0.95)
                pic.rect(tx - 1, top - 1, tx + tw + 1, fy0, OUTLINE)
                pic.rect(tx, top, tx + tw, fy0, col)
                pic.rect(tx + tw - 1, top, tx + tw, fy0, _sh(col, 0.8))
                by = top + (fy0 - top) // 4
                pic.rect(tx - 2, by - 1, tx + tw + 2, by + 2, OUTLINE)
                pic.rect(tx - 1, by, tx + tw + 1, by + 1, _sh(col, 0.85))
                cap = max(3, tw)
                for k in range(cap):
                    half = (tw / 2 + 1) * (1 - k / cap)
                    pic.rect(int(tx + tw / 2 - half), top - 1 - k, int(tx + tw / 2 + half + 0.5), top - k, dcol[0])
    elif form == "onion":  # a log church under green shingles, its onion domes gold and blue
        from realmwalker.ui.gfx import roofs

        under, under_glow = roofs.building(w, h, r, "shingle", wall if wall in roofs.WALLS else "logs", "hip", kind, door,
                                           seed, False, lit)
        pic.a[E:E + under.shape[0], :under.shape[1]] = under[:pic.h - E]
        if glow is not None and under_glow is not None:
            glow.a[E:E + under_glow.shape[0], :under_glow.shape[1]] = under_glow[:pic.h - E]
        ridge_y = E + int((fy0 - E) * 0.4)
        domes = [(W // 2, max(4, int(r * 0.9))), (max(4, W // 5), max(3, r // 2 + 1)), (W - max(4, W // 5), max(3, r // 2 + 1))]
        for i, (mx, dr) in enumerate(domes):
            drum_h = max(3, r // 2) + (r // 2 if i == 0 else 0)
            drum_top = ridge_y - drum_h
            pic.rect(mx - dr // 2, drum_top, mx + dr // 2 + 1, ridge_y + 2, (236, 232, 222))  # the drum
            pic.rect(mx - dr // 2, drum_top, mx - dr // 2 + 1, ridge_y + 2, (200, 196, 186))
            cy = drum_top - dr * 0.55
            onion = pic.ellipse(mx + 0.5, cy, dr * 0.7, dr * 0.75)
            col = (214, 172, 60) if i == 0 else (60, 100, 170)
            pic.mask(onion, col)
            pic.mask(onion & (pic.xs > mx), _sh(col, 0.78))
            pic.mask(onion & (pic.xs < mx - dr * 0.25) & (pic.ys < cy), _sh(col, 1.2))
            tip = int(cy - dr * 0.75)
            for k in range(max(2, dr // 2)):  # the point drawn up from the bulb, and its cross
                pic.px(mx, tip - k, col)
            pic.rect(mx - 1, tip - dr // 2 - 1, mx + 2, tip - dr // 2, (230, 210, 120))
            pic.rect(mx, tip - dr // 2 - 3, mx + 1, tip - dr // 2 + 1, (230, 210, 120))
    elif form == "round":  # a yurt of felt, a round hut of thatch or hide: its roof from above, its wall below
        mx = W / 2
        felt = roof.startswith("felt")
        wall_h = _round_wall(r)
        over = 0 if felt else max(1, r // 5)  # thatch eaves hang over the wall
        rx, ry = W / 2 - 0.5, Hb / 2 - 0.5
        gcy = E + Hb / 2  # the middle of the ground it stands on
        tcy = gcy - wall_h  # the middle of the top of its wall
        face, shade = FACE.get(wall, FACE["felt"])
        y = pic.ys + 0.5
        u = (pic.xs + 0.5 - mx) / rx
        s = np.sqrt(np.clip(1 - u ** 2, 0, 1))
        drum = (np.abs(u) <= 1) & (y >= tcy - ry * s) & (y <= gcy + ry * s)
        pic.mask(drum, face)
        pic.mask(drum & (u > 0.4), shade)
        low = gcy + ry * s - y  # how high up the wall
        if felt:  # the ropes round a yurt
            pic.mask(drum & ((np.abs(low - wall_h * 0.3) < 0.6) | (np.abs(low - wall_h * 0.62) < 0.6)), (150, 60, 50))
        elif wall in ("plaster", "limestone", "whitewash", "ochre"):  # a painted band along the foot
            pic.mask(drum & (low < 1.6), (164, 70, 50))
        roof_m = (np.abs(u) <= 1) & (np.abs(y - tcy - over / 2) <= (ry + over / 2) * s)
        ax, ay = mx, tcy - (r * 0.3 if felt else r * 0.85)  # the crown of the roof, seen a little from the south
        vx, vy = pic.xs + 0.5 - ax, (y - ay) * (W / max(1.0, Hb))
        dist = np.sqrt(vx ** 2 + vy ** 2) + 1e-6
        lum = -(vx * 0.7 + vy * 0.7) / dist  # the light from the north-west
        pic.mask(roof_m, dark)
        pic.mask(roof_m & (lum > -0.3), base)
        pic.mask(roof_m & (lum > 0.45), light)
        ang = np.arctan2(vy, vx)
        if felt:  # straps over the felt from the crown, a worked band round it, the crown ring round its smoke hole
            pic.mask(roof_m & ((ang * 8 / (2 * np.pi)) % 1 < 0.06), _sh(base, 0.82))
            rel = np.sqrt(((pic.xs + 0.5 - mx) / rx) ** 2 + ((y - tcy) / max(1.0, ry)) ** 2)
            band = roof_m & (rel > 0.8) & (rel < 0.9)
            pic.mask(band, (150, 52, 44) if roof == "felt_white" else (60, 70, 130))
            pic.mask(band & ((pic.xs + pic.ys) % 3 == 0), (224, 184, 84))
            pic.mask(pic.ellipse(ax, ay, max(2, W // 10), max(1.5, W // 16)), (150, 110, 70))
            pic.mask(pic.ellipse(ax, ay, max(1, W // 16), max(1, W // 24)), (60, 50, 44))
        else:  # thatch: streaks down from the crown, courses round it, the eaves' edge, a knot on top
            pic.mask(roof_m & ((ang * 28 / (2 * np.pi)) % 1 < 0.2), _sh(base, 0.86))
            pic.mask(roof_m & ((dist / max(3.0, r * 1.5)) % 1 < 0.08), _sh(base, 0.9))
            pic.mask(roof_m & (np.abs(y - (tcy + over / 2 + (ry + over / 2) * s)) < 1.0), _sh(dark, 0.8))
            pic.mask(pic.ellipse(ax, ay, max(1.5, r * 0.18), max(1.5, r * 0.14)), _sh(dark, 0.85))
            pic.rect(int(ax), int(ay - r * 0.3), int(ax) + 1, int(ay), (100, 76, 50))
        if dy >= h - 2:  # the doorway at the front, under the eaves
            ux = float(np.clip((dx * r + r / 2 - mx) / rx, -0.6, 0.6))
            foot = int(gcy + ry * np.sqrt(1 - ux ** 2))
            dw = max(3, r // 3) | 1
            dh = max(4, wall_h - over + 1)
            x0 = int(mx + ux * rx - dw / 2)
            pic.rect(x0 - 1, foot - dh - 1, x0 + dw + 1, foot + 1, OUTLINE)
            pic.rect(x0, foot - dh, x0 + dw, foot + 1, (176, 70, 44) if felt else (70, 52, 38))
            if felt:
                pic.rect(x0, foot - dh, x0 + dw, foot - dh + 1, (220, 180, 80))
            if glow is not None:
                glow.rect(x0 + 1, foot - dh + 1, x0 + dw - 1, foot, LAMP)
        if not felt and wall_h - over >= 3:  # small windows either side
            for sx in (-0.6, 0.6):
                wx = int(mx + rx * sx)
                wy = int(gcy + ry * np.sqrt(1 - sx ** 2) - (wall_h - over) / 2 - 1)
                pic.rect(wx - 1, wy, wx + 1, wy + 2, GLASS)
                if glow is not None:
                    glow.rect(wx - 1, wy, wx + 1, wy + 2, LAMP)
    elif form == "tree":  # a home in the trunk of a giant tree: its crown from above, its foot and door below
        mx = W / 2
        face, shade = FACE.get(wall, FACE["living_wood"])
        if seed % 10 >= 7:  # a golden tree among the green
            base, dark, light = (196, 164, 72), (150, 120, 50), (232, 206, 120)
        ground = E + Hb
        y = pic.ys + 0.5
        tw = max(4.0, W * 0.3)
        rise = np.clip((y - (ground - 1.6 * r)) / (1.6 * r), 0, 1)  # the foot flares out into roots
        trunk = (np.abs(pic.xs + 0.5 - mx) <= tw / 2 + rise ** 2 * W * 0.14) & (y >= E + r) & (y < ground)
        pic.mask(trunk, face)
        pic.mask(trunk & (pic.xs + 0.5 > mx + tw * 0.2), shade)
        pic.mask(trunk & ((pic.xs + pic.ys // 4) % 4 == 0), _sh(face, 0.9))  # the bark's long grain
        for side in (-1, 1):  # roots over the ground
            pic.mask(pic.ellipse(mx + side * (tw * 0.5 + W * 0.12), ground - 1.5, W * 0.12, 1.6), shade)
        box = ground - 1.3 * r  # the crown hangs down to here
        blobs = [(0.32, 0.3, 0.26, 0.26), (0.68, 0.3, 0.26, 0.26), (0.5, 0.18, 0.26, 0.2), (0.5, 0.5, 0.46, 0.38),
                 (0.2, 0.6, 0.22, 0.28), (0.8, 0.6, 0.22, 0.28), (0.5, 0.8, 0.3, 0.2)]
        crown = np.zeros((pic.h, pic.w), bool)
        for bx, by, brx, bry in blobs:  # heaps of leaves, the lower over the higher, each lit from the north-west
            cx_, cy_ = W * bx + rng.uniform(-1, 1), box * by + rng.uniform(-1, 1)
            rx_, ry_ = W * brx, box * bry
            m = pic.ellipse(cx_, cy_, rx_, ry_)
            crown |= m
            pic.mask(m, dark)
            pic.mask(m & pic.ellipse(cx_ - rx_ * 0.15, cy_ - ry_ * 0.2, rx_ * 0.8, ry_ * 0.75), base)
            pic.mask(m & pic.ellipse(cx_ - rx_ * 0.38, cy_ - ry_ * 0.42, rx_ * 0.38, ry_ * 0.32), light)
        speck = rng.random((pic.h, pic.w))
        pic.mask(crown & (speck < 0.05), _sh(dark, 0.82))
        pic.mask(crown & (speck > 0.975), _sh(light, 1.08))
        dw, dh = max(3, r // 3) | 1, max(5, int(r * 0.8))
        x0 = int(np.clip(dx * r + r / 2, mx - tw / 2 + 2, mx + tw / 2 - 2) - dw / 2)
        pale = (214, 220, 214)
        pic.rect(x0 - 1, ground - dh - 1, x0 + dw + 1, ground, pale)  # a pale carved frame, the arch pointed
        pic.rect(x0, ground - dh, x0 + dw, ground, (104, 78, 54))
        pic.px(x0, ground - dh, pale)
        pic.px(x0 + dw - 1, ground - dh, pale)
        pic.px(x0 + dw // 2, ground - dh - 2, pale)
        for _ in range(4 + w // 2):  # lanterns hung in the branches
            lx, ly = int(rng.integers(2, W - 2)), int(rng.integers(2, max(3, int(box * 0.9))))
            if crown[ly, lx]:
                pic.px(lx, ly, (220, 250, 230))
                pic.px(lx, ly + 1, (160, 210, 190))
                if glow is not None:
                    glow.px(lx, ly, (200, 255, 230))
        if glow is not None:
            glow.rect(x0, ground - dh, x0 + dw, ground, LAMP)
    elif form == "mound":  # a burrow: a low grassy hill seen from above, its round door and windows at the front
        mx = W / 2
        ground = E + Hb
        u = (pic.xs + 0.5 - mx) / (W / 2)
        v = (pic.ys + 0.5 - (E + Hb / 2)) / (Hb / 2)
        hill = np.abs(u) ** 2.6 + np.abs(v) ** 2.6 <= 1.0
        g_base, g_dark, g_light = (96, 128, 70), (72, 100, 54), (122, 150, 88)
        lum = (1 - np.clip(u ** 2 + v ** 2, 0, 1)) * 0.7 - (u + v) * 0.3
        pic.mask(hill, g_dark)
        pic.mask(hill & (lum > 0.1), g_base)
        pic.mask(hill & (lum > 0.52), g_light)
        speck = rng.random((pic.h, pic.w))
        pic.mask(hill & (speck < 0.06), _sh(g_dark, 0.88))
        pic.mask(hill & (speck > 0.992), ((230, 210, 120), (220, 120, 140), (240, 240, 230))[seed % 3])  # flowers
        dr = max(3, int(r * 0.42))
        ddx = float(np.clip(dx * r + r / 2, mx - W * 0.2, mx + W * 0.2)) if dy >= h - 2 else mx
        dcy = ground - dr - 1
        door_col = ((60, 110, 60), (170, 60, 50), (60, 80, 150), (190, 150, 60))[seed % 4]
        if dy >= h - 2:  # the round door at the front, in a face of stone set in the hill
            face_m = pic.ellipse(ddx, dcy + 1, dr * 2.3, dr * 1.7) & hill
            pic.mask(face_m, (150, 136, 112))
            pic.mask(face_m & (pic.xs + 0.5 > ddx + dr), (124, 112, 92))
            pic.mask(pic.ellipse(ddx, dcy, dr + 1, dr + 1), OUTLINE)
            pic.mask(pic.ellipse(ddx, dcy, dr, dr), door_col)
            pic.px(int(ddx), int(dcy), (230, 200, 80))  # the knob in the middle
        for sx in (-1, 1):  # round windows either side
            wx, wy = ddx + sx * dr * 3.0, dcy - 1
            pane = pic.ellipse(wx, wy, dr * 0.42, dr * 0.42) & hill
            pic.mask(pic.ellipse(wx, wy, dr * 0.62, dr * 0.62) & hill, (120, 90, 60))
            pic.mask(pane, GLASS)
            if glow is not None:
                glow.mask(pane, LAMP)
        cx_, cy_ = int(mx + W * 0.2), int(E + Hb * 0.3)  # the chimney pot
        pic.rect(cx_, cy_, cx_ + max(2, r // 6), cy_ + max(3, r // 4), (150, 90, 66))
        pic.rect(cx_, cy_, cx_ + max(2, r // 6), cy_ + 1, (96, 60, 44))
    elif form == "long_turf":  # a long hall under turf, with carved beasts' heads at the gable ends
        _front(pic, 0, fy0, W, fy1, wall, r, door_x, kind, rng, glow)
        top = (pic.ys >= E) & (pic.ys < fy0)
        ridge = E + (fy0 - E) // 2
        curve = np.abs(pic.xs + 0.5 - W / 2) / (W / 2)
        sag = (curve ** 2 * r * 0.35).astype(int)  # the ridge sags a little in the middle, like a boat upside down
        north = top & (pic.ys < ridge - sag)
        pic.mask(top, base)
        pic.mask(north, dark)
        speck = rng.random((pic.h, pic.w))
        pic.mask(top & ~north & (speck < 0.09), _sh(base, 1.12))  # tufts in the sun
        pic.mask(north & (speck < 0.07), _sh(dark, 0.85))
        pic.mask(top & (speck > 0.993), ((236, 214, 110), (240, 240, 228), (200, 120, 170))[seed % 3])  # flowers
        pic.mask(top & (np.abs(pic.ys - (ridge - sag)) < 1), _sh(base, 1.25))  # the ridge, dry and pale
        pic.rect(0, fy0 - 1, W, fy0, (82, 60, 40))  # the eaves board
        pic.rect(0, fy0, W, fy0 + 1, _sh(FACE.get(wall, FACE["logs"])[1], 0.7))  # and its shadow on the wall
        for hx in (W // 3, 2 * W // 3) if w >= 9 else (W // 2,):  # smoke holes along the ridge
            pic.rect(hx - 1, ridge - int(sag[0, min(W - 1, hx)]) - 1, hx + 2, ridge - int(sag[0, min(W - 1, hx)]) + 1,
                     (52, 42, 34))
        wood = (96, 70, 46)
        for gx in (0, W - 3):  # the gable boards, crossed above the ridge into beasts' heads
            pic.rect(gx, E, gx + 3, fy0, _sh(wood, 0.9))
            pic.rect(gx + 1, E, gx + 2, fy0, wood)
            for k in range(max(3, r // 3)):
                pic.px(gx + 1 + (k if gx == 0 else -k), E - 1 - k, wood)
                pic.px(gx + 2 + (k if gx == 0 else -k), E - 1 - k, _sh(wood, 0.8))
    _ink(pic)
    if form in ("round", "tree", "mound"):
        if dy < h - 2:  # a door at the back or the side shows as a gap in the roof
            gx0, gy0 = dx * r, E + dy * r
            pic.a[gy0:gy0 + r, gx0:gx0 + r] = 0
    elif door_x is None:  # a door on another side shows as a gap
        gx0, gy0 = dx * r, E + dy * r
        pic.a[gy0:gy0 + r // 2 + 2, gx0:gx0 + r] = 0 if dy == 0 else pic.a[gy0:gy0 + r // 2 + 2, gx0:gx0 + r]
    return pic.a, (glow.a if glow is not None and glow.a[..., 3].any() else None)
