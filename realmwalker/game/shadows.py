"""The people of the shadows (Expansion 4 Part C.3): the black market, poison slipped into a cup, and duels of honour.

- **Poison and the law** (DMG 2024 p. 90, "Purchasing Poison"): data/law.json `shadows.poison_allowed` names the peoples
  whose realms let poison be sold openly (apothecaries in cities stock the book's poisons); everywhere else every poison
  is contraband (`law.contraband_for`: found at the gate, taken), the honest shops will not sell it, and it is bought
  under the counter from a thieves' guild member who knows you as one of their own: the black market
  (`black_market_choice`; a shop of kind "black_market", data/economy.json, at its markup).
- **The guilds' work**: a thieves' guild's commissions to its own are the killing and thieving work (game/story/work.py,
  work.json `by_kind`, given by its fences): the assassins' trade is the thieves' guilds' darker side; there is no
  separate assassins' faction.
- **A poisoned cup**: in a conversation where drink is poured (a town), an ingested poison carried by the party can be
  slipped into the other's cup (`cup_choices`, `slip`): Sleight of Hand against their watchfulness (caught: an assault,
  with witnesses), then their Constitution save against the poison. A lethal dose kills them before the night is out
  (a murder nobody saw); Truth Serum makes them tell their secrets; Torpor sends them home to sleep it off.
- **Duels of honour** (`shadows.duels`: the peoples whose gentlefolk keep the custom): a gentleman or gentlewoman
  (social "high") of such a people answers a failed threat with a challenge; accepted, it is a fight to the first fall
  that the law does not call murder or assault (`duel_settled` from fight._settle_townsfolk); refused, the town
  thinks the less of you.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.textgen import escape_markup as escape
from realmwalker.rules import poisons

CUP_KINDS = ("ingested",)
LETHAL = ("assassins_blood", "midnight_tears", "pale_tincture", "potion_of_poison")


def spec(game) -> dict:
    return game.tables.law.get("shadows", {})


# ---------------------------------------------------------------------------- poison and the law
def poison_ids(tables) -> list[str]:
    return sorted(i for i, d in tables.items.defs.items() if d.get("poison"))


def poison_allowed(game, culture: str) -> bool:
    return culture in spec(game).get("poison_allowed", ())


def shop_sells(game, settlement, item_id: str) -> bool:
    """Whether an honest shop here may stock this (no poison where the realm forbids it)."""
    if not game.tables.items.get(item_id).get("poison"):
        return True
    from realmwalker.world import factions as fx

    realm = fx.realm_of_settlement(game.world, settlement) if game.world.factions else None
    culture = realm.culture if realm is not None else settlement.culture
    return poison_allowed(game, culture)


def black_market_choice(conv) -> list:
    """A guild member who knows you as one of their own, with no shop of their own: what is sold under the counter."""
    from realmwalker.game import law
    from realmwalker.game.dialogue import Choice

    game, npc = conv.game, conv.npc
    if not law.is_fence(game, npc) or game.tables.people["occupations"].get(npc.job, {}).get("trade") or \
            npc.flags.get("black_market"):
        return []  # (once shown, the wares are offered as any shop's are)
    if game.world.settlements[npc.settlement].kind not in ("town", "city"):
        return []
    return [Choice("black_market", "What do you have that the shops don't sell?")]


def open_black_market(conv) -> str:
    npc = conv.npc
    npc.flags["black_market"] = True  # (economy.shop_kind: their wares are the guild's)
    conv.you_say("What do you have that the shops don't sell?")
    conv.npc_says("A slow look round first. \"Not here. Round the back, and keep your voice down.\"")
    return "trade"


def choices(conv) -> list:
    """Everything this module adds to a conversation."""
    if not conv.game.world.factions and not cup_poisons(conv.game):
        return duel_choices(conv)
    return duel_choices(conv) + black_market_choice(conv) + cup_choices(conv)


def choose(conv, choice) -> str | None:
    if choice.id == "black_market":
        return open_black_market(conv)
    if choice.id == "slip_poison":
        slip(conv, int(choice.data["uid"]))
    elif choice.id == "duel_accept":
        accept(conv)
    elif choice.id == "duel_refuse":
        refuse(conv)
    return None


# ---------------------------------------------------------------------------- a poisoned cup
def cup_poisons(game) -> list:
    """The ingested poisons the party carries, shown for what they are."""
    out = []
    for c in game.party:
        if not c.alive:
            continue
        for it in c.inventory:
            rec = poisons.record(game.tables, it.def_id)
            if rec and rec["kind"] in CUP_KINDS and not poisons.masked(it):
                out.append((c, it))
    return out


def cup_choices(conv) -> list:
    from realmwalker.game.dialogue import Choice

    game = conv.game
    if conv.hostile or conv.npc.flags.get("cup_poisoned"):
        return []
    out = []
    for c, it in cup_poisons(game):
        name = game.tables.items.get(it.def_id)["name"]
        out.append(Choice("slip_poison", f"[Sleight of Hand] Slip the {name} into their cup.", data={"uid": it.uid}))
    return out[:3]


def watchfulness(npc) -> int:
    return 10 + (3 if "suspicious" in npc.traits else 0) + (3 if npc.job in ("guard", "lord") else 0) + \
        (2 if npc.flags.get("secret") is not None else 0)


def npc_save(game, npc, dc: int, rng) -> tuple[bool, int]:
    """Their Constitution save, by their own stat block."""
    c = game.tables.creatures[npc.stats] if npc.stats in game.tables.creatures else {}
    con = int((c.get("abilities") or {}).get("con", 10))
    bonus = int((c.get("saves") or {}).get("con", (con - 10) // 2))
    total = dice.d20(rng).natural + bonus
    return total >= dc, total


def npc_hp(game, npc) -> int:
    c = game.tables.creatures[npc.stats] if npc.stats in game.tables.creatures else {}
    hp = c.get("hp", 4)
    return int(c.get("hp_avg", 0) or (dice.parse(hp)[0] * (dice.parse(hp)[1] + 1) // 2 + dice.parse(hp)[2]
                                      if isinstance(hp, str) else hp))


def slip(conv, uid: int) -> None:
    """Into their cup, if nobody sees."""
    from realmwalker.game import law
    from realmwalker.game.dialogue import change_disposition
    from realmwalker.rules.inventory import remove_item

    game, npc = conv.game, conv.npc
    owner = next((c for c in game.party if c.item(uid) is not None), None)
    item = owner.item(uid) if owner is not None else None
    if item is None:
        return
    rec = poisons.record(game.tables, item.def_id) or {}
    name = game.tables.items.get(item.def_id)["name"]
    remove_item(owner, uid, 1)
    game.dirty = True
    npc.flags["cup_poisoned"] = game.world.time
    rng = game.world.rng.child(f"cup/{npc.id}/{game.world.time}")
    sheet = game.sheet(owner)
    roll = dice.d20(rng).natural
    total = roll + sheet.skill_bonus("sleight_of_hand")
    dc = watchfulness(npc)
    conv.you_say("You lean across for the jug and fill their cup.")
    words = f"<dim>(Sleight of Hand {roll} + {total - roll} = {total} vs {dc})</>"
    if total < dc:
        change_disposition(npc, -60)
        npc.remember("caught the traveller poisoning a cup")
        conv.npc_says(f"\"What did you just put in that?\" {escape(npc.first_name)} knocks the cup away.")
        conv.note(f"<danger>Caught.</> {words}")
        if game.world.factions:
            law.commit(game, "assault", victim=npc, witnesses=[npc] + law.witnesses_here(game, exclude=[npc]))
        return
    conv.note(f"<good>Nobody sees.</> {words}")
    ok, save = npc_save(game, npc, int(rec.get("dc", 10)), rng)
    first = escape(npc.first_name)
    if rec.get("truth") and not ok:
        conv.note(f"<magic>{first} drinks. A moment later their eyes lose their guard.</> <dim>({name}: "
                  f"Constitution {save} vs {rec['dc']})</>")
        tell_truth(conv)
        return
    if item.def_id in LETHAL or (rec.get("damage") and not ok):
        dmg = 0 if ok and not rec.get("half") and not rec.get("sure") else \
            dice.roll(rec.get("damage", "1d6"), rng).total
        if ok and rec.get("half") and not rec.get("sure"):
            dmg //= 2
        if item.def_id == "pale_tincture" and not ok:
            dmg = npc_hp(game, npc)  # (a wasting that no healer of theirs can stop)
        if dmg >= npc_hp(game, npc):
            conv.note(f"<danger>{first} drinks it down. They will not see another morning.</> <dim>({name}: "
                      f"Constitution {save} vs {rec.get('dc', 10)})</>")
            die_of_poison(game, npc)
            conv.ended = True
            return
        conv.note(f"{first} drinks, pales, and puts the cup down half full. <dim>({name}: Constitution {save} vs "
                  f"{rec.get('dc', 10)}; it was not enough to kill)</>")
        change_disposition(npc, -5)
        return
    if rec.get("slow") and not ok:
        npc.flags["fled_until"] = game.world.time + 8 * 60  # (home to sleep it off)
        npc.present = False
        conv.note(f"{first} yawns, and yawns again, and goes home heavy-footed to sleep. <dim>({name}: "
                  f"Constitution {save} vs {rec['dc']})</>")
        conv.ended = True
        return
    conv.note(f"{first} drinks, and nothing comes of it. <dim>({name}: Constitution {save} vs {rec.get('dc', 10)})</>")


def die_of_poison(game, npc) -> None:
    """A death in the night that nobody saw: the law looks, and finds no one (unless a witness saw the cup)."""
    from realmwalker.game import quests

    npc.alive = False
    npc.present = False
    game.leader.deeds.append(f"poisoned {npc.name}, the {npc.title}")
    if game.world.factions:
        from realmwalker.game import law

        law.commit(game, "murder", victim=npc, witnesses=[])
    if game.quests:
        quests.on_npc_death(game, npc)
    game.cue("acid")


def tell_truth(conv) -> None:
    """Truth Serum: they cannot knowingly lie. What they hide comes out: a secret faction, what they want, a work's
    hidden side."""
    from realmwalker.game import quests
    from realmwalker.game.reputation import know

    game, npc = conv.game, conv.npc
    w = game.world
    said = False
    secret = w.factions.get(npc.flags.get("secret", -1))
    if secret is not None:
        know(game, secret.id)
        game.renown.flags.setdefault("contacts", {})[str(secret.id)] = npc.id
        npc.flags["probed"] = True
        conv.npc_says(f"\"I belong to {escape(secret.name)}.\" They look appalled at their own mouth.")
        said = True
    if npc.profile.get("want"):
        conv.note(f"What {escape(npc.first_name)} wants: {npc.profile['want']}.")
        said = True
    from realmwalker.game.story import work

    offer = next(iter(work.held_by(game, npc)), None) if game.quests is not None else None
    if offer is not None and offer.get("hidden") and not offer.get("revealed"):
        conv.npc_says("\"About the work I offered you... there is more to it.\"")
        quests.reveal(game, offer)
        said = True
    memories = [m for m in npc.memory if "traveller" in m]
    if memories:
        conv.npc_says(f"\"I remember you: {escape(memories[-1])}.\"")
        said = True
    if not said:
        conv.npc_says("\"I have nothing to hide. Truly.\" And, for once, it is true.")


# ---------------------------------------------------------------------------- duels of honour
def duelling_folk(game, npc) -> bool:
    """A gentle person of a people who settle insults with steel."""
    culture = game.world.settlements[npc.settlement].culture if 0 <= npc.settlement < len(
        game.world.settlements) else ""
    return npc.social == "high" and culture in spec(game).get("duels", ()) and npc.alive and \
        npc.stats in game.tables.creatures


def challenge(conv) -> bool:
    """After a failed threat: a gentle person of a duelling people names the time and the place. True if they did."""
    npc = conv.npc
    if not duelling_folk(conv.game, npc) or npc.flags.get("duelled"):
        return False
    npc.flags["challenge"] = conv.game.world.time
    conv.npc_says(f"\"You will answer for that with steel, not words.\" {escape(npc.first_name)} draws off a glove. "
                  "\"Here, now, to the first fall.\"")
    return True


def duel_choices(conv) -> list:
    from realmwalker.game.dialogue import Choice

    if conv.npc.flags.get("challenge") is None or conv.npc.flags.get("duelled"):
        return []
    return [Choice("duel_accept", "[Duel] I accept. To the first fall."),
            Choice("duel_refuse", "I will not fight you.")]


def accept(conv) -> None:
    from realmwalker.game.fight import start_battle
    from realmwalker.rules.creatures import spawn

    game, npc = conv.game, conv.npc
    npc.flags["duelled"] = True
    npc.flags.pop("challenge", None)
    conv.you_say("Name your second.")
    creature = spawn(game.tables, npc.stats, conv.rng, 9000 + npc.id)
    creature.name = npc.first_name
    creature.named = True
    game.battle_npcs[creature.uid] = npc.id
    game.renown.flags["duel"] = npc.id
    start_battle(game, [creature], f"{npc.first_name} salutes with the blade, and comes on.",
                 title=f"A duel with {npc.first_name}", near=(npc.x, npc.y))
    conv.ended = True


def refuse(conv) -> None:
    from realmwalker.game.dialogue import change_disposition

    game, npc = conv.game, conv.npc
    npc.flags["duelled"] = True
    npc.flags.pop("challenge", None)
    change_disposition(npc, -20)
    conv.you_say("I will not fight you.")
    conv.npc_says("\"Then you are what I thought you were.\" They turn their back on you.")
    settlement = game.world.settlements[npc.settlement]
    owner = settlement.owner if game.world.factions else None
    words = f"refused a duel of honour in {settlement.name}"
    if owner is not None and owner >= 0:
        from realmwalker.game import reputation

        reputation.deed(game, words, {owner: -3})  # (it writes the deed down too)
    else:
        game.leader.deeds.append(words)


def duel_settled(game, npc, f, outcome: str) -> bool:
    """A duel's end (from fight._settle_townsfolk): no crime either way; honour to the one left standing. True if this
    fight was a duel."""
    if game.renown.flags.get("duel") != npc.id:
        return False
    game.renown.flags.pop("duel", None)
    settlement = game.world.settlements[npc.settlement]
    owner = settlement.owner if game.world.factions else None
    from realmwalker.game import reputation

    if f.state == "dead":
        npc.alive = False
        npc.present = False
        game.say(f"<warn>{escape(npc.first_name)} is dead. A duel is a duel: the law looks the other way.</>", "warn")
        words = f"killed {npc.name} in a duel of honour in {settlement.name}"
        if owner is not None and owner >= 0:
            reputation.deed(game, words, {owner: 2})
        else:
            game.leader.deeds.append(words)
    elif outcome == "victory":
        npc.disposition = max(npc.disposition, 10)
        npc.remember("was bested by the traveller in a fair duel")
        npc.flags["fled_until"] = game.world.time + 6 * 60
        npc.present = False
        game.say(f"<good>{escape(npc.first_name)} yields, and gives you the salute. Honour is satisfied.</>", "good")
        words = f"won a duel of honour against {npc.name} in {settlement.name}"
        if owner is not None and owner >= 0:
            reputation.deed(game, words, {owner: 4})
        else:
            game.leader.deeds.append(words)
    else:
        npc.remember("bested the traveller in a duel")
        game.leader.deeds.append(f"lost a duel of honour to {npc.name} in {settlement.name}")
    return True

