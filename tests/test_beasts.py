"""The rest of Appendix B (Expansion 3 F.7): 24 creatures of the 2025 Monster Manual with pictures, each a shape for
Polymorph and met in the land; what the kernel learned for them (a bonus-action Trample on the fallen, a hold that
restrains, a sting that puts to sleep by 5, the sphinx's Burst of Ingenuity, the lion's Running Leap, Invisibility at
will on oneself); the water-breathers never a friend's form; the cult's imp and quasit, the tower's tadpoles."""

import json
from pathlib import Path

import pytest

from realmwalker.rules import shapes, tactics
from realmwalker.rules.combat import FOE
from realmwalker.rules.engine import actions, check, durations, query
from tests.test_servants import battle, hero
from tests.test_wave4 import my_turn

ROOT = Path(__file__).resolve().parents[1]
F7 = ("ape badger constrictor_snake crocodile elephant elk giant_badger giant_crab giant_goat giant_seahorse "
      "giant_weasel goat lion octopus panther reef_shark tiger venomous_snake imp quasit pseudodragon sprite "
      "sphinx_of_wonder slaad_tadpole").split()
WATER = ("octopus", "giant_seahorse", "reef_shark")


@pytest.fixture(scope="module")
def tables(data):
    from realmwalker.world.tables import Tables

    return Tables(data)


def foe(b, cid):
    return next(f for f in b.fighters if f.side == FOE and f.cdef.get("statblock") == cid)


# ---------------------------------------------------------------------------- the data
def test_every_creature_is_in_with_its_numbers_and_a_picture(tables):
    tiles = json.loads((ROOT / "assets" / "tiles" / "tiles.json").read_text(encoding="utf-8"))
    tiles = tiles.get("tiles", tiles)
    for cid in F7:
        d = tables.creatures[cid]
        assert d["attacks"] and d["descriptions"] and f"creature/{cid}" in tiles, cid
    assert not check.problems(tables)
    lion, imp, elephant = tables.creatures["lion"], tables.creatures["imp"], tables.creatures["elephant"]
    assert (lion["ac"], lion["hp"], lion["cr"]) == (12, "4d10", 1.0)
    assert lion["multiattack_plan"] == [["rend"], ["rend", "roar"]]
    assert (imp["ac"], imp["hp"], imp["darkvision"]) == (13, "6d4+6", 120) and "devils_sight" in imp["traits"]
    assert imp["spellcasting"]["at_will"] == ["invisibility"] and imp["spellcasting"]["self_only"]
    assert (elephant["ac"], elephant["hp"], elephant["cr"]) == (12, "8d12+24", 4.0)
    trample = next(a for a in elephant["attacks"] if a["id"] == "trample")
    assert trample["bonus_action"] and trample["requires"] == "target_prone" and trample["single_save"]


def test_each_is_a_shape_and_the_water_breathers_never_a_friends(tables):
    beasts = shapes.forms(tables, ["beast"], 4.0)
    assert {c for c in F7 if tables.creatures[c]["kind"] == "beast"} <= set(beasts)
    assert {"imp", "quasit", "sprite", "sphinx_of_wonder"} <= set(shapes.forms(tables, "any", 1.0))
    b = battle(tables, [hero(tables, "fighter", xp=0)], ["bandit"], {0: (2, 4), 1: (8, 4)})
    me = b.fighters[0]
    for level in (1, 2, 4):
        me.char.level = level
        assert shapes.best(tables, me, ["beast"]) not in WATER
    weakest = shapes.worst(tables, me, ["beast"])
    assert weakest is not None  # (a foe may be one: the octopus is among the weakest)


# ---------------------------------------------------------------------------- the elephant's Trample
def test_trample_is_a_bonus_action_only_on_one_lying_down(tables):
    b = battle(tables, [hero(tables, "fighter")], ["elephant"], {0: (2, 4), 1: (3, 4)})
    me, el = b.fighters[0], foe(b, "elephant")
    my_turn(b, el)
    trample = next(o for o in b.attack_options(el) if o.extra.get("id") == "trample")
    assert b.attack_problem(el, trample, me) == "only at one lying down" and me not in b.targets_for(el, trample)
    durations.give(b, me, "prone", rounds=-1)
    assert b.attack_problem(el, trample, me) is None and me in b.targets_for(el, trample)
    opt = next(o for o in actions.options(b, el) if o.kind == "attack" and o.value.extra.get("id") == "trample")
    assert opt.cost == "bonus" and opt.available
    action, bonus = el.action, el.bonus
    assert b.do_attack(el, trample, me)
    assert el.bonus == bonus - 1 and el.action == action  # (the Action still to spend on its Gores)
    assert b.attack_problem(el, trample, me) == "no bonus action left this turn"


def test_the_elephant_tramples_after_its_gores(tables):
    b = battle(tables, [hero(tables, "fighter")], ["elephant"], {0: (2, 4), 1: (3, 4)})
    me, el = b.fighters[0], foe(b, "elephant")
    me.char.hp = me.char.max_hp = 500
    durations.give(b, me, "prone", rounds=-1)
    my_turn(b, el)
    tactics.take_turn(b, el)
    assert el.bonus == 0  # (its bonus action went on the Trample)


# ---------------------------------------------------------------------------- holds, stings and sleep
def test_a_crocodiles_hold_restrains_until_it_is_broken(tables):
    b = battle(tables, [hero(tables, "fighter")], ["crocodile"], {0: (2, 4), 1: (3, 4)})
    me, croc = b.fighters[0], foe(b, "crocodile")
    bite = next(o for o in b.attack_options(croc) if o.extra.get("id") == "bite")
    b._block_effects(croc, me, bite, bite.extra["on_hit"])
    assert "grappled" in me.conditions and "restrained" in me.conditions
    b._release(croc)
    assert "grappled" not in me.conditions and "restrained" not in me.conditions


def test_the_crocodile_bites_harder_at_the_one_it_holds(tables):
    b = battle(tables, [hero(tables, "fighter")], ["bandit"], {0: (2, 4), 1: (3, 4)})
    me, bandit = b.fighters[0], foe(b, "bandit")
    opt = b.attack_options(bandit)[0]
    opt.extra = {**opt.extra, "advantage_if": "target_grappled_by_self"}
    assert not query.attack_roll(b, bandit, me, opt).advantage
    durations.give(b, me, "grappled", rounds=-1, source=bandit)
    r = query.attack_roll(b, bandit, me, opt)
    assert r.advantage and "held" in r.notes


def test_the_pseudodragons_sting_sleeps_by_five_and_a_blow_wakes(tables, monkeypatch):
    b = battle(tables, [hero(tables, "fighter")], ["pseudodragon"], {0: (2, 4), 1: (3, 4)})
    me, pd = b.fighters[0], foe(b, "pseudodragon")
    me.char.hp = me.char.max_hp = 500
    sting = next(o for o in b.attack_options(pd) if o.extra.get("id") == "sting")
    monkeypatch.setattr(type(b), "_save", lambda self, f, ab, dc, **k: (self.__dict__.update(failed_by=2), False)[1])
    b._save_action(pd, sting, me)
    assert "poisoned" in me.conditions and "unconscious" not in me.conditions
    monkeypatch.setattr(type(b), "_save", lambda self, f, ab, dc, **k: (self.__dict__.update(failed_by=6), False)[1])
    b._save_action(pd, sting, me)
    assert "unconscious" in me.conditions
    durations.on_damage(b, me)
    assert "unconscious" not in me.conditions


def test_the_quasit_opens_with_its_scare(tables):
    b = battle(tables, [hero(tables, "fighter")], ["quasit"], {0: (2, 4), 1: (5, 4)})
    me, q = b.fighters[0], foe(b, "quasit")
    rend = next(o for o in b.attack_options(q) if o.extra.get("id") == "rend")
    scare = next(o for o in b.attack_options(q) if o.extra.get("id") == "scare")
    assert tactics._value(b, q, scare, me, (4, 4)) > tactics._value(b, q, rend, me, (4, 4))


# ---------------------------------------------------------------------------- the sphinx, the lion, the imp
def test_burst_of_ingenuity_turns_a_friends_near_miss_twice_a_day(tables):
    b = battle(tables, [hero(tables, "fighter")], ["sphinx_of_wonder", "bandit"], {0: (2, 4), 1: (7, 4), 2: (8, 6)})
    sphinx, bandit = foe(b, "sphinx_of_wonder"), foe(b, "bandit")
    from realmwalker.rules.engine import events

    ev = events.emit(b, "d20_after", actor=bandit, roll="save", ability="dex", natural=10, bonus=1, dc=12, ok=False)
    assert ev.ok and not sphinx.reaction and sphinx.creature.uses["burst_of_ingenuity"] == 1
    sphinx.reaction = True
    far = events.emit(b, "d20_after", actor=bandit, roll="save", ability="dex", natural=5, bonus=1, dc=12, ok=False)
    assert not far.ok and sphinx.reaction  # (+2 would not turn it: kept)
    events.emit(b, "d20_after", actor=sphinx, roll="save", ability="wis", natural=10, bonus=1, dc=13, ok=False)
    sphinx.reaction = True
    last = events.emit(b, "d20_after", actor=bandit, roll="save", ability="dex", natural=10, bonus=1, dc=12, ok=False)
    assert not last.ok and sphinx.creature.uses["burst_of_ingenuity"] == 0


def test_the_lion_leaps_25_feet_with_a_run(tables):
    b = battle(tables, [hero(tables, "fighter")], ["lion", "tiger"], {0: (2, 4), 1: (8, 4), 2: (8, 8)})
    lion, tiger = foe(b, "lion"), foe(b, "tiger")
    assert lion.jump == (17 // 2, 25) and tiger.jump == (17 // 2, 17)


def test_the_imp_turns_invisible_on_itself_only(tables):
    b = battle(tables, [hero(tables, "fighter")], ["imp", "quasit"], {0: (2, 4), 1: (8, 4), 2: (9, 5)})
    imp, quasit = foe(b, "imp"), foe(b, "quasit")
    assert b.spell_targets(imp, "invisibility") == [imp]
    my_turn(b, imp)
    assert not b.creature_cast(imp, "invisibility", quasit)
    assert b.creature_cast(imp, "invisibility", imp) and "invisible" in imp.conditions


# ---------------------------------------------------------------------------- met in the land
def test_they_are_met_where_they_live(tables, data):
    enc = data.get("creatures.json")["encounters"]
    lives = {"lion": "savanna", "elephant": "savanna", "tiger": "jungle", "ape": "jungle", "crocodile": "marsh",
             "giant_crab": "coast", "giant_goat": "mountains", "elk": "tundra", "sprite": "fey_forest",
             "sphinx_of_wonder": "desert", "venomous_snake": "desert", "pseudodragon": "hills", "badger": "forest",
             "giant_badger": "forest", "constrictor_snake": "jungle", "goat": "hills", "giant_weasel": "plains",
             "panther": "jungle"}
    for cid, biome in lives.items():
        assert any(any(m[0] == cid for m in e["members"]) and biome in e["biomes"] and e["weight"] > 0
                   for e in enc.values()), cid
    for cid in WATER:  # (under the sea: Expansion 22)
        assert not any(any(m[0] == cid for m in e["members"]) for e in enc.values())
    for familiar in ("imp", "quasit"):
        assert any({m[0] for m in e["members"]} >= {"cult_fanatic", familiar} for e in enc.values())
    assert "slaad_tadpoles" in data.get("creatures.json")["site_inhabitants"]["tower"]
    assert all(len(e["intro"]) >= 3 for e in enc.values())
