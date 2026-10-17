"""Level-up choices and spell scrolls (M7 part 1)."""

import copy

import pytest

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.game import magic
from realmwalker.game.state import new_game
from realmwalker.rules import progression
from realmwalker.rules.character import modifier
from realmwalker.rules.combat import PARTY, Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.inventory import add_item
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def hero(tables, cls="fighter", seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("sage" if cls == "wizard" else "soldier")
    return b.build()


def to_level(char, tables, level):
    xp = tables.rules["xp_for_level"][level - 1] - char.xp
    return progression.award_xp(char, xp, tables, RNG(1, "xp"))


def test_the_fighter_chooses_a_path_at_third_level(tables):
    c = hero(tables)
    to_level(c, tables, 3)
    assert c.level == 3 and c.subclass is None
    kinds = [p["kind"] for p in c.pending]
    assert "subclass" in kinds and progression.has_new_choices(c)
    choice = next(p for p in c.pending if p["kind"] == "subclass")
    opts = progression.options(c, tables, choice)
    assert {o[0] for o in opts} == set(tables.classes["fighter"]["subclasses"])
    progression.resolve(c, tables, choice, opts[-1][0])
    assert c.subclass == opts[-1][0]
    sub = tables.classes["fighter"]["subclasses"][c.subclass]
    assert all(f["id"] in c.features for f in sub["features"] if f["level"] <= 3)


def test_ability_increases(tables):
    c = hero(tables)
    to_level(c, tables, 4)
    choice = next(p for p in c.pending if p["kind"] == "asi")
    opts = {o[0] for o in progression.options(c, tables, choice)}
    assert "str+2" in opts or c.abilities["str"] > 18
    assert any("," in o for o in opts)
    con, hp = c.abilities["con"], c.max_hp
    pick = "con+2" if "con+2" in opts else next(o for o in opts if o.startswith("con+1"))
    progression.resolve(c, tables, choice, pick)
    gained = modifier(c.abilities["con"]) - modifier(con)
    assert c.max_hp == hp + gained * c.level


def test_wizards_choose_their_spells(tables):
    c = hero(tables, "wizard")
    book = list(c.spells.get("spellbook", []))
    to_level(c, tables, 3)
    choice = next(p for p in c.pending if p["kind"] == "spells")
    assert choice["count"] == 2
    opts = progression.options(c, tables, choice)
    assert opts and all(o[0] not in book for o in opts)
    assert max(tables.spells[o[0]]["level"] for o in opts) == 2
    progression.resolve(c, tables, choice, opts[0][0])
    assert opts[0][0] in c.spells["spellbook"] and choice["count"] == 1


def test_choices_can_be_made_for_you(tables):
    c = hero(tables, "wizard")
    to_level(c, tables, 8)
    assert c.pending
    progression.auto_resolve(c, tables)
    assert not c.pending and c.subclass
    top = progression.spell_top_level(c, tables)
    available = [s for s in tables.spells.for_class("wizard", top) if tables.spells[s]["level"] > 0]
    assert len(c.spells["spellbook"]) == min(len(available), 6 + 14)
    d = hero(tables, "rogue")
    progression.award_xp(d, 40000, tables, RNG(2), auto=True)
    assert not d.pending and d.subclass


# ---------------------------------------------------------------------------- scrolls
@pytest.fixture
def game(tables):
    world = cached_world(WorldOptions("Scrolland", 3, "small"), tables)
    g = new_game(world, tables, hero(tables, "wizard"))
    g.survival = False
    return g


def fixed_d20(monkeypatch, value):
    class Roll:
        natural = value
        total = value

    monkeypatch.setattr(dice, "d20", lambda *a, **k: Roll())


def test_there_is_a_scroll_for_every_spell(tables):
    for sid, spell in tables.spells.defs.items():
        if "item" not in spell["classes"] and "again" not in spell["classes"]:  # (no scroll of a follow-up)
            d = tables.items.get(f"scroll_{sid}")
            assert d["use"]["scroll"] == sid and d["value"] > 0


def test_a_wizard_copies_a_scroll(game, monkeypatch):
    c = game.leader
    sid = "magic_missile"
    if sid in c.spells.get("spellbook", []):
        c.spells["spellbook"].remove(sid)
    it = add_item(c, game.tables.items, f"scroll_{sid}", 1)
    c.money = 100000
    t0 = game.world.time
    fixed_d20(monkeypatch, 20)
    lines = magic.copy_scroll(game, c, it)
    assert sid in c.spells["spellbook"] and "copies" in lines[0]
    assert c.item(it.uid) is None and c.money == 100000 - magic.COPY_COST_PER_LEVEL
    assert game.world.time - t0 >= 2 * 60
    assert magic.copy_problem(game, c, add_item(c, game.tables.items, f"scroll_{sid}", 1))


def test_copying_can_fail_and_fighters_cannot_copy(game, monkeypatch):
    c = game.leader
    sid = "magic_missile"
    if sid in c.spells.get("spellbook", []):
        c.spells["spellbook"].remove(sid)
    it = add_item(c, game.tables.items, f"scroll_{sid}", 1)
    c.money = 100000
    fixed_d20(monkeypatch, 1)
    magic.copy_scroll(game, c, it)
    assert sid not in c.spells.get("spellbook", []) and c.item(it.uid) is None
    c.cls = "fighter"
    assert "wizard" in magic.copy_problem(game, c, add_item(c, game.tables.items, f"scroll_{sid}", 1))


def test_reading_a_scroll_in_battle(tables):
    c = hero(tables, "wizard")  # (2024: the spell must be on the reader's list; tests/test_scrolls.py has the rest)
    it = add_item(c, tables.items, "scroll_magic_missile", 1)
    rng = RNG(1, "foes")
    b = Battle(tables, [c], [spawn(tables, "wolf", rng, 1)], Env(), RNG(1, "battle"))
    b.start("Test.")
    for _ in range(50):
        if b.pending_party() is not None or b.outcome is not None:
            break
        b.step()
    f = b.pending_party()
    if f is None:
        pytest.skip("the fight ended before the fighter could act")
    options = [o for o in b.spell_options(f) if o[0].startswith("scroll:")]
    assert options
    b.do_cast(f, options[0][0], b.enemies_of(f)[0])
    assert c.item(it.uid) is None


def test_scrolls_are_sold_where_mages_are(game):
    from realmwalker.game import economy
    from realmwalker.game.people import npcs_in, prepare_town

    city = next((s for s in game.world.settlements if s.kind == "city"), None)
    if city is None:
        pytest.skip("no city")
    prepare_town(game, city)
    sellers = [n for n in npcs_in(game.world, city.id) if economy.shop_kind(game, n) in ("general", "apothecary")]
    stock = {}
    for n in sellers:
        stock.update(economy.shop_state(game, n)["stock"])
    assert any(k.startswith("scroll_") for k in stock)
