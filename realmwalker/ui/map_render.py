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


QUEST_BG = (70, 54, 20)  # a patch of lamplight on the map: somewhere work wants you


def quest_marks(game) -> list[tuple[int, int]]:
    """Where the work you have in hand wants you: sites, towns and a patch of wild country."""
    if not getattr(game, "quests", None):
        return []
    from realmwalker.game import quests

    w = game.world
    out = []
    for q in quests.active(game):
        if q["done"]:
            continue
        t = q["target"]
        if "site" in t and 0 <= t["site"] < len(w.sites):
            out.append((w.sites[t["site"]].x, w.sites[t["site"]].y))
        if "dest" in t and 0 <= t["dest"] < len(w.settlements):
            out.append((w.settlements[t["dest"]].x, w.settlements[t["dest"]].y))
        if q["template"] == "hunt_beast":
            out.append((int(t["x"]), int(t["y"])))
    return out


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
    for qx, qy in quest_marks(game):
        lx, ly = qx - mx0, qy - my0
        if 0 <= lx < mw and 0 <= ly < mh:
            bg[lx, ly] = QUEST_BG
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


NPC_COLORS = {"guard": (150, 170, 220), "priest": (200, 160, 240), "acolyte": (200, 160, 240), "lord": (240, 200, 110),
              "market_trader": (230, 200, 90), "beggar": (140, 130, 120)}


def npc_color(npc) -> tuple[int, int, int]:
    if npc.job in NPC_COLORS:
        return NPC_COLORS[npc.job]
    if npc.notable:
        return (240, 225, 150)
    return (190, 185, 170)


def local_visibility(game, lm) -> np.ndarray:
    """Cells the player can see right now; also marks them as remembered."""
    from realmwalker.game.vision import player_fov

    return player_fov(game, lm, remember=True)


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
    fg, bg = apply_light(T.fg[t], T.bg[t], max(game.light, 0.45) if lm.kind != "dungeon" else 0.8)
    fg, bg = fg.copy(), bg.copy()
    visible = fov[sl]
    seen = lm.seen[sl]
    memory = seen & ~visible
    fg[memory] = (fg[memory].astype(np.float32) * 0.35).astype(np.uint8)
    bg[memory] = (bg[memory].astype(np.float32) * 0.35).astype(np.uint8)
    ch[~seen] = ord(" ")
    bg[~seen] = UNSEEN_BG
    for (fx_, fy_), f in lm.features.items():
        sx, sy = fx_ - mx0, fy_ - my0
        if f.get("kind") == "trap" and f.get("found") and 0 <= sx < mw and 0 <= sy < mh and seen[sx, sy]:
            ch[sx, sy] = ord("^")
            fg[sx, sy] = (200, 80, 60) if not f.get("spent") else (110, 90, 80)
    for a in lm.actors:
        sx, sy = a.x - mx0, a.y - my0
        if 0 <= sx < mw and 0 <= sy < mh and visible[sx, sy] and a.creatures:
            d = game.tables.creatures[a.creatures[0].def_id]
            ch[sx, sy] = ord(d["glyph"])
            fg[sx, sy] = d["color"]
            if a.alert:
                bg[sx, sy] = (70, 16, 12)
    if lm.kind == "settlement":
        from realmwalker.game.people import npcs_in, settlement_here

        s = settlement_here(game)
        for npc in npcs_in(game.world, s.id) if s is not None else []:
            sx, sy = npc.x - mx0, npc.y - my0
            if npc.alive and npc.present and 0 <= sx < mw and 0 <= sy < mh and visible[sx, sy]:
                ch[sx, sy] = ord("☺")
                fg[sx, sy] = npc_color(npc)
    if lm.items:
        from realmwalker.ui import colors
        from realmwalker.ui.screens.sheets import item_glyph

        for (ix, iy), pile in lm.items.items():
            sx, sy = ix - mx0, iy - my0
            if pile and 0 <= sx < mw and 0 <= sy < mh and seen[sx, sy]:
                glyph, color = item_glyph(game.tables.items.category(pile[-1]))
                ch[sx, sy] = ord(glyph)
                fg[sx, sy] = colors.named(color) if visible[sx, sy] else (90, 84, 60)
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
