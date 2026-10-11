"""Characters: creation rules, derived numbers, inventory and equipment."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules.character import Character, Sheet
from realmwalker.rules.creation import CharacterBuilder, make_ties, starting_places
from realmwalker.rules.inventory import add_item, equip, remove_item, unequip
from realmwalker.rules.items import coin_weight, money_text
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Charland", 404, "small"), tables)


def build(tables, race="human", cls="fighter", bg="soldier", seed=1):
    b = CharacterBuilder(tables, RNG(seed, "test"))
    b.set_race(race)
    b.set_class(cls)
    b.set_background(bg)
    return b


@pytest.mark.parametrize("race", ["human", "elf", "dwarf", "halfling", "half_orc"])
@pytest.mark.parametrize("cls", ["fighter", "rogue", "cleric", "wizard"])
def test_every_combination_builds_with_defaults(tables, race, cls):
    b = build(tables, race, cls)
    assert b.problems() == []
    assert b.points_left() == 0, "suggested arrays spend all 27 points"
    c = b.build()
    s = Sheet(c, tables)
    assert c.hp == c.max_hp >= 1
    assert 10 <= s.armor_class() <= 20
    assert s.encumbrance() == 0, f"{race} {cls} starts overloaded: {s.load()} lb"
    assert c.equipped.get("main") is not None, "everyone starts dressed"
    assert c.equipped.get("main_hand") is not None


@pytest.mark.parametrize("bg", ["soldier", "acolyte", "criminal", "folk_hero", "noble", "sage", "outlander", "guild_artisan"])
@pytest.mark.parametrize("race", ["human", "elf", "dwarf", "halfling", "half_orc"])
def test_nobody_starts_slowed_by_their_pack_or_dressed_for_summer(tables, race, bg):
    """Half of all new characters used to start encumbered, and acolytes and sages set out in sandals."""
    for cls in ("fighter", "rogue", "cleric", "wizard"):
        c = build(tables, race, cls, bg).build()
        s = Sheet(c, tables)
        assert s.encumbrance() == 0, f"{race} {cls} {bg} starts encumbered: {s.load()} of {s.capacity()[0]} lb"
        assert s.warmth() >= 6, f"{race} {cls} {bg} starts with warmth {s.warmth()}"
        assert c.equipped.get("outer") is not None and c.equipped.get("feet") is not None


@pytest.mark.parametrize("bg", ["soldier", "acolyte", "criminal", "folk_hero", "noble", "sage", "outlander", "guild_artisan"])
def test_backgrounds_give_ties_and_places(tables, world, bg):
    b = build(tables, bg=bg)
    places = starting_places(world, tables, bg, b.race, RNG(1))
    assert places
    c = b.build()
    ties = make_ties(world, tables, c, places[0], RNG(2))
    assert ties and "{" not in ties[0]["text"] and ties[0]["refs"]
    for sid in ties[0]["refs"].values():
        if isinstance(sid, int) and sid < len(world.settlements):
            assert world.settlements[sid].name


def test_point_buy_limits(tables):
    b = build(tables)
    b.scores = {a: 8 for a in b.scores}
    assert b.points_left() == 27
    assert not b.change("str", -1)  # 8 is the floor
    for _ in range(7):
        assert b.change("str", +1)
    assert b.scores["str"] == 15
    assert not b.change("str", +1)  # 15 is the ceiling before racial bonuses
    assert b.points_left() == 18


def test_racial_bonuses_and_traits(tables):
    dwarf = build(tables, race="dwarf").build()
    human = build(tables, race="human").build()
    assert dwarf.abilities["con"] == dwarf.base_scores["con"] + 2
    assert all(human.abilities[a] == human.base_scores[a] + 1 for a in human.abilities)
    s = Sheet(dwarf, tables)
    assert s.darkvision == 60 and s.has_rule("poison_resilience")
    assert dwarf.max_hp == tables.classes["fighter"]["hit_die"] + (dwarf.abilities["con"] - 10) // 2 + 1


def test_skill_choices_and_expertise(tables):
    b = build(tables, cls="rogue", bg="criminal")
    assert len(b.class_skills) == 4 and len(b.expertise) == 2
    first = b.class_skills[0]
    assert b.toggle_skill(first) and first not in b.class_skills
    options = [s for s in b.skill_options() if s not in b.class_skills]
    assert b.toggle_skill(options[0])
    assert not b.toggle_skill(options[1])  # already four
    c = b.build()
    s = Sheet(c, tables)
    exp = c.expertise[0]
    ability = tables.rules["skills"][exp]["ability"]
    assert s.skill_bonus(exp) == s.mod(ability) + 2 * s.proficiency


def test_armor_class_rules(tables):
    b = build(tables, cls="fighter")
    b.kit = 0  # chain mail and shield
    c = b.build()
    s = Sheet(c, tables)
    assert s.armor_class() == 16 + 2 + (1 if c.fighting_style == "defense" else 0)
    unequip(c, "armor")
    assert s.armor_class() == 10 + s.mod("dex") + 2


def test_two_handed_weapons_free_the_off_hand(tables):
    c = build(tables).build()
    items = tables.items
    great = add_item(c, items, "greatsword")
    assert c.equipped_item("off_hand") is not None  # the shield
    ok, msg = equip(c, items, great.uid)
    assert ok and c.equipped_item("off_hand") is None and "put away" in msg
    shield = next(i for i in c.inventory if items.category(i) == "shield")
    ok, _ = equip(c, items, shield.uid)
    assert ok and c.equipped_item("main_hand") is None


def test_stacking_removing_and_weights(tables):
    c = build(tables).build()
    items = tables.items
    before = sum(i.qty for i in c.inventory if i.def_id == "torch")
    add_item(c, items, "torch", 3)
    torches = [i for i in c.inventory if i.def_id == "torch"]
    assert len(torches) == 1 and torches[0].qty == before + 3
    part = remove_item(c, torches[0].uid, 2)
    assert part.qty == 2 and torches[0].qty == before + 1
    assert money_text(1234) == "12 gp 3 sp 4 cp" and coin_weight(100) == 1 / 50


def test_encumbrance_slows_and_stops(tables):
    c = build(tables, race="halfling", cls="wizard").build()
    s = Sheet(c, tables)
    assert s.travel_multiplier() == pytest.approx(30 / 25)
    add_item(c, tables.items, "iron_bar", 3)  # 30 lb of iron
    assert s.encumbrance() >= 1 and s.speed() < 25
    add_item(c, tables.items, "iron_bar", 20)
    assert s.encumbrance() == 3 and s.travel_multiplier() is None


def test_clothing_warmth_and_social(tables):
    c = build(tables, bg="noble").build()
    s = Sheet(c, tables)
    assert s.social() >= 2
    before = s.warmth()
    cloak = add_item(c, tables.items, "fur_cloak")
    equip(c, tables.items, cloak.uid)
    assert s.warmth() > before and s.wind_protection() >= 0.7


def test_character_round_trip(tables):
    c = build(tables, race="elf", cls="wizard", bg="sage").build()
    d = c.to_dict()
    again = Character.from_dict(d)
    assert again.to_dict() == d
