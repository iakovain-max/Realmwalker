"""The battlefield is the place: cut from the dungeon, the town or the wild you are in, or laid out from the land on
the road; the party in its battle order; the enemy placed as the moment says."""

import copy

import numpy as np
import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import arena, dungeon, fight
from realmwalker.game.encounters import make_encounter
from realmwalker.game.state import new_game
from realmwalker.rules import grid
from realmwalker.rules.combat import FOE, PARTY
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Arenaland", 31, "large"), tables)


def companion(tables, cls, seed):
    b = CharacterBuilder(tables, RNG(seed, "c"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("soldier")
    c = b.build()
    c.companion = {"loyalty": 50}
    return c


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    for i, cls in enumerate(("cleric", "rogue", "wizard")):
        g.party.append(companion(tables, cls, i))
    return g


def sane(b):
    taken = set()
    for f in b.fighters:
        for c in f.cells:
            assert b.field.walk[c], f"{f.name} starts in a wall"
            assert c not in taken, f"{f.name} shares a square"
            taken.add(c)


def go_to(game, biome, road=None):
    w = game.world
    idx = w.biome_ids.index(biome)
    for x, y in np.argwhere(w.biome == idx):
        x, y = int(x), int(y)
        if w.settlement_at(x, y) is not None or w.site_at(x, y) is not None:
            continue
        if road is not None and bool(w.road[x, y]) != road:
            continue
        game.player.x, game.player.y = x, y
        return
    pytest.skip(f"no {biome} to fight in")


# ---------------------------------------------------------------------------- the battle order
def test_the_usual_order_puts_the_fighters_in_front(game):
    cells = arena.formation(game.party)
    rows = {c.cls: cells[i][1] for i, c in enumerate(game.party)}
    assert rows["fighter"] < rows["wizard"] and rows["cleric"] <= rows["wizard"]
    assert len(set(cells)) == len(cells)


def test_moving_someone_swaps_with_whoever_stood_there(game):
    party = game.party
    before = arena.formation(party)
    arena.set_cell(party, 3, before[0])  # the wizard to the leader's square
    after = arena.formation(party)
    assert after[3] == before[0] and after[0] == before[3]
    assert len(set(after)) == len(after)


def test_the_front_row_faces_the_enemy(game):
    go_to(game, "plains", road=False)
    game.encounter = make_encounter(game, "bandits", RNG(2, "e"))
    b = fight.start_battle(game, game.encounter.creatures, "Bandits.")
    sane(b)
    cells = arena.formation(game.party)
    foes = b.side(FOE)
    fx = sum(f.x for f in foes) / len(foes)
    dist = {i: abs(f.x - fx) for i, f in enumerate(b.side(PARTY))}
    front = [i for i, c in enumerate(cells) if c[1] == min(r for _, r in cells)]
    back = [i for i, c in enumerate(cells) if c[1] == max(r for _, r in cells)]
    assert min(dist[i] for i in front) < max(dist[i] for i in back)


# ---------------------------------------------------------------------------- on the road
def test_a_road_fight_is_on_the_road(game):
    go_to(game, "plains", road=True)
    game.encounter = make_encounter(game, "bandits", RNG(3, "e"))
    b = fight.start_battle(game, game.encounter.creatures, "Bandits.")
    sane(b)
    T = game.tables.terrain.index
    assert (b.field.terrain == T["road"]).sum() >= b.field.width
    assert b.field.kind == "wilderness"


def test_the_land_makes_the_field(game):
    go_to(game, "forest")
    game.encounter = make_encounter(game, "wolf_pack", RNG(4, "e"))
    b = fight.start_battle(game, game.encounter.creatures, "Wolves.")
    sane(b)
    trees = sum(1 for x in range(b.field.width) for y in range(b.field.height)
                if "tree" in game.tables.terrain.tags[int(b.field.terrain[x, y])])
    assert trees >= 5, "a fight in a forest has trees in it"
    # And the two sides can reach each other.
    p = b.side(PARTY)[0]
    tree = grid.paths(b.field, (p.x, p.y), 1, 5000, blocked=set(), occupied=set())
    assert any(any(grid.gap((x, y, 1), f.space) <= 1 for (x, y) in tree) for f in b.side(FOE))


def test_caught_asleep_at_camp_they_come_from_all_sides(game):
    go_to(game, "plains", road=False)
    enc = make_encounter(game, "bandits", RNG(5, "e"))
    enc.asleep = True
    game.encounter = enc
    b = fight.start_battle(game, enc.creatures, "They are on you.", surprised=PARTY)
    sane(b)
    T = game.tables.terrain.index
    assert (b.field.terrain == T["campfire"]).any()
    px = sum(f.x for f in b.side(PARTY)) / len(b.side(PARTY))
    py = sum(f.y for f in b.side(PARTY)) / len(b.side(PARTY))
    sides = {(f.x > px, f.y > py) for f in b.side(FOE)}
    assert len(sides) >= 2 or len(b.side(FOE)) < 2, "around you, not in a line"
    assert all(f.surprised for f in b.side(PARTY))
    assert all("prone" in f.conditions for f in b.side(PARTY)), "caught asleep, lying down"


def test_caught_unawares_they_are_bunched_up(game):
    go_to(game, "plains", road=False)
    enc = make_encounter(game, "goblins", RNG(6, "e"))
    enc.spotted_first = True
    game.encounter = enc
    b = fight.encounter_fight(game, ambush=True)
    sane(b)
    foes = b.side(FOE)
    if len(foes) >= 2:
        assert max(b.gap(a, c) for a in foes for c in foes) <= 4
    assert all(f.surprised for f in foes)


# ---------------------------------------------------------------------------- in a place
def test_a_dungeon_fight_is_fought_in_the_dungeon(game):
    site = next(s for s in game.world.sites if game.tables.creatures.site_inhabitants.get(s.kind))
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    dungeon.descend(game, 1)
    lm = game.local
    assert lm.kind == "dungeon" and lm.actors
    band = lm.actors[0]
    b = fight.start_battle(game, band.creatures, "Down here.", actor=band)
    sane(b)
    fld = b.field
    assert fld.kind == "dungeon" and fld.underground and fld.solid.any(), "walls"
    ox, oy = fld.origin
    me = b.side(PARTY)[0]
    assert (me.x + ox, me.y + oy) == (game.player.lx, game.player.ly), "you stand where you stood"
    # The ground is the same as the map's.
    remap = game.remap_for(lm)
    assert np.array_equal(fld.terrain, remap[lm.terrain[ox:ox + fld.width, oy:oy + fld.height]])
    assert b.env.carried_light >= 0


def test_a_fight_in_a_house_is_in_the_house(game):
    s = next((s for s in game.world.settlements if s.kind in ("town", "city")), None)
    if s is None:
        pytest.skip("no town")
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    lm = game.local
    inn = next((bd for bd in lm.buildings if bd.kind == "inn"), lm.buildings[0])
    game.player.lx, game.player.ly = inn.x + inn.w // 2, inn.y + inn.h // 2
    if not game.tables.terrain.walk[game.remap_for(lm)[lm.terrain[game.player.lx, game.player.ly]]]:
        game.player.lx, game.player.ly = inn.door
    rng = RNG(9, "folk")
    man = spawn(game.tables, "commoner", rng, 1)
    b = fight.start_battle(game, [man], "He goes for you.", near=(game.player.lx + 1, game.player.ly))
    sane(b)
    floors = {game.tables.terrain.index[t] for t in ("floor_wood", "floor_stone", "floor_earth")}
    assert np.isin(b.field.terrain, list(floors)).any(), "the floor of the house is in the field"
    assert b.field.kind == "settlement"
    assert b.gap(b.side(PARTY)[0], b.side(FOE)[0]) <= 4, "he was beside you"


def test_the_enemy_can_always_reach_you(game):
    """Even a band whose way to you runs outside the piece of the map that becomes the field comes on from a place
    that connects."""
    site = next(s for s in game.world.sites if game.tables.creatures.site_inhabitants.get(s.kind))
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    dungeon.descend(game, 1)
    lm = game.local
    band = max(lm.actors, key=lambda a: abs(a.x - game.player.lx) + abs(a.y - game.player.ly))
    b = fight.start_battle(game, band.creatures, "Far below.", actor=band)
    sane(b)
    me = b.side(PARTY)[0]
    tree = grid.paths(b.field, (me.x, me.y), 1, 10_000, blocked=set(), occupied=set())
    for f in b.side(FOE):
        assert any(grid.gap((x, y, 1), f.space) <= 1 for (x, y) in tree), f"{f.name} cannot be reached"
