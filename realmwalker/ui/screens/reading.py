"""The Reading's screen (Expansion 6 F.4, docs/ADVENTURES.md §5.7): the cards laid at the seer's fire as a picture
(ui/gfx/cards.py), and beneath it the card you point at - its place in the reading, its name and what it means, the
minor card across it, and the riddle. Arrows (or 1-5, Tab, a click) choose a card; Enter or Escape closes. The
journal keeps every riddle (story/reading.journal_lines)."""

from __future__ import annotations

from realmwalker.game.story import beats
from realmwalker.game.story import reading as rd
from realmwalker.ui import markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen, modal_box
from realmwalker.ui.widgets import Canvas

ORDER = ("key", "hand", "shadow", "door", "turn")
MOVES = {"left": {"turn": "key", "hand": "turn", "shadow": "key", "door": "key", "villain": "shadow"},
         "right": {"key": "turn", "turn": "hand", "shadow": "hand", "door": "hand"},
         "up": {"turn": "shadow", "door": "turn", "key": "shadow", "hand": "shadow"},
         "down": {"shadow": "turn", "turn": "door", "key": "door", "hand": "door", "villain": "hand"}}


class ReadingScreen(Screen):
    """The cards on the cloth, and the riddles."""

    modal = True
    title = "The cards"
    sound_open = "ui_page"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        d = beats.director(game.world)
        self.adv = game.world.politics.get("adventures", {}).get((d.get("reading") or {}).get("adv") or "")
        rec = rd.record(self.adv) or {}
        self.rec = rec
        laid = [p for p in ORDER if p in rec.get("cards", {})]
        self.chosen = laid[0] if laid else "key"
        if rec.get("villain") and rec.get("times", 1) == 1:
            self.chosen = "key"

    def music(self) -> str | None:
        return "story/omen"

    def finish(self) -> None:
        beats.director(self.game.world)["reading"] = None
        self.app.save_game()
        self.close()

    def choose(self, pos: str) -> None:
        self.chosen = pos

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("enter", "escape"):
            self.finish()
        elif ev.key in MOVES:
            nxt = MOVES[ev.key].get(self.chosen)
            if ev.key == "right" and self.chosen in ("hand", "shadow") and self.rec.get("villain"):
                nxt = "villain"
            if nxt:
                self.chosen = nxt
        elif ev.key == "tab":
            seq = list(ORDER) + (["villain"] if self.rec.get("villain") else [])
            i = seq.index(self.chosen) if self.chosen in seq else -1
            self.chosen = seq[(i + (-1 if ev.shift else 1)) % len(seq)]
        elif ev.is_text and ev.key.isdigit() and 1 <= int(ev.key) <= len(ORDER):
            self.chosen = ORDER[int(ev.key) - 1]
        return True

    def ui_state(self):
        return self.chosen

    def words(self) -> list[str]:
        """The chosen card in words (marked up)."""
        game, rec = self.game, self.rec
        sp = rd.spec(game)
        if self.chosen == "villain" and rec.get("villain"):
            v = rec["villain"]
            deck = sp["great"][v["card"]]
            return [f"<danger>{markup.escape(rd._cap(deck['name']))}, reversed</> <dim>- its own card. "
                    f"{markup.escape(deck['meaning'])}.</>", "", f"<danger>{markup.escape(v['voice'])}</>"]
        c = rec.get("cards", {}).get(self.chosen)
        pos = sp["positions"][self.chosen]
        head = f"<title>{markup.escape(pos['name'])}</> <dim>- {markup.escape(pos['asks'])}</>"
        if c is None:
            return [head, "", "<faint>Not laid.</>"]
        if c["silent"]:
            return [head, "", "<faint>The card lies face down.</>", "", markup.escape(c["riddle"])]
        deck = sp["great"][c["card"]]
        minor = rd.minor_name(game, c["minor"])
        crossed = f"crossed by the {minor} ({rd.minor_means(game, c['minor'])})"
        return [head, "",
                f"<good>{markup.escape(rd._cap(deck['name']))}</>, {markup.escape(crossed)}. "
                f"<dim>{markup.escape(rd._cap(deck['meaning']))}.</>", "",
                f"<story>{markup.escape(c['riddle'])}</>"]

    def render(self, canvas: Canvas) -> None:
        if self.adv is None or not self.rec:
            self.finish()
            return
        width = min(84, canvas.width - 4)
        iw = width - 6
        text: list[str] = []
        for line in self.words():
            text += markup.wrap(line, iw) if line else [""]
        pic_rows = max(10, min(20, canvas.height - len(text) - 10))
        x, y, w, h = modal_box(canvas, width, pic_rows + len(text) + 7,
                               f"The cards - {self.rec.get('seer', 'the seer')}")
        canvas.clear_cells(x + 2, y + 2, w - 4, pic_rows)
        px = canvas.cell_rect(x + 2, y + 2, w - 4, pic_rows)
        from realmwalker.ui.gfx import cards

        spots = cards.table(canvas, self.game, px, self.rec, canvas.now, self.chosen)
        cw, ch = canvas.cell_w, canvas.cell_h
        for pos, (sx, sy, sw, sh) in spots.items():  # (a click on a card chooses it)
            canvas.hit(int(sx // cw), int(sy // ch), max(1, round(sw / cw)), max(1, round(sh / ch)),
                       lambda p=pos: self.choose(p))
        row = y + 3 + pic_rows
        for line in text:
            canvas.spans(x + 3, row, line, max_width=iw)
            row += 1
        canvas.markup(x + 3, y + h - 3, "<faint>Arrows or 1-5: another card.  The journal keeps every riddle.</>",
                      max_width=iw)
        canvas.button(x + 3, y + h - 2, "Done", self.finish, hotkey="Enter")
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("right"), KeyEvent("down"), KeyEvent("enter")]
