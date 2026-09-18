"""Hidden debug console (the ` key). Disabled in friend builds via config.json.

Commands grow with each milestone; type "help" for the list.
"""

from __future__ import annotations

from collections.abc import Callable

from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas

MAX_HISTORY = 200


class DebugConsole(Screen):
    modal = True
    captures_text = True
    title = "Debug console"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.line = ""
        self.output: list[str] = ["<dim>Debug console. Type</> help <dim>for commands. Esc or ` closes.</>"]
        self.history: list[str] = []
        self.history_pos = 0
        self.commands: dict[str, tuple[Callable[[list[str]], None], str]] = {}
        self._register_builtin()

    def command(self, name: str, help_text: str):
        def deco(fn: Callable[[list[str]], None]):
            self.commands[name] = (fn, help_text)
            return fn

        return deco

    def say(self, text: str) -> None:
        self.output.append(text)
        self.output = self.output[-MAX_HISTORY:]

    def _register_builtin(self) -> None:
        app = self.app

        @self.command("help", "list commands")
        def _help(args):
            for name in sorted(self.commands):
                self.say(f"  <loot>{name}</> <dim>— {self.commands[name][1]}</>")

        @self.command("ai", "ai on|off — switch AI text on or off")
        def _ai(args):
            if args and args[0] in ("on", "off"):
                app.set_ai_enabled(args[0] == "on")
            self.say(f"AI: {app.ai.status_text()[0]}")

        @self.command("offline", "offline on|off — simulate Player2 being closed")
        def _offline(args):
            if args and args[0] in ("on", "off"):
                app.ai.set_simulated_offline(args[0] == "on")
            self.say(f"Simulated offline: {app.ai.simulated_offline}")

        @self.command("ping", "ping Player2 now")
        def _ping(args):
            app.ai.ping_now()
            self.say("Ping requested.")

        @self.command("status", "show AI status, energy and request counts")
        def _status(args):
            ai = app.ai
            self.say(f"{ai.status.value} · version {ai.client_version or '?'} · energy {ai.joules} · {ai.stats}")

        @self.command("font", "font <size> — set text size")
        def _font(args):
            if args and args[0].isdigit():
                app.set_font_size(int(args[0]))
            self.say(f"Text size: {app.settings.font_size}")

        @self.command("notify", "notify <text> — show a message")
        def _notify(args):
            app.notify(" ".join(args) or "Hello.", "info")

        @self.command("test-error", "raise an error on purpose, to check the game recovers")
        def _error(args):
            raise RuntimeError("Deliberate test error from the debug console")

        @self.command("clear", "clear this console")
        def _clear(args):
            self.output.clear()

    def run(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.history.append(text)
        self.history_pos = len(self.history)
        self.say(f"<title>></> {markup.escape(text)}")
        name, *args = text.split()
        entry = self.commands.get(name.lower())
        if entry is None:
            self.say(f"<warn>Unknown command:</> {markup.escape(name)} <dim>(try help)</>")
            return
        entry[0](args)

    # ------------------------------------------------------------------
    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        height = max(8, h // 2)
        y0 = h - height
        canvas.frame(0, y0, w, height, self.title, fg=colors.named("magic"), bg=(12, 10, 18))
        rows = height - 4
        lines: list = []
        for text in self.output:
            lines.extend(markup.wrap(text, w - 4))
        for i, line in enumerate(lines[-rows:]):
            canvas.spans(2, y0 + 1 + i, line, max_width=w - 4)
        canvas.text(2, h - 2, "> " + self.line[-(w - 8):] + "_", colors.SELECT_FG)
        canvas.hit(0, 0, w, h)

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "`", "~"):
            self.close()
        elif ev.key == "enter":
            line, self.line = self.line, ""
            try:
                self.run(line)
            except Exception as exc:
                self.app.report_error(f"running the debug command '{line}'")
                self.say(f"<danger>Error:</> {markup.escape(str(exc))}")
        elif ev.key == "backspace":
            self.line = self.line[:-1]
        elif ev.key == "up" and self.history:
            self.history_pos = max(0, self.history_pos - 1)
            self.line = self.history[self.history_pos]
        elif ev.key == "down" and self.history:
            self.history_pos = min(len(self.history), self.history_pos + 1)
            self.line = self.history[self.history_pos] if self.history_pos < len(self.history) else ""
        elif ev.is_text:
            self.line += ev.key
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(c) for c in "status"] + [KeyEvent("enter"), KeyEvent("escape")]
