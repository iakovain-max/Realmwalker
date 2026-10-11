"""The town being laid out: streets and squares, plots along the streets, and buildings, each with its rooms and the
things in them. The layouts (layouts.py) decide where things go; this makes them.

Every door opens onto a street, a lane, a square or a court; furniture never shuts anybody in; nothing is built in
the water (a street over water is a bridge).
"""

from __future__ import annotations

from collections import deque

import numpy as np
import tcod.path

from realmwalker.world.local import Building

WATER = ("river", "deep_water", "shallow_water", "ford", "bridge", "marsh_reeds", "falls", "plunge_pool",
         "glow_water", "glow_shallow", "lava", "chasm", "crevasse", "brine")
# The stuff of walls (roofs.py's names) as the terrain you see from inside.
WALL_TERRAIN = {"plaster": "wall_plaster", "ochre": "wall_plaster", "rose": "wall_plaster", "whitewash": "wall_white",
                "brick": "wall_brick", "stone": "wall_stone", "dark_stone": "wall_stone", "limestone": "wall_white",
                "sandstone": "wall_sandstone", "marble": "wall_marble", "mudbrick": "wall_mudbrick", "logs": "wall_logs",
                "dark_wood": "wall_logs", "felt": "wall_felt", "living_wood": "giant_bark", "earth": "wall_earth",
                "rock": "cave_wall"}
# Roofs and building shapes the pictures know (ui/gfx/roofs.py).
ROOFS = ("thatch", "slate", "tile", "shingle", "turf", "stone", "flat", "dome", "dome_blue", "onion", "felt",
         "felt_white", "thatch_round", "leaves", "mound", "hide", "none")
SHAPES = ("rect", "long", "round", "court", "tree", "mound", "carved", "pyramid", "L")
PITCHED = ("thatch", "slate", "tile", "shingle", "stone", "turf")  # roofs that can turn a corner (an L-shaped house)
FLOOR_FOR = {"temple": "floor_stone", "keep": "floor_stone", "hall": "floor_stone", "bathhouse": "floor_tile",
             "stable": "floor_earth", "warehouse": "floor_earth", "barracks": "floor_wood", "tomb": "floor_stone",
             "forge_hall": "floor_stone", "mushroom_farm": "floor_earth", "boathouse": "floor_earth"}
# What each kind of building has inside: its rooms, the biggest first.
ROOMS = {
    "house": ["hall", "bedroom", "kitchen"], "inn": ["common", "guest", "guest", "cellar"], "temple": ["nave", "vestry"],
    "smithy": ["forge", "store"], "store": ["shop", "store"], "healer": ["surgery", "bedroom"],
    "hall": ["great_hall", "chamber", "store"], "keep": ["throne", "barracks", "chamber", "armoury"],
    "stable": ["stalls"], "library": ["library", "study"], "bakery": ["bakery", "store"], "brewery": ["brewery", "store"],
    "warehouse": ["store"], "barracks": ["barracks", "armoury"], "bathhouse": ["bath", "bath"],
    "bank": ["counting", "vault"], "caravanserai": ["common", "guest", "stalls"], "boathouse": ["boats"],
    "smokehouse": ["smoking"], "theatre": ["stage"], "forge_hall": ["forge", "forge"],
    "mushroom_farm": ["farm", "farm"], "tomb": ["tomb"],
}
# How a room is furnished: (thing, where, how many). where: wall (along the walls), corner, top (the middle of the
# wall facing the way in), middle, row (rows across the room), near (beside what is already there: chairs at
# tables), floor (something underfoot: a rug).
FURNISH = {
    "hall": [("hearth", "wall", 1), ("table", "middle", 1), ("stool", "near", 2), ("trunk", "corner", 1),
             ("shelf", "wall", 1), ("rug", "floor", 1)],
    "bedroom": [("bed", "corner", 1), ("trunk", "wall", 1), ("wardrobe", "wall", 1)],
    "kitchen": [("oven", "wall", 1), ("barrels", "corner", 1), ("sacks", "corner", 1), ("table", "middle", 1),
                ("shelf", "wall", 1)],
    "common": [("hearth", "wall", 1), ("counter", "wall", 1), ("barrels", "corner", 2), ("table", "row", 4),
               ("stool", "near", 8)],
    "guest": [("bed", "wall", 2), ("trunk", "corner", 1)],
    "cellar": [("barrels", "wall", 4), ("crates", "corner", 1)],
    "nave": [("altar", "top", 1), ("pew", "row", 6), ("candles", "wall", 2), ("statue_small", "corner", 2),
             ("rug", "floor", 1)],
    "vestry": [("bookcase", "wall", 1), ("trunk", "corner", 1), ("candles", "wall", 1)],
    "forge": [("forge", "wall", 1), ("anvil", "middle", 1), ("weapon_rack", "wall", 1), ("trough", "wall", 1),
              ("coal", "corner", 1)],
    "store": [("crates", "wall", 3), ("sacks", "corner", 2), ("barrels", "corner", 1)],
    "shop": [("counter", "top", 1), ("shelf", "wall", 3), ("crates", "corner", 1), ("barrels", "corner", 1)],
    "surgery": [("bed", "wall", 2), ("shelf", "wall", 2), ("table", "middle", 1), ("herbs", "wall", 1)],
    "great_hall": [("throne", "top", 1), ("table", "row", 3), ("bench", "near", 6), ("hearth", "wall", 2),
                   ("banner", "wall", 2), ("tapestry", "wall", 2), ("rug", "floor", 2)],
    "chamber": [("bed", "corner", 1), ("wardrobe", "wall", 1), ("trunk", "wall", 1), ("table", "middle", 1),
                ("rug", "floor", 1)],
    "throne": [("throne", "top", 1), ("banner", "wall", 4), ("rug", "floor", 2), ("statue_small", "corner", 2),
               ("brazier", "corner", 2)],
    "barracks": [("bed", "wall", 6), ("weapon_rack", "wall", 2), ("armour_stand", "wall", 2), ("table", "middle", 1)],
    "armoury": [("weapon_rack", "wall", 3), ("armour_stand", "wall", 3), ("crates", "corner", 1)],
    "stalls": [("haystack", "wall", 3), ("trough", "wall", 1)],
    "library": [("bookcase", "wall", 8), ("table", "row", 2), ("chair", "near", 3), ("lectern", "top", 1),
                ("candles", "corner", 1)],
    "study": [("bookcase", "wall", 2), ("table", "middle", 1), ("chair", "near", 1), ("trunk", "corner", 1)],
    "bakery": [("oven", "wall", 2), ("sacks", "corner", 2), ("table", "middle", 1), ("shelf", "wall", 1)],
    "brewery": [("cauldron", "middle", 1), ("barrels", "wall", 4), ("sacks", "corner", 1)],
    "bath": [("bath_water", "middle", 1), ("bench", "wall", 2)],
    "counting": [("counter", "top", 1), ("table", "middle", 1), ("chair", "near", 2), ("bookcase", "wall", 1)],
    "vault": [("trunk", "wall", 4)],
    "boats": [("boat", "middle", 1), ("fish_rack", "wall", 2)],
    "smoking": [("fish_rack", "wall", 3), ("hearth", "middle", 1)],
    "stage": [("pew", "row", 5)],
    "farm": [("mushrooms", "row", 10)],
    "tomb": [("tomb_slab", "row", 4), ("statue_small", "corner", 2), ("candles", "wall", 2)],
}
FLOOR_THINGS = ("rug",)  # walked on, not round
DIRS4 = ((0, -1), (1, 0), (0, 1), (-1, 0))  # north, east, south, west
SIDES = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
RING = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))  # round a square, in order
DOORS = ("door_closed", "door_open", "doorway", "gate_open")
# What a path to a door costs to lay across (0: it cannot): a bridge over water, clearing a bush or a stall.
BRIDGED = ("river", "shallow_water", "marsh_reeds", "ford", "mud")
DEEP = ("deep_water", "brine", "glow_water")


def style_for(tables, settlement) -> dict:
    """The way this settlement's people build (data/towns.json), the Heartland way for anyone not written down."""
    styles = tables.towns["styles"]
    cid = settlement.culture
    key = tables.cultures.town_style(cid) if cid in tables.cultures.ids else cid
    return styles.get(key) or styles.get(cid) or styles["heartland"]


class Plan:
    def __init__(self, b, s, style: dict) -> None:
        self.b = b
        self.s = s
        self.style = style
        self.rng = b.rng.child("town")
        self.np = self.rng.numpy("town")
        self.W, self.H = b.w, b.h
        self.used = np.zeros((b.w, b.h), bool)  # streets, squares, buildings, gardens: no new building here
        self.built = np.zeros((b.w, b.h), bool)  # buildings only
        self.street = np.zeros((b.w, b.h), bool)
        self.cx, self.cy = b.w // 2, b.h // 2
        self.lights: list[tuple[int, int]] = []
        self.size = {"hamlet": 0, "village": 1, "town": 2, "city": 3, "hold": 2, "elfhall": 1}.get(s.kind, 1)
        if getattr(s, "great", False):
            self.size = 4
        spec = b.tables.sites["settlement_types"][s.kind]
        lo, hi = spec["buildings"]
        self.target = self.rng.randint(lo, hi) * (1, 1, 2, 3, 6)[self.size] // (1 if self.size < 2 else 1)
        self.water = np.isin(b.t, [b.tid(n) for n in WATER if n in b.T])
        self.meta: dict = {}

    # ------------------------------------------------------------------ terrain
    def tid(self, name: str) -> int:
        return self.b.tid(name)

    def set(self, x: int, y: int, name: str) -> None:
        if 0 <= x < self.W and 0 <= y < self.H:
            self.b.t[x, y] = self.b.tid(name)

    def is_(self, x: int, y: int, *names: str) -> bool:
        return self.b.is_(x, y, *names)

    def inside(self, x: int, y: int, margin: int = 0) -> bool:
        return margin <= x < self.W - margin and margin <= y < self.H - margin

    def pave(self, cells, name: str, width: int = 1) -> list[tuple[int, int]]:
        """A street along cells, `width` wide: over a river or a bog it is a bridge (a ford stays a ford); it does not
        go out over the sea or a lake."""
        out = []
        lo = -(width // 2)
        for x, y in cells:
            for ix in range(lo, lo + width):
                for iy in range(lo, lo + width):
                    px, py = x + ix, y + iy
                    if not self.inside(px, py) or self.built[px, py]:
                        continue
                    if self.is_(px, py, "deep_water", "shallow_water", "glow_water", "glow_shallow", "lava", "chasm"):
                        continue
                    if self.is_(px, py, "river", "marsh_reeds"):
                        self.set(px, py, "bridge")
                    elif not self.is_(px, py, "bridge", "ford", "gate_open"):
                        self.set(px, py, name)
                    self.street[px, py] = True
                    self.used[px, py] = True
                    out.append((px, py))
        return out

    def line(self, a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
        """The squares on a straight line from a to b, each touching the last by a side (no diagonal steps)."""
        (x0, y0), (x1, y1) = a, b
        out = [(x0, y0)]
        x, y = x0, y0
        n = max(abs(x1 - x0), abs(y1 - y0))
        for i in range(1, n + 1):
            tx = round(x0 + (x1 - x0) * i / n)
            ty = round(y0 + (y1 - y0) * i / n)
            while (x, y) != (tx, ty):
                if x != tx and (y == ty or abs(tx - x) >= abs(ty - y)):
                    x += 1 if tx > x else -1
                else:
                    y += 1 if ty > y else -1
                out.append((x, y))
        return out

    def wander(self, a: tuple[int, int], b: tuple[int, int], wobble: float = 0.5) -> list[tuple[int, int]]:
        return self.b._meander(a, b, wobble)

    def disc(self, cx: float, cy: float, rx: float, ry: float | None = None) -> np.ndarray:
        ry = rx if ry is None else ry
        xs = np.arange(self.W)[:, None]
        ys = np.arange(self.H)[None, :]
        return ((xs - cx) / max(0.5, rx)) ** 2 + ((ys - cy) / max(0.5, ry)) ** 2 <= 1.0

    def open_space(self, mask: np.ndarray, name: str) -> None:
        """A square, a plaza, a green: paved (or grassed), and kept clear of buildings."""
        mask = mask & ~self.water & ~self.built
        self.b.t[mask] = self.tid(name)
        self.used |= mask
        self.street |= mask

    def thing(self, x: int, y: int, name: str, light: bool = False) -> bool:
        """Put something down (a well, a statue, a lamp post) where it shuts no way."""
        if not self.inside(x, y, 1) or self.built[x, y] or self.water[x, y] or self.is_(x, y, "bridge", "gate_open"):
            return False
        if name not in self.b.T:
            return False
        walk = self.b.tables.terrain.walk
        around = [(x + dx, y + dy) for dx, dy in DIRS4]
        if sum(1 for ax, ay in around if self.inside(ax, ay) and not walk[self.b.t[ax, ay]]) >= 2:
            return False
        if any(self.inside(ax, ay) and self.is_(ax, ay, *DOORS) for ax, ay in around):
            return False  # never in front of a door
        if not walk[self.b.tid(name)] and not self.keeps_ways(x, y):
            return False
        self.set(x, y, name)
        self.used[x, y] = True
        if light:
            self.lights.append((x, y))
        return True

    def keeps_ways(self, x: int, y: int) -> bool:
        """Could this square be filled without cutting any way through it? (The squares you can walk on round it
        must still join up round it: then any way through it can step round instead.)"""
        walk = self.b.tables.terrain.walk
        doors = {self.tid(n) for n in DOORS if n in self.b.T}
        ring = [self.inside(x + dx, y + dy) and (bool(walk[self.b.t[x + dx, y + dy]]) or int(self.b.t[x + dx, y + dy]) in doors)
                for dx, dy in RING]
        if all(ring):
            return True
        side = [i for i in (0, 2, 4, 6) if ring[i]]  # the walkable squares beside it (not the corners)
        if len(side) <= 1:
            return True
        start = ring.index(False)  # runs of walkable squares going round from a blocked one
        run, runs = -1, {}
        for k in range(1, 9):
            i = (start + k) % 8
            if ring[i]:
                if run < 0:
                    run = i
                runs[i] = run
            else:
                run = -1
        return len({runs[i] for i in side}) == 1

    # ------------------------------------------------------------------ plots
    def free(self, x: int, y: int, w: int, h: int, gap: int = 1) -> bool:
        """Room for a building here: on the map, out of the water and the streets, `gap` squares from others."""
        if x < 1 or y < 1 or x + w > self.W - 1 or y + h > self.H - 1:
            return False
        if self.used[x:x + w, y:y + h].any() or self.water[x:x + w, y:y + h].any():
            return False
        if gap:
            x0, y0 = max(0, x - gap), max(0, y - gap)
            if self.built[x0:x + w + gap, y0:y + h + gap].any():
                return False
        return True

    def facing(self, sx: int, sy: int, side: str, w: int, h: int, along: int | None = None):
        """(x, y, door) of a w x h building standing beside the street square (sx, sy) on its `side`, its door on
        the wall that faces the street."""
        dx, dy = SIDES[side]
        if along is None:
            along = (w if dx == 0 else h) // 2
        if dx == 0:  # the building is north or south of the street
            x = sx - along
            y = sy - h if dy < 0 else sy + 1
            door = (sx, sy - 1 if dy < 0 else sy + 1)
        else:
            y = sy - along
            x = sx - w if dx < 0 else sx + 1
            door = (sx - 1 if dx < 0 else sx + 1, sy)
        return x, y, door

    def along(self, cells, kinds, *, sizes=((5, 9), (4, 6)), gap: int = 1, tries: int = 6, sides=None, shape=None,
              count: int | None = None, near: tuple[int, int] | None = None) -> list[Building]:
        """Buildings along these street squares, doors onto the street, until `kinds` (or the room) runs out; from
        the squares nearest `near` outwards when it is given (a town is thickest at its heart), else anywhere.
        `kinds` is a list the caller shares: what is built is taken off it."""
        cells = list(dict.fromkeys(cells))
        if near is not None:
            nx, ny = near
            cells.sort(key=lambda c: (c[0] - nx) ** 2 + (c[1] - ny) ** 2 + self.rng.random() * 9)
        else:
            self.rng.shuffle(cells)
        out: list[Building] = []
        for sx, sy in cells:
            if not kinds or (count is not None and len(out) >= count):
                break
            if self.built[sx, sy]:
                continue
            for side in (sides or self.rng.sample(list(SIDES), 4)):
                kind = kinds[0]
                ax, ay = sx + SIDES[side][0], sy + SIDES[side][1]
                if not self.inside(ax, ay, 1) or self.used[ax, ay] or self.water[ax, ay]:
                    continue  # no open ground on this side for a door to stand in
                for shrink in (0, 1, 2):  # a smaller house where a big one will not go
                    w, h = self.size_for(kind, sizes)
                    w, h = max(4, w - shrink), max(4, h - shrink)
                    if side in ("east", "west"):
                        w, h = h, w
                    span = w if side in ("north", "south") else h
                    x, y, door = self.facing(sx, sy, side, w, h, along=self.rng.randint(1, max(1, span - 2)))
                    bld = self.raise_building(kind, x, y, w, h, door, shape=shape, gap=gap)
                    if bld is not None:
                        break
                if bld is not None:
                    out.append(bld)
                    kinds.pop(0)
                    break
        return out

    def grow(self, budget: int, ground: str, *, near: tuple[int, int] | None = None, length=(6, 16),
             turn: float = 0.1, spacing: int = 5, width: int = 1) -> list[tuple[int, int]]:
        """Side streets branching from the streets there are, until `budget` squares are laid. Each leaves a street
        at a right angle, runs on (now and then bending), and stops where it meets another street, the water, a
        building or the edge; it keeps `spacing` squares from any street beside it, so houses fit between."""
        out: list[tuple[int, int]] = []
        laid, tries = 0, 0
        # Where a street could branch: its squares with open ground beside them.
        edge = self.street & ~self.built
        open_ground = ~self.street & ~self.built & ~self.water & ~self.used
        beside_open = np.zeros_like(edge)
        beside_open[1:, :] |= open_ground[:-1, :]
        beside_open[:-1, :] |= open_ground[1:, :]
        beside_open[:, 1:] |= open_ground[:, :-1]
        beside_open[:, :-1] |= open_ground[:, 1:]
        starts = [tuple(int(v) for v in p) for p in np.argwhere(edge & beside_open)]
        while laid < budget and tries < budget * 3 + 60 and starts:
            tries += 1
            picks = [starts[self.rng.randint(0, len(starts) - 1)] for _ in range(4)]
            if near is not None:
                x, y = min(picks, key=lambda p: (p[0] - near[0]) ** 2 + (p[1] - near[1]) ** 2)
            else:
                x, y = picks[0]
            ways = [(dx, dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if self.inside(x + dx, y + dy) and open_ground[x + dx, y + dy]]
            if not ways:
                continue
            dx, dy = self.rng.choice(ways)
            path: list[tuple[int, int]] = []
            cx, cy = x, y
            for step in range(self.rng.randint(*length)):
                if step > 2 and self.rng.random() < turn:
                    dx, dy = self.rng.choice([(dy, dx), (-dy, -dx)])
                nx, ny = cx + dx, cy + dy
                if not self.inside(nx, ny, 3) or self.water[nx, ny] or self.built[nx, ny]:
                    break
                if self.street[nx, ny]:
                    if step >= 2:
                        path.append((nx, ny))  # it meets another street: joined up
                    break
                too_near = False
                if step >= 2:  # a street running alongside, too near (the street it left does not count)
                    for k in range(1, spacing + 1):
                        for sx, sy in ((nx + dy * k, ny + dx * k), (nx - dy * k, ny - dx * k)):
                            if self.inside(sx, sy) and self.street[sx, sy] and abs(sx - x) + abs(sy - y) > 3:
                                too_near = True
                if too_near:
                    break
                if self.used[nx, ny]:
                    break
                path.append((nx, ny))
                cx, cy = nx, ny
            if len(path) >= 4:
                paved = self.pave(path, ground, width)
                out += paved
                laid += len(path)
                starts += paved
                for px, py in paved:
                    open_ground[max(0, px - 1):px + 2, max(0, py - 1):py + 2] &= ~self.street[max(0, px - 1):px + 2, max(0, py - 1):py + 2]
        return out

    def size_for(self, kind: str, sizes) -> tuple[int, int]:
        (wl, wh), (hl, hh) = sizes
        big = {"temple": 1.6, "hall": 1.7, "keep": 2.0, "inn": 1.4, "library": 1.3, "warehouse": 1.3, "barracks": 1.4,
               "bathhouse": 1.4, "caravanserai": 1.8, "stable": 1.2, "bank": 1.2, "theatre": 1.6}.get(kind, 1.0)
        w = int(round(self.rng.randint(wl, wh) * big))
        h = int(round(self.rng.randint(hl, hh) * min(big, 1.5)))
        return max(4, w), max(4, h)

    # ------------------------------------------------------------------ buildings
    def look_for(self, kind: str, shape: str | None = None) -> dict:
        looks = self.style.get("look", {})
        roofs, walls, shapes = looks.get(kind) or looks.get("_") or [["thatch"], ["plaster"], ["rect"]]
        return {"roof": self.rng.choice(roofs), "walls": self.rng.choice(walls),
                "shape": shape or self.rng.choice(shapes)}

    def raise_building(self, kind: str, x: int, y: int, w: int, h: int, door: tuple[int, int], *,
                       shape: str | None = None, gap: int = 1, look: dict | None = None,
                       uses: list[str] | None = None) -> Building | None:
        """A building of this kind in the rectangle, its door at `door` (a square of its outer wall), its rooms
        `uses` if given (else what the kind has). Returns it, or None if there is no room."""
        if not self.free(x, y, w, h, gap):
            return None
        look = dict(look or self.look_for(kind, shape))
        shape = look["shape"]
        if shape == "round" and min(w, h) < 5:
            shape = look["shape"] = "rect"
        if shape == "court" and min(w, h) < 7:
            shape = look["shape"] = "rect"
        if shape == "L":
            if min(w, h) < 6 or look.get("roof") not in PITCHED:
                shape = look["shape"] = "rect"
            else:  # a corner at the back left open: the main house along the street, a wing behind it
                cw, ch = w - max(4, w // 2), h - max(4, (h + 1) // 2)
                look["cut"] = [w - cw, 0, w, ch] if self.rng.random() < 0.5 else [0, 0, cw, ch]
        dx, dy = door
        if not (x <= dx < x + w and y <= dy < y + h):
            return None
        wall = WALL_TERRAIN.get(look["walls"], "wall_wood")
        floor = FLOOR_FOR.get(kind) or self.style.get("floor", "floor_wood")
        if wall not in self.b.T:
            wall = "wall_stone"
        if floor not in self.b.T:
            floor = "floor_wood"
        cells = self._shape_cells(shape, x, y, w, h, look.get("cut"))
        inner = self._interior(cells)
        edge = cells & ~inner
        if (dx, dy) in zip(*np.nonzero(inner)):
            return None
        if not self._door_fits(edge, inner, cells, dx, dy):  # a round house: the door on its rim nearest the street
            door = self._nearest_edge(edge, inner, cells, dx, dy)
            if door is None:
                return None
            dx, dy = door
        self.b.t[edge] = self.tid(wall)
        self.b.t[inner] = self.tid(floor)
        self.set(dx, dy, "door_closed")
        self.used[x:x + w, y:y + h] = True
        self.built[cells] = True
        rooms = self._rooms(kind, shape, x, y, w, h, inner, door, wall, floor, uses, look.get("cut"))
        bld = Building(x, y, w, h, kind, door=(dx, dy), shape=shape, rooms=rooms, look=look)
        for room in rooms:
            self.furnish(bld, room)
        self.b.buildings.append(bld)
        return bld

    def _shape_cells(self, shape: str, x: int, y: int, w: int, h: int, cut=None) -> np.ndarray:
        m = np.zeros((self.W, self.H), bool)
        if shape == "L" and cut:
            m[x:x + w, y:y + h] = True
            m[x + cut[0]:x + cut[2], y + cut[1]:y + cut[3]] = False
            return m
        if shape in ("round", "tree", "mound"):
            cx, cy = x + (w - 1) / 2, y + (h - 1) / 2
            xs = np.arange(self.W)[:, None]
            ys = np.arange(self.H)[None, :]
            m = ((xs - cx) / (w / 2)) ** 2 + ((ys - cy) / (h / 2)) ** 2 <= 1.0
        else:
            m[x:x + w, y:y + h] = True
        return m

    def _interior(self, cells: np.ndarray) -> np.ndarray:
        inner = cells.copy()
        inner[1:, :] &= cells[:-1, :]
        inner[:-1, :] &= cells[1:, :]
        inner[:, 1:] &= cells[:, :-1]
        inner[:, :-1] &= cells[:, 1:]
        inner[0, :] = inner[-1, :] = False
        inner[:, 0] = inner[:, -1] = False
        return inner

    def _door_fits(self, edge, inner, cells, x: int, y: int) -> bool:
        """A door goes in the outer wall with floor straight inside it and open ground straight outside it (not where
        the rim of a round house turns a corner)."""
        if not (0 <= x < self.W and 0 <= y < self.H) or not edge[x, y]:
            return False
        near = [(x + dx, y + dy) for dx, dy in DIRS4 if self.inside(x + dx, y + dy)]
        return any(inner[c] for c in near) and any(not cells[c] for c in near)

    def _nearest_edge(self, edge, inner, cells, dx: int, dy: int) -> tuple[int, int] | None:
        pts = [(int(x), int(y)) for x, y in np.argwhere(edge) if self._door_fits(edge, inner, cells, int(x), int(y))]
        if not pts:
            return None
        return min(pts, key=lambda p: (p[0] - dx) ** 2 + (p[1] - dy) ** 2)

    def _rooms(self, kind, shape, x, y, w, h, inner, door, wall, floor, uses=None, cut=None) -> list[dict]:
        """Divide the inside into the rooms this kind of building has (inner walls with a doorway between)."""
        asked = uses is not None
        uses = list(uses) if asked else list(ROOMS.get(kind, ["hall"]))
        if shape == "L" and cut:  # the main house and its wing behind, a wall between them with a doorway
            jy = y + cut[3]
            joint = [xx for xx in range(x, x + w) if inner[xx, jy]]
            if joint:
                dx, dy = door
                by_door = [xx for xx in joint if abs(xx - dx) + abs(jy - dy) == 1]  # (never a wall inside a door)
                gap = by_door[0] if by_door else joint[len(joint) // 2]
                for xx in joint:
                    self.set(xx, jy, "doorway" if xx == gap else wall)
                inner = inner.copy()
                inner[joint, jy] = False
            front = np.zeros((self.W, self.H), bool)
            front[x:x + w, jy + 1:y + h] = True
            return [self._room(inner & front, uses[0] if uses else "hall"),
                    self._room(inner & ~front, uses[1] if len(uses) > 1 else "bedroom")]
        ix0, iy0, ix1, iy1 = x + 1, y + 1, x + w - 2, y + h - 2
        if shape in ("round", "tree", "mound") or ix1 < ix0 or iy1 < iy0:
            return [self._room(inner, uses[0] if uses else "hall")]
        if shape == "court":
            return self._court(kind, x, y, w, h, door, wall, uses)
        iw, ih = ix1 - ix0 + 1, iy1 - iy0 + 1
        rooms: list[tuple[int, int, int, int]] = [(ix0, iy0, iw, ih)]
        want = 1 if iw * ih < 16 else min(len(uses), 1 + (iw * ih >= 24) + (iw * ih >= 48) + (iw * ih >= 90))
        if asked:
            want = min(len(uses), want) if len(uses) > 1 else 1
        dx, dy = door
        while len(rooms) < want:
            rooms.sort(key=lambda r: -r[2] * r[3])
            rx, ry, rw, rh = rooms.pop(0)
            if rw >= rh and rw >= 7:  # a wall across, the bigger part where the door is
                cut = rx + (rw * 3) // 5 if abs(dx - rx) < abs(dx - (rx + rw)) else rx + (rw * 2) // 5
                if cut in (dx,):
                    cut += 1
                for yy in range(ry, ry + rh):
                    self.set(cut, yy, wall)
                gap = self.rng.randint(ry, ry + rh - 1)
                self.set(cut, gap, "doorway")
                a, b = (rx, ry, cut - rx, rh), (cut + 1, ry, rx + rw - cut - 1, rh)
            elif rh >= 7:
                cut = ry + (rh * 3) // 5 if abs(dy - ry) < abs(dy - (ry + rh)) else ry + (rh * 2) // 5
                if cut in (dy,):
                    cut += 1
                for xx in range(rx, rx + rw):
                    self.set(xx, cut, wall)
                gap = self.rng.randint(rx, rx + rw - 1)
                self.set(gap, cut, "doorway")
                a, b = (rx, ry, rw, cut - ry), (rx, cut + 1, rw, ry + rh - cut - 1)
            else:
                rooms.append((rx, ry, rw, rh))
                break
            rooms += [r for r in (a, b) if r[2] > 0 and r[3] > 0]
        # The room the street door opens into is the main one.
        def touches_door(r):
            rx, ry, rw, rh = r
            return rx - 1 <= dx <= rx + rw and ry - 1 <= dy <= ry + rh
        rooms.sort(key=lambda r: (not touches_door(r), -r[2] * r[3]))
        out = []
        for i, (rx, ry, rw, rh) in enumerate(rooms):
            m = np.zeros((self.W, self.H), bool)
            m[rx:rx + rw, ry:ry + rh] = True
            out.append(self._room(m & inner & (self.b.t != self.tid(wall)), uses[i] if i < len(uses) else "store"))
        return out

    def _room(self, mask: np.ndarray, use: str) -> dict:
        pts = np.argwhere(mask)
        if not len(pts):
            return {"x": 0, "y": 0, "w": 0, "h": 0, "use": use}
        x0, y0 = pts.min(axis=0)
        x1, y1 = pts.max(axis=0)
        return {"x": int(x0), "y": int(y0), "w": int(x1 - x0 + 1), "h": int(y1 - y0 + 1), "use": use}

    def _court(self, kind, x, y, w, h, door, wall, uses) -> list[dict]:
        """A house round a court open to the sky, with a fountain, a palm or a well in it when there is room. A big
        house has a ring of rooms round its court, a way into it from each; a small one is open all round it."""
        depth = 2 if min(w, h) < 11 else 3
        cx0, cy0, cx1, cy1 = x + 1 + depth, y + 1 + depth, x + w - 2 - depth, y + h - 2 - depth
        if cx1 - cx0 < 1 or cy1 - cy0 < 1:
            return [self._room(self._interior(self._shape_cells("rect", x, y, w, h)), uses[0] if uses else "hall")]
        mid = ((cx0 + cx1) // 2, (cy0 + cy1) // 2)
        if depth >= 3:  # the ring of rooms: a wall round the court, a doorway through it on each side
            for xx in range(cx0 - 1, cx1 + 2):
                for yy in (cy0 - 1, cy1 + 1):
                    self.set(xx, yy, wall)
            for yy in range(cy0 - 1, cy1 + 2):
                for xx in (cx0 - 1, cx1 + 1):
                    self.set(xx, yy, wall)
            for (ax, ay) in ((mid[0], cy0 - 1), (mid[0], cy1 + 1), (cx0 - 1, mid[1]), (cx1 + 1, mid[1])):
                self.set(ax, ay, "doorway")
            dx, dy = door
            if dy == y:  # the street door's passage to the court
                path = [(dx, yy) for yy in range(y + 1, cy0)]
            elif dy == y + h - 1:
                path = [(dx, yy) for yy in range(cy1 + 1, y + h - 1)]
            elif dx == x:
                path = [(xx, dy) for xx in range(x + 1, cx0)]
            else:
                path = [(xx, dy) for xx in range(cx1 + 1, x + w - 1)]
            for px, py in path:
                if self.is_(px, py, *[n for n in WALL_TERRAIN.values() if n in self.b.T]):
                    self.set(px, py, "doorway")
        for xx in range(cx0, cx1 + 1):
            for yy in range(cy0, cy1 + 1):
                self.set(xx, yy, "courtyard")
        if cx1 - cx0 >= 2 and cy1 - cy0 >= 2:  # room in the court for something in its middle
            self.set(*mid, self.rng.choice(["fountain", "palm_pot", "well"]))
        rooms = []
        wings = [(x + 1, y + 1, w - 2, depth), (x + 1, y + h - 1 - depth, w - 2, depth),
                 (x + 1, y + 1 + depth, depth, h - 2 - 2 * depth), (x + w - 1 - depth, y + 1 + depth, depth, h - 2 - 2 * depth)]
        for i, (rx, ry, rw, rh) in enumerate(wings):
            m = np.zeros((self.W, self.H), bool)
            m[rx:rx + rw, ry:ry + rh] = True
            rooms.append(self._room(m, uses[i] if i < len(uses) else ("bedroom" if kind == "house" else "store")))
        return rooms

    # ------------------------------------------------------------------ furniture
    def furnish(self, bld: Building, room: dict) -> None:
        """Put in the room what it is for, never shutting a door or a way across."""
        if room["w"] <= 0 or room["h"] <= 0:
            return
        T = self.b.tables.terrain
        rx, ry, rw, rh = room["x"], room["y"], room["w"], room["h"]
        floor_ids = {self.tid(n) for n in ("floor_wood", "floor_stone", "floor_earth", "floor_tile", "rug_floor",
                                           "hollow_floor") if n in self.b.T}
        cells = [(x, y) for x in range(rx, rx + rw) for y in range(ry, ry + rh) if int(self.b.t[x, y]) in floor_ids]
        if not cells:
            return
        cellset = set(cells)
        ways = {(x, y) for x in range(rx - 1, rx + rw + 1) for y in range(ry - 1, ry + rh + 1)
                if self.inside(x, y) and self.is_(x, y, "door_closed", "door_open", "doorway")}
        keep_clear = {(wx + dx, wy + dy) for wx, wy in ways for dx, dy in DIRS4 + ((0, 0),)}
        door_x, door_y = bld.door

        def is_edge(x, y):
            return any((x + dx, y + dy) not in cellset for dx, dy in DIRS4)

        def corner(x, y):
            return sum(1 for dx, dy in DIRS4 if (x + dx, y + dy) not in cellset) >= 2

        placed: list[tuple[int, int]] = []
        for thing, where, n in FURNISH.get(room["use"], []):
            if thing not in self.b.T:
                continue
            floor_thing = thing in FLOOR_THINGS or T.walk[self.tid(thing)]
            if where == "corner":
                options = [c for c in cells if corner(*c)]
            elif where == "wall":
                options = [c for c in cells if is_edge(*c) and not corner(*c)]
            elif where == "top":  # the wall farthest from the way in
                far = max(cells, key=lambda c: abs(c[0] - door_x) + abs(c[1] - door_y))
                options = sorted([c for c in cells if is_edge(*c)], key=lambda c: abs(c[0] - far[0]) + abs(c[1] - far[1]))[:3]
            elif where == "middle":
                mx, my = rx + rw // 2, ry + rh // 2
                options = sorted([c for c in cells if not is_edge(*c)], key=lambda c: abs(c[0] - mx) + abs(c[1] - my))[:4]
            elif where == "row":
                options = [c for c in cells if not is_edge(*c) and (c[1] - ry) % 2 == 1 and (c[0] - rx) % 3 != 2]
            elif where == "near":
                options = [(x + dx, y + dy) for x, y in placed for dx, dy in DIRS4 if (x + dx, y + dy) in cellset]
            else:  # floor
                options = [c for c in cells if not is_edge(*c)]
            options = [c for c in options if c not in keep_clear and int(self.b.t[c]) in floor_ids]
            self.rng.shuffle(options)
            got = 0
            for x, y in options:
                if got >= n:
                    break
                if int(self.b.t[x, y]) not in floor_ids:
                    continue
                old = int(self.b.t[x, y])
                self.b.t[x, y] = self.tid(thing)
                if not floor_thing and not self._open(cells, ways, floor_ids):
                    self.b.t[x, y] = old  # it would shut someone in: leave it out
                    continue
                if not floor_thing:
                    placed.append((x, y))
                got += 1

    def _open(self, cells, ways, floor_ids) -> bool:
        """Can every floor square of the room still be walked to from its ways in, and from each way to the others
        (one floor, not pockets each with a door of its own)?"""
        walk = self.b.tables.terrain.walk
        free = {c for c in cells if walk[self.b.t[c]]}
        if not free:
            return False
        starts = [(x + dx, y + dy) for x, y in ways for dx, dy in DIRS4 if (x + dx, y + dy) in free]
        if not starts:
            return False
        seen = {starts[0]}
        q = deque(starts[:1])
        while q:
            x, y = q.popleft()
            for dx, dy in DIRS4:
                n = (x + dx, y + dy)
                if n in free and n not in seen:
                    seen.add(n)
                    q.append(n)
        return len(seen) == len(free)

    # ------------------------------------------------------------------ walls round the town
    def ring_wall(self, cx: float, cy: float, rx: float, ry: float, wall: str, gates: int = 4) -> None:
        """A wall round the town (an ellipse), with gates where the streets go through it and towers now and then."""
        xs = np.arange(self.W)[:, None]
        ys = np.arange(self.H)[None, :]
        d = np.sqrt(((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2)
        ring = (d <= 1.0) & (d > 1.0 - 1.4 / max(rx, ry))
        ring &= ~self.water | np.isin(self.b.t, [self.tid(n) for n in ("bridge",) if n in self.b.T])
        for x, y in zip(*np.nonzero(ring)):
            if self.built[x, y]:
                continue
            if self.street[x, y]:
                self.set(x, y, "gate_open")
            elif not self.is_(x, y, "river", "deep_water", "ford", "bridge"):
                self.set(x, y, wall)
            self.used[x, y] = True

    # ------------------------------------------------------------------ every door reached
    def connect(self, lane: str | None = None) -> int:
        """Join every door to the heart of the town: a path (over a bridge, through a hedge or a stall) from each
        door that cannot be walked to; a building that cannot be reached at all is taken down. Returns how many were
        taken down."""
        T = self.b.tables.terrain
        t = self.b.t
        lane = lane or self.style.get("lane") or "dirt"
        door_ids = [self.tid(n) for n in DOORS if n in self.b.T]

        def walkable() -> np.ndarray:
            return T.walk[t] | np.isin(t, door_ids)

        heart = self._heart(walkable())
        if heart is None:
            return 0
        reach = self._reach(walkable(), heart)
        lost = 0
        for bld in list(self.b.buildings):
            if reach[bld.door]:
                continue
            outside = [(bld.door[0] + dx, bld.door[1] + dy) for dx, dy in DIRS4]
            outside = [c for c in outside if self.inside(*c) and not bld.contains(*c)]
            path = self._path_to(reach, outside, bld)
            if path is None:
                self._take_down(bld)
                lost += 1
                continue
            for x, y in path:
                if self.is_(x, y, *BRIDGED, *DEEP):
                    self.set(x, y, "bridge")
                    self.water[x, y] = False
                elif not T.walk[t[x, y]] and not self.is_(x, y, *DOORS):
                    self.set(x, y, lane)
                self.street[x, y] = self.used[x, y] = True
            reach = self._reach(walkable(), heart)
        return lost

    def _heart(self, walk: np.ndarray):
        """The street square nearest the middle of the town (where its main ways meet)."""
        pts = np.argwhere(self.street & walk)
        if not len(pts):
            pts = np.argwhere(walk)
            if not len(pts):
                return None
        d = (pts[:, 0] - self.cx) ** 2 + (pts[:, 1] - self.cy) ** 2
        x, y = pts[int(np.argmin(d))]
        return int(x), int(y)

    def _reach(self, walk: np.ndarray, start) -> np.ndarray:
        dist = np.full(walk.shape, 10**6, dtype=np.int32)
        dist[start] = 0
        tcod.path.dijkstra2d(dist, walk.astype(np.int32), 1, 0, out=dist)
        return dist < 10**6

    def _path_to(self, reach: np.ndarray, starts, bld) -> list[tuple[int, int]] | None:
        """The cheapest way from beside a door to where the town can be walked to, or None if there is none fit to
        lay (it would cross the open sea, a chasm, lava, or other houses)."""
        T = self.b.tables.terrain
        t = self.b.t
        cost = np.where(T.walk[t], 1, 4).astype(np.int32)  # a bush, a stall, a fence: cleared away
        cost[np.isin(t, [self.tid(n) for n in BRIDGED if n in self.b.T])] = 5
        cost[np.isin(t, [self.tid(n) for n in DEEP if n in self.b.T])] = 14
        cost[np.isin(t, [self.tid(n) for n in ("lava", "chasm", "crevasse", "cliff", "cliff_red", "falls",
                                                  "cave_wall", "ice_wall", "pyramid") if n in self.b.T])] = 0
        cost[self.built] = 0
        cost[np.isin(t, [self.tid(n) for n in DOORS if n in self.b.T])] = 1
        dist = np.full(t.shape, 10**6, dtype=np.int32)
        dist[reach] = 0
        tcod.path.dijkstra2d(dist, cost, 1, 0, out=dist)
        best = min((c for c in starts if cost[c] > 0), key=lambda c: dist[c], default=None)
        if best is None or dist[best] >= 90:
            return None
        path = tcod.path.hillclimb2d(dist, best, True, False)
        return [(int(x), int(y)) for x, y in path if not reach[int(x), int(y)]]

    def _take_down(self, bld) -> None:
        """No way to it: the building is not built after all (its plot goes back to the ground round it)."""
        T = self.b.tables.terrain
        cells = np.zeros((self.W, self.H), bool)
        for x in range(max(0, bld.x), min(self.W, bld.x + bld.w)):
            for y in range(max(0, bld.y), min(self.H, bld.y + bld.h)):
                if bld.contains(x, y):
                    cells[x, y] = True
        ring = np.zeros_like(cells)
        x0, y0 = max(0, bld.x - 1), max(0, bld.y - 1)
        ring[x0:bld.x + bld.w + 1, y0:bld.y + bld.h + 1] = True
        ring &= ~cells & T.walk[self.b.t] & ~self.street
        ids, counts = np.unique(self.b.t[ring], return_counts=True)
        ground = int(ids[np.argmax(counts)]) if len(ids) else self.tid("grass" if "grass" in self.b.T else "dirt")
        self.b.t[cells] = ground
        self.built[cells] = False
        self.used[cells] = False
        self.b.buildings.remove(bld)

    def notice_board(self) -> None:
        """The town's notice board (game/notices: work, the wanted, the news), by the street at its heart. A hamlet
        has none."""
        if self.s.kind == "hamlet" or "notice_board" not in self.b.T:
            return
        board = self.tid("notice_board")
        if (self.b.t == board).any():
            return
        T = self.b.tables.terrain
        heart = self._heart(T.walk[self.b.t] & ~self.built & ~self.water)
        if heart is None:
            return
        hx, hy = heart
        for r in range(1, 16):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = hx + dx, hy + dy
                    if not self.inside(x, y, 2) or not any(self.street[x + ox, y + oy] for ox, oy in DIRS4):
                        continue
                    if self.thing(x, y, "notice_board"):
                        return

    # ------------------------------------------------------------------ the end
    def finish(self) -> None:
        if "entry" not in self.meta:  # you come in on a street near the heart of the place, not in someone's house
            T = self.b.tables.terrain
            walk = T.walk[self.b.t] & ~self.built
            heart = self._heart(walk & ~self.water)
            if heart is not None:
                self.meta["entry"] = heart
        self.b.meta_extra = dict(self.meta)
        self.b.meta_extra["lights"] = [list(p) for p in self.lights]
