"""Steel & Shadows part B: the Eldritch Knight and the Arcane Trickster - third casters of the wizard's list, War Bond,
War Magic, Eldritch Strike, Arcane Charge, the unseen Mage Hand, Magical Ambush, Versatile Trickster and Spell Thief,
each at work in a real fight or on the road, and in the Auto's hands."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import progression
from realmwalker.rules import spells as sr
from realmwalker.rules.engine import resources as res
from realmwalker.world.tables import Tables

from tests.test_feats import armed


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def path(tables, sub, level=3, seed=1, weapon=None):
    """A fighter (Eldritch Knight) or rogue (Arcane Trickster) of this level, their choices made the Auto's way."""
    cls = "fighter" if sub == "eldritch_knight" else "rogue"
    c = armed(tables, weapon or ("longsword" if cls == "fighter" else "rapier"), cls=cls, level=1, seed=seed)
    c.abilities["int"] = 16
    for _ in range(level - 1):
        progression.level_up(c, tables, RNG(seed, "lv"))
        s = next((p for p in c.pending if p["kind"] == "subclass"), None)
        if s is not None:
            progression.resolve(c, tables, s, sub)
    progression.auto_resolve(c, tables)
    res.fill(c, tables)
    return c


# ---------------------------------------------------------------------------- B.1 third casters
def test_the_third_casters_tables(tables):
    for sub in ("eldritch_knight", "arcane_trickster"):
        c = path(tables, sub, 3)
        assert c.subclass == sub and sr.is_caster(c, tables)
        assert sr.slots_total(c, tables) == [2] and sr.prepared_count(c, tables) == 3
        assert sr.casting_ability(c, tables) == "int" and sr.spell_list(c, tables) == "wizard"
        want = 2 if sub == "eldritch_knight" else 3
        assert len(c.spells["cantrips"]) == want, c.spells
        assert all("wizard" in tables.spells[s]["classes"] for s in c.spells["cantrips"])
        assert len(sr.prepared(c, tables)) == 3
        assert all(tables.spells[s]["level"] == 1 and "wizard" in tables.spells[s]["classes"]
                   for s in sr.prepared(c, tables))
    c = path(tables, "arcane_trickster", 3)
    assert "mage_hand" in c.spells["cantrips"]
    for level, slots, prep, cantrips in ((7, [4, 2], 5, 2), (10, [4, 3], 7, 3), (13, [4, 3, 2], 9, 3),
                                         (19, [4, 3, 3, 1], 12, 3), (20, [4, 3, 3, 1], 13, 3)):
        c = path(tables, "eldritch_knight", level, seed=level)
        assert sr.slots_total(c, tables) == slots and sr.prepared_count(c, tables) == prep
        assert len(c.spells["cantrips"]) == cantrips and len(sr.prepared(c, tables)) == prep
        assert max(tables.spells[s]["level"] for s in sr.prepared(c, tables)) <= len(slots)


def test_the_list_changes_by_level_not_by_rest(tables):
    c = path(tables, "eldritch_knight", 3)
    sr.close_preparing(c)
    progression.long_rest(c, tables, RNG(1, "rest"))
    assert sr.preparing_open(c) == ""
    progression.level_up(c, tables, RNG(1, "lv"))
    assert sr.preparing_open(c) == "prepare"
    w = path(tables, "eldritch_knight", 3)
    assert sr.has_focus(w, tables) in (True, False)  # (an arcane focus serves; asked without error)
    assert sr.focus_kind(w, tables) == "arcane"


def test_a_plain_fighter_and_rogue_cast_nothing(tables):
    for sub, cls in (("champion", "fighter"), ("thief", "rogue")):
        c = armed(tables, "longsword", cls=cls, level=1)
        for _ in range(4):
            progression.level_up(c, tables, RNG(1, "lv"))
            s = next((p for p in c.pending if p["kind"] == "subclass"), None)
            if s is not None:
                progression.resolve(c, tables, s, sub)
        assert not sr.is_caster(c, tables) and not c.spells


# ---------------------------------------------------------------------------- B.2 the Eldritch Knight in a fight
from realmwalker.rules import war_bond  # noqa: E402
from realmwalker.rules.engine import query  # noqa: E402
from realmwalker.rules.engine.handlers import arcane  # noqa: E402
from realmwalker.rules.inventory import add_item, equip  # noqa: E402

from tests.test_feats import fight, main_opt, on_turn, soft  # noqa: E402


def knight(tables, level, cantrips=("fire_bolt", "shocking_grasp"), seed=1, weapon=None):
    c = path(tables, "eldritch_knight", level, seed=seed, weapon=weapon)
    c.spells["cantrips"] = list(cantrips) + [s for s in c.spells["cantrips"] if s not in cantrips][:max(
        0, len(c.spells["cantrips"]) - len(cantrips))]
    return c


def test_war_magic_a_cantrip_in_place_of_an_attack(tables):
    c = knight(tables, 7)
    b = fight(tables, c, "bandit", "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    soft(foe)
    on_turn(b, me)
    assert b.war_magic(me, "fire_bolt", tables.spells["fire_bolt"]) == 1
    assert b.do_cast(me, "fire_bolt", foe)
    assert me.action == 0 and me.attacks_left == 1  # (the other attack of the Attack action is left)
    assert b.do_attack(me, main_opt(b, me), foe) and me.attacks_left == 0
    on_turn(b, me)
    assert b.do_attack(me, main_opt(b, me), foe) and me.attacks_left == 1
    assert b.do_cast(me, "shocking_grasp", foe) and me.attacks_left == 0  # (the second attack, as a cantrip)


def test_no_spell_in_the_middle_of_the_attack_action_without_war_magic(tables):
    c = knight(tables, 5)  # (Extra Attack, no War Magic yet)
    b = fight(tables, c, "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    soft(foe)
    on_turn(b, me)
    assert b.do_attack(me, main_opt(b, me), foe) and me.attacks_left == 1
    assert b.cast_problem(me, "fire_bolt", foe) == "the Attack action is under way: its attacks first"
    assert not b.do_cast(me, "fire_bolt", foe) and me.attacks_left == 1
    on_turn(b, me)
    assert b.do_cast(me, "fire_bolt", foe) and me.action == 0 and me.attacks_left == 0  # (the Magic action)


def test_improved_war_magic_a_spell_for_two_attacks(tables):
    c = knight(tables, 18)
    if "magic_missile" not in c.spells["prepared"]:
        c.spells["prepared"] = ["magic_missile"] + c.spells["prepared"][1:]
    b = fight(tables, c, "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    soft(foe)
    on_turn(b, me)
    assert b.war_magic(me, "magic_missile", tables.spells["magic_missile"]) == 2
    assert b.do_cast(me, "magic_missile", foe) and me.attacks_left == 1  # (three attacks at 18: one left)


def test_eldritch_strike_undercuts_the_next_save(tables):
    c = knight(tables, 10)
    if "hold_person" not in c.spells["prepared"]:
        c.spells["prepared"] = ["hold_person"] + c.spells["prepared"][1:]
    b = fight(tables, c, "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    soft(foe)
    on_turn(b, me)
    for _ in range(40):
        if b._attack(me, main_opt(b, me), foe):
            break
    assert me.id in foe.buff_value("eldritch_struck")
    b._casting = me
    try:
        assert "Eldritch Strike" in query.save_roll(b, foe, "wis").roll.dis
    finally:
        b._casting = None
    assert "Eldritch Strike" not in query.save_roll(b, foe, "wis").roll.dis  # (only against the knight's spells)
    me.attacks_left, me.action = 0, 1
    b.do_cast(me, "hold_person", foe)
    assert me.id not in foe.buff_value("eldritch_struck")  # (spent on that save)


def test_arcane_charge_steps_through_space_to_a_foe(tables):
    c = knight(tables, 15)
    b = fight(tables, c, "bandit", spots={0: (2, 2), 1: (8, 2)})
    me, foe = b.fighters[0], b.fighters[1]
    on_turn(b, me)
    assert b.gap(me, foe) > 1
    b.do_ability(me, "action_surge")
    assert b.gap(me, foe) <= 1 and any(e["kind"] == "teleport" and e.get("who") == me.id for e in b.events)


def test_war_bond_binds_holds_and_calls(tables):
    c = knight(tables, 3, weapon="javelin")
    add_item(c, tables.items, "longsword")
    c.equipped_item("main_hand").qty = 1  # (one javelin bound, not a bundle)
    notes = war_bond.at_rest(c, tables)
    held = c.equipped_item("main_hand")
    assert notes and war_bond.is_bonded(c, held) and len(war_bond.bonds(c)) == 2
    assert war_bond.at_rest(c, tables) == []  # (two at most)
    from realmwalker.rules.engine.handlers import battle_master as bm

    b = fight(tables, c, "bandit", spots={0: (2, 2), 1: (6, 2)})
    me, foe = b.fighters[0], b.fighters[1]
    assert bm.held_weapon(me) == ""  # (never knocked from the hand: Disarming Attack has nothing to take)
    on_turn(b, me)
    throw = next(o for o in b.attack_options(me) if o.key.startswith("throw") and o.item_uid == held.uid)
    b.do_attack(me, throw, foe)
    assert any(war_bond.is_bonded(c, it) for it in b.thrown) and c.equipped_item("main_hand") is None
    assert b.do_ability(me, "call_bonded") is not False
    back = c.equipped_item("main_hand")
    assert back is not None and back.def_id == "javelin" and war_bond.is_bonded(c, back) and not b.thrown


def test_the_auto_calls_the_other_bonded_weapon(tables):
    from realmwalker.rules import tactics

    c = knight(tables, 3, weapon="longbow")
    add_item(c, tables.items, "longsword")
    war_bond.at_rest(c, tables)
    b = fight(tables, c, "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    me.auto = True
    on_turn(b, me)
    assert tactics._arcane_bonus(b, me)
    assert c.equipped_item("main_hand").def_id == "longsword"  # (blades all round: the sword to hand)


# ---------------------------------------------------------------------------- B.3 the Arcane Trickster
def test_magical_ambush_from_hiding(tables):
    c = path(tables, "arcane_trickster", 9)
    b = fight(tables, c, "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    on_turn(b, me)
    me.hidden = 15
    assert arcane.ambush_ready(b, me)
    me.__dict__["ambush_turn"] = (b.round, b.turn)
    b._casting = me
    try:
        assert "Magical Ambush" in query.save_roll(b, foe, "wis").roll.dis
    finally:
        b._casting = None


def test_the_unseen_hand_and_versatile_trickster(tables, monkeypatch):
    c = path(tables, "arcane_trickster", 13)
    b = fight(tables, c, "bandit", "bandit", spots={0: (3, 4), 1: (4, 4), 2: (5, 4)})
    me, a, other = b.fighters[0], b.fighters[1], b.fighters[2]
    on_turn(b, me)
    assert b.do_ability(me, "unseen_hand", other) is not False
    tok = arcane.hand_of(b, me)
    assert tok is not None and (tok.x, tok.y) == (other.x, other.y) and me.bonus == 0
    monkeypatch.setattr(type(b), "_save", lambda self, *a, **k: False)
    arcane.trip_beside_hand(b, me, a, 15)
    assert "prone" in other.conditions


def test_spell_thief_turns_a_spell(tables, monkeypatch):
    c = path(tables, "arcane_trickster", 17)
    res.fill(c, tables)
    c.spells["prepared"] = [s for s in c.spells["prepared"] if s != "counterspell"]  # (Spell Thief, not a slot)
    b = fight(tables, c, "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    foe.cdef = dict(foe.cdef, spells=["magic_missile"])
    hp = me.hp
    monkeypatch.setattr(type(b), "_save", lambda self, *a, **k: False)
    b.cast(foe, "magic_missile", tables.spells["magic_missile"], me, None, up=0, mod=3, dc=13, bonus=5, mult=1,
           level=1)
    assert me.hp == hp and not me.reaction
    assert c.spells.get("stolen") == "magic_missile" and "magic_missile" in sr.known_spells(c, tables)
    assert "magic_missile" not in b.creature_spells(foe)
    assert res.left(c, "spell_thief") == 0
    progression.long_rest(c, tables, RNG(1, "rest"))
    assert "stolen" not in c.spells and res.left(c, "spell_thief") == 1


# ---------------------------------------------------------------------------- the unseen hand on the road
from realmwalker.game import law, legerdemain  # noqa: E402
from realmwalker.game.dialogue import Conversation  # noqa: E402
from realmwalker.game.people import npcs_in  # noqa: E402

from tests.test_law import fixed_d20, game, in_town, someone, world  # noqa: E402,F401


def _trickster(game):
    c = game.leader
    c.features.append("mage_hand_legerdemain")
    c.spells = {"cantrips": ["mage_hand"], "slots_used": [0] * 9}
    assert legerdemain.trickster(game) is c


def test_the_unseen_hand_robs_a_stall_and_nobody_sees_who(game, monkeypatch):
    from realmwalker.game import economy

    _trickster(game)
    s, realm = in_town(game, "city")
    trader = next(n for n in npcs_in(game.world, s.id) if economy.shop_spec(game, n) is not None)
    shop = economy.shop_state(game, trader)
    item_id = next(iter(shop["stock"]))
    watcher = someone(game, s, exclude=("guard",))
    monkeypatch.setattr(law, "witnesses_here", lambda *a, **k: [watcher])
    fixed_d20(monkeypatch, 20)
    ok, said = law.steal_from_shop(game, trader, item_id)
    assert ok and "unseen hand" in said and not game.renown.crimes
    fixed_d20(monkeypatch, 1)
    item_id = next(iter(shop["stock"]))
    ok, said = law.steal_from_shop(game, trader, item_id)
    assert not ok and "unseen hand" in said and not game.renown.crimes  # (nobody to blame)


def test_the_unseen_hand_picks_a_pocket(game, monkeypatch):
    _trickster(game)
    s, realm = in_town(game)
    mark = someone(game, s, exclude=("guard",))
    mark.purse = 1000
    conv = Conversation(game, mark)
    pick = next(c for c in conv.menu() if c.id == "pickpocket")
    assert "unseen hand" in pick.label
    fixed_d20(monkeypatch, 1)
    conv.choose(pick)
    assert not conv.ended and not game.renown.crimes and mark.purse == 1000
    fixed_d20(monkeypatch, 20)
    money = game.leader.money
    conv.choose(next(c for c in conv.menu() if c.id == "pickpocket"))
    assert game.leader.money > money


def test_robbers_cannot_keep_a_bonded_weapon(game):
    c = game.leader
    c.features.append("war_bond")
    sword = add_item(c, game.tables.items, "longsword")
    c.spells = dict(c.spells or {}, war_bond={str(sword.uid): {"name": "longsword"}})
    from realmwalker.rules.inventory import remove_item

    taken = remove_item(c, sword.uid, 1)
    notes = war_bond.taken(game, [taken], "robbers")
    assert notes and any(it.def_id == "longsword" for it in c.inventory)
    assert len(war_bond.bonds(c)) == 1


# ---------------------------------------------------------------------------- the Auto, in whole fights
def test_a_knight_and_a_trickster_on_auto_fight_with_their_magic(tables):
    from realmwalker.rules import tactics

    cast = 0
    for seed in range(4):
        party = [knight(tables, 7, seed=seed), path(tables, "arcane_trickster", 9, seed=seed + 10)]
        b = fight(tables, party, "bandit", "bandit", "bandit_captain", seed=seed)
        for f in b.side("party"):
            f.auto = True
        for _ in range(400):
            if b.outcome is not None:
                break
            f = b.current
            if f is None:
                b.step()
                continue
            tactics.take_turn(b, f)
            if b.outcome is None and b.current is f:
                b.end_turn()
        assert b.outcome is not None, f"seed {seed}: the fight did not end"
        ours = {f.id for f in b.side("party")}
        cast += sum(1 for e in b.events if e["kind"] == "cast" and e.get("by") in ours)
    assert cast, "neither caster cast a spell in four fights"


# ---------------------------------------------------------------------------- from the fresh review
def test_a_third_caster_reads_wizard_scrolls(tables):
    c = path(tables, "eldritch_knight", 5)
    assert sr.scroll_reader(c, tables, "magic_missile") == "sure"
    assert sr.scroll_reader(c, tables, "fireball") == "check"


def test_magical_ambush_through_a_real_casting(tables, monkeypatch):
    c = path(tables, "arcane_trickster", 9)
    b = fight(tables, c, "bandit")
    me, foe = b.fighters[0], b.fighters[1]
    on_turn(b, me)
    me.hidden = 15
    seen = []
    real = query.save_roll

    def watch(bb, f, ability, **k):
        r = real(bb, f, ability, **k)
        if f is foe:
            seen.append(list(r.roll.dis))
        return r
    monkeypatch.setattr(query, "save_roll", watch)
    sp = "mind_sliver" if "mind_sliver" in tables.spells else "poison_spray"  # (a cantrip with a save)
    if sp not in c.spells["cantrips"]:
        c.spells["cantrips"].append(sp)
    assert b.do_cast(me, sp, foe)
    assert any("Magical Ambush" in d for d in seen)
    me.action, me.attacks_left = 1, 0
    b.do_cast(me, sp, foe)  # (the second, in plain sight)
    assert "ambush_turn" not in me.__dict__


def test_a_thrown_bonded_weapon_comes_home_after_the_fight(tables):
    c = knight(tables, 3, weapon="javelin")
    c.equipped_item("main_hand").qty = 1
    war_bond.at_rest(c, tables)
    b = fight(tables, c, "bandit", spots={0: (2, 2), 1: (6, 2)})
    me, foe = b.fighters[0], b.fighters[1]
    on_turn(b, me)
    held = c.equipped_item("main_hand")
    throw = next(o for o in b.attack_options(me) if o.key.startswith("throw") and o.item_uid == held.uid)
    b.do_attack(me, throw, foe)
    assert b.thrown
    war_bond.home(b)
    assert not b.thrown and any(it.def_id == "javelin" and war_bond.is_bonded(c, it) for it in c.inventory)
