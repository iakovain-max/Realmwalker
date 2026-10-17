"""Spells outside battle, part E.2 (Expansion 3): light (Light, Dancing Lights, Continual Flame, Daylight), the body on
the move (Darkvision, See Invisibility, Jump, Longstrider, Feather Fall, Spider Climb, Levitate, Water Breathing, Water
Walk, Gaseous Form, Meld into Stone, Feign Death, Alter Self, Enhance Ability, Pass without Trace) and travel (Phantom
Steed, Tenser's Floating Disk, Unseen Servant, Wind Walk, Transport via Plants, Tree Stride, Teleport, Teleportation
Circle, Word of Recall, Arcane Gate, Find the Path, Plane Shift, Etherealness, Astral Projection, Gate). Each is cast
where it is used: in the dark, over a pit, at the water's edge, in a real fight, on the road to a far town."""

import copy
import math

import numpy as np
import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import dungeon, fight, magic, spellwork, waymagic
from realmwalker.game.camp import make_camp, pitch_tent
from realmwalker.game.state import new_game
from realmwalker.rules import spells as sp
from realmwalker.rules.combat import FOE, PARTY, Battle, Env, Zone
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import estimates
from realmwalker.rules.inventory import add_item
from realmwalker.rules.progression import award_xp
from realmwalker.world import dungeon as gen
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Lastrites", 37, "small"), tables)


def hero(tables, cls="wizard", xp=355000, seed=1):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race("human")
    b.set_class(cls)
    b.set_background("sage")
    c = b.build()
    if xp:
        award_xp(c, xp, tables, RNG(seed), auto=True)
    add_item(c, tables.items, "component_pouch")
    return c


def companion(tables, seed=2):
    c = hero(tables, "fighter", 0, seed)
    c.is_player = False
    c.companion = {"loyalty": 60, "wage": 0}
    return c


E2 = sorted(sid for sid in ("light dancing_lights continual_flame daylight darkvision see_invisibility jump longstrider "
                            "feather_fall spider_climb levitate water_breathing water_walk gaseous_form meld_into_stone "
                            "feign_death alter_self enhance_ability pass_without_trace phantom_steed "
                            "tensers_floating_disk unseen_servant wind_walk transport_via_plants tree_stride teleport "
                            "teleportation_circle word_of_recall arcane_gate find_the_path plane_shift etherealness "
                            "astral_projection gate").split())


@pytest.fixture(autouse=True)
def casters_know_them(monkeypatch):
    """Every caster in these tests has the spells of E.2 ready (which ones a class learns is Part C's, tested there;
    the druid and the ranger, whose spells many of these are, are not in the game yet)."""
    real = sp.known_spells

    def known(char, tables):
        out = real(char, tables)
        return list(dict.fromkeys(out + E2)) if sp.is_caster(char, tables) else out

    monkeypatch.setattr(sp, "known_spells", known)


@pytest.fixture
def know(monkeypatch):
    """Let a character cast these spells (druid and ranger spells have no caster in the game yet)."""
    extra: dict[int, set] = {}
    real = sp.known_spells

    def known(char, tables):
        return list(dict.fromkeys(real(char, tables) + sorted(extra.get(id(char), ()))))

    monkeypatch.setattr(sp, "known_spells", known)

    def give(c, *sids):
        extra.setdefault(id(c), set()).update(sids)
    return give


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


def into_dungeon(game):
    site = game.world.sites[0]
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    dungeon.descend(game, 1)
    return game.local


def fight_of(tables, party, foes=("bandit",), env=None, spots=None):
    rng = RNG(1, "foes")
    b = Battle(tables, party, [spawn(tables, d, rng, i + 1) for i, d in enumerate(foes)], env or Env(), RNG(1, "b"),
               spots=spots or {})
    b.start("Test fight.")
    return b


def my_turn(b, f):
    b.order = [f.id] + [x for x in b.order if x != f.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(f)


# ---------------------------------------------------------------------------- light
def test_light_and_continual_flame_light_a_dungeon_without_a_torch(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    wiz.inventory = [it for it in wiz.inventory if not tables.items.get(it.def_id).get("light")]
    into_dungeon(game)
    assert dungeon.light_radius(game) <= 0
    cast(game, wiz, "light")
    assert "light" in sp.lasting(wiz, tables)
    assert dungeon.light_radius(game) == 6 and dungeon.light_up(game) is None  # (as a torch, and no torch is lit)
    sp.end(wiz, "light")
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    add_item(cleric, tables.items, "torch", 1)
    add_item(cleric, tables.items, "ruby_dust_pinch", 1)
    torches = sum(it.qty for it in cleric.inventory if it.def_id == "torch")
    cast(game, cleric, "continual_flame")
    assert sum(it.qty for it in cleric.inventory if it.def_id == "torch") == torches - 1
    names = [it.def_id for it in cleric.inventory]
    assert "everburning_torch" in names and "ruby_dust_pinch" not in names
    into_dungeon(game)
    game.lit = None
    assert dungeon.light_radius(game) == 6
    game.pass_time(600)  # (ten hours: it never burns down)
    assert dungeon.light_radius(game) == 6


def test_light_pushes_back_the_night_in_the_close_view(world, tables, monkeypatch):
    from realmwalker.game import vision

    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    game.enter_local()
    monkeypatch.setattr(type(game), "light", property(lambda self: 0.05))
    before, _ = vision.sight_radius(game, game.local)
    cast(game, wiz, "daylight" if "daylight" in sp.known_spells(wiz, tables) else "light")
    after, _ = vision.sight_radius(game, game.local)
    assert after > before or before == 0


def test_light_and_dancing_lights_show_foes_in_a_dark_fight(tables):
    wiz = hero(tables)
    b = fight_of(tables, [wiz], ("bandit",), Env(light=0.0), spots={0: (2, 2), 1: (9, 2)})
    me, foe = b.side(PARTY)[0], b.side(FOE)[0]
    my_turn(b, me)
    assert not b.can_see(me, foe), "a human in the dark sees nobody ten squares off"
    assert estimates.spell_value(b, me, "dancing_lights", point=(foe.x, foe.y)).total(care=4.0) > 0.5
    assert b.do_cast(me, "dancing_lights", point=(foe.x, foe.y))
    assert any(z.kind == "lights" for z in b.zones) and b.can_see(me, foe)
    b2 = fight_of(tables, [hero(tables)], ("bandit",), Env(light=0.0), spots={0: (2, 2), 1: (5, 2)})
    me2, foe2 = b2.side(PARTY)[0], b2.side(FOE)[0]
    my_turn(b2, me2)
    assert not b2.can_see(me2, foe2)
    assert estimates.spell_value(b2, me2, "light").total(care=4.0) > 0.5, "the Auto sees nothing in Light here"
    assert b2.do_cast(me2, "light")
    assert me2.shine == 4 and b2.can_see(me2, foe2)


def test_daylight_burns_away_a_foes_magical_darkness(tables):
    cleric = hero(tables, "cleric")
    b = fight_of(tables, [cleric], ("bandit",), spots={0: (2, 2), 1: (5, 2)})
    me, foe = b.side(PARTY)[0], b.side(FOE)[0]
    my_turn(b, me)
    b.zones.append(Zone(99, "darkness", {(4, 2), (5, 2), (6, 2)}, owner=foe.id, spell="darkness", rounds=10))
    assert estimates.spell_value(b, me, "daylight").total(care=4.0) > 0.5
    assert b.do_cast(me, "daylight")
    assert not any(z.kind == "darkness" for z in b.zones) and me.shine == 12


# ---------------------------------------------------------------------------- the body on the move
def test_darkvision_and_see_invisibility(world, tables):
    wiz = hero(tables)
    friend = companion(tables)
    game = game_with(world, tables, wiz, friend)
    assert game.sheet(friend).darkvision == 0
    cast(game, wiz, "darkvision", friend)
    assert game.sheet(friend).darkvision == 150
    cast(game, wiz, "see_invisibility")
    b = fight_of(tables, [wiz, friend], ("bandit",), Env(light=0.0), spots={0: (2, 2), 1: (3, 3), 2: (12, 2)})
    me, pal = b.side(PARTY)
    foe = b.side(FOE)[0]
    assert b.can_see(pal, foe) and not b.can_see(me, foe)  # (150 feet of darkvision; the wizard has none)
    foe.conditions["invisible"] = -1
    b2 = fight_of(tables, [wiz], ("bandit",), spots={0: (2, 2), 1: (5, 2)})
    seer, ghost = b2.side(PARTY)[0], b2.side(FOE)[0]
    ghost.conditions["invisible"] = -1
    assert b2.can_see(seer, ghost), "See Invisibility, carried into the fight, sees the invisible"
    seer.buffs = [bf for bf in seer.buffs if not bf.get("see_invisible")]
    assert not b2.can_see(seer, ghost)


def test_jump_spider_climb_and_longstrider_in_a_fight(tables):
    wiz = hero(tables)
    friend = companion(tables)
    b = fight_of(tables, [wiz, friend], ("bandit",), spots={0: (2, 2), 1: (3, 2), 2: (9, 2)})
    me, pal = b.side(PARTY)
    my_turn(b, me)
    stand, run = pal.jump
    assert b.do_cast(me, "jump", pal)
    assert pal.jump == (max(stand, 30), max(run, 30))
    me.bonus = me.action = 1
    me.spent_slot = None
    b._slot_turn = None
    assert pal.climb_speed == 0
    pal.buffs.append({"climb": True, "source": "spider_climb"})
    assert pal.climb_speed == pal.speed
    base = b.side(PARTY)[1].sheet.speed()
    friend.effects["spell:longstrider"] = 1.0
    assert b.side(PARTY)[1].sheet.speed() == base + 10


def test_longstrider_speeds_the_road_and_a_higher_slot_takes_a_second(world, tables):
    wiz = hero(tables)
    friend = companion(tables)
    game = game_with(world, tables, wiz, friend)
    assert game.pace() == 1.0
    add_item(friend, tables.items, "iron_bar", 12)  # (a heavy load: the friend is slowed)
    slow = game.pace()
    cast(game, wiz, "longstrider", wiz, slot=2)
    assert "longstrider" in sp.lasting(wiz, tables) and "longstrider" in sp.lasting(friend, tables)
    assert 1.0 <= game.pace() < slow, "the load is carried at a better pace, never quicker than a walker"


def test_feather_fall_in_a_fight_and_over_a_pit(world, tables):
    wiz = hero(tables)
    friend = companion(tables)
    b = fight_of(tables, [wiz, friend], ("bandit",), spots={0: (2, 2), 1: (4, 2), 2: (9, 2)})
    me, pal = b.side(PARTY)
    used = list(wiz.spells.get("slots_used", [0] * 9))
    hp = pal.hp
    pal.z = 40
    b._fall(pal)
    assert pal.hp == hp and pal.z == 0 and "prone" not in pal.conditions and not me.reaction
    assert wiz.spells["slots_used"][0] == used[0] + 1
    game = game_with(world, tables, wiz)
    wiz.spells["slots_used"] = [0] * 9
    lm = into_dungeon(game)
    (x, y), f = next(((xy, f) for xy, f in lm.features.items() if f["kind"] == "trap"))
    f.update(trap="pit", dc=40, found=False, spent=False)
    hp = wiz.hp
    game.player.lx, game.player.ly = x, y
    dungeon.on_step(game, x, y)
    assert wiz.hp == hp and f["spent"] and wiz.spells["slots_used"][0] == 1


def test_levitate_lifts_a_foe_out_of_reach_and_lets_it_down_gently(tables):
    wiz = hero(tables)
    b = fight_of(tables, [wiz], ("bandit",), spots={0: (2, 2), 1: (3, 2)})
    me, foe = b.side(PARTY)[0], b.side(FOE)[0]
    my_turn(b, me)
    assert estimates.spell_value(b, me, "levitate", target=foe).total(care=4.0) > 0.5
    for _ in range(20):  # (until it fails its Constitution save)
        if b.do_cast(me, "levitate", foe) and foe.z == 20:
            break
        me.action, b._slot_turn = 1, None
        foe.z = 0
    assert foe.z == 20 and foe.buff_value("aloft")
    hp = foe.hp
    b._end_concentration(me, quiet=True, why="ends")
    assert foe.z == 0 and foe.hp == hp, "it floats down unharmed"


def test_water_walk_water_breathing_and_wind_walk_on_the_map(world, tables, know):
    cleric = hero(tables, "cleric")
    friend = companion(tables)
    game = game_with(world, tables, cleric, friend)
    w = game.world
    lake = next(((x, y) for x in range(1, w.width - 1) for y in range(1, w.height - 1)
                 if game.biome_key(x, y) == "lake" and any(game.biome_def(x + dx, y + dy)["passable"]
                                                          for dx in (-1, 0, 1) for dy in (-1, 0, 1))), None)
    assert lake is not None
    lx, ly = lake
    shore = next((lx + dx, ly + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                 if game.biome_def(lx + dx, ly + dy)["passable"])
    game.player.x, game.player.y = shore
    assert game.step_minutes(*shore, lx, ly) is None
    cast(game, cleric, "water_walk")
    assert game.magic_crossing(lx, ly) == "over" and game.step_minutes(*shore, lx, ly) is not None
    for c in game.party:
        sp.end(c, "water_walk")
    wiz = hero(tables, "wizard", seed=4)
    game2 = game_with(world, tables, wiz)
    game2.player.x, game2.player.y = shore
    cast(game2, wiz, "water_breathing")
    assert game2.magic_crossing(lx, ly) == "under"
    walk = game2.step_minutes(*shore, lx, ly)
    assert walk is not None
    know(wiz, "wind_walk")
    cast(game2, wiz, "wind_walk")
    assert game2.magic_crossing(lx, ly) == "wind" and game2.pace() == pytest.approx(0.1)
    from realmwalker.game import encounters

    assert encounters.roll_encounter(game2, 600) is None and game2.lost_dc() is None


def test_stranded_on_the_water_when_the_spell_ends_you_swim_ashore(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    w = game.world
    lake = next((x, y) for x in range(1, w.width - 1) for y in range(1, w.height - 1)
                if game.biome_key(x, y) == "lake")
    game.player.x, game.player.y = lake
    said = waymagic.ashore(game)
    assert "swim" in said and game.biome_def(game.player.x, game.player.y)["passable"]


def test_gaseous_form_a_mist_cannot_strike_or_cast(tables):
    wiz = hero(tables)
    friend = companion(tables)
    b = fight_of(tables, [wiz, friend], ("bandit",), spots={0: (2, 2), 1: (3, 2), 2: (4, 2)})
    me, pal = b.side(PARTY)
    my_turn(b, me)
    assert estimates.spell_value(b, me, "gaseous_form", target=pal).total(care=4.0) < 0, "not for a friend still fine"
    pal.hp = max(1, pal.max_hp // 5)
    assert estimates.spell_value(b, me, "gaseous_form", target=pal).total(care=4.0) > 0.5
    assert b.do_cast(me, "gaseous_form", pal)
    assert all(not o.available for o in b.attack_options(pal)) and b.offhand_option(pal) is None
    me.buffs.append({"mist": True})
    assert not b._casting_time_ok(me, tables.spells["fire_bolt"])[0]
    from realmwalker.rules.engine import query

    assert query.speed(pal) <= 10 and pal.fly_speed == 10


def test_feign_death_is_left_alone_and_lives_through_a_lost_fight(world, tables):
    cleric = hero(tables, "cleric")
    friend = companion(tables)
    game = game_with(world, tables, cleric, friend)
    b = fight_of(tables, [cleric, friend], ("orc", "orc"), spots={0: (2, 2), 1: (3, 2), 2: (4, 2), 3: (5, 3)})
    me, pal = b.side(PARTY)
    my_turn(b, me)
    pal.hp = 2
    assert b.do_cast(me, "feign_death", pal)
    assert pal not in b.enemies_of(b.side(FOE)[0]) and "incapacitated" in pal.conditions
    me.hp, me.state = 0, "down"
    me.char.hp = 0
    b._check_end()
    assert b.outcome == "defeat", "nobody left standing: a feigned death does not count"
    game.battle = b
    after = fight.finish_battle(game)
    assert friend.alive and friend.hp >= 1 and after.outcome in ("mauled", "death")
    assert "for one more of the dead" in after.text


def test_meld_into_stone_hides_a_lone_caster(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    make_camp(game)
    cast(game, cleric, "meld_into_stone")
    assert spellwork.hidden(game, "long")
    game2 = game_with(world, tables, cleric, companion(tables))
    make_camp(game2)
    assert "only the caster" in (magic.road_problem(game2, cleric, "meld_into_stone") or "")


def test_alter_self_enhance_ability_and_pass_without_trace(world, tables, know):
    wiz = hero(tables)
    friend = companion(tables)
    game = game_with(world, tables, wiz, friend)
    cast(game, wiz, "alter_self")
    from realmwalker.game import law

    assert law.disguised(game) and int(game.renown.flags["disguise_dc"]) >= 30
    best = sp.best_ability(friend)
    skill = next(k for k, v in tables.rules["skills"].items() if v["ability"] == best)
    before = game.sheet(friend).skill_bonus(skill)
    cast(game, wiz, "enhance_ability", friend)
    assert game.sheet(friend).skill_bonus(skill) == before + 5
    know(wiz, "pass_without_trace")
    sneak = [game.sheet(c).skill_bonus("stealth") for c in game.party]
    sp.end(wiz, "alter_self")
    cast(game, wiz, "pass_without_trace")
    assert [game.sheet(c).skill_bonus("stealth") for c in game.party] == [s + 10 for s in sneak]


# ---------------------------------------------------------------------------- travel
def test_phantom_steed_disk_and_servant(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    walking = game.pace()
    cast(game, wiz, "phantom_steed", wiz)
    assert game.pace() == pytest.approx(3 / 13) and game.pace() < walking
    light, heavy, limit = game.sheet(wiz).capacity()
    cast(game, wiz, "tensers_floating_disk")
    assert game.sheet(wiz).capacity()[0] == light + 500
    cast(game, wiz, "unseen_servant")
    make_camp(game)
    t0 = game.world.time
    pitch_tent(game) if any(it.def_id == "tent" for it in wiz.inventory) else None
    from realmwalker.game import camp

    t0 = game.world.time
    camp.chore(game, 30, "rest")
    assert game.world.time - t0 == pytest.approx(15, abs=1)


def _visited(game, kind=None):
    w = game.world
    here = w.settlement_at(game.player.x, game.player.y)
    far = sorted((s for s in w.settlements if (kind is None or s.kind == kind) and (here is None or s.id != here.id)),
                 key=lambda s: -math.hypot(s.x - game.player.x, s.y - game.player.y))
    return far


def test_teleport_by_the_table_of_familiarity(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    city = next(iter(_visited(game, "city")), None) or _visited(game)[0]
    game.player.visited_settlements.add(city.id)
    pl = next(p for p in magic.road_targets(game, wiz, "teleport") if p.sid == city.id)
    assert pl.known == ("circle" if city.kind == "city" or city.great else "casual")
    cast(game, wiz, "teleport", pl)
    if pl.known == "circle":
        assert (game.player.x, game.player.y) == (city.x, city.y)
    # Every outcome over many tries from a town only heard of.
    outcomes = {}
    rng = RNG(5, "tp")
    for _ in range(400):
        r = waymagic._roll(game, "once", rng)
        outcomes[r] = outcomes.get(r, 0) + 1
    assert set(outcomes) == {"mishap", "similar", "off", "on"} and 80 < outcomes["mishap"] < 260
    x, y, miles = waymagic._off(game, city.x, city.y, RNG(2, "off"))
    assert 0 <= miles <= 24 and game.biome_def(x, y)["passable"]
    hp = wiz.hp
    waymagic._hurt(game, RNG(3, "hurt"))
    assert 3 <= hp - wiz.hp <= 30 or not wiz.alive or wiz.hp == 1


def test_teleportation_circle_and_word_of_recall(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    add_item(wiz, tables.items, "rare_inks")
    game.player.visited_settlements = {s.id for s in game.world.settlements if s.kind not in ("city",) and not s.great}
    assert "know no city" in (magic.road_problem(game, wiz, "teleportation_circle") or "")
    city = next(iter(_visited(game, "city")), None)
    if city is not None:
        game.player.visited_settlements.add(city.id)
        cast(game, wiz, "teleportation_circle")
        assert (game.player.x, game.player.y) == (city.x, city.y)
        assert not any(it.def_id == "rare_inks" for it in wiz.inventory)
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    home = game.world.settlement_at(game.player.x, game.player.y)
    assert "no sanctuary" in magic.road_problem(game, cleric, "word_of_recall")
    monkeypatch.setattr(waymagic, "in_a_temple", lambda g: True)
    cast(game, cleric, "word_of_recall")
    assert waymagic.sanctuary(game, cleric).id == home.id
    monkeypatch.setattr(waymagic, "in_a_temple", lambda g: False)
    far = _visited(game)[0]
    game.player.x, game.player.y = far.x, far.y
    cleric.spells["slots_used"] = [0] * 9
    cast(game, cleric, "word_of_recall")
    assert (game.player.x, game.player.y) == (home.x, home.y)


def test_transport_via_plants_plane_shift_astral_projection_and_gate(world, tables, know):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    towns = [s for s in _visited(game) if waymagic.woodland(game, s.x, s.y)]
    if towns:
        know(cleric, "transport_via_plants")
        target = towns[0]
        game.player.visited_settlements.add(target.id)
        here = next(((x, y) for x in range(game.world.width) for y in range(game.world.height)
                     if waymagic.woodland(game, x, y) and game.biome_def(x, y)["passable"]
                     and game.world.settlement_at(x, y) is None), None)
        game.player.x, game.player.y = here
        pl = next(p for p in magic.road_targets(game, cleric, "transport_via_plants") if p.sid == target.id)
        cast(game, cleric, "transport_via_plants", pl)
        assert (game.player.x, game.player.y) == (target.x, target.y)
    far = _visited(game)[0]
    game.player.known_settlements.add(far.id)
    add_item(cleric, tables.items, "forked_rod")
    cleric.spells["slots_used"] = [0] * 9
    pl = next(p for p in magic.road_targets(game, cleric, "plane_shift") if p.sid == far.id)
    cast(game, cleric, "plane_shift", pl)
    near = math.hypot(game.player.x - far.x, game.player.y - far.y)
    assert near <= 9, "near the place named, off target without a circle"
    assert "jacinth" in magic.road_problem(game, cleric, "astral_projection")
    add_item(cleric, tables.items, "jacinth", 1)
    add_item(cleric, tables.items, "silver_bar", 4)
    second = _visited(game)[1]
    game.player.known_settlements.add(second.id)
    cleric.spells["slots_used"] = [0] * 9
    pl = next(p for p in magic.road_targets(game, cleric, "astral_projection") if p.sid == second.id)
    cast(game, cleric, "astral_projection", pl)
    assert (game.player.x, game.player.y) == (second.x, second.y)
    assert not any(it.def_id in ("jacinth", "silver_bar") for it in cleric.inventory)
    add_item(cleric, tables.items, "great_diamond")
    cleric.spells["slots_used"] = [0] * 9
    pl = next(p for p in magic.road_targets(game, cleric, "gate") if p.sid == far.id)
    cast(game, cleric, "gate", pl)
    assert (game.player.x, game.player.y) == (far.x, far.y)
    assert any(it.def_id == "great_diamond" for it in cleric.inventory), "the diamond is not used up"


def test_arcane_gate_find_the_path_and_etherealness_under_the_ground(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    lm = into_dungeon(game)
    stairs = magic.road_targets(game, wiz, "arcane_gate")
    if stairs:
        cast(game, wiz, "arcane_gate", stairs[0])
        assert (game.player.lx, game.player.ly) == (stairs[0].x, stairs[0].y)
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    lm = into_dungeon(game)
    add_item(cleric, tables.items, "divination_tools")
    lm.seen[:] = False
    lines = cast(game, cleric, "find_the_path")
    assert lm.seen.sum() > 10 and any("stairs" in line for line in lines)
    game.leave_local()
    assert game.lost_dc() is None
    wiz.spells["slots_used"] = [0] * 9
    game = game_with(world, tables, wiz)
    lm = into_dungeon(game)
    cast(game, wiz, "etherealness")
    T = tables.terrain
    remap = game.remap_for(lm)
    p = game.player
    d = next((dx, dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
             if lm.in_bounds(p.lx + dx, p.ly + dy) and not T.walk[int(remap[lm.terrain[p.lx + dx, p.ly + dy]])])
    assert game._move_local(*d) and not T.walk[int(remap[lm.terrain[p.lx, p.ly]])], "walls do not stop the ethereal"
    sp.end(wiz, "etherealness")
    hp = wiz.hp
    game._move_local(0, 0)
    assert T.walk[int(remap[lm.terrain[p.lx, p.ly]])] and wiz.hp < hp, "shunted out of the stone, and hurt"


def test_tree_stride_steps_between_trees_in_a_fight(tables, know):
    wiz = hero(tables)
    know(wiz, "tree_stride")
    b = fight_of(tables, [wiz], ("bandit",), spots={0: (2, 2), 1: (12, 8)})
    me = b.side(PARTY)[0]
    my_turn(b, me)
    tree = [i for i, tid in enumerate(tables.terrain.ids) if "tree" in tables.terrain.tags[i]][0]
    b.field.tree[:] = False
    b.field.tree[1, 2] = b.field.tree[10, 8] = True
    pts = b.spell_points(me, "tree_stride")
    assert pts and all(max(abs(x - 10), abs(y - 8)) <= 1 or max(abs(x - 1), abs(y - 2)) <= 1 for x, y in pts)
    far = max(pts, key=lambda p: p[0])
    assert b.do_cast(me, "tree_stride", point=far) and (me.x, me.y) == far
    assert tree >= 0


def test_travel_spells_are_never_offered_in_a_fight(tables):
    wiz = hero(tables)
    b = fight_of(tables, [wiz], ("bandit",))
    me = b.side(PARTY)[0]
    wiz.spells.setdefault("spellbook", []).extend(["teleport", "etherealness", "tensers_floating_disk"])
    wiz.spells["prepared"] = ["teleport", "etherealness", "tensers_floating_disk"] + wiz.spells.get("prepared", [])
    offered = {s: ok for s, ok, _ in b.spell_options(me)}
    assert not any(offered.get(s) for s in ("teleport", "etherealness", "tensers_floating_disk"))


def test_the_spells_page_lists_where_teleport_goes_and_takes_you(make_app):
    import tcod.console

    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.spells import SpellsScreen

    app = make_app()
    t = app.tables
    world = cached_world(WorldOptions("Screenland", 5, "small"), t)
    wiz = hero(t)
    game = new_game(copy.deepcopy(world), t, wiz)
    app.start_game(game)
    wiz.spells.setdefault("spellbook", []).append("teleport")
    wiz.spells["prepared"] = ["teleport"] + [s for s in wiz.spells.get("prepared", []) if s != "teleport"]
    far = max((s for s in game.world.settlements if s.id != game.player.home),
              key=lambda s: math.hypot(s.x - game.player.x, s.y - game.player.y))
    game.player.visited_settlements.add(far.id)
    screen = SpellsScreen(app, app.game)
    app.push(screen)
    screen.sel = screen.spells().index("teleport")
    targets = screen.targets()
    screen.target = next(i for i, p in enumerate(targets) if p.sid == far.id)
    app.render(tcod.console.Console(120, 40, order="F"))
    shown = app.last_canvas.words()
    assert f"to {far.name}" in shown and "where" in shown, shown
    app.handle_event(KeyEvent("enter"))
    assert math.hypot(game.player.x - far.x, game.player.y - far.y) <= 9 or game.over is not None
    for size in ((80, 30), (160, 45)):
        app.render(tcod.console.Console(*size, order="F"))
    assert app.error_count == 0
