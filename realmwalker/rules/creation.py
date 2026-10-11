"""Character creation: the choices a player makes, checked against the rules, turned into a Character.

Every choice has a sensible default, so a character can be made by accepting everything
(the autoplay bot relies on this). Social ties are tied to real places in the world.
"""

from __future__ import annotations

import math

from realmwalker.core import textgen
from realmwalker.core.rng import RNG
from realmwalker.rules import looks
from realmwalker.rules.character import ABILITIES, Character, modifier
from realmwalker.rules.inventory import add_item, equip_everything_sensible, fill_containers

SEXES = ("male", "female")
# Default skill picks, most generally useful first.
SKILL_PREFERENCE = ["perception", "stealth", "survival", "medicine", "arcana", "insight", "athletics", "investigation",
                    "sleight_of_hand", "persuasion", "acrobatics", "history", "religion", "intimidation", "deception"]
PRONOUNS = {"male": ("he", "him", "his"), "female": ("she", "her", "her")}


class CharacterBuilder:
    def __init__(self, tables, rng: RNG, world=None) -> None:
        self.t = tables
        self.rng = rng
        self.world = world  # names come from this world's forge when there is one
        self.race = "human"
        self.culture = "heartland"
        self.cls = "fighter"
        self.background = "soldier"
        self.scores: dict[str, int] = dict(tables.classes[self.cls]["suggested"])
        self.class_skills: list[str] = []
        self.expertise: list[str] = []
        self.fighting_style: str | None = None
        self.style_chosen = False  # the player picked the fighting style by hand
        self.subclass: str | None = None
        self.kit = 0
        self.sex = "male"
        self.name = ""
        self.age = 25
        self.appearance = ""
        self.looks: dict = {}  # rules/looks.py; the appearance words are written from these
        self.backstory = ""
        self.personality = self.ideal = self.bond = self.flaw = ""
        self.start_settlement: int | None = None
        self.set_class("fighter")
        self.randomize_identity()

    # ------------------------------------------------------------------ choices
    def set_race(self, race: str) -> None:
        self.race = race
        cultures = self.t.races[race]["cultures"]
        if self.culture not in cultures:
            self.culture = cultures[0]
        self.randomize_identity(keep_sex=True)
        self._fix_skills()

    def set_culture(self, culture: str) -> None:
        if culture in self.t.races[self.race]["cultures"]:
            self.culture = culture
            self.randomize_identity(keep_sex=True)

    def set_kit(self, kit: int) -> None:
        """Choose the equipment; until a fighting style has been picked by hand, the one that suits it goes with it
        (Defence with mail and a shield, Archery with a longbow)."""
        c = self.t.classes[self.cls]
        self.kit = max(0, min(kit, len(c["kits"]) - 1))
        style = c["kits"][self.kit].get("style")
        if self.fighting_style is not None and not self.style_chosen and style in c.get("fighting_styles", {}):
            self.fighting_style = style

    def set_class(self, cls: str) -> None:
        self.cls = cls
        c = self.t.classes[cls]
        self.scores = dict(c["suggested"])
        self.kit = 0
        self.fighting_style = next(iter(c.get("fighting_styles", {})), None) if "fighting_style" in c["choices_at_1"] else None
        self.style_chosen = False
        self.set_kit(0)
        subs = list(c.get("subclasses", {}))
        self.subclass = subs[0] if "subclass" in c["choices_at_1"] and subs else None
        self.class_skills = []
        self.expertise = []
        self._fix_skills()

    def set_background(self, bg: str) -> None:
        self.background = bg
        self.start_settlement = None
        self._fix_skills()

    def fixed_skills(self) -> list[str]:
        """Skills granted by race and background (not chosen)."""
        return list(dict.fromkeys(self.t.races[self.race]["skills"] + self.t.backgrounds[self.background]["skills"]))

    def skill_options(self) -> list[str]:
        fixed = set(self.fixed_skills())
        return [s for s in self.t.classes[self.cls]["skill_choices"] if s not in fixed]

    def skill_count(self) -> int:
        return self.t.classes[self.cls]["skill_count"]

    def toggle_skill(self, skill: str) -> bool:
        if skill in self.class_skills:
            self.class_skills.remove(skill)
            if skill in self.expertise:
                self.expertise.remove(skill)
            return True
        if skill in self.skill_options() and len(self.class_skills) < self.skill_count():
            self.class_skills.append(skill)
            return True
        return False

    def all_skills(self) -> list[str]:
        return list(dict.fromkeys(self.fixed_skills() + self.class_skills))

    def needs_expertise(self) -> int:
        return 2 if "expertise" in self.t.classes[self.cls]["choices_at_1"] else 0

    def toggle_expertise(self, skill: str) -> bool:
        if skill in self.expertise:
            self.expertise.remove(skill)
            return True
        if skill in self.all_skills() and len(self.expertise) < self.needs_expertise():
            self.expertise.append(skill)
            return True
        return False

    def _fix_skills(self) -> None:
        """Keep chosen skills valid and fill any missing picks with sensible defaults."""
        options = self.skill_options()
        self.class_skills = [s for s in self.class_skills if s in options][: self.skill_count()]
        for s in [p for p in SKILL_PREFERENCE if p in options] + options:
            if len(self.class_skills) >= self.skill_count():
                break
            if s not in self.class_skills:
                self.class_skills.append(s)
        self.expertise = [s for s in self.expertise if s in self.all_skills()][: self.needs_expertise()]
        preferred = ["stealth", "perception", "sleight_of_hand", "deception", "acrobatics", "investigation"]
        for s in preferred + self.all_skills():
            if len(self.expertise) >= self.needs_expertise():
                break
            if s in self.all_skills() and s not in self.expertise:
                self.expertise.append(s)

    # ------------------------------------------------------------------ ability scores
    @property
    def point_buy(self) -> dict:
        return self.t.rules["point_buy"]

    def points_spent(self) -> int:
        costs = self.point_buy["costs"]
        return sum(costs[str(v)] for v in self.scores.values())

    def points_left(self) -> int:
        return self.point_buy["budget"] - self.points_spent()

    def can_change(self, ability: str, delta: int) -> bool:
        pb = self.point_buy
        new = self.scores[ability] + delta
        if new < pb["min"] or new > pb["max"]:
            return False
        costs = pb["costs"]
        extra = costs[str(new)] - costs[str(self.scores[ability])]
        return self.points_left() - extra >= 0

    def change(self, ability: str, delta: int) -> bool:
        if self.can_change(ability, delta):
            self.scores[ability] += delta
            return True
        return False

    def final_scores(self) -> dict[str, int]:
        bonus = self.t.races[self.race]["ability_bonus"]
        return {a: self.scores[a] + int(bonus.get(a, 0)) for a in ABILITIES}

    def max_hp(self) -> int:
        con = modifier(self.final_scores()["con"])
        return max(1, self.t.classes[self.cls]["hit_die"] + con + int(self.t.races[self.race].get("hp_per_level", 0)))

    # ------------------------------------------------------------------ identity
    def random_name(self) -> str:
        if self.world is not None:
            from realmwalker.world.names import forge

            return forge(self.world, self.t).person(self.culture, self.sex, self.rng)
        culture = self.t.names["cultures"].get(self.culture) or next(iter(self.t.names["cultures"].values()))
        return f"{self.rng.choice(culture[self.sex])} {self.rng.choice(culture['family'])}"

    def culture_label(self) -> str:
        return self.t.cultures.adjective(self.world, self.culture)

    def random_age(self) -> int:
        age = self.t.races[self.race]["age"]
        lo = age["adult"]
        hi = max(lo + 1, int(lo + (age["old"] - lo) * 0.5))
        return self.rng.randint(lo, hi)

    def random_appearance(self) -> str:
        """New looks, at random for this people, sex and age; returns the words for them."""
        self.randomize_looks()
        return self.appearance

    def randomize_looks(self) -> None:
        self.looks = looks.random_looks(self.t, self.race, self.sex, self.age, self.rng)
        self.appearance = looks.describe(self.t, self.looks, self.race, self.sex)

    def set_look(self, slot: str, value: str) -> None:
        """One look chosen (slot: build, skin, eyes, hair, hair_colour, beard, beard_colour, mark, paint, paint_colour,
        dye, cloak, or feature:<name>); the words that describe the character are written again."""
        new = dict(self.looks)
        if slot.startswith("feature:"):
            new["features"] = {**(new.get("features") or {}), slot[8:]: value}
        else:
            if slot == "hair_colour" and new.get("beard_colour") == new.get("hair_colour"):
                new["beard_colour"] = value  # a beard follows the hair unless chosen apart
            new[slot] = value
        self.looks = looks.normalise(self.t, new, self.race, self.sex, self.name)
        self.appearance = looks.describe(self.t, self.looks, self.race, self.sex)

    def fit_looks(self) -> None:
        """Keep the looks that still suit after a change of sex (a beard may go), and say them again."""
        self.looks = looks.normalise(self.t, self.looks, self.race, self.sex, self.name)
        self.appearance = looks.describe(self.t, self.looks, self.race, self.sex)

    def randomize_identity(self, keep_sex: bool = False) -> None:
        if not keep_sex:
            self.sex = self.rng.choice(list(SEXES))
        self.name = self.random_name()
        self.age = self.random_age()
        self.randomize_looks()
        self.backstory = ""

    def fallback_backstory(self, home_name: str) -> dict:
        """A backstory from the built-in words (data/appearance.json backstory)."""
        a = self.t.appearance
        bg = self.t.backgrounds[self.background]
        he, him, his = PRONOUNS[self.sex]
        culture = self.culture_label()
        values = {
            "name": self.name.split()[0], "home": home_name, "years": str(self.age), "culture": culture,
            "season": self.rng.choice(["winter", "spring", "summer", "autumn"]),
            "nth": self.rng.choice(["second", "third", "fourth", "youngest", "eldest"]),
            "pronoun": he, "pronoun_cap": he.capitalize(), "object": him, "possessive": his,
            "coin": "a few coins",
        }
        values["background_line"] = textgen.fill(a["background_lines"][self.background], self.rng, {}, values)
        parts = [textgen.fill(self.rng.choice(a["backstory"][k]), self.rng, {}, values) for k in ("opening", "middle", "closing")]
        return {
            "backstory": " ".join(parts),
            "personality": self.rng.choice(bg["personality"]),
            "ideal": self.rng.choice(bg["ideal"]),
            "bond": self.rng.choice(bg["bond"]),
            "flaw": self.rng.choice(bg["flaw"]),
        }

    def apply_backstory(self, data: dict) -> None:
        self.backstory = data.get("backstory", "")
        self.personality = data.get("personality", "")
        self.ideal = data.get("ideal", "")
        self.bond = data.get("bond", "")
        self.flaw = data.get("flaw", "")

    # ------------------------------------------------------------------ checks and build
    def problems(self) -> list[str]:
        out = []
        if self.points_left() < 0:
            out.append("You have spent more ability points than you have.")
        if len(self.class_skills) != self.skill_count():
            out.append(f"Choose {self.skill_count()} class skills.")
        if len(self.expertise) != self.needs_expertise():
            out.append(f"Choose {self.needs_expertise()} skills for Expertise.")
        if not self.name.strip():
            out.append("Your character needs a name.")
        return out

    def build(self, world_time: int = 0) -> Character:
        t = self.t
        race, cls, bg = t.races[self.race], t.classes[self.cls], t.backgrounds[self.background]
        abilities = self.final_scores()
        armor = list(cls["armor"])
        weapons = list(cls["weapons"])
        if self.subclass:
            sub = cls["subclasses"][self.subclass]
            armor += sub.get("armor", [])
            weapons += sub.get("weapons", [])
        tools = list(dict.fromkeys(cls["tools"] + bg["tools"] + race.get("tools_choice", [])[:1]))
        extra_langs = race["extra_languages"] + bg["languages"]
        languages = list(race["languages"])
        for lang in t.rules["languages"]:
            if extra_langs <= 0:
                break
            if lang not in languages and lang != "Thieves' Cant":
                languages.append(lang)
                extra_langs -= 1
        if self.cls == "rogue":
            languages.append("Thieves' Cant")
        hp = self.max_hp()
        features = [f["id"] for f in cls["features"] if f["level"] <= 1]
        uses = {}
        if "second_wind" in features:
            uses["second_wind"] = 1
        if race and any(tr.get("rule") == "relentless_endurance" for tr in race["traits"]):
            uses["relentless_endurance"] = 1
        char = Character(
            name=self.name.strip(), sex=self.sex, age=self.age, race=self.race, culture=self.culture,
            cls=self.cls, background=self.background, base_scores=dict(self.scores), abilities=abilities,
            level=1, xp=0, subclass=self.subclass, max_hp=hp, hp=hp, hit_dice=1,
            skills=self.all_skills(), expertise=list(self.expertise), saves=list(cls["saves"]),
            armor_prof=list(dict.fromkeys(armor)), weapon_prof=list(dict.fromkeys(weapons)), tools=tools,
            languages=languages, features=features, fighting_style=self.fighting_style, uses=uses,
            money=int(bg["money"]), appearance=self.appearance, looks=dict(self.looks), backstory=self.backstory,
            personality=self.personality, ideal=self.ideal, bond=self.bond, flaw=self.flaw,
        )
        items = t.items
        kit = cls["kits"][max(0, min(self.kit, len(cls["kits"]) - 1))]
        for def_id, qty in t.items.starting_packs.get("everyone", []) + kit["items"] + bg["items"]:
            add_item(char, items, def_id, int(qty), made_at=world_time)
        equip_everything_sensible(char, items)
        fill_containers(char, items, "clean")
        from realmwalker.rules.spells import init_spells

        init_spells(char, t)
        if "channel_divinity" in char.features or self.cls == "cleric":
            char.uses.setdefault("channel_divinity", 0)
        if self.subclass == "war":
            char.uses["war_priest"] = max(1, modifier(abilities["wis"]))
        return char


# ---------------------------------------------------------------------------- places and ties
def starting_places(world, tables, background: str, race: str, rng: RNG, count: int = 4,
                    culture: str | None = None) -> list[int]:
    """A few settlements suited to a background, spread over the map (among the character's own people, where
    there are any)."""
    bg = tables.backgrounds[background]
    kinds = bg["start"]["kinds"]
    biomes = set(bg["start"].get("biomes", []))
    preferred_culture = {"elf": "elven", "dwarf": "dwarven", "halfling": "halfling"}.get(race)
    scored = []
    for s in world.settlements:
        score = 0.0
        if s.kind in kinds:
            score += 3
        elif s.kind in ("town", "village") or (race == "dwarf" and s.kind == "hold") or (race == "elf" and s.kind == "elfhall"):
            score += 1
        else:
            continue
        if biomes and world.biome_id(s.x, s.y) in biomes:
            score += 2
        if preferred_culture and s.culture == preferred_culture:
            score += 2
        if culture and s.culture == culture:
            score += 4
        if race == "dwarf" and s.kind == "hold" or race == "elf" and s.kind == "elfhall":
            score += 3
        score += rng.random()
        scored.append((score, s))
    scored.sort(key=lambda p: -p[0])
    chosen: list = []
    for _, s in scored:
        if all(math.hypot(s.x - o.x, s.y - o.y) > 12 for o in chosen):
            chosen.append(s)
        if len(chosen) >= count:
            break
    return [s.id for s in chosen]


def make_ties(world, tables, character: Character, start_id: int, rng: RNG) -> list[dict]:
    """Starting social ties: people and places that exist in this world."""
    bg = tables.backgrounds[character.background]
    words = tables.backgrounds_data["tie_words"]
    start = world.settlements[start_id]
    culture = tables.names["cultures"].get(start.culture) or tables.names["cultures"]["heartland"]
    from realmwalker.world.names import forge

    nf = forge(world, tables)

    def person(title_m: str = "", title_f: str = "") -> str:
        sex = rng.choice(["male", "female"])
        title = (title_m if sex == "male" else title_f)
        name = nf.person(start.culture, sex, rng)
        return f"{title} {name}" if title else name

    def nearby(kinds: tuple[str, ...], exclude: int | None = None) -> object:
        options = [s for s in world.settlements if s.kind in kinds and s.id != exclude]
        options.sort(key=lambda s: math.hypot(s.x - start.x, s.y - start.y))
        return rng.choice(options[:4]) if options else start

    from realmwalker.world import factions as fx

    tie = bg["tie"]
    values: dict[str, str] = {k: rng.choice(v) for k, v in words.items()}
    refs: dict = {}
    kind = tie["kind"]
    have_factions = bool(getattr(world, "factions", None))
    if kind == "lord_served":
        seat = nearby(("town", "city"))
        lord_faction = fx.owner_of(world, seat) if have_factions else None
        leader = fx.leader_of(world, lord_faction)
        if lord_faction is not None and leader is not None:
            house = lord_faction.name if lord_faction.kind == "noble_house" else                 f"House {lord_faction.flags.get('dynasty') or leader.name.split()[-1]}"
            values.update(lord=leader.full_name(), house=house, place=seat.name)
            deserted = "desert" in values.get("how", "")
            refs.update(faction=lord_faction.id, standing=-30 if deserted else 15)
        else:
            values.update(lord=person("Lord", "Lady"), house=f"House {rng.choice(culture['family'])}", place=seat.name)
        refs["place"] = seat.id
    elif kind == "temple":
        values.update(place=start.name, priest=person("Father", "Mother"))
        refs["place"] = start.id
        church = fx.church_of(world, fx.faith_for_culture(tables, start.culture)) if have_factions else None
        if church is not None:
            refs.update(faction=church.id, standing=25)
    elif kind == "criminal":
        other = nearby(("town", "city", "village"), exclude=start.id)
        bounty = rng.choice([15, 20, 25, 40, 50])
        values.update(contact=person(), place=start.name, bounty_place=other.name, bounty=f"{bounty} gold crowns")
        refs.update(place=start.id, bounty_place=other.id, bounty=bounty * 100, crime=values.get("crime", ""))
        if have_factions:
            realm = fx.realm_of_settlement(world, other)
            if realm is not None:
                refs["bounty_faction"] = realm.id
            thieves = [f for f in fx.active_factions(world, "thieves_guild") if start.id in f.presence]
            if thieves:
                refs.update(faction=thieves[0].id, standing=20)
    elif kind == "home_village":
        values.update(place=start.name, headman=person())
        refs["place"] = start.id
        lord_faction = fx.owner_of(world, start) if have_factions else None
        if lord_faction is not None:
            refs.update(faction=lord_faction.id, standing=10)
    elif kind == "noble_house":
        family = character.name.split()[-1]
        seat = nearby(("town", "city"))
        values.update(house=f"House {family}", place=seat.name, head=person().split()[0] + f" {family}")
        refs["place"] = seat.id
    elif kind == "scholar":
        city = nearby(("city", "town"))
        values.update(master=person("Master", "Mistress"), place=city.name)
        refs["place"] = city.id
        circles = fx.active_factions(world, "mages_circle") if have_factions else []
        if circles:
            refs.update(faction=circles[0].id, standing=15)
    elif kind == "clan":
        values.update(place=start.name, chief=person())
        refs["place"] = start.id
        clans = sorted(fx.active_factions(world, "highland_clan", "clan") if have_factions else [],
                       key=lambda f: math.hypot(world.settlements[f.seat].x - start.x, world.settlements[f.seat].y - start.y))
        if clans and math.hypot(world.settlements[clans[0].seat].x - start.x, world.settlements[clans[0].seat].y - start.y) < 40:
            clan = clans[0]
            leader = fx.leader_of(world, clan)
            name = clan.name[4:] if clan.name.lower().startswith("the ") else clan.name  # "born to the {clan}"
            values.update(clan=name, place=world.settlements[clan.seat].name,
                          chief=leader.full_name() if leader else person())
            refs.update(faction=clan.id, standing=30, place=clan.seat)
    elif kind == "guild":
        values.update(place=start.name, master=person())
        refs["place"] = start.id
        want = "smiths_guild" if "Smith" in values.get("guild", "") else "merchant_guild"
        guilds = fx.active_factions(world, want) if have_factions else []
        if guilds:
            refs.update(faction=guilds[0].id, standing=5)
    from realmwalker.world.ages.ties import enrich

    extra = enrich(world, tables, kind, character, start, values, refs, rng)  # the real past behind it, if any
    text = textgen.fill(tie["text"], rng, {}, values)
    if extra:
        text = f"{text} {extra}"
    return [{"kind": kind, "text": text, "names": {k: v for k, v in values.items() if k not in words}, "refs": refs}]
