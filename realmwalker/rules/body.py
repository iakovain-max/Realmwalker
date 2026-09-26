"""The body over time: hunger, thirst, tiredness, dirt, body heat, wetness and exhaustion.

Pure rules on a Character. `Environment` says what the world is doing to the body (air, wind,
rain, shelter, fire, activity); `tick()` advances one character by some minutes and returns
what happened in words. Game-level code (game/survival.py) builds the environment, feeds and
waters the party, and turns deaths into the end of the game.

Scales: hunger, thirst, fatigue and dirt run 0 (fine) .. 100 (as bad as it gets).
body_heat runs -100 (freezing to death) .. +100 (heatstroke); 0 is comfortable.
wet runs 0 (dry) .. 100 (soaked through). Exhaustion is the 5e track, 0..6 (6 is death).
"""

from __future__ import annotations

from dataclasses import dataclass

from realmwalker.rules.character import Character, Sheet

# Per hour, before activity multipliers.
HUNGER_PER_HOUR = 1.33  # about 3 days from fed to starving
THIRST_PER_HOUR = 2.4  # about a day and a half to dehydrated
FATIGUE_PER_HOUR = 2.4  # about 40 waking hours to exhausted; walking wears you faster
SLEEP_RECOVERY_PER_HOUR = 13.0  # a full night takes fatigue from 100 to nothing
DIRT_PER_HOUR = 0.12
NUTRITION_POINTS = 32.0  # hunger removed by 1.0 nutrition (a day's rations)
PINT_POINTS = 15.0  # thirst removed by a pint of water

STAGES = {
    "hunger": [(80, "starving", "danger"), (55, "hungry", "warn"), (30, "peckish", "dim")],
    "thirst": [(85, "dehydrated", "danger"), (60, "parched", "warn"), (35, "thirsty", "dim")],
    "fatigue": [(90, "exhausted", "danger"), (70, "weary", "warn"), (45, "tired", "dim")],
    "dirt": [(85, "foul", "warn"), (60, "filthy", "warn"), (30, "grubby", "dim")],
    "wet": [(70, "soaked", "warn"), (35, "wet", "dim"), (10, "damp", "dim")],
}
COLD_STAGES = [(-80, "freezing", "danger"), (-60, "hypothermic", "danger"), (-40, "cold", "warn"), (-20, "chilled", "dim")]
HEAT_STAGES = [(90, "heatstroke", "danger"), (70, "heat-exhausted", "danger"), (50, "overheated", "warn"), (30, "hot", "dim")]
EXHAUSTION_EFFECTS = [
    "",
    "disadvantage on ability checks",
    "speed halved",
    "disadvantage on attacks and saving throws",
    "hit point maximum halved",
    "cannot walk",
    "death",
]
STRAIN_PER_LEVEL = 24.0  # strain hours per level of exhaustion (see strain rates below)
COMFORT_LOW = 14.0
COMFORT_HIGH = 32.0


@dataclass
class Environment:
    air: float  # degrees C
    wind: float  # km/h
    wet_per_hour: float  # how fast rain soaks an unprotected person
    activity: str = "rest"  # "walk", "rest", "sleep", "fight"
    sheltered: bool = False  # a roof and walls (town, building)
    fire: bool = False  # warming by a fire
    tent: bool = False
    bedding: float = 0.0  # warmth of blankets and bedrolls while sleeping
    wading: bool = False  # just waded a river


def stage(kind: str, value: float) -> tuple[str, str] | None:
    """(word, colour) for a need's current stage, or None when fine."""
    for limit, word, color in STAGES[kind]:
        if value >= limit:
            return word, color
    return None


def heat_stage(body_heat: float) -> tuple[str, str] | None:
    if body_heat < 0:
        for limit, word, color in COLD_STAGES:
            if body_heat <= limit:
                return word, color
        return None
    for limit, word, color in HEAT_STAGES:
        if body_heat >= limit:
            return word, color
    return None


def stage_index(kind: str, value: float) -> int:
    """0 fine .. 3 worst, for comparing before and after."""
    levels = STAGES[kind]
    for i, (limit, _, _) in enumerate(levels):
        if value >= limit:
            return len(levels) - i
    return 0


def heat_index(body_heat: float) -> int:
    """-4 freezing .. 0 fine .. 4 heatstroke."""
    if body_heat < 0:
        for i, (limit, _, _) in enumerate(COLD_STAGES):
            if body_heat <= limit:
                return -(len(COLD_STAGES) - i)
        return 0
    for i, (limit, _, _) in enumerate(HEAT_STAGES):
        if body_heat >= limit:
            return len(HEAT_STAGES) - i
    return 0


# ---------------------------------------------------------------------------- temperature
def insulation_factor(air: float) -> float:
    """Degrees of comfort per point of clothing warmth: a lot in the cold, little in the heat."""
    return max(0.4, min(1.6, 1.6 - (air - 15.0) * 0.12))


def felt_temperature(char: Character, sheet: Sheet, env: Environment) -> float:
    """What the body feels, all things considered (degrees C)."""
    air = env.air
    wind = 0.0 if env.sheltered or env.tent else env.wind
    if env.sheltered:
        air = max(air, 12.0) if air < 24 else min(air, 26.0)
    warmth = sheet.warmth() * (1.0 - 0.55 * char.wet / 100.0)
    felt = air + warmth * insulation_factor(env.air)
    felt -= wind * 0.25 * (1.0 - sheet.wind_protection()) * (1.0 if air < 20 else 0.3)
    felt -= char.wet / 100.0 * (6.0 if air < 20 else 2.0)  # wet skin loses heat fast
    felt += {"walk": 4.0, "fight": 6.0, "sleep": -3.0}.get(env.activity, 0.0)
    if env.activity == "sleep":
        felt += env.bedding
    if env.tent:
        felt += 4.0
    if env.fire:
        felt += 12.0
    return felt


def heat_change_per_hour(felt: float) -> float:
    if felt < COMFORT_LOW:
        return -(COMFORT_LOW - felt) * 0.75
    if felt > COMFORT_HIGH:
        return (felt - COMFORT_HIGH) * 1.0
    return 0.0


# ---------------------------------------------------------------------------- ticking
def tick(char: Character, sheet: Sheet, env: Environment, minutes: float) -> list[tuple[str, str]]:
    """Advance one character's body by some minutes. Returns (message, colour) pairs for changes worth
    telling the player. Does not eat or drink (game/survival.py does that) and never kills outright:
    it may lower hit points or raise exhaustion, and the caller checks for death."""
    if not char.alive or minutes <= 0:
        return []
    hours = minutes / 60.0
    before = snapshot(char)
    walking = env.activity in ("walk", "fight")
    sleeping = env.activity == "sleep"

    # Hunger and thirst.
    h_mult = 1.3 if walking else (0.6 if sleeping else 1.0)
    if char.body_heat <= -40:
        h_mult *= 1.3  # shivering burns food
    char.hunger = min(100.0, char.hunger + HUNGER_PER_HOUR * h_mult * hours)
    t_mult = 1.4 if walking else (0.5 if sleeping else 1.0)
    if env.air > 25 and not env.sheltered:
        t_mult *= 1.0 + (env.air - 25) * 0.08
    if char.body_heat >= 50:
        t_mult *= 2.0
    char.thirst = min(100.0, char.thirst + THIRST_PER_HOUR * t_mult * hours)

    # Tiredness: sleep restores, walking wears.
    if sleeping:
        char.fatigue = max(0.0, char.fatigue - SLEEP_RECOVERY_PER_HOUR * hours)
    else:
        f_mult = 1.5 if walking else 1.0
        char.fatigue = min(100.0, char.fatigue + FATIGUE_PER_HOUR * f_mult * hours)

    # Dirt.
    d_mult = 1.5 if walking else 1.0
    if any(w.bleed and not w.bandaged for w in char.wounds):
        d_mult += 1.0
    if not env.sheltered and env.wet_per_hour > 30:
        d_mult *= 0.5  # heavy rain rinses a little
    char.dirt = min(100.0, char.dirt + DIRT_PER_HOUR * d_mult * hours)

    # Getting wet and drying out.
    if env.wading:
        char.wet = max(char.wet, 70.0 * (1.0 - 0.5 * sheet.water_protection()))
    covered = env.sheltered or env.tent
    if env.wet_per_hour > 0 and not covered:
        char.wet = min(100.0, char.wet + env.wet_per_hour * (1.0 - sheet.water_protection()) * hours)
    elif char.wet > 0:
        dry = 40.0 if env.fire else (20.0 if covered else 5.0 + max(0.0, env.air) * 0.5 + env.wind * 0.15)
        char.wet = max(0.0, char.wet - dry * hours)

    # Body heat.
    felt = felt_temperature(char, sheet, env)
    change = heat_change_per_hour(felt)
    if change == 0.0:
        # Comfortable: drift back towards normal.
        step = 25.0 * hours
        char.body_heat = max(0.0, char.body_heat - step) if char.body_heat > 0 else min(0.0, char.body_heat + step)
    else:
        char.body_heat = max(-100.0, min(100.0, char.body_heat + change * hours))

    # Strain from the worst states builds up into exhaustion (5e levels).
    strain = 0.0
    if char.hunger >= 80:
        strain += 1.0
    if char.thirst >= 85:
        strain += 3.0
    if char.fatigue >= 90:
        strain += 2.0
    if char.body_heat <= -60:
        strain += 4.0
    if char.body_heat >= 70:
        strain += 6.0
    events: list[tuple[str, str]] = []
    if strain > 0:
        char.strain += strain * hours
        while char.strain >= STRAIN_PER_LEVEL and char.exhaustion < 6:
            char.strain -= STRAIN_PER_LEVEL
            char.exhaustion += 1
            events.append((f"{first(char)} is worn down further (exhaustion {char.exhaustion}: "
                           f"{EXHAUSTION_EFFECTS[char.exhaustion]}).", "danger"))
    else:
        char.strain = max(0.0, char.strain - 2.0 * hours)

    # The deadliest extremes hurt directly.
    damage = 0.0
    if char.body_heat <= -80:
        damage += 2.0 * hours
    if char.body_heat >= 90:
        damage += 2.0 * hours
    if damage > 0:
        char.hurt_carry += damage
        whole = int(char.hurt_carry)
        if whole:
            char.hurt_carry -= whole
            char.hp = max(0, char.hp - whole)
    clamp_hp(char)
    events += describe_changes(char, before)
    return events


def clamp_hp(char: Character) -> None:
    """Exhaustion 4+ halves the hit point maximum."""
    cap = hp_cap(char)
    if char.hp > cap:
        char.hp = cap


def hp_cap(char: Character) -> int:
    return max(1, char.max_hp // 2) if char.exhaustion >= 4 else char.max_hp


def first(char: Character) -> str:
    """What to call them in a sentence: their first name, but not an article ("The Wanderer")."""
    parts = char.name.split()
    if not parts:
        return char.name
    if parts[0].lower() in ("the", "a", "an", "old", "young") and len(parts) > 1:
        return char.name
    return parts[0]


def snapshot(char: Character) -> dict:
    return {"hunger": stage_index("hunger", char.hunger), "thirst": stage_index("thirst", char.thirst),
            "fatigue": stage_index("fatigue", char.fatigue), "dirt": stage_index("dirt", char.dirt),
            "wet": stage_index("wet", char.wet), "heat": heat_index(char.body_heat)}


GETTING_WORSE = {
    "hunger": {1: "{n}'s stomach growls.", 2: "{n} is hungry.", 3: "<danger>{n} is starving.</> Eat something, soon."},
    "thirst": {1: "{n} is thirsty.", 2: "<warn>{n}'s mouth is dry and sticky: parched.</>",
               3: "<danger>{n} is dehydrated: headache, dizziness, dark urine.</> Find water."},
    "fatigue": {1: "{n} is getting tired.", 2: "<warn>{n} is weary; every step is an effort.</>",
                3: "<danger>{n} is exhausted and needs sleep.</>"},
    "dirt": {2: "{n} is filthy. Wounds fester faster on a dirty body.", 3: "{n} stinks."},
    "wet": {2: "{n} is wet.", 3: "<warn>{n} is soaked to the skin.</>"},
}
HEAT_WORSE = {
    -1: "{n} feels the chill.", -2: "<warn>{n} is cold, and shivering.</>",
    -3: "<danger>{n} is hypothermic: clumsy, confused, shaking hard.</> Get warm.",
    -4: "<danger>{n} is freezing to death.</>",
    1: "{n} is hot.", 2: "<warn>{n} is overheated: drink, rest in the shade.</>",
    3: "<danger>{n} has heat exhaustion: nausea, cramps, a pounding head.</>",
    4: "<danger>{n} has heatstroke and is burning up.</>",
}
GETTING_BETTER = {
    "wet": "{n} has dried out.",
    "heat_cold": "{n} is warm again.",
    "heat_hot": "{n} has cooled down.",
}


def describe_changes(char: Character, before: dict) -> list[tuple[str, str]]:
    after = snapshot(char)
    n = first(char)
    out = []
    for key in ("hunger", "thirst", "fatigue", "dirt", "wet"):
        if after[key] > before[key]:
            text = GETTING_WORSE[key].get(after[key])
            if text:
                out.append((text.replace("{n}", n), "warn" if after[key] < 3 else "danger"))
        elif key == "wet" and after[key] == 0 and before[key] > 0:
            out.append((GETTING_BETTER["wet"].replace("{n}", n), "dim"))
    b, a = before["heat"], after["heat"]
    if abs(a) > abs(b) and (a * b >= 0):
        out.append((HEAT_WORSE[a].replace("{n}", n), "danger" if abs(a) >= 3 else "warn"))
    elif a == 0 and b != 0:
        out.append((GETTING_BETTER["heat_cold" if b < 0 else "heat_hot"].replace("{n}", n), "good"))
    return out


# ---------------------------------------------------------------------------- penalties
def condition_penalty(char: Character) -> int:
    """A penalty to checks, attacks and saves from hunger, thirst, tiredness, cold and heat (0 .. -6).
    Exhaustion is separate (5e disadvantage); pain and blood loss are added in rules/health.py."""
    p = 0
    p += {2: 1, 3: 2}.get(stage_index("hunger", char.hunger), 0)
    p += {2: 1, 3: 2}.get(stage_index("thirst", char.thirst), 0)
    p += {2: 1, 3: 2}.get(stage_index("fatigue", char.fatigue), 0)
    p += {-2: 1, -3: 2, -4: 3, 2: 1, 3: 2, 4: 3}.get(heat_index(char.body_heat), 0)
    return -min(6, p)


def travel_multiplier(char: Character) -> float | None:
    """Extra time taken on the road because of the body's state (None = cannot walk)."""
    if char.exhaustion >= 5:
        return None
    m = 2.0 if char.exhaustion >= 2 else 1.0
    if char.fatigue >= 90:
        m *= 1.25
    if char.hunger >= 80:
        m *= 1.15
    if heat_index(char.body_heat) in (-3, -4, 3, 4):
        m *= 1.25
    return m


# ---------------------------------------------------------------------------- eating and drinking
def eat(char: Character, nutrition: float) -> None:
    char.hunger = max(0.0, char.hunger - nutrition * NUTRITION_POINTS)


def drink(char: Character, pints: float, alcohol: float = 0.0) -> None:
    char.thirst = max(0.0, char.thirst - pints * PINT_POINTS)
    if alcohol:
        char.intoxication = min(100.0, char.intoxication + alcohol * 8.0)


def sleep_recovery(char: Character) -> list[str]:
    """After a full night's sleep: one level of exhaustion goes if the body was fed and watered (5e)."""
    notes = []
    if char.exhaustion > 0 and char.hunger < 55 and char.thirst < 60:
        char.exhaustion -= 1
        char.strain = 0.0
        notes.append(f"{first(char)} feels a little stronger (exhaustion {char.exhaustion}).")
    elif char.exhaustion > 0:
        notes.append(f"{first(char)} slept, but on an empty belly or a dry throat it did not restore much.")
    return notes


# ---------------------------------------------------------------------------- where each need is heading
TREND_KINDS = ("hunger", "thirst", "fatigue", "dirt", "wet", "body_heat")


def note_trend(char: Character, before: dict[str, float], minutes: float) -> None:
    """Remember how fast each need moved over the time just passed (points an hour), for the Health screen. Eating
    and drinking come after, so a meal does not hide how fast hunger is rising. Not saved: after loading, the
    trend returns with the first half hour that passes."""
    if minutes > 0:
        char._trend = {k: (getattr(char, k) - v) * 60.0 / minutes for k, v in before.items()}


def trend(char: Character) -> dict[str, float]:
    return getattr(char, "_trend", {})


def _hours(h: float) -> str:
    if h < 1:
        return "within the hour"
    n = round(h)
    return "in about an hour" if n == 1 else f"in about {n} hours"


def trend_words(kind: str, value: float, rate: float | None) -> str:
    """Where a need is heading, in words ("" when it is steady or unknown): "hungry in about 5 hours", "easing",
    "warming", "drying"."""
    if rate is None:
        return ""
    if kind == "body_heat":
        if value < -5:
            return "warming" if rate > 1.0 else "getting colder" if rate < -1.0 else ""
        if value > 5:
            return "cooling" if rate < -1.0 else "getting hotter" if rate > 1.0 else ""
        return "getting colder" if rate < -4.0 else "getting hotter" if rate > 4.0 else ""
    if kind == "wet":
        return "drying" if rate < -1.0 and value > 1 else "getting wetter" if rate > 1.0 else ""
    if rate < -0.5:
        return "easing"
    if rate <= 0.05:
        return ""
    worse = [(limit, word) for limit, word, _ in STAGES[kind] if limit > value]
    if not worse:
        return "worsening"
    limit, word = min(worse)
    hours = (limit - value) / rate
    return f"{word} {_hours(hours)}" if hours <= 36 else ""
