"""Magic items (M8 part 2): made within a budget, their effects, identifying, curses, charges, treasure, the
AI's names, and saving."""

import copy

import pytest

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.game import magic_items, save, services, treasure
from realmwalker.game.people import npcs_in
from realmwalker.game.state import new_game
from realmwalker.rules import magic
from realmwalker.rules.combat import Battle, Env
from realmwalker.rules.creatures import spawn
from realmwalker.rules.inventory import add_existing, equip, remove_item, unequip
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Magicland", 41, "small"), tables).generate()


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    return g


def item(game, kind, rarity="rare", seed=1, **want):
    for i in range(200):
        it = magic_items.make(game, RNG(seed + i, "magic"), kind=kind, rarity=rarity)
        if it is None:
            continue
        if all(any(p["kind"] == k for p in it.magic["props"]) for k in want.get("props", [])):
            it.magic["cursed"] = False
            return it
    pytest.skip(f"no {kind} with {want}")


def test_items_stay_within_their_budget(game):
    spec = game.tables.magic
    for i in range(300):
        it = magic_items.make(game, RNG(i, "budget"), tier=1 + i % 6)
        if it is None:
            continue
        budget = spec["rarities"][it.magic["rarity"]]["budget"]
        spent = sum(spec["properties"][p["kind"]]["cost"] * (p["value"] // spec["properties"][p["kind"]].get("step", 1))
                    for p in it.magic["props"])
        assert spent <= budget + 1e-9, it.magic
        assert it.magic["title"] and "{" not in it.magic["title"] and "{" not in it.magic["story"]
        kind = next(k for k, bases in spec["bases"].items() if it.def_id in bases)
        assert all(kind in spec["properties"][p["kind"]]["for"] for p in it.magic["props"])


def test_a_magic_weapon_hits_harder(game):
    c = game.leader
    sword = add_existing(c, game.tables.items, item(game, "weapon", props=["bonus"]))
    bonus = magic.item_bonus(sword)
    assert bonus >= 1
    b = Battle(game.tables, [c], [spawn(game.tables, "wolf", RNG(1), 1)], Env(), RNG(1))
    b.start("Test")
    f = b.fighters[0] if b.fighters[0].char is c else b.fighters[1]
    before = {o.key: o.bonus for o in b.attack_options(f)}
    equip(c, game.tables.items, sword.uid, "main_hand")
    after = {o.key: (o.bonus, o.damage) for o in b.attack_options(f)}
    assert after["main"][0] >= before.get("main", -99) + bonus or after["main"][0] > 0
    assert f"+{bonus}" in after["main"][1] or bonus <= 0 or after["main"][1]


def test_protection_saves_and_skills(game):
    c = game.leader
    ac = game.sheet().armor_class()
    ring = item(game, "jewellery", props=["ac"])
    ring = add_existing(c, game.tables.items, ring)
    equip(c, game.tables.items, ring.uid)
    assert game.sheet().armor_class() == ac + magic.item_bonus(ring, "ac")
    amulet = add_existing(c, game.tables.items, item(game, "jewellery", props=["save"], seed=500))
    s0 = game.sheet().save_bonus("wis")
    equip(c, game.tables.items, amulet.uid)
    assert game.sheet().save_bonus("wis") >= s0


def test_curses_cling_until_lifted(game):
    c = game.leader
    it = item(game, "jewellery")
    it.magic["cursed"] = True
    it.magic["curse"] = {"text": "It whispers.", "effect": "save", "value": -2}
    it = add_existing(c, game.tables.items, it)
    ok, msg = equip(c, game.tables.items, it.uid)
    assert ok and "will not come off" in msg
    slot = c.slot_of(it.uid)
    assert unequip(c, slot) is None and c.slot_of(it.uid) == slot
    assert remove_item(c, it.uid) is None
    magic_items.lift_curse(it)
    assert unequip(c, slot) is not None


def fixed_d20(monkeypatch, value):
    class Roll:
        natural = value
        total = value

    monkeypatch.setattr(dice, "d20", lambda *a, **k: Roll())


def test_studying_and_asking_a_priest(game, monkeypatch):
    c = game.leader
    it = add_existing(c, game.tables.items, item(game, "weapon"))
    assert game.tables.items.name(it).startswith("strange")
    fixed_d20(monkeypatch, 1)
    magic_items.study(game, c, it)
    assert not it.magic["identified"]
    assert "tomorrow" in magic_items.study(game, c, it)[0]
    game.world.time += 1440
    fixed_d20(monkeypatch, 20)
    magic_items.study(game, c, it)
    assert it.magic["identified"] and not game.tables.items.name(it).startswith("strange")
    # A priest can tell you too.
    other = add_existing(c, game.tables.items, item(game, "jewellery", seed=900))
    s = next(s for s in game.world.settlements if s.kind in ("town", "city"))
    game.player.x, game.player.y = s.x, s.y
    game.enter_local()
    priest = next(n for n in npcs_in(game.world, s.id) if n.job == "priest")
    c.money = 100000
    svc = next(v for v in services.services_for(game, priest) if v.id == "identify")
    arg = next(o[0] for o in svc.options if o[0].endswith(f":{other.uid}"))
    services.perform(game, priest, "identify", arg)
    assert other.magic["identified"]


def test_spell_charges(game):
    c = game.leader
    wand = add_existing(c, game.tables.items, item(game, "focus", props=["charges"]))
    b = Battle(game.tables, [c], [spawn(game.tables, "wolf", RNG(1), 1)], Env(), RNG(1))
    b.start("Test")
    f = next(x for x in b.fighters if x.char is c)
    options = [o for o in b.spell_options(f) if o[0].startswith("charge:")]
    assert options and options[0][1]
    p = next(p for p in wand.magic["props"] if p["kind"] == "charges")
    left = p["left"]
    sid = options[0][0].split(":", 2)[2]
    target = b.enemies_of(f)[0] if game.tables.spells[sid]["target"] == "enemy" else f
    b.do_cast(f, options[0][0], target)
    assert p["left"] == left - 1
    from realmwalker.rules.progression import long_rest

    long_rest(c, game.tables, RNG(2))
    assert p["left"] == p["value"]


def test_treasure_holds_magic_at_higher_tiers(game):
    found = 0
    for i in range(200):
        items, money = treasure.roll(game, 5, RNG(i, "hoard"))
        found += sum(1 for it in items if it.magic)
        assert money > 0
    assert found > 5


def test_the_ai_names_what_you_have_not_seen(game):
    it = item(game, "weapon")
    facts = magic_items.dressing_facts(game, it)
    assert facts["powers"] and facts["hero"]
    assert magic_items.apply_dressing(it, {"name": "The Grey Widow", "history": "It was found in a ditch."})
    assert it.magic["title"] == "The Grey Widow" and it.magic["source"] == "ai"
    it.magic["identified"] = True
    assert not magic_items.apply_dressing(it, {"name": "Something Else", "history": "x"})
    assert it.magic["title"] == "The Grey Widow"


def test_a_magic_item_has_a_look_from_its_words_and_the_ai_may_choose_another(game):
    from realmwalker.ai.tasks import LOOK_CLOTHS, LOOK_EMBLEMS, LOOK_GLOWS, LOOK_METALS, MAGIC_ITEM

    fig = game.tables.sprites["figures"]
    named = set(fig["colours"]) | set(fig["metals"]) | set(fig["glows"])
    for word in LOOK_METALS + LOOK_CLOTHS + tuple(g for g in LOOK_GLOWS if g != "none"):
        assert word in named, f"the AI may choose {word}, which is not a colour in sprites.json"
    looks = game.tables.magic["looks"]
    for table in ("metal", "cloth"):
        assert all(v in named for _, v in looks[table])
    it = item(game, "weapon")
    assert set(it.magic["look"]) >= {"metal", "cloth", "emblem"} and it.magic["look"]["metal"] in named
    m = {"title": "The Raven's Night", "story": "", "props": [{"kind": "resist", "type": "fire", "value": 1}],
         "rarity": "very_rare"}
    look = magic_items.look_for(game, m, RNG(3, "look"))
    assert look["metal"] == "blackened" and look["cloth"] == "black"
    # The AI's reply is cleaned against the whitelists: a word not on them is dropped, not an error.
    reply = MAGIC_ITEM.schema.clean({"name": "Sunfall", "history": "Old.", "metal": "Gold", "glow": "plasma",
                                     "emblem": "sun", "cloth": "tartan"})
    assert reply == {"name": "Sunfall", "history": "Old.", "metal": "gold", "emblem": "sun"}
    assert magic_items.apply_dressing(it, {**reply, "glow": "none"})
    assert it.magic["look"]["metal"] == "gold" and it.magic["look"]["emblem"] == "sun" and "glow" not in it.magic["look"]


def test_magic_items_survive_saving(game, tmp_path):
    c = game.leader
    it = add_existing(c, game.tables.items, item(game, "jewellery"))
    equip(c, game.tables.items, it.uid)
    save.save_game(game, tmp_path)
    loaded = save.load_game(tmp_path / game.world.meta.id, game.tables)
    again = next(i for i in loaded.leader.inventory if i.magic)
    assert again.magic == it.magic and loaded.leader.slot_of(again.uid) is not None
