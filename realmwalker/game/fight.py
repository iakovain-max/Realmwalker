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
from realmwalker.rules.inventory import add_existing, carried, remove_item
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
    elif game.world.road[game.player.x, game.player.y]:
        ground = "road"
    else:
        # What is underfoot in that land ("the leaf litter", "the pine needles"), not the land ("the pine forest").
        ground_ids = game.biome_def(game.player.x, game.player.y)["local"]["ground"]
        top = max(ground_ids, key=lambda g: g[1])[0]
        ground = game.tables.terrain[game.tables.terrain.index[top]]["name"] if top in game.tables.terrain.index else "ground"
    light = game.light
    underground = lm is not None and lm.under_rock(game.player.lx, game.player.ly)
    indoors = underground or (lm is not None and lm.building_at(game.player.lx, game.player.ly) is not None)
    party_light = party_has_light(game)
    if underground:
        # No sun under the ground (it used to be noon down there whenever it was noon outside): only what you carry.
        from realmwalker.game.dungeon import light_radius

        light = 0.0
        party_light = party_light or light_radius(game) > 0
    elif indoors:
        light = max(light, 0.6)  # hearths and rushlights indoors
    w = game.weather
    rain = not indoors and (w.raining or w.snowing) and w.precip > 0.2
    if not indoors and w.visibility < 0.5:
        light = min(light, 0.45)  # fog and blizzards hide the enemy almost as well as night
    carried = 0
    if party_light:
        from realmwalker.game.dungeon import light_radius

        carried = max(4, int(light_radius(game)) * 2 // 3) if light_radius(game) else 4
    return Env(light=light, rain=rain, ground=ground, party_light=party_light, surprised=surprised, carried_light=carried,
               place="underground" if underground else ("indoors" if indoors else ""))


def start_battle(game, creatures: list[Creature], intro: str, *, surprised: str | None = None, actor=None,
                 title: str = "", near: tuple[int, int] | None = None) -> Battle:
    """A fight begins: the field is made from the place (game/arena.py), everyone is set on it, and the dice roll.
    `actor` is the band on a close-up map being fought; `near` is where on that map the enemy comes from when
    there is no band (a townsman you were talking to, the watch)."""
    from realmwalker.game import arena

    # A battle's dice come from its own numbered stream: the number of messages in the log is no business of the
    # dice, and saying one more thing before a fight should not change how it goes.
    fought = int(game.world.politics.get("next_battle", 0))
    game.world.politics["next_battle"] = fought + 1
    rng = game.world.rng.child(f"battle/{fought}/{game.world.time}")
    env = battle_env(game, surprised)
    situation = arena.situation_for(game, surprised)
    field, spots = arena.build(game, creatures, env, rng.child("arena"), actor=actor, near=near, situation=situation,
                               number=fought)
    from realmwalker.game import speech

    for line in speech.nightmares_at_the_start(game, creatures):  # (Dream: a named beast meets you hurt)
        game.say(line, "magic")
    game.battle_group = game.encounter.group if game.encounter is not None else (actor.group if actor else None)
    battle = Battle(game.tables, [c for c in game.party if c.alive], creatures, env, rng,
                    show_dice=getattr(game, "show_dice", True), title=title, now=game.world.time, field=field,
                    spots=spots)
    if situation == "camp":
        for f in battle.side(PARTY):
            f.conditions["prone"] = -1  # caught asleep: on the ground, and getting up takes half a move
    _magic_at_the_start(game, battle)
    from realmwalker.rules import spells as spellrules

    for c in game.party:
        spellrules.close_preparing(c)  # (the prepared spells stay as they are until the next rest)
    battle.start(intro)
    game.battle = battle
    others = [c for c in game.party[1:] if c.alive]
    if others and rng.chance(0.4):
        from realmwalker.game.companions import say

        say(game, "battle", rng.choice(others))
    game.battle_actor = actor
    game.encounter = None
    game.travel = None
    game.say(f"<danger>{intro}</>", "danger")
    return battle


def markup_escape(text: str) -> str:
    from realmwalker.core.textgen import escape_markup

    return escape_markup(text)


def _magic_at_the_start(game, battle: Battle) -> None:
    """What magic items do to their bearers as a fight begins: one a sentient thing has seized fights as it wills (on
    Auto); one bound to an artifact that someone else is wearing is blind or deaf (DMG 2024 artifact flaws). The party
    carries one pack, so "someone else carrying it" means another member wearing or wielding it."""
    from realmwalker.game import magic_items
    from realmwalker.rules import magic

    for f in battle.side(PARTY):
        c = f.char
        if c is None or not c.attuned:
            continue
        if magic_items.seized(game, c):
            f.auto = True
            game.say(f"<magic>{markup_escape(c.name.split()[0])} fights as the thing bound to them wills.</>", "magic")
        for it in magic.attuned_items(c):
            elsewhere = any(o is not c and o.slot_of(it.uid) is not None for o in game.party)
            if not elsewhere:
                continue
            for flag, cond in (("blind_apart", "blinded"), ("deaf_apart", "deafened")):
                if any(p.get("kind") == "flag" and p.get("flag") == flag for p in it.magic.get("props", [])):
                    f.conditions[cond] = -1


def _kinds(game, creatures) -> list[dict]:
    """What a sentient thing sees in a band: each one's kind and alignment."""
    out = []
    for c in creatures:
        d = game.tables.creatures[c.def_id]
        out.append({"type": d.get("kind", ""), "alignment": d.get("alignment", "")})
    return out


def finish_battle(game) -> Aftermath:
    """Apply a finished battle to the world and the party. Returns what the aftermath screen shows."""
    battle: Battle = game.battle
    result: BattleResult = battle.result()
    rng = game.world.rng.child(f"after/{game.world.time}")
    actor = game.battle_actor
    lm = game.local
    if actor is not None:
        # The dead stay dead; survivors keep their hurts if the band lives on.
        actor.creatures = [c for c in actor.creatures if c.alive and c.hp > 0]
        if not actor.creatures and lm is not None and actor in lm.actors:
            lm.actors.remove(actor)
    after = Aftermath(result.outcome, "")
    from realmwalker.game import speech

    speech.remember_the_dead(game, battle, getattr(game, "battle_group", None))  # (for Speak with Dead)
    _settle_townsfolk(game, battle, result)
    if game.party[1:]:
        from realmwalker.game.companions import react

        tags = {"victory": ("victory",), "fled": ("fleeing",), "surrendered": ("surrender",)}.get(result.outcome, ())
        if result.outcome == "victory" and result.xp >= 100:
            tags += ("hard_fight",)
        react(game, *tags)
    from realmwalker.game import magic_items

    if result.outcome in ("victory", "fled", "parley"):
        magic_items.notice(game, result.outcome, creatures=_kinds(game, [f.creature for f in battle.side(FOE)
                                                                         if f.creature is not None]),
                           hard=result.xp >= 100)
    if result.outcome in ("victory", "parley") and game.world.factions:
        from realmwalker.game.reputation import battle_deeds

        battle_deeds(game, result)
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
        one = len(result.dead) == 1  # "The wolf lies still", "Two wolves lie still"
        after.text = template.replace("{dead}", dead_text).replace("{ground}", battle.env.ground).replace(
            "{weather}", "dark" if battle.env.light < 0.5 else "grey light").replace("{survivors}", survivors).replace(
            "{lie}", "lies" if one else "lie").replace("{are}", "is" if one else "are").strip()
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
                after.notes.append(lie_senseless(game, dice.roll("1d4", rng).total))
            if actor is not None and lm is not None and actor in lm.actors:
                lm.actors.remove(actor)
        elif any(f.char is not None and f.char.alive and f.buff_value("feigning") for f in battle.side(PARTY)):
            _feigned(game, battle, rng, after)
            if actor is not None and lm is not None and actor in lm.actors:
                lm.actors.remove(actor)  # (they take you all for dead, and go)
        else:
            beasts = bool(foes) and all(f.kind == "beast" for f in foes)
            if beasts and any(c.alive for c in game.party):
                _left_for_dead(game, battle, rng, after, len(foes))
                if actor is not None and lm is not None and actor in lm.actors:
                    lm.actors.remove(actor)  # they have had what they came for, and gone
            if after.outcome != "mauled" or not game.party[0].alive:
                for c in game.party:
                    if c.alive and after.outcome != "mauled":
                        c.alive = False
                        c.hp = 0
                killers = _list_names(game, [f.creature for f in battle.side(FOE)])
                game.over = {"cause": f"killed by {killers[:1].lower() + killers[1:]}", "place": battle.env.ground}
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
    from realmwalker.game import gear

    after.notes += gear.wear_from_battle(game, battle)  # blows given and taken wear blades and armour
    # The fight's minutes pass only now: anyone knocked down has come round (or been robbed and left, or mauled and
    # left) by this point. Before, a body still at 0 hit points was found dead of its hurts the moment time moved.
    game.pass_seconds(result.rounds * ROUND_SECONDS, "fight")
    from realmwalker.game import revival

    fell = {id(f.char): f for f in battle.side(PARTY) if f.char is not None}
    if game.party and not game.party[0].alive and game.over is None and result.outcome != "fled":
        # The leader fell: a companion still standing may call them back at once (a spell of return).
        f0 = fell.get(id(game.party[0]))
        since = (battle.round - f0.died_round) * ROUND_SECONDS / 60 if f0 is not None and f0.died_round >= 0 else 0.0
        back = revival.save_leader(game, since)
        if back:
            after.notes += back
            if after.outcome == "death":
                after.outcome = result.outcome
    dead_party = [c for c in game.party if not c.alive]  # (left for dead, not everyone wakes)
    leader_alive = game.party and game.party[0].alive
    if dead_party and leader_alive:
        game.party = [c for c in game.party if c.alive]
        game.waiting = [c for c in game.waiting if c.alive]
        from realmwalker.game import pack

        pack.sync(game)  # what they carried stays with the party
        for c in dead_party:
            after.notes.append(f"<danger>{c.name} is dead.</>")
            f = fell.get(id(c))
            when = game.world.time - (battle.round - f.died_round) * ROUND_SECONDS / 60 \
                if f is not None and f.died_round >= 0 else None
            revival.fall(game, c, died_at=when, left=result.outcome == "fled")
        after.notes += revival.auto_revive(game)  # (a companion with Revivify ready, in the minute left)
        after.notes += revival.leader_note(game)
    elif not leader_alive and game.over is None:
        cause = getattr(game.party[0], "death_cause", None) if game.party else None
        game.over = {"cause": cause or "died of wounds after a fight", "place": battle.env.ground}
        after.outcome = "death"
    if after.xp and game.over is None:
        living = [c for c in game.party if c.alive]
        share = after.xp // max(1, len(living))
        for c in living:
            after.notes += progression.award_xp(c, share, game.tables, rng)
        after.notes.insert(0, f"<good>+{share} experience</> each." if len(living) > 1 else f"<good>+{share} experience.</>")
    for text in after.notes:
        game.say(text, "good" if "experience" in text or "level" in text else "info")
    if game.over is None:
        if game.world.politics.get("dragons"):
            from realmwalker.game import dragons

            dragons.on_battle(game, result)
        from realmwalker.game import past

        past.on_battle(game, result)
        if game.quests:
            from realmwalker.game import quests

            quests.on_battle(game, result, actor)
    game.battle = None
    game.battle_actor = None
    game.aftermath = after
    game.dirty = True
    return after


def _settle_townsfolk(game, battle: Battle, result: BattleResult) -> None:
    """Townsfolk who fought: the dead are dead, the beaten hate you, the fled run home."""
    mapping = getattr(game, "battle_npcs", {})
    if not mapping:
        return
    for f in battle.side(FOE):
        npc = game.world.npcs.get(mapping.get(f.creature.uid, -1))
        if npc is None:
            continue
        if f.state == "dead":
            npc.alive = False
            npc.present = False
            game.leader.deeds.append(f"killed {npc.name}, the {npc.title}")
            if game.world.factions:
                from realmwalker.game import law

                law.commit(game, "murder", victim=npc, witnesses=law.witnesses_here(game, exclude=[npc]))
            if game.quests:
                from realmwalker.game import quests

                quests.on_npc_death(game, npc)
        else:
            npc.disposition = -100
            npc.remember("was attacked by the traveller")
            npc.flags["fled_until"] = game.world.time + 12 * 60
            npc.present = False
    game.battle_npcs = {}


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
    from realmwalker.rules.inventory import worn_by

    from realmwalker.game import glamour

    valuables = [i for i in leader.inventory if worn_by(leader, i.uid)[1] is None and game.tables.items.value(i) >= 100
                 and not _keepsake(game, i) and not glamour.hidden_thing(game, i, robbers=True)]
    valuables.sort(key=lambda i: -game.tables.items.value(i))
    for it in valuables[: rng.randint(1, 2)]:
        remove_item(leader, it.uid)
        taken.append(game.tables.items.name(it))
        from realmwalker.game import divining

        divining.taken(game, [it], "robbers")  # (Drawmij's Instant Summons can call it back)
    if leader.animals:
        taken.append(", ".join(a["name"] for a in leader.animals) + " (your animals)")
        leader.animals = []
    if leader.vehicles:
        specs = game.tables.economy.get("vehicles", {})
        taken.append(", ".join("the " + specs.get(v["kind"], {}).get("name", "cart") for v in leader.vehicles))
        leader.vehicles = []
    return ", ".join(taken) if taken else "nothing, having found nothing worth taking"


MAULED_DC = 5  # plus one for each beast still on its feet: a Constitution save to wake up at all


def _feigned(game, battle: Battle, rng, after: Aftermath) -> None:
    """A lost fight with a friend lying as if dead (Feign Death): the foes take everyone for dead and go. The
    feigner gets up when they are gone; the fallen beside them make the Constitution save of those left for dead
    (as after beasts), and the feigner binds them if they wake."""
    from realmwalker.core.textgen import escape_markup
    from realmwalker.rules.character import Sheet

    feigners = [f.char for f in battle.side(PARTY) if f.char is not None and f.char.alive and f.buff_value("feigning")]
    for f in battle.side(PARTY):
        c = f.char
        if c is None or not c.alive or c in feigners:
            continue
        roll = dice.d20(rng).natural
        sheet = Sheet(c, game.tables)
        bonus = sheet.mod("con") + (sheet.proficiency if "con" in c.saves else 0)
        game.say(f"<dice>{escape_markup(c.name.split()[0])} (Constitution save): {roll} {'+' if bonus >= 0 else '-'} "
                 f"{abs(bonus)} = {roll + bonus} vs DC {MAULED_DC}</>", "dice")
        if roll + bonus >= MAULED_DC:
            c.hp = max(1, c.hp)
        else:
            c.alive = False
            c.hp = 0
            if c is not game.party[0]:
                after.notes.append(f"<danger>{escape_markup(c.name.split()[0])} never wakes.</>")
    for c in feigners:
        c.hp = max(1, c.hp)
    after.outcome = "mauled"
    names = ", ".join(escape_markup(c.name.split()[0]) for c in feigners)
    after.text = (f"They prod the bodies, take {names} for one more of the dead, and go. When the last sound of them "
                  f"is gone, {names} gets up.")
    if not game.party[0].alive:
        game.over = {"cause": "killed in a lost fight", "place": battle.env.ground}
        after.outcome = "death"


def _left_for_dead(game, battle: Battle, rng, after: Aftermath, beasts: int) -> None:
    """Beasts that have beaten the party lose interest in what has stopped moving, and go for the food in the pack
    instead. Each of the fallen makes a Constitution save to wake at all; whoever does wakes hours later, hurt and
    alone. (Bandits rob a beaten party; the dead, the mad and the monstrous still finish it.)"""
    from realmwalker.rules.character import Sheet
    from realmwalker.rules.inventory import distinct_packs

    dc = MAULED_DC + beasts
    woke = []
    for f in battle.side(PARTY):
        c = f.char
        if c is None or not c.alive:
            continue
        roll = dice.d20(rng).natural
        sheet = Sheet(c, game.tables)  # the body's own toughness: pain and blood loss are what it is surviving
        bonus = sheet.mod("con") + (sheet.proficiency if "con" in c.saves else 0)
        game.say(f"<dice>{c.name.split()[0]} (Constitution save): {roll} {'+' if bonus >= 0 else '-'} {abs(bonus)} = "
                 f"{roll + bonus} vs DC {dc}</>", "dice")
        if roll + bonus >= dc:
            c.hp = max(1, c.hp)
            woke.append(c)
        else:
            c.alive = False
            c.hp = 0
            if c is not game.party[0]:
                after.notes.append(f"<danger>{c.name.split()[0]} never wakes.</>")
    if not woke or not game.party[0].alive:
        return
    after.outcome = "mauled"
    after.text = rng.choice(game.tables.combat_text["aftermath"]["mauled"])
    eaten = []
    for m in distinct_packs(game.party):
        for it in list(m.inventory):
            if not game.tables.items.get(it.def_id).get("food"):
                continue
            gone = (it.qty + 1) // 2
            if gone and remove_item(m, it.uid, gone) is not None:
                eaten.append(game.tables.items.name(it, with_qty=False))
    if eaten:
        after.notes.append(f"They tore the pack open and dragged off half the food ({', '.join(sorted(set(eaten)))}).")
    note = lie_senseless(game, dice.roll("1d4", rng).total + 1)
    after.notes.append(note + (" Your wounds want seeing to." if note.startswith("You lay") else ""))


def lie_senseless(game, hours: int) -> str:
    """Lying where you fell after a beating, for some hours, or less: losing blood brings you round while there is
    still time to bind the wound (nobody bleeds to death in a faint they never had the chance to wake from)."""
    lay = 0
    for _ in range(hours * 2):
        game.pass_time(30)
        lay += 30
        if game.over is not None:
            break
        if any(c.alive and any(w.bleed and not w.bandaged for w in c.wounds) and c.blood < 70 for c in game.party):
            return f"The bleeding brings you round after {_lay_words(lay)}. Bind it, now."
    return f"You lay senseless for {_lay_words(lay)}."


def _lay_words(minutes: int) -> str:
    hours, half = divmod(minutes, 60)
    if hours == 0:
        return "half an hour"
    if half:
        return "an hour and a half" if hours == 1 else f"{hours} and a half hours"
    return "an hour" if hours == 1 else f"{hours} hours"


NOT_WORTH_STEALING = {"spellbook", "holy_symbol", "arcane_focus", "component_pouch", "prayer_book", "backpack"}


def _keepsake(game, item) -> bool:
    """What robbers leave: a wizard's spellbook, a priest's holy symbol and the like (worth nothing to a fence, and
    everything to their owner), the pack everything else is carried in, and whatever a piece of work has given you to
    carry."""
    return item.def_id in NOT_WORTH_STEALING or any(t.startswith("quest:") for t in item.tags)


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
    # Seeing them first is most of slipping away: advantage on the roll, and five more besides. The travel pace
    # (PHB 2024): at a Fast or Normal pace a party is at a disadvantage to move quietly; at a Slow one it is not.
    from realmwalker.rules import encounter

    loud = encounter.pace(game.tables, game.travel_pace()).get("stealth") == "disadvantage"
    roll = dice.d20(rng, advantage=enc.spotted_first, disadvantage=loud).natural
    bonus = 5 if enc.spotted_first else 0
    ok = roll + stealth + bonus >= best_eyes
    adv = {(True, False): " (adv)", (False, True): " (dis)"}.get((enc.spotted_first, loud), "")
    game.say(f"<dice>Stealth{adv}: {roll} {'+' if stealth + bonus >= 0 else '-'} {abs(stealth + bonus)} = "
             f"{roll + stealth + bonus} vs {best_eyes}</>", "dice")
    if ok:
        game.say("You slip away unseen, and give the place a wide berth.", "good")
        game.pass_time(30, "walk")
        game.encounter = None
    else:
        game.say("They have seen you. There is no getting away now.", "danger")
        start_battle(game, enc.creatures, enc.intro, title=_encounter_title(game, enc.group))
    return ok


SOLDIERLY = ("guard", "noble", "deserter")  # men who were soldiers, and know a rank when they see it


def encounter_talk_dc(game) -> tuple[int | None, str]:
    """How hard it is to talk your way past (Persuasion), or why it cannot be done."""
    enc = game.encounter
    defs = [game.tables.creatures[c.def_id] for c in enc.creatures]
    from realmwalker.game import speech

    tongue, why = speech.talk_problem(game, enc.creatures)  # (no shared tongue; beasts but by Speak with Animals)
    if why:
        return None, why
    from realmwalker.game.encounters import _hated

    if _hated(game, enc.creatures):
        return None, "they know what one of you carries"
    if all(d.get("morale") in FEARLESS for d in defs):
        return None, "they are past words"
    party = sum(1 for c in game.party if c.alive)
    from realmwalker.rules import encounter

    # PHB 2024 Influence: 15 or their best Intelligence, whichever is higher; more of them is harder, fewer easier.
    dc = encounter.influence_dc(game.tables, [c.def_id for c in enc.creatures]) + 2 * (len(enc.creatures) - party) \
        + (2 if not enc.spotted_first else 0) - 3
    if any(c.def_id in SOLDIERLY for c in enc.creatures) and any(
            (game.tables.items.get(it.def_id).get("impress") or {}).get("people") == "soldiers"
            for it in carried(game.party)):
        dc -= 4  # an old soldier's insignia: they still straighten up for rank
    dc = max(8, min(22, dc + tongue))
    from realmwalker.game import uniques

    if uniques.talked_past(game, enc.creatures):
        dc = max(5, dc - 8)  # orcs and goblins know Grusha's name, and argue among themselves about it
    return dc, ""


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
    from realmwalker.rules import encounter

    mode = encounter.influence_mode(game.tables, enc.attitude)  # Friendly: advantage; Hostile: disadvantage
    roll = dice.d20(rng, advantage=mode == "advantage", disadvantage=mode == "disadvantage").natural
    bonus = s.skill_bonus("persuasion")
    how = {"advantage": " (adv)", "disadvantage": " (dis)"}.get(mode, "")
    game.say(f"<dice>Persuasion{how}: {roll} {'+' if bonus >= 0 else '-'} {abs(bonus)} = {roll + bonus} vs DC {dc}</>",
             "dice")
    if roll + bonus >= dc:
        game.say("Words are exchanged, hands stay near hilts, and in the end they let you pass.", "good")
        from realmwalker.game import magic_items

        magic_items.notice(game, "parley", creatures=_kinds(game, enc.creatures))
        game.pass_time(10)
        game.encounter = None
        return True
    game.say("They hear you out, and laugh, and draw.", "danger")
    start_battle(game, enc.creatures, enc.intro, title=_encounter_title(game, enc.group))
    return False


ATTITUDE_WORDS = {
    "hostile": "<danger>They mean you harm.</>",
    "indifferent": "<fg>They are wary, but not set on a fight: you could let them be.</>",
    "friendly": "<good>They seem well disposed towards you.</>",
}


def encounter_pass(game) -> bool:
    """Let an Indifferent or Friendly band be (DMG 2024: they do not attack unprovoked): a wide berth, and on."""
    enc = game.encounter
    if enc is None or enc.attitude == "hostile":
        return False
    rng = game.world.rng.child(f"pass/{game.world.time}")
    if enc.attitude == "friendly":
        game.say(rng.choice(["They raise a hand as you pass, and you raise one back.",
                             "A nod, a word about the road ahead, and each goes their way.",
                             "They step aside to let you by, and wish you better luck than theirs."]), "good")
    else:
        game.say(rng.choice(["You give them a wide berth. They watch you all the way, and let you go.",
                             "Nobody draws. You keep walking, and so do they.",
                             "Eyes on each other, hands away from hilts: you pass, and the road is yours again."]),
                 "info")
    game.pass_time(10, "walk")
    game.encounter = None
    return True


def encounter_pay_cost(game) -> tuple[int | None, str]:
    """What it costs to hand over your purse to men who would rather rob you than fight you (half of what you carry),
    or None and why not."""
    enc = game.encounter
    defs = [game.tables.creatures[c.def_id] for c in enc.creatures]
    if not defs or not all(d.get("morale") in MERCIFUL for d in defs):
        return None, "they want blood, not money"
    purse = sum(c.money for c in game.party if c.alive)
    if purse <= 0:
        return None, "you have nothing to give them"
    return max(1, purse // 2), ""


def encounter_pay(game) -> bool:
    """Hand over the purse: no fight, no beating, and half your money gone."""
    cost, why = encounter_pay_cost(game)
    if cost is None:
        game.say(f"You offer what you have, but {why}.", "warn")
        start_battle(game, game.encounter.creatures, game.encounter.intro,
                     title=_encounter_title(game, game.encounter.group))
        return False
    from realmwalker.game.events import pay

    pay(game, cost)
    game.say(f"You hold out your purse. They take {money_text(cost)} out of it, weigh the rest of you with their eyes, "
             f"and let you go.", "warn")
    game.leader.deeds.append("paid off robbers on the road")
    from realmwalker.game import magic_items

    magic_items.notice(game, "paid_off", creatures=_kinds(game, game.encounter.creatures))
    if game.party[1:]:
        from realmwalker.game.companions import react

        react(game, "surrender", quiet=True)
    game.pass_time(10)
    game.encounter = None
    game.dirty = True
    return True


def encounter_bait_food(game) -> tuple[list | None, str]:
    """The food that would buy off hungry beasts (a meal's worth for each), meat first, or None and why not."""
    enc = game.encounter
    defs = [game.tables.creatures[c.def_id] for c in enc.creatures]
    if not defs or not all("takes_food" in d.get("traits", []) for d in defs):
        return None, "these are not after your food"
    from realmwalker.rules.inventory import distinct_packs

    items = game.tables.items
    food = [(m, it) for m in distinct_packs(game.party) for it in m.inventory
            if items.get(it.def_id).get("food") and float(items.get(it.def_id)["food"].get("nutrition", 0)) >= 0.3]
    food.sort(key=lambda p: (0 if "meat" in p[1].def_id or "pork" in p[1].def_id or "fish" in p[1].def_id else 1,
                             -float(items.get(p[1].def_id)["food"].get("nutrition", 0))))
    need, out = len(enc.creatures), []
    for m, it in food:
        take = min(it.qty, need)
        out.append((m, it, take))
        need -= take
        if need <= 0:
            return out, ""
    return None, "you have not enough food to throw them"


def encounter_bait(game) -> bool:
    """Throw them food and back away: beasts that are hungry, not mad, take it and let you go."""
    food, why = encounter_bait_food(game)
    if food is None:
        game.say(f"You have nothing to throw them: {why}.", "warn")
        start_battle(game, game.encounter.creatures, game.encounter.intro,
                     title=_encounter_title(game, game.encounter.group))
        return False
    names = []
    for m, it, n in food:
        names.append(game.tables.items.name(it, with_qty=False))
        remove_item(m, it.uid, n)
    game.say(f"You throw down {', '.join(dict.fromkeys(names))} and back away, slowly, not turning your back. They fall "
             f"on it, and by the time they look up again you are gone.", "warn")
    game.pass_time(15, "walk")
    game.encounter = None
    game.dirty = True
    return True


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
        from realmwalker.game.companions import react, share_loot

        kept = share_loot(game, after.money)
        leader.money += kept
        taken.append(money_text(after.money) + (f" (your share {money_text(kept)})" if kept != after.money else ""))
        if game.party[1:]:
            react(game, "loot", quiet=True)
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
        reward = int(game.tables.law["rewards"].get(creature.def_id, 0))
        if reward <= 0:
            return f"No one would pay for {name}."
        from realmwalker.game.reputation import foe_faction

        faction = foe_faction(game, creature.def_id)
        game.renown.flags.setdefault("captives", []).append({
            "def_id": creature.def_id, "name": name, "reward": reward, "since": game.world.time,
            "faction": faction.id if faction is not None else -1})
        from realmwalker.game.gear import binding

        how = binding(game, len(game.renown.flags["captives"]))[-1]
        tied = {"manacles": f"You put {name} in manacles", "rope": f"You tie {name}'s hands with rope"}.get(
            how, f"You bind {name}'s hands with a belt")
        risk = {"manacles": "and nobody slips those", "rope": "if they don't slip away first",
                "none": "if they don't slip away first (rope would hold better, and manacles best)"}[how]
        text = (f"{tied} and take them along. The watch in any town will pay for them ({money_text(reward)}), "
                f"{risk}.")
        leader.deeds.append(f"took {name} prisoner")
        after.fates[creature.uid] = fate
        game.say(text, "info")
        game.dirty = True
        return text
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
    if game.party[1:]:
        from realmwalker.game.companions import react

        react(game, *{"spare": ("mercy",), "rob": ("robbing_surrendered",), "execute": ("execution", "cruelty"),
                      "interrogate": ()}.get(fate, ()))
    game.dirty = True
    return text


def _nearest_unknown_site(game):
    p = game.player
    sites = [s for s in game.world.sites if not p.explored[s.x, s.y]]
    if not sites:
        return None
    return min(sites, key=lambda s: abs(s.x - p.x) + abs(s.y - p.y))


# ---------------------------------------------------------------------------- rest
RUSTLING_CHANCE = 0.02  # a night in the open with animals tethered, plus a little more for each step of danger


def _rustlers(game, fire: bool) -> list[str]:
    """A night in the wild with mules or horses: now and then somebody comes for them. Someone on watch sees them
    off; a fire shows where you are."""
    from realmwalker.game.companions import watching

    p = game.player
    rng = game.world.rng.child(f"rustlers/{game.world.time}/{p.x},{p.y}")
    chance = (RUSTLING_CHANCE + 0.01 * int(game.world.danger[p.x, p.y])) * (1.3 if fire else 1.0)
    if not rng.chance(chance):
        return []
    from realmwalker.game import spellwork

    guarded = spellwork.guards_the_animals(game)  # (an alarm, a hound, a dome, a door out of the world)
    if guarded:
        return [guarded]
    if watching(game):
        return ["<warn>In the small hours the one on watch shouts: someone was at the animals.</> Whoever it was runs "
                "off into the dark with nothing."]
    dog = next((a for a in game.leader.animals if a.get("kind") == "mastiff"), None)
    if dog is not None:  # a guard dog among the animals is as good as a watch
        return [f"<warn>In the small hours {dog['name']} goes for someone at the tethers,</> snarling, and whoever it "
                f"was runs off into the dark with nothing but bites."]
    animal = rng.choice(game.leader.animals)
    game.leader.animals.remove(animal)
    game.dirty = True
    what = f"{animal['name']} the {str(animal.get('kind', 'animal')).replace('_', ' ')}"
    return [f"<danger>In the morning {what} is gone:</> a cut tether, and hoofprints going away into the dark. "
            f"Someone on watch might have stopped it."]


def rest(game, kind: str) -> list[str]:
    """Rest: 'short' (1 hour), 'long' (8 hours) or 'night' (sleep until first light: at least 8 hours, at most 14; an
    8-hour sleep begun at dusk wakes you at three in the morning, in the dark, with the night's cold still to come).
    A long rest in the wilds may be interrupted."""
    from realmwalker.game.encounters import roll_encounter

    from realmwalker.game import spellwork

    lm = game.local
    if lm is not None and any(a.alert for a in lm.actors) and not spellwork.hidden(game, kind):
        return ["You can't rest with enemies hunting you."]
    from realmwalker.rules import body

    rng = game.world.rng.child(f"rest/{game.world.time}")
    notes = []
    hours = 1 if kind == "short" else 8
    if kind == "night":
        hours = max(8, min(14, round(game.minutes_to_dawn() / 60))) if game.light < 0.5 else 8
        kind = "long"
    from realmwalker.game.camp import camp_here

    from realmwalker.game import journey

    if kind == "long" and lm is None:
        notes += spellwork.before_rest(game)  # (a companion who knows a ward as a ritual casts it)
    camp = camp_here(game)
    fire = bool(camp and camp.fire)
    lay_down = set(journey.dangers(game))
    for hour in range(hours):
        game.pass_time(60, "sleep" if kind == "long" else "rest")
        if game.over is not None:
            return notes
        # Nobody sleeps through freezing to death: the body wakes them, and the rest is broken.
        woke = journey.woken(game, lay_down) if kind == "long" and hour < hours - 1 else None
        if woke is not None:
            notes.append(f"<danger>{woke}</> Your night is broken after {hour + 1} hour{'s' if hour else ''}.")
            return notes
        if lm is None and kind == "long":
            # A fire is seen from afar, but beasts fear it; a cold camp is harder to find.
            enc = roll_encounter(game, 60 * (0.4 if fire else 0.25))
            if enc is not None and fire and all(game.tables.creatures[c.def_id]["kind"] == "beast" for c in enc.creatures):
                if game.world.rng.child(f"firelight/{game.world.time}").chance(0.6):
                    notes.append("Eyes glint beyond the firelight in the night, but they do not come closer.")
                    enc = None
            if enc is not None:
                enc, said = spellwork.night_visitors(game, enc)  # (the camp's wards: Alarm, the Hound, the Hut...)
                notes += said
            if enc is not None:
                from realmwalker.game.companions import watching

                from realmwalker.game.camp import has_flag

                if spellwork.warded(game, "hound", "alarm") is not None:
                    pass  # (woken by the ward: the camp is up)
                elif watching(game):
                    enc.asleep = False
                    notes.append("<warn>The one on watch shakes you awake: something is coming.</>")
                elif has_flag(game, "alarm")[1] is not None:
                    enc.asleep = False  # the bells strung round the camp
                    notes.append("<warn>The bells on the cord round the camp jangle in the dark: something is coming.</>")
                else:
                    enc.asleep = True
                enc.spotted_first = False
                game.encounter = enc
                notes.append(f"<danger>Your rest is broken after {hour + 1} hour{'s' if hour else ''}.</>")
                return notes
    if kind == "long" and lm is None and game.over is None and game.leader.animals:
        notes += _rustlers(game, fire)
    if kind == "long" and game.over is None:
        from realmwalker.game.gear import check_snares

        notes += check_snares(game)
    if kind == "long" and lm is None and game.over is None:
        from realmwalker.game.camp import night_sound

        heard = night_sound(game) if game.flavour() else ""
        if heard and rng.chance(0.7):
            notes.append(heard)
    if kind == "long" and lm is None and game.party[1:]:
        from realmwalker.game import camp as camping
        from realmwalker.game import companions

        for c in companions.foragers(game):
            notes += camping.forage_while_resting(game, c)
        companions.react(game, "rest", quiet=True)
        talkers = companions.companions(game)
        if talkers and rng.chance(0.35):
            notes.append(companions.line(game, "camp", rng.choice(talkers), rng))
    from realmwalker.rules import magic

    sleepless = next((c for c in game.party if c.attuned and magic.flag(c, "no_rest_near")), None)
    from realmwalker.rules import feats

    chef = next((c for c in game.party if feats.has(c, "chef") and c is not sleepless and c.alive
                 and "cooks_utensils" in {it.def_id for it in c.inventory}), None)
    if kind == "short" and chef is not None:
        notes.append(f"{chef.name.split()[0]} cooks something hearty while the others rest.")
    for c in game.party:
        if sleepless is not None and c is not sleepless:
            notes.append(f"<warn>{c.name.split()[0]} lies awake beside {sleepless.name.split()[0]} and the thing "
                         f"they are bound to, and gets no good of the rest.</>")
            continue  # an artifact's flaw (DMG 2024): nobody near its bearer can rest
        if kind == "short":
            notes += progression.short_rest(c, game.tables, rng, meal=chef is not None)
        elif c.hunger >= 80 or c.thirst >= 85:
            notes.append(f"<warn>{c.name.split()[0]} is too {'hungry' if c.hunger >= 80 else 'thirsty'} to rest "
                         f"properly.</> Only a short rest's worth of good came of it.")
            notes += progression.short_rest(c, game.tables, rng)
        else:
            notes += progression.long_rest(c, game.tables, rng)
        if kind == "long":
            notes += body.sleep_recovery(c)
        body.clamp_hp(c)
    notes += _encouraging_song(game, sleepless)
    notes += _rousing_words(game, sleepless)
    return notes


def _rousing_words(game, sleepless) -> list[str]:
    """Inspiring Leader (2024): after a rest, up to six companions gain temporary hit points equal to the leader's
    level plus the modifier of the ability the feat raised (they carry into the next fight)."""
    from realmwalker.rules import feats
    from realmwalker.rules.character import modifier

    for c in game.party:
        if not feats.has(c, "inspiring_leader") or c is sleepless and len(game.party) > 1 or not c.alive:
            continue
        ability = next(((f.get("choices") or {}).get("increase") for f in feats.taken(c, "inspiring_leader")), "cha")
        amount = max(1, c.level + modifier(c.abilities.get(ability or "cha", 10)))
        for x in [x for x in game.party if x.alive][:6]:
            x.temp_hp = max(x.temp_hp, amount)
        return [f"{c.name.split()[0]} speaks a few plain words before they set off, and spirits lift "
                f"({amount} temporary hit points each)."]
    return []


def _encouraging_song(game, sleepless) -> list[str]:
    """Musician (2024): after a rest, a song with an instrument the musician plays gives Heroic Inspiration to as many
    companions as their proficiency bonus."""
    from realmwalker.rules import feats

    for c in game.party:
        if not feats.has(c, "musician") or c is sleepless and len(game.party) > 1:
            continue
        plays = set(c.tools)  # (any instrument they are proficient with)
        if not any(it.def_id in plays for it in c.inventory):
            continue
        given = [x for x in game.party if x is not c and x.alive][: 2 + (c.level - 1) // 4]
        for x in given:
            x.uses["heroic_inspiration"] = 1
        if given:
            return [f"{c.name.split()[0]} plays for the others, and they rise heartened (Heroic Inspiration)."]
    return []
