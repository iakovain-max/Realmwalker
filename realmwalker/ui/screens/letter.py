"""A letter as a page (Expansion 6 B.2, docs/ADVENTURES.md §8.12): parchment (code-drawn and kept), the writer's hand,
a wax seal in their colours, and the line that matters underlined once the page has been read. Any key closes it; it
opens again from the pack (Read the page)."""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from realmwalker.game import letters
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas

INK = {"plain": (52, 36, 24, 255), "fine": (34, 26, 40, 255), "dark": (24, 10, 10, 255)}
FACE = {"plain": "hand", "fine": "hand_fine", "dark": "hand_dark"}
UNDERLINE_SECONDS = 1.2  # the key line is underlined a moment after the page is first opened


@lru_cache(maxsize=4)
def parchment(w: int, h: int, seed: int = 3):
    """Old paper: warm, blotched, darker at the edges, folded in three."""
    from PIL import Image as PImage, ImageFilter

    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    base = np.array([226, 206, 164], np.float32)
    blot = rng.random((max(2, h // 24), max(2, w // 24))).astype(np.float32)
    big = PImage.fromarray((blot * 255).astype(np.uint8), "L").resize((w, h), PImage.BICUBIC)
    big = np.asarray(big.filter(ImageFilter.GaussianBlur(8)), np.float32) / 255.0
    edge = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy))
    vignette = np.clip(edge / (min(w, h) * 0.12), 0, 1)
    shade = (0.78 + 0.16 * big) * (0.72 + 0.28 * vignette)
    img = base[None, None, :] * shade[..., None]
    for fy in (h / 3, 2 * h / 3):  # (where it was folded)
        band = np.clip(1 - np.abs(yy - fy) / 3.0, 0, 1)
        img *= (1 - 0.12 * band)[..., None]
    img *= rng.normal(1.0, 0.025, (h, w, 1)).astype(np.float32)
    a = np.full((h, w, 1), 255, np.float32)
    rough = (edge < 2 + 3 * rng.random((h, w))) & (edge < 5)
    a[rough] = 0
    return PImage.fromarray(np.clip(np.concatenate([img, a], axis=2), 0, 255).astype(np.uint8), "RGBA")


@lru_cache(maxsize=2)
def _seal():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (96, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = [(48 + math.cos(a) * (40 + 5 * math.sin(a * 7)), 48 + math.sin(a) * (40 + 5 * math.sin(a * 7)))
           for a in np.linspace(0, math.tau, 40)]
    d.polygon(pts, fill=(255, 255, 255, 255))
    d.ellipse([22, 22, 74, 74], outline=(200, 200, 200, 255), width=3)
    d.line([(36, 60), (48, 32), (60, 60)], fill=(190, 190, 190, 255), width=4)
    d.line([(40, 52), (56, 52)], fill=(190, 190, 190, 255), width=3)
    return im.filter(ImageFilter.GaussianBlur(0.6))


class LetterScreen(Screen):
    modal = True
    title = "A letter"
    sound_open = "ui_page"

    def __init__(self, app, game, lid: str) -> None:
        super().__init__(app)
        self.game = game
        self.lid = lid
        self.rec = letters.records(game.world).get(lid)
        self.first = letters.mark_read(game, lid)
        self.opened = None  # when the page was first drawn (for the underline)

    def handle_key(self, ev: KeyEvent) -> bool:
        self.close()
        return True

    def render(self, canvas: Canvas) -> None:
        rec = self.rec
        if rec is None:
            self.close()
            return
        from realmwalker.ui.gfx import typefaces
        from realmwalker.ui.gfx.scene import Image, Rect, Text

        canvas.dim()
        W, H = canvas.width * canvas.cell_w, canvas.height * canvas.cell_h
        pw = int(min(W * 0.62, 760))
        size = max(16, int(pw / 30))
        face = FACE.get(rec["hand"], "hand")
        ink = INK.get(rec["hand"], INK["plain"])
        margin = pw * 0.1
        lines: list[tuple[str, int]] = []  # (words, which of the letter's lines)
        for i, para in enumerate(rec["lines"]):
            for part in typefaces.wrap(para, int(pw - 2 * margin), face, size) if para else [""]:
                lines.append((part, i))
            lines.append(("", -1))
        step = size * 1.45
        ph = int(min(H * 0.92, margin * 1.4 + step * (len(lines) + 2) + size * 3))
        px, py = (W - pw) / 2, (H - ph) / 2
        canvas.clear_cells(0, 0, canvas.width, canvas.height)
        canvas.over(Rect(px + 8, py + 10, pw, ph, (0, 0, 0, 120)))
        canvas.over(Image(("parchment", pw, ph), lambda: parchment(pw, ph), (px, py, pw, ph), smooth=True))
        now = canvas.now
        if self.opened is None:
            self.opened = now
        underline = not self.first or not canvas.gfx.animate or now - self.opened >= UNDERLINE_SECONDS
        y = py + margin * 0.9
        for words, i in lines:
            if words:
                canvas.over(Text(px + margin, y, words, face, size, ink, anchor="lt", shadow=False))
                if underline and rec.get("key") is not None and i == int(rec["key"]):
                    lw = typefaces.measure(words, face, size)[0]
                    canvas.over(Rect(px + margin, y + size * 1.12, lw, max(1, size // 12), (*ink[:3], 200)))
            y += step
        canvas.over(Text(px + pw - margin, y + size * 0.4, f"- {rec['from']}", face, size, ink, anchor="rt",
                         shadow=False))
        s = size * 3.2
        r, g, b = rec.get("seal", (150, 40, 32))
        canvas.over(Image("wax_seal", _seal, (px + margin * 0.6, py + ph - s - margin * 0.4, s, s), rgba=(r, g, b, 255)))
        hint = "Any key: put it away"
        canvas.over(Text(W / 2, py + ph + size * 0.9, hint, "prose", int(size * 0.8), (200, 190, 170, 220),
                         anchor="mt"))
        canvas.hit(0, 0, canvas.width, canvas.height, action=self.close)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("enter")]
