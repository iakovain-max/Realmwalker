"""An assault played on a town's close-up map (Expansion 6 H.1, docs/ADVENTURES.md §5.20, §8.15). The record and its
abstract end are world/assaults.py; this drives it while the party is in the town.

    on_enter(game, lm, s)   walking into a town under assault (from GameState.enter_local): it goes live, and what
                            has happened by now is laid out at once (the waves already in, the fire already set)
    notice(game, lm)        an assault begun while you stand in the town (from pass_time, after politics, and the
                            debug console): it goes live
    tick(game, lm, s)       one step of the town's time (townlife.tick): waves come in at their minute as bands
                            (`LocalActor`s with new ids and a `goal`), the fire is set, the bands take a step towards
                            their goals, slain bands are counted, and it ends when its leader falls or its clock runs out
    settle(game, lm)        the minutes that passed in a wait, a talk or a fight, at once (townlife.settle)
    left(game, lm)          leaving the town mid-assault (GameState.leave_local): it goes on without you, and its
                            end is resolved in the abstract when its time is out (world/assaults.due)
    bands(game, lm)         the assault's bands on this map

A band's goal: [x, y] (the square, the temple's or the keep's door, a gate), "folk" (the nearest townsperson, chosen
afresh as they move) or "you" (it hunts you from the start: `alert`). Bands notice you as any band does
(encounters.move_actors) and a band that reaches you is fought as now. What they do when they reach folk, and the
defenders, are H.2; the fights' reinforcements H.3; objectives H.4; the aftermath's tallies and marks H.5.
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.world import assaults

STEPS_A_MINUTE = 10  # (townlife.STEP_SECONDS: six seconds a step)
MOST_STEPS = 600  # a jump of time walks a band at most this far along its way
FAR = 6  # a band does not come in within this many squares of you
REPATH = 8  # steps before a band hunting folk looks again for the nearest
_paths: dict = {}  # (map key, actor id) -> (target, [steps]): kept while the map is, not saved


def _rec(game, lm):
    from realmwalker.game.people import settlement_of

    s = settlement_of(game, lm)
    return (s, assaults.get(game.world, s.id)) if s is not None else (None, None)


def bands(game, lm) -> list:
    _, rec = _rec(game, lm)
    if rec is None:
        return []
    ids = {b.get("actor") for w in rec["waves"] for b in w["bands"] if b["state"] == "in"}
    return [a for a in lm.actors if a.id in ids]


def _words(game, key: str, rec: dict, s, **more) -> str:
    w = assaults.spec(game.tables).get("words", {})
    lines = w.get(key)
    if isinstance(lines, dict):
        lines = lines.get(rec["kind"])
    if not lines:
        return ""
    rng = game.world.rng.child(f"assault-words/{rec['id']}/{key}/{game.world.time}")
    values = {"town": textgen.escape_markup(s.name), **more}
    return textgen.fill(rng.choice(lines), rng, {}, values)


def _say(game, text: str) -> None:
    if text:
        game.say(text, "danger")


PHASES = {"coming": "it begins", "first_wave": "the first wave", "second_wave": "the second wave",
          "third_wave": "the third wave", "leader": "their leader is in"}
KIND_WORDS = {"raid": "Raiders in the town", "sack": "The town is being sacked", "the_dead": "The dead in the streets",
              "summoned": "Devils loose in the town", "dragon": "A dragon over the town"}


def panel_line(game, lm) -> str:
    """The side panel's line while the town is under assault: what, how far on, how long it may last."""
    _, rec = _rec(game, lm)
    if rec is None or rec["state"] != "live":
        return ""
    left = max(0, int(round(float(rec["clock"]) - assaults.minute(game.world, rec))))
    n = len(bands(game, lm))
    return (f"<danger>{KIND_WORDS.get(rec['kind'], 'The town is attacked')}</> <dim>({PHASES.get(rec['phase'], '')}; "
            f"{n} band{'s' if n != 1 else ''} in; about {left} min)</>")


# ---------------------------------------------------------------------------- going live
def on_enter(game, lm, s) -> None:
    rec = assaults.get(game.world, s.id) if s is not None else None
    if rec is None:
        _clear(game, lm)
        return
    if rec["state"] != "live":
        late = assaults.minute(game.world, rec) > 3
        rec["state"] = "live"
        _say(game, _words(game, "arrive" if late else "begin", rec, s))
        game.cue("horn")
    _run(game, lm, s, rec, jump=True)


def notice(game, lm) -> None:
    s, rec = _rec(game, lm)
    if rec is None or rec["state"] == "live" or game.local is not lm:
        return
    rec["state"] = "live"
    _say(game, _words(game, "begin", rec, s))
    game.cue("horn")
    _run(game, lm, s, rec, jump=True)


def left(game, lm) -> None:
    s, rec = _rec(game, lm)
    if rec is None or rec["state"] != "live":
        return
    rec["state"] = "coming"  # (it goes on; world/assaults.due ends it when its time is out)
    _say(game, _words(game, "left", rec, s))


# ---------------------------------------------------------------------------- the town's time
def tick(game, lm, s) -> None:
    rec = assaults.get(game.world, s.id)
    if rec is None or rec["state"] != "live" or game.local is not lm:
        return
    _run(game, lm, s, rec, jump=False)


def settle(game, lm, seconds: int | None = None) -> None:
    """Time jumped (a wait, a talk, a fight's minutes): the assault is where it would be by now."""
    s, rec = _rec(game, lm)
    if s is None:
        return
    if rec is None:
        _clear(game, lm)
        return
    if rec["state"] != "live" or game.local is not lm:
        return
    _run(game, lm, s, rec, jump=True)


def _clear(game, lm) -> None:
    """Bands of an assault that ended while you were away have gone."""
    if any(a.goal is not None for a in lm.actors):
        keep = getattr(game, "battle_actor", None)
        lm.actors[:] = [a for a in lm.actors if a.goal is None or a is keep]


def _run(game, lm, s, rec: dict, *, jump: bool) -> None:
    m = assaults.minute(game.world, rec)
    ran = float(rec.get("ran", 0.0))
    steps = 1 if not jump else max(0, min(MOST_STEPS, int((m - ran) * STEPS_A_MINUTE)))
    rec["ran"] = max(ran, m)
    if _count_slain(game, lm, rec):
        _end(game, lm, s, rec, broken=True)
        return
    if steps:
        _walk(game, lm, rec, steps)  # (those already in; a wave coming in now walks only its own time)
    for w in rec["waves"]:
        if not w["in"] and m >= w["at"]:
            _enter(game, lm, s, rec, w, steps=min(MOST_STEPS, int(max(0.0, m - w["at"]) * STEPS_A_MINUTE))
                   if jump else 0)
    fire = rec.get("fire")
    if fire and fire.get("since") is None and m >= fire["at"]:
        _set_fire(game, lm, s, rec)
    if m >= float(rec["clock"]):
        _end(game, lm, s, rec, broken=False)


def _count_slain(game, lm, rec: dict) -> bool:
    """Bands no longer on the map were slain (a fight's end takes a beaten band off it). True: the leader is down."""
    ids = {a.id for a in lm.actors}
    keep = getattr(game, "battle_actor", None)
    broken = False
    for w in rec["waves"]:
        for b in w["bands"]:
            if b["state"] == "in" and b.get("actor") not in ids and (keep is None or keep.id != b.get("actor")):
                b["state"] = "slain"
                rec["tally"]["slain"] = int(rec["tally"].get("slain", 0)) + 1
                broken = broken or bool(b.get("leader"))
    return broken


# ---------------------------------------------------------------------------- waves
def _town(game, lm):
    from realmwalker.game import townlife

    return townlife.town_for(game, lm)


def _entries(game, lm, town, entry: str) -> list[tuple[int, int]]:
    """Where a band may come in: inside a gate, at the edge of the town, or in its square (a portal)."""
    if entry == "portal":
        return list(town.square)
    if entry == "gate":
        from realmwalker.game.people import _gate_posts

        gates = _gate_posts(game, lm, town.walk)
        if gates:
            return gates
    w, h = town.walk.shape
    edge = sorted(town.streets, key=lambda c: min(c[0], c[1], w - 1 - c[0], h - 1 - c[1]))
    return edge[:max(8, len(edge) // 12)]


def _goal_cell(game, lm, town, goal: str, rng):
    if goal in ("folk", "you"):
        return goal
    if goal in ("temple", "keep"):
        kinds = ("temple",) if goal == "temple" else ("keep", "hall")
        doors = [b.door for b in lm.buildings if b.kind in kinds and b.door is not None]
        if doors:
            d = rng.choice(doors)
            return [int(d[0]), int(d[1])]
    if goal == "gate":
        from realmwalker.game.people import _gate_posts

        gates = _gate_posts(game, lm, town.walk)
        if gates:
            g = rng.choice(gates)
            return [int(g[0]), int(g[1])]
    c = rng.choice(list(town.square))
    return [int(c[0]), int(c[1])]


def _taken(game, lm) -> set:
    from realmwalker.game.people import npcs_in, settlement_of

    out = {(a.x, a.y) for a in lm.actors}
    if game.local is lm:
        out.add((game.player.lx, game.player.ly))
    s = settlement_of(game, lm)
    if s is not None:
        out |= {(n.x, n.y) for n in npcs_in(game.world, s.id) if n.alive and n.present}
    return out


def _enter(game, lm, s, rec: dict, wave: dict, *, steps: int) -> None:
    from realmwalker.game.encounters import LocalActor, new_id
    from realmwalker.rules.creatures import spawn_group

    wave["in"] = True
    rec["phase"] = wave["phase"]
    town = _town(game, lm)
    rng = game.world.rng.child(f"assault/{rec['id']}/{wave['at']}")
    taken = _taken(game, lm)
    me = (game.player.lx, game.player.ly) if game.local is lm else (-99, -99)
    said = set()
    for i, b in enumerate(wave["bands"]):
        if b["state"] != "due":
            continue
        cells = [c for c in _entries(game, lm, town, b["entry"]) if c not in taken]
        far = [c for c in cells if max(abs(c[0] - me[0]), abs(c[1] - me[1])) >= FAR]
        cells = far or cells
        if not cells:
            b["state"] = "gone"  # (nowhere to come in: they never come)
            continue
        x, y = rng.choice(cells)
        creatures = spawn_group(game.tables, b["group"], rng.child(f"band{i}"), now=game.world.time,
                                party_size=len(game.party))
        if not creatures:
            b["state"] = "gone"
            continue
        a = LocalActor(new_id(lm), b["group"], int(x), int(y), creatures)
        a.goal = _goal_cell(game, lm, town, b["goal"], rng)
        a.alert = a.goal == "you"
        lm.actors.append(a)
        taken.add((a.x, a.y))
        b["state"] = "in"
        b["actor"] = a.id
        if steps:
            _walk(game, lm, rec, steps, only=a)
        if rec.get("ran", 0) > 0 or wave["at"] > 0:
            said.add(b["entry"])
    if game.local is lm:
        names = assaults.spec(game.tables).get("words", {}).get("entries", {})
        for entry in sorted(said):
            _say(game, _words(game, "wave", rec, s, entry=names.get(entry, entry)))


def _set_fire(game, lm, s, rec: dict) -> None:
    """The attackers set the town alight about where they are."""
    from realmwalker.game import fire

    fire_rec = rec["fire"]
    fire_rec["since"] = round(assaults.minute(game.world, rec), 1)
    rng = game.world.rng.child(f"assault/{rec['id']}/fire")
    spots = [(a.x, a.y) for a in bands(game, lm)] or [tuple(c) for c in _town(game, lm).square[:1]]
    lit = 0
    for _ in range(int(fire_rec["seeds"]) * 6):
        if lit >= int(fire_rec["seeds"]):
            break
        x0, y0 = rng.choice(spots)
        x, y = x0 + rng.randint(-5, 5), y0 + rng.randint(-5, 5)
        if lm.in_bounds(x, y) and fire.burns(game, lm, x, y):
            lit += fire.light(game, lm, [(x, y)])
    if lit and game.local is lm:
        _say(game, _words(game, "fire", rec, s, entry="square"))


# ---------------------------------------------------------------------------- walking
def _target(game, lm, a) -> tuple[int, int] | None:
    if isinstance(a.goal, (list, tuple)):
        return int(a.goal[0]), int(a.goal[1])
    if a.goal == "folk":
        from realmwalker.game.people import npcs_in, settlement_of

        s = settlement_of(game, lm)
        folk = [n for n in npcs_in(game.world, s.id) if n.alive and n.present] if s is not None else []
        if not folk:
            return None
        n = min(folk, key=lambda n: (max(abs(n.x - a.x), abs(n.y - a.y)), n.id))
        return int(n.x), int(n.y)
    return None


def _walk(game, lm, rec: dict, steps: int, only=None) -> None:
    """Every band not hunting you takes `steps` steps towards its goal (a jump of time: all at once)."""
    town = _town(game, lm)
    taken = _taken(game, lm)
    for a in [only] if only is not None else bands(game, lm):
        if a.alert or a.goal is None or a is getattr(game, "battle_actor", None):
            continue
        key = (lm.key, a.id)
        want = _target(game, lm, a)
        if want is None:
            continue
        have = _paths.get(key)
        if have is None or have[0] != want or not have[1] or have[2] <= 0:
            path = town.path((a.x, a.y), want) if town.walk[a.x, a.y] else []
            have = (want, path, REPATH if a.goal == "folk" else 10 ** 6)
        want, path, fresh = have
        moved = 0
        while path and moved < steps:
            nx, ny = path[0]
            if (nx, ny) in taken:
                break  # (someone in the way: it waits, or finds another way next time)
            taken.discard((a.x, a.y))
            a.x, a.y = nx, ny
            taken.add((a.x, a.y))
            path = path[1:]
            moved += 1
        _paths[key] = (want, path, fresh - max(1, moved))


# ---------------------------------------------------------------------------- the end
def _end(game, lm, s, rec: dict, *, broken: bool) -> None:
    """Its leader fell or its clock ran out: the attackers go, and the harm is counted (H.5 writes it in full)."""
    keep = getattr(game, "battle_actor", None)
    ids = {b.get("actor") for w in rec["waves"] for b in w["bands"] if b["state"] == "in"}
    for w in rec["waves"]:
        for b in w["bands"]:
            if b["state"] == "in" and (keep is None or keep.id != b.get("actor")):
                b["state"] = "gone"
    lm.actors[:] = [a for a in lm.actors if a.id not in ids or a is keep]
    for k in [k for k in _paths if k[0] == lm.key]:
        _paths.pop(k, None)
    if game.local is lm:
        _say(game, _words(game, "broken" if broken else "over", rec, s))
    day = game.world.time / 1440.0
    assaults.resolve(game.world, game.tables, rec, day=day, rng=game.world.rng.child(f"assault-end/{rec['id']}"))
    if game.local is lm:
        from realmwalker.game import placemarks

        placemarks.stamp(game, lm, s)  # (the marks it left, on the map while you stand there)
