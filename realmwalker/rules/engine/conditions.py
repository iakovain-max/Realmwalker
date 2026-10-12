"""The 2024 conditions, as data (data/conditions.json, the Rules Glossary of the Player's Handbook).

A fighter keeps its conditions as a dict, name -> rounds left (-1: until something ends it), with what caused them in
`Fighter.sources` (name -> fighter id) where that matters (Frightened, Grappled, Charmed). `expand` adds what each
condition brings with it (Unconscious brings Incapacitated and Prone), so the rest of the kernel asks one question:
does anything on this creature say X?
"""

from __future__ import annotations

IDS = ("blinded", "charmed", "deafened", "frightened", "grappled", "incapacitated", "invisible", "paralyzed",
       "petrified", "poisoned", "prone", "restrained", "stunned", "unconscious")


def table(tables) -> dict[str, dict]:
    return tables.conditions["conditions"]


def name(tables, cid: str) -> str:
    d = table(tables).get(cid)
    return d["name"] if d else cid.replace("_", " ").capitalize()


def expand(tables, names) -> frozenset[str]:
    """These conditions and everything they include (only the ones the rules know)."""
    key = frozenset(names)
    cache = tables.__dict__.setdefault("_condition_cache", {})
    hit = cache.get(key)
    if hit is None:
        defs = table(tables)
        out: set[str] = set()
        todo = [n for n in key if n in defs]
        while todo:
            n = todo.pop()
            if n not in out:
                out.add(n)
                todo.extend(defs[n].get("includes", []))
        hit = cache[key] = frozenset(out)
    return hit


def flags(tables, names, key: str) -> list[tuple[str, object]]:
    """(condition, value) for every active condition that says `key`, in a fixed order."""
    defs = table(tables)
    return [(n, defs[n][key]) for n in sorted(expand(tables, names)) if defs[n].get(key)]


def has_flag(tables, names, key: str) -> bool:
    defs = table(tables)
    return any(defs[n].get(key) for n in expand(tables, names))


def immune_to(tables, names, cid: str) -> bool:
    """Whether a condition already on a creature keeps this one off (Petrified keeps off Poisoned)."""
    defs = table(tables)
    return any(cid in defs[n].get("immune", []) for n in expand(tables, names))


def exhaustion(tables) -> dict:
    return tables.conditions["exhaustion"]
