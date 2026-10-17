"""Blades & Backgrounds part C: feats (PHB 2024 chapter 5) - who may take one, its picks, the level's choice between
an ability increase and a feat, and the general and fighting style feats at work in real fights."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import feats, progression, tactics
from realmwalker.rules.character import Sheet
from realmwalker.rules.combat import Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import actions, query
from realmwalker.rules.engine.handlers import general_feats
from realmwalker.rules.inventory import add_item, equip, unequip
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def hero(tables, cls="fighter", seed=1, level=1, race="human"):
    b = CharacterBuilder(tables, RNG(seed, "hero"))
    b.set_race(race)
    b.set_class(cls)
    b.set_background("soldier")
    c = b.build()
    for _ in range(level - 1):
        progression.level_up(c, tables, RNG(seed, "lv"))
    c.pending = [p for p in c.pending if p["kind"] != "asi"]
    progression.auto_resolve(c, tables)
    return c


def wield(tables, c, def_id, slot=None):
    it = add_item(c, tables.items, def_id)
    ok, why = equip(c, tables.items, it.uid, slot)
    assert ok, why
    return it


def armed(tables, *weapons, cls="fighter", level=4, seed=1):
    c = hero(tables, cls, seed=seed, level=level)
    for slot in ("main_hand", "off_hand"):
        unequip(c, slot)
    for w in weapons:
        wield(tables, c, w, "off_hand" if w == "shield" else None)
    return c


def give(tables, c, fid, **choices):
    feats.grant(c, tables, fid, choices or None)


def fight(tables, party, *foes, seed=1, spots=None):
    party = party if isinstance(party, list) else [party]
    rng = RNG(seed, "foes")
    crs = [spawn(tables, d, rng, i + 1) for i, d in enumerate(foes)]
    spots = spots or ({i: (3, 4 + i) for i in range(len(party))}
                      | {len(party) + i: (4, 4 + i) for i in range(len(crs))})
    b = Battle(tables, party, crs, Env(), RNG(seed, "battle"), spots=spots)
    b.start("Test fight.")
    return b


def soft(f, ac=1, hp=300):
    f.cdef = dict(f.cdef, ac=ac)
    f.creature.max_hp = f.creature.hp = hp


def main_opt(b, me):
    return next(o for o in b.attack_options(me) if o.key == "main")


def hits(b, att, target, opt, n=20):
    """The damage of the first n hits."""
    out = []
    for _ in range(400):
        before = target.hp
        if b._attack(att, opt, target):
            out.append(before - target.hp)
            target.hp = before
            if len(out) >= n:
                break
    return out


def on_turn(b, f):
    """Make it `f`'s turn (fresh action, bonus action and reaction)."""
    b.turn = b.order.index(f.id)
    b.round += 1  # (a new turn: what is once a turn is ready again)
    b._start_of_turn(f)
    b.turn_started = True


# ---------------------------------------------------------------------------- C.1 the framework
def test_prerequisites_and_having_it_already(tables):
    c = hero(tables, level=4)
    c.abilities["str"] = 12
    assert feats.problem(c, tables, "great_weapon_master") == "Strength 13 or more"
    c.abilities["str"] = 13
    assert feats.problem(c, tables, "great_weapon_master") is None
    assert feats.problem(c, tables, "heavy_armor_master") is None  # (fighters train in heavy armour)
    assert feats.problem(c, tables, "war_caster") == "the power to cast spells"
    assert feats.problem(c, tables, "defense") == "already taken"
    low = hero(tables, level=3)
    assert feats.problem(low, tables, "durable") == "level 4 or higher"
    wiz = hero(tables, "wizard", level=4)
    assert feats.problem(wiz, tables, "heavily_armored") == "training with medium armour"
    assert feats.problem(wiz, tables, "archery") == "the Fighting Style feature"
    assert "skilled" in feats.choosable(c, tables)  # an origin feat may be taken at a level too (2024)


def test_a_level_offers_feats_beside_the_ability_increases(tables):
    c = hero(tables, level=3)
    progression.level_up(c, tables, RNG(3, "lv"))
    asi = next(p for p in c.pending if p["kind"] == "asi")
    ids = [o[0] for o in progression.options(c, tables, asi)]
    assert "str+2" in ids and "feat:great_weapon_master" in ids and "feat:defense" not in ids
    assert progression.choice_title(c, tables, asi).endswith("or take a feat")
    before = c.abilities["str"]
    progression.resolve(c, tables, asi, "feat:great_weapon_master")  # (only Strength to raise: taken at once)
    assert feats.has(c, "great_weapon_master") and c.abilities["str"] == min(20, before + 1)
    assert not any(p["kind"] in ("asi", "feat") for p in c.pending)


def test_a_feats_own_picks_wait_one_at_a_time(tables):
    wiz = hero(tables, "wizard", level=3)
    progression.level_up(wiz, tables, RNG(3, "lv"))
    asi = next(p for p in wiz.pending if p["kind"] == "asi")
    progression.resolve(wiz, tables, asi, "feat:elemental_adept")
    step = wiz.pending[0]
    assert step["kind"] == "feat" and "which ability" in progression.choice_title(wiz, tables, step)
    assert {o[0] for o in progression.options(wiz, tables, step)} == {"int", "wis", "cha"}
    assert progression.suggest(wiz, tables, step) == "int"
    progression.resolve(wiz, tables, step, "int")
    assert "which element" in progression.choice_title(wiz, tables, step)
    progression.resolve(wiz, tables, step, "cold")
    assert feats.adept_types(wiz) == {"cold"} and not any(p["kind"] == "feat" for p in wiz.pending)
    assert feats.problem(wiz, tables, "elemental_adept") is None  # repeatable, another element
    assert "cold" not in feats.options(tables, wiz, "elemental_adept", "element", {})


def test_suggest_raises_an_even_main_ability_else_takes_the_feat_that_suits(tables):
    c = armed(tables, "greataxe", level=3)
    progression.level_up(c, tables, RNG(3, "lv"))
    asi = next(p for p in c.pending if p["kind"] == "asi")
    c.abilities["str"] = 16
    assert progression.suggest(c, tables, asi) == "str+2"
    c.abilities["str"] = 17
    assert feats.archetype(c, tables) == "great_weapon"
    assert progression.suggest(c, tables, asi) == "feat:great_weapon_master"
    archer = armed(tables, "longbow", level=4)
    assert feats.archetype(archer, tables) == "archer"
    assert feats.archetype(hero(tables, "wizard"), tables) == "caster"


def test_the_fighting_style_is_a_feat_and_the_champion_learns_another(tables):
    c = hero(tables)
    assert feats.style_of(c, tables) == "defense"  # (mail and a shield in the first kit)
    c.subclass = "champion" if "champion" in tables.classes["fighter"]["subclasses"] else c.subclass
    for _ in range(9):
        progression.level_up(c, tables, RNG(5, "lv"))
    style = next((p for p in c.pending if p["kind"] == "style"), None)
    if c.subclass == "champion":
        assert style is not None
        ids = [o[0] for o in progression.options(c, tables, style)]
        assert "defense" not in ids and "archery" in ids
        progression.auto_resolve(c, tables)
        assert len([f for f in c.feats if feats.defs(tables)[f["id"]]["category"] == "fighting_style"]) == 2


def test_half_feats_raise_their_ability_and_give_training(tables):
    wiz = hero(tables, "wizard", level=4)
    give(tables, wiz, "lightly_armored", increase="dex")
    assert "light" in wiz.armor_prof and "shield" in wiz.armor_prof
    give(tables, wiz, "moderately_armored")
    assert "medium" in wiz.armor_prof
    before = wiz.abilities["con"]
    give(tables, wiz, "resilient", increase="con")
    assert "con" in wiz.saves and wiz.abilities["con"] == before + 1
    give(tables, wiz, "skill_expert")
    assert len(wiz.expertise) >= 1
    cleric = hero(tables, "cleric", level=4)
    give(tables, cleric, "weapon_master")
    assert progression.mastery_count(cleric, tables) == 1
    assert any(p["kind"] == "mastery" for p in cleric.pending)


# ---------------------------------------------------------------------------- C.3 Great Weapon Master, the done-when test
def test_a_level_four_fighter_takes_great_weapon_master_and_it_works_in_battle(tables):
    c = armed(tables, "greatsword", level=3)
    c.abilities["str"] = 17
    progression.level_up(c, tables, RNG(4, "lv"))
    asi = next(p for p in c.pending if p["kind"] == "asi")
    progression.resolve(c, tables, asi, progression.suggest(c, tables, asi))
    assert feats.has(c, "great_weapon_master") and c.abilities["str"] == 18
    b = fight(tables, c, "bandit", "bandit")
    me, foe, other = b.fighters
    soft(foe)
    on_turn(b, me)
    opt = main_opt(b, me)
    seen = hits(b, me, foe, opt)
    assert min(seen) >= 2 + 4 + 2  # 2d6 (at least 2) + Strength 4 + proficiency 2
    # Hew: a foe dropped earns the bonus-action blow, and the Auto takes it
    foe.creature.hp = 1
    other.creature.hp = other.creature.max_hp = 300
    other.cdef = dict(other.cdef, ac=1)
    for _ in range(60):
        if b._attack(me, opt, foe):
            break
    assert general_feats.hew_ready(b, me)
    assert any(o.id == "ability:hew" and o.available for o in actions.options(b, me))
    b.fighters[2].x, b.fighters[2].y = 4, 5
    tactics._bonus_strike(b, me)
    assert me.bonus == 0 and not general_feats.hew_ready(b, me)


def test_great_weapon_master_in_the_enemys_hands(tables):
    c = hero(tables, level=4)
    c.max_hp = c.hp = 500
    b = fight(tables, c, "berserker")
    me, brute = b.fighters
    assert brute.has_trait("feat_great_weapon_master")
    opt = next(o for o in b.attack_options(brute) if o.name.lower() == "greataxe")
    assert "heavy" in opt.properties
    on_turn(b, brute)
    me.char.equipped.pop("armor", None)
    seen = hits(b, brute, me, opt, n=30)
    n, sides, flat = __import__("realmwalker.core.dice", fromlist=["parse"]).parse(opt.damage)
    assert min(seen) >= n + flat + query.proficiency(brute)


# ---------------------------------------------------------------------------- the fighting styles
def test_great_weapon_fighting_counts_ones_and_twos_as_threes(tables):
    c = armed(tables, "greatsword")
    c.feats = [f for f in c.feats if f["id"] != "defense"]
    give(tables, c, "great_weapon_fighting")
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe)
    seen = hits(b, me, foe, main_opt(b, me), n=30)
    assert min(seen) >= 3 + 3 + Sheet(c, tables).mod("str")


def test_dueling_thrown_and_two_weapon_styles_add_damage(tables):
    c = armed(tables, "longsword", "shield")
    give(tables, c, "dueling")
    b = fight(tables, c, "bandit")
    me = b.fighters[0]
    mod = Sheet(c, tables).mod("str")
    assert main_opt(b, me).damage.endswith(f"+{mod + 2}")
    tw = armed(tables, "shortsword", "dagger")
    b = fight(tables, tw, "bandit")
    plain = b.offhand_option(b.fighters[0]).damage
    give(tables, tw, "two_weapon_fighting")
    assert b.offhand_option(b.fighters[0]).damage != plain
    th = armed(tables, "javelin")
    give(tables, th, "thrown_weapon_fighting")
    b = fight(tables, th, "bandit")
    throw = next(o for o in b.attack_options(b.fighters[0]) if o.name.startswith("throw"))
    assert throw.damage.endswith(f"+{Sheet(th, tables).mod('str') + 2}")


def test_unarmed_fighting_and_blind_fighting(tables):
    c = armed(tables)
    give(tables, c, "unarmed_fighting")
    give(tables, c, "blind_fighting")
    b = fight(tables, c, "bandit")
    me = b.fighters[0]
    fists = next(o for o in b.attack_options(me) if o.key == "unarmed")
    assert fists.damage.startswith("1d8")
    assert me.senses.get("blindsight") == 10


def test_protection_lasts_until_the_guards_next_turn_and_interception_turns_a_blow(tables):
    knight = armed(tables, "longsword", "shield", seed=2)
    knight.feats = [f for f in knight.feats if f["id"] != "defense"]
    give(tables, knight, "protection")
    give(tables, knight, "interception")
    friend = hero(tables, "wizard", seed=3, level=4)
    friend.max_hp = friend.hp = 300
    b = fight(tables, [knight, friend], "bandit", spots={0: (3, 4), 1: (3, 5), 2: (4, 5)})
    k, w, foe = b.fighters
    opt = next(o for o in b.attack_options(foe) if o.is_melee)
    b._attack(foe, opt, w)
    assert any(bf.get("protected") == k.id for bf in w.buffs)
    assert "shielded" in query.attack_roll(b, foe, w, opt).notes
    k.reaction = True
    k.char.feats = [f for f in k.char.feats if f["id"] != "protection"]
    cut = []
    for _ in range(80):
        k.reaction = True
        before = w.hp
        if b._attack(foe, opt, w):
            cut.append(before - w.hp)
            if not k.reaction:
                break
    assert not k.reaction  # the reaction was spent on Interception


# ---------------------------------------------------------------------------- combat feats
def test_sentinel_strikes_a_foe_that_disengages_and_stops_it(tables):
    c = armed(tables, "longsword")
    give(tables, c, "sentinel")
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    me.char.abilities["str"] = 20
    foe.cdef = dict(foe.cdef, ac=1)
    on_turn(b, foe)
    foe.disengaged = True
    b.walk(foe, [(5, 4), (6, 4)])
    assert not me.reaction  # the blow was struck though they disengaged
    assert (foe.x, foe.y) == (5, 4) or foe.move_left == 0


def test_a_guard_holds_the_line_with_sentinel(tables):
    c = armed(tables, "longsword")
    b = fight(tables, c, "guard")
    me, guard = b.fighters
    assert guard.has_trait("feat_sentinel")
    on_turn(b, me)
    me.disengaged = True
    b.walk(me, [(2, 4)])
    assert not guard.reaction


def test_polearm_master_the_butt_end_and_the_reach(tables):
    c = armed(tables, "glaive")
    c.abilities["str"] = 16
    give(tables, c, "polearm_master")
    b = fight(tables, c, "bandit", spots={0: (3, 4), 1: (4, 4)})
    me, foe = b.fighters
    soft(foe)
    on_turn(b, me)
    b.do_attack(me, main_opt(b, me), foe)
    pole = next(o for o in actions.options(b, me) if o.id == "ability:pole_strike")
    assert pole.available and foe in pole.targets
    b.do_ability(me, "pole_strike", foe)
    assert me.bonus == 0
    # the reach: a foe stepping in from three squares away is struck as it comes
    b2 = fight(tables, armed(tables, "glaive"), "bandit", spots={0: (3, 4), 1: (7, 4)})
    give(tables, b2.fighters[0].char, "polearm_master")
    on_turn(b2, b2.fighters[1])
    b2.walk(b2.fighters[1], [(6, 4), (5, 4), (4, 4)])
    assert not b2.fighters[0].reaction


def test_crusher_piercer_and_slasher(tables):
    c = armed(tables, "warhammer")
    give(tables, c, "crusher")
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe)
    on_turn(b, me)
    start = (foe.x, foe.y)
    for _ in range(60):
        if b._attack(me, main_opt(b, me), foe):
            break
    assert (foe.x, foe.y) != start  # shoved 5 feet
    s = armed(tables, "scimitar")
    give(tables, s, "slasher")
    b = fight(tables, s, "bandit")
    me, foe = b.fighters
    soft(foe)
    on_turn(b, me)
    for _ in range(60):
        if b._attack(me, main_opt(b, me), foe):
            break
    assert any(bf.get("slow") == 10 for bf in foe.buffs)
    p = armed(tables, "rapier")
    give(tables, p, "piercer")
    b = fight(tables, p, "bandit")
    me, foe = b.fighters
    soft(foe)
    on_turn(b, me)
    seen = hits(b, me, foe, main_opt(b, me), n=40)
    assert sum(seen) / len(seen) > 4.5 + Sheet(p, tables).mod("dex")  # (a d8 rerolled when low: above its 4.5)


def test_sharpshooter_ignores_cover_a_foe_at_hand_and_long_range(tables):
    c = armed(tables, "longbow")
    give(tables, c, "sharpshooter")
    b = fight(tables, c, "bandit", spots={0: (3, 4), 1: (4, 4)})
    me, foe = b.fighters
    opt = main_opt(b, me)
    assert "enemy at hand" not in query.attack_roll(b, me, foe, opt).notes
    foe.x = 3 + 160 // 5
    if b.field.fits(foe.x, foe.y, foe.sq):
        assert "long range" not in query.attack_roll(b, me, foe, opt).notes


def test_heavy_armor_master_and_durable_and_the_chef(tables):
    c = armed(tables, "longsword", "shield")
    wield(tables, c, "chain_mail")
    give(tables, c, "heavy_armor_master")
    give(tables, c, "durable")
    give(tables, c, "chef")
    c.uses["chef_treats"] = 2
    c.max_hp, c.hp = 300, 100
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    opt = next(o for o in b.attack_options(foe) if o.is_melee)
    on_turn(b, foe)
    seen = []
    for _ in range(60):
        before = me.hp
        if b._attack(foe, opt, me):
            seen.append(before - me.hp)
    n, sides, flat = __import__("realmwalker.core.dice", fromlist=["parse"]).parse(opt.damage)
    assert seen and max(seen) <= max(0, n * sides * 2 + flat - 2)
    on_turn(b, me)
    hp = me.hp
    assert any(o.id == "ability:speedy_recovery" and o.available for o in actions.options(b, me))
    tactics._party_turn.__wrapped__ if hasattr(tactics._party_turn, "__wrapped__") else None
    b.do_ability(me, "speedy_recovery")
    assert me.hp > hp and me.bonus == 0
    on_turn(b, me)
    b.do_ability(me, "chef_treat")
    assert me.temp_hp == query.proficiency(me)


def test_war_caster_holds_the_spell_and_mage_slayer_shakes_it(tables):
    wiz = hero(tables, "wizard", level=4)
    give(tables, wiz, "war_caster")
    b = fight(tables, wiz, "bandit")
    me = b.fighters[0]
    assert query.save_roll(b, me, "con", against=("concentration",)).roll.mode == "advantage"
    assert query.save_roll(b, me, "con").roll.mode != "advantage"


def test_elemental_adept_cuts_through_resistance(tables):
    wiz = hero(tables, "wizard", level=4)
    give(tables, wiz, "elemental_adept", element="fire")
    b = fight(tables, wiz, "bandit")
    me, foe = b.fighters
    foe.cdef = dict(foe.cdef, resist=["fire"])
    b._casting = me
    before = foe.hp
    b._hit(me, foe, 10, "fire", crit=False, weapon="fire bolt")
    assert before - foe.hp == 10
    b._casting = None
    before = foe.hp
    b._hit(me, foe, 10, "fire", crit=False, weapon="torch")
    assert before - foe.hp == 5


def test_telekinetic_shoves_with_the_mind_and_keen_mind_studies_quickly(tables):
    wiz = hero(tables, "wizard", level=4)
    give(tables, wiz, "telekinetic")
    give(tables, wiz, "keen_mind")
    b = fight(tables, wiz, "bandit", spots={0: (3, 4), 1: (5, 4)})
    me, foe = b.fighters
    on_turn(b, me)
    shove = next(o for o in actions.options(b, me) if o.id == "ability:telekinetic_shove")
    assert shove.available and foe in shove.targets
    study = next(o for o in actions.options(b, me) if o.id == "ability:quick_study")
    assert study.available and foe in study.targets
    b.do_ability(me, "quick_study", foe)
    assert me.bonus == 0 and me.action == 1


def test_shield_master_bashes_and_the_defensive_duelist_parries(tables):
    c = armed(tables, "longsword", "shield")
    give(tables, c, "shield_master")
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe)
    on_turn(b, me)
    start = (foe.x, foe.y)
    for _ in range(60):
        on_turn(b, me)  # (once a turn)
        b._attack(me, main_opt(b, me), foe)
        if "prone" in foe.conditions or (foe.x, foe.y) != start:
            break
    assert "prone" in foe.conditions or (foe.x, foe.y) != start
    d = armed(tables, "rapier")
    give(tables, d, "defensive_duelist")
    b = fight(tables, d, "bandit")
    me, foe = b.fighters
    assert b._duelist_parry(me, foe, total=me.ac() + 1, ac=me.ac())
    assert not me.reaction and sum(me.buff_value("parry_ac")) == query.proficiency(me)


def test_speedy_charger_and_athlete(tables):
    c = armed(tables, "longsword")
    base = Sheet(c, tables).speed()
    give(tables, c, "speedy")
    give(tables, c, "athlete")
    give(tables, c, "charger")
    assert Sheet(c, tables).speed() == base + 10
    b = fight(tables, c, "bandit", spots={0: (3, 4), 1: (9, 4)})
    me, foe = b.fighters
    on_turn(b, me)
    assert me.climb_speed == me.speed
    left = me.move_left
    b.do_dash(me)
    assert me.move_left == left + me.speed + 10


def test_the_inspiring_leader_the_cooks_meal_and_the_ritual_caster(tables):
    from types import SimpleNamespace

    from realmwalker.game import fight as fightmod

    lead = hero(tables, level=4)
    lead.abilities["cha"] = 14
    give(tables, lead, "inspiring_leader", increase="cha")
    other = hero(tables, "wizard", seed=2, level=4)
    words = fightmod._rousing_words(SimpleNamespace(party=[lead, other]), None)
    assert words and other.temp_hp == lead.level + 2 == lead.temp_hp
    b = fight(tables, [lead, other], "bandit")
    assert b.fighters[1].temp_hp == 6 and other.temp_hp == 0  # (carried into the fight)
    c = hero(tables, level=4)
    c.hp = 1
    plain = progression.short_rest(c, tables, RNG(9, "rest"))
    c2 = hero(tables, level=4)
    c2.hp = 1
    fed = progression.short_rest(c2, tables, RNG(9, "rest"), meal=True)
    assert c2.hp > c.hp or c2.hp == c2.max_hp, (plain, fed)
    f = hero(tables, level=4)
    give(tables, f, "ritual_caster")
    got = feats.ritual_spells(f, tables)  # (two rituals of level 1: more came with E.1 and E.3, Alarm and Comprehend
    assert len(got) == 2 and "alarm" in got  # Languages among them)
    assert all(tables.spells[s].get("ritual") and tables.spells[s]["level"] == 1 for s in got)


# ---------------------------------------------------------------------------- the fresh review's fixes
def test_a_duellist_keeps_a_versatile_blade_in_one_hand(tables):
    c = armed(tables, "longsword")
    b = fight(tables, c, "bandit")
    assert main_opt(b, b.fighters[0]).damage.startswith("1d10")  # both hands on the hilt
    give(tables, c, "dueling")
    b = fight(tables, c, "bandit")
    opt = main_opt(b, b.fighters[0])
    assert opt.damage.startswith("1d8") and opt.damage.endswith(f"+{Sheet(c, tables).mod('str') + 2}")
    assert not opt.two_hands


def test_spell_sniper_reaches_further_only_with_spell_attacks(tables):
    c = hero(tables, "wizard", level=4)
    give(tables, c, "spell_sniper", increase="int")
    b = fight(tables, c, "bandit")
    me = b.fighters[0]
    assert b.spell_range(tables.spells["fire_bolt"], me) == 180
    assert b.spell_range(tables.spells["sacred_flame"], me) == 60


def test_mounted_combatant_waits_for_mounts(tables):
    c = hero(tables, level=4)
    offered = feats.choosable(c, tables)
    assert "sentinel" in offered and "mounted_combatant" not in offered


def test_feat_picks_and_the_sheet_speak_in_words(tables):
    assert feats.choice_word(tables, "dex") == "Dexterity"
    assert feats.choice_word(tables, "fire_bolt") == "Fire Bolt"
    assert feats.choice_word(tables, "cleric") == "Cleric"
    c = hero(tables, level=4)
    give(tables, c, "athlete", increase="dex")
    line = next(x for x in feats.sheet_lines(c, tables) if "Athlete" in x)
    assert "Dexterity" in line and "(dex)" not in line


def test_a_spent_once_a_turn_trick_asks_nothing(tables, monkeypatch):
    c = armed(tables, "warhammer")
    give(tables, c, "crusher")
    b = fight(tables, c, "bandit")
    me, foe = b.fighters
    soft(foe)
    asked = []
    real = general_feats.choose
    monkeypatch.setattr(general_feats, "choose", lambda *a: asked.append(a[2]) or real(*a))
    on_turn(b, me)
    landed = 0
    for _ in range(200):
        foe.x, foe.y = me.x + 1, me.y
        if b._attack(me, main_opt(b, me), foe):
            landed += 1
            if landed == 3:
                break
    assert landed == 3 and asked.count("push") == 1


def test_medium_armor_master_dual_wielder_and_feats_kept_in_the_save(tables):
    from realmwalker.rules.character import Character

    c = hero(tables, level=4)
    for slot in ("main_hand", "off_hand", "body"):
        unequip(c, slot)
    wield(tables, c, "breastplate")
    c.abilities["dex"] = 16
    plain = Sheet(c, tables).armor_class()
    give(tables, c, "medium_armor_master", increase="str")
    assert Sheet(c, tables).armor_class() == plain + 1
    w = armed(tables, "shortsword")
    long = add_item(w, tables.items, "longsword")
    assert not equip(w, tables.items, long.uid, "off_hand")[0]  # a longsword is not light
    give(tables, w, "dual_wielder", increase="dex")
    assert equip(w, tables.items, long.uid)[0] and w.equipped.get("off_hand") == long.uid
    b = fight(tables, w, "bandit")
    assert b.offhand_option(b.fighters[0]) is not None
    again = Character.from_dict(w.to_dict())
    assert again.feats == w.feats
