"""Going underground (M8): stairs, light, traps, searching, locks, chests and coffins, and the inhabitants.

Down there it is dark: you see as far as your torch or lantern throws its light (or your darkvision), and
torches burn down (a new one is lit from the packs when one gutters out). Traps wait in the corridors: a sharp eye
may spot one before stepping on it, and searching (s) finds traps and secret doors nearby. Locked doors and chests
can be picked with thieves' tools (Sleight of Hand) or forced (Athletics, and noisy). Opening a coffin in a crypt
is not always wise.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.rules import body, encounter
from realmwalker.rules import spells
from realmwalker.rules.inventory import remove_item
from realmwalker.rules.items import money_text
from realmwalker.world import dungeon as gen

SEARCH_RADIUS = 4
POOLS = {
    "cellars": ["bandits", "restless_dead", "goblins", "cultists", "rats"],
    "crypt": ["restless_dead", "zombies", "ghouls"],
    "tower": ["cultists", "bandits", "restless_dead"],
    "hideout": ["bandits", "footpads", "thugs"],
    "temple": ["cultists", "cultists", "cult_circle"],
    "cave": ["wolf_pack", "bear", "goblins", "spiders", "rats"],
    "warren": ["goblins", "goblins", "orc_raiders"],
    "lair": [],
}
BOSSES = {"crypt": "barrow_wight", "warren": "goblin_warband", "temple": "cult_temple", "hideout": "bandit_hideout",
          "lair": "dragon", "cave": "ogre", "cellars": "bandit_gang", "tower": "cult_circle"}
# Who else a master of that kind keeps about them, and what lives in any dark place.
KIN = {"bandit_gang": ["bandits", "footpads", "thugs"], "bandit_hideout": ["bandits", "footpads", "thugs"],
       "barrow_wight": ["restless_dead", "zombies", "ghouls"], "goblin_warband": ["goblins", "orc_raiders"],
       "cult_temple": ["cultists", "cult_circle"], "cult_circle": ["cultists"],
       "ogre": ["wolf_pack", "bear", "spiders"], "dragon": []}
VERMIN = ("rats", "spiders", "wild_dogs")


def in_dungeon(game) -> bool:
    lm = game.local
    return lm is not None and lm.kind == "dungeon"


def site_here(game):
    return game.world.site_at(game.player.x, game.player.y)


ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth")
FIRST_DOWN = (
    "The air is cold and still.",
    "The cold comes up the steps to meet you.",
    "The daylight gives out three steps in.",
    "The air down here has not been breathed for a long while.",
    "Your own noise comes back to you off the walls.",
)
DEEPER_DOWN = (
    "It is colder down here, and quieter.",
    "The quiet gets heavier the further down you go.",
    "The air is worse at this depth, and still.",
    "Whatever sound you make stays close to you down here.",
    "The dark down here has weight to it.",
)
BACK_UP = (
    "You climb up into daylight, or what passes for it.",
    "You come up into the open air and stand in it a moment.",
    "Daylight, and the smell of living things, and wind.",
    "You climb out. Whatever the weather is doing, it is better than down there.",
)


def ordinal(n: int) -> str:
    return ORDINALS[n - 1] if 1 <= n <= len(ORDINALS) else f"{n}th"


def terrain_id(game, lm, x: int, y: int) -> str:
    return lm.terrain_ids[int(lm.terrain[x, y])]


def set_terrain(lm, x: int, y: int, name: str) -> None:
    if name not in lm.terrain_ids:
        lm.terrain_ids.append(name)
    lm.terrain[x, y] = lm.terrain_ids.index(name)


def rng_for(game, what: str) -> RNG:
    return game.world.rng.child(f"dungeon/{what}/{game.world.time}/{game.player.lx},{game.player.ly}")


# ---------------------------------------------------------------------------- stairs
def descend(game, level: int, *, from_below: bool = False) -> None:
    site = site_here(game)
    if site is None:
        return
    lm = gen.get_dungeon(game.world, game.tables, site, level)
    p = game.player
    p.local_key = lm.key
    x, y = lm.entry
    if from_below:
        import numpy as np

        idx = lm.terrain_ids.index("stairs_down") if "stairs_down" in lm.terrain_ids else -1
        found = np.argwhere(lm.terrain == idx)
        if len(found):
            x, y = int(found[0][0]), int(found[0][1])
    p.lx, p.ly = x, y
    game.cue("stairs")
    populate(game, lm)
    if game.quests:
        from realmwalker.game import quests

        quests.on_arrive_dungeon(game, lm)
    from realmwalker.game import past

    past.on_arrive_dungeon(game, lm, site)  # a treasure the history left here
    name = lm.meta.get("name", "dark")
    rng = game.world.rng.child(f"descend/{lm.key}/{game.player.steps}")
    deep = lm.meta.get("depth", 1) > 1
    where = f"the {ordinal(level)} level of the {name}" if deep else f"the {name}"
    if from_below:
        game.say(f"You climb back up to {where}.", "place")
    else:
        air = rng.choice(FIRST_DOWN if level == 1 else DEEPER_DOWN)
        gained, notes = game.discover("deeper", f"deeper:{site.id}/{level}")
        game.say(f"You go down into {where}. {air}{gained}", "place")
        for note in notes:
            game.say(note, "good")
    light_up(game)
    if lm.meta.get("desc") and not lm.meta.get("desc_seen"):
        lm.meta["desc_seen"] = True
        game.say(lm.meta["desc"], "flavor")
    if game.world.politics.get("dragons"):
        from realmwalker.game import dragons

        warning = dragons.descend_warning(game, lm)
        if warning:
            game.say(warning, "danger")
    game.dirty = True


def ascend(game) -> None:
    lm = game.local
    level = int(lm.meta.get("level", 1))
    if level > 1:
        descend(game, level - 1, from_below=True)
        return
    from realmwalker.world.local import get_local_map

    surface = get_local_map(game.world, game.tables, game.player.x, game.player.y)
    game.player.local_key = surface.key
    game.player.lx, game.player.ly = gen.add_entrance(game.tables, surface)
    game.cue("stairs")
    rng = game.world.rng.child(f"surface/{game.player.steps}")
    game.say(rng.choice(BACK_UP), "place")
    game.dirty = True


def on_step(game, x: int, y: int) -> None:
    """After a step: stairs take you up or down; traps may spring; a hoard may wake its owner."""
    lm = game.local
    tid = terrain_id(game, lm, x, y)
    if tid == "stairs_down":
        if lm.kind == "dungeon":
            descend(game, int(lm.meta.get("level", 1)) + 1)
        elif site_here(game) is not None:
            descend(game, 1)
        return
    if tid == "stairs_up" and lm.kind == "dungeon":
        ascend(game)
        return
    if lm.kind != "dungeon":
        return
    if lm.meta.get("passwall"):  # (Passwall's hour over: the passage closes)
        from realmwalker.game import stonework

        if stonework.on_step(game):
            return  # (put out of the closing passage: this step is over)
    f = lm.features.get((x, y))
    if f and f.get("kind") == "trap" and not f.get("spent"):
        spring(game, lm, x, y, f)
    if tid == "hoard":
        wake_the_dragon(game, lm)


# ---------------------------------------------------------------------------- light
def light_radius(game) -> int:
    from realmwalker.rules import magic

    from realmwalker.game import waymagic

    glow = max([waymagic.spell_light(game)] + [magic.light(c) for c in game.party])  # (Light, Daylight, Continual
    lit = getattr(game, "lit", None)  # Flame's everburning torch)
    if any(c.attuned and magic.flag(c, "douses_flames") for c in game.party):
        return glow  # an artifact's flaw: flames gutter out around its bearer
    if lit and lit.get("hours", 0) > 0:
        return max(glow, int(game.tables.items.get(lit["def_id"]).get("light", {}).get("radius", 5)))
    return glow


def light_up(game) -> str | None:
    """Light a torch (or a lantern, with oil) from the packs if nothing is burning."""
    lit = getattr(game, "lit", None)
    if lit and lit.get("hours", 0) > 0:
        return None
    from realmwalker.rules import magic

    from realmwalker.game import waymagic

    if any(magic.light(c) for c in game.party) or waymagic.spell_light(game):
        return None  # something magic already sheds light
    items = game.tables.items
    best = None
    for c in game.party:
        for it in c.inventory:
            light = items.get(it.def_id).get("light")
            if not light:
                continue
            fuel = light.get("fuel")
            if fuel and not any(i.def_id == fuel for m in game.party for i in m.inventory):
                continue
            if best is None or light["radius"] > items.get(best[1].def_id)["light"]["radius"]:
                best = (c, it)
    if best is None:
        game.lit = None
        game.say("<warn>It is dark, and you have nothing to light.</> You can see only what you can touch.", "warn")
        return None
    c, it = best
    light = items.get(it.def_id)["light"]
    if light.get("fuel"):
        owner = next(m for m in game.party if any(i.def_id == light["fuel"] for i in m.inventory))
        flask = next(i for i in owner.inventory if i.def_id == light["fuel"])
        remove_item(owner, flask.uid, 1)
    else:
        remove_item(c, it.uid, 1)
    game.lit = {"def_id": it.def_id, "hours": float(light.get("hours", 1))}
    from realmwalker.core.textgen import a_or_an

    name = items.get(it.def_id)["name"]
    text = f"{body.first(c)} lights {a_or_an(name)}."
    game.say(text, "dim")
    return text


def burn(game, minutes: float) -> None:
    lit = getattr(game, "lit", None)
    if not lit:
        return
    lit["hours"] -= minutes / 60.0
    if lit["hours"] <= 0:
        name = game.tables.items.get(lit["def_id"])["name"]
        game.lit = None
        game.say(f"The {name} gutters out.", "warn")
        light_up(game)


# ---------------------------------------------------------------------------- traps and searching
def helps(game, key: str):
    """The best that anything the party carries does for `key` (data/items.json "helps": a pole probing for traps, a
    magnifying glass searching, a portable ram forcing a door): (value, item name), or (0, "")."""
    items = game.tables.items
    best, name = 0, ""
    for c in game.party:
        for it in c.inventory:
            v = (items.get(it.def_id).get("helps") or {}).get(key)
            if v and int(v) > best:
                best, name = int(v), items.get(it.def_id)["name"]
    return best, name


def passive(game, skill: str) -> tuple[int, object]:
    best, who = -99, game.leader
    for c in game.party:
        v = 10 + game.sheet(c).skill_bonus(skill)
        if v > best:
            best, who = v, c
    return best, who


def spring(game, lm, x: int, y: int, f: dict) -> None:
    name, damage, dtype = gen.TRAPS.get(f.get("trap", "pit"), gen.TRAPS["pit"])
    if f.get("found"):
        game.say(f"You step carefully around {name}.", "dim")
        return
    from realmwalker.game import waymagic

    if waymagic.ethereal_here(game):
        return  # (on the Border Ethereal nothing of this side touches you)
    if not f.get("found"):
        eyes, who = passive(game, "perception")
        probe, tool = helps(game, "traps")
        if eyes + probe >= int(f.get("dc", 13)):
            f["found"] = True
            how = f", +{probe} {tool}" if probe else ""
            game.say(f"<good>{who.name.split()[0]} spots {name} and stops you just in time.</> "
                     f"<dim>(passive Perception {eyes + probe}{how} vs {f['dc']})</>", "good")
            return
    rng = rng_for(game, "trap")
    c = game.leader
    s = game.sheet(c)
    ready = bool(f.get("sensed"))  # (Find Traps: you knew something waited, and were ready for it)
    roll = dice.d20(rng, advantage=ready, disadvantage=s.armour_disadvantage("dex")).natural
    save = roll + s.save_bonus("dex")
    if f.get("trap", "pit") == "pit":
        from realmwalker.rules.engine import hazards

        damage = hazards.falling(game.tables, int(f.get("depth", 20))) or damage  # a fall: 1d6 for every 10 feet
        caught = feather_fall(game, c)
        if caught:
            f["found"] = True
            f["spent"] = True
            game.say(caught, "magic")
            return
    dmg = dice.roll(damage, rng).total
    if save >= int(f.get("dc", 13)):
        dmg //= 2
    left = c.hp - dmg
    c.hp = max(0, left)
    f["found"] = True
    f["spent"] = True
    game.cue("trap")
    game.say(f"<danger>You spring {name}!</> {c.name.split()[0]} takes {dmg} {dtype} damage. "
             f"<dim>(Dexterity save {save} vs {f['dc']})</>", "danger")
    if dmg >= 8:
        from realmwalker.rules.wounds import make_wound

        part = "left_leg" if f.get("trap") == "pit" else rng.choice(["torso", "left_arm", "right_arm", "right_leg"])
        part = "torso" if f"lost_{part}" in c.injuries else part
        w = make_wound(part, dtype, 1 if dmg < 14 else 2, rng, now=game.world.time, note=name)
        if w is not None:
            c.wounds.append(w)
    if c.hp <= 0 and -left < c.max_hp:
        # Knocked senseless, as in a fight: 0 hit points is down, not dead. Only a blow that would take a whole
        # life's worth of hit points below nothing kills outright (the 5e rule). Until 2026-10 every trap that took
        # the last hit point killed, and a careful explorer at half strength died of a pit.
        from realmwalker.game.fight import lie_senseless

        c.hp = 1
        game.say(f"<danger>{c.name.split()[0]} goes down and lies still.</> " + lie_senseless(game, 1), "danger")
        return
    if c.hp <= 0 and getattr(c, "death_cause", None) is None:
        c.death_cause = f"killed by {name}"  # not "died of their hurts": the darts did it
    from realmwalker.game import survival

    survival.check_death(game, c)


def feather_fall(game, faller) -> str:
    """Someone drops into a pit: whoever in the party has Feather Fall ready casts it with the reaction (a level 1
    slot), and the fall does no harm. Returns what to say ("" when nobody can)."""
    t = game.tables
    for c in sorted((m for m in game.party if m.alive and m.hp > 0 and m.spells), key=lambda m: m is not faller):
        if "feather_fall" not in spells.known_spells(c, t):
            continue
        ok, _why = spells.can_cast(c, t, "feather_fall")
        slot = spells.lowest_free_slot(c, t, 1)
        if not ok or slot is None:
            continue
        spells.spend_slot(c, slot)
        from realmwalker.core.textgen import escape_markup

        me, them = escape_markup(body.first(c)), escape_markup(body.first(faller))
        who = "" if c is faller else f"{me} speaks a word as {them} drops: "
        return (f"<magic>{who}{them} drifts down into the pit like a feather</> and lands unharmed, and climbs out "
                f"again. (Feather Fall)")
    return ""


def search(game) -> list[str]:
    """Look carefully around you for a minute: traps and hidden doors within a few steps."""
    lm = game.local
    if lm is None:
        return ["There is nothing here to search."]
    game.pass_seconds(60)
    p = game.player
    skill = "investigation" if max(game.sheet(c).skill_bonus("investigation") for c in game.party) > \
        max(game.sheet(c).skill_bonus("perception") for c in game.party) else "perception"
    best, who = passive(game, skill)
    rng = rng_for(game, "search")
    glass, tool = helps(game, "search")
    roll = dice.d20(rng, advantage=bool(glass)).natural + best - 10
    near = [f for (x, y), f in lm.features.items() if f.get("sensed") and not f.get("found")
            and max(abs(x - p.lx), abs(y - p.ly)) <= SEARCH_RADIUS]
    sensed = dice.d20(rng.child("sensed"), advantage=True).natural + best - 10 if near else roll  # (Find Traps)
    out = []
    for (x, y), f in list(lm.features.items()):
        if max(abs(x - p.lx), abs(y - p.ly)) > SEARCH_RADIUS:
            continue
        best_roll = max(roll, sensed) if f.get("sensed") else roll
        if f.get("kind") == "trap" and not f.get("found") and best_roll >= int(f.get("dc", 13)):
            f["found"] = True
            name = gen.TRAPS.get(f.get("trap", "pit"), gen.TRAPS["pit"])[0]
            out.append(f"<good>{who.name.split()[0]} finds {name} hidden in the floor.</>")
        elif f.get("kind") == "secret" and roll >= int(f.get("dc", 14)):
            set_terrain(lm, x, y, "door_closed")
            del lm.features[(x, y)]
            out.append(f"<good>{who.name.split()[0]} finds a hidden door in the wall!</>")
            from realmwalker.game import magic_items

            magic_items.notice(game, "discovery")
            if game.party[1:]:
                from realmwalker.game.companions import react

                react(game, "discovery", quiet=True)
    label = game.tables.rules["skills"][skill]["name"] + (f", {tool}: advantage" if glass else "")
    if not out:
        out.append(f"You search carefully and find nothing. <dim>({label} {roll})</>")
    else:
        out.append(f"<dim>({label} {roll})</>")
    return out


# ---------------------------------------------------------------------------- locks, chests and coffins
def has_tools(game) -> bool:
    return any(it.def_id == "thieves_tools" for c in game.party for it in c.inventory)


def best_at(game, skill: str):
    return max(game.party, key=lambda c: game.sheet(c).skill_bonus(skill))


def unlock(game, lm, x: int, y: int, dc: int) -> tuple[bool, str]:
    """Pick the lock if you have the tools, otherwise force it."""
    rng = rng_for(game, "lock")
    game.pass_seconds(60)
    if has_tools(game):
        who = best_at(game, "sleight_of_hand")
        bonus = game.sheet(who).skill_bonus("sleight_of_hand")
        trained = "thieves_tools" in who.tools
        if trained:
            bonus += game.sheet(who).proficiency
        # PHB 2024: trained with the tools and in Sleight of Hand as well, the check has advantage
        adv = trained and ("sleight_of_hand" in who.skills or "sleight_of_hand" in who.expertise)
        hampered = game.sheet(who).armour_disadvantage("dex")
        roll = dice.d20(rng, advantage=adv and not hampered, disadvantage=hampered and not adv).natural + bonus
        if roll >= dc:
            game.cue("unlock")
            return True, f"{who.name.split()[0]} picks the lock. <dim>(Sleight of Hand {roll} vs {dc})</>"
        return False, f"The lock resists {who.name.split()[0]}'s picks. <dim>(Sleight of Hand {roll} vs {dc})</>"
    who = best_at(game, "athletics")
    # A crowbar: leverage (advantage on the roll, as in the Player's Handbook), and a crack instead of a crash.
    bar = any(game.tables.items.get(it.def_id).get("pry") for c in game.party for it in c.inventory)
    hampered = game.sheet(who).armour_disadvantage("str")
    ram, ram_name = helps(game, "force")  # (a portable ram: +4, PHB 2024)
    roll = dice.d20(rng, advantage=bar and not hampered, disadvantage=hampered and not bar).natural + \
        game.sheet(who).skill_bonus("athletics") + ram
    alert_nearby(game, lm, x, y, 6 if bar else 12)
    adv = (", crowbar: advantage" if bar else "") + (f", {ram_name} +{ram}" if ram else "")
    if roll >= dc + 2:
        if bar:
            return True, (f"{who.name.split()[0]} gets the crowbar in and levers it open with a crack. "
                          f"<dim>(Athletics {roll} vs {dc + 2}{adv})</>")
        return True, (f"{who.name.split()[0]} breaks it open with a crash that echoes a long way. "
                      f"<dim>(Athletics {roll} vs {dc + 2}{adv})</>")
    if bar:
        return False, (f"{who.name.split()[0]} heaves on the crowbar; it groans and holds. "
                       f"<dim>(Athletics {roll} vs {dc + 2}{adv}; thieves' tools would be quieter)</>")
    return False, (f"{who.name.split()[0]} throws a shoulder at it; it holds, and the noise carries. "
                   f"<dim>(Athletics {roll} vs {dc + 2}{adv}; thieves' tools would be quieter, a crowbar surer)</>")


def alert_nearby(game, lm, x: int, y: int, radius: int) -> None:
    for a in lm.actors:
        if max(abs(a.x - x), abs(a.y - y)) <= radius:
            a.alert = True


def bump(game, x: int, y: int) -> bool:
    """Walking into a locked door, a chest or a coffin. True if something happened (no step taken)."""
    lm = game.local
    if lm is None:
        return False
    tid = terrain_id(game, lm, x, y)
    if tid == "door_locked":
        f = lm.features.get((x, y), {"dc": 13})
        if f.get("arcane"):  # (Arcane Lock: it opens for the party alone)
            from realmwalker.game import stonework

            return stonework.through_own_lock(game, lm, x, y)
        ok, text = unlock(game, lm, x, y, int(f.get("dc", 13)))
        game.say(text, "info" if ok else "warn")
        if ok:
            set_terrain(lm, x, y, "door_open")
            lm.features.pop((x, y), None)
        return True
    if tid in ("chest", "sarcophagus"):
        open_chest(game, lm, x, y)
        return True
    if tid == "captive":
        from realmwalker.game import quests

        quests.free_captive(game, lm, x, y)
        return True
    return False


def open_chest(game, lm, x: int, y: int) -> None:
    f = lm.features.get((x, y))
    if f is None or f.get("opened"):
        game.say("It is empty.", "dim")
        return
    if f.get("locked"):
        ok, text = unlock(game, lm, x, y, int(f["locked"]))
        game.say(text, "info" if ok else "warn")
        if not ok:
            return
        f["locked"] = 0
    grave = bool(f.get("grave"))
    f["opened"] = True
    game.cue("chest")
    if not grave:
        set_terrain(lm, x, y, "chest_open")
    rng = rng_for(game, "chest")
    if f.get("contents") is not None:  # (fixed already: Detect Magic looked into it)
        from realmwalker.rules.items import Item

        kept = f.pop("contents")
        items, money = [Item.from_dict(d) for d in kept["items"]], int(kept["money"])
    else:
        items, money = _roll_chest(game, lm, f, rng)
    if f.get("hoard"):
        game.say("<loot>This is the hoard of whoever ruled this place.</>", "loot")
    if any(it.magic for it in items):
        from realmwalker.game import magic_items

        magic_items.notice(game, "magic_found")
    if f.get("quest") is not None:
        from realmwalker.game import quests

        items = quests.on_chest(game, f) + items
    if f.get("artifact") is not None:
        from realmwalker.game import past

        items = past.on_chest(game, f) + items
    p = game.player
    if items:
        lm.items.setdefault((p.lx, p.ly), []).extend(items)
    if money:
        game.leader.money += money
    names = ", ".join(game.tables.items.name(i) for i in items)
    what = "the coffin" if grave else "the chest"
    if items or money:
        game.say(f"<loot>In {what}: {names}{', and ' if names and money else ''}"
                 f"{money_text(money) if money else ''}.</>" + (" <dim>(g to pick up)</>" if items else ""), "loot")
    else:
        game.say(f"{what.capitalize()} holds nothing but dust.", "dim")
    if grave:
        from realmwalker.game import magic_items

        magic_items.notice(game, "desecration")
        if game.party[1:]:
            from realmwalker.game.companions import react

            react(game, "desecration")
        if f.get("rouse"):
            rouse_the_dead(game, lm, x, y, rng)


def _roll_chest(game, lm, f: dict, rng: RNG) -> tuple[list, int]:
    """What a chest holds (DMG 2024: by the level's strength and its folk's treasure theme; the ruler's hoard)."""
    from realmwalker.game import treasure

    cr, theme = float(lm.meta.get("cr", max(0, int(f.get("treasure", 1)) - 1.5))), lm.meta.get("theme")
    if f.get("hoard"):
        return treasure.hoard(game, cr, rng, theme=theme)
    return treasure.roll(game, int(f.get("treasure", 1)), rng, grave=bool(f.get("grave")), cr=cr, theme=theme)


def fix_contents(game, lm, pos) -> tuple[list[dict], int]:
    """A closed chest's contents, settled now and kept until it is opened (Detect Magic senses what is inside):
    (the items as dicts, money). The work's and the history's own things are added when it is opened."""
    f = lm.features[pos]
    if f.get("contents") is None:
        items, money = _roll_chest(game, lm, f, game.world.rng.child(f"dungeon/chest/{lm.key}/{pos[0]},{pos[1]}"))
        f["contents"] = {"items": [it.to_dict() for it in items], "money": int(money)}
    return f["contents"]["items"], int(f["contents"]["money"])


def rouse_the_dead(game, lm, x: int, y: int, rng: RNG) -> None:
    from realmwalker.game.encounters import LocalActor
    from realmwalker.rules.creatures import spawn_group

    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    spot = next(((x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1))
                 if lm.in_bounds(x + dx, y + dy) and walk[x + dx, y + dy]
                 and (x + dx, y + dy) != (game.player.lx, game.player.ly)), None)
    if spot is None:
        return
    creatures = spawn_group(game.tables, "restless_dead", rng, now=game.world.time, party_size=len(game.party))
    actor = LocalActor(len(lm.actors) + 1, "restless_dead", spot[0], spot[1], creatures)
    actor.alert = True
    lm.actors.append(actor)
    game.say("<danger>Something in the coffin sits up.</>", "danger")


def wake_the_dragon(game, lm) -> None:
    for a in lm.actors:
        if a.group == "dragon" and not a.alert:
            a.alert = True
            game.say("<danger>The gold shifts under your feet. Somewhere above it, an eye opens.</>", "danger")


def take_hoard(game) -> list[str]:
    """Filling your pockets from a dragon's hoard (g on the gold)."""
    lm = game.local
    p = game.player
    if lm is None or terrain_id(game, lm, p.lx, p.ly) != "hoard":
        return []
    f = lm.meta.setdefault("hoard", {"left": 40})
    if f["left"] <= 0:
        return ["There is nothing left here worth carrying that you can carry."]
    rng = rng_for(game, "hoard")
    from realmwalker.game import treasure

    if "copper" not in f:
        # DMG 2024: a dragon is fond of amassing treasure, so its hoard is the table rolled twice, for its CR.
        cr = max((float(game.tables.creatures[c.def_id].get("cr", 0)) for a in lm.actors if a.group == "dragon"
                  for c in a.creatures), default=10.0)
        items, copper = treasure.hoard(game, cr, rng.child("whole"), theme=None, double=True)
        f["copper"] = copper
        f["items"] = [it.to_dict() for it in items]
    grab = f["copper"] if f["left"] <= 1 else min(f["copper"], max(100, f["copper"] // f["left"] *
                                                                    rng.randint(70, 130) // 100))
    f["copper"] -= grab
    f["left"] -= 1
    game.leader.money += grab
    game.cue("coins")
    if f["items"] and (rng.chance(0.3) or f["left"] <= len(f["items"])):
        from realmwalker.rules.items import Item

        lm.items.setdefault((p.lx, p.ly), []).append(Item.from_dict(f["items"].pop(0)))
    wake_the_dragon(game, lm)
    game.pass_seconds(30)
    return [f"<loot>You stuff your pockets: {money_text(grab)}.</>"]


# ---------------------------------------------------------------------------- inhabitants
def populate(game, lm) -> None:
    if lm.populated:
        return
    lm.populated = True
    from realmwalker.game.encounters import LocalActor
    from realmwalker.rules.creatures import spawn_group

    meta = lm.meta
    style = meta.get("style", "cellars")
    level, depth = int(meta.get("level", 1)), int(meta.get("depth", 1))
    rooms = meta.get("rooms", [])
    rng = game.world.rng.child(f"dungeon-folk/{lm.key}")
    site = game.world.sites[meta["site"]] if 0 <= meta.get("site", -1) < len(game.world.sites) else None
    pool = [g for g in POOLS.get(style, []) if g in game.tables.creatures.encounters]
    if site is not None and style == "cave":
        extra = [g for g in game.tables.creatures.site_inhabitants.get(site.kind, [])
                 if g in game.tables.creatures.encounters]
        pool = pool + extra
    walk = game.tables.terrain.walk[game.remap_for(lm)[lm.terrain]]
    groups: list[tuple[int, str]] = []
    from realmwalker.game import past

    boss, boss_name = past.boss_for(game, site, BOSSES.get(style))  # the beast or the dead king of the history
    if game.quests and site is not None:
        from realmwalker.game import quests

        quest_boss = quests.boss_for(game, site, boss)
        if quest_boss != boss:
            boss, boss_name = quest_boss, None
    meta["boss"] = boss
    if boss_name:
        meta["boss_name"] = boss_name
    # Whoever holds the place holds most of it: a bandit cellar is bandits, with rats in the corners.
    kin = [g for g in KIN.get(boss, []) if g in game.tables.creatures.encounters] or pool
    pool = kin * 3 + [g for g in pool if g in VERMIN]
    hidden = set(meta.get("hidden", []))
    open_rooms = [i for i in range(len(rooms)) if i not in hidden]
    last = open_rooms[-1] if open_rooms else len(rooms) - 1
    has_boss = level == depth and boss in game.tables.creatures.encounters and last >= 1
    if has_boss:
        groups.append((last, boss))
    others = [i for i in open_rooms[1:] if not (groups and i == last)]
    rng.shuffle(others)
    for i in others[: min(len(others), 1 + level)]:
        if pool:
            groups.append((i, rng.choice(pool)))
    for n, (room, group) in enumerate(groups):
        rx, ry, rw, rh = rooms[room]
        cells = [(x, y) for x in range(rx, rx + rw) for y in range(ry, ry + rh)
                 if lm.in_bounds(x, y) and walk[x, y]]
        if not cells:
            continue
        x, y = rng.choice(cells)
        from realmwalker.game.encounters import land_budget

        boss_band = has_boss and n == 0
        worth = None if group == "dragon" else land_budget(game, rng.child(f"budget{n}"),
                                                           difficulty="high" if boss_band else "moderate",
                                                           deeper=level - 1)
        creatures = spawn_group(game.tables, group, rng.child(str(n)), now=game.world.time,
                                party_size=len(game.party), budget=worth)
        if group == "dragon" and site is not None:
            d = gen.dragon_at(game.world, site)
            if d is not None and creatures:
                creatures[0].name = d["name"]
                creatures[0].named = True
                encounter.legend_grows(game.tables, creatures[0], game.leader.level)
        elif boss_name and has_boss and n == 0 and creatures:
            creatures[0].name = boss_name  # the troll the old songs are about; the king who was laid here
            creatures[0].named = True
            encounter.legend_grows(game.tables, creatures[0], game.leader.level)
        lm.actors.append(LocalActor(len(lm.actors) + 1, group, x, y, creatures))
    _treasure_of_the_place(game, lm, rng.child("hoard"), has_boss)


def _treasure_of_the_place(game, lm, rng: RNG, has_boss: bool) -> None:
    """What the chests hold is the business of who lives here (DMG 2024): the level's strength (the highest Challenge
    Rating among its folk) and their treasure theme; on the deepest level, the last and best chest is the ruler's
    hoard."""
    from realmwalker.game import treasure

    folk = [c.def_id for a in lm.actors for c in a.creatures]
    meta = lm.meta
    meta["cr"] = max((float(game.tables.creatures[d].get("cr", 0)) for d in folk), default=0.0)
    meta["theme"] = treasure.theme_of(game, folk, rng) if folk else rng.choice(list(treasure.THEMES))
    if not has_boss:
        return
    chests = [(f.get("treasure", 1), pos) for pos, f in lm.features.items()
              if f.get("kind") == "chest" and not f.get("grave") and f.get("quest") is None
              and f.get("artifact") is None]
    if chests:
        _tier, pos = max(chests)
        lm.features[pos]["hoard"] = True
