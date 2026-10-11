"""Two kinds of configuration:

* GameConfig - config.json in the game's folder. Game-level switches: whether the debug console exists.
* Settings   - the player's preferences in %APPDATA%\\Realmwalker\\settings.json, changed from the
  in-game Settings screen.

Both load forgivingly: a missing or broken file never stops the game, it just falls back to defaults.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

log = logging.getLogger("realmwalker.config")

FONT_SIZES = tuple(range(12, 42, 2))
DEFAULT_FONT_SIZE = 20
VERBOSITY_LEVELS = ("brief", "normal", "rich")
AUTOSAVE_CHOICES = (2, 5, 10, 15, 30)
COMPANION_CHOICES = ("command", "auto")  # in a fight: you play the companions' turns, or they fight by themselves
ANIMATION_CHOICES = ("full", "calm", "off")
TOWN_TIME_CHOICES = ("flows", "waits")  # in towns the clock runs by itself, or (the old way) only when you act
VOLUME_STEPS = 10  # volumes are 0 (silent) to 10 (full)
MAP_ZOOMS = (16, 24, 32, 48, 64)  # pixels per square on a close-up map
WORLD_ZOOMS = (6, 12, 24, 36, 48)  # pixels per square of country (the map is painted at 12: these stay sharp)


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
    debug_console: bool = True

    @classmethod
    def load(cls, path: Path) -> GameConfig:
        raw = _read_json(path)
        cfg = cls()
        for f in fields(cls):
            if f.name in raw and isinstance(raw[f.name], type(getattr(cfg, f.name))):
                setattr(cfg, f.name, raw[f.name])
        return cfg


@dataclass
class Settings:
    font_size: int = DEFAULT_FONT_SIZE
    fullscreen: bool = False
    show_dice: bool = True
    verbosity: str = "normal"
    autosave_minutes: int = 5
    auto_supplies: bool = True  # eat and drink from the pack when needed
    animations: str = "full"  # full, calm (no idle movement: water, fire, weather), off
    map_zoom: int = 32
    world_zoom: int = 24
    battle_companions: str = "command"  # COMPANION_CHOICES
    time_in_towns: str = "flows"  # TOWN_TIME_CHOICES: people walk their day while you stand and watch
    volume: int = 10  # everything (0-10)
    music_volume: int = 6
    effects_volume: int = 9
    interface_volume: int = 7  # clicks, pages, menus
    sound_in_background: bool = True  # keep playing while another window is in front
    muted: bool = False  # Ctrl M
    expansions_seen: list = field(default_factory=list)  # ids of the expansions pointed at on the shelf (no glint)

    def normalise(self) -> None:
        if self.font_size not in FONT_SIZES:
            self.font_size = min(FONT_SIZES, key=lambda s: abs(s - int(self.font_size)))
        if self.verbosity not in VERBOSITY_LEVELS:
            self.verbosity = "normal"
        if self.autosave_minutes not in AUTOSAVE_CHOICES:
            self.autosave_minutes = 5
        if self.animations not in ANIMATION_CHOICES:
            self.animations = "full"
        if self.map_zoom not in MAP_ZOOMS:
            self.map_zoom = 32
        if self.world_zoom not in WORLD_ZOOMS:
            self.world_zoom = 24
        if self.battle_companions not in COMPANION_CHOICES:
            self.battle_companions = "command"
        if self.time_in_towns not in TOWN_TIME_CHOICES:
            self.time_in_towns = "flows"
        for name in ("volume", "music_volume", "effects_volume", "interface_volume"):
            setattr(self, name, max(0, min(VOLUME_STEPS, int(getattr(self, name)))))
        self.expansions_seen = sorted({str(e) for e in self.expansions_seen if isinstance(e, str)})

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
