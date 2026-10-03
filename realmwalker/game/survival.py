"""Survival at the level of the game: what the weather and the place do to the party as time passes,
eating and drinking from the packs, water sources, and death from exposure, hunger or thirst.

GameState.pass_time() calls tick() for every chunk of time with what the party was doing.
"""

from __future__ import annotations

from realmwalker.rules import body
from realmwalker.rules.body import Environment
from realmwalker.rules.character import Character, Sheet
from realmwalker.rules.inventory import WATER_RISK, container_capacity, distinct_packs, remove_item
from realmwalker.world.weather import Weather, WeatherCache

AUTO_EAT_AT = 30.0  # hunger at which a meal is taken
AUTO_DRINK_AT = 30.0
EXPOSURE_CHANCE = {"stream": 0.03, "river": 0.05, "lake": 0.05, "marsh": 0.14}
WATER_NAMES = {"clean": "clean water", "boiled": "boiled water", "stream": "stream water", "river": "river water",
               "lake": "lake water", "marsh": "marsh water"}


def weather(game) -> Weather:
    cache = getattr(game, "_weather_cache", None)
    if cache is None:
        cache = game._weather_cache = WeatherCache()
    p = game.player
    return cache.get(game.world, game.tables, p.x, p.y, game.world.time)


def sheltered(game, activity: str) -> bool:
    """Under a roof: resting or sleeping in a settlement, or inside a building on a close-up map."""
    p = game.player
    lm = game.local
    if getattr(game, "confined", None):
        return True
    if lm is not None and (lm.kind == "dungeon" or lm.building_at(p.lx, p.ly) is not None):
        return True  # under a roof, or under the ground: the rain and the wind do not come down there
    return activity not in ("walk", "ride") and game.world.settlement_at(p.x, p.y) is not None


def bedding(game, char: Character) -> float:
    best = 0.0
    for it in char.inventory:
        best = max(best, float(game.tables.items.get(it.def_id).get("bedding", 0)))
    return best


def environment(game, char: Character, activity: str) -> Environment:
    from realmwalker.game.camp import camp_here

    w = weather(game)
    camp = camp_here(game)
    return Environment(
        air=w.temp, wind=w.wind, wet_per_hour=w.wet_per_hour, activity=activity,
        sheltered=sheltered(game, activity), fire=bool(camp and camp.fire and activity not in ("walk", "ride")),
        tent=bool(camp and camp.tent and activity not in ("walk", "ride")), bedding=bedding(game, char),
        shelter=bool(camp and camp.shelter and activity not in ("walk", "ride")),
        wading=bool(getattr(game, "_wading", False)),
    )


def tick(game, minutes: int, activity: str) -> None:
    """The party lives through some minutes."""
    if not getattr(game, "survival", True):
        return
    from realmwalker.rules import health

    from realmwalker.game import mounts

    ctx = health_context(game, activity)
    for char in list(game.party):
        if not char.alive:
            continue
        sheet = Sheet(char, game.tables)
        doing = mounts.activity_for(game, char, activity) if game.leader.animals else activity
        env = environment(game, char, doing)
        before = {k: getattr(char, k) for k in body.TREND_KINDS}
        for text, color in body.tick(char, sheet, env, minutes):
            game.say(text, color)
        rng = game.world.rng.child(f"health/{game.world.time}/{char.name}")
        for text, color in health.tick(char, game.tables, ctx, minutes, rng):
            game.say(text, color)
        body.note_trend(char, before, minutes)
        if (getattr(game, "auto_supplies", True) or getattr(game, "confined", None)) and activity != "fight":
            feed(game, char)
        check_death(game, char)
    game._wading = False


def health_context(game, activity: str):
    from realmwalker.rules.health import HealthContext

    p = game.player
    season = game.moment.season
    warm = season == "summer" or (season in ("spring", "autumn") and weather(game).temp > 16)
    return HealthContext(activity=activity, marsh=game.biome_key(p.x, p.y) == "marsh", warm_season=warm,
                         now=game.world.time)


def check_death(game, char: Character) -> None:
    if not char.alive:
        return
    cause = getattr(char, "death_cause", None)
    if cause is None and char.exhaustion >= 6:
        cause = death_cause(char, exhausted=True)
    elif cause is None and char.hp <= 0:
        cause = death_cause(char, exhausted=False)
    if cause is None:
        return
    char.alive = False
    char.hp = 0
    game.say(f"<danger>{char.name} is dead: {cause}.</>", "danger")
    if char is game.leader:
        game.over = {"cause": cause, "place": ""}
        game.travel = None
    else:
        game.party = [c for c in game.party if c.alive or c is game.party[0]]  # never the leader: they lead, dead or not
        game.waiting = [c for c in getattr(game, "waiting", []) if c.alive]
        from realmwalker.game import pack

        pack.sync(game)  # what they carried stays with the party
        from realmwalker.game.companions import died

        died(game, char)


def death_cause(char: Character, exhausted: bool) -> str:
    if char.body_heat <= -60:
        return "froze to death"
    if char.body_heat >= 70:
        return "died of heatstroke"
    if char.thirst >= 85:
        return "died of thirst"
    if char.hunger >= 80:
        return "starved to death"
    if char.blood < 25:
        return "bled to death"
    if any(w.infection >= 70 for w in char.wounds):
        return "died of blood poisoning from a festering wound"
    if any(d.get("phase") == "sick" for d in char.diseases):
        return "died of sickness"
    return "died of exhaustion" if exhausted else "died of their hurts"


# ---------------------------------------------------------------------------- food and water
def spoiled(game, item) -> bool:
    food = game.tables.items.get(item.def_id).get("food")
    if not food or not food.get("spoil_days"):
        return False
    return game.world.time - item.made_at > float(food["spoil_days"]) * 24 * 60


def food_choices(game, char: Character, *, desperate: bool = False, fire: bool = False) -> list:
    """Food this character would eat now, best first (whatever spoils soonest, safe food before risky)."""
    out = []
    packs = distinct_packs([char] + [m for m in getattr(game, "party", []) if m is not char])  # own pack first
    for it in (it for m in packs for it in m.inventory):
        d = game.tables.items.get(it.def_id)
        food = d.get("food")
        if not food:
            continue
        risky = spoiled(game, it) or food.get("raw")
        if food.get("needs_cooking") and not fire:
            continue
        if risky and not desperate:
            continue
        left = float(food.get("spoil_days", 999)) * 24 * 60 - (game.world.time - it.made_at)
        out.append((1 if risky else 0, left, it))
    out.sort(key=lambda t: (t[0], t[1]))
    return [it for _, _, it in out]


def eat_item(game, char: Character, item, units: int = 1) -> str:
    d = game.tables.items.get(item.def_id)
    food = d.get("food", {})
    risky_spoiled = spoiled(game, item)
    raw = bool(food.get("raw"))
    owner = next((m for m in getattr(game, "party", []) if any(it is item for it in m.inventory)), char)
    removed = remove_item(owner, item.uid, units)
    if removed is None:
        return ""
    body.eat(char, float(food.get("nutrition", 0.3)) * removed.qty)
    rng = game.world.rng.child(f"eat/{game.world.time}/{item.uid}")
    if risky_spoiled and rng.chance(0.35):
        char.conditions.append("exposed:food_poisoning")
    elif raw and rng.chance(0.2):
        char.conditions.append("exposed:food_poisoning")
    name = game.tables.items.name(removed)
    warn = " It had turned." if risky_spoiled else (" Raw." if raw else "")
    return f"{body.first(char)} eats {name}.{warn}"


def water_sources(game, char: Character) -> list:
    """Containers with water in them, cleanest first."""
    packs = distinct_packs([char] + [m for m in getattr(game, "party", []) if m is not char])
    skins = [it for m in packs for it in m.inventory if it.fill > 0 and container_capacity(game.tables.items, it)]
    return sorted(skins, key=lambda it: WATER_RISK.get(it.fill_kind, 2))


def water_here(game) -> tuple[str, str] | None:
    """(kind, where) of drinkable water at the player's position, if any: a well, a river, a lake, a pool, or failing
    those the rain (or snow melted at a fire)."""
    return _ground_water(game) or sky_water(game)


def _ground_water(game) -> tuple[str, str] | None:
    p = game.player
    w = game.world
    if w.settlement_at(p.x, p.y) is not None:
        return "clean", "the well"
    lm = game.local
    if lm is not None:
        # On foot you must stand by the water itself.
        nearby = local_terrain_near(game, lm)
        if "well" in nearby:
            return "clean", "the well"
        if not nearby & LOCAL_WATER:
            return None
    river = int(w.river[p.x, p.y])
    biome = game.biome_key(p.x, p.y)
    if river:
        r = w.river_at(p.x, p.y)
        name = f"the {r.name.removeprefix('the ')}" if r else ("the stream" if river == 1 else "the river")
        return ("stream" if river == 1 else "river"), name
    if biome == "marsh":
        return "marsh", "the marsh pools"
    for _, nx, ny in w.neighbours(p.x, p.y):
        if w.biome_id(nx, ny) == "lake":
            area = w.area_at(nx, ny)
            return "lake", (area.name if area else "the lake")
    if lm is not None:
        return "stream", "the pool"  # standing water on the close-up map, with no river on the big map
    return None


LOCAL_WATER = {"river", "ford", "shallow_water", "deep_water", "marsh_reeds"}
SKY_WATER = ("rainwater", "melted snow")


def sky_water(game) -> tuple[str, str] | None:
    """Water from the sky, out in the open: real rain can be caught in a cloak or a pot and wrung into a skin, and snow
    melted at a fire. (A traveller once died of thirst after two days soaked to the skin.)"""
    lm = game.local
    p = game.player
    if lm is not None and (lm.kind == "dungeon" or lm.building_at(p.lx, p.ly) is not None):
        return None
    sky = weather(game)
    if sky.raining and sky.precip >= 0.25:
        return "clean", "rainwater"
    camp = getattr(game, "camp", None)
    if sky.snowing and camp is not None and camp.fire:
        return "clean", "melted snow"
    return None


def from_where(where: str) -> str:
    """'from the stream', 'from the well', or 'rainwater' as it is (it is caught, not drawn)."""
    return where if where in SKY_WATER else f"from {where}"


def local_terrain_near(game, lm) -> set[str]:
    p = game.player
    remap = game.remap_for(lm)
    ids = game.tables.terrain.ids
    out = set()
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            x, y = p.lx + dx, p.ly + dy
            if lm.in_bounds(x, y):
                out.add(ids[int(remap[lm.terrain[x, y]])])
    return out


def drink_from(game, char: Character, kind: str, pints: float, where: str) -> str:
    body.drink(char, pints)
    if kind in EXPOSURE_CHANCE:
        rng = game.world.rng.child(f"drink/{game.world.time}/{char.name}")
        if rng.chance(EXPOSURE_CHANCE[kind]):
            char.conditions.append("exposed:marsh_fever" if kind == "marsh" else "exposed:dysentery")
    return f"{body.first(char)} drinks {from_where(where)}."


def feed(game, char: Character) -> None:
    """Eat and drink from the pack when hungry or thirsty (the 'eat and drink automatically' setting)."""
    if getattr(game, "confined", None):
        from realmwalker.game.law import prison_rations

        prison_rations(char)
        return
    camp = getattr(game, "camp", None)
    fire = bool(camp and camp.fire)
    if char.hunger >= AUTO_EAT_AT:
        eaten = []
        desperate = char.hunger >= 80
        for _ in range(6):
            if char.hunger < 12:
                break
            choices = food_choices(game, char, desperate=desperate, fire=fire)
            if not choices:
                break
            text = eat_item(game, char, choices[0])
            if text:
                eaten.append(text)
        for text in eaten[:2]:
            game.say(text, "dim")
        if not eaten and char.hunger >= 55 and not getattr(game, "_warned_food", False):
            game.say(f"<warn>{body.first(char)} has nothing fit to eat.</> Forage, hunt or buy food.", "warn")
            game._warned_food = True
        elif eaten:
            game._warned_food = False
    if char.thirst >= AUTO_DRINK_AT:
        here = water_here(game)
        if here is not None and here[0] == "clean":
            pints = max(1.0, round(char.thirst / body.PINT_POINTS))
            game.say(drink_from(game, char, "clean", pints, here[1]), "dim")
            return
        drank = 0.0
        for skin in water_sources(game, char):
            if char.thirst < 8:
                break
            risky = WATER_RISK.get(skin.fill_kind, 2) > 0
            if risky and here is not None:
                break  # drink from the source instead of a risky skin
            want = min(skin.fill, max(1.0, round(char.thirst / body.PINT_POINTS)))
            skin.fill = round(skin.fill - want, 2)
            body.drink(char, want)
            drank += want
            if risky:
                drink_from(game, char, skin.fill_kind, 0, "")
            if skin.fill <= 0:
                skin.fill, skin.fill_kind = 0.0, ""
        if drank:
            left = sum(it.fill for it in water_sources(game, char))
            tail = f" ({left:g} pints left)" if left else " <warn>The waterskins are empty.</>"
            game.say(f"{body.first(char)} drinks.{tail}", "dim")
        elif here is not None and char.thirst >= AUTO_DRINK_AT:
            pints = max(1.0, round(char.thirst / body.PINT_POINTS))
            game.say(drink_from(game, char, here[0], pints, here[1]), "dim")
        elif char.thirst >= 60 and not getattr(game, "_warned_water", False):
            drinks = [it for it in char.inventory if game.tables.items.get(it.def_id).get("drink")]
            if drinks:
                it = drinks[0]
                d = game.tables.items.get(it.def_id)["drink"]
                remove_item(char, it.uid, 1)
                body.drink(char, float(d.get("water", 0.5)) * 2, float(d.get("alcohol", 0)))
                game.say(f"{body.first(char)} drinks {game.tables.items.get(it.def_id)['name']}.", "dim")
            else:
                game.say(f"<warn>{body.first(char)} has no water.</> Find a river, a lake or a well (w fills skins).",
                         "warn")
                game._warned_water = True
    if char.thirst < 35:
        game._warned_water = False


def fill_skins(game) -> list[str]:
    """Fill every waterskin from the water here. Returns messages."""
    from realmwalker.rules.inventory import fill_containers

    here = water_here(game)
    if here is None:
        return ["There is no water here. Rivers, lakes and wells are marked on the map."]
    kind, where = here
    out = []
    total = 0.0
    for c in game.party:
        total += fill_containers(c, game.tables.items, kind)
        if c.thirst >= 10:
            out.append(drink_from(game, c, kind, max(1.0, round(c.thirst / body.PINT_POINTS)), where))
    if total:
        risk = "" if kind == "clean" else " <warn>It may not be safe to drink unboiled.</>"
        what = f"with {where}" if where in SKY_WATER else f"from {where}"
        out.insert(0, f"You fill the waterskins {what} ({total:g} pints).{risk}")
    elif not out:
        out.append("The waterskins are already full.")
    game.pass_time(5 if total else 1)
    return out


def top_up(game) -> str:
    """Eating and drinking automatically (the setting) also means filling the skins on the way: at a town's well
    whenever they are not full, and from a stream, a river, a lake or the rain when they are all but dry. Otherwise w
    does it, by choice. Before, a traveller could walk past a dozen streams with an empty skin and die of thirst a day later."""
    if not getattr(game, "auto_supplies", True) or game.over is not None:
        return ""
    here = water_here(game)
    if here is None or here[0] == "marsh":
        return ""
    kind, where = here
    items = game.tables.items
    skins = [it for m in distinct_packs(game.party) for it in m.inventory if container_capacity(items, it)]
    room = sum(container_capacity(items, it) - it.fill for it in skins)
    from_town = kind == "clean" and where not in SKY_WATER
    if room < 1.0 or (not from_town and sum(it.fill for it in skins) >= 1.0):
        return ""
    from realmwalker.rules.inventory import fill_containers

    added = sum(fill_containers(m, items, kind) for m in distinct_packs(game.party))
    if not added:
        return ""
    risk = "" if kind == "clean" else " <warn>Unboiled, it may make you ill.</>"
    return f"You fill the waterskins {'with' if where in SKY_WATER else 'at'} {where} ({added:g} pints).{risk}"


def wash(game) -> list[str]:
    here = water_here(game)
    if here is None:
        return ["There is nowhere to wash here."]
    w = weather(game)
    for c in game.party:
        c.dirt = max(0.0, c.dirt - 70.0)
        if here[1] != "the well" and not sheltered(game, "rest"):
            c.wet = max(c.wet, 40.0)
    game.pass_time(20)
    cold = " The water is bitterly cold." if w.temp < 8 else ""
    return [f"You wash in {here[1]}.{cold}"]
