"""Dungeons (M8): the levels beneath a site, made the first time anyone goes down and then kept.

The style follows the place and who holds it: natural caves; cellars under a ruin; a crypt under a barrow (stone
coffins, bones); tower floors; an outlaws' hideout (bedrolls, stolen goods); a cult's temple (an altar); a tribe's
warren; a dragon's lair (and its hoard). Levels are joined by stairs; the first level's way up leads back to the
surface. There are locked doors and chests, a hidden room behind a secret door now and then, and traps.

Hidden things live in `LocalMap.features` ({(x, y): {...}}): traps and chest contents. Rooms and the style are in
`LocalMap.meta`. Inhabitants are placed by game/dungeon.py when the level is first entered.
"""

from __future__ import annotations

import numpy as np

from realmwalker.core.rng import RNG
from realmwalker.world.local import LocalMap

DUNGEON_W, DUNGEON_H = 64, 40
STYLES = {
    "cellars": {"wall": "wall_stone", "floor": "floor_stone", "cave": False, "name": "cellars"},
    "crypt": {"wall": "wall_stone", "floor": "floor_stone", "cave": False, "name": "crypt"},
    "tower": {"wall": "wall_stone", "floor": "floor_wood", "cave": False, "name": "tower"},
    "hideout": {"wall": "cave_wall", "floor": "rock_floor", "cave": True, "name": "hideout"},
    "temple": {"wall": "wall_stone", "floor": "floor_stone", "cave": False, "name": "hidden temple"},
    "cave": {"wall": "cave_wall", "floor": "rock_floor", "cave": True, "name": "caves"},
    "warren": {"wall": "cave_wall", "floor": "rock_floor", "cave": True, "name": "warren"},
    "lair": {"wall": "cave_wall", "floor": "rock_floor", "cave": True, "name": "lair"},
}
TRAPS = {"pit": ("a pit trap", "2d6", "bludgeoning"), "darts": ("poisoned darts", "2d4", "piercing"),
         "blade": ("a swinging blade", "2d8", "slashing"), "fire": ("a gout of fire", "3d6", "fire")}


def dungeon_key(x: int, y: int, level: int) -> str:
    return f"{x},{y}/{level}"


def dragon_at(world, site) -> dict | None:
    for d in world.politics.get("dragons", []):
        if d.get("alive") and d.get("lair") == site.id:
            return d
    return None


def style_for(world, site) -> str:
    if dragon_at(world, site) is not None:
        return "lair"
    f = world.factions.get(site.faction) if getattr(site, "faction", -1) >= 0 else None
    if f is not None and f.active:
        return {"bandit_gang": "hideout", "cult": "temple", "tribe": "warren", "mages_circle": "tower"}.get(
            f.kind, "cellars")
    return {"cave": "cave", "ruin": "cellars", "barrow": "crypt", "tower": "tower"}.get(site.kind, "cellars")


def depth_for(world, site) -> int:
    style = style_for(world, site)
    if style == "lair":
        return 1
    danger = int(getattr(site, "danger", 2))
    depth = 1 + (danger >= 4) + (danger >= 7)
    return min(depth, 2) if style in ("hideout", "warren") else depth


class DungeonBuilder:
    def __init__(self, world, tables, site, level: int) -> None:
        self.world = world
        self.tables = tables
        self.site = site
        self.level = level
        self.depth = depth_for(world, site)
        self.style = style_for(world, site)
        self.spec = STYLES[self.style]
        self.rng = RNG(world.meta.seed, f"dungeon/{site.x},{site.y}/{level}")
        self.w, self.h = DUNGEON_W, DUNGEON_H
        self.T = tables.terrain.index
        self.t = np.full((self.w, self.h), self.T[self.spec["wall"]], dtype=np.uint16)
        self.rooms: list[list[int]] = []  # [x, y, w, h]
        self.hidden: set[int] = set()  # rooms behind a secret door
        self.features: dict = {}

    def set(self, x: int, y: int, name: str) -> None:
        if 0 < x < self.w - 1 and 0 < y < self.h - 1:
            self.t[x, y] = self.T[name]

    def is_(self, x: int, y: int, name: str) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h and int(self.t[x, y]) == self.T[name]

    def floor(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h and bool(self.tables.terrain.walk[self.t[x, y]])

    # ------------------------------------------------------------------ build
    def build(self) -> LocalMap:
        if self.spec["cave"]:
            self.caves()
        else:
            self.rooms_and_corridors()
        self.stairs()
        self.furnish()
        self.chests()
        self.traps()
        variant = self.rng.numpy("variant").integers(0, 256, size=(self.w, self.h)).astype(np.uint8)
        up = self.rooms[0]
        entry = (up[0] + up[2] // 2, up[1] + up[3] // 2)
        return LocalMap(
            key=dungeon_key(self.site.x, self.site.y, self.level), kind="dungeon", width=self.w, height=self.h,
            terrain_ids=list(self.tables.terrain.ids), terrain=self.t, variant=variant, entry=entry,
            features=self.features,
            meta={"site": self.site.id, "level": self.level, "depth": self.depth, "style": self.style,
                  "rooms": self.rooms, "hidden": sorted(self.hidden), "name": self.spec["name"]},
        )

    # ------------------------------------------------------------------ rooms and corridors
    def rooms_and_corridors(self) -> None:
        floor = self.spec["floor"]
        rng = self.rng
        want = rng.randint(6, 10)
        for _ in range(want * 30):
            if len(self.rooms) >= want:
                break
            rw, rh = rng.randint(5, 11), rng.randint(4, 7)
            rx, ry = rng.randint(2, self.w - rw - 3), rng.randint(2, self.h - rh - 3)
            if any(rx < ox + ow + 2 and ox < rx + rw + 2 and ry < oy + oh + 2 and oy < ry + rh + 2
                   for ox, oy, ow, oh in self.rooms):
                continue
            self.rooms.append([rx, ry, rw, rh])
            for x in range(rx, rx + rw):
                for y in range(ry, ry + rh):
                    self.set(x, y, floor)
        self.rooms.sort(key=lambda r: (r[0] + r[2] // 2) + (r[1] + r[3] // 2) * 0.3)
        centres = [(r[0] + r[2] // 2, r[1] + r[3] // 2) for r in self.rooms]
        for a, b in zip(centres, centres[1:]):
            self.corridor(a, b)
        for _ in range(rng.randint(1, 2)):  # a loop or two, so there is more than one way round
            if len(centres) > 3:
                a, b = rng.sample(centres, 2)
                self.corridor(a, b)
        self.doors()
        if rng.chance(0.5):
            self.secret_room()

    def corridor(self, a, b) -> None:
        floor = self.spec["floor"]
        x, y = a
        horizontal_first = self.rng.chance(0.5)
        path = []
        if horizontal_first:
            path += [(xx, y) for xx in range(min(x, b[0]), max(x, b[0]) + 1)]
            path += [(b[0], yy) for yy in range(min(y, b[1]), max(y, b[1]) + 1)]
        else:
            path += [(x, yy) for yy in range(min(y, b[1]), max(y, b[1]) + 1)]
            path += [(xx, b[1]) for xx in range(min(x, b[0]), max(x, b[0]) + 1)]
        for cx, cy in path:
            if not self.floor(cx, cy):
                self.set(cx, cy, floor)

    def in_room(self, x: int, y: int) -> int | None:
        for i, (rx, ry, rw, rh) in enumerate(self.rooms):
            if rx <= x < rx + rw and ry <= y < ry + rh:
                return i
        return None

    def doors(self) -> None:
        """Doors where corridors meet rooms; some of them locked."""
        rng = self.rng
        for i, (rx, ry, rw, rh) in enumerate(self.rooms):
            ring = [(x, ry - 1) for x in range(rx, rx + rw)] + [(x, ry + rh) for x in range(rx, rx + rw)] + \
                   [(rx - 1, y) for y in range(ry, ry + rh)] + [(rx + rw, y) for y in range(ry, ry + rh)]
            for x, y in ring:
                if not self.floor(x, y) or self.in_room(x, y) is not None:
                    continue
                # A doorway: corridor on the outside, wall on both sides along the room's edge.
                horiz = y in (ry - 1, ry + rh)
                sides = [(x - 1, y), (x + 1, y)] if horiz else [(x, y - 1), (x, y + 1)]
                if any(self.floor(sx, sy) for sx, sy in sides):
                    continue
                if rng.chance(0.55):
                    locked = i > 1 and rng.chance(0.2 + 0.1 * self.level)
                    self.set(x, y, "door_locked" if locked else "door_closed")
                    if locked:
                        self.features[(x, y)] = {"kind": "lock", "dc": 11 + 2 * self.level + rng.randint(0, 3)}

    def secret_room(self) -> None:
        """A small room behind a wall that looks like any other."""
        floor = self.spec["floor"]
        rng = self.rng
        for _ in range(60):
            base = rng.choice(self.rooms[1:]) if len(self.rooms) > 1 else self.rooms[0]
            rx, ry, rw, rh = base
            side = rng.choice(["n", "s", "e", "w"])
            w, h = rng.randint(3, 5), rng.randint(3, 4)
            if side == "e":
                sx, sy, door = rx + rw + 1, ry + rh // 2 - h // 2, (rx + rw, ry + rh // 2)
            elif side == "w":
                sx, sy, door = rx - w - 1, ry + rh // 2 - h // 2, (rx - 1, ry + rh // 2)
            elif side == "n":
                sx, sy, door = rx + rw // 2 - w // 2, ry - h - 1, (rx + rw // 2, ry - 1)
            else:
                sx, sy, door = rx + rw // 2 - w // 2, ry + rh + 1, (rx + rw // 2, ry + rh)
            if sx < 2 or sy < 2 or sx + w > self.w - 2 or sy + h > self.h - 2:
                continue
            area = self.t[sx - 1:sx + w + 1, sy - 1:sy + h + 1]
            if not (area == self.T[self.spec["wall"]]).all() or self.floor(*door):
                continue
            for x in range(sx, sx + w):
                for y in range(sy, sy + h):
                    self.set(x, y, floor)
            self.set(door[0], door[1], "secret_door")
            self.features[door] = {"kind": "secret", "dc": 13 + self.level}
            self.rooms.append([sx, sy, w, h])
            self.hidden.add(len(self.rooms) - 1)
            return

    # ------------------------------------------------------------------ caves
    def caves(self) -> None:
        floor, wall = self.T[self.spec["floor"]], self.T[self.spec["wall"]]
        g = self.rng.numpy("cave")
        open_ = g.random((self.w, self.h)) > (0.42 if self.style != "lair" else 0.36)
        for _ in range(5):
            padded = np.pad(open_, 1, constant_values=False)
            n = sum(padded[1 + dx:1 + dx + self.w, 1 + dy:1 + dy + self.h]
                    for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
            open_ = (open_ & (n >= 4)) | (~open_ & (n >= 5))
        open_[0, :] = open_[-1, :] = False
        open_[:, 0] = open_[:, -1] = False
        # Keep the biggest cavern system; fill the rest.
        from collections import deque

        seen = np.zeros_like(open_)
        best: list = []
        for x in range(1, self.w - 1):
            for y in range(1, self.h - 1):
                if open_[x, y] and not seen[x, y]:
                    region = []
                    q = deque([(x, y)])
                    seen[x, y] = True
                    while q:
                        cx, cy = q.popleft()
                        region.append((cx, cy))
                        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                            if open_[nx, ny] and not seen[nx, ny]:
                                seen[nx, ny] = True
                                q.append((nx, ny))
                    if len(region) > len(best):
                        best = region
        self.t[:, :] = wall
        for x, y in best:
            self.t[x, y] = floor
        # "Rooms" in a cave: open spots spread far apart (for stairs, lairs and treasure).
        cells = best
        picks = [cells[len(cells) // 2]]
        want = self.rng.randint(5, 8)
        for _ in range(want - 1):
            far = max(cells[:: max(1, len(cells) // 400)],
                      key=lambda c: min(abs(c[0] - p[0]) + abs(c[1] - p[1]) for p in picks))
            picks.append(far)
        picks.sort(key=lambda c: c[0] + c[1] * 0.3)
        self.rooms = [[x - 1, y - 1, 3, 3] for x, y in picks]

    # ------------------------------------------------------------------ stairs, furniture, treasure, traps
    def centre(self, i: int) -> tuple[int, int]:
        r = self.rooms[i]
        return r[0] + r[2] // 2, r[1] + r[3] // 2

    def stairs(self) -> None:
        x, y = self.centre(0)
        self.set(x, y, "stairs_up")
        if self.level < self.depth:
            open_rooms = [i for i in range(1, len(self.rooms)) if i not in self.hidden]
            far = max(open_rooms, key=lambda i: abs(self.centre(i)[0] - x) + abs(self.centre(i)[1] - y), default=0)
            fx, fy = self.centre(far)
            self.set(fx, fy, "stairs_down")

    def passable(self, x: int, y: int) -> bool:
        return self.floor(x, y) or any(self.is_(x, y, n) for n in ("door_closed", "door_locked", "secret_door"))

    def harmless(self, x: int, y: int) -> bool:
        """Something solid can stand here without cutting a way in two: the open cells around it form one
        unbroken arc, and it is not in a doorway."""
        if any(self.is_(x + dx, y + dy, n) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
               for n in ("door_closed", "door_locked", "secret_door")):
            return False
        ring = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
        open_ = [self.passable(x + dx, y + dy) for dx, dy in ring]
        if not any(open_):
            return False
        # Diagonal steps only count where they could really be walked round.
        runs = sum(1 for i in range(8) if open_[i] and not open_[i - 1])
        return runs <= 1

    def open_cells(self, i: int) -> list[tuple[int, int]]:
        rx, ry, rw, rh = self.rooms[i]
        return [(x, y) for x in range(rx, rx + rw) for y in range(ry, ry + rh)
                if self.floor(x, y) and not self.is_(x, y, "stairs_up") and not self.is_(x, y, "stairs_down")
                and self.harmless(x, y)]

    def furnish(self) -> None:
        rng = self.rng
        style = self.style
        for i in range(1, len(self.rooms)):
            if i in self.hidden:
                continue  # only its chest
            cells = self.open_cells(i)
            if not cells:
                continue
            if style == "crypt":
                for _ in range(rng.randint(1, 3)):
                    cells = self.open_cells(i)
                    if not cells:
                        break
                    x, y = rng.choice(cells)
                    self.set(x, y, "sarcophagus")
                    self.features[(x, y)] = {"kind": "chest", "grave": True, "locked": 0,
                                             "treasure": self.level + 1, "rouse": rng.chance(0.3)}
            elif style == "hideout":
                for x, y in rng.sample(cells, min(len(cells), rng.randint(2, 4))):
                    self.set(x, y, "bedroll")
            elif style in ("warren", "lair", "cave"):
                for x, y in rng.sample(cells, min(len(cells), rng.randint(0, 3))):
                    self.set(x, y, "bones")
        if style == "temple":
            biggest = max(range(1, len(self.rooms)), key=lambda i: self.rooms[i][2] * self.rooms[i][3], default=0)
            cells = self.open_cells(biggest)
            if cells:
                x, y = cells[len(cells) // 2]
                self.set(x, y, "altar")
        if style == "lair":
            far = len(self.rooms) - 1
            cx, cy = self.centre(far)
            for dx in range(-3, 4):
                for dy in range(-2, 3):
                    if self.floor(cx + dx, cy + dy) and abs(dx) + abs(dy) <= 4:
                        self.set(cx + dx, cy + dy, "hoard")
            self.features[(cx, cy)] = {"kind": "hoard"}

    def chests(self) -> None:
        rng = self.rng
        count = rng.randint(1, 2) + (1 if self.level == self.depth else 0)
        candidates = [i for i in range(1, len(self.rooms)) if i not in self.hidden]
        for i in sorted(self.hidden):
            x, y = self.centre(i)
            self.set(x, y, "chest")
            self.features[(x, y)] = {"kind": "chest", "locked": 0, "treasure": self.level + 2}
        rng.shuffle(candidates)
        for i in candidates[:count]:
            cells = [c for c in self.open_cells(i) if not self.features.get(c)]
            if not cells:
                continue
            x, y = rng.choice(cells)
            self.set(x, y, "chest")
            locked = rng.chance(0.5)
            self.features[(x, y)] = {"kind": "chest", "locked": 11 + 2 * self.level if locked else 0,
                                     "treasure": self.level + (1 if locked else 0)}

    def traps(self) -> None:
        if self.style == "lair":
            return
        rng = self.rng
        corridor = [(x, y) for x in range(1, self.w - 1) for y in range(1, self.h - 1)
                    if self.floor(x, y) and self.in_room(x, y) is None and not self.features.get((x, y))
                    and not self.is_(x, y, "door_closed")]
        if self.spec["cave"]:
            first = self.centre(0)
            corridor = [(x, y) for x in range(1, self.w - 1) for y in range(1, self.h - 1)
                        if self.floor(x, y) and abs(x - first[0]) + abs(y - first[1]) > 6]
        for x, y in rng.sample(corridor, min(len(corridor), rng.randint(1, 2) + self.level)):
            kind = rng.choice(sorted(TRAPS))
            self.features[(x, y)] = {"kind": "trap", "trap": kind, "dc": 11 + self.level + rng.randint(0, 3),
                                     "found": False, "spent": False}


def get_dungeon(world, tables, site, level: int) -> LocalMap:
    key = dungeon_key(site.x, site.y, level)
    lm = world.local_maps.get(key)
    if lm is None:
        lm = DungeonBuilder(world, tables, site, level).build()
        world.local_maps[key] = lm
    return lm


def add_entrance(tables, lm: LocalMap) -> tuple[int, int]:
    """The way down on a site's surface map (added to maps made before dungeons existed)."""
    T = tables.terrain
    found = np.argwhere(lm.terrain == lm.terrain_ids.index("stairs_down")) if "stairs_down" in lm.terrain_ids else []
    if len(found):
        return int(found[0][0]), int(found[0][1])
    if "stairs_down" not in lm.terrain_ids:
        lm.terrain_ids.append("stairs_down")
    idx = lm.terrain_ids.index("stairs_down")
    walk_ids = {i for i, tid in enumerate(lm.terrain_ids) if tid in T.index and T.walk[T.index[tid]]}
    cx, cy = lm.width // 2, lm.height // 2
    best = None
    for r in range(0, max(lm.width, lm.height)):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                x, y = cx + dx, cy + dy
                if max(abs(dx), abs(dy)) == r and 0 < x < lm.width - 1 and 0 < y < lm.height - 1 and \
                        int(lm.terrain[x, y]) in walk_ids and (x, y) != tuple(lm.entry):
                    best = (x, y)
                    break
            if best:
                break
        if best:
            break
    x, y = best or (cx, cy)
    lm.terrain[x, y] = idx
    return x, y
