"""The title screen's picture: night over the mountains, mist in the valleys, and one small fire on a hill.

Painted once for the window's size (Pillow, numpy); stars, mist and fire move a little on top of it.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from realmwalker.ui.gfx.scene import Image, Sprite, Text


def _ridge(w: int, base: float, amp: float, seed: int, rough: float = 1.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    xs = np.arange(w, dtype=np.float32)
    y = np.full(w, base, np.float32)
    for k in range(6):
        f = (0.6 + rng.random()) * (2 ** k) / w * 3.0
        ph = rng.random() * math.tau
        y -= amp / (1.7 ** k) * rough ** k * np.abs(np.sin(xs * f * math.pi + ph))
    return y


@lru_cache(maxsize=4)
def landscape(w: int, h: int):
    from PIL import Image as PImage, ImageFilter

    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    top = np.array([10, 12, 26], np.float32)
    mid = np.array([38, 36, 62], np.float32)
    low = np.array([120, 76, 58], np.float32)
    sky = np.where(yy < 0.55, top + (mid - top) * (yy / 0.55), mid + (low - mid) * ((yy - 0.55) / 0.45))
    img = np.broadcast_to(sky.reshape(h, 1, 3), (h, w, 3)).copy()
    # The moon and its glow.
    mx, my, mr = w * 0.78, h * 0.18, max(18, h * 0.045)
    Y, X = np.mgrid[0:h, 0:w]
    d = np.sqrt((X - mx) ** 2 + (Y - my) ** 2)
    glow = np.clip(1 - d / (mr * 7), 0, 1) ** 2 * 50
    img += glow[..., None] * np.array([0.9, 0.9, 1.0], np.float32)
    disc = d < mr
    img[disc] = np.array([226, 222, 206], np.float32)
    crater = disc & (np.sin(X * 0.13 + 1.0) * np.cos(Y * 0.11) > 0.75)
    img[crater] *= 0.95
    # Mountains, far to near: each darker and less blue, with mist laid between.
    layers = [(0.58, 0.16, (74, 70, 100), 3), (0.66, 0.13, (52, 48, 72), 5), (0.74, 0.11, (34, 32, 48), 7),
              (0.84, 0.07, (20, 18, 28), 11)]
    for i, (base, amp, color, seed) in enumerate(layers):
        ridge = _ridge(w, h * base, h * amp, seed, rough=0.8 + 0.1 * i)
        mask = Y >= ridge[None, :]
        shade = np.clip((Y - ridge[None, :]) / (h * 0.25), 0, 1)[..., None]
        col = np.array(color, np.float32) * (1 - 0.35 * shade)
        img = np.where(mask[..., None], col, img)
        mist_top = ridge[None, :] + h * 0.02
        band = np.clip(1 - np.abs(Y - mist_top - h * 0.03) / (h * 0.06), 0, 1)[..., None] * (0.22 - 0.04 * i)
        img = img * (1 - band) + np.array([150, 140, 160], np.float32) * band
    # The near hill, black against the rest.
    hill = h * 0.90 - h * 0.06 * np.exp(-((np.arange(w) - w * 0.24) / (w * 0.18)) ** 2)
    img = np.where((Y >= hill[None, :])[..., None], np.array([10, 9, 12], np.float32), img)
    rng = np.random.default_rng(1)
    img *= rng.normal(1.0, 0.02, (h, w, 1)).astype(np.float32)
    out = PImage.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").filter(ImageFilter.GaussianBlur(0.6))
    # A lone dead tree on the hill.
    from PIL import ImageDraw

    d2 = ImageDraw.Draw(out)
    tx, ty = int(w * 0.31), int(h * 0.86)

    def branch(x, y, ang, length, width):
        if length < 3:
            return
        x2, y2 = x + math.cos(ang) * length, y - math.sin(ang) * length
        d2.line([(x, y), (x2, y2)], fill=(10, 9, 12), width=max(1, int(width)))
        branch(x2, y2, ang + 0.45, length * 0.68, width * 0.7)
        branch(x2, y2, ang - 0.38, length * 0.64, width * 0.7)

    branch(tx, ty, math.pi / 2, h * 0.07, max(2, h * 0.008))
    return out.convert("RGBA")


@lru_cache(maxsize=2)
def stars(w: int, h: int) -> list[tuple[float, float, float, float]]:
    rng = np.random.default_rng(5)
    n = int(w * h / 6000)
    return [(rng.random() * w, rng.random() * h * 0.55, 0.6 + rng.random() * 1.6, rng.random() * math.tau) for _ in range(n)]


def _dot():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (16, 16), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([5, 5, 11, 11], fill=(255, 255, 255, 255))
    return im.filter(ImageFilter.GaussianBlur(1.2))


@lru_cache(maxsize=2)
def mist(w: int, h: int):
    from PIL import Image as PImage, ImageFilter

    rng = np.random.default_rng(9)
    a = np.zeros((h, w, 4), np.uint8)
    n = rng.random((max(2, h // 16), max(2, w // 16))).astype(np.float32)
    # Made three wide and cut from the middle, so its left and right edges meet without a seam as it drifts.
    tiled = np.concatenate([n, n, n], axis=1)
    big = PImage.fromarray((tiled * 255).astype(np.uint8), "L").resize((w * 3, h), PImage.BICUBIC)
    big = big.filter(ImageFilter.GaussianBlur(10)).crop((w, 0, 2 * w, h))
    v = np.asarray(big, np.float32) / 255.0
    a[..., 0], a[..., 1], a[..., 2] = 170, 164, 186
    a[..., 3] = (np.clip(v - 0.35, 0, 1) * 160).astype(np.uint8)
    return PImage.fromarray(a, "RGBA")


def _glow():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([20, 20, 108, 108], fill=(255, 255, 255, 200))
    return im.filter(ImageFilter.GaussianBlur(18))


def draw(canvas, now: float, animate: bool) -> None:
    W, H = canvas.width * canvas.cell_w, canvas.height * canvas.cell_h
    canvas.under(Image(("title_land", W, H), lambda: landscape(W, H), (0, 0, W, H), smooth=False))
    t = now if animate else 0.0
    for i, (x, y, size, ph) in enumerate(stars(W, H)):
        a = 0.55 + 0.45 * math.sin(t * (0.7 + (i % 7) * 0.13) + ph) if animate else 0.8
        s = size * 3
        canvas.under(Image("star", _dot, (x - s / 2, y - s / 2, s, s), rgba=(235, 235, 255, int(70 + 150 * a))))
    # Mist drifting along the valleys.
    mh = int(H * 0.35)
    shift = (t * 9.0) % W
    for k in (0, 1):
        canvas.under(Image(("title_mist", W, mh), lambda: mist(W, mh), (-shift + k * W, H * 0.55, W, mh),
                           rgba=(255, 255, 255, 70)))
    # A fire on the hill, and someone sitting by it.
    fx, fy = W * 0.235, H * 0.835
    fs = max(24, H * 0.04)
    flick = 0.85 + 0.15 * math.sin(t * 11) * math.sin(t * 7.3 + 1) if animate else 1.0
    g = fs * 5 * flick
    canvas.under(Image("title_glow", _glow, (fx - g / 2, fy - g / 2, g, g), rgba=(255, 150, 70, int(130 * flick))))
    frame = int(t * 8) % 3 if animate else 0
    canvas.under(Sprite(f"feature/campfire_{frame}", fx - fs / 2, fy - fs * 0.75, fs, fs))
    for k in range(6 if animate else 0):  # embers rising
        p = (t * 0.35 + k / 6.0) % 1.0
        ex = fx + math.sin(t * 2 + k * 2.1) * fs * 0.4 * p
        ey = fy - fs * 0.6 - p * fs * 3
        canvas.under(Image("star", _dot, (ex - 2, ey - 2, 4, 4), rgba=(255, 170, 80, int(255 * (1 - p)))))
    canvas.under(Sprite("doll/base/human_male", fx - fs * 1.7, fy - fs * 1.05, fs * 1.1, fs * 1.1, (60, 44, 40, 255)))
    canvas.under(Sprite("doll/cloak/brown", fx - fs * 1.7, fy - fs * 1.05, fs * 1.1, fs * 1.1, (60, 44, 40, 255)))


def logo(canvas, cx: float, y: float, size: int) -> None:
    canvas.over(Text(cx, y, "Realmwalker", "title", size, (226, 184, 104, 255), anchor="mt", shadow=True, outline=True))
