"""Steel & Shadows Part C.2: the Assassin, the Spy and the Spy Master (Monster Manual 2025, pp. 22 and 295): their
numbers, their poisoned blows, the Spy Master's Smoke Bomb thrown to a point, Cunning Action, and where they are met."""

from realmwalker.core.rng import RNG
from realmwalker.rules import tactics
from realmwalker.rules.combat import PARTY, Battle, Env, open_field
from realmwalker.rules.creatures import spawn
from tests.test_gear import person, tables  # noqa: F401 (fixtures)


def fight(tables, foe, seed=4):
    hero = person(tables)
    enemy = spawn(tables, foe, RNG(seed, "f"), 1)
    b = Battle(tables, [hero], [enemy], Env(), RNG(seed, "b"), field=open_field(tables, 24, 14))
    b.start("A test fight.")
    return b, b.side(PARTY)[0], [f for f in b.fighters if f.side != PARTY][0]


def test_their_numbers_are_the_books(tables):
    a = tables.creatures["assassin"]
    assert (a["ac"], a["initiative"], a["cr"], a["xp"], a["pb"]) == (16, 10, 8, 3900, 3)
    assert a["resist"] == ["poison"] and "evasion" in a["traits"] and "cunning_action" in a["traits"]
    assert a["multiattack"] == 3
    sword = next(x for x in a["attacks"] if x["id"] == "shortsword")
    assert sword["extra"] == [{"damage": "5d6", "type": "poison"}]
    s = tables.creatures["spy"]
    assert (s["ac"], s["cr"], s["speeds"].get("climb")) == (12, 1.0, 30)
    m = tables.creatures["spy_master"]
    assert (m["ac"], m["initiative"], m["cr"], m["passive"]) == (19, 9, 10, 21)
    bomb = next(x for x in m["attacks"] if x["id"] == "smoke_bomb")
    assert bomb["area"] == {"shape": "sphere", "size": 20} and bomb["dc"] == 16 and bomb["uses"] == "1/day"


def test_the_assassins_blade_poisons(tables):
    b, me, them = fight(tables, "assassin")
    them.x, them.y = me.x + 1, me.y
    me.hp = 500
    sword = next(o for o in b.attack_options(them) if o.name == "shortsword")
    for _ in range(40):
        if b._attack(them, sword, me) and "poisoned" in me.conditions:
            break
    assert "poisoned" in me.conditions


def test_the_smoke_bomb_bursts_where_it_is_thrown(tables):
    b, me, them = fight(tables, "spy_master")
    me.hp = 500
    them.x, them.y = me.x + 5, me.y  # (25 feet: within the bomb's 30, not beside it)
    bomb = next(o for o in b.attack_options(them) if o.name == "smoke bomb")
    cells = b.area_cells(them, bomb.extra, (me.x, me.y))
    assert (me.x, me.y) in cells and (them.x, them.y) not in cells  # (a sphere round the point, not a cone)
    before = me.hp
    b.area_attack(them, bomb, (me.x, me.y))
    assert me.hp < before
    assert not next(o for o in b.attack_options(them) if o.name == "smoke bomb").available  # (once a day)


def test_cunning_action_runs_to_close_in(tables):
    b, me, them = fight(tables, "assassin")
    them.x, them.y = me.x + 18, me.y
    them.char = None
    for o in b.attack_options(them):
        if not o.is_melee:
            o.available = False
    them.bonus, them.action = 1, 1
    them.move_left = them.speed
    before = them.move_left
    tactics._cunning_first(b, them, [o for o in b.attack_options(them) if o.is_melee])
    assert them.bonus == 0 and (them.move_left > before or them.hidden)


def test_they_are_met_on_the_roads(tables):
    groups = tables.creatures.encounters if hasattr(tables.creatures, "encounters") else None
    import json

    data = json.load(open("data/creatures.json", encoding="utf-8"))["encounters"]
    for gid in ("assassin", "spies", "spy_ring"):
        g = data[gid]
        assert len(g["intro"]) >= 3 and g["road"]
        assert all(m[0] in tables.creatures for m in g["members"])
    assert groups is None or groups


def test_they_are_drawn_as_people(tables):
    figures = tables.sprites["figures"]["creatures"]
    for cid in ("assassin", "spy", "spy_master"):
        assert cid in figures and figures[cid]["held"]
