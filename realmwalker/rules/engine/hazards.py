"""The 2024 Rules Glossary's hazards and objects (numbers in data/rules.json "hazards" and "objects"):

    falling      1d6 bludgeoning for every 10 feet fallen, at most 20d6; whoever lands hurt is Prone
    burning      a burning creature takes 1d4 fire at the start of each of its turns until it puts the flames out
                 (an action: it throws itself down and rolls) or they are doused
    breath       how long a creature can hold its breath: 1 + Constitution modifier minutes, at least 30 seconds; after
                 that it gains a level of exhaustion at the end of each of its turns (and loses them when it breathes)
    objects      AC by what a thing is made of, hit points by its size (fragile or resilient); immune to poison and
                 psychic damage
"""

from __future__ import annotations

from realmwalker.rules.character import modifier


def falling(tables, feet: int) -> str:
    """The damage of a fall, as dice ("" if it is too short to hurt)."""
    h = tables.rules["hazards"]["falling"]
    n = min(int(h["max_dice"]), max(0, int(feet)) // int(h["feet_per_die"]))
    return f"{n}d{h['die']}" if n else ""


def burning_damage(tables) -> tuple[str, str]:
    h = tables.rules["hazards"]["burning"]
    return h["damage"], h["type"]


def breath_rounds(tables, con_score: int) -> int:
    """How many rounds (six seconds each) a creature can hold its breath."""
    h = tables.rules["hazards"]["breath"]
    seconds = max(int(h["least_seconds"]), (int(h["minutes"]) + modifier(con_score)) * 60)
    return seconds // 6


def object_ac(tables, substance: str) -> int:
    return int(tables.rules["objects"]["ac"].get(substance, 15))


def object_hp(tables, size: str, resilient: bool = False) -> str:
    """An object's hit points, as dice: fragile or resilient, by size (Huge and larger are taken in Large sections)."""
    row = tables.rules["objects"]["hp"].get(size) or tables.rules["objects"]["hp"]["large"]
    return row[1 if resilient else 0]


def object_immune(tables, dtype: str) -> bool:
    return dtype in tables.rules["objects"]["immune"]
