"""Services offered by a townsperson: beds, meals, baths, healing, prayers, repairs, animals, work."""

from __future__ import annotations

from realmwalker.game import services
from realmwalker.rules.items import money_text
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen, modal_box
from realmwalker.ui.widgets import Canvas


class ServicesScreen(Screen):
    modal = True
    title = "Services"

    def __init__(self, app, game, npc, conv=None) -> None:
        super().__init__(app)
        self.game = game
        self.npc = npc
        self.conv = conv
        self.sub = None  # the service whose options are being chosen
        self.messages: list[str] = []
        self.cur = 0  # the row under the cursor (arrows, Enter), and the first row shown (a long list scrolls)
        self.top = 0
        self.shown = 9

    def _open(self, sub) -> None:
        self.sub = sub
        self.cur = self.top = 0

    def scroll(self, delta: int) -> None:
        n = len(self.entries())
        self.cur = max(0, min(n - 1, self.cur + delta)) if n else 0
        self.top = max(0, min(self.top, self.cur, max(0, n - self.shown)))
        if self.cur >= self.top + self.shown:
            self.top = self.cur - self.shown + 1

    def tip(self, key: str):
        """A spell's card for a line of the spellcasting list (a spell id before the "|")."""
        if self.sub is None or self.sub.id != "spellcasting":
            return None
        sid = key.split("|")[0]
        if sid not in self.game.tables.spells:
            return None
        from realmwalker.rules import describe

        return lambda: describe.spell(self.game.tables, sid)

    def entries(self) -> list:
        if self.sub is not None:
            purse = services.money(self.game)
            return [(arg, f"{label}" + (f" <loot>{money_text(price)}</>" if price else ""), purse >= price,
                     f"you need {money_text(price)}") for arg, label, price in self.sub.options]
        return [(s.id, s.label + (f" <loot>{money_text(s.price)}</>" if s.price else ""), s.enabled, s.why)
                for s in services.services_for(self.game, self.npc)]

    def pick(self, i: int) -> None:
        rows = self.entries()
        if not 0 <= i < len(rows):
            return
        key, label, ok, why = rows[i]
        if not ok:
            self.app.notify(f"You can't: {why}.", "warn")
            return
        if self.sub is None:
            svc = next(s for s in services.services_for(self.game, self.npc) if s.id == key)
            if svc.options:
                self._open(svc)
                return
            where = (self.game.player.x, self.game.player.y)
            msgs = services.perform(self.game, self.npc, key)
        else:
            where = (self.game.player.x, self.game.player.y)
            msgs = services.perform(self.game, self.npc, self.sub.id, key)
            self._open(None)
        for m in msgs:
            self.game.say(m, "info")
            if self.conv is not None:
                self.conv.note(m)
        self.messages = (self.messages + msgs)[-5:]
        self.app.save_game()
        if self.game.busy or where != (self.game.player.x, self.game.player.y):  # (a fight; or the coach left)
            while self.app.top is not None and type(self.app.top).__name__ != "GameScreen":
                self.app.pop()

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "escape":
            if self.sub is not None:
                self._open(None)
            else:
                self.close()
        elif ev.key in ("up", "down", "pageup", "pagedown", "home", "end"):
            step = {"up": -1, "down": 1, "pageup": -self.shown, "pagedown": self.shown, "home": -10 ** 6,
                    "end": 10 ** 6}[ev.key]
            self.scroll(step)
        elif ev.key in ("enter", "kp_enter"):
            self.pick(self.cur)
        elif ev.is_text and ev.key.isdigit() and ev.key != "0" and int(ev.key) <= min(9, self.shown):
            self.pick(self.top + int(ev.key) - 1)  # (only the rows on screen)
        return True

    def render(self, canvas: Canvas) -> None:
        rows = self.entries()
        width = min(84, canvas.width - 4)
        iw = width - 4
        msg_lines = []
        for m in self.messages[-3:]:
            msg_lines += markup.wrap(m, iw)
        title = self.sub.label if self.sub is not None else f"What {self.npc.first_name} can do for you"
        self.shown = max(3, min(len(rows), canvas.height - len(msg_lines) - 12))
        self.scroll(0)
        more = len(rows) > self.shown
        x, y, w, h = modal_box(canvas, width, min(len(rows), self.shown) + len(msg_lines) + 8 + (2 if more else 0),
                               markup.escape(title))
        from realmwalker.game.events import party_money

        canvas.markup(x + 2, y + 2, f"<dim>Your money:</> <loot>{money_text(party_money(self.game))}</>", max_width=iw)
        row = y + 4
        if not rows:
            canvas.text(x + 2, row, "Nothing, just now.", colors.DIM)
            row += 1
        if more:
            canvas.text(x + 2, row, "▲ more above" if self.top > 0 else "", colors.FAINT)
            row += 1
        canvas.hit(x, row, w, self.shown, wheel=lambda dy: self.scroll(-dy * 3))
        for i, (key, label, ok, why) in enumerate(rows):
            if not self.top <= i < self.top + self.shown:
                continue
            hk = str(i - self.top + 1) if i - self.top < 9 else " "
            if i == self.cur:
                canvas.text(x + 1, row, "›", colors.TITLE)
            if ok:
                price_tag = label.split("<loot>")[-1].split("</>")[0] if "<loot>" in label else ""
                # The price goes in its own column, once, not also at the end of the words.
                words = markup.plain(label.rsplit("<loot>", 1)[0]).rstrip(" ·:,") if price_tag else markup.plain(label)
                canvas.button(x + 2, row, words, lambda i=i: self.pick(i), hotkey=hk,
                              max_width=iw - (len(price_tag) + 2 if price_tag else 0))
                if price_tag:
                    canvas.text(x + w - 3 - len(price_tag), row, price_tag, colors.named("loot"))
            else:
                canvas.markup(x + 2, row, f"<faint>[{hk}] {markup.escape(markup.plain(label))}: {why}</>", max_width=iw)
            card = self.tip(key)
            if card is not None:  # (the whole line clicks as the button does, and shows the spell's card)
                canvas.hit(x + 2, row, iw, 1, (lambda i=i: self.pick(i)) if ok else None, card)
            row += 1
        if more:
            canvas.text(x + 2, row, "▼ more below" if self.top + self.shown < len(rows) else "", colors.FAINT)
            row += 1
        row += 1
        for line in msg_lines:
            canvas.spans(x + 2, row, line, max_width=iw)
            row += 1
        canvas.text(x + 2, y + h - 2, "1-9 or ↑↓ Enter choose · Esc back", colors.FAINT)
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("1", "2", "3", "4", "escape")]
