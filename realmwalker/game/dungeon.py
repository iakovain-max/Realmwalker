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
from realmwalker.rules import body
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


def needs_words(lm) -> bool:
    return (lm is not None and lm.kind == "dungeon" and lm.meta.get("desc_source") == "fallback"
            and not lm.meta.get("ai_asked") and not lm.meta.get("desc_seen"))


def dressing_facts(game, lm) -> dict:
    """What the AI is told about a level it has never seen: only what is really down here."""
    site = game.world.site_at(game.player.x, game.player.y)
    meta = lm.meta
    kinds = {f.get("kind") for f in lm.features.values()}
    sights = []
    if "chest" in kinds:
        sights.append("chests or coffins")
    if "trap" in kinds:
        sights.append("traps")
    if "secret" in kinds:
        sights.append("a hidden room")
    terrains = set(lm.terrain_ids)
    for tid, word in (("sarcophagus", "stone coffins"), ("bones", "old bones"), ("bedroll", "bedrolls"),
                      ("altar", "an altar"), ("hoard", "a heap of gold"), ("shallow_water", "standing water"),
                      ("rubble", "fallen stone"), ("pillar", "pillars"), ("table", "tables")):
        if tid in terrains:
            sights.append(word)
    groups = sorted({game.tables.creatures.encounters[a.group]["name"] for a in lm.actors
                     if a.group in game.tables.creatures.encounters})
    return {
        "place": site.name if site is not None else "a hole in the ground",
        "kind": site.kind if site is not None else "ruin",
        "style": meta.get("name", "dark"),
        "level": str(meta.get("level", 1)),
        "depth": str(meta.get("depth", 1)),
        "master": ", ".join(groups) or "nothing living",
        "sights": ", ".join(sights) or "bare stone",
    }


def apply_description(lm, data: dict) -> bool:
    """Keep the AI's words, unless the player has already read the built-in ones."""
    if lm is None or lm.meta.get("desc_seen") or not data.get("description"):
        return False
    lm.meta["desc"] = str(data["description"]).strip()
    lm.meta["desc_source"] = "ai"
    return True


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
    populate(game, lm)
    if game.quests:
        from realmwalker.game import quests

        quests.on_arrive_dungeon(game, lm)
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
        text = lm.meta["desc"]
        ai = lm.meta.get("desc_source") == "ai"
        game.say(f"<ai>{text}</>" if ai else text, "flavor")
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
    f = lm.features.get((x, y))
    if f and f.get("kind") == "trap" and not f.get("spent"):
        spring(game, lm, x, y, f)
    if tid == "hoard":
        wake_the_dragon(game, lm)


# ---------------------------------------------------------------------------- light
def light_radius(game) -> int:
    from realmwalker.rules import magic

    glow = max((magic.light(c) for c in game.party), default=0)
    lit = getattr(game, "lit", None)
    if lit and lit.get("hours", 0) > 0:
        return max(glow, int(game.tables.items.get(lit["def_id"]).get("light", {}).get("radius", 5)))
    return glow


def light_up(game) -> str | None:
    """Light a torch (or a lantern, with oil) from the packs if nothing is burning."""
    lit = getattr(game, "lit", None)
    if lit and lit.get("hours", 0) > 0:
        return None
    from realmwalker.rules import magic

    if any(magic.light(c) for c in game.party):
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
    if not f.get("found"):
        eyes, who = passive(game, "perception")
        if eyes >= int(f.get("dc", 13)):
            f["found"] = True
            game.say(f"<good>{who.name.split()[0]} spots {name} and stops you just in time.</> "
                     f"<dim>(passive Perception {eyes} vs {f['dc']})</>", "good")
            return
    rng = rng_for(game, "trap")
    c = game.leader
    s = game.sheet(c)
    roll = dice.d20(rng).natural
    save = roll + s.save_bonus("dex")
    dmg = dice.roll(damage, rng).total
    if save >= int(f.get("dc", 13)):
        dmg //= 2
    c.hp = max(0, c.hp - dmg)
    f["found"] = True
    f["spent"] = True
    game.say(f"<danger>You spring {name}!</> {c.name.split()[0]} takes {dmg} {dtype} damage. "
             f"<dim>(Dexterity save {save} vs {f['dc']})</>", "danger")
    if dmg >= 8:
        from realmwalker.rules.wounds import make_wound

        part = "left_leg" if f.get("trap") == "pit" else rng.choice(["torso", "left_arm", "right_arm", "right_leg"])
        w = make_wound(part, dtype, 1 if dmg < 14 else 2, rng, now=game.world.time, note=name)
        if w is not None:
            c.wounds.append(w)
    if c.hp <= 0 and getattr(c, "death_cause", None) is None:
        c.death_cause = f"killed by {name}"  # not "died of their hurts": the darts did it
    from realmwalker.game import survival

    survival.check_death(game, c)


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
    roll = dice.d20(rng).natural + best - 10
    out = []
    for (x, y), f in list(lm.features.items()):
        if max(abs(x - p.lx), abs(y - p.ly)) > SEARCH_RADIUS:
            continue
        if f.get("kind") == "trap" and not f.get("found") and roll >= int(f.get("dc", 13)):
            f["found"] = True
            name = gen.TRAPS.get(f.get("trap", "pit"), gen.TRAPS["pit"])[0]
            out.append(f"<good>{who.name.split()[0]} finds {name} hidden in the floor.</>")
        elif f.get("kind") == "secret" and roll >= int(f.get("dc", 14)):
            set_terrain(lm, x, y, "door_closed")
            del lm.features[(x, y)]
            out.append(f"<good>{who.name.split()[0]} finds a hidden door in the wall!</>")
            if game.party[1:]:
                from realmwalker.game.companions import react

                react(game, "discovery", quiet=True)
    label = game.tables.rules["skills"][skill]["name"]
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
        if "thieves_tools" in who.tools:
            bonus += game.sheet(who).proficiency
        roll = dice.d20(rng).natural + bonus
        if roll >= dc:
            return True, f"{who.name.split()[0]} picks the lock. <dim>(Sleight of Hand {roll} vs {dc})</>"
        return False, f"The lock resists {who.name.split()[0]}'s picks. <dim>(Sleight of Hand {roll} vs {dc})</>"
    who = best_at(game, "athletics")
    roll = dice.d20(rng).natural + game.sheet(who).skill_bonus("athletics")
    alert_nearby(game, lm, x, y, 12)
    if roll >= dc + 2:
        return True, (f"{who.name.split()[0]} breaks it open with a crash that echoes a long way. "
                      f"<dim>(Athletics {roll} vs {dc + 2})</>")
    return False, (f"{who.name.split()[0]} throws a shoulder at it; it holds, and the noise carries. "
                   f"<dim>(Athletics {roll} vs {dc + 2}; thieves' tools would be quieter)</>")


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
    if not grave:
        set_terrain(lm, x, y, "chest_open")
    from realmwalker.game import treasure

    rng = rng_for(game, "chest")
    items, money = treasure.roll(game, int(f.get("treasure", 1)), rng, grave=grave)
    if f.get("quest") is not None:
        from realmwalker.game import quests

        items = quests.on_chest(game, f) + items
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
        if game.party[1:]:
            from realmwalker.game.companions import react

            react(game, "desecration")
        if f.get("rouse"):
            rouse_the_dead(game, lm, x, y, rng)


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
    grab = rng.randint(3000, 12000)
    f["left"] -= 1
    game.leader.money += grab
    from realmwalker.game import treasure

    items, _ = treasure.roll(game, 5, rng)
    if items:
        lm.items.setdefault((p.lx, p.ly), []).extend(items[:1])
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
    boss = BOSSES.get(style)
    if game.quests and site is not None:
        from realmwalker.game import quests

        boss = quests.boss_for(game, site, boss)
    meta["boss"] = boss
    # Whoever holds the place holds most of it: a bandit cellar is bandits, with rats in the corners.
    kin = [g for g in KIN.get(boss, []) if g in game.tables.creatures.encounters] or pool
    pool = kin * 3 + [g for g in pool if g in VERMIN]
    hidden = set(meta.get("hidden", []))
    open_rooms = [i for i in range(len(rooms)) if i not in hidden]
    last = open_rooms[-1] if open_rooms else len(rooms) - 1
    if level == depth and boss in game.tables.creatures.encounters and last >= 1:
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
        creatures = spawn_group(game.tables, group, rng.child(str(n)), now=game.world.time,
                                party_size=len(game.party))
        if group == "dragon" and site is not None:
            d = gen.dragon_at(game.world, site)
            if d is not None and creatures:
                creatures[0].name = d["name"]
                creatures[0].named = True
        lm.actors.append(LocalActor(len(lm.actors) + 1, group, x, y, creatures))
