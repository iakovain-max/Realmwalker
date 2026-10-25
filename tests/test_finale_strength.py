"""The finale set by its tier (Expansion 6 E.6, docs/ADVENTURES.md §5.8 rule 1), each piece on its own: the den's band
filled with the tier's guards (never past its size, the weakest giving way), a boss template's might and its floors,
the boss standing its ground in its own den, "fewer of them" sending away half of each kind (strongest first, never a
lieutenant), a finale never fought blind, and the Auto throwing fire at what fears it. The win rates are
tests/test_story_balance.py's (slow)."""

import pytest

from realmwalker.game.story import finale
from realmwalker.rules import encounter, tactics
from realmwalker.rules.combat import FOE, PARTY
from realmwalker.rules.inventory import add_item
from tests.test_finale_arenas import _den, _fight, made, tables  # noqa: F401

pytestmark = pytest.mark.story


def _boss(b):
    return next(f for f in b.side(FOE) if f.creature is not None and (f.creature.story or {}).get("role") == "villain")


def test_the_dens_band_is_set_by_its_tier(made, tables):
    for kind in ("outlaw", "risen"):
        game, adv, band = _den(made, tables, kind)
        spec = dict(finale.strength(tables))
        spec.update(spec["by_kind"].get(kind, {}))
        guards = set(spec["guards"][kind][str(adv["tier"])])
        cs = band.creatures
        assert cs[0].story["role"] == "villain"
        assert len(cs) <= max(spec["most"], 1 + 4), (kind, [c.def_id for c in cs])
        assert any(c.def_id in guards for c in cs[1:]), (kind, [c.def_id for c in cs])
        assert all(c.story and c.story["adv"] == adv["id"] for c in cs), "every one of them is the tale's"
        goal = spec["share"] * encounter.budget(tables, [adv["target_level"]] * 4, spec["difficulty"])
        worth = encounter.xp_of(tables, [c.def_id for c in cs])
        assert worth <= goal + max(int(tables.creatures[g]["xp"]) for g in guards), (kind, worth, goal)


def test_might_and_its_floors():
    d = {"ac": 12, "multiattack": 1, "attacks": [
        {"id": "bite", "kind": "melee", "bonus": 3, "damage": "1d6", "damage_type": "piercing"},
        {"id": "breath", "kind": "melee", "single_save": True, "dc": 12, "damage": "2d6", "damage_type": "fire"}]}
    finale._might(d, {"min_ac": 15, "min_hit": 6, "min_attacks": 3, "damage": "1d8", "hit": 1})
    bite, breath = d["attacks"]
    assert d["ac"] == 15 and d["multiattack"] == 3
    assert bite["bonus"] == 6 and bite["extra"] == [{"damage": "1d8", "type": "piercing"}]
    assert breath["dc"] == 13 and "extra" not in breath, "a save's DC rises with its hit, a blow takes the die"


def test_a_boss_holds_its_ground_in_its_own_den(made, tables):
    game, adv, band = _den(made, tables, "risen", arena="")
    b, boss = _fight(game, adv, band)
    assert boss.cdef.get("holds_ground") and not b.can_leave(boss)
    boss.state = "fleeing"  # (turned: it backs away, but never off the field)
    b.turn = b.order.index(boss.id)
    b.turn_started = True
    tactics.take_turn(b, boss)
    assert boss.state in ("fleeing", "fighting") and b.outcome is None


def test_fewer_of_them_sends_away_the_strongest_first(made, tables):
    game, adv, band = _den(made, tables, "risen", arena="", keys=["ford"])
    b, boss = _fight(game, adv, band)
    gone = [f for f in b.side(FOE) if f.state == "fled"]
    stay = [f for f in b.side(FOE) if f is not boss and f.state == "fighting"]
    assert gone, "half of its minions are not here"
    assert all((f.creature.story or {}).get("role") == "minion" for f in gone), "a lieutenant has its own key"
    minions = [f for f in gone + stay if (f.creature.story or {}).get("role") == "minion"]
    top = max(int(f.cdef["xp"]) for f in minions)
    assert any(int(f.cdef["xp"]) == top for f in gone), "the strongest first"


def test_a_finale_is_never_fought_blind(made, tables):
    game, adv, band = _den(made, tables, "risen", arena="")
    b, boss = _fight(game, adv, band)
    assert any(abs(x - boss.x) <= 1 and abs(y - boss.y) <= 1 for x, y, *_ in b.field.lights), "its end of the hall lit"


def test_the_auto_throws_fire_at_what_fears_it(made, tables, monkeypatch):
    game, adv, band = _den(made, tables, "beast", arena="", keys=["weakness", "means"])
    b, boss = _fight(game, adv, band)
    d = dict(boss.cdef)
    d["vulnerable"] = sorted(set(d.get("vulnerable", [])) | {"fire"})
    boss.cdef = d
    f = next(x for x in b.side(PARTY) if x.char is not None)
    monkeypatch.setattr(tactics, "_best_attack_worth", lambda b_, f_: 2.0)  # (its blows worth little here)
    add_item(f.char, tables.items, "alchemists_fire", 2)
    near = next(((boss.x + dx, boss.y + dy) for dx in range(-4, 5) for dy in range(-4, 5)
                 if 2 <= max(abs(dx), abs(dy)) <= 3 and b.field.in_bounds(boss.x + dx, boss.y + dy)
                 and b.field.passable(boss.x + dx, boss.y + dy)
                 and not any(o.x == boss.x + dx and o.y == boss.y + dy for o in b.fighters)), None)
    if near is None:
        pytest.skip("no room beside the beast")
    f.x, f.y = near
    for x in b.side(PARTY):
        if x is not f and x.state == "fighting":
            x.x, x.y = f.x, f.y  # (out of the way: no friend near the beast)
            x.state = "fled"
    b.turn = b.order.index(f.id)
    b.turn_started = True
    f.action, f.bonus = 1, 1
    assert tactics._throw_flask(b, f), "a flask of fire at a beast that fears it"
    assert any(e["kind"] == "cast" and str(e.get("spell", "")).startswith("thrown") for e in b.events)
