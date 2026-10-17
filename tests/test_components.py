"""Spell components (Expansion 3 C.2, PHB 2024 p. 237): a focus or a component pouch stands in for a Material
component without a cost; one with a cost needs that very thing (sold at temples and town markets); one the spell
consumes is used up as it is cast, and kept when a Counterspell stops the spell."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import describe
from realmwalker.rules import spells as sp
from realmwalker.rules.combat import FOE, PARTY, Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.inventory import add_item, remove_item
from realmwalker.rules.progression import award_xp
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def hero(tables, cls, xp=0, seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("sage")
    c = b.build()
    award_xp(c, xp, tables, RNG(2), auto=True)
    return c


def drop_all(c, tables, ids):
    for it in [i for i in c.inventory if i.def_id in ids]:
        remove_item(c, it.uid, it.qty)


def test_a_focus_or_a_pouch_stands_in_for_free_materials(tables):
    c = hero(tables, "cleric", 900)
    c.spells["prepared"] = ["hold_person", "guiding_bolt", "cure_wounds", "bless"]
    assert sp.can_cast(c, tables, "hold_person")[0]  # (a straight piece of iron: the holy symbol stands in)
    drop_all(c, tables, ("holy_symbol", "holy_emblem", "reliquary", "component_pouch"))
    assert sp.can_cast(c, tables, "hold_person") == (False, "needs a focus or a component pouch for its materials")
    assert sp.can_cast(c, tables, "bless") == (False, "needs a holy symbol worth 5+ GP")
    assert sp.can_cast(c, tables, "guiding_bolt")[0]  # (no material component)
    add_item(c, tables.items, "component_pouch")
    assert sp.can_cast(c, tables, "hold_person")[0] and not sp.can_cast(c, tables, "bless")[0]  # (a cost: the thing)
    w = hero(tables, "wizard")
    drop_all(w, tables, ("component_pouch", "arcane_focus"))
    w.spells["prepared"] = ["sleep", "magic_missile", "shield", "burning_hands"]
    assert sp.can_cast(w, tables, "sleep")[0], "a wizard's spellbook is a focus"


def test_revivify_spends_its_diamond_in_a_real_fight(tables):
    c = hero(tables, "cleric", 6500)
    friend = hero(tables, "fighter", seed=2)
    friend.is_player = False
    c.spells["prepared"] = ["revivify", "guiding_bolt", "cure_wounds", "bless"]
    shared = c.inventory
    b = Battle(tables, [c, friend], [spawn(tables, "wolf", RNG(1), 1)], Env(), RNG(1, "battle"))
    b.start("Test fight.")
    me = next(x for x in b.side(PARTY) if x.char is c)
    pal = next(x for x in b.side(PARTY) if x.char is friend)
    pal.state, pal.hp, pal.died_round = "dead", 0, b.round
    while b.pending_party() is not me and b.outcome is None:
        if b.pending_party() is not None:
            b.end_turn()
        else:
            b.step()
    menu = {sid: why for sid, ok, why in b.spell_options(me)}
    assert menu["revivify"] == "needs a diamond worth 300+ GP"
    assert any("diamond worth 300+" in line for line in describe.spell(tables, "revivify", f=me).lines)
    add_item(c, tables.items, "diamond")
    assert b.do_cast(me, "revivify", pal)
    assert pal.state != "dead" and not any(i.def_id == "diamond" for i in shared)


def test_costly_components_are_sold(tables):
    import json
    from pathlib import Path

    econ = json.loads((Path(__file__).resolve().parents[1] / "data" / "economy.json").read_text(encoding="utf-8"))
    stock = {line[0] for shop in econ["shops"].values() for line in shop.get("stock", ())}
    for sid, spell in tables.spells.defs.items():
        for item in (spell.get("material") or {}).get("items", ()):
            assert item in tables.items.defs, (sid, item)
        if spell.get("material"):
            assert set(spell["material"]["items"]) & stock, f"{sid}: its component is sold nowhere"
