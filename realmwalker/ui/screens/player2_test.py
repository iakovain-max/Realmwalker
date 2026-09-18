"""Player2 connection test: status, health ping, energy, one sample generation, and the fallback."""

from __future__ import annotations

from realmwalker.ai import client as p2client
from realmwalker.ai.service import AIResult, AIStatus, Priority, Ticket
from realmwalker.ai.tasks import SAMPLE_TAVERN, sample_tavern_fallback, sample_tavern_variables
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas

WAIT_TIMEOUT = 45.0  # seconds before we give up on the AI and show built-in text
SPINNER = "|/-\\"


class Player2TestScreen(Screen):
    title = "Player2 Connection Test"
    animating = True

    def __init__(self, app) -> None:
        super().__init__(app)
        self.ticket: Ticket | None = None
        self.started = 0.0
        self.result: dict | None = None
        self.result_source = ""
        self.result_note = ""
        self.frame = 0

    # ------------------------------------------------------------------ actions
    def generate(self) -> None:
        if self.ticket is not None:
            return
        rng = self.app.ui_rng.child(f"tavern{self.frame}")
        variables = sample_tavern_variables(rng, self.app.data)
        self._variables = variables
        self._fallback_rng = rng.child("fallback")
        self.result = None
        if not self.app.ai.usable() and self.app.ai.status != AIStatus.CONNECTING:
            self._show_fallback(f"AI not available: {self.app.ai.status_text()[0]}")
            return
        self.started = self.app.clock()
        self.ticket = self.app.ai.submit(SAMPLE_TAVERN, variables, priority=Priority.URGENT, callback=self._done)

    def _done(self, result: AIResult) -> None:
        self.ticket = None
        if result.ok and result.data:
            self.result = result.data
            self.result_source = "ai"
            retry = ", needed one retry" if result.attempts > 1 else ""
            self.result_note = f"Written by the Player2 AI in {result.elapsed:.1f} s ({result.tokens} tokens{retry})."
        else:
            self._show_fallback(f"AI failed: {result.error}")

    def _show_fallback(self, reason: str) -> None:
        self.result = sample_tavern_fallback(self._fallback_rng, self.app.data, self._variables)
        self.result_source = "fallback"
        self.result_note = f"Built-in text, used instantly. ({reason})"

    def toggle_simulated_offline(self) -> None:
        ai = self.app.ai
        ai.set_simulated_offline(not ai.simulated_offline)
        self.app.notify("Simulating AI offline" if ai.simulated_offline else "Simulation off; reconnecting", "info")

    def ping(self) -> None:
        self.app.ai.ping_now()
        self.app.notify("Pinging Player2…", "info")

    # ------------------------------------------------------------------ frame
    def update(self) -> None:
        self.frame += 1
        if self.ticket is not None and self.app.clock() - self.started > WAIT_TIMEOUT:
            self.ticket.cancel()
            self.ticket = None
            self._show_fallback(f"AI took longer than {WAIT_TIMEOUT:.0f} s")

    def render(self, canvas: Canvas) -> None:
        ai = self.app.ai
        w, h = canvas.width, canvas.height
        width = min(110, w - 2)
        x0 = (w - width) // 2
        canvas.frame(x0, 0, width, h - 1, self.title, double=True)
        x = x0 + 2
        inner = width - 4
        y = 2

        label, color = ai.status_text()
        detected = p2client.app_detected()
        base_url = self.app.config.player2_base_url or p2client.discover_base_url()
        rows = [
            ("Player2 app", "<good>running</> (found its port file)" if detected else "<warn>not detected</> (it may be closed)"),
            ("API address", markup.escape(base_url)),
            ("Status", f"<{color}>● {label}</>" + (f"  <dim>(Player2 v{ai.client_version})</>" if ai.client_version else "")),
            ("Health ping", self._ping_text()),
            ("Energy", self._energy_text()),
            ("Game client ID", "set" if self.app.config.player2_game_client_id else "<dim>not set (optional, not needed)</>"),
            ("Requests", f"sent {ai.stats['sent']} · ok {ai.stats['ok']} · failed {ai.stats['failed']} · "
                         f"retried {ai.stats['retried']} · refused {ai.stats['refused']}"),
        ]
        for name, value in rows:
            canvas.text(x, y, f"{name}:", colors.DIM)
            canvas.markup(x + 17, y, value, max_width=inner - 17)
            y += 1
        if ai.last_error and ai.status != AIStatus.ONLINE:
            canvas.markup(x + 17, y, f"<dim>{markup.escape(ai.last_error)}</>", max_width=inner - 17)
            y += 1

        y += 1
        bx = canvas.button(x, y, "Generate a sample tavern", self.generate, hotkey="G",
                           tooltip="One AI call that writes a whole tavern. Uses a little Player2 energy.")
        bx = canvas.button(bx + 3, y, "Ping now", self.ping, hotkey="P")
        sim = "ON" if ai.simulated_offline else "off"
        bx = canvas.button(bx + 3, y, f"Simulate AI offline: {sim}", self.toggle_simulated_offline, hotkey="O",
                           tooltip="Pretend Player2 is closed, to see the built-in text without closing the app.")
        canvas.button(bx + 3, y, "Back", self.close, hotkey="Esc")
        y += 2

        canvas.section(x, y, inner, "Result")
        y += 1
        if self.ticket is not None:
            spin = SPINNER[self.frame // 3 % len(SPINNER)]
            waited = self.app.clock() - self.started
            canvas.markup(x, y, f"<ai>{spin} Waiting for Player2… {waited:.0f} s</>  <dim>(built-in text after {WAIT_TIMEOUT:.0f} s)</>")
            y += 2
        elif self.result is None:
            canvas.markup(x, y, "<dim>Press G to generate a sample.</>")
            y += 2
        else:
            y = self._render_result(canvas, x, y, inner, h - 12)

        y = max(y + 1, h - 10)
        canvas.section(x, y, inner, "How to test the fallback")
        steps = [
            "1. Close the Player2 app completely (right-click its icon by the clock, then Quit).",
            "2. Within about 15 seconds the status above turns orange: \"AI offline\".",
            "3. Press G. A tavern appears at once, written from the game's built-in text.",
            "4. Start Player2 again. Within about 15 seconds the status is green again.",
        ]
        for i, step in enumerate(steps):
            canvas.text(x, y + 1 + i, step, colors.DIM, max_width=inner)

    def _render_result(self, canvas: Canvas, x: int, y: int, width: int, max_y: int) -> int:
        r = self.result or {}
        source_tag = "<ai>AI text</>" if self.result_source == "ai" else "<warn>Built-in text</>"
        canvas.markup(x, y, f"{source_tag} <dim>— {markup.escape(self.result_note)}</>", max_width=width)
        y += 2
        canvas.markup(x, y, f"<place>{markup.escape(r.get('name', ''))}</>", max_width=width)
        y += 1
        for label, key in (("", "sign"), ("", "description")):
            y += canvas.wrapped(x, y, markup.escape(r.get(key, "")), width, max_lines=max(1, max_y - y))
        y += 1
        y += canvas.wrapped(x, y, f"Keeper: <name>{markup.escape(r.get('keeper', ''))}</>. {markup.escape(r.get('manner', ''))}",
                            width, max_lines=3)
        y += canvas.wrapped(x, y, f"<dim>Overheard:</> {markup.escape(r.get('overheard', ''))}", width, max_lines=3)
        return y

    def _ping_text(self) -> str:
        ai = self.app.ai
        if ai.status == AIStatus.DISABLED:
            return "<dim>not pinging (AI is switched off in Settings)</>"
        if ai.simulated_offline:
            return "<dim>paused while simulating offline</>"
        if ai.last_ping_at is None:
            return "<dim>waiting for the first ping…</>"
        ago = self.app.clock() - ai.last_ping_at
        result = "<good>OK</>" if ai.last_ping_ok else "<warn>no answer</>"
        interval = ai.ping_interval if ai.status == AIStatus.ONLINE else ai.retry_interval
        return f"{ago:.0f} s ago — {result} <dim>(every {interval:.0f} s)</>"

    def _energy_text(self) -> str:
        ai = self.app.ai
        if ai.joules is None:
            return "<dim>unknown</>"
        tier = f" <dim>({markup.escape(ai.patron_tier)})</>" if ai.patron_tier else ""
        color = "good" if ai.joules > 20 else ("warn" if ai.joules > 0 else "danger")
        return f"<{color}>{ai.joules}</> joules left today{tier}"

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("g", "G"):
            self.generate()
        elif ev.key in ("p", "P"):
            self.ping()
        elif ev.key in ("o", "O"):
            self.toggle_simulated_offline()
        elif ev.key == "escape":
            self.close()
        else:
            return False
        return True

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("g"), KeyEvent("g"), KeyEvent("o"), KeyEvent("p"), KeyEvent("escape")]
