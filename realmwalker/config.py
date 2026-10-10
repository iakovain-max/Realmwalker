"""Two kinds of configuration:

* GameConfig - config.json next to the game. Game-level switches: the optional Player2 client id,
  an optional Player2 address override, and whether the debug console exists (off in friend builds).
* Settings   - the player's preferences in %APPDATA%\\Realmwalker\\settings.json, changed from the
  in-game Settings screen.

Both load forgivingly: a missing or broken file never stops the game, it just falls back to defaults.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path

log = logging.getLogger("realmwalker.config")

FONT_SIZES = tuple(range(12, 42, 2))
DEFAULT_FONT_SIZE = 20
VERBOSITY_LEVELS = ("brief", "normal", "rich")
AUTOSAVE_CHOICES = (2, 5, 10, 15, 30)
GRAPHICS_CHOICES = ("tiles", "letters")
COMPANION_CHOICES = ("command", "auto")  # in a fight: you play the companions' turns, or they fight by themselves
ANIMATION_CHOICES = ("full", "calm", "off")
VOLUME_STEPS = 10  # volumes are 0 (silent) to 10 (full)
MAP_ZOOMS = (16, 24, 32, 48, 64)  # pixels per square on a close-up map
WORLD_ZOOMS = (8, 12, 16, 24, 32, 48)  # pixels per square of country on the overworld


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("Could not read %s (%s); using defaults.", path, exc)
        return {}
    if not isinstance(data, dict):
        log.warning("%s does not contain a JSON object; using defaults.", path)
        return {}
    return data


@dataclass
class GameConfig:
    player2_game_client_id: str = ""
    player2_base_url: str = ""  # blank = find the local Player2 app automatically
    debug_console: bool = True
    ai_workers: int = 2

    @classmethod
    def load(cls, path: Path) -> GameConfig:
        raw = _read_json(path)
        cfg = cls()
        for f in fields(cls):
            if f.name in raw and isinstance(raw[f.name], type(getattr(cfg, f.name))):
                setattr(cfg, f.name, raw[f.name])
        cfg.ai_workers = max(1, min(4, cfg.ai_workers))
        return cfg


@dataclass
class Settings:
    font_size: int = DEFAULT_FONT_SIZE
    fullscreen: bool = False
    show_dice: bool = True
    ai_enabled: bool = True
    verbosity: str = "normal"
    autosave_minutes: int = 5
    ai_debug_log: bool = False
    auto_supplies: bool = True  # eat and drink from the pack when needed
    ai_extras: bool = True  # AI words for scenery and things (off: keep the energy for people and places)
    graphics: str = "tiles"  # maps and people as pictures, or as letters (the old look)
    animations: str = "full"  # full, calm (no idle movement: water, fire, weather), off
    map_zoom: int = 32
    world_zoom: int = 24
    battle_companions: str = "command"  # COMPANION_CHOICES
    volume: int = 10  # everything (0-10)
    music_volume: int = 6
    effects_volume: int = 9
    interface_volume: int = 7  # clicks, pages, menus
    sound_in_background: bool = True  # keep playing while another window is in front
    muted: bool = False  # Ctrl M

    def normalise(self) -> None:
        if self.font_size not in FONT_SIZES:
            self.font_size = min(FONT_SIZES, key=lambda s: abs(s - int(self.font_size)))
        if self.verbosity not in VERBOSITY_LEVELS:
            self.verbosity = "normal"
        if self.autosave_minutes not in AUTOSAVE_CHOICES:
            self.autosave_minutes = 5
        if self.graphics not in GRAPHICS_CHOICES:
            self.graphics = "tiles"
        if self.animations not in ANIMATION_CHOICES:
            self.animations = "full"
        if self.map_zoom not in MAP_ZOOMS:
            self.map_zoom = 32
        if self.world_zoom not in WORLD_ZOOMS:
            self.world_zoom = 24
        if self.battle_companions not in COMPANION_CHOICES:
            self.battle_companions = "command"
        for name in ("volume", "music_volume", "effects_volume", "interface_volume"):
            setattr(self, name, max(0, min(VOLUME_STEPS, int(getattr(self, name)))))

    @classmethod
    def load(cls, path: Path) -> Settings:
        raw = _read_json(path)
        s = cls()
        for f in fields(cls):
            if f.name not in raw:
                continue
            value, default = raw[f.name], getattr(s, f.name)
            if isinstance(default, bool):
                if isinstance(value, bool):
                    setattr(s, f.name, value)
            elif isinstance(default, int):
                if isinstance(value, int) and not isinstance(value, bool):
                    setattr(s, f.name, value)
            elif isinstance(value, type(default)):
                setattr(s, f.name, value)
        s.normalise()
        return s

    def save(self, path: Path) -> None:
        self.normalise()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        tmp.replace(path)

    def to_dict(self) -> dict:
        return asdict(self)
