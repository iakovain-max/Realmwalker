"""The spells as definitions (data/spells.json effects, run by rules/engine/effects.py), in their 2024 versions:
what each one does in a fight, and how long it lasts."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import durations, effects
from realmwalker.rules.inventory import add_item
from realmwalker.rules.progression import award_xp
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def hero(tables, cls="wizard", race="human", seed=1, xp=0):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race(race)
    b.set_class(cls)
    b.set_background("sage")
    c = b.build()
    if xp:
        award_xp(c, xp, tables, RNG(seed), auto=True)
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


def always(b, ok: bool):
    b._save = lambda *a, **k: ok


def sure_hits(b):
    b.hit_seq = []
    orig = b._attack

    def hit(att, opt, target, **kw):
        opt.bonus = 99
        return orig(att, opt, target, **kw)
    b._attack = hit


# ---------------------------------------------------------------------------- the data
def test_every_spell_is_a_definition_the_kernel_can_run(tables):
    for sid, sp in tables.spells.defs.items():
        assert sp["effects"], sid
        assert "kind" not in sp, sid
        for o in spellrules.ops(sp):
            assert o["op"] in effects.OPS, (sid, o["op"])


def test_the_2024_numbers(tables):
    s = tables.spells
    assert spellrules.op(s["cure_wounds"], "heal")["dice"] == "2d8"
    assert spellrules.op(s["healing_word"], "heal")["dice"] == "2d4"
    assert spellrules.op(s["mass_cure_wounds"], "heal")["dice"] == "5d8"
    assert s["chill_touch"]["range"] == "touch"
    assert spellrules.op(s["inflict_wounds"], "save")["ability"] == "con"
    assert s["spiritual_weapon"].get("concentration") and s["stoneskin"].get("concentration")
    assert s["spare_the_dying"]["range"] == 15
    assert s["sleep"]["area"]["size"] == 5 and s["sleep"]["range"] == 60
    assert {t for _, t, _ in spellrules.damage_parts(spellrules.op(s["ice_storm"], "save"))} == {"bludgeoning", "cold"}
    assert {t for _, t, _ in spellrules.damage_parts(spellrules.op(s["flame_strike"], "save"))} == {"fire", "radiant"}
    assert s["death_ward"]["rounds"] == 4800  # eight hours


# ---------------------------------------------------------------------------- timings by the caster's turn
def test_ray_of_frost_slows_through_the_targets_turn(tables):
    w = hero(tables)
    b = fight(tables, [w], ["bandit"], {0: (2, 4), 1: (8, 4)})
    me, bandit = b.fighters
    sure_hits(b)
    my_turn(b, me)
    assert b.do_cast(me, "ray_of_frost", bandit)
    full = 30
    b.end_turn()
    b._start_of_turn(bandit)
    assert bandit.speed == full - 10 and bandit.move_left <= full - 10  # its own turn is slowed
    durations.tick(b, me, "turn_start")  # the start of the caster's next turn
    assert bandit.speed == full


def test_chill_touch_stops_healing_until_the_end_of_your_next_turn(tables):
    w = hero(tables)
    b = fight(tables, [w], ["bandit"], {0: (2, 4), 1: (3, 4)})
    me, bandit = b.fighters
    sure_hits(b)
    my_turn(b, me)
    assert b.do_cast(me, "chill_touch", bandit)
    assert bandit.no_heal
    durations.tick(b, me, "turn_end")  # this turn's end does not count
    assert bandit.no_heal
    durations.tick(b, me, "turn_end")
    assert not bandit.no_heal


def test_shocking_grasp_stops_opportunity_attacks_not_other_reactions(tables):
    w = hero(tables)
    b = fight(tables, [w], ["bandit"], {0: (2, 4), 1: (3, 4)})
    me, bandit = b.fighters
    sure_hits(b)
    my_turn(b, me)
    assert b.do_cast(me, "shocking_grasp", bandit)
    assert bandit.reaction and not bandit.can_opportunity
    durations.tick(b, bandit, "turn_start")
    assert bandit.can_opportunity


def test_guiding_bolts_mark_is_spent_by_the_next_roll_hit_or_miss(tables):
    c = hero(tables, "cleric")
    b = fight(tables, [c], ["bandit"], {0: (2, 4), 1: (8, 4)})
    me, bandit = b.fighters
    sure_hits(b)
    my_turn(b, me)
    assert b.do_cast(me, "guiding_bolt", bandit)
    assert bandit.marked
    b._attack = Battle._attack.__get__(b)
    opt = next(o for o in b.attack_options(me) if o.available)
    opt.bonus = -99  # a sure miss
    b._attack(me, opt, bandit)
    assert not bandit.marked


# ---------------------------------------------------------------------------- saves and conditions
def test_inflict_wounds_is_a_constitution_save_for_half(tables):
    c = hero(tables, "cleric")
    b = fight(tables, [c], ["ogre"], {0: (2, 4), 1: (3, 4)})
    me, ogre = b.fighters
    always(b, True)
    my_turn(b, me)
    before = ogre.hp
    assert b.do_cast(me, "inflict_wounds", ogre)
    assert 1 <= before - ogre.hp <= 10  # half of 2d10


def test_hold_person_holds_one_more_with_a_higher_slot_and_ends_with_concentration(tables):
    w = hero(tables, xp=6500)  # level 5: third-level slots
    b = fight(tables, [w], ["bandit", "bandit", "wolf"], {0: (2, 4), 1: (6, 4), 2: (6, 6), 3: (7, 2)})
    me, a, bb, wolf = b.fighters
    always(b, False)
    my_turn(b, me)
    assert b.do_cast(me, "hold_person", a, slot_level=3)
    assert "paralyzed" in a.conditions and "paralyzed" in bb.conditions and not wolf.conditions
    b._end_concentration(me, quiet=True)
    assert "paralyzed" not in a.conditions and "paralyzed" not in bb.conditions


def test_command_grovel_costs_the_target_its_next_turn(tables):
    c = hero(tables, "cleric")
    b = fight(tables, [c], ["bandit"], {0: (2, 4), 1: (8, 4)})
    me, bandit = b.fighters
    always(b, False)
    my_turn(b, me)
    assert b.do_cast(me, "command", bandit)
    b.end_turn()
    b.order = [bandit.id, me.id]
    b.turn, b.turn_started = 0, False
    start = (bandit.x, bandit.y)
    b.step()
    assert "prone" in bandit.conditions and (bandit.x, bandit.y) == start and b.current is me


def test_lesser_restoration_ends_one_condition(tables):
    c = hero(tables, "cleric", xp=900)  # level 3
    friend = hero(tables, "fighter", seed=2)
    b = fight(tables, [c, friend], ["bandit"], {0: (2, 4), 1: (3, 4), 2: (9, 4)})
    me, fr, _ = b.fighters
    fr.conditions.update({"paralyzed": -1, "poisoned": 10})
    my_turn(b, me)
    assert b.do_cast(me, "lesser_restoration", fr)
    assert "paralyzed" not in fr.conditions and "poisoned" in fr.conditions


def test_spiritual_weapon_is_held_by_concentration(tables):
    c = hero(tables, "cleric", xp=900)
    b = fight(tables, [c], ["bandit"], {0: (2, 4), 1: (8, 4)})
    me, bandit = b.fighters
    my_turn(b, me)
    assert b.do_cast(me, "spiritual_weapon", point=(7, 4))
    assert b.tokens and me.concentration is not None
    b._end_concentration(me, quiet=True)
    assert not b.tokens


def test_spare_the_dying_reaches_15_feet_and_30_from_level_5(tables):
    c = hero(tables, "cleric")
    assert Battle.spell_range(None, tables.spells["spare_the_dying"]) == 15
    b = fight(tables, [c], ["bandit"], {0: (2, 4), 1: (9, 4)})
    assert b.spell_range(tables.spells["spare_the_dying"], b.fighters[0]) == 15
    c5 = hero(tables, "cleric", xp=6500)
    b = fight(tables, [c5], ["bandit"], {0: (2, 4), 1: (9, 4)})
    assert b.spell_range(tables.spells["spare_the_dying"], b.fighters[0]) == 30


def test_mass_cure_wounds_heals_allies_in_its_sphere_only(tables):
    c = hero(tables, "cleric", xp=6500 * 4)
    c.level = max(c.level, 9)
    friends = [hero(tables, "fighter", seed=i) for i in range(2, 4)]
    b = fight(tables, [c] + friends, ["bandit"], {0: (2, 4), 1: (5, 4), 2: (6, 5), 3: (7, 4)})
    me, f1, f2, bandit = b.fighters
    for x in (me, f1, f2, bandit):
        x.hp = 1
    c.spells["slots_used"] = [0] * 9
    from realmwalker.rules.spells import slots_left

    if not any(slots_left(c, tables)[4:5]):
        pytest.skip("no fifth-level slot at this level in this data")
    my_turn(b, me)
    assert b.do_cast(me, "mass_cure_wounds", point=(6, 4), slot_level=5)
    assert f1.hp > 1 and f2.hp > 1 and bandit.hp == 1


def test_revivify_needs_and_consumes_a_diamond(tables):
    c = hero(tables, "cleric", xp=2700)  # level 4? third-level slots at 5
    c.level = 5
    friend = hero(tables, "fighter", seed=2)
    b = fight(tables, [c, friend], ["bandit"], {0: (2, 4), 1: (3, 4), 2: (9, 4)})
    me, fr, _ = b.fighters
    b._kill(fr, "a test")
    my_turn(b, me)
    ok = {s: o for s, o, _ in b.spell_options(me)}
    if "revivify" not in ok:
        pytest.skip("revivify not known at this level")
    assert not ok["revivify"]
    add_item(c, tables.items, "diamond", 1)
    assert b.do_cast(me, "revivify", fr)
    assert fr.state == "fighting" and fr.hp == 1 and not any(i.def_id == "diamond" for i in c.inventory)
