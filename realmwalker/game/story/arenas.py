"""A finale's arena (docs/ADVENTURES.md §5.8, Expansion 6 E.5): the place the boss stands is dressed for the fight.

The blueprint's finale names the arenas it may be fought in (`finale.arenas`); adventures.json "arenas" says where
each fits (`styles`: the dungeon styles of the level; `wild`: a field laid on the land) and its words (`enter`, said as
the fight begins; `change`, said when the boss's second phase changes it). The first time the finale's field is built
one of those that fit is chosen for good (`adv["finale"]["arena"]`, by the world's dice).

Each arena is two pieces of code, by id:
    ARENAS[id](terrain, tables, lead, foe_at, rng) -> {"lights", "fires", "marks"} or None
        lays it on the field's terrain before the field is made (game/arena.build: lead is where the party stands,
        foe_at the boss); only open ground is touched, nobody starts inside anything, and the two sides are joined
        again afterwards. `marks` (squares by what they are) go on the field as `field.arena`.
    CHANGES[id](battle, boss, spec, marks) -> None
        what the boss's second phase does to it (a battle phase hook: rules/engine/handlers/bosses.after_damage):
        the sarcophagi open and the raised climb out of them, the pillars crack and fall, the circle flares into
        burning ground, the floor by the chasm falls away, the parapet crumbles, the fire leaps to the next roofs.

The burning village is a field of the land (game/arena.FIELDS too: a set piece's battle on the road), its houses'
timbers catching as the fire spreads (game/fire.py).
"""

from __future__ import annotations

import math

import numpy as np

ARENAS: dict[str, object] = {}
CHANGES: dict[str, object] = {}


def arena(name: str):
    def wrap(fn):
        ARENAS[name] = fn
        return fn
    return wrap


def change(name: str):
    def wrap(fn):
        CHANGES[name] = fn
        return fn
    return wrap


# ---------------------------------------------------------------------------- choosing
def spec(game) -> dict:
    return game.tables.adventures.get("arenas", {})


def choose(game, adv: dict, style: str | None) -> str | None:
    """The arena of this tale's finale for a field of this dungeon style (None: on the land), chosen once."""
    fin = adv.get("finale") or {}
    if "arena" in fin:
        return fin["arena"] or None
    bp = game.tables.adventures["blueprints"][adv["blueprint"]]
    specs = spec(game)
    fits = [a for a in bp["finale"].get("arenas", ()) if a in ARENAS and a in specs and
            (style in specs[a].get("styles", ()) if style is not None else specs[a].get("wild", False))]
    pick = game.world.rng.child(f"arena/{adv['id']}").choice(fits) if fits else ""
    fin["arena"] = pick
    return pick or None


def lay(game, adv: dict, style: str | None, terrain, lead, foe_at, rng) -> dict | None:
    """Dress the finale's terrain (game/arena.build). Returns {"id", "lights", "fires", "marks"} or None."""
    aid = choose(game, adv, style)
    if aid is None:
        return None
    work = terrain.copy()  # (laid on a copy: an arena that does not fit leaves the ground as it was)
    out = ARENAS[aid](work, game.tables, lead, foe_at, rng)
    if out is None:
        return None
    _way_off(work, game.tables, lead)
    terrain[...] = work
    out["id"] = aid
    return out


def _way_off(terrain, tables, lead) -> None:
    """The party can always get away (law 3: no place here seals): if no edge of the field can be walked to from
    where it stands, a way is cut to the nearest edge (the tower's stair, a gap in the rubble)."""
    from collections import deque

    W, H = terrain.shape
    walk = tables.terrain.walk[terrain]
    seen = {lead}
    todo = deque([lead])
    while todo:
        x, y = todo.popleft()
        if x in (0, W - 1) or y in (0, H - 1):
            return
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy)
                if 0 <= n[0] < W and 0 <= n[1] < H and n not in seen and walk[n]:
                    seen.add(n)
                    todo.append(n)
    edges = [(0, lead[1]), (W - 1, lead[1]), (lead[0], 0), (lead[0], H - 1)]
    end = min(edges, key=lambda e: abs(e[0] - lead[0]) + abs(e[1] - lead[1]))
    floor = tables.terrain.index["flagstones" if "flagstones" in tables.terrain.index else "dirt"]
    steps = max(abs(end[0] - lead[0]), abs(end[1] - lead[1]))
    for i in range(steps + 1):
        x = round(lead[0] + (end[0] - lead[0]) * i / max(1, steps))
        y = round(lead[1] + (end[1] - lead[1]) * i / max(1, steps))
        if not walk[x, y]:
            terrain[x, y] = floor


def on_finale(battle, game, adv: dict, boss) -> list[str]:
    """The fight begins in a dressed arena (finale.prepare): its words, and its change armed for the second phase."""
    info = getattr(battle.field, "__dict__", {}).get("arena")
    if not info:
        return []
    aid = info["id"]
    words = spec(game).get(aid, {})
    rng = game.world.rng.child(f"arena-words/{adv['id']}")

    def hook(b, f, phase_spec, _aid=aid, _info=info, _words=words):
        if f is not boss:
            return
        if _words.get("change"):
            b.say(b.rng.choice(_words["change"]), "danger")
        CHANGES[_aid](b, f, phase_spec, _info["marks"])
        b._event("arena", what=_aid)

    battle.__dict__.setdefault("phase_hooks", []).append(hook)
    return [f"<warn>{rng.choice(words['enter'])}</>"] if words.get("enter") else []


# ---------------------------------------------------------------------------- helpers
def _unit(lead, foe_at) -> tuple[float, float, float]:
    dx, dy = foe_at[0] - lead[0], foe_at[1] - lead[1]
    n = math.hypot(dx, dy) or 1.0
    return dx / n, dy / n, n


def _open(terrain, tables, c, keep) -> bool:
    """Open ground that may be built on: walkable, not water, stairs, a door or furniture, and not where anyone
    starts (or beside it)."""
    W, H = terrain.shape
    x, y = c
    if not (0 <= x < W and 0 <= y < H):
        return False
    t = int(terrain[x, y])
    if not tables.terrain.walk[t] or tables.terrain.cost[t] >= 2.0:
        return False
    if tables.terrain.tags[t] & {"water", "stairs", "door", "furniture", "bed", "hoard", "grave"}:
        return False
    return all(max(abs(x - k[0]), abs(y - k[1])) > 1 for k in keep)


def _openish(terrain, tables, c, lead) -> bool:
    """Open ground right behind the boss (the throne's place in a short hall): not where the party stands."""
    W, H = terrain.shape
    if not (0 <= c[0] < W and 0 <= c[1] < H) or max(abs(c[0] - lead[0]), abs(c[1] - lead[1])) <= 1:
        return False
    t = int(terrain[c])
    return bool(tables.terrain.walk[t]) and not tables.terrain.tags[t] & {"water", "stairs", "door", "furniture"}


def _put(terrain, tables, c, name: str) -> None:
    terrain[c] = tables.terrain.index[name]


def _r(v: float) -> int:
    return int(math.floor(v + 0.5))


# ---------------------------------------------------------------------------- the throne hall
@arena("throne_hall")
def _throne_hall(terrain, tables, lead, foe_at, rng):
    """The seat at the far end behind the boss, a brazier either side of it, pillars in two rows down the hall, and
    stone coffins along the sides behind them."""
    ux, uy, n = _unit(lead, foe_at)
    px, py = -uy, ux
    keep = (lead, foe_at)
    marks = {"pillars": [], "sarcophagi": [], "braziers": [], "throne": []}
    lights = []
    throne = (_r(foe_at[0] + ux * 2), _r(foe_at[1] + uy * 2))
    for back in (2, 1):  # (against the far wall, if the hall ends close behind it)
        throne = (_r(foe_at[0] + ux * back), _r(foe_at[1] + uy * back))
        if _open(terrain, tables, throne, (lead,)) or back == 1 and _openish(terrain, tables, throne, lead):
            _put(terrain, tables, throne, "throne")
            marks["throne"].append(throne)
            break
    for side in (-1, 1):
        b = (_r(throne[0] + px * 2 * side), _r(throne[1] + py * 2 * side))
        if _open(terrain, tables, b, keep):
            _put(terrain, tables, b, "brazier")
            marks["braziers"].append(b)
            lights.append((b[0], b[1], 4))
    steps = int(n) + 3
    for i in range(1, steps, 3):
        mx, my = lead[0] + ux * i, lead[1] + uy * i
        for side in (-1, 1):
            for out in (3, 2):  # (a narrow hall has its pillars closer in)
                p = (_r(mx + px * out * side), _r(my + py * out * side))
                if _open(terrain, tables, p, keep):
                    _put(terrain, tables, p, "pillar")
                    marks["pillars"].append(p)
                    break
            s = (_r(mx + px * 5 * side + ux), _r(my + py * 5 * side + uy))
            if _open(terrain, tables, s, keep):
                _put(terrain, tables, s, "sarcophagus")
                marks["sarcophagi"].append(s)
    if not marks["pillars"] and not marks["throne"]:
        return None  # (too cramped a place for a hall: it stays as it is)
    W, H = terrain.shape
    coffin = tables.terrain.index["sarcophagus"]
    marks["sarcophagi"] += [(x, y) for x in range(W) for y in range(H)
                            if terrain[x, y] == coffin and (x, y) not in marks["sarcophagi"]]  # (the crypt's own too)
    return {"lights": lights, "fires": set(), "marks": marks}


@change("throne_hall")
def _throne_hall_change(battle, boss, spec, marks) -> None:
    """The sarcophagi open (the raised climb out of them), or, with nothing to raise, the nearest pillars to the
    party crack and come down in rubble."""
    fld = battle.field
    raised = [f for f in battle.fighters if f.bond is not None and f.bond.get("kind") == "raised" and
              f.bond.get("owner") == boss.id and f.state == "fighting"]
    coffins = [tuple(c) for c in marks.get("sarcophagi", ())]
    if raised and coffins:
        taken = {c for x in battle.on_field() for c in x.cells}
        for f, c in zip(raised, sorted(coffins, key=lambda c: battle.rng.random())):
            if fld.in_bounds(*c):
                fld.set_terrain(c[0], c[1], "grave")
                spot = battle._free_near(c, f.sq, taken - set(f.cells))
                taken -= set(f.cells)
                f.x, f.y = spot
                taken |= set(f.cells)
                battle._event("appear", who=f.id)
        for c in coffins:
            if fld.in_bounds(*c) and fld.terrain[c] == battle.t.terrain.index["sarcophagus"]:
                fld.set_terrain(c[0], c[1], "grave")
        battle._event("terrain", cells=[list(c) for c in coffins])
        return
    party = [f for f in battle.fighters if f.team != boss.team and f.active]
    pillars = sorted((tuple(c) for c in marks.get("pillars", ())),
                     key=lambda c: min((abs(c[0] - f.x) + abs(c[1] - f.y) for f in party), default=0))[:2]
    for c in pillars:
        fld.set_terrain(c[0], c[1], "rubble")
    if pillars:
        battle._event("terrain", cells=[list(c) for c in pillars])


# ---------------------------------------------------------------------------- the ritual circle
@arena("ritual_circle")
def _ritual_circle(terrain, tables, lead, foe_at, rng):
    """A circle cut in the floor round the boss, two squares out, and standing stones at its four quarters."""
    keep = (lead,)
    marks = {"circle": [], "stones": []}
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            d = math.hypot(dx, dy)
            c = (foe_at[0] + dx, foe_at[1] + dy)
            if 1.6 <= d < 2.6 and _open(terrain, tables, c, keep):
                _put(terrain, tables, c, "ritual_circle")
                marks["circle"].append(c)
    stone = "standing_stone" if "standing_stone" in tables.terrain.index else "pillar"
    for dx, dy in ((3, 3), (-3, 3), (3, -3), (-3, -3)):
        c = (foe_at[0] + dx, foe_at[1] + dy)
        if _open(terrain, tables, c, (lead, foe_at)):
            _put(terrain, tables, c, stone)
            marks["stones"].append(c)
    if len(marks["circle"]) < 6:
        return None
    return {"lights": [(foe_at[0], foe_at[1], 2)], "fires": set(), "marks": marks}


RITE_DAMAGE = "2d6"
RITE_DC = 12


@change("ritual_circle")
def _ritual_circle_change(battle, boss, spec, marks) -> None:
    """The circle flares: its line becomes cold burning ground (a Constitution save, necrotic) that hurts the boss's
    foes who stand in it or cross it, to the end of the fight."""
    from realmwalker.rules.combat import Zone

    cells = {tuple(c) for c in marks.get("circle", ()) if battle.field.in_bounds(*c)}
    if not cells:
        return
    dc = int((boss.cdef.get("boss_great") or {}).get("dc", RITE_DC))  # (as hard to bear as its great attack)
    battle._add_zone(Zone(battle._zone_id(), "rite", cells, owner=boss.id, rounds=-1, save="con", dc=dc,
                          damage=RITE_DAMAGE, damage_type="necrotic", on_save="half", friends_safe=True))


# ---------------------------------------------------------------------------- the bridge
@arena("bridge")
def _bridge(terrain, tables, lead, foe_at, rng):
    """A chasm across the way between you and the boss, two squares wide, with a narrow bridge over it."""
    ux, uy, n = _unit(lead, foe_at)
    if n < 5:
        return None
    mx, my = (lead[0] + foe_at[0]) / 2, (lead[1] + foe_at[1]) / 2
    W, H = terrain.shape
    keep = (lead, foe_at)
    marks = {"chasm": [], "bridge": [], "edge": []}
    for x in range(W):
        for y in range(H):
            s = (x - mx) * ux + (y - my) * uy
            d = abs((x - mx) * uy - (y - my) * ux)
            if not -1.0 <= s < 1.0 or d > 3:
                continue  # (across the way between the two sides, not through the rooms beyond)
            c = (x, y)
            if d <= 0.8 and tables.terrain.walk[int(terrain[c])]:
                _put(terrain, tables, c, "bridge")
                marks["bridge"].append(c)
            elif _open(terrain, tables, c, keep):
                _put(terrain, tables, c, "chasm")
                marks["chasm"].append(c)
    if len(marks["chasm"]) < 4 or not marks["bridge"]:
        return None
    for x in range(W):
        for y in range(H):
            s = (x - mx) * ux + (y - my) * uy
            d = abs((x - mx) * uy - (y - my) * ux)
            if (-2.0 <= s < -1.0 or 1.0 <= s < 2.0) and d > 1.5 and tables.terrain.walk[int(terrain[x, y])]:
                marks["edge"].append((x, y))
    return {"lights": [], "fires": set(), "marks": marks}


@change("bridge")
def _bridge_change(battle, boss, spec, marks) -> None:
    """The floor at the chasm's lip falls away: the edge squares nobody stands on drop into the dark."""
    fld = battle.field
    taken = {c for x in battle.on_field() for c in x.cells}
    gone = [tuple(c) for c in marks.get("edge", ()) if tuple(c) not in taken and fld.in_bounds(*c)
            and fld.walk[tuple(c)]]
    for c in gone:
        fld.terrain[c] = battle.t.terrain.index["chasm"]
    if gone:
        fld._derive()
        battle._event("terrain", cells=[list(c) for c in gone])


# ---------------------------------------------------------------------------- the tower top
@arena("tower_top")
def _tower_top(terrain, tables, lead, foe_at, rng):
    """The roof of a tower under the sky: flagstones in a ring of parapet, and nothing beyond it but the drop."""
    W, H = terrain.shape
    cx, cy = (lead[0] + foe_at[0]) / 2, (lead[1] + foe_at[1]) / 2
    _, _, n = _unit(lead, foe_at)
    R = max(4.5, n / 2 + 2.5)
    if cy - R < -0.5 or cy + R > H - 0.5:
        R = max(4.5, min(cy, H - 1 - cy) + 0.4)
    marks = {"parapet": []}
    floor = "flagstones" if "flagstones" in tables.terrain.index else "floor_stone"
    for x in range(W):
        for y in range(H):
            d = math.hypot(x - cx, y - cy)
            c = (x, y)
            if d >= R + 1:
                _put(terrain, tables, c, "chasm")
            elif d >= R:
                _put(terrain, tables, c, "low_wall")
                marks["parapet"].append(c)
            else:
                _put(terrain, tables, c, floor)
    for k in (lead, foe_at):
        if math.hypot(k[0] - cx, k[1] - cy) >= R:
            return None  # (they would stand outside the parapet: not a roof for this fight)
    return {"lights": [], "fires": set(), "marks": marks}


@change("tower_top")
def _tower_top_change(battle, boss, spec, marks) -> None:
    """The parapet cracks and crumbles: a third of it falls into rubble, open to the drop."""
    fld = battle.field
    wall = [tuple(c) for c in marks.get("parapet", ())]
    fallen = [c for c in wall if battle.rng.random() < 0.34]
    for c in fallen:
        fld.terrain[c] = battle.t.terrain.index["rubble"]
    if fallen:
        fld._derive()
        battle._event("terrain", cells=[list(c) for c in fallen])


# ---------------------------------------------------------------------------- the burning village
def _house(terrain, tables, x0, y0, w, h, door) -> list:
    cells = []
    W, H = terrain.shape
    for x in range(x0, x0 + w):
        for y in range(y0, y0 + h):
            if not (0 <= x < W and 0 <= y < H):
                continue
            edge = x in (x0, x0 + w - 1) or y in (y0, y0 + h - 1)
            _put(terrain, tables, (x, y), "wall_wood" if edge and (x, y) != door else "floor_wood")
            cells.append((x, y))
    return cells


@arena("burning_village")
def _burning_village(terrain, tables, lead, foe_at, rng):
    """A hamlet on fire: small timber houses either side of the way between you, the nearest roofs already alight,
    and the fire spreading from house to house (its timbers catch: game/fire.py)."""
    W, H = terrain.shape
    keep = (lead, foe_at)
    nrng = rng if hasattr(rng, "integers") else np.random.default_rng(0)
    houses, fires, lights = [], set(), []
    mid = (lead[1] + foe_at[1]) // 2
    x = min(lead[0], foe_at[0]) + 1
    while x + 4 < max(lead[0], foe_at[0]) + 2 and x + 4 < W:
        for top in (True, False):
            w, h = int(nrng.integers(3, 5)), int(nrng.integers(3, 4))
            y0 = mid - 2 - h if top else mid + 2
            if y0 < 0 or y0 + h > H:
                continue
            box = [(xx, yy) for xx in range(x, x + w) for yy in range(y0, y0 + h)]
            if not all(_open(terrain, tables, c, keep) for c in box):
                continue
            door = (x + w // 2, y0 + h - 1 if top else y0)
            houses.append(_house(terrain, tables, x, y0, w, h, door))
        x += int(nrng.integers(5, 7))
    if not houses:
        return None
    for i, cells in enumerate(houses):
        if i % 2 == 0:
            walls = [c for c in cells if terrain[c] == tables.terrain.index["wall_wood"]]
            for c in walls[:3]:
                fires.add(c)
            if walls:
                lights.append((walls[0][0], walls[0][1], 3))
    return {"lights": lights, "fires": fires, "marks": {"houses": [list(map(list, h)) for h in houses]},
            "burning": True}


@change("burning_village")
def _burning_village_change(battle, boss, spec, marks) -> None:
    """The fire leaps: a roof not yet burning nearest the party goes up at once."""
    from realmwalker.game import fire as firemod

    z = firemod._fire_zone(battle)
    if z is None:
        return
    party = [f for f in battle.fighters if f.team != boss.team and f.active]
    taken = {c for x in battle.on_field() for c in x.cells}
    best = None
    for cells in marks.get("houses", ()):
        cells = [tuple(c) for c in cells]
        if any(c in z.cells for c in cells):
            continue
        d = min((abs(c[0] - f.x) + abs(c[1] - f.y) for c in cells for f in party), default=99)
        if best is None or d < best[0]:
            best = (d, cells)
    if best is None:
        return
    new = {c for c in best[1] if c not in taken and battle.field.flammable[c]}
    z.cells |= new
    battle._sync_zones()
    battle._event("zone_move", id=z.id, cells=sorted(z.cells))


def village_field(terrain, tables, lead, foe_at, nrng) -> tuple[list, set]:
    """game/arena.FIELDS: the burning village as a set piece's battlefield on the land."""
    out = _burning_village(terrain, tables, lead, foe_at, nrng)
    return (out["lights"], out["fires"]) if out else ([], set())
