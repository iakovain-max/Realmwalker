"""Pictures of the wild drawn in code, for the lands the Dungeon Crawl pack has nothing for: palms, acacias, jungle
giants, fey trees, cacti, termite hills, glowing mushrooms, steam vents, salt crust, ash, wind-rippled sand,
crevasses in the ice; and the things of the world's wonders (falls, hot springs, stone arches, drifting stones...).

32x32 RGBA like tools/tile_art.py, in the same manner: a dark outline, light from the top left, a little noise, a
shadow under what stands up. Used only by tools/build_tiles.py.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from tile_art import S, arr, blank, img, noise_shade, outline, rng, shade, shadow, tufts


def _rgba(c, a: int = 255) -> tuple:
    return tuple(int(v) for v in c[:3]) + (a,)


# ---------------------------------------------------------------------------- trees
def palm(seed: int) -> Image.Image:
    """A date palm: a ringed trunk leaning a little, a crown of drooping fronds, a bunch of dates."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    lean = int(r.integers(-3, 4))
    top = (16 + lean, 9 + int(r.integers(0, 3)))
    bark, ring = (122, 92, 58), (86, 62, 38)
    steps = 22
    for i in range(steps):
        t = i / (steps - 1)
        x = 15 + (top[0] - 15) * (t ** 1.6)
        y = 30 + (top[1] - 30) * t
        c = ring if i % 3 == 0 else bark
        d.line([(x - 1, y), (x + 1, y)], fill=_rgba(c))
    dark, mid, light = (34, 82, 38), (58, 118, 48), (96, 152, 64)
    cx, cy = top
    angles = [200, 160, 235, 305, 340, 20, 120, 65][: 6 + int(r.integers(0, 3))]
    for k, a in enumerate(angles):
        a = math.radians(a + r.uniform(-10, 10))
        length = r.uniform(9, 12)
        pts = []
        for s in range(int(length)):
            droop = (s / length) ** 2 * 5
            pts.append((cx + math.cos(a) * s, cy - math.sin(a) * s + droop))
        for s, (x, y) in enumerate(pts):
            c = light if (k % 2 == 0 and s < len(pts) // 2) else mid
            d.point((x, y), fill=_rgba(c))
            if 1 < s < len(pts) - 1:  # leaflets hanging off the rib
                d.point((x, y + 1), fill=_rgba(dark))
                if s % 2 == 0:
                    d.point((x + (1 if math.cos(a) > 0 else -1), y + 2), fill=_rgba(dark))
    for k in range(int(r.integers(2, 4))):  # dates
        d.point((cx - 1 + k, cy + 2), fill=_rgba((150, 82, 40)))
        d.point((cx - 1 + k, cy + 3), fill=_rgba((120, 60, 32)))
    return shadow(outline(noise_shade(im, seed, 0.08)))


def acacia(seed: int) -> Image.Image:
    """A flat-topped thorn tree of the savanna: a forked trunk under a wide umbrella of leaves."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    bark = _rgba((98, 74, 52))
    d.line([(16, 30), (16, 21)], fill=bark, width=2)
    for tx in (9 + int(r.integers(-1, 2)), 23 + int(r.integers(-1, 2)), 16):
        d.line([(16, 22), (tx, 12)], fill=bark, width=1)
    left, right = 2 + int(r.integers(0, 3)), 29 - int(r.integers(0, 3))
    under, top = (70, 92, 40), (118, 140, 62)
    for x in range(left, right + 1):
        h = 3 + int(round(1.5 * math.sin(x * 0.7 + seed) + r.uniform(0, 1.2)))
        edge = min(x - left, right - x)
        h = min(h, 1 + edge)
        d.line([(x, 12 - h), (x, 12)], fill=_rgba(top))
        d.point((x, 12), fill=_rgba(under))
        d.point((x, 13), fill=_rgba(shade(under, 0.8)))
    for _ in range(14):  # light catching the top of the crown
        x = int(r.integers(left + 1, right))
        d.point((x, 9 + int(r.integers(-1, 2))), fill=_rgba((150, 170, 80)))
    return shadow(outline(noise_shade(im, seed, 0.08)))


def jungle_tree(seed: int) -> Image.Image:
    """A jungle giant: a dark heaped crown, lianas hanging, buttress roots."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    bark = (88, 74, 56)
    d.rectangle([14, 20, 18, 30], fill=_rgba(bark))
    d.polygon([(10, 31), (14, 24), (14, 31)], fill=_rgba(shade(bark, 0.85)))  # buttresses
    d.polygon([(22, 31), (18, 24), (18, 31)], fill=_rgba(shade(bark, 0.75)))
    tones = [(26, 70, 36), (36, 92, 44), (52, 116, 52), (78, 140, 62)]
    blobs = [(16, 11, 11), (9, 14, 7), (23, 14, 7), (12, 7, 6), (21, 7, 6), (16, 16, 8)]
    for i, (x, y, rad) in enumerate(blobs):
        x += int(r.integers(-1, 2))
        y += int(r.integers(-1, 2))
        d.ellipse([x - rad, y - rad * 0.8, x + rad, y + rad * 0.8], fill=_rgba(tones[1 if i % 2 else 0]))
    for i, (x, y, rad) in enumerate(blobs[:4]):  # the lit tops of the heaps
        d.ellipse([x - rad * 0.6 - 1, y - rad * 0.7, x + rad * 0.3, y - rad * 0.1], fill=_rgba(tones[2]))
        d.point((x - 2, y - rad * 0.5), fill=_rgba(tones[3]))
    for _ in range(int(r.integers(3, 6))):  # lianas
        x = int(r.integers(5, 27))
        y0 = 17 + int(r.integers(0, 3))
        d.line([(x, y0), (x + int(r.integers(-1, 2)), y0 + int(r.integers(4, 9)))], fill=_rgba((60, 96, 44)))
    for _ in range(3):  # a flower or a fruit in the dark
        d.point((int(r.integers(6, 26)), int(r.integers(5, 18))), fill=_rgba([(220, 80, 70), (240, 200, 80)][int(r.integers(0, 2))]))
    return shadow(outline(noise_shade(im, seed, 0.10)))


def fey_tree(seed: int) -> Image.Image:
    """A tree of the enchanted wood: a pale silver trunk that forks, and long weeping strands of leaves that glow."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    bark = (204, 208, 218)
    d.polygon([(13, 31), (15, 14), (17, 14), (19, 31)], fill=_rgba(bark))
    d.line([(14, 31), (15, 20)], fill=_rgba(shade(bark, 0.78)))
    forks = [(16, 15, 8, 6), (16, 15, 24, 5), (16, 15, 16, 3)]
    for x0, y0, x1, y1 in forks:
        d.line([(x0, y0), (x1 + int(r.integers(-1, 2)), y1)], fill=_rgba(bark), width=2)
    hue = [((70, 170, 160), (160, 240, 228)), ((128, 100, 200), (214, 190, 255)), ((86, 150, 210), (190, 228, 255))]
    base, glow = hue[seed % 3]
    crown = [(8, 6), (24, 5), (16, 3), (12, 9), (20, 8), (5, 11), (27, 10)]
    for cx, cy in crown:  # the arch of the crown
        d.ellipse([cx - 4, cy - 2, cx + 4, cy + 2], fill=_rgba(shade(base, 0.85)))
    for x in range(3, 30, 2):  # strands hanging from it, longest at the sides
        top = 5 + int(abs(x - 16) * 0.25)
        length = int(6 + abs(x - 16) * 0.55 + r.integers(0, 4))
        for k in range(length):
            y = top + k
            if y > 27:
                break
            c = glow if (k + x) % 4 == 0 else (base if k % 3 else shade(base, 0.75))
            d.point((x + (1 if k > length * 0.6 and x > 16 else 0), y), fill=_rgba(c))
    for _ in range(5):  # motes in the air about it
        d.point((int(r.integers(2, 30)), int(r.integers(2, 29))), fill=_rgba((236, 255, 250), 230))
    return shadow(outline(im, (20, 26, 40, 255)))


def petrified_tree(seed: int) -> Image.Image:
    """A tree turned to stone long ago: grey, cracked, branches snapped short."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    stone = (150, 144, 136)
    d.polygon([(13, 31), (14, 12), (18, 12), (20, 31)], fill=_rgba(stone))
    d.line([(15, 12), (9, 6)], fill=_rgba(stone), width=2)
    d.line([(17, 13), (24, 8)], fill=_rgba(stone), width=2)
    d.line([(16, 12), (16, 4)], fill=_rgba(shade(stone, 0.9)), width=2)
    for _ in range(6):  # bands of colour in the stone
        y = int(r.integers(13, 30))
        d.line([(14, y), (18, y)], fill=_rgba([(170, 120, 96), (120, 116, 130), (176, 160, 120)][int(r.integers(0, 3))]))
    d.line([(15, 14), (16, 22), (15, 28)], fill=_rgba(shade(stone, 0.6)))  # a crack
    return shadow(outline(noise_shade(im, seed, 0.10)))


# ---------------------------------------------------------------------------- plants and things on the ground
def cactus(seed: int) -> Image.Image:
    """Variant 0: a tall cactus with arms; 1: barrel cacti in flower; 2: a prickly pear of flat pads."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    green, rib, spine = (70, 128, 70), (100, 156, 90), (226, 220, 190)
    kind = seed % 3
    if kind == 0:
        d.rounded_rectangle([13, 6, 18, 30], radius=2, fill=_rgba(green))
        d.rounded_rectangle([7, 15, 12, 18], radius=1, fill=_rgba(green))
        d.rounded_rectangle([7, 9, 10, 17], radius=1, fill=_rgba(green))
        d.rounded_rectangle([19, 19, 24, 22], radius=1, fill=_rgba(green))
        d.rounded_rectangle([21, 12, 24, 21], radius=1, fill=_rgba(green))
        for x in (15, 8, 22):
            d.line([(x, 8 if x == 15 else 11 if x == 8 else 14), (x, 28 if x == 15 else 16 if x == 8 else 20)],
                   fill=_rgba(rib))
    elif kind == 1:
        for (x, y, rad) in [(11, 24, 6), (21, 26, 4)]:
            d.ellipse([x - rad, y - rad - 2, x + rad, y + rad], fill=_rgba(green))
            for k in range(-rad + 2, rad - 1, 2):
                d.line([(x + k, y - rad), (x + k, y + rad - 1)], fill=_rgba(rib))
        d.ellipse([9, 15, 13, 18], fill=_rgba((236, 110, 140)))
        d.point((11, 16), fill=_rgba((250, 220, 100)))
    else:
        for (x, y, w, h) in [(10, 20, 9, 10), (17, 14, 8, 9), (8, 11, 7, 8), (19, 24, 8, 7)]:
            d.ellipse([x, y, x + w, y + h], fill=_rgba(green if (x + y) % 2 else rib))
        for (x, y) in [(12, 10), (21, 13)]:
            d.ellipse([x, y, x + 2, y + 2], fill=_rgba((200, 60, 90)))
    for _ in range(14):
        x, y = int(r.integers(4, 28)), int(r.integers(5, 30))
        if im.getpixel((x, y))[3]:
            d.point((x, y), fill=_rgba(spine))
    return shadow(outline(im))


def termite_mound(seed: int) -> Image.Image:
    """A termite hill of red earth, taller than a man, fluted by the rain."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    earth = (160, 96, 60)
    peaks = [(16, 3), (11, 9), (21, 7)]
    for (x, y) in peaks[: 2 + seed % 2]:
        x += int(r.integers(-1, 2))
        d.polygon([(x, y), (x - 6, 31), (x + 6, 31)], fill=_rgba(earth))
        d.polygon([(x, y), (x - 6, 31), (x - 1, 31)], fill=_rgba(shade(earth, 1.15)))
    for _ in range(8):
        x = int(r.integers(8, 24))
        y = int(r.integers(10, 29))
        if im.getpixel((x, y))[3]:
            d.line([(x, y), (x, y + 3)], fill=_rgba(shade(earth, 0.75)))
    return shadow(outline(noise_shade(im, seed, 0.10)))


def glowcaps(seed: int) -> Image.Image:
    """Mushrooms that glow in the dark of the deep woods and the deep places."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    cap, core = [((80, 210, 200), (200, 255, 246)), ((170, 120, 236), (236, 210, 255)),
                 ((120, 220, 120), (220, 255, 200))][seed % 3]
    for _ in range(int(r.integers(3, 6))):
        x, y = int(r.integers(6, 26)), int(r.integers(14, 28))
        rad = int(r.integers(2, 5))
        d.line([(x, y), (x, y - rad - 1)], fill=_rgba((214, 210, 196)))
        d.pieslice([x - rad, y - rad * 2 - 1, x + rad, y - 1], 180, 360, fill=_rgba(cap))
        d.point((x - 1, y - rad - 1), fill=_rgba(core))
    return outline(im, (16, 24, 30, 255))


def fumarole(frame: int) -> Image.Image:
    """A vent in the rock, crusted yellow, breathing steam (three frames)."""
    im = blank()
    d = ImageDraw.Draw(im)
    d.ellipse([7, 22, 25, 30], fill=_rgba((62, 58, 56)))
    d.ellipse([10, 24, 22, 28], fill=_rgba((22, 18, 18)))
    for x, y in [(8, 24), (23, 25), (11, 29), (20, 29), (16, 23)]:
        d.point((x, y), fill=_rgba((214, 196, 70)))
    puffs = [(16, 20, 4), (14, 13, 5), (18, 6, 5)]
    for i, (x, y, rad) in enumerate(puffs):
        y -= frame * 2
        x += (frame + i) % 2
        a = 200 - i * 50
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(230, 230, 226, a))
    return im


def dry_tufts(seed: int) -> Image.Image:
    """Bleached tufts of steppe and savanna grass."""
    return tufts(seed, [(186, 164, 92), (164, 144, 78), (204, 184, 110), (140, 128, 74)], count=12, tall=7)


def feather_grass(seed: int) -> Image.Image:
    """Feather grass of the steppe, silver plumes bending in the wind."""
    r = rng(seed)
    im = tufts(seed, [(170, 160, 96), (150, 146, 86)], count=7, tall=6)
    d = ImageDraw.Draw(im)
    for _ in range(6):
        x, y = int(r.integers(3, S - 3)), int(r.integers(10, S - 2))
        for k in range(5):
            d.point((x + k, y - k // 2 - 4), fill=(226, 224, 210, 230 - k * 30))
    return im


def ripples(seed: int) -> Image.Image:
    """Wind ripples across sand."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    phase = r.uniform(0, 6.28)
    for row in range(5):
        y0 = 3 + row * 6 + int(r.integers(-1, 2))
        for x in range(S):
            y = y0 + 1.6 * math.sin(x * 0.32 + phase + row)
            d.point((x, y), fill=(150, 116, 70, 150))
            d.point((x, y - 1), fill=(250, 226, 170, 90))
    return im


# ---------------------------------------------------------------------------- ground
def _ground(seed: int, base, spread: float = 0.06) -> np.ndarray:
    r = rng(seed)
    n = r.normal(0, 1, (S, S))
    n = (n + np.roll(n, 1, 0) + np.roll(n, 1, 1) + np.roll(n, (1, 1), (0, 1))) / 4
    a = np.zeros((S, S, 4), np.float32)
    a[..., :3] = np.array(base, np.float32) * (1 + spread * n[..., None])
    a[..., 3] = 255
    return a


def salt(seed: int) -> Image.Image:
    """A salt pan: white crust cracked into plates, the cracks a little dark with damp."""
    r = rng(seed)
    a = _ground(seed, (226, 222, 210), 0.04)
    im = img(a)
    d = ImageDraw.Draw(im)
    pts = [(int(r.integers(0, S)), int(r.integers(0, S))) for _ in range(7)]
    for (x, y) in pts:  # each plate's edges: a few short straight cracks out from a point
        for _ in range(3):
            ang = r.uniform(0, 6.28)
            length = r.uniform(5, 11)
            d.line([(x, y), (x + math.cos(ang) * length, y + math.sin(ang) * length)], fill=(176, 170, 156, 255))
    for _ in range(10):
        x, y = int(r.integers(0, S)), int(r.integers(0, S))
        d.point((x, y), fill=(248, 248, 244, 255))
    return im


def ash(seed: int) -> Image.Image:
    """Volcanic ash and cinders: grey-black, soft, with a red ember of pumice here and there."""
    r = rng(seed)
    a = _ground(seed, (74, 70, 70), 0.10)
    im = img(a)
    d = ImageDraw.Draw(im)
    for _ in range(18):
        x, y = int(r.integers(0, S)), int(r.integers(0, S))
        d.point((x, y), fill=(118, 112, 108, 255) if r.random() < 0.7 else (40, 36, 36, 255))
    for _ in range(3):
        x, y = int(r.integers(1, S - 2)), int(r.integers(1, S - 2))
        d.rectangle([x, y, x + 1, y], fill=(120, 56, 44, 255))
    return im


def crevasse(seed: int) -> Image.Image:
    """Glacier ice split by a crack too deep to see the bottom of."""
    r = rng(seed)
    a = _ground(seed, (196, 218, 232), 0.04)
    im = img(a)
    d = ImageDraw.Draw(im)
    horizontal = seed % 2 == 0
    pts = []
    for i in range(9):
        t = i * 4
        off = 16 + int(r.integers(-3, 4))
        pts.append((t, off) if horizontal else (off, t))
    for w, c in ((7, (120, 160, 196)), (5, (40, 70, 110)), (2, (12, 18, 34))):
        d.line(pts, fill=c + (255,), width=w)
    return im


def obsidian(seed: int) -> Image.Image:
    """Black volcanic glass, with a cold shine where it breaks."""
    r = rng(seed)
    a = _ground(seed, (34, 30, 38), 0.12)
    im = img(a)
    d = ImageDraw.Draw(im)
    for _ in range(5):
        x, y = int(r.integers(1, S - 6)), int(r.integers(1, S - 3))
        d.line([(x, y), (x + int(r.integers(3, 7)), y + int(r.integers(-2, 3)))], fill=(150, 150, 176, 255))
    return im


def ice_wall(seed: int) -> Image.Image:
    """A wall of old glacier ice, blue in its depths."""
    r = rng(seed)
    a = _ground(seed, (140, 184, 214), 0.08)
    im = img(a)
    d = ImageDraw.Draw(im)
    for _ in range(6):  # layers in the ice
        y = int(r.integers(2, S - 2))
        d.line([(0, y), (S, y + int(r.integers(-2, 3)))], fill=(96, 140, 184, 255))
    for _ in range(4):
        x = int(r.integers(2, S - 2))
        d.line([(x, 0), (x + int(r.integers(-3, 4)), S)], fill=(214, 236, 248, 255))
    return im


def cliff_wall(seed: int, base=(128, 112, 98)) -> Image.Image:
    """A rock face: bands of stone in layers, a crack, light from the top."""
    r = rng(seed)
    a = _ground(seed, base, 0.08)
    for y in range(S):
        a[y, :, :3] *= 1.08 - 0.012 * y
    im = img(a)
    d = ImageDraw.Draw(im)
    y = 0
    while y < S:
        y += int(r.integers(4, 8))
        d.line([(0, y), (S, y + int(r.integers(-1, 2)))], fill=_rgba(shade(base, 0.7)))
        d.line([(0, y + 1), (S, y + 1)], fill=_rgba(shade(base, 1.18)))
    x = int(r.integers(6, 26))
    d.line([(x, 0), (x + int(r.integers(-3, 4)), 14), (x + int(r.integers(-2, 3)), S)], fill=_rgba(shade(base, 0.5)))
    return im


def bark_wall(seed: int) -> Image.Image:
    """The trunk of a giant tree, seen close: deep ridges of bark."""
    r = rng(seed)
    a = _ground(seed, (104, 78, 56), 0.08)
    im = img(a)
    d = ImageDraw.Draw(im)
    for _ in range(8):
        x = int(r.integers(0, S))
        d.line([(x, 0), (x + int(r.integers(-2, 3)), S)], fill=(62, 44, 30, 255), width=int(r.integers(1, 3)))
    for _ in range(5):
        x, y = int(r.integers(0, S)), int(r.integers(0, S))
        d.point((x, y), fill=(140, 164, 90, 255))  # moss
    return im


# ---------------------------------------------------------------------------- things of the wonders
def falls(frame: int) -> Image.Image:
    """Falling water: white streaks sliding down over blue (three frames)."""
    a = np.zeros((S, S, 4), np.float32)
    a[..., 0], a[..., 1], a[..., 2], a[..., 3] = 90, 140, 196, 255
    r = rng(1000)
    cols = r.integers(0, S, 14)
    for i, x in enumerate(cols):
        length = int(r.integers(6, 14))
        y0 = (int(r.integers(0, S)) + frame * 5) % S
        for k in range(length):
            y = (y0 + k) % S
            a[y, x, :3] = (236, 244, 250) if k < length - 2 else (180, 206, 230)
    return img(a)


def spray(frame: int) -> Image.Image:
    """Spray and foam at the foot of falls (drawn over water)."""
    r = rng(1100 + frame)
    im = blank()
    d = ImageDraw.Draw(im)
    for _ in range(16):
        x, y = int(r.integers(0, S)), int(r.integers(0, S))
        rad = int(r.integers(1, 4))
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(240, 246, 250, int(r.integers(90, 200))))
    return im


def steam(frame: int) -> Image.Image:
    """Steam rising off hot water (three frames)."""
    im = blank()
    d = ImageDraw.Draw(im)
    for i, (x, y, rad) in enumerate([(10, 22, 4), (20, 16, 5), (13, 8, 4)]):
        y = (y - frame * 3) % S
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(236, 240, 240, 110 - i * 20))
    return im


def stone_arch(seed: int) -> Image.Image:
    """A natural arch of red stone, carved by the wind."""
    im = blank()
    d = ImageDraw.Draw(im)
    rock = (176, 104, 70)
    d.rectangle([3, 12, 9, 31], fill=_rgba(rock))
    d.rectangle([23, 10, 29, 31], fill=_rgba(shade(rock, 0.85)))
    d.pieslice([3, 1, 29, 27], 180, 360, fill=_rgba(rock))
    d.pieslice([9, 8, 23, 24], 180, 360, fill=(0, 0, 0, 0))
    d.rectangle([9, 16, 23, 31], fill=(0, 0, 0, 0))
    for y in range(4, 30, 5):
        d.line([(3, y), (9, y)], fill=_rgba(shade(rock, 0.75)))
        d.line([(23, y + 2), (29, y + 2)], fill=_rgba(shade(rock, 0.7)))
    return shadow(outline(noise_shade(im, seed, 0.08)))


def drifting_stone(seed: int) -> Image.Image:
    """A boulder hanging in the air, its shadow on the ground beneath it."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    d.ellipse([9, 26, 23, 30], fill=(0, 0, 0, 90))
    rock = (138, 132, 140)
    pts = [(8 + int(r.integers(0, 3)), 12), (13, 4 + int(r.integers(0, 3))), (21, 5), (25, 12 + int(r.integers(0, 3))),
           (19, 19), (11, 18)]
    d.polygon(pts, fill=_rgba(rock))
    d.polygon(pts[:3] + [(16, 12)], fill=_rgba(shade(rock, 1.2)))
    for _ in range(3):  # roots and earth still hanging from its underside
        x = int(r.integers(12, 21))
        d.line([(x, 18), (x + int(r.integers(-1, 2)), 21 + int(r.integers(0, 2)))], fill=_rgba((96, 74, 52)))
    d.point((16, 3), fill=_rgba((200, 230, 255)))
    return outline(noise_shade(im, seed, 0.08))


def geyser(frame: int) -> Image.Image:
    """A geyser's cone of sinter, and its spout (three frames, the middle one high)."""
    im = blank()
    d = ImageDraw.Draw(im)
    d.ellipse([6, 24, 26, 31], fill=_rgba((208, 196, 168)))
    d.ellipse([12, 25, 20, 29], fill=_rgba((90, 160, 176)))
    height = (8, 22, 14)[frame % 3]
    for k in range(height):
        w = 1 + k // 6
        d.line([(16 - w, 26 - k), (16 + w, 26 - k)], fill=(236, 244, 250, 220 - k * 6))
    return im


def water_tile(seed: int, base, light, sparkle=None) -> Image.Image:
    """Still water of some colour, with soft lighter swirls (glowing lakes, hot springs)."""
    r = rng(seed)
    a = _ground(seed, base, 0.05)
    for _ in range(5):
        x, y = int(r.integers(0, S)), int(r.integers(0, S))
        for k in range(6):
            xx, yy = (x + k) % S, (y + int(round(math.sin(k * 0.9) * 1.5))) % S
            a[yy, xx, :3] = light
    if sparkle is not None:
        for _ in range(4):
            a[int(r.integers(0, S)), int(r.integers(0, S)), :3] = sparkle
    return img(a)


def sinter(seed: int) -> Image.Image:
    """The springs' white stone, laid down in little terraces like frozen waves."""
    r = rng(seed)
    a = _ground(seed, (226, 216, 188), 0.04)
    im = img(a)
    d = ImageDraw.Draw(im)
    for row in range(5):
        y0 = 3 + row * 6 + int(r.integers(-1, 2))
        pts = [(x, y0 + 1.5 * math.sin(x * 0.4 + row * 2 + seed)) for x in range(0, S + 1, 2)]
        d.line(pts, fill=(176, 160, 128, 255))
        d.line([(x, y + 1) for x, y in pts], fill=(244, 238, 222, 255))
    for _ in range(4):
        x, y = int(r.integers(0, S)), int(r.integers(0, S))
        d.point((x, y), fill=(210, 150, 90, 255))  # a stain of iron
    return im


def chasm(seed: int) -> Image.Image:
    """The pit: darkness with a little mist in it."""
    r = rng(seed)
    a = _ground(seed, (10, 10, 16), 0.3)
    im = img(a)
    d = ImageDraw.Draw(im)
    for _ in range(3):
        x, y = int(r.integers(0, S)), int(r.integers(0, S))
        d.ellipse([x - 5, y - 2, x + 5, y + 2], fill=(60, 64, 76, 70))
    return im


def roots(seed: int) -> Image.Image:
    """Roots as thick as a wall, snaking across the ground (drawn over earth)."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    y = 10 + int(r.integers(0, 12))
    pts = [(x, y + 3 * math.sin(x * 0.25 + seed)) for x in range(-2, S + 3, 3)]
    d.line(pts, fill=(96, 72, 48, 255), width=7)
    d.line([(x, yy - 2) for x, yy in pts], fill=(140, 108, 72, 255), width=2)
    return outline(im)


def brine(seed: int) -> Image.Image:
    """A skin of salt water lying on the salt (drawn over the crust)."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    x, y = int(r.integers(6, 20)), int(r.integers(6, 20))
    d.ellipse([x - 6, y - 4, x + 12, y + 8], fill=(150, 180, 186, 170))
    d.line([(x - 2, y), (x + 4, y)], fill=(230, 244, 246, 200))
    return im


def cairn(seed: int) -> Image.Image:
    """A cairn of stones on a summit, with a rag of prayer-flag on a pole."""
    im = blank()
    d = ImageDraw.Draw(im)
    stones = [(10, 25, 22, 31), (8, 20, 18, 26), (14, 19, 24, 26), (11, 14, 20, 20), (13, 9, 19, 15)]
    for i, (x0, y0, x1, y1) in enumerate(stones):
        c = (150 + i * 8, 146 + i * 8, 140 + i * 8, 255)
        d.ellipse([x0, y0, x1, y1], fill=c)
    d.line([(17, 10), (17, 1)], fill=(110, 84, 56, 255))
    for k, col in enumerate([(200, 60, 50), (230, 200, 80), (60, 110, 190)]):
        d.rectangle([18, 1 + k * 2, 22, 2 + k * 2], fill=col + (255,))
    return shadow(outline(noise_shade(im, seed, 0.08)))


def moonstone(seed: int) -> Image.Image:
    """A pale standing stone that seems to hold the moonlight."""
    im = blank()
    d = ImageDraw.Draw(im)
    d.polygon([(11, 31), (12, 6), (16, 2), (20, 6), (21, 31)], fill=(196, 210, 226, 255))
    d.polygon([(11, 31), (12, 6), (16, 2), (15, 31)], fill=(224, 236, 248, 255))
    for y, sign in ((10, "o"), (16, "+"), (22, "x")):  # faint marks cut in it
        if sign == "o":
            d.ellipse([14, y - 1, 17, y + 2], outline=(120, 170, 230, 255))
        elif sign == "+":
            d.line([(15, y - 2), (15, y + 2)], fill=(120, 170, 230, 255))
            d.line([(13, y), (17, y)], fill=(120, 170, 230, 255))
        else:
            d.line([(13, y - 2), (17, y + 2)], fill=(120, 170, 230, 255))
            d.line([(17, y - 2), (13, y + 2)], fill=(120, 170, 230, 255))
    return shadow(outline(im, (20, 26, 40, 255)))


def all_drawn() -> dict[str, Image.Image]:
    out: dict[str, Image.Image] = {}
    for i in range(3):
        out[f"water/glow_{i}"] = water_tile(1500 + i, (24, 120, 120), (120, 240, 210), (220, 255, 240))
        out[f"water/glow_shallow_{i}"] = water_tile(1510 + i, (60, 150, 150), (150, 246, 226), (230, 255, 246))
        out[f"water/hot_{i}"] = water_tile(1520 + i, (96, 170, 180), (170, 222, 226))
        out[f"floor/sinter_{i}"] = sinter(1530 + i)
        out[f"floor/chasm_{i}"] = chasm(1540 + i)
        out[f"deco/roots_{i}"] = roots(1550 + i)
        out[f"deco/brine_{i}"] = brine(1560 + i)
    out["feature/cairn"] = cairn(1570)
    out["feature/moonstone"] = moonstone(1580)
    for i in range(3):
        out[f"tree/palm_{i}"] = palm(1200 + i)
        out[f"tree/acacia_{i}"] = acacia(1210 + i)
        out[f"tree/jungle_{i}"] = jungle_tree(1220 + i)
        out[f"tree/fey_{i}"] = fey_tree(1230 + i)
        out[f"tree/stone_{i}"] = petrified_tree(1240 + i)
        out[f"feature/cactus_{i}"] = cactus(1250 + i)
        out[f"feature/glowcap_{i}"] = glowcaps(1260 + i)
        out[f"feature/fumarole_{i}"] = fumarole(i)
        out[f"feature/geyser_{i}"] = geyser(i)
        out[f"deco/drygrass_{i}"] = dry_tufts(1270 + i)
        out[f"deco/feathergrass_{i}"] = feather_grass(1280 + i)
        out[f"deco/ripples_{i}"] = ripples(1290 + i)
        out[f"water/falls_{i}"] = falls(i)
        out[f"deco/spray_{i}"] = spray(i)
        out[f"deco/steam_{i}"] = steam(i)
    for i in range(2):
        out[f"feature/termite_{i}"] = termite_mound(1300 + i)
        out[f"feature/arch_{i}"] = stone_arch(1310 + i)
        out[f"feature/drifting_{i}"] = drifting_stone(1320 + i)
        out[f"floor/crevasse_{i}"] = crevasse(1330 + i)
    for i in range(4):
        out[f"floor/salt_{i}"] = salt(1340 + i)
        out[f"floor/ash_{i}"] = ash(1350 + i)
        out[f"floor/obsidian_{i}"] = obsidian(1360 + i)
        out[f"wall/ice_{i}"] = ice_wall(1370 + i)
        out[f"wall/cliff_{i}"] = cliff_wall(1380 + i)
        out[f"wall/cliff_red_{i}"] = cliff_wall(1390 + i, (150, 86, 60))
        out[f"wall/bark_{i}"] = bark_wall(1400 + i)
    return out
