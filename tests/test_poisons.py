"""Steel & Shadows Part C.1: the DMG 2024 poisons (pp. 90-91) - coated on blades, thrown as vials, harvested from the
slain, brewed by a Poisoner; the Dagger of Venom, the Periapt of Proof against Poison and the Potion of Poison."""

from realmwalker.core.rng import RNG
from realmwalker.game import camp, care, divining, poisoning, treasure
from realmwalker.rules import poisons, tactics
from realmwalker.rules.combat import PARTY
from realmwalker.rules.creatures import spawn
from realmwalker.rules.engine import actions, query
from realmwalker.rules.inventory import add_item
from tests.test_gear import fight_with, game, person, tables, world  # noqa: F401 (fixtures)
from tests.test_gear_2024 import first, my_turn

POISONS = ("assassins_blood", "burnt_othur_fumes", "carrion_crawler_mucus", "essence_of_ether", "lolths_sting",
           "malice", "midnight_tears", "oil_of_taggit", "pale_tincture", "purple_worm_poison", "serpent_venom",
           "torpor", "truth_serum", "wyvern_poison")


def setup(tables, poison, foe="bandit"):
    c = person(tables)
    add_item(c, tables.items, poison)
    b = fight_with(tables, c, foe)
    me = b.side(PARTY)[0]
    them = [f for f in b.fighters if f.side != PARTY][0]
    them.x, them.y = me.x + 1, me.y
    them.cdef = dict(them.cdef, ac=1)
    them.hp = them.max_hp
    my_turn(b, me)
    return c, b, me, them


def buff(f, key):
    return next((bf[key] for bf in f.buffs if key in bf), None)


def fail_saves(b, monkeypatch, by=10):
    def no(*a, **k):
        b.__dict__["failed_by"] = by
        return False
    monkeypatch.setattr(b, "_save", no)


def strike(b, me, them, kinds=("slashing", "piercing")):
    blade = next(o for o in b.attack_options(me) if o.damage_type in kinds)
    for _ in range(60):
        if b._attack(me, blade, them):
            return True
    return False


# ---------------------------------------------------------------------------- the data
def test_the_books_poisons_are_all_here_with_their_numbers(tables):
    book = {"assassins_blood": (10, 15000), "burnt_othur_fumes": (13, 50000), "carrion_crawler_mucus": (13, 20000),
            "essence_of_ether": (15, 30000), "lolths_sting": (13, 20000), "malice": (15, 25000),
            "midnight_tears": (17, 150000), "oil_of_taggit": (13, 40000), "pale_tincture": (16, 25000),
            "purple_worm_poison": (21, 200000), "serpent_venom": (11, 20000), "torpor": (15, 60000),
            "truth_serum": (11, 15000), "wyvern_poison": (14, 120000)}
    for pid, (dc, value) in book.items():
        d = tables.items.get(pid)
        assert d["poison"]["dc"] == dc and d["value"] == value, pid
        assert d.get("how") and d.get("description"), pid
        kind = d["poison"]["kind"]
        if kind in poisons.COATS:
            assert d["use"]["coat"], pid
        if kind == "inhaled":
            spell = tables.spells[d["use"]["throw"]]
            assert spell["effects"] == poisons.battle_ops(d["poison"]), pid  # (the vial's spell is the record's)


# ---------------------------------------------------------------------------- in a fight
def test_serpent_venom_on_a_blade_goes_into_the_first_cut(tables, monkeypatch):
    c, b, me, them = setup(tables, "serpent_venom")
    them.hp = them.creature.hp = 300
    them.creature.max_hp = 300
    coat = b.throw_value(first(c, "serpent_venom"))
    opt = next(o for o in actions.options(b, me) if o.kind == "item" and o.value == coat)
    assert opt.cost == "bonus"
    assert b.do_cast(me, coat, None)
    assert buff(me, "poisoned_blade") == "serpent_venom"
    fail_saves(b, monkeypatch)
    hurt = []
    real = b._hit
    b._hit = lambda att, t, amount, dtype, **k: hurt.append((dtype, amount)) or real(att, t, amount, dtype, **k)
    assert strike(b, me, them)
    assert not me.buff_value("poisoned_blade")
    assert any(d == "poison" and a >= 3 for d, a in hurt)  # (3d6, a failed save)


def test_carrion_crawler_mucus_paralyzes_and_is_shaken_off(tables, monkeypatch):
    c, b, me, them = setup(tables, "carrion_crawler_mucus")
    them.hp = them.creature.hp = them.creature.max_hp = 300
    assert b.do_cast(me, b.throw_value(first(c, "carrion_crawler_mucus")), None)
    fail_saves(b, monkeypatch)
    assert strike(b, me, them, kinds=("slashing", "piercing", "bludgeoning"))
    assert "poisoned" in them.conditions and "paralyzed" in them.conditions
    assert any(e["cond"] == "poisoned" for e in them.save_ends)
    from realmwalker.rules.engine import durations

    durations.remove(them, "poisoned")
    assert "paralyzed" not in them.conditions  # (Paralyzed while Poisoned in this way)


def test_lolths_sting_knocks_out_only_on_a_bad_failure(tables, monkeypatch):
    c, b, me, them = setup(tables, "lolths_sting")
    them.hp = them.creature.hp = them.creature.max_hp = 300
    assert b.do_cast(me, b.throw_value(first(c, "lolths_sting")), None)
    fail_saves(b, monkeypatch, by=2)
    assert strike(b, me, them)
    assert "poisoned" in them.conditions and "unconscious" not in them.conditions
    add_item(c, tables.items, "lolths_sting")
    me.bonus = 1
    assert b.do_cast(me, b.throw_value(first(c, "lolths_sting")), None)
    fail_saves(b, monkeypatch, by=6)
    assert strike(b, me, them)
    assert "unconscious" in them.conditions
    b._hit(me, them, 1, "slashing", crit=False, weapon="dagger")
    assert "unconscious" not in them.conditions and "poisoned" in them.conditions  # (a blow wakes them)


def test_malice_thrown_blinds_and_othur_fumes_choke(tables, monkeypatch):
    c, b, me, them = setup(tables, "malice")
    them.x, them.y = me.x + 3, me.y
    fail_saves(b, monkeypatch)
    assert b.do_cast(me, b.throw_value(first(c, "malice")), None, point=(them.x, them.y))
    assert "blinded" in them.conditions and "poisoned" in them.conditions
    c, b, me, them = setup(tables, "burnt_othur_fumes")
    them.hp = them.creature.hp = them.creature.max_hp = 300
    them.x, them.y = me.x + 3, me.y
    fail_saves(b, monkeypatch)
    assert b.do_cast(me, b.throw_value(first(c, "burnt_othur_fumes")), None, point=(them.x, them.y))
    assert buff(them, "fumes") == 13
    before = them.hp
    poisons.turn_start(b, them)
    assert them.hp < before  # (a failure: 1d6 more)
    monkeypatch.setattr(b, "_save", lambda *a, **k: True)
    for _ in range(3):
        poisons.turn_start(b, them)
    assert not them.buff_value("fumes")  # (three saves: the smoke is out)


def test_the_auto_coats_its_blade_before_striking(tables):
    c, b, me, them = setup(tables, "serpent_venom")
    me.auto = True
    them.hp = them.creature.hp = them.creature.max_hp = 40
    tactics.take_turn(b, me)
    assert not any(it.def_id == "serpent_venom" for it in c.inventory)


def test_a_poisoners_dose_carries_its_brewers_dc(game, tables, monkeypatch):
    c = game.leader
    c.feats.append({"id": "poisoner", "choices": {"increase": "dex"}})
    add_item(c, tables.items, "poisoners_kit")
    c.money = 10000
    ids = [x[0] for x in camp.crafts(game)]
    assert "poisoner_brew" in ids
    camp.make(game, "poisoner_brew")
    dose = first(c, "poisoners_dose")
    sheet = game.sheet(c)
    assert dose.qty == sheet.proficiency and c.money == 5000
    assert f"dc:{8 + sheet.mod('dex') + sheet.proficiency}" in dose.tags
    b = fight_with(tables, c, "bandit")
    me = b.side(PARTY)[0]
    them = [f for f in b.fighters if f.side != PARTY][0]
    them.x, them.y = me.x + 1, me.y
    them.cdef = dict(them.cdef, ac=1)
    my_turn(b, me)
    assert b.do_cast(me, b.throw_value(dose), None)
    assert buff(me, "poison_dc") == 8 + sheet.mod("dex") + sheet.proficiency


# ---------------------------------------------------------------------------- the book's items
def test_the_periapt_wards_off_poison(game, tables):
    it = treasure.make_listed(game, "periapt_of_proof_against_poison", "", "rare", RNG(1, "p"))
    assert it is not None and it.magic["title"] == "Periapt of Proof against Poison"
    c = game.leader
    c.inventory.append(it)
    it.uid = c.new_uid()
    from realmwalker.rules import magic

    c.equipped["neck"] = it.uid
    c.attuned = [it.uid]
    b = fight_with(tables, c, "bandit")
    me = b.side(PARTY)[0]
    assert query.damage_taken(me, 10, "poison")[0] == 0
    assert query.condition_immune(me, "poisoned")
    assert "proof_against_poison" in magic.traits(c)


def test_the_dagger_of_venom_wakes_its_venom_once_a_day(game, tables, monkeypatch):
    it = treasure.make_listed(game, "dagger_of_venom", "", "rare", RNG(2, "d"))
    assert it is not None and it.def_id == "dagger" and it.magic["title"] == "Dagger of Venom"
    c = person(tables)
    it.uid = c.new_uid()
    c.inventory.append(it)
    c.equipped["main_hand"] = it.uid
    b = fight_with(tables, c, "bandit")
    me = b.side(PARTY)[0]
    them = [f for f in b.fighters if f.side != PARTY][0]
    them.x, them.y = me.x + 1, me.y
    them.cdef = dict(them.cdef, ac=1)
    them.hp = them.creature.hp = them.creature.max_hp = 300
    my_turn(b, me)
    assert b.do_cast(me, f"charge:{it.uid}:dagger_venom", None)
    assert buff(me, "poisoned_blade") == "venom_dagger"
    fail_saves(b, monkeypatch)
    assert strike(b, me, them)
    assert "poisoned" in them.conditions
    assert not b.do_cast(me, f"charge:{it.uid}:dagger_venom", None)  # (spent until dawn)


def test_a_potion_of_poison_passes_for_healing_until_drunk_or_found_out(game, tables):
    it = treasure.make_listed(game, "potion_of_poison", "", "uncommon", RNG(3, "p"))
    assert it.def_id == "potion_healing" and poisons.masked(it) == "potion_of_poison"
    assert tables.items.name(it, False) == "potion of healing"
    c = game.leader
    it.uid = c.new_uid()
    c.inventory.append(it)
    c.hp = c.max_hp - 5
    before = c.hp
    words = " ".join(care.drink_potion(game, c, it))
    assert "potion of poison" in words and c.hp < before
    it2 = treasure.make_listed(game, "potion_of_poison", "", "uncommon", RNG(4, "p"))
    it2.uid = c.new_uid()
    c.inventory.append(it2)
    words = " ".join(divining._sense_poison(game, c, tables.spells["detect_poison_and_disease"]))
    assert "potion of poison" in words and it2.def_id == "potion_of_poison" and not poisons.masked(it2)


# ---------------------------------------------------------------------------- outside a fight
def test_venom_is_harvested_from_the_slain_with_a_kit(game, tables, monkeypatch):
    c = game.leader
    spider = spawn(tables, "giant_spider", RNG(5, "s"), 1)
    snake = spawn(tables, "venomous_snake", RNG(5, "s"), 2)
    wolf = spawn(tables, "wolf", RNG(5, "s"), 3)
    assert poisoning.harvestable(game, [spider, snake, wolf]) == []  # (no kit)
    add_item(c, tables.items, "poisoners_kit")
    assert poisoning.harvestable(game, [spider, snake, wolf]) == [spider, snake]

    class Roll:
        natural = total = 20

    monkeypatch.setattr(poisoning.dice, "d20", lambda *a, **k: Roll())
    monkeypatch.setattr(poisoning, "HARVEST_DC", 15)
    items, msgs = poisoning.harvest(game, [spider, snake])
    ids = sorted(i.def_id for i in items)
    assert ids == ["harvested_venom", "serpent_venom"]
    venom = next(i for i in items if i.def_id == "harvested_venom")
    rec = poisons.of_item(tables, venom)
    assert rec["damage"] == "2d6" and rec["creature"] == "giant_spider" and "giant spider" in venom.name

    class Bad:
        natural = total = 1

    monkeypatch.setattr(poisoning.dice, "d20", lambda *a, **k: Bad())
    c.hp = c.max_hp
    items, msgs = poisoning.harvest(game, [spider])
    assert not items and "pricks" in " ".join(msgs)


def test_the_poison_on_a_blade_has_its_card(tables, monkeypatch):
    from realmwalker.rules import describe

    c, b, me, them = setup(tables, "serpent_venom")
    assert b.do_cast(me, b.throw_value(first(c, "serpent_venom")), None)
    cards = [s.card for s in describe.statuses(me, b)]
    card = next(x for x in cards if x.title.startswith("Poisoned blade"))
    assert "serpent venom" in card.title and "3d6" in card.lines[0] and "DC 11" in card.lines[0]
    them.buffs.append({"fumes": 13, "fumes_dice": "1d6", "fumes_successes": 3, "source": "fumes:x"})
    assert any(s.card.title == "Choking on fumes" for s in describe.statuses(them, b))


def test_from_the_review_people_give_no_venom_and_vials_linger(game, tables, monkeypatch):
    add_item(game.leader, tables.items, "poisoners_kit")
    killer = spawn(tables, "assassin", RNG(6, "a"), 1)
    assert poisoning.harvestable(game, [killer]) == []  # (an assassin's venom is in a vial, not in glands)
    c, b, me, them = setup(tables, "essence_of_ether")
    me.hidden = 0
    fail_saves(b, monkeypatch)
    friend_hit = me
    them.x, them.y = me.x + 1, me.y
    assert b.do_cast(me, b.throw_value(first(c, "essence_of_ether")), None, point=(me.x, me.y))
    assert "poisoned" in friend_hit.conditions and friend_hit.__dict__.get("poison_hours") == 8.0
    c2, b2, me2, them2 = setup(tables, "serpent_venom")
    me2.hidden = 14
    assert b2.do_cast(me2, b2.throw_value(first(c2, "serpent_venom")), None)
    assert me2.hidden == 14  # (smearing a blade gives no one away)
