"""What became of them (Expansion 6, docs/ADVENTURES.md §5.9): one page for each thing the tale touched - the place,
the patron, the ally, the witness - and last, you, with the epithet the tale has given you to take or leave."""

from __future__ import annotations

from realmwalker.ui import markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen, modal_box
from realmwalker.ui.widgets import Canvas

ABOUT = {"place": "The place", "patron": "The one who asked", "ally": "The one who helped", "witness": "The one who saw",
         "innocent": "The ones it would have taken", "hero": "You"}


class EpilogueScreen(Screen):
    modal = True
    title = "What became of them"
    sound_open = "ui_page"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        rec = game.epilogue or {}
        self.adv = game.world.politics.get("adventures", {}).get(rec.get("adv"))
        self.pages = list(self.adv["epilogue"]) if self.adv else []
        self.offered = list(game.renown.legend.get("offered", []))
        self.page = 0

    def music(self) -> str | None:
        return "story/epilogue"

    @property
    def last(self) -> bool:
        return self.page >= len(self.pages) - 1

    def next_page(self) -> None:
        if not self.last:
            self.page += 1
        elif not self.offered:
            self.finish()

    def take(self, i: int | None) -> None:
        legend = self.game.renown.legend
        if i is not None and 0 <= i < len(self.offered):
            legend["epithet"] = self.offered[i]
            self.game.say(f"<good>They call you {markup.escape(self.offered[i])} now.</>", "story")
        legend["offered"] = []
        self.finish()

    def finish(self) -> None:
        self.game.epilogue = None
        self.app.save_game()
        self.close()

    def handle_key(self, ev: KeyEvent) -> bool:
        if not self.pages:
            self.finish()
            return True
        if self.last and self.offered:
            if ev.is_text and ev.key.isdigit() and 1 <= int(ev.key) <= len(self.offered):
                self.take(int(ev.key) - 1)
            elif ev.key in ("escape", "n"):
                self.take(None)
            return True
        if ev.key in ("enter", " ", "right", "escape"):
            self.next_page()
        return True

    def render(self, canvas: Canvas) -> None:
        if not self.pages:
            return
        page = self.pages[self.page]
        width = min(72, canvas.width - 4)
        iw = width - 6
        body = markup.wrap(markup.escape(page["text"]), iw)
        extra = len(self.offered) + 3 if self.last and self.offered else 0
        x, y, w, h = modal_box(canvas, width, len(body) + extra + 9, self.adv["title"] if self.adv else self.title)
        canvas.markup(x + 3, y + 2, f"<title>{ABOUT.get(page['about'], 'What became of them')}</>  "
                                    f"<dim>{self.page + 1} of {len(self.pages)}</>", max_width=iw)
        row = y + 4
        for line in body:
            canvas.spans(x + 3, row, line, max_width=iw)
            row += 1
        if self.last and self.offered:
            row += 1
            canvas.markup(x + 3, row, "<dim>They have started to call you something. Take it?</>", max_width=iw)
            row += 1
            for i, ep in enumerate(self.offered):
                canvas.button(x + 3, row, ep, lambda i=i: self.take(i), hotkey=str(i + 1))
                row += 1
            canvas.button(x + 3, y + h - 2, "No, my own name will do", lambda: self.take(None), hotkey="Esc")
        else:
            canvas.button(x + 3, y + h - 2, "Continue", self.next_page, hotkey="Enter")
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        if self.last and self.offered:
            return [KeyEvent("1")]
        return [KeyEvent("enter")]
