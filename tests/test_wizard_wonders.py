"""Schools & Domains Part E: the wizard's wondrous things of the DMG 2024 - crystal balls, the Enduring Spellbook,
Enspelled Armor and Weapon, the Hat of Many Spells and the Hat of Wizardry, the Pearl of Power, the Ring of Spell
Storing, the five robes and the Ruby of the War Mage: made from the book, used in fights and on the road."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import treasure, wonders
from realmwalker.rules import magic
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import PARTY
from tests.test_gear import companion, fight_with, game, person, tables, world  # noqa: F401 (fixtures)
from tests.test_gear_2024 import my_turn

BOOK = {  # slug: (variant, rarity, attunement, title, base)
    "crystal_ball": ("", "very_rare", True, "Crystal Ball", "arcane_orb"),
    "enduring_spellbook": ("", "common", False, "Enduring Spellbook", "spellbook"),
    "enspelled_armor": ("level 2 or 3 spell", "rare", True, None, None),
    "enspelled_weapon": ("level 2 or 3 spell", "rare", True, None, None),
    "hat_of_many_spells": ("", "very_rare", True, "Hat of Many Spells", "pointed_hat"),
    "hat_of_wizardry": ("", "common", True, "Hat of Wizardry", "pointed_hat"),
    "pearl_of_power": ("", "uncommon", True, "Pearl of Power", "pearl"),
    "ring_of_spell_storing": ("", "rare", True, "Ring of Spell Storing", "plain_ring"),
    "robe_of_eyes": ("", "rare", True, "Robe of Eyes", "robe"),
    "robe_of_scintillating_colors": ("", "very_rare", True, "Robe of Scintillating Colors", "robe"),
    "robe_of_stars": ("", "very_rare", True, "Robe of Stars", "robe"),
    "robe_of_the_archmagi": ("", "legendary", True, "Robe of the Archmagi", "robe"),
    "robe_of_useful_items": ("", "uncommon", False, "Robe of Useful Items", "robe"),
    "ruby_of_the_war_mage": ("", "common", True, "Ruby of the War Mage", "gemstone"),
}
SLOT = {"pointed_hat": "head", "robe": "main", "plain_ring": "ring", "arcane_orb": "main_hand"}


def make(game, slug, seed=1, variant=None):
    v, rarity = BOOK[slug][0], BOOK[slug][1]
    it = treasure.make_listed(game, slug, v if variant is None else variant, rarity, RNG(seed, slug))
    assert it is not None, slug
    it.magic["identified"] = True
    return it


def give(c, it, slot=None):
    it.uid = c.new_uid()
    c.inventory.append(it)
    slot = slot if slot is not None else SLOT.get(it.def_id)
    if slot:
        c.equipped[slot] = it.uid
    if it.magic.get("attune"):
        c.attuned.append(it.uid)
    return it


def battle(game, tables, slug, cls="wizard", foes=("bandit",), seed=1, near=True, slot=None):
    c = person(tables, cls, bg="sage")
    it = give(c, make(game, slug, seed), slot)
    b = fight_with(tables, c, *foes)
    me = b.side(PARTY)[0]
    them = [f for f in b.fighters if f.side != PARTY]
    for i, t in enumerate(them):
        t.x, t.y = me.x + (1 if near else 6), me.y + i
        t.hp = t.creature.hp = t.creature.max_hp = 200
    my_turn(b, me)
    return c, it, b, me, them


@pytest.mark.parametrize("slug", sorted(BOOK))
def test_every_part_e_item_is_made_from_the_book(game, slug):
    _v, _rarity, attune, title, base = BOOK[slug]
    it = make(game, slug)
    assert it.magic["source"] == "book" and bool(it.magic["attune"]) is attune
    if title:
        assert it.magic["title"] == title
    if base:
        assert it.def_id == base
    assert all(p.get("text") or p.get("kind") in ("pool",) for p in it.magic["props"] if p.get("kind") != "trait"
               or p.get("text"))


def test_the_tables_reach_every_part_e_item(game):
    rows = {r[2] for t in treasure.spec(game)["tables"].values() for r in t}
    assert set(BOOK) <= rows
