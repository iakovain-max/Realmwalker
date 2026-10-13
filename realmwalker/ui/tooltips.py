"""Drawing cards (rules/describe.Card) as small panels beside what is pointed at (docs/EXPANSIONS.md §4.15).

A card stays inside the window and never covers the thing it describes: it goes to the right of it, or the left, or
below, or above, whichever fits first. It is drawn in cells (the words) over a panel picture, with its icon beside
the title.
"""

from __future__ import annotations

from realmwalker.rules.describe import Card
from realmwalker.ui import colors, markup

MIN_W, MAX_W = 26, 46


def layout(card: Card, width: int) -> list:
    """The card's lines as rows of coloured spans, wrapped to `width` cells, title first."""
    rows: list = []
    texts = [f"<title>{card.title}</>"] + ([f"<dim>{card.subtitle}</>"] if card.subtitle else []) + list(card.lines)
    if card.more:
        texts.append("<dim>More on the sheet.</>")
    if card.footer:
        texts.append(f"<dim>{card.footer}</>")
    for text in texts:
        rows.extend(markup.wrap(text, width) or [[]])
    return rows


def size(card: Card, window_w: int) -> tuple[int, int, list]:
    """The panel's width and height in cells, and its wrapped lines."""
    longest = max([markup.length(card.title) + 3] + [markup.length(x) for x in card.lines]
                  + [markup.length(card.footer), markup.length(card.subtitle)])
    w = max(min(MIN_W, window_w - 2), min(MAX_W, longest + 2, window_w - 2))
    inner = w - 2
    lines = layout(card, inner - (3 if card.icon else 0))
    return w, len(lines) + 2, lines


def place(w: int, h: int, rect, mouse, width: int, height: int) -> tuple[int, int]:
    """Where a w x h panel goes: beside the pointed-at rectangle, inside the window, not over it."""
    if rect is None:
        mx, my = mouse
        rect = (mx, my, 1, 1)
    rx, ry, rw, rh = rect
    my = mouse[1] if mouse[1] >= 0 else ry
    y = max(0, min(height - h, my - 1))
    if rx + rw + 1 + w <= width:
        return rx + rw + 1, y
    if rx - 1 - w >= 0:
        return rx - 1 - w, y
    x = max(0, min(width - w, (mouse[0] if mouse[0] >= 0 else rx) - w // 2))
    if ry + rh + h <= height:
        return x, ry + rh
    if ry - h >= 0:
        return x, ry - h
    return x, max(0, height - h)


def _fits_clear(w: int, h: int, rect, width: int, height: int) -> bool:
    rx, ry, rw, rh = rect
    return (rx + rw + 1 + w <= width or rx - 1 - w >= 0 or ry + rh + h <= height or ry - h >= 0) and h <= height


def draw_card(canvas, card: Card, rect=None) -> tuple[int, int, int, int]:
    """Draw the card beside `rect` (cells: x, y, w, h). Returns where it went."""
    w, h, lines = size(card, canvas.width)
    if rect is not None and not _fits_clear(w, h, rect, canvas.width, canvas.height):
        rx, _, rw, _ = rect
        room = max(canvas.width - (rx + rw + 1), rx - 1)  # narrower, beside it, rather than over it
        if room >= MIN_W - 6:
            w, h, lines = size(card, room + 2)
            w = min(w, room)
    h = min(h, canvas.height)
    x, y = place(w, h, rect, canvas.mouse, canvas.width, canvas.height)
    canvas.frame(x, y, w, h, fg=colors.DIM, bg=(24, 22, 20), style="glass")
    tx = x + 1
    if card.icon:
        canvas.icon(x + 1, y + 1, card.icon)
        tx = x + 4
    for i, row in enumerate(lines[: h - 2]):
        canvas.spans(tx, y + 1 + i, row, max_width=x + w - 1 - tx)
    return x, y, w, h
