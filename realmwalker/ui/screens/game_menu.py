"""The in-game menu (Esc), the Continue list of saved characters, and Saved worlds (play, start again, delete)."""

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


class WorldsScreen(Screen):
    """Every saved world: play on with its character, start a new character in it, or delete it."""

    title = "Saved worlds"

    def __init__(self, app, living_only: bool = False) -> None:
        super().__init__(app)
        self.selected = 0
        self.living_only = living_only  # Continue: only the worlds with someone in them to play
        if living_only:
            self.title = "Continue"
        self.refresh()

    def refresh(self) -> None:
        from realmwalker.game.save import list_saves

        try:
            self.saves = list_saves(self.app.paths.saves)
        except OSError:
            self.saves = []
        if self.living_only:
            self.saves = [s for s in self.saves if s.character]
        self.selected = max(0, min(self.selected, len(self.saves) - 1))

    def current(self):
        return self.saves[self.selected] if self.saves else None

    def play(self) -> None:
        s = self.current()
        if s is None:
            return
        if s.character:
            self.app.continue_game(s.folder)
        else:
            self.close()
            self.app.create_character_in(s.folder)

    def legends(self) -> None:
        """Read a world's history without playing it (as Dwarf Fortress's Legends mode)."""
        from realmwalker.game.save import SaveError, load_world
        from realmwalker.ui.screens.legends import LegendsScreen

        s = self.current()
        if s is None:
            return
        try:
            world = load_world(s.folder)
        except SaveError as exc:
            from realmwalker.ui.screens.base import MessageBox

            self.app.push(MessageBox(self.app, "Could not read the world", str(exc), color=colors.named("danger")))
            return
        self.app.push(LegendsScreen(self.app, world))

    def delete(self) -> None:
        from realmwalker.ui.screens.base import ConfirmBox

        s = self.current()
        if s is None:
            return
        who = f" and {markup.escape(s.character)} with it" if s.character else ""
        self.app.push(ConfirmBox(
            self.app,
            f"Delete the world <place>{markup.escape(s.world_name)}</>{who}? Its land, its people and everything your "
            f"characters did there will be gone.\n\n<dim>On Windows it goes to the Recycle Bin, so it can still be "
            f"brought back from there.</>",
            lambda s=s: self._really_delete(s), title="Delete this world?", danger=True))

    def _really_delete(self, summary) -> None:
        from realmwalker.game.save import SaveError, delete_world

        try:
            where = delete_world(summary.folder, self.app.paths.saves)
        except SaveError as exc:
            from realmwalker.ui.screens.base import MessageBox

            self.app.push(MessageBox(self.app, "Could not delete", str(exc), color=colors.named("danger")))
            return
        self.app.notify(f"{summary.world_name} " + ("is in the Recycle Bin." if where == "recycle bin" else "is deleted."),
                        "warn", 5)
        self.refresh()

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        width = min(110, w - 2)
        height = min(max(14, len(self.saves) + 10), h - 1)
        x0, y0 = (w - width) // 2, max(0, (h - height) // 2)
        canvas.frame(x0, y0, width, height, self.title, double=True)
        list_w = min(60, width * 3 // 5)
        lx, ly = x0 + 2, y0 + 2
        if not self.saves:
            canvas.text(lx, ly, "No saved worlds yet. Make a New World first.", colors.DIM, max_width=width - 4)
        room = height - 6
        first = max(0, min(self.selected - room + 1, len(self.saves) - room))
        for row, s in enumerate(self.saves[first:first + room]):
            i = first + row
            ry = ly + row
            over = canvas.hit(lx, ry, list_w, 1, action=lambda i=i: self._click(i), right_action=lambda i=i: self._pick_delete(i))
            if i == self.selected:
                canvas.fill(lx, ry, list_w, 1, colors.HILITE_BG)
            elif over:
                canvas.fill(lx, ry, list_w, 1, colors.HOVER_BG)
            who = f"<name>{markup.escape(s.character)}</>" if s.character else "<dim>no living character</>"
            canvas.markup(lx + 1, ry, f"<place>{markup.escape(s.world_name)}</> — {who}", max_width=list_w - 2)
        # The chosen world.
        cx = lx + list_w + 2
        cw = x0 + width - 2 - cx
        s = self.current()
        if s is not None and cw > 12:
            lines = [f"<title>{markup.escape(s.world_name)}</>", "",
                     f"<dim>Character:</> {markup.escape(s.character) if s.character else 'none living'}",
                     f"<dim>Size:</> {s.size}", f"<dim>Seed:</> {s.seed}",
                     f"<dim>Made:</> {markup.escape(s.created.replace('T', ' ')[:16])}",
                     f"<dim>Last played:</> {markup.escape(s.saved.replace('T', ' ')[:16])}"]
            yy = ly
            for line in lines:
                yy += canvas.wrapped(cx, yy, line, cw, max_lines=2)
        by = y0 + height - 3
        bx = canvas.button(lx, by, ("Play" if (s and s.character) else "New character here") if s else "Play", self.play,
                           hotkey="Enter", enabled=s is not None)
        bx = canvas.button(bx + 3, by, "Legends", self.legends, hotkey="L", enabled=s is not None)
        bx = canvas.button(bx + 3, by, "Delete world", self.delete, hotkey="Del", enabled=s is not None)
        canvas.button(bx + 3, by, "Back", self.close, hotkey="Esc")

    def _click(self, i: int) -> None:
        now = self.app.clock()
        if i == self.selected and now - getattr(self, "_last", -9.0) < 0.5:
            self.play()
            return
        self._last = now
        self.selected = i

    def _pick_delete(self, i: int) -> None:
        self.selected = i
        self.delete()

    def handle_key(self, ev: KeyEvent) -> bool:
        n = len(self.saves)
        if ev.key == "escape":
            self.close()
        elif ev.key == "up" and n:
            self.selected = (self.selected - 1) % n
        elif ev.key == "down" and n:
            self.selected = (self.selected + 1) % n
        elif ev.key == "enter":
            self.play()
        elif ev.key in ("delete", "x"):
            self.delete()
        elif ev.key in ("l", "L"):
            self.legends()
        else:
            return False
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("down"), KeyEvent("up"), KeyEvent("escape")]
