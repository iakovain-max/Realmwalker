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
    from realmwalker.ui.screens.creation import STEPS

    for step in range(len(STEPS)):
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


@pytest.mark.parametrize("cause, reads", [
    ("froze to death", "froze to death"),
    ("died of thirst", "died of thirst"),
    ("killed by the wolf", "was killed by the wolf"),
    ("hanged by the Crown of Rookmark", "was hanged by the Crown of Rookmark"),
    ("of misfortune", "died of misfortune"),
    ("", "died"),
])
def test_a_death_reads_after_a_name(cause, reads):
    from realmwalker.game import death

    assert death.how_they_died(cause) == reads


def test_ties_never_say_the_the_or_master_master(tables):
    from realmwalker.rules.creation import make_ties, starting_places
    from realmwalker.world.generator import WorldGenerator, WorldOptions

    seen = []
    for seed in range(6):
        world = WorldGenerator(WorldOptions("Kin", 40 + seed, "small"), tables).generate()
        for bg in ("outlander", "sage"):
            b = CharacterBuilder(tables, RNG(seed, "hero"))
            b.set_race("dwarf")
            b.set_background(bg)
            c = b.build()
            places = starting_places(world, tables, bg, c.race, RNG(seed))
            for tie in make_ties(world, tables, c, places[0], RNG(seed)):
                seen.append(tie["text"])
    text = " ".join(seen)
    assert "the the" not in text.lower() and "master master" not in text.lower()
    assert "born to the" in text


def test_travel_days_read_like_speech(make_app):
    from realmwalker.game.state import TravelPlan, new_game
    from realmwalker.world.generator import WorldGenerator, WorldOptions

    app = make_app()
    world = WorldGenerator(WorldOptions("Miles", 8, "small"), app.tables).generate()
    game = new_game(world, app.tables, CharacterBuilder(app.tables, RNG(1, "hero")).build())
    for minutes, words in ((13 * 60, "about a day and a half"), (9 * 60, "about a day at"), (40 * 60, "about 5 days")):
        plan = TravelPlan(path=[(0, 0)], minutes=minutes, miles=20, destination=(0, 0))
        assert words in game.describe_plan(plan), game.describe_plan(plan)
    assert "1 days" not in game.describe_plan(TravelPlan(path=[(0, 0)], minutes=10 * 60 + 50, miles=18,
                                                          destination=(0, 0)))


SLIPS = {
    "a raw id": r"(?<![\w/.])[a-z]+_[a-z0-9_]+(?![\w/.])",
    "the the": r"\b[Tt]he the\b",
    "died died": r"\bdied died\b",
    "1 and a plural": r"(?<![\d.,])1 (days|hours|pints|miles|weeks)\b",
    "(s)": r"[a-z]\(s\)",
    ".:": r"\w\.: ",
}


def test_nothing_on_screen_reads_wrong_during_a_run(tmp_path, monkeypatch):
    """The bot plays for a while; nothing drawn may carry an internal id or one of the slips fixed above."""
    import re
    import sys
    from pathlib import Path

    from realmwalker.ui import widgets

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from autoplay import run_autoplay

    found: dict[str, set] = {}
    spans = widgets.Canvas.spans
    patterns = {name: re.compile(p) for name, p in SLIPS.items()}

    def watch(canvas, x, y, parts, bg=None, max_width=None):
        s = "".join(t for t, _ in parts)
        for name, pat in patterns.items():
            if pat.search(s):
                found.setdefault(name, set()).add(s.strip()[:100])
        return spans(canvas, x, y, parts, bg, max_width)

    monkeypatch.setattr(widgets.Canvas, "spans", watch)
    report = run_autoplay(turns=800, seed=6, ai="off", home=tmp_path / "home")
    assert report.ok, report.summary()
    assert not found, found


def test_asking_whether_a_creature_exists_is_safe(tables):
    """The bot's law check asks this of a captive's kind; it used to fail with KeyError: 0 now and then."""
    assert "wolf" in tables.creatures
    assert "no_such_beast" not in tables.creatures
    assert None not in tables.creatures
