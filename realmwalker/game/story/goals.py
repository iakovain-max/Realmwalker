"""The goal language (docs/ADVENTURES.md §8.10): what a situation's goals test, and how the game tells them it may be time.

A test is a list: `[name, arg, ...]`, combined with `["all", t, ...]`, `["any", t, ...]` and `["not", t]`:

    alive(r)  dead(r)  at(r, place)  with_party(r)  free(r)  holds(r, thing)  gone(r)  married(r, s)  owes(r, s)
    knows(r, truth)  law_state(r, state)  standing(faction, op, n)  status(place, mark)  cleared(place)
    faction_active(f)  flag(f)  day(op, n)

Who (`r`, `s`): "you" (the hero), a role of the situation (`sit["roles"][name]`: {"npc"}, {"figure"}, {"band"},
{"faction"}, {"place"}), or a record written in place ({"npc": 813}). A place: a role bound to a place, a place record
(story/places.py, and {"settlement", "building"} or {"settlement", "spot": [x, y]} for a building of its town map), or
a path of the forge: `home_of(r)`, `work_of(r)`, `town_of(r)`. A thing: an item kind, or a story item by its tag
("story:<id>"). What the predicates read, besides the world's own records: a band role's `state` (dead, taken, fled,
gone: set by `notify` from a fight's tags `{"situation", "role"}` and a captive's fate), `npc.flags` "captive" (held by
captors), "law" (accused, jailed, pardoned, hanged; the people ops of C.6 write it), "gone" (moved away for good),
"knows" (truths), "with_party"; the hero's truths `renown.flags["truths"]`, a situation's `flags` (codewords).

`problems(test, roles=None)` checks a test against the whitelist (story/check.py runs it at start-up on every goal the
data names). `notify(game, kind, way=None, **refs)` is the one call from the game: whenever something happens that
could make a goal true, the live situations within reach that listen to that kind of event (`listens`, worked out from
their goals) test their open goals, and a goal made true is kept with the way it was reached (`sit["ways"]`: talk,
pay, sneak, steal, force, fight, magic, law, favour, companion, wait). Ways are recognised, not scripted: whatever
made the predicate true counts, and an ending may ask how (`way_used`).

    test(game, sit, t) -> bool          problems(t, roles=None) -> [str]     listens(goals) -> [kind]
    notify(game, kind, way=None, **refs) -> [(qid, goal id, way)]          learn(game, who, truth, way="talk")
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# What happens in the game that a goal may hear of (the callers of `notify`).
EVENTS = ("talk", "battle", "captive", "law", "item", "town", "building", "party", "magic", "day")
# How a goal was reached (§8.10); an ending may test them (`way:<kind>`).
WAYS = ("talk", "pay", "sneak", "steal", "force", "fight", "magic", "law", "favour", "companion", "wait")
# The way an event stands for when its caller does not say.
DEFAULT_WAY = {"talk": "talk", "battle": "fight", "captive": "fight", "law": "law", "item": "pay", "town": "wait",
               "building": "wait", "party": "talk", "magic": "magic", "day": "wait"}
# The law's crimes as ways through (law.commit).
CRIME_WAYS = {"theft": "steal", "pickpocket": "steal", "smuggling": "sneak", "trespass": "sneak", "assault": "fight",
              "murder": "fight", "resisting_arrest": "fight", "fleeing_arrest": "force", "jailbreak": "force",
              "unlicensed_magic": "magic", "forbidden_magic": "magic", "poaching": "steal", "heresy": "law"}
LAW_STATES = ("free", "accused", "jailed", "pardoned", "hanged")
OPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
       ">=": lambda a, b: a >= b, ">": lambda a, b: a > b}
COMBINE = ("all", "any", "not")
LIVE = ("latent", "met", "taken")
PATHS = ("home_of", "work_of", "town_of")
BAND_GONE = ("dead", "taken", "fled", "gone")  # a band role's states that are not "still about"
_PATH = re.compile(r"^(\w+)\((\w+)\)$")


@dataclass
class Pred:
    fn: object
    args: tuple  # the kind of each argument: who, place, thing, word, faction, op, int, law, day
    listens: tuple  # the events that may change it


PREDICATES: dict[str, Pred] = {}


def predicate(name: str, args: tuple, listens: tuple):
    """Register a predicate: fn(game, sit, *args) -> bool."""
    def wrap(fn):
        PREDICATES[name] = Pred(fn, args, listens)
        return fn
    return wrap


# ---------------------------------------------------------------------------- the records
def situations(world) -> dict:
    return world.politics.setdefault("situations", {})


def live(game) -> list[dict]:
    return [s for _, s in sorted(situations(game.world).items()) if s.get("state") in LIVE]


def within_reach(game, sit: dict) -> bool:
    """A situation's town within the reach of life events (lives.json `reach`); one with no town is always near."""
    sid = sit.get("town")
    w = game.world
    if sid is None or not 0 <= int(sid) < len(w.settlements):
        return True
    from realmwalker.game.story import lives

    s = w.settlements[int(sid)]
    reach = int((lives.data(game) or {}).get("reach", 30))
    return max(abs(s.x - game.player.x), abs(s.y - game.player.y)) <= reach


def _today(game) -> int:
    return int(game.moment.total_days)


# ---------------------------------------------------------------------------- what a name stands for
def who(game, sit: dict, ref):
    """("you", None) | ("npc", NPC) | ("figure", Figure) | ("band", role record) | ("faction", Faction) | (None, None)."""
    rec = ref
    if isinstance(ref, str):
        if ref in ("you", "hero"):
            return "you", None
        rec = (sit.get("roles") or {}).get(ref)
    if not isinstance(rec, dict):
        return None, None
    w = game.world
    if rec.get("npc") is not None:
        return "npc", w.npcs.get(int(rec["npc"]))
    if rec.get("figure") is not None:
        return "figure", w.figures.get(int(rec["figure"]))
    if rec.get("band") is not None:
        return "band", rec
    if rec.get("faction") is not None:
        return "faction", w.factions.get(int(rec["faction"]))
    return None, None


def place(game, sit: dict, ref) -> dict | None:
    """A place record for a place argument (see the module's docstring), or None."""
    if isinstance(ref, dict):
        return ref.get("place") if isinstance(ref.get("place"), dict) else ref
    if not isinstance(ref, str):
        return None
    m = _PATH.match(ref)
    if m is None:
        rec = (sit.get("roles") or {}).get(ref)
        return place(game, sit, rec) if isinstance(rec, dict) and "place" in rec else None
    kind, npc = who(game, sit, m.group(2))
    if kind != "npc" or npc is None:
        return None
    if m.group(1) == "town_of":
        return {"settlement": int(npc.settlement)}
    if m.group(1) == "home_of":
        return {"settlement": int(npc.settlement), "spot": [int(npc.home[0]), int(npc.home[1])]}
    if npc.building < 0:
        return {"settlement": int(npc.settlement), "spot": [int(npc.post[0]), int(npc.post[1])]}
    return {"settlement": int(npc.settlement), "building": int(npc.building)}


def _town_map(game, sid: int):
    from realmwalker.world.local import local_key

    s = game.world.settlements[sid]
    return game.world.local_maps.get(local_key(s.x, s.y))


def _in_part(game, pl: dict, lm, x: int, y: int) -> bool:
    """(x, y) on a town's map is inside the building (or the inn, or at the spot) a place names."""
    if lm is None:
        return False
    if "building" in pl:
        b = lm.building_at(x, y)
        return b is not None and 0 <= int(pl["building"]) < len(lm.buildings) and b is lm.buildings[int(pl["building"])]
    if "spot" in pl:
        sx, sy = pl["spot"]
        b = lm.building_at(int(sx), int(sy))
        return b.contains(x, y) if b is not None else (x, y) == (int(sx), int(sy))
    if pl.get("part") == "inn":
        b = lm.building_at(x, y)
        return b is not None and b.kind == "inn"
    return True


def _thing_matches(it, thing: str) -> bool:
    return it.def_id == thing or thing in (it.tags or [])


def _npc_gone(sit: dict, npc) -> bool:
    if not npc.alive:
        return False
    if npc.flags.get("gone") or npc.flags.get("moved_on"):
        return True
    return sit.get("town") is not None and int(npc.settlement) != int(sit["town"])


def _held(npc) -> bool:
    return bool(npc.flags.get("captive")) or npc.flags.get("law") in ("jailed", "hanged")


def _with_party(game, npc) -> bool:
    if npc.flags.get("with_party"):
        return True
    if any((c.companion or {}).get("npc") == npc.id for c in game.party[1:]):
        return True
    q = npc.flags.get("escort")
    return q is not None and any(x.get("id") == q and not x.get("done") for x in game.quests)


def _life(npc) -> dict:
    return npc.flags.get("life") or {}


def _tied(npc, kinds: tuple, other) -> bool:
    for t in _life(npc).get("ties", []):
        if t["kind"] in kinds and t.get("state", "alive") == "alive" and (
                t.get("npc") == other.id or (t.get("npc") is None and t.get("name") == other.name)):
            return True
    return False


# ---------------------------------------------------------------------------- the predicates
def _alive(game, sit, r) -> bool | None:
    kind, x = who(game, sit, r)
    if kind == "you":
        return game.over is None
    if kind == "npc" and x is not None:
        return bool(x.alive) and x.flags.get("law") != "hanged"
    if kind == "figure" and x is not None:
        return bool(x.alive)
    if kind == "band":
        return x.get("state") != "dead"
    if kind == "faction" and x is not None:
        return bool(x.active)
    return None


@predicate("alive", ("who",), ("battle", "captive", "law", "day", "talk"))
def p_alive(game, sit, r) -> bool:
    return bool(_alive(game, sit, r))


@predicate("dead", ("who",), ("battle", "captive", "law", "day", "talk"))
def p_dead(game, sit, r) -> bool:
    return _alive(game, sit, r) is False


@predicate("at", ("who", "place"), ("town", "building", "day", "talk", "party"))
def p_at(game, sit, r, where) -> bool:
    pl = place(game, sit, where)
    if pl is None:
        return False
    kind, x = who(game, sit, r)
    w = game.world
    if kind == "you":
        p = game.player
        if "site" in pl or "tile" in pl:
            from realmwalker.game.story import places

            return places.here(game, pl)
        if "settlement" not in pl:
            return False
        s = w.settlement_at(p.x, p.y)
        if s is None or s.id != int(pl["settlement"]):
            return False
        if not any(k in pl for k in ("building", "spot", "part")):
            return True
        return bool(game.in_local) and game.local is not None and game.local.kind == "settlement" and \
            _in_part(game, pl, game.local, p.lx, p.ly)
    if kind == "npc" and x is not None:
        if not x.alive or _held(x) or x.flags.get("gone") or x.flags.get("moved_on") or _with_party(game, x):
            return False
        if "settlement" not in pl or int(x.settlement) != int(pl["settlement"]):
            return False
        if not any(k in pl for k in ("building", "spot", "part")):
            return True
        return x.present and _in_part(game, pl, _town_map(game, int(pl["settlement"])), x.x, x.y)
    if kind == "figure" and x is not None and x.alive:
        home = getattr(x, "home", "") or ""
        return ("settlement" in pl and home == f"S{int(pl['settlement'])}") or \
            ("site" in pl and home == f"X{int(pl['site'])}")
    return False


@predicate("with_party", ("who",), ("talk", "party", "captive", "battle", "day"))
def p_with_party(game, sit, r) -> bool:
    kind, x = who(game, sit, r)
    if kind == "you":
        return True
    if kind == "npc" and x is not None:
        return x.alive and _with_party(game, x)
    if kind == "band":
        return x.get("state") == "taken"
    return False


@predicate("free", ("who",), ("captive", "law", "talk", "battle", "day"))
def p_free(game, sit, r) -> bool:
    kind, x = who(game, sit, r)
    if kind == "you":
        return getattr(game, "sentence", None) is None and getattr(game, "arrest", None) is None
    if kind == "npc" and x is not None:
        return x.alive and not _held(x)
    if kind == "band":
        return x.get("state") not in ("dead", "taken")
    if kind == "figure" and x is not None:
        return x.alive
    return False


@predicate("holds", ("who", "thing"), ("item", "battle", "talk", "day"))
def p_holds(game, sit, r, thing) -> bool:
    kind, x = who(game, sit, r)
    if kind == "you":
        return any(_thing_matches(it, thing) for c in game.party for it in c.inventory)
    if kind == "npc" and x is not None:
        return any(_thing_matches(it, thing) for it in x.inventory)
    return False


@predicate("gone", ("who",), ("day", "talk", "law", "battle", "captive"))
def p_gone(game, sit, r) -> bool:
    kind, x = who(game, sit, r)
    if kind == "npc" and x is not None:
        return _npc_gone(sit, x)
    if kind == "band":
        return x.get("state") in ("fled", "gone")
    return False


@predicate("married", ("who", "who"), ("day", "talk"))
def p_married(game, sit, r, s) -> bool:
    ka, a = who(game, sit, r)
    kb, b = who(game, sit, s)
    if ka != "npc" or kb != "npc" or a is None or b is None or not (a.alive and b.alive):
        return False
    return _tied(a, ("husband", "wife"), b) or _tied(b, ("husband", "wife"), a)


@predicate("owes", ("who", "who"), ("day", "talk", "item"))
def p_owes(game, sit, r, s) -> bool:
    ka, a = who(game, sit, r)
    kb, b = who(game, sit, s)
    if kb != "npc" or b is None:
        return False
    if ka == "you":
        return any(int(d.get("to", -1)) == b.id and not d.get("paid")
                   for d in game.renown.flags.get("debts", []))
    if ka != "npc" or a is None or not a.alive:
        return False
    return _tied(a, ("creditor",), b)


@predicate("knows", ("who", "word"), ("talk", "magic", "day"))
def p_knows(game, sit, r, truth) -> bool:
    kind, x = who(game, sit, r)
    if kind == "you":
        return truth in game.renown.flags.get("truths", [])
    if kind == "npc" and x is not None:
        return x.alive and truth in x.flags.get("knows", [])
    return False


@predicate("law_state", ("who", "law"), ("law", "talk", "day"))
def p_law_state(game, sit, r, state) -> bool:
    kind, x = who(game, sit, r)
    if kind == "you":
        now = "free"
        if getattr(game, "sentence", None) is not None:
            now = "jailed"
        elif any(c.get("reported") and not c.get("settled") for c in game.renown.crimes):
            now = "accused"
        elif game.renown.flags.get("pardoned"):
            now = "pardoned"
        return now == state
    if kind == "npc" and x is not None:
        return x.flags.get("law", "free") == state
    return False


def _faction(game, sit, ref):
    if isinstance(ref, int):
        return game.world.factions.get(ref)
    kind, x = who(game, sit, ref)
    return x if kind == "faction" else None


@predicate("standing", ("faction", "op", "int"), ("talk", "battle", "law", "item", "day"))
def p_standing(game, sit, f, op, n) -> bool:
    fac = _faction(game, sit, f)
    if fac is None:
        return False
    from realmwalker.game import reputation

    return OPS[op](reputation.standing(game, fac.id), int(n))


@predicate("status", ("place", "word"), ("day", "town"))
def p_status(game, sit, where, mark) -> bool:
    pl = place(game, sit, where)
    if pl is None or "settlement" not in pl:
        return False
    from realmwalker.world import marks

    return mark in marks.marks_of(game.world.settlements[int(pl["settlement"])])


@predicate("cleared", ("place",), ("battle", "day"))
def p_cleared(game, sit, where) -> bool:
    pl = place(game, sit, where)
    return pl is not None and "site" in pl and int(pl["site"]) in game.world.politics.get("cleared", [])


@predicate("faction_active", ("faction",), ("day", "battle"))
def p_faction_active(game, sit, f) -> bool:
    fac = _faction(game, sit, f)
    return fac is not None and fac.active


@predicate("flag", ("word",), ("talk", "day", "magic", "item", "battle"))
def p_flag(game, sit, f) -> bool:
    if f in sit.get("flags", []):
        return True
    adv = game.world.politics.get("adventures", {}).get(sit.get("adventure")) if sit.get("adventure") else None
    return adv is not None and f in adv.get("flags", [])


@predicate("day", ("op", "day"), ("day",))
def p_day(game, sit, op, n) -> bool:
    if n == "clock":
        n = (sit.get("clock") or {}).get("due")
        if n is None:
            return False
    return OPS[op](_today(game), int(n))


# ---------------------------------------------------------------------------- testing
def test(game, sit: dict, t) -> bool:
    name = t[0]
    if name == "all":
        return all(test(game, sit, x) for x in t[1:])
    if name == "any":
        return any(test(game, sit, x) for x in t[1:])
    if name == "not":
        return not test(game, sit, t[1])
    return bool(PREDICATES[name].fn(game, sit, *t[1:]))


def _arg_problem(kind: str, a, roles) -> str | None:
    if kind == "who":
        if isinstance(a, dict):
            return None if any(k in a for k in ("npc", "figure", "band", "faction")) else f"{a} names nobody"
        if not isinstance(a, str):
            return f"{a!r} is not a role"
        if a in ("you", "hero") or roles is None or a in roles:
            return None
        return f"'{a}' is not a role of this situation"
    if kind == "place":
        if isinstance(a, dict):
            return None if any(k in a for k in ("site", "settlement", "tile", "place")) else f"{a} is not a place"
        if not isinstance(a, str):
            return f"{a!r} is not a place"
        m = _PATH.match(a)
        if m is not None:
            if m.group(1) not in PATHS:
                return f"'{m.group(1)}(...)' is not a path the game knows"
            return _arg_problem("who", m.group(2), roles)
        return None if roles is None or a in roles else f"'{a}' is not a place of this situation"
    if kind == "faction":
        return None if isinstance(a, int) or _arg_problem("who", a, roles) is None else f"{a!r} is not a faction"
    if kind in ("thing", "word"):
        return None if isinstance(a, str) and a else f"{a!r} is not a word"
    if kind == "op":
        return None if a in OPS else f"'{a}' is not a comparison ({', '.join(OPS)})"
    if kind == "int":
        return None if isinstance(a, int) and not isinstance(a, bool) else f"{a!r} is not a number"
    if kind == "law":
        return None if a in LAW_STATES else f"'{a}' is not a state of the law ({', '.join(LAW_STATES)})"
    if kind == "day":
        return None if a == "clock" or (isinstance(a, int) and not isinstance(a, bool)) else \
            f"{a!r} is not a day (a number or 'clock')"
    return f"the argument kind '{kind}' is unknown"


def problems(t, roles=None, where: str = "goal") -> list[str]:
    """What is wrong with a test, in friendly lines ([] when nothing). `roles`: the role names it may use, or None."""
    if not isinstance(t, list) or not t or not isinstance(t[0], str):
        return [f"{where}: {t!r} is not a test (a list beginning with a predicate's name)."]
    name = t[0]
    if name in ("all", "any"):
        if len(t) < 2:
            return [f"{where}: '{name}' needs at least one test."]
        return [p for x in t[1:] for p in problems(x, roles, where)]
    if name == "not":
        if len(t) != 2:
            return [f"{where}: 'not' takes one test."]
        return problems(t[1], roles, where)
    pred = PREDICATES.get(name)
    if pred is None:
        return [f"{where}: the predicate '{name}' is not one the game knows."]
    if len(t) - 1 != len(pred.args):
        return [f"{where}: '{name}' takes {len(pred.args)} argument(s), not {len(t) - 1}."]
    out = []
    for kind, a in zip(pred.args, t[1:]):
        why = _arg_problem(kind, a, roles)
        if why:
            out.append(f"{where}: in '{name}', {why}.")
    return out


def self_problems() -> list[str]:
    """The language's own consistency (story/check.py): every predicate hears only events the game sends."""
    out = []
    for name, pred in PREDICATES.items():
        for kind in pred.listens:
            if kind not in EVENTS:
                out.append(f"goals: the predicate '{name}' listens to '{kind}', which nothing sends.")
    for kind, way in DEFAULT_WAY.items():
        if kind not in EVENTS or way not in WAYS:
            out.append(f"goals: the default way of '{kind}' ('{way}') is not a known event and way.")
    for crime, way in CRIME_WAYS.items():
        if way not in WAYS:
            out.append(f"goals: the crime '{crime}' stands for '{way}', which is not a way.")
    return out


def data_problems(tables) -> list[str]:
    """Every goal the data names (situations.json predicaments: `roles` and `goals` [{id, test}]) reads right."""
    out = []
    for pid, pred in (getattr(tables, "situations", None) or {}).get("predicaments", {}).items():
        if pid.startswith("_") or not isinstance(pred, dict):
            continue
        roles = set(pred.get("roles", {})) | set(pred.get("places", {}))
        for g in pred.get("goals", []):
            out.extend(problems(g.get("test"), roles, f"situations.json: {pid}, goal {g.get('id', '?')}"))
    return out


def names(t) -> set[str]:
    """The predicates a test uses."""
    if t[0] in COMBINE:
        return set().union(*(names(x) for x in t[1:]))
    return {t[0]}


def listens(goals: list[dict]) -> list[str]:
    """The events a situation's goals may hear of (kept as `sit["listens"]` when it is forged)."""
    kinds = set()
    for g in goals:
        for name in names(g["test"]):
            kinds.update(PREDICATES[name].listens)
    return [k for k in EVENTS if k in kinds]


# ---------------------------------------------------------------------------- listening
def _mark_bands(game, kind: str, refs: dict) -> None:
    """A fight's tagged foes, and a captive's fate, settle the band roles they stand for."""
    found = []
    if kind == "battle" and refs.get("result") is not None:
        r = refs["result"]
        found = [(c, "dead") for c in r.dead] + [(c, "taken") for c in getattr(r, "captives", [])] + \
            [(c, "fled") for c in getattr(r, "fled", [])]
    elif kind == "captive" and refs.get("creature") is not None:
        state = {"execute": "dead", "capture": "taken", "spare": "gone", "rob": "gone"}.get(refs.get("fate", ""))
        if state:
            found = [(refs["creature"], state)]
    sits = situations(game.world)
    for c, state in found:
        tag = getattr(c, "story", None) or {}
        sit = sits.get(tag.get("situation"))
        rec = (sit or {}).get("roles", {}).get(tag.get("role"))
        if isinstance(rec, dict) and rec.get("band") is not None and rec.get("state") != "dead":
            rec["state"] = state


def notify(game, kind: str, way: str | None = None, **refs) -> list[tuple[str, str, str]]:
    """Something happened that may make a goal true: test the live situations within reach that listen to it.
    Returns (situation, goal, way) for every goal reached now."""
    if kind not in EVENTS:
        raise ValueError(f"goals.notify: unknown event kind '{kind}'")
    sits = situations(game.world)
    if not sits:
        return []
    way = way or DEFAULT_WAY[kind]
    _mark_bands(game, kind, refs)
    out = []
    today = _today(game)
    for sit in live(game):
        if "listens" not in sit:
            sit["listens"] = listens(sit.get("goals", []))
        if kind not in sit["listens"] or not within_reach(game, sit):
            continue
        for g in sit.get("goals", []):
            if g.get("reached") is not None or not test(game, sit, g["test"]):
                continue
            g["reached"] = today
            g["way"] = way
            sit.setdefault("ways", []).append({"goal": g["id"], "way": way, "day": today, "by": kind})
            out.append((sit["id"], g["id"], way))
    for qid, gid, w in out:
        for fn in REACTIONS:
            fn(game, sits[qid], gid, w)
    return out


REACTIONS: list = []  # fn(game, sit, goal id, way): what follows a goal reached (situations.py, C.6)


def way_used(sit: dict, way: str, goal: str | None = None) -> bool:
    """An ending's `way:<kind>`: a goal (or any) was reached that way."""
    return any(w["way"] == way and (goal is None or w["goal"] == goal) for w in sit.get("ways", []))


def learn(game, ref, truth: str, way: str = "talk", sit: dict | None = None) -> list:
    """Someone comes to know a truth (the hero by default when `ref` is "you"); then the goals hear of it."""
    if ref in ("you", "hero"):
        known = game.renown.flags.setdefault("truths", [])
    else:
        npc = ref if hasattr(ref, "flags") else who(game, sit or {}, ref)[1]
        if npc is None:
            return []
        known = npc.flags.setdefault("knows", [])
    if truth not in known:
        known.append(truth)
    return notify(game, "magic" if way == "magic" else "talk", way)


def talk_way(conv) -> str:
    """The way a conversation stands for: paid (a bribe taken), magic (a charmed or enthralled listener), or talk."""
    if getattr(conv, "paid", False):
        return "pay"
    from realmwalker.game import glamour

    if glamour.charmed(conv.game, conv.npc) or conv.npc.flags.get("enthralled_until", -1) > conv.game.world.time:
        return "magic"
    return "talk"
