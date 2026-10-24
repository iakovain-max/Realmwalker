"""The villain who notices you (docs/ADVENTURES.md §5.4; Part A's minimal attention).

Attention (0 to villains.json attention.max) rises as the hero does the villain harm (+step a step done, +lieutenant
a lieutenant slain) and falls with quiet (attention.fortnight every fourteen days). The villain answers with moves
chosen by its temper (villains.json tempers: weights; moves: the beat each plays and the attention it needs), at
most one in `moves_apart_days` and `per_chapter` a chapter (Part A: one). The beat waits for the right place and
hour like any other (story/director.py).
"""

from __future__ import annotations


def spec(game) -> dict:
    return game.tables.villains.get("attention", {"step": 1, "lieutenant": 2, "fortnight": -1, "max": 9,
                                                   "moves_apart_days": 2, "per_chapter": 1})


def notice(game, adv: dict, n: int) -> None:
    adv["attention"] = max(0, min(int(spec(game)["max"]), int(adv.get("attention", 0)) + int(n)))


def quiet(game, adv: dict) -> None:
    """A fortnight without harm to it: it thinks of you less (story.daily)."""
    day = int(game.moment.total_days)
    last = int(adv.get("quiet_day", adv.get("began", day)))
    if day - last >= 14:
        adv["quiet_day"] = day
        notice(game, adv, int(spec(game)["fortnight"]))


def temper(game, adv: dict) -> dict:
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    return game.tables.villains.get("tempers", {}).get((t or {}).get("villain", {}).get("temper") or "", {})


def due_move(game, adv: dict, where: str) -> str | None:
    """The beat of a move the villain would make now, here, or None: its temper's weights among the moves its
    attention allows, never two within a few days, never more than allowed in a chapter."""
    from realmwalker.game.story import beats

    s = spec(game)
    day = int(game.moment.total_days)
    moves = adv.setdefault("moves", [])
    if moves and day - int(moves[-1]["day"]) < int(s["moves_apart_days"]):
        return None
    this_chapter = [m for m in moves if m.get("chapter") == adv["chapter"]]
    if len(this_chapter) >= int(s["per_chapter"]):
        return None
    tem = temper(game, adv)
    options, weights = [], []
    for mid, wt in sorted(tem.get("moves", {}).items()):
        move = game.tables.villains["moves"].get(mid)
        lo, hi = move["attention"]
        if not lo <= int(adv.get("attention", 0)) <= hi:
            continue
        rec = {"adv": adv["id"], "where": where}
        if not beats.eligible(game, move["beat"], rec):
            continue
        options.append(mid)
        weights.append(float(wt))
    if not options:
        return None
    rng = game.world.rng.child(f"villain/{adv['id']}/{day}")
    mid = rng.weighted(options, weights)
    moves.append({"day": day, "move": mid, "chapter": adv["chapter"]})
    return game.tables.villains["moves"][mid]["beat"]
