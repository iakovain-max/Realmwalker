"""The overworld painted like a map: colour that blends from one country to the next, hills shaded from the
north-west, coasts, rivers and roads drawn as lines, and little trees, hills and mountains stamped on.

Pure Pillow and numpy, no window: a WorldPainter paints any square piece of the world ("a chunk") at any number
of pixels per square of country, and a whole-world picture for the world map. Chunks are painted in a background
thread by ChunkCache so walking never waits for them.
"""

from __future__ import annotations

import math
import threading
import zlib
from collections import OrderedDict
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from realmwalker.world.model import DIRS

MARKS = {"grass": 1, "broadleaf": 2, "pine": 3, "hills": 4, "mountains": 5, "peaks": 6, "marsh": 7, "tundra": 8, "dunes": 9}
CHUNK_PX = 768  # a chunk is about this many pixels across, whatever the scale


class WorldPainter:
    def __init__(self, world, tables) -> None:
        sp = tables.sprites["world"]
        self.world = world
        self.seed = int(world.meta.seed)
        W, H = world.width, world.height
        biomes = sp["biomes"]
        keys = list(world.biome_ids)
        default = biomes.get("plains", {"color": [100, 110, 70]})
        pal = np.array([biomes.get(k, default)["color"] for k in keys], np.float32)
        deep = np.array([biomes.get(k, default).get("deep", biomes.get(k, default)["color"]) for k in keys], np.float32)
        marks = np.array([MARKS.get(biomes.get(k, {}).get("marks", ""), 0) for k in keys], np.int64)
        dens = np.array([biomes.get(k, {}).get("density", 0.0) for k in keys], np.float32)
        water_b = np.array([k in ("ocean", "lake") for k in keys], bool)
        b = world.biome.astype(np.int64)
        elev = world.elevation.astype(np.float32)
        self.water = water_b[b]
        depth = np.clip(-elev / 400.0, 0, 1)[..., None]
        color = np.where(self.water[..., None], pal[b] * (1 - depth) + deep[b] * depth, pal[b]).astype(np.float32)
        land = ~self.water
        # Soften the land's colours a little where countries meet (water keeps its own).
        soft = _blur(color * land[..., None], 1) / np.maximum(_blur(land.astype(np.float32), 1), 1e-3)[..., None]
        self.color = np.where(land[..., None], soft * 0.6 + color * 0.4, color).astype(np.float32)
        self.elev = np.where(self.water, 0, np.maximum(elev, 0)).astype(np.float32)
        # Shading worked out per square from a smoothed height, then blended: light from the north-west.
        e = _blur(_blur(self.elev, 1), 1)
        gx = np.zeros_like(e)
        gy = np.zeros_like(e)
        gx[1:-1, :] = (e[2:, :] - e[:-2, :]) * 0.5
        gy[:, 1:-1] = (e[:, 2:] - e[:, :-2]) * 0.5
        self.shade = np.clip(1.0 - (gx + gy) / 260.0, 0.6, 1.32).astype(np.float32)
        self.marks = marks[b]
        self.density = dens[b]
        self.road_rgb = tuple(sp["road"])
        self.river_rgb = tuple(sp["river"])
        self.ink = tuple(sp["ink"])
        self.shore = tuple(sp["shore"])
        self.W, self.H = W, H
        self.rivers = self._trace_rivers()
        self.roads = self._road_segments()
        rng = np.random.default_rng(self.seed ^ 0x5EED)
        self.jitter = rng.random((W, H, 8)).astype(np.float32)

    # ------------------------------------------------------------------ lines
    def _trace_rivers(self) -> list[list[tuple[float, float, int]]]:
        """Each river as a list of (x, y, size) through square centres, smoothed."""
        w = self.world
        river = w.river
        if not river.any():
            return []
        W, H = self.W, self.H
        nxt = {}
        has_up = np.zeros((W, H), bool)
        for x, y in np.argwhere(river > 0):
            d = int(w.flow[x, y])
            dx, dy = DIRS[d] if 0 < d < len(DIRS) else (0, 0)
            tx, ty = x + dx, y + dy
            if (dx or dy) and 0 <= tx < W and 0 <= ty < H:
                nxt[(int(x), int(y))] = (int(tx), int(ty))
                if river[tx, ty] > 0:
                    has_up[tx, ty] = True
        chains = []
        seen = set()
        for x, y in np.argwhere((river > 0) & ~has_up):
            cur = (int(x), int(y))
            chain = []
            while cur is not None and cur not in seen:
                seen.add(cur)
                chain.append((cur[0] + 0.5, cur[1] + 0.5, int(river[cur])))
                n = nxt.get(cur)
                if n is None:
                    break
                if river[n] == 0 or n in seen:
                    chain.append((n[0] + 0.5, n[1] + 0.5, int(river[cur])))
                    break
                cur = n
            # Where a river runs through a lake it is the lake: leave those stretches out.
            pieces, piece = [], []
            for k, (x, y, sz) in enumerate(chain):
                if self.water[min(W - 1, int(x)), min(H - 1, int(y))]:
                    if piece:
                        piece.append((x, y, sz))
                        pieces.append(piece)
                    piece = []
                else:
                    if not piece and k > 0:
                        piece.append(chain[k - 1])
                    piece.append((x, y, sz))
            if piece:
                pieces.append(piece)
            chains.extend(_chaikin(pc, 2) for pc in pieces if len(pc) >= 2)
        return chains

    def _road_segments(self) -> list[tuple[float, float, float, float]]:
        """Roads as short segments of smoothed curves: each stretch between crossroads is traced and rounded."""
        road = self.world.road.astype(bool)
        cells = {(int(x), int(y)) for x, y in np.argwhere(road)}

        def nbrs(c):
            x, y = c
            return [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if (x + dx, y + dy) in cells]

        degree = {c: len(nbrs(c)) for c in cells}
        used = set()
        segs = []
        starts = sorted(c for c in cells if degree[c] != 2)
        for start in starts:
            for n in nbrs(start):
                if (start, n) in used:
                    continue
                path = [start, n]
                used.add((start, n))
                used.add((n, start))
                prev, cur = start, n
                while degree.get(cur, 0) == 2:
                    nxt = [m for m in nbrs(cur) if m != prev]
                    if not nxt or (cur, nxt[0]) in used:
                        break
                    used.add((cur, nxt[0]))
                    used.add((nxt[0], cur))
                    prev, cur = cur, nxt[0]
                    path.append(cur)
                pts = _chaikin([(x + 0.5, y + 0.5, 1) for x, y in path], 3)
                segs.extend((a[0], a[1], b[0], b[1]) for a, b in zip(pts[:-1], pts[1:]))
        for c in sorted(cells):  # rings of road with no crossroads at all
            for n in nbrs(c):
                if (c, n) not in used:
                    used.add((c, n))
                    used.add((n, c))
                    segs.append((c[0] + 0.5, c[1] + 0.5, n[0] + 0.5, n[1] + 0.5))
        return segs

    # ------------------------------------------------------------------ painting
    def chunk_cells(self, ppc: int) -> int:
        return max(8, CHUNK_PX // max(1, ppc))

    def paint(self, x0: int, y0: int, nx: int, ny: int, ppc: int, *, detail: bool = True) -> Image.Image:
        """Squares [x0, x0+nx) x [y0, y0+ny) at ppc pixels per square, as an RGBA image."""
        Wpx, Hpx = nx * ppc, ny * ppc
        seed = zlib.crc32(f"{self.seed}/{x0}/{y0}/{ppc}".encode())
        # Smooth fields are worked out on a coarser grid (every `step` pixels) and enlarged; edges are cut sharp
        # afterwards at full size.
        step = max(1, ppc // 6)
        Wl, Hl = -(-Wpx // step), -(-Hpx // step)
        u = x0 + ((np.arange(Wl, dtype=np.float32) + 0.5) * step) / ppc - 0.5
        v = y0 + ((np.arange(Hl, dtype=np.float32) + 0.5) * step) / ppc - 0.5
        warp_cell = max(6.0, ppc * 0.9) / step
        gseed = self.seed & 0xFFFF
        ox, oy = x0 * ppc // step, y0 * ppc // step
        wx = _world_noise(Wl, Hl, warp_cell, gseed + 1, ox, oy) * 0.42
        wy = _world_noise(Wl, Hl, warp_cell, gseed + 2, ox, oy) * 0.42
        wx += _world_noise(Wl, Hl, warp_cell * 3.1, gseed + 3, ox, oy) * 0.35
        wy += _world_noise(Wl, Hl, warp_cell * 3.1, gseed + 4, ox, oy) * 0.35
        U = u[:, None] + wx
        V = v[None, :] + wy
        col = _up(_bilinear(self.color, U, V), Wpx, Hpx)
        wat = _up(_bilinear(self.water.astype(np.float32), U, V), Wpx, Hpx)
        shade = _up(_bilinear(self.shade, u[:, None] + wx * 0.2, v[None, :] + wy * 0.2), Wpx, Hpx)
        ripple_f = _up(V * 9.0 + wx * 6.0, Wpx, Hpx)
        land = wat < 0.5
        col *= np.where(land, shade, 1.0)[..., None]
        # Coasts: a pale shore and a dark line where land meets water; water darker away from it.
        edge = np.abs(wat - 0.5)
        shore = land & (edge < 0.13)
        col[shore] = col[shore] * 0.6 + np.array(self.shore, np.float32) * 0.4
        coastline = edge < 0.035
        col[coastline] = np.array(self.ink, np.float32) * 0.7 + col[coastline] * 0.3
        sea = ~land
        if sea.any():
            fade = np.clip((wat - 0.5) * 2.0, 0, 1)
            col[sea] *= (1.0 - 0.25 * fade[sea])[:, None]
            ripple = (0.5 + 0.5 * np.sin(ripple_f * math.pi)) > 0.93
            ripple &= sea & (edge > 0.12)
            col[ripple] *= 1.18
        # Paper grain.
        grain = np.random.default_rng(seed).normal(1.0, 0.035, (Wpx, Hpx)).astype(np.float32)
        col *= grain[..., None]
        rgb = np.clip(col, 0, 255).astype(np.uint8).transpose(1, 0, 2)
        im = Image.fromarray(np.ascontiguousarray(rgb), "RGB").convert("RGBA")
        draw = ImageDraw.Draw(im)
        self._draw_rivers(draw, x0, y0, nx, ny, ppc)
        self._draw_roads(draw, x0, y0, nx, ny, ppc)
        if detail and ppc >= 6:
            self._stamp(im, x0, y0, nx, ny, ppc)
        return im

    def _draw_rivers(self, draw, x0, y0, nx, ny, ppc) -> None:
        widths = {1: 0.10, 2: 0.17, 3: 0.26}
        margin = 2
        for chain in self.rivers:
            pts = [((x - x0) * ppc, (y - y0) * ppc, s) for x, y, s in chain]
            for (ax, ay, s), (bx, by, _) in zip(pts[:-1], pts[1:]):
                if max(ax, bx) < -margin * ppc or min(ax, bx) > (nx + margin) * ppc:
                    continue
                if max(ay, by) < -margin * ppc or min(ay, by) > (ny + margin) * ppc:
                    continue
                w = max(1, int(ppc * widths.get(s, 0.12)))
                draw.line([(ax, ay), (bx, by)], fill=tuple(int(c * 0.55) for c in self.river_rgb) + (255,), width=w + 2)
        for chain in self.rivers:
            pts = [((x - x0) * ppc, (y - y0) * ppc, s) for x, y, s in chain]
            for (ax, ay, s), (bx, by, _) in zip(pts[:-1], pts[1:]):
                if max(ax, bx) < -margin * ppc or min(ax, bx) > (nx + margin) * ppc:
                    continue
                if max(ay, by) < -margin * ppc or min(ay, by) > (ny + margin) * ppc:
                    continue
                w = max(1, int(ppc * widths.get(s, 0.12)))
                draw.line([(ax, ay), (bx, by)], fill=self.river_rgb + (255,), width=w)
                r = w / 2
                draw.ellipse([bx - r, by - r, bx + r, by + r], fill=self.river_rgb + (255,))

    def _draw_roads(self, draw, x0, y0, nx, ny, ppc) -> None:
        w = max(1, int(ppc * 0.11))
        dark = tuple(int(c * 0.5) for c in self.road_rgb) + (255,)
        segs = [((ax - x0) * ppc, (ay - y0) * ppc, (bx - x0) * ppc, (by - y0) * ppc) for ax, ay, bx, by in self.roads
                if x0 - 3 <= ax <= x0 + nx + 3 and y0 - 3 <= ay <= y0 + ny + 3]
        for ax, ay, bx, by in segs:
            draw.line([(ax, ay), (bx, by)], fill=dark, width=w + 2)
        for ax, ay, bx, by in segs:
            draw.line([(ax, ay), (bx, by)], fill=self.road_rgb + (255,), width=w)
            r = w / 2
            draw.ellipse([ax - r, ay - r, ax + r, ay + r], fill=self.road_rgb + (255,))
            draw.ellipse([bx - r, by - r, bx + r, by + r], fill=self.road_rgb + (255,))

    def _stamp(self, im: Image.Image, x0, y0, nx, ny, ppc) -> None:
        """Trees, hills and mountains, back to front."""
        m = 2
        xa, ya = max(0, x0 - m), max(0, y0 - m)
        xb, yb = min(self.W, x0 + nx + m), min(self.H, y0 + ny + m)
        marks = self.marks[xa:xb, ya:yb]
        if not marks.any():
            return
        dens = self.density[xa:xb, ya:yb]
        jit = self.jitter[xa:xb, ya:yb]
        road = self.world.road[xa:xb, ya:yb]
        river = self.world.river[xa:xb, ya:yb] > 0
        settled = (self.world.settlement_grid[xa:xb, ya:yb] >= 0) | (self.world.site_grid[xa:xb, ya:yb] >= 0)
        items: list[tuple[float, Image.Image, int, int]] = []
        for (i, j) in np.argwhere(marks > 0):
            kind = int(marks[i, j])
            cx, cy = xa + int(i), ya + int(j)
            if settled[i, j]:
                continue
            r = jit[i, j]
            if r[0] > dens[i, j]:
                continue
            px = (cx - x0) * ppc
            py = (cy - y0) * ppc
            busy = road[i, j] or river[i, j]
            if kind in (2, 3):
                n = 3 if ppc >= 16 else 2
                for k in range(n):
                    if busy and k > 0:
                        break
                    tx = px + ppc * (0.15 + 0.7 * r[1 + k])
                    ty = py + ppc * (0.25 + 0.65 * r[4 + (k % 4)])
                    st = stamp("tree" if kind == 2 else "pine", ppc, int(r[7] * 4 + k) % 4)
                    items.append((ty, st, int(tx - st.width / 2), int(ty - st.height)))
            elif kind == 4:
                if busy:
                    continue
                st = stamp("hill", ppc, int(r[1] * 3))
                tx, ty = px + ppc * (0.5 + 0.3 * (r[2] - 0.5)), py + ppc * (0.7 + 0.2 * r[3])
                items.append((ty, st, int(tx - st.width / 2), int(ty - st.height)))
            elif kind in (5, 6):
                st = stamp("peak" if kind == 6 else "mountain", ppc, int(r[1] * 4))
                tx, ty = px + ppc * (0.5 + 0.35 * (r[2] - 0.5)), py + ppc * (0.85 + 0.15 * r[3])
                items.append((ty, st, int(tx - st.width / 2), int(ty - st.height)))
            elif kind == 7:
                for k in range(2):
                    st = stamp("reeds", ppc, int(r[1 + k] * 3))
                    tx, ty = px + ppc * (0.2 + 0.6 * r[2 + k]), py + ppc * (0.3 + 0.6 * r[4 + k])
                    items.append((ty, st, int(tx - st.width / 2), int(ty - st.height)))
            elif kind == 1 and ppc >= 12:
                st = stamp("tuft", ppc, int(r[1] * 3))
                tx, ty = px + ppc * r[2], py + ppc * (0.3 + 0.6 * r[3])
                items.append((ty, st, int(tx - st.width / 2), int(ty - st.height)))
            elif kind == 8 and ppc >= 12:
                st = stamp("scrub", ppc, int(r[1] * 3))
                tx, ty = px + ppc * r[2], py + ppc * (0.3 + 0.6 * r[3])
                items.append((ty, st, int(tx - st.width / 2), int(ty - st.height)))
            elif kind == 9 and ppc >= 10:
                st = stamp("dune", ppc, int(r[1] * 3))
                tx, ty = px + ppc * (0.5 + 0.3 * (r[2] - 0.5)), py + ppc * (0.5 + 0.4 * r[3])
                items.append((ty, st, int(tx - st.width / 2), int(ty - st.height)))
        items.sort(key=lambda t: t[0])
        W, H = im.size
        for _, st, x, y in items:
            if x >= W or y >= H or x + st.width <= 0 or y + st.height <= 0:
                continue
            sx, sy = max(0, -x), max(0, -y)
            im.alpha_composite(st, (x + sx, y + sy), (sx, sy))

    def overview(self, ppc: int) -> Image.Image:
        """The whole world at a small scale (the world map, and a stand-in while chunks are painted)."""
        return self.paint(0, 0, self.W, self.H, ppc, detail=ppc >= 6)


def _world_noise(w: int, h: int, cell: float, seed: int, ox: int, oy: int) -> np.ndarray:
    """Noise in world pixel space, so neighbouring chunks agree at their edges."""
    # Built from a coarse lattice indexed by absolute position: identical values where chunks meet.
    xs = (np.arange(w, dtype=np.float64) + ox) / cell
    ys = (np.arange(h, dtype=np.float64) + oy) / cell
    x0, y0 = np.floor(xs).astype(np.int64), np.floor(ys).astype(np.int64)
    fx, fy = (xs - x0).astype(np.float32), (ys - y0).astype(np.float32)
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)

    def lattice(ix, iy):
        v = (ix * 374761393 + iy * 668265263 + seed * 2246822519) & 0xFFFFFFFF
        v = ((v ^ (v >> 13)) * 1274126177) & 0xFFFFFFFF
        return ((v & 0xFFFF) / 32767.5 - 1.0).astype(np.float32)

    X0, Y0 = x0[:, None], y0[None, :]
    a, b = lattice(X0, Y0), lattice(X0 + 1, Y0)
    c, d = lattice(X0, Y0 + 1), lattice(X0 + 1, Y0 + 1)
    top = a + (b - a) * fx[:, None]
    bot = c + (d - c) * fx[:, None]
    return top + (bot - top) * fy[None, :]


def _blur(a: np.ndarray, r: int) -> np.ndarray:
    """A box blur of radius r over the first two axes (edges repeat)."""
    out = a.astype(np.float32)
    for axis in (0, 1):
        pad = [(0, 0)] * out.ndim
        pad[axis] = (r, r)
        padded = np.pad(out, pad, mode="edge")
        acc = np.zeros_like(out)
        for k in range(2 * r + 1):
            sl = [slice(None)] * out.ndim
            sl[axis] = slice(k, k + out.shape[axis])
            acc += padded[tuple(sl)]
        out = acc / (2 * r + 1)
    return out


def _up(a: np.ndarray, W: int, H: int) -> np.ndarray:
    """Enlarge a field [x, y] or [x, y, channel] to (W, H) with bilinear filtering."""
    if a.shape[0] == W and a.shape[1] == H:
        return a.astype(np.float32)
    if a.ndim == 3:
        return np.stack([_up(a[..., k], W, H) for k in range(a.shape[2])], axis=2)
    im = Image.fromarray(np.ascontiguousarray(a.T.astype(np.float32)), "F").resize((W, H), Image.BILINEAR)
    return np.asarray(im, np.float32).T


def _bilinear(field: np.ndarray, U: np.ndarray, V: np.ndarray) -> np.ndarray:
    W, H = field.shape[:2]
    U = np.clip(U, 0, W - 1.001)
    V = np.clip(V, 0, H - 1.001)
    u0 = U.astype(np.int64)
    v0 = V.astype(np.int64)
    fu = (U - u0).astype(np.float32)
    fv = (V - v0).astype(np.float32)
    if field.ndim == 3:
        fu, fv = fu[..., None], fv[..., None]
    a = field[u0, v0]
    b = field[u0 + 1, v0]
    c = field[u0, v0 + 1]
    d = field[u0 + 1, v0 + 1]
    top = a + (b - a) * fu
    bot = c + (d - c) * fu
    return top + (bot - top) * fv


def _chaikin(pts: list[tuple[float, float, int]], rounds: int) -> list[tuple[float, float, int]]:
    for _ in range(rounds):
        if len(pts) < 3:
            return pts
        out = [pts[0]]
        for (ax, ay, s), (bx, by, _) in zip(pts[:-1], pts[1:]):
            out.append((ax * 0.75 + bx * 0.25, ay * 0.75 + by * 0.25, s))
            out.append((ax * 0.25 + bx * 0.75, ay * 0.25 + by * 0.75, s))
        out.append(pts[-1])
        pts = out
    return pts


# ---------------------------------------------------------------------------- stamps
INK = (36, 28, 20, 255)


@lru_cache(maxsize=256)
def stamp(kind: str, ppc: int, variant: int) -> Image.Image:
    """A small drawing: a tree, a pine, a hill, a mountain... sized for ppc pixels per square."""
    sc = 4
    rng = np.random.default_rng(zlib.crc32(f"{kind}/{variant}".encode()))
    if kind == "tree":
        s = max(5, int(ppc * (0.55 + 0.1 * (variant % 2))))
        big = Image.new("RGBA", (s * sc, int(s * 1.25) * sc), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        W, H = big.size
        green = [(58, 86, 46), (66, 94, 50), (50, 78, 44), (74, 98, 54)][variant % 4]
        d.rectangle([W * 0.45, H * 0.6, W * 0.55, H * 0.98], fill=(70, 52, 34, 255))
        d.ellipse([W * 0.06, H * 0.05, W * 0.94, H * 0.78], fill=green + (255,), outline=INK, width=sc)
        d.ellipse([W * 0.22, H * 0.14, W * 0.6, H * 0.45], fill=tuple(min(255, int(c * 1.22)) for c in green) + (255,))
    elif kind == "pine":
        s = max(5, int(ppc * 0.48))
        big = Image.new("RGBA", (s * sc, int(s * 1.6) * sc), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        W, H = big.size
        green = [(40, 66, 50), (46, 72, 54), (36, 60, 46), (52, 76, 58)][variant % 4]
        d.rectangle([W * 0.44, H * 0.8, W * 0.56, H * 0.99], fill=(64, 46, 30, 255))
        d.polygon([(W * 0.5, H * 0.02), (W * 0.98, H * 0.84), (W * 0.02, H * 0.84)], fill=green + (255,), outline=INK)
        d.polygon([(W * 0.5, H * 0.02), (W * 0.5, H * 0.84), (W * 0.02, H * 0.84)],
                  fill=tuple(min(255, int(c * 1.2)) for c in green) + (255,))
    elif kind == "hill":
        s = max(6, int(ppc * 0.95))
        big = Image.new("RGBA", (s * sc, int(s * 0.55) * sc), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        W, H = big.size
        d.chord([0, 0, W - 1, H * 2], 180, 360, fill=(128, 120, 80, 255))
        d.chord([0, 0, W * 0.55, H * 2], 180, 360, fill=(146, 138, 92, 255))
        d.arc([0, 0, W - 1, H * 2], 190, 350, fill=INK, width=sc)
    elif kind in ("mountain", "peak"):
        s = max(8, int(ppc * (1.35 + 0.15 * (variant % 2))))
        big = Image.new("RGBA", (s * sc, int(s * 0.85) * sc), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        W, H = big.size
        top = W * (0.42 + 0.16 * rng.random())
        rock = (128, 120, 110) if kind == "mountain" else (150, 150, 156)
        dark = (88, 82, 76) if kind == "mountain" else (112, 114, 124)
        d.polygon([(0, H - 1), (top, H * 0.05), (W - 1, H - 1)], fill=dark + (255,))
        d.polygon([(0, H - 1), (top, H * 0.05), (top + W * 0.05, H - 1)], fill=rock + (255,))
        snow = 0.32 if kind == "mountain" else 0.55
        d.polygon([(top - W * snow * 0.32, H * snow), (top, H * 0.05), (top + W * snow * 0.32, H * snow),
                   (top + W * 0.06, H * snow * 0.8), (top - W * 0.05, H * snow * 1.05)], fill=(232, 234, 238, 255))
        d.line([(0, H - 1), (top, H * 0.05), (W - 1, H - 1)], fill=INK, width=sc + 1)
    elif kind == "reeds":
        s = max(4, int(ppc * 0.35))
        big = Image.new("RGBA", (s * sc, s * sc), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        W, H = big.size
        for k in range(4):
            x = W * (0.15 + 0.23 * k)
            d.line([(x, H), (x + (k - 1.5) * sc, H * 0.15)], fill=(70, 90, 52, 255), width=sc)
        d.line([(0, H - sc), (W, H - sc)], fill=(60, 84, 96, 255), width=sc)
    elif kind == "tuft":
        s = max(3, int(ppc * 0.25))
        big = Image.new("RGBA", (s * sc, s * sc), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        W, H = big.size
        for k in range(3):
            x = W * (0.2 + 0.3 * k)
            d.line([(x, H), (x + (k - 1) * sc * 1.5, H * 0.2)], fill=(84, 104, 56, 200), width=sc)
    elif kind == "scrub":
        s = max(3, int(ppc * 0.22))
        big = Image.new("RGBA", (s * sc, s * sc), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        W, H = big.size
        d.ellipse([0, H * 0.3, W, H], fill=(108, 112, 96, 220))
    elif kind == "dune":
        s = max(5, int(ppc * 0.7))
        big = Image.new("RGBA", (s * sc, int(s * 0.4) * sc), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        W, H = big.size
        d.arc([0, 0, W, H * 2], 200, 340, fill=(120, 98, 62, 200), width=sc)
    else:
        big = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    out = big.resize((max(1, big.width // sc), max(1, big.height // sc)), Image.LANCZOS)
    if kind in ("tree", "pine", "mountain", "peak"):
        sh = Image.new("RGBA", (out.width + 3, out.height + 2), (0, 0, 0, 0))
        a = np.asarray(out)[..., 3]
        shadow = np.zeros((sh.height, sh.width, 4), np.uint8)
        shadow[2:2 + a.shape[0], 3:3 + a.shape[1], 3] = (a * 0.35).astype(np.uint8)
        sh = Image.fromarray(shadow, "RGBA").filter(ImageFilter.GaussianBlur(1))
        sh.alpha_composite(out, (0, 0))
        out = sh
    return out


# ---------------------------------------------------------------------------- chunk cache
class ChunkCache:
    """Painted chunks by (ppc, cx, cy), painted in a background thread; the newest requests first."""

    def __init__(self, painter: WorldPainter, limit: int = 96) -> None:
        self.painter = painter
        self.limit = limit
        self.done: OrderedDict = OrderedDict()
        self.wanted: list = []
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop = False
        self.thread: threading.Thread | None = None
        self.version = 0

    def get(self, key):
        with self.lock:
            im = self.done.get(key)
            if im is not None:
                self.done.move_to_end(key)
            return im

    def want(self, keys: list) -> None:
        with self.lock:
            self.wanted = [k for k in keys if k not in self.done]
        if self.wanted:
            if self.thread is None:
                self.thread = threading.Thread(target=self._run, name="map painter", daemon=True)
                self.thread.start()
            self.wake.set()

    def paint_now(self, key) -> Image.Image:
        im = self._paint(key)
        with self.lock:
            self.done[key] = im
        return im

    def _paint(self, key) -> Image.Image:
        ppc, cx, cy = key
        n = self.painter.chunk_cells(ppc)
        x0, y0 = cx * n, cy * n
        nx, ny = min(n, self.painter.W - x0), min(n, self.painter.H - y0)
        return self.painter.paint(x0, y0, max(1, nx), max(1, ny), ppc)

    def _run(self) -> None:
        while not self.stop:
            self.wake.wait(0.5)
            self.wake.clear()
            while not self.stop:
                with self.lock:
                    if not self.wanted:
                        break
                    key = self.wanted.pop(0)
                    if key in self.done:
                        continue
                try:
                    im = self._paint(key)
                except Exception:
                    import logging

                    logging.getLogger("realmwalker.gfx").exception("Could not paint the map at %r", key)
                    continue
                with self.lock:
                    self.done[key] = im
                    self.version += 1
                    while len(self.done) > self.limit:
                        self.done.popitem(last=False)

    def close(self) -> None:
        self.stop = True
        self.wake.set()
