"""The World: overworld arrays plus settlements, sites, named areas, local maps and the clock.

Arrays are numpy, indexed [x, y]. The world outlives any one character: when a character dies,
the world (with its history, flavour text and local maps) remains for the next.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from realmwalker.ai.store import FlavorStore
from realmwalker.core.rng import RNG

# Neighbour offsets. Index 0 means "no direction" (e.g. river mouth or sink).
DIRS: list[tuple[int, int]] = [(0, 0), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]
DIR_NAMES = ["here", "north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]

WORLD_SIZES = {"small": (128, 80), "medium": (192, 120), "large": (256, 160)}

ARRAY_NAMES = ("elevation", "temperature", "moisture", "biome", "river", "flow", "road", "area", "river_area", "danger")


@dataclass
class WorldMeta:
    id: str
    name: str
    seed: int
    size: str = "medium"
    danger: int = 2  # 1 low .. 4 brutal
    magic: int = 2  # 1 scarce .. 3 uncommon
    created: str = ""
    generator_version: int = 1


@dataclass
class Settlement:
    id: int
    name: str
    kind: str  # hamlet, village, town, city, hold, elfhall
    x: int
    y: int
    culture: str
    population: int
    walled: bool = False
    area: int = -1


@dataclass
class Site:
    id: int
    kind: str  # ruin, cave, barrow, tower
    x: int
    y: int
    name: str
    danger: int = 1


@dataclass
class Area:
    """A named region of land or water: a forest, a range of hills, a lake, a river."""

    id: int
    name: str
    kind: str  # a biome id, or "river"
    size: int
    x: int
    y: int


@dataclass
class World:
    meta: WorldMeta
    width: int
    height: int
    biome_ids: list[str]
    elevation: np.ndarray  # int16 metres above sea level (negative = under water)
    temperature: np.ndarray  # float32 yearly mean, degrees C
    moisture: np.ndarray  # float32 0..1
    biome: np.ndarray  # uint8 index into biome_ids
    river: np.ndarray  # uint8 0 = none, 1 stream, 2 river, 3 great river
    flow: np.ndarray  # uint8 direction index (DIRS) water flows to
    road: np.ndarray  # bool
    area: np.ndarray  # int16 named land/water area id or -1
    river_area: np.ndarray  # int16 named river id (an Area of kind "river") or -1
    danger: np.ndarray  # uint8 0..10 how dangerous the wilds are here
    settlements: list[Settlement] = field(default_factory=list)
    sites: list[Site] = field(default_factory=list)
    areas: list[Area] = field(default_factory=list)
    time: int = 0  # minutes since the epoch
    local_maps: dict = field(default_factory=dict)  # key "x,y" -> LocalMap
    flavor: FlavorStore = field(default_factory=FlavorStore)
    rng: RNG | None = None

    def __post_init__(self) -> None:
        if self.rng is None:
            self.rng = RNG(self.meta.seed, "sim")
        self.rebuild_index()

    # ------------------------------------------------------------------ lookups
    def rebuild_index(self) -> None:
        self.settlement_grid = np.full((self.width, self.height), -1, dtype=np.int32)
        for i, s in enumerate(self.settlements):
            self.settlement_grid[s.x, s.y] = i
        self.site_grid = np.full((self.width, self.height), -1, dtype=np.int32)
        for i, s in enumerate(self.sites):
            self.site_grid[s.x, s.y] = i

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def biome_id(self, x: int, y: int) -> str:
        return self.biome_ids[int(self.biome[x, y])]

    def settlement_at(self, x: int, y: int) -> Settlement | None:
        i = int(self.settlement_grid[x, y])
        return self.settlements[i] if i >= 0 else None

    def site_at(self, x: int, y: int) -> Site | None:
        i = int(self.site_grid[x, y])
        return self.sites[i] if i >= 0 else None

    def area_at(self, x: int, y: int) -> Area | None:
        i = int(self.area[x, y])
        return self.areas[i] if 0 <= i < len(self.areas) else None

    def river_at(self, x: int, y: int) -> Area | None:
        i = int(self.river_area[x, y])
        return self.areas[i] if 0 <= i < len(self.areas) else None

    def latitude(self, y: int) -> float:
        """0 at the northern edge, 1 at the southern edge."""
        return y / max(1, self.height - 1)

    def downstream(self, x: int, y: int) -> tuple[int, int] | None:
        d = int(self.flow[x, y])
        if d == 0:
            return None
        dx, dy = DIRS[d]
        nx, ny = x + dx, y + dy
        return (nx, ny) if self.in_bounds(nx, ny) else None

    def neighbours(self, x: int, y: int):
        for d in range(1, 9):
            dx, dy = DIRS[d]
            nx, ny = x + dx, y + dy
            if self.in_bounds(nx, ny):
                yield d, nx, ny

    def arrays(self) -> dict[str, np.ndarray]:
        return {name: getattr(self, name) for name in ARRAY_NAMES}

    def objects_dict(self) -> dict:
        return {
            "settlements": [asdict(s) for s in self.settlements],
            "sites": [asdict(s) for s in self.sites],
            "areas": [asdict(a) for a in self.areas],
        }
