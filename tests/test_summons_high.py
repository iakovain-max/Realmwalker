"""Summoned spirits of levels 5-6 and Animate Objects (Expansion 3 F.3): Summon Celestial (the Avenger and the
Defender, Healing Touch), Summon Dragon (Shared Resistances, the breath with the Rends), Summon Fiend (Magic
Resistance, the demon's Death Throes, the devil's sight in magical darkness, the yugoloth's step) and Animate Objects
(as many things as the caster's modifier, by size and slot, waiting for the caster's word) in real fights."""

import pytest

from realmwalker.rules import allies
from realmwalker.rules import spells as spellrules
from realmwalker.rules import tactics
from realmwalker.rules.combat import FOE, PARTY, Zone
from realmwalker.rules.engine import actions, estimates, query
from tests.test_allies import fight, hero
from tests.test_summons import scene, summon
from tests.test_wave4 import my_turn, sturdy

SPELLS = ("summon_celestial", "summon_dragon", "summon_fiend")


@pytest.fixture(scope="module")
def tables(data):
    from realmwalker.world.tables import Tables

    return Tables(data)


# The book's numbers at the spell's own level (PHB 2024, checked on the page images): form, AC, HP, HP a level more,
# the first attack's damage, attacks a turn.
NUMBERS = {
    ("summon_celestial", "avenger"): (16, 40, 10, "2d6+7", 2),
    ("summon_celestial", "defender"): (18, 40, 10, "1d10+8", 2),
    ("summon_dragon", "cold"): (19, 50, 10, "1d6+9", 2),
    ("summon_fiend", "demon"): (18, 50, 15, "1d12+9", 3),
    ("summon_fiend", "devil"): (18, 40, 15, "2d6+9", 3),
    ("summon_fiend", "yugoloth"): (18, 60, 15, "1d8+9", 3),
}


@pytest.mark.parametrize("sid,form", list(NUMBERS))
def test_each_spirit_has_the_books_numbers_at_two_slots(tables, sid, form):
    ac, hp, hp_up, dmg, n = NUMBERS[(sid, form)]
    b, me = scene(tables)
    my_turn(b, me)
    s = summon(b, me, sid, form=form)
    assert s.bond["form"] == form and s.side == PARTY and s.sq == 2, "a Large spirit"
    assert s.cdef["ac"] == ac and s.hp == hp
    assert s.cdef["attacks"][0]["damage"] == dmg
    assert s.cdef["multiattack"] == n and query.attacks_per_action(s) == n, "the player's spirit strikes as often"
    assert b.order[b.order.index(me.id) + 1] == s.id
    b2, me2 = scene(tables, seed=2)
    my_turn(b2, me2)
    s2 = summon(b2, me2, sid, up=1, form=form)
    assert s2.cdef["ac"] == ac + 1 and s2.hp == hp + hp_up
    assert s2.cdef["multiattack"] == (b2.t.spells[sid]["level"] + 1) // 2


def test_the_defender_wards_a_friend_and_the_celestial_heals_once(tables):
    b, me = scene(tables, foes=("ogre",))
    my_turn(b, me)
    s = summon(b, me, "summon_celestial", point=(8, 4), form="defender")
    ogre = b.fighters[1]
    sturdy(ogre, hp=500)
    me.x, me.y = ogre.x - 1, ogre.y + 1  # (beside the ogre, and hurt)
    me.hp = 3
    s.x, s.y = ogre.x - 2, ogre.y - 1
    mace = next(o for o in b.attack_options(s) if o.extra["id"] == "radiant_mace")
    for _ in range(20):
        if me.temp_hp:
            break
        b._attack(s, mace, ogre)
    assert me.temp_hp > 0, "the hurt friend within 10 feet of the target gains temporary hit points"
    # Healing Touch: once, to another creature, 2d8 + the spell's level.
    s.action = 1
    assert "celestial_healing_touch" in b.creature_spells(s)
    assert s not in b.spell_targets(s, "celestial_healing_touch"), "another creature"
    s.x, s.y = me.x + 1, me.y
    before = me.hp
    assert b.creature_cast(s, "celestial_healing_touch", target=me)
    assert 2 + 5 <= me.hp - before <= 16 + 5
    s.action = 1
    assert "celestial_healing_touch" not in b.creature_spells(s), "once each time it is summoned"


def test_the_dragon_shares_its_resistance_and_breathes_with_its_rends(tables):
    b, me = scene(tables, foes=("bandit", "bandit"))
    my_turn(b, me)
    s = summon(b, me, "summon_dragon", point=(6, 4), form="cold")
    assert query.damage_taken(me, 10, "cold")[0] == 5, "its caster resists cold while the spell holds"
    breath = next(a for a in s.cdef["attacks"] if a.get("area"))
    assert breath["damage_type"] == "cold" and breath["dc"] == allies.caster_numbers(me.char, b.t)[1]
    # On Auto: the Rends and the breath in one turn.
    for e in b.enemies_of(s):
        sturdy(e)
    b.fighters[1].x, b.fighters[1].y = s.x + 2, s.y
    b.fighters[2].x, b.fighters[2].y = s.x + 3, s.y + 1
    my_turn(b, s)
    s.auto = True
    seen = len(b.events)
    tactics.take_turn(b, s)
    mine = [e for e in b.events[seen:] if e.get("by") == s.id]
    assert any(e["kind"] == "cast" and e.get("effect") == "breath" for e in mine), "it breathed"
    assert sum(1 for e in mine if e["kind"] == "attack") >= 1, "and it rent"
    opt = next(o for o in b.attack_options(s) if o.extra.get("area"))
    assert not opt.available, "once a turn"
    # Played by the player: the breath begins the Attack action and the Rends still follow.
    my_turn(b, s)
    opt = next(o for o in b.attack_options(s) if o.extra.get("area"))
    target = b.fighters[1]
    assert b.do_attack(s, opt, target)
    assert s.action == 0 and s.attacks_left == 2
    rend = next(o for o in b.attack_options(s) if o.extra["id"] == "rend")
    s.x, s.y = target.x - 2, target.y
    assert b.do_attack(s, rend, target)
    b._end_concentration(me, quiet=True)
    assert query.damage_taken(me, 10, "cold")[0] == 10, "the resistance goes with the spell"


def test_the_fiends_magic_resistance_and_the_demons_death_throes(tables):
    b, me = scene(tables, foes=("bandit", "bandit"))
    my_turn(b, me)
    s = summon(b, me, "summon_fiend", point=(8, 4), form="demon")
    b.__dict__["_casting"] = "fireball"
    r = query.save_roll(b, s, "dex")
    b.__dict__["_casting"] = None
    assert "advantage" in str(vars(r.roll)).lower() or r.roll.advantage, "Advantage on saves against spells"
    foes = b.enemies_of(s)
    for e in foes:
        sturdy(e, hp=200)
    foes[0].x, foes[0].y = s.x + 2, s.y
    foes[1].x, foes[1].y = s.x + 6, s.y
    before = [e.hp for e in foes]
    b._hit(None, s, 500, "force", crit=False, weapon="test")
    assert s.state == "dead"
    assert foes[0].hp < before[0], "the explosion catches whoever stands within 10 feet"
    assert foes[1].hp == before[1]
    # The spell ending sets it off too.
    b2, me2 = scene(tables, foes=("bandit",), seed=4)
    my_turn(b2, me2)
    s2 = summon(b2, me2, "summon_fiend", point=(8, 4), form="demon")
    foe = b2.fighters[1]
    sturdy(foe, hp=200)
    foe.x, foe.y = s2.x + 2, s2.y
    b2._end_concentration(me2, quiet=True)
    assert s2.state == "dead" and foe.hp < 200


def test_the_devil_sees_through_magical_darkness_and_the_yugoloth_steps(tables):
    b, me = scene(tables, foes=("bandit",))
    my_turn(b, me)
    devil = summon(b, me, "summon_fiend", point=(5, 4), form="devil")
    foe = b.fighters[1]
    foe.x, foe.y = devil.x + 4, devil.y
    cells = {(x, y) for x in range(foe.x - 1, foe.x + 2) for y in range(foe.y - 1, foe.y + 2)}
    b._add_zone(Zone(b._zone_id(), "darkness", cells, owner=foe.id, spell="darkness", rounds=10, dark=True))
    assert not b.can_see(me, foe), "the darkness hides the foe from the caster"
    assert b.can_see(devil, foe), "but not from the devil"
    b._end_concentration(me, quiet=True)
    # The yugoloth: when the foe it clawed falls, it steps beside the next one.
    b2, me2 = scene(tables, foes=("bandit", "bandit"), seed=5)
    my_turn(b2, me2)
    yugo = summon(b2, me2, "summon_fiend", point=(5, 4), form="yugoloth")
    a, c = b2.fighters[1], b2.fighters[2]
    a.x, a.y = yugo.x + 2, yugo.y
    c.x, c.y = yugo.x + 5, yugo.y + 2
    a.hp = 1
    claws = next(o for o in b2.attack_options(yugo) if o.extra["id"] == "claws")
    for _ in range(20):
        if not a.active:
            break
        b2._attack(yugo, claws, a)
    assert not a.active
    assert b2.gap(yugo, c) == 1, "it folded through the world to the next foe"


def objects(b, f, level=5, point=(6, 4), mod=4):
    old = allies.caster_attack_dc
    allies.caster_attack_dc = lambda b_, o_: (old(b_, o_)[0], old(b_, o_)[1], mod)
    try:
        sp = b.t.spells["animate_objects"]
        b.cast(f, "animate_objects", sp, None, point, up=level - 5, mod=mod, dc=15, bonus=7, mult=1, level=level)
    finally:
        allies.caster_attack_dc = old
    return b.objects_of(f)


def test_animate_objects_wakes_things_by_the_casters_modifier(tables):
    b, me = scene(tables, foes=("bandit", "bandit"))
    my_turn(b, me)
    things = objects(b, me, mod=5)
    assert [x.bond["form"] for x in things] == ["large", "large", "medium"], "Large ones in pairs, a Medium one left"
    big = things[0]
    attack = allies.caster_numbers(me.char, b.t)[0]
    assert big.sq == 2 and big.hp == 20 and big.cdef["ac"] == 15 and big.cdef["attacks"][0]["damage"] == "2d6+8"
    assert big.cdef["attacks"][0]["bonus"] == attack and big.cdef["attacks"][0]["damage_type"] == "force"
    assert things[2].hp == 10 and things[2].cdef["attacks"][0]["damage"] == "1d4+3"
    assert all(x.bond["kind"] == "objects" and x.side == PARTY for x in things)
    assert "stone" in things[2].name or "log" in big.name, "outside: stones and logs"
    # A higher slot: another die of each size; a single great foe: a Huge one.
    b2, me2 = scene(tables, foes=("ogre",), seed=2)
    my_turn(b2, me2)
    things2 = objects(b2, me2, level=7, mod=4)
    assert [x.bond["form"] for x in things2] == ["huge", "medium"]
    assert things2[0].sq == 3 and things2[0].hp == 40 and things2[0].cdef["attacks"][0]["damage"] == "4d12+7"
    assert things2[1].cdef["attacks"][0]["damage"] == "3d4+3"
    b2._end_concentration(me2, quiet=True)
    assert not b2.objects_of(me2), "they fall back into things when the spell ends"


def test_the_objects_wait_for_a_word_and_act_when_commanded(tables):
    b, me = scene(tables, foes=("bandit",))
    my_turn(b, me)
    things = objects(b, me, mod=2)
    (log,) = things
    foe = b.fighters[1]
    sturdy(foe)
    log.auto = True
    b.end_turn()
    assert b.current is log
    b.step()
    assert log.dodging and b.current is not log, "no word from its caster: it Dodges"
    # Next round, the caster commands it with the Bonus Action.
    while b.current is not me:
        b.step()
    opt = next(o for o in actions.options(b, me) if o.id == "ability:command_objects")
    assert opt.available and opt.cost == "bonus"
    b.do_ability(me, "command_objects")
    assert me.bonus == 0
    assert not next(o for o in actions.options(b, me) if o.id == "ability:command_objects").available
    b.end_turn()
    assert b.current is log
    seen = len(b.events)
    for _ in range(5):
        if b.current is not log:
            break
        b.step()
    assert not log.dodging
    assert any(e.get("who") == log.id and e["kind"] == "move" or e.get("by") == log.id for e in b.events[seen:])


def test_the_auto_casts_each_spell_and_commands_the_objects(tables):
    from realmwalker.rules.inventory import add_item

    for sid, item in (("summon_celestial", "silver_reliquary"), ("summon_dragon", "dragon_token"),
                      ("summon_fiend", "bloody_vial"), ("animate_objects", None)):
        c = hero(tables, xp=355000)
        c.spells.setdefault("spellbook", []).append(sid)
        c.spells["prepared"] = [sid]
        if item:
            assert tables.items.get(item)["how"]
            assert spellrules.component_problem(c, tables, sid)
            add_item(c, tables.items, item)
            assert spellrules.spend_material(c, tables, sid) is None, "kept, not used up"
        assert not spellrules.component_problem(c, tables, sid)
        b = fight(tables, [c], ["ogre", "ogre"], {0: (2, 4), 1: (10, 4), 2: (10, 6)})
        me = b.fighters[0]
        my_turn(b, me)
        w = estimates.spell_value(b, me, sid, point=(8, 4))
        assert w.help > 20, (sid, w)
        me.auto = True
        tactics.take_turn(b, me)
        made = [x for x in b.fighters if x.bond is not None and x.active]
        assert made and me.concentration["spell"] == sid, sid
        if sid == "animate_objects":
            assert all(x.bond.get("told") == b.round for x in made) or me.bonus == 0, "the Auto gives the word"
        for x in made:
            x.auto = True
        for _ in range(500):
            if b.outcome is not None:
                break
            b.step()
        assert b.outcome is not None, sid


def test_an_enemy_casters_objects_act_without_a_word(tables):
    b, me = scene(tables, foes=("bandit", "bandit"))
    foe = b.fighters[1]
    foe.cdef = dict(foe.cdef, spellcasting={"ability": "int", "dc": 13, "attack": 5})
    made = allies.animate_objects(b, foe, 5, (8, 6), sid="animate_objects")
    assert made and all(x.side == FOE for x in made)
    assert not b._waits_for_word(made[0]), "a creature commands them as part of its own turn"


def test_every_new_form_is_drawn(tables):
    from realmwalker.paths import Paths
    from realmwalker.ui.gfx import battlefx, dolls
    from realmwalker.ui.gfx.atlas import Atlas

    atlas = Atlas(Paths().tiles)
    assert atlas.ok
    for sid in SPELLS:
        cid = tables.spells[sid]["effects"][0]["creature"]
        assert atlas.has(f"creature/{cid}")
        for form in tables.creatures[cid]["summon"]["forms"]:
            b, me = scene(tables)
            my_turn(b, me)
            s = summon(b, me, sid, form=form)
            parts = battlefx._figure(s, None, atlas)
            assert atlas.has(parts[0][0]), parts
            assert dolls.compose(atlas, parts) is not None
    assert atlas.has("creature/animated_object")
    for size, z in tables.creatures["animated_object"]["summon"]["sizes"].items():
        for where in ("in", "out"):
            assert atlas.has(f"creature/{z[where]['picture']}"), (size, where)
    for iid in ("silver_reliquary", "dragon_token", "bloody_vial"):
        assert atlas.has(f"item/{iid}")


def test_the_battle_screen_plays_the_new_spirits_and_the_objects(make_app):
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
    me = hero(app.tables, xp=355000)
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

    def turn_of(f):
        b.order = [f.id] + [i for i in b.order if i != f.id]
        b.turn, b.turn_started = 0, True
        b._start_of_turn(f)

    for sid, form in (("summon_dragon", "fire"), ("summon_celestial", "defender"), ("summon_fiend", "devil")):
        turn_of(caster)
        s = summon(b, caster, sid, point=(caster.x + 2, caster.y), form=form)
        assert s.bond["picture"]
        turn_of(s)
        assert b.pending_party() is s
        for key in ("tab", "escape", "a", "escape", "c", "escape"):
            app.handle_event(KeyEvent(key))
        for size in ((80, 30), (160, 45)):
            screen.render(widgets.Canvas(tcod.console.Console(*size, order="F")))
    turn_of(caster)
    things = objects(b, caster, mod=3, point=(caster.x + 2, caster.y))
    assert things and b.pending_party() is caster
    opt = next(o for o in actions.options(b, caster) if o.id == "ability:command_objects")
    assert opt.available
    for size in ((80, 30), (160, 45)):
        screen.render(widgets.Canvas(tcod.console.Console(*size, order="F")))
    b.do_ability(caster, "command_objects")
    turn_of(things[0])
    assert b.pending_party() is things[0], "a commanded thing is the player's to move"
    for key in ("tab", "escape", "a", "escape"):
        app.handle_event(KeyEvent(key))
    screen.render(widgets.Canvas(tcod.console.Console(160, 45, order="F")))
    assert app.error_count == 0
