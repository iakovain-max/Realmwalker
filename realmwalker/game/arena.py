"""Where a fight happens, and where everyone stands when it starts.

The battlefield is the place itself. On a close-up map (a dungeon level, a town, a ruin, wild country walked into)
the field is cut out of that map around you and the ones you fight: the same walls, trees, doors, tables and hearths,
and everybody where they really were. Out on the road it is laid out from the land you are crossing: its ground, its
trees, brush and stones, the road itself if you are on one, a stream or a river with its ford, the campfire if they
fell on your camp.

Your party stands in its battle order (set on the party screen: a five-by-five block, the front row towards the
enemy), turned to face them. The enemy stands as the moment says:
  - both sides see each other: they come on in a line from the far side, archers and casters behind, wolves and dogs
    spread wide to take you from the flanks, at a distance that depends on the land and the light (open ground in
    daylight, far; woods, night or fog, close);
  - robbers on a road: some in front of you, some behind;
  - you caught them unawares: bunched together where they were, and you a good way off;
  - they caught you unawares: all around you, closing in; asleep at your camp: around the fire.
"""

from __future__ import annotations

import math

import numpy as np

from realmwalker.rules import grid
from realmwalker.rules.combat import FOE, PARTY, Env

FORMATION_SIZE = 5
CLASS_ROW = {"fighter": 0, "cleric": 1, "rogue": 1, "wizard": 2}
COLUMNS = (2, 1, 3, 0, 4)
WILD_W, WILD_H = 22, 14
LOCAL_W, LOCAL_H = 22, 14
DUNGEON_W, DUNGEON_H = 24, 16
MAX_W, MAX_H = 32, 20
OPEN_LAND = {"plains", "desert", "tundra", "coast", "hills", "mountains", "high_mountains"}


# ---------------------------------------------------------------------------- battle order
def default_cell(char, taken: set) -> tuple[int, int]:
    row = CLASS_ROW.get(char.cls, 1)
    for r in list(range(row, FORMATION_SIZE)) + list(range(row - 1, -1, -1)):
        for c in COLUMNS:
            if (c, r) not in taken:
                return c, r
    return 2, 0


def formation(party) -> list[tuple[int, int]]:
    """Each member's square in the battle order: (column 0-4 from left to right, row 0 = the front)."""
    taken: set = set()
    out = []
    for c in party:
        cell = tuple(c.formation) if len(getattr(c, "formation", []) or []) == 2 else None
        if cell is None or cell in taken or not (0 <= cell[0] < FORMATION_SIZE and 0 <= cell[1] < FORMATION_SIZE):
            cell = default_cell(c, taken)
        taken.add(cell)
        out.append(cell)
    return out


def set_cell(party, index: int, cell: tuple[int, int]) -> None:
    """Put one member on a square of the battle order; whoever stood there takes their old square."""
    cells = formation(party)
    old = cells[index]
    for i, other in enumerate(cells):
        if i != index and other == cell:
            party[i].formation = [old[0], old[1]]
    for i, c in enumerate(party):
        if not c.formation:
            c.formation = [cells[i][0], cells[i][1]]
    party[index].formation = [cell[0], cell[1]]


def _offset(cell: tuple[int, int], forward: tuple[int, int]) -> tuple[int, int]:
    fx, fy = forward
    rx, ry = -fy, fx  # facing north the right hand is east
    c, r = cell
    return (c - 2) * rx - r * fx, (c - 2) * ry - r * fy


# ---------------------------------------------------------------------------- building the field
def build(game, creatures: list, env: Env, rng, *, actor=None, near: tuple[int, int] | None = None,
          situation: str = "facing", number: int = 0) -> tuple[grid.Field, dict]:
    """The field and where everyone starts on it: spots maps fighter index (party first, in order, then the
    creatures in order) to a square."""
    party = [c for c in game.party if c.alive]
    lm = game.local
    if lm is not None:
        return _local(game, lm, party, creatures, env, rng, actor=actor, near=near, situation=situation, number=number)
    return _wild(game, party, creatures, env, rng, situation=situation, number=number)


def _local(game, lm, party, creatures, env, rng, *, actor, near, situation, number):
    p = game.player
    me = (p.lx, p.ly)
    them = (actor.x, actor.y) if actor is not None else near
    W, H = (DUNGEON_W, DUNGEON_H) if lm.kind == "dungeon" else (LOCAL_W, LOCAL_H)
    cx, cy = me if them is None else ((me[0] + them[0]) // 2, (me[1] + them[1]) // 2)
    if them is not None:
        W = min(MAX_W, max(W, abs(me[0] - them[0]) + 10))
        H = min(MAX_H, max(H, abs(me[1] - them[1]) + 8))
    W, H = min(W, lm.width), min(H, lm.height)
    # Centred between the two sides, but never so far that you are off the field (a band seen from afar comes on
    # from the field's edge).
    x0 = min(max(cx - W // 2, me[0] - W + 3), me[0] - 2)
    y0 = min(max(cy - H // 2, me[1] - H + 3), me[1] - 2)
    x0 = max(0, min(lm.width - W, x0))
    y0 = max(0, min(lm.height - H, y0))
    terrain = game.remap_for(lm)[lm.terrain[x0:x0 + W, y0:y0 + H]].astype(np.uint16)
    lights = _terrain_lights(game, terrain)
    under = lm.under_rock(*me)
    indoors = under or lm.building_at(*me) is not None
    field = grid.Field(game.tables, terrain, kind=lm.kind, style=lm.meta.get("style", ""),
                       key=f"{lm.key}/battle{number}", base_light=env.light, indoors=indoors, underground=under,
                       ground=env.ground, lights=lights, origin=(x0, y0))
    field.cut_from = lm.key  # (its dead and blood are written back there: game/remains.py)
    lead = (me[0] - x0, me[1] - y0)
    if them is not None:
        foe_at = (max(0, min(W - 1, them[0] - x0)), max(0, min(H - 1, them[1] - y0)))
        forward = _dir(lead, foe_at)
    else:
        forward = _open_side(field, lead)
        foe_at = None
    taken: set = set()
    spots = _place_party(field, party, lead, forward, taken, leader_on=lead)
    if foe_at is None:
        d = 6 if env.light >= 0.5 else 4
        foe_at = (lead[0] + forward[0] * d, lead[1] + forward[1] * d)
        mode = "surround" if situation in ("ambushed", "camp") else "line"
    else:
        mode = "cluster"
    # The two sides must be able to come at each other on this piece of the map: if the way between them runs
    # outside it (or behind a locked door), the enemy comes on from the nearest place that does connect.
    ours = _reach(field, lead)
    if foe_at not in ours:
        far = [sq for sq in ours if max(abs(sq[0] - lead[0]), abs(sq[1] - lead[1])) >= 3] or list(ours)
        foe_at = min(far, key=lambda sq: (sq[0] - foe_at[0]) ** 2 + (sq[1] - foe_at[1]) ** 2)
    _place_foes(game, field, creatures, foe_at, forward, lead, mode, taken, spots, len(party), rng)
    return field, spots


def _wild(game, party, creatures, env, rng, *, situation, number):
    W, H = WILD_W, WILD_H
    tables = game.tables
    T = tables.terrain.index
    x, y = game.player.x, game.player.y
    biome_key = game.biome_key(x, y)
    loc = game.biome_def(x, y)["local"]
    nrng = rng.numpy("arena-ground")
    from realmwalker.world.noise import fbm

    ground = [g for g in loc["ground"] if tables.terrain[T[g[0]]]["walk"]] or [["grass", 1]]
    names = [g[0] for g in ground]
    weights = np.array([float(g[1]) for g in ground])
    cum = np.cumsum(weights / weights.sum())
    patch = fbm(nrng, W, H, cell=6, octaves=2, aspect=1.0)
    v = np.clip(patch * 0.85 + nrng.random((W, H)) * 0.18, 0, 0.9999)
    ids = np.array([T[n] for n in names], dtype=np.uint16)
    terrain = ids[np.clip(np.searchsorted(cum, v), 0, len(ids) - 1)].astype(np.uint16)
    road = bool(game.world.road[x, y])
    river = int(game.world.river[x, y]) if hasattr(game.world, "river") else 0
    camp = situation == "camp"
    # Where the two sides will stand, kept clear of trees and stones.
    mid = H // 2
    if situation in ("ambushed", "camp"):
        lead = (W // 2 - 1, mid)
        forward = (1, 0)
    else:
        lead = (4, mid)
        forward = (1, 0)
    dist = _distance(biome_key, env, situation)
    foe_at = (min(W - 3, lead[0] + dist), mid)
    clump = fbm(nrng, W, H, cell=4, octaves=2, aspect=1.0)
    r = nrng.random((W, H))
    trees = float(loc.get("trees", 0)) * 0.75
    types = [t for t in loc.get("tree_types", []) if t in T] or ["tree_broadleaf"]
    if trees > 0:
        mask = r < np.clip(trees * (0.2 + 1.8 * clump), 0, 0.6)
        pick = nrng.integers(0, len(types), size=(W, H))
        terrain = np.where(mask, np.array([T[t] for t in types], dtype=np.uint16)[pick], terrain).astype(np.uint16)
    r2 = nrng.random((W, H))
    bush = max(float(loc.get("bushes", 0)), 0.02)
    terrain = np.where((r2 < bush * 1.2) & tables.terrain.walk[terrain], T["bush"], terrain).astype(np.uint16)
    r3 = nrng.random((W, H))
    rocks = max(float(loc.get("rocks", 0)), 0.012)
    terrain = np.where((r3 < rocks) & tables.terrain.walk[terrain], T["boulder"], terrain).astype(np.uint16)
    if river >= 1 and not road:
        _stream(terrain, T, nrng, deep=river >= 2)
    if road:
        rr = slice(mid - 1, mid + 1)
        terrain[:, rr] = T["road"]
        if river >= 1:
            sx = W // 2
            terrain[sx - 1:sx + 1, :] = np.where(tables.terrain.walk[terrain[sx - 1:sx + 1, :]], terrain[sx - 1:sx + 1, :],
                                                  T["shallow_water"])
            terrain[sx - 1:sx + 1, rr] = T["bridge"]
        if situation == "facing" and nrng.random() < 0.35 and "cart" in T:
            terrain[min(W - 2, foe_at[0] - 2), mid - 2] = T["cart"]
    # Clear the ground under both sides (a few squares round each), so nobody starts in a tree.
    for (ax, ay), rad in ((lead, 3), (foe_at, 3)):
        for xx in range(max(0, ax - rad), min(W, ax + rad + 1)):
            for yy in range(max(0, ay - rad), min(H, ay + rad + 1)):
                if not tables.terrain.walk[terrain[xx, yy]] or tables.terrain.cost[terrain[xx, yy]] >= 2.0:
                    if (xx - ax) ** 2 + (yy - ay) ** 2 <= rad * rad and not tables.terrain.tags[int(terrain[xx, yy])] & {"water"}:
                        terrain[xx, yy] = ids[0]
    lights = []
    fires: set = set()
    story_field = getattr(game.encounter, "field", "") if game.encounter is not None else ""
    if story_field in FIELDS:
        lights, fires = FIELDS[story_field](terrain, tables, lead, foe_at, nrng)
    if camp:
        fire = (lead[0] + 1, lead[1] + 1)
        terrain[fire] = T["campfire"]
        for dx, dy in ((-1, 0), (0, 1), (1, 1)):
            bx, by = fire[0] + dx, fire[1] + dy
            if 0 <= bx < W and 0 <= by < H and tables.terrain.walk[terrain[bx, by]]:
                terrain[bx, by] = T["bedroll"]
        lights = [(fire[0], fire[1], 3)]
    _connect(terrain, tables, lead, foe_at)
    field = grid.Field(tables, terrain, kind="wilderness", key=f"road/{x},{y}/battle{number}", base_light=env.light,
                       ground=env.ground, lights=lights)
    if fires:
        field.__dict__["fires"] = sorted(fires)  # (lit by fire.on_battle_start: the carts burning)
    taken: set = set()
    spots = _place_party(field, party, lead, forward, taken)
    mode = {"ambushed": "surround", "camp": "surround", "unaware": "cluster"}.get(situation, "line")
    if mode == "line" and road and len(creatures) >= 3 and _robbers(game, creatures):
        mode = "block"
    elif mode == "line" and _pack(game, creatures):
        mode = "arc"
    _place_foes(game, field, creatures, foe_at, forward, lead, mode, taken, spots, len(party), rng)
    return field, spots


def _ford(terrain, tables, lead, foe_at, nrng) -> tuple[list, set]:
    """The ford at night (the Risen's hold): the road crossing a shallow river between the two sides, and across the
    road on your bank the carts drawn up and set alight, a gap left in the middle; the grass beside them catches."""
    T = tables.terrain.index
    W, H = terrain.shape
    mid = H // 2
    terrain[:, mid - 1:mid + 1] = T["road"]
    sx = min(W - 3, (lead[0] + foe_at[0]) // 2 + 1)
    for xx in (sx, sx + 1):
        col = terrain[xx, :]
        terrain[xx, :] = np.where(tables.terrain.walk[col], T["shallow_water"], col)
        terrain[xx, mid - 1:mid + 1] = T["ford"]
    cx = sx - 1
    lights, fires = [], set()
    for yy in (mid - 3, mid - 2, mid + 1, mid + 2):  # (the gap is the road itself: mid-1 and mid)
        if 0 <= yy < H:
            terrain[cx, yy] = T["cart"]
            fires.add((cx, yy))
            lights.append((cx, yy, 3))
    for yy in (mid - 4, mid + 3):
        if 0 <= yy < H and tables.terrain.walk[terrain[cx, yy]]:
            terrain[cx, yy] = T["grass"]
            fires.add((cx, yy))
    return lights, fires


FIELDS = {"ford": _ford}  # a story's own battlefields (the hold step's `field`: Expansion 6 D.3)


def _robbers(game, creatures) -> bool:
    return all(game.tables.creatures[c.def_id].get("morale") in ("bandit", "coward", "soldier") for c in creatures)


def _pack(game, creatures) -> bool:
    defs = [game.tables.creatures[c.def_id] for c in creatures]
    return len(defs) >= 2 and all(d["kind"] == "beast" for d in defs)


def _distance(biome_key: str, env: Env, situation: str) -> int:
    """How far apart the two sides are when they see each other: far on open land by day, close in the woods, at
    night or in fog."""
    if situation == "unaware":
        return 10
    d = 12 if biome_key in OPEN_LAND else 8
    if env.light < 0.35:
        d = min(d, 6)
    elif env.light < 0.6:
        d = min(d, 8)
    return d


def _stream(terrain, T, nrng, *, deep: bool) -> None:
    """A stream (shallow, slow going) or a river (deep, with a ford) across the field from north to south."""
    W, H = terrain.shape
    x = W // 2 + int(nrng.integers(-1, 2))
    ford = H // 2 + int(nrng.integers(-2, 3))
    for y in range(H):
        x = max(2, min(W - 3, x + int(nrng.integers(-1, 2)) * (1 if y % 2 else 0)))
        for dx in range(-1, 1):
            if deep and abs(y - ford) > 1:
                terrain[x + dx, y] = T["deep_water"]
            else:
                terrain[x + dx, y] = T["ford"] if deep else T["shallow_water"]


def _connect(terrain, tables, a, b) -> None:
    """Make sure the two sides can reach each other: clear a way between them if the land has shut it."""
    W, H = terrain.shape
    walk = tables.terrain.walk[terrain]
    seen = {a}
    frontier = [a]
    while frontier:
        nxt = []
        for (x, y) in frontier:
            for dx, dy in grid.DIRS8:
                n = (x + dx, y + dy)
                if 0 <= n[0] < W and 0 <= n[1] < H and n not in seen and walk[n]:
                    seen.add(n)
                    nxt.append(n)
        frontier = nxt
    if b in seen:
        return
    steps = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
    for i in range(steps + 1):
        x = round(a[0] + (b[0] - a[0]) * i / max(1, steps))
        y = round(a[1] + (b[1] - a[1]) * i / max(1, steps))
        if not walk[x, y]:
            terrain[x, y] = tables.terrain.index["ford" if "water" in tables.terrain.tags[int(terrain[x, y])] else "dirt"]


def _terrain_lights(game, terrain) -> list[tuple[int, int, int]]:
    """Hearths and campfires on the field shed light around them."""
    sp = game.tables.sprites["terrain"]
    ids = game.tables.terrain.ids
    lit = {i for i, tid in enumerate(ids) if sp.get(tid, {}).get("light")}
    if not lit:
        return []
    out = []
    for x, y in np.argwhere(np.isin(terrain, list(lit))):
        r = int(sp[ids[int(terrain[x, y])]]["light"][0])
        out.append((int(x), int(y), max(2, r // 2)))
    return out


def _dir(a, b) -> tuple[int, int]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return (1, 0)
    if abs(dx) >= abs(dy):
        return (1 if dx > 0 else -1, 0)
    return (0, 1 if dy > 0 else -1)


def _open_side(field: grid.Field, at) -> tuple[int, int]:
    """With nobody to face: the way with most room in front of you."""
    best, best_n = (1, 0), -1
    for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = 0
        for k in range(1, 8):
            x, y = at[0] + d[0] * k, at[1] + d[1] * k
            if not field.passable(x, y):
                break
            n += 1
        if n > best_n:
            best, best_n = d, n
    return best


# ---------------------------------------------------------------------------- placing
def _reach(field: grid.Field, start: tuple[int, int]) -> dict[tuple[int, int], int]:
    """Steps from a square to every square that can be walked to from it."""
    if not field.passable(*start):
        start = min(((x, y) for x in range(field.width) for y in range(field.height) if field.walk[x, y]),
                    key=lambda s: (s[0] - start[0]) ** 2 + (s[1] - start[1]) ** 2, default=start)
    dist = {start: 0}
    frontier = [start]
    while frontier:
        nxt = []
        for (x, y) in frontier:
            for dx, dy in grid.DIRS8:
                n = (x + dx, y + dy)
                if n not in dist and field.passable(*n):
                    dist[n] = dist[(x, y)] + 1
                    nxt.append(n)
        frontier = nxt
    return dist


def _spot(field: grid.Field, want, size: int, taken: set, reach: dict, *, exact=None) -> tuple[int, int]:
    """The free square, reachable from where this side stands, nearest to where someone wants to be."""
    if exact is not None and field.fits(exact[0], exact[1], size) and not any(c in taken for c in grid.cells(*exact, size)):
        return exact
    best, best_k = None, None
    for sq, steps in reach.items():
        if not field.fits(sq[0], sq[1], size) or any(c in taken for c in grid.cells(sq[0], sq[1], size)):
            continue
        k = (sq[0] - want[0]) ** 2 + (sq[1] - want[1]) ** 2 + steps * 0.05
        if best_k is None or k < best_k:
            best, best_k = sq, k
    if best is None:  # nowhere reachable: anywhere free at all
        for x in range(field.width):
            for y in range(field.height):
                if field.fits(x, y, size) and not any(c in taken for c in grid.cells(x, y, size)):
                    k = (x - want[0]) ** 2 + (y - want[1]) ** 2
                    if best_k is None or k < best_k:
                        best, best_k = (x, y), k
    return best if best is not None else (0, 0)


def _place_party(field, party, anchor, forward, taken: set, *, leader_on=None) -> dict:
    cells = formation(party)
    base = anchor
    if leader_on is not None:
        ox, oy = _offset(cells[0], forward)
        base = (leader_on[0] - ox, leader_on[1] - oy)
    else:
        # The formation's front row centre stands at the anchor.
        base = anchor
    reach = _reach(field, leader_on or anchor)
    order = sorted(range(len(party)), key=lambda i: (i != 0 or leader_on is None, cells[i][1], abs(cells[i][0] - 2)))
    spots = {}
    from realmwalker.rules.grid import footprint

    for i in order:
        ox, oy = _offset(cells[i], forward)
        want = (base[0] + ox, base[1] + oy)
        size = footprint(field.t.races[party[i].race]["size"])
        sq = _spot(field, want, size, taken, reach, exact=leader_on if (i == 0 and leader_on is not None) else None)
        spots[i] = sq
        taken |= set(grid.cells(sq[0], sq[1], size))
    return spots


def _place_foes(game, field, creatures, anchor, forward, party_at, mode, taken, spots, offset, rng) -> None:
    tables = game.tables
    reach = _reach(field, anchor)
    if mode in ("surround", "block"):
        reach = {**_reach(field, party_at), **reach}
    back = (-forward[0], -forward[1])  # from the foes' side, away from the party is the party's forward
    right = (-forward[1], forward[0])
    defs = [tables.creatures[c.def_id] for c in creatures]
    order = sorted(range(len(creatures)), key=lambda i: (_stands_back(defs[i]), i))
    n = len(creatures)
    front_k = back_k = 0
    lanes = (0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5)
    for k, i in enumerate(order):
        d = defs[i]
        size = grid.footprint(d["size"])
        spread = 2 if d["kind"] == "beast" else 1
        if mode == "surround":
            ang = 2 * math.pi * k / max(1, n) + rng.random() * 0.4
            rad = 4 + (k % 2)
            want = (party_at[0] + round(math.cos(ang) * rad), party_at[1] + round(math.sin(ang) * rad * 0.8))
        elif mode == "arc":
            ang = (k - (n - 1) / 2) * (1.6 / max(1, n - 1)) if n > 1 else 0.0
            dist = max(4, abs(anchor[0] - party_at[0]) + abs(anchor[1] - party_at[1]))
            fx, fy = forward
            c, s = math.cos(ang), math.sin(ang)
            vx, vy = fx * c - fy * s, fx * s + fy * c
            want = (party_at[0] + round(vx * dist), party_at[1] + round(vy * dist))
        elif mode == "cluster":
            lane = lanes[k % len(lanes)]
            want = (anchor[0] + right[0] * lane + (back[0] * -1 if _stands_back(d) else 0),
                    anchor[1] + right[1] * lane + (back[1] * -1 if _stands_back(d) else 0))
        elif mode == "block" and k % 2 == 1:
            want = (party_at[0] - forward[0] * 5 + right[0] * (k // 2), party_at[1] - forward[1] * 5 + right[1] * (k // 2))
        else:  # a line, the archers and casters a few squares behind it
            if _stands_back(d):
                lane = lanes[back_k % len(lanes)] * 2
                back_k += 1
                want = (anchor[0] + forward[0] * 3 + right[0] * lane, anchor[1] + forward[1] * 3 + right[1] * lane)
            else:
                lane = lanes[front_k % len(lanes)] * spread
                front_k += 1
                want = (anchor[0] + right[0] * lane, anchor[1] + right[1] * lane)
        want = (max(0, min(field.width - size, want[0])), max(0, min(field.height - size, want[1])))
        sq = _spot(field, want, size, taken | _too_close(party_at, mode), reach)
        spots[offset + i] = sq
        taken |= set(grid.cells(sq[0], sq[1], size))


def _too_close(party_at, mode) -> set:
    """Squares right beside the party that a surrounding enemy should not start on (they close in on their turn)."""
    if mode != "surround":
        return set()
    x, y = party_at
    return {(x + dx, y + dy) for dx in range(-2, 3) for dy in range(-2, 3)}


def situation_for(game, surprised: str | None) -> str:
    """What kind of start this is, from the encounter that led to it."""
    enc = game.encounter
    if surprised == PARTY:
        return "camp" if enc is not None and getattr(enc, "asleep", False) else "ambushed"
    if surprised == FOE:
        return "unaware"
    return "facing"


def _stands_back(d: dict) -> bool:
    """Archers, casters and those who lead from behind start at the back (creatures' "ai" role and range)."""
    ai = d.get("ai") or {}
    return ai.get("role") in ("artillery", "controller", "support") or int(ai.get("range", 0)) > 5
