"""After a fight: what happened, experience, the fate of captives, and the loot. Also the death screen."""

from __future__ import annotations

from realmwalker.game.fight import CAPTIVE_FATES, Aftermath, decide_captive, leave_loot, take_loot
from realmwalker.rules.items import money_text
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import ConfirmBox, Screen
from realmwalker.ui.widgets import Canvas

TITLES = {"victory": "Victory", "robbed": "Beaten and robbed", "mauled": "Left for dead", "fled": "Escape",
          "parley": "Words, not blood",
          "death": "Death", "defeat": "Defeat", "surrendered": "Surrender"}
FATE_KEYS = ["spare", "rob", "interrogate", "execute", "capture"]


class AftermathScreen(Screen):
    title = "Aftermath"
    sound_open = None  # the victory or defeat is in the music

    def __init__(self, app, game, after: Aftermath) -> None:
        super().__init__(app)
        self.game = game
        self.after = after
        self.marked: set[int] = set()  # indexes into after.loot
        self.cursor = 0
        self.fate_texts: list[str] = []
        self.phase = "captives" if self._undecided() else "loot"

    def music(self) -> str | None:
        return {"victory": "victory", "defeat": "defeat"}.get(self.after.outcome)

    # ------------------------------------------------------------------ state
    def _undecided(self) -> list:
        return [c for c in self.after.captives if c.uid not in self.after.fates]

    def _captive_label(self, c) -> str:
        d = self.game.tables.creatures[c.def_id]
        return c.name if c.named and c.name != d["name"] else f"the {d['name']}"

    def choose_fate(self, fate: str) -> None:
        pending = self._undecided()
        if not pending:
            return
        creature = pending[0]

        def go() -> None:
            text = decide_captive(self.game, creature, fate)
            self.fate_texts.append(text)
            if creature.uid not in self.after.fates:  # (taking them along needs someone who pays for them)
                self.app.notify("Nobody here pays for prisoners yet; choose something else.", "warn")
                return
            if not self._undecided():
                self.phase = "loot"
                self.cursor = 0

        if fate == "execute":
            self.app.push(ConfirmBox(self.app, f"Kill {markup.escape(self._captive_label(creature))}, who has surrendered "
                                               f"to you? People may hear of it.", go, title="Kill a prisoner", danger=True))
        else:
            go()

    def toggle(self, i: int) -> None:
        if 0 <= i < len(self.after.loot):
            self.cursor = i
            self.marked ^= {i}

    def take_all(self) -> None:
        taken = take_loot(self.game)
        if taken:
            self.game.say(f"You take {', '.join(taken)}.", "loot")
        self.marked.clear()
        self.cursor = 0

    def take_marked(self) -> None:
        loot = self.after.loot
        chosen = [loot[i] for i in sorted(self.marked) if i < len(loot)]
        if not chosen and loot:
            chosen = [loot[min(self.cursor, len(loot) - 1)]]
        taken = take_loot(self.game, chosen, money=True)
        if taken:
            self.game.say(f"You take {', '.join(taken)}.", "loot")
        self.marked.clear()
        self.cursor = min(self.cursor, max(0, len(self.after.loot) - 1))

    def butcher(self) -> None:
        from realmwalker.game.camp import butcher

        items, msgs = butcher(self.game, self.after.carcasses)
        self.after.carcasses = []
        self.after.loot.extend(items)
        for m in msgs:
            self.game.say(m, "info")
        self.fate_texts += msgs

    def done(self) -> None:
        if self.phase == "captives" and self._undecided():
            self.app.notify("Decide what happens to your prisoners first.", "warn")
            return
        if self.after.loot and self.game.local is None:
            self.app.push(ConfirmBox(self.app, "Leave the rest behind? Out here on the road it will be gone.",
                                     self._close, title="Leave the loot"))
            return
        self._close()

    def _close(self) -> None:
        leave_loot(self.game)
        self.game.aftermath = None
        if self.game.over is not None:
            from realmwalker.game import greatmagic

            back = greatmagic.cheat_death(self.game)  # (Clone: the soul wakes in a grown clone)
            if back:
                for text in back:
                    self.game.say(text, "good")
            else:
                self.app.replace(DeathScreen(self.app, self.game))
                return
        self.app.save_game()
        self.close()

    # ------------------------------------------------------------------ input
    def handle_key(self, ev: KeyEvent) -> bool:
        if self.after.outcome == "death":
            if ev.key in ("enter", " ", "escape"):
                self._close()
            return True
        if self.phase == "captives":
            if ev.is_text and ev.key.isdigit() and 1 <= int(ev.key) <= len(FATE_KEYS):
                self.choose_fate(FATE_KEYS[int(ev.key) - 1])
            return True
        loot = self.after.loot
        if ev.key == "up" and loot:
            self.cursor = (self.cursor - 1) % len(loot)
        elif ev.key == "down" and loot:
            self.cursor = (self.cursor + 1) % len(loot)
        elif ev.key == " " and loot:
            self.toggle(self.cursor)
        elif ev.key == "a":
            self.take_all()
        elif ev.key == "b" and self.after.carcasses:
            self.butcher()
        elif ev.key == "t":
            self.take_marked()
        elif ev.key == "enter":
            if self.marked:
                self.take_marked()
            elif loot or self.after.money:
                self.take_all()
            if not self.after.loot:
                self.done()
        elif ev.key in ("escape", "l"):
            self.done()
        else:
            return False
        return True

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        after = self.after
        w, h = canvas.width, canvas.height
        color = colors.named("danger") if after.outcome in ("death", "robbed", "mauled") else colors.BORDER
        canvas.frame(0, 0, w, h, TITLES.get(after.outcome, "Aftermath"), double=True, fg=color)
        x, iw = 3, w - 6
        y = 2
        y += canvas.wrapped(x, y, markup.escape(after.text), iw, max_lines=6) + 1
        for note in after.notes:
            if y >= h - 12:
                break
            y += canvas.wrapped(x, y, note, iw, max_lines=2)
        for text in self.fate_texts[-3:]:
            y += canvas.wrapped(x, y, text, iw, fg=colors.DIM, max_lines=2)
        y += 1
        if after.outcome == "death":
            canvas.button(x, h - 2, "Continue", self._close, hotkey="Enter")
            return
        if self.phase == "captives":
            self._render_captives(canvas, x, y, iw, h - y - 2)
        else:
            self._render_loot(canvas, x, y, iw, h - y - 2)

    def _render_captives(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        pending = self._undecided()
        if not pending:
            return
        c = pending[0]
        d = self.game.tables.creatures[c.def_id]
        canvas.section(x, y, w, f"Prisoners ({len(pending)} to decide)")
        y += 1
        canvas.markup(x, y, f"<name>{markup.escape(self._captive_label(c)[:1].upper() + self._captive_label(c)[1:])}</> "
                            f"<dim>({d['name']}, {c.hp}/{c.max_hp} hp)</> waits to hear what you will do.", max_width=w)
        y += 2
        for i, fate in enumerate(FATE_KEYS):
            canvas.button(x, y + i, CAPTIVE_FATES[fate], lambda f=fate: self.choose_fate(f), hotkey=str(i + 1))

    def _render_loot(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        after = self.after
        items = self.game.tables.items
        from realmwalker.ui.screens.sheets import item_glyph, load_line

        if after.loot or after.money:
            canvas.section(x, y, w, "Spoils")
            y += 1
            if after.money:
                canvas.markup(x, y, f"<loot>{money_text(after.money)}</> <dim>in coin (taken with anything you take)</>", max_width=w)
                y += 1
            room = max(1, h - 5)
            first = max(0, min(self.cursor - room + 1, len(after.loot) - room))
            for row, it in enumerate(after.loot[first:first + room]):
                i = first + row
                ry = y + row
                selected = i == self.cursor
                over = canvas.hit(x, ry, w, 1, action=lambda i=i: self.toggle(i))
                bg = colors.HILITE_BG if selected else (colors.HOVER_BG if over else None)
                if bg:
                    canvas.fill(x, ry, w, 1, bg)
                mark = "[x]" if i in self.marked else "[ ]"
                glyph, gcolor = item_glyph(items.category(it))
                canvas.text(x, ry, mark, colors.TITLE if i in self.marked else colors.DIM, bg)
                canvas.text(x + 4, ry, glyph, colors.named(gcolor), bg)
                name = items.name(it)
                cond = items.condition_word(it)
                canvas.markup(x + 6, ry, f"{markup.escape(name)} <dim>{items.weight(it):g} lb · {cond} · "
                                         f"{money_text(items.value(it))}</>", bg=bg, max_width=w - 6)
            y += min(room, len(after.loot)) + 1
            canvas.markup(x, y, load_line(self.game.sheet()), max_width=w)
            y += 2
            bx = canvas.button(x, y, "Take all", self.take_all, hotkey="A")
            bx = canvas.button(bx + 3, y, "Take marked", self.take_marked, hotkey="T")
            bx = canvas.button(bx + 3, y, "Leave the rest", self.done, hotkey="L")
            if after.carcasses:
                canvas.button(bx + 3, y, "Butcher the carcasses", self.butcher, hotkey="B")
            canvas.text(x, y + 1, "Space marks an item · Enter takes marked (or all) and goes on", colors.FAINT, max_width=w)
        else:
            canvas.text(x, y, "There is nothing here worth taking." if after.outcome == "victory" else "", colors.DIM)
            bx = canvas.button(x, y + 2, "Continue", self.done, hotkey="Enter")
            if after.carcasses:
                canvas.button(bx + 3, y + 2, "Butcher the carcasses (30 min)", self.butcher, hotkey="B")

    def autoplay_keys(self) -> list[KeyEvent]:
        if self.phase == "captives" and self.after.outcome != "death":
            return [KeyEvent(k) for k in ("1", "2", "3", "4", "5")]
        return [KeyEvent(k) for k in ("down", " ", "t", "b", "a", "enter", "l", "enter")]


class DeathScreen(Screen):
    """The end of a life: the obituary, and what the world will remember (game/death.py)."""

    title = "Death"
    sound_open = "death"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        from realmwalker.game import death

        self.game = game
        game.player.alive = False
        self.record = death.die(game)
        self.lines = death.fallback_obituary(game, self.record)
        self.offset = 0
        game.say(f"<danger>{markup.escape(game.leader.name)} is dead.</>", "danger")
        app.save_game()

    def music(self) -> str | None:
        return "death"

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h, "Here ends the tale", double=True, fg=colors.named("danger"))
        width = min(76, w - 8)
        wrapped: list = []
        for line in self.lines:
            wrapped.extend(markup.wrap(line, width) or [[]])
        room = h - 6
        self.offset = max(0, min(self.offset, max(0, len(wrapped) - room)))
        visible = wrapped[self.offset: self.offset + room]
        y = max(2, (h - len(visible)) // 2 - 1)
        canvas.centered(y - 1, "†", colors.DIM)
        x0 = (w - width) // 2
        for spans in visible:
            canvas.spans(x0, y + 1, spans, max_width=width)
            y += 1
        canvas.button(w // 2 - 10, h - 2, "Back to the title", self.app.end_game, hotkey="Enter")
        if len(wrapped) > room:
            canvas.text(w // 2 + 10, h - 2, "↑↓ scroll", colors.FAINT)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "up":
            self.offset = max(0, self.offset - 1)
        elif ev.key == "down":
            self.offset += 1
        elif ev.key in ("enter", "escape", " "):
            self.app.end_game()
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("enter")]
