"""Tiles drawn in code, for things the Dungeon Crawl pack does not have: furniture, fences, crops, pines,
the overworld's town and ruin marks, and the icons on the action bar.

Everything here is 32x32 RGBA (numpy uint8, [y, x, rgba] like an image), drawn to sit beside the Dungeon Crawl
tiles: a dark outline, light from the top left, a little noise. Used only by tools/build_tiles.py.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

S = 32
OUTLINE = (18, 14, 10, 255)


# ---------------------------------------------------------------------------- helpers
def rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def blank(size: int = S) -> Image.Image:
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))


def arr(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("RGBA"), dtype=np.uint8).copy()


def img(a: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def outline(im: Image.Image, color=OUTLINE) -> Image.Image:
    """A one-pixel dark edge around everything opaque (what makes the Crawl tiles read on any ground)."""
    a = arr(im)
    alpha = a[..., 3] > 40
    grown = alpha.copy()
    grown[1:, :] |= alpha[:-1, :]
    grown[:-1, :] |= alpha[1:, :]
    grown[:, 1:] |= alpha[:, :-1]
    grown[:, :-1] |= alpha[:, 1:]
    edge = grown & ~alpha
    a[edge] = color
    return img(a)


def noise_shade(im: Image.Image, seed: int, amount: float = 0.12) -> Image.Image:
    """Speckle the colours a little so flat shapes look painted, not filled."""
    a = arr(im).astype(np.float32)
    n = rng(seed).uniform(1 - amount, 1 + amount, a.shape[:2])
    a[..., :3] *= n[..., None]
    return img(a)


def shadow(im: Image.Image, dx: int = 2, dy: int = 2, alpha: int = 90) -> Image.Image:
    """A soft drop shadow under a sprite, so it stands on the ground."""
    a = arr(im)
    sh = np.zeros_like(a)
    m = a[..., 3] > 0
    sh[dy:, dx:, 3] = np.where(m[: S - dy, : S - dx] if a.shape[0] == S else m[: a.shape[0] - dy, : a.shape[1] - dx], alpha, 0)
    sh_img = img(sh).filter(ImageFilter.GaussianBlur(0.8))
    out = Image.alpha_composite(sh_img, im)
    return out


def lerp(c1, c2, t):
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3]) + ((c[3],) if len(c) > 3 else (255,))


def supersample(draw_fn, size: int = S, scale: int = 4) -> Image.Image:
    """Draw at `scale` times the size and shrink: smooth edges for icons."""
    big = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(big), scale)
    return big.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------------------- ground
def planks(seed: int, base=(104, 72, 44)) -> Image.Image:
    """A wooden floor: planks running across, joints staggered, grain."""
    r = rng(seed)
    a = np.zeros((S, S, 4), np.float32)
    a[..., 3] = 255
    for row in range(4):
        y0 = row * 8
        tone = r.uniform(0.82, 1.08)
        joint = int(r.integers(4, 28))
        for y in range(y0, y0 + 8):
            for x in range(S):
                g = 1 + 0.07 * math.sin(x * 0.7 + y * 2.1 + seed) + r.uniform(-0.05, 0.05)
                c = [v * tone * g for v in base]
                if y == y0:
                    c = [v * 0.55 for v in base]
                elif y == y0 + 1:
                    c = [v * 1.12 * tone for v in base]
                if x == joint or x == (joint + 16) % S and row % 2:
                    c = [v * 0.6 for v in base]
                a[y, x, :3] = c
    return img(a)


def snow(seed: int) -> Image.Image:
    r = rng(seed)
    base = np.array([214, 220, 230], np.float32)
    n = r.normal(0, 1, (S, S))
    n = (n + np.roll(n, 1, 0) + np.roll(n, 1, 1) + np.roll(n, (1, 1), (0, 1))) / 4
    a = np.zeros((S, S, 4), np.float32)
    a[..., :3] = base * (0.93 + 0.05 * n[..., None])
    a[..., 2] += 6
    for _ in range(5):  # little blue hollows
        x, y = r.integers(2, S - 4, 2)
        a[y, x : x + 3, :3] *= 0.86
    a[..., 3] = 255
    return img(a)


def tinted(src: Image.Image, color, keep: float = 0.35) -> Image.Image:
    """Recolour a ground tile towards `color`, keeping some of its light and dark."""
    a = arr(src).astype(np.float32)
    lum = a[..., :3].mean(axis=2, keepdims=True) / 128.0
    tgt = np.array(color, np.float32)[None, None, :]
    a[..., :3] = a[..., :3] * keep + tgt * lum * (1 - keep)
    return img(a)


# ---------------------------------------------------------------------------- overlays (drawn over ground)
def tufts(seed: int, colors, count: int = 9, tall: int = 6) -> Image.Image:
    """Grass or heather tufts, drawn over a ground tile."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    for _ in range(count):
        x, y = int(r.integers(2, S - 2)), int(r.integers(tall + 2, S - 1))
        c = colors[int(r.integers(0, len(colors)))]
        for k in range(int(r.integers(2, 4))):
            dx = int(r.integers(-2, 3))
            h = int(r.integers(tall // 2, tall + 1))
            d.line([(x, y), (x + dx, y - h)], fill=c + (255,))
        d.point((x, y), fill=shade(c, 0.5))
    return im


def flowers(seed: int, color) -> Image.Image:
    r = rng(seed)
    im = tufts(seed, [(70, 110, 50), (90, 120, 60)], count=6, tall=4)
    d = ImageDraw.Draw(im)
    for _ in range(6):
        x, y = int(r.integers(3, S - 3)), int(r.integers(3, S - 3))
        d.point((x, y), fill=color + (255,))
        d.point((x + 1, y), fill=shade(color, 0.7))
    return im


def leaves(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    cols = [(150, 96, 40), (120, 74, 34), (170, 120, 50), (98, 70, 40)]
    for _ in range(14):
        x, y = int(r.integers(1, S - 3)), int(r.integers(1, S - 2))
        c = cols[int(r.integers(0, len(cols)))]
        d.rectangle([x, y, x + 1, y], fill=c + (255,))
    return im


def needles(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    for _ in range(26):
        x, y = int(r.integers(0, S - 3)), int(r.integers(0, S - 1))
        c = (110 + int(r.integers(0, 30)), 80 + int(r.integers(0, 20)), 50, 200)
        d.line([(x, y), (x + int(r.integers(-2, 3)), y + 1)], fill=c)
    return im


def pebbles(seed: int, n: int = 7, color=(128, 124, 116)) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    for _ in range(n):
        x, y = int(r.integers(2, S - 6)), int(r.integers(2, S - 5))
        w, h = int(r.integers(2, 6)), int(r.integers(2, 4))
        tone = r.uniform(0.75, 1.15)
        d.ellipse([x, y, x + w, y + h], fill=shade(color + (255,), tone))
        d.point((x + 1, y), fill=shade(color + (255,), tone * 1.3))
    return outline(im, (30, 28, 26, 200))


def reeds(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    for _ in range(8):
        x, y = int(r.integers(3, S - 3)), int(r.integers(14, S - 2))
        h = int(r.integers(8, 15))
        d.line([(x, y), (x + int(r.integers(-1, 2)), y - h)], fill=(96, 120, 60, 255))
        if r.random() < 0.5:
            d.rectangle([x - 1, y - h, x, y - h + 3], fill=(92, 60, 36, 255))  # a bulrush head
    return im


def crops(seed: int, ripe: bool) -> Image.Image:
    """Rows of a field: green shoots, or ripe wheat."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    stalk = (150, 140, 60) if ripe else (80, 130, 54)
    head = (206, 178, 92) if ripe else (110, 160, 70)
    for row in range(4):
        y = 6 + row * 8
        d.line([(0, y + 2), (S, y + 2)], fill=(70, 50, 32, 160))  # the furrow
        for x in range(1, S, 3):
            h = int(r.integers(3, 6))
            xx = x + int(r.integers(-1, 2))
            d.line([(xx, y + 1), (xx, y + 1 - h)], fill=stalk + (255,))
            d.point((xx, y + 1 - h), fill=head + (255,))
    return im


def garden(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    for row in range(3):
        for col in range(3):
            x, y = 4 + col * 10 + int(r.integers(-1, 2)), 5 + row * 10 + int(r.integers(-1, 2))
            c = [(84, 140, 70), (110, 150, 80), (70, 120, 90)][int(r.integers(0, 3))]
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=c + (255,))
            d.ellipse([x - 1, y - 2, x + 1, y], fill=shade(c + (255,), 1.3))
    return outline(im, (24, 30, 20, 220))


# ---------------------------------------------------------------------------- trees
def pine(seed: int, snowy: bool = False) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([14, 25, 17, 30], fill=(74, 50, 30, 255))
    dark, mid, light = (22, 54, 34), (34, 78, 46), (60, 106, 62)
    tiers = [(26, 13), (19, 11), (12, 8), (6, 5)]
    for i, (y, half) in enumerate(tiers):
        half += int(r.integers(-1, 2))
        d.polygon([(16, y - 9), (16 - half, y), (16 + half, y)], fill=mid + (255,))
        d.polygon([(16, y - 9), (16 - half, y), (16 - 1, y)], fill=light + (255,))
        d.line([(16 - half, y), (16 + half, y)], fill=dark + (255,))
        if snowy:
            d.line([(16 - half + 2, y - 1), (16 + 1, y - 1)], fill=(226, 232, 240, 255))
            d.point((16, y - 9), fill=(236, 240, 246, 255))
    im = noise_shade(im, seed, 0.10)
    return shadow(outline(im))


def dead_tree(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    bark = (92, 76, 62, 255)
    d.line([(16, 30), (16, 12)], fill=bark, width=3)

    def branch(x, y, ang, length, depth):
        if depth == 0 or length < 2:
            return
        x2 = x + math.cos(ang) * length
        y2 = y - math.sin(ang) * length
        d.line([(x, y), (x2, y2)], fill=bark, width=max(1, depth - 1))
        for da in (-0.5, 0.45):
            branch(x2, y2, ang + da + r.uniform(-0.2, 0.2), length * 0.66, depth - 1)

    branch(16, 14, math.pi / 2, 7, 4)
    branch(16, 20, math.pi * 0.8, 6, 3)
    branch(16, 18, math.pi * 0.2, 6, 3)
    return shadow(outline(im))


def recolor_tree(src: Image.Image, hue_to: float, sat: float = 0.85, val: float = 0.9) -> Image.Image:
    """Turn an autumn tree green: shift the leaves' hue, keep the trunk."""
    hsv = src.convert("RGB").convert("HSV")
    h = np.asarray(hsv, np.float32).copy()
    a = arr(src)
    leafy = (h[..., 1] > 90) & (h[..., 2] > 70)
    h[..., 0] = np.where(leafy, hue_to, h[..., 0])
    h[..., 1] = np.where(leafy, h[..., 1] * sat, h[..., 1])
    h[..., 2] = np.where(leafy, h[..., 2] * val, h[..., 2])
    rgb = np.asarray(Image.fromarray(h.astype(np.uint8), "HSV").convert("RGB"))
    out = np.dstack([rgb, a[..., 3]])
    return img(out)


# ---------------------------------------------------------------------------- furniture and features
WOOD = (120, 84, 50)


def table(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([4, 9, 27, 24], fill=WOOD + (255,))
    for y in (13, 18, 22):
        d.line([(5, y), (26, y)], fill=shade(WOOD + (255,), 0.75))
    d.line([(5, 10), (26, 10)], fill=shade(WOOD + (255,), 1.25))
    d.rectangle([5, 25, 7, 27], fill=shade(WOOD + (255,), 0.5))
    d.rectangle([24, 25, 26, 27], fill=shade(WOOD + (255,), 0.5))
    r = rng(seed)
    if r.random() < 0.6:  # a mug, a bowl, a candle
        d.ellipse([9, 12, 13, 16], fill=(170, 160, 140, 255))
        d.ellipse([10, 13, 12, 15], fill=(90, 60, 40, 255))
    if r.random() < 0.5:
        d.rectangle([20, 12, 21, 16], fill=(230, 220, 180, 255))
        d.point((20, 11), fill=(255, 200, 80, 255))
    return shadow(outline(noise_shade(im, seed, 0.06)))


def bed(seed: int, blanket=(120, 46, 40)) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([7, 3, 24, 29], fill=shade(WOOD + (255,), 0.85))
    d.rectangle([9, 5, 22, 10], fill=(214, 206, 186, 255))
    d.rectangle([9, 11, 22, 27], fill=blanket + (255,))
    for y in range(13, 27, 4):
        d.line([(9, y), (22, y)], fill=shade(blanket + (255,), 0.75))
    d.line([(9, 11), (22, 11)], fill=shade(blanket + (255,), 1.3))
    return shadow(outline(noise_shade(im, seed, 0.05)))


def bedroll(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    c = (96, 84, 60, 255)
    d.rounded_rectangle([6, 8, 25, 26], 4, fill=c)
    d.rectangle([6, 8, 25, 12], fill=shade(c, 1.2))
    d.line([(6, 20), (25, 20)], fill=shade(c, 0.7))
    return shadow(outline(noise_shade(im, seed, 0.06)))


def anvil(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    iron = (96, 96, 104, 255)
    d.polygon([(4, 10), (26, 10), (28, 13), (22, 15), (20, 15), (20, 20), (12, 20), (12, 15), (8, 15), (4, 13)], fill=iron)
    d.rectangle([10, 21, 22, 25], fill=shade(iron, 0.8))
    d.line([(5, 10), (25, 10)], fill=shade(iron, 1.6))
    d.rectangle([7, 26, 25, 29], fill=(80, 58, 40, 255))  # the stump it stands on
    return shadow(outline(im))


def well(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    stone = (128, 124, 116, 255)
    d.ellipse([3, 5, 28, 28], fill=stone)
    d.ellipse([8, 10, 23, 23], fill=(18, 30, 44, 255))
    d.ellipse([10, 13, 18, 18], fill=(36, 62, 86, 255))
    for k in range(10):  # the joints between stones
        ang = k / 10 * math.tau
        x0, y0 = 15.5 + math.cos(ang) * 8, 16.5 + math.sin(ang) * 8
        x1, y1 = 15.5 + math.cos(ang) * 12, 16.5 + math.sin(ang) * 12
        d.line([(x0, y0), (x1, y1)], fill=shade(stone, 0.6))
    d.line([(3, 6), (28, 6)], fill=(90, 62, 40, 255), width=2)  # the windlass beam
    return shadow(outline(noise_shade(im, seed, 0.08)))


def hearth(frame: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    stone = (108, 100, 92, 255)
    d.rectangle([3, 6, 28, 28], fill=stone)
    d.rectangle([7, 12, 24, 28], fill=(26, 18, 14, 255))
    d.line([(3, 6), (28, 6)], fill=shade(stone, 1.4), width=2)
    for y in range(9, 28, 5):
        d.line([(3, y), (6, y)], fill=shade(stone, 0.7))
        d.line([(25, y), (28, y)], fill=shade(stone, 0.7))
    d.rectangle([9, 24, 22, 27], fill=(70, 44, 26, 255))  # logs
    flames = [[(10, 24), (13, 15), (16, 22), (18, 13), (21, 24)],
              [(10, 24), (12, 17), (15, 21), (17, 14), (21, 24)],
              [(10, 24), (14, 14), (16, 21), (19, 16), (21, 24)]][frame % 3]
    d.polygon(flames, fill=(230, 120, 40, 255))
    inner = [(x if i in (0, len(flames) - 1) else x, y + 4 if i not in (0, len(flames) - 1) else y) for i, (x, y) in enumerate(flames)]
    d.polygon(inner, fill=(250, 210, 90, 255))
    return outline(im)


def campfire(frame: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    for k in range(8):  # ring of stones
        ang = k / 8 * math.tau
        x, y = 16 + math.cos(ang) * 10, 19 + math.sin(ang) * 7
        d.ellipse([x - 3, y - 2, x + 3, y + 2], fill=(110, 104, 96, 255))
    d.line([(9, 24), (23, 16)], fill=(86, 56, 32, 255), width=3)
    d.line([(9, 16), (23, 24)], fill=(76, 50, 30, 255), width=3)
    fl = [[(11, 22), (14, 10), (16, 18), (19, 8), (21, 22)], [(11, 22), (13, 12), (16, 17), (18, 9), (21, 22)],
          [(11, 22), (15, 9), (17, 17), (20, 11), (21, 22)]][frame % 3]
    d.polygon(fl, fill=(232, 112, 36, 255))
    d.polygon([(13, 22), (15, 14), (17, 19), (19, 15), (20, 22)], fill=(252, 214, 96, 255))
    return outline(im)


def stall(seed: int, stripe=(160, 50, 44)) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([3, 14, 28, 27], fill=WOOD + (255,))
    d.line([(3, 18), (28, 18)], fill=shade(WOOD + (255,), 0.7))
    for i, x in enumerate(range(2, 30, 4)):  # striped awning
        d.rectangle([x, 4, x + 3, 12], fill=(stripe if i % 2 == 0 else (220, 208, 180)) + (255,))
    d.line([(2, 12), (29, 12)], fill=(60, 40, 30, 255))
    r = rng(seed)
    for _ in range(4):  # goods on the counter
        x = int(r.integers(5, 24))
        c = [(200, 160, 60), (180, 60, 50), (120, 150, 70), (170, 150, 130)][int(r.integers(0, 4))]
        d.ellipse([x, 15, x + 3, 17], fill=c + (255,))
    return shadow(outline(im))


def notice_board(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle([6, 18, 8, 30], fill=(80, 56, 36, 255))
    d.rectangle([23, 18, 25, 30], fill=(80, 56, 36, 255))
    d.rectangle([3, 4, 28, 20], fill=(110, 78, 48, 255))
    d.rectangle([3, 3, 28, 4], fill=(70, 48, 30, 255))
    r = rng(seed)
    for _ in range(5):
        x, y = int(r.integers(5, 22)), int(r.integers(6, 15))
        d.rectangle([x, y, x + 4, y + 4], fill=(222, 212, 182, 255))
        d.line([(x + 1, y + 2), (x + 3, y + 2)], fill=(90, 80, 70, 255))
    return shadow(outline(im))


def grave(seed: int, cross: bool = False) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    d.ellipse([6, 20, 26, 30], fill=(72, 58, 44, 255))  # the mound
    stone = (130, 128, 122, 255)
    if cross:
        d.rectangle([14, 5, 17, 24], fill=stone)
        d.rectangle([9, 10, 22, 13], fill=stone)
    else:
        d.rounded_rectangle([10, 6, 21, 24], 5, fill=stone)
        d.line([(13, 12), (18, 12)], fill=shade(stone, 0.6))
        d.line([(13, 15), (18, 15)], fill=shade(stone, 0.6))
    return shadow(outline(noise_shade(im, seed, 0.08)))


def chains(seed: int) -> Image.Image:
    im = blank()
    d = ImageDraw.Draw(im)
    x, y = 4, 6
    for i in range(7):
        if i % 2 == 0:
            d.ellipse([x, y, x + 5, y + 3], outline=(150, 150, 156, 255))
        else:
            d.ellipse([x + 1, y - 1, x + 4, y + 4], outline=(120, 120, 128, 255))
        x += 3
        y += 3
    d.ellipse([20, 22, 28, 28], outline=(150, 150, 156, 255), width=2)  # the manacle
    return outline(im, (20, 18, 18, 200))


def bones(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    bone = (214, 204, 180, 255)
    for _ in range(3):
        x, y = int(r.integers(4, 22)), int(r.integers(6, 24))
        dx, dy = int(r.integers(-6, 7)), int(r.integers(-3, 4))
        d.line([(x, y), (x + dx, y + dy)], fill=bone, width=2)
        d.ellipse([x - 2, y - 2, x + 1, y + 1], fill=bone)
        d.ellipse([x + dx - 1, y + dy - 1, x + dx + 2, y + dy + 2], fill=bone)
    d.ellipse([14, 14, 21, 20], fill=bone)  # a skull
    d.point((16, 16), fill=(30, 26, 22, 255))
    d.point((19, 16), fill=(30, 26, 22, 255))
    return outline(im)


def boulder(seed: int) -> Image.Image:
    """A grey rock, lit from the top left."""
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    pts = []
    for k in range(9):
        ang = k / 9 * math.tau
        rad = 11 + r.uniform(-2, 2)
        pts.append((16 + math.cos(ang) * rad * 1.1, 18 + math.sin(ang) * rad * 0.85))
    d.polygon(pts, fill=(112, 110, 104, 255))
    d.ellipse([9, 9, 19, 17], fill=(146, 144, 136, 255))
    d.ellipse([18, 19, 27, 26], fill=(84, 82, 78, 255))
    d.line([(14, 20), (19, 23)], fill=(70, 68, 64, 255))
    return shadow(outline(noise_shade(im, seed, 0.08)))


def rubble(seed: int) -> Image.Image:
    return pebbles(seed, n=11, color=(118, 112, 104))


def fence(mask: int) -> Image.Image:
    """A fence piece joining towards its neighbours: N=1, E=2, S=4, W=8."""
    im = blank()
    d = ImageDraw.Draw(im)
    wood = (124, 92, 58, 255)
    dark = shade(wood, 0.6)
    cx, cy = 16, 18
    if mask & 2:
        d.line([(cx, cy - 4), (S, cy - 4)], fill=wood, width=2)
        d.line([(cx, cy + 1), (S, cy + 1)], fill=wood, width=2)
    if mask & 8:
        d.line([(0, cy - 4), (cx, cy - 4)], fill=wood, width=2)
        d.line([(0, cy + 1), (cx, cy + 1)], fill=wood, width=2)
    if mask & 1:
        d.line([(cx - 2, 0), (cx - 2, cy)], fill=dark, width=2)
        d.line([(cx + 2, 0), (cx + 2, cy)], fill=wood, width=2)
    if mask & 4:
        d.line([(cx - 2, cy), (cx - 2, S)], fill=dark, width=2)
        d.line([(cx + 2, cy), (cx + 2, S)], fill=wood, width=2)
    d.rectangle([cx - 2, cy - 9, cx + 1, cy + 6], fill=wood)  # the post
    d.line([(cx - 2, cy - 9), (cx + 1, cy - 9)], fill=shade(wood, 1.3))
    return shadow(outline(im), 1, 2, 70)


def palisade(seed: int) -> Image.Image:
    r = rng(seed)
    im = blank()
    d = ImageDraw.Draw(im)
    for x in range(0, S, 5):
        top = int(r.integers(1, 5))
        c = shade((116, 84, 52, 255), r.uniform(0.85, 1.1))
        d.rectangle([x, top + 4, x + 4, S - 1], fill=c)
        d.polygon([(x, top + 4), (x + 2, top), (x + 4, top + 4)], fill=c)
        d.line([(x, top + 4), (x, S - 1)], fill=shade(c, 0.6))
        d.line([(x + 1, top + 5), (x + 1, S - 1)], fill=shade(c, 1.25))
    d.line([(0, 20), (S, 20)], fill=(70, 50, 34, 255), width=2)
    return outline(im)


def wood_wall(seed: int) -> Image.Image:
    r = rng(seed)
    a = np.zeros((S, S, 4), np.float32)
    a[..., 3] = 255
    base = np.array([94, 66, 42], np.float32)
    for x0 in range(0, S, 8):
        tone = r.uniform(0.82, 1.1)
        for x in range(x0, x0 + 8):
            for y in range(S):
                g = 1 + 0.08 * math.sin(y * 0.6 + x * 1.3 + seed) + r.uniform(-0.05, 0.05)
                a[y, x, :3] = base * tone * g
            if x == x0:
                a[:, x, :3] = base * 0.5
            elif x == x0 + 1:
                a[:, x, :3] = base * 1.18 * tone
    a[0:2, :, :3] *= 0.6  # the eaves
    return img(a)


def bridge(vertical: bool, seed: int) -> Image.Image:
    im = planks(seed, (110, 80, 52))
    if vertical:
        im = im.rotate(90)
    d = ImageDraw.Draw(im)
    if vertical:
        d.line([(1, 0), (1, S)], fill=(60, 40, 26, 255), width=2)
        d.line([(S - 2, 0), (S - 2, S)], fill=(60, 40, 26, 255), width=2)
    else:
        d.line([(0, 1), (S, 1)], fill=(60, 40, 26, 255), width=2)
        d.line([(0, S - 2), (S, S - 2)], fill=(60, 40, 26, 255), width=2)
    return im


def captive_chains() -> Image.Image:
    """Chains drawn over a person: someone held prisoner."""
    im = blank()
    d = ImageDraw.Draw(im)
    for x in (8, 23):
        for y in range(18, 30, 3):
            d.ellipse([x - 1, y, x + 1, y + 2], outline=(160, 160, 168, 255))
    d.line([(8, 20), (23, 20)], fill=(150, 150, 156, 255))
    return im


# ---------------------------------------------------------------------------- the overworld's marks
INK = (40, 30, 22, 255)


def _house(d, x, y, w, h, roof=(132, 62, 44), wall=(196, 176, 138), scale=1):
    s = scale
    d.rectangle([x * s, (y + h // 2) * s, (x + w) * s, (y + h) * s], fill=wall + (255,), outline=INK, width=s)
    d.polygon([((x - 1) * s, (y + h // 2) * s), ((x + w / 2) * s, y * s), ((x + w + 1) * s, (y + h // 2) * s)],
              fill=roof + (255,), outline=INK)
    d.rectangle([(x + w / 2 - 1) * s, (y + h - 3) * s, (x + w / 2 + 1) * s, (y + h) * s], fill=(60, 40, 28, 255))


def town_mark(kind: str, size: int = 48) -> Image.Image:
    """A settlement as a little drawing on the map: a few houses, a wall, towers."""
    sc = 4

    def draw(d, s):
        k = size / 32  # drawing coordinates are in a 32 box, scaled to size
        def H(x, y, w, h, roof=(132, 62, 44), wall=(196, 176, 138)):
            _house(d, x * k, y * k, w * k, h * k, roof, wall, s)

        if kind == "hamlet":
            H(6, 12, 10, 12, (120, 80, 50))
            H(17, 15, 9, 10, (110, 70, 46))
        elif kind == "village":
            H(4, 13, 9, 11, (126, 74, 46))
            H(14, 8, 10, 12, (132, 62, 44))
            H(18, 17, 10, 11, (116, 82, 52))
            d.rectangle([11 * k * s, 4 * k * s, 13 * k * s, 13 * k * s], fill=(150, 140, 120, 255), outline=INK)
            d.polygon([(10 * k * s, 4 * k * s), (12 * k * s, 0), (14 * k * s, 4 * k * s)], fill=(90, 60, 50, 255), outline=INK)
        elif kind in ("town", "city"):
            wall = (150, 142, 128, 255)
            top = 10 if kind == "town" else 6
            d.rectangle([3 * k * s, top * k * s, 29 * k * s, 29 * k * s], fill=(120, 108, 92, 255), outline=INK, width=s)
            for x in range(4, 29, 4):  # crenellations
                d.rectangle([x * k * s, (top - 2) * k * s, (x + 2) * k * s, top * k * s], fill=wall, outline=INK)
            H(7, top + 3, 8, 9, (140, 60, 44))
            H(17, top + 5, 9, 9, (120, 70, 48))
            if kind == "city":
                for tx in (1, 25):
                    d.rectangle([tx * k * s, 2 * k * s, (tx + 6) * k * s, 29 * k * s], fill=wall, outline=INK, width=s)
                    d.polygon([((tx - 1) * k * s, 2 * k * s), ((tx + 3) * k * s, -3 * k * s), ((tx + 7) * k * s, 2 * k * s)],
                              fill=(70, 70, 110, 255), outline=INK)
                d.rectangle([13 * k * s, 0, 19 * k * s, 14 * k * s], fill=wall, outline=INK, width=s)
                d.polygon([(12 * k * s, 0), (16 * k * s, -6 * k * s), (20 * k * s, 0)], fill=(80, 60, 110, 255))
            d.rectangle([14 * k * s, 22 * k * s, 18 * k * s, 29 * k * s], fill=(40, 30, 24, 255))  # the gate
        elif kind == "hold":
            rock = (110, 104, 96, 255)
            d.polygon([(0, 30 * k * s), (10 * k * s, 4 * k * s), (16 * k * s, 9 * k * s), (22 * k * s, 2 * k * s),
                       (32 * k * s, 30 * k * s)], fill=rock, outline=INK)
            d.rectangle([11 * k * s, 16 * k * s, 21 * k * s, 30 * k * s], fill=(150, 140, 120, 255), outline=INK, width=s)
            d.pieslice([12 * k * s, 18 * k * s, 20 * k * s, 34 * k * s], 180, 360, fill=(30, 22, 18, 255))
        elif kind == "elfhall":
            for (x, y, r) in ((9, 14, 8), (22, 12, 9), (16, 7, 8)):
                d.ellipse([(x - r) * k * s, (y - r) * k * s, (x + r) * k * s, (y + r) * k * s], fill=(70, 120, 76, 255), outline=INK)
            d.rectangle([13 * k * s, 16 * k * s, 19 * k * s, 29 * k * s], fill=(200, 196, 170, 255), outline=INK, width=s)
            d.polygon([(11 * k * s, 17 * k * s), (16 * k * s, 11 * k * s), (21 * k * s, 17 * k * s)], fill=(160, 170, 120, 255), outline=INK)

    big = Image.new("RGBA", (size * sc, size * sc), (0, 0, 0, 0))
    draw(ImageDraw.Draw(big), sc)
    return big.resize((size, size), Image.LANCZOS)


def site_mark(kind: str, size: int = 32) -> Image.Image:
    sc = 4

    def draw(d, s):
        k = size / 32 * s
        if kind == "ruin":
            stone = (150, 140, 124, 255)
            for x, h in ((5, 16), (12, 22), (20, 12), (26, 18)):
                d.rectangle([x * k, (30 - h) * k, (x + 4) * k, 30 * k], fill=stone, outline=INK)
            d.line([(4 * k, 30 * k), (30 * k, 30 * k)], fill=INK, width=s)
        elif kind == "cave":
            d.polygon([(1 * k, 30 * k), (8 * k, 8 * k), (16 * k, 3 * k), (25 * k, 10 * k), (31 * k, 30 * k)],
                      fill=(112, 102, 92, 255), outline=INK)
            d.pieslice([9 * k, 15 * k, 23 * k, 40 * k], 180, 360, fill=(18, 14, 12, 255))
        elif kind == "barrow":
            d.chord([2 * k, 12 * k, 30 * k, 44 * k], 180, 360, fill=(90, 110, 70, 255), outline=INK)
            for x in (8, 14, 20):
                d.rectangle([x * k, 20 * k, (x + 3) * k, 28 * k], fill=(160, 156, 146, 255), outline=INK)
            d.rectangle([13 * k, 22 * k, 19 * k, 28 * k], fill=(20, 16, 14, 255))
        elif kind == "tower":
            d.rectangle([11 * k, 6 * k, 21 * k, 30 * k], fill=(140, 132, 120, 255), outline=INK, width=s)
            for x in (10, 14, 18):
                d.rectangle([x * k, 2 * k, (x + 3) * k, 6 * k], fill=(140, 132, 120, 255), outline=INK)
            d.rectangle([15 * k, 12 * k, 17 * k, 16 * k], fill=(30, 24, 20, 255))
            d.line([(12 * k, 22 * k), (20 * k, 24 * k)], fill=INK, width=s)  # a crack
        elif kind == "lair":
            d.polygon([(1 * k, 30 * k), (10 * k, 6 * k), (22 * k, 4 * k), (31 * k, 30 * k)], fill=(96, 84, 74, 255), outline=INK)
            d.pieslice([8 * k, 14 * k, 24 * k, 42 * k], 180, 360, fill=(14, 10, 8, 255))
            d.ellipse([12 * k, 22 * k, 14 * k, 24 * k], fill=(230, 160, 40, 255))
            d.ellipse([18 * k, 22 * k, 20 * k, 24 * k], fill=(230, 160, 40, 255))

    big = Image.new("RGBA", (size * sc, size * sc), (0, 0, 0, 0))
    draw(ImageDraw.Draw(big), sc)
    return big.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------------------- icons for the action bar
GOLD = (226, 190, 116)
GOLD_DARK = (120, 90, 48)


def icon(name: str) -> Image.Image:
    """An engraved-looking icon: light line art with a dark edge, readable at 20-40 pixels."""
    sc = 4

    def P(x, y):
        return (x * sc, y * sc)

    def draw(d: ImageDraw.ImageDraw, s):
        w = 2 * s
        g = GOLD + (255,)
        if name == "look":  # an eye
            d.chord([P(3, 9), P(29, 25)], 200, 340, outline=g, width=w)
            d.chord([P(3, 7), P(29, 23)], 20, 160, outline=g, width=w)
            d.ellipse([P(11, 10), P(21, 20)], outline=g, width=w)
            d.ellipse([P(14, 13), P(18, 17)], fill=g)
        elif name == "search":  # a magnifying glass
            d.ellipse([P(5, 4), P(20, 19)], outline=g, width=w + s)
            d.line([P(18, 18), P(27, 27)], fill=g, width=w + 2 * s)
        elif name == "wait":  # an hourglass
            d.line([P(8, 4), P(24, 4)], fill=g, width=w)
            d.line([P(8, 28), P(24, 28)], fill=g, width=w)
            d.polygon([P(10, 6), P(22, 6), P(16, 16)], outline=g, width=w)
            d.polygon([P(10, 26), P(22, 26), P(16, 16)], fill=g)
        elif name == "camp":  # a tent with a fire
            d.polygon([P(3, 26), P(14, 6), P(25, 26)], outline=g, width=w)
            d.line([P(14, 6), P(14, 26)], fill=g, width=s)
            d.polygon([P(24, 27), P(27, 18), P(30, 27)], fill=(232, 120, 50, 255))
        elif name == "water":  # a waterskin and a drop
            d.ellipse([P(6, 10), P(22, 28)], outline=g, width=w)
            d.line([P(12, 10), P(12, 5)], fill=g, width=w)
            d.line([P(10, 5), P(16, 5)], fill=g, width=w)
            d.polygon([P(25, 4), P(22, 11), P(28, 11)], fill=(120, 170, 230, 255))
            d.ellipse([P(22, 9), P(28, 15)], fill=(120, 170, 230, 255))
        elif name == "wash":  # a basin and drops
            d.chord([P(4, 10), P(28, 28)], 0, 180, outline=g, width=w)
            d.line([P(4, 19), P(28, 19)], fill=g, width=w)
            for x in (10, 16, 22):
                d.ellipse([P(x - 2, 6), P(x + 2, 11)], fill=(120, 170, 230, 255))
        elif name == "sneak":  # footprints
            for (x, y) in ((9, 22), (20, 10)):
                d.ellipse([P(x - 3, y - 6), P(x + 3, y + 4)], fill=g)
                for t in range(3):
                    d.ellipse([P(x - 3 + t * 2.5, y - 10), P(x - 1.5 + t * 2.5, y - 8)], fill=g)
        elif name == "pickup":  # a hand
            d.rounded_rectangle([P(8, 14), P(24, 28)], 3 * s, outline=g, width=w)
            for t, x in enumerate((9, 13, 17, 21)):
                d.line([P(x + 1, 15), P(x + 1, 6 + abs(t - 1.5))], fill=g, width=w)
        elif name == "enter":  # an arch with an arrow in
            d.arc([P(5, 4), P(27, 26)], 180, 360, fill=g, width=w)
            d.line([P(5, 15), P(5, 29)], fill=g, width=w)
            d.line([P(27, 15), P(27, 29)], fill=g, width=w)
            d.line([P(16, 9), P(16, 24)], fill=g, width=w)
            d.polygon([P(11, 20), P(21, 20), P(16, 27)], fill=g)
        elif name == "leave":  # an arch with an arrow out
            d.arc([P(5, 4), P(27, 26)], 180, 360, fill=g, width=w)
            d.line([P(5, 15), P(5, 29)], fill=g, width=w)
            d.line([P(27, 15), P(27, 29)], fill=g, width=w)
            d.line([P(16, 12), P(16, 27)], fill=g, width=w)
            d.polygon([P(11, 15), P(21, 15), P(16, 8)], fill=g)
        elif name == "map":  # a folded map
            d.polygon([P(3, 7), P(11, 4), P(21, 8), P(29, 5), P(29, 25), P(21, 28), P(11, 24), P(3, 27)], outline=g, width=w)
            d.line([P(11, 4), P(11, 24)], fill=g, width=s)
            d.line([P(21, 8), P(21, 28)], fill=g, width=s)
            d.line([P(6, 18), P(14, 14), P(19, 19), P(26, 12)], fill=(200, 80, 60, 255), width=s)
        elif name == "travel":  # a boot and an arrow
            d.polygon([P(6, 6), P(13, 6), P(13, 20), P(24, 22), P(25, 27), P(6, 27)], outline=g, width=w)
            d.line([P(17, 9), P(28, 9)], fill=g, width=w)
            d.polygon([P(25, 5), P(30, 9), P(25, 13)], fill=g)
        elif name == "character":  # a bust
            d.ellipse([P(11, 4), P(21, 14)], outline=g, width=w)
            d.chord([P(5, 15), P(27, 37)], 180, 360, outline=g, width=w)
        elif name == "inventory":  # a pack
            d.rounded_rectangle([P(6, 9), P(26, 29)], 4 * s, outline=g, width=w)
            d.arc([P(11, 3), P(21, 13)], 180, 360, fill=g, width=w)
            d.line([P(6, 16), P(26, 16)], fill=g, width=w)
            d.rectangle([P(14, 15), P(18, 20)], fill=g)
        elif name == "health":  # a heart
            d.ellipse([P(4, 6), P(16, 18)], fill=(200, 64, 54, 255))
            d.ellipse([P(16, 6), P(28, 18)], fill=(200, 64, 54, 255))
            d.polygon([P(5, 14), P(27, 14), P(16, 28)], fill=(200, 64, 54, 255))
            d.ellipse([P(7, 8), P(11, 12)], fill=(240, 150, 140, 255))
        elif name == "journal":  # a book and a quill
            d.rectangle([P(5, 6), P(21, 28)], outline=g, width=w)
            d.line([P(9, 6), P(9, 28)], fill=g, width=s)
            d.line([P(27, 3), P(15, 20)], fill=g, width=w)
            d.polygon([P(27, 3), P(29, 9), P(21, 12)], fill=g)
        elif name == "spells":  # a star in a circle
            d.ellipse([P(3, 3), P(29, 29)], outline=(190, 140, 240, 255), width=w)
            pts = [P(16 + 11 * math.cos(math.pi / 2 + i * 4 * math.pi / 5), 16 - 11 * math.sin(math.pi / 2 + i * 4 * math.pi / 5))
                   for i in range(5)]
            d.line(pts + [pts[0]], fill=(200, 160, 250, 255), width=w)
        elif name == "party":  # three heads
            for x, y, r in ((9, 13, 4), (23, 13, 4), (16, 10, 5)):
                d.ellipse([P(x - r, y - r), P(x + r, y + r)], outline=g, width=w)
            d.chord([P(4, 18), P(28, 40)], 180, 360, outline=g, width=w)
        elif name == "factions":  # a banner
            d.line([P(6, 3), P(6, 30)], fill=g, width=w)
            d.polygon([P(7, 5), P(27, 5), P(22, 12), P(27, 19), P(7, 19)], fill=(150, 50, 44, 255), outline=g)
        elif name == "news":  # a scroll
            d.rectangle([P(7, 6), P(25, 26)], outline=g, width=w)
            d.ellipse([P(4, 3), P(10, 9)], outline=g, width=w)
            d.ellipse([P(22, 23), P(28, 29)], outline=g, width=w)
            for y in (11, 15, 19):
                d.line([P(11, y), P(21, y)], fill=g, width=s)
        elif name == "log":  # lines of writing
            for i, y in enumerate((7, 12, 17, 22, 27)):
                d.line([P(5, y), P(27 - (i % 2) * 6, y)], fill=g, width=w)
        elif name == "legend":  # a key
            d.ellipse([P(3, 5), P(13, 15)], outline=g, width=w)
            d.line([P(12, 13), P(27, 27)], fill=g, width=w)
            d.line([P(22, 22), P(26, 18)], fill=g, width=w)
            d.line([P(25, 25), P(29, 21)], fill=g, width=w)
        elif name == "menu":  # a cog
            for k in range(8):
                a = k * math.pi / 4
                d.line([P(16 + 9 * math.cos(a), 16 + 9 * math.sin(a)), P(16 + 14 * math.cos(a), 16 + 14 * math.sin(a))],
                       fill=g, width=3 * s)
            d.ellipse([P(7, 7), P(25, 25)], outline=g, width=w + s)
            d.ellipse([P(13, 13), P(19, 19)], outline=g, width=w)
        elif name == "help":  # a question mark
            d.arc([P(9, 4), P(23, 18)], 180, 90, fill=g, width=w + s)
            d.line([P(16, 18), P(16, 23)], fill=g, width=w + s)
            d.ellipse([P(14, 26), P(18, 30)], fill=g)
        elif name == "talk":  # a speech bubble
            d.rounded_rectangle([P(3, 5), P(29, 22)], 5 * s, outline=g, width=w)
            d.polygon([P(9, 21), P(8, 29), P(15, 21)], fill=g)
        elif name == "rest":  # a moon
            d.ellipse([P(5, 4), P(27, 26)], fill=g)
            d.ellipse([P(11, 1), P(31, 22)], fill=(0, 0, 0, 0))
        elif name == "equipment":  # a shield and sword
            d.polygon([P(6, 5), P(22, 5), P(22, 16), P(14, 28), P(6, 16)], outline=g, width=w)
            d.line([P(26, 3), P(26, 25)], fill=g, width=w)
            d.line([P(22, 20), P(30, 20)], fill=g, width=w)
        elif name == "drop":  # an arrow down onto the ground
            d.line([P(16, 3), P(16, 20)], fill=g, width=w)
            d.polygon([P(10, 16), P(22, 16), P(16, 24)], fill=g)
            d.line([P(4, 28), P(28, 28)], fill=g, width=w)
        elif name == "eat":  # bread
            d.chord([P(4, 9), P(28, 31)], 180, 360, fill=(190, 140, 80, 255), outline=g, width=s)
            d.rectangle([P(4, 19), P(28, 25)], fill=(170, 120, 66, 255))
            for x in (10, 16, 22):
                d.line([P(x, 12), P(x + 2, 16)], fill=GOLD_DARK + (255,), width=s)
        elif name == "close":  # an x
            d.line([P(7, 7), P(25, 25)], fill=g, width=w + s)
            d.line([P(25, 7), P(7, 25)], fill=g, width=w + s)
        elif name == "trash":
            d.rectangle([P(8, 9), P(24, 29)], outline=(220, 90, 70, 255), width=w)
            d.line([P(5, 8), P(27, 8)], fill=(220, 90, 70, 255), width=w)
            d.rectangle([P(13, 4), P(19, 8)], outline=(220, 90, 70, 255), width=s)
            for x in (12, 16, 20):
                d.line([P(x, 12), P(x, 26)], fill=(220, 90, 70, 255), width=s)
        elif name == "zoom_in":
            d.ellipse([P(4, 4), P(22, 22)], outline=g, width=w)
            d.line([P(20, 20), P(28, 28)], fill=g, width=w + s)
            d.line([P(9, 13), P(17, 13)], fill=g, width=w)
            d.line([P(13, 9), P(13, 17)], fill=g, width=w)
        elif name == "zoom_out":
            d.ellipse([P(4, 4), P(22, 22)], outline=g, width=w)
            d.line([P(20, 20), P(28, 28)], fill=g, width=w + s)
            d.line([P(9, 13), P(17, 13)], fill=g, width=w)
        elif name == "hunger":  # a bowl
            c = (214, 160, 90, 255)
            d.chord([P(4, 8), P(28, 30)], 0, 180, fill=c, outline=g, width=s)
            d.line([P(3, 19), P(29, 19)], fill=g, width=w)
            d.line([P(20, 4), P(14, 16)], fill=(200, 200, 200, 255), width=w)
        elif name == "thirst":  # a drop
            c = (110, 170, 236, 255)
            d.polygon([P(16, 3), P(7, 18), P(25, 18)], fill=c)
            d.ellipse([P(7, 11), P(25, 29)], fill=c)
            d.ellipse([P(11, 16), P(15, 21)], fill=(210, 230, 255, 255))
        elif name == "tired":  # a closed eye and z
            d.arc([P(3, 6), P(21, 24)], 20, 160, fill=g, width=w)
            for k in range(4):
                d.line([P(5 + k * 4, 19), P(4 + k * 4, 23)], fill=g, width=s)
            d.line([P(21, 4), P(29, 4)], fill=(170, 190, 240, 255), width=w)
            d.line([P(29, 4), P(21, 12)], fill=(170, 190, 240, 255), width=w)
            d.line([P(21, 12), P(29, 12)], fill=(170, 190, 240, 255), width=w)
        elif name == "cold":  # a snowflake
            c = (170, 210, 255, 255)
            for k in range(3):
                a = k * math.pi / 3
                d.line([P(16 + 13 * math.cos(a), 16 + 13 * math.sin(a)), P(16 - 13 * math.cos(a), 16 - 13 * math.sin(a))],
                       fill=c, width=w)
            d.ellipse([P(13, 13), P(19, 19)], fill=c)
        elif name == "hot":  # a sun
            c = (250, 170, 60, 255)
            d.ellipse([P(9, 9), P(23, 23)], fill=c)
            for k in range(8):
                a = k * math.pi / 4
                d.line([P(16 + 10 * math.cos(a), 16 + 10 * math.sin(a)), P(16 + 15 * math.cos(a), 16 + 15 * math.sin(a))],
                       fill=c, width=w)
        elif name == "wet":  # drops falling
            c = (120, 160, 220, 255)
            for x, y in ((8, 6), (20, 4), (14, 16), (24, 18), (6, 22)):
                d.line([P(x, y), P(x - 2, y + 7)], fill=c, width=w)
        elif name == "dirty":  # a smudge
            for x, y, r in ((12, 14, 7), (20, 18, 6), (14, 22, 5)):
                d.ellipse([P(x - r, y - r), P(x + r, y + r)], fill=(120, 96, 70, 230))
        elif name == "bleed":  # a red drop
            c = (210, 40, 36, 255)
            d.polygon([P(16, 2), P(6, 18), P(26, 18)], fill=c)
            d.ellipse([P(6, 10), P(26, 30)], fill=c)
            d.ellipse([P(10, 15), P(14, 20)], fill=(255, 140, 130, 255))
        elif name == "pain":  # a jagged star
            c = (236, 90, 70, 255)
            pts = []
            for k in range(14):
                a = k * math.pi / 7
                r = 14 if k % 2 == 0 else 6
                pts.append(P(16 + r * math.cos(a), 16 + r * math.sin(a)))
            d.polygon(pts, fill=c)
        elif name == "sick":  # a green face, crossed eyes
            d.ellipse([P(4, 4), P(28, 28)], fill=(130, 170, 80, 255), outline=g, width=s)
            for x in (11, 21):
                d.line([P(x - 2, 11), P(x + 2, 15)], fill=(30, 40, 20, 255), width=s)
                d.line([P(x + 2, 11), P(x - 2, 15)], fill=(30, 40, 20, 255), width=s)
            d.arc([P(10, 18), P(22, 28)], 200, 340, fill=(30, 40, 20, 255), width=s)
        elif name == "drunk":  # a tankard
            d.rectangle([P(7, 8), P(21, 28)], fill=(170, 120, 60, 255), outline=g, width=s)
            d.arc([P(17, 12), P(27, 22)], 270, 90, fill=g, width=w)
            d.ellipse([P(6, 4), P(22, 11)], fill=(240, 236, 220, 255))
        elif name == "weight":  # a heavy sack
            d.ellipse([P(5, 10), P(27, 30)], fill=(150, 116, 74, 255), outline=g, width=s)
            d.polygon([P(12, 4), P(20, 4), P(18, 11), P(14, 11)], fill=(150, 116, 74, 255))
        elif name == "festering":
            d.ellipse([P(5, 5), P(27, 27)], fill=(150, 160, 60, 255))
            for x, y in ((11, 11), (20, 14), (14, 20)):
                d.ellipse([P(x - 2, y - 2), P(x + 2, y + 2)], fill=(90, 100, 30, 255))
        elif name == "sun":
            c = (250, 214, 100, 255)
            d.ellipse([P(9, 9), P(23, 23)], fill=c)
            for k in range(8):
                a = k * math.pi / 4
                d.line([P(16 + 10 * math.cos(a), 16 + 10 * math.sin(a)), P(16 + 15 * math.cos(a), 16 + 15 * math.sin(a))],
                       fill=c, width=w)
        elif name == "moon":
            d.ellipse([P(6, 5), P(26, 25)], fill=(220, 224, 236, 255))
            d.ellipse([P(12, 2), P(30, 21)], fill=(0, 0, 0, 0))
        elif name == "dusk":
            d.chord([P(5, 12), P(27, 34)], 180, 360, fill=(240, 150, 70, 255))
            d.line([P(2, 23), P(30, 23)], fill=g, width=w)
        elif name in ("cloud", "rain", "snow", "storm", "fog"):
            c = (190, 194, 204, 255) if name != "storm" else (120, 122, 136, 255)
            d.ellipse([P(4, 10), P(16, 22)], fill=c)
            d.ellipse([P(11, 5), P(25, 20)], fill=c)
            d.ellipse([P(18, 11), P(29, 22)], fill=c)
            d.rectangle([P(9, 15), P(24, 22)], fill=c)
            if name == "rain":
                for x in (10, 16, 22):
                    d.line([P(x, 24), P(x - 2, 30)], fill=(110, 160, 230, 255), width=w)
            elif name == "snow":
                for x in (10, 16, 22):
                    d.ellipse([P(x - 1.5, 25), P(x + 1.5, 28)], fill=(240, 244, 255, 255))
            elif name == "storm":
                d.polygon([P(17, 21), P(11, 30), P(16, 27), P(14, 32), P(21, 23), P(16, 25)], fill=(250, 220, 90, 255))
            elif name == "fog":
                for y in (24, 28):
                    d.line([P(4, y), P(28, y)], fill=(170, 174, 184, 220), width=w)
        elif name == "coin":
            d.ellipse([P(5, 5), P(27, 27)], fill=(220, 180, 70, 255), outline=(120, 90, 30, 255), width=w)
            d.ellipse([P(10, 10), P(22, 22)], outline=(150, 112, 40, 255), width=s)
        elif name == "place":  # a compass rose
            d.polygon([P(16, 2), P(19, 16), P(16, 30), P(13, 16)], fill=g)
            d.polygon([P(2, 16), P(16, 13), P(30, 16), P(16, 19)], fill=GOLD_DARK + (255,))
            d.ellipse([P(13, 13), P(19, 19)], fill=(200, 60, 44, 255))
        elif name == "danger":  # a skull
            d.ellipse([P(7, 4), P(25, 22)], fill=(222, 216, 200, 255))
            d.rectangle([P(11, 19), P(21, 27)], fill=(222, 216, 200, 255))
            d.ellipse([P(10, 10), P(15, 15)], fill=(30, 24, 20, 255))
            d.ellipse([P(17, 10), P(22, 15)], fill=(30, 24, 20, 255))
            for x in (13, 16, 19):
                d.line([P(x, 22), P(x, 27)], fill=(30, 24, 20, 255), width=s)
        elif name == "work":  # a sealed letter
            d.rectangle([P(4, 8), P(28, 26)], fill=(220, 206, 170, 255), outline=g, width=s)
            d.line([P(4, 8), P(16, 18), P(28, 8)], fill=GOLD_DARK + (255,), width=s)
            d.ellipse([P(13, 15), P(19, 21)], fill=(170, 40, 34, 255))
        elif name == "realm":  # a crown
            d.polygon([P(4, 24), P(4, 10), P(10, 16), P(16, 6), P(22, 16), P(28, 10), P(28, 24)], fill=g)
            d.rectangle([P(4, 24), P(28, 28)], fill=g)
        elif name == "more":  # three dots
            for x in (8, 16, 24):
                d.ellipse([P(x - 3, 13), P(x + 3, 19)], fill=g)
        elif name == "stairs_down":
            for k in range(4):
                d.rectangle([P(4 + k * 6, 6 + k * 6), P(28, 12 + k * 6)], outline=g, width=s)
            d.polygon([P(8, 20), P(14, 20), P(11, 27)], fill=g)
        elif name == "stairs_up":
            for k in range(4):
                d.rectangle([P(4, 6 + k * 6), P(28 - k * 6, 12 + k * 6)], outline=g, width=s)
            d.polygon([P(20, 12), P(26, 12), P(23, 5)], fill=g)
        elif name == "attack":  # crossed swords
            for a, b in (((5, 27), (25, 5)), ((27, 27), (7, 5))):
                d.line([P(*a), P(*b)], fill=(220, 220, 228, 255), width=w + s)
            d.line([P(6, 20), P(12, 26)], fill=g, width=w)
            d.line([P(26, 20), P(20, 26)], fill=g, width=w)
        elif name == "defend":  # a shield
            d.polygon([P(6, 4), P(26, 4), P(26, 16), P(16, 29), P(6, 16)], fill=(120, 130, 150, 255), outline=g, width=w)
            d.line([P(16, 6), P(16, 26)], fill=g, width=s)
        elif name == "flee":  # a running arrow
            d.line([P(4, 16), P(24, 16)], fill=g, width=w + s)
            d.polygon([P(20, 8), P(30, 16), P(20, 24)], fill=g)
            d.line([P(4, 9), P(14, 9)], fill=g, width=s)
            d.line([P(4, 23), P(14, 23)], fill=g, width=s)
        elif name == "cast":  # a sparkle
            c = (200, 160, 250, 255)
            d.polygon([P(16, 2), P(19, 13), P(30, 16), P(19, 19), P(16, 30), P(13, 19), P(2, 16), P(13, 13)], fill=c)
        elif name == "item":  # a potion
            d.ellipse([P(7, 12), P(25, 30)], fill=(200, 60, 60, 255), outline=g, width=s)
            d.rectangle([P(13, 4), P(19, 13)], fill=(200, 200, 210, 255), outline=g, width=s)
        elif name == "ability":  # a fist
            d.rounded_rectangle([P(8, 10), P(24, 26)], 3 * s, fill=(220, 180, 140, 255), outline=g, width=s)
            for x in (12, 16, 20):
                d.line([P(x, 10), P(x, 16)], fill=GOLD_DARK + (255,), width=s)
        elif name == "rank":  # arrows front/back
            d.polygon([P(4, 10), P(14, 4), P(14, 16)], fill=g)
            d.line([P(12, 10), P(26, 10)], fill=g, width=w)
            d.polygon([P(28, 22), P(18, 16), P(18, 28)], fill=g)
            d.line([P(6, 22), P(20, 22)], fill=g, width=w)
        elif name == "parley":  # a white flag
            d.line([P(8, 3), P(8, 30)], fill=g, width=w)
            d.polygon([P(9, 5), P(28, 7), P(24, 12), P(28, 18), P(9, 17)], fill=(236, 232, 220, 255))
        elif name == "shove":  # a hand pushing
            d.rounded_rectangle([P(10, 8), P(22, 26)], 3 * s, outline=g, width=w)
            d.line([P(22, 17), P(30, 17)], fill=g, width=w)
            d.polygon([P(27, 12), P(31, 17), P(27, 22)], fill=g)
        elif name == "surrender":  # bowed
            d.ellipse([P(11, 3), P(21, 13)], outline=g, width=w)
            d.line([P(16, 13), P(16, 24)], fill=g, width=w)
            d.line([P(6, 12), P(16, 18), P(26, 12)], fill=g, width=w)
        elif name == "trade":  # scales
            d.line([P(16, 4), P(16, 28)], fill=g, width=w)
            d.line([P(5, 9), P(27, 9)], fill=g, width=w)
            d.chord([P(2, 12), P(12, 22)], 0, 180, fill=g)
            d.chord([P(20, 12), P(30, 22)], 0, 180, fill=g)
            d.line([P(10, 28), P(22, 28)], fill=g, width=w)
        else:
            raise KeyError(name)

    big = Image.new("RGBA", (S * sc, S * sc), (0, 0, 0, 0))
    draw(ImageDraw.Draw(big), sc)
    small = big.resize((S, S), Image.LANCZOS)
    # A dark halo so the icon reads on any panel.
    a = arr(small)
    alpha = a[..., 3].astype(np.float32)
    halo = np.maximum.reduce([np.roll(alpha, s_, ax) for s_ in (-1, 1) for ax in (0, 1)] + [alpha])
    base = np.zeros_like(a)
    base[..., :3] = (14, 10, 8)
    base[..., 3] = (halo * 0.85).astype(np.uint8)
    return Image.alpha_composite(img(base), small)


ICON_NAMES = ["look", "search", "wait", "camp", "water", "wash", "sneak", "pickup", "enter", "leave", "map", "travel",
              "character", "inventory", "health", "journal", "spells", "party", "factions", "news", "log", "legend",
              "menu", "help", "talk", "rest", "equipment", "drop", "eat", "close", "trash", "zoom_in", "zoom_out",
              "hunger", "thirst", "tired", "cold", "hot", "wet", "dirty", "bleed", "pain", "sick", "drunk", "weight",
              "festering", "sun", "moon", "dusk", "cloud", "rain", "snow", "storm", "fog", "coin", "place", "danger",
              "work", "realm", "more", "stairs_down", "stairs_up", "attack", "defend", "flee", "cast", "item",
              "ability", "rank", "parley", "shove", "surrender", "trade"]


def all_drawn() -> dict[str, Image.Image]:
    """Every tile this module draws, by its name in the atlas."""
    out: dict[str, Image.Image] = {}
    for i in range(4):
        out[f"floor/planks_{i}"] = planks(100 + i)
        out[f"floor/planks_dark_{i}"] = planks(140 + i, (78, 58, 40))
        out[f"floor/snow_{i}"] = snow(200 + i)
        out[f"wall/wood_{i}"] = wood_wall(300 + i)
    for i in range(3):
        out[f"deco/tallgrass_{i}"] = tufts(400 + i, [(116, 150, 70), (96, 134, 60), (134, 160, 80)], count=12, tall=7)
        out[f"deco/heather_{i}"] = tufts(410 + i, [(140, 90, 130), (120, 80, 110), (100, 110, 70)], count=11, tall=5)
        out[f"deco/leaves_{i}"] = leaves(420 + i)
        out[f"deco/needles_{i}"] = needles(430 + i)
        out[f"deco/pebbles_{i}"] = pebbles(440 + i)
        out[f"deco/rubble_{i}"] = rubble(450 + i)
        out[f"deco/reeds_{i}"] = reeds(460 + i)
        out[f"deco/crops_{i}"] = crops(470 + i, ripe=i == 2)
        out[f"deco/garden_{i}"] = garden(480 + i)
        out[f"tree/pine_{i}"] = pine(500 + i)
        out[f"tree/pine_snow_{i}"] = pine(510 + i, snowy=True)
        out[f"feature/hearth_{i}"] = hearth(i)
        out[f"feature/campfire_{i}"] = campfire(i)
    out["deco/flowers_red"] = flowers(490, (200, 70, 60))
    out["deco/flowers_yellow"] = flowers(491, (220, 200, 80))
    out["deco/flowers_blue"] = flowers(492, (110, 130, 220))
    out["tree/pine_3"] = pine(503)
    for i in range(2):
        out[f"tree/dead_{i}"] = dead_tree(520 + i)
        out[f"feature/table_{i}"] = table(600 + i)
        out[f"feature/stall_{i}"] = stall(620 + i, [(160, 50, 44), (50, 90, 150)][i])
        out[f"feature/notice_board_{i}"] = notice_board(630 + i)
        out[f"feature/grave_{i}"] = grave(640 + i, cross=i == 1)
        out[f"wall/palisade_{i}"] = palisade(650 + i)
    for i, c in enumerate([(120, 46, 40), (50, 70, 120), (70, 100, 60)]):
        out[f"feature/bed_{i}"] = bed(660 + i, c)
    out["feature/bedroll"] = bedroll(670)
    out["feature/anvil"] = anvil(680)
    for i in range(3):
        out[f"feature/rock_{i}"] = boulder(685 + i)
    out["feature/well"] = well(690)
    out["feature/chains"] = chains(700)
    out["feature/bones"] = bones(710)
    out["feature/bridge_h"] = bridge(False, 720)
    out["feature/bridge_v"] = bridge(True, 721)
    out["overlay/captive"] = captive_chains()
    for m in range(16):
        out[f"feature/fence_{m}"] = fence(m)
    for kind in ("hamlet", "village", "town", "city", "hold", "elfhall"):
        out[f"map/{kind}"] = town_mark(kind, 64)
    for kind in ("ruin", "cave", "barrow", "tower", "lair"):
        out[f"map/{kind}"] = site_mark(kind, 48)
    for name in ICON_NAMES:
        out[f"icon/{name}"] = icon(name)
    return out
