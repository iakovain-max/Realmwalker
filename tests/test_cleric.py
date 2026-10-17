"""Demigods & Magics part B.3: the 2024 cleric from level 1 to 20, the Life and War Domains - each feature at work in a
real fight or on the sheet."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import progression, tactics
from realmwalker.rules.character import Sheet
from realmwalker.rules.engine import actions, query
from realmwalker.rules.engine import resources as res
from realmwalker.world.tables import Tables

from tests.test_feats import fight, hero, on_turn, soft


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def cleric(tables, level, sub="life", seed=1, order=None, blessed=None):
    c = hero(tables, "cleric", level=level, seed=seed)
    if order or blessed:
        c.features = [f for f in c.features if not f.startswith(("order_", "blessed_"))]
        c.features += [x for x in (order, blessed) if x]
    c.subclass = sub
    res.fill(c, tables)
    return c


def test_divine_order_is_chosen_at_level_one(tables):
    from realmwalker.rules.creation import CharacterBuilder

    b = CharacterBuilder(tables, RNG(1, "c"))
    b.set_race("human")
    b.set_class("cleric")
    b.set_background("acolyte")
    c = b.build()
    choice = next(p for p in c.pending if p["kind"] == "option")
    ids = [o[0] for o in progression.options(c, tables, choice)]
    assert ids == ["order_protector", "order_thaumaturge"] and c.subclass is None
    progression.resolve(c, tables, choice, "order_protector")
    assert "heavy" in c.armor_prof and "martial" in c.weapon_prof
    t = hero(tables, "cleric", seed=2)
    t.features.append("order_thaumaturge")
    s = Sheet(t, tables)
    assert s.skill_bonus("religion") >= s.mod("int") + max(1, s.mod("wis"))


def test_the_domain_comes_at_three_and_channel_divinity_grows(tables):
    c = hero(tables, "cleric", level=2)
    assert c.subclass is None and res.maximum(c, res.pools(c, tables)["channel_divinity"]) == 2
    progression.award_xp(c, tables.rules["xp_for_level"][2], tables, RNG(1), auto=True)
    assert c.level == 3 and c.subclass in tables.classes["cleric"]["subclasses"]  # (their god's domain: Expansion 5 B)
    c18 = cleric(tables, 18)
    assert res.maximum(c18, res.pools(c18, tables)["channel_divinity"]) == 4


def test_divine_spark_heals_a_friend_and_smites_a_foe(tables):
    c = cleric(tables, 7)
    friend = hero(tables, "fighter", seed=3)
    b = fight(tables, [c, friend], "ogre", spots={0: (3, 4), 1: (5, 4), 2: (8, 4)})
    me, fr, foe = b.fighters
    fr.hp = 3
    on_turn(b, me)
    assert c.uses["channel_divinity"] == 3  # (three from level 6)
    b.do_ability(me, "divine_spark", fr)
    assert fr.hp > 3 + 2 and c.uses["channel_divinity"] == 2  # (2d8 + Wisdom at level 7)
    on_turn(b, me)
    hp = foe.hp
    b.do_ability(me, "divine_spark_harm", foe)
    assert foe.hp < hp


def test_sear_undead_burns_the_turned(tables):
    c = cleric(tables, 5)
    b = fight(tables, c, "skeleton", "zombie", spots={0: (3, 4), 1: (5, 4), 2: (5, 5)})
    me, sk, zo = b.fighters
    sk.creature.max_hp = sk.creature.hp = 200
    zo.creature.max_hp = zo.creature.hp = 200
    burned = False
    for i in range(10):
        b.rng = RNG(i, "turn")
        c.uses["channel_divinity"] = 2
        on_turn(b, me)
        b.do_ability(me, "turn_undead")
        burned = burned or sk.hp < 200 or zo.hp < 200
    assert burned


def test_blessed_strikes_divine_strike_and_potent_spellcasting(tables):
    c = cleric(tables, 14, sub="war", blessed="blessed_divine_strike")
    b = fight(tables, c, "ogre")
    me, foe = b.fighters
    soft(foe, ac=1, hp=500)
    on_turn(b, me)
    opt = next(o for o in b.attack_options(me) if o.is_melee)
    b._attack(me, opt, foe)
    assert any(e["kind"] == "damage" and e.get("dtype") == "radiant" for e in b.events)
    p = cleric(tables, 7, blessed="blessed_potent_spellcasting")
    b = fight(tables, p, "ogre", spots={0: (3, 4), 1: (6, 4)})
    me, foe = b.fighters
    assert me.has_trait("blessed_potent_spellcasting")


def test_divine_intervention_casts_without_a_slot(tables):
    c = cleric(tables, 10)
    friend = hero(tables, "fighter", seed=3)
    b = fight(tables, [c, friend], "ogre", spots={0: (3, 4), 1: (4, 4), 2: (8, 4)})
    me, fr, foe = b.fighters
    fr.hp = 2
    on_turn(b, me)
    used = list(c.spells.get("slots_used", [0] * 9))
    assert actions.problem(b, me, actions.find(me, "divine_intervention")) is None
    b.do_ability(me, "divine_intervention")
    assert c.uses["divine_intervention"] == 0 and me.action == 0
    assert any(e["kind"] == "cast" for e in b.events)
    assert c.spells.get("slots_used", [0] * 9) == used  # (no slot spent)


def test_life_blessed_healer_and_supreme_healing(tables):
    c = cleric(tables, 17)
    friend = hero(tables, "fighter", seed=3)
    b = fight(tables, [c, friend], "ogre", spots={0: (3, 4), 1: (4, 4), 2: (8, 4)})
    me, fr, foe = b.fighters
    me.hp = me.max_hp - 20
    fr.char.max_hp, fr.hp = 100, 1
    on_turn(b, me)
    hp = me.hp
    b.do_cast(me, "cure_wounds", fr, slot_level=1)
    assert me.hp == hp + 3  # (Blessed Healer: 2 + the slot's level)
    assert fr.hp == 1 + 2 * 8 + me.mod("wis") + 3  # (and Disciple of Life: 2 + the slot's level)  # (Supreme Healing: the dice at their highest)


def test_war_guided_strike_for_a_friend_blessing_and_avatar(tables):
    c = cleric(tables, 17, sub="war")
    friend = hero(tables, "fighter", seed=3)
    b = fight(tables, [c, friend], "ogre", spots={0: (3, 4), 1: (4, 5), 2: (5, 5)})
    me, fr, foe = b.fighters
    assert query.resists(me, "slashing") and not query.resists(me, "fire")
    on_turn(b, me)
    c.uses["channel_divinity"] = 4
    b.do_ability(me, "blessing_weapon")
    assert any(t.owner == me.id for t in b.tokens) and c.uses["channel_divinity"] == 3
    assert me.bonus == 0
    opt = next(o for o in b.attack_options(fr) if o.is_melee)
    guided = False
    for i in range(40):
        b.rng = RNG(i, "g")
        me.reaction = True
        before = c.uses["channel_divinity"]
        b._attack(fr, opt, foe)
        if c.uses["channel_divinity"] < before:
            guided = True
            break
    assert guided and not me.reaction


def test_the_auto_cleric_sparks_a_friend_in_trouble(tables):
    c = cleric(tables, 5)
    c.spells["slots_used"] = [9] * 9
    friend = hero(tables, "fighter", seed=3)
    b = fight(tables, [c, friend], "ogre", spots={0: (3, 4), 1: (5, 4), 2: (9, 4)})
    me, fr, foe = b.fighters
    me.auto = True
    fr.hp = 2
    on_turn(b, me)
    tactics.take_turn(b, me)
    assert fr.hp > 2 and c.uses["channel_divinity"] < res.maximum(c, res.pools(c, tables)["channel_divinity"])
