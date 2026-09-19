"""Fights at the level of the whole game: starting a battle, and living with the outcome.

The Battle (rules/combat.py) resolves blows. This module decides what happens around it: who is
surprised, what time passes, experience, loot, captives, robbery, and death.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from realmwalker.core import dice
from realmwalker.rules import progression
from realmwalker.rules.combat import FEARLESS, FOE, MERCIFUL, PARTY, Battle, BattleResult, Env
from realmwalker.rules.creatures import Creature
from realmwalker.rules.inventory import add_existing, remove_item
from realmwalker.rules.items import Item, money_text

ROUND_SECONDS = 6


@dataclass
class Aftermath:
    outcome: str
    text: str
    xp: int = 0
    notes: list[str] = field(default_factory=list)
    loot: list[Item] = field(default_factory=list)
    money: int = 0
    captives: list[Creature] = field(default_factory=list)
    fates: dict[int, str] = field(default_factory=dict)  # creature uid -> fate chosen
    significant: bool = False
    carcasses: list[Creature] = field(default_factory=list)  # dead beasts that could be butchered


def party_has_light(game) -> bool:
    for c in game.party:
        for slot, uid in c.equipped.items():
            it = c.item(uid)
            if it is not None and game.tables.items.get(it.def_id).get("light"):
                return True
    return False


def battle_env(game, surprised: str | None) -> Env:
    lm = game.local
    ground = "grass"
    if lm is not None:
        t = game.tables.terrain[int(game.remap_for(lm)[lm.terrain[game.player.lx, game.player.ly]])]
        ground = t["name"]
    else:
        ground = game.biome_def(game.player.x, game.player.y)["name"]
    light = game.light
    indoors = lm is not None and lm.building_at(game.player.lx, game.player.ly) is not None
    if indoors:
        light = max(light, 0.6)  # hearths and rushlights indoors
    w = game.weather
    rain = not indoors and (w.raining or w.snowing) and w.precip > 0.2
    if not indoors and w.visibility < 0.5:
        light = min(light, 0.45)  # fog and blizzards hide the enemy almost as well as night
    return Env(light=light, rain=rain, ground=ground, party_light=party_has_light(game), surprised=surprised)


def start_battle(game, creatures: list[Creature], intro: str, *, surprised: str | None = None, actor=None,
                 title: str = "") -> Battle:
    rng = game.world.rng.child(f"battle/{game.world.time}/{len(game.log.messages)}")
    battle = Battle(game.tables, [c for c in game.party if c.alive], creatures, battle_env(game, surprised), rng,
                    show_dice=getattr(game, "show_dice", True), title=title, now=game.world.time)
    battle.start(intro)
    game.battle = battle
    game.battle_actor = actor
    game.encounter = None
    game.travel = None
    game.say(f"<danger>{intro}</>", "danger")
    return battle


def finish_battle(game) -> Aftermath:
    """Apply a finished battle to the world and the party. Returns what the aftermath screen shows."""
    battle: Battle = game.battle
    result: BattleResult = battle.result()
    rng = game.world.rng.child(f"after/{game.world.time}")
    game.pass_seconds(result.rounds * ROUND_SECONDS, "fight")
    actor = game.battle_actor
    lm = game.local
    if actor is not None:
        # The dead stay dead; survivors keep their hurts if the band lives on.
        actor.creatures = [c for c in actor.creatures if c.alive and c.hp > 0]
        if not actor.creatures and lm is not None and actor in lm.actors:
            lm.actors.remove(actor)
    after = Aftermath(result.outcome, "")
    from realmwalker.rules import health

    # Survivors of the party who were down get back on their feet (or die of their wounds).
    for f in battle.side(PARTY):
        c = f.char
        health.carry_battle_state(c, f.conditions)
        if f.state != "down":
            continue
        if result.outcome == "fled":
            c.alive = False
            c.hp = 0
            after.notes.append(f"<danger>{c.name.split()[0]} was left behind.</>")
        elif f.stable or result.outcome in ("victory", "parley"):
            c.hp = max(1, c.hp)
            after.notes.append(f"{c.name.split()[0]} comes round, weak and hurting.")
    dead_party = [c for c in game.party if not c.alive]
    if result.outcome == "victory":
        after.xp = result.xp
        after.loot = list(result.loot_items)
        after.money = result.loot_money
        after.captives = list(result.captives)
        after.carcasses = [c for c in result.dead if game.tables.creatures[c.def_id].get("butcher")]
        after.significant = result.xp >= 100 or bool(dead_party) or len(result.dead) >= 3
        dead_text = _list_names(game, result.dead) or "Your enemies"
        survivors = ""
        if result.captives:
            survivors = f"{_list_names(game, result.captives)} kneel{'s' if len(result.captives) == 1 else ''} in the dirt, waiting to learn what you will do."
        elif result.fled:
            survivors = f"{_list_names(game, result.fled)} got away, and may be back."
        template = rng.choice(game.tables.combat_text["aftermath"]["victory"])
        after.text = template.replace("{dead}", dead_text).replace("{ground}", battle.env.ground).replace(
            "{weather}", "dark" if battle.env.light < 0.5 else "grey light").replace("{survivors}", survivors)
        if actor is not None and lm is not None and actor in lm.actors:
            lm.actors.remove(actor)
    elif result.outcome in ("defeat", "surrendered"):
        foes = [f for f in battle.side(FOE) if f.active]
        merciful = any(f.morale_type in MERCIFUL for f in foes) or result.outcome == "surrendered"
        if merciful and any(c.alive for c in game.party):
            taken = _rob_party(game, rng)
            after.outcome = "robbed"
            after.text = rng.choice(game.tables.combat_text["aftermath"]["robbed"])
            after.notes.append(f"They took {taken}.")
            for c in game.party:
                if c.alive:
                    c.hp = max(1, c.hp)
            if result.outcome == "defeat":
                hours = dice.roll("1d4", rng).total
                game.pass_time(hours * 60)
                after.notes.append(f"You lay senseless for {hours} hour{'s' if hours > 1 else ''}.")
            if actor is not None and lm is not None and actor in lm.actors:
                lm.actors.remove(actor)
        else:
            for c in game.party:
                if c.alive:
                    c.alive = False
                    c.hp = 0
            killers = _list_names(game, [f.creature for f in battle.side(FOE)])
            game.over = {"cause": f"killed by {killers}", "place": battle.env.ground}
            after.outcome = "death"
            after.text = "It is over. Nobody will come."
    elif result.outcome == "fled":
        after.text = rng.choice(game.tables.combat_text["aftermath"]["fled"])
        if lm is not None:
            game.leave_local()
    elif result.outcome == "parley":
        after.text = rng.choice(game.tables.combat_text["aftermath"]["parley"])
        after.xp = result.xp
        if actor is not None and lm is not None and actor in lm.actors:
            lm.actors.remove(actor)
    leader_alive = game.party and game.party[0].alive
    if dead_party and leader_alive:
        for c in dead_party:
            after.notes.append(f"<danger>{c.name} is dead.</>")
        game.party = [c for c in game.party if c.alive]
    elif not leader_alive and game.over is None:
        game.over = {"cause": "died of wounds after a fight", "place": battle.env.ground}
        after.outcome = "death"
    if after.xp and game.over is None:
        living = [c for c in game.party if c.alive]
        share = after.xp // max(1, len(living))
        for c in living:
            after.notes += progression.award_xp(c, share, game.tables, rng)
        after.notes.insert(0, f"<good>+{share} experience</> each." if len(living) > 1 else f"<good>+{share} experience.</>")
    for text in after.notes:
        game.say(text, "good" if "experience" in text or "level" in text else "info")
    game.battle = None
    game.battle_actor = None
    game.aftermath = after
    game.dirty = True
    return after


def _list_names(game, creatures: list[Creature]) -> str:
    if not creatures:
        return ""
    counts: dict[str, int] = {}
    for c in creatures:
        counts[c.def_id] = counts.get(c.def_id, 0) + 1
    parts = []
    for def_id, n in counts.items():
        d = game.tables.creatures[def_id]
        parts.append(f"{'the' if n == 1 else textgen_number(n)} {d['name'] if n == 1 else d['plural']}")
    text = ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1]
    return text[:1].upper() + text[1:]


def textgen_number(n: int) -> str:
    return {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}.get(n, str(n))


def _rob_party(game, rng) -> str:
    taken = []
    total = 0
    for c in game.party:
        total += c.money
        c.money = 0
    if total:
        taken.append(money_text(total))
    leader = game.party[0]
    valuables = [i for i in leader.inventory if leader.slot_of(i.uid) is None and game.tables.items.value(i) >= 100]
    valuables.sort(key=lambda i: -game.tables.items.value(i))
    for it in valuables[: rng.randint(1, 2)]:
        remove_item(leader, it.uid)
        taken.append(game.tables.items.name(it))
    return ", ".join(taken) if taken else "nothing, having found nothing worth taking"


# ---------------------------------------------------------------------------- encounters on the road
def encounter_fight(game, ambush: bool) -> Battle:
    enc = game.encounter
    surprised = FOE if ambush and enc.spotted_first else (PARTY if enc.asleep else None)
    return start_battle(game, enc.creatures, enc.intro, surprised=surprised, title=_encounter_title(game, enc.group))


def encounter_evade(game) -> bool:
    """Try to slip away before a fight starts. Stealth against their perception."""
    enc = game.encounter
    rng = game.world.rng.child(f"evade/{game.world.time}")
    stealth = min(game.sheet(c).skill_bonus("stealth") for c in game.party if c.alive)
    best_eyes = max(10 + int(game.tables.creatures[c.def_id].get("skills", {}).get("perception", 0)) for c in enc.creatures)
    roll = dice.d20(rng).natural
    bonus = 5 if enc.spotted_first else 0
    ok = roll + stealth + bonus >= best_eyes
    game.say(f"<dice>Stealth: {roll} + {stealth + bonus} = {roll + stealth + bonus} vs {best_eyes}</>", "dice")
    if ok:
        game.say("You slip away unseen, and give the place a wide berth.", "good")
        game.pass_time(30, "walk")
        game.encounter = None
    else:
        game.say("They have seen you. There is no getting away now.", "danger")
        start_battle(game, enc.creatures, enc.intro, title=_encounter_title(game, enc.group))
    return ok


def encounter_talk_dc(game) -> tuple[int | None, str]:
    """How hard it is to talk your way past (Persuasion), or why it cannot be done."""
    enc = game.encounter
    defs = [game.tables.creatures[c.def_id] for c in enc.creatures]
    if any(d["kind"] == "beast" for d in defs):
        return None, "animals do not bargain"
    if all(d.get("morale") in FEARLESS for d in defs):
        return None, "they are past words"
    party = sum(1 for c in game.party if c.alive)
    dc = 12 + 2 * (len(enc.creatures) - party) + (2 if not enc.spotted_first else 0)
    return max(8, min(22, dc)), ""


def encounter_talk(game) -> bool:
    """Try to talk your way past before blood is spilled. Failure means a fight, with no surprise."""
    enc = game.encounter
    dc, why = encounter_talk_dc(game)
    if dc is None:
        game.say(f"You try to talk, but {why}.", "warn")
        start_battle(game, enc.creatures, enc.intro, title=_encounter_title(game, enc.group))
        return False
    rng = game.world.rng.child(f"talk/{game.world.time}")
    s = game.sheet()
    roll = dice.d20(rng).natural
    bonus = s.skill_bonus("persuasion")
    game.say(f"<dice>Persuasion: {roll} {'+' if bonus >= 0 else '-'} {abs(bonus)} = {roll + bonus} vs DC {dc}</>", "dice")
    if roll + bonus >= dc:
        game.say("Words are exchanged, hands stay near hilts, and in the end they let you pass.", "good")
        game.pass_time(10)
        game.encounter = None
        return True
    game.say("They hear you out, and laugh, and draw.", "danger")
    start_battle(game, enc.creatures, enc.intro, title=_encounter_title(game, enc.group))
    return False


def _encounter_title(game, group: str) -> str:
    name = game.tables.creatures.encounters.get(group, {}).get("name", "a fight")
    return name[:1].upper() + name[1:]


# ---------------------------------------------------------------------------- after the fight
def take_loot(game, items: list[Item] | None = None, money: bool = True) -> list[str]:
    after: Aftermath = game.aftermath
    if after is None:
        return []
    leader = game.leader
    taken = []
    for it in list(items if items is not None else after.loot):
        if it in after.loot:
            after.loot.remove(it)
            add_existing(leader, game.tables.items, it)
            taken.append(game.tables.items.name(it))
    if money and after.money:
        leader.money += after.money
        taken.append(money_text(after.money))
        after.money = 0
    game.dirty = True
    return taken


def leave_loot(game) -> None:
    """Whatever is not taken stays where the fight was (on a local map) or is lost (on the road)."""
    after: Aftermath = game.aftermath
    if after is None:
        return
    lm = game.local
    if lm is not None and after.loot:
        p = game.player
        lm.items.setdefault((p.lx, p.ly), []).extend(after.loot)
    after.loot = []


CAPTIVE_FATES = {
    "spare": "Let them go",
    "rob": "Take what they have, then let them go",
    "interrogate": "Question them",
    "execute": "Kill them",
    "capture": "Take them for a bounty or ransom",
}


def decide_captive(game, creature: Creature, fate: str) -> str:
    after: Aftermath = game.aftermath
    leader = game.leader
    rng = game.world.rng.child(f"fate/{creature.uid}/{game.world.time}")
    name = creature.name if creature.named else f"the {creature.name}"
    cname = name[:1].upper() + name[1:]
    text = ""
    if fate == "capture":
        return "No town here will pay for prisoners yet. (Bounties and ransoms arrive with factions and law.)"
    if fate == "spare":
        text = f"{cname} stares at you, then goes, fast, without looking back."
        leader.deeds.append(f"spared a beaten {game.tables.creatures[creature.def_id]['name']}")
    elif fate == "rob":
        for it in creature.inventory:
            d = game.tables.items.get(it.def_id)
            if d["category"] != "clothing":
                after.loot.append(it)
        after.money += creature.money
        creature.money = 0
        text = f"You strip {name} of weapons and coin and send {'them' if not creature.named else 'him'} off with nothing."
        leader.deeds.append(f"robbed a surrendered {game.tables.creatures[creature.def_id]['name']}")
    elif fate == "interrogate":
        s = game.sheet()
        skill = "intimidation" if s.skill_bonus("intimidation") >= s.skill_bonus("persuasion") else "persuasion"
        roll = dice.d20(rng).natural + s.skill_bonus(skill)
        if roll >= 12:
            site = _nearest_unknown_site(game)
            if site is not None:
                game.player.explored[site.x, site.y] = True
                text = f"{cname} talks: there is {site.name} not far from here, and people go there who don't come back."
            else:
                text = f"{cname} talks, but knows nothing you don't."
        else:
            text = f"{cname} tells you nothing useful, or nothing true."
        leader.deeds.append(f"interrogated a prisoner")
    elif fate == "execute":
        text = rng.choice([f"You kill {name}. It is quick, and it is not clean.",
                           f"{cname} begs until the end. Then the end comes."])
        leader.deeds.append(f"executed a prisoner who had surrendered")
        leader.kills[game.tables.creatures[creature.def_id]["name"]] = leader.kills.get(game.tables.creatures[creature.def_id]["name"], 0) + 1
    after.fates[creature.uid] = fate
    game.say(text, "info" if fate != "execute" else "danger")
    game.dirty = True
    return text


def _nearest_unknown_site(game):
    p = game.player
    sites = [s for s in game.world.sites if not p.explored[s.x, s.y]]
    if not sites:
        return None
    return min(sites, key=lambda s: abs(s.x - p.x) + abs(s.y - p.y))


# ---------------------------------------------------------------------------- rest
def rest(game, kind: str) -> list[str]:
    """Rest: 'short' (1 hour) or 'long' (8 hours). A long rest in the wilds may be interrupted."""
    from realmwalker.game.encounters import roll_encounter

    lm = game.local
    if lm is not None and any(a.alert for a in lm.actors):
        return ["You can't rest with enemies hunting you."]
    from realmwalker.rules import body

    rng = game.world.rng.child(f"rest/{game.world.time}")
    notes = []
    hours = 1 if kind == "short" else 8
    from realmwalker.game.camp import camp_here

    camp = camp_here(game)
    fire = bool(camp and camp.fire)
    for hour in range(hours):
        game.pass_time(60, "sleep" if kind == "long" else "rest")
        if game.over is not None:
            return notes
        if lm is None and kind == "long":
            # A fire is seen from afar, but beasts fear it; a cold camp is harder to find.
            enc = roll_encounter(game, 60 * (0.6 if fire else 0.4))
            if enc is not None and fire and all(game.tables.creatures[c.def_id]["kind"] == "beast" for c in enc.creatures):
                if game.world.rng.child(f"firelight/{game.world.time}").chance(0.6):
                    notes.append("Eyes glint beyond the firelight in the night, but they do not come closer.")
                    enc = None
            if enc is not None:
                enc.asleep = True
                enc.spotted_first = False
                game.encounter = enc
                notes.append(f"<danger>Your rest is broken after {hour + 1} hour{'s' if hour else ''}.</>")
                return notes
    for c in game.party:
        if kind == "short":
            notes += progression.short_rest(c, game.tables, rng)
        elif c.hunger >= 80 or c.thirst >= 85:
            notes.append(f"<warn>{c.name.split()[0]} is too {'hungry' if c.hunger >= 80 else 'thirsty'} to rest "
                         f"properly.</> Only a short rest's worth of good came of it.")
            notes += progression.short_rest(c, game.tables, rng)
        else:
            notes += progression.long_rest(c, game.tables, rng)
        if kind == "long":
            notes += body.sleep_recovery(c)
        body.clamp_hp(c)
    return notes
