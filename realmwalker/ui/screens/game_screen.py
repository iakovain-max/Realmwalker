"""The main game view: the map on the left, the side panel on the right, the message log below."""

from __future__ import annotations

import numpy as np

from realmwalker.game.describe import describe_local, describe_overworld
from realmwalker.game.state import GameState
from realmwalker.rules import progression
from realmwalker.ui import colors, markup
from realmwalker.ui.input import DIRECTIONS, KeyEvent, MouseEvent
from realmwalker.ui.screens.base import ConfirmBox, Screen
from realmwalker.ui.widgets import Canvas

from realmwalker.ui.hud import BAR_H, LOG_H, PANEL_W  # noqa: E402
KEY_DIRECTIONS = {**DIRECTIONS, "home": (-1, -1), "pageup": (1, -1), "end": (-1, 1), "pagedown": (1, 1)}
TRAVEL_STEP_SECONDS = 0.04
WALK_STEP_SECONDS = 0.03  # a walk across a close-up map, one step a frame or so
TOWN_TICK_SECONDS = 0.5  # in a town, one step of its time (townlife.STEP_SECONDS) every half second you watch


def key_direction(ev: KeyEvent) -> tuple[int, int] | None:
    if ev.ctrl or ev.alt:
        return None
    return KEY_DIRECTIONS.get(ev.key)


def _rituals(game, c) -> bool:
    """They know rituals of their own without being casters (Ritual Caster)."""
    from realmwalker.rules import feats

    return bool(feats.ritual_spells(c, game.tables))


class GameScreen(Screen):
    title = "Realmwalker"
    key_sounds = False  # the keys walk; what happens has its own sounds (game.cue)

    def __init__(self, app, game: GameState) -> None:
        super().__init__(app)
        self.game = game
        self.look: tuple[int, int] | None = None  # cursor in map cells while in look mode
        self.hover: tuple[int, int] | None = None
        self._last_travel_step = 0.0
        self._last_town_tick = 0.0
        self._in_local_before = game.in_local
        from realmwalker.ui.gfx.localview import LocalView

        from realmwalker.ui.gfx.worldview import WorldView

        self.local_view = LocalView()
        self.world_view = WorldView()
        self.tiles_drawn = False  # the map has been drawn (so its squares can be found under the mouse)
        self.bar_actions: dict = {}
        self._hp_seen: dict[int, tuple[float, float, float]] = {}  # member -> (shown ratio, lag ratio, time)

    @property
    def animating(self) -> bool:  # type: ignore[override]
        return self.game.travel is not None or self.game.walk_to is not None

    @property
    def moving(self) -> bool:
        """Something glides on the map right now (the window keeps drawing smoothly)."""
        if not self.tiles_drawn:
            return False
        now = self.app.clock()
        return self.local_view.moving(now) if self.game.in_local else self.world_view.moving(now)

    def on_exit(self) -> None:
        self.world_view.close()

    def music(self) -> str | None:
        """Where you are decides the music (data/music.json): the land on the road, the size of a town, an inn,
        the kind of place underground."""
        game = self.game
        p = game.player
        lm = game.local
        if lm is not None and lm.kind == "dungeon":
            style = lm.meta.get("style")
            return f"dungeon/{style}" if style else "dungeon"
        if lm is not None and lm.kind == "settlement":
            b = lm.building_at(p.lx, p.ly)
            if b is not None and b.kind == "inn":
                return "tavern"
            s = game.world.settlement_at(p.x, p.y)
            return f"town/{s.kind}" if s is not None else "town"
        return f"travel/{game.world.biome_id(p.x, p.y)}"

    @property
    def ambient(self) -> bool:
        return self.tiles_drawn

    # ------------------------------------------------------------------ helpers
    def _map_rect(self, canvas: Canvas) -> tuple[int, int, int, int]:
        """The map: left of the side panel, above the message log and the action bar."""
        return 0, 0, max(20, canvas.width - PANEL_W), max(8, canvas.height - LOG_H - BAR_H)

    def screen_to_map(self, sx: int, sy: int, px: float = -1.0, py: float = -1.0) -> tuple[int, int] | None:
        if not self.tiles_drawn:
            return None
        if px < 0:
            px, py = (sx + 0.5) * self.app.gfx.cell_w, (sy + 0.5) * self.app.gfx.cell_h
        if self.game.in_local:
            cell = self.local_view.to_cell(px, py)
            lm = self.game.local
            return cell if cell is not None and lm is not None and lm.in_bounds(*cell) else None
        cell = self.world_view.to_cell(px, py)
        return cell if cell is not None and self.game.world.in_bounds(*cell) else None

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
            self.game.say("You are already on foot among the details. Walk off the edge, or press x to leave.", "system")
            return
        if self.game.gate_shut():
            from realmwalker.game import events

            self.game.event = events.make_event(self.game, "shut_gate")  # the event screen opens by itself
            return
        self.game.enter_local()
        self.app.save_game()

    def leave(self) -> None:
        game = self.game
        if game.local is not None and game.local.kind == "dungeon":
            from realmwalker.game import dungeon

            p = game.player
            if dungeon.terrain_id(game, game.local, p.lx, p.ly) == "stairs_up":
                dungeon.ascend(game)
            else:
                game.say("You are underground: find the stairs up and walk onto them.", "system")
            return
        if game.in_local:
            game.leave_local()
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
            game.say("Leave this place first (x, or the Leave button) to travel across country.", "system")
            return
        if game.lost:
            game.say("You have lost your bearings: you can't plan a journey until you find a road or the weather "
                     "clears. Walk (arrow keys) and hope.", "warn")
            return
        if game.pace() is None:
            from realmwalker.game.journey import why_cannot_walk

            game.say(why_cannot_walk(game), "warn")
            return
        plan = game.plan_travel(dest)
        if plan is None:
            game.say("You can see no way to get there on foot.", "warn")
            return
        from realmwalker.game.journey import outlook

        target = markup.plain(describe_overworld(game, *dest).split("\n")[0])
        notes = "".join(f"{line}\n" for line in outlook(game, plan))
        text = (f"Travel to: {markup.escape(target)}\n\n{game.describe_plan(plan)}.\n\n"
                + (f"{notes}\n" if notes else "")
                + "<dim>Any key stops the journey. You stop by yourself for the night, and when something is "
                  "wrong; t and Enter go on.</>")

        def go() -> None:
            game.set_out(plan)
            game.say(f"You set out: {game.describe_plan(plan)}.", "info")

        self.app.push(ConfirmBox(self.app, text, go, title="Set out?"))

    def open_world_map(self, travel: bool = False) -> None:
        from realmwalker.ui.screens.world_map import WorldMapScreen

        self.app.push(WorldMapScreen(self.app, self, travel_mode=travel))

    # ------------------------------------------------------------------ for the action bar and the mouse
    def press(self, key: str) -> None:
        """Do what a key does (the action bar's buttons press keys)."""
        self.handle_key(KeyEvent(key))

    def npc_beside(self):
        """A townsperson standing next to you, if there is one (the one you know best, if several)."""
        folk = self.npcs_beside()
        return folk[0] if folk else None

    def npcs_beside(self) -> list:
        """Everyone standing next to you in a town: those you know first, then people of note, then the rest."""
        game = self.game
        if not game.in_local or game.local is None or game.local.kind != "settlement":
            return []
        from realmwalker.game.people import npc_at

        px, py = game.player.lx, game.player.ly
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    npc = npc_at(game, px + dx, py + dy)
                    if npc is not None:
                        out.append(npc)
        out.sort(key=lambda n: (not n.known, not n.notable, n.id))
        return out

    def choose_talk(self, folk: list) -> None:
        if len(folk) == 1:
            self.talk(folk[0])
            return
        from realmwalker.ui.screens.base import ChoiceBox

        def label(n) -> str:
            name = n.name if n.known else (n.title or "someone")
            return f"{name[:1].upper() + name[1:]}" + (f", the {n.title}" if n.known and n.title else "")

        self.app.push(ChoiceBox(self.app, "Talk to whom?", [(label(n), lambda n=n: self.talk(n)) for n in folk]))

    def talk(self, npc) -> None:
        from realmwalker.game import townlife

        from realmwalker.game.story import favours

        if townlife.asleep(self.game, npc) and favours.opens_at_night(self.game, npc):
            self.game.say(favours.knock_line(self.game, npc), "info")  # (a contact deals at night: C.7)
        elif townlife.asleep(self.game, npc):
            who = npc.label()
            self.game.say(f"{who[:1].upper() + who[1:]} is asleep.", "system")
            return
        self.game.talk_to = npc.id  # the conversation opens by itself

    def walk_to_talk(self, cell) -> None:
        from realmwalker.game import wayfinding

        px, py = self.player_pos()
        if max(abs(cell[0] - px), abs(cell[1] - py)) <= 1:
            from realmwalker.game.people import npc_at

            npc = npc_at(self.game, *cell)
            if npc is not None:
                self.talk(npc)
                return
        wayfinding.begin(self.game, cell)

    def set_look(self, cell) -> None:
        self.look = cell

    def open_sheet(self, key: str, index: int = 0) -> None:
        from realmwalker.ui.screens.health import HealthScreen
        from realmwalker.ui.screens.sheets import CharacterScreen, EquipmentScreen, InventoryScreen

        screen = {"c": CharacterScreen, "i": InventoryScreen, "e": EquipmentScreen, "h": HealthScreen}[key]
        self.app.push(screen(self.app, self.game, index))

    def member_menu(self, index: int) -> None:
        from realmwalker.ui.screens.popup import ContextMenu

        c = self.game.party[index]
        self.app.push(ContextMenu(self.app, self.app.mouse, [
            ("Character sheet", lambda: self.open_sheet("c", index), "character"),
            ("Pack and gear", lambda: self.open_sheet("i", index), "inventory"),
            ("Health", lambda: self.open_sheet("h", index), "health"),
        ] + ([("Spells", lambda: self._spells(index), "spells")] if c.spells or _rituals(self.game, c) else []),
            markup.escape(c.name)))

    def _spells(self, index: int) -> None:
        from realmwalker.ui.screens.spells import SpellsScreen

        self.app.push(SpellsScreen(self.app, self.game, index))

    def hp_lag(self, index: int, ratio: float) -> float | None:
        """When hit points are lost the bar drains at once, and a pale stretch shows what was lost, fading after."""
        now = self.app.clock()
        shown, lag, t = self._hp_seen.get(index, (ratio, ratio, now))
        if ratio < shown:
            lag, t = max(lag, shown), now
        shown = ratio
        if now - t > 0.6:
            lag = max(ratio, lag - (now - t - 0.6) * 0.8)
        self._hp_seen[index] = (shown, lag, t if lag > ratio else now)
        return lag if lag > ratio + 0.001 else None

    def open_log(self) -> None:
        from realmwalker.ui.screens.log_screen import LogScreen

        self.app.push(LogScreen(self.app, self.game))

    def context(self) -> None:
        """Enter: the obvious thing here. Go into the land; pick up what lies here; talk to who is beside you."""
        game = self.game
        if not game.in_local:
            self.enter()
            return
        lm = game.local
        if lm is not None and lm.items.get((game.player.lx, game.player.ly)):
            game.pick_up()
            return
        npc = self.npc_beside()
        if npc is not None:
            self.talk(npc)
            return
        game.say("Nothing here to do with Enter. Walk into people to talk, onto stairs to take them; x leaves.",
                 "system")

    # ------------------------------------------------------------------ input
    def handle_key(self, ev: KeyEvent) -> bool:
        game = self.game
        if game.travel is not None:
            game.travel = None
            game.say("You stop.", "system")
            return True
        if game.walk_to is not None:
            game.walk_to = None  # any key stops a walk across a close-up map
            return True
        if self.look is not None:
            return self._look_key(ev)
        if game.held:  # a scene is playing: only Space or Escape (straight to its end)
            if ev.key in ("space", " ", "escape"):
                from realmwalker.game.story import stage

                stage.skip(game)
            return True
        d = key_direction(ev)
        if d is not None:
            self.move(*d)
        elif ev.key in (".", "5", "wait"):
            self.wait()
        elif ev.key == ">":
            self.enter()
        elif ev.key == "enter":
            self.context()
        elif ev.key in ("<", "x"):
            self.leave()
        elif ev.key in ("+", "="):
            self.zoom(1)
        elif ev.key == "-":
            self.zoom(-1)
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
        elif ev.key in ("b", "W"):
            self.wash()
        elif ev.key in ("c", "i", "e"):
            from realmwalker.ui.screens.sheets import CharacterScreen, EquipmentScreen, InventoryScreen

            screen = {"c": CharacterScreen, "i": InventoryScreen, "e": EquipmentScreen}[ev.key]
            self.app.push(screen(self.app, game))
        elif ev.key == "f":
            from realmwalker.ui.screens.factions import FactionsScreen

            self.app.push(FactionsScreen(self.app, game))
        elif ev.key in ("a", "S"):
            from realmwalker.ui.screens.spells import SpellsScreen

            caster = next((i for i, c in enumerate(game.party) if c.spells or _rituals(game, c)), 0)
            self.app.push(SpellsScreen(self.app, game, caster))
        elif ev.key == "j":
            from realmwalker.ui.screens.journal import JournalScreen

            self.app.push(JournalScreen(self.app, game))
        elif ev.key == "n":
            from realmwalker.ui.screens.chronicle import ChronicleScreen

            self.app.push(ChronicleScreen(self.app, game))
        elif ev.key == "p":
            from realmwalker.ui.screens.party import PartyScreen

            self.app.push(PartyScreen(self.app, game))
        elif ev.key == "z":
            game.say(game.toggle_sneak(), "info")
        elif ev.key == "v" and not game.in_local:
            game.say(game.cycle_pace(), "info")
        elif ev.key == "s" and game.in_local:
            from realmwalker.game import dungeon

            for text in dungeon.search(game):
                game.say(text, "info")
        elif ev.key == "m":
            self.open_world_map()
        elif ev.key == "t":
            folk = self.npcs_beside()
            if folk:  # in a town, t talks to whoever is beside you (a short list if there are several)
                self.choose_talk(folk)
            else:
                self.open_world_map(travel=True)
        elif ev.key in ("o", "L"):
            self.open_log()
        elif ev.key in ("/", "k"):
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
        elif ev.key == "enter":
            from realmwalker.game import wayfinding

            dest = self.look
            self.look = None
            wayfinding.begin(self.game, dest)
        elif ev.key == "tab" and self.game.in_local:
            # Jump between the places you have seen here: the inn, the shop, the stairs...
            from realmwalker.game import wayfinding

            spots = [(x, y) for x, y, _ in wayfinding.places(self.game)]
            if spots:
                i = spots.index(self.look) if self.look in spots else -1
                self.look = spots[(i + (-1 if ev.shift else 1)) % len(spots)]
        elif ev.key in ("escape", "l"):
            self.look = None
        return True

    def zoom(self, step: int) -> None:
        """Closer or further: the map's squares, in pixels (the close-up map and the overworld keep their own)."""
        from realmwalker.config import MAP_ZOOMS, WORLD_ZOOMS

        s = self.app.settings
        if self.game.in_local:
            i = MAP_ZOOMS.index(s.map_zoom) if s.map_zoom in MAP_ZOOMS else 2
            s.map_zoom = MAP_ZOOMS[max(0, min(len(MAP_ZOOMS) - 1, i + step))]
        else:
            i = WORLD_ZOOMS.index(s.world_zoom) if s.world_zoom in WORLD_ZOOMS else 3
            s.world_zoom = WORLD_ZOOMS[max(0, min(len(WORLD_ZOOMS) - 1, i + step))]
        self.app.save_settings()

    def handle_mouse(self, ev: MouseEvent) -> bool:
        if ev.kind == "move":
            self.hover = self.screen_to_map(ev.x, ev.y, ev.px, ev.py)
            return False
        if ev.kind == "wheel" and self.tiles_drawn and self.screen_to_map(ev.x, ev.y, ev.px, ev.py) is not None:
            self.zoom(1 if ev.dy > 0 else -1)
            return True
        if ev.kind != "click":
            return False
        target = self.screen_to_map(ev.x, ev.y, ev.px, ev.py)
        if target is None:
            return False
        if ev.button == "right":
            from realmwalker.ui.hud import map_menu
            from realmwalker.ui.screens.popup import ContextMenu

            self.app.push(ContextMenu(self.app, (ev.x + 1, ev.y), map_menu(self, target)))
            return True
        px, py = self.player_pos()
        dx, dy = target[0] - px, target[1] - py
        if max(abs(dx), abs(dy)) == 1:
            self.move(dx, dy)
        elif (dx, dy) != (0, 0) and not self.game.in_local:
            self.plan_travel_to(target)
        elif (dx, dy) != (0, 0):
            from realmwalker.game import wayfinding

            wayfinding.begin(self.game, target)  # walk there, or up to whoever is standing there
        return True

    def _open_event_screen(self) -> bool:
        """Death, the aftermath of a fight, a fight, or trouble on the road take over the screen."""
        game = self.game
        if game.over is not None:
            from realmwalker.game import greatmagic
            from realmwalker.ui.screens.aftermath import DeathScreen

            back = greatmagic.cheat_death(game)  # (Clone: the soul wakes in a grown clone)
            if back:
                for text in back:
                    game.say(text, "good")
                self.app.save_game()
                return True
            self.app.push(DeathScreen(self.app, game))
        elif game.aftermath is not None:
            from realmwalker.ui.screens.aftermath import AftermathScreen

            self.app.push(AftermathScreen(self.app, game, game.aftermath))
        elif game.battle is not None:
            from realmwalker.ui.screens.battle import BattleScreen

            self.app.push(BattleScreen(self.app, game))
        elif game.sentence is not None:
            from realmwalker.ui.screens.law import SentenceScreen

            self.app.push(SentenceScreen(self.app, game))
        elif game.arrest is not None:
            from realmwalker.ui.screens.law import ArrestScreen

            self.app.push(ArrestScreen(self.app, game))
        elif any(progression.has_new_choices(c) for c in game.party):
            from realmwalker.ui.screens.levelup import LevelUpScreen

            index = next(i for i, c in enumerate(game.party) if progression.has_new_choices(c))
            self.app.push(LevelUpScreen(self.app, game, index))
        elif game.epilogue is not None:  # (the story's screens: Expansion 6)
            from realmwalker.ui.screens.epilogue import EpilogueScreen

            self.app.push(EpilogueScreen(self.app, game))
        elif game.finale is not None:
            from realmwalker.ui.screens.finale import FinaleScreen

            self.app.push(FinaleScreen(self.app, game))
        elif getattr(game, "letter", None) is not None:  # (a letter put in your hand: its page)
            from realmwalker.ui.screens.letter import LetterScreen

            lid, game.letter = game.letter, None
            self.app.push(LetterScreen(self.app, game, lid))
        elif (game.world.politics.get("director") or {}).get("card"):
            from realmwalker.ui.screens.titlecard import TitleCardScreen

            self.app.push(TitleCardScreen(self.app, game))
        elif (game.world.politics.get("director") or {}).get("pending"):
            from realmwalker.ui.screens.beat import BeatScreen

            self.app.push(BeatScreen(self.app, game))
        elif game.read_board:
            from realmwalker.ui.screens.notices import NoticeBoardScreen

            game.read_board = False
            here = game.world.settlement_at(game.player.x, game.player.y)
            if here is None:
                return False
            self.app.push(NoticeBoardScreen(self.app, game, here))
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
        """Write up a finished day on the road from the built-in words."""
        from realmwalker.game.events import travel_day_facts, travel_day_passage

        game = self.game
        day = game.narration.pop(0)
        rng = game.world.rng.child(f"narrate/{game.world.time}")
        game.say(markup.escape(travel_day_passage(rng, self.app.data, travel_day_facts(game, day))), "flavor")

    def _work_line(self, canvas: Canvas, x: int, y: int, w: int) -> int:
        """One line about the work in hand: how much, and how soon it is due."""
        game = self.game
        if not game.quests:
            return 0
        from realmwalker.game import quests

        live = quests.active(game)
        if not live:
            return 0
        ready = sum(1 for q in live if q["done"])
        days = [d for d in (quests.days_left(game, q) for q in live) if d is not None]
        soon = min(days) if days else None
        text = f"<info>Work:</> {len(live)} in hand"
        if ready:
            text += f", <good>{ready} to report</>"
        walking = [q for q in live if q["template"] == "escort" and not q["done"]]
        if walking:
            who = walking[0]["words"].get("traveller", "someone")
            text += f" <dim>· {markup.escape(who)} walks with you</>"
        if soon is not None:
            color = "danger" if soon <= 2 else "warn" if soon <= 5 else "dim"
            days = max(0, soon)
            due = f"<{color}>(next due in {days} day{'s' if days != 1 else ''})</>"
            # On a line of its own when it will not fit whole, rather than leaving "days)" dangling on the next.
            text += ("\n" if markup.length(text) + 1 + markup.length(due) > w else " ") + due
        used = canvas.wrapped(x, y + 1, text, w, max_lines=2)
        canvas.hit(x, y + 1, w, used, action=lambda: self.handle_key(KeyEvent("j")),
                   tooltip="Click (or press j) for the journal.")
        return used + 1

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
        game.verbosity = self.app.settings.verbosity
        game.animations = self.app.settings.animations
        game.auto_supplies = self.app.settings.auto_supplies
        from realmwalker.game.story import stage

        stage.check_here(game)  # (a scene left behind on another map is simply over)
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
        elif game.walk_to is not None:
            now = self.app.clock()
            if now - self._last_travel_step >= WALK_STEP_SECONDS or self.app.headless:
                from realmwalker.game import wayfinding

                self._last_travel_step = now
                was = game.player.local_key
                if not wayfinding.step(game) and game.player.local_key != was:
                    self.app.save_game()
        elif self.time_flows():
            now = self.app.clock()
            if now - self._last_town_tick >= TOWN_TICK_SECONDS:
                self._last_town_tick = now
                game.town_tick()
        self.app.maybe_autosave()

    def time_flows(self) -> bool:
        """In a town, with Time in towns set to flow, and nothing going on: its clock runs by itself (this screen is
        only updated while it is on top, so the clock stops under any other screen). While a scene holds your keys
        it runs whatever the setting (game/story/stage.py)."""
        game = self.game
        return ((self.app.settings.time_in_towns == "flows" or game.held) and game.in_local and game.local is not None
                and game.local.kind == "settlement" and not game.busy and game.over is None)

    def _weather(self, canvas: Canvas, rect) -> None:
        """Rain, snow and fog over the map, when animations are on."""
        gfx = canvas.gfx
        if gfx.animate and self.game.local is not None:  # (embers, ash, haze: still when calm; B.7)
            from realmwalker.ui.gfx import atmosfx

            atmosfx.draw(canvas, rect, self.game, gfx.now, float(self.game.light), moving=gfx.ambient)
        if not gfx.ambient:
            return
        from realmwalker.ui.gfx import weatherfx

        weatherfx.draw(canvas, rect, self.game.weather, gfx.now, float(self.game.light))

    def render(self, canvas: Canvas) -> None:
        game = self.game
        mx, my, mw, mh = self._map_rect(canvas)
        cursor = self.look
        self.tiles_drawn = False
        if game.in_local and game.local is not None:
            from realmwalker.game.vision import player_fov
            from realmwalker.ui.gfx.localview import cursor_cmd

            fov = player_fov(game, game.local, remember=True)
            canvas.clear_cells(mx, my, mw, mh)
            rect = tuple(int(v) for v in canvas.cell_rect(mx, my, mw, mh))
            from realmwalker.ui.gfx.scene import Clip

            canvas.under(Clip(rect))
            self.local_view.draw(canvas, game, rect, self.app.settings.map_zoom, fov)
            lm = game.local
            p = game.player
            if not lm.under_rock(p.lx, p.ly) and lm.building_at(p.lx, p.ly) is None and fov.any():
                # Only over what you can see: rain over darkness looks like stars.
                xs, ys = np.nonzero(fov)
                ax, ay = self.local_view.cell_px(int(xs.min()), int(ys.min()))
                bx, by = self.local_view.cell_px(int(xs.max()) + 1, int(ys.max()) + 1)
                x0, y0 = max(rect[0], int(ax)), max(rect[1], int(ay))
                x1, y1 = min(rect[0] + rect[2], int(bx)), min(rect[1] + rect[3], int(by))
                if (lm.meta or {}).get("open_below") is not None:  # before a hold: none falls past its gate
                    y0 = max(y0, int(self.local_view.cell_px(0, int(lm.meta["open_below"]))[1]))
                if x1 > x0 and y1 > y0:
                    canvas.under(Clip((x0, y0, x1 - x0, y1 - y0)))
                    self._weather(canvas, (x0, y0, x1 - x0, y1 - y0))
                    canvas.under(Clip(rect))
                    if canvas.gfx.ambient and not lm.seen.all():  # and none over ground never seen
                        from realmwalker.ui.gfx.scene import Image as Pic

                        seen = lm.seen.copy()
                        for b in lm.buildings:  # a building is drawn whole once any of it is seen
                            if seen[b.x:b.x + b.w, b.y:b.y + b.h].any():
                                seen[b.x:b.x + b.w, max(0, b.y - 3):b.y + b.h] = True
                        T = self.local_view.tile
                        ox, oy = self.local_view.cell_px(0, 0)

                        def unseen(seen=seen):
                            a = np.zeros((seen.shape[1], seen.shape[0], 4), np.uint8)
                            a[~seen.T] = (*colors.BG, 255)
                            return a

                        canvas.under(Pic(("unseen", lm.key, int(lm.seen.sum())), unseen,
                                         (ox, oy, lm.width * T, lm.height * T), smooth=False))
            canvas.under(Clip(None))
            self.tiles_drawn = True
            if self.hover is not None and cursor is None:
                canvas.over(Clip(rect), cursor_cmd(self.local_view, *self.hover, (255, 255, 255, 90)), Clip(None))
            if cursor is not None:
                canvas.over(Clip(rect), cursor_cmd(self.local_view, *cursor, (255, 214, 110, 230)), Clip(None))
        else:
            from realmwalker.game.quests import map_marks

            if game.in_local:  # a close-up map that is gone (it should not happen): back on the overworld
                game.player.local_key = None
                game.sneaking = False
            canvas.clear_cells(mx, my, mw, mh)
            rect = tuple(int(v) for v in canvas.cell_rect(mx, my, mw, mh))
            self.world_view.draw(canvas, game, rect, self.app.settings.world_zoom, quests=map_marks(game),
                                 look=cursor, hover=self.hover if cursor is None else None)
            from realmwalker.ui.gfx.scene import Clip

            canvas.under(Clip(rect))
            self._weather(canvas, rect)
            canvas.under(Clip(None))
            self.tiles_drawn = True
        canvas.hit(mx, my, mw, mh, tooltip=None)
        from realmwalker.ui import hud

        hud.render_panel(self, canvas, mw, 0, canvas.width - mw, canvas.height)
        hud.render_log(self, canvas, 0, mh, mw, LOG_H)
        hud.render_actionbar(self, canvas, 0, mh + LOG_H, mw, canvas.height - mh - LOG_H)

    def autoplay_keys(self) -> list[KeyEvent]:
        moves = [KeyEvent(k) for k in ("up", "down", "left", "right", "upleft", "upright", "downleft", "downright")]
        return moves * 4 + [KeyEvent(k) for k in (">", "<", "x", "l", "enter", "escape", ".", "m", "t", "o", "k",
                                                   "c", "i", "e", "g", "r", "h", "w", "b", "f", "n", "p", "s", "j", "a",
                                                   "z", "v", "+", "-", "space")]
