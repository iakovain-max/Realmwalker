"""Expansion 3 C.3: spell scrolls by the 2024 rules (DMG p. 309: who can read one, its own save DC and attack bonus,
the check above your level, copying into a spellbook; the thief's Use Magic Device, PHB p. 140) and the potions of
healing (DMG p. 292: four strengths, a bonus action to drink or give)."""

import pytest

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.game import care, magic, treasure
from realmwalker.rules import spells as sp
from realmwalker.rules import tactics
from realmwalker.rules.engine import actions, effects
from realmwalker.rules.inventory import add_item
from realmwalker.rules.wounds import make_wound
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.test_feats import fight, hero, on_turn, soft
from tests.test_road_magic import game_with
from tests.test_rogue import rogue
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Spellroad", 31, "small"), tables)


def fixed_d20(monkeypatch, value):
    class Roll:
        natural = value
        total = value

    monkeypatch.setattr(dice, "d20", lambda *a, **k: Roll())


def scroll_option(b, f, sid):
    return next(o for o in b.spell_options(f) if o[0].startswith("scroll:") and o[0].endswith(f":{sid}"))


def spy_cast(monkeypatch):
    """Record the numbers each spell is cast with."""
    seen = []
    real = effects.cast

    def cast(b, f, sid, spell, target, point, **kw):
        seen.append(dict(kw, sid=sid))
        return real(b, f, sid, spell, target, point, **kw)

    monkeypatch.setattr(effects, "cast", cast)
    return seen


# ---------------------------------------------------------------------------- the scrolls themselves
def test_a_scroll_for_every_spell_valued_by_the_book(tables):
    for sid, spell in tables.spells.defs.items():
        if {"item", "again", "creature"} & set(spell["classes"]):  # (a flask; a spell's follow-up; a steed's gift)
            assert f"scroll_{sid}" not in tables.items
            continue
        d = tables.items.get(f"scroll_{sid}")
        assert d["use"]["scroll"] == sid and d["value"] > 0 and d["rarity"]
    assert tables.items.get("scroll_fire_bolt")["value"] == 3000  # (30 GP: PHB p. 231)
    assert tables.items.get("scroll_magic_missile")["value"] == 5000  # (50 GP)
    assert tables.items.get("scroll_fireball")["rarity"] == "uncommon"
    assert sp.scroll_numbers(tables, 0) == (13, 5) and sp.scroll_numbers(tables, 3) == (15, 7)
    assert sp.scroll_numbers(tables, 5) == (17, 9) and sp.scroll_numbers(tables, 9) == (19, 11)


def test_who_can_read_a_scroll(tables):
    wiz, priest, fighter = hero(tables, "wizard"), hero(tables, "cleric"), hero(tables, "fighter")
    assert sp.scroll_reader(wiz, tables, "magic_missile") == "sure"
    assert sp.scroll_reader(wiz, tables, "fireball") == "check"  # (level 3 for a level 1 wizard)
    assert sp.scroll_reader(priest, tables, "magic_missile") is None
    assert sp.scroll_reader(priest, tables, "cure_wounds") == "sure"
    assert sp.scroll_reader(fighter, tables, "magic_missile") is None
    assert "unintelligible" in sp.scroll_problem(fighter, tables, "magic_missile")
    thief = rogue(tables, 13)
    assert sp.scroll_reader(thief, tables, "magic_missile") == "device"
    assert sp.scroll_reader(thief, tables, "fireball") == "device_check"
    check = sp.scroll_check(__import__("realmwalker.rules.character", fromlist=["Sheet"]).Sheet(thief, tables),
                            tables, "fireball", "device_check")
    assert check[1] == 13 and "Arcana" in check[2]


# ---------------------------------------------------------------------------- in a fight
def test_a_wizard_reads_a_scroll_with_its_own_numbers_and_no_slot(tables, monkeypatch):
    wiz = hero(tables, "wizard")
    it = add_item(wiz, tables.items, "scroll_magic_missile")
    b = fight(tables, wiz, "wolf")
    me = b.fighters[0]
    on_turn(b, me)
    slots = sp.slots_left(wiz, tables)
    seen = spy_cast(monkeypatch)
    value, ok, why = scroll_option(b, me, "magic_missile")
    assert ok, why
    assert b.do_cast(me, value, b.enemies_of(me)[0])
    assert wiz.item(it.uid) is None and sp.slots_left(wiz, tables) == slots
    assert seen and seen[-1]["dc"] == 13 and seen[-1]["bonus"] == 5 and not seen[-1]["slotted"]


def test_a_fighter_cannot_read_a_wizards_scroll(tables):
    c = hero(tables, "fighter")
    it = add_item(c, tables.items, "scroll_magic_missile")
    b = fight(tables, c, "wolf")
    me = b.fighters[0]
    on_turn(b, me)
    value, ok, why = scroll_option(b, me, "magic_missile")
    assert not ok and "unintelligible" in why
    assert not b.do_cast(me, value, b.enemies_of(me)[0]) and c.item(it.uid) is not None


def test_a_scroll_above_you_takes_a_check_and_fades_on_a_failure(tables, monkeypatch):
    wiz = hero(tables, "wizard")
    it = add_item(wiz, tables.items, "scroll_fireball")
    b = fight(tables, wiz, "wolf")
    me = b.fighters[0]
    on_turn(b, me)
    seen = spy_cast(monkeypatch)
    fixed_d20(monkeypatch, 1)
    value, ok, _ = scroll_option(b, me, "fireball")
    foe = b.enemies_of(me)[0]
    assert ok and b.do_cast(me, value, point=foe.cells[0])
    assert wiz.item(it.uid) is None and not seen and me.action <= 0  # (the words faded: nothing happened)
    it = add_item(wiz, tables.items, "scroll_fireball")
    on_turn(b, me)
    fixed_d20(monkeypatch, 20)
    value, ok, _ = scroll_option(b, me, "fireball")
    assert b.do_cast(me, value, point=foe.cells[0])
    assert wiz.item(it.uid) is None and seen and seen[-1]["dc"] == 15


def test_a_thief_reads_any_scroll_by_use_magic_device(tables, monkeypatch):
    thief = rogue(tables, 13)
    it = add_item(thief, tables.items, "scroll_magic_missile")
    b = fight(tables, thief, "wolf")
    me = b.fighters[0]
    on_turn(b, me)
    value, ok, why = scroll_option(b, me, "magic_missile")
    assert ok, why
    assert b.do_cast(me, value, b.enemies_of(me)[0]) and thief.item(it.uid) is None


def test_the_auto_reads_a_scroll_when_the_slots_are_gone(tables):
    wiz = hero(tables, "wizard")
    wiz.spells["slots_used"] = list(sp.slots_total(wiz, tables)) + [0] * 8
    it = add_item(wiz, tables.items, "scroll_magic_missile")
    b = fight(tables, wiz, "ogre", spots={0: (3, 4), 1: (8, 4)})
    me = b.fighters[0]
    me.auto = True
    soft(b.fighters[1], ac=30)  # (a blow or a fire bolt would hardly land: the sure darts are worth more)
    on_turn(b, me)
    tactics.take_turn(b, me)
    assert wiz.item(it.uid) is None


# ---------------------------------------------------------------------------- outside a fight
def test_a_scroll_of_cure_wounds_heals_on_the_road(world, tables):
    priest = hero(tables, "cleric")
    game = game_with(world, tables, priest)
    priest.hp = max(1, priest.max_hp - 6)
    it = add_item(priest, tables.items, "scroll_cure_wounds")
    slots = sp.slots_left(priest, tables)
    said = magic.read_scroll(game, it)
    assert "scroll" in said[0] and priest.hp > priest.max_hp - 6
    assert priest.item(it.uid) is None and sp.slots_left(priest, tables) == slots


def test_a_healing_scroll_is_read_over_the_most_hurt(world, tables):
    priest, friend = hero(tables, "cleric"), hero(tables, "fighter", seed=2)
    game = game_with(world, tables, priest, friend)
    friend.hp = max(1, friend.max_hp - 7)
    it = add_item(priest, tables.items, "scroll_cure_wounds")
    said = magic.read_scroll(game, it)
    assert "scroll" in said[0] and friend.hp > friend.max_hp - 7
    assert not any(i.def_id == "scroll_cure_wounds" for c in game.party for i in c.inventory)


def test_scroll_lines_and_copying(world, tables):
    wiz = hero(tables, "wizard")
    game = game_with(world, tables, wiz)
    it = add_item(wiz, tables.items, "scroll_fire_bolt")
    assert "cantrip" in magic.copy_problem(game, wiz, it)
    lines = magic.scroll_lines(game, add_item(wiz, tables.items, "scroll_fireball"))
    assert any("DC 15" in line for line in lines) and any("beyond them" in line for line in lines)
    fighter = hero(tables, "fighter")
    lone = game_with(world, tables, fighter)
    assert any("No one in the party" in line for line in magic.scroll_lines(lone, add_item(fighter, tables.items,
                                                                                         "scroll_fireball")))


# ---------------------------------------------------------------------------- potions of healing
def test_four_potions_by_the_book(tables, world):
    heal = {d: tables.items.get(d)["use"]["heal"] for d in ("potion_healing", "potion_healing_greater",
                                                              "potion_healing_superior", "potion_healing_supreme")}
    assert heal == {"potion_healing": "2d4+2", "potion_healing_greater": "4d4+4",
                    "potion_healing_superior": "8d4+8", "potion_healing_supreme": "10d4+20"}
    assert tables.items.get("potion_healing_greater")["value"] == 20000  # (half an uncommon item's 400 GP)
    game = game_with(world, tables, hero(tables))
    rng = RNG(3, "loot")
    for variant, def_id in (("greater", "potion_healing_greater"), ("supreme", "potion_healing_supreme")):
        assert treasure.make_listed(game, "potion_of_healing", variant, "rare", rng).def_id == def_id


def test_a_potion_is_a_bonus_action_in_a_fight(tables):
    c = hero(tables, "fighter")
    it = add_item(c, tables.items, "potion_healing", 2)
    b = fight(tables, c, "wolf")
    me = b.fighters[0]
    on_turn(b, me)
    me.hp = 2
    opt = next(o for o in actions.options(b, me) if o.kind == "item" and o.value == it.uid)
    assert opt.cost == "bonus" and opt.available
    b.do_item(me, it.uid, me)
    assert me.hp > 2 and me.bonus <= 0 and me.action > 0
    assert b.item_problem(me, it) == "no bonus action left this turn"


def test_the_auto_drinks_when_low_and_pours_one_into_a_fallen_friend(tables):
    a, friend = hero(tables, "fighter"), hero(tables, "fighter", seed=2)
    add_item(a, tables.items, "potion_healing", 2)
    b = fight(tables, [a, friend], "wolf", spots={0: (3, 4), 1: (3, 5), 2: (9, 9)})
    me, other = b.fighters[0], b.fighters[1]
    me.auto = True
    other.hp = 0
    other.state = "down"
    on_turn(b, me)
    tactics.take_turn(b, me)
    assert other.hp > 0 and sum(i.qty for i in a.inventory if i.def_id == "potion_healing") == 1


def test_a_potion_drunk_on_the_road(world, tables):
    c = hero(tables, "fighter")
    game = game_with(world, tables, c)
    it = add_item(c, tables.items, "potion_healing")
    assert "no hurt" in care.drink_potion(game, c, it)[0] and c.item(it.uid) is not None
    c.wounds.append(make_wound("arm", "slashing", 2, RNG(1)))
    c.hp = 1
    said = care.drink_potion(game, c, it)
    assert "drinks" in said[0] and c.hp > 1 and c.item(it.uid) is None


def test_the_scroll_card_in_a_fight(tables):
    from realmwalker.rules import describe

    wiz = hero(tables, "wizard")
    add_item(wiz, tables.items, "scroll_fireball")
    b = fight(tables, wiz, "wolf")
    me = b.fighters[0]
    value, ok, why = scroll_option(b, me, "fireball")
    card = describe.choice(b, me, "cast", value, "Fireball", ok, why)
    words = " ".join(card.lines)
    assert card.title == "Fireball" and "From a scroll" in words and "DC 15" in words and "Beyond you" in words


# ---------------------------------------------------------------------------- after the fresh review
def test_a_countered_scroll_is_kept_and_the_casting_lost(tables, monkeypatch):
    wiz = hero(tables, "wizard")
    it = add_item(wiz, tables.items, "scroll_magic_missile")
    b = fight(tables, wiz, "cult_fanatic", spots={0: (3, 4), 1: (8, 4)})
    me, foe = b.side("party")[0], b.side("foe")[0]
    foe.cdef = dict(foe.cdef, spells=list(foe.cdef.get("spells", [])) + ["counterspell"])
    foe.slots = [0, 0, 1]
    monkeypatch.setattr(type(b), "_save", lambda self, f, ability, dc, **kw: False)
    on_turn(b, me)
    hp = foe.hp
    value, ok, _ = scroll_option(b, me, "magic_missile")
    assert ok and b.do_cast(me, value, foe)
    assert foe.hp == hp and foe.slots == [0, 0, 0] and me.action == 0
    assert wiz.item(it.uid) is not None  # (the scroll's words hold)


def test_a_thief_who_fails_the_arcana_check_loses_the_scroll(tables, monkeypatch):
    thief = rogue(tables, 13)
    it = add_item(thief, tables.items, "scroll_fireball")
    b = fight(tables, thief, "wolf")
    me = b.fighters[0]
    on_turn(b, me)
    seen = spy_cast(monkeypatch)
    fixed_d20(monkeypatch, 1)
    value, ok, _ = scroll_option(b, me, "fireball")
    assert ok and b.do_cast(me, value, point=b.enemies_of(me)[0].cells[0])
    assert thief.item(it.uid) is None and not seen and me.cast_action_spell


def test_a_potion_keeps_a_hurt_fighters_turn_open(tables):
    c = hero(tables, "fighter")
    add_item(c, tables.items, "potion_healing")
    b = fight(tables, c, "wolf")
    me = b.fighters[0]
    on_turn(b, me)
    me.action, me.attacks_left, me.move_left = 0, 0, 0
    me.hp = me.max_hp
    assert not any(x.startswith("item:") for x in b.bonus_options(me))  # (unhurt: not worth the bonus action)
    me.hp = me.max_hp - 3
    assert not b.turn_spent(me) and any(x.startswith("item:") for x in b.bonus_options(me))


def test_a_lasting_self_scroll_already_at_work_is_not_offered(tables):
    wiz = hero(tables, "wizard")
    add_item(wiz, tables.items, "scroll_mage_armor", 2)
    b = fight(tables, wiz, "wolf")
    me = b.fighters[0]
    on_turn(b, me)
    value, ok, why = scroll_option(b, me, "mage_armor")
    assert ok, why
    assert b.do_cast(me, value)
    on_turn(b, me)
    value, ok, why = scroll_option(b, me, "mage_armor")
    assert not ok and "already" in why


def test_the_weakest_potion_that_will_do(tables):
    a, friend = hero(tables, "fighter"), hero(tables, "fighter", seed=2)
    add_item(a, tables.items, "potion_healing")
    add_item(a, tables.items, "potion_healing_supreme")
    b = fight(tables, [a, friend], "wolf", spots={0: (3, 4), 1: (3, 5), 2: (9, 9)})
    me, other = b.fighters[0], b.fighters[1]
    other.hp, other.state = 0, "down"
    on_turn(b, me)
    assert tactics._drink(b, me, other)
    assert any(i.def_id == "potion_healing_supreme" for i in a.inventory)
    assert not any(i.def_id == "potion_healing" for i in a.inventory)
