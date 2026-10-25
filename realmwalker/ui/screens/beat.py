"""The story's screens of words (Expansion 6, docs/ADVENTURES.md §8.7): a beat (pages, numbered choices with their
checks and costs, what came of it), with its picture above (ui/gfx/vignette.py). A chapter's title card is
ui/screens/titlecard.py."""

from __future__ import annotations

from realmwalker.game.story import beats
from realmwalker.ui import markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen, modal_box
from realmwalker.ui.widgets import Canvas

PICTURE_ROWS = 9  # (a beat's picture above its words: `picture` in beats.json)


def picture(canvas: Canvas, game, name: str, rect: tuple[float, float, float, float], rec: dict | None = None) -> bool:
    """Draw a beat's (or an event's) picture in a rect of cells: "camp_night" (the party round their own camp), a
    vignette's backdrop (ui/gfx/vignette.BACKDROPS), "place" (the backdrop of the step's place) or "here" (of where you
    stand). False when there is none by that name."""
    px = tuple(int(v) for v in canvas.cell_rect(*rect))
    if name == "camp_night":
        from realmwalker.ui.gfx import scenes

        scenes.camp(canvas, game, px, canvas.now)
        return True
    from realmwalker.ui.gfx import vignette

    backdrop = backdrop_for(game, name, rec)
    if backdrop is None:
        return False
    spec = {"backdrop": backdrop, "figures": vignette.party_figures(game, 1),
            "seed": int((rec or {}).get("n", 0))}
    return vignette.compose(canvas, px, spec, canvas.now, game)


def backdrop_for(game, name: str | None, rec: dict | None = None) -> str | None:
    """The vignette backdrop a picture's name stands for (None: no picture)."""
    from realmwalker.ui.gfx import vignette

    if not name:
        return None
    if name in vignette.BACKDROPS:
        return name
    if name == "place" and rec is not None:
        from realmwalker.game import story

        st = story.find_step(game, rec.get("adv"), rec.get("step"))
        place = ((st or {}).get("target") or {}).get("place") if st else None
        if place:
            return vignette.for_place(game, place)
        name = "here"
    if name == "here":
        p = game.player
        if game.in_local and game.local is not None and game.local.kind == "dungeon":
            site = game.world.site_at(p.x, p.y)
            return "hideout" if site is not None and vignette.is_hideout(game.world, site.id) else "barrow_hall"
        return vignette.for_place(game, {"tile": [p.x, p.y]})
    return None


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
        pic_rows = PICTURE_ROWS + 1 if pic == "camp_night" or backdrop_for(game, pic, self.rec) else 0
        height = len(body) + len(tail) + len(opts) + 8 + pic_rows
        x, y, w, h = modal_box(canvas, width, height, beats.title(game, self.rec) or self.title)
        row = y + 2
        if pic_rows:
            canvas.clear_cells(x + 2, row, iw, PICTURE_ROWS)
            picture(canvas, game, pic, (x + 2, row, iw, PICTURE_ROWS), self.rec)
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
