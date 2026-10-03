"""The overworld drawn as a map on parchment, in sharp pixels: each country's colour printed flat on the paper, hills
shaded from the north-west in dithered steps, an ink line along every coast with ripple lines out to sea, rivers in
blue, roads dashed, and little pixel-drawn trees, hills and mountains with ink outlines.

The map is painted in "map pixels" (about a dozen to a square of country) and enlarged by a whole number, so every
pixel stays a sharp square at any zoom. Pure Pillow and numpy, no window: a WorldPainter paints any square piece of
the world ("a chunk") at any number of screen pixels per square, and the whole world for the world map. Chunks are
painted in a background thread by ChunkCache so walking never waits for them; each is painted with a margin and
cut, and everything that could differ across a seam is worked out from absolute positions, so pieces meet.
"""

from __future__ import annotations

import threading
import zlib
from collections import OrderedDict
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

from realmwalker.world.model import DIRS

MARKS = {"grass": 1, "broadleaf": 2, "pine": 3, "hills": 4, "mountains": 5, "peaks": 6, "marsh": 7, "tundra": 8, "dunes": 9}
CHUNK_PX = 768  # a chunk is about this many pixels across, whatever the scale
MARGIN = 2  # squares painted around a chunk and cut away, so coasts and stamps meet across the seams
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) + 0.5) / 16.0


def pixel_scale(ppc: int) -> int:
    """Screen pixels to one map pixel: the whole divisor of ppc nearest ppc / 12 (so a square is about 12 map
    pixels across, and the map is enlarged without any pixel drawn wider than its neighbour)."""
    divisors = [d for d in range(1, ppc + 1) if ppc % d == 0]
    return min(divisors, key=lambda d: (abs(d - ppc / 12.0), d))


def _paperise(rgb: np.ndarray, paper: np.ndarray, amount: float) -> np.ndarray:
    """A colour as if printed on the paper: a little greyer, a little of the paper showing through."""
    grey = rgb.mean(axis=-1, keepdims=True)
    rgb = rgb * 0.8 + grey * 0.2
    return rgb * (1 - amount) + paper * amount * (rgb.mean(axis=-1, keepdims=True) / paper.mean())


class WorldPainter:
    def __init__(self, world, tables) -> None:
        sp = tables.sprites["world"]
        self.world = world
        self.seed = int(world.meta.seed)
        W, H = world.width, world.height
        biomes = sp["biomes"]
        keys = list(world.biome_ids)
        default = biomes.get("plains", {"color": [100, 110, 70]})
        self.paper = np.array(sp.get("paper", [222, 204, 162]), np.float32)
        self.ink = np.array(sp["ink"], np.float32)
        pal = np.array([biomes.get(k, default)["color"] for k in keys], np.float32)
        self.pal = np.clip(_paperise(pal, self.paper, 0.42) * 1.12, 0, 255).astype(np.float32)
        self.sea = _paperise(np.array(sp.get("sea", [52, 86, 108]), np.float32), self.paper, 0.3)
        marks = np.array([MARKS.get(biomes.get(k, {}).get("marks", ""), 0) for k in keys], np.int64)
        dens = np.array([biomes.get(k, {}).get("density", 0.0) for k in keys], np.float32)
        water_b = np.array([k in ("ocean", "lake") for k in keys], bool)
        b = world.biome.astype(np.int64)
        self.biome = b
        elev = world.elevation.astype(np.float32)
        self.water = water_b[b]
        self.elev = np.where(self.water, 0, np.maximum(elev, 0)).astype(np.float32)
        # Shading worked out per square from a smoothed height: light from the north-west.
        e = _blur(_blur(self.elev, 1), 1)
        gx = np.zeros_like(e)
        gy = np.zeros_like(e)
        gx[1:-1, :] = (e[2:, :] - e[:-2, :]) * 0.5
        gy[:, 1:-1] = (e[:, 2:] - e[:, :-2]) * 0.5
        self.shade = np.clip(1.0 - (gx + gy) / 260.0, 0.6, 1.32).astype(np.float32)
        self.marks = marks[b]
        self.density = dens[b]
        self.road_rgb = tuple(int(c) for c in sp["road"])
        self.river_rgb = tuple(int(c) for c in sp["river"])
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
        """Squares [x0, x0+nx) x [y0, y0+ny) at ppc screen pixels per square, as an RGBA image."""
        s = pixel_scale(ppc)
        k = ppc // s  # map pixels to a square
        m = MARGIN
        X0, Y0, NX, NY = x0 - m, y0 - m, nx + 2 * m, ny + 2 * m
        Wl, Hl = NX * k, NY * k
        ax = np.arange(Wl) + X0 * k  # absolute map-pixel columns and rows: the same on both sides of a seam
        ay = np.arange(Hl) + Y0 * k
        u = (ax + 0.5) / k - 0.5
        v = (ay + 0.5) / k - 0.5
        # The borders between countries wander (a warp of noise), so the squares do not show.
        gseed = self.seed & 0xFFFF
        cell = max(3.0, k * 1.1)
        wx = _world_noise(Wl, Hl, cell, gseed + 1, X0 * k, Y0 * k) * 0.45
        wy = _world_noise(Wl, Hl, cell, gseed + 2, X0 * k, Y0 * k) * 0.45
        wx += _world_noise(Wl, Hl, cell * 3.3, gseed + 3, X0 * k, Y0 * k) * 0.4
        wy += _world_noise(Wl, Hl, cell * 3.3, gseed + 4, X0 * k, Y0 * k) * 0.4
        U = u[:, None] + wx
        V = v[None, :] + wy
        bi = self.biome[np.clip(np.rint(U).astype(np.int64), 0, self.W - 1),
                        np.clip(np.rint(V).astype(np.int64), 0, self.H - 1)]
        col = self.pal[bi].copy()
        land = _bilinear(self.water.astype(np.float32), U, V) < 0.5
        # Hills shaded from the north-west in three dithered tones.
        shade = _bilinear(self.shade, u[:, None] + wx * 0.3, v[None, :] + wy * 0.3)
        t = np.clip((shade - 1.0) / 0.22, -1, 1)
        thr = BAYER[(ax % 4)[:, None], (ay % 4)[None, :]]
        darker = land & (-t > thr)
        lighter = land & (t > thr)
        col[darker] *= 0.80
        col[lighter] = col[lighter] * 0.82 + self.paper * 0.207
        # The sea: paler near the shore, ripple lines following the coast, deep water a dithered shade darker.
        far = 7
        dist = np.full((Wl, Hl), far + 1, np.int16)
        grown = land.copy()
        for d in range(1, far + 1):
            nb = grown.copy()
            nb[1:] |= grown[:-1]
            nb[:-1] |= grown[1:]
            nb[:, 1:] |= grown[:, :-1]
            nb[:, :-1] |= grown[:, 1:]
            dist[nb & ~grown] = d
            grown = nb
        sea = ~land
        col[sea] = self.sea
        col[sea & (dist <= 3)] = self.sea * 0.75 + self.paper * 0.2125
        col[sea & ((dist == 2) | (dist == 5))] = self.sea * 0.45 + self.paper * 0.495
        col[sea & (dist > far) & (thr < 0.5)] *= 0.9
        # An ink line along every coast.
        near_sea = np.zeros_like(sea)
        near_sea[1:] |= sea[:-1]
        near_sea[:-1] |= sea[1:]
        near_sea[:, 1:] |= sea[:, :-1]
        near_sea[:, :-1] |= sea[:, 1:]
        col[land & near_sea] = self.ink
        # A faint grain in the paper, in whole map pixels.
        grain = np.random.default_rng(zlib.crc32(f"{self.seed}/{X0}/{Y0}/{k}".encode())).normal(1.0, 0.015, (Wl, Hl))
        col *= grain.astype(np.float32)[..., None]
        rgba = np.empty((Hl, Wl, 4), np.uint8)
        rgba[..., :3] = np.clip(col, 0, 255).astype(np.uint8).transpose(1, 0, 2)
        rgba[..., 3] = 255
        rgba = self._draw_rivers(rgba, X0, Y0, NX, NY, k)
        self._draw_roads(rgba, X0, Y0, NX, NY, k)
        if detail:
            self._stamp(rgba, X0, Y0, NX, NY, k)
        im = Image.fromarray(np.ascontiguousarray(rgba[m * k:(m + ny) * k, m * k:(m + nx) * k]), "RGBA")
        if s > 1:
            im = im.resize((im.width * s, im.height * s), Image.NEAREST)
        return im

    def _draw_rivers(self, rgba: np.ndarray, X0, Y0, NX, NY, k) -> np.ndarray:
        im = Image.fromarray(rgba, "RGBA")
        draw = ImageDraw.Draw(im)
        colour = self.river_rgb + (255,)
        for chain in self.rivers:
            pts = [((x - X0) * k, (y - Y0) * k, sz) for x, y, sz in chain]
            if all(px < -k or px > (NX + 1) * k or py < -k or py > (NY + 1) * k for px, py, _ in pts):
                continue
            for (ax, ay, sz), (bx, by, _) in zip(pts[:-1], pts[1:]):
                w = 1 if (sz <= 1 or k < 8) else (2 if sz == 2 or k < 12 else 3)
                draw.line([(ax, ay), (bx, by)], fill=colour, width=w)
        return np.array(im)

    def _draw_roads(self, rgba: np.ndarray, X0, Y0, NX, NY, k) -> None:
        """Roads as dashes of ink-brown; which pixels are dashes depends on where they are in the world, so a road
        is dashed the same way on both sides of a seam."""
        H, W = rgba.shape[:2]
        road = self.road_rgb
        for ax, ay, bx, by in self.roads:
            if not (X0 - 2 <= ax <= X0 + NX + 2 and Y0 - 2 <= ay <= Y0 + NY + 2):
                continue
            px0, py0, px1, py1 = (ax - X0) * k, (ay - Y0) * k, (bx - X0) * k, (by - Y0) * k
            n = int(max(abs(px1 - px0), abs(py1 - py0))) + 1
            xs = np.rint(np.linspace(px0, px1, n)).astype(np.int64)
            ys = np.rint(np.linspace(py0, py1, n)).astype(np.int64)
            ok = (xs >= 0) & (xs < W) & (ys >= 0) & (ys < H)
            if k >= 6:
                ok &= ((xs + X0 * k + ys + Y0 * k) % 5) < 3
            rgba[ys[ok], xs[ok], :3] = road
            if k >= 12:  # a broader road: two pixels
                ok2 = ok & (ys + 1 < H)
                rgba[ys[ok2] + 1, xs[ok2], :3] = road

    def _stamp(self, rgba: np.ndarray, X0, Y0, NX, NY, k) -> None:
        """Trees, hills and mountains, back to front."""
        xa, ya = max(0, X0), max(0, Y0)
        xb, yb = min(self.W, X0 + NX), min(self.H, Y0 + NY)
        if xb <= xa or yb <= ya:
            return
        marks = self.marks[xa:xb, ya:yb]
        if not marks.any():
            return
        dens = self.density[xa:xb, ya:yb]
        jit = self.jitter[xa:xb, ya:yb]
        road = self.world.road[xa:xb, ya:yb]
        river = self.world.river[xa:xb, ya:yb] > 0
        settled = (self.world.settlement_grid[xa:xb, ya:yb] >= 0) | (self.world.site_grid[xa:xb, ya:yb] >= 0)
        items: list[tuple[float, np.ndarray, int, int]] = []

        def put(kind: str, variant: int, tx: float, ty: float) -> None:
            st = sprite(kind, k, variant)
            items.append((ty, st, int(tx - st.shape[1] / 2), int(ty - st.shape[0])))

        for (i, j) in np.argwhere(marks > 0):
            if settled[i, j]:
                continue
            kind = int(marks[i, j])
            r = jit[i, j]
            if r[0] > dens[i, j]:
                continue
            px, py = (xa + int(i) - X0) * k, (ya + int(j) - Y0) * k
            busy = road[i, j] or river[i, j]
            if kind in (2, 3):
                n = 3 if k >= 10 else (2 if k >= 6 else 1)
                for q in range(n):
                    if busy and q > 0:
                        break
                    put("tree" if kind == 2 else "pine", int(r[7] * 4 + q) % 4,
                        px + k * (0.15 + 0.7 * r[1 + q]), py + k * (0.3 + 0.65 * r[4 + (q % 4)]))
            elif kind == 4 and not busy:
                for q in range(2 if r[5] > 0.7 else 1):
                    put("hill", int(r[1 + q] * 6), px + k * (0.15 + 0.7 * r[2 + q]), py + k * (0.35 + 0.6 * r[4 + q]))
            elif kind in (5, 6):
                if r[6] < 0.12:
                    continue  # a gap now and then: a range is not a wall
                put("peak" if kind == 6 else "mountain", int(r[1] * 8), px + k * (0.2 + 0.6 * r[2]),
                    py + k * (0.65 + 0.4 * r[3]))
            elif kind == 7 and k >= 6:
                for q in range(2):
                    put("reeds", int(r[1 + q] * 3), px + k * (0.2 + 0.6 * r[2 + q]), py + k * (0.3 + 0.6 * r[4 + q]))
            elif kind == 1 and k >= 10 and r[5] < 0.5:
                put("tuft", int(r[1] * 3), px + k * r[2], py + k * (0.3 + 0.6 * r[3]))
            elif kind == 8 and k >= 10 and r[5] < 0.4:
                put("scrub", int(r[1] * 3), px + k * r[2], py + k * (0.3 + 0.6 * r[3]))
            elif kind == 9 and k >= 8:
                put("dune", int(r[1] * 3), px + k * (0.5 + 0.3 * (r[2] - 0.5)), py + k * (0.5 + 0.4 * r[3]))
        items.sort(key=lambda t: t[0])
        H, W = rgba.shape[:2]
        for _, st, x, y in items:
            h, w = st.shape[:2]
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(W, x + w), min(H, y + h)
            if x1 <= x0 or y1 <= y0:
                continue
            sub = st[y0 - y:y1 - y, x0 - x:x1 - x]
            m = sub[..., 3] > 0
            rgba[y0:y1, x0:x1][m] = sub[m]

    def overview(self, ppc: int) -> Image.Image:
        """The whole world at a small scale (the world map, and a stand-in while chunks are painted)."""
        return self.paint(0, 0, self.W, self.H, ppc, detail=ppc >= 4)


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


# ---------------------------------------------------------------------------- the little drawings
INK = (52, 38, 26, 255)


def _outline(mask: np.ndarray) -> np.ndarray:
    o = np.zeros_like(mask)
    o[1:] |= mask[:-1]
    o[:-1] |= mask[1:]
    o[:, 1:] |= mask[:, :-1]
    o[:, :-1] |= mask[:, 1:]
    return o & ~mask


@lru_cache(maxsize=512)
def sprite(kind: str, k: int, variant: int) -> np.ndarray:
    """A little pixel drawing, (h, w, 4), sized for k map pixels to a square, with an ink outline."""
    rng = np.random.default_rng(zlib.crc32(f"{kind}/{k}/{variant}".encode()))
    if kind in ("mountain", "peak"):
        w = max(5, int(round(k * (1.1 + 0.12 * (variant % 5))))) | 1
        h = max(4, int(round(w * (0.72 + 0.12 * rng.random()))))
        apex = int(round(w * (0.38 + 0.24 * rng.random())))
        H, W = h + 1, w + 2
        mask = np.zeros((H, W), bool)
        face = np.zeros((H, W), np.int8)  # 1 lit, 2 in shadow
        for y in range(h):
            f = (y + 1) / h
            left = int(round(apex - apex * f))
            right = int(round(apex + (w - 1 - apex) * f))
            mask[y + 1, 1 + left:2 + right] = True
            face[y + 1, 1 + left:2 + apex] = 1
            face[y + 1, 2 + apex:2 + right] = 2
        lit, dark = ((150, 138, 120), (96, 86, 74)) if kind == "mountain" else ((168, 166, 168), (116, 116, 124))
        out = np.zeros((H, W, 4), np.uint8)
        out[face == 1] = (*lit, 255)
        out[face == 2] = (*dark, 255)
        snow = int(round(h * (0.30 if kind == "mountain" else 0.55)))
        for y in range(1, snow + 1):
            if y > snow - 1 - int(rng.integers(0, 2)):
                continue
            out[y][mask[y] & (face[y] == 1)] = (240, 240, 236, 255)
            out[y][mask[y] & (face[y] == 2)] = (196, 200, 210, 255)
        if k >= 8:  # a ridge down the shaded side
            for y in range(h // 2, h):
                xx = 2 + apex + int((y - h // 2) * 0.6)
                if 0 <= xx < W and mask[y + 1, xx]:
                    out[y + 1, xx] = (*(int(c * 0.75) for c in dark), 255)
        o = _outline(mask)
        o[-1] = False  # no line along the foot
        out[o] = INK
        return out
    if kind == "hill":
        w = max(4, int(round(k * (0.6 + 0.12 * (variant % 4)))))
        h = max(2, int(round(w * (0.34 + 0.06 * (variant % 3)))))
        H, W = h + 1, w + 2
        mask = np.zeros((H, W), bool)
        for x in range(w):
            t = (x + 0.5) / w * 2 - 1
            mask[1 + int(round(h * (1 - (1 - t * t) ** 0.5))):H, 1 + x] = True
        out = np.zeros((H, W, 4), np.uint8)
        out[mask] = (150, 140, 96, 255)
        lit = mask.copy()
        lit[:, 1 + w // 2:] = False
        out[lit] = (172, 160, 112, 255)
        o = _outline(mask)
        o[-1] = False
        o[:, 0] = False
        o[:, -1] = False
        out[o] = INK
        return out
    if kind == "tree":
        r = max(1, int(round(k * 0.2)))
        d = 2 * r + 1
        H, W = d + max(1, r // 2) + 2, d + 2
        mask = np.zeros((H, W), bool)
        yy, xx = np.mgrid[0:d, 0:d]
        mask[1:1 + d, 1:1 + d] = (xx - r) ** 2 + (yy - r) ** 2 <= r * r + r * 0.6
        trunk = np.zeros((H, W), bool)
        trunk[1 + d:H - 1, 1 + r] = True
        g = np.array([(70, 100, 54), (78, 106, 56), (62, 92, 50), (84, 110, 60)][variant % 4])
        out = np.zeros((H, W, 4), np.uint8)
        out[mask] = (*g, 255)
        ys, xs = np.mgrid[0:H, 0:W]
        out[mask & (ys <= 1 + r * 0.7) & (xs <= 1 + r * 0.9)] = (*np.minimum(255, g * 1.25).astype(int), 255)
        out[trunk] = (86, 62, 40, 255)
        out[_outline(mask | trunk)] = INK
        return out
    if kind == "pine":
        w = max(3, int(round(k * 0.36))) | 1
        h = max(4, int(round(k * 0.62)))
        H, W = h + 3, w + 2
        mask = np.zeros((H, W), bool)
        c = w // 2
        for y in range(h):
            half = int(round(c * (y + 1) / h))
            mask[1 + y, 1 + c - half:2 + c + half] = True
        trunk = np.zeros((H, W), bool)
        trunk[1 + h:H - 1, 1 + c] = True
        g = np.array([(50, 80, 62), (56, 86, 64), (46, 74, 58), (60, 90, 68)][variant % 4])
        out = np.zeros((H, W, 4), np.uint8)
        out[mask] = (*g, 255)
        lit = mask.copy()
        lit[:, 2 + c:] = False
        out[lit] = (*np.minimum(255, g * 1.22).astype(int), 255)
        out[trunk] = (80, 58, 38, 255)
        out[_outline(mask | trunk)] = INK
        return out
    if kind == "reeds":
        h = max(2, k // 4)
        out = np.zeros((h + 1, 5, 4), np.uint8)
        for x in (0, 2, 4):
            out[(x // 2) % 2:h + 1, x] = (70, 92, 56, 255)
        return out
    if kind == "tuft":
        out = np.zeros((2, 3, 4), np.uint8)
        out[0, 0] = out[0, 2] = out[1, 1] = (86, 104, 58, 255)
        return out
    if kind == "scrub":
        out = np.zeros((2, 3, 4), np.uint8)
        out[0, 1] = out[1, 0] = out[1, 2] = (110, 112, 92, 255)
        out[1, 1] = (92, 96, 80, 255)
        return out
    if kind == "dune":
        w = max(4, int(k * 0.7))
        out = np.zeros((2, w, 4), np.uint8)
        out[0, 1:w - 1] = (130, 104, 66, 255)
        out[1, 0] = out[1, w - 1] = (130, 104, 66, 255)
        return out
    return np.zeros((1, 1, 4), np.uint8)


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
