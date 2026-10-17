"""What townsfolk can do for you besides talk: trade, and services — inn beds, meals and baths,
performing and dice at the inn, healers' care and surgery, prayers at the temple, smiths' repairs,
animals at the stable, and a day's paid work. Prices are in data/economy.json ("services")."""

from __future__ import annotations

from dataclasses import dataclass, field

from realmwalker.core import dice
from realmwalker.game.people import NPC, change_disposition
from realmwalker.rules.character import Sheet
from realmwalker.rules.inventory import distinct_packs
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
            options = [(g, f"{GRADE_NAMES[g]}: {ROOM_WORDS[g]}", stay_price(game, npc, "stay", g)) for g in grades(game, npc)]
            out.append(Service("room", "A bed for the night", 0, bool(options), "no room", options=options))
            stays = [(f"{g}:{days}", f"{days} days, living {GRADE_NAMES[g].lower()}ly: {LIFE_WORDS[g]}",
                      stay_price(game, npc, "lifestyle", g) * days)
                     for g in grades(game, npc) for days in (3, 7)]
            out.append(Service("stay", "Stay a while: rest, meals and a bed, day after day", 0, bool(stays), "",
                               options=stays))
            out += passage_services(game, npc)
        elif sid == "meal":
            options = [(g, f"{GRADE_NAMES[g]}: {MEAL_WORDS[g]}", stay_price(game, npc, "meal", g)) for g in grades(game, npc)]
            out.append(Service("meal", "Something to eat and drink", 0, bool(options), "no food", options=options))
        elif sid == "bath":
            price = fee(game, npc, econ["bath"], scaled=True)
            out.append(Service("bath", "A hot bath, and your clothes dried by the fire", price, *affordable(game, price)))
        elif sid == "perform":
            done = npc.flags.get("perform_day") == today
            out.append(Service("perform", "[Performance] Sing, play or tell tales for coin", 0, not done,
                               "you've already performed here today"))
        elif sid == "gamble":
            options = [(str(b), f"Bet {money_text(b)}", b) for b in (10, 50, 100, 500)]
            if _carried_use(game, "game", "cards") is not None:
                options += [(f"cards:{b}", f"Cards, {money_text(b)} a hand [Insight]", b) for b in (10, 50, 100, 500)]
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
            packs = distinct_packs(game.party)  # the party shares one: list each thing once
            unknown = [it for m in packs for it in m.inventory if it.magic and not it.magic.get("identified")]
            price = fee(game, npc, 2000)
            options = [(f"{game.party.index(m)}:{it.uid}", game.tables.items.name(it), price)
                       for m in packs for it in m.inventory if it.magic and not it.magic.get("identified")]
            out.append(Service("identify", "Ask what a strange thing is (a donation)", 0, bool(unknown),
                               "you carry nothing strange", options=options))
            cursed = [(f"{game.party.index(m)}:{it.uid}", game.tables.items.name(it), fee(game, npc, 6000))
                      for m in packs for it in m.inventory if it.magic and it.magic.get("cursed")
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
        from realmwalker.game.mounts import vehicle_specs

        carts = vehicle_specs(game.tables)
        town = game.world.settlements[npc.settlement]
        options = [(vid, f"{v['name']} ({v['weight']} lb; seats {v['seats']})", fee(game, npc, int(v["price"])))
                   for vid, v in carts.items() if vid != "carriage" or town.kind in ("town", "city")]
        if options:
            out.append(Service("buy_vehicle", "Buy a cart, a wagon or something finer", 0, True, "", options=options))
        mine = [(str(i), carts[v["kind"]]["name"], int(carts[v["kind"]]["price"]) // 2) for i, v in enumerate(c.vehicles)
                if v.get("kind") in carts]
        if mine:
            out.append(Service("sell_vehicle", "Sell your vehicle", 0, True, "", options=mine))
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
    price = next((pr for a, _, pr in svc.options if a == arg), 0)
    if price > money(game):
        return [f"You can't: you need {money_text(price)}."]
    c = game.leader
    handler = HANDLERS[sid]
    msgs = handler(game, npc, svc, arg)
    if sid in ("prayer_healing", "cure_disease") and game.party[1:]:
        from realmwalker.game.companions import react

        react(game, "prayer", quiet=True)
    game.dirty = True
    npc.remember(f"did business with the traveller on {game.moment.date_text()}")
    return msgs


# ---------------------------------------------------------------------------- inns by lifestyle (PHB 2024 p. 234)
GRADE_NAMES = {"wretched": "Wretched", "squalid": "Squalid", "poor": "Poor", "modest": "Modest",
               "comfortable": "Comfortable", "wealthy": "Wealthy", "aristocratic": "Aristocratic"}
ROOM_WORDS = {"squalid": "straw in the loft over the stable, and whoever else is in it",
              "poor": "a bench in the common room by the fire",
              "modest": "a small room with a lock on the door",
              "comfortable": "a good room, a feather bed, hot water in the morning",
              "wealthy": "the best room in the house, a fire laid, a servant at the door",
              "aristocratic": "a suite fit for a lord, and everyone in the house knows you have it"}
MEAL_WORDS = {"squalid": "yesterday's pottage, scraped from the bottom of the pot",
              "poor": "bread, dripping and small beer",
              "modest": "a bowl of something hot, bread and a mug of ale",
              "comfortable": "a stew with meat in it, cheese and a jug of good ale",
              "wealthy": "roast meat, white bread and wine",
              "aristocratic": "a dinner of many dishes, and the wine keeps coming"}
LIFE_WORDS = {"squalid": "the cheapest bed and the cheapest food", "poor": "plain food and a bench to sleep on",
              "modest": "decent food and a room of your own", "comfortable": "good food and a good room",
              "wealthy": "the best of the house, and people notice",
              "aristocratic": "living like a lord, and all the town talks of it"}


def inn_spec(game) -> dict:
    return game.tables.economy["services"]["inn"]


def grades(game, npc: NPC) -> list[str]:
    """The kinds of lodging and meal this place offers, by its size."""
    s = game.world.settlements[npc.settlement]
    table = inn_spec(game)["grades"]
    return list(table.get(s.kind, table.get("village", [])))


def stay_price(game, npc: NPC, what: str, grade: str) -> int:
    """For the whole party: the book's price for each of them (the innkeeper's mood still counts)."""
    each = int(inn_spec(game)[what].get(grade, 0))
    return fee(game, npc, each * len([c for c in game.party if c.alive])) if each else 0


def _fill(game, grade: str) -> None:
    hunger, thirst = inn_spec(game)["fill"].get(grade, [60, 45])
    for c in game.party:
        c.hunger = max(0.0, c.hunger - hunger)
        c.thirst = max(0.0, c.thirst - thirst)
        if grade not in ("wretched", "squalid"):
            c.body_heat = max(c.body_heat, min(0.0, c.body_heat + 20))


def _bad_food(game, grade: str, rng) -> list[str]:
    from realmwalker.rules import body, health

    out = []
    chance = float(inn_spec(game)["sick"].get(grade, 0.0))
    for c in game.party:
        if chance and rng.chance(chance) and health.expose(c, game.tables, "food_poisoning", rng):
            out.append(f"<warn>{body.first(c)}'s belly does not like it.</>")
    return out


def _night(game, npc: NPC, grade: str, rng, theft: bool = True) -> list[str]:
    """What a night of this kind does, besides the sleep: thieves in a squalid loft, a real bed's deep rest, being
    seen in the best rooms in town."""
    from realmwalker.rules import body

    spec = inn_spec(game)
    out = []
    from realmwalker.game import stonework

    if theft and not stonework.room_locked(game) and rng.chance(float(spec["theft"].get(grade, 0.0))):
        from realmwalker.game import warding

        c = game.leader
        taken = c.money // rng.randint(5, 10)
        guarded = warding.room_thief(game, rng) if taken > 0 else None  # (E.6: a glyph on the door)
        if guarded:
            out.append(guarded)
        elif taken > 0:
            c.money -= taken
            out.append(f"<danger>In the morning your purse is lighter by {money_text(taken)}.</> Nobody saw anything.")
    if spec["rest"].get(grade):
        for c in game.party:
            if c.exhaustion > 0 and c.hunger < 55 and c.thirst < 60:
                c.exhaustion = max(0, c.exhaustion - int(spec["rest"][grade]))
                out.append(f"{body.first(c)} sleeps like the dead in a real bed.")
            c.effects.pop("hangover", None)
    if spec["seen"].get(grade):
        game.renown.flags["seen_living_well"] = [npc.settlement, game.world.time + 3 * DAY, int(spec["seen"][grade])]
    return out


def _room(game, npc, svc, arg):
    from realmwalker.game.fight import rest

    grade = arg if arg in grades(game, npc) else grades(game, npc)[0]
    price = stay_price(game, npc, "stay", grade)
    charge(game, npc, price)
    rng = game.world.rng.child(f"inn/{npc.id}/{game.world.time}")
    msgs = [f"You pay {money_text(price)}: {ROOM_WORDS[grade]}."]
    msgs += rest(game, "night")  # a bed for the night is until morning, not until two in it
    return msgs + _night(game, npc, grade, rng)


def _meal(game, npc, svc, arg):
    grade = arg if arg in grades(game, npc) else grades(game, npc)[0]
    price = stay_price(game, npc, "meal", grade)
    charge(game, npc, price)
    _fill(game, grade)
    game.pass_time(40, "rest")
    rng = game.world.rng.child(f"meal/{npc.id}/{game.world.time}")
    text = MEAL_WORDS[grade]
    return [f"{text[:1].upper()}{text[1:]} ({money_text(price)})." + (" You feel almost human." if grade not in
                                                                     ("squalid", "poor") else "")] + _bad_food(game, grade, rng)


def _stay(game, npc, svc, arg):
    """Days of living at an inn at a lifestyle (PHB 2024: the lifestyle's price a day covers bed and meals): rest,
    meals, and the town's life going on around you."""
    from realmwalker.game.fight import rest

    grade, _, days = (arg or "").partition(":")
    if grade not in grades(game, npc) or not days.isdigit():
        return ["They have no room like that."]
    days = int(days)
    price = stay_price(game, npc, "lifestyle", grade) * days
    charge(game, npc, price)
    rng = game.world.rng.child(f"stay/{npc.id}/{game.world.time}")
    msgs = [f"You pay {money_text(price)} for {days} days: {LIFE_WORDS[grade]}."]
    for _ in range(days):
        start = game.world.time
        _fill(game, grade)
        msgs += _bad_food(game, grade, rng)
        game.pass_time(10 * 60, "rest")  # the day: sitting by the fire, walking the town, mending
        _fill(game, grade)
        rest(game, "night")
        left = start + DAY - game.world.time
        if left > 0:
            game.pass_time(left, "rest")  # (a whole day, whatever hour the sleep ended)
        msgs += [m for m in _night(game, npc, grade, rng) if "<danger>" in m]
    _night(game, npc, grade, rng, theft=False)  # (a last good night's rest, and being seen; no second thief)
    msgs.append(f"{days} days pass{' quietly' if grade in ('modest', 'comfortable') else ''}.")
    return msgs


# ---------------------------------------------------------------------------- coaches, ships, messengers
def passage_services(game, npc: NPC) -> list[Service]:
    from realmwalker.game import passage

    here = game.world.settlements[npc.settlement]
    out = []
    coach = [(f"{s.id}:{miles}:{minutes}", f"{s.name} ({miles} miles)", passage.fare(game, "coach", miles))
             for s, miles, minutes in passage.coach_routes(game, here)]
    if coach:
        out.append(Service("coach", "Take the coach to another town", 0, True, "", options=coach))
    ship = [(f"{s.id}:{miles}:{minutes}", f"{s.name} ({miles} miles by sea)", passage.fare(game, "ship", miles))
            for s, miles, minutes in passage.ship_routes(game, here)]
    if ship:
        out.append(Service("ship", "Buy a passage on a ship", 0, True, "", options=ship))
    jobs = [(str(game.waiting.index(c)), f"{c.name} ({miles} miles away)", price)
            for c, miles, price in passage.messenger_jobs(game, here)]
    if jobs:
        out.append(Service("messenger", "Send a rider to fetch a companion who waits elsewhere", 0, True, "",
                           options=jobs))
    return out


def _passage(game, npc, svc, arg):
    from realmwalker.game import passage

    sid, miles, minutes = (int(v) for v in (arg or "0:0:0").split(":"))
    dest = game.world.settlements[sid]
    price = passage.fare(game, svc.id, miles)
    charge(game, npc, price)
    return passage.travel(game, svc.id, dest, miles, minutes)


def _messenger(game, npc, svc, arg):
    from realmwalker.game import passage

    here = game.world.settlements[npc.settlement]
    jobs = {str(game.waiting.index(c)): (c, miles, price) for c, miles, price in passage.messenger_jobs(game, here)}
    if arg not in jobs:
        return ["There is nobody to send for."]
    c, miles, price = jobs[arg]
    charge(game, npc, price)
    return [passage.send_for(game, c, here, miles)]


def _bath(game, npc, svc, arg):
    charge(game, npc, svc.price)
    for c in game.party:
        c.dirt = 0.0
        c.wet = 0.0
        c.body_heat = max(c.body_heat, 0.0)
    game.pass_time(45, "rest")
    return [f"Hot water, lye soap, and the grime of the road coming off in layers ({money_text(svc.price)})."]


def _carried_use(game, key: str, value=True):
    """The first thing in the party's packs whose `use` has this key (and value), if any."""
    from realmwalker.rules.inventory import carried

    for it in carried(game.party):
        if (game.tables.items.get(it.def_id).get("use") or {}).get(key) == value:
            return it
    return None


def _trained_with(game, c, item) -> bool:
    tool = game.tables.items.get(item.def_id).get("tool") if item is not None else None
    return bool(tool) and tool in c.tools


def _perform(game, npc, svc, arg):
    c = game.leader
    bonus = Sheet(c, game.tables).skill_bonus("performance")
    instrument = _carried_use(game, "music")
    if instrument is not None:
        # An instrument makes a better show than a voice alone, and a much better one in hands taught to play it.
        bonus += 2 + (Sheet(c, game.tables).proficiency if _trained_with(game, c, instrument) else 0)
    rng = game.world.rng.child(f"perform/{npc.id}/{game.world.time}")
    roll = dice.d20(rng).natural
    total = roll + bonus
    npc.flags["perform_day"] = game.moment.total_days
    game.pass_time(90, "rest")
    played = f" with the {game.tables.items.get(instrument.def_id)['name']}" if instrument is not None else ""
    line = f"<dice>Performance{played}: {roll} {'+' if bonus >= 0 else '-'} {abs(bonus)} = {total}</>"
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
    if arg and str(arg).startswith("cards:"):
        return _cards(game, npc, int(str(arg)[6:] or 10))
    bet = int(arg or 10)
    if money(game) < bet:
        return ["You can't cover that bet."]
    rng = game.world.rng.child(f"dice/{npc.id}/{game.world.time}/{bet}")
    c = game.leader
    own = _carried_use(game, "game", "dice")
    knack = 1 if own is not None and _trained_with(game, c, own) else 0  # your own dice, and you know how they fall
    mine = dice.roll("2d6", rng).total + knack
    theirs = dice.roll("2d6", rng).total
    game.pass_time(15, "rest")
    if mine > theirs:
        c.money += bet
        return [f"You throw {mine}; they throw {theirs}. <loot>You win {money_text(bet)}.</>"]
    if mine < theirs:
        charge(game, npc, bet)
        return [f"You throw {mine}; they throw {theirs}. <warn>You lose {money_text(bet)}.</>"]
    return [f"You both throw {mine}. The bets stay on the table."]


def _cards(game, npc, bet: int) -> list[str]:
    """A hand of cards with your own deck: reading faces (Insight, and training with cards) against the table's."""
    if money(game) < bet:
        return ["You can't cover that bet."]
    c = game.leader
    deck = _carried_use(game, "game", "cards")
    if deck is None:
        return ["You have no cards."]
    rng = game.world.rng.child(f"cards/{npc.id}/{game.world.time}/{bet}")
    sheet = Sheet(c, game.tables)
    bonus = sheet.skill_bonus("insight") + (sheet.proficiency if _trained_with(game, c, deck) else 0)
    mine, theirs = dice.d20(rng).natural + bonus, dice.d20(rng).natural + 2
    game.pass_time(20, "rest")
    line = f"<dice>Insight: you {mine}, the table {theirs}</>"
    if mine > theirs:
        c.money += bet
        return [line, f"You read the table better than it reads you. <loot>You win {money_text(bet)}.</>"]
    if mine < theirs:
        charge(game, npc, bet)
        return [line, f"Somebody at the table was bluffing better. <warn>You lose {money_text(bet)}.</>"]
    return [line, "A hand nobody wins. The pot stays on the table."]


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
    taken = {a.get("name") for a in game.leader.animals}
    if name in taken:  # two horses called Bess are one too many
        name = next((n for n in ("Bess", "Dobbin", "Nell", "Grey", "Jack", "Mouse", "Old Tom", "Clover", "Pepper",
                                 "Stubborn", "Ash", "Hob", "Willow", "Brindle", "Sorrel") if n not in taken), name)
    game.leader.animals.append({"kind": arg, "name": name, "unfed": 0, "bought": game.world.time})
    from realmwalker.game import mounts

    how = mounts.summary(game)
    return [f"You buy {animals[arg]['name']} called {name} for {money_text(price)}. "
            f"<dim>It needs a bag of fodder a day, or good grazing outside winter"
            f"{'' if mounts.tack(game) else '; and whoever rides it needs a saddle (the stable sells them)'}.</>"] + ([how] if how else [])


def _sell_animal(game, npc, svc, arg):
    c = game.leader
    i = int(arg or -1)
    if not 0 <= i < len(c.animals):
        return ["You have no such animal."]
    a = c.animals.pop(i)
    price = int(game.tables.economy["animals"][a["kind"]]["price"]) // 2
    c.money += price
    return [f"You sell {a['name']} for {money_text(price)}."]


def _buy_vehicle(game, npc, svc, arg):
    from realmwalker.game import mounts

    carts = mounts.vehicle_specs(game.tables)
    if arg not in carts:
        return ["They have nothing like that."]
    price = fee(game, npc, int(carts[arg]["price"]))
    charge(game, npc, price)
    game.leader.vehicles.append({"kind": arg, "bought": game.world.time})
    if not mounts.pullers(game):
        note = " <warn>Nothing will pull it yet: it needs an animal that nobody rides.</>"
    else:
        note = " " + mounts.summary(game)
    return [f"You buy a {carts[arg]['name']} for {money_text(price)}.{note}"]


def _sell_vehicle(game, npc, svc, arg):
    from realmwalker.game import mounts

    c = game.leader
    i = int(arg or -1)
    if not 0 <= i < len(c.vehicles):
        return ["You have nothing like that to sell."]
    v = c.vehicles.pop(i)
    spec = mounts.vehicle_specs(game.tables)[v["kind"]]
    c.money += int(spec["price"]) // 2
    return [f"You sell the {spec['name']} for {money_text(int(spec['price']) // 2)}."]


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
    "room": _room, "stay": _stay, "meal": _meal, "coach": _passage, "ship": _passage, "messenger": _messenger,
    "bath": _bath, "perform": _perform, "gamble": _gamble,
    "treat_wounds": _treat, "surgery": _surgery, "herbal_cure": _herbal, "prayer_healing": _prayer,
    "cure_disease": _cure, "repair": _repair, "labour": _labour, "buy_animal": _buy_animal, "sell_animal": _sell_animal,
    "buy_vehicle": _buy_vehicle, "sell_vehicle": _sell_vehicle,
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
    stabling = int(game.tables.economy["services"].get("stabling", 0))
    paid = 0
    for a in list(c.animals):
        meat = specs.get(a["kind"], {}).get("eats") == "meat"  # a mastiff: meat, not fodder or grass
        food_ids = ("raw_meat", "cooked_meat", "salt_pork", "dried_fish", "raw_fish") if meat else ("fodder",)
        fodder = next((it for it in c.inventory if it.def_id in food_ids), None)
        if fodder is not None:
            from realmwalker.rules.inventory import remove_item

            remove_item(c, fodder.uid, 1)
            a["unfed"] = 0
        elif in_town and money(game) >= stabling:  # PHB 2024: stabling, 5 sp a day, feed included
            from realmwalker.game.events import pay

            pay(game, stabling)
            paid += stabling
            a["unfed"] = 0
        elif grazing and not meat:
            a["unfed"] = 0
        else:
            a["unfed"] = a.get("unfed", 0) + 1
            limit = int(specs.get(a["kind"], {}).get("days_without_food", 3))
            if a["unfed"] >= limit:
                c.animals.remove(a)
                msgs.append(f"<danger>{a['name']} the {specs.get(a['kind'], {}).get('name', 'animal')} has starved.</>")
            else:
                msgs.append(f"<warn>{a['name']} has nothing to eat.</> Buy fodder, or find grazing.")
    if paid:
        msgs.append(f"<dim>Stabling for the animals: {money_text(paid)}.</>")
    return msgs


def animal_carry(char, tables) -> int:
    specs = tables.economy["animals"]
    total = sum(int(specs.get(a["kind"], {}).get("carry", 0)) for a in char.animals)
    vs = [v for v in char.vehicles if v.get("kind") in tables.economy.get("vehicles", {})]
    if vs:  # the animals nobody rides pull it: five times what they carry, less its weight (game/mounts.py)
        from realmwalker.rules.inventory import pack_mates

        people = len([m for m in pack_mates(char) if m.alive]) or 1
        herd = sorted((a for a in char.animals if a.get("kind") in specs), key=lambda a: float(specs[a["kind"]]["ride"]))
        pull = sum(int(specs[a["kind"]].get("carry", 0)) for a in herd[people:])
        if pull:
            total += max(0, pull * 4 - int(tables.economy["vehicles"][vs[0]["kind"]]["weight"]))
    return total


def riding_factor(game) -> float:
    """Riding makes roads and open ground quicker where the party stands (game/mounts.py has the rules: everyone
    must ride, and the slowest mount ridden sets the pace)."""
    from realmwalker.game import mounts

    p = game.player
    return mounts.step_factor(game, p.x, p.y, p.x, p.y)
