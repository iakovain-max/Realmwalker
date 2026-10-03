"""The look of the interface: panels, buttons, key badges, highlights, bars and rules, drawn as pictures under the
text cells. Everything here returns picture commands (scene.py) and is made by code, once per size.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from realmwalker.ui.gfx.scene import Image, Lines, Rect, Text

PANEL_TOP = (31, 27, 32)
PANEL_BOTTOM = (17, 15, 19)
EDGE_DARK = (6, 5, 7)
BRONZE = (126, 98, 60)
GOLD = (214, 176, 108)
STYLES = {
    "panel": {"top": PANEL_TOP, "bottom": PANEL_BOTTOM, "edge": BRONZE, "alpha": 248},
    "inset": {"top": (14, 13, 16), "bottom": (20, 18, 22), "edge": (62, 52, 40), "alpha": 235},
    "danger": {"top": (40, 20, 20), "bottom": (20, 12, 13), "edge": (170, 64, 50), "alpha": 250},
    "log": {"top": (16, 14, 17), "bottom": (12, 11, 13), "edge": (70, 58, 44), "alpha": 238},
    "glass": {"top": (12, 11, 14), "bottom": (8, 8, 10), "edge": (90, 74, 52), "alpha": 205},
    "magic": {"top": (28, 22, 40), "bottom": (16, 12, 24), "edge": (140, 104, 190), "alpha": 248},
}


# ---------------------------------------------------------------------------- pictures
@lru_cache(maxsize=8)
def grain():
    """Fine noise laid over panels so they read as a surface, not a flat colour."""
    rng = np.random.default_rng(7)
    n = rng.normal(0, 1, (256, 256)).astype(np.float32)
    n = (n + np.roll(n, 1, 0) + np.roll(n, 1, 1)) / 3
    a = np.zeros((256, 256, 4), np.uint8)
    v = np.clip(128 + n * 60, 0, 255).astype(np.uint8)
    a[..., 0] = v
    a[..., 1] = v
    a[..., 2] = v
    a[..., 3] = 255
    return a


@lru_cache(maxsize=16)
def corner(size: int, flip_x: bool, flip_y: bool, color: tuple):
    """A small filigree for a panel's corner."""
    from PIL import Image as PImage, ImageDraw

    sc = 4
    S = size * sc
    im = PImage.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = tuple(color) + (255,)
    w = max(1, sc)
    d.line([(0, w), (S * 0.85, w)], fill=c, width=w)
    d.line([(w, 0), (w, S * 0.85)], fill=c, width=w)
    d.arc([S * 0.12, S * 0.12, S * 0.62, S * 0.62], 180, 270, fill=c, width=w)
    d.ellipse([S * 0.22 - 2 * w, S * 0.22 - 2 * w, S * 0.22 + 2 * w, S * 0.22 + 2 * w], fill=c)
    im = im.resize((size, size), PImage.LANCZOS)
    if flip_x:
        im = im.transpose(PImage.FLIP_LEFT_RIGHT)
    if flip_y:
        im = im.transpose(PImage.FLIP_TOP_BOTTOM)
    return im


@lru_cache(maxsize=256)
def button_image(w: int, h: int, state: str):
    """A button: rounded, lit from above. state: normal, hover, pressed, off, active."""
    from PIL import Image as PImage, ImageDraw

    sc = 3
    W, H = max(4, w) * sc, max(4, h) * sc
    top, bottom, edge = {
        "normal": ((70, 56, 42), (40, 32, 26), (118, 92, 58)),
        "hover": ((104, 82, 54), (60, 46, 32), (226, 186, 112)),
        "pressed": ((40, 32, 26), (64, 50, 36), (196, 160, 100)),
        "off": ((40, 38, 40), (28, 27, 30), (64, 60, 60)),
        "active": ((92, 70, 38), (56, 42, 24), (240, 200, 120)),
        "danger": ((92, 40, 34), (52, 22, 20), (200, 90, 70)),
    }.get(state, ((70, 56, 42), (40, 32, 26), (118, 92, 58)))
    grad = PImage.new("RGBA", (1, H))
    for y in range(H):
        t = y / max(1, H - 1)
        grad.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,))
    grad = grad.resize((W, H))
    mask = PImage.new("L", (W, H), 0)
    r = min(H // 2 - 1, 4 * sc)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], r, fill=255)
    im = PImage.new("RGBA", (W, H), (0, 0, 0, 0))
    im.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W - 1, H - 1], r, outline=EDGE_DARK + (255,), width=sc)
    d.rounded_rectangle([sc, sc, W - 1 - sc, H - 1 - sc], max(1, r - sc), outline=edge + (255,), width=max(1, sc // 2 + 1))
    if state != "pressed":
        d.line([(r, 2 * sc), (W - r, 2 * sc)], fill=tuple(min(255, c + 40) for c in top) + (160,), width=sc // 2 + 1)
    return im.resize((max(4, w), max(4, h)), PImage.LANCZOS)


@lru_cache(maxsize=64)
def keycap(w: int, h: int, hover: bool):
    from PIL import Image as PImage, ImageDraw

    sc = 3
    W, H = max(4, w) * sc, max(4, h) * sc
    im = PImage.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fill = (36, 30, 26, 255) if not hover else (50, 40, 28, 255)
    d.rounded_rectangle([0, 0, W - 1, H - 1], 3 * sc, fill=fill, outline=(150, 120, 74, 255) if hover else (98, 80, 56, 255),
                        width=sc)
    d.line([(3 * sc, H - 2 * sc), (W - 3 * sc, H - 2 * sc)], fill=(10, 8, 6, 200), width=sc)
    return im.resize((max(4, w), max(4, h)), PImage.LANCZOS)


@lru_cache(maxsize=64)
def highlight(w: int, h: int, kind: str):
    """A row picked out: a warm wash with a bright left edge (selected), or a faint one (hover)."""
    from PIL import Image as PImage

    a = np.zeros((max(1, h), max(1, w), 4), np.uint8)
    if kind == "select":
        xs = np.linspace(1.0, 0.35, a.shape[1])
        a[..., 0], a[..., 1], a[..., 2] = 150, 112, 52
        a[..., 3] = (xs * 120).astype(np.uint8)[None, :]
        a[:, :2, :3] = (238, 196, 120)
        a[:, :2, 3] = 255
        a[0, :, 3] = np.maximum(a[0, :, 3], (xs * 90).astype(np.uint8))
        a[-1, :, 3] = np.maximum(a[-1, :, 3], (xs * 90).astype(np.uint8))
    else:
        a[..., 0], a[..., 1], a[..., 2] = 200, 170, 120
        a[..., 3] = 34
    return PImage.fromarray(a, "RGBA")


@lru_cache(maxsize=128)
def bar_image(w: int, h: int, color: tuple):
    """The filled part of a bar, lit from above."""
    from PIL import Image as PImage

    a = np.zeros((max(1, h), max(1, w), 4), np.uint8)
    ys = np.linspace(1.25, 0.7, a.shape[0])[:, None]
    for k in range(3):
        a[..., k] = np.clip(color[k] * ys, 0, 255).astype(np.uint8)
    a[..., 3] = 255
    if a.shape[0] > 3:
        a[1, :, :3] = np.clip(np.array(color) * 1.5, 0, 255).astype(np.uint8)
    return PImage.fromarray(a, "RGBA")


# ---------------------------------------------------------------------------- commands
def panel(x: float, y: float, w: float, h: float, style: str = "panel", *, title: str = "", title_size: int = 18,
          border: bool = True, ornaments: bool = True) -> list:
    st = STYLES.get(style, STYLES["panel"])
    a = st["alpha"]
    out: list = [Rect(x, y, w, h, (*st["top"], a), bottom=(*st["bottom"], a))]
    out.append(Image("grain", grain, (x, y, w, h), rgba=(255, 255, 255, 10)))
    if border:
        out.append(Rect(x, y, w, h, (*EDGE_DARK, 255), line=1))
        out.append(Rect(x + 1, y + 1, w - 2, h - 2, (*st["edge"], 255), line=1))
        out.append(Rect(x + 2, y + 2, w - 4, h - 4, (*EDGE_DARK, 180), line=1))
        if ornaments and w > 60 and h > 40:
            s = 14
            col = tuple(min(255, int(c * 1.35)) for c in st["edge"])
            for fx, fy, cx, cy in ((False, False, x + 2, y + 2), (True, False, x + w - 2 - s, y + 2),
                                   (False, True, x + 2, y + h - 2 - s), (True, True, x + w - 2 - s, y + h - 2 - s)):
                out.append(Image(("corner", s, fx, fy, col), lambda s=s, fx=fx, fy=fy, col=col: corner(s, fx, fy, col),
                                 (cx, cy, s, s)))
    if title:
        out.extend(title_plate(x, y, w, title, title_size, st))
    return out


def title_plate(x: float, y: float, w: float, title: str, size: int, st: dict | None = None) -> list:
    """A heading set into the top edge of a panel."""
    from realmwalker.ui.gfx import typefaces

    st = st or STYLES["panel"]
    tw, th = typefaces.measure(title, "heading", size)
    pw = min(w - 24, tw + 34)
    px = x + 14
    ph = th + 10
    py = y - ph / 2 + 2 if y > ph / 2 else y + 3
    out = [Rect(px, py, pw, ph, (*st["bottom"], 255), bottom=(*st["top"], 255)),
           Rect(px, py, pw, ph, (*EDGE_DARK, 255), line=1),
           Rect(px + 1, py + 1, pw - 2, ph - 2, (*st["edge"], 255), line=1),
           Text(px + pw / 2, py + ph / 2 + 1, title, "heading", size, (*GOLD, 255), anchor="mm", shadow=True)]
    return out


def heading(x: float, y: float, w: float, text: str, size: int = 16, rgba=(*GOLD, 255)) -> list:
    """A section heading: the words, then a rule fading out to the right."""
    from realmwalker.ui.gfx import typefaces

    tw, th = typefaces.measure(text, "heading", size)
    out = [Text(x, y, text, "heading", size, rgba, anchor="lm", shadow=True)]
    rx = x + tw + 10
    if rx < x + w - 10:
        out.extend(rule(rx, y + 1, x + w - rx))
    return out


def rule(x: float, y: float, w: float) -> list:
    return [Image("rule", _rule_image, (x, y - 1, w, 3))]


def _rule_image():
    a = np.zeros((3, 256, 4), np.uint8)
    xs = np.linspace(1.0, 0.0, 256)
    a[1, :, :3] = BRONZE
    a[1, :, 3] = (xs * 220).astype(np.uint8)
    a[0, :, :3] = EDGE_DARK
    a[0, :, 3] = (xs * 120).astype(np.uint8)
    a[2, :, :3] = EDGE_DARK
    a[2, :, 3] = (xs * 120).astype(np.uint8)
    return a


def button(x: float, y: float, w: float, h: float, state: str) -> Image:
    w, h = int(round(w)), int(round(h))
    return Image(("btn", w, h, state), lambda: button_image(w, h, state), (x, y, w, h), smooth=False)


def badge(x: float, y: float, w: float, h: float, hover: bool = False) -> Image:
    w, h = int(round(w)), int(round(h))
    return Image(("key", w, h, hover), lambda: keycap(w, h, hover), (x, y, w, h), smooth=False)


def row_highlight(x: float, y: float, w: float, h: float, kind: str = "select") -> Image:
    w, h = int(round(w)), int(round(h))
    return Image(("hl", w, h, kind), lambda: highlight(w, h, kind), (x, y, w, h), smooth=False)


def bar(x: float, y: float, w: float, h: float, ratio: float, color, *, lag: float | None = None,
        track=(22, 19, 20)) -> list:
    """A bar: a dark track, the filled part, and (when something was just lost) a pale part fading after it."""
    ratio = max(0.0, min(1.0, ratio))
    out = [Rect(x, y, w, h, (*EDGE_DARK, 255)), Rect(x + 1, y + 1, w - 2, h - 2, (*track, 255))]
    inner_w = w - 2
    if lag is not None and lag > ratio:
        out.append(Rect(x + 1 + inner_w * ratio, y + 1, inner_w * (min(1.0, lag) - ratio), h - 2, (230, 210, 170, 200)))
    fw = int(round(inner_w * ratio))
    if fw > 0:
        c = tuple(int(v) for v in color[:3])
        out.append(Image(("bar", fw, int(h - 2), c), lambda fw=fw, c=c: bar_image(fw, int(h - 2), c),
                         (x + 1, y + 1, fw, h - 2), smooth=False))
    return out


def lines_box(x: float, y: float, w: float, h: float, rgba) -> Lines:
    return Lines([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)], 1, rgba)
