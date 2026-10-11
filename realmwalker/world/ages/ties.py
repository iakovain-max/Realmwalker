"""A new character's ties to the lived history (world/ages): the real war a soldier marched in, the real beast a folk
hero drove off, the real lord a noble's house is sworn to, the real priest who raised an acolyte.

Called by rules/creation.make_ties after the plain ties are made; it changes their words and references in place and
may add a sentence.
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.world import factions as fx


def enrich(world, tables, kind: str, character, start, values: dict, refs: dict, rng) -> str:
    """Root a background in the world's real past. Returns a sentence to add to the tie (or "")."""
    data = tables.history.get("ties", {})
    if not data:
        return ""
    year = tables.calendar.at(world.time).year
    if kind == "lord_served":
        return _soldier(world, data, refs, year, rng)
    if kind == "home_village":
        _folk_hero(world, tables, data, start, values, refs, year, rng)
    elif kind == "noble_house":
        return _noble(world, data, refs, rng)
    elif kind == "temple":
        priests = [f for f in world.figures.values() if f.alive and f.kind == "person" and f.job == "priest"
                   and f.home == f"S{start.id}"]
        if priests:
            values["priest"] = max(priests, key=lambda f: (f.fame, -f.id)).full_name()
    return ""


def _soldier(world, data: dict, refs: dict, year: int, rng) -> str:
    f = world.factions.get(refs.get("faction", -1))
    if f is None:
        return ""
    sides = {f.id}
    top = fx.top_liege(world, f)
    if top is not None:
        sides.add(top.id)
    wars = [w for w in world.wars if w.get("battles") and w.get("name") and
            (w.get("attacker") in sides or w.get("defender") in sides or
             sides & set(w.get("allies", {}).get("attacker", [])) or sides & set(w.get("allies", {}).get("defender", [])))
            and year - (w.get("end_year") or year) <= 25]
    if not wars:
        return ""
    war = max(wars, key=lambda w: (w.get("end_year") or year, w["id"]))
    refs["war"] = war["id"]
    return textgen.fill(rng.choice(data["war"]), rng, {}, {"war": war["name"], "year": str(war["year"])})


def _folk_hero(world, tables, data: dict, start, values: dict, refs: dict, year: int, rng) -> None:
    events = [e for e in world.history if start.id in e.get("places", ()) and e.get("kind") in
              ("beast_attack", "dragon", "raid", "burned") and year - e["year"] <= 25]
    if not events:
        return
    e = max(events, key=lambda e: (e["year"], e.get("id", 0)))
    beasts = [world.figures[h] for h in e.get("figures", ()) if h in world.figures and
              world.figures[h].kind in ("beast", "dragon")]
    if beasts:
        beast = beasts[0]
        lair = beast.home if beast.home.startswith("X") else ""
        site = world.sites[int(lair[1:])].name if lair and int(lair[1:]) < len(world.sites) else "the wild"
        values["deed"] = textgen.fill(rng.choice(data["deed_beast"]), rng, {},
                                      {"beast": f"{beast.name} {beast.epithet}".strip(), "site": site})
        refs["foe"] = beast.id
        return
    tribes = [world.factions[f] for f in e.get("factions", ()) if f in world.factions and
              world.factions[f].kind == "tribe"]
    if tribes:
        values["deed"] = textgen.fill(rng.choice(data["deed_raid"]), rng, {}, {"tribe": tribes[0].name})
        refs["foe_faction"] = tribes[0].id


def _noble(world, data: dict, refs: dict, rng) -> str:
    """A noble's own small house (game/reputation makes it) holds its lands from the real lord of its seat: say who."""
    place = refs.get("place")
    if place is None or not 0 <= place < len(world.settlements):
        return ""
    lord = fx.owner_of(world, world.settlements[place])
    leader = fx.leader_of(world, lord)
    if lord is None or leader is None or not leader.alive:
        return ""
    refs["sworn_to"] = lord.id
    return textgen.fill(rng.choice(data["noble"]), rng, {}, {"house": lord.name, "lord": leader.full_name()})
