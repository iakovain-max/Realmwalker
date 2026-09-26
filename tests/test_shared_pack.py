"""The party's one pack (after v1, asked for by Anton to end the micromanagement): everyone travelling together carries
from one pack, the weight is carried together, companions find what they need in it, and what each wears stays theirs."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import camp, companions, events, pack, save
from realmwalker.game.state import new_game
from realmwalker.rules import health
from realmwalker.rules.character import Sheet
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.inventory import add_item, carried, equip, pack_mates, worn_by
from realmwalker.world.generator import WorldGenerator, WorldOptions
from realmwalker.world.tables import Tables


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return WorldGenerator(WorldOptions("Packhorse", 21, "small"), tables).generate()


def member(tables, cls, seed):
    b = CharacterBuilder(tables, RNG(seed, "member"))
    b.set_class(cls)
    return b.build()


def companion(tables, cls="fighter", seed=5):
    c = member(tables, cls, seed)
    c.is_player = False
    c.money = 0  # a companion's pay is theirs: they carry no purse for the party
    c.companion = {"npc": -1, "archetype": "sellsword", "values": [], "want": "pay", "loyalty": 55.0, "wage": 100,
                   "share": 0.0, "hired": 0, "order": "follow", "home": 0, "unpaid": 0}
    return c


@pytest.fixture
def game(world, tables):
    g = new_game(copy.deepcopy(world), tables, member(tables, "wizard", 1))
    g.survival = False
    return g


def join(game, c):
    game.party.append(c)
    pack.sync(game)
    return c


def test_joining_pours_their_things_into_the_one_pack(game, tables):
    leader = game.leader
    mira = companion(tables)
    theirs = sum(it.qty for it in mira.inventory)
    armour = mira.equipped_item("armor")
    mine = sum(it.qty for it in leader.inventory)
    join(game, mira)
    assert mira.inventory is leader.inventory and sum(it.qty for it in leader.inventory) == mine + theirs
    uids = [it.uid for it in leader.inventory]
    assert len(uids) == len(set(uids)), "every thing has its own number in the shared pack"
    assert mira.equipped_item("armor") is armour  # what she wears is still hers, renumbered or not
    assert worn_by(leader, armour.uid) == (mira, "armor")
    assert pack_mates(leader) == [leader, mira]


def test_counting_what_the_party_carries_counts_it_once(game, tables):
    add_item(game.leader, tables.items, "rations", 3)
    join(game, companion(tables))
    join(game, companion(tables, "rogue", 6))
    n = sum(it.qty for it in carried(game.party) if it.def_id == "rations")
    assert events.count_item(game, "rations") == n
    assert camp.party_has(game, "rations", n) and not camp.party_has(game, "rations", n + 1)


def test_the_load_is_carried_together(game, tables):
    leader = game.leader
    alone_limit = Sheet(leader, tables).capacity()[0]
    mira = join(game, companion(tables))
    together = Sheet(leader, tables).pack_capacity()[0]
    assert together == pytest.approx(alone_limit + Sheet(mira, tables).capacity()[0])
    add_item(leader, tables.items, "iron_pot", 1)
    add_item(leader, tables.items, "rations", 10)
    loads = {Sheet(m, tables).pack_load() for m in game.party}
    assert len(loads) == 1, "one load for the whole party"
    levels = {Sheet(m, tables).encumbrance() for m in game.party}
    assert len(levels) == 1, "everyone carries the same share"
    whole = sum(tables.items.weight(it) for it in leader.inventory)
    assert loads.pop() <= whole + 5  # worn things count for less, and coin a little


def test_a_companion_finds_arrows_and_bandages_in_the_pack(game, tables):
    from realmwalker.rules.combat import PARTY, Battle, Env
    from realmwalker.rules.creatures import spawn
    from realmwalker.rules.inventory import remove_item
    from realmwalker.rules.wounds import Wound

    archer = companion(tables, "fighter", 8)
    bow = add_item(archer, tables.items, "longbow")
    equip(archer, tables.items, bow.uid, "main_hand")
    for it in [i for i in archer.inventory if i.def_id in ("arrows", "bolts")]:
        remove_item(archer, it.uid)
    join(game, archer)
    add_item(game.leader, tables.items, "arrows", 20)  # bought by the leader
    b = Battle(tables, game.party, [spawn(tables, "wolf", RNG(1), 1)], Env(), RNG(2, "b"))
    b.start("Test.")
    f = next(x for x in b.side(PARTY) if x.char is archer)
    shot = next(o for o in b.attack_options(f) if "bow" in o.name)
    assert shot.available, shot.reason
    healer = archer
    wound = Wound("left_arm", "cut", 2, 2, 0)
    add_item(game.leader, tables.items, "bandages", 2)
    opts = {a: ok for a, _, ok, _ in health.treatment_options(healer, game.leader, wound, tables, fire=False,
                                                                 wooded=False)}
    assert opts["bandage"]


def test_waiting_and_leaving_take_only_what_they_wear(game, tables):
    leader = game.leader
    mira = join(game, companion(tables))
    worn = set(mira.equipped.values())
    total = len(leader.inventory)
    game.player.x, game.player.y = game.player.x, game.player.y
    companions.wait_here(game, mira)
    assert mira.inventory is not leader.inventory and {it.uid for it in mira.inventory} == worn
    assert len(leader.inventory) == total - len(worn)
    companions.rejoin(game)
    assert mira.inventory is leader.inventory and len(leader.inventory) == total
    companions.dismiss(game, mira)
    assert mira.inventory is not leader.inventory and len(leader.inventory) == total - len(worn)


def test_the_dead_leave_their_things_to_the_rest(game, tables):
    leader = game.leader
    mira = join(game, companion(tables))
    total = len(leader.inventory)
    mira.alive = False
    game.party = [c for c in game.party if c.alive]
    pack.sync(game)
    assert len(leader.inventory) == total and not mira.equipped
    assert all(worn_by(leader, it.uid)[0] in (None, leader) for it in leader.inventory)


def test_nobody_puts_on_what_another_wears(game, tables):
    leader = game.leader
    mira = join(game, companion(tables))
    armour = mira.equipped_item("armor")
    ok, msg = equip(leader, tables.items, armour.uid)
    assert not ok and "has the" in msg


def test_selling_never_takes_it_off_a_companions_back(game, tables):
    from realmwalker.game import economy
    from realmwalker.game.people import npcs_in

    mira = join(game, companion(tables))
    armour = mira.equipped_item("armor")
    buyer = None
    for s in [s for s in game.world.settlements if s.kind in ("town", "city")]:
        game.player.local_key = None
        game.player.x, game.player.y = s.x, s.y
        game.enter_local()
        buyer = next((n for n in npcs_in(game.world, s.id) if economy.shop_spec(game, n) is not None
                      and economy.sell_price(game, n, armour)[0] is not None), None)
        if buyer is not None:
            break
    if buyer is None:
        pytest.skip("nobody buys armour in this world")
    said = economy.sell(game, buyer, game.leader, armour.uid, 1)
    assert "has it on" in said and mira.equipped_item("armor") is armour


def test_the_pack_is_saved_once_and_shared_again_on_loading(game, tables, tmp_path):
    import json
    import zipfile

    mira = join(game, companion(tables))
    worn = dict(mira.equipped)
    folder = save.save_game(game, tmp_path)
    with zipfile.ZipFile(folder / save.CHARACTER_FILE) as z:
        body = json.loads(z.read("character.json"))
    assert body["party"][1]["inventory"] == []
    loaded = save.load_game(folder, tables)
    leader2, mira2 = loaded.party
    assert mira2.inventory is leader2.inventory and mira2.equipped == worn
    assert mira2.equipped_item("armor") is not None
    assert save.character_entries(loaded)["character.json"] == save.character_entries(game)["character.json"]


def test_an_older_save_with_separate_packs_is_poured_into_one(game, tables):
    leader = game.leader
    mira = companion(tables)  # numbered from 1 like the leader's things, as separate packs were
    game.party.append(mira)  # as an older save would have them: two packs
    before = sum(it.qty for it in leader.inventory) + sum(it.qty for it in mira.inventory)
    pack.sync(game)
    assert sum(it.qty for it in leader.inventory) == before and mira.inventory is leader.inventory
    assert len({it.uid for it in leader.inventory}) == len(leader.inventory)


def test_like_things_join_one_stack(game, tables):
    leader = game.leader
    add_item(leader, tables.items, "rations", 2, made_at=game.world.time)
    mira = companion(tables)
    add_item(mira, tables.items, "rations", 3, made_at=game.world.time)
    ages = {it.made_at for c in (leader, mira) for it in c.inventory if it.def_id == "rations"}
    total = sum(it.qty for c in (leader, mira) for it in c.inventory if it.def_id == "rations")
    join(game, mira)
    stacks = [it for it in leader.inventory if it.def_id == "rations"]
    assert len(stacks) == len(ages), "one stack for each age of food (they spoil apart)"
    assert sum(it.qty for it in stacks) == total


def test_the_jail_keeps_everyones_clothes(game, tables):
    from realmwalker.game import law

    mira = join(game, companion(tables))
    clothes = {uid for slot, uid in mira.equipped.items()
               if tables.items.get(mira.item(uid).def_id)["category"] == "clothing"}
    realm = next(iter(game.world.factions))
    law.confiscate(game, realm)
    assert mira.inventory is game.leader.inventory
    assert {it.uid for it in game.leader.inventory} >= clothes
    assert set(mira.equipped.values()) == clothes


def test_the_inventory_screen_is_the_partys(make_app, world):
    import tcod.console

    from realmwalker.ui.input import KeyEvent
    from realmwalker.ui.screens.sheets import InventoryScreen

    app = make_app()
    tables = app.tables
    game = new_game(copy.deepcopy(world), tables, member(tables, "wizard", 1))
    app.start_game(game)
    mira = join(game, companion(tables))
    screen = InventoryScreen(app, game)
    app.push(screen)
    con = tcod.console.Console(160, 45, order="F")
    app.render(con)
    text = "\n".join("".join(chr(ch) for ch in con.rgb["ch"][:, y]) for y in range(con.height))
    assert "The party's pack" in text and "(Mira" in text.replace(mira.name.split()[0], "Mira")
    assert "Party load" in text
    # "Give to Mira" on a sword: Mira takes it up.
    sword = add_item(game.leader, tables.items, "shortsword")
    screen.selected = screen.visible_items().index(sword)
    screen.give()
    assert worn_by(game.leader, sword.uid)[0] is mira
    for key in ("tab", "down", "enter", "tab"):
        app.handle_event(KeyEvent(key))
        app.render(con)
    assert app.error_count == 0
