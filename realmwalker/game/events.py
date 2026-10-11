"""Travel events that are not (at first) fights: pedlars, pilgrims, patrols, refugees, a wounded
stranger, abandoned camps, hunters, shrines... All from data/travel_events.json.

An event is met while walking (like a hostile encounter, but likelier on roads). The player picks
an option; code applies the outcome (items, money, experience, deeds, news, a fight...).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.rules import body
from realmwalker.rules.character import Sheet
from realmwalker.rules.inventory import add_item, remove_item
from realmwalker.rules.items import money_text

EVENT_CHANCE_PER_HOUR = {True: 0.035, False: 0.015}  # on a road / off it


@dataclass
class PendingEvent:
    event_id: str
    intro: str
    seed: int
    done: bool = False
    result: list[str] = field(default_factory=list)


def event_chance(on_road: bool, minutes: float) -> float:
    return min(0.5, EVENT_CHANCE_PER_HOUR[on_road] * minutes / 60.0)


def fits(spec: dict, game, x: int, y: int, night: bool) -> bool:
    where = spec["where"]
    w = game.world
    on_road = bool(w.road[x, y])
    if "road" in where and where["road"] != on_road:
        return False
    biomes = where.get("biomes", ["any"])
    if "any" not in biomes and game.biome_key(x, y) not in biomes and game.land_key(x, y) not in biomes:
        return False
    lo, hi = where.get("danger", [0, 10])
    if not lo <= int(w.danger[x, y]) <= hi:
        return False
    time = where.get("time", "any")
    if time == "day" and night or time == "night" and not night:
        return False
    season = where.get("season", "any")
    if season != "any" and game.moment.season not in season:
        return False
    return True


def roll_event(game, minutes: float) -> PendingEvent | None:
    w = game.world
    p = game.player
    if w.settlement_at(p.x, p.y) is not None or game.busy or game.over is not None:
        return None
    rng = w.rng.child(f"event/{w.time}/{p.x},{p.y}")
    if not rng.chance(event_chance(bool(w.road[p.x, p.y]), minutes)):
        return None
    night = game.light < 0.5
    options = [(eid, e) for eid, e in game.tables.travel_events.items() if fits(e, game, p.x, p.y, night)]
    if not options:
        return None
    weights = [float(o[1]["weight"]) for o in options]
    if getattr(w, "wars", None):
        from realmwalker.world.politics import war_near

        if war_near(w, p.x, p.y):
            weights = [wt * (3.0 if eid in ("refugees", "hungry_deserters", "patrol") else 1.0)
                       for (eid, _), wt in zip(options, weights)]
    eid = rng.weighted([o[0] for o in options], weights)
    return PendingEvent(eid, rng.choice(game.tables.travel_events[eid]["intro"]), rng.randint(0, 2**30))


def make_event(game, eid: str) -> PendingEvent:
    rng = game.world.rng.child(f"event/{game.world.time}/{eid}")
    return PendingEvent(eid, rng.choice(game.tables.travel_events[eid]["intro"]), rng.randint(0, 2**30))


# ---------------------------------------------------------------------------- options
def count_item(game, item_id: str) -> int:
    from realmwalker.rules.inventory import carried

    return sum(it.qty for it in carried(game.party) if it.def_id == item_id)


def party_money(game) -> int:
    return sum(c.money for c in game.party)


def option_state(game, option: dict) -> tuple[bool, str]:
    req = option.get("requires", {})
    for item_id, qty in req.get("items", []):
        if count_item(game, item_id) < int(qty):
            return False, f"you need {game.tables.items.get(item_id)['name']} ×{qty}"
    if party_money(game) < int(req.get("money", 0)):
        return False, f"you need {money_text(int(req['money']))}"
    return True, ""


def options(game, ev: PendingEvent) -> list[tuple[str, bool, str]]:
    """(label, possible, why not) for each option."""
    out = []
    for opt in game.tables.travel_events[ev.event_id]["options"]:
        ok, why = option_state(game, opt)
        label = opt["label"]
        if "check" in opt:
            c = opt["check"]
            skill = game.tables.rules["skills"][c["skill"]]["name"]
            # "[Persuasion] Argue that you are exempt (DC 13)", not "... (Persuasion, DC 13)" as well
            label += f" (DC {c['dc']})" if label.startswith(f"[{skill}]") else f" ({skill}, DC {c['dc']})"
        out.append((label, ok, why))
    return out


def choose(game, ev: PendingEvent, index: int) -> dict | None:
    """Carry out an option. Returns the option's shop spec if it opens a shop (the event goes on);
    otherwise applies the outcome, ends the event, and fills ev.result with what happened."""
    spec = game.tables.travel_events[ev.event_id]
    opt = spec["options"][index]
    ok, why = option_state(game, opt)
    if not ok:
        ev.result = [f"You can't: {why}."]
        return None
    if "shop" in opt:
        return opt["shop"]
    rng = RNG(ev.seed + index * 7919, f"event/{ev.event_id}")
    msgs = []
    outcome = opt.get("outcome")
    if "check" in opt:
        c = opt["check"]
        who, bonus = best_at(game, c["skill"])
        roll = dice.d20(rng).natural
        total = roll + bonus
        sign = "+" if bonus >= 0 else "-"
        name = game.tables.rules["skills"][c["skill"]]["name"]
        msgs.append(f"<dice>{name} ({who.name.split()[0]}): {roll} {sign} {abs(bonus)} = {total} vs DC {c['dc']}</>")
        outcome = c["success"] if total >= int(c["dc"]) else c["failure"]
    msgs += apply_outcome(game, outcome or {}, rng)
    ev.result = msgs
    ev.done = True
    for m in msgs:
        game.say(m, "info")
    game.dirty = True
    return None


def best_at(game, skill: str):
    able = [c for c in game.party if c.alive and c.hp > 0] or game.party
    c = max(able, key=lambda c: Sheet(c, game.tables).skill_bonus(skill))
    return c, Sheet(c, game.tables).skill_bonus(skill)


def apply_outcome(game, out: dict, rng: RNG) -> list[str]:
    leader = game.leader
    msgs = []
    if out.get("text"):
        msgs.append(rng.choice(out["text"]).replace("{name}", leader.name.split()[0]))
    got = []
    for item_id, qty in out.get("items", []):
        n = dice.roll(str(qty), rng).total if isinstance(qty, str) else int(qty)
        if n > 0:
            add_item(leader, game.tables.items, item_id, n, made_at=game.world.time)
            got.append(f"{game.tables.items.get(item_id)['name']}" + (f" ×{n}" if n > 1 else ""))
        elif n < 0:
            take_items(game, item_id, -n)
    for item_id, amount, chance in out.get("loot", []):
        if rng.chance(float(chance)):
            n = max(1, dice.roll(str(amount), rng).total)
            add_item(leader, game.tables.items, item_id, n, made_at=game.world.time)
            got.append(f"{game.tables.items.get(item_id)['name']}" + (f" ×{n}" if n > 1 else ""))
    money = int(out.get("money", 0))
    if money > 0:
        leader.money += money
        got.append(money_text(money))
    elif money < 0:
        pay(game, -money)
        msgs.append(f"<dim>({money_text(-money)} spent.)</>")
    if got:
        msgs.append(f"<loot>You gain {', '.join(got)}.</>")
    if out.get("fatigue"):
        for c in game.party:
            c.fatigue = max(0.0, min(100.0, c.fatigue + float(out["fatigue"])))
    if out.get("effect"):
        name, hours = out["effect"]
        for c in game.party:
            c.effects[name] = float(hours)
    if out.get("deed"):
        if game.world.factions:
            from realmwalker.game.reputation import deed, realm_here

            realm = realm_here(game)
            deed(game, out["deed"], {realm.id: 2.0} if realm is not None else {}, fame=1)
            if game.party[1:]:
                from realmwalker.game.companions import react

                react(game, "charity" if int(out.get("money", 0)) < 0 else "help_poor")
        else:
            leader.deeds.append(out["deed"])
    if out.get("news"):
        msgs.append(hear_news(game, rng))
    if out.get("xp"):
        from realmwalker.rules.progression import award_xp

        for c in game.party:
            if c.alive:
                msgs += award_xp(c, int(out["xp"]), game.tables, rng)
        msgs.append(f"<good>+{int(out['xp'])} experience.</>")
    if out.get("hurt"):
        lost = dice.roll(str(out["hurt"]), rng).total
        leader.hp = max(1, leader.hp - lost)  # a bad landing, not a death
        msgs.append(f"<warn>{leader.name.split()[0]} loses {lost} hit points.</>")
    if out.get("time"):
        game.pass_time(int(out["time"]), "rest")
    if out.get("until_dawn"):
        game.pass_time(game.minutes_to_dawn(), "sleep")
    if out.get("let_in") or out.get("until_dawn"):
        here = game.world.settlement_at(game.player.x, game.player.y)
        if here is not None:
            game.let_in = (here.id, game._night_of())
            msgs.append("<dim>(> to go in.)</>")
    fight = out.get("fight")
    if not fight and out.get("ambush"):
        group, chance = out["ambush"]
        if rng.chance(float(chance)):
            fight = group
            msgs.append("<danger>You are not alone.</>")
    if fight and fight in game.tables.creatures.encounters and game.over is None:
        from realmwalker.game.encounters import make_encounter

        game.encounter = make_encounter(game, fight, rng)
    return msgs


def take_items(game, item_id: str, qty: int) -> None:
    for c in game.party:
        for it in list(c.inventory):
            if qty <= 0:
                return
            if it.def_id == item_id:
                n = min(qty, it.qty)
                remove_item(c, it.uid, n)
                qty -= n


def pay(game, amount: int) -> None:
    for c in game.party:
        n = min(c.money, amount)
        c.money -= n
        amount -= n
        if amount <= 0:
            return


def hear_news(game, rng: RNG) -> str:
    """Travellers' talk: news from the wider world if any has reached here, else a place you did not know."""
    if getattr(game.world, "news", None):
        from realmwalker.game import news

        heard = news.hear(game, count=1, rng=rng)
        if heard:
            return heard[0]
    return hear_place(game, rng) or "They tell you nothing you do not already know."


HEARSAY_REACH = 40  # tiles (120 miles): nobody in a village talks about a ruin a fortnight's walk away


def hear_place(game, rng: RNG) -> str | None:
    """Learn of a place you did not know: the nearest unknown site or settlement, if there is one near enough for
    anyone here to talk about (None when there is not)."""
    p = game.player
    w = game.world
    near = lambda s: max(abs(s.x - p.x), abs(s.y - p.y)) <= HEARSAY_REACH  # noqa: E731
    unknown_sites = [s for s in w.sites if not p.explored[s.x, s.y] and near(s)]
    unknown_towns = [s for s in w.settlements if s.id not in p.known_settlements and near(s)]
    pool = [("site", s) for s in unknown_sites] + [("town", s) for s in unknown_towns]
    if not pool:
        return None
    kind, place = min(pool, key=lambda t: abs(t[1].x - p.x) + abs(t[1].y - p.y) + rng.random() * 4)
    miles = int(round(((place.x - p.x) ** 2 + (place.y - p.y) ** 2) ** 0.5 * 3))
    direction = compass(place.x - p.x, place.y - p.y)
    if kind == "town":
        p.known_settlements.add(place.id)
        return f"<info>You hear of {place.name}, about {miles} miles to the {direction}.</> (It is on your map now.)"
    p.explored[place.x, place.y] = True
    return (f"<info>You hear of {place.name}, about {miles} miles to the {direction}. People who go there don't "
            f"always come back.</> (It is on your map now.)")


def compass(dx: int, dy: int) -> str:
    import math

    if dx == 0 and dy == 0:
        return "here"
    angle = (math.degrees(math.atan2(-dy, dx)) + 360) % 360
    names = ["east", "north-east", "north", "north-west", "west", "south-west", "south", "south-east"]
    return names[int((angle + 22.5) // 45) % 8]


# ---------------------------------------------------------------------------- buying from a travelling trader
def shop_price(game, item_id: str, markup: float) -> int:
    return max(1, int(round(game.tables.items.get(item_id)["value"] * markup)))


def buy(game, item_id: str, markup: float, stock: dict) -> str:
    if stock.get(item_id, 0) <= 0:
        return "There are none left."
    price = shop_price(game, item_id, markup)
    if party_money(game) < price:
        return f"You can't afford it ({money_text(price)})."
    pay(game, price)
    stock[item_id] -= 1
    it = add_item(game.leader, game.tables.items, item_id, 1, made_at=game.world.time)
    if game.tables.items.get(item_id).get("container"):
        from realmwalker.rules.inventory import fill_containers

        fill_containers(game.leader, game.tables.items, "clean")
    game.dirty = True
    return f"You buy {game.tables.items.name(it, with_qty=False)} for {money_text(price)}."


def _and(words: list[str]) -> str:
    """grassland; grassland and forest; grassland, forest and hills."""
    words = list(words)
    return ", ".join(words[:-1]) + " and " + words[-1] if len(words) > 1 else "".join(words)


def travel_day_facts(game, day: dict) -> dict:
    """Variables for the day's narrated passage (AI prompt or built-in text)."""
    c = game.leader
    moods = []
    for key in ("hunger", "thirst", "fatigue"):
        st = body.stage(key, getattr(c, key))
        if st:
            moods.append(st[0])
    st = body.heat_stage(c.body_heat)
    if st:
        moods.append(st[0])
    if c.wounds:
        moods.append("wounded")
    return {
        "name": c.name.split()[0], "miles": day.get("miles", 0), "lands": _and(day.get("lands", [])) or "open country",
        "weather": day.get("weather", "grey skies"), "sky": day.get("sky", "overcast"),
        "mood": ", ".join(moods) or "well enough",
        "season": game.moment.season, "events": "; ".join(day.get("events", [])) or "nothing much",
        "road": "mostly on the road" if day.get("road", 0) > day.get("off_road", 0) else "mostly across country",
    }
