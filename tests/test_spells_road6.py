"""Spells outside battle, part E.6 (Expansion 3): lasting protections (Glyph of Warding, Symbol, Magic Circle,
Forbiddance, Guards and Wards, Mordenkainen's Private Sanctum, Hallow) and the caster's keeping (Demiplane, Tasha's
Bubbling Cauldron). Each is cast where it is used: at a camp in the wild, underground, at an inn in town, on a haunted
field; and met where it acts: the night's visitors, a rest while hunters search, and a real fight."""

import copy
from types import SimpleNamespace

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import camp, divining, dungeon, economy, encounters, fight, magic, past, services, spellwork, warding
from realmwalker.game.encounters import PendingEncounter
from realmwalker.game.state import new_game
from realmwalker.rules import spells as sp
from realmwalker.rules.combat import FOE, PARTY, Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import check, query
from realmwalker.rules.inventory import add_item
from realmwalker.rules.progression import award_xp
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world

E6 = sorted(("glyph_of_warding symbol guards_and_wards forbiddance magic_circle mordenkainens_private_sanctum hallow "
             "demiplane tashas_bubbling_cauldron").split())
COMPONENTS = ("glyph_diamond_dust", "symbol_diamond_dust", "silver_rod", "hallowing_incense", "silvered_salt",
              "gilded_ladle", "ruby_dust")


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Lastrites", 37, "small"), tables)


@pytest.fixture(autouse=True)
def casters_know_them(monkeypatch):
    """Every caster in these tests has the spells of E.6 ready (the bard, the druid and the warlock, whose spells some
    of these are, are not in the game yet)."""
    real = sp.known_spells

    def known(char, tables):
        out = real(char, tables)
        return list(dict.fromkeys(out + E6 + ["fireball"])) if sp.is_caster(char, tables) else out

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
    for cid in COMPONENTS:
        add_item(c, tables.items, cid, 3 if tables.items.get(cid).get("stack") else 1)
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
    raise AssertionError(f"{sid}: no subject {kind} {name} in {[s.name for s in subs]}")


def text(lines) -> str:
    return " ".join(lines)


def in_the_wild(game):
    game.leave_local() if game.local is not None else None
    for x in range(game.world.width):
        for y in range(game.world.height):
            if game.world.settlement_at(x, y) is None and game.world.danger[x, y] >= 1 \
                    and game.tables.biomes.family(game.land_key(x, y)) in ("forest", "plains", "hills"):
                game.player.x, game.player.y = x, y
                return
    raise AssertionError("no wild land")


def in_town(game):
    town = next(s for s in game.world.settlements if s.kind in ("town", "city"))
    game.player.x, game.player.y = town.x, town.y
    game.enter_local()
    return town


def into_dungeon(game, site_index=0):
    site = game.world.sites[site_index]
    game.player.x, game.player.y = site.x, site.y
    game.enter_local()
    dungeon.descend(game, 1)
    return game.local


def place_in_dungeon(game, lm, margin=6):
    T = game.tables.terrain
    walk = T.walk[game.remap_for(lm)[lm.terrain]]
    for x in range(margin, lm.width - margin):
        for y in range(margin, lm.height - margin):
            if walk[x, y] and (x, y) not in lm.features:
                game.player.lx, game.player.ly = x, y
                return
    raise AssertionError("no floor")


def band(tables, kind, n=2, seed=4):
    rng = RNG(seed, "night")
    return PendingEncounter("test", [spawn(tables, kind, rng, i + 1) for i in range(n)], "Something comes.", False, "",
                            asleep=True)


def at_camp(game):
    in_the_wild(game)
    camp.make_camp(game)


# ---------------------------------------------------------------------------- the data
def test_the_nine_spells_are_in_and_the_start_up_check_knows_them(tables):
    assert all(sid in tables.spells for sid in E6)
    assert not [p for p in check.problems(tables) if any(sid in p for sid in E6)]
    for sid in E6:
        assert sp.out_of_battle(tables.spells[sid]), f"{sid} is never cast in a fight"
        assert sp.road_use(tables, sid) is not None, f"{sid} has a use outside a fight"
    assert sp.upcasts(tables.spells["glyph_of_warding"]) and sp.upcasts(tables.spells["magic_circle"])
    stock = {line[0] for shop in tables.economy["shops"].values() for line in shop.get("stock", ())}
    for cid in COMPONENTS:
        assert tables.items.get(cid).get("how")
        assert cid in stock, f"{cid} is sold somewhere"


# ---------------------------------------------------------------------------- Glyph of Warding
def test_an_explosive_rune_burns_the_night_band_and_wakes_the_camp(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    at_camp(game)
    dust = sum(i.qty for i in wiz.inventory if i.def_id == "glyph_diamond_dust")
    assert "choose" in magic.road_problem(game, wiz, "glyph_of_warding")
    t0 = game.world.time
    said = text(cast(game, wiz, "glyph_of_warding", subject(game, wiz, "glyph_of_warding", "rune", "fire"), 5))
    assert "glyph" in said and "7d8" in said, "5d8 and one more die a slot above 3"
    assert game.world.time - t0 >= 60, "an hour to draw"
    assert sum(i.qty for i in wiz.inventory if i.def_id == "glyph_diamond_dust") == dust - 1
    assert "already waits" in magic.road_problem(game, wiz, "glyph_of_warding",
                                                 subject(game, wiz, "glyph_of_warding", "rune", "cold"))
    enc = band(tables, "wolf")
    hp = [cr.hp for cr in enc.creatures]
    enc, notes = spellwork.night_visitors(game, enc)
    assert "fire" in text(notes)
    assert all(cr.hp < h for cr, h in zip(enc.creatures, hp)) if enc else True
    if enc is not None:
        assert enc.warned and not enc.asleep
    assert spellwork.warded(game, "glyph") is None, "a glyph once set off is spent"


def test_a_spell_glyph_strikes_the_first_of_them_as_the_fight_begins(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    at_camp(game)
    choice = subject(game, wiz, "glyph_of_warding", "spell", "Fireball")
    slots = sum(sp.slots_left(wiz, tables))
    cast(game, wiz, "glyph_of_warding", choice)
    assert sum(sp.slots_left(wiz, tables)) == slots - 2, "the glyph's slot and the stored spell's"
    assert warding.ward(game, "glyph")["spell"] == "fireball"
    enc, notes = spellwork.night_visitors(game, band(tables, "ogre"))
    assert enc is not None and enc.warned and "Fireball" in text(notes)
    game.encounter = enc
    b = fight.encounter_fight(game, ambush=False)
    foes = b.side(FOE)
    assert any(f.hp < f.max_hp for f in foes), "the stored spell burst on them"
    assert any("Fireball" in line for line, _ in b.log)
    assert spellwork.warded(game, "glyph") is None


def test_the_spells_a_glyph_can_hold(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    held = warding.glyph_spells(game, wiz)
    assert "fireball" in held
    for sid in held:
        s = tables.spells[sid]
        assert 1 <= s["level"] <= 5 and not s.get("concentration") and s["target"] in ("enemy", "point")
    assert "glyph_of_warding" not in held and "wall_of_fire" not in held


def test_a_glyph_guards_your_room_at_the_inn(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    town = in_town(game)
    cast(game, wiz, "glyph_of_warding", subject(game, wiz, "glyph_of_warding", "rune", "thunder"))
    assert game.renown.flags["glyph_room"]["settlement"] == town.id
    wiz.money = 1000
    rng = SimpleNamespace(chance=lambda p: True, randint=lambda a, b: 5)
    said = text(services._night(game, SimpleNamespace(settlement=town.id), "squalid", rng))
    assert wiz.money == 1000 and "glyph" in said and "thunder" in said
    assert "glyph_room" not in game.renown.flags, "spent"
    said = text(services._night(game, SimpleNamespace(settlement=town.id), "squalid", rng))
    assert wiz.money < 1000, "the next thief finds no glyph"


def test_a_glyph_is_left_behind_with_the_town(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_town(game)
    cast(game, wiz, "glyph_of_warding", subject(game, wiz, "glyph_of_warding", "rune", "fire"))
    in_the_wild(game)
    warding.tick(game)
    assert "glyph_room" not in game.renown.flags


def test_no_glyph_underground(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    lm = into_dungeon(game)
    place_in_dungeon(game, lm)
    assert "open" in magic.road_problem(game, wiz, "glyph_of_warding",
                                        subject(game, wiz, "glyph_of_warding", "rune", "fire"))


# ---------------------------------------------------------------------------- Symbol
@pytest.mark.parametrize("effect,state", [("pain", "incapacitated"), ("stunning", "stunned"), ("sleep", "unconscious")])
def test_a_symbol_leaves_the_band_as_it_comes_into_the_fight(world, tables, monkeypatch, effect, state):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    at_camp(game)
    cast(game, wiz, "symbol", subject(game, wiz, "symbol", "symbol", effect.capitalize()))
    monkeypatch.setattr(warding, "_save", lambda *a: False)
    enc, notes = spellwork.night_visitors(game, band(tables, "bandit"))
    assert enc is not None and "symbol" in text(notes)
    assert all(cr.conditions.get(state) for cr in enc.creatures)
    game.encounter = enc
    b = fight.encounter_fight(game, ambush=False)
    assert all(state in f.conditions for f in b.side(FOE))
    assert not any(cr.conditions for cr in enc.creatures), "brought in once"
    if effect == "sleep":
        from realmwalker.rules.engine import durations

        f = b.side(FOE)[0]
        durations.on_damage(b, f)
        assert "unconscious" not in f.conditions, "hurt, they wake"


def test_a_symbol_of_death_and_of_fear(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    at_camp(game)
    cast(game, wiz, "symbol", subject(game, wiz, "symbol", "symbol", "Death"))
    enc = band(tables, "ogre")
    hp = [cr.hp for cr in enc.creatures]
    enc2, notes = spellwork.night_visitors(game, enc)
    assert all(cr.hp < h for cr, h in zip(enc.creatures, hp)) and "necrotic" in text(notes)
    camp.make_camp(game)
    cast(game, wiz, "symbol", subject(game, wiz, "symbol", "symbol", "Fear"))
    monkeypatch.setattr(warding, "_save", lambda *a: False)
    enc, notes = spellwork.night_visitors(game, band(tables, "bandit", 3))
    assert enc is None, "they all ran"


def test_discord_makes_their_blows_go_astray(world, tables):
    wiz = hero(tables)
    cr = spawn(tables, "bandit", RNG(2), 1)
    cr.conditions["discord"] = 10
    b = Battle(tables, [wiz], [cr], Env(light=1.0), RNG(3))
    foe, me = b.side(FOE)[0], b.side(PARTY)[0]
    opt = b.attack_options(foe)[0]
    assert "in discord" in query.attack_roll(b, foe, me, opt).dis
    from realmwalker.rules import describe

    assert any("discord" in s.card.title.lower() for s in describe.statuses(foe, b))


# ---------------------------------------------------------------------------- Magic Circle, Forbiddance
def test_a_magic_circle_keeps_the_dead_out_of_the_camp(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    at_camp(game)
    cast(game, cleric, "magic_circle")
    rec = warding.ward(game, "circle")
    assert rec is not None
    enc, notes = spellwork.night_visitors(game, band(tables, "skeleton", 3))
    assert enc is None and "no further" in text(notes)
    mixed = band(tables, "zombie", 2)
    mixed.creatures.append(spawn(tables, "bandit", RNG(9), 9))
    enc, notes = spellwork.night_visitors(game, mixed)
    assert enc is not None and [cr.def_id for cr in enc.creatures] == ["bandit"]


def test_a_higher_slot_holds_the_circle_longer(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    at_camp(game)
    cast(game, cleric, "magic_circle", None, 6)
    rec = warding.ward(game, "circle")
    assert rec["until"] - game.world.time >= 4 * 60 - 1, "an hour and three more"


def test_underground_the_circle_lets_you_rest_while_only_the_dead_hunt(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    lm = into_dungeon(game)
    place_in_dungeon(game, lm)
    lm.actors.clear()
    lm.actors.append(encounters.LocalActor(99, "test", game.player.lx + 8, game.player.ly,
                                           [spawn(tables, "ghoul", RNG(3), 1)], alert=True))
    assert "can't rest" in text(fight.rest(game, "short"))
    camp.make_camp(game)
    cast(game, cleric, "magic_circle")
    assert spellwork.hidden(game, "short")
    lm.actors[0].creatures.append(spawn(tables, "bandit", RNG(4), 2))
    assert not spellwork.hidden(game, "short"), "the bandit is not kept out"


def test_forbiddance_burns_the_dead_coming_in_and_in_the_fight(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    at_camp(game)
    ruby = sum(i.qty for i in cleric.inventory if i.def_id == "ruby_dust")
    cast(game, cleric, "forbiddance", subject(game, cleric, "forbiddance", "damage", "radiant"))
    assert sum(i.qty for i in cleric.inventory if i.def_id == "ruby_dust") == ruby, "the ruby dust is kept"
    enc = band(tables, "ghoul", 2)
    enc.creatures.append(spawn(tables, "bandit", RNG(5), 5))
    hp = {id(cr): cr.hp for cr in enc.creatures}
    enc, notes = spellwork.night_visitors(game, enc)
    assert "forbidden ground" in text(notes)
    assert all(cr.hp < hp[id(cr)] for cr in enc.creatures if cr.def_id == "ghoul" and cr.hp > 0) or \
        all(not cr.alive for cr in enc.creatures if cr.def_id == "ghoul")
    assert next(cr for cr in enc.creatures if cr.def_id == "bandit").hp == hp[id(enc.creatures[-1])]
    game.encounter = enc
    b = fight.encounter_fight(game, ambush=False)
    for f in [f for f in b.side(FOE) if f.state == "fighting"]:
        burns = [bf for bf in f.buffs if bf.get("source") == "forbiddance"]
        assert bool(burns) == (f.kind == "undead"), f.name
        if burns:
            assert burns[0]["dot_type"] == "radiant" and burns[0]["dot_at"] == "end"


def test_a_companion_casts_forbiddance_as_a_ritual_before_the_night(world, tables, monkeypatch):
    leader = hero(tables, "fighter")
    cleric = hero(tables, "cleric", seed=2)
    cleric.companion = {"loyalty": 50, "wage": 0}
    game = game_with(world, tables, leader, cleric)
    in_the_wild(game)
    slots = sum(sp.slots_left(cleric, tables))
    said = text(spellwork.before_rest(game))
    assert "ruby dust" in said and warding.ward(game, "forbiddance")["type"] == "radiant"
    assert sum(sp.slots_left(cleric, tables)) == slots, "a ritual spends no slot"


# ---------------------------------------------------------------------------- Guards and Wards, Private Sanctum
def test_guards_and_wards_lose_them_in_the_fog(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    at_camp(game)
    cast(game, wiz, "guards_and_wards")
    assert "not in the middle of a town" not in (magic.road_problem(game, wiz, "guards_and_wards") or "")
    real = RNG.chance
    monkeypatch.setattr(RNG, "chance", lambda self, p: True if p == warding.GUARDS_LOST else real(self, p))
    enc, notes = spellwork.night_visitors(game, band(tables, "wolf"))
    assert enc is None and "fog" in text(notes)
    monkeypatch.setattr(RNG, "chance", lambda self, p: False if p == warding.GUARDS_LOST else real(self, p))
    enc, notes = spellwork.night_visitors(game, band(tables, "wolf"))
    assert enc is not None and enc.warned and not enc.asleep and "mouth" in text(notes)


def test_guards_and_wards_let_you_rest_underground(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    lm = into_dungeon(game)
    place_in_dungeon(game, lm)
    for a in lm.actors:
        a.alert = True
    camp.make_camp(game)
    cast(game, wiz, "guards_and_wards")
    assert spellwork.hidden(game, "long")
    assert "can't rest" not in text(fight.rest(game, "short"))


def test_a_town_is_no_place_for_the_camp_wards(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_town(game)
    for sid in ("guards_and_wards", "mordenkainens_private_sanctum", "magic_circle"):
        assert "town" in magic.road_problem(game, wiz, sid)


def test_a_private_sanctum_hides_the_camp_and_its_fire(world, tables, monkeypatch):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    at_camp(game)
    game.camp.fire = True
    asked = []
    monkeypatch.setattr(encounters, "roll_encounter", lambda game, minutes: asked.append(minutes))
    fight.rest(game, "long")
    camp.make_camp(game)
    game.camp.fire = True
    cast(game, wiz, "mordenkainens_private_sanctum")
    assert warding.unseen_camp(game)
    n = len(asked)
    fight.rest(game, "long")
    assert asked[0] == pytest.approx(60 * 0.4) and asked[n] == pytest.approx(60 * 0.25 * warding.SANCTUM_CHANCE)
    assert "dark fog" in warding.guards_the_animals(game)


# ---------------------------------------------------------------------------- Hallow
def _scar_here(game):
    p = game.player
    scar = {"x": p.x, "y": p.y, "name": "the Field of Crows", "kind": "battle", "year": 100, "dead": 900}
    game.world.politics.setdefault("scars", []).append(scar)
    return scar


def test_hallow_lays_a_haunted_field_to_rest_for_good(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    in_the_wild(game)
    scar = _scar_here(game)
    t0 = game.world.time
    said = text(cast(game, cleric, "hallow", subject(game, cleric, "hallow", "blessing", "Peaceful Rest")))
    assert game.world.time - t0 >= 24 * 60, "a day of prayer"
    assert scar["laid"] and "Field of Crows" in said
    assert past.restless(game, SimpleNamespace(chance=lambda p: True)) is None
    assert warding.hallowed_at(game) is not None
    assert "hallowed already" in magic.road_problem(game, cleric, "hallow",
                                                    subject(game, cleric, "hallow", "blessing", "Courage"))
    sensed = text(divining._sense_evil(game, cleric, tables.spells["detect_evil_and_good"]))
    assert "hallowed" in sensed and "haunted" not in sensed


def test_hallowed_ground_turns_the_dead_away_and_its_blessing_holds_in_a_fight(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    in_the_wild(game)
    cast(game, cleric, "hallow", subject(game, cleric, "hallow", "blessing", "Courage"))
    camp.make_camp(game)
    enc, notes = spellwork.night_visitors(game, band(tables, "zombie"))
    assert enc is None and "hallowed ground" in text(notes)
    game.encounter = band(tables, "bandit")
    b = fight.encounter_fight(game, ambush=False)
    me = b.side(PARTY)[0]
    assert query.condition_immune(me, "frightened")


def test_hallowed_with_fear_frightens_the_beasts(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    in_the_wild(game)
    cast(game, cleric, "hallow", subject(game, cleric, "hallow", "blessing", "Fear"))
    game.encounter = band(tables, "wolf")
    b = fight.encounter_fight(game, ambush=False)
    assert all("frightened" in f.conditions for f in b.side(FOE))


def test_hallowed_with_vulnerability_and_resistance(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    lm = into_dungeon(game)
    place_in_dungeon(game, lm)
    cast(game, cleric, "hallow", subject(game, cleric, "hallow", "blessing", "Vulnerability"))
    assert warding.hallowed_at(game)["local"] == game.player.local_key
    game.encounter = band(tables, "skeleton")
    b = fight.encounter_fight(game, ambush=False)
    f = b.side(FOE)[0]
    assert query.defences(f, "radiant") == "vulnerable"
    game.player.lx = min(lm.width - 1, game.player.lx + warding.HALLOW_SQUARES + 1)
    assert warding.hallowed_at(game) is None, "60 feet of it underground"


def test_hallowing_a_towns_graves_is_remembered(world, tables):
    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    town = in_town(game)
    said = text(cast(game, cleric, "hallow", subject(game, cleric, "hallow", "blessing", "Peaceful Rest")))
    assert town.name in said


# ---------------------------------------------------------------------------- Demiplane, the cauldron
def test_the_demiplane_keeps_things_for_good_and_gives_them_back(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    wiz.money = 7000
    add_item(wiz, tables.items, "gem_1000", 2)
    add_item(wiz, tables.items, "battleaxe")
    weight = game.sheet(wiz).carried_weight()
    cast(game, wiz, "demiplane", subject(game, wiz, "demiplane", "load", "all of it"))
    kept = {d["def_id"] for d in warding.demiplane_things(game)}
    assert {"gem_1000", "battleaxe"} <= kept and wiz.money == 0
    assert game.sheet(wiz).carried_weight() < weight
    assert spellwork.hidden(game, "short") and not spellwork.hidden(game, "long"), "an hour's room to rest in"
    game.pass_time(24 * 60 * 90, "rest")
    assert warding.demiplane_things(game), "never lost"
    cast(game, wiz, "demiplane", subject(game, wiz, "demiplane", "load", "take back"))
    assert wiz.money == 7000 and any(i.def_id == "battleaxe" for i in wiz.inventory)
    assert not warding.demiplane_things(game)


def test_tashas_cauldron_brews_potions_that_vanish_when_brewed_again(world, tables):
    wiz = hero(tables)
    game = game_with(world, tables, wiz)
    in_the_wild(game)
    choices = [s.ref for s in warding.subjects(game, wiz, "tashas_bubbling_cauldron")]
    assert choices == ["potion_healing", "potion_healing_greater"], "common and uncommon only"
    mod = game.sheet(wiz).mod("int")
    cast(game, wiz, "tashas_bubbling_cauldron", subject(game, wiz, "tashas_bubbling_cauldron", "potion", "greater"))
    brewed = [i for i in wiz.inventory if warding.brewed(i)]
    assert sum(i.qty for i in brewed) == max(1, mod)
    cast(game, wiz, "tashas_bubbling_cauldron", subject(game, wiz, "tashas_bubbling_cauldron", "potion"))
    brewed = [i for i in wiz.inventory if warding.brewed(i)]
    assert {i.def_id for i in brewed} == {"potion_healing"} and sum(i.qty for i in brewed) == max(1, mod)
    town = in_town(game)
    cat = tables.items.get("potion_healing")["category"]
    buyers = [n for n in game.world.npcs.values() if n.settlement == town.id and economy.shop_spec(game, n)
              and cat in economy.shop_spec(game, n)["buys"]]
    assert buyers, "someone in town deals in such things"
    for npc in buyers:
        price, why = economy.sell_price(game, npc, brewed[0])
        assert price is None and "magic" in why


def test_the_spells_page_shows_what_stands(world, tables):
    from realmwalker.ui.screens.spells import working_now

    cleric = hero(tables, "cleric")
    game = game_with(world, tables, cleric)
    at_camp(game)
    cast(game, cleric, "glyph_of_warding", subject(game, cleric, "glyph_of_warding", "rune", "cold"))
    cast(game, cleric, "magic_circle")
    cast(game, cleric, "hallow", subject(game, cleric, "hallow", "blessing", "Resistance"))
    camp.make_camp(game)
    cast(game, cleric, "magic_circle")
    said = text(working_now(game))
    assert "Glyph of Warding" in said and "waiting" in said and "Magic Circle" in said and "Hallowed ground" in said
