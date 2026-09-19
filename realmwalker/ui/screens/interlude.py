"""'While you were away': what changed in a world between one life and the next (game/interlude.py)."""

from __future__ import annotations

from realmwalker.ui import colors
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen, modal_box
from realmwalker.ui.widgets import Canvas, ScrollText


class InterludeScreen(Screen):
    modal = True
    title = "The world moved on"

    def __init__(self, app, game, summary: dict) -> None:
        super().__init__(app)
        self.game = game
        self.summary = summary
        from realmwalker.game import interlude

        self.view = ScrollText("\n".join(interlude.summary_text(game.world, game.tables, summary)))

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "enter", "space"):
            self.close()
            return True
        return self.view.handle_key(ev)

    def render(self, canvas: Canvas) -> None:
        width = min(84, canvas.width - 4)
        height = min(canvas.height - 2, 28)
        x, y, w, h = modal_box(canvas, width, height, "The world moved on without you")
        self.view.render(canvas, x + 2, y + 2, w - 4, h - 5)
        canvas.button(x + 2, y + h - 2, "Walk into it", self.close, hotkey="Enter")
        canvas.text(x + 20, y + h - 2, "↑↓ PgUp PgDn scroll", colors.FAINT)
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("down"), KeyEvent("pagedown"), KeyEvent("enter")]
