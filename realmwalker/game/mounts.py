"""Riding (2026-10, Anton: "you can buy a horse and lead it, but it doesn't in any way speed you up"; "everyone moves as
fast as the slowest member, so everyone needs a horse to go at horse speed").

The party travels together, so it goes at the pace of its slowest member. Each living member who travels with you
rides one of the party's animals, the fastest first; whoever is left over walks, and then the whole party walks with
them. When everyone rides, the slowest mount ridden sets the pace: on roads and open country at the animal's full
speed, through woods at part of it, and through marsh and mountain not at all (there you lead the beasts). A rider
tires less than a walker even at a walking pace, and a lame leg does not slow a rider.

The animals are the party's (they are kept on the leader, `Character.animals`); the numbers are in
data/economy.json: "animals" (ride: travel time on good riding ground, 1 = no faster) and "ride_lands" (how much of
a mount's speed each land allows). Before this, the speed was there but nothing showed it: every plan, estimate and
forecast still counted the walk, and a party with one horse among three went at a walk without a word as to why.
"""

from __future__ import annotations

from realmwalker.rules.character import Character

DEFAULT_LANDS = {"plains": 1.0, "coast": 1.0, "tundra": 1.0, "desert": 1.0, "hills": 1.0}


def specs(tables) -> dict:
    return {k: v for k, v in tables.economy["animals"].items() if not k.startswith("_")}


def herd(game) -> list[dict]:
    """The party's animals."""
    return list(game.leader.animals) if game.party else []


def riders(game) -> list[Character]:
    """Who travels with the party and needs a mount: the living members (not those told to wait)."""
    return [c for c in game.party if c.alive]


def speed_of(tables, animal: dict) -> float:
    return float(specs(tables).get(animal.get("kind"), {}).get("ride", 1.0))


def assign(game) -> tuple[dict[int, dict], list[Character]]:
    """Who rides what: the fastest animals go to the members in party order (id(member) -> animal), and the list of
    those left on foot."""
    mounts = sorted((a for a in herd(game) if a.get("kind") in specs(game.tables)),
                    key=lambda a: speed_of(game.tables, a))
    out: dict[int, dict] = {}
    walkers = []
    for c in riders(game):
        if mounts:
            out[id(c)] = mounts.pop(0)
        else:
            walkers.append(c)
    return out, walkers


def mount_of(game, char: Character) -> dict | None:
    return assign(game)[0].get(id(char))


def all_mounted(game) -> bool:
    people = riders(game)
    return bool(people) and not assign(game)[1]


def pace_animal(game) -> dict | None:
    """The slowest animal being ridden, which sets the party's pace when everyone rides (None if anyone walks)."""
    ridden, walkers = assign(game)
    if walkers or not ridden:
        return None
    return max(ridden.values(), key=lambda a: speed_of(game.tables, a))


def land_share(game, x: int, y: int) -> float:
    """How much of a mount's speed this land allows (1 open country, 0 marsh and mountain)."""
    lands = game.tables.economy.get("ride_lands", DEFAULT_LANDS)
    return float(game.tables.biomes.lookup(lands, game.land_key(x, y), 0.0))


def step_factor(game, x0: int, y0: int, x1: int, y1: int) -> float:
    """Travel time multiplier for one overworld step when the whole party rides (1.0 if anyone walks). Roads are
    good riding everywhere, as step_minutes counts a road: both ends on it."""
    slowest = pace_animal(game)
    if slowest is None:
        return 1.0
    ride = speed_of(game.tables, slowest)
    if ride >= 1.0:
        return 1.0
    w = game.world
    share = 1.0 if (w.road[x0, y0] and w.road[x1, y1]) else min(land_share(game, x0, y0), land_share(game, x1, y1))
    return 1.0 - (1.0 - ride) * max(0.0, min(1.0, share))


def activity_for(game, char: Character, activity: str) -> str:
    """Walking on the big map, a member with a mount rides it (even at the walkers' pace): it tires less."""
    if activity != "walk" or game.in_local or not game.party:
        return activity
    return "ride" if mount_of(game, char) is not None else activity


def kind_name(game, animal: dict) -> str:
    return str(specs(game.tables).get(animal.get("kind"), {}).get("name", "animal"))


def first(c: Character) -> str:
    return c.name.split()[0] if c.name else "Someone"


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def summary(game) -> str:
    """One plain line on how the party travels: who rides what, and why it goes at a walk if it does."""
    animals = herd(game)
    people = riders(game)
    if not animals:
        return ""
    ridden, walkers = assign(game)
    if walkers:
        on_foot = _and([first(c) for c in walkers]) if len(people) > 1 else "You"
        verb = "walks" if len(walkers) == 1 and len(people) > 1 else "walk"
        if not ridden:
            return ""
        return (f"{on_foot} {verb}, with nothing to ride: the party goes at a walk. "
                f"<dim>Everyone needs a mount to go at a mount's pace.</>")
    slowest = pace_animal(game)
    ride = speed_of(game.tables, slowest)
    if ride >= 1.0:
        return (f"{'Everyone rides' if len(people) > 1 else 'You ride'}, at a walk: "
                f"{'a mule is' if slowest.get('kind') == 'mule' else 'these are'} no faster than a walker, only less "
                f"tiring.")
    quicker = int(round((1.0 / ride - 1.0) * 100))
    pace = "" if len(people) == 1 else f" (the {kind_name(game, slowest)} sets the pace)"
    return (f"{'Everyone rides' if len(people) > 1 else 'You ride'}{pace}: about {quicker}% further in an hour on roads "
            f"and open country, less in woods, and nothing gained in marsh or mountains.")


def who_rides_what(game) -> list[str]:
    """'Osric on Bess, the riding horse' for each rider; 'Muriel on foot' for each walker; spare animals."""
    ridden, walkers = assign(game)
    out = []
    used = set()
    for c in riders(game):
        a = ridden.get(id(c))
        if a is not None:
            used.add(id(a))
            out.append(f"{first(c)} on {a['name']}, the {kind_name(game, a)}")
        else:
            out.append(f"{first(c)} on foot")
    spare = [a for a in herd(game) if id(a) not in used]
    if spare:
        out.append("led: " + _and([f"{a['name']} the {kind_name(game, a)}" for a in spare]))
    return out
