"""The beat language (docs/ADVENTURES.md §8.6): small scenes with pages and choices, played on the beat screen.

A beat is data (beats.json): where and when it may play (`when`: conditions), its pages of text (each a list of
variants, written with the adventure's words and nested tables), and its choices (a label, `requires`, a `check`
with success and failure, `ops`, the result's words). Both conditions and ops are whitelists, filled here with
`@condition` and `@op`; story/check.py reports anything a beat names that is not.

One beat waits at a time: `politics["director"]["pending"]` {beat, adv, step, words, n} (kept in the save, so quitting
in the middle of a beat brings it back). `offer` sets it; the game screen opens the beat screen while it waits
(`GameState.busy`); `choose` plays a choice and ends it. A beat that belongs to a step finishes that step.
"""

from __future__ import annotations

from realmwalker.core import textgen

CONDITIONS: dict[str, object] = {}
OPS: dict[str, object] = {}
WHERE = ("road", "wild", "town", "inn", "camp", "dungeon")


def condition(name: str):
    """fn(game, ctx, value) -> bool"""
    def wrap(fn):
        CONDITIONS[name] = fn
        return fn
    return wrap


def op(name: str):
    """fn(game, ctx, *args) -> list of lines said"""
    def wrap(fn):
        OPS[name] = fn
        return fn
    return wrap


# ---------------------------------------------------------------------------- the waiting beat
def director(world) -> dict:
    return world.politics.setdefault("director", {})


def pending(game) -> dict | None:
    return director(game.world).get("pending")


def adventure(game, ctx: dict) -> dict | None:
    aid = (ctx or {}).get("adv")
    return game.world.politics.get("adventures", {}).get(aid) if aid else None


def offer(game, beat_id: str, *, adv: str | None = None, step: str | None = None, where: str = "",
          words: dict | None = None) -> dict:
    """Make a beat wait for the player (the game screen opens it). Returns the pending record."""
    d = director(game.world)
    n = int(d.get("n", 0)) + 1
    d["n"] = n
    rec = {"beat": beat_id, "adv": adv, "step": step, "where": where, "n": n, "words": dict(words or {}),
           "day": int(game.moment.total_days)}
    d["pending"] = rec
    seen = d.setdefault("seen", {})
    seen[beat_id] = int(game.moment.total_days)
    return rec


def rng_for(game, rec: dict):
    return game.world.rng.child(f"beat/{rec['n']}")


def words_for(game, rec: dict) -> dict:
    """The words a beat is written with: the adventure's (villain, home, town...), the hero's, and its own."""
    from realmwalker.game.story import words as wordsmod

    out = wordsmod.for_adventure(game, adventure(game, rec))
    out.update(rec.get("words", {}))
    return out


def pages(game, rec: dict) -> list[str]:
    beat = game.tables.beats[rec["beat"]]
    rng = rng_for(game, rec)
    tables = game.tables.adventures.get("words", {})
    words = words_for(game, rec)
    return [tidy(textgen.fill(rng.choice(page), rng, tables, words)) for page in beat["text"]]


def title(game, rec: dict) -> str:
    beat = game.tables.beats[rec["beat"]]
    if beat.get("title"):
        rng = rng_for(game, rec)
        return tidy(textgen.fill(rng.choice(beat["title"]), rng, game.tables.adventures.get("words", {}),
                                 words_for(game, rec)))
    adv = adventure(game, rec)
    return adv["title"] if adv else ""


def tidy(text: str) -> str:
    text = text.strip()
    return text[:1].upper() + text[1:]


def choices(game, rec: dict) -> list[dict]:
    """The choices as the screen shows them: label, whether it can be taken now (and why not), the check."""
    beat = game.tables.beats[rec["beat"]]
    rng = rng_for(game, rec)
    tables = game.tables.adventures.get("words", {})
    words = words_for(game, rec)
    out = []
    for i, ch in enumerate(beat.get("choices", [])):
        ok, why = True, ""
        for cond, value in ch.get("requires", {}).items():
            if not CONDITIONS[cond](game, rec, value):
                ok, why = False, _why(game, cond, value)
                break
        check = ch.get("check")
        out.append({"i": i, "label": tidy(textgen.fill(rng.choice(ch["label"]), rng, tables, words)), "ok": ok,
                    "why": why, "check": check})
    if not out:
        out.append({"i": -1, "label": "Go on.", "ok": True, "why": "", "check": None})
    return out


def _why(game, cond: str, value) -> str:
    if cond == "item":
        names = [game.tables.items.get(i)["name"] for i in (value if isinstance(value, list) else [value])
                 if game.tables.items.get(i)]
        return f"needs {' or '.join(names) or 'something you do not have'}"
    if cond == "money":
        from realmwalker.game.economy import money_text

        return f"needs {money_text(int(value))}"
    return "not now"


def choose(game, rec: dict, i: int) -> list[str]:
    """Play choice i (or -1, a beat with no choices): the check, the ops, the words of what happened. Ends the
    beat; a beat that belongs to a step finishes it."""
    beat = game.tables.beats[rec["beat"]]
    rng = rng_for(game, rec).child("choice")
    tables = game.tables.adventures.get("words", {})
    words = words_for(game, rec)
    lines: list[str] = []
    ops = list(beat.get("ops", []))
    said = []
    if 0 <= i < len(beat.get("choices", [])):
        ch = beat["choices"][i]
        ops += ch.get("ops", [])
        said = ch.get("result", [])
        if ch.get("check"):
            ok, roll = _check(game, rec, ch["check"])
            lines.append(roll)
            ops += ch["success"] if ok else ch["failure"]
            if not ok and ch.get("fail_result"):
                said = ch["fail_result"]
    if said:
        lines.append(tidy(textgen.fill(rng.choice(said), rng, tables, words)))
    for o in ops:
        lines += OPS[o[0]](game, rec, *o[1:]) or []
    director(game.world)["pending"] = None
    if rec.get("step"):
        from realmwalker.game import story
        from realmwalker.game.story.steps import STEPS

        st = story.find_step(game, rec["adv"], rec["step"])
        if st is not None and STEPS[st["kind"]].beat_finishes:
            story.step_done(game, rec["adv"], rec["step"])
    from realmwalker.game import story

    story.after_beat(game)
    return [x for x in lines if x]


def _check(game, rec: dict, check: dict) -> tuple[bool, str]:
    """A beat's check: through a conversation when a person is speaking, else as a camp check."""
    from realmwalker.game import camp

    ok, text = camp.check(game, check["skill"], int(check["dc"]), tag=f"beat:{rec['beat']}")
    return ok, text


# ---------------------------------------------------------------------------- conditions
@condition("where")
def _where(game, rec, value) -> bool:
    return rec.get("where", "") in (value if isinstance(value, list) else [value])


@condition("time")
def _time(game, rec, value) -> bool:
    hour = game.moment.hour
    part = "dawn" if 5 <= hour < 8 else "day" if 8 <= hour < 18 else "dusk" if 18 <= hour < 21 else "night"
    return part in (value if isinstance(value, list) else [value])


@condition("adventure")
def _adventure(game, rec, value) -> bool:
    adv = adventure(game, rec)
    if adv is None or adv["state"] != "active":
        return False
    if "blueprint" in value and adv["blueprint"] not in (value["blueprint"] if isinstance(value["blueprint"], list)
                                                          else [value["blueprint"]]):
        return False
    if "chapter" in value and adv["chapters"][adv["chapter"]]["id"] != value["chapter"]:
        return False
    return True


@condition("attention")
def _attention(game, rec, value) -> bool:
    adv = adventure(game, rec)
    return adv is not None and int(value[0]) <= int(adv.get("attention", 0)) <= int(value[1])


def _villain(game, rec) -> dict:
    from realmwalker.world import threats

    adv = adventure(game, rec)
    t = threats.records(game.world).get(adv["threat"]) if adv else None
    return t["villain"] if t else {}


@condition("villain.speaks")
def _villain_speaks(game, rec, value) -> bool:
    temper = _villain(game, rec).get("temper")
    spec = game.tables.villains.get("tempers", {}).get(temper or "", {})
    return bool(spec.get("speaks", False)) == bool(value)


@condition("villain.temper")
def _villain_temper(game, rec, value) -> bool:
    return _villain(game, rec).get("temper") in (value if isinstance(value, list) else [value])


@condition("villain.kind")
def _villain_kind(game, rec, value) -> bool:
    from realmwalker.world import threats

    adv = adventure(game, rec)
    t = threats.records(game.world).get(adv["threat"]) if adv else None
    return t is not None and t["kind"] in (value if isinstance(value, list) else [value])


@condition("flag")
def _flag(game, rec, value) -> bool:
    adv = adventure(game, rec)
    have = set(adv["flags"]) if adv else set()
    return all(f in have for f in (value if isinstance(value, list) else [value]))


@condition("cooldown")
def _cooldown(game, rec, value) -> bool:
    seen = director(game.world).get("seen", {}).get(rec.get("beat", ""))
    return seen is None or game.moment.total_days - int(seen) >= int(value)


@condition("once")
def _once(game, rec, value) -> bool:
    return not value or rec.get("beat", "") not in director(game.world).get("seen", {})


@condition("chance")
def _chance(game, rec, value) -> bool:
    return game.world.rng.child(f"beat-chance/{rec.get('beat')}/{game.moment.total_days}").chance(float(value))


@condition("item")
def _item(game, rec, value) -> bool:
    ids = value if isinstance(value, list) else [value]
    return any(it.def_id in ids for c in game.party for it in c.inventory)


@condition("money")
def _money(game, rec, value) -> bool:
    return sum(c.money for c in game.party) >= int(value)


def eligible(game, beat_id: str, rec: dict) -> bool:
    beat = game.tables.beats[beat_id]
    probe = dict(rec, beat=beat_id)
    if beat.get("where") and rec.get("where") not in beat["where"]:
        return False
    if beat.get("time") and not _time(game, probe, beat["time"]):
        return False
    return all(CONDITIONS[k](game, probe, v) for k, v in beat.get("when", {}).items())


# ---------------------------------------------------------------------------- ops
def _outcome(key: str):
    def fn(game, rec, *args):
        from realmwalker.game.events import apply_outcome

        value = args[0] if len(args) == 1 else list(args)
        return apply_outcome(game, {key: value}, rng_for(game, rec).child(f"op/{key}"))
    fn.__name__ = f"_op_{key}"
    return fn


for _key in ("items", "money", "loot", "fatigue", "effect", "deed", "news", "xp", "hurt", "time", "fight",
             "ambush"):
    op(_key)(_outcome(_key))


@op("text")
def _text(game, rec, *lines):
    rng = rng_for(game, rec).child("text")
    return [tidy(textgen.fill(rng.choice(list(lines)), rng, game.tables.adventures.get("words", {}),
                              words_for(game, rec)))]


@op("clue")
def _clue(game, rec, truth: str, n: int = 1):
    adv = adventure(game, rec)
    if adv is not None:
        adv["clues"][truth] = int(adv["clues"].get(truth, 0)) + int(n)
    return []


@op("key")
def _key(game, rec, k: str):
    adv = adventure(game, rec)
    if adv is not None and k not in adv["keys"]:
        adv["keys"].append(k)
        return [f"<good>Something to remember for the end of this: {_key_words(game, adv, k)}.</>"]
    return []


def _key_words(game, adv: dict, k: str) -> str:
    from realmwalker.game.story import words as wordsmod

    return wordsmod.key_text(game, adv, k)


@op("flag")
def _flag_op(game, rec, f: str):
    adv = adventure(game, rec)
    if adv is not None and f not in adv["flags"]:
        adv["flags"].append(f)
    return []


@op("step_done")
def _step_done(game, rec, sid: str | None = None):
    from realmwalker.game import story

    if rec.get("adv"):
        story.step_done(game, rec["adv"], sid or rec.get("step"))
    return []


@op("attention")
def _attention_op(game, rec, n: int):
    from realmwalker.game.story import villain

    adv = adventure(game, rec)
    if adv is not None:
        villain.notice(game, adv, int(n))
    return []


@op("clock")
def _clock(game, rec, days: int):
    """Hold the scheme (a negative number of days holds it that long; a positive one hastens its next stage)."""
    from realmwalker.world import news, threats

    adv = adventure(game, rec)
    t = threats.records(game.world).get(adv["threat"]) if adv else None
    if t is None or t["state"] not in threats.LIVE:
        return []
    now = news.now_days(game.world)
    if int(days) < 0:
        t["scheme"]["held_until"] = max(float(t["scheme"].get("held_until") or now), now) - int(days)
    else:
        t["scheme"]["next"] = max(now, float(t["scheme"]["next"]) - int(days))
    return []


@op("schedule")
def _schedule(game, rec, beat: str, days: int):
    director(game.world).setdefault("scheduled", []).append(
        {"day": int(game.moment.total_days) + int(days), "beat": beat, "adv": rec.get("adv")})
    return []


@op("named_fight")
def _named_fight(game, rec, role: str):
    """The story's own foe, met here and now (the beast at the bait): an encounter with the story tag."""
    from realmwalker.game import story

    return story.named_encounter(game, adventure(game, rec), role)


@op("item")
def _item_op(game, rec, item_id: str, n: int = 1):
    from realmwalker.rules.inventory import add_item

    if game.tables.items.get(item_id) is None:
        return []
    add_item(game.leader, game.tables.items, item_id, int(n), made_at=game.world.time)
    return [f"<loot>You take {game.tables.items.get(item_id)['name']}.</>"]


@op("take_hook")
def _take_hook(game, rec, *args):
    from realmwalker.game import story

    return story.take_hook(game, rec.get("words", {}).get("threat", ""))


@op("decline_hook")
def _decline_hook(game, rec, *args):
    return []  # (the offer stays on the threat: the board and its people may ask again)


@op("use")
def _use(game, rec, *item_ids):
    """One of these things is used up (the bait laid out, the meat thrown): the first anyone in the party carries."""
    for c in game.party:
        for it in list(c.inventory):
            if it.def_id in item_ids:
                if getattr(it, "qty", 1) > 1:
                    it.qty -= 1
                else:
                    c.inventory.remove(it)
                return [f"<dim>({game.tables.items.get(it.def_id)['name']} used.)</>"]
    return []


@op("companions")
def _companions(game, rec, *tags):
    if game.party[1:]:
        from realmwalker.game.companions import react

        react(game, *tags)
    return []
