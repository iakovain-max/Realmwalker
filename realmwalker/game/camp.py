"""Camping and living off the land: fire, tent, cooking, boiling water, foraging, hunting, fishing.

A camp exists while the party stays in one place (it breaks when they move). A fire warms, dries,
cooks and boils, but is seen from afar; a cold camp stays hidden. Numbers are in data/camping.json.
"""

from __future__ import annotations

from dataclasses import dataclass

from realmwalker.core import dice
from realmwalker.rules import body
from realmwalker.rules.character import Character, Sheet
from realmwalker.rules.inventory import WATER_RISK, add_item, container_capacity, remove_item

POTS = ("iron_pot", "mess_kit", "cooks_utensils")
FIRE_DC = {"plenty": 0, "some": 10, "little": 15, "none": 99}


@dataclass
class Camp:
    x: int
    y: int
    local_key: str | None = None
    lx: int = 0
    ly: int = 0
    since: int = 0
    fire: bool = False
    tent: bool = False


def camp_here(game) -> Camp | None:
    """The camp, if the party is still where it was made (otherwise it is gone)."""
    camp = game.camp
    p = game.player
    if camp is None:
        return None
    if (camp.x, camp.y, camp.local_key) != (p.x, p.y, p.local_key) or (p.local_key and (camp.lx, camp.ly) != (p.lx, p.ly)):
        game.camp = None
        return None
    return camp


def make_camp(game) -> Camp:
    camp = camp_here(game)
    if camp is None:
        p = game.player
        camp = Camp(p.x, p.y, p.local_key, p.lx, p.ly, game.world.time)
        game.camp = camp
    return camp


def break_camp(game) -> None:
    game.camp = None


def best(game, skill: str) -> tuple[Character, int]:
    able = [c for c in game.party if c.alive and c.hp > 0] or game.party
    c = max(able, key=lambda c: Sheet(c, game.tables).skill_bonus(skill))
    return c, Sheet(c, game.tables).skill_bonus(skill)


def check(game, skill: str, dc: int, bonus: int = 0, tag: str = "") -> tuple[bool, str]:
    who, b = best(game, skill)
    b += bonus
    rng = game.world.rng.child(f"camp/{tag}/{game.world.time}")
    roll = dice.d20(rng).natural
    name = game.tables.rules["skills"][skill]["name"]
    sign = "+" if b >= 0 else "-"
    return roll + b >= dc, f"<dice>{name} ({who.name.split()[0]}): {roll} {sign} {abs(b)} = {roll + b} vs DC {dc}</>"


def has(game, def_ids) -> tuple[Character, object] | tuple[None, None]:
    for c in game.party:
        for it in c.inventory:
            if it.def_id in def_ids:
                return c, it
    return None, None


def land(game) -> str:
    p = game.player
    return game.biome_key(p.x, p.y)


def indoors(game) -> bool:
    p = game.player
    lm = game.local
    return (lm is not None and lm.building_at(p.lx, p.ly) is not None) or game.world.settlement_at(p.x, p.y) is not None


# ---------------------------------------------------------------------------- fire and shelter
def light_fire(game) -> list[str]:
    camp = make_camp(game)
    if camp.fire:
        return ["The fire is already burning."]
    if game.world.settlement_at(game.player.x, game.player.y) is not None:
        camp.fire = True
        return ["You find a hearth to sit by."]
    owner, tinder = has(game, ("tinderbox",))
    if tinder is None:
        return ["You have nothing to strike a light with (a tinderbox)."]
    w = game.weather
    if w.kind in ("storm", "blizzard") and not camp.tent and not indoors(game):
        return ["In this weather no fire will catch in the open. A tent might shelter one."]
    wood = game.tables.camping["firewood"].get(land(game), "some")
    wet = 4 if (w.raining or w.snowing) else 0
    msgs = []
    if wood == "plenty":
        game.pass_time(15, "walk")
        msgs.append("You gather deadwood and get a fire going.")
    else:
        ok, roll = (False, "")
        if FIRE_DC[wood] < 99:
            ok, roll = check(game, "survival", FIRE_DC[wood] + wet, tag="wood")
            msgs.append(roll)
            game.pass_time(30, "walk")
        if ok:
            msgs.append("You scrape together enough fuel for a fire.")
        else:
            c, bundle = has(game, ("firewood",))
            if bundle is None:
                return msgs + ["There is not enough to burn here, and you carry no firewood."]
            remove_item(c, bundle.uid, 1)
            msgs.append("You burn a bundle of the firewood you carried.")
    if wet:
        msgs.append("The wet wood smokes and spits, but it burns.")
    camp.fire = True
    return msgs


def put_out_fire(game) -> list[str]:
    camp = camp_here(game)
    if camp is None or not camp.fire:
        return ["There is no fire."]
    camp.fire = False
    return ["You kick earth over the fire. Darkness, and quiet."]


def pitch_tent(game) -> list[str]:
    camp = make_camp(game)
    if camp.tent:
        return ["The tent is already up."]
    _, tent = has(game, ("tent",))
    if tent is None:
        return ["You have no tent."]
    camp.tent = True
    game.pass_time(20, "walk")
    return ["You pitch the tent. Out of the wind and the wet, at least."]


# ---------------------------------------------------------------------------- food and water
def cook(game) -> list[str]:
    camp = camp_here(game)
    if camp is None or not camp.fire:
        return ["You need a fire to cook."]
    recipes = game.tables.camping["cooking"]
    _, pot = has(game, POTS)
    done = []
    for c in game.party:
        for it in list(c.inventory):
            recipe = recipes.get(it.def_id)
            if recipe is None or (recipe.get("needs_pot") and pot is None):
                continue
            qty = it.qty
            remove_item(c, it.uid)
            made = add_item(c, game.tables.items, recipe["becomes"], qty, made_at=game.world.time)
            done.append(game.tables.items.name(made))
    if not done:
        missing = " (oats need a pot)" if pot is None and has(game, ("oats",))[1] is not None else ""
        return [f"There is nothing raw to cook{missing}."]
    game.pass_time(30, "rest")
    return [f"You cook over the fire: {', '.join(done)}."]


def boil_water(game) -> list[str]:
    camp = camp_here(game)
    if camp is None or not camp.fire:
        return ["You need a fire to boil water."]
    _, pot = has(game, POTS)
    if pot is None:
        return ["You need a pot or mess kit to boil water in."]
    pints = 0.0
    for c in game.party:
        for it in c.inventory:
            if container_capacity(game.tables.items, it) and it.fill > 0 and WATER_RISK.get(it.fill_kind, 2) > 0:
                pints += it.fill
                it.fill_kind = "boiled"
    if not pints:
        return ["All the water you carry is already safe."]
    game.pass_time(20, "rest")
    return [f"You boil {pints:g} pints of water. It tastes of smoke, and it won't make you sick."]


# ---------------------------------------------------------------------------- living off the land
def forage_while_resting(game, forager) -> list[str]:
    """A companion told to forage looks for food around the camp while the rest of you sleep."""
    if game.world.settlement_at(game.player.x, game.player.y) is not None:
        return []
    spec = game.tables.camping["forage"].get(land(game))
    if spec is None:
        return []
    dc = int(spec["dc"]) + (int(spec.get("winter_dc", 0)) if game.moment.season == "winter" else 0)
    rng = game.world.rng.child(f"camp-forage/{forager.name}/{game.world.time}")
    roll = dice.d20(rng).natural + game.sheet(forager).skill_bonus("survival")
    who = forager.name.split()[0]
    if roll < dc:
        return [f"{who} forages around the camp and finds nothing worth eating."]
    found = []
    for item_id, amount in spec["find"]:
        n = max(1, dice.roll(str(amount), rng).total)
        add_item(forager, game.tables.items, item_id, n, made_at=game.world.time)
        found.append(f"{game.tables.items.get(item_id)['name']}" + (f" ×{n}" if n > 1 else ""))
    return [f"{who} forages around the camp: {', '.join(found)}."]


def forage(game) -> list[str]:
    if game.world.settlement_at(game.player.x, game.player.y) is not None:
        return ["There is nothing to forage in a town: buy food instead."]
    spec = game.tables.camping["forage"].get(land(game))
    if spec is None:
        return ["There is nothing to forage here."]
    dc = int(spec["dc"]) + (int(spec.get("winter_dc", 0)) if game.moment.season == "winter" else 0)
    ok, roll = check(game, "survival", dc, tag="forage")
    game.pass_time(60, "walk")
    msgs = [roll] + _risk(game, 60)
    if not ok:
        return msgs + ["An hour of searching turns up nothing you'd care to eat."]
    rng = game.world.rng.child(f"forage/{game.world.time}")
    leader = game.leader
    found = []
    for item_id, amount in spec["find"]:
        n = max(1, dice.roll(str(amount), rng).total)
        it = add_item(leader, game.tables.items, item_id, n, made_at=game.world.time)
        found.append(game.tables.items.name(it) if n == 1 else f"{game.tables.items.get(item_id)['name']} ×{n}")
    for item_id, amount, chance in spec.get("extra", []):
        if rng.chance(float(chance)):
            n = max(1, dice.roll(str(amount), rng).total)
            add_item(leader, game.tables.items, item_id, n, made_at=game.world.time)
            found.append(f"{game.tables.items.get(item_id)['name']}" + (f" ×{n}" if n > 1 else ""))
    return msgs + [f"You find: {', '.join(found)}."]


def hunt(game) -> list[str]:
    if game.world.settlement_at(game.player.x, game.player.y) is not None:
        return ["No hunting in a town."]
    spec = game.tables.camping["hunt"].get(land(game))
    if spec is None:
        return ["There is no game here worth the name."]
    bonus = 0
    if any(game.tables.items.get(c.equipped_item("main_hand").def_id).get("range") for c in game.party
           if c.equipped_item("main_hand") is not None):
        bonus += 2
    if any(c.effects.get("hunting_tip", 0) > 0 for c in game.party):
        bonus += 5
    ok, roll = check(game, "survival", int(spec["dc"]), bonus, tag="hunt")
    game.pass_time(120, "walk")
    msgs = [roll] + _risk(game, 120)
    if not ok:
        return msgs + ["Two hours of stalking, and nothing to show for it but wet boots."]
    rng = game.world.rng.child(f"hunt/{game.world.time}")
    names = [g[0] for g in spec["game"]]
    weights = [float(g[1]) for g in spec["game"]]
    pick = spec["game"][names.index(rng.weighted(names, weights))]
    name, _, meat, hide = pick
    leader = game.leader
    n = max(1, dice.roll(str(meat), rng).total)
    add_item(leader, game.tables.items, "raw_meat", n, made_at=game.world.time)
    got = [f"raw meat ×{n}" if n > 1 else "raw meat"]
    if hide:
        add_item(leader, game.tables.items, hide, 1, made_at=game.world.time)
        got.append(game.tables.items.get(hide)["name"])
    for c in game.party:
        c.dirt = min(100.0, c.dirt + 10)
    if game.world.factions:
        from realmwalker.game import law

        law.poaching_check(game)
    return msgs + [f"You bring down {name}: {', '.join(got)}. Cook the meat before it turns."]


def fish(game) -> list[str]:
    from realmwalker.game.survival import water_here

    here = water_here(game)
    if here is None or here[0] == "clean":
        return ["There is no water here to fish in."]
    spec = game.tables.camping["fish"]
    _, tackle = has(game, ("fishing_tackle",))
    bonus = int(spec.get("tackle_bonus", 5)) if tackle is not None else -2
    ok, roll = check(game, "survival", int(spec["dc"]), bonus, tag="fish")
    game.pass_time(120, "rest")
    msgs = [roll] + _risk(game, 60)
    if not ok:
        return msgs + ["The fish are not biting." if tackle else "A line of twine and a bent pin catches nothing."]
    rng = game.world.rng.child(f"fish/{game.world.time}")
    item_id, amount = spec["catch"]
    n = max(1, dice.roll(str(amount), rng).total)
    add_item(game.leader, game.tables.items, item_id, n, made_at=game.world.time)
    return msgs + [f"You catch {n} fish in {here[1]}."]


def night_sound(game) -> str:
    """One thing heard in the night in the open: the land, the fire, or nothing much."""
    spec = game.tables.camping.get("night", {})
    if not spec:
        return ""
    pools = list(spec.get("any", []))
    camp = camp_here(game)
    if camp is not None and camp.fire:
        pools += spec.get("fire", [])
    pools += spec.get(game.biome_key(game.player.x, game.player.y), [])
    if not pools:
        return ""
    rng = game.world.rng.child(f"night/{game.world.time}/{game.player.x},{game.player.y}")
    return rng.choice(pools)


def _risk(game, minutes: int) -> list[str]:
    """Out in the wilds for a while: something may find you."""
    from realmwalker.game.encounters import roll_encounter

    if game.busy or game.in_local:
        return []
    enc = roll_encounter(game, minutes)
    if enc is None:
        return []
    game.encounter = enc
    return ["<danger>You are not alone out here.</>"]


def butcher(game, carcasses) -> tuple[list, list[str]]:
    """Cut up dead beasts after a fight. Returns (items, messages); items are new Item stacks."""
    from realmwalker.rules.items import Item

    if not carcasses:
        return [], []
    ok, roll = check(game, "survival", 10, tag="butcher")
    game.pass_time(30, "rest")
    got: dict[str, int] = {}
    for cr in carcasses:
        for item_id, qty in game.tables.creatures[cr.def_id].get("butcher", []):
            q = int(qty) if ok else max(0, int(qty) // 2)
            if q:
                got[item_id] = got.get(item_id, 0) + q
    items = [Item(0, item_id, q, made_at=game.world.time) for item_id, q in got.items()]
    for c in game.party:
        c.dirt = min(100.0, c.dirt + 15)
    names = ", ".join(f"{game.tables.items.get(i)['name']} ×{q}" for i, q in got.items()) or "nothing usable"
    return items, [roll, ("You butcher the carcasses: " if ok else "You hack at the carcasses and waste much: ") + names + "."]


def camp_summary(game) -> list[str]:
    """Lines describing the camp for the camp screen."""
    camp = camp_here(game)
    wood = game.tables.camping["firewood"].get(land(game), "some")
    out = []
    if game.world.settlement_at(game.player.x, game.player.y) is not None:
        out.append("You are in a settlement: there is shelter here (and in M5, inns).")
    if camp is None:
        out.append("You have not made camp. Doing anything here makes camp.")
    else:
        out.append("<good>A fire burns.</>" if camp.fire else "<dim>A cold camp: no fire, and hard to see.</>")
        if camp.tent:
            out.append("<good>The tent is up.</>")
    out.append(f"<dim>Firewood here:</> {wood}.")
    return out


def eat_meal(game, char: Character) -> list[str]:
    from realmwalker.game.survival import eat_item, food_choices

    camp = camp_here(game)
    choices = food_choices(game, char, desperate=char.hunger >= 80, fire=bool(camp and camp.fire))
    if not choices:
        return [f"{body.first(char)} has nothing fit to eat."]
    if char.hunger < 10:
        return [f"{body.first(char)} is not hungry."]
    msgs = []
    while choices and char.hunger >= 12 and len(msgs) < 4:
        msgs.append(eat_item(game, char, choices[0]))
        choices = food_choices(game, char, desperate=char.hunger >= 80, fire=bool(camp and camp.fire))
    game.pass_time(15, "rest")
    return msgs
