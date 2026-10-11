"""The world map (2026-10-11, Anton: "make the world map more comfortable to look at, zoom in/out and scroll. Right
now, the map is a bit laggy and hard to use", "improve diplomatic and cultural map modes to make it easier to
understand"): painted once and shown at any zoom, names on the land, towns in their people's manner, the wheel zooms
where the pointer is, dragging looks about, a click chooses and a double click travels, and the realm and people
views with their keys."""

import copy

import numpy as np
import pytest
import tcod.console

from realmwalker.paths import Paths
from realmwalker.ui.gfx import GfxContext
from realmwalker.ui.gfx.atlas import Atlas
from realmwalker.ui.gfx.scene import Image, Text
from realmwalker.ui.input import KeyEvent, MouseEvent
from tests.worlds import cached_world  # noqa: E402

SIZE = (160, 50)


@pytest.fixture(scope="module")
def atlas():
    a = Atlas(Paths().tiles)
    assert a.ok
    return a


@pytest.fixture
def world(make_app):
    from realmwalker.world.generator import WorldOptions

    app = make_app()
    return cached_world(WorldOptions("Mapland", 13, "small", history=60), app.tables)


def start(make_app, world, atlas=None):
    from realmwalker.game.state import new_game

    app = make_app()
    if atlas is not None:
        app.gfx = GfxContext(atlas, 10, 20, background=False)
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    game.player.explored[:] = True
    for f in game.world.factions:
        game.renown.known.add(f)
    app.start_game(game)
    return app, game


def render(app, size=SIZE):
    con = tcod.console.Console(*size, order="F")
    app.render(con)
    app.update()
    return app.last_canvas


def commands(canvas, kind=None):
    out = []
    for layer in canvas.layers:
        out += [c for c in layer.under + layer.over if kind is None or isinstance(c, kind)]
    return out


def open_map(app):
    from realmwalker.ui.screens.world_map import WorldMapScreen

    wm = WorldMapScreen(app, app.top)
    app.push(wm)
    return wm


# ---------------------------------------------------------------------------- the painter
def test_the_world_is_painted_once_and_shown_at_any_zoom(make_app, world):
    from realmwalker.ui.gfx.paint import CANON, OVERVIEW, ChunkCache, WorldPainter

    app = make_app()
    painter = WorldPainter(world, app.tables)
    cache = ChunkCache(painter)
    small = cache.paint_overview()
    assert small.size == (world.width * OVERVIEW, world.height * OVERVIEW)
    for gx in range(cache.cols):
        for gy in range(cache.rows):
            im = cache.paint_now((gx, gy))
            assert im.size == (min(cache.n, world.width - gx * cache.n) * CANON,
                               min(cache.n, world.height - gy * cache.n) * CANON)
    assert cache.finished
    cache.close()


def test_names_on_the_land_never_cover_each_other(make_app, world):
    from realmwalker.ui.gfx import typefaces
    from realmwalker.ui.gfx.worldview import place_labels

    explored = np.ones((world.width, world.height), bool)
    rect = (0, 0, 1600, 1000)
    for ppc in (6, 12, 24):
        labels = place_labels(world, explored, ppc, 0, 0, rect, typefaces.measure)
        boxes = []
        for x, y, text, font, size, rgba, halo in labels:
            w, h = typefaces.measure(text, font, size)
            box = (x - w / 2, y - h / 2, w, h)
            assert 0 <= box[0] and box[0] + w <= rect[2] and 0 <= box[1] and box[1] + h <= rect[3]
            for b in boxes:
                assert not (b[0] < box[0] + box[2] and box[0] < b[0] + b[2] and b[1] < box[1] + box[3]
                            and box[1] < b[1] + b[3]), (text, ppc)
            boxes.append(box)
        if ppc == 12:
            assert labels, "a map of the whole land has names on it"
    assert not place_labels(world, np.zeros_like(explored), 12, 0, 0, rect, typefaces.measure), \
        "nothing is named where you have not been"


def test_towns_are_drawn_in_their_peoples_manner(make_app, atlas):
    from types import SimpleNamespace

    from realmwalker.ui.gfx.worldview import TOWN_STYLES, town_mark

    app = make_app()
    for style in TOWN_STYLES:
        for kind in ("hamlet", "city"):
            name = town_mark(app.tables, SimpleNamespace(kind=kind, culture=style), "map/village")
            assert atlas.rects.get(name), name
    assert town_mark(app.tables, SimpleNamespace(kind="hold", culture="dwarven"), "map/hold") == "map/hold"
    assert town_mark(app.tables, SimpleNamespace(kind="town", culture="heartland"), "map/town") == "map/town"


# ---------------------------------------------------------------------------- the map screen, in letters
def test_the_views_and_their_keys(make_app, world):
    app, game = start(make_app, world)
    wm = open_map(app)
    for key, mode in (("p", "realms"), ("c", "peoples"), ("w", "weather"), ("l", "land")):
        app.handle_event(KeyEvent(key))
        assert wm.view_mode == mode
        render(app)
        if mode == "realms":
            assert wm.legend and all(len(e) == 4 for e in wm.legend)
        if mode == "peoples":
            assert {e[0] for e in wm.legend} <= set(game.world.culture_ids) and wm.legend
    app.handle_event(KeyEvent("p"))
    render(app)
    first = wm.legend[0][0]
    wm._pick(first)
    assert wm.highlight == first
    render(app)
    app.handle_event(KeyEvent("tab"))
    assert wm.view_mode == "peoples" and wm.highlight is None
    assert app.error_count == 0


def test_a_click_chooses_and_a_double_click_travels(make_app, world):
    app, game = start(make_app, world)
    wm = open_map(app)
    render(app)
    p = game.player
    tx, ty = min(game.world.width - 2, p.x + 3), p.y
    px, py = wm.painted.cell_px(tx + 0.5, ty + 0.5)
    cx, cy = int(px // 10), int(py // 20)
    app.handle_event(MouseEvent("click", cx, cy, px=px, py=py))
    app.handle_event(MouseEvent("release", cx, cy, px=px, py=py))
    assert wm.cursor == (tx, ty) and app.top is wm, "one click only chooses"
    app.handle_event(MouseEvent("click", cx, cy, clicks=2, px=px, py=py))
    assert app.top is not wm, "a double click sets off"
    assert app.error_count == 0


# ---------------------------------------------------------------------------- the map screen, in pictures
def test_the_wheel_zooms_where_the_pointer_is_and_dragging_looks_about(make_app, world, atlas):
    app, game = start(make_app, world, atlas)
    app.gfx.motion = "off"  # the zoom settles at once
    wm = open_map(app)
    render(app)
    assert wm.painted is not None and wm.rect is not None
    x0, y0, w, h = wm.rect
    px, py = x0 + w * 0.3, y0 + h * 0.4
    before = wm.painted.to_cell(px, py)
    ppc = wm.ppc
    app.handle_event(MouseEvent("wheel", int(px // 10), int(py // 20), dy=1, px=px, py=py))
    render(app)
    assert wm.ppc > ppc
    assert wm.painted.to_cell(px, py) == before, "the place under the pointer stays under it"
    # Drag: press, move, let go; the map moves with the pointer and nothing is chosen.
    cursor = wm.cursor
    cam = wm.cam
    app.handle_event(MouseEvent("click", int(px // 10), int(py // 20), px=px, py=py))
    app.handle_event(MouseEvent("move", int(px // 10) + 6, int(py // 20), px=px + 60, py=py))
    app.handle_event(MouseEvent("release", int(px // 10) + 6, int(py // 20), px=px + 60, py=py))
    render(app)
    assert wm.cam[0] < cam[0] and wm.cursor == cursor
    assert app.error_count == 0


def test_the_painted_map_has_names_and_its_views(make_app, world, atlas):
    app, game = start(make_app, world, atlas)
    app.gfx.motion = "off"
    wm = open_map(app)
    canvas = render(app)
    assert [c for c in commands(canvas, Image) if isinstance(c.key, tuple) and c.key[0] in ("chunk", "map overview")]
    land = [c for c in commands(canvas, Text) if c.font in ("heading_light", "prose_italic")]
    assert land, "names on the land"
    app.handle_event(KeyEvent("p"))
    canvas = render(app)
    assert [c for c in commands(canvas, Image) if isinstance(c.key, tuple) and c.key[0] == "realms"]
    app.handle_event(KeyEvent("c"))
    canvas = render(app)
    assert [c for c in commands(canvas, Image) if isinstance(c.key, tuple) and c.key[0] == "peoples"]
    for _ in range(4):
        app.handle_event(KeyEvent("-"))
        render(app)
    assert wm.target == wm.levels(wm.rect)[0], "zoomed right out, the whole world"
    assert app.error_count == 0
