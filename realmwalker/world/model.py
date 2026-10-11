"""The World: overworld arrays plus settlements, sites, named areas, local maps and the clock.

Arrays are numpy, indexed [x, y]. The world outlives any one character: when a character dies,
the world (with its history, flavour text and local maps) remains for the next.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from realmwalker.core.rng import RNG

# Neighbour offsets. Index 0 means "no direction" (e.g. river mouth or sink).
DIRS: list[tuple[int, int]] = [(0, 0), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]
DIR_NAMES = ["here", "north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]

WORLD_SIZES = {"small": (128, 80), "medium": (192, 120), "large": (256, 160)}

ARRAY_NAMES = ("elevation", "temperature", "moisture", "biome", "river", "flow", "road", "area", "river_area", "danger",
               "culture", "relief")
NO_CULTURE = 255  # water, and land no people claims
# The shape of the land beyond its height (world.relief, bit flags per square).
CLIFF = 1  # a scarp or sea-cliff: the land drops sheer here
RAVINE = 2  # a river runs at the bottom of a gorge it has cut
FALLS = 4  # a river falls over a cliff


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
    land: str = "continent"  # the lie of the land: continent, islands, twin, inland_sea
    climate: str = "temperate"  # frozen, cold, temperate, warm, scorched, varied


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
    owner: int = -1  # the faction holding it (world.factions)
    status: dict = field(default_factory=dict)  # siege, sack, plague... (game.politics)
    great: bool = False  # one of the world's great cities, far bigger than the rest (data/towns.json "great")


@dataclass
class Site:
    id: int
    kind: str  # ruin, cave, barrow, tower
    x: int
    y: int
    name: str
    danger: int = 1
    faction: int = -1  # the tribe, gang, cult or circle that uses it


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
class Wonder:
    """A wonder of the world: a great peak, a volcano, falls, a glowing lake, an enchanted wood (world/wonders.py)."""

    id: int
    kind: str
    name: str
    x: int
    y: int
    cells: list = field(default_factory=list)  # [x, y] of every square it covers (with x, y)
    culture: str = ""  # the people who named it
    flags: dict = field(default_factory=dict)  # awake (a volcano), height (a peak), story...


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
    culture: np.ndarray | None = None  # uint8 index into culture_ids (NO_CULTURE: water or nobody's)
    culture_ids: list[str] = field(default_factory=list)  # the peoples of this world (world/cultures.py)
    relief: np.ndarray | None = None  # uint8 CLIFF | RAVINE | FALLS
    settlements: list[Settlement] = field(default_factory=list)
    sites: list[Site] = field(default_factory=list)
    areas: list[Area] = field(default_factory=list)
    wonders: list[Wonder] = field(default_factory=list)
    time: int = 0  # minutes since the epoch
    local_maps: dict = field(default_factory=dict)  # key "x,y" -> LocalMap
    rng: RNG | None = None
    npcs: dict = field(default_factory=dict)  # id -> game.people.NPC
    towns: dict = field(default_factory=dict)  # settlement id -> game.people.Town
    next_npc_id: int = 0
    factions: dict = field(default_factory=dict)  # id -> world.factions.Faction
    figures: dict = field(default_factory=dict)  # id -> world.factions.Figure
    next_figure_id: int = 0
    wars: list = field(default_factory=list)  # game.politics war records (dicts)
    history: list = field(default_factory=list)  # world.history events (dicts), oldest first
    news: list = field(default_factory=list)  # game.news items (dicts)
    politics: dict = field(default_factory=dict)  # counters and dates for the politics simulation
    faction_version: int = 0  # bumped when holdings change (cached territory maps)

    def __post_init__(self) -> None:
        if self.rng is None:
            self.rng = RNG(self.meta.seed, "sim")
        if self.culture is None:
            self.culture = np.full((self.width, self.height), NO_CULTURE, dtype=np.uint8)
        if self.relief is None:
            self.relief = np.zeros((self.width, self.height), dtype=np.uint8)
        self.rebuild_index()

    # ------------------------------------------------------------------ lookups
    def rebuild_index(self) -> None:
        self.settlement_grid = np.full((self.width, self.height), -1, dtype=np.int32)
        for i, s in enumerate(self.settlements):
            self.settlement_grid[s.x, s.y] = i
        self.site_grid = np.full((self.width, self.height), -1, dtype=np.int32)
        for i, s in enumerate(self.sites):
            self.site_grid[s.x, s.y] = i
        self.wonder_grid = np.full((self.width, self.height), -1, dtype=np.int32)
        for i, wd in enumerate(self.wonders):
            for x, y in wd.cells:
                if self.in_bounds(x, y):
                    self.wonder_grid[x, y] = i
        for i, wd in enumerate(self.wonders):  # a wonder's own square is its own, whatever runs across it
            self.wonder_grid[wd.x, wd.y] = i

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

    def wonder_at(self, x: int, y: int) -> Wonder | None:
        """The wonder covering this square, if any (its heart or any square of it)."""
        i = int(self.wonder_grid[x, y])
        return self.wonders[i] if i >= 0 else None

    def area_at(self, x: int, y: int) -> Area | None:
        i = int(self.area[x, y])
        return self.areas[i] if 0 <= i < len(self.areas) else None

    def culture_at(self, x: int, y: int) -> str | None:
        """The people whose land this is (None at sea, or where nobody lives)."""
        i = int(self.culture[x, y])
        return self.culture_ids[i] if i < len(self.culture_ids) else None

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
            "wonders": [asdict(w) for w in self.wonders],
        }
