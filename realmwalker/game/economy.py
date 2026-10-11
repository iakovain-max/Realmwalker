"""Markets: what each merchant has, what they will pay, and what they charge.

Prices start from the item's value and move with what the land around a settlement produces
(cheap near where it is made), with trade goods dear where nobody makes them, with the size of the
place and the season, with how the merchant feels about you, and with haggling. Merchants have
limited coin and stock and restock every week. Numbers are in data/economy.json.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.game.people import NPC, change_disposition, town_of
from realmwalker.rules.character import Sheet
from realmwalker.rules.inventory import add_existing, add_item, remove_item, worn_by
from realmwalker.rules.items import Item, money_text

MOOD_BUY = {"hostile": 1.3, "unfriendly": 1.12, "neutral": 1.0, "friendly": 0.95, "warm": 0.9}
MOOD_SELL = {"hostile": 0.7, "unfriendly": 0.88, "neutral": 1.0, "friendly": 1.04, "warm": 1.08}
DAY = 24 * 60


def shop_kind(game, npc: NPC) -> str | None:
    return game.tables.people["occupations"].get(npc.job, {}).get("trade")


def shop_spec(game, npc: NPC) -> dict | None:
    kind = shop_kind(game, npc)
    return game.tables.economy["shops"].get(kind) if kind else None


def lands_near(game, settlement, radius: int = 3) -> set[str]:
    w = game.world
    out = set()
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            x, y = settlement.x + dx, settlement.y + dy
            if w.in_bounds(x, y):
                out.add(game.land_key(x, y))
    return out


def local_factor(game, settlement, item_id: str) -> float:
    """How this settlement's circumstances move the price of an item (1.0 = its book value)."""
    econ = game.tables.economy
    d = game.tables.items.get(item_id)
    cat = d["category"]
    factor = 1.0
    lookup = game.tables.biomes.lookup
    made_here = [lookup(econ["production"], b, {})[item_id] for b in lands_near(game, settlement)
                 if item_id in lookup(econ["production"], b, {})]
    if made_here:
        factor *= min(made_here)
    elif cat == "trade" and item_id != "diamond":
        factor *= float(econ["trade_goods_scarcity"])
    kind = econ["kind_prices"].get(settlement.kind, {})
    factor *= float(kind.get(item_id, kind.get(cat, 1.0)))
    season = econ["season_prices"].get(game.moment.season, {})
    factor *= float(season.get(item_id, season.get(cat, 1.0)))
    return factor * troubles_factor(game, settlement, cat)


def troubles_factor(game, settlement, cat: str) -> float:
    """War, siege, famine and plague make things dear."""
    st = getattr(settlement, "status", {})
    factor = 1.0
    food = cat in ("food", "drink")
    arms = cat in ("weapon", "armor", "shield", "helmet", "ammo")
    if st.get("siege"):
        factor *= 2.0 if food else 1.3 if arms else 1.15
    if st.get("famine"):
        factor *= 1.7 if food else 1.0
    if st.get("plague"):
        factor *= 1.1
    if st.get("sacked") is not None:
        factor *= 1.2
    if getattr(game.world, "wars", None):
        from realmwalker.world import factions as fx
        from realmwalker.world.politics import at_war

        realm = fx.realm_of_settlement(game.world, settlement)
        if realm is not None and at_war(game.world, realm.id):
            factor *= 1.15 if food else 1.3 if arms else 1.0
    return factor


# ---------------------------------------------------------------------------- the shop
def shop_state(game, npc: NPC) -> dict | None:
    """The merchant's stock and coin, restocked if a week has passed."""
    spec = shop_spec(game, npc)
    if spec is None:
        return None
    town = town_of(game.world, npc.settlement)
    shop = town.shops.get(npc.id)
    now = game.world.time
    if shop is None or now - shop.get("restocked", -10 ** 9) >= int(game.tables.economy["restock_days"]) * DAY:
        shop = restock(game, npc, shop or {"kind": shop_kind(game, npc), "stock": {}, "used": [], "coin": 0})
        town.shops[npc.id] = shop
    return shop


def restock(game, npc: NPC, shop: dict) -> dict:
    econ = game.tables.economy
    settlement = game.world.settlements[npc.settlement]
    size = econ["size"].get(settlement.kind, econ["size"]["village"])
    rng = game.world.rng.child(f"restock/{npc.id}/{game.world.time // DAY}")
    stock = {}
    for item_id, lo, hi in game.tables.economy["shops"][shop["kind"]]["stock"]:
        if item_id not in game.tables.items:
            continue
        qty = int(round(rng.randint(int(lo), int(hi)) * float(size["stock"])))
        if qty > 0:
            stock[item_id] = qty
    if shop["kind"] in ("apothecary", "general"):
        from realmwalker.game.magic import scroll_stock

        for item_id, qty in scroll_stock(game, settlement, rng.child("scrolls")).items():
            stock[item_id] = stock.get(item_id, 0) + qty
    shop["stock"] = stock
    # Things the player sold them are sold on after a month.
    shop["used"] = [u for u in shop.get("used", []) if game.world.time - u.get("sold_at", 0) < 30 * DAY]
    base = int(size["coin"] * {"inn": 0.5, "stable": 0.6, "apothecary": 0.7, "temple": 0.4}.get(shop["kind"], 1.0))
    shop["coin"] = max(shop.get("coin", 0), int(base * rng.uniform(0.7, 1.3)))
    shop["restocked"] = game.world.time
    return shop


def haggle_bonus(game, npc: NPC, shop: dict) -> float:
    return float(shop.get("haggle", 0.0)) if shop.get("haggle_day") == game.moment.total_days else 0.0


def buy_price(game, npc: NPC, item_id: str, item: Item | None = None) -> int:
    """What the merchant charges for one."""
    shop = shop_state(game, npc)
    spec = shop_spec(game, npc)
    settlement = game.world.settlements[npc.settlement]
    items = game.tables.items
    value = items.unit_value(item) if item is not None else int(items.get(item_id)["value"])
    price = value * local_factor(game, settlement, item_id) * float(spec.get("markup", 1.0))
    price *= MOOD_BUY[npc.mood()] * (1.0 + float(npc.flags.get("price_mod", 0.0))) * (1.0 - haggle_bonus(game, npc, shop))
    price *= standing_factor(game, npc)
    return max(1, int(round(price)))


def standing_factor(game, npc: NPC) -> float:
    """Your name with the merchant's guild or lord moves their prices; guild members get a discount."""
    if not getattr(game.world, "factions", None):
        return 1.0
    from realmwalker.game.people import npc_factions
    from realmwalker.game.reputation import member_discount, standing

    facs = npc_factions(game, npc)
    if not facs:
        return 1.0
    score = standing(game, facs[0].id)
    factor = 1.3 if score <= -50 else 1.1 if score <= -15 else 0.9 if score >= 50 else 0.95 if score >= 15 else 1.0
    return factor * (1.0 - member_discount(game, facs))


def sell_price(game, npc: NPC, item: Item) -> tuple[int | None, str]:
    """What the merchant would pay for one of these, or (None, why not)."""
    spec = shop_spec(game, npc)
    if spec is None:
        return None, "they don't trade"
    items = game.tables.items
    d = items.get(item.def_id)
    if d["category"] not in spec["buys"]:
        return None, f"they don't deal in {d['category']}"
    if "stolen" in item.tags:
        from realmwalker.game.law import is_fence

        if not is_fence(game, npc):
            return None, "they won't touch stolen goods"
    shop = shop_state(game, npc)
    settlement = game.world.settlements[npc.settlement]
    econ = game.tables.economy
    ratio = float(econ["sell_ratio_trade"] if d["category"] == "trade" else econ["sell_ratio"])
    price = items.unit_value(item) * ratio * local_factor(game, settlement, item.def_id)
    price *= MOOD_SELL[npc.mood()] * (1.0 + haggle_bonus(game, npc, shop))
    price = min(price, buy_price(game, npc, item.def_id, item) * 0.9)
    return max(0, int(price)), ""


def spoil_fresh(game, item_id: str, rng: RNG) -> int:
    """When a shop's food was made: recently."""
    food = game.tables.items.get(item_id).get("food")
    if not food:
        return game.world.time
    return game.world.time - rng.randint(0, min(2, int(food.get("spoil_days", 3)) // 3) * DAY)


def buy(game, npc: NPC, item_id: str, used_index: int | None = None) -> str:
    """The player buys one item (from new stock, or something sold to the merchant earlier)."""
    shop = shop_state(game, npc)
    items = game.tables.items
    leader = game.leader
    if used_index is not None:
        if not 0 <= used_index < len(shop["used"]):
            return "That is gone."
        item = Item.from_dict(shop["used"][used_index])
        price = buy_price(game, npc, item.def_id, item) * item.qty
    else:
        if shop["stock"].get(item_id, 0) <= 0:
            return "They have none left."
        item = None
        price = buy_price(game, npc, item_id)
    from realmwalker.game.events import party_money, pay

    if party_money(game) < price:
        return f"You can't afford it ({money_text(price)})."
    pay(game, price)
    shop["coin"] += price
    if used_index is not None:
        shop["used"].pop(used_index)
        got = add_existing(leader, items, item)
    else:
        shop["stock"][item_id] -= 1
        if shop["stock"][item_id] <= 0:
            del shop["stock"][item_id]
        rng = game.world.rng.child(f"buy/{npc.id}/{game.world.time}/{item_id}")
        got = add_item(leader, items, item_id, 1, made_at=spoil_fresh(game, item_id, rng))
        if items.get(item_id).get("container"):
            from realmwalker.rules.inventory import fill_containers

            fill_containers(leader, items, "clean")
    game.dirty = True
    return f"You buy {items.name(got, with_qty=False)} for {money_text(price)}."


def sell(game, npc: NPC, char, uid: int, qty: int = 1) -> str:
    shop = shop_state(game, npc)
    items = game.tables.items
    it = char.item(uid)
    if it is None:
        return "You no longer have that."
    price, why = sell_price(game, npc, it)
    if price is None:
        return f"{npc.first_name} shakes their head: {why}."
    qty = max(1, min(qty, it.qty))
    total = price * qty
    if total > shop["coin"]:
        return f"{npc.first_name} can't pay that much right now ({money_text(shop['coin'])} in the till)."
    wearer, slot = worn_by(char, uid)
    if slot is not None and qty >= it.qty:
        return "Take it off first." if wearer is char else f"{wearer.name.split()[0]} has it on."
    sold = remove_item(char, uid, qty)
    if sold is None:
        return "You no longer have that."
    char.money += total
    shop["coin"] -= total
    entry = sold.to_dict()
    entry["sold_at"] = game.world.time
    if items.stackable(sold):
        for u in shop["used"]:
            if u["def_id"] == sold.def_id and u.get("quality") == sold.quality and u.get("condition") == sold.condition:
                u["qty"] += sold.qty
                break
        else:
            shop["used"].append(entry)
    else:
        shop["used"].append(entry)
    game.dirty = True
    return f"You sell {items.name(sold)} for {money_text(total)}."


def haggle(game, npc: NPC) -> str:
    """Once a day per merchant: talk the prices your way (Persuasion or Deception)."""
    shop = shop_state(game, npc)
    today = game.moment.total_days
    if shop.get("haggle_day") == today:
        return f"{npc.first_name} has heard enough haggling for one day."
    c = game.leader
    s = Sheet(c, game.tables)
    skill = "deception" if s.skill_bonus("deception") > s.skill_bonus("persuasion") else "persuasion"
    bonus = s.skill_bonus(skill)
    h = game.tables.economy["haggle"]
    dc = int(h["dc"]) + (2 if set(npc.traits) & {"greedy", "sly", "suspicious"} else 0) - \
        (2 if set(npc.traits) & {"trusting", "cheerful", "generous"} else 0)
    rng = game.world.rng.child(f"haggle/{npc.id}/{today}")
    roll = dice.d20(rng).natural
    total = roll + bonus
    name = game.tables.rules["skills"][skill]["name"]
    line = f"<dice>{name}: {roll} {'+' if bonus >= 0 else '-'} {abs(bonus)} = {total} vs DC {dc}</>"
    shop["haggle_day"] = today
    if total >= dc:
        shop["haggle"] = min(float(h["max"]), float(h["per_point"]) * (total - dc + 2))
        return f"{line} {npc.first_name} sighs and comes down a little: prices {int(shop['haggle'] * 100)}% better for you today."
    shop["haggle"] = 0.0
    if total <= dc - 5:
        change_disposition(npc, -5)
        return f"{line} {npc.first_name} is not amused. The prices stay as they are."
    return f"{line} {npc.first_name} won't budge."


def listing(game, npc: NPC) -> list[dict]:
    """What the merchant has for sale: {"item_id", "used", "name", "price", "qty"}."""
    shop = shop_state(game, npc)
    items = game.tables.items
    rows = []
    for item_id, qty in sorted(shop["stock"].items(), key=lambda kv: (items.get(kv[0])["category"], items.get(kv[0])["name"])):
        rows.append({"item_id": item_id, "used": None, "name": items.get(item_id)["name"], "qty": qty,
                     "price": buy_price(game, npc, item_id)})
    for i, u in enumerate(shop["used"]):
        it = Item.from_dict(u)
        rows.append({"item_id": it.def_id, "used": i, "name": f"{items.name(it, with_qty=False)} (second-hand)",
                     "qty": it.qty, "price": buy_price(game, npc, it.def_id, it) * it.qty})
    return rows
