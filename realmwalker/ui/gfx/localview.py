"""A close-up map (wild country, a town, a dungeon level) drawn with tiles.

Layers, back to front: the ground; walls; tufts and pebbles; things standing (trees, tables, doors, stairs);
traps that were found and things lying on the ground; creatures and townsfolk; you. Light is worked out per
square and blended at the corners, so torchlight and the edge of what you can see fall off softly: daylight and
night outside, hearths and wall torches indoors, your own torch underground. People glide from square to
square, the camera follows, water shimmers and fire flickers (Settings: Animations).
"""

from __future__ import annotations

import math

import numpy as np

from realmwalker.ui.gfx import dolls
from realmwalker.ui.gfx.scene import Batch, Image, Rect, Text

STEP_SECONDS = 0.13  # how long a step takes to glide
FOCUS_SECONDS = 3.0  # a scene's camera focus lasts at most this long (game/story/stage.py)
HAND_SECONDS = 0.5  # a thing handed over in a scene is drawn going from one to the other this long
NIGHT = np.array([0.20, 0.24, 0.42], np.float32)
DAY = np.array([1.0, 1.0, 1.0], np.float32)
DUSK = np.array([1.0, 0.78, 0.62], np.float32)
MEMORY = np.array([0.20, 0.21, 0.27], np.float32)
UNDERGROUND = np.array([0.07, 0.065, 0.09], np.float32)
HOLD = np.array([0.72, 0.64, 0.56], np.float32)  # a city under a mountain: dim, warm, the same at every hour
TORCH = np.array([1.0, 0.80, 0.52], np.float32)
LANTERN = np.array([0.95, 0.78, 0.48], np.float32)
COLD_BIOMES = ("tundra", "high_mountains", "mountains")


def cell_hash(w: int, h: int, seed: int) -> np.ndarray:
    xs = np.arange(w, dtype=np.uint64)[:, None]
    ys = np.arange(h, dtype=np.uint64)[None, :]
    v = (xs * np.uint64(73856093)) ^ (ys * np.uint64(19349663)) ^ np.uint64(seed & 0xFFFFFFFF)
    v = (v ^ (v >> np.uint64(13))) * np.uint64(0x5BD1E995)
    return ((v ^ (v >> np.uint64(15))) & np.uint64(0xFFFFFF)).astype(np.int64)


def _shift(a: np.ndarray, dx: int, dy: int, fill) -> np.ndarray:
    out = np.full_like(a, fill)
    w, h = a.shape
    xs_dst = slice(max(0, dx), w + min(0, dx))
    xs_src = slice(max(0, -dx), w + min(0, -dx))
    ys_dst = slice(max(0, dy), h + min(0, dy))
    ys_src = slice(max(0, -dy), h + min(0, -dy))
    out[xs_dst, ys_dst] = a[xs_src, ys_src]
    return out


class Families:
    """Tile families gathered into one table: a family is a run of rows in `rects`."""

    def __init__(self, atlas) -> None:
        self.atlas = atlas
        self.rects: list[tuple] = []
        self.index: dict[str, int] = {}
        self.start: list[int] = []
        self.count: list[int] = []

    def get(self, name: str | None) -> int:
        if not name:
            return -1
        if name in self.index:
            return self.index[name]
        names = self.atlas.family(name)
        if not names:
            self.index[name] = -1
            return -1
        fid = len(self.start)
        self.start.append(len(self.rects))
        self.count.append(len(names))
        self.rects.extend(self.atlas.rects[n] for n in names)
        self.index[name] = fid
        return fid

    def arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return (np.array(self.rects, np.float32).reshape(-1, 5), np.array(self.start or [0], np.int64),
                np.array(self.count or [1], np.int64))


class LocalArt:
    """Everything about how one local map looks that does not change from frame to frame."""

    def __init__(self, game, lm, atlas) -> None:
        tables = game.tables
        T = tables.terrain
        sp = tables.sprites
        self.lm = lm
        self.stamp = hash(lm.terrain.tobytes())
        fam = Families(atlas)
        terr = game.remap_for(lm)[lm.terrain]
        self.terr = terr
        W, H = terr.shape
        style = sp["dungeon_styles"].get(lm.meta.get("style", ""), {}) if lm.kind == "dungeon" else {}
        cold = False
        if lm.kind != "dungeon":
            try:
                cold = game.biome_key(game.player.x, game.player.y) in COLD_BIOMES
            except Exception:
                cold = False
        n = len(T.ids)
        ground = np.full(n, -1, np.int64)
        wall = np.full(n, -1, np.int64)
        obj = np.full(n, -1, np.int64)
        over = np.full(n, -1, np.int64)
        over_chance = np.ones(n, np.float32)
        anim = np.ones(n, np.int64)
        water = np.zeros(n, bool)
        self.light_spec: dict[int, tuple[float, np.ndarray]] = {}
        fence_id = T.index.get("fence", -1)
        bridge_id = T.index.get("bridge", -1)
        for i, tid in enumerate(T.ids):
            spec = sp["terrain"].get(tid, {})
            g = spec.get("ground")
            w_ = spec.get("wall")
            o = spec.get("object")
            if style:
                if tid in ("floor_stone", "floor_wood", "rock_floor", "floor_earth"):
                    g = style.get("floor", g)
                elif tid in ("wall_stone", "cave_wall", "secret_door"):
                    w_ = style.get("wall", w_)
                elif tid in ("stairs_down", "stairs_up"):
                    o = style.get(tid, o)
            if cold and spec.get("cold"):
                o = spec["cold"]
            ground[i] = fam.get(g)
            wall[i] = fam.get(w_)
            obj[i] = fam.get(o) if not spec.get("autotile") else -2
            ov = spec.get("over")
            if isinstance(ov, list):
                ov = ov[0] if ov else None  # a list: any of them, chosen per square below
                self._over_list = getattr(self, "_over_list", {})
                self._over_list[i] = [fam.get(x) for x in spec["over"]]
            over[i] = fam.get(ov)
            over_chance[i] = float(spec.get("over_chance", 1.0))
            anim[i] = int(spec.get("animate", 1))
            water[i] = bool(spec.get("water"))
            if spec.get("light"):
                r, c = spec["light"]
                self.light_spec[i] = (float(r), np.array(c, np.float32) / 255.0)
        default_ground = fam.get(style.get("floor") if style else ("floor/cobble" if lm.kind == "settlement" else "floor/grass"))
        self.hash = cell_hash(W, H, zlib_key(lm.key))
        # The ground under each square; things standing take theirs from their neighbours.
        G = ground[terr]
        is_wall = wall[terr] >= 0
        for _ in range(8):
            missing = (G < 0) & ~is_wall
            if not missing.any():
                break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                s = _shift(np.where(is_wall, -1, G), dx, dy, -1)
                take = missing & (s >= 0)
                G[take] = s[take]
                missing &= ~take
        G[(G < 0) & ~is_wall] = default_ground
        self.G = G
        self.WALL = np.where(is_wall, wall[terr], -1)
        O = obj[terr]
        if fence_id >= 0:
            fence = terr == fence_id
            if fence.any():
                mask = (np.where(_shift(fence, 0, 1, False), 1, 0) | np.where(_shift(fence, -1, 0, False), 2, 0)
                        | np.where(_shift(fence, 0, -1, False), 4, 0) | np.where(_shift(fence, 1, 0, False), 8, 0))
                pieces = np.array([fam.get(f"feature/fence_{m}") for m in range(16)], np.int64)
                O = np.where(fence, pieces[mask], O)
        if bridge_id >= 0:
            bridge = terr == bridge_id
            if bridge.any():
                vert_fam = fam.get(sp["terrain"].get("bridge", {}).get("object_vertical"))
                road_like = bridge | np.isin(terr, [T.index[t] for t in ("road", "cobbles", "bridge") if t in T.index])
                vertical = _shift(road_like, 0, 1, False) | _shift(road_like, 0, -1, False)
                horizontal = _shift(road_like, 1, 0, False) | _shift(road_like, -1, 0, False)
                O = np.where(bridge & vertical & ~horizontal, vert_fam, O)
        self.O = np.where(O == -2, -1, O)
        V = over[terr]
        roll = (self.hash % 1000) / 1000.0
        V = np.where(roll < over_chance[terr], V, -1)
        for i, choices in getattr(self, "_over_list", {}).items():
            here = terr == i
            if here.any() and choices:
                pick = np.array(choices, np.int64)[(self.hash // 7) % len(choices)]
                V = np.where(here & (V >= 0), pick, V)
        self.V = V
        self.ANIM = anim[terr]
        self.WATER = water[terr]
        self.lights = [(int(x), int(y), *self.light_spec[int(terr[x, y])]) for x, y in np.argwhere(np.isin(terr, list(self.light_spec)))] \
            if self.light_spec else []
        self.fam_rects, self.fam_start, self.fam_count = fam.arrays()
        self.trap_names = sp["traps"]


def zlib_key(key: str) -> int:
    import zlib

    return zlib.crc32(key.encode("utf-8"))


class LocalView:
    """What the close-up map remembers between frames: its look, the camera, who is gliding where."""

    def __init__(self) -> None:
        self.art: LocalArt | None = None
        self.cam: tuple[float, float] | None = None
        self.cam_key = None
        self.glide: dict = {}  # key -> [from_x, from_y, to_x, to_y, start]
        self.last_t = 0.0
        self.origin = (0.0, 0.0)  # pixel of the top left of square (0, 0)
        self.tile = 32
        self.rect = (0, 0, 0, 0)
        self.focus: tuple[int, float] | None = None  # a scene's camera focus: (its number, when it began)
        self.fx_seen: dict[int, float] = {}  # a scene's things changing hands: number -> when first drawn

    # ------------------------------------------------------------------ helpers
    def art_for(self, game, lm, atlas) -> LocalArt:
        stamp = hash(lm.terrain.tobytes())
        if self.art is None or self.art.lm is not lm or self.art.stamp != stamp:
            self.art = LocalArt(game, lm, atlas)
        return self.art

    def pos(self, key, x: int, y: int, now: float, animate: bool) -> tuple[float, float]:
        g = self.glide.get(key)
        if g is None or not animate:
            self.glide[key] = [x, y, x, y, now]
            return float(x), float(y)
        fx, fy, tx, ty, t0 = g
        if (tx, ty) != (x, y):
            cx, cy = self._at(g, now)
            if abs(cx - x) > 3 or abs(cy - y) > 3:
                self.glide[key] = [x, y, x, y, now]
                return float(x), float(y)
            self.glide[key] = g = [cx, cy, x, y, now]
        return self._at(g, now)

    @staticmethod
    def _at(g, now: float) -> tuple[float, float]:
        fx, fy, tx, ty, t0 = g
        t = min(1.0, max(0.0, (now - t0) / STEP_SECONDS))
        t = t * t * (3 - 2 * t)
        return fx + (tx - fx) * t, fy + (ty - fy) * t

    def moving(self, now: float) -> bool:
        return any(now - g[4] < STEP_SECONDS and (g[0], g[1]) != (g[2], g[3]) for g in self.glide.values())

    def to_cell(self, px: float, py: float) -> tuple[int, int] | None:
        x0, y0, w, h = self.rect
        if not (x0 <= px < x0 + w and y0 <= py < y0 + h):
            return None
        return int(math.floor((px - self.origin[0]) / self.tile)), int(math.floor((py - self.origin[1]) / self.tile))

    def cell_px(self, x: float, y: float) -> tuple[float, float]:
        return self.origin[0] + x * self.tile, self.origin[1] + y * self.tile

    # ------------------------------------------------------------------ drawing
    def draw(self, canvas, game, rect_px: tuple[int, int, int, int], tile: int, fov: np.ndarray) -> None:
        gfx = canvas.gfx
        atlas = gfx.atlas
        lm = game.local
        art = self.art_for(game, lm, atlas)
        now = gfx.now
        animate = gfx.animate
        ambient = gfx.ambient
        X0, Y0, VW, VH = rect_px
        self.rect = rect_px
        self.tile = T = tile
        p = game.player
        # The camera glides after you.
        ppos = self.pos("player", p.lx, p.ly, now, animate)
        target = (ppos[0] + 0.5, ppos[1] + 0.5)
        cam = getattr(game, "camera", None)
        if cam and animate:  # a scene eases the camera to a spot, for three seconds at most (game/story/stage.py)
            if self.focus is None or self.focus[0] != cam["n"]:
                self.focus = (cam["n"], now)
            if now - self.focus[1] < FOCUS_SECONDS:
                target = (cam["to"][0] + 0.5, cam["to"][1] + 0.5)
        key = (lm.key, T)
        dt = max(0.0, now - self.last_t)
        self.last_t = now
        if self.cam is None or self.cam_key != key or not animate:
            self.cam = target
        else:
            k = min(1.0, dt * 10.0)
            self.cam = (self.cam[0] + (target[0] - self.cam[0]) * k, self.cam[1] + (target[1] - self.cam[1]) * k)
            if abs(self.cam[0] - target[0]) > 12 or abs(self.cam[1] - target[1]) > 12:
                self.cam = target
        self.cam_key = key
        half_w, half_h = VW / (2 * T), VH / (2 * T)
        cx, cy = self.cam
        cx = lm.width / 2 if lm.width <= 2 * half_w else min(max(cx, half_w), lm.width - half_w)
        cy = lm.height / 2 if lm.height <= 2 * half_h else min(max(cy, half_h), lm.height - half_h)
        ox = round(X0 + VW / 2 - cx * T)
        oy = round(Y0 + VH / 2 - cy * T)
        self.origin = (ox, oy)
        x0 = max(0, int(math.floor(cx - half_w)) - 1)
        y0 = max(0, int(math.floor(cy - half_h)) - 1)
        x1 = min(lm.width, int(math.ceil(cx + half_w)) + 1)
        y1 = min(lm.height, int(math.ceil(cy + half_h)) + 1)
        if x1 <= x0 or y1 <= y0:
            return
        sl = (slice(x0, x1), slice(y0, y1))
        w, h = x1 - x0, y1 - y0
        vis = fov[sl]
        seen = lm.seen[sl]
        light = self._light(game, lm, art, sl, vis, seen, now, ambient)
        corners = _corners(light, art.WALL[sl] >= 0)
        # Pixel rect of every square in the slice.
        gx = (ox + (np.arange(x0, x1) * T))[:, None].repeat(h, 1).astype(np.float32)
        gy = (oy + (np.arange(y0, y1) * T))[None, :].repeat(w, 0).astype(np.float32)
        hsh = art.hash[sl]
        frame = int(now * 5) if ambient else 0
        quads: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []  # (dst, rect rows, colours)

        def layer(F: np.ndarray, mask: np.ndarray, anim: np.ndarray | None = None, shrink: float = 1.0,
                  mult: np.ndarray | None = None) -> None:
            m = mask & (F >= 0)
            if not m.any():
                return
            f = F[m]
            count = art.fam_count[f]
            if anim is not None:
                pick = np.where(anim[m] > 1, (hsh[m] + frame) % count, hsh[m] % count)
            else:
                pick = hsh[m] % count
            rows = art.fam_rects[art.fam_start[f] + pick]
            s = T * shrink
            dst = np.stack([gx[m] + (T - s) / 2, gy[m] + (T - s), np.full(len(f), s, np.float32),
                            np.full(len(f), s, np.float32)], axis=1)
            col = corners[:-1, :-1][m], corners[1:, :-1][m], corners[1:, 1:][m], corners[:-1, 1:][m]
            rgba = np.ones((len(f), 4, 4), np.float32)
            rgba[:, 0, :3], rgba[:, 1, :3], rgba[:, 2, :3], rgba[:, 3, :3] = col
            if mult is not None:
                rgba[:, :, :3] *= mult[m][:, None, None]
            quads.append((dst, rows, rgba))

        shimmer = None
        if ambient and art.WATER[sl].any():
            # Water breathes: a slow ripple of light across it.
            k = 0.90 + 0.10 * np.sin(now * 1.6 + gx / 37.0 + gy / 22.0)
            shimmer = np.where(art.WATER[sl], k, 1.0).astype(np.float32)
        layer(art.G[sl], seen, mult=shimmer)
        layer(art.WALL[sl], seen)
        layer(art.V[sl], seen)
        layer(art.O[sl], seen, art.ANIM[sl])
        cmds = _batches(quads)
        canvas.under(*cmds)
        # Traps that were found, and what lies on the ground.
        small: list[tuple[str, float, float, float, tuple]] = []
        for (fx_, fy_), f in lm.features.items():
            if f.get("kind") == "trap" and f.get("found") and x0 <= fx_ < x1 and y0 <= fy_ < y1 and lm.seen[fx_, fy_]:
                name = art.trap_names.get(f.get("trap", ""), art.trap_names.get("_"))
                c = tuple(light[fx_ - x0, fy_ - y0]) if not f.get("spent") else (0.5, 0.5, 0.5)
                small.append((name, *self.cell_px(fx_, fy_), T, c))
        from realmwalker.game.divining import marks_here

        for m in marks_here(game):  # what divination magic senses, seen or not (a ring of light: tile_art.SENSED)
            if x0 <= m["x"] < x1 and y0 <= m["y"] < y1:
                small.append((f"mark/sensed_{m['kind']}", *self.cell_px(m["x"], m["y"]), T, (1.0, 1.0, 1.0)))
        for (ix, iy), pile in lm.items.items():
            if pile and x0 <= ix < x1 and y0 <= iy < y1 and lm.seen[ix, iy]:
                it = pile[-1]
                name = item_sprite(atlas, game.tables, it)
                s = T * 0.75
                px_, py_ = self.cell_px(ix, iy)
                small.append((name, px_ + (T - s) / 2, py_ + (T - s) / 2, s, tuple(light[ix - x0, iy - y0])))
        canvas.under(*_sprites(atlas, small))
        roofed = self._roofs(canvas, game, lm, x0, y0, x1, y1, light, now, ambient)
        # People and creatures, back to front.
        people: list[tuple[float, list[str], float, float, float, tuple, bool]] = []
        for a in lm.actors:
            if not a.creatures or not (0 <= a.x < lm.width and 0 <= a.y < lm.height) or not fov[a.x, a.y]:
                continue
            if roofed(a.x, a.y):
                continue
            ax, ay = self.pos(("band", a.id), a.x, a.y, now, animate)
            names = dolls.creature(a.creatures[0].def_id, game.tables, f"band{a.id}", atlas, a.creatures[0].sex,
                                   culture=a.creatures[0].culture)
            people.append((ay, names, *self.cell_px(ax, ay), T, _cell_light(light, a.x - x0, a.y - y0), bool(a.alert)))
            if len(a.creatures) > 1:  # the rest of the band, a little behind
                second = dolls.creature(a.creatures[1].def_id, game.tables, f"band{a.id}b", atlas, a.creatures[1].sex,
                                        culture=a.creatures[1].culture)
                bx, by = self.cell_px(ax, ay)
                people.append((ay - 0.01, second, bx - T * 0.28, by - T * 0.18, T * 0.82,
                               tuple(v * 0.85 for v in _cell_light(light, a.x - x0, a.y - y0)), False))
        words = []
        if lm.kind == "settlement":
            from realmwalker.game import townlife
            from realmwalker.game.people import npcs_in, settlement_here

            s = settlement_here(game)
            said = townlife.said(game, lm)
            for npc in npcs_in(game.world, s.id) if s is not None else []:
                if not (npc.alive and npc.present and 0 <= npc.x < lm.width and 0 <= npc.y < lm.height):
                    continue
                if not fov[npc.x, npc.y] or roofed(npc.x, npc.y):
                    continue
                nx, ny = self.pos(("npc", npc.id), npc.x, npc.y, now, animate)
                small = T * 0.74 if npc.age < 14 else T  # children come up to your chest
                px_, py_ = self.cell_px(nx, ny)
                col = _cell_light(light, npc.x - x0, npc.y - y0)
                pose = npc.flags.get("pose")
                if pose == "kneel":  # (lowered by a quarter of their height: a scene)
                    py_ += small * 0.25
                elif pose == "down":
                    py_ += small * 0.4
                    col = tuple(v * 0.6 for v in col)
                people.append((ny, dolls.npc(npc, game.tables, atlas), px_ + (T - small) / 2, py_, small, col, False))
                if npc.id in said:
                    words.append((*self.cell_px(nx, ny), said[npc.id]))
        lit = bool(game.lit and game.lit.get("hours", 0) > 0) if getattr(game, "lit", None) else False
        me = dolls.character(game.leader, game.tables, lit=lit and (lm.under_rock(game.player.lx, game.player.ly)
                                                                    or game.light < 0.4),
                             atlas=atlas)
        people.append((ppos[1] + 0.001, me, *self.cell_px(*ppos), T, (1.0, 1.0, 1.0), False))
        # Companions follow a step or two behind, where you have just been.
        followers = list(game.party[1:])
        if followers:
            taken = {(a.x, a.y) for a in lm.actors}
            if lm.kind == "settlement":
                from realmwalker.game.people import npcs_in, settlement_here

                s = settlement_here(game)
                taken |= {(n.x, n.y) for n in (npcs_in(game.world, s.id) if s is not None else []) if n.alive and n.present}
            for i, (cx_, cy_) in enumerate(self._follow(game, lm, taken)[:len(followers)]):
                fx, fy = self.pos(("comp", i), cx_, cy_, now, animate)
                people.append((fy, dolls.character(followers[i], game.tables, atlas=atlas), *self.cell_px(fx, fy), T,
                               _cell_light(light, cx_ - x0, cy_ - y0), False))
        # A familiar trots (or flutters) behind, small on its square (Find Familiar).
        from realmwalker.rules import allies as ally_rules

        pets = [r for r in (ally_rules.present(c, "familiar") for c in game.party if c.alive) if r is not None]
        if pets:
            taken = {(a.x, a.y) for a in lm.actors}
            spots = self._follow(game, lm, taken)[len(followers):len(followers) + len(pets)]
            small = T * 0.62
            for i, (cx_, cy_) in enumerate(spots):
                fx, fy = self.pos(("pet", i), cx_, cy_, now, animate)
                px_, py_ = self.cell_px(fx, fy)
                people.append((fy - 0.001, [(f"creature/{pets[i]['form']}", dolls.WHITE, 0, 0)], px_ + (T - small) / 2,
                               py_, small, _cell_light(light, cx_ - x0, cy_ - y0), False))
        # The raised dead shamble after them, last of all (Animate Dead, Create Undead: Expansion 3 F.4), and the
        # bound walk with them (F.5: a spirit in its form's picture, a bound creature as itself).
        from realmwalker.game import servants

        dead = servants.following(game)
        if dead:
            taken = {(a.x, a.y) for a in lm.actors}
            start = len(followers) + len(pets)
            for i, (cx_, cy_) in enumerate(self._follow(game, lm, taken)[start:start + len(dead)]):
                fx, fy = self.pos(("dead", i), cx_, cy_, now, animate)
                rec = dead[i]
                if rec.get("picture"):  # (a spirit: its form's picture)
                    look = [(f"creature/{rec['picture']}", dolls.WHITE, 0, 0)]
                elif servants.rules.is_undead(rec):
                    look = [(f"creature/{rec['cid']}", dolls.WHITE, 0, 0)]
                else:  # (a bound creature: drawn as itself; a Simulacrum's copy, in snow)
                    look = dolls.creature(rec["cid"], game.tables, f"servant{i}", atlas)
                    if rec.get("spell") == "simulacrum":
                        look = dolls.frost(look)
                people.append((fy - 0.002, look, *self.cell_px(fx, fy),
                               T, _cell_light(light, cx_ - x0, cy_ - y0), False))
        # A Simulacrum's copy of a person walks with them, the original's likeness in snow (Expansion 3 G.3).
        from realmwalker.rules import simulacrum

        snow = [r for r in (simulacrum.record(c) for c in game.party if c.alive) if r is not None]
        if snow:
            taken = {(a.x, a.y) for a in lm.actors}
            start = len(followers) + len(pets) + len(dead)
            for i, (cx_, cy_) in enumerate(self._follow(game, lm, taken)[start:start + len(snow)]):
                fx, fy = self.pos(("snow", i), cx_, cy_, now, animate)
                look = dolls.frost(dolls.character(simulacrum.likeness(snow[i]), game.tables, atlas=atlas))
                people.append((fy - 0.003, look, *self.cell_px(fx, fy), T,
                               _cell_light(light, cx_ - x0, cy_ - y0), False))
        people.sort(key=lambda t: t[0])
        out = []
        for _, names, px_, py_, size, col, alert in people:
            out.append(Image("shadow", _shadow_image, (px_ + size * 0.18, py_ + size * 0.78, size * 0.64, size * 0.22),
                             rgba=(255, 255, 255, 150)))
            if alert:
                pulse = 0.5 + 0.5 * math.sin(now * 6) if ambient else 1.0
                out.append(Image("alert", _alert_image, (px_ - size * 0.1, py_ + size * 0.55, size * 1.2, size * 0.5),
                                 rgba=(255, 70, 50, int(110 + 90 * pulse))))
            cmd = dolls.draw(atlas, names, px_, py_ + (T - size), size, col)
            if cmd is not None:
                out.append(cmd)
        out.extend(self._handed(game, atlas, now, animate))
        size = max(11, int(T * 0.38))
        for wx, wy, text in words:  # what people say in passing, over their heads
            out.append(Text(wx + T / 2, wy - T * 0.08, text, "prose_bold", size, (250, 240, 214, 255), anchor="mb",
                            shadow=False, outline=True))
        canvas.under(*out)

    def _handed(self, game, atlas, now: float, animate: bool) -> list:
        """A thing changing hands in a scene: its picture goes from one figure to the other (half a second)."""
        fx = getattr(game, "stage_fx", None)
        if not fx or not animate:
            return []
        out = []
        T = self.tile
        for e in fx:
            t0 = self.fx_seen.setdefault(e["n"], now)
            t = (now - t0) / HAND_SECONDS
            if t > 1.0:
                continue
            t = t * t * (3 - 2 * t)
            x = e["a"][0] + (e["b"][0] - e["a"][0]) * t
            y = e["a"][1] + (e["b"][1] - e["a"][1]) * t - math.sin(t * math.pi) * 0.4
            from types import SimpleNamespace

            name = item_sprite(atlas, game.tables, SimpleNamespace(def_id=e["item"]))
            px_, py_ = self.cell_px(x, y)
            out.extend(_sprites(atlas, [(name, px_ + T * 0.25, py_ + T * 0.1, T * 0.5, (1.0, 1.0, 1.0))]))
        if len(self.fx_seen) > 32:
            self.fx_seen = {k: v for k, v in self.fx_seen.items() if now - v < 5}
        return out

    def _follow(self, game, lm, taken: set) -> list[tuple[int, int]]:
        """Where companions stand: the squares you were last on, then the free squares beside you."""
        p = game.player
        cur = (p.lx, p.ly)
        if getattr(self, "trail_key", None) != lm.key:
            self.trail_key, self.trail, self.last_cell = lm.key, [], None
        if self.last_cell is not None and self.last_cell != cur:
            if abs(self.last_cell[0] - cur[0]) <= 1 and abs(self.last_cell[1] - cur[1]) <= 1:
                self.trail.insert(0, self.last_cell)
            else:  # a jump (a door, a stair): start again
                self.trail = []
        self.trail = [c for c in self.trail if c != cur][:8]
        self.last_cell = cur
        walk = game.tables.terrain.walk
        remap = game.remap_for(lm)
        out: list[tuple[int, int]] = []
        around = [(cur[0] + dx, cur[1] + dy) for dx, dy in ((-1, 1), (1, 1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (0, -1))]
        for x, y in self.trail + around:
            if (x, y) == cur or (x, y) in out or (x, y) in taken or not lm.in_bounds(x, y):
                continue
            if not walk[remap[lm.terrain[x, y]]]:
                continue
            out.append((x, y))
        return out

    def _light(self, game, lm, art, sl, vis, seen, now, ambient) -> np.ndarray:
        w, h = vis.shape
        if lm.kind == "dungeon":
            base = UNDERGROUND
        elif lm.under_rock(game.player.lx, game.player.ly):
            base = HOLD
        else:
            day = float(game.light)
            if day >= 0.95:
                base = DAY
            elif day >= 0.45:
                t = (day - 0.45) / 0.5
                base = DUSK + (DAY - DUSK) * t
            else:
                t = max(0.0, day / 0.45)
                base = NIGHT + (DUSK - NIGHT) * t
        self.base_light = base
        L = np.empty((w, h, 3), np.float32)
        L[:] = base
        x0, y0 = sl[0].start, sl[1].start
        xs = np.arange(x0, x0 + w, dtype=np.float32)[:, None]
        ys = np.arange(y0, y0 + h, dtype=np.float32)[None, :]

        def add(cx: float, cy: float, radius: float, color: np.ndarray, strength: float = 1.0) -> None:
            d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
            f = np.clip(1.0 - d / max(0.5, radius), 0, 1) ** 1.25 * strength
            np.add(L, f[..., None] * color[None, None, :], out=L)

        flick = (lambda k: 1.0 + 0.06 * math.sin(now * 9.0 + k * 1.7) + 0.04 * math.sin(now * 23.0 + k)) if ambient else (lambda k: 1.0)
        dark = float(base.mean()) < 0.75
        if dark:
            for i, (lx, ly, r, c) in enumerate(art.lights):
                if x0 - r <= lx < x0 + w + r and y0 - r <= ly < y0 + h + r:
                    add(lx, ly, r * flick(i), c, 1.0)
            if lm.kind == "settlement":  # the watch goes its rounds with lanterns
                from realmwalker.game.people import npcs_in, settlement_here

                s = settlement_here(game)
                for npc in npcs_in(game.world, s.id) if s is not None else []:
                    if npc.alive and npc.present and npc.job in ("guard", "soldier") and \
                            x0 - 4 <= npc.x < x0 + w + 4 and y0 - 4 <= npc.y < y0 + h + 4 and \
                            lm.building_at(npc.x, npc.y) is None:
                        add(npc.x, npc.y, 3.6 * flick(npc.id), LANTERN, 0.9)
            p = game.player
            radius = 0.0
            if lm.kind == "dungeon":
                from realmwalker.game.dungeon import light_radius

                radius = float(light_radius(game))
            elif getattr(game, "lit", None) and game.lit.get("hours", 0) > 0:
                radius = 5.0
            if radius > 0:
                add(p.lx, p.ly, (radius + 2.5) * flick(99), TORCH, 1.3)
        np.clip(L, 0, 1.0, out=L)
        memory = seen & ~vis
        L[memory] = MEMORY
        L[~seen] = 0.0
        return L


    def _roofs(self, canvas, game, lm, x0, y0, x1, y1, light, now, ambient):
        """Roofs over the buildings you are not inside; returns a test for "this square is under a roof"."""
        if lm.kind != "settlement" or not lm.buildings:
            return lambda x, y: False
        from realmwalker.game.people import settlement_here
        from realmwalker.ui.gfx import houses, roofs

        s = settlement_here(game)
        skind = s.kind if s is not None else "village"
        p = game.player
        inside = lm.building_at(p.lx, p.ly)
        T = self.tile
        base = tuple(int(255 * min(1.0, v)) for v in getattr(self, "base_light", DAY))
        covered: list = []
        out = []
        glows = []
        smoke = []
        r = roofs.pixel_size(T)
        k = T // r  # screen pixels to a building pixel
        lit = float(game.light) < 0.45
        shadow = []
        for i, b in enumerate(lm.buildings):
            if b is inside or b.x >= x1 or b.y >= y1 or b.x + b.w <= x0 or b.y + b.h <= y0:
                continue
            foot = lm.seen[b.x:b.x + b.w, b.y:b.y + b.h]
            if not foot.any():
                continue
            key = f"{lm.key}/{i}"
            seed = zlib_key(key)
            door = (b.door[0] - b.x, b.door[1] - b.y)
            look = getattr(b, "look", None) or {}
            special = houses.form_of(b.shape, look.get("roof", ""), b.kind) if look else None
            if special == "none":  # a hall cut in the rock: no roof, you see it as it is
                continue
            covered.append(b)
            px_, py_ = self.cell_px(b.x, b.y)
            top = py_  # where the main picture starts (an L's main house is below its wing)
            if special is not None:  # the buildings of other peoples (houses.py)
                E = houses.extra_top(special, r, b.kind)
                spot = houses.smoke_spot(special, b.w, b.h, r, b.kind) if b.kind not in ("temple", "store") else None
                chimney = spot is not None and seed % 10 < 7
                args = (b.w, b.h, r, look["roof"], look.get("walls", "plaster"), special, b.kind, door, seed, lit)
                draw = houses.draw
            else:
                style = look.get("roof") if look.get("roof") in roofs.STYLES else roofs.style_for(skind, b.kind, key)
                wall = look.get("walls") if look.get("walls") in roofs.WALLS else roofs.wall_for(skind, b.kind, key)
                form = roofs.form_for(b.kind, b.w, b.h, key)
                chimney = b.kind in ("house", "inn", "smithy", "healer") and seed % 10 < 7
                E = roofs.extra_top(form, r)
                args = (b.w, b.h, r, style, wall, form, b.kind, door, seed, chimney, lit)
                draw = roofs.building
                cut = look.get("cut") if b.shape == "L" else None
                if cut:  # an L: the wing behind first (its front hidden under the main roof), then the main house
                    ch = cut[3]
                    wx0, ww = (0, cut[0]) if cut[0] > 0 else (cut[2], b.w - cut[2])
                    wing_door = (door[0] - wx0, door[1]) if door[1] < ch and wx0 <= door[0] < wx0 + ww \
                        else (ww // 2, ch + 1)
                    wargs = (ww, ch + 2, r, style, wall, "gable", b.kind, wing_door, seed + 1, False, lit)
                    wE = roofs.extra_top("gable", r)
                    wdst = (px_ + wx0 * T, py_ - wE * k, ww * T, ((ch + 2) * r + wE) * k)
                    out.append(Image(("bld", *wargs), lambda wargs=wargs: roofs.building(*wargs)[0], wdst,
                                     rgba=(*base, 255), smooth=False))
                    if lit and roofs.building(*wargs)[1] is not None:
                        glows.append(Image(("bldglow", *wargs), lambda wargs=wargs: roofs.building(*wargs)[1], wdst,
                                           rgba=(255, 255, 255, 235), smooth=False))
                    main_door = (door[0], door[1] - ch) if door[1] >= ch else (b.w // 2, b.h - ch - 1)
                    args = (b.w, b.h - ch, r, style, wall, form, b.kind, main_door, seed, chimney, lit)
                    top = py_ + ch * T
            rows = args[1] if draw is roofs.building else b.h
            dst = (px_, top - E * k, b.w * T, (rows * r + E) * k)
            # A shadow on the ground to the south-east, the light being from the north-west.
            shadow.append(Rect(px_ + b.w * T, py_ + T * 0.35, T * 0.3, b.h * T - T * 0.35, (0, 0, 0, 60)))
            shadow.append(Rect(px_ + T * 0.3, py_ + b.h * T, b.w * T, T * 0.22, (0, 0, 0, 60)))
            out.append(Image(("bld", *args), lambda args=args, draw=draw: draw(*args)[0], dst, rgba=(*base, 255),
                             smooth=False))
            if lit and draw(*args)[1] is not None:
                glows.append(Image(("bldglow", *args), lambda args=args, draw=draw: draw(*args)[1], dst,
                                   rgba=(255, 255, 255, 235), smooth=False))
            sign = roofs.SIGNS.get(b.kind)
            if sign and canvas.gfx.atlas.has(sign):
                sz = T * 0.7
                dx, dy = self.cell_px(b.door[0], b.door[1])
                if door[1] == b.h - 1:  # beside a door in the front wall, hung from a bracket
                    sx = min(dx + T * 0.85, px_ + b.w * T - sz)
                    sy = dy - T * 0.55
                else:  # on the roof beside a door on another side (not over the gap that shows the door)
                    ix = dx + (T if door[0] == 0 else (-T if door[0] == b.w - 1 else 0))
                    iy = dy + (T if door[1] == 0 else 0)
                    sx = min(max(ix, px_), px_ + b.w * T - T) + (T - sz) / 2
                    sy = min(max(iy, py_), py_ + b.h * T - T) + (T - sz) / 2
                out.append(Image("plaque", _plaque_image, (sx - 2, sy - 2, sz + 4, sz + 4), rgba=(*base, 235)))
                from realmwalker.ui.gfx.scene import tile_batch

                out.extend(tile_batch(canvas.gfx.atlas, [sign], np.array([[sx + sz * 0.1, sy + sz * 0.1, sz * 0.8, sz * 0.8]],
                                                                         np.float32),
                                      np.array([[base[0] / 255, base[1] / 255, base[2] / 255, 1.0]], np.float32)))
            if chimney and ambient:
                fx, fy = roofs.chimney_spot(b.w, b.h, seed, form) if special is None else spot
                if special is None and b.shape == "L" and look.get("cut"):  # (on the main house, below the wing)
                    ch = look["cut"][3]
                    fx, fy = roofs.chimney_spot(b.w, b.h - ch, seed, form)
                    fy = (ch + fy * (b.h - ch)) / b.h
                if special is None and b.shape == "L" and look.get("cut"):  # (on the main house, below the wing)
                    ch = look["cut"][3]
                    fx, fy = roofs.chimney_spot(b.w, b.h - ch, seed, form)
                    fy = (ch + fy * (b.h - ch)) / b.h
                smoke.append((px_ + b.w * T * fx + T * 0.2, py_ + b.h * T * fy - T * 0.25, seed))
        canvas.under(*shadow)
        canvas.under(*out)
        canvas.under(*glows)
        for cx, cy, seed in smoke:
            for k in range(3):
                t = (now * 0.22 + k / 3 + (seed % 97) / 97) % 1.0
                size = T * (0.35 + 0.7 * t)
                drift = T * 0.6 * t
                canvas.under(Image("smoke", roofs.smoke_puff, (cx + drift - size / 2, cy - T * 1.4 * t - size / 2, size, size),
                                   rgba=(*base, int(120 * (1 - t) * min(1.0, t * 4)))))

        def roofed(x: int, y: int) -> bool:
            return any(b.contains(x, y) for b in covered)

        return roofed


def _plaque_image():
    from PIL import Image as PImage, ImageDraw

    im = PImage.new("RGBA", (40, 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([1, 1, 38, 38], fill=(30, 22, 16, 230), outline=(150, 118, 70, 255), width=2)
    return im


def _corners(L: np.ndarray, walls: np.ndarray) -> np.ndarray:
    """Light at the corners of squares: the average of the four squares around each corner, a little darker where
    a wall meets the floor."""
    w, h, _ = L.shape
    P = np.pad(L, ((1, 1), (1, 1), (0, 0)), mode="edge")
    C = (P[:-1, :-1] + P[1:, :-1] + P[:-1, 1:] + P[1:, 1:]) / 4.0
    Wp = np.pad(walls.astype(np.float32), 1, mode="constant")
    near = (Wp[:-1, :-1] + Wp[1:, :-1] + Wp[:-1, 1:] + Wp[1:, 1:])
    C *= (1.0 - 0.07 * np.clip(near, 0, 3))[..., None]
    return C


def _cell_light(L: np.ndarray, x: int, y: int) -> tuple:
    if 0 <= x < L.shape[0] and 0 <= y < L.shape[1]:
        return tuple(float(v) for v in L[x, y])
    return (1.0, 1.0, 1.0)


def _batches(quads) -> list[Batch]:
    if not quads:
        return []
    out = []
    for dst, rows, rgba in quads:
        sheets = rows[:, 0].astype(np.int64)
        for s in np.unique(sheets):
            m = sheets == s
            out.append(Batch(int(s), dst[m], rows[m, 1:5], rgba[m]))
    return out


def _sprites(atlas, items) -> list[Batch]:
    if not items:
        return []
    names, dst, col = [], [], []
    for name, x, y, size, c in items:
        if name and atlas.has(name):
            names.append(name)
            dst.append((x, y, size, size))
            col.append((*c[:3], 1.0))
    from realmwalker.ui.gfx.scene import tile_batch

    return tile_batch(atlas, names, np.array(dst, np.float32).reshape(-1, 4), np.array(col, np.float32).reshape(-1, 4))


def item_sprite(atlas, tables, item) -> str | None:
    name = f"item/{item.def_id}"
    if atlas.has(name):
        return name
    cat = tables.items.category(item)
    fallback = {"weapon": "_weapon", "ammo": "_weapon", "armor": "_armor", "shield": "_armor", "helmet": "_armor",
                "clothing": "_armor", "food": "_food", "drink": "_drink", "book": "_book", "trade": "_trade",
                "jewellery": "_jewellery"}.get(cat, "_gear")
    return f"item/{fallback}"


def _shadow_image():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (64, 24), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([6, 4, 58, 20], fill=(0, 0, 0, 200))
    return im.filter(ImageFilter.GaussianBlur(3))


def _alert_image():
    from PIL import Image as PImage, ImageDraw, ImageFilter

    im = PImage.new("RGBA", (64, 28), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([4, 4, 60, 24], fill=(255, 255, 255, 200))
    return im.filter(ImageFilter.GaussianBlur(4))


def cursor_cmd(view: LocalView, x: int, y: int, rgba=(255, 220, 120, 220)) -> Rect:
    px, py = view.cell_px(x, y)
    return Rect(px, py, view.tile, view.tile, rgba, line=2)
