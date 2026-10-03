"""The journey (after v1): what a long walk will need, and what makes a sensible traveller stop.

The travel command (t) used to walk on through the night, through exhaustion, thirst and cold, until the
traveller dropped dead on the road: in forty measured lives, sixteen died that way within a week. Now a journey
stops for what a person would stop for, says why, and is taken up again with t and Enter (the world map opens on
the same destination). Before setting out, the plan says how many nights it means in the open and whether the food
and water will last.

`outlook(game, plan)` is the note shown before setting out; `worries(game)` is what is wrong right now, keyed so
that each thing stops the journey once (`GameState.heeded` remembers what the player has already been told, and
forgets it again when it stops being true, so being weary tomorrow stops you again).
"""

from __future__ import annotations

import math

from realmwalker.rules import body, health
from realmwalker.rules.body import first
from realmwalker.rules.inventory import container_capacity

NIGHT_LIGHT = 0.5  # below this it is night (the same line road trouble uses)
FOOD_PER_DAY = 1.0  # nutrition a walker needs in a day (a day's trail rations)
WATER_PER_DAY = 4.0  # pints a walker drinks in a day
COLD_NIGHT = 2.0  # a night colder than this, in the open, is dangerous (degrees C before dawn)


# ---------------------------------------------------------------------------- before setting out
def food_days(game) -> float:
    """Days of food the party carries, eaten cold (what needs cooking does not count)."""
    alive = [c for c in game.party if c.alive] or game.party
    total = 0.0
    for c in game.party:
        for it in c.inventory:
            food = game.tables.items.get(it.def_id).get("food")
            if food and not food.get("needs_cooking") and not food.get("raw"):
                total += float(food.get("nutrition", 0.3)) * it.qty
    return total / (FOOD_PER_DAY * len(alive))


def water_pints(game) -> float:
    return sum(it.fill for c in game.party for it in c.inventory
               if it.fill > 0 and container_capacity(game.tables.items, it))


def water_days(game) -> float:
    alive = [c for c in game.party if c.alive] or game.party
    return water_pints(game) / (WATER_PER_DAY * len(alive))


def water_on_the_way(game, path) -> int:
    """Places on the route where a traveller can drink and fill a skin: rivers, lakes, wells in towns."""
    w = game.world
    count = 0
    for x, y in path:
        if w.river[x, y] or w.settlement_at(x, y) is not None or \
                any(w.biome_id(nx, ny) == "lake" for _, nx, ny in w.neighbours(x, y)):
            count += 1
    return count


def daylight_left(game) -> float:
    """Hours until dark (0 if it is night already)."""
    lat = game.latitude
    cal = game.tables.calendar
    t = game.world.time
    for half in range(49):
        if cal.at(t + half * 30).light(lat) < NIGHT_LIGHT:
            return half / 2.0
    return 24.0


def walking_hours(game, plan) -> float:
    return plan.minutes * (game.pace() or 1.0) * game.weather.travel_factor() / 60.0


def nights(game, plan) -> int:
    """Nights spent in the open on the way, walking from first light to dark."""
    from realmwalker.game.state import WALKING_HOURS_PER_DAY

    hours = walking_hours(game, plan)
    left = daylight_left(game)
    if hours <= left:
        return 0
    return max(1, math.ceil((hours - left) / WALKING_HOURS_PER_DAY))


def night_cold(game) -> float:
    """How cold it will be here in the small hours of the coming night (the sky can be read)."""
    from realmwalker.world.weather import weather_at

    t = game.world.time
    m = game.tables.calendar.at(t)
    minutes_to_small_hours = ((24 + 4 - m.hour) % 24) * 60 - m.minute
    p = game.player
    return weather_at(game.world, game.tables, p.x, p.y, t + max(0, minutes_to_small_hours)).temp


def _days_words(days: float) -> str:
    if days < 0.75:
        return "less than a day"
    if days < 1.5:
        return "about a day"
    return f"about {int(round(days))} days"


def outlook(game, plan) -> list[str]:
    """What a sensible traveller thinks about before a long walk (marked-up lines; empty for a short one)."""
    from realmwalker.game.state import WALKING_HOURS_PER_DAY

    hours = walking_hours(game, plan)
    out: list[str] = []
    n = nights(game, plan)
    if n == 0:
        if hours >= 2:
            out.append("You should be there before dark.")
    elif daylight_left(game) <= 0:
        out.append(f"It is dark already. {'One night' if n == 1 else f'{n} nights'} in the open on the way, "
                   f"walking by day.")
    else:
        out.append(f"{'One night' if n == 1 else f'{n} nights'} in the open on the way, walking by day.")
    if n == 0:
        return out
    days = n + 1 if hours > WALKING_HOURS_PER_DAY * n else float(n) + 0.5
    food = food_days(game)
    if food + 0.25 < days:
        out.append(f"<danger>Food for {_days_words(food) if food >= 0.25 else 'not even a day'}</>, for a journey "
                   f"of {_days_words(days).removeprefix('about ')}. Buy some first, or live off the land (camp: r).")
    else:
        out.append(f"Food for {_days_words(food)}.")
    water = water_days(game)
    springs = water_on_the_way(game, plan.path)
    if water + 0.25 < days and springs == 0:
        out.append(f"<danger>Water for {_days_words(water) if water >= 0.25 else 'not even a day'}, and none on "
                   f"the way that you know of.</> Fill your skins first (w).")
    elif water + 0.25 < days:
        out.append(f"Water for {_days_words(water) if water >= 0.25 else 'not even a day'}; there is water on the "
                   f"way, and w fills a skin where you stand.")
    else:
        out.append(f"Water for {_days_words(water)}.")
    cold = night_cold(game)
    if cold < COLD_NIGHT:
        out.append(f"<warn>The nights are bitter here (about {cold:.0f}°C before dawn).</> Sleep by a fire, "
                   f"under canvas if you have it: a night in the open without one can kill.")
    return out


# ---------------------------------------------------------------------------- on the way
def _night_key(game) -> str | None:
    if game.light >= NIGHT_LIGHT:
        return None
    m = game.moment
    return f"night/{m.total_days if m.hour >= 12 else m.total_days - 1}"


def night_unheeded(game) -> bool:
    """Night has fallen on a journey and the traveller has not yet stopped for it."""
    key = _night_key(game)
    return key is not None and key not in getattr(game, "heeded", set())


def worries(game, nearly_there: bool = False) -> dict[str, str]:
    """Everything wrong right now that a traveller should stop for: key -> what to say.
    Nobody stops for the dark one step short of where they are going."""
    out: dict[str, str] = {}
    night = _night_key(game)
    if night is not None and not nearly_there:
        out[night] = "Night is coming on."
    food, water = food_days(game) > 0, water_pints(game) > 0
    for c in game.party:
        if not c.alive:
            continue
        n = first(c)
        tired = body.stage_index("fatigue", c.fatigue)
        if tired >= 2:
            out[f"tired/{c.name}/{tired}"] = (f"{n} is exhausted and needs sleep." if tired >= 3 else
                                              f"{n} is weary; every step is an effort.")
        if c.exhaustion:
            out[f"worn/{c.name}/{c.exhaustion}"] = (f"{n} is worn down (exhaustion {c.exhaustion}: "
                                                    f"{body.EXHAUSTION_EFFECTS[c.exhaustion]}).")
        hungry = body.stage_index("hunger", c.hunger)
        if hungry >= 2:
            out[f"hungry/{c.name}/{hungry}"] = (f"{n} is starving." if hungry >= 3 else
                                                f"{n} is hungry." if food else
                                                f"{n} is hungry, and there is nothing left to eat.")
        thirst = body.stage_index("thirst", c.thirst)
        if thirst >= 2:
            out[f"thirst/{c.name}/{thirst}"] = (f"{n} is dehydrated." if thirst >= 3 else
                                                f"{n} is parched." if water else
                                                f"{n} is parched, and the water is gone.")
        heat = body.heat_index(c.body_heat)
        if heat <= -2:
            out[f"cold/{c.name}/{heat}"] = (f"{n} is cold, and shivering." if heat == -2 else
                                            f"{n} is hypothermic and must get warm.")
        elif heat >= 2:
            out[f"hot/{c.name}/{heat}"] = (f"{n} is overheated." if heat == 2 else
                                           f"{n} is suffering in the heat.")
        if any(w.bleed and not w.bandaged for w in c.wounds):
            out[f"bleed/{c.name}"] = f"{n} is bleeding."
        blood = health.blood_stage(c)
        if blood is not None and blood[0] in ("faint", "collapsing", "bleeding to death"):
            out[f"blood/{c.name}/{blood[0]}"] = f"{n} has lost a lot of blood and is {blood[0]}."
        for d in c.diseases:
            if d.get("phase") == "sick" and d.get("id") in game.tables.diseases:
                name = game.tables.diseases[d["id"]].get("name", "sick")
                out[f"sick/{c.name}/{d['id']}"] = f"{n} is sick ({name})."
        if any(w.infection >= 30 for w in c.wounds):
            out[f"fester/{c.name}"] = f"A wound of {n}'s is festering."
    if not water and any(c.alive for c in game.party):
        out["dry"] = "The last of the water is gone."
    return out


def begin(game) -> None:
    """Setting out: whatever is already wrong has been seen and accepted (setting out at night, tired...)."""
    game.heeded = set(worries(game))


def reason_to_stop(game, nearly_there: bool = False) -> str | None:
    """After a step of a journey: something new that a sensible traveller would stop for, or None.
    What has been told once is not told again until it has stopped being true."""
    now = worries(game, nearly_there)
    heeded = getattr(game, "heeded", set()) & set(now)
    fresh = [key for key in now if key not in heeded]
    game.heeded = set(now)
    if not fresh:
        return None
    kinds = {key.split("/")[0] for key in fresh}
    text = " ".join(now[key] for key in fresh[:3])
    if kinds & {"night", "tired", "worn", "cold", "hot", "sick", "blood"}:
        roof = nearest_roof(game)
        if roof is not None:
            text += f" {roof}"
    if kinds & {"dry", "thirst"}:
        water = nearest_water(game)
        if water is not None:
            text += f" {water}"
    return text


def _where(game, x: int, y: int) -> str:
    from realmwalker.game.events import compass

    p = game.player
    miles = max(1, int(round(math.hypot(x - p.x, y - p.y) * 3)))
    return f"about {miles} mile{'s' if miles != 1 else ''} to the {compass(x - p.x, y - p.y)}"


def nearest_roof(game, reach: int = 2) -> str | None:
    """A place you know of, close by, with a roof for the night."""
    p = game.player
    known = [s for s in game.world.settlements if (s.id in p.known_settlements or p.explored[s.x, s.y])
             and max(abs(s.x - p.x), abs(s.y - p.y)) <= reach and (s.x, s.y) != (p.x, p.y)]
    if not known:
        return None
    s = min(known, key=lambda s: math.hypot(s.x - p.x, s.y - p.y))
    return f"{s.name} is {_where(game, s.x, s.y)}: a roof for the night."


def nearest_water(game, reach: int = 8) -> str | None:
    """The nearest water you have seen: a stream, a river, a lake, a town's well."""
    w = game.world
    p = game.player
    best = None
    for x in range(max(0, p.x - reach), min(w.width, p.x + reach + 1)):
        for y in range(max(0, p.y - reach), min(w.height, p.y + reach + 1)):
            if (x, y) == (p.x, p.y) or not p.explored[x, y]:
                continue
            what = None
            if w.settlement_at(x, y) is not None:
                what = f"the well at {w.settlement_at(x, y).name}"
            elif w.river[x, y]:
                r = w.river_at(x, y)
                what = f"the {r.name.removeprefix('the ')}" if r else "a stream"
            elif w.biome_id(x, y) == "lake":
                area = w.area_at(x, y)
                what = area.name if area else "a lake"
            if what is not None:
                d = math.hypot(x - p.x, y - p.y)
                if best is None or d < best[0]:
                    best = (d, x, y, what)
    if best is None:
        return None
    _, x, y, what = best
    return f"There is water {_where(game, x, y)}: {what}."


WAKING = {"cold": "The cold wakes you.", "hot": "The heat will not let you sleep.", "thirst": "Thirst wakes you.",
          "hungry": "Hunger wakes you.", "blood": "You wake light-headed and wet.", "bleed": "You wake wet.",
          "worn": "You wake worse than you lay down."}


def _severe(key: str) -> bool:
    kind, *rest = key.split("/")
    if kind in ("blood", "worn", "bleed"):
        return True
    if kind == "cold":
        return int(rest[-1]) <= -3
    if kind == "hot":
        return int(rest[-1]) >= 3
    if kind in ("thirst", "hungry"):
        return rest[-1] == "3"
    return False


def dangers(game) -> dict[str, str]:
    """What is bad enough to wake a sleeper: freezing, heatstroke, dying of thirst or hunger, bleeding."""
    return {k: v for k, v in worries(game, nearly_there=True).items() if _severe(k)}


def woken(game, before: set[str]) -> str | None:
    """Something bad enough to wake the sleepers that was not so when they lay down, in words, or None."""
    fresh = [(k, v) for k, v in dangers(game).items() if k not in before]
    if not fresh:
        return None
    return f"{WAKING[fresh[0][0].split('/')[0]]} {' '.join(v for _, v in fresh[:2])}"


def why_cannot_walk(game) -> str:
    """The real reason nobody can take another step (the old message always blamed the load)."""
    from realmwalker.rules.character import Sheet

    for c in game.party:
        if not c.alive:
            continue
        n = first(c)
        if Sheet(c, game.tables).encumbrance() >= 3:
            return f"{n} is carrying too much to walk. Drop something first (i: inventory)."
        if c.exhaustion >= 5:
            return (f"{n} is too far gone to take another step (exhaustion {c.exhaustion}). Sleep, with food and "
                    f"water in you (r: camp).")
    return "Nobody can take another step."
