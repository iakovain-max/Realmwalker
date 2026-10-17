"""Camping and living off the land: fire, tent, cooking, boiling water, foraging, hunting, fishing.

A camp exists while the party stays in one place (it breaks when they move). A fire warms, dries,
cooks and boils, but is seen from afar; a cold camp stays hidden. Numbers are in data/camping.json.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from realmwalker.core import dice
from realmwalker.rules import body
from realmwalker.rules.character import Character, Sheet
from realmwalker.rules.inventory import WATER_RISK, add_item, carried, container_capacity, distinct_packs, remove_item

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
    shelter: bool = False  # a rough shelter: a lean-to, a hollow in the lee of rocks (build_shelter)
    snares: str = ""  # the snares or trap set for the night (game/gear.py), by item id
    wards: dict = field(default_factory=dict)  # spells guarding it: ward -> world minute it ends (game/spellwork.py)


def chore(game, minutes: int, activity: str) -> None:
    """The time a piece of camp work takes: half with an Unseen Servant fetching, carrying and lighting (E.2)."""
    from realmwalker.game import waymagic

    if waymagic.anyone(game, "servant"):
        minutes = max(1, minutes // 2)
    game.pass_time(minutes, activity)


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


def tool_bonus(game, c: Character, skill: str, tool: str) -> tuple[int, bool]:
    """PHB 2024 tools: proficiency with the tool adds the proficiency bonus to a check made with it; proficiency in
    the skill as well gives advantage. (bonus, advantage)"""
    if not tool or tool not in c.tools:
        return 0, False
    return Sheet(c, game.tables).proficiency, skill in c.skills or skill in c.expertise


def check(game, skill: str, dc: int, bonus: int = 0, tag: str = "", mode: str = "", tool: str = "") -> tuple[bool, str]:
    if tool:  # whoever does it best with the tool in hand
        able = [c for c in game.party if c.alive and c.hp > 0] or game.party
        who = max(able, key=lambda c: (Sheet(c, game.tables).skill_bonus(skill) + tool_bonus(game, c, skill, tool)[0],
                                       tool_bonus(game, c, skill, tool)[1]))
        extra, adv = tool_bonus(game, who, skill, tool)
        b = Sheet(who, game.tables).skill_bonus(skill) + extra
        if adv and mode != "disadvantage":
            mode = "advantage"
        elif adv:
            mode = ""
    else:
        who, b = best(game, skill)
    b += bonus
    if who.attuned and game.tables.rules["skills"][skill]["ability"] in ("str", "con"):
        from realmwalker.rules import magic

        if "item_weak_body" in magic.traits(who):  # an artifact's flaw, out of a fight as in one
            mode = "disadvantage" if mode != "advantage" else ""
    from realmwalker.rules.engine import traits as tr
    from realmwalker.rules.engine.handlers import fighter

    if skill == "athletics" and "remarkable_athlete" in tr.of_char(who, game.tables):
        mode = "advantage" if mode != "disadvantage" else ""  # (the Champion's Remarkable Athlete)
    rng = game.world.rng.child(f"camp/{tag}/{game.world.time}")
    roll = dice.d20(rng, advantage=mode == "advantage", disadvantage=mode == "disadvantage").natural
    name = game.tables.rules["skills"][skill]["name"]
    sign = "+" if b >= 0 else "-"
    how = {"advantage": " (adv)", "disadvantage": " (dis)"}.get(mode, "")
    if roll < 10 and skill in who.skills and "reliable_talent" in tr.of_char(who, game.tables):
        roll = 10  # (a rogue's Reliable Talent)
    total, more = fighter.tactical_mind(who, game.tables, roll + b, dc, rng.child("tactical_mind"))
    return total >= dc, (f"<dice>{name}{how} ({who.name.split()[0]}): {roll} {sign} {abs(b)} = {roll + b} "
                         f"vs DC {dc}{'; ' + more if more else ''}</>")


def has(game, def_ids) -> tuple[Character, object] | tuple[None, None]:
    for c in game.party:
        for it in c.inventory:
            if it.def_id in def_ids:
                return c, it
    return None, None


def has_flag(game, flag: str) -> tuple[Character, object] | tuple[None, None]:
    """The first thing in the packs whose data has this flag set (a shovel digs, a crowbar pries...)."""
    for c in game.party:
        for it in c.inventory:
            if game.tables.items.get(it.def_id).get(flag):
                return c, it
    return None, None


def land(game) -> str:
    """The land the party is in, itself ('jungle', 'dunes'...): tables kept per land fall back to its family."""
    p = game.player
    return game.land_key(p.x, p.y)


def by_land(game, table: dict, default=None):
    """This land's entry in a table kept per land, else its family's ('jungle' falls back to 'forest')."""
    return game.tables.biomes.lookup(table, land(game), default)


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
    if w.kind in ("storm", "blizzard") and not camp.tent and not camp.shelter and not indoors(game):
        return ["In this weather no fire will catch in the open. A tent, or a rough shelter, might shelter one."]
    wood = by_land(game, game.tables.camping["firewood"], "some")
    wet = 4 if (w.raining or w.snowing) else 0
    msgs = []
    if wood == "plenty":
        chore(game, 15, "walk")
        msgs.append("You gather deadwood and get a fire going.")
    else:
        ok, roll = (False, "")
        if FIRE_DC[wood] < 99:
            ok, roll = check(game, "survival", FIRE_DC[wood] + wet, tag="wood")
            msgs.append(roll)
            chore(game, 30, "walk")
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


def build_shelter(game) -> list[str]:
    """A rough shelter for anyone without a tent: a lean-to of branches, turf and bracken, or a hollow scraped in the lee
    of rocks or a bank. Not as good as canvas, but it keeps off the wind and most of the rain, and a fire will burn in
    its lee even in a storm. An hour's work and a Survival check (harder where there is little to build with)."""
    camp = make_camp(game)
    if camp.tent or camp.shelter:
        return ["You are already under cover."]
    if indoors(game):
        return ["There is a roof here already."]
    dc = int(by_land(game, game.tables.camping.get("shelter", {}), 12))
    w = game.weather
    if w.kind in ("storm", "blizzard"):
        dc += 1
    # With a shovel you dig in: a trench under the lean-to, earth banked against the wind, a snow-hole in the drifts.
    _, spade = has_flag(game, "dig")
    ok, roll = check(game, "survival", dc, 5 if spade is not None else 0, tag="shelter")
    if not ok:
        chore(game, 15 if spade is not None else 30, "walk")
        return [roll, "The wind has it down as fast as you put it up. You could try again."]
    chore(game, 30 if spade is not None else 60, "walk")
    camp.shelter = True
    snowy = (game.tables.biomes.family(land(game)) in ("tundra", "high_mountains")
             or (game.weather.snowing and game.moment.season == "winter"))
    if spade is not None and snowy:
        return [roll, "You dig a snow-hole into the drift and roof it with your cloaks. Inside, out of the wind, it is "
                      "almost warm."]
    what = {"forest": "a lean-to of boughs and bracken", "pine_forest": "a lean-to of pine boughs",
            "hills": "a hollow behind a wall of turf and stones", "mountains": "a hollow in the lee of the rocks",
            "high_mountains": "a scrape in the snow behind a boulder", "tundra": "a low wall of snow and turf",
            "desert": "a hollow under a ledge, roofed with your cloak", "coast": "a lean-to of driftwood and wrack",
            "marsh": "a platform of reeds under a roof of reeds", "jungle": "a platform of poles under broad leaves",
            "dunes": "a hollow scooped in the lee of a dune, roofed with your cloak",
            "glacier": "a trench cut in the snow, roofed with blocks of it",
            "steppe": "a low wall of turf and your packs against the wind",
            "savanna": "a ring of thorn branches round a hollow under a thorn tree"}
    what = what.get(land(game)) or what.get(game.tables.biomes.family(land(game)), "a lean-to of whatever is to hand")
    return [roll, f"You build {what}. Out of the wind, and out of most of the wet."]


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
    chore(game, 20, "walk")
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
    chore(game, 30, "rest")
    return [f"You cook over the fire: {', '.join(done)}."]


def boil_water(game) -> list[str]:
    camp = camp_here(game)
    if camp is None or not camp.fire:
        return ["You need a fire to boil water."]
    _, pot = has(game, POTS)
    if pot is None:
        return ["You need a pot or mess kit to boil water in."]
    pints = 0.0
    for c in distinct_packs(game.party):
        for it in c.inventory:
            if container_capacity(game.tables.items, it) and it.fill > 0 and WATER_RISK.get(it.fill_kind, 2) > 0:
                pints += it.fill
                it.fill_kind = "boiled"
    if not pints:
        return ["All the water you carry is already safe."]
    chore(game, 20, "rest")
    return [f"You boil {pints:g} pints of water. It tastes of smoke, and it won't make you sick."]


# ---------------------------------------------------------------------------- living off the land
def forage_while_resting(game, forager) -> list[str]:
    """A companion told to forage looks for food around the camp while the rest of you sleep."""
    if game.world.settlement_at(game.player.x, game.player.y) is not None:
        return []
    spec = by_land(game, game.tables.camping["forage"])
    if spec is None:
        return []
    dc = int(spec["dc"]) + (int(spec.get("winter_dc", 0)) if game.moment.season == "winter" else 0)
    rng = game.world.rng.child(f"camp-forage/{forager.name}/{game.world.time}")
    roll = dice.d20(rng).natural + game.sheet(forager).skill_bonus("survival")
    who = forager.name.split()[0]
    if roll < dc:
        return [f"{who} forages around the camp and finds nothing worth eating."]
    found = []
    from realmwalker.game import stonework

    rich = 2 if stonework.enriched(game) else 1  # (Plant Growth's Enrichment: the land bears twice over)
    for item_id, amount in spec["find"]:
        n = max(1, dice.roll(str(amount), rng).total) * rich
        add_item(forager, game.tables.items, item_id, n, made_at=game.world.time)
        found.append(f"{game.tables.items.get(item_id)['name']}" + (f" ×{n}" if n > 1 else ""))
    return [f"{who} forages around the camp: {', '.join(found)}."]


def forage(game) -> list[str]:
    if game.world.settlement_at(game.player.x, game.player.y) is not None:
        return ["There is nothing to forage in a town: buy food instead."]
    spec = by_land(game, game.tables.camping["forage"])
    if spec is None:
        return ["There is nothing to forage here."]
    dc = int(spec["dc"]) + (int(spec.get("winter_dc", 0)) if game.moment.season == "winter" else 0)
    tip = 5 if any(c.effects.get("forage_tip", 0) > 0 for c in game.party) else 0  # (the plants showed the way)
    ok, roll = check(game, "survival", dc, tip, tag="forage")
    game.pass_time(60, "walk")
    msgs = [roll] + _risk(game, 60)
    if not ok:
        return msgs + ["An hour of searching turns up nothing you'd care to eat."]
    rng = game.world.rng.child(f"forage/{game.world.time}")
    leader = game.leader
    found = []
    from realmwalker.game import stonework

    rich = 2 if stonework.enriched(game) else 1  # (Plant Growth's Enrichment: the land bears twice over)
    for item_id, amount in spec["find"]:
        n = max(1, dice.roll(str(amount), rng).total) * rich
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
    spec = by_land(game, game.tables.camping["hunt"])
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


def party_has(game, item_id: str, qty: int) -> bool:
    return sum(it.qty for it in carried(game.party) if it.def_id == item_id) >= qty


def take_from_party(game, item_id: str, qty: int) -> None:
    left = qty
    for c in game.party:
        for it in list(c.inventory):
            if left <= 0:
                return
            if it.def_id == item_id:
                take = min(left, it.qty)
                remove_item(c, it.uid, take)
                left -= take


def crafts(game) -> list[tuple[str, str, bool, str]]:
    """(id, label, possible, why not) for everything the party could make here."""
    out = []
    camp = camp_here(game)
    fire = bool(camp and camp.fire)
    items = game.tables.items
    for cid, spec in game.tables.camping.get("crafts", {}).items():
        needs = ", ".join(f"{qty} × {items.get(item)['name']}" for item, qty in spec["needs"])
        label = f"{spec['name']} <dim>({needs}, {spec['minutes']} min)</>"
        why = ""
        if spec.get("fire") and not fire:
            why = "needs a fire"
        elif spec.get("tool") and has(game, (spec["tool"],))[1] is None:
            why = f"needs {items.get(spec['tool'])['name']}"
        else:
            missing = [item for item, qty in spec["needs"] if not party_has(game, item, int(qty))]
            if missing:
                why = "you don't have " + ", ".join(items.get(m)["name"] for m in missing)
        out.append((cid, label, not why, why))
    return out


def make(game, cid: str) -> list[str]:
    """Make something: the materials go, the time passes, and a check decides how well it goes."""
    spec = game.tables.camping.get("crafts", {}).get(cid)
    if spec is None:
        return ["You would not know where to start."]
    possible = {c[0]: (c[2], c[3]) for c in crafts(game)}
    ok, why = possible.get(cid, (False, "not here"))
    if not ok:
        return [f"You can't: {why}."]
    for item, qty in spec["needs"]:
        take_from_party(game, item, int(qty))
    prof = game.tables.items.get(spec["tool"]).get("tool", spec["tool"]) if spec.get("tool") else ""
    good, roll = check(game, spec["skill"], int(spec["dc"]), tag=cid, tool=prof)
    game.pass_time(int(spec["minutes"]), "rest")
    made = []
    who = game.leader
    for item, qty in spec["gives"]:
        n = int(qty) if good else int(qty) // 2  # (a failed brew of one makes nothing)
        if n <= 0:
            continue
        it = add_item(who, game.tables.items, item, n, made_at=game.world.time)
        if it is not None:
            made.append(f"{game.tables.items.get(item)['name']}" + (f" ×{n}" if n > 1 else ""))
    text = spec["text"] if good else "It takes longer than it should, and you spoil some of it."
    if not made:
        return [roll, "It goes wrong, and the materials are wasted."]
    return [roll, f"{text} <loot>You have {', '.join(made)}.</>"]


def night_sound(game) -> str:
    """One thing heard in the night in the open: the land, the fire, or nothing much."""
    spec = game.tables.camping.get("night", {})
    if not spec:
        return ""
    pools = list(spec.get("any", []))
    camp = camp_here(game)
    if camp is not None and camp.fire:
        pools += spec.get("fire", [])
    pools += by_land(game, spec, [])
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
    chore(game, 30, "rest")
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
    wood = by_land(game, game.tables.camping["firewood"], "some")
    out = []
    if game.world.settlement_at(game.player.x, game.player.y) is not None:
        out.append("You are in a settlement: there are roofs here, and an inn for the night.")
    if camp is None:
        out.append("You have not made camp. Doing anything here makes camp.")
    else:
        out.append("<good>A fire burns.</>" if camp.fire else "<dim>A cold camp: no fire, and hard to see.</>")
        if camp.tent:
            out.append("<good>The tent is up.</>")
        elif camp.shelter:
            out.append("<good>A rough shelter keeps off the wind and the worst of the wet.</>")
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
    stretch, cook = cooking(game)
    msgs = []
    while choices and char.hunger >= 12 and len(msgs) < 4:
        msgs.append(eat_item(game, char, choices[0], stretch=stretch))
        choices = food_choices(game, char, desperate=char.hunger >= 80, fire=bool(camp and camp.fire))
    from realmwalker.game import glamour

    if cook is None and glamour.warm_meal(game):  # (Prestidigitation: warm and tasty, for the hour)
        char.body_heat = max(char.body_heat, min(0.0, char.body_heat + 15))
        msgs.append(f"{body.first(char)}'s food is warm, and tastes better than it has any right to.")
    if cook is not None:
        char.body_heat = max(char.body_heat, min(0.0, char.body_heat + 15))
        if char is game.party[0] or len(game.party) == 1:
            msgs.append(f"{body.first(cook)} makes a hot stew of it, and it goes further than it would cold.")
    game.pass_time(15, "rest")
    return msgs


def cooking(game) -> tuple[float, Character | None]:
    """(how much further the food goes, the cook) when there is a fire and cook's utensils: a stew stretches what you
    have, the more so if the cook was trained to it."""
    camp = camp_here(game)
    if camp is None or not camp.fire:
        return 1.0, None
    _, kit = has(game, ("cooks_utensils",))
    if kit is None:
        return 1.0, None
    trained = next((c for c in game.party if c.alive and "cooks_utensils" in c.tools), None)
    return (1.3, trained) if trained is not None else (1.15, game.leader)
