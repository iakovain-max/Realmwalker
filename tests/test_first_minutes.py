"""The first minutes (after v1): what a new player reads while making a character and looking at it should read
like English and match the choices on screen."""

import pytest

from realmwalker.core import textgen
from realmwalker.core.rng import RNG
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.mark.parametrize("before, after", [
    ("born in a autumn that people remember", "Born in an autumn that people remember"),
    ("A orc and a ewe.", "An orc and a ewe."),
    ("a one-eyed man with a useful knife", "A one-eyed man with a useful knife"),
    ("wait a hour, then ride a horse", "Wait an hour, then ride a horse"),
    ("an apple, a pear", "An apple, a pear"),
    ("plan a is sound", "Plan a is sound"),
])
def test_built_in_text_says_an_before_a_vowel(before, after):
    assert textgen.tidy(before) == after


def test_backstory_seasons_read_right(tables):
    rng = RNG(3, "seasons")
    lines = {textgen.fill("{name} was born in a {season}.", rng, {"season": ["autumn", "winter"]}, {"name": "Ada"})
             for _ in range(40)}
    assert lines == {"Ada was born in an autumn.", "Ada was born in a winter."}


def test_weapon_training_is_written_in_words(tables):
    b = CharacterBuilder(tables, RNG(1, "hero"))
    b.set_class("rogue")
    c = b.build()
    words = tables.items.proficiency_words(c.weapon_prof)
    assert "hand crossbow" in words and "_" not in words
    assert tables.items.proficiency_words(["simple", "martial"]) == "simple, martial"


def test_the_fighting_style_suits_the_kit_until_you_choose_one(tables):
    b = CharacterBuilder(tables, RNG(1, "hero"))
    b.set_class("fighter")
    kits = [k.get("style") for k in tables.classes["fighter"]["kits"]]
    assert b.fighting_style == kits[0] == "defense"  # mail and a shield: Defence, not Archery
    b.set_kit(1)
    assert b.fighting_style == kits[1] == "archery"  # the longbow
    b.set_kit(2)
    assert b.fighting_style == "great_weapon"  # the greataxe
    b.fighting_style, b.style_chosen = "dueling", True
    b.set_kit(0)
    assert b.fighting_style == "dueling"  # a choice made by hand is kept
    b.set_class("wizard")
    assert b.fighting_style is None


def test_food_in_the_pack_says_how_long_it_keeps(make_app):
    from realmwalker.game.state import new_game
    from realmwalker.rules.inventory import add_item
    from realmwalker.ui.screens.sheets import spoilage_text
    from realmwalker.world.generator import WorldGenerator, WorldOptions

    app = make_app()
    t = app.tables
    world = WorldGenerator(WorldOptions("Pantry", 2, "small"), t).generate()
    b = CharacterBuilder(t, RNG(1, "hero"))
    game = new_game(world, t, b.build())
    food = add_item(game.leader, t.items, "rations", 1)
    assert "keeps" in spoilage_text(game, food, in_list=True)
    assert "keeps" not in spoilage_text(game, food)  # the details say "Keeps: 60 days" already
    days = t.items.get("rations")["food"]["spoil_days"]
    assert len(spoilage_text(game, food, in_list=True).replace("<dim>", "").replace("</>", "")) <= 13
    assert days


def test_creation_speaks_of_an_acolyte(make_app):
    import tcod.console

    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.creation import CreationScreen
    from realmwalker.world.generator import WorldGenerator, WorldOptions

    app = make_app()
    world = WorldGenerator(WorldOptions("Chapel", 4, "small"), app.tables).generate()
    screen = CreationScreen(app, world)
    app.push(screen)
    screen.b.set_background("acolyte")
    seen = []
    for step in range(8):
        screen.step = step
        con = tcod.console.Console(160, 45, order="F")
        app.render(con)
        seen.append("\n".join("".join(chr(c) for c in con.rgb["ch"][:, y]) for y in range(con.height)))
    text = "\n".join(seen)
    assert "suit an acolyte" in text and "formerly an acolyte" in text
    import re

    assert not re.search(r"\ba acolyte", text), re.findall(r".{60}\ba acolyte.{20}", text)
    assert not re.search(r"[a-z]_[a-z]", text)  # no raw ids (the name field's cursor is a lone "_")
    app.handle_event(KeyEvent("escape"))
    assert app.error_count == 0
