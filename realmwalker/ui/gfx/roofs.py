"""Roofs over the buildings of a town, seen from the street: thatch, slate, red tile, shingle, turf.

While you stand outside a building you see its roof (and the sign over its door: a mug for an inn, an anvil for a
smithy); step inside and the roof is lifted so you see the room. Pictures are painted once per size and kept.
"""

from __future__ import annotations

import zlib
from functools import lru_cache

import numpy as np

STYLES = {
    "thatch": ((168, 136, 78), (128, 100, 56), (196, 166, 104)),
    "slate": ((88, 96, 108), (64, 70, 82), (122, 130, 140)),
    "tile": ((150, 70, 52), (112, 50, 40), (184, 98, 72)),
    "shingle": ((112, 84, 58), (84, 62, 44), (140, 108, 76)),
    "turf": ((82, 104, 62), (62, 80, 48), (110, 134, 82)),
    "stone": ((120, 116, 108), (92, 88, 82), (150, 146, 138)),
}

SIGNS = {"inn": "item/ale", "temple": "item/holy_symbol", "smithy": "feature/anvil", "store": "item/_coins_1",
         "healer": "item/potion_healing", "stable": "creature/horse", "hall": "wall/banner", "keep": "wall/banner"}


def style_for(settlement_kind: str, building_kind: str, key: str) -> str:
    h = zlib.crc32(key.encode()) % 100
    if settlement_kind == "hold":
        return "stone"
    if settlement_kind == "elfhall":
        return "turf"
    if building_kind in ("temple", "hall", "keep"):
        return "slate"
    if settlement_kind in ("hamlet", "village"):
        return "thatch" if building_kind == "house" or h < 50 else "shingle"
    return "tile" if h < 55 else ("slate" if h < 80 else "shingle")


@lru_cache(maxsize=256)
def roof(w_px: int, h_px: int, style: str, seed: int, chimney: bool):
    """A roof picture of exactly w_px x h_px (a gable along the longer side)."""
    from PIL import Image, ImageDraw, ImageFilter

    base, dark, light = STYLES.get(style, STYLES["thatch"])
    rng = np.random.default_rng(seed)
    w, h = max(8, w_px), max(8, h_px)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    horizontal = w >= h
    inset = 2
    d.rectangle([inset, inset, w - 1 - inset, h - 1 - inset], fill=base + (255,))
    # The two slopes: the far one in light, the near one in shade.
    if horizontal:
        mid = h // 2
        d.rectangle([inset, inset, w - 1 - inset, mid], fill=light + (255,))
        d.rectangle([inset, mid, w - 1 - inset, h - 1 - inset], fill=dark + (255,))
    else:
        mid = w // 2
        d.rectangle([inset, inset, mid, h - 1 - inset], fill=light + (255,))
        d.rectangle([mid, inset, w - 1 - inset, h - 1 - inset], fill=dark + (255,))
    a = np.asarray(im, np.float32).copy()
    yy, xx = np.mgrid[0:h, 0:w]
    if style == "thatch":
        streak = rng.uniform(0.82, 1.12, w if horizontal else h)
        n = streak[xx] if horizontal else streak[yy]
        a[..., :3] *= (n * (0.94 + 0.06 * np.sin((yy if horizontal else xx) * 0.9)))[..., None]
    else:
        row = 6 if style in ("tile", "slate", "stone") else 5
        along = yy if horizontal else xx
        across = xx if horizontal else yy
        course = (along // row)
        groove = (along % row) == 0
        seam = ((across + (course % 2) * (row // 2 + 2)) % (row * 2)) == 0
        a[groove, :3] *= 0.66
        a[seam & ~groove, :3] *= 0.80
        a[..., :3] *= rng.uniform(0.93, 1.07, (h, w))[..., None]
        if style == "tile":
            a[..., :3] *= (0.92 + 0.08 * np.cos((across % row) / row * np.pi * 2))[..., None]
    alpha = a[..., 3] > 0
    a[~alpha] = 0
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(im)
    # Ridge, eaves and an outline.
    if horizontal:
        d.line([(inset + 2, h // 2), (w - 3 - inset, h // 2)], fill=tuple(int(c * 1.25) for c in light) + (255,), width=2)
    else:
        d.line([(w // 2, inset + 2), (w // 2, h - 3 - inset)], fill=tuple(int(c * 1.25) for c in light) + (255,), width=2)
    d.rectangle([inset, inset, w - 1 - inset, h - 1 - inset], outline=(26, 20, 16, 255), width=2)
    if chimney:
        cxf, cyf = chimney_spot(w, h, seed)
        cx, cy = int(cxf), int(cyf)
        s = max(6, min(w, h) // 6)
        d.rectangle([cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2], fill=(108, 70, 56, 255), outline=(26, 20, 16, 255))
        d.rectangle([cx - s // 2 + 2, cy - s // 2 + 2, cx + s // 2 - 2, cy + s // 2 - 2], fill=(30, 22, 18, 255))
    # A soft shadow under the eaves.
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([inset + 2, inset + 4, w - 1, h - 1], fill=(0, 0, 0, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(2))
    out = Image.alpha_composite(sh, im)
    return out


def chimney_spot(w_px: int, h_px: int, seed: int) -> tuple[float, float]:
    """Where the chimney stands on a roof (fractions of the roof, so it is the same at every zoom)."""
    t = (zlib.crc32(f"chimney{seed}".encode()) % 1000) / 1000.0
    if w_px >= h_px:
        return w_px * (0.25 + 0.5 * t), h_px * 0.30
    return w_px * 0.62, h_px * (0.25 + 0.5 * t)


def smoke_puff():
    from PIL import Image, ImageDraw, ImageFilter

    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([6, 6, 26, 26], fill=(200, 200, 205, 200))
    return im.filter(ImageFilter.GaussianBlur(4))
