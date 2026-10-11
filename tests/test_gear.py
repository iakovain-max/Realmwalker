"""What the party's gear is for (after 1.0, Anton: "make the items do something"): packs carry more, foci sharpen
spells, rings and papers impress, blades wear and are honed, tools mend, snares catch, music cheers, prayer steadies,
prisoners slip their bonds, crowbars force, soap washes, flasks are thrown, scrolls are written."""

import copy

import pytest

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.game import camp, companions, dungeon, economy, events, fight, gear, magic, pack, people, save, survival
from realmwalker.game.state import new_game
from realmwalker.rules import spells as spellrules
from realmwalker.rules.character import Sheet
from realmwalker.rules.combat import PARTY, Battle, Env, open_field
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.inventory import add_item, carried, equip, unequip
from realmwalker.rules.wounds import make_wound
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Toolshed", 33, "small"), tables)


def person(tables, cls="fighter", bg="soldier", seed=1, kit=0):
    b = CharacterBuilder(tables, RNG(seed, "gear"))
    b.set_race("human")
    b.set_class(cls)
    b.set_kit(kit)
    b.set_background(bg)
    return b.build()


def companion(tables, cls="fighter", seed=5):
    c = person(tables, cls, seed=seed)
    c.is_player = False
    c.money = 0
    c.companion = {"npc": -1, "archetype": "sellsword", "values": [], "want": "pay", "loyalty": 50.0, "wage": 100,
                   "share": 0.0, "hired": 0, "order": "follow", "home": 0, "unpaid": 0}
    return c


@pytest.fixture
def game(world, tables):
    g = new_game(copy.deepcopy(world), tables, person(tables))
    g.survival = False
    return g


def wild(game):
    """Stand somewhere in the open woods, away from any town."""
    w = game.world
    idx = w.biome_ids.index("forest")
    for x in range(w.width):
        for y in range(w.height):
            if w.biome[x, y] == idx and w.settlement_at(x, y) is None and not w.road[x, y]:
                game.player.x, game.player.y = x, y
                return
    pytest.skip("no forest")


def always(monkeypatch, natural=20):
    class Roll:
        def __init__(self):
            self.natural = natural
            self.total = natural

    monkeypatch.setattr(dice, "d20", lambda *a, **k: Roll())


def drop_all(c, def_id):
    for it in [i for i in c.inventory if i.def_id == def_id]:
        unequip(c, c.slot_of(it.uid)) if c.slot_of(it.uid) else None
        c.inventory.remove(it)


# ---------------------------------------------------------------------------- packs
def test_a_backpack_on_the_back_carries_more(tables):
    c = person(tables)
    pack_ = c.equipped_item("back")
    assert pack_ is not None and pack_.def_id == "backpack", "everyone starts with their pack on"
    s = Sheet(c, tables)
    worn = s.capacity()
    unequip(c, "back")
    bare = Sheet(c, tables).capacity()
    assert [round(a - b) for a, b in zip(worn, bare)] == [15, 15, 15]
    sack = add_item(c, tables.items, "sack")
    equip(c, tables.items, sack.uid)
    assert c.slot_of(sack.uid) == "back"
    assert round(Sheet(c, tables).capacity()[0] - bare[0]) == 5


def test_every_companion_wears_their_own_pack_and_the_party_carries_more(game, tables):
    before = Sheet(game.leader, tables).pack_capacity()[0]
    mira = companion(tables)
    game.party.append(mira)
    pack.sync(game)
    assert mira.equipped_item("back") is not None
    assert Sheet(game.leader, tables).pack_capacity()[0] == pytest.approx(before + Sheet(mira, tables).capacity()[0])


# ---------------------------------------------------------------------------- foci and things worn
def test_a_priest_with_a_holy_symbol_casts_better(tables):
    c = person(tables, "cleric", "acolyte")
    s = Sheet(c, tables)
    sym = c.equipped_item("neck")
    assert sym is not None and sym.def_id == "holy_symbol", "a priest wears the symbol at the neck"
    with_it = (spellrules.attack_bonus(s, tables), spellrules.save_dc(s, tables))
    unequip(c, "neck")
    without = (spellrules.attack_bonus(s, tables), spellrules.save_dc(s, tables))
    assert with_it == (without[0] + 1, without[1] + 1)
    equip(c, tables.items, sym.uid, "off_hand")  # held works as well as worn
    assert spellrules.save_dc(s, tables) == with_it[1]


def test_a_wizard_holds_a_crystal_or_carries_a_pouch(tables):
    hedge = person(tables, "wizard", kit=1)  # the hedge mage's kit has a crystal focus
    crystal = hedge.equipped_item("off_hand")
    assert crystal is not None and crystal.def_id == "arcane_focus"
    s = Sheet(hedge, tables)
    held = spellrules.attack_bonus(s, tables)
    unequip(hedge, "off_hand")
    assert spellrules.attack_bonus(s, tables) == held - 1, "a crystal in the pack does nothing"
    scholar = person(tables, "wizard", kit=0)  # the scholar's kit has a component pouch
    assert any(it.def_id == "component_pouch" for it in scholar.inventory)
    s2 = Sheet(scholar, tables)
    carried_ = spellrules.save_dc(s2, tables)
    drop_all(scholar, "component_pouch")
    assert spellrules.save_dc(s2, tables) == carried_ - 1
    fighter = person(tables)
    add_item(fighter, tables.items, "component_pouch")
    assert spellrules.focus_bonus(fighter, tables) == 0, "no magic to focus"


def test_a_trophy_at_the_neck_is_frightening(tables):
    c = person(tables, bg="outlander")
    assert c.equipped_item("neck") is not None and c.equipped_item("neck").def_id == "trophy"
    s = Sheet(c, tables)
    worn = s.skill_bonus("intimidation")
    unequip(c, "neck")
    assert s.skill_bonus("intimidation") == worn - 1


def test_rings_and_papers_impress_the_people_they_speak_to(game, tables):
    from types import SimpleNamespace

    c = game.leader
    drop_all(c, "rank_insignia")  # an old soldier's: it would speak to the lord's men-at-arms
    lord = SimpleNamespace(social="high", job="lord")
    base = people.papers_impression(game, lord)
    assert base == 0
    ring = add_item(c, tables.items, "signet_ring")
    assert people.papers_impression(game, lord) == base, "a ring in the pack is not a ring on the hand"
    social = Sheet(c, tables).social()
    equip(c, tables.items, ring.uid)
    assert people.papers_impression(game, lord) == base + 5
    assert Sheet(c, tables).social() == min(3, social + 1)
    add_item(c, tables.items, "pedigree_scroll")
    assert people.papers_impression(game, lord) == base + 5, "the best of a kind counts, not all of them"
    unequip(c, "ring")
    assert people.papers_impression(game, lord) == base + 4
    guard = SimpleNamespace(social="low", job="guard")
    plain = people.papers_impression(game, guard)
    add_item(c, tables.items, "rank_insignia")
    assert people.papers_impression(game, guard) == plain + 6


# ---------------------------------------------------------------------------- wear and mending
def fight_with(tables, hero, *foes_, seed=3):
    rng = RNG(seed, "foes")
    enemies = [spawn(tables, d, rng, i + 1) for i, d in enumerate(foes_)]
    b = Battle(tables, [hero], enemies, Env(), RNG(seed, "battle"), field=open_field(tables))
    b.start("A test fight.")
    return b


def test_blows_wear_blades_and_armour(game, tables, monkeypatch):
    c = game.leader
    monkeypatch.setitem(tables.items.upkeep, "wear", {"weapon": 1.0, "armor": 1.0, "shield": 1.0, "helmet": 1.0})
    b = fight_with(tables, c, "wolf")
    me, wolf = b.side(PARTY)[0], [f for f in b.fighters if f.side != PARTY][0]
    b.events += [{"kind": "attack", "by": me.id, "to": wolf.id, "hit": True, "melee": True}] * 3
    b.events += [{"kind": "attack", "by": wolf.id, "to": me.id, "hit": True, "melee": True}] * 2
    weapon, armour = c.equipped_item("main_hand"), c.equipped_item("armor")
    w0, a0 = weapon.condition, armour.condition
    c.effects["honed"] = 10.0
    gear.wear_from_battle(game, b)
    assert weapon.condition <= w0 - 3 and armour.condition <= a0 - 2
    assert "honed" not in c.effects, "the edge is gone with the fight"


def test_a_battered_weapon_hits_worse_and_a_honed_one_cuts_deeper(tables):
    c = person(tables)
    sword = c.equipped_item("main_hand")
    assert tables.items.get(sword.def_id)["damage_type"] in ("slashing", "piercing")
    b = fight_with(tables, c, "wolf")
    me = b.side(PARTY)[0]
    opt = b._weapon_option(me, me.sheet, sword, "main")
    sword.condition = 10
    worse = b._weapon_option(me, me.sheet, sword, "main")
    assert worse.bonus == opt.bonus - 1
    sword.condition = 100
    c.effects["honed"] = 5.0
    sharper = b._weapon_option(me, me.sheet, sword, "main")
    n, s, flat = dice.parse(opt.damage)
    n2, s2, flat2 = dice.parse(sharper.damage)
    assert (n2, s2, flat2) == (n, s, flat + 1)


def test_a_whetstone_hones_every_blade(game, tables):
    c = game.leader
    drop_all(c, "whetstone")
    assert gear.hone(game) == ["You have no whetstone."]
    add_item(c, tables.items, "whetstone")
    spare = add_item(c, tables.items, "dagger", condition=20)
    lines = gear.hone(game)
    assert c.effects.get("honed", 0) > 0
    assert spare.condition == tables.items.upkeep["hone"]["restore"]
    assert "+1 damage" in lines[0]


def test_tools_mend_what_they_are_made_for(game, tables):
    c = game.leader
    for tool in ("smiths_tools", "carpenters_tools", "leatherworkers_tools", "needle_thread"):
        drop_all(c, tool)
    mail = c.equipped_item("armor")
    mail.condition = 20
    assert "nothing to mend" in gear.mend(game)[0]
    add_item(c, tables.items, "carpenters_tools")
    assert all(p[0] is not mail for p in gear.mend_plan(game)), "a saw does not mend steel"
    add_item(c, tables.items, "smiths_tools")
    c.tools = [t for t in c.tools if t != "smiths_tools"]
    gear.mend(game)
    assert mail.condition == 20 + tables.items.upkeep["mend"]["step"]
    mail.condition = 70
    gear.mend(game)
    assert mail.condition == tables.items.upkeep["mend"]["cap"], "untrained hands only get it so far"
    c.tools.append("smiths_tools")
    gear.mend(game)
    assert mail.condition == 100


# ---------------------------------------------------------------------------- at camp
def test_snares_set_at_night_may_hold_something_in_the_morning(game, tables, monkeypatch):
    wild(game)
    c = game.leader
    assert gear.snare_problem(game) == "you have no snares or trap"
    add_item(c, tables.items, "snares")
    assert gear.snare_problem(game) is None
    lines = gear.set_snares(game)
    assert "set" in lines[0] and camp.camp_here(game).snares == "snares"
    always(monkeypatch, 20)
    meat = sum(it.qty for it in c.inventory if it.def_id == "raw_meat")
    out = gear.check_snares(game)
    assert sum(it.qty for it in c.inventory if it.def_id == "raw_meat") > meat, out
    assert not any(it.def_id == "hides" for it in c.inventory), "snares take only small game"
    assert camp.camp_here(game).snares == ""


def test_an_evening_of_music_cheers_the_companions(game, tables, monkeypatch):
    wild(game)
    assert gear.evening_problem(game) == "there is nobody to play for"
    mira = companion(tables)
    game.party.append(mira)
    pack.sync(game)
    for thing in ("dice_set", "playing_cards", "lute", "flute"):
        drop_all(game.leader, thing)
    assert gear.evening_problem(game) == "you have no instrument, cards or dice"
    add_item(game.leader, tables.items, "lute")
    always(monkeypatch, 20)
    before = mira.companion["loyalty"]
    gear.evening(game)
    assert mira.companion["loyalty"] == before + tables.items.upkeep["evening"]["music"]
    assert gear.evening_problem(game) == "you have already passed this evening"
    mira.companion["loyalty"] = 69.0
    game.leader.uses.pop("evening_day")
    gear.evening(game)
    assert mira.companion["loyalty"] == tables.items.upkeep["evening"]["cap"], "content, but not devoted for a song"


def test_prayer_steadies_and_gives_a_priest_a_spell_back(world, tables):
    g = new_game(copy.deepcopy(world), tables, person(tables, "cleric", "acolyte"))
    g.survival = False
    c = g.leader
    assert any(it.def_id == "prayer_book" for it in c.inventory)
    spellrules.spend_slot(c, 1)
    spellrules.spend_slot(c, 1)
    left = spellrules.slots_left(c, tables)[0]
    mira = companion(tables)
    g.party.append(mira)
    pack.sync(g)
    incense = sum(it.qty for it in carried(g.party) if it.def_id == "incense")
    lines = gear.pray(g, c)
    assert spellrules.slots_left(c, tables)[0] == left + 1, lines
    assert c.effects.get("steadied", 0) > 0 and mira.effects.get("steadied", 0) > 0, "the incense reached everyone"
    assert sum(it.qty for it in carried(g.party) if it.def_id == "incense") == incense - 1
    assert Sheet(c, tables).save_bonus("wis") == Sheet(c, tables).mod("wis") + Sheet(c, tables).proficiency + 1
    assert gear.pray_problem(g, c) is not None, "once a day"


def test_bells_round_the_camp_mean_nobody_is_caught_asleep(game, tables, monkeypatch):
    wild(game)
    from realmwalker.game import encounters

    monkeypatch.setattr(encounters, "encounter_chance", lambda *a, **k: 1.0)
    add_item(game.leader, tables.items, "bell_line")
    notes = fight.rest(game, "long")
    assert game.encounter is not None and not game.encounter.asleep
    assert any("bells" in n for n in notes)


def test_a_shovel_digs_a_shelter_in_half_the_time(game, tables, monkeypatch):
    wild(game)
    always(monkeypatch, 15)
    drop_all(game.leader, "shovel")
    t0 = game.world.time
    camp.build_shelter(game)
    plain = game.world.time - t0
    game.camp = None
    add_item(game.leader, tables.items, "shovel")
    t0 = game.world.time
    camp.build_shelter(game)
    assert game.world.time - t0 == plain // 2


def test_a_cook_makes_the_food_go_further(game, tables):
    wild(game)
    c = game.leader
    camp.make_camp(game).fire = True
    assert camp.cooking(game) == (1.0, None)
    add_item(c, tables.items, "cooks_utensils")
    assert camp.cooking(game)[0] == pytest.approx(1.15)
    c.tools.append("cooks_utensils")
    assert camp.cooking(game) == (pytest.approx(1.3), c)


def test_soap_washes_off_everything_and_cleans_wounds(game, tables, monkeypatch):
    c = game.leader
    monkeypatch.setattr(survival, "water_here", lambda g: ("river", "the river"))
    c.dirt = 90.0
    w = make_wound("left_arm", "slashing", 1, RNG(1, "w"), now=game.world.time)
    c.wounds.append(w)
    drop_all(c, "soap")
    survival.wash(game)
    assert c.dirt == pytest.approx(20.0) and not w.cleaned
    c.dirt = 90.0
    add_item(c, tables.items, "soap", 2)
    lines = survival.wash(game)
    assert c.dirt == 0.0 and w.cleaned, lines
    assert sum(it.qty for it in c.inventory if it.def_id == "soap") == 1


# ---------------------------------------------------------------------------- prisoners
def test_prisoners_in_manacles_never_slip_away(game, tables, monkeypatch):
    game.renown.flags["captives"] = [{"def_id": "bandit", "name": "the bandit", "reward": 100, "since": 0,
                                      "faction": -1} for _ in range(2)]
    drop_all(game.leader, "rope")
    drop_all(game.leader, "manacles")
    assert gear.binding(game, 2) == ["none", "none"]
    add_item(game.leader, tables.items, "manacles")
    add_item(game.leader, tables.items, "rope")
    assert gear.binding(game, 2) == ["manacles", "rope"]
    monkeypatch.setitem(tables.items.upkeep, "escape", {"none": 1.0, "rope": 1.0, "manacles": 0.0})
    gear.captives_slip(game)
    assert len(game.renown.flags["captives"]) == 1, "the one in rope got away, the one in irons did not"


# ---------------------------------------------------------------------------- locks
def test_a_crowbar_forces_a_lock_with_advantage_and_less_noise(game, tables, monkeypatch):
    from realmwalker.game.encounters import LocalActor

    class LM:
        actors = [LocalActor(1, "rats", 9, 0, []), LocalActor(2, "rats", 20, 0, [])]

    drop_all(game.leader, "thieves_tools")
    drop_all(game.leader, "crowbar")
    seen = []
    real = dice.d20
    monkeypatch.setattr(dice, "d20", lambda rng, **k: seen.append(k.get("advantage")) or real(rng, **k))
    dungeon.unlock(game, LM, 0, 0, 13)
    assert seen[-1] is False and LM.actors[0].alert
    LM.actors = [LocalActor(1, "rats", 9, 0, [])]
    add_item(game.leader, tables.items, "crowbar")
    dungeon.unlock(game, LM, 0, 0, 13)
    assert seen[-1] is True and not LM.actors[0].alert, "a crack, not a crash: heard only close by"


# ---------------------------------------------------------------------------- thrown flasks
def test_a_flask_of_oil_is_thrown_and_burns(tables):
    c = person(tables)
    add_item(c, tables.items, "oil_flask", 2)
    b = fight_with(tables, c, "wolf")
    me = b.side(PARTY)[0]
    wolf = [f for f in b.fighters if f.side != PARTY][0]
    flask = next(it for it in c.inventory if it.def_id == "oil_flask")
    assert flask in b.usable_items(me)
    value = b.throw_value(flask)
    assert value and value.startswith("throw:")
    b.order = [me.id] + [x for x in b.order if x != me.id]
    b.turn = 0
    b.turn_started = True
    b._start_of_turn(me)
    wolf.x, wolf.y = me.x + 2, me.y
    hp = wolf.hp
    assert b.do_cast(me, value, None, point=(wolf.x, wolf.y))
    assert flask.qty == 1
    assert wolf.hp < hp or not wolf.active
    assert any(z.kind == "fire" for z in b.zones)
    assert me.action <= 0


def test_holy_water_burns_only_the_dead(tables):
    c = person(tables)
    add_item(c, tables.items, "holy_water", 2)
    flask = next(it for it in c.inventory if it.def_id == "holy_water")
    for foe, hurt in (("wolf", False), ("zombie", True)):
        b = fight_with(tables, c, foe)
        me = b.side(PARTY)[0]
        them = [f for f in b.fighters if f.side != PARTY][0]
        b.order = [me.id] + [x for x in b.order if x != me.id]
        b.turn, b.turn_started = 0, True
        b._start_of_turn(me)
        them.x, them.y = me.x + 2, me.y
        hp = them.hp
        assert b.do_cast(me, b.throw_value(flask), None, point=(them.x, them.y))
        assert (them.hp < hp) == hurt, foe


def test_nothing_that_is_not_for_a_fight_shows_in_the_fight(tables):
    c = person(tables)
    for item in ("prayer_book", "old_map", "whetstone", "poppy_milk", "healing_herbs", "lute"):
        add_item(c, tables.items, item)
    b = fight_with(tables, c, "wolf")
    names = {it.def_id for it in b.usable_items(b.side(PARTY)[0])}
    assert names <= {"bandages", "potion_healing", "healers_kit", "oil_flask", "holy_water", "alchemists_fire"}, names


# ---------------------------------------------------------------------------- writing scrolls
def test_a_wizard_writes_a_spell_out_as_a_scroll(world, tables, monkeypatch):
    g = new_game(copy.deepcopy(world), tables, person(tables, "wizard", kit=0))
    g.survival = False
    c = g.leader
    c.money = 10000
    assert any(it.def_id == "ink_and_quill" for it in c.inventory)
    sid = "magic_missile"
    assert magic.scribe_problem(g, c, "fire_bolt") is not None, "a cantrip cannot be written out"
    assert magic.scribe_problem(g, c, sid) is None
    always(monkeypatch, 20)
    sheets = sum(it.qty for it in c.inventory if it.def_id == "parchment")
    left = spellrules.slots_left(c, tables)[0]
    lines = magic.scribe(g, c, sid)
    assert any(it.def_id == f"scroll_{sid}" for it in c.inventory), lines
    assert spellrules.slots_left(c, tables)[0] == left - 1
    assert sum(it.qty for it in c.inventory if it.def_id == "parchment") == sheets - 1
    assert c.money == 10000 - magic.scribe_cost(1)
    drop_all(c, "parchment")
    assert magic.scribe_problem(g, c, sid) == "you need a sheet of parchment"


# ---------------------------------------------------------------------------- on the road
def test_navigators_tools_help_keep_your_bearings(game, tables):
    drop_all(game.leader, "navigators_tools")
    assert game.bearings_bonus() == 0
    add_item(game.leader, tables.items, "navigators_tools")
    assert game.bearings_bonus() == 4
    game.leader.tools.append("navigators_tools")
    assert game.bearings_bonus() == 4 + game.sheet().proficiency


def test_a_spyglass_sees_further_by_day(game, tables, monkeypatch):
    w = game.world
    idx = w.biome_ids.index("plains")
    spot = next(((x, y) for x in range(w.width) for y in range(w.height) if w.biome[x, y] == idx), None)
    if spot is None:
        pytest.skip("no plains")
    game.player.x, game.player.y = spot
    from types import SimpleNamespace

    monkeypatch.setattr(type(game), "light", property(lambda self: 1.0))
    monkeypatch.setattr(type(game), "weather", property(lambda self: SimpleNamespace(visibility=1.0)))
    game.player.explored[:] = False
    game.reveal()
    plain = int(game.player.explored.sum())
    add_item(game.leader, tables.items, "spyglass")
    game.player.explored[:] = False
    game.reveal()
    assert int(game.player.explored.sum()) > plain


def test_tools_open_new_ways_on_the_road(game, tables):
    spec = tables.travel_events["fallen_climber"]
    rope = next(i for i, o in enumerate(spec["options"]) if "rope" in o["label"])
    drop_all(game.leader, "rope")
    ok, why = events.option_state(game, spec["options"][rope])
    assert not ok and "rope" in why
    add_item(game.leader, tables.items, "rope")
    assert events.option_state(game, spec["options"][rope])[0]
    gate = tables.travel_events["shut_gate"]
    hook = next(o for o in gate["options"] if "grappling" in o["label"])
    assert {i for i, _ in hook["requires"]["items"]} == {"grappling_hook", "rope"}


# ---------------------------------------------------------------------------- shops and the pack
def test_the_new_things_can_be_bought_and_rings_sold(tables):
    shops = tables.economy["shops"]
    stocked = {item for shop in shops.values() for item, *_ in shop["stock"]}
    for item in ("snares", "bell_line", "navigators_tools", "spyglass", "leatherworkers_tools", "holy_water",
                 "alchemists_fire", "manacles", "grappling_hook", "smiths_tools", "prayer_book", "incense",
                 "holy_symbol", "ink_and_quill", "parchment", "dice_set", "playing_cards", "lute", "cooks_utensils"):
        assert item in stocked, f"{item} is sold nowhere"
    assert "jewellery" in shops["general"]["buys"]
    assert tables.people["occupations"]["acolyte"].get("trade") == "temple"


def test_every_thing_in_the_pack_says_what_it_is_for(game, tables):
    """No gear, tool, focus or book is a dead weight: each is worn, used, read, lights, holds water, binds, sleeps,
    mends, impresses or says where it is used."""
    idle = []
    for iid, d in tables.items.defs.items():
        if d["category"] not in ("gear", "tool", "focus", "book") or iid.startswith("scroll_"):
            continue
        it = add_item(game.leader, tables.items, iid)
        if not (tables.items.slots_for(it) or d.get("use") or d.get("light") or d.get("container")
                or d.get("bedding") or d.get("how") or d.get("mends") or d.get("impress") or d.get("tool")):
            idle.append(iid)
    allowed = {"sealed_letter"}  # a piece of work's letter: the pack has its own words for it
    assert set(idle) <= allowed, sorted(set(idle) - allowed)
    for iid in ("whetstone", "smiths_tools", "snares", "lute", "playing_cards", "prayer_book", "ink_and_quill",
                "oil_flask"):
        it = next(i for i in game.leader.inventory if i.def_id == iid)
        assert gear.use_name(game, it), iid
