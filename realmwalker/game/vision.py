"""What can be seen on a local map: shared by the drawing code and by creatures deciding to hunt you."""

from __future__ import annotations

import numpy as np
import tcod.map

# In woods you see a short way in every direction rather than down long gaps between trunks.
WOODLAND_SIGHT = {"forest": 10, "pine_forest": 12, "marsh": 16}

_SIGHT_CACHE: dict[int, tuple[int, bool, np.ndarray]] = {}


def sight_blockers(game, lm, woodland: bool = False) -> np.ndarray:
    """Which cells let light through. Walls and closed doors block sight. A lone tree does not
    hide what lies behind it; thickets of three or more trees do, except in woodland, where
    sight is short instead (see WOODLAND_SIGHT)."""
    T = game.tables.terrain
    terrain = game.remap_for(lm)[lm.terrain]
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


def sight_radius(game, lm) -> tuple[int, bool]:
    """(radius, woodland) for the player's eyes right now. Radius 0 means unlimited."""
    p = game.player
    if lm.kind == "dungeon":
        from realmwalker.game.dungeon import light_radius

        dark_sight = game.sheet().darkvision // 5 if game.party else 0
        return max(1, light_radius(game), dark_sight), False
    woodland_radius = WOODLAND_SIGHT.get(game.biome_key(p.x, p.y)) if lm.kind != "settlement" else None
    light = game.light
    radius = 0 if light >= 0.9 else max(4, int(4 + light * 28))
    dark_sight = game.sheet().darkvision // 5 if game.party else 0
    if light < 0.9 and dark_sight:
        radius = max(radius, dark_sight)
    if woodland_radius:
        radius = min(radius, woodland_radius) if radius else woodland_radius
    visibility = game.weather.visibility if game.party else 1.0
    if visibility < 0.99 and lm.building_at(p.lx, p.ly) is None:
        weather_radius = max(3, int(40 * visibility))
        radius = min(radius, weather_radius) if radius else weather_radius
    return radius, woodland_radius is not None


def player_fov(game, lm, remember: bool = True) -> np.ndarray:
    radius, woodland = sight_radius(game, lm)
    see = sight_blockers(game, lm, woodland)
    fov = tcod.map.compute_fov(see, (game.player.lx, game.player.ly), radius=radius, light_walls=True)
    if remember:
        lm.seen |= fov
    return fov


def can_see(game, lm, frm: tuple[int, int], to: tuple[int, int], radius: int) -> bool:
    if max(abs(frm[0] - to[0]), abs(frm[1] - to[1])) > radius:
        return False
    _, woodland = sight_radius(game, lm)
    see = sight_blockers(game, lm, woodland)
    fov = tcod.map.compute_fov(see, frm, radius=radius, light_walls=True)
    return bool(fov[to])
