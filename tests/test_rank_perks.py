"""What rank buys you (design section 10: "Rising in rank unlocks quests, discounts, training, safehouses and titles"):
lessons from your own guild, order or church, and a thieves' guild safehouse to lie low in."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import guilds, law
from realmwalker.game.dialogue import Conversation
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.world import factions as fx
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Lawland", 12, "medium"), tables)


@pytest.fixture
def game(tables, world):
    b = CharacterBuilder(tables, RNG(3, "hero"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background("folk_hero")
    g = new_game(copy.deepcopy(world), tables, b.build())
    g.survival = False
    return g


def in_town(game):
    s = next(s for s in game.world.settlements if s.kind == "town" and fx.owner_of(game.world, s) is not None)
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    return s


def member(game, f, rank: int) -> None:
    game.renown.members[f.id] = {"rank": rank, "since": game.world.time}
    game.renown.standing[f.id] = game.tables.law["rank_standing"][rank]
    game.renown.flags.setdefault("ranks", {})[str(f.id)] = rank


def a_thief(game, s):
    guild = next(f for f in game.world.factions.values() if f.kind == "thieves_guild")
    npc = next(n for n in npcs_in(game.world, s.id) if n.alive)
    npc.flags["secret"] = guild.id
    game.renown.known.add(guild.id)
    return guild, npc


def test_the_first_rank_is_told_what_it_takes(game):
    s = in_town(game)
    guild, npc = a_thief(game, s)
    member(game, guild, 0)
    offers = guilds.offers(game, npc)
    assert offers and offers[0][1] is None and not offers[0][3] and "cutpurse" in offers[0][4]


def test_a_risen_member_is_taught_a_guild_skill_once_per_rank(game):
    s = in_town(game)
    guild, npc = a_thief(game, s)
    member(game, guild, 1)
    c = game.leader
    c.skills = [k for k in c.skills if k not in ("stealth", "sleight_of_hand", "deception")]
    c.money = 100000
    offers = [o for o in guilds.offers(game, npc) if o[3]]
    assert {o[1] for o in offers} == {"stealth", "sleight_of_hand", "deception"}
    before = game.sheet(c).skill_bonus("stealth")
    t0 = game.world.time
    said = guilds.train(game, npc, guild, "stealth")
    assert "stealth" in c.skills and game.sheet(c).skill_bonus("stealth") == before + game.sheet(c).proficiency
    assert game.world.time - t0 == 10 * 60 and c.money == 100000 - 5000
    assert any("trained in Stealth" in t for t in said)
    # One lesson for one rank risen: the next waits for the next rank, and costs more.
    left = guilds.offers(game, npc)
    assert all(not ok and "rise another rank" in why for _, _, _, ok, why in left)
    member(game, guild, 2)
    assert guilds.lesson_fee(game, guild) == 7500 and any(o[3] for o in guilds.offers(game, npc))


def test_the_lesson_is_a_conversation_choice(game):
    s = in_town(game)
    guild, npc = a_thief(game, s)
    member(game, guild, 1)
    game.leader.skills = [k for k in game.leader.skills if k != "deception"]
    game.leader.money = 100000
    conv = Conversation(game, npc)
    choice = next(c for c in conv.menu() if c.id == "train" and c.data.get("skill") == "deception")
    assert choice.enabled
    conv.choose(choice)
    assert "deception" in game.leader.skills


def test_a_safehouse_halves_the_bounty(game):
    s = in_town(game)
    guild, npc = a_thief(game, s)
    member(game, guild, 0)
    realm = fx.realm_of_settlement(game.world, s)
    assert law.is_fence(game, npc)
    game.leader.money = 100000
    offer = guilds.safehouse_offer(game, npc)
    assert offer is not None and not offer[2] and "nobody is looking" in offer[3]
    game.renown.bounties[realm.id] = 4000
    offer = guilds.safehouse_offer(game, npc)
    assert offer[2]
    t0 = game.world.time
    said = guilds.lie_low(game, npc)
    assert game.renown.bounties[realm.id] == 2000 and game.world.time - t0 == 3 * 24 * 60
    assert game.confined is None and game.leader.fatigue < 70
    assert "2000" not in said[1] and ("gp" in said[1] or "sp" in said[1])
    offer = guilds.safehouse_offer(game, npc)
    assert not offer[2] and "days ago" in offer[3]  # not again this week


def test_only_the_guild_knows_the_way(game):
    s = in_town(game)
    npc = next(n for n in npcs_in(game.world, s.id) if n.alive and not n.flags.get("secret"))
    assert guilds.safehouse_offer(game, npc) is None
    assert guilds.offers(game, npc) == []
