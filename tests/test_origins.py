"""Blades & Backgrounds part B: origins in the 2024 form - species and lineages, the sixteen backgrounds and their
increases, origin feats, languages, the ways of making ability scores - and what each does in a real fight."""

import pytest

from realmwalker.core.rng import RNG
from realmwalker.rules import feats, progression
from realmwalker.rules import spells as spellrules
from realmwalker.rules.character import Sheet
from realmwalker.rules.combat import Battle, Env
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import actions, query, traits
from realmwalker.world.tables import Tables

SPECIES = ("human", "elf", "dwarf", "halfling", "orc")


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


def builder(tables, race="human", cls="fighter", bg="soldier", seed=1):
    b = CharacterBuilder(tables, RNG(seed, "origin"))
    b.set_class(cls)
    b.set_background(bg)
    b.set_race(race)
    return b


def fight(tables, chars, *foes, seed=1, spots=None):
    rng = RNG(seed, "foes")
    crs = [spawn(tables, d, rng, i + 1) for i, d in enumerate(foes)]
    spots = spots or {i: (3, 3 + i) for i in range(len(chars))} | {len(chars) + i: (4, 3 + i) for i in range(len(crs))}
    b = Battle(tables, list(chars), crs, Env(), RNG(seed, "battle"), spots=spots)
    b.start("Test fight.")
    return b


def turn_of(b, f):
    b.order = [f.id] + [x for x in b.order if x != f.id]
    b.turn, b.turn_started = 0, True
    b._start_of_turn(f)


# ---------------------------------------------------------------------------- making a character
@pytest.mark.parametrize("race", SPECIES)
def test_every_species_and_background_makes_a_character(tables, race):
    for bg in tables.backgrounds:
        b = builder(tables, race, "wizard" if bg == "sage" else "fighter", bg)
        assert b.problems() == []
        c = b.build()
        bgd = tables.backgrounds[bg]
        assert c.species == race and c.race == race
        assert c.feats and c.feats[0]["id"] == bgd["feat"]["id"]
        assert set(bgd["skills"]) <= set(c.skills)
        assert c.languages[0] == "Common" and len(c.languages) >= 3
        raised = [a for a in c.abilities if c.abilities[a] > c.base_scores[a]]
        assert set(raised) <= set(bgd["abilities"]) and sum(c.abilities[a] - c.base_scores[a] for a in raised) == 3
        assert c.hp == c.max_hp >= 1


def test_a_human_takes_a_second_origin_feat_and_a_skill(tables):
    b = builder(tables, "human", bg="farmer")
    b.set_choice("versatile", "alert")
    c = b.build()
    assert [f["id"] for f in c.feats] == ["tough", "alert", "defense"]  # (and the fighter's style, a feat)
    assert c.choices["skillful"] in c.skills
    assert c.max_hp == tables.classes["fighter"]["hit_die"] + (c.abilities["con"] - 10) // 2 + 2


def test_an_elfs_lineage_changes_sight_and_speed(tables):
    b = builder(tables, "elf")
    b.set_choice("lineage", "drow")
    assert Sheet(b.build(), tables).darkvision == 120
    b.set_choice("lineage", "wood_elf")
    c = b.build()
    assert Sheet(c, tables).speed() == 35 and c.lineage == "wood_elf"
    assert c.choices["keen_senses"] in ("insight", "perception", "survival") and c.choices["keen_senses"] in c.skills


def test_the_ways_of_making_ability_scores(tables):
    b = builder(tables, cls="wizard", bg="sage")
    b.set_method("array")
    assert sorted(b.scores.values()) == [8, 10, 12, 13, 14, 15] and b.scores["int"] == 15
    b.swap_scores("int", "str")
    assert b.scores["str"] == 15 and b.problems() == []
    b.set_method("roll")
    assert all(3 <= v <= 18 for v in b.scores.values()) and b.problems() == []
    b.set_method("point_buy")
    assert b.points_left() == 0


def test_magic_initiate_and_its_spells(tables):
    b = builder(tables, "human", "fighter", "acolyte")  # Magic Initiate (Cleric)
    c = b.build()
    mi = next(f for f in c.feats if f["id"] == "magic_initiate")
    assert mi["choices"]["list"] == "cleric" and len(mi["choices"]["cantrips"]) == 2 and len(mi["choices"]["spell"]) == 1
    have = feats.innate_spells(c, tables)
    assert {sid for _, sid, _ in have} == set(mi["choices"]["cantrips"]) | set(mi["choices"]["spell"])
    spell = mi["choices"]["spell"][0]
    b2 = fight(tables, [c], "bandit")
    me, foe = b2.fighters
    turn_of(b2, me)
    value = f"innate:feat0:{spell}"
    opts = {sid: ok for sid, ok, _ in b2.spell_options(me)}
    assert opts.get(value)
    target = me if tables.spells[spell]["target"] in ("ally", "self") else foe
    assert b2.do_cast(me, value, target=target) or b2.do_cast(me, value, point=(foe.x, foe.y))
    assert c.uses[feats.innate_key("feat0", spell)] == 0
    assert not {sid: ok for sid, ok, _ in b2.spell_options(me)}[value]  # once a long rest
    progression.long_rest(c, tables, RNG(1, "rest"))
    assert c.uses[feats.innate_key("feat0", spell)] == 1


def test_every_skill_pick_is_one_tick_in_one_list(tables):
    """The Skills & tools step: a human (Skillful, Versatile Skilled) noble (Skilled) fighter ticks and unticks
    skills and tools; each goes to a pick that may take it, an emptied pick stays empty, nothing jumps."""
    b = builder(tables, "human", "fighter", "noble")
    b.set_choice("versatile", "skilled")
    pools = {p["id"]: p for p in b.skill_pools()}
    assert {"class", "species:skillful", "feat:background:skills", "feat:versatile:skills"} <= set(pools)
    assert b.picks_left() == 0 and b.problems() == []
    known = b.known_skills()
    assert len(known) == len(set(known))  # nothing twice
    # untick everything that was picked: every pick empty, and it stays so
    for p in b.skill_pools():
        for x in list(p["picked"]):
            assert b.unpick(x) == ""
    assert all(not p["picked"] for p in b.skill_pools())
    b._fix_skills()
    assert all(not p["picked"] for p in b.skill_pools()), "an emptied pick is not filled again behind the player"
    assert any("Skills & tools" in x for x in b.problems())
    # a granted skill cannot be unticked
    granted = tables.backgrounds["noble"]["skills"][0]
    assert b.unpick(granted) != "" and granted in b.known_skills()
    # tick: a fighter's skill goes to the calling first, others to Skillful, then to the feats; tools only to feats
    fighter = [s for s in tables.classes["fighter"]["skill_choices"] if s not in b.known_skills()]
    assert b.pick(fighter[0]) == "" and fighter[0] in b.class_skills
    assert b.pick("arcana") == "" and b.choices["skillful"] == "arcana"
    assert b.pick("lute") == "" and "lute" in b.known_tools()
    assert b.pick("arcana") != ""  # already had
    # fill the calling, then one more of its skills: one already chosen moves to a free pick to make room
    while len(b.class_skills) < b.skill_count():
        assert b.pick(next(s for s in tables.classes["fighter"]["skill_choices"] if s not in b.known_skills())) == ""
    extra = next(s for s in tables.classes["fighter"]["skill_choices"] if s not in b.known_skills())
    assert b.pick(extra) == "" and extra in b.known_skills()
    while b.picks_left():
        assert b.pick(next(s for s in tables.rules["skills"] if s not in b.known_skills())) == ""
    assert b.problems() == []
    c = b.build()
    assert set(b.known_skills()) <= set(c.skills) and "lute" in c.tools


def test_a_feat_can_be_chosen_on_the_origin_step(tables):
    b = builder(tables, "human", "fighter", "sage")
    slots = b.feat_slots()
    assert any(key == "cantrips" for _, _, key, _, _ in slots)
    src, fid, key, index, opts = next(s for s in slots if s[2] == "cantrips")
    other = next(o for o in opts if o not in b.feat_choices[src]["cantrips"])
    b.set_feat_slot(src, key, index, other)
    c = b.build()
    assert other in next(f for f in c.feats if f["id"] == "magic_initiate")["choices"]["cantrips"]


# ---------------------------------------------------------------------------- species in a fight
def test_brave_halflings_and_fey_elves_save_with_advantage(tables):
    hal = builder(tables, "halfling").build()
    elf = builder(tables, "elf").build()
    b = fight(tables, [hal, elf], "bandit")
    h, e = b.fighters[0], b.fighters[1]
    assert query.save_roll(b, h, "wis", against=("frightened",)).roll.mode == "advantage"
    assert query.save_roll(b, h, "wis").roll.mode != "advantage"
    assert query.save_roll(b, e, "wis", against=("charmed",)).roll.mode == "advantage"


def test_a_halfling_slips_through_a_bigger_foe(tables):
    hal = builder(tables, "halfling").build()
    hum = builder(tables, "human", seed=2).build()
    for who, ok in ((hal, True), (hum, False)):
        b = fight(tables, [who], "bandit", spots={0: (3, 4), 1: (4, 4)})
        me = b.fighters[0]
        turn_of(b, me)
        tree = b.move_tree(me)
        through = any(sq == (5, 4) and any(p == (4, 4) for p in (tree[sq].path if hasattr(tree[sq], "path") else []))
                      for sq in tree)
        assert ((4, 4) in tree or through) == ok or ok and (5, 4) in tree


def test_a_dwarf_feels_the_stone_and_an_orc_rushes(tables):
    dwarf = builder(tables, "dwarf").build()
    orc = builder(tables, "orc", seed=3).build()
    b = fight(tables, [dwarf, orc], "bandit")
    b.field.underground = True
    d, o = b.fighters[0], b.fighters[1]
    turn_of(b, d)
    assert actions.use(b, d, "stonecunning")
    assert d.senses.get("tremorsense") == 60 and dwarf.uses["stonecunning"] == 1
    turn_of(b, o)
    move = o.move_left
    assert actions.use(b, o, "adrenaline_rush")
    assert o.move_left == move + o.speed and o.temp_hp == query.proficiency(o) and o.bonus == 0


def test_the_auto_orc_rushes_in_when_nothing_is_in_reach(tables):
    orc = builder(tables, "orc", seed=4).build()
    orc.inventory = [i for i in orc.inventory if i.def_id not in ("spear", "shortbow", "arrows", "javelin")]
    b = fight(tables, [orc], "bandit", spots={0: (1, 4), 1: (13, 4)})
    me = b.fighters[0]
    me.auto = True
    turn_of(b, me)
    from realmwalker.rules import tactics

    tactics.take_turn(b, me)
    assert orc.uses["adrenaline_rush"] == query.proficiency(me) - 1 and me.temp_hp > 0


# ---------------------------------------------------------------------------- origin feats in a fight
def test_alert_savage_attacker_and_tavern_brawler(tables):
    c = builder(tables, "human", "fighter", "guard").build()  # Alert
    b = fight(tables, [c], "bandit")
    assert query.initiative_bonus(b.fighters[0]) == query.proficiency(b.fighters[0])
    s = builder(tables, "human", "fighter", "sailor").build()  # Tavern Brawler
    b = fight(tables, [s], "bandit")
    fists = next(o for o in b.attack_options(b.fighters[0]) if o.key == "unarmed")
    assert fists.damage.startswith("1d4")
    assert traits.has(b.fighters[0], "feat_tavern_brawler")
    sol = builder(tables, "human", "fighter", "soldier").build()
    b = fight(tables, [sol], "bandit")
    assert traits.has(b.fighters[0], "feat_savage_attacker")


def test_lucky_rolls_a_failed_save_again(tables):
    c = builder(tables, "human", "fighter", "merchant").build()
    assert c.uses["luck"] == 2
    b = fight(tables, [c], "bandit")
    me = b.fighters[0]
    for seed in range(40):
        b.rng = RNG(seed, "luck")
        if c.uses["luck"] <= 1:
            break
        b._save(me, "wis", 18)
    assert c.uses["luck"] <= 1


def test_a_healer_patches_a_friend_with_battle_medic(tables):
    medic = builder(tables, "human", "fighter", "hermit").build()
    friend = builder(tables, "human", "fighter", "soldier", seed=5).build()
    friend.hp = 2
    b = fight(tables, [medic, friend], "bandit", spots={0: (3, 4), 1: (3, 5), 2: (9, 4)})
    me = b.fighters[0]
    turn_of(b, me)
    from realmwalker.rules.inventory import add_item

    add_item(medic, tables.items, "healers_kit")  # (a hermit sets out with herbs; the kit is bought)
    dice_left = friend.hit_dice
    assert actions.use(b, me, "battle_medic")
    assert friend.hp > 2 and friend.hit_dice == dice_left - 1


def test_the_auto_casts_its_magic_initiate_spells(tables):
    used = 0
    for seed in range(4):
        c = builder(tables, "human", "fighter", "sage", seed=seed).build()  # Magic Initiate (Wizard)
        c.inventory = [i for i in c.inventory if tables.items.category(i) != "weapon"]
        c.equipped = {k: v for k, v in c.equipped.items() if k not in ("main_hand", "off_hand")}
        b = fight(tables, [c], "bandit", spots={0: (2, 4), 1: (8, 4)}, seed=seed)
        me = b.fighters[0]
        me.auto = True
        for _ in range(600):
            if b.outcome is not None:
                break
            b.step()
        used += sum(1 for e in b.events if e["kind"] == "cast" and e.get("by") == me.id)
    assert used > 0


def test_spells_need_no_class_for_innate_casting(tables):
    c = builder(tables, "elf", "fighter", "soldier").build()
    c.lineage = "high_elf"
    c.level = 5
    assert ("lineage", "misty_step", c.choices.get("lineage_ability") or "int") in feats.innate_spells(c, tables) or \
        any(sid == "misty_step" for _, sid, _ in feats.innate_spells(c, tables))
    assert not spellrules.is_caster(c, tables)


# ---------------------------------------------------------------------------- the fresh review's points
def test_versatile_never_repeats_the_backgrounds_feat_and_a_second_copy_picks_others(tables):
    b = builder(tables, "human", "fighter", "farmer")  # Tough
    assert "tough" not in b.choice_options("versatile")
    b = builder(tables, "human", "fighter", "charlatan")  # Skilled
    b.set_choice("versatile", "skilled")
    c = b.build()
    picks = [x for f in c.feats if f["id"] == "skilled" for x in f["choices"]["skills"]]
    assert len(picks) == 6 and len(set(picks)) == 6
    b = builder(tables, "human", "fighter", "acolyte")  # Magic Initiate (Cleric)
    b.set_choice("versatile", "magic_initiate")
    lists = [f["choices"]["list"] for f in b.build().feats if f["id"] == "magic_initiate"]
    assert len(lists) == 2 and lists[0] != lists[1]


def test_halfling_luck_saves_a_save_that_rolled_a_one(tables):
    hal = builder(tables, "halfling").build()
    b = fight(tables, [hal], "bandit")
    me = b.fighters[0]
    fails = sum(not b._save(me, "dex", 2, quiet=True) for _ in range(400))
    assert fails <= 4  # only two 1s in a row fail (1 in 400)


def test_savage_attacker_and_tavern_brawler_fire_in_a_fight(tables):
    sol = builder(tables, "human", "fighter", "soldier").build()
    b = fight(tables, [sol], "bandit")
    me, foe = b.fighters
    foe.creature.max_hp = foe.creature.hp = 300
    foe.cdef = dict(foe.cdef, ac=1)
    opt = next(o for o in b.attack_options(me) if o.key == "main")
    turn_of(b, me)
    b._attack(me, opt, foe)
    assert any("Savage Attacker" in r for rolls in b.rolls.values() for r in rolls) or \
        me.__dict__.get("mastery_used", {}).get("savage_attacker")
    sailor = builder(tables, "human", "fighter", "sailor").build()
    b = fight(tables, [sailor], "bandit", spots={0: (3, 4), 1: (4, 4)})
    me, foe = b.fighters
    foe.creature.max_hp = foe.creature.hp = 300
    foe.cdef = dict(foe.cdef, ac=1)
    fists = next(o for o in b.attack_options(me) if o.key == "unarmed")
    turn_of(b, me)
    for _ in range(20):
        b._attack(me, fists, foe)
        if (foe.x, foe.y) != (4, 4):
            break
    assert (foe.x, foe.y) == (5, 4)


def test_a_musicians_song_after_a_rest_inspires_the_others(tables):
    import copy

    from realmwalker.game import fight as fightmod
    from realmwalker.game.state import new_game
    from realmwalker.world.generator import WorldOptions
    from tests.worlds import cached_world

    bard = builder(tables, "human", "fighter", "entertainer").build()
    game = new_game(copy.deepcopy(cached_world(WorldOptions("Songland", 5, "small"), tables)), tables, bard)
    game.survival = False
    friend = builder(tables, "human", "fighter", "soldier", seed=8).build()
    friend.is_player = False
    game.party.append(friend)
    friend.uses.pop("heroic_inspiration", None)
    notes = fightmod._encouraging_song(game, None)
    assert notes and friend.uses.get("heroic_inspiration") == 1


def test_a_level_brings_luck_and_a_lineage_spell_at_once(tables):
    c = builder(tables, "elf", "fighter", "merchant").build()  # Lucky
    c.lineage = "high_elf"
    for _ in range(4):
        progression.level_up(c, tables, RNG(1, "lv"), auto=True)
    assert c.uses["luck"] == 3
    assert c.uses.get(feats.innate_key("lineage", "misty_step")) == 1
