"""Conversations with townsfolk: a menu from code, lines in character, and a few special options
tied to skill checks whose outcomes come from a fixed whitelist (so nobody can promise what the
game cannot deliver). The AI may write the lines and propose the special options (M5 part 2);
without it, built-in lines and options from data/dialogue.json are used.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from realmwalker.core import dice, textgen
from realmwalker.core.rng import RNG
from realmwalker.game.people import NPC, change_disposition, meet, npcs_in
from realmwalker.rules.character import Sheet
from realmwalker.rules.items import money_text

DIFFICULTY_DC = {"easy": 10, "medium": 13, "hard": 16, "very hard": 19}
MOOD_DC = {"hostile": 4, "unfriendly": 2, "neutral": 0, "friendly": -2, "warm": -3}
OUTCOMES = ("reveal_info", "reveal_hook", "disposition_up", "disposition_down", "reputation_up", "reputation_down",
            "price_down", "price_up", "give_item", "agree", "refuse", "fight", "call_guards", "flee", "unlock_topic", "none")
BRIBES = (50, 200, 1000)  # 5 silver, 2 gold, 10 gold
SKILLS_ALLOWED = {"insight", "persuasion", "deception", "intimidation", "performance", "investigation", "history",
                  "religion", "nature", "medicine", "athletics", "sleight_of_hand", "arcana", "survival", "animal_handling"}


@dataclass
class Choice:
    id: str
    label: str
    enabled: bool = True
    why: str = ""
    data: dict = field(default_factory=dict)


def plural(title: str) -> str:
    """innkeeper -> innkeepers, lady -> ladies, headman -> headmen, guildmistress -> guildmistresses,
    traveller at the inn -> travellers at the inn."""
    for joint in (" of ", " at ", " in "):
        if joint in title:
            head, _, tail = title.partition(joint)
            return plural(head) + joint + tail
    if title.endswith("man"):
        return title[:-3] + "men"
    if title.endswith(("s", "x", "ch", "sh")):
        return title + "es"
    if title.endswith("y") and title[-2:-1] not in "aeiou":
        return title[:-1] + "ies"
    return title + "s"


def story_note(npc: NPC, story: str) -> str:
    """A built-in life story is a note about them ("Took over the inn when his father..."), not their own words:
    it is told as what you learn from them."""
    from realmwalker.game.people import pronouns

    pron = pronouns(npc)
    return f"{npc.first_name}'s story, as {pron['they']} tell{pron['s']} it: {story[:1].lower() + story[1:]}"


class Conversation:
    def __init__(self, game, npc: NPC, *, defer_greeting: bool = False) -> None:
        self.game = game
        self.npc = npc
        self.lines: list[tuple[str, str]] = []  # (who, text): "npc", "you", "note"
        self.special: list[dict] = []
        self.topics: list[dict] = []  # unlocked topics: {"label", "info"}
        self.mode = "main"
        self.pending_offer: dict | None = None  # work being offered, waiting for a yes or no (game.quests)
        self.ended = False
        self.pending_ai = False
        self.minutes = 0
        self.rng = game.world.rng.child(f"talk/{npc.id}/{game.world.time}")
        self.settlement = game.world.settlements[npc.settlement]
        first = not npc.met
        meet(game, npc)
        self.first = first
        self.greeted = False
        if first:
            self.note(npc.profile.get("appearance", ""))
            npc.profile_seen = True
        if not defer_greeting:
            self.greet()
        self.special = [dict(o, used=False) for o in builtin_special(game, npc, self.rng)]

    # ------------------------------------------------------------------ helpers
    def fill(self, text: str, **extra) -> str:
        values = {"name": self.npc.first_name, "player": self.game.leader.name.split()[0], "place": self.settlement.name,
                  "job": self.npc.title, "title": self.npc.title}
        values.update({k: str(v) for k, v in extra.items()})
        return textgen.fill(text, self.rng, self.game.tables.dialogue, values)

    def npc_says(self, text: str) -> None:
        self.lines.append(("npc", text))

    def you_say(self, text: str) -> None:
        self.lines.append(("you", text))

    def note(self, text: str) -> None:
        self.lines.append(("note", text))

    def pick(self, key: str) -> str:
        return self.rng.choice(self.game.tables.dialogue[key])

    @property
    def hostile(self) -> bool:
        return self.npc.mood() == "hostile"

    # ------------------------------------------------------------------ opening
    def greet(self) -> None:
        if self.greeted:
            return
        self.greeted = True
        npc = self.npc
        if npc.flags.get("unique"):
            from realmwalker.game.uniques import greeting

            self.npc_says(greeting(self.game, npc, self.rng))  # someone like no one else says hello their own way
            return
        d = self.game.tables.dialogue
        if any("threatened" in m for m in npc.memory) and npc.disposition < 0:
            self.npc_says(self.fill(self.rng.choice(d["remember_threat"])))
        elif any("helped" in m for m in npc.memory) and npc.disposition > 15:
            self.npc_says(self.fill(self.rng.choice(d["remember_help"])))
        else:
            # People who don't mind you greet you out of their trade as often as not.
            trade = d["greeting_job"].get(npc.job) if npc.mood() in ("neutral", "friendly", "warm") else None
            lines = trade if trade and self.rng.chance(0.5) else d["greeting"][npc.mood()]
            self.npc_says(self.fill(self.rng.choice(lines)))

    # ------------------------------------------------------------------ the menu
    def menu(self) -> list[Choice]:
        npc = self.npc
        game = self.game
        if self.mode == "person":
            others = [n for n in npcs_in(game.world, npc.settlement) if n.notable and n.id != npc.id and n.alive]
            out = [Choice("person", f"{n.label()}" if n.known else f"the {n.title}", data={"other": n.id}) for n in others]
            return out + [Choice("back", "Never mind.")]
        if self.mode == "quest_offer":
            from realmwalker.game import quests

            return quests.talk_choices(self)
        if self.mode == "bribe":
            money = sum(c.money for c in game.party)
            out = [Choice("bribe", f"Offer {money_text(a)}", money >= a, "you don't have that much", {"amount": a})
                   for a in BRIBES]
            return out + [Choice("back", "Never mind.")]
        out = []
        if not self.hostile:
            out.append(Choice("who", "Who are you?" if not npc.known else "Tell me about yourself."))
            out.append(Choice("place", f"What should I know about {self.settlement.name}?"))
            out.append(Choice("rumours", "Heard any news?"))
            out.append(Choice("ask_person", "Ask about someone in town..."))
            for i, topic in enumerate(self.topics):
                if not topic.get("used"):
                    out.append(Choice("topic", topic["label"], data={"i": i}))
            for i, opt in enumerate(self.special):
                if not opt.get("used"):
                    out.append(Choice("special", opt["text"], data={"i": i}))
            out += self.role_choices()
        out.append(Choice("threaten", "[Intimidation] Threaten them."))
        out.append(Choice("offer_bribe", "Offer money..."))
        out.append(Choice("goodbye", "Goodbye."))
        return out

    def role_choices(self) -> list[Choice]:
        """Trade and services (M5), the law and the factions (M6), companions (M7) and work (M8)."""
        from realmwalker.game import companions, law_talk, quests, services

        return (quests.talk_choices(self) + companions.talk_choices(self) + services.choices(self)
                + law_talk.choices(self))

    # ------------------------------------------------------------------ doing
    def choose(self, choice: Choice) -> str | None:
        """Carry out a choice. Returns a UI request ("trade", "services"...) or None."""
        cid = choice.id
        if not choice.enabled:
            return None
        self.minutes += 1
        if cid == "back":
            self.mode = "main"
        elif cid == "who":
            self.who()
        elif cid == "place":
            self.about_place()
        elif cid == "rumours":
            self.rumours()
        elif cid == "ask_person":
            self.mode = "person"
        elif cid == "person":
            self.about_person(self.game.world.npcs[choice.data["other"]])
            self.mode = "main"
        elif cid == "topic":
            topic = self.topics[choice.data["i"]]
            topic["used"] = True
            self.you_say(topic["label"])
            self.npc_says(topic["info"])
        elif cid == "special":
            self.special_option(choice.data["i"])
        elif cid == "threaten":
            self.threaten()
        elif cid == "offer_bribe":
            self.mode = "bribe"
        elif cid == "bribe":
            self.bribe(choice.data["amount"])
            self.mode = "main"
        elif cid == "goodbye":
            self.goodbye()
        elif cid == "recruit":
            from realmwalker.game import companions

            companions.talk_choose(self, choice)
        elif cid in quests_choices():
            from realmwalker.game import quests

            quests.talk_choose(self, choice)
        elif cid in LAW_CHOICES:
            from realmwalker.game import law_talk

            return law_talk.choose(self, choice)
        else:
            from realmwalker.game import services

            return services.choose(self, choice)
        return None

    def who(self) -> None:
        npc = self.npc
        self.you_say("Who are you?" if not npc.known else "Tell me about yourself.")
        if not npc.known:
            npc.known = True
            fig = self.game.world.figures.get(npc.flags.get("figure", -1))
            if fig is not None and fig.alive and fig.role == "ruler":
                # The great do not say "I'm the king": they give you their style, and expect you to know it.
                self.npc_says(self.fill(self.pick("who_are_you_ruler"), full=f"{fig.title} {npc.name}"))
            else:
                self.npc_says(self.fill(self.pick("who_are_you")))
            self.faction_note()
            return
        mood = npc.mood()
        if mood in ("hostile", "unfriendly"):
            self.npc_says("\"That's none of your business.\"")
            return
        story = npc.profile.get("backstory", "")
        if not story:
            self.npc_says("\"Not much to tell.\"")
        else:
            self.npc_says(self.fill(self.pick("tell_about_self")))
            self.note(story if npc.profile_source == "ai" else story_note(npc, story))
        if mood in ("friendly", "warm") and npc.profile.get("want"):
            self.note(f"What {npc.first_name} wants: {npc.profile['want']}.")

    def faction_note(self) -> None:
        """Rulers and masters: which faction they lead (and the player now knows of it)."""
        from realmwalker.game.reputation import know
        from realmwalker.world import factions as fx

        w = self.game.world
        fig = w.figures.get(self.npc.flags.get("figure", -1))
        if fig is None or fig.faction not in w.factions:
            return
        f = w.factions[fig.faction]
        know(self.game, f.id)
        role = "the head" if f.kind == "noble_house" or fig.title.startswith("the ") else fig.title.lower()
        self.note(f"{self.npc.first_name} is {role} of {fx.faction_title(w, self.game.tables, f)}.")

    def about_place(self) -> None:
        from realmwalker.game.people import town_of

        s = self.settlement
        town = town_of(self.game.world, s.id)
        d = self.game.tables.dialogue
        self.you_say(f"What should I know about {s.name}?")
        others = [n for n in npcs_in(self.game.world, s.id) if n.notable and n.id != self.npc.id and n.alive]
        by_title: dict[str, list[str]] = {}
        for n in others[:6]:
            # Nobody tells a stranger which of the travellers at the inn is the cutpurse, or the runaway serf.
            title = "traveller at the inn" if n.flags.get("recruit") and not n.flags.get("company") else n.title
            by_title.setdefault(title, []).append(n.first_name)
            n.known = True
        services = "; ".join(f"the {title} is {names[0]}" if len(names) == 1 else
                             f"the {plural(title)} are {', '.join(names[:-1])} and {names[-1]}"
                             for title, names in by_title.items())
        line = self.fill(self.pick("about_place"), size_line=d["size_line"].get(s.kind, ""),
                         services_line=(services[:1].upper() + services[1:] + ".") if services else "")
        self.npc_says(line)
        self.holder_line()
        self.old_days()
        today = self.game.moment.total_days
        if town.description and town.flags.get("described_day") != today:
            town.flags["described_day"] = today  # the place is described once a day, not by everyone you ask
            self.note(town.description)

    def old_days(self) -> None:
        """What they remember of the town's past (world/ages): what they lived through, or what everyone tells."""
        if self.npc.flags.get("told_past") or self.hostile:
            return
        from realmwalker.game import past

        line = past.remembered(self.game, self.npc, self.rng)
        if line:
            self.npc.flags["told_past"] = True
            self.npc_says(line)

    def holder_line(self) -> None:
        """Who rules here, in their words."""
        from realmwalker.game.reputation import know
        from realmwalker.world import factions as fx

        w = self.game.world
        s = self.settlement
        owner = fx.owner_of(w, s)
        if owner is None:
            if w.factions:
                self.npc_says("\"No lord holds this place. We look after ourselves.\"")
            return
        know(self.game, owner.id)
        leader = fx.leader_of(w, owner)
        top = fx.top_liege(w, owner)
        who = f"{leader.full_name()}" if leader is not None and leader.alive else owner.name
        if owner.seat == s.id:
            text = f"\"{who} rules here"
        else:
            text = f"\"We answer to {owner.name}"
        if top is not None and top is not owner:
            know(self.game, top.id)
            text += f", sworn to {top.name}"
        self.npc_says(text + ".\"")

    def rumours(self) -> None:
        npc = self.npc
        game = self.game
        self.you_say("Heard any news?")
        if self.hostile:
            self.npc_says(self.fill(self.pick("refuse_talk")))
            return
        day = game.moment.total_days
        if npc.flags.get("rumour_day") == day:
            self.npc_says(self.fill(self.pick("no_rumours")))
            return
        npc.flags["rumour_day"] = day
        self.npc_says(self.fill(self.pick("rumour_intro")))
        count = 2 if "gossipy" in npc.traits or npc.job == "innkeeper" else 1
        from realmwalker.game import news

        for line in news.hear(game, count=count, rng=self.rng) if game.world.news else []:
            self.note(line)
            count -= 1
        for _ in range(count):
            self.tell_rumour()

    def tell_rumour(self) -> None:
        roll = self.rng.random()
        if roll < 0.4:
            line = danger_rumour(self.game, self.rng)
            if line:
                self.npc_says(line)
                return
        if roll < 0.8:
            from realmwalker.game.events import hear_place

            heard = hear_place(self.game, self.rng)
            if heard:
                self.note(heard)
                return
        self.npc_says(self.pick("flavour_rumours"))

    def about_person(self, other: NPC) -> None:
        self.you_say(f"What about {other.label() if other.known else 'the ' + other.title}?")
        if self.hostile:
            self.npc_says(self.fill(self.pick("refuse_talk")))
            return
        other.known = True
        line = self.pick("person_lines")
        self.npc_says(f"\"{other.first_name}? {line}\" <dim>({other.first_name} is the {other.title}.)</>")

    # ------------------------------------------------------------------ pressure and money
    def threaten(self) -> None:
        npc = self.npc
        game = self.game
        self.you_say("[Intimidation] You make it clear what could happen.")
        trait_mod = sum(int(game.tables.people["personality"][t]["threat"]) for t in npc.traits)
        dc = 12 - trait_mod + (5 if npc.job in ("guard", "lord") else 0)
        ok, roll = self.check("intimidation", dc)
        self.note(roll)
        npc.remember(f"was threatened by the traveller on {game.moment.date_text()}")
        if ok:
            change_disposition(npc, -15)
            self.npc_says(self.pick("threaten_success"))
            self.tell_rumour()
            if "nervous" in npc.traits and self.rng.chance(0.4):
                self.apply_outcome("flee", "")
        else:
            change_disposition(npc, -25)
            self.npc_says(self.fill(self.pick("threaten_failure")))
            if npc.job == "guard" or ("brave" in npc.traits and "cruel" in npc.traits):
                self.apply_outcome("fight", "")
            elif self.town_has_guards() and self.rng.chance(0.25):
                self.apply_outcome("call_guards", "")

    def bribe(self, amount: int) -> None:
        npc = self.npc
        game = self.game
        self.you_say(f"You hold out {money_text(amount)}.")
        trait_mod = sum(int(game.tables.people["personality"][t]["bribe"]) for t in npc.traits)
        wealth = max(50, npc.purse)
        appeal = amount / wealth * 100 + trait_mod + (10 if npc.social == "low" else 0)
        if appeal >= 12 and "honest" not in npc.traits or appeal >= 40:
            from realmwalker.game.events import pay

            pay(game, amount)
            npc.purse += amount
            change_disposition(npc, min(35, 8 + int(appeal / 4)))
            npc.flags.pop("rumour_day", None)
            npc.remember(f"took {money_text(amount)} from the traveller")
            self.npc_says(self.pick("bribe_accept"))
        else:
            change_disposition(npc, -8)
            self.npc_says(self.pick("bribe_refuse"))

    def goodbye(self) -> None:
        self.you_say("Goodbye.")
        if not self.hostile:
            self.npc_says(self.pick("goodbye"))
        self.ended = True

    def town_has_guards(self) -> bool:
        return any(n.job == "guard" and n.alive for n in npcs_in(self.game.world, self.npc.settlement))

    # ------------------------------------------------------------------ special options
    def check(self, skill: str, dc: int) -> tuple[bool, str]:
        c = self.game.leader
        bonus = Sheet(c, self.game.tables).skill_bonus(skill)
        roll = dice.d20(self.rng).natural
        name = self.game.tables.rules["skills"][skill]["name"]
        sign = "+" if bonus >= 0 else "-"
        ok = roll + bonus >= dc
        return ok, (f"<dice>{name}: {roll} {sign} {abs(bonus)} = {roll + bonus} vs DC {dc} — "
                    f"{'success' if ok else 'failure'}</>")

    def special_option(self, i: int) -> None:
        opt = self.special[i]
        opt["used"] = True
        skill = opt["skill"] if opt["skill"] in self.game.tables.rules["skills"] else "persuasion"
        dc = DIFFICULTY_DC.get(opt.get("difficulty", "medium"), 13) + MOOD_DC[self.npc.mood()]
        self.you_say(opt["text"])
        ok, roll = self.check(skill, dc)
        self.note(roll)
        result = opt["success"] if ok else opt["failure"]
        if result.get("line"):
            self.npc_says(result["line"])
        self.apply_outcome(result.get("outcome", "none"), result.get("topic", ""))

    def apply_outcome(self, outcome: str, topic: str) -> None:
        npc = self.npc
        game = self.game
        if outcome == "reveal_info":
            self.tell_rumour()
        elif outcome == "reveal_hook":
            from realmwalker.game.events import hear_news

            self.note(hear_news(game, self.rng))
        elif outcome == "disposition_up":
            change_disposition(npc, 15)
            npc.remember(f"was helped or pleased by the traveller on {game.moment.date_text()}")
            self.note(f"<good>{npc.first_name} warms to you.</>")
        elif outcome == "disposition_down":
            change_disposition(npc, -15)
            self.note(f"<warn>{npc.first_name} cools towards you.</>")
        elif outcome in ("reputation_up", "reputation_down"):
            change_disposition(npc, 8 if outcome == "reputation_up" else -8)
            npc.remember("will tell others about the traveller" + (" kindly" if outcome == "reputation_up" else ""))
        elif outcome in ("price_down", "price_up"):
            mod = npc.flags.get("price_mod", 0.0) + (-0.1 if outcome == "price_down" else 0.1)
            npc.flags["price_mod"] = max(-0.2, min(0.2, mod))
            self.note("<good>Their prices will be kinder to you.</>" if outcome == "price_down" else
                      "<warn>Their prices just went up, for you.</>")
        elif outcome == "give_item":
            self.give_item()
        elif outcome == "fight":
            self.start_fight()
        elif outcome == "call_guards":
            self.call_guards()
        elif outcome == "flee":
            npc.flags["fled_until"] = game.world.time + 6 * 60
            npc.present = False
            self.note(f"<warn>{npc.first_name} backs away and hurries off.</>")
            self.ended = True
        elif outcome == "unlock_topic" and topic:
            info = self.fill(self.pick("rumour_intro")) + " " + danger_or_news(game, self.rng)
            self.topics.append({"label": f"Ask about {topic}.", "info": info})
        elif outcome in ("agree", "refuse"):
            change_disposition(npc, 3 if outcome == "agree" else -3)

    def give_item(self) -> None:
        from realmwalker.rules.inventory import add_existing

        npc = self.npc
        game = self.game
        if npc.inventory:
            it = npc.inventory.pop(0)
            add_existing(game.leader, game.tables.items, it)
            self.note(f"<loot>{npc.first_name} gives you {game.tables.items.name(it)}.</>")
        elif npc.purse >= 20:
            amount = min(npc.purse // 4, 100)
            npc.purse -= amount
            game.leader.money += amount
            self.note(f"<loot>{npc.first_name} presses {money_text(amount)} into your hand.</>")
        else:
            self.note(f"{npc.first_name} has nothing to give.")

    def start_fight(self) -> None:
        from realmwalker.game.fight import start_battle
        from realmwalker.rules.creatures import spawn

        npc = self.npc
        game = self.game
        creature = spawn(game.tables, npc.stats, self.rng, 9000 + npc.id)
        creature.name = npc.first_name
        creature.named = True
        game.battle_npcs[creature.uid] = npc.id
        start_battle(game, [creature], f"{npc.first_name} goes for you.", title=npc.first_name, near=(npc.x, npc.y))
        game.leader.deeds.append(f"came to blows with {npc.label()} in {self.settlement.name}")
        self.ended = True

    def call_guards(self) -> None:
        from realmwalker.game.encounters import make_encounter

        game = self.game
        self.note(f"<danger>{self.npc.first_name} shouts for the watch.</>")
        if self.town_has_guards():
            game.encounter = make_encounter(game, "town_watch", self.rng)
            game.leader.deeds.append(f"had the watch called on them in {self.settlement.name}")
        self.ended = True


def quests_choices() -> set[str]:
    from realmwalker.game.quests import QUEST_CHOICES

    return QUEST_CHOICES


LAW_CHOICES = {"pay_fines", "surrender", "prisoners", "ransom", "licence", "hush_pay", "hush_threat", "probe",
               "join", "title", "pickpocket", "attack", "train", "lie_low"}


def builtin_special(game, npc: NPC, rng: RNG) -> list[dict]:
    """One or two skill-check options from data, for when the AI does not propose any."""
    sp = game.tables.dialogue["special"]
    options = list(sp.get("any", []))
    if npc.job in sp:
        options += sp[npc.job]
    occ = game.tables.people["occupations"].get(npc.job, {})
    if occ.get("trade") and "merchant" in sp:
        options += sp["merchant"]
    rng.shuffle(options)
    return options[:2]


def danger_rumour(game, rng: RNG) -> str:
    """Words about the most dangerous country near here."""
    from realmwalker.game.events import compass

    p = game.player
    w = game.world
    best = None
    for dx in range(-12, 13, 3):
        for dy in range(-12, 13, 3):
            x, y = p.x + dx, p.y + dy
            if w.in_bounds(x, y) and (best is None or w.danger[x, y] > w.danger[best[0], best[1]]):
                best = (x, y)
    if best is None or w.danger[best[0], best[1]] < 3:
        return ""
    kind = rng.choice(["beasts", "bandits", "dead", "monsters"] if w.danger[best[0], best[1]] >= 6 else ["beasts", "bandits"])
    d = game.tables.dialogue
    return textgen.fill(rng.choice(d["danger_rumour"]), rng, d,
                        {"direction": compass(best[0] - p.x, best[1] - p.y), "threat": d["threat_words"][kind]})


def danger_or_news(game, rng: RNG) -> str:
    line = danger_rumour(game, rng)
    if line:
        return line
    from realmwalker.game.events import hear_news

    return hear_news(game, rng)
