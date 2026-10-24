"""Reading the notice board in a town square (and taking down a bounty)."""

from __future__ import annotations

from realmwalker.game import notices
from realmwalker.ui import colors
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen, modal_box
from realmwalker.ui.widgets import Canvas, ScrollText

COLORS = {"wanted": "danger", "proclamation": "info", "law": "warn", "local": "dim", "hook": "title", "hiring": "info"}


class NoticeBoardScreen(Screen):
    modal = True
    title = "Notice board"
    sound_open = "ui_map"

    def __init__(self, app, game, settlement) -> None:
        super().__init__(app)
        self.game = game
        self.settlement = settlement
        self.bounties: list[dict] = []
        self.view = ScrollText("")
        self.refresh()

    def refresh(self) -> None:
        items = notices.read(self.game, self.settlement)
        self.bounties = [n.get("bounty") or {"hook": n["hook"]} for n in items if n.get("bounty") or n.get("hook")]
        lines = []
        for n in items:
            lines.append(f"<{COLORS.get(n['kind'], 'fg')}>{n['title']}</>  {n['text']}")
            took = n.get("bounty") or ({"hook": n["hook"]} if n.get("hook") else None)
            if took and took in self.bounties[:9]:
                i = self.bounties.index(took) + 1
                what = "answer it: a tale begins" if n.get("hook") else                     "take this bounty down and put it in your journal"
                lines.append(f"<dim>(Press {i} to {what}.)</>")
            lines.append("")
        if not items:
            lines = ["<dim>Old nails and torn corners. Nothing is posted here now.</>"]
        self.view.set_text("\n".join(lines))

    def take(self, i: int) -> None:
        from realmwalker.game import quests

        if not 0 <= i < len(self.bounties):
            return
        if "hook" in self.bounties[i]:  # (a plea: the tale is offered, and the board makes way for it)
            from realmwalker.game import story
            from realmwalker.world import threats

            t = threats.records(self.game.world).get(self.bounties[i]["hook"])
            if t is not None:
                story.offer_hook(self.game, t, self.settlement)
            self.close()
            return
        for text in quests.accept(self.game, self.bounties[i]):
            self.game.say(text, "info")
        self.refresh()

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "enter", "space"):
            self.close()
            return True
        if len(ev.key) == 1 and ev.key in "123456789":
            self.take(int(ev.key) - 1)
            return True
        return self.view.handle_key(ev)

    def render(self, canvas: Canvas) -> None:
        width = min(84, canvas.width - 4)
        height = min(canvas.height - 2, 30)
        x, y, w, h = modal_box(canvas, width, height, f"The notice board in {self.settlement.name}")
        self.view.render(canvas, x + 2, y + 2, w - 4, h - 5)
        bx = canvas.button(x + 2, y + h - 2, "Done", self.close, hotkey="Esc")
        for i in range(min(2, len(self.bounties))):
            word = "Answer" if "hook" in self.bounties[i] else "Take bounty"
            bx = canvas.button(bx + 2, y + h - 2, f"{word} {i + 1}", lambda i=i: self.take(i), hotkey=str(i + 1))
        if bx + 22 < x + w:
            canvas.text(bx + 2, y + h - 2, "↑↓ PgUp PgDn scroll", colors.FAINT)
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("down"), KeyEvent("pagedown"), KeyEvent("1"), KeyEvent("escape")]
