"""The title screen and main menu."""

from __future__ import annotations

import math

from realmwalker import MILESTONE, __version__
from realmwalker.ui import colors
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas, Menu, MenuItem

LOGO_LETTERS = {
    "R": ["████ ", "█   █", "████ ", "█  █ ", "█   █"],
    "E": ["█████", "█    ", "████ ", "█    ", "█████"],
    "A": [" ███ ", "█   █", "█████", "█   █", "█   █"],
    "L": ["█    ", "█    ", "█    ", "█    ", "█████"],
    "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █"],
    "W": ["█   █", "█   █", "█ █ █", "██ ██", "█   █"],
    "K": ["█   █", "█  █ ", "███  ", "█  █ ", "█   █"],
}
LOGO_WORD = "REALMWALKER"
TAGLINE = "The realm does not care whether you live."


def logo_rows() -> list[str]:
    return [" ".join(LOGO_LETTERS[ch][row] for ch in LOGO_WORD) for row in range(5)]


class TitleScreen(Screen):
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
            MenuItem("Player2 Connection Test", self._player2_test, "P",
                     note="Check the connection to the Player2 AI app and try a sample generation."),
            MenuItem("Settings", self._settings, "S", note="Text size, dice display, AI on/off and more."),
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

    def _player2_test(self) -> None:
        from realmwalker.ui.screens.player2_test import Player2TestScreen

        self.app.push(Player2TestScreen(self.app))

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

    def render(self, canvas: Canvas) -> None:
        if canvas.gfx is not None:
            self._render_painted(canvas)
            return
        w, h = canvas.width, canvas.height
        self._draw_backdrop(canvas)
        rows = logo_rows()
        logo_w = len(rows[0])
        top = max(1, h // 2 - 12)
        for i, row in enumerate(rows):
            fg = colors.lerp(colors.TITLE, (150, 60, 40), i / 4)
            canvas.text((w - logo_w) // 2, top + i, row, fg)
        canvas.centered(top + 6, f"<dim>{TAGLINE}</>")

        menu_w = 34
        mx = (w - menu_w) // 2
        my = top + 9
        self.menu.render(canvas, mx, my, menu_w)
        note = self.menu.items[self.menu.selected].note
        if note:
            canvas.wrapped(max(2, (w - 70) // 2), my + len(self.menu.items) + 1, f"<dim>{note}</>", min(70, w - 4))
        # As much of the line as fits: a narrow window loses the key hints first, never half a word.
        parts = [f"v{__version__}", MILESTONE, "F1 help", "Ctrl +/- text size", "F11 fullscreen"]
        line = parts[0]
        for part in parts[1:]:
            if len(line) + 3 + len(part) > w - 2:
                break
            line += " · " + part
        canvas.text(1, h - 1, line, colors.FAINT)

    def _render_painted(self, canvas: Canvas) -> None:
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

    def _draw_backdrop(self, canvas: Canvas) -> None:
        """Faint stars and a mountain ridge along the bottom."""
        w, h = canvas.width, canvas.height
        for x in range(0, w, 1):
            seed = (x * 7919) % 101
            if seed < 4:
                y = (x * 31) % max(1, h // 3)
                canvas.text(x, y, "·" if seed < 3 else "*", colors.FAINT)
        base = h - 2
        for x in range(w):
            ridge = 4 + 3 * math.sin(x / 9.0) + 2 * math.sin(x / 3.7 + 1.3) + 1.5 * math.sin(x / 17.0 + 0.4)
            peak = base - max(1, int(ridge))
            canvas.text(x, peak, "▲", (54, 50, 46))
            for y in range(peak + 1, base + 1):
                canvas.text(x, y, "░", (30, 28, 30))

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "escape":
            return True
        return self.menu.handle_key(ev)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("up"), KeyEvent("down"), KeyEvent("enter"), KeyEvent("p"), KeyEvent("s"), KeyEvent("?"),
                KeyEvent("n"), KeyEvent("n"), KeyEvent("c"), KeyEvent("c"), KeyEvent("c")]
