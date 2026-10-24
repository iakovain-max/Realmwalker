"""The boss's card before the finale (Expansion 6, docs/ADVENTURES.md §5.8 rule 5): its name, its first words, and
what you know - each key found ticked, each unknown a question mark - then Fight, or Not yet."""

from __future__ import annotations

from realmwalker.game import story
from realmwalker.ui import markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen, modal_box
from realmwalker.ui.widgets import Canvas


class FinaleScreen(Screen):
    modal = True
    title = "The end of it"
    sound_open = "ui_open"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        self.card = story.finale_card(game)

    def music(self) -> str | None:
        return "story/finale"

    def fight(self) -> None:
        self.close()
        story.fight_finale(self.game)

    def not_yet(self) -> None:
        self.game.finale = None
        self.close()

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("enter", "f"):
            self.fight()
        elif ev.key in ("escape", "n"):
            self.not_yet()
        return True

    def render(self, canvas: Canvas) -> None:
        c = self.card
        if not c:
            self.not_yet()
            return
        width = min(70, canvas.width - 4)
        iw = width - 6
        first = markup.wrap(f"<dim>{markup.escape(c['first'])}</>", iw)
        rows = len(first) + len(c["known"]) + (2 if c["warning"] else 0) + 10
        x, y, w, h = modal_box(canvas, width, rows, c["title"])
        canvas.markup(x + 3, y + 2, f"<danger>{markup.escape(c['name'])}</>", max_width=iw)
        row = y + 4
        for line in first:
            canvas.spans(x + 3, row, line, max_width=iw)
            row += 1
        row += 1
        canvas.markup(x + 3, row, "<title>What you know</>", max_width=iw)
        row += 1
        for text, ok in c["known"]:
            mark = "<good>[x]</>" if ok else "<faint>[?]</>"
            canvas.markup(x + 3, row, f"{mark} {markup.escape(text) if ok else '<faint>something you did not find</>'}",
                          max_width=iw)
            row += 1
        if c["warning"]:
            row += 1
            canvas.markup(x + 3, row, f"<warn>This is a fight for a hero of level {c['level']} or more.</>",
                          max_width=iw)
        bx = canvas.button(x + 3, y + h - 2, "Fight", self.fight, hotkey="Enter")
        canvas.button(bx + 3, y + h - 2, "Not yet", self.not_yet, hotkey="Esc")
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("enter")]
