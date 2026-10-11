"""Realmwalker entry point. Double-click Play.bat, or run: python main.py

Options (for developers):
  --smoke-test [PATH]  open the window, visit a few screens, save a screenshot, exit (AI always off)
  --home DIR           use DIR instead of %APPDATA%\\Realmwalker for settings, saves and logs
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback
from pathlib import Path

from realmwalker import GAME_NAME


def show_fatal_error(message: str) -> None:
    """Last resort when the game cannot even open its window."""
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, f"{GAME_NAME} could not start", 0x10)
    except Exception:
        print(message, file=sys.stderr)


def write_crash_file(text: str) -> Path | None:
    from realmwalker.paths import Paths

    try:
        path = Paths().logs / "crash.log"
        with path.open("a", encoding="utf-8") as f:
            f.write(text + "\n")
        return path
    except OSError:
        return None


def smoke_script():
    """A scripted tour used by --smoke-test: title screens, a new world, character creation, walking,
    the character sheet, the pack and a local map. Returns (steps, last frame, {frame: screenshot name})."""
    from realmwalker.ui.input import KeyEvent

    steps = []
    shots = {}
    frame = 10

    def press(*keys, gap=8):
        nonlocal frame
        for key in keys:
            steps.append((frame, KeyEvent(key)))
            frame += gap

    press("p", "escape", "s", "down", "escape", "f1", "pagedown", "escape", "n", "enter")
    shots[frame + 4] = "worldgen"  # the ages being lived
    frame += 170  # world generation (the land, then its history)
    press("enter", "enter", "enter")  # people, calling, background
    shots[frame + 4] = "creation"
    press("enter", "enter", "enter", "enter", "enter", "enter")  # abilities, skills, identity, looks, start, begin
    frame += 4

    def peaceful(app):
        """The tour must not be hijacked by a random bandit on the road (its own fight comes at the end)."""
        from realmwalker.game import encounters, events

        encounters.encounter_chance = lambda *args, **kwargs: 0.0
        events.event_chance = lambda *args, **kwargs: 0.0
        if app.game is not None:
            app.game.encounter = None
            app.game.event = None

    steps.append((frame, peaceful))
    frame += 6
    press("right", "right", "down", "down", gap=4)
    shots[frame - 1] = "overworld"
    press("c")
    shots[frame - 4] = "character"
    press("escape", "i")
    shots[frame - 4] = "inventory"
    press("escape", "e")
    shots[frame - 4] = "equipment"
    press("escape", "h")
    shots[frame - 4] = "health"
    press("escape", "m", "w")
    shots[frame - 4] = "weather"
    press("w", "p", "z")
    shots[frame - 4] = "realms"
    press("c")
    shots[frame - 4] = "peoples"
    press("escape", "f", "down", "down")
    shots[frame - 4] = "factions"
    press("escape", "n", "2")
    shots[frame - 4] = "chronicle"
    press("b", "down", "down")
    shots[frame - 4] = "legends"
    press("right", "right", "down")
    shots[frame - 4] = "legends_people"
    press("escape", "escape")

    def home(app):
        game = app.game
        if game is not None and not game.in_local:
            town = min(game.world.settlements, key=lambda s: abs(s.x - game.player.x) + abs(s.y - game.player.y))
            game.player.x, game.player.y = town.x, town.y

    steps.append((frame, home))
    frame += 4
    press(">")  # into the nearest town, on foot
    shots[frame - 2] = "local"
    press("left", "up", gap=3)

    def chat(app):
        from realmwalker.game.people import npcs_in

        game = app.game
        if game is None:
            return
        s = game.world.settlement_at(game.player.x, game.player.y)
        people = [n for n in npcs_in(game.world, s.id) if n.notable] if s is not None else []
        if people:
            game.talk_to = people[0].id

    steps.append((frame, chat))
    frame += 6
    press("1", "2", gap=10)
    shots[frame - 2] = "talk"
    press("escape", "escape", "<")

    def work(app):
        """Take on a job or two, so the journal has something in it."""
        from realmwalker.game import quests
        from realmwalker.game.people import npcs_in
        from realmwalker.ui.screens.game_screen import GameScreen

        game = app.game
        while app.screens and not isinstance(app.top, GameScreen):
            app.pop()
        if game is None:
            return
        here = game.world.settlement_at(game.player.x, game.player.y)
        if here is None:
            return
        taken = 0
        for npc in npcs_in(game.world, here.id):
            q = quests.offer_for(game, npc)
            if q is not None:
                quests.accept(game, q)
                taken += 1
                if taken >= 2:
                    break

    steps.append((frame, work))
    frame += 4
    press("j", "down")
    shots[frame - 4] = "journal"
    press("escape")

    def underground(app):
        from realmwalker.game import dungeon
        from realmwalker.ui.screens.game_screen import GameScreen

        game = app.game
        if game is None:
            return
        while app.screens and not isinstance(app.top, GameScreen):
            app.pop()
        game.player.local_key = None
        site = min(game.world.sites, key=lambda s: abs(s.x - game.player.x) + abs(s.y - game.player.y))
        game.player.x, game.player.y = site.x, site.y
        game.enter_local()
        dungeon.descend(game, 1)
        for a in game.local.actors:
            a.alert = False

    steps.append((frame, underground))
    frame += 8
    shots[frame] = "dungeon"
    frame += 4

    def visit(choose, deep: bool = False):
        """Into a settlement on foot (the biggest of its kind): a city of the desert if there is one, a dwarven hold
        (deep inside, past the gate), an elven hall."""
        def go(app):
            from realmwalker.ui.screens.game_screen import GameScreen

            game = app.game
            if game is None:
                return
            while app.screens and not isinstance(app.top, GameScreen):
                app.pop()
            places = [s for s in game.world.settlements if choose(s)]
            if not places:
                return
            s = max(places, key=lambda s: (s.culture == "qasari", getattr(s, "great", False), s.population))
            game.player.local_key = None
            game.player.x, game.player.y = s.x, s.y
            game.enter_local()
            lm = game.local
            if deep and lm is not None:
                walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
                cx, cy = lm.width // 2, lm.height // 2
                spots = [(x, y) for x in range(lm.width) for y in range(lm.height)
                         if walk[x, y] and lm.under_rock(x, y) and lm.building_at(x, y) is None]
                if spots:
                    game.player.lx, game.player.ly = min(spots, key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)
        return go

    for name, choose, deep in (("city", lambda s: s.kind == "city", False), ("hold", lambda s: s.kind == "hold", True),
                               ("grove", lambda s: s.kind == "elfhall", False)):
        steps.append((frame, visit(choose, deep)))
        frame += 10
        shots[frame] = name
        frame += 4

    def surface(app):
        if app.game is not None:
            app.game.player.local_key = None

    steps.append((frame, surface))
    frame += 4

    def trouble(app):
        from realmwalker.game.encounters import make_encounter

        game = app.game
        if game is not None and not game.busy:
            game.encounter = make_encounter(game, "bandits", game.world.rng.child("smoke-test"))

    steps.append((frame, trouble))
    frame += 12
    shots[frame] = "encounter"
    frame += 4
    press("f", gap=150)  # fight; give the enemy time to act if they are quicker
    shots[frame - 4] = "battle"

    def point_far(app):
        """Point at the furthest square the one whose turn it is can walk to: the path and its cost show."""
        screen = app.top
        f = screen.actor() if hasattr(screen, "actor") else None
        if f is not None:
            reach = screen.reach(f)
            if reach:
                screen.hover = max(reach, key=lambda s: reach[s].cost)

    steps.append((frame, point_far))
    frame += 4
    shots[frame] = "battle_move"
    frame += 2
    press("a")
    shots[frame - 3] = "battle_attack"
    press("enter")
    shots[frame - 3] = "battle_target"
    press("escape")
    press("escape")
    press("z", gap=40)  # let the game play the turn: walking, blows
    shots[frame - 30] = "battle_auto"
    press("z", gap=60)
    shots[frame - 30] = "battle_later"
    press("enter", gap=20)
    return steps, frame, shots


def sound_trouble(app) -> str:
    """After the smoke test: did the sound device open, every effect load, and the title music play?"""
    audio = app.audio
    if not audio.real:
        return "the sound device did not open"
    if audio.bank.problems:
        return "effects could not be read: " + "; ".join(audio.bank.problems[:3])
    if audio.problems:
        return "; ".join(audio.problems[:3])
    if audio.music.broken:
        return f"the music stopped: {audio.music.broken}"
    if not audio.music.started:
        return "no music was played"
    if not audio.history:
        return "no sound was played"
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=GAME_NAME)
    parser.add_argument("--smoke-test", nargs="?", const="smoke_test.png", default=None)
    parser.add_argument("--home", default=None)
    args = parser.parse_args(argv)

    if args.smoke_test:
        # The smoke test plays its sounds to SDL's silent "dummy" device: the whole path is used, nothing is heard.
        # (SDL_AUDIO_DRIVER=disk with SDL_DISKAUDIOFILE=<file> records what would have been heard, for checking.)
        os.environ.setdefault("SDL_AUDIO_DRIVER", "dummy")
    try:
        from realmwalker.app import App
        from realmwalker.ui import window

        # The smoke test never talks to the real Player2 app: it must not spend the player's AI energy.
        overrides = {"ai_enabled": False} if args.smoke_test else None
        app = App(home=args.home, settings_overrides=overrides)
    except Exception:
        text = traceback.format_exc()
        crash = write_crash_file(text)
        show_fatal_error(f"The game failed to start.\n\nDetails were saved to:\n{crash}\n\n{text[-600:]}")
        return 1

    try:
        if args.smoke_test:
            script, last, shots = smoke_script()
            shot = Path(args.smoke_test)
            named = {f: shot.with_name(f"{shot.stem}_{name}{shot.suffix}") for f, name in shots.items()}
            window.run(app, script=script, max_frames=last + 20, screenshot_to=shot, screenshots_at=named)
            trouble = sound_trouble(app)
            if trouble:
                logging.getLogger("realmwalker.smoke").error("Sound check failed: %s", trouble)
                print(f"Sound check failed: {trouble}", file=sys.stderr)
                return 2
        else:
            window.run(app)
    except Exception:
        text = traceback.format_exc()
        logging.getLogger("realmwalker.crash").critical("Fatal error in the window loop:\n%s", text)
        crash = write_crash_file(text)
        show_fatal_error(f"The game hit a fatal problem and had to close.\n\nDetails were saved to:\n{crash}")
        return 1
    finally:
        app.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
