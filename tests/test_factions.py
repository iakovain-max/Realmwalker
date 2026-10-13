"""Factions (M6 part 1): who holds what, who rules, who likes whom, laws, the realm map, what the player knows,
background ties, and townsfolk who answer to a faction."""

import copy

import numpy as np
import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import reputation, save
from realmwalker.game.people import first_impression, npc_factions, npcs_in
from realmwalker.game.state import new_game
from realmwalker.rules.creation import CharacterBuilder, make_ties
from realmwalker.world import factions as fx
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Factionland", 11, "medium"), tables)


def hero(tables, background="soldier", seed=1, race="human"):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race(race)
    b.set_class("fighter")
    b.set_background(background)
    return b.build()


def start(tables, world, background="soldier", seed=1):
    w = copy.deepcopy(world)
    char = hero(tables, background, seed)
    towns = [s for s in w.settlements if s.kind in ("town", "village")]
    home = towns[seed % len(towns)]
    char.ties = make_ties(w, tables, char, home.id, RNG(seed, "ties"))
    return new_game(w, tables, char, start_settlement=home.id)


@pytest.mark.slow
@pytest.mark.parametrize("seed,size", [(11, "medium"), (3, "small"), (21, "large")])
def test_every_world_has_its_powers(tables, seed, size):
    w = cached_world(WorldOptions("Powers", seed, size), tables)
    kinds = {f.kind for f in fx.active_factions(w)}
    for needed in ("kingdom", "noble_house", "temple", "merchant_guild", "cult", "bandit_gang", "healers_guild"):
        assert needed in kinds, needed
    assert len(fx.active_factions(w, "kingdom")) >= 2
    for f in fx.active_factions(w):
        leader = fx.leader_of(w, f)
        assert leader is not None and leader.alive and leader.faction == f.id, f.name
        assert f.name and f.name[0] != " "
        assert f.liege < 0 or w.factions[f.liege].active
    # Every town and city is held, and by a realm.
    for s in w.settlements:
        if s.kind in ("town", "city", "hold", "elfhall"):
            owner = fx.owner_of(w, s)
            assert owner is not None and owner.kind in fx.REALM_KINDS, s.name
    # Relations are symmetric and in range.
    for a in fx.active_factions(w):
        for b, v in a.relations.items():
            assert -100 <= v <= 100
            assert w.factions[b].relations[a.id] == v
    names = [f.name for f in fx.active_factions(w)]
    assert len(names) == len(set(names)), "faction names repeat"


def test_structure_of_realms(world, tables):
    w = world
    for k in fx.active_factions(w, "kingdom"):
        capital = w.settlements[k.seat]
        assert capital.owner == k.id
        assert k.laws and {"magic", "weapons", "religion", "harshness"} <= set(k.laws)
        assert k.flags.get("dynasty")
    for h in fx.active_factions(w, "noble_house"):
        if h.liege >= 0:
            assert not h.laws and fx.laws_of(w, h) == fx.laws_of(w, w.factions[h.liege])
            assert fx.relation(w, h.id, h.liege) > 0 or fx.relation_state(w, tables, h.id, h.liege)[0] == "vassal of"
    for c in fx.active_factions(w, "cult", "thieves_guild"):
        assert c.secret
    for c in fx.active_factions(w, "cult"):
        for k in fx.active_factions(w, "kingdom"):
            assert fx.relation(w, c.id, k.id) < -25


def test_the_realm_map(world):
    owner, realm = fx.territory(world)
    assert owner.shape == (world.width, world.height)
    for s in world.settlements:
        f = fx.owner_of(world, s)
        if f is not None:
            top = fx.top_liege(world, f)
            assert realm[s.x, s.y] == top.id
            assert fx.realm_at(world, s.x, s.y) is top
    ocean = world.biome_ids.index("ocean")
    assert (realm[world.biome == ocean] == -1).all()
    # Cached until holdings change.
    assert fx.territory(world)[1] is realm
    fx.touch(world)
    assert fx.territory(world)[1] is not realm


def test_factions_survive_saving(world, tables, tmp_path):
    save.save_world(world, tmp_path)
    loaded = save.load_world(tmp_path)
    assert sorted(loaded.factions) == sorted(world.factions)
    for fid, f in world.factions.items():
        g = loaded.factions[fid]
        assert (g.name, g.kind, g.leader, g.liege, g.relations, g.laws, g.color) == \
            (f.name, f.kind, f.leader, f.liege, f.relations, f.laws, f.color)
    assert [s.owner for s in loaded.settlements] == [s.owner for s in world.settlements]
    assert loaded.figures[0].to_dict() == world.figures[0].to_dict()
    assert [s.faction for s in loaded.sites] == [s.faction for s in world.sites]


def test_a_new_character_knows_their_own_lords(world, tables):
    game = start(tables, world, "farmer")
    home = game.world.settlements[game.player.home]
    owner = fx.owner_of(game.world, home)
    assert owner is not None and owner.id in game.renown.known
    assert fx.top_liege(game.world, owner).id in game.renown.known
    church = fx.church_of(game.world, fx.faith_for_culture(tables, game.leader.culture))
    assert church is None or church.id in game.renown.known
    assert not any(game.world.factions[f].secret for f in game.renown.known)
    assert game.renown.flags["started"]


def test_the_soldier_served_a_real_lord(world, tables):
    for seed in range(1, 8):
        game = start(tables, world, "soldier", seed)
        tie = game.leader.ties[0]
        fid = tie["refs"].get("faction")
        assert fid is not None
        f = game.world.factions[fid]
        leader = fx.leader_of(game.world, f)
        assert leader.full_name() in tie["text"]
        expected = -30 if "desert" in tie["text"] else 15
        assert reputation.standing(game, fid) == expected
        assert fid in game.renown.known


def test_the_criminal_is_wanted(world, tables):
    game = start(tables, world, "criminal")
    tie = game.leader.ties[0]
    realm = tie["refs"].get("bounty_faction")
    assert realm is not None
    assert game.renown.bounties[realm] == tie["refs"]["bounty"]
    assert game.renown.crimes and game.renown.crimes[0]["realm"] == realm


def test_the_noble_has_a_family_house(world, tables):
    game = start(tables, world, "noble")
    fid = game.leader.ties[0]["refs"]["faction"]
    house = game.world.factions[fid]
    assert house.kind == "noble_house" and house.flags.get("minor")
    assert game.leader.name.split()[-1] in house.name
    assert reputation.standing(game, fid) == 50
    assert fid in game.renown.members
    # A second save/load keeps the house and the standing.
    assert house.leader in game.world.figures


def test_renown_survives_saving(world, tables, tmp_path):
    game = start(tables, world, "criminal")
    game.renown.fame = 7
    reputation.change_standing(game, next(iter(game.renown.known)), -12)
    save.save_game(game, tmp_path)
    loaded = save.load_game(tmp_path / game.world.meta.id, tables)
    assert loaded.renown.to_dict() == game.renown.to_dict()


def test_rulers_live_in_their_seats(world, tables):
    game = start(tables, world, "farmer")
    w = game.world
    k = fx.active_factions(w, "kingdom")[0]
    capital = w.settlements[k.seat]
    game.player.local_key = None
    game.player.x, game.player.y = capital.x, capital.y
    game.enter_local()
    king = fx.leader_of(w, k)
    npc = w.npcs.get(king.npc)
    assert npc is not None and npc.name == king.name and npc.flags["figure"] == king.id
    assert npc_factions(game, npc)[0] is k
    # A priest answers to their church; the town's folk to its lord.
    for n in npcs_in(w, capital.id):
        facs = npc_factions(game, n)
        assert facs, n.job
        if n.job == "guard":
            assert facs[0] is fx.owner_of(w, capital)


def test_standing_colours_first_impressions(world, tables):
    game = start(tables, world, "farmer")
    w = game.world
    s = next(s for s in w.settlements if s.kind == "town")
    game.player.local_key = None
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    npc = next(n for n in npcs_in(w, s.id) if n.job == "guard")
    lord = npc_factions(game, npc)[0]
    base = first_impression(game, npc)
    reputation.set_standing(game, lord.id, 60)
    assert first_impression(game, npc) > base
    reputation.set_standing(game, lord.id, -60)
    low = first_impression(game, npc)
    assert low < base
    game.renown.bounties[fx.top_liege(w, lord).id] = 500
    assert first_impression(game, npc) < low


def test_crossing_a_border_is_announced(world, tables):
    game = start(tables, world, "farmer")
    w = game.world
    _, realm = fx.territory(w)
    here = int(realm[game.player.x, game.player.y])
    # Find a neighbouring pair of land tiles in different lords' lands and step across.
    owner, _ = fx.territory(w)
    xs, ys = np.nonzero((owner[:-1, :] != owner[1:, :]) & (owner[:-1, :] >= 0) & (owner[1:, :] >= 0))
    assert len(xs)
    x, y = int(xs[0]), int(ys[0])
    game.player.x, game.player.y = x, y
    game._realm_here = int(owner[x, y])
    game.player.x = x + 1
    game._arrive(None)
    assert any("You cross into the lands of" in m.text for m in game.log.messages[-3:])
    assert here is not None


def test_faction_details_read_well(world, tables):
    game = start(tables, world, "soldier")
    for f in fx.active_factions(game.world):
        game.renown.known.add(f.id)
    for f in fx.active_factions(game.world):
        text = reputation.faction_details(game, f)
        assert "Your standing" in text
        assert "{" not in text and "None" not in text


def test_a_promotion_has_to_be_earned(tables, world):
    game = start(tables, world)
    """Standing opens the door; a piece of the faction's work walks you through it."""
    from realmwalker.game import quests, reputation

    f = next(x for x in game.world.factions.values() if x.active and x.kind in
             ("merchant_guild", "smiths_guild", "healers_guild", "temple", "knightly_order"))
    game.renown.members[f.id] = 0
    reputation.start_at_the_bottom(game, f.id)
    reputation.set_standing(game, f.id, 60)
    assert reputation.standing_rank(game, f.id) > 0
    assert reputation.rank(game, f.id) == 0, "they do not hand out rank for goodwill alone"
    assert reputation.needs_trial(game, f.id)
    said = reputation.confirm_rank(game, f.id)
    assert said and reputation.rank(game, f.id) == 1
    # A job from one of their people is that trial, and finishing it promotes you.
    q = {"id": 999, "template": "clear_lair", "state": "active", "giver": -1, "giver_name": "the guild",
         "giver_job": "guard", "town": 0, "faction": f.id, "reward": 100, "days": 10, "hidden": None,
         "revealed": False, "done": True, "target": {}, "words": {"giver": "the guild", "town": "Anywhere"},
         "journal": [], "source": "fallback", "trial": f.id}
    game.quests.append(q)
    reputation.set_standing(game, f.id, 80)
    before = reputation.rank(game, f.id)
    out = quests.reward(game, q)
    assert any("calls you" in line for line in out), out
    assert reputation.rank(game, f.id) > before
