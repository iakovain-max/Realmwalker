"""The story's screens of words (Expansion 6, docs/ADVENTURES.md §8.7): a beat (pages, numbered choices with their
checks and costs, what came of it) and a chapter's title card ("Chapter II - What Binds Him")."""

from __future__ import annotations

from realmwalker.game.story import beats
from realmwalker.ui import markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen, modal_box
from realmwalker.ui.widgets import Canvas

ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII")
PICTURE_ROWS = 9  # (a beat's picture above its words: `picture` in beats.json)


def picture(canvas: Canvas, game, name: str, rect: tuple[float, float, float, float]) -> bool:
    """Draw a beat's picture in a rect of cells; False when there is none by that name (Part B brings the rest)."""
    if name == "camp_night":
        from realmwalker.ui.gfx import scenes

        scenes.camp(canvas, game, tuple(int(v) for v in canvas.cell_rect(*rect)), canvas.now)
        return True
    return False


class BeatScreen(Screen):
    modal = True
    title = "A tale"
    sound_open = "ui_page"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        self.rec = beats.pending(game)
        self.pages = beats.pages(game, self.rec) if self.rec else []
        self.page = 0
        self.result: list[str] | None = None

    def music(self) -> str | None:
        return "story/omen"

    def choose(self, i: int) -> None:
        opts = beats.choices(self.game, self.rec)
        opt = next((o for o in opts if o["i"] == i), None)
        if opt is None:
            return
        if not opt["ok"]:
            self.app.notify(f"You can't: {opt['why']}.", "warn")
            return
        self.result = beats.choose(self.game, self.rec, i) or [""]
        for line in self.result:
            if line:
                self.game.say(line, "story")

    def finish(self) -> None:
        self.app.save_game()
        self.close()

    def handle_key(self, ev: KeyEvent) -> bool:
        if self.rec is None:
            self.close()
            return True
        if self.result is not None:
            if ev.key in ("enter", "escape", " "):
                self.finish()
            return True
        if self.page < len(self.pages) - 1:
            if ev.key in ("enter", " ", "right"):
                self.page += 1
            return True
        opts = beats.choices(self.game, self.rec)
        if ev.is_text and ev.key.isdigit() and 1 <= int(ev.key) <= len(opts):
            self.choose(opts[int(ev.key) - 1]["i"])
        elif ev.key == "enter" and len(opts) == 1:
            self.choose(opts[0]["i"])
        return True

    def render(self, canvas: Canvas) -> None:
        if self.rec is None:
            return
        game = self.game
        width = min(78, canvas.width - 4)
        iw = width - 4
        body = markup.wrap(markup.escape(self.pages[self.page]), iw) if self.pages else []
        tail: list[str] = []
        opts = beats.choices(game, self.rec) if self.result is None and self.page >= len(self.pages) - 1 else []
        if self.result is not None:
            for line in self.result:
                tail += markup.wrap(line, iw) if line else []
        pic = game.tables.beats.get(self.rec["beat"], {}).get("picture") if self.page == 0 else None
        pic_rows = PICTURE_ROWS + 1 if pic in ("camp_night",) else 0
        height = len(body) + len(tail) + len(opts) + 8 + pic_rows
        x, y, w, h = modal_box(canvas, width, height, beats.title(game, self.rec) or self.title)
        row = y + 2
        if pic_rows:
            canvas.clear_cells(x + 2, row, iw, PICTURE_ROWS)
            picture(canvas, game, pic, (x + 2, row, iw, PICTURE_ROWS))
            row += pic_rows
        for line in body:
            canvas.spans(x + 2, row, line, max_width=iw)
            row += 1
        row += 1
        if self.result is not None:
            for line in tail:
                canvas.spans(x + 2, row, line, max_width=iw)
                row += 1
            canvas.button(x + 2, y + h - 2, "Continue", self.finish, hotkey="Enter")
        elif self.page < len(self.pages) - 1:
            canvas.button(x + 2, y + h - 2, "Go on", self.next_page, hotkey="Enter")
        else:
            for n, opt in enumerate(opts):
                label = opt["label"]
                if opt["check"]:
                    skill = opt["check"]["skill"].replace("_", " ").capitalize()
                    label = f"[{skill} {opt['check']['dc']}] {label}"
                if opt["ok"]:
                    canvas.button(x + 2, row, label, lambda i=opt["i"]: self.choose(i), hotkey=str(n + 1))
                else:
                    canvas.markup(x + 2, row, f"<faint>[{n + 1}] {markup.escape(label)}: {opt['why']}</>",
                                  max_width=iw)
                row += 1
        canvas.hit(0, 0, canvas.width, canvas.height)

    def next_page(self) -> None:
        self.page = min(len(self.pages) - 1, self.page + 1)

    def autoplay_keys(self) -> list[KeyEvent]:
        if self.result is not None:
            return [KeyEvent("enter")]
        if self.page < len(self.pages) - 1:
            return [KeyEvent("enter")]
        return [KeyEvent(str(i)) for i in range(1, 4)]


class TitleCardScreen(Screen):
    """A tale begins, or a chapter of it: the chapter's number and name, and how it opens."""

    modal = True
    title = "A tale"
    sound_open = "chapter"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        d = beats.director(game.world)
        self.card = d.get("card") or {}
        self.adv = game.world.politics.get("adventures", {}).get(self.card.get("adv"))

    def music(self) -> str | None:
        return "story/omen"

    def finish(self) -> None:
        beats.director(self.game.world)["card"] = None
        self.app.save_game()
        self.close()

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("enter", "escape", " "):
            self.finish()
        return True

    def lines(self) -> tuple[str, str, list[str]]:
        adv = self.adv
        if adv is None:
            return "", "", []
        i = int(self.card.get("chapter", 0))
        ch = adv["chapters"][i]
        head = f"Chapter {ROMAN[i] if i < len(ROMAN) else i + 1} - {ch['title']}"
        body = []
        if i == 0:
            body.append(adv["words"]["hook"])
        body.append(ch["opening"])
        body.append(f"<dim>{markup.escape(ch['goal'])}</>")
        return adv["title"], head, body

    def render(self, canvas: Canvas) -> None:
        name, head, body = self.lines()
        if not name:
            self.finish()
            return
        width = min(70, canvas.width - 4)
        iw = width - 6
        wrapped = []
        for i, line in enumerate(body):
            text = line if line.startswith("<") else markup.escape(line)
            wrapped += markup.wrap(text, iw) + [""]
        x, y, w, h = modal_box(canvas, width, len(wrapped) + 11, name)
        # The card's frame: an inset band with the chapter's name set in it, and the tale's seal.
        from realmwalker.ui.gfx import theme
        from realmwalker.ui.gfx.scene import Sprite, Text

        canvas.clear_cells(x + 2, y + 2, w - 4, 3)
        bx, by, bw, bh = canvas.cell_rect(x + 2, y + 2, w - 4, 3)
        canvas.under(*theme.panel(bx, by, bw, bh, "inset", ornaments=True, border=True))
        seal = bh * 0.9
        canvas.under(Sprite("map/story", bx + bw - seal - 8, by + (bh - seal) / 2, seal, seal))
        canvas.under(Text(bx + (bw - seal) / 2, by + bh / 2, head, "heading", int(canvas.cell_h * 1.4),
                          (236, 206, 140, 255), anchor="mm", shadow=True))
        row = y + 6
        for line in wrapped:
            canvas.spans(x + 3, row, line, max_width=iw)
            row += 1
        canvas.button(x + 3, y + h - 2, "Begin", self.finish, hotkey="Enter")
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("enter")]
