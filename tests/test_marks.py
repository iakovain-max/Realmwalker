"""The marks spells leave in a fight (rules/engine/marks.py, Expansion 3 part D) and the catalogue's new ground: each
one doing what its card says, in a real battle."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import spells as spellrules
from realmwalker.rules import tactics
from realmwalker.rules.combat import FOE, PARTY, Battle, Env, Zone
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import marks, query
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


def test_cantrips_grow_with_the_caster(tables):
    """Fixed in D.1: a party member's cantrip dice grow at levels 5, 11 and 17 (they never did)."""
    w = hero(tables, xp=6500)  # level 5
    b = fight(tables, [w], ["ogre"], {0: (2, 4), 1: (8, 4)})
    me, ogre = b.fighters
    my_turn(b, me)
    seen = []
    real = b._attack
    b._attack = lambda att, opt, target, **k: seen.append(opt.damage) or real(att, opt, target, **k)
    assert b.do_cast(me, "fire_bolt", ogre)
    assert seen and seen[0].startswith("2d10")


def test_an_outlined_creature_is_easy_to_hit_and_a_blurred_one_hard(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (3, 4)})
    me, bandit = b.fighters
    opt = next(o for o in b.attack_options(bandit) if o.is_melee)
    me.buffs.append({"outlined": True, "source": "faerie_fire"})
    assert "outlined" in " ".join(query.attack_roll(b, bandit, me, opt).adv)
    me.buffs = [{"blurred": True, "source": "blur"}]
    assert "blurred" in " ".join(query.attack_roll(b, bandit, me, opt).dis)


def test_sanctuary_turns_a_blow_aside_until_the_warded_one_strikes(tables):
    b = fight(tables, [hero(tables, "cleric")], ["bandit"], {0: (2, 4), 1: (3, 4)})
    me, bandit = b.fighters
    me.buffs.append({"sanctuary": 30, "source": "sanctuary"})
    hp = me.hp
    opt = next(o for o in b.attack_options(bandit) if o.is_melee)
    assert b._attack(bandit, opt, me) is False and me.hp == hp
    assert any("Sanctuary" in t for t, _ in b.log)
    my_turn(b, me)
    mine = next(o for o in b.attack_options(me) if o.is_melee)
    b._attack(me, mine, bandit)
    assert not any(bf.get("sanctuary") for bf in me.buffs)


def test_mirror_images_take_hits_and_vanish(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (3, 4)})
    me, bandit = b.fighters
    me.buffs.append({"images": 3, "source": "mirror_image"})
    b.rng.randint = lambda lo, hi: hi  # (every d6 a 6: the image is struck)
    assert marks.image_takes_it(b, bandit, me)
    assert next(bf for bf in me.buffs if bf.get("images"))["images"] == 2


def test_hex_hurts_more_only_from_its_caster(tables):
    b = fight(tables, [hero(tables, "fighter"), hero(tables, "fighter", seed=2)], ["ogre"],
              {0: (2, 4), 1: (2, 5), 2: (3, 4)})
    me, other, ogre = b.fighters
    ogre.buffs.append({"quarry": "1d6", "quarry_type": "necrotic", "by": me.id, "source": "hex"})
    opt = next(o for o in b.attack_options(me) if o.is_melee)
    assert marks.extra_hits(b, me, ogre, opt, False)[0][1] == "necrotic"
    assert not marks.extra_hits(b, other, ogre, opt, False)


def test_spike_growth_cuts_every_square_walked(tables):
    b = fight(tables, [hero(tables, "fighter")], ["wolf"], {0: (1, 1), 1: (12, 8)})
    me, wolf = b.fighters
    cells = {(x, y) for x in range(2, 6) for y in range(0, 4)}
    b._add_zone(Zone(b._zone_id(), "spikes", cells, owner=wolf.id, damage="2d4", damage_type="piercing", save=""))
    my_turn(b, me)
    hp = me.hp
    b.walk(me, [(2, 1), (3, 1), (4, 1)])
    hurt = sum(1 for t, _ in b.log if "Thorns tear" in t)
    assert hurt == 3 and me.hp < hp


def test_no_spell_with_words_is_cast_in_a_silence(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (8, 4)})
    me, bandit = b.fighters
    b._add_zone(Zone(b._zone_id(), "silence", {(2, 4), (3, 4)}, owner=bandit.id, save=""))
    my_turn(b, me)
    opts = {sid: (ok, why) for sid, ok, why in b.spell_options(me)}
    assert opts["fire_bolt"][0] is False and "Silence" in opts["fire_bolt"][1]


def test_heroism_and_harm_over_time_come_with_the_turns(tables):
    b = fight(tables, [hero(tables, "fighter")], ["bandit"], {0: (2, 4), 1: (8, 4)})
    me, bandit = b.fighters
    me.buffs.append({"heroism": 4, "immune": ["frightened"], "source": "heroism"})
    bandit.buffs.append({"dot": "2d4", "dot_type": "acid", "dot_at": "end", "dot_once": True, "by": me.id,
                         "source": "melfs_acid_arrow"})
    my_turn(b, me)
    assert me.temp_hp == 4 and query.condition_immune(me, "frightened")
    hp = bandit.hp
    b._end_of_turn(bandit)
    assert bandit.hp < hp and not any(bf.get("dot") for bf in bandit.buffs)


def test_a_maddened_foe_strikes_its_own_friend(tables):
    b = fight(tables, [hero(tables)], ["bandit", "bandit"], {0: (10, 8), 1: (3, 4), 2: (4, 4)})
    me, b1, b2 = b.fighters
    b1.buffs.append({"maddened": me.id, "source": "crown_of_madness"})
    my_turn(b, b1)
    struck = []
    real = b._attack
    b._attack = lambda att, opt, target, **k: struck.append(target) or real(att, opt, target, **k)
    tactics.take_turn(b, b1)
    assert struck and struck[0] is b2


def test_a_lasting_spell_remembers_its_slot(tables):
    c = hero(tables)
    spell = {"name": "Test", "level": 2, "rounds": 600,
             "effects": [{"op": "modifier", "buff": {"weapon_plus": 1}, "by_level": {"weapon_plus": {"4": 2, "6": 3}}}]}
    assert spellrules.buff_of(spell, 2)["weapon_plus"] == 1
    assert spellrules.buff_of(spell, 5)["weapon_plus"] == 2
    assert spellrules.buff_of(spell, 7)["weapon_plus"] == 3
    m = {"buff": {"dot": "1d6"}, "per_up": {"dot": "1d6"}}
    assert spellrules.buff_at(m, 3, {"level": 1})["dot"] == "3d6"


# ---------------------------------------------------------------------------- from the fresh review
def test_armor_of_agathys_answers_the_blow_that_breaks_it(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (3, 4)})
    me, bandit = b.fighters
    me.temp_hp = 5
    me.buffs.append({"retaliate": 5, "retaliate_type": "cold", "source": "armor_of_agathys"})
    opt = next(o for o in b.attack_options(bandit) if o.is_melee)
    hp = bandit.hp
    marks.after_hit(b, bandit, me, opt, guarded=True)  # (its pool already spent by the blow)
    me.temp_hp = 0
    marks.after_hit(b, bandit, me, opt, guarded=True)
    assert bandit.hp < hp and not any(bf.get("retaliate") for bf in me.buffs)


def test_hellish_rebuke_never_answers_a_friend(tables, monkeypatch):
    b = fight(tables, [hero(tables), hero(tables, seed=2)], ["bandit"], {0: (2, 4), 1: (3, 4), 2: (8, 4)})
    me, friend, bandit = b.fighters
    monkeypatch.setattr(spellrules, "known_spells", lambda char, t: ["hellish_rebuke"])
    assert b._rebuke(me, friend) is False
    assert b._rebuke(me, bandit) is True and not me.reaction


def test_sanctuary_is_one_save_against_a_spell_attack(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (8, 4)})
    me, bandit = b.fighters
    bandit.buffs.append({"sanctuary": 30, "source": "sanctuary"})
    saves = []
    real = b._save
    b._save = lambda f, ability, dc, **k: saves.append(ability) or real(f, ability, dc, **k)
    my_turn(b, me)
    b.do_cast(me, "fire_bolt", bandit)
    assert saves.count("wis") == 1


def test_entangle_holds_those_inside_until_it_ends(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (8, 4)})
    me, bandit = b.fighters
    b._save = lambda *a, **k: False
    my_turn(b, me)
    b.cast(me, "entangle", tables.spells["entangle"], None, (8, 4), up=0, mod=3, dc=14, bonus=5, mult=1, level=1)
    assert "restrained" in bandit.conditions
    b._end_concentration(me, quiet=True)
    assert "restrained" not in bandit.conditions


def test_witch_bolt_burns_again_without_a_slot(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (8, 4)})
    me, bandit = b.fighters
    my_turn(b, me)
    b.cast(me, "witch_bolt", tables.spells["witch_bolt"], bandit, None, up=0, mod=3, dc=14, bonus=5, mult=1, level=1)
    slots = list(me.char.spells.get("slots_used", []))
    my_turn(b, me)
    hp = bandit.hp
    assert b.do_cast(me, "witch_bolt_again", bandit)
    assert bandit.hp < hp and list(me.char.spells.get("slots_used", [])) == slots


def test_the_auto_does_not_cast_a_blessing_already_on(tables):
    from realmwalker.rules.engine import estimates

    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (3, 4)})
    me, bandit = b.fighters
    my_turn(b, me)
    assert estimates.spell_value(b, me, "mirror_image").total() > 0.5
    me.buffs.append({"images": 3, "source": "mirror_image", "rounds": 10})
    assert estimates.spell_value(b, me, "mirror_image").total() <= 0.5
