"""Where things live on disk, both when running from source and in the packaged build.

Read-only game content (data/, ai/prompts/, assets/) sits in the resource root.
Player files (settings, saves, logs, screenshots) live in %APPDATA%\\Realmwalker,
unless a different "home" folder is given (tests and the autoplay bot do this).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "Realmwalker"


def is_frozen() -> bool:
    """True when running as the packaged Realmwalker.exe."""
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Folder holding data/, ai/prompts/ and assets/."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def install_dir() -> Path:
    """Folder the game was launched from (next to Realmwalker.exe, or the project root)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return resource_root()


def default_user_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_DIR_NAME
    return Path.home() / f".{APP_DIR_NAME.lower()}"


class Paths:
    """All file locations used by one running game."""

    def __init__(self, home: Path | str | None = None) -> None:
        self.custom_home = home is not None
        self.home = Path(home) if home is not None else default_user_dir()
        self.resources = resource_root()

    # --- read-only content -------------------------------------------------
    @property
    def data(self) -> Path:
        return self.resources / "data"

    @property
    def prompts(self) -> Path:
        return self.resources / "ai" / "prompts"

    @property
    def fonts(self) -> Path:
        return self.resources / "assets" / "fonts"

    @property
    def tiles(self) -> Path:
        return self.resources / "assets" / "tiles"

    @property
    def sounds(self) -> Path:
        return self.resources / "assets" / "sounds"

    @property
    def music_builtin(self) -> Path:
        """The tunes that come with the game (read-only)."""
        return self.resources / "assets" / "music"

    @property
    def music(self) -> Path:
        """The player's own music: a 'music' folder next to the game (the project folder, or beside Realmwalker.exe),
        where it is easy to find; in %APPDATA%\\Realmwalker\\music when the game's folder cannot be written to, and in
        the home folder when one is given (tests, the autoplay bot)."""
        if self.custom_home:
            return self.home / "music"
        near = install_dir() / "music"
        if near.is_dir() or os.access(install_dir(), os.W_OK):
            return near
        return self.home / "music"

    @property
    def config_file(self) -> Path:
        """Game-level configuration (Player2 client id, debug switches)."""
        near_exe = install_dir() / "config.json"
        if near_exe.exists() or not is_frozen():
            return near_exe
        return self.resources / "config.json"

    # --- player files --------------------------------------------------------
    def _ensure(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def user(self) -> Path:
        return self._ensure(self.home)

    @property
    def settings_file(self) -> Path:
        return self.user / "settings.json"

    @property
    def music_levels(self) -> Path:
        """How loud each of the player's tunes measured (so it is measured once)."""
        return self.user / "music_levels.json"

    @property
    def saves(self) -> Path:
        return self._ensure(self.home / "saves")

    @property
    def screenshots(self) -> Path:
        return self._ensure(self.home / "screenshots")

    @property
    def logs(self) -> Path:
        # Developers find logs in the project folder; players in %APPDATA%.
        if self.custom_home or is_frozen():
            return self._ensure(self.home / "logs")
        return self._ensure(self.resources / "logs")
