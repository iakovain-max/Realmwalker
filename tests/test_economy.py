"""Markets: stock, coin, restocking, prices by place and season and mood, buying, selling, haggling."""

import copy

import pytest

from realmwalker.core.rng import RNG
from realmwalker.game import economy
from realmwalker.game.people import npcs_in, prepare_town
from realmwalker.game.state import new_game
from realmwalker.rules.creation import CharacterBuilder
from realmwalker.rules.inventory import add_item
from realmwalker.rules.items import Item
from realmwalker.world.generator import WorldOptions
from realmwalker.world.tables import Tables
from tests.worlds import cached_world  # noqa: E402


@pytest.fixture(scope="module")
def tables(data):
    return Tables(data)


@pytest.fixture(scope="module")
def world(tables):
    return cached_world(WorldOptions("Tradeland", 8, "medium"), tables)


def hero(tables):
    b = CharacterBuilder(tables, RNG(1, "hero"))
    b.set_race("human")
    b.set_class("fighter")
    b.set_background("guild_artisan")
    return b.build()


@pytest.fixture
def game(tables, world):
    return new_game(copy.deepcopy(world), tables, hero(tables))


def merchant(game, trade: str, kind: str | None = None):
    for s in game.world.settlements:
        if kind and s.kind != kind:
            continue
        prepare_town(game, s)
        for n in npcs_in(game.world, s.id):
            if economy.shop_kind(game, n) == trade:
                return s, n
    pytest.skip(f"no {trade} merchant")


def test_every_kind_of_merchant_has_stock_and_coin(game):
    for trade in ("general", "smith", "apothecary", "market", "inn", "stable"):
        s, npc = merchant(game, trade)
        shop = economy.shop_state(game, npc)
        assert shop["stock"] and shop["coin"] > 0, trade
        assert all(item in game.tables.items for item in shop["stock"])


def test_cities_stock_more_than_villages(game):
    _, city = merchant(game, "general", "city")
    _, village = merchant(game, "general", "village")
    assert sum(economy.shop_state(game, city)["stock"].values()) > sum(economy.shop_state(game, village)["stock"].values())


def test_trade_goods_are_cheap_where_they_are_made(game):
    coastal = [s for s in game.world.settlements if "coast" in economy.lands_near(game, s)]
    inland = [s for s in game.world.settlements if not economy.lands_near(game, s) & {"coast", "desert"}]
    if not coastal or not inland:
        pytest.skip("no coast or no inland town")
    assert economy.local_factor(game, coastal[0], "salt") < 0.6 < 1.3 < economy.local_factor(game, inland[0], "salt")


def test_winter_food_is_dear(game):
    s, npc = merchant(game, "general")
    cal = game.tables.calendar
    game.world.time = cal.minutes_for(cal.start_year, 11, 15, 12)
    winter = economy.buy_price(game, npc, "rations")
    game.world.time = cal.minutes_for(cal.start_year + 1, 8, 15, 12)
    autumn = economy.buy_price(game, npc, "rations")
    assert winter > autumn


def test_mood_and_haggling_move_prices(game):
    s, npc = merchant(game, "smith")
    npc.disposition = 0
    neutral = economy.buy_price(game, npc, "longsword")
    npc.disposition = 80
    assert economy.buy_price(game, npc, "longsword") < neutral
    npc.disposition = -80
    assert economy.buy_price(game, npc, "longsword") > neutral
    npc.disposition = 0
    shop = economy.shop_state(game, npc)
    shop["haggle"], shop["haggle_day"] = 0.1, game.moment.total_days
    assert economy.buy_price(game, npc, "longsword") < neutral
    assert "haggling" in economy.haggle(game, npc), "once a day"


def test_buying_and_selling(game):
    s, npc = merchant(game, "general")
    shop = economy.shop_state(game, npc)
    item_id = "torch" if "torch" in shop["stock"] else next(iter(shop["stock"]))
    c = game.leader
    c.money = 10000
    before_stock, before_coin = shop["stock"][item_id], shop["coin"]
    price = economy.buy_price(game, npc, item_id)
    msg = economy.buy(game, npc, item_id)
    assert "buy" in msg and c.money == 10000 - price
    assert shop["stock"].get(item_id, 0) == before_stock - 1 and shop["coin"] == before_coin + price
    rope = add_item(c, game.tables.items, "rope")
    offer, why = economy.sell_price(game, npc, rope)
    assert offer and offer < economy.buy_price(game, npc, "rope")
    money = c.money
    assert "sell" in economy.sell(game, npc, c, rope.uid)
    assert c.money == money + offer and c.item(rope.uid) is None
    used = [r for r in economy.listing(game, npc) if r["used"] is not None and "rope" in r["name"]]
    assert used  # (a city shop may also have a magic thing or two among the second-hand goods)
    assert "buy" in economy.buy(game, npc, used[0]["item_id"], used[0]["used"])


def test_merchants_only_buy_their_trade_and_run_out_of_coin(game):
    s, npc = merchant(game, "apothecary")
    sword = Item(0, "longsword")
    assert economy.sell_price(game, npc, sword)[0] is None
    s2, smith = merchant(game, "smith")
    shop = economy.shop_state(game, smith)
    shop["coin"] = 5
    blade = add_item(game.leader, game.tables.items, "greatsword")
    assert "can't pay" in economy.sell(game, smith, game.leader, blade.uid)
    stolen = add_item(game.leader, game.tables.items, "dagger", tags=["stolen"])
    assert economy.sell_price(game, smith, stolen)[0] is None


def test_shops_restock_after_a_week(game):
    s, npc = merchant(game, "general")
    shop = economy.shop_state(game, npc)
    shop["stock"].clear()
    assert not economy.shop_state(game, npc)["stock"]
    game.world.time += 8 * 24 * 60
    assert economy.shop_state(game, npc)["stock"]


def test_trading_in_a_conversation(game):
    from realmwalker.game.dialogue import Conversation

    s, npc = merchant(game, "smith")
    conv = Conversation(game, npc)
    ids = [c.id for c in conv.menu()]
    assert "trade" in ids and "haggle" in ids
    assert conv.choose(next(c for c in conv.menu() if c.id == "trade")) == "trade"
    conv.choose(next(c for c in conv.menu() if c.id == "haggle"))
    assert "haggle" not in [c.id for c in conv.menu()]


def test_shops_survive_saving(game, tmp_path):
    from realmwalker.game import save

    s, npc = merchant(game, "market")
    shop = economy.shop_state(game, npc)
    folder = save.save_game(game, tmp_path)
    loaded = save.load_game(folder, game.tables)
    assert loaded.world.towns[s.id].shops[npc.id] == shop
