"""Assaults: battles through a living town (Expansion 6 H.1, docs/ADVENTURES.md §5.20, §8.15). World layer (no game):
the record, its making and its abstract end. Driving it on the town's close-up map while the party is there is
game/assault.py.

When something falls on a town (a raid, a sack, the dead, a dragon, a summoner's portal) and the party stands on that
town's square or next to it (`politics["party_at"]`, threats... assaults.json `near`), the thing is not settled at
once: an assault record is made, with its clock of town minutes from now. Walk in before the clock runs out and it is
played on the map; otherwise it is resolved in the abstract when its time is past (`due`, from `Politics.advance` and
`hosts.advance_world`, so it ends in the interlude too) through `hosts.strike`, scaled by how it went (`resolve`).

A record is `world.politics["assaults"][str(settlement id)]` (one a town at a time) =
    {"id": "A<n>", "kind" (KINDS), "settlement", "strike" (the hosts.strike kind that resolves it), "threat", "adv",
     "since" (day), "clock" (town minutes), "phase" ("coming", then each wave's phase), "state" (STATES),
     "waves": [{"at" (minute), "phase", "in" (come in yet), "bands": [{"group", "entry", "goal", "leader",
                "state": "due" | "in" | "slain" | "gone", "actor" (its LocalActor id while in)}]}],
     "fire": {"at" (minute), "seeds", "since" (minute it was set, or None)} or None,
     "objectives": [] (H.4), "tally": {"dead": [...], "saved": [...], "burned": [...], "slain": n},
     "faction", "who", "group" (the attacker's own encounter group, or None), "strength", "figure", "also"}
and `politics["next_assault"]`.

    begin(world, tables, s, kind, day=, rng=, ...)   a record (or the one already there)
    party_near(world, tables, s)                     is the party close enough to walk into it
    minute(world, rec)                               town minutes since it began
    due(world, tables, day, rng)                     records past their time resolved
    resolve(world, tables, rec, day=, rng=, scale=)  its end in the abstract, through hosts.strike (news, marks,
                                                     losses scaled by `scale`, refugees)
    check(world, tables)                             what is wrong with the records (autoplay)
"""

from __future__ import annotations

KINDS = ("raid", "sack", "the_dead", "summoned", "dragon")
STATES = ("coming", "live")
WHO = {"raid": "the hills", "sack": "the enemy", "the_dead": "the grave", "summoned": "a summoner",
       "dragon": "a dragon"}  # (who they are, when nothing better is known)


def records(world) -> dict:
    return world.politics.setdefault("assaults", {})


def get(world, sid: int) -> dict | None:
    return (world.politics.get("assaults") or {}).get(str(int(sid)))


def spec(tables) -> dict:
    return getattr(tables, "assaults", None) or {}


def tier(tables, s) -> int:
    t = int(spec(tables).get("tiers", {}).get(s.kind, 1))
    if getattr(s, "great", False):
        t += 1
    return max(1, min(3, t))


def party_near(world, tables, s) -> bool:
    at = world.politics.get("party_at")
    if not at or not spec(tables).get("kinds"):
        return False
    return max(abs(int(at[0]) - s.x), abs(int(at[1]) - s.y)) <= int(spec(tables).get("near", 1))


def minute(world, rec: dict) -> float:
    return (world.time / 1440.0 - float(rec["since"])) * 1440.0


def begin(world, tables, s, kind: str, *, day: float, rng, faction: int = -1, who: str = "", group: str | None = None,
          strike: str | None = None, threat=None, adv=None, strength: int = 50, figure=None, also=()) -> dict | None:
    """An assault on `s` begins now (or at `day`, if that is later). None when assaults.json has no such kind."""
    k = spec(tables).get("kinds", {}).get(kind)
    if k is None:
        return None
    have = get(world, s.id)
    if have is not None:
        return have
    encounters = tables.creatures.encounters
    if group is not None and group not in encounters:
        group = None
    t = tier(tables, s)
    waves = []
    for w in k["waves"]:
        bands = []
        for b in w["bands"]:
            choices = [group if g == "$main" else g for g in b["group"] if g != "$main" or group]
            choices = [g for g in choices if g in encounters]
            if not choices:
                continue
            first = group if group in choices else None  # (the attacker's own come first, if they are named)
            for i in range(int(b["count"][t - 1])):
                g = first if first is not None and i == 0 else rng.choice(choices)
                bands.append({"group": g, "entry": b["entry"], "goal": b["goal"], "leader": bool(b.get("leader")),
                              "state": "due"})
        waves.append({"at": int(w["at"]), "phase": w["phase"], "in": False, "bands": bands})
    fire = None
    if k.get("fire") and int(k["fire"]["seeds"][t - 1]) > 0:
        lo, hi = k["fire"]["at"]
        fire = {"at": rng.randint(int(lo), int(hi)), "seeds": int(k["fire"]["seeds"][t - 1]), "since": None}
    lo, hi = k["clock"]
    n = int(world.politics.get("next_assault", 0))
    world.politics["next_assault"] = n + 1
    rec = {"id": f"A{n}", "kind": kind, "settlement": int(s.id), "strike": strike or k.get("strike", kind),
           "threat": threat, "adv": adv, "since": max(float(day), world.time / 1440.0),
           "clock": rng.randint(int(lo), int(hi)), "phase": "coming", "state": "coming", "waves": waves, "fire": fire,
           "objectives": [], "tally": {"dead": [], "saved": [], "burned": [], "slain": 0},
           "faction": int(faction), "who": who or WHO.get(kind, "raiders"), "group": group,
           "strength": max(1, int(strength)), "figure": figure, "also": list(also)}
    records(world)[str(int(s.id))] = rec
    return rec


def over_at(rec: dict, tables=None) -> float:
    """The day its clock runs out."""
    return float(rec["since"]) + float(rec["clock"]) / 1440.0


def due(world, tables, day: float, rng) -> list[str]:
    """Every assault whose time is past and that nobody is playing is resolved in the abstract. One being played
    (the party in the town) is the game's to end, unless it is long past its time (a save left mid-assault)."""
    if not world.politics.get("assaults"):
        return []
    late = float(spec(tables).get("late_days", 1))
    said = []
    for key, rec in list(records(world).items()):
        end = over_at(rec)
        if float(day) < end or (rec["state"] == "live" and float(day) < end + late):
            continue
        said += resolve(world, tables, rec, day=max(float(day), end), rng=rng.child(f"assault/{rec['id']}")
                        if hasattr(rng, "child") else rng, scale=_scale(rec))
    return said


def _scale(rec: dict) -> float:
    """How much of the harm is done, by how it went: every band slain spares the town some (a leader, more)."""
    bands = [b for w in rec["waves"] for b in w["bands"]]
    if not bands:
        return 1.0
    worth = sum(2.0 if b.get("leader") else 1.0 for b in bands)
    slain = sum(2.0 if b.get("leader") else 1.0 for b in bands if b.get("state") == "slain")
    return max(0.15, 1.0 - 0.8 * slain / worth)


def resolve(world, tables, rec: dict, *, day: float, rng, scale: float | None = None) -> list[str]:
    """The assault's end in the abstract: hosts.strike with its kind's losses and marks (scaled), news, refugees."""
    from realmwalker.world import hosts

    records(world).pop(str(int(rec["settlement"])), None)
    if not 0 <= int(rec["settlement"]) < len(world.settlements):
        return []
    s = world.settlements[int(rec["settlement"])]
    host = {"id": "H" + rec["id"][1:], "kind": rec.get("strike") or rec["kind"], "faction": int(rec.get("faction", -1)),
            "strength": int(rec.get("strength", 50)), "who": rec.get("who", ""), "also": list(rec.get("also", []))}
    if rec.get("threat"):
        host["threat"] = rec["threat"]
    if rec.get("figure") is not None:
        host["figure"] = rec["figure"]
    return hosts.strike(world, tables, host, s, day=day, rng=rng, scale=_scale(rec) if scale is None else scale,
                        live=False)


def check(world, tables) -> list[str]:
    out = []
    kinds = spec(tables).get("kinds", {})
    for key, rec in (world.politics.get("assaults") or {}).items():
        if key != str(rec.get("settlement")):
            out.append(f"assault {rec.get('id')} kept under {key} but on settlement {rec.get('settlement')}")
        if not 0 <= int(rec.get("settlement", -1)) < len(world.settlements):
            out.append(f"assault {rec.get('id')} on no settlement")
        if rec.get("kind") not in kinds:
            out.append(f"assault {rec.get('id')} of unknown kind {rec.get('kind')}")
        if rec.get("state") not in STATES:
            out.append(f"assault {rec.get('id')} in state {rec.get('state')}")
        for w in rec.get("waves", []):
            for b in w["bands"]:
                if b["group"] not in tables.creatures.encounters:
                    out.append(f"assault {rec.get('id')} band of unknown group {b['group']}")
                if b.get("state") not in ("due", "in", "slain", "gone"):
                    out.append(f"assault {rec.get('id')} band in state {b.get('state')}")
    return out
