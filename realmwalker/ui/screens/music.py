"""Your music (Settings, then Your music): which folder plays when, what is in each, listening to a mood, and a
button that opens the music folder, so adding music is: open the folder, drop files in, press R."""

from __future__ import annotations

from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas


class MusicScreen(Screen):
    title = "Your music"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.selected = 0
        self.listening: str | None = None

    @property
    def library(self):
        return self.app.audio.library

    def moods(self) -> list[str]:
        return list(self.library.moods)

    def current(self) -> str | None:
        moods = self.moods()
        return moods[self.selected] if moods else None

    # ------------------------------------------------------------------ actions
    def listen(self) -> None:
        mood = self.current()
        if mood is None:
            return
        if self.listening == mood:
            self.stop()
            return
        self.listening = mood
        self.app.audio.music.preview = mood

    def stop(self) -> None:
        self.listening = None
        self.app.audio.music.preview = None

    def open_folder(self) -> None:
        mood = self.current()
        folder = self.library.user
        if folder is None:
            return
        self.library.make_folders()
        target = folder / mood if mood else folder
        if not self.app.open_folder(target if target.is_dir() else folder):
            self.app.notify(f"The music folder is {folder}", "info", 6)

    def rescan(self) -> None:
        self.app.audio.rescan_music()
        mine = sum(len(v) for v in self.library.files.values())
        self.app.notify(f"Found {mine} tune{'s' if mine != 1 else ''} of yours.", "info")

    def on_exit(self) -> None:
        self.stop()

    # ------------------------------------------------------------------ what each mood has
    def summary(self, mood: str) -> tuple[str, str]:
        """A few words on what plays for this mood, and their colour."""
        yours, shipped = self.library.count(mood)
        kinds = [k for k in self.library.moods[mood].get("kinds", []) if self.library.count(f"{mood}/{k}")[0]]
        if yours:
            words = f"{yours} of yours"
        elif shipped:
            words = f"{shipped} of the game's"
        else:
            pool, _ = self.library.resolve(mood)
            words = f"borrows from {pool}" if pool else "quiet"
        if kinds:
            words += f", +{len(kinds)} kind{'s' if len(kinds) > 1 else ''}"
        color = "good" if yours else ("fg" if shipped else "dim")
        return words, color

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        width = min(110, w - 2)
        moods = self.moods()
        height = min(max(20, len(moods) + 12), h - 1)
        x0, y0 = (w - width) // 2, max(0, (h - height) // 2)
        canvas.frame(x0, y0, width, height, self.title, double=True)
        lx, ly = x0 + 2, y0 + 2
        playing = self.app.audio.music.now_playing()
        line = f"<dim>Playing now:</> {markup.escape(playing)}" if playing else "<dim>Playing now: nothing</>"
        if not self.app.audio.real:
            line += "  <dim>(no sound device)</>"
        canvas.markup(lx, ly, line, max_width=width - 4)
        list_w = min(44, width * 2 // 5)
        room = height - 9
        first = max(0, min(self.selected - room + 1, len(moods) - room))
        for row, mood in enumerate(moods[first:first + room]):
            i = first + row
            ry = ly + 2 + row
            over = canvas.hit(lx, ry, list_w, 1, action=lambda i=i: self._click(i))
            if i == self.selected:
                canvas.fill(lx, ry, list_w, 1, colors.HILITE_BG)
            elif over:
                canvas.fill(lx, ry, list_w, 1, colors.HOVER_BG)
            mark = "♪ " if self.listening == mood else "  "
            canvas.text(lx, ry, mark, colors.TITLE)
            canvas.text(lx + 2, ry, mood.capitalize(), colors.SELECT_FG if i == self.selected else colors.FG)
            words, color = self.summary(mood)
            canvas.text(lx + 12, ry, words, colors.named(color), max_width=list_w - 13)
        self._render_detail(canvas, lx + list_w + 2, ly + 2, x0 + width - 2 - (lx + list_w + 2), height - 7)
        by = y0 + height - 3
        canvas.wrapped(lx, by - 1, "<dim>Put .ogg, .mp3, .flac or .wav files in a mood's folder; yours replace the "
                       "game's own for that mood. Then press R.</>", width - 4, max_lines=1)
        listening = self.listening is not None and self.listening == self.current()
        bx = canvas.button(lx, by, "Stop" if listening else "Listen", self.listen, hotkey="Enter")
        bx = canvas.button(bx + 3, by, "Open the folder", self.open_folder, hotkey="O")
        bx = canvas.button(bx + 3, by, "Look for new music", self.rescan, hotkey="R")
        canvas.button(bx + 3, by, "Back", self.close, hotkey="Esc")

    def _render_detail(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        mood = self.current()
        if mood is None or w < 16:
            return
        spec = self.library.moods[mood]
        folder = self.library.user
        lines = [f"<title>{mood.capitalize()}</>", f"<dim>{markup.escape(spec.get('about', ''))}</>", ""]
        if folder is not None:
            lines.append(f"<dim>Folder:</> {markup.escape(str(folder / mood))}")
        mine = self.library.files.get(mood, [])
        shipped = self.library.shipped.get(mood, [])
        if mine:
            lines.append(f"<good>Your tunes:</> " + ", ".join(markup.escape(p.stem) for p in mine[:8]) +
                         (f" and {len(mine) - 8} more" if len(mine) > 8 else ""))
        if shipped:
            lines.append(("<dim>The game's (not played while you have your own):</> " if mine else "<dim>The game's:</> ")
                         + ", ".join(markup.escape(p.stem.replace("_", " ")) for p in shipped))
        if not mine and not shipped:
            pool, _ = self.library.resolve(mood)
            lines.append(f"<dim>No tunes here: it plays {pool}'s.</>" if pool else "<dim>No tunes here: it is quiet.</>")
        kinds = spec.get("kinds", [])
        if kinds:
            parts = []
            for k in kinds:
                n = self.library.count(f"{mood}/{k}")[0]
                parts.append(f"<good>{k} ({n})</>" if n else f"<dim>{k}</>")
            lines += ["", f"<dim>More particular folders inside it (empty ones borrow from {mood}):</>", ", ".join(parts)]
        yy = y
        for line in lines:
            if yy >= y + h:
                break
            yy += max(1, canvas.wrapped(x, yy, line, w, max_lines=max(1, y + h - yy)))

    def _click(self, i: int) -> None:
        now = self.app.clock()
        if i == self.selected and now - getattr(self, "_last", -9.0) < 0.5:
            self.listen()
            return
        self._last = now
        self.selected = i

    def handle_key(self, ev: KeyEvent) -> bool:
        n = len(self.moods())
        if ev.key == "escape":
            self.close()
        elif ev.key == "up" and n:
            self.selected = (self.selected - 1) % n
        elif ev.key == "down" and n:
            self.selected = (self.selected + 1) % n
        elif ev.key in ("enter", " "):
            self.listen()
        elif ev.key in ("o", "O"):
            self.open_folder()
        elif ev.key in ("r", "R"):
            self.rescan()
        else:
            return False
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("down"), KeyEvent("up"), KeyEvent("enter"), KeyEvent("escape")]
