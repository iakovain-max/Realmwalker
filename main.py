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
    """A scripted tour used by --smoke-test: title screens, then a new world, walking and a local map."""
    from realmwalker.ui.input import KeyEvent

    steps = []
    frame = 10
    for key in ["p", "escape", "s", "down", "escape", "f1", "pagedown", "escape", "n", "enter"]:
        steps.append((frame, KeyEvent(key)))
        frame += 8
    frame += 120  # world generation
    for key in ["right", "right", "down", "down", "l", "up", "up", "right"]:
        steps.append((frame, KeyEvent(key)))
        frame += 4
    steps.append((frame, KeyEvent("escape")))
    frame += 6
    steps.append((frame, KeyEvent(">")))
    frame += 6
    for key in ["left", "left", "left", "up", "up"]:
        steps.append((frame, KeyEvent(key)))
        frame += 3
    return steps, frame


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
            script, last = smoke_script()
            shot = Path(args.smoke_test)
            overworld_shot = shot.with_name(shot.stem + "_overworld" + shot.suffix)
            window.run(app, script=script, max_frames=last + 20, screenshot_to=shot,
                       screenshots_at={last - 30: overworld_shot})
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
