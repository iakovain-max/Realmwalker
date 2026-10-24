"""A tale's title card (Expansion 6 B.2, docs/ADVENTURES.md §8.12): a chapter opens on a picture of its first place,
panning slowly with Animations on, the chapter's number and name in the title face across it and its first lines
beneath; the `chapter` sound. Any key goes on: it never holds the player longer than they wish."""

from __future__ import annotations

from realmwalker.game.story import beats
from realmwalker.ui import markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen, modal_box
from realmwalker.ui.widgets import Canvas

ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII")
PICTURE_ROWS = 12


def first_place(adv: dict, i: int) -> dict | None:
    """The chapter's first place: the first of its steps that has one."""
    for st in adv["chapters"][i]["steps"]:
        place = (st.get("target") or {}).get("place")
        if place:
            return place
    return None


class TitleCardScreen(Screen):
    """A tale begins, or a chapter of it: its place, its number and name, and how it opens."""

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
        self.finish()  # (any key goes on)
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
        width = min(76, canvas.width - 4)
        iw = width - 6
        wrapped = []
        for line in body:
            text = line if line.startswith("<") else markup.escape(line)
            wrapped += markup.wrap(text, iw) + [""]
        pic_rows = PICTURE_ROWS if canvas.height >= len(wrapped) + PICTURE_ROWS + 10 else 0
        x, y, w, h = modal_box(canvas, width, len(wrapped) + 7 + pic_rows + (0 if pic_rows else 4), name)
        from realmwalker.ui.gfx import theme, vignette
        from realmwalker.ui.gfx.scene import Rect, Sprite, Text

        title_size = int(canvas.cell_h * 1.5)
        if pic_rows:  # the chapter's place, and its name across the foot of the picture
            canvas.clear_cells(x + 2, y + 2, w - 4, pic_rows)
            px, py, pw, ph = canvas.cell_rect(x + 2, y + 2, w - 4, pic_rows)
            i = int(self.card.get("chapter", 0))
            spec = {"backdrop": vignette.for_place(self.game, first_place(self.adv, i)), "pan": True,
                    "figures": vignette.party_figures(self.game, 1), "figures_x": 0.24,
                    "seed": i + int(self.adv["id"][1:])}
            vignette.compose(canvas, (px, py, pw, ph), spec, canvas.now, self.game)
            band = title_size * 1.9
            canvas.under(Rect(px + 2, py + ph - band - 2, pw - 4, band, (0, 0, 0, 0), bottom=(8, 6, 4, 210)))
            seal = band * 0.9
            canvas.under(Sprite("map/story", px + pw - seal - 10, py + ph - band - 2 + (band - seal) / 2, seal, seal))
            canvas.under(Text(px + pw / 2, py + ph - band / 2 - 2, head, "title", title_size, (240, 212, 150, 255),
                              anchor="mm", shadow=True))
            row = y + 3 + pic_rows
        else:  # (a small window: the band alone, as before)
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
