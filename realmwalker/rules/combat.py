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
from realmwalker.rules import grid
from realmwalker.rules import spells as spellrules
from realmwalker.rules.character import Character, Sheet, modifier
from realmwalker.rules.engine import actions, durations, effects, events, hazards, query, reactions
from realmwalker.rules.engine.reactions import Decision
from realmwalker.rules.engine import traits as trs
from realmwalker.rules.creatures import Creature
from realmwalker.rules.inventory import remove_item
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
STATES = ("fighting", "fleeing", "down", "dead", "fled", "surrendered")


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
    kind: str  # web, fire, fog, ice, guardians (moves with its owner), guardian (stays where it was set)
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

    @property
    def difficult(self) -> bool:
        return self.kind in ("web", "ice", "guardians")

    @property
    def opaque(self) -> bool:
        return self.kind in ("fog", "darkness")

    @property
    def light(self) -> int:
        return 2 if self.kind == "fire" else 0


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
        self.sq = grid.footprint(self.size)
        self.initiative = 0
        self.state = "fighting"  # fighting, fleeing, down, dead, fled, surrendered
        self.conditions: dict[str, int] = {}  # the 2024 conditions (data/conditions.json): rounds left, -1 until ended
        self.sources: dict[str, int] = {}  # who caused a condition, where that matters (rules/engine/query.source)
        self.cond_ends: dict[str, dict] = {}  # how a condition ends, when it is timed by turns (rules/engine/durations.py)
        self.buffs: list[dict] = []
        self.death_saves = [0, 0]  # successes, failures
        self.stable = False
        self.dodging = False
        self.helped = False
        self.grovel = False  # Commanded to grovel: its next turn is spent on the ground
        self.surprised = False
        self.took_fire = False
        self.morale_checked: set[str] = set()
        self.damage_taken = 0
        self.temp_hp = 0  # temporary hit points: lost first, and they do not add up (the higher is kept)
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
        self.cast_bonus_spell = False
        self.cast_action_spell = False
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
        if char is not None:
            from realmwalker.rules import magic

            self.glow = int(magic.light(char) or 0)

    # ------------------------------------------------------------------ identity
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
        return "its" if self.cdef["kind"] in ("beast", "undead") else "his"

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
        return self.char.max_hp if self.char else self.creature.max_hp

    @property
    def wounds(self) -> list:
        return self.char.wounds if self.char else self.creature.wounds

    def mod(self, ability: str) -> int:
        if self.char:
            return self.sheet.mod(ability)
        return modifier(self.cdef["abilities"][ability])

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
    def darkvision(self) -> int:
        if self.char:
            return self.sheet.darkvision
        return int(self.cdef.get("darkvision", 0))

    @property
    def body(self) -> str:
        return "humanoid" if self.char else self.cdef.get("body", "humanoid")

    @property
    def kind(self) -> str:
        return "humanoid" if self.char else self.cdef["kind"]

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
        return self.cdef.get("rank") == "back"

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
    return value.split(":", 2)[2] if value.startswith(("scroll:", "charge:", "throw:")) else value


BATTLE_USES = {"heal", "bandage", "throw"}  # what an item's "use" can do in a fight (do_item, or thrown via do_cast)


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
                part = spellrules.battle_part(tables, sid)
                if part:
                    f.buffs.append(part)
            self.fighters.append(f)
            fid += 1
        if env.carried_light > 0 and self.fighters:
            self.fighters[0].glow = max(self.fighters[0].glow, int(env.carried_light))
        for cr in foes:
            f = Fighter(fid, FOE, tables, creature=cr)
            for a in f.cdef["attacks"]:
                if a.get("recharge"):
                    f.recharge[a["name"]] = True
            self.fighters.append(f)
            fid += 1
        self._place(spots or {})
        self.order: list[int] = []
        self.turn = 0
        self.round = 1
        self.turn_started = False
        self.outcome: str | None = None
        self.known: set[str] = set()
        self.initial_foes = len(foes)
        self.robbed_money = 0
        self.thrown: list = []  # weapons thrown during the fight, lying on the field afterwards
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
        self.log.append((text[:1].upper() + text[1:], category))

    def _event(self, kind: str, **data) -> None:
        self.events.append({"kind": kind, **data})
        if kind in ACTIVITY:
            self.active_round = self.round

    def dice_say(self, text: str) -> None:
        if self.show_dice:
            self.log.append((text, "dice"))

    def fighter(self, fid: int) -> Fighter:
        return next(f for f in self.fighters if f.id == fid)

    @property
    def current(self) -> Fighter:
        return self.fighter(self.order[self.turn])

    def side(self, side: str) -> list[Fighter]:
        return [f for f in self.fighters if f.side == side]

    def enemies_of(self, f: Fighter) -> list[Fighter]:
        return [x for x in self.fighters if x.side != f.side and x.active]

    def allies_of(self, f: Fighter) -> list[Fighter]:
        return [x for x in self.fighters if x.side == f.side and x.active]

    def on_field(self) -> list[Fighter]:
        """Everyone still taking up room: the living, the fallen and the yielded (not the dead or the fled)."""
        return [f for f in self.fighters if f.state in ("fighting", "fleeing", "down", "surrendered")]

    def at(self, x: int, y: int) -> Fighter | None:
        for f in self.on_field():
            if f.x <= x < f.x + f.sq and f.y <= y < f.y + f.sq:
                return f
        return None

    def pending_party(self) -> Fighter | None:
        if self.outcome is not None or not self.order:
            return None
        f = self.current
        if f.side == PARTY and self.turn_started and f.can_act() and not f.surprised and not f.auto:
            return f
        return None

    def gap(self, a: Fighter, b: Fighter) -> int:
        return grid.gap(a.space, b.space)

    def feet(self, a: Fighter, b: Fighter) -> int:
        return grid.gap(a.space, b.space) * grid.SQUARE_FT

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
        for f in self.fighters:
            if self.env.surprised == f.side:
                f.surprised = True
            r = query.initiative_roll(f)
            bonus = int(f.cdef["initiative"]) if f.cdef and "initiative" in f.cdef else f.mod("dex")
            f.initiative = (dice.d20(self.rng, advantage=r.advantage, disadvantage=r.disadvantage).natural + bonus
                            + query.d20_penalty(f))
        self.order = [f.id for f in sorted(self.fighters, key=lambda f: (-f.initiative, -f.mod("dex"), self.rng.random()))]
        if intro:
            self.say(intro, "danger")
        if self.env.surprised == FOE:
            self.say("You have caught them unawares.", "good")
        elif self.env.surprised == PARTY:
            self.say("They are on you before you can draw.", "danger")
        self._knowledge_checks()
        order = ", ".join(self.fighter(i).name for i in self.order)
        self.say(f"Order of battle: {order}.", "system")

    def _knowledge_checks(self) -> None:
        """The party sizes up each kind of foe (Nature for beasts, History for people, Religion for the dead)."""
        skill_for = {"beast": "nature", "humanoid": "history", "undead": "religion", "giant": "nature"}
        party = [f for f in self.side(PARTY) if f.char]
        for def_id in sorted({f.creature.def_id for f in self.side(FOE)}):  # sorted: a set's order changes per run
            d = self.t.creatures[def_id]
            skill = skill_for.get(d["kind"], "arcana")
            dc = 8 + int(round(d["cr"] * 3))
            best = max(party, key=lambda p: p.skill(skill), default=None)
            if best is None:
                continue
            roll = dice.d20(self.rng).natural
            total = roll + best.skill(skill)
            self.dice_say(f"{self.t.rules['skills'][skill]['name']} ({best.name}): {roll} {signed_mod(best.skill(skill))} = {total} vs DC {dc}")
            if total >= dc:
                self.known.add(def_id)
                danger = "a real threat" if d["cr"] >= 1 else ("dangerous in numbers" if d["cr"] >= 0.25 else "weak alone")
                self.say(f"{best.name} knows {d['plural']}: {danger} (AC {d['ac']}).", "info")

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
        if f.side == PARTY and not f.auto:
            return False
        from realmwalker.rules import tactics

        tactics.take_turn(self, f)
        if self.outcome is None and self.turn_started and self.current is f:
            self.end_turn()
        return True

    def _start_of_turn(self, f: Fighter) -> None:
        durations.tick(self, f, "turn_start")  # what lasts "until the start of its next turn" ends
        if f.creature is not None and f.cdef.get("legendary"):
            f.creature.uses["legendary_actions"] = int(f.cdef["legendary"].get("uses", 3))
        f.dodging = False
        f.action, f.bonus, f.reaction = 1, 1, True
        f.attacks_left = 0
        f.dashed = f.disengaged = f.light_attack = False
        f.cast_bonus_spell = f.cast_action_spell = False
        f.spent_round += 1
        for b in list(f.buffs):
            if "rounds" in b:
                b["rounds"] -= 1
                if b["rounds"] < 0:
                    f.buffs.remove(b)
        f.move_left = f.speed
        if f.concentration is not None and f.concentration.get("rounds", -1) >= 0:
            f.concentration["rounds"] -= 1
            if f.concentration["rounds"] < 0:
                self._end_concentration(f, quiet=False, why="runs its course")
        for z in [z for z in self.zones if z.owner == f.id and z.rounds >= 0]:
            z.rounds -= 1
            if z.rounds < 0:
                self._remove_zone(z)
        for tok in [t for t in self.tokens if t.owner == f.id and t.rounds >= 0]:
            tok.rounds -= 1
            if tok.rounds < 0:
                self.tokens.remove(tok)
                self._event("token_end", id=tok.id)
        for z in self.zones:
            z.struck.discard(f.id)
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
        f.move_left = f.speed
        if any(z.kind == "guardians" and z.owner is not None and any(c in z.cells for c in f.cells)
               and self.fighter(z.owner).side != f.side for z in self.zones):
            f.move_left //= 2  # Spirit Guardians: half speed in the emanation (2024)
        # Standing up from the ground costs half your movement.
        if "prone" in f.conditions and f.can_act() and f.state == "fighting" and f.move_left >= f.speed // 2 > 0:
            del f.conditions["prone"]
            f.move_left -= f.speed // 2
            self.say(f"{f.the_name} gets up.", "system")
            self._event("stand", who=f.id)

    def _end_of_turn(self, f: Fighter) -> None:
        for se in list(f.save_ends):
            if se["cond"] not in f.conditions:
                f.save_ends.remove(se)
                continue
            if self._save(f, se["save"], se["dc"]):
                f.conditions.pop(se["cond"], None)
                f.save_ends.remove(se)
                self.say(f"{f.the_name} shakes off the spell.", "system")
        if f.hidden and f.active and any(self.gap(e, f) <= 1 for e in self.enemies_of(f) if e.standing):
            f.hidden = 0
            self.say(f"{f.the_name} is found.", "system")
        durations.tick(self, f, "turn_end")  # and what lasts "until the end of its next turn"

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
        self.turn += 1
        if self.turn >= len(self.order):
            self.turn = 0
            self.round += 1
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

    def _check_end(self) -> None:
        for f in self.fighters:
            if f.concentration is not None and (query.flag(f, "breaks_concentration") or not f.active):
                self._end_concentration(f, quiet=not f.active, why="is lost")  # incapacitated (2024)
        foes = [f for f in self.side(FOE) if f.active and "unconscious" not in f.conditions]
        party = [f for f in self.side(PARTY) if f.active and "unconscious" not in f.conditions]
        if not foes:
            self.outcome = "victory"
        elif not party:
            gone = any(f.state == "fled" for f in self.side(PARTY))
            self.outcome = "fled" if gone else "defeat"

    # ------------------------------------------------------------------ light and sight
    def light(self) -> np.ndarray:
        """How lit each square is now: the field's own light, what people carry, and anything burning."""
        carriers = [(f.x + f.sq // 2, f.y + f.sq // 2, f.glow) for f in self.fighters
                    if f.glow and f.state in ("fighting", "fleeing", "down")]
        fires = [(x, y, 1) for z in self.zones if z.kind == "fire" for (x, y) in z.cells]
        key = (tuple(carriers), tuple(fires), self.field.version)
        if key != self._light_key:
            self._light_key = key
            self._light = self.field.light_map(carriers + fires)
        return self._light

    def light_on(self, f: Fighter) -> float:
        L = self.light()
        return float(max(L[x, y] for x, y in f.cells if self.field.in_bounds(x, y)))

    def can_see(self, a: Fighter, b: Fighter) -> bool:
        """Whether `a` can see `b`: a line of sight, light enough (or darkvision close enough), and not hidden."""
        if "blinded" in a.conditions or a.incapacitated:
            return False
        if b.hidden and b.hidden > a.passive() - (5 if self.dim_for(a, b) else 0) and self.gap(a, b) > 1:
            return False
        if any(self.field.zone_opaque[x, y] for x, y in b.cells) and self.gap(a, b) > 1:
            return False
        if self.field.cover(a.space, b.space) == grid.TOTAL:
            return False
        if self.light_on(b) >= grid.DIM:
            return True
        return a.darkvision > 0 and self.feet(a, b) <= a.darkvision

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
            if not e.standing or not e.can_opportunity or e.incapacitated or e.state != "fighting":
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

    def move_tree(self, f: Fighter, budget: int | None = None, *, risk: float = 0.5) -> dict:
        blocked, occupied = set(), set()
        for x in self.on_field():
            if x is f:
                continue
            hostile = x.side != f.side and x.state in ("fighting", "fleeing", "surrendered")
            for c in x.cells:
                (blocked if hostile else occupied).add(c)
        fire = {c for z in self.zones if z.kind == "fire" for c in z.cells}
        if budget is None:
            budget = f.move_left // 2 if self.dragging(f) else f.move_left
        return grid.paths(self.field, (f.x, f.y), f.sq, budget, blocked=blocked,
                          occupied=occupied, threats=self.threats(f), risk=risk, crawling="prone" in f.conditions,
                          hazard=fire)

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
            cost = 0 if free else (10 if "prone" in f.conditions or any(self.field.difficult(*c) for c in new_cells
                                                                       if c not in f.cells) else 5)
            if heavy and not free:
                cost *= 2
            if cost > f.move_left and not free:
                break
            if provoke and not free and not f.disengaged:
                there = (sq[0], sq[1], f.sq)
                for e in self.enemies_of(f):
                    if (e.state == "fighting" and e.can_opportunity and not e.incapacitated and e.standing
                            and self.gap(e, f) <= self.reach_of(e) and grid.gap(e.space, there) > self.reach_of(e)
                            and self.can_see(e, f)):
                        if walked:
                            self._event("move", who=f.id, path=[start] + walked)
                            start, walked = (f.x, f.y), []
                        self._opportunity(e, f)
                        if not f.active or "unconscious" in f.conditions:
                            break
                if not f.active or "unconscious" in f.conditions:
                    break
            for c in new_cells:
                self.field.open_door(*c)
            before = (f.x, f.y)
            f.x, f.y = sq
            f.move_left -= cost
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
            if self._zones_on(f, start=False):
                break  # caught in a web
        if walked:
            self._event("move", who=f.id, path=[start] + walked)
        self._sync_grapples(f)
        self._follow_auras()
        return n

    def held_by(self, f: Fighter) -> list[Fighter]:
        return [x for x in self.fighters if x.grappled_by == f.id and x.active]

    def dragging(self, f: Fighter) -> bool:
        """Whether moving costs `f` double: it holds someone not tiny and not two sizes smaller (2024)."""
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
        opts = [o for o in self.attack_options(e) if o.is_melee and o.available and self.gap(e, f) <= o.reach_sq]
        if not opts:
            return
        if not reactions.yes(self, Decision(e, "opportunity", f"{f.the_name} breaks away from {e.the_name}. "
                                            "Strike as they go? (your reaction)",
                                            [("yes", "Strike"), ("no", "Let them go")], free=True)):
            return
        e.reaction = False
        opt = max(opts, key=lambda o: _avg(o.damage) + o.bonus)
        self.say(f"{e.the_name} strikes at {f.the_name} as {f.possessive if f.char else 'it'} breaks away.", "warn")
        self._event("opportunity", by=e.id, to=f.id)
        self._attack(e, opt, f)
        self._check_end()

    def area_attack(self, f: Fighter, opt: AttackOption, point: tuple[int, int]) -> None:
        """A breath weapon or the like: everyone in the area saves for half; then it must recharge."""
        a = opt.extra
        shape = a["area"]["shape"]
        cells = self.field.area(shape, int(a["area"]["size"]), origin=f.space, toward=point, from_self=True)
        f.recharge[a["name"]] = False
        self._spend_use(f, opt)
        if f.action > 0:
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
        f.move_left += f.speed
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
            return f"{e.the_name} can see you plainly"
        return None

    def do_hide(self, f: Fighter, *, bonus: bool = False) -> None:
        why = self.hide_problem(f)
        if why:
            self.say(f"Nowhere to hide: {why}.", "warn")
            return
        if not self._spend(f, bonus):
            return
        roll = dice.d20(self.rng).natural
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
        if f.creature:
            out = []
            for i, a in enumerate(f.cdef["attacks"]):
                kind = a["kind"]
                rng_ = (0, 0)
                if kind in ("ranged", "spell_ranged"):
                    rng_ = tuple(a.get("range") or (self.t.items.get(a["item"]).get("range") if a.get("item") in self.t.items
                                                    else None) or DEFAULT_RANGE[kind])
                opt = AttackOption(f"c{i}", a["name"], kind, int(a["bonus"]), a["damage"], a["damage_type"],
                                   reach=bool(a.get("reach")), extra=a, range=(int(rng_[0]), int(rng_[1])))
                if a.get("area") or a.get("recharge"):
                    opt.available = f.recharge.get(a["name"], True)
                    opt.reason = "not ready again yet" if not opt.available else ""
                if a.get("uses") and self.uses_left(f, a) <= 0:
                    opt.available, opt.reason = False, "used up for the day"
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
            out.append(self._weapon_option(f, s, it, key, two_handed_free=(key == "main" and off is None)))
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
        unarmed_bonus = s.proficiency + s.mod("str") + s.attack_condition()
        fists = AttackOption("unarmed", "fists", "melee", unarmed_bonus, str(max(1, 1 + s.mod("str"))), "bludgeoning")
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
        if not f.char:
            return None
        items = self.t.items
        main, off = f.char.equipped_item("main_hand"), f.char.equipped_item("off_hand")
        if main is None or off is None or items.category(main) != "weapon" or items.category(off) != "weapon":
            return None
        if "light" not in items.get(main.def_id).get("properties", []) or "light" not in items.get(off.def_id).get("properties", []):
            return None
        opt = self._weapon_option(f, f.sheet, off, "off")
        opt.name = f"{opt.name} (off hand)"
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

        enchant = magic.item_bonus(it)
        bonus = s.mod(ability) + prof + quality + s.attack_condition(ranged) + enchant + magic.total(f.char, "attack")
        if ranged and f.char.fighting_style == "archery":
            bonus += 2
        if not it.magic and it.condition < int(self.t.items.upkeep.get("battered", 30)):
            bonus -= 1  # battered: a bent blade, a split haft, a warped bow (game/gear.py)
        dmg = d["damage"]
        if "versatile" in props and two_handed_free and not ranged and not ("lost_left_arm" in f.char.injuries
                                                                            or "lost_right_arm" in f.char.injuries):
            dmg = d.get("versatile", dmg)
        mod = s.mod(ability)
        if key == "off" and not thrown and f.char.fighting_style != "two_weapon":
            mod = min(0, mod)  # the off hand adds no bonus damage
        mod += enchant
        if f.char.effects.get("honed", 0) > 0 and not ranged and d.get("damage_type") in ("slashing", "piercing"):
            mod += int(self.t.items.upkeep.get("hone", {}).get("damage", 1))  # a whetstone's edge, until the fight ends
        if f.char.fighting_style == "dueling" and not ranged and "two_handed" not in props and key == "main":
            off = f.char.equipped_item("off_hand")
            if off is None or self.t.items.category(off) == "shield":
                mod += 2
        damage = f"{dmg}{signed_mod(mod)}"
        rng_ = tuple(d.get("range") or ((20, 60) if thrown else (0, 0)))
        opt = AttackOption(key, d["name"], "ranged" if ranged else "melee", bonus, damage, d["damage_type"],
                           reach="reach" in props and not thrown, properties=list(props), item_uid=it.uid,
                           range=(int(rng_[0]), int(rng_[1])))
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
            if not any(i.def_id == ammo for i in f.char.inventory):
                opt.available = False
                opt.reason = f"no {self.t.items.get(ammo)['name']}s left"
        return opt

    def in_reach(self, f: Fighter, opt: AttackOption, target: Fighter, *, at: tuple[int, int] | None = None) -> tuple[bool, str]:
        """Whether an attack of this kind reaches the target from where `f` stands (or would stand)."""
        space = (at[0], at[1], f.sq) if at is not None else f.space
        g = grid.gap(space, target.space)
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
        if not self.has_action(f):
            return "no action left this turn"
        if not target.active and target.state != "down":
            return "not in the fight"
        if target.side == f.side:
            return "on your side"
        ok, why = self.in_reach(f, opt, target)
        if not ok:
            return why
        return None

    def targets_for(self, f: Fighter, opt: AttackOption) -> list[Fighter]:
        """Who this fighter could attack with this option right now, from where they stand."""
        return [x for x in self.enemies_of(f) + [y for y in self.side(FOE if f.side == PARTY else PARTY) if y.state == "down"]
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
        if grid.gap(a_space, target.space) != 1 or att.incapacitated or not self.can_see(att, target):
            return None
        for x in self.allies_of(att):
            if x is att or not x.standing or x.incapacitated or x.state != "fighting":
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
        return target.ac() + grid.COVER_AC[cover], cover

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
        adv, dis, why = self._adv_dis(att, target, opt)
        guard = self._protector(att, target)
        if guard is not None:
            guard.reaction = False
            dis = True
            why.append(f"{guard.name}'s shield")
            self.say(f"{guard.the_name} gets {guard.possessive} shield in the way.", "good" if guard.side == PARTY else "info")
        roll = dice.d20(self.rng, advantage=adv, disadvantage=dis)
        natural = events.emit(self, "d20_after", actor=att, target=target, roll="attack", natural=roll.natural).natural
        crit = natural >= query.crit_range(att)
        bless = sum(dice.roll(d, self.rng).total for d in att.buff_value("attack_die"))
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
        if hit and query.crit_within(self, att, target):
            crit = True  # a blow from right beside someone who cannot defend themselves at all
        if hit:
            crit = events.emit(self, "attack_hit", actor=att, target=target, opt=opt, crit=crit).crit  # Assassinate...
        att.helped = False
        if target.marked:
            target.marked = False  # spent on this roll, hit or miss
        target.buffs = [bf for bf in target.buffs if bf.get("distracted") != att.side]
        if att.hidden:
            att.hidden = 0
        armor = target.armor_name("torso")
        turned = not hit and bool(armor) and total >= ac - 4 and natural != 1 and opt.kind in ("melee", "ranged")
        self._event("attack", by=att.id, to=target.id, hit=hit, crit=crit, how=opt.kind, melee=opt.is_melee,
                    weapon=opt.name, dtype=opt.damage_type, armoured=turned)
        mode = " (adv)" if adv and not dis else (" (dis)" if dis and not adv else "")
        notes = list(why) + ([grid.COVER_WORDS[cover]] if cover else [])
        self.dice_say(f"{att.name} → {target.name}, {opt.name}{mode}: {natural} {signed_mod(opt.bonus + bless)} = {total} vs AC {ac}"
                      f" — {'critical!' if crit else ('hit' if hit else 'miss')}" + (f" [{', '.join(notes)}]" if notes else ""))
        if opt.ammo_def and att.char:
            ammo = next((i for i in att.char.inventory if i.def_id == opt.ammo_def), None)
            if ammo is not None:
                remove_item(att.char, ammo.uid, 1)
        if opt.key.startswith("throw") and att.char and opt.item_uid is not None:
            thrown = remove_item(att.char, opt.item_uid, 1)
            if thrown is not None:
                self.thrown.append(thrown)
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
            return False
        dmg_expr = opt.damage
        n, sides, flat = dice.parse(dmg_expr)
        rolled = dice.roll(dmg_expr, self.rng, double_dice=crit)
        amount = rolled.total
        # Great Weapon Fighting: reroll ones and twos once.
        if att.char and att.char.fighting_style == "great_weapon" and opt.is_melee and "two_handed" in opt.properties:
            amount = sum(r if r > 2 else self.rng.randint(1, sides) for r in rolled.rolls) + flat
        amount += events.emit(self, "attack_damage", actor=att, target=target, opt=opt, crit=crit,
                              advantage=adv and not dis, sides=sides, extra=0).extra  # Sneak Attack, Divine Strike...
        if att.creature and att.cdef.get("attacks") and opt.extra.get("poison"):
            poison = opt.extra["poison"]
            self._save_damage(att, target, "con", poison["dc"], poison["damage"], "poison", "half", quiet=True)
        self._spend_use(att, opt)
        self._hit(att, target, max(1, amount), opt.damage_type, crit=crit, weapon=opt.name,
                  bite=opt.extra.get("wound") == "bite", claws=opt.extra.get("wound") == "cut" and att.creature is not None and opt.name == "claws")
        for e in opt.extra.get("extra", ()):  # a 2025 block's damage of another kind on the same hit (a spider's venom)
            if target.active or target.state == "down":
                self._hit(att, target, dice.roll(e["damage"], self.rng, double_dice=crit).total, e["type"], crit=False,
                          weapon=opt.name)
        if opt.extra.get("on_hit") and target.active:
            self._block_effects(att, target, opt, opt.extra["on_hit"])
        if target.active and opt.extra.get("trip_dc") and "prone" not in target.conditions:
            if not self._save(target, "str", int(opt.extra["trip_dc"])):
                target.conditions["prone"] = -1
                self._event("prone", who=target.id)
                self.say(f"{target.the_name} is dragged down.", "danger")
        if target.active and opt.extra.get("paralyze_dc"):
            immune = target.char and target.char.race == "elf"
            if not immune and not self._save(target, "con", int(opt.extra["paralyze_dc"])):
                target.conditions["paralyzed"] = 2
                self._event("condition", who=target.id, cond="paralyzed")
                self.say(f"{target.the_name} goes rigid, paralysed by the touch.", "danger")
        if opt.extra.get("disease") and target.char and self.rng.chance(float(opt.extra.get("disease_chance", 1.0))):
            target.char.conditions.append(f"exposed:{opt.extra['disease']}")
        return True

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
            if g is target or g.char is None or g.char.fighting_style != "protection" or not g.reaction:
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

    def _shield(self, f: Fighter, att: Fighter | None = None, opt: AttackOption | None = None, total: int = 0,
                ac: int = 0) -> bool:
        """Cast Shield as a reaction (wizards who know it, with a first-level slot to spare)."""
        if not f.char or "shield" not in spellrules.known_spells(f.char, self.t):
            return False
        if f.buff_value("ac") and any(b.get("source") == "shield" for b in f.buffs):
            return False
        slot = spellrules.lowest_free_slot(f.char, self.t, 1)
        if slot is None:
            return False
        blow = f"{att.the_name}'s {opt.name} would hit {f.the_name} ({total} against AC {ac})" if att and opt else \
            f"A blow would hit {f.the_name}"
        if not reactions.yes(self, Decision(f, "shield", f"{blow}. Cast Shield? +5 AC turns it.",
                                            [("yes", f"Shield (a level {slot} slot)"), ("no", "Let it land")])):
            return False
        spellrules.spend_slot(f.char, slot)
        f.reaction = False
        f.buffs.append({"ac": 5, "rounds": 0, "source": "shield"})
        events.emit(self, "spell_cast", actor=f, spell=self.t.spells["shield"], sid="shield", level=1)
        self.say(f"<magic>{f.the_name} throws up a Shield.</> The blow glances off thin air.", "magic")
        self._event("cast", by=f.id, to=f.id, spell="shield", effect="buff", dtype="force", area=[])
        return True

    def _save(self, f: Fighter, ability: str, dc: int, *, quiet: bool = False, bonus: int = 0) -> bool:
        sr = query.save_roll(self, f, ability, bonus=bonus)
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
                targets = [t for t in self.targets_for(f, opt) if t.active and t.side != f.side]
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
        amount = events.emit(self, "save_damage", actor=att, target=target, ability=ability, saved=saved, full=full,
                             amount=amount).amount  # Evasion...
        if amount > 0:
            self._hit(att, target, amount, dtype, crit=False, weapon=dtype)

    def _hit(self, att: Fighter | None, target: Fighter, amount: int, dtype: str, *, crit: bool, weapon: str,
             bite: bool = False, claws: bool = False) -> None:
        """Damage that landed: resistances, text, wounds, going down."""
        amount, defence = query.damage_taken(target, amount, dtype)
        if defence == "immune":
            self.say(f"{target.the_name} does not seem to feel it.", "flavor")
            self._event("immune", to=target.id, by=att.id if att else None)
            return
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
                            crit=crit)
        target.damage_taken += amount
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
            if not self._save(target, "con", dc):
                self._end_concentration(target, quiet=False, why="breaks")
        if target.active and target.side == FOE:
            self._morale_after_hit(target)

    def _apply_hp_loss(self, target: Fighter, amount: int, *, source: Fighter | None, cause: str, crit: bool = False) -> None:
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
            if events.emit(self, "hp_zero", actor=source, target=target, amount=amount, survived=False).survived:
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
            else:
                self._kill(target, cause, killer=source)
        else:
            target.hp = new_hp

    def _death_save(self, f: Fighter) -> None:
        roll = dice.d20(self.rng).natural
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
        f.state = "dead"
        f.hp = 0
        f.died_round = self.round
        f.conditions = {}
        self._release(f)
        self._event("dead", who=f.id)
        if f.creature:
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
        lost = [f for f in self.side(FOE) if not f.active]
        if len(lost) * 2 < self.initial_foes:
            return
        for f in self.side(FOE):
            if f.active and "losses" not in f.morale_checked:
                f.morale_checked.add("losses")
                self._morale_check(f, "losses")

    def _morale_check(self, f: Fighter, reason: str) -> None:
        if f.morale_type in FEARLESS or f.state != "fighting":
            return
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
        why = self.attack_problem(f, opt, target)
        if why:
            return False
        if f.attacks_left <= 0:
            f.action -= 1
            f.attacks_left = query.attacks_per_action(f)
        f.attacks_left -= 1
        self._attack(f, opt, target)
        if f.char and opt.key == "main" and "light" in opt.properties and opt.is_melee:
            f.light_attack = True
        self._after_action(f)
        return True

    def do_offhand(self, f: Fighter, target: Fighter) -> bool:
        opt = self.offhand_option(f)
        if opt is None or not f.light_attack or f.bonus <= 0 or not self.in_reach(f, opt, target)[0]:
            return False
        f.bonus -= 1
        self._attack(f, opt, target)
        self._after_action(f)
        return True

    def help_targets(self, f: Fighter) -> list[Fighter]:
        """Who the Help action can be for (2024): a friend beside you who is down (first aid) or asleep (shaken awake),
        or an enemy beside you, distracted so that a friend's next attack on it has advantage."""
        out = []
        for x in self.side(f.side):
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
        elif target.side == f.side and ("unconscious" in target.conditions or "incapacitated" in target.conditions):
            for cid in ("unconscious", "incapacitated"):
                durations.remove(target, cid)
            self.say(f"{f.the_name} shakes {target.the_name} awake.", "good")
        else:
            foe = target if target.side != f.side else min(
                (e for e in self.enemies_of(f) if e.standing and self.gap(f, e) <= 1), key=lambda e: e.hp, default=None)
            if foe is not None:
                durations.buff(foe, {"distracted": f.side, "source": f"help:{f.id}"}, durations.until(self, f, "turn_start"))
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

    def do_grapple(self, f: Fighter, target: Fighter) -> None:
        if not self.can_grapple(f, target)[0] or not self._use_attack(f):
            return
        if not self._unarmed_save(f, target) and durations.give(self, target, "grappled", source=f,
                                                                escape=query.unarmed_dc(f)):
            target.grappled_by = f.id
            target.move_left = 0
            self.say(f"{f.the_name} gets a grip on {target.the_name} and holds on.", "good")
        else:
            self.say(f"{target.the_name} twists free of {f.the_name}'s grasp.", "system")
        self._after_action(f)

    def do_escape(self, f: Fighter) -> None:
        if not self._spend(f):
            return
        holder = next((x for x in self.fighters if x.id == f.grappled_by), None)
        dc = int(f.cond_ends.get("grappled", {}).get("escape") or (query.unarmed_dc(holder) if holder else 10))
        stuck = "grappled" if "grappled" in f.conditions else "restrained"
        skill = max(f.skill("athletics"), f.skill("acrobatics"))
        web = next((z for z in self.zones if z.kind == "web" and any(c in z.cells for c in f.cells)), None)
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
        if all(f.morale_type in FEARLESS for f in foes):
            return None
        if approach == "calm":
            if not all(f.kind == "beast" for f in foes):
                return None
            return 13 + len(foes)
        if any(f.kind == "beast" for f in foes):
            return None
        party = [f for f in self.side(PARTY) if f.standing]
        hurt = sum(1 for f in foes if f.hp < f.max_hp) / len(foes)
        dc = 12 + 2 * (len(foes) - len(party)) - int(hurt * 4)
        if approach == "intimidate":
            dc += 2 if len(foes) > len(party) else -1
        return max(5, min(25, dc))

    def do_parley(self, f: Fighter, approach: str) -> None:
        dc = self.parley_dc(approach)
        skill = {"persuade": "persuasion", "intimidate": "intimidation", "calm": "animal_handling"}[approach]
        if not self._spend(f):
            return
        if dc is None:
            self.say("They are past listening.", "warn")
            self._after_action(f)
            return
        roll = dice.d20(self.rng).natural
        bonus = f.skill(skill)
        self.dice_say(f"{self.t.rules['skills'][skill]['name']} ({f.name}): {roll} {signed_mod(bonus)} = {roll + bonus} vs DC {dc}")
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
        sid = (self.t.items.get(item.def_id).get("use") or {}).get("throw")
        return f"throw:{item.uid}:{sid}" if sid in self.t.spells else None

    def item_targets(self, f: Fighter) -> list[Fighter]:
        """Who you can reach to pour a potion into or bind: yourself and anyone beside you."""
        return [x for x in self.side(f.side) if (x.active or x.state == "down") and (x is f or self.gap(f, x) <= 1)]

    def fast_hands(self, f: Fighter) -> bool:
        """A thief can use an object with a bonus action (Cunning Action)."""
        return f.char is not None and f.has_trait("fast_hands") and f.bonus > 0

    def do_item(self, f: Fighter, uid: int, target: Fighter) -> None:
        it = f.char.item(uid)
        if it is None or (f.action <= 0 and not self.fast_hands(f)):
            return
        quick = f.action <= 0  # with the bonus action (Fast Hands)
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
        if not f.char:
            return []
        out = []
        for a in actions.activations(f):
            why = actions.problem(self, f, a)
            out.append((a["id"], a["name"], why is None, why or ""))
        if self.offhand_option(f) is not None:
            ok = f.bonus > 0 and f.light_attack
            at = max([0] + [i + 1 for i, row in enumerate(out)
                            if row[0] in ("second_wind", "action_surge") or row[0].startswith("cunning_")])
            out.insert(at, ("offhand", "Off-hand attack (bonus action)", ok,
                            "" if ok else ("attack with the main hand first" if f.bonus > 0 else "no bonus action left")))
        for tok in self.tokens:
            if tok.owner == f.id and tok.kind == "spiritual_weapon":
                out.append(("spirit_strike", "Spiritual weapon: strike (bonus action)", f.bonus > 0,
                            "" if f.bonus > 0 else "no bonus action left"))
        if self.burning(f):
            out.append(("put_out", "Put out the flames (roll on the ground)", f.action > 0,
                        "" if f.action > 0 else "no action left"))
        return out

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
        if aid in ("offhand", "spirit_strike"):
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
                if ok and sp.get("cast") == "bonus" and (not f.cast_action_spell or sp["level"] == 0):
                    out.append(sid)
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
        if tok is None:
            return []
        return [e for e in self.enemies_of(f) if grid.gap((tok.x, tok.y, 1), e.space) <= 5]

    def _spirit_strike(self, f: Fighter, tok: Token, target: Fighter) -> None:
        # The weapon flies to a free square beside its target (twenty feet at most), then strikes.
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
        opt = AttackOption("spirit", "spiritual weapon", "spell_melee", tok.bonus, tok.damage, tok.damage_type)
        self._event("token_strike", id=tok.id, to=target.id)
        self._attack(f, opt, target)

    # ------------------------------------------------------------------ spells
    def creature_spells(self, f: Fighter) -> list[str]:
        """The spells a creature could cast right now (a slot left, the action or bonus action free)."""
        if f.creature is None or not f.cdef.get("spells"):
            return []
        out = []
        sc = f.cdef.get("spellcasting", {})
        for sid in f.cdef["spells"]:
            spell = self.t.spells.defs.get(sid)
            if spell is None or spell.get("cast") == "reaction":
                continue
            level = spell["level"]
            per_day = self._per_day(f, sid)
            if per_day is not None:
                if per_day <= 0:
                    continue  # the 2025 way: so many times a day, no slots
            elif sid not in sc.get("at_will", []) and level and not any(n > 0 for n in f.slots[level - 1:]):
                continue
            if self._casting_time_ok(f, spell)[0]:
                out.append(sid)
        return out

    def creature_cast(self, f: Fighter, sid: str, target: Fighter | None = None,
                      point: tuple[int, int] | None = None) -> bool:
        """A creature casts one of its spells, with its own save DC and spell attack."""
        spell = self.t.spells[sid]
        if sid not in self.creature_spells(f):
            return False
        sc = f.cdef["spellcasting"]
        level = spell["level"]
        if self._per_day(f, sid) is not None:
            f.creature.uses[f"spell:{sid}"] -= 1
        elif level and sid not in sc.get("at_will", []):
            i = next(i for i in range(level - 1, len(f.slots)) if f.slots[i] > 0)
            f.slots[i] -= 1
            level = i + 1
        bonus_cast = spell.get("cast") == "bonus"
        self._spend(f, bonus_cast)
        if bonus_cast:
            f.cast_bonus_spell = True
        else:
            f.cast_action_spell = True
        f.hidden = 0
        self.cast(f, sid, spell, target, point, up=max(0, level - spell["level"]), mod=f.mod(sc["ability"]),
                  dc=int(sc["dc"]), bonus=int(sc["attack"]), mult=1, level=level)
        self._check_end()
        return True

    def _per_day(self, f: Fighter, sid: str) -> int | None:
        """Casts left today of a spell a 2025 block lists as "N/day" (None if it is not one of those)."""
        per_day = (f.cdef.get("spellcasting") or {}).get("per_day") or {}
        for n, sids in per_day.items():
            if sid in sids:
                return f.creature.uses.setdefault(f"spell:{sid}", int(n))
        return None

    def spell_options(self, f: Fighter) -> list[tuple[str, bool, str]]:
        """(spell id, possible, why not). Scrolls in the pack appear as "scroll:<item uid>:<spell id>"."""
        if not f.char:
            return []
        out = []
        for sid in spellrules.known_spells(f.char, self.t):
            ok, why = spellrules.can_cast(f.char, self.t, sid)
            spell = self.t.spells[sid]
            need = (spellrules.op(spell, "revive") or {}).get("consumes")
            if ok and need and not any(i.def_id == need for i in f.char.inventory):
                ok, why = False, f"needs a {self.t.items.get(need)['name'].lower()}"
            if ok and spell["target"] == "self" and sid in spellrules.lasting(f.char, self.t):
                ok, why = False, "already working on you"
            if ok and spellrules.has_op(spell, "identify"):
                ok, why = False, "not in a fight"
            if ok and spell.get("cast") == "reaction":
                ok, why = False, "a reaction: cast by itself when a blow would land"
            if ok:
                ok, why = self._casting_time_ok(f, spell)
            out.append((sid, ok, why))
        for it in f.char.inventory:
            sid = self.t.items.get(it.def_id).get("use", {}).get("scroll")
            if sid in self.t.spells and not spellrules.has_op(self.t.spells[sid], "revive", "identify") \
                    and self.t.spells[sid].get("cast") != "reaction":
                ok, why = self._casting_time_ok(f, self.t.spells[sid])
                out.append((f"scroll:{it.uid}:{sid}", ok, why))
        from realmwalker.rules import magic

        for it, p in magic.charges(f.char):
            if p["spell"] in self.t.spells:
                left = int(p.get("left", p.get("value", 1)))
                ok, why = self._casting_time_ok(f, self.t.spells[p["spell"]])
                out.append((f"charge:{it.uid}:{p['spell']}", left > 0 and ok, why if left > 0 else "no charges left until dawn"))
        return out

    def _casting_time_ok(self, f: Fighter, spell: dict) -> tuple[bool, str]:
        """The action economy of spells: a bonus-action spell needs the bonus action, an ordinary one the action;
        and after a bonus-action spell only a cantrip may be cast with the action (and the other way round)."""
        if spell.get("cast") == "bonus":
            if f.bonus <= 0:
                return False, "no bonus action left"
            if f.cast_action_spell and spell["level"] > 0:
                return False, "you have cast a spell this turn"
            return True, ""
        if f.action <= 0 and f.attacks_left <= 0:
            return False, "no action left this turn"
        if f.cast_bonus_spell and spell["level"] > 0:
            return False, "after a bonus-action spell, only a cantrip"
        return True, ""

    def spell_range(self, spell: dict, f: Fighter | None = None) -> int:
        r = spell.get("range", 60)
        if r == "touch":
            return 5
        if r == "self":
            return 0
        if spell.get("range_scaling") and f is not None and f.char is not None:
            return int(r) * 2 ** (spellrules.cantrip_multiplier(f.char.level) - 1)  # Spare the Dying: 15, 30, 60 feet
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
            return [x for x in self.side(f.side) if (x.active or x.state == "down") and near(x)]
        if target == "downed_ally":
            return [x for x in self.side(f.side) if x.state == "down" and not x.stable and near(x)]
        if target == "dead_ally":
            return [x for x in self.side(f.side) if x.state == "dead" and self.round - x.died_round <= 10 and near(x)
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
        for x in range(max(0, f.x - n), min(self.field.width, f.x + f.sq + n)):
            for y in range(max(0, f.y - n), min(self.field.height, f.y + f.sq + n)):
                if grid.gap(f.space, (x, y, 1)) > n:
                    continue
                if self.field.solid[x, y]:
                    continue
                if occ and ((x, y) in occ or not self.field.passable(x, y)):
                    continue
                if not self.can_see_point(f, x, y):
                    continue
                out.add((x, y))
        return out

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
        return self.field.area(area["shape"], int(area["size"]), origin=f.space, toward=point,
                               from_self=spell["target"] == "direction")

    def sculpted(self, f: Fighter, sid: str, victims: list[Fighter], level: int | None = None) -> set[int]:
        """An evoker's Sculpt Spells: up to one plus the spell's level of their friends caught in the area are left
        untouched."""
        spell = self.t.spells[spell_id(sid)]
        if f.char is None or not f.has_trait("sculpt_spells") or spell.get("school") != "evocation":
            return set()
        n = 1 + (level if level is not None else spell["level"])
        friends = [x for x in victims if x.side == f.side]
        return {x.id for x in friends[:n]}

    def in_area(self, cells: list[tuple[int, int]], who: str = "all", caster: Fighter | None = None) -> list[Fighter]:
        cs = set(cells)
        out = []
        for x in self.fighters:
            if not (x.active or x.state == "down"):
                continue
            if who == "enemies" and caster is not None and x.side == caster.side:
                continue
            if who == "allies" and caster is not None and x.side != caster.side:
                continue
            if any(c in cs for c in x.cells):
                out.append(x)
        return out

    def cast_problem(self, f: Fighter, sid: str, target: Fighter | None = None, point: tuple[int, int] | None = None) -> str | None:
        spell = self.t.spells[spell_id(sid)]
        if sid.startswith("throw:"):
            if f.char is None or f.char.item(int(sid.split(":")[1])) is None:
                return "you have none left"
            if f.action <= 0 and f.attacks_left <= 0:
                return "no action left this turn"
        opts = {s: (ok, why) for s, ok, why in self.spell_options(f)} if not sid.startswith("throw:") else {}
        if sid in opts and not opts[sid][0]:
            return opts[sid][1]
        mode = spell["target"]
        if mode in ("enemy", "ally", "downed_ally", "dead_ally"):
            if target is None or target not in self.spell_targets(f, sid):
                return "out of reach" if target is not None else "no target"
        elif mode in ("point", "direction"):
            if point is None or point not in self.spell_points(f, sid):
                return "you cannot aim it there"
        return None

    def do_cast(self, f: Fighter, sid: str, target: Fighter | None = None, slot_level: int | None = None,
                point: tuple[int, int] | None = None) -> bool:
        why = self.cast_problem(f, sid, target, point)
        if why:
            self.say(f"Not possible: {why}.", "warn")
            return False
        scroll = None
        charged = None
        if sid.startswith("charge:"):
            _, uid, sid = sid.split(":", 2)
            item = f.char.item(int(uid))
            from realmwalker.rules import magic

            charged = next((p for p in magic.props(item) if p.get("kind") == "charges" and p.get("spell") == sid),
                           None) if item is not None else None
            if charged is None or int(charged.get("left", charged.get("value", 1))) <= 0:
                self.say("It has no power left until dawn.", "warn")
                return False
            charged["left"] = int(charged.get("left", charged.get("value", 1))) - 1
            self.say(f"{f.the_name} calls on the power in the {self.t.items.name(item, False)}.", "magic")
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
        bonus_cast = spell.get("cast") == "bonus"
        if flask is not None:
            # A flask thrown: the thrower's aim makes it hard to dodge (8 + proficiency + Dexterity); no magic is spent.
            remove_item(c, flask.uid, 1)
            self._spend(f, False)
            f.hidden = 0
            dc = 8 + s.proficiency + s.mod("dex")
            self.cast(f, sid, spell, target, point, up=0, mod=s.mod("dex"), dc=dc, bonus=s.proficiency + s.mod("dex"),
                      mult=1, level=0)
            self._after_action(f)
            return True
        if scroll is not None:
            remove_item(c, scroll.uid, 1)
            if c.cls not in spell["classes"]:
                roll = dice.d20(self.rng).natural
                bonus = f.skill("arcana")
                self.dice_say(f"Arcana ({f.name}): {roll} {signed_mod(bonus)} = {roll + bonus} vs DC {10 + level}")
                if roll + bonus < 10 + level:
                    self._spend(f, bonus_cast)
                    self.say(f"{f.the_name} stumbles over the words of the scroll, and it crumbles to dust.", "warn")
                    self._after_action(f)
                    return True
            self.say(f"{f.the_name} reads from a scroll.", "magic")
            level = 0  # the scroll's own magic: no spell slot
        if charged is not None:
            level = 0  # the item's own magic
        if level > 0:
            slot_level = slot_level or spellrules.lowest_free_slot(c, self.t, level)
            if slot_level is None:
                self.say("No spell slot left for that.", "warn")
                return False
            spellrules.spend_slot(c, slot_level)
        self._spend(f, bonus_cast)
        if bonus_cast:
            f.cast_bonus_spell = True
        else:
            f.cast_action_spell = True
        f.hidden = 0
        up = max(0, (slot_level or level) - level)
        mod = s.mod(spellrules.casting_ability(c, self.t))
        dc = spellrules.save_dc(s, self.t)
        bonus = spellrules.attack_bonus(s, self.t) + s.attack_condition()
        mult = spellrules.cantrip_multiplier(c.level) if spell.get("cantrip_scaling") else 1
        self.cast(f, sid, spell, target, point, up=up, mod=mod, dc=dc, bonus=bonus, mult=mult, level=slot_level or level)
        self._after_action(f)
        return True

    def cast(self, f: Fighter, sid: str, spell: dict, target: Fighter | None, point: tuple[int, int] | None, *,
             up: int, mod: int, dc: int, bonus: int, mult: int, level: int) -> None:
        """A spell's effects, once it has been paid for (rules/engine/effects.py)."""
        effects.cast(self, f, sid, spell, target, point, up=up, mod=mod, dc=dc, bonus=bonus, mult=mult, level=level)

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
            x.buffs = [b for b in x.buffs if b.get("conc") != f.id]
            for se in [se for se in x.save_ends if se.get("conc") == f.id]:
                x.conditions.pop(se["cond"], None)
                x.save_ends.remove(se)
        for z in [z for z in self.zones if z.owner == f.id and z.rounds < 0]:
            self._remove_zone(z)
        for tok in [t for t in self.tokens if t.owner == f.id and t.rounds < 0]:
            self.tokens.remove(tok)  # a spiritual weapon held by concentration (2024)
            self._event("token_end", id=tok.id)
        durations.end_concentration(self, f)
        for x in self.fighters:  # a lasting spell held by concentration (Shield of Faith) ends with it
            if x.id in conc.get("on", []) and x.char is not None:
                spellrules.end(x.char, sid)
                x.buffs = [b for b in x.buffs if b.get("lasting") != sid]
        if not quiet:
            name = self.t.spells[sid]["name"] if sid in self.t.spells else "the spell"
            self.say(f"{f.the_name}'s {name} {why or 'ends'}.", "magic")
        self._event("concentration_end", who=f.id, spell=sid)

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
            if z.kind == "web":
                for x in self.fighters:
                    if x.conditions.get("restrained") == -1 and any(c in z.cells for c in x.cells):
                        x.conditions.pop("restrained", None)
            if z.kind == "guardian":
                self.tokens = [t for t in self.tokens if t.id != getattr(z, "token", -1)]
            self._sync_zones()
            self._event("zone_end", id=z.id)

    def _sync_zones(self) -> None:
        W, H = self.field.width, self.field.height
        opaque = np.zeros((W, H), dtype=bool)
        difficult = np.zeros((W, H), dtype=bool)
        for z in self.zones:
            for (x, y) in z.cells:
                if 0 <= x < W and 0 <= y < H:
                    if z.opaque:
                        opaque[x, y] = True
                    if z.difficult and z.kind != "guardians":
                        difficult[x, y] = True
        self.field.set_zones(opaque, difficult)

    def _follow_auras(self) -> None:
        """An aura (Spirit Guardians) moves with whoever carries it."""
        for z in self.zones:
            if z.kind != "guardians" or z.owner is None:
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
            if z.friends_safe and z.owner is not None:
                owner = next((x for x in self.fighters if x.id == z.owner), None)
                if owner is not None and owner.side == f.side:
                    continue
            if f.id in z.struck:
                continue
            if z.kind == "web":
                stopped = self._zone_catch(f, z) or stopped
            elif z.kind in ("fire", "guardians", "guardian") and z.damage:
                z.struck.add(f.id)
                owner = next((x for x in self.fighters if x.id == z.owner), None)
                before = f.hp
                if z.kind == "fire":
                    self.say(f"{f.the_name} is in the flames.", "danger" if f.side == PARTY else "info")
                self._save_damage(owner or f, f, z.save, z.dc, z.damage, z.damage_type, z.on_save)
                if z.kind == "guardian":
                    z.budget -= max(0, before - f.hp)
                    if z.budget <= 0:
                        self.say("The guardian fades, its strength spent.", "magic")
                        self._remove_zone(z)
        return stopped

    def _zone_catch(self, f: Fighter, z: Zone) -> bool:
        if z.kind != "web" or "restrained" in f.conditions or "web" in trs.values(f, "ignores_zone", flat=True):
            return False
        z.struck.add(f.id)
        if self._save(f, "dex", z.dc):
            return False
        f.conditions["restrained"] = -1
        f.move_left = 0
        self._event("condition", who=f.id, cond="restrained")
        self.say(f"{f.the_name} is caught in the web.", "good" if f.side == FOE else "danger")
        return True

    def _heal(self, f: Fighter, amount: int) -> None:
        if f.state == "dead":
            return
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
        foes = self.side(FOE)
        dead = [f.creature for f in foes if f.state == "dead"]
        captives = [f.creature for f in foes if f.state == "surrendered" or ("unconscious" in f.conditions and f.state == "fighting")]
        fled = [f.creature for f in foes if f.state in ("fled", "fleeing")]
        xp = 0
        if self.outcome in ("victory", "parley"):
            for f in foes:
                value = int(f.cdef["xp"])
                if f.state == "dead" or f in [x for x in foes if x.creature in captives]:
                    xp += value
                elif f.state in ("fled", "fleeing") and f.damage_taken > 0:
                    xp += value // 2
            if self.outcome == "parley":
                xp //= 2
        money = sum(c.money for c in dead)
        items = [i for c in dead for i in c.inventory] + list(self.thrown)
        party_dead = [f.char for f in self.side(PARTY) if f.state == "dead"]
        return BattleResult(self.outcome or "victory", xp, dead, captives, fled, money, items, party_dead, self.round,
                            self.robbed_money)


def signed_mod(n: int) -> str:
    return f"+{n}" if n > 0 else (f"-{-n}" if n < 0 else "")


def _avg(expr: str) -> float:
    try:
        n, sides, flat = dice.parse(expr)
    except dice.DiceError:
        return 0.0
    return n * (sides + 1) / 2 + flat
