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
    under = lm is not None and lm.under_rock(game.player.lx, game.player.ly)
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
    from realmwalker.game import story

    left_rec = story.left_record(game)
    left = left_rec["what"] if left_rec else None
    low = 0.4 if left == "visitor" else 1.0  # (the fire burns low while the villain stands beyond it: E.2)
    if fire:
        flick = 0.85 + 0.15 * math.sin(now * 11) * math.sin(now * 7.3 + 1) if ambient else 1.0
        g = size * 4.5 * flick * (0.6 + 0.4 * low)
        canvas.under(Image("camp_glow", _glow, (fx - g / 2, fy - g * 0.55, g, g),
                           rgba=(255, int(150 * low + 40 * (1 - low)), int(70 * low), int(150 * flick * low))))
        frame = int(now * 8) % 3 if ambient else 0
        dim = int(255 * (0.55 + 0.45 * low))
        canvas.under(Sprite(f"feature/campfire_{frame}", fx - size / 2, fy - size * 0.8, size, size,
                            (dim, int(dim * (0.7 + 0.3 * low)), int(dim * (0.7 + 0.3 * low)), 255)))
    else:
        canvas.under(Sprite("feature/campfire_0", fx - size / 2, fy - size * 0.8, size, size, (90, 80, 80, 255)))
    if left == "visitor":
        _visitor(canvas, game, left_rec, (x, y, w, h), fx, fy, size, now)
    if left == "dead":  # (the Risen's dead, standing in a ring at the edge of the light, very still: Expansion 6 D.5)
        dw = size * 1.15
        pale = int(70 + 110 * k)
        for i, (sx, kind) in enumerate(((0.05, "creature/zombie"), (0.2, "creature/skeleton"),
                                        (0.8, "creature/wight"), (0.92, "creature/zombie"))):
            sway = math.sin(now * 0.7 + i * 1.9) * size * 0.03 if ambient else 0.0
            canvas.under(Sprite(kind, x + w * sx - dw / 2 + sway, fy - size * 0.55 - dw * 0.9, dw, dw,
                                (pale, int(pale * 1.05), min(255, int(pale * 1.2)), 200)))
    if left == "carcass":  # (the beast's "letter", laid at the camp's edge: Expansion 6)
        cw = size * 1.5
        cx, cy = x + w * 0.16, fy - size * 0.1
        dim = int(90 + 120 * k)
        canvas.under(Sprite("decal/blood_3", cx - cw * 0.6, cy - cw * 0.35, cw * 1.2, cw * 0.7, (dim, dim, dim, 230)))
        canvas.under(Sprite("creature/elk", cx - cw / 2, cy - cw * 0.75, cw, cw, (dim, int(dim * 0.9), int(dim * 0.9),
                                                                                   255), angle=90.0))
    lit = 0.45 + (0.55 if fire else 0.0) * (1 - k) + 0.5 * k
    fs = 64 if size >= 48 else 32
    tint = (int(255 * min(1, lit)), int(235 * min(1, lit)), int(215 * min(1, lit)))
    party = list(game.party)
    for i, member in enumerate(party):
        ang = math.pi * (0.85 + 0.9 * i / max(1, len(party)))
        px = fx + math.cos(ang) * size * 1.9 * (1.2 if len(party) > 2 else 1)
        py = fy + math.sin(ang) * size * 0.35 - size * 0.1
        cmd = dolls.draw(atlas, dolls.character(member, game.tables, atlas=atlas), px - fs / 2, py - fs, fs,
                         tuple(c / 255 for c in tint))
        if cmd is not None:
            canvas.under(cmd)
    canvas.under(Clip(None))
    canvas.under(*theme.panel(x, y, w, h, "inset", ornaments=False, border=True)[2:])


def _visitor(canvas, game, rec: dict, rect, fx: float, fy: float, size: float, now: float) -> None:
    """The villain come to talk (Expansion 6 E.2): a figure at the edge of the light, a pace beyond the fire, dark
    against the dark with only its edges lit, and a breath of mist at its feet."""
    from realmwalker.game import story
    from realmwalker.world import threats

    x, y, w, h = rect
    adv = story.adventures(game.world).get(rec.get("adv") or "")
    t = threats.records(game.world).get(adv["threat"]) if adv else None
    if t is None:
        return
    atlas = canvas.gfx.atlas
    parts = dolls.creature(t["villain"]["creature"], game.tables, f"villain/{t['id']}", atlas=atlas)
    vs = 64 if size >= 48 else 32
    cid = t["villain"]["creature"]
    cdef = game.tables.creatures[cid] if cid in game.tables.creatures else {}
    vs *= 2 if str(cdef.get("size", "")).lower() in ("large", "huge", "gargantuan") else 1
    sway = math.sin(now * 0.6) * size * 0.02 if canvas.gfx.ambient else 0.0
    vx, vy = x + w * 0.2 + sway, fy - size * 0.25
    canvas.under(Image("camp_glow", _glow, (vx - vs * 0.2, vy - vs * 0.25, vs * 1.4, vs * 0.6),
                       rgba=(190, 200, 220, 60)))  # (mist where it stands)
    cmd = dolls.draw(atlas, parts, vx, vy - vs, vs, (0.32, 0.3, 0.38), alpha=0.92)
    if cmd is not None:
        canvas.under(cmd)


def figure(canvas, char, tables, rect, most: int = 224) -> tuple[float, float, int] | None:
    """A character standing in a frame (character creation, the character sheet, the health screen), at most `most`
    pixels tall. Returns where the figure went (x, y, size in pixels), so marks can be put on it."""
    x, y, w, h = rect
    size = max(32, min(int(min(w - 12, h - 12)), most) // 32 * 32)
    w = min(w, size + 40)
    h = min(h, size + 20)
    canvas.under(*theme.panel(x, y, w, h, "glass", ornaments=False))
    canvas.under(Rect(x + 3, y + h * 0.7, w - 6, h * 0.3 - 3, (0, 0, 0, 70)))
    fx, fy = int(x + (w - size) / 2), int(y + h - size - 6)
    cmd = dolls.draw(canvas.gfx.atlas, dolls.character(char, tables, atlas=canvas.gfx.atlas), fx, fy, size)
    if cmd is not None:
        canvas.under(cmd)
        return fx, fy, size
    return None


def bust(canvas, parts, rect, light=(1.0, 1.0, 1.0), panel: bool = True, side: int = 20) -> None:
    """Head and shoulders in a small frame, each pixel a whole number of screen pixels (lists of people)."""
    x, y, w, h = rect
    atlas = canvas.gfx.atlas
    if panel:
        canvas.under(*theme.panel(x, y, w, h, "inset", ornaments=False))
    crop = dolls.bust(atlas, parts, side)
    k = max(1, int(min(w - 4, h - 4)) // crop[2])
    size = crop[2] * k
    cmd = dolls.draw(atlas, parts, int(x + (w - size) / 2), int(y + (h - size) / 2), size, light, crop=crop)
    if cmd is not None:
        canvas.under(cmd)


# Where each part of the body is on a figure, as fractions of its picture (the tiles' "figures" record gives each
# body's own; these are a fallback). The figure faces you: its right arm is on your left.
PARTS = {"head": (0.5, 0.2), "torso": (0.5, 0.45), "right_arm": (0.25, 0.5), "left_arm": (0.75, 0.5),
         "right_leg": (0.42, 0.82), "left_leg": (0.58, 0.82)}


def wound_marks(canvas, char, at: tuple[float, float, int], now: float, selected=None, animate: bool = True):
    """Marks on a figure where it is hurt: red where it bleeds (pulsing), a white strip where it is bandaged, a
    sickly ring where it festers, larger the worse it is. Returns [(wound index, x, y, r)] for clicking."""
    import math

    x, y, size = at
    atlas = canvas.gfx.atlas
    body = dolls.body_key(char.race, char.sex)
    parts = atlas.figures.get("parts", {}).get(body, {})
    out = []
    count: dict[str, int] = {}
    for i, wd in enumerate(char.wounds):
        fx, fy = parts.get(wd.part, PARTS.get(wd.part, (0.5, 0.5)))
        if parts:  # body pixels to fractions
            fx, fy = (fx + 0.5) / atlas.tile, (fy + 0.5) / atlas.tile
        n = count.get(wd.part, 0)
        count[wd.part] = n + 1
        px = x + fx * size + (n % 2) * size * 0.05 - (n // 2) * size * 0.04
        py = y + fy * size + n * size * 0.035
        r = size * (0.035 + 0.02 * wd.severity)
        if wd.bleed and not wd.bandaged:
            pulse = 0.65 + 0.35 * math.sin(now * 5 + i) if animate else 1.0
            colour = (220, 30, 24, int(230 * pulse))
        elif wd.infected or wd.infection > 30:
            colour = (170, 190, 60, 220)
        elif wd.bandaged:
            colour = (236, 230, 214, 230)
        else:
            colour = (150, 40, 34, 220)
        canvas.over(Image("wound", _wound_dot, (px - r, py - r, 2 * r, 2 * r), rgba=colour))
        if wd.bandaged:
            canvas.over(Rect(px - r, py - r * 0.25, 2 * r, r * 0.5, (240, 236, 224, 230)))
        if selected is not None and i == selected:
            canvas.over(Rect(px - r - 3, py - r - 3, 2 * r + 6, 2 * r + 6, (255, 214, 110, 230), line=2))
        out.append((i, px, py, r))
    return out


def _wound_dot():
    from PIL import Image as PImage, ImageDraw

    im = PImage.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([3, 3, 28, 28], fill=(255, 255, 255, 255), outline=(40, 20, 20, 255), width=3)
    return im
