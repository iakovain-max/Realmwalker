"""Marks on a town's close-up map (Expansion 6 B.4, docs/ADVENTURES.md §8.13): a town burned by a war looks burned the
first time you walk in. Show, don't tell.

`stamp(game, lm, s)` dresses the map for the marks the settlement carries (marks.json `dress`): the buildings a mark
touches (a share of them, nearest the town's middle or anywhere) become charred shells - floors to ash, furniture to
ash, some walls fallen, doors broken in, roofs gone or blackened - the streets get their scatter (ash, rubble, weeds)
and props stand where they block nobody (banners, a statue, sacks for barricades, wood for the builders). What each
mark changed is kept in `lm.meta["marks"]` {mark: {"cells": [[x, y, old terrain id]], "looks": [[building, old look]],
"shut": [buildings]}} (the Passwall pattern), so a mark that is lifted is restored exactly and one that ages is
restamped. It runs in `enter_local` right after the map is fetched (before bands and people are placed), in
`people.prepare_town` between the map and its people, and while you stand in a town whose marks change (people step
off changed cells, posts and homes move out of blocked ones).

Rules a stamp keeps (tests/test_towns.py `check_works`): buildings are marked, never removed or reordered; the entry,
doors and the squares before them are never touched; only walkable things are scattered in the streets, and anything
that blocks stands only where it leaves every way round it open.

    stamp(game, lm, s) -> bool     dress (or restore) the map for its marks; True if anything changed
    shut(lm, building_index)        a building whose trade is shut by a mark (a burnt shell)
"""

from __future__ import annotations

import zlib

import numpy as np

DOORS = ("door_closed", "door_open", "doorway", "door_locked")
# Roofs drawn as their own forms (ui/gfx/houses.py): a mark never swaps them for a blackened gable.
OWN_ROOFS = ("flat", "dome", "dome_blue", "onion", "felt", "felt_white", "thatch_round", "leaves", "mound", "hide",
             "turf", "none")


def _dress(game, mark: str) -> dict | None:
    return (getattr(game.tables, "marks", {}) or {}).get(mark, {}).get("dress")


def _hash(*parts) -> int:
    """A steady number from the parts (the same town and mark make the same choices every time)."""
    return zlib.crc32("/".join(map(str, parts)).encode())


def shut(lm, i: int) -> bool:
    """A building whose trade a mark has shut (its keeper is out of business until it is rebuilt)."""
    for rec in (lm.meta or {}).get("marks", {}).values():
        if i in rec.get("shut", ()):
            return True
    return False


def stamp(game, lm, s) -> bool:
    """Bring the map in line with the settlement's marks: restore what was lifted, dress what is new."""
    if lm is None or lm.kind != "settlement" or s is None:
        return False
    from realmwalker.world import marks

    have = lm.meta.setdefault("marks", {})
    want = [m for m in marks.marks_of(s) if _dress(game, m)]
    changed = False
    for m in list(have):
        if m not in want:
            _restore(lm, have.pop(m))
            changed = True
    for m in want:
        if m not in have:
            have[m] = _apply(game, lm, s, m, _dress(game, m))
            changed = True
    if changed:
        _after(game, lm, s)
    return changed


# ---------------------------------------------------------------------------- dressing
def _terrain(game, lm):
    T = game.tables.terrain
    ids = np.array([T.index.get(n, 0) for n in lm.terrain_ids], np.int32)
    return T, ids[lm.terrain]


def _set(lm, rec: dict, x: int, y: int, name: str) -> None:
    from realmwalker.game.dungeon import set_terrain

    old = lm.terrain_ids[int(lm.terrain[x, y])]
    if old == name:
        return
    rec["cells"].append([int(x), int(y), old])
    set_terrain(lm, x, y, name)


def _keep_clear(lm) -> set:
    """Squares a stamp never touches: the entry, every door and the squares before it."""
    out = set()
    ex, ey = lm.entry
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            out.add((ex + dx, ey + dy))
    for b in lm.buildings:
        dx_, dy_ = b.door
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                out.add((dx_ + dx, dy_ + dy))
    return out


def _touched(game, lm, s, mark: str, spec: dict) -> list[int]:
    """The buildings a mark touches: a share of them, the nearest to where it began (the town's middle) or anywhere."""
    n = len(lm.buildings)
    count = int(round(n * float(spec.get("share", 0.0))))
    if count <= 0:
        return []
    keep = {"keep", "temple"} if spec.get("spare") is None else set(spec["spare"])
    pool = [i for i, b in enumerate(lm.buildings) if b.kind not in keep]
    if spec.get("near") == "centre":
        cx, cy = lm.width / 2, lm.height / 2
        h = _hash(s.id, mark) % 1000 / 1000.0
        cx += (h - 0.5) * lm.width * 0.3
        pool.sort(key=lambda i: ((lm.buildings[i].x - cx) ** 2 + (lm.buildings[i].y - cy) ** 2, i))
    else:
        pool.sort(key=lambda i: (_hash(s.id, mark, i), i))
    return pool[:count]


def _apply(game, lm, s, mark: str, spec: dict) -> dict:
    rec = {"cells": [], "looks": [], "shut": []}
    T, terrain = _terrain(game, lm)
    tags = T.tags if hasattr(T, "tags") else None
    clear = _keep_clear(lm)
    for i in _touched(game, lm, s, mark, spec):
        b = lm.buildings[i]
        h = _hash(s.id, mark, "b", i)
        roofless = (h % 1000) / 1000.0 < float(spec.get("roofless", 0.0))
        look = dict(b.look or {})
        rec["looks"].append([i, dict(b.look or {})])
        for k, v in (spec.get("look") or {}).items():
            if k == "roof" and (look.get("roof") in OWN_ROOFS or b.shape not in ("rect", "long", "L")):
                continue  # (a dome, a yurt, a mound keeps its form: only its walls blacken)
            look[k] = v
        if roofless:
            look["roof"] = "none"
        b.look = look
        if spec.get("shut"):
            rec["shut"].append(i)
        for x in range(max(0, b.x), min(lm.width, b.x + b.w)):
            for y in range(max(0, b.y), min(lm.height, b.y + b.h)):
                if not b.contains(x, y) or (x, y) in clear:
                    continue
                name = lm.terrain_ids[int(lm.terrain[x, y])]
                t = _tags(game, name, tags)
                r = (_hash(s.id, mark, x, y) % 1000) / 1000.0
                if name in DOORS:
                    if spec.get("doors") and (x, y) == tuple(b.door):
                        _set(lm, rec, x, y, spec["doors"])
                elif "wall" in t:
                    acc = 0.0
                    for to, share in spec.get("walls", []):
                        acc += float(share)
                        if r < acc:
                            if to != "rubble" or roofless:  # (a wall falls in only where the roof has gone)
                                _set(lm, rec, x, y, to)
                            break
                elif "furniture" in t and spec.get("furniture"):
                    _set(lm, rec, x, y, spec["furniture"])
                elif "floor" in t and spec.get("floor") and roofless:
                    _set(lm, rec, x, y, spec["floor"])
    _streets(game, lm, s, mark, spec, rec, clear)
    _no_pockets(game, lm, rec)
    return rec


def _no_pockets(game, lm, rec: dict) -> None:
    """A square the stamp opened (ash where a chest stood, rubble where a wall fell) that cannot be reached from the
    way in goes back as it was: a town never has a floor nobody can walk to."""
    from realmwalker.game.dungeon import set_terrain

    if not rec["cells"]:
        return
    T = game.tables.terrain
    remap = np.array([T.index.get(n, 0) for n in lm.terrain_ids], np.int32)
    ids = remap[lm.terrain]
    doors = np.isin(ids, [T.index[n] for n in DOORS + ("gate_open",) if n in T.index])
    walk = T.walk[ids] | doors
    seen = _reach(walk, tuple(lm.entry))
    keep = []
    for x, y, old in rec["cells"]:
        if walk[x, y] and not seen[x, y]:
            set_terrain(lm, int(x), int(y), old)
        else:
            keep.append([x, y, old])
    rec["cells"] = keep


def _tags(game, name: str, tags) -> tuple:
    T = game.tables.terrain
    i = T.index.get(name)
    if i is None:
        return ()
    if tags is not None:
        return tuple(tags[i]) if not isinstance(tags, dict) else tuple(tags.get(name, ()))
    d = getattr(T, "defs", None)
    if d is not None:
        return tuple((d[name] if isinstance(d, dict) else d[i]).get("tags", ()))
    return ()


def _streets(game, lm, s, mark: str, spec: dict, rec: dict, clear: set) -> None:
    """The streets' scatter (walkable things only) and props (only where they leave every way open)."""
    from realmwalker.game.people import outdoor_cells

    scatter = spec.get("scatter") or []
    props = spec.get("props") or []
    if not scatter and not props:
        return
    T = game.tables.terrain
    remap = np.array([T.index.get(n, 0) for n in lm.terrain_ids], np.int32)
    streets = [c for c in outdoor_cells(game, lm, settlement=s) if c not in clear]
    for x, y in streets:
        r = (_hash(s.id, mark, "s", x, y) % 10000) / 10000.0
        acc = 0.0
        for to, share in scatter:
            acc += float(share)
            if r < acc:
                if T.walk[T.index[to]]:
                    _set(lm, rec, x, y, to)
                break
    if not props:
        return
    order = sorted(streets, key=lambda c: (_hash(s.id, mark, "p", *c), c))
    if spec.get("props_near") == "square":
        ex, ey = lm.entry
        order.sort(key=lambda c: (c[0] - ex) ** 2 + (c[1] - ey) ** 2)
    placed: list[tuple[int, int]] = []
    want = [to for to, n in props for _ in range(int(n))]
    remap = np.array([T.index.get(n, 0) for n in lm.terrain_ids], np.int32)
    walk = T.walk[remap[lm.terrain]]
    for x, y in order:
        if not want:
            break
        if any(abs(x - px) <= 2 and abs(y - py) <= 2 for px, py in placed):
            continue
        if not _open_all_round(walk, x, y) or lm.building_at(x, y) is not None:
            continue
        to = want.pop(0)
        if to not in T.index:
            continue
        _set(lm, rec, x, y, to)
        walk[x, y] = bool(T.walk[T.index[to]])
        placed.append((x, y))


def _reach(walk, start) -> np.ndarray:
    """Every square reached from `start` by steps along the sides (grown a ring at a time, in numpy)."""
    seen = np.zeros_like(walk)
    if not walk[start]:
        return seen
    seen[start] = True
    while True:
        grow = seen.copy()
        grow[1:, :] |= seen[:-1, :]
        grow[:-1, :] |= seen[1:, :]
        grow[:, 1:] |= seen[:, :-1]
        grow[:, :-1] |= seen[:, 1:]
        grow &= walk
        if (grow == seen).all():
            return seen
        seen = grow


def _open_all_round(walk, x: int, y: int) -> bool:
    """This square and all eight round it open: a thing set here can always be walked round (so props, one by one,
    never cut a way)."""
    w, h = walk.shape
    if not (1 <= x < w - 1 and 1 <= y < h - 1):
        return False
    return bool(walk[x - 1:x + 2, y - 1:y + 2].all())


def _restore(lm, rec: dict) -> None:
    """Put back every cell and every look the mark changed, last first (exactly as they were)."""
    from realmwalker.game.dungeon import set_terrain

    for x, y, old in reversed(rec.get("cells", [])):
        set_terrain(lm, int(x), int(y), old)
    for i, look in reversed(rec.get("looks", [])):
        if 0 <= int(i) < len(lm.buildings):
            lm.buildings[int(i)].look = dict(look)


def _after(game, lm, s) -> None:
    """The map changed: walkers learn it again, and anyone on a square that now blocks steps off it; posts and homes
    that fell inside blocked squares move to the nearest open one."""
    from realmwalker.game import townlife
    from realmwalker.game.people import npcs_in

    lm._building_grid = None
    if hasattr(game, "_remaps"):
        game._remaps.pop(lm.key, None)
    townlife.forget()
    T = game.tables.terrain
    remap = np.array([T.index.get(n, 0) for n in lm.terrain_ids], np.int32)
    walk = T.walk[remap[lm.terrain]]
    for npc in npcs_in(game.world, s.id):
        for attr in ("post", "home"):
            x, y = getattr(npc, attr)
            if 0 <= x < lm.width and 0 <= y < lm.height and not walk[x, y]:
                setattr(npc, attr, _nearest_open(walk, x, y))
        if 0 <= npc.x < lm.width and 0 <= npc.y < lm.height and not walk[npc.x, npc.y]:
            npc.x, npc.y = _nearest_open(walk, npc.x, npc.y)
    for a in lm.actors:
        if 0 <= a.x < lm.width and 0 <= a.y < lm.height and not walk[a.x, a.y]:
            a.x, a.y = _nearest_open(walk, a.x, a.y)


def _nearest_open(walk, x: int, y: int) -> tuple[int, int]:
    w, h = walk.shape
    for r in range(1, 12):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and walk[nx, ny]:
                    return nx, ny
    return x, y
