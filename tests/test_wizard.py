"""Demigods & Magics part B.4: the 2024 wizard from level 1 to 20, the Evoker and the Abjurer - each feature at work in
a real fight, at a rest or on the sheet; Counterspell for the party and the enemy."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import progression, tactics
from realmwalker.rules import spells as spellrules
from realmwalker.rules.engine import actions, query
from realmwalker.world.tables import Tables

from tests.test_feats import fight, hero, on_turn, soft


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def wizard(tables, level, sub="evocation", seed=1, book=()):
    c = hero(tables, "wizard", level=level, seed=seed)
    if level >= 3 and c.subclass != sub:
        c.subclass = sub
        c.features = [f for f in c.features if f not in ("evocation_savant", "potent_cantrip", "sculpt_spells",
                                                         "empowered_evocation", "overchannel", "abjuration_savant",
                                                         "arcane_ward", "projected_ward", "spell_breaker",
                                                         "spell_resistance")]
        c.features += [f["id"] for f in tables.classes["wizard"]["subclasses"][sub]["features"] if f["level"] <= level]
    for sid in book:
        if sid not in c.spells["spellbook"]:
            c.spells["spellbook"].append(sid)
    return c


def spend_all_slots(c, tables):
    c.spells["slots_used"] = list(spellrules.slots_total(c, tables)) + [0] * (9 - len(spellrules.slots_total(c, tables)))


# ---------------------------------------------------------------------------- the sheet and the levels
def test_the_school_at_three_scholar_at_two_and_the_savants_spells(tables):
    c = hero(tables, "wizard", level=1)
    assert c.subclass is None and {"ritual_adept", "arcane_recovery"} <= set(c.features)
    progression.level_up(c, tables, RNG(1))
    choice = next(p for p in c.pending if p["kind"] == "expertise")
    ids = [o[0] for o in progression.options(c, tables, choice)]
    assert ids and set(ids) <= {"arcana", "history", "investigation", "medicine", "nature", "religion"}
    assert set(ids) <= set(c.skills)
    progression.auto_resolve(c, tables)
    assert c.expertise == ["arcana"] if "arcana" in ids else len(c.expertise) == 1
    book = list(c.spells["spellbook"])
    progression.level_up(c, tables, RNG(1))
    assert c.level == 3 and any(p["kind"] == "subclass" for p in c.pending)
    sub = next(p for p in c.pending if p["kind"] == "subclass")
    progression.resolve(c, tables, sub, "evocation")
    savant = next(p for p in c.pending if p.get("school") == "evocation")
    picks = [o[0] for o in progression.options(c, tables, savant)]
    assert picks and all(tables.spells[s]["school"] == "evocation" and tables.spells[s]["level"] <= 2 for s in picks)
    progression.resolve(c, tables, savant, picks[0])
    assert picks[0] in c.spells["spellbook"]  # (two, when the catalogue has two left to give: Part D)
    progression.auto_resolve(c, tables)
    assert not c.pending
    # Level 5 opens level 3 slots: two spells as every level, and one more evocation.
    progression.level_up(c, tables, RNG(1))
    progression.level_up(c, tables, RNG(1))
    assert any(p["kind"] == "spells" and p.get("school") == "evocation" and p["level"] == 5 for p in c.pending)
    assert "memorize_spell" in c.features


def test_arcane_recovery_brings_back_the_highest_slots(tables):
    c = wizard(tables, 6)
    c.spells["slots_used"] = [2, 1, 1, 0, 0, 0, 0, 0, 0]
    notes = progression.short_rest(c, tables, RNG(1))
    # Half of 6 is 3 levels: the level 3 slot (and nothing else fits).
    assert c.spells["slots_used"][:3] == [2, 1, 0] and any("Arcane Recovery" in n for n in notes)
    progression.short_rest(c, tables, RNG(1))
    assert c.spells["slots_used"][:3] == [2, 1, 0]  # (once between long rests)
    progression.long_rest(c, tables, RNG(1))
    c.spells["slots_used"] = [1, 0, 0, 0, 0, 0, 0, 0, 0]
    progression.short_rest(c, tables, RNG(1))
    assert c.spells["slots_used"][0] == 0



def test_spell_mastery_and_signature_spells_cast_without_slots(tables):
    c = wizard(tables, 20)
    assert len(c.spells["mastery"]) == 2 and len(c.spells["signature"]) == 2
    assert {tables.spells[s]["level"] for s in c.spells["mastery"]} == {1, 2}
    assert all(tables.spells[s].get("cast", "action") == "action" for s in c.spells["mastery"])
    c.spells["signature"] = ["fireball", "lightning_bolt"]
    c.uses["signature:fireball"] = c.uses["signature:lightning_bolt"] = 1
    spend_all_slots(c, tables)
    one = next(s for s in c.spells["mastery"] if tables.spells[s]["level"] == 1)
    b = fight(tables, c, "bandit", "bandit", spots={0: (3, 4), 1: (8, 4), 2: (9, 5)})
    me = b.side("party")[0]
    for x in b.side("foe"):
        soft(x)
    on_turn(b, me)
    sp = tables.spells[one]
    target = b.side("foe")[0] if sp["target"] == "enemy" else None
    point = (8, 4) if sp["target"] in ("point", "direction") else None
    from realmwalker.rules import describe

    assert any("Spell Mastery" in line for line in describe.spell(tables, one, f=me).lines)
    assert b.do_cast(me, one, target, point=point), b.log[-3:]
    assert c.spells["slots_used"] == list(spellrules.slots_total(c, tables)) + [0] * 0  # (no slot spent)
    on_turn(b, me)
    assert b.do_cast(me, "fireball", point=(8, 4))
    assert c.uses["signature:fireball"] == 0
    on_turn(b, me)
    assert "no spell slots" in (b.cast_problem(me, "fireball", point=(8, 4)) or "")
    progression.short_rest(c, tables, RNG(1))
    assert c.uses["signature:fireball"] == 1


# ---------------------------------------------------------------------------- the Evoker
def test_potent_cantrip_bites_on_a_miss(tables):
    c = wizard(tables, 3)
    b = fight(tables, c, "bandit")
    me, foe = b.side("party")[0], b.side("foe")[0]
    soft(foe, ac=60)  # (every bolt misses)
    on_turn(b, me)
    hp = foe.hp
    assert b.do_cast(me, "fire_bolt", foe)
    assert 0 < hp - foe.hp <= 5 and any("Potent Cantrip" in t for t, _ in b.log)
    plain = wizard(tables, 3, sub="abjuration")
    b2 = fight(tables, plain, "bandit")
    me2, foe2 = b2.side("party")[0], b2.side("foe")[0]
    soft(foe2, ac=60)
    on_turn(b2, me2)
    hp = foe2.hp
    b2.do_cast(me2, "fire_bolt", foe2)
    assert foe2.hp == hp


def test_overchannel_is_free_once_and_then_burns(tables):
    c = wizard(tables, 14)
    b = fight(tables, c, "bandit")
    me, foe = b.side("party")[0], b.side("foe")[0]
    soft(foe, hp=500)
    on_turn(b, me)
    hp, mine = foe.hp, me.hp
    assert b.do_cast(me, "magic_missile", foe, slot_level=1)
    assert hp - foe.hp == 3 * 5 and me.hp == mine  # three darts of 1d4+1 at their greatest, free the first time
    assert c.uses["overchannel"] == 1
    # The second time the battle does not choose it (it would cost 2d12 necrotic for a level 1 slot).
    on_turn(b, me)
    hp = foe.hp
    b.do_cast(me, "magic_missile", foe, slot_level=1)
    assert c.uses["overchannel"] == 1 and me.hp == mine
    from realmwalker.rules.engine.handlers import wizard as wz

    assert wz.overchannel_cost(me, 2) == "4d12"
    # Asked and paid: the necrotic price, which nothing resists.
    me.__dict__["_overchannel_cost"] = "2d12"
    wz.overchannel_price(b, me)
    assert 2 <= mine - me.hp <= 24
    progression.long_rest(c, tables, RNG(1))
    assert not c.uses.get("overchannel")


def test_empowered_evocation_on_one_roll(tables):
    c = wizard(tables, 10)
    b = fight(tables, c, "bandit")
    me, foe = b.side("party")[0], b.side("foe")[0]
    soft(foe, hp=500)
    from realmwalker.rules.engine import effects

    sp = tables.spells["scorching_ray"]
    cast = effects.Cast(b, me, "scorching_ray", sp, foe, None, empowered=me.mod("int"))
    first = effects.expr(cast, "2d6", empower=True)
    assert first.endswith(f"+{me.mod('int')}")


# ---------------------------------------------------------------------------- the Abjurer
def test_the_ward_is_mended_with_a_slot_and_the_auto_does_it(tables):
    c = wizard(tables, 3, sub="abjuration")
    b = fight(tables, c, "wolf", spots={0: (3, 4), 1: (4, 4)})
    me = b.side("party")[0]
    on_turn(b, me)
    assert actions.problem(b, me, actions.find(me, "ward_mend")) == "no ward woven since the last long rest"
    assert b.do_cast(me, "mage_armor")
    most = 2 * c.level + me.mod("int")
    assert c.uses["arcane_ward"] == most
    c.uses["arcane_ward"] = 1
    on_turn(b, me)
    b.do_ability(me, "ward_mend")
    assert c.uses["arcane_ward"] in (3, 5) and me.bonus == 0
    # On Auto, with the ward half gone and a foe beside it, the wizard spends its bonus action on it.
    c.uses["arcane_ward"] = 1
    me.auto = True
    on_turn(b, me)
    tactics.take_turn(b, me)
    assert c.uses["arcane_ward"] > 1


def test_a_free_cast_weaves_no_ward(tables):
    c = wizard(tables, 18, sub="abjuration")
    c.spells["mastery"] = ["mage_armor", "web"]
    b = fight(tables, c, "wolf")
    me = b.side("party")[0]
    on_turn(b, me)
    assert b.do_cast(me, "mage_armor")
    assert not c.uses.get("ward_made")


def test_spell_resistance(tables):
    c = wizard(tables, 14, sub="abjuration")
    b = fight(tables, c, "cult_fanatic")
    me, foe = b.side("party")[0], b.side("foe")[0]
    assert not query.save_roll(b, me, "wis").roll.advantage
    b._casting = foe
    assert query.save_roll(b, me, "wis").roll.advantage
    hp = me.hp
    c.uses.pop("arcane_ward", None)
    b._hit(foe, me, 10, "fire", crit=False, weapon="fire")
    assert hp - me.hp == 5
    b._casting = None
    hp = me.hp
    b._hit(foe, me, 10, "fire", crit=False, weapon="fire")
    assert hp - me.hp == 10


# ---------------------------------------------------------------------------- Counterspell
def test_a_wizard_counters_a_cultists_spell(tables, monkeypatch):
    c = wizard(tables, 5, book=("counterspell",))
    b = fight(tables, c, "cult_fanatic", spots={0: (3, 4), 1: (6, 4)})
    me, fanatic = b.side("party")[0], b.side("foe")[0]
    on_turn(b, fanatic)
    used = list(c.spells["slots_used"])
    monkeypatch.setattr(type(b), "_save", lambda self, f, ability, dc, **kw: False)
    left = fanatic.creature.uses.get("spell:spiritual_weapon")
    tactics.take_turn(b, fanatic)
    casts = [e for e in b.events if e["kind"] == "cast"]
    assert any(e["spell"] == "counterspell" and e["by"] == me.id for e in casts)
    assert any(e["kind"] == "countered" for e in b.events)
    assert c.spells["slots_used"][2] == used[2] + 1 and not me.reaction
    assert not any(t.owner == fanatic.id for t in b.tokens)  # (no spiritual weapon came)


def test_spell_breaker_keeps_the_slot_when_the_spell_holds(tables, monkeypatch):
    c = wizard(tables, 10, sub="abjuration")
    c.spells["spellbook"] = [s for s in c.spells["spellbook"] if s != "counterspell"]
    assert "counterspell" in spellrules.known_spells(c, tables) and "counterspell" not in c.spells["spellbook"]
    b = fight(tables, c, "cult_fanatic", spots={0: (3, 4), 1: (6, 4)})
    me, fanatic = b.side("party")[0], b.side("foe")[0]
    on_turn(b, fanatic)
    monkeypatch.setattr(type(b), "_save", lambda self, f, ability, dc, **kw: True)
    used = list(c.spells["slots_used"])
    tactics.take_turn(b, fanatic)
    assert any(e["kind"] == "cast" and e["spell"] == "counterspell" for e in b.events)
    assert c.spells["slots_used"] == used and any("Spell Breaker" in t for t, _ in b.log)
    assert c.uses.get("ward_made")  # (Counterspell is an abjuration: the ward is woven)


def test_an_enemy_counters_the_party_wizard(tables, monkeypatch):
    c = wizard(tables, 5)
    b = fight(tables, c, "cult_fanatic", spots={0: (3, 4), 1: (8, 4)})
    me, foe = b.side("party")[0], b.side("foe")[0]
    foe.cdef = dict(foe.cdef, spells=list(foe.cdef.get("spells", [])) + ["counterspell"])
    foe.slots = [0, 0, 1]
    monkeypatch.setattr(type(b), "_save", lambda self, f, ability, dc, **kw: False)
    on_turn(b, me)
    used = list(c.spells["slots_used"])
    hp = foe.hp
    assert b.do_cast(me, "magic_missile", foe)
    assert foe.hp == hp and foe.slots == [0, 0, 0]
    assert c.spells["slots_used"] == used and me.action == 0  # (the slot kept, the action lost)
    # A cantrip is not worth the enemy's level 3 slot.
    foe.slots = [0, 0, 1]
    foe.reaction = True
    on_turn(b, me)
    b.do_cast(me, "fire_bolt", foe)
    assert foe.slots == [0, 0, 1]
