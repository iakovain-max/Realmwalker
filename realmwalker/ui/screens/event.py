"""Travel events: someone or something met on the road that is not (yet) a fight. And a small trade
window for travelling pedlars and hunters (towns get proper markets with M5)."""

from __future__ import annotations

from realmwalker.game import events as ev_logic
from realmwalker.rules.items import money_text
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen, modal_box
from realmwalker.ui.widgets import Canvas


class EventScreen(Screen):
    modal = True
    title = "On the road"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game
        self.ev = game.event
        self.shops: dict[int, dict] = {}  # option index -> remaining stock

    def choose(self, i: int) -> None:
        game = self.game
        if self.ev.done:
            self.finish()
            return
        opts = ev_logic.options(game, self.ev)
        if not 0 <= i < len(opts):
            return
        label, ok, why = opts[i]
        if not ok:
            self.app.notify(f"You can't: {why}.", "warn")
            return
        shop = ev_logic.choose(game, self.ev, i)
        if shop is not None:
            stock = self.shops.setdefault(i, {item: int(qty) for item, qty in shop["stock"]})
            self.app.push(TradeScreen(self.app, game, stock, float(shop["markup"]),
                                      game.tables.travel_events[self.ev.event_id]["name"]))

    def finish(self) -> None:
        self.game.event = None
        self.app.save_game()
        self.close()

    def handle_key(self, ev: KeyEvent) -> bool:
        if self.ev.done:
            if ev.key in ("enter", "escape", " "):
                self.finish()
            return True
        if ev.is_text and ev.key.isdigit():
            self.choose(int(ev.key) - 1)
        return True

    def render(self, canvas: Canvas) -> None:
        game = self.game
        spec = game.tables.travel_events[self.ev.event_id]
        width = min(76, canvas.width - 4)
        iw = width - 4
        intro = markup.wrap(markup.escape(self.ev.intro), iw)
        body_lines = []
        if self.ev.done:
            for m in self.ev.result:
                body_lines += markup.wrap(m, iw)
        opts = ev_logic.options(game, self.ev)
        from realmwalker.ui.screens.beat import PICTURE_ROWS, backdrop_for, picture

        pic = spec.get("picture") if backdrop_for(game, spec.get("picture")) and canvas.height >= 40 else None
        pic_rows = PICTURE_ROWS + 1 if pic else 0  # (what you came upon, as a picture above the words)
        height = len(intro) + len(body_lines) + (len(opts) if not self.ev.done else 1) + 8 + pic_rows
        title = spec["name"][:1].upper() + spec["name"][1:]
        x, y, w, h = modal_box(canvas, width, height, title)
        row = y + 2
        if pic:
            canvas.clear_cells(x + 2, row, iw, PICTURE_ROWS)
            picture(canvas, game, pic, (x + 2, row, iw, PICTURE_ROWS))
            row += pic_rows
        for line in intro:
            canvas.spans(x + 2, row, line, max_width=iw)
            row += 1
        row += 1
        if self.ev.done:
            for line in body_lines:
                canvas.spans(x + 2, row, line, max_width=iw)
                row += 1
            canvas.button(x + 2, y + h - 2, "Continue", self.finish, hotkey="Enter")
        else:
            for i, (label, ok, why) in enumerate(opts):
                if ok:
                    canvas.button(x + 2, row, label, lambda i=i: self.choose(i), hotkey=str(i + 1))
                else:
                    canvas.markup(x + 2, row, f"<faint>[{i + 1}] {markup.escape(label)}: {why}</>", max_width=iw)
                row += 1
            canvas.markup(x + 2, y + h - 2, f"<dim>Money:</> <loot>{money_text(ev_logic.party_money(game))}</>",
                          max_width=iw)
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        if self.ev.done:
            return [KeyEvent("enter")]
        return [KeyEvent(str(i)) for i in range(1, 5)]


class TradeScreen(Screen):
    """Buying from a travelling seller. Selling and real markets arrive with towns (M5)."""

    modal = True
    title = "Trade"

    def __init__(self, app, game, stock: dict, markup_: float, seller: str) -> None:
        super().__init__(app)
        self.game = game
        self.stock = stock
        self.markup = markup_
        self.seller = seller
        self.selected = 0
        self.message = ""

    def rows(self) -> list[str]:
        return [item for item in self.stock]

    def buy(self, i: int | None = None) -> None:
        rows = self.rows()
        if not rows:
            return
        i = self.selected if i is None else i
        self.selected = i
        self.message = ev_logic.buy(self.game, rows[i], self.markup, self.stock)
        self.game.say(self.message, "loot")

    def handle_key(self, ev: KeyEvent) -> bool:
        rows = self.rows()
        if ev.key in ("escape",):
            self.close()
        elif ev.key == "up" and rows:
            self.selected = (self.selected - 1) % len(rows)
        elif ev.key == "down" and rows:
            self.selected = (self.selected + 1) % len(rows)
        elif ev.key in ("enter", "b"):
            self.buy()
        return True

    def render(self, canvas: Canvas) -> None:
        game = self.game
        rows = self.rows()
        width = min(72, canvas.width - 4)
        x, y, w, h = modal_box(canvas, width, len(rows) + 9, f"Buying from {self.seller}")
        canvas.text(x + 2, y + 2, f"{'Item':<34}{'Price':>12}{'Left':>6}", colors.DIM)
        for i, item in enumerate(rows):
            ry = y + 3 + i
            selected = i == self.selected
            over = canvas.hit(x + 2, ry, w - 4, 1, action=lambda i=i: self.buy(i))
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            if bg:
                canvas.fill(x + 2, ry, w - 4, 1, bg)
            name = game.tables.items.get(item)["name"]
            price = money_text(ev_logic.shop_price(game, item, self.markup))
            left = self.stock[item]
            fg = colors.SELECT_FG if selected else (colors.FG if left else colors.FAINT)
            canvas.text(x + 2, ry, f"{name[:33]:<34}{price:>12}{left:>6}", fg, bg)
        canvas.markup(x + 2, y + h - 4, f"<dim>Your money:</> <loot>{money_text(ev_logic.party_money(game))}</>  "
                                        f"<dim>{markup.escape(self.message)}</>", max_width=w - 4)
        bx = canvas.button(x + 2, y + h - 2, "Buy", self.buy, hotkey="Enter")
        canvas.button(bx + 3, y + h - 2, "Done", self.close, hotkey="Esc")
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "enter", "up", "enter", "escape")]
