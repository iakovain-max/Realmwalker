"""Where sound goes: the speakers (SDL, through tcod, mixing on its own thread in C), or nowhere.

Every effect gets an SDL audio stream of its own with the whole clip queued at once (a delay is queued as silence in
front of it, so timing does not depend on the frame rate); music streams are topped up a little at a time from the
music thread. SDL mixes all the streams bound to the device, so no Python runs on the audio thread.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import numpy as np

from realmwalker.audio.bank import Clip

log = logging.getLogger("realmwalker.audio")

DEVICE_RATE = 48000


class SilentBackend:
    """No speakers (tests, the autoplay bot, a PC without a sound device). Streams drain by the clock as if they were
    being played, so everything above this behaves exactly as it would with sound."""

    real = False

    def __init__(self, clock: Callable[[], float]) -> None:
        self.clock = clock
        self.master = 1.0
        self.voices: list[SilentStream] = []

    def play(self, clip: Clip, gain: float, ratio: float, delay: float) -> SilentStream:
        s = SilentStream(self.clock, clip.rate, clip.samples.shape[1])
        s.gain, s.ratio = gain, ratio
        s.queue(np.zeros((int(delay * clip.rate), clip.samples.shape[1]), np.float32))
        s.queue(clip.samples)
        self.voices.append(s)
        return s

    def stream(self, rate: int, channels: int) -> SilentStream:
        return SilentStream(self.clock, rate, channels)

    def set_master(self, gain: float) -> None:
        self.master = gain

    def close(self) -> None:
        pass


class SilentStream:
    def __init__(self, clock: Callable[[], float], rate: int, channels: int) -> None:
        self.clock = clock
        self.rate = rate
        self.channels = channels
        self.gain = 1.0
        self.ratio = 1.0
        self.frames = 0  # queued, including what has "played"
        self.start = clock()
        self.closed = False

    def queue(self, samples: np.ndarray) -> None:
        now = self.clock()
        played = min(self.frames, int((now - self.start) * self.rate * self.ratio))
        if played >= self.frames:  # it had run dry: playing starts again from now
            self.start, self.frames = now, 0
        self.frames += len(samples)

    def queued_seconds(self) -> float:
        played = (self.clock() - self.start) * self.rate * self.ratio
        return max(0.0, (self.frames - played) / self.rate)

    def finished(self) -> bool:
        return self.queued_seconds() <= 0

    def set_gain(self, gain: float) -> None:
        self.gain = gain

    def close(self) -> None:
        self.closed = True


class SDLBackend:
    """The speakers: one logical SDL playback device (stereo, float), shared by effects and music."""

    real = True

    def __init__(self) -> None:
        import tcod.sdl.audio as sdl_audio

        self.device = sdl_audio.get_default_playback().open(format=np.float32, channels=2, frequency=DEVICE_RATE)
        log.info("Sound device opened (%s): %s Hz, %s channels", driver_name(), self.device.frequency,
                 self.device.channels)

    def play(self, clip: Clip, gain: float, ratio: float, delay: float) -> SDLStream:
        s = self.stream(clip.rate, clip.samples.shape[1])
        s.set_gain(gain)
        if abs(ratio - 1.0) > 1e-4:
            s.stream.frequency_ratio = ratio
        if delay > 0.001:
            s.queue(np.zeros((int(delay * clip.rate), clip.samples.shape[1]), np.float32))
        s.queue(clip.samples)
        s.stream.flush()
        return s

    def stream(self, rate: int, channels: int) -> SDLStream:
        return SDLStream(self.device.new_stream(format=np.float32, channels=channels, frequency=rate), rate, channels)

    def set_master(self, gain: float) -> None:
        self.device.gain = max(0.0, float(gain))

    def close(self) -> None:
        try:
            self.device.close()
        except Exception:
            log.exception("Could not close the sound device")


def driver_name() -> str:
    """Which of SDL's sound drivers is in use ("wasapi", "directsound", "dummy"...), for the log."""
    try:
        from tcod.cffi import ffi, lib

        name = lib.SDL_GetCurrentAudioDriver()
        return ffi.string(name).decode("utf-8", "replace") if name != ffi.NULL else "none"
    except Exception:
        return "unknown"


class SDLStream:
    def __init__(self, stream, rate: int, channels: int) -> None:
        self.stream = stream
        self.rate = rate
        self.channels = channels
        self._gain = -1.0
        self.closed = False

    def queue(self, samples: np.ndarray) -> None:
        if len(samples):
            self.stream.queue_audio(np.ascontiguousarray(samples, dtype=np.float32))

    def queued_seconds(self) -> float:
        return self.stream.queued_samples / self.rate

    def finished(self) -> bool:
        return self.stream.queued_bytes <= 0 and self.stream.available_bytes <= 0

    def set_gain(self, gain: float) -> None:
        gain = max(0.0, float(gain))
        if abs(gain - self._gain) > 1e-3:
            self.stream.gain = gain
            self._gain = gain

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.stream.close()
