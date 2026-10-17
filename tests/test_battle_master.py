"""Steel & Shadows part A: the Battle Master - superiority dice, the twenty maneuvers, Student of War, Know Your Enemy,
Relentless - each at work in a real fight or check, and in the Auto's hands."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import progression, tactics
from realmwalker.rules.engine import actions, query
from realmwalker.rules.engine import resources as res
from realmwalker.rules.engine.handlers import battle_master as bm
from realmwalker.world.tables import Tables

from tests.test_feats import armed, fight, main_opt, on_turn, soft


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def master(tables, level=3, know=(), seed=1, weapon="longsword"):
    """A Battle Master of this level who knows these maneuvers first (the rest as the Auto picks)."""
    c = armed(tables, weapon, level=1, seed=seed)
    for _ in range(level - 1):
        progression.level_up(c, tables, RNG(seed, "lv"))
    c.pending = [p for p in c.pending if p["kind"] not in ("asi", "boon")]
    sub = next((p for p in c.pending if p["kind"] == "subclass"), None)
    if sub is not None:
        progression.resolve(c, tables, sub, "battle_master")
    want = [f"maneuver_{m}" for m in know]
    for _ in range(40):
        opt = next((p for p in c.pending if p["kind"] == "option"), None)
        if opt is None:
            break
        ids = [o[0] for o in progression.options(c, tables, opt)]
        pick = next((w for w in want if w in ids), None) or progression.suggest(c, tables, opt)
        progression.resolve(c, tables, opt, pick)
    progression.auto_resolve(c, tables)
    res.fill(c, tables)
    return c


def known(c):
    return sorted(f[9:] for f in c.features if f.startswith("maneuver_"))


def always(monkeypatch, m):
    monkeypatch.setattr(tactics, "maneuver", lambda b, f, t, opts: m if m in opts else None)


# ---------------------------------------------------------------------------- the path, the dice, the choices
def test_the_path_and_its_numbers(tables):
    c = master(tables, 3)
    assert c.subclass == "battle_master" and len(known(c)) == 3
    assert res.maximum(c, res.pools(c, tables)["superiority"]) == 4 and c.uses["superiority"] == 4
    assert any(f["id"] == "student_of_war" for f in c.feats)  # (a tool and a fighter skill, chosen as a feat's are)
    sw = next(f for f in c.feats if f["id"] == "student_of_war")["choices"]
    assert sw["tool"] in c.tools and sw["skill"] in c.skills
    assert sw["skill"] in tables.classes["fighter"]["skill_choices"]
    assert bm.char_sides(c, tables) == 8
    for level, dice_, sides, n in ((7, 5, 8, 5), (10, 5, 10, 7), (15, 6, 10, 9), (18, 6, 12, 9)):
        c = master(tables, level, seed=level)
        assert res.maximum(c, res.pools(c, tables)["superiority"]) == dice_
        assert bm.char_sides(c, tables) == sides and len(known(c)) == n, (level, known(c))


def test_a_short_rest_brings_the_dice_back(tables):
    c = master(tables, 3)
    c.uses["superiority"] = 0
    res.recover(c, tables, "short")
    assert c.uses["superiority"] == 4


def test_suggest_and_the_auto_choose_by_how_they_fight(tables):
    sword = master(tables, 3)
    assert known(sword) == ["precision_attack", "riposte", "trip_attack"]
    bow = master(tables, 3, weapon="longbow")
    assert "riposte" not in known(bow) and "precision_attack" in known(bow)
    c = armed(tables, "longsword", level=2)
    progression.level_up(c, tables, RNG(1, "lv"))
    sub = next(p for p in c.pending if p["kind"] == "subclass")
    assert progression.suggest(c, tables, sub) == "battle_master"
    big = armed(tables, "greatsword", level=2)
    progression.level_up(big, tables, RNG(1, "lv"))
    sub = next(p for p in big.pending if p["kind"] == "subclass")
    assert progression.suggest(big, tables, sub) == "champion"


# ---------------------------------------------------------------------------- the blows' maneuvers
@pytest.mark.parametrize("m", ["trip_attack", "pushing_attack", "menacing_attack", "goading_attack",
                               "distracting_strike", "disarming_attack"])
def test_each_blow_maneuver_in_a_real_fight(tables, monkeypatch, m):
    always(monkeypatch, m)
    c = master(tables, 3, know=[m])
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe, ac=1)
    foe.cdef = dict(foe.cdef, saves={}, abilities=dict(foe.cdef.get("abilities", {}), str=1, wis=1))
    on_turn(b, me)
    monkeypatch.setattr(b, "_save", lambda *a, **k: False)
    before = foe.hp
    assert b._attack(me, main_opt(b, me), foe)
    assert c.uses["superiority"] == 3 and before - foe.hp > 0
    if m == "trip_attack":
        assert "prone" in foe.conditions
    elif m == "pushing_attack":
        assert b.gap(me, foe) > 1
    elif m == "menacing_attack":
        assert "frightened" in foe.conditions
    elif m == "goading_attack":
        assert any(bf.get("goaded") == me.id for bf in foe.buffs)
        ally_opt = main_opt(b, me)
        r = query.attack_roll(b, foe, foe, ally_opt)  # (striking anyone but the goader)
        assert r.disadvantage
    elif m == "distracting_strike":
        assert any(bf.get("exposed") == me.id for bf in foe.buffs)
        assert not b._adv_dis(me, foe, main_opt(b, me))[0]  # (not for the one who struck)
    elif m == "disarming_attack":
        assert any(bf.get("disarmed") for bf in foe.buffs)
        assert all(not o.available for o in b.attack_options(foe) if o.name.lower() == bm.held_weapon(foe).lower())


def test_the_die_adds_to_the_damage(tables, monkeypatch):
    always(monkeypatch, "trip_attack")
    c = master(tables, 3, know=["trip_attack"])
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe, ac=1)
    on_turn(b, me)
    rolled = []
    real = bm.roll_die
    monkeypatch.setattr(bm, "roll_die", lambda b_, f, what: rolled.append(real(b_, f, what)) or rolled[-1])
    seen = []
    for _ in range(30):
        c.uses["superiority"] = 4
        foe.hp = foe.max_hp
        foe.conditions.pop("prone", None)
        if b._attack(me, main_opt(b, me), foe):
            seen.append(foe.max_hp - foe.hp)
    assert rolled and max(seen) > 9  # (a longsword's d8 + 3 alone never passes 11; with the die it can)


def test_sweeping_attack_carries_into_a_second_foe(tables, monkeypatch):
    always(monkeypatch, "sweeping_attack")
    c = master(tables, 3, know=["sweeping_attack"])
    b = fight(tables, c, "bandit", "bandit", spots={0: (3, 4), 1: (4, 4), 2: (4, 5)})
    me, a, second = b.fighters
    soft(a, ac=1)
    soft(second, ac=1)
    on_turn(b, me)
    assert b._attack(me, main_opt(b, me), a)
    assert second.hp < second.max_hp


def test_maneuvering_attack_moves_a_hurt_friend_clear(tables, monkeypatch):
    always(monkeypatch, "maneuvering_attack")
    c = master(tables, 3, know=["maneuvering_attack"])
    friend = armed(tables, "dagger", cls="rogue", level=3, seed=4)
    b = fight(tables, [c, friend], "bandit", spots={0: (3, 4), 1: (5, 5), 2: (4, 5)})
    me, pal, foe = b.fighters
    soft(foe, ac=1)
    pal.hp = 2
    on_turn(b, me)
    assert b.gap(pal, foe) <= 1
    assert b._attack(me, main_opt(b, me), foe)
    assert b.gap(pal, foe) > 1 and not pal.reaction


def test_one_maneuver_an_attack(tables, monkeypatch):
    always(monkeypatch, "trip_attack")
    c = master(tables, 3, know=["trip_attack", "precision_attack"])
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe, ac=14)
    on_turn(b, me)
    seen = 0
    for i in range(80):
        c.uses["superiority"] = 4
        me.reaction = True
        foe.conditions.pop("prone", None)
        b._attack(me, main_opt(b, me), foe)
        spent = 4 - c.uses["superiority"]
        assert spent <= 1
        seen += spent
    assert seen > 10


# ---------------------------------------------------------------------------- the answers: precision, parry, riposte
def test_precision_attack_turns_a_near_miss(tables):
    c = master(tables, 3, know=["precision_attack"])
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe, ac=19)
    on_turn(b, me)
    turned = 0
    for i in range(200):
        c.uses["superiority"] = 4
        if b._attack(me, main_opt(b, me), foe) and c.uses["superiority"] == 3:
            turned += 1
    assert turned > 3


def test_parry_takes_the_sting_out_of_a_blow(tables):
    c = master(tables, 3, know=["parry"])
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    me.char.max_hp = me.char.hp = 300
    taken, parried = [], 0
    for i in range(60):
        me.reaction = True
        c.uses["superiority"] = 4
        before = me.hp
        b._melee_blow = True
        try:
            b._hit(foe, me, 12, "slashing", crit=False, weapon="scimitar")
        finally:
            b._melee_blow = False
        taken.append(before - me.hp)
        parried += c.uses["superiority"] < 4
    assert parried == 60 and max(taken) < 12


def test_riposte_strikes_back_at_a_miss(tables):
    c = master(tables, 3, know=["riposte"])
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe, ac=1)
    on_turn(b, foe)
    foe_opt = next(o for o in b.attack_options(foe) if o.is_melee)
    for _ in range(100):
        me.reaction = True
        c.uses["superiority"] = 4
        before = foe.hp
        hit = b._attack(foe, foe_opt, me)
        if not hit:
            assert c.uses["superiority"] == 3 and not me.reaction and foe.hp < before
            break
    else:
        pytest.fail("the bandit never missed")


# ---------------------------------------------------------------------------- the bonus actions and the rest
def test_feint_lunge_footwork_and_rally(tables):
    c = master(tables, 3, know=["feinting_attack", "evasive_footwork", "rally"])
    friend = armed(tables, "dagger", cls="rogue", level=3, seed=4)
    b = fight(tables, [c, friend], "bandit", spots={0: (3, 4), 1: (3, 5), 2: (4, 4)})
    me, pal, foe = b.fighters
    soft(foe, ac=1)
    on_turn(b, me)
    ids = {o.value: o for o in actions.options(b, me, only=("ability",)) if o.kind == "ability"}
    assert {"feinting_attack", "evasive_footwork", "rally"} <= set(ids)
    assert foe in ids["feinting_attack"].targets and pal in ids["rally"].targets
    b.do_ability(me, "feinting_attack", foe)
    assert c.uses["superiority"] == 3 and b._adv_dis(me, foe, main_opt(b, me))[0]
    before = foe.hp
    b._attack(me, main_opt(b, me), foe)
    assert not any(bf.get("maneuver_die") for bf in me.buffs)  # (the feint's die went into the hit)
    on_turn(b, me)
    ac = me.ac()
    b.do_ability(me, "evasive_footwork")
    assert me.disengaged and me.ac() > ac
    on_turn(b, me)
    b.do_ability(me, "rally", pal)
    assert pal.temp_hp >= 2 and c.uses["superiority"] == 1


def test_lunging_attack_dashes_and_bites(tables):
    c = master(tables, 3, know=["lunging_attack"])
    b = fight(tables, c, "bandit", spots={0: (2, 4), 1: (9, 4)})
    me, foe = b.fighters
    soft(foe, ac=1)
    on_turn(b, me)
    move = me.move_left
    b.do_ability(me, "lunging_attack")
    assert me.move_left == move * 2 and any(bf.get("maneuver_die") for bf in me.buffs)
    b.do_move(me, (8, 4))
    b._attack(me, main_opt(b, me), foe)
    assert not any(bf.get("maneuver_die") for bf in me.buffs)


def test_commanders_strike_gives_a_blow_to_a_friend(tables):
    c = master(tables, 5, know=["commander_s_strike"])
    friend = armed(tables, "dagger", cls="rogue", level=3, seed=4)
    b = fight(tables, [c, friend], "bandit", spots={0: (3, 4), 1: (5, 4), 2: (4, 4)})
    me, pal, foe = b.fighters
    soft(foe, ac=1)
    on_turn(b, me)
    before = foe.hp
    assert b.do_ability(me, "commanders_strike", pal)
    assert not pal.reaction and foe.hp < before and me.attacks_left == 1 and me.action == 0


def test_bait_and_switch_trades_places(tables):
    c = master(tables, 3, know=["bait_and_switch"])
    friend = armed(tables, "dagger", cls="rogue", level=3, seed=4)
    b = fight(tables, [c, friend], "bandit", spots={0: (3, 4), 1: (3, 5), 2: (2, 5)})
    me, pal, foe = b.fighters
    on_turn(b, me)
    here, there = (me.x, me.y), (pal.x, pal.y)
    left = me.move_left
    assert b.do_ability(me, "bait_and_switch", pal)
    assert (me.x, me.y) == there and (pal.x, pal.y) == here and me.move_left == left - 5
    assert any(bf.get("ac") for x in (me, pal) for bf in x.buffs)


def test_know_your_enemy_lays_a_creature_bare(tables):
    c = master(tables, 7)
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    on_turn(b, me)
    b.known.discard(foe.creature.def_id)
    assert b.do_ability(me, "know_your_enemy", foe)
    assert foe.creature.def_id in b.known and c.uses["know_your_enemy"] == 0
    b.known.discard(foe.creature.def_id)
    on_turn(b, me)
    dice_ = c.uses["superiority"]
    assert b.do_ability(me, "know_your_enemy", foe)  # (again, for a superiority die)
    assert c.uses["superiority"] == dice_ - 1


def test_relentless_rolls_a_free_die_once_a_turn(tables, monkeypatch):
    always(monkeypatch, "trip_attack")
    c = master(tables, 15, know=["trip_attack"])
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe, ac=1)
    on_turn(b, me)
    c.uses["superiority"] = 0
    assert bm.ready(b, me)
    b._attack(me, main_opt(b, me), foe)
    assert not bm.ready(b, me)  # (the turn's free die is gone)
    on_turn(b, me)
    assert bm.ready(b, me)


def test_ambush_and_the_checks(tables):
    c = master(tables, 3, know=["ambush", "commanding_presence", "tactical_assessment"])
    turned = 0
    for i in range(80):
        c.uses["superiority"] = 4
        total, line = bm.check_die(c, tables, "persuasion", 10, 14, RNG(i, "cp"))
        if total >= 14:
            turned += 1
            assert c.uses["superiority"] == 3 and "Commanding Presence" in line
    assert turned > 20
    assert bm.check_die(c, tables, "insight", 10, 14, RNG(1))[0] >= 11
    assert bm.check_die(c, tables, "athletics", 10, 14, RNG(1)) == (10, "")
    assert bm.check_die(c, tables, "stealth", 1, 20, RNG(1)) == (1, "")  # (out of the die's reach: not tried)
    spent = 0
    for i in range(30):
        c.uses["superiority"] = 4
        b = fight(tables, c, "bandit", seed=i)
        spent += c.uses["superiority"] < 4
    assert spent > 3  # (Ambush on a poor Initiative)


# ---------------------------------------------------------------------------- the Auto
def test_the_auto_uses_its_maneuvers_in_a_whole_fight(tables):
    used = set()
    for seed in range(6):
        c = master(tables, 7, seed=seed)
        friend = armed(tables, "dagger", cls="rogue", level=5, seed=seed + 9)
        b = fight(tables, [c, friend], "bandit", "bandit", "thug", seed=seed)
        for f in b.fighters:
            f.auto = True
        for _ in range(400):
            if b.outcome is not None:
                break
            b.step()
            if b.current is not None and b.current.side == "party" and b.pending_party():
                tactics.take_turn(b, b.current)
                b.end_turn()
        used |= {e.get("what") for e in b.events if e.get("kind") == "maneuver"}
    assert len(used) >= 3, used
