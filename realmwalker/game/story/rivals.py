"""Rivals (Expansion 6 F.2, docs/ADVENTURES.md §5.6): a band that wants the same prize as you, on its own clock.

A tale may have a rival (adventures.rivals.json `chance` by blueprint, decided once, the first day it is active):
a hero of the land with companions (a living hero of the history when there is one), a band of deserters, or a lord's
child with paid swords. The record is `adv["rival"]` (None: this tale has none) {kind, name, first, sex, figure,
child, who, band_words, relation (-2 to 2), state, made, met, due, prize, last, seen, lost, sold, holds, helping,
pinned_until, in_lair, found, hurt, fought, fate}.

The prize is the tale's thing to fetch (an open fetch step whose quest is out) or, without one, the villain's head.
Once met (the beat "rival_meeting" at an inn or a camp a day or more into the tale) their race runs `race_days`: on
the day it ends (`daily`), if the prize is still to be had, they reach it first. A thing to fetch is then theirs (its
chest is found emptied: quests.on_chest) until you buy it, are given it, take it from them, or let it go (its step
fails). The villain's hall they do not come out of: they are found dead there by the party (`on_descend`: the beat
"rival_found_dead" and their bones on the floor), the most chilling sign of all, and the villain carries the wounds
they gave it into the finale (`wounds` of its hit points).

Their relation to you decides how they show up (`on_night`, every `every` days at most, `event_chance` a night):
at 2 or under a truce, a plea for help once the second chapter has begun (a fight here and now beside them against
the villain's servants: `to_battle`; refused or lost, they are overrun); at 1 an offered truce; at 0 the race (a truce
proposed, their camp sabotaged, or let be); at -1 a theft, and once the second chapter has begun the sale of your
road to the villain (its attention, and no surprising it at the finale); at -2 an ambush at night. A truce gives the
key "rival": they come to the finale on its second round (`at_finale`). Fights with them are bands tagged with the
tale (role "rival"); `on_battle` follows them. The epilogue names them (`after_tale`, `fates`).

    decide(game, adv)   daily(game)   on_night(game, where)   on_descend(game, lm)   to_battle(battle, game, advs)
    at_finale(battle, game, adv, boss)   on_battle(game, result)   after_tale(game, adv)   journal_line(game, adv)
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.game.story.beats import condition, op

LIVE = ("unmet", "racing", "ahead", "truce", "pinned")
STATES = LIVE + ("dead", "slain", "gone", "bought")
BEATS = ("rival_meeting", "rival_race", "rival_truce", "rival_theft", "rival_sold", "rival_ambush", "rival_plea",
         "rival_prize", "rival_found_dead")
THEFT = 0.25  # of the party's coin a theft takes (at most the tier's price)
PLEA_DAYS = 2  # how long they hold out once pinned, waiting for you
ARRIVE_ROUND = 3  # the round of the finale a rival under truce comes on


def spec(game) -> dict:
    return game.tables.adventures.get("rivals") or {}


def _story():
    from realmwalker.game import story

    return story


def _today(game) -> int:
    return int(game.moment.total_days)


def _adv(game, rec) -> dict | None:
    return _story().adventures(game.world).get((rec or {}).get("adv") or "")


def live(adv: dict) -> dict | None:
    rec = adv.get("rival")
    return rec if rec and rec["state"] in LIVE else None


# ---------------------------------------------------------------------------- who they are
def decide(game, adv: dict) -> None:
    """Whether this tale has a rival, and who: decided once (the first day the tale is active)."""
    if "rival" in adv:
        return
    sp = spec(game)
    rng = game.world.rng.child(f"rival/{adv['id']}")
    if not sp or not rng.chance(float(sp["chance"].get(adv["blueprint"], 0.0))):
        adv["rival"] = None
        return
    kinds = sorted(k for k, v in sp["kinds"].items() if int(v["weight"]) > 0)
    kind = rng.weighted(kinds, [float(sp["kinds"][k]["weight"]) for k in kinds])
    ks = sp["kinds"][kind]
    rec = {"kind": kind, "relation": int(ks["relation"]), "state": "unmet", "made": _today(game), "met": None,
           "due": None, "prize": None, "last": _today(game), "seen": [], "lost": 0, "sold": False, "holds": False,
           "helping": False, "pinned_until": None, "in_lair": False, "found": False, "hurt": 0.0, "fought": False,
           "fate": None, "figure": None, "child": ""}
    fig = _hero_figure(game) if kind == "hero" else None
    if fig is not None:
        rec.update(name=fig.name, sex=fig.sex, figure=int(fig.id))
    else:
        from realmwalker.world.names import forge

        culture = _culture(game, adv)
        sex = rng.choice(["male", "female"])
        nf = forge(game.world, game.tables)
        rec.update(name=nf.person(culture, sex, rng.child("name"), noble=bool(ks.get("noble"))), sex=sex)
    rec["first"] = rec["name"].split()[0]
    if ks.get("noble"):
        rec["child"] = "daughter" if rec["sex"] == "female" else "son"
    adv["rival"] = rec
    words = _words(game, adv)
    tables = game.tables.adventures.get("words", {})
    rec["who"] = textgen.fill(rng.choice(ks["who"]), rng, tables, words)
    rec["band_words"] = textgen.fill(rng.choice(ks["band_words"]), rng, tables, _words(game, adv))


def riding(world) -> set[int]:
    """The hero figures of the history riding as a tale's rival (people.heroes_at_the_inn leaves them out)."""
    advs = world.politics.get("adventures", {}).values()
    return {int(a["rival"]["figure"]) for a in advs if a.get("rival") and a["rival"].get("figure") is not None}


def _hero_figure(game):
    """A living hero of the history, free to ride (not at an inn as a townsperson, not another tale's rival)."""
    w = game.world
    taken = riding(w)
    pool = [f for f in w.figures.values() if f.alive and f.kind == "person" and f.job in ("adventurer", "hero")
            and f.id not in taken and (f.npc < 0 or f.npc not in w.npcs or not w.npcs[f.npc].alive)]
    return max(pool, key=lambda f: (f.fame, -f.id)) if pool else None


def _culture(game, adv: dict) -> str:
    from realmwalker.game.story import places

    w = game.world
    at = places.xy(w, adv["places"].get("town") or adv["places"]["home"])
    town = min(w.settlements, key=lambda s: (abs(s.x - at[0]) + abs(s.y - at[1]), s.id))
    return town.culture


def _words(game, adv: dict) -> dict:
    """The tale's words with the rival's: {rival}, {rival_full}, {rival_band}, {rival_who}, {prize}, {price},
    {child}, and the leader's pronouns ({they} walk{s}, {they} go{es}, {theirs})."""
    from realmwalker.game.story import words as wordsmod
    from realmwalker.rules.items import money_text

    out = {k: v for k, v in wordsmod.for_adventure(game, adv).items() if isinstance(v, str)}
    rec = adv.get("rival") or {}
    if rec:
        p = textgen.pronoun_values(rec.get("sex", ""))
        p["es"] = "es" if p["s"] else ""
        p["theirs"] = {"he": "his", "she": "hers"}.get(p["they"], "theirs")
        out.update(p)
        out.update(rival=rec["first"], rival_full=rec["name"], child=rec.get("child") or "child",
                   rival_who=rec.get("who") or "", rival_band=rec.get("band_words") or f"{rec['first']}'s band",
                   prize=prize_name(game, adv), price=money_text(price(game, adv)))
    return out


def prize_name(game, adv: dict) -> str:
    q = _prize_quest(game, adv)
    if q is not None:
        return q["target"].get("item", "the prize")
    from realmwalker.game.story import words as wordsmod

    w = wordsmod.for_adventure(game, adv)
    return f"{w['villain_short']}'s head" if "villain_short" in w else "the prize"


def price(game, adv: dict) -> int:
    tier = max(1, min(4, int(adv.get("tier", 1))))
    return int(spec(game)["clock"]["price"][tier - 1])


def _prize_step(adv: dict) -> dict | None:
    rec = adv.get("rival") or {}
    sid = rec.get("prize") or rec.get("will")
    if not sid or sid == "finale":
        return None
    return next((s for ch in adv["chapters"] for s in ch["steps"] if s["id"] == sid), None)


def _prize_quest(game, adv: dict) -> dict | None:
    from realmwalker.game import quests

    st = _prize_step(adv)
    return quests.by_id(game, st.get("quest")) if st is not None and st.get("quest") else None


def _pick_prize(game, adv: dict) -> str:
    """The thing to fetch whose quest is out (an open fetch step), else the villain's head ("finale")."""
    from realmwalker.game import quests

    for st in _story().open_steps(adv):
        q = quests.by_id(game, st.get("quest")) if st["kind"] == "fetch" and st.get("quest") else None
        if q is not None and not q["done"]:
            return st["id"]
    return "finale"


def _say(game, adv: dict, lines, rng) -> str:
    text = textgen.fill(rng.choice(list(lines)), rng, game.tables.adventures.get("words", {}), _words(game, adv))
    return text[:1].upper() + text[1:]


def _line(game, adv: dict, text: str) -> str:
    """One of this module's own lines, with the rival's words (never a beat's)."""
    return _say(game, adv, [text], game.world.rng.child(f"rival-line/{adv['id']}"))


# ---------------------------------------------------------------------------- their clock
def daily(game) -> None:
    """Once a day (story.daily): a rival decided for each tale; a race run to its end; a pinned band overrun."""
    today = _today(game)
    for adv in _story().active(game):
        decide(game, adv)
        rec = live(adv)
        if rec is None:
            continue
        if rec.get("helping") and game.encounter is None and getattr(game, "battle", None) is None:
            rec["helping"] = False  # (the plea was never fought out: nobody came)
            _overrun(game, adv, rec)
            continue
        if rec["state"] == "pinned" and rec.get("pinned_until") is not None and today > int(rec["pinned_until"]):
            _overrun(game, adv, rec)
            continue
        if rec["state"] != "racing" or rec.get("due") is None:
            continue
        st = _prize_step(adv)
        if st is not None and st["state"] != "open":  # (you were quicker: now they want its head)
            _race(game, adv, rec, "finale")
            continue
        if today >= int(rec["due"]):
            _arrives(game, adv, rec)


def _race(game, adv: dict, rec: dict, prize: str | None = None) -> None:
    lo, hi = spec(game)["clock"]["race_days"]
    rng = game.world.rng.child(f"rival-race/{adv['id']}/{_today(game)}")
    rec["prize"] = prize or rec.pop("will", None) or _pick_prize(game, adv)
    rec["due"] = _today(game) + rng.randint(int(lo), int(hi))


def _arrives(game, adv: dict, rec: dict) -> None:
    """Their race is run: they reach the prize first."""
    if rec["prize"] != "finale":
        q = _prize_quest(game, adv)
        if q is None or q["done"]:
            _race(game, adv, rec, "finale")
            return
        q["target"]["rival"] = True  # (its chest is found forced and empty)
        rec["state"], rec["holds"] = "ahead", True
        _story().journal(adv, esc(_line(game, adv, "{rival_full} reached {prize} before you, and has it.")),
                         _today(game))
        game.say(f"<warn>{esc(_line(game, adv, 'Word on the road: {rival_full} has {prize}. You were too slow.'))}</>",
                 "story")
        return
    if not _villain_alive(game, adv):
        rec["state"], rec["fate"] = "gone", "late"  # (it is dead already: they came too late for anything)
        return
    rec["state"], rec["in_lair"] = "dead", True
    rec["hurt"] = float(spec(game)["clock"]["wounds"])
    _figure_dies(game, adv, rec, "lost in " + _words(game, adv).get("home", "the dark"))
    _story().journal(adv, esc(_line(game, adv, "{rival_band} went into {home} ahead of you. None came out.")),
                     _today(game))
    game.say(f"<warn>{esc(_line(game, adv, '{rival_band} went up to {home} three days ago. Nobody has come down.'))}</>",
             "story")


def _drop_key(adv: dict) -> None:
    """A truce with the dead holds nothing: the key "rival" goes with them."""
    if "rival" in adv["keys"]:
        adv["keys"].remove("rival")


def _overrun(game, adv: dict, rec: dict) -> None:
    rec["state"], rec["pinned_until"], rec["fate"] = "dead", None, "overrun"
    _drop_key(adv)
    _figure_dies(game, adv, rec, "overrun on the road")
    _story().journal(adv, esc(_line(game, adv, "{rival_band} were overrun, waiting for you.")), _today(game))
    game.say(f"<warn>{esc(_line(game, adv, 'Word comes: {rival_band} were overrun where they stood. Nobody came.'))}</>",
             "story")


def _figure_dies(game, adv: dict, rec: dict, cause: str) -> None:
    fig = game.world.figures.get(rec["figure"]) if rec.get("figure") is not None else None
    if fig is not None and fig.alive:
        fig.died = game.moment.year
        fig.cause = cause


# ---------------------------------------------------------------------------- how they show up
def on_night(game, where: str, *, morning: bool = True) -> bool:
    """A night at camp or at the inn (story.on_night): the rival's next beat, if one is due. True when one waits.
    Only the ambush comes in the dark and breaks the rest; the rest wait for the morning (`morning`)."""
    from realmwalker.game.story import beats

    sp = spec(game)
    if not sp or beats.pending(game) is not None or where not in ("inn", "camp"):
        return False
    today = _today(game)
    clock = sp["clock"]
    for adv in _story().active(game):
        rec = live(adv)
        if rec is None:
            continue
        if rec["state"] == "unmet":
            if morning and today - int(rec["made"]) >= int(clock["meet_after"]):
                rec["will"] = _pick_prize(game, adv)  # (what the meeting names; the race takes it up)
                return _offer(game, adv, rec, "rival_meeting", where)
            continue
        if rec["state"] == "ahead":  # (offered again, every few days, until it is settled)
            if morning and "rival_prize" not in rec["seen"] or today - int(rec["last"]) >= int(clock["every"]):
                return _offer(game, adv, rec, "rival_prize", where)
            continue
        if today - int(rec["last"]) < int(clock["every"]):
            continue
        if not game.world.rng.child(f"rival-night/{adv['id']}/{today}").chance(float(clock["event_chance"])):
            continue
        beat = _due_beat(game, adv, rec, where)
        if beat is not None and (beat == "rival_ambush") != morning:
            return _offer(game, adv, rec, beat, where)
    return False


def _due_beat(game, adv: dict, rec: dict, where: str) -> str | None:
    """What their relation to you brings tonight, if anything."""
    from realmwalker.game.story import beats

    later = int(adv["chapter"]) >= 1 and not _in_finale(adv)
    seen, rel = rec["seen"], int(rec["relation"])
    if rec["state"] == "truce":
        if later and "rival_plea" not in seen and beats._minions(game, {"adv": adv["id"]}) is not None:
            return "rival_plea"
        return None
    if rec["state"] != "racing":
        return None
    if rel >= 1:  # (they come to your fire to offer it)
        return "rival_truce" if "rival_truce" not in seen and where == "camp" else None
    if rel == 0:
        return "rival_race" if "rival_race" not in seen else None
    if later and not rec["sold"] and "rival_sold" not in seen and _villain_alive(game, adv) and where == "inn":
        return "rival_sold"  # (heard in the common room)
    if rel <= -2 and where == "camp" and "rival_ambush" not in seen:
        return "rival_ambush"
    if where == "inn" and "rival_theft" not in seen and _coin(game) > 0:
        return "rival_theft"
    return None


def _in_finale(adv: dict) -> bool:
    ch = _story().chapter(adv)
    return ch is not None and any(st["kind"] == "finale" for st in ch["steps"])


def _villain_alive(game, adv: dict) -> bool:
    return not adv.get("boss_dead") and _story()._villain_alive(game, adv)


def _coin(game) -> int:
    return sum(c.money for c in game.party)


def _offer(game, adv: dict, rec: dict, beat: str, where: str) -> bool:
    from realmwalker.game.story import beats

    if beat not in game.tables.beats:
        return False
    rec["seen"].append(beat)
    rec["last"] = _today(game)
    beats.offer(game, beat, adv=adv["id"], where=where, words=_words(game, adv))
    return True


def on_descend(game, lm) -> None:
    """Down into a level of the villain's home: a rival who went in ahead of you lies here (the first level you
    come to after they died), with their band, and a beat says so."""
    from realmwalker.game.story import beats

    if beats.pending(game) is not None:
        return
    site = game.world.site_at(game.player.x, game.player.y)
    for adv in _story().active(game):
        rec = adv.get("rival")
        home = adv["places"].get("home") or {}
        if not rec or not rec.get("in_lair") or rec.get("found") or site is None or home.get("site") != site.id:
            continue
        rec["found"] = True
        _lay_bones(game, lm)
        beats.offer(game, "rival_found_dead", adv=adv["id"], where="dungeon", words=_words(game, adv))
        game.cue("dead")
        return


def _lay_bones(game, lm) -> None:
    """Their bones on the floor near the way in (the picture of it)."""
    from realmwalker.game.dungeon import set_terrain

    ex, ey = lm.entry
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    cells = sorted(((x, y) for x in range(ex - 4, ex + 5) for y in range(ey - 4, ey + 5)
                    if lm.in_bounds(x, y) and walk[x, y] and (x, y) not in lm.features and (x, y) != (ex, ey)
                    and abs(x - ex) + abs(y - ey) >= 2), key=lambda c: (abs(c[0] - ex) + abs(c[1] - ey), c))
    for x, y in cells[:4]:
        set_terrain(lm, x, y, "bones")


# ---------------------------------------------------------------------------- the beats' words
@condition("rival")
def _rival_cond(game, rec, value) -> bool:
    """The rival's relation to you is at least this."""
    adv = _adv(game, rec)
    r = (adv or {}).get("rival")
    return bool(r) and int(r["relation"]) >= int(value)


@condition("rival_price")
def _rival_price(game, rec, value) -> bool:
    """The party has the rival's price on it."""
    adv = _adv(game, rec)
    return adv is not None and (_coin(game) >= price(game, adv)) == bool(value)


def _relate(rec: dict, n: int) -> None:
    rec["relation"] = max(-2, min(2, int(rec["relation"]) + int(n)))


@op("rival")
def _rival_op(game, rec, what: str, n: int = 0):
    """The rival's story moves: met n (the meeting; relation n, their race begins), relation n, slow n (their race
    takes n days more), read (their road known: you hear when they will be there), truce (sworn: the key "rival"),
    steal (a share of your coin), recover (it back), sold (your road sold to the villain), fight (their band, here and
    now), pay_off (their price for a night), plea_go (a fight beside them against its servants), plea_refused
    (pinned, alone), buy, give, let_go (the prize they reached first), search (their bodies), honour."""
    adv = _adv(game, rec)
    r = (adv or {}).get("rival")
    if not r:
        return []
    out: list[str] = []
    story = _story()
    today = _today(game)
    if what == "met":
        r["met"] = today
        _relate(r, n)
        if r["state"] == "unmet":
            r["state"] = "racing"
            _race(game, adv, r)
        story.journal(adv, esc(_line(game, adv, "You met {rival_full}, who is after {prize} too.")), today)
    elif what == "relation":
        _relate(r, n)
    elif what == "slow" and r.get("due") is not None:
        r["due"] = int(r["due"]) + int(n)
    elif what == "read" and r.get("due") is not None:
        from realmwalker.game.quests import when_text

        out.append(f"<good>{esc(_line(game, adv, '{rival} means to be at {prize}'))} "
                   f"{esc(when_text(game, int(r['due'])))}.</>")
    elif what == "truce":
        r["state"], r["due"] = "truce", None
        r["relation"] = max(1, int(r["relation"]))
        if "rival" not in adv["keys"]:
            adv["keys"].append("rival")
        story.journal(adv, esc(_line(game, adv, "{rival_full} swore a truce with you: when you face it, {they} come{s}.")),
                      today)
    elif what == "steal":
        from realmwalker.game.law import take_money
        from realmwalker.rules.items import money_text

        want = min(price(game, adv), int(_coin(game) * THEFT))
        r["stolen"] = take_money(game, want)
        if r["stolen"]:
            out.append(f"<warn>{money_text(int(r['stolen']))} gone.</>")
    elif what == "recover":
        from realmwalker.rules.items import money_text

        back = int(r.pop("stolen", 0) or 0)
        game.leader.money += back
        if back:
            out.append(f"<loot>You take back {money_text(back)}.</>")
    elif what == "sold":
        r["sold"] = True
        story.journal(adv, esc(_line(game, adv, "{rival_full} sold your road to {villain_short}.")), today)
    elif what == "fight":
        out += _fight(game, adv, r)
    elif what == "pay_off":
        from realmwalker.game.law import take_money

        take_money(game, price(game, adv))
        _relate(r, 1)
    elif what == "plea_go":
        out += _plea(game, adv, r)
    elif what == "plea_refused":
        r["state"] = "pinned"
        r["pinned_until"] = today + PLEA_DAYS
        _relate(r, -1)
    elif what in ("buy", "give"):
        from realmwalker.game import quests

        q = _prize_quest(game, adv)
        if q is None or q["done"] or q.get("state") not in quests.LIVE:
            r["state"], r["holds"], r["fate"] = "gone", False, "prize"  # (too late for it: they keep it)
            return [f"<warn>{esc(_line(game, adv, 'It is no use to you now. {rival} keeps it.'))}</>"]
        if what == "buy":
            from realmwalker.game.law import take_money

            take_money(game, price(game, adv))
        out += _hand_over(game, adv, r)
        r["state"] = "bought" if what == "buy" else "truce"
        if what == "give":
            out += _rival_op(game, rec, "truce")
    elif what == "let_go":
        from realmwalker.game.story import deeds

        st = _prize_step(adv)
        r["state"] = "gone"
        r["fate"] = "prize"
        if st is not None:
            deeds.step_failed(game, adv, st, _line(game, adv, "You let {rival_full} keep {prize}."))
    elif what == "search":
        out += _search(game, adv, r)
    game.dirty = True
    return out


def _hand_over(game, adv: dict, r: dict) -> list[str]:
    """The thing they reached first is yours: made as its chest would have given it, and its job done."""
    from realmwalker.game import quests
    from realmwalker.rules.inventory import add_existing

    q = _prize_quest(game, adv)
    r["holds"] = False
    if q is None or q["done"]:
        return []
    item = quests.quest_item(game, q)
    q["target"].pop("rival", None)
    add_existing(game.leader, game.tables.items, item)
    quests.mark_done(game, q)
    from realmwalker.game.story import goals

    goals.notify(game, "item")
    return [f"<loot>You have {esc(item.name or 'it')}.</>"]


def _search(game, adv: dict, r: dict) -> list[str]:
    """What the dead carried: their purse, and what healing they had not used."""
    from realmwalker.rules.inventory import add_item
    from realmwalker.rules.items import money_text

    tier = max(1, min(4, int(adv.get("tier", 1))))
    coin = price(game, adv) // 3
    game.leader.money += coin
    out = [f"<loot>{money_text(coin)} in their purses.</>"]
    potion = "potion_healing" if tier <= 2 else "potion_greater_healing"
    if game.tables.items.get(potion) is not None:
        add_item(game.leader, game.tables.items, potion, 1, made_at=game.world.time)
        out.append(f"<loot>{esc(game.tables.items.get(potion)['name'])}, unopened.</>")
    return out


# ---------------------------------------------------------------------------- their band
def band(game, adv: dict, r: dict, rng) -> list:
    """The rival and their band as creatures: the leader (the first of the tier's that fits the party's budget) and
    as many of the band as the rest of it buys, up to the tier's most, less those you have killed."""
    from realmwalker.rules import encounter
    from realmwalker.rules.creatures import spawn

    ks = spec(game)["kinds"][r["kind"]]
    tier = max(1, min(4, int(adv.get("tier", 1))))
    t = game.tables
    budget = encounter.budget(t, [int(c.level) for c in game.party if c.alive] or [1], "high")
    leaders = [k for k in ks["leader"][tier - 1] if k in t.creatures]
    fits = [k for k in leaders if encounter.xp_of(t, [k]) <= budget]
    lead = fits[0] if fits else min(leaders or ["bandit"], key=lambda k: encounter.xp_of(t, [k]))
    ids = [lead]
    members = [k for k in ks["band"][tier - 1] if k in t.creatures] or ["bandit"]
    most = max(1, int(ks["most"][tier - 1]) - int(r.get("lost", 0)))
    i = 0
    while len(ids) < most and encounter.xp_of(t, ids + [members[i % len(members)]]) <= budget:
        ids.append(members[i % len(members)])
        i += 1
    if len(ids) == 1 and int(ks["most"][tier - 1]) - int(r.get("lost", 0)) > 1:
        ids.append(members[0])  # (never alone: a band is a band)
    culture = _culture(game, adv)
    out = []
    for n, k in enumerate(ids):
        c = spawn(t, k, rng.child(f"m{n}"), 9400 + n, now=int(game.world.time))
        if n == 0:
            c.name, c.named = r["name"], True
        if t.creatures[c.def_id].get("kind") == "humanoid":
            c.culture = culture
        c.story = {"adv": adv["id"], "role": "rival", "leader": n == 0}
        out.append(c)
    return out


def _fight(game, adv: dict, r: dict) -> list[str]:
    """Their band, here and now."""
    from realmwalker.game.encounters import PendingEncounter, threat_words

    if game.over is not None or r["state"] not in LIVE:
        return []
    rng = game.world.rng.child(f"rival-fight/{adv['id']}/{game.world.time}")
    creatures = band(game, adv, r, rng)
    _relate(r, -2)
    intro = _line(game, adv, "{rival_band}, steel out.")
    game.encounter = PendingEncounter("bandits", creatures, intro, True,
                                      threat_words(game.tables, creatures, game.party), attitude="hostile")
    game.travel = None
    return []


def _plea(game, adv: dict, r: dict) -> list[str]:
    """Their cry for help answered: the villain's servants, here and now, and the rival's band beside you."""
    from realmwalker.game.story import beats

    r["helping"] = True
    lines = beats.OPS["strike"](game, {"adv": adv["id"], "n": int(beats.director(game.world).get("n", 0))})
    if game.encounter is None:  # (it has no servants to send: they got out on their own)
        r["helping"] = False
        _relate(r, 1)
        return lines + [f"<good>{esc(_line(game, adv, '{rival_band} fought their way out before you came. {rival} will not forget that you did.'))}</>"]
    return lines


def to_battle(battle, game, advs: dict) -> list[str]:
    """A fight with a tale's foes (finale.prepare): a rival you rode to help fights beside you, with their band."""
    from realmwalker.game.story.finale import story_of
    from realmwalker.rules.combat import FOE, PARTY

    leader = next((f for f in battle.side(PARTY) if f.char is not None and f.bond is None), None)
    if leader is None:
        return []
    ids = sorted({t["adv"] for t in (story_of(f.creature) for f in battle.side(FOE) if f.creature is not None)
                  if t and t.get("adv") and t.get("role") != "rival"})
    out = []
    for aid in ids:
        adv = advs.get(aid)
        r = (adv or {}).get("rival")
        if adv is None or not r or not r.get("helping") or r["state"] not in LIVE:
            continue
        out += _join(battle, game, adv, r, leader, None)
        out.append(f"<good>{esc(_line(game, adv, '{rival_band} are here, at bay, and glad to see you.'))}</>")
    return out


def _join(battle, game, adv: dict, r: dict, leader, point) -> list[str]:
    for c in band(game, adv, r, battle.rng.child(f"rival-ally/{adv['id']}")):
        c.story = None
        f = battle.add_ally(c, leader, "story_ally", point=point)
        f.auto = True
        battle.__dict__.setdefault("rival_allies", {})[f.id] = (adv["id"], c.named)
    return []


def at_finale(battle, game, adv: dict, boss) -> list[str]:
    """The finale (finale.prepare, after its keys): the wounds a rival gave it before they died in its hall; no
    surprising a villain they sold your road to; a rival under truce comes on the second round with their band."""
    from realmwalker.rules.combat import FOE, PARTY

    r = adv.get("rival")
    if not r:
        return []
    out = []
    if r.get("hurt") and r.get("in_lair"):
        boss.hp = max(1, int(boss.hp * (1.0 - float(r["hurt"]))))
        out.append(f"<good>{esc(_line(game, adv, 'It is hurt: {rival} made it pay before the end.'))}</>")
    if r.get("sold") and battle.env.surprised == FOE:
        battle.env.surprised = None
        out.append(f"<warn>{esc(_line(game, adv, 'It was waiting for you. {rival} sold it your road.'))}</>")
    if r["state"] == "truce" and "rival" in adv["keys"]:
        def arrive(b, _done=[]):
            if _done or b.round < ARRIVE_ROUND or b.outcome is not None:
                return
            _done.append(True)
            lead = next((f for f in b.side(PARTY) if f.char is not None and f.active), None)
            if lead is None:
                return
            edge = (0, lead.y) if lead.x < b.field.width // 2 else (b.field.width - 1, lead.y)
            _join(b, game, adv, r, lead, edge)
            r["fought"] = True
            b.say(_line(game, adv, "{rival_band} come in at a run, as {rival} swore {they} would."), "good")
            b._event("arrive", who=lead.id)

        battle.round_hooks.append(arrive)
        out.append(f"<good>{esc(_line(game, adv, '{rival_band} are coming. They swore it.'))}</>")
    return out


def on_battle(game, result) -> None:
    """After a fight (story.on_battle): their band fought (slain, beaten: what they held is yours), a plea answered
    or lost, the dead of a band that stood beside you."""
    battle = getattr(game, "battle", None)
    advs = _story().adventures(game.world)
    won = result.outcome == "victory"
    seen = set()
    for c, how in [(c, "dead") for c in result.dead] + [(c, "taken") for c in getattr(result, "captives", [])] + \
            [(c, "fled") for c in getattr(result, "fled", [])]:
        tag = getattr(c, "story", None) or {}
        adv = advs.get(tag.get("adv")) if tag.get("role") == "rival" else None
        r = (adv or {}).get("rival")
        if not r or r["state"] not in LIVE:
            continue
        seen.add(adv["id"])
        if not tag.get("leader"):
            r["lost"] = int(r.get("lost", 0)) + (how == "dead")
        elif how == "dead":
            r["state"], r["fate"] = "slain", "slain"
            _drop_key(adv)
            _figure_dies(game, adv, r, f"slain by {game.leader.name}")
    for aid in seen:
        adv = advs[aid]
        r = adv["rival"]
        if won or r["state"] == "slain":
            lines = _hand_over(game, adv, r) if r.get("holds") else []
            for line in lines:
                game.say(line, "loot")
            if r["state"] in LIVE:
                r["state"] = "gone"
    for fid, (aid, is_leader) in ((battle.__dict__.get("rival_allies") or {}) if battle is not None else {}).items():
        adv = advs.get(aid)
        r = (adv or {}).get("rival")
        f = battle.fighter(fid)
        if not r or f is None:
            continue
        if f.state == "dead":
            if is_leader and r["state"] in LIVE:
                r["state"] = "dead"
                r["fate"] = "fought" if r.get("fought") else "fell_beside"  # (at the finale, or at their plea)
                _drop_key(adv)
                _figure_dies(game, adv, r, "fell fighting beside " + game.leader.name)
            elif not is_leader:
                r["lost"] = int(r.get("lost", 0)) + 1
    stood = {aid for aid, _ in ((battle.__dict__.get("rival_allies") or {}) if battle is not None else {}).values()}
    for adv in _story().active(game):
        r = adv.get("rival")
        if r and r.get("helping") and adv["id"] in stood:
            r["helping"] = False
            if r["state"] in LIVE and won:
                _relate(r, 1)
                r["state"] = "truce"
                if "rival" not in adv["keys"]:
                    adv["keys"].append("rival")
                game.say(f"<good>{esc(_line(game, adv, '{rival} owes you {their} life, and says so. When you face it, {they} will come.'))}</>",
                         "story")
            elif r["state"] in LIVE:
                _overrun(game, adv, r)


# ---------------------------------------------------------------------------- the end
def after_tale(game, adv: dict) -> None:
    """The tale is over (endings.finish): how it ended for them, and their page in the epilogue."""
    r = adv.get("rival")
    sp = spec(game)
    if not r or not sp:
        return
    if r.get("fate") is None:
        r["fate"] = {"slain": "slain", "bought": "bought"}.get(r["state"]) or (
            "lair" if r.get("in_lair") else "overrun" if r["state"] == "dead" else
            ("fought" if r.get("fought") else "friend") if r["state"] == "truce" else
            "prize" if r["state"] == "ahead" else "overrun" if r["state"] == "pinned" else "late" if adv["state"] == "won" and r["state"] == "racing" else
            "gone")
    never_met = r.get("met") is None and not r.get("in_lair")
    if r["state"] in LIVE:
        r["state"] = "gone"
    if never_met:
        return  # (never met: nothing to tell)
    rng = game.world.rng.child(f"rival-fate/{adv['id']}")
    text = _say(game, adv, sp["fates"].get(r["fate"], sp["fates"]["gone"]), rng)
    pages = adv.setdefault("epilogue", [])
    page = next((p for p in pages if p.get("about") == "rival"), None)
    if page is not None:
        page["text"] = text
    else:
        pages.insert(max(0, len(pages) - 1), {"about": "rival", "text": text})


WORDS = {"unmet": "not yet met", "racing": "racing you", "ahead": "has it", "truce": "under truce", "pinned": "pinned",
         "dead": "dead", "slain": "slain by you", "gone": "gone", "bought": "paid off"}
FEELING = {-2: "an enemy", -1: "hostile", 0: "wary", 1: "friendly", 2: "a friend"}


def journal_line(game, adv: dict) -> str:
    """Who races you for it, and how they stand with you (the journal)."""
    r = adv.get("rival")
    if not r or r["state"] == "unmet":
        return ""
    feel = f", {FEELING[int(r['relation'])]}" if r["state"] in LIVE else ""
    return f"{esc(r['name'])}, {esc(r.get('who') or '')} ({WORDS.get(r['state'], r['state'])}{feel})"
