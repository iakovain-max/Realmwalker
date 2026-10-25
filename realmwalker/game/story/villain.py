"""The villain who acts (docs/ADVENTURES.md §5.4; Part A's minimal attention, Expansion 6 E.1 in full).

Attention (0 to villains.json attention.max; `levels` names each: unaware, has heard of you, watching, testing,
wrathful, obsessed) rises as the hero does the villain harm: `step` a step done, `lieutenant` a lieutenant slain,
`servants` its servants or beasts killed in a fight, `great_magic` a spell of `great_level` or more cast within its
reach; it falls by `fortnight` every quiet fourteen days. (A Reading that draws its card, and each Legend tier at the
start, come with Parts F and J.)

The villain answers with moves (villains.json moves: the beat each plays and the attention it needs; `speaks` for one
that needs words, never a beast's or the bestial's; `tailored` for one made with a token its spy stole; `spy` for the
spy itself), weighted by its temper (tempers: moves). The limits: one move in `moves_apart_days`, `per_chapter` a
chapter, and at each opportunity a chance by attention (`chance`). The beat waits for the right place and hour like
any other (story/director.py).

A spy (villains.json `spy`): the party's best passive Perception against `dc` + attention. Seen, its beat plays (chase
it, or let it go); unseen, it steals a token (`tokens`: a glove, a ribbon) from one of the party, kept in
adv["token"] {what, of, day, used}: the next tailored move is made with it ({token}, {token_of}), at `tailored` times
its weight, and a token makes one such move.

Wrath (`setback`; villains.json `wrath`): a lieutenant slain, or a step done that is a blow to it (its kind in
`steps`): attention jumps by `jump`, and within `days` its next move is one needing `min` attention or more (`weight`
times its temper's weight) whatever the chapter's count: a reprisal, a strike, a visit. A reprisal falls on one of the
cast who helped you (`reprisal_roles`) whom no step still needs: adv["reprisal"] holds them until the op `reprisal`.
"""

from __future__ import annotations

DEFAULT = {"step": 1, "lieutenant": 2, "servants": 1, "great_magic": 1, "great_level": 6, "fortnight": -1, "max": 5,
           "moves_apart_days": 2, "per_chapter": 1, "chance": [1.0],
           "levels": ["unaware", "has heard of you", "watching", "testing", "wrathful", "obsessed"]}


def spec(game) -> dict:
    return dict(DEFAULT, **game.tables.villains.get("attention", {}))


def level(game, adv: dict) -> str:
    """Its attention in words (the journal)."""
    names = spec(game)["levels"]
    return names[max(0, min(len(names) - 1, int(adv.get("attention", 0))))]


def notice(game, adv: dict, n: int) -> None:
    adv["attention"] = max(0, min(int(spec(game)["max"]), int(adv.get("attention", 0)) + int(n)))


def quiet(game, adv: dict) -> None:
    """A fortnight without harm to it: it thinks of you less (story.daily)."""
    day = int(game.moment.total_days)
    last = int(adv.get("quiet_day", adv.get("began", day)))
    if day - last >= 14:
        adv["quiet_day"] = day
        notice(game, adv, int(spec(game)["fortnight"]))


def harmed(game, adv: dict) -> None:
    """Any harm resets the quiet fortnight."""
    adv["quiet_day"] = int(game.moment.total_days)


def setback(game, adv: dict, why: str) -> None:
    """A major blow to it: it lashes out (see the module's docstring)."""
    w = game.tables.villains.get("wrath")
    if not w:
        return
    notice(game, adv, int(w["jump"]))
    harmed(game, adv)
    adv["wrath"] = {"day": int(game.moment.total_days), "why": why}


def on_step(game, adv: dict, st: dict) -> None:
    """A step of its tale done (story.step_done)."""
    notice(game, adv, int(spec(game)["step"]))
    harmed(game, adv)
    if st.get("kind") in (game.tables.villains.get("wrath") or {}).get("steps", []):
        setback(game, adv, st["kind"])


def on_fight(game, adv: dict, *, servants: int = 0, lieutenants: int = 0) -> None:
    """After a fight (story.on_battle): its servants killed (once a fight), its lieutenants slain (each, and wrath)."""
    s = spec(game)
    if servants:
        notice(game, adv, int(s["servants"]))
        harmed(game, adv)
    for _ in range(lieutenants):
        notice(game, adv, int(s["lieutenant"]))
        setback(game, adv, "lieutenant")


def in_reach(game, adv: dict) -> bool:
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    return t is not None and threats.distance(game.world, t, game.player.x, game.player.y) <= int(t["reach"]["r"])


def on_magic(game, level: int) -> None:
    """Great magic cast (on the road or in a fight): every villain within whose reach it was feels it."""
    from realmwalker.game import story

    s = spec(game)
    if int(level) < int(s["great_level"]):
        return
    for adv in story.active(game):
        if in_reach(game, adv):
            notice(game, adv, int(s["great_magic"]))
            harmed(game, adv)


def temper(game, adv: dict) -> dict:
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    return game.tables.villains.get("tempers", {}).get((t or {}).get("villain", {}).get("temper") or "", {})


def speaks(game, adv: dict) -> bool:
    """Whether it can write or talk: a beast never does, whatever its temper."""
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    fig = threats.villain_figure(game.world, t) if t else None
    return bool(temper(game, adv).get("speaks")) and (fig is None or fig.kind != "beast")


def _wrath(game, adv: dict) -> dict | None:
    w, rec = game.tables.villains.get("wrath"), adv.get("wrath")
    if not w or not rec:
        return None
    if int(game.moment.total_days) - int(rec["day"]) > int(w["days"]):
        adv.pop("wrath", None)
        return None
    return rec


def due_move(game, adv: dict, where: str) -> str | None:
    """The beat of a move the villain would make now, here, or None (see the module's docstring). A spy unseen makes
    its move without a beat."""
    from realmwalker.game.story import beats

    s = spec(game)
    day = int(game.moment.total_days)
    moves = adv.setdefault("moves", [])
    if moves and day - int(moves[-1]["day"]) < int(s["moves_apart_days"]):
        return None
    wrath = _wrath(game, adv)
    this_chapter = [m for m in moves if m.get("chapter") == adv["chapter"] and not m.get("wrath")]
    if wrath is None and len(this_chapter) >= int(s["per_chapter"]):
        return None
    table = game.tables.villains["moves"]
    att = int(adv.get("attention", 0))
    talks = speaks(game, adv)
    token = adv.get("token")
    fresh = token is not None and not token.get("used")
    tailor = float((game.tables.villains.get("spy") or {}).get("tailored", 1))
    w_spec = game.tables.villains.get("wrath") or {}
    normal, angry = ([], []), ([], [])
    for mid, wt in sorted(temper(game, adv).get("moves", {}).items()):
        move = table.get(mid)
        if move is None or float(wt) <= 0:
            continue
        lo, hi = move["attention"]
        if not lo <= att <= hi or (move.get("speaks") and not talks) or (move.get("tailored") and not fresh):
            continue
        if move.get("beat") == "villain_reprisal" and _helper(game, adv) is None:
            continue
        if not beats.eligible(game, move["beat"], {"adv": adv["id"], "where": where}):
            continue
        weight = float(wt) * (tailor if move.get("tailored") else 1.0)
        normal[0].append(mid)
        normal[1].append(weight)
        if wrath is not None and lo >= int(w_spec.get("min", 0)):
            angry[0].append(mid)
            angry[1].append(weight * float(w_spec.get("weight", 1)))
    rng = game.world.rng.child(f"villain/{adv['id']}/{day}/{where}")
    if angry[0]:
        options, weights = angry
    elif normal[0] and len(this_chapter) < int(s["per_chapter"]):
        chance = s["chance"][min(att, len(s["chance"]) - 1)]
        if not rng.child("chance").chance(float(chance)):
            return None
        options, weights = normal
    else:
        return None
    mid = rng.weighted(options, weights)
    move = table[mid]
    moves.append({"day": day, "move": mid, "chapter": adv["chapter"], **({"wrath": True} if angry[0] else {})})
    if angry[0]:
        adv.pop("wrath", None)
    if move.get("tailored"):
        token["used"] = day
    if move.get("beat") == "villain_reprisal":
        adv["reprisal"] = _helper(game, adv)
    if move.get("spy"):
        return move["beat"] if _spy_seen(game, adv, rng) else None
    return move["beat"]


# ---------------------------------------------------------------------------- the spy and its token
def _spy_seen(game, adv: dict, rng) -> bool:
    """The party's best passive Perception against the spy; unseen, it steals a token (said in the log)."""
    from realmwalker.core import textgen

    spy = game.tables.villains.get("spy") or {"dc": 12, "tokens": ["a glove"], "missing": ["{token_of} lost {token}."]}
    able = [c for c in game.party if c.alive] or game.party
    if max(game.sheet(c).passive_perception for c in able) >= int(spy["dc"]) + int(adv.get("attention", 0)):
        return True
    who = rng.choice(able)
    adv["token"] = {"what": rng.choice(spy["tokens"]), "of": who.name.split()[0], "day": int(game.moment.total_days)}
    words = {"token": adv["token"]["what"], "token_of": adv["token"]["of"]}
    game.say(f"<dim>{textgen.fill(rng.choice(spy['missing']), rng, {}, words)}</>", "story")
    return False


# ---------------------------------------------------------------------------- reprisals
def _helper(game, adv: dict) -> int | None:
    """The npc id of one of the cast who helped you and may pay for it: alive, in a town you are not in, and needed
    by no step still to do."""
    from realmwalker.game.story import cast

    roles = game.tables.villains.get("reprisal_roles", [])
    needed = set()
    for ch in adv["chapters"]:
        for st in ch["steps"]:
            if st["state"] != "done":
                needed.add(st["target"].get("role"))
                needed.update(r.get("role") for r in st["target"].get("routes", []))
    here = game.world.settlement_at(game.player.x, game.player.y)
    for role in roles:
        entry = adv["cast"].get(role)
        npc = cast.person(game.world, entry) if entry and "npc" in entry else None
        if npc is None or not getattr(npc, "alive", False) or role in needed:
            continue
        if here is not None and int(entry.get("settlement", -1)) == here.id:
            continue
        return int(entry["npc"])
    return None
