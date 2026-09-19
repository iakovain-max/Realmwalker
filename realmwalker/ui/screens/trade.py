"""Trade and service windows opened from a conversation: the market (buy and sell) and, from
M5 part 4, services."""

from __future__ import annotations

from realmwalker.game import economy
from realmwalker.rules.character import Sheet
from realmwalker.rules.items import money_text
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas


def open_request(screen, request: str, choice) -> None:
    """Open the window a conversation asked for."""
    if request == "trade":
        screen.app.push(MarketScreen(screen.app, screen.game, screen.npc))
    elif request == "services":
        from realmwalker.ui.screens.services import ServicesScreen

        screen.app.push(ServicesScreen(screen.app, screen.game, screen.npc, screen.conv))


class MarketScreen(Screen):
    title = "Trade"

    def __init__(self, app, game, npc) -> None:
        super().__init__(app)
        self.game = game
        self.npc = npc
        self.side = 0  # 0 their goods, 1 yours
        self.sel = [0, 0]
        self.offset = [0, 0]
        self.message = ""

    # ------------------------------------------------------------------ rows
    def theirs(self) -> list[dict]:
        return economy.listing(self.game, self.npc)

    def yours(self) -> list[tuple]:
        """(item, price or None, why) for everything in the leader's pack."""
        c = self.game.leader
        out = []
        for it in sorted(c.inventory, key=lambda i: (self.game.tables.items.category(i), self.game.tables.items.name(i))):
            price, why = economy.sell_price(self.game, self.npc, it)
            if c.slot_of(it.uid) is not None and it.qty <= 1:
                price, why = None, "you are wearing it"
            out.append((it, price, why))
        return out

    # ------------------------------------------------------------------ actions
    def act(self) -> None:
        if self.side == 0:
            rows = self.theirs()
            if not rows:
                return
            r = rows[min(self.sel[0], len(rows) - 1)]
            self.message = economy.buy(self.game, self.npc, r["item_id"], r["used"])
        else:
            rows = self.yours()
            if not rows:
                return
            it, price, why = rows[min(self.sel[1], len(rows) - 1)]
            self.message = economy.sell(self.game, self.npc, self.game.leader, it.uid, 1) if price is not None else \
                f"{self.npc.first_name} won't buy that: {why}."
        self.game.say(self.message, "loot")
        self.clamp()

    def haggle(self) -> None:
        self.message = economy.haggle(self.game, self.npc)
        self.game.say(self.message, "info")

    def clamp(self) -> None:
        n = [len(self.theirs()), len(self.yours())]
        for i in (0, 1):
            self.sel[i] = max(0, min(self.sel[i], n[i] - 1))

    def click(self, side: int, i: int) -> None:
        if self.side == side and self.sel[side] == i:
            self.act()
        self.side = side
        self.sel[side] = i

    # ------------------------------------------------------------------ input
    def handle_key(self, ev: KeyEvent) -> bool:
        n = len(self.theirs()) if self.side == 0 else len(self.yours())
        if ev.key == "escape":
            self.close()
        elif ev.key in ("tab", "left", "right"):
            self.side = 1 - self.side
        elif ev.key == "up":
            self.sel[self.side] = max(0, self.sel[self.side] - 1)
        elif ev.key == "down":
            self.sel[self.side] = min(max(0, n - 1), self.sel[self.side] + 1)
        elif ev.key == "pageup":
            self.sel[self.side] = max(0, self.sel[self.side] - 10)
        elif ev.key == "pagedown":
            self.sel[self.side] = min(max(0, n - 1), self.sel[self.side] + 10)
        elif ev.key == "enter":
            self.act()
        elif ev.key in ("h", "H"):
            self.haggle()
        elif ev.key in ("s", "S") and self.side == 0:
            self.steal()
        return True

    def steal(self) -> None:
        """Palm one of their goods (Sleight of Hand). Being caught is a crime."""
        from realmwalker.game import law

        rows = self.theirs()
        if not rows or not self.game.world.factions:
            return
        r = rows[min(self.sel[0], len(rows) - 1)]
        if r["used"] is not None:
            self.message = "Second-hand goods are kept behind the counter."
            return
        ok, self.message = law.steal_from_shop(self.game, self.npc, r["item_id"])
        self.game.say(self.message, "loot" if ok else "danger")
        self.clamp()
        if not ok or self.game.arrest is not None:
            self.close()

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        game = self.game
        npc = self.npc
        w, h = canvas.width, canvas.height
        spec = economy.shop_spec(game, npc)
        shop = economy.shop_state(game, npc)
        canvas.frame(0, 0, w, h - 1, f"Trade — {markup.escape(npc.label())}: {spec['name']}", double=True)
        from realmwalker.game.events import party_money

        s = Sheet(game.leader, game.tables)
        haggle = economy.haggle_bonus(game, npc, shop)
        head = (f"<dim>Your money:</> <loot>{money_text(party_money(game))}</>   <dim>Their coin:</> "
                f"<loot>{money_text(shop['coin'])}</>   <dim>Load:</> {s.load():g} / {s.capacity()[0]:g} lb")
        if haggle:
            head += f"   <good>haggled: {int(haggle * 100)}% better</>"
        canvas.markup(2, 1, head, max_width=w - 4)
        col_w = (w - 5) // 2
        rows_h = h - 9
        self._column(canvas, 2, 3, col_w, rows_h, 0, "Their goods", [
            (r["name"] + (f" ×{r['qty']}" if r["qty"] > 1 and r["used"] is None else ""), money_text(r["price"]), True)
            for r in self.theirs()])
        self._column(canvas, 3 + col_w, 3, col_w, rows_h, 1, "Your goods (what they'd pay)", [
            (game.tables.items.name(it), money_text(price) if price is not None else "—", price is not None)
            for it, price, why in self.yours()])
        # The selected thing.
        from realmwalker.ui.screens.sheets import item_details

        detail = ""
        if self.side == 0:
            rows = self.theirs()
            if rows:
                r = rows[min(self.sel[0], len(rows) - 1)]
                from realmwalker.rules.items import Item

                detail = item_details(game, Item(0, r["item_id"]))
        else:
            rows = self.yours()
            if rows:
                it, price, why = rows[min(self.sel[1], len(rows) - 1)]
                detail = item_details(game, it) + ("" if price is not None else f"\n<warn>They won't buy it: {why}.</>")
        canvas.hline(1, h - 6, w - 2, "─", colors.FAINT)
        canvas.wrapped(2, h - 5, detail.split("\n")[0] + (" · " + detail.split("\n")[1] if "\n" in detail else ""), w - 4,
                       max_lines=1)
        if self.message:
            canvas.markup(2, h - 4, markup.escape(self.message) if "<" not in self.message else self.message,
                          max_width=w - 4)
        bx = canvas.button(2, h - 3, "Buy" if self.side == 0 else "Sell", self.act, hotkey="Enter")
        bx = canvas.button(bx + 3, h - 3, "Switch side", lambda: self.handle_key(KeyEvent("tab")), hotkey="Tab")
        if shop.get("haggle_day") != game.moment.total_days:
            bx = canvas.button(bx + 3, h - 3, "Haggle", self.haggle, hotkey="h")
        if self.side == 0 and game.world.factions:
            bx = canvas.button(bx + 3, h - 3, "Steal", self.steal, hotkey="s",
                               tooltip="Sleight of Hand. Being caught is a crime.")
        canvas.button(bx + 3, h - 3, "Back", self.close, hotkey="Esc")

    def _column(self, canvas: Canvas, x: int, y: int, w: int, h: int, side: int, title: str, rows: list) -> None:
        active = self.side == side
        canvas.text(x, y, title, colors.TITLE if active else colors.DIM, max_width=w)
        if not rows:
            canvas.text(x, y + 2, "Nothing.", colors.DIM)
            return
        sel = min(self.sel[side], len(rows) - 1)
        if sel < self.offset[side]:
            self.offset[side] = sel
        if sel >= self.offset[side] + h - 1:
            self.offset[side] = sel - h + 2
        for row, (label, price, ok) in enumerate(rows[self.offset[side]:self.offset[side] + h - 1]):
            i = row + self.offset[side]
            ry = y + 1 + row
            selected = active and i == sel
            over = canvas.hit(x, ry, w, 1, action=lambda s=side, i=i: self.click(s, i))
            bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
            if bg:
                canvas.fill(x, ry, w, 1, bg)
            fg = colors.SELECT_FG if selected else (colors.FG if ok else colors.FAINT)
            canvas.text(x, ry, label[: w - 12], fg, bg)
            canvas.text(x + w - len(price), ry, price, colors.named("loot") if ok else colors.FAINT, bg)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "enter", "tab", "down", "enter", "up", "h", "escape")]
