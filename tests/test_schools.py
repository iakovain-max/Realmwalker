"""Schools & Domains part A: the Diviner and the Illusionist - Portent in fights and out of them, Expert Divination, The
Third Eye, Greater Portent; Improved Illusions, Phantasmal Creatures, Illusory Self, illusions on the battle mat and
Illusory Reality - each at work in a real fight, at a rest or on the sheet."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game.state import new_game
from realmwalker.world.generator import WorldOptions
from tests.worlds import cached_world
from realmwalker.rules import progression
from realmwalker.rules import spells as spellrules
from realmwalker.rules.character import Sheet
from realmwalker.rules.engine import actions
from realmwalker.rules.engine import resources as res
from realmwalker.rules.engine.handlers import schools
from realmwalker.world.tables import Tables

from tests.test_feats import fight, hero, on_turn, soft


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture
def game(tables):
    g = new_game(copy.deepcopy(cached_world(WorldOptions("Schools", 7, "small"), tables)), tables)
    g.survival = False
    return g


def school(tables, level, sub="divination", seed=1):
    """A wizard of this school, chosen at level 3 as a player chooses it."""
    c = hero(tables, "wizard", level=1, seed=seed)
    for _ in range(level - 1):
        progression.level_up(c, tables, RNG(seed, "lv"))
        c.pending = [p for p in c.pending if p["kind"] not in ("asi", "boon")]
        pick = next((p for p in c.pending if p["kind"] == "subclass"), None)
        if pick is not None:
            progression.resolve(c, tables, pick, sub)
        progression.auto_resolve(c, tables)
    res.fill(c, tables)
    return c


# ---------------------------------------------------------------------------- the paths
def test_the_two_schools_are_chosen_with_their_savants(tables):
    d = school(tables, 3, "divination")
    assert d.subclass == "divination" and {"divination_savant", "portent"} <= set(d.features)
    book = d.spells["spellbook"]
    assert sum(1 for s in book if tables.spells[s].get("school") == "divination" and tables.spells[s]["level"]) >= 2
    i = school(tables, 3, "illusion")
    assert i.subclass == "illusion" and "improved_illusions" in i.features
    assert "minor_illusion" in i.spells["cantrips"]  # (beyond the count)
    count = tables.classes["wizard"]["spellcasting"]["cantrips"][2]
    assert len(i.spells["cantrips"]) == count + 1
    progression.level_up(i, tables, RNG(5, "lv"))  # (and it stays beyond the count at the next level)
    progression.auto_resolve(i, tables)
    assert len(i.spells["cantrips"]) == tables.classes["wizard"]["spellcasting"]["cantrips"][3] + 1


def test_portent_dice_come_with_a_long_rest_three_from_fourteen(tables):
    d = school(tables, 3)
    notes = progression.long_rest(d, tables, RNG(2))
    assert len(d.spells["portent"]) == 2 and any("dreams of what is to come" in n for n in notes)
    g = school(tables, 14)
    progression.long_rest(g, tables, RNG(3))
    assert len(g.spells["portent"]) == 3
    plain = school(tables, 3, "evocation")
    progression.long_rest(plain, tables, RNG(2))
    assert "portent" not in plain.spells


# ---------------------------------------------------------------------------- Portent in a fight
def test_portent_makes_a_foe_fail_its_save_against_the_party(tables):
    d = school(tables, 3)
    d.spells["portent"] = [2, 19]
    b = fight(tables, d, "bandit")
    me, foe = b.side("party")[0], b.side("foe")[0]
    on_turn(b, me)
    b.__dict__["_casting"] = "test"  # (a save against the party's spell)
    ok = b._save(foe, "wis", 11)  # (a fair save: it could go either way)
    b.__dict__.pop("_casting")
    assert not ok and d.spells["portent"] == [19]  # (the 2 laid in its place; the 19 kept)
    assert any("saw this coming" in m for m, _ in b.log[-6:])
    # once a turn: the 19 is not used for a second roll this turn
    me.hp = me.max_hp
    before = list(d.spells["portent"])
    b._save(me, "con", 18)
    assert d.spells["portent"] == before


def test_portent_turns_a_foes_blow_on_a_hurt_friend(tables):
    d = school(tables, 3)
    d.spells["portent"] = [3]
    b = fight(tables, d, "bandit")
    me, foe = b.side("party")[0], b.side("foe")[0]
    me.hp = max(1, me.max_hp // 3)
    on_turn(b, foe)
    soft(foe)
    opt = b.attack_options(foe)[0]
    before = me.hp
    assert not b._attack(foe, opt, me)  # (a 3 does not hit)
    assert me.hp == before and d.spells["portent"] == []


def test_portent_saves_a_dying_friend(tables):
    d = school(tables, 3)
    friend = hero(tables, "fighter", level=3, seed=4)
    d.spells["portent"] = [20]
    b = fight(tables, [d, friend], "bandit")
    f2 = b.side("party")[1]
    f2.hp, f2.state = 0, "down"
    f2.death_saves = [0, 1]
    b._death_save(f2)
    assert f2.hp == 1 and d.spells["portent"] == []


def test_portent_out_of_a_fight_on_a_hard_check(tables, game):
    d = school(tables, 3)
    d.spells["portent"] = [18, 4]
    game.party.append(d)
    from realmwalker.game import camp

    ok, line = camp.check(game, "athletics", 20, tag="climb")
    assert "foretold by" in line and d.spells["portent"] == [4]


# ---------------------------------------------------------------------------- Expert Divination, the Third Eye
def test_expert_divination_gives_a_lower_slot_back(tables):
    d = school(tables, 6)
    d.spells["slots_used"] = [2, 1, 0] + [0] * 6
    assert "level 1 slot comes back" in schools.slot_back(d, 2)
    assert d.spells["slots_used"][0] == 1
    assert schools.slot_back(d, 1) == ""  # (a first-level slot gives nothing back)


def test_the_third_eye_opens_and_closes(tables):
    d = school(tables, 10)
    dark = Sheet(d, tables).darkvision
    b = fight(tables, d, "bandit")
    me = b.side("party")[0]
    on_turn(b, me)
    assert actions.use(b, me, "third_eye_dark")
    assert Sheet(d, tables).darkvision == 120 > dark or dark >= 120
    assert actions.problem(b, me, actions.find(me, "third_eye_unseen"))  # (used; and nobody unseen)
    progression.short_rest(d, tables, RNG(1))
    assert schools.eye(d) == "" and d.uses["third_eye"] == 1


# ---------------------------------------------------------------------------- the Illusionist
def test_illusory_self_turns_a_hit_once_then_for_a_slot(tables):
    i = school(tables, 10, "illusion")
    b = fight(tables, i, "bandit")
    me, foe = b.side("party")[0], b.side("foe")[0]
    soft(foe)
    foe.cdef = dict(foe.cdef)
    me.ac = lambda *a, **k: 1  # (every blow would land)
    i.spells["slots_used"] = list(spellrules.slots_total(i, tables)) + [0] * 9  # (no Shield to cast)
    opt = b.attack_options(foe)[0]
    on_turn(b, foe)
    me.reaction = True
    assert not b._attack(foe, opt, me) and i.uses["illusory_self"] == 0 and not me.reaction
    progression.short_rest(i, tables, RNG(1))
    assert i.uses["illusory_self"] == 1


def test_phantasmal_creatures_come_spectral_at_half_hit_points(tables):
    i = school(tables, 6, "illusion")
    from realmwalker.rules.inventory import add_item

    add_item(i, tables.items, "gilded_acorn")  # (the phantom still needs its acorn)
    assert "summon_beast" in spellrules.always_prepared(i, tables)
    assert spellrules.free_cast(i, tables, "summon_beast") == "phantasm"
    b = fight(tables, i, "bandit")
    me = b.side("party")[0]
    on_turn(b, me)
    used = list(i.spells.get("slots_used") or [0] * 9)
    assert b.do_cast(me, "summon_beast", point=(me.x + 1, me.y))
    beast = next(f for f in b.fighters if f.bond and f.bond.get("spell") == "summon_beast")
    assert beast.bond.get("spectral") and (i.spells.get("slots_used") or [0] * 9) == used
    whole = int(__import__("realmwalker.rules.allies", fromlist=["x"]).summon_def(
        tables, "bestial_spirit", 2, beast.bond["form"], 0, 0)["hp"])
    assert beast.max_hp == max(1, whole // 2)
    assert spellrules.free_cast(i, tables, "summon_beast") is None  # (once a long rest)
    progression.long_rest(i, tables, RNG(1))
    assert spellrules.free_cast(i, tables, "summon_beast") == "phantasm"


# ---------------------------------------------------------------------------- illusions on the battle mat
def image_fight(tables, level=3, sub="illusion"):
    """An illusionist at (3, 4) and a bandit archer ten squares east (5, 14 apart in feet: 50)."""
    w = school(tables, level, sub)
    b = fight(tables, w, "bandit_archer", spots={0: (3, 4), 1: (13, 4)})
    return w, b, b.side("party")[0], b.side("foe")[0]


def test_minor_illusion_hides_the_caster_from_the_archer_until_it_is_studied(tables):
    w, b, me, foe = image_fight(tables)
    assert b.can_see(foe, me)
    on_turn(b, me)
    from realmwalker.rules.combat import cast_kind

    assert cast_kind(me, tables.spells["minor_illusion"]) == "bonus"  # (Improved Illusions)
    assert b.do_cast(me, "minor_illusion", point=(4, 4))
    assert me.bonus == 0 and me.action > 0
    z = next(z for z in b.zones if z.kind == "illusion")
    assert z.cells == {(4, 4)} and b.can_see(me, foe)  # (the caster's side knows it for what it is)
    assert not b.can_see(foe, me)  # (the archer sees a crate where the wizard stood a moment ago)
    on_turn(b, foe)
    z.dc = 30
    b.do_search(foe)
    assert foe.id not in z.seen and not b.can_see(foe, me)  # (it looks hard, and sees a crate)
    on_turn(b, foe)
    z.dc = 1
    b.do_search(foe)
    assert foe.id in z.seen and b.can_see(foe, me)


def test_walking_into_an_image_shows_it_up(tables):
    w, b, me, foe = image_fight(tables)
    on_turn(b, me)
    b.do_cast(me, "minor_illusion", point=(4, 4))
    z = next(z for z in b.zones if z.kind == "illusion")
    foe.x, foe.y = 4, 4
    b._zones_on(foe, start=False)
    assert foe.id in z.seen


def test_an_image_never_covers_a_creature_and_the_auto_values_it(tables):
    w, b, me, foe = image_fight(tables)
    from realmwalker.rules.engine import estimates

    assert estimates.image_worth(b, me, [(me.x, me.y)]) == 0.0
    assert estimates.image_worth(b, me, [(4, 4)]) > 0.5  # (between the archer and the wizard)


def test_improved_illusions_reach_farther_and_need_no_words(tables):
    w, b, me, foe = image_fight(tables)
    assert b.spell_range(tables.spells["silent_image"], me) == 120
    plain, b2, me2, _ = image_fight(tables, sub="evocation")
    assert b2.spell_range(tables.spells["silent_image"], me2) == 60


def test_illusory_reality_makes_the_image_real_for_a_minute(tables):
    w, b, me, foe = image_fight(tables, level=14)
    on_turn(b, me)
    assert actions.problem(b, me, actions.find(me, "illusory_reality"))  # (no image yet)
    assert b.do_cast(me, "silent_image", point=(7, 4))
    z = next(z for z in b.zones if z.kind == "illusion")
    assert z.slotted
    on_turn(b, me)
    assert actions.use(b, me, "illusory_reality")
    assert z.real == 10 and all(b.field.name(*sq) in ("ruin_wall", "bridge") for sq in z.was)
    walls = [sq for sq in z.was if b.field.name(*sq) == "ruin_wall"]
    assert walls and not any(b.field.passable(*sq) or b.field.climb[sq] for sq in walls)  # (it stops feet)
    assert not z.opaque  # (a real thing is terrain now, not a picture)
    assert actions.problem(b, me, actions.find(me, "illusory_reality"))  # (once a casting)
    for _ in range(10):
        on_turn(b, me)
    assert z.real == 0 and not z.was


# ---------------------------------------------------------------------------- the Auto, the enemy, the cards
def test_the_card_shows_the_foretold_rolls_and_the_open_eye(tables):
    from realmwalker.rules import describe

    d = school(tables, 10)
    d.spells["portent"] = [17, 3]
    schools.open_eye(d, "dark")
    b = fight(tables, d, "bandit")
    ids = {s.id: s for s in describe.statuses(b.side("party")[0], b)}
    assert "Foretold: 17, 3" == ids["portent"].card.title and "third_eye" in ids
    assert ids["portent"].card.icon == "status/portent"


def test_the_auto_illusionist_lays_an_image_between_itself_and_the_archers(tables):
    from realmwalker.rules import tactics

    w, b, me, foe = image_fight(tables, level=5)
    me.auto = True
    on_turn(b, me)
    tactics.take_turn(b, me)
    assert any(z.kind == "illusion" for z in b.zones)


def test_a_foe_who_sees_nobody_studies_the_image(tables):
    from realmwalker.rules import tactics

    w, b, me, foe = image_fight(tables)
    on_turn(b, me)
    b.do_cast(me, "minor_illusion", point=(4, 4))
    z = next(z for z in b.zones if z.kind == "illusion")
    assert not b.can_see(foe, me)
    z.dc = 1
    on_turn(b, foe)
    tactics.take_turn(b, foe)
    assert foe.id in z.seen


def test_those_who_know_an_image_shoot_and_cast_through_it(tables):
    w, b, me, foe = image_fight(tables)
    on_turn(b, me)
    b.do_cast(me, "minor_illusion", point=(4, 4))
    z = next(z for z in b.zones if z.kind == "illusion")
    bow = next(o for o in b.attack_options(foe) if o.kind == "ranged")
    assert b.in_reach(foe, bow, me) == (False, "no clear line")  # (fooled: a crate is in the way)
    z.seen.add(foe.id)
    assert b.in_reach(foe, bow, me)[0]  # (seen through: the arrow flies through the picture)
    assert foe in b.spell_targets(me, "fire_bolt") and b.can_see_point(me, foe.x, foe.y)  # (its own side)
    from realmwalker.rules import grid

    assert b.solid_field().cover((3, 4, 1), foe.space) != grid.TOTAL  # (a blast meets no cover in a picture)


def test_the_phantom_or_a_slot_for_the_whole_creature(tables):
    i = school(tables, 6, "illusion")
    assert spellrules.free_cast(i, tables, "summon_beast") == "phantasm"
    assert spellrules.free_cast(i, tables, "summon_beast", 2) is None  # (a slot chosen: the whole creature)


def test_the_spell_card_says_a_bonus_action_and_the_longer_reach(tables):
    from realmwalker.rules import describe

    w, b, me, foe = image_fight(tables)
    lines = " ".join(describe.spell(tables, "minor_illusion", b=b, f=me).lines)
    assert "a bonus action" in lines and "90 ft" in lines
