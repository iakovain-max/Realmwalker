"""Demigods & Magics part B.2: the 2024 rogue from level 1 to 20, the Thief and the Assassin - Sneak Attack and its
Cunning Strikes, Steady Aim, Stroke of Luck and the rest, each in a real fight or check."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import progression, tactics
from realmwalker.rules.engine import actions, query
from realmwalker.rules.engine import resources as res
from realmwalker.rules.engine.handlers import rogue as rh
from realmwalker.rules.inventory import add_item
from realmwalker.world.tables import Tables

from tests.test_feats import fight, hero, on_turn, soft, wield


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def rogue(tables, level, sub="thief", seed=1):
    c = hero(tables, "rogue", level=level, seed=seed)
    for slot in ("main_hand", "off_hand"):
        from realmwalker.rules.inventory import unequip

        unequip(c, slot)
    wield(tables, c, "rapier")
    c.subclass = sub
    for f in tables.classes["rogue"]["subclasses"][sub]["features"]:
        if f["level"] <= level and f["id"] not in c.features:
            c.features.append(f["id"])
            progression.feature_gives(c, tables, f)
    res.fill(c, tables)
    return c


def sneak_fight(tables, c, *foes):
    friend = hero(tables, "fighter", seed=7)
    b = fight(tables, [c, friend], *foes, spots={0: (3, 4), 1: (5, 5), 2: (4, 4)} if len(foes) == 1 else None)
    return b


def test_cunning_strike_trips_and_spends_dice(tables):
    c = rogue(tables, 5)
    b = sneak_fight(tables, c, "bandit")
    me, fr, foe = b.fighters
    soft(foe, ac=1, hp=300)
    assert rh.tricks_open(b, me, foe, 3) == ["trip", "withdraw"]  # (no poisoner's kit in the pack)
    assert tactics.cunning_strike(b, me, foe, ["trip", "withdraw"], 3) == "trip"  # (a friend is beside it)
    downs = 0
    for i in range(12):
        b.rng = RNG(i, "cs")
        on_turn(b, me)
        foe.conditions.pop("prone", None)
        b._attack(me, next(o for o in b.attack_options(me) if o.key == "main"), foe)
        downs += "prone" in foe.conditions
    assert downs >= 3


def test_poison_needs_the_kit_and_the_assassin_envenoms(tables):
    c = rogue(tables, 13, sub="assassin")
    assert "poisoners_kit" in c.tools and any(i.def_id == "poisoners_kit" for i in c.inventory)
    b = sneak_fight(tables, c, "bandit")
    me, fr, foe = b.fighters
    assert "poison" in rh.tricks_open(b, me, foe, 7)
    me.__dict__["cunning"] = (foe.id, ["poison"])
    foe.creature.max_hp = foe.creature.hp = 300
    from types import SimpleNamespace

    hurt = 0
    for i in range(10):
        b.rng = RNG(i, "p")
        foe.conditions.pop("poisoned", None)
        before = foe.hp
        me.__dict__["cunning"] = (foe.id, ["poison"])
        rh.cunning_after(b, me, SimpleNamespace(target=foe), None, None)
        hurt += before - foe.hp
    assert hurt > 0 and any(se["cond"] == "poisoned" for se in foe.save_ends)


def test_devious_strikes_daze_obscure_and_knock_out(tables):
    c = rogue(tables, 14)
    b = sneak_fight(tables, c, "ogre")
    me, fr, foe = b.fighters
    from types import SimpleNamespace

    assert {"daze", "obscure", "knock_out"} <= set(rh.tricks_open(b, me, foe, 7))
    got = set()
    for i in range(20):
        b.rng = RNG(i, "d")
        foe.conditions.clear()
        foe.buffs = []
        foe.save_ends = []
        me.__dict__["cunning"] = (foe.id, ["daze", "obscure", "knock_out"])
        rh.cunning_after(b, me, SimpleNamespace(target=foe), None, None)
        got |= set(foe.conditions) | {"dazed" for bf in foe.buffs if bf.get("dazed")}
    assert {"dazed", "blinded", "unconscious"} <= got
    foe.conditions.clear()
    foe.buffs = [{"dazed": True, "by": me.id, "source": "daze"}]
    on_turn(b, foe)
    assert foe.move_left == 0 and foe.bonus == 0 and foe.action > 0


def test_steady_aim_gives_advantage_and_roots(tables):
    c = rogue(tables, 3)
    b = fight(tables, c, "bandit", spots={0: (3, 4), 1: (8, 4)})
    me, foe = b.fighters
    on_turn(b, me)
    a = actions.find(me, "steady_aim")
    assert actions.problem(b, me, a) is None
    b.do_ability(me, "steady_aim")
    assert me.move_left == 0 and me.bonus == 0
    opt = next(o for o in b.attack_options(me) if o.key == "main")
    assert b._adv_dis(me, foe, opt)[0]
    on_turn(b, me)
    me.moved_feet = 5
    assert actions.problem(b, me, a) == "you have moved this turn"


def test_reliable_talent_slippery_mind_and_elusive(tables):
    c = rogue(tables, 18)
    assert "wis" in c.saves and "cha" in c.saves
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    skill = c.skills[0]
    lows = [b.check(me, skill, 10 + me.skill(skill)) for _ in range(30)]
    assert all(lows)  # (never lower than 10)
    foe_opt = next(o for o in b.attack_options(foe) if o.is_melee)
    me.conditions["prone"] = -1  # (prone: attacks from beside it would have advantage)
    adv, dis, why = b._adv_dis(foe, me, foe_opt)
    assert not adv


def test_stroke_of_luck_turns_a_miss(tables):
    c = rogue(tables, 20)
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe, ac=40)
    on_turn(b, me)
    opt = next(o for o in b.attack_options(me) if o.key == "main")
    for _ in range(10):
        if c.uses["stroke_of_luck"] == 0:
            break
        b._attack(me, opt, foe)  # (all hit: the first miss becomes a 20)
    assert c.uses["stroke_of_luck"] == 0 and any("Stroke of Luck" in t for t, _ in b.log)
    res.recover(c, tables, "short")
    assert c.uses["stroke_of_luck"] == 1


def test_the_thief_climbs_leaps_binds_four_and_acts_twice(tables):
    c = rogue(tables, 17)
    b = fight(tables, c, "bandit")
    me = b.fighters[0]
    assert me.climb_speed == me.speed and me.jump[1] >= c.abilities["dex"]
    assert "use_magic_device" in c.features
    b.round = 1
    me.__dict__.pop("reflexes_used", None)
    on_turn(b, me)
    b.round = 1
    me.__dict__.pop("reflexes_used", None)
    from realmwalker.rules.engine import events

    act = me.action
    events.emit(b, "turn_start", actor=me)
    assert me.action == act + 1


def test_the_assassins_first_blow(tables):
    c = rogue(tables, 17, sub="assassin")
    b = sneak_fight(tables, c, "ogre")
    me, fr, foe = b.fighters
    assert query.initiative_roll(me).advantage
    soft(foe, ac=1, hp=500)
    b.round = 1
    on_turn(b, me)
    b.round = 1
    c.uses.pop("sneak_round", None)
    opt = next(o for o in b.attack_options(me) if o.key == "main")
    adv, _, why = b._adv_dis(me, foe, opt)
    assert adv
    b._attack(me, opt, foe)
    assert 500 - foe.hp > c.level  # (Sneak Attack, and the level more in the first round)


def test_the_auto_rogue_aims_and_strikes(tables):
    c = rogue(tables, 5)
    wield(tables, c, "shortbow")
    add_item(c, tables.items, "arrows")
    b = fight(tables, c, "bandit", spots={0: (3, 4), 1: (9, 4)})
    me, foe = b.fighters
    me.auto = True
    on_turn(b, me)
    tactics.take_turn(b, me)
    assert any("careful aim" in t for t, _ in b.log)
