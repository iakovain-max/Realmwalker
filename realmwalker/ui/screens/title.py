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
        self.menu = Menu(self._items(), on_disabled=self._disabled)

    def _items(self) -> list[MenuItem]:
        return [
            MenuItem("New World", self._new_world, "N", enabled=False,
                     note="Create a new world. Arrives in Milestone 1 (world generation and movement)."),
            MenuItem("New Character", None, "R", enabled=False,
                     note="Start a new character in an existing world. Arrives with character creation (Milestone 2)."),
            MenuItem("Continue", None, "C", enabled=False, note="Continue your living character. Arrives with saving (Milestone 1)."),
            MenuItem("Player2 Connection Test", self._player2_test, "P",
                     note="Check the connection to the Player2 AI app and try a sample generation."),
            MenuItem("Settings", self._settings, "S", note="Text size, dice display, AI on/off and more."),
            MenuItem("Help", self._help, "?", note="Keys and how to play."),
            MenuItem("Quit", self.app.request_quit, "Q", note="Leave the game."),
        ]

    def _disabled(self, item: MenuItem) -> None:
        self.app.notify(item.note or "Not available yet.", "warn", 5)

    def _new_world(self) -> None:
        pass

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
    def render(self, canvas: Canvas) -> None:
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
        canvas.text(1, h - 1, f"v{__version__} · {MILESTONE} · F1 help · Ctrl +/- text size · F11 fullscreen", colors.FAINT)

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
        return [KeyEvent("up"), KeyEvent("down"), KeyEvent("enter"), KeyEvent("p"), KeyEvent("s"), KeyEvent("?"), KeyEvent("n")]
