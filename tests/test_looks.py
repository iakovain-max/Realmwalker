"""How people look (after 1.0): chosen at character creation (build, skin, eyes, hair, beard, the marks of each
people, scars, paint, colours), read from the words that describe townsfolk, written back as words, drawn, saved,
and ready for peoples not yet added."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.data.registry import DataRegistry
from realmwalker.paths import Paths
from realmwalker.rules import looks
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.ui.gfx import dolls
from realmwalker.ui.gfx.atlas import Atlas
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402

RACES = ("human", "elf", "dwarf", "halfling", "half_orc")


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def atlas():
    a = Atlas(Paths().tiles)
    assert a.ok, "the tile sheets (assets/tiles) are missing"
    return a


@pytest.fixture(scope="module")
def newcomers(data):
    """Tables with a people that exists only in data/races.json: no looks written, no body drawn, no skins."""
    raw = copy.deepcopy(data._files)
    gnome = copy.deepcopy(raw["races.json"]["races"]["human"])
    gnome["name"] = "Gnome"
    raw["races.json"]["races"]["gnome"] = gnome
    return Tables(DataRegistry(raw))


def test_every_look_of_every_people_can_be_drawn(tables, atlas):
    assert dolls.looks_problems(tables, atlas) == []
    from realmwalker.data.schemas import LOOK_RACE

    errors = []
    LOOK_RACE.check(looks.data(tables)["races"]["_default"], "looks/_default", errors)
    assert not errors, errors


@pytest.mark.parametrize("race", RACES)
def test_random_looks_suit_the_people_and_say_themselves(tables, atlas, race):
    seen = set()
    for i in range(40):
        for sex in ("male", "female"):
            L = looks.random_looks(tables, race, sex, 30, RNG(i, f"{race}{sex}"))
            opts = looks.options(tables, race, sex)
            for slot in looks.SLOTS:
                assert L[slot] in opts[slot], (race, sex, slot, L[slot])
            assert set(L["features"]) == {f for f, pool in opts["features"].items() if pool}
            assert looks.normalise(tables, L, race, sex) == L, "settled looks stay as they are"
            words = looks.describe(tables, L, race, sex)
            assert words[0].isupper() and words.endswith(".") and "{" not in words and "  " not in words
            seen.add((L["build"], L["hair"], L["beard"]))
            parts = dolls.Figure(tables, race, sex, f"t{i}", L).parts(atlas)
            assert any(p[0].startswith("fig/body/") for p in parts) and any(p[0].startswith("fig/eyes/") for p in parts)
    assert len(seen) > 6, "people of one people do not all look alike"


def test_words_say_how_someone_looks(tables):
    L = looks.from_text(tables, "Heavy-set and red-faced, with a braided red beard, a shaven head and grey eyes; "
                                "a scar through one eye and woad paint across the eyes.", "dwarf", "male", 80, "k")
    assert (L["build"], L["skin"], L["beard"], L["beard_colour"], L["hair"], L["eyes"]) == (
        "heavy", "ruddy", "braided", "red", "bald", "grey")
    assert (L["mark"], L["paint"], L["paint_colour"]) == ("scar_eye", "band", "woad")
    orc = looks.from_text(tables, "Hulking, with heavy tusks and coarse black hair in a topknot.", "half_orc", "male")
    assert orc["features"]["tusks"] == "large" and orc["hair"] == "topknot" and orc["hair_colour"] == "black"
    # What the words do not say is the same every time for the same person, and old people go grey.
    assert looks.from_text(tables, "", "human", "female", 30, "npc7") == looks.from_text(tables, "", "human", "female",
                                                                                          30, "npc7")
    old = looks.from_text(tables, "", "human", "male", 90, "npc8")
    assert old["hair_colour"] in ("grey", "white")
    # Women of the peoples whose women are beardless never are, whatever the words.
    assert looks.from_text(tables, "a full black beard", "human", "female")["beard"] == "none"
    # The words written for a look read back as that look.
    rng = RNG(3, "roundtrip")
    for race in RACES:
        for sex in ("male", "female"):
            L = looks.random_looks(tables, race, sex, 30, rng)
            back = looks.from_text(tables, looks.describe(tables, L, race, sex), race, sex, 30, "x")
            said = ["build", "hair", "mark", "paint"] + (["beard"] if L["beard"] != "none" else [])  # no beard: not said
            if L["hair"] != "bald" or L["beard"] != "none":  # a shaven head and a bare chin say no colour
                said.append("hair_colour")
            for slot in said:
                assert back[slot] == L[slot], (race, sex, slot, L, looks.describe(tables, L, race, sex))


def test_a_character_is_made_with_the_looks_chosen(tables, atlas):
    b = CharacterBuilder(tables, RNG(1, "builder"))
    b.set_race("dwarf")
    b.sex = "male"
    b.fit_looks()
    b.set_look("beard", "forked")
    b.set_look("hair_colour", "copper")
    assert b.looks["beard_colour"] == "copper", "a beard follows the hair unless chosen apart"
    b.set_look("beard_colour", "grey")
    b.set_look("hair_colour", "black")
    assert b.looks["beard_colour"] == "grey"
    b.set_look("mark", "eyepatch")
    b.set_look("dye", "crimson")
    b.set_look("cloak", "navy")
    assert "forked grey beard" in b.appearance and "patch over one eye" in b.appearance
    char = b.build()
    assert char.looks == b.looks and char.appearance == b.appearance
    parts = dolls.character(char, tables, atlas=atlas)
    names = {p[0]: p[1] for p in parts}
    assert any(n.startswith("fig/beard/dwarf_male") and n.endswith("/forked") for n in names)
    assert "fig/mark/" + dolls.resolve_body(atlas, "dwarf", "male", char.looks["build"]) + "/eyepatch" in names
    hair = tuple(tables.sprites["figures"]["hair_colours"]["grey"])
    assert any(n.endswith("/forked") and rgba[:3] == hair for n, rgba in names.items())
    crimson = tuple(tables.sprites["figures"]["colours"]["crimson"])
    dyed = [n for n, rgba in names.items() if rgba[:3] == crimson]
    assert dyed, "the clothes are in the colour chosen"
    # A woman of the same people may keep a beard; a human woman may not.
    b.sex = "female"
    b.fit_looks()
    assert b.looks["beard"] in looks.options(tables, "dwarf", "female")["beard"]
    b.set_race("human")
    b.sex = "female"
    b.fit_looks()
    assert b.looks["beard"] == "none" and "beard" not in b.appearance


def test_looks_are_saved_with_the_character(tables, tmp_path):
    from realmwalker.game import save
    from realmwalker.game.state import new_game
    from realmwalker.world.generator import WorldOptions

    world = cached_world(WorldOptions("Mirrorland", 21, "small"), tables)
    b = CharacterBuilder(tables, RNG(2, "save"))
    b.set_race("elf")
    b.set_look("feature:ears", "swept")
    game = new_game(world, tables, b.build())
    save.save_game(game, tmp_path)
    loaded = save.load_game(tmp_path / world.meta.id, tables)
    assert loaded.leader.looks == game.leader.looks and loaded.leader.looks["features"]["ears"] == "swept"


def test_an_older_character_is_drawn_from_their_words(tables, atlas):
    b = CharacterBuilder(tables, RNG(4, "old"))
    char = b.build()
    char.looks = {}
    char.appearance = "Wiry, with long white hair and green eyes; freckles."
    L = dolls.character_looks(char, tables)
    assert (L["build"], L["hair"], L["hair_colour"], L["eyes"], L["mark"]) == ("slight", "long", "white", "green", "freckles")
    assert dolls.character(char, tables, atlas=atlas)


def test_a_people_added_only_to_races_json_can_be_made_and_drawn(newcomers, atlas):
    t = newcomers
    assert "gnome" in t.races
    opts = looks.options(t, "gnome", "male")
    assert opts["hair"] and opts["skin"] and opts["build"], "a new people gets the default looks"
    b = CharacterBuilder(t, RNG(5, "gnome"))
    b.set_race("gnome")
    b.set_look("hair", "crest")
    char = b.build()
    parts = dolls.character(char, t, atlas=atlas, bare_head=True)  # the fighter's helmet would hide the hair
    body = next(p[0] for p in parts if p[0].startswith("fig/body/"))
    assert body.startswith("fig/body/human_"), "drawn on a human body until one is drawn for them"
    assert any(p[0].endswith("/crest") for p in parts)
    assert dolls.skin_colour(t, "gnome", char.looks["skin"])
    assert looks.from_text(t, "a gnome with green eyes", "gnome", "female", 300, "g")["eyes"] == "green"


def test_the_looks_step_changes_the_character(make_app, atlas):
    import tcod.console

    from realmwalker.ui.gfx import GfxContext
    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.creation import LOOKS, CreationScreen
    from realmwalker.world.generator import WorldOptions

    app = make_app()
    world = cached_world(WorldOptions("Lookland", 9, "small"), app.tables)
    screen = CreationScreen(app, world)
    app.push(screen)
    screen.b.set_race("half_orc")
    screen.go(LOOKS)
    rows = screen._look_rows()
    slots = [r[0] for r in rows]
    assert "feature:tusks" in slots and "build" in slots and "dye" in slots
    before = dict(screen.b.looks)
    screen.cursor[LOOKS] = slots.index("hair")
    screen.handle_key(KeyEvent("right"))
    assert screen.b.looks["hair"] != before["hair"]
    screen.handle_key(KeyEvent("r"))
    con = tcod.console.Console(160, 45, order="F")
    app.render(con)
    text = app.last_canvas.words()
    assert "How others see you" in text and "Tusks" in text
    app.gfx = GfxContext(atlas, 10, 20, background=False)  # with pictures: the face and the figure are drawn
    app.render(tcod.console.Console(160, 45, order="F"))
    assert app.error_count == 0
    for _ in range(3):
        screen.handle_key(KeyEvent("enter"))
    screen.begin()
    assert app.game is not None and app.game.leader.looks == screen.b.looks


def test_a_companion_keeps_the_face_they_had_in_town(tables):
    from realmwalker.game import companions
    from realmwalker.game.people import npcs_in, prepare_town
    from realmwalker.game.state import new_game
    from realmwalker.world.generator import WorldOptions

    world = cached_world(WorldOptions("Faceland", 13, "small"), tables)
    game = new_game(world, tables)
    town = world.settlements[0]
    prepare_town(game, town)
    npc = npcs_in(world, town.id)[0]
    char = companions.build(game, npc, "fighter", "soldier", 1, RNG(1, "comp"))
    assert char.looks == looks.of_npc(tables, npc)
