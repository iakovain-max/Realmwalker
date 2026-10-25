"""Life in towns (2026-10-11, Anton: "bumping into one no longer starts the dialogue automatically ... make the time
move independently of the player's moves, and make the NPC move on their own"): everyone keeps the day of their trade
and walks it (game/townlife.py); you squeeze past people and talk with t; in a town the clock runs by itself."""

import copy
import time

import numpy as np
import pytest

from realmwalker.game import townlife
from realmwalker.game.people import npc_at, npcs_in
from realmwalker.game.state import new_game
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Lifeland", 33, "small", history=40), tables)


def go_to(game, kind: str = "town", great: bool = False):
    s = max((s for s in game.world.settlements if s.kind in ("town", "city")), key=lambda s: s.population)
    s.kind, s.great = kind, great
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    return s


def at_hour(game, hour: int) -> None:
    game.world.time = (game.world.time // 1440 + 1) * 1440 + hour * 60


@pytest.fixture
def town(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    townlife.forget()
    s = go_to(game)
    return game, s


def folk(game, s):
    return [n for n in npcs_in(game.world, s.id) if n.alive and n.present]


def check_nobody_overlaps(game, s):
    lm = game.local
    T = game.tables.terrain
    walk = T.walk[game.remap_for(lm)[lm.terrain]]
    doors = np.isin(game.remap_for(lm)[lm.terrain], [T.index[n] for n in townlife.DOORS])
    spots = [(n.x, n.y) for n in folk(game, s)]
    assert len(spots) == len(set(spots)), "two people on one square"
    assert (game.player.lx, game.player.ly) not in spots, "someone standing on you"
    for x, y in spots:
        assert walk[x, y] or doors[x, y], f"someone stands in a wall at {x},{y}"


# ---------------------------------------------------------------------------- a day
def test_a_town_has_as_many_people_as_its_size_says(town, tables):
    game, s = town
    lo, hi = tables.people["settlement_people"]["town"]["folk"]
    assert lo <= len(npcs_in(game.world, s.id)) <= hi + 12  # (people of history and travellers come on top)
    jobs = {n.job for n in npcs_in(game.world, s.id)}
    assert len(jobs) >= 15, jobs  # bakers, children, elders, porters... not only farmers
    assert "child" in jobs and any(j in jobs for j in ("baker", "tailor", "cobbler", "potter", "butcher"))


def test_every_trade_has_its_words(tables):
    people = tables.people
    for job in people["occupations"]:
        assert people.get("days", {}).get(job) or people["days"].get("_default"), job
    from realmwalker.data.registry import DataRegistry
    from realmwalker.paths import Paths

    reg, errors = DataRegistry.load(Paths().data)
    assert not errors
    greetings = reg["dialogue.json"]["greeting_job"]
    missing = [job for job in people["occupations"] if job not in greetings]
    assert not missing, f"trades with no greeting of their own: {missing}"
    stories = [job for job in people["occupations"] if f"backstory_{job}" not in people["text"]]
    assert len(stories) <= 4, f"trades with no past of their own: {stories}"


def test_people_walk_to_work_and_reach_it(town):
    game, s = town
    lm = game.local
    at_hour(game, 4)
    townlife.settle(game, lm)
    assert sum(townlife.asleep(game, n) for n in folk(game, s)) > len(folk(game, s)) // 2
    workers = [n for n in folk(game, s) if townlife.day_of(game, n)[1:2] and n.job in ("smith", "shopkeeper", "healer")]
    at_hour(game, 9)
    town_ = townlife._town(game, lm)
    for _ in range(400):  # forty minutes of walking, a step every six seconds
        townlife.tick(game, lm, s)
    check_nobody_overlaps(game, s)
    there = [n for n in folk(game, s) if max(abs(n.x - townlife.goal(game, lm, n, town_)[0]),
                                            abs(n.y - townlife.goal(game, lm, n, town_)[1])) <= 1]
    assert len(there) >= 0.8 * len(folk(game, s)), f"{len(there)} of {len(folk(game, s))} where their day has them"
    for n in workers:
        assert max(abs(n.x - n.post[0]), abs(n.y - n.post[1])) <= 1, f"the {n.job} is not at work"


def test_two_put_on_one_square_part_at_the_next_step(town, monkeypatch):
    """Something outside town life (a scene, a trouble sending someone home, a crowded settling) may put two on one
    square; the next step of time parts them, even two who are where they want to be (autoplay saw a headman and a
    beggar piled for twenty turns)."""
    game, s = town
    lm = game.local
    at_hour(game, 9)
    townlife.settle(game, lm)
    a, b = folk(game, s)[:2]
    b.x, b.y = a.x, a.y
    goal = townlife.goal
    monkeypatch.setattr(townlife, "goal", lambda game, lm, npc, town=None: (
        (a.x, a.y) if npc in (a, b) else goal(game, lm, npc, town)))
    townlife.tick(game, lm, s)
    check_nobody_overlaps(game, s)


def test_a_warden_keeps_its_square_when_another_is_put_on_it(town):
    """E.7: of two on one square, the one who never budges stays; the other is parted, never onto you."""
    game, s = town
    lm = game.local
    at_hour(game, 9)
    townlife.settle(game, lm)
    a, b = folk(game, s)[:2]
    a.flags["stays"] = "gate"
    spot = (a.x, a.y)
    b.x, b.y = spot
    townlife.unpile(game, lm)
    assert (a.x, a.y) == spot and (b.x, b.y) != spot
    assert (b.x, b.y) != (game.player.lx, game.player.ly)
    check_nobody_overlaps(game, s)


def test_they_go_in_and_out_through_doors(town):
    game, s = town
    lm = game.local
    at_hour(game, 11)
    townlife.settle(game, lm)
    inside_by_day = {n.id for n in folk(game, s) if lm.building_at(n.x, n.y) is not None}
    game.world.time += 7 * 60 + 40  # the evening: off to the inn, the square, home
    for _ in range(500):
        townlife.tick(game, lm, s)
    moved = {n.id for n in folk(game, s) if (lm.building_at(n.x, n.y) is not None) != (n.id in inside_by_day)}
    assert moved, "nobody went in or out of a door all evening"
    check_nobody_overlaps(game, s)


def test_two_meeting_in_a_doorway_get_past_each_other(town, monkeypatch):
    game, s = town
    lm = game.local
    T = game.tables.terrain
    walk = T.walk[game.remap_for(lm)[lm.terrain]]
    people = folk(game, s)
    a, b = people[0], people[1]
    for n in (a, b):
        n.flags.pop("stays", None)
    for house in (h for h in lm.buildings if h.kind == "house"):
        dx_, dy_ = house.door
        sides = [(dx_ + ox, dy_ + oy) for ox, oy in ((0, 1), (0, -1), (1, 0), (-1, 0))]
        ins = [c for c in sides if house.contains(*c) and walk[c]]
        outs = [c for c in sides if not house.contains(*c) and walk[c] and lm.building_at(*c) is None]
        if ins and outs:
            inner, outer = ins[0], outs[0]
            far_out = (outer[0] * 2 - dx_, outer[1] * 2 - dy_)
            if lm.in_bounds(*far_out) and walk[far_out]:
                break
    else:
        pytest.skip("no house with a door to stand in")
    for n in people:  # everyone else out of the way
        if n not in (a, b):
            n.x, n.y = 0, 0
    a.x, a.y = inner
    b.x, b.y = outer
    goals = {a.id: far_out, b.id: inner}
    monkeypatch.setattr(townlife, "goal", lambda game, lm, npc, town=None: goals.get(npc.id, (npc.x, npc.y)))
    game.player.lx, game.player.ly = 1, 1
    townlife._town(game, lm).paths.clear()
    for _ in range(12):
        townlife.tick(game, lm, s)
    assert (a.x, a.y) == far_out and (b.x, b.y) == inner, "they stuck in the doorway"


# ---------------------------------------------------------------------------- you and them
def test_walking_into_someone_does_not_talk_and_t_does(make_app, world):
    from realmwalker.ui.input import KeyEvent

    app = make_app()
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    app.start_game(game)
    townlife.forget()
    s = go_to(game)
    lm = game.local
    at_hour(game, 12)
    townlife.settle(game, lm)
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    for npc in folk(game, s):
        if npc.flags.get("stays") or lm.building_at(npc.x, npc.y) is not None:
            continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            x, y = npc.x + dx, npc.y + dy
            if lm.in_bounds(x, y) and walk[x, y] and npc_at(game, x, y) is None and lm.building_at(x, y) is None:
                game.player.lx, game.player.ly = x, y
                break
        else:
            continue
        break
    else:
        pytest.skip("nobody in the street to stand beside")
    gs = app.top
    assert gs.npcs_beside(), "someone beside you"
    app.handle_event(KeyEvent("t"))
    app.update()
    from realmwalker.ui.screens.base import ChoiceBox
    from realmwalker.ui.screens.dialogue import DialogueScreen

    if isinstance(app.top, ChoiceBox):  # several beside you: pick one
        app.handle_event(KeyEvent("1"))
        app.update()
    assert isinstance(app.top, DialogueScreen), type(app.top)


def test_a_warden_at_the_gate_will_not_budge(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    townlife.forget()
    max((s for s in game.world.settlements if s.kind in ("town", "city")), key=lambda s: s.population).walled = True
    s = go_to(game)
    lm = game.local
    wardens = [n for n in folk(game, s) if n.flags.get("stays")]
    assert wardens, "a walled town has wardens at its gates"
    w = wardens[0]
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        x, y = w.x + dx, w.y + dy
        if lm.in_bounds(x, y) and walk[x, y] and npc_at(game, x, y) is None:
            game.player.lx, game.player.ly = x, y
            spot = (w.x, w.y)
            assert game.move(-dx, -dy) is False
            assert (w.x, w.y) == spot and (game.player.lx, game.player.ly) == (x, y)
            assert game.talk_to is None
            return
    pytest.skip("nowhere to stand beside the warden")


# ---------------------------------------------------------------------------- the town clock
def test_the_town_clock_runs_by_itself_and_stops_under_other_screens(make_app, world, monkeypatch):
    from realmwalker.ui.screens.base import MessageBox

    app = make_app()
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    app.start_game(game)
    townlife.forget()
    s = go_to(game)
    at_hour(game, 10)
    townlife.settle(game, game.local)
    clock = [1000.0]
    monkeypatch.setattr(app, "clock", lambda: clock[0])
    t0 = game.world.time * 60 + game.player.seconds
    where = {n.id: (n.x, n.y) for n in folk(game, s)}
    for _ in range(40):
        clock[0] += 0.6
        app.update()
    t1 = game.world.time * 60 + game.player.seconds
    assert t1 - t0 >= 30 * townlife.STEP_SECONDS, "time flows in town while you watch"
    assert any((n.x, n.y) != where[n.id] for n in folk(game, s)), "and people walk"
    app.push(MessageBox(app, "Wait", "A box over the town."))
    for _ in range(10):
        clock[0] += 0.6
        app.update()
    assert game.world.time * 60 + game.player.seconds == t1, "time stops while another screen is open"
    app.pop()
    app.settings.time_in_towns = "waits"
    for _ in range(10):
        clock[0] += 0.6
        app.update()
    assert game.world.time * 60 + game.player.seconds == t1, "the setting says time waits for you"


def test_time_waits_in_the_wild(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    game.enter_local()  # wherever you start, if not a town: the wild
    if game.local is not None and game.local.kind == "settlement":
        game.player.local_key = None
        s = game.world.settlements[0]
        game.player.x, game.player.y = s.x + 3, s.y + 3
        game.enter_local()
    if game.local is None or game.local.kind == "settlement":
        pytest.skip("no wild here")
    assert game.town_tick() is False


def test_a_busy_great_city_steps_in_good_time(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    townlife.forget()
    s = go_to(game, "city", great=True)
    lm = game.local
    people = folk(game, s)
    assert len(people) >= 250, len(people)
    at_hour(game, 7)  # everyone off to work
    townlife.settle(game, lm)
    game.world.time += 30
    for _ in range(20):  # the ways get found
        townlife.tick(game, lm, s)
    t0 = time.perf_counter()
    for _ in range(30):
        townlife.tick(game, lm, s)
    each = (time.perf_counter() - t0) / 30
    print(f"a step of time for {len(people)} people: {each * 1000:.1f} ms")
    assert each < 0.03, f"{each * 1000:.1f} ms a step"
    check_nobody_overlaps(game, s)


# ---------------------------------------------------------------------------- words in passing
def _stand_in_the_crowd(game, s):
    """You, in the street where most people are about."""
    lm = game.local
    people = [n for n in folk(game, s) if lm.building_at(n.x, n.y) is None]
    if people:
        mx = sorted(n.x for n in people)[len(people) // 2]
        my = sorted(n.y for n in people)[len(people) // 2]
        walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
        taken = {(n.x, n.y) for n in folk(game, s)}
        spots = [(x, y) for x in range(max(0, mx - 8), min(lm.width, mx + 9))
                 for y in range(max(0, my - 8), min(lm.height, my + 9))
                 if walk[x, y] and (x, y) not in taken and lm.building_at(x, y) is None]
        if spots:
            game.player.lx, game.player.ly = min(spots, key=lambda c: abs(c[0] - mx) + abs(c[1] - my))


def test_people_call_out_in_passing_now_and_then(town):
    game, s = town
    lm = game.local
    game.verbosity = "normal"
    at_hour(game, 11)
    townlife.settle(game, lm)
    _stand_in_the_crowd(game, s)
    heard: dict[int, list[int]] = {}
    most = 0
    for i in range(400):
        townlife.tick(game, lm, s)
        said = townlife.said(game, lm)
        most = max(most, len(said))
        for who in said:
            heard.setdefault(who, []).append(i)
        assert all(isinstance(w, str) and w for w in said.values())
    assert heard, "nobody said a word in forty minutes of the market"
    assert most <= 3, "no more than three voices at once"
    for who, ticks in heard.items():  # each time they speak is a short run of ticks; the next is long after
        runs = [t for k, t in enumerate(ticks) if k == 0 or t != ticks[k - 1] + 1]
        assert all(b - a > townlife.BARK_REST for a, b in zip(runs, runs[1:])), "the same voice again too soon"
    game.verbosity = "brief"  # (Text detail: Brief keeps only what matters)
    townlife.forget()
    for _ in range(200):
        townlife.tick(game, lm, s)
        assert not townlife.said(game, lm)


def test_words_in_passing_are_drawn_over_heads(make_app, world):
    from realmwalker.paths import Paths
    from realmwalker.ui.gfx import GfxContext
    from realmwalker.ui.gfx.atlas import Atlas
    from realmwalker.ui.gfx.scene import Text
    import tcod.console

    app = make_app()
    app.gfx = GfxContext(Atlas(Paths().tiles), 10, 20, background=False)
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    app.start_game(game)
    townlife.forget()
    s = go_to(game)
    lm = game.local
    at_hour(game, 11)
    townlife.settle(game, lm)
    _stand_in_the_crowd(game, s)
    game.verbosity = "normal"
    for _ in range(300):
        townlife.tick(game, lm, s)
        if townlife.said(game, lm):
            break
    said = townlife.said(game, lm)
    if not said:
        pytest.skip("nobody spoke")
    con = tcod.console.Console(160, 50, order="F")
    app.render(con)
    texts = [c.text for layer in app.last_canvas.layers for c in layer.under + layer.over if isinstance(c, Text)]
    visible = [w for who, w in said.items()]
    assert any(w in texts for w in visible), (visible, texts[:10])


def test_market_days_fill_the_square(town):
    game, s = town
    lm = game.local
    town_ = townlife._town(game, lm)
    square = set(town_.square)
    counts = {}
    for day in range(7):  # a week of mornings
        game.world.time = (game.world.time // 1440 + 1) * 1440 + 10 * 60
        townlife.forget()
        town_ = townlife._town(game, lm)
        goals = [townlife.goal(game, lm, n, town_) for n in folk(game, s)]
        counts[townlife.market_day(game)] = counts.get(townlife.market_day(game), []) + [
            sum(1 for g in goals if g in square)]
    assert True in counts and False in counts, "a week has market days and other days"
    assert min(counts[True]) > max(counts[False]), counts


def test_a_town_made_ahead_of_you_is_peopled_on_its_own_map(town):
    """(A job needing someone in another town makes that town while you stand in this one: its people go on its own
    map, and this town's people stay where they are.)"""
    from realmwalker.game.people import prepare_town

    game, s = town
    before = {n.id: (n.x, n.y) for n in folk(game, s)}
    other = next(o for o in game.world.settlements if o.id != s.id and o.kind in ("village", "town", "city"))
    prepare_town(game, other)
    lm = game.world.local_maps[f"{other.x},{other.y}"]
    there = npcs_in(game.world, other.id)
    assert there
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    for n in there:
        assert lm.in_bounds(n.x, n.y) and walk[n.x, n.y]
    assert {n.id: (n.x, n.y) for n in folk(game, s)} == before


# ---------------------------------------------------------------------------- things happening
def test_on_the_holy_day_the_clergy_go_in_procession(town):
    game, s = town
    lm = game.local
    for _ in range(8):  # to the next holy day, mid-morning
        game.world.time = (game.world.time // 1440 + 1) * 1440 + 10 * 60 + 20
        if townlife.holy_day(game):
            break
    clergy = [n for n in folk(game, s) if n.job in townlife.CLERGY]
    if not clergy:
        pytest.skip("no temple here")
    town_ = townlife._town(game, lm)
    route = townlife._route(town_, lm)
    for n in clergy:
        assert townlife.activity(game, n) == "procession"
        assert townlife.goal(game, lm, n, town_) in route
    game.world.time += 2 * 60  # and after it, back to their work
    assert all(townlife.activity(game, n) != "procession" for n in clergy)


def test_a_brawl_brings_the_watch(town):
    game, s = town
    lm = game.local
    game.verbosity = "normal"
    at_hour(game, 20)
    townlife.settle(game, lm)
    town_ = townlife._town(game, lm)
    guards = [n for n in folk(game, s) if n.job == "guard" and not n.flags.get("stays")]
    if not guards:
        pytest.skip("no watch here")
    g = guards[0]
    spot = next(c for c in sorted(town_.streets, key=lambda c: abs(c[0] - g.x) + abs(c[1] - g.y))
                if abs(c[0] - g.x) + abs(c[1] - g.y) >= 6)
    others = [n for n in folk(game, s) if n.job not in ("guard", "soldier")]
    a, b = others[0], others[1]
    a.x, a.y = spot
    town_.brawl = {"spot": spot, "a": a.id, "b": b.id, "until": town_.ticks + 1000, "told": True}
    for _ in range(300):
        townlife.tick(game, lm, s)
        if town_.brawl is None:
            break
    assert town_.brawl is None, "the watch came and broke it up"
    assert any("watch" in m.text for m in game.log.messages[-3:])
