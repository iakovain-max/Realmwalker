"""Resting: a short rest (an hour) or a long rest (eight hours). Camping proper arrives with M4."""

from __future__ import annotations

from realmwalker.game.fight import rest
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import MessageBox, Screen, modal_box
from realmwalker.ui.widgets import Canvas


class RestScreen(Screen):
    modal = True
    title = "Rest"

    def __init__(self, app, game) -> None:
        super().__init__(app)
        self.game = game

    def do_rest(self, kind: str) -> None:
        game = self.game
        self.close()
        game.say("You settle down to rest for an hour." if kind == "short" else "You make what camp you can and sleep.",
                 "system")
        notes = rest(game, kind)
        for note in notes:
            game.say(note, "good" if "level" in note or "recover" in note.lower() else "info")
        self.app.save_game()
        if game.encounter is None and game.battle is None and notes:
            self.app.push(MessageBox(self.app, "Rested", "\n".join(notes[:8])))

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("s", "1"):
            self.do_rest("short")
        elif ev.key in ("l", "2"):
            self.do_rest("long")
        elif ev.key in ("escape", "n", "r"):
            self.close()
        return True

    def render(self, canvas: Canvas) -> None:
        game = self.game
        width = min(64, canvas.width - 4)
        x, y, w, h = modal_box(canvas, width, 13, "Rest")
        iw = w - 4
        row = y + 2
        for c in game.party:
            canvas.markup(x + 2, row, f"<name>{markup.escape(c.name.split()[0])}</> {c.hp}/{c.max_hp} hp "
                                      f"<dim>· hit dice {c.hit_dice}/{c.level}</>", max_width=iw)
            row += 1
        row += 1
        danger = "" if game.world.settlement_at(game.player.x, game.player.y) else " <warn>Out here, something may find you.</>"
        canvas.button(x + 2, row, "Short rest (1 hour): spend hit dice to heal", lambda: self.do_rest("short"), hotkey="S")
        row += 1
        canvas.button(x + 2, row, "Long rest (8 hours): heal fully, recover spells", lambda: self.do_rest("long"), hotkey="L")
        row += 2
        canvas.wrapped(x + 2, row, "<dim>Wounds do not close with rest alone.</>" + danger, iw, fg=colors.DIM, max_lines=2)
        canvas.button(x + 2, y + h - 2, "Cancel", self.close, hotkey="Esc")
        canvas.hit(0, 0, canvas.width, canvas.height)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("s", "l", "escape")]
