"""Wonders of the world: the highest peak, volcanoes (one awake), great falls, the long gorge, great cliffs, salt pans,
a lake that shines at night, oases, hot springs, the enchanted wood, a tree as big as a castle, stone arches, a
sinkhole, a forest of stone, the wall of the ice, and the drifting stones.

Placed while the world is made (`place`, after the lands; some change the land round them), named by the people living
nearest (`name_all`, after the peoples), and kept in `world.wonders`. In play: `arrive` (the first time you reach one),
`look` and `boons` (what one does for a traveller), and `shape_local` (its close-up map). Words are data/wonders.json.
"""

from __future__ import annotations

import math

import numpy as np

from realmwalker.core.rng import RNG
from realmwalker.world import hydrology
from realmwalker.world.model import CLIFF, FALLS, RAVINE, Wonder

ORDER = ("great_peak", "volcano", "great_falls", "great_canyon", "great_cliffs", "salt_pan", "glacier_wall",
         "enchanted_forest", "giant_tree", "glowing_lake", "hot_springs", "oasis", "stone_arches", "petrified_forest",
         "sinkhole", "drifting_stones")
WIDE = {"great_canyon", "great_cliffs", "salt_pan", "glacier_wall", "enchanted_forest", "glowing_lake"}
MAX_CELLS = 80  # how many squares a wide wonder keeps a note of


# ---------------------------------------------------------------------------- making the world
def place(gen) -> list[Wonder]:
    """Find a place for each wonder this world has. Some change the land: the enchanted wood is grown in a forest,
    a crater lake fills a sleeping volcano. Called after the biomes, before the peoples."""
    kinds = gen.tables.wonders["kinds"]
    r = gen.rng.child("wonders")
    B = gen.B
    F = gen.tables.biomes
    w, h = gen.w, gen.h
    land = ~gen.ocean & ~gen.lake
    inner = np.zeros((w, h), dtype=bool)
    inner[3:-3, 3:-3] = True
    biome = gen.biome
    out: list[Wonder] = []
    taken: list[tuple[int, int]] = []

    def is_(*names: str) -> np.ndarray:
        return np.isin(biome, [B[n] for n in names if n in B])

    def family(*names: str) -> np.ndarray:
        return np.isin(biome, F.of_family(*names))

    def free(x: int, y: int, apart: int) -> bool:
        return all(max(abs(x - ox), abs(y - oy)) >= apart for ox, oy in taken)

    def add(kind: str, x: int, y: int, cells=None, **flags) -> Wonder:
        listed = [[int(a), int(b)] for a, b in (cells if cells is not None else [])][:MAX_CELLS]
        wd = Wonder(len(out), kind, "", int(x), int(y), listed, "", flags)
        out.append(wd)
        taken.append((int(x), int(y)))
        return wd

    def how_many(kind: str) -> int:
        spec = kinds.get(kind)
        if spec is None or not r.chance(float(spec["chance"])):
            return 0
        return int(spec["count"][gen.size_index])

    def pick(mask: np.ndarray, apart: int = 10, score: np.ndarray | None = None) -> tuple[int, int] | None:
        cells = np.argwhere(mask & inner)
        if not len(cells):
            return None
        if score is not None:
            order = np.argsort(-score[cells[:, 0], cells[:, 1]], kind="stable").tolist()
        else:
            order = list(range(len(cells)))
            r.shuffle(order)
        for i in order:
            x, y = (int(v) for v in cells[i])
            if free(x, y, apart):
                return x, y
        return None

    def biggest(mask: np.ndarray, at_least: int):
        labels, sizes = hydrology.label_components(mask & inner, diagonal=True)
        if not sizes or max(sizes) < at_least:
            return None
        i = int(np.argmax(sizes))
        cells = np.argwhere(labels == i)
        centre = cells.mean(axis=0)
        hx, hy = (int(v) for v in cells[np.argmin(((cells - centre) ** 2).sum(axis=1))])
        return hx, hy, cells

    def interior(mask: np.ndarray, depth: int) -> np.ndarray:
        return mask & ~hydrology.dilate(~mask, depth)

    for kind in ORDER:
        n = how_many(kind)
        if n <= 0:
            continue
        if kind == "great_peak":
            m = np.where(land & inner, gen.meters, -1e9)
            x, y = np.unravel_index(int(np.argmax(m)), m.shape)
            add(kind, x, y, height=int(round(float(gen.meters[x, y]))))
        elif kind == "volcano":
            spots = list(gen.volcanoes)
            r.shuffle(spots)
            for i, (x, y) in enumerate(spots[:n]):
                if not free(x, y, 4):
                    continue
                flags = {"awake": i == 0, "height": int(round(float(gen.meters[x, y])))}
                if i == 1:
                    flags["crater_lake"] = True
                add(kind, x, y, **flags)
        elif kind == "great_falls":
            drop = np.zeros((w, h), np.float32)
            for x, y in np.argwhere(gen.relief & FALLS):
                dx, dy = _dir(gen, int(x), int(y))
                drop[x, y] = (float(gen.meters[x, y]) - float(gen.meters[x + dx, y + dy])) * float(gen.river[x, y])
            for _ in range(n):
                spot = pick((drop > 0) & land, apart=12, score=drop)
                if spot is None:
                    break
                x, y = spot
                dx, dy = _dir(gen, x, y)
                add(kind, x, y, height=int(round((float(gen.meters[x, y]) - float(gen.meters[x + dx, y + dy])))))
        elif kind == "great_canyon":
            found = biggest((gen.relief & RAVINE) > 0, 5)
            if found and free(found[0], found[1], 6):
                add(kind, found[0], found[1], found[2], length=int(len(found[2])))
        elif kind == "great_cliffs":
            found = biggest((gen.relief & CLIFF) > 0, 8)
            if found and free(found[0], found[1], 6):
                add(kind, found[0], found[1], found[2], length=int(len(found[2])))
        elif kind == "salt_pan":
            found = biggest(is_("salt_flat"), 6)
            if found and free(found[0], found[1], 6):
                add(kind, found[0], found[1], found[2])
        elif kind == "glacier_wall":
            ice = is_("glacier")
            edge = ice & hydrology.dilate(~ice & ~gen.lake, 1)
            if edge.any():
                around = _count(ice, 3)
                spot = pick(edge, apart=8, score=around.astype(np.float32))
                if spot is not None:
                    x, y = spot
                    cells = [(cx, cy) for cx, cy in np.argwhere(edge) if max(abs(cx - x), abs(cy - y)) <= 5]
                    add(kind, x, y, cells)
        elif kind == "enchanted_forest":
            woods = is_("forest")
            spot = pick(interior(woods, 2), apart=12)
            if spot is not None:
                x, y = spot
                cells = _grow_fey(gen, r, x, y, family("forest", "pine_forest") & ~is_("jungle"))
                add(kind, x, y, cells)
        elif kind == "giant_tree":
            spot = pick(interior(is_("forest", "jungle", "fey_forest", "pine_forest"), 2), apart=10)
            if spot is not None:
                add(kind, *spot)
        elif kind == "glowing_lake":
            labels, sizes = hydrology.label_components(gen.lake & inner)
            options = [i for i, s in enumerate(sizes) if 2 <= s <= 80]
            r.shuffle(options)
            for i in options:
                water = labels == i
                shore = np.argwhere(hydrology.dilate(water, 1) & land & inner)
                if not len(shore):
                    continue
                x, y = (int(v) for v in shore[r.randint(0, len(shore) - 1)])
                if free(x, y, 8):
                    add(kind, x, y, [(x, y)] + [tuple(c) for c in np.argwhere(water)])
                    break
        elif kind == "hot_springs":
            near_fire = np.zeros((w, h), dtype=bool)
            for vx, vy in gen.volcanoes:
                near_fire[max(0, vx - 8):vx + 9, max(0, vy - 8):vy + 9] = True
            cold_hills = family("hills", "mountains", "tundra") & (gen.temperature < 12)
            mask = land & (gen.meters < 2600) & ~is_("glacier") & (near_fire | cold_hills) & ~is_("lake")
            score = near_fire * 2.0 + r.numpy("springs").random((w, h))
            for _ in range(n):
                spot = pick(mask, apart=12, score=score)
                if spot is None:
                    break
                add(kind, *spot)
        elif kind == "oasis":
            water = gen.lake | (gen.river > 0) | gen.ocean
            far = ~hydrology.dilate(water, 4)
            mask = is_("desert", "dunes") & far & (gen.temperature > 14)
            for _ in range(n):
                spot = pick(mask, apart=14)
                if spot is None:
                    break
                add(kind, *spot)
        elif kind == "stone_arches":
            spot = pick((is_("badlands", "desert") | (family("hills") & (gen.moisture < 0.3))) & ~is_("volcanic"))
            if spot is not None:
                add(kind, *spot)
        elif kind == "petrified_forest":
            spot = pick(is_("desert", "badlands", "volcanic", "steppe", "savanna") & land)
            if spot is not None:
                add(kind, *spot)
        elif kind == "sinkhole":
            mask = family("plains", "forest", "hills") & ~is_("volcanic", "fey_forest") & (gen.meters < 1000) & \
                (gen.river == 0)
            spot = pick(mask)
            if spot is not None:
                add(kind, *spot)
        elif kind == "drifting_stones":
            mask = family("hills", "mountains", "plains", "tundra") & ~is_("glacier", "high_mountains") & land
            spot = pick(mask, apart=12)
            if spot is not None:
                add(kind, *spot)
    return out


def _dir(gen, x: int, y: int) -> tuple[int, int]:
    from realmwalker.world.model import DIRS

    dx, dy = DIRS[int(gen.flow[x, y])]
    if not (0 <= x + dx < gen.w and 0 <= y + dy < gen.h):
        return 0, 0
    return dx, dy


def _count(mask: np.ndarray, r: int) -> np.ndarray:
    """How many squares of mask are within r of each square."""
    pad = np.pad(mask.astype(np.int32), r)
    c = np.pad(pad.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    n = 2 * r + 1
    return c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]


def _grow_fey(gen, r: RNG, x: int, y: int, wood: np.ndarray) -> list[tuple[int, int]]:
    """The enchanted wood: a ragged patch of an old forest gone strange."""
    rad = r.uniform(3.0, 5.5) + gen.size_index
    noise = r.numpy("fey").random((gen.w, gen.h))
    xs = np.arange(gen.w)[:, None]
    ys = np.arange(gen.h)[None, :]
    d = np.sqrt((xs - x) ** 2 + (ys - y) ** 2) / rad + (noise - 0.5) * 0.5
    blob = (d < 1.0) & wood
    gen.biome[blob] = gen.B["fey_forest"]
    gen.biome[x, y] = gen.B["fey_forest"]
    cells = [(int(a), int(b)) for a, b in np.argwhere(blob)]
    cells.sort(key=lambda c: (c[0] - x) ** 2 + (c[1] - y) ** 2)
    return cells


def avoid(world_or_gen) -> np.ndarray:
    """Where towns and old sites keep off: the heart of every wonder and the squares next to it, and every square
    of the narrow ones."""
    w, h = world_or_gen.w if hasattr(world_or_gen, "w") else world_or_gen.width, \
        world_or_gen.h if hasattr(world_or_gen, "h") else world_or_gen.height
    mask = np.zeros((w, h), dtype=bool)
    for wd in world_or_gen.wonders:
        mask[max(0, wd.x - 1):wd.x + 2, max(0, wd.y - 1):wd.y + 2] = True
        if wd.kind not in ("enchanted_forest", "salt_pan", "glowing_lake"):
            for cx, cy in wd.cells:
                mask[cx, cy] = True
    return mask


def name_all(gen) -> None:
    """Each wonder named by the people living nearest it, in their own words where they have them."""
    kinds = gen.tables.wonders["kinds"]
    forge = gen.forge
    regions = gen.tables.place_names["regions"]
    for wd in gen.wonders:
        rng = gen.rng.child(f"wonder name/{wd.id}")
        cells = np.array(wd.cells or [[wd.x, wd.y]])
        culture = gen._people_of(cells) or ""
        wd.culture = culture
        spec = kinds[wd.kind]
        geo = forge.geo_data.get(culture, {}) if culture else {}
        own = [p for kind in spec.get("geo", []) for p in geo.get(kind, [])]

        def make() -> str:
            pattern = rng.choice(own) if own and rng.chance(0.5) else rng.choice(spec["names"])
            if culture:
                return forge.fill_place(culture, pattern, rng)
            values = {"root": rng.choice(regions["stem"]), "person": rng.choice(regions["noun"])}
            from realmwalker.core import textgen

            name = " ".join(textgen.fill(pattern, rng, regions, values).split())
            return "the " + name[4:] if name.startswith("The ") else name

        wd.name = gen.namer._unique(make)


# ---------------------------------------------------------------------------- the lived history (world/ages)
HOLY = ("glowing_lake", "hot_springs", "giant_tree", "enchanted_forest", "great_falls")


def ages_year(s) -> None:
    """One year of the wonders in the history: a volcano erupts (and may bury a town), someone first stands on the
    highest peak, pilgrims come to holy waters. s is the AgeSim."""
    w = s.w
    if not w.wonders:
        return
    for wd in w.wonders:
        if wd.kind == "volcano" and wd.flags.get("awake") and s.chance("eruption"):
            _erupt(s, wd)
        elif wd.kind == "great_peak" and not s.wonder_firsts.get(wd.id) and s.year > s.year0 + 40 and \
                s.chance("first_ascent"):
            _first_ascent(s, wd)
        elif wd.kind in HOLY and not s.wonder_firsts.get(wd.id) and s.chance("pilgrimage"):
            near = s.land.nearest_standing(wd.x, wd.y, 12)
            if near:
                place = w.settlements[near[0][1]]
                s.wonder_firsts[wd.id] = s.year
                s.record("pilgrimage", {"wonder": wd.name, "place": place.name}, importance=1, places=[near[0][1]],
                         data={"wonder": wd.id})


def _erupt(s, wd: Wonder) -> None:
    near = s.land.nearest_standing(wd.x, wd.y, 7)
    place = s.w.settlements[near[0][1]].name if near else (s.area_name(wd.x, wd.y) or "the land about it")
    e = s.record("eruption", {"volcano": wd.name, "place": place}, importance=3 if near else 2,
                 places=[sid for _, sid in near[:3]], data={"wonder": wd.id})
    for dist, sid in near:
        sp = s.land.spots[sid]
        if not sp.standing:
            continue
        if dist <= 2.5 and s.r.chance(0.35):
            s.land.ruin(sp, f"buried under the ash of {wd.name}", kind="buried",
                        values={"volcano": wd.name}, importance=3)
        elif dist <= 5:
            s.land.damage(sp, 0.25)
    wd.flags.setdefault("eruptions", []).append(int(e["year"]))


def _first_ascent(s, wd: Wonder) -> None:
    people = [f for f in s.w.figures.values() if f.kind == "person" and f.alive and s.year - f.born >= 18 and
              f.fame >= 3]
    if not people:
        return
    hero = max(people, key=lambda f: (f.fame + s.r.random() * 4, -f.id))
    s.wonder_firsts[wd.id] = s.year
    hero.fame += 3
    s.record("first_ascent", {"hero": hero.name, "peak": wd.name}, importance=3, figures=[hero],
             data={"wonder": wd.id})
    wd.flags["first_climbed"] = [int(s.year), int(hero.id)]


# ---------------------------------------------------------------------------- in play
def spec_of(tables, wd: Wonder) -> dict:
    return tables.wonders["kinds"].get(wd.kind, {})


def look(tables, world, wd: Wonder) -> str:
    """How it looks from its square (the same words every time for the same wonder)."""
    spec = spec_of(tables, wd)
    options = spec.get("look_awake") if wd.flags.get("awake") and spec.get("look_awake") else spec.get("look", [])
    if not options:
        return ""
    return world.rng.child(f"wonder look/{wd.id}").choice(options)


def boons(tables, world, x: int, y: int) -> set[str]:
    """What the wonder on this square does for a traveller ("water", "warm", "heal", "bewilder", "shelter")."""
    wd = world.wonder_at(x, y)
    if wd is None:
        return set()
    return set(spec_of(tables, wd).get("boon", []))


def cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def arrive(game) -> None:
    """The first time you come to a wonder: what you see, experience for finding it, and your name for having seen
    it. After that, a word to say you are back."""
    p = game.player
    wd = game.world.wonder_at(p.x, p.y)
    if wd is None:
        return
    key = f"wonder:{wd.id}"
    if key in p.discoveries:
        if game.flavour(1) and getattr(game, "_last_wonder", None) != wd.id:
            game.say(f"<place>{cap(wd.name)}</>.", "place")
        game._last_wonder = wd.id
        return
    game._last_wonder = wd.id
    spec = spec_of(game.tables, wd)
    gained, notes = game.discover("wonder", key)
    found = game.world.rng.child(f"wonder found/{wd.id}").choice(spec.get("found") or [""])
    game.say(f"{found} <place>{cap(wd.name)}</>: {spec.get('what', 'a wonder')}.{gained}", "place")
    for note in notes:
        game.say(note, "good")
    fame = int(spec.get("fame", 0))
    if fame:
        from realmwalker.game.reputation import deed

        deed(game, f"saw {wd.name}", {}, fame=fame)
    from realmwalker.game import magic_items

    magic_items.notice(game, "discovery")
    if game.party[1:]:
        from realmwalker.game.companions import react

        react(game, "discovery", quiet=True)


def describe_line(game, wd: Wonder) -> str:
    """The wonder as told in the Look panel on the world map."""
    spec = spec_of(game.tables, wd)
    what = spec.get("what", "a wonder")
    extra = ""
    if wd.kind in ("great_peak", "volcano") and wd.flags.get("height"):
        extra = f" ({int(wd.flags['height']):,} m)"
    if wd.kind == "volcano":
        what = "a volcano, awake" if wd.flags.get("awake") else "a volcano, sleeping"
    seen = f"wonder:{wd.id}" in game.player.discoveries
    text = f"<place>{cap(wd.name)}</>, {what}{extra}."
    if seen:
        text += " " + look(game.tables, game.world, wd)
    return text


# ---------------------------------------------------------------------------- the close-up map
def shape_local(b, wd: Wonder) -> None:
    """Make a wonder's close-up map out of the wild one built for its square (b is a world.local.LocalBuilder)."""
    fn = SHAPERS.get(wd.kind)
    if fn is not None:
        fn(b, wd)


def _disc(b, cx: int, cy: int, rad: float, name: str, where=None, ragged: float = 0.0) -> np.ndarray:
    xs = np.arange(b.w)[:, None]
    ys = np.arange(b.h)[None, :]
    d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    if ragged:
        d = d + (b.np.random((b.w, b.h)) - 0.5) * ragged
    mask = d <= rad
    if where is not None:
        mask &= where
    b.t[mask] = b.tid(name)
    return mask


def _scatter(b, name: str, chance: float, where=None) -> None:
    mask = b.np.random((b.w, b.h)) < chance
    walk = b.tables.terrain.walk[b.t]
    mask &= walk & ~np.isin(b.t, [b.tid(n) for n in ("road", "bridge", "ford", "river")])
    if where is not None:
        mask &= where
    b.t[mask] = b.tid(name)


def _band(b, y0: int, thick: int, name: str, gaps: int = 2, gap_name: str = "steep_path", vertical: bool = False):
    """A ragged band of `name` across the map (a cliff, a wall of ice) with a few ways through."""
    length = b.h if vertical else b.w
    wave = np.cumsum(b.np.integers(-1, 2, size=length)) * 0.5
    wave = np.clip(wave - wave.mean(), -6, 6)
    gap_at = sorted(b.rng.randint(6, length - 7) for _ in range(gaps))
    for i in range(length):
        mid = int(round(y0 + wave[i]))
        for k in range(thick + (1 if b.rng.chance(0.3) else 0)):
            j = mid + k
            x, y = (j, i) if vertical else (i, j)
            if 0 <= x < b.w and 0 <= y < b.h and not b.is_(x, y, "river", "deep_water", "falls", "plunge_pool"):
                is_gap = any(abs(i - g) <= 1 for g in gap_at)
                b.set(x, y, gap_name if is_gap else name)


def _peak(b, wd):
    rock = b.np.random((b.w, b.h))
    b.t[rock < 0.45] = b.tid("snow")
    b.t[(rock >= 0.45) & (rock < 0.6)] = b.tid("ice")
    _scatter(b, "boulder", 0.06)
    cx, cy = b.w // 2, b.h // 2
    _disc(b, cx, cy, 3, "rock_floor")
    b.set(cx, cy, "cairn")


def _volcano(b, wd):
    cx, cy = b.w // 2, b.h // 2
    rock = b.np.random((b.w, b.h))
    b.t[:] = np.where(rock < 0.5, b.tid("ash"), b.tid("basalt"))
    _disc(b, cx, cy, 17, "crater_rim", ragged=2.5)
    _disc(b, cx, cy, 14, "basalt", ragged=2.0)
    if wd.flags.get("awake"):
        _disc(b, cx, cy, 8, "lava", ragged=2.5)
        _scatter(b, "fumarole", 0.02, where=_ring(b, cx, cy, 9, 14))
    elif wd.flags.get("crater_lake"):
        _disc(b, cx, cy, 9, "deep_water", ragged=2.0)
        _disc(b, cx, cy, 11, "shallow_water", where=~np.isin(b.t, [b.tid("deep_water")]) & _ring(b, cx, cy, 8, 11))
    else:
        _disc(b, cx, cy, 10, "snow", ragged=3.0)
        _scatter(b, "fumarole", 0.006, where=_ring(b, cx, cy, 6, 14))
    # A way in through the rim, toward the south.
    for y in range(cy + 12, cy + 20):
        for x in (cx - 1, cx, cx + 1):
            if b.is_(x, y, "crater_rim"):
                b.set(x, y, "steep_path")
    _scatter(b, "fumarole", 0.004, where=~_ring(b, cx, cy, 0, 18))


def _ring(b, cx, cy, r0, r1) -> np.ndarray:
    xs = np.arange(b.w)[:, None]
    ys = np.arange(b.h)[None, :]
    d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    return (d >= r0) & (d <= r1)


def _falls(b, wd):
    y0 = b.h // 2 - 4
    _band(b, y0, 4, "cliff", gaps=1)
    river = np.argwhere(np.isin(b.t, [b.tid("river"), b.tid("ford")]))
    xs = sorted({int(x) for x, y in river if y0 - 6 <= y <= y0 + 6})
    if not xs:  # the river must go over somewhere: bring one down the middle
        xs = list(range(b.w // 2 - 3, b.w // 2 + 3))
    for x in xs:
        for y in range(y0 - 2, y0 + 6):
            if 0 <= y < b.h:
                b.set(x, y, "falls")
    lo, hi = min(xs), max(xs)
    _disc(b, (lo + hi) // 2, y0 + 10, max(5, (hi - lo) // 2 + 4), "plunge_pool", ragged=2.0)
    _disc(b, (lo + hi) // 2, y0 + 10, max(3, (hi - lo) // 2 + 1), "deep_water", ragged=1.5)


def _canyon(b, wd):
    river = np.argwhere(b.t == b.tid("river"))
    if len(river):
        vertical = np.ptp(river[:, 1]) >= np.ptp(river[:, 0])
    else:
        vertical = True
    xs = np.arange(b.w)[:, None]
    ys = np.arange(b.h)[None, :]
    if len(river):
        # Distance from the river, worked out along the map: walls stand some way off on both sides.
        dist = np.full((b.w, b.h), 999.0)
        for x, y in river[:: max(1, len(river) // 160)]:
            dist = np.minimum(dist, np.sqrt((xs - x) ** 2 + (ys - y) ** 2))
    else:
        dist = np.abs(xs - b.w // 2) + 0 * ys
    wall = (dist > 7) & (dist < 13) & (b.np.random((b.w, b.h)) < 0.92)
    floor = dist <= 7
    b.t[wall & ~np.isin(b.t, [b.tid("river"), b.tid("bridge"), b.tid("ford"), b.tid("road")])] = b.tid("cliff_red")
    b.t[floor & ~np.isin(b.t, [b.tid("river"), b.tid("bridge"), b.tid("ford"), b.tid("road")])] = b.tid("gravel")
    # Ways down to the water, here and there.
    length = b.h if vertical else b.w
    for at in (length // 4, length // 2 + 3, 3 * length // 4):
        for k in range(-1, 2):
            for d in range(0, max(b.w, b.h)):
                x, y = ((d, at + k) if vertical else (at + k, d))
                if 0 <= x < b.w and 0 <= y < b.h and b.is_(x, y, "cliff_red"):
                    b.set(x, y, "steep_path")


def _cliffs(b, wd):
    _band(b, b.h // 2 - 2, 4, "cliff", gaps=2)


def _salt(b, wd):
    noise = b.np.random((b.w, b.h))
    b.t[:] = b.tid("salt_crust")
    pools = (noise < 0.02)
    b.t[hydrology.dilate(pools, 1) & (b.np.random((b.w, b.h)) < 0.6)] = b.tid("brine")


def _glow(b, wd):
    water = np.isin(b.t, [b.tid("deep_water")])
    shallow = np.isin(b.t, [b.tid("shallow_water")])
    b.t[water] = b.tid("glow_water")
    b.t[shallow] = b.tid("glow_shallow")


def _oasis(b, wd):
    cx, cy = b.w // 2 + b.rng.randint(-6, 6), b.h // 2 + b.rng.randint(-4, 4)
    _disc(b, cx, cy, 14, "grass", ragged=4.0)
    ring = _ring(b, cx, cy, 6, 13) & (b.np.random((b.w, b.h)) < 0.22)
    b.t[ring] = b.tid("tree_palm")
    _disc(b, cx, cy, 6, "shallow_water", ragged=2.0)
    _disc(b, cx, cy, 3.5, "deep_water", ragged=1.5)
    _scatter(b, "garden", 0.08, where=_ring(b, cx, cy, 7, 12))


def _springs(b, wd):
    cx, cy = b.w // 2, b.h // 2
    _disc(b, cx, cy, 16, "sinter", ragged=5.0)
    for _ in range(b.rng.randint(4, 7)):
        px, py = cx + b.rng.randint(-12, 12), cy + b.rng.randint(-8, 8)
        _disc(b, px, py, b.rng.uniform(1.5, 3.5), "hot_spring", ragged=1.0)
    b.set(cx + b.rng.randint(-4, 4), cy + b.rng.randint(-3, 3), "geyser")
    _scatter(b, "boulder", 0.02, where=~_ring(b, cx, cy, 0, 16))


def _fey(b, wd):
    cx, cy = b.w // 2, b.h // 2
    _disc(b, cx, cy, 7, "moss", ragged=2.0)
    ring = _ring(b, cx, cy, 3.5, 4.5)
    b.t[ring] = b.tid("glowcaps")
    b.set(cx, cy, "moonstone")


def _giant_tree(b, wd):
    cx, cy = b.w // 2, b.h // 2
    for ang in np.linspace(0, math.tau, 9)[:-1]:  # roots running out across the ground
        for k in range(6, 20):
            x = int(round(cx + math.cos(ang) * k))
            y = int(round(cy + math.sin(ang) * k * 0.8))
            if 0 <= x < b.w and 0 <= y < b.h and not b.is_(x, y, "river", "deep_water"):
                b.set(x, y, "root")
    _disc(b, cx, cy, 6.5, "giant_bark")
    _disc(b, cx, cy, 3.0, "hollow_floor")
    for y in range(cy + 3, cy + 8):  # the way into the hollow
        b.set(cx, y, "hollow_floor")


def _arches(b, wd):
    noise = b.np.random((b.w, b.h))
    b.t[noise < 0.55] = b.tid("red_rock")
    for _ in range(b.rng.randint(4, 8)):
        x, y = b.rng.randint(6, b.w - 7), b.rng.randint(5, b.h - 6)
        b.set(x, y, "stone_arch")


def _sinkhole(b, wd):
    cx, cy = b.w // 2, b.h // 2
    _disc(b, cx, cy, 15, "ledge", ragged=3.0)
    _disc(b, cx, cy, 12, "chasm")
    _scatter(b, "tree_broadleaf", 0.1, where=_ring(b, cx, cy, 12, 15) & np.isin(b.t, [b.tid("ledge")]))


def _petrified(b, wd):
    noise = b.np.random((b.w, b.h))
    b.t[noise < 0.4] = b.tid("dry_earth")
    _scatter(b, "tree_stone", 0.07)


def _ice_wall(b, wd):
    rock = b.np.random((b.w, b.h))
    top = np.arange(b.h)[None, :] < b.h // 2 - 6
    b.t[top & (rock < 0.7)] = b.tid("ice")
    b.t[top & (rock >= 0.7)] = b.tid("snow")
    _band(b, b.h // 2 - 7, 5, "ice_wall", gaps=2)  # steps cut in the ice
    _scatter(b, "crevasse", 0.01, where=top)


def _drifting(b, wd):
    _scatter(b, "drifting_stone", 0.025)


SHAPERS = {
    "great_peak": _peak, "volcano": _volcano, "great_falls": _falls, "great_canyon": _canyon,
    "great_cliffs": _cliffs, "salt_pan": _salt, "glowing_lake": _glow, "oasis": _oasis, "hot_springs": _springs,
    "enchanted_forest": _fey, "giant_tree": _giant_tree, "stone_arches": _arches, "sinkhole": _sinkhole,
    "petrified_forest": _petrified, "glacier_wall": _ice_wall, "drifting_stones": _drifting,
}
