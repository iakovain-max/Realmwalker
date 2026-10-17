"""Companions (M7): people who travel with you. Up to four at a time.

They are found at inns (travellers looking for work) and among the sell-swords of a mercenary company's town.
Each has a class and level, values (what they like and hate you doing) and a want (pay, a share of the loot, a
cause, knowledge, revenge). They are full characters, with needs, wounds and diseases like yours, and they can
die. In a fight you command each of them.

Loyalty (0 to 100) rises and falls with what you do (`react`, called with a tag when you do something), with
pay, and with time. Low loyalty brings grumbling, then desertion in the night (with some of your coin); high
loyalty brings devotion. Outside a fight they take simple orders: follow, wait here, keep watch at camp, forage.

They carry no purse of their own (after v1): what you pay them, wages or a share of the loot, is theirs and gone
(counted in `paid`), and only your money is ever spent.
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.rng import RNG
from realmwalker.rules.character import Character
from realmwalker.rules.items import money_text

ORDERS = {"follow": "Follow me", "wait": "Wait here", "watch": "Keep watch when we camp",
          "forage": "Forage when we camp"}
LOYALTY_WORDS = [(80, "devoted", "good"), (55, "loyal", "good"), (30, "content", "dim"), (12, "unhappy", "warn"),
                 (-1, "mutinous", "danger")]
WANT_LIKES = {"revenge": ("outlaws_beaten",), "knowledge": ("discovery", "scroll", "ruins"),
              "cause": ("help_poor", "mercy", "cult_hunted"), "loot": ("loot",), "pay": ("paid",)}
CRIME_TAGS = {"theft": "theft", "pickpocket": "theft", "trespass": "theft", "assault": "assault", "murder": "murder",
              "forbidden_magic": "forbidden_magic", "unlicensed_magic": "forbidden_magic", "heresy": "heresy",
              "jailbreak": "jailbreak", "smuggling": "smuggling", "resisting_arrest": "assault"}


def data(game) -> dict:
    return game.tables.companions


def companions(game) -> list[Character]:
    return [c for c in game.party if c.companion]


def waiting(game) -> list[Character]:
    return list(getattr(game, "waiting", []))


def first(c: Character) -> str:
    return c.name.split()[0]


def loyalty_word(value: float) -> tuple[str, str]:
    for limit, word, color in LOYALTY_WORDS:
        if value >= limit:
            return word, color
    return "mutinous", "danger"


def wage_for(game, level: int) -> int:
    w = data(game)["wage"]
    return int(w["base"] + w["per_level"] * max(0, level - 1))


def line(game, kind: str, c: Character, rng: RNG | None = None, value: str | None = None) -> str:
    """Something a companion says. Now and then it is in the voice of what they care about ("road_devout",
    "disapprove_mercenary"), and always with the right pronouns for them."""
    rng = rng or game.world.rng.child(f"bark/{kind}/{c.name}/{game.world.time}")
    lines = data(game)["lines"]
    pool = lines[kind]
    if c.companion.get("unique"):
        from realmwalker.game import uniques

        own = uniques.lines(game, c).get(kind)
        if own:  # someone like no one else speaks for themselves
            return textgen.fill(rng.choice(own), rng, {}, {"name": first(c), "leader": first(game.leader)})
    if value is not None and f"{kind}_{value}" in lines and rng.chance(0.7):
        pool = lines[f"{kind}_{value}"]  # the thing they care about is what they are reacting to
    else:
        own = [lines[f"{kind}_{v}"] for v in c.companion.get("values", []) if f"{kind}_{v}" in lines]
        if own and rng.chance(0.4):
            pool = rng.choice(own)
    values = {"name": first(c), "leader": first(game.leader), **textgen.pronoun_values(c.sex)}
    return textgen.fill(rng.choice(pool), rng, {}, values)


def say(game, kind: str, c: Character, color: str = "info") -> None:
    """A companion speaks (or is described) in the log."""
    from realmwalker.core.textgen import escape_markup

    text = line(game, kind, c)
    game.say(f"<name>{escape_markup(first(c))}:</> {escape_markup(text)}" if text.startswith('"')
             else escape_markup(text), color)


# ---------------------------------------------------------------------------- finding and hiring
def archetype_of(npc) -> str | None:
    return npc.flags.get("recruit")


def terms(game, npc) -> dict:
    """What they ask for: a daily wage (and a share of the loot, for those who want loot), some of it up front."""
    arch = data(game)["archetypes"][archetype_of(npc)]
    level = max(1, game.leader.level - (1 if npc.id % 3 == 0 else 0))
    wage = wage_for(game, level)
    share = 0.0
    if arch["want"] == "loot":
        share = float(data(game)["share"])
        wage //= 2
    upfront = wage * int(data(game)["wage"]["upfront_days"])
    if npc.flags.get("company") is not None:
        upfront *= 2  # the company takes its cut
    if npc.flags.get("grateful"):
        wage, upfront, share = 0, 0, 0.0  # they owe you their life: no coin, only their keep
    return {"level": level, "wage": wage, "share": share, "upfront": upfront, "archetype": archetype_of(npc)}


def room(game) -> bool:
    return len(companions(game)) + len(waiting(game)) < int(data(game)["max_companions"])


def recruit_problem(game, npc) -> str | None:
    if archetype_of(npc) is None:
        return "they are not looking for work on the road"
    if not room(game):
        return f"you already have {data(game)['max_companions']} companions"
    if npc.mood() in ("hostile", "unfriendly"):
        return "they don't like you enough"
    t = terms(game, npc)
    if sum(c.money for c in game.party) < t["upfront"]:
        return f"they want {money_text(t['upfront'])} up front"
    return None


def terms_text(game, npc) -> str:
    t = terms(game, npc)
    if not t["wage"] and not t["share"]:
        return "no wage: only their keep"
    share = f" and {int(t['share'] * 100)}% of any coin we take" if t["share"] else ""
    return f"{money_text(t['wage'])} a day{share}; {money_text(t['upfront'])} now"


def hire(game, npc) -> list[str]:
    problem = recruit_problem(game, npc)
    if problem:
        return [f"They won't come: {problem}."]
    from realmwalker.game.law import take_money

    t = terms(game, npc)
    take_money(game, t["upfront"])
    char = make_character(game, npc, t)
    game.party.append(char)
    from realmwalker.game import pack

    pack.sync(game)  # what they bring goes in the party's pack
    npc.present = False
    npc.flags["companion"] = True
    npc.remember(f"joined the traveller on {game.moment.date_text()}")
    game.dirty = True
    msgs = [f"<good>{first(char)} joins you</>: a level {char.level} "
            f"{game.tables.classes[char.cls]['name'].lower()}, {data(game)['archetypes'][t['archetype']]['name']}. "
            f"<dim>({terms_text_for(game, char) if char.companion['wage'] else 'no wage: only their keep'})</>"]
    msgs.append(f"<name>{first(char)}:</> {line(game, 'hired', char)}")
    return msgs


def terms_text_for(game, c: Character) -> str:
    comp = c.companion
    share = f", {int(comp.get('share', 0) * 100)}% of the loot" if comp.get("share") else ""
    return f"{money_text(comp['wage'])} a day{share}"


def pay_word(game, c: Character) -> str:
    """A few words for the side panel, in place of a purse: what they are paid, or what they came for."""
    comp = c.companion
    if comp.get("wage"):
        return f"{money_text(comp['wage'])} a day"
    if comp.get("share"):
        return f"{int(comp['share'] * 100)}% of the loot"
    if bond_of(c) == "unique":
        from realmwalker.game import uniques

        return uniques.pay_word(game, c)
    return bonds(game).get(bond_of(c), {}).get("label", "no wage")


def build(game, npc, cls: str, background: str, level: int, rng: RNG, story: list[str] = ("",)) -> Character:
    """The townsperson as a full character of a class, at a level."""
    from realmwalker.rules import progression
    from realmwalker.rules.creation import CharacterBuilder

    tables = game.tables
    b = CharacterBuilder(tables, rng)
    race = npc.race if npc.race in tables.races else "human"
    b.set_race(race)
    if npc.culture in tables.races[race]["cultures"]:
        b.set_culture(npc.culture)
    b.set_class(cls)
    b.set_background(background if background in tables.backgrounds else "soldier")
    b.sex = npc.sex if npc.sex in ("male", "female") else b.sex
    b.name = npc.name
    b.age = npc.age
    from realmwalker.rules import looks

    b.looks = looks.of_npc(tables, npc)  # the face they had in town
    b.appearance = npc.profile.get("appearance") or looks.describe(tables, b.looks, b.race, b.sex)
    b.backstory = npc.profile.get("backstory") or textgen.fill(rng.choice(list(story)), rng, {},
                                                               textgen.pronoun_values(b.sex))
    char = b.build(game.world.time)
    if level > 1:
        xp = tables.rules["xp_for_level"][min(level, len(tables.rules["xp_for_level"])) - 1]
        progression.award_xp(char, xp, tables, rng, auto=True)
    progression.auto_resolve(char, tables)  # (a level-1 choice too: a cleric's Divine Order)
    return char


def make_character(game, npc, t: dict) -> Character:
    """The townsperson as a full character of their class, at about the party's level."""
    arch = data(game)["archetypes"][t["archetype"]]
    rng = game.world.rng.child(f"companion/{npc.id}")
    char = build(game, npc, rng.choice(arch["classes"]), arch["background"], t["level"], rng, arch.get("story", [""]))
    char.money = 0  # what you pay them is theirs, and gone: only your purse is ever spent
    char.companion = {
        "npc": npc.id, "archetype": t["archetype"], "values": list(arch["values"]), "want": arch["want"],
        "loyalty": float(data(game)["loyalty"]["start"]) + (20.0 if npc.flags.get("grateful") else 0.0),
        "wage": t["wage"], "share": t["share"],
        "hired": game.world.time, "order": "follow", "home": npc.settlement, "unpaid": 0,
    }
    char.companion["bond"] = "grateful" if npc.flags.get("grateful") else "hired"
    return char


# ---------------------------------------------------------------------------- why they follow you
def bonds(game) -> dict:
    return data(game)["bonds"]


def bond_of(c: Character) -> str:
    return c.companion.get("bond") or "hired"


def enlist(game, npc, char: Character, bond: str, **facts) -> list[str]:
    """Someone who comes with you for reasons of their own: no wage, nothing up front (game/followers.py)."""
    spec = bonds(game).get(bond, {})
    char.money = 0
    char.companion = {
        "npc": npc.id, "archetype": "", "values": list(facts.pop("values", spec.get("values", ["brave"]))),
        "want": facts.pop("want", spec.get("want", "cause")),
        "loyalty": float(facts.pop("loyalty", spec.get("loyalty", data(game)["loyalty"]["start"]))),
        "wage": 0, "share": 0.0, "hired": game.world.time, "order": "follow", "home": npc.settlement, "unpaid": 0,
        "bond": bond, **facts,
    }
    game.party.append(char)
    npc.present = False
    npc.flags["companion"] = True
    npc.remember(f"joined the traveller on {game.moment.date_text()}")
    game.dirty = True
    cls = game.tables.classes[char.cls]["name"].lower()
    return [f"<good>{first(char)} joins you</>: a level {char.level} {cls}. <dim>({bond_text(game, char)})</>"]


def who_they_are(game, c: Character) -> str:
    """A sell-sword, a knight of the royal household, a farmer: what to call them."""
    comp = c.companion
    if comp.get("title"):
        return comp["title"]
    arch = data(game)["archetypes"].get(comp.get("archetype"))
    if arch:
        return arch["name"]
    npc = game.world.npcs.get(comp.get("npc", -1))
    return npc.title if npc is not None else "companion"


def bond_text(game, c: Character) -> str:
    """Why they are with you, in a sentence (the party screen)."""
    comp = c.companion
    bond = bond_of(c)
    if bond == "hired":
        return f"Hired, for {terms_text_for(game, c)}."
    if bond == "unique":
        from realmwalker.game import uniques

        return uniques.bond_text(game, c)
    w = game.world
    lender = w.factions.get(comp.get("lender", -1))
    values = {"lender": lender.name if lender is not None else "a lord who is no more",
              "home": comp.get("home_name", "home"), "ruin": comp.get("ruin", "was lost"),
              "share": f"{int(float(comp.get('cut', 0)) * 100)}%", **textgen.pronoun_values(c.sex)}
    return textgen.fill(bonds(game)[bond]["text"], game.world.rng.child("bond"), {}, values)


def dismiss(game, c: Character, *, deserted: bool = False) -> list[str]:
    """They leave the party and go home (where you may find them again)."""
    if c in game.party:
        game.party.remove(c)
    if c in getattr(game, "waiting", []):
        game.waiting.remove(c)
    from realmwalker.game import pack, servants

    servants.dismissed(game, c)  # (a spirit, a bound creature or the dead they kept go with them)

    pack.sync(game)  # they go with what they wear and wield
    npc = game.world.npcs.get(c.companion.get("npc", -1))
    if npc is not None:
        npc.flags.pop("companion", None)
        npc.present = True
        npc.remember("travelled with the traveller for a time" + (" and left them" if deserted else ""))
        if deserted:
            npc.disposition = min(npc.disposition, -30)
    game.dirty = True
    if c.companion.get("unique"):
        from realmwalker.game import uniques

        uniques.left(game, c)  # home again, as they are, to be found there
    return [line(game, "desert" if deserted else "leave", c)]


def released(game, c: Character, npc) -> None:
    """Their leader is dead and they go home. Sell-swords can be hired again by whoever comes next; the others go
    back to being who they were."""
    arch = c.companion.get("archetype") if c.companion else None
    if arch in data(game)["archetypes"]:
        npc.flags["recruit"] = arch
    else:
        npc.flags.pop("recruit", None)
    if c.companion.get("unique"):
        from realmwalker.game import uniques

        uniques.left(game, c)


# ---------------------------------------------------------------------------- loyalty
def change_loyalty(c: Character, amount: float) -> None:
    comp = c.companion
    comp["loyalty"] = max(0.0, min(100.0, float(comp.get("loyalty", 50)) + amount))


def react(game, *tags: str, quiet: bool = False) -> list[str]:
    """The party sees what you did. Each companion likes or hates it according to their values."""
    if not tags:
        return []
    spec = data(game)
    likes, hates = float(spec["reactions"]["likes"]), float(spec["reactions"]["hates"])
    loudest, loudest_delta, why = None, 0.0, None
    for c in companions(game):
        delta = 0.0
        strongest, strongest_delta = None, 0.0  # the value of theirs that this touched most
        for v in c.companion.get("values", []):
            val = spec["values"].get(v, {})
            moved = likes * sum(1 for t in tags if t in val.get("likes", []))
            moved += hates * sum(1 for t in tags if t in val.get("hates", []))
            delta += moved
            if abs(moved) > abs(strongest_delta):
                strongest, strongest_delta = v, moved
        delta += likes * sum(1 for t in tags if t in WANT_LIKES.get(c.companion.get("want", ""), ()))
        if c.companion.get("unique"):
            from realmwalker.game import uniques

            delta += uniques.feelings(game, c, tags)  # what one of the seven cares about beyond their values
        if delta:
            change_loyalty(c, delta)
            if abs(delta) > abs(loudest_delta):
                loudest, loudest_delta, why = c, delta, strongest
    if loudest is None or quiet:
        return []
    kind = "approve" if loudest_delta > 0 else "disapprove"
    color = "good" if loudest_delta > 0 else "warn"
    text = line(game, kind, loudest, value=why)
    word = "approves" if loudest_delta > 0 else "disapproves"
    msg = f"<{color}>{first(loudest)} {word}.</> " + (text if not text.startswith('"') else text)
    game.say(msg, color)
    return [msg]


def road_talk(game) -> None:
    """Somebody says something on the road: about the walking, the weather, the dark, or nothing at all."""
    party = [c for c in companions(game) if c.alive]
    if not party or game.busy or not game.flavour():
        return
    steps = game.player.steps
    flags = game.renown.flags
    if steps - int(flags.get("road_talk", -10**6)) < 25:
        return
    rng = game.world.rng.child(f"road-talk/{steps}")
    if not rng.chance(0.3):
        return
    c = rng.choice(party)
    kind = "road"
    w = game.weather
    if c.fatigue >= 60 or c.exhaustion >= 1:
        kind = "road_tired"
    elif w.precip > 0.3:
        kind = "road_wet"
    elif game.light < 0.4:
        kind = "road_night"
    elif w.temp < 2 or c.body_heat <= -20:
        kind = "road_cold"
    elif w.kind == "heat" or c.body_heat >= 30:
        kind = "road_hot"
    flags["road_talk"] = steps
    if kind == "road" and rng.chance(0.3):
        from realmwalker.game import uniques

        said = uniques.banter(game, rng)  # two of the seven, talking to each other
        if said:
            game.say(textgen.escape_markup(said), "flavor")
            return
    game.say(line(game, kind, c, rng), "flavor")


def react_to_crime(game, crime: str) -> None:
    tag = CRIME_TAGS.get(crime)
    if tag:
        react(game, tag)


# ---------------------------------------------------------------------------- the days go by
def daily(game) -> None:
    """Wages, grumbling, desertion, devotion. Called once a day."""
    from realmwalker.game.law import take_money

    rng = game.world.rng.child(f"companions/{game.moment.total_days}")
    spec = data(game)
    loyal = spec["loyalty"]
    for c in list(companions(game)) + waiting(game):
        comp = c.companion
        wage = int(comp.get("wage", 0))
        if wage:
            if sum(m.money for m in game.party) >= wage:
                take_money(game, wage)
                comp["paid"] = int(comp.get("paid", 0)) + wage  # sent home, drunk, saved: theirs, not the party's
                comp["unpaid"] = 0
                if "mercenary" in comp.get("values", []) or "greedy" in comp.get("values", []):
                    change_loyalty(c, 0.5)
            else:
                comp["unpaid"] = int(comp.get("unpaid", 0)) + 1
                change_loyalty(c, -6)
                if c in game.party and rng.chance(0.6):
                    game.say(f"<warn>{first(c)} was not paid today.</> {line(game, 'unpaid', c, rng)}", "warn")
        value = comp.get("loyalty", 50)
        if value >= loyal["devoted"] and not comp.get("devoted_said"):
            comp["devoted_said"] = True
            game.say(f"<good>{line(game, 'devoted', c, rng)}</>", "good")
        elif value < loyal["desert"] and c in game.party and rng.chance(0.25):
            desert(game, c, rng)
        elif value < loyal["complain"] and c in game.party and rng.chance(0.3):
            game.say(f"<warn>{line(game, 'complain', c, rng)}</>", "warn")
    from realmwalker.game import followers

    followers.daily(game)  # those who follow you for reasons other than pay


def desert(game, c: Character, rng: RNG) -> None:
    """Gone in the night, with a share of the coin (and, if they are greedy, something more)."""
    from realmwalker.game.law import take_money

    days = 5 if "greedy" not in c.companion.get("values", []) else 12
    stolen = take_money(game, min(sum(m.money for m in game.party) // 4, wage_for(game, c.level) * days))
    for text in dismiss(game, c, deserted=True):
        game.say(f"<danger>{text}</>" + (f" ({money_text(stolen)} is missing.)" if stolen else ""), "danger")


def share_loot(game, money: int) -> int:
    """Companions who fight for a share take it. Returns what is left for you."""
    left = money
    for c in companions(game):
        share = float(c.companion.get("share", 0.0))
        if share and money > 0:
            cut = int(money * share)
            c.companion["paid"] = int(c.companion.get("paid", 0)) + cut
            left -= cut
    return max(0, left)


# ---------------------------------------------------------------------------- orders
def set_order(game, c: Character, order: str) -> str:
    if order not in ORDERS:
        return ""
    if order == "wait":
        return wait_here(game, c)
    c.companion["order"] = order
    reply = {"follow": "Right behind you.", "watch": "I'll keep watch.", "forage": "I'll see what the land gives."}
    return f"{first(c)}: \"{reply[order]}\""


def wait_here(game, c: Character) -> str:
    if c not in game.party or c is game.leader:
        return ""
    game.party.remove(c)
    c.companion["order"] = "wait"
    c.companion["wait_at"] = [game.player.x, game.player.y]
    game.waiting.append(c)
    from realmwalker.game import pack

    pack.sync(game)  # they keep what they wear and wield; the pack stays with you
    here = game.world.settlement_at(game.player.x, game.player.y)
    where = here.name if here is not None else "here"
    return f"{first(c)} will wait for you in {where}." + (" (Wages still run.)" if c.companion.get("wage") else "")


def rejoin(game) -> list[str]:
    """Companions waiting where you now stand join you again (the dead do not)."""
    out = []
    for c in list(game.waiting):
        if not c.alive:
            game.waiting.remove(c)
            died(game, c)
            out.append(f"<danger>{c.name} is dead.</>")
            continue
        if not c.companion:
            continue
        if c.companion.get("wait_at") == [game.player.x, game.player.y]:
            if game.world.time < int(c.companion.get("coming", 0)):
                continue  # sent for, and still on the road (game/passage.send_for)
            game.waiting.remove(c)
            c.companion["order"] = "follow"
            c.companion.pop("wait_at", None)
            c.companion.pop("coming", None)
            game.party.append(c)
            from realmwalker.game import pack

            pack.sync(game)
            out.append(f"<good>{first(c)} joins you again.</>")
    return out


def watching(game) -> bool:
    from realmwalker.game import uniques

    # Osric keeps watch every night, whatever you have told him.
    return any(c.companion.get("order") == "watch" and c.alive for c in companions(game)) or \
        uniques.perk(game, "vigil") is not None


def foragers(game) -> list[Character]:
    return [c for c in companions(game) if c.companion.get("order") == "forage" and c.alive]


def mood_line(game, c: Character) -> str:
    value = c.companion.get("loyalty", 50)
    kind = "mood_good" if value >= 55 else "mood_fair" if value >= 25 else "mood_bad"
    return line(game, kind, c)


def raise_wage(game, c: Character) -> str:
    comp = c.companion
    if not comp.get("wage"):
        return f"{first(c)} is not with you for a wage."
    comp["wage"] = int(comp.get("wage", 0) * 1.25) + 5
    change_loyalty(c, 10)
    return f"{first(c)} will have {money_text(comp['wage'])} a day now, and is pleased about it."


# ---------------------------------------------------------------------------- in conversation
def talk_choices(conv) -> list:
    from realmwalker.game.dialogue import Choice

    npc = conv.npc
    if npc.flags.get("companion"):
        return []
    if archetype_of(npc) is None:  # not looking for work: some may come for other reasons
        from realmwalker.game import followers

        return followers.talk_choices(conv)
    problem = recruit_problem(conv.game, npc)
    return [Choice("recruit", f"Would you travel with me? ({terms_text(conv.game, npc)})", problem is None,
                   problem or "")]


def talk_choose(conv, choice) -> None:
    if choice.data.get("how"):
        from realmwalker.game import followers

        followers.talk_choose(conv, choice)
        return
    conv.you_say("Would you travel with me?")
    for text in hire(conv.game, conv.npc):
        conv.note(text)
    if conv.npc.flags.get("companion"):
        conv.ended = True


def died(game, c: Character) -> None:
    """A companion is dead: the town they came from will hear of it (unless a clone of theirs takes the soul)."""
    from realmwalker.game import followers, greatmagic

    if greatmagic.clone_wakes(game, c):  # (Clone: they wake in its vessel and wait there)
        return

    followers.died(game, c)  # a realm that lent you its sword, the world that loses someone like no one else
    from realmwalker.game import allies

    allies.died(game, c)  # (their steed vanishes, their familiar goes)
    from realmwalker.game import servants

    servants.died(game, c)  # (the hold on their raised dead ends)
    npc = game.world.npcs.get(c.companion.get("npc", -1)) if c.companion else None
    if npc is not None:
        npc.alive = False
        npc.present = False
        npc.flags.pop("companion", None)


# ---------------------------------------------------------------------------- the grateful
GRATEFUL_ARCHETYPES = ("old_soldier", "runaway_serf", "outlaw_hunter", "wandering_priest", "sellsword")


def grateful(game, q: dict) -> list[str]:
    """Someone you broke out of a dungeon's chains, home again, waits at the inn: they will travel with you for
    their keep (half a wage, nothing up front) and start out loyal. Design section 12: companions come from
    "freed prisoners, grateful NPCs and so on"."""
    from realmwalker.game.people import add, make_npc

    w = game.world
    lm = game.local
    s = w.settlements[q["town"]]
    town = w.towns.get(s.id)
    target = q["target"]
    if town is None or lm is None or lm.kind != "settlement" or not getattr(game.tables, "companions", None):
        return []
    rng = w.rng.child(f"grateful/{q['id']}")
    inns = [i for i, b in enumerate(lm.buildings) if b.kind == "inn"] or list(range(len(lm.buildings)))
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    taken = {(n.x, n.y) for n in w.npcs.values() if n.settlement == s.id and n.alive and n.present}
    for bi in inns:
        b = lm.buildings[bi]
        cells = [(x, y) for x in range(b.x + 1, b.x + b.w - 1) for y in range(b.y + 1, b.y + b.h - 1)
                 if walk[x, y] and (x, y) not in taken]
        if cells:
            break
    else:
        return []
    spot = rng.choice(cells)
    npc = make_npc(game, s, "adventurer", rng.child("npc"), building=bi, post=spot, home=spot)
    npc.name = target.get("captive", npc.name)
    if target.get("sex") in ("male", "female"):
        npc.sex = target["sex"]
    arch = rng.choice([a for a in GRATEFUL_ARCHETYPES if a in data(game)["archetypes"]])
    site = w.sites[target["site"]].name if 0 <= target.get("site", -1) < len(w.sites) else "that place"
    npc.title = "the one you freed"
    npc.flags.update(recruit=arch, grateful=True)
    npc.met, npc.disposition = True, max(npc.disposition, 60)
    npc.profile["backstory"] = (f"You broke the chains that held them in {site}. They have not forgotten it, and "
                                f"say they never will.")
    npc.remember(f"was freed from {site} by the traveller")
    add(w, town, npc)
    first_name = npc.name.split()[0]
    return [f"<good>{first_name} is at the inn, washed and fed:</> \"If you ever want someone at your back, I'm yours. "
            f"No coin. Just keep me fed.\" <dim>(Talk to them: \"Would you travel with me?\")</>"]
