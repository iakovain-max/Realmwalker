"""Finding your way on foot (after v1): walking to a spot on a close-up map, and the places you know there.

In a town every building looks the same from the street, and a city is a hundred key presses across. Clicking a
spot (or looking at it and pressing Enter) walks you there a step at a time, stopping for anything that matters;
clicking a person walks you up to them and starts the conversation. In look mode, Tab jumps between the places you
have seen: the inn, the shop, the smithy, the healer, the temple, the stable, the hall, the notice board, the people
worth knowing, and underground the stairs and the chests.

`GameState.walk_to` holds where the walk is going (not saved: a walk is a few seconds of the player's time).
"""

from __future__ import annotations

import math

import numpy as np
import tcod.path

BUSINESS = {"inn": "the inn", "store": "the shop", "smithy": "the smithy", "healer": "the healer's",
            "temple": "the temple", "stable": "the stable", "hall": "the hall", "keep": "the keep",
            "guild": "the guildhall", "market": "the market"}
UNDERGROUND = {"stairs_up": "the stairs up", "stairs_down": "the stairs down", "chest": "a chest",
               "sarcophagus": "a coffin", "captive": "someone in chains"}


def _grid(game, lm):
    """(cost grid for walking, terrain ids by cell). Closed doors open as you reach them. People are walked
    round when there is room, and otherwise up to (they move, and the walk stops in front of them with a word);
    bands of strangers are not walked through at all."""
    T = game.tables.terrain
    t = game.remap_for(lm)[lm.terrain]
    ids = np.array(T.ids)[t]
    walk = T.walk[t] | (ids == "door_closed")
    cost = walk.astype(np.int32)
    if lm.kind == "settlement":
        from realmwalker.game.people import npcs_in, settlement_here

        s = settlement_here(game)
        for npc in npcs_in(game.world, s.id) if s is not None else []:
            if npc.alive and npc.present and lm.in_bounds(npc.x, npc.y) and cost[npc.x, npc.y]:
                cost[npc.x, npc.y] = 25
    for a in lm.actors:
        if lm.in_bounds(a.x, a.y):
            cost[a.x, a.y] = 0
    return cost, ids


def plan(game, dest: tuple[int, int]) -> list[tuple[int, int]] | None:
    """The steps from where you stand to `dest` on this close-up map (the last one may be into a person, a chest
    or a locked door, which is how you reach them), or None when there is no way you know of."""
    lm = game.local
    p = game.player
    if lm is None or not lm.in_bounds(*dest) or dest == (p.lx, p.ly) or not lm.seen[dest]:
        return None
    cost, _ = _grid(game, lm)
    cost[dest] = 1  # you may walk into what is there: a person to talk to, a chest to open
    path = tcod.path.path2d(cost, start_points=[(p.lx, p.ly)], end_points=[dest], cardinal=2, diagonal=3)
    points = [(int(x), int(y)) for x, y in path.tolist()[1:]]
    return points or None


def _person_at(game, x: int, y: int):
    if game.local is None or game.local.kind != "settlement":
        return None
    from realmwalker.game.people import npc_at

    return npc_at(game, x, y)


def begin(game, dest: tuple[int, int], *, talk: bool = True) -> bool:
    """Set off for a spot, or (with talk) for the person standing on it. False, and a word why, when there is no
    way there."""
    if plan(game, dest) is None:
        game.say("You can see no way to get there from here.", "system")
        return False
    game.walk_to = dest
    who = _person_at(game, *dest) if talk else None
    game.walk_talk = who.id if who is not None else None  # walking up to someone is to talk to them
    return True


def step(game) -> bool:
    """One step of a walk. False when the walk is over: arrived, blocked, or something worth stopping for."""
    dest = getattr(game, "walk_to", None)
    lm = game.local
    if dest is None or lm is None or game.busy:
        game.walk_to = None
        return False
    talk = getattr(game, "walk_talk", None)
    if talk is not None and talk in game.world.npcs:
        who = game.world.npcs[talk]
        if who.alive and who.present:
            dest = game.walk_to = (who.x, who.y)  # they have moved: follow them
    path = plan(game, dest)  # again every step: people move
    if path is None:
        game.walk_to = None
        return False
    p = game.player
    key, before, told = lm.key, (p.lx, p.ly), len(game.log.messages)
    nx, ny = path[0]
    other = _person_at(game, nx, ny)
    if other is not None and other.id != talk:
        # Somebody stands in the doorway you were making for: stop in front of them rather than accost them.
        game.say(f"{other.label()[:1].upper() + other.label()[1:]} is in your way.", "system")
        game.walk_to = None
        return False
    game.move(nx - p.lx, ny - p.ly)
    arrived = (p.lx, p.ly) == dest
    trouble = any(m.category in ("warn", "danger") for m in game.log.messages[told:])
    alert = any(a.alert for a in lm.actors)
    moved_on = game.player.local_key != key or game.local is None
    stuck = (p.lx, p.ly) == before and len(path) > 1 and not _opened_a_door(game, lm, nx, ny)
    if arrived or trouble or alert or moved_on or stuck or game.busy or game.talk_to is not None or len(path) <= 1:
        game.walk_to = None
        return False
    return True


def _opened_a_door(game, lm, x: int, y: int) -> bool:
    T = game.tables.terrain
    return T.ids[int(game.remap_for(lm)[lm.terrain[x, y]])] == "door_open"


def places(game) -> list[tuple[int, int, str]]:
    """What you have seen here that is worth walking to, nearest first: (x, y, what it is)."""
    lm = game.local
    if lm is None:
        return []
    p = game.player
    out: list[tuple[int, int, str]] = []
    if lm.kind == "settlement":
        from realmwalker.game.people import npcs_in, settlement_here

        s = settlement_here(game)
        town = game.world.towns.get(s.id) if s is not None else None
        for i, b in enumerate(lm.buildings):
            label = BUSINESS.get(b.kind)
            dx, dy = b.door
            if label and lm.in_bounds(dx, dy) and lm.seen[dx, dy]:
                name = town.names.get(i, "") if town is not None else ""
                out.append((dx, dy, f"{label}: {name}" if name else label))
        for npc in npcs_in(game.world, s.id) if s is not None else []:
            if npc.alive and npc.present and npc.notable and lm.in_bounds(npc.x, npc.y) and lm.seen[npc.x, npc.y]:
                out.append((npc.x, npc.y, npc.label()))
    _, ids = _grid(game, lm)
    for name, label in (UNDERGROUND if lm.kind == "dungeon" else {"notice_board": "the notice board"}).items():
        for x, y in np.argwhere((ids == name) & lm.seen):
            out.append((int(x), int(y), label))
    out = [o for o in out if (o[0], o[1]) != (p.lx, p.ly)]
    out.sort(key=lambda o: math.hypot(o[0] - p.lx, o[1] - p.ly))
    return out
