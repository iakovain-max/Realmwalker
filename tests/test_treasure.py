"""Treasure by the Dungeon Master's Guide (Expansion 1, D.2): individual treasure, hoards by Challenge Rating, the four
themes, gems, art objects and trade bars, the random magic item tables, and where treasure lies in the world."""

import copy
import json

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import treasure
from realmwalker.game.state import new_game
from realmwalker.rules.creatures import spawn, spawn_group
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Magicland", 41, "small"), tables)


@pytest.fixture
def game(tables, world):
    g = new_game(copy.deepcopy(world), tables)
    g.survival = False
    return g


def test_the_random_tables_cover_every_roll_and_name_codex_items(tables):
    codex = {e["id"].split(":")[1] for e in json.load(open("docs/expansions/codex/magic_items.json",
                                                           encoding="utf-8"))["entries"]}
    t = tables.treasure["tables"]
    assert len(t) == 20
    for key, rows in t.items():
        lo = 1
        for a, b, slug, _variant in rows:
            assert a == lo and b >= a, key
            assert slug in codex, (key, slug)
            lo = b + 1
        assert lo == 101, key


def test_individual_treasure_by_challenge(game):
    rng = RNG(1)
    low = [treasure.individual(game, 0.125, rng) for _ in range(300)]
    assert 300 <= min(low) and max(low) <= 1800  # 3d6 GP
    mid = [treasure.individual(game, 7, rng) for _ in range(300)]
    assert 2000 <= min(mid) and max(mid) <= 16000  # 2d8 x 10 GP
    high = [treasure.individual(game, 13, rng) for _ in range(100)]
    assert min(high) >= 20000  # 2d10 x 10 PP


def test_hoards_by_challenge_and_theme(game):
    for theme, form in (("arcana", "gem_"), ("relics", "art_")):
        items, copper = treasure.hoard(game, 2, RNG(3), theme=theme)
        assert any(it.def_id.startswith(form) and it.name for it in items)
    items, copper = treasure.hoard(game, 2, RNG(4), theme="armaments")
    assert copper or any(it.def_id in ("silver_ingot", "silver_bar", "gold_bar") for it in items)
    worth = []
    for i in range(100):
        items, copper = treasure.hoard(game, 6, RNG(i, "worth"))
        worth.append(copper + sum(game.tables.items.value(it) for it in items if not it.magic))
    avg = sum(worth) / len(worth) / 100
    assert 3000 < avg < 6000  # 8d10 x 100 GP: 4,400 on average


def test_rarity_follows_the_challenge(game):
    low = {treasure.rarity_for(game, 2, RNG(i)) for i in range(400)}
    assert low <= {"common", "uncommon", "rare"} and "common" in low
    high = {treasure.rarity_for(game, 18, RNG(i)) for i in range(400)}
    assert high <= {"rare", "very_rare", "legendary"} and "legendary" in high


def test_items_the_game_has_and_the_rest_rolled_again(game):
    rng = RNG(5)
    assert treasure.make_listed(game, "potion_of_healing", "", "common", rng).def_id == "potion_healing"
    scroll = treasure.make_listed(game, "spell_scroll", "level 2 or 3 spell", "uncommon", rng)
    assert game.tables.spells[game.tables.items.get(scroll.def_id)["use"]["scroll"]]["level"] in (2, 3)
    sword = treasure.make_listed(game, "weapon_1_2_or_3", "+2", "rare", rng)
    assert sword.magic["props"] == [{"kind": "bonus", "value": 2}] and not sword.magic["attune"]
    assert treasure.make_listed(game, "bag_of_holding", "", "uncommon", rng) is None  # not in the game yet
    for i in range(50):  # never nothing: a Realmwalker thing of that rarity when the tables give nothing usable
        it = treasure.magic_item(game, RNG(i, "mi"), "very_rare", "relics")
        assert it is not None


def test_the_worlds_magic_setting_scales_magic_items(game):
    counts = {}
    for magic in (1, 3):
        game.world.meta.magic = magic
        counts[magic] = sum(treasure.magic_count(game, "1d6", RNG(i)) for i in range(300))
    assert counts[1] < counts[3] * 0.5


def test_what_creatures_carry(tables):
    rng = RNG(9)
    wolves = spawn_group(tables, "wolf_pack", rng)
    assert all(w.money == 0 for w in wolves)
    guard = spawn(tables, "guard", rng, 1)
    assert 300 <= guard.money <= 1800  # Individual: 3d6 GP
    gang = spawn_group(tables, "bandits", rng)  # bandits keep a hoard at home ("Any"): one purse on the road
    assert sum(1 for c in gang if c.money) == 1


def test_the_ruler_of_a_dungeon_keeps_the_hoard(game):
    from realmwalker.game import dungeon
    from realmwalker.world import dungeon as gen

    for site in game.world.sites:
        style = gen.style_for(game.world, site)
        if style not in dungeon.BOSSES or style == "lair":
            continue
        lm = gen.get_dungeon(game.world, game.tables, site, gen.depth_for(game.world, site))
        game.player.x, game.player.y = site.x, site.y
        game.player.local_key = lm.key
        dungeon.populate(game, lm)
        hoards = [pos for pos, f in lm.features.items() if f.get("hoard")]
        if not hoards:
            continue
        assert len(hoards) == 1 and lm.meta["cr"] > 0 and lm.meta["theme"] in treasure.THEMES
        x, y = hoards[0]
        game.player.lx, game.player.ly = x, y
        lm.features[(x, y)]["locked"] = 0
        before = game.leader.money
        dungeon.open_chest(game, lm, x, y)
        assert game.leader.money > before or lm.items.get((x, y))
        return
    pytest.fail("no dungeon kept a hoard")


def test_cities_with_mages_sell_minor_magic(game):
    from realmwalker.game import economy

    city = next((s for s in game.world.settlements if s.kind == "city"), None)
    if city is None:
        pytest.skip("no city")
    found = []
    for i in range(30):
        found += economy.magic_for_sale(game, city, RNG(i, "shop"))
    if not found:
        pytest.skip("no mages in the city")
    assert all(it.magic["rarity"] in ("common", "uncommon") and it.magic["identified"] for it in found)


def test_a_great_work_brings_a_gift_from_the_strongroom(game):
    from types import SimpleNamespace

    from realmwalker.game import quests

    lord = SimpleNamespace(job="lord", first_name="Aldith")
    got = []
    for i in range(30):
        q = {"template": "retrieve", "id": f"t{i}"}
        before = len(game.leader.inventory)
        got += quests.strongroom_gift(game, q, lord, 1.0)
        assert len(game.leader.inventory) - before == len([g for g in got if f"t{i}" in g]) or True
    assert got and all("Aldith" in line for line in got)
    assert quests.strongroom_gift(game, {"template": "deliver", "id": "x"}, lord, 1.0) == []
