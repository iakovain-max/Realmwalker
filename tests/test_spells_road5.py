"""Spells outside battle, part E.5 (Expansion 3): locks and stone (Knock, Arcane Lock, Mending, Mage Hand, Fabricate,
Stone Shape, Passwall, Move Earth, Creation, Leomund's Secret Chest) and weather and land (Control Water, Control
Weather, Plant Growth, Tsunami). Each is cast where it is used: underground, in a town, in the cells, at a camp, on the
road, before a fight and in a real one."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import camp, dungeon, economy, fight, gear, law, magic, services, spellwork, stonework
from realmwalker.game.encounters import PendingEncounter
from realmwalker.game.state import new_game
from realmwalker.rules import grid
from realmwalker.rules import spells as sp
from realmwalker.rules.combat import FOE, PARTY, Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import check, estimates
from realmwalker.rules.inventory import add_item
from realmwalker.rules.progression import award_xp
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world

E5 = sorted(("knock arcane_lock mending mage_hand fabricate creation stone_shape passwall move_earth "
             "leomunds_secret_chest control_water control_weather plant_growth tsunami").split())
COMPONENTS = ("gold_dust", "leomunds_chest", "chest_replica")


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Lastrites", 37, "small"), tables)


@pytest.fixture(autouse=True)
def casters_know_them(monkeypatch):
    """Every caster in these tests has the spells of E.5 ready (the bard, the druid and the sorcerer, whose spells many
    of these are, are not in the game yet)."""
    real = sp.known_spells

    def known(char, tables):
        out = real(char, tables)
        return list(dict.fromkeys(out + E5)) if sp.is_caster(char, tables) else out

    monkeypatch.setattr(sp, "known_spells", known)


class _D20:
    def __init__(self, n):
        self.natural = n


def hero(tables, cls="wizard", xp=355000, seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("sage")
    c = b.build()
    if xp:
        award_xp(c, xp, tables, RNG(seed), auto=True)
    add_item(c, tables.items, "component_pouch")
    for cid in COMPONENTS:
        add_item(c, tables.items, cid, 1 if cid != "gold_dust" else 3)
    return c


def game_with(world, tables, *party):
    game = new_game(copy.deepcopy(world), tables, party[0])
    for c in party[1:]:
        game.party.append(c)
    game.survival = False
    from realmwalker.game import pack

    pack.sync(game)
    return game


def cast(game, c, sid, target=None, slot=None):
    why = magic.road_problem(game, c, sid, target)
    assert why is None, f"{sid}: {why}"
    return magic.cast_on_road(game, c, sid, target, slot)


def subject(game, c, sid, kind=None, name=None):
    subs = magic.road_targets(game, c, sid)
    for s in subs:
        if (kind is None or s.kind == kind) and (name is None or name in s.name):
            return s
    raise AssertionError(f"{sid}: no subject {kind} {name} in {[s.name for s in subs]}")


def text(lines) -> str:
    return " ".join(lines)


def in_town(game, kind=None):
    town = next(s for s in game.world.settlements if kind is None or s.kind == kind)
    game.player.x, game.player.y = town.x, town.y
    game.enter_local()
    return town


def in_the_wild(game):
    game.leave_local() if game.local is not None else None
    for x in range(game.world.width):
        for y in range(game.world.height):
            if game.world.settlement_at(x, y) is None and game.world.danger[x, y] >= 1 \
                    and game.tables.biomes.family(game.land_key(x, y)) in ("forest", "plains", "hills"):
                game.player.x, game.player.y = x, y
                return
    raise AssertionError("no wild land")


def into_dungeon(game, site_index=0):
    site = game.world.sites[site_index]
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    dungeon.descend(game, 1)
    return game.local


def room_to_work(game, lm, walls: int):
    """Lay the ground east of the player: `walls` squares of stone wall and then floor (a wall to pass through)."""
    p = game.player
    for x, y in [(p.lx, p.ly)] + [(p.lx + i, p.ly) for i in range(1, walls + 2)]:
        assert 0 < x < lm.width - 1 and 0 < y < lm.height - 1
    for i in range(1, walls + 1):
        dungeon.set_terrain(lm, p.lx + i, p.ly, "wall_stone")
    dungeon.set_terrain(lm, p.lx + walls + 1, p.ly, "floor_stone")
    lm.actors.clear()


def walkable(tables, tid):
    return bool(tables.terrain[tables.terrain.index[tid]]["walk"])


def place_in_dungeon(game, lm, margin=6):
    """Put the player on a floor square well inside the level."""
    T = game.tables.terrain
    walk = T.walk[game.remap_for(lm)[lm.terrain]]
    for x in range(margin, lm.width - margin):
        for y in range(margin, lm.height - margin):
            if walk[x, y] and (x, y) not in lm.features:
                game.player.lx, game.player.ly = x, y
                return
    raise AssertionError("no floor")


# ---------------------------------------------------------------------------- the data
def test_the_fourteen_spells_are_in_and_the_start_up_check_knows_them(tables):
    assert all(sid in tables.spells for sid in E5)
    assert not [p for p in check.problems(tables) if any(sid in p for sid in E5)]
    for sid in E5:
        if sid != "plant_growth":
            assert sp.out_of_battle(tables.spells[sid]), f"{sid} is never cast in a fight"
        assert sp.road_use(tables, sid) is not None, f"{sid} has a use outside a fight"
    assert sp.road_use(tables, "plant_growth") == "plants" and not sp.out_of_battle(tables.spells["plant_growth"])
    for cid in COMPONENTS:
        assert tables.items.get(cid).get("how")


# ---------------------------------------------------------------------------- locks
def test_knock_opens_a_locked_door_and_wakes_the_level(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    lm = into_dungeon(game)
    place_in_dungeon(game, lm)
    p = game.player
    dungeon.set_terrain(lm, p.lx + 2, p.ly, "door_locked")
    lm.features[(p.lx + 2, p.ly)] = {"kind": "lock", "dc": 30}
    for a in lm.actors:
        a.alert = False
    slots = sp.slots_left(wiz, tables)[1]
    said = text(cast(game, wiz, "knock", subject(game, wiz, "knock", "door")))
    assert "knock" in said and dungeon.terrain_id(game, lm, p.lx + 2, p.ly) == "door_open"
    assert sp.slots_left(wiz, tables)[1] == slots - 1
    near = [a for a in lm.actors if max(abs(a.x - p.lx), abs(a.y - p.ly)) <= stonework.KNOCK_HEARD]
    assert all(a.alert for a in near), "the whole level heard it"


def test_knock_unlocks_a_chest_and_is_no_use_on_the_road(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    assert "underground" in magic.road_problem(game, wiz, "knock")
    lm = into_dungeon(game)
    place_in_dungeon(game, lm)
    p = game.player
    dungeon.set_terrain(lm, p.lx, p.ly + 1, "chest")
    lm.features[(p.lx, p.ly + 1)] = {"kind": "chest", "locked": 25, "treasure": 1}
    cast(game, wiz, "knock", subject(game, wiz, "knock", "chest"))
    assert lm.features[(p.lx, p.ly + 1)]["locked"] == 0


def test_arcane_lock_seals_a_door_that_opens_for_the_party_alone(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    lm = into_dungeon(game)
    place_in_dungeon(game, lm)
    p = game.player
    start = (p.lx, p.ly)
    dungeon.set_terrain(lm, p.lx + 1, p.ly, "door_open")
    dungeon.set_terrain(lm, p.lx + 2, p.ly, "floor_stone")
    lm.actors.clear()
    dust = sum(i.qty for i in wiz.inventory if i.def_id == "gold_dust")
    cast(game, wiz, "arcane_lock", subject(game, wiz, "arcane_lock", "door", "east"))
    assert dungeon.terrain_id(game, lm, p.lx + 1, p.ly) == "door_locked"
    assert sum(i.qty for i in wiz.inventory if i.def_id == "gold_dust") == dust - 1, "the gold dust is used up"
    walk = tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    assert not walk[p.lx + 1, p.ly], "nothing that lives there walks through it"
    assert dungeon.bump(game, start[0] + 1, start[1])
    assert (p.lx, p.ly) == (start[0] + 2, start[1]), "the party passes its own lock"
    assert dungeon.terrain_id(game, lm, start[0] + 1, start[1]) == "door_locked", "and it locks again behind"


def test_arcane_lock_on_the_room_keeps_the_inn_thieves_out(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    town = in_town(game)
    wiz.money = 10000

    class Thief:
        def chance(self, p):
            return True

        def randint(self, a, b):
            return 5

    npc = next(n for n in game.world.npcs.values() if n.settlement == town.id)
    robbed = services._night(game, npc, "squalid", Thief())
    assert wiz.money < 10000 and "lighter" in text(robbed)
    wiz.money = 10000
    cast(game, wiz, "arcane_lock")
    assert stonework.room_locked(game)
    assert "already" in magic.road_problem(game, wiz, "arcane_lock")
    services._night(game, npc, "squalid", Thief())
    assert wiz.money == 10000, "no thief gets into the locked room"
    game.leave_local()
    game.player.x, game.player.y = next((x, y) for x in range(game.world.width) for y in range(game.world.height)
                                        if game.world.settlement_at(x, y) is None)
    spellwork.tick(game)
    assert not stonework.room_locked(game) and "arcane_room" not in game.renown.flags, "only while you stay in town"


def test_knock_in_the_cells_is_ten_more_on_the_escape(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    realm = next(iter(game.world.factions))
    game.sentence = {"realm": realm, "settlement": -1, "steps": ["jail:10"], "notes": [], "escaped": False}
    monkeypatch.setattr(law.dice, "d20", lambda *a, **k: _D20(5))
    bonus = max(game.sheet().skill_bonus("sleight_of_hand"), game.sheet().skill_bonus("athletics"))
    dc = 5 + bonus + stonework.KNOCK_ESCAPE  # (beaten only with the knock)
    slots = sp.slots_left(wiz, tables)[1]
    ok, said = law.attempt_escape(game, dc)
    assert ok and "word of opening" in said
    assert sp.slots_left(wiz, tables)[1] == slots - 1, "a slot is spent"


# ---------------------------------------------------------------------------- mending and the hand
def test_mending_closes_a_break_but_not_the_wear_of_years(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    sword = add_item(wiz, tables.items, "longsword")
    sword.condition = 30
    cast(game, wiz, "mending")
    assert sword.condition == 30 + stonework.MEND_STEP
    cast(game, wiz, "mending")
    assert sword.condition == stonework.MEND_CAP
    for it in wiz.inventory:
        if tables.items.category(it) in ("weapon", "armor", "shield", "helmet", "clothing"):
            it.condition = max(it.condition, stonework.MEND_CAP)
    assert "nothing" in magic.road_problem(game, wiz, "mending")


def test_mage_hand_steals_with_advantage_and_a_caught_hand_is_no_theft(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    town = in_town(game)
    merchant = next((n for n in game.world.npcs.values() if n.settlement == town.id
                     and economy.shop_spec(game, n) is not None), None)
    if merchant is None:
        pytest.skip("no merchant in the test town")
    shop = economy.shop_state(game, merchant)
    item_id = next(iter(shop["stock"]))
    shop["stock"][item_id] = 5
    cast(game, wiz, "mage_hand")
    assert stonework.hand_ready(game)
    seen = []
    real = law.dice.d20

    def d20(rng, *a, **k):
        seen.append(k.get("advantage"))
        return _D20(1)

    monkeypatch.setattr(law.dice, "d20", d20)
    ok, said = law.steal_from_shop(game, merchant, item_id)
    assert seen[0] is True, "the hand steals with Advantage"
    assert not ok and "Witchcraft" in said and "grabs your wrist" not in said
    assert not [r for r in game.renown.crimes if r.get("crime") == "theft"], "no theft was done"
    assert not stonework.hand_ready(game), "the hand is spent"
    monkeypatch.setattr(law.dice, "d20", real)


# ---------------------------------------------------------------------------- making
def test_fabricate_makes_three_batches_without_a_check_or_tools(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    add_item(wiz, tables.items, "firewood", 5)
    monkeypatch.setattr(camp, "check", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no check")))
    s = subject(game, wiz, "fabricate", "craft", "torches")
    assert s.data["batches"] == 3
    torches = sum(i.qty for i in wiz.inventory if i.def_id == "torch")
    cast(game, wiz, "fabricate", s)
    assert sum(i.qty for i in wiz.inventory if i.def_id == "torch") == torches + 9
    assert sum(i.qty for i in wiz.inventory if i.def_id == "firewood") == 2
    crafts = [cid for cid, _, _ in stonework.fabricable(game)]
    assert "arrows_carving" not in crafts, "a woodcarver's work needs someone trained with the tools"
    wiz.tools.append("woodcarvers_tools")
    assert "arrows_carving" in [cid for cid, _, _ in stonework.fabricable(game)]


def test_creation_makes_a_ladder_that_fades_and_nobody_buys(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    s = subject(game, wiz, "creation", "thing", "ladder")
    made = magic.road_targets(game, wiz, "creation")
    assert all(tables.items.get(x.ref).get("material") not in ("iron", "steel", "gold", "silver") for x in made), \
        "no metal"
    assert not {"leomunds_chest", "chest_replica"} & {x.ref for x in made}, "no spell's costly component"
    cast(game, wiz, "creation", s)
    ladder = next(i for i in wiz.inventory if i.def_id == "ladder")
    assert stonework.conjured(ladder)
    town = game.world.settlements[0]
    merchant = next((n for n in game.world.npcs.values() if economy.shop_spec(game, n) is not None
                     and "gear" in economy.shop_spec(game, n)["buys"]), None)
    if merchant is not None:
        price, why = economy.sell_price(game, merchant, ladder)
        assert price is None and "magic" in why
    game.world.time += 23 * 60
    spellwork.tick(game)
    assert any(i.def_id == "ladder" for i in wiz.inventory)
    game.world.time += 2 * 60
    spellwork.tick(game)
    assert not any(i.uid == ladder.uid for i in wiz.inventory), "gone at its time"
    assert town is not None


# ---------------------------------------------------------------------------- stone
def test_stone_shape_opens_a_way_through_the_wall_for_good(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    lm = into_dungeon(game)
    place_in_dungeon(game, lm)
    room_to_work(game, lm, 1)
    p = game.player
    s = subject(game, wiz, "stone_shape", "wall", "east")
    cast(game, wiz, "stone_shape", s)
    assert walkable(tables, dungeon.terrain_id(game, lm, p.lx + 1, p.ly))
    game.world.time += 600
    dungeon.on_step(game, p.lx, p.ly)
    assert walkable(tables, dungeon.terrain_id(game, lm, p.lx + 1, p.ly)), "for good"


def test_passwall_opens_twenty_feet_for_an_hour_and_puts_you_out_when_it_closes(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    lm = into_dungeon(game)
    place_in_dungeon(game, lm)
    room_to_work(game, lm, 4)
    p = game.player
    start = (p.lx, p.ly)
    assert not any("east" in s.name for s in magic.road_targets(game, wiz, "stone_shape")), "too thick to shape"
    cast(game, wiz, "passwall", subject(game, wiz, "passwall", "wall", "east"))
    assert all(walkable(tables, dungeon.terrain_id(game, lm, start[0] + i, start[1])) for i in range(1, 5))
    from realmwalker.game.encounters import LocalActor

    lm.actors.append(LocalActor(99, "wolves", start[0] + 3, start[1], [spawn(tables, "wolf", RNG(2, "w"), 1)]))
    p.lx = start[0] + 2  # (in the passage when the hour runs out, a wolf behind)
    game.world.time += 61
    dungeon.on_step(game, p.lx, p.ly)
    assert (p.lx, p.ly) == start, "put out where it began"
    wolf = lm.actors[-1]
    assert walkable(tables, dungeon.terrain_id(game, lm, wolf.x, wolf.y)) and (wolf.x, wolf.y) != start, \
        "the creature in it is put out too"
    assert all(dungeon.terrain_id(game, lm, start[0] + i, start[1]) == "wall_stone" for i in range(1, 5))


# ---------------------------------------------------------------------------- the camp and the chest
def test_move_earth_digs_in_the_camp_and_the_night_is_seen_coming(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    camp.make_camp(game)
    cast(game, wiz, "move_earth")
    assert spellwork.warded(game, "earthworks")
    enc = PendingEncounter("test", [spawn(tables, "wolf", RNG(4, "night"), 1)], "Wolves.", False, "", asleep=True)
    enc, notes = spellwork.night_visitors(game, enc)
    assert enc is not None and not enc.asleep and enc.spotted_first and "bank" in text(notes)


def test_the_secret_chest_hides_the_treasure_from_robbers_and_comes_back(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    wiz.money = 5000
    add_item(wiz, tables.items, "gem_1000", 2)
    add_item(wiz, tables.items, "battleaxe")
    add_item(wiz, tables.items, "diamond", 1)  # (a spell's costly component stays at hand)
    weight = game.sheet(wiz).carried_weight()
    cast(game, wiz, "leomunds_secret_chest", subject(game, wiz, "leomunds_secret_chest", "load", "all of it"))
    held = {d["def_id"] for d in stonework.chest_things(game)}
    assert {"gem_1000", "battleaxe", "leomunds_chest"} <= held and wiz.money == 0
    assert not any(i.def_id in ("gem_1000", "battleaxe", "leomunds_chest") for i in wiz.inventory), "out of the pack"
    assert any(i.def_id == "diamond" for i in wiz.inventory) and "diamond" not in held
    assert game.sheet(wiz).carried_weight() < weight - 25, "the chest and what is in it weigh nothing here"
    assert magic.road_problem(game, wiz, "leomunds_secret_chest") is not None, "the chest is away"
    assert "Ethereal" in spellwork.problem(game, wiz, "leomunds_secret_chest", None)
    replica = next(i for i in wiz.inventory if i.def_id == "chest_replica")
    assert gear.use_name(game, replica) == "Call back the secret chest"
    said = text(gear.use_item(game, wiz, replica))
    assert "out of the grey" in said and wiz.money == 5000
    assert sum(i.qty for i in wiz.inventory if i.def_id == "gem_1000") == 2
    assert any(i.def_id == "battleaxe" for i in wiz.inventory) and any(i.def_id == "leomunds_chest" for i in wiz.inventory)
    assert "secret_chest" not in game.renown.flags
    assert "Nothing answers" in text(gear.use_item(game, wiz, replica))


def test_the_secret_chest_may_be_lost_after_sixty_days(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    add_item(wiz, tables.items, "gem_1000", 1)
    cast(game, wiz, "leomunds_secret_chest", subject(game, wiz, "leomunds_secret_chest", "load", "treasure"))
    game.world.time += 59 * stonework.DAY
    spellwork.tick(game)
    assert any(d["def_id"] == "gem_1000" for d in stonework.chest_things(game))
    monkeypatch.setattr(type(game.world.rng.child("x")), "chance", lambda self, p: True)
    game.world.time += 3 * stonework.DAY
    spellwork.tick(game)
    assert not stonework.chest_things(game) and "secret_chest" not in game.renown.flags
    assert not any(i.def_id == "gem_1000" for i in wiz.inventory)


# ---------------------------------------------------------------------------- weather and land
def test_control_water_parts_the_next_river(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    w = game.world
    spot = None
    for x in range(1, w.width - 1):
        for y in range(1, w.height - 1):
            if w.river[x, y] and not w.road[x, y] and game.biome_key(x, y) not in ("ocean", "lake") \
                    and game.biome_def(x, y)["passable"] and game.biome_def(x - 1, y)["passable"] \
                    and not w.river[x - 1, y] and w.settlement_at(x - 1, y) is None:
                spot = (x, y)
                break
        if spot:
            break
    assert spot, "a river in the test world"
    game.player.x, game.player.y = spot[0] - 1, spot[1]
    wading = game.step_minutes(spot[0] - 1, spot[1], *spot)
    cast(game, wiz, "control_water")
    assert game.magic_crossing(*spot) == "parted"
    assert game.step_minutes(spot[0] - 1, spot[1], *spot) < wading, "no ford to wade"


def test_control_weather_clears_a_storm_for_eight_hours_under_the_open_sky(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    cast(game, wiz, "control_weather", subject(game, wiz, "control_weather", "weather", "Clear"))
    assert game.weather.kind in ("clear", "heat") and game.weather.precip == 0
    game.world.time += 7 * 60
    game._weather_cache = None
    assert game.weather.precip == 0
    game.world.time += 2 * 60
    spellwork.tick(game)
    assert "weather" not in game.renown.flags
    lm = into_dungeon(game)
    assert lm is not None and "open sky" in magic.road_problem(game, wiz, "control_weather")


def test_control_weather_brings_snow_in_the_cold_and_warms_the_air(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    import dataclasses

    from realmwalker.world.weather import Weather

    cold = Weather("clear", -6.0, 10.0, 0.0, 0.1, 1.0)
    game.renown.flags["weather"] = {"x": game.player.x, "y": game.player.y, "until": game.world.time + 60, "how": "rain"}
    assert stonework.held_weather(game, cold).kind == "snow"
    game.renown.flags["weather"]["how"] = "warm"
    snow = dataclasses.replace(cold, kind="snow", precip=0.6)
    assert stonework.held_weather(game, snow).kind == "rain" and stonework.held_weather(game, snow).temp == 4.0
    game.player.x += stonework.WEATHER_TILES + 1
    assert stonework.held_weather(game, snow) is snow, "five miles round, no further"


def test_plant_growth_doubles_the_forage_for_a_year_and_the_village_remembers(world, tables, monkeypatch):
    druid = hero(tables)
    game = game_with(world, tables, druid)
    in_the_wild(game)
    monkeypatch.setattr(camp.dice, "d20", lambda *a, **k: _D20(20))
    t0 = game.world.time

    def foraged():
        before = sum(i.qty for i in druid.inventory)
        game.world.time = t0
        camp.forage_while_resting(game, druid)
        return sum(i.qty for i in druid.inventory) - before

    plain = foraged()
    assert plain > 0
    cast(game, druid, "plant_growth")
    assert stonework.enriched(game)
    assert foraged() == plain * 2
    assert "rich already" in magic.road_problem(game, druid, "plant_growth")
    game.world.time = t0 + 366 * stonework.DAY
    spellwork.tick(game)
    assert not stonework.enriched(game)
    village = next((s for s in game.world.settlements if s.kind in ("hamlet", "village")), None)
    if village is not None:
        game.player.x, game.player.y = village.x, village.y
        cast(game, druid, "plant_growth")
        assert any(village.name in d for d in druid.deeds)


def test_plant_growth_overgrows_the_ground_round_the_foes_and_spares_friends(tables):
    druid = hero(tables)
    friend = hero(tables, "fighter", seed=3)
    rng = RNG(1, "foes")
    foes = [spawn(tables, "bandit", rng, i + 1) for i in range(2)]
    b = Battle(tables, [druid, friend], foes, Env(), RNG(1, "b"), spots={0: (2, 5), 1: (3, 5), 2: (12, 5), 3: (13, 6)})
    b.start("Test fight.")
    me = b.side(PARTY)[0]
    foe = b.side(FOE)[0]
    b.order = [me.id] + [x for x in b.order if x != me.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    assert estimates.spell_value(b, me, "plant_growth", point=(foe.x, foe.y)).total() > 0, "the Auto sees its worth"
    assert b.do_cast(me, "plant_growth", point=(foe.x, foe.y))
    z = next(z for z in b.zones if z.kind == "overgrowth")
    assert (foe.x, foe.y) in z.cells and (me.x, me.y) not in z.cells and (me.x + 1, me.y) not in z.cells
    assert b.field.zone_thick[foe.x, foe.y]
    assert grid.step_feet(b.field, [(foe.x - 1, foe.y)]) == 20, "four feet for every foot"
    assert grid.step_feet(b.field, [(me.x, me.y + 1)]) == 5, "the friends' ground is clear"


# ---------------------------------------------------------------------------- the wave
def test_tsunami_falls_on_a_band_seen_first_and_the_fight_begins(world, tables, monkeypatch):
    druid = hero(tables)
    game = game_with(world, tables, druid)
    in_the_wild(game)
    rng = RNG(5, "band")
    ogres = [spawn(tables, "ogre", rng, i + 1) for i in range(2)]
    group = next(g for g, e in tables.creatures.encounters.items() if e.get("name"))
    game.encounter = PendingEncounter(group, ogres, "Ogres.", True, "")
    assert "seen first" in magic.road_problem(game, druid, "tsunami")
    assert stonework.wave_casters(game)
    hp = [o.hp for o in ogres]
    slots = sp.slots_left(druid, tables)[7]
    said = text(stonework.wave(game))
    assert "wall of water" in said and sp.slots_left(druid, tables)[7] == slots - 1
    assert tables.creatures.encounters[group]["name"] in said and group not in said.replace(
        tables.creatures.encounters[group]["name"], ""), "the band by its name, not its id"
    assert all(o.hp < h for o, h in zip(ogres, hp))
    fight.encounter_fight(game, ambush=False)
    assert game.battle is not None


def test_a_band_drowned_to_the_last_is_a_fight_won(world, tables):
    druid = hero(tables)
    game = game_with(world, tables, druid)
    in_the_wild(game)
    rng = RNG(5, "band")
    game.encounter = PendingEncounter("rats", [spawn(tables, "wolf", rng, i + 1) for i in range(2)], "Wolves.", True, "")
    for cr in game.encounter.creatures:
        cr.hp = 1
    stonework.wave(game)
    assert all(cr.hp <= 0 for cr in game.encounter.creatures)
    b = fight.encounter_fight(game, ambush=False)
    b.step() if b.outcome is None else None
    assert b.outcome == "victory"


def test_the_encounter_screen_offers_the_wave(make_app, world, tables):
    from realmwalker.ui.screens.encounter import EncounterScreen

    druid = hero(tables)
    game = game_with(world, tables, druid)
    in_the_wild(game)
    game.encounter = PendingEncounter("ogres", [spawn(tables, "ogre", RNG(5, "band"), 1)], "Ogres.", True, "")
    app = make_app()
    screen = EncounterScreen(app, game)
    opts = {o[2]: o for o in screen.options()}
    assert "wave" in opts and opts["wave"][3]
    screen.act("wave")
    assert game.battle is not None
