"""The stage (Expansion 6 Part B, docs/ADVENTURES.md §5.18, §8.11): small pieces of choreography played on a town's
close-up map by its own people, in the town's own time. Show, don't tell: a child runs up to you through the crowd, a
crowd gathers at the gibbet, a door is slammed in your face.

A scene is data (scenes.json: `cues`, a whitelist filled here with `@cue`) or a dict given to `start`. One plays at a
time, kept in `politics["director"]["scene"]` = {"id", "map", "town", "cast" {role: npc id | "you"}, "i" (the cue
being played), "t" (town ticks spent on it), "hold", "words", "then", "made", "day"}.

    start(game, scene, *, cast=, words=, then=)  ask for a scene on the map you are on (None if it cannot play here)
    tick(game, lm)        one town tick of the scene (townlife.tick calls it first, so the whole town moves with it)
    settle(game, lm)      a jump of time: the scene plays to its end (townlife.settle)
    skip(game)            Space or Escape while a scene holds: straight to its end
    holding(game)         the player's keys wait (GameState.held)
    on_load(game)         a scene saved in the middle is played to its end, so it never repeats or breaks

How cues become movement: walking cues give the actor an errand (`npc.flags["errand"]` {"to", "pace", "scene"}),
which townlife.goal reads before anything else (runners take two steps a tick); words go through `townlife.speak`
(shown whatever the Text detail, for they are not flavour); a crowd is `Town.flags["gathering"]`, which townlife.goal
sends its people to in rings. A cue that cannot finish in STALL ticks is skipped: a scene never stalls. With
Animations off (`game.animations`), movement completes at once. If a cue cannot cast its actor (nobody of that trade
is about), the scene jumps to its end and plays only the cues marked `"always": true` (the beat a runner would have
brought still opens).

Scenes advance only on a town's map (the people who act in them are townsfolk); a camp's scenes are played by the
camp screen in its picture (Part B.9).
"""

from __future__ import annotations

from realmwalker.core import textgen

CUES: dict[str, object] = {}
STALL = 40  # town ticks a cue may take before the scene goes on without it
SAY_TICKS = 3  # a line stays over a head this many ticks before the next cue (a short while to read it)
COOLDOWN_DAYS = 1  # a town's people stage something for you at most once a day
BESIDE = ((0, 1), (1, 0), (-1, 0), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1))


def cue(name: str):
    """fn(game, lm, rec, c) -> True when this cue is done (the scene goes on to the next)"""
    def wrap(fn):
        CUES[name] = fn
        return fn
    return wrap


# ---------------------------------------------------------------------------- the record
def _director(world) -> dict:
    return world.politics.setdefault("director", {})


def current(game) -> dict | None:
    return _director(game.world).get("scene")


def _cues(game, rec: dict) -> list[dict]:
    if "cues" in rec:
        return rec["cues"]
    return game.tables.scenes.get(rec["id"], {}).get("cues", [])


def _here(game, rec: dict):
    lm = game.local
    return lm if lm is not None and game.in_local and lm.key == rec["map"] else None


def holding(game) -> bool:
    """A scene holds the player's keys (only on its own town's map)."""
    rec = current(game)
    return bool(rec and rec.get("hold") and _here(game, rec) is not None)


def start(game, scene, *, cast: dict | None = None, words: dict | None = None, then: dict | None = None,
          force: bool = False) -> dict | None:
    """Ask for a scene (an id in scenes.json, or a dict with `cues`) on the town map you stand on. None if it cannot
    play: not on a town's map, another scene playing, something waiting, or this town staged one today."""
    from realmwalker.game.people import settlement_of, town_of

    lm = game.local
    if lm is None or not game.in_local or lm.kind != "settlement" or current(game) is not None:
        return None
    s = settlement_of(game, lm)
    if s is None:
        return None
    flags = town_of(game.world, s.id).flags
    today = int(game.moment.total_days)
    if not force and today - int(flags.get("scene_day", -99)) < COOLDOWN_DAYS:
        return None
    rec = {"id": scene if isinstance(scene, str) else scene.get("id", "scene"), "map": lm.key, "town": s.id,
           "cast": dict(cast or {}), "i": 0, "t": 0, "hold": False, "words": dict(words or {}), "then": then,
           "made": [], "day": today}
    if not isinstance(scene, str):
        rec["cues"] = list(scene["cues"])
    elif scene not in game.tables.scenes:
        return None
    rec["cast"].setdefault("you", "you")
    flags["scene_day"] = today
    _director(game.world)["scene"] = rec
    return rec


# ---------------------------------------------------------------------------- driving
def tick(game, lm) -> None:
    """One town tick of the scene on this map: the cue being played, and every cue after it that is done at once."""
    rec = current(game)
    if rec is None or rec["map"] != lm.key or game.local is not lm:
        return
    cues = _cues(game, rec)
    for _ in range(len(cues) + 1):
        if rec["i"] >= len(cues):
            end(game)
            return
        c = cues[rec["i"]]
        if rec.get("failed") and not c.get("always"):
            rec["i"] += 1
            continue
        fn = CUES.get(c.get("cue"))
        done = True if fn is None else fn(game, lm, rec, c)
        if current(game) is not rec:
            return  # (the cue ended the scene)
        if not done:
            rec["t"] += 1
            if rec["t"] < STALL:
                return
            _give_up(game, lm, rec, c)
        rec["i"] += 1
        rec["t"] = 0
        if c.get("hold"):
            rec["hold"] = False
        if game.busy:
            return  # (a beat, a talk or a fight opened: the rest waits for it)


def _give_up(game, lm, rec: dict, c: dict) -> None:
    """A cue that would not finish: whoever was walking is simply where they were going."""
    if c.get("cue") in MOVES:
        npc = _actor(game, rec, c.get("who"))
        if npc is not None:
            _arrive_now(game, lm, rec, npc, c)


def settle(game, lm) -> None:
    """Time has jumped: the scene plays to its end at once."""
    rec = current(game)
    if rec is not None and rec["map"] == lm.key:
        _finish(game, lm, rec)


def skip(game) -> bool:
    """Space or Escape while a scene holds: everything it would do, done at once."""
    rec = current(game)
    if rec is None:
        return False
    _finish(game, _here(game, rec), rec)
    return True


def check_here(game) -> None:
    """A scene whose map you have left (out of the gate, down a stair) is over: what it was bringing still comes."""
    rec = current(game)
    if rec is not None and _here(game, rec) is None and not game.busy:
        _finish(game, None, rec)


def on_load(game) -> None:
    """A scene saved in its middle ends on load (so it never repeats, and nobody is left on an errand)."""
    rec = current(game)
    if rec is not None:
        _finish(game, _here(game, rec), rec)


def _finish(game, lm, rec: dict) -> None:
    """Play every cue left with animations off (movement completes at once), then end."""
    if lm is None:
        end(game)
        return
    was = getattr(game, "animations", "full")
    game.animations = "off"
    try:
        cues = _cues(game, rec)
        guard = 0
        while current(game) is rec and rec["i"] < len(cues) and guard < len(cues) * 3:
            guard += 1
            c = cues[rec["i"]]
            fn = CUES.get(c.get("cue"))
            if (rec.get("failed") and not c.get("always")) or fn is None or c.get("cue") in SKIPPED:
                rec["i"] += 1
                continue
            fn(game, lm, rec, c)
            if current(game) is not rec:
                return
            rec["i"] += 1
        if current(game) is rec:
            end(game)
    finally:
        game.animations = was


def end(game) -> None:
    """The scene is over: errands and gatherings cleared, its people back to their days, visitors gone."""
    from realmwalker.game import townlife
    from realmwalker.game.people import town_of

    d = _director(game.world)
    rec = d.pop("scene", None)
    if rec is None:
        return
    town = town_of(game.world, rec["town"]) if rec.get("town") is not None else None
    if town is not None:
        town.flags.pop("gathering", None)
    for who in rec["cast"].values():
        npc = game.world.npcs.get(who) if isinstance(who, int) else None
        if npc is not None:
            npc.flags.pop("errand", None)
            npc.flags.pop("holding", None)
            if npc.flags.get("pose") == "kneel":
                npc.flags.pop("pose", None)
    for nid in rec.get("made", []):
        if nid in rec.get("keep", []):
            continue
        npc = game.world.npcs.pop(nid, None)
        if town is not None and nid in town.npcs:
            town.npcs.remove(nid)
        if npc is not None:
            townlife.forget_person(npc.id)
    game.camera = None
    if rec.get("then") and not rec.get("then_done"):
        _then(game, rec)


def _then(game, rec: dict) -> None:
    """What the scene was bringing (a beat), if its `beat` cue never played."""
    from realmwalker.game.story import beats

    then = rec["then"]
    rec["then_done"] = True
    if then.get("beat") and beats.pending(game) is None:
        beats.offer(game, then["beat"], adv=then.get("adv"), step=then.get("step"), where=then.get("where", "town"),
                    words=then.get("words"))


# ---------------------------------------------------------------------------- helpers
def _actor(game, rec: dict, role):
    who = rec["cast"].get(role) if role is not None else None
    return game.world.npcs.get(who) if isinstance(who, int) else None


def _people(game, rec: dict) -> list:
    from realmwalker.game.people import npcs_in

    return [n for n in npcs_in(game.world, rec["town"]) if n.alive and n.present]


def _taken(game, lm, rec: dict, but=None) -> set:
    out = {(n.x, n.y) for n in _people(game, rec) if n is not but} | {(a.x, a.y) for a in lm.actors}
    out.add((game.player.lx, game.player.ly))
    return out


def _stand(game, lm):
    from realmwalker.game import townlife

    return townlife.town_for(game, lm).stand


def _free_beside(game, lm, rec, spot, npc, far: int = 1) -> tuple[int, int] | None:
    """A free square beside a spot, the nearest to whoever is coming."""
    stand = _stand(game, lm)
    taken = _taken(game, lm, rec, but=npc)
    best = None
    for r in range(1, far + 3):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                x, y = spot[0] + dx, spot[1] + dy
                if not (0 <= x < stand.shape[0] and 0 <= y < stand.shape[1]) or not stand[x, y] or (x, y) in taken:
                    continue
                d = (x - npc.x) ** 2 + (y - npc.y) ** 2 if npc is not None else 0
                if best is None or d < best[0]:
                    best = (d, (x, y))
        if best is not None:
            return best[1]
    return None


def _spot(game, lm, rec: dict, to, npc=None) -> tuple[int, int] | None:
    """Where a cue's `to`/`at` points: "you", a role, "home", "gate", "away" (as far from you as their way allows), or
    [x, y]."""
    p = game.player
    if to in (None, "you"):
        return p.lx, p.ly
    if isinstance(to, (list, tuple)):
        return int(to[0]), int(to[1])
    if to == "gate":
        return tuple(lm.entry)
    if to == "square":
        from realmwalker.game import townlife

        sq = townlife.town_for(game, lm).square
        return sq[len(sq) // 2] if sq else tuple(lm.entry)
    if npc is not None and to == "home":
        return tuple(npc.home)
    if npc is not None and to == "away":
        options = [tuple(npc.home), tuple(npc.post), tuple(lm.entry)]
        return max(options, key=lambda c: (c[0] - p.lx) ** 2 + (c[1] - p.ly) ** 2)
    other = _actor(game, rec, to)
    if other is not None:
        return other.x, other.y
    return None


def _near(a, spot, d: int = 1) -> bool:
    return max(abs(a[0] - spot[0]), abs(a[1] - spot[1])) <= d


def _words(game, rec: dict, c: dict, npc=None) -> str:
    """A cue's line: one of its `words` (or of the scene's `words` table named by `key`), filled with the scene's
    words, the actor's name and the story's tables."""
    lines = c.get("words")
    if lines is None and c.get("key"):
        lines = game.tables.scenes.get(rec["id"], {}).get("words", {}).get(c["key"]) or rec["words"].get(c["key"])
    if isinstance(lines, str):
        lines = [lines]
    if not lines:
        return ""
    rng = game.world.rng.child(f"scene/{rec['day']}/{rec['i']}/{rec['id']}")
    values = {k: v for k, v in rec["words"].items() if isinstance(v, str)}
    if npc is not None:
        values.setdefault("name", npc.first_name)
        values.setdefault("trade", npc.title)
    values.setdefault("you", game.leader.name.split()[0])
    return textgen.fill(rng.choice(list(lines)), rng, game.tables.adventures.get("words", {}), values)


def _instant(game) -> bool:
    return getattr(game, "animations", "full") == "off"


# ---------------------------------------------------------------------------- casting
@cue("pick")
def _pick(game, lm, rec, c) -> bool:
    """Cast a role from the townsfolk about: the nearest of the trades in `jobs` (any trade with `any`), awake, not
    already cast; `near` a role or you. Nobody: the scene goes to its end (its `always` cues still play)."""
    from realmwalker.game import townlife

    role = c["role"]
    if isinstance(rec["cast"].get(role), int):
        return True
    centre = _spot(game, lm, rec, c.get("near", "you")) or (game.player.lx, game.player.ly)
    cast = {v for v in rec["cast"].values() if isinstance(v, int)}
    jobs = c.get("jobs") or []
    far = int(c.get("within", 60))
    folk = [n for n in _people(game, rec) if n.id not in cast and not n.flags.get("stays")
            and not n.flags.get("visitor") and not townlife.asleep(game, n) and n.flags.get("pose") is None
            and _near((n.x, n.y), centre, far)]
    pool = [n for n in folk if n.job in jobs] or ([n for n in folk] if c.get("any") or not jobs else [])
    if not pool:
        rec["failed"] = True
        return True
    npc = min(pool, key=lambda n: ((n.x - centre[0]) ** 2 + (n.y - centre[1]) ** 2, n.id))
    rec["cast"][role] = npc.id
    if c.get("holding"):  # (drawn carrying it until it changes hands)
        npc.flags["holding"] = c["holding"]
    return True


@cue("arrive")
def _arrive(game, lm, rec, c) -> bool:
    """Someone comes in at the gate (or `at` a role's side) for this scene: a person of the trade `job`, who goes
    again when it ends (unless `keep`)."""
    from realmwalker.game import people

    role = c["role"]
    if isinstance(rec["cast"].get(role), int):
        return True
    s = game.world.settlements[rec["town"]]
    town = people.town_of(game.world, s.id)
    job = c.get("job", "pilgrim")
    if job not in game.tables.people["occupations"]:
        job = "pilgrim"
    at = _spot(game, lm, rec, c.get("at", "gate")) or tuple(lm.entry)
    rng = game.world.rng.child(f"scene/arrive/{rec['day']}/{role}/{len(game.world.npcs)}")
    npc = people.make_npc(game, s, job, rng, post=at, home=at)
    spot = _free_beside(game, lm, rec, at, None, far=3) if at in _taken(game, lm, rec) else at
    if spot is None:
        rec["failed"] = True
        return True
    npc.x, npc.y = spot
    npc.present = True
    npc.flags.update({"visitor": True, "placed": True})
    people.add(game.world, town, npc)
    rec["cast"][role] = npc.id
    rec["made"].append(npc.id)
    if c.get("keep"):
        rec.setdefault("keep", []).append(npc.id)
    return True


# ---------------------------------------------------------------------------- moving
MOVES = ("walk", "run", "follow", "flee")
SKIPPED = ()  # (cues that _finish never plays; none yet)


def _arrive_now(game, lm, rec, npc, c) -> None:
    to = "away" if c.get("cue") == "flee" else c.get("to", "you")
    spot = _spot(game, lm, rec, to, npc)
    if spot is None:
        return
    close = to == "you" or isinstance(rec["cast"].get(to), int)
    there = _free_beside(game, lm, rec, spot, npc) if close or spot in _taken(game, lm, rec, but=npc) else spot
    if there is not None:
        npc.x, npc.y = there
    npc.flags.pop("errand", None)
    from realmwalker.game import townlife

    townlife.forget_person(npc.id)


def _go(game, lm, rec, c, pace: int, to) -> bool:
    npc = _actor(game, rec, c.get("who"))
    if npc is None:
        return True
    spot = _spot(game, lm, rec, to, npc)
    if spot is None:
        npc.flags.pop("errand", None)
        return True
    close = to == "you" or isinstance(rec["cast"].get(to), int)
    if (close and _near((npc.x, npc.y), spot)) or (not close and (npc.x, npc.y) == spot):
        npc.flags.pop("errand", None)
        return True
    if _instant(game):
        _arrive_now(game, lm, rec, npc, c)
        return True
    goal = _free_beside(game, lm, rec, spot, npc) if close else spot
    if goal is None:
        return False  # (everyone round you: wait a tick)
    npc.flags["errand"] = {"to": [int(goal[0]), int(goal[1])], "pace": pace, "scene": rec["id"]}
    return False


@cue("walk")
def _walk(game, lm, rec, c) -> bool:
    return _go(game, lm, rec, c, 1, c.get("to", "you"))


@cue("run")
def _run(game, lm, rec, c) -> bool:
    return _go(game, lm, rec, c, 2, c.get("to", "you"))


@cue("follow")
def _follow(game, lm, rec, c) -> bool:
    return _go(game, lm, rec, c, 1, c.get("to", "you"))


@cue("flee")
def _flee(game, lm, rec, c) -> bool:
    return _go(game, lm, rec, c, 2, "away")


# ---------------------------------------------------------------------------- words
def _say_cue(game, lm, rec, c, loud: bool) -> bool:
    from realmwalker.game import townlife

    npc = _actor(game, rec, c.get("who"))
    if npc is None:
        return True
    ticks = int(c.get("ticks", SAY_TICKS))
    if rec["t"] == 0:
        words = _words(game, rec, c, npc)
        if not words:
            return True
        townlife.speak(game, lm, npc, words, ticks + townlife.BARK_TICKS)
        if loud or c.get("log"):
            game.say(f"{textgen.escape_markup(npc.first_name)}: “{textgen.escape_markup(words)}”",
                     "speech" if not loud else "warn")
    return _instant(game) or rec["t"] + 1 >= ticks


@cue("say")
def _say(game, lm, rec, c) -> bool:
    return _say_cue(game, lm, rec, c, False)


@cue("shout")
def _shout(game, lm, rec, c) -> bool:
    return _say_cue(game, lm, rec, c, True)


# ---------------------------------------------------------------------------- things
@cue("give")
def _give(game, lm, rec, c) -> bool:
    """An item changes hands, drawn between the two for a moment: `who` gives `item` (an item id) to you; with
    `letter` (a words key), a sealed letter written from those words, in its sender's hand (game/letters.py)."""
    from realmwalker.rules.inventory import add_item

    npc = _actor(game, rec, c.get("who"))
    if npc is not None and c.get("letter"):
        lid = _letter(game, rec, c["letter"])
        npc.flags.pop("holding", None)
        if lid is not None:
            from realmwalker.game import letters

            letters.give(game, lid)
            rec["letter"] = lid
            _fx(game, "sealed_letter", (npc.x, npc.y), (game.player.lx, game.player.ly))
            game.say(f"<loot>{textgen.escape_markup(npc.first_name)} presses a sealed letter into your hand.</>",
                     "loot")
        return True
    item_id = c.get("item") or (rec.get("then") or {}).get("item")
    if npc is None or not item_id or game.tables.items.get(item_id) is None:
        return True
    add_item(game.leader, game.tables.items, item_id, 1, made_at=game.world.time,
             tags=[c["tag"]] if c.get("tag") else None)
    _fx(game, item_id, (npc.x, npc.y), (game.player.lx, game.player.ly))
    game.say(f"<loot>{textgen.escape_markup(npc.first_name)} presses {game.tables.items.get(item_id)['name']} "
             f"into your hand.</>", "loot")
    return True


@cue("take")
def _take(game, lm, rec, c) -> bool:
    """`who` takes `item` from you (if you have it)."""
    from realmwalker.rules.inventory import remove_item

    npc = _actor(game, rec, c.get("who"))
    item_id = c.get("item")
    if npc is None or not item_id:
        return True
    have = next((it for it in game.leader.inventory if it.def_id == item_id), None)
    if have is None:
        return True
    taken = remove_item(game.leader, have.uid, 1)
    if taken is not None:
        npc.inventory.append(taken)
        _fx(game, item_id, (game.player.lx, game.player.ly), (npc.x, npc.y))
    return True


def _letter(game, rec: dict, key: str) -> str | None:
    """Write the scene's letter: its words (paragraphs split by a blank line), signed by the town's headman, lord or
    eldest (or "the people of" the town), the paragraph naming the trouble ({hook}) underlined once read."""
    from realmwalker.game import letters
    from realmwalker.game.people import npcs_in

    lines = game.tables.scenes.get(rec["id"], {}).get("words", {}).get(key)
    if not lines:
        return None
    rng = game.world.rng.child(f"scene/letter/{rec['day']}/{rec['id']}")
    template = rng.choice(list(lines))
    words = dict((rec.get("then") or {}).get("words") or {})
    words.update({k: v for k, v in rec["words"].items() if isinstance(v, str)})
    folk = [n for n in npcs_in(game.world, rec["town"]) if n.alive]
    writer = next((n for job in ("lord", "headman", "priest", "elder", "scribe") for n in folk if n.job == job), None)
    town = game.world.settlements[rec["town"]].name
    sender = f"{writer.first_name}, {writer.title} of {town}" if writer is not None else f"the people of {town}"
    words.setdefault("town", town)
    words["sender"] = sender
    values = {k: str(v) for k, v in words.items()}
    parts = template.split("\n\n")
    paragraphs = [textgen.fill(part, rng, game.tables.adventures.get("words", {}), values) for part in parts]
    key_line = next((i for i, part in enumerate(parts) if "{hook}" in part), None)
    hand = letters.hand_for(writer.job if writer is not None else "plain")
    return letters.write(game, sender=sender, lines=paragraphs, hand=hand, key=key_line)


@cue("read")
def _read(game, lm, rec, c) -> bool:
    """The letter just given opens as its page (the scene waits under it)."""
    from realmwalker.game import letters

    if rec.get("letter"):
        rec["hold"] = False
        letters.show(game, rec["letter"])
    return True


def _fx(game, item_id: str, a, b) -> None:
    """For LocalView: the item drawn between two figures for a moment (never saved)."""
    n = int(getattr(game, "stage_n", 0)) + 1
    game.stage_n = n
    fx = getattr(game, "stage_fx", None)
    if fx is None:
        fx = game.stage_fx = []
    fx.append({"n": n, "item": item_id, "a": list(a), "b": list(b)})
    del fx[:-4]


# ---------------------------------------------------------------------------- the body
@cue("kneel")
def _kneel(game, lm, rec, c) -> bool:
    npc = _actor(game, rec, c.get("who"))
    if npc is not None:
        npc.flags["pose"] = "kneel"
    return True


@cue("rise")
def _rise(game, lm, rec, c) -> bool:
    npc = _actor(game, rec, c.get("who"))
    if npc is not None:
        npc.flags.pop("pose", None)
    return True


@cue("fall")
def _fall(game, lm, rec, c) -> bool:
    """The figure goes down where it stands (and stays down until the scene, or someone, lifts it)."""
    npc = _actor(game, rec, c.get("who"))
    if npc is not None:
        npc.flags["pose"] = "down"
        npc.flags.pop("errand", None)
    return True


@cue("die")
def _die(game, lm, rec, c) -> bool:
    """The person dies where they stand, through the people code (jobs that wanted them notice)."""
    npc = _actor(game, rec, c.get("who"))
    if npc is None or not npc.alive:
        return True
    npc.flags["pose"] = "down"
    npc.flags.pop("errand", None)
    npc.alive = False
    npc.present = False
    if game.quests:
        from realmwalker.game import quests

        quests.on_npc_death(game, npc)
    return True


# ---------------------------------------------------------------------------- the crowd
@cue("crowd")
def _crowd(game, lm, rec, c) -> bool:
    """`count` townsfolk gather round a spot (`at`: you, a role, "square", [x, y]) and murmur; done once most of them
    are there (or after `ticks`)."""
    from realmwalker.game import townlife
    from realmwalker.game.people import town_of

    town = town_of(game.world, rec["town"])
    g = town.flags.get("gathering")
    if g is None or rec["t"] == 0:
        spot = _spot(game, lm, rec, c.get("at", "you")) or (game.player.lx, game.player.ly)
        cast = {v for v in rec["cast"].values() if isinstance(v, int)}
        folk = [n for n in _people(game, rec) if n.id not in cast and not townlife.asleep(game, n)
                and not n.flags.get("stays") and n.flags.get("pose") is None and _near((n.x, n.y), spot, 40)]
        folk.sort(key=lambda n: ((n.x - spot[0]) ** 2 + (n.y - spot[1]) ** 2, n.id))
        ids = [n.id for n in folk[:int(c.get("count", 8))]]
        murmur = c.get("murmur") or game.tables.scenes.get(rec["id"], {}).get("words", {}).get(c.get("key", "murmur"))
        g = town.flags["gathering"] = {"spot": [int(spot[0]), int(spot[1])], "ids": ids,
                                       "radius": int(c.get("radius", 2)), "murmur": list(murmur or []),
                                       "until": int(game.world.time) + 60}
        if _instant(game):
            townlife.gather_now(game, lm, g)
            return True
    if _instant(game):
        return True
    there = sum(1 for nid in g["ids"] if (n := game.world.npcs.get(nid)) is not None
                and _near((n.x, n.y), g["spot"], g["radius"] + 2))
    return there * 2 >= len(g["ids"]) or rec["t"] + 1 >= int(c.get("ticks", 20))


@cue("disperse")
def _disperse(game, lm, rec, c) -> bool:
    from realmwalker.game.people import town_of

    town_of(game.world, rec["town"]).flags.pop("gathering", None)
    return True


# ---------------------------------------------------------------------------- the place
@cue("door")
def _door(game, lm, rec, c) -> bool:
    """A door (the home of `who`, or the nearest door to `at`) opens, closes or is slammed (`do`)."""
    from realmwalker.game import dungeon

    npc = _actor(game, rec, c.get("who"))
    door = None
    if npc is not None:
        b = lm.building_at(*npc.home)
        door = tuple(b.door) if b is not None else None
    if door is None:
        at = _spot(game, lm, rec, c.get("at", "you"))
        doors = [tuple(b.door) for b in lm.buildings]
        door = min(doors, key=lambda d: (d[0] - at[0]) ** 2 + (d[1] - at[1]) ** 2) if doors and at else None
    if door is None:
        return True
    do = c.get("do", "close")
    if do in ("close", "slam") and (game.player.lx, game.player.ly) != door and door not in _taken(game, lm, rec):
        dungeon.set_terrain(lm, door[0], door[1], "door_closed")
    elif do == "open":
        dungeon.set_terrain(lm, door[0], door[1], "door_open")
    if do == "slam":
        game.cue("door")
    return True


@cue("bell")
def _bell(game, lm, rec, c) -> bool:
    """A bell heard across the map (and the line in the log)."""
    game.cue("bell")
    words = _words(game, rec, c)
    if words:
        game.say(textgen.escape_markup(words), "warn")
    return True


@cue("focus")
def _focus(game, lm, rec, c) -> bool:
    """The camera eases to a spot and back (at most three seconds; never with Animations off)."""
    spot = _spot(game, lm, rec, c.get("at"))
    if spot is not None and not _instant(game):
        game.camera = {"to": [int(spot[0]), int(spot[1])], "n": int(rec["i"]) + 1000 * int(rec["day"])}
    return True


@cue("wait")
def _wait(game, lm, rec, c) -> bool:
    return _instant(game) or rec["t"] + 1 >= int(c.get("ticks", 2))


@cue("hold")
def _hold(game, lm, rec, c) -> bool:
    """From here the player's keys wait (Space or Escape skips the scene) until a `release` cue or the end."""
    rec["hold"] = bool(c.get("on", True))
    return True


@cue("release")
def _release(game, lm, rec, c) -> bool:
    rec["hold"] = False
    return True


# ---------------------------------------------------------------------------- what it leads to
@cue("talk")
def _talk(game, lm, rec, c) -> bool:
    """`who` speaks to you: the conversation opens with their words before any greeting."""
    npc = _actor(game, rec, c.get("who"))
    if npc is None or not npc.alive:
        return True
    words = _words(game, rec, c, npc)
    if words:
        npc.flags["opener"] = words
    rec["hold"] = False
    game.talk_to = npc.id
    return True


@cue("beat")
def _beat(game, lm, rec, c) -> bool:
    """Open a beat: the cue's `id`, or the one the scene was asked to bring (`then`)."""
    from realmwalker.game.story import beats

    rec["hold"] = False
    then = dict(rec.get("then") or {})
    if c.get("id"):
        then = {"beat": c["id"], "adv": then.get("adv"), "words": then.get("words")}
    rec["then_done"] = True
    if then.get("beat") and beats.pending(game) is None and then["beat"] in game.tables.beats:
        beats.offer(game, then["beat"], adv=then.get("adv"), step=then.get("step"), where="town",
                    words=then.get("words"))
    return True


@cue("fight")
def _fight(game, lm, rec, c) -> bool:
    """A fight with a band (`group`, an encounter id)."""
    from realmwalker.game.events import apply_outcome

    rec["hold"] = False
    group = c.get("group")
    if group and group in game.tables.creatures.encounters and game.battle is None:
        for line in apply_outcome(game, {"fight": group}, game.world.rng.child(f"scene/fight/{rec['day']}")):
            game.say(line, "warn")
    return True
