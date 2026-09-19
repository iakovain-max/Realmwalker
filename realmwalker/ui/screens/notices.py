"""Reading the notice board in a town square."""

from __future__ import annotations

from realmwalker.game import notices
from realmwalker.ui import colors
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen, modal_box
from realmwalker.ui.widgets import Canvas, ScrollText

COLORS = {"wanted": "danger", "proclamation": "info", "law": "warn", "local": "dim"}


class NoticeBoardScreen(Screen):
    modal = True
    title = "Notice board"

    def __init__(self, app, game, settlement) -> None:
        super().__init__(app)
        self.game = game
        self.settlement = settlement
        items = notices.read(game, settlement)
        lines = []
        for n in items:
            lines.append(f"<{COLORS.get(n['kind'], 'fg')}>{n['title']}</>  {n['text']}")
            lines.append("")
        if not items:
            lines = ["<dim>Old nails and torn corners. Nothing is posted here now.</>"]
        self.view = ScrollText("\n".join(lines))

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "enter", "space"):
            self.close()
            return True
        return self.view.handle_key(ev)

    def render(self, canvas: Canvas) -> None:
        width = min(84, canvas.width - 4)
        height = min(canvas.height - 2, 30)
        x, y, w, h = modal_box(canvas, width, height, f"The notice board in {self.settlement.name}")
        self.view.render(canvas, x + 2, y + 2, w - 4, h - 5)
        canvas.button(x + 2, y + h - 2, "Done", self.close, hotkey="Esc")
        canvas.text(x + 12, y + h - 2, "↑↓ PgUp PgDn scroll", colors.FAINT)
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("down"), KeyEvent("pagedown"), KeyEvent("escape")]
