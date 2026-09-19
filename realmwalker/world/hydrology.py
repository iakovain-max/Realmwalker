"""Water: every land tile drains downhill to the sea; rivers form where enough rain gathers,
and lakes fill the hollows.

Uses the "priority flood" method: flood inwards from the coast, always extending from the lowest
known tile. Each tile's water flows to the tile it was reached from, so no river ever gets stuck.
"""

from __future__ import annotations

import heapq

import numpy as np

from realmwalker.world.model import DIRS


def opposite(d: int) -> int:
    return ((d - 1 + 4) % 8) + 1


def priority_flood(elev: np.ndarray, ocean: np.ndarray, epsilon: float = 1e-5):
    """Returns (filled elevation, flow direction per tile, processing order from low to high)."""
    w, h = elev.shape
    filled = elev.astype(np.float64).copy()
    visited = ocean.copy()
    flow = np.zeros((w, h), dtype=np.uint8)
    heap: list[tuple[float, int, int, int]] = []
    counter = 0
    ocean_l = ocean.tolist()
    elev_l = elev.tolist()
    for x in range(w):
        for y in range(h):
            if ocean_l[x][y]:
                continue
            seed_dir = -1
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                seed_dir = 0  # drains off the edge of the map
            for d in range(1, 9):
                dx, dy = DIRS[d]
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and ocean_l[nx][ny]:
                    seed_dir = d
                    break
            if seed_dir >= 0:
                visited[x, y] = True
                flow[x, y] = seed_dir
                heapq.heappush(heap, (elev_l[x][y], counter, x, y))
                counter += 1
    visited_l = visited.tolist()
    filled_l = filled.tolist()
    flow_l = flow.tolist()
    order: list[tuple[int, int]] = []
    while heap:
        e, _, x, y = heapq.heappop(heap)
        order.append((x, y))
        for d in range(1, 9):
            dx, dy = DIRS[d]
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not visited_l[nx][ny]:
                visited_l[nx][ny] = True
                ne = max(elev_l[nx][ny], e + epsilon)
                filled_l[nx][ny] = ne
                flow_l[nx][ny] = opposite(d)
                heapq.heappush(heap, (ne, counter, nx, ny))
                counter += 1
    return np.array(filled_l), np.array(flow_l, dtype=np.uint8), order


def flow_accumulation(rain: np.ndarray, flow: np.ndarray, order: list[tuple[int, int]], ocean: np.ndarray) -> np.ndarray:
    """How much water passes through each tile: its own rain plus everything upstream."""
    w, h = rain.shape
    acc = rain.astype(np.float64).tolist()
    flow_l = flow.tolist()
    ocean_l = ocean.tolist()
    for x, y in reversed(order):
        d = flow_l[x][y]
        if d == 0:
            continue
        dx, dy = DIRS[d]
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h and not ocean_l[nx][ny]:
            acc[nx][ny] += acc[x][y]
    return np.array(acc)


def label_components(mask: np.ndarray, diagonal: bool = False) -> tuple[np.ndarray, list[int]]:
    """Connected regions of True cells. Returns (labels with -1 for False, sizes per label)."""
    w, h = mask.shape
    labels = np.full((w, h), -1, dtype=np.int32)
    sizes: list[int] = []
    mask_l = mask.tolist()
    labels_l = labels.tolist()
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diagonal:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    for sx in range(w):
        for sy in range(h):
            if not mask_l[sx][sy] or labels_l[sx][sy] >= 0:
                continue
            label = len(sizes)
            stack = [(sx, sy)]
            labels_l[sx][sy] = label
            count = 0
            while stack:
                x, y = stack.pop()
                count += 1
                for dx, dy in steps:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and mask_l[nx][ny] and labels_l[nx][ny] < 0:
                        labels_l[nx][ny] = label
                        stack.append((nx, ny))
            sizes.append(count)
    return np.array(labels_l, dtype=np.int32), sizes


def dilate(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    out = mask.copy()
    for _ in range(radius):
        grown = out.copy()
        grown[1:, :] |= out[:-1, :]
        grown[:-1, :] |= out[1:, :]
        grown[:, 1:] |= out[:, :-1]
        grown[:, :-1] |= out[:, 1:]
        grown[1:, 1:] |= out[:-1, :-1]
        grown[:-1, :-1] |= out[1:, 1:]
        grown[1:, :-1] |= out[:-1, 1:]
        grown[:-1, 1:] |= out[1:, :-1]
        out = grown
    return out
