"""Turns world and local-map arrays into glyphs and colours, using numpy for speed.

The full overworld picture is computed once per world and cached; each frame just slices the
visible window out of it and applies fog of war and the light of day or night.
"""

from __future__ import annotations

import numpy as np

from realmwalker.world.model import World
from realmwalker.world.tables import Tables

ROAD_FG = np.array([176, 136, 84], dtype=np.uint8)
RIVER_FG = {1: (86, 136, 214), 2: (96, 150, 226), 3: (120, 170, 240)}
RIVER_BG = {1: (16, 30, 54), 2: (14, 32, 66), 3: (12, 30, 76)}

# Road glyph by which of the four neighbours also have road: N=1, E=2, S=4, W=8.
ROAD_GLYPHS = {
    0: "·", 1: "║", 4: "║", 5: "║", 2: "═", 8: "═", 10: "═", 3: "╚", 6: "╔", 12: "╗", 9: "╝",
    7: "╠", 14: "╦", 13: "╣", 11: "╩", 15: "╬",
}


def _variation(width: int, height: int, seed: int) -> np.ndarray:
    """A fixed pseudo-random number per tile, so glyph choice is stable between frames."""
    xs = np.arange(width, dtype=np.uint64)[:, None]
    ys = np.arange(height, dtype=np.uint64)[None, :]
    h = (xs * np.uint64(73856093)) ^ (ys * np.uint64(19349663)) ^ np.uint64(seed & 0xFFFFFFFF)
    h = (h ^ (h >> np.uint64(13))) * np.uint64(0x5BD1E995)
    return (h ^ (h >> np.uint64(15))) & np.uint64(0xFFFF)


def road_mask(road: np.ndarray) -> np.ndarray:
    m = np.zeros(road.shape, dtype=np.uint8)
    m[:, 1:] |= np.where(road[:, :-1], 1, 0).astype(np.uint8)  # north neighbour
    m[:-1, :] |= np.where(road[1:, :], 2, 0).astype(np.uint8)  # east
    m[:, :-1] |= np.where(road[:, 1:], 4, 0).astype(np.uint8)  # south
    m[1:, :] |= np.where(road[:-1, :], 8, 0).astype(np.uint8)  # west
    return m


class OverworldPicture:
    """The whole overworld as (ch, fg, bg) arrays, before fog and lighting."""

    def __init__(self, world: World, tables: Tables) -> None:
        B = tables.biomes
        # Map this world's stored biome order onto the current data (saves stay valid if data changes).
        remap = np.array([B.index.get(bid, B.index["plains"]) for bid in world.biome_ids], dtype=np.int32)
        biome = remap[world.biome]
        var = _variation(world.width, world.height, world.meta.seed)
        counts = B.glyph_counts[biome]
        ch = B.glyphs[biome, (var % counts.astype(np.uint64)).astype(np.int64)]
        shade = 0.88 + (((var >> np.uint64(4)) % np.uint64(16)).astype(np.float32) / 15.0) * 0.24
        fg = np.clip(B.fg[biome].astype(np.float32) * shade[..., None], 0, 255).astype(np.uint8)
        bg = B.bg[biome].copy()

        for size in (1, 2, 3):
            m = world.river == size
            ch[m] = ord("≈") if size >= 2 else ord("~")
            fg[m] = RIVER_FG[size]
            bg[m] = RIVER_BG[size]

        roads = world.road.astype(bool)
        mask = road_mask(roads)
        glyph_for = np.array([ord(ROAD_GLYPHS.get(i, "·")) for i in range(16)], dtype=np.int32)
        ch[roads] = glyph_for[mask[roads]]
        fg[roads] = ROAD_FG
        bridge = roads & (world.river > 0)
        bg[bridge] = (40, 34, 30)

        types = tables.sites["site_types"]
        for s in world.sites:
            spec = types.get(s.kind)
            if spec:
                ch[s.x, s.y] = ord(spec["glyph"])
                fg[s.x, s.y] = spec["fg"]
        stypes = tables.sites["settlement_types"]
        for s in world.settlements:
            spec = stypes[s.kind]
            ch[s.x, s.y] = ord(spec["glyph"])
            fg[s.x, s.y] = spec["fg"]
            bg[s.x, s.y] = (30, 24, 18)
        self.ch = ch.astype(np.int32)
        self.fg = fg
        self.bg = bg


def apply_light(fg: np.ndarray, bg: np.ndarray, light: float) -> tuple[np.ndarray, np.ndarray]:
    """Darken and cool colours as the light fails."""
    if light >= 0.999:
        return fg, bg
    k = 0.30 + 0.70 * light
    tint = np.array([0.80, 0.88, 1.15]) * (1 - light) + np.array([1.0, 1.0, 1.0]) * light
    f = np.clip(fg.astype(np.float32) * k * tint, 0, 255).astype(np.uint8)
    b = np.clip(bg.astype(np.float32) * k * tint, 0, 255).astype(np.uint8)
    return f, b


# ---------------------------------------------------------------------------- viewports
def camera(center: int, view: int, size: int) -> tuple[int, int]:
    """(first map cell shown, screen offset) for one axis, keeping the centre in view."""
    if size <= view:
        return 0, (view - size) // 2
    start = max(0, min(size - view, center - view // 2))
    return start, 0


UNSEEN_BG = (6, 6, 9)
PLAYER_FG = (255, 244, 200)


def draw_overworld(con, game, picture: OverworldPicture, x: int, y: int, w: int, h: int,
                   cursor: tuple[int, int] | None = None) -> tuple[int, int, int, int]:
    """Draw the overworld into console rect (x, y, w, h). Returns (map_x0, map_y0, off_x, off_y)
    so callers can convert screen cells to map cells."""
    world = game.world
    p = game.player
    mx0, ox = camera(p.x, w, world.width)
    my0, oy = camera(p.y, h, world.height)
    mw, mh = min(w, world.width), min(h, world.height)
    sl = (slice(mx0, mx0 + mw), slice(my0, my0 + mh))
    ch = picture.ch[sl].copy()
    fg, bg = apply_light(picture.fg[sl], picture.bg[sl], game.light)
    fg, bg = fg.copy(), bg.copy()
    explored = p.explored[sl]
    ch[~explored] = ord(" ")
    bg[~explored] = UNSEEN_BG
    # Places you have heard of show even where you have not been.
    stypes = game.tables.sites["settlement_types"]
    for sid in p.known_settlements:
        s = world.settlements[sid]
        lx, ly = s.x - mx0, s.y - my0
        if 0 <= lx < mw and 0 <= ly < mh and not explored[lx, ly]:
            ch[lx, ly] = ord(stypes[s.kind]["glyph"])
            fg[lx, ly] = tuple(int(c * 0.6) for c in stypes[s.kind]["fg"])
    px, py = p.x - mx0, p.y - my0
    ch[px, py] = ord("@")
    fg[px, py] = PLAYER_FG
    dst = (slice(x + ox, x + ox + mw), slice(y + oy, y + oy + mh))
    con.rgb["ch"][dst] = ch
    con.rgb["fg"][dst] = fg
    con.rgb["bg"][dst] = bg
    if cursor is not None:
        cx, cy = cursor[0] - mx0 + x + ox, cursor[1] - my0 + y + oy
        if x <= cx < x + w and y <= cy < y + h:
            con.rgb["bg"][cx, cy] = (120, 100, 40)
    return mx0, my0, ox, oy


_SIGHT_CACHE: dict[int, tuple[int, bool, np.ndarray]] = {}
# In woods you see a short way in every direction rather than down long gaps between trunks.
WOODLAND_SIGHT = {"forest": 10, "pine_forest": 12, "marsh": 16}


def sight_blockers(game, lm, woodland: bool = False) -> np.ndarray:
    """Which cells let light through. Walls and closed doors block sight. A lone tree does not
    hide what lies behind it; thickets of three or more trees do, except in woodland, where
    sight is short instead (see WOODLAND_SIGHT)."""
    T = game.tables.terrain
    remap = game.remap_for(lm)
    terrain = remap[lm.terrain]
    stamp = hash(lm.terrain.tobytes())
    cached = _SIGHT_CACHE.get(id(lm))
    if cached is not None and cached[0] == stamp and cached[1] == woodland:
        return cached[2]
    see = T.see[terrain].copy()
    tree = T.tag_mask("tree")[terrain]
    if woodland:
        see[tree] = True
    else:
        padded = np.pad(tree, 1)
        neighbours = sum(padded[1 + dx: 1 + dx + tree.shape[0], 1 + dy: 1 + dy + tree.shape[1]]
                         for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
        see[tree & (neighbours < 3)] = True
    _SIGHT_CACHE[id(lm)] = (stamp, woodland, see)
    return see


def local_visibility(game, lm) -> np.ndarray:
    """Cells the player can see right now; also marks them as remembered."""
    import tcod.map

    p = game.player
    woodland_radius = WOODLAND_SIGHT.get(game.biome_key(p.x, p.y)) if lm.kind != "settlement" else None
    see = sight_blockers(game, lm, woodland=woodland_radius is not None)
    light = game.light
    radius = 0 if light >= 0.9 else max(4, int(4 + light * 28))
    if woodland_radius:
        radius = min(radius, woodland_radius) if radius else woodland_radius
    fov = tcod.map.compute_fov(see, (p.lx, p.ly), radius=radius, light_walls=True)
    lm.seen |= fov
    return fov


def draw_local(con, game, x: int, y: int, w: int, h: int, cursor: tuple[int, int] | None = None) -> tuple[int, int, int, int]:
    lm = game.local
    p = game.player
    T = game.tables.terrain
    remap = game.remap_for(lm)
    fov = local_visibility(game, lm)
    mx0, ox = camera(p.lx, w, lm.width)
    my0, oy = camera(p.ly, h, lm.height)
    mw, mh = min(w, lm.width), min(h, lm.height)
    sl = (slice(mx0, mx0 + mw), slice(my0, my0 + mh))
    t = remap[lm.terrain[sl]]
    var = lm.variant[sl].astype(np.int64)
    ch = T.glyphs[t, var % T.glyph_counts[t]]
    fg, bg = apply_light(T.fg[t], T.bg[t], max(game.light, 0.45))
    fg, bg = fg.copy(), bg.copy()
    visible = fov[sl]
    seen = lm.seen[sl]
    memory = seen & ~visible
    fg[memory] = (fg[memory].astype(np.float32) * 0.35).astype(np.uint8)
    bg[memory] = (bg[memory].astype(np.float32) * 0.35).astype(np.uint8)
    ch[~seen] = ord(" ")
    bg[~seen] = UNSEEN_BG
    px, py = p.lx - mx0, p.ly - my0
    ch[px, py] = ord("@")
    fg[px, py] = PLAYER_FG
    dst = (slice(x + ox, x + ox + mw), slice(y + oy, y + oy + mh))
    con.rgb["ch"][dst] = ch
    con.rgb["fg"][dst] = fg
    con.rgb["bg"][dst] = bg
    if cursor is not None:
        cx, cy = cursor[0] - mx0 + x + ox, cursor[1] - my0 + y + oy
        if x <= cx < x + w and y <= cy < y + h:
            con.rgb["bg"][cx, cy] = (120, 100, 40)
    return mx0, my0, ox, oy
