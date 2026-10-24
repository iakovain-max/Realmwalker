"""The fallen, blood and graves (Expansion 6 B.5, docs/ADVENTURES.md §8.14): a fight in a town's street leaves its dead
and its blood where they fell (game/remains.py, written back through Field.origin); the party stands where its leader
stood; the town carries its dead off after a day and buries its own; in the wild the dead become bones; blood fades;
the caps hold."""

import copy

import pytest

from realmwalker.game import fight, remains, townlife
from realmwalker.game.encounters import make_encounter
from realmwalker.game.state import new_game
from realmwalker.rules.combat import FOE, PARTY
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.test_townlife import go_to
from tests.worlds import cached_world


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Lifeland", 33, "small", history=40), tables)


def _street_fight(game):
    """Bandits in the street of the town you stand in, fought and won: every foe dead where it stood."""
    enc = make_encounter(game, "bandits", game.world.rng.child("street"))
    battle = fight.start_battle(game, enc.creatures, enc.intro, title="Bandits")
    foes = [f for f in battle.fighters if f.side == FOE]
    for f in foes:
        battle._hit(None, f, 1, "slashing", crit=False, weapon="a knife")
        f.hp, f.state = 0, "dead"
    battle.outcome = "victory"
    return battle, foes


def test_a_street_fight_s_dead_lie_where_they_fell(made, tables):
    game = new_game(copy.deepcopy(made), tables)
    game.survival = False
    townlife.forget()
    go_to(game)
    lm = game.local
    battle, foes = _street_fight(game)
    assert getattr(battle.field, "cut_from", None) == lm.key
    ox, oy = battle.field.origin
    where = {(f.x + ox, f.y + oy) for f in foes}
    lead = next(f for f in battle.fighters if f.side == PARTY and f.char is game.leader)
    stood = (lead.x + ox, lead.y + oy)
    fight.finish_battle(game)
    bodies = lm.meta["bodies"]
    assert {(b["x"], b["y"]) for b in bodies} == where, "each where it fell"
    assert all("creature" in b["who"] for b in bodies)
    decals = lm.meta["decals"]
    assert all(f"{x},{y}" in decals for x, y in where), "blood under the dead"
    assert (game.player.lx, game.player.ly) == stood, "the party stands where its leader stood"
    # A day later the town has carried them away; tomorrow's blood is fading, and in a week it is gone.
    game.world.time += 1440 + 10
    remains.tick(game, lm)
    assert not lm.meta["bodies"]
    assert all(0 < remains.blood_alpha(game.world.time / 1440.0, rec) < 1 for rec in decals.values())
    game.world.time += 1440 * 7
    remains.tick(game, lm)
    assert not lm.meta["decals"], "the blood is washed away in a week"


def test_the_town_buries_its_own(made, tables):
    game = new_game(copy.deepcopy(made), tables)
    game.survival = False
    townlife.forget()
    s = go_to(game)
    lm = game.local
    from realmwalker.game.people import npcs_in

    dead = [n for n in npcs_in(game.world, s.id) if n.alive][:3]
    day = game.world.time / 1440.0
    for i, n in enumerate(dead):
        n.alive = False
        lm.meta.setdefault("bodies", []).append({"x": n.x, "y": n.y, "who": {"npc": n.id}, "angle": 90, "day": day,
                                                 "side": "town"})
    game.world.time += 1500
    lines = remains.tick(game, lm)
    graves = lm.meta["graves"]
    assert len(graves) == len(dead), "a fresh grave each"
    for g in graves:
        assert lm.terrain_ids[int(lm.terrain[g["x"], g["y"]])] == "grave_fresh"
        assert lm.building_at(g["x"], g["y"]) is None
    assert lines, "you are told, being there"
    from tests.test_place_marks import _as_tables_order
    from tests.test_towns import check_works

    check_works(_as_tables_order(lm, tables), tables, "graves dug")


def test_in_the_wild_the_dead_become_bones_and_the_caps_hold(made, tables):
    game = new_game(copy.deepcopy(made), tables)
    game.survival = False
    w = game.world
    spot = next((x, y) for s in w.settlements for x, y in ((s.x + 3, s.y + 3), (s.x - 3, s.y + 2), (s.x + 2, s.y - 3))
                if w.in_bounds(x, y) and w.settlement_at(x, y) is None and w.site_at(x, y) is None
                and game.biome_key(x, y) not in ("ocean", "lake"))
    game.player.local_key = None
    game.player.x, game.player.y = spot
    lm = game.enter_local()
    walk = tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    spots = [(x, y) for x in range(lm.width) for y in range(lm.height) if walk[x, y]][:80]
    assert len(spots) == 80, (lm.kind, int(walk.sum()))
    day = game.world.time / 1440.0
    lm.meta["bodies"] = [{"x": x, "y": y, "who": {"creature": "wolf"}, "angle": 90, "day": day, "side": "foe"}
                         for x, y in spots]
    lm.meta["decals"] = {f"{i},{0}": ["blood", day, 0] for i in range(500)}
    remains._caps(lm)
    assert len(lm.meta["bodies"]) == remains.BODIES and len(lm.meta["decals"]) == remains.DECALS
    game.world.time += 1440 * 2 + 10
    remains.tick(game, lm)
    assert not lm.meta["bodies"]
    x, y = spots[-1]
    assert lm.terrain_ids[int(lm.terrain[x, y])] == "bones" or lm.building_at(x, y) is not None, "bones"
