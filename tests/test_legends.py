"""The Legends book (2026-10): every person, realm, place, war, beast, artifact, age, god and song has a page; every
link on a page leads to another page; the screen shows them, follows links, goes back, searches, and fits."""

import pytest
import tcod.console

from realmwalker.ui import widgets
from realmwalker.ui.input import KeyEvent
from realmwalker.world import legends
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Lorebook", 21, "medium"), tables).generate()


def test_every_kind_of_thing_has_pages(world, tables):
    for category, _ in legends.CATEGORIES:
        items = legends.entries(world, tables, category)
        assert items, category
        for ref, label in items[:40]:
            title, lines = legends.page(world, tables, ref)
            assert title and title != "Nothing", (category, ref, label)
            assert lines and all(isinstance(line, str) for line in lines)


def test_every_link_leads_somewhere(world, tables):
    seen = 0
    for category, _ in legends.CATEGORIES:
        for ref, _ in legends.entries(world, tables, category)[:25]:
            _, lines = legends.page(world, tables, ref)
            for line in lines:
                for _text, target in legends.segments(line):
                    if target is None:
                        continue
                    title, _ = legends.page(world, tables, target)
                    assert title != "Nothing", (ref, target)
                    seen += 1
    assert seen > 100


def test_a_ruler_s_page_tells_their_family_and_life(world, tables):
    from realmwalker.world import factions as fx

    king = fx.leader_of(world, fx.active_factions(world, "kingdom")[0])
    title, lines = legends.page(world, tables, f"H{king.id}")
    text = "\n".join(legends.plain(line) for line in lines)
    assert king.first_name in title
    assert "born in" in text and "Life" in text
    assert any("[[F" in line for line in lines)


def test_search_finds_by_any_part_of_a_name(world, tables):
    people = legends.entries(world, tables, "people")
    name = people[0][1].split()[1]
    found = legends.entries(world, tables, "people", name.lower())
    assert found and all(name.lower() in label.lower() for _, label in found)
    assert legends.entries(world, tables, "places", "zzzzqqq") == []


def test_unknown_pages_say_so(world, tables):
    assert legends.page(world, tables, "H999999")[0] == "Nothing"
    assert legends.page(world, tables, "Q1")[0] == "Nothing"
    assert legends.page(world, tables, "Sx")[0] == "Nothing"


def render(screen, size):
    con = tcod.console.Console(*size, order="F")
    canvas = widgets.Canvas(con)
    screen.render(canvas)
    return canvas, "\n".join("".join(chr(c) for c in con.rgb["ch"][:, y]) for y in range(con.height))


def test_the_screen_reads_follows_and_goes_back(make_app, world):
    from realmwalker.ui.screens.legends import LegendsScreen

    app = make_app()
    screen = LegendsScreen(app, world)
    app.push(screen)
    for size in [(80, 30), (120, 45), (192, 54)]:
        _, text = render(screen, size)
        assert "Legends of Lorebook" in text
    first = screen.ref
    screen.handle_key(KeyEvent("down"))
    assert screen.ref != first and screen.back == [first]
    screen.handle_key(KeyEvent("backspace"))
    assert screen.ref == first
    screen.handle_key(KeyEvent("]"))
    assert screen.ref != first
    for _ in range(len(legends.CATEGORIES)):
        screen.handle_key(KeyEvent("right"))
        render(screen, (120, 45))
    screen.handle_key(KeyEvent("/"))
    assert screen.captures_text
    for ch in "the":
        screen.handle_key(KeyEvent(ch))
    screen.handle_key(KeyEvent("enter"))
    assert not screen.captures_text and screen.query == "the"
    # A click on a link in the page opens that page.
    canvas, _ = render(screen, (160, 45))
    links = [r for r in canvas.regions if r.action is not None and r.x > 50]
    before = screen.ref
    if links:
        links[0].action()
        assert screen.ref != before or screen.back
    screen.handle_key(KeyEvent("escape"))
    assert app.top is not screen


def test_saved_worlds_open_the_legends_book(make_app, tmp_path, world):
    from realmwalker.game import save
    from realmwalker.ui.screens.game_menu import WorldsScreen
    from realmwalker.ui.screens.legends import LegendsScreen

    app = make_app()
    save.save_world(world, save.world_folder(app.paths.saves, world))
    screen = WorldsScreen(app)
    app.push(screen)
    assert screen.saves
    screen.handle_key(KeyEvent("l"))
    assert isinstance(app.top, LegendsScreen) and app.top.world.meta.name == "Lorebook"
