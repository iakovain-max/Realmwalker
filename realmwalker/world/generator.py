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
from realmwalker.world.model import DIRS, WORLD_SIZES, Area, Settlement, Site, World, WorldMeta
from realmwalker.world.naming import Namer
from realmwalker.world.noise import fbm, normalise, ridged
from realmwalker.world.tables import Tables

log = logging.getLogger("realmwalker.worldgen")

GENERATOR_VERSION = 1
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
}
HABITABILITY = {
    "plains": 1.0, "coast": 0.9, "forest": 0.55, "pine_forest": 0.4, "hills": 0.6, "mountains": 0.05,
    "high_mountains": 0.0, "marsh": 0.2, "tundra": 0.15, "desert": 0.15, "ocean": 0.0, "lake": 0.0,
}
WILDNESS = {
    "plains": 0, "coast": 0, "forest": 1, "pine_forest": 1, "hills": 1, "mountains": 2, "high_mountains": 3,
    "marsh": 2, "tundra": 1, "desert": 1, "ocean": 0, "lake": 0,
}


@dataclass
class WorldOptions:
    name: str
    seed: int
    size: str = "medium"
    danger: int = 2  # 1 low, 2 normal, 3 high, 4 brutal
    magic: int = 2  # 1 scarce, 2 rare, 3 uncommon
    history: int = 0  # years of history to live (0: the usual, data/politics.json "history_years")


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
        self._progress(4)
        self.namer = Namer(self.tables.place_names, self.rng.child("names"))
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
        from realmwalker.world.ages import AgeSim

        self.sim = AgeSim(world, self.tables, self.rng.child("ages"), years=self.history_years, spots=self.doomed,
                          namer=self.namer, progress=self._ages_progress)
        self.sim.run()
        self.sim = None
        self._progress(9)
        log.info("Generated world '%s' (seed %d, %s) in %.1f s: %d settlements, %d sites, %d named areas, "
                 "%d years of history (%d figures, %d events)", world.meta.name, world.meta.seed, world.meta.size,
                 time.monotonic() - started, len(world.settlements), len(world.sites), len(world.areas),
                 self.history_years, len(world.figures), len(world.history))
        return world

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
        base = fbm(g, w, h, cell=w / 2.2, octaves=6, persistence=0.52)
        detail = fbm(g, w, h, cell=w / 9, octaves=4)
        xs = np.linspace(-1, 1, w)[:, None]
        ys = np.linspace(-1, 1, h)[None, :]
        edge_noise = fbm(g, w, h, cell=w / 6, octaves=3)
        d = np.sqrt((xs * 1.02) ** 2 + (ys * 1.05) ** 2) + (edge_noise - 0.5) * 0.45
        falloff = np.clip(d, 0, 2) ** 2.4
        shape = normalise(base * 0.65 + detail * 0.35 - falloff * 0.9)

        sea = float(np.quantile(shape, SEA_FRACTION))
        below = shape < sea
        labels, _sizes = hydrology.label_components(below)
        border = set(labels[0, :].tolist()) | set(labels[-1, :].tolist()) | set(labels[:, 0].tolist()) | set(labels[:, -1].tolist())
        border.discard(-1)
        ocean = np.isin(labels, list(border)) if border else below
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
        land_h = 0.30 * inland + 0.30 * rolling ** 1.5 + 0.95 * ranges * range_mask * np.clip(inland * 2.5, 0, 1)
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
        # Heights by percentile, so every world gets a sensible mix of lowland, hills and peaks.
        levels = np.quantile(land_h[~ocean], [0.0, 0.55, 0.75, 0.885, 0.97, 1.0])
        levels = np.maximum.accumulate(levels + np.arange(len(levels)) * 1e-9)
        land_m = np.interp(land_h, levels, [0.0, 280.0, 650.0, 1400.0, 2600.0, 4200.0])
        meters = np.where(ocean, -np.clip((sea - shape) / max(sea, 1e-6), 0, 1) * 900 - 5, land_m)
        self.e = e
        self.sea = sea
        self.ocean = ocean
        self.meters = meters
        self.preview["elevation"] = meters

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
        moisture = 0.45 * near_sea + 0.40 * shadow + 0.35 * noise - 0.12
        self.moisture = np.clip(moisture, 0, 1)

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
        lat = np.linspace(0, 1, h)[None, :]
        noise = fbm(g, w, h, cell=w / 4, octaves=3)
        temp = -6.0 + 31.0 * lat - 6.5 * np.clip(self.meters, 0, None) / 1000.0 + (noise - 0.5) * 4.0
        # The sea keeps coasts milder.
        coastal = np.exp(-self.dist_sea / 6.0)
        temp = temp * (1 - 0.15 * coastal) + 8 * 0.15 * coastal
        self.temperature = temp.astype(np.float32)

    # ------------------------------------------------------------------ 3. biomes
    def _biomes(self) -> None:
        B = self.B
        w, h = self.w, self.h
        g = self.rng.numpy("biomes")
        m, t, wet = self.meters, self.temperature, self.moisture
        land = ~self.ocean & ~self.lake
        biome = np.full((w, h), B["plains"], dtype=np.uint8)
        forest_noise = fbm(g, w, h, cell=w / 10, octaves=3)
        forested = land & (wet + (forest_noise - 0.5) * 0.35 > 0.50)
        biome[forested & (t < 6.5)] = B["pine_forest"]
        biome[forested & (t >= 6.5)] = B["forest"]
        biome[land & (m > 650)] = B["hills"]
        biome[land & (t < -2.5) & (m <= 1400)] = B["tundra"]
        biome[land & (t > 13.5) & (wet < 0.3) & (m <= 1500)] = B["desert"]
        near_water = hydrology.dilate((self.river > 0) | self.lake | self.ocean, 2)
        marsh_noise = fbm(g, w, h, cell=w / 14, octaves=3)
        biome[land & (m < 160) & (wet > 0.6) & near_water & (marsh_noise > 0.5) & (t > -1)] = B["marsh"]
        coast = land & hydrology.dilate(self.ocean, 1) & (m < 90) & (biome != B["marsh"])
        biome[coast] = B["coast"]
        biome[land & (m > 1400)] = B["mountains"]
        biome[land & (m > 2600)] = B["high_mountains"]
        biome[self.lake] = B["lake"]
        biome[self.ocean] = B["ocean"]
        self.biome = biome
        self.river[~land] = 0
        self.preview["biome"] = biome

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
                a = Area(len(areas), self.namer.region(kind), kind, int(size), int(cx), int(cy))
                areas.append(a)
                area[labels == label] = a.id
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
            a = Area(len(areas), self.namer.region("river"), "river", len(stem), mouth[0], mouth[1])
            areas.append(a)
            for x, y in stem:
                river_area[x, y] = a.id
        return river_area

    # ------------------------------------------------------------------ 5. settlements
    def _habitability(self) -> np.ndarray:
        B = self.tables.biomes
        g = self.rng.numpy("habitability")
        weights = np.array([HABITABILITY.get(bid, 0.3) for bid in B.ids])
        score = weights[self.biome]
        near_river = hydrology.dilate(self.river > 0, 1)
        score = score + near_river * 0.7 + (self.river >= 2) * 0.3
        near_coast = hydrology.dilate(self.ocean, 1) & ~self.ocean
        near_lake = hydrology.dilate(self.lake, 1) & ~self.lake
        score = score + near_coast * 0.35 + near_lake * 0.4
        comfort = np.exp(-(((self.temperature - 10.0) / 12.0) ** 2))
        score = score * (0.4 + 0.6 * comfort) + g.random((self.w, self.h)) * 0.25
        score[self.ocean | self.lake] = -1
        # Keep settlements off the outermost tiles.
        score[:2, :] = score[-2:, :] = -1
        score[:, :2] = score[:, -2:] = -1
        return score

    def _culture_for(self, x: int, y: int, kind: str, rng: RNG) -> str:
        lat = y / max(1, self.h - 1)
        if lat < 0.34:
            return "northmarch"
        if lat > 0.6 and self.dist_sea[x, y] < 14:
            return "southron"
        if kind in ("village", "hamlet") and self.biome_id(x, y) in ("plains", "hills") and rng.chance(0.2):
            return "halfling"
        return "heartland"

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
                  doomed: bool = False) -> None:
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

        land_cells = np.argwhere(score >= 0)
        for kind in ("city", "town", "village", "hamlet"):
            counts, spacing = SETTLEMENT_COUNTS[kind]
            place(kind, counts[self.size_index], spacing, land_cells)
        B = self.B
        mountain = np.isin(self.biome, [B["mountains"]])
        approachable = hydrology.dilate(np.isin(self.biome, [B["hills"], B["plains"], B["pine_forest"], B["forest"]]), 1)
        hold_cells = np.argwhere(mountain & approachable & (score > -1))
        hold_score = None
        if len(hold_cells):
            score_backup = score.copy()
            score[mountain] = 1.0 + rng.numpy("holds").random(int(mountain.sum()))
            place("hold", SPECIAL_COUNTS["hold"][self.size_index], 20, hold_cells, "dwarven")
            hold_score = score
            score = score_backup
        forest = self.biome == B["forest"]
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

    # ------------------------------------------------------------------ 6. roads
    def _roads(self) -> None:
        B = self.tables.biomes
        cost_by_biome = np.array([ROAD_COST.get(bid, 20) for bid in B.ids], dtype=np.int32)
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
        wild = np.array([WILDNESS.get(bid, 1) for bid in self.tables.biomes.ids])[self.biome]
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
        allowed = {
            "ruin": land & ~np.isin(self.biome, [B["high_mountains"]]),
            "cave": np.isin(self.biome, [B["hills"], B["mountains"], B["pine_forest"]]),
            "barrow": np.isin(self.biome, [B["hills"], B["plains"], B["tundra"]]),
            "tower": land & ~np.isin(self.biome, [B["high_mountains"], B["marsh"]]),
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
                sites.append(Site(len(sites), kind, x, y, self.namer.site(kind), int(self.danger[x, y])))
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
            settlements=self.settlements,
            sites=self.sites,
            areas=self.areas,
            time=start,
        )


def _slug(name: str) -> str:
    s = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    while "--" in s:
        s = s.replace("--", "-")
    return s[:24] or "world"


def generate_world(options: WorldOptions, tables: Tables) -> World:
    return WorldGenerator(options, tables).generate()
