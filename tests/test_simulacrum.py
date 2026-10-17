"""Simulacrum (Expansion 3 G.3): the copy of a person (half the maximum, only what is worn, in snow), a second casting
unmaking the first, the copy in a real fight (beside its maker, right after them, a construct that healing does not
touch, melting at 0, never among the dead), its slots spent for good, the repair at a long rest and its cap, the copy
of a herd beast and of a prisoner (servants, in towns too), the Auto playing it, the record kept in a save."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import fight as game_fight
from realmwalker.game import servants
from realmwalker.rules import simulacrum as sim
from realmwalker.rules import servants as servant_rules
from realmwalker.rules import spells as sp
from realmwalker.rules import tactics
from realmwalker.rules.character import Character
from realmwalker.rules.combat import PARTY
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import check
from realmwalker.rules.inventory import add_item
from realmwalker.rules.progression import long_rest
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.test_servants import cast, game_with, hero, in_the_wild, subject
from tests.test_spells_road6 import in_town
from tests.worlds import cached_world


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Lastrites", 37, "small"), tables)


@pytest.fixture(autouse=True)
def wizards_know_it(monkeypatch):
    real = sp.known_spells

    def known(char, tables):
        out = real(char, tables)
        return list(dict.fromkeys(out + ["simulacrum"])) if char.cls == "wizard" else out

    monkeypatch.setattr(sp, "known_spells", known)


def maker(tables, world, *more):
    wiz = hero(tables)
    add_item(wiz, tables.items, "ruby_dust", 3)
    game = game_with(world, tables, wiz, *more)
    in_the_wild(game)
    return game, wiz


def fighter_of(b, name):
    return next(f for f in b.fighters if f.char is not None and f.char.name == name)


def copy_in(b):
    return next(f for f in b.fighters if sim.snow(f))


def test_the_spell_is_in_and_the_start_up_check_knows_it(tables):
    s = tables.spells["simulacrum"]
    assert s["level"] == 7 and s["school"] == "illusion" and s["minutes"] == 720
    assert s["material"]["items"] == ["ruby_dust"] and s["material"]["consumed"]
    assert sp.road_use(tables, "simulacrum") == "simulacrum"
    assert not [p for p in check.problems(tables) if "simulacrum" in str(p)]


def test_a_copy_of_oneself_has_half_the_maximum_and_only_what_is_worn(world, tables):
    game, wiz = maker(tables, world)
    wiz.money = 5000
    worn = {wiz.item(uid).def_id for uid in wiz.equipped.values()}
    dust = sum(i.qty for i in wiz.inventory if i.def_id == "ruby_dust")
    t0 = game.world.time
    lines = cast(game, wiz, "simulacrum", subject(game, wiz, "simulacrum", wiz.name))
    assert lines and game.world.time - t0 >= 700, "twelve hours of work"
    assert sum(i.qty for i in wiz.inventory if i.def_id == "ruby_dust") == dust - 1, "the ruby dust is consumed"
    rec = sim.record(wiz)
    copy = sim.copy_char(rec)
    assert rec["of"] == wiz.name and copy.name == sim.name_for(wiz.name)
    assert copy.max_hp == wiz.max_hp // 2 and copy.hp == copy.max_hp
    assert {i.def_id for i in copy.inventory} == worn and all(not i.magic for i in copy.inventory)
    assert copy.money == 0 and not copy.attuned and not copy.companion
    assert "simulacrum" not in copy.spells.get("spellbook", []) and "simulacrum" not in copy.spells
    assert copy.level == wiz.level and copy.abilities == wiz.abilities


def test_a_second_casting_unmakes_the_first(world, tables):
    friend = hero(tables, "fighter", seed=4)
    friend.name = "Brannoc Hale"
    game, wiz = maker(tables, world, friend)
    cast(game, wiz, "simulacrum", subject(game, wiz, "simulacrum", wiz.name))
    lines = cast(game, wiz, "simulacrum", subject(game, wiz, "simulacrum", friend.name))
    assert any("unmakes the first" in ln for ln in lines)
    assert sim.record(wiz)["of"] == friend.name
    servant_rules.add(wiz, tables, "mule", sim.SPELL, until=None, now=0, word=False, max_hp=5, type="construct")
    assert sim.destroy(wiz) and sim.record(wiz) is None and not servant_rules.of_spell(wiz, sim.SPELL)


def test_the_copy_fights_beside_its_maker_and_melts_at_nothing(world, tables):
    game, wiz = maker(tables, world)
    cast(game, wiz, "simulacrum", subject(game, wiz, "simulacrum", wiz.name))
    rng = RNG(5, "foes")
    b = game_fight.start_battle(game, [spawn(tables, "bandit", rng, 1)], "A fight.")
    me, snow = fighter_of(b, wiz.name), copy_in(b)
    assert snow.side == PARTY and snow.kind == "construct" and snow.bond["owner"] == me.id
    assert b.order.index(snow.id) == b.order.index(me.id) + 1, "it acts right after its maker"
    assert b.gap(me, snow) <= 2
    snow.hp -= 5
    was = snow.hp
    b._heal(snow, 10)
    assert snow.hp == was, "healing does nothing to snow"
    b._apply_hp_loss(snow, snow.hp + 1, source=None, cause="test")
    assert snow.state == "dead" and snow.death_saves == [0, 0], "it melts, no death saves"
    assert snow.char not in b.result().party_dead
    for f in b.fighters:
        if f.side != PARTY:
            f.creature.hp, f.creature.alive, f.state, f.hp = 0, False, "dead", 0
    b._check_end()
    game_fight.finish_battle(game)
    assert sim.record(wiz) is None, "melted for good"
    assert wiz.alive and wiz in game.party


def test_what_the_fight_takes_stays_taken_slots_and_hit_points(world, tables):
    game, wiz = maker(tables, world)
    cast(game, wiz, "simulacrum", subject(game, wiz, "simulacrum", wiz.name))
    before = sim.copy_char(sim.record(wiz))
    b = game_fight.start_battle(game, [spawn(tables, "bandit", RNG(6, "f"), 1)], "A fight.")
    snow = copy_in(b)
    from tests.test_wave4 import my_turn

    my_turn(b, snow)
    foe = next(f for f in b.fighters if f.side != PARTY)
    assert b.do_cast(snow, "magic_missile", foe) is not False
    snow.hp -= 3
    for f in b.fighters:
        if f.side != PARTY:
            f.creature.hp, f.creature.alive, f.state, f.hp = 0, False, "dead", 0
    b._check_end()
    game_fight.finish_battle(game)
    after = sim.copy_char(sim.record(wiz))
    assert after.hp <= before.hp - 3
    assert sp.slots_left(after, tables) != sp.slots_left(before, tables), "a slot spent is spent for good"
    long_rest(wiz, tables, RNG(1))
    assert sp.slots_left(sim.copy_char(sim.record(wiz)), tables) == sp.slots_left(after, tables)


def test_the_repair_at_a_long_rest_costs_100_gp_a_hit_point_and_half_the_purse_at_most(world, tables):
    game, wiz = maker(tables, world)
    cast(game, wiz, "simulacrum", subject(game, wiz, "simulacrum", wiz.name))
    rec = sim.record(wiz)
    rec["char"]["hp"] = rec["char"]["max_hp"] - 10
    wiz.money = 2 * 4 * sim.REPAIR  # (half of it pays for 4 hit points)
    lines = long_rest(wiz, tables, RNG(1))
    assert any("powders" in ln for ln in lines)
    assert sim.missing(rec) == 6 and wiz.money == 4 * sim.REPAIR
    wiz.money = 100 * sim.REPAIR
    long_rest(wiz, tables, RNG(1))
    assert sim.missing(rec) == 0 and wiz.money == 94 * sim.REPAIR
    wiz.money = 0
    rec["char"]["hp"] -= 1
    assert any("not the coin" in ln for ln in long_rest(wiz, tables, RNG(1)))


def test_a_herd_beast_and_a_prisoner_are_copied_as_servants_that_go_into_towns(world, tables):
    game, wiz = maker(tables, world)
    game.leader.animals.append({"kind": "mule", "name": "Bess", "unfed": 0, "bought": 0})
    game.renown.flags.setdefault("captives", []).append({"def_id": "bandit", "name": "Orrin", "reward": 0,
                                                         "since": 0, "faction": -1})
    subs = {s.ref: s for s in sp_subjects(game, wiz)}
    assert "mule" in subs and "bandit" in subs
    cast(game, wiz, "simulacrum", subs["mule"])
    rec = servant_rules.of_spell(wiz, sim.SPELL)[0]
    assert rec["cid"] == "mule" and rec["type"] == "construct"
    assert rec["max_hp"] == max(1, servant_rules.avg_hp(tables, "mule") // 2)
    cast(game, wiz, "simulacrum", subs["bandit"])
    rows = servant_rules.of_spell(wiz, sim.SPELL)
    assert len(rows) == 1 and rows[0]["cid"] == "bandit", "the mule's copy melted"
    in_town(game)
    assert not servants.here(game) and servants.following(game), "a snow likeness walks into town"
    b = game_fight.start_battle(game, [spawn(tables, "bandit", RNG(3, "w"), 1)], "A fight in town.")
    snow = copy_in(b)
    assert snow.kind == "construct" and snow.creature.def_id == "bandit"
    was = snow.hp
    b._heal(snow, 5)
    assert snow.hp == was


def sp_subjects(game, wiz):
    from realmwalker.game import magic

    return magic.road_targets(game, wiz, "simulacrum")


def test_the_auto_plays_the_copy(world, tables):
    game, wiz = maker(tables, world)
    cast(game, wiz, "simulacrum", subject(game, wiz, "simulacrum", wiz.name))
    b = game_fight.start_battle(game, [spawn(tables, "bandit", RNG(8, "f"), i + 1) for i in range(2)], "A fight.")
    snow = copy_in(b)
    from tests.test_wave4 import my_turn

    my_turn(b, snow)
    snow.auto = True
    tactics.take_turn(b, snow)
    assert any(e.get("who") == snow.id or e.get("by") == snow.id or e.get("from") == snow.id for e in b.events)


def test_the_record_is_kept_in_a_save(world, tables):
    game, wiz = maker(tables, world)
    cast(game, wiz, "simulacrum", subject(game, wiz, "simulacrum", wiz.name))
    back = Character.from_dict(wiz.to_dict())
    assert sim.copy_char(sim.record(back)).max_hp == wiz.max_hp // 2
