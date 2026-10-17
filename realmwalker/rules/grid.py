"""The battlefield: a grid of five-foot squares, as on a D&D battle mat, and the geometry a fight needs on it.

Distances are counted the way the Player's Handbook counts them on a grid: every square, straight or diagonal, is
five feet, so a reach of five feet means the eight squares around you. A creature takes up a block of squares by its
size: tiny, small and medium one square, large two by two, huge three by three.

Sight and cover follow the Dungeon Master's Guide grid rule. From the corner of the attacker's space that sees best,
lines are drawn to the four corners of the target's square. A line through a wall, a tree, a closed door or thick
fog is blocked; a line through a low obstacle (a boulder, a table, a fence) is hindered, and so is one through
another creature. One or two hindered lines give half cover (+2 to AC and Dexterity saves), three or four
three-quarters cover (+5); a creature gives at most half cover. When walls block all four lines from every corner,
there is no line of sight at all (total cover).

Areas (a Fireball's sphere, a Burning Hands cone, a Lightning Bolt's line, a Thunderwave's cube) are laid on the
grid from their point of origin; a square counts when its centre is inside the shape and nothing solid stands
between it and the origin.

Pure logic: arrays are indexed [x, y], like every other map in the game.
"""

from __future__ import annotations

import heapq
import math
from functools import lru_cache

import numpy as np

SQUARE_FT = 5
FOOTPRINT = {"tiny": 1, "small": 1, "medium": 1, "large": 2, "huge": 3, "gargantuan": 4}
NONE, HALF, THREE_QUARTERS, TOTAL = 0, 1, 2, 3
COVER_AC = {NONE: 0, HALF: 2, THREE_QUARTERS: 5, TOTAL: 0}
COVER_WORDS = {NONE: "", HALF: "half cover", THREE_QUARTERS: "three-quarters cover", TOTAL: "total cover"}
DIRS8 = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
CONE_HALF_ANGLE = math.atan(0.5) + 0.02  # a 5e cone is as wide at any point as it is far from its origin
EPS = 0.001  # corners are pulled this far into their square, so a line along a grid edge falls on one side of it


# ---------------------------------------------------------------------------- distances
def footprint(size: str) -> int:
    return FOOTPRINT.get(size, 1)


def cells(x: int, y: int, s: int = 1) -> list[tuple[int, int]]:
    return [(x + i, y + j) for i in range(s) for j in range(s)]


def gap(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    """Squares from one creature's space to another's (x, y, size each), as the Player's Handbook counts them:
    1 for neighbours (five feet), 0 for overlapping spaces."""
    ax, ay, asz = a
    bx, by, bsz = b
    dx = max(bx - (ax + asz - 1), ax - (bx + bsz - 1), 0)
    dy = max(by - (ay + asz - 1), ay - (by + bsz - 1), 0)
    return max(dx, dy)


def feet(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return gap(a, b) * SQUARE_FT


def centre(x: int, y: int, s: int = 1) -> tuple[float, float]:
    return x + s / 2.0, y + s / 2.0


def flanks(a: tuple[int, int, int], b: tuple[int, int, int], t: tuple[int, int, int]) -> bool:
    """The Dungeon Master's Guide's flanking rule, on the grid: two creatures flank a third when both are beside it
    and a line drawn between the centres of their spaces passes through opposite sides or opposite corners of its
    space (straight across it, or corner to corner). A large creature flanks if any one of its squares does."""
    for ca in cells(*a):
        if gap((ca[0], ca[1], 1), t) != 1:
            continue
        for cb in cells(*b):
            if gap((cb[0], cb[1], 1), t) == 1 and _across(centre(*ca), centre(*cb), t):
                return True
    return False


def _across(p: tuple[float, float], q: tuple[float, float], t: tuple[int, int, int]) -> bool:
    """The segment from p to q passes through opposite sides (or opposite corners) of the square block t."""
    x0, y0 = float(t[0]), float(t[1])
    x1, y1 = x0 + t[2], y0 + t[2]
    dx, dy = q[0] - p[0], q[1] - p[1]
    u0, u1 = 0.0, 1.0
    for d, room in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):  # Liang-Barsky
        if abs(d) < 1e-12:
            if room < 0:
                return False
            continue
        r = room / d
        if d < 0:
            u0 = max(u0, r)
        else:
            u1 = min(u1, r)
    if u0 >= u1 - 1e-9:
        return False  # it misses the block, or only touches a corner

    def sides(u: float) -> set:
        x, y = p[0] + dx * u, p[1] + dy * u
        out = set()
        if abs(x - x0) < 1e-6:
            out.add("left")
        if abs(x - x1) < 1e-6:
            out.add("right")
        if abs(y - y0) < 1e-6:
            out.add("top")
        if abs(y - y1) < 1e-6:
            out.add("bottom")
        return out

    s0, s1 = sides(u0), sides(u1)
    return bool(({"left", "right"} <= s0 | s1 and ("left" in s0) != ("left" in s1))
                or ({"top", "bottom"} <= s0 | s1 and ("top" in s0) != ("top" in s1)))


# ---------------------------------------------------------------------------- lines across the grid
@lru_cache(maxsize=400_000)
def crossed(x0: float, y0: float, x1: float, y1: float) -> tuple[tuple[int, int], ...]:
    """Every square a straight line passes through, in order (a line through the very corner of a square, as it
    passes between two others, does not count as passing through those two)."""
    cx, cy = int(math.floor(x0)), int(math.floor(y0))
    ex, ey = int(math.floor(x1)), int(math.floor(y1))
    dx, dy = x1 - x0, y1 - y0
    out = [(cx, cy)]
    if (cx, cy) == (ex, ey):
        return tuple(out)
    stepx = 1 if dx > 0 else -1
    stepy = 1 if dy > 0 else -1
    tdx = abs(1.0 / dx) if dx else math.inf
    tdy = abs(1.0 / dy) if dy else math.inf
    tmx = ((cx + (1 if stepx > 0 else 0)) - x0) / dx if dx else math.inf
    tmy = ((cy + (1 if stepy > 0 else 0)) - y0) / dy if dy else math.inf
    for _ in range(4 * (abs(ex - cx) + abs(ey - cy)) + 4):
        if (cx, cy) == (ex, ey):
            break
        if abs(tmx - tmy) < 1e-9:
            tmx += tdx
            tmy += tdy
            cx += stepx
            cy += stepy
        elif tmx < tmy:
            tmx += tdx
            cx += stepx
        else:
            tmy += tdy
            cy += stepy
        out.append((cx, cy))
    return tuple(out)


def _corners_of(x: int, y: int, s: int) -> list[tuple[float, float]]:
    """The corners of a space, pulled a hair inside it."""
    return [(x + EPS, y + EPS), (x + s - EPS, y + EPS), (x + EPS, y + s - EPS), (x + s - EPS, y + s - EPS)]


# ---------------------------------------------------------------------------- the field
class Field:
    """The ground a fight happens on: what each square is, and what that means for moving, seeing and cover.

    terrain: [x, y] indices into the current terrain table (data/local_terrain.json). Squares that cannot be walked
    on but can be seen past (boulders, tables, fences, wells, carts) are low obstacles that give half cover;
    squares that cannot be seen past (walls, tree trunks, closed doors) block sight. A closed (unlocked) door opens
    as somebody walks through it. Terrain that costs half again as much to cross or more (mud, deep snow, brush,
    shallow water, rubble) is difficult terrain: every square of it costs ten feet of movement instead of five.
    Squares at the edge of the field that can be walked on lead away from the fight. Low things tagged "climb" (a
    fence, a table, barrels) can be clambered onto and over, and deep water tagged "swim" swum, each foot costing a
    foot more (2024 Climbing, Swimming); water tagged "flowing" is rough water. What is not solid can be leapt over
    (`leap`: the ground, water, chasms, fire and the low things one could climb).
    """

    def __init__(self, tables, terrain: np.ndarray, *, kind: str = "wilderness", style: str = "", key: str = "battle",
                 base_light: float = 1.0, indoors: bool = False, underground: bool = False, ground: str = "",
                 lights: list | None = None, origin: tuple[int, int] = (0, 0)) -> None:
        self.t = tables
        self.terrain = np.ascontiguousarray(np.asarray(terrain, dtype=np.uint16))
        self.width, self.height = self.terrain.shape
        self.kind = kind
        self.style = style
        self.key = key
        self.base_light = float(base_light)
        self.indoors = indoors
        self.underground = underground
        self.ground = ground
        self.lights = list(lights or [])  # fixed lights: (x, y, radius in squares) - hearths, campfires
        self.origin = origin  # where the field's (0, 0) lies on the close-up map it was cut from
        self.version = 0
        self.zone_opaque = np.zeros((self.width, self.height), dtype=bool)  # fog and darkness laid by spells
        self.zone_difficult = np.zeros((self.width, self.height), dtype=bool)  # webs, ice, the press of guardians
        self._derive()

    # ------------------------------------------------------------------ what each square is
    def _derive(self) -> None:
        T = self.t.terrain
        idx = self.terrain
        n = len(T.ids)
        tag = lambda name: np.array([name in T.tags[i] for i in range(n)], dtype=bool)  # noqa: E731
        water, door, locked, opened = tag("water"), tag("door"), tag("locked"), tag("open")
        walk = T.walk[idx].copy()
        see = T.see[idx]
        self.openable = (door & ~locked & ~opened)[idx]
        self.walk = walk | self.openable
        self.solid = ~see  # blocks sight and gives total cover
        self.low = ~T.walk[idx] & see & ~water[idx] & ~self.openable  # low obstacles: half cover
        self.rough = T.cost[idx] >= 1.5  # difficult terrain by nature
        self.water = water[idx]
        self.fly = (self.walk | self.water | self.low) & ~self.solid  # over water and low things, not through walls
        self.climb = (tag("climb") & ~T.walk & T.see)[idx]  # clambered onto and over (a fence, a table, barrels)
        self.swim = (tag("swim") & ~T.walk)[idx]  # deep water, swum
        self.rough_water = self.swim & tag("flowing")[idx]  # a river's current
        self.leap = (self.walk | self.water | self.climb | (tag("chasm") | tag("fire") | tag("hot"))[idx]) & ~self.solid
        self.hiding = tag("cover")[idx]  # brush, tall grass, reeds: somewhere to hide
        self.tree = tag("tree")[idx]  # a living tree or a dead one (Tree Stride steps from one to another)
        flammable = np.array([T.ids[i] in FLAMMABLE for i in range(n)], dtype=bool)
        self.flammable = flammable[idx]
        edge = np.zeros_like(self.walk)
        edge[0, :] = edge[-1, :] = True
        edge[:, 0] = edge[:, -1] = True
        self.exits = edge & self.walk
        self._refresh()

    def _refresh(self) -> None:
        """Fast lookups for the line-of-sight code (plain lists index far faster than numpy one square at a time)."""
        opaque = self.solid | self.zone_opaque
        self._opaque = opaque.tolist()
        self._solid = self.solid.tolist()
        self._low = self.low.tolist()
        self.version += 1
        self._sight_cache: dict = {}

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def name(self, x: int, y: int) -> str:
        return self.t.terrain.ids[int(self.terrain[x, y])]

    def describe(self, x: int, y: int) -> str:
        return self.t.terrain[int(self.terrain[x, y])]["name"]

    def difficult(self, x: int, y: int) -> bool:
        return bool(self.rough[x, y] or self.zone_difficult[x, y])

    def passable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and bool(self.walk[x, y])

    def fits(self, x: int, y: int, s: int = 1) -> bool:
        """A creature of this many squares could stand here (the terrain allows it; who else is here is not asked)."""
        if x < 0 or y < 0 or x + s > self.width or y + s > self.height:
            return False
        return bool(self.walk[x:x + s, y:y + s].all())

    def set_terrain(self, x: int, y: int, name: str) -> None:
        """A door opens, the ground changes: everything derived is worked out again."""
        self.terrain[x, y] = self.t.terrain.index[name]
        self._derive()

    def open_door(self, x: int, y: int) -> bool:
        if self.in_bounds(x, y) and self.openable[x, y] and "door_open" in self.t.terrain.index:
            self.set_terrain(x, y, "door_open")
            return True
        return False

    def set_zones(self, opaque: np.ndarray, difficult: np.ndarray) -> None:
        changed = not np.array_equal(opaque, self.zone_opaque)
        self.zone_opaque = opaque
        self.zone_difficult = difficult
        if changed:
            self._refresh()

    # ------------------------------------------------------------------ sight and cover
    def line_clear(self, x0: float, y0: float, x1: float, y1: float, skip: set | None = None, *,
                   terrain_only: bool = False) -> bool:
        """Nothing solid stands on the line (the squares at either end, and any in `skip`, are not asked). Fog
        hides what is beyond it but stops nothing: `terrain_only` asks only about walls."""
        squares = crossed(x0, y0, x1, y1)
        op = self._solid if terrain_only else self._opaque
        for sq in squares[1:-1]:
            if skip and sq in skip:
                continue
            if op[sq[0]][sq[1]]:
                return False
        return True

    def cover(self, att: tuple[int, int, int], tgt: tuple[int, int, int], creatures: dict | None = None) -> int:
        """The target's cover against the attacker (x, y, size each): NONE, HALF, THREE_QUARTERS or TOTAL.
        `creatures` maps squares to whoever stands there (the attacker and the target are left out of it)."""
        key = (att, tgt)
        terrain = self._sight_cache.get(key)
        if terrain is None:
            terrain = self._terrain_lines(att, tgt)
            self._sight_cache[key] = terrain
        best = TOTAL
        own = set(cells(*att)) | set(cells(*tgt))
        for (walls, hindered, lines) in terrain:
            if walls == 4:
                continue
            # Walls in the way give cover by how much of the target they hide; a low obstacle or a creature can
            # only ever give half cover (the Player's Handbook's low wall, piece of furniture, narrow trunk).
            level = NONE if walls == 0 else (HALF if walls <= 2 else THREE_QUARTERS)
            if hindered > walls:
                level = max(level, HALF)
            if creatures and level < HALF:
                for squares in lines:
                    if any(sq in creatures and sq not in own for sq in squares):
                        level = HALF
                        break
            best = min(best, level)
            if best == NONE:
                break
        return best

    def _terrain_lines(self, att, tgt) -> list[tuple[int, int, list]]:
        """For each corner of the attacker and each square of the target: how many of the four lines walls block,
        how many any obstacle hinders, and the squares the open lines cross (for the creatures in the way)."""
        ax, ay, asz = att
        tx, ty, tsz = tgt
        op, low = self._opaque, self._low
        own = set(cells(ax, ay, asz)) | set(cells(tx, ty, tsz))
        out = []
        for (cx, cy) in _corners_of(ax, ay, asz):
            for (sx, sy) in cells(tx, ty, tsz):
                walls = hindered = 0
                lines = []
                for (qx, qy) in _corners_of(sx, sy, 1):
                    squares = [sq for sq in crossed(round(cx, 4), round(cy, 4), round(qx, 4), round(qy, 4))
                               if sq not in own]
                    if any(op[x][y] for x, y in squares):
                        walls += 1
                        hindered += 1
                    elif any(low[x][y] for x, y in squares):
                        hindered += 1
                        lines.append(squares)
                    else:
                        lines.append(squares)
                out.append((walls, hindered, lines))
        return out

    def sees(self, att: tuple[int, int, int], tgt: tuple[int, int, int]) -> bool:
        """A line of sight between two spaces (light aside)."""
        return self.cover(att, tgt) != TOTAL

    # ------------------------------------------------------------------ areas
    def area(self, shape: str, size_ft: int, *, origin: tuple[int, int, int], toward: tuple[int, int],
             from_self: bool = False) -> list[tuple[int, int]]:
        """The squares an area of effect covers. origin is the caster's space (x, y, size); toward is the square
        aimed at: the centre of a sphere, cylinder or cube laid at a point, or the direction of a cone, a line, or a
        cube that starts at the caster's side (from_self)."""
        n = max(1, int(size_ft) // SQUARE_FT)
        ox, oy, osz = origin
        tx, ty = toward
        out: list[tuple[int, int]] = []
        own = set(cells(ox, oy, osz))
        if shape == "emanation":  # reaching out from every side of the one it comes from, who is not in it (2024)
            ocx, ocy = centre(ox, oy, osz)
            for x in range(max(0, ox - n), min(self.width, ox + osz + n)):
                for y in range(max(0, oy - n), min(self.height, oy + osz + n)):
                    if (x, y) not in own and gap((x, y, 1), origin) <= n and self._reaches(ocx, ocy, x, y):
                        out.append((x, y))
            return out
        if shape in ("sphere", "cylinder", "radius"):
            cx, cy = tx + 0.5, ty + 0.5
            for x in range(max(0, tx - n), min(self.width, tx + n + 1)):
                for y in range(max(0, ty - n), min(self.height, ty + n + 1)):
                    if (x - tx) ** 2 + (y - ty) ** 2 <= n * (n + 1) and self._reaches(cx, cy, x, y):
                        out.append((x, y))
            return out
        if shape == "cube" and not from_self:
            x0, y0 = tx - (n - 1) // 2, ty - (n - 1) // 2
            for x in range(x0, x0 + n):
                for y in range(y0, y0 + n):
                    if self.in_bounds(x, y) and self._reaches(tx + 0.5, ty + 0.5, x, y):
                        out.append((x, y))
            return out
        ocx, ocy = centre(ox, oy, osz)
        vx, vy = tx + 0.5 - ocx, ty + 0.5 - ocy
        length = math.hypot(vx, vy)
        if length < 1e-6:
            return []
        ux, uy = vx / length, vy / length
        if shape == "cube":  # a cube that starts at the caster's side and reaches out (Thunderwave)
            sx = 0 if abs(ux) < 0.38 else (1 if ux > 0 else -1)
            sy = 0 if abs(uy) < 0.38 else (1 if uy > 0 else -1)
            x0 = ox + osz if sx > 0 else (ox - n if sx < 0 else ox - (n - osz) // 2)
            y0 = oy + osz if sy > 0 else (oy - n if sy < 0 else oy - (n - osz) // 2)
            for x in range(x0, x0 + n):
                for y in range(y0, y0 + n):
                    if self.in_bounds(x, y) and (x, y) not in own and self._reaches(ocx, ocy, x, y):
                        out.append((x, y))
            return out
        reach = n + osz / 2.0
        for x in range(max(0, int(ocx - reach - 1)), min(self.width, int(ocx + reach + 2))):
            for y in range(max(0, int(ocy - reach - 1)), min(self.height, int(ocy + reach + 2))):
                if (x, y) in own:
                    continue
                px, py = x + 0.5 - ocx, y + 0.5 - ocy
                along = px * ux + py * uy
                if along <= 0:
                    continue
                if shape == "cone":
                    dist = math.hypot(px, py)
                    if dist > reach + 0.01:
                        continue
                    if math.acos(max(-1.0, min(1.0, along / max(dist, 1e-6)))) > CONE_HALF_ANGLE:
                        continue
                else:  # a line five feet wide
                    if along > reach + 0.01 or abs(px * uy - py * ux) > 0.55:
                        continue
                if self._reaches(ocx, ocy, x, y):
                    out.append((x, y))
        return out

    def _reaches(self, cx: float, cy: float, x: int, y: int) -> bool:
        """An area spreads from its origin to this square without passing through anything solid."""
        if not self.in_bounds(x, y) or self._solid[x][y]:
            return False
        if int(math.floor(cx)) == x and int(math.floor(cy)) == y:
            return True
        return self.line_clear(round(cx, 4), round(cy, 4), x + 0.5, y + 0.5, terrain_only=True)

    # ------------------------------------------------------------------ light
    def light_map(self, carried: list[tuple[int, int, float]]) -> np.ndarray:
        """How lit each square is (0 dark .. 1 daylight): the day (or the dark under the ground), hearths and fires
        on the field, and the lights people carry: (x, y, radius in squares). Bright within the radius, dim for a
        few squares beyond it."""
        L = np.full((self.width, self.height), self.base_light, dtype=np.float32)
        xs = np.arange(self.width, dtype=np.float32)[:, None]
        ys = np.arange(self.height, dtype=np.float32)[None, :]
        for (lx, ly, r) in list(self.lights) + list(carried):
            if r <= 0:
                continue
            d = np.maximum(np.abs(xs - lx), np.abs(ys - ly))
            lit = np.where(d <= r, 1.0, np.where(d <= r + max(2, r // 2), 0.45, 0.0)).astype(np.float32)
            np.maximum(L, lit, out=L)
        return L


# What catches fire when fire falls on it.
FLAMMABLE = {"grass", "tall_grass", "heather", "leaf_litter", "needles", "bush", "crops", "haystack", "woodpile",
             "marsh_reeds", "dead_tree", "bedroll", "garden"}

BRIGHT, DIM = 0.6, 0.25  # light at or above which a square is in bright light, dim light


def light_word(level: float) -> str:
    return "bright" if level >= BRIGHT else ("dim" if level >= DIM else "dark")


# ---------------------------------------------------------------------------- moving
class Step:
    __slots__ = ("cost", "prev", "provokes", "risk")

    def __init__(self, cost: int, prev, provokes: frozenset, risk: float) -> None:
        self.cost = cost
        self.prev = prev
        self.provokes = provokes
        self.risk = risk


def step_feet(field: Field, entering, *, crawling: bool = False, flying: bool = False, climber: bool = False,
              swimmer: bool = False) -> int:
    """What stepping into these squares costs, in feet (2024): 5; 10 in difficult terrain or crawling; climbing onto a
    low thing or swimming costs a foot more for every foot (two more in difficult terrain), unless one has a Climb or
    Swim Speed. A flier is slowed only by what is in the air (webs, spirits)."""
    rough = any(field.zone_difficult[c] if flying else (field.rough[c] or field.zone_difficult[c]) for c in entering)
    feet = 10 if crawling or rough else 5
    if not flying and any((field.climb[c] and not climber) or (field.swim[c] and not swimmer) for c in entering):
        feet += 5  # (in difficult terrain that makes three feet for every foot, as the book says)
    return feet


def paths(field: Field, start: tuple[int, int], size: int, budget: int, *, blocked: set, occupied: set,
          threats: list[tuple[int, tuple[int, int, int], int]] = (), risk: float = 0.5, crawling: bool = False,
          hazard: set | None = None, hazard_risk: float = 10.0, flying: bool = False, climber: bool = False,
          swimmer: bool = False, jump: tuple[int, int] = (0, 0), through: set | None = None) -> dict[tuple[int, int], Step]:
    """Every square a creature could move to with `budget` feet of movement, with the cheapest way there.

    blocked: squares it cannot pass (enemies stand there); occupied: squares it may pass but not stop on (friends,
    the fallen). threats: (who, their space, their reach in squares) for opportunity attacks: leaving a square
    within someone's reach for one outside it provokes them. Paths that provoke, or cross a hazard (fire), are
    avoided when one as cheap exists (each costs `risk` or `hazard_risk` feet in the choosing, not in the moving).
    Difficult terrain (and crawling) costs ten feet a square instead of five; climbing and swimming cost more
    (`step_feet`). A flier goes over water and low things and is not slowed by the ground (only by what is in the
    air: webs, spirits). On foot, `jump` (feet: standing, after a run of 10 feet) lets it leap over what it cannot
    or would rather not walk - water, a chasm, a fire, a fence - landing on the ground beyond (2024 Long Jump: each
    foot costs a foot; clearing a low thing takes an Athletics check, landing on difficult ground an Acrobatics one,
    so those leaps are chosen warily). The way found to a square has the leap's landing after its take-off.
    `through`: squares to plan as if they were open (a door or a barricade to be broken down on the way).
    """
    sx, sy = start
    best: dict[tuple[int, int], Step] = {(sx, sy): Step(0, None, frozenset(), 0.0)}
    heap = [(0.0, 0, sx, sy)]
    W, H = field.width, field.height
    walk = field.fly if flying else (field.walk | field.climb | field.swim)
    if through:
        walk = walk.copy()
        for c in through:
            walk[c] = True
    rough = field.zone_difficult if flying else field.rough | field.zone_difficult
    hard_going = [] if flying else [m for m, easy in ((field.climb, climber), (field.swim, swimmer)) if not easy]
    labour = np.logical_or.reduce(hard_going) if hard_going else None  # climbing, swimming without the speed for it
    if labour is not None and not labour.any():
        labour = None
    rapids = None if flying or swimmer or not field.rough_water.any() else field.rough_water
    leaping = not flying and jump[0] >= SQUARE_FT and size == 1
    while heap:
        key, cost, x, y = heapq.heappop(heap)
        node = best.get((x, y))
        if node is None or node.cost != cost or key > node.cost + node.risk + 1e-6:
            continue
        here = (x, y, size)
        reach_now = [(fid, sp, r) for fid, sp, r in threats if gap(here, sp) <= r]
        for dx, dy in DIRS8:
            nx, ny = x + dx, y + dy
            if nx < 0 or ny < 0 or nx + size > W or ny + size > H:
                continue
            if not walk[nx:nx + size, ny:ny + size].all():
                continue
            if dx and dy and size == 1 and not walk[x + dx, y] and not walk[x, y + dy]:
                continue  # no squeezing between two walls at their corners
            new = [(cx, cy) for cx in range(nx, nx + size) for cy in range(ny, ny + size)]
            if any(c in blocked for c in new):
                continue
            entering = [c for c in new if not (x <= c[0] < x + size and y <= c[1] < y + size)] or new
            hard = any(rough[c] for c in entering)
            step = 10 if crawling or hard else 5
            if labour is not None and any(labour[c] for c in entering):
                step += 5  # climbing, swimming (step_feet)
            ncost = cost + step
            if ncost > budget:
                continue
            provokes = node.provokes
            there = (nx, ny, size)
            left = [fid for fid, sp, r in reach_now if gap(there, sp) > r and fid not in provokes]
            if left:
                provokes = provokes | frozenset(left)
            nrisk = node.risk + risk * len(left)
            if hazard and any(c in hazard for c in entering):
                nrisk += hazard_risk
            if rapids is not None and any(rapids[c] for c in entering):
                nrisk += LEAP_RISK  # an Athletics check against the current
            old = best.get((nx, ny))
            if old is not None and old.cost + old.risk <= ncost + nrisk:
                continue
            best[(nx, ny)] = Step(ncost, (x, y), provokes, nrisk)
            heapq.heappush(heap, (ncost + nrisk, ncost, nx, ny))
        if leaping:
            _leaps(field, x, y, node, cost, jump, budget, blocked, reach_now, risk, hazard, best, heap)
    return best


LEAP_RISK = 8.0  # what a check that could fail is worth avoiding, in feet, in the choosing (not in the moving): a
# sure climb over a fence is chosen before a leap that could fall short


def _leaps(field: Field, x: int, y: int, node: Step, cost: int, jump: tuple[int, int], budget: int, blocked: set,
           reach_now: list, risk: float, hazard: set | None, best: dict, heap: list) -> None:
    """Leaps from (x, y): over one square or more that cannot (or should not) be walked, onto the ground beyond. A run
    of 10 feet on this move before it gives the full Strength score in feet, else half (2024 Long Jump). The leap is
    the whole way from here to where it lands, each foot costing a foot: clearing one square takes a 10-foot leap."""
    walk, leap, rough, low = field.walk, field.leap, field.rough, field.climb
    feet = jump[1] if cost >= 10 else jump[0]
    longest = feet // SQUARE_FT
    W, H = field.width, field.height
    for dx, dy in DIRS8:
        first = (x + dx, y + dy)
        if not (0 <= first[0] < W and 0 <= first[1] < H) or not leap[first] or first in blocked:
            continue
        if walk[first] and not rough[first] and not field.zone_difficult[first] and not (hazard and first in hazard):
            continue  # plain ground: a step there and a leap from it is never worse
        over_low = False
        for k in range(1, longest):  # k squares cleared, k + 1 squares moved
            sq = (x + dx * k, y + dy * k)
            if not (0 <= sq[0] < W and 0 <= sq[1] < H) or not leap[sq] or sq in blocked:
                break
            over_low = over_low or bool(low[sq])
            land = (x + dx * (k + 1), y + dy * (k + 1))
            if not (0 <= land[0] < W and 0 <= land[1] < H) or not walk[land] or land in blocked:
                continue
            if hazard and land in hazard:
                continue
            ncost = cost + (k + 1) * SQUARE_FT
            if ncost > budget:
                break
            there = (land[0], land[1], 1)
            left = [fid for fid, sp, r in reach_now if gap(there, sp) > r and fid not in node.provokes]
            provokes = node.provokes | frozenset(left) if left else node.provokes
            nrisk = node.risk + risk * len(left) + (LEAP_RISK if over_low else 0.0) \
                + (LEAP_RISK if rough[land] or field.zone_difficult[land] else 0.0) + 0.5  # (a step is surer)
            old = best.get(land)
            if old is not None and old.cost + old.risk <= ncost + nrisk:
                continue
            best[land] = Step(ncost, (x, y), provokes, nrisk)
            heapq.heappush(heap, (ncost + nrisk, ncost, land[0], land[1]))


def route(tree: dict[tuple[int, int], Step], goal: tuple[int, int]) -> list[tuple[int, int]]:
    """The squares from the start (not included) to the goal, along the cheapest way found."""
    if goal not in tree:
        return []
    out = []
    sq = goal
    while sq is not None and tree[sq].prev is not None:
        out.append(sq)
        sq = tree[sq].prev
    out.reverse()
    return out


def can_stop(sq: tuple[int, int], size: int, occupied: set) -> bool:
    return not any(c in occupied for c in cells(sq[0], sq[1], size))
