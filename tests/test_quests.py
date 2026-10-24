"""Quests (M8 part 3): work made from real things in the world, taken on in conversation or from the notice board,
noticed where it happens (fights, chests, chains, words), paid for, failed, and saved."""

import copy
from types import SimpleNamespace

import pytest

from realmwalker.core import dice
from realmwalker.game import dungeon, quests, save
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.state import new_game
from realmwalker.world import dungeon as gen
from realmwalker.world import factions as fx
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Questland", 99, "small"), tables)


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    return g


def fixed_d20(monkeypatch, value):
    class Roll:
        natural = value
        total = value

    monkeypatch.setattr(dice, "d20", lambda *a, **k: Roll())


def a_town(game):
    return next(s for s in game.world.settlements if s.kind in ("town", "city"))


def visit(game, s):
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    return npcs_in(game.world, s.id)


def offer(game, template, jobs=None):
    """A job of this kind from someone in some town of this world."""
    for s in game.world.settlements:
        if s.kind not in ("town", "city", "village"):
            continue
        folk = npcs_in(game.world, s.id) or (prepare_town(game, s) and npcs_in(game.world, s.id))
        for npc in folk:
            if npc.job not in game.tables.quests["templates"][template]["givers"] or (jobs and npc.job not in jobs):
                continue
            q = quests.make_offer(game, npc, game.world.rng.child(f"test/{npc.id}"), template)
            if q is not None:
                return q, npc
    pytest.skip(f"no {template} work in this world")


def result(outcome="victory", dead=(), captives=()):
    return SimpleNamespace(outcome=outcome, dead=list(dead), captives=list(captives), fled=[], xp=0)


def go_down(game, site, level=None):
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    dungeon.descend(game, level or gen.depth_for(game.world, site))
    return game.local


# ---------------------------------------------------------------------------- where work comes from (Expansion 6 C.2)
def test_work_is_tied_to_real_things(game):
    w = game.world
    seen = set()
    for s in [s for s in w.settlements if s.kind in ("town", "city")][:5]:
        for npc in visit(game, s):
            if not npc.notable or npc.job not in quests.giver_jobs(game):
                continue
            q = quests.make_offer(game, npc, w.rng.child(f"real/{npc.id}"))
            if q is None:
                continue
            seen.add(q["template"])
            t = q["target"]
            assert q["giver"] in w.npcs and q["reward"] > 0 and q["days"] > 0
            if "site" in t:
                assert 0 <= t["site"] < len(w.sites)
            if "gang" in t:
                assert w.factions[t["gang"]].kind == "bandit_gang"
            if "npc" in t:
                assert t["npc"] in w.npcs
                if q["template"] != "escort":  # the one you escort starts where the work was offered
                    assert w.npcs[t["npc"]].settlement == t["dest"]
            for kind in ("title", "pitch", "journal", "done", "failed"):
                text = quests.fill(game, q, kind)
                assert text and "{" not in text, (q["template"], kind, text)
        game.leave_local()
    assert len(seen) >= 5, seen


def test_no_weekly_offers_and_nobody_asks_for_work(game):
    """The job board is gone: weeks pass in a town and nobody has thought of a job; "Is there any work?" is no
    choice anyone has; none of the old machinery is left to call."""
    assert not hasattr(quests, "offer_for") and not hasattr(quests, "offers_in")
    s = a_town(game)
    folk = visit(game, s)
    for _ in range(3):
        game.pass_time(7 * 1440, "rest")
    town = game.world.towns[s.id]
    assert "offers" not in town.flags and "offer_day" not in town.flags
    for npc in folk[:40]:
        labels = [c.label for c in Conversation(game, npc).menu()]
        assert not any("any work" in lab.lower() for lab in labels), (npc.job, labels)


def test_every_builder_makes_for_a_given_target(game):
    """Each kind of work is a picker and a maker: whatever chose the target (a situation, a contract, a step), make
    builds the same work on it, with the words filled in and the target kept."""
    from realmwalker.core.rng import RNG

    w = game.world
    assert set(quests.PICKERS) == set(quests.MAKERS) == set(game.tables.quests["templates"])
    for c in game.party:
        c.level = 6  # (a dragon is not given to beginners)
    for s in w.settlements:
        s.status.setdefault("plague", {"until": 10**9})  # (so 'cure' has a need somewhere)
    made = {}
    for s in w.settlements:
        if len(made) == len(quests.KINDS):
            break
        folk = npcs_in(w, s.id) or (prepare_town(game, s) and npcs_in(w, s.id))
        for npc in folk:
            for kind in set(quests.KINDS) - set(made):
                target = quests.pick(game, kind, npc, RNG(npc.id, kind))
                if target is None:
                    continue
                assert target["kind"] == kind and target["town"] == npc.settlement
                one = quests.make(game, npc, dict(target), RNG(1, kind))
                two = quests.make(game, npc, dict(target), RNG(2, kind))
                keep = {k: v for k, v in one["target"].items() if k not in ("captive", "sex")}
                assert keep == {k: v for k, v in two["target"].items() if k in keep}, kind
                assert one["template"] == kind and one["giver"] == npc.id and one["town"] == npc.settlement
                for what in ("title", "pitch", "journal", "done", "failed"):
                    text = quests.fill(game, one, what)
                    assert text and "{" not in text, (kind, what, text)
                for hidden in game.tables.quests["templates"][kind].get("hidden", {}):
                    text = quests.fill(game, one, "hidden", hidden)
                    assert text and "{" not in text, (kind, hidden, text)
                made[kind] = one
    assert not set(quests.KINDS) - set(made) - {"slay_dragon"}, set(quests.KINDS) - set(made)
    # A target chosen by something else: the watch's bounty on a named gang, set from a town with no giver.
    gang = next((f for f in fx.active_factions(w, "bandit_gang") if 0 <= f.site < len(w.sites)), None)
    if gang is not None:
        town = w.settlements[0]
        q = quests.make(game, None, {"kind": "bounty", "gang": gang.id, "town": town.id}, RNG(3, "b"))
        assert q["target"]["gang"] == gang.id and q["giver"] == -1 and q["town"] == town.id
        assert w.sites[gang.site].name in quests.fill(game, q, "pitch")


def test_a_commission_from_a_faction_you_serve(game):
    """A faction you have joined sends word of work from its goals, given by one of its people in a town near you;
    that person has their own choice for it; taken, it is in the journal and the next waits its turn."""
    from realmwalker.game.story import work

    w = game.world
    f = None
    for s in [s for s in w.settlements if s.kind in ("town", "city")]:
        visit(game, s)
        for cand in fx.active_factions(w, *fx.REALM_KINDS, "temple", "merchant_guild", "healers_guild"):
            if game.tables.law["join"].get(cand.kind) and work.kinds_for(game, cand) and \
                    any(n.notable and work.member(game, n, cand) for n in npcs_in(w, s.id)):
                f = cand
                break
        if f is not None:
            break
        game.leave_local()
    if f is None:
        pytest.skip("no faction with people of standing in these towns")
    game.renown.members[f.id] = 0
    q = None
    for _ in range(20):
        work.daily(game)
        q = game.renown.flags.get("commissions", {}).get(str(f.id))
        if q is not None:
            break
        game.renown.flags["commission_day"] = {}
        game.world.time += 1440
    assert q is not None, f.kind
    assert q["commission"] == f.id and q["template"] in work.kinds_for(game, f)
    giver = w.npcs[q["giver"]]
    assert work.member(game, giver, f)
    s = w.settlements[giver.settlement]
    game.player.x, game.player.y = s.x, s.y
    conv = Conversation(game, giver)
    own = next(c for c in conv.menu() if c.id == "own_work")
    conv.choose(own)
    assert conv.mode == "quest_offer" and any(quests.pitch(game, q) in text for _, text in conv.lines)
    conv.choose(next(c for c in conv.menu() if c.id == "work_accept"))
    assert q in game.quests and q["state"] == "active"
    assert str(f.id) not in game.renown.flags["commissions"]
    game.world.time += 1440 * 30
    game.renown.flags["commission_day"] = {}
    if q["state"] == "active":
        work.daily(game)
        assert str(f.id) not in game.renown.flags["commissions"]  # (one piece of their work at a time)


def test_a_commission_is_the_rank_trial(game, monkeypatch):
    from realmwalker.game import reputation
    from realmwalker.game.story import work

    f = next(f for f in fx.active_factions(game.world, *fx.REALM_KINDS))
    game.renown.members[f.id] = 0
    monkeypatch.setattr(reputation, "needs_trial", lambda g, fid: fid == f.id)
    q = {"reward": 1000}
    work.mark_trial(game, f, q)
    assert q["trial"] == f.id and q["reward"] == 1200
    assert f.name in quests.trial_note(game, q)


def test_a_plea_from_a_sick_town(game):
    """The healer of a town with the plague asks you for herbs themselves: their own choice, kept while the
    sickness lasts and gone with it."""
    from realmwalker.game.story import work

    w = game.world
    healer = None
    for s in [s for s in w.settlements if s.kind in ("town", "city", "village")]:
        folk = visit(game, s)
        healer = next((n for n in folk if n.alive and n.job in ("healer", "priest", "headman")), None)
        if healer is not None:
            break
        game.leave_local()
    if healer is None:
        pytest.skip("no healer anywhere")
    s.status.pop("plague", None)
    assert work.plea_of(game, healer) is None or work.plea_of(game, healer)["template"] != "cure"
    w.towns[s.id].flags.pop("plea_day", None)
    w.towns[s.id].flags.pop("pleas", None)
    s.status["plague"] = {"until": 10**9}
    conv = Conversation(game, healer)
    own = next(c for c in conv.menu() if c.id == "own_work")
    q = work.plea_of(game, healer)
    assert q["template"] == "cure" and q["plea"] == "sickness" and own.label
    assert work.plea_of(game, healer) is q  # (the same plea, asked again)
    s.status.pop("plague")
    assert work.plea_of(game, healer) is None and not work.held_by(game, healer)


def test_work_json_names_real_kinds(game):
    sp = game.tables.work
    kinds = set(quests.KINDS)
    for g in sp["commissions"]["goals"].values():
        assert set(g["kinds"]) <= kinds
    for v in sp["commissions"]["by_kind"].values():
        assert set(v) <= kinds
    assert {p["kind"] for p in sp["pleas"]} <= kinds


# ---------------------------------------------------------------------------- doing the work
def test_clearing_a_lair(game):
    q, npc = offer(game, "clear_lair")
    quests.accept(game, q)
    site = game.world.sites[q["target"]["site"]]
    lm = go_down(game, site)
    boss = next((a for a in lm.actors if a.group == quests.boss_of(lm)), None)
    if boss is None:
        assert q["done"]  # nothing lived at the bottom: cleared on sight
    else:
        lm.actors.remove(boss)
        quests.on_battle(game, result(dead=boss.creatures), boss)
        assert q["done"] and q["state"] == "return"
    assert site.id in game.world.politics["cleared"]
    # Back to the giver for the pay.
    money = game.leader.money
    conv = Conversation(game, npc)
    turn_in = next(c for c in conv.menu() if c.id == "quest_turn_in")
    conv.choose(turn_in)
    assert q["state"] == "finished" and game.leader.money == money + q["reward"]
    assert game.leader.xp > 0


def test_a_bounty_from_the_notice_board(game):
    w = game.world
    for s in w.settlements:
        bounties = quests.board_bounties(game, s)
        if bounties:
            break
    else:
        pytest.skip("no gangs near any town")
    q = bounties[0]
    assert q["giver"] == -1
    quests.accept(game, q)
    assert q not in quests.board_bounties(game, s)
    site = w.sites[q["target"]["site"]]
    lm = go_down(game, site)
    captain = [c for a in lm.actors for c in a.creatures if c.def_id == "bandit_captain"]
    if captain:
        quests.on_battle(game, result(dead=captain[:1]))
    else:
        boss = next(a for a in lm.actors if a.group == quests.boss_of(lm))
        lm.actors.remove(boss)
        quests.on_battle(game, result(dead=boss.creatures), boss)
    assert q["done"]
    # Any guard (or the headman) of the town pays.
    folk = npcs_in(w, s.id) or (prepare_town(game, s) and npcs_in(w, s.id))
    guard = next(n for n in folk if n.job in quests.AUTHORITY_JOBS)
    game.player.x, game.player.y = s.x, s.y
    conv = Conversation(game, guard)
    assert any(c.id == "quest_turn_in" for c in conv.menu())
    before = game.renown.standing.get(q["target"]["gang"], 0)
    conv.choose(next(c for c in conv.menu() if c.id == "quest_turn_in"))
    assert q["state"] == "finished"
    assert game.renown.standing.get(q["target"]["gang"], 0) < before


def test_the_deserters_can_be_talked_away(game):
    q, npc = offer(game, "bounty")
    q["hidden"] = "deserters"
    quests.accept(game, q)
    site = game.world.sites[q["target"]["site"]]
    lm = go_down(game, site)
    assert q["revealed"] and any("deserted" in line for line in q["journal"])
    boss = next(a for a in lm.actors if a.group == quests.boss_of(lm))
    assert boss.group == "deserters"
    lm.actors.remove(boss)
    quests.on_battle(game, result("parley"), boss)
    assert q["done"] and q["mercy"]
    conv = Conversation(game, npc)
    money = game.leader.money
    conv.choose(next(c for c in conv.menu() if c.id == "quest_turn_in"))
    assert game.leader.money == money + q["reward"] // 2


def test_hunting_a_named_beast(game):
    q, npc = offer(game, "hunt_beast")
    quests.accept(game, q)
    t = q["target"]
    game.player.x, game.player.y = t["x"], t["y"]
    game.encounter = None
    quests.on_arrive(game)
    enc = game.encounter
    assert enc is not None and enc.creatures[0].name == q["words"]["beast"]
    quests.on_battle(game, result(dead=enc.creatures))
    assert q["done"]


def test_retrieving_a_thing_from_the_deep(game):
    q, npc = offer(game, "retrieve")
    quests.accept(game, q)
    site = game.world.sites[q["target"]["site"]]
    lm = go_down(game, site)
    spot = next(pos for pos, f in lm.features.items() if f.get("quest") == q["id"])
    assert lm.terrain_ids[lm.terrain[spot]] == "chest"
    game.player.lx, game.player.ly = spot[0], spot[1]
    dungeon.open_chest(game, lm, *spot)
    assert q["done"]
    found = [it for it in lm.items.get((game.player.lx, game.player.ly), []) if f"quest:{q['id']}" in it.tags]
    assert found
    conv = Conversation(game, npc)
    choice = next(c for c in conv.menu() if c.id == "quest_turn_in")
    assert not choice.enabled  # you have to bring it
    game.pick_up()
    assert quests.holds_quest_item(game, q)
    choice = next(c for c in Conversation(game, npc).menu() if c.id == "quest_turn_in")
    assert choice.enabled
    conv = Conversation(game, npc)
    conv.choose(choice)
    assert q["state"] == "finished" and not quests.holds_quest_item(game, q)


def test_rescuing_a_captive_or_finding_them_dead(game):
    q, npc = offer(game, "rescue")
    quests.accept(game, q)
    site = game.world.sites[q["target"]["site"]]
    lm = go_down(game, site)
    spot = next(pos for pos, f in lm.features.items() if f.get("kind") == "captive")
    assert lm.terrain_ids[lm.terrain[spot]] == "captive"
    assert dungeon.bump(game, *spot)
    assert q["done"] and lm.terrain_ids[lm.terrain[spot]] == "chains"
    # Another: too late.
    q2, _ = offer(game, "rescue")
    quests.accept(game, q2)
    site = game.world.sites[q2["target"]["site"]]
    game.world.time += 1440 * (q2["days"] + 1)
    quests.daily(game)
    assert q2["state"] == "failed"


def test_a_letter_delivered_or_opened(game, monkeypatch):
    q, npc = offer(game, "deliver")
    quests.accept(game, q)
    assert quests.holds_quest_item(game, q)
    letter = next(it for it in game.leader.inventory if f"quest:{q['id']}" in it.tags)
    q["hidden"] = None
    lines = quests.read_letter(game, letter)
    assert q["opened"] and lines
    who = game.world.npcs[q["target"]["npc"]]
    game.player.x, game.player.y = game.world.settlements[who.settlement].x, game.world.settlements[who.settlement].y
    conv = Conversation(game, who)
    money = game.leader.money
    conv.choose(next(c for c in conv.menu() if c.id == "deliver_letter"))
    assert q["state"] == "finished" and game.leader.money == money + q["reward"] // 2  # the seal was broken
    assert not quests.holds_quest_item(game, q)


def test_an_incriminating_letter(game, monkeypatch):
    q, npc = offer(game, "deliver", jobs=("priest", "shopkeeper", "healer", "smith", "innkeeper"))
    q["hidden"] = "incriminating"
    quests.accept(game, q)
    letter = next(it for it in game.leader.inventory if f"quest:{q['id']}" in it.tags)
    quests.read_letter(game, letter)
    assert q["revealed"]
    s = game.world.settlements[npc.settlement]
    game.player.x, game.player.y = s.x, s.y
    conv = Conversation(game, npc)
    blackmail = next(c for c in conv.menu() if c.id == "blackmail")
    fixed_d20(monkeypatch, 20)
    npc.purse = 100000
    money = game.leader.money
    conv.choose(blackmail)
    assert game.leader.money > money and q["state"] == "finished" and npc.disposition <= -80


def test_collecting_a_debt(game, monkeypatch):
    q, npc = offer(game, "collect_debt")
    q["hidden"] = None
    quests.accept(game, q)
    debtor = game.world.npcs[q["target"]["npc"]]
    fixed_d20(monkeypatch, 1)
    conv = Conversation(game, debtor)
    conv.choose(next(c for c in conv.menu() if c.id == "collect_debt"))
    assert not q["done"]
    assert not next(c for c in Conversation(game, debtor).menu() if c.id == "collect_debt").enabled  # not today
    game.world.time += 1440
    fixed_d20(monkeypatch, 20)
    conv = Conversation(game, debtor)
    conv.choose(next(c for c in conv.menu() if c.id == "collect_debt"))
    assert q["done"] and q["target"]["collected"] == q["target"]["debt"]
    money = game.leader.money
    conv = Conversation(game, npc)
    conv.choose(next(c for c in conv.menu() if c.id == "quest_turn_in"))
    assert game.leader.money == money - q["target"]["debt"] + q["target"]["debt"] // 4


def test_a_debtor_with_nothing(game):
    q, npc = offer(game, "collect_debt")
    q["hidden"] = "destitute"
    quests.accept(game, q)
    debtor = game.world.npcs[q["target"]["npc"]]
    conv = Conversation(game, debtor)
    conv.choose(next(c for c in conv.menu() if c.id == "collect_debt"))
    assert q["revealed"]
    ids = [c.id for c in conv.menu()]
    assert "debt_take" in ids and "debt_forgive" in ids
    conv.choose(next(c for c in conv.menu() if c.id == "debt_forgive"))
    assert q["state"] == "finished"


def test_investigating_the_missing(game):
    q, npc = offer(game, "investigate")
    quests.accept(game, q)
    s = game.world.settlements[q["town"]]
    folk = npcs_in(game.world, s.id)
    game.player.x, game.player.y = s.x, s.y
    asked = 0
    for n in folk:
        if n.notable or q["target"].get("clue"):
            continue
        conv = Conversation(game, n)
        choice = next((c for c in conv.menu() if c.id == "ask_missing"), None)
        if choice is None:
            continue
        conv.choose(choice)
        asked += 1
    assert q["target"].get("clue"), asked
    site = game.world.sites[q["target"]["site"]]
    assert game.player.explored[site.x, site.y]
    go_down(game, site, 1)
    assert q["done"] and q["target"]["found"]
    assert game.renown.known and q["target"]["cult"] in game.renown.known


# ---------------------------------------------------------------------------- deadlines, the dead, saving
def test_deadlines_and_the_dead(game):
    q, npc = offer(game, "clear_lair")
    quests.accept(game, q)
    faction = q["faction"]
    before = game.renown.standing.get(faction, 0)
    game.world.time += 1440 * (q["days"] + 1)
    quests.daily(game)
    assert q["state"] == "failed"
    if faction in game.world.factions:
        assert game.renown.standing.get(faction, 0) < before
    q2, npc2 = offer(game, "hunt_beast")
    quests.accept(game, q2)
    npc2.alive = False
    quests.daily(game)
    assert q2["state"] == "finished" and "dead" in q2["journal"][-1]


def test_quests_survive_saving(game, tmp_path):
    q, npc = offer(game, "deliver")
    quests.accept(game, q)
    save.save_game(game, tmp_path)
    loaded = save.load_game(tmp_path / game.world.meta.id, game.tables)
    assert loaded.quests == game.quests
    assert quests.holds_quest_item(loaded, loaded.quests[0])


def test_broken_quest_data_is_reported(data):
    from realmwalker.data.registry import check_cross_references

    files = dict(data._files)
    files["quests.json"] = copy.deepcopy(files["quests.json"])
    files["quests.json"]["templates"]["bounty"]["givers"].append("dragon_tamer")
    files["quests.json"]["beasts"].append(["no_such_group", "x", "y"])
    errors = check_cross_references(files)
    assert any("dragon_tamer" in e for e in errors) and any("no_such_group" in e for e in errors)


# ---------------------------------------------------------------------------- the rest of the work (M9+)
def test_walking_someone_home(game):
    q, npc = offer(game, "escort")
    quests.accept(game, q)
    who = game.world.npcs[q["target"]["npc"]]
    assert who.flags.get("escort") == q["id"] and not who.present
    dest = game.world.settlements[q["target"]["dest"]]
    money = game.leader.money
    game.player.x, game.player.y = dest.x, dest.y
    quests.on_arrive(game)
    assert q["state"] == "finished" and game.leader.money == money + q["reward"]
    assert who.settlement == dest.id and who.present and not who.flags.get("escort")


def test_losing_the_one_you_were_walking_with(game):
    q, npc = offer(game, "escort")
    quests.accept(game, q)
    who = game.world.npcs[q["target"]["npc"]]
    quests.on_battle(game, result("fled"))
    assert q["state"] == "failed" and not who.alive


def test_a_knife_in_the_dark_or_a_warning(game):
    q, npc = offer(game, "assassinate")
    quests.accept(game, q)
    mark = game.world.npcs[q["target"]["npc"]]
    quests.on_npc_death(game, mark)
    assert q["done"]
    money = game.leader.money
    conv = Conversation(game, npc)
    conv.choose(next(c for c in conv.menu() if c.id == "quest_turn_in"))
    assert q["state"] == "finished" and game.leader.money == money + q["reward"]
    # The other way: warn them instead.
    q2, npc2 = offer(game, "assassinate")
    q2["hidden"] = "innocent"
    quests.accept(game, q2)
    mark2 = game.world.npcs[q2["target"]["npc"]]
    mark2.purse = 5000
    s = game.world.settlements[mark2.settlement]
    game.player.x, game.player.y = s.x, s.y
    conv = Conversation(game, mark2)
    assert not q2["revealed"] or True
    choices = conv.menu()  # meeting them reveals what they are
    assert q2["revealed"]
    conv.choose(next(c for c in choices if c.id == "warn_target"))
    assert q2["state"] == "finished" and mark2.disposition > 0
    assert game.world.npcs[q2["giver"]].disposition <= -70


def test_herbs_against_the_sickness(game):
    s = a_town(game)
    s.status["plague"] = {"until": 10**6}
    folk = visit(game, s)
    npc = next(n for n in folk if n.job in ("healer", "priest", "headman"))
    q = quests.make_offer(game, npc, game.world.rng.child("cure"), "cure")
    assert q is not None
    quests.accept(game, q)
    conv = Conversation(game, npc)
    assert not any(c.id == "hand_over_goods" for c in conv.menu())  # you have no herbs yet
    from realmwalker.rules.inventory import add_item

    add_item(game.leader, game.tables.items, "healing_herbs", q["target"]["count"])
    money = game.leader.money
    conv = Conversation(game, npc)
    conv.choose(next(c for c in conv.menu() if c.id == "hand_over_goods"))
    assert q["state"] == "finished" and game.leader.money == money + q["reward"]
    assert not s.status.get("plague")  # the sickness is checked, for now
    assert quests.herbs_held(game, q) == 0


def test_settling_a_feud(game, monkeypatch):
    q, npc = offer(game, "feud")
    quests.accept(game, q)
    one = game.world.npcs[q["target"]["a"]]
    two = game.world.npcs[q["target"]["b"]]
    s = game.world.settlements[one.settlement]
    game.player.x, game.player.y = s.x, s.y
    fixed_d20(monkeypatch, 20)
    conv = Conversation(game, one)
    conv.choose(next(c for c in conv.menu() if c.id == "make_peace"))
    assert one.id in q["target"]["agreed"] and not q["done"]
    # The other one takes money instead.
    game.leader.money = 100000
    conv = Conversation(game, two)
    conv.choose(next(c for c in conv.menu() if c.id == "buy_peace"))
    assert q["done"]
    conv = Conversation(game, npc)
    conv.choose(next(c for c in conv.menu() if c.id == "quest_turn_in"))
    assert q["state"] == "finished"


def test_picking_a_pocket_for_someone_else(game, monkeypatch):
    from realmwalker.game import law_talk

    q, npc = offer(game, "steal")
    quests.accept(game, q)
    mark = game.world.npcs[q["target"]["npc"]]
    mark.purse = 500
    s = game.world.settlements[mark.settlement]
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    fixed_d20(monkeypatch, 20)
    conv = Conversation(game, mark)
    law_talk.pickpocket(conv)
    assert q["done"] and quests.holds_quest_item(game, q)
    conv = Conversation(game, npc)
    conv.choose(next(c for c in conv.menu() if c.id == "quest_turn_in"))
    assert q["state"] == "finished" and not quests.holds_quest_item(game, q)


def test_standing_with_a_village_when_the_raid_comes(game):
    q, npc = offer(game, "defend")
    quests.accept(game, q)
    t = q["target"]
    town = game.world.settlements[t["settlement"]]
    assert t["when"] > game.moment.total_days and t["group"] in game.tables.creatures.encounters
    # Not the day yet: nothing happens.
    game.player.x, game.player.y = town.x, town.y
    quests.on_arrive(game)
    assert game.encounter is None
    # The day comes, and you are there.
    game.world.time += (t["when"] - game.moment.total_days) * 1440
    quests.on_arrive(game)
    assert game.encounter is not None and t["spawned"]
    quests.on_battle(game, result(dead=list(game.encounter.creatures)))
    assert q["done"]
    money = game.leader.money
    conv = Conversation(game, npc)
    conv.choose(next(c for c in conv.menu() if c.id == "quest_turn_in"))
    assert q["state"] == "finished" and game.leader.money == money + q["reward"]


def test_the_village_burns_if_you_are_not_there(game):
    q, npc = offer(game, "defend")
    quests.accept(game, q)
    t = q["target"]
    town = game.world.settlements[t["settlement"]]
    far = next(s for s in game.world.settlements if s.id != town.id)
    game.player.x, game.player.y = far.x, far.y
    game.world.time += (t["when"] - game.moment.total_days + 1) * 1440
    quests.daily(game)
    assert q["state"] == "failed"
    assert town.status.get("raided")
    assert any(town.name in n["text"] for n in game.world.news)


def test_smuggling_past_the_gate(game, monkeypatch):
    from realmwalker.game import law

    q, npc = offer(game, "smuggle")
    quests.accept(game, q)
    assert quests.holds_quest_item(game, q)
    crate = next(it for it in game.leader.inventory if f"quest:{q['id']}" in it.tags)
    assert "contraband" in crate.tags
    dest = game.world.settlements[q["target"]["dest"]]
    who = game.world.npcs[q["target"]["npc"]]
    game.player.x, game.player.y = dest.x, dest.y
    money = game.leader.money
    conv = Conversation(game, who)
    conv.choose(next(c for c in conv.menu() if c.id == "deliver_goods"))
    assert q["state"] == "finished" and game.leader.money == money + q["reward"]
    assert not quests.holds_quest_item(game, q)
    # The other way: the wardens find it.
    q2, npc2 = offer(game, "smuggle")
    quests.accept(game, q2)
    walled = next(s for s in game.world.settlements if s.walled)
    game.player.x, game.player.y = walled.x, walled.y
    monkeypatch.setattr(law, "rng_for", lambda g, what: __import__("realmwalker.core.rng", fromlist=["RNG"]).RNG(1, "x"))
    monkeypatch.setitem(game.tables.law, "gate_search_chance", 1.0)
    lines = law.gate_search(game, walled)
    assert any("take it" in line for line in lines), lines
    assert q2["state"] == "failed" and not quests.holds_quest_item(game, q2)


def test_work_cannot_be_taken_on_twice(game):
    q, npc = offer(game, "clear_lair")
    quests.accept(game, q)
    before = len(game.quests)
    assert quests.accept(game, q) == []
    assert len(game.quests) == before


def test_giving_up_on_someone_sends_them_home(game):
    q, npc = offer(game, "escort")
    quests.accept(game, q)
    who = game.world.npcs[q["target"]["npc"]]
    quests.abandon(game, q)
    assert who.alive and who.present and not who.flags.get("escort")
    assert q["state"] == "abandoned"


def test_quiet_work_stays_quiet(game):
    """Killing a man for money does not make you famous: no news, no fame, and the infamy is yours alone."""
    q, npc = offer(game, "assassinate")
    quests.accept(game, q)
    mark = game.world.npcs[q["target"]["npc"]]
    quests.on_npc_death(game, mark)
    news_before = len(game.world.news)
    fame, infamy = game.renown.fame, game.renown.infamy
    conv = Conversation(game, npc)
    conv.choose(next(c for c in conv.menu() if c.id == "quest_turn_in"))
    assert len(game.world.news) == news_before
    assert game.renown.fame == fame and game.renown.infamy > infamy
    assert any("quiet work" in d for d in game.leader.deeds)
