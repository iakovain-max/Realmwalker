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
    return f"<place>{s.name}</>: {spec['name']}{walls}, {size}. <dim>{culture} folk.</>"


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
    b = lm.building_at(x, y)
    if b is not None:
        kind = {"house": "a house", "inn": "an inn", "temple": "a temple", "smithy": "a smithy",
                "hall": "a guild hall", "keep": "the keep"}.get(b.kind, b.kind)
        lines.append(f"<dim>Part of {kind}.</>")
    return "\n".join(lines)
