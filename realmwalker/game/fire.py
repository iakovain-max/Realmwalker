"""Fire on close-up maps (Expansion 6 B.7, docs/ADVENTURES.md §8.14): a burning street burns. Show, don't tell.

**Live fire is an overlay, not terrain.** `lm.meta["fire"]` = {"x,y": [stage, steps]} (JSON-native, saved with the
map): stage 0 catching, 1 ablaze, 2 dying, 3 burned out and waiting for the next batch. A burning square blocks
everyone through one mask: townlife's walk grid (changed square by square: `townlife.patch`), the bands' steps
(`encounters.move_actors`) and yours (`GameState._move_local`). A square is lit only while nobody stands on it.

Spread, a step of the town's time at a time (`townlife.tick` calls `tick`, under a millisecond: it visits only the
burning squares and their neighbours): a square burns for as many steps as data/marks.json "fire" `burns` says for what
it is (thatch fast, timber slower, furniture between), and each step may light a neighbour that burns (by the
neighbour's own chance, more downwind, less in rain; stone, water and wells never catch). Burned-out squares are
written to terrain in batches, every FLUSH steps (their `into` forms: charred floor and walls, embers, scorched earth,
broken doors, now and then a fallen beam under a roof), and the close-up map's art is patched square by square
(`ui/gfx/localview.LocalArt.patch`). A building burned past `shell` of its squares is a roofless shell, its trade shut
(`placemarks.shut`). What burned is kept in `lm.meta["burnt"]` [[x, y, old terrain, day]] and the shells' old looks in
`lm.meta["shells"]`, so a town mends: embers cool to scorched earth after half a day, and once no fire mark is left
and MEND_DAYS have passed, the burned squares are built again as they were.

Fire spreads only on a town's map. A town marked "burning" (world/marks.py) has a few buildings alight when you walk
in (`kindle`). Fire written back to a wild map or a dungeon level from a fight burns out at once into scorched ground.

    burning(lm, x, y)             is this square alight now
    blocked(lm)                   a mask of the squares fire blocks (None: no fire)
    light(game, lm, cells)        set squares alight (only those that burn and that nobody stands on)
    tick(game, lm)                one step of the fire (from townlife.tick)
    settle(game, lm)              the fire moved on for the time that passed (townlife.settle, entering, leaving)
    kindle(game, lm, s)           a town marked "burning" has buildings alight
    mend(game, lm, s)             embers cool; a town with no fire mark builds again what burned long ago
    unsafe(lm, spot)              townsfolk keep away from here (a burning building, beside a fire)

In battle (`on_battle_start`, from fight.start_battle after arena.build): ownerless fire zones on the field's burning
squares and smoke beside them; `Battle.round_hooks` spread it each round with `Battle._ignite`'s numbers (1d6 fire,
Dexterity DC 10), burn squares out and bring burning timber walls down (telegraphed the round before). Only on a
field marked burning do houses' timbers, floors and furniture catch (`Field.flammable` widened there, never
`grid.FLAMMABLE` itself: a Fireball in an ordinary inn starts no blaze). `write_back` (from fight.finish_battle)
returns what still burns, and what burned, to the map.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

STEP = 6  # seconds of the world in a step of fire (townlife.STEP_SECONDS)
FLUSH = 10  # steps between batches of burned-out squares written to terrain
SETTLE_MOST = 120  # steps played out when time has jumped (twelve minutes); beyond that, what burns burns out
MEND_DAYS = 120  # a burned square built again (once no fire mark is left on the town)
COOL_DAYS = 0.5  # embers go cold
SMOKE = 3  # battle: smoke drifts this many squares from a fire
WALL_FALLS = 4  # battle: rounds a timber wall burns before it comes down
OCC_NEAR = 1  # nobody stands on a square that is lit

_mats: dict = {}  # lm.key -> (len(terrain_ids), burns list, catch list, into list): never saved
_weather: dict = {}  # (world minute // 10) -> (wind dx, dy, strength, wet)
_buildings: dict = {}  # lm.key -> (fire version, set of building indices alight)
_grids: dict = {}  # lm.key -> (terrain stamp, catch chance per square)

NEIGHBOURS = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))


def _spec(game) -> dict:
    return getattr(game.tables, "fire", None) or {}


def _key(x: int, y: int) -> str:
    return f"{x},{y}"


@lru_cache(maxsize=65536)
def _xy(key: str) -> tuple[int, int]:
    a, b = key.split(",")
    return int(a), int(b)


def _catch_grid(game, lm, catch) -> np.ndarray:
    """Each square's chance a step to catch from a burning neighbour (cached while the map's terrain is unchanged)."""
    stamp = (len(lm.terrain_ids), hash(lm.terrain.tobytes()))
    got = _grids.get(lm.key)
    if got is None or got[0] != stamp:
        got = (stamp, np.asarray(catch, np.float32)[lm.terrain])
        if len(_grids) > 4:
            _grids.clear()
        _grids[lm.key] = got
    return got[1]


def _mask(lm, fire) -> np.ndarray:
    m = np.zeros((lm.width, lm.height), bool)
    if fire:
        pts = np.array([_xy(k) for k in fire], np.int32)
        m[pts[:, 0], pts[:, 1]] = True
    return m


# ---------------------------------------------------------------------------- what burns
def _materials(game, lm):
    """Per stored terrain index: steps it burns, chance a step to catch, what it becomes (cached per map)."""
    got = _mats.get(lm.key)
    if got is not None and got[0] == len(lm.terrain_ids):
        return got
    spec = _spec(game)
    burns = spec.get("burns", {})
    into = spec.get("into", {})
    T = game.tables.terrain
    steps, catch, becomes = [], [], []
    for name in lm.terrain_ids:
        b = burns.get(name)
        steps.append(int(b[0]) if b else 0)
        catch.append(float(b[1]) if b else 0.0)
        tags = T.tags[T.index[name]] if name in T.index else ()
        default = "charred_wall" if "wall" in tags else "charred_floor" if "floor" in tags else \
            "embers" if "furniture" in tags or "bed" in tags else "scorched"
        becomes.append(into.get(name, default))
    got = (len(lm.terrain_ids), steps, catch, becomes)
    _mats[lm.key] = got
    return got


def burns(game, lm, x: int, y: int) -> bool:
    _, steps, catch, _ = _materials(game, lm)
    i = int(lm.terrain[x, y])
    return steps[i] > 0 and catch[i] > 0


def burning(lm, x: int, y: int) -> bool:
    fire = (lm.meta or {}).get("fire")
    return bool(fire) and _key(x, y) in fire


def blocked(lm) -> np.ndarray | None:
    """The squares fire blocks on this map (None when nothing burns)."""
    fire = (lm.meta or {}).get("fire")
    if not fire:
        return None
    return _mask(lm, fire)


def alight_buildings(lm) -> set:
    """The buildings that have fire in them."""
    fire = (lm.meta or {}).get("fire")
    if not fire:
        return set()
    v = (lm.meta.get("fire_n"), len(fire), next(iter(fire)))
    got = _buildings.get(lm.key)
    if got is not None and got[0] == v:
        return got[1]
    out = set()
    grid = None
    for k in fire:
        x, y = _xy(k)
        b = lm.building_at(x, y)
        if b is not None:
            if grid is None:
                grid = lm._building_grid
            out.add(int(grid[x, y]))
    _buildings[lm.key] = (v, out)
    return out


def unsafe(lm, spot) -> bool:
    """Townsfolk keep away: a building with fire in it, or beside a fire."""
    fire = (lm.meta or {}).get("fire")
    if not fire:
        return False
    x, y = int(spot[0]), int(spot[1])
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if _key(x + dx, y + dy) in fire:
                return True
    if lm.building_at(x, y) is not None:
        return int(lm._building_grid[x, y]) in alight_buildings(lm)
    return False


def _occupied(game, lm) -> set:
    taken = set()
    if game.local is lm:
        taken.add((game.player.lx, game.player.ly))
    for a in lm.actors:
        taken.add((a.x, a.y))
    if lm.kind == "settlement":
        from realmwalker.game.people import npcs_in, settlement_of

        s = settlement_of(game, lm)
        if s is not None:
            for n in npcs_in(game.world, s.id):
                if n.alive and n.present:
                    taken.add((n.x, n.y))
    return taken


def light(game, lm, cells, *, taken: set | None = None) -> int:
    """Set squares alight: only those that burn and that nobody stands on. The number lit."""
    fire = lm.meta.setdefault("fire", {})
    taken = _occupied(game, lm) if taken is None else taken
    new = []
    for x, y in cells:
        x, y = int(x), int(y)
        if not lm.in_bounds(x, y) or (x, y) in taken or _key(x, y) in fire or not burns(game, lm, x, y):
            continue
        fire[_key(x, y)] = [0, 0]
        new.append((x, y))
    if new:
        _blocked_now(game, lm, new)
    if not fire:
        lm.meta.pop("fire", None)
    elif "fire_at" not in lm.meta:
        lm.meta["fire_at"] = _now(game)
    return len(new)


def _blocked_now(game, lm, cells) -> None:
    """Walkers learn of newly burning (or newly cold) squares, square by square."""
    if lm.kind == "settlement":
        from realmwalker.game import townlife

        townlife.patch(game, lm, cells)


def _now(game) -> int:
    return int(game.world.time) * 60 + int(getattr(game.player, "seconds", 0))


# ---------------------------------------------------------------------------- the weather's say
def _air(game) -> tuple[float, float, float, float]:
    """The wind's way (a unit step), its strength 0..1, and how wet it is 0..1 (cached by ten minutes)."""
    slot = int(game.world.time) // 10
    got = _weather.get(slot)
    if got is not None:
        return got
    try:
        w = game.weather
        kph, wet = float(w.wind), float(w.precip) if (w.raining or w.snowing) else 0.0
    except Exception:  # (a map with no weather to ask: a test's bare world)
        kph, wet = 10.0, 0.0
    day = int(game.world.time) // 1440
    ang = (((day * 2654435761) & 0xFFFF) / 65535.0 - 0.5) * math.pi * 0.9  # (the fronts go west to east)
    got = (math.cos(ang), math.sin(ang), min(1.0, kph / 40.0), wet)
    if len(_weather) > 64:
        _weather.clear()
    _weather[slot] = got
    return got


# ---------------------------------------------------------------------------- a step of fire
def tick(game, lm, rng=None) -> int:
    """One step of the fire on a town's map: each square burns on, may light its neighbours, and burns out; every
    FLUSH steps the burned-out squares are written. Returns the squares newly lit."""
    fire = (lm.meta or {}).get("fire")
    if not fire:
        return 0
    lm.meta["fire_at"] = _now(game)
    if lm.kind != "settlement":
        burn_out_all(game, lm)
        return 0
    n = int(lm.meta.get("fire_n", 0)) + 1
    lm.meta["fire_n"] = n
    _, steps, catch, _ = _materials(game, lm)
    terr = lm.terrain
    W, H = lm.width, lm.height
    xs, ys, heat = [], [], []
    for k, rec in fire.items():  # (each square burns on: the only Python loop, over the burning squares alone)
        stage, t = rec
        if stage >= 3:
            continue
        x, y = _xy(k)
        last = max(1, steps[terr.item(x, y)])
        t += 1
        if t >= last:
            rec[0], rec[1] = 3, t
            continue
        stage = 0 if t < last * 0.2 else 1 if t < last * 0.8 else 2
        rec[0], rec[1] = stage, t
        xs.append(x)
        ys.append(y)
        heat.append(1.0 if stage == 1 else 0.45)
    want: dict = {}
    if xs:
        wx, wy, strength, wet = _air(game)
        damp = max(0.15, 1.0 - 0.8 * wet)
        C = _catch_grid(game, lm, catch)
        alight = _mask(lm, fire)
        xs_, ys_, heat_ = np.array(xs), np.array(ys), np.array(heat) * damp
        rolls = (rng.numpy("roll") if rng is not None else game.world.rng.child(f"fire/{lm.key}/{n}").numpy("roll")) \
            .random((8, len(xs)))
        for d, (dx, dy) in enumerate(NEIGHBOURS):  # (the neighbours, all at once)
            nx, ny = xs_ + dx, ys_ + dy
            ok = (nx >= 0) & (nx < W) & (ny >= 0) & (ny < H)
            nx, ny = np.where(ok, nx, 0), np.where(ok, ny, 0)
            diag = dx != 0 and dy != 0
            along = (dx * wx + dy * wy) / (1.41 if diag else 1.0)
            p = C[nx, ny] * heat_ * (1.0 + 0.9 * strength * along) * (0.75 if diag else 1.0)
            hit = ok & ~alight[nx, ny] & (rolls[d] < p)
            for x, y in zip(nx[hit].tolist(), ny[hit].tolist()):
                want[(x, y)] = None
    lit = 0
    if want:
        taken = _occupied(game, lm)
        lit = light(game, lm, list(want), taken=taken)
        if lit and game.local is lm:
            _cry(game, lm, list(want), taken)
    if n % FLUSH == 0:
        flush(game, lm)
    return lit


def _cry(game, lm, cells, taken) -> None:
    """Someone near calls out when a building catches."""
    spec = _spec(game)
    cries = spec.get("cries")
    if not cries or not lm.buildings:
        return
    done = lm.meta.setdefault("fire_cried", [])
    for x, y in cells:
        b = lm.building_at(x, y)
        if b is None:
            continue
        i = int(lm._building_grid[x, y])
        if i in done:
            continue
        done.append(i)
        from realmwalker.game import townlife
        from realmwalker.game.people import npcs_in, settlement_of

        s = settlement_of(game, lm)
        near = [n for n in npcs_in(game.world, s.id) if n.alive and n.present and not townlife.asleep(game, n)
                and max(abs(n.x - x), abs(n.y - y)) <= 8] if s is not None else []
        if not near:
            continue
        who = min(near, key=lambda n: (abs(n.x - x) + abs(n.y - y), n.id))
        what = _building_word(b)
        line = cries[(i * 7 + len(done)) % len(cries)].replace("{what}", what)
        townlife.speak(game, lm, who, line)
        return


def _building_word(b) -> str:
    return {"inn": "the inn", "caravanserai": "the caravanserai", "temple": "the temple", "smithy": "the smithy",
            "store": "the store", "keep": "the keep", "stable": "the stables", "barn": "the barn",
            "healer": "the healer's", "guild": "the guildhall"}.get(b.kind, "the houses")


def flush(game, lm) -> list[tuple[int, int]]:
    """Write the burned-out squares to terrain, in one batch: their burnt forms; buildings burned past their share
    become shells. Returns the squares written."""
    fire = (lm.meta or {}).get("fire")
    if not fire:
        return []
    out = [k for k, rec in fire.items() if rec[0] >= 3]
    if not out:
        return []
    _, _, _, becomes = _materials(game, lm)
    from realmwalker.game.dungeon import set_terrain

    spec = _spec(game)
    beams = float(spec.get("beams", 0.0))
    day = round(float(game.world.time) / 1440.0, 3)
    burnt = lm.meta.setdefault("burnt", [])
    cells = []
    touched = set()
    for k in out:
        del fire[k]
        x, y = _xy(k)
        i = int(lm.terrain[x, y])
        old = lm.terrain_ids[i]
        to = becomes[i]
        b = lm.building_at(x, y)
        if b is not None:
            touched.add(int(lm._building_grid[x, y]))
            if to == "charred_floor" and (x * 73 + y * 151) % 1000 < beams * 1000:
                to = "fallen_beam"
        if to and to != old:
            set_terrain(lm, x, y, to)
            burnt.append([x, y, old, day])
        cells.append((x, y))
    if not fire:
        lm.meta.pop("fire", None)
        lm.meta.pop("fire_cried", None)
    _mats.pop(lm.key, None)
    _shells(game, lm, touched)
    _after_terrain(game, lm, cells)
    return cells


def _shells(game, lm, touched) -> None:
    share = float(_spec(game).get("shell", 0.35))
    shells = lm.meta.setdefault("shells", {})
    if not touched:
        return
    burnt_at = {(int(c[0]), int(c[1])) for c in lm.meta.get("burnt", ())}
    for i in touched:
        if str(i) in shells or not (0 <= i < len(lm.buildings)):
            continue
        b = lm.buildings[i]
        foot = [(x, y) for x in range(b.x, b.x + b.w) for y in range(b.y, b.y + b.h)
                if lm.in_bounds(x, y) and b.contains(x, y)]
        if foot and sum(1 for c in foot if c in burnt_at) >= share * len(foot):
            shells[str(i)] = dict(b.look or {})
            look = dict(b.look or {})
            look["walls"] = "charred"
            look["roof"] = "none"
            b.look = look
    if not shells:
        lm.meta.pop("shells", None)


def _after_terrain(game, lm, cells) -> None:
    if hasattr(game, "_remaps"):
        game._remaps.pop(lm.key, None)
    _blocked_now(game, lm, cells)


def burn_out_all(game, lm) -> list[tuple[int, int]]:
    """Everything still burning burns out now (time has jumped; a wild map or a dungeon: fire does not spread there,
    and what was alight is scorched ground)."""
    fire = (lm.meta or {}).get("fire")
    if not fire:
        return []
    if lm.kind != "settlement":
        from realmwalker.game.dungeon import set_terrain

        _, _, _, becomes = _materials(game, lm)
        cells = []
        for k in list(fire):
            x, y = _xy(k)
            i = int(lm.terrain[x, y])
            to = becomes[i]
            if to in ("charred_floor", "charred_wall", "fallen_beam"):
                to = lm.terrain_ids[i] if lm.kind == "dungeon" else "scorched"
            set_terrain(lm, x, y, to if lm.kind != "dungeon" or to != "scorched" else lm.terrain_ids[i])
            cells.append((x, y))
        lm.meta.pop("fire", None)
        _mats.pop(lm.key, None)
        _after_terrain(game, lm, cells)
        return cells
    for rec in fire.values():
        rec[0] = 3
    return flush(game, lm)


def settle(game, lm) -> None:
    """The fire moves on for the time that has passed since its last step (at most SETTLE_MOST steps played out;
    after longer than that, whatever was burning has burned out)."""
    if lm is None or not (lm.meta or {}).get("fire"):
        return
    now = _now(game)
    last = int(lm.meta.get("fire_at", now))
    steps = max(0, (now - last) // STEP)
    for _ in range(min(steps, SETTLE_MOST)):
        tick(game, lm)
        if not lm.meta.get("fire"):
            break
    if steps > SETTLE_MOST:
        burn_out_all(game, lm)
    else:
        flush(game, lm)
    if lm.meta.get("fire"):
        lm.meta["fire_at"] = now


# ---------------------------------------------------------------------------- a town that burns, a town that mends
def kindle(game, lm, s) -> int:
    """A town marked "burning" has a few buildings alight when you walk in: the nearest to the burned ones that are
    still standing (once a burning mark)."""
    if lm is None or lm.kind != "settlement" or s is None or "burning" not in s.status:
        return 0
    from realmwalker.world import marks

    since = marks.since(s, "burning")
    if lm.meta.get("kindled") == since:
        return 0
    lm.meta["kindled"] = since
    lo, hi = (_spec(game).get("kindle") or [2, 4])
    count = int(lo) + (int(s.id) * 31 + int(since or 0)) % max(1, int(hi) - int(lo) + 1)
    shut = set()
    for rec in (lm.meta.get("marks") or {}).values():
        shut |= set(rec.get("shut", ()))
    burned = [lm.buildings[i] for i in shut if 0 <= i < len(lm.buildings)]
    cx = sum(b.x + b.w / 2 for b in burned) / len(burned) if burned else lm.width / 2
    cy = sum(b.y + b.h / 2 for b in burned) / len(burned) if burned else lm.height / 2
    keep = {"keep", "temple"}
    pool = [i for i, b in enumerate(lm.buildings) if i not in shut and b.kind not in keep]
    pool.sort(key=lambda i: ((lm.buildings[i].x + lm.buildings[i].w / 2 - cx) ** 2
                             + (lm.buildings[i].y + lm.buildings[i].h / 2 - cy) ** 2, i))
    lit = 0
    taken = _occupied(game, lm)
    for i in pool[:count]:
        b = lm.buildings[i]
        cells = [(x, y) for x in range(b.x, b.x + b.w) for y in range(b.y, b.y + b.h)
                 if lm.in_bounds(x, y) and b.contains(x, y) and (x, y) != tuple(b.door)]
        seeds = [c for c in cells if (c[0] * 17 + c[1] * 29 + i) % 5 == 0][:6] or cells[:3]
        lit += light(game, lm, seeds, taken=taken)
    return lit


def mend(game, lm, s) -> bool:
    """Time heals a burned town: embers cool into scorched earth; once no fire mark is left on it and MEND_DAYS have
    passed, the burned squares are built again and the shells roofed. True if anything changed."""
    burnt = (lm.meta or {}).get("burnt")
    if not burnt:
        return False
    from realmwalker.game.dungeon import set_terrain

    now = float(game.world.time) / 1440.0
    marked = s is not None and any(m in s.status for m in ("burning", "burned", "rebuilding", "sacked"))
    fire = lm.meta.get("fire") or {}
    cells = []
    keep = []
    for rec in burnt:
        x, y, old, day = int(rec[0]), int(rec[1]), rec[2], float(rec[3])
        here = lm.terrain_ids[int(lm.terrain[x, y])]
        if not marked and now - day >= MEND_DAYS and not fire:
            set_terrain(lm, x, y, old)
            cells.append((x, y))
            continue
        if here == "embers" and now - day >= COOL_DAYS:
            set_terrain(lm, x, y, "scorched")
            cells.append((x, y))
        keep.append(rec)
    if keep:
        lm.meta["burnt"] = keep
    else:
        lm.meta.pop("burnt", None)
        for i, look in (lm.meta.pop("shells", None) or {}).items():
            if 0 <= int(i) < len(lm.buildings):
                lm.buildings[int(i)].look = dict(look)
    if cells:
        _mats.pop(lm.key, None)
        _after_terrain(game, lm, cells)
    return bool(cells)


def shell(lm, i: int) -> bool:
    """A building the fire has made a shell (its trade shut until it is built again)."""
    return str(i) in ((lm.meta or {}).get("shells") or {})


# ---------------------------------------------------------------------------- fire in battle
HOUSE_BURNS = ("floor_wood", "floor_earth", "rug_floor", "rug", "doorway", "door_closed", "door_open", "wall_wood",
               "wall_logs", "wall_plaster", "wall_felt", "table", "bed", "bench", "chair", "stool", "counter", "shelf",
               "bookcase", "wardrobe", "trunk", "barrels", "crates", "sacks", "cart", "stall", "boardwalk", "fence",
               "pew", "scaffold", "barricade")
TIMBER_WALLS = ("wall_wood", "wall_logs", "wall_plaster", "palisade")


def on_battle_start(battle, game) -> list[str]:
    """A fight on a burning map: the burning squares are ownerless fire, smoke drifts beside them, houses' timbers
    catch, and each round the fire spreads (Battle.round_hooks)."""
    lm = game.local
    fld = getattr(battle, "field", None)
    if lm is None or fld is None or getattr(fld, "cut_from", None) != lm.key or not lm.meta.get("fire"):
        return []
    from realmwalker.rules.combat import Zone

    ox, oy = fld.origin
    cells = set()
    for k in lm.meta["fire"]:
        x, y = _xy(k)
        if fld.in_bounds(x - ox, y - oy):
            cells.add((x - ox, y - oy))
    if not cells:
        return []
    T = game.tables.terrain
    burns_here = np.array([T.ids[i] in HOUSE_BURNS for i in range(len(T.ids))], bool)
    fld.flammable = fld.flammable | burns_here[fld.terrain]
    fld.__dict__["burning"] = True
    battle._add_zone(Zone(battle._zone_id(), "fire", set(cells), owner=None, rounds=-1, save="dex", dc=10,
                          damage="1d6", damage_type="fire", on_save="none"))
    _smoke(battle, cells)
    battle.__dict__.setdefault("walls_burning", {})
    battle.round_hooks.append(_round)
    return ["<danger>The fire is all round you: smoke rolls along the ground, and the heat beats at your face.</>"]


def _fire_zone(battle):
    return next((z for z in battle.zones if z.kind == "fire" and z.owner is None and z.rounds < 0), None)


def _smoke(battle, cells) -> None:
    """Smoke beside the fire, drifting a few squares: lightly obscuring (a fog that does not block sight)."""
    from realmwalker.rules.combat import Zone

    fld = battle.field
    near = set()
    for x, y in cells:
        for dx in range(-SMOKE, SMOKE + 1):
            for dy in range(-1, 2):
                c = (x + dx, y + dy - 1)
                if fld.in_bounds(*c) and c not in cells and (abs(dx) + abs(dy)) <= SMOKE:
                    near.add(c)
    old = next((z for z in battle.zones if z.kind == "smoke" and z.owner is None), None)
    if old is not None:
        old.cells = near
        battle._event("zone_move", id=old.id, cells=sorted(near))
    elif near:
        battle._add_zone(Zone(battle._zone_id(), "smoke", near, owner=None, rounds=-1))


def _round(battle) -> None:
    """A round of fire on the field: it spreads to what burns (not under anyone), squares burn out into scorched
    ground, and a burning timber wall groans and then comes down."""
    z = _fire_zone(battle)
    if z is None:
        return
    fld = battle.field
    rng = battle.rng
    age = battle.__dict__.setdefault("fire_age", {})
    walls = battle.__dict__.setdefault("walls_burning", {})
    taken = {c for f in battle.fighters if f.active for c in f.cells}
    new = set()
    for x, y in list(z.cells):
        age[(x, y)] = age.get((x, y), 0) + 1
        for dx, dy in NEIGHBOURS:
            c = (x + dx, y + dy)
            if c in z.cells or c in new or not fld.in_bounds(*c) or c in taken:
                continue
            if fld.flammable[c] and rng.chance(0.3):
                new.add(c)
            elif fld.solid[c] and fld.name(*c) in TIMBER_WALLS and c not in walls and rng.chance(0.25):
                walls[c] = 0
    out = {c for c, n in age.items() if n >= 4 and c in z.cells}
    for c in out:
        z.cells.discard(c)
        del age[c]
        name = fld.name(*c)
        if fld.walk[c] or fld.flammable[c]:
            fld.terrain[c] = battle.t.terrain.index["scorched"]
    if out:
        fld._derive()
    if new:
        z.cells |= new
        battle.say("The fire spreads.", "danger")
    battle._event("zone_move", id=z.id, cells=sorted(z.cells))
    for c, n in list(walls.items()):
        walls[c] = n + 1
        if walls[c] == WALL_FALLS - 1:
            battle.say("The beams groan overhead.", "warn")
        elif walls[c] >= WALL_FALLS:
            del walls[c]
            _wall_falls(battle, c)
    _smoke(battle, z.cells)
    if not z.cells:
        battle._remove_zone(z)


def _wall_falls(battle, c) -> None:
    """A burning wall comes down: rubble where it stood, and whoever is beside it is struck and knocked down."""
    from realmwalker.core import dice

    fld = battle.field
    fld.set_terrain(c[0], c[1], "rubble")
    battle.say("A burning wall comes down in a rush of sparks!", "danger")
    battle._event("collapse", x=c[0], y=c[1])
    for f in battle.fighters:
        if not f.active or max(abs(f.x - c[0]), abs(f.y - c[1])) > 1:
            continue
        if battle.check(f, "acrobatics", 12, why="the falling wall"):
            battle.say(f"{f.the_name} leaps clear of the falling timbers.", "info")
            continue
        battle._hit(None, f, dice.roll("2d6", battle.rng).total, "bludgeoning", crit=False, weapon="falling timbers")
        if f.active and "prone" not in f.conditions:
            f.conditions["prone"] = -1
            battle._event("prone", who=f.id)


def write_back(game, battle) -> None:
    """The field's fire, back on the map it was cut from: what still burns burns on there (a town) or is scorched
    ground (anywhere else); what burned out is scorched."""
    lm = game.local
    fld = getattr(battle, "field", None)
    if lm is None or fld is None or getattr(fld, "cut_from", None) != lm.key:
        return
    z = next((z for z in battle.zones if z.kind == "fire" and (z.owner is None or z.rounds >= 0)), None)
    ox, oy = fld.origin
    from realmwalker.game.dungeon import set_terrain

    scorched = battle.t.terrain.index.get("scorched")
    cells = []
    for x in range(fld.width):
        for y in range(fld.height):
            if int(fld.terrain[x, y]) == scorched and lm.in_bounds(x + ox, y + oy):
                old = lm.terrain_ids[int(lm.terrain[x + ox, y + oy])]
                if old != "scorched":
                    set_terrain(lm, x + ox, y + oy, "scorched")
                    lm.meta.setdefault("burnt", []).append([x + ox, y + oy, old, round(game.world.time / 1440.0, 3)])
                    cells.append((x + ox, y + oy))
    if cells:
        _mats.pop(lm.key, None)
        _after_terrain(game, lm, cells)
    burning = [(x + ox, y + oy) for x, y in (z.cells if z is not None else ())]
    for z_ in battle.zones:  # (the ground a spell set alight - straw, hay, dry grass - burns on in a town)
        if z_.kind == "fire" and z_ is not z and z_.owner is not None and not z_.spell:
            burning += [(x + ox, y + oy) for x, y in z_.cells if fld.flammable[x, y]]
    if burning:
        lit_now = set(lm.meta.get("fire") or {})
        light(game, lm, [c for c in burning if _key(*c) not in lit_now], taken={(game.player.lx, game.player.ly)})
        if lm.kind != "settlement":
            burn_out_all(game, lm)
