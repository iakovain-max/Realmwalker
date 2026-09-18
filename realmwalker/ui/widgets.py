"""Drawing helpers and small widgets (menus, scrolling text), with mouse hit regions.

Screens draw every frame onto a Canvas. Anything clickable or hoverable registers a region;
the app routes the next mouse click or hover to it. Only the top screen is interactive.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import tcod.console

from realmwalker.ui import colors, markup
from realmwalker.ui.colors import Color
from realmwalker.ui.input import KeyEvent

SINGLE = "┌─┐│ │└─┘"
DOUBLE = "╔═╗║ ║╚═╝"


@dataclass
class Region:
    x: int
    y: int
    w: int
    h: int
    action: Callable[[], None] | None = None
    tooltip: str | None = None
    wheel: Callable[[int], None] | None = None
    right_action: Callable[[], None] | None = None

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h


class Canvas:
    def __init__(self, console: tcod.console.Console, mouse: tuple[int, int] = (-1, -1), interactive: bool = True) -> None:
        self.con = console
        self.width = console.width
        self.height = console.height
        self.mouse = mouse
        self.interactive = interactive
        self.regions: list[Region] = []
        self.tooltip: str | None = None

    # ------------------------------------------------------------------ mouse
    def hovered(self, x: int, y: int, w: int, h: int) -> bool:
        mx, my = self.mouse
        return self.interactive and x <= mx < x + w and y <= my < y + h

    def hit(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        action: Callable[[], None] | None = None,
        tooltip: str | None = None,
        *,
        wheel: Callable[[int], None] | None = None,
        right_action: Callable[[], None] | None = None,
    ) -> bool:
        """Register a clickable/hoverable area. Returns True while the mouse is over it."""
        if not self.interactive:
            return False
        if action or tooltip or wheel or right_action:
            self.regions.append(Region(x, y, w, h, action, tooltip, wheel, right_action))
        over = self.hovered(x, y, w, h)
        if over and tooltip:
            self.tooltip = tooltip
        return over

    # ------------------------------------------------------------------ drawing
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def text(self, x: int, y: int, s: str, fg: Color = colors.FG, bg: Color | None = None, max_width: int | None = None) -> int:
        """Print plain text on one line (clipped). Returns the x after the text."""
        if y < 0 or y >= self.height or not s:
            return x
        if max_width is not None:
            s = s[: max(0, max_width)]
        if x < 0:
            s = s[-x:]
            x = 0
        s = s[: max(0, self.width - x)]
        if s:
            self.con.print(x, y, s, fg=fg, bg=bg)
        return x + len(s)

    def spans(self, x: int, y: int, spans: list[markup.Span], bg: Color | None = None, max_width: int | None = None) -> int:
        limit = x + max_width if max_width is not None else self.width
        for text, color in spans:
            if x >= limit:
                break
            x = self.text(x, y, text[: limit - x], color, bg)
        return x

    def markup(self, x: int, y: int, text: str, fg: Color = colors.FG, bg: Color | None = None, max_width: int | None = None) -> int:
        return self.spans(x, y, markup.parse(text, fg), bg, max_width)

    def wrapped(self, x: int, y: int, text: str, width: int, fg: Color = colors.FG, max_lines: int | None = None,
                bg: Color | None = None) -> int:
        """Word-wrapped marked-up text. Returns the number of lines drawn."""
        lines = markup.wrap(text, width, fg)
        if max_lines is not None:
            lines = lines[:max_lines]
        for i, line in enumerate(lines):
            self.spans(x, y + i, line, bg, width)
        return len(lines)

    def centered(self, y: int, text: str, fg: Color = colors.FG, x: int = 0, width: int | None = None) -> None:
        width = self.width if width is None else width
        n = markup.length(text)
        self.markup(x + max(0, (width - n) // 2), y, text, fg)

    def fill(self, x: int, y: int, w: int, h: int, bg: Color, ch: str = " ", fg: Color | None = None) -> None:
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + w), min(self.height, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        self.con.rgb["ch"][x0:x1, y0:y1] = ord(ch)
        self.con.rgb["bg"][x0:x1, y0:y1] = bg
        if fg is not None:
            self.con.rgb["fg"][x0:x1, y0:y1] = fg

    def frame(self, x: int, y: int, w: int, h: int, title: str = "", *, fg: Color = colors.BORDER,
              bg: Color | None = colors.PANEL_BG, double: bool = False, title_fg: Color = colors.TITLE) -> None:
        if w < 2 or h < 2:
            return
        if bg is not None:
            self.fill(x, y, w, h, bg)
        deco = DOUBLE if double else SINGLE
        tl, top, tr, left, _, right, bl, bottom, br = deco
        self.text(x, y, tl + top * (w - 2) + tr, fg)
        for yy in range(y + 1, y + h - 1):
            self.text(x, yy, left, fg)
            self.text(x + w - 1, yy, right, fg)
        self.text(x, y + h - 1, bl + bottom * (w - 2) + br, fg)
        if title:
            label = f" {title} "
            self.text(x + 2, y, label[: max(0, w - 4)], title_fg)

    def hline(self, x: int, y: int, w: int, ch: str = "─", fg: Color = colors.BORDER) -> None:
        self.text(x, y, ch * max(0, w), fg)

    def section(self, x: int, y: int, w: int, title: str, fg: Color = colors.BORDER) -> None:
        """A divider line with a heading: ── Title ─────"""
        label = f"── {title} "
        self.text(x, y, label, colors.TITLE)
        self.hline(x + len(label), y, w - len(label), "─", fg)

    def button(self, x: int, y: int, label: str, action: Callable[[], None], *, hotkey: str | None = None,
               tooltip: str | None = None, enabled: bool = True) -> int:
        """[G] Generate  - clickable, highlighted on hover. Returns the x after it."""
        text = f"[{hotkey}] {label}" if hotkey else f"[ {label} ]"
        over = self.hit(x, y, len(text), 1, action if enabled else None, tooltip)
        bg = colors.HOVER_BG if over and enabled else None
        if not enabled:
            return self.text(x, y, text, colors.FAINT)
        if hotkey:
            self.text(x, y, "[", colors.DIM, bg)
            self.text(x + 1, y, hotkey, colors.TITLE, bg)
            self.text(x + 1 + len(hotkey), y, "] ", colors.DIM, bg)
            return self.text(x + 3 + len(hotkey), y, label, colors.SELECT_FG if over else colors.FG, bg)
        return self.text(x, y, text, colors.SELECT_FG if over else colors.FG, bg)

    def draw_tooltip(self) -> None:
        if not self.tooltip or self.mouse[0] < 0:
            return
        width = min(48, max(12, markup.length(self.tooltip) + 2))
        lines = markup.wrap(self.tooltip, width - 2)
        h = len(lines) + 2
        mx, my = self.mouse
        x = mx + 2 if mx + 2 + width <= self.width else max(0, mx - width - 1)
        y = my + 1 if my + 1 + h <= self.height else max(0, my - h)
        self.frame(x, y, width, h, fg=colors.DIM, bg=(24, 22, 20))
        for i, line in enumerate(lines):
            self.spans(x + 1, y + 1 + i, line)


# ---------------------------------------------------------------------------- menus
@dataclass
class MenuItem:
    label: str
    action: Callable[[], None] | None = None
    hotkey: str | None = None
    enabled: bool = True
    note: str = ""


@dataclass
class Menu:
    items: list[MenuItem]
    selected: int = 0
    on_disabled: Callable[[MenuItem], None] | None = None
    _last_mouse: tuple[int, int] = field(default=(-1, -1), repr=False)

    def move(self, delta: int) -> None:
        if self.items:
            self.selected = (self.selected + delta) % len(self.items)

    def activate(self, index: int) -> None:
        if not 0 <= index < len(self.items):
            return
        self.selected = index
        item = self.items[index]
        if item.enabled and item.action:
            item.action()
        elif not item.enabled and self.on_disabled:
            self.on_disabled(item)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "up" and not ev.ctrl:
            self.move(-1)
        elif ev.key == "down" and not ev.ctrl:
            self.move(1)
        elif ev.key == "home":
            self.selected = 0
        elif ev.key == "end":
            self.selected = len(self.items) - 1
        elif ev.key == "enter":
            self.activate(self.selected)
        else:
            for i, item in enumerate(self.items):
                if item.hotkey and ev.is_text and ev.key.lower() == item.hotkey.lower():
                    self.activate(i)
                    return True
            return False
        return True

    def hotkeys(self) -> list[str]:
        return [i.hotkey for i in self.items if i.hotkey]

    def render(self, canvas: Canvas, x: int, y: int, width: int) -> None:
        # Hovering selects, but only when the mouse actually moved (keyboard keeps control otherwise).
        mouse_moved = canvas.mouse != self._last_mouse
        self._last_mouse = canvas.mouse
        for i, item in enumerate(self.items):
            row = y + i
            index = i
            over = canvas.hit(x, row, width, 1, action=lambda index=index: self.activate(index),
                              tooltip=item.note or None)
            if over and mouse_moved:
                self.selected = i
            selected = i == self.selected
            bg = colors.HILITE_BG if selected else None
            if bg:
                canvas.fill(x, row, width, 1, bg)
            if item.enabled:
                fg = colors.SELECT_FG if selected else colors.FG
            else:
                fg = colors.DIM if selected else colors.FAINT
            cx = x
            cx = canvas.text(cx, row, "► " if selected else "  ", colors.TITLE, bg)
            if item.hotkey:
                key_fg = colors.TITLE if item.enabled else fg
                cx = canvas.text(cx, row, item.hotkey.upper() if len(item.hotkey) == 1 else item.hotkey, key_fg, bg)
                cx = canvas.text(cx, row, "  ", fg, bg)
            canvas.text(cx, row, item.label, fg, bg, max_width=x + width - cx)


class ScrollText:
    """A scrollable block of marked-up text (help pages, long descriptions, logs)."""

    def __init__(self, text: str = "") -> None:
        self.text = text
        self.offset = 0
        self._lines: list[list[markup.Span]] = []
        self._width = -1
        self._height = 1

    def set_text(self, text: str) -> None:
        self.text = text
        self._width = -1

    def scroll(self, delta: int) -> None:
        max_offset = max(0, len(self._lines) - self._height)
        self.offset = max(0, min(max_offset, self.offset + delta))

    def handle_key(self, ev: KeyEvent) -> bool:
        step = {"up": -1, "down": 1, "pageup": -max(1, self._height - 1), "pagedown": max(1, self._height - 1)}
        if ev.key in step:
            self.scroll(step[ev.key])
            return True
        if ev.key == "home":
            self.offset = 0
            return True
        if ev.key == "end":
            self.scroll(10**6)
            return True
        return False

    def render(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        if w != self._width:
            self._lines = markup.wrap(self.text, max(1, w - 1))
            self._width = w
        self._height = h
        self.scroll(0)
        canvas.hit(x, y, w, h, wheel=lambda dy: self.scroll(-dy * 3))
        for i, line in enumerate(self._lines[self.offset : self.offset + h]):
            canvas.spans(x, y + i, line, max_width=w - 1)
        if len(self._lines) > h:
            # A simple scroll bar on the right edge.
            bar_h = max(1, h * h // len(self._lines))
            max_offset = max(1, len(self._lines) - h)
            bar_y = y + (h - bar_h) * self.offset // max_offset
            for yy in range(y, y + h):
                canvas.text(x + w - 1, yy, "│", colors.FAINT)
            for yy in range(bar_y, bar_y + bar_h):
                canvas.text(x + w - 1, yy, "█", colors.DIM)
