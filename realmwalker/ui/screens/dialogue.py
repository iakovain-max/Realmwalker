"""Talking to someone: what they say, what you say, and the menu of what you can say next."""

from __future__ import annotations

from realmwalker.game.dialogue import Conversation
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas

AI_TALK_TIMEOUT = 9.0  # seconds to wait for the AI's opening line before using built-in text


class DialogueScreen(Screen):
    title = "Talk"

    def __init__(self, app, game, npc) -> None:
        super().__init__(app)
        self.game = game
        self.npc = npc
        self.ticket = None
        self._asked_attack = False  # the confirmation for drawing steel is asked once
        self.asked_at = 0.0
        wants_ai = npc.notable and app.ai.usable() and npc.flags.get("ai_day") != game.moment.total_days
        self.conv = Conversation(game, npc, defer_greeting=wants_ai)
        self.scroll = 0
        if wants_ai:
            self.ask_ai()

    def ask_ai(self) -> None:
        """Ask the AI for their opening line and special options; the built-in ones stand in if it is slow."""
        from realmwalker.ai.service import Priority
        from realmwalker.ai.tasks import DIALOGUE
        from realmwalker.game.people_ai import apply_dialogue, dialogue_variables

        conv = self.conv
        conv.pending_ai = True
        self.asked_at = self.app.clock()

        def done(result) -> None:
            if not conv.pending_ai:
                return  # too late: the built-in lines are already in use
            conv.pending_ai = False
            if result.ok and result.data:
                apply_dialogue(conv, result.data)
            conv.greet()

        self.ticket = self.app.ai.submit(DIALOGUE, dialogue_variables(self.game, self.npc), priority=Priority.URGENT,
                                         callback=done)

    def update(self) -> None:
        conv = self.conv
        if conv.pending_ai and self.app.clock() - self.asked_at > AI_TALK_TIMEOUT:
            conv.pending_ai = False
            if self.ticket is not None:
                self.ticket.cancel()
            conv.greet()

    # ------------------------------------------------------------------ actions
    def hotkeys(self) -> dict[str, int]:
        """Key -> menu index: letters for the fixed entries, numbers for everything else."""
        fixed = {"threaten": "t", "offer_bribe": "o", "goodbye": "g", "back": "b", "attack": "a"}
        spare = [str(d) for d in range(1, 10)] + list("cdefhijklmnpqrsuvwxyz")
        keys: dict[str, int] = {}
        n = 0
        for i, choice in enumerate(self.conv.menu()):
            if choice.id in fixed:
                keys[fixed[choice.id]] = i
            elif n < len(spare):
                keys[spare[n]] = i
                n += 1
        return keys

    def choose(self, i: int) -> None:
        menu = self.conv.menu()
        if not 0 <= i < len(menu):
            return
        choice = menu[i]
        if not choice.enabled:
            self.app.notify(choice.why or "You can't.", "warn")
            return
        if choice.id == "attack" and not self._asked_attack:
            self._confirm_attack(choice)
            return
        request = self.conv.choose(choice)
        self.scroll = 0
        if request:
            self.open_request(request, choice)
        if self.conv.ended:
            self.finish()

    def _confirm_attack(self, choice) -> None:
        """Drawing steel on somebody in their own town is not a thing to do by pressing a key twice."""
        from realmwalker.ui.screens.base import ConfirmBox

        npc = self.npc
        what = "a guard of the watch" if npc.job == "guard" else f"the {markup.escape(npc.title)}"
        warning = " The watch will come, and the town will remember it." if self.game.world.factions else ""

        def yes() -> None:
            self._asked_attack = True
            self.choose(self.conv.menu().index(choice) if choice in self.conv.menu() else 0)

        self.app.push(ConfirmBox(self.app, f"Draw steel on {what}?{warning}", yes, title="Attack?", danger=True))

    def open_request(self, request: str, choice) -> None:
        """Trade and service windows (M5 parts 3 and 4)."""
        from realmwalker.ui.screens import trade

        trade.open_request(self, request, choice)

    def finish(self) -> None:
        if self.conv.pending_ai:
            self.conv.pending_ai = False
            if self.ticket is not None:
                self.ticket.cancel()
        if self.conv.minutes:
            self.game.pass_time(self.conv.minutes, "rest")
        self.game.dirty = True
        self.close()

    # ------------------------------------------------------------------ input
    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key == "escape":
            if self.conv.mode != "main":
                self.conv.mode = "main"
            else:
                self.conv.goodbye()
                self.finish()
        elif ev.is_text and ev.key in self.hotkeys():
            self.choose(self.hotkeys()[ev.key])
        elif ev.key in ("pageup", "up"):
            self.scroll += 3
        elif ev.key in ("pagedown", "down"):
            self.scroll = max(0, self.scroll - 3)
        return True

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        npc = self.npc
        conv = self.conv
        w, h = canvas.width, canvas.height
        title = f"{npc.first_name}, the {npc.title}" if npc.known else f"The {npc.title}"
        canvas.frame(0, 0, w, h - 1, markup.escape(title), double=True)
        side = w >= 110
        text_w = (w - 40) if side else (w - 4)
        mood = npc.mood()
        mood_color = {"hostile": "danger", "unfriendly": "warn", "neutral": "dim", "friendly": "good", "warm": "good"}[mood]
        header = f"<name>{markup.escape(npc.name if npc.known else 'The ' + npc.title)}</> <dim>·</> <{mood_color}>{mood}</>"
        if conv.pending_ai:
            header += " <dim>· …</>"
        canvas.markup(2, 1, header, max_width=text_w)
        menu = conv.menu()
        # Choices matter more than the words already said: give the menu the room it needs, within reason.
        menu_h = min(len(menu), max(6, h - 12)) + 1
        log_top, log_bottom = 3, h - 3 - menu_h
        # The conversation so far.
        lines: list = []
        for who, text in conv.lines:
            if not text:
                continue
            if who == "you":
                lines += markup.wrap(f"<title>You:</> <dim>{text}</>", text_w)
            elif who == "note":
                lines += markup.wrap(f"<dim>{text}</>", text_w)
            else:
                lines += markup.wrap(text, text_w)
            lines.append([])
        avail = max(1, log_bottom - log_top)
        self.scroll = min(self.scroll, max(0, len(lines) - avail))
        end = max(0, len(lines) - self.scroll)
        for i, line in enumerate(lines[max(0, end - avail):end]):
            canvas.spans(2, log_top + i, line, max_width=text_w)
        canvas.hline(1, log_bottom, text_w + 2, "─", colors.FAINT)
        # The menu.
        by_index = {i: k for k, i in self.hotkeys().items()}
        for i, choice in enumerate(menu[: menu_h - 1]):
            y = log_bottom + 1 + i
            key = by_index.get(i, " ")
            if choice.enabled:
                canvas.button(2, y, markup.plain(choice.label)[: text_w - 5], lambda i=i: self.choose(i), hotkey=key)
            else:
                label = markup.escape(markup.plain(choice.label)).rstrip(".")
                canvas.markup(2, y, f"<faint>[{key}] {label} — {choice.why}</>",
                              max_width=text_w)
        hidden = len(menu) - (menu_h - 1)
        if hidden > 0:
            canvas.markup(2, log_bottom + menu_h, f"<dim>… and {hidden} more (press the letter shown for them, "
                                                  f"or make the window bigger)</>", max_width=text_w)
        if side:
            self._render_side(canvas, w - 36, 2, 34, h - 5)
        canvas.text(2, h - 2, "1-9 or the letter shown to choose · ↑↓ scroll · Esc leave", colors.FAINT, max_width=w - 4)

    def _render_side(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        npc = self.npc
        if canvas.gfx is not None:
            y = self._portrait(canvas, x, y, w)
        canvas.section(x, y, w, "What you know")
        y += 1
        facts = [f"<dim>{npc.age}, {self.game.tables.races.get(npc.race, {}).get('name', npc.race)}</>"]
        if npc.profile.get("appearance"):
            facts.append(markup.escape(npc.profile["appearance"]))
        if npc.known and npc.mood() in ("neutral", "friendly", "warm") and npc.profile.get("personality"):
            facts.append(markup.escape(npc.profile["personality"]))
        if npc.memory:
            facts.append("<dim>They remember: " + "; ".join(markup.escape(m) for m in npc.memory[-3:]) + ".</>")
        for f in facts:
            if y >= h:
                break
            y += canvas.wrapped(x, y, f, w, max_lines=6) + 1

    def _portrait(self, canvas: Canvas, x: int, y: int, w: int) -> int:
        """The person, large, in the light of where you meet them; their trade and mood under it."""
        from realmwalker.ui.gfx import dolls, theme
        from realmwalker.ui.gfx.scene import Rect, Text

        npc = self.npc
        cw, ch = canvas.cell_w, canvas.cell_h
        rows = 9
        canvas.clear_cells(x, y, w, rows)
        px, py, pw, phh = x * cw, y * ch, w * cw, rows * ch
        indoors = False
        lm = self.game.local
        if lm is not None:
            indoors = lm.building_at(self.game.player.lx, self.game.player.ly) is not None
        top, bottom = ((46, 34, 26), (20, 14, 12)) if indoors else ((70, 84, 104), (34, 40, 36))
        canvas.under(Rect(px, py, pw, phh, (*top, 255), bottom=(*bottom, 255)))
        canvas.under(*theme.panel(px, py, pw, phh, "inset", ornaments=False))
        canvas.under(Rect(px + 4, py + phh * 0.72, pw - 8, phh * 0.28 - 4, (0, 0, 0, 60)))
        size = min(pw - 20, phh - 30)
        mood_tint = {"hostile": (255, 200, 190), "unfriendly": (245, 225, 210)}.get(npc.mood(), (255, 255, 255))
        for name in dolls.npc(npc, self.game.tables):
            canvas.sprite(name, px + (pw - size) / 2, py + phh - size - 8, size, size, (*mood_tint, 255), over=False)
        trade = self.game.tables.people["occupations"].get(npc.job, {}).get("name", npc.job.replace("_", " "))
        canvas.over(Text(px + pw / 2, py + 6, npc.name if npc.known else f"the {npc.title}",
                         "heading", 16, (214, 176, 108, 255), anchor="mt", outline=True, shadow=False))
        canvas.over(Text(px + pw / 2, py + 26, str(trade), "prose", 15, (200, 190, 170, 255), anchor="mt",
                         outline=True, shadow=False))
        return y + rows + 1

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(str(i)) for i in range(1, 9)] + [KeyEvent(k) for k in ("t", "o", "b", "escape")]
