"""Demigods & Magics part A: twenty levels and the epic boons (PHB 2024 pp. 44, 213-214) - the tables to 20, the boon
chosen at 19, and each of the twelve boons at work in a real fight or check."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import feats, grid, progression, tactics
from realmwalker.rules.character import Sheet
from realmwalker.rules.engine import actions, query
from realmwalker.rules.engine import resources as res
from realmwalker.world.tables import Tables

from tests.test_feats import armed, fight, give, hero, on_turn, soft, wield

ANY = {"increase": "con"}


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def test_twenty_levels_and_the_boon_at_nineteen(tables):
    rules = tables.rules
    assert rules["max_level"] == 20 and len(rules["xp_for_level"]) == 20 and rules["xp_for_level"][-1] == 355000
    assert rules["proficiency_bonus"][16] == 6
    c = hero(tables, "fighter", level=20)
    assert c.level == 20 and Sheet(c, tables).proficiency == 6
    boons = [f["id"] for f in c.feats if feats.defs(tables)[f["id"]]["category"] == "epic"]
    assert len(boons) == 1  # (the Auto took one at 19, by the way it fights)
    w = hero(tables, "wizard", level=20)
    assert any(f["id"] == "boon_of_spell_recall" for f in w.feats)
    assert tables.classes["wizard"]["spellcasting"]["slots"][19][8] >= 1  # a ninth-level slot at 17 and after


def test_the_boon_choice_offers_epic_boons_first(tables):
    c = hero(tables, "fighter", level=18)
    progression.level_up(c, tables, RNG(1, "lv"))
    choice = next(p for p in c.pending if p["kind"] == "boon")
    opts = progression.options(c, tables, choice)
    assert opts[0][1].startswith("Epic boon") and any(o[1].startswith("Feat:") for o in opts)
    assert "spell_recall" not in " ".join(o[0] for o in opts)  # (a fighter casts no spells)
    pick = progression.suggest(c, tables, choice, opts)
    assert pick.startswith("feat:boon_of_")
    plain = next(o[0] for o in opts if not o[0].startswith("feat:"))  # (the plain increase is there too)
    str_before = c.abilities[plain.split("+")[0]]
    progression.resolve(c, tables, choice, plain)
    assert c.abilities[plain.split("+")[0]] > str_before


def test_an_ability_may_rise_to_thirty(tables):
    c = hero(tables, "fighter", level=19)
    c.abilities["str"] = 20
    give(tables, c, "boon_of_combat_prowess", increase="str")
    assert c.abilities["str"] == 21


def test_peerless_aim_turns_one_miss_a_turn_into_a_hit(tables):
    c = armed(tables, "longsword", level=19)
    give(tables, c, "boon_of_combat_prowess", **ANY)
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe, ac=60)  # (only a 20 would hit)
    opt = next(o for o in b.attack_options(me) if o.key == "main")
    on_turn(b, me)
    hits = [b._attack(me, opt, foe) for _ in range(4)]
    assert hits.count(True) >= 1 and hits[0]
    on_turn(b, me)
    assert b._attack(me, opt, foe)  # (ready again on the next turn)


def test_blink_steps_after_an_attack(tables):
    c = armed(tables, "longsword", level=19)
    give(tables, c, "boon_of_dimensional_travel", **ANY)
    b = fight(tables, c, "bandit", "bandit")
    me, foe, foe2 = b.fighters
    soft(foe)
    on_turn(b, me)
    a = actions.find(me, "blink_steps")
    assert actions.problem(b, me, a)
    opt = next(o for o in b.attack_options(me) if o.key == "main")
    b.do_attack(me, opt, foe)
    if me.attacks_left > 0:
        assert actions.problem(b, me, a)  # (not between the swings of one Attack action)
    while me.attacks_left > 0:
        b.do_attack(me, opt, foe)
    assert actions.problem(b, me, a) is None
    before = (me.x, me.y)
    assert b.do_ability(me, "blink_steps") is not False
    assert (me.x, me.y) != before and grid.gap(me.space, (before[0], before[1], 1)) <= 6
    assert not any(b.gap(me, e) <= 1 for e in (foe, foe2))
    assert actions.problem(b, me, a)  # (once, until the next attack)


def test_energy_resistance_halves_and_turns_the_fire_back(tables):
    c = hero(tables, "fighter", level=19)
    give(tables, c, "boon_of_energy_resistance", increase="con", resist=["fire", "cold"])
    assert feats.boon_resists(c) == {"fire", "cold"}
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe, hp=300)
    assert query.resists(me, "fire") and not query.resists(me, "acid")
    hp = me.hp
    b._hit(foe, me, 20, "fire", crit=False, weapon="fire")
    assert hp - me.hp == 10
    assert not me.reaction  # (the reaction went on turning it back)
    assert any(e.get("spell") == "energy_redirection" for e in b.events)


def test_improve_fate_saves_a_friend_and_comes_back_with_the_initiative(tables):
    c = hero(tables, "cleric", level=19)
    give(tables, c, "boon_of_fate", **ANY)
    friend = hero(tables, "fighter", seed=2, level=5)
    b = fight(tables, [c, friend], "bandit")
    me, fr, foe = b.fighters
    assert c.uses.get("improve_fate") == 1
    saved = 0
    for _ in range(80):
        c.uses["improve_fate"] = 1
        if b._save(fr, "wis", 30):  # (only with luck: Improve Fate adds 2d4 when it falls short by 5 or less)
            saved += 1
    assert saved == 0  # (too far short)
    turned = 0
    for _ in range(200):
        c.uses["improve_fate"] = 1
        bonus = query.save_roll(b, fr, "str").bonus
        if b._save(fr, "str", 10 + bonus + 3):
            turned += 1
    assert turned > 0


def test_fortitude_forty_hit_points_and_more_from_healing(tables):
    c = hero(tables, "fighter", level=19)
    hp = c.max_hp
    give(tables, c, "boon_of_fortitude", increase="con")
    con = (c.abilities["con"] - 10) // 2
    assert c.max_hp >= hp + 40
    b = fight(tables, c, "bandit")
    me = b.fighters[0]
    on_turn(b, me)
    me.hp = 10
    b._heal(me, 5)
    assert me.hp == 15 + max(0, con)
    b._heal(me, 5)
    assert me.hp == 20 + max(0, con)  # (once a turn)


def test_irresistible_offense_cuts_through_and_strikes_with_the_score(tables):
    c = armed(tables, "longsword", level=19)
    give(tables, c, "boon_of_irresistible_offense", increase="str")
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe)
    foe.cdef = dict(foe.cdef, resist=["slashing"])
    assert b._ignores_resist(me, "slashing") and not b._ignores_resist(me, "fire")
    hp = foe.hp
    b._hit(me, foe, 20, "slashing", crit=False, weapon="sword")
    assert hp - foe.hp == 20
    from realmwalker.rules.engine import events

    opt = next(o for o in b.attack_options(me) if o.key == "main")
    ev = events.emit(b, "attack_damage", actor=me, target=foe, opt=opt, crit=True, natural=20, advantage=False,
                     sides=8, extra=0, typed=[], rolls=[4])
    assert ev.extra >= c.abilities["str"]


def test_recovery_last_stand_and_the_ten_dice(tables):
    c = hero(tables, "fighter", level=19)
    c.pending = []
    progression.take_feat(c, tables, "boon_of_recovery")
    while c.pending:
        progression.auto_resolve(c, tables)
    assert c.uses["last_stand"] == 1 and c.uses["vitality_dice"] == 10
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    b._apply_hp_loss(me, me.hp + 5, source=foe, cause="test")
    assert me.state == "fighting" and me.hp >= me.max_hp // 2
    me.hp = 5
    on_turn(b, me)
    b.do_ability(me, "recover_vitality")
    assert me.hp > 5 and c.uses["vitality_dice"] < 10 and me.bonus == 0
    res.recover(c, tables, "long")
    assert c.uses["vitality_dice"] == 10 and c.uses["last_stand"] == 1


def test_skill_every_skill_and_one_expertise(tables):
    c = hero(tables, "rogue", level=19)
    give(tables, c, "boon_of_skill", increase="dex", expertise="arcana")
    assert set(tables.rules["skills"]) <= set(c.skills) and "arcana" in c.expertise


def test_speed_thirty_feet_more_and_escape_artist(tables):
    c = hero(tables, "fighter", level=19)
    before = Sheet(c, tables).speed()
    give(tables, c, "boon_of_speed", **ANY)
    assert Sheet(c, tables).speed() == before + 30
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    on_turn(b, me)
    me.conditions["grappled"] = -1
    b.do_ability(me, "escape_artist")
    assert "grappled" not in me.conditions and me.disengaged and me.bonus == 0


def test_spell_recall_keeps_a_slot_on_its_level(tables):
    w = hero(tables, "wizard", level=19)
    w.feats = [f for f in w.feats if feats.defs(tables)[f["id"]]["category"] != "epic"]
    give(tables, w, "boon_of_spell_recall", increase="int")
    b = fight(tables, w, "bandit")
    me, foe = b.fighters
    soft(foe)
    from realmwalker.rules import spells as spellrules

    sid = next(s for s in spellrules.known_spells(w, tables) if tables.spells[s]["level"] == 1
               and tables.spells[s]["target"] == "enemy")
    kept = 0
    for i in range(40):
        w.spells["slots_used"] = [0] * 9
        foe.hp = 300
        on_turn(b, me)
        assert b.do_cast(me, sid, foe, slot_level=1)
        kept += w.spells["slots_used"][0] == 0
    assert 0 < kept < 40  # (about one in four)


def test_night_spirit_unseen_in_the_dark_and_harder_to_hurt(tables):
    c = armed(tables, "longsword", level=19)
    give(tables, c, "boon_of_the_night_spirit", **ANY)
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe)
    b.light = lambda: __import__("numpy").zeros((b.field.width, b.field.height))  # a moonless night
    on_turn(b, me)
    assert actions.problem(b, me, actions.find(me, "merge_with_shadows")) is None
    b.do_ability(me, "merge_with_shadows")
    assert "invisible" in me.conditions and me.bonus == 0
    hp = me.hp
    b._hit(foe, me, 20, "slashing", crit=False, weapon="sword")
    assert hp - me.hp == 10
    hp = me.hp
    b._hit(foe, me, 20, "radiant", crit=False, weapon="light")
    assert hp - me.hp == 20
    b.do_attack(me, next(o for o in b.attack_options(me) if o.key == "main"), foe)
    assert "invisible" not in me.conditions  # (the shadows let go when they act)


def test_truesight_sees_the_invisible(tables):
    c = hero(tables, "fighter", level=19)
    give(tables, c, "boon_of_truesight", **ANY)
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    assert me.senses.get("truesight") == 60
    foe.conditions["invisible"] = -1
    assert b.can_see(me, foe)


def test_the_auto_uses_its_boons_in_a_fight(tables):
    c = armed(tables, "longsword", level=19)
    give(tables, c, "boon_of_the_night_spirit", **ANY)
    give(tables, c, "boon_of_recovery", **ANY)
    res.fill(c, tables)
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    me.auto = True
    soft(foe, ac=30)
    b.light = lambda: __import__("numpy").zeros((b.field.width, b.field.height))
    me.hp = me.max_hp // 3
    on_turn(b, me)
    tactics.take_turn(b, me)
    assert me.hp > me.max_hp // 3 or "invisible" in me.conditions


def test_the_worst_sites_go_five_levels_down(tables):
    from types import SimpleNamespace

    from realmwalker.world import dungeon

    site = SimpleNamespace(kind="ruin", danger=9, faction=-1, id=1, x=0, y=0)
    world = SimpleNamespace(factions={}, politics={})
    assert dungeon.depth_for(world, site) == 5
    site.danger = 3
    assert dungeon.depth_for(world, site) == 1


def test_a_named_beast_grows_with_its_legend(tables):
    from realmwalker.rules import encounter
    from realmwalker.rules.creatures import spawn

    assert [encounter.tier_of(lv) for lv in (1, 4, 5, 10, 11, 16, 17, 20)] == [1, 1, 2, 2, 3, 3, 4, 4]
    c = spawn(tables, "troll", RNG(1, "t"), 1)
    hp = c.max_hp
    encounter.legend_grows(tables, c, 3)
    assert c.max_hp == hp
    encounter.legend_grows(tables, c, 17)
    assert c.max_hp == hp * 4 and c.hp == c.max_hp
    c2 = spawn(tables, "troll", RNG(1, "t"), 1)
    encounter.legend_grows(tables, c2, 8)
    assert c2.max_hp == hp  # (the game before twenty levels is untouched)


def test_dungeons_under_ordinary_lands_keep_their_old_depths(tables):
    from realmwalker.rules import encounter

    assert [encounter.land_level(tables, 7, d) for d in range(4)] == [3, 4, 5, 6]
    assert encounter.land_level(tables, 5, 4) == 5
    assert encounter.land_level(tables, 8, 2) == 20 and encounter.land_level(tables, 9, 0) == 11
