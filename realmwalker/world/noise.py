"""Smooth random noise for terrain, built from interpolated random grids (fractal value noise).

All arrays are indexed [x, y] (shape (width, height)) to match the console layout.
"""

from __future__ import annotations

import numpy as np


def _smooth(t: np.ndarray) -> np.ndarray:
    return t * t * (3.0 - 2.0 * t)


def value_noise(rng: np.random.Generator, width: int, height: int, cell: float, cell_y: float | None = None) -> np.ndarray:
    """One octave: random values on a grid every `cell` tiles, smoothly interpolated. Range 0..1.
    `cell_y` allows a different vertical scale (local-map cells are twice as tall as they are wide)."""
    cell = max(1.0, cell)
    cell_y = max(1.0, cell_y if cell_y is not None else cell)
    gw = int(np.ceil(width / cell)) + 2
    gh = int(np.ceil(height / cell_y)) + 2
    grid = rng.random((gw, gh))
    xs = np.arange(width) / cell
    ys = np.arange(height) / cell_y
    x0 = np.floor(xs).astype(int)
    y0 = np.floor(ys).astype(int)
    tx = _smooth(xs - x0)[:, None]
    ty = _smooth(ys - y0)[None, :]
    g00 = grid[x0[:, None], y0[None, :]]
    g10 = grid[x0[:, None] + 1, y0[None, :]]
    g01 = grid[x0[:, None], y0[None, :] + 1]
    g11 = grid[x0[:, None] + 1, y0[None, :] + 1]
    top = g00 + (g10 - g00) * tx
    bottom = g01 + (g11 - g01) * tx
    return top + (bottom - top) * ty


def fbm(rng: np.random.Generator, width: int, height: int, *, cell: float, octaves: int = 5,
        persistence: float = 0.5, aspect: float = 1.0) -> np.ndarray:
    """Fractal noise: several octaves of value noise, normalised to 0..1.
    aspect < 1 squashes features vertically (use 0.5 for local maps with tall cells)."""
    total = np.zeros((width, height))
    amplitude = 1.0
    norm = 0.0
    for _ in range(octaves):
        total += value_noise(rng, width, height, cell, cell * aspect) * amplitude
        norm += amplitude
        amplitude *= persistence
        cell /= 2.0
        if cell < 1.0:
            break
    return normalise(total / norm)


def ridged(rng: np.random.Generator, width: int, height: int, *, cell: float, octaves: int = 4) -> np.ndarray:
    """Ridged noise (sharp crests) for mountain ranges. 0..1."""
    n = fbm(rng, width, height, cell=cell, octaves=octaves)
    return normalise(1.0 - np.abs(n * 2.0 - 1.0)) ** 2


def normalise(a: np.ndarray) -> np.ndarray:
    lo, hi = float(a.min()), float(a.max())
    if hi - lo < 1e-12:
        return np.zeros_like(a)
    return (a - lo) / (hi - lo)
