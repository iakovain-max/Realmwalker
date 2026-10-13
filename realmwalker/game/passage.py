"""Paid passage (PHB 2024 p. 234, Expansion 2 part D): a coach along the roads to another town, a ship's passage
over the sea between harbours, and a messenger sent to fetch a companion who waits somewhere else. Prices and speeds
are data/economy.json "services" (coach, ship, messenger). Logic only: the services screen offers them."""

from __future__ import annotations

import math

import numpy as np
import tcod

COACH_KINDS = ("town", "city", "hold", "elfhall")  # places with a coaching inn
HARBOUR_KINDS = ("village", "town", "city")  # places on the shore that ships put in at


def _miles_per_tile() -> int:
    from realmwalker.game.state import MILES_PER_TILE

    return MILES_PER_TILE


def _spec(game, kind: str) -> dict:
    return game.tables.economy["services"][kind]


def _from_here(game, cost: np.ndarray, x: int, y: int) -> np.ndarray:
    """Distance (in hundredths of a tile) from (x, y) over the squares of `cost` that are not 0."""
    dist = tcod.path.maxarray(cost.shape, dtype=np.int32)
    dist[x, y] = 0
    tcod.path.dijkstra2d(dist, cost, 100, 141, out=dist)
    return dist


_KEPT: dict = {}  # (world, kind, settlement) -> routes: the roads and the coasts do not move while you play


def _routes(game, here, cost: np.ndarray, kinds: tuple, spec: dict) -> list[tuple[object, int, int]]:
    """(settlement, miles, minutes) for every place of these kinds that `cost` reaches from `here`, nearest first."""
    dist = _from_here(game, cost, here.x, here.y)
    far = int(spec["max_miles"])
    out = []
    for s in game.world.settlements:
        if s is here or s.kind not in kinds or not cost[s.x, s.y]:
            continue
        d = int(dist[s.x, s.y])
        if d >= np.iinfo(np.int32).max:
            continue
        miles = max(1, int(round(d / 100 * _miles_per_tile())))
        if miles > far:
            continue
        hours = miles / float(spec["mph"])
        days = hours / int(spec["hours_a_day"])  # the coach stops at night; a ship sails on
        minutes = int(round(hours * 60 + max(0, math.ceil(days) - 1) * (24 - int(spec["hours_a_day"])) * 60))
        out.append((s, miles, minutes))
    out.sort(key=lambda r: r[1])
    return out[:6]


def coach_routes(game, here) -> list[tuple[object, int, int]]:
    """Towns the coaches run to from here, along the roads."""
    if here is None or here.kind not in COACH_KINDS:
        return []
    key = (game.world.meta.id, "coach", here.id)
    if key not in _KEPT:
        _KEPT[key] = _coach_routes(game, here)
    return _KEPT[key]


def _coach_routes(game, here) -> list[tuple[object, int, int]]:
    w = game.world
    cost = np.where(w.road, 1, 0).astype(np.int32)
    for s in w.settlements:
        cost[s.x, s.y] = 1  # (the road ends at the gate)
    return _routes(game, here, cost, COACH_KINDS, _spec(game, "coach"))


def _sea(game) -> np.ndarray:
    w = game.world
    ocean = w.biome_ids.index("ocean") if "ocean" in w.biome_ids else -1
    return w.biome == ocean


def harbour(game, s, sea: np.ndarray | None = None) -> bool:
    """A place on the sea shore."""
    if s is None or s.kind not in HARBOUR_KINDS:
        return False
    sea = _sea(game) if sea is None else sea
    W, H = sea.shape
    return any(sea[x, y] for x in range(max(0, s.x - 1), min(W, s.x + 2)) for y in range(max(0, s.y - 1), min(H, s.y + 2)))


def ship_routes(game, here) -> list[tuple[object, int, int]]:
    """Harbours a ship sails to from here, over the open sea."""
    if here is None or here.kind not in HARBOUR_KINDS:
        return []
    key = (game.world.meta.id, "ship", here.id)
    if key not in _KEPT:
        _KEPT[key] = _ship_routes(game, here)
    return _KEPT[key]


def _ship_routes(game, here) -> list[tuple[object, int, int]]:
    sea = _sea(game)
    if not harbour(game, here, sea):
        return []
    cost = np.where(sea, 1, 0).astype(np.int32)
    ports = [s for s in game.world.settlements if harbour(game, s, sea)]
    for s in ports:
        cost[s.x, s.y] = 1
    return _routes(game, here, cost, HARBOUR_KINDS, _spec(game, "ship"))


def fare(game, kind: str, miles: int) -> int:
    """For the whole party: each of them pays by the mile."""
    return max(1, int(_spec(game, kind)["per_mile"]) * miles * len([c for c in game.party if c.alive]))


def travel(game, kind: str, dest, miles: int, minutes: int) -> list[str]:
    """Ride the coach or sail: the days pass on the way (the body still eats, drinks and tires), and you are set
    down at the gate of `dest`. The fare has been paid."""
    if game.in_local:
        game.leave_local()
    p = game.player
    p.x, p.y = dest.x, dest.y
    game.travel = None
    game.reveal()
    game.pass_time(minutes, "rest")
    days = minutes / (24 * 60)
    span = "a few hours" if days < 0.5 else "a day" if days < 1.5 else f"{round(days)} days"
    if kind == "coach":
        return [f"The coach rattles out of the yard. {span.capitalize()} of ruts, mud and coaching inns ({miles} "
                f"miles), and it sets you down at the gate of {dest.name}."]
    return [f"The ship stands out from the harbour. {span.capitalize()} at sea ({miles} miles), salt in "
            f"everything, and you come ashore at {dest.name}."]


# ---------------------------------------------------------------------------- messengers
def messenger_jobs(game, here) -> list[tuple[object, int, int]]:
    """(companion, miles, price) for each companion waiting somewhere else, who a messenger could fetch here."""
    out = []
    for c in getattr(game, "waiting", []):
        at = (c.companion or {}).get("wait_at")
        if not c.alive or not at or at == [here.x, here.y]:
            continue
        miles = max(1, int(round(math.hypot(at[0] - here.x, at[1] - here.y) * _miles_per_tile())))
        out.append((c, miles, max(1, int(_spec(game, "messenger")["per_mile"]) * miles)))
    return out


def send_for(game, c, here, miles: int) -> str:
    """The companion sets out for `here` and waits for you there (game/companions.rejoin)."""
    per_day = int(_spec(game, "messenger")["miles_a_day"])
    days = miles / per_day * 2  # the messenger goes there, and they come back with him
    c.companion["wait_at"] = [here.x, here.y]
    c.companion["coming"] = int(game.world.time + days * 24 * 60)
    span = "a day" if days < 1.5 else f"{round(days)} days"
    return (f"A rider sets off with your word for {c.name.split()[0]}. They should be here in about {span}, and will "
            f"wait for you in {here.name}.")
