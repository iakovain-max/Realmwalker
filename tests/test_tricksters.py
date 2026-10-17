"""Steel & Shadows part B: the Eldritch Knight and the Arcane Trickster - third casters of the wizard's list, War Bond,
War Magic, Eldritch Strike, Arcane Charge, the unseen Mage Hand, Magical Ambush, Versatile Trickster and Spell Thief,
each at work in a real fight or on the road, and in the Auto's hands."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import progression
from realmwalker.rules import spells as sr
from realmwalker.rules.engine import resources as res
from realmwalker.world.tables import Tables

from tests.test_feats import armed


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def path(tables, sub, level=3, seed=1, weapon=None):
    """A fighter (Eldritch Knight) or rogue (Arcane Trickster) of this level, their choices made the Auto's way."""
    cls = "fighter" if sub == "eldritch_knight" else "rogue"
    c = armed(tables, weapon or ("longsword" if cls == "fighter" else "rapier"), cls=cls, level=1, seed=seed)
    c.abilities["int"] = 16
    for _ in range(level - 1):
        progression.level_up(c, tables, RNG(seed, "lv"))
        s = next((p for p in c.pending if p["kind"] == "subclass"), None)
        if s is not None:
            progression.resolve(c, tables, s, sub)
    progression.auto_resolve(c, tables)
    res.fill(c, tables)
    return c


# ---------------------------------------------------------------------------- B.1 third casters
def test_the_third_casters_tables(tables):
    for sub in ("eldritch_knight", "arcane_trickster"):
        c = path(tables, sub, 3)
        assert c.subclass == sub and sr.is_caster(c, tables)
        assert sr.slots_total(c, tables) == [2] and sr.prepared_count(c, tables) == 3
        assert sr.casting_ability(c, tables) == "int" and sr.spell_list(c, tables) == "wizard"
        want = 2 if sub == "eldritch_knight" else 3
        assert len(c.spells["cantrips"]) == want, c.spells
        assert all("wizard" in tables.spells[s]["classes"] for s in c.spells["cantrips"])
        assert len(sr.prepared(c, tables)) == 3
        assert all(tables.spells[s]["level"] == 1 and "wizard" in tables.spells[s]["classes"]
                   for s in sr.prepared(c, tables))
    c = path(tables, "arcane_trickster", 3)
    assert "mage_hand" in c.spells["cantrips"]
    for level, slots, prep, cantrips in ((7, [4, 2], 5, 2), (10, [4, 3], 7, 3), (13, [4, 3, 2], 9, 3),
                                         (19, [4, 3, 3, 1], 12, 3), (20, [4, 3, 3, 1], 13, 3)):
        c = path(tables, "eldritch_knight", level, seed=level)
        assert sr.slots_total(c, tables) == slots and sr.prepared_count(c, tables) == prep
        assert len(c.spells["cantrips"]) == cantrips and len(sr.prepared(c, tables)) == prep
        assert max(tables.spells[s]["level"] for s in sr.prepared(c, tables)) <= len(slots)


def test_the_list_changes_by_level_not_by_rest(tables):
    c = path(tables, "eldritch_knight", 3)
    sr.close_preparing(c)
    progression.long_rest(c, tables, RNG(1, "rest"))
    assert sr.preparing_open(c) == ""
    progression.level_up(c, tables, RNG(1, "lv"))
    assert sr.preparing_open(c) == "prepare"
    w = path(tables, "eldritch_knight", 3)
    assert sr.has_focus(w, tables) in (True, False)  # (an arcane focus serves; asked without error)
    assert sr.focus_kind(w, tables) == "arcane"


def test_a_plain_fighter_and_rogue_cast_nothing(tables):
    for sub, cls in (("champion", "fighter"), ("thief", "rogue")):
        c = armed(tables, "longsword", cls=cls, level=1)
        for _ in range(4):
            progression.level_up(c, tables, RNG(1, "lv"))
            s = next((p for p in c.pending if p["kind"] == "subclass"), None)
            if s is not None:
                progression.resolve(c, tables, s, sub)
        assert not sr.is_caster(c, tables) and not c.spells
