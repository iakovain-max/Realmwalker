"""Blades & Backgrounds part D.1: the 2024 tools and adventuring gear at work (PHB 2024 pp. 220-231): packs that open,
acid, nets, caltrops and ball bearings in a fight, basic poison and antitoxin, gear that helps a search, a trap or a
forced door, a costume, the tool rule (proficiency, and advantage with the skill as well), carried containers, the
gear the road's events ask for, and trinkets."""

import pytest

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.game import camp, dungeon, gear
from realmwalker.rules.character import Sheet
from realmwalker.rules.combat import PARTY
from realmwalker.rules.engine import actions, query
from realmwalker.rules.inventory import add_item
from realmwalker.rules.items import make_trinket, trinket_words
from tests.test_gear import always, drop_all, fight_with, game, person, tables, world  # noqa: F401 (fixtures)


def my_turn(b, me):
    b.order = [me.id] + [x for x in b.order if x != me.id]
    b.turn = 0
    b.turn_started = True
    b._start_of_turn(me)


def first(c, def_id):
    return next(it for it in c.inventory if it.def_id == def_id)


# ---------------------------------------------------------------------------- the data
def test_every_new_item_says_what_it_is_for(tables):
    for iid in ("acid", "net", "caltrops", "ball_bearings", "basic_poison", "antitoxin", "explorers_pack", "pole",
                "magnifying_glass", "portable_ram", "costume", "lamp", "bullseye_lantern", "ladder", "climbers_kit",
                "lock", "quiver", "jug", "alchemists_supplies", "lyre", "dragonchess_set", "yew_wand", "trinket"):
        d = tables.items.get(iid)
        assert d.get("use") or d.get("how") or d.get("pack") or d.get("container") or d.get("carry") or \
            d.get("helps") or d.get("light") or d.get("focus") or d.get("bind") or d.get("impress"), iid
    for iid, d in tables.items.defs.items():
        for def_id, qty in d.get("pack") or []:
            assert def_id in tables.items, (iid, def_id)
    for craft in tables.camping["crafts"].values():
        for def_id, _ in craft["needs"] + craft["gives"]:
            assert def_id in tables.items, def_id
        if craft.get("tool"):
            assert craft["tool"] in tables.items


def test_a_pack_opens_into_its_contents(game, tables):
    c = game.leader
    add_item(c, tables.items, "explorers_pack")
    before = sum(it.qty for it in c.inventory if it.def_id == "torch")
    pack = first(c, "explorers_pack")
    assert gear.use_name(game, pack) == "Open the pack"
    gear.use_item(game, c, pack)
    assert not any(it.def_id == "explorers_pack" for it in c.inventory)
    assert sum(it.qty for it in c.inventory if it.def_id == "torch") > before


# ---------------------------------------------------------------------------- in a fight
def test_acid_and_the_net_are_thrown_at_someone(tables, monkeypatch):
    c = person(tables)
    add_item(c, tables.items, "acid")
    add_item(c, tables.items, "net")
    b = fight_with(tables, c, "bandit")
    me = b.side(PARTY)[0]
    foe = [f for f in b.fighters if f.side != PARTY][0]
    foe.x, foe.y = me.x + 2, me.y
    my_turn(b, me)
    acid = b.throw_value(first(c, "acid"))
    opt = next(o for o in actions.options(b, me) if o.kind == "item" and o.value == acid)
    assert opt.aim == "creature" and foe in opt.targets
    monkeypatch.setattr(b, "_save", lambda *a, **k: False)
    hp = foe.hp
    assert b.do_cast(me, b.throw_value(first(c, "acid")), foe)
    assert foe.hp < hp
    my_turn(b, me)
    assert b.do_cast(me, b.throw_value(first(c, "net")), foe)
    assert "restrained" in foe.conditions


def test_caltrops_and_ball_bearings_lie_in_wait(tables, monkeypatch):
    c = person(tables)
    add_item(c, tables.items, "caltrops")
    add_item(c, tables.items, "ball_bearings")
    b = fight_with(tables, c, "bandit", "bandit")
    me = b.side(PARTY)[0]
    one, two = [f for f in b.fighters if f.side != PARTY]
    my_turn(b, me)
    spot = (me.x + 1, me.y)
    one.x, one.y = me.x + 4, me.y
    assert b.do_cast(me, b.throw_value(first(c, "caltrops")), None, point=spot)
    zone = next(z for z in b.zones if z.kind == "caltrops")
    assert zone.dc == 15 and spot in zone.cells
    monkeypatch.setattr(b, "_save", lambda *a, **k: False)
    hp = one.hp
    b._zones_on(one, start=False)  # (not standing in it: nothing)
    assert one.hp == hp
    one.x, one.y = spot
    one.move_left = 30
    assert b._zones_on(one, start=False)
    assert one.hp == hp - 1 and one.move_left == 0
    my_turn(b, me)
    far = (me.x - 3, me.y)
    if far in b.spell_points(me, b.throw_value(first(c, "ball_bearings"))):
        assert b.do_cast(me, b.throw_value(first(c, "ball_bearings")), None, point=far)
        z = next(z for z in b.zones if z.kind == "bearings")
        two.x, two.y = sorted(z.cells)[0]
        b._zones_on(two, start=False)
        assert "prone" in two.conditions


def test_basic_poison_coats_a_blade_for_one_cut(tables):
    c = person(tables)
    add_item(c, tables.items, "basic_poison")
    b = fight_with(tables, c, "bandit")
    me = b.side(PARTY)[0]
    foe = [f for f in b.fighters if f.side != PARTY][0]
    foe.x, foe.y = me.x + 1, me.y
    my_turn(b, me)
    coat = b.throw_value(first(c, "basic_poison"))
    opt = next(o for o in actions.options(b, me) if o.kind == "item" and o.value == coat)
    assert opt.cost == "bonus"
    assert b.do_cast(me, coat, None)
    assert me.bonus == 0 and me.action > 0 and me.buff_value("poisoned_blade")
    foe.cdef = dict(foe.cdef, ac=1)
    foe.creature.max_hp = foe.creature.hp = foe.hp = 300
    blade = next(o for o in b.attack_options(me) if o.damage_type in ("slashing", "piercing"))
    kinds = []
    real = b._hit
    b._hit = lambda att, t, amount, dtype, **k: kinds.append(dtype) or real(att, t, amount, dtype, **k)
    for _ in range(40):
        if b._attack(me, blade, foe):
            break
    assert not me.buff_value("poisoned_blade")  # spent on the first cut
    assert "poison" in kinds
    kinds.clear()
    for _ in range(40):
        if b._attack(me, blade, foe):
            break
    assert "poison" not in kinds


def test_antitoxin_steadies_a_save_against_poison(game, tables):
    c = game.leader
    add_item(c, tables.items, "antitoxin")
    gear.use_item(game, c, first(c, "antitoxin"))
    assert c.effects.get("antitoxin", 0) > 0
    b = fight_with(tables, c, "bandit")
    me = b.side(PARTY)[0]
    assert query.save_roll(b, me, "con", against=("poisoned",)).roll.advantage
    assert not query.save_roll(b, me, "con").roll.advantage


# ---------------------------------------------------------------------------- gear that helps
def test_a_pole_finds_a_trap_and_a_magnifying_glass_searches_well(game, tables, monkeypatch):
    seen = []
    real = dice.d20
    monkeypatch.setattr(dice, "d20", lambda rng, **k: seen.append(k.get("advantage")) or real(rng, **k))

    class LM:
        features = {}
        kind = "dungeon"
        actors = []

    monkeypatch.setattr(type(game), "local", property(lambda self: LM))
    for c in game.party:
        drop_all(c, "magnifying_glass")
    dungeon.search(game)
    assert seen[-1] is False
    add_item(game.leader, tables.items, "magnifying_glass")
    dungeon.search(game)
    assert seen[-1] is True
    assert dungeon.helps(game, "traps") == (0, "")
    add_item(game.leader, tables.items, "pole")
    assert dungeon.helps(game, "traps")[0] == 5
    add_item(game.leader, tables.items, "portable_ram")
    assert dungeon.helps(game, "force")[0] == 4


def test_tools_add_proficiency_and_the_skill_gives_advantage(game, tables, monkeypatch):
    c = game.leader
    seen = []
    real = dice.d20
    monkeypatch.setattr(dice, "d20", lambda rng, **k: seen.append(k.get("advantage")) or real(rng, **k))
    c.tools = [t for t in c.tools if t != "smiths_tools"]
    plain = camp.tool_bonus(game, c, "athletics", "smiths_tools")
    assert plain == (0, False)
    c.tools.append("smiths_tools")
    bonus, adv = camp.tool_bonus(game, c, "athletics", "smiths_tools")
    assert bonus == Sheet(c, tables).proficiency
    assert adv == ("athletics" in c.skills or "athletics" in c.expertise)
    camp.check(game, "athletics", 10, tool="smiths_tools", tag="t")
    assert seen[-1] is adv


def test_a_quiver_and_a_basket_carry_more(tables):
    c = person(tables)
    before = Sheet(c, tables).pack_carry()
    add_item(c, tables.items, "basket")
    add_item(c, tables.items, "basket")
    add_item(c, tables.items, "quiver")
    gain = float(tables.items.get("basket")["carry"]) + float(tables.items.get("quiver")["carry"])
    assert Sheet(c, tables).pack_carry() == pytest.approx(before + gain)  # (each kind counts once)


def test_the_roads_events_use_ladders_and_climbing_gear(tables):
    asks = set()
    for ev in tables.travel_events.values():
        for opt in ev.get("options", []):
            for def_id, _ in (opt.get("requires") or {}).get("items", []):
                assert def_id in tables.items, def_id
                asks.add(def_id)
    for iid in ("ladder", "climbers_kit", "iron_spikes", "block_and_tackle", "signal_whistle", "string", "chain"):
        assert iid in asks, iid


# ---------------------------------------------------------------------------- trinkets
def test_trinkets_are_kept_and_told(tables):
    rng = RNG(4, "t")
    seen = {make_trinket(tables, rng).name for _ in range(30)}
    assert len(seen) > 15
    t = make_trinket(tables, rng)
    assert trinket_words(tables, t) and tables.items.name(t) == t.name
    c = person(tables, seed=8)
    assert sum(1 for it in c.inventory if it.def_id == "trinket") == 1
