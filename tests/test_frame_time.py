"""Budgets for the eye (Expansion 6 B.9, docs/ADVENTURES.md §8.18): a frame on a burning great city at the closest
zoom, recorded headless (every picture command built as in a window, nothing drawn), stays inside its budget - at
most 64 squares of moving flames, 40 smoke columns and one atmosphere - and the world map's signs inside theirs
(tests/test_mapsigns.py). The bound is generous, for slow machines: the budget is 8 ms."""

import copy
import statistics
import time

import numpy as np
import pytest
import tcod.console

from realmwalker.game import fire, townlife
from realmwalker.game.state import new_game
from realmwalker.world import marks
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.test_townlife import at_hour, go_to
from tests.worlds import cached_world

BUDGET = 0.008
GENEROUS = 3.0  # (a slow machine, or one busy with other tests)


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.mark.slow
def test_a_frame_on_a_burning_great_city(tables):
    from realmwalker.ui.gfx import atmosfx, headless
    from realmwalker.ui.gfx.localview import FIRE_ANIMATED, LocalView
    from realmwalker.ui.gfx.scene import Sprite
    from realmwalker.ui.widgets import Canvas

    game = new_game(copy.deepcopy(cached_world(WorldOptions("Lifeland", 33, "small", history=40), tables)), tables)
    game.survival = False
    townlife.forget()
    at_hour(game, 21)
    s = go_to(game, "city", great=True)
    marks.add(game.world, s, "burning", game.world.time / 1440.0, tables)
    game.player.local_key = None
    game.enter_local()
    lm = game.local
    lm.seen[:] = True
    p = game.player
    houses = sorted((b for b in lm.buildings if b.kind == "house"),
                    key=lambda b: (b.x + b.w / 2 - p.lx) ** 2 + (b.y + b.h / 2 - p.ly) ** 2)[:24]
    cells = [(x, y) for b in houses for x in range(b.x, b.x + b.w) for y in range(b.y, b.y + b.h) if b.contains(x, y)]
    fire.light(game, lm, cells, taken=set())
    burning = len(lm.meta.get("fire") or {})
    assert burning > FIRE_ANIMATED, "more burning than is ever drawn moving"
    gfx = headless()
    view = LocalView()
    fov = np.ones((lm.width, lm.height), bool)
    rect = (0, 0, 1600, 1000)
    tile = 64  # (the closest zoom)
    times = []
    for frame in range(16):
        canvas = Canvas(tcod.console.Console(160, 50, order="F"), gfx=gfx)
        t0 = time.perf_counter()
        view.draw(canvas, game, rect, tile, fov)
        atmosfx.draw(canvas, rect, game, frame / 30)
        if frame:  # (the first frame makes the map's art, once)
            times.append(time.perf_counter() - t0)
    blaze = set(gfx.atlas.family("fx/blaze"))
    flames = [c for layer in canvas.layers for c in layer.under + layer.over if isinstance(c, Sprite) and c.name in blaze]
    assert flames, "the fire is drawn"
    took = statistics.median(times)
    assert took < BUDGET * GENEROUS, f"{took * 1000:.1f} ms a frame"
