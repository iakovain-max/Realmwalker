"""Work that waits to be taken (Expansion 6 Part C; ADVENTURES.md 5.15 and 8.10; numbers and words in work.json).

Nobody rolls a job each week any more, and nobody answers "Is there any work?". Work waits with the person who
has it, and that person has their own choice in a conversation ("own_work"):
- **Commissions**: a faction you have joined sends one now and then (every `renew` days while none of its work is
  live), made from its goals (`goals`: words matched in `Faction.goals`, each with kinds of work; `by_kind` for the
  guilds and orders) and given by one of its people of standing in a peopled town within `reach` of you. Word of it
  reaches you (`daily`). A faction waiting to promote you makes it the trial (`mark_trial`): the rank trials
  and the thieves' guild's work ride on commissions. Kept in `game.renown.flags["commissions"]` {faction id: quest}.
- **Pleas**: someone whose town has a real need asks it of you - the healer of a sick town, the lord of a town that
  pays a dragon tribute, a mage who would take an apprentice, someone with a blood feud of the history (`pleas`).
  Thought of when you speak to them, kept in `Town.flags["pleas"]` {npc id: quest} while the need lasts; after one is
  taken, refused or gone stale, that person asks again only after `plea_gap` days.
- **Contracts** (C.3): the town's paid work, one at a time (two in a city), with a real danger on the way that the
  party meets there (`contracts`, `on_the_road`; the section below says the rest). The one hiring has their own choice
  and the board says who is hiring and the terms (`notices`).
The quest dicts are built by `quests.make` for a target the picker of its kind chose. Situations (C.6) will wait here
too.
"""

from __future__ import annotations

from realmwalker.core.textgen import escape_markup as esc

COMMISSIONS = "commissions"
PLEAS = "pleas"


def spec(game) -> dict:
    return game.tables.work or {}


# ---------------------------------------------------------------------------- what waits
def waiting(game) -> list[dict]:
    """Every piece of work waiting to be taken: commissions, pleas and contracts (so nothing else chases the same
    thing)."""
    out = list(game.renown.flags.get(COMMISSIONS, {}).values())
    for town in game.world.towns.values():
        out += list(town.flags.get(PLEAS, {}).values())
    for recs in records(game.world).values():
        out += [r["quest"] for r in recs if not r.get("taken")]
    return out


def held_by(game, npc) -> list[dict]:
    """The work this person has for you, now: their faction's commission, the town's contract they are hiring for,
    their own plea."""
    if not npc.alive or npc.flags.get("disgraced"):
        return []
    from realmwalker.game import quests

    if any(q["giver"] == npc.id for q in quests.active(game)):
        return []  # one piece of work at a time from each person
    out = [q for q in game.renown.flags.get(COMMISSIONS, {}).values() if q["giver"] == npc.id]
    if 0 <= npc.settlement < len(game.world.settlements):
        out += [r["quest"] for r in contracts(game, game.world.settlements[npc.settlement])
                if r["giver"] == npc.id and not r.get("taken")]
    plea = plea_of(game, npc)
    if plea is not None:
        out.append(plea)
    return out


def offers_here(game, settlement) -> list[tuple]:
    """(person, quest) for every piece of work waiting in this town - its people's commissions and pleas, and the
    bounties on its board (person None) - for the bots and the tests."""
    from realmwalker.game import quests
    from realmwalker.game.people import npcs_in

    out = [(npc, q) for npc in npcs_in(game.world, settlement.id) for q in held_by(game, npc)]
    return out + [(None, q) for q in quests.board_bounties(game, settlement)]


def taken(game, q) -> None:
    """It is in the journal now: it no longer waits anywhere."""
    pool = game.renown.flags.get(COMMISSIONS, {})
    for k, v in list(pool.items()):
        if v is q or v.get("id") == q["id"]:
            del pool[k]
    town = game.world.towns.get(q["town"])
    if town is not None:
        for k, v in list(town.flags.get(PLEAS, {}).items()):
            if v is q or v.get("id") == q["id"]:
                del town.flags[PLEAS][k]
    for rec in records(game.world).get(str(q["town"]), []):
        if rec["quest"] is q or rec["quest"].get("id") == q["id"]:
            rec["taken"] = True  # (the town has no other contract until this one's time is up)


# ---------------------------------------------------------------------------- commissions
def daily(game) -> None:
    """Once a day: a commission goes stale, or a faction you serve sends a new one."""
    from realmwalker.game import quests

    w = game.world
    sp = spec(game).get("commissions")
    if not sp or not w.factions:
        return
    today = int(game.moment.total_days)
    pool = game.renown.flags.setdefault(COMMISSIONS, {})
    due = game.renown.flags.setdefault("commission_day", {})
    for key, q in list(pool.items()):
        giver = w.npcs.get(q["giver"])
        f = w.factions.get(int(key))
        if today >= int(q.get("until", 0)) or giver is None or not giver.alive or f is None or not f.active or \
                f.id not in game.renown.members:
            del pool[key]
    for fid in sorted(game.renown.members):
        f = w.factions.get(fid)
        key = str(fid)
        if f is None or not f.active or key in pool or today < int(due.get(key, -1)):
            continue
        if any(q.get("commission") == fid for q in quests.active(game)):
            continue  # (one piece of their work at a time)
        rng = w.rng.child(f"commission/{fid}/{today}")
        q = commission(game, f, rng)
        lo, hi = sp["renew"]
        gap = rng.randint(int(lo), int(hi))
        due[key] = today + gap
        if q is None:
            continue
        q["until"] = today + gap
        pool[key] = q
        giver = w.npcs[q["giver"]]
        town = w.settlements[giver.settlement]
        game.player.known_settlements.add(town.id)
        game.say(rng.choice(sp["word"]).format(faction=esc(f.name), giver=esc(giver.name), title=esc(giver.title),
                                               town=esc(town.name)), "info")


def kinds_for(game, f) -> list[str]:
    """The kinds of work this faction's goals give (its goals' words matched against work.json `goals`)."""
    sp = spec(game).get("commissions", {})
    out = list(sp.get("by_kind", {}).get(f.kind, []))
    for goal in f.goals:
        for g in sp.get("goals", {}).values():
            if any(goal.startswith(m) for m in g["match"]):
                out += [k for k in g["kinds"] if k not in out]
    return out


def member(game, npc, f) -> bool:
    """Does this person speak for that faction (its own, its guild's or church's, its lord's)?"""
    from realmwalker.game import law
    from realmwalker.game.people import npc_factions

    if f.kind == "thieves_guild":
        return law.is_fence(game, npc)
    if f.kind == "mages_circle":
        return npc.job == "mage"
    return any(o.id == f.id for o in npc_factions(game, npc))


def commission(game, f, rng) -> dict | None:
    """A piece of this faction's work, given by one of its people of standing in a peopled town near you."""
    from realmwalker.game import quests
    from realmwalker.game.people import npcs_in

    w = game.world
    sp = spec(game)["commissions"]
    kinds = kinds_for(game, f)
    if not kinds:
        return None
    here = (game.player.x, game.player.y)
    towns = sorted((s for s in w.settlements if s.id in w.towns and
                    abs(s.x - here[0]) + abs(s.y - here[1]) <= int(sp["reach"])),
                   key=lambda s: (abs(s.x - here[0]) + abs(s.y - here[1]), s.id))
    busy = {q["giver"] for q in quests.active(game)} | {q["giver"] for q in waiting(game)}
    for s in towns:
        folk = [n for n in npcs_in(w, s.id) if n.alive and (n.notable or f.kind == "thieves_guild")
                and n.id not in busy and not n.flags.get("disgraced") and member(game, n, f)]
        if not folk:
            continue
        giver = rng.choice(sorted(folk, key=lambda n: n.id))
        order = list(kinds)
        rng.shuffle(order)
        for kind in order:
            q = quests.build(game, giver, kind, rng)
            if q is None:
                continue
            q["commission"] = f.id
            q["faction"] = f.id
            mark_trial(game, f, q)
            return q
    return None


def mark_trial(game, f, q) -> None:
    """If this faction is waiting to promote you, its commission is the trial for it."""
    from realmwalker.game.reputation import needs_trial

    if needs_trial(game, f.id):
        q["trial"] = f.id
        q["reward"] = int(q["reward"] * 1.2)


# ---------------------------------------------------------------------------- pleas
def need_met(game, need: str, town) -> bool:
    """Is the town's need real today?"""
    if need == "sickness":
        return bool(town.status.get("plague") or town.status.get("famine"))
    if need == "dragon":
        return bool(town.status.get("tribute") or town.status.get("burned"))
    return True  # ("always"; a grudge is the picker's to find)


def plea_of(game, npc) -> dict | None:
    """The need this person would ask you to meet (made the first time it is asked after), or None."""
    from realmwalker.game import quests
    from realmwalker.game.people import town_of

    w = game.world
    town = town_of(w, npc.settlement)
    pool = town.flags.setdefault(PLEAS, {})
    key = str(npc.id)
    s = w.settlements[npc.settlement]
    q = pool.get(key)
    if q is not None:
        p = next((p for p in spec(game).get("pleas", []) if p["kind"] == q["template"] and
                  p["need"] == q.get("plea")), None)
        if p is not None and need_met(game, p["need"], s):
            return q
        del pool[key]  # (the need is over)
        return None
    today = int(game.moment.total_days)
    stamps = town.flags.setdefault("plea_day", {})
    if today < int(stamps.get(key, -1)):
        return None
    stamps[key] = today + int(spec(game).get("plea_gap", 14))
    rng = w.rng.child(f"plea/{npc.id}/{today}")
    for p in spec(game).get("pleas", []):
        if p["jobs"] and npc.job not in p["jobs"] or not need_met(game, p["need"], s):
            continue
        if p["need"] == "grudge":
            target = quests._vendetta_pick(game, npc, rng, s)
            target = None if target is None else {"kind": p["kind"], "town": s.id, **target}
        else:
            target = quests.pick(game, p["kind"], npc, rng)
        if target is None:
            continue
        q = quests.make(game, npc, target, rng)
        q["plea"] = p["need"]
        pool[key] = q
        return q
    return None


# ---------------------------------------------------------------------------- contracts
# Paid work (C.3; ADVENTURES.md 5.15 rule 3, 8.10): one contract a town at a time, two in a city or a great city,
# kept in world.politics["contracts"] {settlement id: [record]}. A record is {"id", "kind" (work.json contracts.kinds),
# "giver", "terms" {"pay", "days", "route": [from, to]}, "danger", "until", "quest", "taken"}; it lasts its 14-28 days
# whether or not it is taken, and then the town has another. What it is comes from what the town has: its trade
# (carts or papers to the nearest market town), its faith (pilgrims to a temple town), a village's known raiders
# (defend). Its danger is real and on the way (`danger_on`): a threat's servants, a gang, a lair's beasts, or what
# the land along the road breeds; the party meets it there (`on_the_road`, from the overworld walk).
CONTRACTS = "contracts"
MARKET = ("town", "city", "hold", "elfhall")


def _cspec(game) -> dict:
    return spec(game).get("contracts") or {}


def slots(s) -> int:
    return 2 if s.kind == "city" or s.great else 1


def records(world) -> dict:
    return world.politics.setdefault(CONTRACTS, {})


def contracts(game, s) -> list[dict]:
    """This town's contracts as they stand today (renewed first if their time is up): only a peopled town has any."""
    w = game.world
    sp = _cspec(game)
    town = w.towns.get(s.id)
    if not sp or town is None or not town.npcs:
        return []
    renew(game, s)
    return records(w).get(str(s.id), [])


def _stale(game, rec, today: int) -> bool:
    if today >= int(rec["until"]):
        return True
    if rec.get("taken"):
        return False
    giver = game.world.npcs.get(rec["giver"])
    q = rec["quest"]
    who = game.world.npcs.get(q["target"].get("npc", -1))
    if "npc" in q["target"] and (who is None or not who.alive or
                                 q["template"] == "escort" and who.flags.get("escort") is not None):
        return True  # (the traveller is dead, or gone with somebody else; the one the papers are for is dead)
    return giver is None or not giver.alive or bool(giver.flags.get("disgraced"))


def renew(game, s) -> None:
    """Drop what has run its time; fill the empty places from what the town has, if it is time to look again."""
    w = game.world
    sp = _cspec(game)
    today = int(game.moment.total_days)
    pool = records(w)
    key = str(s.id)
    recs = [r for r in pool.get(key, []) if not _stale(game, r, today)]
    pool[key] = recs
    look = w.politics.setdefault("contract_day", {})
    if len(recs) >= slots(s) or today < int(look.get(key, -1)):
        return
    rng = w.rng.child(f"contract/{s.id}/{today}")
    kinds = list(sp["kinds"])
    rng.shuffle(kinds)
    for cid in kinds:
        if len(recs) >= slots(s):
            break
        if any(r["kind"] == cid for r in recs):
            continue
        rec = _contract(game, s, cid, rng)
        if rec is not None:
            recs.append(rec)
    lo, hi = sp["renew"]
    look[key] = today + (rng.randint(int(lo), int(hi)) if len(recs) < slots(s) else 0)


def _contract(game, s, cid: str, rng) -> dict | None:
    """One piece of paid work of this kind from this town, or None when the town has nothing of the kind."""
    from realmwalker.game import quests
    from realmwalker.game.people import npcs_in

    w = game.world
    sp = _cspec(game)
    c = sp["kinds"][cid]
    today = int(game.moment.total_days)
    busy = {q["giver"] for q in quests.active(game)} | {q["giver"] for q in waiting(game)}
    folk = [n for n in npcs_in(w, s.id) if n.alive and not n.flags.get("disgraced") and not n.flags.get("companion")]
    givers = sorted((n for n in folk if n.job in c["givers"] and n.id not in busy), key=lambda n: (not n.notable, n.id))
    if not givers:
        return None
    giver = givers[0] if givers[0].notable else rng.choice(givers)
    if c["kind"] == "defend":
        target = quests.pick(game, "defend", giver, rng, town=s)
        if target is None or int(target["when"]) - 1 <= today:
            return None
        danger = {"kind": "raiders", "group": target["group"], "faction": target["faction"], "met": False}
        route = [s.id, s.id]
    else:
        dest = _destination(game, s, c.get("to", "market"))
        if dest is None:
            return None
        path = _route(game, s, dest)
        if path is None:
            return None
        danger = danger_on(game, path, s, rng)  # (before anyone in the far town is thought of: it may be quiet)
        if danger is None:
            return None
        if c["kind"] == "escort":
            used = {q["target"].get("npc") for q in waiting(game) + quests.active(game)}
            pool = [n for n in folk if not n.notable and n.id not in used and n.flags.get("escort") is None
                    and n.job not in ("guard", "beggar", "child")]
            fitting = [n for n in pool if n.job in c.get("travellers", ())] or pool
            if not fitting:
                return None
            target = {"kind": "escort", "town": s.id, "dest": dest.id,
                      "npc": rng.choice(sorted(fitting, key=lambda n: n.id)).id}
        else:
            who = quests._someone_in(game, dest, rng, jobs=c.get("recipients")) or quests._someone_in(game, dest, rng)
            if who is None:
                return None
            target = {"kind": "deliver", "town": s.id, "dest": dest.id, "npc": who.id}
        route = [s.id, dest.id]
    q = quests.make(game, giver, target, rng)
    n = int(w.politics.get("next_contract", 0))
    w.politics["next_contract"] = n + 1
    rec_id = f"K{n}"
    q["contract"] = rec_id
    q["hidden"] = None  # (paid work is what it says it is: the hidden sides are for the ones who ask a favour)
    if c.get("text"):
        q["text_key"] = c["text"]
    lo, hi = sp["renew"]
    until = today + rng.randint(int(lo), int(hi))
    if c["kind"] == "defend":
        until = min(until, int(q["target"]["when"]) - 1)  # (no use hiring a sword after they have come)
        danger["name"] = q["words"]["raiders"]
    else:
        q["danger"] = danger
        q["words"]["danger"] = danger["name"]
    q["until"] = until
    return {"id": rec_id, "kind": cid, "giver": giver.id, "until": until, "taken": False, "danger": danger,
            "terms": {"pay": q["reward"], "days": q["days"], "route": route}, "quest": q}


def _destination(game, s, to: str):
    """The nearest market town (carts and papers go to market), or for pilgrims a temple town: a city first."""
    from realmwalker.game.quests import dist

    w = game.world
    places = [d for d in w.settlements if d.id != s.id and 6 <= dist(d, s) <= 30]
    if to == "holy":
        best = [d for d in places if d.kind == "city" or d.great] or [d for d in places if d.kind in MARKET]
    else:
        best = [d for d in places if d.kind in MARKET or d.great]
    return min(best, key=lambda d: (dist(d, s), d.id)) if best else None


def _route(game, frm, to) -> list[tuple[int, int]] | None:
    """The way a carter would go: by the roads and the lie of the land (the walk's own costs)."""
    import tcod.path

    path = tcod.path.path2d(game.travel_costs(), start_points=[(frm.x, frm.y)], end_points=[(to.x, to.y)],
                            cardinal=100, diagonal=141)
    return [(int(x), int(y)) for x, y in path.tolist()] if len(path) >= 4 else None


def danger_on(game, path: list, town, rng) -> dict | None:
    """The real danger nearest the road (within `near` tiles): a threat's servants, a gang, the beasts of a lair -
    one the party might live through, if any is - or, when the road is quiet of those, what its land breeds."""
    import math

    from realmwalker.game import past
    from realmwalker.game.encounters import DEADLY_RATIO
    from realmwalker.game.quests import beast_ratio, cleared, RAIDER_GROUPS
    from realmwalker.rules.creatures import choose_encounter
    from realmwalker.world import factions as fx
    from realmwalker.world import threats

    w = game.world
    sp = _cspec(game)
    groups = game.tables.creatures.encounters
    n = len(path)
    mid = path[n // 4: max(n // 4 + 1, 3 * n // 4)]  # (not at either town's gate)

    def nearest(x, y):
        d, at = min((math.hypot(px - x, py - y), (px, py)) for px, py in mid)
        return d, at

    found = []  # (deadly, order, distance, danger)
    villains = set()
    for t in threats.live(w):
        fig = threats.villain_figure(w, t)
        if fig is None or fig.kind != "beast":
            continue
        villains.add(fig.id)
        group = past.group_of(game, fig)
        d, at = nearest(*threats.home_xy(w, t))
        if group in groups and d <= sp["near"]:
            found.append((0, d, {"kind": "threat", "threat": t["id"], "group": group, "at": list(at),
                                 "words": {"name": threats.villain_name(w, t)}}))
    for gang in fx.active_factions(w, "bandit_gang"):
        if not 0 <= gang.site < len(w.sites) or gang.site in cleared(game):
            continue
        site = w.sites[gang.site]
        group = next((g for g in RAIDER_GROUPS["bandit_gang"] if g in groups), None)
        d, at = nearest(site.x, site.y)
        if group is not None and d <= sp["near"]:
            found.append((1, d, {"kind": "gang", "gang": gang.id, "site": site.id, "group": group, "at": list(at),
                                 "words": {"name": gang.name, "site": site.name}}))
    for key, hid in sorted(w.politics.get("lairs", {}).items()):
        fig = w.figures.get(hid)
        if fig is None or not fig.alive or fig.kind != "beast" or fig.id in villains or not 0 <= int(key) < len(w.sites):
            continue
        site = w.sites[int(key)]
        group = past.group_of(game, fig)
        d, at = nearest(site.x, site.y)
        if group in groups and d <= sp["near"] and site.id not in cleared(game):
            found.append((2, d, {"kind": "lair", "beast": fig.id, "site": site.id, "group": group, "at": list(at),
                                 "words": {"name": past.beast_title(fig), "site": site.name}}))
    if found:
        found.sort(key=lambda f: (beast_ratio(game, f[2]["group"]) >= DEADLY_RATIO, f[0], f[1]))
        danger = found[0][2]
    else:
        x, y = path[n // 2]
        group = choose_encounter(game.tables, game.land_key(x, y), int(w.danger[x, y]), False, True, rng)
        if group is None or group not in groups:
            return None
        area = w.area_at(x, y)
        danger = {"kind": "wild", "group": group, "at": [x, y],
                  "words": {"name": groups[group].get("name", "trouble"),
                            "area": area.name if area is not None else "the wild"}}
    danger["name"] = rng.choice(sp["danger"][danger["kind"]]).format(**{"site": "", "area": "", **danger["words"]})
    danger["met"] = False
    return danger


def on_the_road(game):
    """The danger a contract named, met where it was said to be (from the overworld walk, before the road's own
    chance of trouble): a PendingEncounter, or None."""
    from realmwalker.game import quests
    from realmwalker.game.encounters import make_encounter

    w = game.world
    p = game.player
    if game.in_local or w.settlement_at(p.x, p.y) is not None or game.over is not None:
        return None
    for q in quests.active(game):
        d = q.get("danger")
        if not d or d.get("met") or q["done"] or q["template"] not in ("escort", "deliver"):
            continue
        if max(abs(p.x - d["at"][0]), abs(p.y - d["at"][1])) > 2 or d["group"] not in game.tables.creatures.encounters:
            continue
        rng = w.rng.child(f"contract-danger/{q['id']}")
        enc = make_encounter(game, d["group"], rng)
        if not enc.creatures:
            continue
        d["met"], d["met_day"] = True, int(game.moment.total_days)
        words = {"site": "", "area": "", **d.get("words", {}), "town": w.settlements[q["town"]].name,
                 "giver": q["words"].get("giver", "they")}
        words = {k: esc(str(v)) for k, v in words.items()}
        enc.intro = rng.choice(_cspec(game)["met"][d["kind"]]).format(**words) + " " + enc.intro
        enc.attitude = "hostile"
        return enc
    return None


def terms_note(game, q) -> str:
    """Paid work shows its terms: the pay, the days, the road and what is on it."""
    from realmwalker.game.quests import dist, money_text

    w = game.world
    if q.get("contract") is None:
        return ""
    town = w.settlements[q["town"]]
    if q["template"] == "defend":
        return f"<dim>Paid work:</> {money_text(q['reward'])}, for being in {esc(town.name)} " \
               f"{esc(q['words'].get('when', 'when they come'))}."
    dest = w.settlements[q["target"]["dest"]]
    d = q.get("danger") or {}
    if d.get("met"):
        d = {"name": "met, and behind you"}
    return _cspec(game)["terms"].format(pay=money_text(q["reward"]), days=q["days"], town=esc(town.name),
                                        dest=esc(dest.name), miles=int(round(dist(town, dest) * 3)),
                                        danger=esc(d.get("name", "nothing worse than the weather")))


def notices(game, s) -> list[dict]:
    """The town's contracts, pinned up where people look for work (who to ask, and the terms)."""
    out = []
    for rec in contracts(game, s):
        q = rec["quest"]
        if rec.get("taken"):
            continue
        out.append({"kind": "hiring", "title": "HIRING",
                    "text": f"{esc(q['giver_name'])} ({esc(q['giver_job'].replace('_', ' '))}): "
                            f"{esc(label_words(game, q))} {terms_note(game, q)}"})
    return out


def label_words(game, q) -> str:
    words = {"dest": "", "raiders": "", **{k: str(v) for k, v in q["words"].items()}}
    return {"escort": f"A guard wanted on the road to {words['dest']}.",
            "deliver": f"A carrier wanted for {words['dest']}.",
            "defend": f"Swords wanted against {words['raiders']}."}.get(q["template"], "Paid work.")


# ---------------------------------------------------------------------------- in a conversation
def choices(conv) -> list:
    """Each piece of work this person has: its own choice, in its own words."""
    from realmwalker.game.dialogue import Choice

    game, npc = conv.game, conv.npc
    out = []
    for q in held_by(game, npc):
        out.append(Choice("own_work", label(game, q, conv.rng), data={"q": q["id"]}))
    return out


def label(game, q, rng) -> str:
    if q.get("commission") is not None:
        f = game.world.factions.get(q["commission"])
        words = spec(game)["commissions"]["choice"]
        # (the same words for the same piece of work, however often the menu is drawn)
        return words[q["id"] % len(words)].format(faction=esc(f.name) if f is not None else "them")
    if q.get("contract") is not None:
        rec = next((r for recs in records(game.world).values() for r in recs if r["id"] == q["contract"]), None)
        c = _cspec(game)["kinds"].get(rec["kind"]) if rec is not None else None
        if c is not None:
            words = {"dest": "", "raiders": "", **{k: str(v) for k, v in q["words"].items()}}
            return c["choice"][q["id"] % len(c["choice"])].format(**words)
    p = next((p for p in spec(game).get("pleas", []) if p["kind"] == q["template"] and p["need"] == q.get("plea")),
             None)
    return p["choice"][q["id"] % len(p["choice"])] if p is not None else "About the work..."


def offer(conv, choice) -> None:
    """They tell you what it is; you say yes or no (the conversation's quest_offer mode)."""
    from realmwalker.game import quests

    game, npc = conv.game, conv.npc
    q = next((q for q in held_by(game, npc) if q["id"] == choice.data.get("q")), None)
    conv.you_say(choice.label)
    if q is None:
        conv.npc_says("\"It is seen to. Thank you all the same.\"")
        return
    conv.npc_says(quests.pitch(game, q))
    if q.get("contract") is not None:
        conv.note(terms_note(game, q))
    danger = quests.danger_note(game, q)
    if danger:
        conv.note(danger)
    if q.get("trial") is not None:
        conv.note(quests.trial_note(game, q))
    conv.pending_offer = q
    conv.mode = "quest_offer"
