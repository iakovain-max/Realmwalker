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
`steps`): attention jumps by `jump`, and within `days` its next move is one needing `min` attention or more, or one
of `moves` (a beast's test), at `weight` times its temper's weight, whatever the chapter's count: a reprisal, a strike,
a visit. It makes no other move while its wrath waits for the place to lash out. A reprisal falls on one of the
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
    fresh = token is not None and "used" not in token
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
        if not all(able(game, adv, need) for need in _needs(move)):
            continue
        if not beats.eligible(game, move["beat"], {"adv": adv["id"], "where": where}):
            continue
        weight = float(wt) * (tailor if move.get("tailored") else 1.0)
        normal[0].append(mid)
        normal[1].append(weight)
        if wrath is not None and (lo >= int(w_spec.get("min", 0)) or mid in w_spec.get("moves", [])):
            angry[0].append(mid)
            angry[1].append(weight * float(w_spec.get("weight", 1)))
    rng = game.world.rng.child(f"villain/{adv['id']}/{day}/{where}")
    if angry[0]:
        options, weights = angry
    elif wrath is not None:
        return None  # (in its wrath it waits for the place to lash out, rather than spend itself on a sign)
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
    if "helper" in _needs(move):
        adv["reprisal"] = _helper(game, adv)
    if "companion" in _needs(move):
        adv["reprisal"] = _helper(game, adv)  # (one it might be given instead: the wedge's darkest answer)
        adv["wedge"] = _tempted(game, adv, rng)
        loyal = float((game.tables.villains.get("wedge") or {}).get("loyal", 50))
        if move.get("disloyal") and adv["wedge"]["loyalty"] < loyal:
            return move["disloyal"]  # (one who is not yours already: they go over to it, and say nothing)
    if "town" in _needs(move):
        adv["frame"] = _frame_plan(game, adv, rng)
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
    who = rng.choice([c for c in able if c is not game.leader] or able)  # (a companion's, when there is one)
    adv["token"] = {"what": rng.choice(spy["tokens"]), "of": who.name.split()[0], "day": int(game.moment.total_days)}
    words = {"token": adv["token"]["what"], "token_of": adv["token"]["of"]}
    game.say(f"<dim>{textgen.fill(rng.choice(spy['missing']), rng, {}, words)}</>", "story")
    return False


# ---------------------------------------------------------------------------- reprisals
def _helper(game, adv: dict) -> int | None:
    """The npc id of one of the cast who helped you and may pay for it: a step that named them done, alive, in a town
    you are not in, and needed by no step still to do."""
    from realmwalker.game.story import cast

    roles = game.tables.villains.get("reprisal_roles", [])
    needed, helped = set(), set()
    for ch in adv["chapters"]:
        for st in ch["steps"]:
            named = {st["target"].get("role")} | {r.get("role") for r in st["target"].get("routes", [])}
            (helped if st["state"] == "done" else needed).update(named)
    here = game.world.settlement_at(game.player.x, game.player.y)
    for role in roles:
        entry = adv["cast"].get(role)
        npc = cast.person(game.world, entry) if entry and "npc" in entry else None
        if npc is None or not getattr(npc, "alive", False) or role in needed or role not in helped:
            continue
        if here is not None and int(entry.get("settlement", -1)) == here.id:
            continue
        return int(entry["npc"])
    return None


# ---------------------------------------------------------------------------- what a move needs (E.2)
NEEDS = ("helper", "companion", "town", "lair")


def _needs(move: dict) -> list[str]:
    return list(move.get("needs", ())) + (["helper"] if move.get("beat") == "villain_reprisal" else [])


def able(game, adv: dict, need: str) -> bool:
    """Whether what a move needs is there: one who helped you (a reprisal, a kidnap), a companion to tempt (a wedge),
    a town under a lord's law in its reach (a frame), a hall under its home to hold a captive in (a kidnap)."""
    if need == "helper":
        return _helper(game, adv) is not None
    if need == "companion":
        return any(c.alive and c.companion for c in game.party[1:])
    if need == "town":
        return _frame_town(game, adv) is not None
    if need == "lair":
        return lair(game, adv) is not None
    return False


def lair(game, adv: dict) -> dict | None:
    """The first level under its home (a place record), where it keeps those it takes; None if it has no hall."""
    from realmwalker.game.story import places

    home = adv["places"].get("home") or {}
    if "site" not in home:
        return None
    place = {"site": int(home["site"]), "part": "level", "level": 1}
    return place if places.dungeon_key(game.world, place) is not None else None


# ---------------------------------------------------------------------------- the wedge (E.2)
def _tempted(game, adv: dict, rng) -> dict:
    """The companion it whispers to (the least loyal is the likeliest), and what it offers them."""
    pool = [c for c in game.party[1:] if c.alive and c.companion]
    weights = [max(5.0, 110.0 - float(c.companion.get("loyalty", 50))) for c in pool]
    c = rng.weighted(pool, weights)
    offers = (game.tables.villains.get("wedge") or {}).get("offers") or ["what they want most"]
    return {"name": c.name, "loyalty": float(c.companion.get("loyalty", 50)), "offer": rng.choice(offers),
            "day": int(game.moment.total_days)}


def tempted(game, adv: dict):
    """The companion its wedge was driven at, if still with you."""
    rec = adv.get("wedge") or {}
    return next((c for c in game.party[1:] if c.name == rec.get("name")), None)


# ---------------------------------------------------------------------------- the frame (E.2)
def _frame_town(game, adv: dict) -> int | None:
    """A town in its reach where a lord's law runs and people live, not the one you stand in (the nearest to its
    home): where it does a murder and lays it at your door."""
    from realmwalker.game.law import fx
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    if t is None:
        return None
    here = game.world.settlement_at(game.player.x, game.player.y)
    best = None
    for s in game.world.settlements:
        if s.kind not in ("village", "town", "city") or (here is not None and s.id == here.id):
            continue
        d = threats.distance(game.world, t, s.x, s.y)
        if d > int(t["reach"]["r"]) * 1.5:
            continue
        lord = fx.owner_of(game.world, s)
        if lord is None or lord.kind == "tribe":
            continue
        if best is None or (d, s.id) < best[0]:
            best = ((d, s.id), s.id)
    return best[1] if best else None


# ---------------------------------------------------------------------------- the villain's hand (E.2)
def hand(game, adv: dict | None) -> dict:
    """The hand its letters are written in: its temper's (villains.json tempers `hand`: face, ink, seal), else a
    villain's dark hand."""
    from realmwalker.game import letters

    h = dict(temper(game, adv).get("hand") or {}) if adv is not None else {}
    face = h.get("face", "dark")
    return {"hand": face if face in letters.HANDS else "dark", "ink": h.get("ink"),
            "seal": h.get("seal") or list(letters.SEALS["dark"])}


# ---------------------------------------------------------------------------- the invitation (E.2)
def invited(game) -> dict | None:
    """A safe conduct running now (the villain's invitation, there and home again): no band troubles you on the road
    while it lasts (encounters.roll_encounter)."""
    from realmwalker.game import story

    day = float(game.moment.total_days)
    for adv in story.active(game):
        rec = adv.get("invited")
        if rec and day <= float(rec["until"]):
            return rec
    return None


def lapse(game, adv: dict) -> None:
    """An invitation not taken up in time is a slight (story.daily): it lapses, and the villain marks it."""
    rec = adv.get("invited")
    if rec and rec.get("state") == "going" and float(game.moment.total_days) > float(rec["until"]):
        adv.pop("invited", None)
        if "snubbed_it" not in adv["flags"]:
            adv["flags"].append("snubbed_it")
        notice(game, adv, int((game.tables.villains.get("invitation") or {}).get("snub", 1)))
    elif rec and rec.get("state") == "home" and float(game.moment.total_days) > float(rec["until"]):
        adv.pop("invited", None)


# ---------------------------------------------------------------------------- what it does to those who helped you (E.2)
SEEN = {"hanged": ("gibbet", "reprisal_gibbet"), "burned": ("burned_out", "reprisal_ashes"),
        "given up": ("gibbet", "reprisal_gibbet")}  # how they died -> the mark on their town, the scene there


def name_of(game, adv: dict) -> str:
    from realmwalker.world import threats

    t = threats.records(game.world).get(adv["threat"])
    return threats.villain_name(game.world, t) if t else "it"


def pay(game, adv: dict, npc, how: str, words: dict) -> None:
    """One who helped you dies for it: their kin mourn, the news goes out, and their town shows it (a gibbet in the
    square or a burned house: a mark, and a crowd round it the next time you walk in)."""
    from realmwalker.game import townlife
    from realmwalker.game.story import beats, lives
    from realmwalker.world import marks, news

    npc.alive = False
    npc.present = False
    npc.flags.pop("with_party", None)
    npc.flags.pop("captive", None)
    townlife.forget_person(npc.id)
    for t in (lives.life(npc) or {}).get("ties", []):  # (their kin mourn them, as any death of the people code)
        other = game.world.npcs.get(t["npc"]) if t.get("npc") is not None else None
        if other is not None and other.alive and lives.KIN_OF.get(t["kind"]) is not None:
            lives._mourn(game, other, 21)
            for ot in (lives.life(other) or {}).get("ties", []):
                if ot.get("npc") == npc.id:
                    ot["state"] = "dead"
    day = int(game.moment.total_days)
    npc.flags["died"] = {"how": how, "day": day}
    npc.flags["reprisal"] = {"adv": adv["id"], "how": how, "day": day}
    adv.setdefault("reprisals", []).append(int(npc.id))
    s = game.world.settlements[int(npc.settlement)]
    news.add(game.world, f"{npc.name} of {s.name} was found {how}, and the word is that it was for helping "
             f"{words.get('hero', 'a stranger')} against {words.get('villain', 'the dark')}.", s.x, s.y,
             kind="crime", importance=3, places=[s.id])
    mark, scene = SEEN.get(how, (None, None))
    if mark in marks.table(game.tables):
        marks.add(game.world, s, mark, float(news.now_days(game.world)), game.tables, npc=int(npc.id))
    if scene:
        beats.director(game.world).setdefault("reprisals", []).append(
            {"npc": int(npc.id), "settlement": int(s.id), "scene": scene, "adv": adv["id"], "day": day})
    if game.quests:
        from realmwalker.game import quests

        quests.on_npc_death(game, npc)


def seen_in_town(game, settlement) -> bool:
    """Into a town where one who helped you was made an example of, while it is fresh (30 days): a crowd at the
    gibbet, or at the ashes, and their words (the stage). True when a scene began."""
    from realmwalker.game.story import beats, stage

    recs = beats.director(game.world).get("reprisals") or []
    today = int(game.moment.total_days)
    for r in list(recs):
        if today - int(r["day"]) > 30:
            recs.remove(r)
            continue
        if int(r["settlement"]) != settlement.id:
            continue
        npc = game.world.npcs.get(int(r["npc"]))
        words = {"helper": npc.name if npc is not None else "the one who helped you",
                 "helper_first": npc.first_name if npc is not None else "them",
                 "villain": name_of(game, game.world.politics.get("adventures", {}).get(r["adv"]) or {"threat": ""})}
        if stage.start(game, r["scene"], words=words, force=True) is not None:
            recs.remove(r)
            return True
    return False


def _frame_plan(game, adv: dict, rng) -> dict:
    """Where it will do its murder, and to whom: one of the town's people nobody's tale needs (none known: a
    stranger). {frame_town} and {frame_victim} in its beat's words."""
    from realmwalker.game.people import npcs_in

    sid = _frame_town(game, adv)
    cast_ids = {int(e["npc"]) for e in adv["cast"].values() if isinstance(e, dict) and e.get("npc") is not None}
    folk = sorted((n for n in npcs_in(game.world, sid) if n.alive and n.id not in cast_ids
                   and not n.flags.get("companion") and not n.flags.get("stays")
                   and not n.flags.get("visitor")), key=lambda n: n.id)
    victim = rng.choice(folk) if folk else None
    return {"settlement": sid, "victim": victim.id if victim is not None else None,
            "name": victim.name if victim is not None else "a stranger at the inn"}


def frame(game, adv: dict, crime: str = "murder") -> dict | None:
    """Its murder laid at your door (adv["frame"], planned by due_move): the one it chose dead, two of their
    neighbours swearing it was you, and the crime reported (law.framed). Kept in adv["frames"]."""
    from realmwalker.game import law, townlife
    from realmwalker.game.people import npcs_in

    plan = adv.get("frame") or {}
    if plan.get("settlement") is None or plan.get("done"):
        return None
    s = game.world.settlements[int(plan["settlement"])]
    victim = game.world.npcs.get(int(plan["victim"])) if plan.get("victim") is not None else None
    victim = victim if victim is not None and victim.alive else None
    rng = game.world.rng.child(f"frame/{adv['id']}/{game.moment.total_days}")
    witnesses = sorted((n for n in npcs_in(game.world, s.id) if n.alive and n is not victim
                        and not n.flags.get("visitor") and not n.flags.get("companion")), key=lambda n: n.id)
    rng.shuffle(witnesses)
    if victim is not None:
        victim.alive = False
        victim.present = False
        victim.flags["died"] = {"how": "murdered", "day": int(game.moment.total_days)}
        townlife.forget_person(victim.id)
    rec = law.framed(game, s, crime, victim=victim, witnesses=witnesses[:2], by=adv["id"])
    plan["done"] = True
    if rec is not None:
        adv.setdefault("frames", []).append(int(rec["id"]))
    return rec


def kidnap(game, adv: dict) -> str | None:
    """One who helped you (adv["reprisal"]) is taken to the first level of its hall: an optional rescue step joins
    the chapter (its step quest has villains.json kidnap `days`); if the days run out they die there (story.
    on_quest_end -> `lost`). Returns their name."""
    from realmwalker.game import story
    from realmwalker.game.story import deeds, places

    npc = game.world.npcs.get(int(adv["reprisal"])) if adv.get("reprisal") is not None else None
    place = lair(game, adv)
    ch = story.chapter(adv)
    role = next((r for r, e in adv["cast"].items() if isinstance(e, dict) and npc is not None
                 and e.get("npc") == npc.id), None)
    if npc is None or not npc.alive or place is None or ch is None or role is None:
        return None
    n = 1 + sum(1 for c in adv["chapters"] for st in c["steps"] if st.get("kidnap"))
    st = {"id": f"{ch['id']}.taken{n}", "kind": "rescue", "state": "open", "optional": True, "gives": [],
          "kidnap": True, "set": True,
          "target": {"place": place, "role": role, "who": dict(adv["cast"][role]),
                     "level": places.dungeon_key(game.world, place), "n": 1}}
    ch["steps"].append(st)
    deeds._setup_rescue(game, adv, st)
    days = int((game.tables.villains.get("kidnap") or {}).get("days", 12))
    for q in game.quests:
        if q.get("id") == st.get("quest"):
            q["days"] = days
            q["deadline"] = game.moment.total_days + days
    npc.present = False
    npc.flags["kidnapped"] = {"adv": adv["id"], "day": int(game.moment.total_days)}
    adv.setdefault("kidnapped", []).append(int(npc.id))
    adv["reprisal"] = None
    story.journal(adv, f"{npc.name} was taken to {places.name(game.world, place)}.", int(game.moment.total_days))
    return npc.name


def lost(game, adv: dict, st: dict) -> None:
    """A kidnap's days ran out: the one it took dies in its hall (story.on_quest_end)."""
    from realmwalker.game.story import words as wordsmod

    who = (st["target"].get("who") or {}).get("npc")
    npc = game.world.npcs.get(int(who)) if who is not None else None
    if npc is not None and npc.alive:
        npc.flags.pop("kidnapped", None)
        pay(game, adv, npc, "dead in the dark", wordsmod.for_adventure(game, adv))
