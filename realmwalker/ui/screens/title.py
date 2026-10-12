"""The title screen and main menu."""

from __future__ import annotations

from realmwalker import MILESTONE, __version__
from realmwalker.ui import colors
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas, Menu, MenuItem

TAGLINE = "The realm does not care whether you live."


class TitleScreen(Screen):
    sound_open = None  # the game starting is greeted by its music, not a thump

    def __init__(self, app) -> None:
        super().__init__(app)
        self.saves = app.saves_with_characters() if app.tables is not None else []
        self.empty_worlds = app.worlds_without_characters() if app.tables is not None else []
        self.menu = Menu(self._items(), on_disabled=self._disabled)
        if not self.saves:
            self.menu.selected = 1

    def _items(self) -> list[MenuItem]:
        return [
            MenuItem("Continue", self._continue, "C", enabled=bool(self.saves),
                     note="Carry on with your living character." if self.saves else "No saved characters yet."),
            MenuItem("New World", self._new_world, "N",
                     note="Create a new world: its land, rivers, towns and roads. Then set out into it."),
            MenuItem("New Character", self._new_character, "R", enabled=bool(self.empty_worlds),
                     note="Create a character in a world you already made." if self.empty_worlds
                     else "Every world you have made has a living character. Make a New World, or Continue."),
            MenuItem("Saved Worlds", self._worlds, "W", enabled=bool(self.saves or self.empty_worlds),
                     note="Every world you have made: play on, start a new character, or delete one."),
            MenuItem("Settings", self._settings, "S", note="Text size, sound, animations, dice display and more."),
            MenuItem("Help", self._help, "?", note="Keys and how to play."),
            MenuItem("Quit", self.app.request_quit, "Q", note="Leave the game."),
        ]

    def _disabled(self, item: MenuItem) -> None:
        self.app.notify(item.note or "Not available yet.", "warn", 5)

    def _worlds(self) -> None:
        from realmwalker.ui.screens.game_menu import WorldsScreen

        self.app.push(WorldsScreen(self.app))

    def _new_world(self) -> None:
        from realmwalker.ui.screens.new_world import NewWorldScreen

        self.app.push(NewWorldScreen(self.app))

    def _new_character(self) -> None:
        from realmwalker.ui.screens.game_menu import WorldPickScreen

        self.app.push(WorldPickScreen(self.app, self.empty_worlds))

    def _continue(self) -> None:
        if len(self.saves) == 1:
            self.app.continue_game(self.saves[0].folder)
        else:
            from realmwalker.ui.screens.game_menu import WorldsScreen

            self.app.push(WorldsScreen(self.app, living_only=True))

    def on_enter(self) -> None:
        # Refresh the Continue entry when coming back to the title.
        self.saves = self.app.saves_with_characters() if self.app.tables is not None else []
        self.empty_worlds = self.app.worlds_without_characters() if self.app.tables is not None else []
        selected = self.menu.selected
        self.menu = Menu(self._items(), on_disabled=self._disabled)
        self.menu.selected = selected if self.saves or selected != 0 else 1

    def _settings(self) -> None:
        from realmwalker.ui.screens.settings_screen import SettingsScreen

        self.app.push(SettingsScreen(self.app))

    def _help(self) -> None:
        from realmwalker.ui.screens.help import HelpScreen

        self.app.push(HelpScreen(self.app))

    # ------------------------------------------------------------------
    @property
    def ambient(self) -> bool:
        return True

    def music(self) -> str | None:
        return "title"  # and for every menu opened over it: new world, the character, saved worlds

    def render(self, canvas: Canvas) -> None:
        """Night over the mountains; the name in blackletter; the menu on a pane of dark glass."""
        from realmwalker.ui.gfx import theme, titleart
        from realmwalker.ui.gfx.scene import Text

        w, h = canvas.width, canvas.height
        canvas.clear_cells(0, 0, w, h)
        titleart.draw(canvas, canvas.now, canvas.gfx.ambient)
        cw, ch = canvas.cell_w, canvas.cell_h
        size = max(48, min(120, int(h * ch * 0.11)))
        top = max(1, h // 2 - 15)
        titleart.logo(canvas, w * cw / 2, top * ch, size)
        canvas.over(Text(w * cw / 2, top * ch + size * 1.08, TAGLINE, "prose", max(16, size // 4), (200, 190, 170, 235),
                         anchor="mt", shadow=True))
        menu_w = 34
        mx = (w - menu_w) // 2
        my = top + max(7, int(size * 1.6 // ch) + 2)
        n = len(self.menu.items)
        canvas.under(*theme.panel((mx - 3) * cw, (my - 1) * ch, (menu_w + 6) * cw, (n + 2) * ch, "glass", ornaments=True))
        self.menu.render(canvas, mx, my, menu_w)
        note = self.menu.items[self.menu.selected].note
        if note:
            nw = min(70, w - 4)
            canvas.wrapped(max(2, (w - nw) // 2), my + n + 2, f"<dim>{note}</>", nw)
        parts = [f"v{__version__}", MILESTONE, "F1 help", "Ctrl +/- text size", "F11 fullscreen"]
        line = parts[0]
        for part in parts[1:]:
            if len(line) + 3 + len(part) > w - 2:
                break
            line += " · " + part
        canvas.text(1, h - 1, line, colors.DIM)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "escape":
            return True
        return self.menu.handle_key(ev)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("up"), KeyEvent("down"), KeyEvent("enter"), KeyEvent("s"), KeyEvent("?"),
                KeyEvent("n"), KeyEvent("n"), KeyEvent("c"), KeyEvent("c"), KeyEvent("c")]
