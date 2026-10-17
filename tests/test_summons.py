"""Summoned spirits (Expansion 3 F.2): Summon Beast, Fey, Undead, Aberration, Construct, Elemental and Giant Insect
in real fights - their numbers for the slot, placed at the point, their turn right after their caster's, gone when the
concentration ends or at 0 hit points, the form chosen for the fight, every trait and blow that does more, the fey
spirit's moods and the centipede's spew, the Auto casting one, an enemy's spirit on the enemy's side, and the costly
components."""

import pytest

from realmwalker.rules import allies
from realmwalker.rules import spells as spellrules
from realmwalker.rules.combat import FOE, PARTY
from realmwalker.rules import tactics
from realmwalker.rules.engine import actions, estimates
from tests.test_allies import fight, hero
from tests.test_wave4 import my_turn

SPELLS = ("summon_beast", "summon_fey", "summon_undead", "summon_aberration", "summon_construct", "summon_elemental",
          "giant_insect")


@pytest.fixture(scope="module")
def tables(data):
    from realmwalker.world.tables import Tables

    return Tables(data)


def summon(b, f, sid, point=(6, 4), up=0, form=""):
    sp = b.t.spells[sid]
    if form:
        cid = sp["effects"][0]["creature"]
        old = allies.best_form
        allies.best_form = lambda b_, o_, c_: form if c_ == cid else old(b_, o_, c_)
        try:
            b.cast(f, sid, sp, None, point, up=up, mod=4, dc=15, bonus=7, mult=1, level=sp["level"] + up)
        finally:
            allies.best_form = old
    else:
        b.cast(f, sid, sp, None, point, up=up, mod=4, dc=15, bonus=7, mult=1, level=sp["level"] + up)
    return next(x for x in reversed(b.fighters) if x.bond is not None and x.bond["kind"] == "summon")


def scene(tables, foes=("bandit",), seed=1, xp=200000):
    me = hero(tables, xp=xp)
    spots = {0: (2, 4)}
    for i in range(len(foes)):
        spots[i + 1] = (9, 3 + i)
    b = fight(tables, [me], list(foes), spots, seed=seed)
    return b, b.fighters[0]


# The book's numbers at the spell's own level and at a higher slot (PHB 2024, checked on the page images).
NUMBERS = {  # spell: (form, AC at its level, HP at its level, HP a level more, first attack's damage at its level)
    "summon_beast": ("land", 13, 30, 5, "1d8+6"),
    "summon_fey": ("fuming", 15, 30, 10, "2d6+6"),
    "summon_undead": ("putrid", 14, 30, 10, "1d6+6"),
    "summon_aberration": ("slaad", 15, 40, 10, "1d10+7"),
    "summon_construct": ("metal", 17, 40, 15, "1d8+8"),
    "summon_elemental": ("fire", 15, 50, 10, "1d10+8"),
    "giant_insect": ("centipede", 15, 70, 10, "1d6+7"),
}


@pytest.mark.parametrize("sid", SPELLS)
def test_each_spirit_has_its_numbers_for_the_slot_and_goes_with_the_concentration(tables, sid):
    form, ac, hp, hp_up, dmg = NUMBERS[sid]
    b, me = scene(tables)
    my_turn(b, me)
    s = summon(b, me, sid, form=form)
    assert s.bond["form"] == form and s.side == PARTY and s.bond["conc"]
    assert s.cdef["ac"] == ac and s.hp == hp == s.max_hp
    atk = s.cdef["attacks"][0]
    assert atk["damage"] == dmg and atk["bonus"] == allies.caster_numbers(me.char, b.t)[0], "the caster's spell attack"
    assert "multiattack" not in s.cdef or b.t.spells[sid]["level"] >= 4
    assert max(abs(s.x - 6), abs(s.y - 4)) <= 1, "it appears at the point"
    assert b.order[b.order.index(me.id) + 1] == s.id, "its turn comes right after its caster's"
    assert me.concentration["spell"] == sid
    b._end_concentration(me, quiet=False, why="is let go")
    assert s.state == "dead" and not s.active
    # A higher slot: more hit points, harder to hit, and more blows.
    b2, me2 = scene(tables, seed=2)
    my_turn(b2, me2)
    s2 = summon(b2, me2, sid, up=2, form=form)
    assert s2.cdef["ac"] == ac + 2 and s2.hp == hp + 2 * hp_up
    assert s2.cdef["multiattack"] == (b2.t.spells[sid]["level"] + 2) // 2


def test_a_spirit_at_zero_hit_points_is_gone_and_a_new_casting_replaces_the_old(tables):
    b, me = scene(tables)
    my_turn(b, me)
    s = summon(b, me, "summon_beast")
    b._hit(None, s, 500, "force", crit=False, weapon="test")
    assert s.state == "dead"
    s2 = summon(b, me, "summon_fey")
    s3 = summon(b, me, "summon_undead")
    assert s2.state == "dead" and s3.active, "a new concentration lets the old spirit go"
    assert len([x for x in b.fighters if x.bond is not None and x.active]) == 1


def test_the_form_suits_the_fight(tables):
    b, me = scene(tables, foes=("bandit", "bandit", "bandit"))
    assert allies.best_form(b, me, "bestial_spirit") == "land"
    for e in b.enemies_of(me):
        e.z = 20  # (they are up in the air)
    assert allies.best_form(b, me, "bestial_spirit") == "air"
    assert allies.best_form(b, me, "giant_insect") == "wasp"
    # The element whose blow hurts them most: never fire against the fire-proof.
    b2, me2 = scene(tables, foes=("young_dragon",))
    assert "fire" in b2.fighters[1].cdef["immune"]
    assert allies.best_form(b2, me2, "elemental_spirit") != "fire"


def test_the_slaad_regenerates_and_its_claw_stops_healing(tables):
    b, me = scene(tables)
    my_turn(b, me)
    s = summon(b, me, "summon_aberration", point=(8, 4), form="slaad")
    foe = b.fighters[1]
    s.hp -= 20
    b.order = [s.id] + [x for x in b.order if x != s.id]
    b.turn = 0
    b.turn_started = True
    b._start_of_turn(s)
    assert s.hp == s.max_hp - 15
    claw = next(o for o in b.attack_options(s) if o.extra.get("id") == "claw")
    for _ in range(20):
        if foe.buff_value("no_heal"):
            break
        b._attack(s, claw, foe)
        if not foe.active:
            break
    assert foe.buff_value("no_heal") or not foe.active


def test_the_mind_flayers_whispers_hurt_all_beside_it_but_its_caster(tables):
    b, me = scene(tables, foes=("bandit",))
    my_turn(b, me)
    s = summon(b, me, "summon_aberration", point=(3, 4), form="mind_flayer")
    foe = b.fighters[1]
    foe.x, foe.y = s.x + 1, s.y
    b.order = [s.id] + [x for x in b.order if x != s.id]
    b.turn = 0
    b.turn_started = True
    hp_me, hp_foe = me.hp, foe.hp
    for _ in range(6):
        b._start_of_turn(s)
    assert me.hp == hp_me, "its caster is spared"
    assert foe.hp < hp_foe or foe.state != "fighting"


def test_the_putrid_spirit_poisons_and_its_claw_paralyses_the_poisoned(tables):
    b, me = scene(tables)
    my_turn(b, me)
    s = summon(b, me, "summon_undead", point=(8, 4), form="putrid")
    foe = b.fighters[1]
    foe.x, foe.y = s.x + 1, s.y
    for _ in range(10):
        b._start_of_turn(foe)
        if "poisoned" in foe.conditions:
            break
    assert "poisoned" in foe.conditions
    claw = next(o for o in b.attack_options(s) if o.extra.get("id") == "rotting_claw")
    for _ in range(20):
        b._attack(s, claw, foe)
        if "paralyzed" in foe.conditions or not foe.active:
            break
    assert "paralyzed" in foe.conditions or not foe.active


def test_the_ghostly_touch_frightens_and_the_web_bolt_roots(tables):
    b, me = scene(tables)
    my_turn(b, me)
    g = summon(b, me, "summon_undead", point=(8, 4), form="ghostly")
    foe = b.fighters[1]
    touch = next(o for o in b.attack_options(g) if o.extra.get("id") == "deathly_touch")
    for _ in range(20):
        b._attack(g, touch, foe)
        if "frightened" in foe.conditions or not foe.active:
            break
    assert "frightened" in foe.conditions or not foe.active
    b2, me2 = scene(tables, seed=3)
    my_turn(b2, me2)
    spider = summon(b2, me2, "giant_insect", point=(4, 4), form="spider")
    foe2 = b2.fighters[1]
    web = next(o for o in b2.attack_options(spider) if o.extra.get("id") == "web_bolt")
    for _ in range(20):
        b2._attack(spider, web, foe2)
        if foe2.buff_value("slow") or not foe2.active:
            break
    from realmwalker.rules.engine import query

    assert not foe2.active or query.speed(foe2) == 0


def test_the_metal_body_burns_and_the_clay_lashes_back(tables):
    b, me = scene(tables, foes=("bandit",))
    my_turn(b, me)
    metal = summon(b, me, "summon_construct", point=(8, 4), form="metal")
    foe = b.fighters[1]
    foe.x, foe.y = metal.x + 1, metal.y
    blow = next(o for o in b.attack_options(foe) if o.is_melee)
    hp = foe.hp
    for _ in range(30):
        if b._attack(foe, blow, metal) or not foe.active:
            break
    assert foe.hp < hp or not foe.active, "hitting it burns"
    b2, me2 = scene(tables, foes=("bandit",), seed=4)
    my_turn(b2, me2)
    clay = summon(b2, me2, "summon_construct", point=(8, 4), form="clay")
    foe2 = b2.fighters[1]
    foe2.x, foe2.y = clay.x + 1, clay.y
    b2._hit(foe2, clay, 3, "slashing", crit=False, weapon="sword")
    assert not clay.reaction, "it spent its reaction lashing back"


def test_stony_lethargy_slows_a_foe_beside_it(tables):
    b, me = scene(tables, foes=("bandit",))
    my_turn(b, me)
    stone = summon(b, me, "summon_construct", point=(8, 4), form="stone")
    foe = b.fighters[1]
    foe.x, foe.y = stone.x + 1, stone.y
    for _ in range(12):
        b._start_of_turn(foe)
        if foe.buff_value("no_opportunity"):
            break
    assert foe.buff_value("no_opportunity") and foe.buff_value("slow")


def test_the_fey_moods_and_the_centipedes_spew(tables):
    b, me = scene(tables, foes=("bandit",))
    my_turn(b, me)
    fey = summon(b, me, "summon_fey", point=(6, 4), form="fuming")
    foe = b.fighters[1]
    fey.bonus = 1
    assert "fey_step_fuming" in b.creature_spells(fey)
    assert b.creature_cast(fey, "fey_step_fuming", point=(7, 3))
    assert (fey.x, fey.y) == (7, 3) and any(bf.get("aimed") for bf in fey.buffs)
    b2, me2 = scene(tables, foes=("bandit",), seed=5)
    my_turn(b2, me2)
    tricksy = summon(b2, me2, "summon_fey", point=(6, 4), form="tricksy")
    tricksy.bonus = 1
    assert b2.creature_cast(tricksy, "fey_step_tricksy", point=(6, 5))
    assert any(z.kind == "darkness" and z.owner == tricksy.id for z in b2.zones)
    b3, me3 = scene(tables, foes=("bandit",), seed=6)
    my_turn(b3, me3)
    mirth = summon(b3, me3, "summon_fey", point=(6, 4), form="mirthful")
    foe3 = b3.fighters[1]
    charmed = False
    for _ in range(15):
        mirth.bonus = 1
        mirth.cast_bonus_spell = False
        b3.creature_cast(mirth, "fey_step_mirthful", point=(foe3.x - 1, foe3.y))
        if "charmed" in foe3.conditions:
            charmed = True
            break
        mirth.x, mirth.y = 6, 4
    assert charmed
    b4, me4 = scene(tables, foes=("bandit",), seed=7)
    my_turn(b4, me4)
    pede = summon(b4, me4, "giant_insect", point=(8, 4), form="centipede")
    foe4 = b4.fighters[1]
    foe4.x, foe4.y = pede.x + 2, pede.y
    for _ in range(15):
        pede.bonus = 1
        pede.cast_bonus_spell = False
        b4.creature_cast(pede, "venomous_spew", foe4)
        if "poisoned" in foe4.conditions:
            break
    assert "poisoned" in foe4.conditions


def test_the_auto_summons_a_spirit_and_plays_it(tables):
    c = hero(tables, xp=200000)
    c.spells.setdefault("spellbook", []).append("summon_elemental")
    c.spells["prepared"] = ["summon_elemental"]
    from realmwalker.rules.inventory import add_item

    add_item(c, tables.items, "elemental_vial")
    assert not spellrules.component_problem(c, tables, "summon_elemental")
    b = fight(tables, [c], ["ogre"], {0: (2, 4), 1: (12, 4)})
    me = b.fighters[0]
    my_turn(b, me)
    opts = [o for o in actions.options(b, me, only=("cast",)) if o.value == "summon_elemental"]
    assert opts and opts[0].available
    w = estimates.spell_value(b, me, "summon_elemental", point=(10, 4))
    assert w.help > 20
    me.auto = True
    tactics.take_turn(b, me)
    spirit = [x for x in b.fighters if x.bond is not None and x.bond["kind"] == "summon"]
    assert spirit and spirit[0].active, "the Auto called up the spirit"
    spirit[0].auto = True
    for _ in range(400):
        if b.outcome is not None:
            break
        b.step()
    assert b.outcome is not None


def test_an_enemy_casters_spirit_fights_on_the_enemys_side(tables):
    b, me = scene(tables, foes=("bandit", "bandit"))
    foe = b.fighters[1]
    s = allies.summon_spirit(b, foe, "undead_spirit", 3, (8, 6), sid="summon_undead")
    assert s.side == FOE and s.team == FOE and s.bond["owner"] == foe.id
    for x in b.fighters:
        if x.side == FOE and x.bond is None:
            x.state = "dead"
    b._check_end()
    assert b.outcome == "victory", "a spirit alone does not keep the fight going"


def test_the_costly_components_are_needed_and_kept(tables):
    c = hero(tables, xp=200000)
    c.spells.setdefault("spellbook", []).append("summon_beast")
    assert "gilded acorn" in spellrules.component_problem(c, tables, "summon_beast")
    for iid in ("gilded_acorn", "gilded_flower", "gilded_skull", "platinum_vial", "lockbox", "elemental_vial"):
        assert tables.items.get(iid)["how"]
    assert spellrules.spend_material(c, tables, "summon_beast") is None, "kept, not used up"


def test_the_battle_screen_plays_a_summoned_spirit(make_app):
    import copy

    import tcod

    from realmwalker.core.rng import RNG
    from realmwalker.game import fight as gamefight
    from realmwalker.game.encounters import PendingEncounter
    from realmwalker.game.state import new_game
    from realmwalker.rules.creatures import spawn
    from realmwalker.ui import widgets
    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.battle import BattleScreen
    from realmwalker.world.generator import WorldOptions
    from tests.worlds import cached_world

    app = make_app()
    world = cached_world(WorldOptions("Lastrites", 37, "small"), app.tables)
    me = hero(app.tables, xp=200000)
    game = new_game(copy.deepcopy(world), app.tables, me)
    app.start_game(game)
    game.survival = False
    rng = RNG(5, "band")
    game.encounter = PendingEncounter("test", [spawn(app.tables, "bandit", rng, i + 1) for i in range(2)],
                                      "They come.", False, "")
    b = gamefight.encounter_fight(game, False)
    game.encounter = None
    caster = next(f for f in b.fighters if f.char is me)
    screen = BattleScreen(app, game)
    app.push(screen)
    for sid, form in (("summon_fey", "tricksy"), ("giant_insect", "spider"), ("summon_beast", "air")):
        b.order = [caster.id] + [i for i in b.order if i != caster.id]
        b.turn, b.turn_started = 0, True
        b._start_of_turn(caster)
        s = summon(b, caster, sid, point=(caster.x + 1, caster.y), form=form)
        assert s.bond["picture"]
        b.order = [s.id] + [i for i in b.order if i != s.id]
        b.turn, b.turn_started = 0, True
        b._start_of_turn(s)
        assert b.pending_party() is s, "the player commands a spirit like a member of the party"
        for key in ("tab", "escape", "a", "escape", "c", "escape"):
            app.handle_event(KeyEvent(key))
        for size in ((80, 30), (160, 45)):
            screen.render(widgets.Canvas(tcod.console.Console(*size, order="F")))
    assert app.error_count == 0
