"""Preparing spells (Expansion 3 C.1, PHB 2024): the class table's count, a cleric from the whole list and a wizard
from the book, the always-prepared domain spells, the list changed after a long rest or a new level (one spell
after a short rest: Memorize Spell), the Auto's choice by archetype, Ritual Adept, and one spell slot a turn."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import magic
from realmwalker.rules import spells as sp
from realmwalker.rules.combat import FOE, PARTY, Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.progression import award_xp, long_rest, short_rest
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402

XP = {3: 900, 5: 6500}


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Preparing", 41, "small"), tables)


def hero(tables, cls, level=1, seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("sage")
    c = b.build()
    if level > 1:
        award_xp(c, XP[level], tables, RNG(2), auto=True)
    return c


def game_with(world, tables, char):
    import copy

    from realmwalker.game.state import new_game

    return new_game(copy.deepcopy(world), tables, char)


def test_the_counts_follow_the_class_tables(tables):
    # PHB 2024 pp. 70 and 166, checked on the page images.
    cleric = tables.classes["cleric"]["spellcasting"]["prepared"]
    wizard = tables.classes["wizard"]["spellcasting"]["prepared"]
    assert cleric[:5] == [4, 5, 6, 7, 9] and cleric[-1] == 22 and len(cleric) == 20
    assert wizard[:5] == [4, 5, 6, 7, 9] and wizard[13:] == [18, 19, 21, 22, 23, 24, 25]
    c = hero(tables, "cleric")
    assert sp.prepared_count(c, tables) == 4 and len(sp.prepared(c, tables)) == 4
    # A cleric prepares from the whole list, and casts only what is prepared.
    level1 = [s for s in tables.spells.for_class("cleric", 1) if tables.spells[s]["level"] == 1]
    assert len(level1) > 4
    known = sp.known_spells(c, tables)
    assert set(level1) - set(known), "an unprepared prayer is not cast"
    w = hero(tables, "wizard")
    assert set(sp.prepared(w, tables)) <= set(w.spells["spellbook"]) and len(sp.prepared(w, tables)) == 4


def test_the_auto_prepares_by_what_the_caster_is_for(tables):
    healer = hero(tables, "cleric")
    assert {"cure_wounds", "healing_word"} & set(sp.prepared(healer, tables))
    wiz = hero(tables, "wizard")
    mine = sp.prepared(wiz, tables)
    assert "magic_missile" in mine and "shield" in mine
    wiz.spells["spellbook"].append("identify")
    wiz.spells["prepared"] = []
    sp.fill_prepared(wiz, tables)
    assert "identify" not in sp.prepared(wiz, tables), "a ritual is read from the book (Ritual Adept)"


def test_domain_spells_are_always_prepared_and_do_not_count(tables):
    c = hero(tables, "cleric", 5)
    c.subclass = "life"
    sp.fill_prepared(c, tables)
    always = sp.always_prepared(c, tables)
    assert {"bless", "cure_wounds", "lesser_restoration", "mass_healing_word", "revivify"} <= set(always)
    assert "aid" not in always  # (waits for the catalogue, Part D)
    assert sp.prepared_count(c, tables) == 9
    # (every other cleric spell of levels 1-3 the game has, until the catalogue brings more: Part D)
    assert len(sp.prepared(c, tables)) == min(9, len(sp.preparable(c, tables)))
    assert not set(always) & set(sp.prepared(c, tables))
    assert set(always) <= set(sp.known_spells(c, tables))
    assert sp.toggle_prepared(c, tables, "bless").endswith("always prepared.")


def test_the_list_changes_after_a_long_rest_until_the_next_fight(world, tables):
    from realmwalker.game import fight

    c = hero(tables, "cleric")
    game = game_with(world, tables, c)
    mine = sp.prepared(c, tables)
    other = next(s for s in sp.preparable(c, tables) if s not in mine)
    # A new character chooses freely until the first fight.
    assert sp.preparing_open(c) == "prepare"
    fight.start_battle(game, [spawn(tables, "wolf", RNG(1), 1)], "A wolf.")
    game.battle = None
    assert sp.preparing_open(c) == ""
    assert "after a long rest" in sp.toggle_prepared(c, tables, mine[0])
    assert "full" in sp.toggle_prepared(c, tables, other)
    long_rest(c, tables, RNG(3))
    assert "put aside" in sp.toggle_prepared(c, tables, mine[0])
    assert mine[0] not in sp.known_spells(c, tables)
    assert sp.toggle_prepared(c, tables, other) == f"{tables.spells[other]['name']} is prepared."
    assert other in sp.known_spells(c, tables) and len(sp.prepared(c, tables)) == 4


def test_memorize_spell_swaps_one_after_a_short_rest(tables):
    w = hero(tables, "wizard", 5)
    assert "memorize_spell" in w.features
    sp.close_preparing(w)
    mine = sp.prepared(w, tables)
    spare = [s for s in sp.preparable(w, tables) if s not in mine]
    assert spare, w.spells
    short_rest(w, tables, RNG(4))
    assert sp.preparing_open(w) == "memorize"
    assert "Memorize Spell" in sp.toggle_prepared(w, tables, mine[0])
    assert "after a long rest" in sp.toggle_prepared(w, tables, mine[1]), "only one"
    assert "is prepared" in sp.toggle_prepared(w, tables, spare[0])  # (an empty place is filled at any time)
    # A wizard below level 5 has no Memorize Spell.
    young = hero(tables, "wizard")
    sp.close_preparing(young)
    short_rest(young, tables, RNG(4))
    assert sp.preparing_open(young) == ""


def test_ritual_adept_reads_a_ritual_from_the_book(world, tables):
    from realmwalker.game import magic_items
    from realmwalker.rules.inventory import add_existing

    from realmwalker.rules.inventory import add_item

    wiz = hero(tables, "wizard")
    wiz.spells["spellbook"].append("identify")
    add_item(wiz, tables.items, "pearl")
    assert "identify" not in sp.known_spells(wiz, tables)
    game = game_with(world, tables, wiz)
    ring = add_existing(wiz, tables.items, magic_items.make(game, game.world.rng.child("ring"), rarity="uncommon"))
    ring.magic["identified"] = False
    assert magic.road_problem(game, wiz, "identify") is None
    assert "ritual" in magic.cast_on_road(game, wiz, "identify")[0] and ring.magic["identified"]
    # Anything else must be prepared first.
    wiz.spells["prepared"] = [s for s in sp.prepared(wiz, tables) if s != "mage_armor"]
    assert magic.road_problem(game, wiz, "mage_armor").startswith("not prepared")
    cleric = hero(tables, "cleric")
    unprepared = next(s for s in sp.preparable(cleric, tables) if s not in sp.prepared(cleric, tables)
                      and sp.road_use(tables, s))
    assert magic.road_problem(game_with(world, tables, cleric), cleric, unprepared).startswith("not prepared")


def test_one_spell_slot_a_turn_in_a_real_fight(tables):
    c = hero(tables, "cleric", 3)
    c.spells["prepared"] = ["guiding_bolt", "healing_word", "bless", "spiritual_weapon"]
    c.subclass = None
    b = Battle(tables, [c], [spawn(tables, "wolf", RNG(1), 1)], Env(), RNG(1, "battle"))
    b.start("Test fight.")
    while b.pending_party() is None and b.outcome is None:
        b.step()
    f, wolf = b.pending_party(), b.side(FOE)[0]
    menu = {sid: (ok, why) for sid, ok, why in b.spell_options(f)}
    assert menu["guiding_bolt"][0] and menu["healing_word"][0]
    # A bonus-action spell with a slot, then the action: a cantrip still, but no second slot (2024).
    assert b.do_cast(f, "healing_word", f)
    menu = {sid: (ok, why) for sid, ok, why in b.spell_options(f)}
    assert menu["guiding_bolt"] == (False, "one spell slot a turn: a slot has been spent this turn")
    assert menu["sacred_flame"][0], "a cantrip goes beside it"
    used = list(c.spells["slots_used"])
    assert not b.do_cast(f, "guiding_bolt", wolf) and c.spells["slots_used"] == used
    assert b.do_cast(f, "sacred_flame", wolf)
    b.end_turn()
    while b.outcome is None and b.pending_party() is None:
        b.step()
    if b.outcome is None:
        assert {sid: ok for sid, ok, _ in b.spell_options(f)}["guiding_bolt"], "a new turn, a new slot"


def test_the_spells_page_prepares(make_app):
    import tcod.console

    from realmwalker.game.state import new_game
    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.spells import SpellsScreen

    app = make_app()
    t = app.tables
    world = cached_world(WorldOptions("Screenland", 5, "small"), t)
    c = hero(t, "cleric")
    app.start_game(new_game(world, t, c))
    screen = SpellsScreen(app, app.game)
    app.push(screen)
    order = screen.spells()
    mine = sp.prepared(c, t)
    spare = next(s for s in order if t.spells[s]["level"] and s not in mine)
    assert spare in order, "the page lists what could be prepared too"
    screen.sel = order.index(mine[0])
    app.render(tcod.console.Console(120, 40, order="F"))
    shown = app.last_canvas.words()
    assert "Prepared: 4 of 4" in shown and "Put aside" in shown
    app.handle_event(KeyEvent("p"))
    assert mine[0] not in sp.prepared(c, t) and "put aside" in screen.message
    screen.sel = order.index(spare)
    app.handle_event(KeyEvent("p"))
    assert spare in sp.prepared(c, t)
    for size in ((80, 30), (160, 45)):
        app.render(tcod.console.Console(*size, order="F"))
    assert app.error_count == 0
