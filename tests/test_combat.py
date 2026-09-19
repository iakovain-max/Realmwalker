"""Combat: the battle engine, creatures, spells, morale, fleeing, the aftermath and encounters."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import fight, save
from realmwalker.game.encounters import encounter_chance, make_encounter, populate_local, threat_words
from realmwalker.game.state import new_game
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import BACK, FOE, FRONT, PARTY, Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn, spawn_group
from realmwalker.rules.inventory import add_item
from realmwalker.rules.progression import award_xp, long_rest, short_rest
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables

OUTCOMES = {"victory", "defeat", "fled", "parley", "surrendered"}


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Battleland", 77, "small"), tables).generate()


def hero(tables, cls="fighter", race="human", seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race(race)
    b.set_class(cls)
    b.set_background("soldier")
    return b.build()


def foes(tables, *def_ids, seed=1):
    rng = RNG(seed, "foes")
    return [spawn(tables, d, rng, i + 1) for i, d in enumerate(def_ids)]


def battle(tables, party, enemies, seed=1, **env):
    b = Battle(tables, party, enemies, Env(**env), RNG(seed, "battle"))
    b.start("Test fight.")
    return b


def autoplay(b: Battle, max_steps: int = 2000) -> None:
    """Party members attack the weakest enemy they can reach; otherwise they step up or dodge."""
    for _ in range(max_steps):
        if b.outcome is not None:
            return
        if b.step():
            continue
        f = b.pending_party()
        assert f is not None, "step() returned False without anyone to act"
        for opt in b.attack_options(f):
            targets = b.targets_for(f, opt.kind, opt.reach)
            if opt.available and targets and (not opt.is_melee or b.can_melee(f, opt)[0]):
                b.do_attack(f, opt, min(targets, key=lambda t: t.hp))
                break
        else:
            if f.rank == BACK:
                b.do_change_rank(f)
            else:
                b.do_dodge(f)
    raise AssertionError("battle did not finish")


def check_sane(b: Battle) -> None:
    for f in b.fighters:
        assert 0 <= f.hp <= f.max_hp, f"{f.name} {f.hp}/{f.max_hp}"
        assert f.state in ("fighting", "fleeing", "down", "dead", "fled", "surrendered")
        assert f.rank in (FRONT, BACK)
    r = b.result()
    assert r.outcome in OUTCOMES
    assert r.xp >= 0 and r.loot_money >= 0


# ---------------------------------------------------------------------------- the engine
@pytest.mark.parametrize("group", ["lone_wolf", "bandits", "wolf_pack", "restless_dead", "goblins", "cultists", "rats"])
@pytest.mark.parametrize("seed", range(6))
def test_battles_always_finish_sanely(tables, group, seed):
    party = [hero(tables, "fighter", seed=seed)]
    enemies = spawn_group(tables, group, RNG(seed, "g"), party_size=1)
    b = battle(tables, party, enemies, seed=seed)
    autoplay(b)
    check_sane(b)
    assert b.outcome in ("victory", "defeat")


@pytest.mark.parametrize("cls", ["fighter", "rogue", "cleric", "wizard"])
def test_every_class_can_fight(tables, cls):
    b = battle(tables, [hero(tables, cls)], foes(tables, "giant_rat"), seed=3)
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


def test_ranks_limit_melee(tables):
    party = [hero(tables, "fighter"), hero(tables, "wizard", seed=2)]
    b = battle(tables, party, foes(tables, "bandit", "bandit_archer"))
    fighter, wizard = b.side(PARTY)
    assert fighter.rank == FRONT and wizard.rank == BACK
    bandit, archer = b.side(FOE)
    assert bandit.rank == FRONT and archer.rank == BACK
    # Melee reaches only the enemy front rank while it stands.
    assert b.targets_for(fighter, "melee") == [bandit]
    assert set(b.targets_for(fighter, "ranged")) == {bandit, archer}
    # From the back rank, no melee without reach.
    assert b.targets_for(wizard, "melee") == []
    melee = next(o for o in b.attack_options(wizard) if o.is_melee and not o.reach)
    assert not b.can_melee(wizard, melee)[0]
    # With the front rank gone, the back rank is open to blades.
    bandit.state = "dead"
    assert b.targets_for(fighter, "melee") == [archer]


def test_change_rank_and_dodge(tables):
    b = battle(tables, [hero(tables)], foes(tables, "wolf"))
    while b.pending_party() is None:
        b.step()
    f = b.pending_party()
    b.do_change_rank(f)
    assert f.rank == BACK
    while b.pending_party() is None and b.outcome is None:
        b.step()
    if b.outcome is None:
        b.do_dodge(f)
        assert f.dodging


# ---------------------------------------------------------------------------- down, dying and wounds
def test_going_down_bleeding_out_and_first_aid(tables):
    fighter, cleric = hero(tables, "fighter"), hero(tables, "cleric", seed=4)
    b = battle(tables, [fighter, cleric], foes(tables, "wolf"))
    f = b.side(PARTY)[0]
    b._apply_hp_loss(f, f.hp + 3, source=None, cause="test")
    assert f.state == "down" and f.hp == 0 and "unconscious" in f.conditions
    assert f.dying >= 1 and not f.stable
    helper = b.side(PARTY)[1]
    add_item(cleric, tables.items, "healers_kit")
    b.order = [helper.id] + [x for x in b.order if x != helper.id]
    b.turn = 0
    b.turn_started = True
    b.do_help(helper, f)
    assert f.stable


def test_bleeding_out_kills(tables):
    c = hero(tables)
    b = battle(tables, [c, hero(tables, "rogue", seed=5)], foes(tables, "wolf"))
    f = b.side(PARTY)[0]
    b._apply_hp_loss(f, f.hp, source=None, cause="test")
    for _ in range(10):
        b._start_of_turn(f)
    assert f.state == "dead" and not c.alive


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


# ---------------------------------------------------------------------------- morale, surrender, parley, flight
def test_bandits_break_and_surrender(tables):
    b = battle(tables, [hero(tables)], foes(tables, "bandit", "bandit"))
    first, second = b.side(FOE)
    b._break(first, "surrender")
    assert first.state == "surrendered" and not first.active
    b._break(second, "flee")
    assert second.state == "fleeing"
    assert b.outcome is None  # a fleeing foe is still on the field until it gets away
    b._ai(second)
    b._ai(second)
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


def test_fleeing_sometimes_works(tables):
    results = set()
    for seed in range(30):
        b = battle(tables, [hero(tables)], foes(tables, "bandit", "bandit"), seed=seed)
        while b.pending_party() is None and b.outcome is None:
            b.step()
        if b.outcome is None:
            b.do_flee(b.pending_party())
            results.add(b.outcome == "fled")
    assert results == {True, False}


# ---------------------------------------------------------------------------- spells and abilities
def test_wizard_spells_and_slots(tables):
    wiz = hero(tables, "wizard", race="elf")
    assert "magic_missile" in spellrules.known_spells(wiz, tables)
    before = spellrules.slots_left(wiz, tables)[0]
    b = battle(tables, [wiz], foes(tables, "wolf", "wolf"))
    f = b.side(PARTY)[0]
    wolf = b.side(FOE)[0]
    hp = wolf.hp
    b.do_cast(f, "fire_bolt", wolf)  # a cantrip: free
    assert spellrules.slots_left(wiz, tables)[0] == before
    wolf2 = b.side(FOE)[1]
    hp2 = wolf2.hp
    b.do_cast(f, "magic_missile", wolf2)  # never misses, spends a slot
    assert spellrules.slots_left(wiz, tables)[0] == before - 1
    assert wolf2.hp < hp2 or wolf2.state == "dead"
    assert wolf.hp <= hp
    long_rest(wiz, tables, RNG(1))
    assert spellrules.slots_left(wiz, tables)[0] == before


def test_sleep_puts_the_weak_to_sleep(tables):
    wiz = hero(tables, "wizard")
    b = battle(tables, [wiz], foes(tables, "giant_rat", "giant_rat"), seed=2)
    b.do_cast(b.side(PARTY)[0], "sleep", None)
    assert any("unconscious" in f.conditions for f in b.side(FOE))


def test_cleric_heals_and_turns_undead(tables):
    cleric = hero(tables, "cleric")
    award_xp(cleric, 300, tables, RNG(1))  # Channel Divinity comes at level 2
    fighter = hero(tables, "fighter", seed=3)
    b = battle(tables, [fighter, cleric], foes(tables, "skeleton", "zombie"))
    ally = b.side(PARTY)[0]
    ally.hp = 1
    caster = b.side(PARTY)[1]
    b.do_cast(caster, "cure_wounds", ally)
    assert ally.hp > 1
    ids = [a[0] for a in b.class_abilities(caster)]
    assert "turn_undead" in ids
    b.do_ability(caster, "turn_undead")
    assert cleric.uses.get("channel_divinity", 0) == 0


def test_second_wind_heals(tables):
    c = hero(tables, "fighter")
    b = battle(tables, [c], foes(tables, "wolf"))
    f = b.side(PARTY)[0]
    f.hp = 1
    assert ("second_wind", "Second Wind", True, "used; rest to recover") in b.class_abilities(f)
    b.do_ability(f, "second_wind")
    assert f.hp > 1 and c.uses["second_wind"] == 0
    short_rest(c, tables, RNG(2))
    assert c.uses["second_wind"] == 1


def test_potions_and_bandages(tables):
    c = hero(tables)
    add_item(c, tables.items, "potion_healing")
    b = battle(tables, [c], foes(tables, "wolf"))
    f = b.side(PARTY)[0]
    f.hp = 1
    potion = next(i for i in b.usable_items(f) if i.def_id == "potion_healing")
    b.do_item(f, potion.uid, f)
    assert f.hp > 1
    assert c.item(potion.uid) is None or c.item(potion.uid).qty < 2


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
    world = WorldGenerator(WorldOptions("Fightland", 303, "small"), tables).generate()
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


def test_defeat_by_wolves_is_death(game):
    game.encounter = make_encounter(game, "wolf_pack", RNG(7, "enc"))
    fight.encounter_fight(game, ambush=False)
    f = game.battle.side(PARTY)[0]
    game.battle._apply_hp_loss(f, f.hp, source=None, cause="test")
    game.battle._check_end()
    after = fight.finish_battle(game)
    assert after.outcome == "death" and game.over is not None
    assert not game.leader.alive


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
    for gid, g in tables.creatures.encounters.items():
        for member, _ in g["members"]:
            assert member in tables.creatures.defs, f"{gid} has unknown {member}"
        assert g["intro"], gid
    for kind, groups in tables.creatures.site_inhabitants.items():
        for g in groups:
            assert g in tables.creatures.encounters, f"{kind} lists unknown group {g}"
