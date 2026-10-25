"""Escapes, early ends, anchors and returning villains (docs/ADVENTURES.md §5.4; Expansion 6 E.4).

Escapes: a villain met before its finale breaks off when hurt (its boss template's `before`, the kernel's boss phase)
once in a tale. `may_escape` says whether it still can: not when it got away already (adv["escaped"] {day}, kept by
`on_fled` from story.on_battle), nor when a key found forbids it (a finale key `no_escape`: the crown in your hands).
Met again with its escape spent it does not run (`no_flight`: its morale fanatic, villains.json early `spent` said).
Held fast, or killed in one blow, it dies like anything else.

Early ends: the villain dead before its finale step is open (`begin`, from story.on_battle) does not end the tale at
once: the chapters still ahead are put away (adv["early"] {kind, day, chapters}) and a short last chapter takes their
place, chosen by the blueprint's `early` weights among the kinds that can be here (KINDS):
- `succession`: a lieutenant still free takes its place, a weaker villain: a defeat step on that lieutenant's band
  where the finale would have been (the dead villain's band there is unbound);
- `contingency`: what it set to happen on its death (a letter delivered after it, standing orders to its servants, a
  caged thing let loose): an `endure` step, its set piece a beat and a battle (story/deeds.py);
- `cat_away`: nothing is left to fight; the places it held open up, said at once, and the tale ends.
A last chapter done ends the tale (`after_chapter`, from story._chapter_check): the kill was fairly won, and the
ending is the one a slain villain earns.

Anchors and returning villains: a villain killed without its anchor dealt with comes back (the ending's consequence
`sequel`): its threat sleeps until `held_until` and then stirs for sure (world/threats.advance), with
`threat["returns"]` {adv, life, times}. The hero who put it down hears of it first (`daily`: the beat
villain_returns, which takes the tale on); the tale forged on it (`on_forge`) starts with villains.json early
`returning` attention and keeps adv["returning"] {times}, and its boss comes back with more hit points (`on_boss`).
At the top of its attention the villain may move the anchor into its own hall (`relic_movable`, `move_relic`: the
move relic_moved) while nobody has laid a hand on it yet.
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.textgen import escape_markup as esc

KINDS = ("succession", "contingency", "cat_away")
DEFAULT_KINDS = {"cat_away": 1}  # (a blueprint with no `early` of its own)
BEATS = ("early_last_letter", "early_loosed", "villain_returns")  # (played by name; story/check.py)
FREE = ("unmet", "met", "escaped", "spared")  # a lieutenant's fates that leave it free to take up the villain's place
DEFAULT = {"returning": {"attention": 3, "hp": 0.15, "max": 3}, "after": [0, 1]}


def _story():
    from realmwalker.game import story

    return story


def spec(game) -> dict:
    return dict(DEFAULT, **(game.tables.villains.get("early") or {}))


def _words(game, adv: dict, more: dict | None = None) -> dict:
    from realmwalker.game.story import words as wordsmod

    w = wordsmod.for_adventure(game, adv)
    w.update(more or {})
    return w


def _fill(game, adv: dict, lst: list, rng, more: dict | None = None) -> str:
    return textgen.fill(rng.choice(lst), rng, game.tables.adventures.get("words", {}), _words(game, adv, more))


# ---------------------------------------------------------------------------- escapes
def _forbidding_keys(adv: dict) -> list[str]:
    """The keys found whose finale effects include no_escape."""
    return [k for k, effects in (adv.get("finale") or {}).get("keys", {}).items()
            if k in adv.get("keys", []) and any(e.split("(")[0].strip() == "no_escape" for e in effects)]


def may_escape(game, adv: dict) -> bool:
    """Met before its finale, may it still break off when hurt?"""
    return not adv.get("escaped") and not _forbidding_keys(adv)


def no_flight(battle, game, adv: dict, f) -> str:
    """Its escape spent (or forbidden): it stands and fights to the end this time. Returns what to say."""
    f.cdef = dict(f.cdef, morale="fanatic")
    f.cdef.pop("boss_phase", None)
    lst = (spec(game).get("spent") or [])
    if not lst:
        return ""
    rng = game.world.rng.child(f"early/spent/{adv['id']}/{game.world.time}")
    return f"<danger>{esc(_fill(game, adv, lst, rng))}</>"


def on_fled(game, adv: dict) -> None:
    """It got away from a fight before its finale: that was its one escape in this tale."""
    from realmwalker.game.story import finale

    if adv.get("escaped") or finale._is_finale(adv):
        return
    adv["escaped"] = {"day": int(game.moment.total_days)}
    lst = spec(game).get("escaped") or []
    if lst:
        rng = game.world.rng.child(f"early/escaped/{adv['id']}")
        _story().journal(adv, _fill(game, adv, lst, rng), int(game.moment.total_days))


# ---------------------------------------------------------------------------- early ends
def _finale_step(adv: dict) -> dict | None:
    return next((st for ch in adv["chapters"] for st in ch["steps"] if st["kind"] == "finale"), None)


def _heir(game, adv: dict) -> tuple[str, dict] | None:
    """The lieutenant still free who could take its place (the greatest grudge first), with its cast role."""
    t = _story().threat_of(game, adv)
    recs = (t or {}).get("lieutenants", [])
    best = None
    for role, entry in sorted(adv["cast"].items()):
        if not isinstance(entry, dict) or entry.get("lt") is None or int(entry["lt"]) >= len(recs):
            continue
        rec = recs[int(entry["lt"])]
        if rec.get("fate") not in FREE or entry.get("band") not in game.tables.creatures.encounters:
            continue
        if best is None or int(rec.get("grudge", 0)) > int(best[1].get("grudge", 0)):
            best = (role, rec)
    return best


def available(game, adv: dict) -> list[str]:
    """The early ends that can be here."""
    from realmwalker.game.story import beats

    fin = _finale_step(adv)
    out = []
    if _heir(game, adv) is not None and fin is not None and fin["target"].get("level"):
        out.append("succession")
    if beats._minions(game, {"adv": adv["id"]}):
        out.append("contingency")
    out.append("cat_away")
    return out


def is_early(game, adv: dict) -> bool:
    """Would the villain dead now be dead before its finale?"""
    from realmwalker.game.story import finale

    if any(st["kind"] == "slay" for st in _story().open_steps(adv)):
        return False  # (killed where the tale meant it to be: the beast at the bait)
    return adv["state"] == "active" and not adv.get("early") and not finale._is_finale(adv) and \
        _finale_step(adv) is not None and _finale_step(adv)["state"] == "open"


def begin(game, adv: dict) -> bool:
    """The villain is dead before its finale: a short last chapter, or the tale ends at once (cat_away: False)."""
    if not is_early(game, adv):
        return False
    bp = game.tables.adventures["blueprints"][adv["blueprint"]]
    weights = dict(bp.get("early") or DEFAULT_KINDS)
    can = available(game, adv)
    options = [k for k in KINDS if k in can and int(weights.get(k, 0)) > 0] or ["cat_away"]
    rng = game.world.rng.child(f"early/{adv['id']}")
    kind = rng.weighted(options, [max(1, int(weights.get(k, 1))) for k in options])
    story = _story()
    cur = int(adv["chapter"])
    ch = story.chapter(adv)
    adv["early"] = {"kind": kind, "day": int(game.moment.total_days), "chapters": len(adv["chapters"])}
    _unbind_finale(game, adv)
    words = spec(game).get("kinds", {}).get(kind, {})
    dropped = set()
    for st in (ch or {}).get("steps", []):
        if st["state"] == "open":
            st["state"] = "done" if st["kind"] in ("slay", "finale") else "dropped"
            dropped.add(st["id"])
    game.quests[:] = [q for q in game.quests if not (q.get("adventure") == adv["id"] and q.get("step") in dropped)]
    if ch is not None:
        ch["state"] = "done"
    if kind == "cat_away":
        line = _fill(game, adv, words.get("lines") or ["With {villain_short} dead, what it held lies open."], rng)
        story.journal(adv, line, int(game.moment.total_days))
        game.say(f"<good>{esc(line)}</>", "story")
        return False
    step = _succession_step(game, adv) if kind == "succession" else _contingency_step(game, adv)
    more = {}
    if kind == "succession":
        from realmwalker.game.story import lieutenants

        more = {"heir": lieutenants.full(lieutenants.records(game, adv)[int(adv["cast"][step["target"]["role"]]["lt"])])}
    last = {"id": "early", "need": "all", "state": "open", "steps": [step]}
    for k in ("title", "goal", "opening", "reveal"):
        last[k] = _fill(game, adv, words.get(k) or ["{villain_short} is dead."], rng.child(k), more)
    adv["chapters"] = adv["chapters"][:cur + 1] + [last]
    adv["chapter"] = cur + 1
    story.journal(adv, last["opening"], int(game.moment.total_days))
    from realmwalker.game.story import beats, deeds

    beats.director(game.world)["card"] = {"adv": adv["id"], "chapter": int(adv["chapter"])}
    deeds.setup(game, adv)
    game.dirty = True
    return True


def _unbind_finale(game, adv: dict) -> None:
    """The dead villain's band is no longer bound to its den (whatever is there already stays as it is)."""
    for key, recs in game.world.politics.get("story_sites", {}).items():
        recs[:] = [r for r in recs if not (r.get("adv") == adv["id"] and not r.get("role"))]


def _succession_step(game, adv: dict) -> dict:
    role, rec = _heir(game, adv)
    fin = _finale_step(adv)
    entry = adv["cast"][role]
    target = {"place": dict(fin["target"]["place"]), "level": fin["target"]["level"], "role": role,
              "who": dict(entry), "group": entry["band"], "fled_ok": False}
    rec["heir"] = adv["id"]
    return {"id": "early.1", "kind": "defeat", "state": "open", "optional": False, "gives": [], "target": target}


def _contingency_step(game, adv: dict) -> dict:
    from realmwalker.game.story import beats, villain

    beat = "early_last_letter" if villain.speaks(game, adv) else "early_loosed"
    lo, hi = spec(game)["after"]
    target = {"beat": beat, "group": beats._minions(game, {"adv": adv["id"]}), "after": [int(lo), int(hi)]}
    field = game.tables.adventures["blueprints"][adv["blueprint"]]["finale"].get("endure_field")
    if field:
        target["field"] = field  # (its last orders carried out on the land: a burning village, E.5)
    return {"id": "early.1", "kind": "endure", "state": "open", "optional": False, "gives": [], "target": target}


def after_chapter(game, adv: dict) -> list[str]:
    """A chapter just done: if it was a short last chapter, the tale ends."""
    from realmwalker.game.story import endings

    if adv.get("early") and adv["state"] == "active" and adv["chapters"][-1]["state"] == "done":
        return endings.finish(game, adv)
    return []


# ---------------------------------------------------------------------------- returning villains
def returns(game, adv: dict, t: dict) -> None:
    """The ending's sequel: its threat remembers whom it comes back for (endings._sequel)."""
    old = t.get("returns") or {}
    t["returns"] = {"adv": adv["id"], "life": adv["hero"]["life"], "times": int(old.get("times", 0)) + 1}


def on_forge(game, adv: dict, t: dict) -> None:
    """A tale forged on a villain come back: it starts out angry with you, and remembers how often."""
    rec = t.get("returns")
    if not rec or not t.pop("sequel", None):
        return
    r = spec(game)["returning"]
    adv["returning"] = {"times": int(rec["times"]), "from": rec["adv"]}
    if rec.get("life") == adv["hero"]["life"]:  # (it remembers the one who put it down)
        adv["attention"] = max(int(adv.get("attention", 0)), int(r["attention"]))


def on_boss(battle, game, adv: dict, f) -> str:
    """Its finale: a villain come back is harder to put down again. Returns what to say."""
    rec = adv.get("returning")
    if not rec:
        return ""
    r = spec(game)["returning"]
    times = min(int(rec["times"]), int(r["max"]))
    extra = int(round(f.max_hp * float(r["hp"]) * times))
    f.max_hp += extra
    f.hp += extra
    lst = spec(game).get("back") or []
    if not lst:
        return ""
    rng = game.world.rng.child(f"early/back/{adv['id']}")
    return f"<danger>{esc(_fill(game, adv, lst, rng))}</>"


def daily(game) -> None:
    """A villain this hero put down walks again: they hear of it first (a beat that offers its tale)."""
    from realmwalker.game.story import beats, forge
    from realmwalker.world import threats

    if beats.pending(game) is not None or game.busy:
        return
    life = forge.life_of(game)
    for t in sorted(threats.records(game.world).values(), key=lambda t: int(t["id"][1:])):
        rec = t.get("returns")
        if not rec or rec.get("life") != life or rec.get("told") or t["state"] not in threats.LIVE \
                or t.get("adventure") is not None or not t.get("sequel"):
            continue
        story = _story()
        if not story._can_take(game, t):
            continue
        rec["told"] = int(game.moment.total_days)
        t["offer"] = {"by": t["stakes"][0] if t["stakes"] else -1, "where": story._where(game),
                      "since": int(game.moment.total_days)}
        words = story.hook_words(game, t)
        words["threat"] = t["id"]
        beats.offer(game, "villain_returns", where=story._where(game), words=words)
        return


# ---------------------------------------------------------------------------- the relic moved
def relic_movable(game, adv: dict) -> dict | None:
    """The fetch step for its anchor, while nobody has laid a hand on it and its hall is another place."""
    from realmwalker.game import quests

    home = adv["places"].get("home") or {}
    if "site" not in home:
        return None
    for ch in adv["chapters"]:
        for st in ch["steps"]:
            if st["kind"] != "fetch" or st["state"] != "open" or "key:anchor" not in st.get("gives", []):
                continue
            if int(st["target"]["place"].get("site", -1)) == int(home["site"]) or st.get("moved"):
                return None
            q = quests.by_id(game, st.get("quest")) if st.get("quest") else None
            if q is not None and q["target"].get("placed"):
                return None
            return st
    return None


def move_relic(game, adv: dict) -> list[str]:
    """It takes its anchor into its own hall: the fetch step's thing lies now on the first level under its home."""
    from realmwalker.game.story import deeds, places

    st = relic_movable(game, adv)
    if st is None:
        return []
    home = adv["places"]["home"]
    place = {"site": int(home["site"]), "part": "level", "level": 1}
    st["target"].update({"place": place, "level": places.dungeon_key(game.world, place), "n": 1})
    st["moved"] = int(game.moment.total_days)
    if st.get("quest"):
        game.quests[:] = [q for q in game.quests if q.get("id") != st["quest"]]
        st.pop("quest", None)
        st["set"] = False
        if any(s is st for s in _story().open_steps(adv)):
            st["set"] = True
            deeds._setup_fetch(game, adv, st)
    rng = game.world.rng.child(f"early/relic/{adv['id']}")
    lst = spec(game).get("relic") or ["{villain_short} has taken {his} anchor home to {home}."]
    line = _fill(game, adv, lst, rng)
    _story().journal(adv, line, int(game.moment.total_days))
    return [f"<warn>{esc(line)}</>"]
