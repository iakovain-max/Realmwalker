"""Land changes while you play (Expansion 6 G.6; ADVENTURES.md §5.21 and §8.16): the ledger of what the world's
great events did to the land itself.

    world.politics["land"]          [{"id", "kind", "day", "seed", "shape", "v", "cells": [[x, y, field, old, new]...],
                                      "story"?, "spread"?}]  (in the order they were applied)
    world.politics["land_version"]  one more for every change (apply or undo)
    world.politics["land_log"]      [[version, [[x, y]...], [fields]]] the last LOG_KEEP changes, so a painter or a
                                    traveller that knows an older version takes only the squares that changed
    world.politics["party_at"]      [x, y] the party's square (set by GameState before politics moves the world):
                                    a change never falls on it, nor on the map it stands on

The base world plus the ledger gives today's land: every cell a record changed says its field, the old value and the
new, so `undo` puts the old back and `check` (autoplay's `_check_land`) undoes and redoes the whole ledger on a copy
and compares. The kinds and their land (biomes.json fragment of the pack):

    rift          a wandering crack (shape {x, y, dir, len}): biome "rift" (impassable), every LEDGE_EVERY squares
                  a "rift_ledge" (a crossing, slow); RAVINE in the relief; roads cut except at a ledge
    blight        a ragged blob (shape {x, y, r}): "blighted" (grey dead country); grows a ring at a time while
                  its `spread` {threat, max} says so (`weekly`, from Politics.advance)
    dead_forest   a blight that takes only forest
    scorch        a ragged blob: "scorched_land" (a dragon's fire)
    drown         a flood from a low point (shape {x, y, n}): "drowned" (land under water, rivers lost in it)
    crater        a disc (shape {x, y, r}): the inside a "lake" a little lower (r >= 2), a "crater" rim with CLIFF

Never under a settlement, a site or a wonder (`wonders.avoid`), the sea or a lake, or the party's square. Who makes
them: the risen dead's "emptying" stage (the stage op "reshape": the country round the barrow dies, spreading week by
week while he walks), a dragon burning a village (`Politics.dragon_wakes`: its fields scorched), and the debug
console's `land`. What follows a change: `GameState.land_changed` (travel, caches, the route), the painter
(`ui/gfx/worldview.WorldView.ready` -> `ChunkCache.refresh`), and close-up maps already built (`local.patch_land`).
"""

from __future__ import annotations

import heapq
import math
import zlib

import numpy as np

from realmwalker.core.rng import RNG
from realmwalker.world.model import CLIFF, RAVINE

KINDS = ("rift", "blight", "dead_forest", "scorch", "drown", "crater")
BIOME_OF = {"rift": "rift", "blight": "blighted", "dead_forest": "blighted", "scorch": "scorched_land",
            "drown": "drowned", "crater": "crater"}
NEW_BIOMES = ("rift", "rift_ledge", "blighted", "scorched_land", "drowned", "crater")
FIELDS = ("biome", "relief", "elevation", "road", "river")
FORESTS = ("forest", "pine_forest", "jungle", "fey_forest")
WATER = ("ocean", "lake")
LEDGE_EVERY = 8  # a rift leaves a ledge to cross by about this often
MAX_CELLS = 80  # a change covers at most this many squares (as a wonder may)
LOG_KEEP = 64


# ---------------------------------------------------------------------------- the ledger
def ledger(world) -> list:
    return world.politics.setdefault("land", [])


def version(world) -> int:
    return int(world.politics.get("land_version", 0))


def _bump(world, cells, fields) -> int:
    v = version(world) + 1
    world.politics["land_version"] = v
    log = world.politics.setdefault("land_log", [])
    log.append([v, [[int(x), int(y)] for x, y in cells], sorted(set(fields))])
    del log[:-LOG_KEEP]
    return v


def changes_since(world, v: int) -> tuple[set, set] | None:
    """The squares and fields changed after version v, or None when the log no longer reaches back that far (then
    everything must be read again)."""
    now = version(world)
    if v >= now:
        return set(), set()
    log = world.politics.get("land_log", [])
    if not log or int(log[0][0]) > v + 1:
        return None
    cells, fields = set(), set()
    for ver, cs, fs in log:
        if int(ver) > v:
            cells.update((int(x), int(y)) for x, y in cs)
            fields.update(fs)
    return cells, fields


def biome_index(world, bid: str) -> int:
    """The index of a biome in this world's list, appending it when the world has never had it."""
    if bid not in world.biome_ids:
        world.biome_ids.append(bid)
    return world.biome_ids.index(bid)


def keep_out(world, keep=()) -> np.ndarray:
    """Where no change may fall: settlements, sites, wonders and their hearts, the sea and the lakes, the party."""
    from realmwalker.world import wonders

    mask = wonders.avoid(world)
    mask |= world.settlement_grid >= 0
    mask |= world.site_grid >= 0
    water = [i for i, b in enumerate(world.biome_ids) if b in WATER]
    if water:
        mask |= np.isin(world.biome, water)
    for x, y in list(keep) + ([world.politics["party_at"]] if world.politics.get("party_at") else []):
        if world.in_bounds(int(x), int(y)):
            mask[int(x), int(y)] = True
    return mask


def _arr(world, field: str):
    return getattr(world, field, None)


def _write(world, rec: dict, undo: bool = False) -> None:
    cells = reversed(rec["cells"]) if undo else rec["cells"]
    for x, y, field, old, new in cells:
        a = _arr(world, field)
        if a is not None:
            a[x, y] = old if undo else new


# ---------------------------------------------------------------------------- shapes
def _blob(world, seed: str, x: int, y: int, r: float, mask: np.ndarray) -> list[tuple[int, int]]:
    out = []
    R = int(math.ceil(r + 1))
    for cx in range(max(0, x - R), min(world.width, x + R + 1)):
        for cy in range(max(0, y - R), min(world.height, y + R + 1)):
            d = math.hypot(cx - x, cy - y)
            # (the ragged edge: the same squares at the same radius whatever grows later)
            edge = r + (zlib.crc32(f"{seed}/{cx},{cy}".encode()) / 0xFFFFFFFF - 0.5) * 1.2
            if d <= edge and not mask[cx, cy]:
                out.append((cx, cy))
    out.sort(key=lambda c: (math.hypot(c[0] - x, c[1] - y), c))
    return out[:MAX_CELLS]


def _rift_line(world, rng: RNG, x: int, y: int, ang: float, n: int, mask: np.ndarray) -> list[tuple[int, int]]:
    cells: list[tuple[int, int]] = []
    fx, fy = float(x), float(y)
    seen = set()
    for _ in range(n * 3):
        if len(cells) >= min(n, MAX_CELLS):
            break
        ang += rng.uniform(-0.35, 0.35)
        fx += math.cos(ang)
        fy += math.sin(ang)
        cx, cy = int(round(fx)), int(round(fy))
        if not world.in_bounds(cx, cy):
            break
        if (cx, cy) in seen:
            continue
        seen.add((cx, cy))
        if not mask[cx, cy]:  # (a town on its way is passed by: the crack runs round it, a gap is left)
            cells.append((cx, cy))
    return cells


def _flood(world, x: int, y: int, n: int, mask: np.ndarray) -> list[tuple[int, int]]:
    """The lowest country first, spreading from where the water broke out."""
    start = int(world.elevation[x, y])
    heap = [(0, x, y)]
    seen = {(x, y)}
    out = []
    while heap and len(out) < min(n, MAX_CELLS):
        _, cx, cy = heapq.heappop(heap)
        if not mask[cx, cy]:
            out.append((cx, cy))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if world.in_bounds(nx, ny) and (nx, ny) not in seen and not mask[nx, ny]:
                seen.add((nx, ny))
                e = int(world.elevation[nx, ny])
                if e - start <= 60:  # (the water does not climb the hills)
                    heapq.heappush(heap, (max(0, e - start), nx, ny))
    return out


# ---------------------------------------------------------------------------- applying
def _cell(world, out: list, x: int, y: int, field: str, new) -> None:
    a = _arr(world, field)
    if a is None:
        return
    old = a[x, y].item() if hasattr(a[x, y], "item") else a[x, y]
    new = type(old)(new)
    if old != new:
        out.append([int(x), int(y), field, old, new])
        a[x, y] = new


def make(world, kind: str, shape: dict, *, seed: str, day: float, keep=(), story=None, spread=None) -> dict | None:
    """Work a land change out from its shape (seeded), write it into the world's arrays and the ledger. None when it
    would change nothing (every square it would take is kept out, or already so)."""
    if kind not in KINDS:
        raise ValueError(f"unknown land change {kind!r}")
    rng = RNG(int(world.meta.seed), f"land/{seed}")
    mask = keep_out(world, keep)
    x, y = int(shape["x"]), int(shape["y"])
    target = BIOME_OF[kind]
    have = [i for i, b in enumerate(world.biome_ids) if b in (target, "rift_ledge") or (kind == "crater" and b == "lake")]
    cells: list = []
    if kind == "rift":
        line = _rift_line(world, rng, x, y, float(shape.get("dir", rng.uniform(0, 2 * math.pi))),
                          int(shape.get("len", 24)), mask)
        rift, ledge = biome_index(world, "rift"), biome_index(world, "rift_ledge")
        gap = rng.randint(3, LEDGE_EVERY)
        for i, (cx, cy) in enumerate(line):
            crossing = (i % LEDGE_EVERY == gap % LEDGE_EVERY) or (world.road[cx, cy] and rng.chance(0.5))
            _cell(world, cells, cx, cy, "biome", ledge if crossing else rift)
            if world.relief is not None:
                _cell(world, cells, cx, cy, "relief", int(world.relief[cx, cy]) | RAVINE)
            if not crossing:
                _cell(world, cells, cx, cy, "road", False)
                _cell(world, cells, cx, cy, "river", 0)
    elif kind in ("blight", "dead_forest", "scorch"):
        bi = biome_index(world, target)
        taken = mask | np.isin(world.biome, have)
        if kind == "dead_forest":
            taken |= ~np.isin(world.biome, [i for i, b in enumerate(world.biome_ids) if b in FORESTS])
        for cx, cy in _blob(world, f"{world.meta.seed}/{shape.get('root', seed)}", x, y, float(shape.get("r", 2)),
                            taken):
            _cell(world, cells, cx, cy, "biome", bi)
    elif kind == "drown":
        bi = biome_index(world, target)
        for cx, cy in _flood(world, x, y, int(shape.get("n", 20)), mask):
            if int(world.biome[cx, cy]) in have:
                continue
            _cell(world, cells, cx, cy, "biome", bi)
            _cell(world, cells, cx, cy, "river", 0)
    elif kind == "crater":
        r = max(1.0, float(shape.get("r", 2)))
        rim, lake = biome_index(world, "crater"), biome_index(world, "lake")
        for cx, cy in _blob(world, f"{world.meta.seed}/{seed}", x, y, r, mask):
            d = math.hypot(cx - x, cy - y)
            inner = r >= 2 and d <= r - 1.0
            _cell(world, cells, cx, cy, "biome", lake if inner else rim)
            e = int(world.elevation[cx, cy])
            _cell(world, cells, cx, cy, "elevation", -6 if inner else max(1, e) + 30)
            _cell(world, cells, cx, cy, "road", False)
            _cell(world, cells, cx, cy, "river", 0)
            if world.relief is not None and not inner:
                _cell(world, cells, cx, cy, "relief", int(world.relief[cx, cy]) | CLIFF)
    if not cells:
        return None
    rec = {"id": int(world.politics.get("land_next", len(ledger(world)))), "kind": kind, "day": float(day),
           "seed": str(seed), "shape": {k: (float(v) if isinstance(v, float) else v) for k, v in shape.items()},
           "cells": cells}
    world.politics["land_next"] = rec["id"] + 1
    if story is not None:
        rec["story"] = story
    if spread is not None:
        rec["spread"] = spread
    rec["v"] = _bump(world, {(c[0], c[1]) for c in cells}, {c[2] for c in cells})
    ledger(world).append(rec)
    return rec


def record(world, rid: int) -> dict | None:
    return next((r for r in ledger(world) if int(r["id"]) == int(rid)), None)


def undo(world, rid: int) -> bool:
    """Put the land back as it was before this change (the record leaves the ledger). Refused (False) while a later
    change lies over the same squares: those must be undone first."""
    led = ledger(world)
    rec = record(world, rid)
    if rec is None:
        return False
    i = led.index(rec)
    mine = {(c[0], c[1], c[2]) for c in rec["cells"]}
    if any((c[0], c[1], c[2]) in mine for later in led[i + 1:] for c in later["cells"]):
        return False
    _write(world, rec, undo=True)
    led.pop(i)
    _bump(world, {(c[0], c[1]) for c in rec["cells"]}, {c[2] for c in rec["cells"]})
    return True


def changed_at(world, x: int, y: int, since: int = 0) -> list[dict]:
    """The records after version `since` that changed the land of this square."""
    return [r for r in ledger(world) if int(r.get("v", 0)) > since
            and any(c[0] == x and c[1] == y and c[2] == "biome" for c in r["cells"])]


def check(world) -> list[str]:
    """The ledger replays (autoplay's `_check_land`): undone in reverse on a copy, each change finds its own new
    values; done again, each finds its old ones; and the result is today's land."""
    out = []
    led = ledger(world)
    copy = {f: _arr(world, f).copy() for f in FIELDS if _arr(world, f) is not None}
    for rec in reversed(led):
        for x, y, field, old, new in reversed(rec["cells"]):
            if field not in copy:
                continue
            if copy[field][x, y] != new:
                out.append(f"land change {rec['id']} ({rec['kind']}): {field} at {x},{y} is {copy[field][x, y]}, "
                           f"not {new}")
            copy[field][x, y] = old
    for rec in led:
        for x, y, field, old, new in rec["cells"]:
            if field in copy:
                copy[field][x, y] = new
    for f, a in copy.items():
        if not np.array_equal(a, _arr(world, f)):
            out.append(f"the land ledger does not give today's {f}")
    if len(set(int(r["id"]) for r in led)) != len(led):
        out.append("two land changes share an id")
    for r in led:
        if len(r["cells"]) > MAX_CELLS * 4:
            out.append(f"land change {r['id']} is too big ({len(r['cells'])} cells)")
    return out


# ---------------------------------------------------------------------------- while you play
def weekly(pol) -> list[dict]:
    """A blight that spreads grows by a ring a week while the will behind it lasts (Politics.advance)."""
    from realmwalker.world import threats

    w = pol.w
    made = []
    for rec in list(ledger(w)):
        sp = rec.get("spread")
        if not sp:
            continue
        t = threats.records(w).get(str(sp.get("threat")))
        if t is None or t.get("state") not in threats.LIVE or not threats.villain_lives(w, t):
            rec.pop("spread", None)
            continue
        r = float(rec["shape"].get("r", 2))
        if r >= float(sp.get("max", 5)):
            rec.pop("spread", None)
            continue
        shape = dict(rec["shape"], r=r + 1)
        shape.setdefault("root", rec["seed"])  # (the same ragged edge, a ring further out)
        new = make(w, rec["kind"], shape, seed=f"{rec['seed']}/{int(r + 1)}", day=pol.day, story=rec.get("story"),
                   spread=dict(sp))
        rec.pop("spread", None)
        if new is None:  # (nothing left to take at that ring: keep the next week's try on the old record)
            rec["shape"] = shape
            rec["spread"] = dict(sp)
            continue
        made.append(new)
    return made
