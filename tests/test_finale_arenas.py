"""The finale in full, first half (Expansion 6 E.5, docs/ADVENTURES.md §5.8): the arenas laid where the boss stands
(a throne hall, a ritual circle, a bridge over a chasm, a tower top; the burning village on the land), their change
at the boss's second phase, the telegraphed great attack (marked a turn before, stepped out of, falling on those still
inside), the boss's entrance, the templates at tiers 3-4 and the legendary action that commands its minions - each in a
real fight."""

import copy

import pytest

from realmwalker.game import dungeon, story
from realmwalker.game.state import new_game
from realmwalker.game.story import arenas, finale, forge
from realmwalker.rules.combat import FOE, PARTY
from realmwalker.rules.engine.handlers import bosses
from realmwalker.world import threats
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world

pytestmark = pytest.mark.story


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def made(tables):
    return cached_world(WorldOptions("Forgeland", 77, "medium"), tables)


def _den(made, tables, kind="beast", arena=None, keys=(), tier=None):
    w = copy.deepcopy(made)
    t = next((t for t in threats.records(w).values() if t["kind"] == kind and t["state"] != "ended"), None)
    if t is None:
        pytest.skip(f"no {kind}")
    game = new_game(w, tables)
    game.survival = False
    adv = forge.make(game, t)
    adv["chapter"] = len(adv["chapters"]) - 1
    adv["keys"] = list(keys)
    if arena is not None:
        adv["finale"]["arena"] = arena
    if tier is not None:
        adv["tier"] = tier
    site = w.sites[adv["places"]["home"]["site"]]
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    depth = dungeon.gen.depth_for(w, site)
    dungeon.descend(game, 1)
    while int(game.local.meta.get("level", 1)) < depth:
        dungeon.descend(game, int(game.local.meta["level"]) + 1)
    band = next(a for a in game.local.actors if a.creatures and getattr(a.creatures[0], "story", None))
    for c in game.party:
        c.level = max(c.level, adv["target_level"])
    return game, adv, band


def _fight(game, adv, band):
    # (met in the level's biggest room, you at one end and the band at the other, so the arena has room)
    p = game.player
    rooms = game.local.meta.get("rooms") or []
    if rooms:
        rx, ry, rw, rh = max(rooms, key=lambda r: r[2] * r[3])
        p.lx, p.ly = rx + 1, ry + rh // 2
        band.x, band.y = rx + rw - 2, ry + rh // 2
    else:
        band.x, band.y = _spot_near(game, (p.lx, p.ly), 7)
    game.finale = {"adv": adv["id"], "actor": band.id}
    story.fight_finale(game)
    b = game.battle
    boss = next(f for f in b.side(FOE) if f.creature is not None and (f.creature.story or {}).get("role") == "villain")
    return b, boss


def _spot_near(game, at, dist):
    lm = game.local
    T = game.tables.terrain
    walk = T.walk[game.remap_for(lm)[lm.terrain]]
    best = None
    for x in range(lm.width):
        for y in range(lm.height):
            if walk[x, y] and abs(max(abs(x - at[0]), abs(y - at[1])) - dist) <= 1:
                if not any(a.x == x and a.y == y for a in lm.actors):
                    best = (x, y) if best is None or abs(y - at[1]) < abs(best[1] - at[1]) else best
    return best or at


def _names(b, cells):
    return {b.field.name(*c) for c in cells}


def test_every_blueprints_arenas_are_known_and_worded(tables):
    for bid, bp in tables.adventures["blueprints"].items():
        for a in bp["finale"].get("arenas", ()):
            assert a in arenas.ARENAS and a in arenas.CHANGES and a in tables.adventures["arenas"], (bid, a)
    assert set(arenas.ARENAS) == set(arenas.CHANGES) == set(tables.adventures["arenas"])


def test_the_arena_is_chosen_once_by_the_dungeon_style(made, tables):
    game, adv, band = _den(made, tables, "risen")
    style = game.local.meta.get("style", "")
    pick = arenas.choose(game, adv, style)
    assert pick is None or style in tables.adventures["arenas"][pick]["styles"]
    assert arenas.choose(game, adv, "nowhere") == pick, "chosen once, kept"


@pytest.mark.parametrize("aid", ["throne_hall", "ritual_circle", "bridge", "tower_top"])
def test_an_arena_in_a_real_finale_and_its_change_at_the_second_phase(made, tables, aid):
    from tools.arena import run

    game, adv, band = _den(made, tables, "risen", arena=aid)
    b, boss = _fight(game, adv, band)
    info = b.field.__dict__.get("arena")
    if info is None:
        pytest.skip(f"{aid}: no room for it on this level")
    assert info["id"] == aid
    lead = next(f for f in b.side(PARTY) if f.char is not None)
    tree = b.move_tree(lead, budget=9999)
    assert any(max(abs(sq[0] - boss.x), abs(sq[1] - boss.y)) <= 1 for sq in tree), "the two sides can reach each other"
    marks = info["marks"]
    before = b.field.terrain.copy()
    boss.hp = boss.max_hp // 2 - 1
    bosses.after_damage(b, boss)
    assert any(e.get("kind") == "arena" and e.get("what") == aid for e in b.events), "the arena changed with it"
    if aid == "throne_hall":
        changed = (b.field.terrain != before).any()
        raised = [f for f in b.fighters if f.bond and f.bond.get("kind") == "raised"]
        assert changed and (raised or not marks["sarcophagi"])
        if raised and marks["sarcophagi"]:
            assert "grave" in _names(b, marks["sarcophagi"]), "the coffins stand open"
    elif aid == "ritual_circle":
        assert any(z.kind == "rite" for z in b.zones), "the circle flares into burning ground"
    elif aid == "bridge":
        assert "chasm" in _names(b, marks["chasm"]) and "bridge" in _names(b, marks["bridge"])
    elif aid == "tower_top":
        assert "chasm" in {b.field.name(x, y) for x in range(b.field.width) for y in range(b.field.height)}
    for f in b.side(PARTY):
        f.auto = True
    run(b, max_steps=4000)
    assert b.outcome is not None


def test_the_great_attack_is_marked_a_turn_before_and_falls_where_it_was_marked(made, tables):
    game, adv, band = _den(made, tables, "risen", arena="")
    b, boss = _fight(game, adv, band)
    spec = boss.cdef["boss_great"]
    assert spec["dc"] == finale.great_at(tables.villains["bosses"]["risen"]["great"], adv["tier"])["dc"]
    foe = next(f for f in b.side(PARTY) if f.char is not None)
    b.round = 3
    bosses.turn_start(b, boss)
    omen = next((z for z in b.zones if z.kind == bosses.OMEN), None)
    assert omen is not None and any(c in omen.cells for c in foe.cells), "marked where the party stands"
    assert any(e.get("kind") == "telegraph" for e in b.events)
    assert bosses.in_omen(b, foe)
    hp = foe.hp
    bosses.turn_start(b, boss)  # (its next turn: it falls)
    assert not any(z.kind == bosses.OMEN for z in b.zones)
    ev = next(e for e in b.events if e.get("kind") == "great")
    assert foe.id in ev["hit"] and foe.hp < hp and boss.action == 0


def test_the_auto_steps_out_of_the_omen(made, tables):
    from realmwalker.rules import tactics

    game, adv, band = _den(made, tables, "risen", arena="")
    b, boss = _fight(game, adv, band)
    b.round = 3
    bosses.turn_start(b, boss)
    inside = [f for f in b.side(PARTY) if f.active and bosses.in_omen(b, f)]
    assert inside
    f = inside[0]
    f.move_left = f.speed
    tactics._out_of_harm(b, f)
    assert not bosses.in_omen(b, f), "stepped out before the blow"


def test_held_when_its_turn_comes_the_great_attack_fizzles(made, tables):
    game, adv, band = _den(made, tables, "risen", arena="")
    b, boss = _fight(game, adv, band)
    b.round = 3
    bosses.turn_start(b, boss)
    boss.conditions["stunned"] = 1
    bosses.turn_start(b, boss)
    assert not any(e.get("kind") == "great" for e in b.events)
    assert not any(z.kind == bosses.OMEN for z in b.zones)


def test_the_entrance_and_the_templates_at_tiers_three_and_four(made, tables):
    t1 = finale.at_tier(tables.villains["bosses"]["risen"], 1)
    t4 = finale.at_tier(tables.villains["bosses"]["risen"], 4)
    assert t4["resistances"] > t1["resistances"] and t4["actions"] > t1["actions"] and t4["hp"] > t1["hp"]
    assert "command" in t4["menu"] and "command" not in t1["menu"]
    g = tables.villains["bosses"]["risen"]["great"]
    assert finale.great_at(g, 4)["dc"] > finale.great_at(g, 1)["dc"]
    game, adv, band = _den(made, tables, "risen", arena="", tier=4)
    b, boss = _fight(game, adv, band)
    assert boss.cdef["legendary_resistance"]["per_day"] == t4["resistances"]
    assert any(a.get("command") for a in boss.cdef["legendary"]["actions"])
    assert boss.cdef["boss_great"]["dc"] == finale.great_at(g, 4)["dc"]
    assert any(e.get("kind") == "boss" for e in b.events)


def test_the_captain_commands_its_men(made, tables):
    game, adv, band = _den(made, tables, "outlaw", arena="", tier=2)
    b, boss = _fight(game, adv, band)
    assert any(a.get("command") for a in boss.cdef["legendary"]["actions"])
    men = [f for f in b.side(FOE) if f is not boss and f.active]
    hero = next(f for f in b.side(PARTY) if f.char is not None)
    if not men:
        pytest.skip("the captain alone")
    man = men[0]
    taken = {c for x in b.on_field() if x is not man for c in x.cells}
    man.x, man.y = b._free_near((hero.x + 1, hero.y), man.sq, taken)
    boss.creature.uses["legendary_actions"] = 1
    n = len(b.events)
    assert bosses.command(b, boss, 1)
    ev = next(e for e in b.events[n:] if e.get("kind") == "legendary")
    assert ev["what"] == "command" and ev["who"] == man.id
    assert any(e.get("kind") == "attack" and e.get("by") == man.id for e in b.events[n:])
    assert boss.creature.uses["legendary_actions"] == 0


def test_the_burning_village_on_the_land(made, tables):
    from realmwalker.game import arena as arenamod
    from realmwalker.game import encounters, fire
    from realmwalker.game.fight import start_battle
    from realmwalker.rules.creatures import spawn

    game = new_game(copy.deepcopy(made), tables)
    game.survival = False
    rng = game.world.rng.child("village-test")
    foes = [spawn(tables, "bandit", rng.child(str(i)), i + 1) for i in range(3)]
    game.encounter = encounters.PendingEncounter("bandits", foes, "Bandits!", False, "", field="burning_village")
    start_battle(game, foes, "Bandits!")
    b = game.battle
    assert "burning_village" in arenamod.FIELDS
    assert b.field.__dict__.get("village") and b.field.__dict__.get("burning")
    z = fire._fire_zone(b)
    assert z is not None and z.cells
    names = {b.field.name(x, y) for x in range(b.field.width) for y in range(b.field.height)}
    assert "wall_wood" in names and "floor_wood" in names
    assert b.field.flammable[b.field.terrain == tables.terrain.index["floor_wood"]].all(), "the houses' floors catch"


@pytest.mark.parametrize("aid", ["throne_hall", "ritual_circle", "bridge", "tower_top"])
def test_an_arena_that_does_not_fit_leaves_the_ground_and_a_way_off_always_stays(made, tables, aid):
    import numpy as np

    from realmwalker.core.rng import RNG

    game, adv, band = _den(made, tables, "risen", arena=aid)
    T = tables.terrain
    floor = T.index["floor_stone"]
    for lead, foe in (((2, 8), (20, 8)), ((8, 8), (14, 8)), ((6, 6), (12, 6)), ((10, 8), (15, 9))):
        terrain = np.full((24, 16), floor, np.uint16)
        before = terrain.copy()
        out = arenas.lay(game, adv, "tower", terrain, lead, foe, RNG(5).numpy("t"))
        if out is None:
            assert (terrain == before).all(), "nothing laid, nothing changed"
            continue
        walk = T.walk[terrain]
        seen, todo = {lead}, [lead]
        while todo:
            x, y = todo.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (x + dx, y + dy)
                    if 0 <= n[0] < 24 and 0 <= n[1] < 16 and n not in seen and walk[n]:
                        seen.add(n)
                        todo.append(n)
        assert any(x in (0, 23) or y in (0, 15) for x, y in seen), f"{aid}: a way off the field (law 3)"
