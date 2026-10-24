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
