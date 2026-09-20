"""Companions (M7): people who travel with you. Up to four at a time.

They are found at inns (travellers looking for work) and among the sell-swords of a mercenary company's town.
Each has a class and level, values (what they like and hate you doing) and a want (pay, a share of the loot, a
cause, knowledge, revenge). They are full characters, with needs, wounds and diseases like yours, and they can
die. In a fight you command each of them.

Loyalty (0 to 100) rises and falls with what you do (`react`, called with a tag when you do something), with
pay, and with time. Low loyalty brings grumbling, then desertion in the night (with some of your coin); high
loyalty brings devotion. Outside a fight they take simple orders: follow, wait here, keep watch at camp, forage.
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


def line(game, kind: str, c: Character, rng: RNG | None = None) -> str:
    rng = rng or game.world.rng.child(f"bark/{kind}/{c.name}/{game.world.time}")
    text = rng.choice(data(game)["lines"][kind])
    return textgen.fill(text, rng, {}, {"name": first(c), "leader": first(game.leader)})


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
    npc.present = False
    npc.flags["companion"] = True
    npc.remember(f"joined the traveller on {game.moment.date_text()}")
    game.dirty = True
    msgs = [f"<good>{first(char)} joins you</>: a level {char.level} "
            f"{game.tables.classes[char.cls]['name'].lower()}, {data(game)['archetypes'][t['archetype']]['name']}. "
            f"<dim>({terms_text_for(game, char)})</>"]
    msgs.append(f"<name>{first(char)}:</> {line(game, 'hired', char)}")
    return msgs


def terms_text_for(game, c: Character) -> str:
    comp = c.companion
    share = f", {int(comp.get('share', 0) * 100)}% of the loot" if comp.get("share") else ""
    return f"{money_text(comp['wage'])} a day{share}"


def make_character(game, npc, t: dict) -> Character:
    """The townsperson as a full character of their class, at about the party's level."""
    from realmwalker.rules import progression
    from realmwalker.rules.creation import CharacterBuilder

    tables = game.tables
    arch = data(game)["archetypes"][t["archetype"]]
    rng = game.world.rng.child(f"companion/{npc.id}")
    b = CharacterBuilder(tables, rng)
    race = npc.race if npc.race in tables.races else "human"
    b.set_race(race)
    if npc.culture in tables.races[race]["cultures"]:
        b.set_culture(npc.culture)
    b.set_class(rng.choice(arch["classes"]))
    b.set_background(arch["background"] if arch["background"] in tables.backgrounds else "soldier")
    b.sex = npc.sex if npc.sex in ("male", "female") else b.sex
    b.name = npc.name
    b.age = npc.age
    b.appearance = npc.profile.get("appearance") or b.appearance
    b.backstory = npc.profile.get("backstory") or rng.choice(arch.get("story", [""]))
    char = b.build(game.world.time)
    if t["level"] > 1:
        xp = tables.rules["xp_for_level"][t["level"] - 1]
        progression.award_xp(char, xp, tables, rng, auto=True)
    char.money = rng.randint(0, 200)
    char.companion = {
        "npc": npc.id, "archetype": t["archetype"], "values": list(arch["values"]), "want": arch["want"],
        "loyalty": float(data(game)["loyalty"]["start"]), "wage": t["wage"], "share": t["share"],
        "hired": game.world.time, "order": "follow", "home": npc.settlement, "unpaid": 0,
    }
    return char


def dismiss(game, c: Character, *, deserted: bool = False) -> list[str]:
    """They leave the party and go home (where you may find them again)."""
    if c in game.party:
        game.party.remove(c)
    if c in getattr(game, "waiting", []):
        game.waiting.remove(c)
    npc = game.world.npcs.get(c.companion.get("npc", -1))
    if npc is not None:
        npc.flags.pop("companion", None)
        npc.present = True
        npc.remember("travelled with the traveller for a time" + (" and left them" if deserted else ""))
        if deserted:
            npc.disposition = min(npc.disposition, -30)
    game.dirty = True
    return [line(game, "desert" if deserted else "leave", c)]


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
    loudest, loudest_delta = None, 0.0
    for c in companions(game):
        delta = 0.0
        for v in c.companion.get("values", []):
            val = spec["values"].get(v, {})
            delta += likes * sum(1 for t in tags if t in val.get("likes", []))
            delta += hates * sum(1 for t in tags if t in val.get("hates", []))
        delta += likes * sum(1 for t in tags if t in WANT_LIKES.get(c.companion.get("want", ""), ()))
        if delta:
            change_loyalty(c, delta)
            if abs(delta) > abs(loudest_delta):
                loudest, loudest_delta = c, delta
    if loudest is None or quiet:
        return []
    kind = "approve" if loudest_delta > 0 else "disapprove"
    color = "good" if loudest_delta > 0 else "warn"
    text = line(game, kind, loudest)
    word = "approves" if loudest_delta > 0 else "disapproves"
    msg = f"<{color}>{first(loudest)} {word}.</> " + (text if not text.startswith('"') else text)
    game.say(msg, color)
    return [msg]


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
                c.money += wage
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


def desert(game, c: Character, rng: RNG) -> None:
    """Gone in the night, with a share of the coin (and, if they are greedy, something more)."""
    from realmwalker.game.law import take_money

    days = 5 if "greedy" not in c.companion.get("values", []) else 12
    stolen = take_money(game, min(sum(m.money for m in game.party) // 4, wage_for(game, c.level) * days))
    c.money += stolen
    for text in dismiss(game, c, deserted=True):
        game.say(f"<danger>{text}</>" + (f" ({money_text(stolen)} is missing.)" if stolen else ""), "danger")


def share_loot(game, money: int) -> int:
    """Companions who fight for a share take it. Returns what is left for you."""
    left = money
    for c in companions(game):
        share = float(c.companion.get("share", 0.0))
        if share and money > 0:
            cut = int(money * share)
            c.money += cut
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
    here = game.world.settlement_at(game.player.x, game.player.y)
    where = here.name if here is not None else "here"
    return f"{first(c)} will wait for you in {where}. (Wages still run.)"


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
            game.waiting.remove(c)
            c.companion["order"] = "follow"
            c.companion.pop("wait_at", None)
            game.party.append(c)
            out.append(f"<good>{first(c)} joins you again.</>")
    return out


def watching(game) -> bool:
    return any(c.companion.get("order") == "watch" and c.alive for c in companions(game))


def foragers(game) -> list[Character]:
    return [c for c in companions(game) if c.companion.get("order") == "forage" and c.alive]


def mood_line(game, c: Character) -> str:
    value = c.companion.get("loyalty", 50)
    kind = "mood_good" if value >= 55 else "mood_fair" if value >= 25 else "mood_bad"
    return line(game, kind, c)


def raise_wage(game, c: Character) -> str:
    comp = c.companion
    comp["wage"] = int(comp.get("wage", 0) * 1.25) + 5
    change_loyalty(c, 10)
    return f"{first(c)} will have {money_text(comp['wage'])} a day now, and is pleased about it."


# ---------------------------------------------------------------------------- in conversation
def talk_choices(conv) -> list:
    from realmwalker.game.dialogue import Choice

    npc = conv.npc
    if archetype_of(npc) is None or npc.flags.get("companion"):
        return []
    problem = recruit_problem(conv.game, npc)
    return [Choice("recruit", f"Would you travel with me? ({terms_text(conv.game, npc)})", problem is None,
                   problem or "")]


def talk_choose(conv, choice) -> None:
    conv.you_say("Would you travel with me?")
    for text in hire(conv.game, conv.npc):
        conv.note(text)
    if conv.npc.flags.get("companion"):
        conv.ended = True


def died(game, c: Character) -> None:
    """A companion is dead: the town they came from will hear of it."""
    npc = game.world.npcs.get(c.companion.get("npc", -1)) if c.companion else None
    if npc is not None:
        npc.alive = False
        npc.present = False
        npc.flags.pop("companion", None)
