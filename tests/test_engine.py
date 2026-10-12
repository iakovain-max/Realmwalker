"""The rules kernel (realmwalker/rules/engine): the 2024 conditions as data, the numbers asked in one place, the hooks
of traits and features, and the start-up check that the data names only what the code has."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import grid
from realmwalker.rules.combat import Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import check, conditions, durations, events, query
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
    assert {"pack_tactics", "takes_food"} <= trs.of(them)  # its 2025 block's, and the game's own
    assert them.passive() == 15 == them.cdef["passive"]  # 10 + Perception +5 (2025: no Keen Senses)


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


# ---------------------------------------------------------------------------- the 2024 rules glossary
def test_damage_resistance_then_vulnerability_rounding_down(tables):
    b, me, them = duel(tables)
    them.buffs.append({"resist": ["fire"], "source": "test"})
    assert query.damage_taken(them, 1, "fire") == (0, "resist")  # halved and rounded down: nothing
    assert query.damage_taken(them, 7, "fire") == (3, "resist")
    b, me, bones = duel(tables, foe="skeleton")
    bones.buffs.append({"resist": ["bludgeoning"], "source": "test"})
    assert query.damage_taken(bones, 23, "bludgeoning") == (22, "vulnerable")  # 23 -> 11 -> 22 (the PHB's example)


def test_temporary_hit_points_go_first(tables):
    b, me, them = duel(tables)
    them.creature.hp = them.creature.max_hp = 20
    them.temp_hp = 5
    b._apply_hp_loss(them, 7, source=me, cause="test")
    assert them.temp_hp == 0 and them.hp == 18


def test_concentration_dc_is_capped_at_30(tables):
    assert query.concentration_dc(4) == 10
    assert query.concentration_dc(31) == 15
    assert query.concentration_dc(200) == 30


def test_the_incapacitated_lose_their_concentration(tables):
    b, me, them = duel(tables, cls="cleric")
    me.concentration = {"spell": "bless", "rounds": 10}
    me.conditions["stunned"] = 1
    b._check_end()
    assert me.concentration is None


def test_surprise_costs_initiative_not_a_turn(tables):
    c = hero(tables)
    cr = spawn(tables, "bandit", RNG(1, "foe"), 1)
    b = Battle(tables, [c], [cr], Env(surprised="foe"), RNG(1, "battle"), spots={0: (3, 4), 1: (9, 4)})
    b.start()
    bandit = b.fighters[1]
    assert query.initiative_roll(bandit).disadvantage
    b.order = [bandit.id, b.fighters[0].id]
    b.turn, b.turn_started = 0, False
    start = (bandit.x, bandit.y)
    b.step()
    assert (bandit.x, bandit.y) != start or any(e["kind"] == "attack" for e in b.events)  # it acts


def test_an_emanation_reaches_out_from_its_maker_and_leaves_them_out(tables):
    b, me, them = duel(tables, gap=6)
    cells = b.field.area("emanation", 10, origin=me.space, toward=(me.x, me.y))
    assert (me.x, me.y) not in cells
    assert (me.x + 2, me.y) in cells and (me.x + 3, me.y) not in cells
    assert (me.x + 2, me.y + 2) in cells  # 5-5-5: a diagonal square counts as five feet


def test_a_grapple_is_a_save_and_one_of_the_attack_actions_attacks(tables):
    from realmwalker.rules.progression import award_xp

    c = hero(tables, "fighter")
    award_xp(c, 6500, tables, RNG(1), auto=True)  # level 5: Extra Attack
    cr = spawn(tables, "bandit", RNG(1, "foe"), 1)
    b = Battle(tables, [c], [cr], Env(), RNG(1, "battle"), spots={0: (3, 4), 1: (4, 4)})
    b.start()
    me, them = b.fighters
    b.order = [me.id, them.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    b._save = lambda *a, **k: False
    b.do_grapple(me, them)
    assert "grappled" in them.conditions and them.grappled_by == me.id
    assert me.action == 0 and me.attacks_left == 1  # one attack of two used: the other is still there
    assert them.cond_ends["grappled"]["escape"] == query.unarmed_dc(me) == 8 + me.mod("str") + query.proficiency(me)


def test_the_held_are_dragged_along_at_double_cost(tables):
    b, me, them = duel(tables, gap=1)
    them.conditions["grappled"] = -1
    them.grappled_by = me.id
    b.order = [me.id, them.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    assert b.dragging(me)
    left = me.move_left
    b.walk(me, [(2, 4), (1, 4)])
    assert (me.x, me.y) == (1, 4) and (them.x, them.y) == (2, 4) and me.move_left == left - 20


def test_help_distracts_an_enemy_for_a_friends_next_attack(tables):
    friend = hero(tables, "rogue", seed=2)
    c = hero(tables)
    cr = spawn(tables, "bandit", RNG(1, "foe"), 1)
    b = Battle(tables, [c, friend], [cr], Env(), RNG(1, "battle"), spots={0: (3, 4), 1: (3, 6), 2: (4, 4)})
    b.start()
    me, fr, them = b.fighters
    b.order = [me.id, fr.id, them.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    assert them in b.help_targets(me)
    b.do_help(me, them)
    assert "distracted" in query.attack_roll(b, fr, them, weapon(b, fr)).adv
    assert "distracted" not in query.attack_roll(b, them, fr, weapon(b, them)).adv  # only for the helper's side


def test_humans_wake_with_heroic_inspiration(tables):
    from realmwalker.rules.progression import long_rest

    c = hero(tables, race="human")
    c.uses.pop("heroic_inspiration", None)
    long_rest(c, tables, RNG(1))
    assert c.uses["heroic_inspiration"] == 1
    d = hero(tables, race="dwarf", seed=3)
    long_rest(d, tables, RNG(1))
    assert not d.uses.get("heroic_inspiration")


def test_heroic_inspiration_rerolls_a_failed_save_once(tables):
    b, me, them = duel(tables)
    me.char.uses["heroic_inspiration"] = 1
    seen = []
    b.dice_say = lambda text: seen.append(text)
    for _ in range(40):
        b._save(me, "wis", 15)
        if me.char.uses["heroic_inspiration"] == 0:
            break
    assert me.char.uses["heroic_inspiration"] == 0 and any("Heroic Inspiration" in s for s in seen)


def test_falling_burning_breath_and_objects(tables):
    from realmwalker.rules.engine import hazards

    assert hazards.falling(tables, 5) == "" and hazards.falling(tables, 20) == "2d6"
    assert hazards.falling(tables, 500) == "20d6"
    assert hazards.breath_rounds(tables, 10) == 10 and hazards.breath_rounds(tables, 14) == 30
    assert hazards.breath_rounds(tables, 3) == 5  # at least thirty seconds
    assert hazards.object_ac(tables, "wood") == 15 and hazards.object_ac(tables, "adamantine") == 23
    assert hazards.object_hp(tables, "medium", resilient=True) == "4d8"
    assert hazards.object_immune(tables, "psychic")


def test_a_burning_creature_burns_each_turn_until_it_rolls_the_flames_out(tables):
    b, me, them = duel(tables, foe="ogre", gap=4)
    durations.buff(them, {"burning": True, "source": "burning"})
    before = them.hp
    b.order = [them.id, me.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(them)
    assert them.hp < before
    b.do_extinguish(them)
    assert not b.burning(them) and "prone" in them.conditions


def test_dim_light_hides_better(tables):
    b, me, them = duel(tables, gap=4)
    them.hidden = me.passive() - 2
    assert b.can_see(me, them)
    b.field.base_light = grid.DIM
    b._light_key = None
    assert b.dim_for(me, them) and not b.can_see(me, them)


# ---------------------------------------------------------------------------- reactions that ask first
def _shield_fight(tables, setting="ask"):
    w = hero(tables, "wizard")
    cr = spawn(tables, "bandit", RNG(1, "foe"), 1)
    b = Battle(tables, [w], [cr], Env(), RNG(1, "battle"), spots={0: (3, 4), 1: (4, 4)})
    b.start()
    b.human, b.reactions = True, setting
    me, them = b.fighters
    me.auto = False
    sword = next(o for o in b.attack_options(them) if o.is_melee)
    return b, me, them, sword


def _land_a_blow(b, me, them, sword):
    """An attack that would hit by 1: Shield would turn it."""
    import realmwalker.core.dice as dice_mod

    need = me.ac() - sword.bonus
    real = dice_mod.d20
    dice_mod.d20 = lambda rng, advantage=False, disadvantage=False: dice_mod.D20Roll(max(2, min(19, need)), [need])
    try:
        return b.run(b._attack, them, sword, me)
    finally:
        dice_mod.d20 = real


def test_a_reaction_that_spends_a_slot_stops_the_fight_to_ask(tables):
    b, me, them, sword = _shield_fight(tables)
    _land_a_blow(b, me, them, sword)
    d = b.pending_decision
    assert d is not None and d.kind == "shield" and "Shield" in d.text
    assert b.run(b.step) is None  # nothing else happens until it is answered
    b.answer("yes")
    assert b.pending_decision is None and any(x.get("source") == "shield" for x in me.buffs)


def test_saying_no_lets_the_blow_land(tables):
    b, me, them, sword = _shield_fight(tables)
    hp = me.hp
    _land_a_blow(b, me, them, sword)
    b.answer("no")
    assert not any(x.get("source") == "shield" for x in me.buffs) and me.hp < hp


def test_decide_for_me_never_asks(tables):
    b, me, them, sword = _shield_fight(tables, setting="auto")
    _land_a_blow(b, me, them, sword)
    assert b.pending_decision is None and any(x.get("source") == "shield" for x in me.buffs)


def test_without_a_player_nothing_ever_waits(tables):
    b, me, them, sword = _shield_fight(tables)
    b.human = False  # tests, the balance tool, autoplay without a window
    _land_a_blow(b, me, them, sword)
    assert b.pending_decision is None


def test_free_reactions_do_not_ask_unless_everything_should(tables):
    from realmwalker.rules.engine import reactions
    from realmwalker.rules.engine.reactions import Decision

    b, me, them, sword = _shield_fight(tables)
    asked = []
    b.resolver.in_worker = lambda: True
    b.resolver.ask = lambda d: asked.append(d.kind) or "no"
    assert reactions.ask(b, Decision(me, "opportunity", "x", free=True)) == "yes"
    b.reactions = "all"
    assert reactions.ask(b, Decision(me, "opportunity", "x", free=True)) == "no" and asked == ["opportunity"]


# ---------------------------------------------------------------------------- changing sides
def test_a_dominated_companion_fights_for_the_enemy_until_freed(tables):
    a, friend = hero(tables), hero(tables, "fighter", seed=4)
    cr = spawn(tables, "bandit", RNG(1, "foe"), 1)
    b = Battle(tables, [a, friend], [cr], Env(), RNG(1, "battle"), spots={0: (3, 4), 1: (4, 4), 2: (9, 4)})
    b.start()
    me, fr, bandit = b.fighters
    durations.give(b, fr, "charmed", source=bandit, control="foe")
    assert fr.team == "foe" and fr in b.enemies_of(me) and fr in b.allies_of(bandit)
    b.order = [fr.id, me.id, bandit.id]
    b.turn, b.turn_started = 0, False
    assert b.pending_party() is None
    b.step()  # played by the enemy's side: it turns on its friend
    assert any(e["kind"] == "attack" and e["by"] == fr.id and e["to"] == me.id for e in b.events)
    durations.remove(fr, "charmed")
    assert fr.team == "party" and fr in b.allies_of(me)


def test_the_charmed_will_not_strike_the_charmer(tables):
    b, me, them = duel(tables)
    me.action = 1
    durations.give(b, me, "charmed", source=them)
    assert b.attack_problem(me, weapon(b, me), them) == "charmed: you will not harm them"


# ---------------------------------------------------------------------------- senses and the missing actions
def test_blindsight_and_truesight_see_what_eyes_cannot(tables):
    b, me, drake = duel(tables, foe="young_dragon", gap=3)  # blindsight 30 ft, darkvision 120 ft
    me.conditions["invisible"] = -1
    assert b.can_see(drake, me)  # within its blindsight, invisible or not
    me.conditions.pop("invisible")
    b2, me2, bandit = duel(tables, gap=3)
    me2.conditions["invisible"] = -1
    assert not b2.can_see(bandit, me2)
    assert "unseen" in query.attack_roll(b2, me2, bandit, weapon(b2, me2)).adv


def test_study_search_and_ready(tables):
    b, me, them = duel(tables, gap=3)
    b.order = [me.id, them.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    them.hidden = 1
    b.do_search(me)
    assert them.hidden == 0
    me.action = 1
    b.do_ready(me, "reach")
    assert me.readied == "reach"
    b.end_turn()
    them.move_left = 30
    b.walk(them, [(5, 4), (4, 4)])  # comes within reach of the waiting sword
    assert not me.reaction and any(e["kind"] == "attack" and e["by"] == me.id for e in b.events)


# ---------------------------------------------------------------------------- height, falling, antimagic, objects
def test_height_counts_in_reach_and_a_knocked_down_flier_falls(tables):
    b, me, drake = duel(tables, foe="young_dragon", gap=1)
    assert drake.fly_speed == 80
    drake.move_left = 80
    assert b.do_fly(drake, 20) and drake.z == 20
    assert b.gap(me, drake) == 4  # 20 feet up: out of a sword's reach
    sword = weapon(b, me)
    assert not b.in_reach(me, sword, drake)[0]
    hp = drake.hp
    drake.conditions["prone"] = -1
    b._check_end()
    assert drake.z == 0 and drake.hp < hp and "prone" in drake.conditions


def test_a_flier_goes_over_what_stops_walkers(tables):
    b, me, drake = duel(tables, foe="stirge", gap=4)
    drake.move_left = drake.fly_speed
    tree = b.move_tree(drake)
    b.field.rough[:, :] = True  # the whole field is mud
    assert len(b.move_tree(drake)) == len(tree)  # (the mud does not slow it)


def test_no_spell_works_in_an_antimagic_area(tables):
    from realmwalker.rules.combat import Zone

    w = hero(tables, "wizard")
    cr = spawn(tables, "bandit", RNG(1, "foe"), 1)
    b = Battle(tables, [w], [cr], Env(), RNG(1, "battle"), spots={0: (3, 4), 1: (8, 4)})
    b.start()
    me, them = b.fighters
    b.order = [me.id, them.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    from realmwalker.rules.combat import Token

    b.tokens.append(Token(99, "spiritual_weapon", x=7, y=4, owner=me.id, bonus=5, damage="1d8", damage_type="force"))
    assert b.spirit_targets(me) == [them]
    b._add_zone(Zone(b._zone_id(), "antimagic", {(8, 4), (8, 5)}))
    assert b.cast_problem(me, "fire_bolt", them) == "magic does not work there"
    # Nor what a spell has summoned or laid on the ground: a spiritual weapon cannot strike there, guardians hurt nobody.
    assert b.spirit_targets(me) == []
    hp = them.hp
    b._add_zone(Zone(b._zone_id(), "guardians", {(8, 4), (8, 5)}, owner=me.id, spell="spirit_guardians", save="wis",
                     dc=30, damage="3d8", damage_type="radiant"))
    b._zones_on(them, start=True)
    assert them.hp == hp


def test_doors_and_barrels_can_be_broken(tables):
    b, me, them = duel(tables, gap=6)
    T = tables.terrain.index
    b.field.terrain[4, 4] = T["barrels"]
    b.field._derive()
    obj = b.object_at((4, 4))
    assert obj is not None and obj["ac"] == 15
    obj["hp"] = 1
    b.order = [me.id, them.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    for _ in range(20):
        me.action, me.attacks_left = 1, 0
        if b.object_at((4, 4)) is None:
            break
        b.attack_object(me, weapon(b, me), (4, 4))
    assert b.object_at((4, 4)) is None and b.field.passable(4, 4)


def test_ending_a_turn_in_another_creatures_space_leaves_you_prone(tables):
    b, me, them = duel(tables, foe="bandit", gap=1)
    me.x, me.y = them.x, them.y  # stopped on the way through (a blow, a web)
    b._crowded(me)
    assert "prone" in me.conditions and "prone" not in them.conditions
    b, me, ogre = duel(tables, foe="ogre", gap=1)
    ogre.x, ogre.y = me.x, me.y
    b._crowded(ogre)
    assert "prone" not in ogre.conditions  # the larger keeps its feet
