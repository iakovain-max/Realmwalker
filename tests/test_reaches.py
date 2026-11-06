"""A threat's reach washed on the world map once known (Expansion 6 G.8, docs/ADVENTURES.md §5.21, §8.16): the country
round a beast's den red, a risen king's under mist, an outlaw's grey; shown only once the hero has heard its signs and
seen its den, or taken its tale; spreading and thickening stage by stage; one soft picture a threat, kept by its key."""

import copy

import numpy as np
import pytest
import tcod.console

from realmwalker.game import story
from realmwalker.ui.gfx import mapsigns
from realmwalker.ui.gfx.scene import Image
from realmwalker.world import threats
from tests.worlds import cached_world

pytestmark = pytest.mark.story


def _game(make_app):
    from realmwalker.game.state import new_game
    from realmwalker.world.generator import WorldOptions

    app = make_app()
    world = cached_world(WorldOptions("Forgeland", 77, "medium"), app.tables)
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    app.start_game(game)
    return app, game


def _a_threat(game, kind=None):
    live = [t for t in threats.live(game.world) if t.get("adventure") is None and (kind is None or t["kind"] == kind)]
    if not live:
        pytest.skip(f"no live {kind or 'threat'}")
    t = live[0]
    for other in threats.records(game.world).values():
        if other is not t:
            other["state"] = "ended"
    if t["state"] == "dormant":
        threats.stir(game.world, game.tables, t, game.world.rng, day=0)
    if not t.get("signs"):
        t["signs"] = [987654]
    return t


def _reach_images(canvas):
    return [c for layer in canvas.layers for c in layer.under
            if isinstance(c, Image) and isinstance(c.key, tuple) and c.key[0] == "reach"]


def test_every_kind_says_how_its_reach_looks(make_app):
    app = make_app()
    for kid, kind in app.tables.threats["kinds"].items():
        assert kind.get("wash", "grey") in mapsigns.WASHES, kid
    assert {k.get("wash") for k in app.tables.threats["kinds"].values()} >= {"red", "mist", "grey"}


def test_a_reach_is_shown_only_once_known(make_app):
    app, game = _game(make_app)
    t = _a_threat(game)
    hx, hy = threats.home_xy(game.world, t)
    game.player.explored[hx, hy] = False
    game.renown.heard.discard(t["signs"][-1])
    assert not story.known_reaches(game), "nothing heard, nothing shown"
    game.renown.heard.add(t["signs"][-1])
    assert not story.known_reaches(game), "heard, but the den never seen: not given away"
    game.player.explored[hx, hy] = True
    (r,) = story.known_reaches(game)
    assert r["id"] == t["id"] and (r["x"], r["y"]) == (t["reach"]["x"], t["reach"]["y"])
    assert r["wash"] == app.tables.threats["kinds"][t["kind"]].get("wash", "grey")
    t["state"] = "ended"
    assert not story.known_reaches(game), "an ended threat's shadow lifts"


def test_a_tale_taken_shows_its_reach(make_app):
    from realmwalker.game.story import beats, forge

    app, game = _game(make_app)
    t = next((t for t in threats.live(game.world) if t.get("adventure") is None and forge.fitting(game, t)), None)
    if t is None:
        pytest.skip("no fitting tale")
    hx, hy = threats.home_xy(game.world, t)
    game.player.explored[hx, hy] = False
    game.renown.heard.difference_update(t.get("signs", []))
    forge.make(game, t)
    beats.director(game.world)["pending"] = None
    assert t["id"] in {r["id"] for r in story.known_reaches(game)}, "the hero's own tale: its reach is known"


def test_the_reach_spreads_and_thickens_stage_by_stage(make_app):
    app, game = _game(make_app)
    t = _a_threat(game)
    game.renown.heard.add(t["signs"][-1])
    game.player.explored[threats.home_xy(game.world, t)] = True
    seen = []
    for stage in range(len(t["scheme"]["stages"])):
        t["scheme"]["stage"] = stage
        (r,) = story.known_reaches(game)
        seen.append(r)
    assert seen[0]["r"] < seen[-1]["r"] == int(t["reach"]["r"])
    assert seen[0]["strength"] < seen[-1]["strength"] <= 1.0
    assert len({tuple(r["key"]) for r in seen}) == len(seen), "a new stage, a new picture"
    t["scheme"]["stage"] = len(seen) - 1
    assert story.known_reaches(game)[0]["key"] == seen[-1]["key"], "the same stage, the same picture"


def test_the_wash_picture(make_app):
    for wash, (rgb, most, rag, _) in mapsigns.WASHES.items():
        a = mapsigns.wash_picture("T3", 9, rgb, most, rag)
        side = 19 * mapsigns.WASH_PX
        assert a.shape == (side, side, 4) and a.dtype == np.uint8
        assert a[side // 2, side // 2, 3] > 0, "thick in the middle"
        assert a[0, 0, 3] == 0 and a[-1, -1, 3] == 0, "nothing at the corners"
        assert a[..., 3].max() <= most
        assert np.array_equal(a, mapsigns.wash_picture("T3", 9, rgb, most, rag)), "the same threat, the same picture"
    assert not np.array_equal(mapsigns.wash_picture("T3", 9, *mapsigns.WASHES["red"][:3]),
                              mapsigns.wash_picture("T4", 9, *mapsigns.WASHES["red"][:3])), "each its own edge"


def test_the_world_map_washes_a_known_reach(make_app):
    from realmwalker.ui.screens.world_map import WorldMapScreen

    app, game = _game(make_app)
    t = _a_threat(game)
    game.renown.heard.add(t["signs"][-1])
    game.player.explored[:] = True
    wm = WorldMapScreen(app, app.top)
    app.push(wm)
    for zoom in (None, 16.0):
        if zoom is not None:
            wm.target = wm.ppc = zoom
            wm.cam = wm.cursor = (t["reach"]["x"], t["reach"]["y"])
        con = tcod.console.Console(160, 50, order="F")
        app.render(con)
        app.update()
        ims = _reach_images(app.last_canvas)
        assert len(ims) == 1 and ims[0].key[1] == t["id"], zoom
        im = ims[0]
        assert im.make().shape[2] == 4 and im.src is not None
    # the game screen's own map draws it too
    app.screens.pop()
    con = tcod.console.Console(160, 50, order="F")
    app.render(con)
    assert len(_reach_images(app.last_canvas)) == 1
    t["state"] = "ended"
    app.render(con)
    assert not _reach_images(app.last_canvas)
    assert app.error_count == 0
