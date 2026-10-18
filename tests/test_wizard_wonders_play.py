"""Schools & Domains Part E in play: the Ring of Spell Storing, the Pearl of Power, the five robes, the wizard's
hats, Enspelled Armor and Weapon, the Ruby of the War Mage, a crystal ball and the Enduring Spellbook - in real fights
and on the road (the makers are checked in tests/test_wizard_wonders.py)."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import wonders
from realmwalker.rules import magic
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import PARTY
from realmwalker.rules.combat import spell_id as spell_of
from realmwalker.rules.engine import actions
from tests.test_gear import companion, fight_with, game, person, tables, world  # noqa: F401 (fixtures)
from tests.test_gear_2024 import my_turn
from tests.test_wizard_wonders import battle, give, make


# ---------------------------------------------------------------------------- the ring
def _clear_ring(ring):
    ring.magic["props"] = [p for p in ring.magic["props"] if not p.get("stored")]


def test_a_found_ring_keeps_up_to_five_levels(game):
    for seed in range(1, 12):
        ring = make(game, "ring_of_spell_storing", seed)
        assert 0 <= magic.stored_levels(ring) <= 5
        for p in ring.magic["props"]:
            if p.get("stored"):
                assert 1 <= p["level"] <= 5 and p["dc"] >= 13 and p["value"] == p["left"] == 1


def test_a_spell_cast_into_the_ring_is_cast_later_once_with_its_casters_numbers(game, tables):
    wiz = person(tables, "wizard", bg="sage")
    game.party[0] = wiz
    fighter = companion(tables)
    game.party.append(fighter)
    ring = give(fighter, make(game, "ring_of_spell_storing"))
    _clear_ring(ring)
    left = spellrules.slots_left(wiz, tables)[0]
    assert wonders.store_problem(game, wiz, "magic_missile", 1) is None
    lines = wonders.store(game, wiz, "magic_missile", 1)
    assert "into the ring" in lines[0] and spellrules.slots_left(wiz, tables)[0] == left - 1
    assert magic.stored_levels(ring) == 1 and wonders.room(ring) == 4
    kept = next(p for p in ring.magic["props"] if p.get("stored"))
    assert kept["dc"] == spellrules.save_dc(game.sheet(wiz), tables)
    assert wonders.store_problem(game, wiz, "fireball", 3) is not None  # (not hers to cast)
    b = fight_with(tables, fighter, "bandit")
    me = b.side(PARTY)[0]
    foe = [f for f in b.fighters if f.side != PARTY][0]
    foe.hp = foe.creature.hp = 100
    my_turn(b, me)
    value = f"charge:{ring.uid}:magic_missile"
    assert any(o.value == value and o.available for o in actions.options(b, me, only=("cast",)))
    assert b.do_cast(me, value, foe)
    assert foe.hp < 100 and magic.stored_levels(ring) == 0 and wonders.room(ring) == 5


def test_a_ring_is_cast_from_only_while_worn(game, tables):
    c = person(tables, "fighter")
    ring = give(c, make(game, "ring_of_spell_storing"), slot="")
    _clear_ring(ring)
    wonders._keep(game, ring, "magic_missile", 2, 15, 7, 4, "")
    assert not magic.charges(c)
    c.equipped["ring"] = ring.uid
    assert [p["spell"] for _it, p in magic.charges(c)] == ["magic_missile"]


# ---------------------------------------------------------------------------- the pearl
def test_the_pearl_of_power_gives_back_a_slot_once_a_day(game, tables):
    c, pearl, b, me, them = battle(game, tables, "pearl_of_power")
    spellrules.spend_slot(c, 1)
    full = spellrules.slots_total(c, tables)[0]
    assert spellrules.slots_left(c, tables)[0] == full - 1
    assert {aid: ok for aid, _n, ok, _w in b.class_abilities(me)}.get("pearl_draw") is True
    b.do_ability(me, "pearl_draw")
    assert spellrules.slots_left(c, tables)[0] == full
    spellrules.spend_slot(c, 1)
    my_turn(b, me)
    assert {aid: ok for aid, _n, ok, _w in b.class_abilities(me)}.get("pearl_draw") is False
    magic.dawn([pearl], RNG(1, "dawn"))
    assert wonders.pearl_problem(c, tables, pearl) is None


def test_the_pearl_on_the_road(game, tables):
    from realmwalker.game import gear

    c = person(tables, "wizard", bg="sage")
    game.party[0] = c
    pearl = give(c, make(game, "pearl_of_power"))
    assert gear.use_name(game, pearl) == "Take back a spell slot"
    assert "no spent spell slot" in gear.use_item(game, c, pearl)[0]
    spellrules.spend_slot(c, 1)
    assert "comes back" in gear.use_item(game, c, pearl)[0]
    assert spellrules.slots_left(c, tables)[0] == spellrules.slots_total(c, tables)[0]


# ---------------------------------------------------------------------------- the robes
def test_the_robe_of_the_archmagi(game, tables):
    c = person(tables, "wizard", bg="sage")
    sheet = game.sheet(c)
    ac, dc, atk = sheet.armor_class(), spellrules.save_dc(sheet, tables), spellrules.attack_bonus(sheet, tables)
    give(c, make(game, "robe_of_the_archmagi"))
    sheet = game.sheet(c)
    assert sheet.armor_class() == 15 + sheet.mod("dex") and sheet.armor_class() > ac
    assert spellrules.save_dc(sheet, tables) == dc + 2 and spellrules.attack_bonus(sheet, tables) == atk + 2
    assert "magic_resistance" in magic.traits(c)


def test_the_robe_of_eyes_sees_and_is_blinded_by_daylight(game, tables):
    c, robe, b, me, them = battle(game, tables, "robe_of_eyes")
    assert me.senses["darkvision"] >= 120 and me.senses["truesight"] == 120
    assert "robe_of_eyes" in magic.traits(c)
    sp = tables.spells["daylight"]
    b.cast(them[0], "daylight", sp, None, None, up=0, mod=3, dc=13, bonus=5, mult=1, level=3)
    assert "blinded" in me.conditions
    assert any(e["cond"] == "blinded" and e["dc"] == 15 for e in me.save_ends)


def test_the_robe_of_stars(game, tables):
    c, robe, b, me, them = battle(game, tables, "robe_of_stars")
    assert magic.total(c, "save") == 1
    value = f"charge:{robe.uid}:magic_missile"
    hp = them[0].hp
    assert b.do_cast(me, value, them[0])
    assert hp - them[0].hp >= 14  # (the level 5 version: seven darts of 1d4 + 1)
    stars = next(p for p in robe.magic["props"] if p.get("spell") == "magic_missile")
    assert stars["left"] == 5
    my_turn(b, me)
    b.do_ability(me, "astral_step")
    assert me.state == "away" and me.away["why"] == "astral"
    b._start_of_turn(me)
    assert me.state == "fighting" and me.action == 0


def test_the_robe_of_stars_casts_only_while_worn(game, tables):
    c = person(tables, "wizard", bg="sage")
    give(c, make(game, "robe_of_stars"), slot="")
    assert not any(p.get("spell") == "magic_missile" for _it, p in magic.charges(c))


def test_the_robe_of_scintillating_colors(game, tables, monkeypatch):
    c, robe, b, me, them = battle(game, tables, "robe_of_scintillating_colors", foes=("bandit", "bandit"))
    monkeypatch.setattr(type(b), "_save", lambda self, f, *a, **k: f.side == PARTY)
    assert b.do_cast(me, f"charge:{robe.uid}:robe_colors", None)
    assert me.buff_value("blurred")
    assert all("stunned" in t.conditions for t in them)
    assert "stunned" not in me.conditions


def test_the_robe_of_useful_items(game, tables):
    from realmwalker.game import gear

    c = game.leader
    robe = give(c, make(game, "robe_of_useful_items"))
    left = wonders.patches(robe)
    assert len(left) >= 12 + 4 and not set(left) & set(wonders.CANNOT)
    for p in ("bullseye_lantern", "dagger", "mirror", "pole", "rope", "sack"):
        assert left.count(p) >= 2
    assert gear.use_name(game, robe) == "Tear off a patch"
    rows = wonders.choices(game, c, robe)
    assert any(what == "pole" for _w, what in rows)
    n = sum(it.qty for it in c.inventory if it.def_id == "pole")
    wonders.choose(game, c, robe, "pole")
    assert sum(it.qty for it in c.inventory if it.def_id == "pole") == n + 1
    assert len(wonders.patches(robe)) == len(left) - 1
    next(p for p in robe.magic["props"] if p.get("kind") == "patches")["left"] = ["gold_100"]
    money = c.money
    wonders.choose(game, c, robe, "gold_100")
    assert c.money == money + 10000 and not robe.magic


# ---------------------------------------------------------------------------- hats
def _aim(b, me, them, value, tables):
    sp = tables.spells[spell_of(value)]
    target = them[0] if sp["target"] in ("enemy", "creature") else me if sp["target"] in ("ally",) else None
    point = (them[0].x, them[0].y) if sp["target"] in ("point", "direction") else None
    return target, point


def test_the_hat_of_many_spells_casts_an_unknown_spell(game, tables, monkeypatch):
    from realmwalker.rules import hats

    c, hat, b, me, them = battle(game, tables, "hat_of_many_spells", near=False)
    assert spellrules.has_focus(c, tables) and spellrules.focus_bonus(c, tables) == 1
    options = b.hat_options(me)
    known = set(spellrules.known_spells(c, tables)) | set(c.spells.get("spellbook", ()))
    assert options and all(spell_of(v) not in known for v, _ok, _w in options)
    value = next(v for v, ok, _w in options if ok and tables.spells[spell_of(v)]["target"] == "enemy")
    monkeypatch.setattr(type(b), "check", lambda self, f, skill, dc, why="": True)
    left = spellrules.slots_left(c, tables)[0]
    assert b.do_cast(me, value, them[0])
    assert spellrules.slots_left(c, tables)[0] == left - 1
    assert hats.prop(hat)["spent"] == "short" and not b.hat_options(me, short=True)
    assert any("out of the Hat of Many Spells" in line for line, _kind in b.log[-8:])
    hats.rest(c, False)
    assert hats.ready(hat)


def test_the_hat_of_many_spells_mishaps(game, tables, monkeypatch):
    from realmwalker.rules import hats

    c, hat, b, me, them = battle(game, tables, "hat_of_many_spells", near=False)
    c.spells["slots_used"] = [0] * 9
    value = next(v for v, ok, _w in b.hat_options(me) if ok)
    monkeypatch.setattr(type(b), "check", lambda self, f, skill, dc, why="": False)
    for roll in (52, 58, 63, 68, 73, 78, 83, 88, 93, 99, 20):
        monkeypatch.setattr(hats, "mishap_roll", lambda rng, roll=roll: roll)
        my_turn(b, me)
        me.conditions.clear()
        me.cond_ends.clear()
        me.hp = me.max_hp
        me.slot_turn = None
        c.spells["slots_used"] = [0] * 9
        target, point = _aim(b, me, them, value, tables)
        assert b.do_cast(me, value, target, point=point)
        assert hats.ready(hat)  # (a failure never puts the Hat of Many Spells to rest)
    assert b.outcome is None or b.outcome


def test_the_hat_of_wizardry(game, tables, monkeypatch):
    from realmwalker.rules import hats

    c, hat, b, me, them = battle(game, tables, "hat_of_wizardry", near=False)
    options = b.hat_options(me)
    assert options and all(tables.spells[spell_of(v)]["level"] == 0 for v, _o, _w in options)
    monkeypatch.setattr(type(b), "check", lambda self, f, skill, dc, why="": False)
    value = next(v for v, ok, _w in options if ok)
    target, point = _aim(b, me, them, value, tables)
    assert b.do_cast(me, value, target, point=point)
    assert hats.prop(hat)["spent"] == "long"
    hats.rest(c, False)
    assert not hats.ready(hat)
    hats.rest(c, True)
    assert hats.ready(hat)


def test_the_auto_reaches_into_the_hat(game, tables, monkeypatch):
    from realmwalker.rules import hats, tactics

    c, hat, b, me, them = battle(game, tables, "hat_of_many_spells", near=False)
    opts = [o for o in actions.options(b, me, only=("cast",)) if str(o.value).startswith("hat:")]
    assert opts and all(tables.spells[spell_of(o.value)]["level"] == 1 for o in opts)
    c.spells["spellbook"] = []  # (a wizard who has forgotten every spell of their own reaches into the hat)
    c.spells["prepared"] = []
    monkeypatch.setattr(type(b), "check", lambda self, f, skill, dc, why="": True)
    me.auto = True
    left = spellrules.slots_left(c, tables)[0]
    tactics.take_turn(b, me)
    assert spellrules.slots_left(c, tables)[0] == left - 1 and hats.prop(hat).get("spent") == "short"


def test_a_hat_on_the_road(game, tables):
    from realmwalker.game import magic as roadmagic
    from realmwalker.rules import hats

    c = person(tables, "wizard", bg="sage")
    game.party[0] = c
    hat = give(c, make(game, "hat_of_wizardry"))
    road = hats.spells(c, tables, hat, battle=False)
    assert road and all(tables.spells[s]["level"] == 0 for s in road)
    lines = roadmagic.cast_from_hat(game, c, f"hat:{hat.uid}:{road[0]}", c)
    assert "hat" in lines[0].lower() and hats.prop(hat)["spent"] == "long"
    assert "rests" in roadmagic.cast_from_hat(game, c, f"hat:{hat.uid}:{road[0]}", c)[0]


# ---------------------------------------------------------------------------- the rest
def test_enspelled_arms_bind_a_spell_of_their_schools(game, tables):
    for slug, schools in (("enspelled_armor", {"abjuration", "illusion"}),
                          ("enspelled_weapon", {"conjuration", "divination", "evocation", "necromancy",
                                                "transmutation"})):
        for seed in range(1, 6):
            it = make(game, slug, seed)
            prop = next(p for p in it.magic["props"] if p.get("kind") == "charges")
            assert tables.spells[prop["spell"]]["school"] in schools
            assert tables.spells[prop["spell"]]["level"] in (2, 3) and prop["dc"] in (13, 15)
            assert it.magic["title"].startswith(("Enspelled Armor of", "Enspelled Weapon of"))


def test_enspelled_armor_casts_only_while_worn(game, tables):
    c = person(tables, "fighter")
    armor = give(c, make(game, "enspelled_armor", 2), slot="")
    assert not magic.charges(c)
    c.equipped["armor"] = armor.uid
    assert magic.charges(c)


def test_the_ruby_of_the_war_mage_makes_a_weapon_a_focus(game, tables):
    c = person(tables, "cleric", bg="acolyte")
    game.party[0] = c
    c.inventory = [it for it in c.inventory if not tables.items.get(it.def_id).get("focus")
                   and it.def_id != "component_pouch"]
    c.equipped = {k: v for k, v in c.equipped.items() if c.item(v) is not None}
    assert not spellrules.has_focus(c, tables)
    ruby = give(c, make(game, "ruby_of_the_war_mage"))
    weapon = next(it for it in c.inventory if tables.items.category(it) == "weapon")
    c.equipped["main_hand"] = weapon.uid
    rows = wonders.choices(game, c, ruby)
    assert rows and rows[0][1] == weapon.uid
    wonders.choose(game, c, ruby, weapon.uid)
    assert ruby.magic["on"] == weapon.uid and spellrules.has_focus(c, tables)
    assert spellrules.focus_bonus(c, tables) == 1
    wonders.use(game, c, ruby)
    assert "on" not in ruby.magic and not spellrules.has_focus(c, tables)


def test_a_crystal_ball_scries_at_dc_17(game, tables):
    from realmwalker.game import magic as roadmagic

    c = game.leader
    ball = give(c, make(game, "crystal_ball", variant="of mind reading"), slot="")
    assert ball.magic["title"] == "Crystal Ball of Mind Reading"
    held = next((it, p) for it, p in roadmagic.item_spells(game, c) if p["spell"] == "scrying")
    subjects = roadmagic.road_targets(game, c, "scrying")
    if not subjects:
        pytest.skip("no one to scry in this world")
    text = " ".join(roadmagic.cast_on_road(game, c, "scrying", subjects[0], charge=held))
    assert "crystal ball" in text and "vs DC 17" in text


def test_the_enduring_spellbook_is_a_spellbook(game, tables):
    book = make(game, "enduring_spellbook")
    assert book.def_id == "spellbook" and magic.item_flag(book, "enduring")
