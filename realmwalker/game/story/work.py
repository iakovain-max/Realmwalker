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
The quest dicts are built by `quests.make` for a target the picker of its kind chose. Contracts (C.3) and situations
(C.6) will wait here too.
"""

from __future__ import annotations

from realmwalker.core.textgen import escape_markup as esc

COMMISSIONS = "commissions"
PLEAS = "pleas"


def spec(game) -> dict:
    return game.tables.work or {}


# ---------------------------------------------------------------------------- what waits
def waiting(game) -> list[dict]:
    """Every piece of work waiting to be taken: commissions and pleas (so nothing else chases the same thing)."""
    out = list(game.renown.flags.get(COMMISSIONS, {}).values())
    for town in game.world.towns.values():
        out += list(town.flags.get(PLEAS, {}).values())
    return out


def held_by(game, npc) -> list[dict]:
    """The work this person has for you, now: their faction's commission, their own plea."""
    if not npc.alive or npc.flags.get("disgraced"):
        return []
    from realmwalker.game import quests

    if any(q["giver"] == npc.id for q in quests.active(game)):
        return []  # one piece of work at a time from each person
    out = [q for q in game.renown.flags.get(COMMISSIONS, {}).values() if q["giver"] == npc.id]
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
    danger = quests.danger_note(game, q)
    if danger:
        conv.note(danger)
    if q.get("trial") is not None:
        conv.note(quests.trial_note(game, q))
    conv.pending_offer = q
    conv.mode = "quest_offer"
