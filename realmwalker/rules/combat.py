"""Battles: rank combat (front and back rank per side) on 5e dice. Pure logic, no drawing.

Flow: create a Battle, call start(). Then repeatedly call step(): it runs start-of-turn effects,
skips anyone who cannot act, and plays enemy turns (one per call, so the screen can pace them).
When step() returns False and pending_party() gives a fighter, the player chooses an action and
calls one of the do_* methods. When `outcome` is set, the battle is over; result() summarises it.

Rules used (v1 simplifications from the design): one action per turn, no reactions, bonus actions,
opportunity attacks or concentration. Melee reaches only the enemy front rank (unless it is empty,
or the weapon has reach); melee from the back rank needs reach. Ranged attacks and spells reach
anyone; a ranged attack from the front rank while engaged has disadvantage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.rules import spells as spellrules
from realmwalker.rules.character import Character, Sheet, modifier
from realmwalker.rules.creatures import Creature
from realmwalker.rules.inventory import remove_item
from realmwalker.rules.wounds import ARMOR_FACTOR, PART_GROUP, make_wound, roll_location, severity_for, wound_chance

FRONT, BACK = "front", "back"
PARTY, FOE = "party", "foe"
SIZES = ["tiny", "small", "medium", "large", "huge", "gargantuan"]
MORALE_HP = {"beast": 0.4, "bandit": 0.35, "coward": 0.6, "soldier": 0.3, "warrior": 0.15}
FEARLESS = {"fanatic", "mindless"}
MERCIFUL = {"bandit", "coward", "soldier"}  # these rob a beaten party and leave it alive
METAL = {"chain_shirt", "scale_mail", "breastplate", "half_plate", "ring_mail", "chain_mail", "splint_armor", "plate_armor"}


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

    @property
    def is_melee(self) -> bool:
        return self.kind in ("melee", "spell_melee")


@dataclass
class Env:
    light: float = 1.0
    rain: bool = False
    place: str = ""
    ground: str = "ground"
    party_light: bool = False  # a torch or lantern is lit
    surprised: str | None = None  # PARTY or FOE


class Fighter:
    def __init__(self, fid: int, side: str, rank: str, tables, *, char: Character | None = None,
                 creature: Creature | None = None) -> None:
        self.id = fid
        self.side = side
        self.rank = rank
        self.t = tables
        self.char = char
        self.creature = creature
        self.cdef = tables.creatures[creature.def_id] if creature else None
        self.initiative = 0
        self.state = "fighting"  # fighting, fleeing, down, dead, fled, surrendered
        self.conditions: dict[str, int] = {}
        self.buffs: list[dict] = []
        self.dying = 0
        self.stable = False
        self.dodging = False
        self.helped = False
        self.marked = False
        self.surprised = False
        self.extra_actions = 0
        self.free_rank_change = False
        self.took_fire = False
        self.morale_checked: set[str] = set()
        self.damage_taken = 0
        self.uncanny_used_round = -1
        self.died_round = -1

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

    def save_bonus(self, ability: str) -> int:
        if self.char:
            return self.sheet.save_bonus(ability)
        return self.mod(ability)

    def buff_value(self, key: str) -> list:
        return [b[key] for b in self.buffs if key in b]

    def ac(self) -> int:
        if self.char:
            s = self.sheet
            ac = s.armor_class()
            for base in self.buff_value("mage_armor"):
                if self.char.equipped_item("armor") is None:
                    ac = max(ac, base + s.mod("dex"))
            return ac + sum(self.buff_value("ac"))
        return int(self.cdef["ac"]) + sum(self.buff_value("ac"))

    @property
    def size(self) -> str:
        if self.char:
            return self.t.races[self.char.race]["size"]
        return self.cdef["size"]

    @property
    def speed(self) -> int:
        if self.char:
            return self.sheet.speed()
        return int(self.cdef["speed"])

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
        if self.char:
            return self.sheet.has_rule(trait)
        return trait in self.cdef.get("traits", [])

    @property
    def morale_type(self) -> str:
        return "fanatic" if self.char else self.cdef.get("morale", "warrior")

    # ------------------------------------------------------------------ state
    @property
    def active(self) -> bool:
        """Still in the fight (can be targeted and threatens the other side)."""
        return self.state in ("fighting", "fleeing")

    @property
    def standing(self) -> bool:
        return self.active and "unconscious" not in self.conditions

    def can_act(self) -> bool:
        return (self.state in ("fighting", "fleeing") and "unconscious" not in self.conditions
                and "stunned" not in self.conditions)

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
    """The spell behind a spell-menu value (a spell id, or "scroll:<uid>:<spell id>")."""
    return value.split(":", 2)[2] if value.startswith(("scroll:", "charge:")) else value


class Battle:
    def __init__(self, tables, party: list[Character], foes: list[Creature], env: Env, rng: RNG, *,
                 show_dice: bool = True, title: str = "", now: int = 0) -> None:
        self.t = tables
        self.rng = rng
        self.env = env
        self.show_dice = show_dice
        self.title = title
        self.now = now
        self.log: list[tuple[str, str]] = []
        self.fighters: list[Fighter] = []
        fid = 1
        for i, c in enumerate(party):
            rank = FRONT if i == 0 or self._prefers_front(c) else BACK
            f = Fighter(fid, PARTY, rank, tables, char=c)
            # Spells cast before the fight and still working (Stoneskin, Death Ward...) come into it with them.
            for sid in spellrules.lasting(c, tables):
                part = spellrules.battle_part(tables, sid)
                if part:
                    f.buffs.append(part)
            self.fighters.append(f)
            fid += 1
        for cr in foes:
            rank = tables.creatures[cr.def_id].get("rank", FRONT)
            self.fighters.append(Fighter(fid, FOE, rank, tables, creature=cr))
            fid += 1
        # Nobody fights from an empty front: if a side put everyone at the back, the first steps forward.
        for side in (PARTY, FOE):
            members = [f for f in self.fighters if f.side == side]
            if members and not any(f.rank == FRONT for f in members):
                members[0].rank = FRONT
        self.order: list[int] = []
        self.turn = 0
        self.round = 1
        self.turn_started = False
        self.outcome: str | None = None
        self.known: set[str] = set()
        self.initial_foes = len(foes)
        self.robbed_money = 0
        self.thrown: list = []  # weapons thrown during the fight, lying on the field afterwards

    def _prefers_front(self, c: Character) -> bool:
        return self.t.classes[c.cls]["hit_die"] >= 10

    # ------------------------------------------------------------------ helpers
    def say(self, text: str, category: str = "info") -> None:
        self.log.append((text[:1].upper() + text[1:], category))

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

    def rank_of(self, side: str, rank: str) -> list[Fighter]:
        return [f for f in self.fighters if f.side == side and f.rank == rank and f.active]

    def engaged(self, f: Fighter) -> bool:
        """In the front rank, facing enemies who could strike back."""
        other = FOE if f.side == PARTY else PARTY
        return f.rank == FRONT and any(x.standing for x in self.rank_of(other, FRONT))

    def pending_party(self) -> Fighter | None:
        if self.outcome is not None or not self.order:
            return None
        f = self.current
        if f.side == PARTY and self.turn_started and f.can_act() and not f.surprised:
            return f
        return None

    # ------------------------------------------------------------------ start
    def start(self, intro: str = "") -> None:
        for f in self.fighters:
            f.initiative = dice.d20(self.rng).natural + f.mod("dex")
            if self.env.surprised == f.side:
                f.surprised = True
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
        for def_id in {f.creature.def_id for f in self.side(FOE)}:
            d = self.t.creatures[def_id]
            skill = skill_for.get(d["kind"], "arcana")
            dc = 8 + int(round(d["cr"] * 3))
            best = max(party, key=lambda p: p.skill(skill), default=None)
            if best is None:
                continue
            roll = dice.d20(self.rng).natural
            total = roll + best.skill(skill)
            if total >= dc:
                self.known.add(def_id)
                danger = "a real threat" if d["cr"] >= 1 else ("dangerous in numbers" if d["cr"] >= 0.25 else "weak alone")
                self.say(f"{best.name} knows {d['plural']}: {danger} (AC {d['ac']}).", "info")
            self.dice_say(f"{self.t.rules['skills'][skill]['name']} ({best.name}): {roll} {signed_mod(best.skill(skill))} = {total} vs DC {dc}")

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
            f.surprised = False
            if f.active:
                self.say(f"{f.the_name} is caught flat-footed.", "system")
            self.end_turn()
            return True
        if not f.can_act():
            if f.state == "fighting" and "stunned" in f.conditions:
                self.say(f"{f.the_name} cannot move.", "system")
            self.end_turn()
            return True
        if f.side == PARTY:
            return False
        self._ai(f)
        if self.outcome is None and self.turn_started and self.current is f:
            self.end_turn()
        return True

    def _start_of_turn(self, f: Fighter) -> None:
        f.dodging = False
        f.free_rank_change = False
        for b in list(f.buffs):
            if "rounds" in b:
                b["rounds"] -= 1
                if b["rounds"] < 0:
                    f.buffs.remove(b)
        if f.state == "down":
            if not f.stable:
                f.dying -= 1
                if f.dying <= 0:
                    self._kill(f, "bleeds out")
                else:
                    self.say(f"{f.the_name} is bleeding out ({f.dying} round{'s' if f.dying != 1 else ''} left).", "danger")
            return
        if not f.active:
            return
        # Regeneration (trolls), spiritual weapons and holy auras.
        if f.has_trait("regeneration") and f.hp > 0 and not f.took_fire:
            healed = min(10, f.max_hp - f.hp)
            if healed:
                f.hp += healed
                self.say(f"{f.the_name}'s wounds knit closed before your eyes.", "danger")
        f.took_fire = False
        if f.char and f.state == "fighting" and "stunned" not in f.conditions:
            from realmwalker.rules import health

            if health.concussed(f.char) and self.rng.chance(0.06):
                f.conditions["stunned"] = 1
                self.say(f"{f.the_name}'s sight swims and goes dark for a moment.", "danger")
            elif health.pain(f.char, self.t) >= 15 and not self._save(f, "con", 10, quiet=True):
                f.conditions["stunned"] = 1
                self.say(f"The pain is too much: {f.the_name} can only gasp.", "danger")
        for b in list(f.buffs):
            if "spirit_weapon" in b:
                targets = [x for x in self.enemies_of(f) if x.rank == FRONT] or self.enemies_of(f)
                if targets:
                    target = self.rng.choice(targets)
                    opt = AttackOption("spirit", "spiritual weapon", "spell_ranged", b["bonus"], b["spirit_weapon"], "force")
                    self._attack(f, opt, target)
            if "aura" in b:
                aura = b["aura"]
                for target in [x for x in self.enemies_of(f) if x.rank == FRONT]:
                    self._save_damage(f, target, aura["save"], aura["dc"], aura["damage"], aura["damage_type"], "half")
        # Bleeding wounds cost hit points each round.
        bleed = sum(w.bleed for w in f.wounds if not w.bandaged)
        if bleed and f.hp > 0:
            loss = max(1, bleed // 2)
            self.say(f"{f.the_name} is bleeding.", "danger")
            self._apply_hp_loss(f, loss, source=None, cause="blood loss")
        for cond in list(f.conditions):
            if cond == "prone":
                if f.can_act() and f.state == "fighting":
                    del f.conditions["prone"]
                    self.say(f"{f.the_name} gets up.", "system")
                continue
            if f.conditions[cond] > 0:
                f.conditions[cond] -= 1
                if f.conditions[cond] == 0:
                    del f.conditions[cond]
                    if cond in ("stunned", "restrained", "frightened"):
                        self.say(f"{f.the_name} is no longer {cond}.", "system")

    def end_turn(self) -> None:
        if self.outcome is not None:
            return
        f = self.current
        if f.extra_actions > 0 and f.can_act() and f.state == "fighting":
            f.extra_actions -= 1
            self.say(f"{f.the_name} pushes on (Action Surge).", "good")
            return
        self._check_end()
        if self.outcome is not None:
            return
        self.turn += 1
        if self.turn >= len(self.order):
            self.turn = 0
            self.round += 1
        self.turn_started = False

    def _check_end(self) -> None:
        foes = [f for f in self.side(FOE) if f.active and "unconscious" not in f.conditions]
        party = [f for f in self.side(PARTY) if f.active and "unconscious" not in f.conditions]
        if not foes:
            self.outcome = "victory"
        elif not party:
            self.outcome = "defeat"

    # ------------------------------------------------------------------ attack options
    def attack_options(self, f: Fighter) -> list[AttackOption]:
        if f.creature:
            out = []
            for i, a in enumerate(f.cdef["attacks"]):
                kind = a["kind"]
                out.append(AttackOption(f"c{i}", a["name"], kind, int(a["bonus"]), a["damage"], a["damage_type"],
                                        reach=bool(a.get("reach")), extra=a))
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
            out.append(self._weapon_option(f, s, it, key, two_handed_free=(key == "main" and off is None)))
        for it in c.inventory:
            d = items.get(it.def_id)
            if d["category"] == "weapon" and "thrown" in d.get("properties", []) and it.uid not in (c.equipped.values()):
                opt = self._weapon_option(f, s, it, f"throw{it.uid}", thrown=True)
                opt.name = f"throw {d['name']}"
                out.append(opt)
        unarmed_bonus = s.proficiency + s.mod("str") + s.attack_condition()
        fists = AttackOption("unarmed", "fists", "melee", unarmed_bonus, str(max(1, 1 + s.mod("str"))), "bludgeoning")
        from realmwalker.rules import health

        if health.broken_arm(c, "right") and health.broken_arm(c, "left"):
            fists.available, fists.reason = False, "both arms are broken"
        out.append(fists)
        return out

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
        dmg = d["damage"]
        if "versatile" in props and two_handed_free and not ranged:
            dmg = d.get("versatile", dmg)
        mod = s.mod(ability)
        if key == "off" and not thrown:
            mod = min(0, mod)  # the off hand adds no bonus damage
        mod += enchant
        if f.char.fighting_style == "dueling" and not ranged and "two_handed" not in props and key == "main":
            off = f.char.equipped_item("off_hand")
            if off is None or self.t.items.category(off) == "shield":
                mod += 2
        damage = f"{dmg}{signed_mod(mod)}"
        opt = AttackOption(key, d["name"], "ranged" if ranged else "melee", bonus, damage, d["damage_type"],
                           reach="reach" in props, properties=list(props), item_uid=it.uid)
        # A broken arm cannot hold a weapon; two-handed weapons need both.
        from realmwalker.rules import health

        right, left = health.broken_arm(f.char, "right"), health.broken_arm(f.char, "left")
        if key == "main" and right or key == "off" and left or thrown and right and left:
            opt.available, opt.reason = False, "that arm is broken"
        elif "two_handed" in props and (right or left):
            opt.available, opt.reason = False, "it needs two good arms"
        if "ammunition" in props:
            ammo = d.get("ammo")
            opt.ammo_def = ammo
            if not any(i.def_id == ammo for i in f.char.inventory):
                opt.available = False
                opt.reason = f"no {self.t.items.get(ammo)['name']}s left"
        return opt

    def targets_for(self, f: Fighter, kind: str, reach: bool = False) -> list[Fighter]:
        """Who this fighter could hit with an attack of this kind."""
        enemies = [x for x in self.enemies_of(f)]
        if kind in ("melee", "spell_melee"):
            if f.rank == BACK and not reach:
                return []
            front = [x for x in enemies if x.rank == FRONT]
            if reach or not front:
                return enemies
            return front
        return enemies

    def can_melee(self, f: Fighter, opt: AttackOption) -> tuple[bool, str]:
        if f.rank == BACK and not opt.reach:
            return False, "too far back for a melee blow (change rank, or use a reach weapon)"
        return True, ""

    # ------------------------------------------------------------------ resolving attacks
    def _adv_dis(self, att: Fighter, target: Fighter, opt: AttackOption) -> tuple[bool, bool, list[str]]:
        adv, dis, why = False, False, []
        if att.helped:
            adv = True
            why.append("helped")
        if target.marked:
            adv = True
            why.append("marked")
        if "prone" in target.conditions:
            if opt.is_melee:
                adv = True
            else:
                dis = True
            why.append("target prone")
        if any(c in target.conditions for c in ("restrained", "stunned", "unconscious")):
            adv = True
            why.append("target helpless")
        if target.dodging:
            dis = True
            why.append("dodging")
        if any(c in att.conditions for c in ("prone", "frightened", "poisoned", "blinded", "restrained")):
            dis = True
            why.append("hampered")
        if att.char and att.char.exhaustion >= 3:
            dis = True
            why.append("exhausted")
        dark = self.env.light < 0.35
        if dark and att.darkvision <= 0 and not (att.side == PARTY and self.env.party_light):
            if not (att.side == FOE and self.env.party_light):
                dis = True
                why.append("darkness")
        if opt.kind == "ranged" and self.engaged(att):
            dis = True
            why.append("in melee")
        if opt.kind == "ranged" and self.env.rain and "ammunition" in opt.properties:
            dis = True
            why.append("rain")
        if att.has_trait("pack_tactics") and opt.is_melee:
            if any(x is not att and x.standing and x.rank == FRONT for x in self.allies_of(att)):
                adv = True
                why.append("pack")
        if att.char and "heavy" in opt.properties and att.size == "small":
            dis = True
            why.append("too heavy")
        if att.char:
            armor = att.char.equipped_item("armor")
            if armor is not None and not att.sheet.proficient_with_armor(armor):
                dis = True
                why.append("untrained in armour")
        if opt.extra.get("metal_advantage") and target.char:
            armor = target.char.equipped_item("armor")
            if armor is not None and armor.def_id in METAL:
                adv = True
        return adv, dis, why

    def _attack(self, att: Fighter, opt: AttackOption, target: Fighter, *, spell_text: str = "") -> bool:
        adv, dis, why = self._adv_dis(att, target, opt)
        roll = dice.d20(self.rng, advantage=adv, disadvantage=dis)
        natural = roll.natural
        if natural == 1 and att.char and att.has_trait("lucky"):
            natural = dice.d20(self.rng).natural
            self.dice_say(f"{att.name} is lucky: rerolls the 1 and gets {natural}.")
        crit_on = 19 if att.char and att.has_trait("crit_19") else 20
        crit = natural >= crit_on
        bless = sum(dice.roll(d, self.rng).total for d in att.buff_value("attack_die"))
        total = natural + opt.bonus + bless
        ac = target.ac()
        hit = crit or (natural != 1 and total >= ac)
        att.helped = False
        mode = " (adv)" if adv and not dis else (" (dis)" if dis and not adv else "")
        self.dice_say(f"{att.name} → {target.name}, {opt.name}{mode}: {natural} {signed_mod(opt.bonus + bless)} = {total} vs AC {ac}"
                      f" — {'critical!' if crit else ('hit' if hit else 'miss')}" + (f" [{', '.join(why)}]" if why else ""))
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
            armor = target.armor_name("torso")
            if armor and total >= ac - 4 and natural != 1:
                text = self.rng.choice(self.t.combat_text["armored_miss"])
            else:
                text = self.rng.choice(self.t.combat_text["miss"])
            self.say(self._fill(text, att, target, weapon=weapon, armor=armor or "armour"), "flavor")
            return False
        if target.marked:
            target.marked = False
        dmg_expr = opt.damage
        n, sides, flat = dice.parse(dmg_expr)
        rolled = dice.roll(dmg_expr, self.rng, double_dice=crit)
        amount = rolled.total
        # Great Weapon Fighting: reroll ones and twos once.
        if att.char and att.char.fighting_style == "great_weapon" and opt.is_melee and "two_handed" in opt.properties:
            amount = sum(r if r > 2 else self.rng.randint(1, sides) for r in rolled.rolls) + flat
        if crit and att.char and opt.is_melee and att.has_trait("savage_attacks"):
            amount += self.rng.randint(1, sides)
        amount += self._sneak_attack(att, target, opt, adv and not dis, crit)
        if att.char and opt.kind in ("melee", "ranged") and att.has_trait("divine_strike"):
            amount += dice.roll("1d8", self.rng, double_dice=crit).total
        if att.creature and att.cdef.get("attacks") and opt.extra.get("poison"):
            poison = opt.extra["poison"]
            self._save_damage(att, target, "con", poison["dc"], poison["damage"], "poison", "half", quiet=True)
        self._hit(att, target, max(1, amount), opt.damage_type, crit=crit, weapon=opt.name,
                  bite=opt.extra.get("wound") == "bite", claws=opt.extra.get("wound") == "cut" and att.creature is not None and opt.name == "claws")
        if target.active and opt.extra.get("trip_dc") and "prone" not in target.conditions:
            if not self._save(target, "str", int(opt.extra["trip_dc"])):
                target.conditions["prone"] = -1
                self.say(f"{target.the_name} is dragged down.", "danger")
        if target.active and opt.extra.get("paralyze_dc"):
            immune = target.char and target.char.race == "elf"
            if not immune and not self._save(target, "con", int(opt.extra["paralyze_dc"])):
                target.conditions["stunned"] = 2
                self.say(f"{target.the_name} goes rigid, paralysed by the touch.", "danger")
        if opt.extra.get("disease") and target.char and self.rng.chance(float(opt.extra.get("disease_chance", 1.0))):
            target.char.conditions.append(f"exposed:{opt.extra['disease']}")
        return True

    def _sneak_attack(self, att: Fighter, target: Fighter, opt: AttackOption, advantage: bool, crit: bool) -> int:
        if not att.char or "sneak_attack" not in att.char.features or att.char.uses.get("sneak_round") == self.round:
            return 0
        if opt.kind == "melee" and "finesse" not in opt.properties:
            return 0
        ally_engaged = any(x is not att and x.standing and x.rank == FRONT for x in self.allies_of(att)) and target.rank == FRONT
        if not (advantage or ally_engaged):
            return 0
        att.char.uses["sneak_round"] = self.round
        n = (att.char.level + 1) // 2
        extra = dice.roll(f"{n}d6", self.rng, double_dice=crit).total
        self.say(f"{att.the_name} finds the gap.", "good")
        return extra

    def _save(self, f: Fighter, ability: str, dc: int, *, quiet: bool = False) -> bool:
        adv = False
        if ability == "con" and f.has_trait("poison_resilience"):
            adv = True
        roll = dice.d20(self.rng, advantage=adv)
        bonus = f.save_bonus(ability) + sum(dice.roll(d, self.rng).total for d in f.buff_value("save_die"))
        total = roll.natural + bonus
        ok = total >= dc
        if not quiet:
            self.dice_say(f"{f.name} {ability.upper()} save: {roll.natural} {signed_mod(bonus)} = {total} vs DC {dc} — "
                          f"{'saved' if ok else 'failed'}")
        return ok

    def _save_damage(self, att: Fighter, target: Fighter, ability: str, dc: int, expr: str, dtype: str, on_save: str,
                     *, quiet: bool = False) -> None:
        amount = dice.roll(expr, self.rng).total
        saved = self._save(target, ability, dc, quiet=quiet)
        if dtype == "poison" and not saved and target.char and not target.has_trait("poison_resilience"):
            target.conditions["poisoned"] = 10
        if saved:
            if ability == "dex" and target.char and target.has_trait("evasion"):
                amount = 0
            elif on_save == "half":
                amount //= 2
            else:
                amount = 0
        elif ability == "dex" and target.char and target.has_trait("evasion"):
            amount //= 2
        if amount > 0:
            self._hit(att, target, amount, dtype, crit=False, weapon=dtype)

    def _hit(self, att: Fighter | None, target: Fighter, amount: int, dtype: str, *, crit: bool, weapon: str,
             bite: bool = False, claws: bool = False) -> None:
        """Damage that landed: resistances, text, wounds, going down."""
        if target.creature:
            if dtype in target.cdef.get("immune", []):
                self.say(f"{target.the_name} does not seem to feel it.", "flavor")
                return
            if dtype in target.cdef.get("vulnerable", []):
                amount *= 2
        resist = [r for b in target.buffs for r in b.get("resist", [])]
        if target.char is not None:
            from realmwalker.rules import magic

            resist += magic.resistances(target.char)
        if dtype in resist or (dtype == "poison" and target.has_trait("poison_resilience")):
            amount = max(1, amount // 2)
        if target.char and target.has_trait("uncanny_dodge") and target.uncanny_used_round != self.round and att is not None:
            target.uncanny_used_round = self.round
            amount = max(1, amount // 2)
            self.say(f"{target.the_name} rolls with the blow.", "good")
        if dtype in ("fire", "acid"):
            target.took_fire = True
        part = roll_location(self.t.combat_text["locations"].get(target.body, self.t.combat_text["locations"]["humanoid"]), self.rng)
        names = self.t.combat_text["part_names"].get(target.body, self.t.combat_text["part_names"]["humanoid"])
        part_text = self.rng.choice(names.get(part, [part.replace("_", " ")]))
        style = "bite" if bite else ("claws" if claws else dtype)
        templates = self.t.combat_text["hit"].get(style) or self.t.combat_text["hit"]["bludgeoning"]
        text = self._fill(self.rng.choice(templates), att, target, weapon=weapon, part=part_text)
        if crit:
            text = f"{self.rng.choice(self.t.combat_text['crit'])} {text}"
        hp_before = target.hp
        self.say(f"{text} <dim>({amount})</>", "danger" if target.side == PARTY else "info")
        self._apply_hp_loss(target, amount, source=att, cause=f"{att.the_name if att else 'a wound'}'s {weapon}" if att else weapon)
        target.damage_taken += amount
        if target.state not in ("dead",) and hp_before > 0:
            chance = wound_chance(amount, target.max_hp, target.hp, crit, target.armor_factor(part))
            if self.rng.chance(chance):
                severity = severity_for(amount, target.max_hp, crit, self.rng)
                wound = make_wound(part, dtype, severity, self.rng, bite=bite, now=self.now,
                                   note=f"{att.cdef['name'] if att and att.creature else weapon}")
                if wound is not None:
                    target.wounds.append(wound)
                    wt = self.t.combat_text["wound"].get(wound.kind, {}).get(str(wound.severity))
                    if wt:
                        self.say(self.rng.choice(wt), "danger" if target.side == PARTY else "flavor")
        if "unconscious" in target.conditions and target.state == "fighting" and target.hp > 0:
            del target.conditions["unconscious"]
            self.say(f"{target.the_name} wakes with a start.", "system")
        if target.active and target.side == FOE:
            self._morale_after_hit(target)

    def _apply_hp_loss(self, target: Fighter, amount: int, *, source: Fighter | None, cause: str) -> None:
        if target.state == "down":
            if not target.stable or amount > 0:
                target.stable = False
                target.dying -= 2 if amount < target.max_hp else 99
                if target.dying <= 0:
                    self._kill(target, cause)
            return
        new_hp = target.hp - amount
        if new_hp <= 0:
            if target.creature and target.creature.uses.get("relentless") and amount <= 7:
                target.creature.uses["relentless"] = 0
                target.hp = 1
                self.say(f"{target.the_name} refuses to fall.", "danger")
                return
            if target.creature and target.has_trait("undead_fortitude") and self.rng.random() < 0.5:
                if self._save(target, "con", 5 + amount):
                    target.hp = 1
                    self.say(f"{target.the_name} shudders and keeps coming.", "danger")
                    return
            ward = next((b for b in target.buffs if b.get("death_ward")), None)
            if ward is not None:
                target.buffs.remove(ward)
                if ward.get("lasting") and target.char:
                    spellrules.end(target.char, ward["lasting"])  # spent: it does not come into the next fight
                target.hp = 1
                self.say(f"<magic>The ward over {target.the_name} takes the blow instead.</>", "good")
                return
            if target.char and target.char.uses.get("relentless_endurance"):
                target.char.uses["relentless_endurance"] = 0
                target.hp = 1
                self.say(f"{target.the_name} should be down, and is not.", "good")
                return
            target.hp = 0
            if target.char:
                target.state = "down"
                target.conditions = {"unconscious": -1, "prone": -1}
                target.dying = max(1, 3 + target.mod("con"))
                target.stable = False
                self.say(self._fill(self.rng.choice(self.t.combat_text["down"]), source, target), "danger")
                self._morale_losses(target.side)
            else:
                self._kill(target, cause, killer=source)
        else:
            target.hp = new_hp

    def _kill(self, f: Fighter, cause: str, killer: Fighter | None = None) -> None:
        f.state = "dead"
        f.hp = 0
        f.died_round = self.round
        f.conditions = {}
        if f.creature:
            f.creature.alive = False
            self.say(self._fill(self.rng.choice(self.t.combat_text["dead"]), killer, f), "good" if f.side == FOE else "danger")
            if killer is not None and killer.char:
                killer.char.kills[f.cdef["name"]] = killer.char.kills.get(f.cdef["name"], 0) + 1
        else:
            f.char.alive = False
            self.say(f"<danger>{f.the_name} is dead.</> ({cause})", "danger")
        self._morale_losses(f.side)
        if f.creature and "leader" in f.cdef.get("traits", []):
            for other in self.side(f.side):
                if other.active and other is not f:
                    self._morale_check(other, "leader")

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
            else:  # bandit
                choice = "surrender" if (f.rank == FRONT or "grappled" in f.conditions) else "flee"
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
            text = self._fill(self.rng.choice(self.t.combat_text["surrender"]), None, f)
            self.say(text, "good")
            if self.rng.chance(0.5):
                self.say(self.rng.choice(self.t.combat_text["beg"]), "speech")
        self._morale_losses(f.side)
        self._check_end()

    # ------------------------------------------------------------------ AI
    def _ai(self, f: Fighter) -> None:
        if f.state == "fleeing":
            if f.rank == FRONT and "grappled" not in f.conditions:
                f.rank = BACK
                self.say(f"{f.the_name} backs away from the fight.", "system")
            elif "grappled" not in f.conditions:
                f.state = "fled"
                self.say(f"{f.the_name} escapes.", "system")
                self._check_end()
            return
        options = self.attack_options(f)
        melee = [o for o in options if o.is_melee]
        ranged = [o for o in options if not o.is_melee]
        # Step up if our front rank is empty and we fight in melee.
        if f.rank == BACK and melee and not ranged and not any(x.standing for x in self.rank_of(f.side, FRONT)):
            f.rank = FRONT
            self.say(f"{f.the_name} moves up.", "system")
            return
        if f.rank == FRONT and ranged and not melee and self.engaged(f) and len(self.allies_of(f)) > 1:
            f.rank = BACK
            self.say(f"{f.the_name} falls back to shoot.", "system")
            return
        attacks = max(1, int(f.cdef.get("multiattack", 1)))
        for i in range(attacks):
            if not f.can_act() or self.outcome is not None:
                return
            usable = melee if (melee and (f.rank == FRONT or any(o.reach for o in melee))) else ranged
            if f.rank == FRONT and melee and self.targets_for(f, "melee"):
                usable = melee
            if not usable:
                if melee and f.rank == BACK:
                    f.rank = FRONT
                    self.say(f"{f.the_name} pushes forward.", "system")
                return
            opt = usable[i % len(usable)] if f.cdef.get("multiattack") else max(usable, key=lambda o: _avg(o.damage))
            targets = [t for t in self.targets_for(f, opt.kind, opt.reach) if t.side == PARTY]
            targets = [t for t in targets if t.state != "down"] or targets
            if not targets:
                return
            target = min(targets, key=lambda t: (t.hp / max(1, t.max_hp)) + self.rng.random() * 0.6)
            self._attack(f, opt, target)
            self._check_end()

    # ------------------------------------------------------------------ party actions
    def do_attack(self, f: Fighter, opt: AttackOption, target: Fighter) -> None:
        attacks = 2 if f.char and f.char.level >= 5 and "extra_attack" in f.char.features and opt.kind != "spell" else 1
        for i in range(attacks):
            if target.active and self.outcome is None:
                self._attack(f, opt, target)
            elif i > 0:
                others = [t for t in self.targets_for(f, opt.kind, opt.reach)]
                if others and self.outcome is None:
                    self._attack(f, opt, self.rng.choice(others))
        self._after_action(f)

    def do_dodge(self, f: Fighter) -> None:
        f.dodging = True
        self.say(f"{f.the_name} watches for the next blow, ready to twist away.", "system")
        self._after_action(f)

    def do_help(self, f: Fighter, target: Fighter) -> None:
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
        else:
            target.helped = True
            self.say(f"{f.the_name} creates an opening for {target.the_name}.", "system")
        self._after_action(f)

    def contest(self, att: Fighter, target: Fighter) -> bool:
        a = dice.d20(self.rng).natural + att.skill("athletics")
        best = max(target.skill("athletics"), target.skill("acrobatics"))
        d = dice.d20(self.rng).natural + best
        self.dice_say(f"{att.name} Athletics {a} vs {target.name} {d}")
        return a >= d

    def can_grapple(self, att: Fighter, target: Fighter) -> tuple[bool, str]:
        if SIZES.index(target.size) > SIZES.index(att.size) + 1:
            return False, "too big to wrestle"
        if att.rank == BACK:
            return False, "too far back"
        if target.rank == BACK and any(x.standing for x in self.rank_of(target.side, FRONT)):
            return False, "their front rank is in the way"
        return True, ""

    def do_shove(self, f: Fighter, target: Fighter, mode: str) -> None:
        if self.contest(f, target):
            if mode == "prone":
                target.conditions["prone"] = -1
                self.say(f"{f.the_name} knocks {target.the_name} off {target.possessive} feet.", "good")
            else:
                target.rank = BACK
                self.say(f"{f.the_name} drives {target.the_name} back out of the line.", "good")
        else:
            self.say(f"{target.the_name} keeps {target.possessive} footing.", "system")
        self._after_action(f)

    def do_grapple(self, f: Fighter, target: Fighter) -> None:
        if self.contest(f, target):
            target.conditions["grappled"] = -1
            self.say(f"{f.the_name} gets a grip on {target.the_name} and holds on.", "good")
        else:
            self.say(f"{target.the_name} twists free of {f.the_name}'s grasp.", "system")
        self._after_action(f)

    def do_escape(self, f: Fighter) -> None:
        if dice.d20(self.rng).natural + max(f.skill("athletics"), f.skill("acrobatics")) >= 12:
            f.conditions.pop("grappled", None)
            self.say(f"{f.the_name} breaks free.", "good")
        else:
            self.say(f"{f.the_name} cannot break the hold.", "danger")
        self._after_action(f)

    def do_change_rank(self, f: Fighter) -> None:
        if "grappled" in f.conditions:
            self.say(f"{f.the_name} is held and cannot move.", "warn")
            return
        f.rank = BACK if f.rank == FRONT else FRONT
        self.say(f"{f.the_name} moves to the {f.rank} rank.", "system")
        if f.char and "cunning_action" in f.char.features and not f.free_rank_change:
            f.free_rank_change = True
            self.say(f"{f.the_name} is quick enough to act as well.", "good")
            return
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
            self._after_action(f)
            return
        self.say(f"{f.the_name} throws down {f.possessive} weapon and raises empty hands.", "warn")
        self.outcome = "surrendered"

    def flee_dc(self) -> int:
        foes = [x for x in self.side(FOE) if x.standing and x.state == "fighting"]
        if not foes:
            return 0
        fastest = max(x.speed for x in foes)
        return 10 + (fastest - 30) // 5 + max(0, len(foes) - len(self.allies_of(self.side(PARTY)[0])))

    def do_flee(self, f: Fighter) -> None:
        dc = self.flee_dc()
        runners = [x for x in self.side(PARTY) if x.standing]
        results = []
        for r in runners:
            bonus = max(r.skill("athletics"), r.skill("acrobatics"))
            penalty = 0
            if r.char and any(w.part in ("left_leg", "right_leg") and w.severity >= 2 for w in r.char.wounds):
                penalty = 5
            if "grappled" in r.conditions:
                penalty = 99
            roll = dice.d20(self.rng).natural
            results.append(roll + bonus - penalty >= dc)
            self.dice_say(f"Flee ({r.name}): {roll} {signed_mod(bonus - penalty)} = {roll + bonus - penalty} vs DC {dc}")
        if results and sum(results) * 2 >= len(results):
            self.say("You break away and run.", "warn")
            self.outcome = "fled"
        else:
            self.say("You try to get away, but they are all around you.", "danger")
            for x in self.side(FOE):
                if x.active:
                    x.helped = True
            self._after_action(f)

    # ------------------------------------------------------------------ items and abilities
    def usable_items(self, f: Fighter) -> list:  # (scrolls are read from the spell menu)
        if not f.char:
            return []
        return [i for i in f.char.inventory if self.t.items.get(i.def_id).get("use")
                and not self.t.items.get(i.def_id)["use"].get("scroll")
                and not self.t.items.get(i.def_id)["use"].get("disguise")]

    def do_item(self, f: Fighter, uid: int, target: Fighter) -> None:
        it = f.char.item(uid)
        if it is None:
            return
        d = self.t.items.get(it.def_id)
        use = d.get("use", {})
        name = d["name"]
        if "heal" in use:
            amount = dice.roll(use["heal"], self.rng).total
            self._heal(target, amount)
            self.say(f"{f.the_name} gets the {name} into {target.the_name}.", "good")
            remove_item(f.char, uid, 1)
        elif use.get("bandage"):
            bleeding = [w for w in target.wounds if w.bleed and not w.bandaged]
            if not bleeding:
                self.say(f"There is nothing on {target.the_name} that a bandage would stop.", "system")
                return
            roll = dice.d20(self.rng).natural
            bonus = f.skill("medicine")
            self.dice_say(f"Medicine ({f.name}): {roll} {signed_mod(bonus)} = {roll + bonus} vs DC 10")
            if roll + bonus >= 10:
                worst = max(bleeding, key=lambda w: w.bleed)
                worst.bandaged = True
                self.say(f"{f.the_name} binds {target.the_name}'s wound tight. The bleeding slows.", "good")
            else:
                self.say(f"The bandage soaks through at once.", "danger")
            if d.get("stack"):
                remove_item(f.char, uid, 1)
        else:
            return
        self._after_action(f)

    def class_abilities(self, f: Fighter) -> list[tuple[str, str, bool, str]]:
        """(id, name, available, why not)."""
        if not f.char:
            return []
        c = f.char
        out = []
        if "second_wind" in c.features:
            out.append(("second_wind", "Second Wind", c.uses.get("second_wind", 0) > 0, "used; rest to recover"))
        if "action_surge" in c.features:
            out.append(("action_surge", "Action Surge", c.uses.get("action_surge", 0) > 0, "used; rest to recover"))
        if "channel_divinity" in c.features:
            has = c.uses.get("channel_divinity", 0) > 0
            out.append(("turn_undead", "Turn Undead", has and any(x.kind == "undead" for x in self.enemies_of(f)),
                        "no undead here" if has else "used; rest to recover"))
            if c.subclass == "life":
                out.append(("preserve_life", "Preserve Life", has, "used; rest to recover"))
        if c.subclass == "war" and c.cls == "cleric":
            out.append(("war_priest", "War Priest (extra attack)", c.uses.get("war_priest", 0) > 0, "used; rest to recover"))
        return out

    def do_ability(self, f: Fighter, ability: str) -> None:
        c = f.char
        s = f.sheet
        if ability == "second_wind":
            c.uses["second_wind"] = 0
            amount = dice.roll("1d10", self.rng).total + c.level
            self._heal(f, amount)
            self.say(f"{f.the_name} catches {f.possessive} breath and fights on.", "good")
        elif ability == "action_surge":
            c.uses["action_surge"] = 0
            f.extra_actions += 1
            self.say(f"{f.the_name} digs deep.", "good")
            return  # the surge itself costs nothing
        elif ability == "turn_undead":
            c.uses["channel_divinity"] = 0
            dc = spellrules.save_dc(s, self.t)
            self.say(f"{f.the_name} raises the holy symbol and speaks the words of banishing.", "magic")
            for x in self.enemies_of(f):
                if x.kind != "undead":
                    continue
                if not self._save(x, "wis", dc):
                    if "destroy_undead" in c.features and x.cdef["cr"] <= 0.5:
                        self._kill(x, "turned to dust", killer=f)
                    else:
                        x.state = "fleeing"
                        self.say(f"{x.the_name} recoils from the light and flees.", "good")
        elif ability == "preserve_life":
            c.uses["channel_divinity"] = 0
            pool = 5 * c.level
            for ally in sorted(self.allies_of(f) + [x for x in self.side(f.side) if x.state == "down"],
                               key=lambda a: a.hp / max(1, a.max_hp)):
                if pool <= 0:
                    break
                need = max(0, ally.max_hp // 2 - ally.hp)
                give = min(need, pool)
                if give:
                    self._heal(ally, give)
                    pool -= give
            self.say("Warm light spreads through the wounded.", "magic")
        elif ability == "war_priest":
            c.uses["war_priest"] = c.uses.get("war_priest", 1) - 1
            opts = [o for o in self.attack_options(f) if o.available and o.item_uid is not None]
            targets = self.targets_for(f, opts[0].kind, opts[0].reach) if opts else []
            if opts and targets:
                self._attack(f, opts[0], min(targets, key=lambda t: t.hp))
            return  # an extra attack, then the normal action
        self._after_action(f)

    # ------------------------------------------------------------------ spells
    def spell_options(self, f: Fighter) -> list[tuple[str, bool, str]]:
        """(spell id, possible, why not). Scrolls in the pack appear as "scroll:<item uid>:<spell id>"."""
        if not f.char:
            return []
        out = []
        for sid in spellrules.known_spells(f.char, self.t):
            ok, why = spellrules.can_cast(f.char, self.t, sid)
            spell = self.t.spells[sid]
            if ok and spell["kind"] == "revive" and not any(i.def_id == "diamond" for i in f.char.inventory):
                ok, why = False, "needs a diamond"
            if ok and spell["target"] == "self" and sid in spellrules.lasting(f.char, self.t):
                ok, why = False, "already working on you"
            out.append((sid, ok, why))
        for it in f.char.inventory:
            sid = self.t.items.get(it.def_id).get("use", {}).get("scroll")
            if sid in self.t.spells and self.t.spells[sid]["kind"] != "revive":
                out.append((f"scroll:{it.uid}:{sid}", True, ""))
        from realmwalker.rules import magic

        for it, p in magic.charges(f.char):
            if p["spell"] in self.t.spells:
                left = int(p.get("left", p.get("value", 1)))
                out.append((f"charge:{it.uid}:{p['spell']}", left > 0, "no charges left until dawn"))
        return out

    def spell_targets(self, f: Fighter, sid: str) -> list[Fighter]:
        spell = self.t.spells[spell_id(sid)]
        target = spell["target"]
        if target == "enemy":
            kind = "spell_melee" if spell.get("attack") == "melee" or spell.get("touch") else "spell_ranged"
            return self.targets_for(f, kind)
        if target == "ally":
            return [x for x in self.side(f.side) if x.active or x.state == "down"]
        if target == "downed_ally":
            return [x for x in self.side(f.side) if x.state == "down" and not x.stable]
        if target == "dead_ally":
            return [x for x in self.side(f.side) if x.state == "dead" and self.round - x.died_round <= 10]
        return []

    def do_cast(self, f: Fighter, sid: str, target: Fighter | None, slot_level: int | None = None) -> None:
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
                return
            charged["left"] = int(charged.get("left", charged.get("value", 1))) - 1
            self.say(f"{f.the_name} calls on the power in the {self.t.items.name(item, False)}.", "magic")
        if sid.startswith("scroll:"):
            _, uid, sid = sid.split(":", 2)
            scroll = f.char.item(int(uid))
            if scroll is None:
                return
        spell = self.t.spells[sid]
        c = f.char
        s = f.sheet
        level = spell["level"]
        if scroll is not None:
            remove_item(c, scroll.uid, 1)
            if c.cls not in spell["classes"]:
                roll = dice.d20(self.rng).natural
                bonus = f.skill("arcana")
                self.dice_say(f"Arcana ({f.name}): {roll} {signed_mod(bonus)} = {roll + bonus} vs DC {10 + level}")
                if roll + bonus < 10 + level:
                    self.say(f"{f.the_name} stumbles over the words of the scroll, and it crumbles to dust.", "warn")
                    self._after_action(f)
                    return
            self.say(f"{f.the_name} reads from a scroll.", "magic")
            level = 0  # the scroll's own magic: no spell slot
        if charged is not None:
            level = 0  # the item's own magic
        if level > 0:
            slot_level = slot_level or spellrules.lowest_free_slot(c, self.t, level)
            if slot_level is None:
                self.say("No spell slot left for that.", "warn")
                return
            spellrules.spend_slot(c, slot_level)
        up = max(0, (slot_level or level) - level)
        mod = s.mod(spellrules.casting_ability(c, self.t))
        dc = spellrules.save_dc(s, self.t)
        bonus = spellrules.attack_bonus(s, self.t) + s.attack_condition()
        mult = spellrules.cantrip_multiplier(c.level) if spell.get("cantrip_scaling") else 1
        kind = spell["kind"]
        self.say(f"{f.the_name} casts <magic>{spell['name']}</>.", "magic")

        def dmg_expr(base: str) -> str:
            n, sides, flat = dice.parse(base)
            n = n * mult
            if spell.get("upcast") and up:
                un, us, _ = dice.parse(spell["upcast"])
                if us == sides:
                    n += un * up
            return f"{n}d{sides}{signed_mod(flat)}" if n else str(flat)

        if kind == "attack":
            rays = int(spell.get("rays", 1)) + int(spell.get("upcast_rays", 0)) * up
            for _ in range(rays):
                if target is None or not target.active:
                    options = self.spell_targets(f, sid)
                    if not options:
                        break
                    target = self.rng.choice(options)
                opt = AttackOption("spell", spell["name"].lower(), "spell_melee" if spell["attack"] == "melee" else "spell_ranged",
                                   bonus, dmg_expr(spell["damage"]), spell["damage_type"], extra=spell)
                hit = self._attack(f, opt, target)
                if hit and spell.get("marks") and target.active:
                    target.marked = True
        elif kind == "auto":
            darts = int(spell.get("darts", 1)) + int(spell.get("upcast_darts", 0)) * up
            for _ in range(darts):
                if target is None or not target.active:
                    options = self.enemies_of(f)
                    if not options:
                        break
                    target = min(options, key=lambda x: x.hp)
                amount = dice.roll(spell["damage"], self.rng).total
                self._hit(f, target, amount, spell["damage_type"], crit=False, weapon="dart of force")
        elif kind == "save":
            for x in self._area(f, spell["target"], target, spell):
                if spell.get("humanoid_only") and x.kind != "humanoid":
                    continue
                self._save_damage(f, x, spell["save"], dc, dmg_expr(spell["damage"]), spell["damage_type"], spell.get("on_save", "half"))
                if spell.get("push") and x.active and x.rank == FRONT and x.hp > 0:
                    x.rank = BACK
        elif kind == "heal":
            targets = [x for x in self.side(f.side) if x.active or x.state == "down"] if spell["target"] == "all_allies" else [target]
            for x in targets:
                if x is None:
                    continue
                amount = dice.roll(dmg_expr(spell["heal"]), self.rng).total + (mod if spell.get("add_mod") else 0)
                if c.subclass == "life":
                    amount += 2 + max(1, level)
                self._heal(x, amount)
                if spell.get("mends_wound") and x.wounds:
                    w = max(x.wounds, key=lambda w: (w.severity, w.bleed))
                    w.severity -= 1
                    w.bleed = max(0, w.bleed - 1)
                    if w.severity <= 0:
                        x.wounds.remove(w)
                    self.say(f"The worst of {x.the_name}'s wounds closes a little.", "magic")
        elif kind == "buff":
            targets = [x for x in self.side(f.side) if x.active] if spell["target"] == "all_allies" else \
                ([f] if spell["target"] == "self" else [target])
            for x in targets:
                if x is None:
                    continue
                if x.char is not None and spellrules.lasts(self.t, sid):
                    # It outlives the fight: kept on them (the sheet counts its armour), the rest carried here.
                    spellrules.keep(x.char, self.t, sid)
                    x.buffs = [b for b in x.buffs if b.get("lasting") != sid]
                    part = spellrules.battle_part(self.t, sid)
                    if part:
                        x.buffs.append(part)
                else:
                    x.buffs.append({**spell["buff"], "rounds": int(spell.get("rounds", 10)), "source": sid})
            self.say(spell["text"], "magic")
        elif kind == "condition":
            for x in self._area(f, spell["target"], target, spell):
                if spell.get("humanoid_only") and x.kind != "humanoid":
                    self.say(f"{x.the_name} is not a person; the spell finds no grip.", "system")
                    continue
                if spell.get("no_undead") and x.kind == "undead":
                    continue
                if not self._save(x, spell["save"], dc):
                    x.conditions[spell["condition"]] = int(spell.get("rounds", 1)) if spell["condition"] != "prone" else -1
                    self.say(f"{x.the_name} is {spell['condition']}.", "good")
        elif kind == "sleep":
            pool = dice.roll(dmg_expr(spell["pool"]), self.rng).total
            for x in sorted(self.enemies_of(f), key=lambda x: x.hp):
                if x.kind == "undead" or x.hp > pool or "unconscious" in x.conditions:
                    continue
                pool -= x.hp
                x.conditions["unconscious"] = 10
                x.conditions["prone"] = -1
                self.say(f"{x.the_name} slumps to the ground, asleep.", "good")
        elif kind == "stabilize":
            if target is not None:
                target.stable = True
                self.say(f"{target.the_name} stops bleeding out.", "good")
        elif kind == "cure":
            if target is not None:
                for cond in spell.get("cures", []):
                    target.conditions.pop(cond, None)
                    if target.char:
                        target.char.conditions = [x for x in target.char.conditions if not x.startswith("exposed:")]
                self.say(f"{target.the_name} looks clearer.", "good")
        elif kind == "summon":
            f.buffs.append({"spirit_weapon": dmg_expr(spell["damage"]) + signed_mod(mod), "bonus": bonus,
                            "rounds": int(spell.get("rounds", 10))})
        elif kind == "aura":
            f.buffs.append({"aura": {"save": spell["save"], "dc": dc, "damage": dmg_expr(spell["damage"]),
                                     "damage_type": spell["damage_type"]}, "rounds": int(spell.get("rounds", 10))})
        elif kind == "move":
            f.rank = BACK if f.rank == FRONT else FRONT
            self.say(f"{f.the_name} is suddenly in the {f.rank} rank.", "magic")
            return  # a step through the mist, then act
        elif kind == "revive":
            if target is not None and target.state == "dead":
                diamond = next((i for i in c.inventory if i.def_id == "diamond"), None)
                if diamond is not None:
                    remove_item(c, diamond.uid, 1)
                    target.state = "fighting"
                    target.char.alive = True
                    target.hp = 1
                    target.conditions = {"prone": -1}
                    self.say(f"{target.the_name} draws a ragged breath.", "magic")
        self._after_action(f)

    def _area(self, f: Fighter, area: str, target: Fighter | None, spell: dict) -> list[Fighter]:
        enemies = self.enemies_of(f)
        if area == "enemy" and target is not None:
            return [target]
        if area == "enemy_front":
            front = [x for x in enemies if x.rank == FRONT]
            return front or enemies
        if area == "enemy_back":
            back = [x for x in enemies if x.rank == BACK]
            if spell.get("pierce"):
                return enemies
            return back or enemies
        if area == "all_enemies":
            return enemies
        return [target] if target is not None else []

    def _heal(self, f: Fighter, amount: int) -> None:
        if f.state == "dead":
            return
        f.hp = min(f.max_hp, f.hp + amount)
        if f.state == "down" and f.hp > 0:
            f.state = "fighting"
            f.conditions.pop("unconscious", None)
            f.stable = False
            self.say(f"{f.the_name} opens {f.possessive} eyes.", "good")
        self.say(f"{f.the_name} recovers {amount} hit points.", "good")

    # ------------------------------------------------------------------ bookkeeping
    def _after_action(self, f: Fighter) -> None:
        self._check_end()
        if self.outcome is None and self.current is f:
            self.end_turn()

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
