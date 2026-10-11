"""The Screen base class and a few small modal screens used everywhere."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from realmwalker.ui import colors
from realmwalker.ui.input import KeyEvent, MouseEvent
from realmwalker.ui.widgets import Canvas

if TYPE_CHECKING:
    from realmwalker.app import App


class Screen:
    """One screen in the stack. Modal screens draw on top of the screen below them."""

    modal = False
    show_status = True  # draw the AI status indicator in the corner
    captures_text = False  # true while typing into a text field (disables single-key global hotkeys)
    title = ""
    sound_open: str | None = "ui_open"  # sounds (data/sounds.json) as the screen opens and closes
    sound_close: str | None = "ui_close"
    key_sounds = True  # a quiet sound when a key visibly changes the screen (off where keys walk or fight)

    def __init__(self, app: App) -> None:
        self.app = app

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass

    def render(self, canvas: Canvas) -> None:
        raise NotImplementedError

    def handle_key(self, ev: KeyEvent) -> bool:
        return False

    def handle_mouse(self, ev: MouseEvent) -> bool:
        return False

    def update(self) -> None:
        pass

    def music(self) -> str | None:
        """The music this screen wants (a mood from data/music.json, e.g. "travel/forest"), or None to keep the
        music of the screen beneath it."""
        return None

    def autoplay_keys(self) -> list[KeyEvent]:
        """Sensible keys for the headless autoplay bot to press on this screen."""
        return [KeyEvent("escape")]

    def close(self) -> None:
        if self.app.top is self:
            self.app.pop()


def modal_box(canvas: Canvas, width: int, height: int, title: str = "", *, fg=colors.BORDER, double: bool = True) -> tuple[int, int, int, int]:
    """Draw a centred dialog frame; returns (x, y, w, h) of the whole box."""
    w = min(width, canvas.width - 2)
    h = min(height, canvas.height - 2)
    x = (canvas.width - w) // 2
    y = (canvas.height - h) // 2
    canvas.frame(x, y, w, h, title, fg=fg, double=double)
    return x, y, w, h


class MessageBox(Screen):
    """A modal notice. Any key closes it."""

    modal = True

    def __init__(self, app: App, title: str, text: str, *, color=colors.BORDER, on_close: Callable[[], None] | None = None) -> None:
        super().__init__(app)
        self.title = title
        self.text = text
        self.color = color
        self.on_close = on_close

    def render(self, canvas: Canvas) -> None:
        from realmwalker.ui import markup

        width = min(70, canvas.width - 4)
        lines = markup.wrap(self.text, width - 4)
        x, y, w, h = modal_box(canvas, width, len(lines) + 5, self.title, fg=self.color)
        for i, line in enumerate(lines):
            canvas.spans(x + 2, y + 2 + i, line, max_width=w - 4)
        canvas.button(x + 2, y + h - 2, "Continue", self._close, hotkey="Enter")
        canvas.hit(0, 0, canvas.width, canvas.height)  # swallow clicks outside the box

    def _close(self) -> None:
        self.close()
        if self.on_close:
            self.on_close()

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("enter", "escape", " "):
            self._close()
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("enter")]


class ChoiceBox(Screen):
    """A short list to choose from (who to talk to, of those beside you): a number, the arrows and Enter, or a click.
    Escape chooses nothing."""

    modal = True

    def __init__(self, app: App, title: str, choices: list[tuple[str, Callable[[], None]]]) -> None:
        super().__init__(app)
        self.title = title
        self.choices = choices[:9]
        self.selected = 0

    def render(self, canvas: Canvas) -> None:
        from realmwalker.ui import markup

        width = min(60, canvas.width - 4)
        x, y, w, h = modal_box(canvas, width, len(self.choices) + 4, self.title)
        for i, (label, _) in enumerate(self.choices):
            row = y + 2 + i
            mark = "►" if i == self.selected else " "
            canvas.text(x + 2, row, mark, colors.named("gold"))
            canvas.button(x + 4, row, markup.plain(label), lambda i=i: self._pick(i), hotkey=str(i + 1),
                          max_width=w - 6)
        canvas.hit(0, 0, canvas.width, canvas.height)  # swallow clicks outside the box

    def _pick(self, i: int) -> None:
        self.close()
        self.choices[i][1]()

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "q"):
            self.close()
        elif ev.key.isdigit() and 1 <= int(ev.key) <= len(self.choices):
            self._pick(int(ev.key) - 1)
        elif ev.key in ("up", "k8", "8"):
            self.selected = (self.selected - 1) % len(self.choices)
        elif ev.key in ("down", "k2", "2"):
            self.selected = (self.selected + 1) % len(self.choices)
        elif ev.key in ("enter", " "):
            self._pick(self.selected)
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("1"), KeyEvent("escape")]


class ConfirmBox(Screen):
    """Yes/no question before anything dangerous or irreversible."""

    modal = True

    def __init__(self, app: App, question: str, on_yes: Callable[[], None], on_no: Callable[[], None] | None = None,
                 *, title: str = "Are you sure?", danger: bool = False) -> None:
        super().__init__(app)
        self.question = question
        self.on_yes = on_yes
        self.on_no = on_no
        self.title = title
        self.danger = danger

    def render(self, canvas: Canvas) -> None:
        from realmwalker.ui import markup

        width = min(64, canvas.width - 4)
        lines = markup.wrap(self.question, width - 4)
        color = colors.named("danger") if self.danger else colors.BORDER
        x, y, w, h = modal_box(canvas, width, len(lines) + 5, self.title, fg=color)
        for i, line in enumerate(lines):
            canvas.spans(x + 2, y + 2 + i, line, max_width=w - 4)
        bx = canvas.button(x + 2, y + h - 2, "Yes", self._yes, hotkey="Y")
        canvas.button(bx + 3, y + h - 2, "No", self._no, hotkey="N")

    def _yes(self) -> None:
        self.close()
        self.on_yes()

    def _no(self) -> None:
        self.close()
        if self.on_no:
            self.on_no()

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("y", "Y"):
            self._yes()
        elif ev.key in ("n", "N", "escape"):
            self._no()
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("y"), KeyEvent("n")]
