"""Hosts on the map (Expansion 6 G.7, docs/ADVENTURES.md §5.21, §8.16): armies marching to their sieges, a tribe's
warband riding out, the dead of a risen king on the march, a crusade going to meet them, and columns of refugees on
the roads from a sacked or emptied town. World layer (no game): they move in the interlude between lives too.

A host is a record in `world.politics["hosts"]` (oldest first; finished ones are dropped):
    {"id": "H<n>", "kind", "faction" (-1: none), "group" (an encounter group, "" for refugees), "strength",
     "x", "y", "path": [[x, y], ...] (its whole road, start to goal), "at" (how far along it, in squares),
     "goal": {"settlement": id}, "speed" (squares a day), "since", "state" "marching" | "holding",
     and by kind "war" (an army's or a horde's war id), "threat" (the dead's), "against" (a crusade's host of the
     dead), "people" (refugees), "also" (marks the dead leave), "until" (a crusade holding a town)}
and `politics["hosts_tick"]` (the day they were last moved).

    raise_host(world, tables, kind, start, goal, day=, ...)   a host on its way (None when no road goes there)
    advance(pol, days=None)        every host moved by the days since hosts_tick (from Politics.advance weekly and
                                   game/story.daily daily, whichever comes first: the stamp keeps them in step);
                                   arriving, it acts: an army or a horde of a war begins its siege
                                   (`Politics.begin_siege`), a warband raids (`Politics.raid(target=)`), the dead,
                                   a crusade and a horde with no war act through `strike`, refugees settle
    advance_world(world, tables, day)                         the same, with a Politics of that day made for it
    strike(world, tables, host, s, day=, rng=)                a host with no war or tribe behind it falls on a town:
                                   marks (beset, burned, emptied, haunted), losses down to a floor of survivors,
                                   refugees, news; a crusade holds a town against the dead or cleanses it after them
    refugees(world, tables, s, lost, day=, rng=)              a column of the town's people on the road away
    near(world, x, y, within=)     the nearest host that is not refugees within `within` squares (for encounters)
    place(world, fid)              where a faction's host in the field is (news.faction_place, for a faction with no
                                   seat, lair or country)
    check(world, tables)           what is wrong with the hosts (autoplay `_check_hosts`)

Numbers and words are threats.json "hosts" (Expansion 6 pack); news lines are politics.json text ("host_*").
"""

from __future__ import annotations

import math

import numpy as np

from realmwalker.core import textgen
from realmwalker.world import marks

KINDS = ("army", "horde", "the_dead", "crusade", "warband", "refugees")
STATES = ("marching", "holding")
_COST: dict = {}  # (id(world), land_version) -> the walking cost of every square (roads cheap), kept while it holds


# ---------------------------------------------------------------------------- the records
def records(world) -> list[dict]:
    return world.politics.setdefault("hosts", [])


def get(world, hid) -> dict | None:
    return next((h for h in records(world) if h["id"] == hid), None)


def spec(tables) -> dict:
    return (getattr(tables, "threats", None) or {}).get("hosts") or {}


def _year(tables, day: float) -> int:
    return int(tables.calendar.at(int(day * 1440)).year)


def _cost(world, tables) -> np.ndarray:
    key = (id(world), world.meta.id, int(world.politics.get("land_version", 0)), world.width, world.height)
    got = _COST.get(key)
    if got is not None:
        return got
    B = tables.biomes
    remap = np.array([B.index.get(b, B.index["plains"]) for b in world.biome_ids], dtype=np.int32)
    passable = B.passable[remap][world.biome]
    cost = np.where(world.road, 1, 3).astype(np.int32)
    cost[~passable] = 0
    _COST.clear()
    _COST[key] = cost
    return cost


def route(world, tables, a: tuple[int, int], b: tuple[int, int]) -> list[list[int]] | None:
    """The way a host goes from a to b, keeping to the roads where it can (None: no way over land)."""
    import tcod

    if tuple(a) == tuple(b):
        return [[int(a[0]), int(a[1])]]
    cost = _cost(world, tables).copy()
    for x, y in (a, b):  # (a town or a barrow stands on ground a host can always leave and reach)
        cost[int(x), int(y)] = max(1, int(cost[int(x), int(y)]))
    path = tcod.path.path2d(cost, start_points=[(int(a[0]), int(a[1]))], end_points=[(int(b[0]), int(b[1]))],
                            cardinal=10, diagonal=14)
    if len(path) == 0:
        return None
    out = [[int(x), int(y)] for x, y in path.tolist()]
    if out[0] != [int(a[0]), int(a[1])]:
        out.insert(0, [int(a[0]), int(a[1])])
    return out


def raise_host(world, tables, kind: str, start: tuple[int, int], goal: int, *, day: float, faction: int = -1,
               strength: int = 50, group: str | None = None, most: float | None = None, **more) -> dict | None:
    """A host sets out from `start` for settlement `goal`. None when no road goes there, or the march would take
    longer than `most` days (threats.json hosts most_days): the caller then acts at once, as before hosts."""
    sp = spec(tables)
    s = world.settlements[int(goal)]
    path = route(world, tables, start, (s.x, s.y))
    if path is None:
        return None
    speed = float(sp.get("speed", {}).get(kind, 3.0))
    most = float(sp.get("most_days", 60)) if most is None else float(most)
    if (len(path) - 1) / max(0.1, speed) > most:
        return None
    n = int(world.politics.get("next_host", 0))
    world.politics["next_host"] = n + 1
    h = {"id": f"H{n}", "kind": kind, "faction": int(faction),
         "group": group if group is not None else str(sp.get("groups", {}).get(kind, "")),
         "strength": max(1, int(strength)), "x": path[0][0], "y": path[0][1], "path": path, "at": 0.0,
         "goal": {"settlement": int(goal)}, "speed": speed, "since": float(day), "state": "marching"}
    h.update(more)
    records(world).append(h)
    return h


def figures(h: dict) -> int:
    """How many figures its column shows on the map: three to seven, by its strength."""
    return max(3, min(7, 2 + int(math.log2(max(1.0, h["strength"] / 25.0)))))


def heading(h: dict) -> tuple[float, float, float]:
    """Where it is now between the squares of its road (x, y as floats) and which way it faces (dx)."""
    path = h["path"]
    i = min(int(h["at"]), len(path) - 1)
    j = min(i + 1, len(path) - 1)
    k = h["at"] - i if j > i else 0.0
    x = path[i][0] + (path[j][0] - path[i][0]) * k
    y = path[i][1] + (path[j][1] - path[i][1]) * k
    a, b = path[max(0, j - 1)], path[j]
    dx = (b[0] - a[0]) or (path[-1][0] - path[0][0]) or 1
    return x, y, float(dx)


def near(world, x: int, y: int, within: float | None = None, tables=None) -> dict | None:
    """The nearest host on the land within `within` squares (refugees are no fight; a crusade holding a town is
    inside it)."""
    if within is None:
        within = float(spec(tables).get("near", 3)) if tables is not None else 3.0
    best, bd = None, None
    for h in records(world):
        if h["kind"] == "refugees" or h["state"] != "marching" or not h.get("group"):
            continue
        d = max(abs(h["x"] - x), abs(h["y"] - y))
        if d <= within and (bd is None or d < bd):
            best, bd = h, d
    return best


def place(world, fid: int) -> tuple[int, int] | None:
    for h in records(world):
        if h["faction"] == int(fid):
            return int(h["x"]), int(h["y"])
    return None


def name_of(world, tables, h: dict) -> str:
    """What the people call it ("the army of Varn", "the dead of Old Harrow's barrow", "a crusade of the Lantern")."""
    words = spec(tables).get("names", {}).get(h["kind"], ["a host"])
    f = world.factions.get(h["faction"]) if h["faction"] >= 0 else None
    who = f.name if f is not None else h.get("who", "")
    line = words[int(h["id"][1:]) % len(words)]
    return line.replace("{who}", who)


# ---------------------------------------------------------------------------- moving
def advance_world(world, tables, day: float) -> None:
    from realmwalker.world.politics import Politics

    if world.politics.get("assaults"):
        from realmwalker.world import assaults

        assaults.due(world, tables, float(day), world.rng.child(f"assaults/{int(day * 1440)}"))  # (H.1)
    last = world.politics.get("hosts_tick")
    if last is None or float(day) - float(last) <= 0:
        if last is None:
            world.politics["hosts_tick"] = float(day)
        return
    if not records(world):
        world.politics["hosts_tick"] = float(day)
        return
    pol = Politics(world, tables, world.rng.child(f"hosts/{int(day)}"), day=float(day), year=_year(tables, day))
    advance(pol)
    if pol.changed:
        from realmwalker.world import factions as fx

        fx.touch(world)


def advance(pol, days: float | None = None) -> None:
    """Every host moved on (by `days`, or by the days since the stamp), and those arriving act."""
    w = pol.w
    if days is None:
        last = w.politics.get("hosts_tick")
        w.politics["hosts_tick"] = max(float(pol.day), float(last) if last is not None else float(pol.day))
        if last is None or pol.day <= float(last):
            return
        days = pol.day - float(last)
    for h in list(records(w)):
        if h not in records(w):
            continue  # (broken by another host this step)
        if not _still_wanted(pol, h):
            records(w).remove(h)
            continue
        if h["state"] == "holding":
            if pol.day >= float(h.get("until", 0)):
                records(w).remove(h)
            continue
        walked = min(float(days), max(0.0, float(pol.day) - float(h["since"])))  # (none of it before it set out)
        h["at"] = min(float(len(h["path"]) - 1), h["at"] + h["speed"] * walked)
        i = int(h["at"])
        h["x"], h["y"] = h["path"][i]
        if h["at"] >= len(h["path"]) - 1:
            arrive(pol, h)


def _still_wanted(pol, h: dict) -> bool:
    """A host whose reason is gone goes home: an army of a war that ended, the dead of a king laid to rest."""
    w = pol.w
    if h.get("war") is not None:
        war = next((x for x in w.wars if x["id"] == h["war"]), None)
        return war is not None and war["active"] and war.get("march") == h["id"]
    if h["kind"] == "the_dead":
        from realmwalker.world import threats

        t = threats.records(w).get(h.get("threat"))  # (its doom under way ends the threat: its dead still walk)
        return t is not None and (t["state"] in threats.LIVE or t.get("outcome") == "doom") and \
            threats.villain_lives(w, t)  # (their king laid or slain on the way: the dead go back to the earth)
    if h["kind"] == "warband" or h["faction"] >= 0:
        f = w.factions.get(h["faction"])
        return f is not None and f.active
    return True


def arrive(pol, h: dict) -> None:
    w = pol.w
    s = w.settlements[h["goal"]["settlement"]]
    if h["kind"] in ("army", "horde") and h.get("war") is not None:
        records(w).remove(h)
        war = next(x for x in w.wars if x["id"] == h["war"])
        war["march"] = None
        by = w.factions.get(h["faction"])
        if by is not None and war.get("siege") is None:
            pol.begin_siege(war, by, s)
        return
    if h["kind"] == "warband":
        records(w).remove(h)
        tribe = w.factions.get(h["faction"])
        if tribe is not None:
            pol.raid(tribe, target=s)
        return
    if h["kind"] == "refugees":
        records(w).remove(h)
        _settle(pol, h, s)
        return
    strike(w, pol.t, h, s, day=pol.day, rng=pol.rng)
    if h["kind"] == "crusade" and h in records(w):
        return  # (it holds the town a while)
    if h in records(w):
        records(w).remove(h)


# ---------------------------------------------------------------------------- arriving
def _say(world, tables, key: str, values: dict, rng, *, day: float, where, importance: int = 2, factions=(),
         places=(), figures=()) -> str:
    from realmwalker.world import news
    from realmwalker.world.history import remember

    lines = tables.politics["text"].get(key) or [key]
    text = textgen.fill(rng.choice(lines), rng, {}, {k: str(v) for k, v in values.items()})
    news.add(world, text, where[0], where[1], kind=key, importance=importance, factions=factions, places=places,
             day=day)
    if importance >= 3:
        remember(world, _year(tables, day), key, text, importance=importance, factions=factions, places=places,
                 figures=figures)
    return text


def _words(world, tables, h: dict, s=None) -> dict:
    out = {"host": name_of(world, tables, h)}
    f = world.factions.get(h["faction"]) if h["faction"] >= 0 else None
    out["who"] = f.name if f is not None else h.get("who", "")
    if s is not None:
        out["place"] = s.name
    return out


def strike(world, tables, host: dict, s, *, day: float, rng, scale: float = 1.0, live: bool = True) -> list[str]:
    """A host with no war or tribe behind it reaches a town (the dead, a horde, a crusade). Returns the news.
    With the party at the town (`live`, world/assaults.party_near) the dead and a horde begin an assault there
    instead, played on the map or resolved later; an assault's end comes back here with `live` False and its
    `scale` (how much of the harm is done) and its own kinds (raid, sack, summoned, dragon)."""
    sp = spec(tables).get("strike", {})
    said = []
    if host["kind"] == "crusade":
        return _crusade_arrives(world, tables, host, s, day=day, rng=rng)
    guard = next((c for c in records(world) if c["kind"] == "crusade" and c["state"] == "holding"
                  and c["goal"]["settlement"] == s.id), None)
    if guard is not None:  # (a crusade stands at its fences: the hosts meet)
        if rng.random() < guard["strength"] / float(guard["strength"] + host["strength"]):
            if host in records(world):
                records(world).remove(host)
            guard["strength"] = max(1, int(guard["strength"] * rng.uniform(0.5, 0.8)))
            said.append(_say(world, tables, "host_crusade_holds", {**_words(world, tables, guard, s),
                                                                    "foe": name_of(world, tables, host)},
                             rng, day=day, where=(s.x, s.y), importance=3, places=[s.id],
                             factions=[guard["faction"]] if guard["faction"] >= 0 else []))
            return said
        records(world).remove(guard)
        said.append(_say(world, tables, "host_crusade_broken", {**_words(world, tables, guard, s),
                                                                 "foe": name_of(world, tables, host)},
                         rng, day=day, where=(s.x, s.y), importance=3, places=[s.id]))
    if live and host["kind"] in ("the_dead", "horde"):
        from realmwalker.world import assaults

        if assaults.party_near(world, tables, s) and assaults.begin(
                world, tables, s, "the_dead" if host["kind"] == "the_dead" else "raid", day=day, rng=rng,
                faction=host["faction"], who=_words(world, tables, host)["who"], group=host.get("group"),
                strike=host["kind"], threat=host.get("threat"), strength=host["strength"], figure=host.get("figure"),
                also=host.get("also", ())) is not None:
            if host in records(world):
                records(world).remove(host)
            return said  # (the party is there: it is fought through the town, H.1)
    k = sp.get(host["kind"], {"losses": [0.15, 0.3], "marks": ["beset"]})
    was = s.population
    scale = max(0.0, min(1.0, float(scale)))
    if host["kind"] == "the_dead" and scale < 0.5:  # (held off: the town is beset, not emptied)
        floor = float(tables.threats.get("emptied", {}).get("floor", 0.2))
        s.population = max(10, int(s.population * (1.0 - (1.0 - floor) * scale)))
        k = {"marks": ["beset"], "days": 30}
    elif host["kind"] == "the_dead":
        floor = float(tables.threats.get("emptied", {}).get("floor", 0.2))
        s.population = max(10, int(s.population * floor))
        days = float(tables.threats.get("emptied", {}).get("rebuild_days", 90))
        marks.add(world, s, "emptied", day, tables, until=day + days, was=was, by=host.get("who", ""),
                  threat=host.get("threat"))
    else:
        lo, hi = k.get("losses", [0.15, 0.3])
        s.population = max(10, int(s.population * (1.0 - rng.uniform(float(lo), float(hi)) * scale)))
    for mark in list(k.get("marks", [])) + list(host.get("also", [])):
        if mark == "burned" and s.kind not in ("hamlet", "village"):
            continue
        extra = {"until": day + float(k.get("days", 30))} if mark in ("beset", "raided") else {}
        marks.add(world, s, mark, day, tables, by=host.get("who", ""), **extra,
                  **({"threat": host["threat"]} if host.get("threat") else {}))
    figs = [host["figure"]] if host.get("figure") is not None else []
    said.append(_say(world, tables, f"host_{host['kind']}_strikes", _words(world, tables, host, s), rng, day=day,
                     where=(s.x, s.y), importance=3, places=[s.id], figures=figs))
    refugees(world, tables, s, was - s.population, day=day, rng=rng)
    return said


def _crusade_arrives(world, tables, host: dict, s, *, day: float, rng) -> list[str]:
    """A crusade at the town it came to save: if the dead have been, it cleanses what they left (the haunting
    lifted); if not, it holds the town for a month against them."""
    cs = spec(tables).get("crusade", {})
    words = _words(world, tables, host, s)
    facs = [host["faction"]] if host["faction"] >= 0 else []
    if s.status.get("haunted") is not None:
        marks.lift(world, s, "haunted")
        records(world).remove(host)
        return [_say(world, tables, "host_crusade_cleanses", words, rng, day=day, where=(s.x, s.y), importance=3,
                     places=[s.id], factions=facs)]
    host["state"] = "holding"
    host["until"] = day + float(cs.get("hold_days", 30))
    return [_say(world, tables, "host_crusade_arrives", words, rng, day=day, where=(s.x, s.y), importance=2,
                 places=[s.id], factions=facs)]


def refugees(world, tables, s, lost: int, *, day: float, rng) -> dict | None:
    """Some of those a town lost take to the road, for the nearest bigger place of the land that is not itself in
    trouble (a column on the map for some days; its people join that town when they come)."""
    rs = spec(tables).get("refugees", {})
    people = int(lost * float(rs.get("share", 0.4)))
    if people < int(rs.get("least", 20)):
        return None
    reach = float(rs.get("reach", 30))
    bad = ("siege", "beset", "emptied", "burning", "plague", "sacked")
    order = {"hamlet": 0, "village": 1, "town": 2, "city": 3}
    options = [t for t in world.settlements if t.id != s.id and order.get(t.kind, 2) >= order.get(s.kind, 1)
               and math.hypot(t.x - s.x, t.y - s.y) <= reach and not any(t.status.get(m) for m in bad)]
    if not options:
        return None
    to = min(options, key=lambda t: (math.hypot(t.x - s.x, t.y - s.y), t.id))
    h = raise_host(world, tables, "refugees", (s.x, s.y), to.id, day=day, strength=max(1, people // 10),
                   group="", people=people, came_from=s.id)
    if h is None:
        return None
    _say(world, tables, "host_refugees_flee", {"place": s.name, "to": to.name}, rng, day=day, where=(s.x, s.y),
         importance=2, places=[s.id, to.id])
    return h


def _settle(pol, h: dict, s) -> None:
    s.population += int(h.get("people", 0))
    frm = pol.w.settlements[int(h["came_from"])] if h.get("came_from") is not None else None
    _say(pol.w, pol.t, "host_refugees_arrive", {"place": s.name, "from": frm.name if frm is not None else "the south"},
         pol.rng, day=pol.day, where=(s.x, s.y), importance=1, places=[s.id])


# ---------------------------------------------------------------------------- raising (from politics and threats)
def nearest_holding(world, f, target) -> tuple[int, int] | None:
    """Where a faction musters to march on `target`: its holding nearest it, else its seat, lair or country."""
    from realmwalker.world import factions as fx
    from realmwalker.world import news

    held = [t for t in fx.holdings(world, f, deep=True) if t.id != target.id]
    if held:
        t = min(held, key=lambda t: ((t.x - target.x) ** 2 + (t.y - target.y) ** 2, t.id))
        return t.x, t.y
    return news.faction_place(world, f)


def march_to_siege(pol, war: dict, besieger, target) -> dict | None:
    """A war's besieger sends its army (a tribe its horde) to the town it will besiege: the siege begins when the
    host arrives, so it is seen coming. None when it musters at the walls already (the siege begins at once)."""
    w = pol.w
    start = nearest_holding(w, besieger, target)
    if start is None or math.hypot(start[0] - target.x, start[1] - target.y) < 2:
        return None
    kind = "horde" if besieger.kind == "tribe" else "army"
    h = raise_host(w, pol.t, kind, start, target.id, day=pol.day, faction=besieger.id,
                   strength=int(besieger.military * 0.6), war=war["id"])
    if h is None:
        return None
    war["march"] = h["id"]
    pol.say("host_marches" if kind == "army" else "host_horde_marches",
            {"attacker": besieger.name, "place": target.name}, where=(start[0], start[1]), importance=3,
            factions=[besieger], places=[target])
    return h


def ride_out(pol, tribe, target) -> dict | None:
    """A tribe's warband rides for the village it will raid (the raid falls when it gets there)."""
    w = pol.w
    start = nearest_holding(w, tribe, target)
    if start is None or math.hypot(start[0] - target.x, start[1] - target.y) < 2:
        return None
    return raise_host(w, pol.t, "warband", start, target.id, day=pol.day, faction=tribe.id,
                      strength=max(10, int(tribe.military * 0.4)))


def the_dead_march(pol, t: dict, target, also=()) -> dict | None:
    """A risen king's dead march from his barrow on the place he will empty; a crusade may set out to meet them."""
    from realmwalker.world import threats

    w = pol.w
    hx, hy = threats.home_xy(w, t)
    h = raise_host(w, pol.t, "the_dead", (hx, hy), target.id, day=pol.day, threat=t["id"],
                   strength=40 + 30 * int(t.get("tier", 1)), also=list(also), who=threats.villain_name(w, t),
                   figure=t["villain"].get("figure"))
    if h is None:
        return None
    pol.say("host_the_dead_marches", {"villain": threats.villain_name(w, t), "place": target.name},
            where=(hx, hy), importance=3, places=[target])
    crusade(pol, h)
    return h


def crusade(pol, dead: dict) -> dict | None:
    """The nearest temple or knightly order (else the realm whose land it is) takes up arms against the dead: a
    crusade marches to the town they march on."""
    from realmwalker.world import factions as fx

    w = pol.w
    cs = spec(pol.t).get("crusade", {})
    target = w.settlements[dead["goal"]["settlement"]]
    if not pol.rng.chance(float(cs.get("chance", 0.6))):
        return None
    reach = float(cs.get("reach", 45))
    best = None
    for f in fx.active_factions(w, "knightly_order") + fx.active_factions(w, "temple"):
        at = nearest_holding(w, f, target)
        if at is None:
            continue
        d = math.hypot(at[0] - target.x, at[1] - target.y)
        rank = (0 if f.kind == "knightly_order" else 1, d, f.id)  # (an order before a temple, then the nearest)
        if 2 <= d <= reach and (best is None or rank < best[2]):
            best = (f, at, rank)
    if best is None:
        lord = fx.realm_of_settlement(w, target)
        lord = fx.top_liege(w, lord) if lord is not None else None
        at = nearest_holding(w, lord, target) if lord is not None else None
        if at is None or math.hypot(at[0] - target.x, at[1] - target.y) < 2:
            return None
        best = (lord, at, None)
    f, at, _ = best
    lo, hi = cs.get("strength", [40, 120])
    h = raise_host(w, pol.t, "crusade", at, target.id, day=pol.day, faction=f.id,
                   strength=int(pol.rng.uniform(float(lo), float(hi))), against=dead["id"])
    if h is None:
        return None
    pol.say("host_crusade_marches", {"who": f.name, "place": target.name, "villain": dead.get("who", "")},
            where=at, importance=3, factions=[f], places=[target])
    return h


# ---------------------------------------------------------------------------- checking
def check(world, tables) -> list[str]:
    """What is wrong with the hosts (autoplay)."""
    out = []
    seen = set()
    for h in records(world):
        hid = h.get("id")
        if hid in seen:
            out.append(f"host {hid} twice")
        seen.add(hid)
        if h.get("kind") not in KINDS or h.get("state") not in STATES:
            out.append(f"host {hid}: kind {h.get('kind')} state {h.get('state')}")
            continue
        path = h.get("path") or []
        if not path or not 0 <= h["at"] <= len(path) - 1:
            out.append(f"host {hid}: at {h.get('at')} on a road of {len(path)}")
            continue
        if any(max(abs(a[0] - b[0]), abs(a[1] - b[1])) != 1 for a, b in zip(path, path[1:])):
            out.append(f"host {hid}: its road jumps")
        if any(not world.in_bounds(x, y) for x, y in path):
            out.append(f"host {hid}: its road leaves the world")
        if [h["x"], h["y"]] != path[int(h["at"])]:
            out.append(f"host {hid}: at ({h['x']},{h['y']}), off its road")
        g = h.get("goal", {}).get("settlement", -1)
        if not 0 <= g < len(world.settlements) or path[-1] != [world.settlements[g].x, world.settlements[g].y]:
            out.append(f"host {hid}: its road does not end at its goal")
        if h["strength"] <= 0:
            out.append(f"host {hid}: strength {h['strength']}")
        if h.get("war") is not None:
            war = next((x for x in world.wars if x["id"] == h["war"]), None)
            if war is None:
                out.append(f"host {hid}: war {h['war']} is no war")
        if (h["kind"] in ("army", "warband", "crusade") or h.get("war") is not None) and \
                h["faction"] not in world.factions:
            out.append(f"host {hid}: faction {h['faction']} is no faction")
    for war in world.wars:
        if war.get("active") and war.get("march") and get(world, war["march"]) is None:
            out.append(f"war {war['id']} marches with a host that is not there")
    return out
