"""Logging setup. Everything goes to logs/game.log; problems also go to logs/errors.log."""

from __future__ import annotations

import logging
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

_handlers: list[logging.Handler] = []


def setup_logging(logs_dir: Path) -> None:
    """Point all game logging at files in `logs_dir`. Safe to call more than once."""
    root = logging.getLogger("realmwalker")
    for handler in _handlers:
        root.removeHandler(handler)
        handler.close()
    _handlers.clear()

    root.setLevel(logging.INFO)
    root.propagate = False
    fmt = logging.Formatter(LOG_FORMAT)

    game = RotatingFileHandler(logs_dir / "game.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    game.setFormatter(fmt)
    game.setLevel(logging.INFO)

    errors = RotatingFileHandler(logs_dir / "errors.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    errors.setFormatter(fmt)
    errors.setLevel(logging.WARNING)

    root.addHandler(game)
    root.addHandler(errors)
    _handlers.extend([game, errors])

    install_crash_hooks()


def install_crash_hooks() -> None:
    """Make sure uncaught exceptions anywhere end up in errors.log."""
    log = logging.getLogger("realmwalker.crash")

    def excepthook(exc_type, exc, tb):
        log.critical("Uncaught exception:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_type is SystemExit:
            return
        log.error(
            "Uncaught exception in thread %s:\n%s",
            args.thread.name if args.thread else "?",
            "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
        )

    sys.excepthook = excepthook
    threading.excepthook = thread_hook


def count_error_lines(logs_dir: Path) -> int:
    """Number of ERROR/CRITICAL entries in errors.log (used by the autoplay bot)."""
    path = logs_dir / "errors.log"
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8", errors="replace")
    return sum(1 for line in text.splitlines() if " ERROR " in line or " CRITICAL " in line)
