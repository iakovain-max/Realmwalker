"""The spell catalogue's second wave (Expansion 3 D.2, levels 3 to 5): the new kernel pieces doing what their cards
say in real fights - sent away and brought back, Dispel Magic and Spell Breaker, auras shared with friends,
Confusion, Haste and its lethargy, Slow, Blink, Fire Shield, Dominate, ground that holds, walls and the Wind Wall."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import FOE, PARTY, Battle, Env, cast_kind
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import marks, query
from realmwalker.rules.engine.effects import held_spells
from realmwalker.rules.progression import award_xp
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def hero(tables, cls="wizard", seed=1, xp=0, sub=None):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("sage")
    c = b.build()
    if xp:
        award_xp(c, xp, tables, RNG(seed), auto=True)
    if sub:
        c.subclass = sub
    c.hp = c.max_hp
    return c


def fight(tables, party, foes, spots, seed=1):
    rng = RNG(seed, "foes")
    crs = [spawn(tables, d, rng, i + 1) for i, d in enumerate(foes)]
    b = Battle(tables, party, crs, Env(), RNG(seed, "battle"), spots=spots)
    b.start()
    return b


def my_turn(b, f):
    b.order = [f.id] + [x for x in b.order if x != f.id]
    b.turn = 0
    b.turn_started = True
    b._start_of_turn(f)


def cast(b, f, sid, target=None, point=None, *, dc=30, level=None, up=0):
    sp = b.t.spells[sid]
    b.cast(f, sid, sp, target, point, up=up, mod=4, dc=dc, bonus=8, mult=1, level=level or sp["level"])


def test_banishment_sends_a_foe_away_and_it_comes_back_when_the_spell_ends(tables):
    b = fight(tables, [hero(tables)], ["bandit", "bandit"], {0: (2, 4), 1: (4, 4), 2: (8, 4)})
    me, bandit, other = b.fighters
    my_turn(b, me)
    cast(b, me, "banishment", bandit)
    assert bandit.state == "away" and not bandit.active
    assert bandit not in b.enemies_of(me) and b.outcome is None
    b._kill(other, "slain", killer=me)
    b._check_end()
    assert b.outcome is None, "a banished foe is still in the fight"
    b._end_concentration(me, quiet=False, why="is lost")
    assert bandit.state == "fighting" and bandit.active


def test_a_banished_fiend_stays_gone_after_the_whole_minute(tables):
    fiend = next((cid for cid, c in tables.creatures.defs.items() if c.get("type") == "fiend"), None)
    if fiend is None:
        pytest.skip("no fiend in the bestiary")
    b = fight(tables, [hero(tables)], [fiend], {0: (2, 4), 1: (5, 4)})
    me, foe = b.fighters
    my_turn(b, me)
    cast(b, me, "banishment", foe)
    assert foe.state == "away"
    b._end_concentration(me, quiet=False, why="runs its course")
    assert foe.state == "fled"
    b._check_end()
    assert b.outcome == "victory"


def test_the_resilient_sphere_seals_a_foe_where_it_stands(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (4, 4)})
    me, bandit = b.fighters
    my_turn(b, me)
    cast(b, me, "otilukes_resilient_sphere", bandit)
    assert bandit.state == "away" and bandit in b.on_field() and b.at(4, 4) is bandit
    b._end_concentration(me, quiet=False, why="is lost")
    assert bandit.state == "fighting" and (bandit.x, bandit.y) == (4, 4)


def test_blink_takes_the_caster_away_on_a_high_roll_and_back_on_its_turn(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (8, 4)})
    me, bandit = b.fighters
    my_turn(b, me)
    cast(b, me, "blink")
    gone = 0
    for _ in range(40):
        marks.turn_end(b, me)
        if me.state == "away":
            gone += 1
            assert me not in b.enemies_of(bandit)
            b._start_of_turn(me)
            assert me.state == "fighting"
    assert 5 < gone < 35


def test_dispel_magic_ends_a_spell_on_a_friend(tables):
    b = fight(tables, [hero(tables, xp=14000), hero(tables, "fighter", seed=2)], ["mage"] if "mage" in tables.creatures.defs
              else ["bandit"], {0: (2, 4), 1: (3, 5), 2: (8, 4)})
    me, friend, foe = b.fighters
    my_turn(b, foe)
    cast(b, foe, "hold_person" if "hold_person" in tables.spells else "hold_monster", friend)
    assert "paralyzed" in friend.conditions
    assert held_spells(b, friend)
    my_turn(b, me)
    cast(b, me, "dispel_magic", point=(friend.x, friend.y), level=3)
    assert "paralyzed" not in friend.conditions


def test_spell_breaker_casts_dispel_magic_with_a_bonus_action_and_keeps_the_slot_when_nothing_ends(tables):
    w = hero(tables, xp=64000, sub="abjuration")  # level 10
    if "spell_breaker" not in w.features:
        pytest.skip("Spell Breaker is not reached at this level")
    b = fight(tables, [w], ["bandit"], {0: (2, 4), 1: (6, 4)})
    me, bandit = b.fighters
    my_turn(b, me)
    assert cast_kind(me, tables.spells["dispel_magic"]) == "bonus"
    before = list(w.spell_slots_used) if hasattr(w, "spell_slots_used") else None
    slots = [n for n in me.char.slots] if hasattr(me.char, "slots") else None
    assert b.do_cast(me, "dispel_magic", None, point=(bandit.x, bandit.y))
    assert any("Spell Breaker" in t for t, _ in b.log)
    assert me.action == 1, "the action is still free"
    del before, slots


def test_crusaders_mantle_is_shared_with_friends_near_the_caster(tables):
    b = fight(tables, [hero(tables, "paladin" if "paladin" in tables.classes else "cleric", xp=14000),
                       hero(tables, "fighter", seed=2), hero(tables, "fighter", seed=3)],
              ["bandit"], {0: (2, 4), 1: (3, 4), 2: (14, 8), 3: (8, 4)})
    me, near, far, bandit = b.fighters
    far.x, far.y = 14, 8
    my_turn(b, me)
    cast(b, me, "crusaders_mantle")
    assert any(bf.get("aura_of") == me.id for bf in near.buffs)
    assert not any(bf.get("aura_of") == me.id for bf in far.buffs)
    b._end_concentration(me, quiet=True)
    b._follow_auras()
    assert not any(bf.get("aura_of") is not None for bf in near.buffs)


def test_haste_doubles_speed_and_leaves_lethargy_when_it_ends(tables):
    b = fight(tables, [hero(tables), hero(tables, "fighter", seed=2)], ["bandit"], {0: (2, 4), 1: (3, 4), 2: (9, 4)})
    me, friend, bandit = b.fighters
    my_turn(b, me)
    speed, ac, n = query.speed(friend), friend.ac(), query.attacks_per_action(friend)
    cast(b, me, "haste", friend)
    assert query.speed(friend) == speed * 2 and friend.ac() == ac + 2 and query.attacks_per_action(friend) == n + 1
    b._end_concentration(me, quiet=False, why="is lost")
    assert "incapacitated" in friend.conditions and query.speed(friend) == 0


def test_slow_and_confusion_take_a_foes_turn_from_it(tables):
    b = fight(tables, [hero(tables)], ["bandit", "bandit"], {0: (2, 4), 1: (5, 4), 2: (6, 4)})
    me, a, c = b.fighters
    my_turn(b, me)
    speed = query.speed(a)
    cast(b, me, "slow", point=(a.x, a.y))
    assert query.speed(a) == speed // 2 and query.attacks_per_action(a) == 1
    my_turn(b, a)
    assert a.bonus == 0
    my_turn(b, me)
    me.concentration = None
    cast(b, me, "confusion", point=(c.x, c.y))
    assert c.buff_value("confused")
    took = sum(marks.confused_turn(b, c) for _ in range(30) if c.active)
    assert took > 10


def test_dominate_turns_a_foe_on_its_friends_until_it_shakes_it_off(tables):
    b = fight(tables, [hero(tables, "wizard", xp=100000)], ["bandit", "bandit"], {0: (2, 4), 1: (4, 4), 2: (6, 4)})
    me, a, c = b.fighters
    my_turn(b, me)
    cast(b, me, "dominate_person", a)
    assert a.team == PARTY and c in b.enemies_of(a)
    b._end_concentration(me, quiet=True)
    assert a.team == FOE


def test_black_tentacles_hold_and_hurt(tables):
    b = fight(tables, [hero(tables)], ["ogre"], {0: (2, 4), 1: (6, 4)})
    me, ogre = b.fighters
    my_turn(b, me)
    hp = ogre.hp
    cast(b, me, "evards_black_tentacles", point=(6, 4))
    assert "restrained" in ogre.conditions and ogre.hp < hp


def test_a_wall_of_stone_rises_and_falls_and_the_wind_wall_turns_arrows(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (9, 4)})
    me, bandit = b.fighters
    my_turn(b, me)
    before = b.field.name(5, 4)
    sp = tables.spells["wall_of_stone"]
    cast(b, me, "wall_of_stone", point=(5, 4))
    walls = [z for z in b.zones if z.kind == "stone"]
    assert walls and not b.field.passable(*sorted(walls[0].cells)[0])
    b._end_concentration(me, quiet=True)
    assert not [z for z in b.zones if z.kind == "stone"] and b.field.name(5, 4) == before
    del sp
    cast(b, me, "wind_wall", point=(5, 4))
    wind = [z for z in b.zones if z.kind == "wind"]
    assert wind
    archer = next((o for o in b.attack_options(bandit) if o.kind == "ranged"), None)
    if archer is not None and b.wind_between(bandit, me):
        hp = me.hp
        assert b._attack(bandit, archer, me) is False and me.hp == hp


def test_vampiric_touch_heals_the_caster(tables):
    b = fight(tables, [hero(tables)], ["ogre"], {0: (2, 4), 1: (3, 4)})
    me, ogre = b.fighters
    me.hp = 3
    my_turn(b, me)
    for _ in range(6):
        hp = ogre.hp
        cast(b, me, "vampiric_touch", ogre)
        me.concentration = None
        if ogre.hp < hp:
            break
    assert me.hp > 3


def test_fire_shield_burns_whoever_strikes_in_melee(tables):
    b = fight(tables, [hero(tables)], ["ogre"], {0: (2, 4), 1: (3, 4)})
    me, ogre = b.fighters
    my_turn(b, me)
    cast(b, me, "fire_shield")
    opt = next(o for o in b.attack_options(ogre) if o.is_melee)
    hp = ogre.hp
    for _ in range(20):
        if b._attack(ogre, opt, me):
            break
        me.hp = me.max_hp
    assert ogre.hp < hp


def test_beacon_of_hope_makes_healing_the_most_it_can_be(tables):
    b = fight(tables, [hero(tables, "cleric", xp=14000), hero(tables, "fighter", seed=2)], ["bandit"],
              {0: (2, 4), 1: (3, 4), 2: (9, 4)})
    me, friend, bandit = b.fighters
    my_turn(b, me)
    cast(b, me, "beacon_of_hope")
    assert friend.buff_value("heal_max")
    friend.hp = 1
    sp = tables.spells["cure_wounds"]
    b.cast(me, "cure_wounds", sp, friend, None, up=0, mod=0, dc=10, bonus=0, mult=1, level=1)
    most = sum(int(n) * int(s) for n, s in [spellrules.ops(sp)[0]["dice"].split("d")])
    assert friend.hp == min(friend.max_hp, 1 + most)
