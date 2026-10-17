"""The raised dead (Expansion 3 F.4): Animate Dead on the fresh dead and on a crypt's bones, Create Undead at night by
the slot and the onyx stones, holding them again, going free (a fight out in the land, gone in a town), servants in a
fight (beside their master, waiting for a word, commanded by the player and the Auto, the command's reach), Finger of
Death's zombie, the ghast's Stench and Claw, the mummy's Glare and rot (the dust, the curse carried and lifted)."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import fight as game_fight
from realmwalker.game import magic, revival, servants, speech
from realmwalker.game.state import new_game
from realmwalker.rules import allies, tactics
from realmwalker.rules import servants as rules
from realmwalker.rules import spells as sp
from realmwalker.rules.combat import FOE, PARTY, Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import check
from realmwalker.rules.inventory import add_item
from realmwalker.rules.progression import award_xp
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.test_wave4 import my_turn, sturdy
from tests.worlds import cached_world

F4 = ("animate_dead", "create_undead")


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Lastrites", 37, "small"), tables)


@pytest.fixture(autouse=True)
def casters_know_them(monkeypatch):
    real = sp.known_spells

    def known(char, tables):
        out = real(char, tables)
        return list(dict.fromkeys(out + list(F4) + ["finger_of_death", "remove_curse"])) \
            if sp.is_caster(char, tables) else out

    monkeypatch.setattr(sp, "known_spells", known)


def hero(tables, cls="wizard", xp=355000, seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("sage")
    c = b.build()
    if xp:
        award_xp(c, xp, tables, RNG(seed), auto=True)
    add_item(c, tables.items, "component_pouch")
    c.hp = c.max_hp
    return c


def game_with(world, tables, *party):
    game = new_game(copy.deepcopy(world), tables, party[0])
    for c in party[1:]:
        game.party.append(c)
    game.survival = False
    return game


def in_the_wild(game):
    game.leave_local() if game.local is not None else None
    for x in range(game.world.width):
        for y in range(game.world.height):
            if game.world.settlement_at(x, y) is None and game.world.danger[x, y] >= 1 \
                    and game.tables.biomes.family(game.land_key(x, y)) in ("forest", "plains", "hills"):
                game.player.x, game.player.y = x, y
                return
    raise AssertionError("no wild land")


def at_night(game):
    day = int(game.world.time // 1440) * 1440
    for h in range(24):
        game.world.time = day + h * 60
        if game.light < 0.5:
            return
    raise AssertionError("no night")


def at_noon(game):
    game.world.time = int(game.world.time // 1440) * 1440 + 12 * 60


def slain(tables, game, foes):
    """A fight where every foe fell: its dead lie here (game.fresh_dead)."""
    rng = RNG(1, "foes")
    b = Battle(tables, [game.leader], [spawn(tables, d, rng, i + 1) for i, d in enumerate(foes)], Env(), RNG(1, "b"),
               spots={})
    b.start("Test fight.")
    for f in b.side(FOE):
        f.creature.hp, f.creature.alive, f.state, f.hp = 0, False, "dead", 0
    speech.remember_the_dead(game, b, "bandits")
    return b


def subject(game, c, sid, ref):
    subs = magic.road_targets(game, c, sid)
    found = [s for s in subs if s.ref == ref]
    assert found, f"{sid}: no subject {ref} in {[s.name for s in subs]}"
    return found[0]


def cast(game, c, sid, target, slot=None):
    why = magic.road_problem(game, c, sid, target)
    assert why is None, f"{sid}: {why}"
    return magic.cast_on_road(game, c, sid, target, slot)


def battle(tables, party, foes, spots, seed=1):
    rng = RNG(seed, "foes")
    crs = [spawn(tables, d, rng, i + 1) for i, d in enumerate(foes)]
    b = Battle(tables, party, crs, Env(), RNG(seed, "battle"), spots=spots)
    owners = [f for f in b.side(PARTY) if f.char is not None]
    allies.bring_in(b, owners)
    rules.bring_in(b, owners)
    b.start()
    return b


# ---------------------------------------------------------------------------- the data
def test_the_spells_and_creatures_are_in_and_the_start_up_check_knows_them(tables):
    for sid in F4:
        assert sid in tables.spells and sp.road_use(tables, sid) == "raise" and sp.upcasts(tables.spells[sid])
        assert f"scroll_{sid}" in tables.items
    assert sp.op(tables.spells["finger_of_death"], "rise")["as"] == "zombie"
    assert not check.problems(tables)
    ghast, mummy = tables.creatures["ghast"], tables.creatures["mummy"]
    assert (ghast["ac"], ghast["hp"], ghast["cr"], ghast["kind"]) == (13, "8d8", 2.0, "undead")
    assert "stench" in ghast["traits"] and "necrotic" in ghast["resist"]
    assert (mummy["ac"], mummy["hp"], mummy["speed"], mummy["vulnerable"]) == (11, "9d8+18", 20, ["fire"])
    assert mummy["multiattack_plan"] == [["rotting_fist"], ["rotting_fist"], ["dreadful_glare"]]
    assert tables.items.get("black_onyx")["value"] == 15000
    assert "raised_dead" in tables.creatures.encounters


# ---------------------------------------------------------------------------- Animate Dead
def test_animate_dead_raises_zombies_from_the_fresh_dead_more_at_a_higher_slot(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    slain(tables, game, ("bandit", "bandit", "bandit", "bandit"))
    cast(game, wiz, "animate_dead", subject(game, wiz, "animate_dead", "zombie"), 3)
    assert [r["cid"] for r in rules.records(wiz)] == ["zombie"]
    rec = rules.records(wiz)[0]
    assert rec["word"] and rec["reach"] == 60 and rec["until"] == pytest.approx(game.world.time - 1 + rules.DAY, abs=2)
    assert len(servants.corpses(game)) == 3
    cast(game, wiz, "animate_dead", subject(game, wiz, "animate_dead", "zombie"), 4)  # (one and two more)
    assert len(rules.records(wiz)) == 4 and not servants.corpses(game)
    assert servants.problem(game, wiz, "animate_dead", None) is not None  # (no body left; four wait to be held)


def test_bones_of_a_crypt_and_of_destroyed_skeletons_rise_as_skeletons(world, tables):
    from tests.test_spells_road6 import into_dungeon, place_in_dungeon

    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    lm = into_dungeon(game)
    place_in_dungeon(game, lm)
    lm.meta["style"] = "crypt"
    assert servants.bones(game) == servants.CRYPT_BONES
    slain(tables, game, ("skeleton", "bandit"))
    assert servants.bones(game) == servants.CRYPT_BONES + 1
    cast(game, wiz, "animate_dead", subject(game, wiz, "animate_dead", "skeleton"), 5)  # (five)
    assert [r["cid"] for r in rules.records(wiz)] == ["skeleton"] * 5
    assert servants.bones(game) == 2 and lm.meta["bones"] == 2


def test_holding_the_dead_again_the_warning_and_going_free_in_the_land(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    slain(tables, game, ("bandit", "bandit"))
    cast(game, wiz, "animate_dead", subject(game, wiz, "animate_dead", "zombie"), 4)
    first_until = rules.records(wiz)[0]["until"]
    game.world.time += 20 * 60
    cast(game, wiz, "animate_dead", subject(game, wiz, "animate_dead", "hold"), 3)
    assert all(r["until"] > first_until + 19 * 60 for r in rules.records(wiz))
    until = rules.records(wiz)[0]["until"]
    game.world.time = until - 60
    servants.tick(game)
    assert any("restless" in m.text for m in game.log.messages[-6:])
    assert all(r["warned"] for r in rules.records(wiz))
    game.world.time = until + 1
    servants.tick(game)
    assert not rules.records(wiz)
    assert game.encounter is not None and game.encounter.group == "raised_dead"
    assert [c.def_id for c in game.encounter.creatures] == ["zombie", "zombie"]
    assert game.encounter.attitude == "hostile" and game.encounter.spotted_first


def test_freed_in_a_town_they_shamble_off_and_wait_outside_its_walls_until_then(world, tables):
    from tests.test_spells_road6 import in_town

    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    slain(tables, game, ("bandit",))
    cast(game, wiz, "animate_dead", subject(game, wiz, "animate_dead", "zombie"), 3)
    assert servants.following(game)
    in_town(game)
    assert not servants.here(game) and not servants.following(game)
    rng = RNG(3, "watch")
    b = game_fight.start_battle(game, [spawn(tables, "bandit", rng, 1)], "A fight in town.")
    assert not [f for f in b.fighters if f.bond is not None and f.bond["kind"] == "servant"]
    game.battle = None
    game.encounter = None
    game.world.time = rules.records(wiz)[0]["until"] + 1
    servants.tick(game)
    assert not rules.records(wiz) and game.encounter is None


def test_the_hold_of_a_dead_master_ends_at_once(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    rules.add(wiz, tables, "zombie", "animate_dead", until=game.world.time + rules.DAY, now=game.world.time)
    servants.died(game, wiz)
    assert not rules.records(wiz) and game.encounter is not None


def test_twelve_at_most_answer_one_master(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    for _ in range(rules.MAX):
        assert rules.add(wiz, tables, "skeleton", "animate_dead", until=game.world.time + 9, now=game.world.time)
    assert rules.add(wiz, tables, "skeleton", "animate_dead", until=1, now=0) is None
    slain(tables, game, ("bandit",))
    assert "twelve" in servants.problem(game, wiz, "animate_dead", subject(game, wiz, "animate_dead", "zombie")) \
        or "12" in servants.problem(game, wiz, "animate_dead", subject(game, wiz, "animate_dead", "zombie"))


# ---------------------------------------------------------------------------- Create Undead
def test_create_undead_only_at_night_with_an_onyx_for_each_corpse_by_the_slot(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    in_the_wild(game)
    slain(tables, game, ("bandit",) * 6)
    at_noon(game)
    assert servants.problem(game, cleric, "create_undead", None) == "only at night"
    at_night(game)
    ghouls = subject(game, cleric, "create_undead", "ghoul")
    assert "onyx" in magic.road_problem(game, cleric, "create_undead", ghouls)
    add_item(cleric, tables.items, "black_onyx", 6)
    cast(game, cleric, "create_undead", ghouls, 6)
    assert [r["cid"] for r in rules.records(cleric)] == ["ghoul"] * 3
    assert all(r["reach"] == 120 for r in rules.records(cleric))
    assert sum(it.qty for it in cleric.inventory if it.def_id == "black_onyx") == 6, "the stones are kept"
    out = cast(game, cleric, "create_undead", subject(game, cleric, "create_undead", "wight"), 7)  # (too low)
    assert "only ghouls answer" in " ".join(out)
    assert [r["cid"] for r in rules.records(cleric)] == ["ghoul"] * 6


def test_create_undead_at_slot_nine_raises_two_mummies_or_three_ghasts(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    in_the_wild(game)
    slain(tables, game, ("bandit",) * 5)
    at_night(game)
    add_item(cleric, tables.items, "black_onyx", 5)
    assert servants.count(game, cleric, "create_undead", "mummy", 9) == 2
    assert servants.count(game, cleric, "create_undead", "ghast", 9) == 3
    assert servants.count(game, cleric, "create_undead", "ghast", 8) == 2
    assert servants.count(game, cleric, "create_undead", "ghoul", 8) == 5


# ---------------------------------------------------------------------------- in a fight
def test_servants_come_in_beside_their_master_and_dodge_without_a_word(tables):
    wiz = hero(tables)
    rules.add(wiz, tables, "zombie", "animate_dead", until=10 ** 6, now=0)
    rules.add(wiz, tables, "skeleton", "animate_dead", until=10 ** 6, now=0)
    b = battle(tables, [wiz], ["bandit"], {0: (2, 4), 1: (12, 4)})
    me = b.fighters[0]
    dead = b.commanded_of(me)
    assert [x.cdef["name"] for x in dead] == ["zombie", "skeleton"] and all(b.gap(x, me) <= 2 for x in dead)
    z = dead[0]
    b.order = [z.id] + [x for x in b.order if x != z.id]
    b.turn, b.turn_started = 0, False
    b.step()
    assert z.dodging and z.action == 0
    my_turn(b, me)
    row = next(r for r in b.class_abilities(me) if r[0] == "command_objects")
    assert row[1].startswith("Command the dead") and row[2]


def test_commanded_by_the_player_the_dead_fight_and_the_word_carries_sixty_feet(tables):
    wiz = hero(tables)
    rules.add(wiz, tables, "zombie", "animate_dead", until=10 ** 6, now=0)
    rules.add(wiz, tables, "ghoul", "create_undead", until=10 ** 6, now=0)
    b = battle(tables, [wiz], ["bandit"], {0: (2, 4), 1: (4, 9)})
    me = b.fighters[0]
    zombie, ghoul = b.commanded_of(me)
    zombie.x, zombie.y = 2 + 14, 4  # (70 feet: beyond Animate Dead's 60)
    ghoul.x, ghoul.y = 2 + 20, 5  # (100 feet: within Create Undead's 120)
    my_turn(b, me)
    assert b.do_ability(me, "command_objects") is not False
    assert ghoul.bond.get("told") == b.round and zombie.bond.get("told") != b.round
    assert me.bonus == 0


def test_the_auto_commands_its_dead_and_they_strike(tables):
    wiz = hero(tables)
    for _ in range(3):
        rules.add(wiz, tables, "zombie", "animate_dead", until=10 ** 6, now=0)
    b = battle(tables, [wiz], ["bandit"], {0: (2, 4), 1: (5, 4)})
    me = b.fighters[0]
    sturdy(*b.side(FOE))
    my_turn(b, me)
    tactics._command_objects(b, me)
    assert all(x.bond.get("told") == b.round for x in b.commanded_of(me))
    b.end_turn()
    z = b.current
    assert z in b.commanded_of(me)
    b.step()  # (its turn begins: it has its orders, so it does not only Dodge)
    assert not z.dodging and z.action == 1
    tactics.take_turn(b, z)
    assert [e for e in b.events if e.get("kind") == "attack" and e.get("by") == z.id]


def test_after_the_fight_hurts_stay_and_the_destroyed_are_struck_off(tables):
    wiz = hero(tables)
    rules.add(wiz, tables, "zombie", "animate_dead", until=10 ** 6, now=0)
    rules.add(wiz, tables, "skeleton", "animate_dead", until=10 ** 6, now=0)
    b = battle(tables, [wiz], ["bandit"], {0: (2, 4), 1: (12, 4)})
    zombie, skeleton = b.commanded_of(b.fighters[0])
    zombie.hp = 5
    b._kill(skeleton, "test")
    assert skeleton.creature is not None and not skeleton.creature.alive
    rules.after(b, 0)
    assert [(r["cid"], r["hp"]) for r in rules.records(wiz)] == [("zombie", 5)]


# ---------------------------------------------------------------------------- Finger of Death
def test_finger_of_death_raises_a_slain_humanoid_as_its_casters_zombie_who_stays(tables):
    from tests.test_wave4 import cast as battle_cast

    wiz = hero(tables)
    b = battle(tables, [wiz], ["bandit", "bandit"], {0: (2, 4), 1: (8, 4), 2: (8, 7)})
    me, foe, other = b.fighters[0], b.side(FOE)[0], b.side(FOE)[1]
    sturdy(other)
    my_turn(b, me)
    battle_cast(b, me, "finger_of_death", target=foe)
    assert foe.state == "dead"
    my_turn(b, me)
    z = next(x for x in b.fighters if x.bond is not None and x.bond["kind"] == "servant")
    assert z.cdef["name"] == "zombie" and z.side == PARTY and not z.bond["word"] and z.bond["keep"]
    assert not b._waits_for_word(z) and b.gap(z, foe) <= 1
    assert b.order.index(z.id) == b.order.index(me.id) + 1
    out = rules.after(b, 0)
    rec = rules.records(wiz)[0]
    assert rec["cid"] == "zombie" and rec["until"] is None and not rec["word"] and out


def test_a_foes_finger_of_death_raises_its_own_zombie_for_the_fight_only(tables):
    from tests.test_wave4 import cast as battle_cast

    wiz, friend = hero(tables), hero(tables, "fighter", seed=2)
    b = battle(tables, [wiz, friend], ["bandit"], {0: (2, 4), 1: (2, 7), 2: (8, 4)})
    me, foe = b.fighters[0], b.side(FOE)[0]
    victim = next(f for f in b.side(PARTY) if f.char is friend)
    b.mark_rising(foe, victim, "zombie")
    victim.state = "dead"
    my_turn(b, foe)
    z = next(x for x in b.fighters if x.bond is not None and x.bond["kind"] == "servant")
    assert z.side == FOE
    rules.after(b, 0)
    assert not rules.records(wiz) and not rules.records(friend)
    assert battle_cast  # (the helper is the same as for the caster's own)


# ---------------------------------------------------------------------------- the ghast and the mummy
def test_the_ghasts_stench_poisons_and_a_save_spares_one_for_the_fight(tables):
    fighter = hero(tables, "fighter")
    b = battle(tables, [fighter], ["ghast"], {0: (4, 4), 1: (5, 4)})
    me, ghast = b.fighters[0], b.side(FOE)[0]
    saves = iter([False, True])
    b._save = lambda x, ab, dc, **kw: next(saves, True)
    my_turn(b, me)
    assert "poisoned" in me.conditions
    me.conditions.pop("poisoned", None)
    me.cond_ends.pop("poisoned", None)
    my_turn(b, me)
    assert me.id in ghast.spared and "poisoned" not in me.conditions
    my_turn(b, me)
    assert "poisoned" not in me.conditions


def test_the_ghasts_claw_paralyses_the_living(tables):
    fighter = hero(tables, "fighter")
    b = battle(tables, [fighter], ["ghast"], {0: (4, 4), 1: (5, 4)})
    me, ghast = b.fighters[0], b.side(FOE)[0]
    me.hp = 300
    claw = next(o for o in b.attack_options(ghast) if o.extra.get("id") == "claw")
    b._save = lambda x, ab, dc, **kw: False
    my_turn(b, ghast)
    for _ in range(10):
        b._attack(ghast, claw, me)
        if "paralyzed" in me.conditions:
            break
    assert "paralyzed" in me.conditions


def test_the_mummys_glare_frightens_and_a_save_spares_one(tables):
    fighter = hero(tables, "fighter")
    b = battle(tables, [fighter], ["mummy"], {0: (4, 4), 1: (8, 4)})
    me, mummy = b.fighters[0], b.side(FOE)[0]
    glare = next(o for o in b.attack_options(mummy) if o.extra.get("id") == "dreadful_glare")
    b._save = lambda x, ab, dc, **kw: True
    my_turn(b, mummy)
    b._attack(mummy, glare, me)
    assert me.id in mummy.spared and "frightened" not in me.conditions
    b._save = lambda x, ab, dc, **kw: False
    b._attack(mummy, glare, me)
    assert "frightened" not in me.conditions, "spared for the day"
    friend = hero(tables, "fighter", seed=3)
    b2 = battle(tables, [friend], ["mummy"], {0: (4, 4), 1: (8, 4)})
    b2._save = lambda x, ab, dc, **kw: False
    m2 = b2.side(FOE)[0]
    my_turn(b2, m2)
    b2._attack(m2, next(o for o in b2.attack_options(m2) if o.extra.get("id") == "dreadful_glare"), b2.fighters[0])
    assert "frightened" in b2.fighters[0].conditions


def test_the_rotting_fist_curses_no_healing_and_a_fall_to_it_is_dust(world, tables):
    fighter = hero(tables, "fighter")
    game = game_with(world, tables, hero(tables, "cleric", seed=5))
    b = battle(tables, [fighter], ["mummy"], {0: (4, 4), 1: (5, 4)})
    me, mummy = b.fighters[0], b.side(FOE)[0]
    fist = next(o for o in b.attack_options(mummy) if o.extra.get("id") == "rotting_fist")
    me.hp = me.char.hp = 300
    me.char.max_hp = 300
    my_turn(b, mummy)
    for _ in range(20):
        b._attack(mummy, fist, me)
        if me.no_heal:
            break
    assert me.no_heal and fighter.effects.get(rules.ROT)
    me.hp = 1
    for _ in range(20):
        b._attack(mummy, fist, me)
        if me.state != "fighting":
            break
    assert me.state == "dead" and fighter.effects.get(rules.DUST)
    now = float(game.world.time)
    body = {"char": fighter, "died": now, "since": now, "counted": 0.0, "repose": 0.0}
    assert "dust" in revival.problem(game, "raise_dead", body)
    assert "dust" not in (revival.problem(game, "true_resurrection", body) or "")


def test_the_rot_carried_after_the_fight_eats_the_maximum_until_remove_curse(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    in_the_wild(game)
    cleric.effects[rules.ROT] = float(game.world.time)
    top = cleric.max_hp
    cleric.hp = top - 10
    servants.tick(game)
    cleric.hp = top  # (healing that the rot will not allow)
    servants.tick(game)
    assert cleric.hp == top - 10
    game.world.time += rules.DAY + 1
    servants.tick(game)
    assert cleric.max_hp < top and cleric.effects.get(rules.ROT_LOST, 0) == top - cleric.max_hp
    game.world.time += 61  # (an hour passes: the marks are kept, not worn away)
    from realmwalker.rules import health

    health._timed_effects(cleric, 1.0, tables)
    assert cleric.effects.get(rules.ROT)
    add_item(cleric, tables.items, "silvered_salt")
    out = cast(game, cleric, "remove_curse", cleric)
    assert "rot" in " ".join(out) and cleric.max_hp == top and not cleric.effects.get(rules.ROT)


# ---------------------------------------------------------------------------- the battle screen
def test_the_battle_screen_lists_the_command_and_draws_the_dead(tables):
    from realmwalker.rules.engine import actions

    wiz = hero(tables)
    rules.add(wiz, tables, "ghoul", "create_undead", until=10 ** 6, now=0)
    b = battle(tables, [wiz], ["bandit"], {0: (2, 4), 1: (12, 4)})
    me = b.fighters[0]
    my_turn(b, me)
    ids = {o.id for o in actions.options(b, me)}
    assert any("command_objects" in i for i in ids)
    ghoul = b.commanded_of(me)[0]
    assert ghoul.bond.get("type") == "undead"


# ---------------------------------------------------------------------------- the fresh review's fixes
def test_reading_the_servants_leaves_a_fighter_without_spells(world, tables):
    fighter = hero(tables, "fighter", xp=0)
    game = game_with(world, tables, fighter)
    in_the_wild(game)
    had = dict(fighter.spells)
    servants.following(game)
    servants.tick(game)
    rules.bring_in(battle(tables, [fighter], ["bandit"], {0: (2, 4), 1: (9, 4)}), [])
    assert fighter.spells == had and "servants" not in fighter.spells
    rec = rules.add(fighter, tables, "zombie", "animate_dead", until=1, now=0)
    rules.drop(fighter, rec)
    assert "servants" not in fighter.spells


def test_rotting_away_to_nothing_is_a_real_death_and_true_resurrection_makes_them_whole(world, tables):
    cleric, friend = hero(tables, "cleric"), hero(tables, "fighter", seed=2)
    friend.companion = {"loyalty": 50, "wage": 0}
    game = game_with(world, tables, cleric, friend)
    in_the_wild(game)
    top = friend.max_hp
    friend.effects[rules.ROT] = float(game.world.time) or 1.0
    friend.max_hp = 3  # (all but gone already)
    friend.effects[rules.ROT_LOST] = float(top - 3)
    game.world.time += rules.DAY + 1
    servants.tick(game)
    assert not friend.alive and friend.effects.get(rules.DUST)
    assert friend not in game.party
    out = revival.return_to_life(game, friend, tables.spells["true_resurrection"],
                                 sp.op(tables.spells["true_resurrection"], "revive"), RNG(1, "r"))
    assert out and friend.alive and friend.max_hp == top and friend.hp == top
    assert not friend.effects.get(rules.DUST) and not friend.effects.get(rules.ROT)


def test_a_fist_on_someone_already_down_is_not_dust(tables):
    fighter = hero(tables, "fighter")
    b = battle(tables, [fighter], ["mummy"], {0: (4, 4), 1: (5, 4)})
    me, mummy = b.fighters[0], b.side(FOE)[0]
    fist = next(o for o in b.attack_options(mummy) if o.extra.get("id") == "rotting_fist")
    me.hp = 0
    me.state = "down"
    me.conditions = {"unconscious": -1, "prone": -1}
    me.death_saves = [0, 0]
    my_turn(b, mummy)
    b._attack(mummy, fist, me)
    assert not fighter.effects.get(rules.DUST)


def test_the_warning_comes_in_the_middle_of_a_long_rest(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    rules.add(wiz, tables, "zombie", "animate_dead", until=game.world.time + 6 * 60, now=game.world.time)
    game.pass_time(5 * 60, "rest")
    assert rules.records(wiz) and rules.records(wiz)[0]["warned"]
