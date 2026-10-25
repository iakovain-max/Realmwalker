"""Vignettes (Expansion 6 C.9, docs/ADVENTURES.md §5.16, §6.11): hand-made situations, each needing particular things
in the world, met once a world, seldom, in their own scenes."""

import pytest

from realmwalker.game import townlife
from realmwalker.game.people import prepare_town
from realmwalker.game.story import check, goals, situations, stage, vignettes
from realmwalker.world import marks
from realmwalker.world.tables import Tables
from tests.test_first_hour import SEEDS, a_life
from tests.test_situations import talk


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def peopled(game, n: int = 16) -> list:
    """The towns nearest the hero, peopled now."""
    w = game.world
    here = (game.player.x, game.player.y)
    towns = sorted(w.settlements, key=lambda s: (abs(s.x - here[0]) + abs(s.y - here[1]), s.id))[:n]
    for s in towns:
        prepare_town(game, s)
    return towns


def forged(game, vid: str):
    """The vignette forged in the first peopled town whose need holds, the hero standing in that town's streets."""
    for s in peopled(game):
        sit = situations.make(game, s.id, predicament=vid)
        if sit is not None:
            if game.in_local:
                game.leave_local()
            game.player.x, game.player.y = s.x, s.y
            game.player.local_key = None
            game.enter_local()
            return sit, s
    pytest.skip(f"{vid}'s need finds nothing in this world")


def test_the_data_reads_right(tables):
    assert [p for p in check.problems(tables) if "vignette" in p or "situations" in p] == []
    vs = vignettes.vignettes(tables)
    assert len(vs) == 20, "the first twenty hand-made vignettes of §6.11"
    assert len({v["vignette"]["needs"] for v in vs.values()}) == 20, "each needs its own particular things"
    meets = tables.situations["meetings"]
    for vid, v in vs.items():
        assert {e["tone"] for e in v["endings"]} | {v["lapse"]["tone"]} & {"mixed", "bitter"}, vid
        for m in v["meetings"]:
            assert m.startswith("v_") and meets[m]["scene"] in tables.scenes, f"{vid} meets in its own scene"
        assert len(v["words"]["plea"]) >= 2 and len(v["words"]["title"]) >= 2, vid
    roots = tables.situations["roots"]
    assert not any(vid in lst for lst in roots.values() for vid in vs), "never forged from the ordinary roots"


@pytest.mark.slow
def test_every_vignette_is_found_in_the_world_and_fills_its_words(tables):
    found = set()
    for seed in SEEDS:
        townlife.forget()
        game, town = a_life(tables, seed)
        towns = peopled(game)
        for vid in vignettes.vignettes(tables):
            if vid in found:
                continue
            for s in towns:
                sit = situations.make(game, s.id, predicament=vid)
                if sit is None:
                    continue
                found.add(vid)
                assert sit["root"]["kind"] == "vignette" and sit["root"]["vignette"] == vid
                for role, rec in sit["roles"].items():
                    if rec.get("npc") is not None:
                        assert game.world.npcs[rec["npc"]].flags["story"] == {"sit": sit["id"], "role": role}
                for key in ("title", "plea", "first", "stakes"):
                    assert sit["words"][key] and "{" not in sit["words"][key], (vid, key, sit["words"][key])
                assert vignettes.find(game, s, vid) is None, "once a world"
                situations._unbind(game, sit)
                sit["state"] = "done"
                break
    missing = set(vignettes.vignettes(tables)) - found
    assert len(missing) <= 2, f"almost every vignette's need is met somewhere in two small worlds: {missing}"


@pytest.mark.slow
def test_every_vignette_is_met_in_its_own_scene_and_taken(tables, monkeypatch):
    monkeypatch.setattr(situations, "maybe_forge", lambda game, s=None: None)  # (no ordinary trouble in the way)
    met = set()
    for seed in SEEDS:
        townlife.forget()
        game, town = a_life(tables, seed)
        for vid in sorted(vignettes.vignettes(tables)):
            if vid in met:
                continue
            for s in peopled(game):
                sit = situations.make(game, s.id, predicament=vid)
                if sit is None:
                    continue
                if game.in_local:
                    game.leave_local()
                game.player.x, game.player.y = s.x, s.y
                game.player.local_key = None
                game.enter_local()
                game.world.towns[s.id].flags.pop("scene_day", None)  # (a town stages one scene a day)
                if sit["state"] == "latent" and any(townlife.asleep(game, game.world.npcs[i])
                                                    for i in situations._meet_cast(game, sit).values()):
                    situations._unbind(game, sit)  # (the meeting waits for them to wake: look elsewhere)
                    situations._undo(game, sit)
                    del situations.records(game.world)[sit["id"]]
                    continue
                assert situations._try_meet(game, s) or sit["state"] == "met", f"{vid}: its meeting plays in {s.name}"
                scene = situations.data(game)["meetings"][sit["meeting"]["kind"]]["scene"]
                assert stage.current(game)["id"] == scene and scene.startswith("vig_")
                stage.skip(game)
                asker = situations.asker(game, sit)
                assert game.talk_to == asker.id, f"{vid}: the one who asks comes to talk"
                talk(game, asker, "sit_take")
                assert sit["state"] == "taken", vid
                met.add(vid)
                situations._unbind(game, sit)
                sit["state"] = "done"
                break
    assert len(set(vignettes.vignettes(tables)) - met) <= 2, set(vignettes.vignettes(tables)) - met


def test_seldom_and_one_near_at_a_time(tables):
    townlife.forget()
    game, town = a_life(tables, SEEDS[0])
    towns = peopled(game)
    rng = game.world.rng.child("test")
    rules = game.tables.situations["vignettes"]
    old = dict(rules)
    try:
        rules["share"] = 0.0
        assert all(vignettes.roots(game, s, rng) == [] for s in towns), "only a share of forgings look for them"
        rules["share"] = 1.0
        s = next((s for s in towns if vignettes.roots(game, s, rng)), None)
        if s is None:
            pytest.skip("no vignette's need is met near this hero")
        root = vignettes.roots(game, s, rng)[0]
        sit = situations.make(game, s.id, root=root, predicament=root["vignette"])
        assert sit is not None and sit["predicament"] == root["vignette"]
        assert all(vignettes.roots(game, x, rng) == [] for x in towns
                   if goals.within_reach(game, {"town": x.id})), "at most one live near the hero"
    finally:
        rules.clear()
        rules.update(old)


def test_a_vignette_is_forged_by_the_ordinary_way_when_its_need_holds(tables, monkeypatch):
    townlife.forget()
    game, town = a_life(tables, SEEDS[0])
    towns = peopled(game)
    monkeypatch.setitem(game.tables.situations["vignettes"], "share", 1.0)
    for kind in list(situations.ROOTS):
        if kind != "vignette":
            monkeypatch.setitem(situations.ROOTS, kind, lambda game, s, rng: [])
    for s in towns:
        game.world.towns[s.id].flags.pop("sit_next", None)
        game.player.x, game.player.y = s.x, s.y
        sit = situations.make(game, s.id)
        if sit is not None:
            assert vignettes.is_vignette(situations.spec_of(game, sit))
            return
    pytest.skip("no vignette's need is met near this hero")


def test_the_drowned_bell_is_met_in_its_own_scene_raised_and_remembered(tables):
    townlife.forget()
    game, town = a_life(tables, SEEDS[0])
    sit, s = forged(game, "v_drowned_bell")
    assert sit["words"]["water"] and sit["words"]["ruin_was"] in sit["words"]["plea"] + sit["words"]["first"]
    assert situations._try_meet(game, s)
    assert stage.current(game)["id"] == "vig_drowned_bell"
    stage.skip(game)
    keeper = situations.asker(game, sit)
    assert game.talk_to == keeper.id
    talk(game, keeper, "sit_take")
    q = next(q for q in game.quests if q.get("situation") == sit["id"])
    assert q["template"] == "retrieve" and q["target"]["site"] == sit["roles"]["ruin"]["site"], \
        "the work goes to the real ruin"
    sit["flags"].append("knows_night")
    situations.on_quest_end(game, q, True)
    assert sit["state"] == "done" and sit["ending"] == "raised_known"
    assert "memorial" in marks.marks_of(s), "the bell's memorial is a mark on the town"


def test_the_hanging_tree_lays_its_field(tables):
    townlife.forget()
    game, town = a_life(tables, SEEDS[0])
    sit, s = forged(game, "v_hanging_tree")
    i = sit["root"]["scar"]
    situations._op(game, sit, ["lay_scar"])
    assert game.world.politics["scars"][i]["laid"], "the field of the dead is laid for good"
    assert vignettes.NEEDS["gallows_scar"](game, s, game.world.rng.child("t")) is None or \
        vignettes.NEEDS["gallows_scar"](game, s, game.world.rng.child("t"))[2]["scar"] != i
