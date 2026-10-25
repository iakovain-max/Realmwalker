"""The first hour (Expansion 6 D.4, docs/ADVENTURES.md §5.12): a new life never starts on a quiet road. When a hero sets
out (story.begin), the Storyteller picks a threat near the start town and an opening for its tale, from the threat's
kind, the hero's background and where the start town stands (adventures.json "openings"):

- **crisis**: arriving into it. The start town lies within the threat's reach: as you come in at the gate the bell
  goes, the gate is barred behind you, a crowd gathers and one of them speaks for it (scene `opening_gate`); then the
  beat `opening_crisis` (take the tale, or not now).
- **summons**: a letter with a seal. A runner finds you in the street with a letter from the threat's own town
  (scene `opening_summons`: its page opens), then the beat `opening_summons`.
- **terror**: you wake as the gang's captive (outlaws only). The beat `opening_captive` opens at once, before
  anything else: work the knots, strain at the stake or talk the youngest guard round. The tale begins either way
  (they are your business now); a good escape finds the guards unaware at their fire, a bad one with blades out.
  Fight them or slip away (the encounter screen); the captors' camp is its own field (arena.FIELDS "captors").

Crisis and summons are staged on the start town's map when you first walk into it; leave without going in, or let the
first day go by, and the opening is told as its beat wherever you are (`on_travel`, `daily`). Either way a hook is
offered on the first game day (tests/test_first_hour.py).

The record is `politics["director"]["opening"]` = {"kind", "threat", "town", "day", "state" (waiting, played)}; the
tale it begins keeps `adv["opening"]` (story.take_hook).
"""

from __future__ import annotations

from realmwalker.core.textgen import escape_markup as esc

KINDS = ("crisis", "summons", "terror")
BEATS = {"crisis": "opening_crisis", "summons": "opening_summons", "terror": "opening_captive"}
SCENES = {"crisis": "opening_gate", "summons": "opening_summons"}
GUARDS = "bandits"  # who watches a captive by the fire (an encounter group, cut to the land's budget)


def record(game) -> dict | None:
    from realmwalker.game.story import beats

    return beats.director(game.world).get("opening")


def choose(game, t: dict, town) -> str:
    """Which opening fits: each kind of adventures.json "openings" that may happen here (its threat `kinds`, `near`:
    the start town within the threat's reach or among its stakes), weighed by `weight` and the hero's `backgrounds`."""
    from realmwalker.world import threats

    specs = game.tables.adventures.get("openings", {})
    reach = int(game.tables.threats["kinds"].get(t["kind"], {}).get("reach", 14))
    near = town is not None and (town.id in t["stakes"][:6] or threats.distance(game.world, t, town.x, town.y) <= reach)
    bg = game.leader.background
    kinds, weights = [], []
    for kind in KINDS:
        spec = specs.get(kind)
        if spec is None or (spec.get("kinds") and t["kind"] not in spec["kinds"]) or (spec.get("near") and not near):
            continue
        if kind in SCENES and town is None:
            continue
        kinds.append(kind)
        weights.append(int(spec.get("weight", 1)) + int(spec.get("backgrounds", {}).get(bg, 0)))
    if not kinds:
        return "summons"
    from realmwalker.game.story.forge import life_of

    rng = game.world.rng.child(f"opening/{life_of(game)}")
    return rng.weighted(kinds, weights)


def begin(game, t: dict) -> str:
    """A new life's opening, on the threat `t` (story.begin chose it). Terror plays at once; the others wait for the
    start town's map, the road or the day's end. Returns the kind."""
    from realmwalker.game.story import beats

    w = game.world
    home = game.player.home
    town = w.settlements[home] if home is not None and 0 <= home < len(w.settlements) else None
    kind = choose(game, t, town)
    rec = {"kind": kind, "threat": t["id"], "town": town.id if town is not None else None,
           "day": int(game.moment.total_days), "state": "waiting"}
    beats.director(w)["opening"] = rec
    if kind == "terror":
        play(game)
    return kind


def words(game, rec: dict) -> dict:
    """The hook's words for the opening's beat and scene: the villain, its home, the town that asks (the start town
    for a crisis or a captive; the threat's own town for a summons) and the hook line."""
    from realmwalker.game import story
    from realmwalker.world import threats

    w = game.world
    t = threats.records(w).get(rec["threat"])
    start = w.settlements[rec["town"]] if rec.get("town") is not None else None
    asking = start
    if rec["kind"] == "summons" and t["stakes"]:
        asking = w.settlements[t["stakes"][0]]
    out = story.hook_words(game, t, asking)
    out["hook"] = story.hook_line(game, t, asking)
    out["threat"] = t["id"]
    out["opening"] = rec["kind"]
    out["start"] = start.name if start is not None else out["town"]
    out["gang"] = threats.villain_name(w, t)
    return out


def live(game) -> dict | None:
    """The opening still waiting to be played, when its threat can still be taken on."""
    from realmwalker.game import story
    from realmwalker.world import threats

    rec = record(game)
    if rec is None or rec.get("state") != "waiting":
        return None
    t = threats.records(game.world).get(rec["threat"])
    if t is None or t["state"] not in threats.LIVE or t.get("adventure") is not None or not story._can_take(game, t):
        rec["state"] = "lost"
        return None
    return rec


def play(game, *, staged: bool = False) -> bool:
    """Play the waiting opening now: staged on the start town's map when `staged` and it has a scene, else as its
    beat. True when something began."""
    from realmwalker.game import story
    from realmwalker.game.story import beats, stage
    from realmwalker.world import threats

    rec = live(game)
    if rec is None or beats.pending(game) is not None:
        return False
    t = threats.records(game.world).get(rec["threat"])
    wd = words(game, rec)
    town = game.world.settlements[rec["town"]] if rec.get("town") is not None else None
    t["offer"] = {"by": rec.get("town") if rec.get("town") is not None else -1, "where": story._where(game),
                  "since": int(game.moment.total_days)}
    then = {"beat": BEATS[rec["kind"]], "where": "town", "words": wd}
    if staged and rec["kind"] in SCENES and town is not None:
        sw = {"town": wd["start"]} if rec["kind"] == "crisis" else {}  # (a summons' {town} is the one that asks)
        if rec["kind"] == "summons" and wd["town"] != wd["start"]:
            sw["sender"] = f"the elders of {wd['town']}"
            sw["hand_of"] = "elder"
        if stage.start(game, SCENES[rec["kind"]], words=sw, then=then, force=True) is not None:
            rec["state"] = "played"
            return True
    beats.offer(game, BEATS[rec["kind"]], where=story._where(game), words=wd)
    rec["state"] = "played"
    return True


# ---------------------------------------------------------------------------- the hooks (from story/__init__.py)
def on_enter_town(game, settlement) -> bool:
    """Into the start town's streets: the crisis at the gate, or the runner with the summons. True when it began."""
    rec = live(game)
    if rec is None or rec["kind"] not in SCENES or rec.get("town") != settlement.id:
        return False
    return play(game, staged=True)


def on_travel(game) -> bool:
    """Walking away from the start without going in: the opening finds you on the road (its beat)."""
    rec = live(game)
    if rec is None or rec["kind"] not in SCENES:
        return False
    home = game.world.settlements[rec["town"]] if rec.get("town") is not None else None
    if home is not None and (game.player.x, game.player.y) == (home.x, home.y):
        return False  # (still at its gate: it waits for you to go in)
    return play(game)


def daily(game) -> None:
    """The first day is over and the opening never came: it comes now, wherever you are."""
    rec = live(game)
    if rec is not None and int(game.moment.total_days) > int(rec["day"]):
        play(game)


# ---------------------------------------------------------------------------- the captive's escape
def escape(game, rec: dict, how: str) -> list[str]:
    """Out of the ropes (the beat's op `opening_escape`): the tale is taken, the party is a little way out of the
    start town, and the guards are there: unaware at their fire (`how` "quiet") or on their feet ("loud")."""
    from realmwalker.game import story
    from realmwalker.game.encounters import make_encounter

    wd = rec.get("words", {})
    out = story.take_hook(game, wd.get("threat", ""))
    _out_of_town(game)
    groups = game.tables.creatures.encounters
    if GUARDS not in groups:
        return out
    rng = game.world.rng.child(f"opening/guards/{game.world.time}")
    enc = make_encounter(game, GUARDS, rng)
    if not enc.creatures:
        return out
    adv = next((a for a in story.active(game) if a["threat"] == wd.get("threat")), None)
    for c in enc.creatures:
        if adv is not None:
            c.story = {"adv": adv["id"], "role": "minion"}
    enc.attitude = "hostile"
    enc.spotted_first = how == "quiet"
    enc.field = "captors"
    gang = esc(wd.get("gang", "the gang"))
    enc.intro = (f"The men of {gang} who were set to watch you sit by their fire with their backs to you."
                 if how == "quiet" else f"The men of {gang} are on their feet, and they have their blades out.")
    game.encounter = enc
    game.travel = None
    return out


def _out_of_town(game) -> None:
    """The captors' camp is a short way out of the start town: the party stands on the nearest open tile beside it."""
    w, p = game.world, game.player
    best = None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            nx, ny = p.x + dx, p.y + dy
            if (dx, dy) == (0, 0) or not w.in_bounds(nx, ny) or w.settlement_at(nx, ny) is not None:
                continue
            if w.river[nx, ny] or game.step_minutes(p.x, p.y, nx, ny) is None:
                continue
            score = (0 if w.road[nx, ny] else 1, abs(dx) + abs(dy), dx, dy)
            if best is None or score < best[0]:
                best = (score, nx, ny)
    if best is not None:
        p.x, p.y = best[1], best[2]
        p.local_key = None


def _register() -> None:
    from realmwalker.game.story import beats

    @beats.op("opening_escape")
    def _escape(game, rec, how: str = "loud"):
        return escape(game, rec, how)


_register()
