"""Atmospheres over a close-up map (Expansion 6 B.7, docs/ADVENTURES.md §8.14): embers rising over a burning town, ash
falling on a burned one, a dark haze over a sacked or plague-struck place, mist, a red sky. One at a time, chosen by
the map's fire and marks (or `lm.meta["atmosphere"]`, which a story may set); drawn as tiled textures shifted by time
on weatherfx's method, clipped to the map. Still with Animations on "calm", none with "off". Nothing here changes the
game.

    choose(game, lm)                      the atmosphere this map has now (None: none)
    draw(canvas, rect, game, now, light)  draw it over rect (pixels)
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from realmwalker.ui.gfx.scene import Rect
from realmwalker.ui.gfx.weatherfx import TEX, _tiles

KINDS = ("embers", "ash", "haze", "mist", "red_sky")
BY_MARK = (("burning", "embers"), ("burned", "ash"), ("sacked", "haze"), ("plague", "haze"))


def choose(game, lm) -> str | None:
    meta = lm.meta or {}
    if meta.get("atmosphere") in KINDS:
        return meta["atmosphere"]
    fire = meta.get("fire")
    if fire:
        return "red_sky" if len(fire) > 120 else "embers"
    if lm.kind != "settlement":
        return None
    s = game.world.settlement_at(game.player.x, game.player.y)
    if s is None:
        return None
    for mark, kind in BY_MARK:
        if mark in s.status:
            return kind
    return None


@lru_cache(maxsize=2)
def _specks(kind: str):
    """Bright specks (embers) or grey flakes (ash) scattered over a texture."""
    a = np.zeros((TEX, TEX, 4), np.uint8)
    rng = np.random.default_rng(4000 if kind == "embers" else 4100)
    for _ in range(70 if kind == "embers" else 110):
        x, y = rng.integers(0, TEX - 2, 2)
        if kind == "embers":
            hot = rng.random() < 0.3
            a[y:y + 2, x:x + 1] = (255, 200, 90, 240) if hot else (240, 110, 40, 200)
        else:
            big = rng.random() < 0.3
            a[y:y + (2 if big else 1), x:x + 2] = (150, 146, 140, 200 if big else 150)
    return a


@lru_cache(maxsize=2)
def _haze(tint: tuple):
    from PIL import Image as PImage, ImageFilter

    rng = np.random.default_rng(4200 + sum(tint))
    small = (rng.random((12, 12)) * 255).astype(np.uint8)
    im = PImage.fromarray(small, "L").resize((TEX, TEX), PImage.BICUBIC).filter(ImageFilter.GaussianBlur(12))
    a = np.zeros((TEX, TEX, 4), np.uint8)
    a[..., :3] = tint
    a[..., 3] = np.asarray(im)
    return a


def draw(canvas, rect, game, now: float, light: float = 1.0, *, moving: bool = True) -> None:
    lm = game.local
    if lm is None:
        return
    kind = choose(game, lm)
    if kind is None:
        return
    t = now if moving else 0.0
    lv = max(0.4, min(1.0, light))
    shade = tuple(int(255 * lv) for _ in range(3))
    if kind == "embers":
        _tiles(canvas, ("atmo", "embers"), lambda: _specks("embers"), rect, -t * 9, t * 34, (255, 255, 255, 210))
        _tiles(canvas, ("atmo", "smoke"), lambda: _haze((60, 52, 48)), rect, -t * 5, t * 3, (*shade, 90), 3.0)
    elif kind == "ash":
        _tiles(canvas, ("atmo", "ash"), lambda: _specks("ash"), rect, -t * 6, -t * 14, (*shade, 190))
    elif kind == "haze":
        _tiles(canvas, ("atmo", "haze"), lambda: _haze((44, 40, 38)), rect, -t * 3, -t * 1, (*shade, 120), 3.0)
    elif kind == "mist":
        _tiles(canvas, ("atmo", "mist"), lambda: _haze((206, 210, 214)), rect, -t * 4, -t * 1, (*shade, 110), 3.0)
    elif kind == "red_sky":
        canvas.under(Rect(*rect, (150, 40, 20, 46)))
        _tiles(canvas, ("atmo", "embers"), lambda: _specks("embers"), rect, -t * 12, t * 40, (255, 255, 255, 230))
        _tiles(canvas, ("atmo", "smoke"), lambda: _haze((60, 52, 48)), rect, -t * 6, t * 3, (*shade, 110), 3.0)
