"""Situations (Expansion 6 C.6, docs/ADVENTURES.md §5.16, §6.7-6.10, §8.10): small stories about real people, forged
only in towns that have their people, met in a scene, taken on in a conversation, ended however the hero makes the
goals true, and ended by the world itself when the clock runs out."""

import pytest

from realmwalker.game import townlife
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.story import check, goals, situations, stage
from realmwalker.world.tables import Tables
from tests.test_first_hour import SEEDS, a_life


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture
def life(tables):
    townlife.forget()
    return a_life(tables, SEEDS[0])


def plain(tables) -> dict:
    """The predicaments forged from ordinary roots (not the hand-made vignettes, tests/test_vignettes.py, nor an
    adventure's steps, tests/test_inside.py)."""
    return {k: v for k, v in situations.predicaments(tables).items() if not v.get("vignette") and not v.get("inside")}


def watched_town(game):
    """A town with a watch (guards), peopled now, the hero standing at its gate."""
    w = game.world
    for s in sorted(w.settlements, key=lambda s: (abs(s.x - game.player.x) + abs(s.y - game.player.y), s.id)):
        if s.kind in ("town", "city"):
            prepare_town(game, s)
            if any(n.job == "guard" and n.alive for n in npcs_in(w, s.id)):
                stand_in(game, s)
                return s
    pytest.skip("no town with a watch in this world")


def stand_in(game, s) -> None:
    game.leave_local() if game.in_local else None
    game.player.x, game.player.y = s.x, s.y


def forced(game, town, pid):
    sit = situations.make(game, town.id, root={"kind": "town", "key": "town"}, predicament=pid)
    assert sit is not None, f"{pid} could not be forged in {town.name}"
    return sit


def talk(game, npc, cid, **data):
    """Talk to someone and pick the situation's choice `cid` (an act by its id in data)."""
    conv = Conversation(game, npc)
    opts = [c for c in conv.menu() if c.id == cid and all(c.data.get(k) == v for k, v in data.items())]
    assert opts, f"{npc.name} offers no {cid} {data}: {[(c.id, c.label) for c in conv.menu()]}"
    conv.choose(opts[0])
    conv.close()
    return conv


def test_the_data_reads_right(tables):
    probs = [p for p in check.problems(tables) if "situations" in p or "sit_" in p]
    assert probs == []
    preds = situations.predicaments(tables)
    assert len(plain(tables)) == 20, "the first twenty predicaments of §6.7 (besides the hand-made vignettes)"
    for pid, p in preds.items():
        tones = {e["tone"] for e in p["endings"]} | {p["lapse"]["tone"]}
        assert tones & {"mixed", "bitter"}, f"{pid}: every predicament has a bitter or mixed end"
    meets = {m for p in preds.values() for m in p["meetings"]}
    assert len(meets) >= 12, "twelve ways of meeting at least"
    assert len(tables.situations["turns"]) >= 12, "a first twelve turns"


def test_every_predicament_can_be_forged_from_the_world(tables):
    found = set()
    for seed in SEEDS:
        townlife.forget()
        game, town = a_life(tables, seed)
        try:
            towns = [town, watched_town(game)]
        except pytest.skip.Exception:
            towns = [town]
        for pid in plain(tables):
            if pid in found:
                continue
            for s in towns:
                sit = situations.make(game, s.id, root={"kind": "town", "key": "town"}, predicament=pid)
                if sit is None:
                    continue
                found.add(pid)
                for role, rec in sit["roles"].items():  # roles are bound to real people of the world
                    if rec.get("npc") is not None:
                        n = game.world.npcs[rec["npc"]]
                        assert n.alive and n.flags["story"] == {"sit": sit["id"], "role": role}
                assert sit["meeting"]["kind"] in tables.situations["meetings"]
                assert sit["words"]["title"] and sit["words"]["plea"] and "{" not in sit["words"]["plea"]
                situations._unbind(game, sit)
                sit["state"] = "done"
                break
    assert found == set(plain(tables)), set(plain(tables)) - found


def test_rarity_one_live_a_town_and_a_gap(life):
    game, town = life
    t = game.world.towns[town.id]
    t.flags.pop("sit_next", None)
    assert situations.due_here(game, town)
    sit = situations.maybe_forge(game, town)
    assert sit is not None and sit["town"] == town.id
    assert not situations.due_here(game, town), "one live situation a town"
    assert situations.maybe_forge(game, town) is None
    gap = int(t.flags["sit_next"]) - int(game.moment.total_days)
    assert 10 <= gap <= 20, "the next comes 10 to 20 days on"
    sit["state"] = "done"
    assert not situations.due_here(game, town), "and not before its gap has passed"
    t.flags["sit_next"] = int(game.moment.total_days)
    assert situations.due_here(game, town)


def test_at_most_three_live_within_reach(life):
    game, town = life
    sits = goals.situations(game.world)
    for i in range(3):
        sits[f"Qz{i}"] = {"id": f"Qz{i}", "town": town.id, "state": "met", "goals": [], "predicament": "x"}
    other = min((s for s in game.world.settlements if s.id != town.id),
                key=lambda s: max(abs(s.x - town.x), abs(s.y - town.y)))
    prepare_town(game, other)
    game.player.x, game.player.y = other.x, other.y
    game.world.towns[other.id].flags.pop("sit_next", None)
    assert not situations.due_here(game, other)


def test_forging_never_builds_a_town_map(life):
    game, town = life
    w = game.world
    far = next(s for s in w.settlements if s.id not in w.towns)
    before = set(w.local_maps)
    assert situations.make(game, far.id) is None, "a town that has no people yet gets none"
    assert set(w.local_maps) == before


def test_met_in_a_scene_then_taken_in_talk_with_work_for_its_real_target(life):
    game, town = life
    sit = situations.make(game, town.id, root={"kind": "town", "key": "town"}, predicament="gone_where_not")
    if sit is None:
        pytest.skip("no band near this town")
    assert game.in_local and stage.current(game) is None
    assert situations._try_meet(game, town), "the meeting plays as a scene on the town's map"
    rec = stage.current(game)
    assert rec["id"] == situations.data(game)["meetings"][sit["meeting"]["kind"]]["scene"]
    assert sit["state"] == "met" and sit["life"] == situations._life(game)
    assert situations.troubles(game) == [sit], "it is in the journal's Troubles"
    stage.skip(game)
    asker = situations.asker(game, sit)
    assert game.talk_to == asker.id, "the one who asks comes to talk"
    lost = situations._npc(game, sit, "lost")
    assert lost.flags.get("captive") and not lost.present, "the lost one is away with the band"
    talk(game, asker, "sit_take")
    assert sit["state"] == "taken"
    q = next(q for q in game.quests if q.get("situation") == sit["id"])
    assert q["template"] == "rescue" and q["target"]["npc"] == lost.id
    assert q["target"]["holder"] == sit["roles"]["band"]["faction"], "the work names the real band"
    # the captive freed (quests.free_captive's way) and led home
    lost.flags.pop("captive")
    lost.flags["with_party"] = True
    goals.notify(game, "captive", "force", npc=lost)
    game.leave_local()
    game.player.x, game.player.y = town.x, town.y
    goals.notify(game, "town")
    if sit["turn"] and sit["turn"]["id"] == "lost_unwilling":
        assert sit["state"] == "taken", "the lost one may not want to stay: not over yet"
        return
    assert sit["state"] == "done" and sit["ending"] == "home"
    assert lost.present and not lost.flags.get("with_party"), "home, in the streets again"
    assert any(f["from"] == asker.id for f in game.renown.legend.get("favours", [])), "a favour kept"
    assert not asker.flags.get("story"), "the people are let go"


def test_an_act_with_a_price_ends_it_and_the_ending_knows_the_way(life):
    game, town = life
    sit = forced(game, town, "promise_unkept")
    situations.met(game, sit)
    asker, creditor = situations.asker(game, sit), situations._npc(game, sit, "creditor")
    talk(game, asker, "sit_take")
    game.leader.money = 10000
    talk(game, creditor, "sit_act", act="pay")
    assert game.leader.money == 7000
    assert sit["state"] == "done" and sit["ending"] == "kept_paid"
    assert goals.way_used(sit, "pay")


def test_a_failed_haggle_costs_nothing(life):
    game, town = life
    sit = forced(game, town, "precious_wrong_hands")
    situations.met(game, sit)
    holder = situations._npc(game, sit, "holder")
    assert any(f"story:{sit['id']}" in it.tags for it in holder.inventory), "the heirloom is in the holder's pocket"
    talk(game, situations.asker(game, sit), "sit_take")
    game.leader.money = 10000
    conv = Conversation(game, holder)
    conv.check = lambda skill, dc: (False, "(failed)")
    haggle = next(c for c in conv.menu() if c.id == "sit_act" and c.data["act"] == "haggle")
    conv.choose(haggle)
    assert game.leader.money == 10000
    talk(game, holder, "sit_act", act="buy")
    assert any(f"story:{sit['id']}" in it.tags for c in game.party for it in c.inventory), "the hero has it now"
    talk(game, situations.asker(game, sit), "sit_act", act="give")
    assert sit["state"] == "done" and sit["ending"] == "bought", "bought back dear"


def test_the_clock_runs_out_and_the_world_has_its_own_outcome(life):
    game, _ = life
    town = watched_town(game)
    sit = forced(game, town, "innocent_accused")
    accused = situations._npc(game, sit, "accused")
    assert accused.flags["law"] == "accused"
    sit["clock"]["due"] = int(game.moment.total_days)
    situations.daily(game)
    assert sit["state"] == "lapsed"
    assert not accused.alive and accused.flags["law"] == "hanged", "they hanged the innocent"
    lm = goals._town_map(game, town.id)
    assert any(g["who"] == {"npc": accused.id} for g in lm.meta.get("graves", [])), "and the grave is there to see"


def test_the_law_way_through(life):
    game, _ = life
    town = watched_town(game)
    sit = forced(game, town, "innocent_accused")
    situations.met(game, sit)
    talk(game, situations.asker(game, sit), "sit_take")
    culprit, judge = situations._npc(game, sit, "culprit"), situations._npc(game, sit, "judge")
    conv = Conversation(game, culprit)
    conv.check = lambda skill, dc: (True, "(passed)")
    conv.choose(next(c for c in conv.menu() if c.id == "sit_act" and c.data["act"] == "catch"))
    conv.close()
    assert "knows_culprit" in sit["flags"]
    talk(game, judge, "sit_act", act="proof")
    assert sit["state"] == "done" and sit["ending"] == "freed"
    assert culprit.flags["law"] == "accused"
    assert goals.way_used(sit, "law")


def test_a_spell_lifts_a_curse(life):
    game, town = life
    sit = forced(game, town, "curse_on_house")
    situations.met(game, sit)
    talk(game, situations.asker(game, sit), "sit_take")
    game.leave_local() if game.in_local else None
    game.player.x, game.player.y = town.x, town.y
    lines = situations.on_magic(game, "remove_curse")
    assert lines
    goals.notify(game, "magic")
    assert sit["state"] == "done" and sit["ending"] == "lifted"
    assert goals.way_used(sit, "magic")


def test_refusing_is_a_way_too(life):
    game, town = life
    sit = forced(game, town, "ruler_needs")
    situations.met(game, sit)
    talk(game, situations.asker(game, sit), "sit_refuse")
    assert sit["state"] == "failed" and sit["ending"] == "refused", "refused, and remembered"


def test_a_story_person_takes_the_place_of_the_generated_one(life):
    game, town = life
    sit = forced(game, town, "ruler_needs")
    rec = sit["roles"]["envoy_to"]
    w = game.world
    dest = w.settlements[rec["settlement"]]
    if rec.get("npc") is None:
        assert any(r.get("sit") == sit["id"] for r in w.politics["story_people"][f"S{dest.id}"])
        prepare_town(game, dest)
        rec = sit["roles"]["envoy_to"]
    n = w.npcs[rec["npc"]]
    assert n.settlement == dest.id and n.job in ("lord", "headman", "elder")
    same = [x for x in npcs_in(w, dest.id) if x.job == n.job]
    assert len(same) == len({x.id for x in same}), "never two of one office for the story's sake"


def test_a_turn_fires_when_its_time_comes(life):
    game, town = life
    sit = forced(game, town, "promise_unkept")
    sit["turn"] = {"id": "clock_shorter", "state": "hidden"}
    sit["clock"]["due"] = int(game.moment.total_days) + 12
    situations.met(game, sit)
    assert sit["turn"]["state"] == "hidden"
    talk(game, situations.asker(game, sit), "sit_take")
    assert sit["turn"]["state"] == "fired"
    assert sit["clock"]["due"] - int(game.moment.total_days) == 6


def test_when_the_hero_dies_their_troubles_wait_for_the_next(life):
    from realmwalker.game import story

    game, town = life
    sit = situations.make(game, town.id, root={"kind": "town", "key": "town"}, predicament="gone_where_not")
    if sit is None:
        pytest.skip("no band near this town")
    situations.met(game, sit)
    talk(game, situations.asker(game, sit), "sit_take")
    assert sit["quest"] is not None
    due = sit["clock"]["due"]
    story.on_death(game)
    assert sit["state"] == "latent" and sit["quest"] is None and sit["life"] is None
    assert sit["meeting"]["state"] == "waiting" and sit["clock"]["due"] == due


def test_the_journal_shows_troubles(life, make_app):
    from realmwalker.ui.screens.journal import ADVENTURES, JournalScreen

    game, town = life
    sit = forced(game, town, "promise_unkept")
    situations.met(game, sit)
    text = situations.journal_lines(game, sit)
    assert situations.title(game, sit) in text and "At stake" in text
    app = make_app()
    screen = JournalScreen(app, game)
    assert screen.tab == ADVENTURES
    assert ("quest", sit) in screen.rows()


def test_forging_is_quick(life):
    import time

    game, town = life
    t0 = time.perf_counter()
    n = 0
    for _ in range(10):
        sit = situations.make(game, town.id)
        if sit is not None:
            n += 1
            situations._unbind(game, sit)
            sit["state"] = "done"
    if n:
        assert (time.perf_counter() - t0) / n < 0.05, "a situation is forged in a few milliseconds"


def test_a_failed_check_may_be_tried_again_the_next_day(life):
    game, town = life
    sit = forced(game, town, "promise_unkept")
    situations.met(game, sit)
    talk(game, situations.asker(game, sit), "sit_take")
    creditor = situations._npc(game, sit, "creditor")
    conv = Conversation(game, creditor)
    conv.check = lambda skill, dc: (False, "(failed)")
    conv.choose(next(c for c in conv.menu() if c.id == "sit_act" and c.data["act"] == "wait"))
    assert not any(c.data.get("act") == "wait" for c in Conversation(game, creditor).menu())
    sit["tried"] = {k: v - 1 for k, v in sit["tried"].items()}  # (a day later)
    assert any(c.data.get("act") == "wait" for c in Conversation(game, creditor).menu())


def test_the_heirloom_in_the_pocket_is_the_one_in_the_words(life):
    game, town = life
    sit = forced(game, town, "precious_wrong_hands")
    holder = situations._npc(game, sit, "holder")
    it = next(i for i in holder.inventory if f"story:{sit['id']}" in i.tags)
    assert it.name == sit["words"]["heirloom"]
    assert not sit["words"]["heirloom"].startswith("The "), "a kept name keeps its own small letter"


def test_an_ending_is_played_once(life):
    game, town = life
    sit = forced(game, town, "blood_owed")
    situations.met(game, sit)
    talk(game, situations.asker(game, sit), "sit_take")
    sit["clock"]["due"] = int(game.moment.total_days)
    situations.daily(game)
    assert sit["state"] == "lapsed"
    assert sit["ending"] == "lapsed"
    marked = situations._npc(game, sit, "marked")
    lm = goals._town_map(game, town.id)
    assert sum(g["who"] == {"npc": marked.id} for g in lm.meta.get("graves", [])) == 1, "one grave, not two"
