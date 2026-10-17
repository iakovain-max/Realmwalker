"""What conversations can do about the law and the factions (M6): settle your debts or give yourself up, buy a
witness's silence, hand over prisoners, buy a licence for magic, join a guild or church, ask a ruler for an
honour, find the hidden guilds, cut a purse, or draw steel."""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.game import law, reputation
from realmwalker.game.people import change_disposition, npc_factions
from realmwalker.rules.items import money_text
from realmwalker.world import factions as fx

AUTHORITIES = ("guard", "headman", "lord")


def _count(n: int, word: str) -> str:
    """How many, in words: "a prisoner", "3 prisoners"."""
    return f"a {word}" if n == 1 else f"{n} {word}s"


def realm_of_npc(game, npc):
    return fx.realm_of_settlement(game.world, game.world.settlements[npc.settlement])


def joinable(game, npc) -> list:
    """Factions this person could swear you into: their own guild or church, or a secret one you have found."""
    out = []
    w = game.world
    fig = w.figures.get(npc.flags.get("figure", -1))
    for f in npc_factions(game, npc):
        if f.kind in game.tables.law["join"] and (f.kind not in fx.REALM_KINDS):
            out.append(f)
    secret = w.factions.get(npc.flags.get("secret", -1))
    if secret is not None and secret.id in game.renown.known and secret not in out:
        out.append(secret)
    if fig is not None and fig.faction in w.factions:
        f = w.factions[fig.faction]
        if f.kind in game.tables.law["join"] and f not in out:
            out.append(f)
    return [f for f in out if f.id not in game.renown.members]


def choices(conv) -> list:
    from realmwalker.game.dialogue import Choice

    game = conv.game
    npc = conv.npc
    w = game.world
    if not w.factions:
        return []
    out = []
    realm = realm_of_npc(game, npc)
    law_data = game.tables.law
    if realm is not None and npc.job in AUTHORITIES:
        bounty = game.renown.bounties.get(realm.id, 0)
        if bounty > 0:
            ok = law.can_buy_off(game, realm.id)
            out.append(Choice("pay_fines", f"I want to settle what I owe ({money_text(bounty)}).",
                              ok and law.party_money(game) >= bounty,
                              "your crimes are too grave to buy off" if not ok else "you don't have enough"))
            out.append(Choice("surrender", "I give myself up."))
        captives = game.renown.flags.get("captives", [])
        if captives:
            out.append(Choice("prisoners", f"I have {len(captives)} prisoner{'s' if len(captives) > 1 else ''} for "
                                           f"the law."))
    if realm is not None and npc.job in ("headman", "lord", "mage") and \
            fx.laws_of(w, realm).get("magic") == "licensed" and \
            realm.id not in game.renown.flags.get("licences", []) and law.party_casts(game):  # (Expansion 3 G.2:
        # anyone in the party who casts; the circle's mages write licences too)
        fee = int(law_data["licence_fee"])
        out.append(Choice("licence", f"I need a licence to work magic ({money_text(fee)}).",
                          law.party_money(game) >= fee, "you don't have enough"))
    if law.is_fence(game, npc) and game.renown.flags.get("captives"):
        captives = game.renown.flags["captives"]
        out.append(Choice("ransom", f"I have {len(captives)} prisoner{'s' if len(captives) > 1 else ''}. "
                                    f"Their own people would pay to have them back."))
    if law.unreported_seen_by(game, npc):
        cost = hush_price(game, npc)
        out.append(Choice("hush_pay", f"[Persuasion] About what you saw... ({money_text(cost)})",
                          law.party_money(game) >= cost, "you don't have enough"))
        out.append(Choice("hush_threat", "[Intimidation] You saw nothing. Understand?"))
    secret = w.factions.get(npc.flags.get("secret", -1))
    if secret is not None and secret.id not in game.renown.known and not npc.flags.get("probed"):
        skill = "insight" if secret.kind == "thieves_guild" else "religion"
        hint = "You look like someone who knows the night trade." if secret.kind == "thieves_guild" else \
            "You pray to other gods, don't you?"
        out.append(Choice("probe", f"[{skill.capitalize()}] {hint}"))
    for f in joinable(game, npc):
        problem = reputation.join_problem(game, f)
        out.append(Choice("join", f"I want to join {f.name}.", problem is None, problem or "", {"faction": f.id}))
    fig = w.figures.get(npc.flags.get("figure", -1))
    if fig is not None and fig.role == "ruler" and fig.faction in w.factions:
        f = w.factions[fig.faction]
        if f.kind in law_data["titles"]["names"]:
            problem = reputation.title_problem(game, f)
            if problem != "they have already honoured you":
                out.append(Choice("title", f"Ask {fig.first_name} for an honour.", problem is None, problem or "",
                                  {"faction": f.id}))
    from realmwalker.game import guilds

    for f, skill, fee, ok, why in guilds.offers(game, npc)[:3]:
        if skill is None:
            out.append(Choice("train", "Will you teach me what you know?", False, why))
        else:
            name = game.tables.rules["skills"][skill]["name"]
            out.append(Choice("train", f"Teach me {name}. ({money_text(fee)}, a long day)", ok, why,
                              {"faction": f.id, "skill": skill}))
    hide = guilds.safehouse_offer(game, npc)
    if hide is not None:
        out.append(Choice("lie_low", f"I need somewhere to lie low. ({money_text(hide[1])})", hide[2], hide[3]))
    out.append(Choice("pickpocket", "[Sleight of Hand] Try for their purse."))
    out.append(Choice("attack", "Attack them."))
    return out


def hush_price(game, npc) -> int:
    crimes = law.unreported_seen_by(game, npc)
    worst = max((law.crime_def(game, r["crime"])["fine"] for r in crimes), default=500)
    return max(500, int(worst * 0.4))


def choose(conv, choice) -> str | None:
    game = conv.game
    npc = conv.npc
    w = game.world
    cid = choice.id
    rng = conv.rng
    if cid == "pay_fines":
        realm = realm_of_npc(game, npc)
        conv.you_say("I want to settle what I owe.")
        conv.note(law.pay_bounty(game, realm.id))
    elif cid == "surrender":
        conv.you_say("I give myself up.")
        conv.npc_says("\"Wise. Come along, then.\"")
        law.start_arrest(game, npc if npc.job == "guard" else None)
        conv.ended = True
    elif cid == "prisoners":
        conv.you_say("I have prisoners for the law.")
        conv.note(hand_over(game, npc))
    elif cid == "ransom":
        conv.you_say("I have prisoners. Their own people would pay to have them back.")
        conv.note(ransom(game, npc))
    elif cid == "licence":
        conv.you_say("I need a licence to work magic.")
        conv.note(law.buy_licence(game, realm_of_npc(game, npc).id))
    elif cid == "hush_pay":
        hush(conv, pay=True)
    elif cid == "hush_threat":
        hush(conv, pay=False)
    elif cid == "probe":
        probe(conv)
    elif cid == "join":
        f = w.factions[choice.data["faction"]]
        conv.you_say(f"I want to join {f.name}.")
        conv.note(reputation.join(game, f))
    elif cid == "title":
        f = w.factions[choice.data["faction"]]
        conv.you_say("I have served your house well. I ask for an honour.")
        conv.note(reputation.grant_title(game, f))
    elif cid in ("train", "lie_low"):
        from realmwalker.game import guilds

        if cid == "train":
            f = w.factions[choice.data["faction"]]
            skill = game.tables.rules["skills"][choice.data["skill"]]["name"]
            conv.you_say(f"Will you teach me {skill}?")
            conv.npc_says("\"For one of ours? Sit down. We start with how you are holding your hands.\"")
            for text in guilds.train(game, npc, f, choice.data["skill"]):
                conv.note(text)
        else:
            conv.you_say("I need somewhere to lie low for a while.")
            conv.npc_says("\"Say nothing, and follow me. Not so close.\"")
            for text in guilds.lie_low(game, npc):
                conv.note(text)
    elif cid == "pickpocket":
        pickpocket(conv)
    elif cid == "attack":
        conv.you_say("(You draw steel.)")
        conv.start_fight()
        law.commit(game, "assault", victim=npc, witnesses=law.witnesses_here(game))
    return None


# ---------------------------------------------------------------------------- the pieces
def hand_over(game, npc) -> str:
    captives = game.renown.flags.pop("captives", [])
    if not captives:
        return "You have no prisoners."
    total = sum(int(c["reward"]) for c in captives)
    game.leader.money += total
    realm = realm_of_npc(game, npc)
    amounts = {}
    if realm is not None:
        amounts[realm.id] = 3.0 * len(captives)
    for c in captives:
        fid = c.get("faction", -1)
        if fid in w_factions(game):
            amounts[fid] = amounts.get(fid, 0.0) - 6.0
    names = ", ".join(c["name"] for c in captives[:3]) + (" and the rest" if len(captives) > 3 else "")
    if game.party[1:]:
        from realmwalker.game.companions import react

        react(game, "prisoners_to_law")
    n = len(captives)
    reputation.deed(game, f"handed {_count(n, 'prisoner')} to the law", amounts,
                    immediate=(realm.id,) if realm is not None else (), fame=len(captives),
                    importance=1 + (len(captives) >= 3),
                    news_text=f"{game.leader.name} brought {_count(n, 'outlaw')} to the law in "
                              f"{game.world.settlements[npc.settlement].name}")
    return f"<good>The watch takes {names} off your hands and pays {money_text(total)}.</>"


def ransom(game, npc) -> str:
    """Sell prisoners back to their own people through the guild. It pays better than the watch and it is
    never spoken of: no news, no fame, and their friends remember who let them go."""
    captives = game.renown.flags.pop("captives", [])
    if not captives:
        return "You have no prisoners."
    share = float(game.tables.law["ransom_share"])
    total = sum(int(int(c["reward"]) * share) for c in captives)
    game.leader.money += total
    amounts = {}
    guild = game.world.factions.get(npc.flags.get("secret", -1))
    if guild is not None:
        amounts[guild.id] = 4.0
    for c in captives:
        fid = c.get("faction", -1)
        if fid in w_factions(game):
            amounts[fid] = amounts.get(fid, 0.0) + 6.0
    realm = realm_of_npc(game, npc)
    if realm is not None:
        amounts[realm.id] = amounts.get(realm.id, 0.0) - 3.0 * len(captives)
    names = ", ".join(c["name"] for c in captives[:3]) + (" and the rest" if len(captives) > 3 else "")
    if game.party[1:]:
        from realmwalker.game.companions import react

        react(game, "ransom")
    reputation.deed(game, f"sold {_count(len(captives), 'prisoner')} back to their own people",
                    amounts, immediate=(guild.id,) if guild is not None else (),
                    fame=0, infamy=len(captives), importance=1, news_text=None)
    change_disposition(npc, 4)
    return (f"<good>{npc.first_name} takes {names} away by a back door and comes back with "
            f"{money_text(total)}.</> <dim>Nobody will hear of it from them.</>")


def w_factions(game) -> dict:
    return game.world.factions


def hush(conv, pay: bool) -> None:
    game = conv.game
    npc = conv.npc
    crimes = law.unreported_seen_by(game, npc)
    worst = max(law.crime_def(game, r["crime"])["severity"] for r in crimes)
    if pay:
        cost = hush_price(game, npc)
        conv.you_say("About what you saw. Perhaps this will help you forget.")
        dc = 8 + worst * 2 + (4 if "honest" in npc.traits else 0) - (4 if "greedy" in npc.traits else 0)
        roll = conv.influence_roll("persuasion")
        if roll >= dc:
            law.take_money(game, cost)
            npc.purse += cost
            law.silence(npc, crimes)
            npc.remember("took the traveller's money to forget something")
            conv.npc_says("\"Forget what?\"")
            conv.note(f"<good>{npc.first_name} will keep quiet.</> <dim>(Persuasion {roll} vs {dc})</>")
            return
        conv.npc_says("\"You think I can be bought? We'll see what the watch thinks.\"")
    else:
        conv.you_say("You saw nothing. Understand?")
        dc = 10 + worst * 2 + (-3 if "nervous" in npc.traits else 0) + (4 if "brave" in npc.traits else 0)
        roll = conv.influence_roll("intimidation")
        if roll >= dc:
            law.silence(npc, crimes)
            change_disposition(npc, -15)
            npc.remember("was frightened into silence by the traveller")
            conv.npc_says("\"I... I didn't see anything. Nothing at all.\"")
            conv.note(f"<good>{npc.first_name} will keep quiet, out of fear.</> <dim>(Intimidation {roll} vs {dc})</>")
            return
        conv.npc_says("\"Threaten me, will you? WATCH!\"")
    conv.note(f"<warn>That went badly.</> <dim>(roll {roll} vs {dc})</>")
    for rec in crimes:
        law.report(game, rec)
    if conv.town_has_guards():
        law.start_arrest(game, None)
        conv.ended = True


def probe(conv) -> None:
    from realmwalker.game.reputation import know

    game = conv.game
    npc = conv.npc
    w = game.world
    secret = w.factions[npc.flags["secret"]]
    npc.flags["probed"] = True
    skill = "insight" if secret.kind == "thieves_guild" else "religion"
    roll = dice.d20(conv.rng).natural + game.sheet().skill_bonus(skill)
    bonus = 3 if game.leader.background == "criminal" and secret.kind == "thieves_guild" else 0
    if roll + bonus >= 13:
        know(game, secret.id)
        game.renown.flags.setdefault("contacts", {})[str(secret.id)] = npc.id
        if secret.kind == "thieves_guild":
            conv.npc_says("\"Keep your voice down.\" A long look. \"Maybe I know some people. Maybe they'd want to "
                          f"meet you.\" They call themselves {secret.name}.")
        else:
            conv.npc_says(f"Their eyes go flat. \"There are older powers than the priests', stranger.\" A whisper: "
                          f"{secret.name}.")
        conv.note(f"<magic>You have found {secret.name}.</> <dim>({skill.capitalize()} {roll + bonus} vs 13)</>")
    else:
        change_disposition(npc, -10)
        conv.npc_says("\"I don't know what you mean.\"")
        conv.note(f"<dim>({skill.capitalize()} {roll + bonus} vs 13)</>")


def pickpocket(conv) -> None:
    game = conv.game
    npc = conv.npc
    sheet = game.sheet()
    rng = conv.rng
    roll = dice.d20(rng).natural + sheet.skill_bonus("sleight_of_hand")
    watch = 10 + (2 if "suspicious" in npc.traits else 0) + (2 if npc.job == "guard" else 0)
    npc.flags["picked_day"] = game.moment.total_days
    if roll >= watch:
        take = min(npc.purse, max(1, int(npc.purse * rng.uniform(0.2, 0.6))))
        npc.purse -= take
        game.leader.money += take
        conv.note(f"<loot>Your fingers find their purse: {money_text(take)}.</> <dim>(Sleight of Hand {roll} vs {watch})</>"
                  if take else f"<dim>Their purse is empty. (Sleight of Hand {roll} vs {watch})</>")
        if game.quests:
            from realmwalker.game import quests

            for line in quests.on_pickpocket(game, npc):
                conv.note(line)
        from realmwalker.game import glamour

        others = [n for n in law.witnesses_here(game, exclude=[npc])
                  if dice.d20(rng).natural + 2 - glamour.watcher_minus(game, n) >= roll]
        if others:
            game.say(f"<warn>{others[0].label().capitalize()} saw that.</>", "warn")
            law.commit(game, "pickpocket", victim=npc, value=take, witnesses=others)
        return
    conv.npc_says("\"Hey! Thief! THIEF!\"")
    conv.note(f"<warn>They catch your hand.</> <dim>(Sleight of Hand {roll} vs {watch})</>")
    change_disposition(npc, -40)
    law.commit(game, "pickpocket", victim=npc, witnesses=[npc] + law.witnesses_here(game, exclude=[npc]))
    conv.ended = True
