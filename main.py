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
    """A short scripted tour of the screens, used by --smoke-test."""
    from realmwalker.ui.input import KeyEvent

    keys = ["p", None, "escape", "s", "down", "escape", "f1", "pagedown", "escape", "p"]
    return [(10 + i * 8, KeyEvent(k)) for i, k in enumerate(keys) if k]


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
            window.run(app, script=smoke_script(), max_frames=120, screenshot_to=Path(args.smoke_test))
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
