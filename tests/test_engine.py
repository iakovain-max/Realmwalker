"""The rules kernel (realmwalker/rules/engine): the 2024 conditions as data, the numbers asked in one place, the hooks
of traits and features, and the start-up check that the data names only what the code has."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import grid
from realmwalker.rules.combat import Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import check, conditions, events, query
from realmwalker.rules.engine import traits as trs
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def hero(tables, cls="fighter", race="human", seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race(race)
    b.set_class(cls)
    b.set_background("soldier")
    return b.build()


def duel(tables, foe="bandit", gap=1, cls="fighter", race="human", seed=1):
    """A hero and one foe on an open field, `gap` squares apart, in good light."""
    c = hero(tables, cls, race, seed)
    cr = spawn(tables, foe, RNG(seed, "foe"), 1)
    b = Battle(tables, [c], [cr], Env(), RNG(seed, "battle"), spots={0: (3, 4), 1: (3 + gap, 4)})
    b.start()
    me, them = b.fighters
    return b, me, them


def weapon(b, f):
    return next(o for o in b.attack_options(f) if o.is_melee and o.available)


# ---------------------------------------------------------------------------- the data and the check
def test_the_real_data_passes_the_kernel_check(tables):
    assert check.problems(tables) == []


def test_the_check_finds_what_the_code_lacks(tables):
    t = copy.copy(tables)
    t.traits = {"traits": {**tables.traits["traits"],
                           "bad": {"name": "Bad", "text": "x",
                                   "modifiers": [{"glow": 1}, {"attack": "advantage", "when": ["full_moon"]}],
                                   "hooks": [{"event": "teatime", "as": "self", "handler": "nobody"}]}}}
    t.conditions = {**tables.conditions, "conditions": {k: v for k, v in tables.conditions["conditions"].items()
                                                        if k != "stunned"}}
    found = "\n".join(check.problems(t))
    for bit in ("glow", "full_moon", "teatime", "nobody", "'stunned'"):
        assert bit in found, bit


def test_every_condition_of_the_2024_rules_is_there(tables):
    assert set(conditions.IDS) <= set(conditions.table(tables))
    assert conditions.exhaustion(tables)["d20_per_level"] == -2  # PHB p. 369 (PDF), checked on the page
    assert conditions.exhaustion(tables)["speed_per_level"] == -5
    assert conditions.exhaustion(tables)["levels"] == 6


def test_conditions_bring_what_they_include(tables):
    assert conditions.expand(tables, {"unconscious"}) == {"unconscious", "incapacitated", "prone"}
    for cid in ("paralyzed", "petrified", "stunned"):
        assert "incapacitated" in conditions.expand(tables, {cid})
    assert conditions.expand(tables, {"made_up"}) == frozenset()


# ---------------------------------------------------------------------------- the conditions in a fight
@pytest.mark.parametrize("cid", ["blinded", "paralyzed", "petrified", "restrained", "stunned", "unconscious"])
def test_attacks_against_the_helpless_have_advantage(tables, cid):
    b, me, them = duel(tables)
    them.conditions[cid] = -1
    r = query.attack_roll(b, me, them, weapon(b, me))
    assert r.advantage and any(cid[:5] in w or "paralysed" in w for w in r.adv), r.notes


@pytest.mark.parametrize("cid", ["blinded", "frightened", "poisoned", "prone", "restrained"])
def test_these_conditions_spoil_your_own_attacks(tables, cid):
    b, me, them = duel(tables)
    me.conditions[cid] = -1
    assert query.attack_roll(b, me, them, weapon(b, me)).disadvantage


def test_prone_is_easy_to_hit_from_beside_and_hard_from_afar(tables):
    b, me, them = duel(tables, gap=1)
    them.conditions["prone"] = -1
    assert query.attack_roll(b, me, them, weapon(b, me)).mode == "advantage"
    b, me, them = duel(tables, gap=4)
    them.conditions["prone"] = -1
    bow = next(o for o in b.attack_options(them) if not o.is_melee)  # the bandit's crossbow, the other way round
    me.conditions["prone"] = -1
    assert "target prone" in query.attack_roll(b, them, me, bow).dis


def test_paralysed_and_stunned_fail_strength_and_dexterity_saves(tables):
    for cid in ("paralyzed", "stunned", "unconscious", "petrified"):
        b, me, them = duel(tables)
        them.conditions[cid] = -1
        assert query.save_roll(b, them, "dex").auto_fail
        assert query.save_roll(b, them, "str").auto_fail
        assert not query.save_roll(b, them, "wis").auto_fail
        assert not b._save(them, "dex", 1)


def test_a_hit_from_beside_the_senseless_is_a_critical(tables):
    b, me, them = duel(tables, gap=1)
    them.conditions["paralyzed"] = -1
    assert query.crit_within(b, me, them)
    b, me, them = duel(tables, gap=3)
    them.conditions["paralyzed"] = -1
    assert not query.crit_within(b, me, them)


def test_restrained_dodges_badly_and_the_grappled_cannot_move(tables):
    b, me, them = duel(tables)
    them.conditions["restrained"] = -1
    assert query.save_roll(b, them, "dex").roll.disadvantage
    assert them.speed == 0
    b, me, them = duel(tables)
    them.conditions["grappled"] = -1
    them.grappled_by = me.id
    assert them.speed == 0


def test_the_grappled_strike_well_at_the_one_holding_on_and_badly_at_others(tables):
    b, me, them = duel(tables)
    me.conditions["grappled"] = -1
    me.grappled_by = them.id
    assert "grappled" not in query.attack_roll(b, me, them, weapon(b, me)).dis
    me.grappled_by = 99  # someone else has hold of them
    assert "grappled" in query.attack_roll(b, me, them, weapon(b, me)).dis


def test_fear_spoils_attacks_only_while_its_cause_is_in_sight(tables):
    b, me, them = duel(tables)
    me.conditions["frightened"] = 3
    me.sources["frightened"] = them.id
    assert "frightened" in query.attack_roll(b, me, them, weapon(b, me)).dis
    them.state = "fled"  # gone from the field
    assert "frightened" not in query.attack_roll(b, me, them, weapon(b, me)).dis


def test_the_incapacitated_cannot_act_and_petrified_flesh_resists_everything(tables):
    b, me, them = duel(tables)
    them.conditions["stunned"] = 1
    assert them.incapacitated and not them.can_act()
    them.conditions = {"petrified": -1}
    assert query.damage_taken(them, 10, "fire") == (5, "resist")
    assert query.condition_immune(them, "poisoned")


def test_advantage_and_disadvantage_cancel(tables):
    b, me, them = duel(tables)
    them.conditions["restrained"] = -1
    me.conditions["poisoned"] = -1
    r = query.attack_roll(b, me, them, weapon(b, me))
    assert r.advantage and r.disadvantage and r.mode == ""


# ---------------------------------------------------------------------------- the old way, for comparison
def old_adv_dis(b, att, target, opt):
    """The battle's advantage rules as they were before the kernel (combat.py, 2026-10-11), for the comparison
    below. Only what the kernel was meant to keep the same."""
    adv, dis = False, False
    g = grid.gap(att.space, target.space)
    if att.helped or target.marked:
        adv = True
    if "prone" in target.conditions:
        adv, dis = (True, dis) if g <= 1 else (adv, True)
    if any(c in target.conditions for c in ("restrained", "stunned", "unconscious", "paralyzed")):
        adv = True
    if target.dodging and b.can_see(target, att):
        dis = True
    if any(c in att.conditions for c in ("prone", "frightened", "poisoned", "blinded", "restrained")):
        dis = True
    if not b.can_see(att, target):
        dis = True
    elif att.hidden or not b.can_see(target, att):
        adv = True
    if not opt.is_melee:
        if any(e.standing and not e.incapacitated and grid.gap(att.space, e.space) <= 1 for e in b.enemies_of(att)):
            dis = True
        if opt.range[0] and g * grid.SQUARE_FT > opt.range[0]:
            dis = True
    if att.has_trait("pack_tactics") and any(x is not att and x.standing and not x.incapacitated
                                             and b.gap(x, target) <= 1 for x in b.allies_of(att)):
        adv = True
    if opt.is_melee and b.flanker(att, target) is not None:
        adv = True
    return adv, dis


def test_the_kernel_gives_the_old_answers_where_the_rules_did_not_change(tables):
    """Hundreds of random moments of a fight, asked both ways (the 2024 changes are left out of the sample: blinded or
    grappled targets and attackers, dodging while held fast)."""
    rng = RNG(7, "sample")
    kept = ("prone", "restrained", "stunned", "unconscious", "paralyzed", "frightened", "poisoned")
    asked = 0
    for i in range(400):
        foe = rng.choice(["wolf", "bandit", "goblin", "bandit_archer", "zombie"])
        b, me, them = duel(tables, foe=foe, gap=rng.choice([1, 1, 2, 4, 7]), seed=i)
        for f in (me, them):
            for cid in kept:
                if rng.chance(0.12):
                    f.conditions[cid] = -1
            if "unconscious" in f.conditions:
                f.conditions["prone"] = -1  # (as the game always lays them down; 2024: Unconscious includes Prone)
            f.dodging = rng.chance(0.2) and "restrained" not in f.conditions and not f.incapacitated
            f.helped = rng.chance(0.1)
            f.marked = rng.chance(0.1)
        for att, target in ((me, them), (them, me)):
            for opt in b.attack_options(att):
                if not opt.available:
                    continue
                r = query.attack_roll(b, att, target, opt)
                assert (r.advantage, r.disadvantage) == old_adv_dis(b, att, target, opt), (foe, att.name, opt.name,
                                                                                         att.conditions, target.conditions, r.notes)
                asked += 1
    assert asked > 500


# ---------------------------------------------------------------------------- traits and hooks
def test_traits_come_from_race_class_and_stat_block(tables):
    b, me, them = duel(tables, foe="wolf", race="halfling", cls="rogue")
    assert {"lucky", "sneak_attack"} <= trs.of(me)
    assert {"pack_tactics", "keen_senses"} <= trs.of(them)
    assert them.passive() == 10 + them.skill("perception") + 5  # Keen Senses through its modifier


def test_hooks_are_asked_target_first_then_in_the_order_of_battle(tables):
    b, me, them = duel(tables)
    asked = []
    events.HANDLERS["_probe"] = lambda b_, owner, ev, hook, buff: asked.append(owner.id)
    try:
        defs = tables.traits["traits"]
        defs["_probe_trait"] = {"name": "Probe", "text": "",
                                "hooks": [{"event": "turn_end", "as": "any", "handler": "_probe"}]}
        orig = trs.of
        trs.of = lambda f: orig(f) | {"_probe_trait"}  # type: ignore[assignment]
        try:
            events.emit(b, "turn_end", actor=me, target=them)
        finally:
            trs.of = orig  # type: ignore[assignment]
    finally:
        defs.pop("_probe_trait", None)
        events.HANDLERS.pop("_probe", None)
    assert asked == [them.id, me.id]


def test_a_reaction_hook_waits_for_a_reaction(tables):
    b, me, them = duel(tables, cls="rogue")
    me.char.level = 5
    me.char.features.append("uncanny_dodge")
    ev = events.emit(b, "damage_incoming", actor=them, target=me, stage="blow", amount=10)
    assert ev.amount == 5 and not me.reaction
    b.round += 1
    ev = events.emit(b, "damage_incoming", actor=them, target=me, stage="blow", amount=10)
    assert ev.amount == 10  # no reaction left


# ---------------------------------------------------------------------------- abilities and their uses
def test_second_wind_heals_and_is_spent_until_a_rest(tables):
    from realmwalker.rules.engine import actions
    from realmwalker.rules.progression import short_rest

    b, me, them = duel(tables, cls="fighter")
    me.hp = 1
    b.order = [me.id, them.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    assert me.char.uses["second_wind"] == 1
    b.do_ability(me, "second_wind")
    assert 1 + 1 + me.char.level <= me.hp and me.char.uses["second_wind"] == 0
    why = actions.problem(b, me, actions.find(me, "second_wind"))
    assert why == "used; rest to recover"
    short_rest(me.char, tables, RNG(1))
    assert me.char.uses["second_wind"] == 1


def test_a_new_level_brings_its_pools_ready(tables):
    from realmwalker.rules.progression import award_xp, long_rest

    c = hero(tables, "fighter")
    assert "action_surge" not in c.uses
    award_xp(c, 300, tables, RNG(1), auto=True)  # level 2: Action Surge
    assert c.uses.get("action_surge") == 1
    c.uses["action_surge"] = 0
    long_rest(c, tables, RNG(1))
    assert c.uses["action_surge"] == 1


def test_turn_undead_needs_undead_near(tables):
    from realmwalker.rules.progression import award_xp

    c = hero(tables, "cleric")
    award_xp(c, 300, tables, RNG(1), auto=True)
    cr = spawn(tables, "bandit", RNG(1, "foe"), 1)
    b = Battle(tables, [c], [cr], Env(), RNG(1, "battle"), spots={0: (3, 4), 1: (5, 4)})
    b.start()
    me = b.fighters[0]
    rows = {aid: (ok, why) for aid, _, ok, why in b.class_abilities(me)}
    assert rows["turn_undead"] == (False, "no undead within 30 feet")


def test_every_ability_in_the_data_resolves(tables):
    from realmwalker.rules.engine import actions, effects

    for tid, d in tables.traits["traits"].items():
        acts = d.get("activate") or []
        for a in acts if isinstance(acts, list) else [acts]:
            assert a["cost"] in ("action", "bonus", "free"), tid
            for o in a.get("effects", []):
                assert o["op"] in effects.OPS
            for r in a.get("requires", []):
                assert r in actions.REQUIRES
