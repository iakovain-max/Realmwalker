"""World generation, in the order the design asks for:

1. Terrain: elevation, the sea, rivers running downhill to it, lakes in the hollows.
2. Climate and biomes: temperature from latitude and height, rain from the sea and mountains.
3. Named regions, settlements (by habitability and culture), roads between them, old sites.
4. (M6) History and politics.  5. Flavour text is added lazily, with built-in fallbacks.

Everything is derived from the seed, so the same seed and options always give the same world.
Runs in a background thread; `stage` and `fraction` report progress, `preview` holds arrays to draw.
"""

from __future__ import annotations

import datetime
import logging
import math
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import tcod.path

from realmwalker.core.rng import RNG
from realmwalker.world import hydrology
from realmwalker.world.model import DIRS, NO_CULTURE, WORLD_SIZES, Area, Settlement, Site, World, WorldMeta
from realmwalker.world.names import forge
from realmwalker.world.naming import Namer
from realmwalker.world.noise import fbm, normalise, ridged
from realmwalker.world.tables import Tables

log = logging.getLogger("realmwalker.worldgen")

GENERATOR_VERSION = 2  # 2: lands, climates, great ranges, the new biomes, wonders
SEA_FRACTION = 0.40

SETTLEMENT_COUNTS = {
    # kind: (small, medium, large), min spacing in tiles
    "city": ((2, 3, 5), 28),
    "town": ((5, 8, 13), 13),
    "village": ((12, 22, 38), 7),
    "hamlet": ((14, 26, 44), 4),
}
SPECIAL_COUNTS = {"hold": (1, 2, 3), "elfhall": (1, 2, 3)}
SITE_COUNTS = {"ruin": (6, 11, 18), "cave": (5, 9, 15), "barrow": (4, 7, 11), "tower": (3, 5, 8)}

ROAD_COST = {
    "plains": 10, "coast": 10, "forest": 16, "pine_forest": 16, "hills": 22, "mountains": 70,
    "high_mountains": 250, "marsh": 40, "tundra": 16, "desert": 20, "ocean": 0, "lake": 0,
    "glacier": 120, "steppe": 10, "savanna": 12, "jungle": 45, "dunes": 60, "badlands": 30, "salt_flat": 16,
    "volcanic": 50, "fey_forest": 24,
}
HABITABILITY = {
    "plains": 1.0, "coast": 0.9, "forest": 0.55, "pine_forest": 0.4, "hills": 0.6, "mountains": 0.05,
    "high_mountains": 0.0, "marsh": 0.2, "tundra": 0.15, "desert": 0.15, "ocean": 0.0, "lake": 0.0,
    "glacier": 0.0, "steppe": 0.7, "savanna": 0.7, "jungle": 0.35, "dunes": 0.03, "badlands": 0.2, "salt_flat": 0.02,
    "volcanic": 0.08, "fey_forest": 0.2,
}
CULTURE_COST = {  # how hard a people finds it to spread across each kind of land
    "plains": 8, "coast": 8, "forest": 12, "pine_forest": 13, "hills": 16, "mountains": 45, "high_mountains": 90,
    "marsh": 22, "tundra": 16, "desert": 18, "lake": 20,
    "glacier": 70, "steppe": 7, "savanna": 9, "jungle": 20, "dunes": 30, "badlands": 22, "salt_flat": 30,
    "volcanic": 30, "fey_forest": 18,
}
WILDNESS = {
    "plains": 0, "coast": 0, "forest": 1, "pine_forest": 1, "hills": 1, "mountains": 2, "high_mountains": 3,
    "marsh": 2, "tundra": 1, "desert": 1, "ocean": 0, "lake": 0,
    "glacier": 3, "steppe": 1, "savanna": 1, "jungle": 2, "dunes": 2, "badlands": 2, "salt_flat": 2, "volcanic": 3,
    "fey_forest": 2,
}

# The lie of the land, and the climate (world options; "random" picks one by these weights).
LANDS = ("continent", "islands", "twin", "inland_sea")
LAND_WEIGHTS = (6, 2, 2, 2)
CLIMATES = ("frozen", "cold", "temperate", "warm", "scorched", "varied")
CLIMATE_WEIGHTS = (1, 2, 6, 2, 1, 2)
SEA_FRACTION_OF = {"continent": SEA_FRACTION, "islands": 0.56, "twin": 0.46, "inland_sea": 0.44}
# The year's mean temperature at sea level: the far north, the middle and the far south of the map (degrees C).
CLIMATE_TEMPERATURE = {"frozen": (-32.0, -7.0, 10.0), "cold": (-26.0, 3.0, 22.0), "temperate": (-19.0, 12.0, 31.0),
                       "warm": (-9.0, 16.0, 36.0), "scorched": (0.0, 23.0, 41.0), "varied": (-27.0, 10.0, 39.0)}
TOP_OF_THE_WORLD = (6400.0, 8850.0)  # how high the highest peak stands (m), chosen per world


@dataclass
class WorldOptions:
    name: str
    seed: int
    size: str = "medium"
    danger: int = 2  # 1 low, 2 normal, 3 high, 4 brutal
    magic: int = 2  # 1 scarce, 2 rare, 3 uncommon
    history: int = 0  # years of history to live (0: the usual, data/politics.json "history_years")
    land: str = "random"  # LANDS, or random
    climate: str = "random"  # CLIMATES, or random


class WorldGenerator:
    STAGES = [
        ("Raising the land from the sea", 0.04),
        ("Carving rivers and filling lakes", 0.12),
        ("Setting the winds and the seasons", 0.16),
        ("Growing forests and fens", 0.19),
        ("Naming the land", 0.24),
        ("Finding where people could live", 0.27),
        ("Laying roads", 0.33),
        ("Scattering the old places of the wild", 0.36),
        ("Living the ages", 0.38),
        ("Finishing", 1.0),
    ]
    AGES_FROM, AGES_TO = 0.38, 0.99

    def __init__(self, options: WorldOptions, tables: Tables, progress: Callable[[str, float], None] | None = None) -> None:
        self.opt = options
        self.tables = tables
        self.progress_cb = progress
        self.rng = RNG(options.seed, "worldgen")
        self.w, self.h = WORLD_SIZES.get(options.size, WORLD_SIZES["medium"])
        self.size_index = ["small", "medium", "large"].index(options.size) if options.size in WORLD_SIZES else 1
        self.stage = "Starting"
        self.fraction = 0.0
        self.preview: dict[str, np.ndarray] = {}
        self.B = tables.biomes.index
        self.doomed: list[dict] = []  # places that will stand for a while in the ages, and be ruins today
        self.ages = None  # (year, figures, events, headline) while the history is being lived
        self.places: tuple = ()  # (x, y, kind or "ruin") of every place founded so far in the ages
        self.sim = None
        self.history_years = int(options.history or tables.politics["history_years"])
        pick = self.rng.child("options")
        self.land = options.land if options.land in LANDS else pick.weighted(list(LANDS), list(LAND_WEIGHTS))
        self.climate = options.climate if options.climate in CLIMATES else \
            pick.weighted(list(CLIMATES), list(CLIMATE_WEIGHTS))
        self.volcanoes: list[tuple[int, int]] = []  # cones raised in the land (world/wonders.py names them)
        self.relief = np.zeros((self.w, self.h), dtype=np.uint8)
        self.wonders: list = []

    def _progress(self, i: int) -> None:
        self.stage, self.fraction = self.STAGES[i]
        if self.progress_cb:
            self.progress_cb(self.stage, self.fraction)

    # ------------------------------------------------------------------ entry point
    def generate(self) -> World:
        started = time.monotonic()
        self._progress(0)
        self._elevation()
        self._progress(1)
        self._climate_base()
        self._water()
        self._progress(2)
        self._climate()
        self._progress(3)
        self._biomes()
        from realmwalker.world import wonders

        self.wonders = wonders.place(self)
        self._progress(4)
        self.forge = forge(self.opt.seed, self.tables)
        self.namer = Namer(self.tables.place_names, self.rng.child("names"), forge=self.forge)
        self._cultures()
        wonders.name_all(self)
        self._areas()
        self._progress(5)
        self._settlements()
        self._progress(6)
        self._roads()
        self._progress(7)
        self._danger()
        self._sites()
        self._progress(8)
        world = self._assemble()
        self.tables.cultures.choose_folk(world, self.rng.child("folk"))  # what this world calls each people
        from realmwalker.world.ages import AgeSim

        self.sim = AgeSim(world, self.tables, self.rng.child("ages"), years=self.history_years, spots=self.doomed,
                          namer=self.namer, progress=self._ages_progress)
        self.sim.run()
        self.sim = None
        self._great_cities(world)
        self._progress(9)
        log.info("Generated world '%s' (seed %d, %s) in %.1f s: %d settlements, %d sites, %d named areas, "
                 "%d years of history (%d figures, %d events)", world.meta.name, world.meta.seed, world.meta.size,
                 time.monotonic() - started, len(world.settlements), len(world.sites), len(world.areas),
                 self.history_years, len(world.figures), len(world.history))
        return world

    def _great_cities(self, world: World) -> None:
        """The world's great cities (data/towns.json "great"): its biggest cities when the ages are done, grown to many
        times the size of any other - a capital of tens of thousands among towns of a few thousand. Their close-up
        maps are the biggest there are (towns.size_of)."""
        spec = (getattr(self.tables, "towns", None) or {}).get("great")
        if not spec:
            return
        n = spec["count"][self.size_index]
        rng = self.rng.child("great")
        cities = sorted((s for s in world.settlements if s.kind == "city"), key=lambda s: (-s.population, s.id))
        for s in cities[:n]:
            s.great = True
            s.population = int(s.population * rng.uniform(*spec["times"]))

    def _ages_progress(self, year: int, figures: int, events: int, headline: str) -> None:
        start = self.tables.calendar.start_year - self.history_years
        done = (year - start + 1) / max(1, self.history_years)
        self.ages = (year, figures, events, headline)
        sim = self.sim
        if sim is not None:
            # What stands and what has fallen, for the map shown while the ages are lived (read by the UI thread).
            self.places = tuple((sp.x, sp.y, sp.kind_now if sp.standing else "ruin") for sp in sim.land.spots
                                if sp.founded is not None)
        self.fraction = self.AGES_FROM + (self.AGES_TO - self.AGES_FROM) * min(1.0, done)
        if self.progress_cb:
            self.progress_cb(self.stage, self.fraction)

    # ------------------------------------------------------------------ 1. terrain
    def _elevation(self) -> None:
        """Shape the coastline first, then build land height from distance inland, rolling
        noise and a few ridged mountain ranges, so lowlands, uplands and ranges all appear."""
        w, h = self.w, self.h
        g = self.rng.numpy("elevation")
        shape = self._land_shape(g)
        sea = float(np.quantile(shape, SEA_FRACTION_OF.get(self.land, SEA_FRACTION)))
        below = shape < sea
        labels, sizes = hydrology.label_components(below)
        border = set(labels[0, :].tolist()) | set(labels[-1, :].tolist()) | set(labels[:, 0].tolist()) | set(labels[:, -1].tolist())
        border.discard(-1)
        # Water that reaches the edge is the ocean; so is any great inland sea, even with no strait to the open sea.
        seas = border | {i for i, n in enumerate(sizes) if n >= w * h * 0.012}
        ocean = np.isin(labels, list(seas)) if seas else below
        # Keep the edge of the map as sea so nobody walks off the world.
        ocean[0, :] = ocean[-1, :] = True
        ocean[:, 0] = ocean[:, -1] = True

        dist = np.full((w, h), 10**6, dtype=np.int32)
        dist[ocean] = 0
        tcod.path.dijkstra2d(dist, np.ones((w, h), dtype=np.int32), 2, 3, out=dist)
        inland = np.clip((dist / 2.0) / (w * 0.14), 0, 1)
        rolling = fbm(g, w, h, cell=w / 7, octaves=5)
        ranges = ridged(g, w, h, cell=w / 3.2, octaves=5)
        range_mask = np.clip((fbm(g, w, h, cell=w / 2.4, octaves=2) - 0.52) * 3.2, 0, 1)
        land_h = 0.30 * inland + 0.30 * rolling ** 1.5 + 0.70 * ranges * range_mask * np.clip(inland * 2.5, 0, 1)
        # The great ranges: a few long spines raised far above the rest, the roofs of the world.
        land_h = land_h + 1.25 * self._great_ranges(g, ocean, inland)
        # Tablelands: high country ending in a scarp all round, the cliffs a traveller sees for a day before them.
        plateau = self._plateaus(g, ocean, inland)
        land_h = land_h + 0.30 * plateau
        land_h = land_h + self._volcanoes(g, ocean, dist)
        land_h = np.clip(land_h, 0, None)

        # Carve a few basins that will fill with water: the world's lakes.
        lake_count = (4, 7, 11)[self.size_index]
        candidates = np.argwhere(~ocean & (dist > 10) & (land_h < 0.45))
        yy, xx = np.meshgrid(np.arange(h), np.arange(w))
        for _ in range(lake_count if len(candidates) else 0):
            cx, cy = candidates[g.integers(len(candidates))]
            radius = g.uniform(1.5, 3.5)
            bowl = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * radius**2)))
            land_h = land_h - bowl * 0.12

        land_h = np.clip(land_h, 0.0, None)
        e = np.where(ocean, sea - 0.01 - (1 - shape) * 0.01, sea + 0.0005 + land_h * 0.5)
        # Heights by percentile, so every world gets a sensible mix of lowland, hills and peaks; the very top (the
        # crests of the great ranges) climbs to a height chosen for the world.
        top = self.rng.child("top").uniform(*TOP_OF_THE_WORLD)
        levels = np.quantile(land_h[~ocean], [0.0, 0.55, 0.75, 0.885, 0.965, 0.992, 1.0])
        levels = np.maximum.accumulate(levels + np.arange(len(levels)) * 1e-9)
        land_m = np.interp(land_h, levels, [0.0, 280.0, 650.0, 1400.0, 2600.0, 4700.0, top])
        meters = np.where(ocean, -np.clip((sea - shape) / max(sea, 1e-6), 0, 1) * 900 - 5, land_m)
        self.e = e
        self.sea = sea
        self.ocean = ocean
        self.meters = meters
        self.plateau = plateau
        self.preview["elevation"] = meters

    def _land_shape(self, g: np.random.Generator) -> np.ndarray:
        """Where the land rises out of the sea, by the world's lie of the land: one continent, a scatter of islands,
        two lands with a sea between, or a continent round an inland sea."""
        w, h = self.w, self.h
        r = self.rng.child("land shape")
        base = fbm(g, w, h, cell=w / 2.2, octaves=6, persistence=0.52)
        detail = fbm(g, w, h, cell=w / 9, octaves=4)
        xs = np.linspace(-1, 1, w)[:, None]
        ys = np.linspace(-1, 1, h)[None, :]
        edge_noise = fbm(g, w, h, cell=w / 6, octaves=3)
        wobble = (edge_noise - 0.5) * 0.45
        if self.land == "islands":
            d = np.full((w, h), 9.0)
            centres: list[tuple[float, float]] = []
            for _ in range(200):  # islands with open sea between them
                if len(centres) >= (6, 8, 10)[self.size_index]:
                    break
                cx, cy = r.uniform(-0.75, 0.75), r.uniform(-0.7, 0.7)
                if all(math.hypot(cx - ox, cy - oy) > 0.42 for ox, oy in centres):
                    centres.append((cx, cy))
            for cx, cy in centres:
                rad = r.uniform(0.14, 0.27)
                d = np.minimum(d, np.sqrt(((xs - cx) / rad) ** 2 + ((ys - cy) / rad) ** 2) * 0.62)
            d = d + wobble * 1.1
        elif self.land == "twin":
            if r.chance(0.65):  # side by side
                a, b = (-0.5, r.uniform(-0.15, 0.15)), (0.5, r.uniform(-0.15, 0.15))
            else:  # one above the other
                a, b = (r.uniform(-0.15, 0.15), -0.5), (r.uniform(-0.15, 0.15), 0.5)
            ra, rb = r.uniform(0.5, 0.62), r.uniform(0.42, 0.56)
            da = np.sqrt(((xs - a[0]) / ra) ** 2 + ((ys - a[1]) / ra) ** 2)
            db = np.sqrt(((xs - b[0]) / rb) ** 2 + ((ys - b[1]) / rb) ** 2)
            d = np.minimum(da, db) * 0.78 + wobble
        else:
            d = np.sqrt((xs * 1.02) ** 2 + (ys * 1.05) ** 2) + wobble
        falloff = np.clip(d, 0, 2) ** 2.4
        shape = normalise(base * 0.65 + detail * 0.35 - falloff * 0.9)
        if self.land == "inland_sea":
            cx, cy = r.uniform(-0.25, 0.25), r.uniform(-0.2, 0.2)
            sigma = r.uniform(0.19, 0.25)
            basin = np.exp(-((xs - cx) ** 2 + (ys - cy) ** 2) / (2 * sigma ** 2))
            ang = r.uniform(0, math.tau)  # a strait out to the open sea
            ux, uy = math.cos(ang), math.sin(ang)
            along = (xs - cx) * ux + (ys - cy) * uy
            across = np.abs(-(xs - cx) * uy + (ys - cy) * ux)
            strait = np.exp(-(across / 0.05) ** 2) * (along > 0)
            shape = normalise(shape - basin * 0.55 - strait * 0.45)
        return shape

    def _great_ranges(self, g: np.random.Generator, ocean: np.ndarray, inland: np.ndarray) -> np.ndarray:
        """One to four spines wandering across the land; returns how much each square is lifted by them (0..1)."""
        w, h = self.w, self.h
        r = self.rng.child("great ranges")
        count = r.randint(*((1, 2), (2, 3), (2, 4))[self.size_index])
        if self.land == "islands":
            count = max(1, count - 1)
        spine = np.zeros((w, h), dtype=bool)
        starts = np.argwhere(~ocean & (inland > 0.25))
        if not len(starts):
            return np.zeros((w, h), np.float32)
        self.spines: list[list[tuple[int, int]]] = []
        for _ in range(count):
            x, y = (float(v) for v in starts[r.randint(0, len(starts) - 1)])
            ang = r.uniform(0, math.tau)
            length = r.uniform(0.35, 0.7) * w
            turn = 0.0
            line: list[tuple[int, int]] = []
            for _step in range(int(length / 1.5)):
                turn = turn * 0.8 + r.gauss(0, 0.05)  # long gentle bends, not a snake's
                ang += turn
                x += math.cos(ang) * 1.5
                y += math.sin(ang) * 1.5
                ix, iy = int(x), int(y)
                if not (1 <= ix < w - 1 and 1 <= iy < h - 1) or ocean[ix, iy]:
                    break
                spine[ix, iy] = True
                line.append((ix, iy))
            if len(line) >= 6:
                self.spines.append(line)
        if not spine.any():
            return np.zeros((w, h), np.float32)
        dist = np.full((w, h), 10**6, dtype=np.int32)
        dist[spine] = 0
        tcod.path.dijkstra2d(dist, np.ones((w, h), dtype=np.int32), 2, 3, out=dist)
        # The range swells and narrows along its length, throws out spurs, and breaks into peaks and saddles.
        width = r.uniform(2.6, 3.8) * (0.6 + 0.8 * fbm(g, w, h, cell=w / 8, octaves=2))
        crests = ridged(g, w, h, cell=w / 16, octaves=4)
        spurs = ridged(g, w, h, cell=w / 9, octaves=3)
        d = (dist / 2.0) / width
        lift = np.exp(-d ** 1.6) * (0.45 + 0.55 * crests) + np.exp(-(d / 2.2) ** 2) * spurs * 0.35
        lift[ocean] = 0
        return lift.astype(np.float32)

    def _plateaus(self, g: np.random.Generator, ocean: np.ndarray, inland: np.ndarray) -> np.ndarray:
        """Now and then a tableland: high flat country with a scarp all round (0..1, 1 on the top)."""
        w, h = self.w, self.h
        r = self.rng.child("plateaus")
        out = np.zeros((w, h), np.float32)
        count = sum(1 for _ in range(1 + self.size_index) if r.chance(0.55))
        cells = np.argwhere(~ocean & (inland > 0.35))
        xs = np.arange(w)[:, None]
        ys = np.arange(h)[None, :]
        wobble = fbm(g, w, h, cell=w / 14, octaves=4)
        for _ in range(count if len(cells) else 0):
            cx, cy = (int(v) for v in cells[r.randint(0, len(cells) - 1)])
            rad = r.uniform(5, 9 + 3 * self.size_index)
            stretch = r.uniform(0.6, 1.0)
            ang = r.uniform(0, math.pi)
            ux, uy = math.cos(ang), math.sin(ang)
            along = ((xs - cx) * ux + (ys - cy) * uy) / rad
            across = (-(xs - cx) * uy + (ys - cy) * ux) / (rad * stretch)
            d = np.sqrt(along ** 2 + across ** 2) + (wobble - 0.5) * 1.6
            out = np.maximum(out, 1.0 / (1.0 + np.exp(-(1.0 - d) * 14.0)))
        out[ocean] = 0
        return out

    def _volcanoes(self, g: np.random.Generator, ocean: np.ndarray, dist: np.ndarray) -> np.ndarray:
        """Volcanoes: on the flanks of the great ranges, on islands out at sea, now and then alone on a plain."""
        w, h = self.w, self.h
        r = self.rng.child("volcanoes")
        spots: list[tuple[int, int]] = []
        for line in getattr(self, "spines", []):
            if r.chance(0.6):
                x, y = line[r.randint(len(line) // 3, len(line) - 1)]
                spots.append((x + r.randint(-3, 3), y + r.randint(-3, 3)))
        land = np.argwhere(~ocean & (dist > 4))
        extra = r.randint(0, 1 + self.size_index) + (2 if self.land == "islands" else 0)
        for _ in range(extra if len(land) else 0):
            x, y = (int(v) for v in land[r.randint(0, len(land) - 1)])
            spots.append((x, y))
        lift = np.zeros((w, h), np.float32)
        xs = np.arange(w)[:, None]
        ys = np.arange(h)[None, :]
        for x, y in spots:
            if not (3 <= x < w - 3 and 3 <= y < h - 3) or ocean[x, y]:
                continue
            if any(math.hypot(x - ox, y - oy) < 12 for ox, oy in self.volcanoes):
                continue
            rr = (xs - x) ** 2 + (ys - y) ** 2
            lift += 0.95 * np.exp(-rr / (2 * 1.7 ** 2)) - 0.18 * np.exp(-rr / (2 * 0.6 ** 2))
            self.volcanoes.append((x, y))
        lift[ocean] = 0
        return lift

    # ------------------------------------------------------------------ 2. climate (rain first, for rivers)
    def _climate_base(self) -> None:
        w, h = self.w, self.h
        g = self.rng.numpy("climate")
        dist = np.full((w, h), 10**6, dtype=np.int32)
        dist[self.ocean] = 0
        tcod.path.dijkstra2d(dist, np.ones((w, h), dtype=np.int32), 2, 3, out=dist)
        self.dist_sea = dist / 2.0
        near_sea = np.exp(-self.dist_sea / (w * 0.11))
        mountainness = np.clip((self.meters - 900) / 2200, 0, 1)
        shadow = np.zeros((w, h))
        cloud = np.ones(h)
        for x in range(w):
            col_ocean = self.ocean[x, :]
            cloud = np.where(col_ocean, np.minimum(1.0, cloud + 0.25), cloud * (1 - 0.005 - 0.35 * mountainness[x, :]))
            shadow[x, :] = cloud
        noise = fbm(g, w, h, cell=w / 5, octaves=4)
        # Belts of rain by latitude, as on our own world: wet westerlies in the middle, a dry belt where the great
        # deserts lie, the rains of the hot south, and a dry cold far north.
        lat = self._land_latitude()

        def belt(at: float, width: float) -> np.ndarray:
            return np.exp(-((lat - at) / width) ** 2)

        belts = 0.10 * belt(0.42, 0.14) - 0.40 * belt(0.82, 0.09) + 0.30 * belt(1.03, 0.06) - 0.16 * belt(0.0, 0.1)
        moisture = 0.45 * near_sea + 0.40 * shadow + 0.35 * noise - 0.12 + belts
        self.moisture = np.clip(moisture, 0, 1)

    def _land_latitude(self) -> np.ndarray:
        """0 at the northernmost land, 1 at the southernmost ((1, h), a little beyond 0..1 out at sea): the climate
        runs across the land wherever it lies on the map, so every world has its frozen north and burning south."""
        h = self.h
        rows = np.nonzero((~self.ocean).any(axis=0))[0]
        lo, hi = (float(np.quantile(rows, 0.02)), float(np.quantile(rows, 0.98))) if len(rows) else (0.0, h - 1.0)
        span = max(h * 0.25, hi - lo)
        return ((np.arange(h, dtype=np.float64) - lo) / span)[None, :]

    def _water(self) -> None:
        filled, flow, order = hydrology.priority_flood(self.e, self.ocean)
        land = ~self.ocean
        depth = filled - self.e
        lake_candidates = land & (depth > 0.003)
        labels, sizes = hydrology.label_components(lake_candidates)
        big = [i for i, s in enumerate(sizes) if s >= 3]
        lake = np.isin(labels, big) & lake_candidates
        rain = 0.2 + self.moisture
        acc = hydrology.flow_accumulation(rain, flow, order, self.ocean)
        river = np.zeros((self.w, self.h), dtype=np.uint8)
        river_land = land & ~lake
        if river_land.any():
            vals = acc[river_land]
            t1, t2, t3 = (float(np.quantile(vals, q)) for q in (0.962, 0.988, 0.9965))
            river[(acc >= t1) & river_land] = 1
            river[(acc >= t2) & river_land] = 2
            river[(acc >= t3) & river_land] = 3
        self.flow = flow
        self.acc = acc
        self.lake = lake
        self.river = river
        self.meters = np.where(lake, np.maximum(self.meters, 1), self.meters)
        wet = hydrology.dilate((river > 0) | lake, 2)
        self.moisture = np.clip(self.moisture + wet * 0.12, 0, 1)
        self.preview["river"] = river

    def _climate(self) -> None:
        w, h = self.w, self.h
        g = self.rng.numpy("temperature")
        noise = fbm(g, w, h, cell=w / 4, octaves=3)
        north, mid, south = CLIMATE_TEMPERATURE.get(self.climate, CLIMATE_TEMPERATURE["temperate"])
        u = np.clip(self._land_latitude(), -0.05, 1.05) * 2 - 1  # -1 the far north, 1 the far south
        curve = 0.45 * np.abs(u) + 0.55 * np.abs(u) ** 4  # gentle through the middle, steep at the ends
        sea_level = mid + np.where(u < 0, north - mid, south - mid) * curve
        temp = sea_level - 6.5 * np.clip(self.meters, 0, None) / 1000.0 + (noise - 0.5) * 4.0
        # The sea keeps coasts milder.
        coastal = np.exp(-self.dist_sea / 6.0)
        temp = temp * (1 - 0.15 * coastal) + (mid + 1) * 0.15 * coastal
        self.temperature = temp.astype(np.float32)
        self._relief()

    def _relief(self) -> None:
        """Cliffs, gorges and falls (world.relief): the scarps round the tablelands and the sea-cliffs of high coasts;
        rivers through dry high country cut gorges; where a river drops off a scarp or a range, it falls."""
        from realmwalker.world.model import CLIFF, FALLS, RAVINE

        m = self.meters
        land = ~self.ocean
        lowest = m.copy()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            lowest = np.minimum(lowest, np.roll(np.roll(m, dx, 0), dy, 1))
        drop = m - lowest
        # The rim of a tableland: on top, with lower ground beside it.
        low_side = self.plateau.copy()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            low_side = np.minimum(low_side, np.roll(np.roll(self.plateau, dx, 0), dy, 1))
        cliff = land & (self.plateau > 0.5) & (low_side < 0.5) & (drop > 150)
        cliff |= land & hydrology.dilate(self.ocean, 1) & (m > 220) & (drop > 200)  # sea-cliffs
        relief = np.zeros_like(self.relief)
        relief[cliff] = CLIFF
        # Gorges: rivers in dry uplands, cut down into the rock.
        gorge = (self.river > 0) & ~self.lake & (self.moisture < 0.42) & (m > 400) & (m < 2600) & \
            (self.temperature > 0)
        labels, sizes = hydrology.label_components(gorge, diagonal=True)
        long_ones = [i for i, n in enumerate(sizes) if n >= 4]
        gorge = np.isin(labels, long_ones) & gorge
        relief[gorge] |= RAVINE
        self.meters = np.where(gorge, m - np.clip(m * 0.18, 120, 450), m)
        # Falls: a river whose next square is far below it.
        rx, ry = np.nonzero((self.river > 0) & ~self.lake)
        for x, y in zip(rx.tolist(), ry.tolist()):
            dx, dy = DIRS[int(self.flow[x, y])]
            nx, ny = x + dx, y + dy
            if (dx or dy) and 0 <= nx < self.w and 0 <= ny < self.h and m[x, y] - m[nx, ny] > 260:
                relief[x, y] |= FALLS
        self.relief = relief

    # ------------------------------------------------------------------ 3. biomes
    def _biomes(self) -> None:
        B = self.B
        w, h = self.w, self.h
        g = self.rng.numpy("biomes")
        m, t, wet = self.meters, self.temperature, self.moisture
        self._dry_lakes()
        land = ~self.ocean & ~self.lake
        biome = np.full((w, h), B["plains"], dtype=np.uint8)
        forest_noise = fbm(g, w, h, cell=w / 10, octaves=3)
        forested = land & (wet + (forest_noise - 0.5) * 0.35 > 0.50)
        biome[forested & (t < 6.5)] = B["pine_forest"]
        biome[forested & (t >= 6.5)] = B["forest"]
        biome[forested & (t >= 20.5) & (wet > 0.56)] = B["jungle"]
        # Open dry country: steppe where it is cool, savanna where it is hot.
        grass_noise = fbm(g, w, h, cell=w / 11, octaves=3)
        open_dry = land & ~forested & (wet + (grass_noise - 0.5) * 0.2 < 0.26)
        biome[open_dry & (t > 0.0) & (t < 16.5)] = B["steppe"]
        biome[land & ~forested & (wet < 0.48) & (t >= 19.5)] = B["savanna"]
        biome[land & (m > 650)] = B["hills"]
        broken = fbm(g, w, h, cell=w / 13, octaves=3)
        biome[land & (m > 280) & (m <= 1400) & (wet < 0.28) & (t > 9) & (broken > 0.47)] = B["badlands"]
        biome[land & (t < -2.5) & (m <= 1400)] = B["tundra"]
        biome[land & (t > 13.5) & (wet < 0.3) & (m <= 1500)] = B["desert"]
        sand = fbm(g, w, h, cell=w / 9, octaves=3)
        biome[land & (t > 17.5) & (wet < 0.2) & (m <= 900) & (sand > 0.42)] = B["dunes"]
        biome[self.salt] = B["salt_flat"]
        near_water = hydrology.dilate((self.river > 0) | self.lake | self.ocean, 2)
        marsh_noise = fbm(g, w, h, cell=w / 14, octaves=3)
        biome[land & (m < 160) & (wet > 0.6) & near_water & (marsh_noise > 0.5) & (t > -1)] = B["marsh"]
        coast = land & hydrology.dilate(self.ocean, 1) & (m < 90) & (biome != B["marsh"]) & ~self.salt
        biome[coast] = B["coast"]
        biome[land & (m > 1400)] = B["mountains"]
        biome[land & (m > 2600)] = B["high_mountains"]
        # The ice: below about -10 degrees the snow never melts, and the glaciers creep down to the sea.
        biome[land & (t < -10.0) & (m <= 2600)] = B["glacier"]
        xs = np.arange(w)[:, None]
        ys = np.arange(h)[None, :]
        for vx, vy in self.volcanoes:  # the burnt land round each volcano
            r = 2.0 + 1.5 * float(self.rng.child(f"volcano/{vx},{vy}").random())
            near = land & ((xs - vx) ** 2 + (ys - vy) ** 2 <= r * r) & (m <= 2600)
            biome[near] = B["volcanic"]
        biome[self.lake] = B["lake"]
        biome[self.ocean] = B["ocean"]
        self.biome = biome
        self.river[~land] = 0
        self.preview["biome"] = biome

    def _dry_lakes(self) -> None:
        """Lakes in hot dry country have long since dried to salt pans (and a white crust round their shores)."""
        self.salt = np.zeros((self.w, self.h), dtype=bool)
        labels, sizes = hydrology.label_components(self.lake)
        ragged = fbm(self.rng.numpy("salt"), self.w, self.h, cell=4, octaves=3) > 0.45
        for i, n in enumerate(sizes):
            cells = labels == i
            if float(self.temperature[cells].mean()) > 15.0 and float(self.moisture[cells].mean()) < 0.38:
                self.lake[cells] = False
                shore = hydrology.dilate(cells, 1 if n < 8 else 2) & ragged
                inner = cells & (hydrology.dilate(~cells, 1) & ~ragged)  # the old shoreline bitten in, here and there
                pan = ((cells & ~inner) | shore) & ~self.ocean & (self.meters < 1200)
                self.salt |= pan
        self.river[self.salt] = 0

    # ------------------------------------------------------------------ 4. names
    def _areas(self) -> None:
        B = self.B
        areas: list[Area] = []
        area = np.full((self.w, self.h), -1, dtype=np.int16)
        groups = [
            ("forest", [B["forest"]], 12), ("pine_forest", [B["pine_forest"]], 12), ("hills", [B["hills"]], 10),
            ("mountains", [B["mountains"], B["high_mountains"]], 8), ("marsh", [B["marsh"]], 8),
            ("plains", [B["plains"]], 20), ("coast", [B["coast"]], 25), ("tundra", [B["tundra"]], 14),
            ("desert", [B["desert"]], 14), ("lake", [B["lake"]], 3), ("ocean", [B["ocean"]], 60),
            ("glacier", [B["glacier"]], 12), ("steppe", [B["steppe"]], 16), ("savanna", [B["savanna"]], 16),
            ("jungle", [B["jungle"]], 12), ("dunes", [B["dunes"]], 10), ("badlands", [B["badlands"]], 8),
            ("salt_flat", [B["salt_flat"]], 4), ("volcanic", [B["volcanic"]], 6), ("fey_forest", [B["fey_forest"]], 4),
        ]
        for kind, ids, min_size in groups:
            mask = np.isin(self.biome, ids)
            labels, sizes = hydrology.label_components(mask)
            for label, size in enumerate(sizes):
                if size < min_size:
                    continue
                cells = np.argwhere(labels == label)
                centre = cells.mean(axis=0)
                cx, cy = cells[np.argmin(((cells - centre) ** 2).sum(axis=1))]
                a = Area(len(areas), self.namer.region(kind, self._people_of(cells)), kind, int(size), int(cx), int(cy))
                areas.append(a)
                area[labels == label] = a.id
        # A wonder that is a whole country (the enchanted wood, a salt pan) gives that country its name.
        for wd in self.wonders:
            i = int(area[wd.x, wd.y])
            if i >= 0 and (wd.kind, areas[i].kind) in (("enchanted_forest", "fey_forest"), ("salt_pan", "salt_flat")):
                areas[i].name = wd.name
        river_area = self._name_rivers(areas)
        self.areas = areas
        self.area = area
        self.river_area = river_area

    def _name_rivers(self, areas: list[Area]) -> np.ndarray:
        river_area = np.full((self.w, self.h), -1, dtype=np.int16)
        ups: dict[tuple[int, int], list[tuple[int, int]]] = {}
        mouths = []
        rx, ry = np.nonzero(self.river)
        for x, y in zip(rx.tolist(), ry.tolist()):
            d = int(self.flow[x, y])
            dx, dy = DIRS[d]
            nx, ny = x + dx, y + dy
            if d and 0 <= nx < self.w and 0 <= ny < self.h and self.river[nx, ny]:
                ups.setdefault((nx, ny), []).append((x, y))
            else:
                mouths.append((x, y))
        mouths.sort(key=lambda p: -self.acc[p])
        for mouth in mouths:
            stem = [mouth]
            cur = mouth
            while cur in ups:
                cur = max(ups[cur], key=lambda p: self.acc[p])
                stem.append(cur)
            if len(stem) < 10:
                continue
            a = Area(len(areas), self.namer.region("river", self._people_of(np.array(stem))), "river", len(stem),
                     mouth[0], mouth[1])
            areas.append(a)
            for x, y in stem:
                river_area[x, y] = a.id
        return river_area

    # ------------------------------------------------------------------ 5. settlements
    def _habitability(self) -> np.ndarray:
        B = self.tables.biomes
        g = self.rng.numpy("habitability")
        weights = np.array([B.lookup(HABITABILITY, bid, 0.3) for bid in B.ids])
        score = weights[self.biome]
        near_river = hydrology.dilate(self.river > 0, 1)
        score = score + near_river * 0.7 + (self.river >= 2) * 0.3
        near_coast = hydrology.dilate(self.ocean, 1) & ~self.ocean
        near_lake = hydrology.dilate(self.lake, 1) & ~self.lake
        score = score + near_coast * 0.35 + near_lake * 0.4
        comfort = np.exp(-(((self.temperature - 10.0) / 12.0) ** 2))
        score = score * (0.4 + 0.6 * comfort) + g.random((self.w, self.h)) * 0.25
        score[self.ocean | self.lake] = -1
        from realmwalker.world import wonders

        score[wonders.avoid(self)] = -1  # nobody builds on the wonders of the world
        # Keep settlements off the outermost tiles.
        score[:2, :] = score[-2:, :] = -1
        score[:, :2] = score[:, -2:] = -1
        return score

    def _people_shares(self, score: np.ndarray, cells: np.ndarray) -> list[tuple[int, float]]:
        """Each people's share of the towns: half for how much land it holds, half for how good that land is."""
        if not len(cells):
            return []
        owner = self.culture[cells[:, 0], cells[:, 1]]
        good = np.clip(score[cells[:, 0], cells[:, 1]], 0, None)
        out = []
        for ci in range(len(self.culture_ids)):
            mine = owner == ci
            if not mine.any():
                continue
            land = mine.sum() / len(cells)
            fertile = good[mine].sum() / max(1e-6, good.sum())
            out.append((ci, float(0.5 * land + 0.5 * fertile) * 0.85))  # (and some left over for the best spots)
        return out

    def _culture_for(self, x: int, y: int, kind: str, rng: RNG) -> str:
        """The people of the ground a place stands on (and now and then, in green farming country, halflings)."""
        i = int(self.culture[x, y])
        culture = self.culture_ids[i] if i < len(self.culture_ids) else "heartland"
        if kind in ("village", "hamlet") and culture in ("heartland", "highland") and \
                self.tables.biomes.family(self.biome_id(x, y)) in ("plains", "hills") and rng.chance(0.2):
            return "halfling"
        return culture

    # ------------------------------------------------------------------ 4. peoples
    def _cultures(self) -> None:
        """Where each people lives: every human people that finds a home in this world's climate has a hearth at its
        best ground, and spreads from there over the land, mountains and seas slowing it, until it meets another."""
        C = self.tables.cultures
        B = self.tables.biomes
        rng = self.rng.child("cultures")
        g = rng.numpy("cultures")
        land = ~self.ocean & ~self.lake
        T, M = self.temperature, self.moisture
        coastal = np.exp(-self.dist_sea / 5.0)
        suits: dict[str, np.ndarray] = {}
        for cid in C.human:
            home = C.home(cid)
            weights = np.array([float(B.lookup(home["biomes"], b, 0.0)) for b in B.ids], np.float32)
            lo, hi = home["temperature"]
            tfit = np.exp(-((np.maximum(0, lo - T) + np.maximum(0, T - hi)) / 5.0) ** 2)
            lo, hi = home["moisture"]
            mfit = np.exp(-((np.maximum(0, lo - M) + np.maximum(0, M - hi)) / 0.15) ** 2)
            c = float(home["coast"])
            cfit = 1 + c * coastal if c >= 0 else 1 + (-c) * (1 - coastal)
            fit = weights[self.biome] * tfit * mfit * cfit
            fit[~land] = 0
            suits[cid] = _box_blur(fit, 3)
        want = rng.randint(*((4, 5), (6, 7), (8, 9))[self.size_index])
        order = sorted(C.human, key=lambda c: -float(suits[c].max()) * rng.uniform(0.75, 1.25))
        apart = math.hypot(self.w, self.h) * 0.17
        xs = np.arange(self.w)[:, None]
        ys = np.arange(self.h)[None, :]
        hearths: list[tuple[int, int, str]] = []
        for cid in order:
            if len(hearths) >= want:
                break
            cand = suits[cid] * (0.85 + 0.3 * g.random((self.w, self.h)))
            for hx, hy, _ in hearths:
                cand[(xs - hx) ** 2 + (ys - hy) ** 2 < apart ** 2] = 0
            x, y = divmod(int(np.argmax(cand)), self.h)
            if cand[x, y] < 0.04:
                continue
            hearths.append((x, y, cid))
        if not hearths:  # a world too strange for any people: the heartlanders make do
            x, y = (int(v) for v in np.argwhere(land)[0]) if land.any() else (self.w // 2, self.h // 2)
            hearths.append((x, y, "heartland"))
        base = np.array([B.lookup(CULTURE_COST, b, 14) for b in B.ids], np.float32)[self.biome]
        reach = []
        for x, y, cid in hearths:
            s = suits[cid] / max(float(suits[cid].max()), 1e-6)
            cost = base * np.clip(1.6 - s, 0.45, 1.6)
            cost[self.ocean] = 22 if float(C.home(cid)["coast"]) > 0.4 else 60  # sea peoples sail to the islands
            cost[self.lake] = 20
            cost = np.maximum(1, cost).astype(np.int32)
            dist = np.full((self.w, self.h), 10**8, dtype=np.int32)
            dist[x, y] = 0
            tcod.path.dijkstra2d(dist, cost, 2, 3, out=dist)
            reach.append(dist.astype(np.float32))
        D = np.stack(reach)
        weight = np.array([rng.uniform(0.85, 1.2) for _ in hearths], np.float32)
        n = len(hearths)
        for _ in range(5):  # a people that takes far more than its share spreads less far (and the reverse)
            owner = np.argmin(D * weight[:, None, None], axis=0)
            shares = np.bincount(owner[land], minlength=n) / max(1, int(land.sum()))
            weight *= np.clip((shares * n) ** 0.4, 0.7, 1.45).astype(np.float32)
        owner = np.argmin(D * weight[:, None, None], axis=0)
        self.culture_ids = [cid for _, _, cid in hearths]
        culture = np.where(owner >= 0, owner, NO_CULTURE).astype(np.uint8)
        culture[~land] = NO_CULTURE
        self.culture = culture
        self.hearths = hearths

    def _people_of(self, cells: np.ndarray) -> str | None:
        """The people most of these cells belong to (for water, the people of the nearest shore; None if nobody's)."""
        if not len(cells):
            return None
        vals = self.culture[cells[:, 0], cells[:, 1]]
        vals = vals[vals != NO_CULTURE]
        if not len(vals):
            cx, cy = (int(v) for v in cells[len(cells) // 2])
            r = 6
            near = self.culture[max(0, cx - r):cx + r + 1, max(0, cy - r):cy + r + 1]
            vals = near[near != NO_CULTURE]
            if not len(vals):
                return None
        i = int(np.bincount(vals).argmax())
        return self.culture_ids[i] if i < len(self.culture_ids) else None

    def _elder_lands(self) -> None:
        """The dwarves' mountains around their holds, the elves' woods round their halls, the halflings' fields."""
        places = [(s.culture, s.x, s.y) for s in self.settlements] + [(d["prior"], d["x"], d["y"]) for d in self.doomed]
        for culture, px, py in places:
            if culture not in ("dwarven", "elven", "halfling"):
                continue
            if culture not in self.culture_ids:
                self.culture_ids.append(culture)
            ci = self.culture_ids.index(culture)
            r = {"dwarven": 7, "elven": 7, "halfling": 2}[culture]
            x0, x1 = max(0, px - r), min(self.w, px + r + 1)
            y0, y1 = max(0, py - r), min(self.h, py + r + 1)
            xs = np.arange(x0, x1)[:, None]
            ys = np.arange(y0, y1)[None, :]
            ground = ((xs - px) ** 2 + (ys - py) ** 2 <= r * r) & (self.culture[x0:x1, y0:y1] != NO_CULTURE)
            B = self.tables.biomes
            if culture == "dwarven":
                ground &= np.isin(self.biome[x0:x1, y0:y1], B.of_family("mountains", "high_mountains", "hills"))
            elif culture == "elven":
                ground &= np.isin(self.biome[x0:x1, y0:y1], B.of_family("forest", "pine_forest"))
            self.culture[x0:x1, y0:y1][ground] = ci

    def biome_id(self, x: int, y: int) -> str:
        return self.tables.biomes.ids[int(self.biome[x, y])]

    def _settlements(self) -> None:
        rng = self.rng.child("settlements")
        score = self._habitability()
        base_score = score.copy()
        types = self.tables.sites["settlement_types"]
        placed: list[Settlement] = []
        taken: list[tuple[int, int, int]] = []  # x, y, spacing

        def far_enough(x: int, y: int, spacing: int) -> bool:
            for ox, oy, osp in taken:
                if math.hypot(x - ox, y - oy) < min(spacing, osp) or (x == ox and y == oy):
                    return False
            return True

        def place(kind: str, count: int, spacing: int, candidates: np.ndarray, culture: str | None = None,
                  doomed: bool = False) -> int:
            if count <= 0 or not len(candidates):
                return 0
            order = candidates[np.argsort(-score[candidates[:, 0], candidates[:, 1]])]
            added = 0
            for x, y in order.tolist():
                if added >= count:
                    break
                if score[x, y] < 0 or not far_enough(x, y, spacing):
                    continue
                spec = types[kind]
                cul = culture or self._culture_for(x, y, kind, rng)
                taken.append((x, y, spacing))
                added += 1
                if doomed:
                    # A place that will stand for a while in the ages, and be a ruin today.
                    self.doomed.append({"kind": kind, "x": x, "y": y, "prior": cul, "area": int(self.area[x, y])})
                    continue
                lo, hi = spec["population"]
                s = Settlement(
                    id=len(placed), name=self.namer.settlement(cul), kind=kind, x=x, y=y, culture=cul,
                    population=rng.randint(lo, hi), walled=rng.chance(spec.get("wall_chance", 0.0)),
                    area=int(self.area[x, y]),
                )
                placed.append(s)
            return added

        land_cells = np.argwhere(score >= 0)
        # Every people has its towns: a share of each kind for its lands (how much land, and how good), the rest
        # wherever is best. (The best land alone would leave the peoples of desert, steppe and tundra almost none.)
        shares = self._people_shares(score, land_cells)
        owner = self.culture[land_cells[:, 0], land_cells[:, 1]]
        for kind in ("city", "town", "village", "hamlet"):
            counts, spacing = SETTLEMENT_COUNTS[kind]
            total = counts[self.size_index]
            done = 0
            for ci, share in shares:
                done += place(kind, int(total * share), spacing, land_cells[owner == ci])
            place(kind, total - done, spacing, land_cells)
        B = self.B
        F = self.tables.biomes
        mountain = np.isin(self.biome, [B["mountains"]])
        approachable = hydrology.dilate(np.isin(self.biome, F.of_family("hills", "plains", "pine_forest", "forest")), 1)
        hold_cells = np.argwhere(mountain & approachable & (score > -1))
        hold_score = None
        if len(hold_cells):
            score_backup = score.copy()
            score[mountain] = 1.0 + rng.numpy("holds").random(int(mountain.sum()))
            place("hold", SPECIAL_COUNTS["hold"][self.size_index], 20, hold_cells, "dwarven")
            hold_score = score
            score = score_backup
        forest = np.isin(self.biome, [B["forest"], B["fey_forest"]])
        deep_forest = forest & ~hydrology.dilate(~forest, 2)
        elf_cells = np.argwhere(deep_forest)
        if len(elf_cells):
            score[deep_forest] = 1.0 + rng.numpy("elves").random(int(deep_forest.sum()))
            place("elfhall", SPECIAL_COUNTS["elfhall"][self.size_index], 18, elf_cells, "elven")
        self.settlements = placed
        # The doomed: more good places, spaced like the rest, that the ages will use up.
        elf_score = score
        score = base_score
        doomed = self.tables.history["spots"]["doomed"]
        for kind in ("city", "town", "village", "hamlet"):
            _counts, spacing = SETTLEMENT_COUNTS[kind]
            place(kind, int(doomed[kind][self.size_index]), spacing, land_cells, doomed=True)
        if len(hold_cells) and hold_score is not None:
            score_backup = score
            score = hold_score
            place("hold", int(doomed["hold"][self.size_index]), 20, hold_cells, "dwarven", doomed=True)
            score = score_backup
        if len(elf_cells):
            score = elf_score
            place("elfhall", int(doomed["elfhall"][self.size_index]), 18, elf_cells, "elven", doomed=True)
        self._elder_lands()

    # ------------------------------------------------------------------ 6. roads
    def _roads(self) -> None:
        B = self.tables.biomes
        cost_by_biome = np.array([B.lookup(ROAD_COST, bid, 20) for bid in B.ids], dtype=np.int32)
        cost = cost_by_biome[self.biome]
        cost = cost + (self.river == 1) * 20 + (self.river == 2) * 35 + (self.river == 3) * 60
        cost[self.ocean | self.lake] = 0
        road = np.zeros((self.w, self.h), dtype=bool)
        main = [s for s in self.settlements if s.kind != "hamlet"]
        edges: set[tuple[int, int]] = set()
        if len(main) > 1:
            # Minimum spanning tree (Prim) by straight-line distance.
            in_tree = {0}
            while len(in_tree) < len(main):
                best = None
                for i in in_tree:
                    for j in range(len(main)):
                        if j in in_tree:
                            continue
                        d = math.hypot(main[i].x - main[j].x, main[i].y - main[j].y)
                        if best is None or d < best[0]:
                            best = (d, i, j)
                assert best is not None
                in_tree.add(best[2])
                edges.add((min(best[1], best[2]), max(best[1], best[2])))
            # A few extra links between larger places, so the network has loops.
            rng = self.rng.child("roads")
            for i, s in enumerate(main):
                if s.kind not in ("town", "city"):
                    continue
                others = sorted(range(len(main)), key=lambda j: math.hypot(main[j].x - s.x, main[j].y - s.y))
                for j in others[1:3]:
                    if math.hypot(main[j].x - s.x, main[j].y - s.y) < 40 and rng.chance(0.6):
                        edges.add((min(i, j), max(i, j)))
        pairs = [(main[i], main[j]) for i, j in edges]
        for s in self.settlements:
            if s.kind != "hamlet" or not main:
                continue
            nearest = min(main, key=lambda m: math.hypot(m.x - s.x, m.y - s.y))
            if math.hypot(nearest.x - s.x, nearest.y - s.y) <= 14:
                pairs.append((s, nearest))
        pairs.sort(key=lambda p: math.hypot(p[0].x - p[1].x, p[0].y - p[1].y))
        for a, b in pairs:
            path = tcod.path.path2d(cost, start_points=[(a.x, a.y)], end_points=[(b.x, b.y)], cardinal=10, diagonal=None)
            if len(path) == 0:
                continue
            for x, y in path.tolist():
                road[x, y] = True
            path_x, path_y = path[:, 0], path[:, 1]
            cost[path_x, path_y] = np.minimum(cost[path_x, path_y], 4)
        for s in self.settlements:
            road[s.x, s.y] = True
        self.road = road
        self.preview["road"] = road

    # ------------------------------------------------------------------ 7. danger and sites
    def _danger(self) -> None:
        w, h = self.w, self.h
        dist = np.full((w, h), 10**6, dtype=np.int32)
        for s in self.settlements:
            if s.kind in ("town", "city", "hold", "elfhall"):
                dist[s.x, s.y] = 0
            elif s.kind == "village":
                dist[s.x, s.y] = min(dist[s.x, s.y], 8)
        walk = np.where(self.ocean | self.lake, 0, 1).astype(np.int32)
        tcod.path.dijkstra2d(dist, walk, 2, 3, out=dist)
        dist = np.where(dist >= 10**6, 60, dist / 2.0)
        B = self.tables.biomes
        wild = np.array([B.lookup(WILDNESS, bid, 1) for bid in B.ids])[self.biome]
        danger = np.clip(dist / 7.0, 0, 7) + wild + (self.opt.danger - 2) - self.road * 1.0
        danger = np.clip(np.round(danger), 0, 10).astype(np.uint8)
        danger[self.ocean | self.lake] = 0
        self.danger = danger

    def _sites(self) -> None:
        rng = self.rng.child("sites")
        B = self.B
        types = self.tables.sites["site_types"]
        land = ~self.ocean & ~self.lake
        settled = np.zeros((self.w, self.h), dtype=bool)
        for s in self.settlements:
            settled[s.x, s.y] = True
        for d in self.doomed:
            settled[d["x"], d["y"]] = True  # a town of the ages will stand there (and its ruin after)
        near_settled = hydrology.dilate(settled, 4)
        from realmwalker.world import wonders

        near_settled |= hydrology.dilate(wonders.avoid(self), 2)
        F = self.tables.biomes
        allowed = {
            "ruin": land & ~np.isin(self.biome, [B["high_mountains"], B["glacier"], B["salt_flat"]]),
            "cave": np.isin(self.biome, F.of_family("hills", "mountains", "pine_forest")),
            "barrow": np.isin(self.biome, F.of_family("hills", "plains", "tundra")) & (self.biome != B["glacier"]),
            "tower": land & ~np.isin(self.biome, [B["high_mountains"], B["marsh"], B["glacier"], B["salt_flat"]]),
        }
        sites: list[Site] = []
        taken = np.zeros((self.w, self.h), dtype=bool)
        danger_factor = 0.75 + 0.25 * self.opt.danger
        for kind in ("ruin", "cave", "barrow", "tower"):
            if kind not in types:
                continue
            count = int(round(SITE_COUNTS[kind][self.size_index] * danger_factor))
            if kind == "ruin":
                # Most ruins are the towns the ages destroy; a few were ruins before the records began.
                count = max(2, count - len(self.doomed))
            cells = np.argwhere(allowed[kind] & ~near_settled & ~self.road & ~taken)
            if not len(cells):
                continue
            idx = list(range(len(cells)))
            rng.shuffle(idx)
            added = 0
            for i in idx:
                if added >= count:
                    break
                x, y = (int(v) for v in cells[i])
                if taken[max(0, x - 5):x + 6, max(0, y - 5):y + 6].any():
                    continue
                ci = int(self.culture[x, y])
                people = self.culture_ids[ci] if ci < len(self.culture_ids) else None
                sites.append(Site(len(sites), kind, x, y, self.namer.site(kind, people), int(self.danger[x, y])))
                taken[x, y] = True
                added += 1
        self.sites = sites

    # ------------------------------------------------------------------ result
    def _assemble(self) -> World:
        meta = WorldMeta(
            id=f"{_slug(self.opt.name)}-{uuid.uuid4().hex[:6]}",
            name=self.opt.name,
            seed=self.opt.seed,
            size=self.opt.size,
            danger=self.opt.danger,
            magic=self.opt.magic,
            created=datetime.date.today().isoformat(),
            generator_version=GENERATOR_VERSION,
            land=self.land,
            climate=self.climate,
        )
        cal = self.tables.calendar
        start = cal.minutes_for(cal.start_year, 1, 1 + self.rng.randint(0, 9), 8, 0)
        return World(
            meta=meta,
            width=self.w,
            height=self.h,
            biome_ids=list(self.tables.biomes.ids),
            elevation=np.round(self.meters).astype(np.int16),
            temperature=self.temperature.astype(np.float32),
            moisture=self.moisture.astype(np.float32),
            biome=self.biome.astype(np.uint8),
            river=self.river.astype(np.uint8),
            flow=self.flow.astype(np.uint8),
            road=self.road.astype(bool),
            area=self.area.astype(np.int16),
            river_area=self.river_area.astype(np.int16),
            danger=self.danger.astype(np.uint8),
            culture=self.culture.astype(np.uint8),
            culture_ids=list(self.culture_ids),
            relief=self.relief.astype(np.uint8),
            settlements=self.settlements,
            sites=self.sites,
            areas=self.areas,
            wonders=self.wonders,
            time=start,
        )


def _box_blur(a: np.ndarray, r: int) -> np.ndarray:
    """The mean over a (2r+1)-square around each cell (edges repeat): how good the neighbourhood is."""
    pad = np.pad(a.astype(np.float64), r, mode="edge")
    c = np.pad(pad.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    n = 2 * r + 1
    total = c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]
    return (total / (n * n)).astype(np.float32)


def _slug(name: str) -> str:
    s = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    while "--" in s:
        s = s.replace("--", "-")
    return s[:24] or "world"


def generate_world(options: WorldOptions, tables: Tables) -> World:
    return WorldGenerator(options, tables).generate()
