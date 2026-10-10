"""The game's sound: effects by name (data/sounds.json), interface sounds, and music by mood.

Screens and the app ask; nothing in the game's logic knows sound exists, and nothing waits for it. In a window the
sound goes to the speakers (SDL); headless (tests, the autoplay bot) and on a PC without a sound device the same calls
go to a silent backend, so the game behaves the same either way.

Two kinds of request:
* `play(id)` - a sound now (or after `delay` seconds, timed to the sample: the battle board uses it to put a blow's
  sound on the frame where it lands).
* `ui(id)` - the answer to something the player did. Only one per frame is played, the most important: a click that
  opens a screen sounds like the screen opening, not like both.
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from pathlib import Path

from realmwalker.audio.backend import SDLBackend, SilentBackend
from realmwalker.audio.bank import SoundBank
from realmwalker.audio.music import LevelStore, MusicLibrary, MusicPlayer

log = logging.getLogger("realmwalker.audio")

MAX_VOICES = 24
DEFAULT_COOLDOWN = 0.04


def level(step: int | float) -> float:
    """A volume setting (0-10) as a gain: a curve that sounds even to the ear (5 is about half as loud as 10)."""
    v = max(0.0, min(10.0, float(step))) / 10.0
    return v ** 1.5


class Audio:
    def __init__(self, *, bank: SoundBank, library: MusicLibrary, settings, clock: Callable[[], float], rng,
                 backend=None, levels_file: Path | None = None) -> None:
        self.bank = bank
        self.library = library
        self.settings = settings
        self.clock = clock
        self.rng = rng
        self.backend = backend if backend is not None else SilentBackend(clock)
        self.music = MusicPlayer(library, self.backend, clock, rng.child("music"),
                                 LevelStore(levels_file, library.builtin))
        self.voices: list[tuple[str, object]] = []
        self.last_played: dict[str, float] = {}  # sound id -> when it last started (counting any delay)
        self.last_file: dict[str, str] = {}
        self.history: deque[str] = deque(maxlen=64)  # what was played, newest last (tests, the debug console)
        self._pending: tuple[int, str] | None = None
        self.focused = True
        self.problems: list[str] = []
        self.unknown: set[str] = set()  # names asked for that data/sounds.json does not have (the autoplay bot checks)
        self.apply_settings()

    @property
    def real(self) -> bool:
        return bool(getattr(self.backend, "real", False))

    # ------------------------------------------------------------------ effects
    def play(self, sid: str, *, delay: float = 0.0, volume: float = 1.0) -> bool:
        """Play a sound by id. Returns whether it was played (not when unknown, too soon after itself, or silenced)."""
        d = self.bank.get(sid)
        if d is None:
            self.unknown.add(sid)
            return False
        group_gain = self._group_gain(d.get("group", "effects"))
        if group_gain <= 0 or volume <= 0:
            return False
        now = self.clock()
        at = now + max(0.0, delay)
        cooldown = float(d.get("cooldown", DEFAULT_COOLDOWN))
        if abs(at - self.last_played.get(sid, -1e9)) < cooldown:
            return False
        limit = int(d.get("max", 3))
        if sum(1 for s, _ in self.voices if s == sid) >= limit or len(self.voices) >= MAX_VOICES:
            return False
        files = list(d["files"])
        if len(files) > 1 and self.last_file.get(sid) in files:
            files.remove(self.last_file[sid])  # never the same one twice running
        rel = self.rng.choice(files)
        clip = self.bank.clip(rel)
        if clip is None:
            return False
        pitch = float(d.get("pitch", 0.03))
        ratio = 1.0 + self.rng.uniform(-pitch, pitch) if pitch > 0 else 1.0
        gain = group_gain * float(d.get("volume", 1.0)) * volume
        try:
            voice = self.backend.play(clip, gain, ratio, max(0.0, delay))
        except Exception as exc:
            self._problem(f"playing {sid}: {exc}")
            return False
        self.voices.append((sid, voice))
        self.last_played[sid] = at
        self.last_file[sid] = rel
        self.history.append(sid)
        return True

    def ui(self, sid: str | None) -> None:
        """The sound answering the player's input this frame; the most important request wins."""
        if not sid:
            return
        if sid not in self.bank:
            self.unknown.add(sid)
            return
        priority = int(self.bank.get(sid).get("priority", 1))
        if self._pending is None or priority >= self._pending[0]:
            self._pending = (priority, sid)

    @property
    def pending(self) -> str | None:
        return self._pending[1] if self._pending else None

    def _group_gain(self, group: str) -> float:
        s = self.settings
        return level(s.interface_volume if group == "interface" else s.effects_volume)

    # ------------------------------------------------------------------ music
    def want_music(self, mood: str | None) -> None:
        self.music.want(mood)

    def rescan_music(self) -> None:
        with self.music.lock:
            self.library.scan()
            self.music.bad.clear()
            self.music.recheck = True

    # ------------------------------------------------------------------ each frame
    def update(self) -> None:
        if self._pending is not None:
            _, sid = self._pending
            self._pending = None
            self.play(sid)
        if self.voices:
            alive = []
            for sid, v in self.voices:
                if v.finished():
                    v.close()
                else:
                    alive.append((sid, v))
            self.voices = alive
        if not self.real:
            self.music.tick()  # no music thread headless: the player is stepped with the frames

    # ------------------------------------------------------------------ settings and the window
    def apply_settings(self) -> None:
        s = self.settings
        master = level(s.volume)
        if s.muted or (not self.focused and not s.sound_in_background):
            master = 0.0
        try:
            self.backend.set_master(master)
        except Exception as exc:
            self._problem(f"setting the volume: {exc}")
        self.music.volume = level(s.music_volume)

    def set_focus(self, focused: bool) -> None:
        if focused != self.focused:
            self.focused = focused
            self.apply_settings()

    def _problem(self, text: str) -> None:
        if text not in self.problems:
            self.problems.append(text)
            log.warning("Sound: %s", text)

    def start(self) -> None:
        """Begin the music thread (only with real speakers; headless, `update` steps the music)."""
        if self.real:
            self.music.start()

    def close(self) -> None:
        try:
            self.music.stop()
        except Exception:
            log.exception("Could not stop the music")
        for _, v in self.voices:
            try:
                v.close()
            except Exception:
                pass
        self.voices = []
        self.backend.close()


def open_speakers() -> SDLBackend | None:
    """The sound device, or None when there is none (written to the log; the game plays on in silence)."""
    try:
        return SDLBackend()
    except Exception as exc:
        log.warning("No sound: the sound device could not be opened (%s)", exc)
        return None
