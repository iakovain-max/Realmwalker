"""Schools & Domains Part D: the wizard's and cleric's wands, staffs and rods of the DMG 2024 - one store of charges per
thing, spells drawn from it in a fight and on the road, the last charge's d20, and the powers beyond a spell."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import gear, magic as roadmagic, treasure
from realmwalker.rules import grid, magic, spells as spellrules, tactics
from realmwalker.rules.combat import PARTY
from realmwalker.rules.engine import query
from realmwalker.rules.engine.handlers import staves
from tests.test_gear import companion, fight_with, game, person, tables, world  # noqa: F401 (fixtures)
from tests.test_gear_2024 import my_turn

BOOK = {  # slug: (variant, rarity, attunement, title, base)
    "wand_of_binding": ("", "rare", True, "Wand of Binding", "arcane_wand"),
    "wand_of_enemy_detection": ("", "rare", True, "Wand of Enemy Detection", "arcane_wand"),
    "wand_of_fear": ("", "rare", True, "Wand of Fear", "arcane_wand"),
    "wand_of_fireballs": ("", "rare", True, "Wand of Fireballs", "arcane_wand"),
    "wand_of_lightning_bolts": ("", "rare", True, "Wand of Lightning Bolts", "arcane_wand"),
    "wand_of_magic_detection": ("", "uncommon", False, "Wand of Magic Detection", "arcane_wand"),
    "wand_of_magic_missiles": ("", "uncommon", False, "Wand of Magic Missiles", "arcane_wand"),
    "wand_of_paralysis": ("", "rare", True, "Wand of Paralysis", "arcane_wand"),
    "wand_of_polymorph": ("", "very_rare", True, "Wand of Polymorph", "arcane_wand"),
    "wand_of_pyrotechnics": ("", "common", False, "Wand of Pyrotechnics", "arcane_wand"),
    "wand_of_the_war_mage": ("+2", "rare", True, "Wand of the War Mage +2", "arcane_wand"),
    "staff_of_adornment": ("", "common", False, "Staff of Adornment", "arcane_staff"),
    "staff_of_charming": ("", "rare", True, "Staff of Charming", "arcane_staff"),
    "staff_of_healing": ("", "rare", True, "Staff of Healing", "arcane_staff"),
    "staff_of_power": ("", "very_rare", True, "Staff of Power", "quarterstaff"),
    "staff_of_striking": ("", "very_rare", True, "Staff of Striking", "quarterstaff"),
    "staff_of_the_magi": ("", "legendary", True, "Staff of the Magi", "quarterstaff"),
    "enspelled_staff": ("level 2 or 3 spell", "rare", True, None, "quarterstaff"),
    "rod_of_absorption": ("", "very_rare", True, "Rod of Absorption", "arcane_rod"),
    "rod_of_alertness": ("", "very_rare", True, "Rod of Alertness", "arcane_rod"),
    "rod_of_resurrection": ("", "legendary", True, "Rod of Resurrection", "arcane_rod"),
    "rod_of_rulership": ("", "rare", True, "Rod of Rulership", "arcane_rod"),
}


def make(game, slug, seed=1, variant=None):
    v, rarity = BOOK[slug][0], BOOK[slug][1]
    it = treasure.make_listed(game, slug, v if variant is None else variant, rarity, RNG(seed, slug))
    assert it is not None, slug
    it.magic["identified"] = True
    return it


def give(c, it, slot="main_hand"):
    it.uid = c.new_uid()
    c.inventory.append(it)
    if slot:
        c.equipped[slot] = it.uid
    if it.magic.get("attune"):
        c.attuned.append(it.uid)
    return it


def battle(game, tables, slug, cls="wizard", foes=("bandit",), seed=1, near=True):
    c = person(tables, cls, bg="sage")
    it = give(c, make(game, slug, seed))
    b = fight_with(tables, c, *foes)
    me = b.side(PARTY)[0]
    them = [f for f in b.fighters if f.side != PARTY]
    for i, t in enumerate(them):
        t.x, t.y = me.x + (1 if near else 6), me.y + i
        t.hp = t.creature.hp = t.creature.max_hp = 200
    my_turn(b, me)
    return c, it, b, me, them


def value(c, it, sid):
    return f"charge:{it.uid}:{sid}"


class Rolls:
    """An rng whose d20s come out as asked (for the last charge)."""
    def __init__(self, n):
        self.n = n

    def randint(self, a, b):
        return self.n if b == 20 else a

    def random(self):
        return 0.0


# ---------------------------------------------------------------------------- made as the book says
@pytest.mark.parametrize("slug", sorted(BOOK))
def test_each_is_made_as_the_book_says(game, slug):
    v, rarity, attune, title, base = BOOK[slug]
    it = make(game, slug)
    assert it.def_id == base
    assert bool(it.magic.get("attune")) == attune
    if title:
        assert it.magic["title"] == title
    for p in magic.props(it):
        if p.get("kind") == "charges":
            assert p["spell"] in game.tables.spells, p
            if magic.pooled(p) and int(p["cost"]) > 0:
                assert magic.pool(it) is not None
    assert any(p.get("text") for p in magic.props(it)), "its card must say what it does"


def test_the_enspelled_staff_binds_a_spell_of_its_levels(game):
    t = game.tables
    for variant, levels, dc in (("cantrip or level 1 spell", {0, 1}, 13), ("level 2 or 3 spell", {2, 3}, None),
                                ("level 4 or 5 spell", {4, 5}, None), ("level 6, 7, or 8 spell", {6, 7, 8}, None)):
        for seed in range(6):
            it = make(game, "enspelled_staff", seed, variant)
            p = next(p for p in magic.props(it) if p.get("kind") == "charges")
            level = t.spells[p["spell"]]["level"]
            assert level in levels
            assert [p["dc"], p["attack"]] == treasure.spec(game)["enspell"][str(level)]
            if dc:
                assert p["dc"] == dc
            assert magic.pool(it)["value"] == 6 and magic.pool(it)["last"] == "mundane"
            assert t.spells[p["spell"]]["name"] in it.magic["title"]


def test_hoards_find_them(game):
    found = set()
    for seed in range(400):
        it = treasure.magic_item(game, RNG(seed, "hoard"), "rare", "arcana")
        if it is not None and it.magic.get("book"):
            found.add(it.magic["book"])
    assert {"wand_of_fireballs", "wand_of_binding", "staff_of_charming"} & found


# ---------------------------------------------------------------------------- one store, levels for charges
def test_a_wand_of_fireballs_burns_hotter_for_more_charges(game, tables):
    c, it, b, me, them = battle(game, tables, "wand_of_fireballs", foes=("bandit", "bandit"), near=False)
    v = value(c, it, "fireball")
    opts = {o[0]: o for o in b.spell_options(me)}
    assert opts[v][1], opts[v]
    prop = next(p for p in magic.props(it) if p.get("spell") == "fireball")
    assert magic.charge_levels(it, prop, 3) == [3, 4, 5]
    target = them[0]
    b.show_dice = True
    assert b.do_cast(me, v, None, slot_level=5, point=(target.x, target.y))
    assert magic.pool(it)["left"] == 4  # (three charges for level 5)
    cast = next(e for e in reversed(b.events) if e.get("kind") == "cast")
    assert cast["spell"] == "fireball"
    assert any("vs DC 15" in text for text, _k in b.log[-20:])  # (the wand's own DC, not the wizard's)


def test_a_spell_the_store_cannot_pay_for_is_not_offered(game, tables):
    c, it, b, me, them = battle(game, tables, "wand_of_binding", cls="fighter")
    magic.pool(it)["left"] = 3
    opts = {o[0]: o for o in b.spell_options(me)}
    assert opts[value(c, it, "hold_person")][1]
    assert not opts[value(c, it, "hold_monster")][1]  # (5 charges)
    prop = next(p for p in magic.props(it) if p.get("spell") == "hold_person")
    assert prop["dc"] == 17


def test_the_last_charge_rolls_a_d20(game, tables):
    c = person(tables, "wizard", bg="sage")
    it = give(c, make(game, "wand_of_magic_missiles"))
    magic.pool(it)["left"] = 0
    assert magic.drained(c, it, Rolls(2)) == []
    assert it in c.inventory
    words = magic.drained(c, it, Rolls(1))
    assert words and it not in c.inventory and it.uid not in c.attuned
    staff = give(c, make(game, "staff_of_power"), slot=None)
    magic.pool(staff)["left"] = 0
    magic.drained(c, staff, Rolls(1))
    assert [p["kind"] for p in magic.props(staff)] == ["bonus"]  # (only its +2 as a weapon)
    magi = give(c, make(game, "staff_of_the_magi"), slot=None)
    magic.pool(magi)["left"] = 0
    magic.drained(c, magi, Rolls(20))
    assert 2 <= magic.pool(magi)["left"] <= 13  # (1d12 + 1 back on a 20)
    striking = give(c, make(game, "staff_of_striking"), slot=None)
    magic.pool(striking)["left"] = 0
    magic.drained(c, striking, Rolls(1))
    assert not striking.magic and striking in c.inventory  # (a plain quarterstaff)


def test_charges_come_back_at_dawn_by_their_dice(game):
    it = make(game, "staff_of_healing")
    magic.pool(it)["left"] = 0
    magic.dawn([it], RNG(3, "dawn"))
    assert 5 <= magic.pool(it)["left"] <= 10  # (1d6 + 4)
    rod = make(game, "rod_of_resurrection")
    magic.pool(rod)["left"] = 0
    magic.dawn([rod], RNG(3, "dawn"))
    assert magic.pool(rod)["left"] == 1


# ---------------------------------------------------------------------------- the Auto
def test_the_auto_spends_a_wands_charges(game, tables):
    c, it, b, me, them = battle(game, tables, "wand_of_magic_missiles", cls="fighter", near=False)
    for t in them:
        t.hp = t.creature.hp = 12
    me.auto = True
    tactics.take_turn(b, me)
    assert magic.pool(it)["left"] < 7


# ---------------------------------------------------------------------------- wands
def test_the_wand_of_paralysis_locks_a_foe(game, tables):
    c, it, b, me, them = battle(game, tables, "wand_of_paralysis")
    t = them[0]
    t.cdef = dict(t.cdef, abilities=dict(t.cdef["abilities"], con=1), saves={})
    for _ in range(10):
        my_turn(b, me)
        b.do_cast(me, value(c, it, "wand_paralysis"), t)
        if "paralyzed" in t.conditions:
            break
    assert "paralyzed" in t.conditions


def test_the_wand_of_enemy_detection_finds_the_unseen(game, tables):
    c, it, b, me, them = battle(game, tables, "wand_of_enemy_detection", near=False)
    t = them[0]
    t.hidden = 99
    assert not b.can_see(me, t)
    assert b.do_cast(me, value(c, it, "wand_enemy_detection"), None)
    assert b.can_see(me, t)


def test_the_war_mages_wand_sharpens_spell_attacks(game, tables):
    from realmwalker.rules.character import Sheet

    c = person(tables, "wizard", bg="sage")
    before = spellrules.attack_bonus(Sheet(c, tables), tables)
    it = give(c, make(game, "wand_of_the_war_mage"))
    assert spellrules.attack_bonus(Sheet(c, tables), tables) >= before + 2  # (+2, and a focus in hand)
    del c.equipped["main_hand"]
    assert spellrules.attack_bonus(Sheet(c, tables), tables) == before  # (only while held)
    assert it in c.inventory


def test_the_war_mages_wand_ignores_half_cover(game, tables, monkeypatch):
    from types import SimpleNamespace

    c, it, b, me, them = battle(game, tables, "wand_of_the_war_mage", near=False)
    spell = SimpleNamespace(kind="spell", is_melee=False)  # (a Fire Bolt's attack)
    bow = SimpleNamespace(kind="ranged", is_melee=False)
    monkeypatch.setattr(type(b), "cover", lambda self, a, t: grid.HALF)
    assert b.target_ac(me, them[0], spell)[1] == grid.NONE
    assert b.target_ac(me, them[0], bow)[1] == grid.HALF


def test_the_pyrotechnics_wand_lights_an_evening(game, tables):
    game.party.append(companion(tables))
    c = game.leader
    for member in game.party:
        for it in list(member.inventory):
            use = tables.items.get(it.def_id).get("use") or {}
            if use.get("music") or use.get("game"):
                member.inventory.remove(it)
    wand = give(c, make(game, "wand_of_pyrotechnics"), slot=None)
    assert gear.evening_problem(game) is None
    out = gear.evening(game)
    assert any("coloured fire" in line for line in out)
    assert magic.pool(wand)["left"] == 6


# ---------------------------------------------------------------------------- staffs
def test_the_staff_of_striking_spends_charges_on_a_hit(game, tables):
    c, it, b, me, them = battle(game, tables, "staff_of_striking", cls="fighter")
    t = them[0]
    t.cdef = dict(t.cdef, ac=1)
    opt = next(o for o in b.attack_options(me) if o.item_uid == it.uid)
    for _ in range(40):
        if b._attack(me, opt, t):
            break
    assert magic.pool(it)["left"] < 10


def test_the_staff_of_power_guards_its_bearer(game, tables):
    from realmwalker.rules.character import Sheet

    c = person(tables, "wizard", bg="sage")
    before = Sheet(c, tables)
    ac, save = before.armor_class(), before.save_bonus("dex")
    give(c, make(game, "staff_of_power"))
    after = Sheet(c, tables)
    assert after.armor_class() == ac + 2
    assert after.save_bonus("dex") == save + 2


def test_retributive_strike_breaks_the_staff(game, tables):
    c, it, b, me, them = battle(game, tables, "staff_of_power")
    ids = [a[0] for a in b.class_abilities(me)]
    assert "retributive_strike" in ids
    before = them[0].hp
    b.do_ability(me, "retributive_strike")
    assert it not in c.inventory
    assert them[0].hp < before


def test_the_staff_of_healing_mends_on_the_road(game, tables):
    c = game.leader
    staff = give(c, make(game, "staff_of_healing"), slot=None)
    c.hp = 1
    held = next((i, p) for i, p in roadmagic.item_spells(game, c) if p["spell"] == "cure_wounds")
    assert roadmagic.road_problem(game, c, "cure_wounds", c, charge=held) is None
    out = roadmagic.cast_on_road(game, c, "cure_wounds", c, slot_level=3, charge=held)
    assert c.hp > 1, out
    assert magic.pool(staff)["left"] == 7  # (3 charges for level 3)


def test_the_staff_of_charming_shakes_off_an_enchantment(game, tables):
    c, it, b, me, them = battle(game, tables, "staff_of_charming", cls="cleric")
    foe = them[0]
    b._casting, b._casting_sid = foe, "command"
    try:
        assert b._save(me, "wis", 40)  # (a failure made a success, once a day)
        assert not b._save(me, "wis", 40)
    finally:
        b._casting = b._casting_sid = None


def test_the_staff_of_the_magi_drinks_a_spell(game, tables):
    c, it, b, me, them = battle(game, tables, "staff_of_the_magi")
    foe = them[0]
    magic.pool(it)["left"] = 10
    me.reaction = True
    assert staves.absorbed(b, foe, "hold_person", tables.spells["hold_person"], me, 2)
    assert magic.pool(it)["left"] == 12
    b._casting = foe
    try:
        roll = query.save_roll(b, me, "wis")
    finally:
        b._casting = None
    assert roll.roll.advantage


# ---------------------------------------------------------------------------- rods
def test_the_rod_of_absorption_stores_a_spell_and_gives_a_slot(game, tables):
    c, it, b, me, them = battle(game, tables, "rod_of_absorption")
    prop = next(p for p in magic.props(it) if p.get("kind") == "absorb")
    prop["left"] = prop["value"] = 0
    me.reaction = True
    assert staves.absorbed(b, them[0], "hold_person", tables.spells["hold_person"], me, 2)
    assert prop["left"] == 2 and prop["value"] == 2
    spellrules.spend_slot(c, 1)
    assert staves.draw_level(b, me) == 1
    left = spellrules.slots_left(c, tables)[0]
    b.do_ability(me, "rod_draw")
    assert spellrules.slots_left(c, tables)[0] == left + 1
    assert prop["left"] == 1


def test_the_rod_of_alertness_and_its_aura(game, tables):
    c, it, b, me, them = battle(game, tables, "rod_of_alertness", cls="fighter")
    assert query.initiative_roll(me).advantage
    ac = me.ac()
    assert b.do_cast(me, value(c, it, "rod_aura"), None)
    assert me.ac() == ac + 1
    opts = {o[0] for o in b.spell_options(me)}
    assert value(c, it, "see_invisibility") in opts


def test_the_rod_of_rulership_holds_foes_in_thrall(game, tables):
    c, it, b, me, them = battle(game, tables, "rod_of_rulership", cls="fighter", foes=("bandit", "bandit"))
    for t in them:
        t.cdef = dict(t.cdef, abilities=dict(t.cdef["abilities"], wis=1), saves={})
    assert b.do_cast(me, value(c, it, "rod_rulership"), None)
    assert any("charmed" in t.conditions for t in them)


def test_the_rod_of_resurrection_heals_in_a_fight(game, tables):
    c, it, b, me, them = battle(game, tables, "rod_of_resurrection", cls="cleric")
    me.hp = 3
    assert b.do_cast(me, value(c, it, "heal"), me)
    assert me.hp > 3
    assert magic.pool(it)["left"] == 4


def test_an_items_spells_are_listed_on_the_road(game, tables):
    c = game.leader
    give(c, make(game, "staff_of_the_magi"), slot=None)
    listed = {p["spell"] for _i, p in roadmagic.item_spells(game, c)}
    assert {"detect_magic", "arcane_lock", "plane_shift"} <= listed
    from realmwalker.ui.screens.battle import charge_words

    it = next(i for i, _p in roadmagic.item_spells(game, c))
    assert "at will" in charge_words(c, f"charge:{it.uid}:detect_magic", tables)
    assert "7 charges" in charge_words(c, f"charge:{it.uid}:plane_shift", tables)


def test_the_auto_draws_a_slot_from_the_rod(game, tables):
    c, it, b, me, them = battle(game, tables, "rod_of_absorption")
    prop = next(p for p in magic.props(it) if p.get("kind") == "absorb")
    prop["left"] = 5
    while spellrules.slots_left(c, tables)[0] > 0:
        spellrules.spend_slot(c, 1)
    tactics._rod_slots(b, me)
    assert spellrules.slots_left(c, tables)[0] == 1 and prop["left"] == 4


def test_the_mage_carries_a_wand(tables):
    gear = dict(tables.creatures["mage"]["gear"]) if isinstance(tables.creatures["mage"], dict) else {}
    assert "arcane_wand" in gear


def test_the_spells_page_casts_from_a_staff(make_app):
    import tcod.console

    from realmwalker.game.state import new_game
    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.spells import SpellsScreen
    from realmwalker.world.generator import WorldOptions
    from tests.worlds import cached_world

    app = make_app()
    t = app.tables
    world = cached_world(WorldOptions("Screenland", 5, "small"), t)
    c = person(t, "fighter")
    app.start_game(new_game(world, t, c))
    app.game.survival = False
    staff = give(c, make(app.game, "staff_of_healing"), slot=None)
    c.hp = 1
    screen = SpellsScreen(app, app.game)
    app.push(screen)
    order = screen.spells()
    v = f"charge:{staff.uid}:cure_wounds"
    assert v in order
    screen.sel = order.index(v)
    app.render(tcod.console.Console(120, 40, order="F"))
    shown = app.last_canvas.words()
    assert "Wands, staffs, rods" in shown and "Staff of Healing" in shown and "1 charge of 10 left" in shown
    app.handle_event(KeyEvent("l"))
    app.handle_event(KeyEvent("enter"))
    assert c.hp > 1 and magic.pool(staff)["left"] == 8
    for size in ((80, 30), (160, 45)):
        app.render(tcod.console.Console(*size, order="F"))
    assert app.error_count == 0
