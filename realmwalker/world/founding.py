"""Founding: new places made while you play (Expansion 6 G.9; docs/ADVENTURES.md §5.21 "New places", §8.16
"Founding"). World layer (no game): the interlude between lives founds and grows camps too.

Until now nothing made a settlement while the game was played. A founded place is an ordinary `Settlement`, appended
at the end of `world.settlements` (its index is its id: a settlement is never deleted or reordered), with a name, a
realm that holds it (in the history's ledger through `Politics.set_owner`, as autoplay demands), a people, and a road
to the nearest road (laid through `world/reshape.py` as a land change of kind "road", so the painter draws it and the
ledger keeps it). The record of what it is and how far it has grown is kept beside it:

    world.politics["foundings"]  [{"id": "F<n>", "kind" (KINDS), "settlement", "stage" (index into STAGES), "since",
                                 "staged" (the day it reached its stage), "of" (the town it came out of, or None),
                                 "home" (the day its refugees went home, once), "story"?}]
    world.politics["styles"]     {str(settlement id): a towns.json style}: how its close-up map is laid out, read by
                               `towns.plan.style_for` and `ui/gfx/worldview.town_mark` before the people's own way

Its stages (STAGES): a camp of canvas tents ("encampment"), a fortified camp behind a palisade where timber halls
stand among the tents ("encampment_fortified"), and at last a village built its people's own way (the style override
lifted). Each stage is a re-stamp: the close-up map is laid out again from the record the next time the party walks in
(`game/founding.before_entry`), and on the world map it is drawn by `ui/gfx/mapsigns.founded`, a camp drawn larger
than any town mark, growing with it.

The first use: a refugee camp pitched outside a besieged city (`Politics.begin_siege` -> `refugee_camp`): some of the
city's people flee, on the side away from the besiegers; when the siege lifts some go home, the rest stay and the
camp grows (`weekly`, from `Politics.advance`). Numbers are threats.json "founding" (Expansion 6 pack), news lines
politics.json text ("camp_*").

    found(pol, x, y, kind=, people=, owner=, population=, ...)  the checklist; returns the Settlement
    spot_near(world, tables, s, away=None, rng=)               a square for a camp outside s, or None
    refugee_camp(pol, target, besieger)                        the first use (None when no camp is pitched)
    weekly(pol)                                                 refugees going home, camps growing, stages
    record_of(world, sid) / stage_of(world, s) / style_of(world, s)
    check(world, tables)                                        what is wrong (autoplay `_check_founded`)
"""

from __future__ import annotations

import math

import numpy as np

KINDS = ("refugee_camp",)
STAGES = ("camp", "fortified", "town")
STAGE_STYLES = ("encampment", "encampment_fortified")  # the towns.json style of each stage but the last
FIRST_KIND = "hamlet"  # a camp is a hamlet to the rules (services, prices, its size); a grown town a village
TOWN_KIND = "village"


# ---------------------------------------------------------------------------- records
def records(world) -> list[dict]:
    return world.politics.setdefault("foundings", [])


def styles(world) -> dict:
    return world.politics.setdefault("styles", {})


def spec(tables) -> dict:
    return (getattr(tables, "threats", None) or {}).get("founding") or {}


def record_of(world, sid: int) -> dict | None:
    for rec in world.politics.get("foundings", ()):
        if int(rec["settlement"]) == int(sid):
            return rec
    return None


def stage_of(world, s) -> int | None:
    rec = record_of(world, s.id)
    return int(rec["stage"]) if rec is not None else None


def style_of(world, s) -> str | None:
    """The style a settlement is laid out in instead of its people's own, if any (`politics["styles"]`)."""
    if world is None:
        return None
    return (world.politics.get("styles") or {}).get(str(s.id))


# ---------------------------------------------------------------------------- where
def _remap(world, tables) -> np.ndarray:
    B = tables.biomes
    return np.array([B.index.get(b, B.index["plains"]) for b in world.biome_ids], dtype=np.int32)


def _passable(world, tables) -> np.ndarray:
    return tables.biomes.passable[_remap(world, tables)][world.biome]


WET = ("coast", "marsh")  # (a camp would sooner not pitch where half the ground is water)


def spot_near(world, tables, s, *, away: tuple[int, int] | None = None, rng=None,
              reach: tuple[float, float] = (2.0, 3.6)) -> tuple[int, int] | None:
    """A square for a camp outside s: open passable land a short walk off, never on or beside another place, a
    wonder, water, a changed land or the party's square; on the side away from `away` (the besiegers) when given,
    near a road if it can be."""
    from realmwalker.world import reshape

    mask = reshape.keep_out(world)
    ok = _passable(world, tables) & ~mask
    hours = tables.biomes.move_hours[_remap(world, tables)][world.biome]
    places = (world.settlement_grid >= 0) | (world.site_grid >= 0)
    lo, hi = reach
    options = []
    R = int(math.ceil(hi))
    for x in range(max(1, s.x - R), min(world.width - 1, s.x + R + 1)):
        for y in range(max(1, s.y - R), min(world.height - 1, s.y + R + 1)):
            d = math.hypot(x - s.x, y - s.y)
            if not lo <= d <= hi or not ok[x, y]:
                continue
            if places[x - 1:x + 2, y - 1:y + 2].any():
                continue  # (never beside another place: each has its own square round it)
            if reshape.changed_at(world, x, y):
                continue
            score = d * 0.3 + max(0.0, float(hours[x, y]) - 1.0) * 0.8  # (open dry ground first)
            score += 0.8 if world.biome_id(x, y) in WET else 0.0
            if away is not None:
                ax, ay = away[0] - s.x, away[1] - s.y
                n = math.hypot(ax, ay) or 1.0
                score += ((x - s.x) * ax + (y - s.y) * ay) / (n * d)  # (-1 straight away from them, +1 towards)
            near_road = bool(world.road[max(0, x - 2):x + 3, max(0, y - 2):y + 3].any())
            score -= 0.4 if near_road else 0.0
            score += (rng.random() * 0.2 if rng is not None else 0.0)
            options.append((score, x, y))
    if not options:
        return None
    options.sort()
    return options[0][1], options[0][2]


# ---------------------------------------------------------------------------- the checklist
def _name(pol, people: str) -> str:
    from realmwalker.world import names
    from realmwalker.world.naming import Namer

    w = pol.w
    namer = Namer(pol.t.place_names, pol.rng.child("found_name"), forge=names.forge(w, pol.t))
    namer.used.update(s.name for s in w.settlements)
    namer.used.update(x.name for x in w.sites)
    return namer.settlement(people)


def _culture(world, x: int, y: int, people: str) -> None:
    if people not in world.culture_ids:
        world.culture_ids.append(people)
    i = world.culture_ids.index(people)
    if i < 255:
        world.culture[x, y] = i


def lay_road(world, tables, s, *, day: float, most: int = 14) -> dict | None:
    """A road from the new place to the nearest road (cardinal steps, as the world's roads are laid), through the land
    ledger (reshape kind "road"). None when it already stands on a road's edge or none is near enough."""
    import tcod

    from realmwalker.world import reshape

    pts = np.argwhere(world.road)
    if not len(pts):
        return None
    d = np.abs(pts[:, 0] - s.x) + np.abs(pts[:, 1] - s.y)
    near = pts[(d > 0) & (d <= most)]
    if not len(near):
        return None
    cost = np.where(_passable(world, tables), 3, 0).astype(np.int32)
    cost[world.road] = 1
    keep = reshape.keep_out(world)
    cost[keep & ~world.road] = 0  # (round other places, wonders and water, never through them)
    cost[s.x, s.y] = 1
    path = tcod.path.path2d(cost, start_points=[(s.x, s.y)], end_points=[tuple(map(int, p)) for p in near],
                            cardinal=10, diagonal=None)
    cells = [(int(x), int(y)) for x, y in path.tolist() if (int(x), int(y)) != (s.x, s.y) and not world.road[x, y]]
    if not cells:
        return None
    rec = reshape.make(world, "road", {"x": s.x, "y": s.y, "cells": [list(c) for c in cells]},
                       seed=f"road/{s.id}", day=day)
    if rec is not None:
        from realmwalker.world.local import local_key

        for x, y, *_ in rec["cells"]:  # (wilderness maps built there are laid out again, with the road)
            world.local_maps.pop(local_key(x, y), None)
    return rec


def found(pol, x: int, y: int, *, kind: str, people: str, owner: int, population: int, name: str | None = None,
          of: int | None = None, story=None) -> object:
    """Found a settlement at (x, y) by the survey's checklist (ADVENTURES.md §8.16); returns it."""
    from realmwalker.world import factions as fx, reshape
    from realmwalker.world.local import local_key
    from realmwalker.world.model import Settlement

    if kind not in KINDS:
        raise ValueError(f"unknown founding {kind!r}")
    w = pol.w
    if w.settlement_grid[x, y] >= 0 or w.site_grid[x, y] >= 0:
        raise ValueError(f"a place already stands at {x},{y}")
    holder = w.factions.get(int(owner))
    if holder is None or holder.kind not in fx.REALM_KINDS:
        raise ValueError(f"a founded place is held by a realm, not {owner}")
    # (1) appended, never reordered; (8) named
    s = Settlement(id=len(w.settlements), name=name or _name(pol, people), kind=FIRST_KIND, x=int(x), y=int(y),
                   culture=people, population=max(1, int(population)), walled=False,
                   area=int(w.area[x, y]) if getattr(w, "area", None) is not None else -1)
    w.settlements.append(s)
    w.rebuild_index()
    # (2) its realm, in the ledger; (3) the territory
    pol.set_owner(s, holder.id)
    fx.touch(w)
    # (4) its people on the map
    _culture(w, s.x, s.y, people)
    # (6) the wilderness map built on its square goes (a town's is laid out there next time)
    w.local_maps.pop(local_key(s.x, s.y), None)
    # (7) its style
    styles(w)[str(s.id)] = STAGE_STYLES[0]
    w.politics.setdefault("founded", {})[str(s.id)] = int(pol.year)  # ("Founded in ..." on its Legends page)
    n = int(w.politics.get("next_founded", 0))
    w.politics["next_founded"] = n + 1
    rec = {"id": f"F{n}", "kind": kind, "settlement": s.id, "stage": 0, "since": float(pol.day),
           "staged": float(pol.day), "of": None if of is None else int(of)}
    if story is not None:
        rec["story"] = story
    records(w).append(rec)
    # (5) a road to the nearest road (the land's version moves on, so the painter draws it and the square repaints)
    if lay_road(w, pol.t, s, day=pol.day) is None:
        reshape._bump(w, {(s.x, s.y)}, {"road"})
    pol.changed = True
    return s


# ---------------------------------------------------------------------------- the first use: refugees
def refugee_camp(pol, target, besieger) -> object | None:
    """Some of a besieged town's people pitch a camp outside it, on the side away from the besiegers (a chance;
    towns and cities only; one camp a town at a time)."""
    from realmwalker.world import factions as fx

    sp = spec(pol.t).get("refugee_camp") or {}
    if not sp or target.kind not in sp.get("kinds", ("town", "city")):
        return None
    w = pol.w
    if any(r.get("of") == target.id and r["stage"] == 0 for r in records(w)):
        return None
    if sum(1 for r in records(w) if r["stage"] < len(STAGES) - 1) >= int(sp.get("most_camps", 6)):
        return None
    if not pol.rng.chance(float(sp.get("chance", 0.5))):
        return None
    realm = fx.top_liege(w, w.factions.get(target.owner))
    if realm is None or realm.kind not in fx.REALM_KINDS or not realm.active:
        return None
    seat = pol.place_of(besieger) if besieger is not None else None
    spot = spot_near(w, pol.t, target, away=seat, rng=pol.rng)
    if spot is None:
        return None
    people = max(int(sp.get("least", 40)), min(int(sp.get("most", 600)),
                                              int(target.population * float(sp.get("share", 0.08)))))
    people = min(people, max(1, target.population // 3))
    if people < int(sp.get("least", 40)):
        return None
    target.population = max(1, target.population - people)
    s = found(pol, *spot, kind="refugee_camp", people=target.culture, owner=realm.id, population=people, of=target.id)
    pol.say("camp_pitched", {"camp": s.name, "place": target.name, "attacker": besieger.name if besieger else "the enemy"},
            where=(s.x, s.y), importance=3, factions=[realm.id], places=[s.id, target.id])
    return s


# ---------------------------------------------------------------------------- growing
def weekly(pol) -> None:
    """Refugees go home when their town's siege lifts; camps that are left grow, fortify, and become villages."""
    w = pol.w
    sp = spec(pol.t)
    st = sp.get("stages") or {}
    home_share = float((sp.get("refugee_camp") or {}).get("home", 0.5))
    floor = int(st.get("floor", 30))
    for rec in records(w):
        sid = int(rec["settlement"])
        if not 0 <= sid < len(w.settlements):
            continue
        s = w.settlements[sid]
        stage = int(rec["stage"])
        of = w.settlements[rec["of"]] if rec.get("of") is not None and 0 <= rec["of"] < len(w.settlements) else None
        if rec["kind"] == "refugee_camp" and rec.get("home") is None and of is not None and \
                of.status.get("siege") is None and pol.day - float(rec["since"]) >= 7:
            back = min(s.population - floor, int(s.population * home_share))
            rec["home"] = float(pol.day)
            if back > 0:
                s.population -= back
                of.population += back
                pol.say("camp_home", {"camp": s.name, "place": of.name}, where=(s.x, s.y), importance=2,
                        places=[s.id, of.id])
                continue
        if rec["kind"] == "refugee_camp" and rec.get("home") is None:
            continue  # (while the siege lasts it is only a camp of the frightened)
        if stage < len(STAGES) - 1:
            s.population += max(1, int(s.population * float(st.get("growth", 0.01))))
        held = pol.day - float(rec["staged"])
        if stage == 0 and held >= float(st.get("fortified_days", 60)):
            set_stage(pol, rec, s, 1)
        elif stage == 1 and held >= float(st.get("town_days", 300)) and s.population >= int(st.get("town_people", 150)):
            set_stage(pol, rec, s, 2)


def set_stage(pol, rec: dict, s, stage: int) -> None:
    """The camp grows into its next stage (its map is laid out again at the next visit)."""
    w = pol.w
    rec["stage"] = int(stage)
    rec["staged"] = float(pol.day)
    if stage < len(STAGE_STYLES):
        styles(w)[str(s.id)] = STAGE_STYLES[stage]
    else:
        styles(w).pop(str(s.id), None)
    if stage >= 1:
        s.walled = True
    if stage >= 2:
        s.kind = TOWN_KIND
    realm = w.factions.get(s.owner)
    pol.say("camp_fortified" if stage == 1 else "camp_grown", {"camp": s.name}, where=(s.x, s.y),
            importance=2 if stage == 1 else 3, factions=[realm.id] if realm is not None else [], places=[s.id])


# ---------------------------------------------------------------------------- checks
def check(world, tables) -> list[str]:
    """What is wrong with the founded places (autoplay `_check_founded`)."""
    from realmwalker.world import factions as fx

    out = []
    seen = set()
    for rec in world.politics.get("foundings", ()):
        sid = int(rec.get("settlement", -1))
        if rec.get("kind") not in KINDS:
            out.append(f"a founded place of an unknown kind {rec.get('kind')!r}")
        if not 0 <= sid < len(world.settlements):
            out.append(f"founded {rec.get('id')} names no settlement ({sid})")
            continue
        if sid in seen:
            out.append(f"two founding records for one settlement ({sid})")
        seen.add(sid)
        s = world.settlements[sid]
        if s.id != sid:
            out.append(f"{s.name}'s id is {s.id}, but it stands at {sid} in the list")
        if not 0 <= int(rec.get("stage", -1)) < len(STAGES):
            out.append(f"{s.name} is at an unknown stage {rec.get('stage')}")
        elif int(rec["stage"]) < len(STAGE_STYLES) and style_of(world, s) != STAGE_STYLES[int(rec["stage"])]:
            out.append(f"{s.name} is a {STAGES[int(rec['stage'])]} laid out as {style_of(world, s)!r}")
        if s.population <= 0:
            out.append(f"{s.name}, founded, has no people")
        f = world.factions.get(s.owner)
        if f is None or f.kind not in fx.REALM_KINDS:
            out.append(f"{s.name}, founded, is held by something that is not a realm ({s.owner})")
        if world.settlement_grid[s.x, s.y] != sid:
            out.append(f"{s.name} is not on the map at its square")
    known = set((tables.towns or {}).get("styles", {})) if getattr(tables, "towns", None) else set()
    for sid, style in (world.politics.get("styles") or {}).items():
        if not str(sid).isdigit() or not 0 <= int(sid) < len(world.settlements):
            out.append(f"a town style for a settlement that does not exist ({sid})")
        elif known and style not in known:
            out.append(f"{world.settlements[int(sid)].name} is laid out in an unknown style {style!r}")
    return out
