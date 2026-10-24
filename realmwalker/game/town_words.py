"""Words for towns: how a place reads as you arrive, its inns' names, and what an inn's common room is like.
All of it written once from built-in text (data/fallback_text.json, each people's own words in data/towns.json) and
kept in the save, so a place reads the same every time."""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.rng import RNG
from realmwalker.game.people import Town

KIND_WORDS = {"hamlet": "hamlet", "village": "village", "town": "market town", "city": "walled city", "hold": "dwarven hold",
              "elfhall": "elven hall"}


def town_description(game, settlement, rng: RNG) -> str:
    tables = game.tables.fallback["settlement"]
    if getattr(game.tables, "towns", None):  # each people's own words for their places (data/towns.json)
        from realmwalker.world.towns.plan import style_for

        own = style_for(game.tables, settlement).get("words")
        if own:
            tables = {**tables, **own}
    land = game.biome_def(settlement.x, settlement.y)["name"]
    values = {"name": settlement.name, "kind": KIND_WORDS.get(settlement.kind, settlement.kind),
              "land": land, "land_in": "on the coast" if land == "coast" else f"in the {land}",
              "season": game.moment.season}
    text = textgen.tidy(textgen.fill(rng.choice(tables["passage"]), rng, tables, values))
    from realmwalker.world import marks

    marked = marks.words(game.world, game.tables, settlement, "description", rng)  # (what it is going through now)
    return text + (" " + " ".join(marked) if marked else "")


def inn_name(game, rng: RNG) -> str:
    tavern = game.tables.fallback["tavern"]
    names = game.tables.names["cultures"]
    family = rng.choice(next(iter(names.values()))["family"])  # tavern names stay homely, whatever the town
    return textgen.fill(rng.choice(tavern["name_pattern"]), rng, tavern, {"family": family})


def taproom(game, town: Town, building: int) -> str:
    """What the common room of this inn is like: written once, kept in the save, the same every time you
    push the door open."""
    kept = town.flags.setdefault("taprooms", {})
    said = kept.get(str(building))
    if said:
        return said
    tables = game.tables.fallback["tavern"]
    rng = game.world.rng.child(f"taproom/{town.settlement}/{building}")
    parts = [textgen.fill(rng.choice(tables["description"]), rng, tables)]
    if rng.chance(0.6):
        parts.append(rng.choice(tables["overheard"]))
    text = textgen.tidy(" ".join(parts))
    kept[str(building)] = text
    return text
