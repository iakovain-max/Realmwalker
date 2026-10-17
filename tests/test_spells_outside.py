"""Spells outside battle, part E.1 (Expansion 3): healing (Aid, Regenerate, Remove Curse), return from death
(Revivify, Raise Dead, Reincarnate, Resurrection, True Resurrection, Gentle Repose), food and the body (Goodberry,
Create or Destroy Water, Purify Food and Drink, Create Food and Water, Heroes' Feast), shelter and watch (Alarm,
Leomund's Tiny Hut, Rope Trick, Mordenkainen's Faithful Hound and Magnificent Mansion). Each is cast where it is
used: in a real fight, over a body, at a camp in the night, on a party with nothing to eat."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import fight, magic, revival, spellwork
from realmwalker.game.camp import make_camp
from realmwalker.game.encounters import PendingEncounter
from realmwalker.game.state import new_game
from realmwalker.rules import health
from realmwalker.rules import spells as sp
from realmwalker.rules.combat import PARTY, Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.inventory import add_item, equip, unequip
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


def hero(tables, cls, xp=0, seed=1, race="human"):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race(race)
    b.set_class(cls)
    b.set_background("sage")
    c = b.build()
    if xp:
        award_xp(c, xp, tables, RNG(seed), auto=True)
    return c


def companion(tables, cls="fighter", xp=0, seed=2):
    c = hero(tables, cls, xp, seed)
    c.is_player = False
    c.companion = {"loyalty": 60, "wage": 0}
    return c


def game_with(world, tables, *party):
    game = new_game(copy.deepcopy(world), tables, party[0])
    for c in party[1:]:
        game.party.append(c)
    game.survival = False
    from realmwalker.game import pack

    pack.sync(game)
    return game


def prepare(c, tables, *sids):
    c.spells["prepared"] = list(dict.fromkeys(list(sids) + list(c.spells.get("prepared", []))))
    for s in sids:
        assert s in sp.known_spells(c, tables), f"{s} could not be prepared by a {c.cls} of level {c.level}"


def kill(game, c):
    c.hp = 0
    c.alive = False
    game.bury_the_dead()


# ---------------------------------------------------------------------------- healing
def test_aid_on_the_road_raises_the_maximum_for_eight_hours(world, tables):
    cleric = hero(tables, "cleric", 6500)  # level 5: third-level slots
    pal = companion(tables)
    game = game_with(world, tables, cleric, pal)
    prepare(cleric, tables, "aid")
    game.survival = True  # (what wears off wears off as the body lives through the hours)
    top, top2 = cleric.max_hp, pal.max_hp
    pal.hp = pal.max_hp - 3
    assert magic.road_problem(game, cleric, "aid") is None
    out = magic.cast_on_road(game, cleric, "aid", slot_level=3)  # (a level 3 slot: +10)
    assert any("+10 hit points" in line for line in out), out
    assert (cleric.max_hp, pal.max_hp) == (top + 10, top2 + 10)
    assert pal.hp == top2 + 7
    game.pass_time(8 * 60 + 1, "rest")
    assert (cleric.max_hp, pal.max_hp) == (top, top2)
    assert "spell_hp:aid" not in cleric.effects


def test_aid_in_a_real_fight_stands_up_the_fallen_and_outlives_the_fight(tables):
    cleric = hero(tables, "cleric", 2700)
    prepare(cleric, tables, "aid")
    friend = hero(tables, "fighter", 0, 3)
    b = Battle(tables, [cleric, friend], [spawn(tables, "wolf", RNG(1, "w"), 1)], Env(), RNG(1, "b"))
    b.start("Test fight.")
    me, down = b.side(PARTY)
    down.hp = 0
    down.state = "down"
    b.order = [me.id] + [x for x in b.order if x != me.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    assert "aid" in [s for s, ok, _ in b.spell_options(me) if ok]
    from realmwalker.rules.engine import estimates

    assert estimates.spell_value(b, me, "aid").total(care=4.0) > 0.5, "the Auto sees nothing in Aid"
    assert b.do_cast(me, "aid")
    assert down.state == "fighting" and friend.hp == 5
    assert friend.effects.get("spell_hp:aid") == 5
    assert "aid" in sp.lasting(friend, tables)


def test_regenerate_grows_back_what_was_cut_off(world, tables):
    cleric = hero(tables, "cleric", 120000)  # level 13: seventh-level slots
    hurt = companion(tables)
    hurt.injuries.append("lost_left_arm")
    hurt.hp = 3
    game = game_with(world, tables, cleric, hurt)
    prepare(cleric, tables, "regenerate")
    assert magic.road_problem(game, cleric, "regenerate", hurt) is None
    out = magic.cast_on_road(game, cleric, "regenerate", hurt)
    assert "lost_left_arm" not in hurt.injuries and hurt.hp == hurt.max_hp, out
    assert spellwork.problem(game, cleric, "regenerate", hurt) == "they are whole already"


def test_remove_curse_loosens_a_cursed_thing_until_it_is_put_on_again(world, tables):
    cleric = hero(tables, "cleric", 6500)
    game = game_with(world, tables, cleric)
    it = add_item(cleric, tables.items, "plain_ring")
    it.magic = {"rarity": "rare", "kind": "ring", "props": [], "identified": True, "cursed": True,
                "curse": {"text": "It saps the will."}}
    ok, _ = equip(cleric, tables.items, it.uid)
    assert ok and unequip(cleric, cleric.slot_of(it.uid)) is None  # (it clings)
    assert magic.road_problem(game, cleric, "remove_curse", cleric) == "not prepared (p prepares it)"
    prepare(cleric, tables, "remove_curse")
    out = magic.cast_on_road(game, cleric, "remove_curse", cleric)
    assert any("loosens" in line for line in out), out
    slot = cleric.slot_of(it.uid)
    assert unequip(cleric, slot) is not None
    equip(cleric, tables.items, it.uid)
    assert unequip(cleric, cleric.slot_of(it.uid)) is None  # (put on again, it takes hold again)


# ---------------------------------------------------------------------------- return from death
def test_a_fallen_companion_is_carried_and_raised_with_the_toll(world, tables):
    cleric = hero(tables, "cleric", 64000)  # level 9: fifth-level slots
    friend = companion(tables)
    game = game_with(world, tables, cleric, friend)
    prepare(cleric, tables, "raise_dead")
    kill(game, friend)
    assert friend not in game.party and revival.body_of(game, friend) is not None
    game.pass_time(3 * 24 * 60, "rest")  # three days on the road with the body
    assert revival.body_of(game, friend) is not None
    assert magic.road_problem(game, cleric, "raise_dead", friend) == "needs a diamond worth 500+ GP"
    add_item(cleric, tables.items, "fine_diamond")
    assert friend in magic.road_targets(game, cleric, "raise_dead")
    out = magic.cast_on_road(game, cleric, "raise_dead", friend)
    assert friend.alive and friend.hp == 1 and friend in game.party, out
    assert not any(it.def_id == "fine_diamond" for it in cleric.inventory)
    assert friend.effects.get(health.DEATH_TOLL) == 4 and health.penalty(friend, tables) <= -4
    long_rest(friend, tables, RNG(1))
    assert friend.effects.get(health.DEATH_TOLL) == 3
    game.pass_time(60, "rest")
    assert friend.effects.get(health.DEATH_TOLL) == 3  # (the hours do not wear it down)


def test_a_body_nobody_could_raise_is_buried_at_once(world, tables):
    lead = hero(tables, "fighter")
    friend = companion(tables)
    game = game_with(world, tables, lead, friend)
    kill(game, friend)
    assert not game.fallen


def test_a_body_is_buried_after_ten_days_unless_gentle_repose_keeps_it(world, tables):
    cleric = hero(tables, "cleric", 64000)
    a, b_ = companion(tables, seed=4), companion(tables, seed=5)
    game = game_with(world, tables, cleric, a, b_)
    prepare(cleric, tables, "gentle_repose")
    kill(game, a)
    kill(game, b_)
    assert len(game.fallen) == 2
    out = magic.cast_on_road(game, cleric, "gentle_repose", b_)
    assert any("kept from decay" in line for line in out), out
    game.pass_time(11 * 24 * 60, "rest")
    assert revival.body_of(game, a) is None and revival.body_of(game, b_) is not None
    assert revival.dead_for(game, revival.body_of(game, b_)) < 2 * 24 * 60


def test_revivify_after_a_fight_by_a_companion_in_the_last_minute(world, tables):
    lead = hero(tables, "fighter")
    priest = companion(tables, "cleric", 6500)  # level 5: Revivify
    friend = companion(tables, seed=6)
    game = game_with(world, tables, lead, priest, friend)
    prepare(priest, tables, "revivify")
    add_item(priest, tables.items, "diamond")
    b = Battle(tables, [lead, priest, friend], [spawn(tables, "wolf", RNG(1, "w"), 1)], Env(), RNG(1, "b"))
    b.start("Test fight.")
    game.battle = b
    f = next(x for x in b.side(PARTY) if x.char is friend)
    f.state, f.died_round, friend.alive, friend.hp = "dead", b.round, False, 0
    for e in b.enemies_of(b.side(PARTY)[0]):
        e.hp, e.state = 0, "dead"
    after = fight.finish_battle(game)
    assert friend.alive and friend in game.party, after.notes
    assert any("Revivify" in n for n in after.notes)


def test_a_companion_calls_the_leader_back(world, tables):
    lead = hero(tables, "fighter")
    priest = companion(tables, "cleric", 6500)
    game = game_with(world, tables, lead, priest)
    prepare(priest, tables, "revivify")
    add_item(priest, tables.items, "diamond")
    lead.hp = 0
    lead.death_cause = "killed by a fall"
    from realmwalker.game import survival

    survival.check_death(game, lead)
    assert lead.alive and lead.hp == 1 and game.over is None
    lead.hp = 0
    lead.death_cause = "killed by a fall"
    survival.check_death(game, lead)  # (no diamond left: the end)
    assert game.over is not None


def test_reincarnate_and_true_resurrection(world, tables):
    cleric = hero(tables, "cleric", 64000)
    a, b_ = companion(tables, seed=4), companion(tables, seed=5)
    game = game_with(world, tables, cleric, a, b_)
    prepare(cleric, tables, "raise_dead")  # (someone who could raise them: the bodies are kept)
    a.injuries.append("lost_right_leg")
    kill(game, a)
    kill(game, b_)
    # No druid yet: Reincarnate comes by a scroll (or a druid's hands, later); its casting is the same.
    out = revival.raise_body(game, cleric, "reincarnate", revival.body_of(game, a), RNG(5))
    assert a.alive and a.hp == a.max_hp and "lost_right_leg" not in a.injuries, out
    assert any("body" in line for line in out) and a in game.party
    b_.diseases.append({"id": "flux", "phase": "sick"})
    out = revival.raise_body(game, cleric, "true_resurrection", revival.body_of(game, b_), RNG(6))
    assert b_.alive and b_.hp == b_.max_hp and not b_.diseases and not b_.effects.get(health.DEATH_TOLL), out


def test_spells_of_return_are_never_offered_in_a_fight_but_revivify_is(tables):
    cleric = hero(tables, "cleric", 64000)
    prepare(cleric, tables, "raise_dead", "revivify", "aid")
    add_item(cleric, tables.items, "fine_diamond")
    b = Battle(tables, [cleric], [spawn(tables, "wolf", RNG(1, "w"), 1)], Env(), RNG(1, "b"))
    b.start("Test fight.")
    opts = {s: (ok, why) for s, ok, why in b.spell_options(b.side(PARTY)[0])}
    assert opts["raise_dead"][0] is False and "60 minutes" in opts["raise_dead"][1]
    assert "raise_dead" not in sp.wish_copies(tables)


# ---------------------------------------------------------------------------- food and the body
def test_goodberries_feed_heal_and_are_gone_in_a_day(world, tables):
    ranger = hero(tables, "cleric", 0)
    game = game_with(world, tables, ranger)
    game.survival = True
    out = spellwork.cast(game, ranger, "goodberry", None, 1)
    berries = [it for it in ranger.inventory if it.def_id == "goodberry"]
    assert berries and berries[0].qty == 10, out
    from realmwalker.game import survival

    ranger.hp, ranger.hunger = ranger.max_hp - 2, 60.0
    survival.eat_item(game, ranger, berries[0])
    assert ranger.hp == ranger.max_hp - 1 and ranger.hunger < 60
    game.pass_time(25 * 60, "rest")
    assert not any(it.def_id == "goodberry" for it in ranger.inventory)


def test_water_food_and_purifying(world, tables):
    cleric = hero(tables, "cleric", 6500)
    game = game_with(world, tables, cleric)
    prepare(cleric, tables, "create_or_destroy_water", "purify_food_and_drink", "create_food_and_water")
    skins = [it for it in cleric.inventory if sp and tables.items.get(it.def_id).get("container", {}).get("liquid")]
    if not skins:
        skins = [add_item(cleric, tables.items, "waterskin")]
    for s in skins:
        s.fill, s.fill_kind = 0.0, ""
    assert magic.road_problem(game, cleric, "purify_food_and_drink") == "nothing you carry has turned or gone foul"
    magic.cast_on_road(game, cleric, "create_or_destroy_water")
    assert all(s.fill > 0 and s.fill_kind == "clean" for s in skins)
    meat = add_item(cleric, tables.items, "rations", made_at=game.world.time - 100 * 24 * 60)
    skins[0].fill_kind = "marsh"
    assert magic.road_problem(game, cleric, "purify_food_and_drink") is None
    out = magic.cast_on_road(game, cleric, "purify_food_and_drink")  # (a ritual: no slot)
    assert meat.made_at >= game.world.time - 20 and skins[0].fill_kind == "clean", out
    magic.cast_on_road(game, cleric, "create_food_and_water")
    food = next(it for it in cleric.inventory if it.def_id == "conjured_food")
    assert food.qty == 15


def test_heroes_feast_lasts_a_day_and_keeps_poison_and_fear_off_in_a_fight(world, tables):
    cleric = hero(tables, "cleric", 100000)  # level 13: sixth-level slots
    game = game_with(world, tables, cleric, companion(tables))
    prepare(cleric, tables, "heroes_feast")
    assert magic.road_problem(game, cleric, "heroes_feast") == "needs a gem-encrusted bowl worth 1"
    add_item(cleric, tables.items, "feast_bowl")
    top = cleric.max_hp
    start = game.world.time
    game.survival = True
    magic.cast_on_road(game, cleric, "heroes_feast")
    assert game.world.time - start >= 70
    assert cleric.max_hp > top and cleric.hunger < 5
    b = Battle(tables, [cleric], [spawn(tables, "wolf", RNG(1, "w"), 1)], Env(), RNG(1, "b"))
    b.start("Test fight.")
    me = b.side(PARTY)[0]
    from realmwalker.rules.engine import query

    assert query.defences(me, "poison") == "resist"
    assert any("poisoned" in bf.get("immune", []) for bf in me.buffs)
    game.pass_time(25 * 60, "rest")
    assert cleric.max_hp == top


# ---------------------------------------------------------------------------- shelter and watch
def _night_wolves(tables):
    rng = RNG(3, "night")
    return PendingEncounter("wolves", [spawn(tables, "wolf", rng, i + 1) for i in range(2)], "Wolves.", False, "a pack")


def test_the_tiny_hut_turns_away_the_night_and_keeps_the_weather_out(world, tables, monkeypatch):
    bard = hero(tables, "wizard", 6500)
    bard.spells.setdefault("spellbook", []).append("leomunds_tiny_hut")
    game = game_with(world, tables, bard)
    monkeypatch.setattr("realmwalker.game.encounters.roll_encounter", lambda *a: _night_wolves(tables))
    magic.cast_on_road(game, bard, "leomunds_tiny_hut")  # (a ritual: from the book, no slot)
    assert spellwork.sheltering(game)
    from realmwalker.game import survival

    assert survival.environment(game, bard, "sleep").sheltered
    notes = fight.rest(game, "long")
    assert game.encounter is None and any("no way in" in n for n in notes), notes


def test_the_alarm_and_the_hound_wake_the_camp(world, tables, monkeypatch):
    wiz = hero(tables, "wizard", 6500)  # level 5
    wiz.spells.setdefault("spellbook", []).append("alarm")
    game = game_with(world, tables, wiz)
    monkeypatch.setattr("realmwalker.game.encounters.roll_encounter", lambda *a: _night_wolves(tables))
    magic.cast_on_road(game, wiz, "alarm")
    notes = fight.rest(game, "long")
    assert game.encounter is not None and not game.encounter.asleep, notes
    assert any("alarm" in n for n in notes)


def test_rope_trick_lets_you_rest_with_enemies_hunting(world, tables):
    wiz = hero(tables, "wizard", 900)  # level 3
    game = game_with(world, tables, wiz)
    camp = make_camp(game)
    camp.wards["rope"] = {"until": game.world.time + 60, "dc": 13, "by": wiz.name}
    assert spellwork.hidden(game, "short") and not spellwork.hidden(game, "long")


def test_a_companion_casts_a_ritual_ward_before_sleeping(world, tables, monkeypatch):
    lead = hero(tables, "fighter")
    wiz = companion(tables, "wizard", 6500)
    game = game_with(world, tables, lead, wiz)
    if "leomunds_tiny_hut" not in wiz.spells.get("spellbook", []):
        wiz.spells.setdefault("spellbook", []).append("leomunds_tiny_hut")
    monkeypatch.setattr("realmwalker.game.encounters.roll_encounter", lambda *a: None)
    notes = fight.rest(game, "long")
    assert any("dome" in n for n in notes), notes


def test_a_companion_conjures_food_when_there_is_none(world, tables):
    lead = hero(tables, "fighter")
    priest = companion(tables, "cleric", 6500)
    game = game_with(world, tables, lead, priest)
    prepare(priest, tables, "create_food_and_water")
    for c in (lead,):
        for it in [it for it in c.inventory if tables.items.get(it.def_id).get("food")]:
            c.inventory.remove(it)
    lead.hunger = 70.0
    from realmwalker.game import survival

    survival.feed(game, lead)
    assert lead.hunger < 70.0
    assert any(it.def_id == "conjured_food" for it in lead.inventory)
