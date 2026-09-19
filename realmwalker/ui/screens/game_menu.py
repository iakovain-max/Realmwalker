"""The in-game menu (Esc), and the Continue list of saved characters."""

from __future__ import annotations

from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen, modal_box
from realmwalker.ui.widgets import Canvas, Menu, MenuItem


class GameMenu(Screen):
    modal = True
    title = "Menu"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.menu = Menu([
            MenuItem("Return to the game", self.close, "Esc"),
            MenuItem("Help", self._help, "?"),
            MenuItem("Settings", self._settings, "S"),
            MenuItem("Save and return to the title screen", self._to_title, "T"),
            MenuItem("Save and quit the game", self._quit, "Q"),
        ])

    def _help(self) -> None:
        from realmwalker.ui.screens.help import HelpScreen

        self.app.replace(HelpScreen(self.app))

    def _settings(self) -> None:
        from realmwalker.ui.screens.settings_screen import SettingsScreen

        self.app.replace(SettingsScreen(self.app))

    def _to_title(self) -> None:
        self.app.end_game()

    def _quit(self) -> None:
        self.app.save_game()
        self.app.request_quit()

    def render(self, canvas: Canvas) -> None:
        x, y, w, h = modal_box(canvas, 48, len(self.menu.items) + 6, self.title)
        self.menu.render(canvas, x + 2, y + 2, w - 4)
        canvas.text(x + 2, y + h - 2, "The game saves itself as you play.", colors.FAINT, max_width=w - 4)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "escape":
            self.close()
            return True
        return self.menu.handle_key(ev)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("escape"), KeyEvent("escape"), KeyEvent("down"), KeyEvent("enter"), KeyEvent("t")]


class WorldPickScreen(Screen):
    """Choose a world (without a living character) to create a new character in."""

    title = "New Character: choose a world"

    def __init__(self, app, worlds) -> None:
        super().__init__(app)
        self.worlds = worlds
        items = [MenuItem(f"{w.world_name} ({w.size}, seed {w.seed})", lambda w=w: self._pick(w),
                          note=f"Created {w.created}.") for w in worlds]
        items.append(MenuItem("Back", self.close, "Esc"))
        self.menu = Menu(items)

    def _pick(self, summary) -> None:
        self.close()
        self.app.create_character_in(summary.folder)

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        width = min(80, w - 2)
        height = min(len(self.menu.items) + 6, h - 1)
        x0, y0 = (w - width) // 2, max(0, (h - height) // 2)
        canvas.frame(x0, y0, width, height, self.title, double=True)
        self.menu.render(canvas, x0 + 2, y0 + 2, width - 4)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "escape":
            self.close()
            return True
        return self.menu.handle_key(ev)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("down"), KeyEvent("enter")]


class ContinueScreen(Screen):
    title = "Continue"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.saves = app.saves_with_characters()
        items = []
        for s in self.saves:
            label = f"{s.character} — {s.world_name} ({s.size})"
            items.append(MenuItem(label, lambda s=s: self._load(s), note=f"Last played {s.saved.replace('T', ' ')}. Seed {s.seed}."))
        items.append(MenuItem("Back", self.close, "Esc"))
        self.menu = Menu(items)

    def _load(self, summary) -> None:
        self.app.continue_game(summary.folder)

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        width = min(80, w - 2)
        height = min(len(self.menu.items) + 8, h - 1)
        x0, y0 = (w - width) // 2, max(0, (h - height) // 2)
        canvas.frame(x0, y0, width, height, self.title, double=True)
        if not self.saves:
            canvas.text(x0 + 3, y0 + 2, "No living characters. Create a New World first.", colors.DIM)
        self.menu.render(canvas, x0 + 2, y0 + 2 + (1 if not self.saves else 0), width - 4)
        note = self.menu.items[self.menu.selected].note
        if note:
            canvas.markup(x0 + 3, y0 + height - 2, f"<dim>{markup.escape(note)}</>", max_width=width - 6)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "escape":
            self.close()
            return True
        return self.menu.handle_key(ev)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("down"), KeyEvent("up"), KeyEvent("enter")]
