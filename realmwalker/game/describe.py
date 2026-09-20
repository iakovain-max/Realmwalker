"""Look / examine text for overworld tiles and local-map cells (built-in templates; the AI adds
richer descriptions of important places in later milestones). Returns marked-up text."""

from __future__ import annotations

from realmwalker.game.state import GameState

DANGER_WORDS = [
    (1, "safe enough", "good"), (3, "unsafe", "fg"), (5, "dangerous", "warn"),
    (7, "very dangerous", "danger"), (99, "deadly", "danger"),
]
TEMP_WORDS = [(-10, "bitterly cold"), (0, "freezing"), (7, "cold"), (14, "cool"), (22, "mild"), (28, "warm"), (99, "hot")]


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def danger_text(level: int) -> str:
    for limit, word, color in DANGER_WORDS:
        if level <= limit:
            return f"<{color}>{word}</>"
    return "unknown"


def temperature_word(celsius: float) -> str:
    for limit, word in TEMP_WORDS:
        if celsius < limit:
            return word
    return "hot"


def typical_temperature(game: GameState, x: int, y: int) -> float:
    return float(game.world.temperature[x, y]) + game.moment.month.temp_offset


def settlement_line(game: GameState, s) -> str:
    spec = game.tables.sites["settlement_types"][s.kind]
    culture = game.tables.names["cultures"].get(s.culture, {}).get("label", s.culture)
    walls = ", walled" if s.walled else ""
    size = f"about {round(s.population, -1 if s.population < 1000 else -2):,} people"
    line = f"<place>{s.name}</>: {spec['name']}{walls}, {size}. <dim>{culture} folk.</>"
    line += holder_line(game, s)
    p = getattr(game, "player", None)  # (the character creation screen shows these lines too)
    if p is not None and abs(s.x - p.x) + abs(s.y - p.y) <= 12:  # close enough to see the smoke
        st = s.status
        words = [w for key, w in (("siege", "<danger>under siege</>"), ("plague", "<danger>plague</>"),
                                  ("sacked", "<danger>sacked</>"), ("burned", "<warn>burned</>"),
                                  ("famine", "<warn>hungry</>"), ("raided", "<warn>raided</>")) if st.get(key) is not None]
        if words:
            line += " " + ", ".join(words).capitalize() + "."
    return line


def holder_line(game: GameState, s) -> str:
    """ Held by House Draycott, sworn to the Kingdom of Ashmere."""
    from realmwalker.world import factions as fx

    owner = fx.owner_of(game.world, s)
    if owner is None:
        return " <dim>No lord holds it.</>" if game.world.factions else ""
    top = fx.top_liege(game.world, owner)
    if owner.seat == s.id and owner.kind in ("kingdom", "free_city", "clan", "highland_clan", "elven_realm"):
        return f" <dim>Seat of</> <info>{owner.name}</>."
    if owner.seat == s.id:
        text = f" <dim>Seat of</> <info>{owner.name}</>"
    else:
        text = f" <dim>Held by</> <info>{owner.name}</>"
    if top is not None and top is not owner:
        text += f"<dim>, sworn to {top.name}</>"
    return text + "."


def area_text(world, area) -> str:
    """The AI's words for a named stretch of country, if it has written any."""
    return world.politics.get("area_text", {}).get(str(area.id), "")


def area_facts(game, area) -> dict:
    """What the AI is told about a region: only what is really there."""
    import math

    w = game.world
    biome = game.tables.biomes.defs[game.tables.biomes.index[area.kind]] if area.kind in game.tables.biomes.index \
        else {"name": area.kind}
    near = sorted((s for s in w.settlements if math.hypot(s.x - area.x, s.y - area.y) <= 12),
                  key=lambda s: math.hypot(s.x - area.x, s.y - area.y))[:3]
    sites = sorted((s for s in w.sites if math.hypot(s.x - area.x, s.y - area.y) <= 10),
                   key=lambda s: math.hypot(s.x - area.x, s.y - area.y))[:2]
    from realmwalker.world import factions as fx

    realm = fx.realm_at(w, area.x, area.y)
    m = game.moment
    return {
        "name": area.name,
        "land": biome.get("name", area.kind),
        "size": "small" if area.size < 30 else "wide" if area.size < 120 else "vast",
        "season": m.season,
        "weather": game.weather.kind,
        "danger": str(int(w.danger[area.x, area.y])),
        "realm": realm.name if realm is not None else "no lord anyone here obeys",
        "towns": ", ".join(s.name for s in near) or "nowhere anyone lives",
        "sites": ", ".join(s.name for s in sites) or "nothing anyone built",
    }


def keep_area_text(world, area, data: dict) -> bool:
    if not data or not data.get("description"):
        return False
    kept = world.politics.setdefault("area_text", {})
    if str(area.id) in kept:
        return False
    kept[str(area.id)] = str(data["description"]).strip()
    return True


def describe_overworld(game: GameState, x: int, y: int) -> str:
    w = game.world
    if not w.in_bounds(x, y):
        return "Beyond the edge of the known world."
    p = game.player
    settlement = w.settlement_at(x, y)
    if not p.explored[x, y]:
        if settlement is not None and settlement.id in p.known_settlements:
            return settlement_line(game, settlement) + "\n<dim>You have heard of it, but never been.</>"
        return "<dim>Land you have not seen.</>"
    lines = []
    if (x, y) == (p.x, p.y):
        lines.append("<name>You are here.</>")
    if settlement is not None:
        lines.append(settlement_line(game, settlement))
    site = w.site_at(x, y)
    if site is not None:
        spec = game.tables.sites["site_types"].get(site.kind, {})
        lines.append(f"<place>{cap(site.name)}</>. {spec.get('desc', '')}")
    biome = game.biome_def(x, y)
    area = w.area_at(x, y)
    where = f"{cap(biome['name'])}" + (f", in <place>{area.name}</>" if area else "")
    lines.append(where + ".")
    if w.factions and settlement is None:
        from realmwalker.world import factions as fx

        lord = fx.lord_at(w, x, y)
        if lord is not None:
            top = fx.top_liege(w, lord)
            if lord.kind == "tribe":
                lines.append(f"<warn>{cap(lord.name)} roam here.</>")
            else:
                lines.append(f"<dim>The lands of</> <info>{lord.name}</>" +
                             (f"<dim>, sworn to {top.name}</>" if top is not None and top is not lord else "") + ".")
    extras = []
    if w.river[x, y]:
        river = w.river_at(x, y)
        kind = {1: "A stream", 2: "A river", 3: "A great river"}[int(w.river[x, y])]
        extras.append(f"{kind} runs here" + (f": <place>{river.name}</>" if river else "") + ".")
    if w.road[x, y] and settlement is None:
        extras.append("A road passes through.")
    if extras:
        lines.append(" ".join(extras))
    if biome["passable"]:
        height = int(w.elevation[x, y])
        temp = typical_temperature(game, x, y)
        lines.append(f"<dim>{height:,} m above the sea; {temperature_word(temp)} at this time of year.</>")
        lines.append(f"The wilds here are {danger_text(int(w.danger[x, y]))}.")
        if (x, y) != (p.x, p.y) and abs(x - p.x) <= 1 and abs(y - p.y) <= 1:
            minutes = game.step_minutes(p.x, p.y, x, y)
            if minutes:
                lines.append(f"<dim>About {max(1, round(minutes / 60))} hour(s) to walk there.</>")
    return "\n".join(lines)


def describe_local(game: GameState, x: int, y: int) -> str:
    lm = game.local
    if lm is None or not lm.in_bounds(x, y):
        return ""
    p = game.player
    if not lm.seen[x, y]:
        return "<dim>You cannot see there.</>"
    t = game.tables.terrain[int(game.remap_for(lm)[lm.terrain[x, y]])]
    lines = []
    if (x, y) == (p.lx, p.ly):
        lines.append("<name>You are here.</>")
    lines.append(f"<fg>{cap(t['name'])}.</> {t['desc']}")
    pile = lm.items.get((x, y))
    if pile:
        names = ", ".join(game.tables.items.name(i) for i in pile[:5])
        lines.append(f"<loot>On the ground: {names}.</>")
    if lm.kind == "settlement":
        from realmwalker.game.people import describe_npc, npc_at

        npc = npc_at(game, x, y)
        if npc is not None and (x, y) != (p.lx, p.ly):
            lines.insert(0, describe_npc(game, npc) + " <dim>(walk into them to talk)</>")
    b = lm.building_at(x, y)
    if b is not None:
        kind = {"house": "a house", "inn": "an inn", "temple": "a temple", "smithy": "a smithy", "store": "a shop",
                "healer": "a healer's house", "stable": "a stable", "hall": "the hall", "keep": "the keep"}.get(b.kind, b.kind)
        name = ""
        s = game.world.settlement_at(p.x, p.y)
        town = game.world.towns.get(s.id) if s is not None else None
        if town is not None:
            bi = lm.buildings.index(b)
            name = town.names.get(bi, "")
            if name and bi not in town.names_seen:
                town.names_seen.append(bi)
        lines.append(f"<dim>Part of {kind}{': ' + name if name else ''}.</>")
    return "\n".join(lines)
