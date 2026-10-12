"""A character: the numbers of the sheet, what they carry and wear, and what follows from it.

`Character` is plain saveable data. `Sheet` answers questions about it (armour class, skill
bonuses, speed, how laden they are, how warm their clothes are) using the rules tables.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from realmwalker.rules.items import BODY_PARTS, EQUIP_SLOTS, Item, coin_weight
from realmwalker.rules.wounds import Wound

ABILITIES = ("str", "dex", "con", "int", "wis", "cha")


def modifier(score: int) -> int:
    return (score - 10) // 2


def signed(n: int) -> str:
    return f"+{n}" if n >= 0 else str(n)


@dataclass
class Character:
    name: str
    sex: str
    age: int
    race: str
    culture: str
    cls: str
    background: str
    base_scores: dict[str, int]
    abilities: dict[str, int]
    level: int = 1
    xp: int = 0
    subclass: str | None = None
    max_hp: int = 1
    hp: int = 1
    temp_hp: int = 0
    hit_dice: int = 1
    skills: list[str] = field(default_factory=list)
    expertise: list[str] = field(default_factory=list)
    saves: list[str] = field(default_factory=list)
    armor_prof: list[str] = field(default_factory=list)
    weapon_prof: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    fighting_style: str | None = None
    uses: dict[str, int] = field(default_factory=dict)
    spells: dict = field(default_factory=dict)
    inventory: list[Item] = field(default_factory=list)
    equipped: dict[str, int] = field(default_factory=dict)
    money: int = 0
    appearance: str = ""
    looks: dict = field(default_factory=dict)  # build, skin, eyes, hair, beard, marks... (rules/looks.py); {} = from words
    backstory: str = ""
    personality: str = ""
    ideal: str = ""
    bond: str = ""
    flaw: str = ""
    ties: list[dict] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    wounds: list[Wound] = field(default_factory=list)
    kills: dict[str, int] = field(default_factory=dict)
    deeds: list[str] = field(default_factory=list)
    pending: list[dict] = field(default_factory=list)  # level-up choices waiting (rules/progression.py)
    companion: dict = field(default_factory=dict)  # for companions: loyalty, wages, orders (game/companions.py)
    # The body over time (rules/body.py and rules/health.py). 0 = fine for the needs.
    hunger: float = 0.0
    thirst: float = 0.0
    fatigue: float = 0.0
    dirt: float = 0.0
    body_heat: float = 0.0  # -100 freezing .. 0 comfortable .. +100 heatstroke
    wet: float = 0.0
    exhaustion: int = 0  # 5e exhaustion, 0..6
    strain: float = 0.0  # builds towards the next level of exhaustion
    hurt_carry: float = 0.0  # fractions of hit points lost to cold, heat or sickness
    blood: float = 100.0  # 100 = all of it
    intoxication: float = 0.0
    diseases: list[dict] = field(default_factory=list)
    injuries: list[str] = field(default_factory=list)  # lasting injuries (scar, limp, lost eye...)
    addictions: dict[str, float] = field(default_factory=dict)
    effects: dict[str, float] = field(default_factory=dict)  # timed effects, hours left (poppy, herbal, hangover...)
    animals: list[dict] = field(default_factory=list)  # mules and horses: {"kind", "name", "unfed", "bought"}
    attuned: list[int] = field(default_factory=list)  # uids of magic items bound to them (rules/magic.py), at most 3
    formation: list[int] = field(default_factory=list)  # [column, row] in the battle order (game/arena.py); [] = by class
    next_uid: int = 1
    is_player: bool = True
    alive: bool = True

    # ------------------------------------------------------------------ saving
    def to_dict(self) -> dict:
        d = asdict(self)
        d["inventory"] = [i.to_dict() for i in self.inventory]
        d["wounds"] = [w.to_dict() for w in self.wounds]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Character:
        d = dict(d)
        d["inventory"] = [Item.from_dict(i) for i in d.get("inventory", [])]
        d["wounds"] = [Wound.from_dict(w) for w in d.get("wounds", [])]
        d["equipped"] = {k: int(v) for k, v in d.get("equipped", {}).items()}
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})

    # ------------------------------------------------------------------ inventory
    def item(self, uid: int) -> Item | None:
        for it in self.inventory:
            if it.uid == uid:
                return it
        return None

    def equipped_item(self, slot: str) -> Item | None:
        uid = self.equipped.get(slot)
        return self.item(uid) if uid is not None else None

    def slot_of(self, uid: int) -> str | None:
        for slot, u in self.equipped.items():
            if u == uid:
                return slot
        return None

    def new_uid(self) -> int:
        # The party shares one pack (rules/inventory.py), so a number must be free in it, not just in our own count.
        uid = max(self.next_uid, max((it.uid for it in self.inventory), default=0) + 1)
        self.next_uid = uid + 1
        return uid


class Sheet:
    """Everything derived from a character and the rules. Cheap to create; create one when needed."""

    def __init__(self, char: Character, tables) -> None:
        self.c = char
        self.t = tables
        self.items = tables.items
        self.rules = tables.rules

    # ------------------------------------------------------------------ basics
    def score(self, ability: str) -> int:
        score = self.c.abilities.get(ability, 10)
        if self.c.equipped:
            from realmwalker.rules import magic

            score = min(24, score + magic.total(self.c, "ability", ability=ability))
        return score

    def mod(self, ability: str) -> int:
        return modifier(self.score(ability))

    @property
    def proficiency(self) -> int:
        table = self.rules["proficiency_bonus"]
        return table[max(0, min(len(table) - 1, self.c.level - 1))]

    def skill_bonus(self, skill: str) -> int:
        ability = self.rules["skills"][skill]["ability"]
        bonus = self.mod(ability)
        if skill in self.c.expertise:
            bonus += 2 * self.proficiency
        elif skill in self.c.skills:
            bonus += self.proficiency
        elif self.c.attuned:
            from realmwalker.rules import magic

            if magic.proficient(self.c, skill):  # an artifact's gift
                bonus += self.proficiency
        if skill == "perception":
            helm = self.c.equipped_item("helmet")
            if helm is not None:
                bonus -= int(self.items.get(helm.def_id).get("perception_penalty", 0))
        if self.c.equipped:
            from realmwalker.rules import magic

            bonus += magic.total(self.c, "skill", skill=skill) + self.worn_skill_bonus(skill)
        return bonus + self.skill_condition(skill)

    def skill_condition(self, skill: str) -> int:
        """What the body's state does to a skill: pain, hunger, sickness..., exhaustion (2024: 2 per level off every
        d20 test), concussion for Int and Wis, lasting injuries."""
        from realmwalker.rules import health

        c = self.c
        if not (c.wounds or c.injuries or c.diseases or c.exhaustion or c.effects or c.intoxication
                or c.hunger >= 55 or c.thirst >= 60 or c.fatigue >= 70 or abs(c.body_heat) >= 40 or c.blood < 80):
            return 0
        total = health.penalty(c, self.t) - 2 * c.exhaustion
        if self.rules["skills"][skill]["ability"] in ("int", "wis") and health.concussed(c):
            total -= 5
        total += health.injury_effects(c, self.t)["skills"].get(skill, 0)
        return total

    def worn_skill_bonus(self, skill: str) -> int:
        """What plain things worn add to a skill (a trophy at the neck: +1 Intimidation)."""
        total = 0
        for uid in self.c.equipped.values():
            it = self.c.item(uid)
            if it is not None:
                total += int(self.items.get(it.def_id).get("bonus", {}).get("skills", {}).get(skill, 0))
        return total

    def save_bonus(self, ability: str) -> int:
        bonus = self.mod(ability) + (self.proficiency if ability in self.c.saves else 0)
        c = self.c
        if ability == "wis" and c.effects.get("steadied", 0) > 0:
            bonus += 1  # an hour of prayer (game/gear.py pray)
        if c.equipped:
            from realmwalker.rules import magic

            bonus += magic.total(c, "save")
        if c.wounds or c.diseases or c.exhaustion or c.effects or c.intoxication or c.hunger >= 55 or c.thirst >= 60                 or c.fatigue >= 70 or abs(c.body_heat) >= 40 or c.blood < 80:
            from realmwalker.rules import health

            bonus += health.penalty(c, self.t) - 2 * c.exhaustion  # exhaustion: 2 per level (2024)
        return bonus

    def attack_condition(self, ranged: bool = False) -> int:
        """Pain, hunger, sickness, old injuries and exhaustion (2024: 2 per level) on attack rolls."""
        c = self.c
        if not (c.wounds or c.injuries or c.diseases or c.effects or c.intoxication or c.exhaustion or c.hunger >= 55
                or c.thirst >= 60 or c.fatigue >= 70 or abs(c.body_heat) >= 40 or c.blood < 80):
            return 0
        from realmwalker.rules import health

        inj = health.injury_effects(c, self.t)
        return health.penalty(c, self.t) + inj["attack"] + (inj["ranged_attack"] if ranged else 0) - 2 * c.exhaustion

    @property
    def initiative(self) -> int:
        return self.mod("dex")

    @property
    def passive_perception(self) -> int:
        return 10 + self.skill_bonus("perception")

    @property
    def race(self) -> dict:
        return self.t.races[self.c.race]

    @property
    def klass(self) -> dict:
        return self.t.classes[self.c.cls]

    def has_rule(self, rule: str) -> bool:
        """True if a race trait or class feature with this rule tag applies."""
        for trait in self.race["traits"]:
            if trait.get("rule") == rule:
                return True
        for feat in self.features():
            if feat.get("rule") == rule:
                return True
        return False

    def features(self) -> list[dict]:
        cls = self.klass
        out = [f for f in cls["features"] if f["level"] <= self.c.level]
        if self.c.subclass and self.c.subclass in cls.get("subclasses", {}):
            out += [f for f in cls["subclasses"][self.c.subclass]["features"] if f["level"] <= self.c.level]
        return out

    @property
    def darkvision(self) -> int:
        return int(self.race.get("darkvision", 0))

    # ------------------------------------------------------------------ armour
    def armor_class(self) -> int:
        dex = self.mod("dex")
        armor = self.c.equipped_item("armor")
        if armor is not None:
            d = self.items.get(armor.def_id)
            kind = d.get("armor_type", "light")
            base = int(d.get("ac", 10)) + int(self.items.qualities.get(armor.quality, {}).get("armor", 0))
            if armor.condition < int(self.items.upkeep.get("battered", 30)):
                base -= 1
            if kind == "light":
                ac = base + dex
            elif kind == "medium":
                ac = base + min(dex, 2)
            else:
                ac = base
            if self.c.fighting_style == "defense":
                ac += 1
        else:
            from realmwalker.rules import spells

            ac = max([10] + [int(b) for b in spells.lasting_values(self.c, self.t, "mage_armor")]) + dex
        shield = self.c.equipped_item("off_hand")
        if shield is not None and self.items.category(shield) == "shield":
            ac += int(self.items.get(shield.def_id).get("ac_bonus", 2))
        if self.c.equipped:
            from realmwalker.rules import magic

            ac += magic.total(self.c, "ac")
        if self.c.effects:
            from realmwalker.rules import spells

            ac += sum(int(b) for b in spells.lasting_values(self.c, self.t, "ac"))
        return ac

    def proficient_with_armor(self, item: Item) -> bool:
        d = self.items.get(item.def_id)
        kind = d.get("armor_type") if d["category"] == "armor" else ("shield" if d["category"] == "shield" else None)
        return kind is None or kind in self.c.armor_prof

    def proficient_with_weapon(self, item: Item) -> bool:
        d = self.items.get(item.def_id)
        return d.get("group") in self.c.weapon_prof or item.def_id in self.c.weapon_prof

    def coverage(self) -> dict[str, list[str]]:
        """Which worn armour protects each body part."""
        out: dict[str, list[str]] = {part: [] for part in BODY_PARTS}
        for slot in ("armor", "helmet"):
            it = self.c.equipped_item(slot)
            if it is not None:
                for part in self.items.get(it.def_id).get("covers", []):
                    out[part].append(self.items.name(it, with_qty=False))
        shield = self.c.equipped_item("off_hand")
        if shield is not None and self.items.category(shield) == "shield":
            out["arms"].append(self.items.name(shield, with_qty=False))
        return out

    # ------------------------------------------------------------------ clothing
    def worn(self) -> list[Item]:
        items = []
        for slot in ("under", "main", "armor", "outer", "head", "helmet", "hands", "feet"):
            it = self.c.equipped_item(slot)
            if it is not None:
                items.append(it)
        return items

    def warmth(self) -> float:
        """Insulation from everything worn (clothing layers and padded armour)."""
        total = 0.0
        for it in self.worn():
            d = self.items.get(it.def_id)
            w = float(d.get("warmth", 0))
            total += w * (0.5 + 0.5 * it.condition / 100.0)
        if self.c.equipped:
            from realmwalker.rules import magic

            total += magic.total(self.c, "warmth")
        return round(total, 1)

    def wind_protection(self) -> float:
        """0..1: how well the outer layers keep out the wind."""
        best = 0.0
        for slot in ("outer", "main", "armor"):
            it = self.c.equipped_item(slot)
            if it is not None:
                best = max(best, float(self.items.get(it.def_id).get("wind", 0.2 if slot == "armor" else 0)))
        return best

    def water_protection(self) -> float:
        best = 0.0
        for slot in ("outer", "main", "head"):
            it = self.c.equipped_item(slot)
            if it is not None:
                best = max(best, float(self.items.get(it.def_id).get("water", 0)))
        return best

    def social(self) -> int:
        """How respectable the clothes look: -2 rags .. +3 courtly."""
        main = self.c.equipped_item("main")
        if main is None:
            return -3
        value = int(self.items.get(main.def_id).get("social", 0))
        feet = self.c.equipped_item("feet")
        if feet is not None:
            value += 1 if self.items.get(feet.def_id).get("social", 0) >= 2 else 0
        if main.condition < 40:
            value -= 1
        jewels = (self.c.equipped_item("ring"), self.c.equipped_item("neck"))
        if any(int(self.items.get(it.def_id).get("social", 0)) > 0 for it in jewels if it is not None):
            value += 1  # a ring or a pendant: somebody with something to lose
        return max(-3, min(3, value))

    # ------------------------------------------------------------------ carrying
    def carried_weight(self) -> float:
        return round(sum(self.items.weight(i) for i in self.c.inventory) + coin_weight(self.c.money), 1)

    def capacity(self) -> tuple[float, float, float]:
        """(encumbered above, heavily encumbered above, cannot move above), in pounds."""
        s = self.c.abilities.get("str", 10)
        carry = self.rules["carry"]
        extra = self.pack_carry()
        if self.c.animals:
            from realmwalker.game.services import animal_carry

            extra += animal_carry(self.c, self.t)
        return (s * carry["encumbered_per_strength"] + extra, s * carry["heavily_per_strength"] + extra,
                s * carry["per_strength"] + extra)

    def pack_carry(self) -> float:
        """Pounds more before you count as laden, for what is worn on the back (a backpack, a sack)."""
        back = self.c.equipped_item("back")
        return float(self.items.get(back.def_id).get("carry", 0)) if back is not None else 0.0

    def load(self) -> float:
        """Weight that counts against strength: worn armour counts half (the body carries it), and the clothes
        you are dressed in not at all; what is in your hands and your pack counts in full."""
        worn = {uid for slot, uid in self.c.equipped.items() if slot not in ("main_hand", "off_hand")}
        total = 0.0
        for it in self.c.inventory:
            w = self.items.weight(it)
            if it.uid in worn:
                w *= 0.0 if self.items.get(it.def_id).get("category") == "clothing" else 0.5
            total += w
        return round(total + coin_weight(self.c.money), 1)

    def encumbrance(self) -> int:
        """0 unburdened, 1 encumbered, 2 heavily encumbered, 3 overloaded (cannot travel)."""
        w = self.pack_load()
        light, heavy, limit = self.pack_capacity()
        if w > limit:
            return 3
        if w > heavy:
            return 2
        if w > light:
            return 1
        return 0

    def pack_load(self) -> float:
        """What the party carries together when it shares one pack (rules/inventory.py): the pack once, each
        member's worn things counted the way load() counts them, and everyone's coin. Alone, just load()."""
        from realmwalker.rules.inventory import pack_mates

        mates = pack_mates(self.c)
        if len(mates) <= 1:
            return self.load()
        whole = sum(self.items.weight(it) for it in self.c.inventory)
        return round(sum(Sheet(m, self.t).load() for m in mates) - (len(mates) - 1) * whole, 1)

    def pack_capacity(self) -> tuple[float, float, float]:
        """Everyone's strength together (and the animals) when the party shares one pack. Alone, just capacity()."""
        from realmwalker.rules.inventory import pack_mates

        mates = pack_mates(self.c)
        if len(mates) <= 1:
            return self.capacity()
        caps = [Sheet(m, self.t).capacity() for m in mates]
        return tuple(sum(c[i] for c in caps) for i in range(3))  # type: ignore[return-value]

    def armor_too_heavy(self) -> bool:
        armor = self.c.equipped_item("armor")
        if armor is None or self.has_rule_trait("sturdy"):
            return False
        req = int(self.items.get(armor.def_id).get("str_req", 0))
        return req > 0 and self.c.abilities.get("str", 10) < req

    def is_caster(self) -> bool:
        from realmwalker.rules import spells

        return spells.is_caster(self.c, self.t)

    def has_rule_trait(self, trait_id: str) -> bool:
        return any(t["id"] == trait_id for t in self.race["traits"])

    def speed(self) -> int:
        speed = int(self.race["speed"])
        if self.c.injuries:
            from realmwalker.rules import health

            speed += health.injury_effects(self.c, self.t)["speed"]
        if self.armor_too_heavy():
            speed -= 10
        speed -= 5 * self.c.exhaustion  # 2024: 5 feet per level of exhaustion
        if self.c.attuned:
            from realmwalker.rules import magic

            speed += magic.total(self.c, "speed")
        enc = self.encumbrance()
        if enc == 1:
            speed -= 10
        elif enc >= 2:
            speed -= 20
        return max(5, speed) if enc < 3 else 0

    def travel_multiplier(self) -> float | None:
        """How much longer journeys take than for an unburdened walker at 30 ft (None = cannot move)."""
        if self.encumbrance() >= 3:
            return None
        return 30.0 / max(5, self.speed())

    # ------------------------------------------------------------------ progression
    def xp_for_next(self) -> int | None:
        table = self.rules["xp_for_level"]
        return table[self.c.level] if self.c.level < len(table) else None


def all_slots() -> tuple[str, ...]:
    return EQUIP_SLOTS
