"""What the party's gear is for (after 1.0, Anton's request: "make the items do something").

Most things are used where they are needed and are read elsewhere: a backpack on the back carries more
(`Sheet.capacity`), a focus sharpens a caster's spells (`rules/spells.focus_bonus`), a crowbar forces locks
(`game/dungeon.unlock`), a shovel digs a shelter (`game/camp.build_shelter`), soap washes (`game/survival.wash`), a
spyglass sees further (`GameState.reveal`), navigator's tools keep your bearings (`GameState._check_bearings`),
a string of bells wakes the camp (`game/fight.rest`), cook's utensils make a meal go further (`game/camp.eat_meal`),
instruments, cards and dice play at the inn (`game/services`), papers and rings impress people
(`game/people.first_impression`). Flasks are thrown in a fight like spells (`rules/combat`).

This module has what is done with them:
- wear: weapons, armour, shields and helmets lose a little condition with the blows they give and take
  (`wear_from_battle`, from `fight.finish_battle`); below `battered` they fight worse. A smith mends anything for a fee;
- a whetstone puts an edge on every blade (`hone`): +1 damage until the next fight, and the nicks ground out;
- tools mend what they are made for (`mend`): smith's tools metal, carpenter's tools wood and bone, leatherworker's
  tools leather and cloth, a needle and thread cloth;
- snares and a hunting trap set at camp may catch something by morning (`set_snares`, `check_snares`);
- music, cards or dice in the evening cheer the companions (`evening`);
- an hour's prayer from a prayer book (`pray`);
- prisoners slip their bonds unless tied with rope or chained (`captives_slip`, daily).
The numbers are in data/items.json "upkeep".
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules.character import Character, Sheet
from realmwalker.rules.inventory import add_item, carried, remove_item

EDGED = ("slashing", "piercing")
WEAR_KINDS = ("weapon", "armor", "shield", "helmet")


def upkeep(game) -> dict:
    return game.tables.items.upkeep


def has(game, test) -> tuple[Character | None, object]:
    """The first thing in the party's packs that passes `test(def)`, and who carries it."""
    items = game.tables.items
    for c in game.party:
        for it in c.inventory:
            if test(items.get(it.def_id)):
                return c, it
    return None, None


def first(c: Character) -> str:
    return c.name.split()[0]


# ---------------------------------------------------------------------------- armour on and off
def don_minutes(game, item, on: bool) -> int:
    """Minutes to put this armour on (or take it off), PHB 2024: light 1/1, medium 5/1, heavy 10/5."""
    d = game.tables.items.get(item.def_id)
    if d["category"] != "armor":
        return 0
    pair = upkeep(game).get("don", {}).get(d.get("armor_type", "light"), [0, 0])
    return int(pair[0 if on else 1])


def dressed(game, item, on: bool) -> None:
    """Armour was put on or taken off outside a fight: the minutes pass (buckles, laces, a squire's help)."""
    minutes = don_minutes(game, item, on)
    if minutes and game.battle is None:
        name = game.tables.items.name(item, False)
        game.say(f"{'Buckling on' if on else 'Getting out of'} the {name} takes "
                 f"{minutes} minute{'s' if minutes != 1 else ''}.", "system")
        game.pass_time(minutes, "rest")


# ---------------------------------------------------------------------------- wear
def battered(game, item) -> bool:
    return item is not None and item.condition < int(upkeep(game).get("battered", 30))


def wear_from_battle(game, battle) -> list[str]:
    """Every blow a weapon lands, and every blow armour, a shield or a helmet takes, may cost it a point of condition
    (better-made things wear slower). Returns a line for anything that has just become battered."""
    from realmwalker.rules.combat import PARTY

    spec = upkeep(game).get("wear", {})
    if not spec:
        return []
    items = game.tables.items
    rng = game.world.rng.child(f"wear/{int(game.world.politics.get('next_battle', 0))}")
    gave: dict[int, int] = {}
    took: dict[int, int] = {}
    for ev in battle.events:
        if ev.get("kind") != "attack" or not ev.get("hit"):
            continue
        if ev.get("melee"):
            gave[ev["by"]] = gave.get(ev["by"], 0) + 1
        took[ev["to"]] = took.get(ev["to"], 0) + 1
    out = []

    def worn(it, chance: float, blows: int) -> None:
        if it is None or blows <= 0 or it.magic:
            return  # magic things do not wear
        durability = float(items.qualities.get(it.quality, {}).get("durability", 1.0)) or 1.0
        lost = sum(1 for _ in range(blows) if rng.chance(chance / durability))
        if not lost:
            return
        was = battered(game, it)
        it.condition = max(0, it.condition - lost)
        if battered(game, it) and not was:
            out.append(f"<warn>The {items.name(it, False)} is battered now</> and needs mending (a smith, or tools).")

    for f in battle.side(PARTY):
        c = f.char
        if c is None:
            continue
        main = c.equipped_item("main_hand")
        if main is not None and items.category(main) == "weapon":
            worn(main, float(spec.get("weapon", 0)), gave.get(f.id, 0))
        hits = took.get(f.id, 0)
        worn(c.equipped_item("armor"), float(spec.get("armor", 0)), hits)
        off = c.equipped_item("off_hand")
        if off is not None and items.category(off) == "shield":
            worn(off, float(spec.get("shield", 0)), hits)
        worn(c.equipped_item("helmet"), float(spec.get("helmet", 0)), hits)
        c.effects.pop("honed", None)  # the edge is gone with the fight
    return out


# ---------------------------------------------------------------------------- a whetstone
def edged(game, item) -> bool:
    d = game.tables.items.get(item.def_id)
    return d["category"] == "weapon" and d.get("damage_type") in EDGED and "ranged" not in d.get("properties", [])


def hone(game) -> list[str]:
    """Twenty minutes with a whetstone: every blade the party carries gets an edge (+1 damage with it until the next
    fight) and is ground back up to `restore` condition if it was worse."""
    spec = upkeep(game).get("hone", {})
    _, stone = has(game, lambda d: (d.get("use") or {}).get("hone"))
    if stone is None:
        return ["You have no whetstone."]
    blades = [it for it in carried(game.party) if edged(game, it)]
    if not blades:
        return ["You carry nothing with an edge to sharpen."]
    restore = int(spec.get("restore", 60))
    ground = [it for it in blades if it.condition < restore and not it.magic]
    for it in ground:
        it.condition = restore
    armed = []
    for c in game.party:
        main = c.equipped_item("main_hand")
        off = c.equipped_item("off_hand")
        if c.alive and any(w is not None and edged(game, w) for w in (main, off)):
            c.effects["honed"] = 24.0
            armed.append(first(c))
    game.pass_time(int(spec.get("minutes", 20)), "rest")
    out = [f"You work the whetstone along every edge you carry until it bites. "
           f"<good>+{int(spec.get('damage', 1))} damage with a blade until your next fight</>"
           + (f" ({', '.join(armed)})." if armed and len(game.party) > 1 else ".")]
    if ground:
        out.append(f"The worst nicks are ground out of the {', '.join(sorted({game.tables.items.name(it, False) for it in ground}))}.")
    return out


# ---------------------------------------------------------------------------- mending
def tools_for(game, item) -> list[tuple[object, dict]]:
    """(the tool, its 'mends') for each tool in the packs that can mend this thing."""
    items = game.tables.items
    material = items.get(item.def_id).get("material", "")
    out = []
    for tool in carried(game.party):
        mends = items.get(tool.def_id).get("mends")
        if mends and material in mends["materials"]:
            out.append((tool, mends))
    return out


def mend_plan(game) -> list[tuple[object, object, int, Character]]:
    """(thing, tool, condition it would reach, who does it): the most worn first, each with the tool that does best."""
    spec = upkeep(game).get("mend", {})
    items = game.tables.items
    plan = []
    for it in carried(game.party):
        if items.category(it) not in ("weapon", "armor", "shield", "helmet", "clothing") or it.condition >= 100:
            continue
        best = None
        for tool, mends in tools_for(game, it):
            prof = items.get(tool.def_id).get("tool")
            trained = next((c for c in game.party if c.alive and prof and prof in c.tools), None)
            hands = trained or next((c for c in game.party if c.alive), game.leader)
            cap = int(mends.get("cap") or (spec.get("cap_trained", 100) if trained else spec.get("cap", 75)))
            step = int(spec.get("step_trained", 40) if trained else spec.get("step", 25))
            reach = min(cap, it.condition + step)
            if reach > it.condition and (best is None or reach > best[2]):
                best = (it, tool, reach, hands)
        if best is not None:
            plan.append(best)
    plan.sort(key=lambda p: p[0].condition)
    return plan[: int(spec.get("items", 3))]


def has_mending_tools(game) -> bool:
    return has(game, lambda d: bool(d.get("mends")))[1] is not None


def mend(game) -> list[str]:
    """An hour's work on the most worn gear the party's tools can mend."""
    if not has_mending_tools(game):
        return ["You have nothing to mend gear with (smith's, carpenter's or leatherworker's tools, or a needle and "
                "thread)."]
    plan = mend_plan(game)
    if not plan:
        return ["Nothing you carry needs mending that your tools could improve."]
    items = game.tables.items
    lines = []
    for it, tool, reach, who in plan:
        it.condition = reach
        lines.append(f"{first(who)} mends the {items.name(it, False)} with the {items.get(tool.def_id)['name']} "
                     f"<dim>({items.condition_word(it)})</>.")
    game.pass_time(int(upkeep(game).get("mend", {}).get("minutes", 60)), "rest")
    return lines


# ---------------------------------------------------------------------------- snares and traps
def snare_item(game):
    """The best trap the party carries: a hunting trap before snares."""
    best = None
    for it in carried(game.party):
        spec = (game.tables.items.get(it.def_id).get("use") or {}).get("snare")
        if spec and (best is None or spec.get("big") and not best[1].get("big")):
            best = (it, spec)
    return best


def snare_problem(game) -> str | None:
    from realmwalker.game.camp import by_land

    if snare_item(game) is None:
        return "you have no snares or trap"
    if game.world.settlement_at(game.player.x, game.player.y) is not None:
        return "not in a town"
    if game.local is not None and game.local.kind == "dungeon":
        return "not under the ground"
    if by_land(game, game.tables.camping.get("hunt", {})) is None:
        return "there is no game here"
    return None


def set_snares(game) -> list[str]:
    from realmwalker.game.camp import make_camp

    why = snare_problem(game)
    if why:
        return [f"You can't set them: {why}."]
    camp = make_camp(game)
    if camp.snares:
        return ["The snares are already set."]
    it, spec = snare_item(game)
    camp.snares = it.def_id
    game.pass_time(20, "walk")
    name = game.tables.items.get(it.def_id)["name"]
    return [f"You set the {name} along the game trails near the camp. Sleep, and see in the morning."]


def check_snares(game) -> list[str]:
    """After a night's sleep: is there anything in them? A Survival check against the land's hunting DC; snares take
    only small game, a hunting trap anything."""
    from realmwalker.game.camp import by_land, camp_here, check

    camp = camp_here(game)
    if camp is None or not camp.snares:
        return []
    def_id, camp.snares = camp.snares, ""
    spec = (game.tables.items.get(def_id).get("use") or {}).get("snare", {})
    hunt = by_land(game, game.tables.camping.get("hunt", {}))
    if hunt is None:
        return []
    winter = 2 if game.moment.season == "winter" else 0
    dc = int(hunt["dc"]) + int(upkeep(game).get("snare", 2)) + winter
    ok, roll = check(game, "survival", dc, int(spec.get("bonus", 0)), tag="snares")
    name = game.tables.items.get(def_id)["name"]
    if not ok:
        return [roll, f"The {name} are empty in the morning." if def_id == "snares" else f"The {name} is empty."]
    rng = game.world.rng.child(f"snared/{game.world.time}/{game.player.x},{game.player.y}")
    choices = [g for g in hunt["game"] if spec.get("big") or not g[3]]
    if not choices:
        return [roll, f"The {name} {'are' if def_id == 'snares' else 'is'} sprung, and empty."]
    names = [g[0] for g in choices]
    beast, _, meat, hide = choices[names.index(rng.weighted(names, [float(g[1]) for g in choices]))]
    n = max(1, dice.roll(str(meat), rng).total)
    add_item(game.leader, game.tables.items, "raw_meat", n, made_at=game.world.time)
    got = [f"raw meat ×{n}" if n > 1 else "raw meat"]
    if hide:
        add_item(game.leader, game.tables.items, hide, 1, made_at=game.world.time)
        got.append(game.tables.items.get(hide)["name"])
    if game.world.factions:
        from realmwalker.game import law

        law.poaching_check(game)
    return [roll, f"<good>In the {name}: {beast}.</> {', '.join(got).capitalize()}. Cook it before it turns."]


# ---------------------------------------------------------------------------- the evening
def evening_problem(game) -> str | None:
    from realmwalker.game.companions import companions

    if not companions(game):
        return "there is nobody to play for"
    if game.leader.uses.get("evening_day") == game.moment.total_days:
        return "you have already passed this evening"
    music, games = pastimes(game)
    if music is None and games is None:
        return "you have no instrument, cards or dice"
    return None


def pastimes(game):
    """(the instrument and the best player for it, the cards or dice) the party carries."""
    items = game.tables.items
    music = None
    games = None
    for it in carried(game.party):
        use = items.get(it.def_id).get("use") or {}
        if use.get("music"):
            player = max((c for c in game.party if c.alive), key=lambda c: _music_bonus(game, c, it))
            if music is None or _music_bonus(game, player, it) > _music_bonus(game, music[1], music[0]):
                music = (it, player)
        elif use.get("game") and games is None:
            games = it
    return music, games


def _music_bonus(game, c: Character, instrument) -> int:
    tool = game.tables.items.get(instrument.def_id).get("tool")
    s = Sheet(c, game.tables)
    return s.skill_bonus("performance") + (s.proficiency if tool and tool in c.tools else 0)


def evening(game) -> list[str]:
    """An hour by the fire with music, or a game of cards or dice: every companion's loyalty rises a little (music
    played well more than a game), as far as content but never to devoted. Once a day."""
    from realmwalker.game.companions import change_loyalty, companions

    why = evening_problem(game)
    if why:
        return [f"Not tonight: {why}."]
    spec = upkeep(game).get("evening", {})
    music, games = pastimes(game)
    game.leader.uses["evening_day"] = game.moment.total_days
    rng = game.world.rng.child(f"evening/{game.moment.total_days}")
    out = []
    if music is not None:
        it, player = music
        roll = dice.d20(rng).natural
        bonus = _music_bonus(game, player, it)
        dc = int(spec.get("dc", 12))
        out.append(f"<dice>Performance ({first(player)}): {roll} {'+' if bonus >= 0 else '-'} {abs(bonus)} = "
                   f"{roll + bonus} vs DC {dc}</>")
        name = game.tables.items.get(it.def_id)["name"]
        if roll + bonus >= dc:
            lift = float(spec.get("music", 3))
            out.append(f"{first(player)} plays the {name} by the fire, and for an hour nobody thinks about the road.")
        else:
            lift = float(spec.get("game", 2)) / 2
            out.append(f"{first(player)} plays the {name}. Badly, but it passes the evening, and there is laughing.")
    else:
        lift = float(spec.get("game", 2))
        kind = (game.tables.items.get(games.def_id).get("use") or {}).get("game", "dice")
        out.append("Cards by the fire, for pebbles and boasts, until the fire burns low." if kind == "cards" else
                   "Dice by the fire, for pebbles and boasts, until the fire burns low.")
    cap = float(spec.get("cap", 70))  # good company makes people content; devotion is earned by deeds
    for c in companions(game):
        change_loyalty(c, max(0.0, min(lift, cap - float(c.companion.get("loyalty", 50)))))
    out.append(f"<good>The company is in better spirits</> <dim>(loyalty +{lift:g}, up to {cap:g})</>.")
    game.pass_time(int(spec.get("minutes", 60)), "rest")
    return out


# ---------------------------------------------------------------------------- prayer
def pray_problem(game, char: Character) -> str | None:
    if not char.alive or char.hp <= 0:
        return f"{first(char)} is in no state to"
    if char.uses.get("prayed_day") == game.moment.total_days:
        return f"{first(char)} has prayed today already"
    if has(game, lambda d: (d.get("use") or {}).get("pray"))[1] is None:
        return "you have no prayer book"
    if game.busy:
        return "not now"
    return None


def pray(game, char: Character) -> list[str]:
    """An hour's prayer from the book, once a day. It steadies whoever prays (+1 to Wisdom saves for some hours) and
    gives a priest back spent spells, as a wizard's Arcane Recovery does (spell levels up to half their level, rounded
    up). Burning a block of incense with it steadies the whole party."""
    why = pray_problem(game, char)
    if why:
        return [f"Not now: {why}."]
    hours = float(upkeep(game).get("prayer", 12))
    char.uses["prayed_day"] = game.moment.total_days
    burner, incense = next(((c, it) for c in game.party for it in c.inventory if it.def_id == "incense"), (None, None))
    who = [char]
    out = [f"{first(char)} kneels and prays from the book for an hour."]
    if incense is not None:
        remove_item(burner, incense.uid, 1)
        who = [c for c in game.party if c.alive]
        out.append("The incense smoke goes up sweet and grey, and the words reach everyone in the camp.")
    for c in who:
        c.effects["steadied"] = hours
    out.append(f"<good>{'Everyone is' if len(who) > 1 else first(char) + ' is'} steadied</> "
               f"<dim>(+1 to Wisdom saves for {hours:g} hours)</>.")
    if char.cls == "cleric" and char.spells:
        used = char.spells.setdefault("slots_used", [0] * 9)
        budget = max(1, (char.level + 1) // 2)
        back = []
        for i in range(min(5, len(used))):
            while used[i] and budget >= i + 1:
                used[i] -= 1
                budget -= i + 1
                back.append(i + 1)
        if back:
            out.append(f"<magic>The god is listening: {first(char)} has back "
                       f"{'a spent prayer' if len(back) == 1 else str(len(back)) + ' spent prayers'} "
                       f"(level {', '.join(str(b) for b in back)}).</>")
    from realmwalker.game import magic_items

    magic_items.notice(game, "prayer")
    if game.party[1:]:
        from realmwalker.game.companions import react

        react(game, "prayer")
    game.pass_time(60, "rest")
    return out


# ---------------------------------------------------------------------------- prisoners
def binding(game, n: int) -> list[str]:
    """How each of n prisoners is bound: in manacles while there are pairs, then with rope if there is any, then with
    whatever is to hand."""
    items = game.tables.items
    pairs = sum(it.qty for it in carried(game.party) if items.get(it.def_id).get("bind") == "manacles")
    rope = any(items.get(it.def_id).get("bind") == "rope" for it in carried(game.party))
    return ["manacles" if i < pairs else ("rope" if rope else "none") for i in range(n)]


def captives_slip(game) -> list[str]:
    """Each day, a prisoner bound with nothing better than a belt may slip away in the night; rope holds most; nobody
    slips manacles."""
    captives = game.renown.flags.get("captives") or []
    if not captives:
        return []
    chances = upkeep(game).get("escape", {})
    rng = game.world.rng.child(f"slip/{game.moment.total_days}")
    kept, out = [], []
    for cap, how in zip(list(captives), binding(game, len(captives))):
        if rng.chance(float(chances.get(how, 0.0))):
            out.append(f"<warn>In the night {cap['name']} slipped the {'cords' if how == 'rope' else 'knots'} and is "
                       f"gone.</>" + (" Rope would have held better; manacles better still." if how == "none" else ""))
        else:
            kept.append(cap)
    game.renown.flags["captives"] = kept
    for line in out:
        game.say(line, "warn")
    return out


# ---------------------------------------------------------------------------- the pack: what each thing is for
def use_name(game, item) -> str | None:
    """The pack's verb for a thing with a use of its own (None: no use from the pack)."""
    use = game.tables.items.get(item.def_id).get("use") or {}
    if use.get("hone"):
        return "Sharpen blades"
    if use.get("mend"):
        return "Mend gear"
    if use.get("snare"):
        return "Set it for the night"
    if use.get("music") or use.get("game"):
        return "Pass the evening"
    if use.get("pray"):
        return "Pray"
    if use.get("scribe"):
        return "Write a scroll"
    if use.get("throw"):
        return "Throw (in a fight)"
    if use.get("coat"):
        return "Coat a blade (in a fight)"
    if use.get("drink") == "antitoxin":
        return "Drink the antitoxin"
    if game.tables.items.get(item.def_id).get("pack"):
        return "Open the pack"
    return None


def open_pack(game, char: Character, item) -> list[str]:
    """A bought pack (PHB 2024: the explorer's, the priest's...) becomes what is in it."""
    items = game.tables.items
    contents = items.get(item.def_id).get("pack") or []
    if remove_item(char, item.uid, 1) is None:
        return ["It will not come open."]
    got = []
    for def_id, qty in contents:
        add_item(char, items, def_id, int(qty), made_at=item.made_at)
        got.append(f"{items.get(def_id)['name']}" + (f" ×{int(qty)}" if int(qty) > 1 else ""))
    return [f"You unpack the {items.get(item.def_id)['name']}: {', '.join(got)}."]


def drink_antitoxin(game, char: Character, item) -> list[str]:
    """PHB 2024: for an hour, advantage on saving throws against being poisoned."""
    if remove_item(char, item.uid, 1) is None:
        return ["There is none left."]
    char.effects["antitoxin"] = 1.0
    return [f"{first(char)} drinks the antitoxin: it tastes of chalk and bitter root. For an hour, poison takes "
            f"less hold of them (advantage on saves against being poisoned)."]


def use_item(game, char: Character, item) -> list[str]:
    """What happens on Enter in the pack for a thing used from it."""
    name = use_name(game, item)
    if name == "Sharpen blades":
        return hone(game)
    if name == "Mend gear":
        return mend(game)
    if name == "Set it for the night":
        return set_snares(game)
    if name == "Pass the evening":
        return evening(game)
    if name == "Pray":
        return pray(game, char)
    if name == "Write a scroll":
        return ["Choose the spell to write on the Spells screen (S), then w. It needs a sheet of parchment, costly inks "
                "and one of the day's spells."]
    if name in ("Throw (in a fight)", "Coat a blade (in a fight)"):
        use = game.tables.items.get(item.def_id).get("use") or {}
        spell = game.tables.spells[use.get("throw") or "coat_poison"]
        return [f"In a fight, the Item menu (u) lists it: {spell['text']}"]
    if name == "Open the pack":
        return open_pack(game, char, item)
    if name == "Drink the antitoxin":
        return drink_antitoxin(game, char, item)
    return [how_text(game, item)]


def how_text(game, item) -> str:
    d = game.tables.items.get(item.def_id)
    if d.get("how"):
        return d["how"]
    if d.get("tool") and d["category"] == "tool":
        return "Those trained with it use it where it is needed: there is nothing to do with it from the pack."
    return "You can't use that here. (Bandages, herbs and kits are used on the Health screen, h.)"
