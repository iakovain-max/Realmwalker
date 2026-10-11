"""The Expansions screen (E on the title screen, or a click on the shelf): every released expansion, its icon and its
whole text — what it adds, what it counts, its version and date."""

from __future__ import annotations

from realmwalker import expansions as exp
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas


class ExpansionsScreen(Screen):
    title = "Expansions"
    sound_open = "ui_page"

    def __init__(self, app, focus: str | None = None) -> None:
        super().__init__(app)
        self.items = exp.released(app.data)
        self.offset = 0
        self._page = 10
        self._rows = 0
        self._focus = focus  # an expansion to open the page at (the one clicked on the shelf)
        self.app.settings.expansions_seen = sorted(set(self.app.settings.expansions_seen) | {e.id for e in self.items})
        self.app.save_settings()

    def music(self) -> str | None:
        return "title"

    def scroll(self, dy: int) -> None:
        self.offset = max(0, min(max(0, self._rows - self._page), self.offset + dy))

    def blocks(self, width: int) -> list[tuple[exp.Expansion, list]]:
        """Each expansion and its text, wrapped to `width` cells (lines of coloured spans)."""
        out = []
        for e in self.items:
            text = [f"<title>{markup.escape(e.name)}</>", f"<dim>{markup.escape(e.tagline)}</>"]
            if e.adds:
                text.append("<loot>Adds:</>")
                text += [f"· {markup.escape(a)}" for a in e.adds]
            if e.counts:
                text.append(f"<dim>{markup.escape(' · '.join(e.counts))}</>")
            if e.when():
                text.append(f"<faint>{markup.escape(e.when())}</>")
            lines: list = []
            for t in text:
                lines += markup.wrap(t, width) or [[]]
            out.append((e, lines))
        return out

    def render(self, canvas: Canvas) -> None:
        from realmwalker.ui.gfx.scene import Rect

        w, h = canvas.width, canvas.height
        width = min(100, w - 2)
        x0 = (w - width) // 2
        canvas.frame(x0, 0, width, h - 1, self.title, double=True)
        top, bottom = 2, h - 4
        self._page = max(1, bottom - top)
        if not self.items:
            canvas.wrapped(x0 + 3, top + 1, "<dim>No expansions have come out yet. When one does, its icon appears on the "
                                            "right of the main menu, and it is described here.</>", width - 6)
        text_x, text_w = x0 + 9, width - 12
        rows: list[tuple[exp.Expansion | None, list, bool]] = []
        for e, lines in self.blocks(text_w):
            for i, line in enumerate(lines):
                rows.append((e, line, i == 0))
            rows.append((None, [], False))
        self._rows = len(rows)
        if self._focus is not None:
            first = next((i for i, (e, _, start) in enumerate(rows) if start and e is not None and e.id == self._focus), 0)
            self.offset, self._focus = first, None
        self.scroll(0)
        canvas.hit(x0, top, width, self._page, wheel=lambda dy: self.scroll(-dy * 3))
        cw, ch = canvas.cell_w, canvas.cell_h
        for i, (e, line, start) in enumerate(rows[self.offset:self.offset + self._page]):
            y = top + i
            if start and e is not None:
                r, g, b = e.accent
                size = min(3 * ch, 6 * cw) - 4
                px, py = (x0 + 2) * cw, y * ch + 2
                canvas.clear_cells(x0 + 2, y, 6, 3)
                canvas.under(Rect(px, py, size, size, (20, 18, 22, 230)), Rect(px, py, size, size, (r, g, b, 255), line=2))
                inner = size - 8
                if not canvas.sprite(e.icon, px + 4, py + 4, inner, inner):
                    canvas.under(Rect(px + size / 2 - 6, py + size / 2 - 6, 12, 12, (r, g, b, 255)))
            canvas.spans(text_x, y, line, max_width=text_w)
        canvas.button(x0 + 2, h - 3, "Back", self.close, hotkey="Esc")
        canvas.text(x0 + 12, h - 3, "↑↓ PgUp PgDn scroll", colors.FAINT)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "e", "E"):
            self.close()
            return True
        step = {"up": -1, "down": 1, "pageup": -self._page, "pagedown": self._page, "home": -10**6, "end": 10**6}
        if ev.key in step:
            self.scroll(step[ev.key])
            return True
        return False

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("down"), KeyEvent("pagedown"), KeyEvent("escape")]
