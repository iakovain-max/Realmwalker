"""Music: tunes for each mood of the game, chosen from folders, faded and crossfaded, evened out in loudness.

A mood is a path like "travel/forest" or "combat/undead". Its tunes are the files in the matching folder: the player's
own music folder first (music/travel/forest), the tunes that ship with the game second (assets/music/travel/forest).
A mood with no tunes of its own borrows its parent's ("travel"), then the mood data/music.json names as its fallback
("tavern" -> "town"); with none anywhere, there is silence. The player's tunes for a mood replace the shipped ones.

How each mood plays (pauses between tunes, fades, playing once, picking up where it left off) is in data/music.json.
Tunes are read a little at a time (the `soundfile` package: OGG, MP3, FLAC, WAV) on a thread of their own, so a busy
frame never makes the music stutter. Each tune's loudness is measured the first time it plays and remembered, so a
loud tune and a quiet one sound alike.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from realmwalker.audio import levels

log = logging.getLogger("realmwalker.audio")

EXTENSIONS = (".ogg", ".mp3", ".flac", ".wav", ".opus")
TARGET_LUFS = -18.0  # every tune is brought to this loudness (the shipped ones already are)
AHEAD = 2.5  # seconds of music kept queued: the music thread may be late by this much without a gap
CHUNK = 0.5  # seconds read at a time
CROSSFADE = 1.5  # the next tune starts this long before the last one has finished playing
MEASURE_SECONDS = 90  # how much of a tune is measured for its loudness
RESUME_WITHIN = 240.0  # come back to a mood within this many seconds and its tune carries on where it was
TICK = 0.03

README = """\
YOUR MUSIC FOR REALMWALKER
==========================

Put music files (.ogg, .mp3, .flac or .wav) in these folders and the game plays them at the right moments.
There is nothing else to do: the game looks here every time it starts, and when you press "Look for new music"
on the Music page in Settings.

Each folder is a mood:

{moods}
A folder inside another is more particular: music in travel\\forest plays in forests, and anywhere without music
of its own (travel\\desert, say) the game plays what is in travel. Leave a folder empty and it borrows from the one
above it.

Your music for a mood replaces the music that comes with the game for that mood. To hear the game's own music
again, empty the folder.

Every tune is evened out to the same loudness the first time it plays, so a loud file and a quiet one sound alike.
The volume of music, effects and the interface are in Settings (Esc, then Settings).
"""


@dataclass
class Deck:
    """One tune being played: its file, its SDL stream, and its fade."""

    path: Path
    reader: object  # soundfile.SoundFile
    stream: object
    gain: float  # evens out its loudness
    fade: float = 0.0
    target: float = 1.0
    fade_time: float = 1.5
    read: int = 0  # frames read from the file
    done: bool = False  # nothing more will be read
    loop: bool = False  # starts again from the beginning when it ends (a single tune for a mood with no pauses)

    def played_frames(self) -> int:
        return max(0, self.read - int(self.stream.queued_seconds() * self.stream.rate))


@dataclass
class MoodState:
    resume: tuple[Path, int, float] | None = None  # tune, frame, when it was left
    last: list[Path] = field(default_factory=list)  # most recent first


class MusicLibrary:
    """What tunes there are for each mood, in the player's folder and the game's."""

    def __init__(self, spec: dict, builtin: Path | None, user: Path | None) -> None:
        self.spec = spec or {}
        self.moods: dict[str, dict] = {k: v for k, v in self.spec.get("moods", {}).items() if not k.startswith("_")}
        self.builtin = builtin
        self.user = user
        self.files: dict[str, list[Path]] = {}  # mood path -> the player's tunes
        self.shipped: dict[str, list[Path]] = {}  # mood path -> the game's tunes
        self.scan()

    @staticmethod
    def _walk(root: Path | None) -> dict[str, list[Path]]:
        out: dict[str, list[Path]] = {}
        if root is None or not root.is_dir():
            return out
        for dirpath, _dirs, names in os.walk(root):
            tunes = sorted(Path(dirpath) / n for n in names if n.lower().endswith(EXTENSIONS) and not n.startswith("."))
            if tunes:
                rel = Path(dirpath).relative_to(root).as_posix().lower()
                out[rel] = tunes
        return out

    def scan(self) -> None:
        self.files = self._walk(self.user)
        self.shipped = self._walk(self.builtin)

    def own(self, mood: str) -> list[Path]:
        mood = mood.lower()
        return self.files.get(mood) or self.shipped.get(mood) or []

    def settings(self, mood: str) -> dict:
        return self.moods.get(mood.split("/")[0], {})

    def resolve(self, mood: str | None) -> tuple[str, list[Path]]:
        """The mood whose tunes play for `mood` (itself, a parent, or a fallback), and those tunes."""
        seen = set()
        while mood and mood not in seen:
            seen.add(mood)
            parts = mood.split("/")
            for i in range(len(parts), 0, -1):
                m = "/".join(parts[:i])
                tunes = self.own(m)
                if tunes:
                    return m, tunes
            mood = self.moods.get(parts[0], {}).get("fallback") or ""
        return "", []

    def folders(self) -> list[str]:
        """Every folder the game makes for the player's music: the moods and their particular kinds."""
        out = []
        for mood, spec in self.moods.items():
            out.append(mood)
            out.extend(f"{mood}/{v}" for v in spec.get("kinds", []))
        return out

    def make_folders(self) -> None:
        """Create the player's music folders (and the note that explains them), if they are not there yet."""
        if self.user is None:
            return
        try:
            for rel in self.folders():
                (self.user / rel).mkdir(parents=True, exist_ok=True)
            lines = []
            for mood, spec in self.moods.items():
                lines.append(f"  {mood:10s} {spec.get('about', '')}")
                if spec.get("kinds"):
                    lines.append(f"  {'':10s} Folders inside it: {', '.join(spec['kinds'])}.")
                lines.append("")
            note = README.format(moods="\n".join(lines))
            readme = self.user / "README.txt"
            if not readme.exists() or readme.read_text(encoding="utf-8") != note:
                readme.write_text(note, encoding="utf-8")
        except OSError as exc:
            log.warning("Could not make the music folders in %s (%s)", self.user, exc)

    def count(self, mood: str) -> tuple[int, int]:
        """(the player's tunes, the game's tunes) in exactly this mood's folder."""
        mood = mood.lower()
        return len(self.files.get(mood, [])), len(self.shipped.get(mood, []))


class LevelStore:
    """Measured loudness of the player's tunes, remembered between sessions (music_levels.json)."""

    def __init__(self, path: Path | None, builtin: Path | None) -> None:
        self.path = path
        self.builtin = builtin
        self.data: dict[str, list[float]] = {}
        if path is not None and path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self.data = {k: v for k, v in raw.items() if isinstance(v, list) and len(v) == 2}
            except (OSError, ValueError):
                self.data = {}

    @staticmethod
    def _key(path: Path) -> str:
        st = path.stat()
        return f"{path.resolve()}|{st.st_size}|{int(st.st_mtime)}"

    def gain(self, path: Path, read: Callable[[Path], tuple[np.ndarray, int]]) -> float:
        if self.builtin is not None and self.builtin in path.parents:
            return 1.0  # the game's own tunes were evened out when they were made
        try:
            key = self._key(path)
        except OSError:
            return 1.0
        if key not in self.data:
            samples, rate = read(path)
            self.data[key] = [levels.integrated(samples, rate), levels.peak(samples)]
            self._save()
        lufs, pk = self.data[key]
        return levels.gain_to(lufs, TARGET_LUFS, pk, ceiling=0.95, most=3.0)

    def _save(self) -> None:
        if self.path is None:
            return
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            log.warning("Could not save %s", self.path)


def _gap(spec: dict) -> tuple[float, float]:
    gap = spec.get("gap") or [0, 0]
    return float(gap[0]), float(gap[1])


def open_tune(path: Path):
    import soundfile

    return soundfile.SoundFile(str(path))


def read_start(path: Path) -> tuple[np.ndarray, int]:
    """The first minute and a half of a tune, for measuring it."""
    with open_tune(path) as f:
        data = f.read(int(f.samplerate * MEASURE_SECONDS), dtype="float32", always_2d=True)
        return data, int(f.samplerate)


class MusicPlayer:
    """Plays the mood it is asked for. `want()` and `volume` are set from the game; `tick()` does the work (on the
    music thread in a window, or called by hand in tests)."""

    def __init__(self, library: MusicLibrary, backend, clock: Callable[[], float], rng, levels_store: LevelStore,
                 *, opener: Callable[[Path], object] = open_tune) -> None:
        self.library = library
        self.backend = backend
        self.clock = clock
        self.rng = rng
        self.levels = levels_store
        self.opener = opener
        self.lock = threading.RLock()
        self.wanted: str | None = None
        self.mood: str | None = None  # the mood being served
        self.pool: str = ""  # the folder its tunes come from
        self.volume = 1.0
        self.current: Deck | None = None
        self.fading: list[Deck] = []
        self.wait_until: float | None = None
        self.once_done = False
        self.states: dict[str, MoodState] = {}
        self.bad: set[Path] = set()
        self.broken = ""  # why music stopped for good this session
        self.preview: str | None = None  # a mood being listened to from the Music page
        self.recheck = False  # the folders were looked at again: choose afresh
        self.started: list[str] = []  # the tunes begun this session, newest last (the smoke test checks it)
        self._last = clock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # ------------------------------------------------------------------ asked from the game
    def want(self, mood: str | None) -> None:
        self.wanted = mood

    def now_playing(self) -> str:
        deck = self.current
        if deck is None:
            return ""
        name = " ".join(w[:1].upper() + w[1:] for w in deck.path.stem.replace("_", " ").split())
        return f"{name} ({self.pool})" if self.pool else name

    # ------------------------------------------------------------------ the thread
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="music", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        with self.lock:
            for d in [self.current, *self.fading]:
                if d is not None:
                    self._close(d)
            self.current, self.fading = None, []

    def _run(self) -> None:
        while not self._stop.wait(TICK):
            try:
                self.tick()
            except Exception as exc:
                log.exception("Music stopped after an error")
                self.broken = str(exc) or exc.__class__.__name__
                with self.lock:
                    for d in [self.current, *self.fading]:
                        if d is not None:
                            self._close(d)
                    self.current, self.fading = None, []
                return

    # ------------------------------------------------------------------ the work
    def tick(self) -> None:
        with self.lock:
            now = self.clock()
            dt = max(0.0, min(0.5, now - self._last))
            self._last = now
            wanted = self.preview if self.preview is not None else self.wanted
            if wanted != self.mood or self.recheck:
                self.recheck = False
                self._switch(wanted, now)
            deck = self.current
            if deck is not None:
                self._feed(deck, now)
            if self.current is None and self.wait_until is not None and now >= self.wait_until:
                self.wait_until = None
                self._start_next(now)
            spec = self.library.settings(self.pool) if self.pool else {}
            mood_volume = float(spec.get("volume", 1.0))
            for d in [self.current, *self.fading]:
                if d is None:
                    continue
                if d.fade != d.target:
                    step = dt / max(0.05, d.fade_time)
                    d.fade = min(d.target, d.fade + step) if d.target > d.fade else max(d.target, d.fade - step)
                d.stream.set_gain(d.fade * d.gain * self.volume * mood_volume)
            for d in list(self.fading):
                if (d.target == 0 and d.fade <= 0) or d.stream.finished():
                    self.fading.remove(d)
                    self._close(d)

    def _state(self, pool: str) -> MoodState:
        return self.states.setdefault(pool, MoodState())

    def _switch(self, mood: str | None, now: float) -> None:
        pool, tunes = self.library.resolve(mood)
        self.mood = mood
        if pool == self.pool:
            # The same music serves the new mood: carry on (a forest, then hills, both play "travel"). Only if the
            # tune playing is no longer among them (the player has just added their own) does it give way.
            if self.current is not None and self.current.path in tunes:
                spec = self.library.settings(pool)
                self.current.loop = len(tunes) == 1 and _gap(spec)[1] <= 0 and not spec.get("once")
                return
            if self.current is None and (self.wait_until is not None or self.once_done):
                return
        deck = self.current
        if deck is not None:
            spec = self.library.settings(self.pool)
            if spec.get("resume", False) and not deck.done:
                self._state(self.pool).resume = (deck.path, deck.played_frames(), now)
            deck.target = 0.0
            deck.fade_time = float(spec.get("fade_out", 2.0))
            self.fading.append(deck)
            self.current = None
        self.pool = pool
        self.wait_until = None
        self.once_done = False
        if not tunes:
            return
        spec = self.library.settings(pool)
        st = self._state(pool)
        if st.resume is not None:
            path, frame, when = st.resume
            st.resume = None
            if now - when <= RESUME_WITHIN and path in tunes and path not in self.bad:
                if self._start(path, now, frame=frame, fade_in=float(spec.get("fade_in", 2.0))):
                    return
        first = spec.get("first")
        if first:
            self.wait_until = now + self.rng.uniform(float(first[0]), float(first[1]))
        else:
            self._start_next(now)

    def _pick(self, tunes: list[Path]) -> Path | None:
        good = [t for t in tunes if t not in self.bad]
        if not good:
            return None
        st = self._state(self.pool)
        fresh = [t for t in good if t not in st.last[: max(0, len(good) // 2)]] or good
        return self.rng.choice(fresh)

    def _start_next(self, now: float, fade_in: float | None = None) -> None:
        _, tunes = self.library.resolve(self.mood)
        for _ in range(3):
            path = self._pick(tunes)
            if path is None:
                return
            spec = self.library.settings(self.pool)
            if self._start(path, now, fade_in=float(spec.get("fade_in", 2.0)) if fade_in is None else fade_in):
                return

    def _start(self, path: Path, now: float, *, frame: int = 0, fade_in: float = 2.0) -> bool:
        try:
            reader = self.opener(path)
            gain = self.levels.gain(path, read_start)
            if frame:
                reader.seek(min(frame, max(0, reader.frames - 1)))
        except Exception as exc:
            log.warning("Could not play %s (%s); it is skipped from now on", path.name, exc)
            self.bad.add(path)
            return False
        spec = self.library.settings(self.pool)
        _, tunes = self.library.resolve(self.mood)
        stream = self.backend.stream(int(reader.samplerate), int(reader.channels))
        deck = Deck(path, reader, stream, gain, fade=0.0 if fade_in > 0 else 1.0, fade_time=max(0.05, fade_in),
                    read=frame, loop=len(tunes) == 1 and _gap(spec)[1] <= 0 and not spec.get("once"))
        st = self._state(self.pool)
        st.last = [path] + [p for p in st.last if p != path]
        self.current = deck
        log.info("Music: %s (%s)", path.name, self.pool)
        self.started = (self.started + [path.name])[-20:]
        self._feed(deck, now)
        return True

    def _feed(self, deck: Deck, now: float) -> None:
        rate = deck.stream.rate
        while not deck.done and deck.stream.queued_seconds() < AHEAD:
            block = deck.reader.read(int(rate * CHUNK), dtype="float32", always_2d=True)
            if len(block):
                deck.stream.queue(block)
                deck.read += len(block)
            if len(block) < int(rate * CHUNK):
                if deck.loop and deck.reader.frames > 0:
                    deck.reader.seek(0)  # a single tune with no pauses goes round without a seam
                    deck.read = 0
                else:
                    deck.done = True
        if not deck.done:
            return
        left = deck.stream.queued_seconds()
        spec = self.library.settings(self.pool)
        if spec.get("once"):
            if left <= 0:
                self._retire(deck)
                self.once_done = True
            return
        gap = _gap(spec)
        if gap[1] <= 0:
            if left <= CROSSFADE:  # the next tune begins as this one rings out
                self._retire(deck)
                self._start_next(now, fade_in=1.0)
        elif left <= 0:
            self._retire(deck)
            self.wait_until = now + self.rng.uniform(gap[0], gap[1])

    def _retire(self, deck: Deck) -> None:
        """A tune that has been read to the end: it plays out what is queued, then is closed."""
        if self.current is deck:
            self.current = None
        deck.target = deck.fade
        self.fading.append(deck)

    def _close(self, deck: Deck) -> None:
        try:
            deck.stream.close()
        finally:
            try:
                deck.reader.close()
            except Exception:
                pass
