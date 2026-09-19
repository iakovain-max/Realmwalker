"""What townsfolk can do for you besides talk: trade, and services — inn beds, meals and baths,
performing and dice at the inn, healers' care and surgery, prayers at the temple, smiths' repairs,
animals at the stable, and a day's paid work. Prices are in data/economy.json ("services")."""

from __future__ import annotations

from dataclasses import dataclass, field

from realmwalker.core import dice
from realmwalker.game.people import NPC, change_disposition
from realmwalker.rules.character import Sheet
from realmwalker.rules.items import money_text

DAY = 24 * 60


@dataclass
class Service:
    id: str
    label: str
    price: int = 0
    enabled: bool = True
    why: str = ""
    options: list[tuple[str, str, int]] = field(default_factory=list)  # (arg, label, price) for a second choice


# ---------------------------------------------------------------------------- the menu in a conversation
def choices(conv) -> list:
    """Extra menu entries for this person's trade and services."""
    from realmwalker.game import economy
    from realmwalker.game.dialogue import Choice

    npc = conv.npc
    game = conv.game
    out = []
    spec = economy.shop_spec(game, npc)
    if spec is not None:
        out.append(Choice("trade", f"Let me see your {spec['name']}."))
        shop = economy.shop_state(game, npc)
        if shop.get("haggle_day") != game.moment.total_days:
            out.append(Choice("haggle", "[Persuasion] Haggle over your prices."))
    if services_for(game, npc):
        out.append(Choice("services", "What can you do for me?"))
    return out


def choose(conv, choice) -> str | None:
    from realmwalker.game import economy

    if choice.id == "trade":
        conv.you_say("Let me see what you have.")
        return "trade"
    if choice.id == "haggle":
        conv.you_say("Surely you can do better than that.")
        conv.note(economy.haggle(conv.game, conv.npc))
    if choice.id == "services":
        conv.you_say("What can you do for me?")
        return "services"
    return None


# ---------------------------------------------------------------------------- prices
def fee(game, npc: NPC, base: int, scaled: bool = False) -> int:
    econ = game.tables.economy
    s = game.world.settlements[npc.settlement]
    price = base * (float(econ["services"]["size_factor"].get(s.kind, 1.0)) if scaled else 1.0)
    mood = {"hostile": 1.5, "unfriendly": 1.2, "neutral": 1.0, "friendly": 0.9, "warm": 0.8}[npc.mood()]
    return max(1, int(round(price * mood * (1.0 + float(npc.flags.get("price_mod", 0.0))))))


def money(game) -> int:
    return sum(c.money for c in game.party)


def affordable(game, price: int) -> tuple[bool, str]:
    return (True, "") if money(game) >= price else (False, f"you need {money_text(price)}")


def charge(game, npc: NPC, price: int) -> None:
    from realmwalker.game.events import pay

    pay(game, price)
    npc.purse += price


# ---------------------------------------------------------------------------- what is on offer
def services_for(game, npc: NPC) -> list[Service]:
    occ = game.tables.people["occupations"].get(npc.job, {})
    offered = [s for s in occ.get("services", []) if s != "rumours"]
    if not offered or npc.mood() == "hostile":
        return []
    econ = game.tables.economy["services"]
    c = game.leader
    today = game.moment.total_days
    out: list[Service] = []
    for sid in offered:
        if sid == "room":
            for key, label in (("room_common", "A bed in the common room for the night"),
                               ("room_private", "A private room for the night")):
                price = fee(game, npc, econ[key], scaled=True)
                out.append(Service(key, label, price, *affordable(game, price)))
        elif sid == "meal":
            price = fee(game, npc, econ["meal"], scaled=True)
            out.append(Service("meal", "A hot meal and a drink", price, *affordable(game, price)))
        elif sid == "bath":
            price = fee(game, npc, econ["bath"], scaled=True)
            out.append(Service("bath", "A hot bath, and your clothes dried by the fire", price, *affordable(game, price)))
        elif sid == "perform":
            done = npc.flags.get("perform_day") == today
            out.append(Service("perform", "[Performance] Sing, play or tell tales for coin", 0, not done,
                               "you've already performed here today"))
        elif sid == "gamble":
            options = [(str(b), f"Bet {money_text(b)}", b) for b in (10, 50, 100, 500)]
            out.append(Service("gamble", "Dice with the drinkers", 0, money(game) >= 10, "you have nothing to bet",
                               options=options))
        elif sid == "treat_wounds":
            price = sum(fee(game, npc, int(econ["treat_per_wound"][str(w.severity)])) for w in c.wounds)
            ok, why = affordable(game, price)
            out.append(Service("treat_wounds", "Have your wounds cleaned, stitched, splinted and bound", price,
                               ok and bool(c.wounds), why if c.wounds else "you have no wounds"))
        elif sid == "surgery":
            price = fee(game, npc, econ["surgery"])
            internal = any(w.internal for w in c.wounds)
            ok, why = affordable(game, price)
            out.append(Service("surgery", "Surgery for the bleeding inside you", price, ok and internal,
                               why if internal else "you are not bleeding inside"))
        elif sid == "herbal_cure":
            price = fee(game, npc, econ["herbal_cure"])
            sick = any(d.get("phase") == "sick" for d in c.diseases) or any(w.infection > 0 for w in c.wounds)
            ok, why = affordable(game, price)
            out.append(Service("herbal_cure", "Herbal remedies against sickness and festering", price, ok and sick,
                               why if sick else "you are not sick"))
        elif sid == "prayer_healing":
            price = fee(game, npc, econ["prayer_healing"])
            hurt = c.hp < c.max_hp or bool(c.wounds)
            ok, why = affordable(game, price)
            out.append(Service("prayer_healing", "Prayers for healing (a donation)", price, ok and hurt,
                               why if hurt else "you are not hurt"))
        elif sid == "cure_disease":
            price = fee(game, npc, econ["cure_disease"])
            sick = any(d.get("phase") in ("sick", "incubating") and d["id"] != "wound_fever" for d in c.diseases) or \
                any(w.infection > 0 for w in c.wounds)
            ok, why = affordable(game, price)
            out.append(Service("cure_disease", "Ask the gods to lift a sickness (a donation)", price, ok and sick,
                               why if sick else "you are not sick"))
        elif sid == "blessing":
            unknown = [it for m in game.party for it in m.inventory if it.magic and not it.magic.get("identified")]
            price = fee(game, npc, 2000)
            options = [(f"{game.party.index(m)}:{it.uid}", game.tables.items.name(it), price)
                       for m in game.party for it in m.inventory if it.magic and not it.magic.get("identified")]
            out.append(Service("identify", "Ask what a strange thing is (a donation)", 0, bool(unknown),
                               "you carry nothing strange", options=options))
            cursed = [(f"{game.party.index(m)}:{it.uid}", game.tables.items.name(it), fee(game, npc, 6000))
                      for m in game.party for it in m.inventory if it.magic and it.magic.get("cursed")
                      and it.magic.get("curse_known")]
            if cursed:
                out.append(Service("remove_curse", "Have a curse lifted (a donation)", 0, True, "", options=cursed))
        elif sid == "repair":
            options = []
            for it in c.inventory:
                cat = game.tables.items.category(it)
                if cat in ("weapon", "armor", "shield", "helmet") and it.condition < 100:
                    price = repair_price(game, npc, it)
                    options.append((str(it.uid), f"{game.tables.items.name(it)} ({game.tables.items.condition_word(it)})", price))
            out.append(Service("repair", "Mend weapons and armour", 0, bool(options), "nothing of yours needs mending",
                               options=options))
        elif sid == "labour":
            done = npc.flags.get("labour_day") == today
            out.append(Service("labour", "Ask for a day's work (8 hours)", 0, not done, "no more work for you today"))
    if npc.job == "stablemaster":
        animals = game.tables.economy["animals"]
        options = [(aid, a["name"], fee(game, npc, int(a["price"]))) for aid, a in animals.items() if not aid.startswith("_")]
        out.append(Service("buy_animal", "Buy a pack or riding animal", 0, True, "", options=options))
        mine = [(str(i), a["name"], int(animals[a["kind"]]["price"]) // 2) for i, a in enumerate(c.animals)
                if a["kind"] in animals]
        if mine:
            out.append(Service("sell_animal", "Sell one of your animals", 0, True, "", options=mine))
    return out


def repair_price(game, npc: NPC, item) -> int:
    share = float(game.tables.economy["services"]["repair_share"])
    value = int(game.tables.items.get(item.def_id)["value"])
    return max(1, fee(game, npc, int(value * share * (100 - item.condition) / 100)))


# ---------------------------------------------------------------------------- doing it
def perform(game, npc: NPC, sid: str, arg: str | None = None) -> list[str]:
    """Carry out a service. Returns messages."""
    services = {s.id: s for s in services_for(game, npc)}
    svc = services.get(sid)
    if svc is None:
        return ["They don't offer that."]
    if not svc.enabled:
        return [f"You can't: {svc.why}."]
    c = game.leader
    handler = HANDLERS[sid]
    msgs = handler(game, npc, svc, arg)
    if sid in ("prayer_healing", "cure_disease") and game.party[1:]:
        from realmwalker.game.companions import react

        react(game, "prayer", quiet=True)
    game.dirty = True
    npc.remember(f"did business with the traveller on {game.moment.date_text()}")
    return msgs


def _room(game, npc, svc, arg):
    from realmwalker.game.fight import rest
    from realmwalker.rules import body

    charge(game, npc, svc.price)
    msgs = [f"You pay {money_text(svc.price)} and take the {'room' if svc.id == 'room_private' else 'bed'}."]
    msgs += rest(game, "long")
    if svc.id == "room_private":
        for c in game.party:
            if c.exhaustion > 0 and c.hunger < 55 and c.thirst < 60:
                c.exhaustion -= 1
                msgs.append(f"{body.first(c)} sleeps like the dead in a real bed.")
            c.effects.pop("hangover", None)
    return msgs


def _meal(game, npc, svc, arg):
    charge(game, npc, svc.price)
    for c in game.party:
        c.hunger = max(0.0, c.hunger - 60)
        c.thirst = max(0.0, c.thirst - 45)
        c.body_heat = max(c.body_heat, min(0.0, c.body_heat + 20))
    game.pass_time(40, "rest")
    return [f"A bowl of something hot, bread, and a mug of ale ({money_text(svc.price)}). You feel almost human."]


def _bath(game, npc, svc, arg):
    charge(game, npc, svc.price)
    for c in game.party:
        c.dirt = 0.0
        c.wet = 0.0
        c.body_heat = max(c.body_heat, 0.0)
    game.pass_time(45, "rest")
    return [f"Hot water, lye soap, and the grime of the road coming off in layers ({money_text(svc.price)})."]


def _perform(game, npc, svc, arg):
    c = game.leader
    bonus = Sheet(c, game.tables).skill_bonus("performance")
    rng = game.world.rng.child(f"perform/{npc.id}/{game.world.time}")
    roll = dice.d20(rng).natural
    total = roll + bonus
    npc.flags["perform_day"] = game.moment.total_days
    game.pass_time(90, "rest")
    line = f"<dice>Performance: {roll} {'+' if bonus >= 0 else '-'} {abs(bonus)} = {total}</>"
    if total >= 20:
        earned = rng.randint(80, 150)
        change_disposition(npc, 10)
        text = "The room goes quiet, then roars. Coins rattle into your cap."
    elif total >= 13:
        earned = rng.randint(20, 60)
        text = "They listen, mostly, and some of them pay."
    elif total >= 8:
        earned = rng.randint(2, 10)
        text = "Polite indifference, and a few coppers out of pity."
    else:
        earned = 0
        change_disposition(npc, -5)
        text = "Someone throws a crust. The innkeeper asks you to stop."
    c.money += earned
    return [line, text + (f" <loot>+{money_text(earned)}</>" if earned else "")]


def _gamble(game, npc, svc, arg):
    bet = int(arg or 10)
    if money(game) < bet:
        return ["You can't cover that bet."]
    rng = game.world.rng.child(f"dice/{npc.id}/{game.world.time}/{bet}")
    mine = dice.roll("2d6", rng).total
    theirs = dice.roll("2d6", rng).total
    game.pass_time(15, "rest")
    c = game.leader
    if mine > theirs:
        c.money += bet
        return [f"You throw {mine}; they throw {theirs}. <loot>You win {money_text(bet)}.</>"]
    if mine < theirs:
        charge(game, npc, bet)
        return [f"You throw {mine}; they throw {theirs}. <warn>You lose {money_text(bet)}.</>"]
    return [f"You both throw {mine}. The bets stay on the table."]


def _treat(game, npc, svc, arg):
    c = game.leader
    charge(game, npc, svc.price)
    minutes = 0
    for w in c.wounds:
        w.bandaged = w.bandaged or bool(w.bleed)
        if w.kind in ("cut", "bite", "puncture", "burn", "frostbite"):
            w.cleaned = True
            w.infection = max(0.0, w.infection - 40.0)
            w.infected = w.infection > 0
        if w.kind in ("cut", "bite", "puncture") and w.severity >= 2:
            w.stitched = True
            w.bleed = max(0, w.bleed - 2)
        if w.kind == "fracture":
            w.splinted = True
        minutes += 30
    game.pass_time(minutes, "rest")
    return [f"{npc.first_name} cleans, stitches, sets and binds every wound, not gently ({money_text(svc.price)})."]


def _surgery(game, npc, svc, arg):
    c = game.leader
    charge(game, npc, svc.price)
    rng = game.world.rng.child(f"surgery/{game.world.time}")
    for w in c.wounds:
        w.internal = False
    game.pass_time(120, "rest")
    msgs = [f"{npc.first_name} opens you up, finds the bleeding and ties it off. You remember very little of it "
            f"({money_text(svc.price)})."]
    if rng.chance(0.15):
        c.conditions.append("exposed:wound_fever")
        msgs.append("<warn>The knife was not as clean as it might have been.</>")
    return msgs


def _herbal(game, npc, svc, arg):
    c = game.leader
    charge(game, npc, svc.price)
    c.effects["herbal"] = 72.0
    for w in c.wounds:
        if w.infection > 0:
            w.infection = max(0.0, w.infection - 30.0)
            w.infected = w.infection > 0
    game.pass_time(30, "rest")
    return [f"Bitter draughts, a poultice, and instructions you only half follow ({money_text(svc.price)}). "
            f"It should help you fight it off."]


def _prayer(game, npc, svc, arg):
    from realmwalker.rules import health

    c = game.leader
    charge(game, npc, svc.price)
    rng = game.world.rng.child(f"prayer/{game.world.time}")
    amount = dice.roll("2d8", rng).total + 3
    worst = max(c.wounds, key=lambda w: (w.severity, w.bleed, w.infection), default=None)
    msgs = [f"{npc.first_name} lays hands on you and prays. Warmth spreads from the palms ({money_text(svc.price)})."]
    msgs += health.magic_heal(c, worst, amount)
    game.pass_time(20, "rest")
    return msgs


def _cure(game, npc, svc, arg):
    from realmwalker.rules import health

    charge(game, npc, svc.price)
    game.pass_time(30, "rest")
    return [f"{npc.first_name} prays over you for a long time ({money_text(svc.price)})."] + \
        health.magic_restore(game.leader, game.tables)


def _repair(game, npc, svc, arg):
    c = game.leader
    it = c.item(int(arg)) if arg else None
    if it is None:
        return ["You no longer have that."]
    price = repair_price(game, npc, it)
    ok, why = affordable(game, price)
    if not ok:
        return [f"You can't: {why}."]
    charge(game, npc, price)
    it.condition = 100
    game.pass_time(60, "rest")
    return [f"{npc.first_name} hammers, grinds and oils your {game.tables.items.name(it, with_qty=False)} back into "
            f"shape ({money_text(price)})."]


def _labour(game, npc, svc, arg):
    c = game.leader
    lo, hi = game.tables.economy["services"]["labour_pay"]
    rng = game.world.rng.child(f"labour/{npc.id}/{game.world.time}")
    bonus = Sheet(c, game.tables).skill_bonus("athletics")
    roll = dice.d20(rng).natural + bonus
    pay = int(hi) if roll >= 12 else int(lo)
    npc.flags["labour_day"] = game.moment.total_days
    game.pass_time(8 * 60, "walk")
    c.money += pay
    c.dirt = min(100.0, c.dirt + 25)
    change_disposition(npc, 5 if roll >= 12 else 0)
    what = {"smith": "working the bellows and hauling charcoal", "stablemaster": "mucking out and carrying feed",
            "farmer": "in the fields"}.get(npc.job, "at whatever needs doing")
    return [f"A long day {what}. {'Good work,' if roll >= 12 else 'Slow work, but'} {npc.first_name} pays you "
            f"<loot>{money_text(pay)}</>."]


def _buy_animal(game, npc, svc, arg):
    animals = game.tables.economy["animals"]
    if arg not in animals or arg.startswith("_"):
        return ["They have no such animal."]
    price = fee(game, npc, int(animals[arg]["price"]))
    ok, why = affordable(game, price)
    if not ok:
        return [f"You can't: {why}."]
    charge(game, npc, price)
    rng = game.world.rng.child(f"animal/{game.world.time}")
    name = rng.choice(["Bess", "Dobbin", "Nell", "Grey", "Jack", "Mouse", "Old Tom", "Clover", "Pepper", "Stubborn"])
    game.leader.animals.append({"kind": arg, "name": name, "unfed": 0, "bought": game.world.time})
    return [f"You buy {animals[arg]['name']} called {name} for {money_text(price)}. "
            f"<dim>It needs a bag of fodder a day, or good grazing outside winter.</>"]


def _sell_animal(game, npc, svc, arg):
    c = game.leader
    i = int(arg or -1)
    if not 0 <= i < len(c.animals):
        return ["You have no such animal."]
    a = c.animals.pop(i)
    price = int(game.tables.economy["animals"][a["kind"]]["price"]) // 2
    c.money += price
    return [f"You sell {a['name']} for {money_text(price)}."]


def _pick_item(game, arg: str | None):
    if not arg or ":" not in arg:
        return None, None
    i, uid = arg.split(":", 1)
    try:
        m = game.party[int(i)]
    except (ValueError, IndexError):
        return None, None
    return m, m.item(int(uid))


def _identify(game, npc: NPC, svc, arg) -> list[str]:
    from realmwalker.game import magic_items

    m, it = _pick_item(game, arg)
    if it is None:
        return ["Show them what?"]
    price = dict((o[0], o[2]) for o in svc.options).get(arg, 0)
    if money(game) < price:
        return [f"You need {money_text(price)}."]
    charge(game, npc, price)
    return [f"{npc.first_name} holds it to the light and murmurs over it for a long while."] + \
        magic_items.identify(game, it)


def _remove_curse(game, npc: NPC, svc, arg) -> list[str]:
    from realmwalker.game import magic_items

    m, it = _pick_item(game, arg)
    if it is None:
        return ["Show them what?"]
    price = dict((o[0], o[2]) for o in svc.options).get(arg, 0)
    if money(game) < price:
        return [f"You need {money_text(price)}."]
    charge(game, npc, price)
    magic_items.lift_curse(it)
    game.pass_time(60, "rest")
    return [f"Candles, bitter smoke and an hour of prayer. At the end of it the {game.tables.items.name(it, False)} "
            f"is only a thing again, and it comes off in your hand when you want it to."]


HANDLERS = {
    "room_common": _room, "room_private": _room, "meal": _meal, "bath": _bath, "perform": _perform, "gamble": _gamble,
    "treat_wounds": _treat, "surgery": _surgery, "herbal_cure": _herbal, "prayer_healing": _prayer,
    "cure_disease": _cure, "repair": _repair, "labour": _labour, "buy_animal": _buy_animal, "sell_animal": _sell_animal,
    "identify": _identify, "remove_curse": _remove_curse,
}


# ---------------------------------------------------------------------------- animals day to day
def feed_animals(game) -> list[str]:
    """Once a day: animals eat a bag of fodder, or graze outside winter, or go hungry and die."""
    c = game.leader
    if not c.animals:
        return []
    msgs = []
    specs = game.tables.economy["animals"]
    p = game.player
    grazing = game.biome_key(p.x, p.y) in game.tables.economy["grazing"] and game.moment.season != "winter"
    in_town = game.world.settlement_at(p.x, p.y) is not None
    for a in list(c.animals):
        fodder = next((it for it in c.inventory if it.def_id == "fodder"), None)
        if fodder is not None:
            from realmwalker.rules.inventory import remove_item

            remove_item(c, fodder.uid, 1)
            a["unfed"] = 0
        elif grazing or in_town:
            a["unfed"] = 0
        else:
            a["unfed"] = a.get("unfed", 0) + 1
            limit = int(specs.get(a["kind"], {}).get("days_without_food", 3))
            if a["unfed"] >= limit:
                c.animals.remove(a)
                msgs.append(f"<danger>{a['name']} the {specs.get(a['kind'], {}).get('name', 'animal')} has starved.</>")
            else:
                msgs.append(f"<warn>{a['name']} has nothing to eat.</> Buy fodder, or find grazing.")
    return msgs


def animal_carry(char, tables) -> int:
    specs = tables.economy["animals"]
    return sum(int(specs.get(a["kind"], {}).get("carry", 0)) for a in char.animals)


def riding_factor(game) -> float:
    """Riding makes open ground and roads quicker (the slowest mount sets the pace; everyone must ride)."""
    c = game.leader
    specs = game.tables.economy["animals"]
    mounts = [float(specs[a["kind"]]["ride"]) for a in c.animals if a["kind"] in specs and float(specs[a["kind"]]["ride"]) < 1.0]
    if not mounts or len(mounts) < len([m for m in game.party if m.alive]):
        return 1.0
    p = game.player
    if game.world.road[p.x, p.y] or game.biome_key(p.x, p.y) in ("plains", "coast", "tundra", "desert", "hills"):
        return max(mounts)
    return 1.0
