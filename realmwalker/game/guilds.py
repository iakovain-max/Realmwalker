"""What rank in a guild, order or church buys you besides quests, discounts and titles (after v1): training and, in the
thieves' guild, a safehouse. Design section 10: "Rising in rank unlocks quests, discounts, training, safehouses and
titles."

Training: from the second rank, one of the faction's people will teach you one of its skills (data/law.json
join.<kind>.trains) for each rank you have risen: a long day of it, and a fee that grows with each lesson. What you have
been taught is kept in `renown.flags["trained"]` {faction id: [skills]}.

A safehouse: a member of the thieves' guild can lie low in its house in the town of the fence they are talking to: some
days out of sight, fed and under a roof, for a fee, and the watch of that realm lose half their interest (the bounty).
Once a week.
"""

from __future__ import annotations

from realmwalker.rules.items import money_text


def _spec(game, f) -> dict:
    return game.tables.law["join"].get(f.kind, {})


def teacher_factions(game, npc) -> list:
    """The factions this person belongs to that you are a member of."""
    from realmwalker.game.people import npc_factions

    w = game.world
    out = [f for f in npc_factions(game, npc) if f.id in game.renown.members]
    secret = w.factions.get(npc.flags.get("secret", -1))
    if secret is not None and secret.id in game.renown.members and secret not in out:
        out.append(secret)
    return [f for f in out if _spec(game, f).get("trains")]


def taken(game, f) -> list[str]:
    return list(game.renown.flags.get("trained", {}).get(str(f.id), []))


def lesson_fee(game, f) -> int:
    t = game.tables.law.get("training", {"fee": 5000, "more_per_lesson": 2500})
    return int(t["fee"]) + int(t["more_per_lesson"]) * len(taken(game, f))


def offers(game, npc) -> list[tuple]:
    """(faction, skill, fee, possible, why not) for each lesson this person could give you. A member not yet risen
    gets one line that says what it takes."""
    from realmwalker.game import law, reputation

    c = game.leader
    out = []
    for f in teacher_factions(game, npc):
        r = reputation.rank(game, f.id) or 0
        spec = _spec(game, f)
        left = r - len(taken(game, f))
        skills = [s for s in spec["trains"] if s not in c.skills]
        if r == 0:
            nxt = spec["ranks"][1] if len(spec["ranks"]) > 1 else "the next rank"
            out.append((f, None, 0, False, f"they teach their own from the rank of {nxt}"))
            continue
        fee = lesson_fee(game, f)
        for s in skills:
            if left <= 0:
                why = "rise another rank for the next lesson"
            elif law.party_money(game) < fee:
                why = "you don't have enough"
            else:
                why = ""
            out.append((f, s, fee, not why, why))
    return out


def train(game, npc, f, skill: str) -> list[str]:
    """A long day's teaching (and a meal in it); the leader is trained in the skill."""
    from realmwalker.game import events, law, reputation
    from realmwalker.game.people import change_disposition

    c = game.leader
    spec = _spec(game, f)
    name = game.tables.rules["skills"][skill]["name"]
    r = reputation.rank(game, f.id) or 0
    if skill not in spec.get("trains", []) or skill in c.skills:
        return [f"There is nothing more {npc.first_name} can teach you of {name}."]
    if r - len(taken(game, f)) <= 0:
        return ["Rise another rank first."]
    fee = lesson_fee(game, f)
    if law.party_money(game) < fee:
        return [f"You can't: it costs {money_text(fee)}."]
    events.pay(game, fee)
    hours = int(game.tables.law.get("training", {}).get("hours", 10))
    game.pass_time(hours * 60, "rest")
    for m in game.party:
        m.hunger = max(0.0, m.hunger - 40)
        m.thirst = max(0.0, m.thirst - 30)
    c.skills.append(skill)
    game.renown.flags.setdefault("trained", {}).setdefault(str(f.id), []).append(skill)
    change_disposition(npc, 3)
    game.dirty = True
    bonus = game.sheet(c).skill_bonus(skill)
    return [f"{npc.first_name} spends the long day on you: over and over, until it goes right without thinking "
            f"({money_text(fee)}).",
            f"<good>{c.name.split()[0]} is trained in {name}</> (now {bonus:+d})."]


# ---------------------------------------------------------------------------- the safehouse
def safehouse_offer(game, npc):
    """(faction, fee, possible, why not) when this person can hide you, else None."""
    from realmwalker.game import law
    from realmwalker.game.law_talk import realm_of_npc

    if not law.is_fence(game, npc):
        return None
    f = game.world.factions[npc.flags["secret"]]
    spec = game.tables.law.get("safehouse", {"fee": 1500, "days": 3, "bounty_left": 0.5, "every_days": 7})
    fee = int(spec["fee"])
    realm = realm_of_npc(game, npc)
    last = game.renown.flags.get("lay_low_day")
    if realm is None or game.renown.bounties.get(realm.id, 0) <= 0:
        return f, fee, False, "nobody is looking for you here"
    if last is not None and game.moment.total_days - int(last) < int(spec["every_days"]):
        return f, fee, False, "you hid there only days ago; they will not risk it again so soon"
    if law.party_money(game) < fee:
        return f, fee, False, "you don't have enough"
    return f, fee, True, ""


def lie_low(game, npc) -> list[str]:
    """Days out of sight in the guild's house: fed and sheltered, and the watch lose half their interest."""
    from realmwalker.game import events
    from realmwalker.game.law_talk import realm_of_npc

    offer = safehouse_offer(game, npc)
    if offer is None or not offer[2]:
        return [f"You can't: {offer[3]}." if offer else "They know nothing of any safehouse."]
    f, fee, _, _ = offer
    spec = game.tables.law.get("safehouse", {"days": 3, "bounty_left": 0.5})
    realm = realm_of_npc(game, npc)
    events.pay(game, fee)
    game.confined = {"kind": "safehouse"}  # fed and under a roof, going nowhere
    try:
        for _ in range(int(spec["days"])):
            game.pass_time(16 * 60, "rest")
            game.pass_time(8 * 60, "sleep")
    finally:
        game.confined = None
    before = game.renown.bounties.get(realm.id, 0)
    game.renown.bounties[realm.id] = int(before * float(spec["bounty_left"]))
    game.renown.flags["lay_low_day"] = game.moment.total_days
    game.dirty = True
    return [f"{npc.first_name} takes you through a yard, a cellar and a door you would never have found. You spend "
            f"{int(spec['days'])} days in a loft over a tannery, eating what they bring ({money_text(fee)}).",
            f"<good>When you come out, the watch of {realm.name} have other things on their minds:</> the price on "
            f"you is {money_text(game.renown.bounties[realm.id])} now."]
