"""Steel & Shadows Part D.1: the fighter's and rogue's magic items of the DMG 2024 (Vorpal Sword, Luck Blade, Defender,
Dancing Sword, the Swords of Sharpness, Wounding, Answering and Vengeance, the Scimitar of Speed, the Executioner's
Axe, the Mace of Terror, Vicious Weapons, Weapons of Warning, the Rod of Lordly Might, the Veteran's Cane, the Gloves
of Thievery, the Boots of False Tracks and the Amulet of Proof against Detection and Location), each in a real fight
or where it works on the road."""

import pytest

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.game import dungeon, fight, glamour, magic_items, treasure
from realmwalker.rules import magic, tactics
from realmwalker.rules.combat import PARTY
from realmwalker.rules.engine import actions, query
from realmwalker.rules.engine.handlers import arms
from tests.test_gear import fight_with, game, person, tables, world  # noqa: F401 (fixtures)
from tests.test_gear_2024 import my_turn

BOOK = {  # slug: (rarity, attunement, base ids it may be, title)
    "vicious_weapon": ("rare", False, None, "Vicious Weapon"),
    "executioner_s_axe": ("very_rare", False, {"battleaxe", "greataxe", "halberd", "handaxe"}, "Executioner's Axe"),
    "sword_of_wounding": ("rare", True, {"glaive", "greatsword", "longsword", "rapier", "scimitar", "shortsword"},
                          "Sword of Wounding"),
    "sword_of_sharpness": ("very_rare", True, {"glaive", "greatsword", "longsword", "scimitar"}, "Sword of Sharpness"),
    "vorpal_sword": ("legendary", True, {"glaive", "greatsword", "longsword", "scimitar"}, "Vorpal Sword"),
    "sword_of_answering": ("legendary", True, {"longsword"}, "Sword of Answering"),
    "sword_of_vengeance": ("uncommon", True, {"glaive", "greatsword", "longsword", "rapier", "scimitar", "shortsword"},
                           "Sword of Vengeance"),
    "scimitar_of_speed": ("very_rare", True, {"scimitar"}, "Scimitar of Speed"),
    "dancing_sword": ("very_rare", True, {"greatsword", "longsword", "rapier", "scimitar", "shortsword"},
                      "Dancing Sword"),
    "defender": ("legendary", True, None, "Defender"),
    "luck_blade": ("legendary", True, {"glaive", "greatsword", "longsword", "rapier", "scimitar", "sickle",
                                       "shortsword"}, "Luck Blade"),
    "mace_of_terror": ("rare", True, {"mace"}, "Mace of Terror"),
    "rod_of_lordly_might": ("legendary", True, {"mace"}, "Rod of Lordly Might"),
    "veteran_s_cane": ("common", False, {"longsword"}, "Veteran's Cane"),
    "weapon_of_warning": ("uncommon", True, None, "Weapon of Warning"),
    "gloves_of_thievery": ("uncommon", False, {"leather_gloves"}, "Gloves of Thievery"),
    "boots_of_false_tracks": ("common", True, {"boots"}, "Boots of False Tracks"),
    "amulet_of_proof_against_detection_and_location": ("uncommon", True, {"amulet"},
                                                       "Amulet of Proof against Detection and Location"),
}


def make(game, slug, seed=1):
    rarity = BOOK[slug][0]
    it = treasure.make_listed(game, slug, "", rarity, RNG(seed, slug))
    assert it is not None, slug
    return it


def give(c, it, slot="main_hand"):
    it.uid = c.new_uid()
    c.inventory.append(it)
    if slot:
        c.equipped[slot] = it.uid
    if it.magic.get("attune"):
        c.attuned.append(it.uid)
    return it


def armed(game, tables, slug, foe="bandit", seed=1, hp=300, base=None):
    """A fighter with the item in hand, a foe beside them that is easy to hit and hard to kill, and their turn."""
    c = person(tables)
    it = make(game, slug, seed)
    if base:
        it.def_id = base
    give(c, it)
    b = fight_with(tables, c, foe)
    me = b.side(PARTY)[0]
    them = [f for f in b.fighters if f.side != PARTY][0]
    them.x, them.y = me.x + 1, me.y
    them.cdef = dict(them.cdef, ac=1)
    them.hp = them.creature.hp = them.creature.max_hp = hp
    my_turn(b, me)
    return c, it, b, me, them


def blow(b, me, it):
    return next(o for o in b.attack_options(me) if o.item_uid == it.uid)


def hit(b, me, them, opt, tries=80):
    for _ in range(tries):
        if b._attack(me, opt, them):
            return True
    return False


def fail_saves(b, monkeypatch):
    def no(*a, **k):
        b.__dict__["failed_by"] = 10
        return False
    monkeypatch.setattr(b, "_save", no)


def twenties(monkeypatch):
    real = dice.d20

    def d20(*a, **k):
        r = real(*a, **k)
        r.natural = 20
        return r
    monkeypatch.setattr(dice, "d20", d20)


# ---------------------------------------------------------------------------- the book's items, made
def test_every_item_is_made_as_the_book_has_it(game, tables):
    for slug, (rarity, attune, bases, title) in BOOK.items():
        for seed in (1, 2, 3):
            it = make(game, slug, seed)
            assert it.magic["title"] == title, slug
            assert bool(it.magic.get("attune")) == attune, slug
            if bases:
                assert it.def_id in bases, (slug, it.def_id)
            it.magic["identified"] = True
            words = " ".join(magic_items.describe(game, it))
            assert title in words and len(words) > 60, slug
    luck = make(game, "luck_blade")
    wish = next(p for p in luck.magic["props"] if p.get("spell") == "wish")
    assert 1 <= wish["value"] <= 3 and wish["left"] == wish["value"] and "dice" not in wish
    assert make(game, "sword_of_vengeance").magic["cursed"]
    assert make(game, "veteran_s_cane").magic["form"] == "cane"


def test_they_are_in_the_treasure_tables(game, tables):
    rows = {row[2] for rows in treasure.spec(game)["tables"].values() for row in rows}
    assert set(BOOK) <= rows


# ---------------------------------------------------------------------------- blows
def test_a_vicious_weapon_bites_deeper(game, tables):
    c, it, b, me, them = armed(game, tables, "vicious_weapon", base="dagger")
    _, _, b2, me2, them2 = armed(game, tables, "vicious_weapon", base="dagger")
    me2.char.item(me2.char.equipped["main_hand"]).magic["props"] = []
    hits = lost = hits2 = lost2 = 0
    for _ in range(30):
        before = them.hp
        if b._attack(me, blow(b, me, it), them):
            hits, lost = hits + 1, lost + before - them.hp
        before = them2.hp
        if b2._attack(me2, next(o for o in b2.attack_options(me2) if o.item_uid is not None), them2):
            hits2, lost2 = hits2 + 1, lost2 + before - them2.hp
    assert hits and hits2 and lost / hits >= lost2 / hits2 + 5  # (2d6 more: seven on the average)


def test_the_executioners_axe_feeds_on_people(game, tables):
    c, it, b, me, them = armed(game, tables, "executioner_s_axe")
    assert blow(b, me, it).bonus >= 1 + 2  # (+1 and proficiency at the least)
    assert hit(b, me, them, blow(b, me, it))
    assert me.temp_hp >= 2


def test_a_sword_of_wounding_keeps_the_wound_open(game, tables, monkeypatch):
    c, it, b, me, them = armed(game, tables, "sword_of_wounding")
    fail_saves(b, monkeypatch)
    assert hit(b, me, them, blow(b, me, it))
    assert them.no_heal and arms.wounded(them)
    monkeypatch.undo()
    them.buffs = [bf for bf in them.buffs if bf.get("source") != "wounding"]
    assert not them.no_heal


def test_a_sword_of_sharpness_tires_on_a_twenty_and_cleaves_things(game, tables, monkeypatch):
    c, it, b, me, them = armed(game, tables, "sword_of_sharpness")
    twenties(monkeypatch)
    before = them.hp
    assert b._attack(me, blow(b, me, it), them)
    assert them.__dict__.get("exhaustion") == 1 and before - them.hp >= 14
    assert query.d20_penalty(them) == -2
    monkeypatch.undo()
    assert arms.sharp(me, blow(b, me, it))


def test_the_vorpal_sword_takes_a_head(game, tables, monkeypatch):
    c, it, b, me, them = armed(game, tables, "vorpal_sword")
    assert blow(b, me, it).bonus >= 3 + 2
    twenties(monkeypatch)
    assert b._attack(me, blow(b, me, it), them)
    assert them.state == "dead"
    assert any(e.get("kind") == "behead" for e in b.events)
    # A creature with no head to lose takes the 30 more instead.
    c, it, b, me, them = armed(game, tables, "vorpal_sword", seed=2)
    them.cdef = dict(them.cdef, kind="ooze")
    before = them.hp
    assert b._attack(me, blow(b, me, it), them)
    assert them.state != "dead" and before - them.hp >= 30
    assert not arms.has_head(them)


def test_the_vorpal_sword_cuts_through_resistance(game, tables):
    c, it, b, me, them = armed(game, tables, "vorpal_sword")
    b.__dict__["_wielded"] = (me, blow(b, me, it))
    assert b._ignores_resist(me, "slashing") and not b._ignores_resist(me, "fire")


def test_the_sword_of_answering_strikes_back(game, tables):
    c, it, b, me, them = armed(game, tables, "sword_of_answering")
    me.hp = 400
    hp = them.hp
    claws = next(o for o in b.attack_options(them) if o.is_melee)
    for _ in range(60):
        if b._attack(them, claws, me):
            break
    assert not me.reaction and them.hp < hp


def test_the_sword_of_vengeance_holds_its_bearer_to_one_foe(game, tables, monkeypatch):
    c, it, b, me, them = armed(game, tables, "sword_of_vengeance", foe="bandit")
    other = make(game, "vicious_weapon")
    give(c, other, slot=None)
    from realmwalker.rules.combat import Battle, Env
    from tests.test_gear import open_field
    from realmwalker.rules.creatures import spawn

    two = spawn(tables, "bandit", RNG(5, "x"), 9)
    b = Battle(tables, [c], [them.creature, two], Env(), RNG(3, "battle"), field=open_field(tables))
    b.start("Two of them.")
    me = b.side(PARTY)[0]
    a, z = [f for f in b.fighters if f.side != PARTY]
    a.x, a.y, z.x, z.y = me.x + 1, me.y, me.x, me.y + 1
    my_turn(b, me)
    fail_saves(b, monkeypatch)
    me.hp = 400
    knife = next(o for o in b.attack_options(a) if o.is_melee)
    for _ in range(60):
        if b._attack(a, knife, me):
            break
    assert arms.vengeful(b, me) is a
    sword = blow(b, me, it)
    assert b.targets_for(me, sword) == [a]
    assert b.attack_problem(me, sword, z)
    assert tactics._targets(b, me) == [a]
    # Another weapon turns in the hand.
    c.equipped["main_hand"] = other.uid
    r = query.attack_roll(b, me, a, next(o for o in b.attack_options(me) if o.item_uid == other.uid))
    assert r.disadvantage
    # Lifting the curse leaves a +1 sword.
    magic_items.lift_curse(it)
    assert arms.trait_prop(it, "sword_of_vengeance") is None and magic.item_bonus(it) == 1


def test_the_scimitar_of_speed_strikes_with_the_bonus_action(game, tables):
    c, it, b, me, them = armed(game, tables, "scimitar_of_speed")
    opt = next(o for o in actions.options(b, me, only=("ability",)) if o.value == "speed_strike")
    assert opt.available and them in opt.targets
    events = len(b.events)
    b.do_ability(me, "speed_strike", them)
    assert me.bonus == 0 and me.action == 1
    assert any(e.get("kind") == "attack" for e in b.events[events:])


def test_the_dancing_sword_dances_four_blows_and_comes_home(game, tables):
    c, it, b, me, them = armed(game, tables, "dancing_sword")
    them.x, them.y = me.x + 5, me.y  # (twenty feet away: out of the hand's reach)
    assert them in arms.toss_targets(b, me)
    b.do_ability(me, "dance_toss", them)
    tok = arms.dancer(b, me)
    assert tok is not None and tok.blows == 1 and max(abs(tok.x - them.x), abs(tok.y - them.y)) <= 1
    assert not blow(b, me, it).available  # (it is in the air)
    for n in (2, 3, 4):
        my_turn(b, me)
        b.do_ability(me, "dance_strike", them)
    assert arms.dancer(b, me) is None and blow(b, me, it).available


def test_the_defender_guards_when_pressed(game, tables):
    c, it, b, me, them = armed(game, tables, "defender")
    full = blow(b, me, it).bonus
    assert any(bf.get("defender") for bf in me.buffs)
    shift = arms.defender_shift(me, it)
    assert 1 <= shift <= 3
    assert blow(b, me, it).bonus == full  # (the guard was set as the turn began: the option already carries it)
    me.buffs = [bf for bf in me.buffs if not bf.get("defender")]
    assert blow(b, me, it).bonus == full + shift
    them.x, them.y = me.x + 8, me.y
    my_turn(b, me)
    assert not any(bf.get("defender") for bf in me.buffs)


def test_the_luck_blade_turns_a_failed_save_once_a_day(game, tables):
    c, it, b, me, them = armed(game, tables, "luck_blade")
    assert arms.ready(it, "luck_blade")
    for _ in range(40):
        b._save(me, "wis", 21)  # (a hard save: the luck is spent on the first failure)
        if not arms.ready(it, "luck_blade"):
            break
    assert not arms.ready(it, "luck_blade")
    magic.dawn([it], RNG(1, "dawn"))
    assert arms.ready(it, "luck_blade")
    wish = next(p for p in it.magic["props"] if p.get("spell") == "wish")
    n = wish["left"]
    assert magic.charges_left(wish) == n
    magic.spend_charge(wish, RNG(1, "w"))
    assert magic.charges_left(wish) == 0  # (once a day)
    magic.dawn([it], RNG(1, "dawn"))
    assert wish["left"] == n - 1  # (no charge ever comes back)


def test_the_mace_of_terror_sends_them_running(game, tables, monkeypatch):
    c, it, b, me, them = armed(game, tables, "mace_of_terror")
    fail_saves(b, monkeypatch)
    assert b.do_cast(me, f"charge:{it.uid}:mace_terror", None)
    assert "frightened" in them.conditions and them.cond_ends["frightened"].get("terror")
    gap = b.gap(me, them)
    b.order = [them.id] + [x for x in b.order if x != them.id]
    b.turn = 0
    b.turn_started = True
    b._start_of_turn(them)
    tactics.take_turn(b, them)
    assert b.gap(me, them) > gap and not any(e.get("kind") == "attack" and e.get("by") == them.id for e in b.events)


def test_the_rod_of_lordly_might(game, tables, monkeypatch):
    c, it, b, me, them = armed(game, tables, "rod_of_lordly_might")
    assert blow(b, me, it).damage_type == "bludgeoning"
    b.do_ability(me, "rod_flame")
    assert it.magic["form"] == "flame"
    opt = blow(b, me, it)
    assert opt.damage_type == "slashing" and opt.bonus >= 3 + 2
    fail_saves(b, monkeypatch)
    assert hit(b, me, them, opt)
    assert "paralyzed" in them.conditions and not arms.ready(it, "rod_paralyze")
    assert hit(b, me, them, opt)
    assert not arms.ready(it, "rod_drain")
    terrify = next(p for p in it.magic["props"] if p.get("spell") == "rod_terrify")
    assert magic.charges_left(terrify) == 1
    monkeypatch.undo()
    magic.dawn([it], RNG(2, "dawn"))
    assert arms.ready(it, "rod_paralyze") and arms.ready(it, "rod_drain")
    # The ram and the needle, on the road.
    game.leader.inventory.append(it)
    assert dungeon.helps(game, "force")[0] == 10
    assert game.bearings_bonus() >= 5


def test_the_veterans_cane_hides_a_sword(game, tables):
    c, it, b, me, them = armed(game, tables, "veteran_s_cane")
    assert blow(b, me, it).name.lower() == "club"
    assert tactics._arms_bonus(b, me)
    assert it.magic["form"] == "sword" and blow(b, me, it).name.lower() == "longsword"


def test_the_auto_lights_the_rods_blade(game, tables):
    c, it, b, me, them = armed(game, tables, "rod_of_lordly_might")
    me.auto = True
    tactics.take_turn(b, me)
    assert it.magic.get("form") == "flame"


def test_a_weapon_of_warning_wakes_and_readies(game, tables):
    c, it, b, me, them = armed(game, tables, "weapon_of_warning")
    assert me.id in arms.warned(b) and them.id not in arms.warned(b)
    give(game.leader, make(game, "weapon_of_warning"), slot=None)
    assert fight._warning_weapon(game)


def test_gloves_of_thievery(game, tables):
    gloves = make(game, "gloves_of_thievery")
    c = game.leader
    before = game.sheet(c).skill_bonus("sleight_of_hand")
    give(c, gloves, slot="hands")
    assert game.sheet(c).skill_bonus("sleight_of_hand") == before + 5
    assert glamour.hidden_thing(game, gloves) and glamour.hidden_thing(game, gloves, robbers=True)


def test_the_amulet_hides_from_divination(game, tables):
    c, it, b, me, them = armed(game, tables, "vorpal_sword")
    amulet = give(c, make(game, "amulet_of_proof_against_detection_and_location"), slot=None)
    assert arms.hidden_from_divination(me) and not b.thinks(me)
    assert tables.spells["mind_spike"]["school"] == "divination"
    assert me not in b.spell_targets(them, "mind_spike")  # (a foe's divination finds nobody to aim at)
    assert me in b.spell_targets(them, "fire_bolt") or "fire_bolt" not in tables.spells
    c.attuned.remove(amulet.uid)
    assert not arms.hidden_from_divination(me)


def test_boots_of_false_tracks_are_bound_to_be_read_wrong(game, tables):
    boots = give(game.leader, make(game, "boots_of_false_tracks"), slot=None)
    assert magic.flag(game.leader, "false_tracks")
    assert boots.magic["attune"]


@pytest.mark.parametrize("slug", ["vorpal_sword", "dancing_sword", "scimitar_of_speed", "rod_of_lordly_might",
                                  "defender", "luck_blade"])
def test_a_companion_on_auto_fights_with_it(game, tables, slug):
    c, it, b, me, them = armed(game, tables, slug, hp=40)
    me.auto = True
    for _ in range(12):
        if b.outcome is not None:
            break
        f = b.current
        if f is None:
            break
        tactics.take_turn(b, f)
        if b.outcome is None and b.current is f:
            b.end_turn()
        nxt = b.current
        if nxt is not None and not b.turn_started:
            b._start_of_turn(nxt)
    assert me.state != "dead" or them.state != "dead"
