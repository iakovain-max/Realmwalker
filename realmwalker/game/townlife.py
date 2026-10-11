"""Life in a town (2026-10-11, Anton: "bumping into one no longer starts the dialogue automatically ... This also
allows for the NPC to move on their own, and not only when the player moves ... make the time move independently of
the player's moves, and make the NPC move on their own").

Everyone in a town has a day by their trade (data/people.json "days"): from such an hour, asleep at home; from
another, at work; a meal; the inn or the square of an evening; the temple; the streets (guards on their rounds,
children at play, beggars). Each step of time (STEP_SECONDS of the world) everyone takes a step towards where their day
says they should be, along a path found once and kept while that is where they are going. They step round each other
and round you; two meeting in a narrow way swap places; you squeeze past them (you take each other's squares) unless
they will not budge. When a lot of time has passed at once (a night's sleep, a long wait, coming back after weeks),
everyone is simply where their day has taken them.

    catch_up(game, lm)        townsfolk act for the time passed since they last did (after anything that passes time
                              on a town's close-up map; the town clock in the game screen passes it in real time)
    settle(game, lm)          everyone straight to where they should be now
    activity(game, npc)       what their day has them doing at this hour ("sleep", "post", "evening"...)
    goal(game, lm, npc)       the square they are making for
    asleep(game, npc)         in bed now
    squeeze(game, npc)        you push past them: they take your square (False if they will not budge)
    said(game, lm)            what people near you are calling out just now (npc id -> words), for over their heads

Now and then something happens: on the holy day the clergy go in procession round the square, chanting; of an
evening two drinkers may come to blows outside the inn until the watch breaks it up.

Nothing here is saved but where people stand (NPC.x, y) and when the town last moved (Town.flags["clock"]): the paths
and the places of a town are found again when needed.
"""

from __future__ import annotations

import numpy as np
import tcod.path

STEP_SECONDS = 6  # one step of time: about one 5e round, as one of your steps
MOST_TICKS = 40  # more steps of time than this at once (four minutes) and everyone is simply where they are going
PATHS_PER_TICK = 12  # ways found in one step of time; the others wait their turn
DOORS = ("door_closed", "door_open", "doorway", "gate_open")
DEFAULT_DAY = [[0, "sleep"], [6, "post"], [12, "meal"], [13, "post"], [18, "evening"], [21, "sleep"]]
WANDERING = ("streets", "patrol", "play", "square")  # a new spot every little while
BARK_TICKS = 6  # words over someone's head stay this many steps of time (half a minute or so of watching)
BARK_REST = 40  # and the same person does not call out again for this many
BARK_NEAR = 11  # only people near you call out (squares)
HOLY_DAY = "Sunsday"  # the procession goes round the square in the morning
CLERGY = ("priest", "acolyte", "monk")
BRAWLERS = ("labourer", "sailor", "soldier", "porter", "carter", "tanner", "butcher", "farmer", "miner")
BRAWL_TICKS = 25  # how long a fight lasts if nobody stops it (two and a half minutes)

_towns: dict = {}  # lm.key -> _Town (paths and places), never saved


# ---------------------------------------------------------------------------- the town, as walkers see it
class _Town:
    """What walking needs to know about a town's close-up map: where one can walk, a pathfinder, its places."""

    def __init__(self, game, lm) -> None:
        from realmwalker.game.people import outdoor_cells, settlement_of

        T = game.tables.terrain
        terrain = game.remap_for(lm)[lm.terrain]
        doors = [T.index[n] for n in DOORS if n in T.index]
        self.stand = T.walk[terrain].copy()  # where one can stand (not in a shut doorway)
        self.walk = self.stand | np.isin(terrain, doors)  # where one can walk (doors open as you go through)
        self.astar = tcod.path.AStar(self.walk.astype(np.int16), diagonal=1.41)
        self.lm = lm
        self.count = len(lm.buildings)
        self.paths: dict[int, tuple[tuple[int, int], list[tuple[int, int]]]] = {}
        self.ticks = 0
        self.barks: dict[int, tuple[str, int]] = {}  # npc id -> (words, the step of time they end)
        self.barked: dict[int, int] = {}  # npc id -> the step of time they last called out
        self.near_home: dict[int, list[tuple[int, int]]] = {}  # npc id -> the streets round their home (children)
        self.brawl: dict | None = None  # {"spot", "a", "b", "until", "told"}: a fight in the street
        self.route: list[tuple[int, int]] | None = None  # the procession's way round the square
        s = settlement_of(game, lm)
        streets = outdoor_cells(game, lm, settlement=s) if s is not None else []
        self.streets = [c for c in streets if self.walk[c]] or [tuple(lm.entry)]
        hx, hy = lm.entry
        near = sorted(self.streets, key=lambda c: (c[0] - hx) ** 2 + (c[1] - hy) ** 2)
        self.square = near[:max(12, min(80, len(near) // 6))]
        self.inside: dict[str, list[tuple[int, int]]] = {}
        for b in lm.buildings:
            cells = [(x, y) for x in range(b.x + 1, b.x + b.w - 1) for y in range(b.y + 1, b.y + b.h - 1)
                     if b.contains(x, y) and self.walk[x, y] and T.walk[terrain[x, y]]]
            kind = "inn" if b.kind in ("inn", "caravanserai") else b.kind
            self.inside.setdefault(kind, []).extend(cells)

    def fresh(self, lm) -> bool:
        return self.lm is lm and self.count == len(lm.buildings)

    def path(self, here, there) -> list[tuple[int, int]]:
        if not self.walk[there]:
            return []
        return [(int(x), int(y)) for x, y in self.astar.get_path(here[0], here[1], there[0], there[1])]


def _town(game, lm) -> _Town:
    t = _towns.get(lm.key)
    if t is None or not t.fresh(lm):
        if len(_towns) > 8:  # only the towns you have just been in
            _towns.clear()
        t = _towns[lm.key] = _Town(game, lm)
    return t


def forget() -> None:
    """Drop what is known of the towns' ways (a new game, a loaded save)."""
    _towns.clear()


def _h(*parts: int) -> int:
    """A steady number from the parts: the same person on the same day makes the same choices."""
    v = 2166136261
    for p in parts:
        v = ((v ^ (int(p) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return v


# ---------------------------------------------------------------------------- a day
def day_of(game, npc) -> list:
    days = game.tables.people.get("days", {})
    return days.get(npc.job) or days.get("_default") or DEFAULT_DAY


MARKET_GOERS = ("farmer", "labourer", "weaver", "carter", "washerwoman", "elder", "child", "herder", "potter", "tailor",
                "cobbler", "fisher", "woodcutter", "miner", "porter", "pilgrim")
_market: dict[int, bool] = {}


def market_day(game) -> bool:
    """Is today a market day (people.MARKET_DAYS), when the square fills up of a morning?"""
    day = game.world.time // 1440
    if day not in _market:
        from realmwalker.game.people import MARKET_DAYS

        if len(_market) > 64:
            _market.clear()
        _market[day] = game.moment.weekday in MARKET_DAYS
    return _market[day]


def activity(game, npc) -> str:
    """What this person's day has them doing now (their hours move a little each way from the book's)."""
    if npc.flags.get("stays"):  # a gate guard, a wayfarer at the inn: where they were put
        return "post"
    shift = int(npc.flags.get("shift", 0))
    minute = (game.world.time + shift) % 1440
    hour = minute / 60
    day = day_of(game, npc)
    what = day[-1][1]
    for start, act in day:
        if hour >= start:
            what = act
    if what in ("post", "meal", "home") and 9 <= hour < 13 and npc.job in MARKET_GOERS and market_day(game) \
            and _h(npc.id, game.world.time // 1440, 11) % 3 == 0:
        return "square"  # off to the market
    if npc.job in CLERGY and 10 <= hour < 11 and holy_day(game):
        return "procession"
    return what


def holy_day(game) -> bool:
    return game.moment.weekday == HOLY_DAY


def asleep(game, npc) -> bool:
    return activity(game, npc) == "sleep" and (npc.x, npc.y) == tuple(npc.home)


def goal(game, lm, npc, town: _Town | None = None) -> tuple[int, int]:
    """The square this person is making for at this hour."""
    town = town or _town(game, lm)
    brawl = town.brawl
    if brawl is not None:
        if npc.id in (brawl["a"], brawl["b"]):
            return npc.x, npc.y  # they stand and fight
        if npc.job in ("guard", "soldier") and not npc.flags.get("stays") and _near(npc, brawl["spot"], 30):
            return brawl["spot"]  # the watch comes running
    act = activity(game, npc)
    today = game.world.time // 1440
    if act == "procession":
        route = _route(town, lm)
        step = (game.world.time % 60) // 6 + (CLERGY.index(npc.job) if npc.job in CLERGY else 0)
        return route[step % len(route)]
    if act in ("sleep", "home"):
        return tuple(npc.home)
    if act == "post":
        return tuple(npc.post)
    if act == "meal":
        if tuple(npc.home) != tuple(npc.post) and _h(npc.id, today, 1) % 3:
            return tuple(npc.home)
        act = "inn"
    if act == "evening":
        act = "inn" if _h(npc.id, today, 2) % 5 < 3 else "square"
    if act in ("inn", "temple"):
        cells = town.inside.get(act) or town.square
        return cells[_h(npc.id, today, 3) % len(cells)]
    if act in WANDERING:
        every = {"play": 12, "square": 90}.get(act, 20)  # minutes before they make for somewhere else
        slot = (game.world.time + int(npc.flags.get("shift", 0))) // every
        cells = town.square if act == "square" else town.streets
        if act == "play":  # children keep near home
            cells = town.near_home.get(npc.id)
            if cells is None:
                hx, hy = npc.home
                cells = town.near_home[npc.id] = [c for c in town.streets
                                                  if abs(c[0] - hx) < 14 and abs(c[1] - hy) < 10] or town.square
        return cells[_h(npc.id, slot, 4) % len(cells)]
    return tuple(npc.post)


def _near(npc, spot, d: int) -> bool:
    return max(abs(npc.x - spot[0]), abs(npc.y - spot[1])) <= d


def _route(town: _Town, lm) -> list[tuple[int, int]]:
    """The procession's way: from the temple's door round the corners of the square and back."""
    if town.route is None:
        sq = town.square
        temple = next((b for b in lm.buildings if b.kind == "temple"), None)
        start = None
        if temple is not None:
            dx, dy = temple.door
            start = min(sq, key=lambda c: (c[0] - dx) ** 2 + (c[1] - dy) ** 2)
        xs = [c[0] for c in sq]
        ys = [c[1] for c in sq]
        corners = []
        for tx, ty in ((min(xs), min(ys)), (max(xs), min(ys)), (max(xs), max(ys)), (min(xs), max(ys))):
            corners.append(min(sq, key=lambda c: (c[0] - tx) ** 2 + (c[1] - ty) ** 2))
        town.route = ([start] if start else []) + corners + ([start] if start else [])
    return town.route


# ---------------------------------------------------------------------------- moving
def _people(game, s) -> list:
    from realmwalker.game.people import npcs_in

    return [n for n in npcs_in(game.world, s.id) if n.alive and n.present]


def settle(game, lm) -> None:
    """Everyone straight to where their day has them now (no walking: time has jumped)."""
    from realmwalker.game.people import settlement_of, town_of

    s = settlement_of(game, lm)
    if s is None:
        return
    town = _town(game, lm)
    town.paths.clear()
    taken = {_you(game, lm)} | {(a.x, a.y) for a in lm.actors}
    for npc in sorted(_people(game, s), key=lambda n: n.id):
        spot = _free_near(town, goal(game, lm, npc, town), taken)
        if spot is not None:
            npc.x, npc.y = spot
        taken.add((npc.x, npc.y))
        npc.flags.pop("waited", None)
        npc.flags["placed"] = True
    town_of(game.world, s.id).flags["clock"] = _now(game)


def place_new(game, lm) -> None:
    """Anyone new in town (just made, just come back) goes straight to where their day has them."""
    from realmwalker.game.people import settlement_of

    s = settlement_of(game, lm)
    if s is None:
        return
    people = _people(game, s)
    new = [n for n in people if not n.flags.get("placed")]
    if not new:
        return
    town = _town(game, lm)
    taken = {_you(game, lm)} | {(a.x, a.y) for a in lm.actors} | \
        {(n.x, n.y) for n in people if n.flags.get("placed")}
    for npc in new:
        spot = _free_near(town, goal(game, lm, npc, town), taken)
        if spot is not None:
            npc.x, npc.y = spot
        taken.add((npc.x, npc.y))
        npc.flags["placed"] = True


def _free_near(town: _Town, spot, taken) -> tuple[int, int] | None:
    x0, y0 = spot
    for r in range(0, 5):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                x, y = x0 + dx, y0 + dy
                if 0 <= x < town.stand.shape[0] and 0 <= y < town.stand.shape[1] and town.stand[x, y] \
                        and (x, y) not in taken:
                    return x, y
    return None


def _you(game, lm) -> tuple[int, int]:
    """Where you stand on this map (nowhere, if it is a town made ahead of your arrival)."""
    return (game.player.lx, game.player.ly) if game.local is lm else (-9, -9)


def _now(game) -> int:
    return int(game.world.time) * 60 + int(getattr(game.player, "seconds", 0))


def catch_up(game, lm) -> None:
    """Townsfolk act for the time that has passed since they last did: a step each STEP_SECONDS, or (after a long
    while) straight to where they are going."""
    from realmwalker.game.people import settlement_of, town_of

    s = settlement_of(game, lm)
    if s is None:
        return
    flags = town_of(game.world, s.id).flags
    now = _now(game)
    last = flags.get("clock")
    if last is None or now < last or now - last > MOST_TICKS * STEP_SECONDS:
        settle(game, lm)
        return
    ticks = (now - last) // STEP_SECONDS
    for _ in range(ticks):
        tick(game, lm, s)
    flags["clock"] = last + ticks * STEP_SECONDS


def tick(game, lm, s) -> None:
    """One step of time: everyone takes a step towards where they are going."""
    town = _town(game, lm)
    town.ticks += 1
    people = _people(game, s)
    if not people:
        return
    me = _you(game, lm)
    occupied = {(n.x, n.y): n for n in people}
    for a in lm.actors:
        occupied.setdefault((a.x, a.y), None)
    budget = PATHS_PER_TICK
    start = town.ticks % len(people)  # who goes first goes round, so nobody is always last
    for npc in people[start:] + people[:start]:
        here = (npc.x, npc.y)
        g = goal(game, lm, npc, town)
        if here == g:
            npc.flags.pop("waited", None)
            continue
        if max(abs(here[0] - g[0]), abs(here[1] - g[1])) <= 1 and (g in occupied or g == me):
            continue  # beside the spot, and somebody is on it: near enough
        kept = town.paths.get(npc.id)
        if kept is None or kept[0] != g or not kept[1] or max(abs(kept[1][0][0] - here[0]),
                                                               abs(kept[1][0][1] - here[1])) != 1:
            if budget <= 0:
                continue
            budget -= 1
            cells = town.path(here, g)
            if not cells:
                continue
            kept = town.paths[npc.id] = (g, cells)
        nxt = kept[1][0]
        if nxt == me:  # you are in the way: wait, then go round you
            if _waited(npc) > 2:
                _side_step(town, npc, g, occupied, me)
            continue
        if nxt in occupied:
            other = occupied[nxt]
            if other is None:  # a beast in the street
                _side_step(town, npc, g, occupied, me)
                continue
            coming = town.paths.get(other.id)
            head_on = coming is not None and coming[1] and coming[1][0] == here
            idle = asleep(game, other) or (other.x, other.y) == goal(game, lm, other, town)
            waited = _waited(npc)
            if head_on or (idle and waited > 1):
                _swap(town, npc, other, occupied)  # two in a narrow way pass each other; one standing lets you by
            elif not _side_step(town, npc, g, occupied, me) and waited > 8:
                _swap(town, npc, other, occupied)  # (a queue that will not move: push through at last)
            continue
        _move(town, npc, nxt, occupied)
        kept[1].pop(0)
        npc.flags.pop("waited", None)
    for npc in people:  # whoever passes through a door leaves it open behind them
        _door(game, lm, npc)
    if game.local is lm:
        _brawl(game, lm, town, people)
        _call_out(game, lm, town, people)


def _waited(npc) -> int:
    npc.flags["waited"] = npc.flags.get("waited", 0) + 1
    return npc.flags["waited"]


def _move(town: _Town, npc, to, occupied) -> None:
    occupied.pop((npc.x, npc.y), None)
    npc.x, npc.y = to
    occupied[to] = npc


def _swap(town: _Town, a, b, occupied) -> None:
    pa, pb = (a.x, a.y), (b.x, b.y)
    a.x, a.y = pb
    b.x, b.y = pa
    occupied[pa], occupied[pb] = b, a
    for n, now in ((a, pb), (b, pa)):
        kept = town.paths.get(n.id)
        if kept is not None and kept[1] and kept[1][0] == now:
            kept[1].pop(0)
        else:
            town.paths.pop(n.id, None)
        n.flags.pop("waited", None)


def _side_step(town: _Town, npc, g, occupied, me) -> bool:
    """A step aside that still goes the right way, if there is one; else they wait. True if they stepped."""
    here = (npc.x, npc.y)
    best, gain = None, 0.0
    base = (here[0] - g[0]) ** 2 + (here[1] - g[1]) ** 2
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            c = (here[0] + dx, here[1] + dy)
            if (dx or dy) and 0 <= c[0] < town.walk.shape[0] and 0 <= c[1] < town.walk.shape[1] and town.walk[c] \
                    and c not in occupied and c != me:
                d = base - ((c[0] - g[0]) ** 2 + (c[1] - g[1]) ** 2)
                if best is None or d > gain:
                    best, gain = c, d
    if best is not None and (gain > 0 or npc.flags.get("waited", 0) > 4):
        _move(town, npc, best, occupied)
        town.paths.pop(npc.id, None)
        npc.flags.pop("waited", None)
        return True
    return False


def _door(game, lm, npc) -> None:
    T = game.tables.terrain
    here = int(game.remap_for(lm)[lm.terrain[npc.x, npc.y]])
    if T.ids[here] == "door_closed" and "door_open" in lm.terrain_ids:
        lm.terrain[npc.x, npc.y] = lm.terrain_ids.index("door_open")


# ---------------------------------------------------------------------------- words in passing
def _brawl(game, lm, town: _Town, people) -> None:
    """Of an evening, now and then, two who have drunk too much come to blows in the street by the inn, shouting,
    until the watch comes and pulls them apart (or they tire of it). Only with the world's voice on."""
    b = town.brawl
    if b is not None:
        guards = [n for n in people if n.job in ("guard", "soldier") and _near(n, b["spot"], 1)]
        if guards or town.ticks >= b["until"]:
            town.brawl = None
            if b.get("told") and getattr(game, "flavour", None) and game.flavour():
                game.say("The watch pulls the brawlers apart and sends them home." if guards else
                         "The brawl runs out of breath, and so do they.", "flavor")
        return
    if not getattr(game, "flavour", None) or not game.flavour() or game.light >= 0.5:
        return
    if _h(town.ticks, game.world.time, 13) % 900:  # rare: about once an evening of watching
        return
    me = (game.player.lx, game.player.ly)
    out = [n for n in people if n.job in BRAWLERS and activity(game, n) in ("evening", "inn")
           and lm.building_at(n.x, n.y) is None and _near(n, me, BARK_NEAR)]
    for a in out:
        for c in out:
            if c is not a and _near(a, (c.x, c.y), 1):
                town.brawl = {"spot": (a.x, a.y), "a": a.id, "b": c.id, "until": town.ticks + BRAWL_TICKS, "told": True}
                insults = game.tables.people.get("barks", {}).get("_brawl", ["Say that again!", "You cheat!"])
                town.barks[a.id] = (insults[_h(a.id, town.ticks) % len(insults)], town.ticks + BARK_TICKS)
                town.barks[c.id] = (insults[_h(c.id, town.ticks, 1) % len(insults)], town.ticks + BARK_TICKS)
                game.say("A fight breaks out in the street: fists, then a bench.", "flavor")
                return


def _call_out(game, lm, town: _Town, people) -> None:
    """Now and then someone near you says something in passing (data/people.json "barks"): the baker cries her
    bread, the crier the news, a child dares another. Only with the world's voice on (Text detail)."""
    town.barks = {k: v for k, v in town.barks.items() if v[1] > town.ticks}
    if not getattr(game, "flavour", None) or not game.flavour() or len(town.barks) >= 3:
        return
    if _h(town.ticks, game.world.time, 7) % 4:  # about one in four steps of time
        return
    me = (game.player.lx, game.player.ly)
    inside = lm.building_at(*me)
    near = [n for n in people if max(abs(n.x - me[0]), abs(n.y - me[1])) <= BARK_NEAR and n.id not in town.barks
            and town.ticks - town.barked.get(n.id, -10**6) > BARK_REST and not asleep(game, n)
            and lm.building_at(n.x, n.y) is inside]
    if near:  # only those you can see (not round a corner, not behind a wall)
        from realmwalker.game import vision

        seen = vision.player_fov(game, lm, remember=False)
        near = [n for n in near if seen[n.x, n.y]]
    if not near:
        return
    npc = near[_h(town.ticks, len(near), 8) % len(near)]
    words = _words_for(game, npc, _h(npc.id, town.ticks, 9))
    if words:
        town.barks[npc.id] = (words, town.ticks + BARK_TICKS)
        town.barked[npc.id] = town.ticks


def _words_for(game, npc, roll: int) -> str | None:
    barks = game.tables.people.get("barks", {})
    if npc.job == "crier" and roll % 3 == 0:  # the news, cried
        from realmwalker.game.news import heard_items

        items = [n for n in heard_items(game) if len(n["text"]) <= 70]
        if items:
            return "Hear ye! " + items[roll % len(items)]["text"]
    own = barks.get(npc.job, [])
    if npc.job in CLERGY and activity(game, npc) == "procession":
        own = barks.get("_procession", own)
    night = game.light < 0.35
    common = barks.get("_night" if night else "_any", [])
    pool = own if own and (roll % 10 < 7 or not common) else common
    return pool[(roll // 10) % len(pool)] if pool else None


def said(game, lm) -> dict[int, str]:
    """What people near you are calling out just now: npc id -> their words (for over their heads)."""
    t = _towns.get(lm.key) if lm is not None else None
    if t is None:
        return {}
    return {k: v[0] for k, v in t.barks.items() if v[1] > t.ticks}


# ---------------------------------------------------------------------------- you and them
def squeeze(game, npc) -> bool:
    """You push past someone: they step into your square as you step into theirs. False if they will not budge (a
    guard at a gate, someone asleep in bed)."""
    lm = game.local
    if lm is None or npc.flags.get("stays") or asleep(game, npc):
        return False
    town = _town(game, lm)
    p = game.player
    if not town.walk[p.lx, p.ly]:
        return False
    npc.x, npc.y = p.lx, p.ly
    town.paths.pop(npc.id, None)
    npc.flags.pop("waited", None)
    return True
