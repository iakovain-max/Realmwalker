"""5e dice: expressions like "2d6+3", d20 tests with advantage/disadvantage, and readable roll text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from realmwalker.core.rng import RNG

_DICE_RE = re.compile(r"^\s*(\d*)\s*d\s*(\d+)\s*(?:([+-])\s*(\d+))?\s*$", re.IGNORECASE)
_FLAT_RE = re.compile(r"^\s*([+-]?\d+)\s*$")


class DiceError(ValueError):
    pass


@dataclass
class DiceRoll:
    expression: str
    rolls: list[int]
    modifier: int
    total: int

    def __str__(self) -> str:
        dice = "+".join(str(r) for r in self.rolls) if self.rolls else "0"
        if self.modifier:
            sign = "+" if self.modifier > 0 else "-"
            return f"{self.expression}: {dice} {sign} {abs(self.modifier)} = {self.total}"
        return f"{self.expression}: {dice} = {self.total}"


def parse(expression: str) -> tuple[int, int, int]:
    """Return (count, sides, modifier) for "2d6+3"-style text, or a flat number."""
    m = _DICE_RE.match(expression)
    if m:
        count = int(m.group(1)) if m.group(1) else 1
        sides = int(m.group(2))
        mod = int(m.group(4)) if m.group(4) else 0
        if m.group(3) == "-":
            mod = -mod
        if count < 0 or count > 100 or sides < 1 or sides > 1000:
            raise DiceError(f"dice out of range: {expression!r}")
        return count, sides, mod
    m = _FLAT_RE.match(expression)
    if m:
        return 0, 1, int(m.group(1))
    raise DiceError(f"not a dice expression: {expression!r}")


def roll(expression: str, rng: RNG, *, double_dice: bool = False) -> DiceRoll:
    """Roll an expression. `double_dice` doubles the number of dice (critical hits)."""
    count, sides, mod = parse(expression)
    if double_dice:
        count *= 2
    rolls = [rng.randint(1, sides) for _ in range(count)]
    return DiceRoll(expression, rolls, mod, max(0, sum(rolls) + mod) if count else mod)


@dataclass
class D20Roll:
    natural: int
    rolls: list[int] = field(default_factory=list)
    advantage: bool = False
    disadvantage: bool = False

    @property
    def is_crit(self) -> bool:
        return self.natural == 20

    @property
    def is_fumble(self) -> bool:
        return self.natural == 1


def d20(rng: RNG, *, advantage: bool = False, disadvantage: bool = False) -> D20Roll:
    """Roll a d20. Advantage and disadvantage cancel each other out, as in 5e."""
    if advantage and disadvantage:
        advantage = disadvantage = False
    if advantage or disadvantage:
        a, b = rng.randint(1, 20), rng.randint(1, 20)
        natural = max(a, b) if advantage else min(a, b)
        return D20Roll(natural, [a, b], advantage, disadvantage)
    n = rng.randint(1, 20)
    return D20Roll(n, [n])


@dataclass
class CheckResult:
    label: str
    roll: D20Roll
    modifier: int
    dc: int

    @property
    def total(self) -> int:
        return self.roll.natural + self.modifier

    @property
    def success(self) -> bool:
        return self.total >= self.dc

    @property
    def margin(self) -> int:
        return self.total - self.dc

    def text(self) -> str:
        """e.g. 'Persuasion: 14 + 3 = 17 vs DC 15 — success.'"""
        sign = "+" if self.modifier >= 0 else "-"
        die = str(self.roll.natural)
        if self.roll.advantage or self.roll.disadvantage:
            tag = "adv" if self.roll.advantage else "dis"
            die = f"{die} ({tag} {self.roll.rolls[0]}/{self.roll.rolls[1]})"
        outcome = "success" if self.success else "failure"
        return f"{self.label}: {die} {sign} {abs(self.modifier)} = {self.total} vs DC {self.dc} — {outcome}."


def check(rng: RNG, label: str, modifier: int, dc: int, *, advantage: bool = False, disadvantage: bool = False) -> CheckResult:
    return CheckResult(label, d20(rng, advantage=advantage, disadvantage=disadvantage), modifier, dc)


def ability_modifier(score: int) -> int:
    return (score - 10) // 2
