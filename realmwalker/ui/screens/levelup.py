"""Level-up choices: a path, ability increases, spells and cantrips, for each member of the party."""

from __future__ import annotations

from realmwalker.rules import progression
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas


class LevelUpScreen(Screen):
    title = "Level up"
    sound_open = None  # the harp has already sounded as the level came

    def __init__(self, app, game, index: int = 0) -> None:
        super().__init__(app)
        self.game = game
        self.index = index
        self.sel = 0
        self.offset = 0
        self.log: list[str] = []
        for c in game.party:
            progression.seen_choices(c)
        if not self.char.pending:
            self.next_member()

    @property
    def char(self):
        return self.game.party[min(self.index, len(self.game.party) - 1)]

    def choice(self):
        return self.char.pending[0] if self.char.pending else None

    def next_member(self) -> bool:
        """Move to the next party member with choices waiting. False if nobody has any."""
        n = len(self.game.party)
        for step in range(1, n + 1):
            i = (self.index + step) % n
            if self.game.party[i].pending:
                self.index = i
                self.sel = 0
                return True
        return False

    def pick(self) -> None:
        choice = self.choice()
        if choice is None:
            return
        opts = progression.options(self.char, self.game.tables, choice)
        if not opts:
            self.char.pending.remove(choice)
            return
        oid = opts[min(self.sel, len(opts) - 1)][0]
        self.log += progression.resolve(self.char, self.game.tables, choice, oid)
        for line in self.log[-3:]:
            self.game.say(line, "good")
        self.sel = 0
        self.game.dirty = True
        if not self.char.pending and not self.next_member():
            self.close()

    def auto(self) -> None:
        for c in self.game.party:
            for line in progression.auto_resolve(c, self.game.tables):
                self.game.say(line, "good")
        self.game.dirty = True
        self.close()

    def handle_key(self, ev: KeyEvent) -> bool:
        choice = self.choice()
        n = len(progression.options(self.char, self.game.tables, choice)) if choice else 0
        if ev.key == "escape":
            self.close()
        elif ev.key == "up":
            self.sel = max(0, self.sel - 1)
        elif ev.key == "down":
            self.sel = min(max(0, n - 1), self.sel + 1)
        elif ev.key == "pageup":
            self.sel = max(0, self.sel - 10)
        elif ev.key == "pagedown":
            self.sel = min(max(0, n - 1), self.sel + 10)
        elif ev.key == "enter":
            self.pick()
        elif ev.key in ("a", "A"):
            self.auto()
        elif ev.key == "tab":
            self.next_member()
        return True

    def choose_row(self, i: int) -> None:
        if self.sel == i:
            self.pick()
        else:
            self.sel = i

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        c = self.char
        canvas.frame(0, 0, w, h - 1, f"Level up: {markup.escape(c.name)}, level {c.level}", double=True)
        choice = self.choice()
        if choice is None:
            canvas.markup(2, 2, "<dim>No choices are waiting.</>")
            canvas.button(2, h - 3, "Done", self.close, hotkey="Esc")
            return
        t = self.game.tables
        canvas.markup(2, 2, f"<title>{markup.escape(progression.choice_title(c, t, choice))}</>", max_width=w - 4)
        waiting = sum(1 for m in self.game.party for _ in m.pending)
        canvas.markup(2, 3, f"<dim>{waiting} choice{'s' if waiting != 1 else ''} waiting in the party</>",
                      max_width=w - 4)
        opts = progression.options(c, t, choice)
        list_w = min(48, max(26, w // 2 - 2))
        top, bottom = 5, h - 5
        rows = bottom - top
        self.sel = max(0, min(self.sel, len(opts) - 1))
        if self.sel < self.offset:
            self.offset = self.sel
        elif self.sel >= self.offset + rows:
            self.offset = self.sel - rows + 1
        for i, (oid, label, _) in enumerate(opts[self.offset:self.offset + rows]):
            idx = self.offset + i
            y = top + i
            chosen = idx == self.sel
            if chosen:
                canvas.fill(2, y, list_w, 1, colors.HILITE_BG)
            canvas.hit(2, y, list_w, 1, lambda idx=idx: self.choose_row(idx))
            canvas.text(3, y, label[: list_w - 2], colors.SELECT_FG if chosen else colors.FG)
        if opts:
            detail = opts[self.sel][2]
            canvas.wrapped(list_w + 5, top, markup.escape(detail), max(20, w - list_w - 8), max_lines=rows)
        y = bottom
        for line in self.log[-2:]:
            canvas.markup(2, y, f"<good>{markup.escape(line)}</>", max_width=w - 4)
            y += 1
        bx = canvas.button(2, h - 2, "Choose", self.pick, hotkey="Enter")
        bx = canvas.button(bx + 3, h - 2, "Choose for me", self.auto, hotkey="a")
        if len(self.game.party) > 1:
            bx = canvas.button(bx + 3, h - 2, "Next member", self.next_member, hotkey="Tab")
        canvas.button(bx + 3, h - 2, "Later", self.close, hotkey="Esc")

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "down", "enter", "enter", "a", "escape")]
