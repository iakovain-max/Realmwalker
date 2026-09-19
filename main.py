"""Realmwalker entry point. Double-click Play.bat, or run: python main.py

Options (for developers):
  --smoke-test [PATH]  open the window, visit a few screens, save a screenshot, exit
  --home DIR           use DIR instead of %APPDATA%\\Realmwalker for settings, saves and logs
"""

from __future__ import annotations

import argparse
import logging
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
    frame += 110  # world generation
    press("enter", "enter", "enter")  # people, calling, background
    shots[frame + 4] = "creation"
    press("enter", "enter", "enter", "enter", "enter")  # abilities, skills, identity, start, begin
    frame += 10
    press("right", "right", "down", "down", gap=4)
    shots[frame - 1] = "overworld"
    press("c")
    shots[frame - 4] = "character"
    press("escape", "i")
    shots[frame - 4] = "inventory"
    press("escape", "e")
    shots[frame - 4] = "equipment"
    press("escape", ">")
    press("left", "left", "left", "up", "up", gap=3)
    return steps, frame, shots


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=GAME_NAME)
    parser.add_argument("--smoke-test", nargs="?", const="smoke_test.png", default=None)
    parser.add_argument("--home", default=None)
    args = parser.parse_args(argv)

    try:
        from realmwalker.app import App
        from realmwalker.ui import window

        app = App(home=args.home)
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
