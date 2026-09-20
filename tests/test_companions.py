"""Companions (M7 part 2): travellers at the inns, hiring, wages, loyalty and what moves it, desertion, orders,
shared food, death, saving."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import companions as comp
from realmwalker.game import save
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.rules.inventory import add_item
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Fellowland", 21, "medium"), tables).generate()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    g.leader.money = 100000
    return g


def to_town(game, kind="town"):
    s = next(s for s in game.world.settlements if s.kind == kind)
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    return s


def travellers(game, s):
    return [n for n in npcs_in(game.world, s.id) if n.flags.get("recruit") and n.alive and not n.flags.get("companion")]


def hire_one(game, kind="town"):
    s = to_town(game, kind)
    t = travellers(game, s)
    if not t:
        pytest.skip("no traveller at this inn")
    npc = t[0]
    npc.disposition = 20
    npc.met = True
    msgs = comp.hire(game, npc)
    assert "joins you" in msgs[0], msgs
    return game.party[-1], npc, s


def test_travellers_wait_at_the_inns(game):
    s = to_town(game, "city")
    t = travellers(game, s)
    assert t, "a city inn has people looking for work"
    arch = game.tables.companions["archetypes"]
    for n in t:
        assert n.flags["recruit"] in arch and n.notable
    # A month later they have moved on and others have come.
    first = {n.id for n in t}
    game.leave_local()
    game.world.time += 31 * 1440
    game.enter_local()
    assert {n.id for n in travellers(game, s)} != first


def test_hiring_a_companion(game):
    money = game.leader.money
    c, npc, s = hire_one(game, "city")
    assert c in game.party and c.companion["npc"] == npc.id
    assert not npc.present and npc.flags["companion"]
    assert game.leader.money < money
    assert c.level >= 1 and c.inventory and c.max_hp > 0
    assert c.name == npc.name
    assert not c.pending, "a new companion's level-up choices are already made"


def test_who_will_not_come(game):
    s = to_town(game, "city")
    t = travellers(game, s)
    if not t:
        pytest.skip("no traveller")
    npc = t[0]
    npc.met, npc.disposition = True, -60
    assert "like you" in comp.recruit_problem(game, npc)
    npc.disposition = 20
    game.leader.money = 0
    assert "up front" in comp.recruit_problem(game, npc)


def test_hiring_in_conversation(game):
    s = to_town(game, "city")
    t = travellers(game, s)
    if not t:
        pytest.skip("no traveller")
    npc = t[0]
    conv = Conversation(game, npc)
    npc.disposition = 20
    choice = next(c for c in conv.menu() if c.id == "recruit")
    assert choice.enabled
    conv.choose(choice)
    assert npc.flags.get("companion") and conv.ended


def test_loyalty_follows_values(game):
    c, npc, s = hire_one(game, "city")
    c.companion["values"] = ["compassionate"]
    before = c.companion["loyalty"]
    comp.react(game, "mercy")
    assert c.companion["loyalty"] > before
    comp.react(game, "execution", "cruelty")
    assert c.companion["loyalty"] < before
    c.companion["values"] = ["lawful"]
    before = c.companion["loyalty"]
    from realmwalker.game import law

    law.commit(game, "theft", witnesses=[])
    assert c.companion["loyalty"] < before


def test_wages_and_desertion(game, monkeypatch):
    c, npc, s = hire_one(game, "city")
    wage = c.companion["wage"]
    money = sum(m.money for m in game.party)
    comp.daily(game)
    assert c.companion["unpaid"] == 0 and sum(m.money for m in game.party) == money
    for m in game.party:
        m.money = 0
    before = c.companion["loyalty"]
    comp.daily(game)
    assert c.companion["unpaid"] == 1 and c.companion["loyalty"] < before
    game.leader.money = 5000
    c.companion["loyalty"] = 5
    monkeypatch.setattr(RNG, "chance", lambda self, p: True)
    comp.daily(game)
    assert c not in game.party
    assert npc.present and npc.disposition <= -30
    assert wage > 0


def test_loot_shares(game):
    c, npc, s = hire_one(game, "city")
    c.companion["share"] = 0.2
    before = c.money
    left = comp.share_loot(game, 1000)
    assert left == 800 and c.money == before + 200


def test_waiting_and_rejoining(game):
    c, npc, s = hire_one(game, "city")
    game.leave_local()
    text = comp.set_order(game, c, "wait")
    assert c not in game.party and c in game.waiting and "wait" in text
    x, y = game.player.x, game.player.y
    game.player.x += 1
    game._arrive(None)
    assert c in game.waiting
    game.player.x, game.player.y = x, y
    game._arrive(None)
    assert c in game.party and not game.waiting


def test_watch_and_forage_at_camp(game, monkeypatch):
    from realmwalker.game import camp, fight
    from realmwalker.game.encounters import make_encounter

    c, npc, s = hire_one(game, "city")
    game.leave_local()
    comp.set_order(game, c, "watch")
    assert comp.watching(game)
    enc = make_encounter(game, "wolf_pack", RNG(1))
    monkeypatch.setattr(fight, "roll_encounter", lambda *a, **k: enc, raising=False)
    import realmwalker.game.encounters as encounters

    monkeypatch.setattr(encounters, "roll_encounter", lambda *a, **k: enc)
    fight.rest(game, "long")
    assert game.encounter is enc and not enc.asleep
    game.encounter = None
    comp.set_order(game, c, "forage")
    lines = camp.forage_while_resting(game, c)
    assert isinstance(lines, list)


def test_the_party_shares_its_food(game):
    from realmwalker.game.survival import feed

    c, npc, s = hire_one(game, "city")
    c.inventory = [it for it in c.inventory if not game.tables.items.get(it.def_id).get("food")]
    add_item(game.leader, game.tables.items, "rations", 3)
    c.hunger = 70
    feed(game, c)
    assert c.hunger < 70


def test_a_companion_can_die(game):
    from realmwalker.game import survival

    c, npc, s = hire_one(game, "city")
    c.hp = 0
    c.death_cause = "a fall"
    survival.check_death(game, c)
    assert c not in game.party and not npc.alive and game.over is None


def test_companions_survive_saving(game, tmp_path):
    c, npc, s = hire_one(game, "city")
    comp.change_loyalty(c, 12)
    game.leave_local()
    save.save_game(game, tmp_path)
    loaded = save.load_game(tmp_path / game.world.meta.id, game.tables)
    assert len(loaded.party) == 2
    assert loaded.party[1].companion == c.companion
    comp.set_order(loaded, loaded.party[1], "wait")
    save.save_game(loaded, tmp_path)
    again = save.load_game(tmp_path / game.world.meta.id, game.tables)
    assert len(again.party) == 1 and len(again.waiting) == 1


def test_companions_fight_under_your_command(game):
    from realmwalker.game.fight import start_battle
    from realmwalker.rules.creatures import spawn

    c, npc, s = hire_one(game, "city")
    game.leave_local()
    b = start_battle(game, [spawn(game.tables, "wolf", RNG(3), 1)], "Wolves.")
    sides = [f.char for f in b.fighters if f.char is not None]
    assert c in sides
    seen = set()
    for _ in range(200):
        if b.outcome is not None:
            break
        if b.step():
            continue
        f = b.pending_party()
        if f is None:
            break
        seen.add(f.char.name)
        b.do_dodge(f)
    assert c.name in seen or b.outcome is not None


def test_the_dead_do_not_travel_with_you(game):
    """Whatever kills a companion, they leave the party and those waiting (autoplay caught one lingering)."""
    c, npc, s = hire_one(game)
    game.leave_local()
    # One who dies while waiting somewhere is not picked up again.
    comp.set_order(game, c, "wait")
    assert c in game.waiting
    c.alive = False
    game._arrive(None)
    assert c not in game.waiting and c not in game.party
    assert not npc.alive  # the town hears of it
    # And one who dies in the party is buried as time passes.
    c.alive = True
    game.party.append(c)
    c.alive = False
    game.bury_the_dead()
    assert c not in game.party and c not in game.waiting
