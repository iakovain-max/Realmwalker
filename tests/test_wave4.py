"""The spell catalogue's fourth wave (Expansion 3 D.4, levels 8 and 9): the new kernel pieces doing what their cards say
in real fights - the earthquake that breaks concentration, the maze and its way out, words of power, Holy Aura,
Foresight, Befuddlement, Mind Blank, the antimagic field that goes with its caster, Mass Heal's pool, Power Word Heal,
the four meteors, the prismatic wall's glare, the storm's turns, Time Stop's turns in a row, and Wish: its copies, its
Instant Health and the stress that follows."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import actions, estimates
from realmwalker.rules.progression import award_xp, long_rest
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def hero(tables, cls="wizard", seed=1, xp=0):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("sage")
    c = b.build()
    if xp:
        award_xp(c, xp, tables, RNG(seed), auto=True)
    c.hp = c.max_hp
    return c


def fight(tables, party, foes, spots, seed=1, env=None, field=None):
    rng = RNG(seed, "foes")
    crs = [spawn(tables, d, rng, i + 1) for i, d in enumerate(foes)]
    b = Battle(tables, party, crs, env or Env(), RNG(seed, "battle"), spots=spots, field=field)
    b.start()
    return b


def my_turn(b, f):
    b.order = [f.id] + [x for x in b.order if x != f.id]
    b.turn = 0
    b.turn_started = True
    b._start_of_turn(f)


def cast(b, f, sid, target=None, point=None, *, dc=30, level=None, up=0):
    sp = b.t.spells[sid]
    b.cast(f, sid, sp, target, point, up=up, mod=4, dc=dc, bonus=8, mult=1, level=(level or sp["level"]) + up)


def sturdy(*xs, hp=300):
    for x in xs:
        x.creature.hp = x.creature.max_hp = hp


def test_the_earthquake_throws_foes_down_and_breaks_their_concentration(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (1, 4), 1: (8, 4)})
    me, foe = b.fighters
    foe.concentration = {"spell": "bless", "rounds": -1, "on": []}
    my_turn(b, me)
    cast(b, me, "earthquake", point=(8, 4), dc=40)
    assert "prone" in foe.conditions and foe.concentration is None
    assert "prone" not in me.conditions, "it spares the caster's side"


def test_the_maze_holds_a_foe_until_a_check_finds_the_way_out(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (1, 4), 1: (5, 4)})
    me, foe = b.fighters
    my_turn(b, me)
    cast(b, me, "maze", foe)
    assert foe.state == "away" and foe.away.get("escape")
    foe.away["escape"]["dc"] = 1  # (a way out that cannot be missed)
    b.end_turn()
    b.order = [me.id, foe.id]
    b.turn, b.turn_started = 1, False
    b.step()
    assert foe.state == "fighting" and me.concentration is None, "out, and the spell is over"
    assert b.current is me or foe.acted, "the turn went on finding the way"
    assert foe.action >= 0


def test_power_word_stun_stuns_the_weak_and_only_slows_the_strong(tables):
    b = fight(tables, [hero(tables)], ["bandit", "bandit"], {0: (1, 4), 1: (5, 4), 2: (5, 6)})
    me, weak, strong = b.fighters
    sturdy(strong, hp=200)
    my_turn(b, me)
    cast(b, me, "power_word_stun", weak)
    cast(b, me, "power_word_stun", strong)
    assert "stunned" in weak.conditions
    assert "stunned" not in strong.conditions and strong.speed == 0


def test_power_word_kill_kills_at_a_hundred_and_hurts_above(tables):
    b = fight(tables, [hero(tables)], ["bandit", "bandit"], {0: (1, 4), 1: (5, 4), 2: (5, 6)})
    me, weak, strong = b.fighters
    sturdy(weak, hp=100)
    sturdy(strong, hp=400)
    my_turn(b, me)
    cast(b, me, "power_word_kill", weak)
    cast(b, me, "power_word_kill", strong)
    assert weak.state == "dead"
    assert strong.state in ("fighting", "fleeing") and 400 - 144 <= strong.hp < 400


def test_holy_aura_gives_friends_advantage_on_saves_and_blinds_the_undead_that_strike(tables):
    from realmwalker.rules.engine import query

    foe_id = "skeleton" if "skeleton" in tables.creatures.defs else "zombie"
    b = fight(tables, [hero(tables, "cleric"), hero(tables, "fighter", seed=2)], [foe_id],
              {0: (2, 4), 1: (3, 4), 2: (4, 4)})
    me, friend, dead = b.fighters
    my_turn(b, me)
    cast(b, me, "holy_aura", dc=40)
    assert friend.buff_value("holy"), "a friend within 30 feet shares it"
    assert query.save_roll(b, friend, "wis").roll.mode == "advantage"
    opt = next(o for o in b.attack_options(dead) if o.is_melee)
    assert query.attack_roll(b, dead, friend, opt).mode == "disadvantage"
    from realmwalker.rules.engine import marks

    marks.after_hit(b, dead, friend, opt)
    assert "blinded" in dead.conditions


def test_foresight_gives_advantage_and_disadvantage_against(tables):
    from realmwalker.rules.engine import query

    b = fight(tables, [hero(tables, "wizard", xp=355000)], ["bandit"], {0: (2, 4), 1: (3, 4)})
    me, foe = b.fighters
    my_turn(b, me)
    cast(b, me, "foresight", me)
    opt = next(o for o in b.attack_options(foe) if o.is_melee)
    assert query.attack_roll(b, foe, me, opt).mode == "disadvantage"
    assert query.save_roll(b, me, "dex").roll.mode == "advantage"


def test_befuddlement_leaves_a_caster_without_spells(tables):
    b = fight(tables, [hero(tables), hero(tables, "wizard", seed=3, xp=6500)], ["bandit"],
              {0: (1, 4), 1: (1, 6), 2: (5, 4)})
    me, other, _ = b.fighters
    other.buffs.append({"befuddled": True, "source": "befuddlement"})
    other.action = 1
    opts = b.spell_options(other)
    assert opts and all(not ok for _, ok, _ in opts) and any("befuddled" in why for _, _, why in opts)
    assert not b._shield(other), "nor a Shield as a reaction"


def test_mind_blank_turns_aside_psychic_harm_and_charms(tables):
    from realmwalker.rules.engine import query

    b = fight(tables, [hero(tables)], ["bandit"], {0: (1, 4), 1: (5, 4)})
    me, _ = b.fighters
    my_turn(b, me)
    cast(b, me, "mind_blank", me)
    assert query.damage_taken(me, 20, "psychic")[0] == 0
    assert query.condition_immune(me, "charmed")


def test_the_antimagic_field_goes_with_its_caster_and_stops_casting(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (2, 4), 1: (3, 4)})
    me, foe = b.fighters
    my_turn(b, me)
    cast(b, me, "antimagic_field")
    z = next(z for z in b.zones if z.kind == "antimagic")
    assert b.antimagic(foe.cells) and b.antimagic(me.cells)
    me.x, me.y = 10, 8
    b._follow_auras()
    assert (10, 8) in z.cells and not b.antimagic(foe.cells), "it moved with the caster"


def test_mass_heal_shares_its_pool_and_power_word_heal_makes_whole(tables):
    party = [hero(tables, "cleric", xp=355000), hero(tables, "fighter", seed=2), hero(tables, "fighter", seed=3)]
    b = fight(tables, party, ["bandit"], {0: (2, 4), 1: (3, 4), 2: (3, 6), 3: (12, 4)})
    me, a, c = b.fighters[:3]
    for x in (me, a, c):
        x.char.hp = 1
    a.conditions["poisoned"] = 10
    my_turn(b, me)
    cast(b, me, "mass_heal")
    assert all(x.hp == x.max_hp for x in (me, a, c)) and "poisoned" not in a.conditions
    a.char.hp = 1
    a.conditions["stunned"] = 10
    cast(b, me, "power_word_heal", a)
    assert a.hp == a.max_hp and "stunned" not in a.conditions


def test_meteor_swarm_catches_foes_far_apart_each_once(tables):
    from realmwalker.rules.combat import open_field

    b = fight(tables, [hero(tables)], ["bandit", "bandit", "bandit"], {0: (1, 1), 1: (14, 4), 2: (4, 26), 3: (28, 26)},
              field=open_field(tables, 40, 34))
    me, *foes = b.fighters
    sturdy(*foes, hp=1000)
    my_turn(b, me)
    assert [(x.x, x.y) for x in foes] == [(14, 4), (4, 26), (28, 26)]
    cells = b.spell_area(me, "meteor_swarm", (foes[0].x, foes[0].y))
    caught = b.in_area(cells, "all", me)
    assert all(x in caught for x in foes), "the other spheres fall on the foes not yet caught"
    cast(b, me, "meteor_swarm", point=(foes[0].x, foes[0].y), dc=40)
    for x in foes:
        assert 1000 - 240 <= x.hp <= 1000 - 40, "40d6 once, not once a sphere"


def test_the_prismatic_wall_blinds_foes_beside_it(tables):
    b = fight(tables, [hero(tables)], ["bandit"], {0: (1, 4), 1: (12, 4)})
    me, foe = b.fighters
    my_turn(b, me)
    cast(b, me, "prismatic_wall", point=(9, 4), dc=40)
    assert any(z.kind == "prismatic" for z in b.zones) and any(z.kind == "glare" for z in b.zones)
    assert "blinded" in foe.conditions


def test_the_storm_of_vengeance_brings_something_new_each_turn(tables):
    b = fight(tables, [hero(tables)], ["bandit", "bandit"], {0: (1, 4), 1: (6, 4), 2: (8, 6)})  # (no druids yet)
    me, *foes = b.fighters
    sturdy(*foes, hp=500)
    my_turn(b, me)
    cast(b, me, "storm_of_vengeance", point=(7, 5), dc=40)
    z = next(z for z in b.zones if z.kind == "storm")
    assert all("deafened" in x.conditions for x in foes)
    hp = [x.hp for x in foes]
    my_turn(b, me)
    assert z.stage == 1 and all(x.hp < h for x, h in zip(foes, hp)), "acid rain"
    for _ in range(3):
        my_turn(b, me)
    assert z.rough and z.dark, "the freezing rain and the wind"
    assert me.hp == me.max_hp, "it spares the caster's side"


def test_time_stop_gives_turns_in_a_row_until_the_caster_touches_another(tables):
    b = fight(tables, [hero(tables, "wizard", xp=355000)], ["bandit"], {0: (1, 4), 1: (9, 4)})
    me, foe = b.fighters
    my_turn(b, me)
    cast(b, me, "time_stop")
    n = next(bf["time_stop"] for bf in me.buffs if bf.get("time_stop") is not None)
    assert 2 <= n <= 5
    b.end_turn()
    assert b.current is me, "another turn, and nobody else moves"
    b.step()
    b._event("damage", to=foe.id, amount=1)  # (something of theirs reaches the foe)
    b.end_turn()
    assert b.current is foe, "time flows again"
    assert not any(bf.get("time_stop") is not None for bf in me.buffs)


def wisher(tables):
    c = hero(tables, "wizard", xp=355000)
    c.spells.setdefault("spellbook", []).append("wish")
    c.spells["prepared"] = ["wish"] + [s for s in c.spells.get("prepared", []) if s != "wish"]
    return c


def test_wish_copies_a_spell_with_its_level_nine_slot_and_no_components(tables):
    c = wisher(tables)
    assert "wish" in spellrules.known_spells(c, tables)
    b = fight(tables, [c], ["bandit"], {0: (1, 4), 1: (5, 4)})
    me, foe = b.fighters
    my_turn(b, me)
    nine = spellrules.slots_left(c, tables)[8]
    assert nine >= 1
    assert any(v == "wish:copy:forcecage" for v, ok, _ in b.wish_options(me)), "a costly spell, copied freely"
    assert b.do_cast(me, "wish:copy:power_word_stun", foe)
    assert spellrules.slots_left(c, tables)[8] == nine - 1
    assert "stunned" in foe.conditions or foe.speed == 0
    assert not c.effects.get("wish_stress"), "a copy brings no stress"
    assert any(o.value.startswith("wish:copy:") for o in actions.options(b, me, only=("cast",))), "the Auto sees it"


def test_wishing_for_instant_health_brings_the_stress(tables):
    c = wisher(tables)
    b = fight(tables, [c, hero(tables, "fighter", seed=2)], ["bandit"], {0: (1, 4), 1: (2, 4), 2: (9, 4)})
    me, friend, _ = b.fighters
    friend.char.hp = 1
    my_turn(b, me)
    assert b.do_cast(me, "wish")
    assert friend.hp == friend.max_hp
    assert c.effects.get("wish_stress") and c.effects.get("wish_strength", 0) >= 48
    assert me.sheet.score("str") == 3, "Strength 3 for days"
    assert estimates.spell_value(b, me, "wish").total() >= 0
    # the strain: the next spell tears at its caster
    me.action, me.bonus = 1, 1
    b.round += 1  # (a new turn: one slot a turn)
    hp = me.hp
    assert b.do_cast(me, "magic_missile", b.fighters[2])
    assert me.hp < hp, "1d10 necrotic a level"
    long_rest(c, tables, RNG(1))
    assert not c.effects.get("wish_stress"), "a long rest ends the strain"
    assert c.effects.get("wish_strength", 0) > 0, "but not the lost Strength"


def test_a_third_of_wishes_are_the_last(tables):
    lost = 0
    for seed in range(60):
        c = hero(tables, "wizard", xp=355000)
        spellrules.wish_stress(c, RNG(seed, "wish"))
        lost += bool(c.spells.get("wish_lost"))
        if c.spells.get("wish_lost"):
            c.spells.setdefault("prepared", []).append("wish")
            assert not spellrules.can_cast(c, tables, "wish")[0]
    assert 8 <= lost <= 35


def test_the_battle_screen_opens_wishes_and_casts_a_copy(make_app):
    import copy

    import tcod.console

    from realmwalker.game.state import new_game
    from realmwalker.ui.screens.battle import BattleScreen
    from realmwalker.world.generator import WorldOptions
    from tests.worlds import cached_world

    app = make_app()
    t = app.tables
    wiz = wisher(t)
    g = new_game(copy.deepcopy(cached_world(WorldOptions("Wishland", 7, "small"), t)), t, wiz)
    g.survival = False
    app.start_game(g)
    b = Battle(t, [wiz], [spawn(t, "ogre", RNG(1), 1)], Env(), RNG(1, "battle"), spots={0: (2, 4), 1: (6, 4)})
    b.start("Test fight.")
    g.battle = b
    me = b.fighters[0]
    my_turn(b, me)
    screen = BattleScreen(app, g)
    app.push(screen)
    app.render(tcod.console.Console(160, 45, order="F"))
    screen.pick_action("cast")
    screen.choice_index = next(i for i, r in enumerate(screen.choices) if r[1] == "wish")
    screen.confirm_choice()
    assert screen.choice_kind == "wish" and screen.choices[0][1] == "wish"
    assert any(r[1] == "wish:copy:power_word_stun" for r in screen.choices)
    app.render(tcod.console.Console(160, 45, order="F"))
    screen.choice_index = next(i for i, r in enumerate(screen.choices) if r[1] == "wish:copy:power_word_stun")
    screen.confirm_choice()
    assert screen.mode == "target"
    nine = spellrules.slots_left(wiz, t)[8]
    screen.confirm_target()
    assert spellrules.slots_left(wiz, t)[8] == nine - 1
    app.render(tcod.console.Console(160, 45, order="F"))
    assert app.error_count == 0


def test_nobody_reacts_while_time_stands_still_and_the_spells_do_not_wear_down(tables):
    b = fight(tables, [hero(tables, "wizard", xp=355000)], ["bandit"], {0: (4, 4), 1: (5, 4)})
    me, foe = b.fighters
    my_turn(b, me)
    cast(b, me, "time_stop")
    me.concentration = {"spell": "bless", "rounds": 3, "on": []}
    b.end_turn()
    b.step()  # (the extra turn begins)
    assert b.current is me and me.concentration["rounds"] == 3, "no time passes"
    assert not b.threats(me), "the foe is held in the moment"
    hp = me.hp
    b.do_move(me, (1, 4))
    assert me.hp == hp and foe.reaction, "no blow as the caster walks away"


def test_a_countered_wish_brings_no_stress(tables, monkeypatch):
    c = wisher(tables)
    b = fight(tables, [c], ["bandit"], {0: (1, 4), 1: (9, 4)})
    me, _ = b.fighters
    my_turn(b, me)
    monkeypatch.setattr(Battle, "_countered", lambda self, f, sid, spell: True)
    nine = spellrules.slots_left(c, tables)[8]
    b.do_cast(me, "wish")
    assert not c.effects.get("wish_stress") and spellrules.slots_left(c, tables)[8] == nine
