"""The selector language of blueprints (docs/ADVENTURES.md §8.5): how a blueprint names its places and its people.

A selector is `name(arg, ...)`; `a | b` tries `a`, then `b`; `hidden(n, a, b, ...)` binds a hidden variable from up
to n candidates; a path names something already bound (`threat.home`, `villain.slayer`, `home.level(1)`,
`home.deepest`, `town.outskirts`, `town.inn`). Arguments are numbers (distance bands in tiles), paths, nested
selectors, and `|`-joined words (`site_style(crypt|temple, 6, 30)`).

`parse(text)` turns the text into a tree once (story/check.py parses every selector of the data at start-up); the
resolvers are registered by name with `@selector("name")` and run by the forge.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# What a path may ask of a place (`home.deepest`): story/forge.py resolves them.
PLACE_PARTS = {"level", "deepest", "outskirts", "inn"}
# What a path may start with besides a place or a role bound by this blueprint.
ROOTS = {"threat", "villain", "hidden", "places", "tier"}

SELECTORS: dict[str, object] = {}


def selector(name: str):
    """Register a resolver: fn(forge, *args) -> a list of candidates (best first), or [] when nothing fits."""
    def wrap(fn):
        SELECTORS[name] = fn
        return fn
    return wrap


@dataclass
class Call:
    name: str
    args: list = field(default_factory=list)


@dataclass
class Path:
    parts: list  # [str | Call]: "home", Call("level", [1])


@dataclass
class Words:
    words: list


@dataclass
class Alt:
    options: list  # tried in order


class SelectorError(ValueError):
    pass


def _split(text: str, sep: str) -> list[str]:
    """Split at `sep` outside brackets."""
    out, depth, cur = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                raise SelectorError(f"a ')' too many in '{text}'")
        if ch == sep and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if depth:
        raise SelectorError(f"a '(' is not closed in '{text}'")
    out.append("".join(cur))
    return [p.strip() for p in out]


def _word(text: str) -> bool:
    return bool(text) and all(c.isalnum() or c == "_" for c in text)


def _term(text: str):
    text = text.strip()
    if not text:
        raise SelectorError("an empty selector")
    try:
        return int(text)
    except ValueError:
        pass
    if "(" not in text and "|" in text:
        words = [w.strip() for w in text.split("|")]
        if not all(_word(w) for w in words):
            raise SelectorError(f"'{text}' is not a list of words")
        return Words(words)
    parts = _split(text, ".")
    out = []
    for p in parts:
        if p.endswith(")") and "(" in p:
            name, rest = p.split("(", 1)
            name = name.strip()
            if not _word(name):
                raise SelectorError(f"'{name}' is not a name")
            inner = rest[:-1].strip()
            args = [_arg(a) for a in _split(inner, ",")] if inner else []
            out.append(Call(name, args))
        elif _word(p):
            out.append(p)
        else:
            raise SelectorError(f"cannot read '{p}'")
    if len(out) == 1 and isinstance(out[0], Call):
        return out[0]
    return Path(out)


def _arg(text: str):
    alts = [a for a in _split(text, "|")]
    if len(alts) > 1 and all("(" not in a and "." not in a for a in alts):
        return _term(text)  # (style words: crypt|temple)
    return parse(text)


def parse(text: str):
    """The tree of a selector's text; raises SelectorError when it cannot be read."""
    alts = _split(str(text), "|")
    if len(alts) > 1 and all(_word(a) for a in alts):
        return Words(alts)
    nodes = [_term(a) for a in alts]
    return nodes[0] if len(nodes) == 1 else Alt(nodes)


def calls(node) -> list[Call]:
    """Every selector call in a tree (to check that each one exists)."""
    out = []
    if isinstance(node, Call):
        out.append(node)
        for a in node.args:
            out += calls(a)
    elif isinstance(node, Alt):
        for o in node.options:
            out += calls(o)
    elif isinstance(node, Path):
        for p in node.parts[1:]:
            if isinstance(p, Call):
                for a in p.args:
                    out += calls(a)
        if isinstance(node.parts[0], Call):
            out += calls(node.parts[0])
    return out


def paths(node) -> list[Path]:
    out = []
    if isinstance(node, Path):
        out.append(node)
    elif isinstance(node, Call):
        for a in node.args:
            out += paths(a)
    elif isinstance(node, Alt):
        for o in node.options:
            out += paths(o)
    return out


# ---------------------------------------------------------------------------- the places of Part A
# Each resolver: fn(forge, *args) -> candidates, best first. Distances are in tiles from the reference place (or,
# when a selector takes none, from the threat's home).
def _band(forge, ref, lo, hi):
    from realmwalker.game.story import places

    w = forge.world
    out = []
    for s in w.settlements:
        d = places.dist(w, ref, {"settlement": s.id})
        if lo <= d <= hi:
            out.append((d, s))
    out.sort(key=lambda p: (p[0], p[1].id))
    return out


@selector("settlement_near")
def _settlement_near(forge, ref, lo, hi):
    """The settlements in the band round `ref`, nearest first; the threat's own stakes before the rest."""
    stakes = set(forge.threat.get("stakes", []))
    found = _band(forge, ref, lo, hi)
    return [{"settlement": s.id} for d, s in sorted(found, key=lambda p: (p[1].id not in stakes, p[0], p[1].id))]


@selector("settlement_with")
def _settlement_with(forge, words, lo, hi):
    """A settlement with a building of that kind (a temple: every place bigger than a hamlet; a library: a city)."""
    from realmwalker.world.towns.layouts import SPECIAL

    words = words if isinstance(words, list) else [words]
    out = []
    for d, s in _band(forge, forge.home, lo, hi):
        has = set(SPECIAL.get(s.kind, [])) | ({"library"} if s.kind == "city" or getattr(s, "great", False) else set())
        if all(w in has for w in words):
            out.append({"settlement": s.id})
    return out


@selector("settlement_great")
def _settlement_great(forge, lo, hi):
    return [{"settlement": s.id} for d, s in _band(forge, forge.home, lo, hi) if getattr(s, "great", False)]


@selector("road_tile_near")
def _road_tile_near(forge, ref, lo, hi):
    """Open country by a road in the band round `ref` (a field for a set piece: a kill, a ford, a crossroads)."""
    from realmwalker.game.story import places

    w = forge.world
    x0, y0 = places.xy(w, ref)
    out = []
    for dx in range(-int(hi), int(hi) + 1):
        for dy in range(-int(hi), int(hi) + 1):
            x, y = x0 + dx, y0 + dy
            d = (dx * dx + dy * dy) ** 0.5
            if not lo <= d <= hi or not w.in_bounds(x, y) or not w.road[x, y]:
                continue
            if w.settlement_at(x, y) is not None or w.site_at(x, y) is not None:
                continue
            if not forge.game.biome_def(x, y)["passable"]:
                continue
            out.append((d, x, y))
    out.sort()
    return [{"tile": [x, y]} for d, x, y in out]


@selector("site_style")
def _site_style(forge, words, lo, hi):
    from realmwalker.game.story import places
    from realmwalker.world import dungeon as gen

    w = forge.world
    words = words if isinstance(words, list) else [words]
    out = []
    for s in w.sites:
        d = places.dist(w, forge.home, {"site": s.id})
        if lo <= d <= hi and gen.style_for(w, s) in words:
            out.append((d, s.id))
    out.sort()
    return [{"site": sid} for d, sid in out]


@selector("weakness_of")
def _weakness_of(forge, villain):
    """What the villain fears (villains.json weaknesses: by creature id, else by creature type)."""
    weak = forge.tables.villains.get("weaknesses", {})
    creature = forge.threat["villain"].get("creature", "")
    kind = forge.tables.creatures[creature].get("type", "") if creature in forge.tables.creatures else ""
    return [{"weakness": w["id"]} for w in weak.get(creature, weak.get(kind, []))]


# ---------------------------------------------------------------------------- the routes to a truth (learn)
@selector("sage")
def _sage(forge, town):
    """A learned person of that town who can tell it, for a price: its priest."""
    return [{"how": "talk", "who": {"job": "priest", "settlement": town["settlement"]}}] if "settlement" in town else []


@selector("ask")
def _ask(forge, who):
    """Someone of the cast who knows it (the hunter ally)."""
    return [{"how": "talk", "who": who}] if who else []


@selector("nature")
def _nature(forge, at):
    """A skill check at the place where the signs are (a kill, a carcass)."""
    return [{"how": "check", "skill": "nature", "at": at}]


@selector("divine")
def _divine(forge):
    """Divination: Augury, Commune, Legend Lore and the rest are told the truth (game/divining.questions)."""
    return [{"how": "divine"}]
