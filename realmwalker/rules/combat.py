"""Battles on a grid of five-foot squares, by the rules of D&D 5e. Pure logic, no drawing.

Flow: create a Battle (with the field it is fought on and where everyone starts), call start(). Then repeatedly call
step(): it runs start-of-turn effects, skips anyone who cannot act, and plays whole turns for the enemy (and for
party members on Auto). When step() returns False and pending_party() gives a fighter, the player spends that
fighter's turn with the do_* methods (move, attack, cast, dash, dodge...) and ends it with end_turn(). When `outcome`
is set the battle is over; result() summarises it.

The turn, as in the Player's Handbook: move up to your speed (before, after or between the other things you do),
one action, one bonus action if something gives you one, and one reaction a round (an opportunity attack against
someone leaving your reach, the Shield spell, Uncanny Dodge). Actions: Attack (more than one swing with Extra
Attack, with movement between them), Cast a Spell, Dash, Disengage, Dodge, Help, Hide, Shove, Grapple, Use an
Object, plus Parley, Surrender and leaving the field from its edge. Area spells hit everyone in the area, friend or
foe. Concentration ends when the caster fails a Constitution save after being hurt. At 0 hit points a party member
is down and makes death saving throws; monsters die.

The geometry (distances, sight, cover, areas, paths) is in rules/grid.py; the enemy's choices in rules/tactics.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.rules import feats, grid
from realmwalker.rules import spells as spellrules
from realmwalker.rules.character import Character, Sheet, modifier
from realmwalker.rules.engine import actions, durations, effects, events, hazards, marks, query, reactions
from realmwalker.rules.engine.handlers import general_feats, mastery
from realmwalker.rules.engine.reactions import Decision
from realmwalker.rules.engine import traits as trs
from realmwalker.rules.creatures import Creature
from realmwalker.rules.inventory import remove_item
from realmwalker.rules.items import Item
from realmwalker.rules.magic import item_flag as magic_flag
from realmwalker.rules.wounds import ARMOR_FACTOR, PART_GROUP, make_wound, roll_location, severity_for, wound_chance

PARTY, FOE = "party", "foe"
SIZES = ["tiny", "small", "medium", "large", "huge", "gargantuan"]
WOUND_HP_FLOOR = 14  # hit points a character's body counts as having, at least, when a blow is sized as a wound
MORALE_HP = {"beast": 0.4, "bandit": 0.35, "coward": 0.6, "soldier": 0.3, "warrior": 0.15}
FEARLESS = {"fanatic", "mindless"}
MERCIFUL = {"bandit", "coward", "soldier"}  # these rob a beaten party and leave it alive
DEFAULT_RANGE = query.DEFAULT_RANGE
ACTIVITY = ("move", "attack", "damage", "cast", "push", "teleport", "heal", "dart", "token_strike")
QUIET_ROUNDS = 3  # rounds in which nobody can get at anybody before a fight breaks off
STATES = ("fighting", "fleeing", "down", "dead", "fled", "surrendered", "away")  # away: banished, blinked, sealed


# The weapon properties a stat block's attack keeps from its item (its numbers are the block's own; Heavy is what
# Great Weapon Master reads).
CREATURE_PROPS = ("heavy", "two_handed", "finesse", "light", "thrown")


@dataclass
class AttackOption:
    key: str
    name: str
    kind: str  # melee, ranged, spell_melee, spell_ranged
    bonus: int
    damage: str
    damage_type: str
    reach: bool = False
    properties: list[str] = field(default_factory=list)
    item_uid: int | None = None
    ammo_def: str | None = None
    extra: dict = field(default_factory=dict)
    available: bool = True
    reason: str = ""
    range: tuple[int, int] = (0, 0)  # feet, normal and long (ranged and thrown)
    two_hands: bool = False  # a melee weapon held in both hands (two-handed, or versatile with the other hand free)

    @property
    def is_melee(self) -> bool:
        return self.kind in ("melee", "spell_melee")

    @property
    def reach_sq(self) -> int:
        return 2 if self.reach else 1


@dataclass
class Env:
    light: float = 1.0
    rain: bool = False
    place: str = ""
    ground: str = "ground"
    party_light: bool = False  # a torch or lantern is lit
    surprised: str | None = None  # PARTY or FOE
    carried_light: int = 0  # squares of bright light around the one carrying the party's torch or lantern


@dataclass
class Zone:
    """Something lying on the field for a while: a web, burning ground, fog, a spell's aura."""
    id: int
    kind: str  # web, fire, fog, ice, guardians (moves with its owner), guardian (stays where it was set); the
    # catalogue's: plants (Entangle), grease, spikes (Spike Growth), daggers (Cloud of Daggers), moonbeam, sphere
    # (Flaming Sphere), silence, darkness
    cells: set
    owner: int | None = None
    spell: str = ""
    rounds: int = 10  # owner's turns left; -1 while the owner keeps concentrating
    radius: int = 0
    centre: tuple[int, int] | None = None
    save: str = ""
    dc: int = 10
    damage: str = ""
    damage_type: str = ""
    on_save: str = "half"
    friends_safe: bool = False  # it spares the side of the one who made it
    budget: int = 0  # damage it can still deal before it is spent (Guardian of Faith)
    struck: set = field(default_factory=set)  # who it has already caught this turn
    # The catalogue's ground (Expansion 3 D.2), said by the spell's zone op:
    fail: str = ""  # a condition a failed save brings ("restrained" holds while it stays, "prone", "retching"...)
    rough: bool = False  # difficult terrain (Evard's tentacles, insects, sleet)
    dark: bool = False  # heavily obscured (Cloudkill, Stinking Cloud, Hunger of Hadar, Sleet Storm)
    was: dict = field(default_factory=dict)  # a wall's squares and the ground they were before it rose
    held: str = ""  # the damage a held creature takes on a failed save each turn, when it differs (Conjure Elemental)
    frees: bool = False  # a held creature's later save frees it (Conjure Elemental; tentacles need an escape)
    heal: str = ""  # friends of its owner in it are healed this much (once a turn) instead of hurt (Conjure Celestial)
    # The fourth wave's (Expansion 3 D.4):
    follows: bool = False  # it moves with its owner, `radius` squares round them (Antimagic Field)
    breaks: bool = False  # a failed save also breaks the creature's concentration (Earthquake)
    lasts: int = 0  # a failure's condition lasts this many rounds (Prismatic Wall's glare: blinded for a minute)
    stage: int = 0  # the owner's turns it has lasted (Storm of Vengeance)
    stages: list = field(default_factory=list)  # [{ops, count, rough, dark}, ...]: what each later turn brings
    cast: dict = field(default_factory=dict)  # the numbers it was cast with (dc, mod, level, up): for its stages

    @property
    def difficult(self) -> bool:
        return self.rough or self.kind in ("web", "ice", "guardians", "plants", "grease", "spikes", "overgrowth")

    @property
    def holds(self) -> bool:
        """It holds whoever it catches Restrained until it ends (a web, Entangle's plants, Evard's tentacles)."""
        return self.kind in ("web", "plants") or self.fail == "restrained"

    @property
    def opaque(self) -> bool:
        return self.dark or self.kind in ("fog", "darkness")

    @property
    def light(self) -> int:
        return 2 if self.kind == "fire" else 0


def _feigning(f) -> bool:
    """Lying as if dead (Feign Death): it does not count among those still standing."""
    return bool(f.buffs) and bool(f.buff_value("feigning"))


@dataclass
class Token:
    """A thing a spell put on the field that acts but is not a creature: a spiritual weapon, a guardian."""
    id: int
    kind: str
    x: int
    y: int
    owner: int
    rounds: int = 10
    damage: str = ""
    bonus: int = 0
    damage_type: str = "force"
    spell: str = ""


TOUCHES = ("attack", "damage", "condition", "prone", "save", "heal", "push", "vanish", "buff", "dart", "dust", "down",
           "dead", "teleport")  # (events that reach another creature: they end a Time Stop)
EXTRAPLANAR = ("aberration", "celestial", "elemental", "fey", "fiend")  # (Banishment sends them home)
GROUND_WORDS = {  # what the catalogue's ground does to whoever is caught in it (Battle._ground)
    "tentacles": "Black tentacles writhe up around {T}.",
    "cloud": "The poison fog burns {T}'s lungs.",
    "stench": "The stinking cloud rolls over {T}.",
    "hunger": "Something unseen in the black gnaws at {T}.",
    "insects": "Biting locusts swarm over {T}.",
    "sleet": "Freezing sleet lashes {T}.",
    "radiance": "Searing light and thunder fall on {T}.",
    "spirits": "Spectral beasts rake at {T}.",
    "elemental": "The elemental spirit engulfs {T}.",
    "fire": "{T} is in the flames.",
    "blades": "Whirling blades of force cut at {T}.",
    "thorns": "Needle-sharp thorns tear at {T}.",
    "celestial": "Searing light from above falls on {T}.",
    "quake": "The ground heaves and bucks under {T}.",
    "embers": "Burning embers and smoke swirl round {T}.",
    "glare": "The wall's many colours blaze in {T}'s eyes.",
}


class Fighter:
    def __init__(self, fid: int, side: str, tables, *, char: Character | None = None,
                 creature: Creature | None = None) -> None:
        self.id = fid
        self.side = side
        self.t = tables
        self.char = char
        self.creature = creature
        self.cdef = tables.creatures[creature.def_id] if creature else None
        self.x = 0
        self.y = 0
        self.z = 0  # feet above the ground (a flier aloft)
        self.max_cut = 0  # hit point maximum lost for the rest of the fight (Harm)
        self.sq = grid.footprint(self.size)
        self.initiative = 0
        self.state = "fighting"  # fighting, fleeing, down, dead, fled, surrendered
        if creature is not None and (creature.hp <= 0 or not creature.alive):
            self.state = "dead"  # (killed before the fight began: Tsunami's wave, game/stonework.py)
        self.conditions: dict[str, int] = {}  # the 2024 conditions (data/conditions.json): rounds left, -1 until ended
        self.sources: dict[str, int] = {}  # who caused a condition, where that matters (rules/engine/query.source)
        self.cond_ends: dict[str, dict] = {}  # how a condition ends, when it is timed by turns (rules/engine/durations.py)
        self.buffs: list[dict] = []
        self.death_saves = [0, 0]  # successes, failures
        self.stable = False
        self.dodging = False
        self.helped = False
        self.grovel = False  # Commanded to grovel: its next turn is spent on the ground
        self.away: dict | None = None  # sent off the field for a while (state "away"): Banishment, Blink, a sphere
        self.readied: str | None = None  # the Ready action: "reach" or "sight", until its next turn
        self.moved_feet = 0  # how far it has moved this turn (a boar's charge)
        self.attached_to: int | None = None  # a stirge fastened on someone
        self.surprised = False
        self.took_fire = False
        self.morale_checked: set[str] = set()
        self.damage_taken = 0
        self.temp_hp = 0  # temporary hit points: lost first, and they do not add up (the higher is kept)
        if char is not None and char.temp_hp:
            self.temp_hp, char.temp_hp = char.temp_hp, 0  # (an Inspiring Leader's words, brought into the fight)
        self.uncanny_used_round = -1
        self.died_round = -1
        # This turn.
        self.action = 0
        self.bonus = 0
        self.reaction = True
        self.move_left = 0
        self.attacks_left = 0
        self.dashed = False
        self.disengaged = False
        self.light_attack = False  # attacked with a light weapon this turn (two-weapon fighting)
        self.loaded_fired = False  # a Loading weapon fired in this Attack action (one shot an action, 2024)
        self.offhand_done = False  # the Light property's one extra blow this turn
        self.cast_bonus_spell = False
        self.cast_action_spell = False
        self.slot_turn: tuple | None = None  # the (round, turn) it last spent a spell slot in (one a turn, 2024)
        self.hidden = 0  # Stealth total while hidden (0: not hidden)
        self.concentration: dict | None = None  # {"spell": id, "rounds": n}
        self.save_ends: list[dict] = []  # conditions shaken off with a save at the end of each turn
        self.grappled_by: int | None = None
        self.auto = False  # the game plays this party member's turns
        self.recharge: dict[str, bool] = {}  # breath weapons: ready or not
        self.slots = list((self.cdef or {}).get("spellcasting", {}).get("slots", []))  # a creature's spell slots left
        self.spent_round = 0  # how many rounds it has been on the field (for Revivify's minute)
        self.acted = False  # has had a turn in this fight (the Cutthroat's Assassinate)
        self.glow = 0  # squares of bright light it carries (a torch, a glowing blade)
        self.jar: dict | None = None  # (Magic Jar: a body whose soul is in its gem: {host, dc, tried})
        # A creature fighting for the party (Battle.add_ally): {owner: fighter id, kind: familiar/steed, spell, level,
        # type: the creature type it has instead of its form's (a familiar's celestial, fey or fiend)}.
        self.bond: dict | None = None
        if char is not None:
            from realmwalker.rules import magic

            self.glow = int(magic.light(char) or 0)

    # ------------------------------------------------------------------ identity
    @property
    def team(self) -> str:
        """Who it fights for now: its own side, unless something has taken it over (a condition with "control":
        charmed into serving, dominated, possessed). When that ends, it is back on its own side."""
        for cid, e in self.cond_ends.items():
            if e.get("control") and e.get("control") != self.side and cid in self.conditions:
                return e["control"]
        return self.side

    @property
    def controlled(self) -> bool:
        return self.team != self.side

    @property
    def name(self) -> str:
        if self.char:
            return self.char.name.split()[0]
        return self.creature.name

    @property
    def the_name(self) -> str:
        """For prose: 'Mira', 'Wat', 'the wolf'."""
        if self.char or self.creature.named:
            return self.name
        return f"the {self.creature.name}"

    @property
    def possessive(self) -> str:
        if self.char:
            return "his" if self.char.sex == "male" else "her"
        return "its" if self.cdef["kind"] in ("beast", "undead") or self.bond is not None else "his"

    @property
    def sheet(self) -> Sheet | None:
        return Sheet(self.char, self.t) if self.char else None

    # ------------------------------------------------------------------ where
    @property
    def space(self) -> tuple[int, int, int]:
        return self.x, self.y, self.sq

    @property
    def cells(self) -> list[tuple[int, int]]:
        return grid.cells(self.x, self.y, self.sq)

    # ------------------------------------------------------------------ numbers
    @property
    def hp(self) -> int:
        return self.char.hp if self.char else self.creature.hp

    @hp.setter
    def hp(self, value: int) -> None:
        if self.char:
            self.char.hp = value
        else:
            self.creature.hp = value

    @property
    def max_hp(self) -> int:
        top = self.char.max_hp if self.char else self.creature.max_hp
        return max(1, top - self.max_cut) if self.max_cut else top

    @property
    def wounds(self) -> list:
        return self.char.wounds if self.char else self.creature.wounds

    def mod(self, ability: str) -> int:
        if self.char:
            return self.sheet.mod(ability)
        return modifier(self.cdef["abilities"][ability])

    def score(self, ability: str) -> int:
        return self.sheet.score(ability) if self.char else int(self.cdef["abilities"][ability])

    def skill(self, skill: str) -> int:
        if self.char:
            return self.sheet.skill_bonus(skill)
        ability = self.t.rules["skills"][skill]["ability"]
        return int(self.cdef.get("skills", {}).get(skill, self.mod(ability)))

    def passive(self, skill: str = "perception") -> int:
        return 10 + self.skill(skill) + sum(int(p.get(skill, 0)) for p in trs.values(self, "passive"))

    def save_bonus(self, ability: str) -> int:
        if self.char:
            return self.sheet.save_bonus(ability)
        return int(self.cdef.get("saves", {}).get(ability, self.mod(ability)))  # a 2025 block's proficient saves

    def buff_value(self, key: str) -> list:
        return [b[key] for b in self.buffs if key in b]

    @property
    def marked(self) -> bool:
        """The next attack roll against it has advantage (Guiding Bolt)."""
        return any(b.get("marked") for b in self.buffs)

    @marked.setter
    def marked(self, value: bool) -> None:
        self.buffs = [b for b in self.buffs if not b.get("marked")]
        if value:
            self.buffs.append({"marked": True, "source": "mark"})

    @property
    def no_heal(self) -> bool:
        """It cannot regain hit points just now (Chill Touch)."""
        return any(b.get("no_heal") for b in self.buffs)

    @property
    def can_opportunity(self) -> bool:
        """Whether it could make an opportunity attack now (Shocking Grasp stops it)."""
        return self.reaction and not any(b.get("no_opportunity") for b in self.buffs)

    def ac(self) -> int:
        return query.ac(self)

    @property
    def size(self) -> str:
        if self.char:
            return self.t.races[self.char.race]["size"]
        return self.cdef["size"]

    @property
    def speed(self) -> int:
        """Walking speed in feet this turn."""
        return query.speed(self)

    @property
    def fly_speed(self) -> int:
        """Flying speed in feet (0: it cannot fly); nothing that stops it moving lets it fly either."""
        if query.flag(self, "speed_zero"):
            return 0
        fly = 0 if self.char else int(self.cdef.get("speeds", {}).get("fly", 0))
        return max(fly, max([0] + [int(v) for v in self.buff_value("fly")]))

    @property
    def hovers(self) -> bool:
        return bool(self.creature and self.cdef.get("speeds", {}).get("hover"))

    def _speed_of(self, kind: str) -> int:
        if query.flag(self, "speed_zero"):
            return 0
        own = 0 if self.char else int(self.cdef.get("speeds", {}).get(kind, 0))
        if kind == "climb" and self.char is not None and (feats.has(self.char, "athlete")
                                                          or self.has_trait("second_story_work")):
            own = self.speed  # (Athlete, a thief's Second-Story Work: a Climb Speed equal to the Speed)
        # (a buff of True: a speed equal to the walking speed - Spider Climb, Alter Self's gills)
        return max(own, max([0] + [self.speed if v is True else int(v) for v in self.buff_value(kind)]))

    @property
    def climb_speed(self) -> int:
        """Climbing speed in feet: climbing costs it no extra movement (a spider, a bear)."""
        return self._speed_of("climb")

    @property
    def swim_speed(self) -> int:
        """Swimming speed in feet: swimming costs it no extra movement, and a current does not trouble it."""
        return self._speed_of("swim")

    @property
    def jump(self) -> tuple[int, int]:
        """How far it can leap, in feet: standing, and after a run of 10 feet - half its Strength score, and all of it
        (2024 Long Jump)."""
        s = self.score("str")
        if self.char is not None and self.has_trait("second_story_work"):
            s = max(s, self.score("dex"))  # (a thief leaps by Dexterity)
        leap = max([0] + [int(v) for v in self.buff_value("leap")])  # (Jump: 30 feet, standing or running)
        return max(s // 2, leap), max(s, leap)

    @property
    def shine(self) -> int:
        """Squares of bright light it carries now: a torch or a glowing blade, or a spell's light on it (Light,
        Daylight)."""
        return max([self.glow] + [int(v) for v in self.buff_value("light")])

    @property
    def darkvision(self) -> int:
        if self.char:
            return self.sheet.darkvision
        return int(self.cdef.get("darkvision", 0))

    @property
    def senses(self) -> dict[str, int]:
        """Feet of each special sense: darkvision, blindsight, truesight, tremorsense."""
        if self.char:
            tremor = max([0] + [int(v) for v in self.buff_value("tremorsense")])  # (Stonecunning)
            blind = 10 if feats.has(self.char, "blind_fighting") or feats.has(self.char, "skulker") else 0
            true = 60 if feats.has(self.char, "boon_of_truesight") else 0
            true = max([true] + [int(v) for v in self.buff_value("truesight")])  # (True Seeing)
            return {"darkvision": self.darkvision, **({"tremorsense": tremor} if tremor else {}),
                    **({"blindsight": blind} if blind else {}), **({"truesight": true} if true else {})}
        out = {**self.cdef.get("senses", {}), "darkvision": self.darkvision}
        if self.buffs and self.buff_value("truesight"):
            out["truesight"] = max([int(out.get("truesight", 0))] + [int(v) for v in self.buff_value("truesight")])
        return out

    @property
    def body(self) -> str:
        return "humanoid" if self.char else self.cdef.get("body", "humanoid")

    @property
    def kind(self) -> str:
        if self.bond is not None and self.bond.get("type"):
            return self.bond["type"]  # (a familiar in an owl's shape is a fey, a celestial or a fiend)
        return "humanoid" if self.char else self.cdef["kind"]

    @property
    def blows(self) -> bool:
        """Whether it may attack at all: a familiar cannot (PHB 2024), though it can Help and do the rest."""
        return self.bond is None or self.bond.get("kind") != "familiar"

    def has_trait(self, trait: str) -> bool:
        return trs.has(self, trait)

    @property
    def morale_type(self) -> str:
        return "fanatic" if self.char else self.cdef.get("morale", "warrior")

    @property
    def prefers_range(self) -> bool:
        """Keeps its distance and shoots (bandit archers, priests, wizards)."""
        if self.char:
            return self.char.cls == "wizard"
        ai = self.cdef.get("ai") or {}
        return ai.get("role") in ("artillery", "controller", "support") or int(ai.get("range", 0)) > 5

    # ------------------------------------------------------------------ state
    @property
    def active(self) -> bool:
        """Still in the fight (can be targeted and threatens the other side)."""
        return self.state in ("fighting", "fleeing")

    @property
    def standing(self) -> bool:
        return self.active and "unconscious" not in self.conditions

    @property
    def incapacitated(self) -> bool:
        return query.incapacitated(self)

    def can_act(self) -> bool:
        if self.jar is not None and self.jar.get("host") is None and self.state in ("fighting", "fleeing"):
            return True  # (Magic Jar: the body lies still, but the soul in its gem may act)
        return self.state in ("fighting", "fleeing") and not self.incapacitated

    def armor_factor(self, part: str) -> float:
        """How much armour on this body part reduces the chance of a real wound (1 = none)."""
        group = PART_GROUP.get(part, "torso")
        if self.char:
            it = self.char.equipped_item("helmet" if group == "head" else "armor")
            if it is None:
                return 1.0
            d = self.t.items.get(it.def_id)
            if group not in d.get("covers", []):
                return 1.0
            return ARMOR_FACTOR["helmet"] if d["category"] == "helmet" else ARMOR_FACTOR.get(d.get("armor_type", "light"), 1.0)
        for it in self.creature.inventory:
            d = self.t.items.get(it.def_id)
            if d["category"] == "armor" and group in d.get("covers", []):
                return ARMOR_FACTOR.get(d.get("armor_type", "light"), 1.0)
        return ARMOR_FACTOR["natural"] if int(self.cdef["ac"]) >= 14 else 1.0

    def armor_name(self, part: str) -> str:
        group = PART_GROUP.get(part, "torso")
        if self.char:
            it = self.char.equipped_item("helmet" if group == "head" else "armor")
            if it is not None and group in self.t.items.get(it.def_id).get("covers", []):
                return self.t.items.name(it, False)
            shield = self.char.equipped_item("off_hand")
            if shield is not None and self.t.items.category(shield) == "shield":
                return self.t.items.name(shield, False)
            return ""
        for it in self.creature.inventory:
            d = self.t.items.get(it.def_id)
            if d["category"] in ("armor", "shield"):
                return d["name"]
        return "hide" if int(self.cdef["ac"]) >= 13 and self.cdef["kind"] == "beast" else ""


@dataclass
class BattleResult:
    outcome: str
    xp: int
    dead: list[Creature]
    captives: list[Creature]
    fled: list[Creature]
    loot_money: int
    loot_items: list
    party_dead: list[Character]
    rounds: int
    robbed_money: int = 0


def spell_id(value: str) -> str:
    """The spell behind a spell-menu value (a spell id, or "scroll:<uid>:<spell id>"; a flask thrown from the Item menu
    is "throw:<uid>:<spell id>")."""
    return value.split(":", 2)[2] if value.startswith(("scroll:", "charge:", "throw:", "innate:", "wish:")) else value


def again_spell(f: Fighter, tables) -> str | None:
    """The follow-up of the spell `f` concentrates on, when it has one (Witch Bolt's later bolts, a Flame Blade's
    strikes, moving a Moonbeam): "<spell id>_again", cast without a slot (rules/spells.SpellTable)."""
    conc = f.concentration
    if conc is None:
        return None
    sid = f"{conc['spell']}_again"
    return sid if sid in tables.spells else None


BATTLE_USES = {"heal", "bandage", "throw", "coat"}  # what an item's "use" can do in a fight (do_item, or via do_cast)


def open_field(tables, width: int = 16, height: int = 10, ground: str = "grass", light: float = 1.0) -> grid.Field:
    """A plain field with nothing on it (tests, the balance numbers, and fights nobody built a field for)."""
    T = tables.terrain.index
    terrain = np.full((width, height), T.get(ground, 0), dtype=np.uint16)
    return grid.Field(tables, terrain, kind="wilderness", key="open", base_light=light, ground=ground)


class Battle:
    def __init__(self, tables, party: list[Character], foes: list[Creature], env: Env, rng: RNG, *,
                 show_dice: bool = True, title: str = "", now: int = 0, field: grid.Field | None = None,
                 spots: dict | None = None) -> None:
        self.t = tables
        self.rng = rng
        self.env = env
        self.show_dice = show_dice
        self.title = title
        self.now = now
        self.field = field if field is not None else open_field(tables, light=max(env.light, 0.0))
        self.log: list[tuple[str, str]] = []
        # What happened, for the battle screen to show (who moved where, who struck whom, hit or missed, damage,
        # healing, spells and their areas). Pure record: nothing in the rules reads it.
        self.events: list[dict] = []
        self.fighters: list[Fighter] = []
        self.zones: list[Zone] = []
        self.tokens: list[Token] = []
        self._next_zone = 1
        fid = 1
        for c in party:
            f = Fighter(fid, PARTY, tables, char=c)
            # Spells cast before the fight and still working (Stoneskin, Death Ward...) come into it with them.
            for sid in spellrules.lasting(c, tables):
                part = spellrules.battle_part(tables, sid, c)
                if part:
                    f.buffs.append(part)
            if c.uses.get("addled"):  # (Contact Other Plane's failure: Incapacitated until a long rest)
                f.conditions["incapacitated"] = -1
            if (c.spells or {}).get("jar"):  # (Magic Jar: the body lies still; the soul in the gem may act)
                f.jar = {"host": None, "dc": int(c.spells["jar"].get("dc", 13)), "tried": []}
                f.conditions["incapacitated"] = -1
            self.fighters.append(f)
            fid += 1
        if env.carried_light > 0 and self.fighters:
            self.fighters[0].glow = max(self.fighters[0].glow, int(env.carried_light))
        from realmwalker.rules.engine import conditions as cond

        for cr in foes:
            f = Fighter(fid, FOE, tables, creature=cr)
            for a in f.cdef["attacks"]:
                if a.get("recharge"):
                    f.recharge[a["name"]] = True
            # What it comes into the fight with (a Symbol on the way into the camp, game/warding.py): a sleep brought
            # in breaks on damage; "discord" is Symbol's quarrel (Disadvantage on its attacks).
            for cid, n in sorted(cr.conditions.items()):
                if cid == "discord":
                    f.buffs.append({"discord": True, "rounds": int(n), "source": "symbol"})
                elif cid in cond.table(tables):
                    durations.give(self, f, cid, rounds=int(n), **({"on_damage": True} if cid == "unconscious" else {}))
            cr.conditions.clear()
            self.fighters.append(f)
            fid += 1
        self._place(spots or {})
        self.order: list[int] = []
        self.turn = 0
        self.round = 1
        self.turn_started = False
        self.outcome: str | None = None
        self.known: set[str] = set()
        self.rolls: dict[int, list[str]] = {}  # log line -> the rolls behind it (the log's tooltips)
        self._melee_blow = False  # the damage being dealt comes from a melee attack (knocking out)
        self._rolls_waiting: list[str] = []
        self.initial_foes = len(foes)
        self.robbed_money = 0
        self.thrown: list = []  # weapons thrown during the fight, lying on the field afterwards
        self.shot: dict[str, int] = {}  # the party's arrows, bolts, needles and bullets loosed (half found after)
        self._light_key = None
        self._light = None
        self.active_round = 1  # the last round in which anyone moved, struck or cast
        # Decisions that pause the fight (rules/engine/reactions.py): a battle a person is watching runs its pieces
        # in the resolver (run), which stops where the player is asked and goes on with answer().
        self.resolver = reactions.Resolver()
        self.human = False  # someone is playing (the battle screen says so); else every decision is the game's own
        self.reactions = "ask"  # the Reactions setting: ask, all, auto

    # ------------------------------------------------------------------ decisions
    @property
    def pending_decision(self) -> Decision | None:
        return self.resolver.pending

    def run(self, fn, *args, **kwargs):
        """Run part of the battle (a step, a player's action) so that it can stop at a decision."""
        if not self.human:
            return fn(*args, **kwargs)
        return self.resolver.run(fn, *args, **kwargs)

    def answer(self, value: str):
        """The player's answer to the decision waiting (pending_decision); the battle goes on."""
        return self.resolver.answer(value)

    # ------------------------------------------------------------------ helpers
    def say(self, text: str, category: str = "info") -> None:
        if self._rolls_waiting:  # the rolls just made explain this line
            self.rolls[len(self.log)] = self._rolls_waiting[-6:]
            self._rolls_waiting = []
        self.log.append((text[:1].upper() + text[1:], category))

    def _event(self, kind: str, **data) -> None:
        self.events.append({"kind": kind, **data})
        if kind in TOUCHES and self.__dict__.get("_time_stop") is not None:
            other = data.get("to") if "to" in data else data.get("who")
            if other is not None and other != self._time_stop:
                self._time_broken = True
        if kind in ACTIVITY:
            self.active_round = self.round

    def dice_say(self, text: str) -> None:
        """A roll: kept for the next line of the log (its tooltip), and shown as a line itself if dice are shown."""
        if self.show_dice:
            self._rolls_waiting = []  # (shown as a line of its own: the next line need not repeat it)
            self.log.append((text, "dice"))
            return
        self.note_roll(text)

    def note_roll(self, text: str) -> None:
        """A roll told only in the tooltip of the line that follows (damage and what changed it)."""
        self._rolls_waiting.append(text)

    def fighter(self, fid: int) -> Fighter:
        return next(f for f in self.fighters if f.id == fid)

    @property
    def current(self) -> Fighter:
        return self.fighter(self.order[self.turn])

    def side(self, side: str) -> list[Fighter]:
        """Everyone who started on a side (the party, the foes)."""
        return [f for f in self.fighters if f.side == side]

    def team(self, team: str) -> list[Fighter]:
        """Everyone fighting for a side now (a dominated companion is on the foes' team)."""
        return [f for f in self.fighters if f.team == team]

    def enemies_of(self, f: Fighter) -> list[Fighter]:
        # (one lying as if dead under Feign Death is taken for dead: nobody aims at it, though an area still catches it)
        return [x for x in self.fighters if x.team != f.team and x.active and not (x.buffs and x.buff_value("feigning"))]

    def allies_of(self, f: Fighter) -> list[Fighter]:
        return [x for x in self.fighters if x.team == f.team and x.active]

    def on_field(self) -> list[Fighter]:
        """Everyone still taking up room: the living, the fallen and the yielded (not the dead or the fled), and one
        sealed in a sphere where it stands."""
        return [f for f in self.fighters if f.state in ("fighting", "fleeing", "down", "surrendered")
                or f.state == "away" and f.away and f.away.get("stays")]

    def at(self, x: int, y: int) -> Fighter | None:
        for f in self.on_field():
            if f.x <= x < f.x + f.sq and f.y <= y < f.y + f.sq:
                return f
        return None

    def pending_party(self) -> Fighter | None:
        if self.outcome is not None or not self.order:
            return None
        f = self.current
        if f.side == PARTY and not f.controlled and self.turn_started and f.can_act() and not f.surprised and not f.auto:
            return f
        if self.ridden(f) and self.turn_started and f.can_act() and not f.surprised:
            return f  # (Magic Jar: the player's soul in a foe's body)
        return None

    def gap(self, a: Fighter, b: Fighter) -> int:
        """Squares between two creatures, height included (the 5-5-5 grid: the larger of across and up)."""
        return max(grid.gap(a.space, b.space), abs(a.z - b.z) // grid.SQUARE_FT)

    def feet(self, a: Fighter, b: Fighter) -> int:
        return self.gap(a, b) * grid.SQUARE_FT

    def gap_from(self, f: Fighter, sq: tuple[int, int], t: Fighter) -> int:
        """Squares from `f` standing (or flying, at its height) on `sq` to `t`, height included."""
        return max(grid.gap((sq[0], sq[1], f.sq), t.space), abs(f.z - t.z) // grid.SQUARE_FT)

    # ------------------------------------------------------------------ placing everyone
    def _place(self, spots: dict) -> None:
        """Everyone onto the field: where the arena said (spots: fighter index -> (x, y), party first, then the
        foes in the order given), else in two lines facing each other across it."""
        taken: set = set()
        party = self.side(PARTY)
        foes = self.side(FOE)
        W, H = self.field.width, self.field.height
        for i, f in enumerate(self.fighters):
            want = spots.get(i)
            if want is None:
                spread = (0, 1, -1, 2, -2, 3, -3, 4, -4)
                if f.side == PARTY:
                    k = party.index(f)
                    want = (2 - (1 if f.prefers_range else 0), H // 2 + spread[k % len(spread)])
                else:
                    k = foes.index(f)
                    want = (W - 2 - f.sq + (1 if f.prefers_range else 0), H // 2 + spread[k % len(spread)])
            f.x, f.y = self._free_near(want, f.sq, taken)
            taken |= set(f.cells)

    # ------------------------------------------------------------------ allies: familiars and steeds (Expansion 3 F)
    def add_ally(self, creature: Creature, owner: Fighter, kind: str, *, spell: str = "", level: int = 0,
                 type_: str = "", cdef: dict | None = None, point: tuple[int, int] | None = None) -> Fighter:
        """A creature that fights on `owner`'s side (a familiar, a steed, a summoned spirit): on the nearest free
        squares beside its owner (or to `point`), at once. In a fight already under way a familiar rolls its own
        Initiative and joins the order by it (its turn comes next round if its place has passed); anything else takes
        its turn right after its owner's (PHB 2024)."""
        f = Fighter(max((x.id for x in self.fighters), default=0) + 1, owner.side, self.t, creature=creature)
        if cdef is not None:
            f.cdef = cdef  # (its numbers for its slot: allies.steed_def, allies.summon_def)
            f.sq = grid.footprint(f.size)  # (an animated object's size: Medium, Large or Huge)
        f.slots = list(f.cdef.get("spellcasting", {}).get("slots", []))
        f.bond = {"owner": owner.id, "kind": kind, "spell": spell, "level": int(level), "type": type_}
        for a in f.cdef["attacks"]:
            if a.get("recharge"):
                f.recharge[a["name"]] = True
        taken = {c for x in self.on_field() for c in x.cells}
        f.x, f.y = self._free_near(point if point is not None else (owner.x + owner.sq, owner.y), f.sq, taken)
        f.z = 0
        self.fighters.append(f)
        if self.order:
            if kind == "familiar":
                bonus = int(f.cdef.get("initiative", f.mod("dex")))
                f.initiative = dice.d20(self.rng).natural + bonus
                at = next((i for i, fid in enumerate(self.order) if self.fighter(fid).initiative < f.initiative),
                          len(self.order))
                self.order.insert(at, f.id)
                if at <= self.turn:
                    self.turn += 1  # (its place has passed this round: it acts next round)
            else:
                f.initiative = owner.initiative
                at = self.order.index(owner.id) + 1 if owner.id in self.order else len(self.order)
                self.order.insert(at, f.id)
                if at <= self.turn:
                    self.turn += 1
        self._event("appear", who=f.id)
        return f

    def _clear_bonded(self, x: Fighter) -> None:
        """A summoned or bonded creature gone: the ground and tokens it laid go with it (a fey spirit's darkness)."""
        for z in [z for z in self.zones if z.owner == x.id]:
            self._remove_zone(z)
        for tok in [t for t in self.tokens if t.owner == x.id]:
            self.tokens.remove(tok)
            self._event("token_end", id=tok.id)

    def allies_of_owner(self, owner: Fighter) -> list[Fighter]:
        return [x for x in self.fighters if x.bond is not None and x.bond.get("owner") == owner.id]

    def dismiss(self, x: Fighter, quiet: bool = False) -> None:
        """A summoned creature leaves the field for good, leaving nothing (the spell that held it ended)."""
        events.emit(self, "dismissed", target=x)  # (a demon spirit's Death Throes, Expansion 3 F.3)
        self._release(x)
        self._clear_bonded(x)
        x.state = "dead"
        x.hp = 0
        x.conditions = {}
        if x.creature is not None:
            x.creature.alive = False
        self._event("vanish", who=x.id)
        if not quiet:
            self.say(f"{x.the_name[:1].upper() + x.the_name[1:]} fades away.", "magic")

    def _bond_order(self) -> None:
        """A steed's turn comes right after its owner's, whatever it rolled (it shares the owner's count)."""
        for f in [x for x in self.fighters if x.bond is not None and x.bond.get("kind") != "familiar"]:
            owner = f.bond["owner"]
            if owner in self.order and f.id in self.order:
                self.order.remove(f.id)
                self.order.insert(self.order.index(owner) + 1, f.id)
                f.initiative = self.fighter(owner).initiative

    def _free_near(self, want: tuple[int, int], size: int, taken: set) -> tuple[int, int]:
        """The nearest place (by walking, then as the crow flies) where a creature of this size can stand."""
        fld = self.field
        wx = max(0, min(fld.width - size, int(want[0])))
        wy = max(0, min(fld.height - size, int(want[1])))
        best, best_d = None, None
        for r in range(0, max(fld.width, fld.height)):
            for x in range(wx - r, wx + r + 1):
                for y in range(wy - r, wy + r + 1):
                    if max(abs(x - wx), abs(y - wy)) != r:
                        continue
                    if not fld.fits(x, y, size) or any(c in taken for c in grid.cells(x, y, size)):
                        continue
                    d = (x - wx) ** 2 + (y - wy) ** 2
                    if best_d is None or d < best_d:
                        best, best_d = (x, y), d
            if best is not None:
                return best
        return wx, wy

    # ------------------------------------------------------------------ start
    def start(self, intro: str = "") -> None:
        """Initiative, the 2024 way: a Dexterity check, at a disadvantage for the surprised (they still act)."""
        linked = {s: sum(1 for f in self.fighters if f.side == s and f.buff_value("linked")) for s in (PARTY, FOE)}
        for f in self.fighters:
            if self.env.surprised == f.side and not (f.buff_value("linked") and linked[f.side] >= 2):
                f.surprised = True  # (minds linked by Rary's Telepathic Bond: one warning reaches them all)
            r = query.initiative_roll(f)
            bonus = int(f.cdef["initiative"]) if f.cdef and "initiative" in f.cdef else f.mod("dex")
            bonus += query.initiative_bonus(f)  # (Alert)
            f.initiative = (dice.d20(self.rng, advantage=r.advantage, disadvantage=r.disadvantage).natural + bonus
                            + query.d20_penalty(f))
        self.order = [f.id for f in sorted(self.fighters, key=lambda f: (-f.initiative, -f.mod("dex"), self.rng.random()))]
        self._bond_order()
        events.emit(self, "battle_start")  # (Improve Fate comes back with the initiative)
        if intro:
            self.say(intro, "danger")
        if self.env.surprised == FOE:
            self.say("You have caught them unawares.", "good")
        elif self.env.surprised == PARTY:
            self.say("They are on you before you can draw.", "danger")
        self._known_from_before()
        order = ", ".join(self.fighter(i).name for i in self.order)
        self.say(f"Order of battle: {order}.", "system")
        for f in self.side(PARTY):
            self._contingency(f, "start")  # (a spell that waited for the fight)
        self._check_end()  # (a band drowned to the last before it began: Tsunami)

    def _known_from_before(self) -> None:
        """What the party has killed before, it knows (the rest is learned with the Study action, 2024)."""
        killed = {name for f in self.side(PARTY) if f.char for name in f.char.kills}
        for def_id in sorted({f.creature.def_id for f in self.side(FOE)}):  # sorted: a set's order changes per run
            if self.t.creatures[def_id]["name"] in killed:
                self.known.add(def_id)

    def study_dc(self, f: Fighter) -> int:
        """How hard a creature is to call to mind (data/rules.json "study"): harder the more dangerous it is."""
        dc = (self.t.rules.get("study") or {}).get("dc") or {"base": 10, "per_cr": 0.5, "max": 25}
        return min(int(dc["max"]), int(dc["base"] + float(f.cdef["cr"]) * float(dc["per_cr"])))

    def study_skill(self, f: Fighter) -> str:
        return ((self.t.rules.get("study") or {}).get("skills") or {}).get(f.cdef["kind"], "arcana")

    def do_study(self, f: Fighter, target: Fighter, *, bonus: bool = False) -> None:
        """The Study action (2024): an Intelligence check - Arcana, History, Nature or Religion by what it is - to call
        to mind what a kind of creature is and what it can do."""
        if target.creature is None or not self._spend(f, bonus):
            return
        d = target.cdef
        skill = self.study_skill(target)
        dc = self.study_dc(target)
        roll = dice.d20(self.rng).natural
        bonus = f.skill(skill)
        self.dice_say(f"{self.t.rules['skills'][skill]['name']} ({f.name}): {roll} {signed_mod(bonus)} = {roll + bonus} vs DC {dc}")
        if roll + bonus < dc:
            self.say(f"{f.the_name} cannot place {target.the_name}.", "system")
        else:
            self.known.add(target.creature.def_id)
            self.say(f"{f.the_name} knows {d['plural']}: {self.what_is_known(target)}.", "info")
        self._after_action(f)

    def what_is_known(self, f: Fighter) -> str:
        """What studying a creature tells: how hard to hit and to kill, and what it shrugs off."""
        d = f.cdef
        bits = [f"AC {d['ac']}", f"about {d.get('hp_avg') or f.max_hp} hit points"]
        for key, word in (("immune", "immune to"), ("resist", "resists"), ("vulnerable", "hurt most by")):
            if d.get(key):
                bits.append(f"{word} {', '.join(d[key])}")
        if d.get("condition_immune"):
            bits.append(f"never {', '.join(d['condition_immune'])}")
        named = [self.t.traits["traits"][t]["name"] for t in d.get("traits", []) if t in self.t.traits["traits"]
                 and self.t.traits["traits"][t].get("where") != "sheet"]
        if named:
            bits.append(", ".join(named))
        return "; ".join(bits)

    # ------------------------------------------------------------------ Search and Ready (2024)
    def do_search(self, f: Fighter, *, bonus: bool = False) -> None:
        """The Search action: a Wisdom (Perception) check against everyone hiding; whoever it beats is found."""
        if not self._spend(f, bonus):
            return
        roll = dice.d20(self.rng).natural
        total = roll + f.skill("perception")
        self.dice_say(f"Perception ({f.name}): {roll} {signed_mod(f.skill('perception'))} = {total}")
        found = [e for e in self.enemies_of(f) if e.hidden and e.hidden <= total]
        for e in found:
            e.hidden = 0
            self._event("found", who=e.id)
        self.say(f"{f.the_name} finds {', '.join(e.the_name for e in found)}." if found
                 else f"{f.the_name} looks hard, and finds nobody.", "good" if found else "system")
        self._after_action(f)

    def do_ready(self, f: Fighter, trigger: str) -> None:
        """The Ready action: wait with a blow for "reach" (an enemy coming within reach) or "sight" (an enemy coming
        into range and sight), and strike then with the reaction, until the start of the next turn."""
        if trigger not in ("reach", "sight") or not self._spend(f):
            return
        f.readied = trigger
        self.say(f"{f.the_name} waits, " + ("weapon ready for the first to come close." if trigger == "reach"
                                             else "an arrow on the string for the first to show."), "system")
        self._after_action(f)

    def _readied(self, mover: Fighter) -> None:
        """Whoever was waiting for this strikes now."""
        for r in [x for x in self.fighters if x.readied and x.team != mover.team and x.reaction and x.can_act()]:
            if not mover.active:
                return
            melee = r.readied == "reach"
            opts = [o for o in self.attack_options(r) if o.available and o.is_melee == melee and self.in_reach(r, o, mover)[0]]
            if not opts or not self.can_see(r, mover):
                continue
            r.readied = None
            r.reaction = False
            self.say(f"{r.the_name} was waiting for that.", "warn")
            self._attack(r, max(opts, key=lambda o: _avg(o.damage) + o.bonus), mover)
            self._check_end()

    # ------------------------------------------------------------------ turn engine
    def step(self) -> bool:
        """Advance the battle by one automatic event. False when the player must choose."""
        if self.outcome is not None:
            return False
        f = self.current
        if not self.turn_started:
            self.turn_started = True
            self._start_of_turn(f)
            if self.outcome is not None:
                return True
            if self._waits_for_word(f):  # (Animate Objects: uncommanded, it takes the Dodge action)
                self.end_turn()
                return True
        if f.__dict__.pop("lost_turn", False):  # (Maze: the turn spent finding the way out)
            self.end_turn()
            return True
        if f.surprised:
            f.surprised = False  # (2024: surprise costs only initiative; the Cutthroat still strikes them hard first)
        if f.grovel and f.can_act():
            f.grovel = False
            f.conditions["prone"] = -1
            self._event("prone", who=f.id)
            self.say(f"{f.the_name} throws {f.possessive if f.char else 'itself'} to the ground, as commanded.", "system")
            self.end_turn()
            return True
        if not f.can_act():
            if f.state == "fighting" and ("stunned" in f.conditions or "paralyzed" in f.conditions):
                self.say(f"{f.the_name} cannot move.", "system")
            self.end_turn()
            return True
        self._unseal_the_last(f)  # (only foes it has sealed away are left: it lets them go)
        if marks.dancing_turn(self, f):  # (Otto's Irresistible Dance: its turn spent collecting itself)
            if self.outcome is None and self.turn_started and self.current is f:
                self.end_turn()
            return True
        if marks.confused_turn(self, f):  # (Confusion: the d10 says what it does with its turn)
            if self.outcome is None and self.turn_started and self.current is f:
                self.end_turn()
            return True
        if f.side == PARTY and not f.controlled and not f.auto or self.ridden(f):
            return False
        from realmwalker.rules import tactics

        tactics.take_turn(self, f)
        if self.outcome is None and self.turn_started and self.current is f:
            self.end_turn()
        return True

    def _start_of_turn(self, f: Fighter) -> None:
        self._rolls_waiting = []  # a roll that explained nothing (a check with no line after it) is not carried over
        extra = f.__dict__.pop("extra_turn", False)  # (a turn in a stopped time: no time passes)
        if not extra:
            durations.tick(self, f, "turn_start")  # what lasts "until the start of its next turn" ends
            marks.turn_start(self, f)  # (Heroism; harm at the start of a turn)
        f.readied = None
        if f.creature is not None and f.cdef.get("legendary"):
            f.creature.uses["legendary_actions"] = int(f.cdef["legendary"].get("uses", 3))
        f.dodging = False
        f.action, f.bonus, f.reaction = 1, 1, True
        f.attacks_left = 0
        f.dashed = f.disengaged = f.light_attack = f.offhand_done = False
        if f.creature is not None and (f.fly_speed > 0 and f.has_trait("flyby") or f.has_trait("agile")):
            f.disengaged = True  # (Flyby, Agile: an owl or a rat slips out of reach and nobody gets a blow at it)
        f.cast_bonus_spell = f.cast_action_spell = False
        if f.creature is not None:
            for a in f.cdef["attacks"]:
                if a.get("with_multiattack"):
                    f.recharge[a["name"]] = True  # (a draconic spirit's breath: every turn, with its Rends)
        f.moved_feet = 0
        f.__dict__["turn_start_at"] = (f.x, f.y)  # (Charger: how far they ran at a foe)
        f.spent_round += 1
        for b in list(f.buffs) if not extra else ():
            if "rounds" in b:
                b["rounds"] -= 1
                if b["rounds"] < 0:
                    f.buffs.remove(b)
        f.move_left = f.speed
        marks.after_turn_start(self, f)  # (Slow: no bonus action)
        if self.__dict__.get("risings"):
            self._rise_as_zombies(f)  # (Finger of Death: the slain rise as its caster's turn begins)
        if extra:  # (Time Stop: a fresh turn, but nothing wears down, nothing burns, nothing bleeds)
            self._follow_auras()
            if f.active:
                f.move_left = max(f.speed, f.fly_speed)
                self._stand_up(f)
            return
        if f.concentration is not None and f.concentration.get("rounds", -1) >= 0:
            f.concentration["rounds"] -= 1
            if f.concentration["rounds"] < 0:
                self._end_concentration(f, quiet=False, why="runs its course")
        for z in [z for z in self.zones if z.owner == f.id and z.rounds >= 0]:
            z.rounds -= 1
            if z.rounds < 0:
                self._remove_zone(z)
        for z in [z for z in self.zones if z.owner == f.id and z.stages]:
            self._storm_turn(f, z)  # (Storm of Vengeance: what each later turn brings)
            if self.outcome is not None:
                return
        for tok in [t for t in self.tokens if t.owner == f.id and t.rounds >= 0]:
            tok.rounds -= 1
            if tok.rounds < 0:
                self.tokens.remove(tok)
                self._event("token_end", id=tok.id)
        for z in self.zones:
            z.struck.discard(f.id)
        if f.state == "away" and (f.away or {}).get("why") == "blink":
            self.bring_back(f)  # (Blink: back from the Ethereal Plane at the start of its turn)
        if f.state == "away" and (f.away or {}).get("escape"):
            self._maze_turn(f)  # (Maze: its turn goes on looking for the way out)
        self._follow_auras()
        if f.state == "down":
            if not f.stable:
                self._death_save(f)
            return
        if not f.active:
            return
        events.emit(self, "turn_start", actor=f)  # regeneration...
        f.took_fire = False
        for name in list(f.recharge):
            if not f.recharge[name] and self.rng.randint(1, 6) >= 5:
                f.recharge[name] = True
        if f.char and f.state == "fighting" and "stunned" not in f.conditions:
            from realmwalker.rules import health

            if health.concussed(f.char) and self.rng.chance(0.06):
                f.conditions["stunned"] = 1
                self.say(f"{f.the_name}'s sight swims and goes dark for a moment.", "danger")
            elif health.pain(f.char, self.t) >= 15 and not self._save(f, "con", 10, quiet=True):
                f.conditions["stunned"] = 1
                self.say(f"The pain is too much: {f.the_name} can only gasp.", "danger")
        # Whatever lies where they stand: fire, a web, the guardians' wrath.
        self._zones_on(f, start=True)
        if not f.active:
            return
        if f.attached_to is not None:  # a stirge drinking
            prey = next((x for x in self.fighters if x.id == f.attached_to), None)
            if prey is None or not (prey.active or prey.state == "down") or self.gap(f, prey) > 1:
                f.attached_to = None
            else:
                drink = next((e for a in f.cdef.get("attacks", []) for e in a.get("on_hit", [])
                              if e.get("op") == "damage" and e.get("when")), None)
                if drink:
                    self.say(f"{f.the_name} drinks from {prey.the_name}.", "danger" if prey.side == PARTY else "info")
                    self._hit(f, prey, dice.roll(drink["damage"], self.rng).total, drink.get("type", "necrotic"),
                              crit=False, weapon=drink.get("type", "drain"))
        if any(bf.get("burning") for bf in f.buffs):  # (the Burning hazard, 2024)
            dmg, dtype = hazards.burning_damage(self.t)
            self.say(f"{f.the_name} is burning.", "danger" if f.side == PARTY else "info")
            self._hit(None, f, dice.roll(dmg, self.rng).total, dtype, crit=False, weapon="flames")
            if not f.active:
                return
        # Bleeding wounds cost hit points each round.
        bleed = sum(w.bleed for w in f.wounds if not w.bandaged)
        if bleed and f.hp > 0:
            loss = max(1, bleed // 2)
            self.say(f"{f.the_name} is bleeding.", "danger")
            self._apply_hp_loss(f, loss, source=None, cause="blood loss")
            if not f.active:
                return
        for cond in list(f.conditions):
            if cond == "prone":
                continue
            if f.conditions[cond] > 0:
                f.conditions[cond] -= 1
                if f.conditions[cond] == 0:
                    del f.conditions[cond]
                    if cond in ("stunned", "restrained", "frightened", "paralyzed"):
                        self.say(f"{f.the_name} is no longer {cond}.", "system")
        f.move_left = max(f.speed, f.fly_speed) if f.jar is None else 0  # (Magic Jar: the body lies still)
        if any(z.kind == "guardians" and z.owner is not None and any(c in z.cells for c in f.cells)
               and self.fighter(z.owner).team != f.team for z in self.zones) and not self.antimagic(f.cells):
            f.move_left //= 2  # Spirit Guardians: half speed in the emanation (2024)
        self._stand_up(f)

    def _stand_up(self, f: Fighter) -> None:
        """Standing up from the ground costs half your movement."""
        rise = 5 if f.char is not None and feats.has(f.char, "athlete") else f.speed // 2  # (Athlete: Hop Up)
        if "prone" in f.conditions and f.can_act() and f.state == "fighting" and f.move_left >= rise > 0:
            del f.conditions["prone"]
            f.move_left -= rise
            self.say(f"{f.the_name} gets up.", "system")
            self._event("stand", who=f.id)

    def _end_of_turn(self, f: Fighter) -> None:
        for se in list(f.save_ends):
            if se["cond"] not in f.conditions:
                f.save_ends.remove(se)
                continue
            if se.get("tally") is not None:  # (Flesh to Stone: three of a kind, successes or failures)
                self._stone_save(f, se)
                continue
            if self._save(f, se["save"], se["dc"], against=(se["cond"],)):
                f.conditions.pop(se["cond"], None)
                f.save_ends.remove(se)
                self.say(f"{f.the_name} shakes off the spell.", "system")
        if f.hidden and f.active and any(self.gap(e, f) <= 1 for e in self.enemies_of(f) if e.standing):
            f.hidden = 0
            self.say(f"{f.the_name} is found.", "system")
        marks.turn_end(self, f)  # (Melf's Acid Arrow; marks shaken off with a save)
        for z in [z for z in self.zones if z.kind == "grease" and any(c in z.cells for c in f.cells)]:
            if f.active and f.z == 0 and "prone" not in f.conditions:
                z.struck.discard(f.id)
                self._zone_underfoot(f, z)  # (ending a turn on the grease)
        durations.tick(self, f, "turn_end")  # and what lasts "until the end of its next turn"
        self._crowded(f)

    def _stone_save(self, f: Fighter, se: dict) -> None:
        """Flesh to Stone, Prismatic Spray's indigo ray: a save at the end of each of its turns while it is held; three
        successes free it, three failures turn it to stone (Petrified for as long as the spell lasts, for good from an
        instant one). They need not come in a row."""
        ok = self._save(f, se["save"], se["dc"], against=("petrified",))
        se["tally"][0 if ok else 1] += 1
        good, bad = se["tally"]
        self.dice_say(f"{f.name} against the stone: {good} saved, {bad} failed")
        if good >= 3:
            f.conditions.pop(se["cond"], None)
            f.save_ends.remove(se)
            self.say(f"The grey drains out of {f.the_name}'s skin: the stone has lost its grip.", "system")
        elif bad >= 3:
            f.conditions.pop(se["cond"], None)
            f.save_ends.remove(se)
            if durations.give(self, f, "petrified", rounds=None if se.get("conc") is not None else -1,
                              **({"conc": se["conc"]} if se.get("conc") is not None else {})):
                self._event("condition", who=f.id, cond="petrified")
                self.say(f"{f.the_name} turns to stone.", "good" if f.side == FOE else "danger")
        else:
            self.say(f"{f.the_name}'s limbs stiffen, grey as granite.", "good" if f.side == FOE else "danger")

    def _crowded(self, f: Fighter) -> None:
        """Ending a turn in another creature's space (stopped on the way through it) leaves you Prone, unless you are
        Tiny or the larger of the two (PHB 2024, Movement and Position). Nobody chooses to stop there."""
        from realmwalker.rules.engine.statblocks import SIZE_ORDER

        if "prone" in f.conditions or f.size == "tiny" or f.z or f.state not in ("fighting", "fleeing", "surrendered"):
            return
        mine = set(f.cells)
        for x in self.on_field():
            if x is not f and not x.z and mine & set(x.cells) and SIZE_ORDER.index(f.size) <= SIZE_ORDER.index(x.size):
                f.conditions["prone"] = -1
                self._event("prone", who=f.id)
                self.say(f"{f.the_name} is left crowded into the space of {x.the_name}, and goes down in the press.",
                         "system")
                return

    def end_turn(self) -> None:
        if self.outcome is not None:
            return
        f = self.current
        f.acted = True
        self._end_of_turn(f)
        self._check_end()
        if self.outcome is not None:
            return
        self._legendary_window(f)
        if self.outcome is not None:
            return
        if self._more_time(f):  # (Time Stop: another turn, and nobody else moves)
            self.turn_started = False
            return
        self.turn += 1
        if self.turn >= len(self.order):
            self.turn = 0
            self.round += 1
            if any(x.state == "away" for x in self.fighters):
                self.active_round = self.round  # (someone sent away is coming back: not a stand-off)
            if self.round - self.active_round > QUIET_ROUNDS:
                self._break_off()
        self.turn_started = False

    def _break_off(self) -> None:
        """Neither side can get at the other (a gulf, a locked door, a stand-off in the dark): it ends there."""
        self.say("Neither side can come at the other, and in the end the fight simply breaks off.", "system")
        for f in self.side(FOE):
            if f.active:
                f.state = "fled"
                self._event("leave", who=f.id)
        self.outcome = "parley"

    def _check_end(self) -> None:  # (by team: a companion fighting for the enemy is an enemy until freed)
        for f in self.fighters:
            blinked = f.state == "away" and (f.away or {}).get("why") == "blink"  # (on the Ethereal Plane, still free)
            if f.concentration is not None and (query.flag(f, "breaks_concentration") or not f.active) and not blinked:
                self._end_concentration(f, quiet=not f.active, why="is lost")  # incapacitated (2024)
            if f.z > 0 and not f.hovers and ("prone" in f.conditions or f.incapacitated or f.state == "down"
                                             or f.fly_speed <= 0) and not f.buff_value("aloft"):
                self._fall(f)
        foes = [f for f in self.team(FOE) if f.bond is None and (
            f.active and "unconscious" not in f.conditions and not _feigning(f) or f.state == "away")]
        # (an ally alone - a familiar, a steed - does not keep a fight going when every one of the party is down)
        party = [f for f in self.team(PARTY) if f.bond is None and (
            f.active and "unconscious" not in f.conditions and not _feigning(f) or f.state == "away")]
        if not foes:
            self.outcome = "victory"
        elif not party:
            gone = any(f.state == "fled" for f in self.side(PARTY))
            self.outcome = "fled" if gone else "defeat"
        if self.outcome is not None:
            self._jar_release()

    # ------------------------------------------------------------------ light and sight
    def light(self) -> np.ndarray:
        """How lit each square is now: the field's own light, what people carry, and anything burning."""
        carriers = [(f.x + f.sq // 2, f.y + f.sq // 2, f.shine) for f in self.fighters
                    if f.shine and f.state in ("fighting", "fleeing", "down")]
        fires = [(x, y, 1) for z in self.zones if z.kind in ("fire", "lights") for (x, y) in z.cells]
        key = (tuple(carriers), tuple(fires), self.field.version)
        if key != self._light_key:
            self._light_key = key
            self._light = self.field.light_map(carriers + fires)
        return self._light

    def light_on(self, f: Fighter) -> float:
        L = self.light()
        return float(max(L[x, y] for x, y in f.cells if self.field.in_bounds(x, y)))

    def can_see(self, a: Fighter, b: Fighter) -> bool:
        """Whether `a` can see `b`: a line of sight, light enough (or darkvision close enough), not hidden, not
        invisible. Blindsight sees everything near that is not behind total cover; truesight sees the invisible and
        through any darkness (2024)."""
        if a.incapacitated and not (a.jar is not None and a.jar.get("host") is None):
            return False  # (a soul in its gem sees from where the gem is: Magic Jar)
        feet = self.feet(a, b)
        senses = a.senses
        if senses.get("blindsight", 0) >= feet and self.field.cover(a.space, b.space) != grid.TOTAL:
            return True
        if senses.get("tremorsense", 0) >= feet and a.z == 0 and b.z == 0:
            return True  # Tremorsense: anything touching the same ground, through darkness and walls alike (2024)
        if "blinded" in a.conditions:
            return False
        if max(a.buff_value("sense_thoughts"), default=0) >= feet and self.thinks(b) \
                and self.field.cover(a.space, b.space) != grid.TOTAL:
            return True  # (Detect Thoughts: a thinking mind near is known where it is, invisible or hidden)
        if query.flag(b, "unseen") and senses.get("truesight", 0) < feet and not a.buff_value("see_invisible"):
            return False  # Invisible (See Invisibility sees it as if it were not)
        if b.hidden and b.hidden > a.passive() - (5 if self.dim_for(a, b) else 0) and self.gap(a, b) > 1:
            return False
        if self._devils_sight(a, b, feet):
            return True  # (a devil spirit: magical darkness does not stop its darkvision)
        if any(self.field.zone_opaque[x, y] for x, y in b.cells) and self.gap(a, b) > 1:
            return False
        if self.field.cover(a.space, b.space) == grid.TOTAL:
            return False
        if self.light_on(b) >= grid.DIM or senses.get("truesight", 0) >= feet:
            return True
        return a.darkvision > 0 and feet <= a.darkvision

    def _devils_sight(self, a: Fighter, b: Fighter, feet: int) -> bool:
        """Devil's Sight: within its darkvision, magical darkness hides nothing from it (fog and walls still do)."""
        if a.creature is None or feet > a.darkvision or not a.has_trait("devils_sight"):
            return False
        ax, ay, bx, by = (a.x + a.sq / 2 - 0.01, a.y + a.sq / 2 - 0.01, b.x + b.sq / 2 - 0.01, b.y + b.sq / 2 - 0.01)
        line = set(grid.crossed(ax, ay, bx, by)) | set(b.cells)  # (centres a hair inside a square: a Large one's
        if any(z.opaque and not z.dark and line & z.cells for z in self.zones):  # falls on a line between four)
            return False  # (a fog cloud)
        return self.field.line_clear(ax, ay, bx, by, set(a.cells) | set(b.cells), terrain_only=True)

    def thinks(self, f: Fighter) -> bool:
        """A mind Detect Thoughts can sense: a person, or a creature that knows a language (and is not warded by
        Nondetection)."""
        if f.buff_value("nondetection"):
            return False
        return f.char is not None or bool((f.cdef or {}).get("languages"))

    def dim_for(self, a: Fighter, b: Fighter) -> bool:
        """Whether `b` stands lightly obscured to `a`'s eyes: dim light, or darkness seen by darkvision (2024)."""
        lit = self.light_on(b)
        if lit >= grid.BRIGHT:
            return False
        if lit >= grid.DIM:
            return not (a.darkvision > 0 and self.feet(a, b) <= a.darkvision)
        return a.darkvision > 0 and self.feet(a, b) <= a.darkvision

    def cover(self, a: Fighter, b: Fighter) -> int:
        others = {c: x.id for x in self.on_field() if x is not a and x is not b and x.state != "dead" for c in x.cells}
        return self.field.cover(a.space, b.space, others)

    def can_see_point(self, f: Fighter, x: int, y: int) -> bool:
        return self.field.in_bounds(x, y) and self.field.cover(f.space, (x, y, 1)) != grid.TOTAL

    # ------------------------------------------------------------------ moving
    def threats(self, f: Fighter) -> list[tuple[int, tuple[int, int, int], int]]:
        """Who would get an opportunity attack on `f` for leaving their reach: (id, space, reach in squares)."""
        out = []
        if f.disengaged:
            return out
        for e in self.enemies_of(f):
            if not e.standing or not e.can_opportunity or e.incapacitated or e.state != "fighting" or self.frozen(e):
                continue
            r = self.reach_of(e)
            if r:
                out.append((e.id, e.space, r))
        return out

    def reach_of(self, f: Fighter) -> int:
        """How many squares this fighter's melee reaches (0 if it has nothing to strike with)."""
        key = (f.id, self.round, self.turn)
        cache = self.__dict__.setdefault("_reach_cache", {})
        if key not in cache:
            melee = [o for o in self.attack_options(f) if o.is_melee and o.available]
            if len(cache) > 400:
                cache.clear()
            cache[key] = max((o.reach_sq for o in melee), default=0)
        return cache[key]

    def move_tree(self, f: Fighter, budget: int | None = None, *, risk: float = 0.5, through: set | None = None) -> dict:
        blocked, occupied = set(), set()
        for x in self.on_field():
            if x is f:
                continue
            hostile = x.team != f.team and x.state in ("fighting", "fleeing", "surrendered")
            if hostile and x.size in SIZES and f.size in SIZES:
                apart = SIZES.index(x.size) - SIZES.index(f.size)
                if abs(apart) >= 2 or apart >= 1 and f.has_trait("halfling_nimbleness"):
                    hostile = False  # slipped past (through, never stopping there)
            for c in x.cells:
                (blocked if hostile else occupied).add(c)
        fire = {c for z in self.zones if z.kind == "fire" for c in z.cells}
        if budget is None:
            budget = f.move_left // 2 if self.dragging(f) else f.move_left
        return grid.paths(self.field, (f.x, f.y), f.sq, budget, blocked=blocked,
                          occupied=occupied, threats=self.threats(f), risk=risk, crawling="prone" in f.conditions,
                          hazard=fire, flying=f.fly_speed > 0, climber=f.climb_speed > 0, swimmer=f.swim_speed > 0,
                          jump=(0, 0) if "prone" in f.conditions or self.held_by(f) or self.dragging(f) else f.jump,
                          through=through)

    def occupied_by_others(self, f: Fighter) -> set:
        return {c for x in self.on_field() if x is not f for c in x.cells}

    def reachable(self, f: Fighter) -> dict:
        """Squares `f` can end a move on this turn, with the way there (rules/grid.Step)."""
        tree = self.move_tree(f)
        occ = self.occupied_by_others(f)
        return {sq: st for sq, st in tree.items() if sq != (f.x, f.y) and grid.can_stop(sq, f.sq, occ)}

    def path_to(self, f: Fighter, dest: tuple[int, int]) -> list[tuple[int, int]]:
        tree = self.move_tree(f)
        if dest not in tree or not grid.can_stop(dest, f.sq, self.occupied_by_others(f)):
            return []
        return grid.route(tree, dest)

    def do_move(self, f: Fighter, dest: tuple[int, int]) -> bool:
        """Walk to a square along the cheapest way (provoking whoever that way provokes). False if it cannot."""
        path = self.path_to(f, dest)
        if not path:
            return False
        self.walk(f, path)
        self._after_action(f, quiet=True)
        return True

    def walk(self, f: Fighter, path: list[tuple[int, int]], *, free: bool = False, provoke: bool = True) -> int:
        """Move along a path square by square: opportunity attacks as reach is left, doors opened on the way, webs
        and fire as they are entered. Returns how many squares were walked (a web, a fall or a blow can stop it)."""
        walked: list[tuple[int, int]] = []
        start = (f.x, f.y)
        n = 0
        held = self.held_by(f)
        heavy = self.dragging(f)
        for sq in path:
            if not f.active or "unconscious" in f.conditions:
                break
            if f.speed <= 0 and not free:
                break
            new_cells = grid.cells(sq[0], sq[1], f.sq)
            ground = f.fly_speed <= 0
            leap = max(abs(sq[0] - f.x), abs(sq[1] - f.y))
            if leap > 1:  # a long jump: each foot costs a foot, whatever it passes over
                cost = 0 if free else leap * grid.SQUARE_FT
            else:
                entering = [c for c in new_cells if c not in f.cells] or new_cells
                cost = 0 if free else grid.step_feet(self.field, entering, crawling="prone" in f.conditions,
                                                     flying=not ground, climber=f.climb_speed > 0,
                                                     swimmer=f.swim_speed > 0)
            if heavy and not free and not (f.char is not None and feats.has(f.char, "grappler")):
                cost *= 2  # (Grappler: Fast Wrestler drags at no extra cost)
            if not free and leap <= 1 and f.__dict__.get("easy_dash") == self.round:
                cost = min(cost, grid.SQUARE_FT)  # (Speedy: a Dash takes no notice of rough ground)
            if cost > f.move_left and not free:
                break
            if not free and not self._may_go(f, sq, leap, cost):
                break
            if provoke and not free:
                there = (sq[0], sq[1], f.sq)
                for e in self.enemies_of(f):
                    if f.disengaged and not (e.has_trait("feat_sentinel") and self.gap(e, f) <= 1):
                        continue  # (Sentinel: a foe beside them gets a blow even at one who disengages)
                    if (e.state == "fighting" and e.can_opportunity and not e.incapacitated and e.standing
                            and self.gap(e, f) <= self.reach_of(e) and grid.gap(e.space, there) > self.reach_of(e)
                            and self.can_see(e, f)):
                        if walked:
                            self._event("move", who=f.id, path=[start] + walked)
                            start, walked = (f.x, f.y), []
                        self.opportunity(e, f, why="sentinel" if f.disengaged else "")
                        if not f.active or "unconscious" in f.conditions:
                            break
                if not f.active or "unconscious" in f.conditions or cost > f.move_left:
                    break  # (struck down, or stopped where they stand: Sentinel)
            for c in new_cells:
                self.field.open_door(*c)
            before = (f.x, f.y)
            f.x, f.y = sq
            f.move_left -= cost
            f.moved_feet += grid.SQUARE_FT * max(1, leap)
            walked.append(sq)
            n += 1
            for x in held:  # the held come along, into the square just left
                if x.active and self.gap(x, f) > 1 and self.field.fits(before[0], before[1], x.sq) and not any(
                        c in self.occupied_by_others(x) for c in grid.cells(before[0], before[1], x.sq)):
                    self._event("push", who=x.id, path=[(x.x, x.y), before])
                    x.x, x.y = before
            if f.hidden and not any(self.field.hiding[c] for c in f.cells):
                if any(self.can_see(e, f) for e in self.enemies_of(f) if e.standing and self.field.cover(e.space, f.space) < grid.HALF):
                    f.hidden = 0
            if leap > 1 and not free and any(self.field.difficult(*c) for c in f.cells) and \
                    not self.check(f, "acrobatics", 10, "Landing on rough ground"):
                f.conditions["prone"] = -1
                self._event("prone", who=f.id)
                self.say(f"{f.the_name} lands badly on the rough ground and goes sprawling.", "warn")
                break
            if self._zones_on(f, start=False):
                break  # caught in a web
            if provoke and not free and self._polearm_guard(f, before, walked, start):
                start, walked = (f.x, f.y), []
                if not f.active or "unconscious" in f.conditions or f.move_left <= 0:
                    break
            if any(x.readied for x in self.fighters):
                self._readied(f)
                if not f.active or "unconscious" in f.conditions:
                    break
        if walked:
            self._event("move", who=f.id, path=[start] + walked)
        self._sync_grapples(f)
        self._follow_auras()
        return n

    def _may_go(self, f: Fighter, sq: tuple[int, int], leap: int, cost: int) -> bool:
        """The checks a way can ask for (2024): clearing a low thing in a leap (Athletics, DC 10), or swimming against
        a current (Athletics, DC 15). A failure spends the effort and ends the move where it is."""
        if leap > 1:
            dx, dy = (sq[0] - f.x) // leap, (sq[1] - f.y) // leap
            over = [(f.x + dx * i, f.y + dy * i) for i in range(1, leap)]
            low = next((c for c in over if self.field.climb[c]), None)
            if low is not None and not self.check(f, "athletics", 10, "Clearing it in a leap"):
                f.move_left = max(0, f.move_left - cost)
                self.say(f"{f.the_name} leaps for it, catches the {self.field.describe(*low)} and comes down short.",
                         "warn")
                return False
            return True
        if f.swim_speed <= 0 and f.fly_speed <= 0 and any(self.field.rough_water[c] for c in grid.cells(sq[0], sq[1], f.sq)
                                                          if c not in f.cells):
            if not self.check(f, "athletics", 15, "Swimming against the current"):
                f.move_left = max(0, f.move_left - cost)
                self.say(f"The current is too strong for {f.the_name}, who makes no headway.", "warn")
                return False
        return True

    def check(self, f: Fighter, skill: str, dc: int, why: str = "") -> bool:
        """An ability check in a fight: a d20 and the skill (exhaustion counted in it) against the DC, in the dice log."""
        ability = self.t.rules["skills"].get(skill, {}).get("ability", skill)
        ctx = trs.Ctx(self, f, ability=ability, skill=skill)
        modes = {mode for mode, _ in trs.modifiers(f, "check", ctx)}
        if f.buff_value("foresight"):
            modes.add("advantage")  # (Foresight: every D20 Test)
        if ability in ("str", "dex") and query.untrained_armour(f):
            modes.add("disadvantage")
        adv, dis = "advantage" in modes, "disadvantage" in modes
        roll = dice.d20(self.rng, advantage=adv and not dis, disadvantage=dis and not adv).natural
        bonus = f.skill(skill)
        self.dice_say(f"{why or skill.title()} ({f.name}): {roll} {'+' if bonus >= 0 else '-'} {abs(bonus)} = "
                      f"{roll + bonus} vs DC {dc}")
        total = roll + bonus
        if roll < 10 and f.char is not None and f.has_trait("reliable_talent") and skill in f.char.skills:
            total = 10 + bonus  # (Reliable Talent)
        if total < dc and f.char is not None:
            from realmwalker.rules.engine.handlers import fighter

            total, line = fighter.tactical_mind(f.char, self.t, total, dc, self.rng)
            if line:
                self.dice_say(f"{f.name} ({line})")
        return total >= dc

    def object_at(self, cell: tuple[int, int]) -> dict | None:
        """A thing on the field that can be broken: a door, a barrel, a table... with its AC and hit points (data/rules.json
        objects "terrain"), kept while the fight lasts."""
        if not self.field.in_bounds(*cell):
            return None
        tid = self.field.name(*cell)
        spec = self.t.rules.get("objects", {}).get("terrain", {}).get(tid)
        if spec is None:
            return None
        store = self.__dict__.setdefault("objects", {})
        if cell not in store:
            substance, size, resilient, becomes = spec
            store[cell] = {"name": self.field.describe(*cell), "ac": hazards.object_ac(self.t, substance),
                           "hp": dice.roll(hazards.object_hp(self.t, size, resilient), self.rng).total, "becomes": becomes}
        return store[cell]

    def attack_object(self, f: Fighter, opt: AttackOption, cell: tuple[int, int]) -> bool:
        """Strike a thing (an attack of the Attack action): beat its AC to hurt it; at 0 hit points it is broken and
        the square opens. Poison and psychic damage do nothing to things."""
        obj = self.object_at(cell)
        if obj is None or self.object_problem(f, opt, cell) or not self._use_attack(f):
            return False
        self._spend_shot(f, opt)
        f.hidden = 0
        roll = dice.d20(self.rng).natural
        total = roll + opt.bonus
        hit = roll == 20 or (roll != 1 and total >= obj["ac"])
        self.dice_say(f"{f.name} → {obj['name']}, {opt.name}: {roll} {signed_mod(opt.bonus)} = {total} vs AC {obj['ac']}"
                      f" — {'hit' if hit else 'miss'}")
        self._event("attack", by=f.id, to=None, hit=hit, crit=roll == 20, how=opt.kind, melee=opt.is_melee, weapon=opt.name,
                    dtype=opt.damage_type, armoured=False, cell=list(cell))
        if hit and not hazards.object_immune(self.t, opt.damage_type):
            hard = f.char is not None and opt.item_uid is not None and magic_flag(f.char.item(opt.item_uid),
                                                                                    "adamantine_weapon")
            obj["hp"] -= dice.roll(opt.damage, self.rng, double_dice=roll == 20 or hard).total
            if obj["hp"] <= 0:
                becomes = obj["becomes"] if obj["becomes"] != "ground" else (self.field.ground or "rubble")
                self.field.set_terrain(*cell, becomes if becomes in self.t.terrain.index else "rubble")
                self.__dict__["objects"].pop(cell, None)
                self._event("broken", cell=list(cell))
                self.say(f"{f.the_name} smashes the {obj['name'].lower()}.", "system")
        self._after_action(f)
        return True

    def object_problem(self, f: Fighter, opt: AttackOption, cell: tuple[int, int]) -> str | None:
        """Why this attack cannot strike the thing on that square (None if it can)."""
        if not opt.available:
            return opt.reason or "not possible"
        if not self.has_action(f):
            return "no action left this turn"
        g = max(grid.gap(f.space, (cell[0], cell[1], 1)), f.z // grid.SQUARE_FT)
        if opt.is_melee:
            return None if g <= opt.reach_sq else "out of reach"
        if g * grid.SQUARE_FT > (opt.range or DEFAULT_RANGE.get(opt.kind, (60, 120)))[1]:
            return "out of range"
        if not self.field.line_clear(f.x + f.sq / 2, f.y + f.sq / 2, cell[0] + 0.5, cell[1] + 0.5, set(f.cells) | {cell},
                                     terrain_only=True):
            return "no clear line"
        return None

    def breakables(self, f: Fighter) -> dict:
        """The things `f` could strike now: {square: the best attack for it} (weapons only, no spells)."""
        weapons = [o for o in self.attack_options(f) if o.available and o.kind in ("melee", "ranged")
                   and not o.extra.get("area") and not o.extra.get("single_save")]
        if not weapons or not self.has_action(f):
            return {}
        reach = max(max(o.reach_sq for o in weapons if o.is_melee) if any(o.is_melee for o in weapons) else 0,
                    max(((o.range or (0, 0))[1] // grid.SQUARE_FT) for o in weapons if not o.is_melee)
                    if any(not o.is_melee for o in weapons) else 0)
        spec = self.t.rules.get("objects", {}).get("terrain", {})
        out = {}
        for x in range(max(0, f.x - reach), min(self.field.width, f.x + f.sq + reach)):
            for y in range(max(0, f.y - reach), min(self.field.height, f.y + f.sq + reach)):
                if self.field.name(x, y) not in spec:
                    continue
                fits = [o for o in weapons if self.object_problem(f, o, (x, y)) is None]
                if fits:
                    out[(x, y)] = max(fits, key=lambda o: (o.is_melee, _avg(o.damage)))
        return out

    def _spend_shot(self, att: Fighter, opt: AttackOption) -> None:
        """An arrow or a bolt from the quiver, a thrown weapon out of the hand (it lies on the field after)."""
        if opt.ammo_def and att.char:
            uid = opt.extra.get("ammo_uid")
            ammo = att.char.item(uid) if uid is not None else \
                next((i for i in att.char.inventory if i.def_id == opt.ammo_def and not i.magic), None)
            if ammo is not None:
                remove_item(att.char, ammo.uid, 1)
                if att.side == PARTY and not ammo.magic:
                    self.shot[ammo.def_id] = self.shot.get(ammo.def_id, 0) + 1
        if opt.key.startswith("throw") and att.char and opt.item_uid is not None:
            thrown = remove_item(att.char, opt.item_uid, 1)
            if thrown is not None:
                self.thrown.append(thrown)

    def do_fly(self, f: Fighter, feet: int) -> bool:
        """Rise (or come down, negative) by this many feet, at the cost of as much movement."""
        feet = int(feet) // grid.SQUARE_FT * grid.SQUARE_FT
        if f.fly_speed <= 0 or not feet or abs(feet) > f.move_left or f.z + feet < 0 or not f.active:
            return False
        to = f.z + feet
        if not f.disengaged:  # out of reach upwards is still out of reach: they strike as it goes
            for e in self.enemies_of(f):
                if (e.state == "fighting" and e.can_opportunity and not e.incapacitated and e.standing
                        and self.gap(e, f) <= self.reach_of(e) and self.can_see(e, f)
                        and max(grid.gap(e.space, f.space), abs(e.z - to) // grid.SQUARE_FT) > self.reach_of(e)):
                    self._opportunity(e, f)
                    if not f.active or "unconscious" in f.conditions or f.z == 0 and to > 0 and "prone" in f.conditions:
                        return True  # brought down before it got away
        f.move_left = max(0, f.move_left - abs(feet))
        start = f.z
        f.z = to
        self._event("fly", who=f.id, z=f.z, before=start)
        if f.active and any(x.readied for x in self.fighters):
            self._readied(f)  # coming down into a readied blow
        self._check_end()
        return True

    def _fall(self, f: Fighter) -> None:
        """A flier knocked down, senseless or held still falls (unless it can hover): 1d6 for every 10 feet, and Prone
        if it hurt (2024)."""
        feet, f.z = f.z, 0
        self._event("fall", who=f.id, feet=feet)
        if f.__dict__.pop("soft_landing", False):
            self.say(f"{f.the_name} floats gently to the ground.", "info")
            return
        if feet >= 10 and self._feather_fall(f):
            return
        expr = hazards.falling(self.t, feet)
        self.say(f"{f.the_name} falls {feet} feet.", "danger" if f.side == PARTY else "info")
        if expr:
            self._hit(None, f, dice.roll(expr, self.rng).total, "bludgeoning", crit=False, weapon="fall")
            if f.active or f.state == "down":
                f.conditions["prone"] = -1

    def _feather_fall(self, f: Fighter) -> bool:
        """Someone falls: a friend within 60 feet (or the faller) with Feather Fall ready casts it with the reaction,
        and the fall does no harm (2024: a reaction, a level 1 slot, up to five falling creatures)."""
        for x in sorted(self.team(f.team), key=lambda x: x is not f):
            if x.char is None or not x.reaction or not x.active or query.incapacitated(x) or self.feet(x, f) > 60:
                continue
            if "feather_fall" not in spellrules.known_spells(x.char, self.t) or self.slot_used_now(x):
                continue
            ok, _why = spellrules.can_cast(x.char, self.t, "feather_fall")
            slot = spellrules.lowest_free_slot(x.char, self.t, 1)
            if not ok or slot is None or self.antimagic(x.cells):
                continue
            spellrules.spend_slot(x.char, slot)
            self.note_slot(x)
            x.reaction = False
            self._event("cast", by=x.id, to=f.id, spell="feather_fall", effect="buff", look="buff", dtype="", area=[])
            who = "" if x is f else f"{x.the_name} speaks a word: "
            self.say(f"<magic>{who}{f.the_name} drifts down like a feather</> and lands unharmed. (Feather Fall)",
                     "magic")
            return True
        return False

    def held_by(self, f: Fighter) -> list[Fighter]:
        return [x for x in self.fighters if x.grappled_by == f.id and x.active]

    def dragging(self, f: Fighter) -> bool:
        """Whether moving costs `f` double: it holds someone not tiny and not two sizes smaller (2024)."""
        if any(trs.values(f, "drag_free")):
            return False  # (a bugbear's Abduct)
        return any(x.size != "tiny" and SIZES.index(x.size) > SIZES.index(f.size) - 2 for x in self.held_by(f))

    def _sync_grapples(self, f: Fighter) -> None:
        """A hold breaks when the one holding moves out of reach."""
        for x in self.fighters:
            if x.grappled_by == f.id and self.gap(x, f) > 1:
                x.grappled_by = None
                x.conditions.pop("grappled", None)
                self.say(f"{x.the_name} is no longer held.", "system")
        if f.grappled_by is not None:
            g = next((x for x in self.fighters if x.id == f.grappled_by), None)
            if g is None or not g.standing or self.gap(f, g) > 1:
                f.grappled_by = None
                f.conditions.pop("grappled", None)

    def _opportunity(self, e: Fighter, f: Fighter) -> None:
        self.opportunity(e, f)

    def opportunity(self, e: Fighter, f: Fighter, *, why: str = "") -> bool:
        """A blow with the reaction at someone breaking away (why ""), stepping into a polearm's reach ("polearm") or
        striking a friend beside a sentinel ("sentinel"). War Caster may answer with a harmful cantrip instead. Returns
        whether it was made."""
        if not e.reaction or not e.active or e.incapacitated or self.frozen(e):
            return False
        opts = [o for o in self.attack_options(e) if o.is_melee and o.available and self.gap(e, f) <= o.reach_sq]
        cantrip = self._war_cantrip(e, f, opts)
        if not opts and cantrip is None:
            return False
        what = {"polearm": f"{f.the_name} steps into the reach of {e.the_name}'s weapon",
                "sentinel": f"{f.the_name} turns {f.possessive if f.char else 'its'} back on {e.the_name}"}.get(
                    why, f"{f.the_name} breaks away from {e.the_name}")
        if not reactions.yes(self, Decision(e, "opportunity", f"{what}. Strike? (your reaction)",
                                            [("yes", "Strike"), ("no", "Let them go")], free=True)):
            return False
        e.reaction = False
        self._event("opportunity", by=e.id, to=f.id)
        if cantrip is not None:
            self.say(f"{e.the_name} answers {f.the_name} with a spell.", "warn")
            action, flags = e.action, (e.cast_action_spell, e.cast_bonus_spell)
            e.action = 1
            try:
                self.do_cast(e, cantrip, f)
            finally:
                e.action = action
                e.cast_action_spell, e.cast_bonus_spell = flags
            self._check_end()
            return True
        opt = max(opts, key=lambda o: _avg(o.damage) + o.bonus)
        self.say(f"{e.the_name} strikes at {f.the_name} as {f.possessive if f.char else 'it'} "
                 f"{'comes on' if why == 'polearm' else 'breaks away' if not why else 'turns away'}.", "warn")
        self._oa_target = f
        try:
            hit = self._attack(e, opt, f)
        finally:
            self._oa_target = None
        if hit and e.has_trait("feat_sentinel") and f.active and f.move_left > 0 and f.z == 0                 and grid.can_stop((f.x, f.y), f.sq, self.occupied_by_others(f)):
            f.move_left = 0  # (Sentinel: Halt)
            self.say(f"{e.the_name} stops {f.the_name} where {'they stand' if f.char else 'it stands'}.", "system")
        self._check_end()
        return True

    def _war_cantrip(self, e: Fighter, f: Fighter, opts: list) -> str | None:
        """War Caster: a harmful cantrip aimed at one creature, when it would do better than the blow (or there is
        no blow to make)."""
        if e.char is None or not feats.has(e.char, "war_caster"):
            return None
        best = None
        for sid, ok, _ in self.spell_options(e):
            sp = self.t.spells[spell_id(sid)]
            if not ok or sp["level"] != 0 or sp["target"] != "enemy" or sp.get("cast", "action") != "action":
                continue
            if f not in self.spell_targets(e, sid):
                continue
            dmg = sum(_avg(d) for o in spellrules.ops(sp) for d, _t, _u in spellrules.damage_parts(o))                 * (2 if e.char.level >= 5 else 1)
            if best is None or dmg > best[1]:
                best = (sid, dmg)
        if best is None:
            return None
        blow = max([_avg(o.damage) for o in opts], default=0)
        return best[0] if blow < best[1] else None

    def _polearm_guard(self, f: Fighter, before: tuple, walked: list, start: tuple) -> bool:
        """Polearm Master: a foe holding a polearm strikes, with the reaction, at one who steps into its reach."""
        made = False
        for e in self.enemies_of(f):
            if e.char is None or not feats.has(e.char, "polearm_master") or not e.reaction or not e.can_opportunity:
                continue
            if e.incapacitated or not e.standing or not self.can_see(e, f):
                continue
            main = e.char.equipped_item("main_hand")
            props = self.t.items.get(main.def_id).get("properties", []) if main is not None else []
            if main is None or not (main.def_id in feats.POLEARMS or "heavy" in props and "reach" in props):
                continue
            reach = self.reach_of(e)
            if self.gap(e, f) <= reach < grid.gap(e.space, (before[0], before[1], f.sq)):
                if walked and not made:
                    self._event("move", who=f.id, path=[start] + walked)
                made = self.opportunity(e, f, why="polearm") or made
        return made

    def area_attack(self, f: Fighter, opt: AttackOption, point: tuple[int, int]) -> None:
        """A breath weapon or the like: everyone in the area saves for half; then it must recharge. One made with the
        Multiattack (a draconic spirit's) is part of the Attack action: it begins it, or comes with this turn's
        attacks, once a turn."""
        a = opt.extra
        shape = a["area"]["shape"]
        cells = self.field.area(shape, int(a["area"]["size"]), origin=f.space, toward=point, from_self=True)
        f.recharge[a["name"]] = False
        self._spend_use(f, opt)
        if a.get("with_multiattack"):
            if not self.struck_this_turn(f) and f.action > 0:
                f.action -= 1
                f.attacks_left = query.attacks_per_action(f)  # (the Rends are still to come)
                f.__dict__["struck_turn"] = f.spent_round
        elif f.action > 0:
            f.action -= 1
        self.say(f"{f.the_name} unleashes {f.possessive} {opt.name}!", "danger")
        self._event("cast", by=f.id, to=None, spell=a["name"], effect="breath", dtype=opt.damage_type, area=list(cells),
                    point=point, shape=shape)
        rolled = dice.roll(opt.damage, self.rng).total
        for x in self.in_area(cells, "all", f):
            if x is f:
                continue
            saved = self._save_damage(f, x, a.get("save", "dex"), int(a.get("dc", 13)), opt.damage, opt.damage_type,
                                      "half" if a.get("half", True) else "none", rolled=rolled)
            if not saved and a.get("on_fail") and x.active:
                self._block_effects(f, x, opt, a["on_fail"])
        if opt.damage_type == "fire":
            self._ignite(f, cells)
        self._check_end()

    def do_dash(self, f: Fighter, *, bonus: bool = False) -> None:
        if not self._spend(f, bonus):
            return
        f.dashed = True
        f.move_left += f.speed + (10 if f.char is not None and feats.has(f.char, "charger") else 0)
        if f.char is not None and feats.has(f.char, "speedy"):
            f.__dict__["easy_dash"] = self.round
        self.say(f"{f.the_name} runs.", "system")
        self._after_action(f)

    def do_disengage(self, f: Fighter, *, bonus: bool = False) -> None:
        if not self._spend(f, bonus):
            return
        f.disengaged = True
        self.say(f"{f.the_name} gives ground carefully, watching every blade.", "system")
        self._after_action(f)

    def do_dodge(self, f: Fighter) -> None:
        if not self._spend(f):
            return
        f.dodging = True
        self.say(f"{f.the_name} watches for the next blow, ready to twist away.", "system")
        self._after_action(f)

    def hide_problem(self, f: Fighter) -> str | None:
        for e in self.enemies_of(f):
            if not e.standing:
                continue
            if self.gap(e, f) <= 1:
                return f"{e.the_name} is right beside you"
            if not self.can_see(e, f):
                continue
            if self.cover(e, f) >= grid.THREE_QUARTERS:
                continue
            if any(self.field.hiding[c] for c in f.cells) and self.gap(e, f) > 2:
                continue
            if f.has_trait("naturally_stealthy") and any(
                    x is not f and x.standing and x.size in SIZES and f.size in SIZES
                    and SIZES.index(x.size) > SIZES.index(f.size) and self.gap(x, f) <= 1 and self.gap(x, e) < self.gap(f, e)
                    for x in self.on_field()):
                continue  # (a halfling behind someone bigger)
            return f"{e.the_name} can see you plainly"
        return None

    def do_hide(self, f: Fighter, *, bonus: bool = False) -> None:
        why = self.hide_problem(f)
        if why:
            self.say(f"Nowhere to hide: {why}.", "warn")
            return
        if not self._spend(f, bonus):
            return
        stink = False
        if f.char is not None and f.char.attuned:
            from realmwalker.rules import magic

            stink = magic.flag(f.char, "stench")  # an artifact's sour stink gives them away
        skulker = f.char is not None and feats.has(f.char, "skulker")  # (Skulker: the fog of war)
        roll = dice.d20(self.rng, advantage=skulker, disadvantage=stink).natural
        total = roll + f.skill("stealth")
        self.dice_say(f"Stealth ({f.name}): {roll} {signed_mod(f.skill('stealth'))} = {total}")
        seen = [e for e in self.enemies_of(f) if e.standing and e.passive() >= total and self.can_see(e, f)]
        if total < 15:  # the 2024 Hide: a DC 15 Dexterity (Stealth) check
            self.say(f"{f.the_name} tries to keep out of sight, and fails.", "warn")
        elif seen:
            self.say(f"{f.the_name} tries to keep out of sight, but {seen[0].the_name} is watching.", "warn")
        else:
            f.hidden = total
            self.say(f"{f.the_name} slips out of sight.", "good")
            self._event("hide", who=f.id)
        self._after_action(f)

    def can_leave(self, f: Fighter) -> bool:
        return f.active and f.speed > 0 and f.move_left >= 5 and any(self.field.exits[c] for c in f.cells
                                                                      if self.field.in_bounds(*c))

    def do_leave(self, f: Fighter) -> bool:
        """Off the edge of the field and away: out of the fight for good."""
        if not self.can_leave(f) or "grappled" in f.conditions:
            return False
        f.move_left -= 5
        f.state = "fled"
        self._event("leave", who=f.id)
        if f.side == PARTY:
            self.say(f"{f.the_name} gets clear of the fight.", "warn")
        else:
            self.say(f"{f.the_name} escapes.", "system")
        self._release(f)
        self._check_end()
        if self.outcome is None and self.current is f:
            self.end_turn()
        return True

    def _release(self, f: Fighter) -> None:
        if f.concentration is not None:
            self._end_concentration(f, quiet=True)
        for x in self.fighters:
            if x.grappled_by == f.id:
                x.grappled_by = None
                x.conditions.pop("grappled", None)

    # ------------------------------------------------------------------ the action economy
    def _spend(self, f: Fighter, bonus: bool = False) -> bool:
        if bonus:
            if f.bonus <= 0:
                return False
            f.bonus -= 1
            return True
        if f.action <= 0:
            return False
        f.action -= 1
        f.attacks_left = 0
        return True

    def has_action(self, f: Fighter) -> bool:
        return f.action > 0 or f.attacks_left > 0

    def struck_this_turn(self, f: Fighter) -> bool:
        """Its action went on this turn's attacks (a breath made with the Multiattack may still come)."""
        return f.__dict__.get("struck_turn") == f.spent_round

    def _after_action(self, f: Fighter, quiet: bool = False) -> None:
        self._check_end()
        if self.outcome is not None or self.current is not f or not self.turn_started:
            return
        if not f.can_act() or f.state != "fighting":
            self.end_turn()

    def turn_spent(self, f: Fighter) -> bool:
        """Nothing useful left to do this turn: no action, no movement, nothing for a bonus action."""
        return f.action <= 0 and f.attacks_left <= 0 and f.move_left < 5 and not self.bonus_options(f)

    # ------------------------------------------------------------------ attack options
    def attack_options(self, f: Fighter) -> list[AttackOption]:
        if not f.blows:
            return []  # (a familiar)
        out = self._attack_options(f)
        if f.buffs and f.buff_value("mist"):
            for o in out:  # (Gaseous Form: a drifting mist cannot strike)
                o.available, o.reason = False, "a drifting mist cannot strike (Gaseous Form)"
        return out

    def _attack_options(self, f: Fighter) -> list[AttackOption]:
        if f.creature:
            out = []
            for i, a in enumerate(f.cdef["attacks"]):
                kind = a["kind"]
                rng_ = (0, 0)
                if kind in ("ranged", "spell_ranged"):
                    rng_ = tuple(a.get("range") or (self.t.items.get(a["item"]).get("range") if a.get("item") in self.t.items
                                                    else None) or DEFAULT_RANGE[kind])
                props = [p for p in self.t.items.get(a["item"]).get("properties", []) if p in CREATURE_PROPS]                     if a.get("item") in self.t.items else []
                opt = AttackOption(f"c{i}", a["name"], kind, int(a["bonus"]), a["damage"], a["damage_type"],
                                   reach=bool(a.get("reach")), extra=a, range=(int(rng_[0]), int(rng_[1])),
                                   properties=props)  # (the weapon's: Heavy for Great Weapon Master)
                if a.get("area") or a.get("recharge"):
                    opt.available = f.recharge.get(a["name"], True)
                    opt.reason = "not ready again yet" if not opt.available else ""
                    if a.get("with_multiattack") and not opt.available:
                        opt.reason = "once a turn"
                    elif a.get("with_multiattack") and f.action <= 0 and not self.struck_this_turn(f):
                        opt.available, opt.reason = False, "part of the Attack action"
                if a.get("uses") and self.uses_left(f, a) <= 0:
                    opt.available, opt.reason = False, "used up for the day"
                if f.attached_to is not None and any(e.get("op") == "special" and e.get("attach") for e in a.get("on_hit", [])):
                    opt.available, opt.reason = False, "fastened on"
                out.append(opt)
            return out
        c = f.char
        s = f.sheet
        items = self.t.items
        out = []
        main = c.equipped_item("main_hand")
        off = c.equipped_item("off_hand")
        for key, it in (("main", main), ("off", off)):
            if it is None or items.category(it) != "weapon":
                continue
            if key == "off":
                continue  # the off hand strikes as a bonus action after attacking (two-weapon fighting)
            opt = self._weapon_option(f, s, it, key, two_handed_free=(key == "main" and off is None))
            out.append(opt)
            if opt.ammo_def:
                out += self._magic_ammo_options(f, opt)
        for it in c.inventory:
            d = items.get(it.def_id)
            if d["category"] == "weapon" and "thrown" in d.get("properties", []) and it.uid not in (c.equipped.values()):
                opt = self._weapon_option(f, s, it, f"throw{it.uid}", thrown=True)
                opt.name = f"throw {d['name']}"
                out.append(opt)
        if main is not None and items.category(main) == "weapon" and "thrown" in items.get(main.def_id).get("properties", []):
            opt = self._weapon_option(f, s, main, f"throw{main.uid}", thrown=True)
            opt.name = f"throw {items.get(main.def_id)['name']}"
            out.append(opt)
        if main is not None and items.category(main) == "weapon" and "ranged" in items.get(main.def_id).get("properties", []):
            # An improvised weapon (2024): a bow or a crossbow swung like a club, without proficiency, for 1d4.
            out.append(self._improvised_option(f, s, main, "bash"))
        unarmed_bonus = s.proficiency + s.mod("str") + s.attack_condition()
        brawler = feats.has(c, "tavern_brawler")
        fist_die = "1d4" if brawler else None
        if feats.has(c, "unarmed_fighting"):  # 1d8 with no weapon and no shield in hand, else 1d6
            fist_die = "1d6" if main is not None or off is not None else "1d8"
        fists = AttackOption("unarmed", "fists", "melee", unarmed_bonus,
                             f"{fist_die}{signed_mod(s.mod('str'))}" if fist_die else str(max(1, 1 + s.mod("str"))),
                             "bludgeoning")
        from realmwalker.rules import health

        if health.broken_arm(c, "right") and health.broken_arm(c, "left"):
            fists.available, fists.reason = False, "both arms are broken"
        out.append(fists)
        return out

    def uses_left(self, f: Fighter, a: dict) -> int:
        """Uses left of a creature's "1/day" action."""
        key = f"action:{a.get('id', a['name'])}"
        if key not in f.creature.uses:
            f.creature.uses[key] = int(str(a["uses"]).split("/")[0])
        return f.creature.uses[key]

    def _spend_use(self, f: Fighter, opt: AttackOption) -> None:
        a = opt.extra
        if f.creature is not None and a.get("uses"):
            f.creature.uses[f"action:{a.get('id', a['name'])}"] = self.uses_left(f, a) - 1
        if f.creature is not None and a.get("recharge") and not a.get("area"):
            f.recharge[a["name"]] = False

    def offhand_option(self, f: Fighter) -> AttackOption | None:
        """Two-weapon fighting: a light weapon in each hand, and the main one already used this turn."""
        if not f.char or f.buff_value("mist"):
            return None
        items = self.t.items
        main, off = f.char.equipped_item("main_hand"), f.char.equipped_item("off_hand")
        if main is None or off is None or items.category(main) != "weapon" or items.category(off) != "weapon":
            return None
        off_props = items.get(off.def_id).get("properties", [])
        wielder = feats.has(f.char, "dual_wielder") and "ranged" not in off_props and "two_handed" not in off_props
        if "light" not in items.get(main.def_id).get("properties", []) or "light" not in off_props and not wielder:
            return None
        opt = self._weapon_option(f, f.sheet, off, "off")
        opt.name = f"{opt.name} (off hand)"
        return opt

    def _improvised_option(self, f: Fighter, s: Sheet, it, key: str) -> AttackOption:
        """A thing used as a makeshift weapon (PHB 2024 glossary): no proficiency, 1d4, of a type that suits it."""
        mod = s.mod("str")
        from realmwalker.rules import magic

        bonus = mod + s.attack_condition() + magic.total(f.char, "attack")
        if feats.has(f.char, "tavern_brawler"):
            bonus += s.proficiency  # (proficient with improvised weapons)
        opt = AttackOption(key, f"strike with the {self.t.items.get(it.def_id)['name']}", "melee", bonus,
                           f"1d4{signed_mod(mod)}", "bludgeoning", properties=["improvised"], item_uid=it.uid)
        from realmwalker.rules import health

        if health.broken_arm(f.char, "right"):
            opt.available, opt.reason = False, "that arm is broken"
        return opt

    def _weapon_option(self, f: Fighter, s: Sheet, it, key: str, *, two_handed_free: bool = False,
                       thrown: bool = False) -> AttackOption:
        d = self.t.items.get(it.def_id)
        props = d.get("properties", [])
        ranged = "ranged" in props or thrown
        use_dex = ranged and not thrown or "finesse" in props and s.mod("dex") > s.mod("str") or \
            thrown and "finesse" in props and s.mod("dex") > s.mod("str")
        ability = "dex" if use_dex else "str"
        prof = s.proficiency if s.proficient_with_weapon(it) else 0
        quality = int(self.t.items.qualities.get(it.quality, {}).get("attack", 0))
        from realmwalker.rules import magic

        enchant = magic.item_bonus(it, char=f.char)
        bonus = s.mod(ability) + prof + quality + s.attack_condition(ranged) + enchant + magic.total(f.char, "attack")
        if ranged and not thrown and feats.has(f.char, "archery"):
            bonus += 2
        if not it.magic and it.condition < int(self.t.items.upkeep.get("battered", 30)):
            bonus -= 1  # battered: a bent blade, a split haft, a warped bow (game/gear.py)
        dmg = d["damage"]
        sh = next((bf for bf in f.buffs if bf.get("shillelagh")), None) if not ranged else None
        if sh is not None and it.def_id in ("club", "quarterstaff") and int(sh.get("mod", 0)) > s.mod(ability):
            bonus += int(sh["mod"]) - s.mod(ability)  # (Shillelagh: the spellcasting ability strikes)
        if sh is not None and it.def_id in ("club", "quarterstaff"):
            dmg = ("1d8", "1d10", "1d12", "2d6")[max(0, min(3, int(sh.get("tier", 1)) - 1))]
        both_hands = False  # a duellist keeps a versatile blade in one hand (d8 + 2 beats d10)
        if "versatile" in props and two_handed_free and not ranged and not feats.has(f.char, "dueling") \
                and not ("lost_left_arm" in f.char.injuries or "lost_right_arm" in f.char.injuries):
            dmg = d.get("versatile", dmg)
            both_hands = True
        mod = s.mod(ability)
        if sh is not None and it.def_id in ("club", "quarterstaff"):
            mod = max(mod, int(sh.get("mod", 0)))
            dmg = dmg if sh.get("tier") else d["damage"]
        if key == "off" and not thrown and not feats.has(f.char, "two_weapon_fighting") and not (
                feats.has(f.char, "crossbow_expert") and "ranged" in props):
            mod = min(0, mod)  # the off hand adds no bonus damage
        mod += enchant
        if f.char.effects.get("honed", 0) > 0 and not ranged and d.get("damage_type") in ("slashing", "piercing"):
            mod += int(self.t.items.upkeep.get("hone", {}).get("damage", 1))  # a whetstone's edge, until the fight ends
        if feats.has(f.char, "dueling") and not ranged and "two_handed" not in props and key == "main" \
                and not both_hands:  # Dueling is for a weapon in one hand
            off = f.char.equipped_item("off_hand")
            if off is None or self.t.items.category(off) != "weapon":
                mod += 2
        if thrown and feats.has(f.char, "thrown_weapon_fighting"):
            mod += 2  # the Thrown Weapon Fighting style
        damage = str(max(1, int(dmg) + mod)) if dmg.isdigit() else f"{dmg}{signed_mod(mod)}"  # a blowgun's 1
        rng_ = tuple(d.get("range") or ((20, 60) if thrown else (0, 0)))
        opt = AttackOption(key, d["name"], "ranged" if ranged else "melee", bonus, damage, d["damage_type"],
                           reach="reach" in props and not thrown, properties=list(props), item_uid=it.uid,
                           range=(int(rng_[0]), int(rng_[1])), extra={"ability_mod": s.mod(ability)},
                           two_hands=not ranged and ("two_handed" in props or both_hands))
        # A broken arm cannot hold a weapon; two-handed weapons need both.
        from realmwalker.rules import health

        right, left = health.broken_arm(f.char, "right"), health.broken_arm(f.char, "left")
        if key == "main" and right or key == "off" and left or thrown and right and left:
            opt.available, opt.reason = False, "that arm is broken"
        elif "two_handed" in props and (right or left or health.one_armed(f.char)):
            opt.available, opt.reason = False, "it needs two good arms"
        elif key == "off" and health.one_armed(f.char):
            opt.available, opt.reason = False, "there is only one hand"
        if "ammunition" in props:
            ammo = d.get("ammo")
            opt.ammo_def = ammo
            if opt.available and not any(i.def_id == ammo and not i.magic for i in f.char.inventory):
                opt.available = False
                opt.reason = f"no {self.t.items.get(ammo)['name']}s left"
        return opt

    def _magic_ammo_options(self, f: Fighter, base: AttackOption) -> list[AttackOption]:
        """A shot with each stack of magic ammunition (DMG 2024, +1 to +3 to hit and damage): the archer chooses."""
        from dataclasses import replace

        from realmwalker.rules import magic

        out = []
        for it in f.char.inventory:
            if it.def_id != base.ammo_def or not it.magic:
                continue
            plus = magic.item_bonus(it)
            n, sides, flat = dice.parse(base.damage)
            damage = f"{n}d{sides}{signed_mod(flat + plus)}" if n else str(max(1, flat + plus))
            name = f"{base.name}, {self.t.items.name(it, False)}"
            ok = base.available or base.reason == f"no {self.t.items.get(it.def_id)['name']}s left"
            out.append(replace(base, key=f"ammo{it.uid}", name=name, bonus=base.bonus + plus, damage=damage,
                               available=ok, reason="" if ok else base.reason,
                               extra=dict(base.extra, ammo_uid=it.uid)))
        return out

    def in_reach(self, f: Fighter, opt: AttackOption, target: Fighter, *, at: tuple[int, int] | None = None) -> tuple[bool, str]:
        """Whether an attack of this kind reaches the target from where `f` stands (or would stand)."""
        space = (at[0], at[1], f.sq) if at is not None else f.space
        g = max(grid.gap(space, target.space), abs(f.z - target.z) // grid.SQUARE_FT)
        if opt.is_melee:
            if g > opt.reach_sq:
                return False, "out of reach"
            return True, ""
        normal, long = opt.range or DEFAULT_RANGE.get(opt.kind, (60, 120))
        if g * grid.SQUARE_FT > long:
            return False, "out of range"
        if self.field.cover(space, target.space) == grid.TOTAL:
            return False, "no clear line"
        return True, ""

    def attack_problem(self, f: Fighter, opt: AttackOption, target: Fighter) -> str | None:
        if not opt.available:
            return opt.reason or "not possible"
        if not self.has_action(f) and not opt.extra.get("with_multiattack"):
            return "no action left this turn"
        if "loading" in opt.properties and not opt.is_melee and f.loaded_fired and f.attacks_left > 0 \
                and not (f.char is not None and feats.has(f.char, "crossbow_expert")):
            return "it must be loaded again: one shot an action"
        if not target.active and target.state != "down":
            return "not in the fight"
        if target.team == f.team:
            return "on your side"
        if query.source(f, "charmed") == target.id and "charmed" in f.conditions:
            return "charmed: you will not harm them"
        ok, why = self.in_reach(f, opt, target)
        if not ok:
            return why
        return None

    def targets_for(self, f: Fighter, opt: AttackOption) -> list[Fighter]:
        """Who this fighter could attack with this option right now, from where they stand."""
        return [x for x in self.enemies_of(f) + [y for y in self.fighters if y.team != f.team and y.state == "down"]
                if self.in_reach(f, opt, x)[0]]

    # ------------------------------------------------------------------ resolving attacks
    def _adv_dis(self, att: Fighter, target: Fighter, opt: AttackOption, *, space=None) -> tuple[bool, bool, list[str]]:
        """Advantage, disadvantage and why (rules/engine/query.attack_roll)."""
        r = query.attack_roll(self, att, target, opt, space=space)
        return r.advantage, r.disadvantage, r.notes

    def flanker(self, att: Fighter, target: Fighter, *, space=None) -> Fighter | None:
        """A friend of the attacker on the far side of the target (the DMG's flanking rule): both beside it, on
        opposite sides or corners, both able to see it and neither of them helpless. None if there is none."""
        a_space = space or att.space
        if grid.gap(a_space, target.space) != 1 or abs(att.z - target.z) >= grid.SQUARE_FT or att.incapacitated \
                or not self.can_see(att, target):
            return None
        for x in self.allies_of(att):
            if x is att or not x.standing or x.incapacitated or x.state != "fighting" or abs(x.z - target.z) >= grid.SQUARE_FT:
                continue
            if grid.flanks(a_space, x.space, target.space) and self.can_see(x, target):
                return x
        return None

    def target_ac(self, att: Fighter, target: Fighter, opt: AttackOption) -> tuple[int, int]:
        """The AC to beat, with the target's cover; and the cover."""
        cover = self.cover(att, target)
        if cover == grid.TOTAL:
            cover = grid.THREE_QUARTERS
        if opt.is_melee and self.gap(att, target) <= 1 and cover == grid.HALF and self.field.cover(att.space, target.space) == grid.NONE:
            cover = grid.NONE  # someone beside you does not shield the one you are fighting hand to hand
        if cover in (grid.HALF, grid.THREE_QUARTERS) and att.char is not None and (
                opt.kind == "ranged" and feats.has(att.char, "sharpshooter")
                or opt.kind.startswith("spell") and feats.has(att.char, "spell_sniper")):
            cover = grid.NONE  # (Sharpshooter, Spell Sniper: half and three-quarters cover ignored)
        parry = sum(int(v) for v in target.buff_value("parry_ac")) if opt.is_melee else 0
        return target.ac() + grid.COVER_AC[cover] + parry, cover

    def hit_chance(self, att: Fighter, opt: AttackOption, target: Fighter) -> float:
        adv, dis, _ = self._adv_dis(att, target, opt)
        ac, _ = self.target_ac(att, target, opt)
        need = max(2, min(20, ac - opt.bonus))
        p = (21 - need) / 20.0
        if adv and not dis:
            return 1 - (1 - p) ** 2
        if dis and not adv:
            return p * p
        return p

    def _attack(self, att: Fighter, opt: AttackOption, target: Fighter, *, spell_text: str = "") -> bool:
        marks.acted(self, att)
        if marks.sanctuary_stops(self, att, target):
            return False
        if opt.kind == "ranged" and self.wind_between(att, target):
            self.say(f"The wall of wind tears {att.the_name}'s missile aside.", "magic")
            self._event("attack", by=att.id, to=target.id, hit=False, weapon=opt.name)
            return False
        if opt.extra.get("single_save"):
            return self._save_action(att, opt, target)
        adv, dis, why = self._adv_dis(att, target, opt)
        guard = self._protector(att, target)
        if guard is not None:
            guard.reaction = False
            dis = True
            durations.buff(target, {"protected": guard.id, "source": f"protection:{guard.id}"},
                           durations.until(self, guard, "turn_start"))  # (and every attack on them, until then)
            why.append(f"{guard.name}'s shield")
            self.say(f"{guard.the_name} gets {guard.possessive} shield in the way.", "good" if guard.side == PARTY else "info")
        roll = dice.d20(self.rng, advantage=adv, disadvantage=dis)
        att.buffs = [bf for bf in att.buffs if not bf.get("sapped") and bf.get("vex") != target.id
                     and not bf.get("aimed")]  # spent on this roll
        natural = events.emit(self, "d20_after", actor=att, target=target, roll="attack", natural=roll.natural).natural
        crit = natural >= query.crit_range(att)
        bless = sum(dice.roll(d, self.rng).total for d in att.buff_value("attack_die")) \
            + marks.roll_adjust(self, att, target, opt)
        total = natural + opt.bonus + bless
        ac, cover = self.target_ac(att, target, opt)
        hit = crit or (natural != 1 and total >= ac)
        if not hit:
            ev = events.emit(self, "attack_missed", actor=att, target=target, opt=opt, natural=natural, total=total, ac=ac,
                             hit=False)  # Guided Strike...
            hit, total = ev.hit, ev.total
        # The Shield spell: a wizard who sees the blow coming turns it with a reaction, if that is enough.
        if hit and not crit and target.char and target.reaction and not target.incapacitated and total < ac + 5:
            if self._shield(target, att, opt, total, ac):
                ac += 5
                hit = False
        if hit and not crit and opt.is_melee and self._duelist_parry(target, att, total, ac):
            ac += query.proficiency(target)
            hit = total >= ac
        if hit and not crit and opt.is_melee and target.creature is not None and target.reaction \
                and target.has_trait("parry") and total < ac + 2 and not target.incapacitated:
            target.reaction = False
            ac += 2
            hit = False
            self.say(f"{target.the_name} parries.", "info" if target.side == FOE else "good")
        if hit and query.crit_within(self, att, target):
            crit = True  # a blow from right beside someone who cannot defend themselves at all
        if hit and marks.image_takes_it(self, att, target):
            hit = crit = False  # (Mirror Image: a duplicate took it)
        if hit:
            crit = events.emit(self, "attack_hit", actor=att, target=target, opt=opt, crit=crit).crit  # Assassinate...
        if crit and target.char is not None and magic_flag(target.char.equipped_item("armor"), "adamantine_armor"):
            crit = False
            why.append("adamantine")  # (the blow lands, but the armour will not let it bite deep)
        att.helped = False
        if target.marked:
            target.marked = False  # spent on this roll, hit or miss
        target.buffs = [bf for bf in target.buffs if bf.get("distracted") != att.team]
        if att.hidden and (hit or not (att.char is not None and feats.has(att.char, "skulker"))):
            att.__dict__["was_hidden"] = att.hidden  # (a thief's Stealth Attack may keep it)
            att.hidden = 0  # (Skulker: a miss does not give away where they hide)
        armor = target.armor_name("torso")
        turned = not hit and bool(armor) and total >= ac - 4 and natural != 1 and opt.kind in ("melee", "ranged")
        self._event("attack", by=att.id, to=target.id, hit=hit, crit=crit, how=opt.kind, melee=opt.is_melee,
                    weapon=opt.name, dtype=opt.damage_type, armoured=turned, bonus=opt.bonus + bless, ac=ac,
                    round=self.round)
        mode = " (adv)" if adv and not dis else (" (dis)" if dis and not adv else "")
        notes = list(why) + ([grid.COVER_WORDS[cover]] if cover else [])
        self.dice_say(f"{att.name} → {target.name}, {opt.name}{mode}: {natural} {signed_mod(opt.bonus + bless)} = {total} vs AC {ac}"
                      f" — {'critical!' if crit else ('hit' if hit else 'miss')}" + (f" [{', '.join(notes)}]" if notes else ""))
        self._spend_shot(att, opt)
        if not hit:
            weapon = opt.name
            lines = self.t.combat_text
            if turned:
                text = self.rng.choice(lines["armored_miss"])
            elif opt.kind == "ranged":
                text = self.rng.choice(lines.get("ranged_miss") or lines["miss"])
            elif opt.kind.startswith("spell"):
                text = self.rng.choice(lines.get("spell_miss") or lines["miss"])
            else:
                text = self.rng.choice(lines["miss"])
            self.say(self._fill(text, att, target, weapon=weapon, armor=armor or "armour"), "flavor")
            events.emit(self, "attack_done", actor=att, target=target, opt=opt, hit=False, dealt=0, crit=False)  # Graze
            return False
        if opt.extra.get("no_damage"):  # (a touch that only carries the spell: Plane Shift)
            events.emit(self, "attack_done", actor=att, target=target, opt=opt, hit=True, crit=crit, dealt=0)
            return True
        dmg_expr = opt.damage
        n, sides, flat = dice.parse(dmg_expr)
        rolled = dice.roll(dmg_expr, self.rng, double_dice=crit)
        amount = rolled.total
        if crit and n and att.char is not None and opt.item_uid is not None and target.has_trait("shapechanger") \
                and magic_flag(att.char.item(opt.item_uid), "silvered"):
            amount += self.rng.randint(1, sides)  # silver bites a shapechanger deep
        # Great Weapon Fighting (2024): a 1 or 2 on a damage die of a weapon held in both hands counts as a 3.
        if att.char and opt.is_melee and opt.two_hands and feats.has(att.char, "great_weapon_fighting"):
            amount = sum(max(3, r) for r in rolled.rolls) + flat
        if att.char is not None and opt.kind.startswith("spell") and self.__dict__.get("_casting") is att:
            amount += feats.adept_ones(att.char, opt.damage_type, rolled.rolls)  # (Elemental Adept: 1s count as 2s)
        dmg_ev = events.emit(self, "attack_damage", actor=att, target=target, opt=opt, crit=crit, natural=natural,
                             advantage=adv and not dis, disadvantage=dis and not adv, sides=sides, extra=0, typed=[],
                             rolls=list(rolled.rolls),
                             double=False)
        amount += dmg_ev.extra  # Sneak Attack, Divine Strike...
        if dmg_ev.double:
            amount *= 2  # (an assassin's Death Strike)
        amount = marks.hit_damage(self, att, target, opt, amount, crit)  # (Magic Weapon, Ray of Enfeeblement)
        self._spend_use(att, opt)
        before = target.hp + target.temp_hp
        guarded = target.temp_hp > 0  # (Armor of Agathys answers the blow that breaks it too)
        self._melee_blow = opt.is_melee
        try:
            self._hit(att, target, max(1, amount), opt.damage_type, crit=crit, weapon=opt.name,
                      bite=opt.extra.get("wound") == "bite",
                      claws=opt.extra.get("wound") == "cut" and att.creature is not None and opt.name == "claws")
        finally:
            self._melee_blow = False
        for e in opt.extra.get("extra", ()):  # a 2025 block's damage of another kind on the same hit (a spider's venom)
            if e.get("if") == "advantage" and not (adv and not dis):
                continue  # (a goblin's extra 1d4 needs the advantage)
            if target.active or target.state == "down":
                self._hit(att, target, dice.roll(e["damage"], self.rng, double_dice=crit).total, e["type"], crit=False,
                          weapon=opt.name)
        if att.buff_value("poisoned_blade") and opt.damage_type in ("piercing", "slashing") \
                and not opt.kind.startswith("spell") and (target.active or target.state == "down"):
            att.buffs = [bf for bf in att.buffs if "poisoned_blade" not in bf]  # (basic poison: spent on the first cut)
            self._hit(att, target, dice.roll("1d4", self.rng, double_dice=crit).total, "poison", crit=False,
                      weapon=opt.name)
        for extra_amount, extra_type in dmg_ev.typed + marks.extra_hits(self, att, target, opt, crit):
            if target.active or target.state == "down":  # (a power's own kind of damage; Divine Favor, Hex)
                self._hit(att, target, extra_amount, extra_type, crit=False, weapon=opt.name)
        if target.active or target.state == "down":
            marks.smite(self, att, target, opt, crit)  # (a smite readied on the weapon)
        marks.after_hit(self, att, target, opt, guarded)  # (Armor of Agathys)
        if opt.extra.get("on_hit") and target.active:
            self._block_effects(att, target, opt, opt.extra["on_hit"])
        if opt.extra.get("dust") and target.state == "down" and before > 0:
            self._turn_to_dust(att, target)  # (a mummy's Rotting Fist: brought to 0 by it, they die and crumble)
        if opt.extra.get("disease") and target.char and self.rng.chance(float(opt.extra.get("disease_chance", 1.0))):
            target.char.conditions.append(f"exposed:{opt.extra['disease']}")
        events.emit(self, "attack_done", actor=att, target=target, opt=opt, hit=True, crit=crit,
                    dealt=max(0, before - target.hp - target.temp_hp))  # the weapon masteries
        return True

    def _save_action(self, att: Fighter, opt: AttackOption, target: Fighter) -> bool:
        """A stat block's action that one creature saves against (no attack roll): damage, and what a failure brings."""
        a = opt.extra
        self._spend_use(att, opt)
        att.hidden = 0
        spared = att.__dict__.setdefault("spared", set()) if a.get("spares") else set()
        if target.id in spared:  # (a mummy's Dreadful Glare: one who withstood it is spared it for the day)
            self.say(f"{target.the_name} meets {att.the_name}'s {a['name'].lower()} and does not flinch.", "info")
            return False
        self.say(f"{att.the_name} uses {a['name'].title()} on {target.the_name}.", "danger" if target.side == PARTY else "info")
        self._event("cast", by=att.id, to=target.id, spell=a.get("id", a["name"]), effect="save", dtype=opt.damage_type,
                    area=list(target.cells), point=None, shape="")
        if opt.damage and opt.damage != "0":
            saved = self._save_damage(att, target, a["save"], int(a["dc"]), opt.damage, opt.damage_type,
                                      "half" if a.get("half") else "none")
        else:
            saved = self._save(target, a["save"], int(a["dc"]))
            self._event("save", who=target.id, ok=saved)
        if not saved and target.active and a.get("on_fail"):
            self._block_effects(att, target, opt, a["on_fail"])
        if saved and a.get("spares"):
            spared.add(target.id)
        return not saved

    def _block_effects(self, att: Fighter, target: Fighter, opt: AttackOption, block_effects: list[dict]) -> None:
        """What a stat block's hit or failed save brings (rules/engine/statblocks.ops), run by the kernel."""
        from realmwalker.rules.engine import statblocks

        c = effects.Cast(self, att, opt.name, {"target": "enemy", "name": opt.name, "ability": True}, target, None,
                         dc=int(opt.extra.get("dc", 10)))
        effects.run(c, statblocks.ops(block_effects), target)

    def _protector(self, att: Fighter, target: Fighter) -> Fighter | None:
        """The Protection fighting style: a friend beside the target, shield up, spends their reaction to make the
        blow harder."""
        for g in self.allies_of(target):
            if g is target or g.char is None or not feats.has(g.char, "protection") or not g.reaction:
                continue
            if g.incapacitated or not g.standing or self.gap(g, target) > 1 or not self.can_see(g, att):
                continue
            shield = g.char.equipped_item("off_hand")
            if shield is not None and self.t.items.category(shield) == "shield" and reactions.yes(
                    self, Decision(g, "protection", f"{att.the_name} strikes at {target.the_name}, beside "
                                   f"{g.the_name}. Put your shield in the way? (your reaction: the blow is at a "
                                   "disadvantage)", [("yes", "Shield them"), ("no", "Keep the reaction")], free=True)):
                return g
        return None

    def _duelist_parry(self, f: Fighter, att: Fighter, total: int, ac: int) -> bool:
        """Defensive Duelist: holding a finesse weapon, the reaction adds the proficiency bonus to AC against melee
        blows until the start of one's next turn, when it would turn this one."""
        if f.char is None or not f.reaction or f.incapacitated or not feats.has(f.char, "defensive_duelist"):
            return False
        main = f.char.equipped_item("main_hand")
        if main is None or "finesse" not in self.t.items.get(main.def_id).get("properties", []):
            return False
        pb = query.proficiency(f)
        if total >= ac + pb:
            return False
        if not reactions.yes(self, Decision(f, "parry", f"{att.the_name}'s blow would hit {f.the_name} ({total} "
                                            f"against AC {ac}). Parry? (your reaction: +{pb} AC against blows until "
                                            "your next turn)", [("yes", "Parry"), ("no", "Take it")])):
            return False
        f.reaction = False
        durations.buff(f, {"parry_ac": pb, "source": "defensive_duelist"}, durations.until(self, f, "turn_start"))
        self.say(f"{f.the_name} parries.", "good" if f.side == PARTY else "info")
        return True

    def _shield(self, f: Fighter, att: Fighter | None = None, opt: AttackOption | None = None, total: int = 0,
                ac: int = 0) -> bool:
        """Cast Shield as a reaction (wizards who know it, with a first-level slot to spare)."""
        if not f.char or "shield" not in spellrules.known_spells(f.char, self.t) or f.buff_value("befuddled"):
            return False
        if f.buff_value("ac") and any(b.get("source") == "shield" for b in f.buffs):
            return False
        slot = spellrules.lowest_free_slot(f.char, self.t, 1)
        if slot is None or self.slot_used_now(f):
            return False
        blow = f"{att.the_name}'s {opt.name} would hit {f.the_name} ({total} against AC {ac})" if att and opt else \
            f"A blow would hit {f.the_name}"
        if not reactions.yes(self, Decision(f, "shield", f"{blow}. Cast Shield? +5 AC turns it.",
                                            [("yes", f"Shield (a level {slot} slot)"), ("no", "Let it land")])):
            return False
        spellrules.spend_slot(f.char, slot)
        self.note_slot(f)
        f.reaction = False
        f.buffs.append({"ac": 5, "rounds": 0, "source": "shield"})
        events.emit(self, "spell_cast", actor=f, spell=self.t.spells["shield"], sid="shield", level=slot)
        self.say(f"<magic>{f.the_name} throws up a Shield.</> The blow glances off thin air.", "magic")
        self._event("cast", by=f.id, to=f.id, spell="shield", effect="buff", dtype="force", area=[])
        return True

    def _rebuke(self, f: Fighter, att: Fighter) -> bool:
        """Hellish Rebuke (2024): hurt by a creature it can see within 60 feet, a caster who has the spell ready may
        answer with its reaction and a level 1 slot or more."""
        sid = "hellish_rebuke"
        if sid not in self.t.spells or att.team == f.team or not f.active or not f.reaction \
                or query.incapacitated(f) or not att.active \
                or self.feet(f, att) > 60 or not self.can_see(f, att) or self.antimagic(f.cells):
            return False
        spell = self.t.spells[sid]
        if f.char is not None:
            if sid not in spellrules.known_spells(f.char, self.t):
                return False
            slot = spellrules.lowest_free_slot(f.char, self.t, 1)
            if slot is None or self.slot_used_now(f) or spellrules.armour_problem(f.char, self.t):
                return False
            s = f.sheet
            mod, dc = s.mod(spellrules.casting_ability(f.char, self.t)), spellrules.save_dc(s, self.t)
        else:
            sc = f.cdef.get("spellcasting") or {}
            if sid not in f.cdef.get("spells", []) or not sc:
                return False
            slot = spell["level"]
            mod, dc = f.mod(sc.get("ability", "cha")), int(sc.get("dc", 10))
        if not reactions.yes(self, Decision(f, "hellish_rebuke", f"{att.the_name} has hurt {f.the_name}. Answer with "
                                            "Hellish Rebuke? (your reaction: a DEX save against fire)",
                                            [("yes", f"Hellish Rebuke (a level {slot} slot)"), ("no", "Let it go")],
                                            default="yes")):
            return False
        f.reaction = False
        if f.char is not None:
            spellrules.spend_slot(f.char, slot)
            self.note_slot(f)
        if not self.cast(f, sid, spell, att, None, up=max(0, slot - spell["level"]), mod=mod, dc=dc, bonus=0, mult=1,
                         level=slot):
            if f.char is not None:
                spellrules.unspend_slot(f.char, slot)
        return True

    def _save(self, f: Fighter, ability: str, dc: int, *, quiet: bool = False, bonus: int = 0,
              against: tuple = (), disadvantage: bool = False, advantage: str = "") -> bool:
        sr = query.save_roll(self, f, ability, bonus=bonus, against=against)
        if disadvantage:
            sr.roll.add("disadvantage", "mage slayer")
        if advantage:
            sr.roll.add("advantage", advantage)
        if sr.auto_fail:
            if not quiet:
                self.dice_say(f"{f.name} {ability.upper()} save: fails ({sr.auto_fail})")
            return False
        roll = dice.d20(self.rng, advantage=sr.roll.advantage, disadvantage=sr.roll.disadvantage)
        total_bonus = sr.bonus + sum(dice.roll(d, self.rng).total for d in sr.dice)
        total = roll.natural + total_bonus
        ok = total >= dc
        if not quiet:
            self.dice_say(f"{f.name} {ability.upper()} save: {roll.natural} {signed_mod(total_bonus)} = {total} vs DC {dc} — "
                          f"{'saved' if ok else 'failed'}")
        marks.spend_saves(f)  # (Mind Sliver: the next save only)
        ok = events.emit(self, "d20_after", actor=f, roll="save", ability=ability, natural=roll.natural,
                         bonus=total_bonus, dc=dc, ok=ok).ok  # Indomitable...
        if not ok and self._legendary_resistance(f):
            ok = True
        if not ok and self._inspired(f, dc - total_bonus):
            again = dice.d20(self.rng).natural + total_bonus
            ok = again >= dc
            self.dice_say(f"{f.name} spends Heroic Inspiration and rolls again: {again} vs DC {dc} — "
                          f"{'saved' if ok else 'failed'}")
        return ok

    def _legendary_resistance(self, f: Fighter) -> bool:
        """A legendary creature chooses to succeed on a save it failed, a few times a day."""
        lr = f.cdef.get("legendary_resistance") if f.creature is not None else None
        if not lr:
            return False
        left = f.creature.uses.setdefault("legendary_resistance", int(lr.get("per_day", 3)))
        if left <= 0:
            return False
        f.creature.uses["legendary_resistance"] = left - 1
        self.say(f"{f.the_name} will not be moved. <dim>(Legendary Resistance, {left - 1} left)</>", "danger")
        return True

    def legendary_options(self, f: Fighter) -> list[AttackOption]:
        """The attacks a legendary creature can make out of turn."""
        leg = f.cdef.get("legendary") if f.creature is not None else None
        if not leg:
            return []
        from realmwalker.rules.engine import statblocks

        opts = []
        mine = {o.extra.get("id"): o for o in self.attack_options(f)}
        for i, a in enumerate(statblocks.attacks(leg.get("actions", []), {})):
            if a["kind"] in ("melee", "ranged") and not a.get("area"):
                opts.append(AttackOption(f"L{i}", a["name"], a["kind"], int(a["bonus"]), a["damage"], a["damage_type"],
                                         reach=bool(a.get("reach")), extra=a, range=tuple(a.get("range") or (0, 0))))
        for a in leg.get("actions", []):
            if a.get("use") in mine:
                opts.append(mine[a["use"]])
        return [o for o in opts if o.available]

    def _legendary_window(self, after: Fighter) -> None:
        """Right after another creature's turn, each legendary creature may spend a use to strike (2025: no lair
        actions on initiative 20; Legendary Action Uses come back at the start of its own turn)."""
        for f in list(self.fighters):
            leg = f.cdef.get("legendary") if f.creature is not None else None
            if not leg or f is after or not f.can_act() or self.outcome is not None:
                continue
            left = f.creature.uses.setdefault("legendary_actions", int(leg.get("uses", 3)))
            if left <= 0:
                continue
            for opt in self.legendary_options(f):
                targets = [t for t in self.targets_for(f, opt) if t.active and t.team != f.team]
                if targets:
                    f.creature.uses["legendary_actions"] = left - 1
                    self.say(f"{f.the_name} strikes out of turn. <dim>(Legendary Action)</>", "danger")
                    self._attack(f, opt, min(targets, key=lambda t: t.hp))
                    self._check_end()
                    break

    def _inspired(self, f: Fighter, need: int, what: str = "a saving throw") -> bool:
        """Heroic Inspiration (2024): a party member may reroll a die once; spent on a failed save worth saving."""
        if f.char is None or f.char.uses.get("heroic_inspiration", 0) <= 0 or need > 20:
            return False
        if not reactions.yes(self, Decision(f, "heroic_inspiration", f"{f.the_name} fails {what}. Spend Heroic "
                                            f"Inspiration to roll again? (needs {max(1, need)} or more)",
                                            [("yes", "Roll again"), ("no", "Keep it for later")])):
            return False
        f.char.uses["heroic_inspiration"] = 0
        return True

    def _save_damage(self, att: Fighter, target: Fighter, ability: str, dc: int, expr: str, dtype: str, on_save: str,
                     *, quiet: bool = False, cover: int = 0, rolled: int | None = None) -> bool:
        """A saving throw against damage (half on a save, or none); returns whether it was saved."""
        full = dice.roll(expr, self.rng).total if rolled is None else rolled
        saved = self._save(target, ability, dc, quiet=quiet, bonus=grid.COVER_AC[cover] if ability == "dex" else 0)
        self._event("save", who=target.id, ok=saved)
        self._save_hit(att, target, ability, saved, full, dtype, on_save)
        return saved

    def _save_hit(self, att: Fighter | None, target: Fighter, ability: str, saved: bool, full: int, dtype: str,
                  on_save: str) -> None:
        """The damage of a saving throw already made: all of it, half or none (Evasion...)."""
        if dtype == "poison" and not saved and target.char and not query.condition_immune(target, "poisoned"):
            target.conditions["poisoned"] = 10
        amount = (full // 2 if on_save == "half" else 0) if saved else full
        if saved and self.__dict__.get("_casting") is not None and target.buff_value("evade_spells"):
            amount = 0  # (Circle of Power: a save against a spell's damage takes none of it)
        amount = events.emit(self, "save_damage", actor=att, target=target, ability=ability, saved=saved, full=full,
                             amount=amount).amount  # Evasion...
        if amount > 0:
            self._hit(att, target, amount, dtype, crit=False, weapon=dtype)

    def _night_spirit(self, f: Fighter, dtype: str) -> bool:
        """Boon of the Night Spirit: in dim light or darkness, resistance to all harm but psychic and radiant."""
        return (f.char is not None and dtype not in ("psychic", "radiant")
                and feats.has(f.char, "boon_of_the_night_spirit") and self.light_on(f) < grid.BRIGHT)

    def _spell_resisted(self, f: Fighter, att: Fighter | None) -> bool:
        """An abjurer's Spell Resistance: the damage of a spell (as it is cast) is halved."""
        return att is not None and self.__dict__.get("_casting") is att and f.char is not None \
            and f.has_trait("spell_resistance")

    def _ignores_resist(self, att: Fighter | None, dtype: str) -> bool:
        """Poisoner (poison from anything they do) and Elemental Adept (their spells' element) cut through
        resistance."""
        if att is None or att.char is None:
            return False
        if dtype in ("bludgeoning", "piercing", "slashing") and feats.has(att.char, "boon_of_irresistible_offense"):
            return True  # (Boon of Irresistible Offense)
        if dtype == "poison" and (feats.has(att.char, "poisoner") or self.__dict__.get("_envenom") is att):
            return True  # (Poisoner; an assassin's Envenom Weapons)
        return self.__dict__.get("_casting") is att and dtype in feats.adept_types(att.char)

    def _hit(self, att: Fighter | None, target: Fighter, amount: int, dtype: str, *, crit: bool, weapon: str,
             bite: bool = False, claws: bool = False, raw: bool = False) -> None:
        """Damage that landed: resistances, text, wounds, going down. `raw`: nothing resists it (an evoker's
        Overchannel)."""
        rolled_amount = amount
        shadow = self._night_spirit(target, dtype) or self._spell_resisted(target, att)
        if raw:
            defence = ""
        else:
            amount, defence = query.damage_taken(target, amount, dtype, ignore_resist=self._ignores_resist(att, dtype),
                                                 resist=shadow)
        changed = {"immune": "immune: none", "vulnerable": "vulnerable: doubled",
                   "threshold": "below its damage threshold: none"}.get(defence) \
            or ("resisted: halved" if amount < rolled_amount and (shadow or query.resists(target, dtype)) else "")
        self.note_roll(f"{rolled_amount} {dtype} damage{' (critical: dice doubled)' if crit else ''}"
                       + (f", {changed} = {amount}" if changed else ""))
        if defence == "threshold":
            self.say(f"The blow does not get through {target.the_name}'s hide.", "flavor")
            self._event("immune", to=target.id, by=att.id if att else None)
            return
        if defence == "immune":
            self.say(f"{target.the_name} does not seem to feel it.", "flavor")
            self._event("immune", to=target.id, by=att.id if att else None)
            return
        amount = marks.soaked(self, target, amount, dtype)  # (the Resistance cantrip)
        if att is not None:
            amount = events.emit(self, "damage_incoming", actor=att, target=target, stage="blow", amount=amount,
                                 dtype=dtype).amount  # Uncanny Dodge...
        if dtype in ("fire", "acid"):
            target.took_fire = True
        part = roll_location(self.t.combat_text["locations"].get(target.body, self.t.combat_text["locations"]["humanoid"]), self.rng)
        if target.char and f"lost_{part}" in target.char.injuries:
            part = "torso"  # the blow meant for the arm that is not there lands on the body
        names = self.t.combat_text["part_names"].get(target.body, self.t.combat_text["part_names"]["humanoid"])
        part_text = self.rng.choice(names.get(part, [part.replace("_", " ")]))
        style = "bite" if bite else ("claws" if claws else dtype)
        templates = self.t.combat_text["hit"].get(style) or self.t.combat_text["hit"]["bludgeoning"]
        text = self._fill(self.rng.choice(templates), att, target, weapon=weapon, part=part_text)
        if crit:
            text = f"{self.rng.choice(self.t.combat_text['crit'])} {text}"
        hp_before = target.hp
        self.say(f"{text} <dim>({amount})</>", "danger" if target.side == PARTY else "info")
        self._event("damage", to=target.id, by=att.id if att else None, amount=amount, dtype=dtype, crit=crit)
        self._apply_hp_loss(target, amount, source=att, cause=f"{att.the_name if att else 'a wound'}'s {weapon}" if att else weapon,
                            crit=crit, dtype=dtype)
        if target.char is not None and (target.char.spells or {}).get("contingency"):
            if target.state == "down" and hp_before > 0:
                self._contingency(target, "down")
            elif target.state == "fighting" and target.hp <= target.max_hp // 2 < hp_before:
                self._contingency(target, "bloodied")
        target.damage_taken += amount
        events.emit(self, "damage_taken", actor=att, target=target, amount=amount, dtype=dtype)  # Energy Redirection
        marks.shared(self, target, amount)  # (Warding Bond)
        if att is not None and att is not target:
            self._rebuke(target, att)
        if target.state not in ("dead",) and hp_before > 0:
            # A wound is judged against the body, not the hit points: a level-1 wizard's seven are luck and nerve,
            # and a 5-point scratch on them is not a gushing wound. Below WOUND_HP_FLOOR the floor is used.
            body_hp = max(target.max_hp, WOUND_HP_FLOOR) if target.char else target.max_hp
            hp_now = target.hp + (body_hp - target.max_hp)
            chance = wound_chance(amount, body_hp, hp_now, crit, target.armor_factor(part))
            if self.rng.chance(chance):
                severity = severity_for(amount, body_hp, crit, self.rng)
                wound = make_wound(part, dtype, severity, self.rng, bite=bite, now=self.now,
                                   note=f"{att.cdef['name'] if att and att.creature else weapon}")
                if wound is not None:
                    target.wounds.append(wound)
                    wt = self.t.combat_text["wound"].get(wound.kind, {}).get(str(wound.severity))
                    if wt:
                        self.say(self.rng.choice(wt), "danger" if target.side == PARTY else "flavor")
        durations.on_damage(self, target)  # a magical sleep breaks
        if "unconscious" in target.conditions and target.state == "fighting" and target.hp > 0:
            durations.remove(target, "unconscious")
            self.say(f"{target.the_name} wakes with a start.", "system")
        if target.concentration is not None and target.active and target.standing:
            dc = query.concentration_dc(amount)
            slayer = att is not None and att.char is not None and feats.has(att.char, "mage_slayer")
            casting = self.__dict__.get("_casting")
            self._casting = None  # (holding on is not a save against the spell that hurt them: Spell Resistance)
            try:
                held = self._save(target, "con", dc, against=("concentration",), disadvantage=slayer)
            finally:
                self._casting = casting
            if not held:
                self._end_concentration(target, quiet=False, why="breaks")
        if target.active and target.side == FOE:
            self._morale_after_hit(target)

    def _apply_hp_loss(self, target: Fighter, amount: int, *, source: Fighter | None, cause: str, crit: bool = False,
                       dtype: str = "") -> None:
        if target.temp_hp > 0 and amount > 0 and cause != "blood loss":
            took = min(target.temp_hp, amount)
            target.temp_hp -= took
            amount -= took  # temporary hit points go first (2024)
            if amount <= 0:
                return
        if source is not None and target.state == "fighting" and amount > 0:
            amount = events.emit(self, "damage_incoming", actor=source, target=target, stage="hp",
                                 amount=amount).amount  # an Arcane Ward
            if amount <= 0:
                return
        if target.state == "down":
            target.stable = False
            if amount >= max(target.max_hp, WOUND_HP_FLOOR):
                self._kill(target, cause, killer=source)
                return
            target.death_saves[1] += 2 if crit else 1
            if target.death_saves[1] >= 3:
                self._kill(target, cause, killer=source)
            return
        new_hp = target.hp - amount
        if new_hp <= 0:
            if events.emit(self, "hp_zero", actor=source, target=target, amount=amount, survived=False, crit=crit,
                           dtype=dtype).survived:
                return  # Death Ward, Relentless Endurance, Undead Fortitude...
            target.hp = 0
            if target.char:
                # A blow that would take a whole life's worth below nothing kills outright (massive damage).
                if -new_hp >= max(target.max_hp, WOUND_HP_FLOOR):
                    self._kill(target, cause, killer=source)
                    return
                target.state = "down"
                target.conditions = {"unconscious": -1, "prone": -1}
                target.death_saves = [0, 0]
                target.stable = False
                target.hidden = 0
                self._release(target)
                self._event("down", who=target.id)
                self.say(self._fill(self.rng.choice(self.t.combat_text["down"]), source, target), "danger")
                self._morale_losses(target.side)
            elif self._knock_out(source, target):
                return
            else:
                self._kill(target, cause, killer=source)
        else:
            target.hp = new_hp

    def _knock_out(self, source: Fighter | None, target: Fighter) -> bool:
        """Knocking a creature out (PHB 2024): a melee blow that would drop it to 0 may leave it senseless instead.
        A party member's blow on someone who can be taken alive asks (the Auto, and the enemy, kill)."""
        if source is None or source.side != PARTY or not self._melee_blow or target.creature is None \
                or target.kind != "humanoid" or not target.active:
            return False
        if not reactions.yes(self, Decision(source, "knock_out", f"{target.the_name} is beaten. Knock them out "
                                            f"instead of killing? (taken alive, a prisoner)", [("yes", "Knock out"), ("no", "Kill")],
                                            default="no")):
            return False
        target.hp = 0
        target.state = "surrendered"  # taken alive: a prisoner when the fight is over
        target.conditions = {"unconscious": -1, "prone": -1}
        target.hidden = 0
        self._release(target)
        self._event("down", who=target.id)
        self.say(f"{source.the_name} knocks {target.the_name} senseless.", "good")
        self._morale_losses(target.side)
        return True

    def _death_save(self, f: Fighter) -> None:
        survivor = f.has_trait("survivor")  # (the Champion's Defy Death)
        hope = any("death" in (v or ()) for v in f.buff_value("save_adv"))  # (Beacon of Hope)
        roll = dice.d20(self.rng, advantage=f.char is not None and feats.has(f.char, "durable") or survivor
                        or hope).natural
        if survivor and roll >= 18:
            roll = 20
        if 1 < roll < 10 and roll + query.d20_penalty(f) < 10 and self._inspired(f, 10, "a death save"):
            roll = dice.d20(self.rng).natural
            self.dice_say(f"{f.name} spends Heroic Inspiration on the death save: {roll}")
        if roll not in (1, 20):
            roll = max(2, min(19, roll + query.d20_penalty(f)))  # exhaustion counts against it too
        if roll == 20:
            f.hp = 1
            f.state = "fighting"
            f.conditions.pop("unconscious", None)
            f.death_saves = [0, 0]
            self.dice_say(f"{f.name} death save: 20")
            self.say(f"{f.the_name} gasps and comes round.", "good")
            self._event("heal", to=f.id, amount=1)
            return
        if roll == 1:
            f.death_saves[1] += 2
        elif roll >= 10:
            f.death_saves[0] += 1
        else:
            f.death_saves[1] += 1
        s, fail = f.death_saves
        self.dice_say(f"{f.name} death save: {roll} — {'success' if roll >= 10 else 'failure'} ({s} saved, {fail} failed)")
        if fail >= 3:
            self._kill(f, "bleeds out")
        elif s >= 3:
            f.stable = True
            self.say(f"{f.the_name} stops bleeding out, and lies still.", "good")
        else:
            self.say(f"{f.the_name} is bleeding out.", "danger")

    def _kill(self, f: Fighter, cause: str, killer: Fighter | None = None) -> None:
        if "possessed" in f.conditions:
            self._host_dies(f)
        if f.jar is not None:
            self._body_dies(f)
        f.state = "dead"
        f.hp = 0
        f.died_round = self.round
        f.conditions = {}
        self._release(f)
        self._event("dead", who=f.id)
        if killer is not None and killer.bond is not None:
            killer = self.fighter(killer.bond["owner"])  # (what a familiar or a steed kills, its owner is known for)
        if f.creature and f.bond is not None and f.bond.get("kind") == "servant":
            f.creature.alive = False  # (the raised dead fall, and this time they stay down: Expansion 3 F.4)
            self._clear_bonded(f)
            self.say(f"{f.the_name[:1].upper() + f.the_name[1:]} falls apart, and nothing moves it again.", "danger")
        elif f.creature and f.bond is not None:
            f.creature.alive = False  # (it disappears at 0 hit points, leaving nothing: PHB 2024)
            self._clear_bonded(f)
            self._event("vanish", who=f.id)
            self.say(f"{f.the_name[:1].upper() + f.the_name[1:]} is gone, back to wherever it came from.", "danger")
        elif f.creature:
            f.creature.alive = False
            self.say(self._fill(self.rng.choice(self.t.combat_text["dead"]), killer, f), "good" if f.side == FOE else "danger")
            if killer is not None and killer.char:
                killer.char.kills[f.cdef["name"]] = killer.char.kills.get(f.cdef["name"], 0) + 1
        else:
            f.char.alive = False
            # What the chronicle will say: who did it, or what it was they bled to death fighting.
            if killer is not None and killer.creature is not None:
                f.char.death_cause = f"killed by {killer.the_name}"
            else:
                kinds = [x.cdef["plural"] for x in self.side(FOE) if x.creature is not None]
                f.char.death_cause = f"bled to death fighting {kinds[0]}" if kinds else "bled to death in a fight"
            self.say(f"<danger>{f.the_name} is dead.</> ({cause})", "danger")
            for x in self.fighters:  # (a steed disappears when its rider dies: PHB 2024)
                if x.bond is not None and x.bond.get("kind") == "steed" and x.bond["owner"] == f.id and x.active:
                    self._kill(x, "its rider is dead")
        self._morale_losses(f.side)
        events.emit(self, "killed", actor=killer, target=f)  # a leader's fall...

    # ------------------------------------------------------------------ morale
    def _morale_after_hit(self, f: Fighter) -> None:
        threshold = MORALE_HP.get(f.morale_type)
        if threshold is None or "hp" in f.morale_checked:
            return
        if f.hp / max(1, f.max_hp) < threshold:
            f.morale_checked.add("hp")
            self._morale_check(f, "hurt")

    def _morale_losses(self, side: str) -> None:
        if side != FOE:
            return
        lost = [f for f in self.side(FOE) if not f.active and f.bond is None]
        if len(lost) * 2 < self.initial_foes:
            return
        for f in self.side(FOE):
            if f.active and "losses" not in f.morale_checked:
                f.morale_checked.add("losses")
                self._morale_check(f, "losses")

    def _morale_check(self, f: Fighter, reason: str) -> None:
        if f.morale_type in FEARLESS or f.state != "fighting" or "possessed" in f.conditions or f.bond is not None:
            return  # (a familiar or a steed obeys: it does not run)
        dc = 10 + (2 if reason == "leader" else 0)
        roll = dice.d20(self.rng).natural + f.mod("wis")
        self.dice_say(f"{f.name} morale ({reason}): {roll} vs {dc}")
        if roll >= dc:
            return
        self._break(f)

    def _break(self, f: Fighter, force: str | None = None) -> None:
        mt = f.morale_type
        choice = force
        if choice is None:
            if mt in ("beast", "coward", "warrior"):
                choice = "flee"
            elif mt == "soldier":
                choice = "surrender"
            else:  # bandit: gives up if somebody has them hand to hand, runs if they can
                close = any(self.gap(f, e) <= 1 for e in self.enemies_of(f) if e.standing)
                choice = "surrender" if (close or "grappled" in f.conditions) else "flee"
        if "grappled" in f.conditions or "restrained" in f.conditions:
            choice = "surrender" if f.kind == "humanoid" else "fight"
        if choice == "fight":
            return
        if choice == "flee":
            f.state = "fleeing"
            self.say(self._fill(self.rng.choice(self.t.combat_text["flee"]), None, f), "good")
        else:
            f.state = "surrendered"
            f.conditions.pop("prone", None)
            self._release(f)
            text = self._fill(self.rng.choice(self.t.combat_text["surrender"]), None, f)
            self.say(text, "good")
            self._event("yield", who=f.id)
            if self.rng.chance(0.5):
                self.say(self.rng.choice(self.t.combat_text["beg"]), "speech")
        self._morale_losses(f.side)
        self._check_end()

    # ------------------------------------------------------------------ party actions
    def do_attack(self, f: Fighter, opt: AttackOption, target: Fighter) -> bool:
        """One attack. The first one takes the action (and with Extra Attack leaves more to make this turn, with
        movement between them if you like)."""
        if self.jar_still(f):
            return False
        why = self.attack_problem(f, opt, target)
        if why:
            return False
        if opt.extra.get("area"):  # (a creature's breath, played by the player: aimed at the target)
            self.area_attack(f, opt, (target.x, target.y))
            self._after_action(f)
            return True
        if f.attacks_left <= 0:
            f.action -= 1
            f.attacks_left = query.attacks_per_action(f)
            f.loaded_fired = False
            f.__dict__["struck_turn"] = f.spent_round
        f.attacks_left -= 1
        if "loading" in opt.properties and not opt.is_melee:
            f.loaded_fired = True
        self._attack(f, opt, target)
        if f.char and opt.key == "main" and "light" in opt.properties and opt.is_melee:
            f.light_attack = True
        self._after_action(f)
        return True

    def do_offhand(self, f: Fighter, target: Fighter) -> bool:
        opt = self.offhand_option(f)
        nick = mastery.nick_ready(self, f)
        if opt is None or not f.light_attack or f.offhand_done or (f.bonus <= 0 and not nick) \
                or not self.in_reach(f, opt, target)[0]:
            return False
        f.offhand_done = True
        if nick:
            mastery.once_a_turn(self, f, "nick")  # Nick: part of the Attack action; the bonus action is kept
        else:
            f.bonus -= 1
        self._attack(f, opt, target)
        self._after_action(f)
        return True

    def feat_blow_option(self, f: Fighter, ability: str) -> AttackOption | None:
        """The weapon blow a feat allows with the bonus action: Hew (Great Weapon Master) or the butt end (Polearm
        Master)."""
        if ability == "hew":
            key = general_feats.hew_ready(self, f)
            return next((o for o in self.attack_options(f) if o.key == key and o.available), None) if key else None
        if ability == "pole_strike" and not f.__dict__.get("pole_done") == self.round:
            return general_feats.pole_option(self, f)
        return None

    def do_feat_blow(self, f: Fighter, ability: str, target: Fighter) -> bool:
        opt = self.feat_blow_option(f, ability)
        if opt is None or f.bonus <= 0 or not self.in_reach(f, opt, target)[0]:
            return False
        f.bonus -= 1
        if ability == "hew":
            f.__dict__.pop("hew", None)
            self.say(f"{f.the_name} follows through with another great swing.", "warn" if f.side == FOE else "good")
        else:
            f.__dict__["pole_done"] = self.round
        self._attack(f, opt, target)
        self._after_action(f)
        return True

    def help_targets(self, f: Fighter) -> list[Fighter]:
        """Who the Help action can be for (2024): a friend beside you who is down (first aid) or asleep (shaken awake),
        or an enemy beside you, distracted so that a friend's next attack on it has advantage."""
        out = []
        for x in self.team(f.team):
            if x is f or self.gap(f, x) > 1:
                continue
            if x.state == "down" or x.active and ("unconscious" in x.conditions or "incapacitated" in x.conditions):
                out.append(x)
        out += [e for e in self.enemies_of(f) if e.standing and self.gap(f, e) <= 1]
        return out

    def do_help(self, f: Fighter, target: Fighter) -> None:
        if not self._spend(f):
            return
        if target.state == "down":
            kit = next((i for i in f.char.inventory if i.def_id == "healers_kit"), None) if f.char else None
            if kit is not None:
                ok = True
                self.say(f"{f.the_name} packs {target.the_name}'s wounds from the healer's kit.", "good")
            else:
                roll = dice.d20(self.rng).natural
                bonus = f.skill("medicine")
                ok = roll + bonus >= 10
                self.dice_say(f"Medicine ({f.name}): {roll} {signed_mod(bonus)} = {roll + bonus} vs DC 10")
            if ok:
                target.stable = True
                self.say(f"{target.the_name} is no longer bleeding out.", "good")
            else:
                self.say(f"{f.the_name} fumbles at the wound; the blood keeps coming.", "danger")
        elif target.team == f.team and ("unconscious" in target.conditions or "incapacitated" in target.conditions):
            for cid in ("unconscious", "incapacitated"):
                durations.remove(target, cid)
            self.say(f"{f.the_name} shakes {target.the_name} awake.", "good")
        else:
            foe = target if target.team != f.team else min(
                (e for e in self.enemies_of(f) if e.standing and self.gap(f, e) <= 1), key=lambda e: e.hp, default=None)
            if foe is not None:
                durations.buff(foe, {"distracted": f.team, "source": f"help:{f.id}"}, durations.until(self, f, "turn_start"))
                self.say(f"{f.the_name} feints at {foe.the_name}, opening a way for a friend.", "system")
        self._after_action(f)

    def _unarmed_save(self, att: Fighter, target: Fighter) -> bool:
        """A grapple or a shove (2024): the target makes a Strength or Dexterity save, whichever suits it, against
        8 + the attacker's Strength and proficiency."""
        ability = max(("str", "dex"), key=lambda ab: target.save_bonus(ab))
        return self._save(target, ability, query.unarmed_dc(att))

    def _use_attack(self, f: Fighter) -> bool:
        """One attack of the Attack action (a grapple or a shove replaces one, 2024)."""
        if f.attacks_left <= 0:
            if f.action <= 0:
                return False
            f.action -= 1
            f.attacks_left = query.attacks_per_action(f)
            f.loaded_fired = False
            f.__dict__["struck_turn"] = f.spent_round  # (a breath made with the Multiattack may still follow)
        f.attacks_left -= 1
        return True

    def can_grapple(self, att: Fighter, target: Fighter) -> tuple[bool, str]:
        if SIZES.index(target.size) > SIZES.index(att.size) + 1:
            return False, "too big to wrestle"
        if self.gap(att, target) > 1:
            return False, "not beside you"
        if not target.active:
            return False, "not in the fight"
        return True, ""

    def do_shove(self, f: Fighter, target: Fighter, mode: str) -> None:
        if not self.can_grapple(f, target)[0] or not self._use_attack(f):
            return
        if not self._unarmed_save(f, target):
            if mode == "prone":
                target.conditions["prone"] = -1
                self._event("prone", who=target.id)
                self.say(f"{f.the_name} knocks {target.the_name} off {target.possessive} feet.", "good")
            else:
                if self._push(f, target, 1):
                    self.say(f"{f.the_name} drives {target.the_name} back.", "good")
                else:
                    self.say(f"{f.the_name} shoves, but {target.the_name} has nowhere to go.", "system")
        else:
            self.say(f"{target.the_name} keeps {target.possessive} footing.", "system")
        self._after_action(f)

    def _push(self, src: Fighter | tuple, target: Fighter, squares: int) -> bool:
        """Push a creature straight away from a creature or a point, as far as there is room."""
        sx, sy = grid.centre(*src.space) if isinstance(src, Fighter) else (src[0] + 0.5, src[1] + 0.5)
        tx, ty = grid.centre(*target.space)
        dx = 0 if abs(tx - sx) < 0.5 else (1 if tx > sx else -1)
        dy = 0 if abs(ty - sy) < 0.5 else (1 if ty > sy else -1)
        if dx == 0 and dy == 0:
            return False
        path = []
        x, y = target.x, target.y
        occ = self.occupied_by_others(target)
        for _ in range(squares):
            nx, ny = x + dx, y + dy
            if not self.field.fits(nx, ny, target.sq) or any(c in occ for c in grid.cells(nx, ny, target.sq)):
                break
            path.append((nx, ny))
            x, y = nx, ny
        if not path:
            return False
        start = (target.x, target.y)
        target.x, target.y = path[-1]
        self._event("push", who=target.id, path=[start] + path)
        self._sync_grapples(target)
        self._zones_on(target, start=False)
        return True

    def _pull(self, src: Fighter, target: Fighter, squares: int) -> bool:
        """Pull a creature straight towards another, as far as there is room, until it stands beside it (Thorn
        Whip)."""
        path = []
        x, y = target.x, target.y
        occ = self.occupied_by_others(target)
        for _ in range(squares):
            if grid.gap((x, y, target.sq), src.space) <= 1:
                break
            sx, sy = grid.centre(*src.space)
            tx, ty = x + target.sq / 2, y + target.sq / 2
            dx = 0 if abs(tx - sx) < 0.5 else (-1 if tx > sx else 1)
            dy = 0 if abs(ty - sy) < 0.5 else (-1 if ty > sy else 1)
            nx, ny = x + dx, y + dy
            if (dx, dy) == (0, 0) or not self.field.fits(nx, ny, target.sq) \
                    or any(c in occ for c in grid.cells(nx, ny, target.sq)):
                break
            path.append((nx, ny))
            x, y = nx, ny
        if not path:
            return False
        start = (target.x, target.y)
        target.x, target.y = path[-1]
        self._event("push", who=target.id, path=[start] + path)
        self._sync_grapples(target)
        self._zones_on(target, start=False)
        return True

    def do_grapple(self, f: Fighter, target: Fighter) -> None:
        if not self.can_grapple(f, target)[0] or not self._use_attack(f):
            return
        self.grapple(f, target)
        self._after_action(f)

    def grapple(self, f: Fighter, target: Fighter, *, free: bool = False) -> bool:
        """The grab itself (the target saves against it); `free` when a feat gives it with a punch (Grappler)."""
        if not self._unarmed_save(f, target) and durations.give(self, target, "grappled", source=f,
                                                                escape=query.unarmed_dc(f)):
            target.grappled_by = f.id
            target.move_left = 0
            self.say(f"{f.the_name} gets a grip on {target.the_name} and holds on.", "good")
            return True
        self.say(f"{target.the_name} twists free of {f.the_name}'s grasp.", "system")
        return False

    def do_escape(self, f: Fighter) -> None:
        if not self._spend(f):
            return
        holder = next((x for x in self.fighters if x.id == f.grappled_by), None)
        dc = int(f.cond_ends.get("grappled", {}).get("escape") or (query.unarmed_dc(holder) if holder else 10))
        stuck = "grappled" if "grappled" in f.conditions else "restrained"
        skill = max(f.skill("athletics"), f.skill("acrobatics"))
        web = next((z for z in self.zones if z.holds and any(c in z.cells for c in f.cells)), None)
        if stuck == "restrained" and web is not None:
            dc, skill = web.dc, f.skill("athletics")  # 2024: a Strength (Athletics) check against the spell's DC
        if dice.d20(self.rng).natural + skill >= dc:
            durations.remove(f, stuck)
            f.grappled_by = None
            f.move_left = f.speed
            self.say(f"{f.the_name} breaks free.", "good")
        else:
            self.say(f"{f.the_name} cannot break the hold.", "danger")
        self._after_action(f)

    def parley_dc(self, approach: str) -> int | None:
        foes = [f for f in self.side(FOE) if f.active]
        if not foes:
            return None
        from realmwalker.rules import magic

        for p in self.side(PARTY):
            if p.char is None or not p.char.attuned:
                continue
            if approach == "calm" and magic.flag(p.char, "beasts_hate"):
                return None  # an artifact's flaw: no beast can abide its bearer
            hated = magic.flag_value(p.char, "hated_by")
            if hated and any(f.kind == hated for f in foes):
                return None
        if all(f.morale_type in FEARLESS for f in foes):
            return None
        if approach == "calm":
            if not all(f.kind == "beast" for f in foes):
                return None
            return 13 + len(foes)
        if any(f.kind == "beast" for f in foes):
            return None
        party = [f for f in self.side(PARTY) if f.standing and f.bond is None]  # (an owl does not make you more)
        hurt = sum(1 for f in foes if f.hp < f.max_hp) / len(foes)
        from realmwalker.rules import encounter

        # PHB 2024 Influence: 15 or their best Intelligence, whichever is higher; numbers and hurts move it.
        dc = encounter.influence_dc(self.t, [f.creature.def_id for f in foes if f.creature is not None]) - 3 \
            + 2 * (len(foes) - len(party)) - int(hurt * 4)
        if approach == "intimidate":
            dc += 2 if len(foes) > len(party) else -1
        return max(5, min(25, dc))

    def foe_attitude(self) -> str:
        """In a fight the enemy is Hostile (Influence at a disadvantage), until most of them are bloodied: then they
        are no longer set on it (Indifferent)."""
        foes = [f for f in self.side(FOE) if f.active]
        bloodied = sum(1 for f in foes if f.hp * 2 <= f.max_hp)
        return "indifferent" if foes and bloodied * 2 >= len(foes) else "hostile"

    def do_parley(self, f: Fighter, approach: str) -> None:
        dc = self.parley_dc(approach)
        skill = {"persuade": "persuasion", "intimidate": "intimidation", "calm": "animal_handling"}[approach]
        if not self._spend(f):
            return
        if dc is None:
            self.say("They are past listening.", "warn")
            self._after_action(f)
            return
        from realmwalker.rules import encounter

        mode = encounter.influence_mode(self.t, self.foe_attitude())
        roll = dice.d20(self.rng, advantage=mode == "advantage", disadvantage=mode == "disadvantage").natural
        bonus = f.skill(skill)
        how = {"advantage": " (adv)", "disadvantage": " (dis: hostile)"}.get(mode, "")
        self.dice_say(f"{self.t.rules['skills'][skill]['name']}{how} ({f.name}): {roll} {signed_mod(bonus)} = "
                      f"{roll + bonus} vs DC {dc}")
        lines = {"persuade": "'There's no profit in this. Walk away, and so will we.'",
                 "intimidate": "'Drop it, or I'll open you like a sack of grain.'",
                 "calm": f"{f.the_name} speaks low and steady, and makes no sudden moves."}
        self.say(lines[approach], "speech")
        if roll + bonus >= dc:
            foes = [x for x in self.side(FOE) if x.active]
            if approach == "intimidate":
                for x in foes:
                    self._break(x, "surrender" if x.kind == "humanoid" and x.morale_type != "warrior" else "flee")
            else:
                for x in foes:
                    x.state = "fled"
                    self._event("leave", who=x.id)
                self.say("They back off, weapons still raised, and are gone.", "good")
                self.outcome = "parley"
                return
        else:
            self.say("It doesn't work.", "warn")
        self._after_action(f)

    def surrender_possible(self) -> tuple[bool, str]:
        foes = [x for x in self.side(FOE) if x.active]
        if any(x.morale_type in MERCIFUL for x in foes):
            return True, ""
        return False, "these do not take prisoners"

    def do_surrender(self, f: Fighter) -> None:
        ok, why = self.surrender_possible()
        if not ok:
            self.say(f"You try to surrender. {why.capitalize()}.", "danger")
            return
        self.say(f"{f.the_name} throws down {f.possessive} weapon and raises empty hands.", "warn")
        self.outcome = "surrendered"

    # ------------------------------------------------------------------ items and abilities
    def usable_items(self, f: Fighter) -> list:  # (scrolls are read from the spell menu)
        """What can be used in a fight: potions and bandages on someone beside you, flasks thrown (aimed like a spell:
        "throw:<uid>:<spell>" through do_cast)."""
        if not f.char:
            return []
        return [i for i in f.char.inventory if BATTLE_USES & set(self.t.items.get(i.def_id).get("use") or {})]

    def throw_value(self, item) -> str | None:
        """The do_cast value for throwing this flask, or None if it is not thrown."""
        use = self.t.items.get(item.def_id).get("use") or {}
        sid = use.get("throw") or ("coat_poison" if use.get("coat") else None)  # (basic poison: smeared on a blade)
        return f"throw:{item.uid}:{sid}" if sid in self.t.spells else None

    def item_targets(self, f: Fighter) -> list[Fighter]:
        """Who you can reach to pour a potion into or bind: yourself and anyone beside you."""
        return [x for x in self.team(f.team) if (x.active or x.state == "down") and (x is f or self.gap(f, x) <= 1)]

    def fast_hands(self, f: Fighter) -> bool:
        """A thief can use an object with a bonus action (Cunning Action)."""
        return f.char is not None and f.has_trait("fast_hands") and f.bonus > 0

    def item_cost(self, f: Fighter, item) -> str:
        """What using this thing takes: a potion is drunk or given with the bonus action (DMG 2024); other things
        take the action (or a thief's bonus action: Fast Hands)."""
        return "bonus" if "heal" in (self.t.items.get(item.def_id).get("use") or {}) else "action"

    def item_problem(self, f: Fighter, item) -> str:
        """Why this thing cannot be used now ("" if it can)."""
        if self.item_cost(f, item) == "bonus":
            return "" if f.bonus > 0 else "no bonus action left this turn"
        return "" if f.action > 0 or self.fast_hands(f) else "no action left this turn"

    def do_item(self, f: Fighter, uid: int, target: Fighter) -> None:
        it = f.char.item(uid)
        if it is None or self.item_problem(f, it):
            return
        quick = self.item_cost(f, it) == "bonus" or f.action <= 0  # (a potion; or Fast Hands)
        d = self.t.items.get(it.def_id)
        use = d.get("use", {})
        name = d["name"]
        if "heal" in use:
            self._spend(f, quick)
            amount = dice.roll(use["heal"], self.rng).total
            self._heal(target, amount)
            self.say(f"{f.the_name} gets the {name} into {target.the_name}.", "good")
            remove_item(f.char, uid, 1)
        elif use.get("bandage"):
            bleeding = [w for w in target.wounds if w.bleed and not w.bandaged]
            if not bleeding:
                self.say(f"There is nothing on {target.the_name} that a bandage would stop.", "system")
                return
            self._spend(f, quick)
            roll = dice.d20(self.rng).natural
            bonus = f.skill("medicine")
            self.dice_say(f"Medicine ({f.name}): {roll} {signed_mod(bonus)} = {roll + bonus} vs DC 10")
            if roll + bonus >= 10:
                worst = max(bleeding, key=lambda w: w.bleed)
                worst.bandaged = True
                self.say(f"{f.the_name} binds {target.the_name}'s wound tight. The bleeding slows.", "good")
            else:
                self.say("The bandage soaks through at once.", "danger")
            if d.get("stack"):
                remove_item(f.char, uid, 1)
        else:
            return
        self._after_action(f)

    def class_abilities(self, f: Fighter) -> list[tuple[str, str, bool, str]]:
        """(id, name, available, why not): what features give (data/traits.json, rules/engine/actions.py), the off-hand
        blow of two-weapon fighting, and a spiritual weapon's strike."""
        jar = self._jar_abilities(f)
        if jar is not None:
            return jar
        if not f.char:
            return []
        out = []
        for a in actions.activations(f):
            why = actions.problem(self, f, a)
            out.append((a["id"], a["name"], why is None, why or ""))
        if self.offhand_option(f) is not None:
            nick = mastery.nick_ready(self, f)
            ok = (f.bonus > 0 or nick) and f.light_attack and not f.offhand_done
            at = max([0] + [i + 1 for i, row in enumerate(out)
                            if row[0] in ("second_wind", "action_surge") or row[0].startswith("cunning_")])
            out.insert(at, ("offhand", "Off-hand attack (Nick: part of the Attack)" if nick else
                            "Off-hand attack (bonus action)", ok,
                            "" if ok else ("attack with the main hand first" if f.bonus > 0 or nick
                                           else "no bonus action left")))
        for tok in self.tokens:
            if tok.owner == f.id and tok.kind == "spiritual_weapon":
                out.append(("spirit_strike", "Spiritual weapon: strike (bonus action)", f.bonus > 0,
                            "" if f.bonus > 0 else "no bonus action left"))
        if feats.has(f.char, "great_weapon_master") and general_feats.hew_ready(self, f):
            out.append(("hew", "Hew: strike again (bonus action)", True, ""))
        if feats.has(f.char, "polearm_master"):
            pole = general_feats.pole_option(self, f)
            ok = pole is not None and f.bonus > 0 and not f.__dict__.get("pole_done") == self.round
            out.append(("pole_strike", "Butt end of the polearm (bonus action)", ok,
                        "" if ok else ("attack with the polearm first" if f.bonus > 0 else "no bonus action left")))
        if self.burning(f):
            out.append(("put_out", "Put out the flames (roll on the ground)", f.action > 0,
                        "" if f.action > 0 else "no action left"))
        waiting = self.commanded_of(f)
        if waiting:
            told = all(x.bond.get("told") == self.round for x in waiting)
            near = [x for x in waiting if self.within_word(f, x)]
            ok = f.bonus > 0 and not told and bool(near)
            out.append(("command_objects", f"{self.command_words(f)} (bonus action)", ok,
                        "" if ok else ("they have their orders" if told else "no bonus action left" if f.bonus <= 0
                                       else "none of them is near enough to hear")))
        return out

    # ------------------------------------------------------------------ Animate Objects (Expansion 3 F.3)
    def objects_of(self, f: Fighter) -> list[Fighter]:
        """The things `f` animated that still stand."""
        return [x for x in self.allies_of_owner(f) if x.bond.get("kind") == "objects" and x.active]

    # ------------------------------------------------------------------ the raised dead (Expansion 3 F.4)
    def _turn_to_dust(self, att: Fighter, f: Fighter) -> None:
        """Brought to 0 hit points by a mummy's fist: dead at once, and nothing left but dust (only True Resurrection
        or a wish reaches them: game/revival.problem)."""
        if f.char is not None:
            from realmwalker.rules.servants import DUST

            f.char.effects[DUST] = 1.0
        self._kill(f, "the mummy's rot", killer=att)
        f.__dict__["risen"] = True  # (no body to raise or to speak with)
        self.say(f"{f.the_name[:1].upper() + f.the_name[1:]} withers to grey dust in a breath.", "danger")

    def mark_rising(self, caster: Fighter, victim: Fighter, cid: str) -> None:
        """A creature slain by Finger of Death will rise as `cid` at the start of its slayer's next turn."""
        rows = self.__dict__.setdefault("risings", [])
        if not any(r["who"] == victim.id for r in rows):
            rows.append({"by": caster.id, "who": victim.id, "as": cid})

    def _rise_as_zombies(self, f: Fighter) -> list[Fighter]:
        """Those `f` slew with Finger of Death stand up again as its zombies, where they fell; they act right after
        it and follow its spoken orders (no Bonus Action: played like any ally). A party caster keeps them after the
        fight (rules/servants.after); a foe's go with the fight."""
        from realmwalker.rules import servants

        rows = self.__dict__.get("risings") or []
        mine = [r for r in rows if r["by"] == f.id]
        self.__dict__["risings"] = [r for r in rows if r["by"] != f.id]
        out = []
        for r in mine:
            body = self.fighter(r["who"])
            if body is None or body.state != "dead" or body.__dict__.get("risen") or r["as"] not in self.t.creatures:
                continue
            body.__dict__["risen"] = True
            hp = servants.avg_hp(self.t, r["as"])
            uid = max([servants.UID + 5000] + [x.creature.uid + 1 for x in self.fighters if x.creature is not None])
            cr = Creature(uid=uid, def_id=r["as"], name=self.t.creatures[r["as"]]["name"], hp=hp, max_hp=hp,
                          named=False)
            z = self.add_ally(cr, f, "servant", spell="finger_of_death", type_="undead", point=(body.x, body.y))
            z.bond["word"] = False
            z.bond["keep"] = True
            self.say(f"{body.the_name[:1].upper() + body.the_name[1:]} jerks, and gets up again: a "
                     f"{cr.name}, and {f.the_name}'s.", "magic")
            out.append(z)
        return out

    @staticmethod
    def _needs_word(x: Fighter) -> bool:
        """An animated object, or a servant raised by Animate Dead or Create Undead (Expansion 3 F.4)."""
        return x.bond is not None and (x.bond.get("kind") == "objects"
                                       or x.bond.get("kind") == "servant" and bool(x.bond.get("word")))

    def commanded_of(self, f: Fighter) -> list[Fighter]:
        """Everything of `f`'s that waits for its word: animated objects and the raised dead still standing."""
        return [x for x in self.allies_of_owner(f) if self._needs_word(x) and x.active]

    def within_word(self, f: Fighter, x: Fighter) -> bool:
        """A command carries to an animated object anywhere, to the raised dead within their spell's reach."""
        if x.bond.get("kind") != "servant":
            return True
        return self.gap(f, x) * grid.SQUARE_FT <= int(x.bond.get("reach", 60))

    def command_words(self, f: Fighter) -> str:
        kinds = {x.bond.get("kind") for x in self.commanded_of(f)}
        if kinds == {"objects"}:
            return "Command the animated objects"
        return "Command the dead" if kinds == {"servant"} else "Command your servants"

    def command_objects(self, f: Fighter) -> bool:
        """The caster's Bonus Action: every thing it animated, and every one of its raised dead within the command's
        reach, acts on its next turn (otherwise it Dodges)."""
        things = [x for x in self.commanded_of(f) if self.within_word(f, x)]
        if not things or not self._spend(f, bonus=True):
            return False
        for x in things:
            x.bond["told"] = self.round
        kinds = {x.bond.get("kind") for x in things}
        if kinds == {"objects"}:
            what = "the animated thing" if len(things) == 1 else "the animated things"
        elif kinds == {"servant"}:
            what = f"the {things[0].cdef['name']}" if len(things) == 1 else "the dead"
        else:
            what = "the things and the dead that serve"
        self.say(f"{f.the_name} sends {what} against {f.possessive if f.char is not None else 'its'} foes.", "magic")
        self._after_action(f)
        return True

    def _waits_for_word(self, f: Fighter) -> bool:
        """An animated object or a raised servant with no command since its master's last turn takes the Dodge action
        as its turn begins (a creature that casts Animate Objects commands them as part of its own turn)."""
        if not self._needs_word(f) or not f.can_act():
            return False
        owner = self.fighter(f.bond["owner"])
        if owner is None or owner.char is None:
            return False
        if f.bond.get("told") == self.round:  # (its master commanded it on this round's turn)
            return False
        f.dodging = True
        f.action = 0
        kind = f.bond.get("kind")
        alike = [x for x in self.commanded_of(owner) if x.bond.get("kind") == kind]
        if alike and alike[0] is f:
            if kind == "objects":
                what = "the animated thing only keeps" if len(alike) == 1 else "the animated things only keep"
            else:
                what = f"the {f.cdef['name']} only keeps" if len(alike) == 1 else "the dead only keep"
            self.say(f"With no word from {owner.the_name}, {what} out of harm's way.", "system")
        return True

    def burning(self, f: Fighter) -> bool:
        return any(bf.get("burning") for bf in f.buffs)

    def do_extinguish(self, f: Fighter) -> None:
        """An action: down on the ground and rolling, and the fire is out (the Burning hazard)."""
        if not self.burning(f) or not self._spend(f):
            return
        f.buffs = [bf for bf in f.buffs if not bf.get("burning")]
        f.conditions["prone"] = -1
        self._event("prone", who=f.id)
        self.say(f"{f.the_name} throws {f.possessive if f.char else 'itself'} down and rolls the flames out.", "system")
        self._after_action(f)

    def _ability_cost(self, f: Fighter, aid: str) -> str:
        if aid == "offhand" and mastery.nick_ready(self, f):
            return "free"
        if aid in ("offhand", "spirit_strike", "hew", "pole_strike", "command_objects"):
            return "bonus"
        if aid == "put_out":
            return "action"
        a = actions.find(f, aid)
        return a["cost"] if a else "action"

    def bonus_options(self, f: Fighter) -> list[str]:
        """What `f` could still do with a bonus action this turn."""
        if f.bonus <= 0 or not f.can_act():
            return []
        out = [aid for aid, _, ok, _ in self.class_abilities(f) if ok and self._ability_cost(f, aid) == "bonus"]
        if f.char:
            for sid, ok, _ in self.spell_options(f):
                sp = self.t.spells[spell_id(sid)]
                if ok and cast_kind(f, sp) == "bonus":
                    out.append(sid)
            hurt = any(x.hp < x.max_hp for x in self.item_targets(f))
            for it in self.usable_items(f) if hurt else ():  # (a potion, with the bonus action: only worth it when
                if self.item_cost(f, it) == "bonus" and not self.item_problem(f, it):  # someone in reach is hurt)
                    out.append(f"item:{it.uid}")
        return out

    def do_ability(self, f: Fighter, ability: str, target: Fighter | None = None) -> None:
        """Use an ability (rules/engine/actions.use), the off-hand blow, or the spiritual weapon."""
        if ability == "offhand":
            if target is not None:
                self.do_offhand(f, target)
            return
        if ability == "put_out":
            self.do_extinguish(f)
            return
        if ability == "command_objects":
            self.command_objects(f)
            return
        if ability == "jar_possess":
            if target is not None:
                self.do_possess(f, target)
            return
        if ability == "jar_return":
            self.do_jar_return(f)
            return
        if ability == "jar_leave":
            self.do_jar_leave(f)
            return
        if ability in ("hew", "pole_strike"):
            if target is not None:
                self.do_feat_blow(f, ability, target)
            return
        if ability == "spirit_strike":
            tok = next((t for t in self.tokens if t.owner == f.id and t.kind == "spiritual_weapon"), None)
            if tok is None or target is None or not self._spend(f, bonus=True):
                return
            self._spirit_strike(f, tok, target)
            self._after_action(f)
            return
        actions.use(self, f, ability, target)

    def spirit_targets(self, f: Fighter) -> list[Fighter]:
        """Who the spiritual weapon can reach this turn: it moves twenty feet and strikes someone beside it."""
        tok = next((t for t in self.tokens if t.owner == f.id and t.kind == "spiritual_weapon"), None)
        if tok is None or self.antimagic([(tok.x, tok.y)]):
            return []
        return [e for e in self.enemies_of(f) if grid.gap((tok.x, tok.y, 1), e.space) <= 5 and not self.antimagic(e.cells)]

    def _spirit_strike(self, f: Fighter, tok: Token, target: Fighter) -> None:
        # The weapon flies to a free square beside its target (twenty feet at most), then strikes.
        if self.antimagic(target.cells) or self.antimagic([(tok.x, tok.y)]):
            self.say("The spell's conjured weapon wavers and fades where no magic works.", "system")
            return
        best = None
        occ = {c for x in self.on_field() for c in x.cells}
        for c in target.cells:
            for dx, dy in grid.DIRS8:
                sq = (c[0] + dx, c[1] + dy)
                if sq in occ or not self.field.passable(*sq):
                    continue
                d = grid.gap((tok.x, tok.y, 1), (sq[0], sq[1], 1))
                if d <= 4 and (best is None or d < best[0]):
                    best = (d, sq)
        if best is not None:
            start = (tok.x, tok.y)
            tok.x, tok.y = best[1]
            self._event("token_move", id=tok.id, path=[start, best[1]])
        name = self.t.spells[tok.spell]["name"].lower() if tok.spell in self.t.spells else "spiritual weapon"
        opt = AttackOption("spirit", name, "spell_melee", tok.bonus, tok.damage, tok.damage_type)
        self._event("token_strike", id=tok.id, to=target.id)
        if self._attack(f, opt, target):
            from realmwalker.rules.engine import effects

            effects.after_strike(self, f, tok, target)  # (Conjure Fey: the fear it brings)

    # ------------------------------------------------------------------ spells
    def creature_spells(self, f: Fighter) -> list[str]:
        """The spells a creature could cast right now (a slot left, the action or bonus action free)."""
        if f.creature is None or not f.cdef.get("spells"):
            return []
        out = []
        sc = f.cdef.get("spellcasting", {})
        for sid in f.cdef["spells"]:
            spell = self.t.spells.defs.get(sid)
            if spell is None or spell.get("cast") == "reaction" or spellrules.out_of_battle(spell):
                continue  # (Thaumaturgy and the like on a stat block: their use is outside a fight)
            level = spell["level"]
            per_day = self._per_day(f, sid)
            if per_day is not None:
                if per_day <= 0:
                    continue  # the 2025 way: so many times a day, no slots
            elif sid not in sc.get("at_will", []) and level and not any(n > 0 for n in f.slots[level - 1:]):
                continue
            slotted = bool(level) and per_day is None and sid not in sc.get("at_will", [])
            if self._casting_time_ok(f, spell, slotted)[0]:
                out.append(sid)
        return out

    def creature_cast(self, f: Fighter, sid: str, target: Fighter | None = None, slot_level: int | None = None,
                      point: tuple[int, int] | None = None) -> bool:
        """A creature casts one of its spells, with its own save DC and spell attack."""
        spell = self.t.spells[sid]
        if sid not in self.creature_spells(f):
            return False
        if self.antimagic(f.cells) or (target is not None and self.antimagic(target.cells)):
            return False
        mode = spell["target"]  # the same reach as anyone's spell
        if mode in ("enemy", "ally", "downed_ally", "dead_ally") and (target is None or target not in self.spell_targets(f, sid)):
            return False
        if mode in ("point", "direction") and (point is None or point not in self.spell_points(f, sid)):
            return False
        sc = f.cdef["spellcasting"]
        level = spell["level"]
        slot_i = None
        if self._per_day(f, sid) is not None:
            self._spend_per_day(f, sid)
        elif level and sid not in sc.get("at_will", []):
            if self.slot_used_now(f):
                return False
            slot_i = i = next(i for i in range(level - 1, len(f.slots)) if f.slots[i] > 0)
            if slot_level and slot_level - 1 >= i and slot_level <= len(f.slots) and f.slots[slot_level - 1] > 0:
                slot_i = i = slot_level - 1  # (a higher slot for more)
            f.slots[i] -= 1
            self.note_slot(f)
            level = i + 1
        bonus_cast = spell.get("cast") == "bonus"
        self._spend(f, bonus_cast)
        if bonus_cast:
            f.cast_bonus_spell = True
        else:
            f.cast_action_spell = True
        f.hidden = 0
        if not self.cast(f, sid, spell, target, point, up=max(0, level - spell["level"]), mod=f.mod(sc["ability"]),
                         dc=int(sc["dc"]), bonus=int(sc["attack"]), mult=1, level=level, slotted=slot_i is not None):
            if slot_i is not None:
                f.slots[slot_i] += 1  # (countered: the slot is not spent, 2024)
        self._check_end()
        return True

    def _per_day(self, f: Fighter, sid: str) -> int | None:
        """Casts left today of a spell a 2025 block lists as "N/day" (None if it is not one of those)."""
        sc = f.cdef.get("spellcasting") or {}
        for n, sids in (sc.get("per_day") or {}).items():
            if sid in sids:
                return f.creature.uses.setdefault(f"spell:{sid}", int(n))
        for pool, p in (sc.get("shared") or {}).items():
            if sid in p["spells"]:
                return f.creature.uses.setdefault(f"pool:{pool}", int(p["uses"]))
        return None

    def _spend_per_day(self, f: Fighter, sid: str) -> None:
        sc = f.cdef.get("spellcasting") or {}
        for pool, p in (sc.get("shared") or {}).items():
            if sid in p["spells"] and not any(sid in s for s in (sc.get("per_day") or {}).values()):
                f.creature.uses[f"pool:{pool}"] -= 1
                return
        f.creature.uses[f"spell:{sid}"] -= 1

    def spell_options(self, f: Fighter) -> list[tuple[str, bool, str]]:
        """(spell id, possible, why not). Scrolls in the pack appear as "scroll:<item uid>:<spell id>"."""
        if not f.char:
            return []
        out = []
        for sid in spellrules.known_spells(f.char, self.t):
            ok, why = spellrules.can_cast(f.char, self.t, sid)
            spell = self.t.spells[sid]
            if ok and spell["target"] == "self" and sid in spellrules.lasting(f.char, self.t):
                ok, why = False, "already working on you"
            if ok and (spellrules.has_op(spell, "identify") or spellrules.out_of_battle(spell)):
                ok, why = False, "not in a fight" if not spell.get("minutes") else \
                    f"it takes {spell['minutes']} minute{'s' if spell['minutes'] != 1 else ''} to cast: not in a fight"
            if ok and spell.get("cast") == "reaction":
                ok, why = False, ("a reaction: cast by itself when a foe nearby casts a spell" if sid == "counterspell"
                                  else "a reaction: cast by itself when a blow would land")
            if ok:
                ok, why = self._casting_time_ok(f, spell, spell["level"] > 0
                                                and not spellrules.free_cast(f.char, self.t, sid))
            out.append((sid, ok, why))
        again = again_spell(f, self.t)
        if again is not None:
            ok, why = self._casting_time_ok(f, self.t.spells[again], False)
            if ok and self.t.spells[again]["target"] == "point" and not self.spell_points(f, again):
                ok, why = False, "nowhere to aim it from here"  # (Tree Stride with no tree beside you)
            out.append((again, ok, why))
        for it in f.char.inventory:  # (a scroll: on the reader's spell list, or a thief's Use Magic Device)
            sid = self.t.items.get(it.def_id).get("use", {}).get("scroll")
            if sid in self.t.spells and not spellrules.has_op(self.t.spells[sid], "revive", "identify") \
                    and not spellrules.out_of_battle(self.t.spells[sid]) \
                    and self.t.spells[sid].get("cast") != "reaction":
                why = spellrules.scroll_problem(f.char, self.t, sid)
                ok = not why
                if ok and self.t.spells[sid]["target"] == "self" and sid in spellrules.lasting(f.char, self.t):
                    ok, why = False, "already working on you"
                if ok:
                    ok, why = self._casting_time_ok(f, self.t.spells[sid], False)
                out.append((f"scroll:{it.uid}:{sid}", ok, why))
        for src, sid, _ability in feats.innate_spells(f.char, self.t):  # a feat's or a lineage's spells
            sp = self.t.spells[sid]
            if sp.get("cast") == "reaction" or spellrules.has_op(sp, "revive", "identify"):
                continue
            ok, why = self._casting_time_ok(f, sp, False)
            left = sp["level"] == 0 or f.char.uses.get(feats.innate_key(src, sid), 0) > 0
            if ok and not left:
                ok, why = False, "once a long rest: used"
            if ok and spellrules.armour_problem(f.char, self.t):
                ok, why = False, spellrules.armour_problem(f.char, self.t)
            out.append((f"innate:{src}:{sid}", ok, why))
        from realmwalker.rules import magic

        for it, p in magic.charges(f.char):
            if p["spell"] in self.t.spells:
                left = magic.charges_left(p)
                ok, why = self._casting_time_ok(f, self.t.spells[p["spell"]], False)
                out.append((f"charge:{it.uid}:{p['spell']}", left > 0 and ok, why if left > 0 else "no charges left until dawn"))
        if self.antimagic(f.cells):
            out = [(sid, False, "magic does not work here") for sid, _, _ in out]
        return out

    def _wish_ok(self, f: Fighter) -> tuple[bool, str]:
        """Whether `f` can cast Wish now (to copy a spell with it)."""
        if f.char is None or "wish" not in self.t.spells or "wish" not in spellrules.known_spells(f.char, self.t):
            return False, "you cannot cast Wish"
        ok, why = spellrules.can_cast(f.char, self.t, "wish")
        if ok:
            ok, why = self._casting_time_ok(f, self.t.spells["wish"], True)
        return ok, why

    def wish_options(self, f: Fighter, *, short: bool = False) -> list[tuple[str, bool, str]]:
        """(value, possible, why not) for each spell Wish could copy now ("wish:copy:<spell id>"); `short`: only the
        mightiest (levels 7 and 8), for the Auto's quick weighing."""
        if f.char is None or "wish" not in spellrules.known_spells(f.char, self.t):
            return []
        ok, why = self._wish_ok(f)
        out = []
        for sid in spellrules.wish_copies(self.t):
            if short and self.t.spells[sid]["level"] < 7:
                continue
            out.append((f"wish:copy:{sid}", ok, why))
        return out

    def _casting_time_ok(self, f: Fighter, spell: dict, slotted: bool | None = None) -> tuple[bool, str]:
        """The action economy of spells: a bonus-action spell needs the bonus action, an ordinary one the action;
        and only one spell slot may be spent on a turn (2024; `slotted`: whether this casting would spend one, by
        default when the spell is not a cantrip). A cantrip, a scroll, an item's charge or a gift's spell may go
        beside a slotted spell."""
        if self.antimagic(f.cells):
            return False, "magic does not work here"
        if f.buff_value("befuddled") and not spell.get("ability") and "item" not in spell.get("classes", ()):
            return False, "befuddled: no spell will come (Befuddlement)"
        if f.buff_value("mist"):
            return False, "a drifting mist cannot cast (Gaseous Form)"
        if "V" in spell.get("components", ()) and self.silenced(f):
            return False, "no sound can be made here (Silence)"
        if cast_kind(f, spell) == "bonus":
            if f.bonus <= 0:
                return False, "no bonus action left"
        elif f.action <= 0 and f.attacks_left <= 0:
            return False, "no action left this turn"
        if (spell["level"] > 0 if slotted is None else slotted) and self.slot_used_now(f):
            return False, "one spell slot a turn: a slot has been spent this turn"
        return True, ""

    def slot_used_now(self, f: Fighter) -> bool:
        """Whether `f` has spent a spell slot on this turn (anyone's turn: a reaction counts on the turn it is
        taken)."""
        return f.slot_turn == (self.round, self.turn)

    def note_slot(self, f: Fighter) -> None:
        f.slot_turn = (self.round, self.turn)

    def spell_range(self, spell: dict, f: Fighter | None = None) -> int:
        r = spell.get("range", 60)
        if r == "touch":
            return 5
        if r == "self":
            return 0
        if spell.get("range_scaling") and f is not None and f.char is not None:
            return int(r) * 2 ** (spellrules.cantrip_multiplier(f.char.level) - 1)  # Spare the Dying: 15, 30, 60 feet
        if f is not None and f.char is not None and int(r) >= 10 and feats.has(f.char, "spell_sniper") \
                and spellrules.has_op(spell, "attack"):
            return int(r) + 60  # (Spell Sniper: spells with an attack roll)
        return int(r)

    def spell_targets(self, f: Fighter, sid: str) -> list[Fighter]:
        spell = self.t.spells[spell_id(sid)]
        target = spell["target"]
        reach = self.spell_range(spell, f)

        def near(x: Fighter) -> bool:
            if x is f:
                return True
            return self.feet(f, x) <= max(5, reach) and self.field.cover(f.space, x.space) != grid.TOTAL

        if target == "enemy":
            return [x for x in self.enemies_of(f) if near(x)]
        if target == "ally":
            return [x for x in self.team(f.team) if (x.active or x.state == "down") and near(x)
                    and not (spell.get("others") and x is f)]
        if target == "downed_ally":
            return [x for x in self.team(f.team) if x.state == "down" and not x.stable and near(x)]
        if target == "bound":  # (a follow-up at the creature the spell was cast at: Witch Bolt, Heat Metal)
            held = (f.concentration or {}).get("target")
            return [x for x in self.fighters if x.id == held and x.active and x is not f and near(x)]
        if target == "dead_ally":
            return [x for x in self.team(f.team) if x.state == "dead" and self.round - x.died_round <= 10 and near(x)
                    and x.char is not None]
        return []

    def spell_points(self, f: Fighter, sid: str) -> set[tuple[int, int]]:
        """Squares a spell aimed at a point (or in a direction) can be aimed at."""
        spell = self.t.spells[spell_id(sid)]
        if spell["target"] == "direction":
            out = set()
            for x in range(self.field.width):
                for y in range(self.field.height):
                    if (x, y) not in f.cells:
                        out.add((x, y))
            return out
        reach = self.spell_range(spell)
        n = reach // grid.SQUARE_FT
        occ = {c for x in self.on_field() for c in x.cells} if spellrules.has_op(spell, "teleport", "summon", "guardian") \
            else set()
        out = set()
        near = (spellrules.op(spell, "teleport") or {}).get("near")  # (Tree Stride: from beside a tree to beside one)
        if near == "tree" and not self._beside_tree(f.cells):
            return out
        for x in range(max(0, f.x - n), min(self.field.width, f.x + f.sq + n)):
            for y in range(max(0, f.y - n), min(self.field.height, f.y + f.sq + n)):
                if grid.gap(f.space, (x, y, 1)) > n:
                    continue
                if self.field.solid[x, y]:
                    continue
                if occ and ((x, y) in occ or not self.field.passable(x, y)):
                    continue
                if near == "tree":
                    if not self._beside_tree([(x, y)]):
                        continue  # (a tree strider knows where every tree is: it need not see the place)
                elif not self.can_see_point(f, x, y):
                    continue
                out.add((x, y))
        return out

    def _beside_tree(self, cells) -> bool:
        tree = self.field.tree
        return any(tree[x + dx, y + dy] for x, y in cells for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                   if self.field.in_bounds(x + dx, y + dy))

    def spell_area(self, f: Fighter, sid: str, point: tuple[int, int] | None, target: Fighter | None = None) -> list[tuple[int, int]]:
        spell = self.t.spells[spell_id(sid)]
        area = spell.get("area")
        if not area:
            if target is not None:
                return list(target.cells)
            return []
        if spell["target"] == "self":
            point = (f.x, f.y)
            if area["shape"] == "emanation":
                return self.field.area("emanation", int(area["size"]), origin=f.space, toward=point)
            return self.field.area(area["shape"], int(area["size"]) + (f.sq - 1) * 5 // 2,
                                   origin=f.space, toward=point) + list(f.cells) if area["shape"] in ("sphere", "radius") else []
        if point is None:
            return []
        cells = self.field.area(area["shape"], int(area["size"]), origin=f.space, toward=point,
                                from_self=spell["target"] == "direction")
        if spell.get("spheres"):  # (Meteor Swarm: more spheres, each creature caught once)
            cells = self._more_spheres(f, spell, cells, int(spell["spheres"]) - 1)
        return cells

    def sculpted(self, f: Fighter, sid: str, victims: list[Fighter], level: int | None = None) -> set[int]:
        """An evoker's Sculpt Spells: up to one plus the spell's level of their friends caught in the area are left
        untouched."""
        spell = self.t.spells[spell_id(sid)]
        if f.char is None or not f.has_trait("sculpt_spells") or spell.get("school") != "evocation":
            return set()
        n = 1 + (level if level is not None else spell["level"])
        friends = [x for x in victims if x.team == f.team]
        return {x.id for x in friends[:n]}

    def in_area(self, cells: list[tuple[int, int]], who: str = "all", caster: Fighter | None = None) -> list[Fighter]:
        cs = set(cells)
        out = []
        for x in self.fighters:
            if not (x.active or x.state == "down"):
                continue
            if who == "enemies" and caster is not None and x.team == caster.team:
                continue
            if who == "allies" and caster is not None and x.team != caster.team:
                continue
            if any(c in cs for c in x.cells):
                out.append(x)
        return out

    def silenced(self, f: Fighter) -> bool:
        """Whether a creature stands in a Silence: no spell with a Verbal component can be cast there."""
        return any(z.kind == "silence" and z.cells & set(f.cells) for z in self.zones)

    def antimagic(self, cells) -> bool:
        """Whether any of these squares lies in an antimagic area (no spell works there, 2024)."""
        cells = set(cells)
        return any(z.kind == "antimagic" and z.cells & cells for z in self.zones)

    def cast_problem(self, f: Fighter, sid: str, target: Fighter | None = None, point: tuple[int, int] | None = None) -> str | None:
        spell = self.t.spells[spell_id(sid)]
        if self.antimagic(f.cells) or (target is not None and self.antimagic(target.cells)) or \
                (point is not None and self.antimagic([point])):
            return "magic does not work there"
        if sid.startswith("throw:"):
            if f.char is None or f.char.item(int(sid.split(":")[1])) is None:
                return "you have none left"
            if spell.get("cast") == "bonus":
                if f.bonus <= 0:
                    return "no bonus action left this turn"
            elif f.action <= 0 and f.attacks_left <= 0:
                return "no action left this turn"
        if sid.startswith("wish:"):  # (a spell copied by Wish: Wish's own action and slot)
            ok, why = self._wish_ok(f)
            if not ok:
                return why
        opts = {s: (ok, why) for s, ok, why in self.spell_options(f)} \
            if not sid.startswith(("throw:", "wish:")) else {}
        if sid in opts and not opts[sid][0]:
            return opts[sid][1]
        mode = spell["target"]
        if mode in ("enemy", "ally", "downed_ally", "dead_ally", "bound"):
            if target is None or target not in self.spell_targets(f, sid):
                return "out of reach" if target is not None else "no target"
        elif mode in ("point", "direction"):
            if point is None or point not in self.spell_points(f, sid):
                return "you cannot aim it there"
        return None

    def do_cast(self, f: Fighter, sid: str, target: Fighter | None = None, slot_level: int | None = None,
                point: tuple[int, int] | None = None) -> bool:
        if sid.startswith("wish:redo:"):  # (Wish's Roll Redo: no spell, no aim)
            return self.do_redo(f, int(sid.split(":")[2]))
        if self.jar_still(f):
            return False
        if f.char is None and f.creature is not None:  # (a creature the player commands: a steed's gift)
            if sid not in self.creature_spells(f):
                self.say("Not possible now.", "warn")
                return False
            return self.creature_cast(f, sid, target, point=point)
        why = self.cast_problem(f, sid, target, point)
        if why:
            self.say(f"Not possible: {why}.", "warn")
            return False
        scroll = None
        charged = None
        innate = None
        if sid.startswith("wish:"):
            return self._cast_wished(f, spell_id(sid), target, point)
        if sid.startswith("innate:"):
            _, src, sid = sid.split(":", 2)
            innate = next((a for s_, x, a in feats.innate_spells(f.char, self.t) if s_ == src and x == sid), None)
            if innate is None:
                return False
            if self.t.spells[sid]["level"] > 0:
                key = feats.innate_key(src, sid)
                f.char.uses[key] = max(0, f.char.uses.get(key, 0) - 1)
        if sid.startswith("charge:"):
            _, uid, sid = sid.split(":", 2)
            item = f.char.item(int(uid))
            from realmwalker.rules import magic

            charged = next((p for p in magic.props(item) if p.get("kind") == "charges" and p.get("spell") == sid),
                           None) if item is not None else None
            if charged is None or magic.charges_left(charged) <= 0:
                self.say("It has no power left until dawn.", "warn")
                return False
            spent = False if f.has_trait("use_magic_device") and self.rng.randint(1, 6) == 6 \
                else magic.spend_charge(charged, self.rng)  # (a thief's Use Magic Device: a 6 keeps the charge)
            self.say(f"{f.the_name} calls on the power in the {self.t.items.name(item, False)}"
                     f"{'' if spent or charged.get('at_will') else ', and the power stays in it'}.", "magic")
        if sid.startswith("scroll:"):
            _, uid, sid = sid.split(":", 2)
            scroll = f.char.item(int(uid))
            if scroll is None:
                return False
        flask = None
        if sid.startswith("throw:"):
            _, uid, sid = sid.split(":", 2)
            flask = f.char.item(int(uid))
            if flask is None:
                return False
        spell = self.t.spells[sid]
        c = f.char
        s = f.sheet
        level = spell["level"]
        bonus_cast = cast_kind(f, spell) == "bonus"
        if spell.get("again_of"):
            if again_spell(f, self.t) != sid:
                return False
            level = 0  # (the spell already paid for: no slot)
        if flask is not None:
            # A flask thrown: the thrower's aim makes it hard to dodge (8 + proficiency + Dexterity); no magic is spent.
            remove_item(c, flask.uid, 1)
            self._spend(f, bonus_cast)
            f.hidden = 0
            dc = 8 + s.proficiency + s.mod("dex")
            self.cast(f, sid, spell, target, point, up=0, mod=s.mod("dex"), dc=dc, bonus=s.proficiency + s.mod("dex"),
                      mult=1, level=0)
            self._after_action(f)
            return True
        scroll_how = None
        if scroll is not None:  # (DMG 2024 Spell Scroll; spells.scroll_reader)
            scroll_how = spellrules.scroll_reader(c, self.t, sid)
            if scroll_how is None:
                self.say("The writing on the scroll means nothing to you.", "warn")
                return False
            check = spellrules.scroll_check(s, self.t, sid, scroll_how)
            if check is not None:
                bonus, dc, words = check
                roll = dice.d20(self.rng).natural
                self.dice_say(f"{words} ({f.name}), reading a scroll above you: {roll} {signed_mod(bonus)} = "
                              f"{roll + bonus} vs DC {dc}")
                if roll + bonus < dc:
                    remove_item(c, scroll.uid, 1)
                    self._spend(f, bonus_cast)
                    f.hidden = 0
                    if bonus_cast:
                        f.cast_bonus_spell = True
                    else:
                        f.cast_action_spell = True
                    self.say(f"{f.the_name} stumbles over the words of the scroll; they fade from the page, and it "
                             f"crumbles to dust.", "warn")
                    self._after_action(f)
                    return True
            self.say(f"{f.the_name} reads from a scroll.", "magic")
            level = 0  # the scroll's own magic: no spell slot
        if charged is not None or innate is not None:
            level = 0  # the item's own magic, or a gift of blood or training (no slot)
        if level > 0 and f.__dict__.get("free_slot", 0) >= level:
            level = 0  # (the god casts it: Divine Intervention, War God's Blessing)
        at_will = spellrules.free_cast(c, self.t, sid, slot_level) if level > 0 else None
        if at_will:  # (a wizard's Spell Mastery or Signature Spells: at the spell's own level, no slot)
            spellrules.spend_free(c, sid, at_will)
            slot_level = level
            level = 0
        slotted = False
        if level > 0:
            if slot_level and slot_level not in spellrules.slot_choices(c, self.t, sid):
                self.say(f"No level {slot_level} spell slot left for that.", "warn")
                return False
            slot_level = slot_level or spellrules.lowest_free_slot(c, self.t, level)
            if slot_level is None:
                self.say("No spell slot left for that.", "warn")
                return False
            if self.slot_used_now(f):
                self.say("Only one spell slot can be spent on a turn.", "warn")
                return False
            spellrules.spend_slot(c, slot_level)
            self.note_slot(f)
            slotted = True
        self._spend(f, bonus_cast)
        if bonus_cast:
            f.cast_bonus_spell = True
        else:
            f.cast_action_spell = True
        f.hidden = 0
        up = max(0, (slot_level or level) - spell["level"])  # (0 for a free cast at its own level)
        if spell.get("again_of"):
            up = int((f.concentration or {}).get("up", 0))  # (as strong as the spell was cast)
        mod = s.mod(spellrules.casting_ability(c, self.t))
        dc = spellrules.save_dc(s, self.t)
        bonus = spellrules.attack_bonus(s, self.t) + s.attack_condition()
        if innate is not None:  # cast with the ability the feat or the lineage names
            mod = s.mod(innate)
            dc = 8 + s.proficiency + mod
            bonus = s.proficiency + mod + s.attack_condition()
        if scroll is not None:  # the scroll's own numbers, by the spell's level (data/rules.json spell_scrolls)
            mod = s.mod(spellrules.scroll_ability(c, self.t, scroll_how))
            dc, bonus = spellrules.scroll_numbers(self.t, spell["level"])
            bonus += s.attack_condition()
        mult = spellrules.cantrip_multiplier(c.level) if spell["level"] == 0 else 1  # (Cantrip Upgrade: 5, 11, 17)
        strained = spellrules.strain(c, slot_level or spell["level"], self.rng) \
            if scroll is None and charged is None else 0
        held = self.cast(f, sid, spell, target, point, up=up, mod=mod, dc=dc, bonus=bonus, mult=mult,
                         level=slot_level or level, slotted=slotted)
        if not held:
            strained = 0  # (countered: no spell was cast)
            if slotted:
                spellrules.unspend_slot(c, slot_level)  # (countered: the slot is not spent, 2024)
            if scroll is not None:
                self.say("The spell is lost and so is the turn's casting, but the scroll's words hold: it can be read "
                         "again another turn.", "magic")
        elif scroll is not None:
            remove_item(c, scroll.uid, 1)  # (it crumbles once the spell is cast)
            self.say("The scroll crumbles to dust as the last word is spoken.", "magic")
        elif charged is None and innate is None:
            used = spellrules.spend_material(c, self.t, sid)
            if used:
                self.say(f"The {used} is gone into the spell.", "magic")
        self._strain(f, strained)
        if spell.get("stress") and held:  # (Wish used for anything but a copy)
            for line in spellrules.wish_stress(c, self.rng):
                self.say(line, "danger")
        self._after_action(f)
        return True

    def _strain(self, f: Fighter, amount: int) -> None:
        """An earlier Wish's stress: the spell just cast tears at its caster (necrotic; nothing reduces it)."""
        if amount > 0 and f.active:
            self.say(f"Casting tears at {f.the_name}: the strain of the wish.", "danger")
            self._hit(None, f, amount, "necrotic", crit=False, weapon="the strain of a wish", raw=True)

    # ------------------------------------------------------------------ great magic (Expansion 3 E.7)
    def _contingency(self, f: Fighter, trigger: str) -> None:
        """Contingency: the spell that waited on `f` takes effect on them alone, now, without an action, when its
        moment comes (as the fight begins, below half the hit points, falling). It needs the statuette at hand."""
        c = f.char
        rec = (c.spells or {}).get("contingency") if c is not None else None
        if not rec or rec.get("trigger") != trigger or rec.get("spell") not in self.t.spells:
            return
        c.spells.pop("contingency", None)
        if not any(it.def_id == "contingency_statuette" for x in self.side(PARTY) if x.char is not None
                   for it in x.char.inventory):
            self.say(f"The Contingency on {f.the_name} is gone: the statuette is not with them.", "warn")
            return
        sid = rec["spell"]
        spell = self.t.spells[sid]
        level = int(rec.get("slot", spell["level"]))
        s = f.sheet
        self.say(f"<magic>Contingency:</> the {spell['name']} waiting on {f.the_name} springs into being.", "magic")
        effects.cast(self, f, sid, spell, f, (f.x, f.y), up=max(0, level - int(spell["level"])),
                     mod=s.mod(spellrules.casting_ability(c, self.t)), dc=spellrules.save_dc(s, self.t),
                     bonus=spellrules.attack_bonus(s, self.t) + s.attack_condition(), mult=1, level=level,
                     slotted=True)

    def jar_still(self, f: Fighter) -> bool:
        """A body whose soul is in its gem (Magic Jar): it strikes, casts and moves no more."""
        return f.jar is not None

    def ridden(self, f: Fighter) -> bool:
        """A foe's body that the player's soul has taken (Magic Jar), played by the player."""
        e = f.cond_ends.get("possessed") if "possessed" in f.conditions else None
        body = self.fighter(e["jar"]) if e and e.get("jar") is not None else None
        return body is not None and body.side == PARTY and not body.auto

    def _body_of(self, host: Fighter) -> Fighter | None:
        e = host.cond_ends.get("possessed") if "possessed" in host.conditions else None
        return self.fighter(e["jar"]) if e and e.get("jar") is not None else None

    def jar_targets(self, f: Fighter) -> list[Fighter]:
        """Who a soul in its gem could take: a humanoid foe within 100 feet that it sees, not one that threw it off
        (for a day), and not one warded against fiends and the dead."""
        if f.jar is None or f.jar.get("host") is not None:
            return []
        n = 100 // grid.SQUARE_FT
        return [e for e in self.enemies_of(f) if e.active and e.creature is not None and e.kind == "humanoid"
                and e.id not in f.jar["tried"] and self.gap(f, e) <= n and self.can_see(f, e)
                and "possessed" not in e.conditions and not any(bf.get("warded_kinds") for bf in e.buffs)]

    def _jar_abilities(self, f: Fighter) -> list[tuple[str, str, bool, str]] | None:
        """What a soul in a gem may do (Possess, Return), and a taken body's way back (Leave); None for anyone else."""
        if f.jar is not None and f.jar.get("host") is None:
            free = f.action > 0
            near = self.jar_targets(f)
            return [("jar_possess", "Possess a humanoid foe (Magic Jar: a Charisma save)", free and bool(near),
                     "" if free and near else ("no action left" if not free else "no humanoid foe within 100 feet in sight")),
                    ("jar_return", "Return to the body (Magic Jar ends; the gem shatters)", free,
                     "" if free else "no action left")]
        if "possessed" in f.conditions:
            body = self._body_of(f)
            near = body is not None and self.gap(f, body) <= 100 // grid.SQUARE_FT
            ok = f.action > 0 and near
            return [("jar_leave", "Leave this body (back into the gem)", ok,
                     "" if ok else ("no action left" if f.action <= 0 else "the gem is more than 100 feet away"))]
        return None

    def do_possess(self, f: Fighter, target: Fighter) -> None:
        """Magic Jar: the soul leaps from its gem into a humanoid foe, which makes a Charisma save."""
        if target not in self.jar_targets(f) or not self._spend(f):
            return
        self._event("cast", by=f.id, to=target.id, spell="magic_jar", effect="charm", look="ray", dtype="",
                    area=[], point=None, shape="")
        if self._save(target, "cha", int(f.jar["dc"])):
            f.jar["tried"].append(target.id)
            self.say(f"{target.the_name} throws off the soul that reached for it.", "info")
        else:
            durations.give(self, target, "possessed", source=f, control=PARTY, jar=f.id)
            f.jar["host"] = target.id
            target.dodging = False
            self.say(f"<magic>{f.the_name}'s soul pours into {target.the_name}:</> its body is theirs now, and its own "
                     "soul cries out from the gem.", "magic")
        self._after_action(f)

    def do_jar_leave(self, host: Fighter) -> None:
        """Magic Jar: the soul goes back into its gem; the host's own soul returns to its body."""
        body = self._body_of(host)
        if body is None or self.gap(host, body) > 100 // grid.SQUARE_FT or not self._spend(host):
            return
        durations.remove(host, "possessed")
        body.jar["host"] = None
        self.say(f"{body.the_name}'s soul leaves {host.the_name}, which staggers, itself again.", "magic")
        self._after_action(host)

    def do_jar_return(self, f: Fighter) -> None:
        """Magic Jar: the soul goes home to its body, and the spell ends; the gem shatters."""
        if f.jar is None or f.jar.get("host") is not None or not self._spend(f):
            return
        f.jar = None
        if not (f.char is not None and f.char.uses.get("addled")):
            durations.remove(f, "incapacitated")
        if f.char is not None:
            f.char.spells.pop("jar", None)
        self.say(f"<magic>{f.the_name} draws a breath:</> the soul is home, and the gem cracks to pieces.", "magic")
        self._after_action(f)

    def _host_dies(self, host: Fighter) -> None:
        """The body the soul had taken dies: a Charisma save against the caster's own DC sends it back to the gem;
        a failure is death."""
        body = self._body_of(host)
        durations.remove(host, "possessed")
        if body is None or body.jar is None:
            return
        body.jar["host"] = None
        if self._save(body, "cha", int(body.jar["dc"])):
            self.say(f"{body.the_name}'s soul tears free of the dying body and flees back into the gem.", "magic")
        else:
            self._kill(body, "the soul went down with the body it had taken")

    def _body_dies(self, f: Fighter) -> None:
        """A body whose soul was away dies: the soul dies with it (Magic Jar), and a host goes free."""
        host = self.fighter(f.jar["host"]) if f.jar and f.jar.get("host") is not None else None
        if host is not None:
            durations.remove(host, "possessed")
        f.jar = None
        if f.char is not None:
            f.char.spells.pop("jar", None)

    def _jar_release(self) -> None:
        """At the end of a fight, a soul in a taken body goes back to its gem; the body, itself again, runs."""
        for host in [x for x in self.fighters if "possessed" in x.conditions]:
            body = self._body_of(host)
            durations.remove(host, "possessed")
            if body is not None and body.jar is not None:
                body.jar["host"] = None
            if host.active and host.side == FOE:
                host.state = "fled"
                self._event("leave", who=host.id)
                self.say(f"{host.the_name}, its soul its own again, stumbles away and runs.", "info")

    def redo_options(self, f: Fighter) -> list[tuple[int, str, bool, str]]:
        """Roll Redo: the foes' hits on friends since this caster's last turn, (event index, words, possible, why)."""
        ok, why = self._wish_ok(f)
        out = []
        for i, ev in enumerate(self.events):
            if ev.get("kind") != "attack" or not ev.get("hit") or ev.get("redone") or "bonus" not in ev:
                continue
            if int(ev.get("round", 0)) < self.round - 1:
                continue
            att, x = self.fighter(ev["by"]), self.fighter(ev["to"])
            if att is None or x is None or att.team == f.team or x.team != f.team or x.state == "dead":
                continue
            dealt = self._blow_damage(i)
            if dealt <= 0:
                continue
            out.append((i, f"{att.the_name}'s {'critical ' if ev.get('crit') else ''}hit on {x.the_name} with "
                           f"{ev.get('weapon', 'a blow')} ({dealt} damage)", ok, why))
        return out

    def _blow_damage(self, i: int) -> int:
        """The damage the attack of event `i` did to its target (until the next attack)."""
        ev = self.events[i]
        total = 0
        for e in self.events[i + 1:]:
            if e.get("kind") == "attack":
                break
            if e.get("kind") == "damage" and e.get("to") == ev["to"] and e.get("by") == ev["by"]:
                total += int(e.get("amount", 0))
        return total

    def do_redo(self, f: Fighter, i: int) -> bool:
        """Wish's Roll Redo (PHB 2024): a foe's hit on a friend in the last round is rolled again with Disadvantage.
        A miss undoes it (its damage given back); a critical that is not one again gives back half. The stress."""
        if not any(j == i and ok for j, _w, ok, _why in self.redo_options(f)):
            return False
        c = f.char
        wish = self.t.spells["wish"]
        slot = spellrules.lowest_free_slot(c, self.t, 9)
        if slot is None:
            return False
        spellrules.spend_slot(c, slot)
        self.note_slot(f)
        self._spend(f, False)
        f.cast_action_spell = True
        f.hidden = 0
        strained = spellrules.strain(c, 9, self.rng)
        if self._countered(f, "wish", wish):
            spellrules.unspend_slot(c, slot)
            self._after_action(f)
            return True
        ev = self.events[i]
        ev["redone"] = True
        att, x = self.fighter(ev["by"]), self.fighter(ev["to"])
        dealt = self._blow_damage(i)
        self.say(f"{f.the_name} speaks a <magic>Wish</>, and the last moments run back.", "magic")
        roll = dice.d20(self.rng, disadvantage=True).natural
        total = roll + int(ev["bonus"])
        hit = roll == 20 or (roll != 1 and total >= int(ev["ac"]))
        self.dice_say(f"{att.name} → {x.name}, again (dis): {roll} {signed_mod(int(ev['bonus']))} = {total} vs AC "
                      f"{ev['ac']} — {'critical!' if roll == 20 else ('hit' if hit else 'miss')}")
        back = dealt if not hit else (dealt // 2 if ev.get("crit") and roll != 20 else 0)
        if back > 0:
            self._undo_damage(x, back)
            self.say(f"<good>{'The blow never landed' if not hit else 'It was no critical after all'}:</> "
                     f"{x.the_name} {'has back' if not hit else 'gets back'} {back} hit points.", "good")
        else:
            self.say(f"Reality bends and settles: {att.the_name}'s blow lands all the same.", "warn")
        self._strain(f, strained)
        for line in spellrules.wish_stress(c, self.rng):
            self.say(line, "danger")
        self._after_action(f)
        return True

    def _undo_damage(self, x: Fighter, amount: int) -> None:
        """Hit points given back by an undone blow (not healing: nothing can refuse it)."""
        x.hp = min(x.max_hp, x.hp + amount)
        self._event("heal", to=x.id, amount=amount)
        if x.state == "down" and x.hp > 0:
            x.state = "fighting"
            x.conditions.pop("unconscious", None)
            x.stable = False
            x.death_saves = [0, 0]

    def _cast_wished(self, f: Fighter, sid: str, target, point) -> bool:
        """Wish's basic use (PHB 2024): any other spell of level 8 or lower simply takes effect, with no components
        and nothing else asked of it; the Wish's action and its level 9 slot are what it costs, and no stress."""
        c = f.char
        wish = self.t.spells["wish"]
        spell = self.t.spells[sid]
        slot = spellrules.lowest_free_slot(c, self.t, 9)
        if slot is None:
            self.say("No spell slot left for that.", "warn")
            return False
        spellrules.spend_slot(c, slot)
        self.note_slot(f)
        self._spend(f, False)
        f.cast_action_spell = True
        f.hidden = 0
        strained = spellrules.strain(c, 9, self.rng)
        if self._countered(f, "wish", wish):
            spellrules.unspend_slot(c, slot)  # (countered: the slot is not spent, 2024)
            self._after_action(f)
            return True
        self.say(f"{f.the_name} speaks a <magic>Wish</>.", "magic")
        s = f.sheet
        mod = s.mod(spellrules.casting_ability(c, self.t))
        effects.cast(self, f, sid, spell, target, point, up=0, mod=mod, dc=spellrules.save_dc(s, self.t),
                     bonus=spellrules.attack_bonus(s, self.t) + s.attack_condition(), mult=1, level=spell["level"],
                     slotted=True)
        self._strain(f, strained)
        self._after_action(f)
        return True

    def cast(self, f: Fighter, sid: str, spell: dict, target: Fighter | None, point: tuple[int, int] | None, *,
             up: int, mod: int, dc: int, bonus: int, mult: int, level: int, slotted: bool = True) -> bool:
        """A spell's effects, once it has been paid for (rules/engine/effects.py); False if a foe's Counterspell
        stopped it (the action spent, the effects lost)."""
        if self._countered(f, sid, spell):
            return False
        effects.cast(self, f, sid, spell, target, point, up=up, mod=mod, dc=dc, bonus=bonus, mult=mult, level=level,
                     slotted=slotted)
        return True

    def _countered(self, caster: Fighter, sid: str, spell: dict) -> bool:
        """Counterspell (2024): a foe within 60 feet who sees the casting may answer with its reaction and a level 3
        slot; the caster makes a Constitution save, and on a failure the spell comes to nothing. A Spell Breaker's
        slot is kept when the spell holds."""
        from realmwalker.rules.engine.handlers import wizard

        if spell.get("ability") or spell.get("thrown") or "item" in spell.get("classes", ()) or sid == "counterspell" \
                or spell.get("again_of"):
            return False  # (a follow-up of a spell already cast is not a casting)
        for x in self.enemies_of(caster):
            if not x.reaction or query.incapacitated(x) or self.feet(x, caster) > 60 or not self.can_see(x, caster) \
                    or self.antimagic(x.cells) or x.buff_value("befuddled") or self.frozen(x):
                continue
            slot = wizard.counter_slot(self, x)
            if slot is None:
                continue
            if not reactions.yes(self, Decision(
                    x, "counterspell", f"{caster.the_name} begins to cast {spell['name']}. Counterspell? They make a "
                    "Constitution save; if they fail, the spell comes to nothing.",
                    [("yes", f"Counterspell (a level {slot} slot)"), ("no", "Let it be cast")],
                    default="yes" if spell["level"] >= 1 else "no")):
                continue
            wizard.pay_counter(self, x, slot)
            x.reaction = False
            kept = False
            if x.char is not None:  # (an abjuration: an abjurer's ward; Free Casting may keep the slot)
                kept = bool(getattr(events.emit(self, "spell_cast", actor=x, spell=self.t.spells["counterspell"],
                                                sid="counterspell", level=slot), "kept", False))
            self.say(f"<magic>{x.the_name} cuts across the spell with a Counterspell.</>", "magic")
            self._event("cast", by=x.id, to=caster.id, spell="counterspell", effect="condition", look="curse",
                        dtype="force", area=[])
            before = self.__dict__.get("_casting")
            self._casting = x  # (a save against a spell: Spell Resistance)
            try:
                held = self._save(caster, "con", wizard.counter_dc(self, x))
            finally:
                self._casting = before
            if held:
                self.say(f"{caster.the_name} holds the spell together.", "info")
                if x.char is not None and x.has_trait("spell_breaker") and not kept:
                    spellrules.unspend_slot(x.char, slot)
                    self.say("<magic>The slot is not lost.</> (Spell Breaker)", "magic")
                continue
            self.say(f"{caster.the_name}'s {spell['name']} unravels into nothing.",
                     "good" if x.side == PARTY else "danger")
            self._event("countered", who=caster.id, by=x.id, spell=sid)
            return True
        return False

    # ------------------------------------------------------------------ concentration
    def _start_concentration(self, f: Fighter, sid: str, spell: dict) -> None:
        if f.concentration is not None:
            self._end_concentration(f, quiet=False, why="is let go")
        f.concentration = {"spell": sid, "rounds": int(spell.get("rounds", 10))}

    def _end_concentration(self, f: Fighter, *, quiet: bool, why: str = "") -> None:
        conc = f.concentration
        if conc is None:
            return
        f.concentration = None
        sid = conc["spell"]
        for x in self.fighters:
            if any(b.get("haste") and b.get("conc") == f.id for b in x.buffs) and x.active:
                self.lethargy(x)
            x.buffs = [b for b in x.buffs if b.get("conc") != f.id]
            if x.state == "away" and x.away and x.away.get("by") == f.id and x.away.get("why") != "blink":
                if why == "runs its course" and x.away.get("why") == "banished" and x.kind in EXTRAPLANAR \
                        and x.away.get("home", True):
                    x.state = "fled"  # (banished for the whole minute to the plane it came from: it stays there)
                    x.away = None
                    x.__dict__["banished_home"] = True  # (beaten: full experience, as for a kill)
                    self._event("leave", who=x.id)
                    self.say(f"{x.the_name} does not come back.", "good" if x.team != f.team else "danger")
                else:
                    self.bring_back(x)
            for se in [se for se in x.save_ends if se.get("conc") == f.id]:
                x.conditions.pop(se["cond"], None)
                x.save_ends.remove(se)
        for z in [z for z in self.zones if z.owner == f.id and z.rounds < 0]:
            self._remove_zone(z)
        for x in self.fighters:  # (Reverse Gravity ends: those it held up come down)
            if x.z > 0 and not x.hovers and x.state in ("fighting", "fleeing", "down") and not x.buff_value("aloft") \
                    and (x.fly_speed <= 0 or x.incapacitated or x.state == "down"):
                self._fall(x)
        for tok in [t for t in self.tokens if t.owner == f.id and t.rounds < 0]:
            self.tokens.remove(tok)  # a spiritual weapon held by concentration (2024)
            self._event("token_end", id=tok.id)
        for x in self.allies_of_owner(f):  # a summoned spirit goes when the spell does (Expansion 3 F.2)
            if x.bond.get("conc") and x.state not in ("dead", "fled"):
                self.dismiss(x)
        durations.end_concentration(self, f)
        for x in self.fighters:  # a lasting spell held by concentration (Shield of Faith) ends with it
            if x.id in conc.get("on", []) and x.char is not None:
                spellrules.end(x.char, sid)
                x.buffs = [b for b in x.buffs if b.get("lasting") != sid]
        if not quiet:
            name = self.t.spells[sid]["name"] if sid in self.t.spells else "the spell"
            self.say(f"{f.the_name}'s {name} {why or 'ends'}.", "magic")
        self._event("concentration_end", who=f.id, spell=sid)

    # ------------------------------------------------------------------ sent away
    def send_away(self, f: Fighter, why: str, *, by: Fighter | None = None, spell: str = "") -> None:
        """Off the field for a while: banished to a harmless pocket (Banishment), blinked into the Ethereal Plane
        (Blink), or sealed in a sphere where it stands (Otiluke's Resilient Sphere). Nobody can reach it, and it can
        do nothing, until it comes back (`bring_back`)."""
        if f.state not in ("fighting", "fleeing"):
            return
        f.away = {"why": why, "by": by.id if by is not None else None, "spell": spell, "state": f.state,
                  "stays": why in ("sphere", "cage")}
        f.state = "away"
        if f.grappled_by is not None:
            f.grappled_by = None
            f.conditions.pop("grappled", None)
        for x in self.fighters:
            if x.grappled_by == f.id:
                x.grappled_by = None
                x.conditions.pop("grappled", None)
        f.readied = None
        self._event("vanish", who=f.id, why=why)
        self.say({"banished": f"{f.the_name} vanishes from the field.",
                  "blink": f"{f.the_name} blinks out of sight.",
                  "sphere": f"A shimmering sphere closes around {f.the_name}.",
                  "cage": f"Walls of force snap shut around {f.the_name}."}.get(why, f"{f.the_name} is gone."),
                 "magic")

    def _unseal_the_last(self, f: Fighter) -> None:
        """At the start of its turn, a caster whose only foes left are sealed in its own sphere or forcecage lets the
        spell go, and the fight goes on (rather than waiting out the hour)."""
        if f.concentration is None:
            return
        foes = [x for x in self.fighters if x.team != f.team and (x.active and "unconscious" not in x.conditions
                                                                  or x.state == "away")]
        if foes and all(x.state == "away" and (x.away or {}).get("why") in ("sphere", "cage")
                        and (x.away or {}).get("by") == f.id for x in foes):
            self._end_concentration(f, quiet=False, why="is let go")

    def send_off(self, f: Fighter, *, by: Fighter | None = None) -> None:
        """Sent from this plane for good (Plane Shift, Divine Word): gone from the fight, and beaten."""
        if f.state not in ("fighting", "fleeing", "away"):
            return
        self._release(f)
        f.away = None
        f.state = "fled"
        f.__dict__["banished_home"] = True  # (beaten: full experience, as for a kill)
        self._event("vanish", who=f.id, why="banished")
        self._event("leave", who=f.id)
        self.say(f"{f.the_name} is torn from this world and does not come back.",
                 "good" if by is not None and f.team != by.team else "danger")
        self._check_end()

    def lethargy(self, x: Fighter) -> None:
        """Haste ends (2024): until the end of its next turn it cannot move or take actions."""
        durations.give(self, x, "incapacitated", ends=durations.until(self, x, "turn_end"))
        x.buffs.append({"slow": 999, "source": "lethargy", "rounds": 1})
        self.say(f"A wave of lethargy sweeps over {x.the_name} as the haste leaves them.", "system")

    def bring_back(self, f: Fighter) -> None:
        """Back from wherever it was sent: where it left, or the nearest free place."""
        if f.state != "away" or f.away is None:
            return
        state = f.away.get("state", "fighting")
        why = f.away.get("why")
        f.away = None
        f.state = state if state in ("fighting", "fleeing") else "fighting"
        if why not in ("sphere", "cage"):
            taken = {c for x in self.on_field() if x is not f for c in x.cells}
            if not self.field.fits(f.x, f.y, f.sq) or any(c in taken for c in f.cells):
                f.x, f.y = self._free_near((f.x, f.y), f.sq, taken)
        self._event("appear", who=f.id)
        self.say(f"The sphere around {f.the_name} winks out." if why == "sphere" else
                 f"The walls of force around {f.the_name} are gone." if why == "cage" else
                 f"{f.the_name} is back.", "magic")

    def _maze_turn(self, f: Fighter) -> None:
        """Maze (2024): lost in the labyrinth, it spends its turn on a Study action to find the way out, a DC 20
        Intelligence (Investigation) check; on a success it escapes and the spell ends."""
        esc = (f.away or {}).get("escape") or {}
        if not self.check(f, esc.get("skill", "investigation"), int(esc.get("dc", 20)), "The way out of the maze"):
            self.say(f"Somewhere in its maze, {f.the_name} takes another wrong turn.", "good" if f.side == FOE else "info")
            return
        by = next((x for x in self.fighters if x.id == (f.away or {}).get("by")), None)
        self.say(f"{f.the_name} finds the way out of the maze.", "danger" if f.side == FOE else "good")
        if by is not None and by.concentration is not None and by.concentration.get("spell") == f.away.get("spell"):
            self._end_concentration(by, quiet=True)
        else:
            self.bring_back(f)
        f.lost_turn = True  # (the turn went on finding the way: Battle.step ends it)

    def frozen(self, x: Fighter) -> bool:
        """Time Stop: everyone but the one who stopped time is held in the moment (no reactions)."""
        stopper = self.__dict__.get("_time_stop")
        return stopper is not None and x.id != stopper

    def _more_time(self, f: Fighter) -> bool:
        """Time Stop (2024): 1d4 + 1 turns in a row for the caster; it ends when an action or an effect of theirs
        reaches another creature (Battle._event), or when they fall. True when they take another turn now."""
        bf = next((bf for bf in f.buffs if bf.get("time_stop") is not None), None)
        if bf is None:
            return False
        broken = self.__dict__.pop("_time_broken", False)
        if broken or not f.active or int(bf["time_stop"]) <= 0:
            f.buffs.remove(bf)
            self._time_stop = None
            self.say("Time flows again." if not broken else
                     f"{f.the_name} has touched the world, and time flows again.", "magic")
            self._event("time", who=f.id, stopped=False)
            return False
        bf["time_stop"] = int(bf["time_stop"]) - 1
        self._time_stop = f.id
        f.extra_turn = True  # (no time passes: _start_of_turn wears nothing down)
        self.say(f"Time stands still: {f.the_name} moves alone.", "magic")
        return True

    def _storm_turn(self, owner: Fighter, z: Zone) -> None:
        """Storm of Vengeance: at the start of each of the caster's later turns the storm brings its next stage
        (the last one again and again): its ops on each creature under it it does not spare, `count` of them at most
        (six bolts of lightning); `rough` and `dark` from then on."""
        from realmwalker.rules.engine import effects

        st = z.stages[min(z.stage, len(z.stages) - 1)]
        z.stage += 1
        if st.get("say"):
            self.say(st["say"], "magic")
        if st.get("rough") or st.get("dark"):
            z.rough = z.rough or bool(st.get("rough"))
            z.dark = z.dark or bool(st.get("dark"))
            self._sync_zones()
        spell = self.t.spells[z.spell] if z.spell in self.t.spells else {"name": "the storm", "level": 0,
                                                                          "target": "point"}
        under = [x for x in self.in_area(sorted(z.cells), "enemies" if z.friends_safe else "all", owner)
                 if x.active]
        if st.get("count"):
            self.rng.shuffle(under)
            under = under[:int(st["count"])]
        c = effects.Cast(self, owner, z.spell, spell, None, z.centre, sorted(z.cells), int(z.cast.get("up", 0)),
                         int(z.cast.get("mod", 0)), int(z.cast.get("dc", z.dc)), 0, 1,
                         int(z.cast.get("level", spell.get("level", 0))), slotted=False)
        before = self.__dict__.get("_casting")
        self._casting = owner
        try:
            for x in under:
                if x.active:
                    effects.run(c, st.get("ops", ()), x)
        finally:
            self._casting = before
        self._check_end()

    def _more_spheres(self, f: Fighter, spell: dict, cells: list, more: int) -> list:
        """Meteor Swarm: the other spheres fall where they catch the most foes not yet caught and the fewest friends
        (the battle's judgement), each creature counted once."""
        area = spell["area"]
        have = set(cells)
        for _ in range(max(0, more)):
            caught = {x.id for x in self.in_area(sorted(have), "all", f)}
            best, best_score = None, 0.0
            for e in self.enemies_of(f):
                if e.id in caught or not e.active:
                    continue
                sq = self.field.area(area["shape"], int(area["size"]), origin=f.space, toward=(e.x, e.y))
                new = [x for x in self.in_area(sq, "all", f) if x.id not in caught]
                score = sum(1.0 if x.team != f.team else -2.5 for x in new)
                if score > best_score:
                    best, best_score = sq, score
            if best is None:
                break
            have |= set(best)
        return sorted(have)

    # ------------------------------------------------------------------ zones
    def _zone_id(self) -> int:
        self._next_zone += 1
        return self._next_zone

    def _add_zone(self, z: Zone) -> None:
        self.zones.append(z)
        self._sync_zones()
        self._event("zone", id=z.id, zone=z.kind, cells=sorted(z.cells), owner=z.owner)

    def _remove_zone(self, z: Zone) -> None:
        if z in self.zones:
            self.zones.remove(z)
            if z.holds:
                for x in self.fighters:
                    if x.conditions.get("restrained") == -1 and any(c in z.cells for c in x.cells):
                        x.conditions.pop("restrained", None)
            if z.kind == "guardian":
                self.tokens = [t for t in self.tokens if t.id != getattr(z, "token", -1)]
            if z.was:  # (a wall of stone or force: the ground it stood on comes back)
                for (x, y), name in z.was.items():
                    self.field.terrain[x, y] = self.t.terrain.index[name]
                self.field._derive()
            self._sync_zones()
            self._event("zone_end", id=z.id)

    def wind_between(self, att: Fighter, target: Fighter) -> bool:
        """A Wind Wall stands between them: arrows, bolts and other ordinary missiles cannot cross it."""
        walls = [z for z in self.zones if z.kind == "wind"]
        if not walls:
            return False
        line = set(grid.crossed(att.x + att.sq / 2, att.y + att.sq / 2, target.x + target.sq / 2,
                                target.y + target.sq / 2))
        return any(line & z.cells for z in walls)

    def _sync_zones(self) -> None:
        W, H = self.field.width, self.field.height
        opaque = np.zeros((W, H), dtype=bool)
        difficult = np.zeros((W, H), dtype=bool)
        thick = np.zeros((W, H), dtype=bool)
        for z in self.zones:
            for (x, y) in z.cells:
                if 0 <= x < W and 0 <= y < H:
                    if z.opaque:
                        opaque[x, y] = True
                    if z.difficult and z.kind != "guardians":
                        difficult[x, y] = True
                    if z.kind == "overgrowth":
                        thick[x, y] = True
        self.field.set_zones(opaque, difficult, thick)

    def _follow_auras(self) -> None:
        """An aura (Spirit Guardians) moves with whoever carries it; an aura that helps friends (Crusader's Mantle,
        Aura of Life, Circle of Power) is shared with those now within it (marks.share_auras)."""
        marks.share_auras(self)
        for z in self.zones:
            if not (z.kind == "guardians" or z.follows) or z.owner is None:
                continue
            o = next((x for x in self.fighters if x.id == z.owner), None)
            if o is None or o.state not in ("fighting", "down"):
                continue
            r = z.radius
            cells_ = set()
            for x in range(o.x - r, o.x + o.sq + r):
                for y in range(o.y - r, o.y + o.sq + r):
                    if self.field.in_bounds(x, y) and grid.gap(o.space, (x, y, 1)) <= r:
                        cells_.add((x, y))
            if cells_ != z.cells:
                z.cells = cells_
                if z.follows:
                    self._sync_zones()
                self._event("zone_move", id=z.id, cells=sorted(cells_))

    def _ignite(self, f: Fighter, area: list[tuple[int, int]]) -> None:
        """Fire falling on dry grass, brush or straw sets it burning for a round or two."""
        burning = {c for c in area if self.field.in_bounds(*c) and self.field.flammable[c]}
        if burning:
            self._add_zone(Zone(self._zone_id(), "fire", burning, owner=f.id, rounds=1, save="dex", dc=10,
                                damage="1d6", damage_type="fire", on_save="none"))
            self.say("The ground catches.", "danger")

    def _zones_on(self, f: Fighter, *, start: bool) -> bool:
        """What the zones where `f` now stands do to it. True if it stops a move (a web holds)."""
        self._follow_auras()
        stopped = False
        for z in list(self.zones):
            if not f.active or z not in self.zones:
                break
            if not any(c in z.cells for c in f.cells):
                continue
            if z.heal and f.id not in z.struck and z.owner is not None:
                owner = next((x for x in self.fighters if x.id == z.owner), None)
                if owner is not None and owner.team == f.team:  # (Conjure Celestial: its healing light)
                    z.struck.add(f.id)
                    if f.hp < f.max_hp and not f.no_heal and f.state in ("fighting", "fleeing", "down"):
                        self.say(f"Healing light bathes {f.the_name}.", "good" if f.side == PARTY else "info")
                        self._heal(f, dice.roll(z.heal, self.rng).total)
                    continue
            if z.friends_safe and z.owner is not None:
                owner = next((x for x in self.fighters if x.id == z.owner), None)
                if owner is not None and owner.team == f.team:
                    continue
            if f.id in z.struck:
                continue
            if z.kind != "antimagic" and (z.spell or z.kind in ("guardians", "guardian")) and self.antimagic(f.cells):
                continue  # a spell laid on the ground does nothing where magic does not work
            if z.kind == "web":
                stopped = self._zone_catch(f, z) or stopped
            elif z.kind in ("caltrops", "bearings", "grease") and not start and f.standing and f.z == 0:
                stopped = self._zone_underfoot(f, z) or stopped
            elif z.kind == "spikes" and not start and f.z == 0:
                # (Spike Growth: every five feet walked through it, no save; once per square entered)
                self.say(f"Thorns tear at {f.the_name}.", "good" if f.side == FOE else "danger")
                owner = next((x for x in self.fighters if x.id == z.owner), None)
                self._hit(owner, f, dice.roll(z.damage or "2d4", self.rng).total, z.damage_type or "piercing",
                          crit=False, weapon="thorns")
            elif z.kind in ("fire", "guardians", "guardian", "daggers", "moonbeam", "sphere") and z.damage \
                    and not z.fail:
                z.struck.add(f.id)
                owner = next((x for x in self.fighters if x.id == z.owner), None)
                before = f.hp
                if z.kind == "fire":
                    self.say(f"{f.the_name} is in the flames.", "danger" if f.side == PARTY else "info")
                elif z.kind == "daggers":
                    self.say(f"Blades whirl around {f.the_name}.", "danger" if f.side == PARTY else "info")
                elif z.kind == "moonbeam":
                    self.say(f"Pale light sears {f.the_name}.", "danger" if f.side == PARTY else "info")
                if z.save:
                    self._save_damage(owner or f, f, z.save, z.dc, z.damage, z.damage_type, z.on_save)
                else:  # (no save: a cloud of daggers)
                    self._hit(owner, f, dice.roll(z.damage, self.rng).total, z.damage_type, crit=False,
                              weapon=z.damage_type)
                if z.kind == "guardian":
                    z.budget -= max(0, before - f.hp)
                    if z.budget <= 0:
                        self.say("The guardian fades, its strength spent.", "magic")
                        self._remove_zone(z)
            elif z.damage or z.fail:
                stopped = self._ground(f, z, start=start) or stopped
        return stopped

    def _ground(self, f: Fighter, z: Zone, *, start: bool) -> bool:
        """The catalogue's ground (Expansion 3 D.2): a save against its damage, and what a failure brings (held
        down, knocked over, retching). Once a turn for each. True if it stops a move."""
        if f.z > 0 and z.fail in ("restrained", "prone"):
            return False  # (tentacles and ice catch only those on the ground)
        if z.lasts and z.fail in f.conditions:
            return False  # (already blinded by the glare: nothing more it can do)
        owner = next((x for x in self.fighters if x.id == z.owner), None)
        if z.fail == "restrained" and f.conditions.get("restrained") == -1 and "restrained" not in f.cond_ends:
            if z.damage and start and z.save:  # (held by the tentacles: the save again each turn, hurt if it fails)
                z.struck.add(f.id)
                if self._save_damage(owner or f, f, z.save, z.dc, z.held or z.damage, z.damage_type, "none") \
                        and z.frees:
                    f.conditions.pop("restrained", None)
                    self.say(f"{f.the_name} tears free.", "system")
            return False
        z.struck.add(f.id)
        self.say(GROUND_WORDS.get(z.kind, "The spell catches {T}.").replace("{T}", f.the_name),
                 "danger" if f.side == PARTY else "info")
        if not z.save:
            if z.damage:
                self._hit(owner, f, dice.roll(z.damage, self.rng).total, z.damage_type, crit=False,
                          weapon=z.damage_type)
            return False
        against = ("poisoned",) if z.fail == "retching" else ((z.fail,) if z.fail else ())
        if z.damage:
            saved = self._save_damage(owner or f, f, z.save, z.dc, z.damage, z.damage_type, z.on_save)
        else:
            saved = self._save(f, z.save, z.dc, against=against)
            self._event("save", who=f.id, ok=saved)
        if saved or not f.active or not z.fail:
            return False
        if z.fail == "restrained":
            if query.condition_immune(f, "restrained") or z.kind in trs.values(f, "ignores_zone", flat=True):
                return False
            f.conditions["restrained"] = -1
            f.move_left = 0
            self._event("condition", who=f.id, cond="restrained")
            return True
        if z.breaks and f.concentration is not None:  # (Earthquake: thrown down, the spell held is lost)
            self._end_concentration(f, quiet=False, why="is shaken loose")
        if z.fail == "prone":
            if durations.give(self, f, "prone"):
                self._event("prone", who=f.id)
                return True
            return False
        if z.fail == "retching":  # (Stinking Cloud: Poisoned, and no action or bonus action, this turn)
            if durations.give(self, f, "poisoned", ends=durations.until(self, f, "turn_end")):
                self._event("condition", who=f.id, cond="poisoned")
                if durations.give(self, f, "incapacitated", ends=durations.until(self, f, "turn_end")):
                    f.action = f.bonus = 0  # (on entering too: no action or bonus action for the rest of the turn)
                self.say(f"{f.the_name} retches, helpless.", "good" if f.side == FOE else "danger")
            return False
        if z.lasts:  # (Prismatic Wall's glare: blinded for a minute)
            if durations.give(self, f, z.fail, rounds=z.lasts):
                self._event("condition", who=f.id, cond=z.fail)
            return False
        if durations.give(self, f, z.fail, ends=durations.until(self, f, "turn_end")):
            self._event("condition", who=f.id, cond=z.fail)
        return False

    def _zone_underfoot(self, f: Fighter, z: Zone) -> bool:
        """Caltrops (PHB 2024): Dexterity save or 1 piercing damage and no more moving this turn. Ball bearings: a
        Dexterity save or down on the ground. Once a turn for each. True if it stops the move."""
        z.struck.add(f.id)
        if z.kind == "grease" and "prone" in f.conditions:
            return False
        if self._save(f, "dex", z.dc):
            return False
        if z.kind == "grease":
            if durations.give(self, f, "prone"):
                self._event("prone", who=f.id)
                self.say(f"{f.the_name} slips on the grease and falls.", "good" if f.side == FOE else "danger")
                return True
            return False
        if z.kind == "caltrops":
            self.say(f"{f.the_name} treads on a caltrop.", "good" if f.side == FOE else "danger")
            self._hit(f, f, 1, "piercing", crit=False, weapon="caltrops")
            f.move_left = 0
            return True
        if durations.give(self, f, "prone"):
            self._event("prone", who=f.id)
            self.say(f"{f.the_name} skids on the ball bearings and goes down.", "good" if f.side == FOE else "danger")
            return True
        return False

    def _zone_catch(self, f: Fighter, z: Zone) -> bool:
        if z.kind == "grease":
            return self._zone_underfoot(f, z)  # (as the grease appears)
        if not z.holds or "restrained" in f.conditions or z.kind in trs.values(f, "ignores_zone", flat=True):
            return False
        if query.condition_immune(f, "restrained"):
            return False
        z.struck.add(f.id)
        if self._save(f, z.save or "dex", z.dc):
            return False
        f.conditions["restrained"] = -1
        f.move_left = 0
        self._event("condition", who=f.id, cond="restrained")
        self.say(f"{f.the_name} is caught in the web." if z.kind == "web" else
                 f"Grasping weeds and vines seize {f.the_name}.", "good" if f.side == FOE else "danger")
        return True

    def _heal(self, f: Fighter, amount: int) -> None:
        if f.state == "dead":
            return
        if f.char is not None and f.char.attuned:
            from realmwalker.rules import magic

            if magic.flag(f.char, "no_healing"):
                self.say(f"The healing slides off {f.the_name}: the artifact will not allow it.", "warn")
                return
        amount = events.emit(self, "healed", target=f, amount=amount).amount  # Boon of Fortitude
        f.hp = min(f.max_hp, f.hp + amount)
        self._event("heal", to=f.id, amount=amount)
        if f.state == "down" and f.hp > 0:
            f.state = "fighting"
            f.conditions.pop("unconscious", None)
            f.stable = False
            f.death_saves = [0, 0]
            self.say(f"{f.the_name} opens {f.possessive} eyes.", "good")
        self.say(f"{f.the_name} recovers {amount} hit points.", "good")

    # ------------------------------------------------------------------ bookkeeping
    def _fill(self, template: str, att: Fighter | None, target: Fighter, **extra) -> str:
        values = {
            "A": att.the_name if att else "something", "T": target.the_name, "their": target.possessive,
            "weapon": extra.get("weapon", "blow"), "part": extra.get("part", "body"), "armor": extra.get("armor", "armour"),
        }
        text = template
        for k, v in values.items():
            text = text.replace("{" + k + "}", str(v))
        return text[:1].upper() + text[1:]

    def result(self) -> BattleResult:
        foes = [f for f in self.side(FOE) if f.bond is None]  # (an enemy caster's spirit leaves nothing behind)
        dead = [f.creature for f in foes if f.state == "dead"]
        captives = [f.creature for f in foes if f.state == "surrendered" or ("unconscious" in f.conditions and f.state == "fighting")]
        fled = [f.creature for f in foes if f.state in ("fled", "fleeing", "away")]
        xp = 0
        if self.outcome in ("victory", "parley"):
            for f in foes:
                value = int(f.cdef["xp"])
                if f.state == "dead" or f in [x for x in foes if x.creature in captives]:
                    xp += value
                elif f.__dict__.get("banished_home"):
                    xp += value  # (sent home for good by Banishment: beaten)
                elif f.state in ("fled", "fleeing") and f.damage_taken > 0:
                    xp += value // 2
            if self.outcome == "parley":
                xp //= 2
        money = sum(c.money for c in dead)
        items = [i for c in dead for i in c.inventory] + list(self.thrown)
        if self.outcome in ("victory", "parley"):  # a minute's search finds half the ammunition loosed (2024)
            items += [Item(0, def_id, n // 2) for def_id, n in sorted(self.shot.items()) if n // 2 > 0]
        party_dead = [f.char for f in self.side(PARTY) if f.state == "dead" and f.char is not None]
        return BattleResult(self.outcome or "victory", xp, dead, captives, fled, money, items, party_dead, self.round,
                            self.robbed_money)


def cast_kind(f: Fighter, spell: dict) -> str:
    """How long a casting takes for this caster: "bonus", "reaction" or "action". An abjurer's Spell Breaker casts
    Dispel Magic with a bonus action (the spell's `breaker_bonus`)."""
    if spell.get("breaker_bonus") and f.has_trait("spell_breaker"):
        return "bonus"
    return spell.get("cast", "action")


def signed_mod(n: int) -> str:
    return f"+{n}" if n > 0 else (f"-{-n}" if n < 0 else "")


def _avg(expr: str) -> float:
    try:
        n, sides, flat = dice.parse(expr)
    except dice.DiceError:
        return 0.0
    return n * (sides + 1) / 2 + flat
