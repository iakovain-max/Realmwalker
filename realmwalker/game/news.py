"""News and rumours (M6). Every significant event becomes news that travels outward from where it happened at
the pace of carters, pedlars and messengers: about 24 miles (8 tiles) a day, a little slower than a straight line
because roads bend. Small news dies out close to home; great news crosses the world. People only know what
has reached them, so the same death can be old news in one town and unheard of in the next.

News items are plain dicts kept in world.news (they outlive characters). The player's own deeds also become
news; what they do to the player's standing travels separately, with the character (game.reputation).
"""

from __future__ import annotations

import math

SPEED = 8.0  # tiles a day
ROAD_BEND = 1.15
REACH = {1: 14, 2: 32, 3: 64, 4: 140, 5: 10**6}  # importance -> how far it travels, in tiles
KEEP_DAYS = {1: 30, 2: 60, 3: 150, 4: 300, 5: 600}
MAX_NEWS = 400


def now_days(world) -> float:
    return world.time / 1440.0


def add(world, text: str, x: int, y: int, *, kind: str = "event", importance: int = 2, factions=(), places=(),
        day: float | None = None, player: bool = False) -> dict:
    item = {
        "id": int(world.politics.get("next_news", 0)), "day": now_days(world) if day is None else float(day),
        "x": int(x), "y": int(y), "text": text, "kind": kind, "importance": int(max(1, min(5, importance))),
        "factions": [int(f) for f in factions], "places": [int(p) for p in places], "player": bool(player),
    }
    world.politics["next_news"] = item["id"] + 1
    world.news.append(item)
    if len(world.news) > MAX_NEWS:
        prune(world, force=True)
    return item


def distance(item: dict, x: int, y: int) -> float:
    return math.hypot(item["x"] - x, item["y"] - y) * ROAD_BEND


def travel_days(x0: float, y0: float, x1: float, y1: float) -> float:
    return math.hypot(x0 - x1, y0 - y1) * ROAD_BEND / SPEED


def reaches(item: dict, x: int, y: int) -> bool:
    return distance(item, x, y) <= REACH.get(item["importance"], 30)


def arrived(item: dict, x: int, y: int, today: float) -> bool:
    d = distance(item, x, y)
    return d <= REACH.get(item["importance"], 30) and today >= item["day"] + d / SPEED


def known_at(world, x: int, y: int) -> list[dict]:
    """News that has reached a place, newest first."""
    today = now_days(world)
    out = [n for n in world.news if arrived(n, x, y, today)]
    out.sort(key=lambda n: -n["day"])
    return out


def age_text(days: float) -> str:
    days = max(0.0, days)
    if days < 1:
        return "today"
    if days < 2:
        return "yesterday"
    if days < 7:
        return f"{int(days)} days ago"
    if days < 14:
        return "a week ago"
    if days < 60:
        return f"{int(days // 7)} weeks ago"
    return f"{int(days // 30)} months ago"


def hear(game, *, count: int = 1, rng=None, x: int | None = None, y: int | None = None,
         exclude_player: bool = False) -> list[str]:
    """The player hears news that has reached here and that they have not heard: the most important and
    freshest first. Returns the lines heard (marked up)."""
    from realmwalker.core.textgen import escape_markup

    w = game.world
    p = game.player
    x = p.x if x is None else x
    y = p.y if y is None else y
    today = now_days(w)
    heard = game.renown.heard
    fresh = [n for n in known_at(w, x, y) if n["id"] not in heard and not (exclude_player and n.get("player"))]
    fresh.sort(key=lambda n: (-n["importance"], -n["day"]))
    out = []
    for n in fresh[:count]:
        heard.add(n["id"])
        when = age_text(today - n["day"])
        out.append(f"<info>{escape_markup(n['text'][:1].upper() + n['text'][1:])}</> <dim>({when})</>")
        for fid in n.get("factions", []):
            from realmwalker.game.reputation import know

            f = w.factions.get(fid)
            if f is not None and not f.secret:
                know(game, fid)
    return out


def heard_items(game) -> list[dict]:
    heard = game.renown.heard
    return sorted((n for n in game.world.news if n["id"] in heard), key=lambda n: -n["day"])


def prune(world, force: bool = False) -> None:
    today = now_days(world)
    keep = [n for n in world.news if today - n["day"] <= KEEP_DAYS.get(n["importance"], 60)]
    if force and len(keep) > MAX_NEWS:
        keep.sort(key=lambda n: (n["importance"], n["day"]))
        keep = keep[len(keep) - MAX_NEWS:]
        keep.sort(key=lambda n: n["day"])
    world.news = keep


def faction_place(world, faction) -> tuple[int, int] | None:
    """Where a faction hears things: its seat, its lair, its country, or its home coast."""
    if faction.seat >= 0:
        s = world.settlements[faction.seat]
        return s.x, s.y
    if faction.site >= 0:
        s = world.sites[faction.site]
        return s.x, s.y
    if faction.area >= 0:
        a = world.areas[faction.area]
        return a.x, a.y
    coast = faction.flags.get("coast")
    if coast:
        return int(coast[0]), int(coast[1])
    return None
