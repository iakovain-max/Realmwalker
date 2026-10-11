"""The expansion shelf on the title screen (docs/EXPANSIONS.md §4.13): a column of framed icons along the right edge,
one per released expansion, in release order (wrapping into a second column when the window is short). Pointing at
one shows its card: the name, the tagline, what it adds, what it counts, its version and date. A new icon glints until
it has been pointed at once (the ids already seen are kept in Settings). Clicking one, or E, opens the Expansions
screen."""

from __future__ import annotations

import math

from realmwalker import expansions as exp
from realmwalker.ui.widgets import Canvas

MARGIN = 16  # pixels from the window's edge
GAP = 8


def frame_size(canvas: Canvas) -> tuple[int, int]:
    """(frame, icon) in pixels: 40/32, or 72/64 on a big window."""
    return (72, 64) if canvas.height * canvas.cell_h >= 1000 else (40, 32)


def layout(canvas: Canvas, count: int) -> list[tuple[float, float, int]]:
    """(x, y, size) in pixels of each frame: down the right edge, then a column further left."""
    size, _ = frame_size(canvas)
    w_px, h_px = canvas.width * canvas.cell_w, canvas.height * canvas.cell_h
    per_col = max(1, int((h_px - 2 * MARGIN - canvas.cell_h) // (size + GAP)))
    out = []
    for i in range(count):
        col, row = divmod(i, per_col)
        out.append((w_px - MARGIN - size - col * (size + GAP), MARGIN + row * (size + GAP), size))
    return out


def cell_box(canvas: Canvas, x: float, y: float, size: int) -> tuple[int, int, int, int]:
    """The text cells a frame covers (for its hit area)."""
    cw, ch = canvas.cell_w, canvas.cell_h
    x0, y0 = int(x // cw), int(y // ch)
    x1, y1 = int(math.ceil((x + size) / cw)), int(math.ceil((y + size) / ch))
    return x0, y0, max(1, x1 - x0), max(1, y1 - y0)


def card_lines(e: exp.Expansion, width: int) -> list[tuple[str, str, int, tuple]]:
    """The card's lines as (text, typeface, size, colour), wrapped to `width` pixels."""
    from realmwalker.ui.gfx import typefaces

    gold, pale, dim = (232, 196, 120, 255), (226, 216, 196, 255), (168, 156, 140, 255)
    lines: list[tuple[str, str, int, tuple]] = []
    for t in typefaces.wrap(e.name, width, "heading", 22):
        lines.append((t, "heading", 22, gold))
    for t in typefaces.wrap(e.tagline, width, "prose_italic", 17):
        lines.append((t, "prose_italic", 17, pale))
    if e.adds:
        lines.append(("Adds:", "prose_bold", 16, gold))
        for add in e.adds:
            for i, t in enumerate(typefaces.wrap(add, width - 14, "prose", 16)):
                lines.append((("· " if i == 0 else "  ") + t, "prose", 16, pale))
    if e.counts:
        for t in typefaces.wrap(" · ".join(e.counts), width, "prose", 15):
            lines.append((t, "prose", 15, dim))
    if e.when():
        lines.append((e.when(), "prose", 15, dim))
    return lines


def line_height(size: int) -> int:
    return int(size * 1.3)


def card_size(lines) -> tuple[int, int]:
    from realmwalker.ui.gfx import typefaces

    w = max((typefaces.measure(t, face, size)[0] for t, face, size, _ in lines), default=0)
    h = sum(line_height(size) for _, _, size, _ in lines)
    return w + 32, h + 28


def draw_card(canvas: Canvas, e: exp.Expansion, at: tuple[float, float, int]) -> tuple[float, float, int, int]:
    """The card beside a frame (to its left, kept inside the window). Returns its pixel rect."""
    from realmwalker.ui.gfx import theme
    from realmwalker.ui.gfx.scene import Text

    x, y, size = at
    h_px = canvas.height * canvas.cell_h
    width = min(380, max(200, int(x - GAP - MARGIN - 32)))
    lines = card_lines(e, width)
    cw_, ch_ = card_size(lines)
    cx = max(MARGIN, x - GAP - cw_)
    cy = max(MARGIN, min(y, h_px - MARGIN - ch_))
    canvas.over(*theme.panel(cx, cy, cw_, ch_, "glass", ornaments=False))
    ty = cy + 14
    for text, face, fsize, rgba in lines:
        canvas.over(Text(cx + 16, ty, text, face, fsize, rgba, anchor="lt", shadow=True))
        ty += line_height(fsize)
    return cx, cy, cw_, ch_


def draw(canvas: Canvas, app, on_open) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Draw the shelf; returns (expansion id, cell box) for each icon (its hit area)."""
    from realmwalker.ui.gfx import theme
    from realmwalker.ui.gfx.scene import Rect

    shown = exp.released(app.data)
    if not shown:
        return []
    seen = set(app.settings.expansions_seen)
    boxes = []
    hovered = None
    for e, (x, y, size) in zip(shown, layout(canvas, len(shown))):
        box = cell_box(canvas, x, y, size)
        over = canvas.hit(*box, action=lambda e=e: on_open(e.id))
        r, g, b = e.accent
        canvas.over(*theme.panel(x, y, size, size, "glass", ornaments=False))
        canvas.over(Rect(x + 1, y + 1, size - 2, size - 2, (r, g, b, 255 if over else 200), line=2))
        icon = frame_size(canvas)[1]
        if not canvas.sprite(e.icon, x + (size - icon) / 2, y + (size - icon) / 2, icon, icon):
            canvas.over(Rect(x + size / 2 - 6, y + size / 2 - 6, 12, 12, (r, g, b, 255)))
        if e.id not in seen:  # new: a soft glint until it has been pointed at
            glow = 0.5 + 0.5 * math.sin(canvas.now * 3.0) if canvas.gfx.ambient else 0.7
            canvas.over(Rect(x - 3, y - 3, size + 6, size + 6, (255, 236, 180, int(60 + 120 * glow)), line=2))
        if over:
            hovered = (e, (x, y, size))
        boxes.append((e.id, box))
    if hovered is not None:
        e, at = hovered
        draw_card(canvas, e, at)
        if e.id not in seen:
            app.settings.expansions_seen = sorted(seen | {e.id})
            app.save_settings()
    return boxes
