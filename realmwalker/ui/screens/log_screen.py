"""The full message log, newest at the bottom, with the time each thing happened."""

from __future__ import annotations

from realmwalker.game.state import GameState
from realmwalker.ui import colors
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas, ScrollText


class LogScreen(Screen):
    title = "Message log"

    def __init__(self, app, game: GameState) -> None:
        super().__init__(app)
        cal = game.tables.calendar
        lines = []
        for m in game.log.messages:
            t = cal.at(m.time)
            stamp = f"<faint>{t.day:>2} {t.month.name[:4]} {t.time_text()}</> "
            count = f" <dim>(×{m.count})</>" if m.count > 1 else ""
            lines.append(f"{stamp}<{m.color}>{m.text}</>{count}")
        self.view = ScrollText("\n".join(lines) or "<dim>Nothing has happened yet.</>")
        self.view.offset = 10**6

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, self.title, double=True)
        self.view.render(canvas, 2, 2, w - 4, h - 5)
        canvas.button(2, h - 3, "Back", self.close, hotkey="Esc")
        canvas.text(12, h - 3, "↑↓ PgUp PgDn scroll", colors.FAINT)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "L", "enter"):
            self.close()
            return True
        return self.view.handle_key(ev)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("pageup"), KeyEvent("down"), KeyEvent("escape")]
