"""Dragons (M8): the worst thing in the world, and the only one with a name everybody knows.

A world's dragons are made with its history (`world/history.py`): some were slain by heroes long ago, the rest
are only sleeping, each in a lair (a site in the mountains). A sleeping dragon is not a quiet neighbour: while
you play it wakes now and then to burn a village or take tribute in cattle and gold (`world/politics.py`), and
the news of it travels. The country around a lair is marked: burned trees, bones, no birds.

Killing one is the greatest thing a party can do: the world hears of it, the tribute stops, and the name of
whoever did it goes into the chronicle beside the old heroes.

Here: what the player sees and does. The dragon's own records live in `world.politics["dragons"]`.
"""

from __future__ import annotations

import math

from realmwalker.world import factions as fx

DRAGON_KINDS = ("dragon",)  # creature "kind" in data/creatures.json
SIGN_RANGE = 3  # tiles from the lair where the land shows it


def records(world) -> list[dict]:
    return world.politics.get("dragons", [])


def living(world) -> list[dict]:
    return [d for d in records(world) if d.get("alive") and 0 <= d.get("lair", -1) < len(world.sites)]


def at_site(world, site) -> dict | None:
    for d in living(world):
        if d["lair"] == site.id:
            return d
    return None


def near(game, x: int | None = None, y: int | None = None) -> dict | None:
    """The dragon whose lair is within sight of here, if any."""
    w = game.world
    x = game.player.x if x is None else x
    y = game.player.y if y is None else y
    for d in living(w):
        lair = w.sites[d["lair"]]
        if math.hypot(lair.x - x, lair.y - y) <= SIGN_RANGE:
            return d
    return None


def tribute_towns(world, d: dict, within: float = 12.0) -> list:
    lair = world.sites[d["lair"]]
    return [s for s in world.settlements if math.hypot(s.x - lair.x, s.y - lair.y) <= within]


def sign_text(game, d: dict) -> str:
    """What the land around a lair looks like (once for each stretch of country)."""
    w = game.world
    lair = w.sites[d["lair"]]
    here = math.hypot(lair.x - game.player.x, lair.y - game.player.y)
    signs = game.tables.politics["dragons"].get("signs", [])
    rng = w.rng.child(f"dragon-sign/{d['name']}/{game.player.x},{game.player.y}")
    text = rng.choice(signs) if signs else "The country here is burned, and there are bones in the grass."
    if here <= 1:
        return f"<danger>{text}</> <danger>{lair.name[:1].upper() + lair.name[1:]} is the lair of {d['name']}.</>"
    return f"<warn>{text}</>"


def arrive(game) -> None:
    """Walking into the country around a lair: the land warns you."""
    d = near(game)
    if d is None:
        return
    seen = game.renown.flags.setdefault("dragon_signs", [])
    key = f"{d['name']}/{game.player.x // 2},{game.player.y // 2}"
    if key in seen:
        return
    seen.append(key)
    del seen[:-20]
    game.say(sign_text(game, d), "danger")


def descend_warning(game, lm) -> str | None:
    site = game.world.site_at(game.player.x, game.player.y)
    if site is None:
        return None
    d = at_site(game.world, site)
    if d is None:
        return None
    return (f"<danger>The heat comes up the steps at you, and a smell of burned metal. {d['name']} is down here, "
            f"and it is not a story.</>")


# ---------------------------------------------------------------------------- killing one
def is_dragon(game, creature) -> bool:
    return game.tables.creatures[creature.def_id].get("kind") in DRAGON_KINDS


def on_battle(game, result) -> None:
    """A dragon dead at your feet: the world will hear of this for a hundred years."""
    if result.outcome != "victory":
        return
    slain = [c for c in result.dead if is_dragon(game, c)]
    if not slain:
        return
    w = game.world
    site = w.site_at(game.player.x, game.player.y)
    for creature in slain:
        d = next((d for d in living(w) if d["name"] == creature.name), None)
        if d is None and site is not None:
            d = at_site(w, site)
        if d is None:
            continue
        mark_slain(game, d)


def mark_slain(game, d: dict) -> None:
    from realmwalker.game import reputation
    from realmwalker.world.politics import year_of

    w = game.world
    d["alive"] = False
    d["slain_by"] = game.leader.name
    year = year_of(w, game.tables)
    d["slain_year"] = year
    text = f"{game.leader.name} slew the dragon {d['name']}"
    w.history.append({"year": year, "kind": "dragon_slain", "text": text, "factions": [], "places": [],
                      "figures": [], "importance": 5, "player": True})
    amounts = {}
    for s in tribute_towns(w, d, 20.0):
        s.status.pop("tribute", None)
        realm = fx.realm_of_settlement(w, s)
        if realm is not None:
            amounts[realm.id] = max(amounts.get(realm.id, 0.0), 20.0)
    lair = w.sites[d["lair"]]
    reputation.deed(game, f"slew the dragon {d['name']}", amounts, x=lair.x, y=lair.y,
                    immediate=tuple(amounts), fame=25, importance=5, news_text=text)
    game.say(f"<good>{d['name']} is dead.</> <dim>They will be telling this one long after you are gone.</>", "good")
    if game.party[1:]:
        from realmwalker.game.companions import react

        react(game, "victory", "hard_fight", "discovery")
    game.dirty = True
