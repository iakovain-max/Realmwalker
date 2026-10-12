"""Combat encounters by the Dungeon Master's Guide (2024): the XP budget per character, how hard a band is for a party,
building a band for a budget, travel pace, and the attitudes that feed the Influence action (Expansion 1, D.3;
numbers in data/rules.json "encounters", "travel_pace" and "attitudes").

Realmwalker builds bands for the land and not for the party (DESIGN.md: some fights should be avoided): a region's
danger stands for a party level, the difficulty is rolled, and the budget is that level's per character, times the
party's size. What the player is told is measured against the real party."""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.rng import RNG

DIFFICULTIES = ("low", "moderate", "high")
ATTITUDES = ("hostile", "indifferent", "friendly")


def spec(tables) -> dict:
    return tables.rules["encounters"]


def per_character(tables, level: int) -> list[int]:
    """[Low, Moderate, High] XP for one character of this level."""
    rows = spec(tables)["budget"]
    return list(rows[max(1, min(len(rows), int(level))) - 1])


def budget(tables, levels: list[int], difficulty: str) -> int:
    i = DIFFICULTIES.index(difficulty)
    return sum(per_character(tables, lv)[i] for lv in levels)


def danger_level(tables, danger: int) -> int:
    rows = spec(tables)["danger_level"]
    return int(rows[max(0, min(len(rows) - 1, int(danger)))])


def roll_difficulty(tables, rng: RNG) -> str:
    odds = spec(tables)["odds"]
    return rng.weighted(list(DIFFICULTIES), [float(odds.get(d, 0)) for d in DIFFICULTIES])


def land_budget(tables, danger: int, party_size: int, difficulty: str) -> int:
    """What a band met in a land of this danger may be worth, for a party of this size."""
    return budget(tables, [danger_level(tables, danger)] * max(1, party_size), difficulty)


def xp_of(tables, def_ids: list[str]) -> int:
    return sum(int(tables.creatures[d]["xp"]) for d in def_ids)


def difficulty(tables, def_ids: list[str], levels: list[int]) -> str:
    """How hard a band is for this party (DMG: the most it spends of each budget): "trivial" (under half of Low),
    "low", "moderate", "high", "beyond" (over High) or "deadly" (over `deadly` times High)."""
    xp = xp_of(tables, def_ids)
    low, mod, high = (budget(tables, levels, d) for d in DIFFICULTIES)
    if xp * 2 < low:
        return "trivial"
    if xp <= low:
        return "low"
    if xp <= mod:
        return "moderate"
    if xp <= high:
        return "high"
    return "deadly" if xp > high * float(spec(tables)["deadly"]) else "beyond"


def ratio(tables, def_ids: list[str], levels: list[int]) -> float:
    """The band's XP over the party's High budget (above `deadly`: very likely to kill)."""
    return xp_of(tables, def_ids) / max(1, budget(tables, levels, "high"))


def counts_for(tables, members: list, rng: RNG, worth: int | None, party_size: int) -> list[int]:
    """How many of each member of a band (its [creature, dice] list): rolled and thinned for a small party; then,
    given a budget, trimmed of its rank and file until it fits (never the last of a kind), and grown while it fits up
    to `most_extra` times that."""
    counts = [max(1, dice.roll(str(n), rng).total) for _id, n in members]
    # A lone traveller meets fewer of the rank and file (Fair Chances, 2026-10): the band as it would come for a party
    # of this size, and the budget may only thin it further.
    scale = min(1.3, 0.45 + 0.2 * max(1, party_size))
    counts = [c if c <= 1 else max(1, int(round(c * scale))) for c in counts]
    if worth is None:
        return counts
    xp = [int(tables.creatures[d]["xp"]) for d, _n in members]
    # A band grows past its roll only by `most_extra` (1.0: never; the roll is the band the land sends).
    most = [max(c, int(c * float(spec(tables)["most_extra"]))) for c in counts]
    variable = [i for i, (_d, n) in enumerate(members) if str(n) != "1"]
    total = sum(x * c for x, c in zip(xp, counts))
    while total > worth:
        cut = [i for i in variable if counts[i] > 1]
        if not cut:
            break
        i = max(cut, key=lambda j: (counts[j], -xp[j]))
        counts[i] -= 1
        total -= xp[i]
    grown = True
    while grown:
        grown = False
        for i in sorted(variable, key=lambda j: xp[j]):
            if counts[i] < most[i] and total + xp[i] <= worth:
                counts[i] += 1
                total += xp[i]
                grown = True
                break
    return counts


# ---------------------------------------------------------------------------- attitudes
def start_attitude(tables, def_ids: list[str], rng: RNG) -> str:
    """A band's attitude when met, by its leader's alignment (DMG: Starting Attitude), weighted towards Hostile."""
    att = tables.rules["attitudes"]["start"]
    lead = max(def_ids, key=lambda d: float(tables.creatures[d].get("cr", 0)))
    align = str(tables.creatures[lead].get("alignment", "unaligned"))
    key = "evil" if "evil" in align else "good" if "good" in align else "unaligned" if align in ("unaligned", "") \
        else "neutral"
    odds = att.get(key, att["neutral"])
    return rng.weighted(list(odds), [float(v) for v in odds.values()])


def influence_mode(tables, attitude: str) -> str:
    """"advantage", "disadvantage" or "" for a check to influence someone of this attitude."""
    mode = tables.rules["attitudes"]["influence"].get(attitude, "none")
    return "" if mode == "none" else mode


def attitude_of_mood(tables, mood: str) -> str:
    return tables.rules["attitudes"]["moods"].get(mood, "indifferent")


def influence_dc(tables, def_ids: list[str]) -> int:
    """PHB 2024 Influence: 15 or the highest Intelligence among them, whichever is higher."""
    best = max((int(tables.creatures[d].get("abilities", {}).get("int", 10)) for d in def_ids), default=10)
    return max(int(tables.rules["attitudes"]["default_dc"]), best)


# ---------------------------------------------------------------------------- travel pace
def pace(tables, name: str) -> dict:
    paces = tables.rules["travel_pace"]["paces"]
    return paces.get(name, paces["normal"])


def max_pace(tables, land: str, family: str, road: bool) -> str:
    """The fastest pace the land allows (DMG Travel Terrain), one step faster on a good road."""
    m = tables.rules["travel_pace"]["max"]
    top = m.get(land) or m.get(family) or "normal"
    order = ["slow", "normal", "fast"]
    if road:
        top = order[min(2, order.index(top) + 1)]
    return top


def allowed(chosen: str, top: str) -> str:
    order = ["slow", "normal", "fast"]
    return order[min(order.index(chosen if chosen in order else "normal"), order.index(top))]
