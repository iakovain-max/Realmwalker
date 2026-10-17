"""Expansion 5 Part C: mages and priests of the world (docs/expansions/05-schools-domains.md).

C.1: the Monster Manual's Mage Apprentice, Mage, Archmage, Priest and Archpriest - their blocks, the casting their
blocks describe (spells at a higher level, Divine Aid and Misty Step with the bonus action, Protective Magic's
Counterspell or Shield three times a day, Holy Word on enemies only), their dress among each people, and the road.
"""
from __future__ import annotations

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules.combat import FOE, PARTY
from realmwalker.rules.creatures import Creature, spawn
from realmwalker.world.tables import Tables
from tests.test_feats import fight, hero, on_turn, soft


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def foe(b, def_id):
    return next(f for f in b.fighters if f.side == FOE and f.creature.def_id == def_id)


# ---------------------------------------------------------------------------- C.1 the blocks
@pytest.mark.parametrize("cid, ac, hp, cr, multi", [
    ("mage_apprentice", 15, "9d8+9", 2, None), ("mage", 15, "18d8", 6, 3), ("archmage", 17, "31d8+31", 12, 4),
    ("priest", 13, "7d8+7", 2, 2), ("archpriest", 16, "32d8+96", 12, 3)])
def test_the_book_numbers(tables, cid, ac, hp, cr, multi):
    d = tables.creatures[cid]
    assert (d["ac"], d["hp"], d["cr"], d.get("multiattack")) == (ac, hp, cr, multi)
    assert d["kind"] == "humanoid" and d["descriptions"]


def test_what_the_block_says_it_casts(tables):
    mage, arch, priest = tables.creatures["mage"], tables.creatures["archmage"], tables.creatures["priest"]
    assert mage["spellcasting"]["dc"] == 14 and mage["spellcasting"]["levels"] == {"fireball": 4}
    assert mage["spellcasting"]["shared"]["protective_magic"] == {"uses": 3, "spells": ["counterspell", "shield"]}
    assert "misty_step" in mage["spellcasting"]["bonus"] and "misty_step" in mage["spellcasting"]["per_day"]["3"]
    assert "mage_armor" not in mage["spells"]  # (included in its AC)
    assert "mind_blank" not in arch["spells"] and "magic_resistance" in arch["traits"]
    assert arch["immune"] == ["psychic"] and arch["condition_immune"] == ["charmed"]
    # A priest's DC and attack are not printed: Wisdom and proficiency (8 + 2 + 3; 2 + 3).
    assert (priest["spellcasting"]["dc"], priest["spellcasting"]["attack"]) == (13, 5)
    assert set(priest["spellcasting"]["bonus"]) == {"bless", "dispel_magic", "healing_word", "lesser_restoration"}


def test_divine_aid_is_a_bonus_action_whatever_the_spell(tables):
    c = hero(tables, "fighter", level=3)
    b = fight(tables, c, "priest")
    pr = foe(b, "priest")
    on_turn(b, pr)
    assert "bless" in b.creature_spells(pr)
    assert b.creature_cast(pr, "bless", target=pr)
    assert pr.bonus == 0 and pr.action == 1  # (Bless, an action's spell, went with the bonus action)
    assert pr.creature.uses["pool:divine_aid"] == 2


def test_a_mage_casts_fireball_at_level_four(tables, monkeypatch):
    c = hero(tables, "fighter", level=5)
    b = fight(tables, c, "mage", spots={0: (3, 4), 1: (9, 4)})
    m = foe(b, "mage")
    on_turn(b, m)
    seen = {}
    real = b.cast

    def cast(f, sid, spell, target, point, **kw):
        seen[sid] = kw
        return real(f, sid, spell, target, point, **kw)

    monkeypatch.setattr(b, "cast", cast)
    pc = next(f for f in b.fighters if f.side == PARTY)
    point = (pc.x, pc.y)
    assert point in b.spell_points(m, "fireball")
    assert b.creature_cast(m, "fireball", point=point)
    assert seen["fireball"]["up"] == 1 and seen["fireball"]["level"] == 4
    assert m.creature.uses["spell:fireball"] == 1


def test_protective_magic_shield_turns_a_blow_and_shares_the_three_with_counterspell(tables):
    c = hero(tables, "fighter", level=5)
    b = fight(tables, c, "mage")
    m = foe(b, "mage")
    pc = next(f for f in b.fighters if f.side == PARTY)
    on_turn(b, pc)
    m.reaction = True
    opt = next(o for o in b.attack_options(pc) if o.key == "main")
    assert b._shield(m, pc, opt, 16, 15)
    assert m.creature.uses["pool:protective_magic"] == 2 and not m.reaction
    assert any(x.get("source") == "shield" and x.get("ac") == 5 for x in m.buffs)
    from realmwalker.rules.engine.handlers import wizard

    m.creature.uses["pool:protective_magic"] = 0
    assert wizard.counter_slot(b, m) is None  # (the three are spent: no Counterspell either)
    m.reaction = True
    m.buffs = [x for x in m.buffs if x.get("source") != "shield"]
    assert not b._shield(m, pc, opt, 16, 15)


def test_a_mage_counterspells_a_party_caster(tables):
    c = hero(tables, "wizard", level=5)
    b = fight(tables, c, "mage", spots={0: (3, 4), 1: (6, 4)})
    m = foe(b, "mage")
    pc = next(f for f in b.fighters if f.side == PARTY)
    on_turn(b, pc)
    m.reaction = True
    assert b._countered(pc, "magic_missile", tables.spells["magic_missile"]) in (True, False)
    assert m.creature.uses["pool:protective_magic"] == 2 and not m.reaction


def test_holy_word_strikes_enemies_only_and_recharges_on_a_four(tables):
    c = hero(tables, "fighter", level=5)
    b = fight(tables, c, "archpriest", "priest", spots={0: (3, 4), 1: (4, 4), 2: (4, 5)})
    ap, pr = foe(b, "archpriest"), foe(b, "priest")
    pc = next(f for f in b.fighters if f.side == PARTY)
    on_turn(b, ap)
    word = next(o for o in b.attack_options(ap) if o.extra.get("area") and o.available)
    hp_pr = pr.hp
    b.area_attack(ap, word, (pc.x, pc.y))
    assert pr.hp == hp_pr  # (each enemy in it: the priest beside it is spared)
    assert b._recharge_on(ap, word.extra["name"]) == 4 and not ap.recharge[word.extra["name"]]


def test_a_mage_and_a_priest_fight_to_the_end(tables):
    from tools import arena

    party = [hero(tables, "fighter", seed=s, level=6) for s in (1, 2, 3)]
    for cid in ("mage", "priest", "mage_apprentice", "archpriest"):
        b = fight(tables, party, cid, seed=4, spots={0: (2, 4), 1: (2, 5), 2: (2, 6), 3: (9, 5)})
        for f in b.fighters:
            f.auto = True
        r = arena.run(b)
        assert b.outcome is not None, cid
        assert any(k.startswith("cast:") for k in r["used"]), (cid, r["used"])


# ---------------------------------------------------------------------------- C.1 dress and the road
def test_a_creature_keeps_its_people_in_the_save(tables):
    c = spawn(tables, "mage", RNG(1, "m"), 1)
    c.culture = "qasari"
    assert Creature.from_dict(c.to_dict()).culture == "qasari"
    c.culture = ""
    assert "culture" not in c.to_dict() and Creature.from_dict(c.to_dict()).culture == ""


def test_mages_dress_as_their_people(tables):
    from realmwalker.ui.gfx import dolls

    plain = [p[0] for p in dolls.creature("mage", tables, "m1")]
    qasari = [p[0] for p in dolls.creature("mage", tables, "m1", culture="qasari")]
    assert any("wizard" in t for t in plain) and any("turban" in t for t in qasari)
    assert not dolls.check(tables) if hasattr(dolls, "check") else True


def test_folk_met_on_the_road_are_of_the_land(tables, monkeypatch):
    import copy

    from realmwalker.game.encounters import make_encounter
    from realmwalker.game.state import new_game
    from realmwalker.world.generator import WorldOptions
    from tests.worlds import cached_world

    g = new_game(copy.deepcopy(cached_world(WorldOptions("Mages", 7, "small"), tables)), tables)
    w, p = g.world, g.player
    folk = w.culture_at(p.x, p.y) if w.culture is not None else None
    e = make_encounter(g, "travelling_mage", RNG(3, "enc"))
    assert {c.def_id for c in e.creatures} <= {"mage", "mage_apprentice"}
    assert all(c.culture == (folk or "") for c in e.creatures)
