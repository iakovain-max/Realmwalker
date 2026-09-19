"""Wounds: real injuries to specific body parts, separate from hit points (which are stamina and luck).

M3 creates wounds in combat; M4 adds bleeding into blood loss, pain, infection, treatment and
healing over time. A hit that lands has a chance to wound: more likely for big hits, criticals,
and when already worn down; less likely where armour covers the part that was struck.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from realmwalker.core.rng import RNG

SEVERITY = {1: "minor", 2: "serious", 3: "critical"}
PART_GROUP = {"head": "head", "torso": "torso", "left_arm": "arms", "right_arm": "arms", "left_leg": "legs", "right_leg": "legs"}
PART_LABEL = {"head": "head", "torso": "torso", "left_arm": "left arm", "right_arm": "right arm",
              "left_leg": "left leg", "right_leg": "right leg"}
KIND_BY_DAMAGE = {"slashing": "cut", "piercing": "puncture", "bludgeoning": "blunt", "fire": "burn", "cold": "frostbite",
                  "lightning": "burn", "acid": "burn", "necrotic": "cut", "radiant": "burn", "force": "blunt",
                  "thunder": "blunt", "poison": None, "psychic": None}
ARMOR_FACTOR = {"heavy": 0.35, "medium": 0.55, "light": 0.75, "helmet": 0.5, "natural": 0.7}


@dataclass
class Wound:
    part: str  # head, torso, left_arm, right_arm, left_leg, right_leg
    kind: str  # cut, puncture, blunt, fracture, burn, frostbite, bite
    severity: int  # 1 minor, 2 serious, 3 critical
    bleed: int = 0  # 0 none .. 3 heavy
    created: int = 0  # world minute
    bandaged: bool = False
    infected: bool = False
    note: str = ""  # e.g. the source: "wolf bite"
    # Healing over time (rules/health.py).
    healing: float = 0.0  # hours of healing towards the next step down in severity
    infection: float = 0.0  # 0 clean .. 100 fatal
    clock: float = 0.0  # hours since the body last fought the infection
    cleaned: bool = False
    stitched: bool = False
    splinted: bool = False
    internal: bool = False  # bleeding inside (critical body wounds)
    peak: int = 0  # the worst it has been

    def __post_init__(self) -> None:
        self.peak = max(self.peak, self.severity)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Wound:
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})

    @property
    def label(self) -> str:
        kind = {"puncture": "stab wound", "blunt": "bruising", "cut": "cut", "fracture": "broken bone", "bite": "bite",
                "burn": "burn", "frostbite": "frostbite"}.get(self.kind, self.kind)
        return f"{SEVERITY[self.severity]} {kind} ({PART_LABEL.get(self.part, self.part)})"


def roll_location(locations: list, rng: RNG) -> str:
    parts = [p for p, _ in locations]
    weights = [w for _, w in locations]
    return rng.weighted(parts, weights)


def wound_chance(damage: int, max_hp: int, hp_after: int, crit: bool, armor_factor: float) -> float:
    """Chance that a landed hit becomes a real wound."""
    if crit:
        return 1.0
    if damage <= 0:
        return 0.0
    share = damage / max(1, max_hp)
    worn_down = 1.0 - max(0, hp_after) / max(1, max_hp)
    chance = 0.10 + share * 1.2 + worn_down * 0.35
    return max(0.0, min(0.95, chance * armor_factor))


def severity_for(damage: int, max_hp: int, crit: bool, rng: RNG) -> int:
    share = damage / max(1, max_hp)
    severity = 1 if share < 0.35 else (2 if share < 0.7 else 3)
    if crit and rng.chance(0.5):
        severity = min(3, severity + 1)
    return severity


def make_wound(part: str, damage_type: str, severity: int, rng: RNG, *, bite: bool = False, now: int = 0,
               note: str = "") -> Wound | None:
    kind = "bite" if bite else KIND_BY_DAMAGE.get(damage_type, "blunt")
    if kind is None:
        return None
    if kind == "blunt" and severity >= 2 and part != "torso" and rng.chance(0.5):
        kind = "fracture"
    bleed = {"cut": severity, "puncture": severity, "bite": severity, "blunt": 0, "fracture": max(0, severity - 2),
             "burn": 0, "frostbite": 0}.get(kind, 0)
    internal = part == "torso" and kind in ("puncture", "blunt") and severity == 3 and rng.chance(0.5)
    if internal:
        bleed = max(bleed, 2)
    return Wound(part, kind, severity, bleed, now, note=note, internal=internal)


def worst(wounds: list[Wound]) -> Wound | None:
    return max(wounds, key=lambda w: (w.severity, w.bleed), default=None)
