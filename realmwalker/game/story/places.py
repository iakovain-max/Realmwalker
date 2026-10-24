"""Places in a story: a site, a settlement or a tile of the world map, maybe with a part ("deepest", a level, the
outskirts, the inn). Records are JSON-native: {"site": 12} / {"settlement": 4, "part": "inn"} / {"tile": [x, y]}."""

from __future__ import annotations

import math


def xy(world, place: dict) -> tuple[int, int]:
    if "site" in place:
        s = world.sites[place["site"]]
        return s.x, s.y
    if "settlement" in place:
        s = world.settlements[place["settlement"]]
        return s.x, s.y
    x, y = place["tile"]
    return int(x), int(y)


def name(world, place: dict) -> str:
    if "site" in place:
        return world.sites[place["site"]].name
    if "settlement" in place:
        return world.settlements[place["settlement"]].name
    x, y = xy(world, place)
    s = world.settlement_at(x, y)
    if s is not None:
        return s.name
    if world.road[x, y] and world.settlements:  # (a kill on the road: "the road near Skartun")
        near = min(world.settlements, key=lambda t: math.hypot(t.x - x, t.y - y))
        if math.hypot(near.x - x, near.y - y) <= 12:
            return f"the road near {near.name}"
    area = world.area_at(x, y)
    if area is None:
        return "the open country"
    return area.name if area.name.lower().startswith("the ") else f"the country of {area.name}"


def dist(world, a: dict, b: dict) -> float:
    ax, ay = xy(world, a)
    bx, by = xy(world, b)
    return math.hypot(ax - bx, ay - by)


def exists(world, place: dict) -> bool:
    if "site" in place:
        return 0 <= int(place["site"]) < len(world.sites)
    if "settlement" in place:
        return 0 <= int(place["settlement"]) < len(world.settlements)
    if "tile" in place:
        x, y = place["tile"]
        return world.in_bounds(int(x), int(y))
    return False


def here(game, place: dict) -> bool:
    """The party stands on the place's tile of the world map."""
    p = game.player
    return (p.x, p.y) == xy(game.world, place)


def dungeon_level(world, place: dict) -> int | None:
    """The level a place's part names in its site's dungeon: "deepest", or "level" n."""
    if "site" not in place:
        return None
    if place.get("part") == "deepest":
        from realmwalker.world import dungeon as gen

        return gen.depth_for(world, world.sites[place["site"]])
    if place.get("part") == "level":
        return int(place.get("level", 1))
    return None


def dungeon_key(world, place: dict) -> str | None:
    level = dungeon_level(world, place)
    if level is None:
        return None
    x, y = xy(world, place)
    return f"{x},{y}/{level}"
