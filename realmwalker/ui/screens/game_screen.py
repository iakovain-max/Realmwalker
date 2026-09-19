"""The main game view: the map on the left, the side panel on the right, the message log below."""

from __future__ import annotations

from realmwalker.game.describe import cap, danger_text, describe_local, describe_overworld, temperature_word, typical_temperature
from realmwalker.game.state import GameState
from realmwalker.ui import colors, markup
from realmwalker.ui.input import DIRECTIONS, KeyEvent, MouseEvent
from realmwalker.ui.map_render import OverworldPicture, draw_local, draw_overworld
from realmwalker.ui.screens.base import ConfirmBox, Screen
from realmwalker.ui.widgets import Canvas

PANEL_W = 38
LOG_H = 9
KEY_DIRECTIONS = {**DIRECTIONS, "home": (-1, -1), "pageup": (1, -1), "end": (-1, 1), "pagedown": (1, 1)}
TRAVEL_STEP_SECONDS = 0.04


def key_direction(ev: KeyEvent) -> tuple[int, int] | None:
    if ev.ctrl or ev.alt:
        return None
    return KEY_DIRECTIONS.get(ev.key)


class GameScreen(Screen):
    title = "Realmwalker"

    def __init__(self, app, game: GameState) -> None:
        super().__init__(app)
        self.game = game
        self.picture = OverworldPicture(game.world, app.tables)
        self.look: tuple[int, int] | None = None  # cursor in map cells while in look mode
        self.hover: tuple[int, int] | None = None
        self.view = (0, 0, 0, 0, 0, 0)  # viewport x, y and the camera from the last draw
        self._last_travel_step = 0.0
        self._in_local_before = game.in_local

    @property
    def animating(self) -> bool:  # type: ignore[override]
        return self.game.travel is not None

    # ------------------------------------------------------------------ helpers
    def _map_rect(self, canvas: Canvas) -> tuple[int, int, int, int]:
        # The bottom row is left free for the AI status line.
        return 0, 0, max(20, canvas.width - PANEL_W), max(10, canvas.height - 1 - LOG_H)

    def screen_to_map(self, sx: int, sy: int) -> tuple[int, int] | None:
        vx, vy, mx0, my0, ox, oy = self.view
        x, y = sx - vx - ox + mx0, sy - vy - oy + my0
        if self.game.in_local:
            lm = self.game.local
            return (x, y) if lm is not None and lm.in_bounds(x, y) else None
        return (x, y) if self.game.world.in_bounds(x, y) else None

    def describe(self, x: int, y: int) -> str:
        if self.game.in_local:
            return describe_local(self.game, x, y)
        return describe_overworld(self.game, x, y)

    def player_pos(self) -> tuple[int, int]:
        p = self.game.player
        return (p.lx, p.ly) if self.game.in_local else (p.x, p.y)

    # ------------------------------------------------------------------ actions
    def move(self, dx: int, dy: int) -> None:
        was_local = self.game.in_local
        self.game.move(dx, dy)
        if was_local != self.game.in_local:
            self.app.save_game()

    def enter(self) -> None:
        if self.game.in_local:
            self.game.say("You are already on foot among the details. Walk off the edge, or press < to leave.", "system")
            return
        self.game.enter_local()
        self.app.save_game()

    def leave(self) -> None:
        if self.game.in_local:
            self.game.leave_local()
            self.app.save_game()

    def wait(self) -> None:
        if self.game.in_local:
            self.game.wait(1)
        else:
            self.game.wait(60)
            self.game.say("You rest a while and watch the sky.", "flavor")

    def plan_travel_to(self, dest: tuple[int, int]) -> None:
        from realmwalker.game.describe import describe_overworld

        game = self.game
        if game.in_local:
            game.say("Leave this place first (press <) to travel across country.", "system")
            return
        if game.lost:
            game.say("You have lost your bearings: you can't plan a journey until you find a road or the weather "
                     "clears. Walk (arrow keys) and hope.", "warn")
            return
        plan = game.plan_travel(dest)
        if plan is None:
            game.say("You can see no way to get there on foot.", "warn")
            return
        target = markup.plain(describe_overworld(game, *dest).split("\n")[0])
        text = f"Travel to: {markup.escape(target)}\n\n{game.describe_plan(plan)}.\n\n<dim>Any key stops the journey.</>"

        def go() -> None:
            game.travel = plan
            game.say(f"You set out: {game.describe_plan(plan)}.", "info")

        self.app.push(ConfirmBox(self.app, text, go, title="Set out?"))

    def open_world_map(self, travel: bool = False) -> None:
        from realmwalker.ui.screens.world_map import WorldMapScreen

        self.app.push(WorldMapScreen(self.app, self, travel_mode=travel))

    # ------------------------------------------------------------------ input
    def handle_key(self, ev: KeyEvent) -> bool:
        game = self.game
        if game.travel is not None:
            game.travel = None
            game.say("You stop.", "system")
            return True
        if self.look is not None:
            return self._look_key(ev)
        d = key_direction(ev)
        if d is not None:
            self.move(*d)
        elif ev.key in (".", "5", "wait"):
            self.wait()
        elif ev.key == ">":
            self.enter()
        elif ev.key == "<":
            self.leave()
        elif ev.key == "l":
            self.look = self.player_pos()
        elif ev.key in ("g", ","):
            self.game.pick_up()
        elif ev.key == "r":
            self.rest()
        elif ev.key == "h":
            from realmwalker.ui.screens.health import HealthScreen

            self.app.push(HealthScreen(self.app, game))
        elif ev.key == "w":
            self.water()
        elif ev.key == "W":
            self.wash()
        elif ev.key in ("c", "i", "e"):
            from realmwalker.ui.screens.sheets import CharacterScreen, EquipmentScreen, InventoryScreen

            screen = {"c": CharacterScreen, "i": InventoryScreen, "e": EquipmentScreen}[ev.key]
            self.app.push(screen(self.app, game))
        elif ev.key == "m":
            self.open_world_map()
        elif ev.key == "t":
            self.open_world_map(travel=True)
        elif ev.key == "L":
            from realmwalker.ui.screens.log_screen import LogScreen

            self.app.push(LogScreen(self.app, game))
        elif ev.key == "/":
            from realmwalker.ui.screens.legend import LegendScreen

            self.app.push(LegendScreen(self.app))
        elif ev.key in ("escape", "q"):
            from realmwalker.ui.screens.game_menu import GameMenu

            self.app.push(GameMenu(self.app))
        elif ev.key == "?":
            from realmwalker.ui.screens.help import HelpScreen

            self.app.push(HelpScreen(self.app))
        else:
            return False
        return True

    def _look_key(self, ev: KeyEvent) -> bool:
        d = key_direction(ev)
        if d is not None:
            x, y = self.look
            nx, ny = x + d[0], y + d[1]
            inside = self.game.local.in_bounds(nx, ny) if self.game.in_local else self.game.world.in_bounds(nx, ny)
            if inside:
                self.look = (nx, ny)
        elif ev.key == "enter" and not self.game.in_local:
            dest = self.look
            self.look = None
            self.plan_travel_to(dest)
        elif ev.key in ("escape", "l"):
            self.look = None
        return True

    def handle_mouse(self, ev: MouseEvent) -> bool:
        if ev.kind == "move":
            self.hover = self.screen_to_map(ev.x, ev.y)
            return False
        if ev.kind != "click":
            return False
        target = self.screen_to_map(ev.x, ev.y)
        if target is None:
            return False
        if ev.button == "right":
            self.look = target
            return True
        px, py = self.player_pos()
        dx, dy = target[0] - px, target[1] - py
        if max(abs(dx), abs(dy)) == 1:
            self.move(dx, dy)
        elif (dx, dy) != (0, 0) and not self.game.in_local:
            self.plan_travel_to(target)
        return True

    def _open_event_screen(self) -> bool:
        """Death, the aftermath of a fight, a fight, or trouble on the road take over the screen."""
        game = self.game
        if game.over is not None:
            from realmwalker.ui.screens.aftermath import DeathScreen

            self.app.push(DeathScreen(self.app, game))
        elif game.aftermath is not None:
            from realmwalker.ui.screens.aftermath import AftermathScreen

            self.app.push(AftermathScreen(self.app, game, game.aftermath))
        elif game.battle is not None:
            from realmwalker.ui.screens.battle import BattleScreen

            self.app.push(BattleScreen(self.app, game))
        elif game.talk_to is not None:
            from realmwalker.ui.screens.dialogue import DialogueScreen

            npc = game.world.npcs.get(game.talk_to)
            game.talk_to = None
            if npc is None or not npc.alive:
                return False
            self.app.push(DialogueScreen(self.app, game, npc))
        elif game.event is not None:
            from realmwalker.ui.screens.event import EventScreen

            self.app.push(EventScreen(self.app, game))
        elif game.encounter is not None:
            from realmwalker.ui.screens.encounter import EncounterScreen

            self.app.push(EncounterScreen(self.app, game))
        else:
            return False
        return True

    def _narrate(self) -> None:
        """Write up a finished day on the road: by the AI if it is there, or from built-in text at once."""
        from realmwalker.ai.service import Priority
        from realmwalker.ai.tasks import TRAVEL_DAY, travel_day_fallback
        from realmwalker.game.events import travel_day_facts

        game = self.game
        day = game.narration.pop(0)
        variables = travel_day_facts(game, day)

        def fallback() -> None:
            rng = game.world.rng.child(f"narrate/{game.world.time}")
            text = travel_day_fallback(rng, self.app.data, variables)["passage"]
            game.say(markup.escape(text), "flavor")

        if not self.app.ai.usable():
            fallback()
            return

        def done(result) -> None:
            if result.ok and result.data and result.data.get("passage"):
                game.say(f"<ai>{markup.escape(result.data['passage'])}</>", "flavor")
            else:
                fallback()

        self.app.ai.submit(TRAVEL_DAY, variables, priority=Priority.BACKGROUND, callback=done)

    def water(self) -> None:
        from realmwalker.game.survival import fill_skins

        for text in fill_skins(self.game):
            self.game.say(text, "info")

    def wash(self) -> None:
        from realmwalker.game.survival import wash

        for text in wash(self.game):
            self.game.say(text, "info")

    def rest(self) -> None:
        from realmwalker.ui.screens.camp import CampScreen

        self.app.push(CampScreen(self.app, self.game))

    # ------------------------------------------------------------------ frame
    def update(self) -> None:
        game = self.game
        game.show_dice = self.app.settings.show_dice
        game.auto_supplies = self.app.settings.auto_supplies
        if self._open_event_screen():
            return
        if game.narration:
            self._narrate()
        if game.travel is not None:
            now = self.app.clock()
            if now - self._last_travel_step >= TRAVEL_STEP_SECONDS or self.app.headless:
                self._last_travel_step = now
                if not game.travel_step():
                    self.app.save_game()
        self.app.maybe_autosave()

    def render(self, canvas: Canvas) -> None:
        game = self.game
        mx, my, mw, mh = self._map_rect(canvas)
        cursor = self.look
        if game.in_local and game.local is not None:
            camera = draw_local(canvas.con, game, mx, my, mw, mh, cursor)
        else:
            if game.in_local:
                game.player.local_key = None
            camera = draw_overworld(canvas.con, game, self.picture, mx, my, mw, mh, cursor)
        self.view = (mx, my, *camera)
        canvas.hit(mx, my, mw, mh, tooltip=None)
        self._render_panel(canvas, mw, 0, canvas.width - mw, canvas.height - 1)
        self._render_log(canvas, 0, mh, mw, canvas.height - 1 - mh)

    def _render_panel(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        game = self.game
        p = game.player
        canvas.frame(x, y, w, h, markup.escape(game.leader.name), fg=colors.BORDER, bg=colors.PANEL_BG)
        ix, iw = x + 2, w - 4
        row = y + 2
        row = self._render_party(canvas, ix, row, iw) + 1
        m = game.moment
        canvas.text(ix, row, m.date_text(), colors.TITLE, max_width=iw)
        row += 1
        canvas.text(ix, row, f"{m.year} {m.cal.era}", colors.DIM, max_width=iw)
        row += 1
        part = m.part_of_day(game.latitude)
        canvas.markup(ix, row, f"{m.time_text()} · {part} · {m.season}", max_width=iw)
        row += 1
        from realmwalker.world.weather import describe as describe_weather

        row += canvas.wrapped(ix, row, f"<info>{describe_weather(game.weather)}</>", iw, max_lines=2)
        temp = typical_temperature(game, p.x, p.y)
        canvas.markup(ix, row, f"<dim>Usually</> {temperature_word(temp)} <dim>this month</>", max_width=iw)
        row += 2

        canvas.section(ix, row, iw, "Where")
        row += 1
        world = game.world
        area = world.area_at(p.x, p.y)
        settlement = world.settlement_at(p.x, p.y)
        if settlement is not None:
            kind = game.tables.sites["settlement_types"][settlement.kind]["name"]
            canvas.markup(ix, row, f"<place>{settlement.name}</> <dim>({kind})</>", max_width=iw)
            row += 1
        if area is not None:
            canvas.markup(ix, row, f"<place>{cap(area.name)}</>", max_width=iw)
            row += 1
        canvas.text(ix, row, cap(game.biome_def(p.x, p.y)["name"]) + (" · on the road" if world.road[p.x, p.y] else ""),
                    colors.FG, max_width=iw)
        row += 1
        canvas.markup(ix, row, f"Wilds: {danger_text(int(world.danger[p.x, p.y]))}", max_width=iw)
        row += 1
        if game.in_local:
            lm = game.local
            b = lm.building_at(p.lx, p.ly) if lm else None
            canvas.markup(ix, row, "<dim>On foot, looking closely" + (f"; inside a {b.kind}" if b else "") + ".</>", max_width=iw)
            row += 1
        if game.lost:
            canvas.markup(ix, row, "<warn>Lost: you don't know which way you're going.</>", max_width=iw)
            row += 1
        if game.travel is not None:
            row += 1
            canvas.markup(ix, row, f"<good>Travelling</> <dim>— {len(game.travel.path) * 3} miles to go</>", max_width=iw)
            row += 1
        row += 1

        target = self.look or self.hover
        if target is not None:
            canvas.section(ix, row, iw, "Looking at" if self.look else "Under the mouse")
            row += 1
            text = self.describe(*target)
            used = canvas.wrapped(ix, row, text, iw, max_lines=max(1, h - row - 9))
            row += used + 1
            if self.look is not None:
                hint = "arrows move · Enter: travel there · Esc: stop" if not game.in_local else "arrows move · Esc: stop looking"
                canvas.text(ix, row, hint, colors.FAINT, max_width=iw)

        keys = [
            ("arrows", "walk"), (">", "enter the land here") if not game.in_local else ("<", "back to the overworld"),
            ("l", "look"), ("m t", "world map · travel"), ("c i e", "character · pack · gear"),
            ("g", "pick up") if game.in_local else (".", "wait an hour"), ("r h", "camp · health"),
            ("w W", "water · wash"), ("L /", "log · legend"), ("Esc", "menu"),
        ]
        ky = h - len(keys) - 1
        for key, what in keys:
            if ky > row:
                canvas.markup(ix, ky, f"<loot>{key:>6}</> <dim>{what}</>", max_width=iw)
            ky += 1

    def _render_party(self, canvas: Canvas, x: int, y: int, w: int) -> int:
        from realmwalker.rules.character import Sheet
        from realmwalker.rules.items import money_text
        from realmwalker.ui.screens.sheets import ENCUMBRANCE_WORDS

        game = self.game
        for member in game.party:
            s = Sheet(member, game.tables)
            ratio = member.hp / max(1, member.max_hp)
            color = "good" if ratio > 0.6 else ("warn" if ratio > 0.3 else "danger")
            bar_w = max(4, w - 22)
            filled = int(round(bar_w * ratio))
            cls = game.tables.classes[member.cls]["name"]
            canvas.markup(x, y, f"<name>{markup.escape(member.name.split()[0])}</> <dim>{cls} {member.level}</>", max_width=w)
            y += 1
            canvas.text(x, y, "█" * filled, colors.named(color))
            canvas.text(x + filled, y, "░" * (bar_w - filled), colors.FAINT)
            canvas.markup(x + bar_w + 1, y, f"<{color}>{member.hp}/{member.max_hp}</> <dim>AC</> {s.armor_class()}", max_width=w - bar_w - 1)
            canvas.hit(x, y - 1, w, 2, action=lambda: self.handle_key(KeyEvent("c")),
                       tooltip="Click (or press c) for the character sheet.")
            y += 1
            enc = s.encumbrance()
            word, ecolor = ENCUMBRANCE_WORDS[enc]
            load = "" if enc == 0 else f" · <{ecolor}>{word}</>"
            canvas.markup(x, y, f"<loot>{money_text(member.money)}</>{load}", max_width=w)
            y += 1
            from realmwalker.ui.screens.health import status_words

            words = status_words(member, game.tables)
            if words:
                used = canvas.wrapped(x, y, " · ".join(words), w, max_lines=2)
                canvas.hit(x, y, w, used, action=lambda: self.handle_key(KeyEvent("h")),
                           tooltip="Click (or press h) for the Health screen.")
                y += used
        return y

    def _render_log(self, canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
        canvas.frame(x, y, w, h, "Messages", fg=colors.FAINT, bg=colors.PANEL_BG, title_fg=colors.DIM)
        inner = w - 4
        lines: list = []
        for msg in self.game.log.recent(h * 2):
            color = colors.named(msg.color)
            text = msg.text + (f" <dim>(×{msg.count})</>" if msg.count > 1 else "")
            lines.extend(markup.wrap(text, inner, color))
        visible = lines[-(h - 2):]
        for i, line in enumerate(visible):
            canvas.spans(x + 2, y + 1 + i, line, max_width=inner)
        canvas.hit(x, y, w, h, action=self._open_log, tooltip="Click (or press L) for the full message log.")

    def _open_log(self) -> None:
        from realmwalker.ui.screens.log_screen import LogScreen

        self.app.push(LogScreen(self.app, self.game))

    def autoplay_keys(self) -> list[KeyEvent]:
        moves = [KeyEvent(k) for k in ("up", "down", "left", "right", "upleft", "upright", "downleft", "downright")]
        return moves * 4 + [KeyEvent(k) for k in (">", "<", "l", "enter", "escape", ".", "m", "t", "L", "/",
                                                   "c", "i", "e", "g", "r", "h", "w", "W")]
