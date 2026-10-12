"""People who follow you for reasons other than a wage (after v1; Anton asked for them on 2026-09-26).

- Sworn swords: a realm that honours you (standing 50 or more) lends you one of its own when you ask its ruler:
  a knight of the household, a sergeant of the city guard, a hearth-guard of the hold. The realm pays them. If it
  stops thinking well of you (below 15), or puts a price on your head, they are called home.
- Dreamers: a farm lad, a serving girl, a drunk at the inn, told about the work you have taken. They come for a
  share of what it pays (a fifth of every reward while they are with you). Tell them it will make you both rich
  (Deception, which is easier) and they will remember it when the money comes.
- The restless: a hard word (Persuasion) can talk a young guard, a woodcutter or an acolyte into leaving home.
- The homeless: survivors of a burned, sacked or raided place wait at the inns nearby, and follow you for their
  keep.
- Admirers: once your name is known (fame 10, and more of it than infamy), someone who has heard of you may be
  waiting at an inn. They like you less as your name darkens.

None of them take a wage, and none carry a purse. The words are in data/companions.json ("bonds"). Unique
companions, hand-made and the same in every world, are in game/uniques.py.
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.rng import RNG
from realmwalker.game import companions as comp
from realmwalker.rules.character import Character
from realmwalker.rules.items import money_text

LENDING_KINDS = ("kingdom", "noble_house", "free_city", "clan", "highland_clan", "elven_realm")
SWORN_STANDING = 50  # Honoured: they will lend you one of their own
RECALL_BELOW = 15  # below Respected, they want their sword back
LOST_DAYS = 90  # after one of theirs dies with you, a realm will not lend another for a season
DREAM_DC = 12  # telling a farm lad the truth about the work
LIE_DC = 10  # telling them it will make you both rich
RESTLESS_DC = 16  # talking someone into leaving home
RICH = 1000  # ten gold is riches, to a farm lad: the lie was true after all
IDLE_DAYS = 7  # a dreamer with no paying work in hand for this long starts to wonder
ADMIRER_FAME = 10
RUIN_REACH = 20  # tiles: how far the homeless walk to the next inn
TRAIT_VALUES = {"brave": "brave", "kind": "compassionate", "generous": "compassionate", "pious": "devout",
                "honest": "honourable", "proud": "honourable", "greedy": "greedy", "cruel": "cruel", "bitter": "rebel",
                "sly": "rebel", "nervous": "cautious", "suspicious": "cautious"}
JOB_CLASS = {"guard": ("fighter", "soldier"), "acolyte": ("cleric", "acolyte"), "fisher": ("rogue", "folk_hero"),
             "serving_hand": ("rogue", "folk_hero"), "carter": ("rogue", "folk_hero"), "beggar": ("rogue", "criminal"),
             "weaver": ("rogue", "guild_artisan")}


def spec(game, bond: str) -> dict:
    return game.tables.companions["bonds"][bond]


def following(game, bond: str | None = None) -> list[Character]:
    return [c for c in list(game.party[1:]) + comp.waiting(game)
            if c.companion and (bond is None or comp.bond_of(c) == bond)]


def words(game, bond: str, kind: str, rng: RNG, **values) -> str:
    """One of a bond's lines ({name} and the pronouns of whoever it is about)."""
    lines = spec(game, bond).get("lines", {}).get(kind) or [""]
    return textgen.fill(rng.choice(lines), rng, {}, {k: str(v) for k, v in values.items()})


def voice(game, bond: str, kind: str, c_or_npc, rng: RNG, **values) -> str:
    return words(game, bond, kind, rng, name=c_or_npc.name.split()[0], leader=game.leader.name.split()[0],
                 **textgen.pronoun_values(c_or_npc.sex), **values)


def refit(game, char: Character, kit: list) -> None:
    """Take away the kit a class would bring, and give them only what someone like this owns."""
    from realmwalker.rules.inventory import add_item, equip_everything_sensible, fill_containers

    items = game.tables.items
    char.inventory, char.equipped, char.next_uid = [], {}, 1
    for def_id, qty in items.starting_packs.get("everyone", []) + [["common_clothes", 1], ["boots", 1]] + list(kit):
        if def_id in items:
            add_item(char, items, def_id, int(qty), made_at=game.world.time)
    equip_everything_sensible(char, items)
    fill_containers(char, items, "clean")


def spot_in(game, lm, kinds=("inn",)) -> tuple[int, tuple[int, int]] | None:
    """A free floor cell inside one of these buildings (or any building): (building index, (x, y))."""
    from realmwalker.game.people import npcs_in

    s = game.world.settlement_at(game.player.x, game.player.y) if lm.kind == "settlement" else None
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    taken = {(n.x, n.y) for n in npcs_in(game.world, s.id)} if s is not None else set()
    rng = game.world.rng.child(f"spot/{lm.key}/{game.world.time}")
    order = [i for i, b in enumerate(lm.buildings) if b.kind in kinds] or list(range(len(lm.buildings)))
    for bi in order:
        b = lm.buildings[bi]
        cells = [(int(x), int(y)) for x in range(b.x + 1, b.x + b.w - 1) for y in range(b.y + 1, b.y + b.h - 1)
                 if walk[x, y] and (x, y) not in taken and (x, y) != tuple(b.door)]
        if cells:
            return bi, rng.choice(cells)
    return None


def problem_with(game, npc) -> str | None:
    if not comp.room(game):
        return f"you already have {comp.data(game)['max_companions']} companions"
    if npc.mood() in ("hostile", "unfriendly"):
        return "they don't like you enough"
    return None


# ---------------------------------------------------------------------------- sworn swords
def lender_of(game, npc):
    """The realm this ruler speaks for, if it is one that might lend you a sword."""
    w = game.world
    fig = w.figures.get(npc.flags.get("figure", -1))
    if fig is None or fig.role != "ruler" or fig.faction not in w.factions or not fig.alive:
        return None
    f = w.factions[fig.faction]
    return f if f.active and f.kind in LENDING_KINDS and f.kind in spec(game, "sworn").get("titles", {}) else None


def sworn_problem(game, f) -> str | None:
    from realmwalker.game.reputation import standing
    from realmwalker.world import factions as fx

    if not comp.room(game):
        return f"you already have {comp.data(game)['max_companions']} companions"
    if any(c.companion.get("lender") == f.id for c in following(game, "sworn")):
        return "one of theirs already rides with you"
    lost = game.renown.flags.get("sworn_lost", {}).get(str(f.id))
    if lost is not None and game.moment.total_days - int(lost) < LOST_DAYS:
        return "the last one they lent you came home dead"
    realm = fx.top_liege(game.world, f)
    if game.renown.bounties.get(f.id) or (realm is not None and game.renown.bounties.get(realm.id)):
        return "there is a price on your head here"
    if standing(game, f.id) < SWORN_STANDING:
        return "they would have to honour you first"
    return None


def lend(game, npc, f) -> list[str]:
    """The ruler gives you one of their own."""
    from realmwalker.game.people import add, make_npc, town_of

    w = game.world
    s = w.settlements[npc.settlement]
    rng = w.rng.child(f"sworn/{f.id}/{game.moment.total_days}")
    lm = game.local
    where = spot_in(game, lm, ("keep", "hall")) if lm is not None and lm.kind == "settlement" else None
    bi, cell = where if where is not None else (npc.building, (npc.x, npc.y))
    knight = make_npc(game, s, "guard", rng.child("who"), building=bi, post=cell, home=cell)
    title = spec(game, "sworn")["titles"][f.kind]
    knight.title = title
    knight.flags["sworn"] = f.id
    knight.met = knight.known = True
    add(w, town_of(w, s.id), knight)
    background = "noble" if f.kind in ("kingdom", "noble_house") else "soldier"
    char = comp.build(game, knight, "fighter", background, max(2, game.leader.level), rng.child("build"),
                      spec(game, "sworn").get("story", [""]))
    said = voice(game, "sworn", "lent", knight, rng, ruler=npc.first_name, lender=f.name)
    notes = comp.enlist(game, knight, char, "sworn", lender=f.id, title=title)
    return [said] + notes


def recall_check(game) -> None:
    """Swords lent by a realm that no longer thinks well of you (or no longer is) go home."""
    from realmwalker.game.reputation import standing

    w = game.world
    rng = w.rng.child(f"recall/{game.moment.total_days}")
    for c in following(game, "sworn"):
        f = w.factions.get(c.companion.get("lender", -1))
        if f is None or not f.active:
            name = f.name if f is not None else "the realm that sent them"
            c.companion.update(bond="refugee", home_name=name, ruin="is no more")
            game.say(f"<warn>{voice(game, 'sworn', 'orphaned', c, rng, lender=name)}</>", "warn")
            continue
        if standing(game, f.id) < RECALL_BELOW or sworn_problem(game, f) == "there is a price on your head here":
            text = voice(game, "sworn", "recalled", c, rng, lender=f.name)
            comp.dismiss(game, c)
            game.say(f"<warn>{text}</>", "warn")


# ---------------------------------------------------------------------------- dreamers
def dreamer(game, npc) -> bool:
    """A farm lad, a serving girl, a drunk: somebody who might be talked into it by the promise of money."""
    s = spec(game, "dreamer")
    return (npc.job in s.get("jobs", []) and npc.alive and not npc.notable
            and (npc.age <= 24 or "trusting" in npc.traits or npc.job == "beggar"))


def work_to_tell(game) -> dict | None:
    """The best-paid work in hand (a companion's own business does not count: it is theirs)."""
    from realmwalker.game import quests

    live = [q for q in quests.active(game) if q.get("personal") is None and int(q.get("reward", 0)) >= 50]
    return max(live, key=lambda q: q["reward"]) if live else None


def asked_today(game, npc, key: str = "asked_day") -> bool:
    return npc.flags.get(key) == game.moment.total_days


def dreamer_choices(conv) -> list:
    from realmwalker.game.dialogue import Choice

    game, npc = conv.game, conv.npc
    problem = problem_with(game, npc) or ("you have asked them once today" if asked_today(game, npc) else None)
    q = work_to_tell(game)
    if q is None:
        return [Choice("recruit", "[Persuasion] Tell them about your work...", False,
                       "you have taken on no paying work to tell them of", {"how": "dream"})]
    cut = int(float(spec(game, "dreamer").get("share", 0.2)) * 100)
    return [Choice("recruit", f"[Persuasion] Tell them about your work: {cut}% of what it pays.", problem is None,
                   problem or "", {"how": "dream", "q": q["id"]}),
            Choice("recruit", "[Deception] Tell them it will make you both rich.", problem is None, problem or "",
                   {"how": "dream", "q": q["id"], "lie": True})]


def tell_of_work(conv, qid, lie: bool) -> None:
    from realmwalker.game import quests
    from realmwalker.game.people import change_disposition

    game, npc = conv.game, conv.npc
    q = quests.by_id(game, qid)
    if q is None:
        return
    npc.flags["asked_day"] = game.moment.total_days
    rng = conv.rng
    reward = money_text(q["reward"])
    if lie:
        conv.you_say(f"[Deception] You tell {npc.first_name} about {quests.title(game, q)}, and what it will make of "
                     f"you both: riches.")
    else:
        conv.you_say(f"[Persuasion] You tell {npc.first_name} about {quests.title(game, q)}: {reward}, and a fair share "
                     f"of it for whoever comes along.")
    ok, roll = conv.check("deception" if lie else "persuasion", LIE_DC if lie else DREAM_DC)
    conv.note(roll)
    if not ok:
        change_disposition(npc, -10 if lie else -3)
        conv.npc_says(voice(game, "dreamer", "seen_through" if lie else "refused", npc, rng))
        return
    s = spec(game, "dreamer")
    cls, background = JOB_CLASS.get(npc.job, (rng.choice(s.get("classes", ["fighter"])), s.get("background", "folk_hero")))
    cls = cls if cls in s.get("classes", [cls]) else "fighter"
    char = comp.build(game, npc, cls, background, 1, rng.child("build"), s.get("story", [""]))
    for a in char.abilities:  # no soldier: softer hands, a slower eye, and (sometimes) a thick head
        char.abilities[a] = max(8, char.abilities[a] - 1)
    char.max_hp = char.hp = max(4, char.max_hp - 2)
    refit(game, char, s.get("kit", {}).get(cls, []))
    conv.npc_says(voice(game, "dreamer", "fooled" if lie else "told", npc, rng))
    for text in comp.enlist(game, npc, char, "dreamer", work=q["id"], cut=float(s.get("share", 0.2)), lied=lie,
                            idle=0):
        conv.note(text)
    conv.ended = True


def on_reward(game, q, money: int) -> tuple[int, list[str]]:
    """Dreamers take their share of what the work pays. Returns (what is left for you, what was said)."""
    kept, notes = money, []
    rng = game.world.rng.child(f"shares/{q['id']}")
    for c in [c for c in game.party[1:] if c.alive and comp.bond_of(c) == "dreamer"]:
        k = c.companion
        cut = int(money * float(k.get("cut", 0.2)))
        if cut <= 0:
            continue
        kept -= cut
        k["paid"] = int(k.get("paid", 0)) + cut
        k["idle"] = 0
        first = comp.first(c)
        if k.get("lied") and not k.get("lie_out"):
            k["lie_out"] = True
            if money < RICH:
                comp.change_loyalty(c, -25)
                notes.append(f"<warn>{first} takes {money_text(cut)}.</> {voice(game, 'dreamer', 'cheated', c, rng)}")
                continue
        comp.change_loyalty(c, 8)
        their = textgen.pronoun_values(c.sex)["their"]
        notes.append(f"<good>{first} takes {their} share: {money_text(cut)}.</> {voice(game, 'dreamer', 'share', c, rng)}")
    return max(0, kept), notes


def on_fail(game, q) -> None:
    """Work that fails or is given up: those who came for a share of it lose heart; Durgin keeps his oaths."""
    for c in [c for c in game.party[1:] if c.alive and comp.bond_of(c) == "dreamer"]:
        comp.change_loyalty(c, -15 if c.companion.get("work") == q["id"] else -5)
    if q.get("unique"):
        from realmwalker.game import uniques

        uniques.on_fail(game, q)


def dreamers_daily(game) -> None:
    rng = game.world.rng.child(f"dreamers/{game.moment.total_days}")
    working = work_to_tell(game) is not None
    for c in following(game, "dreamer"):
        k = c.companion
        k["idle"] = 0 if working else int(k.get("idle", 0)) + 1
        if k["idle"] > IDLE_DAYS:
            comp.change_loyalty(c, -3)
            if c in game.party and rng.chance(0.3):
                game.say(f"<warn>{voice(game, 'dreamer', 'idle', c, rng)}</>", "warn")


# ---------------------------------------------------------------------------- the restless
def restless(game, npc) -> bool:
    """Someone who would leave, if somebody asked the right way."""
    s = spec(game, "restless")
    if npc.job not in s.get("jobs", []) or not 16 <= npc.age <= 45 or not npc.alive or npc.flags.get("figure"):
        return False
    want = npc.profile.get("want", "")
    return bool({"brave", "proud", "bitter"} & set(npc.traits)) or "leave" in want or "respected" in want


def restless_choice(conv) -> list:
    from realmwalker.game.dialogue import Choice

    game, npc = conv.game, conv.npc
    asked = npc.flags.get("restless_day")
    problem = problem_with(game, npc) or ("give them time to think about it" if asked is not None and
                                          game.moment.total_days - int(asked) < 7 else None)
    return [Choice("recruit", "[Persuasion] There's more to the world than this. Come with me.",
                   problem is None, problem or "", {"how": "restless"})]


def persuade(conv) -> None:
    from realmwalker.game.people import change_disposition

    game, npc = conv.game, conv.npc
    rng = conv.rng
    npc.flags["restless_day"] = game.moment.total_days
    conv.you_say(f"[Persuasion] There is more to the world than {conv.settlement.name}. Come with me.")
    ok, roll = conv.check("persuasion", RESTLESS_DC)
    conv.note(roll)
    if not ok:
        change_disposition(npc, -3)
        conv.npc_says(voice(game, "restless", "refused", npc, rng))
        return
    s = spec(game, "restless")
    cls, background = JOB_CLASS.get(npc.job, ("fighter", "folk_hero"))
    char = comp.build(game, npc, cls, background, max(1, game.leader.level - 1), rng.child("build"))
    values = list(dict.fromkeys(TRAIT_VALUES[t] for t in npc.traits if t in TRAIT_VALUES))[:2] or s.get("values", ["brave"])
    conv.npc_says(voice(game, "restless", "persuaded", npc, rng))
    for text in comp.enlist(game, npc, char, "restless", values=values):
        conv.note(text)
    conv.ended = True


# ---------------------------------------------------------------------------- the homeless and the admirers
def ruined_near(game, settlement) -> list[tuple[object, str]]:
    """Places near here that were burned, sacked or raided lately, and how to say what happened to them."""
    w = game.world
    today = game.moment.total_days
    out = []
    for s in w.settlements:
        if s.id == settlement.id or abs(s.x - settlement.x) + abs(s.y - settlement.y) > RUIN_REACH:
            continue
        st = s.status
        raided = st.get("raided") if isinstance(st.get("raided"), dict) else None
        if st.get("burned") is not None and today - float(st["burned"]) <= 365:
            out.append((s, "was burned"))
        elif st.get("sacked") is not None and today - float(st["sacked"]) <= 120:
            out.append((s, "was sacked"))
        elif raided is not None:
            tribe = w.factions.get(raided.get("by", -1))
            out.append((s, f"was raided by {tribe.name}" if tribe is not None else "was raided"))
    return out


def arrive_town(game, lm, settlement) -> None:
    """The homeless of places nearby, and (for somebody whose name is known) an admirer, at the inns. A new lot
    about once a month, like the travellers looking for work."""
    from realmwalker.game.people import TRAVELLER_DAYS, add, make_npc, npcs_in, update_positions

    from realmwalker.game import uniques

    w = game.world
    town = w.towns.get(settlement.id)
    if town is None or not town.npcs or lm.kind != "settlement":
        return
    uniques.arrive_town(game, lm, settlement)  # whoever of the seven lives here, and what they remember of it
    day = game.moment.total_days
    if day - int(town.flags.get("followers_day", -10**6)) < TRAVELLER_DAYS:
        return
    town.flags["followers_day"] = day
    rng = w.rng.child(f"followers/{settlement.id}/{day}")
    here = [n for n in npcs_in(w, settlement.id) if n.alive and n.flags.get("follower")]
    made = False
    for place, ruin in ruined_near(game, settlement)[:2]:
        if any(n.flags.get("from") == place.id for n in here):
            continue
        where = spot_in(game, lm)
        if where is None:
            break
        bi, cell = where
        npc = make_npc(game, place, "adventurer", rng.child(f"homeless/{place.id}"), building=bi, post=cell, home=cell)
        npc.settlement = settlement.id
        npc.title = f"survivor of {place.name}"
        npc.flags.update({"follower": "refugee", "from": place.id, "ruin": ruin})
        story = textgen.fill(rng.choice(spec(game, "refugee").get("story", [""])), rng, {},
                             textgen.pronoun_values(npc.sex))
        npc.profile["backstory"] = f"{place.name} {ruin}. {story}"
        npc.profile["want"] = "somewhere to belong, and someone to follow"
        add(w, town, npc)
        made = True
    r = game.renown
    if r.fame >= ADMIRER_FAME and r.fame > r.infamy and not any(n.flags.get("follower") == "admirer" for n in here) \
            and rng.chance(min(0.8, r.fame / 40)):
        where = spot_in(game, lm)
        if where is not None:
            bi, cell = where
            npc = make_npc(game, settlement, "adventurer", rng.child("admirer"), building=bi, post=cell, home=cell)
            npc.title = "young hopeful"
            npc.age = min(npc.age, 17 + rng.randint(0, 9))
            npc.flags["follower"] = "admirer"
            npc.disposition = max(npc.disposition, 40)
            story = textgen.fill(rng.choice(spec(game, "admirer").get("story", [""])), rng, {},
                                 textgen.pronoun_values(npc.sex))
            npc.profile["backstory"] = f"Has heard of {game.leader.name}. {story}"
            npc.profile["want"] = f"to ride with {game.leader.name}"
            add(w, town, npc)
            made = True
    if made:
        update_positions(game, lm)


def take_in(conv, kind: str) -> None:
    """The homeless and the admirers need no persuading."""
    game, npc = conv.game, conv.npc
    rng = conv.rng
    conv.you_say("Would you travel with me?")
    s = spec(game, kind)
    char = comp.build(game, npc, rng.choice(s.get("classes", ["fighter"])), s.get("background", "folk_hero"),
                      max(1, game.leader.level - 1), rng.child("build"), s.get("story", [""]))
    conv.npc_says(voice(game, kind, "joined", npc, rng))
    facts = {}
    if kind == "refugee":
        place = game.world.settlements[npc.flags["from"]] if 0 <= npc.flags.get("from", -1) < len(
            game.world.settlements) else None
        facts = {"home_name": place.name if place is not None else "home", "ruin": npc.flags.get("ruin", "was lost")}
    for text in comp.enlist(game, npc, char, kind, **facts):
        conv.note(text)
    conv.ended = True


def admirers_daily(game) -> None:
    r = game.renown
    if r.infamy <= r.fame:
        return
    rng = game.world.rng.child(f"admirers/{game.moment.total_days}")
    for c in following(game, "admirer"):
        comp.change_loyalty(c, -4)
        if c in game.party and rng.chance(0.3):
            game.say(f"<warn>{voice(game, 'admirer', 'disillusioned', c, rng)}</>", "warn")


# ---------------------------------------------------------------------------- in conversation
def talk_choices(conv) -> list:
    """Ways to ask someone who is not looking for work to come with you anyway."""
    from realmwalker.game.dialogue import Choice

    game, npc = conv.game, conv.npc
    if npc.flags.get("unique"):
        from realmwalker.game import uniques

        return uniques.talk_choices(conv)
    if not npc.alive:
        return []
    kind = npc.flags.get("follower")
    if kind in ("refugee", "admirer"):
        problem = problem_with(game, npc)
        label = "Would you travel with me? (For your keep.)" if kind == "refugee" else "Would you travel with me?"
        return [Choice("recruit", label, problem is None, problem or "", {"how": kind})]
    from realmwalker.game import uniques

    out = uniques.reckoning_choices(conv)  # Grusha's village has something to say to her
    f = lender_of(game, npc)
    if f is not None:
        problem = sworn_problem(game, f)
        out.append(Choice("recruit", "Ask for one of their own to ride with you.",
                          problem is None, problem or "", {"how": "sworn", "faction": f.id}))
    if dreamer(game, npc):
        out += dreamer_choices(conv)
    if restless(game, npc):
        out += restless_choice(conv)
    return out


def talk_choose(conv, choice) -> None:
    how = choice.data.get("how")
    game = conv.game
    if how == "sworn":
        f = game.world.factions[choice.data["faction"]]
        conv.you_say(f"I have served {f.name} well. Will you lend me one of your own?")
        problem = sworn_problem(game, f)
        if problem:
            conv.npc_says(f"\"No.\" <dim>({problem})</>")
            return
        for text in lend(game, conv.npc, f):
            conv.note(text)
    elif how == "dream":
        tell_of_work(conv, choice.data.get("q"), bool(choice.data.get("lie")))
    elif how == "restless":
        persuade(conv)
    elif how in ("refugee", "admirer"):
        take_in(conv, how)
    elif how == "unique":
        from realmwalker.game import uniques

        uniques.talk_choose(conv, choice)


# ---------------------------------------------------------------------------- the days go by
def daily(game) -> None:
    recall_check(game)
    dreamers_daily(game)
    admirers_daily(game)
    from realmwalker.game import uniques

    uniques.daily(game)


def died(game, c: Character) -> None:
    """A realm's lent sword dies with you: it will remember. Someone like no one else dies: the world will."""
    from realmwalker.game import reputation

    if not c.companion:
        return
    bond = comp.bond_of(c)
    if bond == "sworn":
        f = game.world.factions.get(c.companion.get("lender", -1))
        if f is not None:
            game.renown.flags.setdefault("sworn_lost", {})[str(f.id)] = game.moment.total_days
            reputation.change_standing(game, f.id, -5)
    elif bond == "unique":
        from realmwalker.game import uniques

        uniques.died(game, c)
