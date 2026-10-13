"""Blades & Backgrounds part A: arms and armour to the 2024 book (weapons, properties, armour training, improvised
weapons, ammunition) and the weapon masteries."""

import json

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import spells as spellrules
from realmwalker.rules.character import Sheet
from realmwalker.rules.combat import Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import query
from realmwalker.rules.inventory import add_item, equip, unequip
from realmwalker.world.tables import Tables

# PHB 2024 pages 215-217: name -> (damage, mastery, weight, cost in cp)
TABLE = {
    "club": ("1d4", "slow", 2, 10), "dagger": ("1d4", "nick", 1, 200), "greatclub": ("1d8", "push", 10, 20),
    "handaxe": ("1d6", "vex", 2, 500), "javelin": ("1d6", "slow", 2, 50), "light_hammer": ("1d4", "nick", 2, 200),
    "mace": ("1d6", "sap", 4, 500), "quarterstaff": ("1d6", "topple", 4, 20), "sickle": ("1d4", "nick", 2, 100),
    "spear": ("1d6", "sap", 3, 100), "dart": ("1d4", "vex", 0.25, 5), "light_crossbow": ("1d8", "slow", 5, 2500),
    "shortbow": ("1d6", "vex", 2, 2500), "sling": ("1d4", "slow", 0.1, 10), "battleaxe": ("1d8", "topple", 4, 1000),
    "flail": ("1d8", "sap", 2, 1000), "glaive": ("1d10", "graze", 6, 2000), "greataxe": ("1d12", "cleave", 7, 3000),
    "greatsword": ("2d6", "graze", 6, 5000), "halberd": ("1d10", "cleave", 6, 2000), "lance": ("1d10", "topple", 6, 1000),
    "longsword": ("1d8", "sap", 3, 1500), "maul": ("2d6", "topple", 10, 1000), "morningstar": ("1d8", "sap", 4, 1500),
    "pike": ("1d10", "push", 18, 500), "rapier": ("1d8", "vex", 2, 2500), "scimitar": ("1d6", "nick", 3, 2500),
    "shortsword": ("1d6", "vex", 2, 1000), "trident": ("1d8", "topple", 4, 500), "warhammer": ("1d8", "push", 5, 1500),
    "war_pick": ("1d8", "sap", 2, 500), "whip": ("1d4", "slow", 3, 200), "blowgun": ("1", "vex", 1, 1000),
    "hand_crossbow": ("1d6", "vex", 3, 7500), "heavy_crossbow": ("1d10", "push", 18, 5000),
    "longbow": ("1d8", "slow", 2, 5000), "musket": ("1d12", "slow", 10, 50000), "pistol": ("1d10", "vex", 3, 25000),
}


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def hero(tables, cls="fighter", seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("soldier")
    return b.build()


def wield(tables, c, def_id, slot=None):
    it = add_item(c, tables.items, def_id)
    ok, why = equip(c, tables.items, it.uid, slot)
    assert ok, why
    return it


def fight(tables, c, *foes, seed=1, at=(4, 4)):
    rng = RNG(seed, "foes")
    crs = [spawn(tables, d, rng, i + 1) for i, d in enumerate(foes)]
    spots = {0: (3, 4)} | {i + 1: (at[0], at[1] + i) for i in range(len(crs))}
    b = Battle(tables, [c], crs, Env(), RNG(seed, "battle"), spots=spots)
    b.start("Test fight.")
    return b


# ---------------------------------------------------------------------------- A.1 the weapon table
def test_every_weapon_of_the_2024_table_is_there_with_its_mastery(tables):
    for wid, (damage, mastery, weight, cost) in TABLE.items():
        d = tables.items.get(wid)
        assert d["damage"] == damage and d["mastery"] == mastery, wid
        assert d["weight"] == weight and d["value"] == cost, wid
    assert tables.items.get("war_pick")["versatile"] == "1d10"
    assert {"finesse", "reach"} <= set(tables.items.get("whip")["properties"])
    assert tables.items.get("blowgun")["ammo"] == "needles"


def test_firearms_are_gnomish_rarities_never_sold_or_found_as_plain_loot(data, tables):
    for wid in ("musket", "pistol", "firearm_bullets"):
        assert tables.items.get(wid).get("rare")
    shops = json.dumps(data["economy.json"]["shops"])
    assert "musket" not in shops and "pistol" not in shops
    assert "musket" not in json.dumps(data["items.json"]["starting_packs"])


def test_heavy_weapons_want_strength_15_or_dexterity_13(tables):
    c = hero(tables)
    wield(tables, c, "greataxe")
    b = fight(tables, c, "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    opt = next(o for o in b.attack_options(me) if o.key == "main")
    c.abilities["str"] = 14
    assert "too heavy" in query.attack_roll(b, me, foe, opt).notes
    c.abilities["str"] = 15
    assert "too heavy" not in query.attack_roll(b, me, foe, opt).notes


def test_a_blowgun_needle_does_one_point_and_the_dexterity(tables):
    c = hero(tables)
    wield(tables, c, "blowgun")
    add_item(c, tables.items, "needles", 10)
    b = fight(tables, c, "bandit", at=(6, 4))
    opt = next(o for o in b.attack_options(b.fighters[0]) if o.key == "main")
    assert opt.damage == str(max(1, 1 + Sheet(c, tables).mod("dex")))
    assert opt.available


def test_armour_and_shields_need_training(tables):
    c = hero(tables, "wizard")
    assert "heavy" not in c.armor_prof and "shield" not in c.armor_prof
    before = Sheet(c, tables).armor_class()
    wield(tables, c, "shield")
    assert Sheet(c, tables).armor_class() == before  # no training: the shield gives nothing
    wield(tables, c, "chain_mail")
    ok, why = spellrules.can_cast(c, tables, next(s for s, sp in tables.spells.defs.items()
                                                    if sp["level"] == 0 and "wizard" in sp.get("classes", ())))
    assert not ok and "armour" in why
    b = fight(tables, c, "bandit")
    me = b.fighters[0]
    assert query.untrained_armour(me)
    assert "untrained in armour" in query.save_roll(b, me, "dex").roll.notes
    assert "untrained in armour" not in query.save_roll(b, me, "wis").roll.notes
    unequip(c, "armor")
    assert spellrules.armour_problem(c, tables) == ""


def test_a_bow_swung_at_close_quarters_is_an_improvised_weapon(tables):
    c = hero(tables)
    wield(tables, c, "longbow")
    b = fight(tables, c, "bandit")
    bash = next(o for o in b.attack_options(b.fighters[0]) if o.key == "bash")
    s = Sheet(c, tables)
    assert bash.is_melee and bash.damage.startswith("1d4") and bash.bonus == s.mod("str") + s.attack_condition()


def test_half_the_arrows_are_found_after_a_won_fight(tables):
    c = hero(tables)
    wield(tables, c, "shortbow")
    add_item(c, tables.items, "arrows", 20)
    b = fight(tables, c, "bandit", at=(9, 4))
    me, foe = b.fighters[0], b.fighters[1]
    opt = next(o for o in b.attack_options(me) if o.key == "main")
    for _ in range(5):
        b._spend_shot(me, opt)
    assert sum(i.qty for i in c.inventory if i.def_id == "arrows") == 15
    b.outcome = "victory"
    found = [i for i in b.result().loot_items if i.def_id == "arrows"]
    assert sum(i.qty for i in found) == 2


def test_a_loading_weapon_fires_once_an_action_even_with_extra_attack(tables):
    c = hero(tables)
    wield(tables, c, "heavy_crossbow")
    add_item(c, tables.items, "bolts", 10)
    b = fight(tables, c, "ogre", at=(8, 4))
    me, foe = b.fighters[0], b.fighters[1]
    b.order = [me.id] + [x for x in b.order if x != me.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    me.attacks_left = 0
    opt = next(o for o in b.attack_options(me) if o.key == "main")
    query_attacks = query.attacks_per_action
    try:
        query.attacks_per_action = lambda f: 2
        assert b.do_attack(me, opt, foe)
        assert me.attacks_left == 1
        assert "loaded again" in b.attack_problem(me, opt, foe)
    finally:
        query.attacks_per_action = query_attacks


def test_armour_takes_minutes_to_put_on(tables):
    from types import SimpleNamespace

    from realmwalker.game import gear
    from realmwalker.rules.items import Item

    game = SimpleNamespace(tables=tables)
    assert gear.don_minutes(game, Item(0, "plate_armor"), True) == 10
    assert gear.don_minutes(game, Item(0, "plate_armor"), False) == 5
    assert gear.don_minutes(game, Item(0, "chain_shirt"), True) == 5
    assert gear.don_minutes(game, Item(0, "leather_armor"), False) == 1
    assert gear.don_minutes(game, Item(0, "shield"), True) == 0


# ---------------------------------------------------------------------------- A.2 the weapon masteries
from realmwalker.rules import describe, progression  # noqa: E402
from realmwalker.rules.engine import actions  # noqa: E402
from realmwalker.rules.engine.handlers import mastery  # noqa: E402


def soft(f, ac=1, hp=300):
    """A foe that is easy to hit and hard to kill (so a test can watch the trick land)."""
    f.cdef = dict(f.cdef, ac=ac)
    f.creature.max_hp = f.creature.hp = hp


def strike(b, me, foe, opt, *, want_hit=True, tries=60):
    """Swing until a blow lands (or misses), and return the events it made."""
    for _ in range(tries):
        start = len(b.events)
        b._attack(me, opt, foe)
        evs = b.events[start:]
        hit = any(e["kind"] == "attack" and e.get("to") == foe.id and e["hit"] for e in evs)
        if hit == want_hit:
            return evs
    raise AssertionError("never landed")


def main_opt(b, me):
    return next(o for o in b.attack_options(me) if o.key == "main")


def tricks(evs):
    return [e["trick"] for e in evs if e["kind"] == "mastery"]


def armed(tables, weapon, *, cls="fighter", seed=1, also=()):
    c = hero(tables, cls, seed=seed)
    for slot in ("main_hand", "off_hand"):
        unequip(c, slot)
    wield(tables, c, weapon)
    c.masteries = [weapon, *also]
    return c


def test_fighters_and_rogues_master_their_kit_weapons_and_change_them_after_a_long_rest(tables):
    f = hero(tables, "fighter")
    assert len(f.masteries) == 3 and "weapon_mastery" in f.features
    assert len(hero(tables, "rogue").masteries) == 2
    w = hero(tables, "wizard")
    assert w.masteries == [] and progression.mastery_count(w, tables) == 0
    assert progression.relearn_masteries(f, tables)
    choice = f.pending[-1]
    assert f.masteries == [] and choice["kind"] == "mastery" and choice["count"] == 3
    assert all(":" in label for _, label, _ in progression.options(f, tables, choice))
    for _ in range(3):
        progression.resolve(f, tables, choice, progression.options(f, tables, choice)[0][0])
    assert len(f.masteries) == 3 and not any(c["kind"] == "mastery" for c in f.pending)
    assert not progression.relearn_masteries(f, tables)  # once, until the next long rest
    progression.long_rest(f, tables, RNG(1, "rest"))
    assert f.uses["mastery_change"] == 1


def test_a_fourth_mastery_comes_at_level_four(tables):
    f = hero(tables, "fighter")
    for _ in range(3):
        progression.level_up(f, tables, RNG(2, "lv"))
    assert any(c["kind"] == "mastery" and c["count"] == 1 for c in f.pending)
    progression.auto_resolve(f, tables)
    assert len(f.masteries) == 4


def test_topple_knocks_down_and_the_prone_are_struck_with_advantage(tables):
    b = fight(tables, armed(tables, "maul"), "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    soft(foe)
    opt = main_opt(b, me)
    assert any(o.id == "attack:main" and "(Topple)" in o.name for o in actions.options(b, me))
    seen = []
    for _ in range(40):
        seen += tricks(strike(b, me, foe, opt))
        if "prone" in foe.conditions:
            break
    assert "prone" in foe.conditions and "topple" in seen
    assert query.attack_roll(b, me, foe, opt).mode == "advantage"


def test_push_drives_the_foe_ten_feet_back(tables):
    b = fight(tables, armed(tables, "warhammer"), "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    soft(foe)
    evs = strike(b, me, foe, main_opt(b, me))
    assert "push" in tricks(evs) and (foe.x, foe.y) == (6, 4)


def test_sap_spoils_the_next_blow(tables):
    b = fight(tables, armed(tables, "mace"), "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    soft(foe)
    strike(b, me, foe, main_opt(b, me))
    blow = b.attack_options(foe)[0]
    assert "sapped" in query.attack_roll(b, foe, me, blow).notes
    assert "sapped" in [s.id for s in describe.statuses(foe, b)]
    b._attack(foe, blow, me)
    assert "sapped" not in query.attack_roll(b, foe, me, blow).notes  # spent on that roll


def test_vex_gives_the_next_blow_advantage(tables):
    b = fight(tables, armed(tables, "rapier"), "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    soft(foe)
    opt = main_opt(b, me)
    assert "vex" in tricks(strike(b, me, foe, opt))
    assert "vexed" in query.attack_roll(b, me, foe, opt).notes
    assert "vexing" in [s.id for s in describe.statuses(me, b)]


def test_slow_takes_ten_feet_once_however_often_it_lands(tables):
    b = fight(tables, armed(tables, "club"), "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    soft(foe)
    base = query.speed(foe)
    strike(b, me, foe, main_opt(b, me))
    strike(b, me, foe, main_opt(b, me))
    assert query.speed(foe) == base - 10


def test_graze_still_cuts_on_a_miss(tables):
    c = armed(tables, "greatsword")
    c.abilities["str"] = 16
    b = fight(tables, c, "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    soft(foe, ac=30)
    before = foe.hp
    strike(b, me, foe, main_opt(b, me), want_hit=False)
    assert before - foe.hp == 3


def test_cleave_carries_into_the_next_foe_once_a_turn(tables):
    b = fight(tables, armed(tables, "greataxe"), "bandit", "bandit")  # both beside the fighter
    me, a, other = b.fighters
    soft(a)
    soft(other)
    evs = strike(b, me, a, main_opt(b, me))
    assert "cleave" in tricks(evs)
    assert any(e["kind"] == "attack" and e.get("to") == other.id for e in evs)
    assert "cleave" not in tricks(strike(b, me, a, main_opt(b, me)))


def test_nick_makes_the_off_hand_blow_part_of_the_attack(tables):
    c = armed(tables, "scimitar", also=("dagger",))
    wield(tables, c, "dagger", "off_hand")
    b = fight(tables, c, "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    soft(foe)
    b.order = [me.id] + [x for x in b.order if x != me.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(me)
    assert b.do_attack(me, main_opt(b, me), foe)
    row = next(r for r in b.class_abilities(me) if r[0] == "offhand")
    assert row[2] and "Nick" in row[1]
    bonus = me.bonus
    assert b.do_offhand(me, foe)
    assert me.bonus == bonus  # the bonus action is kept
    assert not b.do_offhand(me, foe)  # one extra blow a turn


def test_a_monster_without_training_uses_no_mastery(tables):
    b = fight(tables, hero(tables), "bandit")
    foe = b.fighters[1]
    assert all(mastery.of(foe, o) is None for o in b.attack_options(foe))


def test_the_auto_uses_its_masteries_in_a_real_fight(tables):
    used = []
    for seed in (1, 2, 3, 4):
        c = armed(tables, "maul", seed=seed)
        c.max_hp = c.hp = 80  # (long enough a fight to see the trick)
        b = fight(tables, c, "bandit", "bandit", at=(8, 3), seed=seed)
        for f in b.fighters:
            if f.side == "party":
                f.auto = True
        for _ in range(3000):
            if b.outcome is not None:
                break
            b.step()
        assert b.outcome is not None
        used += [e["trick"] for e in b.events if e["kind"] == "mastery"]
    assert "topple" in used
