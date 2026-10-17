"""The spell catalogue's third wave (Expansion 3 D.3, levels 6 and 7): the new kernel pieces doing what their cards say
in real fights - a bolt that leaps, dust, a withered maximum, the three saves against stone, the Globe's ward, Heal,
Otto's dance, true sight, walls of ice and thorns, the pillar of celestial light, Divine Word, the forcecage, Plane
Shift's banishing touch, shared temporary hit points, Prismatic Spray's rays, Reverse Gravity and Conjure Fey."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules.combat import Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import estimates
from realmwalker.rules.progression import award_xp
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


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


def fight(tables, party, foes, spots, seed=1, env=None):
    rng = RNG(seed, "foes")
    crs = [spawn(tables, d, rng, i + 1) for i, d in enumerate(foes)]
    b = Battle(tables, party, crs, env or Env(), RNG(seed, "battle"), spots=spots)
    b.start()
    return b


def my_turn(b, f):
    b.order = [f.id] + [x for x in b.order if x != f.id]
    b.turn = 0
    b.turn_started = True
    b._start_of_turn(f)


def cast(b, f, sid, target=None, point=None, *, dc=30, level=None, up=0):
    sp = b.t.spells[sid]
    b.cast(f, sid, sp, target, point, up=up, mod=4, dc=dc, bonus=8, mult=1, level=(level or sp["level"]) + up)


def test_chain_lightning_leaps_to_foes_near_the_first_and_no_further(tables):
    b = fight(tables, [hero(tables)], ["bandit", "bandit", "bandit", "bandit"],
              {0: (1, 4), 1: (6, 4), 2: (8, 4), 3: (6, 6), 4: (15, 8)})
    me, first, near1, near2, far = b.fighters
    for x in (first, near1, near2, far):
        x.creature.hp = x.creature.max_hp = 200
    my_turn(b, me)
    cast(b, me, "chain_lightning", first)
    assert all(x.hp < 200 for x in (first, near1, near2)), "the bolt leaps to those within 30 feet of the first"
    assert far.hp == 200, "and no further"


def test_disintegrate_leaves_dust_that_nothing_brings_back(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (5, 4)})
    me, bandit = b.fighters
    my_turn(b, me)
    cast(b, me, "disintegrate", bandit)
    assert bandit.state == "dead" and bandit.__dict__.get("dust")


def test_harm_withers_the_hit_point_maximum(tables):
    b = fight(tables, [hero(tables)], ["ogre" if "ogre" in tables.creatures.defs else "bandit"], {0: (2, 4), 1: (5, 4)})
    me, foe = b.fighters
    foe.creature.hp = foe.creature.max_hp = 200
    my_turn(b, me)
    cast(b, me, "harm", foe)
    assert foe.max_hp < 200 and foe.max_hp == max(1, 200 - (200 - foe.hp))
    b._heal(foe, 500)
    assert foe.hp == foe.max_hp < 200, "the lost maximum cannot be healed back in this fight"


def test_flesh_to_stone_turns_a_foe_to_stone_after_three_failed_saves(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (6, 4)})
    me, bandit = b.fighters
    my_turn(b, me)
    cast(b, me, "flesh_to_stone", bandit, dc=40)
    assert "restrained" in bandit.conditions
    for _ in range(3):
        b._end_of_turn(bandit)
    assert "petrified" in bandit.conditions and "restrained" not in bandit.conditions
    b._end_concentration(me, quiet=True)
    assert "petrified" not in bandit.conditions, "the stone lasts as long as the spell"


def test_flesh_to_stone_lets_go_after_three_saves(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (6, 4)})
    me, bandit = b.fighters
    my_turn(b, me)
    cast(b, me, "flesh_to_stone", bandit, dc=40)
    se = next(se for se in bandit.save_ends if se.get("tally") is not None)
    se["dc"] = -10  # (every later save succeeds)
    for _ in range(3):
        b._end_of_turn(bandit)
    assert "restrained" not in bandit.conditions and "petrified" not in bandit.conditions


def test_the_globe_keeps_lesser_spells_out_and_lets_greater_ones_in(tables):
    b = fight(tables, [hero(tables), hero(tables, "fighter", seed=2)], ["bandit"],
              {0: (4, 4), 1: (5, 4), 2: (12, 4)})
    me, friend, foe = b.fighters
    my_turn(b, me)
    cast(b, me, "globe_of_invulnerability")
    assert any(bf.get("spell_ward") == 6 for bf in friend.buffs)
    hp = friend.hp
    cast(b, foe, "fireball", point=(friend.x, friend.y), dc=40)
    assert friend.hp == hp and me.hp == me.max_hp, "a level 3 spell from outside cannot touch them"
    assert estimates.spell_value(b, foe, "fireball", point=(friend.x, friend.y)).total() <= 0.5
    cast(b, foe, "finger_of_death", friend, dc=40)
    assert friend.hp < hp, "a level 7 spell passes"


def test_heal_restores_seventy_and_ten_more_a_slot_and_ends_poison(tables):
    b = fight(tables, [hero(tables, "cleric"), hero(tables, "fighter", seed=2, xp=265000)], ["bandit"],
              {0: (2, 4), 1: (3, 5), 2: (12, 4)})  # (level 18: no Boon of Fortitude adding to healing)
    me, friend, _ = b.fighters
    friend.hp = 1
    friend.conditions["poisoned"] = -1
    my_turn(b, me)
    cast(b, me, "heal", friend, up=1)
    assert friend.hp == min(friend.max_hp, 81)
    assert "poisoned" not in friend.conditions


def test_ottos_dance_holds_a_foe_in_place_and_it_spends_its_action_to_stop(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (3, 4)})
    me, bandit = b.fighters
    my_turn(b, me)
    cast(b, me, "ottos_irresistible_dance", bandit, dc=40)
    assert bandit.buff_value("dancing") and bandit.speed == 0
    adv, dis, _ = b._adv_dis(me, bandit, b.attack_options(me)[0])
    assert adv
    bandit.action = 1
    from realmwalker.rules.engine import marks

    marks.dancing_turn(b, bandit)
    assert bandit.action == 0 and bandit.buff_value("dancing"), "a failed save: it dances on"


def test_true_seeing_sees_the_invisible(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (6, 4)})
    me, bandit = b.fighters
    bandit.conditions["invisible"] = -1
    assert not b.can_see(me, bandit)
    my_turn(b, me)
    cast(b, me, "true_seeing", me)
    assert b.can_see(me, bandit)


def test_a_wall_of_ice_freezes_whoever_it_rises_beside_and_stands_until_the_spell_ends(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (1, 4), 1: (8, 4)})
    me, bandit = b.fighters
    bandit.creature.hp = bandit.creature.max_hp = 200
    my_turn(b, me)
    cast(b, me, "wall_of_ice", point=(8, 4), dc=40)
    assert bandit.hp < 200
    z = next(z for z in b.zones if z.kind == "icewall")
    sq = next(iter(z.cells))
    assert not b.field.passable(*sq)
    b._end_concentration(me, quiet=True)
    assert b.field.passable(*sq)


def test_the_wall_of_thorns_tears_at_whoever_walks_into_it(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (1, 4), 1: (12, 8)})
    me, bandit = b.fighters
    bandit.creature.hp = bandit.creature.max_hp = 200
    my_turn(b, me)
    cast(b, me, "wall_of_thorns", point=(12, 4), dc=40)
    z = next(z for z in b.zones if z.kind == "thorns")
    sq = sorted(z.cells)[len(z.cells) // 2]
    bandit.x, bandit.y = sq
    b._zones_on(bandit, start=True)
    assert bandit.hp < 200


def test_conjure_celestial_heals_friends_and_sears_foes(tables):
    b = fight(tables, [hero(tables, "cleric"), hero(tables, "fighter", seed=2, xp=355000)], ["bandit"],
              {0: (1, 4), 1: (6, 4), 2: (7, 4)})
    me, friend, bandit = b.fighters
    friend.hp = 5
    bandit.creature.hp = bandit.creature.max_hp = 200
    my_turn(b, me)
    cast(b, me, "conjure_celestial", point=(6, 4), dc=40)
    assert friend.hp > 5 and bandit.hp < 200


def test_divine_word_kills_the_weak_stuns_the_stronger_and_spares_the_strong(tables):
    b = fight(tables, [hero(tables, "cleric")], ["bandit", "bandit", "bandit"], {0: (4, 4), 1: (5, 4), 2: (3, 4), 3: (4, 6)})
    me, weak, middling, strong = b.fighters
    weak.creature.hp = 10
    middling.creature.hp = middling.creature.max_hp = 25
    strong.creature.hp = strong.creature.max_hp = 90
    my_turn(b, me)
    cast(b, me, "divine_word", dc=40)
    assert weak.state == "dead"
    assert {"blinded", "deafened", "stunned"} <= set(middling.conditions)
    assert not {"blinded", "deafened", "stunned"} & set(strong.conditions)


def test_divine_word_sends_a_fiend_home_for_good(tables):
    fiend = next((cid for cid, c in tables.creatures.defs.items() if c.get("kind") == "fiend"), None)
    if fiend is None:
        pytest.skip("no fiend in the bestiary")
    b = fight(tables, [hero(tables, "cleric")], [fiend], {0: (4, 4), 1: (5, 4)})
    me, foe = b.fighters
    foe.creature.hp = foe.creature.max_hp = 300
    my_turn(b, me)
    cast(b, me, "divine_word", dc=40)
    assert foe.state == "fled" and foe.__dict__.get("banished_home")
    assert b.outcome == "victory"


def test_the_forcecage_seals_those_in_the_box_and_dispel_magic_cannot_open_it(tables):
    b = fight(tables, [hero(tables, xp=355000)], ["bandit", "bandit"], {0: (1, 4), 1: (6, 4), 2: (12, 8)})
    me, caged, free = b.fighters
    my_turn(b, me)
    cast(b, me, "forcecage", point=(6, 4))
    assert caged.state == "away" and caged.away["why"] == "cage" and free.state == "fighting"
    from realmwalker.rules.engine.effects import held_spells

    assert not held_spells(b, caged), "Dispel Magic finds nothing it can end"
    b._end_concentration(me, quiet=True)
    assert caged.state == "fighting" and (caged.x, caged.y) == (6, 4)


def test_plane_shift_banishes_a_foe_for_good_with_a_touch(tables):
    hits = 0
    for seed in range(12):
        b = fight(tables, [hero(tables, "cleric")], ["bandit"], {0: (2, 4), 1: (3, 4)}, seed=seed)
        me, bandit = b.fighters
        my_turn(b, me)
        hp = bandit.hp
        cast(b, me, "plane_shift", bandit, dc=40)
        assert bandit.hp == hp, "the touch itself does no harm"
        if bandit.state == "fled":
            hits += 1
            assert bandit.__dict__.get("banished_home") and b.outcome == "victory"
    assert hits >= 6


def test_power_word_fortify_shares_its_hundred_and_twenty(tables):
    b = fight(tables, [hero(tables, "cleric"), hero(tables, "fighter", seed=2), hero(tables, "rogue", seed=3)],
              ["bandit"], {0: (2, 4), 1: (3, 4), 2: (2, 5), 3: (12, 4)})
    party = b.fighters[:3]
    my_turn(b, party[0])
    cast(b, party[0], "power_word_fortify")
    assert [x.temp_hp for x in party] == [40, 40, 40]


def test_prismatic_spray_strikes_each_foe_with_a_ray(tables):
    seen = set()
    for seed in range(6):
        b = fight(tables, [hero(tables)], ["bandit", "bandit", "bandit"], {0: (1, 4), 1: (4, 4), 2: (5, 3), 3: (5, 5)},
                  seed=seed)
        me, *foes = b.fighters
        for x in foes:
            x.creature.hp = x.creature.max_hp = 300
        my_turn(b, me)
        cast(b, me, "prismatic_spray", point=(6, 4), dc=40)
        for x in foes:
            hurt = x.hp < 300
            held = bool({"restrained", "blinded"} & set(x.conditions))
            assert hurt or held or x.state != "fighting", "every ray does something on a failed save"
            seen.add("hurt" if hurt else "held")
    assert seen == {"hurt", "held"}


def test_reverse_gravity_lifts_foes_and_drops_them_when_it_ends(tables):
    b = fight(tables, [hero(tables)], ["bandit", "bandit"], {0: (1, 4), 1: (11, 4), 2: (12, 5)})
    me, a, c = b.fighters
    for x in (a, c):
        x.creature.hp = x.creature.max_hp = 200
    my_turn(b, me)
    cast(b, me, "reverse_gravity", point=(12, 4), dc=40)
    assert a.z == 100 and c.z == 100 and a.speed == 0 and me.z == 0
    b._check_end()
    assert a.z == 100, "it hangs there while the spell holds"
    b._end_concentration(me, quiet=True)
    assert a.z == 0 and a.hp < 200 and "prone" in a.conditions


def test_reverse_gravity_below_ground_strikes_the_ceiling(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (1, 4), 1: (8, 4)}, env=Env(place="underground"))
    me, a = b.fighters
    a.creature.hp = a.creature.max_hp = 200
    my_turn(b, me)
    cast(b, me, "reverse_gravity", point=(8, 4), dc=40)
    assert a.z == 20 and a.hp < 200


def test_conjure_fey_strikes_and_frightens(tables):
    for seed in range(8):
        b = fight(tables, [hero(tables)], ["bandit"], {0: (1, 4), 1: (8, 4)}, seed=seed)
        me, bandit = b.fighters
        bandit.creature.hp = bandit.creature.max_hp = 200
        my_turn(b, me)
        cast(b, me, "conjure_fey", point=(7, 4))
        if bandit.hp < 200:
            assert "frightened" in bandit.conditions
            return
    pytest.fail("the spirit never hit in eight tries")


def test_mass_suggestion_reaches_many_foes(tables):
    b = fight(tables, [hero(tables)], ["bandit"] * 5, {0: (1, 4), 1: (5, 4), 2: (6, 4), 3: (5, 6), 4: (6, 6), 5: (7, 5)})
    me, *foes = b.fighters
    my_turn(b, me)
    cast(b, me, "mass_suggestion", foes[0], dc=40)
    assert all("incapacitated" in x.conditions for x in foes)
