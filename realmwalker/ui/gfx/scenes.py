"""Small pictures for screens that are mostly words: the camp, the figure of a character being made."""

from __future__ import annotations

import math

import numpy as np

from realmwalker.ui.gfx import dolls, theme
from realmwalker.ui.gfx.scene import Image, Rect, Sprite, tile_batch


def _glow():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([16, 16, 112, 112], fill=(255, 255, 255, 210))
    return im.filter(ImageFilter.GaussianBlur(16))


def _tent(colour=(116, 96, 66)):
    from PIL import Image as PImage, ImageDraw

    im = PImage.new("RGBA", (96, 72), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(4, 70), (48, 6), (92, 70)], fill=colour + (255,), outline=(30, 24, 18, 255))
    d.polygon([(48, 6), (40, 70), (56, 70)], fill=(30, 22, 16, 255))
    d.line([(48, 2), (48, 10)], fill=(60, 44, 30, 255), width=3)
    return im


def _lean_to():
    from PIL import Image as PImage, ImageDraw

    im = PImage.new("RGBA", (96, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i in range(9):
        d.line([(8 + i * 9, 62), (40 + i * 7, 8)], fill=(92, 70, 46, 255), width=4)
    d.line([(36, 8), (98, 8)], fill=(70, 52, 34, 255), width=4)
    return im


def camp(canvas, game, rect, now: float) -> None:
    """The party around their camp: the ground, a fire if one is lit, a tent or shelter, everyone sitting about."""
    x, y, w, h = rect
    ambient = canvas.gfx.ambient
    light = float(game.light)
    lm = game.local
    under = lm is not None and lm.kind == "dungeon"
    k = 0.0 if under else max(0.0, min(1.0, (light - 0.2) / 0.7))
    sky = tuple(int(n + (d - n) * k) for n, d in zip((14, 16, 30), (90, 110, 130)))
    canvas.under(Rect(x, y, w, h * 0.45, (*tuple(int(c * 0.7) for c in sky), 255), bottom=(*sky, 255)))
    atlas = canvas.gfx.atlas
    ground = "floor/flagstone" if under else ("floor/snow" if game.weather.snowing else "floor/grass")
    names = atlas.family(ground)
    t = 40
    cols, rows = int(w // t) + 1, int(h * 0.6 // t) + 2
    dst, picks = [], []
    for j in range(rows):
        for i in range(cols):
            picks.append(names[(i * 5 + j * 3) % len(names)])
            dst.append((x + i * t, y + h * 0.42 + j * t, t, t))
    c = np.full((len(dst), 4), 0.35 + 0.6 * k, np.float32)
    c[:, 3] = 1
    from realmwalker.ui.gfx.scene import Clip

    canvas.under(Clip((int(x), int(y), int(w), int(h))))
    canvas.under(*tile_batch(atlas, picks, np.array(dst, np.float32), c))
    fx, fy = x + w * 0.5, y + h * 0.78
    size = min(h * 0.32, 64)
    cp = game.camp
    if cp is not None and (cp.tent or cp.shelter):
        tw = size * 2.2
        canvas.under(Image("camp_tent" if cp.tent else "camp_leanto", _tent if cp.tent else _lean_to,
                           (fx + size * 1.1, fy - tw * 0.72, tw, tw * 0.72), rgba=(*(int(120 + 135 * k),) * 3, 255)))
    fire = cp is not None and cp.fire
    if fire:
        flick = 0.85 + 0.15 * math.sin(now * 11) * math.sin(now * 7.3 + 1) if ambient else 1.0
        g = size * 4.5 * flick
        canvas.under(Image("camp_glow", _glow, (fx - g / 2, fy - g * 0.55, g, g), rgba=(255, 150, 70, int(150 * flick))))
        frame = int(now * 8) % 3 if ambient else 0
        canvas.under(Sprite(f"feature/campfire_{frame}", fx - size / 2, fy - size * 0.8, size, size))
    else:
        canvas.under(Sprite("feature/campfire_0", fx - size / 2, fy - size * 0.8, size, size, (90, 80, 80, 255)))
    lit = 0.45 + (0.55 if fire else 0.0) * (1 - k) + 0.5 * k
    tint = (int(255 * min(1, lit)), int(235 * min(1, lit)), int(215 * min(1, lit)))
    party = list(game.party)
    for i, member in enumerate(party):
        ang = math.pi * (0.85 + 0.9 * i / max(1, len(party)))
        px = fx + math.cos(ang) * size * 1.9 * (1.2 if len(party) > 2 else 1)
        py = fy + math.sin(ang) * size * 0.35 - size * 0.1
        for name in dolls.character(member, game.tables):
            canvas.under(Sprite(name, px - size / 2, py - size, size, size, (*tint, 255)))
    canvas.under(Clip(None))
    canvas.under(*theme.panel(x, y, w, h, "inset", ornaments=False, border=True)[2:])


def figure(canvas, char, tables, rect) -> None:
    """A character standing in a frame (character creation, the character sheet)."""
    x, y, w, h = rect
    canvas.under(*theme.panel(x, y, w, h, "glass", ornaments=False))
    canvas.under(Rect(x + 3, y + h * 0.7, w - 6, h * 0.3 - 3, (0, 0, 0, 70)))
    size = min(w - 12, h - 12)
    for name in dolls.character(char, tables):
        canvas.sprite(name, x + (w - size) / 2, y + h - size - 6, size, size, over=False)
