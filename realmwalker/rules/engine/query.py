"""Every derived number of a fight, through one door (docs/EXPANSIONS.md §4.3.4).

Advantage and disadvantage on an attack (`attack_roll`) or a saving throw (`save_roll`), armour class, speed, what
damage does after immunity, resistance and vulnerability, the critical range. Each reads the base numbers (the
character sheet, or the creature's stat block) and then everything active on the creature: its conditions
(data/conditions.json), its traits and features (data/traits.json modifiers), the spells on it (buffs) and the
situation on the field. The battle, the battle screen's attack preview and the tactics all ask here, so they can never
disagree.

Advantage and disadvantage are lists of reasons; one of each cancels out (2024: a roll has at most one of either).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from realmwalker.rules import grid
from realmwalker.rules.engine import conditions as cond
from realmwalker.rules.engine import traits as tr

METAL = {"chain_shirt", "scale_mail", "breastplate", "half_plate", "ring_mail", "chain_mail", "splint_armor", "plate_armor"}
DEFAULT_RANGE = {"ranged": (80, 320), "spell_ranged": (60, 120)}


@dataclass
class Roll:
    """The reasons for advantage and for disadvantage on one d20 roll, in the order they were found."""
    adv: list[str] = field(default_factory=list)
    dis: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, mode: str, why: str) -> None:
        (self.adv if mode == "advantage" else self.dis).append(why)
        self.notes.append(why)

    @property
    def advantage(self) -> bool:
        return bool(self.adv)

    @property
    def disadvantage(self) -> bool:
        return bool(self.dis)

    @property
    def mode(self) -> str:
        """"advantage", "disadvantage" or "" once they have cancelled out."""
        if self.adv and not self.dis:
            return "advantage"
        if self.dis and not self.adv:
            return "disadvantage"
        return ""


@dataclass
class SaveRoll:
    roll: Roll
    bonus: int = 0
    dice: list[str] = field(default_factory=list)  # added dice (Bless)
    auto_fail: str = ""  # why it fails without a roll ("paralysed")


# ---------------------------------------------------------------------------- conditions
def conditions(f) -> frozenset[str]:
    """The conditions on a fighter with everything they bring with them."""
    return cond.expand(f.t, f.conditions)


def has(f, cid: str) -> bool:
    return cid in conditions(f)


def flag(f, key: str) -> bool:
    return cond.has_flag(f.t, f.conditions, key)


def incapacitated(f) -> bool:
    return cond.has_flag(f.t, f.conditions, "inactive")


def source(f, cid: str) -> int | None:
    """Who caused a condition (the one holding on, the one feared), if anyone did."""
    if cid == "grappled" and f.grappled_by is not None:
        return f.grappled_by
    return f.sources.get(cid)


def _cond_name(f, cid: str) -> str:
    return cond.name(f.t, cid).lower()


# ---------------------------------------------------------------------------- attacks
def attack_roll(b, att, target, opt, *, space=None) -> Roll:
    """Advantage and disadvantage on one attack, with the reasons (the dice log prints them)."""
    r = Roll()
    a_space = space or att.space
    g = max(grid.gap(a_space, target.space), abs(att.z - target.z) // grid.SQUARE_FT)  # (height counts: 5-5-5)
    if att.helped:
        r.add("advantage", "helped")
    if any(bf.get("distracted") == att.team for bf in target.buffs):
        r.add("advantage", "distracted")
    if target.marked:
        r.add("advantage", "marked")
    defs = cond.table(att.t)
    # The target's conditions: easy to hit when helpless, at a distance hard to hit when lying down.
    for cid in sorted(conditions(target)):
        d = defs[cid]
        if d.get("unless_seen"):
            continue  # being unseen is the sight rule below
        mode = d.get("attacked_near" if g <= 1 else "attacked_far") or d.get("attacked")
        if mode:
            r.add(mode, f"target {_cond_name(target, cid)}")
    if target.dodging and not incapacitated(target) and target.speed > 0 and b.can_see(target, att):
        r.add("disadvantage", "dodging")
    # The attacker's own state.
    for cid in sorted(conditions(att)):
        d = defs[cid]
        mode = d.get("attacks")
        if not mode or d.get("unless_seen"):
            continue
        src = source(att, cid)
        if d.get("not_against_source") and src is not None and src == target.id:
            continue
        if d.get("while_source_seen") and src is not None:
            who = next((x for x in b.fighters if x.id == src), None)
            if who is None or not who.active or not b.can_see(att, who):
                continue
        r.add(mode, _cond_name(att, cid))
    if not b.can_see(att, target):
        r.add("disadvantage", "cannot see them" if not target.hidden else "hidden")
    elif att.hidden or not b.can_see(target, att):
        r.add("advantage", "unseen")
    if not opt.is_melee:
        near = [e for e in b.enemies_of(att) if e.standing and not incapacitated(e) and grid.gap(a_space, e.space) <= 1
                and abs(e.z - att.z) < grid.SQUARE_FT]
        if near:
            r.add("disadvantage", "enemy at hand")
        normal = (opt.range or DEFAULT_RANGE.get(opt.kind, (60, 120)))[0]
        if normal and g * grid.SQUARE_FT > normal:
            r.add("disadvantage", "long range")
    if opt.kind == "ranged" and b.env.rain and "ammunition" in opt.properties:
        r.add("disadvantage", "rain")
    if opt.is_melee and b.flanker(att, target, space=a_space) is not None:
        r.add("advantage", "flanking")
    if att.char and "heavy" in opt.properties and att.size == "small":
        r.add("disadvantage", "too heavy")
    if att.char:
        armor = att.char.equipped_item("armor")
        if armor is not None and not att.sheet.proficient_with_armor(armor):
            r.add("disadvantage", "untrained in armour")
    if opt.extra.get("metal_advantage") and target.char:
        armor = target.char.equipped_item("armor")
        if armor is not None and armor.def_id in METAL:
            r.add("advantage", "metal armour")
    # Traits and features: the attacker's own, the target's, and those of enemies standing over the attacker.
    ctx = tr.Ctx(b, att, att=att, target=target, opt=opt, space=a_space)
    for mode, why in tr.modifiers(att, "attack", ctx):
        r.add(mode, why)
    ctx = tr.Ctx(b, target, att=att, target=target, opt=opt, space=a_space)
    for mode, why in tr.modifiers(target, "attacked", ctx):
        r.add(mode, why)
    for k in b.enemies_of(att):  # (only the first: a knight holding the line keeps the attacker busy enough)
        if k is target:
            continue
        ctx = tr.Ctx(b, k, att=att, target=target, opt=opt, space=a_space)
        found = next(iter(tr.modifiers(k, "enemy_attacks", ctx)), None)
        if found is not None:
            r.add(found[0], found[1].format(name=k.name))
            break
    return r


def crit_range(att) -> int:
    """The lowest natural roll that is a critical hit (20; 19 for a champion)."""
    return min([20] + [int(v) for v in tr.values(att, "crit_range")])


def crit_within(b, att, target) -> bool:
    """A hit from right beside a creature that cannot defend itself at all is a critical hit."""
    feet = b.feet(att, target)
    return any(feet <= int(v) for _, v in cond.flags(att.t, target.conditions, "crit_within"))


# ---------------------------------------------------------------------------- saving throws
def save_roll(b, f, ability: str, *, bonus: int = 0) -> SaveRoll:
    """Advantage, disadvantage and the bonus on a saving throw; or why it fails without a roll."""
    out = SaveRoll(Roll(), bonus=f.save_bonus(ability) + bonus, dice=list(f.buff_value("save_die")))
    for cid, abilities in cond.flags(f.t, f.conditions, "fails_saves"):
        if ability in abilities:
            out.auto_fail = _cond_name(f, cid)
            return out
    for cid, modes in cond.flags(f.t, f.conditions, "saves"):
        mode = modes.get(ability)
        if mode:
            out.roll.add(mode, _cond_name(f, cid))
    if ability == "dex" and f.dodging and not incapacitated(f) and f.speed > 0:
        out.roll.add("advantage", "dodging")  # the Dodge action: easier to get out of the way of fire
    ctx = tr.Ctx(b, f, ability=ability)
    for mode, why in tr.modifiers(f, "save", ctx):
        out.roll.add(mode, why)
    return out


# ---------------------------------------------------------------------------- armour and movement
def ac(f) -> int:
    if f.char:
        s = f.sheet
        value = s.armor_class()
        for base in f.buff_value("mage_armor"):
            if f.char.equipped_item("armor") is None:
                value = max(value, base + s.mod("dex"))
        return value + sum(f.buff_value("ac"))
    return int(f.cdef["ac"]) + sum(f.buff_value("ac"))


def speed(f) -> int:
    """Walking speed in feet this turn."""
    base = f.sheet.speed() if f.char else int(f.cdef["speed"])
    if flag(f, "speed_zero"):
        return 0
    base -= sum(f.buff_value("slow"))
    return max(0, base)


# ---------------------------------------------------------------------------- damage
def defences(f, dtype: str) -> str:
    """What a creature has against a type of damage: "immune", "resist", "vulnerable" or ""."""
    if f.creature and dtype in f.cdef.get("immune", []):
        return "immune"
    if f.creature and dtype in f.cdef.get("vulnerable", []):
        return "vulnerable"
    weak = tr.values(f, "vulnerable", flat=True)
    if dtype in weak or ("all" in weak and dtype):
        return "vulnerable"
    if resists(f, dtype):
        return "resist"
    return ""


def resists(f, dtype: str) -> bool:
    if flag(f, "resist_all"):
        return True
    if f.creature is not None and dtype in f.cdef.get("resist", []):
        return True
    if any(dtype in b.get("resist", []) for b in f.buffs):
        return True
    if dtype in tr.values(f, "resist", flat=True):
        return True
    if f.char is not None:
        from realmwalker.rules import magic

        return dtype in magic.resistances(f.char)
    return False


def damage_taken(f, amount: int, dtype: str) -> tuple[int, str]:
    """Damage after immunity, resistance and vulnerability, in the 2024 order (PHB chapter 1, Order of Application:
    adjustments first, then Resistance, halving and rounding down, then Vulnerability), and which of them applied."""
    kind = defences(f, dtype)
    if kind == "immune":
        return 0, kind
    if resists(f, dtype):
        amount //= 2
    if kind == "vulnerable":
        amount *= 2
    return amount, kind


def proficiency(f) -> int:
    """The proficiency bonus: a character's by level, a creature's by challenge (2 up to CR 4, then +1 every 4)."""
    if f.char is not None:
        return f.sheet.proficiency
    cr = float(f.cdef.get("cr", 0))
    return 2 + max(0, (max(1, int(-(-cr // 1))) - 1) // 4)


def unarmed_dc(f) -> int:
    """The saving throw against a grapple or a shove, and the DC to escape a grapple: 8 + Strength + proficiency."""
    return 8 + f.mod("str") + proficiency(f)


def d20_penalty(f) -> int:
    """What exhaustion takes off every d20 test (2024: 2 per level)."""
    return -2 * f.char.exhaustion if f.char is not None else 0


def concentration_dc(damage: int) -> int:
    """The Constitution save to keep concentrating after damage: 10 or half the damage, at most 30 (2024)."""
    return min(30, max(10, damage // 2))


def initiative_roll(f) -> Roll:
    """Advantage or disadvantage on initiative (2024): surprised or incapacitated, or invisible."""
    r = Roll()
    if f.surprised:
        r.add("disadvantage", "surprised")
    for cid, mode in cond.flags(f.t, f.conditions, "initiative"):
        r.add(mode, _cond_name(f, cid))
    return r


def condition_immune(f, cid: str) -> bool:
    """Whether a condition cannot take hold of this creature (its traits, or a condition that keeps it off)."""
    if cond.immune_to(f.t, f.conditions, cid):
        return True
    if f.creature is not None and cid in f.cdef.get("condition_immune", []):
        return True
    return cid in tr.values(f, "immune_condition", flat=True)


def attacks_per_action(f) -> int:
    """How many attacks the Attack action makes (Extra Attack: 2)."""
    return max([1] + [int(v) for v in tr.values(f, "attacks")])
