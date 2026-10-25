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
    from realmwalker.game.story import villain

    if beat_id in villain.SEEN_IN and adventure(game, rec) is not None:  # (it showed itself: E.7)
        villain.seen(game, adventure(game, rec))
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
    text = list(beat["text"])
    own = (beat.get("tempers") or {}).get(_villain(game, rec).get("temper") or "")
    if own:  # (a temper's own first page: a zealot's letter does not read like a cruel man's, E.7)
        text[0] = own
    return [tidy(textgen.fill(rng.choice(page), rng, tables, words)) for page in text]


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
    if cond == "party_room":
        return "your company is full"
    if cond == "ally_loyal":
        return "they do not think well enough of you"
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
    if "chapter" in value and adv["chapters"][adv["chapter"]]["id"] not in (
            value["chapter"] if isinstance(value["chapter"], list) else [value["chapter"]]):
        return False
    if value.get("at_large") and (adv.get("boss_fled") or adv.get("boss_dead")):
        return False  # (gone to ground, hurt: it no longer comes looking for you)
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
        out = [f"<good>Something to remember for the end of this: {_key_words(game, adv, k)}.</>"]
        if k == "ally":
            from realmwalker.game.story import stakes

            out += stakes.join(game, adv)  # (their stake, and a place in the party or by the patron: F.1)
        return out
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


@op("endure")
def _endure(game, rec, *args):
    """A set piece's battle (an endure step's beat): its band, here and now (E.4)."""
    from realmwalker.game import story
    from realmwalker.game.story import deeds

    adv = adventure(game, rec)
    if adv is None or adv["state"] != "active":
        return []
    return deeds.endure(game, adv, story.find_step(game, adv["id"], rec.get("step")))


@op("move_relic")
def _move_relic(game, rec, *args):
    """It takes its anchor into its own hall (the move relic_moved, E.4)."""
    from realmwalker.game.story import early

    adv = adventure(game, rec)
    return early.move_relic(game, adv) if adv is not None and adv["state"] == "active" else []


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


# ---------------------------------------------------------------------------- the Risen and the Outlaw Lord (D.3)
@condition("key")
def _has_key(game, rec, value) -> bool:
    adv = adventure(game, rec)
    have = set(adv["keys"]) if adv else set()
    return all(k in have for k in (value if isinstance(value, list) else [value]))


@op("letter")
def _letter(game, rec, key: str, hand: str = "dark"):
    """A letter put in your hand (the villain's in an old hand, a warning nailed to your door): its words are the
    adventures.json words table `key` (paragraphs split by a blank line), signed by the villain; its page opens
    (game/letters.py), and it is kept in the pack to be read again."""
    from realmwalker.game import letters

    lines = game.tables.adventures.get("words", {}).get(key)
    if not lines:
        return []
    rng = rng_for(game, rec).child(f"letter/{key}")
    words = {k: str(v) for k, v in words_for(game, rec).items()}
    tables = game.tables.adventures.get("words", {})
    paragraphs = [tidy(textgen.fill(p, rng, tables, words)) for p in rng.choice(list(lines)).split("\n\n")]
    sender = words.get("villain", "someone who does not sign")
    adv = adventure(game, rec)
    if hand in ("dark", "villain") and adv is not None:  # (in the villain's own hand: its temper's ink and seal, E.2)
        from realmwalker.game.story import villain

        own = villain.hand(game, adv)
        lid = letters.write(game, sender=sender, lines=paragraphs, hand=own["hand"], seal=own["seal"], ink=own["ink"],
                            sigil=own["sigil"])
    else:
        lid = letters.write(game, sender=sender, lines=paragraphs, hand=letters.hand_for(hand))
    letters.give(game, lid)
    letters.show(game, lid)
    return ["<loot>You keep the letter.</>"]


@op("finish")
def _finish(game, rec, *args):
    """The tale ends here, without its last fight (the rite done, the parley won): its ending and epilogue."""
    from realmwalker.game import story
    from realmwalker.game.story import endings

    adv = adventure(game, rec)
    if adv is None or adv["state"] != "active":
        return []
    for st in story.open_steps(adv):
        if st["kind"] in ("finale", "slay"):
            st["state"] = "done"
    return endings.finish(game, adv)


# ---------------------------------------------------------------------------- the villain's moves (E.1)
@condition("villain.minions")
def _villain_minions(game, rec, value) -> bool:
    """Its kind has servants to send without it (threats.json kind `minions`)."""
    return bool(_minions(game, rec)) == bool(value)


def _minions(game, rec) -> str | None:
    from realmwalker.world import threats

    adv = adventure(game, rec)
    t = threats.records(game.world).get(adv["threat"]) if adv else None
    group = game.tables.threats["kinds"].get(t["kind"], {}).get("minions") if t else None
    return group if group in game.tables.creatures.encounters else None


@condition("villain.breaks_off")
def _villain_breaks_off(game, rec, value) -> bool:
    """Met before its finale, it breaks off when hurt (its boss template's `before`): it may come in person."""
    from realmwalker.game.story import finale

    adv = adventure(game, rec)
    boss = finale.template_for(game.tables, adv) if adv and (adv.get("finale") or {}).get("template") in         game.tables.villains.get("bosses", {}) else None
    return bool((boss or {}).get("before")) == bool(value)


@op("strike")
def _strike(game, rec, *args):
    """Its servants in force (a band of its kind's `minions` and half another), each with the story tag: a fight here
    and now."""
    from realmwalker.game.encounters import make_encounter

    group = _minions(game, rec)
    if group is None or game.over is not None:
        return []
    rng = rng_for(game, rec).child("strike")
    enc = make_encounter(game, group, rng)
    more = make_encounter(game, group, rng.child("more")).creatures
    enc.creatures += more[:(len(more) + 1) // 2]
    if not enc.creatures:
        return []
    enc.attitude = "hostile"  # (sent to fight: never a band you may pass by)
    for c in enc.creatures:
        c.story = {"adv": rec.get("adv"), "role": "minion"}
    game.encounter = enc
    game.travel = None
    return []


@op("band")
def _band(game, rec, group: str):
    """A band of its servants (a test): a fight with the story tag, so that the villain hears of their deaths."""
    from realmwalker.game.encounters import make_encounter

    if group not in game.tables.creatures.encounters or game.over is not None:
        return []
    enc = make_encounter(game, group, rng_for(game, rec).child(f"band/{group}"))
    enc.attitude = "hostile"  # (sent to test you)
    for c in enc.creatures:
        c.story = {"adv": rec.get("adv"), "role": "minion"}
    game.encounter = enc
    game.travel = None
    return []


@op("reprisal")
def _reprisal(game, rec, how: str = "hanged"):
    """One who helped you pays for it (villain.due_move chose them: adv["reprisal"]): dead, and the news goes out
    from their town; their town shows it (villain.pay)."""
    from realmwalker.game.story import villain

    adv = adventure(game, rec)
    npc = game.world.npcs.get(int(adv["reprisal"])) if adv and adv.get("reprisal") is not None else None
    if npc is None or not npc.alive:
        return []
    villain.pay(game, adv, npc, how, words_for(game, rec))
    adv["reprisal"] = None
    return []


# ---------------------------------------------------------------------------- invitations, bargains, wedges, frames
# and kidnaps (E.2)
@condition("helper")
def _has_helper(game, rec, value) -> bool:
    """One who helped you stands to pay for it (the move chose them: adv["reprisal"])."""
    adv = adventure(game, rec)
    npc = game.world.npcs.get(int(adv["reprisal"])) if adv and adv.get("reprisal") is not None else None
    return (npc is not None and bool(npc.alive)) == bool(value)


@op("invite")
def _invite(game, rec, days: int = 6, beat: str = "villain_dinner"):
    """Its invitation taken: safe conduct to its hall for `days` (no band troubles you on the road there), and the
    dinner (`beat`) when you arrive."""
    adv = adventure(game, rec)
    if adv is None:
        return []
    from realmwalker.game.story import places

    today = int(game.moment.total_days)
    p = game.player
    home = adv["places"].get("home")
    dist = places.dist(game.world, home, {"tile": [p.x, p.y]}) if home else None
    adv["invited"] = {"day": today, "until": today + int(days), "state": "going", "beat": beat, "dist": dist}
    hall = words_for(game, rec).get("home", "its hall")
    return [f"<warn>Safe conduct: nothing will trouble you on the road to {textgen.escape_markup(hall)} for "
            f"{int(days)} days.</>"]


@op("conduct")
def _conduct(game, rec, days: int = 2):
    """After the dinner: safe conduct home again for `days`, and then it is over."""
    adv = adventure(game, rec)
    if adv is None or not adv.get("invited"):
        return []
    if int(days) <= 0:  # (guest-right broken at its table: no conduct at all)
        adv.pop("invited", None)
        return []
    today = int(game.moment.total_days)
    adv["invited"].update({"state": "home", "until": today + int(days)})
    adv.setdefault("dined", []).append(today)
    return [f"<dim>Its safe conduct holds for {int(days)} days more.</>"]


@op("loyalty")
def _loyalty(game, rec, n: int):
    """The companion its wedge was driven at grows closer to you (or further)."""
    from realmwalker.game.companions import change_loyalty
    from realmwalker.game.story import villain

    adv = adventure(game, rec)
    c = villain.tempted(game, adv) if adv else None
    if c is not None:
        change_loyalty(c, float(n))
    return []


@op("betray")
def _betray(game, rec):
    """The companion its wedge was driven at goes over to it: gone in the night, and what you knew goes with them (a
    key of the tale lost)."""
    from realmwalker.game import companions
    from realmwalker.game.story import villain

    adv = adventure(game, rec)
    c = villain.tempted(game, adv) if adv else None
    if c is None:
        return []
    lines = companions.dismiss(game, c, deserted=True)
    lost = None
    keys = sorted(adv["keys"])
    if keys:
        lost = rng_for(game, rec).child("betray").choice(keys)
        adv["keys"].remove(lost)
    adv["turned"] = {"name": c.name, "key": lost, "day": int(game.moment.total_days)}
    if "betrayed" not in adv["flags"]:
        adv["flags"].append("betrayed")
    out = [f"<danger>{textgen.escape_markup(x)}</>" for x in lines]
    if lost:
        from realmwalker.game.story import words as wordsmod

        out.append(f"<danger>{textgen.escape_markup(villain.name_of(game, adv))} knows of "
                   f"{textgen.escape_markup(wordsmod.key_text(game, adv, lost))} now.</>")
    return out


@op("frame")
def _frame(game, rec, crime: str = "murder"):
    """It does a murder in a town under a lord's law (villain.due_move chose it: adv["frame"]) and false witnesses
    swear it was you: the crime is on your record there, reported, with a price on your head until the truth comes
    out (the tale won: law.clear_framed)."""
    from realmwalker.game.story import villain

    adv = adventure(game, rec)
    if adv is not None:
        villain.frame(game, adv, crime)
    return []


@op("kidnap")
def _kidnap(game, rec):
    """One who helped you is taken to its hall (adv["reprisal"]): a rescue step is added to the chapter, with a
    short time to do it in (villain.kidnap)."""
    from realmwalker.game.story import villain

    adv = adventure(game, rec)
    if adv is None:
        return []
    name = villain.kidnap(game, adv)
    hall = words_for(game, rec).get("home", "its hall")
    return [f"<warn>{textgen.escape_markup(name)} is held in {textgen.escape_markup(hall)}.</>"] if name else []
