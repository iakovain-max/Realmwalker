"""A small menu that opens where you right-click: what you can do with the thing under the mouse."""

from __future__ import annotations

from collections.abc import Callable

from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent, MouseEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas

Entry = tuple[str, Callable[[], None] | None, str]  # (label, action or None for disabled, icon name)


class ContextMenu(Screen):
    modal = True
    show_status = False

    def __init__(self, app, at: tuple[int, int], entries: list[Entry], title: str = "") -> None:
        super().__init__(app)
        self.at = at
        self.entries = [e for e in entries if e[0]]
        self.title = title
        self.selected = next((i for i, e in enumerate(self.entries) if e[1] is not None), 0)
        self.rect = (0, 0, 0, 0)

    def render(self, canvas: Canvas) -> None:
        width = max([markup.length(e[0]) for e in self.entries] + [markup.length(self.title)]) + 7
        width = min(width, canvas.width - 2)
        h = len(self.entries) + (3 if self.title else 2)
        x, y = self.at
        x = max(0, min(x, canvas.width - width))
        y = max(0, min(y, canvas.height - h))
        self.rect = (x, y, width, h)
        canvas.frame(x, y, width, h, "", style="glass")
        row = y + 1
        if self.title:
            canvas.markup(x + 2, row, f"<title>{markup.escape(self.title)}</>", max_width=width - 3)
            row += 1
        for i, (label, action, icon) in enumerate(self.entries):
            over = canvas.hit(x + 1, row, width - 2, 1, action=lambda i=i: self.choose(i))
            if over:
                self.selected = i
            if i == self.selected and action is not None:
                canvas.fill(x + 1, row, width - 2, 1, colors.HILITE_BG)
            canvas.icon(x + 1, row, f"icon/{icon}" if icon else "", "·" if not icon else "", colors.DIM)
            fg = colors.SELECT_FG if (i == self.selected and action) else (colors.FG if action else colors.FAINT)
            canvas.markup(x + 4, row, label, fg=fg, max_width=width - 5)
            row += 1
        canvas.hit(0, 0, canvas.width, canvas.height, action=self.close, right_action=self.close)

    def choose(self, i: int) -> None:
        if not 0 <= i < len(self.entries):
            return
        action = self.entries[i][1]
        if action is None:
            return
        self.close()
        action()

    def handle_key(self, ev: KeyEvent) -> bool:
        n = len(self.entries)
        if ev.key == "escape":
            self.close()
        elif ev.key == "up" and n:
            self.selected = (self.selected - 1) % n
        elif ev.key == "down" and n:
            self.selected = (self.selected + 1) % n
        elif ev.key == "enter":
            self.choose(self.selected)
        elif ev.is_text and ev.key.isdigit() and 0 < int(ev.key) <= n:
            self.choose(int(ev.key) - 1)
        return True

    def handle_mouse(self, ev: MouseEvent) -> bool:
        return False

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("down"), KeyEvent("enter"), KeyEvent("escape")]
