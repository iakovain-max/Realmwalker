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

    def entries(self) -> list:
        if self.sub is not None:
            return [(arg, f"{label}" + (f" <loot>{money_text(price)}</>" if price else ""), True, "")
                    for arg, label, price in self.sub.options]
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
                self.sub = svc
                return
            msgs = services.perform(self.game, self.npc, key)
        else:
            msgs = services.perform(self.game, self.npc, self.sub.id, key)
            self.sub = None
        for m in msgs:
            self.game.say(m, "info")
            if self.conv is not None:
                self.conv.note(m)
        self.messages = (self.messages + msgs)[-5:]
        self.app.save_game()
        if self.game.busy:
            while self.app.top is not None and type(self.app.top).__name__ != "GameScreen":
                self.app.pop()

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "escape":
            if self.sub is not None:
                self.sub = None
            else:
                self.close()
        elif ev.is_text and ev.key.isdigit() and ev.key != "0":
            self.pick(int(ev.key) - 1)
        return True

    def render(self, canvas: Canvas) -> None:
        rows = self.entries()
        width = min(84, canvas.width - 4)
        iw = width - 4
        msg_lines = []
        for m in self.messages[-3:]:
            msg_lines += markup.wrap(m, iw)
        title = self.sub.label if self.sub is not None else f"What {self.npc.first_name} can do for you"
        x, y, w, h = modal_box(canvas, width, len(rows) + len(msg_lines) + 8, markup.escape(title))
        from realmwalker.game.events import party_money

        canvas.markup(x + 2, y + 2, f"<dim>Your money:</> <loot>{money_text(party_money(self.game))}</>", max_width=iw)
        row = y + 4
        if not rows:
            canvas.text(x + 2, row, "Nothing, just now.", colors.DIM)
            row += 1
        for i, (key, label, ok, why) in enumerate(rows):
            hk = str(i + 1) if i < 9 else " "
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
            row += 1
        row += 1
        for line in msg_lines:
            canvas.spans(x + 2, row, line, max_width=iw)
            row += 1
        canvas.text(x + 2, y + h - 2, "1-9 choose · Esc back", colors.FAINT)
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("1", "2", "3", "4", "escape")]
