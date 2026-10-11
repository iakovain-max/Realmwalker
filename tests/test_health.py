"""Health over time: bleeding, infection, healing, lasting injuries, diseases, treatment, drink and poppy."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import care, save
from realmwalker.game.state import new_game
from realmwalker.rules import body, health
from realmwalker.rules.body import Environment
from realmwalker.rules.character import Sheet
from realmwalker.rules.combat import Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.health import HealthContext
from realmwalker.rules.inventory import add_item
from realmwalker.rules.wounds import Wound
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def hero(tables, seed=1, cls="fighter"):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("soldier")
    return b.build()


def live(char, tables, days, seed=1, activity="rest"):
    """Days of ordinary life: sleep at night, fed and watered."""
    rng = RNG(seed, "live")
    s = Sheet(char, tables)
    for hour in range(int(days * 24)):
        act = "sleep" if hour % 24 < 8 else activity
        char.hunger = char.thirst = 10
        body.tick(char, s, Environment(15, 5, 0, act), 60)
        health.tick(char, tables, HealthContext(act, now=hour * 60), 60, rng)
        if getattr(char, "death_cause", None) or char.hp <= 0:
            return False
    return True


# ---------------------------------------------------------------------------- bleeding
def test_an_open_wound_bleeds_and_a_bandage_stops_it(tables):
    c = hero(tables)
    c.wounds.append(Wound("left_arm", "cut", 3, 3, 0))
    health.tick(c, tables, HealthContext("rest"), 60, RNG(1))
    assert c.blood < 100
    lost = 100 - c.blood
    c.blood = 100
    c.wounds[0].bandaged = True
    health.tick(c, tables, HealthContext("rest"), 60, RNG(1))
    assert c.blood == 100 and lost > 5


def test_small_cuts_clot_by_themselves(tables):
    c = hero(tables)
    c.wounds.append(Wound("left_arm", "cut", 1, 1, 0))
    for h in range(24):
        health.tick(c, tables, HealthContext("rest", now=h * 60), 60, RNG(h))
    assert not c.wounds or c.wounds[0].bleed == 0
    assert c.blood > 80


def test_blood_comes_back_when_fed(tables):
    c = hero(tables)
    c.blood = 50
    for h in range(10):
        health.tick(c, tables, HealthContext("rest"), 60, RNG(h))
    assert c.blood > 55


def test_losing_all_blood_is_death(tables):
    c = hero(tables)
    c.blood = 1
    c.wounds.append(Wound("torso", "cut", 3, 3, 0))
    health.tick(c, tables, HealthContext("rest"), 60, RNG(1))
    assert c.death_cause == "bled to death"


# ---------------------------------------------------------------------------- infection and healing
def test_dirty_wounds_fester_more_than_clean_ones(tables):
    dirty = clean = 0
    for seed in range(60):
        a, b = hero(tables, seed), hero(tables, seed)
        a.wounds.append(Wound("left_arm", "cut", 2, 0, 0))
        b.wounds.append(Wound("left_arm", "cut", 2, 0, 0, cleaned=True))
        for h in range(24 * 4):
            health.tick(a, tables, HealthContext("rest", now=h * 60), 60, RNG(seed * 1000 + h))
            health.tick(b, tables, HealthContext("rest", now=h * 60), 60, RNG(seed * 1000 + h))
        dirty += any(w.infection > 0 for w in a.wounds) or bool(a.diseases)
        clean += any(w.infection > 0 for w in b.wounds) or bool(b.diseases)
    assert dirty > clean


def test_wounds_heal_over_days_and_bones_over_weeks(tables):
    c = hero(tables)
    c.wounds.append(Wound("left_arm", "cut", 1, 0, 0, bandaged=True))
    assert live(c, tables, 4)
    assert not c.wounds
    c.wounds.append(Wound("right_leg", "fracture", 2, 0, 0, splinted=True))
    assert live(c, tables, 12)
    assert c.wounds, "a broken leg is not mended in twelve days"
    assert live(c, tables, 30)
    assert not c.wounds


def test_unset_bones_and_critical_wounds_can_leave_lasting_injuries(tables):
    limps = 0
    for seed in range(20):
        c = hero(tables, seed)
        c.wounds.append(Wound("left_leg", "fracture", 2, 0, 0))
        live(c, tables, 45, seed)
        limps += "limp" in c.injuries
    assert 3 <= limps <= 19
    c = hero(tables)
    c.injuries.append("limp")
    s = Sheet(c, tables)
    assert s.speed() == 25 and health.travel_multiplier(c, tables) > 1.0


def test_a_festering_wound_brings_wound_fever(tables):
    c = hero(tables)
    c.wounds.append(Wound("left_arm", "cut", 2, 0, 0, infection=45.0, infected=True))
    health.tick(c, tables, HealthContext("rest"), 60, RNG(1))
    assert any(d["id"] == "wound_fever" for d in c.diseases)
    assert health.penalty(c, tables) <= -2


# ---------------------------------------------------------------------------- diseases
def test_disease_incubates_then_strikes_or_passes(tables):
    outcomes = set()
    for seed in range(30):
        c = hero(tables, seed)
        assert health.expose(c, tables, "dysentery", RNG(seed))
        assert not health.expose(c, tables, "dysentery", RNG(seed)), "no double infection"
        for h in range(80):
            health.tick(c, tables, HealthContext("rest", now=h * 60), 60, RNG(seed * 100 + h))
        outcomes.add(bool(c.diseases) and c.diseases[0]["phase"] == "sick")
    assert outcomes == {True, False}


def test_exposures_from_bites_become_diseases(tables):
    c = hero(tables)
    c.conditions.append("exposed:grave_rot")
    health.tick(c, tables, HealthContext("rest"), 10, RNG(1))
    assert c.diseases and c.diseases[0]["id"] == "grave_rot" and not c.conditions


def test_the_frothing_sickness_kills_unless_caught_early(tables):
    c = hero(tables)
    health.expose(c, tables, "frothing_sickness", RNG(1))
    assert not live(c, tables, 40)
    assert "frothing" in c.death_cause
    d = hero(tables)
    health.expose(d, tables, "frothing_sickness", RNG(1))
    health.magic_restore(d, tables)
    assert not d.diseases


def test_sickness_slows_and_weakens(tables):
    c = hero(tables)
    c.diseases.append({"id": "lung_fever", "phase": "sick", "stage": 1, "hours": 0.0, "until": 0, "day": 0.0,
                       "wins": 0, "rested": 0.0})
    assert health.penalty(c, tables) <= -3
    assert health.travel_multiplier(c, tables) > 1.2
    assert Sheet(c, tables).skill_bonus("athletics") < Sheet(hero(tables), tables).skill_bonus("athletics")


def test_diseases_can_be_recovered_from(tables):
    recovered = 0
    for seed in range(20):
        c = hero(tables, seed)
        c.diseases.append({"id": "filth_fever", "phase": "sick", "stage": 0, "hours": 0.0, "until": 0, "day": 0.0,
                           "wins": 0, "rested": 0.0})
        live(c, tables, 20, seed)
        recovered += not c.diseases
    assert recovered >= 15


# ---------------------------------------------------------------------------- treatment
def test_treatments_use_supplies_and_skill(tables):
    c = hero(tables)
    w = Wound("left_arm", "cut", 2, 2, 0)
    c.wounds.append(w)
    opts = {a: (ok, why) for a, _, ok, why in health.treatment_options(c, c, w, tables, fire=False, wooded=False)}
    assert opts["bandage"][0], "everyone starts with bandages"
    assert not opts["splint"][0] and not opts["poultice"][0]
    bandages = sum(i.qty for i in c.inventory if i.def_id == "bandages")
    ok, msgs, minutes = health.treat(c, c, w, "bandage", tables, RNG(3))
    assert minutes > 0 and msgs
    assert sum(i.qty for i in c.inventory if i.def_id == "bandages") == bandages - 1
    assert w.bandaged == ok


def test_cauterizing_stops_bleeding_and_burns(tables):
    c = hero(tables)
    w = Wound("left_leg", "cut", 3, 3, 0)
    c.wounds.append(w)
    ok, msgs, _ = health.treat(c, c, w, "cauterize", tables, RNG(1), fire=True)
    assert ok and w.bleed == 0
    assert any(x.kind == "burn" for x in c.wounds)


def test_splints_and_poultices(tables):
    c = hero(tables)
    bone = Wound("right_arm", "fracture", 2, 0, 0)
    sore = Wound("left_arm", "cut", 2, 0, 0, infection=40.0, infected=True)
    c.wounds += [bone, sore]
    add_item(c, tables.items, "splint")
    add_item(c, tables.items, "healing_herbs", 3)
    c.skills.append("medicine")
    for seed in range(10):
        health.treat(c, c, bone, "splint", tables, RNG(seed))
        if bone.splinted:
            break
    assert bone.splinted
    before = sore.infection
    for seed in range(3):
        health.treat(c, c, sore, "poultice", tables, RNG(seed))
    assert sore.infection < before


def test_healing_magic_outside_battle(tables):
    world = cached_world(WorldOptions("Healland", 3, "small"), tables)
    cleric = hero(tables, cls="cleric")
    game = new_game(world, tables, cleric)
    w = Wound("torso", "cut", 2, 1, 0)
    cleric.wounds.append(w)
    cleric.hp = 1
    spells = {sid for sid, _, ok, _ in care.healing_magic(game, cleric) if ok}
    assert "cure_wounds" in spells
    msgs = care.cast(game, cleric, cleric, w, "cure_wounds")
    assert cleric.hp > 1 and (w.severity == 1 or w not in cleric.wounds)
    assert msgs


def test_poppy_eases_pain_and_hooks(tables):
    c = hero(tables)
    c.wounds.append(Wound("torso", "cut", 3, 0, 0))
    before = health.pain(c, tables)
    for _ in range(4):
        health.take_poppy(c)
    assert health.pain(c, tables) < before
    assert c.addictions["poppy"] >= 40
    for h in range(40):
        health.tick(c, tables, HealthContext("rest"), 60, RNG(h))
    assert c.effects.get("withdrawal", 0) > 0


def test_drink_dulls_pain_and_leaves_a_hangover(tables):
    c = hero(tables)
    c.wounds.append(Wound("torso", "cut", 2, 0, 0))
    sober = health.pain(c, tables)
    body.drink(c, 1, 6)
    body.drink(c, 1, 6)
    assert health.pain(c, tables) < sober
    assert health.intox_stage(c) is not None
    for h in range(8):
        health.tick(c, tables, HealthContext("rest"), 60, RNG(h))
    assert c.intoxication < 20 and c.effects.get("hangover", 0) > 0


# ---------------------------------------------------------------------------- effects on rolls and fights
def test_the_body_state_shows_in_skills_and_saves(tables):
    fresh = Sheet(hero(tables), tables)
    c = hero(tables)
    c.exhaustion = 1
    s = Sheet(c, tables)
    assert s.skill_bonus("athletics") == fresh.skill_bonus("athletics") - 5
    assert s.save_bonus("con") == fresh.save_bonus("con")
    c.exhaustion = 3
    assert s.save_bonus("con") == fresh.save_bonus("con") - 5
    d = hero(tables)
    d.wounds.append(Wound("head", "blunt", 2, 0, 0))
    assert Sheet(d, tables).skill_bonus("insight") < fresh.skill_bonus("insight") - 4


def test_a_broken_arm_cannot_hold_a_weapon(tables):
    c = hero(tables)
    c.wounds.append(Wound("right_arm", "fracture", 2, 0, 0))
    b = Battle(tables, [c], [spawn(tables, "wolf", RNG(1), 1)], Env(), RNG(1))
    b.start()
    f = b.side("party")[0]
    main = [o for o in b.attack_options(f) if o.key == "main"]
    assert main and not main[0].available and "arm" in main[0].reason


def test_exhaustion_gives_disadvantage_in_battle(tables):
    c = hero(tables)
    c.exhaustion = 3
    b = Battle(tables, [c], [spawn(tables, "wolf", RNG(1), 1)], Env(), RNG(1))
    b.start()
    f, wolf = b.side("party")[0], b.side("foe")[0]
    opt = b.attack_options(f)[0]
    adv, dis, why = b._adv_dis(f, wolf, opt)
    assert dis and "exhausted" in why


# ---------------------------------------------------------------------------- saving
def test_health_state_survives_saving(tables, tmp_path):
    world = cached_world(WorldOptions("Saveland", 5, "small"), tables)
    game = new_game(world, tables, hero(tables))
    c = game.leader
    c.wounds.append(Wound("left_leg", "fracture", 2, 0, 0, splinted=True, healing=12.5, infection=3.0, internal=False))
    c.diseases.append({"id": "marsh_fever", "phase": "dormant", "stage": 0, "hours": 5.0, "until": 0, "day": 2.0,
                       "wins": 0, "rested": 0.0})
    c.effects["poppy"] = 3.5
    c.addictions["poppy"] = 24.0
    folder = save.save_game(game, tmp_path)
    d = save.load_game(folder, tables).leader
    w = d.wounds[-1]
    assert (w.splinted, w.healing, w.infection, w.peak) == (True, 12.5, 3.0, 2)
    assert d.diseases == c.diseases and d.effects == c.effects and d.addictions == c.addictions
