"""Hidden debug console (the ` key). Switched off by config.json (debug_console).

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

        def need_game():
            if app.game is None:
                self.say("<warn>Start or continue a game first.</>")
            return app.game

        @self.command("fight", "fight <group> — meet an encounter group (fight list: show groups)")
        def _fight(args):
            game = need_game()
            if game is None:
                return
            groups = sorted(app.tables.creatures.encounters)
            if not args or args[0] == "list" or args[0] not in groups:
                self.say("Groups: " + ", ".join(groups))
                return
            from realmwalker.game.encounters import make_encounter

            if game.busy:
                self.say("<warn>Finish what is happening first.</>")
                return
            game.encounter = make_encounter(game, args[0], game.world.rng.child(f"debug/{game.world.time}/{args[0]}"))
            self.close()

        @self.command("quest", "quest <kind> — take on work of that kind (quest list: show kinds)")
        def _quest(args):
            game = need_game()
            if game is None:
                return
            from realmwalker.game import quests
            from realmwalker.game.people import npcs_in

            kinds = sorted(quests.spec(game)["templates"])
            if not args or args[0] == "list" or args[0] not in kinds:
                self.say("Kinds: " + ", ".join(kinds))
                return
            kind = args[0]
            here = game.world.settlement_at(game.player.x, game.player.y)
            folk = [n for n in npcs_in(game.world, here.id) if n.alive] if here is not None else []
            folk = [n for n in folk if n.job in quests.spec(game)["templates"][kind]["givers"]] or folk
            if not folk:
                self.say("<warn>Stand in a town with people in it first (> to enter it).</>")
                return
            rng = game.world.rng.child(f"debug-quest/{game.world.time}/{kind}")
            q = quests.make_offer(game, folk[0], rng, kind)
            if q is None:
                self.say(f"<warn>Nothing in this world fits '{kind}' from here.</>")
                return
            for text in quests.accept(game, q):
                self.say(text)
            self.say(f"<good>{quests.title(game, q)}</> — {quests.pitch(game, q)}")

        @self.command("heal", "heal the party fully (and close wounds)")
        def _heal(args):
            game = need_game()
            if game is None:
                return
            for c in game.party:
                c.hp = c.max_hp
                c.wounds.clear()
            self.say("Healed.")

        @self.command("gold", "gold <n> — give the leader n gold pieces")
        def _gold(args):
            game = need_game()
            if game is not None and args and args[0].lstrip("-").isdigit():
                game.leader.money = max(0, game.leader.money + int(args[0]) * 100)
                self.say(f"Money: {game.leader.money // 100} gp")

        @self.command("xp", "xp <n> — give the leader experience")
        def _xp(args):
            game = need_game()
            if game is not None and args and args[0].isdigit():
                from realmwalker.rules.progression import award_xp

                for note in award_xp(game.leader, int(args[0]), app.tables, game.world.rng.child("debug-xp")):
                    self.say(note)
                self.say(f"Level {game.leader.level}, {game.leader.xp} XP")

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
