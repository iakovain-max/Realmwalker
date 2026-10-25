"""The goal language (Expansion 6 C.5, docs/ADVENTURES.md §8.10): a situation's goals are tests over the world, checked
against a whitelist at start-up, heard by `goals.notify` from wherever the game changes something they read, and kept
with the way they were reached (talk, pay, sneak, steal, force, fight, magic, law, wait...). Each predicate is made
true here by the ways the game has, through the game's own code."""

import pytest

from realmwalker.core import dice
from realmwalker.game import economy, fight, law, quests, townlife
from realmwalker.game.dialogue import Conversation
from realmwalker.game.encounters import make_encounter
from realmwalker.game.people import npcs_in
from realmwalker.game.story import check, goals
from realmwalker.rules.combat import FOE
from realmwalker.rules.items import Item
from realmwalker.world import marks
from realmwalker.world.tables import Tables
from tests.test_first_hour import SEEDS, a_life


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture
def life(tables):
    townlife.forget()
    return a_life(tables, SEEDS[0])


def folk(game, town, n=2):
    people = [p for p in npcs_in(game.world, town.id) if p.alive and not p.flags.get("visitor")
              and not p.flags.get("stays") and p.job != "guard"]
    assert len(people) >= n
    return people[:n]


def situation(game, town, roles: dict, tests: dict, **extra) -> dict:
    sits = goals.situations(game.world)
    qid = f"Q{len(sits) + 1}"
    rec = {"id": qid, "town": town.id, "roles": roles, "state": "met", "flags": [], "ways": [],
           "goals": [{"id": gid, "test": t} for gid, t in tests.items()]}
    rec.update(extra)
    sits[qid] = rec
    return rec


def reached(sit: dict, gid: str = "g") -> str | None:
    g = next(g for g in sit["goals"] if g["id"] == gid)
    return g.get("way") if g.get("reached") is not None else None


def next_day(game) -> None:
    game.pass_time(24 * 60, "rest")


# ---------------------------------------------------------------------------- the whitelist
def test_the_language_is_a_whitelist_checked_at_start_up(tables):
    assert goals.self_problems() == []
    assert not [p for p in check.problems(tables) if "goal" in p]
    roles = {"boy", "gang", "home"}
    assert goals.problems(["all", ["alive", "boy"], ["not", ["at", "boy", "home_of(boy)"]]], roles) == []
    assert goals.problems(["any", ["standing", 3, ">=", 10], ["day", "<", "clock"]], roles) == []
    bad = {
        "game knows": ["wanders", "boy"],
        "takes 1 argument": ["alive", "boy", "gang"],
        "not a role": ["alive", "girl"],
        "not a path": ["at", "boy", "barn_of(boy)"],
        "comparison": ["standing", 3, "about", 10],
        "state of the law": ["law_state", "boy", "flogged"],
        "not a day": ["day", ">", "tomorrow"],
        "one test": ["not", ["alive", "boy"], ["dead", "boy"]],
        "at least one": ["all"],
        "not a test": "alive(boy)",
    }
    for why, t in bad.items():
        found = goals.problems(t, roles)
        assert found and any(why in p for p in found), (t, found)

    class Fake:
        situations = {"predicaments": {"lost_boy": {"roles": {"boy": {}}, "goals": [{"id": "home",
                                                                                      "test": ["alive", "girl"]}]}}}
    assert goals.data_problems(Fake) == ["situations.json: lost_boy, goal home: in 'alive', 'girl' is not a role "
                                         "of this situation."]


def test_a_situation_listens_only_to_what_its_goals_read(life):
    game, town = life
    a, = folk(game, town, 1)
    sit = situation(game, town, {"x": {"npc": a.id}}, {"g": ["day", ">=", 0]})
    assert goals.listens(sit["goals"]) == ["day"]
    assert goals.notify(game, "talk") == [], "a talk cannot change the calendar"
    assert goals.notify(game, "day") == [(sit["id"], "g", "wait")]
    assert goals.notify(game, "day") == [], "a goal is reached once"
    far = max(game.world.settlements, key=lambda s: abs(s.x - town.x) + abs(s.y - town.y))
    away = situation(game, far, {}, {"g": ["day", ">=", 0]})
    goals.notify(game, "day")
    assert reached(away) is None, "only the situations within reach of the hero are tested"
    with pytest.raises(ValueError):
        goals.notify(game, "sneeze")


# ---------------------------------------------------------------------------- by blood
def _tagged_street_fight(game, sit, role):
    enc = make_encounter(game, "bandits", game.world.rng.child("goals/street"))
    for c in enc.creatures:
        c.story = {"situation": sit["id"], "role": role}
    battle = fight.start_battle(game, enc.creatures, enc.intro, title="Bandits")
    for f in battle.fighters:
        if f.side == FOE:
            f.hp, f.state = 0, "dead"
    battle.outcome = "victory"
    return battle


def test_a_band_killed_in_a_fight_is_dead_by_the_sword(life):
    game, town = life
    sit = situation(game, town, {"gang": {"band": "the Red Hands"}}, {"g": ["dead", "gang"], "h": ["alive", "gang"]})
    assert goals.test(game, sit, ["alive", "gang"])
    _tagged_street_fight(game, sit, "gang")
    fight.finish_battle(game)
    assert sit["roles"]["gang"]["state"] == "dead"
    assert reached(sit) == "fight" and goals.way_used(sit, "fight", "g")
    assert not goals.way_used(sit, "talk")


def test_a_townsman_struck_down_is_dead(life):
    game, town = life
    a, = folk(game, town, 1)
    sit = situation(game, town, {"x": {"npc": a.id}}, {"g": ["dead", "x"]})
    Conversation(game, a).start_fight()
    for f in game.battle.fighters:
        if f.side == FOE:
            f.hp, f.state = 0, "dead"
    game.battle.outcome = "victory"
    fight.finish_battle(game)
    assert not a.alive and reached(sit) == "fight"


def test_a_captive_s_fate_settles_its_band(life):
    game, town = life
    sit = situation(game, town, {"gang": {"band": "x"}, "boss": {"band": "y"}},
                    {"g": ["gone", "gang"], "h": ["dead", "boss"]})
    _tagged_street_fight(game, sit, "gang")
    fight.finish_battle(game)  # (the fight is over; two of them are brought before you)
    sit["roles"]["gang"].pop("state")
    enc = make_encounter(game, "bandits", game.world.rng.child("goals/captives"))
    spared, executed = enc.creatures[0], enc.creatures[-1]
    spared.story = {"situation": sit["id"], "role": "gang"}
    executed.story = {"situation": sit["id"], "role": "boss"}
    fight.decide_captive(game, spared, "spare")
    assert reached(sit, "g") == "talk"
    fight.decide_captive(game, executed, "execute")
    assert reached(sit, "h") == "fight"


# ---------------------------------------------------------------------------- hands and things
def test_a_thing_comes_to_you_by_purse_gift_theft_and_the_spoils(life, monkeypatch):
    game, town = life
    w = game.world
    seller = next(n for n in npcs_in(w, town.id) if n.alive and economy.shop_state(game, n)
                  and economy.shop_state(game, n)["stock"])
    shop = economy.shop_state(game, seller)
    item_id = sorted(shop["stock"])[0]
    game.leader.money += 100000
    sit = situation(game, town, {}, {"g": ["holds", "you", item_id]})
    economy.buy(game, seller, item_id)
    assert reached(sit) == "pay"

    giver, = [n for n in folk(game, town, 3) if n is not seller][:1]
    giver.inventory.append(Item(uid=0, def_id="sealed_letter", qty=1, made_at=w.time, tags=["story:letter"]))
    sit = situation(game, town, {"x": {"npc": giver.id}},
                    {"g": ["holds", "you", "story:letter"], "h": ["not", ["holds", "x", "story:letter"]]})
    Conversation(game, giver).give_item()
    assert reached(sit) == "talk" and reached(sit, "h") == "talk"

    shop = economy.shop_state(game, seller)
    item_id = sorted(shop["stock"])[0]
    for c in game.party:
        c.inventory = [it for it in c.inventory if it.def_id != item_id]
    sit = situation(game, town, {}, {"g": ["holds", "you", item_id]})
    monkeypatch.setattr(dice, "d20", lambda rng, **kw: dice.D20Roll(20, [20]))
    ok, _ = law.steal_from_shop(game, seller, item_id)
    assert ok and reached(sit) == "steal"

    sit = situation(game, town, {}, {"g": ["holds", "you", "story:ring"]})
    _tagged_street_fight(game, sit, "nobody")
    after = fight.finish_battle(game)
    after.loot.append(Item(uid=0, def_id="sealed_letter", qty=1, made_at=w.time, tags=["story:ring"]))
    fight.take_loot(game)
    assert reached(sit) == "fight"


# ---------------------------------------------------------------------------- places
def _step_into(game, building) -> None:
    lm = game.local
    p = game.player
    dx, dy = building.door
    for ox, oy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        x, y = dx + ox, dy + oy
        if lm.in_bounds(x, y) and lm.building_at(x, y) is not building and \
                game.tables.local_terrain_walk(lm, x, y) if hasattr(game.tables, "local_terrain_walk") else \
                lm.in_bounds(x, y) and lm.building_at(x, y) is not building:
            p.lx, p.ly = x, y
            for _ in range(3):  # (a shut door opens first)
                game.move(-ox, -oy)
                if lm.building_at(p.lx, p.ly) is building:
                    return
    raise AssertionError("no way in found")


def test_into_a_house_openly_or_unseen_and_out_of_town(life, monkeypatch):
    game, town = life
    lm = game.local
    a, b = [n for n in folk(game, town, 6) if lm.building_at(*n.home) is not None][:2]
    sit = situation(game, town, {"x": {"npc": a.id}}, {"g": ["at", "you", "home_of(x)"],
                                                         "t": ["at", "you", "town_of(x)"]})
    assert goals.test(game, sit, ["at", "you", "town_of(x)"])
    _step_into(game, lm.building_at(*a.home))
    assert reached(sit) == "wait"
    other = lm.building_at(*b.home)
    if other is not lm.building_at(*a.home):
        sit2 = situation(game, town, {"y": {"npc": b.id}}, {"g": ["at", "you", "home_of(y)"]})
        game.sneaking = True
        _step_into(game, other)
        assert reached(sit2) == "sneak"
    # Out of the town and away down the road: no longer at it.
    from realmwalker.game import encounters, events

    monkeypatch.setattr(encounters, "encounter_chance", lambda *a, **k: 0.0)
    monkeypatch.setattr(events, "event_chance", lambda *a, **k: 0.0)
    sit3 = situation(game, town, {"x": {"npc": a.id}}, {"g": ["not", ["at", "you", "town_of(x)"]]})
    game.leave_local()
    assert reached(sit3) is None, "still at the town's gate"
    w = game.world
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
        x, y = town.x + dx, town.y + dy
        if w.in_bounds(x, y) and w.settlement_at(x, y) is not town and game.move(dx, dy):
            break
    assert reached(sit3) == "wait"


def test_where_townsfolk_are_and_where_they_have_gone(life):
    game, town = life
    a, b = folk(game, town, 2)
    sit = situation(game, town, {"x": {"npc": a.id}, "y": {"npc": b.id}},
                    {"g": ["gone", "x"], "h": ["at", "y", "town_of(y)"], "i": ["at", "y", "work_of(y)"]})
    assert goals.test(game, sit, ["at", "x", "town_of(x)"]) and not goals.test(game, sit, ["gone", "x"])
    a.flags["moved_on"] = True
    next_day(game)
    assert reached(sit) == "wait" and reached(sit, "h") == "wait"
    assert not goals.test(game, sit, ["at", "x", "town_of(x)"]), "gone from the town is not in it"


def test_a_captive_in_chains_is_freed_and_comes_along(life):
    game, town = life
    a, = folk(game, town, 1)
    a.flags["captive"] = True
    sit = situation(game, town, {"x": {"npc": a.id}}, {"g": ["all", ["free", "x"], ["with_party", "x"]]})
    assert not goals.test(game, sit, ["free", "x"])
    lm = game.local
    lm.features[(1, 1)] = {"type": "captive", "npc": a.id, "name": a.name}
    quests.free_captive(game, lm, 1, 1)
    assert reached(sit) == "force" and "captive" not in a.flags


def test_one_who_joins_the_party_is_with_it(life):
    game, _ = life
    from realmwalker.game import companions

    w = game.world
    game.leader.money += 100000
    hired = town = None
    for s in sorted(w.settlements, key=lambda s: s.kind not in ("town", "city")):  # (travellers wait at inns)
        if game.in_local:
            game.leave_local()
        game.player.x, game.player.y = s.x, s.y
        game.enter_local()
        for n in npcs_in(w, s.id):
            if n.alive and n.flags.get("recruit"):
                n.disposition, n.met = 20, True
                if not companions.recruit_problem(game, n):
                    hired, town = n, s
                    break
        if hired is not None:
            break
    assert hired is not None, "somebody in this world will come along"
    sit = situation(game, town, {"x": {"npc": hired.id}}, {"g": ["with_party", "x"], "h": ["not", ["at", "x",
                                                                                                     "town_of(x)"]]})
    companions.hire(game, hired)
    assert reached(sit) in ("pay", "talk") and reached(sit, "h") == reached(sit)


# ---------------------------------------------------------------------------- words, the law, the world
def test_a_conversation_reaches_a_goal_by_talk_by_coin_or_by_a_charm(life):
    game, town = life
    a, b, c = folk(game, town, 3)
    sit = situation(game, town, {"x": {"npc": a.id}}, {"g": ["knows", "you", "where_the_boy_went"]})
    conv = Conversation(game, a)
    goals.learn(game, "you", "where_the_boy_went")
    assert reached(sit) == "talk"
    conv.close()
    sit = situation(game, town, {"x": {"npc": b.id}}, {"g": ["flag", "the_gate_opened"]})
    conv = Conversation(game, b)
    conv.paid = True
    sit["flags"].append("the_gate_opened")
    conv.close()
    assert reached(sit) == "pay"
    sit = situation(game, town, {"x": {"npc": c.id}}, {"g": ["knows", "x", "the_lie"]})
    c.flags["charmed_until"] = game.world.time + 600
    conv = Conversation(game, c)
    c.flags.setdefault("knows", []).append("the_lie")
    conv.close()
    assert reached(sit) == "magic"


def test_the_law_s_states_and_a_realm_s_standing(life):
    game, town = life
    from realmwalker.game import reputation

    realm, _ = law.jurisdiction(game)
    if realm is None:
        pytest.skip("no lord's law here")
    a, = folk(game, town, 1)
    before = reputation.standing(game, realm.id)
    sit = situation(game, town, {"realm": {"faction": realm.id}, "x": {"npc": a.id}},
                    {"g": ["law_state", "you", "accused"], "h": ["standing", "realm", "<", before],
                     "j": ["law_state", "x", "jailed"], "k": ["not", ["free", "x"]]})
    law.commit(game, "theft", victim=a, value=10, reported=True, witnesses=[])
    assert reached(sit) == "steal" and reached(sit, "h") == "steal"
    a.flags["law"] = "jailed"  # (C.6's people ops write it; the law's door hears it)
    goals.notify(game, "law")
    assert reached(sit, "j") == "law" and reached(sit, "k") == "law"


def test_ties_of_marriage_and_debt(life):
    game, town = life
    a, b = folk(game, town, 2)
    for p in (a, b):
        p.flags.setdefault("life", {"ties": [], "secrets": [], "events": []})
    sit = situation(game, town, {"x": {"npc": a.id}, "y": {"npc": b.id}},
                    {"g": ["married", "x", "y"], "h": ["owes", "y", "x"], "i": ["not", ["owes", "y", "x"]]})
    goals.notify(game, "day")
    assert reached(sit, "i") == "wait" and reached(sit) is None
    a.flags["life"]["ties"].append({"kind": "wife", "name": b.name, "npc": b.id, "state": "alive"})
    b.flags["life"]["ties"].append({"kind": "creditor", "name": a.name, "npc": a.id, "state": "alive"})
    next_day(game)
    assert reached(sit) == "wait" and reached(sit, "h") == "wait"


def test_marks_cleared_places_fallen_factions_codewords_and_the_clock(life):
    game, town = life
    w = game.world
    site = min(w.sites, key=lambda s: abs(s.x - town.x) + abs(s.y - town.y))
    faction = next(f for f in w.factions.values() if f.active)
    today = int(game.moment.total_days)
    sit = situation(game, town, {"f": {"faction": faction.id}, "here": {"place": {"settlement": town.id}},
                                 "den": {"place": {"site": site.id}}},
                    {"plague": ["status", "here", "plague"], "clear": ["cleared", "den"],
                     "fallen": ["not", ["faction_active", "f"]], "word": ["flag", "bell_rung"],
                     "due": ["day", ">=", "clock"], "early": ["day", "<", "clock"]},
                    clock={"due": today + 1, "what": "the_raid"})
    goals.notify(game, "day")
    assert reached(sit, "early") == "wait" and reached(sit, "due") is None
    marks.add(w, town, "plague", today)
    quests.site_cleared(game, site.id)
    faction.fallen = 1
    sit["flags"].append("bell_rung")
    next_day(game)
    for gid in ("plague", "clear", "fallen", "word", "due"):
        assert reached(sit, gid) == "wait", gid


def test_a_reached_goal_is_told_to_whoever_listens(life):
    game, town = life
    heard = []
    goals.REACTIONS.append(lambda game, sit, gid, way: heard.append((sit["id"], gid, way)))
    try:
        sit = situation(game, town, {}, {"g": ["alive", "you"]})
        goals.notify(game, "talk", "favour")
    finally:
        goals.REACTIONS.pop()
    assert heard == [(sit["id"], "g", "favour")] and sit["ways"][0]["by"] == "talk"
