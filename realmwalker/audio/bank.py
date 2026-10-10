"""The sound effects: what data/sounds.json names, read from assets/sounds once and kept in memory.

Effects are short 16-bit WAV files (read with the standard library, so they work even if the music decoder is
missing); anything else (OGG, FLAC, MP3) is read with the `soundfile` package when it is there.
"""

from __future__ import annotations

import logging
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger("realmwalker.audio")

GROUPS = ("interface", "effects")


@dataclass
class Clip:
    samples: np.ndarray  # float32 [frames, channels]
    rate: int

    @property
    def seconds(self) -> float:
        return len(self.samples) / self.rate


def read_wav(path: Path) -> Clip:
    with wave.open(str(path), "rb") as w:
        width, channels, rate = w.getsampwidth(), w.getnchannels(), w.getframerate()
        raw = w.readframes(w.getnframes())
    if width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"{path.name}: {width * 8}-bit WAV files are not supported")
    return Clip(np.ascontiguousarray(data.reshape(-1, channels)), rate)


def read_any(path: Path) -> Clip:
    if path.suffix.lower() == ".wav":
        try:
            return read_wav(path)
        except (wave.Error, ValueError, EOFError):
            pass  # a WAV the standard library cannot read (float, ADPCM...): try soundfile
    import soundfile

    data, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
    return Clip(np.ascontiguousarray(data), int(rate))


class SoundBank:
    """Sound definitions by id, and their clips (loaded on first use)."""

    def __init__(self, spec: dict, folder: Path) -> None:
        self.defs: dict[str, dict] = {k: v for k, v in (spec or {}).get("sounds", {}).items() if not k.startswith("_")}
        self.folder = folder
        self._clips: dict[str, Clip | None] = {}
        self.problems: list[str] = []

    def __contains__(self, sid: str) -> bool:
        return sid in self.defs

    def get(self, sid: str) -> dict | None:
        return self.defs.get(sid)

    def clip(self, rel: str) -> Clip | None:
        if rel not in self._clips:
            try:
                self._clips[rel] = read_any(self.folder / rel)
            except Exception as exc:  # a missing or broken file is silent, once, and written down
                self._clips[rel] = None
                self.problems.append(f"{rel}: {exc}")
                log.warning("Could not read sound %s (%s)", rel, exc)
        return self._clips[rel]

    def preload(self) -> None:
        for d in self.defs.values():
            for rel in d["files"]:
                self.clip(rel)
