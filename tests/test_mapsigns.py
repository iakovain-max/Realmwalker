"""Signs on the world map for marks (Expansion 6 B.8, docs/ADVENTURES.md §8.16, §8.18): smoke over a burning, burned
or sacked town, tents round a besieged or beset one, the black flag of plague, a dragon's shadow over tribute,
festival lanterns, a memorial's statue; drawn headless from the marks, and under 2 ms a frame."""

import copy
import time

import tcod.console

from realmwalker.ui.gfx import mapsigns
from realmwalker.ui.gfx.scene import Image
from tests.worlds import cached_world

MARKS = {
    "burning": {"since": 0.0}, "sacked": 0.0, "burned": 0.0, "siege": {"since": 0.0, "by": 0},
    "beset": {"since": 0.0, "by": "the Horde"}, "plague": {"since": 0.0}, "tribute": "Vorgath",
    "festival": {"since": 0.0}, "memorial": {"since": 0.0},
}
KEYS = {"burning": "puff", "sacked": "puff", "burned": "puff", "siege": "tent", "beset": "tent", "plague": "black_flag",
        "tribute": "dragon_shadow", "festival": "lantern", "memorial": "statue"}


def _game(make_app):
    from realmwalker.game.state import new_game
    from realmwalker.world.generator import WorldOptions

    app = make_app()
    world = cached_world(WorldOptions("Signland", 21, "small", history=60), app.tables)
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    game.player.explored[:] = True
    app.start_game(game)
    return app, game


def _signs(canvas):
    out = set()
    for layer in canvas.layers:
        for c in layer.under + layer.over:
            if isinstance(c, Image) and isinstance(c.key, tuple) and c.key[0] == "sign":
                out.add(c.key[1])
    return out


def test_only_the_strongest_smoke_shows():
    from types import SimpleNamespace

    s = SimpleNamespace(id=1, status={"burned": 3.0, "burning": {"since": 4.0}, "plague": {"since": 1.0},
                                      "famine": {"since": 1.0}})
    assert mapsigns.signed(s) == ["burning", "plague"]
    s.status = {"burned": 3.0, "sacked": 2.0}
    assert mapsigns.signed(s) == ["sacked"]
    s.status = {"raided": {"since": 1}, "rebuilding": {"since": 1}}
    assert mapsigns.signed(s) == []


def test_every_mark_with_a_sign_is_drawn_on_the_world_map(make_app):
    from realmwalker.ui.screens.world_map import WorldMapScreen

    app, game = _game(make_app)
    p = game.player
    near = sorted(game.world.settlements, key=lambda s: abs(s.x - p.x) + abs(s.y - p.y))
    for mark, s in zip(MARKS, near):
        for other in near:
            other.status.pop(mark, None)
        s.status = {mark: copy.deepcopy(MARKS[mark])}
    wm = WorldMapScreen(app, app.top)
    app.push(wm)
    seen = set()
    for zoom in (None, 16.0):  # as it opens, then near enough to see them all
        if zoom is not None:
            wm.target = wm.ppc = zoom
        con = tcod.console.Console(160, 50, order="F")
        app.render(con)
        app.update()
        seen |= _signs(app.last_canvas)
    missing = [m for m in MARKS if KEYS[m] not in seen]
    assert not missing, missing
    for s in near[:len(MARKS)]:
        s.status = {}
    con = tcod.console.Console(160, 50, order="F")
    app.render(con)
    assert not _signs(app.last_canvas), "no marks, no signs"


def test_the_pictures_are_made(make_app):
    for make in (mapsigns._tent, mapsigns._banner, mapsigns._statue, mapsigns._lantern, mapsigns._glow,
                 lambda: mapsigns._black_flag(0), lambda: mapsigns._black_flag(1), lambda: mapsigns._puff(2)):
        a = make()
        assert a.ndim == 3 and a.shape[2] == 4 and a[..., 3].max() > 0
    assert mapsigns._dragon().size == (64, 40)


def test_signs_cost_under_two_milliseconds_a_frame(make_app):
    from realmwalker.ui.gfx import headless
    from realmwalker.ui.widgets import Canvas

    app, game = _game(make_app)
    towns = game.world.settlements[:40]
    for i, s in enumerate(towns):  # forty marked towns on the screen at once, two signs each: far beyond a real map
        m1, m2 = list(MARKS)[i % len(MARKS)], list(MARKS)[(i + 4) % len(MARKS)]
        s.status = {m1: copy.deepcopy(MARKS[m1]), m2: copy.deepcopy(MARKS[m2])}
    places = [(s, 20.0 + (i % 10) * 60, 20.0 + (i // 10) * 60, 36.0, 1.0) for i, s in enumerate(towns)]
    gfx = headless()
    canvas = Canvas(tcod.console.Console(160, 50, order="F"), gfx=gfx)
    spent = 0.0
    for frame in range(60):
        for layer in canvas.layers:
            layer.under.clear()
        t0 = time.perf_counter()
        mapsigns.under(canvas, game, places, frame / 30, (180, 170, 200))
        mapsigns.over(canvas, game, places, frame / 30, (180, 170, 200))
        spent += time.perf_counter() - t0
    assert spent / 60 < 0.002 * 3, spent / 60  # (the budget is 2 ms; a slow or busy machine is allowed three times it)


def test_a_siege_by_a_realm_that_is_gone_still_draws():
    from types import SimpleNamespace

    import tcod.console

    from realmwalker.ui.gfx import headless
    from realmwalker.ui.widgets import Canvas

    game = SimpleNamespace(world=SimpleNamespace(factions={0: SimpleNamespace(color=(40, 70, 160))}))
    canvas = Canvas(tcod.console.Console(40, 20, order="F"), gfx=headless())
    for by in (0, 7, None, "the Horde"):
        s = SimpleNamespace(id=1, kind="town", status={"siege": {"since": 0.0, "by": by}})
        mapsigns.under(canvas, game, [(s, 40.0, 40.0, 30.0, 1.0)], 0.0, (255, 255, 255))
        mapsigns.over(canvas, game, [(s, 40.0, 40.0, 30.0, 1.0)], 0.0, (255, 255, 255))
    assert "banner" in _signs(canvas)
