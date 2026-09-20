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
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Questland", 99, "small"), tables).generate()


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


# ---------------------------------------------------------------------------- offers
def test_offers_are_tied_to_real_things(game):
    w = game.world
    seen = set()
    for s in [s for s in w.settlements if s.kind in ("town", "city")][:5]:
        visit(game, s)
        for q in quests.offers_in(game, s):
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


def test_one_offer_a_week_and_it_waits(game):
    s = a_town(game)
    folk = visit(game, s)
    npc = next(n for n in folk if n.notable and n.job in quests.giver_jobs(game))
    town = game.world.towns[s.id]
    town.flags.setdefault("offer_day", {})[str(npc.id)] = -100
    for i in range(20):  # sooner or later they think of something
        town.flags["offer_day"][str(npc.id)] = -100
        q = quests.offer_for(game, npc)
        if q is not None:
            break
        game.world.time += 1440 * 8
    assert q is not None
    assert quests.offer_for(game, npc) is q  # the same job until taken or stale
    quests.accept(game, q)
    assert quests.offer_for(game, npc) is None  # one job at a time


def test_asking_for_work_in_conversation(game):
    q, npc = offer(game, "clear_lair")
    town = game.world.towns[npc.settlement]
    town.flags.setdefault("offers", {})[str(npc.id)] = q
    s = game.world.settlements[npc.settlement]
    game.player.x, game.player.y = s.x, s.y
    conv = Conversation(game, npc)
    work = next(c for c in conv.menu() if c.id == "work")
    conv.choose(work)
    assert conv.mode == "quest_offer"
    assert any(quests.pitch(game, q) in text for _, text in conv.lines)
    yes = next(c for c in conv.menu() if c.id == "work_accept")
    conv.choose(yes)
    assert conv.mode == "main" and q in game.quests and q["state"] == "active"
    site = game.world.sites[q["target"]["site"]]
    assert game.player.explored[site.x, site.y]
    assert str(npc.id) not in town.flags["offers"]


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


def test_old_characters_have_an_empty_journal():
    assert save.MIGRATIONS[7]("character", {"name": "x"})["quests"] == []


def test_the_ai_words_an_offer(game):
    q, npc = offer(game, "rescue")
    facts = quests.ai_facts(game, q)
    assert q["words"]["captive"] in facts["task"] and facts["giver"] == npc.name
    assert quests.needs_words(q)
    assert quests.apply_words(q, {"title": "The Fletcher Boy", "pitch": "They took him in the night."})
    assert quests.title(game, q) == "The Fletcher Boy" and quests.pitch(game, q).startswith('"They took')
    assert not quests.needs_words(q)


def test_broken_quest_data_is_reported(data):
    from realmwalker.data.registry import check_cross_references

    files = dict(data._files)
    files["quests.json"] = copy.deepcopy(files["quests.json"])
    files["quests.json"]["templates"]["bounty"]["givers"].append("dragon_tamer")
    files["quests.json"]["beasts"].append(["no_such_group", "x", "y"])
    errors = check_cross_references(files)
    assert any("dragon_tamer" in e for e in errors) and any("no_such_group" in e for e in errors)


def test_the_ai_can_word_an_offer_through_the_mock(game, mock_p2):
    """End to end with the mock Player2 server: facts in, words out, numbers still the game's own."""
    from tests.test_ai_service import make_service, wait_for
    from realmwalker.ai.tasks import QUEST

    q, npc = offer(game, "clear_lair")
    svc = make_service(mock_p2.base_url)
    try:
        results = []
        svc.submit(QUEST, quests.ai_facts(game, q), callback=results.append)
        assert wait_for(lambda: svc.poll() or results, 10)
        assert results[0].ok, results[0].error
        assert quests.apply_words(q, results[0].data)
    finally:
        svc.stop()
    assert q["source"] == "ai" and quests.pitch(game, q).startswith('"')
    assert quests.terms(q) == f"{quests.money_text(q['reward'])}, {q['days']} days"


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


def test_every_kind_of_work_can_be_worded(game):
    """Each template must have built-in words, AI facts and a title that fills in: a missing one is a crash."""
    kinds = set(game.tables.quests["templates"])
    assert kinds == set(quests.BUILDERS)
    made = {}
    for s in game.world.settlements:
        if len(made) == len(kinds):
            break
        folk = npcs_in(game.world, s.id) or (prepare_town(game, s) and npcs_in(game.world, s.id))
        s.status.setdefault("plague", {"until": 10**9})  # so 'cure' can be offered somewhere
        for npc in folk:
            for kind in kinds - set(made):
                if npc.job not in game.tables.quests["templates"][kind]["givers"]:
                    continue
                for c in game.party:
                    c.level = 6  # a dragon is not offered to beginners
                q = quests.make_offer(game, npc, game.world.rng.child(f"all/{npc.id}/{kind}"), kind)
                if q is not None:
                    made[kind] = q
    missing = kinds - set(made)
    assert not missing - {"slay_dragon"}, missing  # every kind but the dragon should be findable here
    for kind, q in made.items():
        for what in ("title", "pitch", "journal", "done", "failed"):
            text = quests.fill(game, q, what)
            assert text and "{" not in text, (kind, what, text)
        facts = quests.ai_facts(game, q)
        assert facts["task"] and "{" not in facts["task"] and "None" not in facts["task"], (kind, facts)
        for hidden in game.tables.quests["templates"][kind].get("hidden", {}):
            text = quests.fill(game, q, "hidden", hidden)
            assert text and "{" not in text, (kind, hidden, text)


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
