"""Weather: moving fronts of cloud, rain, snow and wind over the climate of each place.

Weather is not stored. It is a smooth, deterministic function of the world seed, the place and
the time: noise fields drift west to east and slowly change, so fronts roll across the map,
linger and break up. The same moment always has the same weather, so saves need nothing extra.

Air temperature = the place's yearly mean (world.temperature, which already includes height)
+ the season (a smooth curve through the calendar's monthly offsets) + day and night
+ the passing fronts. Rain is likelier where the land is wet; deserts rarely see it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from realmwalker.world.calendar import MINUTES_PER_DAY, MINUTES_PER_HOUR

FRONT_CELL = 22.0  # tiles between noise lattice points: fronts are a few days' walk across
FRONT_DRIFT = 1.6  # tiles per hour, west to east
FRONT_EVOLVE_HOURS = 30.0  # how long a front keeps its shape
WIND_CELL = 30.0


@dataclass(frozen=True)
class Weather:
    kind: str  # clear, cloudy, overcast, fog, drizzle, rain, storm, flurries, snow, blizzard, heat
    temp: float  # air temperature, degrees C
    wind: float  # km/h
    precip: float  # 0 dry .. 1 downpour
    cloud: float  # 0 clear sky .. 1 thick cloud
    visibility: float  # 1 clear .. 0.15 you can't see your hand (daylight only; night is separate)

    @property
    def snowing(self) -> bool:
        return self.kind in ("flurries", "snow", "blizzard")

    @property
    def raining(self) -> bool:
        return self.kind in ("drizzle", "rain", "storm")

    @property
    def wet_per_hour(self) -> float:
        """How fast an unprotected person gets soaked (0..100 wetness per hour)."""
        if self.raining:
            return 20.0 + 90.0 * self.precip
        if self.snowing:
            # Snow wets you slowly as it melts; dry powder in hard frost hardly at all.
            return 2.0 + 6.0 * self.precip if self.temp < -2 else 5.0 + 25.0 * self.precip
        if self.kind == "fog":
            return 3.0
        return 0.0

    def travel_factor(self) -> float:
        """How much longer each step takes in this weather."""
        return {"storm": 1.3, "rain": 1.1, "snow": 1.4, "blizzard": 2.0, "flurries": 1.1, "heat": 1.15,
                "fog": 1.05}.get(self.kind, 1.0)


KIND_WORDS = {
    "clear": "clear skies", "cloudy": "broken cloud", "overcast": "grey, heavy cloud", "fog": "thick fog",
    "drizzle": "a thin drizzle", "rain": "rain", "storm": "a storm, rain driving sideways",
    "flurries": "a few flakes of snow", "snow": "falling snow", "blizzard": "a blizzard",
    "heat": "a hard, heavy heat",
}


def wind_word(kph: float) -> str:
    if kph < 6:
        return "still air"
    if kph < 15:
        return "a light breeze"
    if kph < 28:
        return "a steady wind"
    if kph < 45:
        return "a strong wind"
    if kph < 65:
        return "a gale"
    return "a howling gale"


def describe(w: Weather) -> str:
    """'Rain, 8°C, a strong wind.'"""
    text = KIND_WORDS.get(w.kind, w.kind)
    return f"{text[:1].upper() + text[1:]}, {round(w.temp):d}°C, {wind_word(w.wind)}."


# ---------------------------------------------------------------------------- noise
def _hash01(ix, iy, it, seed: int):
    """Deterministic pseudo-random 0..1 for integer lattice points (numpy arrays of int64)."""
    h = (ix * 374761393 + iy * 668265263 + it * 1103515245 + seed * 1274126177) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h = (h ^ (h >> 16)) & 0xFFFFFFFF
    return h.astype(np.float64) / 4294967296.0


def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def noise3(x, y, t, seed: int):
    """Smooth value noise in (x, y, t); arrays broadcast. 0..1."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    t = np.asarray(t, dtype=np.float64)
    x0, y0, t0 = np.floor(x), np.floor(y), np.floor(t)
    fx, fy, ft = _smooth(x - x0), _smooth(y - y0), _smooth(t - t0)
    ix, iy, it = x0.astype(np.int64), y0.astype(np.int64), t0.astype(np.int64)
    out = 0.0
    for dx in (0, 1):
        wx = fx if dx else 1.0 - fx
        for dy in (0, 1):
            wy = fy if dy else 1.0 - fy
            for dt in (0, 1):
                wt = ft if dt else 1.0 - ft
                out = out + wx * wy * wt * _hash01(ix + dx, iy + dy, it + dt, seed)
    return out


def _noise3_scalar(x: float, y: float, t: float, seed: int) -> float:
    """The same value noise as noise3, for one point, in plain Python (much faster than numpy here)."""
    x0, y0, t0 = math.floor(x), math.floor(y), math.floor(t)
    fx, fy, ft = x - x0, y - y0, t - t0
    fx, fy, ft = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy), ft * ft * (3 - 2 * ft)
    ix, iy, it = int(x0), int(y0), int(t0)
    base = seed * 1274126177
    out = 0.0
    for dx in (0, 1):
        wx = fx if dx else 1.0 - fx
        hx = (ix + dx) * 374761393
        for dy in (0, 1):
            wy = fy if dy else 1.0 - fy
            hy = hx + (iy + dy) * 668265263
            for dt in (0, 1):
                wt = ft if dt else 1.0 - ft
                h = (hy + (it + dt) * 1103515245 + base) & 0xFFFFFFFF
                h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
                h = (h ^ (h >> 16)) & 0xFFFFFFFF
                out += wx * wy * wt * (h / 4294967296.0)
    return out


def _fbm3(x, y, t, seed: int, octaves: int = 3):
    total, amp, norm = 0.0, 1.0, 0.0
    scalar = isinstance(x, float)
    for o in range(octaves):
        fn = _noise3_scalar if scalar else noise3
        total = total + fn(x * (2 ** o), y * (2 ** o), t * (1.5 ** o), seed + o * 7919) * amp
        norm += amp
        amp *= 0.5
    return total / norm


def _stretch(v):
    """fbm bunches up around 0.5; spread it back towards 0..1."""
    if isinstance(v, float):
        return min(1.0, max(0.0, (v - 0.5) * 1.9 + 0.5))
    return np.clip((v - 0.5) * 1.9 + 0.5, 0.0, 1.0)


# ---------------------------------------------------------------------------- climate
def season_offset(calendar, minute: int) -> float:
    """Degrees added to the yearly mean on this day: a smooth curve through the month midpoints."""
    days = calendar.days_per_year
    dpm = calendar.days_per_month
    day = (minute / MINUTES_PER_DAY) % days
    pos = day / dpm - 0.5  # 0 at the middle of the first month
    i0 = int(math.floor(pos)) % len(calendar.months)
    i1 = (i0 + 1) % len(calendar.months)
    f = pos - math.floor(pos)
    f = f * f * (3 - 2 * f)
    return calendar.months[i0].temp_offset * (1 - f) + calendar.months[i1].temp_offset * f


def _fields(world, xs, ys, minute: int):
    seed = int(world.meta.seed) & 0x7FFFFFFF
    hours = minute / MINUTES_PER_HOUR
    drift = hours * FRONT_DRIFT
    fx = (xs - drift) / FRONT_CELL
    fy = ys / FRONT_CELL
    ft = hours / FRONT_EVOLVE_HOURS
    wet = _stretch(_fbm3(fx, fy, ft, seed + 11))
    warm = _stretch(_fbm3(fx + 40.0, fy + 17.0, ft * 0.7, seed + 23, octaves=2))
    wind = _stretch(_fbm3((xs - drift * 1.3) / WIND_CELL, ys / WIND_CELL, hours / 18.0, seed + 37, octaves=2))
    fog = (_noise3_scalar if isinstance(xs, float) else noise3)(xs / 9.0, ys / 9.0, hours / 6.0, seed + 51)
    return wet, warm, wind, fog


def _clip(v, lo: float, hi: float):
    if isinstance(v, float):
        return min(hi, max(lo, v))
    return np.clip(v, lo, hi)


def _combine(world, tables, xs, ys, minute: int, temperature, moisture, elevation):
    """Weather fields for one point (floats) or the whole map (arrays): temp, cloud, precip, wind, fog."""
    moment = tables.calendar.at(minute)
    wet, warm, wind_n, fog_n = _fields(world, xs, ys, minute)
    hour = moment.fractional_hour
    # Seasons swing hardest in the cold north and hardly at all in the warm south.
    latitude = ys / max(1, world.height - 1)
    swing = 1.15 - 0.85 * latitude
    season = season_offset(tables.calendar, minute) * swing
    cloud = _clip((wet - 0.3) * 1.9 + moisture * 0.25, 0.0, 1.0)
    # The day warms and the night cools, more under a clear sky and in dry country.
    dry = 1.0 - moisture
    diurnal = (2.5 + 4.0 * (1.0 - cloud) + 3.0 * dry) * math.cos(2 * math.pi * (hour - 15.0) / 24.0)
    temp = temperature + season + diurnal + (warm - 0.5) * 10.0
    rain_line = 0.9 - 0.28 * moisture
    precip = _clip((wet - rain_line) * 4.5, 0.0, 1.0)
    height = _clip(elevation / 3000.0, 0.0, 1.5)
    wind = 3.0 + 42.0 * wind_n ** 2 + 18.0 * height + 20.0 * precip
    return {"temp": temp, "cloud": cloud, "precip": precip, "wind": wind, "fog": fog_n, "hour": hour,
            "moisture": moisture, "season": moment.season}


def _kind(temp: float, cloud: float, precip: float, wind: float, fog: float, hour: float, moisture: float,
          season: str) -> tuple[str, float]:
    if precip > 0.0:
        snow = temp <= 0.5
        if precip > 0.6 and wind > 36:
            return ("blizzard", 0.2) if snow else ("storm", 0.55)
        if precip < 0.25:
            return ("flurries", 0.85) if snow else ("drizzle", 0.85)
        return ("snow", 0.6) if snow else ("rain", 0.75)
    if 3.0 <= hour <= 10.0 and moisture > 0.45 and wind < 14 and cloud > 0.25 and fog > 0.6:
        return "fog", 0.25
    if temp >= 31.0:
        return "heat", 0.95
    if cloud > 0.75:
        return "overcast", 0.95
    if cloud > 0.4:
        return "cloudy", 1.0
    return "clear", 1.0


def weather_at(world, tables, x: int, y: int, minute: int) -> Weather:
    """The weather at one overworld tile at one moment."""
    f = _combine(world, tables, float(x), float(y), minute, float(world.temperature[x, y]),
                 float(world.moisture[x, y]), float(max(0, int(world.elevation[x, y]))))
    temp, cloud, precip, wind, fog = (float(f[k]) for k in ("temp", "cloud", "precip", "wind", "fog"))
    kind, vis = _kind(temp, cloud, precip, wind, fog, f["hour"], float(world.moisture[x, y]), f["season"])
    return Weather(kind, round(temp, 1), round(wind, 1), round(precip, 2), round(cloud, 2), vis)


def weather_grid(world, tables, minute: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(precip, temp, cloud) over the whole map, for the world map's weather view."""
    xs, ys = np.meshgrid(np.arange(world.width, dtype=np.float64), np.arange(world.height, dtype=np.float64),
                         indexing="ij")
    f = _combine(world, tables, xs, ys, minute, world.temperature.astype(np.float64),
                 world.moisture.astype(np.float64), np.maximum(0, world.elevation).astype(np.float64))
    return f["precip"], f["temp"], f["cloud"]


class WeatherCache:
    """Remembers the weather at the player's tile for a few minutes of game time (it changes slowly)."""

    def __init__(self, minutes: int = 10) -> None:
        self.minutes = minutes
        self._key = None
        self._value: Weather | None = None

    def get(self, world, tables, x: int, y: int, minute: int) -> Weather:
        key = (x, y, minute // self.minutes)
        if key != self._key or self._value is None:
            self._value = weather_at(world, tables, x, y, minute)
            self._key = key
        return self._value
