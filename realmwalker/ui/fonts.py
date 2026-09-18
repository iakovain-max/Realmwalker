"""Builds the CP437 tileset at any size from DejaVu Sans Mono (free licence, see assets/fonts).

Letters and symbols are rendered from the font. Box-drawing lines and block/shade characters
are drawn pixel by pixel so frames join up cleanly and shades look like classic dithering.
Building at runtime means the text size can be changed with a hotkey.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import tcod.tileset
from PIL import Image, ImageDraw, ImageFont

FONT_FILE = "DejaVuSansMono.ttf"

# Useful characters beyond CP437 (all present in DejaVu Sans Mono).
EXTRA_CHARS = "†‡…–—‘’“”«»×·•√∞≈≠≤≥←↑→↓↔↕▪▫◊○●◘◙◦☼♀♂♠♣♥♦♪♫⌂▲►▼◄"

# Box-drawing characters in CP437: (up, down, left, right) with 1 = single line, 2 = double line.
BOX_ARMS: dict[str, tuple[int, int, int, int]] = {
    "─": (0, 0, 1, 1), "│": (1, 1, 0, 0), "┌": (0, 1, 0, 1), "┐": (0, 1, 1, 0), "└": (1, 0, 0, 1),
    "┘": (1, 0, 1, 0), "├": (1, 1, 0, 1), "┤": (1, 1, 1, 0), "┬": (0, 1, 1, 1), "┴": (1, 0, 1, 1),
    "┼": (1, 1, 1, 1),
    "═": (0, 0, 2, 2), "║": (2, 2, 0, 0), "╔": (0, 2, 0, 2), "╗": (0, 2, 2, 0), "╚": (2, 0, 0, 2),
    "╝": (2, 0, 2, 0), "╠": (2, 2, 0, 2), "╣": (2, 2, 2, 0), "╦": (0, 2, 2, 2), "╩": (2, 0, 2, 2),
    "╬": (2, 2, 2, 2),
    "╒": (0, 1, 0, 2), "╓": (0, 2, 0, 1), "╕": (0, 1, 2, 0), "╖": (0, 2, 1, 0), "╘": (1, 0, 0, 2),
    "╙": (2, 0, 0, 1), "╛": (1, 0, 2, 0), "╜": (2, 0, 1, 0), "╞": (1, 1, 0, 2), "╟": (2, 2, 0, 1),
    "╡": (1, 1, 2, 0), "╢": (2, 2, 1, 0), "╤": (0, 1, 2, 2), "╥": (0, 2, 1, 1), "╧": (1, 0, 2, 2),
    "╨": (2, 0, 1, 1), "╪": (1, 1, 2, 2), "╫": (2, 2, 1, 1),
}

BLOCKS = "█▀▄▌▐░▒▓"


def tile_size(tile_height: int, font_path: Path) -> tuple[int, int, ImageFont.FreeTypeFont]:
    font = ImageFont.truetype(str(font_path), max(6, round(tile_height * 0.84)))
    width = max(5, round(font.getlength("M")))
    return width, tile_height, font


def _box_tile(ch: str, w: int, h: int) -> np.ndarray:
    up, down, left, right = BOX_ARMS[ch]
    t = max(1, round(h / 18))
    g = max(t + 1, round(min(w, h) / 5))
    cx, cy = w // 2, h // 2
    a = np.zeros((h, w), np.uint8)

    def band(c: int) -> tuple[int, int]:
        return c - t // 2, c - t // 2 + t - 1

    def vline(x: int, y0: int, y1: int) -> None:
        x0, x1 = band(x)
        a[max(0, min(y0, y1)) : min(h, max(y0, y1) + 1), max(0, x0) : min(w, x1 + 1)] = 255

    def hline(y: int, x0: int, x1: int) -> None:
        y0, y1 = band(y)
        a[max(0, y0) : min(h, y1 + 1), max(0, min(x0, x1)) : min(w, max(x0, x1) + 1)] = 255

    arms = {"up": up, "down": down, "left": left, "right": right}
    opposite = {"up": "down", "down": "up", "left": "right", "right": "left"}
    # For vertical arms the two strokes of a double line sit left/right; for horizontal arms, up/down.
    sides = {"up": ("left", "right"), "down": ("left", "right"), "left": ("up", "down"), "right": ("up", "down")}

    for arm, weight in arms.items():
        if not weight:
            continue
        vertical = arm in ("up", "down")
        from_start = arm in ("up", "left")  # the arm runs from the top/left edge inwards
        edge = 0 if from_start else (h - 1 if vertical else w - 1)
        centre_line = cx if vertical else cy
        centre = cy if vertical else cx
        near_line = centre - g if from_start else centre + g  # nearer stroke of a crossing double line
        far_line = centre + g if from_start else centre - g
        draw = vline if vertical else hline
        side_a, side_b = sides[arm]
        doubles_across = sum(1 for s in (side_a, side_b) if arms[s] == 2)

        if weight == 1:
            if arms[opposite[arm]]:
                end = centre
            elif doubles_across == 2:
                end = near_line  # touches a double line that runs straight through
            elif doubles_across == 1:
                end = far_line  # must reach both strokes of a double line that ends here
            else:
                end = centre
            draw(centre_line, edge, end)
            continue

        for side, offset in ((side_a, -g), (side_b, +g)):
            other = side_b if side == side_a else side_a
            if arms[side]:
                end = near_line if arms[side] == 2 else centre
            elif arms[opposite[arm]]:
                end = centre
            elif arms[other] == 2:
                end = far_line
            else:
                end = centre
            draw(centre_line + offset, edge, end)
    return a


def _block_tile(ch: str, w: int, h: int) -> np.ndarray:
    a = np.zeros((h, w), np.uint8)
    if ch == "█":
        a[:] = 255
    elif ch == "▀":
        a[: h // 2] = 255
    elif ch == "▄":
        a[h // 2 :] = 255
    elif ch == "▌":
        a[:, : w // 2] = 255
    elif ch == "▐":
        a[:, w // 2 :] = 255
    else:
        yy, xx = np.mgrid[0:h, 0:w]
        if ch == "░":
            mask = (xx % 2 == 0) & (yy % 2 == 0)
        elif ch == "▒":
            mask = (xx + yy) % 2 == 0
        else:  # ▓
            mask = ~((xx % 2 == 1) & (yy % 2 == 1))
        a[mask] = 255
    return a


def _glyph_tile(font: ImageFont.FreeTypeFont, ch: str, w: int, h: int) -> np.ndarray:
    ascent, descent = font.getmetrics()
    baseline = (h - (ascent + descent)) // 2 + ascent
    img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(img)
    advance = font.getlength(ch)
    x = (w - advance) / 2
    draw.text((x, baseline), ch, font=font, fill=255, anchor="ls")
    return np.asarray(img, dtype=np.uint8)


@lru_cache(maxsize=8)
def build_tileset(tile_height: int, font_path: Path) -> tcod.tileset.Tileset:
    w, h, font = tile_size(tile_height, font_path)
    tileset = tcod.tileset.Tileset(w, h)
    chars = {chr(cp) for cp in tcod.tileset.CHARMAP_CP437 if cp > 32} | set(EXTRA_CHARS)
    tileset[ord(" ")] = np.zeros((h, w), np.uint8)
    for ch in sorted(chars):
        if ch in BOX_ARMS:
            tile = _box_tile(ch, w, h)
        elif ch in BLOCKS:
            tile = _block_tile(ch, w, h)
        else:
            tile = _glyph_tile(font, ch, w, h)
        tileset[ord(ch)] = tile
    return tileset


def default_font_path(fonts_dir: Path) -> Path:
    return fonts_dir / FONT_FILE
