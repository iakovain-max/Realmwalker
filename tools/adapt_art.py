"""The adaptation pass for borrowed creature tiles (docs/EXPANSIONS.md §4.11, Expansion 1 part E.2).

The Dungeon Crawl pack's monsters are drawn in another game's manner. Before they go into the atlas, each passes
through the same steps so that it sits beside Realmwalker's own figures:

    clean     soft glows, shadows and stray half-transparent pixels go (alpha is all or nothing)
    size      height set by what it is (a wolf is smaller than a man), feet on the dolls' foot line
    palette   colours snapped onto ramps of a few shades each, keeping each creature's colour relationships,
              shadows leaning to the game's warm dark
    outline   one consistent dark outline just inside the silhouette
    light     light from the top left: a highlight on edges that face it, a shade on those that do not

Any creature can opt out of a step that makes it worse (`SKIP`). `before_after(...)` writes the contact sheet that
shows each borrowed tile before and after, side by side (`build_tiles.py --adapt-sheet PATH`).
"""

from __future__ import annotations

import numpy as np
from PIL import Image

OUTLINE = np.array([22, 17, 16], np.float32)
SHADOW = np.array([44, 32, 36], np.float32)  # the game's dark leans warm and a little red
FOOT = 31  # the dolls stand on the tile's last row
LEVELS = 7  # shades per colour ramp

# How tall a creature stands on its square, as a share of the tile (a man is the whole tile). Left out: the whole.
HEIGHT = {
    "wolf": 0.78, "wild_dog": 0.66, "giant_rat": 0.5, "stirge": 0.66, "boar": 0.72,
    "black_bear": 0.9, "hound": 0.72, "war_dog": 0.75, "sheep": 0.66, "snake": 0.5, "adder": 0.5,
    "giant_frog": 0.7, "giant_beetle": 0.62, "scorpion": 0.66, "giant_centipede": 0.72, "bat": 0.62, "raven": 0.62,
    "kobold": 0.78, "skeleton_beast": 0.72,
}

# Steps a creature is better without.
SKIP = {
    "ghost": {"clean", "palette", "outline", "light"},  # faint and dotted: every pixel is an edge
    "wraith": {"clean", "palette", "outline", "light"},
    "fire_elemental": {"palette", "light"},  # its fire keeps its own colours and light
    "golden_dragon": {"palette"},
}

STEPS = ("clean", "size", "palette", "outline", "light")


def _lum(rgb: np.ndarray) -> np.ndarray:
    return rgb @ np.array([0.299, 0.587, 0.114], np.float32)


def clean(a: np.ndarray) -> np.ndarray:
    a = a.copy()
    alpha = a[..., 3]
    a[..., 3] = np.where(alpha >= 110, 255, 0)
    a[a[..., 3] == 0, :3] = 0
    return a


def bbox(a: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(a[..., 3] > 0)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def size(a: np.ndarray, height: float | None, hard: bool = True) -> np.ndarray:
    """Scale the figure to its height (box filter, then alpha made hard again) and stand it on the foot line."""
    box = bbox(a)
    if box is None:
        return a
    x0, y0, x1, y1 = box
    fig = Image.fromarray(a[y0:y1, x0:x1].astype(np.uint8), "RGBA")
    w, h = fig.size
    if height is not None and h > 0:
        want = max(4, round(32 * height))
        if want < h:
            k = want / h
            fig = fig.resize((max(1, round(w * k)), want), Image.BOX)
    f = np.asarray(fig, np.float32)
    f = clean(f) if hard else f
    out = np.zeros_like(a)
    fh, fw = f.shape[:2]
    left = max(0, min(32 - fw, x0 + (w - fw) // 2))
    top = FOOT + 1 - fh
    out[max(0, top):top + fh, left:left + fw] = f[max(0, -top):]
    return out


def palette(a: np.ndarray) -> np.ndarray:
    """Each pixel's shade snapped to one of a few levels, its colour kept in proportion; the darks warmed."""
    a = a.copy()
    on = a[..., 3] > 0
    rgb = a[..., :3]
    lum = _lum(rgb)
    lo, hi = (np.percentile(lum[on], 2), np.percentile(lum[on], 98)) if on.any() else (0, 255)
    span = max(1.0, hi - lo)
    t = np.clip((lum - lo) / span, 0, 1)
    q = np.round(t * (LEVELS - 1)) / (LEVELS - 1)
    want = lo + q * span
    scale = np.where(lum > 1, want / np.maximum(lum, 1), 1.0)[..., None]
    snapped = np.clip(rgb * scale, 0, 255)
    dark = (1 - q)[..., None] ** 2 * 0.35  # the deepest shade leans to the warm dark
    snapped = snapped * (1 - dark) + SHADOW * dark
    a[..., :3] = np.where(on[..., None], snapped, rgb)
    return a


def _edge(on: np.ndarray) -> np.ndarray:
    pad = np.pad(on, 1)
    n = pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
    return on & ~n


def outline(a: np.ndarray) -> np.ndarray:
    a = a.copy()
    on = a[..., 3] > 0
    edge = _edge(on)
    rgb = a[..., :3]
    dark = _lum(rgb) < 50
    mix = np.where((edge & ~dark)[..., None], 0.72, 0.0)
    a[..., :3] = rgb * (1 - mix) + OUTLINE * mix
    return a


def light(a: np.ndarray) -> np.ndarray:
    """Pixels just inside the outline: lit where the light comes from (up and left), shaded on the far side."""
    a = a.copy()
    on = a[..., 3] > 0
    edge = _edge(on)
    inner = on & ~edge
    pad = np.pad(edge | ~on, 1, constant_values=True)
    up_left = pad[:-2, :-2] | pad[:-2, 1:-1] | pad[1:-1, :-2]
    down_right = pad[2:, 2:] | pad[2:, 1:-1] | pad[1:-1, 2:]
    lit = inner & up_left & ~down_right
    shade = inner & down_right & ~up_left
    rgb = a[..., :3]
    rgb = np.where(lit[..., None], np.clip(rgb * 1.16 + 10, 0, 255), rgb)
    rgb = np.where(shade[..., None], rgb * 0.82, rgb)
    a[..., :3] = rgb
    return a


def adapt(im: Image.Image, creature: str = "") -> Image.Image:
    a = np.asarray(im.convert("RGBA"), np.float32)
    if a.shape[:2] != (32, 32):
        return im
    skip = SKIP.get(creature, set())
    if "clean" not in skip:
        a = clean(a)
    if "size" not in skip:
        a = size(a, HEIGHT.get(creature), hard="clean" not in skip)
    if "palette" not in skip:
        a = palette(a)
    if "outline" not in skip:
        a = outline(a)
    if "light" not in skip:
        a = light(a)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def before_after(pairs: list[tuple[str, Image.Image, Image.Image]], path, scale: int = 4) -> None:
    """A contact sheet: each creature's tile as borrowed and as adapted, side by side, a man beside them for scale."""
    from PIL import ImageDraw

    cols = 4
    cell_w, cell_h = (32 * 2 + 8) * scale, 32 * scale + 14
    rows = -(-len(pairs) // cols)
    sheet = Image.new("RGBA", (cols * (cell_w + 12) + 12, rows * (cell_h + 10) + 10), (52, 50, 46, 255))
    d = ImageDraw.Draw(sheet)
    for i, (name, before, after) in enumerate(pairs):
        r, c = divmod(i, cols)
        x, y = 12 + c * (cell_w + 12), 10 + r * (cell_h + 10)
        for k, im in enumerate((before, after)):
            big = im.resize((32 * scale, 32 * scale), Image.NEAREST)
            sheet.alpha_composite(big, (x + k * (32 + 8) * scale, y))
        d.text((x, y + 32 * scale + 1), name, fill=(220, 210, 190, 255))
    sheet.save(path)
