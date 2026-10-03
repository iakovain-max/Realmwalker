"""Picture commands, recorded by screens and drawn by the window (gpu.py). Coordinates are pixels in the frame.

A frame is a stack of layers. Each layer is: the pictures under its text, its text cells (a tcod console whose
empty cells are see-through), and the pictures over its text. A screen draws the map under, and a cursor or a
floating number over; a dialog opens a new layer above everything before it.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

RGBA = tuple[int, int, int, int]


class Batch:
    """Many tiles from one sheet. dst and src are (N, 4) x, y, w, h; rgba is (N, 4) for each tile or (N, 4, 4) for
    each corner (top left, top right, bottom right, bottom left), 0..1."""

    __slots__ = ("sheet", "dst", "src", "rgba")

    def __init__(self, sheet: int, dst: np.ndarray, src: np.ndarray, rgba: np.ndarray) -> None:
        self.sheet = sheet
        self.dst = dst
        self.src = src
        self.rgba = rgba

    def __len__(self) -> int:
        return len(self.dst)


class Sprite:
    """One tile, turned or mirrored (a body falling, a swing)."""

    __slots__ = ("name", "x", "y", "w", "h", "rgba", "angle", "flip")

    def __init__(self, name: str, x: float, y: float, w: float, h: float, rgba: RGBA = (255, 255, 255, 255),
                 angle: float = 0.0, flip: bool = False) -> None:
        self.name, self.x, self.y, self.w, self.h = name, x, y, w, h
        self.rgba, self.angle, self.flip = rgba, angle, flip


class Rect:
    """A filled rectangle; with `bottom`, a vertical gradient from rgba to bottom. With `line`, only its edge."""

    __slots__ = ("x", "y", "w", "h", "rgba", "bottom", "line")

    def __init__(self, x: float, y: float, w: float, h: float, rgba: RGBA, bottom: RGBA | None = None,
                 line: int = 0) -> None:
        self.x, self.y, self.w, self.h, self.rgba, self.bottom, self.line = x, y, w, h, rgba, bottom, line


class Lines:
    """A thick line through points (N, 2). `dash` (on, off) in pixels draws it dashed."""

    __slots__ = ("points", "width", "rgba", "dash")

    def __init__(self, points, width: float, rgba: RGBA, dash: tuple[float, float] | None = None) -> None:
        self.points = np.asarray(points, np.float32).reshape(-1, 2)
        self.width, self.rgba, self.dash = width, rgba, dash


class Text:
    """Text in a real typeface (headings, names on the map, numbers that float up in a fight).
    anchor: two letters as in Pillow: l/m/r then t/m/b (or s for the baseline)."""

    __slots__ = ("x", "y", "text", "font", "size", "rgba", "anchor", "shadow", "outline")

    def __init__(self, x: float, y: float, text: str, font: str = "heading", size: int = 20,
                 rgba: RGBA = (232, 196, 120, 255), anchor: str = "lt", shadow: bool = True, outline: bool = False) -> None:
        self.x, self.y, self.text, self.font, self.size = x, y, text, font, size
        self.rgba, self.anchor, self.shadow, self.outline = rgba, anchor, shadow, outline


class Image:
    """A picture made by code (a painted map, a panel), kept on the GPU under `key` until it is not used for a while.
    `make` returns a PIL image or an (h, w, 4) uint8 array; it is only called the first time the key is drawn."""

    __slots__ = ("key", "make", "dst", "src", "rgba", "smooth")

    def __init__(self, key, make: Callable, dst: tuple[float, float, float, float],
                 src: tuple[float, float, float, float] | None = None, rgba: RGBA = (255, 255, 255, 255),
                 smooth: bool = True) -> None:
        self.key, self.make, self.dst, self.src, self.rgba, self.smooth = key, make, dst, src, rgba, smooth


class Clip:
    """Draw only inside this rectangle from here on (None: everywhere again)."""

    __slots__ = ("rect",)

    def __init__(self, rect: tuple[int, int, int, int] | None) -> None:
        self.rect = rect


Command = Batch | Sprite | Rect | Lines | Text | Image | Clip


class Layer:
    __slots__ = ("console", "under", "over")

    def __init__(self, console) -> None:
        self.console = console
        self.under: list[Command] = []
        self.over: list[Command] = []


# ---------------------------------------------------------------------------- building batches
def tile_batch(atlas, names: list[str], dst: np.ndarray, rgba: np.ndarray | None = None) -> list[Batch]:
    """Batches (one per sheet) drawing `names[i]` at dst[i]. Unknown names are skipped."""
    if not names:
        return []
    rects = [atlas.rects.get(n) for n in names]
    keep = [i for i, r in enumerate(rects) if r is not None]
    if not keep:
        return []
    r = np.array([rects[i] for i in keep], np.float32)
    d = np.asarray(dst, np.float32)[keep]
    if rgba is None:
        c = np.ones((len(keep), 4), np.float32)
    else:
        c = np.asarray(rgba, np.float32)[keep]
    out = []
    for sheet in np.unique(r[:, 0]).astype(int):
        m = r[:, 0] == sheet
        out.append(Batch(int(sheet), d[m], r[m, 1:5], c[m]))
    return out
