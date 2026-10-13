"""Demigods & Magics part B.1: the 2024 fighter from level 1 to 20, the Champion, and the Knight to 18 - each feature at
work in a real fight or check."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import progression, tactics
from realmwalker.rules.engine import actions, query
from realmwalker.rules.engine import resources as res
from realmwalker.rules.engine.handlers import fighter as fh
from realmwalker.world.tables import Tables

from tests.test_feats import armed, fight, hero, on_turn, soft


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def fighter(tables, level, sub="champion", seed=1):
    c = armed(tables, "longsword", level=level, seed=seed)
    c.subclass = sub
    res.fill(c, tables)
    return c


def test_the_table_to_twenty(tables):
    c = fighter(tables, 20)
    assert res.maximum(c, res.pools(c, tables)["second_wind"]) == 4
    assert res.maximum(c, res.pools(c, tables)["action_surge"]) == 2
    assert res.maximum(c, res.pools(c, tables)["indomitable"]) == 3
    b = fight(tables, c, "bandit")
    me = b.fighters[0]
    assert query.attacks_per_action(me) == 4 and query.crit_range(me) == 18
    for level, attacks in ((5, 2), (11, 3), (19, 3)):
        b = fight(tables, fighter(tables, level), "bandit")
        assert query.attacks_per_action(b.fighters[0]) == attacks


def test_tactical_mind_turns_a_failed_check(tables):
    c = fighter(tables, 2)
    c.uses["second_wind"] = 2
    spent = turned = 0
    for i in range(60):
        before = c.uses["second_wind"]
        total, line = fh.tactical_mind(c, tables, 10, 14, RNG(i, "tm"))
        if total >= 14:
            turned += 1
            assert c.uses["second_wind"] == before - 1
            c.uses["second_wind"] = 2
        else:
            assert c.uses["second_wind"] == before and "nothing spent" in line
    assert turned > 20
    assert fh.tactical_mind(c, tables, 2, 14, RNG(1))[1] == ""  # (out of reach: not even tried)


def test_tactical_shift_slips_away_after_second_wind(tables):
    c = fighter(tables, 5)
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    on_turn(b, me)
    me.hp = 5
    move = me.move_left
    b.do_ability(me, "second_wind")
    assert me.move_left == move + me.speed // 2 and me.disengaged


def test_studied_attacks_and_action_surge_once_a_turn(tables):
    c = fighter(tables, 17)
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe, ac=40)
    on_turn(b, me)
    opt = next(o for o in b.attack_options(me) if o.key == "main")
    b._attack(me, opt, foe)
    assert any(bf.get("vex") == foe.id for bf in me.buffs)  # (a miss teaches)
    adv, dis, why = b._adv_dis(me, foe, opt)
    assert adv
    assert c.uses["action_surge"] == 2
    b.do_ability(me, "action_surge")
    a = actions.find(me, "action_surge")
    assert actions.problem(b, me, a) == "already used this turn" and c.uses["action_surge"] == 1
    on_turn(b, me)
    assert actions.problem(b, me, a) is None


def test_indomitable_adds_the_level(tables):
    c = fighter(tables, 13)
    b = fight(tables, c, "bandit")
    me = b.fighters[0]
    assert c.uses["indomitable"] == 2
    saved = b._save(me, "int", 22 + 1)  # (beyond any first roll; within reach with +13)
    assert c.uses["indomitable"] == 1 and any("indomitable" in t for t, _ in b.log)
    assert saved in (True, False)


def test_tactical_master_saps_instead_of_a_weak_trick(tables):
    c = fighter(tables, 9)
    b = fight(tables, c, "ogre")
    me, foe = b.fighters
    soft(foe, ac=1)
    assert tactics.tactical_mastery(b, me, "graze", foe) == "sap"
    assert tactics.tactical_mastery(b, me, "topple", foe) == "topple"
    c.masteries = ["longsword"]  # (the longsword's own trick is Sap; a greatsword's Graze would become one)
    on_turn(b, me)
    b._attack(me, next(o for o in b.attack_options(me) if o.key == "main"), foe)
    assert any(bf.get("sapped") == me.id for bf in foe.buffs)


def test_the_champion_athlete_warrior_and_survivor(tables):
    c = fighter(tables, 18)
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    assert query.initiative_roll(me).advantage
    c.uses["heroic_inspiration"] = 0
    on_turn(b, me)
    assert c.uses["heroic_inspiration"] == 1  # (Heroic Warrior)
    on_turn(b, me)
    me.hp = me.max_hp // 3
    hp = me.hp
    on_turn(b, me)
    assert me.hp == hp + 5 + me.mod("con")  # (Heroic Rally)
    me.hp, me.state = 0, "down"
    me.conditions = {"unconscious": -1, "prone": -1}
    up = 0
    for i in range(40):
        b.rng = RNG(i, "ds")
        me.hp, me.state, me.death_saves = 0, "down", [0, 0]
        b._death_save(me)
        up += me.state == "fighting"
    assert up >= 8  # (advantage, and 18-20 counts as a 20: about a third)


def test_the_champions_remarkable_athlete_out_of_a_fight(tables, monkeypatch):
    c = fighter(tables, 3)
    seen = []
    from realmwalker.core import dice as dicemod

    real = dicemod.d20

    def spy(rng, advantage=False, disadvantage=False):
        seen.append(advantage)
        return real(rng, advantage=advantage, disadvantage=disadvantage)
    b = fight(tables, c, "bandit")
    monkeypatch.setattr("realmwalker.rules.combat.dice.d20", spy)
    b.check(b.fighters[0], "athletics", 10)
    b.check(b.fighters[0], "acrobatics", 10)
    assert seen == [True, False]


def test_the_knight_unyielding_and_warden(tables):
    from tests.test_feats import fight as f2

    k = fighter(tables, 18, sub="knight")
    friend = hero(tables, "wizard", seed=3)
    b = f2(tables, [k, friend], "bandit", spots={0: (3, 4), 1: (8, 4), 2: (5, 4)})
    me, fr, foe = b.fighters
    opt = next(o for o in b.attack_options(foe) if o.is_melee)
    assert b.gap(me, foe) == 2
    adv, dis, why = b._adv_dis(foe, fr, opt)
    assert dis  # (two strides from the knight is near enough)
    b._apply_hp_loss(me, me.hp + 3, source=foe, cause="test")
    assert me.state == "fighting" and me.hp == k.level and k.uses["unyielding"] == 0


def test_a_level_up_brings_the_new_features(tables):
    c = hero(tables, "fighter", level=10)
    c.subclass = "champion"
    progression.award_xp(c, tables.rules["xp_for_level"][10], tables, RNG(1), auto=True)
    assert c.level == 11
    b = fight(tables, c, "bandit")
    assert query.attacks_per_action(b.fighters[0]) == 3
