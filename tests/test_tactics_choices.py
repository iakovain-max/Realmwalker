"""The enemy (and Auto) plays the whole game (docs/EXPANSIONS.md §4.7): each choice beyond a plain blow is made where it
pays, in a fight built for it - rising out of reach and coming down to strike, waiting below a flier with a readied
blow, breaking down a door, searching for the hidden, a lurker hiding, a shove for the band, Help for a stronger
friend, a grab on a caster, a caster on guard over its spell. And the rules those choices lean on."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import grid, tactics
from realmwalker.rules.combat import FOE, PARTY, Battle, Env
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import actions, durations
from realmwalker.world.tables import Tables
from tests.test_combat import battle, foes, hero, hero_at, turn_of, walls


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def calls(b, name):
    """Count the times the tactics call one of the battle's actions on this battle."""
    seen = []
    real = getattr(b, name)

    def counted(*a, **k):
        seen.append(a)
        return real(*a, **k)
    setattr(b, name, counted)
    return seen


def spend_breath(b, f):
    """Its breath (or web) used up: it must fight some other way this turn."""
    for o in b.attack_options(f):
        if o.extra.get("recharge"):
            f.recharge[o.extra["name"]] = False


def test_a_dragon_breathes_then_rises_out_of_reach(tables):
    b = battle(tables, [hero_at(tables, "fighter", 5)], foes(tables, "young_dragon"), spots={0: (4, 4), 1: (7, 4)})
    me, drake = b.fighters
    turn_of(b, drake)
    tactics.take_turn(b, drake)
    assert any(e["kind"] == "cast" and e.get("by") == drake.id for e in b.events)  # the breath
    assert drake.z > 0 and b.gap(me, drake) > b.reach_of(me)


def test_a_flier_comes_down_to_strike_and_a_readied_blow_meets_it(tables):
    b = battle(tables, [hero_at(tables, "fighter", 5)], foes(tables, "young_dragon"), spots={0: (4, 4), 1: (5, 4)})
    me, drake = b.fighters
    drake.z = 20
    me.auto = True
    turn_of(b, me)
    tactics.take_turn(b, me)
    assert me.readied == "reach"  # nothing to reach up there: wait below with a blow ready
    turn_of(b, drake)
    spend_breath(b, drake)
    tactics.take_turn(b, drake)
    assert any(e["kind"] == "fly" and e["z"] < 20 for e in b.events)  # down it came
    assert any(e["kind"] == "attack" and e.get("by") == me.id for e in b.events)  # into the readied blow
    assert any(e["kind"] == "attack" and e.get("by") == drake.id for e in b.events)


def test_rising_out_of_reach_provokes(tables):
    b = battle(tables, [hero_at(tables, "fighter", 5)], foes(tables, "young_dragon"), spots={0: (4, 4), 1: (5, 4)})
    me, drake = b.fighters
    turn_of(b, drake)
    assert b.do_fly(drake, 20)
    assert any(e["kind"] == "opportunity" and e["by"] == me.id for e in b.events)


def test_a_brute_breaks_down_a_locked_door_to_reach_them(tables):
    fld = walls(tables, wall_stone=[(6, y) for y in range(8) if y != 4], door_locked=[(6, 4)])
    b = battle(tables, [hero(tables)], foes(tables, "orc"), field=fld, spots={0: (2, 4), 1: (8, 4)})
    me, orc = b.fighters  # (an orc: an ogre is too big for the doorway)
    seen = calls(b, "attack_object")
    for _ in range(4):
        turn_of(b, orc)
        tactics.take_turn(b, orc)
        if b.field.name(6, 4) != "door_locked":
            break
    assert seen and all(a[2] == (6, 4) for a in seen)


def test_striking_a_thing_out_of_reach_spends_nothing(tables):
    fld = walls(tables, barrels=[(8, 4)])
    b = battle(tables, [hero(tables)], foes(tables, "wolf"), field=fld, spots={0: (2, 4), 1: (11, 1)})
    me = b.fighters[0]
    turn_of(b, me)
    sword = next(o for o in b.attack_options(me) if o.is_melee and o.available)
    action, attacks = me.action, me.attacks_left
    assert not b.attack_object(me, sword, (8, 4))
    assert (me.action, me.attacks_left) == (action, attacks)
    opt = next(o for o in actions.options(b, me) if o.kind == "object")
    assert not opt.available and opt.why == "nothing in reach to break"


def test_a_creature_searches_when_nobody_is_in_sight(tables):
    b = battle(tables, [hero(tables)], foes(tables, "bandit"), spots={0: (2, 4), 1: (10, 4)})
    me, bandit = b.fighters
    me.hidden = 30
    seen = calls(b, "do_search")
    turn_of(b, bandit)
    tactics.take_turn(b, bandit)
    assert seen


def test_a_lurker_hides_rather_than_running_in(tables):
    fld = walls(tables, width=20, tall_grass=[(x, y) for x in range(14, 20) for y in range(8)])
    b = battle(tables, [hero(tables)], foes(tables, "giant_spider"), field=fld, spots={0: (1, 4), 1: (16, 3)})
    me, spider = b.fighters
    seen = calls(b, "do_hide")
    turn_of(b, spider)
    spend_breath(b, spider)  # (no web to throw from afar)
    tactics.take_turn(b, spider)
    assert seen


def test_a_shove_for_the_band_and_help_for_a_stronger_friend(tables):
    weak = hero_at(tables, "wizard", 5)
    weak.abilities["str"] = weak.abilities["dex"] = 6  # easy to knock down
    b = battle(tables, [weak], foes(tables, "bandit_captain", "troll", "ogre"),
               spots={0: (5, 4), 1: (4, 4), 2: (6, 4), 3: (5, 2)})
    me, captain = b.fighters[0], b.fighters[1]
    shoves = calls(b, "do_shove")
    turn_of(b, captain)
    tactics.take_turn(b, captain)
    assert shoves and shoves[0][2] == "prone"
    b = battle(tables, [hero_at(tables, "fighter", 5)], foes(tables, "commoner", "troll"),
               spots={0: (5, 4), 1: (4, 4), 2: (6, 4)})
    commoner = b.fighters[1]
    helped = calls(b, "do_help")
    turn_of(b, commoner)
    tactics.take_turn(b, commoner)
    assert helped


def test_a_clever_fighter_grabs_a_caster_who_would_step_away(tables):
    b = battle(tables, [hero(tables, "wizard")], foes(tables, "bandit_captain"), spots={0: (4, 4), 1: (5, 4)})
    grabs = calls(b, "do_grapple")
    captain = b.fighters[1]
    turn_of(b, captain)
    tactics.take_turn(b, captain)
    assert grabs


def test_a_caster_holding_a_spell_keeps_away_or_stands_on_guard(tables):
    b = battle(tables, [hero_at(tables, "fighter", 5)], foes(tables, "acolyte"), spots={0: (4, 4), 1: (5, 4)})
    me, acolyte = b.fighters
    acolyte.concentration = {"spell": "bless", "rounds": 10}
    acolyte.slots = [0] * len(acolyte.slots)
    turn_of(b, acolyte)
    tactics.take_turn(b, acolyte)
    assert acolyte.dodging or b.gap(me, acolyte) > 1


def test_a_creature_taken_over_comes_back_when_the_condition_ends(tables):
    a, friend = hero(tables), hero(tables, "fighter", seed=4)
    cr = spawn(tables, "bandit", RNG(1, "foe"), 1)
    b = Battle(tables, [a, friend], [cr], Env(), RNG(1, "battle"), spots={0: (3, 4), 1: (4, 4), 2: (9, 4)})
    b.start()
    me, fr, bandit = b.fighters
    durations.give(b, fr, "charmed", rounds=1, source=bandit, control="foe")
    assert fr.team == "foe"
    fr.conditions.pop("charmed")  # (a countdown or a save ends it without its ending being tidied away)
    assert fr.team == "party"


def test_only_the_party_can_influence_and_antimagic_is_in_the_lists(tables):
    b = battle(tables, [hero(tables, "wizard")], foes(tables, "bandit"), spots={0: (2, 4), 1: (8, 4)})
    me, bandit = b.fighters
    assert not [o for o in actions.options(b, bandit) if o.id.startswith("action:influence")]
    assert [o for o in actions.options(b, me) if o.id.startswith("action:influence")]
    from realmwalker.rules.combat import Zone

    b.zones.append(Zone(99, "antimagic", set(me.cells), owner=bandit.id, rounds=10))
    turn_of(b, me)
    spells = [o for o in actions.options(b, me) if o.kind == "cast"]
    assert spells and not any(o.available for o in spells)
    assert all(o.why == "magic does not work here" for o in spells)


def test_a_long_jump_is_the_whole_way_moved(tables):
    fld = walls(tables, river=[(5, y) for y in range(8)] + [(6, y) for y in range(8)])
    c = hero(tables)
    c.abilities["str"] = 14  # a running leap of 14 feet: one square cleared (10 ft), not two (15 ft)
    b = battle(tables, [c], foes(tables, "wolf"), field=fld, spots={0: (2, 4), 1: (10, 1)})
    f = b.fighters[0]
    turn_of(b, f)
    tree = b.move_tree(f)
    route = grid.route(tree, (7, 4))
    assert not route or all(max(abs(a[0] - b2[0]), abs(a[1] - b2[1])) < 3 for a, b2 in zip([(2, 4)] + route, route))


# ---------------------------------------------------------------------------- the one list keeps its word
ACTION_CALLS = {
    "dash": lambda b, f, o: b.do_dash(f), "disengage": lambda b, f, o: b.do_disengage(f),
    "dodge": lambda b, f, o: b.do_dodge(f), "hide": lambda b, f, o: b.do_hide(f),
    "help": lambda b, f, o: b.do_help(f, o.targets[0]), "study": lambda b, f, o: b.do_study(f, o.targets[0]),
    "search": lambda b, f, o: b.do_search(f), "ready": lambda b, f, o: b.do_ready(f, o.value),
    "prone": lambda b, f, o: b.do_shove(f, o.targets[0], "prone"),
    "push": lambda b, f, o: b.do_shove(f, o.targets[0], "push"),
    "grapple": lambda b, f, o: b.do_grapple(f, o.targets[0]), "escape": lambda b, f, o: b.do_escape(f),
}


def spent(f) -> tuple:
    return (f.action, f.bonus, f.attacks_left, f.move_left, f.hidden, bool(f.readied))


def try_option(b, f, o) -> bool:
    """Do it on this battle: True if the battle took it (said so, or something of the turn was spent)."""
    before = spent(f)
    if o.kind == "attack":
        return b.do_attack(f, o.value, o.targets[0])
    if o.kind == "object":
        cell = next(iter(o.points))
        return b.attack_object(f, o.value[cell], cell)
    if o.kind == "cast":
        target = o.targets[0] if o.aim == "creature" else None
        point = next(iter(sorted(o.points))) if o.aim == "point" else None
        return b.do_cast(f, o.value, target, point=point)
    if o.kind == "move":
        return b.do_fly(f, o.value)
    if o.kind == "action":
        key = o.id.split(":")[1]
        if key not in ACTION_CALLS:
            return True  # (Influence and leaving end the fight: proven in their own tests)
        ACTION_CALLS[key](b, f, o)
        return spent(f) != before
    return True


@pytest.mark.parametrize("cls, foe, gap", [("fighter", "bandit", 1), ("wizard", "bandit", 4), ("cleric", "skeleton", 2),
                                           ("rogue", "wolf", 1)])
def test_every_option_the_list_calls_possible_is_taken(tables, cls, foe, gap):
    def fresh():  # the same fight, made again (seeded): each option is tried on its own copy of the moment
        b = battle(tables, [hero_at(tables, cls, 5)], foes(tables, foe), field=walls(tables, barrels=[(2, 5)]),
                   spots={0: (3, 4), 1: (3 + gap, 4)})
        turn_of(b, b.fighters[0])
        return b, b.fighters[0]

    b, f = fresh()
    refused = []
    for o in actions.options(b, f):
        if not o.available or o.kind in ("ability", "item"):
            continue
        if o.aim == "creature" and not o.targets or o.aim == "point" and not o.points:
            refused.append(f"{o.id}: available, but nothing to aim it at")
            continue
        twin, tf = fresh()
        same = next(x for x in actions.options(twin, tf) if x.id == o.id)
        if not try_option(twin, tf, same):
            refused.append(o.id)
    assert not refused
