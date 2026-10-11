"""Pictures of the things in towns, drawn in code for tools/build_tiles.py: walls and floors of each people's
buildings (whitewash, mud brick, logs, felt, turf, tiles, rugs, boardwalks, white causeways), the furniture of their
rooms (stools, chairs, benches, counters, shelves, bookcases, wardrobes, trunks, ovens, pews, candles, thrones,
banners, tapestries, weapon racks, armour stands, lecterns, cauldrons...) and the things in their streets (lamp posts,
lanterns, braziers, torches, fire pits, fountains, statues, standing stones, runestones, stelae, horsetail standards,
beehives, skull posts...). 32x32, the same hand as tools/tile_art.py.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from tile_art import S, arr, blank, img, noise_shade, outline, rng, shade, shadow


def c(rgb, a: int = 255) -> tuple:
    return tuple(int(v) for v in rgb[:3]) + (a,)


def _ground(seed: int, base, spread: float = 0.06) -> np.ndarray:
    r = rng(seed)
    n = r.normal(0, 1, (S, S))
    n = (n + np.roll(n, 1, 0) + np.roll(n, 1, 1) + np.roll(n, (1, 1), (0, 1))) / 4
    a = np.zeros((S, S, 4), np.float32)
    a[..., :3] = np.array(base, np.float32) * (1 + spread * n[..., None])
    a[..., 3] = 255
    return a


# ---------------------------------------------------------------------------- walls
def wall_courses(seed: int, base, joint, course: int = 6, brick: int = 10, light_top=True) -> Image.Image:
    """A wall of blocks in courses, the joints a darker line, the top lit."""
    r = rng(seed)
    a = _ground(seed, base, 0.05)
    for y in range(S):
        row = y // course
        for x in range(S):
            if y % course == 0 or (x + row * (brick // 2)) % brick == 0:
                a[y, x, :3] = joint
    if light_top:
        a[:2, :, :3] = np.clip(a[:2, :, :3] * 1.15, 0, 255)
    for _ in range(6):
        x, y = int(r.integers(0, S)), int(r.integers(0, S))
        a[y, x, :3] = np.clip(a[y, x, :3] * 1.12, 0, 255)
    return img(a)


def plaster_wall(seed: int, base=(222, 208, 178), beam=(98, 68, 46)) -> Image.Image:
    """Plaster between oak beams."""
    a = _ground(seed, base, 0.04)
    im = img(a)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, S - 1, 2], fill=c(beam))
    d.rectangle([0, 15, S - 1, 16], fill=c(beam))
    for x in (0, 15, 31):
        d.rectangle([x, 0, x + 1, S - 1], fill=c(beam))
    d.line([(2, 14), (14, 3)], fill=c(beam), width=2)
    return im


def whitewash_wall(seed: int) -> Image.Image:
    r = rng(seed)
    a = _ground(seed, (238, 236, 228), 0.025)
    for _ in range(5):  # where the whitewash has worn to the stone
        x, y = int(r.integers(0, S - 4)), int(r.integers(0, S - 3))
        a[y:y + 2, x:x + 3, :3] = (204, 196, 180)
    a[-3:, :, :3] *= 0.9
    return img(a)


def mudbrick_wall(seed: int) -> Image.Image:
    a = arr(wall_courses(seed, (196, 160, 110), (160, 126, 84), course=5, brick=9)).astype(np.float32)
    r = rng(seed + 1)
    for _ in range(4):  # a skin of mud plaster here and there
        x, y = int(r.integers(0, S - 8)), int(r.integers(0, S - 6))
        a[y:y + 6, x:x + 8, :3] = (204, 170, 122)
    return img(a)


def log_wall(seed: int) -> Image.Image:
    """Whole logs, one above another, round ends lit at the top."""
    r = rng(seed)
    a = np.zeros((S, S, 4), np.float32)
    a[..., 3] = 255
    base = np.array([132, 94, 60], np.float32)
    for y in range(S):
        k = y % 8
        f = {0: 0.62, 1: 1.18, 2: 1.12, 3: 1.04, 4: 1.0, 5: 0.94, 6: 0.86, 7: 0.74}[k]
        a[y, :, :3] = base * f
    for _ in range(14):
        x, y = int(r.integers(0, S)), int(r.integers(0, S))
        a[y, x:x + 3, :3] *= 0.86
    for y in range(4, S, 8):  # moss in the cracks
        for x in range(0, S, 5):
            if r.random() < 0.4:
                a[y - 4, x, :3] = (96, 120, 60)
    return img(a)


def felt_wall(seed: int) -> Image.Image:
    a = _ground(seed, (222, 210, 186), 0.03)
    for y in range(S):
        if y % 10 in (0, 1):  # the bands of rope round a yurt
            a[y, :, :3] = (150, 60, 50)
    for x in range(0, S, 8):  # the lattice showing through
        for y in range(S):
            if (x + y) % 8 == 0:
                a[y, x % S, :3] *= 0.9
    return img(a)


def earth_wall(seed: int) -> Image.Image:
    """The grassy flank of a burrow."""
    r = rng(seed)
    a = _ground(seed, (96, 140, 72), 0.08)
    for _ in range(30):
        x, y = int(r.integers(0, S)), int(r.integers(0, S))
        a[y, x, :3] = (130, 170, 96) if r.random() < 0.6 else (230, 210, 120)
    a[-6:, :, :3] = a[-6:, :, :3] * 0.8 + np.array([110, 80, 50], np.float32) * 0.2
    return img(a)


def earthwork(seed: int) -> Image.Image:
    """A bank of turf with sharpened stakes along its top."""
    a = arr(earth_wall(seed)).astype(np.float32)
    im = img(a)
    d = ImageDraw.Draw(im)
    for x in range(1, S, 5):
        d.polygon([(x, 6), (x + 2, 0), (x + 4, 6)], fill=c((120, 90, 56)))
    return im


def pyramid_wall(seed: int) -> Image.Image:
    """The stepped face of a pyramid: courses of stone, painted plaster here and there."""
    a = arr(wall_courses(seed, (214, 204, 180), (160, 150, 128), course=8, brick=16)).astype(np.float32)
    for y in range(0, S, 8):
        a[y:y + 2, :, :3] = (176, 164, 140)
    r = rng(seed)
    if r.random() < 0.5:
        a[10:14, 4:28, :3] = (170, 70, 50)  # a band of red
    return img(a)


# ---------------------------------------------------------------------------- floors
def slabs(seed: int) -> Image.Image:
    """Dressed stone slabs, warm grey, in staggered rows: the floor of halls, temples and the halls of the deep."""
    r = rng(seed)
    a = _ground(seed, (150, 142, 130), 0.035)
    joint = np.array((98, 92, 84), np.float32)
    rows = [0, 11, 22, S]
    for ri in range(3):
        y0, y1 = rows[ri], rows[ri + 1]
        x = -int((ri * 7 + seed * 5) % 14)
        while x < S:
            w = int(r.integers(12, 17))
            x0, x1 = max(0, x), min(S, x + w)
            if x1 > x0:
                a[y0:y1, x0:x1, :3] *= r.uniform(0.92, 1.07)
                a[y0 + 1:y0 + 2, x0 + 1:x1 - 1, :3] = np.clip(a[y0 + 1:y0 + 2, x0 + 1:x1 - 1, :3] * 1.1, 0, 255)
                if x >= 0:
                    a[y0:y1, x0, :3] = joint
            x += w
        a[y0, :, :3] = joint
    for _ in range(10):  # wear and small chips
        x, y = int(r.integers(0, S)), int(r.integers(0, S))
        a[y, x, :3] *= 0.9
    return img(np.clip(a, 0, 255))


def flags(seed: int) -> Image.Image:
    """Pale flagstones set unevenly and worn by feet: squares, plazas, courtyards."""
    r = rng(seed)
    a = _ground(seed, (178, 170, 152), 0.045)
    joint = np.array((120, 112, 98), np.float32)
    rows = [0, 8, 17, 25, S]  # the same courses in every tile, so they meet; the stones in them differ
    for ri in range(len(rows) - 1):
        y, y1 = rows[ri], rows[ri + 1]
        x = -int(r.integers(0, 8))
        while x < S:
            w = int(r.integers(7, 13))
            x0, x1 = max(0, x), min(S, x + w)
            if x1 > x0:
                a[y:y1, x0:x1, :3] *= r.uniform(0.9, 1.08)
                if x >= 0:
                    a[y:y1, x0, :3] = joint
            x += w
        a[y, :, :3] = joint
    return img(np.clip(a, 0, 255))


def tile_floor(seed: int) -> Image.Image:
    """Glazed tiles in a star pattern."""
    a = np.zeros((S, S, 4), np.float32)
    a[..., 3] = 255
    cols = [(190, 140, 100), (60, 110, 140), (230, 220, 196)]
    for y in range(S):
        for x in range(S):
            u, v = x % 8, y % 8
            k = 2 if (u in (0, 7) or v in (0, 7)) else (1 if abs(u - 3.5) + abs(v - 3.5) < 2.5 else 0)
            a[y, x, :3] = cols[k]
    a[..., :3] *= rng(seed).uniform(0.94, 1.04, (S, S))[..., None]
    return img(a)


def rugs(seed: int) -> Image.Image:
    r = rng(seed)
    a = np.zeros((S, S, 4), np.float32)
    a[..., 3] = 255
    reds = [(150, 50, 44), (60, 60, 120), (180, 130, 60)]
    base = np.array(reds[seed % 3], np.float32)
    a[..., :3] = base
    for y in range(S):
        for x in range(S):
            if (x // 4 + y // 4) % 2 == 0 and 3 < x < S - 4 and 3 < y < S - 4:
                a[y, x, :3] = base * 1.25
            if x in (1, S - 2) or y in (1, S - 2):
                a[y, x, :3] = (220, 200, 150)
    a[..., :3] *= r.uniform(0.95, 1.03, (S, S))[..., None]
    return img(np.clip(a, 0, 255))


def boardwalk(seed: int) -> Image.Image:
    """Split logs laid across the mud."""
    r = rng(seed)
    a = np.zeros((S, S, 4), np.float32)
    a[..., 3] = 255
    for y in range(S):
        k = y % 5
        a[y, :, :3] = np.array([160, 118, 76], np.float32) * (0.7 if k == 0 else (1.1 if k == 1 else 1.0))
    a[..., :3] *= r.uniform(0.9, 1.05, (S, S))[..., None]
    a[:, :2, :3] = (70, 56, 40)
    a[:, -2:, :3] = (70, 56, 40)
    return img(a)


def causeway(seed: int) -> Image.Image:
    a = _ground(seed, (232, 228, 214), 0.025)
    a[:2, :, :3] *= 0.86
    a[-2:, :, :3] *= 0.86
    return img(a)


def steps(seed: int) -> Image.Image:
    a = _ground(seed, (220, 210, 186), 0.03)
    for y in range(0, S - 2, 6):
        a[y:y + 2, :, :3] = (150, 140, 120)
        a[y + 2, :, :3] = (240, 234, 216)
    return img(a)


def rug_over(seed: int) -> Image.Image:
    """A rug laid on a floor (drawn over it)."""
    im = blank()
    d = ImageDraw.Draw(im)
    col = [(150, 50, 44), (60, 60, 120), (180, 130, 60)][seed % 3]
    d.rectangle([3, 6, 28, 25], fill=c(col))
    d.rectangle([5, 8, 26, 23], outline=c((220, 200, 150)))
    d.rectangle([12, 13, 19, 18], fill=c(shade(col, 1.3)))
    for x in range(3, 29, 2):
        d.point((x, 5), fill=c((220, 200, 150)))
        d.point((x, 26), fill=c((220, 200, 150)))
    return im


def mushroom_bed(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    for row in range(3):
        y = 7 + row * 9
        for x in range(3, S - 2, 5):
            xx = x + int(r.integers(-1, 2))
            d.line([(xx, y + 3), (xx, y)], fill=c((220, 214, 196)))
            d.pieslice([xx - 2, y - 2, xx + 2, y + 2], 180, 360, fill=c((200, 186, 150)))
    return im


# ---------------------------------------------------------------------------- furniture
WOOD = (150, 106, 66)
DARK = (104, 72, 44)


def stool(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.ellipse([10, 12, 22, 18], fill=c(WOOD))
    for x in (11, 16, 20):
        d.line([(x, 17), (x - 1 if x < 16 else x + 1, 26)], fill=c(DARK), width=2)
    return shadow(outline(im))


def chair(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([10, 4, 21, 6], fill=c(WOOD))
    d.rectangle([10, 4, 11, 26], fill=c(DARK))
    d.rectangle([20, 4, 21, 26], fill=c(DARK))
    d.rectangle([9, 15, 22, 18], fill=c(WOOD))
    d.rectangle([10, 8, 21, 9], fill=c(DARK))
    return shadow(outline(im))


def bench(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([2, 13, 29, 17], fill=c(WOOD))
    d.rectangle([2, 13, 29, 13], fill=c(shade(WOOD, 1.2)))
    for x in (4, 26):
        d.rectangle([x, 17, x + 2, 24], fill=c(DARK))
    return shadow(outline(im))


def counter(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([1, 10, 30, 26], fill=c(DARK))
    d.rectangle([1, 10, 30, 14], fill=c(WOOD))
    for x in range(4, 30, 7):
        d.line([(x, 15), (x, 25)], fill=c(shade(DARK, 0.8)))
    d.ellipse([20, 6, 24, 10], fill=c((200, 170, 80)))  # a mug on it
    return shadow(outline(im))


def shelf(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([3, 2, 28, 28], fill=c(DARK))
    for y in (9, 17, 25):
        d.rectangle([3, y, 28, y + 1], fill=c(WOOD))
        for x in range(5, 27, 4):
            col = [(170, 90, 60), (90, 120, 150), (200, 190, 150), (120, 140, 80)][int(r.integers(0, 4))]
            hh = int(r.integers(3, 6))
            d.rectangle([x, y - hh, x + 2, y - 1], fill=c(col))
    return shadow(outline(im))


def bookcase(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([3, 1, 28, 30], fill=c(DARK))
    for y in (8, 16, 24):
        d.rectangle([3, y, 28, y + 1], fill=c(WOOD))
    for y0 in (2, 10, 18, 26):
        x = 5
        while x < 27:
            w = int(r.integers(1, 3))
            col = [(150, 50, 40), (60, 80, 130), (80, 110, 60), (170, 130, 70), (110, 70, 110)][int(r.integers(0, 5))]
            d.rectangle([x, y0, x + w, y0 + (5 if y0 < 26 else 3)], fill=c(col))
            x += w + 1
    return shadow(outline(im))


def wardrobe(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([6, 2, 25, 29], fill=c(DARK))
    d.rectangle([7, 3, 15, 28], fill=c(WOOD))
    d.rectangle([16, 3, 24, 28], fill=c(shade(WOOD, 0.9)))
    d.point((14, 15), fill=c((210, 180, 100)))
    d.point((17, 15), fill=c((210, 180, 100)))
    return shadow(outline(im))


def trunk(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    col = [(120, 80, 50), (90, 60, 40), (140, 100, 60)][seed % 3]
    d.rectangle([5, 12, 26, 26], fill=c(col))
    d.rectangle([5, 10, 26, 14], fill=c(shade(col, 1.2)))
    for x in (8, 23):
        d.rectangle([x, 10, x + 1, 26], fill=c((110, 110, 120)))
    d.rectangle([14, 16, 17, 19], fill=c((200, 170, 80)))
    return shadow(outline(im))


def oven(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.pieslice([4, 6, 28, 38], 180, 360, fill=c((176, 110, 70)))
    d.rectangle([4, 21, 28, 27], fill=c((150, 90, 60)))
    d.pieslice([11, 15, 21, 29], 180, 360, fill=c((40, 24, 18)))
    d.ellipse([13, 19, 19, 23], fill=c((250, 150, 60)))
    return shadow(outline(im))


def pew(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([1, 9, 30, 12], fill=c(DARK))
    d.rectangle([1, 13, 30, 18], fill=c(WOOD))
    for x in (2, 15, 28):
        d.rectangle([x, 18, x + 1, 23], fill=c(DARK))
    return shadow(outline(im))


def candles(frame: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([12, 24, 19, 27], fill=c((170, 150, 110)))
    d.line([(15, 24), (15, 12)], fill=c((150, 130, 100)), width=2)
    for x, h in ((9, 8), (15, 10), (21, 7)):
        d.rectangle([x - 1, 22 - h, x + 1, 22], fill=c((236, 228, 206)))
        flick = (frame + x) % 3
        d.ellipse([x - 1, 18 - h - flick, x + 1, 21 - h], fill=c((255, 214, 120)))
        d.point((x, 19 - h), fill=c((255, 250, 220)))
    d.line([(9, 22), (21, 22)], fill=c((150, 130, 100)), width=2)
    return outline(im)


def statue_small(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    stone = (196, 192, 184)
    d.rectangle([9, 24, 22, 29], fill=c(shade(stone, 0.85)))
    d.ellipse([13, 3, 18, 8], fill=c(stone))
    d.polygon([(11, 24), (12, 10), (19, 10), (20, 24)], fill=c(stone))
    d.line([(12, 12), (8, 18)], fill=c(stone), width=2) if seed % 2 else d.line([(19, 12), (24, 6)], fill=c(stone), width=2)
    return shadow(outline(noise_shade(im, seed, 0.06)))


def forge(frame: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([3, 12, 28, 28], fill=c((110, 100, 96)))
    d.rectangle([3, 12, 28, 14], fill=c((140, 130, 124)))
    d.ellipse([7, 14, 24, 22], fill=c((50, 30, 20)))
    for i in range(6):
        x = 9 + i * 3
        d.ellipse([x - 1, 16 + (i + frame) % 2, x + 2, 19 + (i + frame) % 2],
                  fill=c((255, 150 + 20 * ((i + frame) % 3), 50)))
    d.rectangle([12, 2, 19, 12], fill=c((90, 84, 80)))  # the hood
    return shadow(outline(im))


def coal(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    d.polygon([(4, 27), (16, 10), (28, 27)], fill=c((50, 46, 46)))
    for _ in range(14):
        x, y = int(r.integers(8, 24)), int(r.integers(14, 26))
        d.point((x, y), fill=c((96, 92, 92)))
    return shadow(outline(im))


def herbs(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    d.line([(2, 4), (29, 4)], fill=c(DARK), width=2)
    for x in range(5, 28, 5):
        col = [(110, 150, 80), (150, 160, 90), (130, 100, 140)][int(r.integers(0, 3))]
        d.line([(x, 5), (x, 9)], fill=c((120, 100, 70)))
        d.polygon([(x - 2, 9), (x + 2, 9), (x, 20)], fill=c(col))
    return outline(im)


def throne(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    gold = (210, 170, 80)
    d.rectangle([8, 2, 23, 20], fill=c(gold))
    d.rectangle([10, 4, 21, 18], fill=c((150, 40, 40)))
    d.rectangle([6, 16, 25, 22], fill=c(shade(gold, 0.85)))
    d.rectangle([9, 18, 22, 21], fill=c((170, 50, 50)))
    for x in (7, 23):
        d.rectangle([x, 22, x + 2, 29], fill=c(shade(gold, 0.7)))
    d.polygon([(14, 0), (16, 2), (18, 0)], fill=c(gold))
    return shadow(outline(im))


def banner(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    col = [(160, 44, 40), (44, 70, 140), (50, 100, 60), (140, 110, 40)][seed % 4]
    d.line([(15, 1), (15, 30)], fill=c((110, 84, 56)), width=2)
    d.rectangle([7, 3, 23, 4], fill=c((110, 84, 56)))
    d.polygon([(8, 5), (22, 5), (22, 22), (15, 18), (8, 22)], fill=c(col))
    d.ellipse([12, 9, 18, 14], fill=c((220, 200, 120)))
    return shadow(outline(im))


def tapestry(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([2, 3, 29, 4], fill=c((110, 84, 56)))
    d.rectangle([3, 5, 28, 27], fill=c((150, 100, 70)))
    for _ in range(18):  # a hunt, a battle, a wedding: figures in thread
        x, y = int(r.integers(5, 26)), int(r.integers(8, 25))
        d.rectangle([x, y, x + 1, y + 2], fill=c([(60, 80, 120), (170, 60, 50), (220, 200, 150), (70, 110, 60)][int(r.integers(0, 4))]))
    d.rectangle([3, 5, 28, 7], fill=c((180, 140, 70)))
    d.rectangle([3, 25, 28, 27], fill=c((180, 140, 70)))
    return outline(im)


def weapon_rack(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([3, 26, 28, 28], fill=c(DARK))
    d.rectangle([3, 8, 28, 9], fill=c(DARK))
    steel = (190, 190, 200)
    d.line([(7, 27), (7, 2)], fill=c((120, 90, 60)), width=1)
    d.polygon([(6, 3), (7, 0), (8, 3)], fill=c(steel))
    d.line([(13, 27), (13, 10)], fill=c(steel), width=2)
    d.rectangle([11, 9, 15, 10], fill=c((140, 110, 60)))
    d.line([(20, 27), (20, 6)], fill=c((120, 90, 60)), width=1)
    d.polygon([(20, 6), (25, 3), (25, 10)], fill=c(steel))
    d.line([(25, 27), (25, 12)], fill=c(steel), width=2)
    return shadow(outline(im))


def armour_stand(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    mail = (160, 160, 170)
    d.line([(15, 29), (15, 6)], fill=c(DARK), width=2)
    d.rectangle([10, 28, 21, 29], fill=c(DARK))
    d.ellipse([12, 2, 19, 9], fill=c(shade(mail, 1.1)))
    d.polygon([(9, 10), (22, 10), (21, 22), (10, 22)], fill=c(mail))
    for y in range(11, 22, 2):
        d.line([(10, y), (21, y)], fill=c(shade(mail, 0.85)))
    return shadow(outline(im))


def lectern(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([14, 14, 17, 28], fill=c(DARK))
    d.rectangle([10, 27, 21, 29], fill=c(DARK))
    d.polygon([(7, 14), (24, 10), (24, 15), (7, 19)], fill=c(WOOD))
    d.polygon([(9, 13), (15, 11), (15, 15), (9, 17)], fill=c((236, 228, 206)))
    d.polygon([(16, 11), (22, 10), (22, 14), (16, 15)], fill=c((226, 218, 196)))
    return shadow(outline(im))


def cauldron(frame: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    for x in (9, 22):
        d.line([(x, 20), (x - 2 if x < 16 else x + 2, 29)], fill=c((70, 70, 74)), width=2)
    d.ellipse([6, 10, 25, 27], fill=c((70, 70, 76)))
    d.ellipse([8, 10, 23, 15], fill=c((90, 140, 70)))
    for i in range(2):
        y = 6 - frame + i * 3
        d.ellipse([11 + i * 5, y, 15 + i * 5, y + 3], fill=(230, 230, 220, 160))
    d.ellipse([10, 26, 22, 30], fill=c((250, 140, 50)))
    return outline(im)


def boat(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    hull = (130, 92, 58)
    d.polygon([(2, 12), (29, 12), (25, 22), (6, 22)], fill=c(hull))
    d.line([(4, 15), (27, 15)], fill=c(shade(hull, 0.8)))
    d.line([(6, 18), (25, 18)], fill=c(shade(hull, 0.8)))
    for x in (6, 25):
        d.line([(x, 22), (x, 28)], fill=c(DARK), width=2)
    return shadow(outline(im))


def fish_rack(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    for x in (4, 27):
        d.line([(x, 28), (x, 6)], fill=c(DARK), width=2)
    d.line([(4, 7), (27, 7)], fill=c(DARK), width=2)
    for x in range(7, 26, 4):
        d.polygon([(x - 1, 8), (x + 1, 8), (x + 2, 20), (x, 22), (x - 2, 20)], fill=c((190, 180, 150)))
    return shadow(outline(im))


def tomb_slab(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    stone = (176, 172, 160)
    d.rectangle([4, 8, 27, 27], fill=c(shade(stone, 0.85)))
    d.rectangle([5, 6, 26, 22], fill=c(stone))
    d.ellipse([12, 8, 19, 13], fill=c(shade(stone, 1.1)))  # the face of the one inside
    d.polygon([(10, 13), (21, 13), (19, 21), (12, 21)], fill=c(shade(stone, 1.05)))
    return shadow(outline(noise_shade(im, seed, 0.05)))


# ---------------------------------------------------------------------------- lights and things in the street
def brazier(frame: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    iron = (70, 66, 64)
    for x0, x1 in ((10, 7), (21, 24), (15, 15)):
        d.line([(x0, 18), (x1, 29)], fill=c(iron), width=2)
    d.pieslice([7, 8, 24, 24], 0, 180, fill=c(iron))
    for i in range(5):
        x = 9 + i * 3
        h = 4 + ((i + frame) * 7) % 5
        d.polygon([(x - 2, 16), (x + 2, 16), (x, 16 - h)], fill=c((255, 120 + ((i + frame) % 3) * 40, 40)))
    d.ellipse([10, 12, 21, 18], fill=c((255, 200, 90)))
    return outline(im)


def lamp_post(seed: int, glow=(255, 214, 140), metal=(60, 56, 54)) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([14, 8, 17, 30], fill=c(metal))
    d.rectangle([11, 28, 20, 30], fill=c(metal))
    d.rectangle([10, 1, 21, 9], fill=c(metal))
    d.rectangle([12, 3, 19, 8], fill=c(glow))
    d.polygon([(9, 1), (15, -3), (22, 1)], fill=c(metal))
    return shadow(outline(im))


def torch_post(frame: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.line([(15, 30), (15, 9)], fill=c((110, 80, 50)), width=3)
    d.rectangle([13, 8, 18, 12], fill=c((70, 50, 30)))
    flick = frame % 3
    d.polygon([(11, 9), (20, 9), (16 + flick - 1, 0)], fill=c((255, 140, 40)))
    d.polygon([(13, 9), (18, 9), (15 + flick - 1, 3)], fill=c((255, 220, 120)))
    return outline(im)


def fire_pit(frame: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    for i in range(8):
        a = i * math.tau / 8
        x, y = 16 + math.cos(a) * 10, 22 + math.sin(a) * 5
        d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=c((130, 124, 116)))
    d.line([(9, 24), (22, 19)], fill=c((90, 60, 36)), width=2)
    d.line([(10, 19), (22, 24)], fill=c((90, 60, 36)), width=2)
    for i in range(4):
        x = 11 + i * 3
        h = 6 + ((i + frame) * 5) % 6
        d.polygon([(x - 2, 22), (x + 2, 22), (x, 22 - h)], fill=c((255, 130 + ((i + frame) % 3) * 40, 40)))
    return outline(im)


def fountain(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    stone = (180, 176, 168)
    d.ellipse([2, 14, 29, 30], fill=c(stone))
    d.ellipse([5, 16, 26, 27], fill=c((80, 140, 190)))
    d.rectangle([14, 6, 17, 20], fill=c(shade(stone, 0.9)))
    d.ellipse([10, 4, 21, 9], fill=c(stone))
    for x in (11, 20):
        d.line([(x, 8), (x + (-3 if x < 16 else 3), 18)], fill=c((200, 230, 250)))
    d.point((15, 3), fill=c((230, 244, 250)))
    return shadow(outline(im))


def palm_pot(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.polygon([(10, 20), (21, 20), (19, 30), (12, 30)], fill=c((180, 100, 60)))
    d.line([(15, 20), (16, 8)], fill=c((120, 90, 56)), width=2)
    for dx, dy in ((-8, 2), (8, 2), (-6, -4), (6, -4), (0, -6)):
        d.line([(16, 8), (16 + dx, 8 + dy)], fill=c((70, 130, 60)), width=2)
    return shadow(outline(im))


def rug_stall(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.line([(4, 30), (4, 6)], fill=c(DARK), width=2)
    d.line([(27, 30), (27, 6)], fill=c(DARK), width=2)
    d.line([(4, 6), (27, 6)], fill=c(DARK), width=2)
    for i, col in enumerate([(160, 50, 44), (60, 60, 130), (190, 140, 60)]):
        x = 6 + i * 7
        d.rectangle([x, 7, x + 5, 22], fill=c(col))
        d.rectangle([x + 1, 9, x + 4, 20], outline=c((220, 200, 150)))
    d.rectangle([5, 24, 26, 28], fill=c((170, 60, 50)))
    return shadow(outline(im))


def standing_stone(seed: int, rune: bool = False) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    stone = (160, 156, 150) if not rune else (172, 162, 150)
    d.polygon([(10, 30), (11, 5), (16, 1), (21, 5), (22, 30)], fill=c(stone))
    d.polygon([(10, 30), (11, 5), (16, 1), (15, 30)], fill=c(shade(stone, 1.12)))
    if rune:  # a serpent band of runes, painted red
        for y in range(6, 28, 2):
            x = 16 + int(round(math.sin(y * 0.6) * 3))
            d.point((x, y), fill=c((170, 50, 40)))
        d.line([(13, 10), (19, 14)], fill=c((170, 50, 40)))
    else:
        for _ in range(5):
            d.point((int(rng(seed).integers(12, 20)), int(rng(seed + 1).integers(8, 28))), fill=c((150, 170, 110)))
    return shadow(outline(noise_shade(im, seed, 0.06)))


def stela(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    stone = (220, 210, 186)
    d.rectangle([10, 2, 21, 30], fill=c(stone))
    d.ellipse([13, 4, 18, 9], fill=c(shade(stone, 0.85)))  # a lord in his headdress
    d.polygon([(11, 4), (15, 0), (20, 4)], fill=c((80, 140, 110)))
    d.rectangle([13, 10, 18, 20], fill=c(shade(stone, 0.88)))
    for y in range(22, 29, 2):
        d.line([(12, y), (19, y)], fill=c(shade(stone, 0.75)))
    return shadow(outline(im))


def altar_stone(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    stone = (170, 150, 140)
    d.rectangle([4, 14, 27, 26], fill=c(stone))
    d.rectangle([4, 12, 27, 16], fill=c(shade(stone, 1.15)))
    d.line([(6, 14), (25, 14)], fill=c((100, 40, 36)), width=2)
    return shadow(outline(im))


def pottery(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    for x, y, rad, col in ((9, 18, 6, (190, 120, 80)), (21, 20, 5, (170, 90, 60)), (15, 10, 5, (200, 140, 90))):
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=c(col))
        d.line([(x - rad + 2, y), (x + rad - 2, y)], fill=c((60, 40, 30)))
        d.rectangle([x - 2, y - rad - 2, x + 2, y - rad + 1], fill=c(shade(col, 0.8)))
    return shadow(outline(im))


def maize_crib(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    for x in (6, 25):
        d.line([(x, 30), (x, 22)], fill=c(DARK), width=2)
    d.rectangle([4, 6, 27, 22], fill=c((120, 90, 56)))
    for x in range(6, 26, 3):
        for y in range(8, 21, 4):
            d.ellipse([x, y, x + 2, y + 3], fill=c((220, 190, 80)))
    d.polygon([(2, 7), (16, 0), (29, 7)], fill=c((180, 150, 80)))
    return shadow(outline(im))


def amphora(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    for x in (9, 16, 23):
        d.ellipse([x - 4, 10, x + 4, 26], fill=c((180, 110, 70)))
        d.rectangle([x - 1, 5, x + 1, 11], fill=c((160, 96, 60)))
        d.line([(x - 3, 8), (x - 1, 6)], fill=c((140, 80, 50)))
        d.line([(x - 3, 17), (x + 3, 17)], fill=c((70, 40, 30)))
    return shadow(outline(im))


def standard(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.line([(15, 31), (15, 2)], fill=c((110, 84, 56)), width=2)
    d.polygon([(13, 2), (15, -2), (17, 2)], fill=c((200, 200, 210)))
    d.ellipse([12, 4, 18, 8], fill=c((200, 180, 120)))
    for i, x in enumerate((11, 14, 17, 20)):  # the horsetails
        d.line([(15, 7), (x, 20 + (i % 2) * 2)], fill=c((230, 226, 214) if i % 2 else (60, 50, 44)), width=2)
    return shadow(outline(im))


def horse_post(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([14, 8, 17, 29], fill=c(DARK))
    d.ellipse([16, 12, 21, 17], outline=c((150, 150, 160)), width=1)
    d.rectangle([12, 28, 19, 30], fill=c(DARK))
    return shadow(outline(im))


def sledge(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([4, 12, 26, 18], fill=c(WOOD))
    d.line([(2, 22), (27, 22)], fill=c(DARK), width=2)
    d.line([(2, 22), (1, 18)], fill=c(DARK), width=2)
    for x in (7, 23):
        d.line([(x, 18), (x, 22)], fill=c(DARK))
    return shadow(outline(im))


def bell_post(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    for x in (7, 24):
        d.line([(x, 30), (x, 5)], fill=c(DARK), width=2)
    d.line([(5, 5), (26, 5)], fill=c(DARK), width=2)
    d.polygon([(10, 2), (16, -2), (21, 2)], fill=c((120, 90, 56)))
    d.pieslice([11, 7, 21, 25], 180, 360, fill=c((200, 160, 80)))
    d.rectangle([11, 15, 21, 18], fill=c((180, 140, 70)))
    return shadow(outline(im))


def mine_cart(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.polygon([(5, 10), (26, 10), (23, 22), (8, 22)], fill=c((110, 104, 100)))
    for x, y in ((9, 8), (14, 6), (19, 8), (12, 9), (17, 7)):
        d.ellipse([x - 3, y - 2, x + 3, y + 3], fill=c((120, 100, 80)))
    d.point((15, 6), fill=c((230, 200, 90)))  # a glint of gold
    for x in (10, 21):
        d.ellipse([x - 3, 21, x + 3, 27], fill=c((60, 58, 56)))
    return shadow(outline(im))


def beehive(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    for x in (9, 22):
        d.pieslice([x - 7, 10, x + 7, 34], 180, 360, fill=c((210, 176, 90)))
        for y in range(13, 22, 3):
            d.line([(x - 6, y), (x + 6, y)], fill=c((170, 136, 60)))
        d.ellipse([x - 1, 18, x + 1, 20], fill=c((40, 30, 20)))
    d.rectangle([1, 22, 30, 24], fill=c(DARK))
    for _ in range(4):
        d.point((int(r.integers(2, 30)), int(r.integers(2, 12))), fill=c((40, 30, 20)))
    return shadow(outline(im))


def skull_post(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.line([(15, 31), (15, 6)], fill=c((110, 84, 56)), width=2)
    d.ellipse([11, 1, 20, 9], fill=c((226, 220, 200)))
    d.rectangle([13, 8, 18, 11], fill=c((226, 220, 200)))
    for x in (13, 17):
        d.point((x, 5), fill=c((30, 24, 20)))
    for x, y in ((8, 27), (22, 28)):
        d.ellipse([x - 3, y - 3, x + 3, y + 2], fill=c((216, 210, 190)))
    return shadow(outline(im))


def low_wall(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    stone = (176, 168, 150)
    d.rectangle([0, 14, 31, 25], fill=c(stone))
    d.rectangle([0, 14, 31, 16], fill=c(shade(stone, 1.15)))
    for x in range(0, S, 7):
        d.line([(x, 17), (x, 25)], fill=c(shade(stone, 0.8)))
    return shadow(outline(im))


def hedge(seed: int, thorn: bool = False) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    green = (70, 120, 56) if not thorn else (80, 104, 66)
    for _ in range(9):
        x, y = int(r.integers(4, 28)), int(r.integers(8, 26))
        rad = int(r.integers(5, 8))
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=c(shade(green, r.uniform(0.85, 1.1))))
    if thorn:
        for _ in range(16):
            x, y = int(r.integers(2, 30)), int(r.integers(4, 30))
            d.line([(x, y), (x + 2, y - 2)], fill=c((200, 190, 160)))
    else:
        for _ in range(5):
            d.point((int(r.integers(4, 28)), int(r.integers(6, 26))), fill=c((220, 70, 60)))  # holly berries
    return shadow(outline(im))


# ---------------------------------------------------------------------------- trees of towns
def cypress(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([15, 26, 16, 30], fill=c((90, 66, 44)))
    d.ellipse([10, 0, 21, 28], fill=c((44, 84, 54)))
    d.ellipse([11, 2, 16, 24], fill=c((64, 108, 70)))
    return shadow(outline(noise_shade(im, seed, 0.08)))


def olive(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    d.line([(15, 30), (13, 20), (17, 14)], fill=c((110, 96, 80)), width=3)
    for _ in range(7):
        x, y = int(r.integers(5, 26)), int(r.integers(4, 18))
        d.ellipse([x - 5, y - 4, x + 5, y + 4], fill=c((140, 160, 116) if r.random() < 0.6 else (170, 186, 150)))
    return shadow(outline(im))


def birch(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([14, 10, 16, 30], fill=c((230, 230, 220)))
    for y in range(12, 30, 3):
        d.point((14 + int(r.integers(0, 3)), y), fill=c((40, 36, 32)))
    for _ in range(8):
        x, y = int(r.integers(6, 25)), int(r.integers(2, 18))
        d.ellipse([x - 4, y - 3, x + 4, y + 3], fill=c((150, 180, 90) if r.random() < 0.6 else (190, 200, 110)))
    return shadow(outline(im))


def party_tree(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.polygon([(12, 30), (14, 16), (18, 16), (20, 30)], fill=c((110, 80, 52)))
    for (x, y, rad, g) in ((16, 10, 10, (70, 120, 60)), (8, 13, 6, (64, 110, 56)), (24, 13, 6, (64, 110, 56)),
                           (16, 4, 6, (90, 140, 70))):
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=c(g))
    for x, col in ((9, (230, 80, 70)), (20, (240, 200, 80)), (14, (90, 120, 220))):  # bunting for the feast
        d.point((x, 18), fill=c(col))
    return shadow(outline(im))


def all_drawn() -> dict[str, Image.Image]:
    out: dict[str, Image.Image] = {}
    for i in range(4):
        out[f"wall/plaster_{i}"] = plaster_wall(2000 + i)
        out[f"wall/white_{i}"] = whitewash_wall(2010 + i)
        out[f"wall/mudbrick_{i}"] = mudbrick_wall(2020 + i)
        out[f"wall/logs_{i}"] = log_wall(2030 + i)
        out[f"wall/felt_{i}"] = felt_wall(2040 + i)
        out[f"wall/earth_{i}"] = earth_wall(2050 + i)
        out[f"wall/earthwork_{i}"] = earthwork(2060 + i)
        out[f"wall/pyramid_{i}"] = pyramid_wall(2070 + i)
        out[f"floor/tile_{i}"] = tile_floor(2080 + i)
        out[f"floor/slabs_{i}"] = slabs(2400 + i)
        out[f"floor/flags_{i}"] = flags(2410 + i)
        out[f"floor/boardwalk_{i}"] = boardwalk(2090 + i)
        out[f"floor/causeway_{i}"] = causeway(2100 + i)
        out[f"floor/steps_{i}"] = steps(2110 + i)
    for i in range(3):
        out[f"floor/rugs_{i}"] = rugs(2120 + i)
        out[f"deco/rug_{i}"] = rug_over(2130 + i)
        out[f"deco/mushrooms_{i}"] = mushroom_bed(2140 + i)
        out[f"feature/candles_{i}"] = candles(i)
        out[f"feature/forge_{i}"] = forge(i)
        out[f"feature/cauldron_{i}"] = cauldron(i)
        out[f"feature/brazier_{i}"] = brazier(i)
        out[f"feature/torch_post_{i}"] = torch_post(i)
        out[f"feature/fire_pit_{i}"] = fire_pit(i)
        out[f"feature/trunk_{i}"] = trunk(2150 + i)
        out[f"feature/banner_{i}"] = banner(2160 + i)
    for i in range(2):
        out[f"feature/shelf_{i}"] = shelf(2170 + i)
        out[f"feature/bookcase_{i}"] = bookcase(2180 + i)
        out[f"feature/statue_small_{i}"] = statue_small(2190 + i)
        out[f"feature/tapestry_{i}"] = tapestry(2200 + i)
        out[f"feature/hedge_{i}"] = hedge(2210 + i)
        out[f"feature/thorn_hedge_{i}"] = hedge(2220 + i, thorn=True)
        out[f"feature/standing_stone_{i}"] = standing_stone(2230 + i)
        out[f"feature/runestone_{i}"] = standing_stone(2240 + i, rune=True)
        out[f"tree/cypress_{i}"] = cypress(2250 + i)
        out[f"tree/olive_{i}"] = olive(2260 + i)
        out[f"tree/birch_{i}"] = birch(2270 + i)
    singles = {
        "feature/stool": stool(2300), "feature/chair": chair(2301), "feature/bench": bench(2302),
        "feature/counter": counter(2303), "feature/wardrobe": wardrobe(2304), "feature/oven": oven(2305),
        "feature/pew": pew(2306), "feature/coal": coal(2307), "feature/herbs": herbs(2308),
        "feature/throne": throne(2309), "feature/weapon_rack": weapon_rack(2310),
        "feature/armour_stand": armour_stand(2311), "feature/lectern": lectern(2312), "feature/boat": boat(2313),
        "feature/fish_rack": fish_rack(2314), "feature/tomb_slab": tomb_slab(2315), "feature/lamp_post": lamp_post(2316),
        "feature/lantern_post": lamp_post(2317, glow=(190, 250, 230), metal=(90, 110, 100)),
        "feature/fountain": fountain(2318), "feature/palm_pot": palm_pot(2319), "feature/rug_stall": rug_stall(2320),
        "feature/stela": stela(2321), "feature/altar_stone": altar_stone(2322), "feature/pottery": pottery(2323),
        "feature/maize_crib": maize_crib(2324), "feature/amphora": amphora(2325), "feature/standard": standard(2326),
        "feature/horse_post": horse_post(2327), "feature/sledge": sledge(2328), "feature/bell_post": bell_post(2329),
        "feature/mine_cart": mine_cart(2330), "feature/beehive": beehive(2331), "feature/skull_post": skull_post(2332),
        "feature/low_wall": low_wall(2333), "tree/party": party_tree(2334), "feature/peat_stack": None,
    }
    peat = blank()
    d = ImageDraw.Draw(peat)
    for row in range(3):
        for k in range(4 - row):
            x = 4 + k * 6 + row * 3
            y = 24 - row * 6
            d.rectangle([x, y, x + 5, y + 5], fill=c((100, 72, 50)))
            d.line([(x, y), (x + 5, y)], fill=c((130, 96, 66)))
    singles["feature/peat_stack"] = shadow(outline(peat))
    out.update(singles)
    return out
