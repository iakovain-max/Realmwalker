"""Shown at startup when a data file is missing or has mistakes, instead of crashing."""

from __future__ import annotations

from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas, ScrollText


class DataErrorScreen(Screen):
    title = "Problems in the game data"

    def __init__(self, app, errors: list[str]) -> None:
        super().__init__(app)
        body = [
            "The game found mistakes in its data files and cannot start safely. "
            "Nothing has been changed or lost. Fix the lines below (or restore the files) and start the game again.",
            "",
            f"<dim>Data folder:</> <place>{markup.escape(str(app.paths.data))}</>",
            "",
        ]
        body += [f"<danger>•</> {markup.escape(e)}" for e in errors]
        self.view = ScrollText("\n".join(body))

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, self.title, double=True, fg=colors.named("danger"))
        self.view.render(canvas, 2, 2, w - 4, h - 6)
        canvas.button(2, h - 3, "Quit", self.app.request_quit, hotkey="Q")

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("q", "Q", "escape"):
            self.app.request_quit()
            return True
        return self.view.handle_key(ev)
