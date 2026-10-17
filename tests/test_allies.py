"""Allies on the field (Expansion 3 F.1): a familiar and a steed in real fights - placed beside their owner, their
turns in the order, the familiar's options without attacks and its Help, the steed's slam and its kind's gift, Life
Bond, vanishing at 0, a fight lost with only an ally standing - and outside one: Find Familiar and Find Steed cast on
the road, a familiar sent away and called back, records kept and healed, the steed ridden by its owner and never sold,
the familiar's watch at night."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import allies
from realmwalker.rules.combat import PARTY, Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import actions
from realmwalker.rules.progression import award_xp, long_rest
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Lastrites", 37, "small"), tables)


def game_with(world, tables, *party):
    from realmwalker.game import pack
    from realmwalker.game.state import new_game

    game = new_game(copy.deepcopy(world), tables, party[0])
    for c in party[1:]:
        game.party.append(c)
    game.survival = False
    pack.sync(game)
    return game


def hero(tables, cls="wizard", seed=1, xp=0):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("sage")
    c = b.build()
    if xp:
        award_xp(c, xp, tables, RNG(seed), auto=True)
    c.hp = c.max_hp
    return c


def with_familiar(c, form="owl", type_="fey", tables=None):
    hp = allies.familiar_max_hp(tables, form)
    c.spells["familiar"] = {"form": form, "type": type_, "name": "Wren", "hp": hp, "max_hp": hp, "gone": False,
                            "away": False}
    return c


def fight(tables, party, foes, spots, seed=1):
    rng = RNG(seed, "foes")
    crs = [spawn(tables, d, rng, i + 1) for i, d in enumerate(foes)]
    b = Battle(tables, party, crs, Env(), RNG(seed, "battle"), spots=spots)
    allies.bring_in(b, [f for f in b.side(PARTY) if f.char is not None])
    b.start()
    return b


def test_a_familiar_comes_into_the_fight_beside_its_owner_and_cannot_attack(tables):
    me = with_familiar(hero(tables), tables=tables)
    b = fight(tables, [me], ["bandit"], {0: (2, 4), 1: (9, 4)})
    owl = next(f for f in b.fighters if f.bond is not None)
    owner = b.fighters[0]
    assert owl.bond["kind"] == "familiar" and owl.kind == "fey" and b.gap(owl, owner) <= 1
    assert owl.id in b.order and owl.name == "Wren"
    assert b.attack_options(owl) == [] and not owl.blows
    ids = {o.id for o in actions.options(b, owl)}
    assert "action:help" in ids and "action:dodge" in ids
    assert not any(i.startswith("attack:") for i in ids) and "action:grapple" not in ids


def test_the_familiar_on_auto_helps_a_friend_against_the_foe(tables):
    from realmwalker.rules import tactics

    me = with_familiar(hero(tables, "fighter"), "hawk", tables=tables)
    b = fight(tables, [me], ["bandit"], {0: (4, 4), 1: (5, 4)})
    hawk = next(f for f in b.fighters if f.bond is not None)
    hawk.auto = True
    b.order = [hawk.id] + [i for i in b.order if i != hawk.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(hawk)
    tactics.take_turn(b, hawk)
    foe = next(f for f in b.fighters if f.side != PARTY)
    assert b.gap(hawk, foe) <= 1
    assert any("feints at" in text for text, _ in b.log[-4:]), b.log[-4:]


def test_an_ally_does_not_keep_a_lost_fight_going_and_vanishes_at_nothing(tables):
    me = with_familiar(hero(tables), tables=tables)
    b = fight(tables, [me], ["bandit"], {0: (2, 4), 1: (9, 4)})
    owl = next(f for f in b.fighters if f.bond is not None)
    owner = b.fighters[0]
    b._apply_hp_loss(owl, 50, source=None, cause="test")
    assert owl.state == "dead" and owl.creature.alive is False
    allies.after(b)
    assert me.spells["familiar"]["gone"] is True
    me.spells["familiar"]["gone"] = False
    b2 = fight(tables, [me], ["bandit"], {0: (2, 4), 1: (9, 4)})
    owner = b2.fighters[0]
    owner.hp = 0
    owner.state = "down"
    owner.conditions = {"unconscious": -1, "prone": -1}
    b2._check_end()
    assert b2.outcome == "defeat", "the familiar alone does not keep the fight going"
    assert b2.result().party_dead == []


def test_find_steed_in_a_fight_brings_a_steed_that_acts_after_its_rider(tables):
    me = hero(tables, "cleric", xp=6500)  # (level 5: a slot of level 2)
    b = fight(tables, [me], ["bandit", "bandit"], {0: (2, 4), 1: (10, 4), 2: (10, 6)})
    f = b.fighters[0]
    b.order = [f.id] + [i for i in b.order if i != f.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(f)
    b.cast(f, "find_steed", b.t.spells["find_steed"], None, None, up=1, mod=3, dc=13, bonus=5, mult=1, level=3)
    steed = next(x for x in b.fighters if x.bond is not None)
    assert steed.bond["kind"] == "steed" and steed.bond["level"] == 3
    assert steed.ac() == 13 and steed.max_hp == 35
    assert b.order[b.order.index(f.id) + 1] == steed.id, "the steed takes its turn right after its rider"
    slam = b.attack_options(steed)[0]
    assert slam.bonus == allies.caster_numbers(me, tables)[0]
    assert me.spells["steed"]["level"] == 3


def test_the_steed_gift_life_bond_and_its_rider_death(tables):
    me = hero(tables, "cleric", xp=6500)
    me.spells["steed"] = {"look": "horse", "type": "celestial", "level": 2, "name": "Gloam", "hp": 25, "gone": False,
                          "uses": {}}
    b = fight(tables, [me], ["bandit"], {0: (2, 4), 1: (10, 4)})
    rider = b.fighters[0]
    steed = next(x for x in b.fighters if x.bond is not None)
    steed.bonus = 1
    assert "steed_healing_touch" in b.creature_spells(steed), "a celestial steed's gift: Healing Touch"
    assert steed.bond["picture"] == "riding_horse" and steed.kind == "celestial"
    rider.hp = 5
    steed.hp = 10
    b.cast(rider, "cure_wounds", b.t.spells["cure_wounds"], rider, None, up=0, mod=3, dc=13, bonus=5, mult=1, level=1)
    assert steed.hp > 10, "Life Bond: the steed beside its rider heals as much"
    b._kill(rider, "test")
    assert steed.state == "dead", "the steed vanishes when its rider dies"


def test_find_familiar_on_the_road_and_its_pocket(tables, world):
    from realmwalker.game import allies as road
    from realmwalker.game.divining import Subject
    game = game_with(world, tables, hero(tables))
    me = game.leader
    subs = road.subjects(game, me, "find_familiar")
    owl = next(s for s in subs if s.data.get("form") == "owl" and s.data.get("type") == "fey")
    out = road.cast(game, me, "find_familiar", owl, 1)
    rec = me.spells["familiar"]
    assert rec["form"] == "owl" and rec["name"] and "owl" in " ".join(out)
    away = next(s for s in road.subjects(game, me, "find_familiar") if s.ref == "dismiss")
    road.free_use(game, me, away)
    assert rec["away"] and allies.present(me, "familiar") is None
    back = next(s for s in road.subjects(game, me, "find_familiar") if s.ref == "recall")
    road.free_use(game, me, back)
    assert not rec["away"]
    rec["hp"] = 0
    long_rest(me, game.tables, RNG(3))
    assert rec["hp"] == rec["max_hp"]
    assert isinstance(owl, Subject)


def test_the_steed_is_ridden_by_its_owner_never_sold_and_watch_at_night(tables, world):
    from realmwalker.game import allies as road, mounts

    game = game_with(world, tables, hero(tables, "cleric", xp=6500))
    me = game.leader
    horse = next(s for s in road.subjects(game, me, "find_steed") if s.data == {"look": "horse", "type": "fey",
                                                                                "group": "horse"})
    road.cast(game, me, "find_steed", horse, 2)
    steed = next(a for a in me.animals if a.get("summoned"))
    assert mounts.mount_of(game, me) is steed
    animals = game.tables.economy["animals"]
    assert animals["otherworldly_steed"].get("summoned")
    with_familiar(me, tables=game.tables)
    assert road.watcher(game) is not None
    road.died(game, me)
    assert not any(a.get("summoned") for a in me.animals)



def test_the_familiar_is_drawn_following_on_the_close_up_map(make_app):
    from tests.test_app_ui import render, start_small_world

    app = make_app()
    gs = start_small_world(app)
    me = gs.game.leader
    with_familiar(me, "cat", tables=gs.game.tables)
    gs.enter()
    for _ in range(3):
        render(app)
    assert app.error_count == 0


def test_the_battle_screen_plays_a_familiar_and_a_steed(make_app, world):
    import tcod

    from realmwalker.game import fight
    from realmwalker.game.encounters import PendingEncounter
    from realmwalker.game.state import new_game
    from realmwalker.ui import widgets
    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.battle import BattleScreen

    app = make_app()
    me = with_familiar(hero(app.tables, "cleric", xp=6500), "raven", "fiend", tables=app.tables)
    me.spells["steed"] = {"look": "dire_wolf", "type": "fiend", "level": 2, "name": "Ember", "hp": 25, "gone": False,
                          "uses": {}}
    game = new_game(copy.deepcopy(world), app.tables, me)
    app.start_game(game)
    game.survival = False
    rng = RNG(5, "band")
    game.encounter = PendingEncounter("test", [spawn(app.tables, "bandit", rng, i + 1) for i in range(2)],
                                      "They come.", False, "")
    b = fight.encounter_fight(game, False)
    game.encounter = None
    raven = next(f for f in b.fighters if f.bond is not None and f.bond["kind"] == "familiar")
    steed = next(f for f in b.fighters if f.bond is not None and f.bond["kind"] == "steed")
    assert steed.bond["picture"] == "dire_wolf" and steed.kind == "fiend"
    screen = BattleScreen(app, game)
    app.push(screen)
    for who in (raven, steed):
        b.order = [who.id] + [i for i in b.order if i != who.id]
        b.turn, b.turn_started = 0, True
        b._start_of_turn(who)
        assert b.pending_party() is who, "the player commands an ally like a member of the party"
        for key in ("tab", "escape", "a", "escape"):
            app.handle_event(KeyEvent(key))
        for size in ((80, 30), (160, 45)):
            screen.render(widgets.Canvas(tcod.console.Console(*size, order="F")))
    assert app.error_count == 0
    b.outcome = "victory"
    fight.finish_battle(game)
    assert me.spells["familiar"]["gone"] is False and me.spells["steed"]["hp"] > 0
