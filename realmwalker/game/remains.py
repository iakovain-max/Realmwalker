"""The fallen, blood and graves (Expansion 6 B.5, docs/ADVENTURES.md §5.19, §8.14): when a fight on a close-up map
ends, the dead lie where they fell and the blood stays on the squares where the blows landed; the party stands where
its leader stood. The cheapest, strongest piece of show-don't-tell: walk back through the street where the fight was
and see it.

Kept on the map (saved with it, JSON-native):
    lm.meta["bodies"]  [{"x", "y", "who": {"npc": id} | {"creature": def id}, "angle", "day", "side"}] - who they
                       were, never their picture (LocalView composes the figure); at most BODIES a map
    lm.meta["decals"]  {"x,y": [kind, day, variant]} - blood; at most DECALS a map, the oldest first to go
    lm.meta["graves"]  [{"x", "y", "who", "day"}] - fresh graves the town dug for its own

    after_field(game, battle, result)   from fight.finish_battle: the field written back through Field.origin
    tick(game, lm)                      the days pass: a town carries its dead off after a day and buries its own;
                                        in the wild the dead lie two days and then are bones; blood fades
"""

from __future__ import annotations

BODIES = 60
DECALS = 400
TOWN_KEEPS_DEAD = 1.0  # days before a town carries its dead off
WILD_KEEPS_DEAD = 2.0  # days before the crows have done and bones are left
BLOOD_DAYS = (3, 6)  # blood fades in this many days (by the square)


def _days(game) -> float:
    return float(game.world.time) / 1440.0


def after_field(game, battle, result) -> list[str]:
    """Write a fight's dead and blood back onto the close-up map it was fought on (only a field cut from it)."""
    lm = game.local
    fld = getattr(battle, "field", None)
    if lm is None or fld is None or getattr(fld, "cut_from", None) != lm.key:
        return []
    from realmwalker.rules.combat import PARTY

    ox, oy = fld.origin
    day = _days(game)
    bodies = lm.meta.setdefault("bodies", [])
    decals = lm.meta.setdefault("decals", {})
    mapping = getattr(game, "battle_npcs", {}) or {}
    for f in battle.fighters:
        if f.state != "dead" or f.side == PARTY and f.creature is None or getattr(f, "bond", None) is not None:
            continue
        x, y = int(f.x) + ox, int(f.y) + oy
        if not lm.in_bounds(x, y):
            continue
        if f.creature is not None:
            nid = mapping.get(f.creature.uid)
            who = {"npc": int(nid)} if nid is not None else {"creature": f.creature.def_id}
        else:
            continue
        angle = 90 if (x * 7 + y * 3) % 2 else -90
        bodies.append({"x": x, "y": y, "who": who, "angle": angle, "day": day,
                       "side": "party" if f.side == PARTY else "foe"})
        decals[f"{x},{y}"] = ["pool", day, (x * 5 + y) % 5]
    for bx, by in getattr(battle, "__dict__", {}).get("blood", []):
        x, y = int(bx) + ox, int(by) + oy
        if lm.in_bounds(x, y) and f"{x},{y}" not in decals:
            decals[f"{x},{y}"] = ["blood", day, (x * 3 + y * 7) % 8]
    _caps(lm)
    _stand_where_it_ended(game, battle, lm)
    return []


def _stand_where_it_ended(game, battle, lm) -> None:
    """The party stands where its leader stood when the fight ended, so the dead lie round them."""
    from realmwalker.rules.combat import PARTY

    lead = next((f for f in battle.fighters if f.side == PARTY and f.char is game.leader), None)
    if lead is None:
        return
    ox, oy = battle.field.origin
    x, y = int(lead.x) + ox, int(lead.y) + oy
    T = game.tables.terrain
    if lm.in_bounds(x, y) and T.walk[game.remap_for(lm)[lm.terrain[x, y]]]:
        game.player.lx, game.player.ly = x, y


def _caps(lm) -> None:
    bodies = lm.meta.get("bodies", [])
    if len(bodies) > BODIES:
        del bodies[:len(bodies) - BODIES]
    decals = lm.meta.get("decals", {})
    if len(decals) > DECALS:
        for k in sorted(decals, key=lambda k: decals[k][1])[:len(decals) - DECALS]:
            del decals[k]


def blood_alpha(day_now: float, rec) -> float:
    """How strong a decal still shows (1 fresh, fading to 0): blood over days, tracks over a day."""
    kind, day, variant = rec
    age = day_now - float(day)
    if kind == "tracks":
        return max(0.0, 1.0 - age / TRACK_DAYS)
    life = BLOOD_DAYS[0] + (BLOOD_DAYS[1] - BLOOD_DAYS[0]) * (int(variant) % 4) / 3.0
    return max(0.0, 1.0 - age / life)


def tick(game, lm) -> list[str]:
    """The days pass on this map: blood fades; a town carries its dead off after a day and gives each of its own a
    fresh grave; in the wild the dead lie two days, then are bones."""
    if lm is None or not lm.meta:
        return []
    now = _days(game)
    out: list[str] = []
    decals = lm.meta.get("decals")
    if decals:
        for k in [k for k, rec in decals.items() if blood_alpha(now, rec) <= 0]:
            del decals[k]
    bodies = lm.meta.get("bodies")
    if not bodies:
        return out
    town = lm.kind == "settlement"
    keep = TOWN_KEEPS_DEAD if town else WILD_KEEPS_DEAD
    gone = [b for b in bodies if now - float(b["day"]) >= keep]
    if not gone:
        return out
    lm.meta["bodies"] = [b for b in bodies if b not in gone]
    if town:
        own = [b for b in gone if "npc" in b["who"]]
        for b in own:
            spot = _grave_spot(game, lm)
            if spot is None:
                break
            from realmwalker.game.dungeon import set_terrain

            set_terrain(lm, spot[0], spot[1], "grave")
            lm.meta.setdefault("graves", []).append({"x": spot[0], "y": spot[1], "who": b["who"], "day": now})
        if own and game.local is lm:
            out.append("<dim>The town has carried its dead away. There are new graves.</>")
    else:
        from realmwalker.game.dungeon import set_terrain

        T = game.tables.terrain
        remap = game.remap_for(lm)
        for b in gone:
            x, y = int(b["x"]), int(b["y"])
            if lm.in_bounds(x, y) and T.walk[remap[lm.terrain[x, y]]] and lm.building_at(x, y) is None:
                set_terrain(lm, x, y, "bones")
    return out


def _grave_spot(game, lm):
    """A square for a new grave: beside the graves already dug, else near the temple, else near the town's edge -
    never in a doorway or on a way that people need."""
    from realmwalker.game.people import outdoor_cells

    graves = lm.meta.get("graves") or []
    T = game.tables.terrain
    remap = game.remap_for(lm)
    walk = T.walk[remap[lm.terrain]]
    temple = next((b for b in lm.buildings if b.kind == "temple"), None)
    if graves:
        anchor = (graves[-1]["x"], graves[-1]["y"])
    elif temple is not None:
        anchor = (temple.x + temple.w + 1, temple.y + temple.h // 2)
    else:
        anchor = (2, lm.height // 2)
    doors = {tuple(b.door) for b in lm.buildings}
    taken = {(g["x"], g["y"]) for g in graves}
    best = None
    for x, y in outdoor_cells(game, lm):
        if (x, y) in taken or not walk[x, y] or any(abs(x - dx) <= 1 and abs(y - dy) <= 1 for dx, dy in doors):
            continue
        if abs(x - lm.entry[0]) <= 3 and abs(y - lm.entry[1]) <= 3:
            continue
        d = (x - anchor[0]) ** 2 + (y - anchor[1]) ** 2
        if best is None or d < best[0]:
            best = (d, (x, y))
    return best[1] if best else None


# ---------------------------------------------------------------------------- tracks (B.6)
DIRS = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))  # (decal variant = the way they go)
TRACK_DAYS = 1.0  # tracks last a day (rain takes them sooner: Part G)


def lay_tracks(game, lm, start, toward: tuple[int, int] | None = None) -> list[tuple[int, int]]:
    """Tracks from `start` to the map's edge (the edge nearest `toward`, or the nearest): a decal on every square of
    the way, pointing the way they went; the world map's square beyond that edge is where they lead. Returns the way."""
    import numpy as np
    import tcod.path

    T = game.tables.terrain
    walk = T.walk[game.remap_for(lm)[lm.terrain]]
    sx, sy = int(start[0]), int(start[1])
    if toward is None:
        cands = [(0, sy), (lm.width - 1, sy), (sx, 0), (sx, lm.height - 1)]
        toward = min(cands, key=lambda c: abs(c[0] - sx) + abs(c[1] - sy))
    edge = [(x, y) for x in range(lm.width) for y in (0, lm.height - 1)] + \
        [(x, y) for x in (0, lm.width - 1) for y in range(1, lm.height - 1)]
    edge = sorted((c for c in edge if walk[c]), key=lambda c: (c[0] - toward[0]) ** 2 + (c[1] - toward[1]) ** 2)
    if not edge:
        return []
    astar = tcod.path.AStar(walk.astype(np.int16), diagonal=1.41)
    path = [(int(x), int(y)) for x, y in astar.get_path(sx, sy, edge[0][0], edge[0][1])]
    if not path:
        return []
    day = _days(game)
    decals = lm.meta.setdefault("decals", {})
    prev = (sx, sy)
    for x, y in path:
        d = (x - prev[0], y - prev[1])
        variant = DIRS.index(d) if d in DIRS else 0
        if decals.get(f"{x},{y}", [""])[0] not in ("blood", "pool"):
            decals[f"{x},{y}"] = ["tracks", day, variant]
        prev = (x, y)
    ex, ey = path[-1]
    dx = -1 if ex == 0 else (1 if ex == lm.width - 1 else 0)
    dy = -1 if ey == 0 else (1 if ey == lm.height - 1 else 0)
    wx, wy = (int(v) for v in lm.key.split("/")[0].split(","))
    lm.meta["tracks_to"] = {"edge": [ex, ey], "tile": [wx + dx, wy + dy], "day": day}
    _caps(lm)
    return path


def follow_off(game, lm) -> list[str]:
    """Leaving a map where the tracks you were following end at its edge: the world map's next square lights up
    (story.map_marks), for a day."""
    t = (lm.meta or {}).get("tracks_to")
    p = game.player
    if not t or _days(game) - float(t["day"]) > TRACK_DAYS:
        return []
    ex, ey = t["edge"]
    if max(abs(p.lx - ex), abs(p.ly - ey)) > 4:
        return []
    wx, wy = t["tile"]
    if not game.world.in_bounds(wx, wy):
        return []
    led = game.world.politics.setdefault("director", {}).setdefault("tracks", [])
    led[:] = [r for r in led if _days(game) - float(r["day"]) <= TRACK_DAYS] + [{"x": wx, "y": wy, "day": _days(game)}]
    return ["<info>The tracks go on beyond, out into the land. You mark where.</>"]
