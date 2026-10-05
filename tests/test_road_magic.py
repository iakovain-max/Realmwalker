"""Magic on the road (after v1): a spell that lasts (Mage Armour, Shield of Faith, Stoneskin, Death Ward) can be cast
before a fight and outlives the one it was cast in; the sheet counts its armour, a battle carries the rest, and it
wears off as time passes. The Spells screen casts it (and healing) outside a fight."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import magic
from realmwalker.game.state import new_game
from realmwalker.rules import spells as sp
from realmwalker.rules.character import Sheet
from realmwalker.rules.combat import PARTY, Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.inventory import add_item, equip
from realmwalker.rules.progression import award_xp
from realmwalker.rules.wounds import make_wound
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Spellroad", 31, "small"), tables).generate()


def hero(tables, cls, seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("sage")
    return b.build()


def game_with(world, tables, *party):
    import copy

    game = new_game(copy.deepcopy(world), tables, party[0])
    for c in party[1:]:
        c.is_player = False
        game.party.append(c)
    return game


def fight(tables, party, seed=1):
    rng = RNG(seed, "foes")
    b = Battle(tables, party, [spawn(tables, "wolf", rng, 1)], Env(), RNG(seed, "battle"))
    b.start("Test fight.")
    return b


def test_mage_armour_cast_on_the_road_counts_on_the_sheet_and_wears_off(world, tables):
    wiz = hero(tables, "wizard")
    assert wiz.equipped_item("armor") is None
    game = game_with(world, tables, wiz)
    before = Sheet(wiz, tables).armor_class()
    slots = sp.slots_left(wiz, tables)[0]
    assert magic.road_problem(game, wiz, "mage_armor") is None
    said = magic.cast_on_road(game, wiz, "mage_armor")
    assert "Mage Armour" in said[0] and "eight hours" in said[0]
    assert sp.slots_left(wiz, tables)[0] == slots - 1
    assert Sheet(wiz, tables).armor_class() == 13 + Sheet(wiz, tables).mod("dex") > before
    # It is still working: casting it again would waste a slot.
    assert "still working" in magic.road_problem(game, wiz, "mage_armor")
    game.pass_time(9 * 60, "rest")
    assert "mage_armor" not in sp.lasting(wiz)
    assert Sheet(wiz, tables).armor_class() == before
    assert any("Mage Armour" in m.text and "fades" in m.text for m in game.log.messages)


def test_mage_armour_does_nothing_under_real_armour(world, tables):
    wiz = hero(tables, "wizard")
    sp.keep(wiz, tables, "mage_armor")
    unarmoured = Sheet(wiz, tables).armor_class()
    it = add_item(wiz, tables.items, "chain_shirt")
    equip(wiz, tables.items, it.uid)
    armoured = Sheet(wiz, tables)
    assert unarmoured == 13 + armoured.mod("dex")
    assert armoured.armor_class() == 13 + min(2, armoured.mod("dex"))  # the chain shirt, not the spell


def test_only_what_makes_sense_outside_a_fight(world, tables):
    wiz = hero(tables, "wizard")
    game = game_with(world, tables, wiz)
    assert magic.road_problem(game, wiz, "magic_missile") == "only in a fight"
    assert magic.road_problem(game, wiz, "fire_bolt") == "only in a fight"
    assert "too quickly" in magic.road_problem(game, wiz, "shield")
    slots = sp.slots_left(wiz, tables)[0]
    said = magic.cast_on_road(game, wiz, "magic_missile")
    assert "only in a fight" in said[0]
    assert sp.slots_left(wiz, tables)[0] == slots  # nothing spent
    wiz.spells["slots_used"][0] = sp.slots_total(wiz, tables)[0]
    assert "slot" in magic.road_problem(game, wiz, "mage_armor")


def test_lasting_spells_come_into_a_fight(world, tables):
    wiz = hero(tables, "wizard")
    sp.keep(wiz, tables, "mage_armor")
    b = fight(tables, [wiz])
    f = b.side(PARTY)[0]
    assert f.ac() == 13 + f.mod("dex")
    # The menu knows it is already on: no slot wasted casting it again.
    menu = {sid: (ok, why) for sid, ok, why in b.spell_options(f)}
    assert menu["mage_armor"] == (False, "already working on you")


def test_mage_armour_cast_in_a_fight_is_still_on_afterwards(world, tables):
    wiz = hero(tables, "wizard")
    b = fight(tables, [wiz])
    f = b.side(PARTY)[0]
    before = f.ac()
    f.action = 1  # their turn
    b.do_cast(f, "mage_armor", None)
    assert f.ac() == max(before, 13 + f.mod("dex"))
    assert sp.lasting(wiz, tables)["mage_armor"] == pytest.approx(8.0)
    assert Sheet(wiz, tables).armor_class() == 13 + Sheet(wiz, tables).mod("dex")


def test_shield_of_faith_never_counts_twice(world, tables):
    cleric = hero(tables, "cleric")
    fighter = hero(tables, "fighter", seed=4)
    base = Sheet(fighter, tables).armor_class()
    b = fight(tables, [fighter, cleric])
    ally, caster = b.side(PARTY)
    caster.bonus = 1  # a bonus action, on their turn
    b.do_cast(caster, "shield_of_faith", ally)
    assert ally.ac() == base + 2
    caster.bonus = 1
    b.do_cast(caster, "shield_of_faith", ally)  # again: renewed, not doubled
    assert ally.ac() == base + 2
    b2 = fight(tables, [fighter, cleric], seed=2)  # the next fight, ten minutes later at most
    assert b2.side(PARTY)[0].ac() == base + 2


def test_a_death_ward_rides_into_battle_and_is_spent_there(world, tables):
    cleric = hero(tables, "cleric")
    award_xp(cleric, 23000, tables, RNG(2), auto=True)  # level 7: 4th-level prayers, Death Ward among them
    assert "death_ward" in sp.known_spells(cleric, tables)
    game = game_with(world, tables, cleric)
    magic.cast_on_road(game, cleric, "death_ward", cleric)
    assert "death_ward" in sp.lasting(cleric, tables)
    b = fight(tables, [cleric])
    f = b.side(PARTY)[0]
    ward = [x for x in f.buffs if x.get("death_ward")]
    assert ward and ward[0]["lasting"] == "death_ward"
    # A killing blow takes the ward instead, and it is gone for the next fight.
    b._apply_hp_loss(f, f.hp + 50, source=None, cause="a test")
    assert f.hp == 1
    assert "death_ward" not in sp.lasting(cleric, tables)


def test_healing_from_the_spells_screen_goes_to_the_worst_wound(world, tables):
    cleric = hero(tables, "cleric")
    fighter = hero(tables, "fighter", seed=5)
    game = game_with(world, tables, cleric, fighter)
    assert magic.road_problem(game, cleric, "cure_wounds", fighter) == "nobody needs healing"
    fighter.hp = 3
    fighter.wounds.append(make_wound("torso", "slashing", 2, RNG(1)))
    assert magic.road_problem(game, cleric, "cure_wounds", fighter) is None
    said = magic.cast_on_road(game, cleric, "cure_wounds", fighter)
    assert any("Cure Wounds" in s for s in said)
    assert fighter.hp > 3


def test_lasting_text_reads_like_speech():
    assert magic.lasting_text(8.0) == "eight hours"
    assert magic.lasting_text(1.0) == "an hour"
    assert magic.lasting_text(1 / 6) == "10 minutes"
    assert magic.lasting_text(2.6) == "3 hours"


def test_stoneskin_resists_weapons_in_the_next_fight(world, tables):
    wiz = hero(tables, "wizard")
    award_xp(wiz, 23000, tables, RNG(3), auto=True)
    wiz.spells["spellbook"].append("stoneskin")
    game = game_with(world, tables, wiz)
    said = magic.cast_on_road(game, wiz, "stoneskin")
    assert "an hour" in said[0]
    b = fight(tables, [wiz])
    assert "slashing" in [r for x in b.side(PARTY)[0].buffs for r in x.get("resist", [])]


def test_the_spells_screen_casts(make_app):
    import tcod.console

    from realmwalker.game.state import new_game as ng
    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.spells import SpellsScreen

    app = make_app()
    tables = app.tables
    world = WorldGenerator(WorldOptions("Screenland", 5, "small"), tables).generate()
    wiz = hero(tables, "wizard")
    app.start_game(ng(world, tables, wiz))
    screen = SpellsScreen(app, app.game)
    app.push(screen)
    order = screen.spells()
    screen.sel = order.index("mage_armor")
    for size in ((80, 30), (160, 45)):
        app.render(tcod.console.Console(*size, order="F"))
    app.handle_event(KeyEvent("enter"))
    assert "mage_armor" in sp.lasting(wiz, tables)
    assert "Mage Armour" in screen.message
    for key in ("right", "down", "enter", "tab", "pagedown", "end", "home"):
        app.handle_event(KeyEvent(key))
        app.render(tcod.console.Console(80, 30, order="F"))
    assert app.error_count == 0


def test_identify_tells_a_wizard_what_a_strange_thing_is(world, tables):
    from realmwalker.game import magic_items

    wiz = hero(tables, "wizard")
    wiz.spells["spellbook"].append("identify")
    game = game_with(world, tables, wiz)
    assert magic.road_problem(game, wiz, "identify") == "nothing you carry is strange to you"
    from realmwalker.rules.inventory import add_existing

    ring = add_existing(wiz, tables.items, magic_items.make(game, game.world.rng.child("test-ring"), rarity="uncommon"))
    ring.magic["identified"] = False
    assert not ring.magic.get("identified")
    slots = sp.slots_left(wiz, tables)[0]
    t0 = game.world.time
    said = magic.cast_on_road(game, wiz, "identify")
    assert "Identify" in said[0] and ring.magic["identified"]
    assert sp.slots_left(wiz, tables)[0] == slots - 1 and game.world.time - t0 == 10
    # Never in a fight, and never from a scroll read aloud in one.
    b = fight(tables, [wiz])
    menu = {sid: (ok, why) for sid, ok, why in b.spell_options(b.side(PARTY)[0])}
    assert menu["identify"] == (False, "not in a fight")
