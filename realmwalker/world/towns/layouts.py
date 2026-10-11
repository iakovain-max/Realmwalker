"""The plans of towns, one for each way of building (data/towns.json "layout"). Each takes a Plan (plan.py) and lays
out its streets, squares and buildings; the shared work (the market square's things, the buildings along the
streets, walls, fields, the things by the doors, lamps) is done by the helpers at the top.
"""

from __future__ import annotations

import math

import numpy as np

from realmwalker.world.model import DIRS
from realmwalker.world.towns.plan import Plan

SPECIAL = {
    "hamlet": [],
    "village": ["inn", "temple", "store", "smithy"],
    "town": ["inn", "inn", "temple", "smithy", "hall", "store", "healer", "stable"],
    "city": ["inn", "inn", "inn", "temple", "temple", "smithy", "smithy", "hall", "keep", "store", "store", "healer",
             "stable"],
    "hold": ["hall", "smithy", "smithy", "temple", "inn", "store"],
    "elfhall": ["hall", "temple", "healer"],
}


# ---------------------------------------------------------------------------- shared
def kinds(plan: Plan) -> list[str]:
    """What is to be built: the special buildings first, this people's own in bigger places, then homes."""
    s = plan.s
    out = list(SPECIAL.get(s.kind, []))
    extra = plan.style.get("extra", [])
    if plan.size >= 2 and extra:
        out += extra[: 1 + plan.size]
    if plan.size >= 4:  # a great city has more of everything
        out += ["inn", "inn", "temple", "store", "store", "smithy", "healer", "warehouse", "barracks"] + list(extra)
    return out + ["house"] * max(0, plan.target - len(out))


def road_ends(plan: Plan) -> list[tuple[int, int]]:
    """Where the roads come in at the edge of the map (from the roads on the big map), at least two."""
    b = plan.b
    w = b.world
    ends = []
    for d in (1, 3, 5, 7):  # roads come in through the four sides
        dx, dy = DIRS[d]
        nx, ny = b.ox + dx, b.oy + dy
        if w.in_bounds(nx, ny) and w.road[nx, ny]:
            ends.append(b._edge_point(d, 0.5))
    for d in (3, 7, 1, 5):
        if len(ends) >= 2:
            break
        p = b._edge_point(d, 0.5)
        if p not in ends:
            ends.append(p)
    return ends


def centre(plan: Plan, jitter: int = 3) -> tuple[int, int]:
    """The middle of the town: near the map's middle, on dry land."""
    for _ in range(40):
        x = plan.cx + plan.rng.randint(-jitter, jitter)
        y = plan.cy + plan.rng.randint(-jitter, jitter)
        if not plan.water[max(0, x - 2):x + 3, max(0, y - 2):y + 3].any():
            return x, y
    return plan.cx, plan.cy


def square(plan: Plan, cx: int, cy: int, rx: float, ry: float, ground: str) -> np.ndarray:
    mask = plan.disc(cx, cy, rx, ry)
    plan.open_space(mask, ground)
    return mask


def square_things(plan: Plan, mask: np.ndarray, cx: int, cy: int) -> None:
    """The middle of the place: its well or fountain, its stalls, a statue, lamps round the edge."""
    things = list(plan.style.get("square", ["well"]))
    if not things:
        return
    first = things[0]
    plan.thing(cx, cy, first, light=first in ("brazier", "fire_pit"))
    cells = [tuple(int(v) for v in c) for c in np.argwhere(mask)]
    plan.rng.shuffle(cells)
    stalls = sum(1 for t in things if "stall" in t)
    n_stalls = {0: 0, 1: 1, 2: 4, 3: 8, 4: 14}[plan.size] if stalls else 0
    others = [t for t in things[1:] if "stall" not in t]
    placed = 0
    for x, y in cells:
        if placed >= n_stalls:
            break
        if abs(x - cx) + abs(y - cy) < 3:
            continue
        if plan.thing(x, y, plan.rng.choice([t for t in things if "stall" in t])):
            placed += 1
    for t in others:
        for x, y in cells:
            if abs(x - cx) + abs(y - cy) >= 3 and plan.thing(x, y, t, light=t in ("lamp_post", "brazier", "lantern_post")):
                cells.remove((x, y))
                break


def street_lights(plan: Plan, cells, every: int = 7) -> None:
    light = plan.style.get("light")
    if not light or light not in plan.b.T or plan.size < 2:
        return
    cells = list(dict.fromkeys(cells))
    most = (0, 0, 10, 24, 48)[plan.size]
    lit = 0
    for i, (x, y) in enumerate(cells):
        if i % every or lit >= most:
            continue
        lit += 1
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nx, ny = x + dx, y + dy
            if plan.inside(nx, ny, 1) and not plan.used[nx, ny] and not plan.water[nx, ny]:
                if plan.thing(nx, ny, light, light=True):
                    break


def nearest_way(plan: Plan, x: int, y: int, least: int = 4) -> tuple[int, int]:
    """The nearest street, track or square to (x, y) at least `least` squares off (to lead a new way to)."""
    pts = np.argwhere(plan.street & ~plan.built)
    if not len(pts):
        return plan.cx, plan.cy
    d = (pts[:, 0] - x) ** 2 + (pts[:, 1] - y) ** 2
    d = np.where(d < least * least, 10**9, d)
    px, py = pts[int(np.argmin(d))]
    return int(px), int(py)


def lanes(plan: Plan, n: int, starts, ground: str, length=(8, 22), turn: float = 0.25) -> list[tuple[int, int]]:
    """Alleys branching off the streets, wandering a little, now and then turning."""
    out = []
    starts = list(starts)
    if not starts:
        return out
    for _ in range(n):
        x, y = plan.rng.choice(starts)
        dx, dy = plan.rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        steps = plan.rng.randint(*length)
        path = []
        for _s in range(steps):
            if plan.rng.random() < turn:
                dx, dy = plan.rng.choice([(dy, dx), (-dy, -dx)])
            nx, ny = x + dx, y + dy
            if not plan.inside(nx, ny, 3) or plan.built[nx, ny] or plan.water[nx, ny]:
                break
            x, y = nx, ny
            path.append((x, y))
        out += plan.pave(path, ground, 1)
    return out


def finish_town(plan: Plan, streets, *, walled_with: str | None = None, fields: bool = True) -> None:
    """What every town has round its buildings: things by the doors, lamps, walls, fields and a graveyard."""
    b, s = plan.b, plan.s
    for bld in b.buildings:
        if bld.shape not in ("carved",):
            b._yard(bld, s.kind)
    street_lights(plan, streets, every=9 if plan.size >= 3 else 12)
    things = plan.style.get("street_things", [])
    if things:
        open_cells = [tuple(int(v) for v in c) for c in np.argwhere(plan.street & ~plan.built)]
        plan.rng.shuffle(open_cells)
        for x, y in open_cells[: max(2, len(open_cells) // 60)]:
            # Beside the street, not in it: on the ground next to it.
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nx, ny = x + dx, y + dy
                if plan.inside(nx, ny, 1) and not plan.used[nx, ny] and not plan.water[nx, ny]:
                    plan.thing(nx, ny, plan.rng.choice(things))
                    break
    built = np.argwhere(plan.built)
    if not len(built):
        return
    x0, y0 = built.min(axis=0)
    x1, y1 = built.max(axis=0)
    if s.walled and walled_with:  # round the heart of the place; the newest houses may stand outside it
        qx0, qy0 = np.percentile(built, 12, axis=0)
        qx1, qy1 = np.percentile(built, 88, axis=0)
        cx, cy = (qx0 + qx1) / 2, (qy0 + qy1) / 2
        plan.ring_wall(cx, cy, (qx1 - qx0) / 2 + 4, (qy1 - qy0) / 2 + 4, walled_with)
    if fields and s.kind in ("hamlet", "village"):
        b._fields(int(x0), int(y0), int(x1), int(y1))
    if s.kind in ("village", "town", "city"):
        b._graveyard(int(x0), int(y0), int(x1), int(y1))
    trees = [t for t in plan.style.get("trees", []) if t in b.T]
    if trees:
        ground = [tuple(int(v) for v in c) for c in np.argwhere(~plan.used & ~plan.water)]
        plan.rng.shuffle(ground)
        for x, y in ground[: max(4, len(ground) // 120)]:
            if x0 - 2 <= x <= x1 + 2 and y0 - 2 <= y <= y1 + 2:
                plan.thing(x, y, plan.rng.choice(trees))


def specials_by(plan: Plan, cells, kinds_left: list[str], near: tuple[int, int], **kw) -> None:
    """The special buildings first, as near the middle as they will go."""
    near_first = sorted(set(cells), key=lambda c: (c[0] - near[0]) ** 2 + (c[1] - near[1]) ** 2)
    while kinds_left and kinds_left[0] != "house":
        kind = kinds_left[0]
        got = plan.along(near_first[: max(40, len(near_first) // 3)], [kind], **kw)
        if not got:
            got = plan.along(near_first, [kind], **kw)
        kinds_left.pop(0)  # placed, or no room for it anywhere


# ---------------------------------------------------------------------------- organic: roads in, a market square
def organic(plan: Plan) -> None:
    st = plan.style
    cx, cy = centre(plan)
    width = 1 if plan.size <= 1 else (2 if plan.size <= 3 else 3)
    mains = []
    for end in road_ends(plan):
        mains += plan.pave(plan.wander(end, (cx, cy), 0.45), st["street"], width)
    r = (2.5, 4, 6, 8, 11)[plan.size]
    sq = square(plan, cx, cy, r, r * 0.7, st.get("plaza", st["street"]))
    square_things(plan, sq, cx, cy)
    todo = kinds(plan)
    rim = [tuple(int(v) for v in c) for c in np.argwhere(sq)]
    specials_by(plan, rim + mains, todo, (cx, cy), gap=1)
    side: list[tuple[int, int]] = []
    for _round in range(4):  # side streets, and houses along them, until the town is the size it should be
        side += plan.grow(len(todo) * 6 + 10, st["lane"], near=(cx, cy), length=(6, 12 + 3 * plan.size))
        plan.along(rim + mains + side, todo, gap=1, near=(cx, cy))
        if not todo:
            break
    finish_town(plan, mains, walled_with=st.get("wall") if plan.size >= 2 else st.get("palisade"))


# ---------------------------------------------------------------------------- grid: planned blocks round a square
def grid(plan: Plan) -> None:
    st = plan.style
    cx, cy = centre(plan, 2)
    bw, bh = plan.rng.randint(12, 15), plan.rng.randint(9, 11)
    margin = 4
    blocks = max(4, plan.target // 4 + 2)  # about four houses to a block, and room for the piazza
    half_x = int(math.ceil(math.sqrt(blocks * 1.5) / 2)) + 1
    half_y = int(math.ceil(math.sqrt(blocks / 1.5) / 2)) + 1
    xs = [x for x in range(cx - half_x * bw, cx + half_x * bw + 1, bw) if margin <= x < plan.W - margin]
    ys = [y for y in range(cy - half_y * bh, cy + half_y * bh + 1, bh) if margin <= y < plan.H - margin]
    if not xs or not ys:
        return organic(plan)
    streets = []
    for x in xs:
        streets += plan.pave(plan.line((x, ys[0]), (x, ys[-1])), st["street"], 2 if x == cx else 1)
    for y in ys:
        streets += plan.pave(plan.line((xs[0], y), (xs[-1], y)), st["street"], 2 if y == cy else 1)
    for end in road_ends(plan):  # the roads in, to the grid
        target = min(streets, key=lambda c: (c[0] - end[0]) ** 2 + (c[1] - end[1]) ** 2)
        streets += plan.pave(plan.line(end, target), st["street"], 1)
    # The piazza: the block (or two) at the middle.
    px0 = max(x for x in xs if x <= cx) if any(x <= cx for x in xs) else xs[0]
    py0 = max(y for y in ys if y <= cy) if any(y <= cy for y in ys) else ys[0]
    pw = bw * (2 if plan.size >= 3 else 1)
    mask = np.zeros((plan.W, plan.H), bool)
    mask[px0:min(plan.W - 2, px0 + pw + 1), py0:min(plan.H - 2, py0 + bh + 1)] = True
    plan.open_space(mask, st.get("plaza", st["street"]))
    mx, my = px0 + pw // 2, py0 + bh // 2
    square_things(plan, mask, mx, my)
    todo = kinds(plan)
    rim = [tuple(int(v) for v in c) for c in np.argwhere(mask)]
    specials_by(plan, rim + streets, todo, (mx, my), gap=0)
    plan.along(streets, todo, gap=0, sizes=((4, 7), (4, 5)), near=(mx, my))
    # The middles of the blocks: gardens behind the houses.
    for x, y in np.argwhere(~plan.used & ~plan.water):
        if plan.inside(x, y, 3) and plan.rng.random() < 0.04:
            plan.thing(int(x), int(y), plan.rng.choice([t for t in st.get("trees", ["tree_broadleaf"]) if t in plan.b.T] or ["planter"]))
    finish_town(plan, streets, walled_with=st.get("wall"))


# ---------------------------------------------------------------------------- medina: a bazaar, alleys, courts
def medina(plan: Plan) -> None:
    st = plan.style
    cx, cy = centre(plan, 2)
    ends = road_ends(plan)
    gate = ends[0]
    bazaar = plan.pave(plan.wander(gate, (cx, cy), 0.25), st["street"], 2)
    others = []
    for end in ends[1:]:
        others += plan.pave(plan.wander(end, (cx, cy), 0.5), st["lane"], 1)
    # Stalls down both sides of the bazaar, under awnings.
    for i, (x, y) in enumerate(bazaar):
        if i % 3 == 0 and plan.size >= 1:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if plan.inside(nx, ny, 1) and not plan.used[nx, ny] and not plan.water[nx, ny]:
                    if plan.thing(nx, ny, plan.rng.choice(["stall", "rug_stall", "stall"])):
                        break
    sq = square(plan, cx, cy, (3, 4, 5, 7, 9)[plan.size], (2, 3, 4, 5, 6)[plan.size], st.get("plaza", st["street"]))
    square_things(plan, sq, cx, cy)
    todo = kinds(plan)
    rim = [tuple(int(v) for v in c) for c in np.argwhere(sq)]
    specials_by(plan, rim + bazaar, todo, (cx, cy), gap=0, shape="court",
                sizes=((9, 12), (8, 10)))
    alleys: list[tuple[int, int]] = []
    for _round in range(4):
        alleys += plan.grow(len(todo) * 6 + 10, st["lane"], near=(cx, cy), length=(5, 12), turn=0.35, spacing=4)
        plan.along(rim + bazaar + others + alleys, todo, gap=0, sizes=((6, 9), (6, 8)), near=(cx, cy))
        if not todo:
            break
    for bld in plan.b.buildings:  # palms in the courts of the big houses
        if bld.shape == "court":
            for room in bld.rooms[:0]:
                pass
    finish_town(plan, bazaar, walled_with=st.get("wall"))


# ---------------------------------------------------------------------------- camp: rings of tents
def camp(plan: Plan) -> None:
    """A horde's camp: the khan's great white tent among its standards on the assembly ground, the shrine, the
    traders' and the smiths' tents round it, and out on the grass the clans, each a circle of tents round its own fire
    with its carts and hitching posts, joined by beaten tracks; horse corrals beyond."""
    st = plan.style
    cx, cy = centre(plan, 2)
    tracks = []
    for end in road_ends(plan):
        tracks += plan.pave(plan.wander(end, (cx, cy), 0.6), st["street"], 1)
    great = (7, 9, 11, 11, 13)[plan.size]
    todo = kinds(plan)
    head = "keep" if "keep" in todo else ("hall" if "hall" in todo else "house")
    if head in todo:
        todo.remove(head)
    khan = None
    for r in range(0, 16):  # the khan's tent as near the middle as it will stand
        for dx, dy in sorted({(dx, dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1) if max(abs(dx), abs(dy)) == r}):
            x, y = cx + dx, cy + dy
            plan.used[x - great // 2 - 1:x + great // 2 + 2, y - great // 2 - 1:y + great // 2 + 2] &= plan.water[
                x - great // 2 - 1:x + great // 2 + 2, y - great // 2 - 1:y + great // 2 + 2]
            khan = plan.raise_building(head, x - great // 2, y - great // 2, great, great, (x, y + great // 2),
                                       shape="round", gap=0, look={"roof": "felt_white", "walls": "felt", "shape": "round"})
            if khan is not None:
                cx, cy = x, y
                break
        if khan is not None:
            break
    ground = square(plan, cx, cy + great // 2 + 4, 6 + plan.size, 3, st.get("plaza", "dirt"))
    square_things(plan, ground, cx, cy + great // 2 + 4)
    if khan is not None:
        for dx in (-great // 2 - 1, great // 2 + 1):  # the horse-tail standards either side of the door
            plan.thing(cx + dx, cy + great // 2, "standard")
    # The shrine, the traders, the smiths and the guests close round the khan's.
    specials = [k for k in todo if k != "house"]
    homes = [k for k in todo if k == "house"]
    ring = great // 2 + 7
    placed = 0
    for i, kind in enumerate(specials):
        size = 7 if kind in ("inn", "temple", "hall", "store", "barracks") else 5
        for tries in range(24):
            a = math.tau * (i + tries * 0.37) / max(4, len(specials)) + 0.4
            tx = int(round(cx + math.cos(a) * ring * 1.4))
            ty = int(round(cy + math.sin(a) * ring))
            door = (tx - int(round(math.cos(a) * size / 2)), ty - int(round(math.sin(a) * size / 2)))
            if plan.raise_building(kind, tx - size // 2, ty - size // 2, size, size, door, shape="round", gap=2):
                placed += 1
                tracks += plan.pave(plan.wander((tx, ty + size // 2 + 1), (cx, cy + great // 2 + 4), 0.4), st["lane"], 1)
                break
            if tries % 6 == 5:
                ring += 3
    # The clans: circles of tents round their fires, out on the grass, the nearest first.
    sites = []
    for gx in range(10, plan.W - 9, 19):
        for gy in range(9, plan.H - 8, 15):
            sites.append((gx + plan.rng.randint(-3, 3), gy + plan.rng.randint(-2, 2)))
    sites = [s for s in sites if ((s[0] - cx) / 1.45) ** 2 + (s[1] - cy) ** 2 > (ring + 6) ** 2]
    sites.sort(key=lambda s: ((s[0] - cx) / 1.45) ** 2 + (s[1] - cy) ** 2 + plan.rng.random() * 30)
    radius = ring + 10
    clans = 0
    for ox, oy in sites:
        if not homes:
            break
        n = min(len(homes), plan.rng.randint(4, 7))
        r = 6 if n <= 5 else 7
        if not plan.inside(ox, oy, 4) or plan.used[ox - 2:ox + 3, oy - 2:oy + 3].any() or plan.water[ox, oy]:
            continue
        got = 0
        start = plan.rng.uniform(0, math.tau)
        for k in range(n):
            b = start + math.tau * k / n
            size = plan.rng.choice((5, 5, 5, 6))
            tx = int(round(ox + math.cos(b) * r * 1.3))
            ty = int(round(oy + math.sin(b) * r))
            door = (tx - int(round(math.cos(b) * size / 2)), ty - int(round(math.sin(b) * size / 2)))
            if homes and plan.raise_building(homes[0], tx - size // 2, ty - size // 2, size, size, door, shape="round", gap=1):
                homes.pop(0)
                got += 1
        if not got:
            continue
        clans += 1
        plan.thing(ox, oy, "fire_pit", light=True)
        for thing in ("cart", "horse_post", plan.rng.choice(("cauldron", "haystack", "sledge" if plan.np.random() < 0.3 else "cart"))):
            for _ in range(6):
                if plan.thing(ox + plan.rng.randint(-3, 3), oy + plan.rng.randint(-2, 2), thing):
                    break
        tracks += plan.pave(plan.wander((ox, oy + 2), nearest_way(plan, ox, oy + 2), 0.5), st["lane"], 1)
        radius = max(radius, int(math.hypot((ox - cx) / 1.45, oy - cy)) + 8)
    # Horse corrals on the outskirts: a ring of fence with a gap for the gate, hay and a trough inside.
    for _ in range(1 + plan.size):
        for _try in range(30):
            a = plan.rng.uniform(0, math.tau)
            d = radius + 8
            hx, hy = int(round(cx + math.cos(a) * d * 1.45)), int(round(cy + math.sin(a) * d))
            rx, ry = plan.rng.randint(4, 6), plan.rng.randint(3, 4)
            if not plan.inside(hx, hy, rx + 3) or plan.used[hx - rx:hx + rx + 1, hy - ry:hy + ry + 1].any() or \
                    plan.water[hx - rx:hx + rx + 1, hy - ry:hy + ry + 1].any():
                continue
            gate = plan.rng.randint(0, 3)
            for x in range(hx - rx, hx + rx + 1):
                for y in range(hy - ry, hy + ry + 1):
                    edge = x in (hx - rx, hx + rx) or y in (hy - ry, hy + ry)
                    if edge and not (gate == 0 and y == hy - ry and abs(x - hx) <= 1) and \
                            not (gate == 1 and y == hy + ry and abs(x - hx) <= 1) and \
                            not (gate == 2 and x == hx - rx and abs(y - hy) <= 1) and \
                            not (gate == 3 and x == hx + rx and abs(y - hy) <= 1):
                        plan.thing(x, y, "fence")
                    plan.used[x, y] = True
            plan.thing(hx, hy, "haystack")
            plan.thing(hx + 2, hy, "trough")
            break
    finish_town(plan, tracks, walled_with=None, fields=False)


# ---------------------------------------------------------------------------- kremlin: a fort above log houses
def kremlin(plan: Plan) -> None:
    st = plan.style
    fx, fy = centre(plan, 2)
    fy = max(10, fy - plan.H // 6)
    rf = (6, 7, 9, 11, 13)[plan.size]
    fort = plan.disc(fx, fy, rf * 1.3, rf)
    plan.open_space(fort, st.get("plaza", st["street"]))
    todo = kinds(plan)
    for kind, dx in (("temple", -rf // 2), ("keep" if "keep" in todo else "hall", rf // 2)):
        if kind in todo:
            w, h = (7, 7) if kind == "temple" else (9, 6)
            bx, by = fx + dx - w // 2, fy - h // 2 - 1
            plan.used[bx:bx + w, by:by + h] = False
            if plan.raise_building(kind, bx, by, w, h, (bx + w // 2, by + h - 1), gap=0):
                todo.remove(kind)
    plan.thing(fx, fy + rf // 2, "well")
    plan.ring_wall(fx, fy, rf * 1.3 + 1, rf + 1, st.get("wall", "palisade"))
    gate = (fx, fy + rf + 1)
    plan.set(*gate, "gate_open")
    # The town below the gate: a market, and streets out from it.
    mx, my = fx, min(plan.H - 8, gate[1] + 5)
    sq = square(plan, mx, my, (2, 3, 4, 6, 7)[plan.size], (2, 2, 3, 4, 5)[plan.size], st.get("plaza", st["street"]))
    square_things(plan, sq, mx, my)
    plan.pave(plan.line(gate, (mx, my)), st["street"], 2 if plan.size >= 2 else 1)
    streets = []
    for end in road_ends(plan):
        streets += plan.pave(plan.wander(end, (mx, my), 0.4), st["street"], 1 if plan.size < 3 else 2)
    rim = [tuple(int(v) for v in c) for c in np.argwhere(sq)]
    specials_by(plan, rim + streets, todo, (mx, my), gap=1)
    for _round in range(4):
        streets += plan.grow(len(todo) * 6 + 10, st["lane"], near=(mx, my), length=(6, 14), turn=0.15)
        plan.along(rim + streets, todo, gap=1, near=(mx, my))
        if not todo:
            break
    finish_town(plan, streets, walled_with=st.get("wall") if plan.size >= 3 else None)


# ---------------------------------------------------------------------------- terraces: white houses down a slope
def terraces(plan: Plan) -> None:
    st = plan.style
    cx, cy = centre(plan, 2)
    rows = list(range(6, plan.H - 6, 7))
    streets = []
    for y in rows:
        cells = [(x, y + int(round(math.sin(x / 9 + y) * 1.2))) for x in range(4, plan.W - 4)]
        streets += plan.pave(cells, st["lane"], 1)
    for x in range(8 + plan.rng.randint(0, 6), plan.W - 6, plan.rng.randint(12, 16)):  # steps up between the rows
        streets += plan.pave(plan.line((x, rows[0]), (x, rows[-1])), st["lane"], 1)
    for end in road_ends(plan):
        target = min(streets, key=lambda c: (c[0] - end[0]) ** 2 + (c[1] - end[1]) ** 2) if streets else (cx, cy)
        streets += plan.pave(plan.line(end, target), st["street"], 1)
    sq = square(plan, cx, cy, (2, 3, 4, 6, 7)[plan.size], (2, 2, 3, 4, 5)[plan.size], st.get("plaza", st["street"]))
    square_things(plan, sq, cx, cy)
    todo = kinds(plan)
    if "temple" in todo:  # the temple of columns above the town
        top = [c for c in streets if c[1] <= rows[0] + 1]
        plan.along(top, ["temple"], sides=["north"], gap=1)
        todo.remove("temple")
    rim = [tuple(int(v) for v in c) for c in np.argwhere(sq)]
    specials_by(plan, rim + streets, todo, (cx, cy), gap=0)
    plan.along(streets, todo, gap=0, sizes=((5, 7), (4, 5)), sides=["north", "south"], near=(cx, cy))
    finish_town(plan, streets, walled_with=st.get("wall") if plan.size >= 3 else None, fields=False)


# ---------------------------------------------------------------------------- plaza: a pyramid on a great square
def plaza(plan: Plan) -> None:
    st = plan.style
    cx, cy = centre(plan, 2)
    pw, ph = (8, 10, 14, 18, 24)[plan.size], (6, 8, 10, 12, 16)[plan.size]
    mask = np.zeros((plan.W, plan.H), bool)
    mask[cx - pw // 2:cx + pw // 2 + 1, cy - ph // 2:cy + ph // 2 + 1] = True
    plan.open_space(mask, st.get("plaza", "flagstones"))
    todo = kinds(plan)
    # The pyramid, north of the plaza, its temple on top and its stair down to the plaza.
    side = (7, 9, 11, 13, 17)[plan.size]
    px0, py0 = cx - side // 2, cy - ph // 2 - side - 1
    if py0 >= 2 and "temple" in todo:
        tw = 5
        tx0, ty0 = cx - tw // 2, py0 + side // 2 - tw // 2
        pyramid = np.zeros((plan.W, plan.H), bool)
        pyramid[px0:px0 + side, py0:py0 + side] = True
        pyramid &= ~plan.water
        plan.b.t[pyramid] = plan.tid("pyramid")
        plan.used |= pyramid
        plan.used[tx0:tx0 + tw, ty0:ty0 + tw] = False
        plan.raise_building("temple", tx0, ty0, tw, tw, (cx, ty0 + tw - 1), gap=0,
                            look={"roof": "flat", "walls": "limestone", "shape": "rect"})
        for y in range(ty0 + tw, py0 + side):
            plan.set(cx, y, "pyramid_steps")
        todo.remove("temple")
    for k in range(4):  # causeways out from the plaza
        dx, dy = ((1, 0), (-1, 0), (0, 1), (0, -1))[k]
        start = (cx + dx * (pw // 2 + 1), cy + dy * (ph // 2 + 1))
        end = (cx + dx * (plan.W // 2 - 3), cy + dy * (plan.H // 2 - 3))
        if dy < 0:
            start, end = (cx + pw // 2 + 2, cy - ph // 2), (cx + pw // 2 + 2, 3)
        plan.pave(plan.line(start, end), st["street"], 2 if plan.size >= 2 else 1)
    plan.thing(cx - pw // 3, cy, "stela")
    plan.thing(cx + pw // 3, cy, "stela")
    plan.thing(cx, cy + ph // 3, "brazier", light=True)
    if plan.size >= 2:  # the ball court
        bx0, by0 = cx + pw // 2 + 4, cy - 3
        if plan.free(bx0, by0, 12, 6, 0):
            for x in range(bx0, bx0 + 12):
                plan.set(x, by0, "low_wall")
                plan.set(x, by0 + 5, "low_wall")
                for y in range(by0 + 1, by0 + 5):
                    plan.set(x, y, "flagstones")
            plan.used[bx0:bx0 + 12, by0:by0 + 6] = True
    # Compounds: little walled yards of round houses, with paths to the causeways.
    streets = [tuple(int(v) for v in c) for c in np.argwhere(plan.street)]
    for _round in range(3):
        plan.along(streets, todo, gap=2, shape="round", sizes=((5, 7), (5, 7)), near=(cx, cy))
        if not todo:
            break
        streets += plan.grow(len(todo) * 6 + 10, st["lane"], near=(cx, cy), length=(6, 12), turn=0.2, spacing=6)
    finish_town(plan, streets, walled_with=None)


# ---------------------------------------------------------------------------- longhouse: long halls, an earth bank
def longhouse(plan: Plan) -> None:
    st = plan.style
    cx, cy = centre(plan, 3)
    todo = kinds(plan)
    head = "hall" if "hall" in todo else "house"
    if head in todo:
        todo.remove(head)
    hw, hh = (12, 14, 16, 18, 22)[plan.size], (5, 6, 6, 7, 8)[plan.size]
    plan.raise_building(head, cx - hw // 2, cy - hh // 2, hw, hh, (cx, cy + hh // 2 + (hh % 2) - 1), shape="long",
                        gap=0)
    square(plan, cx, cy + hh // 2 + 3, 4, 2, st.get("plaza", "dirt"))
    plan.thing(cx - 2, cy + hh // 2 + 3, "fire_pit", light=True)
    plan.thing(cx + 3, cy + hh // 2 + 3, "runestone")
    paths = []
    for end in road_ends(plan):
        paths += plan.pave(plan.wander(end, (cx, cy + hh // 2 + 3), 0.55), st["street"], 1)
    roads = list(paths)
    reach = 14 + 9 * plan.size
    gap = 2 if plan.size < 3 else 1
    # Long halls about the yard, each a little way from the next, their doors on the long side.
    placed = 0
    for _ in range(plan.target * 30):
        if not todo:
            break
        kind = todo[0]
        long_w = plan.rng.randint(9, 14) if kind == "house" else plan.rng.randint(11, 16)
        long_h = plan.rng.randint(4, 6)
        if plan.rng.random() < 0.3:
            w, h = long_h, long_w
        else:
            w, h = long_w, long_h
        x = plan.rng.randint(3, plan.W - w - 3)
        y = plan.rng.randint(3, plan.H - h - 3)
        if (x + w / 2 - cx) ** 2 / 4 + (y + h / 2 - cy) ** 2 > reach ** 2:
            continue
        door = (x + w // 2, y + h - 1) if w >= h else (x + w - 1 if x < cx else x, y + h // 2)
        if plan.raise_building(kind, x, y, w, h, door, shape="long", gap=gap):
            todo.pop(0)
            placed += 1
            outside = (door[0] + (1 if door[0] == x + w - 1 and w < h else (-1 if door[0] == x and w < h else 0)),
                       door[1] + (1 if w >= h else 0))
            paths += plan.pave(plan.wander(outside, (cx, cy + hh // 2 + 3), 0.6), st["lane"], 1)
    finish_town(plan, roads, walled_with=st.get("wall") if plan.s.walled else None)


# ---------------------------------------------------------------------------- hold: halls cut in the mountain
def hold(plan: Plan) -> None:
    """A dwarven hold, all of it under the mountain: great doors in the rock face between two stone kings, the
    gatehouse, the high road in to the great hall, galleries on three levels joined by two cross-ways, and off them
    the districts: the market hall, the forges along a channel of lava, the temple and the tombs, the mushroom farms
    by a dark lake, the mine and its chasm, and homes down side passages. No daylight comes in (meta "underground"):
    its braziers, its forges and the lava light it, the same at noon as at midnight."""
    b = plan.b
    W, H = plan.W, plan.H
    face = H - 7  # the rock face: below it the open mountainside, where the road comes up
    plan.meta.update(underground=True, open_below=face)
    b.t[:, :face] = plan.tid("cave_wall")
    plan.water[:, :face] = False
    gx = W // 2
    wide = 5 if plan.size >= 3 else 3
    half = wide // 2
    todo = kinds(plan)
    carved = {"roof": "none", "walls": "rock", "shape": "carved"}
    ways: list[tuple[int, int]] = []

    def open_floor(x0, y0, w, h, name="floor_stone") -> np.ndarray:
        """Floor cut out of the rock for everyone: a hall, a court, a cave's floor."""
        m = np.zeros((W, H), bool)
        m[max(2, x0):min(W - 2, x0 + w), max(2, y0):min(face - 1, y0 + h)] = True
        m &= ~plan.built
        b.t[m] = plan.tid(name)
        plan.street |= m
        plan.used |= m
        return m

    def way(a, z, width=3, name="floor_stone") -> list[tuple[int, int]]:
        cells = plan.pave(plan.line(a, z), name, width)
        ways.extend(cells)
        return cells

    def cave(cx, cy, rx, ry, name="rock_floor") -> np.ndarray:
        """A natural cave: a lumpy blob of floor, every bit of it joined to its middle."""
        core = plan.disc(cx, cy, rx, ry)
        rim = plan.disc(cx, cy, rx * 1.3, ry * 1.3) & (plan.np.random((W, H)) < 0.45)
        m = core | rim
        m[:2, :] = False
        m[W - 2:, :] = False
        m[:, :2] = False
        m[:, face - 1:] = False
        m &= ~plan.built
        reach = core & m
        for _ in range(int(max(rx, ry) * 0.4) + 2):  # keep only the rim that touches the cave
            grown = reach.copy()
            grown[1:, :] |= reach[:-1, :]
            grown[:-1, :] |= reach[1:, :]
            grown[:, 1:] |= reach[:, :-1]
            grown[:, :-1] |= reach[:, 1:]
            reach = grown & m
        b.t[reach] = plan.tid(name)
        plan.street |= reach
        plan.used |= reach
        return reach

    def pillar(x, y, name="pillar") -> bool:
        """A pillar (or a statue) standing free, with open floor all round it."""
        walk = b.tables.terrain.walk
        if not plan.inside(x, y, 2) or not walk[b.t[x, y]] or plan.is_(x, y, "doorway", "door_closed", "bridge"):
            return False
        if any(not walk[b.t[x + dx, y + dy]] or plan.is_(x + dx, y + dy, "doorway", "door_closed", "gate_open")
               for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy):
            return False
        plan.set(x, y, name)
        return True

    # The gate: great doors in the rock face, stone kings either side, fires before them, the road up to them.
    for x in range(gx - half - 1, gx + half + 2):
        plan.set(x, face - 1, "gate_open")
        plan.street[x, face - 1] = plan.used[x, face - 1] = True
    plan.pave(plan.line((gx, H - 1), (gx, face)), "road", wide)
    for side in (-1, 1):
        plan.thing(gx + side * (half + 3), face, "statue")
        plan.thing(gx + side * (half + 6), face + 1, "brazier", light=True)
    # The gatehouse, its pillars, its racks of arms.
    gh, gw = 6 + plan.size, 13 + 2 * plan.size
    gy0 = face - 1 - gh
    gx0 = gx - gw // 2
    open_floor(gx0, gy0, gw, gh)
    for y in range(gy0 + 1, face - 2, 3):
        for x in (gx0 + 2, gx0 + gw - 3):
            pillar(x, y)
    for i, y in enumerate(range(gy0 + 1, face - 2, 2)):
        plan.thing(gx0, y, ("weapon_rack", "armour_stand", "brazier")[i % 3], light=i % 3 == 2)
        plan.thing(gx0 + gw - 1, y, ("armour_stand", "weapon_rack", "brazier")[i % 3], light=i % 3 == 2)
    # The great hall, with its throne at the far end, its pillars, its kings in stone along the north wall.
    hall_w, hall_h = (24, 28, 32, 36, 40)[plan.size], (12, 13, 15, 16, 18)[plan.size]
    hx0, hy0 = gx - hall_w // 2, 3
    lord = "hall" if "hall" in todo else ("keep" if "keep" in todo else "hall")
    if lord in todo:
        todo.remove(lord)
    great = plan.raise_building(lord, hx0, hy0, hall_w, hall_h, (gx, hy0 + hall_h - 1), gap=0, look=dict(carved),
                                uses=["great_hall"])
    if great is not None:
        for x in range(hx0 + 3, hx0 + hall_w - 3, 4):
            for y in (hy0 + 3, hy0 + hall_h - 4):
                if plan.is_(x, y, "floor_stone"):
                    plan.set(x, y, "pillar")
        for i, x in enumerate(range(hx0 + 4, hx0 + hall_w - 4, 5)):
            if plan.is_(x, hy0 + 1, "floor_stone") and abs(x - gx) > 2:
                plan.set(x, hy0 + 1, "statue" if i % 2 == 0 else "brazier")
                if i % 2:
                    plan.lights.append((x, hy0 + 1))
    # The high road, the galleries on three levels, the two cross-ways.
    g1 = hy0 + hall_h + 2
    g3 = gy0 - 4
    g2 = (g1 + g3) // 2
    xw, xe = max(8, W // 4), min(W - 9, 3 * W // 4)
    road = way((gx, hy0 + hall_h), (gx, gy0), width=wide)
    for gy in (g1, g2, g3):
        way((4, gy), (W - 5, gy))
    for x in (xw, xe):
        way((x, g1), (x, g3))
    for i, (x, y) in enumerate(sorted(set(road), key=lambda c: c[1])):  # ancestors in stone along the high road
        if (x == gx - half or x == gx + half) and y % 6 == 0 and g1 + 2 < y < g3 - 2 and abs(y - g2) > 2:
            pillar(x, y, "statue")
    # The market hall, west of the high road: a hall of pillars full of stalls, open to the ways round it.
    mx0, mx1 = xw + 4, gx - half - 4
    my0, my1 = g1 + 5, g2 - 4
    if mx1 - mx0 >= 10 and my1 - my0 >= 8:
        open_floor(mx0, my0, mx1 - mx0, my1 - my0, "flagstones")
        mcx, mcy = (mx0 + mx1) // 2, (my0 + my1) // 2
        way((mx1 - 1, mcy), (gx - half, mcy), width=3, name="flagstones")
        way((mcx, my0), (mcx, g1), width=3, name="flagstones")
        way((mcx, my1 - 1), (mcx, g2), width=3, name="flagstones")
        way((mx0, mcy), (xw, mcy), width=3, name="flagstones")
        plan.thing(mcx, mcy, "fountain")
        for x in range(mx0 + 2, mx1 - 1, 4):
            for y in range(my0 + 2, my1 - 1, 4):
                if abs(x - mcx) > 2 or abs(y - mcy) > 2:
                    if not pillar(x, y):
                        continue
                    for dx, dy, what in ((1, 0, "stall"), (0, 1, "rug_stall"), (-1, 0, "barrels"), (0, -1, "crates")):
                        if plan.rng.random() < 0.45:
                            plan.thing(x + dx, y + dy, what)
        for x, y in ((mx0, my0), (mx1 - 1, my0), (mx0, my1 - 1), (mx1 - 1, my1 - 1)):
            plan.thing(x, y, "brazier", light=True)
    # The forges, east of the high road: a channel of lava across a floor of forges, anvils and coal.
    fx0, fx1 = gx + half + 4, xe - 4
    fy0, fy1 = g1 + 5, g2 - 4
    forge_mid = ((fx0 + fx1) // 2, (fy0 + fy1) // 2)
    if fx1 - fx0 >= 10 and fy1 - fy0 >= 8:
        open_floor(fx0, fy0, fx1 - fx0, fy1 - fy0)
        cy = forge_mid[1]
        for x in range(fx0, fx1):
            for y in (cy, cy + 1):
                if abs(x - forge_mid[0]) <= 1:
                    plan.set(x, y, "bridge")
                else:
                    plan.set(x, y, "lava")
                    plan.water[x, y] = True
        way((forge_mid[0], fy0), (forge_mid[0], g1), width=3)
        way((forge_mid[0], fy1 - 1), (forge_mid[0], g2), width=3)
        way((fx0, cy - 2), (gx + half, cy - 2), width=3)
        way((fx1 - 1, cy + 3), (xe, cy + 3), width=3)
        for x in range(fx0 + 1, fx1 - 1, 3):
            if abs(x - forge_mid[0]) <= 3:
                continue
            for y, what in ((cy - 1, "forge"), (cy + 2, "forge"), (cy - 3, "anvil"), (cy + 4, "anvil")):
                if plan.is_(x, y, "floor_stone") and plan.rng.random() < (0.8 if what == "forge" else 0.5):
                    plan.set(x, y, what)
                    if what == "forge":
                        plan.lights.append((x, y))
        for x, y in ((fx0, fy0), (fx1 - 1, fy0), (fx0, fy1 - 1), (fx1 - 1, fy1 - 1)):
            plan.thing(x, y, plan.rng.choice(["coal", "mine_cart", "crates"]))
    # The dark lake and its mushroom farms, far to the west, in a cave of their own.
    lake_c = (max(10, xw // 2), (g1 + g3) // 2)
    lake = cave(lake_c[0], lake_c[1], max(5, xw // 2 - 3), max(8, (g3 - g1) // 2 - 4))
    water = plan.disc(lake_c[0], lake_c[1] + 2, max(2, xw // 5), max(3, (g3 - g1) // 6)) & lake
    deep = plan.disc(lake_c[0], lake_c[1] + 2, max(1, xw // 5 - 2), max(2, (g3 - g1) // 6 - 2)) & lake
    b.t[water] = plan.tid("shallow_water")
    b.t[deep] = plan.tid("deep_water")
    plan.water |= water
    shore = [tuple(int(v) for v in c) for c in np.argwhere(lake & ~water)]
    plan.rng.shuffle(shore)
    grown = 0
    for x, y in shore:
        if grown >= 18 + 6 * plan.size:
            break
        if pillar(x, y, plan.rng.choice(["glowcaps", "mushrooms", "mushrooms"])):
            grown += 1
    for x, y in shore[:40]:
        if water[max(0, x - 1):x + 2, max(0, y - 1):y + 2].any() and plan.thing(x, y, "fish_rack"):
            break
    for gy in (g1, g2, g3):  # the galleries come out into the cave
        way((xw, gy), (lake_c[0], gy), width=3, name="rock_floor")
    # The mine, far to the east: caves joined by passages, carts and rubble, and a chasm with bridges.
    mine_x = min(W - 12, xe + (W - xe) // 2)
    for cy_, gy in ((g1 + (g2 - g1) // 2, g1), (g2 + (g3 - g2) // 2, g2)):
        cave(mine_x, cy_, max(4, (W - xe) // 3), max(4, (g3 - g1) // 7))
        way((mine_x, gy), (mine_x, cy_), width=3, name="rock_floor")  # a passage down from the gallery
        way((mine_x + 3, cy_), (mine_x + 3, gy + (g2 - g1)), width=1, name="rock_floor")  # and on to the next
    mine = [tuple(int(v) for v in c) for c in np.argwhere(plan.street & (np.arange(W)[:, None] > xe + 2))]
    plan.rng.shuffle(mine)
    for x, y in mine[: 10 + 4 * plan.size]:
        pillar(x, y, plan.rng.choice(["mine_cart", "rubble", "boulder", "crates"]))
    if plan.size >= 2:
        chx = xe + max(4, (mine_x - xe) // 3)  # between the cross-way and the mine: the mine is over the bridges
        for y in range(2, g3 + 3):
            for x in (chx, chx + 1):
                if plan.built[x, y]:
                    continue
                if plan.street[x, y] and any(abs(y - gy) <= 1 for gy in (g1, g2, g3)):
                    plan.set(x, y, "bridge")
                else:
                    plan.set(x, y, "chasm")
                    plan.water[x, y] = True
                    plan.used[x, y] = True
                    plan.street[x, y] = False
    # The special buildings, each in its district; then homes down side passages.
    near = {"temple": (xw, g1), "tomb": (xw + 6, g1), "smithy": forge_mid, "forge_hall": forge_mid,
            "store": ((mx0 + mx1) // 2, g2), "warehouse": ((mx0 + mx1) // 2, g2), "inn": (gx, g3),
            "barracks": (gx, g3), "healer": (gx, g2), "mushroom_farm": lake_c, "brewery": lake_c, "bakery": (gx, g2)}
    specials = [k for k in todo if k != "house"]
    homes = [k for k in todo if k == "house"]
    for kind in specials:
        spot = near.get(kind, (gx, g2))
        w_h = ((9, 13), (6, 9)) if kind in ("temple", "tomb", "inn", "forge_hall", "mushroom_farm", "barracks") \
            else ((6, 9), (5, 7))
        got = plan.along(ways, [kind], sizes=w_h, sides=["north", "south", "east", "west"], gap=1, count=1, near=spot)
        for g in got:
            g.look, g.shape = dict(carved), "carved"
            if g.kind == "smithy":  # a forge over a little channel of lava
                for x in range(g.x + 2, g.x + g.w - 2):
                    if plan.is_(x, g.y + 1, "floor_stone") and plan.keeps_ways(x, g.y + 1):
                        plan.set(x, g.y + 1, "lava")
                plan.lights.append((g.x + g.w // 2, g.y + 1))
    lanes_ = plan.grow(max(60, len(homes) * 5), "rock_floor", near=(gx, g2), length=(5, 12), turn=0.12, spacing=6)
    ways.extend(lanes_)
    plan.along(ways, homes, sizes=((5, 7), (5, 6)), gap=1, near=(gx, g2))
    for g in b.buildings:
        g.look, g.shape = dict(carved), "carved"
    # Light along the ways, things by the walls.
    lit = 0
    for i, (x, y) in enumerate(sorted(set(ways))):
        if i % 11 or lit >= 30 + 14 * plan.size:
            continue
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            if plan.is_(x + dx, y + dy, "cave_wall") and not plan.built[x + dx, y + dy]:
                if plan.thing(x, y, "brazier" if plan.rng.random() < 0.6 else "torch_post", light=True):
                    lit += 1
                break
    things = ["barrels", "crates", "mine_cart", "sacks"]
    for x, y in [c for i, c in enumerate(sorted(set(ways))) if i % 17 == 5][:20 + 8 * plan.size]:
        if any(plan.is_(x + dx, y + dy, "cave_wall") for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))):
            plan.thing(x, y, plan.rng.choice(things))
    plan.meta["entry"] = (gx, H - 2)


# ---------------------------------------------------------------------------- grove: homes in giant trees
def grove(plan: Plan) -> None:
    st = plan.style
    cx, cy = centre(plan, 3)
    square(plan, cx, cy, 7, 5, st.get("plaza", "grass"))
    for x in range(cx - 1, cx + 2):
        for y in range(cy - 1, cy + 2):
            plan.set(x, y, "glow_water" if (x, y) == (cx, cy) else "glow_shallow")
    plan.lights.append((cx, cy))
    for a in range(6):
        ang = a * math.tau / 6
        plan.thing(int(cx + math.cos(ang) * 5), int(cy + math.sin(ang) * 3.5), "lantern_post", light=True)
    paths = []
    for end in road_ends(plan):
        paths += plan.pave(plan.wander(end, (cx, cy), 0.6), st["street"], 1)
    todo = kinds(plan)
    head = "hall" if "hall" in todo else None
    if head:  # the hall: the greatest tree, north of the glade (or wherever round it there is room)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            hx, hy = cx + dx * 15, cy + dy * 13
            door = (hx - dx * 6, hy - dy * 5)
            hall = plan.raise_building(head, hx - 6, hy - 5, 13, 11, door, shape="tree", gap=1,
                                       look={"roof": "leaves", "walls": "living_wood", "shape": "tree"})
            if hall is not None:
                todo.remove(head)
                out = (hall.door[0] - dx, hall.door[1] - dy)
                paths += plan.pave(plan.wander(out, (cx, cy), 0.3), st["lane"], 1)
                break
    ring = 13
    while todo and ring < max(plan.W, plan.H) // 2:
        n = max(5, int(2 * math.pi * ring / 13))
        start = plan.rng.uniform(0, math.tau)
        for i in range(n):
            if not todo:
                break
            a = start + math.tau * i / n
            size = 9 if todo[0] != "house" else 7
            tx, ty = int(cx + math.cos(a) * ring * 1.4), int(cy + math.sin(a) * ring)
            door = (tx - int(math.cos(a) * size / 2), ty - int(math.sin(a) * size / 2))
            bld = plan.raise_building(todo[0], tx - size // 2, ty - size // 2, size, size, door, shape="tree", gap=2,
                                      look={"roof": "leaves", "walls": "living_wood", "shape": "tree"})
            if bld is not None:
                todo.pop(0)
                out = (bld.door[0] + int(round(-math.cos(a))), bld.door[1] + int(round(-math.sin(a))))
                paths += plan.pave(plan.wander(out, (cx, cy), 0.5), st["lane"], 1)
        ring += 10
    street_lights(plan, paths, every=6)


# ---------------------------------------------------------------------------- burrows: homes in green mounds
def burrows(plan: Plan) -> None:
    st = plan.style
    cx, cy = centre(plan, 3)
    green = square(plan, cx, cy, 5, 4, st.get("plaza", "grass"))
    plan.thing(cx, cy, "party_tree")
    plan.thing(cx + 3, cy + 1, "well")
    lanes_ = []
    for end in road_ends(plan):
        lanes_ += plan.pave(plan.wander(end, (cx, cy), 0.7), st["street"], 1)
    lanes_ += plan.grow((20, 40, 90, 160, 260)[plan.size], st["lane"], near=(cx, cy), length=(6, 14), turn=0.3,
                        spacing=6)
    todo = kinds(plan)
    look = {"roof": "mound", "walls": "earth", "shape": "mound"}
    rim = [tuple(int(v) for v in c) for c in np.argwhere(green)]
    specials = [k for k in todo if k != "house"]
    homes = [k for k in todo if k == "house"]
    got = plan.along(rim + lanes_, specials, sizes=((8, 8), (7, 7)), gap=2, shape="mound", near=(cx, cy))
    got += plan.along(rim + lanes_, homes, sizes=((6, 7), (5, 6)), gap=2, shape="mound", near=(cx, cy))
    for g in got:
        g.look = dict(look)
        g.shape = "mound"
    for bld in plan.b.buildings:  # a garden before each door
        dx, dy = bld.door
        for gx in range(dx - 2, dx + 3):
            for gy in range(dy - 3, dy + 4):
                if plan.inside(gx, gy, 1) and not plan.used[gx, gy] and not plan.water[gx, gy] and \
                        plan.rng.random() < 0.3:
                    plan.set(gx, gy, "garden")
                    plan.used[gx, gy] = True
    finish_town(plan, lanes_, walled_with=st.get("wall") if plan.s.walled else None)


# ---------------------------------------------------------------------------- stockade: huts in a ring of stakes
def stockade(plan: Plan) -> None:
    st = plan.style
    cx, cy = centre(plan, 3)
    paths = []
    for end in road_ends(plan):
        paths += plan.pave(plan.wander(end, (cx, cy), 0.6), st["street"], 1)
    sq = square(plan, cx, cy, 4, 3, st.get("plaza", "dirt"))
    square_things(plan, sq, cx, cy)
    todo = kinds(plan)
    paths += plan.grow(len(todo) * 6 + 10, st["lane"], near=(cx, cy), length=(5, 10), turn=0.3)
    plan.along([tuple(int(v) for v in c) for c in np.argwhere(sq)] + paths, todo, gap=1, sizes=((5, 8), (4, 6)),
               near=(cx, cy))
    finish_town(plan, paths, walled_with="palisade", fields=False)
