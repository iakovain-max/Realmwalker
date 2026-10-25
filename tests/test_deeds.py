"""Part D's step kinds in a real game (Expansion 6 D.2, docs/ADVENTURES.md §6.2, §8.5): a test tale on a risen threat
uses all ten - rescue on the barrow's upper level, defeat and capture on the road (the captive judged in the
aftermath), fetch, recruit, rally, confront, escort with its ambush, hold on a set night (waves with no rest), the
rite - and each is finished by what the game already does (step quests, fights, talk, the goal language); a missed
night fails its step and the tale goes on (law 6)."""

import copy
from types import SimpleNamespace

import pytest

from realmwalker.game import camp, dungeon, quests
from realmwalker.game import story
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import prepare_town
from realmwalker.game.state import new_game
from realmwalker.game.story import beats, cast, deeds, forge, places
from realmwalker.world import threats
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world

pytestmark = pytest.mark.story


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Threatland", 61, "medium"), tables)


def _blueprint(tables):
    bp = copy.deepcopy(tables.adventures["blueprints"]["beast"])
    bp.update({"name": "The Test of the Dead", "from": ["risen"], "tiers": [1, 4]})
    bp["places"] = {"home": "threat.home", "town": "settlement_near(home, 0, 40)",
                    "road": "road_tile_near(town, 1, 12) | road_tile_near(home, 1, 20)",
                    "dest": "settlement_near(town, 3, 40)"}
    bp["hidden"] = {}
    bp["cast"] = {"patron": {"pick": ["headman_of(town)", "notable_of(town)"]},
                  "ally": {"pick": ["hunter_of(town)"]}, "taken": {"pick": ["survivor_of(town)"]},
                  "carter": {"pick": ["carter_of(town)", "survivor_of(town)"]},
                  "suspect": {"pick": ["suspect_of(town)", "notable_of(town)"]},
                  "waker": {"pick": ["band(cultists)"]}, "rider": {"pick": ["band(bandits)"]},
                  "innocent": {"pick": ["settlement(town)"]}}
    words = {"title": ["One", "First"], "goal": ["Do it."], "opening": ["a", "b", "c"], "reveal": ["x", "y", "z"]}
    bp["chapters"] = [
        dict(words, id="taken", need="all", steps=[
            {"kind": "rescue", "who": "taken", "at": "home.level(1)", "gives": ["flag:freed"]},
            {"kind": "defeat", "who": "waker", "at": "road"},
            {"kind": "capture", "who": "rider", "at": "road", "gives": ["clue:inside"]}]),
        dict(words, id="binds", need="all", steps=[
            {"kind": "fetch", "what": "the crown of {villain_short}", "base": "gold_ring", "at": "home.level(1)"},
            {"kind": "recruit", "who": "ally", "check": ["persuasion", 10], "gives": ["flag:ally_won"]},
            {"kind": "rally", "at": "town"},
            {"kind": "confront", "who": "suspect", "clue": "inside"},
            {"kind": "escort", "who": "carter", "to": "dest", "ambush": "bandits"}]),
        dict(words, id="night", need="all", steps=[
            {"kind": "hold", "at": "town", "group": "restless_dead", "waves": 2, "days": [1, 1],
             "fails_to": "town_fell"},
            {"kind": "rite", "at": "home", "needs": ["key:militia"], "gives": ["flag:laid"]},
            {"kind": "finale", "at": "home.deepest"}]),
    ]
    return bp


@pytest.fixture
def tale(made, tables, monkeypatch):
    w = copy.deepcopy(made)
    risen = [t for t in threats.records(w).values() if t["kind"] == "risen" and t["state"] != "ended"]
    assert risen, "this world has a risen king"
    t = risen[0]
    town = min((s for s in w.settlements if s.kind in ("town", "village")),
               key=lambda s: threats.distance(w, t, s.x, s.y))
    game = new_game(w, tables, start_settlement=town.id)
    game.survival = False
    monkeypatch.setitem(tables.adventures["blueprints"], "test_dead", _blueprint(tables))
    monkeypatch.setitem(tables.threats["kinds"]["risen"], "blueprints", ["test_dead"])
    monkeypatch.setattr(camp, "check", lambda game, skill, dc, **kw: (True, f"{skill} check: success"))
    t = threats.records(game.world)[t["id"]]
    if t["state"] == "dormant":
        threats.stir(game.world, tables, t, game.world.rng, day=0)
    for line in story.take_hook(game, t["id"]):
        assert "too late" not in line and "Nobody" not in line, line
    adv = story.active(game)[0]
    beats.director(game.world)["card"] = None
    return game, adv, t


def _stand(game, place):
    game.player.x, game.player.y = places.xy(game.world, place)


def _down_to(game, place, level):
    site = game.world.sites[place["site"]]
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    dungeon.descend(game, 1)
    while int(game.local.meta.get("level", 1)) < level:
        dungeon.descend(game, int(game.local.meta["level"]) + 1)


def _step(adv, sid):
    return next(s for ch in adv["chapters"] for s in ch["steps"] if s["id"] == sid)


def _talk(game, who, cid):
    conv = Conversation(game, who)
    choice = next((c for c in conv.menu() if c.id == cid), None)
    assert choice is not None, [c.id for c in conv.menu()]
    conv.choose(choice)
    return conv


def test_a_tale_of_part_d_s_steps_from_rescue_to_the_rite(tale, tables, monkeypatch):
    game, adv, t = tale
    w = game.world
    # I. The rescue (a step quest: the captive on the barrow's first level), the waker slain, the rider taken.
    rescue = _step(adv, "taken.1")
    q = quests.by_id(game, rescue["quest"])
    assert q is not None and q["adventure"] == adv["id"] and q["target"]["level"] == 1 and q["reward"] == 0
    _down_to(game, adv["places"]["home"], 1)
    spot = next(xy for xy, f in game.local.features.items() if f.get("kind") == "captive")
    quests.free_captive(game, game.local, *spot)
    assert rescue["state"] == "done" and "freed" in adv["flags"] and q["state"] == "finished"
    game.player.local_key = None  # (back up on the land)
    _stand(game, adv["places"]["road"])
    assert story.on_arrive(game) and game.encounter is not None
    band = game.encounter.creatures
    assert band[0].story["role"] in ("waker", "rider") and band[0].story["adv"] == adv["id"]
    first = band[0].story["role"]
    game.encounter = None
    story.on_battle(game, SimpleNamespace(outcome="victory", dead=list(band), captives=[], fled=[]))
    sid = "taken.2" if first == "waker" else "taken.3"
    if first == "waker":
        assert _step(adv, sid)["state"] == "done" and "waker_slain" in adv["flags"]
    else:
        assert _step(adv, sid)["state"] == "failed", "a capture's foe killed: the step fails, the tale goes on"
    beats.director(w)["day"] = -1
    game.world.time += 1440
    assert story.on_arrive(game) and game.encounter is not None, "the other band waits on the road too"
    other = game.encounter.creatures
    game.encounter = None
    if other[0].story["role"] == "rider":
        game.aftermath = SimpleNamespace(fates={}, loot=[], money=0)
        story.on_battle(game, SimpleNamespace(outcome="victory", dead=list(other[1:]), captives=[other[0]], fled=[]))
        from realmwalker.game import fight

        text = fight.decide_captive(game, other[0], "interrogate")
        assert "talks" in text or text
        assert _step(adv, "taken.3")["state"] == "done" and "rider_interrogate" in adv["flags"]
    else:
        story.on_battle(game, SimpleNamespace(outcome="victory", dead=list(other), captives=[], fled=[]))
    assert adv["chapter"] == 1, [s["state"] for s in adv["chapters"][0]["steps"]]
    beats.director(w)["card"] = None

    # II. The crown fetched (its chest on the first level), the ally won, the militia raised, the suspect confronted,
    # the carter walked to the next town through the gang's ambush.
    fetch = _step(adv, "binds.1")
    fq = quests.by_id(game, fetch["quest"])
    assert fq is not None and fq["template"] == "retrieve" and fq["target"]["tag"] == fetch["target"]["tag"]
    lm = w.local_maps.get(f"{w.sites[adv['places']['home']['site']].x},{w.sites[adv['places']['home']['site']].y}/1")
    _stand(game, adv["places"]["home"])
    quests.on_arrive_dungeon(game, lm)
    chest = next(f for f in lm.features.values() if f.get("quest") == fq["id"])
    items = quests.on_chest(game, chest)
    assert items and fetch["target"]["tag"] in items[0].tags and fetch["state"] == "done"
    town = w.settlements[adv["places"]["town"]["settlement"]]
    prepare_town(game, town)
    ally = cast.person(w, adv["cast"]["ally"])
    monkeypatch.setattr(Conversation, "check", lambda self, skill, dc: (True, f"({skill}: success)"))
    _talk(game, ally, "story_recruit")
    assert "ally" in adv["keys"] and _step(adv, "binds.2")["state"] == "done"
    headman = next(n for n in (w.npcs[i] for i in w.towns[town.id].npcs) if n.alive and n.notable)
    _talk(game, headman, "story_rally")
    assert "militia" in adv["keys"]
    suspect = cast.person(w, adv["cast"]["suspect"])
    if "inside" not in adv.get("clues", {}):
        beats.OPS["clue"](game, {"adv": adv["id"]}, "inside")
    _talk(game, suspect, "story_confront")
    assert "suspect_yielded" in adv["flags"]
    carter = cast.person(w, adv["cast"]["carter"])
    _talk(game, carter, "story_escort")
    esc = _step(adv, "binds.5")
    eq = quests.by_id(game, esc["quest"])
    assert eq["template"] == "escort" and carter.flags.get("escort") == eq["id"]
    road = places.xy(w, adv["places"]["road"])
    game.player.x, game.player.y = road
    if max(abs(road[0] - town.x), abs(road[1] - town.y)) >= 3:
        assert deeds.on_travel(game) and game.encounter is not None and esc.get("ambushed")
        game.encounter = None
    dest = w.settlements[adv["places"]["dest"]["settlement"]]
    game.player.x, game.player.y = dest.x, dest.y
    quests.on_arrive(game)
    assert esc["state"] == "done", "the escort is done when they are there"
    assert adv["chapter"] == 2, [s["state"] for s in adv["chapters"][1]["steps"]]
    beats.director(w)["card"] = None

    # III. The night: the waves at the town, one after another, then the rite at the barrow.
    hold = _step(adv, "night.1")
    night = int(hold["target"]["night"])
    assert night == int(game.moment.total_days) + 1 and any("night" in str(j) for j in adv["journal"])
    game.world.time += 1440 * 2
    _stand(game, adv["places"]["town"])
    assert story.on_arrive(game) and game.encounter is not None and hold["wave"] == 1
    wave = game.encounter.creatures
    assert all(c.story["role"] == "wave" for c in wave)
    game.encounter = None
    story.on_battle(game, SimpleNamespace(outcome="victory", dead=list(wave), captives=[], fled=[]))
    assert game.encounter is not None and hold["wave"] == 2, "the next wave comes with no rest between"
    wave = game.encounter.creatures
    game.encounter = None
    story.on_battle(game, SimpleNamespace(outcome="victory", dead=list(wave), captives=[], fled=[]))
    assert hold["state"] == "done"
    _stand(game, adv["places"]["home"])
    story.on_arrive(game)
    assert _step(adv, "night.2")["state"] == "done" and "laid" in adv["flags"]


def test_a_missed_night_fails_its_step_and_leaves_its_codeword(tale):
    game, adv, t = tale
    for ch in adv["chapters"][:2]:
        for st in ch["steps"]:
            st["state"] = "done"
        ch["state"] = "done"
    adv["chapter"] = 2
    adv["chapters"][2]["state"] = "open"
    deeds.setup(game, adv)
    hold = _step(adv, "night.1")
    assert hold["target"].get("night") is not None
    game.world.time += 1440 * 4
    beats.director(game.world)["day"] = -1
    story.daily(game)
    assert hold["state"] == "failed" and "town_fell" in adv["flags"]


def test_the_test_tale_passes_the_start_up_check(tables, monkeypatch):
    from realmwalker.game.story import check
    from realmwalker.game.story.steps import STEPS

    assert all(kind in STEPS for kind in deeds.KINDS)
    monkeypatch.setitem(tables.adventures["blueprints"], "test_dead", _blueprint(tables))
    assert check.problems(tables) == []
