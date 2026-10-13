"""The expansion shelf on the title screen and the Expansions screen (docs/EXPANSIONS.md §4.13)."""

from pathlib import Path

import pytest
import tcod.console

from realmwalker.data.packs import Pack
from realmwalker.ui.input import KeyEvent, MouseEvent
from realmwalker.ui.screens.expansions import ExpansionsScreen
from realmwalker.ui.screens.title import TitleScreen

SIZES = [(80, 30), (120, 45), (240, 67)]


def released(pid, order, adds=3):
    return Pack(Path("."), {"id": pid, "order": order, "name": f"Test {pid.title()}", "tagline": "A line to test with.",
                            "icon": f"dlc/{pid}", "accent": [150, 64, 170], "status": "released", "version": f"1.{order}.0",
                            "released_on": "2026-11-02", "adds": [f"Thing number {i} that it adds" for i in range(adds)]})


def render(app, size):
    con = tcod.console.Console(*size, order="F")
    app.render(con)
    app.update()
    return app.last_canvas


@pytest.fixture
def shelved(make_app):
    app = make_app()
    app.data.packs = [p for p in app.data.packs if p.record["status"] != "released"]
    app.data.packs += [released(f"x{i}", 80 + i) for i in range(5)]
    return app


def test_no_released_expansion_means_no_shelf(make_app):
    app = make_app()
    app.data.packs = [p for p in app.data.packs if p.record["status"] != "released"]
    render(app, (120, 45))
    assert isinstance(app.top, TitleScreen) and app.top.shelf == []
    app.handle_event(KeyEvent("e"))
    assert isinstance(app.top, ExpansionsScreen)
    assert "No expansions have come out yet" in render(app, (120, 45)).words()
    app.handle_event(KeyEvent("escape"))
    assert isinstance(app.top, TitleScreen) and app.error_count == 0


@pytest.mark.parametrize("size", SIZES)
def test_every_released_expansion_has_an_icon_with_a_card_that_fits(shelved, size):
    app = shelved
    canvas = render(app, size)
    shelf = app.top.shelf
    assert [pid for pid, _ in shelf] == [f"x{i}" for i in range(5)]
    for pid, (x, y, w, h) in shelf:
        assert 0 <= x and x + w <= size[0] and 0 <= y and y + h <= size[1], f"{pid} is off the window"
        assert any(r.x == x and r.y == y and r.action is not None for r in canvas.regions), "an icon can be clicked"
    pid, (x, y, w, h) = shelf[0]
    app.handle_event(MouseEvent("move", x, y))
    canvas = render(app, size)
    assert "Test X0" in canvas.words() and "Thing number 2 that it adds" in canvas.words()
    assert "Version 1.80 · 2 November 2026" in canvas.words()
    from realmwalker import expansions
    from realmwalker.ui import shelf as shelf_mod

    e = next(e for e in expansions.released(app.data) if e.id == "x0")
    cx, cy, cw, ch = shelf_mod.draw_card(canvas, e, shelf_mod.layout(canvas, 5)[0])
    assert cx >= 0 and cy >= 0 and cx + cw <= size[0] * canvas.cell_w and cy + ch <= size[1] * canvas.cell_h
    assert "x0" in app.settings.expansions_seen, "pointed at once: it no longer glints"
    assert app.error_count == 0


def test_a_click_opens_the_expansions_screen_at_that_one(shelved):
    app = shelved
    render(app, (160, 50))
    pid, (x, y, w, h) = app.top.shelf[3]
    app.handle_event(MouseEvent("click", x, y))
    screen = app.top
    assert isinstance(screen, ExpansionsScreen)
    words = render(app, (160, 50)).words()
    assert "Test X3" in words and "Adds:" in words
    screen.handle_key(KeyEvent("home"))
    assert "Test X0" in render(app, (160, 50)).words()
    assert set(app.settings.expansions_seen) >= {f"x{i}" for i in range(5)}
    app.handle_event(KeyEvent("escape"))
    assert isinstance(app.top, TitleScreen) and app.error_count == 0


def test_the_seen_expansions_are_kept_in_the_settings(shelved, tmp_path):
    from realmwalker.config import Settings

    app = shelved
    app.settings.expansions_seen = ["x1", "x0", 5]
    app.settings.normalise()
    assert app.settings.expansions_seen == ["x0", "x1"]
    path = tmp_path / "settings.json"
    app.settings.save(path)
    assert Settings.load(path).expansions_seen == ["x0", "x1"]


def test_every_real_expansion_has_its_icon_in_the_atlas(make_app):
    from realmwalker import expansions
    from realmwalker.ui.gfx import headless

    app = make_app()
    atlas = headless().atlas
    for e in expansions.all_expansions(app.data):
        if e.released:
            assert atlas.has(e.icon), f"{e.name} has no icon: draw it in tools/tile_art.py dlc_icons and rebuild"
    assert atlas.has("dlc/dice_destiny")
