"""Combat on the grid: the battle engine, movement and reach, cover, spells and their areas, dying, morale, the
enemy's tactics, the aftermath and encounters."""

import numpy as np
import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import fight, save
from realmwalker.game.encounters import encounter_chance, make_encounter, populate_local, threat_words
from realmwalker.game.state import new_game
from realmwalker.rules import grid
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import FOE, PARTY, Battle, Env, open_field
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn, spawn_group
from realmwalker.rules.inventory import add_item
from realmwalker.rules.progression import award_xp, long_rest, short_rest
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402

OUTCOMES = {"victory", "defeat", "fled", "parley", "surrendered"}


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def hero(tables, cls="fighter", race="human", seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race(race)
    b.set_class(cls)
    b.set_background("soldier")
    return b.build()


def foes(tables, *def_ids, seed=1):
    rng = RNG(seed, "foes")
    return [spawn(tables, d, rng, i + 1) for i, d in enumerate(def_ids)]


def battle(tables, party, enemies, seed=1, field=None, spots=None, **env):
    b = Battle(tables, party, enemies, Env(**env), RNG(seed, "battle"), field=field, spots=spots)
    b.start("Test fight.")
    return b


def autoplay(b: Battle, max_steps: int = 4000) -> None:
    """The party fights on Auto (the same tactics the enemy uses, plus heals and spells)."""
    for f in b.side(PARTY):
        f.auto = True
    for _ in range(max_steps):
        if b.outcome is not None:
            return
        b.step()
    raise AssertionError("battle did not finish")


def turn_of(b: Battle, f) -> None:
    """Make it `f`'s turn now, with a fresh turn's worth of action and movement."""
    b.order = [f.id] + [x for x in b.order if x != f.id]
    b.turn = 0
    b.turn_started = True
    b._start_of_turn(f)


def walls(tables, width=12, height=8, **squares):
    T = tables.terrain.index
    terrain = np.full((width, height), T["grass"], np.uint16)
    for name, cells in squares.items():
        for c in cells:
            terrain[c] = T[name]
    return grid.Field(tables, terrain)


def check_sane(b: Battle) -> None:
    taken = {}
    for f in b.fighters:
        assert 0 <= f.hp <= f.max_hp, f"{f.name} {f.hp}/{f.max_hp}"
        assert f.state in ("fighting", "fleeing", "down", "dead", "fled", "surrendered")
        if f.state in ("fighting", "fleeing", "down", "surrendered"):
            for c in f.cells:
                assert b.field.in_bounds(*c) and b.field.walk[c], f"{f.name} stands in a wall at {c}"
                assert c not in taken, f"{f.name} and {taken.get(c)} share {c}"
                taken[c] = f.name
    r = b.result()
    assert r.outcome in OUTCOMES
    assert r.xp >= 0 and r.loot_money >= 0


# ---------------------------------------------------------------------------- the engine
@pytest.mark.parametrize("group", ["lone_wolf", "bandits", "wolf_pack", "restless_dead", "goblins", "cultists", "rats"])
@pytest.mark.parametrize("seed", range(5))
def test_battles_always_finish_sanely(tables, group, seed):
    party = [hero(tables, "fighter", seed=seed)]
    enemies = spawn_group(tables, group, RNG(seed, "g"), party_size=1)
    b = battle(tables, party, enemies, seed=seed)
    autoplay(b)
    check_sane(b)
    assert b.outcome in ("victory", "defeat", "fled")


@pytest.mark.parametrize("cls", ["fighter", "rogue", "cleric", "wizard"])
def test_every_class_can_fight(tables, cls):
    b = battle(tables, [hero(tables, cls)], foes(tables, "giant_rat"), seed=3)
    autoplay(b)
    check_sane(b)


def test_a_party_of_four_against_bandits(tables):
    party = [hero(tables, c, seed=i) for i, c in enumerate(("fighter", "rogue", "cleric", "wizard"))]
    b = battle(tables, party, spawn_group(tables, "bandits", RNG(4, "g"), party_size=4), seed=4)
    autoplay(b)
    check_sane(b)


def test_initiative_order_and_turn_cycle(tables):
    b = battle(tables, [hero(tables)], foes(tables, "wolf", "wolf"))
    assert sorted(b.order) == sorted(f.id for f in b.fighters)
    inits = [b.fighter(i).initiative for i in b.order]
    assert inits == sorted(inits, reverse=True)
    rounds = b.round
    autoplay(b)
    assert b.round >= rounds


def test_battle_is_deterministic_for_a_seed(tables):
    logs = []
    for _ in range(2):
        b = battle(tables, [hero(tables)], foes(tables, "bandit", "bandit"), seed=11)
        autoplay(b)
        logs.append(list(b.log))
    assert logs[0] == logs[1]


def test_everyone_starts_on_the_field_apart(tables):
    party = [hero(tables, c, seed=i) for i, c in enumerate(("fighter", "wizard"))]
    b = battle(tables, party, foes(tables, "ogre", "goblin", "goblin"))
    check_sane(b)
    ogre = b.side(FOE)[0]
    assert ogre.sq == 2 and len(ogre.cells) == 4  # large: two squares by two
    assert all(b.gap(p, e) > 3 for p in b.side(PARTY) for e in b.side(FOE)), "the two sides start apart"


# ---------------------------------------------------------------------------- moving and reaching
def test_melee_needs_reach_and_moving_costs_movement(tables):
    b = battle(tables, [hero(tables)], foes(tables, "bandit"), spots={0: (2, 4), 1: (8, 4)})
    f, bandit = b.side(PARTY)[0], b.side(FOE)[0]
    turn_of(b, f)
    sword = next(o for o in b.attack_options(f) if o.key == "main")
    assert b.attack_problem(f, sword, bandit) == "out of reach"
    speed = f.move_left
    assert b.do_move(f, (7, 4))
    assert (f.x, f.y) == (7, 4) and f.move_left == speed - 25
    assert b.attack_problem(f, sword, bandit) is None
    assert b.do_attack(f, sword, bandit)
    assert f.action == 0


def test_difficult_terrain_costs_double(tables):
    fld = walls(tables, mud=[(3, 4), (4, 4), (5, 4)])
    b = battle(tables, [hero(tables)], foes(tables, "wolf"), field=fld, spots={0: (2, 4), 1: (10, 1)})
    f = b.side(PARTY)[0]
    turn_of(b, f)
    reach = b.reachable(f)
    assert reach[(3, 4)].cost == 10  # one square of mud
    assert reach[(3, 3)].cost == 5


def test_leaving_reach_provokes_and_disengaging_does_not(tables):
    b = battle(tables, [hero(tables)], foes(tables, "wolf"), spots={0: (4, 4), 1: (5, 4)})
    f, wolf = b.side(PARTY)[0], b.side(FOE)[0]
    turn_of(b, f)
    before = len([e for e in b.events if e["kind"] == "opportunity"])
    b.do_move(f, (2, 4))
    assert len([e for e in b.events if e["kind"] == "opportunity"]) == before + 1
    assert not wolf.reaction  # one opportunity attack a round
    b2 = battle(tables, [hero(tables)], foes(tables, "wolf"), spots={0: (4, 4), 1: (5, 4)})
    f2 = b2.side(PARTY)[0]
    turn_of(b2, f2)
    b2.do_disengage(f2)
    b2.do_move(f2, (2, 4))
    assert not [e for e in b2.events if e["kind"] == "opportunity"]


def test_dash_doubles_the_way(tables):
    b = battle(tables, [hero(tables)], foes(tables, "wolf"), spots={0: (0, 0), 1: (15, 9)})
    f = b.side(PARTY)[0]
    turn_of(b, f)
    speed = f.move_left
    b.do_dash(f)
    assert f.move_left == 2 * speed and f.action == 0


def test_large_creatures_need_room(tables):
    fld = walls(tables, wall_stone=[(4, y) for y in range(8) if y != 3])
    b = battle(tables, [hero(tables)], foes(tables, "ogre"), field=fld, spots={0: (1, 3), 1: (7, 3)})
    ogre = b.side(FOE)[0]
    turn_of(b, ogre)
    ogre.move_left = 60
    assert not any(sq[0] <= 4 for sq in b.reachable(ogre)), "a two-square ogre cannot squeeze through a one-square gap"


# ---------------------------------------------------------------------------- sight and cover
def test_walls_block_sight_and_a_low_wall_gives_cover(tables):
    fld = walls(tables, wall_stone=[(5, y) for y in range(2, 6)], fence=[(5, 7)])
    archer = foes(tables, "bandit_archer")
    b = battle(tables, [hero(tables)], archer, field=fld, spots={0: (2, 4), 1: (8, 4)})
    f, a = b.side(PARTY)[0], b.side(FOE)[0]
    assert b.field.cover(a.space, f.space) == grid.TOTAL
    assert not b.can_see(a, f)
    bow = next(o for o in b.attack_options(a) if not o.is_melee)
    assert not b.in_reach(a, bow, f)[0]
    f.x, f.y = 2, 7  # now behind the fence: seen, but half hidden
    assert b.field.cover(a.space, f.space) == grid.HALF
    ac, cover = b.target_ac(a, bow, f) if False else b.target_ac(a, f, bow)
    assert cover == grid.HALF and ac == f.ac() + 2


def test_shooting_with_an_enemy_beside_you_is_at_disadvantage(tables):
    b = battle(tables, [hero(tables)], foes(tables, "bandit_archer", "bandit"), spots={0: (5, 4), 1: (6, 4), 2: (12, 4)})
    f, archer = b.side(PARTY)[0], b.side(FOE)[0]
    bow = next(o for o in b.attack_options(archer) if not o.is_melee)
    adv, dis, why = b._adv_dis(archer, f, bow)
    assert dis and "enemy at hand" in why


def test_darkness_hides_and_darkvision_sees(tables):
    party = [hero(tables, race="human"), hero(tables, race="dwarf", seed=2)]
    b = battle(tables, party, foes(tables, "goblin"), spots={0: (2, 2), 1: (2, 6), 2: (8, 4)}, light=0.0)
    human, dwarf = b.side(PARTY)
    goblin = b.side(FOE)[0]
    assert not b.can_see(human, goblin)
    assert b.can_see(dwarf, goblin)
    assert b.can_see(goblin, human)  # goblins see in the dark


# ---------------------------------------------------------------------------- the turn
def test_extra_attack_lets_you_move_between_swings(tables):
    c = hero(tables, "fighter")
    award_xp(c, 6500, tables, RNG(1))
    assert c.level >= 5
    b = battle(tables, [c], foes(tables, "ogre", "ogre"), spots={0: (5, 4), 1: (6, 4), 2: (6, 7)})
    f, o1, o2 = b.side(PARTY)[0], *b.side(FOE)
    turn_of(b, f)
    sword = next(o for o in b.attack_options(f) if o.key == "main")
    assert b.do_attack(f, sword, o1)
    assert f.attacks_left == 1 and f.action == 0
    b.walk(f, [(5, 5), (5, 6)], provoke=False)
    assert b.do_attack(f, sword, o2)
    assert f.attacks_left == 0


def test_the_turn_ends_when_told(tables):
    b = battle(tables, [hero(tables)], foes(tables, "wolf"), spots={0: (2, 4), 1: (12, 4)})
    while b.pending_party() is None and b.outcome is None:
        b.step()
    f = b.pending_party()
    b.do_dodge(f)
    assert f.dodging and b.pending_party() is f  # still free to move
    b.end_turn()
    assert b.pending_party() is not f


# ---------------------------------------------------------------------------- spells and their areas
def test_fireball_burns_friend_and_foe(tables):
    wiz = hero(tables, "wizard")
    award_xp(wiz, 6500, tables, RNG(1))  # third-level spells come at level 5
    wiz.spells["spellbook"].append("fireball")
    friend = hero(tables, "fighter", seed=4)
    b = battle(tables, [wiz, friend], foes(tables, "bandit", "bandit"), spots={0: (1, 1), 1: (9, 5), 2: (10, 5), 3: (10, 6)})
    caster = b.side(PARTY)[0]
    turn_of(b, caster)
    cells = b.spell_area(caster, "fireball", (10, 5))
    caught = b.in_area(cells, "all", caster)
    assert b.side(PARTY)[1] in caught and all(x in caught for x in b.side(FOE))
    hp = {x.id: x.hp for x in caught}
    assert b.do_cast(caster, "fireball", point=(10, 5))
    assert all(x.hp < hp[x.id] or x.state != "fighting" for x in caught)


def test_burning_hands_is_a_cone_and_thunderwave_throws_them_back(tables):
    wiz = hero(tables, "wizard")
    b = battle(tables, [wiz], foes(tables, "bandit", "bandit"), spots={0: (5, 4), 1: (6, 4), 2: (7, 4)})
    caster = b.side(PARTY)[0]
    cone = b.spell_area(caster, "burning_hands", (8, 4))
    assert (6, 4) in cone and (8, 4) in cone and (8, 3) in cone and (4, 4) not in cone and (5, 4) not in cone
    cube = b.spell_area(caster, "thunderwave", (6, 4))
    assert len(cube) == 9 and all(x >= 6 for x, _ in cube)
    near = b.side(FOE)[0]
    turn_of(b, caster)
    before = near.x
    b.do_cast(caster, "thunderwave", point=(6, 4))
    pushed = {e["who"] for e in b.events if e["kind"] == "push"}
    failed = {e["who"] for e in b.events if e["kind"] == "save" and not e["ok"]}
    assert not near.active or near.x >= before
    assert {x.id for x in b.side(FOE) if x.active and x.id in failed} <= pushed


def test_web_holds_and_slows(tables):
    wiz = hero(tables, "wizard")
    award_xp(wiz, 900, tables, RNG(1))
    wiz.spells["spellbook"].append("web")
    b = battle(tables, [wiz], foes(tables, "bandit", "bandit"), spots={0: (1, 4), 1: (9, 4), 2: (10, 4)})
    caster = b.side(PARTY)[0]
    turn_of(b, caster)
    assert b.do_cast(caster, "web", point=(9, 4))
    assert any(z.kind == "web" for z in b.zones) and b.field.difficult(9, 4)
    assert caster.concentration and caster.concentration["spell"] == "web"
    # Losing concentration takes the web away and frees whoever it held.
    b._end_concentration(caster, quiet=True)
    assert not b.zones and not b.field.difficult(9, 4)
    assert not any("restrained" in x.conditions for x in b.side(FOE))


def test_concentration_breaks_when_hurt(tables):
    cleric = hero(tables, "cleric")
    b = battle(tables, [cleric, hero(tables, seed=2)], foes(tables, "wolf"), spots={0: (2, 4), 1: (3, 4), 2: (12, 4)})
    caster = b.side(PARTY)[0]
    turn_of(b, caster)
    assert b.do_cast(caster, "bless")
    assert caster.concentration is not None and any(x.buff_value("attack_die") for x in b.side(PARTY))
    broke = False
    for seed in range(30):
        b.rng = RNG(seed, "conc")
        caster.concentration = caster.concentration or {"spell": "bless", "rounds": 10}
        b._hit(b.side(FOE)[0], caster, 1, "piercing", crit=False, weapon="bite")
        if caster.concentration is None:
            broke = True
            break
        caster.hp = caster.max_hp
    assert broke
    assert not any(b.get("conc") for x in b.side(PARTY) for b in x.buffs)


def test_wizard_spells_and_slots(tables):
    wiz = hero(tables, "wizard", race="elf")
    assert "magic_missile" in spellrules.known_spells(wiz, tables)
    before = spellrules.slots_left(wiz, tables)[0]
    b = battle(tables, [wiz], foes(tables, "wolf", "wolf"), spots={0: (2, 4), 1: (10, 3), 2: (10, 6)})
    f = b.side(PARTY)[0]
    wolf, wolf2 = b.side(FOE)
    turn_of(b, f)
    b.do_cast(f, "fire_bolt", wolf)  # a cantrip: free
    assert spellrules.slots_left(wiz, tables)[0] == before
    turn_of(b, f)
    hp2 = wolf2.hp
    b.do_cast(f, "magic_missile", wolf2)  # never misses, spends a slot
    assert spellrules.slots_left(wiz, tables)[0] == before - 1
    assert wolf2.hp < hp2 or wolf2.state == "dead"
    long_rest(wiz, tables, RNG(1))
    assert spellrules.slots_left(wiz, tables)[0] == before


def test_a_bonus_action_spell_leaves_only_a_cantrip(tables):
    cleric = hero(tables, "cleric")
    b = battle(tables, [cleric, hero(tables, seed=3)], foes(tables, "wolf"), spots={0: (2, 4), 1: (3, 4), 2: (12, 4)})
    f, ally = b.side(PARTY)
    ally.hp = 1
    turn_of(b, f)
    assert b.do_cast(f, "healing_word", ally)
    options = {sid: (ok, why) for sid, ok, why in b.spell_options(f)}
    assert not options["cure_wounds"][0] and options["sacred_flame"][0]


def test_sleep_the_2024_way(tables):
    """Sleep (2024): a failed Wisdom save leaves a foe able to do nothing until the end of its next turn; a second
    failure puts it to sleep; a blow wakes it, lying down. The dead never sleep."""
    from realmwalker.rules.engine import durations

    wiz = hero(tables, "wizard")
    b = battle(tables, [wiz], foes(tables, "giant_rat", "skeleton"), seed=2, spots={0: (2, 4), 1: (9, 4), 2: (10, 5)})
    f = b.side(PARTY)[0]
    rat, bones = b.side(FOE)
    b._save = lambda *a, **k: False  # every save fails
    turn_of(b, f)
    assert b.do_cast(f, "sleep", point=(9, 4))
    assert "incapacitated" in rat.conditions and not rat.can_act()
    assert not bones.conditions  # undead do not sleep
    durations.tick(b, rat, "turn_end")  # the end of its next turn: the second save
    assert "unconscious" in rat.conditions and "prone" in conditions_of(rat)
    b._hit(bones, rat, 1, "piercing", crit=False, weapon="bite")
    assert "unconscious" not in rat.conditions and "prone" in rat.conditions and rat.can_act()


def conditions_of(f):
    from realmwalker.rules.engine import query

    return query.conditions(f)


def test_cleric_heals_and_turns_undead(tables):
    cleric = hero(tables, "cleric")
    award_xp(cleric, 300, tables, RNG(1))  # Channel Divinity comes at level 2
    fighter = hero(tables, "fighter", seed=3)
    b = battle(tables, [fighter, cleric], foes(tables, "skeleton", "zombie"),
               spots={0: (4, 4), 1: (3, 4), 2: (8, 4), 3: (8, 5)})
    ally = b.side(PARTY)[0]
    ally.hp = 1
    caster = b.side(PARTY)[1]
    turn_of(b, caster)
    b.do_cast(caster, "cure_wounds", ally)
    assert ally.hp > 1
    turn_of(b, caster)
    ids = [a[0] for a in b.class_abilities(caster) if a[2]]
    assert "turn_undead" in ids
    b.do_ability(caster, "turn_undead")
    assert cleric.uses.get("channel_divinity", 0) == 0


def test_spiritual_weapon_strikes_where_it_is_put(tables):
    cleric = hero(tables, "cleric")
    award_xp(cleric, 900, tables, RNG(1))
    b = battle(tables, [cleric], foes(tables, "ogre"), spots={0: (2, 4), 1: (9, 4)})
    f = b.side(PARTY)[0]
    turn_of(b, f)
    assert b.do_cast(f, "spiritual_weapon", point=(8, 4))
    assert b.tokens and any(e["kind"] == "attack" for e in b.events)
    turn_of(b, f)
    assert "spirit_strike" in [a[0] for a in b.class_abilities(f) if a[2]]


def test_second_wind_heals(tables):
    c = hero(tables, "fighter")
    b = battle(tables, [c], foes(tables, "wolf"))
    f = b.side(PARTY)[0]
    turn_of(b, f)
    f.hp = 1
    assert ("second_wind", True) in [(a[0], a[2]) for a in b.class_abilities(f)]
    b.do_ability(f, "second_wind")
    assert f.hp > 1 and c.uses["second_wind"] == 0 and f.bonus == 0
    short_rest(c, tables, RNG(2))
    assert c.uses["second_wind"] == 1


def test_potions_and_bandages(tables):
    c = hero(tables)
    add_item(c, tables.items, "potion_healing")
    b = battle(tables, [c], foes(tables, "wolf"))
    f = b.side(PARTY)[0]
    turn_of(b, f)
    f.hp = 1
    potion = next(i for i in b.usable_items(f) if i.def_id == "potion_healing")
    b.do_item(f, potion.uid, f)
    assert f.hp > 1
    assert c.item(potion.uid) is None or c.item(potion.uid).qty < 2


def test_dragon_breath_is_a_cone(tables):
    b = battle(tables, [hero(tables), hero(tables, "wizard", seed=2)], foes(tables, "young_dragon"),
               spots={0: (8, 4), 1: (9, 5), 2: (3, 4)})
    dragon = b.side(FOE)[0]
    breath = next(o for o in b.attack_options(dragon) if o.extra.get("area"))
    turn_of(b, dragon)
    b.area_attack(dragon, breath, (8, 4))
    assert not dragon.recharge["fire breath"]
    assert all(x.hp < x.max_hp or x.state != "fighting" for x in b.side(PARTY))


# ---------------------------------------------------------------------------- down, dying and wounds
def test_going_down_death_saves_and_first_aid(tables):
    fighter, cleric = hero(tables, "fighter"), hero(tables, "cleric", seed=4)
    b = battle(tables, [fighter, cleric], foes(tables, "wolf"), spots={0: (4, 4), 1: (5, 4), 2: (12, 4)})
    f, helper = b.side(PARTY)
    b._apply_hp_loss(f, f.hp + 3, source=None, cause="test")
    assert f.state == "down" and f.hp == 0 and "unconscious" in f.conditions
    assert f.death_saves == [0, 0] and not f.stable
    add_item(cleric, tables.items, "healers_kit")
    turn_of(b, helper)
    b.do_help(helper, f)
    assert f.stable


def test_death_saves_end_one_way_or_the_other(tables):
    outcomes = set()
    for seed in range(30):
        c = hero(tables, seed=seed)
        b = battle(tables, [c, hero(tables, "rogue", seed=5)], foes(tables, "wolf"), seed=seed)
        f = b.side(PARTY)[0]
        b._apply_hp_loss(f, f.hp, source=None, cause="test")
        for _ in range(12):
            if f.state != "down" or f.stable:
                break
            b._start_of_turn(f)
        outcomes.add("dead" if f.state == "dead" else ("stable" if f.stable else "up"))
        if f.state == "dead":
            assert not c.alive
    assert {"dead", "stable"} <= outcomes


def test_blows_while_down_and_massive_damage_kill(tables):
    c = hero(tables)
    b = battle(tables, [c, hero(tables, "rogue", seed=5)], foes(tables, "wolf"))
    f = b.side(PARTY)[0]
    b._apply_hp_loss(f, f.hp, source=None, cause="test")
    b._apply_hp_loss(f, 1, source=None, cause="test", crit=True)
    assert f.death_saves[1] == 2
    b._apply_hp_loss(f, 1, source=None, cause="test")
    assert f.state == "dead"
    c2 = hero(tables, seed=3)
    b2 = battle(tables, [c2, hero(tables, "rogue", seed=5)], foes(tables, "wolf"))
    f2 = b2.side(PARTY)[0]
    b2._apply_hp_loss(f2, f2.hp + max(f2.max_hp, 14), source=None, cause="test")
    assert f2.state == "dead"


def test_heavy_hits_leave_wounds(tables):
    wounded = 0
    for seed in range(40):
        c = hero(tables, seed=seed)
        b = battle(tables, [c], foes(tables, "wolf", seed=seed), seed=seed)
        wolf = b.side(FOE)[0]
        b._hit(wolf, b.side(PARTY)[0], 7, "piercing", crit=True, weapon="bite", bite=True)
        wounded += bool(c.wounds)
        for w in c.wounds:
            assert 1 <= w.severity <= 3 and w.part and w.label
    assert wounded >= 5, "a critical bite for most of a character's hit points often wounds"


def test_death_ward_takes_the_blow(tables):
    """A cleric's ward turns the blow that would put somebody down, once."""
    c = hero(tables, "cleric")
    b = battle(tables, [c], foes(tables, "wolf"))
    f = next(x for x in b.fighters if x.char is c)
    f.buffs.append({"death_ward": 1, "rounds": 10, "source": "death_ward"})
    f.hp = 3
    b._apply_hp_loss(f, 3, source=None, cause="test")
    assert f.hp == 1 and f.state == "fighting" and not any("death_ward" in x for x in f.buffs)
    b._apply_hp_loss(f, 3, source=None, cause="test")
    assert f.state == "down"


# ---------------------------------------------------------------------------- morale, surrender, parley, running
def test_bandits_break_surrender_and_run_for_the_edge(tables):
    b = battle(tables, [hero(tables)], foes(tables, "bandit", "bandit"), spots={0: (2, 4), 1: (3, 4), 2: (13, 4)})
    first, second = b.side(FOE)
    b._break(first, "surrender")
    assert first.state == "surrendered" and not first.active
    b._break(second, "flee")
    assert second.state == "fleeing"
    assert b.outcome is None  # a fleeing foe is still on the field until it gets away
    for _ in range(6):
        if second.state == "fled":
            break
        turn_of(b, second)
        from realmwalker.rules import tactics

        tactics.take_turn(b, second)
    assert second.state == "fled"
    assert b.outcome == "victory"
    r = b.result()
    assert first.creature in r.captives and second.creature in r.fled


def test_fanatics_and_the_dead_never_break(tables):
    b = battle(tables, [hero(tables)], foes(tables, "skeleton", "cult_fanatic"))
    for f in b.side(FOE):
        b._morale_check(f, "hurt")
        assert f.state == "fighting"
    assert b.parley_dc("persuade") is None and b.parley_dc("calm") is None


def test_parley_options_depend_on_the_enemy(tables):
    beasts = battle(tables, [hero(tables)], foes(tables, "wolf", "wolf"))
    assert beasts.parley_dc("calm") is not None
    assert beasts.parley_dc("persuade") is None
    people = battle(tables, [hero(tables)], foes(tables, "bandit"))
    assert people.parley_dc("persuade") is not None and people.parley_dc("calm") is None


def test_surrender_only_to_the_merciful(tables):
    wolves = battle(tables, [hero(tables)], foes(tables, "wolf"))
    assert not wolves.surrender_possible()[0]
    bandits = battle(tables, [hero(tables)], foes(tables, "bandit"))
    assert bandits.surrender_possible()[0]
    f = bandits.side(PARTY)[0]
    bandits.do_surrender(f)
    assert bandits.outcome == "surrendered"


def test_getting_away_off_the_edge_of_the_field(tables):
    b = battle(tables, [hero(tables), hero(tables, "rogue", seed=2)], foes(tables, "bandit"),
               spots={0: (0, 4), 1: (5, 4), 2: (14, 4)})
    a, c = b.side(PARTY)
    turn_of(b, a)
    assert b.can_leave(a)
    assert b.do_leave(a)
    assert a.state == "fled" and b.outcome is None
    turn_of(b, c)
    assert not b.can_leave(c)
    b.do_move(c, (0, 4))
    assert b.do_leave(c)
    assert b.outcome == "fled"


# ---------------------------------------------------------------------------- tactics
def test_wolves_close_in_and_bite(tables):
    b = battle(tables, [hero(tables)], foes(tables, "wolf"), spots={0: (2, 4), 1: (10, 4)})
    wolf = b.side(FOE)[0]
    from realmwalker.rules import tactics

    turn_of(b, wolf)
    tactics.take_turn(b, wolf)
    assert b.gap(wolf, b.side(PARTY)[0]) <= 1
    assert any(e["kind"] == "attack" and e["by"] == wolf.id for e in b.events)


def test_archers_shoot_from_where_they_stand(tables):
    b = battle(tables, [hero(tables)], foes(tables, "bandit_archer"), spots={0: (2, 4), 1: (10, 4)})
    archer = b.side(FOE)[0]
    from realmwalker.rules import tactics

    turn_of(b, archer)
    tactics.take_turn(b, archer)
    assert b.gap(archer, b.side(PARTY)[0]) > 1, "an archer does not walk up to a swordsman"
    assert any(e["kind"] == "attack" and e["by"] == archer.id and not e["melee"] for e in b.events)


# ---------------------------------------------------------------------------- experience and rest
def test_xp_levels_up_automatically(tables):
    c = hero(tables, "fighter")
    hp = c.max_hp
    notes = award_xp(c, 300, tables, RNG(1))
    assert c.level == 2 and c.max_hp > hp
    assert any("level 2" in n for n in notes)


def test_short_rest_spends_hit_dice(tables):
    c = hero(tables)
    c.hp = 1
    short_rest(c, tables, RNG(3))
    assert c.hp > 1 and c.hit_dice == 0
    long_rest(c, tables, RNG(3))
    assert c.hp == c.max_hp and c.hit_dice >= 1


# ---------------------------------------------------------------------------- whole-game flow
@pytest.fixture
def game(tables):
    world = cached_world(WorldOptions("Fightland", 303, "small"), tables)
    return new_game(world, tables, hero(tables))


def win(game):
    b = game.battle
    for f in b.side(FOE):
        f.state = "dead"
        f.creature.alive = False
        f.hp = 0
    b._check_end()
    assert b.outcome == "victory"


def test_encounter_to_victory_with_loot_and_xp(game):
    game.encounter = make_encounter(game, "bandits", RNG(5, "enc"))
    assert game.busy and not game.move(1, 0)
    fight.encounter_fight(game, ambush=False)
    assert game.battle is not None and game.encounter is None
    check_sane(game.battle)
    win(game)
    after = fight.finish_battle(game)
    assert game.battle is None and game.aftermath is after
    assert after.outcome == "victory" and after.xp > 0
    assert game.leader.xp == after.xp
    money = game.leader.money
    items = len(game.leader.inventory)
    loot_money = after.money
    fight.take_loot(game)
    assert game.leader.money == money + loot_money
    assert len(game.leader.inventory) >= items
    fight.leave_loot(game)


def test_defeat_by_bandits_means_robbery_not_death(game):
    game.leader.money = 500
    game.encounter = make_encounter(game, "bandits", RNG(6, "enc"))
    fight.encounter_fight(game, ambush=False)
    f = game.battle.side(PARTY)[0]
    game.battle._apply_hp_loss(f, f.hp, source=None, cause="test")
    game.battle._check_end()
    assert game.battle.outcome == "defeat"
    after = fight.finish_battle(game)
    assert after.outcome == "robbed" and game.over is None
    assert game.leader.alive and game.leader.hp >= 1 and game.leader.money == 0


def test_defeat_by_wolves_is_death_for_whoever_does_not_wake(game, monkeypatch):
    monkeypatch.setattr(fight, "MAULED_DC", 100)  # nobody makes the Constitution save
    game.encounter = make_encounter(game, "wolf_pack", RNG(7, "enc"))
    fight.encounter_fight(game, ambush=False)
    f = game.battle.side(PARTY)[0]
    game.battle._apply_hp_loss(f, f.hp, source=None, cause="test")
    game.battle._check_end()
    after = fight.finish_battle(game)
    assert after.outcome == "death" and game.over is not None
    assert not game.leader.alive


def test_beaten_by_beasts_you_may_be_left_for_dead(game, monkeypatch):
    """Beasts lose interest in what has stopped moving and go for the food in the pack instead: whoever makes the
    Constitution save wakes hours later, alone, at 1 hit point, with half the food gone."""
    monkeypatch.setattr(fight, "MAULED_DC", -100)
    from realmwalker.rules.inventory import add_item

    add_item(game.leader, game.tables.items, "rations", 4)
    before = sum(it.qty for it in game.leader.inventory if it.def_id == "rations")
    game.encounter = make_encounter(game, "wolf_pack", RNG(7, "enc"))
    fight.encounter_fight(game, ambush=False)
    start = game.world.time
    f = game.battle.side(PARTY)[0]
    game.battle._apply_hp_loss(f, f.hp, source=None, cause="test")
    game.battle._check_end()
    after = fight.finish_battle(game)
    assert after.outcome == "mauled" and game.over is None
    assert game.leader.alive and game.leader.hp >= 1
    assert sum(it.qty for it in game.leader.inventory if it.def_id == "rations") < before
    assert game.world.time - start >= 30
    assert any("food" in n for n in after.notes)


def test_nobody_downed_in_a_long_fight_dies_of_it_once_the_fight_is_over(game):
    """The fight's minutes used to pass before anyone came round: a body still at 0 hit points was found dead of its
    hurts, so bandits who rob and leave you killed you after all, if the fight had gone on for ten rounds."""
    game.leader.money = 500
    game.encounter = make_encounter(game, "bandits", RNG(6, "enc"))
    fight.encounter_fight(game, ambush=False)
    game.battle.round = 40
    f = game.battle.side(PARTY)[0]
    game.battle._apply_hp_loss(f, f.hp, source=None, cause="test")
    game.battle._check_end()
    after = fight.finish_battle(game)
    assert after.outcome == "robbed" and game.over is None and game.leader.alive


def test_captive_fates(game):
    game.encounter = make_encounter(game, "bandits", RNG(8, "enc"))
    fight.encounter_fight(game, ambush=True)
    b = game.battle
    first, *rest = b.side(FOE)
    b._break(first, "surrender")
    for f in rest:
        f.state = "dead"
        f.creature.alive = False
    b._check_end()
    after = fight.finish_battle(game)
    assert first.creature in after.captives
    loot_before = len(after.loot)
    fight.decide_captive(game, first.creature, "rob")
    assert after.fates[first.creature.uid] == "rob"
    assert len(after.loot) >= loot_before
    assert any("robbed" in d for d in game.leader.deeds)


def test_slipping_away_and_talking(game):
    outcomes = set()
    for seed in range(12):
        game.battle = None
        game.encounter = make_encounter(game, "bandits", RNG(seed, "enc"))
        ok = fight.encounter_evade(game)
        outcomes.add(ok)
        assert (game.battle is None) == ok
    assert outcomes == {True, False}
    game.battle = None
    game.encounter = make_encounter(game, "wolf_pack", RNG(1, "enc"))
    assert fight.encounter_talk_dc(game)[0] is None


def test_encounter_chance_rises_with_danger_and_night():
    assert encounter_chance(0, 60, False, False) < encounter_chance(5, 60, False, False)
    assert encounter_chance(3, 60, False, False) < encounter_chance(3, 60, True, False)
    assert encounter_chance(3, 60, False, True) < encounter_chance(3, 60, False, False)
    assert encounter_chance(9, 100000, True, False) <= 0.9


def test_threat_words_scale(tables):
    party = [hero(tables)]
    rng = RNG(1)
    weak = threat_words(tables, [spawn(tables, "giant_rat", rng, 1)], party)
    deadly = threat_words(tables, [spawn(tables, "troll", rng, 1)], party)
    assert "could take" in weak and "kill" in deadly


def test_sites_are_inhabited_and_actors_survive_saving(game, tmp_path):
    world = game.world
    site = next(s for s in world.sites if game.tables.creatures.site_inhabitants.get(s.kind))
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    lm = game.local
    assert lm.populated and lm.actors, f"{site.kind} should have inhabitants"
    folder = save.save_game(game, tmp_path)
    loaded = save.load_game(folder, game.tables)
    lm2 = loaded.world.local_maps[lm.key]
    assert [a.to_dict() for a in lm2.actors] == [a.to_dict() for a in lm.actors]
    assert lm2.populated


def test_rest_heals_and_can_be_interrupted(game):
    game.leader.hp = 1
    notes = fight.rest(game, "long")
    assert game.leader.hp == game.leader.max_hp or game.encounter is not None
    assert notes


def test_populate_is_only_once(game):
    game.enter_local()
    lm = game.local
    count = len(lm.actors)
    populate_local(game, lm)
    assert len(lm.actors) == count


# ---------------------------------------------------------------------------- data
def test_creature_data_is_consistent(tables):
    for def_id, d in tables.creatures.defs.items():
        assert d["attacks"], def_id
        for item_id, _ in d.get("gear", []):
            assert item_id in tables.items, f"{def_id} carries unknown {item_id}"
        for a in d["attacks"]:
            if a.get("area"):
                assert a.get("save") and a.get("dc"), f"{def_id}'s {a['name']} has an area but no save"
    for gid, g in tables.creatures.encounters.items():
        for member, _ in g["members"]:
            assert member in tables.creatures.defs, f"{gid} has unknown {member}"
        assert g["intro"], gid
    for kind, groups in tables.creatures.site_inhabitants.items():
        for g in groups:
            assert g in tables.creatures.encounters, f"{kind} lists unknown group {g}"


def test_every_spell_can_be_aimed(tables):
    """Each spell says how far it reaches and how it is aimed, and an area spell has a shape the grid knows."""
    for sid, sp in tables.spells.defs.items():
        assert "range" in sp, sid
        if sp["target"] in ("point", "direction"):
            assert sp.get("area") or spellrules.has_op(sp, "teleport", "summon", "guardian"), sid
        if sp.get("area"):
            assert sp["area"]["shape"] in ("sphere", "cylinder", "cube", "cone", "line", "emanation"), sid


def test_a_fight_nobody_can_reach_breaks_off(tables):
    """A wall between the two sides with no way round: after a few rounds of nothing, it ends."""
    fld = walls(tables, wall_stone=[(6, y) for y in range(8)])
    b = battle(tables, [hero(tables)], foes(tables, "wolf"), field=fld, spots={0: (2, 4), 1: (10, 4)})
    autoplay(b)
    assert b.outcome == "parley" and b.round <= 6
    assert any("breaks off" in text for text, _ in b.log)


# ---------------------------------------------------------------------------- the paths' powers on the grid
def hero_at(tables, cls, level, sub=None, seed=1, race="human"):
    c = hero(tables, cls, race=race, seed=seed)
    xp = {1: 0, 2: 300, 3: 900, 5: 6500, 6: 14000, 7: 23000, 9: 48000, 10: 64000}[level]
    award_xp(c, xp, tables, RNG(seed, "xp"), auto=True)
    if sub:
        c.subclass = sub
    c.hp = c.max_hp
    return c


def test_sculpt_spells_spares_friends_in_the_fire(tables):
    wiz = hero_at(tables, "wizard", 3, "evocation")
    friend = hero(tables, "fighter", seed=3)
    b = battle(tables, [wiz, friend], foes(tables, "bandit"), spots={0: (3, 4), 1: (5, 4), 2: (6, 4)})
    caster, ally = b.side(PARTY)
    turn_of(b, caster)
    hp = ally.hp
    assert ally in b.in_area(b.spell_area(caster, "burning_hands", (6, 4)), "all", caster)
    assert b.do_cast(caster, "burning_hands", point=(6, 4))
    assert ally.hp == hp and any("Sculpt Spells" in t for t, _ in b.log)


def test_an_abjurers_ward_takes_the_blows_first(tables):
    wiz = hero_at(tables, "wizard", 3, "abjuration")
    b = battle(tables, [wiz], foes(tables, "wolf"), spots={0: (3, 4), 1: (4, 4)})
    f, wolf = b.side(PARTY)[0], b.side(FOE)[0]
    turn_of(b, f)
    assert b.do_cast(f, "mage_armor")
    ward = wiz.uses.get("arcane_ward", 0)
    assert ward == 2 * wiz.level + f.mod("int")
    hp = f.hp
    b._hit(wolf, f, 3, "piercing", crit=False, weapon="bite")
    assert f.hp == hp and wiz.uses["arcane_ward"] == ward - 3
    long_rest(wiz, tables, RNG(1))
    assert not wiz.uses.get("arcane_ward")


def test_protection_and_holding_the_line(tables):
    knight = hero_at(tables, "fighter", 3, "knight")
    knight.fighting_style = "protection"
    add_item(knight, tables.items, "shield")
    from realmwalker.rules.inventory import equip

    shield = next(i for i in knight.inventory if i.def_id == "shield")
    equip(knight, tables.items, shield.uid, "off_hand")
    friend = hero(tables, "wizard", seed=5)
    b = battle(tables, [knight, friend], foes(tables, "bandit"), spots={0: (4, 4), 1: (4, 5), 2: (5, 5)})
    k, w = b.side(PARTY)
    bandit = b.side(FOE)[0]
    sword = next(o for o in b.attack_options(bandit) if o.is_melee)
    adv, dis, why = b._adv_dis(bandit, w, sword)
    assert dis and any("holds the line" in x for x in why)
    b._attack(bandit, sword, w)
    assert not k.reaction and any("shield in the way" in t for t, _ in b.log)


def test_a_cutthroat_strikes_first_and_hard(tables):
    rogue = hero_at(tables, "rogue", 3, "cutthroat")
    b = battle(tables, [rogue], foes(tables, "bandit"), spots={0: (4, 4), 1: (5, 4)})
    r, bandit = b.side(PARTY)[0], b.side(FOE)[0]
    knife = next(o for o in b.attack_options(r) if o.is_melee)
    adv, dis, why = b._adv_dis(r, bandit, knife)
    assert adv and "not yet moving" in why
    bandit.acted = True
    adv, dis, why = b._adv_dis(r, bandit, knife)
    assert "not yet moving" not in why


def test_indomitable_and_guided_strike(tables):
    fighter = hero_at(tables, "fighter", 9, "champion")
    b = battle(tables, [fighter], foes(tables, "wolf"))
    f = b.side(PARTY)[0]
    assert not b._save(f, "wis", 99)  # nobody makes DC 99, but it is tried twice
    assert fighter.uses["indomitable"] == 0 and any("indomitable" in t for t, _ in b.log)
    priest = hero_at(tables, "cleric", 2, "war")
    priest.uses["channel_divinity"] = 1
    b2 = battle(tables, [priest], foes(tables, "ogre"), spots={0: (4, 4), 1: (5, 4)})
    c, ogre = b2.side(PARTY)[0], b2.side(FOE)[0]
    mace = next(o for o in b2.attack_options(c) if o.is_melee)
    for seed in range(40):
        b2.rng = RNG(seed, "guided")
        if priest.uses["channel_divinity"] == 0:
            break
        b2._attack(c, mace, ogre)
    assert priest.uses["channel_divinity"] == 0 and any("guides the blow" in t for t, _ in b2.log)


def test_divine_intervention(tables):
    cleric = hero_at(tables, "cleric", 10, "life")
    friend = hero(tables, seed=4)
    b = battle(tables, [cleric, friend], foes(tables, "bandit", "bandit"))
    c, ally = b.side(PARTY)
    turn_of(b, c)
    ally.hp = 1
    assert ("divine_intervention", True) in [(a[0], a[2]) for a in b.class_abilities(c)]
    real = RNG(3, "god")

    class Answered:
        """The dice, except that the god answers (the percentile roll comes up 1)."""

        def __getattr__(self, name):
            return getattr(real, name)

        def randint(self, a, top):
            return 1 if top == 100 else real.randint(a, top)

    b.rng = Answered()
    b.do_ability(c, "divine_intervention")
    assert ally.hp == ally.max_hp and cleric.uses["divine_intervention"] == 0
    assert ("divine_intervention", False) in [(a[0], a[2]) for a in b.class_abilities(c)]


def test_enemy_casters_use_their_spells(tables):
    """A cult fanatic raises a spiritual weapon and holds the strongest of you; an acolyte blesses the band."""
    party = [hero(tables, "fighter"), hero(tables, "rogue", seed=2)]
    b = battle(tables, party, foes(tables, "cult_fanatic", "cultist", "cultist"),
               spots={0: (3, 4), 1: (3, 5), 2: (9, 4), 3: (7, 3), 4: (7, 6)})
    fanatic = b.side(FOE)[0]
    from realmwalker.rules import tactics

    turn_of(b, fanatic)
    assert "hold_person" in b.creature_spells(fanatic)
    tactics.take_turn(b, fanatic)
    casts = [e["spell"] for e in b.events if e["kind"] == "cast" and e["by"] == fanatic.id]
    assert "spiritual_weapon" in casts and ("hold_person" in casts or "command" in casts or "sacred_flame" in casts)
    assert fanatic.slots[1] < 3 or fanatic.slots[0] < 4
    b2 = battle(tables, [hero(tables)], foes(tables, "acolyte", "bandit", "bandit"))
    acolyte = b2.side(FOE)[0]
    turn_of(b2, acolyte)
    tactics.take_turn(b2, acolyte)
    assert acolyte.concentration and acolyte.concentration["spell"] == "bless"


# ---------------------------------------------------------------------------- flanking (DMG optional rule)
def test_flanking_geometry():
    t = (5, 5, 1)
    around = [(4, 4), (5, 4), (6, 4), (4, 5), (6, 5), (4, 6), (5, 6), (6, 6)]
    pairs = {frozenset((a, c)) for a in around for c in around if a != c and grid.flanks((*a, 1), (*c, 1), t)}
    assert pairs == {frozenset(((4, 5), (6, 5))), frozenset(((5, 4), (5, 6))), frozenset(((4, 4), (6, 6))),
                     frozenset(((6, 4), (4, 6)))}, "only opposite sides and opposite corners"
    assert not grid.flanks((3, 5, 1), (6, 5, 1), t), "both must be beside it"
    assert grid.flanks((3, 4, 2), (6, 5, 1), t), "a large creature flanks if any of its squares does"
    ogre = (5, 5, 2)
    assert grid.flanks((4, 5, 1), (7, 6, 1), ogre) and not grid.flanks((4, 5, 1), (5, 7, 1), ogre)


def test_flanking_gives_advantage_in_melee_only(tables):
    b = battle(tables, [hero(tables), hero(tables, "rogue", seed=2)], foes(tables, "bandit"),
               spots={0: (4, 5), 1: (6, 5), 2: (5, 5)})
    f, r = b.side(PARTY)
    bandit = b.side(FOE)[0]
    sword = next(o for o in b.attack_options(f) if o.is_melee)
    adv, dis, why = b._adv_dis(f, bandit, sword)
    assert adv and "flanking" in why
    assert b.flanker(f, bandit) is r
    # The bandit is not flanked by two of you standing side by side.
    r.x, r.y = 4, 4
    adv, dis, why = b._adv_dis(f, bandit, sword)
    assert "flanking" not in why
    # A friend who cannot act does not flank.
    r.x, r.y = 6, 5
    r.conditions["stunned"] = 1
    assert b.flanker(f, bandit) is None
    del r.conditions["stunned"]
    # And it is for blows, not for shooting.
    bow = next((o for o in b.attack_options(r) if not o.is_melee), None)
    if bow is not None:
        assert "flanking" not in b._adv_dis(r, bandit, bow)[2]


def test_the_enemy_walks_round_to_flank(tables):
    """Two bandits and a lone fighter: the second bandit goes to the far side of him, not to the near one."""
    b = battle(tables, [hero(tables)], foes(tables, "bandit", "bandit"), spots={0: (8, 5), 1: (9, 5), 2: (12, 5)})
    me = b.side(PARTY)[0]
    first, second = b.side(FOE)
    from realmwalker.rules import tactics

    for x in b.attack_options(second):
        if not x.is_melee:
            x.available = False
    turn_of(b, second)
    plan = tactics.best_plan(b, second, [o for o in b.attack_options(second) if o.is_melee])
    assert plan is not None
    end = plan[1][-1] if plan[1] else (second.x, second.y)
    assert grid.flanks((end[0], end[1], 1), first.space, me.space), f"it should stand opposite its friend, not at {end}"


def test_dodging_helps_against_fire_and_exhaustion_hurts_saves(tables):
    """Dodge: Dexterity saves with advantage. Exhaustion (2024): 2 off every saving throw for each level."""
    from realmwalker.rules.engine import query

    c = hero(tables)
    b = battle(tables, [c], foes(tables, "wolf"))
    f = b.side(PARTY)[0]
    f.dodging = True
    assert query.save_roll(b, f, "dex").roll.mode == "advantage"
    f.dodging = False
    fresh = query.save_roll(b, f, "wis").bonus
    c.exhaustion = 3
    r = query.save_roll(b, f, "wis")
    assert r.roll.mode == "" and r.bonus == fresh - 6
