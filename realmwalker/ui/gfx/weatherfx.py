"""Weather you can see over the map: rain slanting with the wind, snow drifting down, fog, and now and then lightning
in a storm. Drawn as textures that scroll (cheap, and the same however much of the map is on screen); nothing here
changes the game. Only with animations on, and never underground or indoors.
"""

from __future__ import annotations

import math
import zlib
from functools import lru_cache

import numpy as np

from realmwalker.ui.gfx.scene import Image, Rect

TEX = 256


@lru_cache(maxsize=16)
def _rain(slant: int, density: int):
    """Streaks of rain, slanted by `slant` tenths of a pixel across per pixel down."""
    a = np.zeros((TEX, TEX, 4), np.uint8)
    rng = np.random.default_rng(1000 + slant * 10 + density)
    n = 40 + density * 30
    for _ in range(n):
        x, y = rng.integers(0, TEX, 2)
        length = int(rng.integers(8, 16))
        for i in range(length):
            px = int(x + i * slant / 10.0) % TEX
            py = int(y + i) % TEX
            a[py, px] = (200, 214, 230, int(60 + 120 * i / length))
    return a


@lru_cache(maxsize=4)
def _snow(density: int):
    a = np.zeros((TEX, TEX, 4), np.uint8)
    rng = np.random.default_rng(2000 + density)
    for _ in range(50 + density * 40):
        x, y = rng.integers(0, TEX - 2, 2)
        big = rng.random() < 0.35
        a[y:y + (2 if big else 1), x:x + (2 if big else 1)] = (244, 246, 252, 230 if big else 170)
    return a


@lru_cache(maxsize=2)
def _fog():
    from PIL import Image as PImage, ImageFilter

    rng = np.random.default_rng(3000)
    small = (rng.random((16, 16)) * 255).astype(np.uint8)
    im = PImage.fromarray(small, "L").resize((TEX, TEX), PImage.BICUBIC).filter(ImageFilter.GaussianBlur(10))
    a = np.zeros((TEX, TEX, 4), np.uint8)
    a[..., :3] = (196, 200, 206)
    a[..., 3] = np.asarray(im)
    return a


def _tiles(canvas, key, make, rect, ox: float, oy: float, rgba, scale: float = 1.0) -> None:
    """A texture repeated over rect, shifted by (ox, oy) pixels."""
    x0, y0, w, h = rect
    size = TEX * scale
    sx = x0 - (ox % size)
    sy = y0 - (oy % size)
    y = sy
    while y < y0 + h:
        x = sx
        while x < x0 + w:
            canvas.under(Image(key, make, (x, y, size, size), rgba=rgba, smooth=False))
            x += size
        y += size


def draw(canvas, rect, weather, now: float, light: float = 1.0) -> None:
    """The weather over the map in rect (pixels). `light` dims it at night."""
    if weather is None:
        return
    lv = max(0.35, min(1.0, light))
    shade = tuple(int(255 * lv) for _ in range(3))
    kind = weather.kind
    p = max(0.0, min(1.0, weather.precip))
    wind = max(0.0, weather.wind)
    if weather.raining or kind == "storm":
        slant = int(min(6, wind / 8))
        density = 1 + int(p * 4)
        speed = 520 + 380 * p
        for layer, (k, a, sc) in enumerate(((1.0, 70 + 120 * p, 1.0), (0.62, 40 + 70 * p, 0.75))):
            v = speed * k
            _tiles(canvas, ("rain", slant, density), lambda s=slant, d=density: _rain(s, d), rect,
                   -now * v * slant / 10.0 * sc, -now * v, (*shade, int(a)), sc)
        if kind == "storm":
            beat = int(now / 6.0)
            if zlib.crc32(f"bolt{beat}".encode()) % 3 == 0:
                t = now - beat * 6.0 - (zlib.crc32(f"at{beat}".encode()) % 400) / 100.0
                if 0 <= t < 0.18:
                    canvas.under(Rect(*rect, (230, 236, 255, int(110 * (1 - t / 0.18)))))
    elif weather.snowing:
        density = 1 + int(p * 4)
        speed = 26 + 30 * p + wind * 0.4
        for k, a, sc in ((1.0, 220, 1.0), (0.6, 150, 0.7)):
            sway = math.sin(now * 0.8 * k) * 18 + now * wind * 0.5 * k
            _tiles(canvas, ("snow", density), lambda d=density: _snow(d), rect, -sway, -now * speed * k,
                   (*shade, int(a)), sc)
    if kind == "fog" or weather.visibility < 0.6:
        a = int(min(200, (1.0 - weather.visibility) * 220))
        _tiles(canvas, "fog", _fog, rect, -now * 6, -now * 2, (*shade, a), 3.0)
