"""Local maps: the ground-level view of one overworld tile, generated from the world seed the
first time it is visited and then kept (with any changes) in the save.

Kinds (M1): wilderness for every biome, with rivers, roads and shorelines carried over from
the overworld; settlements with streets, buildings, walls and fields; ruins at old sites.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from realmwalker.core.rng import RNG
from realmwalker.world.model import DIRS, Settlement, World
from realmwalker.world.noise import fbm
from realmwalker.world.tables import Tables

LOCAL_W = 96
LOCAL_H = 60
ASPECT = 0.5  # screen cells are about twice as tall as wide; keep patches round on screen


@dataclass
class Building:
    x: int
    y: int
    w: int
    h: int
    kind: str  # house, inn, temple, smithy, market, hall, keep
    name: str = ""
    door: tuple[int, int] = (0, 0)

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h


@dataclass
class LocalMap:
    key: str
    kind: str  # wilderness, settlement, ruin
    width: int
    height: int
    terrain_ids: list[str]  # the terrain order used by `terrain`, stored so saves survive data changes
    terrain: np.ndarray  # uint16 [x, y] index into terrain_ids
    variant: np.ndarray  # uint8 [x, y] which glyph variation to draw
    buildings: list[Building] = field(default_factory=list)
    entry: tuple[int, int] = (0, 0)
    seen: np.ndarray | None = None  # bool [x, y] cells the player has seen
    items: dict = field(default_factory=dict)  # (x, y) -> list of Item lying on the ground
    actors: list = field(default_factory=list)  # bands of creatures (game.encounters.LocalActor)
    populated: bool = False  # inhabitants have been placed

    def __post_init__(self) -> None:
        if self.seen is None:
            self.seen = np.zeros((self.width, self.height), dtype=bool)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def building_at(self, x: int, y: int) -> Building | None:
        for b in self.buildings:
            if b.contains(x, y):
                return b
        return None


def local_key(x: int, y: int) -> str:
    return f"{x},{y}"


class LocalBuilder:
    """Generates one local map. Deterministic for a given world seed and tile."""

    def __init__(self, world: World, tables: Tables, x: int, y: int) -> None:
        self.world = world
        self.tables = tables
        self.T = tables.terrain.index
        self.ox, self.oy = x, y
        self.rng = RNG(world.meta.seed, f"local/{x},{y}")
        self.np = self.rng.numpy("cells")
        self.w, self.h = LOCAL_W, LOCAL_H
        self.t = np.zeros((self.w, self.h), dtype=np.uint16)
        self.buildings: list[Building] = []
        biome_id = world.biome_id(x, y)
        self.biome = tables.biomes.defs[tables.biomes.index.get(biome_id, tables.biomes.index["plains"])]
        self.biome_id = biome_id

    # ------------------------------------------------------------------ helpers
    def tid(self, name: str) -> int:
        return self.T[name]

    def fill_rect(self, x: int, y: int, w: int, h: int, name: str) -> None:
        self.t[max(0, x):max(0, min(self.w, x + w)), max(0, y):max(0, min(self.h, y + h))] = self.tid(name)

    def set(self, x: int, y: int, name: str) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.t[x, y] = self.tid(name)

    def is_(self, x: int, y: int, *names: str) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h and self.tables.terrain.ids[int(self.t[x, y])] in names

    # ------------------------------------------------------------------ build
    def build(self) -> LocalMap:
        self._ground()
        self._water_edges()
        self._vegetation()
        river_path = self._river()
        road_cells = self._roads(river_path)
        settlement = self.world.settlement_at(self.ox, self.oy)
        site = self.world.site_at(self.ox, self.oy)
        kind = "wilderness"
        if settlement is not None:
            self._settlement(settlement)
            kind = "settlement"
        elif site is not None and site.kind in ("ruin", "tower"):
            self._ruin()
            kind = "ruin"
        self._ensure_passable_edges()
        variant = (self.np.integers(0, 256, size=(self.w, self.h))).astype(np.uint8)
        entry = self._entry_point(road_cells)
        return LocalMap(
            key=local_key(self.ox, self.oy), kind=kind, width=self.w, height=self.h,
            terrain_ids=list(self.tables.terrain.ids), terrain=self.t, variant=variant,
            buildings=self.buildings, entry=entry,
        )

    def _ground(self) -> None:
        ground = self.biome["local"]["ground"]
        names = [g[0] for g in ground]
        weights = np.array([float(g[1]) for g in ground])
        cum = np.cumsum(weights / weights.sum())
        patch = fbm(self.np, self.w, self.h, cell=9, octaves=3, aspect=ASPECT)
        jitter = self.np.random((self.w, self.h)) * 0.18
        v = np.clip(patch * 0.85 + jitter, 0, 0.9999)
        idx = np.searchsorted(cum, v)
        ids = np.array([self.tid(n) for n in names], dtype=np.uint16)
        self.t[:] = ids[np.clip(idx, 0, len(ids) - 1)]

    def _water_edges(self) -> None:
        """If a neighbouring overworld tile is sea or lake, flood that side of the map."""
        B = self.tables.biomes.index
        water_ids = {B["ocean"], B["lake"]}
        own_water = int(self.world.biome[self.ox, self.oy]) in water_ids
        noise = fbm(self.np, self.w, self.h, cell=12, octaves=3, aspect=ASPECT)
        xs = np.linspace(-1, 1, self.w)[:, None]
        ys = np.linspace(-1, 1, self.h)[None, :]
        wet = np.zeros((self.w, self.h))
        for d, nx, ny in self.world.neighbours(self.ox, self.oy):
            if int(self.world.biome[nx, ny]) not in water_ids:
                continue
            dx, dy = DIRS[d]
            reach = xs * dx + ys * dy if (dx and dy) else (xs * dx if dx else ys * dy)
            wet = np.maximum(wet, reach)
        if own_water:
            wet[:] = 1.0
        if wet.max() <= 0:
            return
        level = wet + (noise - 0.5) * 0.35
        deep = level > 0.62
        shallow = (level > 0.50) & ~deep
        beach = (level > 0.40) & ~deep & ~shallow
        shore = "sand" if self.biome_id in ("coast", "plains", "desert") else "gravel"
        self.t[beach] = self.tid(shore)
        self.t[shallow] = self.tid("shallow_water")
        self.t[deep] = self.tid("deep_water")

    def _vegetation(self) -> None:
        loc = self.biome["local"]
        free = ~np.isin(self.t, [self.tid(n) for n in ("deep_water", "shallow_water")])
        cluster = fbm(self.np, self.w, self.h, cell=7, octaves=3, aspect=ASPECT)
        r = self.np.random((self.w, self.h))
        if loc["trees"] > 0 and loc["tree_types"]:
            p = np.clip(loc["trees"] * (0.35 + 1.5 * cluster), 0, 0.9)
            trees = free & (r < p)
            types = [self.tid(n) for n in loc["tree_types"]]
            choice = self.np.integers(0, len(types), size=(self.w, self.h))
            self.t[trees] = np.array(types, dtype=np.uint16)[choice[trees]]
        r2 = self.np.random((self.w, self.h))
        if loc["bushes"] > 0:
            self.t[free & (r2 < loc["bushes"])] = self.tid("bush")
        r3 = self.np.random((self.w, self.h))
        if loc["rocks"] > 0:
            self.t[free & (r3 < loc["rocks"] * 0.5)] = self.tid("boulder")
            self.t[free & (r3 >= loc["rocks"] * 0.5) & (r3 < loc["rocks"])] = self.tid("gravel")
        if loc["water"] > 0:
            pools = fbm(self.np, self.w, self.h, cell=6, octaves=3, aspect=ASPECT)
            self.t[free & (pools > 1 - loc["water"] * 1.6)] = self.tid("shallow_water")

    def _edge_point(self, d: int, offset: float) -> tuple[int, int]:
        """A point on the map edge in overworld direction d (offset 0..1 along the edge)."""
        dx, dy = DIRS[d]
        cx = int(offset * (self.w - 1))
        cy = int(offset * (self.h - 1))
        if dx and dy:
            return (0 if dx < 0 else self.w - 1, 0 if dy < 0 else self.h - 1)
        if dx:
            return (0 if dx < 0 else self.w - 1, cy)
        return (cx, 0 if dy < 0 else self.h - 1)

    def _meander(self, a: tuple[int, int], b: tuple[int, int], wobble: float) -> list[tuple[int, int]]:
        """A wandering line of cells from a to b (4-connected), drifting sideways now and then."""
        x, y = a
        bx, by = b
        points = [(x, y)]
        guard = 0
        while (x, y) != (bx, by) and guard < 4000:
            guard += 1
            dx, dy = bx - x, by - y
            if self.rng.random() < wobble * 0.3:
                if abs(dx) > abs(dy):
                    y = max(0, min(self.h - 1, y + self.rng.choice([-1, 1])))
                else:
                    x = max(0, min(self.w - 1, x + self.rng.choice([-1, 1])))
            elif self.rng.random() * (abs(dx) + abs(dy)) < abs(dx):
                x += 1 if dx > 0 else -1
            else:
                y += 1 if dy > 0 else -1
            points.append((x, y))
        if points[-1] != (bx, by):
            points.append((bx, by))
        return points

    def _river(self) -> list[tuple[int, int]]:
        size = int(self.world.river[self.ox, self.oy])
        if size == 0:
            return []
        inflows = []
        for d, nx, ny in self.world.neighbours(self.ox, self.oy):
            if self.world.river[nx, ny] and self.world.downstream(nx, ny) == (self.ox, self.oy):
                inflows.append(d)
        out = int(self.world.flow[self.ox, self.oy])
        centre = (self.w // 2 + self.rng.randint(-6, 6), self.h // 2 + self.rng.randint(-4, 4))
        start_points = [self._edge_point(d, self.rng.uniform(0.35, 0.65)) for d in inflows] or [centre]
        end = self._edge_point(out, self.rng.uniform(0.35, 0.65)) if out else centre
        width = {1: 2, 2: 4, 3: 6}[size]
        path: list[tuple[int, int]] = []
        for sp in start_points:
            path += self._meander(sp, centre, 0.8)
        path += self._meander(centre, end, 0.8)
        for x, y in path:
            for ix in range(-(width // 2) - 1, width // 2 + 2):
                for iy in range(-(width // 2) - 1, width // 2 + 2):
                    px, py = x + ix, y + iy
                    if not (0 <= px < self.w and 0 <= py < self.h):
                        continue
                    edge = abs(ix) > width // 2 or abs(iy) > width // 2
                    if edge:
                        if not self.is_(px, py, "river", "deep_water"):
                            self.set(px, py, "mud" if self.rng.chance(0.5) else "gravel")
                    else:
                        self.set(px, py, "river")
        return path

    def _roads(self, river_path: list[tuple[int, int]]) -> list[tuple[int, int]]:
        if not self.world.road[self.ox, self.oy]:
            return []
        centre = (self.w // 2, self.h // 2)
        cells: list[tuple[int, int]] = []
        for d in (1, 3, 5, 7):  # roads leave through the four sides
            dx, dy = DIRS[d]
            nx, ny = self.ox + dx, self.oy + dy
            if self.world.in_bounds(nx, ny) and self.world.road[nx, ny]:
                cells += self._meander(self._edge_point(d, 0.5), centre, 0.35)
        if not cells:
            cells = [centre]
        river_cells = set(river_path)
        crossed_river = False
        for x, y in cells:
            for ix, iy in ((0, 0), (1, 0), (0, 1)):
                px, py = x + ix, y + iy
                if not (0 <= px < self.w and 0 <= py < self.h):
                    continue
                if self.is_(px, py, "river", "deep_water"):
                    self.set(px, py, "bridge")
                    crossed_river = True
                elif not self.is_(px, py, "bridge"):
                    self.set(px, py, "road")
        if river_cells and not crossed_river:
            self._ford(river_path)
        return cells

    def _ford(self, river_path: list[tuple[int, int]]) -> None:
        """Rivers without a bridge get a ford somewhere, so the map is never cut in two."""
        if not river_path:
            return
        x, y = river_path[len(river_path) // 2]
        for ix in range(-4, 5):
            for iy in range(-4, 5):
                if self.is_(x + ix, y + iy, "river"):
                    self.set(x + ix, y + iy, "ford")

    # ------------------------------------------------------------------ settlements
    def _settlement(self, s: Settlement) -> None:
        spec = self.tables.sites["settlement_types"][s.kind]
        lo, hi = spec["buildings"]
        n_buildings = self.rng.randint(lo, hi)
        size = {"hamlet": 14, "village": 22, "town": 30, "city": 40, "hold": 24, "elfhall": 22}.get(s.kind, 22)
        half_w = min(self.w // 2 - 3, size)
        half_h = min(self.h // 2 - 3, int(size * 0.62))
        cx, cy = self.w // 2, self.h // 2
        x0, y0, x1, y1 = cx - half_w, cy - half_h, cx + half_w, cy + half_h
        stone = s.kind in ("town", "city", "hold")
        street = "cobbles" if stone else "road"
        wall = "wall_stone" if stone else "wall_wood"
        floor = "floor_stone" if s.kind in ("city", "hold") else ("floor_wood" if stone else "floor_earth")

        # Clear the ground inside the settlement of trees, rocks and water.
        area = self.t[x0:x1, y0:y1]
        blocked = ~self.tables.terrain.walk[area] | np.isin(area, [self.tid("shallow_water"), self.tid("bush")])
        area[blocked & ~np.isin(area, [self.tid("river"), self.tid("bridge"), self.tid("ford")])] = self.tid("dirt")
        if s.kind == "hold":
            # Dwarven holds are cut into the mountain: rock all round, halls inside.
            self.t[:, :] = np.where(self.np.random((self.w, self.h)) < 0.9, self.tid("cave_wall"), self.tid("rubble"))
            self.fill_rect(x0, y0, x1 - x0, y1 - y0, "rock_floor")
            street = "cobbles"

        # Main streets: one across, one down, plus side streets in bigger places.
        streets = [(x0, cy, x1 - x0, 1), (cx, y0, 1, y1 - y0)]
        if s.kind in ("town", "city"):
            streets += [(x0, cy - half_h // 2, x1 - x0, 1), (x0, cy + half_h // 2, x1 - x0, 1),
                        (cx - half_w // 2, y0, 1, y1 - y0), (cx + half_w // 2, y0, 1, y1 - y0)]
        for sx, sy, sw, sh in streets:
            for x in range(sx, sx + sw):
                for y in range(sy, sy + sh):
                    if self.is_(x, y, "river", "deep_water"):
                        self.set(x, y, "bridge")
                    elif not self.is_(x, y, "bridge"):
                        self.set(x, y, street)
        # A square in the middle with a well (and stalls in towns).
        sq = 3 if s.kind in ("hamlet", "village", "elfhall") else 5
        self.fill_rect(cx - sq, cy - sq // 2 - 1, sq * 2 + 1, sq + 2, street)
        self.set(cx + 2, cy - 1, "well")
        if s.kind != "hamlet" and "notice_board" in self.tables.terrain.index:
            self.set(cx - 2, cy - 1, "notice_board")
        if s.kind in ("town", "city"):
            for sx in (cx - sq + 1, cx - sq + 3, cx + sq - 3, cx + sq - 1):
                self.set(sx, cy - sq // 2 - 1, "stall")

        kinds = self._building_kinds(s.kind, n_buildings)
        placed = 0
        attempts = 0
        while placed < len(kinds) and attempts < n_buildings * 40:
            attempts += 1
            kind = kinds[placed]
            bw = self.rng.randint(5, 9) if kind == "house" else self.rng.randint(8, 13)
            bh = self.rng.randint(4, 6) if kind == "house" else self.rng.randint(5, 8)
            bx = self.rng.randint(x0 + 1, max(x0 + 1, x1 - bw - 1))
            by = self.rng.randint(y0 + 1, max(y0 + 1, y1 - bh - 1))
            if not self._space_free(bx - 1, by - 1, bw + 2, bh + 2, street):
                continue
            door = self._place_building(bx, by, bw, bh, wall, floor, street)
            if door is None:
                continue
            b = Building(bx, by, bw, bh, kind, door=door)
            self._furnish(b)
            self.buildings.append(b)
            placed += 1

        if s.kind == "elfhall":
            # Elves leave their trees standing between the halls.
            for _ in range(160):
                x, y = self.rng.randint(x0, x1), self.rng.randint(y0, y1)
                if self.is_(x, y, "dirt", "grass", "leaf_litter"):
                    self.set(x, y, "tree_broadleaf")
        if s.walled and s.kind != "hold":
            self._walls(x0 - 2, y0 - 2, x1 + 2, y1 + 2, "palisade" if spec["walls"] == "palisade" else "wall_stone")
        if s.kind in ("hamlet", "village"):
            self._fields(x0, y0, x1, y1)
        if s.kind in ("village", "town", "city"):
            self._graveyard(x0, y0, x1, y1)

    def _building_kinds(self, kind: str, n: int) -> list[str]:
        special = {
            "hamlet": [],
            "village": ["inn", "temple", "store", "smithy"],
            "town": ["inn", "inn", "temple", "smithy", "hall", "store", "healer", "stable"],
            "city": ["inn", "inn", "inn", "temple", "temple", "smithy", "smithy", "hall", "keep", "store", "store", "healer",
                     "stable"],
            "hold": ["hall", "smithy", "smithy", "temple", "inn", "store"],
            "elfhall": ["hall", "temple", "healer"],
        }.get(kind, [])
        kinds = special + ["house"] * max(0, n - len(special))
        return kinds

    def _space_free(self, x: int, y: int, w: int, h: int, street: str) -> bool:
        if x < 0 or y < 0 or x + w > self.w or y + h > self.h:
            return False
        area = self.t[x:x + w, y:y + h]
        bad = [self.tid(n) for n in ("wall_stone", "wall_wood", "floor_wood", "floor_stone", "floor_earth", "river",
                                     "deep_water", "bridge", "well", "shallow_water", "ford", "door_closed")]
        if np.isin(area, bad).any():
            return False
        # Keep buildings off the streets themselves (but allow them to touch).
        inner = self.t[x + 1:x + w - 1, y + 1:y + h - 1]
        return not np.isin(inner, [self.tid(street), self.tid("cobbles"), self.tid("road")]).any()

    def _place_building(self, x: int, y: int, w: int, h: int, wall: str, floor: str, street: str) -> tuple[int, int] | None:
        self.fill_rect(x, y, w, h, wall)
        self.fill_rect(x + 1, y + 1, w - 2, h - 2, floor)
        # Door on the side nearest a street.
        options = [(x + w // 2, y), (x + w // 2, y + h - 1), (x, y + h // 2), (x + w - 1, y + h // 2)]
        street_ids = {self.tid("road"), self.tid("cobbles"), self.tid("floor_stone") if street == "floor_stone" else -1}

        def street_distance(p: tuple[int, int]) -> int:
            px, py = p
            best = 99
            for r in range(1, 12):
                for ix in range(-r, r + 1):
                    for iy in (-r, r):
                        if 0 <= px + ix < self.w and 0 <= py + iy < self.h and int(self.t[px + ix, py + iy]) in street_ids:
                            return r
                for iy in range(-r, r + 1):
                    for ix in (-r, r):
                        if 0 <= px + ix < self.w and 0 <= py + iy < self.h and int(self.t[px + ix, py + iy]) in street_ids:
                            return r
            return best

        door = min(options, key=street_distance)
        self.set(door[0], door[1], "door_closed")
        return door

    def _furnish(self, b: Building) -> None:
        ix0, iy0, ix1, iy1 = b.x + 1, b.y + 1, b.x + b.w - 2, b.y + b.h - 2
        dx, dy = b.door

        def put(x: int, y: int, name: str) -> None:
            if ix0 <= x <= ix1 and iy0 <= y <= iy1 and abs(x - dx) + abs(y - dy) > 1:
                self.set(x, y, name)

        if b.kind == "house":
            put(ix0, iy0, "bed")
            put(ix1, iy0, "hearth")
            if self.rng.chance(0.6):
                put((ix0 + ix1) // 2, iy1, "table")
        elif b.kind == "inn":
            put(ix0, iy0, "hearth")
            for x in range(ix0 + 1, ix1, 3):
                put(x, (iy0 + iy1) // 2, "table")
            for x in range(ix0, ix1 + 1, 2):
                put(x, iy1, "bed")
        elif b.kind == "temple":
            put((ix0 + ix1) // 2, iy0, "altar")
        elif b.kind == "smithy":
            put(ix0 + 1, iy0 + 1, "anvil")
            put(ix0, iy0, "hearth")
        elif b.kind in ("store", "healer"):
            for x in range(ix0 + 1, ix1):
                put(x, iy0, "table")
        elif b.kind == "stable":
            for y in range(iy0, iy1 + 1, 2):
                put(ix1, y, "fence")
        elif b.kind in ("hall", "keep"):
            put(ix0, iy0, "hearth")
            put(ix1, iy0, "hearth")
            for x in range(ix0 + 2, ix1 - 1):
                put(x, (iy0 + iy1) // 2, "table")

    def _walls(self, x0: int, y0: int, x1: int, y1: int, wall: str) -> None:
        x0, y0 = max(1, x0), max(1, y0)
        x1, y1 = min(self.w - 2, x1), min(self.h - 2, y1)
        for x in range(x0, x1 + 1):
            for y in (y0, y1):
                self._wall_cell(x, y, wall)
        for y in range(y0, y1 + 1):
            for x in (x0, x1):
                self._wall_cell(x, y, wall)

    def _wall_cell(self, x: int, y: int, wall: str) -> None:
        if self.is_(x, y, "road", "cobbles", "bridge"):
            self.set(x, y, "gate_open")
        elif self.is_(x, y, "river", "deep_water", "ford"):
            return
        else:
            self.set(x, y, wall)

    def _fields(self, x0: int, y0: int, x1: int, y1: int) -> None:
        for _ in range(self.rng.randint(2, 5)):
            fw, fh = self.rng.randint(8, 16), self.rng.randint(4, 8)
            side = self.rng.randint(0, 3)
            if side == 0:
                fx, fy = self.rng.randint(x0, max(x0, x1 - fw)), y0 - fh - 2
            elif side == 1:
                fx, fy = self.rng.randint(x0, max(x0, x1 - fw)), y1 + 2
            elif side == 2:
                fx, fy = x0 - fw - 2, self.rng.randint(y0, max(y0, y1 - fh))
            else:
                fx, fy = x1 + 2, self.rng.randint(y0, max(y0, y1 - fh))
            crop = "crops" if self.rng.chance(0.7) else "garden"
            for x in range(fx, fx + fw):
                for y in range(fy, fy + fh):
                    if self.is_(x, y, "grass", "tall_grass", "dirt", "heather", "leaf_litter", "needles", "bush",
                                "tree_broadleaf", "tree_pine", "dead_tree", "boulder", "gravel", "sand", "mud"):
                        self.set(x, y, crop)

    def _graveyard(self, x0: int, y0: int, x1: int, y1: int) -> None:
        gx = x1 + 3 if x1 + 10 < self.w else max(1, x0 - 10)
        gy = y0 + self.rng.randint(0, max(0, (y1 - y0) - 6))
        for x in range(gx, gx + 7):
            for y in range(gy, gy + 5):
                if not self.is_(x, y, "grass", "tall_grass", "dirt", "heather", "leaf_litter", "needles", "gravel", "rock_floor"):
                    continue
                if (x - gx) % 2 == 1 and (y - gy) % 2 == 1:
                    self.set(x, y, "grave")

    # ------------------------------------------------------------------ ruins
    def _ruin(self) -> None:
        cx, cy = self.w // 2 + self.rng.randint(-8, 8), self.h // 2 + self.rng.randint(-5, 5)
        for _ in range(self.rng.randint(3, 6)):
            rw, rh = self.rng.randint(6, 14), self.rng.randint(5, 9)
            rx, ry = cx + self.rng.randint(-14, 8), cy + self.rng.randint(-8, 5)
            for x in range(rx, rx + rw):
                for y in range(ry, ry + rh):
                    if not (0 <= x < self.w and 0 <= y < self.h) or self.is_(x, y, "river", "deep_water"):
                        continue
                    border = x in (rx, rx + rw - 1) or y in (ry, ry + rh - 1)
                    if border:
                        self.set(x, y, "ruin_wall" if self.rng.chance(0.62) else "rubble")
                    elif self.rng.chance(0.25):
                        self.set(x, y, "rubble")
                    elif not self.is_(x, y, "tree_broadleaf", "tree_pine"):
                        self.set(x, y, "rock_floor")

    # ------------------------------------------------------------------ connectivity
    def _ensure_passable_edges(self) -> None:
        """Keep a walkable cell near the middle of each edge so the player can always leave."""
        walk = self.tables.terrain.walk
        for x, y in ((self.w // 2, 0), (self.w // 2, self.h - 1), (0, self.h // 2), (self.w - 1, self.h // 2)):
            if not walk[self.t[x, y]] and not self.is_(x, y, "deep_water", "river"):
                self.set(x, y, "dirt")

    def _entry_point(self, road_cells: list[tuple[int, int]]) -> tuple[int, int]:
        walk = self.tables.terrain.walk
        candidates = road_cells or [(self.w // 2, self.h // 2)]
        cx, cy = candidates[len(candidates) // 2] if road_cells else candidates[0]
        for r in range(0, max(self.w, self.h)):
            for ix in range(-r, r + 1):
                for iy in range(-r, r + 1):
                    if max(abs(ix), abs(iy)) != r:
                        continue
                    x, y = cx + ix, cy + iy
                    if 0 <= x < self.w and 0 <= y < self.h and walk[self.t[x, y]] and not self.is_(x, y, "ford"):
                        return (x, y)
        return (cx, cy)


def get_local_map(world: World, tables: Tables, x: int, y: int) -> LocalMap:
    """The local map for an overworld tile: loaded if visited before, generated otherwise."""
    key = local_key(x, y)
    lm = world.local_maps.get(key)
    if lm is None:
        lm = LocalBuilder(world, tables, x, y).build()
        world.local_maps[key] = lm
    return lm


def terrain_remap(lm: LocalMap, tables: Tables) -> np.ndarray:
    """Array converting this map's stored terrain indices to the current data's indices."""
    return np.array([tables.terrain.index.get(t, tables.terrain.index["dirt"]) for t in lm.terrain_ids], dtype=np.int32)
