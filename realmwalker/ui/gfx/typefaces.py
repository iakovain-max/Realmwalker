"""Real typefaces for headings, names on the map and numbers in a fight (Pillow only, no window needed).

heading: Cinzel (titles of screens and panels, names on the map)
prose:   EB Garamond (longer passages, where there is room)
title:   Grenze Gotisch (the name of the game)
mono:    DejaVu Sans Mono (numbers)
All are under the SIL Open Font Licence or the DejaVu licence; see assets/fonts.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import numpy as np

log = logging.getLogger("realmwalker.gfx")

FACES = {
    "heading": ("Cinzel.ttf", "Bold"),
    "heading_light": ("Cinzel.ttf", "Regular"),
    "prose": ("EBGaramond.ttf", "Regular"),
    "prose_bold": ("EBGaramond.ttf", "SemiBold"),
    "prose_italic": ("EBGaramond.ttf", "Regular"),
    "title": ("GrenzeGotisch.ttf", "Bold"),
    "mono": ("DejaVuSansMono.ttf", None),
}

_folder: Path | None = None


def set_folder(folder: Path) -> None:
    global _folder
    _folder = folder
    font.cache_clear()


@lru_cache(maxsize=64)
def font(role: str, size: int):
    from PIL import ImageFont

    fn, variation = FACES.get(role, FACES["heading"])
    folder = _folder or Path(__file__).resolve().parents[3] / "assets" / "fonts"
    try:
        f = ImageFont.truetype(str(folder / fn), max(6, int(size)))
        if variation:
            try:
                f.set_variation_by_name(variation)
            except Exception:  # not a variable font, or no such style: the default is fine
                pass
        return f
    except OSError:
        log.warning("Typeface %s is missing; using the default font.", fn)
        return ImageFont.load_default()


def measure(text: str, role: str = "heading", size: int = 20) -> tuple[int, int]:
    """Width and height in pixels."""
    if not text:
        return 0, 0
    f = font(role, size)
    l, t, r, b = f.getbbox(text)
    return int(r - min(0, l)), int(b - min(0, t))


def render(text: str, role: str, size: int, rgba, shadow: bool = True, outline: bool = False) -> tuple[np.ndarray, int, int]:
    """The text as an RGBA array, and the offset of its top left from the anchor's top left (for the shadow)."""
    from PIL import Image, ImageDraw, ImageFilter

    f = font(role, size)
    l, t, r, b = f.getbbox(text)
    pad = 3 if (shadow or outline) else 1
    w, h = int(r - l) + pad * 2 + 2, int(b - t) + pad * 2 + 2
    im = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ox, oy = pad - l, pad - t
    if shadow or outline:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        if outline:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    sd.text((ox + dx, oy + dy), text, font=f, fill=(8, 6, 4, 235))
        if shadow:
            sd.text((ox + 1, oy + 2), text, font=f, fill=(0, 0, 0, 200))
            sh = sh.filter(ImageFilter.GaussianBlur(1.0)) if not outline else sh
        im = Image.alpha_composite(im, sh)
        d = ImageDraw.Draw(im)
    d.text((ox, oy), text, font=f, fill=tuple(rgba[:3]) + (255,))
    a = np.asarray(im, np.uint8).copy()
    if len(rgba) > 3 and rgba[3] < 255:
        a[..., 3] = (a[..., 3].astype(np.uint16) * rgba[3] // 255).astype(np.uint8)
    return a, -pad + l, -pad + t


def wrap(text: str, width: int, role: str = "prose", size: int = 20) -> list[str]:
    """Break text into lines no wider than `width` pixels (newlines kept)."""
    f = font(role, size)
    out: list[str] = []
    for para in text.split("\n"):
        words = para.split(" ")
        line = ""
        for w in words:
            trial = f"{line} {w}" if line else w
            if f.getlength(trial) <= width or not line:
                line = trial
            else:
                out.append(line)
                line = w
        out.append(line)
    return out
