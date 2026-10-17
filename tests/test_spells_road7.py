"""Spells outside battle, part E.7 (Expansion 3): great magic (Contingency, Magic Jar, Clone, Imprisonment) and Wish's
other uses (Instant Health, Object Creation, Resistance, Spell Immunity, Sudden Learning, Reshape Reality; Roll Redo in
a fight). Each is cast where it is used and met where it acts: a real fight, the meeting screen, a death, the sheet."""

import copy
from types import SimpleNamespace

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import companions, greatmagic, magic
from realmwalker.game.encounters import PendingEncounter
from realmwalker.game.state import new_game
from realmwalker.rules import feats, progression
from realmwalker.rules import spells as sp
from realmwalker.rules.combat import FOE, PARTY, Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import actions, check, query
from realmwalker.rules.inventory import add_item
from realmwalker.rules.progression import award_xp
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world

E7 = ["clone", "contingency", "imprisonment", "magic_jar"]
COMPONENTS = ("contingency_statuette", "gem_500", "flawless_diamond", "clone_vessel", "imprisonment_statuette")


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Lastrites", 37, "small"), tables)


@pytest.fixture(autouse=True)
def casters_know_them(monkeypatch):
    """Every caster in these tests has the spells of E.7 and Wish ready (Imprisonment is the warlock's too)."""
    real = sp.known_spells

    def known(char, tables):
        out = real(char, tables)
        return list(dict.fromkeys(out + E7 + ["wish"])) if sp.is_caster(char, tables) else out

    monkeypatch.setattr(sp, "known_spells", known)


def hero(tables, cls="wizard", xp=355000, seed=1, name=None):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("sage")
    c = b.build()
    if name:
        c.name = name
    if xp:
        award_xp(c, xp, tables, RNG(seed), auto=True)
    c.hp = c.max_hp
    add_item(c, tables.items, "component_pouch")
    for cid in COMPONENTS:
        add_item(c, tables.items, cid, 1)
    return c


def follower(tables, name, seed):
    c = hero(tables, "fighter", 0, seed, name)
    c.inventory = [it for it in c.inventory if it.def_id not in COMPONENTS]
    c.companion = {"order": "follow", "wage": 0, "loyalty": 60}
    return c


def game_with(world, tables, *party):
    game = new_game(copy.deepcopy(world), tables, party[0])
    for c in party[1:]:
        game.party.append(c)
    game.survival = False
    from realmwalker.game import pack

    pack.sync(game)
    return game


def cast(game, c, sid, target=None, slot=None):
    why = magic.road_problem(game, c, sid, target)
    assert why is None, f"{sid}: {why}"
    return magic.cast_on_road(game, c, sid, target, slot)


def subject(game, c, sid, kind=None, name=None):
    subs = magic.road_targets(game, c, sid)
    for s in subs:
        if (kind is None or s.kind == kind) and (name is None or name in s.name):
            return s
    raise AssertionError(f"{sid}: no subject {kind} {name} in {[s.name for s in subs][:30]}")


def text(lines) -> str:
    return " ".join(lines)


def in_the_wild(game):
    if game.local is not None:
        game.leave_local()
    for x in range(game.world.width):
        for y in range(game.world.height):
            if game.world.settlement_at(x, y) is None and game.world.danger[x, y] >= 1:
                game.player.x, game.player.y = x, y
                return
    raise AssertionError("no wild land")


def in_town(game):
    town = next(s for s in game.world.settlements if s.kind in ("town", "city"))
    game.player.x, game.player.y = town.x, town.y
    game.enter_local()
    return town


def battle(tables, party, foes, spots, seed=1):
    rng = RNG(seed, "foes")
    crs = [spawn(tables, d, rng, i + 1) for i, d in enumerate(foes)]
    b = Battle(tables, party, crs, Env(light=1.0), RNG(seed, "battle"), spots=spots)
    b.start()
    return b


def my_turn(b, f):
    b.order = [f.id] + [x for x in b.order if x != f.id]
    b.turn = 0
    b.turn_started = True
    b._start_of_turn(f)


def logged(b) -> str:
    return " ".join(line for line, _ in b.log)


# ---------------------------------------------------------------------------- the data
def test_the_four_spells_and_wish_are_in_and_the_start_up_check_knows_them(tables):
    assert not [p for p in check.problems(tables) if any(sid in p for sid in E7 + ["wish"])]
    for sid in E7:
        assert sp.out_of_battle(tables.spells[sid]), f"{sid} is never cast in a fight"
        assert sp.road_use(tables, sid) is not None
    assert sp.road_use(tables, "wish") == "wish", "Wish has its other uses outside a fight"
    stock = {line[0] for shop in tables.economy["shops"].values() for line in shop.get("stock", ())}
    for cid in COMPONENTS:
        assert tables.items.get(cid).get("how") or tables.items.get(cid).get("description")
        assert cid in stock, f"{cid} is sold somewhere"


# ---------------------------------------------------------------------------- Contingency
def test_contingency_holds_a_spell_and_spends_both_slots(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    assert "choose" in magic.road_problem(game, wiz, "contingency")
    held = greatmagic.contingent_spells(game, wiz)
    assert "fire_shield" in held and "fireball" not in held, "an action spell on yourself, not one at a foe"
    slots = sum(sp.slots_left(wiz, tables))
    t0 = game.world.time
    said = text(cast(game, wiz, "contingency", subject(game, wiz, "contingency", "contingency",
                                                       "Fire Shield (level 4), as a fight begins")))
    assert "statuette" in said and game.world.time - t0 >= 10
    assert sum(sp.slots_left(wiz, tables)) == slots - 2
    assert wiz.spells["contingency"]["spell"] == "fire_shield"
    assert any(it.def_id == "contingency_statuette" for it in wiz.inventory), "the statuette is kept"
    from realmwalker.ui.screens.spells import working_now

    assert "Contingency" in text(working_now(game))
    game.pass_time(11 * 24 * 60, "rest")
    assert "contingency" not in wiz.spells, "ten days, and it is gone"


def test_a_contingency_takes_effect_as_the_fight_begins(tables):
    wiz = hero(tables)
    wiz.spells["contingency"] = {"spell": "fire_shield", "slot": 4, "trigger": "start", "until": 1e12}
    b = battle(tables, [wiz], ["bandit"], {0: (2, 2), 1: (10, 10)})
    me = b.side(PARTY)[0]
    assert "Contingency" in logged(b) and me.buffs, "Fire Shield on the wizard before anyone moves"
    assert "contingency" not in wiz.spells


def test_a_contingency_when_brought_below_half(tables):
    wiz = hero(tables)
    wiz.spells["contingency"] = {"spell": "fire_shield", "slot": 4, "trigger": "bloodied", "until": 1e12}
    b = battle(tables, [wiz], ["bandit"], {0: (2, 2), 1: (3, 2)})
    me, foe = b.side(PARTY)[0], b.side(FOE)[0]
    b._hit(foe, me, 3, "slashing", crit=False, weapon="sword")
    assert "contingency" in wiz.spells, "not yet below half"
    b._hit(foe, me, me.hp - me.max_hp // 2 + 1, "slashing", crit=False, weapon="sword", raw=True)
    assert "contingency" not in wiz.spells and me.buffs


def test_a_contingency_cures_the_fallen(tables):
    cleric = hero(tables, "cleric")
    cleric.spells["contingency"] = {"spell": "cure_wounds", "slot": 5, "trigger": "down", "until": 1e12}
    b = battle(tables, [cleric], ["bandit"], {0: (2, 2), 1: (3, 2)})
    me, foe = b.side(PARTY)[0], b.side(FOE)[0]
    b._hit(foe, me, me.hp, "slashing", crit=False, weapon="sword", raw=True)
    assert me.state == "fighting" and me.hp > 0, "Cure Wounds the moment they fall"


def test_a_contingency_without_its_statuette_is_lost(tables):
    wiz = hero(tables)
    wiz.inventory = [it for it in wiz.inventory if it.def_id != "contingency_statuette"]
    wiz.spells["contingency"] = {"spell": "fire_shield", "slot": 4, "trigger": "start", "until": 1e12}
    b = battle(tables, [wiz], ["bandit"], {0: (2, 2), 1: (10, 10)})
    assert "statuette is not with them" in logged(b) and not b.side(PARTY)[0].buffs


# ---------------------------------------------------------------------------- Magic Jar
def test_magic_jar_on_the_road(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    slots = sum(sp.slots_left(wiz, tables))
    cast(game, wiz, "magic_jar")
    assert wiz.spells.get("jar") and sum(sp.slots_left(wiz, tables)) == slots - 1
    assert not any(it.def_id == "gem_500" for it in wiz.inventory), "the gem holds the soul"
    ok, why = sp.can_cast(wiz, tables, "fireball")
    assert not ok and "Magic Jar" in why
    said = text(cast(game, wiz, "magic_jar", subject(game, wiz, "magic_jar", "jar")))
    assert "home" in said and not wiz.spells.get("jar")
    assert sum(sp.slots_left(wiz, tables)) == slots - 1, "going home needs no slot"


def jar_fight(tables, seed=1):
    wiz = hero(tables)
    wiz.spells["jar"] = {"since": 0, "dc": 30}
    b = battle(tables, [wiz], ["bandit", "bandit", "bandit"],
               {0: (2, 2), 1: (8, 8), 2: (9, 8), 3: (8, 9)}, seed)
    return wiz, b, b.side(PARTY)[0], b.side(FOE)


def test_in_a_fight_the_body_lies_still_and_the_soul_takes_a_foe(tables, monkeypatch):
    wiz, b, me, foes = jar_fight(tables)
    assert "incapacitated" in me.conditions and me.can_act()
    my_turn(b, me)
    assert me.move_left == 0
    opts = actions.options(b, me)
    assert {o.id for o in opts} == {"ability:jar_possess", "ability:jar_return"}
    possess = next(o for o in opts if o.id == "ability:jar_possess")
    assert possess.available and set(possess.targets) == set(foes)
    assert not b.do_cast(me, "fireball", None, None, foes[0].cells[0]), "no spell from the gem"
    monkeypatch.setattr(b, "_save", lambda *a, **k: False)
    b.do_ability(me, "jar_possess", foes[0])
    host = foes[0]
    assert host.team == PARTY and b.ridden(host) and me.jar["host"] == host.id
    assert not me.can_act(), "the body lies still while the soul is away"
    my_turn(b, host)
    assert b.pending_party() is host, "the player plays the body the soul has taken"
    opt = next(o for o in b.attack_options(host) if o.available)
    hp = foes[1].hp
    for _ in range(6):
        if foes[1].hp < hp or not b.has_action(host):
            break
        b.do_attack(host, opt, foes[1])
    assert any(o.id == "ability:jar_leave" for o in actions.options(b, host))
    from realmwalker.rules import describe

    assert any(s.card.title == "Possessed" for s in describe.statuses(host, b))
    assert any(s.card.title == "Soul in the jar" for s in describe.statuses(me, b))


def test_leaving_a_body_and_going_home(tables, monkeypatch):
    wiz, b, me, foes = jar_fight(tables, 2)
    monkeypatch.setattr(b, "_save", lambda *a, **k: False)
    my_turn(b, me)
    b.do_ability(me, "jar_possess", foes[0])
    my_turn(b, foes[0])
    b.do_ability(foes[0], "jar_leave")
    assert foes[0].team == FOE and me.jar["host"] is None
    my_turn(b, me)
    b.do_ability(me, "jar_return")
    assert me.jar is None and "jar" not in wiz.spells and "incapacitated" not in me.conditions


def test_the_host_dies_and_the_soul_with_it_on_a_failed_save(tables, monkeypatch):
    wiz, b, me, foes = jar_fight(tables, 3)
    monkeypatch.setattr(b, "_save", lambda *a, **k: False)
    my_turn(b, me)
    b.do_ability(me, "jar_possess", foes[0])
    b._kill(foes[0], "a blow")
    assert me.state == "dead" and "jar" not in wiz.spells


def test_the_host_dies_and_the_soul_flees_home_on_a_good_save(tables, monkeypatch):
    wiz, b, me, foes = jar_fight(tables, 4)
    monkeypatch.setattr(b, "_save", lambda *a, **k: False)
    my_turn(b, me)
    b.do_ability(me, "jar_possess", foes[0])
    monkeypatch.setattr(b, "_save", lambda *a, **k: True)
    b._kill(foes[0], "a blow")
    assert me.state == "fighting" and me.jar["host"] is None


def test_a_host_left_standing_runs_when_the_fight_is_won(tables, monkeypatch):
    wiz, b, me, foes = jar_fight(tables, 5)
    monkeypatch.setattr(b, "_save", lambda *a, **k: False)
    my_turn(b, me)
    b.do_ability(me, "jar_possess", foes[0])
    for x in foes[1:]:
        b._kill(x, "a blow")
    b._check_end()
    assert b.outcome == "victory" and foes[0].state == "fled" and "possessed" not in foes[0].conditions
    assert wiz.spells.get("jar"), "the soul is back in its gem"


def test_the_auto_possesses_the_strongest(tables, monkeypatch):
    from realmwalker.rules import tactics

    wiz, b, me, foes = jar_fight(tables, 6)
    me.auto = True
    monkeypatch.setattr(b, "_save", lambda *a, **k: False)
    my_turn(b, me)
    tactics.take_turn(b, me)
    assert me.jar["host"] is not None


# ---------------------------------------------------------------------------- Clone
def test_a_clone_takes_the_leaders_soul_when_grown(world, tables):
    wiz = hero(tables)
    friend = follower(tables, "Osmund Reed", 7)
    game = game_with(world, tables, wiz, friend)
    in_the_wild(game)
    assert "town or city" in magic.road_problem(game, wiz, "clone", subject(game, wiz, "clone", "clone", wiz.name))
    town = in_town(game)
    t0 = game.world.time
    cast(game, wiz, "clone", subject(game, wiz, "clone", "clone", wiz.name))
    assert game.world.time - t0 >= 60
    assert not [it.def_id for it in wiz.inventory if it.def_id in ("clone_vessel", "flawless_diamond")]
    rec = greatmagic.clone_of(game, wiz)
    assert rec and rec["settlement"] == town.id
    game.leave_local()
    in_the_wild(game)
    game.over = {"cause": "killed by a troll", "place": ""}
    wiz.alive = False
    assert greatmagic.cheat_death(game) is None, "not grown yet"
    rec["ready"] = game.world.time
    carried = {it.def_id for it in wiz.inventory}
    said = text(greatmagic.cheat_death(game))
    assert "vessel" in said and game.over is None and wiz.alive and wiz.hp == wiz.max_hp
    assert (game.player.x, game.player.y) == (town.x, town.y) and game.party == [wiz]
    assert not wiz.inventory, "the clone has nothing"
    assert carried <= {it.def_id for it in friend.inventory}, "the companions bring what was carried"
    assert friend in game.waiting and friend.companion["wait_at"] == [town.x, town.y]
    assert greatmagic.clone_of(game, wiz) is None, "the clone is spent"


def test_a_companions_clone_takes_their_soul(world, tables):
    wiz = hero(tables)
    friend = follower(tables, "Osmund Reed", 7)
    game = game_with(world, tables, wiz, friend)
    town = in_town(game)
    cast(game, wiz, "clone", subject(game, wiz, "clone", "clone", friend.name))
    greatmagic.clone_of(game, friend)["ready"] = game.world.time
    friend.alive = False
    friend.hp = 0
    game.party.remove(friend)
    companions.died(game, friend)
    assert friend.alive and friend in game.waiting and friend.companion["wait_at"] == [town.x, town.y]


def test_the_death_screen_is_not_opened_when_a_clone_waits(make_app, world, tables):
    app = make_app()
    wiz = hero(app.tables)
    game = new_game(copy.deepcopy(world), app.tables, wiz)
    app.start_game(game)
    game.survival = False
    greatmagic.clones(game).append({"who": wiz.name, "settlement": game.world.settlements[0].id,
                                    "x": game.world.settlements[0].x, "y": game.world.settlements[0].y,
                                    "ready": 0, "made": 0})
    game.over = {"cause": "fell", "place": ""}
    wiz.alive = False
    app.screens[-1]._open_event_screen()
    assert game.over is None and type(app.screens[-1]).__name__ != "DeathScreen"


# ---------------------------------------------------------------------------- Imprisonment
def test_imprisonment_binds_the_strongest_of_a_band_seen_first(make_app, world, tables, monkeypatch):
    from realmwalker.ui.screens.encounter import EncounterScreen

    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    rng = RNG(5, "band")
    game.encounter = PendingEncounter("test", [spawn(tables, "bandit", rng, 1), spawn(tables, "ogre", rng, 2)],
                                      "They come.", True, "")
    assert "meeting screen" in magic.road_problem(game, wiz, "imprisonment")
    app = make_app()
    opts = {o[2]: o for o in EncounterScreen(app, game).options()}
    assert "imprison" in opts and opts["imprison"][3] and "ogre" in opts["imprison"][1]
    monkeypatch.setattr(greatmagic, "dice", SimpleNamespace(d20=lambda rng, **k: SimpleNamespace(natural=1)))
    xp = wiz.xp
    said = text(greatmagic.imprison(game))
    assert "ogre" in said.lower() and [cr.def_id for cr in game.encounter.creatures] == ["bandit"]
    assert wiz.xp > xp and not any(it.def_id == "imprisonment_statuette" for it in wiz.inventory)
    assert not game.encounter.spotted_first


def test_a_strong_will_throws_the_binding_off(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    game.encounter = PendingEncounter("test", [spawn(tables, "ogre", RNG(5), 1)], "It comes.", True, "")
    monkeypatch.setattr(greatmagic, "dice", SimpleNamespace(d20=lambda rng, **k: SimpleNamespace(natural=20)))
    monkeypatch.setattr(sp, "save_dc", lambda *a, **k: 10)
    greatmagic.imprison(game)
    assert len(game.encounter.creatures) == 1


# ---------------------------------------------------------------------------- Wish outside a fight
def wish_game(world, tables, *more):
    wiz = hero(tables)
    game = game_with(world, tables, wiz, *more)
    in_the_wild(game)
    return wiz, game


def test_wish_lists_its_uses_in_groups(world, tables):
    wiz, game = wish_game(world, tables)
    assert "choose the wish" in magic.road_problem(game, wiz, "wish")
    groups = [s.data.get("group") for s in magic.road_targets(game, wiz, "wish")]
    assert {"health", "object", "resist", "immune", "learn"} <= set(groups)
    assert groups == sorted(groups, key=groups.index), "each kind together"


def test_wishing_for_a_thing(world, tables):
    wiz, game = wish_game(world, tables)
    said = text(cast(game, wiz, "wish", subject(game, wiz, "wish", "object", "casket of diamonds")))
    assert any(it.def_id == "diamond_hoard" for it in wiz.inventory) and "toll" in said
    assert wiz.effects.get("wish_stress") and wiz.effects.get("wish_strength", 0) > 0
    assert not any(tables.items.get(i).get("magic") for i in greatmagic.wish_objects(game))
    assert all(int(tables.items.get(i)["value"]) <= 2500000 for i in greatmagic.wish_objects(game))


def test_a_wished_resistance_lasts_into_every_fight(world, tables):
    friend = follower(tables, "Osmund Reed", 7)
    wiz, game = wish_game(world, tables, friend)
    cast(game, wiz, "wish", subject(game, wiz, "wish", "resist", "fire"))
    assert "fire" in wiz.spells["wished_resist"] and "fire" in friend.spells["wished_resist"]
    game.pass_time(30 * 24 * 60, "rest")
    b = battle(tables, [wiz, friend], ["bandit"], {0: (2, 2), 1: (3, 2), 2: (10, 10)})
    me = b.side(PARTY)[0]
    assert query.resists(me, "fire") and not query.resists(me, "cold")
    assert not [s for s in magic.road_targets(game, wiz, "wish") if s.kind == "resist" and s.ref == "fire"]


def test_a_wished_immunity_keeps_a_spell_off(world, tables):
    wiz, game = wish_game(world, tables)
    choice = subject(game, wiz, "wish", "immune", "Hold Person")
    assert not [s for s in magic.road_targets(game, wiz, "wish") if s.kind == "immune" and s.ref == "bless"], \
        "only what is cast at you"
    cast(game, wiz, "wish", choice)
    b = battle(tables, [wiz], ["bandit"], {0: (2, 2), 1: (4, 2)})
    me, foe = b.side(PARTY)[0], b.side(FOE)[0]
    me.reaction = False  # (no Counterspell: the wish is what is tested)
    sp_ = tables.spells["hold_person"]
    b.cast(foe, "hold_person", sp_, me, None, up=0, mod=3, dc=40, bonus=5, mult=1, level=2)
    assert "paralyzed" not in me.conditions and "a wish keeps it off" in logged(b)
    game.survival = True
    game.pass_time(9 * 60, "rest")
    assert not wiz.effects.get("immune_spell:hold_person"), "eight hours"


def test_sudden_learning_trades_a_feat(world, tables):
    wiz, game = wish_game(world, tables)
    old = "skilled"
    assert feats.has(wiz, old)
    skills = list(wiz.skills)
    cast(game, wiz, "wish", subject(game, wiz, "wish", "learn", feats.name(tables, old)))
    assert not feats.has(wiz, old) and len(wiz.skills) < len(skills), "its skills go with it"
    choice = next(c for c in wiz.pending if c["kind"] == "relearn")
    opts = [o[0] for o in progression.options(wiz, tables, choice)]
    assert opts and f"feat:{old}" not in opts
    pick = progression.suggest(wiz, tables, choice) if hasattr(progression, "suggest") else opts[0]
    progression.resolve(wiz, tables, choice, pick)
    progression.auto_resolve(wiz, tables)
    assert choice not in wiz.pending and len(wiz.feats) == len([f for f in wiz.feats])
    assert feats.has(wiz, pick[5:])


def test_reshape_reality_forgets_your_crimes(world, tables):
    from realmwalker.world import factions as fx

    wiz, game = wish_game(world, tables)
    realm = None
    for s in game.world.settlements:
        realm = fx.realm_at(game.world, s.x, s.y)
        if realm is not None:
            game.player.x, game.player.y = s.x, s.y
            break
    assert realm is not None
    game.renown.bounties[realm.id] = 5000
    game.renown.crimes.append({"crime": "theft", "realm": realm.id, "reported": True, "settled": False,
                               "witnesses": [], "bounty": 5000})
    cast(game, wiz, "wish", subject(game, wiz, "wish", "reshape", "forgot your crimes"))
    assert game.renown.bounties[realm.id] == 0 and all(r["settled"] for r in game.renown.crimes)


def test_reshape_reality_carries_you_to_a_lost_artifact(world, tables):
    wiz, game = wish_game(world, tables)
    arts = game.world.politics.setdefault("artifacts", [])
    arts.append({"name": "the crown of ash", "site": 0, "kind": "crown"})
    for a in arts[:-1]:
        a["found"] = True
    cast(game, wiz, "wish", subject(game, wiz, "wish", "reshape", "rown of ash"))
    site = game.world.sites[0]
    assert (game.player.x, game.player.y) == (site.x, site.y)


def test_reshape_reality_brings_a_fallen_friend_back(world, tables):
    friend = follower(tables, "Osmund Reed", 7)
    wiz, game = wish_game(world, tables, friend)
    friend.alive = False
    friend.hp = 0
    game.party.remove(friend)
    game.fallen = [{"char": friend, "died": game.world.time, "since": game.world.time, "counted": 0.0,
                    "repose": 0.0, "cause": "a blade"}]
    cast(game, wiz, "wish", subject(game, wiz, "wish", "reshape", "Osmund were alive"))
    assert friend.alive and friend in game.party and not game.fallen


def test_reshape_reality_against_a_beast_of_the_songs(world, tables, monkeypatch):
    wiz, game = wish_game(world, tables)
    lairs = game.world.politics.get("lairs", {})
    living = [(k, h) for k, h in lairs.items() if game.world.figures.get(h) is not None
              and game.world.figures[h].alive]
    if not living:
        pytest.skip("no beast lives in this world")
    key, hid = living[0]
    monkeypatch.setattr(greatmagic, "RESHAPE_BEAST", 1.0)
    choice = next(s for s in magic.road_targets(game, wiz, "wish") if s.kind == "reshape" and s.ref == "beast"
                  and s.data["fig"] == hid)
    cast(game, wiz, "wish", choice)
    assert not game.world.figures[hid].alive and key not in game.world.politics.get("lairs", {})


def test_the_spells_page_jumps_between_the_kinds_of_wish(make_app, world, tables):
    import tcod

    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.spells import SpellsScreen

    app = make_app()
    wiz = hero(app.tables)
    app.start_game(new_game(copy.deepcopy(world), app.tables, wiz))
    screen = SpellsScreen(app, app.game)
    app.push(screen)
    screen.sel = screen.spells().index("wish")
    targets = screen.targets()
    assert targets[screen.target if screen.target < len(targets) else 0].data["group"] == "health"
    screen.target = 0
    app.handle_event(KeyEvent("right", shift=True))
    assert targets[screen.target].data["group"] == "object"
    app.handle_event(KeyEvent("right", shift=True))
    assert targets[screen.target].data["group"] == "resist"
    app.handle_event(KeyEvent("left", shift=True))
    assert targets[screen.target].data["group"] == "object" and targets[screen.target - 1].data["group"] == "health"
    app.render(tcod.console.Console(120, 40, order="F"))
    assert app.error_count == 0


# ---------------------------------------------------------------------------- Roll Redo, in a fight
def test_roll_redo_undoes_a_foes_hit(tables, monkeypatch):
    from realmwalker.rules import combat

    wiz = hero(tables)
    wiz.max_hp = wiz.hp = 400
    b = battle(tables, [wiz], ["ogre"], {0: (2, 2), 1: (3, 2)}, seed=3)
    me, foe = b.side(PARTY)[0], b.side(FOE)[0]
    me.reaction = False  # (no Shield: its slot would be this turn's)
    opt = next(o for o in b.attack_options(foe) if o.available)
    for _ in range(40):
        b._attack(foe, opt, me)
        if b.redo_options(me):
            break
    my_turn(b, me)
    redo = b.redo_options(me)
    assert redo, "an ogre's club landed"
    i, words, ok, why = redo[-1]
    assert ok and "ogre" in words.lower(), why
    hp = me.hp
    dealt = b._blow_damage(i)
    monkeypatch.setattr(combat.dice, "d20", lambda rng, **k: SimpleNamespace(natural=1))
    assert b.do_cast(me, f"wish:redo:{i}")
    assert me.hp == min(me.max_hp, hp + dealt) and wiz.effects.get("wish_stress")
    assert not any(j == i for j, *_ in b.redo_options(me)), "once undone, it is done"


def test_the_battle_screen_plays_the_soul_and_the_body_it_took(make_app, world, tables, monkeypatch):
    import tcod

    from realmwalker.game import fight
    from realmwalker.ui import widgets
    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.battle import BattleScreen

    app = make_app()
    wiz = hero(app.tables)
    wiz.spells["jar"] = {"since": 0, "dc": 30}
    game = new_game(copy.deepcopy(world), app.tables, wiz)
    app.start_game(game)
    game.survival = False
    rng = RNG(5, "band")
    game.encounter = PendingEncounter("test", [spawn(app.tables, "bandit", rng, i + 1) for i in range(3)],
                                      "They come.", False, "")
    b = fight.encounter_fight(game, False)
    game.encounter = None
    me, foes = b.side(PARTY)[0], b.side(FOE)
    screen = BattleScreen(app, game)
    app.push(screen)
    my_turn(b, me)
    for key in ("tab", "escape", "a", "escape"):  # (the soul's turn: only its two abilities)
        app.handle_event(KeyEvent(key))
    app.render(tcod.console.Console(160, 45, order="F"))
    monkeypatch.setattr(b, "_save", lambda *a, **k: False)
    my_turn(b, me)
    near = b.jar_targets(me)
    assert near, "a bandit within 100 feet, in sight"
    b.do_possess(me, near[0])
    host = near[0]
    assert "possessed" in host.conditions
    my_turn(b, host)
    assert screen.actor() is host
    for key in ("tab", "escape", "a", "escape", "z"):
        app.handle_event(KeyEvent(key))
    for size in ((80, 30), (160, 45)):
        screen.render(widgets.Canvas(tcod.console.Console(*size, order="F")))
    assert app.error_count == 0
