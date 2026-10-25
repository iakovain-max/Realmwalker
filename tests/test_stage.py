"""The stage (Expansion 6 B.1, docs/ADVENTURES.md §5.18, §8.11): scenes played on a town's map by its own people - a
runner comes to you through the crowd, folk gather round, words over heads whatever the Text detail, a thing handed
over, a door slammed - while the whole town goes on living, and never two people on one square."""

import copy
import time

import pytest

from realmwalker.game import townlife
from realmwalker.game.people import npcs_in, town_of
from realmwalker.game.state import new_game as _new_game
from realmwalker.game.story import beats, stage
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.test_townlife import at_hour, check_nobody_overlaps, go_to
from tests.worlds import cached_world, quiet_start


def new_game(*a, **k):
    return quiet_start(_new_game(*a, **k))  # (the first hour's opening has its own tests)

EVERY_CUE = {"id": "every_cue", "cues": [
    {"cue": "pick", "role": "a", "jobs": ["child", "labourer", "farmer", "porter"], "any": True},
    {"cue": "pick", "role": "b", "any": True},
    {"cue": "arrive", "role": "c", "job": "pilgrim"},
    {"cue": "hold"},
    {"cue": "focus", "at": "a"},
    {"cue": "run", "who": "a", "to": "you"},
    {"cue": "say", "who": "a", "words": ["Wait!"], "ticks": 1},
    {"cue": "shout", "who": "a", "words": ["Over here!"], "ticks": 1},
    {"cue": "give", "who": "a", "item": "sealed_letter"},
    {"cue": "take", "who": "a", "item": "sealed_letter"},
    {"cue": "walk", "who": "c", "to": "a"},
    {"cue": "follow", "who": "b", "to": "a"},
    {"cue": "kneel", "who": "b"},
    {"cue": "rise", "who": "b"},
    {"cue": "crowd", "at": "a", "count": 6, "murmur": ["Look!", "Who is it?"], "ticks": 12},
    {"cue": "wait", "ticks": 2},
    {"cue": "disperse"},
    {"cue": "bell", "words": ["A bell rings out over the roofs."]},
    {"cue": "door", "who": "b", "do": "slam"},
    {"cue": "release"},
    {"cue": "flee", "who": "c"},
    {"cue": "fall", "who": "c"},
    {"cue": "die", "who": "c"},
    {"cue": "talk", "who": "b", "words": ["You. We must talk."]},
    {"cue": "beat", "id": "story_hook"},
    {"cue": "fight", "group": "nonexistent_band"},
]}


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Lifeland", 33, "small", history=40), tables)


def _town_of(game, s):
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    return s


def test_every_cue_plays_on_a_town_of_each_people(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    towns = {}
    for s in game.world.settlements:
        if s.kind in ("town", "city", "village") and s.culture not in towns:
            towns[s.culture] = s
    assert towns
    for culture, s in sorted(towns.items()):
        townlife.forget()
        _town_of(game, s)
        at_hour(game, 11)
        townlife.settle(game, game.local)
        rec = stage.start(game, copy.deepcopy(EVERY_CUE), force=True)
        assert rec is not None, culture
        talked = []
        lm = game.local
        for _ in range(400):
            if stage.current(game) is None:
                break
            if game.talk_to is not None:
                talked.append(game.talk_to)
            game.talk_to = None
            beats.director(game.world)["pending"] = None
            townlife.tick(game, lm, s)
            check_nobody_overlaps(game, s)
        assert stage.current(game) is None, f"{culture}: the scene ended"
        assert not any(n.flags.get("errand") for n in npcs_in(game.world, s.id)), "errands cleared"
        assert "gathering" not in town_of(game.world, s.id).flags
        assert talked, f"{culture}: the talk cue opened a conversation"
        assert not any(it.def_id == "sealed_letter" for it in game.leader.inventory), "given, then taken back"


def test_a_runner_comes_to_you_through_a_crowded_street(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    townlife.forget()
    s = go_to(game, "city", great=True)
    lm = game.local
    at_hour(game, 12)
    townlife.settle(game, lm)
    p = game.player
    sq = townlife.town_for(game, lm).square
    taken = {(n.x, n.y) for n in npcs_in(game.world, s.id) if n.alive and n.present}
    p.lx, p.ly = next(c for c in sq[len(sq) // 2:] + sq if c not in taken)
    rec = stage.start(game, "runner", force=True, then={"beat": "story_hook", "words": {
        "hook": "The wolf has killed again.", "villain": "the wolf", "home": "the hills", "where": "north"}})
    assert rec is not None
    reached = None
    for i in range(80):
        townlife.tick(game, lm, s)
        check_nobody_overlaps(game, s)
        runner = game.world.npcs.get(rec["cast"].get("runner"))
        if runner is None and stage.current(game) is None:
            break  # (nobody to run: the beat comes all the same)
        if runner is not None and max(abs(runner.x - p.lx), abs(runner.y - p.ly)) <= 1:
            reached = i
            break
    assert reached is not None, "the runner reached you"
    assert game.held, "your keys wait while they come and speak"
    for _ in range(40):
        if beats.pending(game) is not None:
            break
        townlife.tick(game, lm, s)
    assert beats.pending(game) is not None and beats.pending(game)["beat"] == "story_hook", "and the beat opens"
    # They pressed a letter into your hand: a page in its writer's hand, opening now and again from the pack.
    from realmwalker.game import letters

    item = next(it for it in game.leader.inventory if letters.lid_of(it))
    rec = letters.of_item(game, item)
    assert rec["lines"] and rec["from"] and rec["hand"] in letters.HANDS
    assert game.letter == letters.lid_of(item), "its page opens"
    assert "{" not in " ".join(rec["lines"]), rec["lines"]


def test_words_of_a_scene_are_shown_whatever_the_text_detail(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    game.verbosity = "terse"
    townlife.forget()
    s = go_to(game)
    at_hour(game, 11)
    townlife.settle(game, game.local)
    rec = stage.start(game, {"cues": [{"cue": "pick", "role": "a", "any": True},
                                      {"cue": "say", "who": "a", "words": ["A word in your ear."], "ticks": 2}]},
                      force=True)
    townlife.tick(game, game.local, s)
    assert "A word in your ear." in townlife.said(game, game.local).values()
    assert rec["cast"]["a"] in townlife.said(game, game.local)


def test_the_town_clock_runs_while_a_scene_holds(make_app, world, monkeypatch):
    app = make_app()
    game = new_game(copy.deepcopy(world), app.tables)
    game.survival = False
    app.start_game(game)
    townlife.forget()
    s = go_to(game)
    at_hour(game, 10)
    townlife.settle(game, game.local)
    app.settings.time_in_towns = "waits"
    clock = [1000.0]
    monkeypatch.setattr(app, "clock", lambda: clock[0])
    stage.start(game, {"cues": [{"cue": "hold"}, {"cue": "wait", "ticks": 30}]}, force=True)
    townlife.tick(game, game.local, s)
    assert game.held and not game.busy
    t0 = game.world.time * 60 + game.player.seconds
    where = (game.player.lx, game.player.ly)
    from realmwalker.ui.input import KeyEvent

    app.screens[-1].handle_key(KeyEvent("right"))
    assert (game.player.lx, game.player.ly) == where, "moves wait while the scene holds"
    for _ in range(10):
        clock[0] += 0.6
        app.update()
    assert game.world.time * 60 + game.player.seconds > t0, "the town clock runs (whatever the setting)"
    app.screens[-1].handle_key(KeyEvent("escape"))
    assert stage.current(game) is None and not game.held, "Escape skips to the end"
    t1 = game.world.time * 60 + game.player.seconds
    for _ in range(5):
        clock[0] += 0.6
        app.update()
    assert game.world.time * 60 + game.player.seconds == t1, "and then time waits for you again, as set"


def test_with_animations_off_movement_completes_at_once(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    game.animations = "off"
    townlife.forget()
    s = go_to(game)
    at_hour(game, 11)
    townlife.settle(game, game.local)
    rec = stage.start(game, {"cues": [{"cue": "pick", "role": "a", "any": True},
                                      {"cue": "run", "who": "a", "to": "you"},
                                      {"cue": "crowd", "at": "you", "count": 5},
                                      {"cue": "wait", "ticks": 5}]}, force=True)
    townlife.tick(game, game.local, s)
    a = game.world.npcs[rec["cast"]["a"]]
    p = game.player
    assert max(abs(a.x - p.lx), abs(a.y - p.ly)) <= 1, "the runner is beside you"
    check_nobody_overlaps(game, s)


def test_a_scene_saved_in_its_middle_ends_on_load(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    townlife.forget()
    s = go_to(game)
    at_hour(game, 11)
    townlife.settle(game, game.local)
    rec = stage.start(game, "runner", force=True, then={"beat": "story_hook", "words": {}})
    for _ in range(2):
        townlife.tick(game, game.local, s)
    if stage.current(game) is None:
        pytest.skip("the runner was there already")
    stage.on_load(game)
    assert stage.current(game) is None
    assert not any(n.flags.get("errand") for n in npcs_in(game.world, s.id))
    assert beats.pending(game) is not None, "what the scene was bringing still comes"
    assert rec["id"] == "runner"


def test_a_scene_left_behind_is_over(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    townlife.forget()
    go_to(game)
    stage.start(game, "plea", force=True, then={"beat": "story_hook", "words": {}})
    game.leave_local()
    stage.check_here(game)
    assert stage.current(game) is None and beats.pending(game) is not None


def test_a_great_city_steps_in_good_time_with_a_scene_of_twenty(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    townlife.forget()
    s = go_to(game, "city", great=True)
    lm = game.local
    at_hour(game, 7)
    townlife.settle(game, lm)
    game.world.time += 30
    for _ in range(20):
        townlife.tick(game, lm, s)
    cues = [{"cue": "pick", "role": f"r{i}", "any": True, "within": 200} for i in range(4)]
    cues += [{"cue": "run", "who": f"r{i}", "to": "square"} for i in range(4)]
    cues += [{"cue": "crowd", "at": "square", "count": 16, "radius": 3, "murmur": ["Look!"], "ticks": 300}]
    stage.start(game, {"cues": cues}, force=True)
    for _ in range(5):  # (the actors are cast and set going)
        townlife.tick(game, lm, s)
    t0 = time.perf_counter()
    for _ in range(30):
        townlife.tick(game, lm, s)
    each = (time.perf_counter() - t0) / 30
    print(f"a step of time with a scene of twenty: {each * 1000:.1f} ms")
    assert each < 0.03, f"{each * 1000:.1f} ms a step"
    check_nobody_overlaps(game, s)


def test_the_scenes_data_is_sound(tables):
    from realmwalker.game.story import check

    assert check.scene_problems(tables) == []
    assert {"runner", "plea"} <= set(tables.scenes)


@pytest.mark.story
def test_a_town_s_people_bring_a_tale_to_you(tables):
    """Entering a town at a beast's door: someone of the town comes to you with it (the runner or the plea), and the
    hook opens when they have had their say."""
    from tests.test_story_hooks import _start_near_a_beast

    made = cached_world(WorldOptions("Forgeland", 77, "medium"), tables)
    game, t = _start_near_a_beast(made, tables)
    beats.director(game.world)["scheduled"] = []
    if not t["stakes"]:
        pytest.skip("no town at its door")
    town = game.world.settlements[t["stakes"][0]]
    townlife.forget()
    at_hour(game, 11)
    _town_of(game, town)
    rec = stage.current(game)
    assert rec is not None and rec["id"] in ("runner", "plea"), "someone comes to you"
    lm = game.local
    for _ in range(200):
        if beats.pending(game) is not None:
            break
        townlife.tick(game, lm, town)
    pend = beats.pending(game)
    assert pend is not None and pend["beat"] == "story_hook" and pend["words"]["threat"] == t["id"]


# ---------------------------------------------------------------------------- eavesdropping, tailing, tracks (B.6)
def _two_talking(game, s):
    lm = game.local
    rec = stage.start(game, {"id": "talk", "cues": [
        {"cue": "pick", "role": "a", "any": True, "within": 200},
        {"cue": "pick", "role": "b", "any": True, "within": 200},
        {"cue": "walk", "who": "a", "to": "square"},
        {"cue": "walk", "who": "b", "to": "a"},
        {"cue": "overhear", "a": "a", "b": "b", "matters": 1, "knows": "the_mill",
         "words": ["Did you see him at the mill?", "At midnight. With a lantern.", "Say nothing."]}]}, force=True)
    for _ in range(80):  # (they go to their spot and wait there, talking low, for someone to hear)
        townlife.tick(game, lm, s)
        if rec["i"] == 4:
            break
    return rec


def test_a_talk_overheard_only_near_enough(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    townlife.forget()
    s = go_to(game)
    at_hour(game, 11)
    townlife.settle(game, game.local)
    lm = game.local
    p = game.player
    town = townlife.town_for(game, lm)
    sq = town.square[len(town.square) // 2]
    taken = {(n.x, n.y) for n in game.world.npcs.values() if n.present}
    p.lx, p.ly = max((c for c in town.streets if c not in taken),
                     key=lambda c: max(abs(c[0] - sq[0]), abs(c[1] - sq[1])))  # (you, far off down the streets)
    rec = _two_talking(game, s)
    a = game.world.npcs[rec["cast"]["a"]]
    for _ in range(10):
        townlife.tick(game, lm, s)
    assert not rec.get("said") and not rec.get("known"), "too far: nothing heard"
    walk = tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    from realmwalker.game import vision

    near = next((x, y) for x in range(a.x - 3, a.x + 4) for y in range(a.y - 3, a.y + 4)
                if lm.in_bounds(x, y) and walk[x, y] and (x, y) != (a.x, a.y)
                and all((n.x, n.y) != (x, y) for n in game.world.npcs.values() if n.present)
                and vision.can_see(game, lm, (x, y), (a.x, a.y), 6))
    p.lx, p.ly = near
    for _ in range(12):
        townlife.tick(game, lm, s)
        if stage.current(game) is None:
            break
    assert "the_mill" in rec.get("known", []), "near: the line that matters is heard"


def test_tailing_a_suspect(tables, world):
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    townlife.forget()
    s = go_to(game)
    at_hour(game, 11)
    townlife.settle(game, game.local)
    lm = game.local
    scene = {"id": "tail", "cues": [{"cue": "pick", "role": "s", "any": True, "within": 8},
                                    {"cue": "tail", "who": "s", "to": "gate", "seen": "run", "knows": "the_door"}]}
    # Walking upright behind them, you are seen when they look back.
    rec = stage.start(game, copy.deepcopy(scene), force=True)
    for _ in range(60):
        townlife.tick(game, lm, s)
        if stage.current(game) is None:
            break
    assert rec.get("spotted") or rec.get("followed") or rec.get("lost")
    if rec.get("spotted"):
        assert "the_door" not in rec.get("known", [])
    # Creeping well, you follow them all the way (you keep up, a step behind).
    stage.end(game)
    game.sneaking, game.sneak_roll = True, 40
    s.__dict__  # (the same town)
    import realmwalker.game.people as people_mod

    town = people_mod.town_of(game.world, s.id)
    town.flags.pop("scene_day", None)
    rec = stage.start(game, copy.deepcopy(scene), force=True)
    for _ in range(200):
        townlife.tick(game, lm, s)
        if stage.current(game) is None:
            break
        npc = game.world.npcs.get(rec["cast"].get("s"))
        if npc is not None:  # (you keep two squares behind)
            walk = tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
            spots = [(npc.x + dx, npc.y + dy) for dx in (-2, -1, 1, 2) for dy in (-2, -1, 1, 2)
                     if lm.in_bounds(npc.x + dx, npc.y + dy) and walk[npc.x + dx, npc.y + dy]
                     and all((n.x, n.y) != (npc.x + dx, npc.y + dy) for n in game.world.npcs.values() if n.present)]
            if spots:
                game.player.lx, game.player.ly = spots[0]
    assert rec.get("followed") and "the_door" in rec.get("known", []), rec


def test_tracks_lead_off_the_map_and_on_across_the_land(tables, world):
    from realmwalker.game import remains, story

    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    townlife.forget()
    go_to(game)
    lm = game.local
    p = game.player
    path = remains.lay_tracks(game, lm, (p.lx, p.ly))
    assert path and (path[-1][0] in (0, lm.width - 1) or path[-1][1] in (0, lm.height - 1)), "to the map's edge"
    assert all(lm.meta["decals"][f"{x},{y}"][0] == "tracks" for x, y in path)
    p.lx, p.ly = path[-1]
    game.leave_local()
    tile = tuple(lm.meta["tracks_to"]["tile"])
    assert tile in story.map_marks(game), "the next square of the land is marked"
    game.world.time += 1440 * 2
    remains.tick(game, lm)
    assert not any(rec[0] == "tracks" for rec in lm.meta["decals"].values()), "in two days they are gone"
