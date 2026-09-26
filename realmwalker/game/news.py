"""What the player hears (M6): news that has reached where they are, most important and freshest first.
The news itself, and how it travels, is in world/news.py.
"""

from __future__ import annotations

from realmwalker.world.news import (  # noqa: F401  (the news API, used from game code through here)
    KEEP_DAYS, MAX_NEWS, REACH, ROAD_BEND, SPEED, add, age_text, arrived, distance, faction_place, known_at, now_days,
    prune, reaches, travel_days,
)


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
        if n.get("kind") == "unique":  # talk of where one of the seven is to be found: it goes on your map
            fresh_places = [sid for sid in n.get("places", []) if sid not in game.player.known_settlements]
            game.player.known_settlements.update(fresh_places)
            if fresh_places:
                out[-1] += " (It is on your map now.)"
        for fid in n.get("factions", []):
            from realmwalker.game.reputation import know

            f = w.factions.get(fid)
            if f is not None and not f.secret:
                know(game, fid)
    return out


def heard_items(game) -> list[dict]:
    heard = game.renown.heard
    return sorted((n for n in game.world.news if n["id"] in heard), key=lambda n: -n["day"])
